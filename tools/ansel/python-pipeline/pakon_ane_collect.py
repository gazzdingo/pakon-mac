#!/usr/bin/env python3
"""AneSampledImage / AneResidualImage producers — collectData leaf.

PakonIMAu.dll base ``0x10000000``.

``AnsAneCapabilityImpl::collectData`` @ ``0x101ee590`` (string
``0x1059b55c``) builds portfolio entries named ``AneSampledImage`` /
``AneResidualImage`` (``0x1059b2e8`` / ``0x1059b2d4``). Pixel fill is
dispatched by ``0x10280bd0``:

* ``this+0x7c == 0`` → directional residual ``0x1027fc80`` (this module).
* ``this+0x7c != 0`` → box-average residual ``0x102804e0`` (this module).

Shipped ``ane-*.dpi`` uses ``filterMode=Laplacian`` → null ``+0x7c`` →
fc80. Box ``804e0`` is ported for honesty when ``filterSize`` is 3 or 5
(``this+0x7c`` non-null).

``collectData`` portfolio wrap @ ``0x101ee590`` (PORTED host face)
-----------------------------------------------------------------
Cited Cap fields fed into dispatch (``0x101ee80a…0x101ee839``):

| Cap off   | dpi / role                         | cite              |
|-----------|------------------------------------|-------------------|
| ``+0x7a`` | ``correctForFilter`` (byte)        | ``0x101ee812``    |
| ``+0x7c`` | filterMode object* (0 → Laplacian) | ``0x101ee816``    |
| ``+0x80`` | ``filterSize`` (box path)          | ``0x101ee80a``    |
| ``+0xb0`` | ``colSampling`` → x_step           | ``0x101ee829``    |
| ``+0xb4`` | ``rowSampling`` → y_step           | ``0x101ee823``    |
| ``+0xb8`` | ``minMajorDim`` gate               | ``0x101ee663``    |

Orchestration (host, cited; COM QI insert runtime-only):

1. Walk circular QI image list; keep desc with largest
   ``max(+0x14,+0x18)`` when ``≥ Cap+0xb8`` (``0x101ee650…``).
2. If desc type dword ``!= 2`` → COM convert ``0x100da770`` (not host).
3. Planar RGB ends: ``base``, ``base+2·w·h``, ``base+4·w·h`` then
   ``0x100db490`` (3 channels) — host uses ndarray planes instead.
4. ``0x10280bd0`` fill sampled + residual images.
5. Cap ``0x101ed9b0`` wraps planes into QI payloads (COM).
6. Alloc QI ``0x44`` bytes; name ``AneSampledImage`` /
   ``AneResidualImage``; copy 9 dwords at ``+0x20``; insert via
   ``0x1008b7e0`` (COM). Host returns named plane entries instead.

``0x1027fc80`` (ported leaf — sample + residual int16 planes)
--------------------------------------------------------------
For each output pixel at source center ``C`` (margin 2 in rows/cols),
evaluate four axis predictors of the form::

    pred = 4·(inner₀ + inner₁) − outer₀ − outer₁
    err  = |6·C − pred|

Axes (relative to ``C``):

* H:  (±1,0) inners, (±2,0) outers
* V:  (0,±1) / (0,±2)
* D1: (−1,−1)/(+1,+1) / (−2,−2)/(+2,+2)
* D2: (−1,+1)/(+1,−1) / (−2,+2)/(+2,−2)

Keep the ``pred`` with smallest ``err`` (ties keep earlier axis;
cite ``jge`` / final ``jl`` @ ``0x1028009d…0x10280199``). Then::

    approx    = (pred · 0x555 + 0x1000) >> 13   # ≈ pred/6
    residual  = i16(approx − C)
    sample    = C                                 # when avg flag clear
    sample    = i16(signed_div17(C + Σ₁₆))        # when flag set

``Σ₁₆`` = sum of the 16 axis neighbors (all four axes' inners+outers).
``signed_div17`` = MSVC ``imul 0x78787879; sar 3; +sign`` @
``0x102801cf…``.

Subsample: output grid uses ``x_step`` / ``y_step`` (Cap ``+0xb0`` /
``+0xb4``); source walks start at ``(col0−2, row0−2)`` for the 5-tap
window (cite ``0x1027fe9a…0x1027feb9``).

``0x102804e0`` (ported leaf — box average residual)
---------------------------------------------------
Pixel body @ ``0x10280800…0x102808f1`` (cite DLL):

* ``filterSize == 3`` (@ ``esp+0x4e0``): sum 3×3; MSVC
  ``imul 0x38e38e39; sar edx,1`` + signbit → trunc ``/9``.
* else (5): sum 5×5 (25 taps); ``imul 0x51eb851f; sar edx,3`` +
  signbit → trunc ``/25``.
* ``residual = i16(avg − C)``; ``sample = avg`` if correctForFilter
  flag (@ ``esp+0x4e4``) else ``C``.
* Margin: 1 for size 3, 2 for size 5 (cite ``0x10280578…0x10280587``).

Flags
-----
* ``ANE_COLLECT_FC80_PORTED`` — directional leaf (Unicorn-golden).
* ``ANE_COLLECT_804E0_PORTED`` — box leaf (Unicorn-golden).
* ``ANE_COLLECT_DATA_PORTED`` — collectData host orch (pick / Cap→
  dispatch / named portfolio entries).
* ``ANE_COLLECT_QI_INSERT_PORTED`` — QI entry layout + name ctor vtable
  stamp + 9-dword payload copy + insert-or-replace by name (ATL string /
  red-black insert helpers remain call-through).
* ``ANE_COLLECT_CONVERT_PORTED`` — type≠2 ``0x100da770`` desc stamp
  (``+4=2``) + same-type memcpy size ``2·w·(+0x14)·h``; planar factory
  ``0x100db490`` alloc ``0x24`` / vtbl. Cap wrap ``0x101ed9b0`` still open.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ANE_COLLECT_FC80_PORTED = True
ANE_COLLECT_804E0_PORTED = True
ANE_COLLECT_DATA_PORTED = True
ANE_COLLECT_QI_INSERT_PORTED = True  # layout + replace-by-name host face
ANE_COLLECT_CONVERT_PORTED = True  # 0x100da770 stamp + size; 0x100db490 planar

ANE_COLLECT_DATA = 0x101EE590
ANE_COLLECT_DISPATCH = 0x10280BD0
ANE_COLLECT_COPY_IEM = 0x100DA770  # type≠2 convert
ANE_COLLECT_MAKE_PLANAR = 0x100DB490  # 3-channel planar
ANE_COLLECT_WRAP_QI = 0x101ED9B0  # Cap planes → QI payload (COM)
ANE_COLLECT_QI_NAME_CTOR = 0x1008B3C0  # named QI object init
ANE_COLLECT_QI_INSERT = 0x1008B7E0  # portfolio insert-or-replace
ANE_COLLECT_QI_NAME_COPY = 0x1008B360  # name → local CString @ insert
ANE_COLLECT_QI_MAP_INSERT = 0x1008B700  # map insert helper
ANE_COLLECT_QI_MAP_ERASE = 0x10029FB0  # erase replaced node
ANE_COLLECT_PLANAR_VTBL = 0x1057B10C  # stamped @ 0x100db500
ANE_COLLECT_PLANAR_ALLOC = 0x24  # push $0x24 @ 0x100db4a7
ANE_SAMPLE_RESIDUAL_FC80 = 0x1027FC80
ANE_SAMPLE_RESIDUAL_804E0 = 0x102804E0
ANE_SAMPLE_RESIDUAL_PIXEL = 0x10280030  # fc80 inner pixel body
ANE_SAMPLE_RESIDUAL_PIXEL_END = 0x102801E4  # after optional avg store
ANE_SAMPLE_RESIDUAL_804E0_PIXEL = 0x10280800  # box pixel body
ANE_SAMPLE_RESIDUAL_804E0_PIXEL_END = 0x102808F1  # after sample/resid stores

STR_COLLECT_DATA = 0x1059B55C
STR_ANE_SAMPLED_IMAGE = 0x1059B2E8
STR_ANE_RESIDUAL_IMAGE = 0x1059B2D4
STR_UNABLE_INSERT_SAMPLED = 0x1059B4F8
STR_UNABLE_INSERT_RESIDUAL = 0x1059B528

# Cap Impl field offsets (cite collectData loads @ 0x101ee80a…)
ANE_CAP_CORRECT_FOR_FILTER_OFF = 0x7A  # PakonIMAu.dll @ 0x101ee812
ANE_CAP_FILTER_MODE_PTR_OFF = 0x7C  # PakonIMAu.dll @ 0x101ee816
ANE_CAP_FILTER_SIZE_OFF = 0x80  # PakonIMAu.dll @ 0x101ee80a
ANE_CAP_COL_SAMPLING_OFF = 0xB0  # PakonIMAu.dll @ 0x101ee829
ANE_CAP_ROW_SAMPLING_OFF = 0xB4  # PakonIMAu.dll @ 0x101ee823
ANE_CAP_MIN_MAJOR_DIM_OFF = 0xB8  # PakonIMAu.dll @ 0x101ee663

# Portfolio QI entry layout (cite construct @ 0x101ee9bf…0x101eea0d)
ANE_QI_ENTRY_SIZE = 0x44  # PakonIMAu.dll @ 0x101ee9bf
ANE_QI_PAYLOAD_OFF = 0x20  # PakonIMAu.dll @ 0x101ee9f9
ANE_QI_PAYLOAD_DWORDS = 9  # PakonIMAu.dll @ 0x101ee9fc
ANE_QI_NAME_SAMPLED = "AneSampledImage"  # PakonIMAu.dll @ 0x1059b2e8
ANE_QI_NAME_RESIDUAL = "AneResidualImage"  # PakonIMAu.dll @ 0x1059b2d4
# thiscall name-ctor stamps [esi]=0x1057c008 then CString at +4 @ 0x1008b3cb
ANE_QI_VTBL_NAME = 0x1057C008  # PakonIMAu.dll @ 0x1008b3cb
# After payload copy, collectData overwrites [obj]=0x10583eb0 @ 0x101eea07
ANE_QI_VTBL_IMAGE = 0x10583EB0  # PakonIMAu.dll @ 0x101eea07
# Node that holds image ptr at +0x28 before erase @ 0x1008b859
ANE_QI_NODE_IMAGE_OFF = 0x28  # PakonIMAu.dll @ 0x1008b859

# Image desc type dword at local+4 / node+0xc (cite @ 0x101ee6aa)
ANE_IMAGE_TYPE_SKIP_CONVERT = 2  # PakonIMAu.dll @ 0x101ee6aa / stamp @ 0x100da7a9
ANE_PLANAR_CHANNELS = 3  # PakonIMAu.dll @ 0x101ee7da
ANE_DESC_COPY_DWORDS = 9  # PakonIMAu.dll @ 0x101ee672
ANE_DESC_WIDTH_OFF = 0xC  # PakonIMAu.dll @ 0x100da7b3
ANE_DESC_HEIGHT_OFF = 0x10  # PakonIMAu.dll @ 0x100da7b9
ANE_DESC_PITCH_OFF = 0x14  # PakonIMAu.dll @ 0x100da7bf / imul @ 0x100da88d
ANE_DESC_FLAGS_OFF = 0x1C  # same-type fast path test @ 0x100da886


def _i16(x: int) -> int:
    x = int(x) & 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def _sar32(x: int, n: int) -> int:
    return int(np.int32(x) >> n)


def ane_pred_div6(pred: int) -> int:
    """``(pred * 0x555 + 0x1000) >> 13`` @ ``0x102801a1…`` (signed)."""
    lo = (int(np.int32(pred)) * 0x555) & 0xFFFFFFFF
    if lo >= 0x80000000:
        lo -= 0x100000000
    return _sar32(lo + 0x1000, 13)


def ane_signed_div17(n: int) -> int:
    """MSVC signed ``n/17`` @ ``0x102801cf…0x102801de``."""
    magic = struct.unpack("<i", struct.pack("<I", 0x78787879))[0]
    prod = int(np.int32(n)) * magic
    edx = _sar32(prod >> 32, 3)
    return edx + ((edx >> 31) & 1)


def ane_signed_div9(n: int) -> int:
    """MSVC signed ``n/9`` @ ``0x10280871…0x102808d4`` (``0x38e38e39; sar 1``)."""
    magic = struct.unpack("<i", struct.pack("<I", 0x38E38E39))[0]
    prod = int(np.int32(n)) * magic
    edx = _sar32(prod >> 32, 1)
    return edx + ((edx >> 31) & 1)


def ane_signed_div25(n: int) -> int:
    """MSVC signed ``n/25`` @ ``0x102808bf…0x102808d4`` (``0x51eb851f; sar 3``)."""
    magic = struct.unpack("<i", struct.pack("<I", 0x51EB851F))[0]
    prod = int(np.int32(n)) * magic
    edx = _sar32(prod >> 32, 3)
    return edx + ((edx >> 31) & 1)


def ane_804e0_pixel(
    plane: Sequence[int],
    pitch: int,
    cy: int,
    cx: int,
    *,
    filter_size: int = 5,
    avg_flag: bool = False,
) -> Tuple[int, int]:
    """Box-average sample/residual for one center ``(cy, cx)``.

    Cite pixel body ``0x10280800…0x102808f1``. ``filter_size`` 3 → 3×3 /9;
    else 5×5 /25. Returns ``(sample, residual)`` int16-range ints.
    """
    pitch = int(pitch)
    fs = 3 if int(filter_size) == 3 else 5
    rad = 1 if fs == 3 else 2

    def p(dr: int, dc: int) -> int:
        return int(plane[(cy + dr) * pitch + (cx + dc)])

    c = p(0, 0)
    total = 0
    for dr in range(-rad, rad + 1):
        for dc in range(-rad, rad + 1):
            total += p(dr, dc)
    avg = ane_signed_div9(total) if fs == 3 else ane_signed_div25(total)
    residual = _i16(avg - c)
    sample = _i16(avg) if avg_flag else _i16(c)
    return sample, residual


def ane_fc80_pixel(
    plane: Sequence[int],
    pitch: int,
    cy: int,
    cx: int,
    *,
    avg_flag: bool = False,
) -> Tuple[int, int]:
    """Directional sample/residual for one center ``(cy, cx)``.

    ``plane`` is row-major int16 samples with row stride ``pitch``.
    Requires ``cy,cx`` in ``[2, h-3]`` / ``[2, pitch-3]`` for the window.
    Returns ``(sample, residual)`` as Python ints in int16 range.
    """
    pitch = int(pitch)

    def p(dr: int, dc: int) -> int:
        return int(plane[(cy + dr) * pitch + (cx + dc)])

    c = p(0, 0)
    axes = (
        (p(0, -1), p(0, 1), p(0, -2), p(0, 2)),
        (p(-1, 0), p(1, 0), p(-2, 0), p(2, 0)),
        (p(-1, -1), p(1, 1), p(-2, -2), p(2, 2)),
        (p(-1, 1), p(1, -1), p(-2, 2), p(2, -2)),
    )
    best_pred = 0
    best_err = 0xFFFF
    neigh = 0
    for ia, ib, oa, ob in axes:
        pred = 4 * (ia + ib) - oa - ob
        err = abs(6 * c - pred)
        neigh += ia + ib + oa + ob
        if err < best_err:
            best_err = err
            best_pred = pred
    approx = ane_pred_div6(best_pred)
    residual = _i16(approx - c)
    if avg_flag:
        sample = _i16(ane_signed_div17(c + neigh))
    else:
        sample = _i16(c)
    return sample, residual


# Shipped ``ane-default.dpi`` / ``ane-CN-Fps.dpi`` (cite install tree)
ANE_DPI_COL_SAMPLING = 32  # Cap ``+0xb0`` → fc80 x_step
ANE_DPI_ROW_SAMPLING = 32  # Cap ``+0xb4`` → fc80 y_step
ANE_DPI_CORRECT_FOR_FILTER = True  # Cap ``+0x7a`` avg-flag (dpi = 1)
ANE_DPI_FILTER_MODE_LAPLACIAN = True  # → ``0x1027fc80`` (not box ``804e0``)
ANE_DPI_FILTER_SIZE = 5  # Cap ``+0x80`` / dpi ``filterSize``
ANE_DPI_MIN_MAJOR_DIM = 1500  # Cap ``+0xb8`` / dpi ``minMajorDim``


@dataclass(frozen=True)
class AneCollectCapParams:
    """Cap fields read by ``collectData`` @ ``0x101ee80a…`` / pick gate."""

    correct_for_filter: bool = ANE_DPI_CORRECT_FOR_FILTER  # +0x7a
    filter_mode_ptr: int = 0  # +0x7c; 0 → Laplacian (cite 0x10280bd0)
    filter_size: int = ANE_DPI_FILTER_SIZE  # +0x80
    col_sampling: int = ANE_DPI_COL_SAMPLING  # +0xb0
    row_sampling: int = ANE_DPI_ROW_SAMPLING  # +0xb4
    min_major_dim: int = ANE_DPI_MIN_MAJOR_DIM  # +0xb8


@dataclass(frozen=True)
class AnePortfolioEntry:
    """Named QI portfolio image after ``0x1008b3c0`` + payload + insert.

    DLL: alloc ``0x44``; name-ctor; copy 9 dwords at ``+0x20``; stamp
    image vtable; ``0x1008b7e0`` insert-or-replace by name.
    """

    name: str
    planes: Tuple[np.ndarray, ...]  # length-3 sample or residual
    payload: Tuple[int, ...] = ()  # 9 dwords at +0x20 when set
    vtbl_name: int = ANE_QI_VTBL_NAME
    vtbl_image: int = ANE_QI_VTBL_IMAGE


@dataclass
class AneQiPortfolio:
    """Host face of the named QI map used by ``0x1008b7e0``.

    Insert replaces an existing same-name entry (DLL find → Release
    ``node+0x28`` → erase → re-insert). ATL CString / tree nodes are not
    mirrored; success is always ``True`` when ``entry`` is non-null
    (DLL returns ``al=1`` @ ``0x1008b8d3`` after insert path).
    """

    by_name: Dict[str, AnePortfolioEntry] = field(default_factory=dict)
    replaced: List[str] = field(default_factory=list)


def ane_qi_name_ctor_vtbl() -> int:
    """Initial ``[esi]`` after ``0x1008b3c0`` @ ``0x1008b3cb``."""
    if not ANE_COLLECT_QI_INSERT_PORTED:
        raise NotImplementedError("QI insert not marked ported")
    # PakonIMAu.dll @ 0x1008b3cb — mov dword ptr [esi], 0x1057c008
    return ANE_QI_VTBL_NAME


def ane_qi_image_vtbl_after_payload() -> int:
    """``[obj]`` stamped after ``rep movsd`` @ ``0x101eea07``."""
    if not ANE_COLLECT_QI_INSERT_PORTED:
        raise NotImplementedError("QI insert not marked ported")
    # PakonIMAu.dll @ 0x101eea07 — mov dword ptr [eax], 0x10583eb0
    return ANE_QI_VTBL_IMAGE


def ane_qi_pack_payload(dwords: Sequence[int]) -> bytes:
    """Nine little-endian dwords for QI ``+0x20`` (``rep movsd``)."""
    if not ANE_COLLECT_QI_INSERT_PORTED:
        raise NotImplementedError("QI insert not marked ported")
    vals = list(dwords)[:ANE_QI_PAYLOAD_DWORDS]
    while len(vals) < ANE_QI_PAYLOAD_DWORDS:
        vals.append(0)
    # PakonIMAu.dll @ 0x101ee9fc — mov ecx, 9 / rep movsd
    return struct.pack(f"<{ANE_QI_PAYLOAD_DWORDS}I", *[int(v) & 0xFFFFFFFF for v in vals])


def ane_qi_build_entry(
    name: str,
    planes: Tuple[np.ndarray, ...],
    payload_dwords: Optional[Sequence[int]] = None,
) -> AnePortfolioEntry:
    """Host construct matching collectData Sampled/Residual build."""
    if not ANE_COLLECT_QI_INSERT_PORTED:
        raise NotImplementedError("QI insert not marked ported")
    pl = tuple(int(x) & 0xFFFFFFFF for x in (payload_dwords or (0,) * ANE_QI_PAYLOAD_DWORDS))
    if len(pl) < ANE_QI_PAYLOAD_DWORDS:
        pl = pl + (0,) * (ANE_QI_PAYLOAD_DWORDS - len(pl))
    else:
        pl = pl[:ANE_QI_PAYLOAD_DWORDS]
    return AnePortfolioEntry(
        name=str(name),
        planes=planes,
        payload=pl,
        vtbl_name=ane_qi_name_ctor_vtbl(),
        vtbl_image=ane_qi_image_vtbl_after_payload(),
    )


def ane_qi_insert(portfolio: AneQiPortfolio, entry: Optional[AnePortfolioEntry]) -> bool:
    """``0x1008b7e0`` host face: null → fail; else insert-or-replace by name.

    DLL null path: ``test esi`` after alloc fail skips insert (caller
    tests ``al``). Non-null always reaches ``mov al,1`` @ ``0x1008b8d3``.
    Same-name: ``Release`` on ``[edi+0x28]`` then erase @ ``0x10029fb0``.
    """
    if not ANE_COLLECT_QI_INSERT_PORTED:
        raise NotImplementedError("QI insert not marked ported")
    # PakonIMAu.dll @ 0x101eea34… — push esi; call insert; test al
    if entry is None:
        return False
    name = entry.name
    # @ 0x1008b854 — existing name → Release + erase before re-insert
    if name in portfolio.by_name:
        portfolio.replaced.append(name)
    portfolio.by_name[name] = entry
    # @ 0x1008b8d3 — mov al, 1
    return True


@dataclass(frozen=True)
class AneCollectDataResult:
    """Host ``collectData`` output: Sampled then Residual entries."""

    entries: Tuple[AnePortfolioEntry, ...]
    source_index: Optional[int]
    used_laplacian: bool
    portfolio: Optional[AneQiPortfolio] = None


def ane_collect_image_major_dim(width: int, height: int) -> int:
    """``max(w, h)`` as collectData pick uses @ ``0x101ee65a…0x101ee660``."""
    w = int(width)
    h = int(height)
    # PakonIMAu.dll @ 0x101ee65a — cmp edx, edi / jg keep edx else edi
    return w if w > h else h


def ane_collect_pick_best_source(
    candidates: Sequence[Tuple[int, int]],
    min_major_dim: int,
) -> Optional[int]:
    """Index of best ``(w, h)`` under Cap ``+0xb8`` gate.

    Cite walk ``0x101ee650…0x101ee688``: keep largest
    ``max(+0x14,+0x18)`` when ``≥ Cap+0xb8``; ties keep earlier.
    Returns ``None`` when none qualify (DLL early-out @ ``0x101ee68a``).
    """
    best_i: Optional[int] = None
    best = 0  # PakonIMAu.dll @ 0x101ee647 — xor ecx, ecx
    thresh = int(min_major_dim)
    for i, (w, h) in enumerate(candidates):
        maj = ane_collect_image_major_dim(w, h)
        # PakonIMAu.dll @ 0x101ee663 — cmp edx, [edi+0xb8] / jl skip
        if maj < thresh:
            continue
        # PakonIMAu.dll @ 0x101ee66b — cmp edx, ecx / jle skip
        if maj <= best:
            continue
        best = maj  # PakonIMAu.dll @ 0x101ee67f
        best_i = i
    return best_i


def ane_collect_dispatch_uses_laplacian(filter_mode_ptr: int) -> bool:
    """``0x10280bd0``: null Cap ``+0x7c`` → ``0x1027fc80`` else ``804e0``."""
    # PakonIMAu.dll @ 0x10280bd0 — test [esp+0x18] / jne box
    return int(filter_mode_ptr) == 0


def ane_collect_needs_image_convert(image_type: int) -> bool:
    """True when desc type dword ≠ 2 → COM ``0x100da770``.

    Cite ``cmp dword [ebp-0x58], 2`` @ ``0x101ee6aa``.
    """
    # PakonIMAu.dll @ 0x101ee6aa
    return int(image_type) != ANE_IMAGE_TYPE_SKIP_CONVERT


def ane_collect_convert_stamp_type() -> int:
    """``0x100da770`` writes ``out+4 = 2`` @ ``0x100da7a9``."""
    if not ANE_COLLECT_CONVERT_PORTED:
        raise NotImplementedError("Ane convert not marked ported")
    # PakonIMAu.dll @ 0x100da7a9 — mov dword ptr [edi+4], 2
    return ANE_IMAGE_TYPE_SKIP_CONVERT


def ane_collect_convert_same_type_bytes(width: int, height: int, pitch: int) -> int:
    """Fast-path memcpy size when src type already 2 @ ``0x100da88d…0x100da89b``.

    ``bytes = 2 · width · pitch · height`` (``imul`` chain then ``shl 1``).
    """
    if not ANE_COLLECT_CONVERT_PORTED:
        raise NotImplementedError("Ane convert not marked ported")
    # PakonIMAu.dll @ 0x100da88a…0x100da89b
    return (int(width) * int(pitch) * int(height)) << 1


def ane_collect_convert_same_type_ok(src_type: int, flags_1c: int) -> bool:
    """Same-type memcpy arm: type==2 and ``+0x1c==0`` @ ``0x100da87d…0x100da888``."""
    if not ANE_COLLECT_CONVERT_PORTED:
        raise NotImplementedError("Ane convert not marked ported")
    # PakonIMAu.dll @ 0x100da87d / @ 0x100da886
    return int(src_type) == ANE_IMAGE_TYPE_SKIP_CONVERT and int(flags_1c) == 0


def ane_collect_planar_factory_size() -> int:
    """``0x100db490`` alloc size ``0x24`` @ ``0x100db4a7``."""
    if not ANE_COLLECT_CONVERT_PORTED:
        raise NotImplementedError("Ane convert not marked ported")
    return ANE_COLLECT_PLANAR_ALLOC


def ane_collect_planar_factory_vtbl() -> int:
    """``[esi]=0x1057b10c`` after planar ctor @ ``0x100db500``."""
    if not ANE_COLLECT_CONVERT_PORTED:
        raise NotImplementedError("Ane convert not marked ported")
    return ANE_COLLECT_PLANAR_VTBL


def ane_collect_planar_plane_bases(
    base: int, width: int, height: int
) -> Tuple[int, int, int]:
    """Planar int16 plane bases for ``w×h`` RGB.

    Cite ``0x101ee78d…0x101ee7a8``: ``base``, ``base+2·w·h``,
    ``base+4·w·h`` (stored at ``ebp-0x84/-0x80/-0x7c`` before
    ``0x100db490``).
    """
    wh = int(width) * int(height)  # PakonIMAu.dll @ 0x101ee790 imul
    b0 = int(base)  # PakonIMAu.dll @ 0x101ee797
    b1 = b0 + wh * 2  # PakonIMAu.dll @ 0x101ee79d lea [ecx+eax*2]
    b2 = b1 + wh * 2  # PakonIMAu.dll @ 0x101ee7a0 lea [ecx+eax*2]
    return b0, b1, b2


def ane_collect_qi_payload_byte_count() -> int:
    """Bytes copied into QI at ``+0x20`` (9 dwords)."""
    # PakonIMAu.dll @ 0x101ee9fc — mov ecx, 9 / rep movsd
    return ANE_QI_PAYLOAD_DWORDS * 4


def ane_fc80_planes(
    plane: np.ndarray,
    *,
    x_step: int = 1,
    y_step: int = 1,
    avg_flag: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build sample + residual int16 planes for one channel (``0x1027fc80``).

    ``plane`` is 2-D int16. Output size matches DLL: from starts aligned so
    the last center stays ≥2 from borders (cite ``0x1027fd3c…0x1027fd96``).
    Host uses the same margin/step arithmetic for parity.
    """
    if plane.ndim != 2:
        raise ValueError("plane must be 2-D")
    h, w = plane.shape
    xs = max(1, int(x_step))
    ys = max(1, int(y_step))
    # DLL: start at 1+step (while start < 2), end trimmed by −3 margin.
    x0 = 1
    while x0 < 2:
        x0 += xs
    y0 = 1
    while y0 < 2:
        y0 += ys
    # last center ≤ dim-3
    def n_out(dim: int, start: int, step: int) -> int:
        if start > dim - 3:
            return 0
        return (dim - 3 - start) // step + 1

    nw = n_out(w, x0, xs)
    nh = n_out(h, y0, ys)
    if nh == 0 or nw == 0:
        return (
            np.zeros((0, 0), dtype=np.int16),
            np.zeros((0, 0), dtype=np.int16),
        )
    flat = plane.astype(np.int16, copy=False).ravel()
    pitch = w
    sampled = np.empty((nh, nw), dtype=np.int16)
    residual = np.empty((nh, nw), dtype=np.int16)
    for oy in range(nh):
        cy = y0 + oy * ys
        for ox in range(nw):
            cx = x0 + ox * xs
            s, r = ane_fc80_pixel(flat, pitch, cy, cx, avg_flag=avg_flag)
            sampled[oy, ox] = s
            residual[oy, ox] = r
    return sampled, residual


def ane_fc80_rgb_sample_residual(
    rgb_i16: np.ndarray,
    *,
    col_sampling: int = ANE_DPI_COL_SAMPLING,
    row_sampling: int = ANE_DPI_ROW_SAMPLING,
    correct_for_filter: bool = ANE_DPI_CORRECT_FOR_FILTER,
) -> Tuple[list[np.ndarray], list[np.ndarray]]:
    """Per-channel ``0x1027fc80`` planes for HxWx3 int16 RGB.

    Returns ``(sample_planes, residual_planes)`` each length 3. Empty when
    the source is smaller than the 5-tap + step grid.
    """
    img = np.asarray(rgb_i16)
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError("rgb_i16 must be HxWx≥3")
    samples: list[np.ndarray] = []
    residuals: list[np.ndarray] = []
    for c in range(3):
        s, r = ane_fc80_planes(
            img[:, :, c],
            x_step=col_sampling,
            y_step=row_sampling,
            avg_flag=correct_for_filter,
        )
        samples.append(s)
        residuals.append(r)
    return samples, residuals


def ane_noise_table_from_rgb_fc80(
    rgb_i16: np.ndarray,
    n: int,
    *,
    col_sampling: int = ANE_DPI_COL_SAMPLING,
    row_sampling: int = ANE_DPI_ROW_SAMPLING,
    correct_for_filter: bool = ANE_DPI_CORRECT_FOR_FILTER,
    code_value_bins: int = 32,
    **e9d0_kwargs,
):
    """``collectData`` Laplacian leaf → ``0x1027e9d0`` ``NoiseTable``.

    One scene / one RGB image (shipped path builds portfolio then analyze).
    Defaults match ``ane-CN-Fps.dpi`` bins=32 when ``code_value_bins`` omitted.
    Raises ``ValueError`` if the sample grid is empty.
    """
    from pakon_ane_order import ane_build_noise_table_e9d0

    samples, residuals = ane_fc80_rgb_sample_residual(
        rgb_i16,
        col_sampling=col_sampling,
        row_sampling=row_sampling,
        correct_for_filter=correct_for_filter,
    )
    if samples[0].size == 0:
        raise ValueError(
            "fc80 sample grid empty (need image larger than step+margin)"
        )
    return ane_build_noise_table_e9d0(
        [(samples, residuals)],
        int(n),
        code_value_bins=int(code_value_bins),
        **e9d0_kwargs,
    )


def _box_margin(filter_size: int) -> int:
    """Border margin for box filter (cite ``0x10280578…0x10280587``)."""
    return 1 if int(filter_size) == 3 else 2


def ane_804e0_planes(
    plane: np.ndarray,
    *,
    filter_size: int = 5,
    x_step: int = 1,
    y_step: int = 1,
    avg_flag: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build sample + residual int16 planes for one channel (``0x102804e0``).

    Margin 1 for ``filter_size==3``, else 2 (cite setup ``0x10280578…``).
    Step alignment matches the DLL ``start=1; while start < margin: +step``.
    """
    if plane.ndim != 2:
        raise ValueError("plane must be 2-D")
    h, w = plane.shape
    xs = max(1, int(x_step))
    ys = max(1, int(y_step))
    margin = _box_margin(filter_size)
    # last center ≤ dim - (margin+1); same as dim-3 when margin=2
    last_lim = margin + 1

    x0 = 1
    while x0 < margin:
        x0 += xs
    y0 = 1
    while y0 < margin:
        y0 += ys

    def n_out(dim: int, start: int, step: int) -> int:
        if start > dim - last_lim:
            return 0
        return (dim - last_lim - start) // step + 1

    nw = n_out(w, x0, xs)
    nh = n_out(h, y0, ys)
    if nh == 0 or nw == 0:
        return (
            np.zeros((0, 0), dtype=np.int16),
            np.zeros((0, 0), dtype=np.int16),
        )
    flat = plane.astype(np.int16, copy=False).ravel()
    pitch = w
    sampled = np.empty((nh, nw), dtype=np.int16)
    residual = np.empty((nh, nw), dtype=np.int16)
    for oy in range(nh):
        cy = y0 + oy * ys
        for ox in range(nw):
            cx = x0 + ox * xs
            s, r = ane_804e0_pixel(
                flat,
                pitch,
                cy,
                cx,
                filter_size=filter_size,
                avg_flag=avg_flag,
            )
            sampled[oy, ox] = s
            residual[oy, ox] = r
    return sampled, residual


def ane_collect_planes(
    plane: np.ndarray,
    *,
    filter_mode_laplacian: bool = ANE_DPI_FILTER_MODE_LAPLACIAN,
    filter_size: int = 5,
    x_step: int = 1,
    y_step: int = 1,
    avg_flag: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Dispatch helper: Laplacian → fc80 else box ``804e0`` (``0x10280bd0``).

    Shipped dpi is Laplacian → fc80. Pass ``filter_mode_laplacian=False``
    with ``filter_size`` 3 or 5 for the box path.
    """
    if filter_mode_laplacian:
        return ane_fc80_planes(
            plane, x_step=x_step, y_step=y_step, avg_flag=avg_flag
        )
    return ane_804e0_planes(
        plane,
        filter_size=filter_size,
        x_step=x_step,
        y_step=y_step,
        avg_flag=avg_flag,
    )


def ane_collect_rgb_sample_residual(
    rgb_i16: np.ndarray,
    *,
    cap: Optional[AneCollectCapParams] = None,
) -> Tuple[list[np.ndarray], list[np.ndarray], bool]:
    """Per-channel sample/residual via Cap→``0x10280bd0`` dispatch.

    Returns ``(sample_planes, residual_planes, used_laplacian)``.
    """
    p = cap or AneCollectCapParams()
    img = np.asarray(rgb_i16)
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError("rgb_i16 must be HxWx≥3")
    # PakonIMAu.dll @ 0x10280bd0
    use_lap = ane_collect_dispatch_uses_laplacian(p.filter_mode_ptr)
    samples: list[np.ndarray] = []
    residuals: list[np.ndarray] = []
    for c in range(3):  # PakonIMAu.dll @ 0x101ee7da push 3
        s, r = ane_collect_planes(
            img[:, :, c],
            filter_mode_laplacian=use_lap,
            filter_size=p.filter_size,
            x_step=p.col_sampling,
            y_step=p.row_sampling,
            avg_flag=p.correct_for_filter,
        )
        samples.append(s)
        residuals.append(r)
    return samples, residuals, use_lap


def ane_collect_data(
    rgb_images: Sequence[np.ndarray],
    *,
    cap: Optional[AneCollectCapParams] = None,
    image_types: Optional[Sequence[int]] = None,
    portfolio: Optional[AneQiPortfolio] = None,
) -> AneCollectDataResult:
    """Host face of ``AnsAneCapabilityImpl::collectData`` @ ``0x101ee590``.

    Picks the best source under ``minMajorDim``, dispatches Cap fields
    through ``0x10280bd0``, builds named QI entries, and
    ``0x1008b7e0``-inserts (replace-by-name) into ``portfolio``.
    Type≠2 COM convert is not executed on host.
    """
    if not ANE_COLLECT_DATA_PORTED:
        raise NotImplementedError("collectData host orch not marked ported")
    p = cap or AneCollectCapParams()
    port = portfolio if portfolio is not None else AneQiPortfolio()
    imgs = list(rgb_images)
    if not imgs:
        return AneCollectDataResult(
            entries=(), source_index=None, used_laplacian=False, portfolio=port
        )

    dims = []
    for im in imgs:
        a = np.asarray(im)
        if a.ndim != 3 or a.shape[2] < 3:
            raise ValueError("each rgb image must be HxWx≥3")
        dims.append((int(a.shape[1]), int(a.shape[0])))  # (w, h)

    # PakonIMAu.dll @ 0x101ee650… — pick best under Cap+0xb8
    src_i = ane_collect_pick_best_source(dims, p.min_major_dim)
    if src_i is None:
        return AneCollectDataResult(
            entries=(), source_index=None, used_laplacian=False, portfolio=port
        )

    if image_types is not None:
        # PakonIMAu.dll @ 0x101ee6aa — host cannot run 0x100da770
        if ane_collect_needs_image_convert(int(image_types[src_i])):
            raise NotImplementedError(
                "image type≠2 needs COM convert 0x100da770 "
                f"(type={int(image_types[src_i])})"
            )

    samples, residuals, use_lap = ane_collect_rgb_sample_residual(
        imgs[src_i], cap=p
    )
    if samples[0].size == 0:
        return AneCollectDataResult(
            entries=(),
            source_index=src_i,
            used_laplacian=use_lap,
            portfolio=port,
        )

    # PakonIMAu.dll @ 0x101ee9d6…0x101eeabf — name ctor + payload + insert
    h, w = int(samples[0].shape[0]), int(samples[0].shape[1])
    # Minimal 9-dword desc: type=2 skip-convert, w, h (offsets match pick walk
    # +0x14/+0x18 style locals — host only needs cited dword count).
    desc = (ANE_IMAGE_TYPE_SKIP_CONVERT, 0, 0, 0, 0, w, h, 0, 0)
    sampled = ane_qi_build_entry(ANE_QI_NAME_SAMPLED, tuple(samples), desc)
    residual = ane_qi_build_entry(ANE_QI_NAME_RESIDUAL, tuple(residuals), desc)
    # @ 0x101eea38 / @ 0x101eeabf — insert; fail → unable-insert strings
    if not ane_qi_insert(port, sampled):
        return AneCollectDataResult(
            entries=(), source_index=src_i, used_laplacian=use_lap, portfolio=port
        )
    if not ane_qi_insert(port, residual):
        return AneCollectDataResult(
            entries=(sampled,),
            source_index=src_i,
            used_laplacian=use_lap,
            portfolio=port,
        )
    return AneCollectDataResult(
        entries=(sampled, residual),
        source_index=src_i,
        used_laplacian=use_lap,
        portfolio=port,
    )
