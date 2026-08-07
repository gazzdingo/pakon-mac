#!/usr/bin/env python3
"""AnsSceneContext find/insert — dmin bag for CnPremium mid-aims.

PakonIMAu.dll base ``0x10000000``. Host models the named property bag that
``CnPremium_analyzeSceneSpecific`` reads for mid-aim RGB. Do **not** invent
scene dmin values — only pack/unpack + bag I/O matching the binary.

VERIFIED
========

``AnsSceneContext::find`` @ ``0x10022a40``
-----------------------------------------
* String ``0x10576ba4`` / source ``AnsSceneContext.cpp`` ``0x10576bd4``.
* Looks up name in map at ``this+0xc`` via ``0x10022900``; on hit copies
  stored blob into caller buffer (``rep movsd`` @ ``0x10022bc4``).
* CnPremium mid-aim call @ ``0x100566ac``:

  - Seed stack RGB ``[ebp-0x34…]`` from ShastaParams ``black`` (``+0x3c``)
    replicated to R=G=B (``0x10056663…``).
  - ``find("dmin" @ ``0x105737c8``, size=6, buf=*)`` — 6-byte RGB int16.
  - Success (status == null sentinel ``0x106b5bd4``) continues to
    ``NoiseMethods::getNoiseTable`` @ ``0x10112980``; failure aborts
    SceneSpecific (no silent keep-seed on the dens path).

``AnsSceneContext::insert`` @ ``0x10023f10``
-------------------------------------------
* String ``0x10576c98``.
* Args include name, data pointer, byte size, overwrite flag.

Cited dmin **writers** (size=6, name ``"dmin"``):

1. ``CiColorCorrectionAnsel::bAddScene`` @ insert site ``0x10002523``
   (string ``0x10573a58``). Jump table ``0x10002824`` on desc
   ``+0x48`` (``cmp eax,4; ja``):

   | case | entry        | packs dmin from desc? | ``ebp-0x18`` |
   |------|--------------|-----------------------|--------------|
   | 0    | ``0x10002318`` | no                    | 3            |
   | 1–3  | ``0x100022e6`` | **yes** ``+0x54/58/5c`` → ``ebp-0x38`` | 1 |
   | 4    | ``0x1000230b`` | no                    | 3            |

   Insert runs only when ``[ebp-0x18]==1`` (``0x100024f3``) — i.e. cases
   1–3. Pack leaf Unicorn-golden → ``BADDSCENE_DMIN_PACK_PORTED``.
2. ``ColorNegativePath::analyzeScpLutBalance`` @ ``0x100fdaa8``:
   - Remap ``path+0x3c/+0x3e/+0x40`` through a LUT (``0x100fd984…``),
   - ``lea esi, [edi+0x3c]`` then ``insert("dmin", esi, 6, …)``.

Host ``PIAnselAddScene`` / TLA desc pack (VERIFIED + Unicorn)
-----------------------------------------------------------
* Export ``PIAnselAddScene`` @ ``0x100183c0`` — thin wrapper:
  ``push arg3,arg2,arg1; ecx=singleton 0x106b5b18; call bAddScene``.
* TLA ``bKcdfsCorrections`` @ ``0x1003f720`` call site ``0x1003fb7a``:
  ``call [JT+0x54]`` with desc ``&esp+0x68``.
* Desc pack leaf ``0x1003f901…0x1003f941`` (Unicorn):

  1. ``rep stosd`` zero ``0x1a`` dwords (``0x68`` bytes) at desc.
  2. ``desc+0x48`` ← case dword (film-type switch → ``esp+0x14``).
  3. ``desc+0x54/+0x58/+0x5c`` ← dword stores of zero-extended words
     from locals ``esp+0x34/+0x3c/+0x44`` (bAddScene reads as int16).

* Seed RGB words before pack (``0x1003f7db…``): frame object
  ``+0x6cac/+0x6cb0/+0x6cb4`` → locals; optional 1-pixel ColNeg
  ``JT+0x44`` / ColRev ``JT+0x4c`` remap of the 3-word buffer
  (``0x1003f82d…``) — **not** host-ported (needs planar args).
* Case table from ``[ebx]+0x34`` film class (``0x1003f89b…``).

``ADDSCENE_DESC_PACK_PORTED = True``. Frame ``+0x6cac`` producers +
ColNeg remap of those words still open for end-to-end live RGB.

``path+0x3c`` source — ``getCnContext`` (VERIFIED)
-------------------------------------------------
``ColorNegativePath::getCnContext`` @ ``0x100f8620`` (OrderWide):

* ``lea edi, [path+0x3c]``; ``find("dmin", size=6, buf=&path+0x3c)``
  @ ``0x100f8bd6…`` — find ``rep movsd`` fills the three int16s.
* On empty size (``0x100f8c6f…``): zero ``+0x3c/+0x3e/+0x40``.

No non-zero static ``mov word [path+0x3c]`` in cnMethods — the bag
copy **is** the source writer. FUGC Cap analyze still only *reads*
``&path+0x3c``. ``PATH_DMIN_FROM_BAG_PORTED = True``.

ScpLut remap @ ``0x100fd984…0x100fd9b3`` (VERIFIED + Unicorn)
-------------------------------------------------------------
Cap getter ``0x10122150`` → Impl ``0x10212100`` (``ret 0xc``) writes:

* ``out0`` ← ``int16`` at CapImpl ``+0x10`` blob ``+0`` → **stride**
* ``out1`` ← ``int16`` at blob ``+2`` (unused by remap)
* ``out2`` ← ``dword`` at blob ``+4`` → **int16 LUT** base

Call-site push order aliases ``stride`` to ``[esp+0x2c]`` and LUT to
``[esp+0x20]``. Remap (in place on ``path+0x3c``):

* ``R' = lut[R]``
* ``G' = lut[G + stride]``
* ``B' = lut[B + 2·stride]``

``SCPLUT_DMIN_REMAP_PORTED = True``.

Other ``"dmin"`` push sites exist (FUGC / noise / …); mid-aim **reader**
is the CnPremium ``find`` above.

Host bag
--------
``SceneContextBag`` is a plain name→bytes map. It is **not** a COM port of
``0x10022a40`` / ``0x10023f10`` (STL/refcount). It is enough to feed
``cn_premium_mid_aim_rgb`` when the host already knows dmin RGB (e.g. from
bAddScene desc or ScpLut-remapped ``path+0x3c``).

``SCENE_CONTEXT_DMIN_PORTED = True`` — bag I/O + pack/unpack + ScpLut
remap + bAddScene pack + AddScene desc pack + getCnContext path load.
Frame ``+0x6cac`` live RGB + ColNeg side path + Ane knots still open
for ``SHASTA_ANALYZE_PORTED``.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Sequence

SCENE_CONTEXT_DMIN_PORTED = True
SCPLUT_DMIN_REMAP_PORTED = True
BADDSCENE_DMIN_PACK_PORTED = True
ADDSCENE_DESC_PACK_PORTED = True
PATH_DMIN_FROM_BAG_PORTED = True

SCENE_CONTEXT_FIND = 0x10022A40
SCENE_CONTEXT_INSERT = 0x10023F10
STR_DMIN = 0x105737C8
STR_FIND = 0x10576BA4
STR_INSERT = 0x10576C98
STR_BADDSCENE = 0x10573A58

CN_PREMIUM_DMIN_FIND_CALL = 0x100566AC  # E8 → find
BADDSCENE_DMIN_INSERT = 0x10002523
BADDSCENE_DMIN_PACK = 0x100022E6  # cases 1–3: desc → ebp-0x38
BADDSCENE_DMIN_PACK_END = 0x10002309  # before jmp join
BADDSCENE_CASE_JT = 0x10002824  # dword[5] jump table on desc+0x48
PIANSEL_ADD_SCENE = 0x100183C0  # export → bAddScene
BADDSCENE = 0x10002290
TLA_BKCDFS_CORRECTIONS = 0x1003F720  # TLA.dll
TLA_ADDSCENE_CALL = 0x1003FB7A  # call [JT+0x54]
TLA_DESC_PACK = 0x1003F901  # zero + case + RGB dword stores
TLA_DESC_PACK_END = 0x1003F941  # before call [vt+0x70]
TLA_FRAME_DMIN_R_OFF = 0x6CAC
TLA_FRAME_DMIN_G_OFF = 0x6CB0
TLA_FRAME_DMIN_B_OFF = 0x6CB4
GET_CN_CONTEXT = 0x100F8620
GET_CN_CONTEXT_DMIN_FIND = 0x100F8BD6  # lea path+0x3c; find dmin
GET_CN_CONTEXT_DMIN_ZERO = 0x100F8C6F  # empty → zero +0x3c/3e/40
SCPLUT_DMIN_INSERT = 0x100FDAA8
SCPLUT_DMIN_REMAP = 0x100FD984  # path+0x3c through LUT, then insert
SCPLUT_CAP_GET_LUT = 0x10122150
SCPLUT_IMPL_GET_LUT = 0x10212100
PATH_DMIN_RGB_OFF = 0x3C  # 3×int16 at +0x3c/+0x3e/+0x40
DESC_BYTES = 0x68  # TLA zero span (0x1a dwords)
DESC_DMIN_CASE_OFF = 0x48
DESC_DMIN_R_OFF = 0x54
DESC_DMIN_G_OFF = 0x58
DESC_DMIN_B_OFF = 0x5C
DMIN_BYTES = 6


def pack_dmin_rgb(r: int, g: int, b: int) -> bytes:
    """6-byte little-endian int16 RGB (find/insert size)."""
    return struct.pack("<hhh", int(r), int(g), int(b))


def unpack_dmin_rgb(blob: bytes) -> tuple[int, int, int]:
    """Inverse of ``pack_dmin_rgb``; requires exactly 6 bytes."""
    if len(blob) != DMIN_BYTES:
        raise ValueError(f"dmin blob must be {DMIN_BYTES} bytes, got {len(blob)}")
    r, g, b = struct.unpack("<hhh", blob)
    return int(r), int(g), int(b)


def baddscene_case_packs_dmin(case: int) -> bool:
    """True when desc ``+0x48`` selects packed dmin insert (cases 1–3)."""
    return int(case) in (1, 2, 3)


def baddscene_pack_dmin_from_desc(
    word_54: int, word_58: int, word_5c: int
) -> bytes:
    """bAddScene packed case @ ``0x100022e6…`` — desc ``+0x54/+0x58/+0x5c``.

    Unicorn-golden word copy into the 6-byte insert buffer (``ebp-0x38``).
    """
    return pack_dmin_rgb(word_54, word_58, word_5c)


def addscene_pack_desc(case: int, r: int, g: int, b: int) -> bytearray:
    """TLA AddScene desc pack @ ``0x1003f901…`` (Unicorn-golden).

    Zero ``DESC_BYTES``, store case at ``+0x48``, RGB as zero-extended
    dwords at ``+0x54/+0x58/+0x5c`` (bAddScene reads the low int16s).
    """
    desc = bytearray(DESC_BYTES)
    struct.pack_into("<I", desc, DESC_DMIN_CASE_OFF, int(case) & 0xFFFFFFFF)
    struct.pack_into("<I", desc, DESC_DMIN_R_OFF, int(r) & 0xFFFF)
    struct.pack_into("<I", desc, DESC_DMIN_G_OFF, int(g) & 0xFFFF)
    struct.pack_into("<I", desc, DESC_DMIN_B_OFF, int(b) & 0xFFFF)
    return desc


def addscene_desc_dmin_rgb(desc: bytes | bytearray) -> tuple[int, int, int]:
    """Read desc ``+0x54/+0x58/+0x5c`` as int16 (bAddScene view).

    TLA stores zero-extended **dwords** at those offsets; bAddScene
    reads the low int16 of each (not three packed consecutive words).
    """
    if len(desc) < DESC_DMIN_B_OFF + 4:
        raise ValueError("desc too short for dmin dwords")
    r = struct.unpack_from("<h", desc, DESC_DMIN_R_OFF)[0]
    g = struct.unpack_from("<h", desc, DESC_DMIN_G_OFF)[0]
    b = struct.unpack_from("<h", desc, DESC_DMIN_B_OFF)[0]
    return int(r), int(g), int(b)


def getcncontext_path_dmin_from_bag(
    bag: "SceneContextBag",
) -> tuple[int, int, int]:
    """getCnContext path ``+0x3c`` load @ ``0x100f8bd6…`` / zero ``0x100f8c6f``.

    Host stand-in for ``find("dmin", size=6, buf=&path+0x3c)``: return
    bag RGB, or ``(0,0,0)`` when absent (DLL zeroes the three words).
    """
    rgb = bag.find_dmin()
    if rgb is None:
        return (0, 0, 0)
    return rgb


def scplut_remap_dmin_rgb(
    lut: Sequence[int],
    stride: int,
    r: int,
    g: int,
    b: int,
) -> tuple[int, int, int]:
    """ScpLutBalance dmin remap @ ``0x100fd984…`` before insert.

    ``lut`` is int16-indexed (host may pass a list/array of int). Indices
    are ``R``, ``G+stride``, ``B+2*stride`` — cite Cap getter outs.
    """
    rr = int(r)
    gg = int(g)
    bb = int(b)
    s = int(stride)
    return int(lut[rr]), int(lut[gg + s]), int(lut[bb + 2 * s])


def scplut_remap_and_pack(
    lut: Sequence[int],
    stride: int,
    r: int,
    g: int,
    b: int,
) -> bytes:
    """Remap then pack 6-byte dmin (insert payload)."""
    return pack_dmin_rgb(*scplut_remap_dmin_rgb(lut, stride, r, g, b))


@dataclass
class SceneContextBag:
    """Host stand-in for AnsSceneContext named blobs (dmin and kin)."""

    items: dict[str, bytes] = field(default_factory=dict)

    def insert(self, name: str, data: bytes, *, overwrite: bool = True) -> None:
        """``0x10023f10`` contract: store ``data`` under ``name``."""
        if not overwrite and name in self.items:
            return
        self.items[name] = bytes(data)

    def insert_dmin(self, rgb: tuple[int, int, int] | list[int], *, overwrite: bool = True) -> None:
        self.insert("dmin", pack_dmin_rgb(rgb[0], rgb[1], rgb[2]), overwrite=overwrite)

    def find(self, name: str, size: int | None = None) -> bytes | None:
        """``0x10022a40`` contract: return blob or ``None`` if missing.

        When ``size`` is set, require exact length (CnPremium passes 6).
        """
        blob = self.items.get(name)
        if blob is None:
            return None
        if size is not None and len(blob) != size:
            raise ValueError(f"{name!r}: stored {len(blob)} bytes, find size={size}")
        return bytes(blob)

    def find_dmin(
        self,
        *,
        seed_black: int | None = None,
    ) -> tuple[int, int, int] | None:
        """CnPremium dmin read: optional black seed, then find size=6.

        Returns ``None`` if ``dmin`` is absent (DLL aborts SceneSpecific).
        When present, returns the stored RGB (seed is only the pre-find
        stack init the binary overwrites on success).
        """
        blob = self.find("dmin", DMIN_BYTES)
        if blob is None:
            return None
        return unpack_dmin_rgb(blob)


def main() -> None:
    print("AnsSceneContext dmin bag (base 0x10000000)")
    print(f"  find   {SCENE_CONTEXT_FIND:#010x}")
    print(f"  insert {SCENE_CONTEXT_INSERT:#010x}")
    print(f"  CnPremium find call {CN_PREMIUM_DMIN_FIND_CALL:#010x}")
    print(f"  bAddScene insert    {BADDSCENE_DMIN_INSERT:#010x}")
    print(f"  bAddScene pack      {BADDSCENE_DMIN_PACK:#010x}")
    print(f"  PIAnselAddScene     {PIANSEL_ADD_SCENE:#010x}")
    print(f"  TLA desc pack       {TLA_DESC_PACK:#010x} (TLA.dll)")
    print(f"  getCnContext        {GET_CN_CONTEXT:#010x}")
    print(f"  ScpLut insert       {SCPLUT_DMIN_INSERT:#010x} (remap {SCPLUT_DMIN_REMAP:#010x})")
    print(f"  ScpLut getLut Cap/Impl {SCPLUT_CAP_GET_LUT:#010x}/{SCPLUT_IMPL_GET_LUT:#010x}")
    bag = SceneContextBag()
    bag.insert_dmin((100, 200, 300))
    print(
        f"  roundtrip {bag.find_dmin()} "
        f"SCENE_CONTEXT_DMIN_PORTED={SCENE_CONTEXT_DMIN_PORTED} "
        f"BADDSCENE_PACK={BADDSCENE_DMIN_PACK_PORTED} "
        f"ADDSCENE_DESC={ADDSCENE_DESC_PACK_PORTED} "
        f"PATH_FROM_BAG={PATH_DMIN_FROM_BAG_PORTED}"
    )
    desc = addscene_pack_desc(2, 100, 200, 300)
    print(
        f"  addscene desc case={struct.unpack_from('<I', desc, DESC_DMIN_CASE_OFF)[0]} "
        f"rgb={addscene_desc_dmin_rgb(desc)}"
    )
    print(f"  getCnContext path dmin={getcncontext_path_dmin_from_bag(bag)}")
    lut = list(range(400))
    print(
        f"  scplut remap sample {scplut_remap_dmin_rgb(lut, 100, 5, 6, 7)} "
        f"REMAP_PORTED={SCPLUT_DMIN_REMAP_PORTED}"
    )
    print(
        f"  bAddScene cases pack? "
        f"{[baddscene_case_packs_dmin(c) for c in range(5)]}"
    )


if __name__ == "__main__":
    main()
