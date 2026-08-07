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
   **Producing** the desc words themselves (host ``PIAnselAddScene``)
   remains outside this module.
2. ``ColorNegativePath::analyzeScpLutBalance`` @ ``0x100fdaa8``:
   - Remap ``path+0x3c/+0x3e/+0x40`` through a LUT (``0x100fd984…``),
   - ``lea esi, [edi+0x3c]`` then ``insert("dmin", esi, 6, …)``.

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

``SCPLUT_DMIN_REMAP_PORTED = True``. Upstream ``path+0x3c`` **source**
values remain WALL (FUGC Cap analyze *reads* ``&path+0x3c`` as aim
input when policy passes — it does not fill those words; sole static
``mov word`` to ``+0x4b6`` is ScpLut zeroing).

Other ``"dmin"`` push sites exist (FUGC / noise / …); mid-aim **reader**
is the CnPremium ``find`` above.

Host bag
--------
``SceneContextBag`` is a plain name→bytes map. It is **not** a COM port of
``0x10022a40`` / ``0x10023f10`` (STL/refcount). It is enough to feed
``cn_premium_mid_aim_rgb`` when the host already knows dmin RGB (e.g. from
bAddScene desc or ScpLut-remapped ``path+0x3c``).

``SCENE_CONTEXT_DMIN_PORTED = True`` — bag I/O + pack/unpack + ScpLut
remap + bAddScene pack leaf. Live desc words / ``path+0x3c`` **source**
producers still host-supplied / WALL.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Sequence

SCENE_CONTEXT_DMIN_PORTED = True
SCPLUT_DMIN_REMAP_PORTED = True
BADDSCENE_DMIN_PACK_PORTED = True

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
SCPLUT_DMIN_INSERT = 0x100FDAA8
SCPLUT_DMIN_REMAP = 0x100FD984  # path+0x3c through LUT, then insert
SCPLUT_CAP_GET_LUT = 0x10122150
SCPLUT_IMPL_GET_LUT = 0x10212100
PATH_DMIN_RGB_OFF = 0x3C  # 3×int16 at +0x3c/+0x3e/+0x40
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
    print(f"  ScpLut insert       {SCPLUT_DMIN_INSERT:#010x} (remap {SCPLUT_DMIN_REMAP:#010x})")
    print(f"  ScpLut getLut Cap/Impl {SCPLUT_CAP_GET_LUT:#010x}/{SCPLUT_IMPL_GET_LUT:#010x}")
    bag = SceneContextBag()
    bag.insert_dmin((100, 200, 300))
    print(
        f"  roundtrip {bag.find_dmin()} "
        f"SCENE_CONTEXT_DMIN_PORTED={SCENE_CONTEXT_DMIN_PORTED} "
        f"BADDSCENE_PACK={BADDSCENE_DMIN_PACK_PORTED}"
    )
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
