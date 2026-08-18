"""Golden: the real per-frame ``orderFpo`` writer, executed under Unicorn.

``fcn.1028b8d0`` (``PakonIMAu.dll``, md5 ``eea9dcf78ee21d4f7c515a6c2512242d``)
is the function that writes the per-scene ``orderFpo`` Y/U/V triple into
``pref_data`` (``scene+0x38a2``) — the value the SBA ``Preference`` stage then
consumes. docs/74 §73 confirmed it does so on real hardware (12/12, keyed on
the ``pref_data`` address); §74 pinned the three write instructions
(``0x1028c2be``/``2b6``/``2c2``); §75 live-confirmed the argument mapping and
built the v22 capture this harness feeds on.

**What makes this Tier 1** (CLAUDE.md's own hierarchy): nothing here models
or re-implements the vendor's arithmetic. The real DLL bytes execute, on the
real argument buffers captured off the real scanner, and the value the real
code writes is compared against the value the real hardware was observed to
produce for the same scene. There is no tuning knob anywhere in the loop —
it either reproduces the captured triple exactly or it does not.

Why this could not be built earlier, and what changed: docs/74 §72.6 refused
to build it because three load-bearing inputs were unknown and inventing them
is forbidden. §73.3 settled the switch selector live (``arg3`` is 0 on this
path, and — refuting the static read — 1 on the other half of the calls);
§73.4/§75.1 settled the argument mapping; and v22 dumped the six pointer
buffers whose *contents* had never been captured. Every input below is real
captured data.

Usage::

    python3 pakon_orderfpo_golden.py <PakonIMAu.dll> [capture.jsonl]

Exits non-zero if any scene fails to reproduce.
"""

from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

from unicorn import (UC_ARCH_X86, UC_HOOK_MEM_INVALID, UC_MODE_32, Uc, UcError)
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP,
                               UC_X86_REG_ESP, UC_X86_REG_FPCW)

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
RET_MAGIC = 0x00110000
FPCW_WINDOWS = 0x027F
PAGE = 0x1000

ORDER_FPO_CALC = 0x1028B8D0

# The nine dumped buffers, in argument order. Args 3/4/8/9 are immediates
# (all 0 on the live path, docs/74 §73.3/§73.4) and need no buffer.
ARG_DUMP = {
    0: "arg0_dens",
    1: "arg1_cbank",
    2: "arg2_388c",
    5: "arg5_blob",
    6: "arg6_unknown",
    7: "arg7_3c34",
    10: "arg10_local2",
    11: "fos_dmin",
    12: "pref_data_before",
}


def _align_up(n: int) -> int:
    return (n + PAGE - 1) & ~(PAGE - 1)


class Emu:
    """PE load plus real-address mapping of captured argument buffers.

    Captured buffers are mapped at the addresses they really had in the
    vendor process (all below ``IMAGE_BASE``), not relocated into a synthetic
    heap. That matters: if any structure holds a pointer to another, it
    resolves to the right place instead of silently reading poison.
    """

    def __init__(self, pe: bytes):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.pe = pe
        self._load()
        self.uc.mem_map(0, PAGE)                    # flat FS base, fs:[0]
        self.uc.mem_map(STACK, STACK_SZ)
        self.uc.mem_map(RET_MAGIC & ~0xFFF, PAGE)
        self.uc.mem_write(RET_MAGIC, b"\xC3")
        self.uc.mem_write(0, struct.pack("<I", 0xFFFFFFFF))
        self.uc.reg_write(UC_X86_REG_FPCW, FPCW_WINDOWS)
        self._mapped: set[int] = set()
        self.faults: list[str] = []
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)

    def _load(self) -> None:
        pe = self.pe
        e = struct.unpack_from("<I", pe, 0x3C)[0]
        ns = struct.unpack_from("<H", pe, e + 6)[0]
        osz = struct.unpack_from("<H", pe, e + 20)[0]
        opt = e + 24
        size_image = struct.unpack_from("<I", pe, opt + 56)[0]
        self.uc.mem_map(IMAGE_BASE, _align_up(size_image))
        self.uc.mem_write(IMAGE_BASE, pe[:PAGE])
        so = opt + osz
        for i in range(ns):
            o = so + i * 40
            vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
            if rsz == 0 or raddr == 0:
                continue
            d = pe[raddr:raddr + rsz]
            if len(d) < vsz:
                d += b"\x00" * (vsz - len(d))
            self.uc.mem_write(IMAGE_BASE + va, d[:max(vsz, rsz)])

    def place(self, addr: int, data: bytes) -> None:
        """Map (idempotently) the pages covering ``addr`` and write ``data``."""
        lo = addr & ~(PAGE - 1)
        hi = _align_up(addr + len(data))
        for p in range(lo, hi, PAGE):
            if p not in self._mapped:
                self.uc.mem_map(p, PAGE)
                # Poison unwritten bytes so a short dump cannot read as
                # plausible zeros -- an under-supplied buffer should be loud.
                self.uc.mem_write(p, b"\xCD" * PAGE)
                self._mapped.add(p)
        self.uc.mem_write(addr, data)

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"access={access} addr={address:#010x} size={size} "
            f"eip={uc.reg_read(UC_X86_REG_EIP):#010x}")
        return False

    def read(self, addr: int, n: int) -> bytes:
        return bytes(self.uc.mem_read(addr, n))

    def call(self, va: int, args=()) -> int:
        uc = self.uc
        esp = STACK + STACK_SZ - 0x20000
        blob = b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        esp -= len(blob)
        if blob:
            uc.mem_write(esp, blob)
        esp -= 4
        uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
        uc.reg_write(UC_X86_REG_ESP, esp)
        self.faults = []
        try:
            uc.emu_start(va, RET_MAGIC, timeout=0, count=200_000_000)
        except UcError as ex:
            raise RuntimeError(
                f"emu {va:#x} eip={uc.reg_read(UC_X86_REG_EIP):#010x}: {ex}"
                + ("; " + "; ".join(self.faults[:3]) if self.faults else "")
            ) from ex
        if self.faults:
            raise RuntimeError(f"emu {va:#x} faults: {self.faults[:3]}")
        return uc.reg_read(UC_X86_REG_EAX)


def load_capture(path: Path):
    """Return [(args, {label: (addr, bytes)}, expected_triple), ...].

    Only ``arg3 == 0`` calls are returned -- the other half of the real calls
    run the ``arg3 == 1`` case (docs/74 §73.3), which is a different path and
    does not write the triple. ``expected`` comes from the *next* Preference
    observation on the same ``pref_data`` address, which is exactly how §73.2
    established the write in the first place.
    """
    events = [json.loads(l) for l in path.open() if l.strip()]
    dumps: dict[int, dict] = defaultdict(dict)
    for d in events:
        if d.get("kind") == "buffer_dump":
            dumps[d["call_id"]][d["label"]] = d

    # pref_data addr -> triple, as seen by the real Preference call
    expected_by_addr: dict[str, tuple] = {}
    for d in events:
        if (d.get("kind") == "call" and d.get("event") == "enter"
                and d.get("hook_id") == "sba_preference"):
            r = dumps[d["call_id"]].get("pref_data")
            if r and r.get("readable"):
                expected_by_addr[r["addr"]] = struct.unpack_from(
                    "<hhh", bytes.fromhex(r["hex"]), 0)

    cases = []
    for d in events:
        if (d.get("kind") != "call" or d.get("event") != "enter"
                or d.get("hook_id") != "sba_order_fpo_calc"):
            continue
        sw = d.get("stack_dwords") or []
        if len(sw) < 13:
            continue
        args = [int(x, 16) for x in sw[:13]]
        if args[3] != 0:
            continue
        bufs = {}
        ok = True
        for label in set(ARG_DUMP.values()):
            r = dumps[d["call_id"]].get(label)
            if not r or not r.get("readable"):
                ok = False
                break
            bufs[label] = (int(r["addr"], 16), bytes.fromhex(r["hex"]))
        if not ok:
            continue
        pref_addr = dumps[d["call_id"]]["pref_data_before"]["addr"]
        exp = expected_by_addr.get(pref_addr)
        if exp is None:
            continue
        cases.append((d["call_id"], args, bufs, exp))
    return cases


def run_case(pe: bytes, args, bufs, verbose=False):
    emu = Emu(pe)
    for label, (addr, data) in bufs.items():
        emu.place(addr, data)
    emu.call(ORDER_FPO_CALC, args)
    pref = args[12]
    return struct.unpack("<hhh", emu.read(pref, 6))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    dll = Path(argv[1])
    cap = Path(argv[2]) if len(argv) > 2 else Path(
        "/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/"
        "live_hooks_20260817-115157.jsonl")
    pe = dll.read_bytes()
    cases = load_capture(cap)
    if not cases:
        print("no usable arg3==0 cases with all buffers readable in", cap)
        return 2

    print(f"{len(cases)} real arg3==0 calls with all 9 buffers readable")
    print(f"DLL   : {dll}")
    print(f"capture: {cap.name}")
    print("-" * 70)
    npass = nfail = nerr = 0
    for cid, args, bufs, exp in cases:
        try:
            got = run_case(pe, args, bufs)
        except RuntimeError as ex:
            nerr += 1
            print(f"  call {cid:4d}  ERROR  {ex}")
            continue
        if got == exp:
            npass += 1
            print(f"  call {cid:4d}  PASS   {got}")
        else:
            nfail += 1
            print(f"  call {cid:4d}  FAIL   got={got} want={exp}")
    print("-" * 70)
    print(f"pass {npass}  fail {nfail}  error {nerr}  of {len(cases)}")
    return 0 if (npass == len(cases)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
