#!/usr/bin/env python3
"""Golden ``AnsShastaCapabilityImpl::analyze`` inner stage vs PakonIMAu.dll.

This is the **assembled-whole** harness: the earlier six ``pakon_shasta_*_golden``
files each verify one leaf with hand-injected work-object bytes. This one packs
a work object from a shipped ``shasta-*.dpi`` and runs the real orchestrator

    ``0x1027be10``  (analyze's image stage, called at ``0x101e584d``)

which itself calls, for real, ``0x1027b1c0`` (prep) → ``0x1027b970``
(percentiles, which calls the Iem histogram fill ``0x104eab00`` → ``0x104ea940``
→ ``0x104ea7f0``) → ``0x1027b3c0`` (planar means) → seed → ``0x102935d0``
→ post-scale → ``0x1027b2f0`` (filter-policy flags), and then feeds the result
into the builder ``0x10293ee0``. Nothing between the image and the toneLut is
injected.

Work-object layout (PROVEN, not inferred)
-----------------------------------------
``AnsShastaCapabilityImpl::analyze`` builds the work object at ``ebp-0x770``
(ctor ``0x101e0db0`` @ ``0x101e5805``) and then, at ``0x101e5814/0x101e581e``,
copies the Cap's ``ShastaParams`` (``this+0x10``) into ``work+0x10`` via
``0x1008e970``.  Therefore::

    work_offset = ShastaParams_offset + 0x10

The ``ShastaParams`` field↔name map is read straight out of the params dump
function (``0x10127e00…``, the ``params.<name>`` printer whose store offsets and
literal names pair one-to-one). ``SHASTA_WORK_LAYOUT`` below is that map shifted
by ``0x10``, and it is cross-checked by six independent uses in the DLL:

* prep ``0x1027b1c0`` multiplies by ``work+0x58`` → ``codeValuesPerButton``
* ``0x1027b970`` reads percents at ``work+0x80…+0x98`` and
  ``highlightDiffMult/Limit`` at ``+0xa0/+0xa8``
* ``0x1027b970`` sizes the histogram from ``work+0x64`` → ``maxValue``
* ``0x1027b3c0`` gates white-point compression on ``work+0x208`` and reads
  ``work+0x210/+0x218`` → ``bUseWhitePtCompression`` / ``whiteSat{Lower,Upper}Limit``
* ``0x1027be10`` scales the shadow adj ``+0x370`` by ``work+0x228`` and the
  highlight adj ``+0x378`` by ``work+0x230`` → ``shadowDeltaGain`` /
  ``highlightDeltaGain``
* ``0x1027b2f0`` switches on ``work+0x1c8`` → ``filterPolicy``

and by the builder's own symmetry (fill#1/highlight takes ``+0x128``
``highlightCompBlend`` / ``+0x148`` ``highlightTransitionRatio`` / ``+0x340``
whitePointRatio; fill#2/shadow takes ``+0x120`` ``shadowCompBlend`` / ``+0x140``
``shadowTransitionRatio`` / ``+0x220`` ``blackPointRatio``).

Harness stubs (host-supplied, none of them arithmetic)
-----------------------------------------------------
The PE is loaded unbound and CRT init never runs, so the harness supplies:
``operator new`` → bump allocator; ``operator delete``/``delete[]`` → no-op;
``memmove`` import thunk; a plane vtable whose ``+0x20`` "has data" predicate
returns true; and the I16 type singleton ``[0x106c8250]``. Everything that
computes a number is the DLL's own code.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_shasta_analyze_golden.py [dll] [dpi]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from unicorn import (
    Uc,
    UcError,
    UC_ARCH_X86,
    UC_MODE_32,
    UC_HOOK_CODE,
    UC_HOOK_MEM_INVALID,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x02000000
SCRATCH = 0x00100000
RET_MAGIC = 0x00110000

VA_OP_NEW = 0x104FFD53
VA_OP_DELETE = 0x104FFDD0
VA_OP_DELETE_ARR = 0x104FFE3E
IAT_MEMMOVE = 0x105735B8
VA_I16_TYPE_SINGLETON = 0x106C8250

VA_7BE10 = 0x1027BE10   # analyze image stage
VA_7B3C0 = 0x1027B3C0   # planar means
VA_7B970 = 0x1027B970   # percentile codes
VA_93EE0 = 0x10293EE0   # toneLut builder
VA_VEC_FILL = 0x10246050
VA_HIST_FILLED = 0x1027BA3A  # first instruction after 0x104eab00 returns

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)
DEFAULT_DPI = (
    Path(__file__).resolve().parents[3]
    / "vendor/ansel/anselinstalldir/dataPathItems/shasta/shasta-rpd.dpi"
)

# ---------------------------------------------------------------------------
# Proven work-object layout: ShastaParams offset + 0x10.
# (offset, dpi key, "d" double / "i" int32)
# ---------------------------------------------------------------------------
SHASTA_WORK_LAYOUT: tuple[tuple[int, str, str], ...] = (
    (0x48, "metricGray", "i"),
    (0x4C, "black", "i"),
    (0x50, "white", "i"),
    (0x58, "codeValuesPerButton", "d"),
    (0x60, "minValue", "i"),
    (0x64, "maxValue", "i"),
    (0x68, "analysisImageDim", "d"),
    (0x70, "rowPortion", "d"),
    (0x78, "colPortion", "d"),
    (0x80, "extShadowPercent", "d"),
    (0x88, "shadowPercent", "d"),
    (0x90, "highlightPercent", "d"),
    (0x98, "extHighlightPercent", "d"),
    (0xA0, "highlightDiffMult", "d"),
    (0xA8, "highlightDiffLimit", "d"),
    (0xB0, "blackButtons", "d"),
    (0xB8, "extShadowButtons", "d"),
    (0xC0, "shadowButtons", "d"),
    (0xC8, "highlightButtons", "d"),
    (0xD0, "extHighlightButtons", "d"),
    (0xD8, "blackAggr", "d"),
    (0xE0, "extShadowAggr", "d"),
    (0xE8, "shadowAggr", "d"),
    (0xF0, "highlightAggr", "d"),
    (0xF8, "extHighlightAggr", "d"),
    (0x100, "shadowExpScale", "d"),
    (0x108, "highlightExpScale", "d"),
    (0x110, "shadowMaxExpSlope", "d"),
    (0x118, "highlightMaxExpSlope", "d"),
    (0x120, "shadowCompBlend", "d"),
    (0x128, "highlightCompBlend", "d"),
    (0x130, "shadowExpBlend", "d"),
    (0x138, "highlightExpBlend", "d"),
    (0x140, "shadowTransitionRatio", "d"),
    (0x148, "highlightTransitionRatio", "d"),
    (0x150, "shadowExpSatFactor", "d"),
    (0x158, "shadowCompSatFactor", "d"),
    (0x160, "highlightExpSatFactor", "d"),
    (0x168, "highlightCompSatFactor", "d"),
    (0x170, "satSmoothingWidth", "d"),
    (0x178, "shadowDesatDim", "d"),
    (0x180, "shadowMinDesat", "d"),
    (0x188, "shadowDesatLumAdj", "d"),
    (0x190, "shadowDesatBlend", "d"),
    (0x198, "shadowExpTxtFactor", "d"),
    (0x1A0, "shadowCompTxtFactor", "d"),
    (0x1A8, "highlightExpTxtFactor", "d"),
    (0x1B0, "highlightCompTxtFactor", "d"),
    (0x1B8, "txtSmoothingWidth", "d"),
    (0x1C0, "txtAmpLimit", "d"),
    (0x1C8, "filterPolicy", "i"),
    (0x1D0, "blackNoiseSigmaMult", "d"),
    (0x1D8, "blackNoiseSuppStops", "d"),
    (0x1E0, "blackNoiseStdDev", "d"),
    (0x1E8, "minBlackOffset", "d"),
    (0x1F0, "maxWhiteOffset", "d"),
    (0x1F8, "maxExpDelta", "d"),
    (0x200, "maxCompDelta", "d"),
    (0x208, "bUseWhitePtCompression", "i"),
    (0x210, "whiteSatLowerLimit", "d"),
    (0x218, "whiteSatUpperLimit", "d"),
    (0x220, "blackPointRatio", "d"),
    (0x228, "shadowDeltaGain", "d"),
    (0x230, "highlightDeltaGain", "d"),
)

WORK_SIZE = 0x800
N_TONE = 4096


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    """Minimal PakonIMAu.dll emulator with a bump heap and CRT stubs."""

    def __init__(self, pe: bytes):
        self.pe = pe
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self._load()
        uc.mem_map(0, 0x1000)            # flat FS base -> fs:[0] SEH head
        uc.mem_map(STACK, STACK_SZ)
        uc.mem_map(HEAP, HEAP_SZ)
        uc.mem_map(SCRATCH, 0x10000)
        uc.mem_map(RET_MAGIC & ~0xFFF, 0x1000)
        uc.mem_write(RET_MAGIC, b"\xC3")
        uc.mem_write(0, struct.pack("<I", 0xFFFFFFFF))
        self.brk = HEAP + 0x1000
        self._stub_next = SCRATCH + 0x1000
        self.faults: list[str] = []
        uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)
        self.hook(VA_OP_NEW, lambda e, a: (e.alloc(max(e.r32(a), 4)), 0))
        self.hook(VA_OP_DELETE, lambda e, a: (None, 0))
        self.hook(VA_OP_DELETE_ARR, lambda e, a: (None, 0))
        mm = self.stub()
        uc.mem_write(IAT_MEMMOVE, struct.pack("<I", mm))

        def _memmove(e, args):
            dst, src, n = e.r32(args), e.r32(args + 4), e.r32(args + 8)
            if n:
                e.uc.mem_write(dst, bytes(e.uc.mem_read(src, n)))
            return dst, 0

        self.hook(mm, _memmove)

    def _load(self) -> None:
        pe = self.pe
        e = struct.unpack_from("<I", pe, 0x3C)[0]
        ns = struct.unpack_from("<H", pe, e + 6)[0]
        osz = struct.unpack_from("<H", pe, e + 20)[0]
        opt = e + 24
        size_image = struct.unpack_from("<I", pe, opt + 56)[0]
        self.uc.mem_map(IMAGE_BASE, _align(size_image))
        self.uc.mem_write(IMAGE_BASE, pe[:0x1000])
        so = opt + osz
        for i in range(ns):
            o = so + i * 40
            vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
            if rsz == 0 or raddr == 0:
                continue
            d = pe[raddr:raddr + rsz]
            if len(d) < vsz:
                d += b"\x00" * (vsz - len(d))
            self.uc.mem_write(IMAGE_BASE + va, d[:max(vsz, rsz)])

    # -- memory ------------------------------------------------------------
    def alloc(self, size: int, fill: bytes | None = None) -> int:
        p = self.brk
        self.brk = (self.brk + size + 0x40) & ~0xF
        if self.brk >= HEAP + HEAP_SZ:
            raise RuntimeError("emu heap exhausted")
        self.uc.mem_write(p, b"\x00" * size)
        if fill:
            self.uc.mem_write(p, fill)
        return p

    def stub(self) -> int:
        p = self._stub_next
        self._stub_next += 0x10
        self.uc.mem_write(p, b"\xC3")
        return p

    def wi32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<i", int(v)))

    def wu32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", int(v) & 0xFFFFFFFF))

    def wf64(self, a: int, v: float) -> None:
        self.uc.mem_write(a, struct.pack("<d", float(v)))

    def ri32(self, a: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(a, 4))[0]

    def r32(self, a: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def rf64(self, a: int) -> float:
        return struct.unpack("<d", self.uc.mem_read(a, 8))[0]

    # -- hooks -------------------------------------------------------------
    def hook(self, va: int, fn) -> None:
        def cb(uc, address, size, _u):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            res = fn(self, esp + 4)
            eax, pop = res if isinstance(res, tuple) else (res, 0)
            if eax is not None:
                uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)

        self.uc.hook_add(UC_HOOK_CODE, cb, begin=va, end=va)

    def watch(self, va: int, fn) -> None:
        """Observe-only hook (does not alter control flow)."""
        self.uc.hook_add(
            UC_HOOK_CODE, lambda uc, a, s, u: fn(self), begin=va, end=va
        )

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"bad mem access={access} addr={address:#x} eip="
            f"{uc.reg_read(UC_X86_REG_EIP):#x}"
        )
        return False

    def fake_vtable(self, nslots: int = 40) -> int:
        vt = self.alloc(4 * nslots)
        for i in range(nslots):
            s = self.stub()
            self.wu32(vt + 4 * i, s)
            self.hook(s, lambda e, a: (1, 0))
        return vt

    # -- calling -----------------------------------------------------------
    def call(self, va: int, args=(), ecx: int | None = None) -> int:
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
            uc.emu_start(va, RET_MAGIC, timeout=0, count=400_000_000)
        except UcError as ex:
            raise RuntimeError(
                f"emu {va:#x} eip={uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
                + ("; " + "; ".join(self.faults[:2]) if self.faults else "")
            ) from ex
        if self.faults:
            raise RuntimeError(f"emu {va:#x} faults: {self.faults[:2]}")
        return uc.reg_read(UC_X86_REG_EAX)


def make_image(emu: Emu, planes, height: int, width: int) -> int:
    """Iem image handle over int16 planes.

    ``image+4`` → planeset; ``ps+0x14`` rows, ``+0x18`` cols, ``+0x1c`` nPlanes,
    ``+0x20`` → container whose entry ``k`` is at ``+8k+4`` (cites ``0x1027b3c0``
    ``0x1027b411``/``0x1027b449``, accessors ``0x104d48d0/e0/f0``).
    Plane: ``+0x4`` refcount, ``+0xc`` type desc, ``+0x10`` rows, ``+0x14`` cols,
    ``+0x18`` row-pointer table (cites ``0x104d2e70/e80``, ``0x104ea7f0``).
    """
    vt = emu.fake_vtable()
    tdesc = emu.alloc(0x20)
    emu.wi32(tdesc, 3)                       # I16 (0x104ea940 case -> 0x104ea7f0)
    emu.wu32(VA_I16_TYPE_SINGLETON, tdesc)   # CRT init never ran
    ps = emu.alloc(0x40)
    arr = emu.alloc(8 * len(planes) + 16)
    for k, p in enumerate(planes):
        a = np.ascontiguousarray(np.asarray(p, dtype=np.int16))
        data = emu.alloc(a.nbytes + 64, a.tobytes())
        rows = emu.alloc(4 * height + 16)
        for y in range(height):
            emu.wu32(rows + 4 * y, data + y * width * 2)
        obj = emu.alloc(0x40)
        emu.wu32(obj + 0x00, vt)
        emu.wu32(obj + 0x04, 1)
        emu.wu32(obj + 0x0C, tdesc)
        emu.wi32(obj + 0x10, height)
        emu.wi32(obj + 0x14, width)
        emu.wu32(obj + 0x18, rows)
        emu.wu32(arr + 8 * k + 4, obj)
    emu.wi32(ps + 0x14, height)
    emu.wi32(ps + 0x18, width)
    emu.wi32(ps + 0x1C, len(planes))
    emu.wu32(ps + 0x20, arr)
    img = emu.alloc(0x20)
    emu.wu32(img + 4, ps)
    return img


def pack_work(emu: Emu, dpi: shasta.ShastaDpi) -> int:
    """Allocate + fill a work object from a shipped dpi via SHASTA_WORK_LAYOUT."""
    work = emu.alloc(WORK_SIZE)
    raw = dpi.raw
    for off, key, kind in SHASTA_WORK_LAYOUT:
        v = raw.get(key)
        if v is None:
            continue
        if kind == "i":
            if v.strip().lower() in ("true", "false"):
                emu.wi32(work + off, 1 if v.strip().lower() == "true" else 0)
            else:
                emu.wi32(work + off, int(float(v)))
        else:
            emu.wf64(work + off, float(v))
    return work


def dll_analyze_7be10(
    pe: bytes,
    dpi: shasta.ShastaDpi,
    rgb: np.ndarray,
    blockavg: np.ndarray,
    codes: tuple[int, int, int, int],
) -> tuple[dict, np.ndarray, list[int], list[int]]:
    """Run the real ``0x1027be10`` then the real builder ``0x10293ee0``.

    Returns (work-field snapshot, DLL histogram counts, toneLut, blackNoise).
    """
    emu = Emu(pe)
    h, w = rgb.shape[:2]
    bh, bw = blockavg.shape[:2]
    image = make_image(emu, [rgb[:, :, c] for c in range(3)], h, w)
    block = make_image(emu, [blockavg[:, :, c] for c in range(3)], bh, bw)
    work = pack_work(emu, dpi)

    n_bins = int(round(dpi.max_value)) + 1
    grabbed: list[np.ndarray] = []

    def _grab(e: Emu) -> None:
        begin = e.r32(work + 0x390)
        if begin and not grabbed:
            grabbed.append(
                np.frombuffer(
                    bytes(e.uc.mem_read(begin, n_bins * 4)), dtype=np.int32
                ).copy()
            )

    emu.watch(VA_HIST_FILLED, _grab)
    emu.call(VA_7BE10, [image, block, *codes], ecx=work)

    snap = {}
    for off in (0x2B0, 0x2B4, 0x2B8, 0x2BC, 0x2C0, 0x2C4, 0x2C8, 0x2CC, 0x2D0,
                0x2D4, 0x2D8, 0x2DC, 0x2E0, 0x2E4, 0x2E8, 0x2EC, 0x2F0,
                0x2F4, 0x2F8, 0x2FC, 0x300, 0x328, 0x32C, 0x330, 0x334, 0x338):
        snap[off] = emu.ri32(work + off)
    for off in (0x308, 0x310, 0x318, 0x320, 0x340, 0x368, 0x370, 0x378, 0x380):
        snap[off] = emu.rf64(work + off)

    # --- builder 0x10293ee0 on the work object analyze just produced ---
    tone = emu.alloc(N_TONE * 4)
    bn = emu.alloc(N_TONE * 4)
    emu.wu32(work + 0x3AC, 0)
    emu.wu32(work + 0x3B0, tone)
    emu.wu32(work + 0x3B4, tone + N_TONE * 4)
    emu.wu32(work + 0x3BC, 0)
    emu.wu32(work + 0x3C0, bn)
    emu.wu32(work + 0x3C4, bn + N_TONE * 4)

    def _vec_fill(e: Emu, args):
        count, _fill = e.r32(args), e.r32(args + 4)
        this = e.uc.reg_read(UC_X86_REG_ECX)
        begin = e.r32(this + 4)
        if begin and count > 0:
            e.uc.mem_write(begin, b"\x00" * (count * 4))
        return None, 8

    emu.hook(VA_VEC_FILL, _vec_fill)
    arg = emu.ri32(work + 0x48) - emu.ri32(work + 0x2B0)
    emu.call(VA_93EE0, [arg], ecx=work)
    tone_out = list(
        struct.unpack(f"<{N_TONE}i", emu.uc.mem_read(tone, N_TONE * 4))
    )
    bn_out = list(struct.unpack(f"<{N_TONE}i", emu.uc.mem_read(bn, N_TONE * 4)))
    counts = grabbed[0] if grabbed else np.zeros(n_bins, np.int32)
    return snap, counts, tone_out, bn_out


def dll_7b3c0(
    pe: bytes, rgb: np.ndarray, lo: int, hi: int, dpi: shasta.ShastaDpi
) -> tuple[float, float, float, float]:
    emu = Emu(pe)
    h, w = rgb.shape[:2]
    image = make_image(emu, [rgb[:, :, c] for c in range(3)], h, w)
    work = pack_work(emu, dpi)
    emu.wi32(work + 0x2EC, lo)
    emu.wi32(work + 0x2F0, hi)
    emu.call(VA_7B3C0, [image], ecx=work)
    return (
        emu.rf64(work + 0x310),
        emu.rf64(work + 0x318),
        emu.rf64(work + 0x320),
        emu.rf64(work + 0x340),
    )


# ---------------------------------------------------------------------------
# Test images
# ---------------------------------------------------------------------------
def _case_images(seed: int, kind: str):
    rng = np.random.default_rng(seed)
    h, w = 64, 64
    img = np.zeros((h, w, 3), dtype=np.int16)
    if kind == "uniform":
        for c in range(3):
            img[:, :, c] = rng.integers(200, 3500, (h, w))
    elif kind == "dark":                      # near-black, crushed shadow case
        for c in range(3):
            img[:, :, c] = rng.integers(0, 400, (h, w))
    elif kind == "bright":                    # near-white
        for c in range(3):
            img[:, :, c] = rng.integers(3600, 4095, (h, w))
    elif kind == "saturated":                 # heavy channel imbalance
        img[:, :, 0] = rng.integers(1400, 1700, (h, w))
        img[:, :, 1] = rng.integers(80, 240, (h, w))
        img[:, :, 2] = rng.integers(3200, 3900, (h, w))
    elif kind == "bimodal":
        for c in range(3):
            a = rng.integers(150, 500, (h, w // 2))
            b = rng.integers(2800, 3900, (h, w - w // 2))
            img[:, :, c] = np.concatenate([a, b], axis=1)
    elif kind == "flat":                      # degenerate: single code
        img[:, :, :] = 1618
    blk = img[::8, ::8, :].copy()
    return img, blk


CASES = [
    ("uniform", 11, (1550, 800, 1200, 3000)),
    ("dark", 12, (1618, 120, 260, 3000)),
    ("bright", 13, (1618, 3400, 3600, 3000)),
    ("saturated", 14, (1618, 300, 900, 3000)),
    ("bimodal", 15, (1618, 400, 700, 3000)),
    ("flat", 16, (1618, 1500, 1600, 3000)),
    # adversarial aim orders: mid_hi < mid_lo, grey above white
    ("uniform", 17, (1618, 1400, 900, 3000)),
    ("bimodal", 18, (2900, 200, 600, 2400)),
]


def main() -> int:
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    dpi_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DPI
    pe = dll.read_bytes()
    dpi = shasta.ShastaDpi.load(dpi_path)
    print(f"DLL {dll}\nDPI {dpi_path} key={dpi.key}")
    print(
        f"  ANALYZE_INNER={shasta.SHASTA_ANALYZE_INNER_PORTED} "
        f"WORK_LAYOUT={shasta.SHASTA_WORK_LAYOUT_PORTED} "
        f"IEM_HIST_FILL={shasta.SHASTA_IEM_HIST_FILL_PORTED}"
    )
    bad = 0

    # --- leaf: 0x1027b3c0 on a real plane set --------------------------
    for kind, seed, _ in CASES[:5]:
        img, _ = _case_images(seed, kind)
        for lo, hi in ((1000, 3000), (0, 4095), (2000, 2000)):
            d = dll_7b3c0(pe, img, lo, hi, dpi)
            hst = shasta.image_range_means_7b3c0(
                img, lo, hi,
                use_white_pt=dpi.use_white_pt_compression,
                white_sat_lower=dpi.white_sat_lower_limit,
                white_sat_upper=dpi.white_sat_upper_limit,
                code_values_per_button=dpi.code_values_per_button,
            )
            got = (hst.mean_310, hst.mean_318, hst.hypot_320, hst.p340)
            ok = all(a == b for a, b in zip(got, d))
            bad += not ok
            print(
                f"  7b3c0 {kind:9s} [{lo},{hi}] "
                f"{'OK' if ok else f'FAIL host={got} dll={d}'}"
            )

    # --- assembled whole: 0x1027be10 + builder 0x10293ee0 ---------------
    for kind, seed, codes in CASES:
        img, blk = _case_images(seed, kind)
        snap, dll_counts, dll_tone, dll_bn = dll_analyze_7be10(
            pe, dpi, img, blk, codes
        )

        # Iem histogram fill 0x104ea940/0x104ea7f0 vs host counts
        n_bins = int(round(dpi.max_value)) + 1
        host_counts = shasta.hist_counts_from_plane0(img[:, :, 0], n_bins)
        hist_ok = bool(np.array_equal(host_counts, dll_counts))
        bad += not hist_ok
        print(f"  iem-hist {kind:9s} {'OK' if hist_ok else 'FAIL'}")

        # Host orchestrator
        work = shasta.analyze_work_from_dpi(dpi)
        work.code_start, work.mid_lo, work.mid_hi, work.code_white = codes
        shasta.analyze_inner_7be10(work, dpi, img, blockavg_rgb=blk)
        host = {
            0x2B0: work.code_start, 0x2B4: work.mid_lo, 0x2B8: work.mid_hi,
            0x2BC: work.code_white,
            0x2E4: work.code_2e4, 0x2E8: work.code_2e8,
            0x2EC: work.code_2ec, 0x2F0: work.code_2f0,
            0x2F4: work.code_2f4, 0x2F8: work.code_2f8,
            0x2FC: work.code_2fc, 0x300: work.code_300,
            0x328: work.off_328, 0x32C: work.code_32c,
            0x330: work.code_330, 0x334: work.code_334, 0x338: work.code_338,
            0x340: work.p340, 0x368: work.adj_368, 0x370: work.adj_370,
            0x378: work.adj_378, 0x380: work.adj_380,
        }
        diffs = [
            (hex(o), host[o], snap[o]) for o in host if host[o] != snap[o]
        ]
        ok = not diffs
        bad += not ok
        print(f"  7be10    {kind:9s} codes={codes} {'OK' if ok else 'FAIL'}")
        for d in diffs[:6]:
            print(f"      +{d[0]}: host={d[1]} dll={d[2]}")

        # Full toneLut through the real builder
        tone, bn, cap = shasta.assemble_tone_lut(
            work, run_935d0=False, scale_adjs=False, run_prep=True,
            prep_inputs=shasta.dpi_prep_inputs(dpi),
        )
        hi_i = int(work.code_max)
        mism_t = [i for i in range(hi_i + 1) if int(tone[i]) != dll_tone[i]]
        mism_b = [i for i in range(hi_i) if int(bn[i]) != dll_bn[i]]
        ok = not mism_t and not mism_b
        bad += not ok
        print(
            f"  toneLut  {kind:9s} mism_tone={len(mism_t)} "
            f"mism_bn={len(mism_b)} {'OK' if ok else 'FAIL'}"
        )
        for i in mism_t[:4]:
            print(f"      tone[{i}] host={int(tone[i])} dll={dll_tone[i]}")

    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
