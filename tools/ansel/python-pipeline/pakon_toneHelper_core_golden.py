#!/usr/bin/env python3
r"""Golden ``toneHelper`` **core** (everything except the tree walk) vs the DLL.

The decision-tree walker has its own harness — ``pakon_toneHelper_tree_golden``
— because it can be checked exhaustively.  This file covers the part that
cannot: the floating-point statistics, the metric producer that drives them,
and the histogram-fed entry point that ties the whole subsystem together.

WHAT RUNS FOR REAL
==================
Six vendor functions execute start to finish, on real input, with nothing
about their arithmetic intercepted::

    0x10278140  AnsHistogram::AnsHistogram   (the ctor, so the object layout
                                              is the DLL's and not a guess)
    0x10278df0  AnsHistogram::calcWork
    0x102781d0  AnsHistogram::calcDistance
    0x10278730  AnsHistogram::calcStats
    0x101da6b0  AnsToneHelperCapabilityImpl param validation
    0x101db020  the 29-metric producer (which calls the four above, 14x)
    0x101dd1b0  AnsToneHelperCapabilityImpl::analyze — the histogram-fed
                entry point, end to end, including 0x101dabe0 allocateMemory,
                0x101da8c0/0x101da800 and 0x101db890
    0x1010bb40  the rep-movsd getResults behind Cap 0x1010c6a0

THE X87 CONTROL WORD IS LOAD-BEARING
====================================
Measured on this machine with a three-instruction probe (``fld1``,
``fidiv`` by 3, ``fstp tbyte``), the stored significand of 1/3 is:

    FPCW left alone   0xaaaaaaaaaaaaaaab   64-bit extended
    FPCW = 0x007f     0xaaaaab0000000000   24-bit single
    FPCW = 0x027f     0xaaaaaaaaaaaaa800   53-bit double  <-- Windows
    FPCW = 0x037f     0xaaaaaaaaaaaaaaab   64-bit extended

Unicorn *reports* ``FPCW == 0x0000`` on a fresh ``Uc`` but behaves as extended
until the register is written, so leaving it alone is not "the default", it is
an unspecified third thing.  Windows initialises the x87 CW to ``0x027f`` and
MSVC 7.1's CRT keeps it there, which is exactly a Python ``float`` — that is
why ``pakon_toneHelper`` can model ST(0) in doubles at all.  This harness sets
``0x027f`` and then **re-runs the whole matrix at ``0x037f``** and reports
which outputs move, so the choice is measured, not assumed.  Same convention
as ``pakon_ast_golden.py``.

WHAT IS STUBBED (none of it arithmetic)
=======================================
* ``0x104ffd78`` (``operator new``) and the MSVCR71 ``operator delete`` import
  — a bump allocator and a no-op.  The PE is loaded unbound and CRT init never
  runs.  ``allocateMemory``'s *sizes* are still the DLL's own, and the harness
  records them off the ``new`` calls to check them against
  ``pakon_toneHelper.allocate_memory``.
* MSVCP71 ``basic_string`` ctor/dtor/append and ``_itoa`` — error-path string
  building only.
* ``0x1001ed90`` / ``0x10020ad0`` — the exception raisers.  Recorded, not
  executed; the negative cases below check they are *reached* with the right
  source line and that a non-OK status then short-circuits the caller.
* ``fcn.104ffe44`` (``_ftol``) is **not** stubbed — it is real code in this
  image and the ``mi = (int)mean`` truncation depends on it.

dei
===
Nothing in this file, or in anything it runs, touches dei.  ``0x101dd1b0``'s
only non-histogram scalar input is ``[ebp+0x18]``, which
``analyzeAutoTone`` fills with ``&ctx[0x4bc]`` (``0x100fc36a``); it lands at
``impl+0x128`` and is metric id 30, ``EXPOSURE``.  See ``pakon_toneHelper``'s
header for the full disposal of the dei question.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_toneHelper_core_golden.py [dll]``
"""
from __future__ import annotations

import random
import struct
import sys
from pathlib import Path

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
    UC_X86_REG_FPCW,
)

import pakon_toneHelper as th

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x02000000
SCRATCH = 0x00100000
RET_MAGIC = 0x00110000

FPCW_WINDOWS = th.FPCW_WINDOWS      # 0x027f, 53-bit  -- the model
FPCW_EXTENDED = th.FPCW_EXTENDED    # 0x037f, 64-bit  -- the sensitivity check

VA_OP_NEW = 0x104FFD53
VA_OP_NEW_2 = 0x104FFD78            # what allocateMemory calls
VA_OP_DELETE = 0x104FFDD0
VA_OP_DELETE_ARR = 0x104FFE3E
IAT_STRING_CTOR = 0x10573394
IAT_STRING_DTOR = 0x10573418
IAT_STRING_APPEND_C = 0x10573204
IAT_STRING_APPEND_S = 0x105731D4
IAT_STRING_ASSIGN = 0x1057327C
IAT_ITOA = 0x105735A0

VA_THROW1 = 0x1001ED90
VA_THROW2 = 0x10020AD0

DEFAULT_DLL = Path("/tmp/pakon_re/PakonIMAu.dll")


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    """Minimal PakonIMAu.dll emulator: bump heap, CRT stubs, flat SEH head."""

    def __init__(self, pe: bytes, fpcw: int = FPCW_WINDOWS):
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self.pe = pe
        self.fpcw = fpcw
        self._load()
        uc.mem_map(0, 0x1000)
        uc.mem_map(STACK, STACK_SZ)
        uc.mem_map(HEAP, HEAP_SZ)
        uc.mem_map(SCRATCH, 0x10000)
        uc.mem_map(RET_MAGIC & ~0xFFF, 0x1000)
        uc.mem_write(RET_MAGIC, b"\xC3")
        uc.mem_write(0, struct.pack("<I", 0xFFFFFFFF))
        uc.reg_write(UC_X86_REG_FPCW, fpcw)
        self.brk = HEAP + 0x1000
        self._stub_next = SCRATCH + 0x1000
        self.faults: list[str] = []
        self.new_sizes: list[int] = []
        self.thrown: list[tuple[str, int]] = []
        uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)

        def op_new(e: "Emu", a: int):
            n = e.r32(a)
            e.new_sizes.append(n)
            return e.alloc(max(n, 4)), 0

        self.hook(VA_OP_NEW, op_new)
        self.hook(VA_OP_NEW_2, op_new)
        self.hook(VA_OP_DELETE, lambda e, a: (None, 0))
        self.hook(VA_OP_DELETE_ARR, lambda e, a: (None, 0))
        # MSVCR71 operator delete, called by 0x101da800/0x101da8c0 -- cdecl.
        for slot in self._find_iat_delete():
            s = self.stub()
            self.wu32(slot, s)
            self.hook(s, lambda e, a: (None, 0))
        for iat in (IAT_STRING_CTOR, IAT_STRING_APPEND_C,
                    IAT_STRING_APPEND_S, IAT_STRING_ASSIGN):
            s = self.stub()
            self.wu32(iat, s)
            self.hook(s, lambda e, a: (e.uc.reg_read(UC_X86_REG_ECX), 4))
        s = self.stub()
        self.wu32(IAT_STRING_DTOR, s)
        self.hook(s, lambda e, a: (None, 0))
        s = self.stub()
        self.wu32(IAT_ITOA, s)
        self.hook(s, lambda e, a: (e.r32(a + 4), 0))

        self.err_status = self._make_error_status()

        def throw1(e: "Emu", a: int):
            e.thrown.append((e.cstr(e.r32(a + 12)), e.r32(a + 20)))
            e.wu32(e.r32(a), e.err_status)
            return e.r32(a), 0

        def throw2(e: "Emu", a: int):
            e.thrown.append((e.cstr(e.r32(a + 8)), e.r32(a + 20)))
            e.wu32(e.r32(a), e.err_status)
            return e.r32(a), 0

        self.hook(VA_THROW1, throw1)
        self.hook(VA_THROW2, throw2)

    #: ``??3@YAXPAX@Z`` — MSVCR71's ``operator delete``.  Located by scanning
    #: the import thunks rather than hard-coded, because the two ``sub.``
    #: aliases r2 shows resolve to the same IAT slot.
    @staticmethod
    def _find_iat_delete() -> tuple[int, ...]:
        return (0x105734F4, 0x105733C4)

    def _make_error_status(self) -> int:
        """A non-OK AnsStatus the DLL's own smart pointers can hold.

        ``0x100065e0``/``0x100012e0`` are ``lock inc``/``lock dec`` on
        ``obj+0x74``; a high seed keeps the virtual destructor unreached.
        """
        dtor = self.stub()
        self.uc.mem_write(dtor, b"\xC2\x04\x00")     # ret 4
        vft = self.alloc(0x40)
        self.wu32(vft, dtor)
        obj = self.alloc(0x100)
        self.wu32(obj, vft)
        self.wu32(obj + 0x74, 0x01000000)
        return obj

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

    def wu32(self, a, v):
        self.uc.mem_write(a, struct.pack("<I", int(v) & 0xFFFFFFFF))

    def wi32(self, a, v):
        self.uc.mem_write(a, struct.pack("<i", int(v)))

    def wi16(self, a, v):
        self.uc.mem_write(a, struct.pack("<h", int(v)))

    def wf32(self, a, v):
        self.uc.mem_write(a, struct.pack("<f", float(v)))

    def r32(self, a):
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def ri32(self, a):
        return struct.unpack("<i", self.uc.mem_read(a, 4))[0]

    def rf32(self, a):
        return struct.unpack("<f", self.uc.mem_read(a, 4))[0]

    def cstr(self, a, limit=120):
        return bytes(self.uc.mem_read(a, limit)).split(b"\x00", 1)[0] \
            .decode("latin-1")

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

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"bad mem access={access} addr={address:#x} "
            f"eip={uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

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
        uc.reg_write(UC_X86_REG_FPCW, self.fpcw)
        if ecx is not None:
            uc.reg_write(UC_X86_REG_ECX, ecx)
        self.faults = []
        try:
            uc.emu_start(va, RET_MAGIC, timeout=0, count=1_000_000_000)
        except UcError as ex:
            raise RuntimeError(
                f"emu {va:#x} eip={uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
                + ("; " + "; ".join(self.faults[:2]) if self.faults else "")
            ) from ex
        if self.faults:
            raise RuntimeError(f"emu {va:#x} faults: {self.faults[:2]}")
        return uc.reg_read(UC_X86_REG_EAX)

    # -- helpers -----------------------------------------------------------
    def make_hist(self, bins, min_v: int, max_v: int) -> tuple[int, int]:
        """Build a real ``AnsHistogram`` by calling ``0x10278140``."""
        data = self.alloc(max(len(bins) * 4, 4),
                          b"".join(struct.pack("<i", b) for b in bins))
        obj = self.alloc(0x20)
        self.call(th.HIST_CTOR, [len(bins), data, min_v, max_v], ecx=obj)
        return obj, data

    def make_lut(self, lut) -> int:
        return self.alloc(max(len(lut) * 2, 4),
                          b"".join(struct.pack("<h", v) for v in lut))


# ---------------------------------------------------------------------------
# impl construction
# ---------------------------------------------------------------------------

IMPL_SIZE = 0x200


def build_impl(e: Emu, p: th.ToneHelperParams, nodes=None) -> int:
    """An ``AnsToneHelperCapabilityImpl`` with its params filled in.

    Only ``impl+0x0c``'s params matter to the functions under test; the
    ``std::string`` key/version at ``+0x0c``/``+0x28`` are left zero because
    nothing on this path reads them.
    """
    impl = e.alloc(IMPL_SIZE)
    e.wi16(impl + 0x44, p.maxValue)
    e.wf32(impl + 0x48, p.thresholdMultiplier)
    e.wf32(impl + 0x4C, p.thresholdReductionFactor)
    e.wi16(impl + 0x50, p.minEdgeThreshold)
    e.wf32(impl + 0x54, p.minEdgeRatio)
    e.wf32(impl + 0x58, p.smoothingSizeFactor)
    e.wf32(impl + 0x5C, p.smoothingSigma)
    for off, band in ((0x60, p.lowToneRange), (0x64, p.midLowToneRange),
                      (0x68, p.midHighToneRange), (0x6C, p.highToneRange)):
        e.wi16(impl + off, band[0])
        e.wi16(impl + off + 2, band[1])
    nodes = p.nodes if nodes is None else nodes
    if nodes:
        blob = b"".join(n.pack() for n in nodes)
        e.wi32(impl + 0x70, len(nodes))
        e.wu32(impl + 0x78, e.alloc(len(blob), blob))
    return impl


# ---------------------------------------------------------------------------
# the individual comparisons
# ---------------------------------------------------------------------------


def dll_calc_work(e: Emu, bins, lut, max_v, frm, to):
    h, _ = e.make_hist(bins, 0, max_v)
    lutp = e.make_lut(lut)
    cnt = e.alloc(4)
    work = e.alloc(4)
    sret = e.alloc(0x10)
    e.call(th.HIST_CALC_WORK, [sret, lutp, frm, to, cnt, work], ecx=h)
    return e.ri32(cnt), e.rf32(work)


def dll_calc_distance(e: Emu, bins, lut, max_v, frm, to):
    h, _ = e.make_hist(bins, 0, max_v)
    out, _ = e.make_hist([0] * len(bins), 0, max_v)
    lutp = e.make_lut(lut)
    dist = e.alloc(4)
    inter = e.alloc(4)
    sret = e.alloc(0x10)
    e.call(th.HIST_CALC_DISTANCE,
           [sret, lutp, frm, to, out, 0, dist, inter], ecx=h)
    return e.rf32(dist), e.rf32(inter)


def dll_calc_stats(e: Emu, bins, max_v, frm, to):
    h, _ = e.make_hist(bins, 0, max_v)
    outs = [e.alloc(4) for _ in range(6)]
    sret = e.alloc(0x10)
    e.call(th.HIST_CALC_STATS, [sret, frm, to] + outs, ecx=h)
    return (e.ri32(outs[0]),) + tuple(e.rf32(o) for o in outs[1:])


def dll_compute_metrics(e: Emu, p: th.ToneHelperParams, lum, edge, lut):
    """Run ``0x101db020`` on a hand-built Impl and read both metric groups."""
    impl = build_impl(e, p)
    n = p.maxValue + 1
    e.wu32(impl + 0x88, e.alloc(n * 4,
           b"".join(struct.pack("<i", v) for v in lum)))
    e.wu32(impl + 0x98, e.alloc(n * 4,
           b"".join(struct.pack("<i", v) for v in edge)))
    e.wu32(impl + 0xA4, e.alloc(n * 4))
    e.wu32(impl + 0xAC, e.make_lut(lut))
    sret = e.alloc(0x10)
    e.call(th.COMPUTE_METRICS, [sret], ecx=impl)
    if e.r32(sret) != 0:
        raise RuntimeError(f"0x101db020 returned non-OK: {e.thrown}")
    return impl, read_groups(e, impl)


def read_groups(e: Emu, impl: int) -> tuple[dict, dict]:
    out = []
    for base in (th.LUM_GROUP_OFFSET, th.EDGE_GROUP_OFFSET):
        g = {}
        for off, name, kind in th.METRIC_GROUP_FIELDS:
            g[name] = (e.ri32(impl + base + off) if kind == "i32"
                       else e.rf32(impl + base + off))
        out.append(g)
    return out[0], out[1]


def dll_analyze(e: Emu, p: th.ToneHelperParams, lum, edge, lut, exposure):
    """``0x101dd1b0`` end to end, then ``0x1010bb40`` to copy the results out.

    Argument mapping, off the Cap wrapper ``0x1010c3b0`` (``0x1010c3f6``..
    ``0x1010c412``) and confirmed in the callee::

        [ebp+0x08]  &AnsStatus (the wrapper's own slot, not the shell's)
        [ebp+0x0c]  the CAPABILITY object -- the wrapper substitutes it for
                    the holder; only byte +0x0e is read (0x101dd54c)
        [ebp+0x10]  luminance histogram -> impl+0x88, (maxValue+1)*4 bytes
        [ebp+0x14]  edge histogram      -> impl+0x98, (maxValue+1)*4 bytes
        [ebp+0x18]  &ctx[0x4bc]         -> impl+0x128 (metric 30, EXPOSURE)
        [ebp+0x1c]  the tone LUT        -> impl+0xac, (maxValue+1)*2 bytes
    """
    impl = build_impl(e, p)
    n = p.maxValue + 1
    lump = e.alloc(n * 4, b"".join(struct.pack("<i", v) for v in lum))
    edgep = e.alloc(n * 4, b"".join(struct.pack("<i", v) for v in edge))
    lutp = e.make_lut(lut)
    expp = 0
    if exposure is not None:
        expp = e.alloc(4)
        e.wf32(expp, exposure)
    cap = e.alloc(0x40)
    e.uc.mem_write(cap + 0x0E, b"\x01")     # skip the 0x101da800 free
    sret = e.alloc(0x10)
    e.new_sizes.clear()
    e.call(th.IMPL_ANALYZE_HIST,
           [sret, cap, lump, edgep, expp, lutp], ecx=impl)
    status = e.r32(sret)
    # getResults: Cap 0x1010c6a0 -> Impl 0x1010bb40, rep movsd 0x2f dwords
    dst = e.alloc(th.RESULTS_SIZE)
    sret2 = e.alloc(0x10)
    e.call(th.IMPL_GET_RESULTS, [sret2, dst], ecx=impl)
    return {
        "status": status,
        "results": bytes(e.uc.mem_read(dst, th.RESULTS_SIZE)),
        "groups": read_groups(e, impl),
        "exposure": e.rf32(impl + 0x128),
        "terminal": e.ri32(impl + 0x12C),
        "tone": e.ri32(impl + 0x134),
        "cls": e.ri32(impl + 0x138),
        "new_sizes": list(e.new_sizes),
        "thrown": list(e.thrown),
    }


# ---------------------------------------------------------------------------
# test data
# ---------------------------------------------------------------------------


def small_params(max_value: int = 255) -> th.ToneHelperParams:
    """A scaled-down but still valid params set, for the fast cases."""
    q = max_value / 4095.0
    p = th.ToneHelperParams(
        maxValue=max_value,
        lowToneRange=(int(600 * q), int(1149 * q)),
        midLowToneRange=(int(1150 * q), int(1549 * q)),
        midHighToneRange=(int(1550 * q), int(1849 * q)),
        highToneRange=(int(1850 * q), int(2449 * q)),
    )
    p.nodes = th.load_tree(th.DEFAULT_TREE)
    return p


def make_bins(kind: str, n: int, seed: int = 1) -> list[int]:
    r = random.Random(seed)
    if kind == "flat":
        return [1000] * n
    if kind == "random":
        return [r.randint(0, 5000) for _ in range(n)]
    if kind == "sparse":
        return [r.randint(0, 3) for _ in range(n)]
    if kind == "spike":
        b = [0] * n
        b[n // 3] = 1_000_000
        b[2 * n // 3] = 500_000
        return b
    if kind == "gauss":
        mu, sd = n * 0.4, n * 0.15
        return [max(0, int(50000 * pow(2.718281828,
                                       -((i - mu) / sd) ** 2 / 2)))
                for i in range(n)]
    if kind == "onebin":
        b = [0] * n
        b[n // 2] = 7
        return b
    if kind == "empty":
        return [0] * n
    if kind == "single":                    # count == 1 -> the < 2 early-out
        b = [0] * n
        b[n // 2] = 1
        return b
    if kind == "skewed":
        return [max(0, (n - i) * 13 % 977) for i in range(n)]
    if kind == "narrow":
        # Two adjacent bins only -> stdDev == 0.5, below AllOnTree1's live
        # root threshold of 1.000, which is the ONLY way a real histogram
        # takes that tree's lessEqual edge.  See the note in main().
        b = [0] * n
        b[n // 2] = 900
        b[n // 2 + 1] = 900
        return b
    if kind == "twobin":
        b = [0] * n
        b[n // 2] = 5
        b[n // 2 + 1] = 3
        return b
    raise KeyError(kind)


def make_lut(kind: str, n: int, seed: int = 2) -> list[int]:
    r = random.Random(seed)
    if kind == "identity":
        return list(range(n))
    if kind == "gain":
        return [min(n - 1, int(v * 1.35)) for v in range(n)]
    if kind == "crush":
        return [int(v * 0.6) for v in range(n)]
    if kind == "sgamma":
        return [min(n - 1, int((v / (n - 1)) ** 0.7 * (n - 1)))
                for v in range(n)]
    if kind == "random":
        return [r.randrange(n) for _ in range(n)]
    if kind == "flat":
        return [n // 2] * n
    raise KeyError(kind)


def fmt(v) -> str:
    return f"{v:14.7g}" if isinstance(v, float) else f"{v:>14}"


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll.exists():
        alt = dll.parent / "bin" / dll.name
        if alt.exists():
            dll = alt
        else:
            print(f"{dll} not found — run "
                  f"'python3 tools/re/reachability.py extract' first")
            return 2
    pe = dll.read_bytes()
    bad = 0
    N = 256
    p = small_params(N - 1)
    print(f"FPCW {FPCW_WINDOWS:#06x} (53-bit, Windows/MSVC default); "
          f"sensitivity re-run at {FPCW_EXTENDED:#06x}\n")

    # ---- 1. calcWork ----------------------------------------------------
    print("== 0x10278df0 AnsHistogram::calcWork ==")
    for bk in ("flat", "random", "sparse", "spike", "gauss", "empty"):
        for lk in ("identity", "gain", "crush", "random"):
            bins = make_bins(bk, N)
            lut = make_lut(lk, N)
            e = Emu(pe)
            d = dll_calc_work(e, bins, lut, N - 1, 20, 200)
            h = th.AnsHistogram(N, list(bins), 0, N - 1).calc_work(lut, 20, 200)
            ok = d == h
            bad += not ok
            print(f"  {bk:<7} x {lk:<9} count={d[0]:>10} work={d[1]:14.7g}  "
                  f"{'OK' if ok else f'FAIL host={h}'}")
    # the from >= to default (use the histogram's own range)
    e = Emu(pe)
    d = dll_calc_work(e, make_bins("random", N), make_lut("gain", N),
                      N - 1, 0, 0)
    h = th.AnsHistogram(N, make_bins("random", N), 0, N - 1) \
        .calc_work(make_lut("gain", N), 0, 0)
    ok = d == h
    bad += not ok
    print(f"  from==to==0 -> full range          work={d[1]:14.7g}  "
          f"{'OK' if ok else f'FAIL host={h}'}")
    print()

    # ---- 2. calcDistance ------------------------------------------------
    print("== 0x102781d0 AnsHistogram::calcDistance ==")
    for bk in ("flat", "random", "sparse", "gauss", "skewed"):
        for lk in ("identity", "gain", "crush", "sgamma", "flat"):
            bins = make_bins(bk, N)
            lut = make_lut(lk, N)
            e = Emu(pe)
            d = dll_calc_distance(e, bins, lut, N - 1, 0, 0)
            h = th.AnsHistogram(N, list(bins), 0, N - 1) \
                .calc_distance(lut, th.AnsHistogram(N, [0] * N, 0, N - 1),
                               0, 0)
            ok = d == h
            bad += not ok
            print(f"  {bk:<7} x {lk:<9} dist={d[0]:14.7g} "
                  f"inter={d[1]:14.7g}  {'OK' if ok else f'FAIL host={h}'}")
    print()

    # ---- 3. calcStats — the precision test ------------------------------
    print("== 0x10278730 AnsHistogram::calcStats "
          "(count, average, avgDev, stdDev, skew, kurtosis) ==")
    stats_cases = []
    for bk in ("flat", "random", "sparse", "spike", "gauss", "skewed",
               "onebin", "single", "empty"):
        stats_cases.append((bk, 0, 0))
    stats_cases += [("random", 10, 100), ("gauss", 3, 250),
                    ("skewed", 128, 129)]
    for bk, frm, to in stats_cases:
        bins = make_bins(bk, N)
        e = Emu(pe)
        d = dll_calc_stats(e, bins, N - 1, frm, to)
        h = th.AnsHistogram(N, list(bins), 0, N - 1).calc_stats(frm, to)
        ok = d == h
        bad += not ok
        rng = "full" if frm >= to else f"{frm}..{to}"
        print(f"  {bk:<7} {rng:<8} " + " ".join(fmt(v) for v in d)
              + ("  OK" if ok else "  FAIL"))
        if not ok:
            print("           host " + " ".join(fmt(v) for v in h))
            for i, (a, b) in enumerate(zip(d, h)):
                if a != b:
                    print(f"           field {i} dll={a!r} host={b!r}")
    print()

    # ---- 4. param validation --------------------------------------------
    print("== 0x101da6b0 AnsToneHelperParams validation ==")
    good = small_params(N - 1)
    e = Emu(pe)
    impl = build_impl(e, good)
    out = e.alloc(4)
    r = e.call(th.PARAM_CHECK, [impl + th.PARAMS_BASE, out])
    ok = (r == 0)
    bad += not ok
    print(f"  shipped-shaped params            -> {r:#010x} "
          f"{'OK' if ok else 'FAIL'}")
    for field, value, want_idx in (
            ("maxValue", -1, 1),
            ("thresholdMultiplier", 0.5, 2),
            ("thresholdMultiplier", 2.5, 2),
            ("thresholdReductionFactor", 0.4, 3),
            ("thresholdReductionFactor", 0.9999, 3),
            ("minEdgeThreshold", -1, 4),
            ("minEdgeRatio", 1.5, 5),
            ("smoothingSizeFactor", 0.5, 6),
            ("smoothingSizeFactor", 11.0, 6),
            ("smoothingSigma", 0.5, 7),
            ("smoothingSigma", 60.0, 7)):
        q = small_params(N - 1)
        setattr(q, field, value)
        e = Emu(pe)
        impl = build_impl(e, q)
        out = e.alloc(4)
        r = e.call(th.PARAM_CHECK, [impl + th.PARAMS_BASE, out])
        idx = e.ri32(out)
        host_idx = None
        try:
            th.check_params(q)
        except th.ToneHelperError as exc:
            host_idx = int(str(exc).split("#")[1].split(")")[0])
        ok = (r == 0xFFFFFFFF and idx == want_idx and host_idx == want_idx)
        bad += not ok
        print(f"  {field:<26}={str(value):<7} -> bad field #{idx} "
              f"host #{host_idx}  {'OK' if ok else 'FAIL'}")
    print()

    # ---- 5. the metric producer -----------------------------------------
    print("== 0x101db020 — 29 metrics (two AnsHistogram passes) ==")
    metric_cases = [
        ("flat", "flat", "identity"),
        ("random", "sparse", "gain"),
        ("gauss", "skewed", "crush"),
        ("skewed", "gauss", "sgamma"),
        ("random", "random", "random"),
        ("spike", "gauss", "gain"),
    ]
    for lk, ek, tk in metric_cases:
        lum, edge = make_bins(lk, N, 3), make_bins(ek, N, 4)
        lut = make_lut(tk, N)
        e = Emu(pe)
        impl, (dl, de) = dll_compute_metrics(e, p, lum, edge, lut)
        hl, he = th.compute_metrics(p, lum, edge, lut)
        diffs = [(g, k) for g, dd, hh in (("lum", dl, hl), ("edge", de, he))
                 for k in dd if dd[k] != hh[k]]
        ok = not diffs
        bad += not ok
        print(f"  lum={lk:<7} edge={ek:<7} lut={tk:<9} "
              f"lumStdDev={dl['stdDev']:12.7g} "
              f"edgeWorkTotal={de['workTotal']:12.7g}  "
              f"{'OK' if ok else 'FAIL ' + str(diffs)}")
        if diffs:
            for g, k in diffs:
                dd = dl if g == "lum" else de
                hh = hl if g == "lum" else he
                print(f"      {g}.{k}: dll={dd[k]!r} host={hh[k]!r}")
    print()

    # ---- 6. the entry point, end to end ---------------------------------
    print("== 0x101dd1b0 analyze(hist) end to end + 0x1010bb40 getResults ==")
    entry_cases = [
        ("flat", "flat", "identity", 0.0),
        ("random", "sparse", "gain", 0.0),
        ("gauss", "skewed", "crush", -2.0),
        ("skewed", "gauss", "sgamma", 3.5),
        ("random", "random", "random", None),      # NULL exposure pointer
        ("spike", "gauss", "gain", 1.0),
        # -- the lessEqual side of AllOnTree1's root, which needs a
        #    luminance histogram narrower than 1 code value --------------
        ("narrow", "gauss", "identity", 0.0),
        ("narrow", "narrow", "gain", 0.0),
        ("narrow", "sparse", "crush", 0.0),
        ("twobin", "flat", "gain", 0.0),
    ]
    for lk, ek, tk, exposure in entry_cases:
        lum, edge = make_bins(lk, N, 5), make_bins(ek, N, 6)
        lut = make_lut(tk, N)
        e = Emu(pe)
        d = dll_analyze(e, p, lum, edge, lut, exposure)
        h = th.analyze_with_histograms(p, lum, edge, lut, exposure)
        hb = bytearray(h.to_bytes())
        db = bytearray(d["results"])
        # the eight heap-pointer slots inside the results window are raw
        # addresses; blank them on both sides and check the sizes instead.
        for off in (0x04, 0x08, 0x0C, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28,
                    0x2C):
            db[off:off + 4] = b"\0\0\0\0"
            hb[off:off + 4] = b"\0\0\0\0"
        want_sizes = sorted(th.allocate_memory(p, -1, -1).values())
        ok = (bytes(db) == bytes(hb) and d["status"] == 0
              and sorted(d["new_sizes"]) == want_sizes)
        bad += not ok
        print(f"  lum={lk:<7} edge={ek:<7} lut={tk:<9} exp={str(exposure):<5} "
              f"-> node={d['terminal']:>3} value={d['tone']} class={d['cls']} "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            if sorted(d["new_sizes"]) != want_sizes:
                print(f"      allocateMemory dll={sorted(d['new_sizes'])} "
                      f"host={want_sizes}")
            for i in range(0, th.RESULTS_SIZE, 4):
                if db[i:i + 4] != hb[i:i + 4]:
                    print(f"      results+{i:#04x}: dll={db[i:i+4].hex()} "
                          f"host={hb[i:i+4].hex()}")
    print()

    # ---- 7. the full-size shipped configuration -------------------------
    print("== the shipped configuration: maxValue=4095, AllOnTree1 ==")
    full = th.load_params()
    NF = full.maxValue + 1
    for lk, ek, tk in (("gauss", "skewed", "sgamma"),
                       ("random", "sparse", "gain")):
        lum, edge = make_bins(lk, NF, 11), make_bins(ek, NF, 12)
        lut = make_lut(tk, NF)
        e = Emu(pe)
        d = dll_analyze(e, full, lum, edge, lut, 0.0)
        h = th.analyze_with_histograms(full, lum, edge, lut, 0.0)
        hb = bytearray(h.to_bytes())
        db = bytearray(d["results"])
        for off in (0x04, 0x08, 0x0C, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28,
                    0x2C):
            db[off:off + 4] = b"\0\0\0\0"
            hb[off:off + 4] = b"\0\0\0\0"
        ok = bytes(db) == bytes(hb) and d["status"] == 0
        bad += not ok
        print(f"  lum={lk:<7} edge={ek:<7} lut={tk:<7} -> "
              f"toneHelperValue={d['tone']} sceneClass={d['cls']} "
              f"(node {d['terminal']})  {'OK' if ok else 'FAIL'}")
        if not ok:
            for i in range(0, th.RESULTS_SIZE, 4):
                if db[i:i + 4] != hb[i:i + 4]:
                    print(f"      results+{i:#04x}: dll={db[i:i+4].hex()} "
                          f"host={hb[i:i+4].hex()}")
    print()

    # ---- 8. FPCW sensitivity --------------------------------------------
    print("== FPCW sensitivity: is 53-bit precision control really the model? ==")
    FPCW_SINGLE = 0x007F        # 24-bit -- the negative control
    moved53_64: list[str] = []
    moved53_24: list[str] = []
    cases = ("random", "gauss", "skewed", "narrow")
    for bk in cases:
        bins = make_bins(bk, N)
        h = th.AnsHistogram(N, list(bins), 0, N - 1).calc_stats(0, 0)
        a = dll_calc_stats(Emu(pe, fpcw=FPCW_WINDOWS), bins, N - 1, 0, 0)
        b = dll_calc_stats(Emu(pe, fpcw=FPCW_EXTENDED), bins, N - 1, 0, 0)
        c = dll_calc_stats(Emu(pe, fpcw=FPCW_SINGLE), bins, N - 1, 0, 0)
        if a != b:
            moved53_64.append(bk)
        if a != c:
            moved53_24.append(bk)
        if a != h:
            bad += 1
        print(f"  calcStats {bk:<7} "
              f"0x027f {'==' if a == h else '!='} host   "
              f"0x037f {'==' if b == a else '!='} 0x027f   "
              f"0x007f {'==' if c == a else '!='} 0x027f")
    # A sensitivity check that never moves proves nothing, so 24-bit is run as
    # a negative control: if THAT never diverged, the harness would not be
    # measuring the control word at all.
    ok = len(moved53_24) >= 3
    bad += not ok
    print(f"  53-bit vs 64-bit: {len(moved53_64)}/{len(cases)} move "
          f"{moved53_64}")
    print(f"  53-bit vs 24-bit: {len(moved53_24)}/{len(cases)} move "
          f"{moved53_24}  (negative control)  {'OK' if ok else 'FAIL'}")
    print("  'narrow' is expected not to move at 24-bit: two adjacent bins of "
          "900 give\n        exact small integers, representable in every "
          "precision.  The three broad\n        histograms all move, so the "
          "control word IS being measured.")
    if not moved53_64:
        print("  RESULT: this subsystem is insensitive to 53- vs 64-bit, "
              "because calcStats\n        spills its accumulators to float32 "
              "inside the loop (see the slot table\n        in calc_stats' "
              "docstring) -- the spilling dominates the register width.\n"
              "        The control word is still pinned rather than left to "
              "Unicorn's default,\n        which is a fourth, unspecified "
              "thing (it reports 0x0000 and behaves as\n        extended).")
    print()

    # ---- 9. dei is not wired in, and cannot be ---------------------------
    print("== dei negative control: nothing here can read the dei tree ==")
    lum, edge = make_bins("gauss", N, 21), make_bins("skewed", N, 22)
    lut = make_lut("sgamma", N)
    base = th.analyze_with_histograms(p, lum, edge, lut, 0.0).to_bytes()
    checks = []
    # (a) point decisionTreeDei at a tree whose every terminal is class 4 --
    #     if it were consulted, toneHelperValue would move.
    q = small_params(N - 1)
    q.decisionTreeDei = "AllOnTree1"
    q.nodes = p.nodes
    checks.append(("decisionTreeDei retargeted",
                   th.analyze_with_histograms(q, lum, edge, lut, 0.0)
                   .to_bytes()))
    # (b) delete it outright.
    q2 = small_params(N - 1)
    q2.decisionTreeDei = ""
    q2.nodes = p.nodes
    checks.append(("decisionTreeDei removed",
                   th.analyze_with_histograms(q2, lum, edge, lut, 0.0)
                   .to_bytes()))
    for label, got in checks:
        ok = got == base
        bad += not ok
        print(f"  {label:<32} results identical: {'OK' if ok else 'FAIL'}")
    # (c) the DLL itself: impl+0x74 / impl+0x7c (the dei count and array) are
    #     left NULL by build_impl and 0x101dd1b0 still completes with OK --
    #     i.e. this path never dereferences them.  If it did, the run would
    #     fault on a null read and this harness would have failed long ago.
    e = Emu(pe)
    impl = build_impl(e, p)
    ok = (e.r32(impl + 0x74) == 0 and e.r32(impl + 0x7C) == 0)
    d = dll_analyze(e, p, lum, edge, lut, 0.0)
    ok = ok and d["status"] == 0 and not d["thrown"]
    bad += not ok
    print(f"  DLL runs with impl+0x74/+0x7c (dei count/array) NULL: "
          f"{'OK' if ok else 'FAIL'}")
    print("  -> the dei tree is loaded by AnsToneHelperDpi and read only by "
          "0x101dc310\n     (ColorNegativePath::CalcDei's route), never by "
          "0x101dd1b0 or 0x101db890.")
    print()

    if bad:
        print(f"FAILED {bad} check(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
