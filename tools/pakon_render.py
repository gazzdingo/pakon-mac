#!/usr/bin/env python3
"""Parametric per-frame render engine for the Pakon scanning application.

One image per frame. Nothing on this path writes a file the user keeps —
frames are rendered from (capture + parameters) on demand, in memory, and
handed straight to the UI. Only ``export_frame`` writes, and only where the
user asked.

FIDELITY RULE
-------------
The image path adds **nothing** of its own. Every operation here is either a
call into ``pakon_decode`` / ``pakon_ansel`` / ``pakon_color``, or geometry
(rotate / flip / crop) which selects pixels without altering their values.
There is no tone curve, no saturation, no sharpening, no percentile stretch
and no white balance in this file — see ``UNAVAILABLE_CONTROLS`` for the
controls that were dropped for exactly that reason.

``render_frame(..., scale="full")`` with default parameters is intended to be
**byte-for-byte identical** to the corresponding ``frames/NN_srgb.png`` from
``pakon_decode.py strip --color --icc --frames``. ``pakon_render.py verify``
proves it on a real capture and prints the differing pixel count.

What that does and does not establish:

  verified here   the UI introduces zero deviation from the owned pipeline.
  NOT verified    that the owned pipeline equals Kodak's. The Ansel stage is
                  documented by its own authors as a stand-in
                  (``SETSHIFTS_12_PORTED = False``, "full AnsOrder/pcode is
                  NOT ported" — pakon_decode's docstring). Byte equality with
                  PSI/TLB cannot be claimed until that lands, and this module
                  must not be read as claiming it.

Ownership: this module *calls* the colour work in ``tools/pakon_decode.py``
and ``tools/ansel/`` — it does not modify or duplicate it. The two narrow
places it re-expresses vendor arithmetic, both using ``pakon_color``'s own
LUT/matrix/quantisation so the kernel is not duplicated:

  * ``_rpd16`` — ``pakon_decode.render_rpd`` recomputes Dmin per call and
    prints to stdout. The UI needs the *roll* Dmin held fixed while one
    frame's offsets change (docs/11 §5: per-frame-only balancing breaks the
    look), so the offset column has to be an argument. The accumulate, the
    rounding and the 0..4092 clamp are the same expressions in the same order.
  * ``roll_offsets_from`` — computes the same p99 Dmin as ``render_rpd``, but
    from an exact 14-bit histogram so it can be taken over the whole strip
    without materialising it. Integer inputs make the histogram exact, not an
    approximation.

Pipeline per frame (docs/11):

    capture .bin
      → segment_lines → to_rgb14                     (once, cached as memmap)
      → apply_unit_calibration                       (per frame slice)
      → density LUT + 3x4 matrix + roll offsets + user offsets   → RPD 12-bit
      → AnselEngine.render_scene(roll_scale)         → toned
      → AnselEngine.to_srgb                          → sRGB u8
      → transport unsquash + rot90                   → square pixels
      → user geometry / tone / sharpening            → display or file

Measured on this repo's captures (Apple silicon, 2026-08-07):

    open 694 MB / 57 900 lines .......... ~3.5 s   (one time, cached)
    full-quality single frame ........... ~0.5 - 0.9 s
    quarter-res preview ................. ~30 - 90 ms

so the UI drags on the preview path and commits to full quality on release.
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field, asdict
from io import StringIO
from pathlib import Path

import numpy as np

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_TOOLS / "ansel"))

import pakon_decode as dec      # noqa: E402  (theirs — call, do not modify)
import pakon_color as pc        # noqa: E402
import pakon_filmstock as film  # noqa: E402
import pakon_ansel as ansel     # noqa: E402

# --------------------------------------------------------------------------
# parameter model
# --------------------------------------------------------------------------

# Where user corrections enter, and in what unit.
#
# They are applied to the *toned* RPD, after AnselEngine.render_scene and
# before to_srgb. On the median-balance fallback path, render_scene still
# ends in aim_medians() (NBP=1550), which would cancel upstream offsets.
# On the CN Preference→setShifts→apply path aim_medians is skipped (it
# cancelled Preference OUT — Gold 400), so corrections remain post-render
# for a single consistent hook before to_srgb.
#
# The unit is the vendor's own: codeValuesPerButton from the shipped Shasta
# DPI file (75.0 for this stock; pakon_shasta.py:236 uses it as
# `a = fist(stops * aggr * codeValuesPerButton + 0.5)`). One UI step is one
# button, exactly as PSI's per-frame density/colour keys worked.
#
# Deliberately NOT expressed in D-units, which is what design/frame.html
# labels them: after the Shasta and FUGC tone LUTs the code values are no
# longer linear in density, so a D conversion here would be invented.
#
# With every offset at zero nothing is added at all, so the default render
# stays byte-for-byte the pipeline's own output.
RPD_PER_DENSITY = pc.LUT_SCALE / 8.0       # 437.5 counts per 1.00 D, pre-Ansel

#: render steps — decimation of both axes before the expensive colour stages.
SCALES = {"thumb": 8, "preview": 4, "display": 2, "full": 1}

DEFAULT_PARAMS: dict = {
    # --- colour: the vendor's per-frame control, in vendor button-steps.
    # PSI exposed exactly this shape (density + three colour offsets) and
    # docs/11 §5 keeps them as offsets on top of the roll balance, never a
    # replacement for it. Nothing else touches pixel values.
    "density": 0.0,       # steps, + is brighter (all three channels)
    "red": 0.0,           # steps, + red / - cyan
    "green": 0.0,         # steps, + green / - magenta
    "blue": 0.0,          # steps, + blue / - yellow
    # --- geometry: selects pixels, never alters them
    "rotate": 0,          # 0 / 90 / 180 / 270, clockwise
    "flip_h": False,
    "flip_v": False,
    "crop": None,         # [x, y, w, h] normalised to the rotated frame
    # --- bookkeeping, not image processing
    "rejected": False,
    "ice": False,         # IR dust removal; needs a 4-channel capture
}

#: Controls drawn in design/frame.html that are deliberately NOT implemented,
#: with the reason. The UI shows them disabled carrying this text rather than
#: silently omitting them or, worse, faking them with an invented curve.
UNAVAILABLE_CONTROLS: list[dict] = [
    {
        "key": "contrast",
        "label": "Contrast",
        "reason": "The vendor's contrast lives in the FUGC LUT selector "
                  "(AnselEngine picks fugc_contrast per film path). Exposing "
                  "it means choosing a different shipped LUT, not applying a "
                  "curve of ours — that selection is not ported yet.",
    },
    {
        "key": "saturation",
        "label": "Saturation",
        "reason": "No saturation operator has been traced in TLB.dll. Adding "
                  "one would put invented processing in the image path.",
    },
    {
        "key": "sharpen",
        "label": "Sharpening",
        "reason": "The vendor sharpens inside Ansel, not as a host-side "
                  "unsharp mask. Not ported; a host-side mask would not match.",
    },
]


def merged_params(p: dict | None) -> dict:
    out = dict(DEFAULT_PARAMS)
    if p:
        for k, v in p.items():
            if k in out:
                out[k] = v
    return out


def is_adjusted(p: dict | None) -> bool:
    """True when the frame carries creative work worth warning about."""
    if not p:
        return False
    m = merged_params(p)
    for k, v in DEFAULT_PARAMS.items():
        if k == "rejected":
            continue
        if k == "crop":
            if m[k] is not None:
                return True
        elif m[k] != v:
            return True
    return False


def describe_params(p: dict | None) -> str:
    """Short human summary for the export queue's Adjustments column."""
    if not is_adjusted(p):
        return "auto"
    m = merged_params(p)
    bits = []
    if m["density"]:
        bits.append(f"density {m['density']:+.2f}")
    for key, lbl in (("red", "R"), ("green", "G"), ("blue", "B")):
        if m[key]:
            bits.append(f"{lbl} {m[key]:+g}")
    if m["ice"]:
        bits.append("ICE")
    if m["rotate"]:
        bits.append(f"{m['rotate']}°")
    if m["flip_h"]:
        bits.append("flip H")
    if m["flip_v"]:
        bits.append("flip V")
    if m["crop"]:
        bits.append("cropped")
    return " · ".join(bits) or "auto"


# --------------------------------------------------------------------------
# cached vendor kernel pieces
# --------------------------------------------------------------------------

_kernel_lock = threading.Lock()
_kernel_cache: dict = {}
_engine_cache: dict = {}


def _quiet(fn, *a, **kw):
    """Run a chatty vendor-port function without polluting the job log."""
    sink = StringIO()
    with redirect_stdout(sink):
        return fn(*a, **kw)


def load_kernel(data_dir: str):
    """(lut, coeff, matrix3x3, template_offset) from the shipped vendor files."""
    with _kernel_lock:
        hit = _kernel_cache.get(data_dir)
        if hit is not None:
            return hit
    lut = np.asarray(_quiet(dec.load_true_lut, data_dir), dtype=np.float64)
    mat_path = os.path.join(data_dir, "_ClientColNegMat.txt")
    matrix = pc.load_vendor_matrix(mat_path)
    coeff, template_offset = pc.quantise_matrix(matrix)
    coeff = np.asarray(coeff, dtype=np.float64)
    m33 = np.asarray([[matrix[i][c] for c in range(3)] for i in range(3)],
                     dtype=np.float64)
    val = (lut, coeff, m33, np.asarray(template_offset, dtype=np.float64))
    with _kernel_lock:
        _kernel_cache[data_dir] = val
    return val


def load_engine(ansel_root: str, scene_key: str, scene,
                sba_key: str | None = None) -> "ansel.AnselEngine":
    key = (ansel_root, scene_key)
    with _kernel_lock:
        hit = _engine_cache.get(key)
        if hit is not None:
            return hit
    try:
        eng = _quiet(ansel.AnselEngine.load, ansel_root, scene=scene,
                     sba_key_override=sba_key)
    except TypeError:
        # older signature without sba_key_override
        eng = _quiet(ansel.AnselEngine.load, ansel_root, scene=scene)
    with _kernel_lock:
        _engine_cache[key] = eng
    return eng


def _p99_linear(hist: np.ndarray, total: int) -> float:
    """numpy's ``percentile(x, 99, method='linear')`` from an exact histogram.

    Inputs are 14-bit integers, so a 16384-bin histogram loses nothing. This
    lets the roll Dmin be taken over the *whole* strip — matching what
    ``pakon_decode.cmd_strip`` does when it calls ``render_rpd`` once on the
    full array — without ever holding the full array in memory.
    """
    if total <= 0:
        return 0.0
    virt = 0.99 * (total - 1)
    lo_i, hi_i = int(np.floor(virt)), int(np.ceil(virt))
    cum = np.cumsum(hist)
    v_lo = float(np.searchsorted(cum, lo_i + 1))
    v_hi = float(np.searchsorted(cum, hi_i + 1))
    return v_lo + (virt - lo_i) * (v_hi - v_lo)


def roll_offsets_from_hist(hist: np.ndarray, total: int,
                           data_dir: str) -> np.ndarray:
    """The Auto column: offset = -(M3x3 . Dmin)/8 so clear film base -> RPD 0.

    Same expression as ``pakon_decode.render_rpd(offsets="dmin")``; taken once
    per roll and then held fixed while a single frame's offsets move.
    """
    lut, _coeff, m33, _tmpl = load_kernel(data_dir)
    dmin = np.array(
        [float(lut[int(_p99_linear(hist[c], total)) & 0x3FFF]) for c in range(3)],
        dtype=np.float64)
    return -(m33 @ dmin) / 8.0


def _rpd16(rgb14: np.ndarray, data_dir: str, offset: np.ndarray) -> np.ndarray:
    """14-bit -> 16-bit-scaled 12-bit RPD, with an explicit offset column.

    Identical expression, order, rounding and clamp to
    ``pakon_decode.render_rpd``; only the offset column is an argument instead
    of being recomputed. LUT, matrix and quantisation come from pakon_color.
    """
    lut, coeff, _m33, _t = load_kernel(data_dir)
    idx = rgb14.astype(np.int32) & 0x3FFF
    d = lut[idx].astype(np.float64)
    acc = np.einsum("...c,ic->...i", d, coeff) / (pc.COEFF_FIXED * 8.0)
    rpd = np.clip(np.rint(acc + np.asarray(offset, dtype=np.float64)),
                  0, pc.RPD_MAX)
    return (rpd * (65535.0 / pc.RPD_MAX)).astype(np.uint16)


# --------------------------------------------------------------------------
# the roll
# --------------------------------------------------------------------------

@dataclass
class Frame:
    index: int
    a: int
    b: int
    confidence: str = "good"        # good | low
    params: dict = field(default_factory=dict)
    exported: str | None = None


@dataclass
class Roll:
    id: str
    name: str
    capture: str                    # absolute path to the .bin (never copied)
    workspace: str                  # this roll's cache dir
    lines: int = 0
    frames: list = field(default_factory=list)
    stock: dict | None = None
    # Film selection. pakon_decode refuses --icc without one of these:
    # "Captures do not carry DX; do not silently assume CN-default." A .bin
    # has no DX in it, so the UI has to ask, and the answer is stored here.
    dx: str | None = None
    film_path: str | None = None      # ColNeg | BnW | POSITIVE | IMPORTED
    sba_key: str | None = None
    sba_default: bool = False
    sync: dict = field(default_factory=dict)
    auto_offsets: list = field(default_factory=list)
    roll_scale: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    created: float = 0.0
    data_dir: str = dec.DEFAULT_DATA_DIR
    ansel_root: str = dec.DEFAULT_ANSEL_ROOT
    transport_scale: float = dec.DEFAULT_TRANSPORT_SCALE

    # runtime only
    _rgb: object = field(default=None, repr=False, compare=False)
    _dark: object = field(default=None, repr=False, compare=False)
    _gain: object = field(default=None, repr=False, compare=False)
    _lock: object = field(default_factory=threading.Lock, repr=False,
                          compare=False)

    # -------------------------------------------------------------- storage
    @property
    def cache_path(self) -> Path:
        return Path(self.workspace) / "rgb14.npy"

    #: serialised fields, listed rather than derived — ``asdict`` would try to
    #: deep-copy the memmap and the lock.
    JSON_FIELDS = ("id", "name", "capture", "workspace", "lines", "stock",
                   "dx", "film_path", "sba_key", "sba_default", "sync",
                   "auto_offsets", "roll_scale", "trace", "created",
                   "data_dir", "ansel_root", "transport_scale")

    def to_json(self) -> dict:
        d = {k: getattr(self, k) for k in self.JSON_FIELDS}
        d["frames"] = [asdict(f) for f in self.frames]
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Roll":
        frames = [Frame(**f) for f in d.pop("frames", [])]
        d.pop("_rgb", None)
        known = {f for f in cls.__dataclass_fields__ if not f.startswith("_")}
        r = cls(**{k: v for k, v in d.items() if k in known})
        r.frames = frames
        return r

    # -------------------------------------------------------------- pixels
    def attach(self) -> np.ndarray:
        """Memory-map the cached 14-bit strip (never loads it all at once)."""
        with self._lock:
            if self._rgb is None:
                self._rgb = np.load(self.cache_path, mmap_mode="r")
            if self._dark is None:
                self._dark, self._gain, _ = dec.load_unit_calibration()
        return self._rgb

    def slice14(self, a: int, b: int, step: int = 1) -> np.ndarray:
        """Calibrated 14-bit block for a line range, decimated by `step`."""
        rgb = self.attach()
        a = max(0, min(a, self.lines))
        b = max(a + 1, min(b, self.lines))
        raw = np.asarray(rgb[a:b:step, ::step])
        return dec.apply_unit_calibration(
            raw, self._dark[::step], self._gain[::step])

    def has_film(self) -> bool:
        return bool(self.dx or self.film_path or self.sba_key
                    or self.sba_default)

    def engine(self):
        """Mirrors pakon_decode.cmd_strip's scene construction exactly."""
        if not self.has_film():
            raise ValueError(
                "no film selected. A capture carries no DX, so colour needs "
                "an explicit choice (dx, film_path, sba_key or sba_default) — "
                "pakon_decode refuses to assume CN-default and so does this.")
        sba_key = self.sba_key
        if self.stock:
            scene = ansel.scene_from_filmstock(
                path=self.stock.get("path"),
                dx_part1=self.stock.get("dx_part1"),
                dx_part2=self.stock.get("dx_part2"),
                iso=self.stock.get("iso"),
            )
        elif self.film_path:
            scene = ansel.scene_from_filmstock(path=self.film_path)
        else:
            scene = ansel.SceneContext()
        if self.sba_default and not sba_key and not self.stock \
                and not self.film_path:
            sba_key = "ansel-sba-CN-default"
        key = f"{self.dx}|{self.film_path}|{sba_key}|{self.sba_default}"
        return load_engine(self.ansel_root, key, scene, sba_key)


# --------------------------------------------------------------------------
# opening a capture
# --------------------------------------------------------------------------

def probe_capture(path: str | Path) -> dict:
    """Cheap facts about a .bin without decoding it."""
    p = Path(path)
    size = p.stat().st_size
    return {
        "path": str(p),
        "name": p.name,
        "bytes": size,
        "mtime": p.stat().st_mtime,
        # 6000 words/line x 2 bytes
        "approx_lines": size // (dec.WORDS_PER_LINE * 2),
    }


def open_capture(path: str | Path, workspace: str | Path, roll_id: str,
                 name: str | None = None, dx: str | None = None,
                 progress=lambda *a: None,
                 data_dir: str | None = None,
                 ansel_root: str | None = None,
                 max_lines: int = 0,
                 film_path: str | None = None,
                 sba_key: str | None = None,
                 sba_default: bool = False) -> Roll:
    """Decode a capture into the workspace cache and detect its frames.

    Writes exactly one file — ``rgb14.npy`` in the roll's workspace dir — which
    is render cache, deleted with the workspace. The user's photographs are not
    written anywhere by this function.
    """
    src = Path(path).resolve()
    ws = Path(workspace) / roll_id
    ws.mkdir(parents=True, exist_ok=True)

    roll = Roll(
        id=roll_id,
        name=name or src.stem,
        capture=str(src),
        workspace=str(ws),
        dx=dx,
        film_path=film_path,
        sba_key=sba_key,
        sba_default=sba_default,
        created=time.time(),
        data_dir=data_dir or dec.DEFAULT_DATA_DIR,
        ansel_root=ansel_root or dec.DEFAULT_ANSEL_ROOT,
    )

    progress("reading", 0.02, f"reading {src.name}")
    words = dec.load_u16(src)
    markers = int((words & 1).sum())

    progress("segmenting", 0.12, "finding line sync markers")
    lines = _quiet(dec.segment_lines, words)
    n_all = int(lines.shape[0])          # before any truncation
    if max_lines:
        lines = lines[:max_lines]
    n = int(lines.shape[0])
    roll.lines = n
    # docs/45: a clean capture has one marker per line and no short gaps. The
    # last marker never has a full line behind it, hence markers - 1.
    usable = max(1, markers - 1)
    roll.sync = {
        "markers": markers,
        "lines": n_all,
        "losses": max(0, usable - n_all),
        "pct_clean": round(100.0 * n_all / usable, 3),
        "bytes": int(src.stat().st_size),
        "truncated": bool(max_lines and n < n_all),
    }

    progress("unpacking", 0.30, f"{n} lines x {dec.PIXELS_PER_LINE} px")
    rgb = dec.to_rgb14(lines)
    del words, lines

    progress("caching", 0.45, "writing render cache")
    np.save(roll.cache_path, rgb)
    del rgb
    strip = roll.attach()

    # --- pass A: exact 14-bit histogram + the green plane, in chunks ---
    # Both are taken at FULL resolution because pakon_decode.cmd_strip takes
    # them at full resolution; decimating here would move frame boundaries and
    # the Dmin offsets, and the render would no longer match the pipeline.
    progress("analysing", 0.55, "roll Dmin and frame boundaries")
    hist = np.zeros((3, 1 << 14), dtype=np.int64)
    green = np.empty((n, dec.PIXELS_PER_LINE), dtype=np.uint16)
    CH = 4096
    for a0 in range(0, n, CH):
        b0 = min(n, a0 + CH)
        blk = dec.apply_unit_calibration(
            np.asarray(strip[a0:b0]), roll._dark, roll._gain)
        for c in range(3):
            hist[c] += np.bincount(blk[:, :, c].ravel(), minlength=1 << 14)
        green[a0:b0] = blk[:, :, 1]
        progress("analysing", 0.55 + 0.12 * (b0 / n), f"line {b0} of {n}")
    del blk

    roll.auto_offsets = [float(v) for v in roll_offsets_from_hist(
        hist, n * dec.PIXELS_PER_LINE, roll.data_dir)]

    progress("frames", 0.70, "detecting frame boundaries")
    # find_frames_rpd only reads channel 1, so a broadcast view costs nothing
    spans = dec.find_frames(
        np.broadcast_to(green[:, :, None], (n, dec.PIXELS_PER_LINE, 3)))
    del green
    roll.frames = [Frame(index=i, a=int(a), b=int(b))
                   for i, (a, b) in enumerate(spans)]
    _flag_confidence(roll)

    if dx:
        try:
            p1, p2 = film.parse_dx(dx)
            s = film.lookup(p1, p2)
            roll.stock = {
                "name": s.name, "manufacturer": s.manufacturer,
                "path": s.path, "iso": s.iso,
                "dx_part1": s.dx_part1, "dx_part2": s.dx_part2,
                "sba_override": s.sba_override,
            }
        except Exception:                                   # noqa: BLE001
            roll.stock = None

    # --- pass B: the Ansel roll pass, at full resolution, one frame at a time
    progress("balance", 0.78, "roll scene balance (Ansel pass 1)")
    eng = roll.engine()
    off = np.asarray(roll.auto_offsets, dtype=np.float64)
    acc = np.zeros(3, dtype=np.float64)
    trace: list[float] = []
    nf = max(1, len(roll.frames))
    for i, f in enumerate(roll.frames):
        seg = roll.slice14(f.a, f.b, 1)
        rpd12 = ansel.rpd16_to_rpd12(_rpd16(seg, roll.data_dir, off))
        # analyze_roll_scales averages over the scenes it is given, so calling
        # it per scene and averaging here is the same number it would return
        # for the whole list — but bounded to one frame of memory.
        acc += eng.analyze_roll_scales([rpd12])
        g = float(seg[:, :, 1].mean())
        trace.append(round(-pc.LUT_SCALE * math.log10(max(g, 1.0) / 16383.0)
                           / 1000.0, 4))
        del seg, rpd12
        progress("balance", 0.78 + 0.20 * ((i + 1) / nf),
                 f"scene {i + 1} of {nf}")
    roll.roll_scale = [float(v) for v in (acc / nf)]
    roll.trace = trace

    progress("done", 1.0, f"{len(roll.frames)} frames")
    return roll


def _flag_confidence(roll: Roll) -> None:
    """Mark boundaries that look wrong so Review can annotate them (amber,
    never modal — design/index.html 'warnings that don't abort')."""
    if not roll.frames:
        return
    widths = np.array([f.b - f.a for f in roll.frames], dtype=np.float64)
    med = float(np.median(widths))
    for f in roll.frames:
        w = f.b - f.a
        f.confidence = "low" if (med > 0 and abs(w - med) / med > 0.22) else "good"


# --------------------------------------------------------------------------
# rendering one frame
# --------------------------------------------------------------------------

def _apply_geometry(img: np.ndarray, p: dict) -> np.ndarray:
    rot = int(p.get("rotate") or 0) % 360
    if rot == 90:
        img = np.rot90(img, k=3)
    elif rot == 180:
        img = np.rot90(img, k=2)
    elif rot == 270:
        img = np.rot90(img, k=1)
    if p.get("flip_h"):
        img = img[:, ::-1]
    if p.get("flip_v"):
        img = img[::-1]
    crop = p.get("crop")
    if crop:
        h, w = img.shape[:2]
        x0 = int(round(max(0.0, min(1.0, crop[0])) * w))
        y0 = int(round(max(0.0, min(1.0, crop[1])) * h))
        x1 = int(round(max(0.0, min(1.0, crop[0] + crop[2])) * w))
        y1 = int(round(max(0.0, min(1.0, crop[1] + crop[3])) * h))
        if x1 - x0 >= 8 and y1 - y0 >= 8:
            img = img[y0:y1, x0:x1]
    return np.ascontiguousarray(img)


def correction_steps(p: dict) -> np.ndarray:
    """This frame's user correction, in vendor button-steps, per channel."""
    d = float(p.get("density") or 0.0)
    return np.array([float(p.get("red") or 0.0) + d,
                     float(p.get("green") or 0.0) + d,
                     float(p.get("blue") or 0.0) + d], dtype=np.float64)


def apply_correction(toned: np.ndarray, p: dict, eng) -> np.ndarray:
    """User steps on the toned RPD — after the auto chain, before the ICC hop.

    Returns ``toned`` untouched when every step is zero, which is what keeps
    the default render byte-identical to the pipeline.
    """
    steps = correction_steps(p)
    if not steps.any():
        return toned
    cv = float(getattr(eng.shasta, "code_values_per_button", 75.0))
    return np.clip(toned + (steps * cv).reshape(1, 1, 3), 0, ansel.SHASTA_MAX)


def render_frame(roll: Roll, index: int, params: dict | None = None,
                 scale: str = "preview",
                 max_edge: int | None = None) -> np.ndarray:
    """(capture + parameters) -> one sRGB image. No files, no intermediates.

    With default parameters and ``scale="full"`` this is byte-for-byte the
    pipeline's own output — see ``pakon_render.py verify``.
    """
    if index < 0 or index >= len(roll.frames):
        raise IndexError(f"frame {index} of {len(roll.frames)}")
    f = roll.frames[index]
    p = merged_params(params if params is not None else f.params)
    step = SCALES.get(scale, 4)

    seg = roll.slice14(f.a, f.b, step)
    rpd16 = _rpd16(seg, roll.data_dir,
                   np.asarray(roll.auto_offsets, dtype=np.float64))
    rpd12 = ansel.rpd16_to_rpd12(rpd16)

    eng = roll.engine()
    scale_v = (np.asarray(roll.roll_scale, dtype=np.float64)
               if roll.roll_scale else None)
    toned = _quiet(eng.render_scene, rpd12, scale_v)
    toned = apply_correction(toned, p, eng)
    srgb = _quiet(eng.to_srgb, toned)

    img = dec.to_frame_image(srgb, roll.transport_scale)
    img = _apply_geometry(img, p)

    if max_edge:
        h, w = img.shape[:2]
        if max(h, w) > max_edge:
            from PIL import Image
            r = max_edge / float(max(h, w))
            img = np.asarray(
                Image.fromarray(img, "RGB").resize(
                    (max(1, int(w * r)), max(1, int(h * r))),
                    Image.Resampling.LANCZOS),
                dtype=np.uint8)
    return img


def frame_histogram(roll: Roll, index: int, params: dict | None = None) -> dict:
    """RGB histogram of the 14-bit source plus the facts frame.html shows."""
    f = roll.frames[index]
    seg = roll.slice14(f.a, f.b, 4)
    hist = {}
    for c, name in enumerate("rgb"):
        h, _ = np.histogram(seg[:, :, c], bins=64, range=(0, dec.RAW14_MAX))
        hist[name] = [int(v) for v in h]
    dmin = [float(np.percentile(seg[:, :, c], 99.0)) for c in range(3)]
    clipped = float((seg >= dec.RAW14_MAX - 1).mean() * 100.0)
    return {
        "hist": hist,
        "dmin": [round(v, 1) for v in dmin],
        "clipped_pct": round(clipped, 3),
        "lines": [f.a, f.b],
    }


# --------------------------------------------------------------------------
# encoding / export — the only writes the user keeps
# --------------------------------------------------------------------------

def encode(img: np.ndarray, fmt: str = "JPEG", quality: int = 88) -> bytes:
    from io import BytesIO
    from PIL import Image
    bio = BytesIO()
    Image.fromarray(img, "RGB").save(bio, fmt, quality=quality)
    return bio.getvalue()


def render_name(template: str, roll: Roll, index: int, ext: str) -> str:
    f = roll.frames[index]
    stock = (roll.stock or {}).get("name", "")
    slug = "".join(ch for ch in stock.lower().replace(" ", "")
                   if ch.isalnum()) or "film"
    fields = {
        "roll": roll.name.replace(" ", ""),
        "frame": index + 1,
        "stock": slug,
        "date": time.strftime("%Y-%m-%d", time.localtime(roll.created or time.time())),
        "iso": (roll.stock or {}).get("iso") or "",
        "count": len(roll.frames),
        "lines": f.b - f.a,
    }
    try:
        name = template.format(**fields)
    except (KeyError, ValueError, IndexError):
        name = f"{fields['roll']}_{index + 1:02d}"
    name = "".join(c for c in name if c not in '/\\:*?"<>|').strip() or "frame"
    return f"{name}.{ext}"


#: Which (format, colour) pairs can honestly carry more than 8 bits.
#:
#: The sRGB path ends in ``AnselEngine.to_srgb``, which calls
#: ``rpd12_to_icc_u8`` and runs the ICC transform on 8-bit RGB. Its output
#: therefore *is* 8-bit. Writing it into a 16-bit container by replicating
#: bytes would advertise depth that does not exist, so 16-bit is offered only
#: on the Linear/RPD path, which is genuinely 16-bit all the way.
def depth_options(colour: str) -> list[int]:
    return [16, 8] if colour == "linear" else [8]


def export_frame(roll: Roll, index: int, dest: Path, fmt: str = "tiff",
                 depth: int = 16, colour: str = "linear",
                 template: str = "{roll}_{frame:02}_{stock}") -> dict:
    """Render at full quality and write one file — the only act that keeps a
    file (design/index.html: 'Export is the only moment files are written').

    The bytes written are the pipeline's output with nothing added. The only
    user operations that reach them are the matrix offset column (density and
    colour balance, which is the vendor's own per-frame control) and geometry,
    which selects pixels without altering their values.
    """
    f = roll.frames[index]
    p = merged_params(f.params)
    ext = {"tiff": "tif", "jpeg": "jpg", "png": "png"}.get(fmt, "tif")
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / render_name(template, roll, index, ext)

    if colour == "linear":
        # The vendor's "Save As Raw": 16-bit RPD, no Ansel, no ICC hop.
        # Per-frame steps are NOT baked in — they are a correction to the
        # rendered result, and this file is deliberately the data before that.
        # A "one step" equivalent in the RPD domain would be a made-up
        # conversion across the Shasta/FUGC LUTs, so it is not attempted.
        seg = roll.slice14(f.a, f.b, 1)
        rpd16 = _rpd16(seg, roll.data_dir,
                       np.asarray(roll.auto_offsets, dtype=np.float64))
        img16 = _apply_geometry(
            dec.to_frame_image(rpd16, roll.transport_scale), p)
        out = out.with_suffix(".tif")
        h, w = img16.shape[:2]
        pc.write_tiff(str(out), w, h,
                      np.ascontiguousarray(img16).astype("<u2").tobytes())
    else:
        img = render_frame(roll, index, p, scale="full")   # 8-bit by nature
        from PIL import Image
        im = Image.fromarray(img, "RGB")
        if fmt == "jpeg":
            im.save(out, "JPEG", quality=95, subsampling=0)
        elif fmt == "png":
            im.save(out, "PNG")
        else:
            im.save(out, "TIFF", compression="tiff_deflate")

    size = out.stat().st_size if out.is_file() else 0
    f.exported = str(out)
    return {"path": str(out), "bytes": size, "frame": index,
            "depth": 16 if colour == "linear" else 8}


# --------------------------------------------------------------------------
# CLI — lets the engine be exercised without Electron
# --------------------------------------------------------------------------

def _open_cli(a) -> Roll:
    t0 = time.perf_counter()
    roll = open_capture(
        a.capture, a.workspace, "check", dx=a.dx, max_lines=a.max_lines,
        film_path=a.film_path, sba_key=a.sba_key, sba_default=a.sba_default,
        progress=lambda ph, f, m: print(f"  [{f:5.0%}] {ph}: {m}"))
    print(f"open: {time.perf_counter() - t0:.2f} s — {roll.lines} lines, "
          f"{len(roll.frames)} frames")
    print(f"  sync:         {roll.sync}")
    print(f"  auto offsets: {[round(v, 1) for v in roll.auto_offsets]}")
    print(f"  roll scale:   {[round(v, 3) for v in roll.roll_scale]}")
    return roll


def cmd_check(a) -> int:
    """Timing across the render scales — the number the UI is designed around."""
    roll = _open_cli(a)
    for scale in ("thumb", "preview", "display", "full"):
        t = time.perf_counter()
        img = render_frame(roll, a.frame, None, scale=scale)
        print(f"  render {scale:<8} {img.shape[1]:>5}x{img.shape[0]:<5} "
              f"{(time.perf_counter() - t) * 1000:8.1f} ms")
    if a.out:
        Path(a.out).write_bytes(
            encode(render_frame(roll, a.frame, None, scale=a.scale), "PNG"))
        print(f"wrote {a.out}")
    return 0


def cmd_verify(a) -> int:
    """Prove the UI adds nothing: our full-quality frame must equal
    ``pakon_decode.py strip --color --icc --frames`` byte for byte."""
    import subprocess
    import tempfile
    from PIL import Image

    tmp = Path(tempfile.mkdtemp(prefix="pakon-verify-"))
    cmd = [sys.executable, str(_TOOLS / "pakon_decode.py"), "strip",
           str(a.capture), str(tmp), "--color", "--icc", "--frames"]
    if a.max_lines:
        cmd += ["--max-lines", str(a.max_lines)]
    if a.dx:
        cmd += ["--dx", a.dx]
    if a.film_path:
        cmd += ["--film-path", a.film_path]
    if a.sba_key:
        cmd += ["--sba-key", a.sba_key]
    if a.sba_default:
        cmd += ["--sba-default"]
    print("reference: " + " ".join(cmd))
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:], file=sys.stderr)
        return 1
    print(f"  reference decode: {time.perf_counter() - t0:.1f} s")

    roll = _open_cli(a)
    refs = sorted((tmp / "frames").glob("*_srgb.png"))
    print(f"\ncomparing {len(refs)} reference frames against render_frame(full)")
    if len(refs) != len(roll.frames):
        print(f"  FAIL: frame count differs — reference {len(refs)}, "
              f"ours {len(roll.frames)}")
        return 1

    bad = 0
    for i, ref_path in enumerate(refs):
        ref = np.asarray(Image.open(ref_path).convert("RGB"), dtype=np.uint8)
        ours = render_frame(roll, i, None, scale="full")
        if ref.shape != ours.shape:
            print(f"  frame {i:02d}  SHAPE  ref {ref.shape} ours {ours.shape}")
            bad += 1
            continue
        diff = int((ref != ours).sum())
        total = ref.size
        if diff:
            worst = int(np.abs(ref.astype(int) - ours.astype(int)).max())
            print(f"  frame {i:02d}  {diff:>10} / {total} samples differ "
                  f"({100.0 * diff / total:.4f} %), max delta {worst}")
            bad += 1
        else:
            print(f"  frame {i:02d}  identical  {ours.shape[1]}x{ours.shape[0]}")

    print()
    if bad:
        print(f"RESULT: {bad} of {len(refs)} frames differ from the pipeline.")
        return 1
    print(f"RESULT: all {len(refs)} frames byte-for-byte identical to "
          f"pakon_decode.py. The UI adds nothing to the image path.")
    print("NOTE:   this verifies UI == pipeline. It does NOT verify "
          "pipeline == Kodak; the Ansel stage is still a stand-in "
          "(SETSHIFTS_12_PORTED=False).")
    return 0


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("capture")
        p.add_argument("--workspace", default="/tmp/pakon-render-check")
        p.add_argument("--max-lines", type=int, default=0)
        # same explicit film contract as pakon_decode.py
        p.add_argument("--dx", default=None)
        p.add_argument("--film-path", default=None,
                       choices=("ColNeg", "BnW", "POSITIVE", "IMPORTED"))
        p.add_argument("--sba-key", default=None)
        p.add_argument("--sba-default", action="store_true")

    c = sub.add_parser("check", help="open + render timing at every scale")
    common(c)
    c.add_argument("--frame", type=int, default=0)
    c.add_argument("--scale", default="preview", choices=list(SCALES))
    c.add_argument("--out", default=None, help="write a PNG here (test only)")
    c.set_defaults(fn=cmd_check)

    v = sub.add_parser("verify", help="byte-compare against pakon_decode.py")
    common(v)
    v.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(_cli())
