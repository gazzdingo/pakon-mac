"""Golden: the COMPLETE per-scene ``orderFpo`` triple (Y, U, V).

``fcn.1028b8d0`` (``PakonIMAu.dll``, md5 ``eea9dcf78ee21d4f7c515a6c2512242d``)
writes the per-scene ``orderFpo`` Y/U/V triple into ``pref_data``
(``scene+0x38a2``) — the value the SBA ``Preference`` stage consumes, and the
head of the per-frame balance chain that drives the washed-out defect.

This verifies all three components against real hardware data:

    Y = fos_opening_axes(arg5).Y  + L                (L = helper arg 9)
    U = fos_opening_axes(arg5).C1 + rdiv(num1, den)
    V = fos_opening_axes(arg5).C2 + rdiv(num2, den)

`fos_opening_axes` is this project's own already-Unicorn-verified port
function (``pakon_fos``); the U/V residual is docs/74 §76.4's derived
weighted-mean chroma computation, transcribed instruction by instruction.

**Why this is not a whole-function emulation.** docs/74 §78.2 established
that emulating ``0x1028b8d0`` end to end reaches a *bytecode interpreter*
(``fcn.102aadf0``: 16-bit opcodes, 254-entry dispatch table at
``0x102abf4c``, ``0xff`` halt) whose operands scatter unpredictably across
the address space. §78.3 recorded the alternative that actually closed Y and
now U/V: derive the decomposition statically, then verify each term against
real captured data.

**No fitted parameters.** Every input is a real captured buffer or a real
captured argument; every expected value is the real triple the vendor's own
code wrote, read back from the ``sba_preference`` dump and matched to its
producing call by ``pref_data`` address.

Usage::

    python3 pakon_orderfpo_triple_golden.py [capture.jsonl]

Exits non-zero unless every scene reproduces exactly.
"""

from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

import pakon_fos as F
from pakon_orderfpo_uv_golden import compute_uv

DEFAULT_CAP = ("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/"
               "live_hooks_20260817-181440.jsonl")
DENS_END = 0x21C0 + 2 * 864          # arg0 must reach this (§76.4)


def _s32(v: int) -> int:
    return v - (1 << 32) if v >= (1 << 31) else v


def load(capture: Path):
    events = [json.loads(l) for l in capture.open() if l.strip()]
    dumps = defaultdict(dict)
    for d in events:
        if d.get("kind") == "buffer_dump":
            dumps[d["call_id"]][d["label"]] = d

    def buf(cid, *labels):
        best = None
        for lab in labels:
            r = dumps[cid].get(lab)
            if r and r.get("readable"):
                b = bytes.fromhex(r["hex"])
                if best is None or len(b) > len(best):
                    best = b
        return best

    cases, pend = [], None
    for d in events:
        if d.get("kind") != "call" or d.get("event") != "enter":
            continue
        h = d.get("hook_id")
        if h == "sba_order_fpo_calc":
            sw = d.get("stack_dwords") or []
            pend = None
            if len(sw) >= 13 and int(sw[3], 16) == 0:
                cid = d["call_id"]
                r = dumps[cid].get("pref_data_before")
                pend = {"addr": r["addr"] if r else None, "L": None,
                        "arg0": buf(cid, "arg0_big", "arg0_dens"),
                        "arg2": buf(cid, "arg2_big", "arg2_388c"),
                        "arg6": buf(cid, "arg6_big", "arg6_unknown"),
                        "arg7": buf(cid, "arg7_big", "arg7_3c34"),
                        "arg11": buf(cid, "arg11_big", "fos_dmin"),
                        "arg5": buf(cid, "arg5_big", "arg5_blob")}
        elif h == "sba_order_fpo_helper" and pend is not None:
            sw = d.get("stack_dwords") or []
            if pend["L"] is None and len(sw) > 9:
                pend["L"] = _s32(int(sw[9], 16))
        elif h == "sba_preference" and pend is not None:
            r = dumps[d["call_id"]].get("pref_data")
            if r and r.get("readable") and r["addr"] == pend["addr"]:
                pend["want"] = struct.unpack_from(
                    "<hhh", bytes.fromhex(r["hex"]), 0)
                cases.append(pend)
            pend = None
    return cases


def main(argv):
    cap = Path(argv[1]) if len(argv) > 1 else Path(DEFAULT_CAP)
    cases = load(cap)
    print(f"capture : {cap.name}")
    print(f"scenes  : {len(cases)}")
    print("-" * 62)
    npass = nfail = 0
    for i, c in enumerate(cases, 1):
        if c["arg0"] is None or len(c["arg0"]) < DENS_END or c["L"] is None:
            have = 0 if c["arg0"] is None else len(c["arg0"])
            print(f"  scene {i:2d}: SKIP (arg0 {have:#x} < {DENS_END:#x} "
                  f"or helper arg9 missing)")
            nfail += 1
            continue
        rgb = struct.unpack_from("<hhh", c["arg5"], 0)
        Yo, C1o, C2o = F.fos_opening_axes(*rgb)
        out4, out8 = compute_uv(c["arg0"], c["arg2"], c["arg6"],
                                c["arg7"], c["arg11"], (Yo, C1o, C2o))
        got = (Yo + c["L"], C1o + out4, C2o + out8)
        ok = got == c["want"]
        npass += ok
        nfail += (not ok)
        print(f"  scene {i:2d}: got {str(got):>18s}  want {str(c['want']):>18s}"
              f"   {'PASS' if ok else 'FAIL'}")
    print("-" * 62)
    print(f"pass {npass}  fail {nfail}  of {len(cases)}")
    if npass == len(cases) and cases:
        print("\norderFpo (Y, U, V): GOLDEN -- all three components reproduce "
              "bit-exactly on real hardware data.")
    return 0 if (cases and npass == len(cases)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
