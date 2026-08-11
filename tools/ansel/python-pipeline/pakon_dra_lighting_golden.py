#!/usr/bin/env python3
"""Dynamic (Unicorn) resolution of dra's find("lighting") branch polarity.

DISPUTE
-------
``tools/ansel/pipeline/shasta.go`` (AutoTonePorted comment) says:

    "One lookup, AnsDraCapabilityImpl::analyze's guarded find("lighting") at
    0x1022b2e5->0x1022b314, whose miss is fatal at 0x1022b35b, cannot be
    satisfied on this path at all -- "lighting" is not in CN-Enhanced's
    declared capability list -- so that branch must not be taken for a
    negative."

``docs/reports/autotone-scope-2026-08-10/dra.md`` disagreed, reading the
polarity the other way (miss continues, hit aborts), but could not settle it
statically and asked for dynamic confirmation.

WHAT THIS SCRIPT DOES
----------------------
Loads the real ``PakonIMAu.dll`` bytes into Unicorn (x86-32) and executes,
for real:

  * ``AnsSceneContext::find`` (0x10022a40) itself, called with a real,
    hand-built *empty* STL map (so the lookup is a real, unmocked "miss") --
    this is exactly the runtime condition for a colour negative, where
    "lighting" is never inserted into the scene context at all.
  * The exact dra call-site bytes, 0x1022b2e1 (build the "lighting" key
    string, call find, branch) through to whichever of the two landing
    addresses is actually reached:
      - 0x1022b3b0  -- the "continue" path (LUT building / normal return)
      - 0x1022b383  -- the "Failed in AnsSceneContext::find(...)." error
                       log + early-exit-via-jmp-0x1022b277 path

A second run mocks find() itself (hooked at its entry, 0x10022a40) to return
find()'s *other* documented contract -- an internal error/exception object
(non-null field 0) -- to independently confirm the OTHER landing address is
reachable and that the branch is a real two-way fork, not a NOP.

The mock contract for run 2 is not a guess: it is copied verbatim from
find()'s own machine code, read via complete disassembly of BOTH of its
real exit points (0x10022b3f "esi (non-null) -> [edi]" on the internal-error
path building an exception object via 0x1001ed90/0x10001580, and
0x10022e91-0x10022ea2 "sentinel (0x106b5bd4, contents 0) -> [edi]" on the
shared not-found/success-no-exception path) -- see module docstring bottom
for the full byte-level trace notes.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_dra_lighting_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import (
    Uc,
    UcError,
    UC_ARCH_X86,
    UC_MODE_32,
    UC_HOOK_CODE,
    UC_HOOK_MEM_INVALID,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x00200000
SCRATCH = 0x00100000
RET_MAGIC = 0x00110000

# ---------------------------------------------------------------------------
# Addresses under test
# ---------------------------------------------------------------------------
VA_DRA_BLOCK_START = 0x1022B2E1   # lea eax,[esp+0x28] -- build "lighting" key
VA_FIND = 0x10022A40              # AnsSceneContext::find
VA_CONTINUE = 0x1022B3B0          # "miss/no-error" landing (LUT build continues)
VA_ABORT_LOG = 0x1022B383         # "Failed in AnsSceneContext::find(...)." landing

# Imports find()/dra's snippet touch that we must supply (none of them do
# arithmetic relevant to the branch -- they are CRT/OS plumbing).
IAT_STR_CTOR_PBD = 0x10573394     # MSVCP71 basic_string(const char*)
IAT_STR_DTOR = 0x10573418         # MSVCP71 ~basic_string()
IAT_ENTER_CS = 0x10573028         # KERNEL32 EnterCriticalSection
IAT_LEAVE_CS = 0x10573044         # KERNEL32 LeaveCriticalSection

STR_LIGHTING_LITERAL = 0x10574048  # "lighting" C string already in .rdata


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    def __init__(self, pe: bytes):
        self.pe = pe
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self._load()
        uc.mem_map(0, 0x1000)  # flat FS base -> fs:[0] SEH head
        uc.mem_map(STACK, STACK_SZ)
        uc.mem_map(HEAP, HEAP_SZ)
        uc.mem_map(SCRATCH, 0x10000)
        uc.mem_map(RET_MAGIC & ~0xFFF, 0x1000)
        uc.mem_write(RET_MAGIC, b"\xC3")
        uc.mem_write(0, struct.pack("<I", 0xFFFFFFFF))
        self.brk = HEAP + 0x1000
        self._stub_next = SCRATCH + 0x1000
        self.faults: list[str] = []
        uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)

    def _load(self) -> None:
        pe = self.pe
        e = struct.unpack_from("<I", pe, 0x3C)[0]
        ns = struct.unpack_from("<H", pe, e + 6)[0]
        osz = struct.unpack_from("<H", pe, e + 20)[0]
        opt = e + 24
        size_image = struct.unpack_from("<I", pe, opt + 56)[0]
        self.uc.mem_map(IMAGE_BASE, _align(size_image))
        self.uc.mem_write(IMAGE_BASE, pe[:0x1000])
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

    def alloc(self, size: int, fill: bytes | None = None) -> int:
        p = self.brk
        self.brk = (self.brk + size + 0x40) & ~0xF
        if self.brk >= HEAP + HEAP_SZ:
            raise RuntimeError("emu heap exhausted")
        self.uc.mem_write(p, b"\x00" * size)
        if fill:
            self.uc.mem_write(p, fill)
        return p

    def stub(self) -> int:
        p = self._stub_next
        self._stub_next += 0x10
        self.uc.mem_write(p, b"\xC3")
        return p

    def w32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", int(v) & 0xFFFFFFFF))

    def wb(self, a: int, v: int) -> None:
        self.uc.mem_write(a, bytes([int(v) & 0xFF]))

    def r32(self, a: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def hook_stdcall(self, va: int, fn) -> None:
        """``fn(emu, args_addr) -> (eax, extra_pop_bytes)``.

        ``args_addr`` points at the first stack arg (i.e. esp+4 at the
        callee's entry, matching a __stdcall/cdecl call). ``extra_pop_bytes``
        is bytes to pop OFF TOP OF the already-popped return address, i.e.
        pass 4 for a "ret 4" (one stack arg consumed by callee), 0 for a
        plain "ret".
        """

        def cb(uc, address, size, _u):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            eax, pop = fn(self, esp + 4)
            if eax is not None:
                uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)

        self.uc.hook_add(UC_HOOK_CODE, cb, begin=va, end=va)

    def patch_iat_stub(self, iat_addr: int, fn) -> int:
        """Point an IAT slot at a fresh stub and hook the stub."""
        s = self.stub()
        self.w32(iat_addr, s)
        self.hook_stdcall(s, fn)
        return s

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"bad mem access={access} addr={address:#x} eip="
            f"{uc.reg_read(UC_X86_REG_EIP):#x}"
        )
        return False


# ---------------------------------------------------------------------------
# MSVC7.1 basic_string<char> layout: union{buf[16]/ptr} + size_t + size_t
# ---------------------------------------------------------------------------
def write_msvc_string(emu: Emu, obj_addr: int, text: bytes) -> None:
    n = len(text)
    if n < 16:
        emu.uc.mem_write(obj_addr, text + b"\x00" * (16 - n))
        emu.w32(obj_addr + 16, n)       # _Mysize
        emu.w32(obj_addr + 20, 15)      # _Myres (SSO capacity)
    else:
        buf = emu.alloc(n + 1, text + b"\x00")
        emu.w32(obj_addr, buf)
        emu.uc.mem_write(obj_addr + 4, b"\x00" * 12)
        emu.w32(obj_addr + 16, n)
        emu.w32(obj_addr + 20, n)


def install_common_hooks(emu: Emu) -> None:
    # basic_string(const char*) ctor -- __thiscall, ecx=this, 1 stack arg
    def str_ctor(e: Emu, args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        src = e.r32(args)
        s = bytearray()
        p = src
        while True:
            b = e.uc.mem_read(p, 1)[0]
            if b == 0:
                break
            s.append(b)
            p += 1
        write_msvc_string(e, this, bytes(s))
        return this, 4  # ret 4

    def str_dtor(e: Emu, args: int):
        return None, 0  # ret (plain), no-op

    def enter_cs(e: Emu, args: int):
        return None, 4  # ret 4 (one arg: LPCRITICAL_SECTION)

    def leave_cs(e: Emu, args: int):
        return None, 4

    emu.patch_iat_stub(IAT_STR_CTOR_PBD, str_ctor)
    emu.patch_iat_stub(IAT_STR_DTOR, str_dtor)
    emu.patch_iat_stub(IAT_ENTER_CS, enter_cs)
    emu.patch_iat_stub(IAT_LEAVE_CS, leave_cs)


# ---------------------------------------------------------------------------
# Empty AnsSceneContext (guaranteed real "not found")
# ---------------------------------------------------------------------------
def build_empty_scene_context(emu: Emu) -> int:
    # 0x2000: generously covers the bookkeeping fields (+0x1c8c/+0x1c9c/
    # +0x1cc0 etc.) that the abort-path's context-release call (0x102294d0,
    # invoked from 0x1022b365 before the "Failed in find()" log) reads.
    # Zeroed (via alloc's zero-fill) so all of them read as "nothing cached".
    ctx = emu.alloc(0x2000)
    head = emu.alloc(0x60)
    # map embedded at ctx+0xc; map+4 (== ctx+0x10) is _Myhead
    emu.w32(ctx + 0x10, head)
    # empty red-black tree sentinel: self-referential parent, isnil=1
    emu.w32(head + 4, head)   # _Myhead->_Parent == _Myhead (root==nil)
    emu.wb(head + 0x4D, 1)    # _Myhead->_Isnil == true
    return ctx


def run_case(pe: bytes, *, ctx_addr_provider, mock_find: bool):
    emu = Emu(pe)
    install_common_hooks(emu)

    hit = {}

    def mark(name):
        def cb(uc, address, size, _u):
            hit["landed"] = name
            uc.emu_stop()
        return cb

    emu.uc.hook_add(UC_HOOK_CODE, mark("continue"), begin=VA_CONTINUE, end=VA_CONTINUE)
    emu.uc.hook_add(UC_HOOK_CODE, mark("abort_log"), begin=VA_ABORT_LOG, end=VA_ABORT_LOG)

    if mock_find:
        # Short-circuit the REAL find() with its OTHER documented contract:
        # an internal-error/exception object (non-null field 0), copied from
        # find()'s own 0x10022b3f exit ("mov dword[edi], esi" with esi
        # non-null after building an exception via 0x1001ed90/0x10001580).
        def mock(e: Emu, args_addr_unused):
            esp = e.uc.reg_read(UC_X86_REG_ESP)
            ret_struct = e.r32(esp + 4)   # [ebp+8] equivalent, 1st stack arg
            fake_exc = e.alloc(4, b"\x01\x00\x00\x00")
            e.w32(ret_struct, fake_exc)   # field0 = non-null -> "error"
            return ret_struct, 0x14       # eax=ret_struct, ret 0x14
        emu.hook_stdcall(VA_FIND, mock)
    # else: let the real find() run (calls KERNEL32/MSVCP71 hooks above,
    # walks the real empty-map tree code, hits its real 0x10022d72/0x10022e91
    # not-found exit).

    ctx = ctx_addr_provider(emu)

    # Set up ESP_START and pre-populate ESP_START+0x10 with the scene
    # context pointer (the value the real snippet's
    # `mov ecx,[esp+0x1c]` at 0x1022b301 reads, computed by hand-tracing
    # the exact push sequence between block start and that instruction --
    # see module docstring / report for the full derivation).
    esp_start = STACK + 0x40000
    emu.uc.reg_write(UC_X86_REG_ESP, esp_start)
    # [esp+0x1c] at 0x1022b301 (esp_rel=-0xc there) == absolute esp_start+0x10
    # -- the scene-context "this" read right before calling find().
    emu.w32(esp_start + 0x10, ctx)
    # [esp+0x1c] at 0x1022b35f/0x1022b365 (esp_rel=0 there, i.e. AFTER find()
    # returns) == absolute esp_start+0x1c -- a second local slot the abort
    # path reads for the same scene-context pointer (confirmed by direct
    # Unicorn register trace, not assumed: esp differs between the two read
    # sites because find()'s `ret 0x14` pops 20 bytes of args on return).
    emu.w32(esp_start + 0x1C, ctx)

    emu.faults = []
    try:
        emu.uc.emu_start(VA_DRA_BLOCK_START, 0, timeout=0, count=2_000_000)
    except UcError as ex:
        raise RuntimeError(
            f"emu fault eip={emu.uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
            + ("; " + "; ".join(emu.faults[:4]) if emu.faults else "")
        ) from ex
    if "landed" not in hit and emu.faults:
        raise RuntimeError(f"emu faults, no landing: {emu.faults[:4]}")
    return hit.get("landed", "UNKNOWN")


def main() -> int:
    default_dll = Path(
        "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
        "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
    )
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else default_dll
    pe = dll.read_bytes()
    print(f"DLL {dll}")

    print("\n=== Run 1: REAL AnsSceneContext::find(), real EMPTY map ===")
    print("    (this is the actual runtime condition for a colour negative:")
    print("     'lighting' is never inserted, so the lookup is a genuine miss)")
    landed1 = run_case(pe, ctx_addr_provider=build_empty_scene_context, mock_find=False)
    print(f"    landed at: {landed1}"
          f" ({'0x1022b3b0 continue' if landed1=='continue' else '0x1022b383 abort/log' if landed1=='abort_log' else '?'})")

    print("\n=== Run 2: find() mocked to return its OTHER contract (internal error) ===")
    print("    (sanity check that the branch is a real fork, not dead code)")
    landed2 = run_case(pe, ctx_addr_provider=build_empty_scene_context, mock_find=True)
    print(f"    landed at: {landed2}"
          f" ({'0x1022b3b0 continue' if landed2=='continue' else '0x1022b383 abort/log' if landed2=='abort_log' else '?'})")

    print("\n=== Verdict ===")
    ok = (landed1 == "continue") and (landed2 == "abort_log")
    if ok:
        print("CONFIRMED: miss (real, unmocked find() on an empty map) -> CONTINUES")
        print("           (lands at 0x1022b3b0, the LUT-building path).")
        print("           An internal find() ERROR -> ABORTS (0x1022b383,")
        print("           'Failed in AnsSceneContext::find(...).' + early exit).")
        print()
        print("This REFUTES shasta.go's comment ('whose miss is fatal at")
        print("0x1022b35b') and CONFIRMS docs/reports/autotone-scope-2026-08-10/")
        print("dra.md's re-reading (miss is the safe, continuing path).")
    else:
        print(f"UNEXPECTED: run1={landed1} run2={landed2} -- does not match either")
        print("prior static reading; needs re-investigation before trusting this.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
