"""Per-frame SBA colour-balance: analysis image -> orderFpo triple, OFFLINE.

WHAT THIS IS
------------
The vendor computes the SBA balance ``orderFpo`` triple ``(Y, U, V)`` per
frame from a 245x367x3 analysis image; this port has that whole chain ported
and proven bit-exact 6/6 against the real DLL, NO DLL executed
(``/tmp/pakon_re/wire3/offline_final.py``):

    analysis_img(245x367x3)
      -> build_grid_from_source        (createAlgData, MEASURE_PREP_SAMPLER_PORTED)
      -> build_measure_inputs(fpo)     (image / offsets / arg0)
      -> l_input_vector + VM L-term    (pakon_sba_measure + pakon_vm, L)
      -> compute_uv                    (pakon_orderfpo_uv_golden, U/V)
      -> (Y=const0+L, U=const1+U, V=const2+V)

The frame-invariant SBA config (``en``, ``par``, ``obj`` template, ``arg2``,
``arg6``, ``arg7`` and the 720..732 VM tail) is BAKED from the reference live
capture (roll opening 879/1250/1386, CN 35mm), every piece proven
frame-invariant, and ``Ythr`` (the only genuinely per-frame ``arg11`` scalar)
is DERIVED as ``mean(band3 - Yo)`` -- reproduces the captured triple exactly
6/6 despite a +/-1 rounding difference (compute_uv is that insensitive).

THE APPROXIMATION (documented, by design)
-----------------------------------------
The ONE piece that is NOT bit-exact is the frame -> 245x367x3 analysis image
resample: the vendor's ``resampleAnalysisImage`` (fcn.100d8030) target dims +
filter kernel and the ``area_image_apply_lut`` density transfer are unported
(FLESH_ANALYSIS_IMAGE_PORTED=False). :func:`analysis_image_from_frame` builds a
plausible stand-in -- an area/box downsample of a roll-anchored log density in
the analysis-density domain (opening = ``eng.sba.fpo``). So the triple is
"visually per-frame-correct", NOT bit-exact. Tier: empirical/approximate.

Nothing here executes unless a caller invokes it; the module is inert on import.
"""
from __future__ import annotations
import base64
import os
import pickle
import struct
import zlib
from pathlib import Path

import numpy as np

import pakon_sba_measure as _M
import pakon_vm as _V
import pakon_fos as _F
from pakon_orderfpo_uv_golden import compute_uv as _compute_uv

PER_FRAME_BALANCE_PORTED = False   # the RESAMPLE is approximate (see module doc)

# --- baked frame-invariant SBA config -------------------------------------
# Embedded (zlib+base64) so the module is self-contained; a scratch .pkl at
# the path below overrides it if present. Provenance: reference live capture,
# every field proven frame-invariant in /tmp/pakon_re/wire3.
_BAKED_PKL = Path("/tmp/pakon_re/wire3/baked_config.pkl")
_BAKED_B64 = (
    "eNrtWwtsI9UVfWM7ju04jp04Tpw49sROHDuO//l583E+zs+Ok2w2/2ySdWJn4yU/OQm/aquW0oqKVOUToK0oQkhV0UoIKmglKBILFCGk0oVuC3TLtgullEoUbREsaGE9vW88TmzH3t0kpUiVr3X9xvPunHfm3vvum8xMvsW5b96BaDm5pdtkBZa32lucPCwEiFQhlTp7kBihbrAgaLtS5psPu3nICZulej4IbetVgO3WJnvVF9pq/xaXNUFgnUBG5CYEoEp0O/txdD+qp6ZYH7EuIxv6hPiEeJC6H7GREr2dQbKf4PjBxo9CKCrR3zv7OREmvEL4KqOJRXYcY6M4ASIrsye22hCJkJ44z3qJ/RFxkf0QChOvU/3E+1QOga5LbqAo6knQ+2H7j9A+D3oWtt+5QlFFYYo6CfrmlxTVBfsfAz0FuJ+BSoDP66A/Bdvn4ffJzDBV/kWYuvULAk0vUtQ9eor61yusuLFWntZdF6fnYJzotrhiR88Dj+j2xbcoKqpfsnZ+x+J0vhH/e69ijtmO5fHAleQ83iCS8xhUogPJLSn80ZeCB45LMh7fO3Uwf2hS+OPNFHH5QQoe87KD+eNUCn84U/jjcor8OPer5P7wfsZNOfYUlfyY92LGjosREc8lquc2DhaLe1LwKAkn59GfgsfyIwfj8UAKHt9MwePOFDyqf34wHtoUPN5JEZdTKXgQ3QfjEZXTTPsYwys67i8Yv9xLRdrouBNMjp6j4vP0zCOR9q9P74+XHrQJMJ9K4HEv8MD19NsJPBBT1/+ewON9NUJLkxRV+dz+eNiZ9qUEHicZf3Ql8Agw/sDrSyyP+wyR9s5X98ejgVkX/5LAw8qM/3gCDwlTw2YSeFgEEaDwu3vjgevHfaB+2H4I2hdAn0my3q6mWG9nmPX23IthqtlCUY0vQD1toyjWHRR16Xj8on9hvfi6OGWkqKfvXUpeT/285PX04eJwUl98unTrnuOUbM4m8ohV9F+UB8LJ/bFXHr8m987rIwjhQzjXINZh2DZAXjQDn++D/gGUC7FSgdaDngD9Dr5mA5tfQvsPJo42+soSIXxN9w5oFeB0gN4FSgKuMBw5Lo/Z54B9q7AP28igfSScnPdphsPHDI8iUBMopB+Fjx9hOEEqUg/ivAb9HeiHoFI4Hl/93ZbivN0E+krlbJL14W6GazL7eurasfsudf3x/YpP7+ACBImkEuml/w5JaRM1Sm2wFxt0QBsUtUFXxSF2RWbn+DibbdPUNkScTYJxzPaufIgBIRJsYsbf+U4YK5YjEWMUb5Oc0S6cXd7ZYUZcQ+IoXNsGpcJM4cGYrhic3SnFdMfZ0Km7Kz2IXTgJPIiEuF9FwmEofmHc0DLDKxEq/5dT92dpSUta0pKWtKQlLWlJS1rSkpa0pOX/XrY2Ob7QcdtWG2J9/Tcj0vL1SiQZaiEZOAgd9HUXbFsfZ5stFiMhtkUIm/IlconEuaQQK5LYGsUXgQRty6OfpRSKxVfD5cTgYs7OBQS4O1LK3DjUoYvQfpVv4Fz629vXfAOHPi0i8kTjrpZzvIMELRPVIg/BY3c3vM69+d9neLglEBe18M/y2DA+hBLOgYvwUxQV6BM//D2MRyERHNlCZLNX5/3G9j6j1WYx+gPzvo3FdZN/NYiqTRba8xTIq7/F8qEzE7+QwqgbtBUUvyZlZfQnP8byT2cjflGDlkvO7dugGTDijcBzdW7FHzAGQsGlpZmFkM1imbGZaoAfCy0j/EgkCyyXwO7ClTO8zzUv8xa0L/NC5E0+3W/O83yziwF/FRlcJ1dD0fMhe1duGoC+UGBtLXhjgIR2I9qH38W48OR52r9Z8JkH3Nf6X+bdAdi4xbgzrctrgcUB3/rCDMK4WWCbg3G7g8dj+zBwtE+I4/f4eRxCGrcYcE+7XuNdEH3Kw+0yEPUvBZdRyEcG5ue9vpvNAQ5z7Bq5FqT75nzL66SukbSYHNE+zPeD99+i+bIBV0gI2TiWOeCdu2nvqFuyoIfPjPd592vb462tbITmAkO3rAYQPZ4gZryYPnq8aB8eV/zin7fPgwW4Y9QZngUwI8WgDopB7nXloUipNDU1NzcfqrXbzVUGXZmGLC4qkEnE2Vn8DPa+HitJSkstTpDG+poaq8lQqdWolYqiQmluTjY/k7Ofx2IZ+bIyeytI86G6arvFqNdrS8kSRaEsTyIS8ricfUDyBfKKmjYQZ6Oj1m4zV+l1mlJSUVSQnysWCnj7oilSVNa5QFqbG+prbGaToUKrUSmL5TKpWCTgcfcBmZFLGh0dnZ2d7S1NcOpWs1FfoVWrSmhvCgVc9t4x+bKCMksXiMvZdMgBmMYqvbasVKmQgzezBbx9BJ2VU1xhb+7p6XG1OhtxhMzGSl25miwpLsiHAPEz9w6ZKVUZalrcbndne2tzo6POboUIVZSVqorl+XngzUwOa6+QQpHGVN/W29vb3dHe0tjgqIFEMujKNWQJDrooi8/dM83MPKWuoaOvr7enqx1OHbxpo2mqIeiQR9mCzIx4mhUwPdjcqywcrOxCdVVtV3+/1wM0W50NkJwwh2hvyguk2JsJNHX6yipOJj9LJE6OyOFlSVUWR+vhw/297i5XG0S9rsZmwUGHABWCN7MTvanTG6qMZotQJMnLB8KJ0yuDny2RlhkbXYODh/t6u3GEgCYkElQPtQqmENDE3ozFPDI0VGUyW2z2GqmssLgkg5cVjyjKlcnVBkfX0NCRgd6e7g6Gptmg12pKlUAzFxekuFMHyKHh4RFbdU1tvUOhJDXl4jwZO5M5a74or6BYpTY3uUZGhgb6IUL0tKyFoOPcVCnkEPQcYXxBYiBHRkZH6x0NjU0ara6yoFgpFBOw0PGycwsUZJnO3Ng1ODo8OOB1d3e2MdMSvAl5hKcQ7U12HOQwhhwdHR0bGxtvdra2GUwWm7pcViTKy5LIislyvdHS0Dk0PjoE3nTH0KzQ0rkpldCYRHLI8fHxiYk2V0dnd039IaOlrEglV5XpTbbaRveRibGRIwN9HsabuHpUwhTCBSmPjtAO5m7IycnJo91uT2+Ts6bepFXrjLa6BmfX8NGJ0aFBSKTObZoGHU2zkDn1bcgdV8ZCHp2amurrP9zR5ay3W2obWlw9I9OT40AT53vEm3QtpiMky8MR2gn6DiR2JSBOYEQMOT09MzM07O13O52uHu/ozNQERIjO98i0xFMomkhxQU8JOY0hjx075psYGvR4B0d900eB5mHwJq7FdH2vingTQ8ae+bUhfbOzs0fHJmePTU2MAU0vE3SYlcZtSPHeIefm/H7f9OTYMHgzCmnfgczbA+SR4ZGx8aHR4cMD/TgrPT0ul7Oh1lZnt1TpyktL5DKol7uq+m7I1nZXZ1ePu9fb3+bq6mnraIWLgmYIektzQx0ExWow6TRKjapIJsnmQZURpIK0wiSvqz/U0NTcApBmW3Wdo9FsqzVaq6xmXaVWW2mttloMWm1pmUZRnF+YK8zNhotolLSea3F1M5kZSIVKXVahrzIrVJoKeYlarpLnS/OgMkgV6jK1AldxUZaQn8XJuOqbqBFIgTAnV1ogV6hK+UKxtACKWh5XyBZE1+hMUa40V5STyb3epYsFZV2YI8FXxQSHubhMFDZnT4sWweGm/15OS1rSkpa0XE0WFiuveYMrJ2Z79Rt/irOP3szBYrWYbQ6zzWJh/idAEHPsjxKOy2WOe4Z6hTpLnWHjz8f0B6+j08SjLPxZYb/LOQGLcieSw+cD9gdsD3r0igd1Z5NsnYCDdKgOXUa3s/HtPgLGe5hBt5xm2pbbkIheC59CWtazLBPyuQKzG8fRDDlntZJLgfVQcI4M2m0CgYZcDQWWghtLpD94PLjuWyTnfEuBkI9c9a0vkBtrgTXS1T7AmKz6QtC5HgitCVztxuheOxkRH74vZZxbWVwJtfpPbKytG6NHRnrWZn34ph5zQw+lNl/CtHzLt5Ar6wuBUITJTUH4gqtJb4QT3tra5Kz7gotbU1s677MsN74pmPDlQZ7Lnsteku19guMh4BcKbLJh1C1vmNrkLK34A1seYpOPN2ZWfXM3bHkQfYOpGjY2TP8BnG8bsA=="
)


def _load_config() -> dict:
    if _BAKED_PKL.is_file():
        try:
            return pickle.loads(_BAKED_PKL.read_bytes())
        except Exception:
            pass
    return pickle.loads(zlib.decompress(base64.b64decode(_BAKED_B64)))


_CFG = _load_config()
_RECS = None


def _records():
    global _RECS
    if _RECS is None:
        _RECS = _V.load_pcode()
    return _RECS


_N_SAMPLES = 864
_BAND_STRIDE = _N_SAMPLES
_ARG0_LEN = 0x3000


def _derive_ythr(image, Yo: int) -> int:
    """arg11@0x48 = mean(band3 - Yo). Matches the captured value +/-1; the U/V
    it feeds is that insensitive (offline triple stays exact 6/6)."""
    s = 0
    for i in range(_N_SAMPLES):
        s += _M._i16(image[3 * _BAND_STRIDE + i] - Yo)
    return int(round(s / _N_SAMPLES))


def grid_bands_to_triple(rgb_bands, fpo) -> tuple[int, int, int]:
    """``(3,24,36)`` (or 3x864) RGB density grid + opening ``fpo`` -> orderFpo.

    The proven-offline half: everything from the grid down is bit-exact against
    the real DLL (6/6). ``fpo`` is ``eng.sba.fpo`` (analysis-density opening).
    """
    opening = tuple(int(round(float(v))) for v in fpo)
    image, offsets, _arg0_unused = _M.build_measure_inputs(rgb_bands, opening)
    const = _F.fos_opening_axes(*opening)

    # --- L term (VM) ---
    mv = _M.l_input_vector(
        image=image, offsets=offsets, sel=_CFG["sel"], arg4=_CFG["arg4"],
        en=_CFG["en"], par=_CFG["par"], obj=_CFG["obj"],
        mode=_CFG["mode"], mode_pack=_CFG["mode_pack"])
    full = list(mv) + list(_CFG["tail"])
    L = _V.l_term(_records(), full)
    Y = const[0] + L

    # --- U/V (compute_uv) with recomputed mask + derived Ythr ---
    objb = bytearray(_CFG["obj"])
    _M.selection_mask(image, offsets, sel=_CFG["sel"], mode=_CFG["mode"],
                      mode_pack=_CFG["mode_pack"], en=_CFG["en"],
                      par=_CFG["par"], obj=objb)
    a11 = bytearray(0x1200)
    struct.pack_into("<i", a11, 0x48, _derive_ythr(image, const[0]))
    a11[0xC20:0xC20 + _N_SAMPLES] = objb[0xC20:0xC20 + _N_SAMPLES]
    arg0 = struct.pack("<%dh" % (6 * _N_SAMPLES),
                       *[_M._i16(v) for v in image]) \
        + bytes(_ARG0_LEN - 6 * _N_SAMPLES * 2)
    u, v = _compute_uv(arg0, _CFG["arg2"], _CFG["arg6"], _CFG["arg7"],
                       bytes(a11), const)
    return (int(Y), int(const[1] + u), int(const[2] + v))


# --------------------------------------------------------------------------
# The APPROXIMATE part: frame -> 245x367x3 analysis image (see module doc).
# --------------------------------------------------------------------------
ANALYSIS_W = 245
ANALYSIS_H = 367

# density-per-decade of the analysis-density domain, fitted to the reference
# capture's grid span (~500 codes over the ~2-decade scene log range); see
# /tmp/pakon_re/wire3 notes. Roll-anchored so per-frame casts survive.
_ANALYSIS_SLOPE = 505.0


def analysis_image_from_frame(linear_rgb: np.ndarray, fpo,
                              ref_linear) -> np.ndarray:
    """Full-res LINEAR frame (H,W,3) -> approx 245x367x3 analysis density.

    Roll-anchored log density ``D = fpo + SLOPE*log10(ref/linear)`` (ref =
    the roll's per-band linear value that maps to the opening), area-averaged
    (box) to 245x367. NOT the vendor's resample/area-LUT -- a documented
    stand-in (module doc). ``ref_linear`` is roll-level so per-frame casts are
    preserved rather than self-normalised away.
    """
    a = np.asarray(linear_rgb, dtype=np.float64)
    if a.ndim != 3 or a.shape[2] != 3:
        raise ValueError("linear_rgb must be (H,W,3)")
    ref = np.asarray(ref_linear, dtype=np.float64).reshape(1, 1, 3)
    op = np.asarray([float(v) for v in fpo], dtype=np.float64).reshape(1, 1, 3)
    dens = op + _ANALYSIS_SLOPE * np.log10(ref / np.clip(a, 1.0, None))
    dens = np.clip(dens, 0.0, 16383.0)
    return _box_resize(dens, ANALYSIS_W, ANALYSIS_H)


def _box_resize(img: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """Area-average (box) resample to (out_h,out_w,3). Integer-block where it
    divides, bilinear-of-integral otherwise; approximate by design."""
    h, w = img.shape[:2]
    # integral-image area average: exact box means for arbitrary target size
    ii = np.zeros((h + 1, w + 1, 3), dtype=np.float64)
    ii[1:, 1:, :] = np.cumsum(np.cumsum(img, axis=0), axis=1)
    ys = np.linspace(0, h, out_h + 1)
    xs = np.linspace(0, w, out_w + 1)
    y0 = np.floor(ys[:-1]).astype(int); y1 = np.clip(np.ceil(ys[1:]).astype(int), 1, h)
    x0 = np.floor(xs[:-1]).astype(int); x1 = np.clip(np.ceil(xs[1:]).astype(int), 1, w)
    out = np.zeros((out_h, out_w, 3), dtype=np.float64)
    for i in range(out_h):
        for j in range(out_w):
            a = ii[y1[i], x1[j]] - ii[y0[i], x1[j]] - ii[y1[i], x0[j]] + ii[y0[i], x0[j]]
            cnt = max(1, (y1[i] - y0[i]) * (x1[j] - x0[j]))
            out[i, j] = a / cnt
    return out


def frame_to_triple(linear_rgb: np.ndarray, fpo, ref_linear) -> tuple[int, int, int]:
    """Convenience: full-res linear frame -> orderFpo triple (approximate)."""
    ana = analysis_image_from_frame(linear_rgb, fpo, ref_linear)
    grid = _M.build_grid_from_source(np.rint(ana).astype(np.int64))
    return grid_bands_to_triple(grid, fpo)
