#!/usr/bin/env python3
"""Golden attempt: emulate ``sba_preference`` and recover the balance shift.

WHAT THIS IS FOR
----------------
docs/74 §93–§95 established that the vendor's per-frame balance shift is
``shift[f,c] = A[c] + k[f]`` — a per-channel constant plus a per-frame scalar —
and §95.2 located the producer exactly: ``sba_preference`` (``fcn.1028c780``,
``PakonIMAu.dll`` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``) runs one call after
``L`` is computed and one call before the shift exists.

§96 then read the function statically and found its FPU constants are the
orthonormal opponent basis (``1/√3``, ``1/√2``, ``1/√6``, ``√3``), which
explains the decomposition: ``k`` is a pure move along ``(1,1,1)`` (luminance)
and ``A`` is chroma. **That is tier 3 — indicated by constants, not executed.**

This promotes it, or fails loudly trying. The target is the six real shifts,
which two independent routes already agree on (§95.1):

    [800, 388, 136]  [829, 402, 167]  [798, 360, 130]
    [889, 458, 221]  [833, 405, 169]  [766, 351,  96]

WHY IT MAY NOT REACH THEM, STATED UP FRONT
------------------------------------------
The scene structs are 25 820 bytes (§95.4) and the capture dumps ``0x64`` of
them at this call site. If Preference reads outside that window the emulation
faults — and **that is still a useful result**: this harness reports every
fault as ``argN+0xNNN`` (inherited from ``pakon_orderfpo_golden``'s reporter),
which names exactly which dump row v29 needs to widen. A fault list is a
capture spec, not a failure.

No fitted parameters: every input is a real captured buffer at its real
process address.
"""
from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pakon_orderfpo_golden import Emu, RET_MAGIC, STACK, STACK_SZ  # noqa: E402
from unicorn import UcError                           # noqa: E402
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_ESP)  # noqa: E402

PREFERENCE_VA = 0x1028C780

PE_PATH = "/Users/guy/pakon-windows-repair/COM-SERVER/PakonIMAu.dll"

DEFAULT_CAP = ("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/"
               "live_hooks_20260818-080318.jsonl")

#: §95.1, confirmed two independent ways (balance_shift_4b6 and lut[i]-i).
EXPECTED = [(800, 388, 136), (829, 402, 167), (798, 360, 130),
            (889, 458, 221), (833, 405, 169), (766, 351, 96)]


def load_calls(cap: Path):
    """Every ``sba_preference`` entry: its stack args and its dumped buffers."""
    calls = {}
    for line in open(cap):
        d = json.loads(line)
        if d.get("hook_id") != "sba_preference":
            continue
        cid = d.get("call_id")
        if cid is None:
            continue
        e = calls.setdefault(cid, {"args": None, "bufs": {}})
        if d.get("kind") == "call" and d.get("stack_dwords"):
            e["args"] = [int(x, 16) for x in d["stack_dwords"]]
        elif d.get("kind") == "buffer_dump" and d.get("readable"):
            e["bufs"][d["label"]] = bytes.fromhex(d["hex"])
    return {c: v for c, v in sorted(calls.items()) if v["args"]}


def run_one(pe: bytes, args, bufs, verbose=False):
    emu = Emu(pe)
    # Place every captured buffer at its REAL process address, so pointer
    # arithmetic inside the function resolves the way it did on hardware.
    label_arg = {"pref_data": 0, "blob": 3, "pref_scene_big": 0}
    arg_bases = {}
    for label, data in bufs.items():
        idx = label_arg.get(label)
        if idx is None or idx >= len(args):
            continue
        addr = args[idx]
        if not addr:
            continue
        emu.place(addr, data)
        arg_bases[idx] = addr
    emu.arg_bases = arg_bases
    emu.scene_base = args[0] if args else None

    # cdecl: push args right-to-left, then the magic return address.
    esp = STACK + STACK_SZ - 0x1000
    n = min(len(args), 16)
    for i, v in enumerate(args[:n]):
        emu.uc.mem_write(esp + 4 + 4 * i, struct.pack("<I", v & 0xFFFFFFFF))
    emu.uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)

    try:
        emu.uc.emu_start(PREFERENCE_VA, RET_MAGIC, timeout=15_000_000,
                         count=8_000_000)
        ok, err = True, None
    except UcError as exc:
        ok, err = False, str(exc)
    return emu, ok, err


def main(argv):
    cap = Path(argv[1]) if len(argv) > 1 else Path(DEFAULT_CAP)
    pe = Path(PE_PATH).read_bytes()
    calls = load_calls(cap)
    print(f"capture : {cap.name}")
    print(f"sba_preference calls with args: {len(calls)}")
    if not calls:
        return 1

    faults_all = []
    for i, (cid, e) in enumerate(list(calls.items())[:6]):
        bufs = ", ".join(f"{k}={len(v)}B" for k, v in sorted(e["bufs"].items()))
        print(f"\n  call {cid}: buffers [{bufs}]")
        emu, ok, err = run_one(pe, e["args"], e["bufs"])
        if ok:
            print(f"    ran to completion, eax = "
                  f"{emu.uc.reg_read(UC_X86_REG_EAX):#x}")
        else:
            print(f"    stopped: {err}")
        for f in emu.faults[:6]:
            print(f"      fault: {f}")
            faults_all.append(f)
        if len(emu.faults) > 6:
            print(f"      ... {len(emu.faults) - 6} more faults")

    print("\n--- verdict ---")
    if faults_all:
        print(f"{len(faults_all)} memory faults recorded. Each is reported "
              f"arg-relative, so this IS the capture spec for the next hook "
              f"build: widen the named dump rows and re-run.")
        print("This is not a golden result and is not recorded as one.")
        return 2
    print("no faults. Compare eax//written fields against EXPECTED before "
          "claiming anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
