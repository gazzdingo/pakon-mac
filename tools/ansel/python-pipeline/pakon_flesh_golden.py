#!/usr/bin/env python3
"""Golden FLESH adjust arithmetic vs the real PakonIMAu.dll (Unicorn).

Executes the real bytes of ``fcn.10270280``'s tail —
``0x102714e1 … 0x10271760``, the block that computes ``m_fleshAdjust`` and
therefore the per-frame RPD ``Delta`` of `docs/74` §178/§180 — on a real
parameter blob built from the shipped
``flesh-srcType-metric-default-default.dpi``, and diffs the emitted
``word [edi+0x30..+0x34]`` against ``pakon_flesh.flesh_delta``.

Nothing in the DLL is patched.  The only two calls inside the range,
``0x104d4520`` / ``0x104d4530``, are real two-instruction accessors
(``mov ecx,[ecx+4]`` → ``mov eax,[ecx+0x14]`` / ``[ecx+0x18]``), so they
are satisfied by building the real two-level object in guest memory rather
than by stubbing.  ``_ftol`` (``0x104ffe44``) runs for real.

The x87 control word is set to ``0x027f`` (53-bit precision), which is what
the MSVC7 CRT startup leaves it at in the real process, so that the
register-resident multiply chain at ``0x102716ea`` rounds the way it does on
Windows rather than the way Unicorn's ``0x037f`` reset would.  Stated as a
negative result rather than a claim: sweeping the control word over
``0x027f`` / ``0x037f`` / ``0x007f`` changes **nothing** on any of the 317
cases tried, so this is correctness by construction, not a fix for an
observed difference.

What this proves, and what it does not
--------------------------------------

Proves, bit-exact: the guard order, both ``ftol`` truncations, the
``frontLitBeta`` / ``backLitBeta`` selection, the ``darkenOnly`` post-guard,
and the channel-uniform write.

On the parameter mapping, be precise about which half is proven.  The
*calculator* side — that the byte/double at each offset is used the way
``pakon_flesh`` says — is tier 1 here for the nine fields the tail actually
reads: ``tSpace`` (+0x5c), ``frontLitBeta`` (+0x5070), ``backLitBeta``
(+0x5078), ``fleshPrefAdj`` (+0x5080), ``fleshNeutralAim`` (+0x5088),
``fleshCountThresh`` (+0x5090), ``percentFleshAdj`` (+0x5098),
``exposureLimit`` (+0x50a0), ``darkenOnly`` (+0x60aa); every one is varied
away from its shipped value in ``variants`` and moves the DLL's answer.
The *reader* side — that those offsets are the ones
``fleshParameterReader`` fills from those DPI key names — is **tier 3**:
read out of ``fcn.10272380``, not executed.  The remaining offsets
(``loff``/``soff``/``toff``, the scales, ``clipAmount``, ``axialProb``,
``regionThreshold``, ``growThreshold``, ``stOnly``, ``oneDTable``,
``useAdvanced``, ``writeIntermediateImages``, ``useSmallAnalysisImage``)
are tier 3 on both sides — nothing in the tail touches them.

Does **not** prove: the flesh detector that produces ``stat`` / ``nsum`` /
``fleshCount``.  Most of that detector *is* now ported and proven bit-exact
by its own harness, ``pakon_flesh_detector_golden.py`` — the LST transform,
the axis indices, the separable skin-probability product, the analysis
border, the clamp map and the reduction loop.  What is still missing is the
threshold stage `fcn.1029ec50` is now ported too
(``pakon_flesh_threshold_golden.py``).  What is still missing on the way
from a *frame* to ``stat``/``nsum``/``fleshCount`` is upstream of all of
them: the analysis-image construction and the reduction's weight plane.
See ``pakon_flesh``'s header and that harness's section [6].

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \\
    tools/ansel/python-pipeline/pakon_flesh_golden.py [PakonIMAu.dll]``
"""
from __future__ import annotations

import hashlib
import struct
import sys
from dataclasses import replace
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EBP,
    UC_X86_REG_EDI,
    UC_X86_REG_ESP,
    UC_X86_REG_FPCW,
)

import pakon_flesh as fl

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x200000
DATA_ADDR = 0x20000000
DATA_SIZE = 0x20000

#: MSVC7 CRT startup precision-control setting.
FPCW_WIN32 = 0x027F

DEFAULT_DLL = Path(__file__).resolve().parents[2] / "re" / "live_hooks" / "wine_host" / "PakonIMAu.dll"


def _align_up(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


def load_pe_into_uc(uc: Uc, pe: bytes) -> None:
    e_lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
    num_sec = struct.unpack_from("<H", pe, e_lfanew + 6)[0]
    opt_size = struct.unpack_from("<H", pe, e_lfanew + 20)[0]
    opt = e_lfanew + 24
    size_image = struct.unpack_from("<I", pe, opt + 56)[0]
    uc.mem_map(IMAGE_BASE, _align_up(size_image))
    uc.mem_write(IMAGE_BASE, pe[:0x1000])
    sec_off = opt + opt_size
    for i in range(num_sec):
        o = sec_off + i * 40
        vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
        if rsz == 0 or raddr == 0:
            continue
        data = pe[raddr : raddr + rsz]
        if len(data) < vsz:
            data = data + b"\x00" * (vsz - len(data))
        uc.mem_write(IMAGE_BASE + va, data[: max(vsz, rsz)])


def run_dll_tail(
    dll: bytes,
    params: fl.FleshParams,
    *,
    stat: float,
    nsum: float,
    flesh_count: int,
    max_prob: int,
    dim_4520: int,
    dim_4530: int,
    b_inner: int,
    b_outer: int,
    exposure: float,
) -> dict:
    """Run ``0x102714e1 … 0x10271760`` for real and read the results struct."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(DATA_ADDR, DATA_SIZE)
    uc.reg_write(UC_X86_REG_FPCW, FPCW_WIN32)

    # --- the parameter struct (ebp) and the results struct (edi) -----------
    p_addr = DATA_ADDR
    uc.mem_write(p_addr, bytes(params.to_bytes()))
    res_addr = DATA_ADDR + 0x8000
    uc.mem_write(res_addr, b"\xcd" * 0x40)

    # --- the image object read by 0x104d4520 / 0x104d4530 ------------------
    # ``lea ecx,[esp+0x30]`` -> object at esp+0x30; ``mov ecx,[ecx+4]`` ->
    # a data block whose +0x14 / +0x18 hold the two dimensions.
    dims = DATA_ADDR + 0x9000
    uc.mem_write(dims + 0x14, struct.pack("<ii", int(dim_4520), int(dim_4530)))

    # --- the frame ---------------------------------------------------------
    esp = STACK_ADDR + 0x100000
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBP, p_addr)
    uc.reg_write(UC_X86_REG_EDI, res_addr)

    def w32(off: int, val: int) -> None:
        uc.mem_write(esp + off, struct.pack("<i", int(val)))

    def wf64(off: int, val: float) -> None:
        uc.mem_write(esp + off, struct.pack("<d", float(val)))

    w32(0x1C, max_prob)  # running max probability
    w32(0x24, flesh_count)  # fleshCount
    w32(0x34, dims)  # the object's +4 pointer
    w32(0x64, b_inner)  # inner border
    wf64(0x78, nsum)  # sum of weights
    wf64(0x94, stat)  # sum of weight*(p0+p1+p2)
    w32(0xA0, b_outer)  # outer border
    uc.mem_write(esp + 0x1CA0, struct.pack("<f", float(exposure)))

    stop = fl.FLESH_ADJUST_TAIL_EXIT

    def hook(u: Uc, address: int, size: int, _user: object) -> None:
        if address == stop:
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook, begin=stop, end=stop + 1)
    try:
        uc.emu_start(fl.FLESH_ADJUST_TAIL_ENTRY, 0, timeout=20_000_000)
    except UcError as e:  # pragma: no cover - diagnostics
        raise RuntimeError(f"unicorn flesh tail: {e}") from e

    blob = bytes(uc.mem_read(res_addr, 0x36))
    # +0x00 X, +0x08 nsum, +0x10 Q, +0x18 -D/130, +0x20 maxProb/255
    x, ns, frac, negd130, maxp255 = struct.unpack_from("<5d", blob, 0)
    triple = struct.unpack_from("<3h", blob, 0x30)
    return {
        "x": x,
        "nsum": ns,
        "fraction": frac,
        "neg_drive_over_130": negd130,
        "max_prob_over_255": maxp255,
        "triple": triple,
    }


def _stat_for(x: float, nsum: float) -> float:
    """The ``stat`` accumulator that yields flesh statistic ``x`` (tSpace=1)."""
    return x * nsum / fl.INV_1732


#: (stat, nsum, fleshCount, maxProb, dim4520, dim4530, b_inner, b_outer, exposure)
CASES: tuple[tuple, ...] = (
    # X above the 2740 aim -> D < 0 -> negative Delta (the §178 sign)
    (_stat_for(2860.0, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, 0.0),
    # X below the aim -> positive Delta
    (_stat_for(2620.0, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, 0.0),
    # exactly on the aim (frontLitBeta branch, D == 0)
    (_stat_for(2740.0, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, 0.0),
    # one ulp either side of the aim, to pin the >= / < beta selection
    (_stat_for(2740.0 + 1e-9, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, 0.0),
    (_stat_for(2740.0 - 1e-9, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, 0.0),
    # fleshCount == 0 -> X = aim, and the area guard also fires
    (0.0, 0.0, 0, -1, 800, 600, 30, 40, 0.0),
    # just under / just over the fleshCountThresh guard
    (_stat_for(2860.0, 1.0e7), 1.0e7, 2000, 200, 800, 600, 30, 40, 0.0),
    (_stat_for(2860.0, 1.0e7), 1.0e7, 3000, 200, 800, 600, 30, 40, 0.0),
    # the exposureLimit guard
    (_stat_for(2860.0, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, -3.9),
    (_stat_for(2860.0, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, -4.0),
    (_stat_for(2860.0, 1.0e7), 1.0e7, 40000, 200, 800, 600, 30, 40, -4.1),
    # far off the aim, both ways
    (2.9e10, 1.0e7, 40000, 200, 800, 600, 30, 40, 0.0),
    (-1.0e9, 1.0e7, 40000, 200, 800, 600, 30, 40, 0.0),
    # asymmetric borders, to exercise the crossed area insets
    (_stat_for(2700.0, 1.0e7), 1.0e7, 40000, 200, 1024, 683, 7, 61, 0.0),
    (_stat_for(2810.0, 9.4e6), 9.4e6, 33333, 77, 1024, 683, 61, 7, 0.0),
    # a tiny frame
    (_stat_for(2900.0, 4.0e3), 4.0e3, 90, 12, 40, 30, 3, 4, 0.0),
    # huge, to push the first ftol toward the 32-bit wrap
    (9.0e12, 1.0e6, 40000, 200, 800, 600, 30, 40, 0.0),
)


def _sweep_cases(n: int = 400) -> list[tuple]:
    """A deterministic pseudo-random sweep over the same argument shape."""
    out: list[tuple] = []
    s = 0x13579BDF
    for _ in range(n):
        def nxt() -> int:
            nonlocal s
            s = (s * 1103515245 + 12345) & 0x7FFFFFFF
            return s

        nsum = float(nxt() % 5_000_000 + 1)
        # aim the ratio near 2740 so the interesting branches are hit
        ratio = 2400.0 + (nxt() % 700_000) / 1000.0
        stat = ratio * nsum / fl.INV_1732
        cnt = nxt() % 60000
        out.append(
            (
                stat if nxt() % 8 else -stat,
                nsum,
                cnt,
                nxt() % 300 - 1,
                nxt() % 2000 + 40,
                nxt() % 2000 + 40,
                nxt() % 20,
                nxt() % 20,
                (nxt() % 200) / 20.0 - 6.0,
            )
        )
    return out


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll_path.is_file():
        print(f"FAILED: no DLL at {dll_path}")
        return 1
    dll = dll_path.read_bytes()
    md5 = hashlib.md5(dll).hexdigest()
    print(f"  {dll_path.name} md5 {md5}")
    if md5 != fl.PAKONIMAU_MD5:
        print(f"FAILED: expected md5 {fl.PAKONIMAU_MD5}")
        return 1
    dpi_md5 = hashlib.md5(fl.DEFAULT_DPI.read_bytes()).hexdigest()
    print(f"  {fl.DEFAULT_DPI.name} md5 {dpi_md5}")
    if dpi_md5 != fl.FLESH_DPI_DEFAULT_MD5:
        print(f"FAILED: expected DPI md5 {fl.FLESH_DPI_DEFAULT_MD5}")
        return 1

    base = fl.default_params()
    assert base.flesh_neutral_aim == 2740.0
    assert base.flesh_count_thresh == 0.00625
    assert base.front_lit_beta == base.back_lit_beta == 0.69
    assert base.percent_flesh_adj == 0.85
    assert base.exposure_limit == -4.0
    assert base.t_space == 1 and base.use_advanced == 0 and base.one_d_table == 1
    assert base.darken_only == 0
    print("  DPI parse (layout from fcn.10272380): OK")

    # Parameter variants, so the mapping itself is exercised rather than the
    # single shipped point.  ``darkenOnly`` and ``fleshPrefAdj`` in
    # particular are only observable when they are non-default.
    variants = {
        "shipped": base,
        "darkenOnly=1": replace(base, darken_only=1),
        "prefAdj=12.5": replace(base, flesh_pref_adj=12.5),
        "prefAdj=-7.25": replace(base, flesh_pref_adj=-7.25),
        "betas split": replace(base, front_lit_beta=0.42, back_lit_beta=0.91),
        "tSpace=0": replace(base, t_space=0),
        "pctAdj=0.5": replace(base, percent_flesh_adj=0.5),
        "thresh=0.5": replace(base, flesh_count_thresh=0.5),
        "expLimit=0.0": replace(base, exposure_limit=0.0),
    }

    fails = 0
    checked = 0
    nonzero = 0
    for name, params in variants.items():
        for case in CASES:
            stat, nsum, cnt, maxp, d20, d30, bi, bo, expo = case
            got = run_dll_tail(
                dll,
                params,
                stat=stat,
                nsum=nsum,
                flesh_count=cnt,
                max_prob=maxp,
                dim_4520=d20,
                dim_4530=d30,
                b_inner=bi,
                b_outer=bo,
                exposure=expo,
            )
            area = fl.flesh_area(d20, d30, bi, bo)
            host = fl.flesh_results(
                stat=stat,
                nsum=nsum,
                flesh_count=cnt,
                max_prob=maxp,
                area=area,
                exposure=expo,
                params=params,
            )
            checked += 1
            if got["triple"][0]:
                nonzero += 1
            ok = (
                got["triple"] == (host["delta"],) * 3
                and _same(got["x"], host["x"])
                and _same(got["fraction"], host["fraction"])
                and _same(got["neg_drive_over_130"], host["neg_drive_over_130"])
                and _same(got["max_prob_over_255"], host["max_prob_over_255"])
            )
            if not ok:
                fails += 1
                print(
                    f"  FAIL [{name}] {case}\n"
                    f"       dll triple={got['triple']} x={got['x']!r} "
                    f"Q={got['fraction']!r}\n"
                    f"       host delta={host['delta']} x={host['x']!r} "
                    f"Q={host['fraction']!r}"
                )
    print(
        f"  {checked} curated cases over {len(variants)} parameter variants "
        f"({nonzero} with a non-zero Delta): "
        f"{'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}"
    )

    # --- the sweep ---------------------------------------------------------
    sweep = _sweep_cases()
    sweep_fail = 0
    sweep_nonzero = 0
    for case in sweep:
        stat, nsum, cnt, maxp, d20, d30, bi, bo, expo = case
        got = run_dll_tail(
            dll,
            base,
            stat=stat,
            nsum=nsum,
            flesh_count=cnt,
            max_prob=maxp,
            dim_4520=d20,
            dim_4530=d30,
            b_inner=bi,
            b_outer=bo,
            exposure=expo,
        )
        area = fl.flesh_area(d20, d30, bi, bo)
        host = fl.flesh_delta(
            stat=stat,
            nsum=nsum,
            flesh_count=cnt,
            area=area,
            exposure=expo,
            params=base,
        )
        if got["triple"][0]:
            sweep_nonzero += 1
        if got["triple"] != (host,) * 3:
            sweep_fail += 1
            if sweep_fail <= 5:
                print(f"  SWEEP FAIL {case}: dll={got['triple']} host={host}")
    print(
        f"  {len(sweep)} swept cases ({sweep_nonzero} non-zero): "
        f"{'ALL BIT-EXACT' if not sweep_fail else f'{sweep_fail} FAILED'}"
    )
    fails += sweep_fail

    # --- the harness must have teeth: break the PORT, not the parameters ---
    real_ftol = fl._ftol32
    real_lt = fl._lt

    def _ftol_round(x: float) -> int:
        if x != x or x in (float("inf"), float("-inf")):
            return 0
        v = int(round(x))
        return ((v + 0x80000000) & 0xFFFFFFFF) - 0x80000000

    def _lt_le(a: float, b: float) -> bool:
        if a != a or b != b:
            return True
        return a <= b

    for name, patch in (
        ("_ftol32 -> round-to-nearest", ("_ftol32", _ftol_round)),
        ("guard '<' -> '<='", ("_lt", _lt_le)),
    ):
        setattr(fl, patch[0], patch[1])
        caught = 0
        for case in CASES + tuple(sweep[:200]):
            stat, nsum, cnt, maxp, d20, d30, bi, bo, expo = case
            got = run_dll_tail(
                dll, base, stat=stat, nsum=nsum, flesh_count=cnt,
                max_prob=maxp, dim_4520=d20, dim_4530=d30,
                b_inner=bi, b_outer=bo, exposure=expo,
            )
            host = fl.flesh_delta(
                stat=stat, nsum=nsum, flesh_count=cnt,
                area=fl.flesh_area(d20, d30, bi, bo),
                exposure=expo, params=base,
            )
            if got["triple"] != (host,) * 3:
                caught += 1
        fl._ftol32 = real_ftol
        fl._lt = real_lt
        print(f"  deliberate port bug '{name}': caught on {caught} cases")
        if not caught:
            print("  FAILED: the harness did not catch a deliberate port bug")
            fails += 1

    mutants = {
        "swap front/back beta": lambda p: replace(
            p, front_lit_beta=p.back_lit_beta, back_lit_beta=p.front_lit_beta
        ),
        "aim 2740 -> 2750": lambda p: replace(p, flesh_neutral_aim=2750.0),
        "percentFleshAdj 0.85 -> 0.86": lambda p: replace(p, percent_flesh_adj=0.86),
    }
    teeth = 0
    probe = replace(base, front_lit_beta=0.42, back_lit_beta=0.91)
    for name, mut in mutants.items():
        differ = 0
        for case in CASES:
            stat, nsum, cnt, maxp, d20, d30, bi, bo, expo = case
            area = fl.flesh_area(d20, d30, bi, bo)
            good = fl.flesh_delta(
                stat=stat, nsum=nsum, flesh_count=cnt, area=area,
                exposure=expo, params=probe,
            )
            bad = fl.flesh_delta(
                stat=stat, nsum=nsum, flesh_count=cnt, area=area,
                exposure=expo, params=mut(probe),
            )
            if good != bad:
                differ += 1
        print(f"  mutation '{name}': {differ}/{len(CASES)} cases move")
        if differ:
            teeth += 1
    if teeth != len(mutants):
        print("  FAILED: a mutation was invisible — the cases do not exercise it")
        fails += 1

    # --- what the six measured Deltas imply (tier 4, a consistency check) --
    print("  §178's six measured Deltas, inverted through the ported arithmetic:")
    xs = []
    for delta in (-40, 34, 15, 35, -59, 13):
        d, x = fl.invert_delta_to_statistic(delta, base)
        xs.append(x)
        print(f"    Delta {delta:+4d}  ->  D ~= {d:+9.3f}  ->  X ~= {x:9.2f}")
    span = max(abs(x - base.flesh_neutral_aim) for x in xs) / base.flesh_neutral_aim
    print(
        f"    aim = {base.flesh_neutral_aim:g}; implied X in "
        f"{min(xs):.0f}..{max(xs):.0f}, i.e. within {span * 100:.1f} % of the aim."
    )
    print(
        "    That is a CONSISTENCY CHECK ONLY (tier 4).  It is not a "
        "reproduction of the six values: no capture pairs one of them to the "
        "frame that produced it, so X cannot be checked against them even "
        "though the detector that produces X is now ported and bit-exact."
    )

    print("\n  Porting state (pakon_flesh module flags):")
    print(fl.porting_state())

    assert fl.FLESH_ADJUST_ARITHMETIC_PORTED
    # The detector's upstream blocks are proven by pakon_flesh_detector_golden.py
    # and pakon_flesh_threshold_golden.py, and the whole of fcn.10270280 by
    # pakon_flesh_whole_golden.py — not here.
    assert fl.FLESH_DETECTOR_PORTED
    assert fl.FLESH_THRESHOLD_PORTED

    if fails:
        print(f"FAILED ({fails})")
        return 1
    print("FLESH adjust arithmetic golden: ALL OK (bit-exact)")
    return 0


def _same(a: float, b: float) -> bool:
    return struct.pack("<d", a) == struct.pack("<d", b)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
