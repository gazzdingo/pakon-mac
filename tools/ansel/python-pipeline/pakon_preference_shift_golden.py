#!/usr/bin/env python3
"""Golden: ``Preference`` (``fcn.1028c780``) — the per-frame balance shift.

``PakonIMAu.dll`` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``.  Two independent
checks, both run on every call this harness can find:

**Tier 1 — the real DLL vs the port.**  The real function bytes execute under
Unicorn on the real captured argument buffers, at their real process
addresses, and the three ``int16`` it writes to ``arg2+0x02`` (the anchor),
the three at ``arg2+0x08`` (the shift) and the word at ``arg2+0x00`` are
diffed against ``pakon_sba_preference.preference_full`` for the identical
input.  Nothing is fitted; the port either reproduces the DLL exactly or it
does not.  (§99 established that this Unicorn harness and a Wine host running
the real loader agree byte-for-byte on this same function, so Unicorn is not
a weaker instrument here.)

**Tier 2 — both vs the vendor's own hardware output.**  ``sba_get_shifts``
dumps ``shifts_3a38`` (= ``arg2+0x08``, all three words) and
``pref_out_3a30`` (= ``arg2+0x00``, so its second and third words are the
anchor's first two — the "misaligned" row of docs/74 §160.3).  Every call is
paired to its dump **by pointer identity** — ``pref_out_3a30.addr`` must equal
the call's own ``arg2`` and ``shifts_3a38.addr`` must equal ``arg2+8`` — so
there is no ordering assumption and no analysis/render pairing hazard
(§161.1, §178.2).

What the function computes, in one line::

    anchor = ftol(inv( lim46 - s', +U_r, +V_r ))     -> arg2+0x02
    shift  = ftol(inv(         s', -U_r, -V_r ))     -> arg2+0x08

so per channel ``anchor + shift`` is EXACTLY ``lim46/sqrt(3)`` before the two
independent ``_ftol`` truncations — ``lim46 = blob+0x46 = round(NBP*sqrt(3))``
= 2685 on every shipped scan, i.e. ``2685/sqrt(3) = 1550.18547...``.  That is
the whole of docs/74 §160.2's "``shift = 1549 - preference``, exact on 96/117,
1550 on 21, 1551 on 3": 1550 when the anchor's fraction is below 0.1855,
1549 otherwise, and 1551 when the shift falls in ``(-1, 0]`` and truncation
*toward zero* rounds it up instead of down.  There is no off-by-one; the
constant is not an integer.  The harness asserts the ``lim46/sqrt(3)`` identity
directly rather than restating the 1549/1550 histogram.

Usage::

    python3 pakon_preference_shift_golden.py [capture.jsonl ...]

With no argument every ``live_hooks_*.jsonl`` in the default capture directory
is used.  Exits non-zero if any call fails, if the mutation self-test is not
caught, or if no case was found at all.
"""

from __future__ import annotations

import glob
import json
import math
import os
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pakon_sba_preference as SP                          # noqa: E402
import pakon_orderfpo_golden as OG                         # noqa: E402
from pakon_orderfpo_golden import Emu, RET_MAGIC           # noqa: E402
from unicorn import UcError                                # noqa: E402
from unicorn.x86_const import UC_X86_REG_ESP               # noqa: E402

# Captured Preference scene pointers run to 0x0d4d0ae0 on the longer rolls,
# which collides with ``pakon_orderfpo_golden``'s emulator stack (0x0BF00000)
# and CRT stub heap (0x0A000000).  Move both above the image so that every
# captured buffer can be placed at its REAL process address — the whole point
# of that emulator's addressing scheme — instead of silently failing to map.
OG.STACK = 0x50000000
OG.HEAP = 0x40000000

PREFERENCE_VA = 0x1028C780
PE_CANDIDATES = (
    "/Users/guy/pakon-windows-repair/COM-SERVER/PakonIMAu.dll",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "re", "live_hooks", "wine_host", "PakonIMAu.dll"),
)
DEFAULT_CAP_DIR = "/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp"
DLL_MD5 = "eea9dcf78ee21d4f7c515a6c2512242d"


def find_pe() -> Path:
    for c in PE_CANDIDATES:
        p = Path(c)
        if p.is_file():
            import hashlib
            h = hashlib.md5(p.read_bytes()).hexdigest()
            if h != DLL_MD5:
                raise SystemExit(f"{p}: md5 {h}, expected {DLL_MD5}")
            return p
    raise SystemExit("PakonIMAu.dll not found in any known location")


def load_calls(cap: Path):
    """Every ``sba_preference`` entry, with its buffers and its output dump.

    Returns ``[(call_id, args, pref_data, blob, arg2_bytes, want)]`` where
    ``want`` is ``(out0, anchor01, shift3)`` from the vendor's own memory, or
    ``None`` if this call has no matching ``sba_get_shifts`` dump.
    """
    byid: dict[tuple[str, int], dict] = defaultdict(dict)
    seen: list[tuple[str, int]] = []
    with cap.open() as fh:
        for line in fh:
            if '"sba_preference"' not in line and '"sba_get_shifts"' not in line:
                continue
            d = json.loads(line)
            cid = d.get("call_id")
            if cid is None:
                continue
            k = (d["hook_id"], cid)
            if k not in byid:
                seen.append(k)
            if d.get("kind") == "call" and d.get("event") == "enter":
                byid[k]["args"] = [int(x, 16)
                                   for x in (d.get("stack_dwords") or [])[:8]]
            elif d.get("kind") == "buffer_dump" and d.get("readable"):
                byid[k][d["label"]] = (int(d["addr"], 16),
                                       bytes.fromhex(d.get("hex") or ""))

    # arg2 pointer -> the most recent Preference call that wrote through it.
    last: dict[int, int] = {}
    outs: dict[int, tuple[int, list[int], list[int]]] = {}
    for h, cid in sorted(seen, key=lambda t: t[1]):
        v = byid[(h, cid)]
        if h == "sba_preference" and "args" in v:
            last[v["args"][2]] = cid
        elif h == "sba_get_shifts":
            sh, po = v.get("shifts_3a38"), v.get("pref_out_3a30")
            if not (sh and po) or sh[0] != po[0] + 8:
                continue
            owner = last.get(po[0])
            if owner is None or owner in outs:
                continue
            w = struct.unpack("<3h", po[1])
            outs[owner] = (w[0], list(w[1:3]),
                           list(struct.unpack("<3h", sh[1])))

    cases = []
    for h, cid in sorted(seen, key=lambda t: t[1]):
        if h != "sba_preference":
            continue
        v = byid[(h, cid)]
        args, pd = v.get("args"), v.get("pref_data")
        bl, a2 = v.get("blob"), v.get("pref_arg2")
        if not (args and pd and bl):
            continue
        # arg2 is the OUTPUT struct.  Older hook builds do not dump it; a
        # zero fill is sound because the one field the function reads from it
        # (``arg2+0x54``) it writes first — read/write-ordered trace in
        # docs/74 §98.2 — and everything else it does to arg2 is a store.
        arg2 = a2[1] if a2 else b"\x00" * 0x400
        cases.append((cid, args[:5], pd[1], bl[1], arg2, outs.get(cid)))
    return cases


def run_dll(pe: bytes, args, pref_data: bytes, blob: bytes, arg2: bytes):
    """Execute the real ``fcn.1028c780`` and read back what it wrote."""
    emu = Emu(pe)
    # arg2 is written well past the 0x80 the hook dumps: the copy block ends
    # at arg2+0x176 and 0x1028c802..0x1028c84c store at +0x182..+0x18c.  Back
    # it with a zero region wide enough to hold all of that (a short one only
    # faults when the writes happen to cross a page boundary, which is a
    # capture-dependent coin flip), then lay the real buffers over the top so
    # the INPUTS always win if any of them overlap.
    emu.place(args[2], b"\x00" * 0x400)
    emu.place(args[2], arg2)
    emu.place(args[0], pref_data)
    emu.place(args[3], blob)
    emu.arg_bases = {0: args[0], 2: args[2], 3: args[3]}
    emu.scene_base = args[0]
    esp = OG.STACK + OG.STACK_SZ - 0x1000
    for i, v in enumerate(args):
        emu.uc.mem_write(esp + 4 + 4 * i, struct.pack("<I", v & 0xFFFFFFFF))
    emu.uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    err = None
    try:
        emu.uc.emu_start(PREFERENCE_VA, RET_MAGIC,
                         timeout=15_000_000, count=8_000_000)
    except UcError as exc:
        err = str(exc)
    out = emu.read(args[2], 16)
    return (struct.unpack_from("<h", out, 0)[0],
            list(struct.unpack_from("<3h", out, 2)),
            list(struct.unpack_from("<3h", out, 8)),
            err, list(emu.faults))


def check(cases, pe: bytes, mutate: str | None = None):
    """Returns ``(n_dll, n_vendor, failures, sums, modes)``."""
    n_dll = n_vendor = 0
    fails: list[str] = []
    sums: Counter = Counter()
    modes: Counter = Counter()
    saved = (SP.ftol2_104ffe44, SP.SQRT_2_OVER_3)
    if mutate == "ftol_round":
        SP.ftol2_104ffe44 = lambda x: int(round(x))     # nearest, not chop
    elif mutate == "ftol_floor":
        SP.ftol2_104ffe44 = lambda x: math.floor(x)     # chop DOWN, not
        #                                                 toward zero
    elif mutate == "g_basis":
        SP.SQRT_2_OVER_3 = SP.INV_SQRT6                 # wrong G axis gain
    try:
        for cid, args, pd, bl, a2, want in cases:
            modes[args[4]] += 1
            got = SP.preference_full(pd, bl, args[4])
            d_w0, d_anchor, d_shift, err, faults = run_dll(pe, args, pd, bl, a2)
            if err or faults:
                fails.append(f"cid {cid}: DLL run failed err={err} "
                             f"faults={faults[:2]}")
                continue
            if got is None:
                fails.append(f"cid {cid}: port took the 0x18a4 guard, "
                             f"DLL did not")
                continue
            p_anchor, p_shift, p_w0 = got
            if (list(p_anchor) != d_anchor or list(p_shift) != d_shift
                    or p_w0 != d_w0):
                fails.append(
                    f"cid {cid} mode {args[4]:#x}: port vs DLL\n"
                    f"    anchor port {list(p_anchor)} dll {d_anchor}\n"
                    f"    shift  port {list(p_shift)} dll {d_shift}\n"
                    f"    w0     port {p_w0} dll {d_w0}")
                continue
            n_dll += 1
            # lim46/sqrt(3) identity, on the DLL's own output.
            lim46 = struct.unpack_from("<h", bl, 0x46)[0]
            for c in range(3):
                sums[d_anchor[c] + d_shift[c]] += 1
            exact = lim46 / math.sqrt(3.0)
            for c in range(3):
                s = d_anchor[c] + d_shift[c]
                if not (math.floor(exact) - 1 <= s <= math.floor(exact) + 1):
                    fails.append(f"cid {cid}: anchor+shift {s} outside "
                                 f"floor({exact:.4f})+-1")
            if want is not None:
                v_w0, v_anchor01, v_shift = want
                if (d_shift != v_shift or d_anchor[:2] != v_anchor01
                        or d_w0 != v_w0):
                    fails.append(
                        f"cid {cid}: DLL vs VENDOR HARDWARE\n"
                        f"    shift  {d_shift} vs {v_shift}\n"
                        f"    anchor {d_anchor[:2]} vs {v_anchor01}\n"
                        f"    w0     {d_w0} vs {v_w0}")
                    continue
                n_vendor += 1
    finally:
        SP.ftol2_104ffe44, SP.SQRT_2_OVER_3 = saved
    return n_dll, n_vendor, fails, sums, modes


def main(argv):
    pe_path = find_pe()
    pe = pe_path.read_bytes()
    caps = [Path(a) for a in argv[1:]]
    if not caps:
        caps = sorted(Path(p) for p in
                      glob.glob(os.path.join(DEFAULT_CAP_DIR,
                                             "live_hooks_*.jsonl")))
    if not caps:
        print("no captures found")
        return 1
    print(f"DLL     : {pe_path}  md5 {DLL_MD5}")

    cases = []
    for c in caps:
        if not c.is_file():
            print(f"  {c.name}: MISSING")
            continue
        got = load_calls(c)
        print(f"  {c.name}: {len(got)} Preference calls, "
              f"{sum(1 for g in got if g[5])} with a vendor output dump")
        cases.extend(got)
    if not cases:
        print("no usable Preference calls in any capture")
        return 1

    n_dll, n_vendor, fails, sums, modes = check(cases, pe)
    print(f"\nmodes seen                        : "
          f"{dict(sorted(modes.items()))}")
    print(f"port == real DLL, bit-exact       : {n_dll}/{len(cases)}")
    print(f"DLL  == vendor hardware output    : {n_vendor}")
    print(f"anchor+shift histogram            : {dict(sorted(sums.items()))}"
          f"   (lim46/sqrt3 = {2685 / math.sqrt(3.0):.5f})")
    for f in fails[:20]:
        print("  FAIL " + f)
    if len(fails) > 20:
        print(f"  ... {len(fails) - 20} more")

    # Teeth.  Each mutation is a plausible tidy-up of a load-bearing detail:
    # rounding instead of chopping, chopping DOWN instead of toward zero (the
    # distinction that produces the 1551 sums), and the wrong basis gain on the
    # G axis.  A harness that cannot see these is not testing anything.
    print("\n--- mutation self-test (each must be CAUGHT) ---")
    teeth_ok = True
    sub = cases[: min(len(cases), 60)]
    for m in ("ftol_round", "ftol_floor", "g_basis"):
        _, _, mf, _, _ = check(sub, pe, mutate=m)
        print(f"  {m:11s}: {len(mf)}/{len(sub)} mismatched "
              f"{'CAUGHT' if mf else 'NOT CAUGHT'}")
        teeth_ok = teeth_ok and bool(mf)

    wiring_ok = check_host_wiring()

    ok = (not fails and n_dll == len(cases) and n_vendor > 0 and teeth_ok
          and wiring_ok)
    print("\n" + ("ALL OK" if ok else "FAILED"))
    return 0 if ok else 1


def check_host_wiring() -> bool:
    """The host runs mode 0, and its static default is unchanged by that.

    ``pakon_ansel.preference_shift_words`` used to call the mode-``0x11``
    fragment; every live call is mode 0 (above), so it now calls
    ``preference_full`` in mode 0.  With no per-frame ``orderFpo`` the aim
    triple is the opening triple's own axes, every delta truncates to zero,
    and the result must equal the old fragment **exactly** — otherwise the
    switch silently moved the default render.  Checked on every shipped
    ``sba-*.dpi``, not just the one this scanner selects.
    """
    print("\n--- host wiring: mode-0 default == the old 0x11 triple ---")
    try:
        import pakon_ansel as A
        import pakon_sba_preference as SPref
    except Exception as exc:                            # noqa: BLE001
        print(f"  SKIP ({type(exc).__name__}: {exc})")
        return True
    dpi_dir = (Path(A.DEFAULT_ANSEL_ROOT) / "sba" / "SbaDPI")
    files = sorted(dpi_dir.glob("*.dpi"))
    if not files:
        print(f"  SKIP (no dpi under {dpi_dir})")
        return True
    bad = 0
    for p in files:
        sba = A.SbaParams.load(p)
        old = tuple(SPref.preference_shifts_from_dpi_fields(
            fpo=sba.fpo, fpa=sba.fpa,
            neutral_balance_point=sba.neutral_balance_point,
            neutral_button=sba.neutral_button,
            under_constraint=sba.neutral_under_constraint,
            over_constraint=sba.neutral_over_constraint,
            pcls=sba.pcls))
        new = tuple(A.preference_shift_words(sba))
        if old != new:
            bad += 1
            print(f"  {p.name}: 0x11 {old} vs mode-0 default {new}  DIFFER")
    print(f"  {len(files)} shipped dpi, {bad} differ "
          f"{'OK' if not bad else 'FAILED'}")
    return bad == 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
