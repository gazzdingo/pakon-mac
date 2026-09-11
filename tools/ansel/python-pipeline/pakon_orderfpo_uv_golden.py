"""Golden: `orderFpo` U and V, from docs/74 §76.4's derived arithmetic.

Companion to ``pakon_orderfpo_y_golden.py`` (which closes Y). Together they
verify all three components of the per-scene ``orderFpo`` triple that
``fcn.1028b8d0`` writes into ``pref_data`` (``scene+0x38a2``).

Approach, and why it is not a full-function emulation: docs/74 §78.2 found
that emulating ``0x1028b8d0`` end-to-end runs into a **bytecode interpreter**
(``fcn.102aadf0`` — 16-bit opcodes, 254-entry dispatch table, ``0xff`` halt),
whose operands scatter unpredictably across the address space. §78.3 records
the productive alternative that closed Y: derive the decomposition
statically, then verify each term against real captured data. This does the
same for U and V, whose arithmetic §76.4 derived in full — a weighted mean
chroma residual over 864 dens samples, computed from six flat buffers, no
interpreter involved.

Everything below is transcribed from §76.4's per-instruction citations. The
only inputs are real captured buffers and the real observed outputs; there
is no fitted constant anywhere.

Usage::

    python3 pakon_orderfpo_uv_golden.py [capture.jsonl]
"""

from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

import pakon_fos as F

N = 864          # helper arg2
NX, NY = 50, 83  # helper arg4 / arg5
OFFX = (NX - 1) // 2   # 24
OFFY = (NY - 1) // 2   # 41

# dens block offsets within outer arg0 (§76.4)
OFF_Y, OFF_C1, OFF_C2 = 0x1440, 0x1B00, 0x21C0


def _i16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def _trunc_div16(v: int) -> int:
    """`mov eax,r; cdq; and edx,0xf; add eax,edx; sar eax,4` -- truncation
    toward zero, NOT an arithmetic shift (§76.4)."""
    return -((-v) >> 4) if v < 0 else v >> 4


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else (hi if v > hi else v)


def _ctrunc(a: int, b: int) -> int:
    """C/x86 `idiv` semantics: quotient truncated toward zero."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _rdiv(n: int, d: int) -> int:
    """Round half away from zero, then truncating idiv (§76.4).

    The half-step is the DLL's own ``mov eax,d; cdq; sub eax,edx; sar eax,1``
    at ``0x1028b27e``-``0x1028b285`` -- which is truncating division by two,
    NOT ``abs(d) >> 1``. The two agree for every divisor that occurs here
    (``N*100`` = 86400, or ``cnt*100`` with ``cnt > 0``, both positive) but
    diverge for a negative divisor, so the faithful form is used rather than
    the merely-equivalent one.
    """
    h = _ctrunc(d, 2)
    q = (n + h) if n >= 0 else (n - h)
    return _ctrunc(q, d)


def compute_uv(arg0: bytes, arg2: bytes, arg6: bytes, arg7: bytes,
               arg11: bytes, const: tuple[int, int, int]):
    """Return (out4, out8) -- the U and V residuals (§76.4)."""
    Yo, C1o, C2o = const

    def i16at(buf, off):
        return struct.unpack_from("<h", buf, off)[0]

    Nmin = i16at(arg6, 0xDC + 0x12)
    R1sq = i16at(arg6, 0xDC + 0x14) ** 2
    R2sq = i16at(arg6, 0xDC + 0x16) ** 2
    if struct.unpack_from("<b", arg2, 4)[0] < 0:
        R1sq = 0x3D0900                      # 2000**2
    Ythr = struct.unpack_from("<i", arg11, 0x48)[0]

    cnt = 0
    Sall1 = Sall2 = Ssel1 = Ssel2 = 0
    for i in range(N):
        y = _i16(i16at(arg0, OFF_Y + 2 * i) - Yo)
        c1 = _i16(i16at(arg0, OFF_C1 + 2 * i) - C1o)
        c2 = _i16(i16at(arg0, OFF_C2 + 2 * i) - C2o)

        gx = _clamp(_trunc_div16(c1) + OFFX, 0, NX - 1)
        gy = _clamp(_trunc_div16(c2) + OFFY, 0, NY - 1)
        w = struct.unpack_from("<b", arg7, gx * NY + gy)[0]

        if cnt < Nmin:
            Sall1 += w * c1
            Sall2 += w * c2

        sq = c1 * c1 + c2 * c2
        sel = (arg11[0xC20 + i] == 1 and sq < R1sq)
        if not sel:
            sel = (y > Ythr and sq < R2sq)
        if sel:
            cnt += 1
            Ssel1 += w * c1
            Ssel2 += w * c2

    if cnt < Nmin:
        num1, num2, den = Sall1, Sall2, N * 100
    else:
        num1, num2, den = Ssel1, Ssel2, cnt * 100
    return _rdiv(num1, den), _rdiv(num2, den)


def load(capture: Path):
    events = [json.loads(l) for l in capture.open() if l.strip()]
    dumps = defaultdict(dict)
    for d in events:
        if d.get("kind") == "buffer_dump":
            dumps[d["call_id"]][d["label"]] = d

    def buf(cid, *labels):
        """Prefer the largest readable row among `labels`."""
        best = None
        for lab in labels:
            r = dumps[cid].get(lab)
            if r and r.get("readable"):
                b = bytes.fromhex(r["hex"])
                if best is None or len(b) > len(best):
                    best = b
        return best

    cases, pending = [], None
    for d in events:
        if d.get("kind") != "call" or d.get("event") != "enter":
            continue
        h = d.get("hook_id")
        if h == "sba_order_fpo_calc":
            sw = d.get("stack_dwords") or []
            pending = None
            if len(sw) >= 13 and int(sw[3], 16) == 0:
                cid = d["call_id"]
                r = dumps[cid].get("pref_data_before")
                pending = {
                    "addr": r["addr"] if r else None,
                    "arg0": buf(cid, "arg0_big", "arg0_dens"),
                    "arg2": buf(cid, "arg2_big", "arg2_388c"),
                    "arg6": buf(cid, "arg6_big", "arg6_unknown"),
                    "arg7": buf(cid, "arg7_big", "arg7_3c34"),
                    "arg11": buf(cid, "arg11_big", "fos_dmin"),
                    "arg5": buf(cid, "arg5_big", "arg5_blob"),
                }
        elif h == "sba_preference" and pending is not None:
            r = dumps[d["call_id"]].get("pref_data")
            if r and r.get("readable") and r["addr"] == pending["addr"]:
                pending["triple"] = struct.unpack_from(
                    "<hhh", bytes.fromhex(r["hex"]), 0)
                cases.append(pending)
            pending = None
    return cases


def main(argv):
    cap = Path(argv[1]) if len(argv) > 1 else Path(
        "/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/"
        "live_hooks_20260817-175818.jsonl")
    cases = load(cap)
    print(f"capture: {cap.name}   {len(cases)} scenes\n")
    need = {"arg0": OFF_C2 + 2 * N}
    npass = nfail = nskip = 0
    for i, c in enumerate(cases, 1):
        if c["arg0"] is None or len(c["arg0"]) < need["arg0"]:
            have = 0 if c["arg0"] is None else len(c["arg0"])
            print(f"  scene {i}: SKIP -- arg0 is {have:#x} bytes, "
                  f"need {need['arg0']:#x} (dens C2 block ends there)")
            nskip += 1
            continue
        rgb = struct.unpack_from("<hhh", c["arg5"], 0)
        const = F.fos_opening_axes(*rgb)
        out4, out8 = compute_uv(c["arg0"], c["arg2"], c["arg6"],
                                c["arg7"], c["arg11"], const)
        gotU, gotV = const[1] + out4, const[2] + out8
        wantU, wantV = c["triple"][1], c["triple"][2]
        ok = (gotU, gotV) == (wantU, wantV)
        npass += ok
        nfail += (not ok)
        print(f"  scene {i}: U {gotU:5d} vs {wantU:5d}   "
              f"V {gotV:5d} vs {wantV:5d}   {'PASS' if ok else 'FAIL'}")
    print(f"\npass {npass}  fail {nfail}  skipped {nskip}")
    return 0 if (npass and not nfail and not nskip) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
