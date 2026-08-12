#!/usr/bin/env python3
"""Golden ``cna`` (``AnsCnaCapabilityImpl``) vs PakonIMAu.dll (Unicorn).

Same shape and the same conventions as ``pakon_shasta_curve_golden.py`` and
``pakon_autotone_shell_golden.py``: ``Uc(UC_ARCH_X86, UC_MODE_32)``, the PE
loaded at ``IMAGE_BASE = 0x10000000``, a bump-allocator heap, CRT stubs for
``operator new``/``delete``/``memmove``, and ``hook()`` interception.  The
``Emu`` class is **imported** from the Phase-1 harness rather than copied, so
there is exactly one emulator in the tree.

WHAT RUNS FOR REAL
==================
Every function under test is the vendor's own code, executed start to finish:

    0x104ffe44  _ftol2                      -> pakon_cna.ftol2
    0x1022c340  laplacian                   -> pakon_cna.laplacian
    0x1022c8f0  gaussian smooth             -> pakon_cna.gauss_smooth
    0x1022c3e0  peak of 2nd difference      -> pakon_cna.peak_second_difference
    0x1022ca80  moments + smooth + resample -> pakon_cna.hist_resample
    0x1022d970  allocateMemory              -> pakon_cna.buffer_sizes
    0x1022ddc0  analyzeImage (to 0x1022e23e)-> pakon_cna.analyze_image_threshold

Only ``operator new[]`` / ``operator delete[]`` are stubbed, because the PE is
loaded unbound and CRT init never runs; ``new`` becomes the bump allocator and
``delete`` a no-op.  No cna arithmetic is stubbed anywhere.

THE POISON TEST
===============
Phase 1 caught layout mistakes by filling struct windows with sentinel dwords
that name their own offset.  The same technique is used here in two places:

* ``allocateMemory``'s fifteen buffers are poisoned with ``0xDEADxxxx`` before
  ``analyzeImage`` runs, so a port that reads a buffer the vendor never writes
  produces garbage instead of a coincidentally-correct zero.
* every scratch buffer the port does **not** claim to model is poisoned with a
  distinct pattern and re-read afterwards, so a silently-wrong buffer
  assignment in ``buffer_sizes`` shows up as a size mismatch rather than
  passing because two buffers happened to be the same length.

X87 PRECISION
=============
MSVC's CRT sets the x87 control word to ``0x027f`` (53-bit significand) on
Win32; QEMU/Unicorn start at ``0x037f`` (64-bit).  Since the port keeps
register values in Python ``float`` (binary64), ``0x027f`` is both the more
faithful setting and the one the port can match exactly, so the harness sets it
before every call.  ``--fpcw 0x037f`` re-runs everything at the emulator
default and reports which cases move -- that difference is a real property of
the vendor code, not a porting artefact, and is printed rather than hidden.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_cna_golden.py [dll] [--fpcw 0x27f]``

Add ``--selftest`` to run the whole suite once per deliberate defect and
require each to be rejected.  That is roughly 15x the runtime -- about 25
minutes -- because the suite runs full 5000-bin analyses; it is a
before-you-trust-the-flags check, not something to run on every edit.  Use
``python3 -u`` if you pipe it, or Python block-buffers and you see nothing
until it finishes.

The DLL is not in the repo.  Extract it with
``python3 tools/re/reachability.py extract`` (default ``/tmp/pakon_re``).
"""
from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

from unicorn import UcError, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EBX,
    UC_X86_REG_EAX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
    UC_X86_REG_FPCW,
)

import pakon_cna as cna
from pakon_autotone_shell_golden import Emu, RET_MAGIC, STACK, STACK_SZ

DEFAULT_DLL = Path("/tmp/pakon_re/PakonIMAu.dll")

VA_FTOL2 = cna.CRT_FTOL2
VA_NEW = cna.CRT_NEW_ARRAY
VA_DELETE = cna.CRT_DELETE_ARRAY
VA_LAPLACIAN = cna.CNA_LAPLACIAN
VA_GAUSS = cna.CNA_GAUSS_SMOOTH
VA_PEAK = cna.CNA_PEAK_SEARCH
VA_RESAMPLE = cna.CNA_HIST_RESAMPLE
VA_ALLOC = cna.CNA_ALLOCATE_MEMORY
VA_ANALYZE_IMAGE = cna.CNA_ANALYZE_IMAGE

#: ``0x1022e23e`` — the first instruction after the threshold relaxation loop
#: has settled.  Everything the port models is decided by here.
VA_AFTER_THRESHOLD = 0x1022E23E
#: ``0x1022e21c`` — the identity-LUT early return the relaxation loop falls into
#: when it runs out of threshold.
VA_GAVE_UP = 0x1022E21C
#: ``0x1022e865`` — the first instruction of the elmo block; ``0x1022e9b0`` is
#: where all three of its exits rejoin.
VA_ELMO_START = 0x1022E865
VA_ELMO_END = 0x1022E9B0

FPCW_MSVC = 0x027F
FPCW_QEMU = 0x037F

POISON = 0xDEAD0000


class CnaEmu(Emu):
    """``Emu`` plus the two CRT allocators cna needs and an x87 control word."""

    def __init__(self, pe: bytes, fpcw: int = FPCW_MSVC):
        super().__init__(pe)
        self.fpcw = fpcw
        #: Byte size of every ``operator new[]`` the run performs, in call
        #: order.  ``allocateMemory``'s fifteen sizes are checked against
        #: ``buffer_sizes`` through this, not through the resulting pointers --
        #: two buffers of equal length would otherwise be interchangeable.
        self.new_sizes: list[int] = []
        # ``operator new[]`` / ``delete[]`` are the only CRT calls in cna's own
        # code.  ``Emu`` already hooks ``0x104ffdd0`` and ``0x104ffe3e`` (its
        # ``VA_OP_DELETE`` / ``VA_OP_DELETE_ARR``), and **a second hook at the
        # same VA is not additive**: both callbacks run, each pops a dword and
        # rewrites EIP, so the second reads the callee's *argument* as a return
        # address and jumps into the heap.  A duplicate ``delete[]`` hook did
        # exactly that here, and it surfaced only on the ``cap+0xe == 0`` path
        # because that is the only one that frees anything.
        #
        # So: hook ``new`` at cna's own thunk ``0x104ffd78`` (which jmps to the
        # ``0x104ffd53`` the base hooks -- the base's never fires, because EIP
        # has already moved), and leave ``delete`` entirely to the base.
        self.hook(VA_NEW, self._op_new)

    @staticmethod
    def _op_new(e: "CnaEmu", args: int):
        sz = e.r32(args)
        e.new_sizes.append(sz)
        return e.alloc(max(sz, 4)), 0

    def call(self, va, args=(), ecx=None):
        self.uc.reg_write(UC_X86_REG_FPCW, self.fpcw)
        return super().call(va, args, ecx)

    # -- typed memory ------------------------------------------------------
    def poison(self, addr: int, n_bytes: int, tag: int) -> None:
        for off in range(0, n_bytes, 4):
            self.wu32(addr + off, (POISON | tag << 8 | (off >> 2)) & 0xFFFFFFFF)

    def wf32(self, a: int, v: float) -> None:
        self.uc.mem_write(a, struct.pack("<f", v))

    def rf32(self, a: int) -> float:
        return struct.unpack("<f", self.uc.mem_read(a, 4))[0]

    def wi16(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<h", v))

    def ri16(self, a: int) -> int:
        return struct.unpack("<h", self.uc.mem_read(a, 2))[0]

    def arr_i16(self, a: int, n: int) -> list[int]:
        raw = bytes(self.uc.mem_read(a, 2 * n))
        return list(struct.unpack(f"<{n}h", raw))

    def arr_i32(self, a: int, n: int) -> list[int]:
        raw = bytes(self.uc.mem_read(a, 4 * n))
        return list(struct.unpack(f"<{n}i", raw))

    def arr_f32(self, a: int, n: int) -> list[float]:
        raw = bytes(self.uc.mem_read(a, 4 * n))
        return list(struct.unpack(f"<{n}f", raw))

    def put_i16(self, vals) -> int:
        vals = list(vals)
        p = self.alloc(max(2 * len(vals), 4))
        if vals:
            self.uc.mem_write(p, struct.pack(f"<{len(vals)}h", *vals))
        return p

    def put_i32(self, vals) -> int:
        vals = list(vals)
        p = self.alloc(max(4 * len(vals), 4))
        if vals:
            self.uc.mem_write(p, struct.pack(f"<{len(vals)}i", *vals))
        return p

    def put_f32(self, vals) -> int:
        vals = list(vals)
        p = self.alloc(max(4 * len(vals), 4))
        if vals:
            self.uc.mem_write(p, struct.pack(f"<{len(vals)}f", *vals))
        return p


# ---------------------------------------------------------------------------
# _ftol2 -- needs a float already on the x87 stack, so it gets a thunk
# ---------------------------------------------------------------------------


def dll_ftol2(emu: CnaEmu, x: float) -> int:
    """``fld qword [src]; call 0x104ffe44; ret`` — the real truncation."""
    src = emu.alloc(8)
    emu.uc.mem_write(src, struct.pack("<d", x))
    code = emu.alloc(0x40)
    body = (b"\xDD\x05" + struct.pack("<I", src)            # fld qword [src]
            + b"\xE8" + struct.pack("<i", VA_FTOL2 - (code + 11))
            + b"\xC3")
    emu.uc.mem_write(code, body)
    emu.uc.reg_write(UC_X86_REG_FPCW, emu.fpcw)
    esp = STACK + STACK_SZ - 0x30000
    esp -= 4
    emu.uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.faults = []
    emu.uc.emu_start(code, RET_MAGIC, timeout=0, count=10_000_000)
    lo = emu.uc.reg_read(UC_X86_REG_EAX)
    hi = emu.uc.reg_read(UC_X86_REG_EDX)
    v = (hi << 32) | lo
    return v - (1 << 64) if v & (1 << 63) else v


# ---------------------------------------------------------------------------
# per-function drivers
# ---------------------------------------------------------------------------


def dll_laplacian(emu: CnaEmu, lum, width, height):
    src = emu.put_i16(lum)
    n_out = max((height - 2) * (width - 2), 0)
    out = emu.alloc(max(2 * n_out, 4) + 16)
    emu.poison(out, max(2 * n_out, 4), 0x11)
    emu.call(VA_LAPLACIAN, [width, height, out], ecx=src)
    return emu.arr_i16(out, n_out)


def _params_blob(emu: CnaEmu, p: cna.CnaParams) -> int:
    return emu.alloc(0x80, cna.params_to_bytes(p))


def dll_gauss(emu: CnaEmu, src, n, sigma, p: cna.CnaParams):
    """``0x1022c8f0(params, results, in, n, sigma, out)``.

    ``results+0x30`` and ``+0x34`` are the two scratch buffers the vendor uses
    for the padded copy and the kernel; they are sized here from
    ``buffer_sizes`` and poisoned first.
    """
    par = _params_blob(emu, p)
    d = cna.gauss_half_width(sigma, p.smoothingSizeFactor)
    pad = emu.alloc(4 * (n + 2 * d) + 64)
    kern = emu.alloc(4 * (2 * d + 1) + 64)
    emu.poison(pad, 4 * (n + 2 * d), 0x21)
    emu.poison(kern, 4 * (2 * d + 1), 0x22)
    res = emu.alloc(0x60)
    emu.wu32(res + 0x30, pad)
    emu.wu32(res + 0x34, kern)
    a_in = emu.put_f32(src)
    a_out = emu.alloc(max(4 * n, 4) + 64)
    emu.poison(a_out, max(4 * n, 4), 0x23)
    sig = emu.alloc(4)
    emu.wf32(sig, sigma)
    emu.call(VA_GAUSS, [par, res, a_in, n,
                        struct.unpack("<I", struct.pack("<f", sigma))[0],
                        a_out])
    return emu.arr_f32(a_out, n), emu.arr_f32(kern, 2 * d + 1)


def dll_peak(emu: CnaEmu, f, start, limit):
    a = emu.put_f32(f)
    out = emu.alloc(8)
    emu.wu32(out, 0xCAFEBABE)
    uc = emu.uc
    uc.reg_write(UC_X86_REG_FPCW, emu.fpcw)
    esp = STACK + STACK_SZ - 0x20000
    blob = struct.pack("<II", limit, out)
    esp -= len(blob)
    uc.mem_write(esp, blob)
    esp -= 4
    uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, a)
    uc.reg_write(UC_X86_REG_EAX, start)
    emu.faults = []
    uc.emu_start(VA_PEAK, RET_MAGIC, timeout=0, count=200_000_000)
    if emu.faults:
        raise RuntimeError(f"peak faults {emu.faults[:2]}")
    return emu.ri32(out)


def dll_resample(emu: CnaEmu, p: cna.CnaParams, hist, n, pivot, scale, gain):
    par = _params_blob(emu, p)
    out_sigma = cna.f32(cna.f32(math.sqrt(max(_moment_var(hist, n), 0.0)))
                        * p.blend)
    out_sigma = min(max(out_sigma, p.minGaussSigma), p.maxGaussSigma)
    d = cna.gauss_half_width(out_sigma, p.smoothingSizeFactor)
    npad = n + 2 * d
    # ``0x1022ca80`` calls the gaussian with ``n = npad``, so its own padded
    # scratch is ``npad + 2d`` floats, not ``npad`` -- exactly the sizing
    # ``allocateMemory`` encodes as ``2*hw2 + (histSize + 2*hw1)``.  Getting
    # this wrong lets the DLL run off the end of the buffer and silently
    # corrupt the next allocation, which is how the first version of this
    # harness produced a real-looking but wrong reference.
    n_pad_buf = npad + 2 * d
    n_kern = 2 * d + 1
    res = emu.alloc(0x60)
    pad = emu.alloc(4 * n_pad_buf + 256)
    kern = emu.alloc(4 * n_kern + 256)
    work = emu.alloc(4 * npad + 256)
    emu.poison(pad, 4 * n_pad_buf, 0x31)
    emu.poison(kern, 4 * n_kern, 0x32)
    emu.poison(work, 4 * npad, 0x33)
    emu.wu32(res + 0x30, pad)
    emu.wu32(res + 0x34, kern)
    emu.wu32(res + 0x38, work)
    a_hist = emu.put_i32(hist)
    a_out = emu.alloc(max(4 * n, 4) + 64)
    emu.poison(a_out, max(4 * n, 4), 0x34)
    p_in = emu.alloc(4)
    p_out = emu.alloc(4)
    emu.wu32(p_in, 0)
    emu.wu32(p_out, 0)
    fbits = lambda v: struct.unpack("<I", struct.pack("<f", v))[0]  # noqa: E731
    emu.call(VA_RESAMPLE, [par, fbits(scale), fbits(gain), res, a_hist, n,
                           pivot, p_in, p_out, a_out])
    return emu.rf32(p_in), emu.rf32(p_out), emu.arr_i32(a_out, n)


def _moment_var(hist, n):
    """Host-side pre-estimate of sigma, used only to size the DLL's scratch."""
    total = sum(hist[:n]) or 1
    s1 = sum(i * hist[i] for i in range(n))
    s2 = sum(i * i * hist[i] for i in range(n))
    mean = s1 / total
    return s2 / total - mean * mean


def dll_alloc(emu: CnaEmu, p: cna.CnaParams, width, height):
    """``0x1022d970(sret, width, height)`` with ``ecx`` = the Impl.

    ``operator new[]`` is intercepted so the byte size of every one of the
    fifteen allocations is recorded in call order — that record is what
    ``buffer_sizes`` is checked against, not just the resulting pointers.
    """
    impl = emu.alloc(0x400)
    emu.uc.mem_write(impl + cna.PARAMS_AT, cna.params_to_bytes(p))
    emu.new_sizes.clear()
    sret = emu.alloc(0x10)
    emu.call(VA_ALLOC, [sret, width, height], ecx=impl)
    sizes = list(emu.new_sizes)
    ptrs = {off: emu.r32(impl + off) for off in
            (0x8C, 0x90, 0x94, 0xA4, 0xB8, 0xBC, 0xC0, 0xC4, 0xC8, 0xCC,
             0xD0, 0xD4, 0xD8, 0xDC)}
    return sizes, ptrs, impl


def dll_analyze_image_threshold(emu: CnaEmu, p: cna.CnaParams, img):
    """Run the real ``0x1022ddc0`` and stop at ``0x1022e23e`` / ``0x1022e21c``.

    Both stop points are on the vendor's own control flow: ``0x1022e23e`` is
    where the threshold loop has settled with enough edge pixels, and
    ``0x1022e21c`` is the identity-LUT bail-out.  Registers are read at the stop
    instruction rather than reconstructed, so the comparison is against the
    machine's own state.
    """
    impl = emu.alloc(0x400)
    emu.uc.mem_write(impl + cna.PARAMS_AT, cna.params_to_bytes(p))
    sret = emu.alloc(0x10)
    emu.call(VA_ALLOC, [sret, img.width, img.height], ecx=impl)
    # Poison every working buffer so an unwritten read is loud, not silent.
    sizes = cna.buffer_sizes(p, img.width * img.height)
    for off, key, esz in ((0x8C, "lum_i16", 2), (0x90, "lum_hist_i32", 4),
                          (0x94, "lap_i16", 2), (0xA4, "edge_hist_i32", 4),
                          (0xC4, "scratch_c4_i32", 4),
                          (0xC8, "bucket_hist_i32", 4),
                          (0xCC, "scratch_cc_f32", 4),
                          (0xDC, "tone_lut_i16", 2)):
        emu.poison(emu.r32(impl + off), sizes[key] * esz, off & 0xFF)

    px = emu.put_i16(img.pixels)
    desc = emu.alloc(0x40)
    emu.wu32(desc + 0x0C, img.width)
    emu.wu32(desc + 0x10, img.height)
    emu.wu32(desc + 0x20, px)

    snap: dict = {}

    def stop(uc, address, size, _u):
        snap["eip"] = address
        snap["threshold"] = _sx32(uc.reg_read(UC_X86_REG_EAX))
        uc.emu_stop()

    def at_settled(uc, address, size, _u):
        snap["eip"] = address
        snap["gave_up"] = False
        uc.emu_stop()

    def at_gave_up(uc, address, size, _u):
        snap["eip"] = address
        snap["gave_up"] = True
        uc.emu_stop()

    h1 = emu.uc.hook_add(UC_HOOK_CODE, at_settled,
                         begin=VA_AFTER_THRESHOLD, end=VA_AFTER_THRESHOLD)
    h2 = emu.uc.hook_add(UC_HOOK_CODE, at_gave_up,
                         begin=VA_GAVE_UP, end=VA_GAVE_UP)
    sret2 = emu.alloc(0x10)
    try:
        emu.call(VA_ANALYZE_IMAGE, [sret2, desc], ecx=impl)
    except RuntimeError:
        if "eip" not in snap:
            raise
    emu.uc.hook_del(h1)
    emu.uc.hook_del(h2)

    n_bins = p.histSize
    n_pix = img.width * img.height
    n_lap = max((img.height - 2) * (img.width - 2), 0)
    res = {
        "gave_up": snap.get("gave_up"),
        "n_pixels": emu.ri32(impl + 0x88),
        "threshold": emu.ri32(impl + 0x98),
        "n_edge": emu.ri32(impl + 0x9C),
        "lum": emu.arr_i16(emu.r32(impl + 0x8C), n_pix),
        "lum_hist": emu.arr_i32(emu.r32(impl + 0x90), n_bins),
        "lap": emu.arr_i16(emu.r32(impl + 0x94), n_lap),
        "edge_hist": emu.arr_i32(emu.r32(impl + 0xA4), n_bins),
    }
    if snap.get("gave_up"):
        # 0x1022e230 fills the LUT after the bail-out point, so let it finish.
        res["tone_lut"] = None
    return res


def dll_elmo(emu: CnaEmu, p: cna.CnaParams, img, light_in: float,
             light_out: float):
    """Run the real ``0x1022ddc0`` and drive the elmo block's two gate inputs.

    ``0x1022e865`` is the first instruction of the elmo block; the harness
    hooks it, overwrites ``results.lightInSigma`` (``impl+0xac``) and
    ``results.lightOutSigma`` (``impl+0xb4``) with the values under test, and
    lets the vendor code proceed.  ``0x1022e9b0`` is where both gates and the
    count rejoin, so that is the stop point.  Everything in between —- the
    per-pixel saturation test, the ``fidiv`` percentage and the final compare —-
    is the DLL's own code.

    Driving the inputs this way is what makes both gates reachable: on a real
    frame ``lightInSigma <= lightOutSigma`` almost always holds and the block
    would never run.
    """
    impl = emu.alloc(0x400)
    emu.uc.mem_write(impl + cna.PARAMS_AT, cna.params_to_bytes(p))
    sret = emu.alloc(0x10)
    emu.call(VA_ALLOC, [sret, img.width, img.height], ecx=impl)
    px = emu.put_i16(img.pixels)
    desc = emu.alloc(0x40)
    emu.wu32(desc + 0x0C, img.width)
    emu.wu32(desc + 0x10, img.height)
    emu.wu32(desc + 0x20, px)

    seen: dict = {}

    def at_elmo(uc, address, size, _u):
        seen["reached"] = True
        emu.wf32(impl + 0xAC, light_in)     # results.lightInSigma
        emu.wf32(impl + 0xB4, light_out)    # results.lightOutSigma

    def at_end(uc, address, size, _u):
        seen["done"] = True
        uc.emu_stop()

    h1 = emu.uc.hook_add(UC_HOOK_CODE, at_elmo,
                         begin=VA_ELMO_START, end=VA_ELMO_START)
    h2 = emu.uc.hook_add(UC_HOOK_CODE, at_end,
                         begin=VA_ELMO_END, end=VA_ELMO_END)
    sret2 = emu.alloc(0x10)
    try:
        emu.call(VA_ANALYZE_IMAGE, [sret2, desc], ecx=impl)
    except RuntimeError:
        if not seen.get("done"):
            raise
    emu.uc.hook_del(h1)
    emu.uc.hook_del(h2)
    if not seen.get("reached"):
        raise RuntimeError("0x1022e865 never reached (threshold loop bailed "
                           "out?) — pick an image with real edge structure")
    return emu.rf32(impl + 0xE0), bool(emu.ru8(impl + 0xE4))


def dll_analyze_image(emu: CnaEmu, p: cna.CnaParams, img):
    """Run the real ``0x1022ddc0`` end to end and read back everything.

    Nothing is intercepted: ``allocateMemory`` runs, then ``analyzeImage``
    runs to its own ``ret``, and the comparison is against the resulting
    ``AnsCnaResults`` window plus the ``histSize``-entry ToneScaleLut it
    produced.  All fifteen buffers are poisoned first, so any slot the port
    thinks is written but the vendor leaves alone shows up as a poison value.
    """
    impl = emu.alloc(0x400)
    emu.uc.mem_write(impl + cna.PARAMS_AT, cna.params_to_bytes(p))
    sret = emu.alloc(0x10)
    emu.call(VA_ALLOC, [sret, img.width, img.height], ecx=impl)
    sizes = cna.buffer_sizes(p, img.width * img.height)
    for off, key, esz in ((0x8C, "lum_i16", 2), (0x90, "lum_hist_i32", 4),
                          (0x94, "lap_i16", 2), (0xA4, "edge_hist_i32", 4),
                          (0xC0, "resample_f32", 4),
                          (0xC4, "scratch_c4_i32", 4),
                          (0xC8, "bucket_hist_i32", 4),
                          (0xCC, "scratch_cc_f32", 4),
                          (0xD0, "scratch_d0_f32", 4),
                          (0xD4, "scratch_d4_f32", 4),
                          (0xD8, "scratch_d8_f32", 4),
                          (0xDC, "tone_lut_i16", 2)):
        emu.poison(emu.r32(impl + off), sizes[key] * esz, off & 0xFF)

    px = emu.put_i16(img.pixels)
    desc = emu.alloc(0x40)
    emu.wu32(desc + 0x0C, img.width)
    emu.wu32(desc + 0x10, img.height)
    emu.wu32(desc + 0x20, px)
    sret2 = emu.alloc(0x10)
    emu.call(VA_ANALYZE_IMAGE, [sret2, desc], ecx=impl)
    n_bins = p.histSize
    return {
        "status": emu.r32(sret2),
        "n_pixels": emu.ri32(impl + 0x88),
        "threshold": emu.ri32(impl + 0x98),
        "n_edge": emu.ri32(impl + 0x9C),
        "darkInSigma": emu.rf32(impl + 0xA8),
        "lightInSigma": emu.rf32(impl + 0xAC),
        "darkOutSigma": emu.rf32(impl + 0xB0),
        "lightOutSigma": emu.rf32(impl + 0xB4),
        "elmoPercent": emu.rf32(impl + 0xE0),
        "bElmoOccured": bool(emu.ru8(impl + 0xE4)),
        "tone_lut": emu.arr_i16(emu.r32(impl + 0xDC), n_bins),
        "bucket_hist": emu.arr_i32(emu.r32(impl + 0xC8),
                                   cna.idiv(n_bins, p.bucketSize)),
        "results": bytes(emu.uc.mem_read(impl + 0x88, 0x60)),
    }


def dll_validate(emu: CnaEmu, p: cna.CnaParams):
    """``0x1022ceb0(ecx = &params, ebx = &fieldIndex) -> 0 | -1``."""
    par = _params_blob(emu, p)
    out = emu.alloc(8)
    emu.wu32(out, 0xDEADDEAD)
    uc = emu.uc
    uc.reg_write(UC_X86_REG_FPCW, emu.fpcw)
    esp = STACK + STACK_SZ - 0x20000 - 4
    uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, par)
    uc.reg_write(UC_X86_REG_EBX, out)
    emu.faults = []
    uc.emu_start(cna.CNA_VALIDATE_PARAMS, RET_MAGIC, timeout=0,
                 count=10_000_000)
    rc = _sx32(uc.reg_read(UC_X86_REG_EAX))
    return rc, (emu.ri32(out) if rc else None)


def dll_cap_analyze(emu: CnaEmu, p: cna.CnaParams, img, *, cap_flag_e=0):
    """The shell's stage 1, run for real: ``0x10132dc0`` then ``0x10132ed0``.

    This is the strongest check in the file, because nothing between
    ``pakon_autotone``'s boundary and the tone scale is stubbed:

        0x10132dc0  the Cap wrapper Phase 1 ported (refcounts, cap+0xf)
          -> 0x1022ea50  AnsCnaCapabilityImpl::analyze
               -> 0x1022ceb0  validate  -> 0x1022d2e0 freeAll
               -> 0x1022d970  allocateMemory
               -> 0x1022ddc0  analyzeImage
               -> 0x1022d1a0  freeScratch (gated on cap+0xe)
        0x10132ed0  getResults -> 0x101320b0's 0x18-dword rep movsd

    and the 0x60 bytes that come back are compared against
    ``pakon_cna.analyze_to_results(...).raw`` field by field.  ``arg2`` -- the
    shell's ``[ebp+0x10]``, threaded verbatim into ``cna.acquire`` -- is the
    **image descriptor**; that is what makes the shell's third argument
    meaningful, and it was established by watching which slot ``0x1022ea50``
    dereferences, not assumed.
    """
    impl = emu.alloc(0x400)
    emu.uc.mem_write(impl + cna.PARAMS_AT, cna.params_to_bytes(p))
    vft = emu.alloc(0x40)
    for i in range(8):
        emu.wu32(vft + 4 * i, emu.stub())
    cap = emu.alloc(0x40)
    emu.wu32(cap, vft)
    emu.wu32(cap + 4, 0x01000000)
    emu.wu8(cap + 0x0C, 1)
    emu.wu8(cap + 0x0E, cap_flag_e)
    emu.wu32(cap + 0x10, impl)
    holder = emu.alloc(0x100)
    emu.wu32(holder, vft)
    emu.wu32(holder + 4, 0x01000000)
    emu.wu32(holder + 0x74, 0x01000000)
    px = emu.put_i16(img.pixels)
    desc = emu.alloc(0x40)
    emu.wu32(desc + 0x0C, img.width)
    emu.wu32(desc + 0x10, img.height)
    emu.wu32(desc + 0x20, px)

    thrown = {}
    emu.hook(0x10020AD0, lambda e, a: (thrown.setdefault("sret", e.r32(a)),
                                       0x18))
    sret = emu.alloc(0x10)
    emu.call(cna.CNA_CAP_ACQUIRE, [sret, holder, desc], ecx=cap)
    if thrown:
        return {"threw": True}
    res = emu.alloc(0x80)
    sret2 = emu.alloc(0x10)
    emu.call(cna.CNA_CAP_GET_RESULTS, [sret2, res], ecx=cap)
    raw = bytes(emu.uc.mem_read(res, 0x60))
    n_bins = p.histSize
    return {
        "threw": False,
        "raw": raw,
        "cap_ok_byte": emu.ru8(cap + 0x0F),
        "tone_lut": emu.arr_i16(struct.unpack_from("<I", raw, 0x54)[0], n_bins),
        "lum_hist": emu.arr_i32(struct.unpack_from("<I", raw, 0x08)[0], n_bins),
        "edge_hist": emu.arr_i32(struct.unpack_from("<I", raw, 0x1C)[0], n_bins),
    }


#: The ``AnsCnaResults`` fields ``analyze_to_results`` fills, and how to read
#: them.  The three pointer slots are compared for null-ness only, because the
#: port cannot produce real addresses.
RESULT_SCALARS = (
    (0x00, "<i", "nPixels"), (0x10, "<i", "threshold"),
    (0x14, "<i", "nEdgePixels"), (0x20, "<f", "darkInSigma"),
    (0x24, "<f", "lightInSigma"), (0x28, "<f", "darkOutSigma"),
    (0x2C, "<f", "lightOutSigma"), (0x58, "<f", "elmoPercent"),
)
RESULT_POINTERS = ((0x08, "LuminanceHist"), (0x1C, "EdgeHist"),
                   (0x54, "ToneScaleLut"))


def _sx32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

FTOL_CASES = [
    0.0, -0.0, 0.5, -0.5, 1.5, -1.5, 2.5, -2.5, 0.49999999, -0.49999999,
    0.9999999999, -0.9999999999, 1.0, -1.0, 3.7, -3.7, 1e6 + 0.5,
    -1e6 - 0.5, 4095.5, 4096.4999, 2147483646.5, -2147483647.5,
    1550.0, 0.1, -0.1, 1e-30, -1e-30, 123456789.75,
]

#: A small synthetic image whose luminance covers the histogram and produces a
#: laplacian with real structure -- a flat frame would make every branch of the
#: relaxation loop trivially reachable in the same way.
def make_image(w, h, seed=1):
    px = []
    for i in range(w * h):
        r = (i * 37 + seed * 11) % 3500 + 200
        g = (i * 53 + seed * 7) % 3300 + 150
        b = (i * 71 + seed * 13) % 3100 + 100
        if (i // w) % 5 == 0:
            r, g, b = r // 4, g // 4, b // 4        # dark bands -> edges
        px += [r, g, b]
    return cna.CnaImage(width=w, height=h, pixels=px)


def make_flat(w, h, value=1200):
    """A frame with no edge structure at all.

    Its laplacian is identically zero, so the relaxation loop can never reach
    ``minLapPixels`` and drives the threshold below ``minPosThreshold`` — the
    ``0x1022e21c`` identity-LUT bail-out.  Without this case that whole branch
    of ``analyze_image_threshold`` would be unexercised.
    """
    return cna.CnaImage(width=w, height=h, pixels=[value] * (3 * w * h))


def make_gradient(w, h):
    """A smooth ramp: a laplacian that is zero except at the row wrap."""
    px = []
    for i in range(w * h):
        v = 300 + (i % w) * 8
        px += [v, v, v]
    return cna.CnaImage(width=w, height=h, pixels=px)


IMAGE_CASES = [
    ("16x12 banded", 16, 12, 1),
    ("32x24 banded", 32, 24, 2),
    ("9x7 odd dims", 9, 7, 3),
    ("40x30 banded", 40, 30, 5),
]

def make_signed(w, h, seed=9):
    """Mixed-sign, high-chroma pixels.

    Two things only this case exercises:

    * the signed ``/3``, ``/4`` and ``/2`` in ``luminance_plane`` and
      ``elmo_detect`` with **negative** numerators, which is the only way to
      tell x86's truncate-toward-zero apart from Python's floor;
    * strongly non-neutral pixels, so ``elmo_detect``'s ``u`` and ``v`` are
      large and of both signs rather than clustered near zero.

    It must be run with non-zero channel shifts (``SHIFTED_PARAMS``) so the
    luminance takes the **clamped** branch at ``0x1022deea``: the unclamped
    branch would hand a negative index to ``inc dword [edi + eax*4]`` at
    ``0x1022df80``, which is a genuine out-of-bounds write in the vendor code
    and would corrupt emulated memory rather than test anything.
    """
    px = []
    for i in range(w * h):
        r = ((i * 131 + seed * 17) % 5000) - 2500
        g = ((i * 97 + seed * 29) % 5000) - 2500
        b = ((i * 173 + seed * 41) % 5000) - 2500
        px += [r, g, b]
    return cna.CnaImage(width=w, height=h, pixels=px)


#: Pixels whose ``u`` or ``v`` lands **exactly** on ``elmoSatThreshold`` when
#: the division truncates toward zero, and one step past it when it floors.
#:
#: This is the only construction found that makes x86's signed division
#: observable anywhere in the ported surface.  The two other candidate sites
#: cannot expose it, which is worth recording rather than re-deriving:
#:
#: * ``luminance_plane`` clamps a negative quotient to 0 either way
#:   (``0x1022deec``), so ``trunc`` and ``floor`` are indistinguishable there;
#: * ``elmo_detect``'s ``u`` and ``v`` are squared before the comparison, so a
#:   one-unit difference is invisible unless the pixel sits on the boundary.
#:
#: With ``elmoSatThreshold = 400`` (the shipped DPI value) the test is
#: ``u*u + v*v > 160000``.  Each triple below puts one of the two at exactly
#: -400 under truncation (-401 under floor) and the other at 0, so the sum is
#: exactly 160000 -- **not** greater -- and the pixel must NOT be counted::
#:
#:     u: numerator 2G+2-R-B = -1601, v numerator B-R+1 = 0
#:     v: numerator B-R+1    = -801,  u numerator 2G+2-R-B = 0
#:
#: Both also clear the gates: ``R = 1700 > elmoRedLimit`` (1600), and the
#: luminance (1432 / 1299) is below ``elmoNeutralLimit`` (1500).
ELMO_BOUNDARY_PIXELS = (
    (1700, 898, 1699),     # u = -400 exactly, v = 0
    (1700, 1298, 898),     # v = -400 exactly, u = 0
)


def make_elmo_boundary(w, h):
    """Banded filler with the boundary triples above woven through it.

    The filler is needed because the frame still has to survive the threshold
    relaxation loop to reach ``0x1022e865`` at all -- a frame made only of the
    boundary pixels has no edge structure and takes the identity-LUT bail-out.
    """
    base = make_image(w, h, 2)
    px = list(base.pixels)
    for i in range(0, w * h, 7):
        r, g, b = ELMO_BOUNDARY_PIXELS[(i // 7) % len(ELMO_BOUNDARY_PIXELS)]
        px[3 * i], px[3 * i + 1], px[3 * i + 2] = r, g, b
    return cna.CnaImage(width=w, height=h, pixels=px)


def shifted_params() -> cna.CnaParams:
    """Non-zero ``redShift``/``greenShift``/``blueShift``.

    The shipped DPI leaves all three at 0, so the default params only ever
    reach the *unclamped* luminance loop.  Nothing else in the subsystem reads
    them, so flipping them is exactly the switch between ``0x1022deb5`` and
    ``0x1022df0f``.
    """
    p = cna.default_params()
    p.redShift, p.greenShift, p.blueShift = 40, -25, 13
    return p


#: Images built to reach the bail-out rather than the settled path.
SPECIAL_IMAGES = [
    ("flat 20x16", lambda: make_flat(20, 16)),
    ("flat 20x16 dark", lambda: make_flat(20, 16, 90)),
    ("gradient 24x18", lambda: make_gradient(24, 18)),
    ("2-row 12x2 (no interior)", lambda: make_flat(12, 2)),
]

#: ``(lightInSigma, lightOutSigma)`` pairs driven into the elmo gates.  The
#: first two exercise the "declined" path; the rest force the count to run.
ELMO_CASES = [
    ("gate closed (in == out)", 12.0, 12.0),
    ("gate closed (in < out)", 8.0, 20.0),
    ("gate open, narrow", 20.0, 8.0),
    ("gate open, marginal", 8.000001, 8.0),
    ("gate open, wide", 400.0, 1.0),
]


def _cmp(label, got, ref, out, limit=6):
    ok = got == ref
    if not ok:
        diffs = []
        if isinstance(got, list) and isinstance(ref, list):
            if len(got) != len(ref):
                diffs.append(f"len {len(got)} != {len(ref)}")
            for i, (a, b) in enumerate(zip(got, ref)):
                if a != b:
                    diffs.append(f"[{i}] port={a} dll={b}")
                    if len(diffs) >= limit:
                        break
        else:
            diffs.append(f"port={got} dll={ref}")
        out.append(f"    {label}: " + "; ".join(diffs))
    return ok


# ---------------------------------------------------------------------------
# --selftest: prove the comparison can fail
# ---------------------------------------------------------------------------


def _perturbations():
    """Deliberate defects, each targeting one claim the port makes.

    A verification suite that cannot fail proves nothing, so every substantive
    claim in ``pakon_cna`` gets a matching defect here and the suite is
    required to reject it.  Two of these were originally **not** caught, and
    that is why the case list above contains the exact-equality elmo case and
    why ``gauss_smooth``'s docstring no longer claims its association order is
    load-bearing (it reduces to left-to-right, and a naive implementation is
    bit-identical -- which this list still demonstrates).
    """
    saved = {}

    def sv(name):
        saved[name] = getattr(cna, name)

    def rs(name):
        setattr(cna, name, saved[name])

    out = []

    # the shipped 1/sqrt(2pi) is NOT the mathematical constant
    def a1():
        saved["K"] = cna.K_INV_SQRT_2PI
        cna.K_INV_SQRT_2PI = 0.3989422804014327

    out.append(("gauss amplitude = true 1/sqrt(2pi), not the shipped qword",
                a1, lambda: setattr(cna, "K_INV_SQRT_2PI", saved["K"])))

    # the dot product's association -- expected NOT to be caught, see above
    def a2():
        sv("gauss_smooth")

        def naive(src, n, sigma, ssf):
            d = cna.gauss_half_width(sigma, ssf)
            k = cna.gauss_kernel(sigma, ssf)
            pad = ([cna.f32(src[0])] * d + [cna.f32(v) for v in src[:n]]
                   + [cna.f32(src[n - 1])] * d)
            return [cna.f32(sum(k[i] * pad[b + i] for i in range(2 * d + 1)))
                    for b in range(n)]
        cna.gauss_smooth = naive

    out.append(("gauss dot product summed naively left-to-right "
                "(EXPECTED equal)", a2, lambda: rs("gauss_smooth")))

    # the two float32 spills inside 0x1022ca80's moment loop
    def a3():
        sv("hist_resample")
        src = saved["hist_resample"]

        def patched(params, hist, n, pivot, scale, gain):
            real = cna.f32
            seen = {"n": 0}

            def fake(x):
                seen["n"] += 1
                return x if seen["n"] <= 4 * n else real(x)
            cna.f32 = fake
            try:
                return src(params, hist, n, pivot, scale, gain)
            finally:
                cna.f32 = real
        cna.hist_resample = patched

    out.append(("moment accumulators kept at register precision",
                a3, lambda: rs("hist_resample")))

    # the laplacian's 16-bit wraparound
    def a4():
        sv("laplacian")

        def wide(lum, w, h):
            if w <= 2 or h <= 2:
                return []
            return [lum[(r + 1) * w + c - 1] - 4 * lum[(r + 1) * w + c]
                    + lum[r * w + c] + lum[(r + 2) * w + c]
                    + lum[(r + 1) * w + c + 1]
                    for r in range(h - 2) for c in range(1, w - 1)]
        cna.laplacian = wide

    out.append(("laplacian widened to 32-bit (no int16 wrap)",
                a4, lambda: rs("laplacian")))

    # bElmoOccured's strict compare
    def a5():
        sv("elmo_detect")
        src = saved["elmo_detect"]

        def inclusive(p, img, lin, lout):
            r = src(p, img, lin, lout)
            if r.ran:
                r.b_elmo_occured = r.elmo_percent >= p.elmoCriticalPercent
            return r
        cna.elmo_detect = inclusive

    out.append(("bElmoOccured uses >= instead of >",
                a5, lambda: rs("elmo_detect")))

    # _ftol2's truncation
    def a6():
        sv("ftol2")
        cna.ftol2 = lambda x: int(round(x))

    out.append(("_ftol2 rounds to nearest instead of truncating",
                a6, lambda: rs("ftol2")))

    # results.threshold published before, not after, the reduction
    def a7():
        sv("analyze_image_threshold")
        src = saved["analyze_image_threshold"]

        def shifted(img, p):
            st = src(img, p)
            if st.gave_up and st.reduced_threshold is not None:
                st.threshold = st.reduced_threshold
            return st
        cna.analyze_image_threshold = shifted

    out.append(("results.threshold set to the reduced value on bail-out",
                a7, lambda: rs("analyze_image_threshold")))

    # the buffer order allocateMemory uses
    def a8():
        sv("buffer_sizes")
        src = saved["buffer_sizes"]

        def swapped(p, n):
            s = dict(src(p, n))
            s["scratch_c4_i32"], s["bucket_hist_i32"] = (
                s["bucket_hist_i32"], s["scratch_c4_i32"])
            return s
        cna.buffer_sizes = swapped

    out.append(("allocateMemory buffers 8 and 9 swapped",
                a8, lambda: rs("buffer_sizes")))

    # the /3 in the luminance and elmo paths
    def a9():
        sv("idiv")
        cna.idiv = lambda a, b: a // b          # floor, not truncate

    out.append(("signed division floors instead of truncating toward zero",
                a9, lambda: rs("idiv")))

    # _contrast_map's per-step ratio clamp, [lowClamp, highClamp] swapped
    def a10():
        sv("_contrast_map")
        src = saved["_contrast_map"]

        def swapped(params, s, ratio_den, out_, pivot, idx, limit, *,
                    ascending):
            lo, hi = params.lowClamp, params.highClamp
            # ``params`` is the caller's own CnaParams instance, not a copy
            # handed to this call -- both contrast_map_down and _up share it,
            # so the swap has to be undone before control returns to
            # analyze_image, not just before selftest's next perturbation.
            params.lowClamp, params.highClamp = hi, lo
            try:
                return src(params, s, ratio_den, out_, pivot, idx, limit,
                           ascending=ascending)
            finally:
                params.lowClamp, params.highClamp = lo, hi
        cna._contrast_map = swapped

    out.append(("contrast map ratio clamp bounds swapped (lowClamp/highClamp)",
                a10, lambda: rs("_contrast_map")))

    # build_tone_lut's interior start offset, 0x1022c75d (`sar esi,1`).
    #
    # The interior is written from bin ``step/2``, leaving half a bucket at
    # each end for the two extrapolated tails.  Starting one bin later shifts
    # the whole curve and shortens the low tail, which the 5000-entry
    # ToneScaleLut comparison catches immediately.
    #
    # TWO defects that were tried here and are NOT discriminating, recorded so
    # nobody re-derives them:
    #  * ``(step+1)/2`` instead of ``step/2`` -- identical whenever ``step`` is
    #    even, and the shipped params give ``step = histSize/bucketSize = 10``.
    #    It would only bite on a .dpi with an odd ratio.
    #  * the high tail's clamp constant ``0x1059f880`` (4095.0) moved to
    #    4094.0 -- the extrapolator stops one step earlier and then fills the
    #    remainder with 0x0fff, so the two agree except when the accumulator
    #    lands in the narrow (4094, 4094.5) window where ``trunc(acc+0.5)`` is
    #    still 4094.  None of these frames put it there.
    def a11():
        sv("build_tone_lut")
        src = saved["build_tone_lut"]

        def shifted_start(curve, n_buckets, n_bins):
            real_idiv = cna.idiv
            state = {"n": 0}

            def fake(a, b):
                state["n"] += 1
                # call 1 is step = n_bins/n_buckets; call 2 is half = step/2
                return real_idiv(a, b) + (1 if state["n"] == 2 else 0)
            cna.idiv = fake
            try:
                return src(curve, n_buckets, n_bins)
            finally:
                cna.idiv = real_idiv
        cna.build_tone_lut = shifted_start

    out.append(("tone LUT interior starts one bin late (step/2 + 1)",
                a11, lambda: rs("build_tone_lut")))

    # validate_params's thresholdReductionFactor upper bound, 0x1022cfc1
    def a12():
        sv("validate_params")
        src = saved["validate_params"]

        def loose(pp):
            fld = src(pp)
            if fld == 0xD and pp.thresholdReductionFactor == 1.0:
                return None
            return fld
        cna.validate_params = loose

    out.append(("thresholdReductionFactor upper bound accepts 1.0 (>= -> >)",
                a12, lambda: rs("validate_params")))

    # analyze_image's step 8 normalisation pivot, 0x1022e9e3
    def a13():
        sv("analyze_image")
        src = saved["analyze_image"]

        def wrong_pivot(img, pp):
            a = src(img, pp)
            # The vendor keeps the ORIGINAL params.pivot in a separate slot
            # (E-0x04) for this step; re-deriving from a.pivot instead uses
            # whichever bin the percentile search landed on.
            if a.threshold_stage is not None and not a.threshold_stage.gave_up:
                lut = list(a.tone_lut)
                # undo the port's normalisation and redo it at a.pivot
                delta_orig = pp.pivot - lut[pp.pivot]
                unshifted = [v for v in lut]
                # lut already has delta_orig applied and clamped; clamping is
                # lossy, so this defect is only meaningful where nothing
                # clamped -- which the shipped-default cases satisfy (the LUT
                # sits comfortably inside [0, 0xfff] away from the tails).
                for i in range(len(unshifted)):
                    unshifted[i] = unshifted[i] - delta_orig
                delta_new = a.pivot - unshifted[a.pivot]
                out_lut = []
                for v in unshifted:
                    v2 = v + delta_new
                    if v2 < 0:
                        v2 = 0
                    elif v2 > cna.K_LUT_MAX:
                        v2 = cna.K_LUT_MAX
                    out_lut.append(cna.i16(v2))
                a.tone_lut = out_lut
            return a
        cna.analyze_image = wrong_pivot

    out.append(("analyzeImage normalises the tone LUT at the re-derived "
                "pivot, not params.pivot", a13, lambda: rs("analyze_image")))

    # elmo_detect's per-pixel saturation test, 0x1022e963
    def a14():
        sv("elmo_detect")

        def inclusive_sat(pp, img, lin, lout):
            r = cna.ElmoResult(elmo_percent=-1.0, b_elmo_occured=False)
            if not (lin > lout):
                return r
            if not (pp.elmoCriticalPercent < cna.K_HUNDRED_F32):
                return r
            r.ran = True
            sat2 = cna.i32(pp.elmoSatThreshold * pp.elmoSatThreshold)
            n = img.width * img.height
            px = img.pixels
            count = 0
            for i in range(n):
                red, grn, blu = px[3 * i], px[3 * i + 1], px[3 * i + 2]
                lum = cna.idiv(red + grn + blu + 1, 3)
                u = cna.idiv(2 * grn + 2 - red - blu, 4)
                v = cna.idiv(blu - red + 1, 2)
                if not (cna.i16(red) > pp.elmoRedLimit
                        or cna.i16(grn) > pp.elmoGreenLimit
                        or cna.i16(blu) > pp.elmoBlueLimit):
                    continue
                if cna.i16(lum) >= pp.elmoNeutralLimit:
                    continue
                # defect: >= instead of the vendor's strict >
                if (cna.i32(cna.i16(u) * cna.i16(u))
                        + cna.i32(cna.i16(v) * cna.i16(v)) >= sat2):
                    count += 1
            r.count = count
            r.elmo_percent = cna.f32(float(count) * cna.K_HUNDRED_F32
                                     / float(n))
            r.b_elmo_occured = r.elmo_percent > pp.elmoCriticalPercent
            return r
        cna.elmo_detect = inclusive_sat

    out.append(("elmo saturation test counts u*u+v*v == satThreshold**2 "
                "(>= instead of >)", a14, lambda: rs("elmo_detect")))

    return out


def selftest(argv: list[str]) -> int:
    """Run the whole suite once per deliberate defect and require rejection."""
    import contextlib
    import io

    print("== selftest: the suite must reject each deliberate defect ==")
    base = main(argv + ["--no-selftest"])
    print(f"  unperturbed run: rc={base}")
    if base != 0:
        print("  cannot selftest against a failing baseline")
        return 1
    bad = 0
    for label, apply, undo in _perturbations():
        apply()
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(argv + ["--no-selftest"])
        except Exception:                             # noqa: BLE001
            rc = 1
        finally:
            undo()
        expected_equal = "EXPECTED equal" in label
        ok = (rc == 0) if expected_equal else (rc != 0)
        bad += not ok
        verdict = "equal, as documented" if expected_equal else (
            "rejected" if rc else "*** NOT REJECTED ***")
        print(f"  {label:<58} rc={rc} {verdict}")
    if bad:
        print(f"SELFTEST FAILED {bad}")
        return 1
    print("SELFTEST OK")
    return 0


def main(argv: list[str]) -> int:
    fpcw = FPCW_MSVC
    argv = list(argv)
    if "--fpcw" in argv:
        i = argv.index("--fpcw")
        fpcw = int(argv[i + 1], 0)
        del argv[i:i + 2]
    args = [a for a in argv[1:] if not a.startswith("--")]
    dll = Path(args[0]) if args else DEFAULT_DLL
    if not dll.exists():
        print(f"{dll} not found — run "
              f"'python3 tools/re/reachability.py extract' first")
        return 2
    pe = dll.read_bytes()
    p = cna.default_params()
    bad = 0
    print(f"DLL {dll}  x87 CW={fpcw:#06x} "
          f"({'MSVC/Win32 53-bit' if fpcw == FPCW_MSVC else 'QEMU 64-bit'})")
    print()

    # ---- 1. _ftol2 ------------------------------------------------------
    print("== 0x104ffe44 _ftol2 (truncate toward zero) ==")
    emu = CnaEmu(pe, fpcw)
    n_bad = 0
    for x in FTOL_CASES:
        ref = dll_ftol2(emu, x)
        got = cna.ftol2(x)
        if got != ref:
            n_bad += 1
            print(f"    FAIL x={x!r} port={got} dll={ref}")
    bad += n_bad
    print(f"  {len(FTOL_CASES)} cases  {'OK' if not n_bad else 'FAILED'}\n")

    # ---- 2. laplacian ---------------------------------------------------
    print("== 0x1022c340 laplacian (int16 wraparound) ==")
    n_bad = 0
    for label, w, h, seed in IMAGE_CASES:
        emu = CnaEmu(pe, fpcw)
        img = make_image(w, h, seed)
        lum = cna.luminance_plane(img, p)
        ref = dll_laplacian(emu, lum, w, h)
        got = cna.laplacian(lum, w, h)
        msgs: list[str] = []
        ok = _cmp(label, got, ref, msgs)
        n_bad += not ok
        print(f"  {label:<16} {len(ref):>5} taps  {'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    # a deliberate wraparound case: values large enough that 4*centre overflows
    emu = CnaEmu(pe, fpcw)
    big = [(i * 4127) % 40000 - 20000 for i in range(7 * 5)]
    ref = dll_laplacian(emu, big, 7, 5)
    got = cna.laplacian(big, 7, 5)
    msgs = []
    ok = _cmp("int16 wrap", got, ref, msgs)
    n_bad += not ok
    print(f"  {'int16 wrap':<16} {len(ref):>5} taps  {'OK' if ok else 'FAIL'}")
    for m in msgs:
        print(m)
    bad += n_bad
    print()

    # ---- 3. gaussian smooth ---------------------------------------------
    print("== 0x1022c8f0 gaussian smooth ==")
    n_bad = 0
    gauss_cases = [
        ("n=64 sigma=2", [float((i * 13) % 97) for i in range(64)], 64, 2.0),
        ("n=64 sigma=10", [float((i * 13) % 97) for i in range(64)], 64, 10.0),
        ("n=200 sigma=4", [float(abs(100 - i)) for i in range(200)], 200, 4.0),
        ("n=200 sigma=1", [float(abs(100 - i)) for i in range(200)], 200, 1.0),
        ("n=500 sigma=10 spike",
         [1000.0 if i == 250 else 0.0 for i in range(500)], 500, 10.0),
        ("n=33 sigma=0.5", [float(i % 7) for i in range(33)], 33, 0.5),
        ("n=120 negatives", [float((i % 11) - 5) for i in range(120)], 120, 3.0),
    ]
    for label, src, n, sigma in gauss_cases:
        emu = CnaEmu(pe, fpcw)
        ref, ref_k = dll_gauss(emu, src, n, sigma, p)
        got_k = cna.gauss_kernel(sigma, p.smoothingSizeFactor)
        got = cna.gauss_smooth(src, n, sigma, p.smoothingSizeFactor)
        msgs = []
        ok = _cmp(label + " kernel", got_k, ref_k, msgs)
        ok = _cmp(label, got, ref, msgs) and ok
        n_bad += not ok
        print(f"  {label:<22} d={cna.gauss_half_width(sigma, p.smoothingSizeFactor):>3} "
              f"{'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    bad += n_bad
    print()

    # ---- 4. peak of the second difference -------------------------------
    print("== 0x1022c3e0 argmax f[j-2]+f[j+2]-2f[j] ==")
    n_bad = 0
    peak_cases = [
        ("bell", [math.exp(-((i - 60) ** 2) / 200.0) * 1000 for i in range(140)],
         30, 120),
        ("flat", [1.0] * 100, 10, 90),
        ("ties", [float(i % 3) for i in range(100)], 5, 90),
        ("two peaks",
         [1000 * math.exp(-((i - 30) ** 2) / 50.0)
          + 999 * math.exp(-((i - 70) ** 2) / 50.0) for i in range(120)],
         5, 110),
        ("descending", [float(200 - i) for i in range(150)], 20, 140),
    ]
    for label, f, start, limit in peak_cases:
        emu = CnaEmu(pe, fpcw)
        ref = dll_peak(emu, f, start, limit)
        got = cna.peak_second_difference(f, start, limit)
        ok = ref == got
        n_bad += not ok
        print(f"  {label:<14} start={start:>4} limit={limit:>4} "
              f"port={got:>4} dll={ref:>4} {'OK' if ok else 'FAIL'}")
    bad += n_bad
    print()

    # ---- 5. allocateMemory ----------------------------------------------
    print("== 0x1022d970 allocateMemory (byte sizes, in call order) ==")
    n_bad = 0
    for label, w, h in (("640x480", 640, 480), ("16x12", 16, 12),
                        ("1000x1500", 1000, 1500)):
        emu = CnaEmu(pe, fpcw)
        sizes, ptrs, _ = dll_alloc(emu, p, w, h)
        s = cna.buffer_sizes(p, w * h)
        want = [
            2 * s["lum_i16"], 4 * s["lum_hist_i32"], 2 * s["lap_i16"],
            4 * s["edge_hist_i32"], 4 * s["gauss_pad_f32"],
            4 * s["gauss_kern_f32"], 4 * s["resample_f32"],
            4 * s["scratch_c4_i32"], 4 * s["bucket_hist_i32"],
            4 * s["scratch_cc_f32"], 4 * s["scratch_d0_f32"],
            4 * s["scratch_d4_f32"], 4 * s["scratch_d8_f32"],
            2 * s["tone_lut_i16"],
        ]
        msgs = []
        ok = _cmp(label, want, sizes, msgs)
        n_bad += not ok
        print(f"  {label:<10} {len(sizes)} allocations  "
              f"{'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    bad += n_bad
    print()

    # ---- 6. hist moments + smooth + resample ----------------------------
    print("== 0x1022ca80 moments + smooth + resample ==")
    n_bad = 0
    resample_cases = [
        ("bell n=200",
         [int(1000 * math.exp(-((i - 100) ** 2) / 400.0)) + 1
          for i in range(200)], 200, 100),
        ("skewed n=200",
         [int(500 * math.exp(-((i - 40) ** 2) / 200.0)) + 2
          for i in range(200)], 200, 60),
        ("flat n=100", [7] * 100, 100, 50),
        ("n=500 wide",
         [int(300 * math.exp(-((i - 250) ** 2) / 5000.0)) + 1
          for i in range(500)], 500, 155),
        # A real scanned roll's dark-half edge-bucket histogram drove
        # `in_sigma` to NaN on 100% of its 40 frames (a genuine x87
        # negative-variance rounding outcome on real data, live-DLL-confirmed
        # against the exact real histogram -- not reproduced here, per this
        # project's rule against committing anything capture-derived). This
        # is the smallest synthetic shape found that reproduces the same real
        # DLL behaviour bit-for-bit (also live-DLL-confirmed): almost all mass
        # in one bucket, with a single stray count one bucket over stopping
        # the variance from being exactly representable. Before the
        # `0x1022ce98` int32-store-truncation fix, this made every `hist_
        # resample` caller's crossing search in `analyze_image._half` walk
        # unboundedly past `n_buckets` instead of landing on 0 immediately.
        ("near-spike n=500 (NaN sigma)",
         [1_000_000 if i == 50 else (1 if i == 51 else 0)
          for i in range(500)], 500, 50),
        # The even more degenerate cousin: ALL mass in exactly one bucket.
        # Mathematically zero variance, but not exactly representable once
        # the moments round through float32, so this ALSO comes back NaN on
        # real hardware (live-DLL-confirmed) rather than the "sigma == 0.0
        # exactly" a naive reading would expect -- which is what exposed the
        # separate, previously-unwrapped `ratio`/`step` divides
        # (0x1022cdf5..0x1022ce07, 0x1022ce33..0x1022ce3d) to a genuine
        # `ZeroDivisionError` in the port whenever the real and port-computed
        # variance rounding happened to disagree at exactly 0.0.
        ("exact spike n=500 (zero-variance divide)",
         [1_000_000 if i == 50 else 0 for i in range(500)], 500, 50),
    ]
    scale = cna.f32(p.darkScale / p.bucketSize)
    for label, hist, n, pivot in resample_cases:
        emu = CnaEmu(pe, fpcw)
        try:
            r_in, r_out, r_arr = dll_resample(emu, p, hist, n, pivot, scale,
                                              p.darkMaxContrastGain)
        except Exception as exc:                      # noqa: BLE001
            n_bad += 1
            print(f"  {label:<16} DLL RUN FAILED: {exc}")
            continue
        try:
            h = cna.hist_resample(p, hist, n, pivot, scale,
                                  p.darkMaxContrastGain)
        except Exception as exc:                      # noqa: BLE001
            n_bad += 1
            print(f"  {label:<16} PORT RAISED: {exc}")
            continue
        msgs = []
        # `_cmp`'s `==` is correct for every ordinary case, but NaN != NaN,
        # so a genuinely-matching "both sides are the real indefinite QNaN"
        # result must be checked with `isnan`, not `==`, or a real pass would
        # print as a false FAIL.
        if math.isnan(r_in) or math.isnan(h.in_sigma):
            ok = math.isnan(r_in) and math.isnan(h.in_sigma)
            if not ok:
                msgs.append(f"    {label} inSigma: port={h.in_sigma} "
                            f"dll={r_in}")
        else:
            ok = _cmp(label + " inSigma", h.in_sigma, r_in, msgs)
        ok = _cmp(label + " outSigma", h.out_sigma, r_out, msgs) and ok
        ok = _cmp(label + " out", h.out, r_arr, msgs) and ok
        n_bad += not ok
        print(f"  {label:<16} inSigma={r_in!r} outSigma={r_out:.6f} "
              f"{'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    bad += n_bad
    print()

    # ---- 7. analyzeImage, entry .. 0x1022e23e ---------------------------
    print("== 0x1022ddc0 analyzeImage, entry .. threshold settled ==")
    n_bad = 0
    ps = shifted_params()
    cases = ([(lbl, make_image(w, h, s), p) for lbl, w, h, s in IMAGE_CASES]
             + [(lbl, fn(), p) for lbl, fn in SPECIAL_IMAGES]
             + [("signed 24x18 +shifts", make_signed(24, 18), ps),
                ("signed 13x11 +shifts", make_signed(13, 11, 4), ps),
                ("banded 32x24 +shifts", make_image(32, 24, 2), ps)])
    for label, img, pp in cases:
        emu = CnaEmu(pe, fpcw)
        try:
            ref = dll_analyze_image_threshold(emu, pp, img)
        except Exception as exc:                      # noqa: BLE001
            n_bad += 1
            print(f"  {label:<16} DLL RUN FAILED: {exc}")
            continue
        st = cna.analyze_image_threshold(img, pp)
        msgs = []
        ok = _cmp(label + " nPixels", st.n_pixels, ref["n_pixels"], msgs)
        ok = _cmp(label + " lum", st.lum, ref["lum"], msgs) and ok
        ok = _cmp(label + " lumHist", st.lum_hist, ref["lum_hist"], msgs) and ok
        ok = _cmp(label + " lap", st.lap, ref["lap"], msgs) and ok
        ok = _cmp(label + " threshold", st.threshold, ref["threshold"],
                  msgs) and ok
        ok = _cmp(label + " nEdge", st.n_edge, ref["n_edge"], msgs) and ok
        ok = _cmp(label + " edgeHist", st.edge_hist, ref["edge_hist"],
                  msgs) and ok
        ok = _cmp(label + " gaveUp", st.gave_up, ref["gave_up"], msgs) and ok
        n_bad += not ok
        print(f"  {label:<24} thr={ref['threshold']:>5} "
              f"nEdge={ref['n_edge']:>7} gaveUp={ref['gave_up']} "
              f"{'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    bad += n_bad
    print()

    # ---- 7b. analyzeImage end to end ------------------------------------
    print("== 0x1022ddc0 analyzeImage, entry .. ret (full tone scale) ==")
    n_bad = 0
    full_cases = ([(lbl, make_image(w, h, s), p) for lbl, w, h, s in IMAGE_CASES]
                  + [("flat 20x16 (bail-out)", make_flat(20, 16), p),
                     ("gradient 24x18 (bail-out)", make_gradient(24, 18), p),
                     ("signed 24x18 +shifts", make_signed(24, 18), ps),
                     ("sat boundary 32x24", make_elmo_boundary(32, 24), p)])
    for label, img, pp in full_cases:
        emu = CnaEmu(pe, fpcw)
        try:
            ref = dll_analyze_image(emu, pp, img)
        except Exception as exc:                      # noqa: BLE001
            n_bad += 1
            print(f"  {label:<26} DLL RUN FAILED: {exc}")
            continue
        try:
            a = cna.analyze_image(img, pp)
        except Exception as exc:                      # noqa: BLE001
            n_bad += 1
            print(f"  {label:<26} PORT RAISED: {exc}")
            continue
        msgs = []
        ok = _cmp(label + " nPixels", a.n_pixels, ref["n_pixels"], msgs)
        ok = _cmp(label + " threshold", a.threshold, ref["threshold"],
                  msgs) and ok
        ok = _cmp(label + " nEdge", a.n_edge, ref["n_edge"], msgs) and ok
        if a.dark is not None:
            ok = _cmp(label + " darkInSigma", a.dark.in_sigma,
                      ref["darkInSigma"], msgs) and ok
            ok = _cmp(label + " darkOutSigma", a.dark.out_sigma,
                      ref["darkOutSigma"], msgs) and ok
            ok = _cmp(label + " lightInSigma", a.light.in_sigma,
                      ref["lightInSigma"], msgs) and ok
            ok = _cmp(label + " lightOutSigma", a.light.out_sigma,
                      ref["lightOutSigma"], msgs) and ok
            ok = _cmp(label + " bucketHist", a.bucket_hist,
                      ref["bucket_hist"], msgs) and ok
        ok = _cmp(label + " elmoPercent", a.elmo.elmo_percent,
                  ref["elmoPercent"], msgs) and ok
        ok = _cmp(label + " bElmoOccured", a.elmo.b_elmo_occured,
                  ref["bElmoOccured"], msgs) and ok
        # THE deliverable: the LUT the shell threads into ctx+0x64d0.
        ok = _cmp(label + " ToneScaleLut", a.tone_lut, ref["tone_lut"],
                  msgs) and ok
        n_bad += not ok
        lut = ref["tone_lut"]
        print(f"  {label:<26} lut[0]={lut[0]:>5} lut[1550]={lut[1550]:>5} "
              f"lut[-1]={lut[-1]:>5} elmo={int(ref['bElmoOccured'])} "
              f"{'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    bad += n_bad
    print()

    # ---- 8. elmo -- cna's half of the shell's bElmoOccured fork ---------
    print("== 0x1022e865 elmo detection (gates driven from the harness) ==")
    n_bad = 0
    elmo_images = [("16x12 banded", make_image(16, 12, 1), p),
                   ("32x24 banded", make_image(32, 24, 2), p),
                   # negative u/v: the only case that separates x86's
                   # truncate-toward-zero /4 and /2 from a floor division.
                   ("signed 24x18", make_signed(24, 18), ps),
                   ("signed 13x11", make_signed(13, 11, 4), ps),
                   # u/v exactly on elmoSatThreshold -- the only input that
                   # separates truncate-toward-zero from floor.
                   ("sat boundary", make_elmo_boundary(32, 24), p)]
    for img_label, img, pp in elmo_images:
        for label, lin, lout in ELMO_CASES:
            emu = CnaEmu(pe, fpcw)
            try:
                r_pct, r_occ = dll_elmo(emu, pp, img, lin, lout)
            except Exception as exc:                  # noqa: BLE001
                n_bad += 1
                print(f"  {img_label} / {label:<24} DLL RUN FAILED: {exc}")
                continue
            e = cna.elmo_detect(pp, img, lin, lout)
            msgs = []
            ok = _cmp("elmoPercent", e.elmo_percent, r_pct, msgs)
            ok = _cmp("bElmoOccured", e.b_elmo_occured, r_occ, msgs) and ok
            n_bad += not ok
            print(f"  {img_label} / {label:<24} pct={r_pct:>12.6f} "
                  f"occ={int(r_occ)} ran={int(e.ran)} "
                  f"{'OK' if ok else 'FAIL'}")
            for m in msgs:
                print(m)
    # The exact-equality case, which is the only thing that distinguishes the
    # vendor's strictly-greater compare (0x1022e9a4 `test ah,0x41; jne`) from
    # a >= .  Without it a port using >= passes -- checked, and it did.
    img = make_image(32, 24, 2)
    emu = CnaEmu(pe, fpcw)
    eq_pct, _ = dll_elmo(emu, p, img, 400.0, 1.0)
    p_eq = cna.default_params()
    p_eq.elmoCriticalPercent = eq_pct
    emu = CnaEmu(pe, fpcw)
    r_pct, r_occ = dll_elmo(emu, p_eq, img, 400.0, 1.0)
    e = cna.elmo_detect(p_eq, img, 400.0, 1.0)
    msgs = []
    ok = _cmp("elmoPercent", e.elmo_percent, r_pct, msgs)
    ok = _cmp("bElmoOccured", e.b_elmo_occured, r_occ, msgs) and ok
    n_bad += not ok
    print(f"  {'elmoCriticalPercent == elmoPercent exactly':<40} "
          f"pct={r_pct:>12.6f} occ={int(r_occ)} {'OK' if ok else 'FAIL'}")
    for m in msgs:
        print(m)

    # ...and the critical-percent disable switch, the second gate.
    for crit, label in ((100.0, "elmoCriticalPercent=100 (disabled)"),
                        (0.0, "elmoCriticalPercent=0 (always fires)")):
        p2 = cna.default_params()
        p2.elmoCriticalPercent = crit
        img = make_image(32, 24, 2)
        emu = CnaEmu(pe, fpcw)
        try:
            r_pct, r_occ = dll_elmo(emu, p2, img, 400.0, 1.0)
        except Exception as exc:                      # noqa: BLE001
            n_bad += 1
            print(f"  {label:<40} DLL RUN FAILED: {exc}")
            continue
        e = cna.elmo_detect(p2, img, 400.0, 1.0)
        msgs = []
        ok = _cmp("elmoPercent", e.elmo_percent, r_pct, msgs)
        ok = _cmp("bElmoOccured", e.b_elmo_occured, r_occ, msgs) and ok
        n_bad += not ok
        print(f"  {label:<40} pct={r_pct:>12.6f} occ={int(r_occ)} "
              f"{'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    bad += n_bad
    print()

    # ---- 9. 0x1022ceb0, the params validator ---------------------------
    print("== 0x1022ceb0 AnsCnaParams validator ==")
    n_bad = 0
    #: One perturbation per check, plus the shipped values.  Each names the
    #: field index the DLL is expected to report.
    perturb = [
        ("shipped defaults", {}),
        ("histSize = 4095", {"histSize": 4095}),
        ("histSize = 4096", {"histSize": 4096}),
        ("bucketSize = 0", {"bucketSize": 0}),
        ("bucketSize = 7 (not a divisor)", {"bucketSize": 7}),
        ("lowClamp = 0", {"lowClamp": 0.0}),
        ("highClamp = lowClamp", {"highClamp": 0.5}),
        ("blend = 0.05", {"blend": 0.05}),
        ("blend = 9.0 (upper bound, inclusive)", {"blend": 9.0}),
        ("blend = 9.001", {"blend": 9.001}),
        ("minPivotPercentile = -0.1", {"minPivotPercentile": -0.1}),
        ("maxPivot == minPivot", {"maxPivotPercentile": 0.1}),
        ("maxPivot = 1.0 (inclusive)", {"maxPivotPercentile": 1.0}),
        ("maxPivot = 1.5", {"maxPivotPercentile": 1.5}),
        ("thresholdMultiplier = 0", {"thresholdMultiplier": 0.0}),
        ("reductionFactor = 1.0 (exclusive)",
         {"thresholdReductionFactor": 1.0}),
        ("reductionFactor = 0", {"thresholdReductionFactor": 0.0}),
        ("minPosThreshold = 3", {"minPosThreshold": 3}),
        ("minPosThreshold = 4 (boundary)", {"minPosThreshold": 4}),
        ("minLapPixelRatio = -0.01", {"minLapPixelRatio": -0.01}),
        ("minLapPixelRatio = 1.0 (inclusive)", {"minLapPixelRatio": 1.0}),
        ("minLapPixelRatio = 1.01", {"minLapPixelRatio": 1.01}),
        ("smoothingSizeFactor = 0.5", {"smoothingSizeFactor": 0.5}),
        ("smoothingSizeFactor = 10.5", {"smoothingSizeFactor": 10.5}),
        ("laplacianSigma = 0.5", {"laplacianHistSmoothingSigma": 0.5}),
        ("laplacianSigma = 50.5", {"laplacianHistSmoothingSigma": 50.5}),
        ("coarseSigma = 0.5", {"coarseHistSmoothingSigma": 0.5}),
        ("toneScaleSigma = 60", {"toneScaleSmoothingSigma": 60.0}),
        ("elmoNeutralLimit = -1", {"elmoNeutralLimit": -1}),
        ("elmoRedLimit = 4096", {"elmoRedLimit": 4096}),
        ("elmoGreenLimit = -5", {"elmoGreenLimit": -5}),
        ("elmoBlueLimit = 4096", {"elmoBlueLimit": 4096}),
        ("elmoSatThreshold = 4096", {"elmoSatThreshold": 4096}),
        ("elmoAggressiveness = 2", {"elmoAggressiveness": 2}),
        ("elmoAggressiveness = 0", {"elmoAggressiveness": 0}),
    ]
    for label, changes in perturb:
        pv = cna.params_from_bytes(cna.params_to_bytes(cna.default_params()))
        for k, v in changes.items():
            setattr(pv, k, v)
        emu = CnaEmu(pe, fpcw)
        rc, fld = dll_validate(emu, pv)
        got = cna.validate_params(pv)
        want = fld if rc else None
        ok = got == want
        n_bad += not ok
        print(f"  {label:<38} dll={'ok' if want is None else f'field #{want}'}"
              f"  port={'ok' if got is None else f'field #{got}'} "
              f"{'OK' if ok else 'FAIL'}")
    bad += n_bad
    print()

    # ---- 10. the whole stage 1, through the real Cap wrapper -----------
    print("== 0x10132dc0 -> 0x1022ea50 -> 0x10132ed0 (the shell's stage 1) ==")
    n_bad = 0
    for label, img, pp, fe in (
        ("16x12 banded", make_image(16, 12, 1), p, 0),
        ("32x24 banded", make_image(32, 24, 2), p, 0),
        ("32x24 banded, cap+0xe=1", make_image(32, 24, 2), p, 1),
        ("flat 20x16 (bail-out)", make_flat(20, 16), p, 0),
        ("signed 24x18 +shifts", make_signed(24, 18), ps, 0),
        ("sat boundary 32x24", make_elmo_boundary(32, 24), p, 0),
    ):
        emu = CnaEmu(pe, fpcw)
        try:
            ref = dll_cap_analyze(emu, pp, img, cap_flag_e=fe)
        except Exception as exc:                      # noqa: BLE001
            n_bad += 1
            print(f"  {label:<26} DLL RUN FAILED: {exc}")
            continue
        if ref["threw"]:
            n_bad += 1
            print(f"  {label:<26} DLL threw unexpectedly")
            continue
        got = cna.analyze_to_results(img, pp, cap_flag_e=fe)
        msgs = []
        ok = True
        for off, code, name in RESULT_SCALARS:
            ok = _cmp(f"{label} {name}",
                      struct.unpack_from(code, got.raw, off)[0],
                      struct.unpack_from(code, ref["raw"], off)[0], msgs) and ok
        ok = _cmp(f"{label} bElmoOccured", got.raw[0x5C], ref["raw"][0x5C],
                  msgs) and ok
        for off, name in RESULT_POINTERS:
            a = struct.unpack_from("<I", got.raw, off)[0] != 0
            b = struct.unpack_from("<I", ref["raw"], off)[0] != 0
            ok = _cmp(f"{label} {name} non-null", a, b, msgs) and ok
        ok = _cmp(f"{label} ToneScaleLut", got.tone_scale_lut, ref["tone_lut"],
                  msgs) and ok
        ok = _cmp(f"{label} LuminanceHist", got.luminance_hist,
                  ref["lum_hist"], msgs) and ok
        ok = _cmp(f"{label} EdgeHist", got.edge_hist, ref["edge_hist"],
                  msgs) and ok
        ok = _cmp(f"{label} cap+0xf", 1, ref["cap_ok_byte"], msgs) and ok
        n_bad += not ok
        print(f"  {label:<26} lut[{pp.pivot}]="
              f"{ref['tone_lut'][pp.pivot]:>5} "
              f"elmo={ref['raw'][0x5C]} {'OK' if ok else 'FAIL'}")
        for m in msgs:
            print(m)
    bad += n_bad
    print()

    if bad:
        print(f"FAILED {bad} check(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest([a for a in sys.argv
                                   if a != "--selftest"]))
    raise SystemExit(main(sys.argv))
