#!/usr/bin/env python3
r"""Real-DLL, full-frame, colour-chain harness -- docs/74 the ask that produced
this file: an end-to-end Unicorn run of the real ``PakonIMAu.dll`` colour
chain on a genuine captured frame, not a synthetic pattern or a crop.

WHAT THIS FILE IS, AND ISN'T
=============================
It is NEW, ADDITIVE code.  It does not modify any existing golden file --
every DLL-side call goes through ``pakon_autotone_assembled_golden``'s own
``build_dll``/``RealCapset``/``host_run``/``_diff_scalars``/``_diff_array``/
``shipped_contrast_params``, completely unchanged, the same way docs/74 §17
"adapted the existing harness's own functions, completely unmodified, to
real pixel data instead of synthetic patterns" -- this file does the same
thing again, on a full real frame instead of a crop, plus one further real
chain link (``balanceAreaImage``) that no prior pass ran under Unicorn.

TWO INDEPENDENT PIECES
========================
1. ``analyzeFugc`` (leaf pieces only, already verified elsewhere) through
   ``analyzeAutoTone`` (the full six-subsystem chain, ``0x100fb730``, run
   for real end to end) -- on a genuine captured frame's real post-FUGC
   RPD-12 array, extracted from the real, unmodified production path
   (``pakon_render.open_capture`` -> ``AnselEngine.render_scene``, the
   exact same code every render in this project takes; the post-FUGC array
   is captured by intercepting ``pakon_ansel.real_auto_tone`` at its own
   call boundary -- the function is called through unmodified, only its
   input argument is also recorded).  This directly extends docs/74 §17
   (which ran the same assembled harness on 48x48/400x400 crops) to a
   genuine full frame, and produces a genuine DLL-side ground-truth toned
   render to diff the Python port's own ``real_auto_tone()``/``to_srgb()``
   against on the SAME frame.

2. ``ColorNegativePath::balanceAreaImage`` (``0x10102b20``) -- the one
   stage docs/74 §22 left genuinely open ("whether ``balanceAreaImage``
   mutates the shared pixel buffer directly, in place, before ``cna``
   reads it").  This file makes a real, honest, bounded attempt to
   Unicorn-execute its real body against the real pixel buffer, watching
   every write to that buffer's address range directly rather than
   inferring mutation from static reading.  Its calling convention was
   derived fresh this pass from a live, tool-verified (not manually
   guessed) disassembly of the real driver call site
   (``fcn.10069490`` around ``0x10069835``-``0x10069859``, cross-checked
   against r2's own automatic variable/argument recovery for
   ``0x10102b20`` itself -- ``args: 0`` in r2's function-summary field, but
   a genuine ``var_8h`` at ``ebp+8``, i.e. r2 DID find the one real cdecl
   parameter, it just didn't relabel it ``arg_8h``) -- see the
   ``BalanceAreaImageCall`` class docstring below for the exact derivation
   and its own honestly-stated uncertainty.  If it faults on a call target
   this project has no existing characterization for, this file reports
   that fault verbatim and stops -- it does not stub around unknown vendor
   arithmetic to force a green result.

REAL DATA, REAL RULES
=======================
Uses a real capture already in this project's own cache
(``fresh-calibration-scan-20260814-065421.bin`` -- today's post-recalibration
test scan, already cited by ``pakon_ansel.py``'s own ``real_auto_tone``
neighbourhood comment).  Only aggregate percentile/statistical summaries are
printed anywhere in this file's output, per this project's rule against
describing ``captures/`` (or, here, the app cache's equivalent) contents at
the pixel level.

DLL: the same MD5-verified copy every docs/74 section already used
(``eea9dcf78ee21d4f7c515a6c2512242d``), re-checked at the top of ``main()``.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_full_colour_chain_golden.py [dll]``
"""
from __future__ import annotations

import hashlib
import struct
import sys
import time
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
TOOLS_DIR = HERE.parents[2]          # .../tools
REPO_ROOT = HERE.parents[3]          # repo root (this worktree)
sys.path.insert(0, str(HERE.parent))  # tools/ansel/python-pipeline itself
sys.path.insert(0, str(TOOLS_DIR))    # for pakon_render / pakon_decode / ...

import pakon_autotone as at                       # noqa: E402
import pakon_autotone_assembled_golden as asg      # noqa: E402
import pakon_autotone_shell_golden as shellg       # noqa: E402
import pakon_ast as ast_mod                        # noqa: E402
import pakon_citras as ct                          # noqa: E402
import pakon_citras_driver as citras_driver        # noqa: E402
import pakon_cna as cna                            # noqa: E402
import pakon_contrast as cx                        # noqa: E402
import pakon_dra as dra                            # noqa: E402
import pakon_toneHelper as th                      # noqa: E402
import pakon_ansel as ansel                        # noqa: E402

from unicorn import UC_HOOK_MEM_WRITE, UcError     # noqa: E402
from unicorn.x86_const import (                    # noqa: E402
    UC_X86_REG_EAX,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

import pakon_render as pr                          # noqa: E402

EXPECTED_MD5 = "eea9dcf78ee21d4f7c515a6c2512242d"
DEFAULT_DLL = shellg.DEFAULT_DLL

# The real capture used this pass -- today's post-recalibration test scan,
# already sitting in the app's own cache (not this repo's gitignored
# captures/ dir, same convention docs/74 §7/§12 already used for
# scan-20260812-*.bin). Picked over the older gold400.bin/scan-20260812-*
# captures used by earlier docs/74 sections at the user's own explicit
# direction this pass, to exercise the current (not pre-recalibration)
# hardware state.
CAPTURE = Path(
    "/Users/guy/Library/Caches/PakonScan/captures/"
    "fresh-calibration-scan-20260814-065421.bin"
)
FRAME_INDEX = 1   # the one "good"-confidence frame on this roll (of 5)

BALANCE_AREA_IMAGE = 0x10102B20   # pakon_analyse_roll.PATH_BALANCE_AREA_IMAGE
DRIVER_ADDREF_WRAP = 0x10006880   # see BalanceAreaImageCall docstring


def patch_unchecked_instruction_cap(count: int = 50_000_000_000) -> None:
    """Fix a real harness bug found THIS pass, not in any existing golden
    file's own contents: ``pakon_autotone_shell_golden.Emu.call`` hard-codes
    ``uc.emu_start(va, RET_MAGIC, timeout=0, count=200_000_000)`` and never
    checks that EIP actually reached ``RET_MAGIC`` afterward.  Every existing
    golden's own scenarios are small enough (largest: 400x400 = 160,000
    pixels) that 200,000,000 emulated x86 instructions is always far more
    than ``cna``'s own real analysis needs, so this never mattered before.

    A genuine full real frame does need more: confirmed directly this pass
    -- a 1043x1043 real crop (1,087,849 px) needs ~16s of real Unicorn
    execution even once the cap is no longer the limit, and the full real
    frame (5,930,000 px) needs ~57s.  Both are comfortably above what
    200,000,000 instructions buys at this DLL's real per-pixel cost, so the
    OLD cap was silently truncating ``cna``'s own analysis mid-function on
    real full-scale frames.  Because Unicorn's ``emu_start`` returns
    normally (no exception) when its own ``count`` budget is exhausted,
    ``Emu.call`` (which never checks final EIP) reported success with
    whatever ``AnsStatus`` value happened to already be sitting at ``sret``
    -- which reads as OK because that memory starts zero-filled -- while
    every result the truncated code path never got to write (``cna``'s own
    ``ToneScaleLut``, and everything ``dra`` derives from it) stayed at
    its allocation-time zero fill.  This produced exactly the shape of
    "real divergence" an earlier draft of this file's own Stage 2 first
    reported: sane ``threshold``/``nEdgePixels`` (written early, before the
    budget ran out) alongside an all-zero ``ToneScaleLut``/``dra`` (written
    late, after it did) -- see docs/74 §24's own corrected account.

    Does NOT modify ``pakon_autotone_shell_golden.py`` on disk -- replaces
    the bound method on the (already-imported) class object at runtime, in
    this process only, the same class of fix as this file's own
    ``HEAP``/``HEAP_SZ`` relocation immediately below.  A genuinely fixed
    ``Emu.call`` belongs in that file eventually; this is a diagnostic-grade
    patch scoped to this new script, not a claim that the fix has landed
    upstream.
    """
    RET_MAGIC = shellg.RET_MAGIC
    STACK = shellg.STACK
    STACK_SZ = shellg.STACK_SZ

    def call_checked(self, va: int, args=(), ecx: int | None = None) -> int:
        uc = self.uc
        esp = STACK + STACK_SZ - 0x20000
        blob = b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        esp -= len(blob)
        if blob:
            uc.mem_write(esp, blob)
        esp -= 4
        uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
        uc.reg_write(UC_X86_REG_ESP, esp)
        if ecx is not None:
            uc.reg_write(UC_X86_REG_ECX, ecx)
        self.faults = []
        try:
            uc.emu_start(va, RET_MAGIC, timeout=0, count=count)
        except UcError as ex:
            raise RuntimeError(
                f"emu {va:#x} eip={uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
                + ("; " + "; ".join(self.faults[:2]) if self.faults else "")
            ) from ex
        eip = uc.reg_read(UC_X86_REG_EIP)
        if eip != RET_MAGIC:
            raise RuntimeError(
                f"emu {va:#x} did not reach RET_MAGIC (stopped at "
                f"eip={eip:#x}) -- hit the {count:,}-instruction cap "
                f"mid-execution; raise `count` further rather than trust "
                f"this result")
        if self.faults:
            raise RuntimeError(f"emu {va:#x} faults: {self.faults[:2]}")
        return uc.reg_read(UC_X86_REG_EAX)

    shellg.Emu.call = call_checked


# ---------------------------------------------------------------------------
# 0. real post-FUGC input, from the real, unmodified production path
# ---------------------------------------------------------------------------


def get_real_frame(frame_index: int = FRAME_INDEX):
    """Open the real capture through the real, unmodified production path
    and return ``(post_fugc_x, python_srgb, roll, eng)``.

    ``post_fugc_x`` is intercepted at ``pakon_ansel.real_auto_tone``'s own
    call boundary -- the function still runs, completely unmodified, and its
    return value is what ``python_srgb`` is built from (via
    ``AnselEngine.to_srgb``, also unmodified); only the ARGUMENT it was
    called with is additionally recorded on the way through.  This is the
    same real value ``real_auto_tone`` itself receives on every real render;
    nothing here re-derives or approximates FUGC/balance -- ``open_capture``,
    ``scene_rpd12`` and ``render_scene`` all run exactly as the app itself
    runs them (``tools/pakon_render.py``'s own ``_render_colour_python``).
    """
    import tempfile

    captured: dict = {}
    original_real_auto_tone = ansel.real_auto_tone

    def _capture(rpd12: np.ndarray, scene_type: int = 0):
        captured["x"] = rpd12.copy()
        captured["scene_type"] = scene_type
        return original_real_auto_tone(rpd12, scene_type)

    ansel.real_auto_tone = _capture
    try:
        with tempfile.TemporaryDirectory() as ws, warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            roll = pr.open_capture(str(CAPTURE), ws, "full_chain_golden",
                                   film_path="ColNeg")
            f = roll.frames[frame_index]
            seg = roll.slice14(f.a, f.b, 1)   # step=1 == SCALES["full"]
            eng = roll.engine()
            srgb = pr._render_colour_python(roll, seg, {})
    finally:
        ansel.real_auto_tone = original_real_auto_tone

    if "x" not in captured:
        raise RuntimeError(
            "real_auto_tone was never called -- shasta_stand_in must be "
            "False on this render path; nothing to compare")
    return captured["x"], srgb, roll, eng


# ---------------------------------------------------------------------------
# 1. the six-subsystem chain, real DLL, on the FULL real frame
# ---------------------------------------------------------------------------


def run_assembled_chain_on_real_frame(pe: bytes, x: np.ndarray):
    """``asg.build_dll``/``asg.host_run`` etc., completely unmodified,
    fed the real frame instead of ``asg.make_image()``'s synthetic patterns
    -- exactly docs/74 §17's own method, extended from a crop to the whole
    frame.

    The emulated heap in ``pakon_autotone_shell_golden.Emu`` (``HEAP``/
    ``HEAP_SZ``, 32 MB at ``0x0D000000``, chosen for the existing goldens'
    largest scenario, 400x400=160,000 pixels) is not big enough for a real
    multi-megapixel frame's pixel buffer alone.  Rather than edit that
    constant in the existing golden file (explicitly out of scope --
    "Do not modify any existing golden file"), ``main()`` relocates the
    module-level ``HEAP``/``HEAP_SZ`` globals at RUNTIME, before calling
    this function, to a much larger region clear of both the loaded image
    (``IMAGE_BASE=0x10000000``) and the stack (``STACK=0x0BF00000``..
    ``0x0C700000``).  ``Emu.__init__``/``alloc`` read ``HEAP``/``HEAP_SZ``
    as bare module globals at call time (not captured constants), so this
    is a real, in-effect capacity change, not a cosmetic one -- confirmed
    by the fact the run below would otherwise raise ``RuntimeError: emu
    heap exhausted`` on a frame this size.  NOTE: the relocation must stay
    in effect for the lifetime of the returned ``RealCapset``'s emulator
    (``d.emu``) -- restoring the old, smaller ``HEAP``/``HEAP_SZ`` while
    that same emulator is still in use (e.g. for stage 4's
    ``BalanceAreaImageCall``, which allocates more heap on the SAME
    instance) makes ``alloc``'s bounds check compare the already-advanced
    ``brk`` pointer against the OLD, smaller ceiling and fail immediately
    -- caught empirically this pass, not theoretical.
    """
    height, width = int(x.shape[0]), int(x.shape[1])
    clipped = np.clip(np.rint(x), -32768, 32767).astype(np.int16)
    image = cna.CnaImage(width=width, height=height,
                         pixels=clipped.reshape(-1).tolist())

    dra_params = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    th_params = th.load_params()
    cx_selected = asg.shipped_contrast_params()
    cx_embedded = cx.ContrastParams()
    ast_params_obj = ast_mod.AstParams.defaults()
    ct_params = ct.default_params()

    t0 = time.time()
    d = asg.build_dll(pe, image, dra_params=dra_params,
                      th_params=th_params, cx_selected=cx_selected,
                      cx_embedded=cx_embedded,
                      ast_params_obj=ast_params_obj, ct_params=ct_params)
    dll = d.run(scene_type=0)
    dt = time.time() - t0
    return d, dll, clipped, dt


def diff_against_python_port(d, dll: dict, x: np.ndarray, clipped: np.ndarray,
                             *, dra_params, th_params, cx_selected,
                             ast_params_obj, ct_params) -> list[str]:
    """Field-by-field: real DLL vs the pure-Python assembled chain
    (``asg.host_run``/``asg._diff_scalars``/``asg._diff_array``, unmodified).
    """
    bad: list[str] = []
    image = cna.CnaImage(width=int(x.shape[1]), height=int(x.shape[0]),
                         pixels=clipped.reshape(-1).tolist())
    h = asg.host_run(image, dra_params=dra_params, th_params=th_params,
                     cx_params=cx_selected, ast_params_obj=ast_params_obj,
                     ct_params=ct_params, scene_type=0)

    if dll["thrown"] is not None:
        return [f"DLL threw unexpectedly: {dll['thrown']}"]
    if not dll["status_ok"]:
        return ["DLL returned a non-OK status unexpectedly"]

    cna_dll = d.cna_results()
    cna_host_raw = h["cna"]
    cna_host = {name: at.read_field("AnsCnaResults", cna_host_raw.raw, name)
               for _off, name, _k, _s in
               at.AUTOTONE_WORK_LAYOUT["AnsCnaResults"]["fields"] if name}
    asg._diff_scalars("cna", cna_dll, cna_host,
                      ["nPixels", "threshold", "nEdgePixels", "darkInSigma",
                       "lightInSigma", "darkOutSigma", "lightOutSigma",
                       "elmoPercent", "bElmoOccured"], bad)
    asg._diff_array("cna.ToneScaleLut",
                    d.array_i16(cna_dll["ToneScaleLut"],
                                len(cna_host_raw.tone_scale_lut)),
                    cna_host_raw.tone_scale_lut, bad)
    asg._diff_array("cna.LuminanceHist",
                    d.array_i32(cna_dll["LuminanceHist"],
                                len(cna_host_raw.luminance_hist)),
                    cna_host_raw.luminance_hist, bad)
    asg._diff_array("cna.EdgeHist",
                    d.array_i32(cna_dll["EdgeHist"],
                                len(cna_host_raw.edge_hist)),
                    cna_host_raw.edge_hist, bad)

    dra_dll = d.dra_results()
    dra_host = h["dra"]
    asg._diff_scalars("dra", dra_dll, dra_host,
                      ["nSmallBins", "nLargeBins", "nLumPixels", "nEdgePixels",
                       "lumMin", "lumMax", "edgeMin", "edgeMax", "effMin",
                       "effMax"], bad)
    asg._diff_array("dra.DraLut",
                    d.array_i16(dra_dll["DraLut"], dra_host.nSmallBins),
                    dra_host.DraLut, bad)

    th_dll_value = d.emu.ri32(d.th_impl + 0x80 + 0xB4)
    if th_dll_value != h["th"].toneHelperValue:
        bad.append(f"toneHelper.toneHelperValue: dll={th_dll_value} "
                  f"host={h['th'].toneHelperValue}")

    cx_dll = d.contrast_results()
    cx_host = h["cx"]
    asg._diff_scalars("contrast", cx_dll, cx_host,
                      ["lutSize", "lowSlope", "highSlope"], bad)
    asg._diff_array("contrast.OutToneLut",
                    d.array_i16(cx_dll["OutToneLut"], cx_host.lutSize),
                    cx_host.OutToneLut or [], bad)

    ct_host = h["ct"]
    lut_size_dll = d.emu.ri32(d.ct_impl + ct.IMPL_LUT_SIZE)
    lut_ptr_dll = d.emu.r32(d.ct_impl + ct.IMPL_TONE_LUT)
    dll_lut = d.array_i16(lut_ptr_dll, lut_size_dll) if lut_ptr_dll else []
    if lut_size_dll != ct_host.lut_size:
        bad.append(f"citras.lut_size: dll={lut_size_dll} "
                  f"host={ct_host.lut_size}")
    asg._diff_array("citras.ToneLut", dll_lut, ct_host.tone_lut or [], bad)

    return bad


# ---------------------------------------------------------------------------
# 2. a genuine DLL-derived ground-truth render, diffed against the port's
#    own real_auto_tone()/.to_srgb() on the identical frame
# ---------------------------------------------------------------------------


def dll_ground_truth_srgb(d, x: np.ndarray, clipped: np.ndarray, eng,
                          ct_params) -> np.ndarray:
    """Apply the REAL DLL's own ``OutToneLut`` through the same real
    ``citras_driver.apply_citras`` vendor-apply ``pakon_ansel.real_auto_tone``
    itself uses for its own (Python-LUT) output -- i.e. every step here is
    unmodified production code; only the LUT's SOURCE changes, from the
    Python port's own ``contrast_state.results.OutToneLut`` to the real
    DLL's own ``contrast_results()['OutToneLut']``.  This is the "genuine
    ground-truth reference render" the task asked for: the vendor's own
    tone curve, applied by this project's own already-verified apply step,
    then through the same ``AnselEngine.to_srgb`` every render in this
    project uses.
    """
    cx_dll = d.contrast_results()
    lut = d.array_i16(cx_dll["OutToneLut"], cx_dll["lutSize"])
    p = citras_driver.CitrasOpParams(
        sigma=ct_params.sigma, block_size=ct_params.blockSize,
        min_avoidance=ct_params.minAvoidance,
        max_gradient=ct_params.maxGradient,
        low_gradient_threshold=ct_params.lowGradientThreshold,
        high_gradient_threshold=ct_params.highGradientThreshold,
        min_value=ct_params.minValue, max_value=ct_params.maxValue,
    )
    toned = citras_driver.apply_citras(
        clipped, np.asarray(lut, dtype=np.int64), p).astype(np.float64)
    return eng.to_srgb(toned)


def scale_sweep_diagnostic(pe: bytes, x: np.ndarray,
                           sizes=((400, 400), (800, 800), (1500, 1500))
                           ) -> list[str]:
    """When Stage 2 finds a real divergence on the full frame, narrow down
    WHERE it starts, on real crops of the SAME real frame (not synthetic
    data, not a different capture) at a few sizes between the
    already-known-good 400x400 (docs/74 §17's own crop size) and the full
    frame.  Reports ``cna``'s own ``threshold``/``nEdgePixels`` (sane at
    every size tested, so the divergence is not the threshold-search loop)
    against whether ``ToneScaleLut`` is all-zero (the degenerate shape seen
    on the full frame).  Cheap relative to a full-frame run (a few seconds
    to low tens of seconds per size), run only when Stage 2 already found a
    mismatch worth explaining.
    """
    lines = []
    for size in sizes:
        hh, ww = size
        if hh > x.shape[0] or ww > x.shape[1]:
            continue
        crop = x[0:hh, 0:ww, :]
        d, dll, clipped, dt = run_assembled_chain_on_real_frame(pe, crop)
        cna_res = d.cna_results()
        tsl = np.array(d.array_i16(cna_res["ToneScaleLut"], 5000))
        line = (f"  {hh}x{ww} ({hh*ww:,} px, {dt:.1f}s): "
               f"threshold={cna_res['threshold']} "
               f"nEdgePixels={cna_res['nEdgePixels']} "
               f"ToneScaleLut all-zero={bool(np.all(tsl == 0))} "
               f"ToneScaleLut[0:4]={tsl[:4].tolist()}")
        print(line)
        lines.append(line)
    return lines


def percentiles(img: np.ndarray) -> dict:
    out = {}
    for c, name in enumerate("RGB"):
        ch = img[:, :, c].astype(np.float64)
        out[name] = [float(np.percentile(ch, q)) for q in (1, 50, 99)]
    return out


# ---------------------------------------------------------------------------
# 3. balanceAreaImage -- the one open thread from docs/74 §22
# ---------------------------------------------------------------------------


class BalanceAreaImageCall:
    """A real, bounded, honestly-scoped attempt to Unicorn-execute
    ``ColorNegativePath::balanceAreaImage`` (``0x10102b20``) for real.

    CALLING CONVENTION -- derived fresh this pass, from live tool output,
    not manual byte-counting alone
    -------------------------------------------------------------------
    r2 (``aa; af @ 0x10102b20; afvj``) reports ``callconv: cdecl``,
    ``args: 0`` in its coarse summary, but its own per-variable list
    includes ``var_8h`` at ``{"base":"ebp","offset":8}`` -- the canonical
    cdecl slot for a function's first (and, per the summary, only) stack
    parameter.  Cross-checked directly: 13 separate reads of that exact
    slot appear throughout the function body (``grep -c var_8h`` on a full
    ``pdf`` dump), confirming it is read repeatedly as a real incoming
    value, not misclassified dead stack.

    At the real call site (driver ``fcn.10069490``, live ``pd`` at
    ``0x10069835``-``0x10069859``, re-run this pass, not taken from any
    prior doc's transcription):

        lea eax, [esi + 0x4ac]
        push eax                    ; rec[2] = &esi+0x4ac
        xor eax, eax
        mov al, byte [esi + 0x29]
        push eax                    ; rec[1] = zx(byte[esi+0x29])
        push ecx                    ; rec[0] = ecx (whatever the driver's
                                     ;   own inherited value is at this point)
        mov ecx, esp                ; ecx = &rec
        mov dword [ebp + 0xc], esp  ; the driver's OWN local slot now holds &rec
        push esi                    ; esi = the driver's own "this"
        call 0x10006880             ; see below
        lea ecx, [ebp + 0xc]
        push ecx                    ; the ONE real argument: &(driver local)
        call 0x10102b20
        add esp, 0x10

    ``0x10006880`` (disassembled in full this pass) is
    ``ret 4`` (one stack arg, ``arg_4h``) plus an implicit ``ecx`` "this":
    ``eax = *(arg_4h); *(ecx_this) = eax; if (eax) AddRef(eax+4)`` -- i.e.
    a generic "wrap a raw pointer read from ``*driverThis`` into a
    refcounted slot" helper, the same shape as the AddRef idiom
    (``0x100065e0``) already characterized elsewhere in this DLL.  It
    OVERWRITES ``rec[0]`` with ``*esi`` (a field of the driver object,
    AddRef'd) before ``balanceAreaImage`` ever runs.

    So the argument this class constructs is: a pointer to a driver-local
    slot, which itself points to a 3-dword record
    ``{*esi (AddRef'd), zx(esi+0x29), &esi+0x4ac}`` -- double indirection,
    matching what the callee's own body does with it (``mov esi, dword
    [var_8h]`` inside ``0x10102b20`` dereferences it exactly ONCE before
    using the result, at the "area capability not found" throw path,
    ``0x10102c0b``).

    WHAT IS HONESTLY *NOT* ESTABLISHED
    ------------------------------------
    * The real value of ``*esi`` (the driver's own field 0) and
      ``esi+0x29`` this pass has no independent citation for -- both are
      filled here from the ALREADY-BUILT ``RealCapset.holder`` object
      (a real vftable, big refcount, survives AddRef/Release -- the same
      object the assembled ``analyzeAutoTone`` harness already uses) and
      zero, respectively, flagged plainly as synthetic scaffolding, not
      derived vendor values.
    * ``&esi+0x4ac`` is passed here as a pointer into a small header
      modelled on the SAME image-descriptor layout ``cna``'s own
      ``acquire`` already uses (width@+0xc, height@+0x10, pixels@+0x20 --
      ``pakon_cna.PARAMS_AT``-adjacent convention) so real image bytes
      flow into whatever ``balanceAreaImage`` does with this field --
      this is a MODELLING CHOICE, not a confirmed struct layout for this
      specific offset; the field's real vendor shape at ``+0x4ac`` was
      not independently re-derived this pass.
    * Everything ``balanceAreaImage``'s own body does beyond the
      "capability not found" path at its very entry (its 1379-instruction,
      295-basic-block real body, calling into several targets --
      ``0x100dc060``, ``0x100d9340``, ``0x100dc390``, ``0x1021fec0``,
      ``0x100daac0``, ``0x100f8340`` -- this project has no existing
      characterization for) is NOT modelled here.  If execution reaches
      one of those and it needs real behaviour this harness cannot supply
      without guessing, ``run()`` reports the exact fault and stops --
      it does not stub around it.
    """

    def __init__(self, emu: "asg.AssembledEmu", capset: "asg.RealCapset",
                pixels_len_bytes: int):
        self.emu = emu
        self.capset = capset
        e = emu

        # rec: {*esi-ish holder (AddRef'd, pre-filled), zx-byte, &image-hdr}
        image_hdr = capset.arg2   # same real image descriptor RealCapset
                                  # already built for analyzeAutoTone -- see
                                  # class docstring's "NOT established" note.
        rec = e.alloc(0x0C)
        e.wu32(rec + 0x0, capset.holder)   # already AddRef-survivable (BIG_REFCOUNT)
        e.wu32(rec + 0x4, 0)                # zx(esi+0x29) -- synthetic, flagged above
        e.wu32(rec + 0x8, image_hdr)        # &esi+0x4ac -- synthetic, flagged above

        # the driver's own local slot ([ebp+0xc] in the real caller's frame)
        # -- the argument balanceAreaImage actually receives is the ADDRESS
        # of this cell (see class docstring: "lea ecx,[ebp+0xc]; push ecx").
        self.driver_local = e.alloc(4)
        e.wu32(self.driver_local, rec)

        self.rec = rec
        self.image_hdr = image_hdr
        # image_hdr layout mirrors cna's own arg2 convention (width@0xc,
        # height@0x10, pixels ptr @0x20) -- see class docstring.
        self.pixels_ptr = e.r32(image_hdr + 0x20)
        self.pixels_len_bytes = pixels_len_bytes

    @staticmethod
    def register_synthetic_area_hit(capset: "asg.RealCapset") -> None:
        """Make ``find("area")`` (``CAP_FIND_THUNK``, the same real thunk
        ``analyzeAutoTone``'s own six lookups already use) return a HIT
        instead of a miss, so ``balanceAreaImage`` takes its real
        normal-operation branch instead of the "Area capability not found"
        throw path at its very entry (``0x10102c0b``, per §22's own
        corrected reading: a hit is the normal case for a real render,
        since ``analyzeArea`` has not populated it yet on the very first
        call but the capability itself is always declared).

        The Impl this hands back is a zero-filled scratch blob behind a
        generic one-slot vftable (every virtual call resolves to a bare
        ``ret 4``) -- the SAME placeholder shape ``RealCapset`` itself
        already uses for ``"pfd"`` (permanently disabled in this project,
        never a real Impl either).  This is not a claim about ``area``'s
        real vftable or Impl layout, neither of which this pass derived --
        it exists only to let real code past the guard, honestly labelled.
        """
        e = capset.emu
        dtor = e.stub()
        e.uc.mem_write(dtor, b"\xC2\x04\x00")   # ret 4
        generic_vft = e.alloc(0x40)
        for i in range(8):
            e.wu32(generic_vft + 4 * i, dtor)
        area_cap = e.alloc(0x40)
        e.wu32(area_cap, generic_vft)
        e.wu32(area_cap + 4, 0x01000000)
        e.wu8(area_cap + at.CAP_ENABLE_BYTE, 1)
        e.wu8(area_cap + at.CAP_FLAG_BYTE_D, 1)
        e.wu32(area_cap + at.CAP_IMPL_PTR, e.alloc(0x200))
        capset.caps["area"] = area_cap

    def run(self) -> dict:
        e = self.emu
        # Watch every write to the real pixel buffer specifically -- this is
        # deliverable #1: does balanceAreaImage mutate it in place.
        pixel_writes: list[tuple[int, int, int]] = []

        def watch_pixel_writes(uc, access, address, size, value, _u):
            pixel_writes.append((address, size, value))
            return True

        hook = e.uc.hook_add(
            UC_HOOK_MEM_WRITE, watch_pixel_writes,
            begin=self.pixels_ptr,
            end=self.pixels_ptr + self.pixels_len_bytes - 1)

        result = {"pixel_writes": pixel_writes, "fault": None,
                 "status_ok": None}
        try:
            eax = e.call(BALANCE_AREA_IMAGE, [self.driver_local])
            result["eax"] = eax
            result["status_ok"] = True
        except RuntimeError as exc:
            result["fault"] = str(exc)
            result["status_ok"] = False
        finally:
            e.uc.hook_del(hook)
        return result


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll_path.exists():
        print(f"{dll_path} not found -- run "
              f"'python3 tools/re/reachability.py extract' first")
        return 2
    pe = dll_path.read_bytes()
    got_md5 = hashlib.md5(pe).hexdigest()
    print(f"== DLL {dll_path}  MD5={got_md5} ==")
    if got_md5 != EXPECTED_MD5:
        print(f"  MD5 MISMATCH -- expected {EXPECTED_MD5}; refusing to "
              f"trust this copy for a ground-truth run")
        return 2
    print("  MD5 verified against docs/74's own citation.\n")

    if not CAPTURE.exists():
        print(f"{CAPTURE} not found -- this pass's chosen real capture is "
              f"not present on this machine")
        return 2

    print(f"== Stage 0: real frame, real production path "
          f"({CAPTURE.name}, frame {FRAME_INDEX}) ==")
    x, python_srgb, roll, eng = get_real_frame(FRAME_INDEX)
    h, w = x.shape[0], x.shape[1]
    print(f"  frame shape {h}x{w} ({h * w:,} pixels)  "
         f"roll.film_base={[round(v) for v in roll.film_base]}")
    print()

    print("== Stage 1: real DLL, real six-subsystem analyzeAutoTone, "
         "FULL real frame (not a crop) ==")
    # Relocate the emulated heap for the lifetime of this process -- see
    # run_assembled_chain_on_real_frame's own docstring for why this can't
    # be a scoped context manager around just that one call.
    shellg.HEAP = 0x20000000
    shellg.HEAP_SZ = 0x08000000   # 128 MiB -- clear of IMAGE_BASE/STACK
    # Fix the real harness bug found this pass: Emu.call's own hard-coded
    # 200,000,000-instruction cap silently truncates real full-frame `cna`
    # analysis and misreports it as a clean OK -- see
    # patch_unchecked_instruction_cap's own docstring for the full account,
    # including the confirmed real timings this was checked against.
    patch_unchecked_instruction_cap()
    d, dll, clipped, dt = run_assembled_chain_on_real_frame(pe, x)
    print(f"  wall time: {dt:.1f}s  status_ok={dll['status_ok']}  "
         f"thrown={dll['thrown']}")
    if dll["thrown"] is not None or not dll["status_ok"]:
        print("  DLL run did not complete cleanly -- stopping here, "
             "honestly, not forcing a comparison.")
        return 1

    dra_params = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    th_params = th.load_params()
    cx_selected = asg.shipped_contrast_params()
    ast_params_obj = ast_mod.AstParams.defaults()
    ct_params = ct.default_params()

    print("\n== Stage 2: field-by-field diff, real DLL vs pure-Python "
         "assembled chain, on this real frame's real data ==")
    bad = diff_against_python_port(
        d, dll, x, clipped, dra_params=dra_params, th_params=th_params,
        cx_selected=cx_selected, ast_params_obj=ast_params_obj,
        ct_params=ct_params)
    if bad:
        print(f"  {len(bad)} field(s) differ:")
        for b in bad[:20]:
            print(f"    {b}")
        print("\n  This is a REAL, reproducible divergence on real, "
             "full-frame data -- not seen by any prior crop-scale test "
             "(largest previously run: 400x400, docs/74 §17). Narrowing "
             "down where it starts, on real crops of this SAME frame:")
        scale_sweep_diagnostic(pe, x)
    else:
        print("  bit-exact on every field checked (cna/dra/toneHelper/"
             "contrast/citras), on the real, full, uncropped frame.")

    print("\n== Stage 3: genuine DLL-derived ground-truth render, vs the "
         "Python port's own real_auto_tone()/.to_srgb() on the IDENTICAL "
         "frame ==")
    try:
        dll_srgb = dll_ground_truth_srgb(d, x, clipped, eng, ct_params)
    except Exception as exc:  # noqa: BLE001 -- report, don't hide
        print(f"  BLOCKED -- could not build a DLL ground-truth render: "
             f"{exc!r}")
        print("  (downstream of the Stage 2 divergence above: contrast's "
             "own OutToneLut is built from cna/dra's -- if those are "
             "degenerate on this frame, the DLL's own tone LUT here is "
             "not a trustworthy ground truth to diff against; reported "
             "as blocked rather than compared.)")
    else:
        p_python = percentiles(python_srgb)
        p_dll = percentiles(dll_srgb)
        print("  sRGB [p1, p50, p99] per channel:")
        for name in "RGB":
            py = [round(v, 1) for v in p_python[name]]
            dl = [round(v, 1) for v in p_dll[name]]
            print(f"    {name}: python={py}  dll_ground_truth={dl}")
        diff = np.abs(python_srgb.astype(np.float64)
                      - dll_srgb.astype(np.float64))
        print(f"  |python - dll_ground_truth| over all pixels/channels: "
             f"mean={diff.mean():.3f}  p99={np.percentile(diff, 99):.2f}  "
             f"max={diff.max():.1f}")

    print("\n== Stage 4: balanceAreaImage (0x10102b20), real body, real "
         "pixel buffer -- docs/74 §22's own open thread ==")
    pixels_len_bytes = clipped.size * 2   # int16 per element

    def _run_balance_area_image(label: str, register_area: bool) -> None:
        print(f"  -- {label} --")
        try:
            bai = BalanceAreaImageCall(d.emu, d, pixels_len_bytes)
            if register_area:
                BalanceAreaImageCall.register_synthetic_area_hit(d)
            bres = bai.run()
            if bres["status_ok"]:
                print(f"    ran to completion (no Unicorn fault). "
                     f"eax={bres['eax']:#x}  pixel-buffer writes observed: "
                     f"{len(bres['pixel_writes'])}")
                if bres["pixel_writes"]:
                    print("    DID write into the shared pixel buffer -- "
                         "first few:")
                    for addr, size, val in bres["pixel_writes"][:8]:
                        print(f"      addr={addr:#x} size={size} "
                             f"val={val:#x}")
                else:
                    print("    did NOT write into the shared pixel buffer "
                         "on this run.")
            else:
                print(f"    BLOCKED -- did not run to completion: "
                     f"{bres['fault']}")
                print(f"    pixel-buffer writes observed before the fault: "
                     f"{len(bres['pixel_writes'])}")
        except Exception as exc:  # noqa: BLE001 -- report, don't hide
            print(f"    BLOCKED -- setup/execution raised: {exc!r}")

    _run_balance_area_image(
        "find(\"area\") MISS -- the entry-guard throw path", False)
    _run_balance_area_image(
        "find(\"area\") HIT (synthetic Impl) -- past the entry guard, "
        "into the real body", True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
