#!/usr/bin/env python3
r"""Golden ``AnsContrastAdjustCapabilityImpl::analyze`` vs PakonIMAu.dll.

WHAT RUNS FOR REAL
==================
``0x101d8240`` executes start to finish on every case, and with it every piece
of contrast's actual arithmetic:

    0x101d8240  analyze            the mode dispatch + COMBINE/OVERRIDE compose
    0x101d2e50  <free buffers>
    0x101d2ad0  <ramp builder>     xxx_WITH_SLOPE
    0x101d2c80  <segment builder>  xxx_WITH_POINT
    0x101d2eb0  constrainSlope     (its own dedicated harness is
                                    pakon_contrast_slope_golden.py; here it is
                                    verified *in situ*, reached through
                                    bConstrainSlope)
    0x104ffe44  __ftol             real code in the image, not an IAT thunk --
                                   so the vendor's exact truncate-toward-zero
                                   rounding is what runs

The second half of the file drives the real ``0x101d8880`` front end as well,
which additionally runs ``0x1005dab0`` (the params ctor, i.e. every default in
``ContrastParams``), ``0x101d7e70`` setParams, ``0x1010b450`` the params
``operator=`` and ``0x101d3860`` validateParams for real.

WHAT IS STUBBED (and why none of it is vendor arithmetic)
=========================================================
* ``operator new`` ``0x104ffd53`` (``operator new[]`` ``0x104ffd78`` jumps
  straight into it) -> a bump allocator that zeroes.  The real one reaches
  ``malloc``; the CRT never initialised because the PE is loaded unbound.
  Zeroing matters: ``xxx_WITH_SLOPE`` does not memset its adjustment buffer, it
  relies on the two ramps covering ``[0, lutSize)``, so an allocator that
  returned garbage would make the test depend on heap contents.
* ``operator delete[]`` ``0x104ffe3e`` -- an *unbound IAT thunk* in the shipped
  file (``jmp dword [0x105735e8]``), so there is no vendor code to run.  The
  stub is a no-op; the harness reads each buffer's contents *before* the frees
  and separately asserts the pointer NULLing that the ``cap+0xe`` branch does.
* MSVCP71 ``basic_string`` ctor/dtor/assign and the ``ostringstream``
  ctor/dtor -- CRT.  Only ``0x1005dab0``, ``0x1010b450`` and ``0x101d3860``'s
  *success* path touch them, and on that path they are pure bookkeeping around
  strings this subsystem never reads.
* ``0x10021730`` (resolve the scene holder) and ``0x101d5d20``
  (``selectParams``) in the front-end section: behind them is the live
  ``std::map``/``ostringstream`` DPI registry walk, which is built at library
  *initialisation* and is therefore not part of what ``analyzeAutoTone``
  executes.  Both stubs reproduce the contract exactly -- write the OK status
  into the hidden ``AnsStatus&``, fill the caller's params object -- and the
  failure paths are exercised too, by returning a non-OK status and checking
  the ``.cpp`` 176/185 log lines.

FLOATING POINT
==============
``FPCW`` is forced to ``0x027f`` (53-bit mantissa, round-nearest): the Windows
CRT default, and the only setting under which x87 intermediates are bit-equal
to a Python ``float``.  Unicorn powers up at ``0x0000`` (24-bit!), so leaving
it alone would compare the port against arithmetic the scanner never did.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_contrast_lut_golden.py [dll]``

The DLL is not in the repo.  Extract it with
``python3 tools/re/reachability.py extract`` (default ``/tmp/pakon_re``).
"""
from __future__ import annotations

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

import pakon_contrast as cx

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x02000000            # must not run into IMAGE_BASE at 0x10000000
SCRATCH = 0x00100000
RET_MAGIC = 0x00110000

#: The Windows CRT's x87 control word: 53-bit mantissa, round to nearest.
FPCW_WINDOWS = 0x027F

VA_OP_NEW = cx.OP_NEW
VA_OP_DELETE = 0x104FFDD0           # operator delete (std::vector's dealloc)
VA_OP_DELETE_ARR = cx.OP_DELETE_ARR
VA_THROW = 0x1001ED90
VA_LOG_STATUS = 0x1001F650          # status->log(func, file, line)

IAT_STRING_CTOR = 0x10573394        # basic_string::basic_string(const char*)
IAT_STRING_DTOR = 0x10573418        # basic_string::~basic_string()
IAT_STRING_ASSIGN = 0x10573134      # basic_string::operator=
IAT_OSTRINGSTREAM_CTOR = 0x10573248
IAT_OSTRINGSTREAM_DTOR = 0x105735A4
#: validateParams' *error* path only: ostream::operator<< for a literal and for
#: a formatted buffer, plus the CRT ``sprintf`` between them.  Pure message
#: construction -- the pass/fail decision is already made by the time any of
#: these run, and the harness observes that decision through the returned
#: AnsStatus, not through the text.
IAT_OSTREAM_INS_LITERAL = 0x1057327C   # thiscall, 1 arg
IAT_OSTREAM_INS_BUFFER = 0x105731D4    # thiscall, 1 arg
IAT_SPRINTF = 0x105735F4               # cdecl, caller cleans

DEFAULT_DLL = Path("/tmp/pakon_re/PakonIMAu.dll")


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    """PakonIMAu.dll under Unicorn: bump heap, CRT stubs, Windows FPCW."""

    def __init__(self, pe: bytes, fpcw: int = FPCW_WINDOWS):
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self.pe = pe
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
        self.thrown: list[tuple[str, int]] = []
        self.logged: list[tuple[str, int]] = []
        uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)

        # operator new / new[] -- zeroing bump allocator.
        self.hook(VA_OP_NEW, lambda e, a: (e.alloc(max(e.r32(a), 4)), 0))
        self.hook(VA_OP_DELETE, lambda e, a: (None, 0))
        self.hook(VA_OP_DELETE_ARR, lambda e, a: (None, 0))

        # MSVCP71 string / ostringstream: no-ops returning ``this``.  See the
        # module docstring.  The pop count is per call site, taken from the
        # disassembly -- ``basic_string(const char*)`` and ``operator=`` take
        # one stack argument, the ostringstream ctor/dtor take none.
        for iat, pop in ((IAT_STRING_CTOR, 4), (IAT_STRING_ASSIGN, 4),
                         (IAT_OSTRINGSTREAM_CTOR, 0),
                         (IAT_OSTREAM_INS_LITERAL, 4),
                         (IAT_OSTREAM_INS_BUFFER, 4),
                         (IAT_SPRINTF, 0)):
            s = self.stub()
            self.wu32(iat, s)
            self.hook(s, self._make_ret_this(pop))
        for iat in (IAT_STRING_DTOR, IAT_OSTRINGSTREAM_DTOR):
            s = self.stub()
            self.wu32(iat, s)
            self.hook(s, lambda e, a: (None, 0))

        self.error_status = self.err_status()

        # 0x1001ed90: the "<msg>" status builder -- record the message and hand
        # back a *non-OK* status.  Writing the OK sentinel here would silently
        # convert every vendor error path into a success and make the harness
        # agree with anything: with an OK-returning stub, validateParams reports
        # success for a midpoint of 9000 and a slope of 0.05.
        def throw(e: "Emu", args: int):
            sret = e.r32(args)
            msg = e.cstr(e.r32(args + 12))
            line = e.r32(args + 20)
            self.thrown.append((msg, line))
            e.wu32(sret, self.error_status)
            return sret, 0                      # cdecl
        self.hook(VA_THROW, throw)

        # 0x1001f650: status->log(func, file, line) -- record, do not execute.
        # Behind it is the real 0x1001f540 sink, which formats through MSVCP71
        # and then dispatches a virtual off the formatted object; letting it
        # run would be testing the CRT.  The `.cpp` line it is handed is the
        # observable this harness checks.
        def logsink(e: "Emu", args: int):
            self.logged.append((e.cstr(e.r32(args)), e.r32(args + 8)))
            return None, 0x0C
        self.hook(VA_LOG_STATUS, logsink)

    def err_status(self) -> int:
        """A stand-in for a constructed non-OK ``AnsStatus``.

        Its refcount at ``+0x74`` is parked high so the ``lock dec`` in
        ``0x100012e0`` never reaches zero and the virtual destructor is never
        dispatched; every vftable slot is a ``ret 4`` stub in case it is anyway.
        """
        vdtor = self.stub()
        self.hook(vdtor, lambda e, a: (None, 4))
        vft = self.alloc(0x40)
        for i in range(0x10):
            self.wu32(vft + 4 * i, vdtor)
        obj = self.alloc(0x100)
        self.wu32(obj, vft)
        self.wu32(obj + 0x74, 1 << 20)
        return obj

    @staticmethod
    def _make_ret_this(pop: int):
        def fn(e: "Emu", _args: int):
            return e.uc.reg_read(UC_X86_REG_ECX), pop
        return fn

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

    def wu32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", int(v) & 0xFFFFFFFF))

    def r32(self, a: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def rf32(self, a: int) -> float:
        return struct.unpack("<f", self.uc.mem_read(a, 4))[0]

    def ru8(self, a: int) -> int:
        return self.uc.mem_read(a, 1)[0]

    def shorts(self, a: int, n: int) -> list[int]:
        return list(struct.unpack(f"<{n}h", self.uc.mem_read(a, 2 * n)))

    def cstr(self, a: int, limit: int = 128) -> str:
        if not a:
            return ""
        try:
            raw = bytes(self.uc.mem_read(a, limit))
        except UcError:
            return f"<unmapped {a:#x}>"
        return raw.split(b"\x00", 1)[0].decode("latin-1")

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

    # -- calling -----------------------------------------------------------
    def call(self, va: int, args=(), ecx: int | None = None) -> int:
        uc = self.uc
        esp = STACK + STACK_SZ - 0x20000
        blob = b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        esp -= len(blob)
        if blob:
            uc.mem_write(esp, blob)
        # Zero the frame the callee is about to use.  validateParams' error
        # path hands 0x10020ad0 a std::string built on the stack; with a zeroed
        # frame its length/capacity read as 0, which is the empty-string case
        # (0x10020adf) and therefore deterministic instead of heap-dependent.
        uc.mem_write(esp - 0x8000, b"\x00" * 0x8000)
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


# ---------------------------------------------------------------------------
# building an Impl in emulated memory
# ---------------------------------------------------------------------------

IMPL_SIZE = 0x1B8
PARAMS_OFF = 0x0C
RESULTS_OFF = 0x18C


def build_impl(emu: Emu, p: cx.ContrastParams, res: cx.ContrastResults) -> int:
    """Lay out the 0x1b8-byte Impl exactly as ``0x101d5e60`` leaves it."""
    impl = emu.alloc(IMPL_SIZE)
    emu.wu32(impl, cx.IMPL_VFTABLE)
    emu.wu32(impl + 4, 0)                      # refcount
    emu.wu32(impl + 8, 0)                      # AnsStatus (OK is NULL here)
    pts = emu.alloc(max(4 * len(p.points), 4), p.points_bytes())
    emu.uc.mem_write(impl + PARAMS_OFF, p.to_bytes(points_ptr=pts))
    emu.uc.mem_write(impl + RESULTS_OFF, res.to_bytes())
    return impl


def read_results(emu: Emu, impl: int, lut_size: int) -> dict:
    """Snapshot ``impl+0x18c`` -- exactly the 0x2c bytes ``0x10109d70`` copies."""
    r = impl + RESULTS_OFF
    p_adj, p_in, p_out = emu.r32(r + 0x20), emu.r32(r + 0x24), emu.r32(r + 0x28)
    return {
        "lutSize": struct.unpack("<i", emu.uc.mem_read(r, 4))[0],
        "lowSlope": emu.rf32(r + 0x04),
        "highSlope": emu.rf32(r + 0x08),
        "lowerMinSlopeLimit": emu.rf32(r + 0x0C),
        "lowerMaxSlopeLimit": emu.rf32(r + 0x10),
        "upperMinSlopeLimit": emu.rf32(r + 0x14),
        "upperMaxSlopeLimit": emu.rf32(r + 0x18),
        "bWasLowerMinLimitReached": bool(emu.ru8(r + 0x1C)),
        "bWasLowerMaxLimitReached": bool(emu.ru8(r + 0x1D)),
        "bWasUpperMinLimitReached": bool(emu.ru8(r + 0x1E)),
        "bWasUpperMaxLimitReached": bool(emu.ru8(r + 0x1F)),
        "CAdjLut": emu.shorts(p_adj, lut_size) if p_adj else None,
        "InToneLut": emu.shorts(p_in, lut_size) if p_in else None,
        "OutToneLut": emu.shorts(p_out, lut_size) if p_out else None,
    }


def host_results(r: cx.ContrastResults) -> dict:
    return {
        "lutSize": r.lutSize,
        "lowSlope": r.lowSlope,
        "highSlope": r.highSlope,
        "lowerMinSlopeLimit": r.lowerMinSlopeLimit,
        "lowerMaxSlopeLimit": r.lowerMaxSlopeLimit,
        "upperMinSlopeLimit": r.upperMinSlopeLimit,
        "upperMaxSlopeLimit": r.upperMaxSlopeLimit,
        "bWasLowerMinLimitReached": r.bWasLowerMinLimitReached,
        "bWasLowerMaxLimitReached": r.bWasLowerMaxLimitReached,
        "bWasUpperMinLimitReached": r.bWasUpperMinLimitReached,
        "bWasUpperMaxLimitReached": r.bWasUpperMaxLimitReached,
        "CAdjLut": r.CAdjLut,
        "InToneLut": r.InToneLut,
        "OutToneLut": r.OutToneLut,
    }


def run_dll_analyze(pe: bytes, p: cx.ContrastParams, res: cx.ContrastResults,
                    *, scene_type: int, x: int, tone: list | None,
                    keep: bool) -> dict:
    """Drive the real ``0x101d8240``.

    ``params`` is handed in as ``impl+0xc`` itself, which is the one case
    ``0x101d828e`` short-circuits, so ``setParams`` does not run and this
    isolates the LUT build.  The ``0x101d8880`` front end (which always passes
    a *different* object, and therefore always runs ``setParams``) is covered
    by :func:`run_dll_acquire` below.
    """
    emu = Emu(pe)
    impl = build_impl(emu, p, res)
    tone_ptr = 0
    if tone is not None:
        tone_ptr = emu.alloc(2 * len(tone),
                             struct.pack(f"<{len(tone)}h", *tone))
    sret = emu.alloc(0x10)
    emu.call(cx.IMPL_ANALYZE,
             [sret, 0, 1 if keep else 0, impl + PARAMS_OFF, scene_type, x,
              tone_ptr], ecx=impl)
    out = read_results(emu, impl, p.lutSize)
    out["thrown"] = list(emu.thrown)
    out["status_ok"] = emu.r32(sret) == 0
    return out


def run_host_analyze(p: cx.ContrastParams, res: cx.ContrastResults, *,
                     scene_type: int, x: int, tone: list | None,
                     keep: bool) -> dict:
    impl = cx.ContrastImpl(params=p.copy(), results=res)
    r = impl.analyze(None, scene_type, x, tone, keep_intermediates=keep)
    out = host_results(r)
    out["thrown"] = []
    out["status_ok"] = True
    return out


# ---------------------------------------------------------------------------
# the 0x101d8880 front end
# ---------------------------------------------------------------------------


def run_dll_acquire(pe: bytes, embedded: cx.ContrastParams,
                    selected: cx.ContrastParams, res: cx.ContrastResults, *,
                    scene_type: int, x: int, tone: list | None, keep: bool,
                    fail_holder: bool = False,
                    fail_select: bool = False) -> dict:
    """Drive the real ``0x101d8880``: holder resolve, params ctor, selectParams,
    setParams, validateParams, then the LUT build -- all vendor code except the
    two initialisation-time lookups named in the module docstring."""
    emu = Emu(pe)
    impl = build_impl(emu, embedded, res)
    tone_ptr = 0
    if tone is not None:
        tone_ptr = emu.alloc(2 * len(tone),
                             struct.pack(f"<{len(tone)}h", *tone))
    bad_status = emu.err_status()               # a non-OK AnsStatus

    # 0x10021730 -- resolve the scene holder.  Contract: *arg0 = AnsStatus,
    # *arg1 = the resolved object, returns arg0.
    def resolve(e: Emu, args: int):
        sret, out = e.r32(args), e.r32(args + 4)
        e.wu32(sret, bad_status if fail_holder else 0)
        e.wu32(out, 0)
        return sret, 8
    emu.hook(0x10021730, resolve)

    # 0x101d5d20 -- selectParams(status&, holder, outParams).  cdecl.
    sel_pts = emu.alloc(max(4 * len(selected.points), 4),
                        selected.points_bytes())
    sel_bytes = selected.to_bytes(points_ptr=sel_pts)

    def select(e: Emu, args: int):
        sret, _holder, outp = e.r32(args), e.r32(args + 4), e.r32(args + 8)
        if not fail_select:
            e.uc.mem_write(outp, sel_bytes)
        e.wu32(sret, bad_status if fail_select else 0)
        return sret, 0                          # cdecl
    emu.hook(cx.SELECT_PARAMS, select)

    sret = emu.alloc(0x10)
    emu.call(cx.IMPL_ACQUIRE,
             [sret, 0, 1 if keep else 0, scene_type, x, tone_ptr], ecx=impl)
    out = read_results(emu, impl, embedded.lutSize)
    out["params_after"] = bytes(emu.uc.mem_read(impl + PARAMS_OFF, 0x180))
    out["status_ok"] = emu.r32(sret) == 0
    out["logged"] = list(emu.logged)
    return out


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def lut_identity(n: int, max_value: int) -> list[int]:
    return [min(i, max_value) for i in range(n)]


def lut_crushed(n: int, max_value: int) -> list[int]:
    """A shadow-crushed curve: a near-flat toe, then a steep mid.

    The toe's local slope falls well under ``aLowerMinSlope`` / the shoulder's
    over ``aUpperMaxSlope``, so ``constrainSlope`` genuinely flags windows in
    both passes rather than passing everything straight through.  A test in
    which nothing is ever flagged would not exercise the regression logic at
    all -- it would only exercise the re-integration's unflagged branch.
    """
    out = []
    for i in range(n):
        t = i / (n - 1)
        if t < 0.35:
            v = t * 0.12                        # very shallow toe
        elif t < 0.75:
            v = 0.042 + (t - 0.35) * 2.1        # steep mid
        else:
            v = 0.882 + (t - 0.75) * 0.47       # shoulder
        out.append(max(0, min(max_value, int(v * max_value))))
    return out


def lut_steep(n: int, max_value: int) -> list[int]:
    """A hard-contrast curve whose middle exceeds every ``aUpperMaxSlope``."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        v = 0.5 + (t - 0.5) * 3.0
        out.append(max(0, min(max_value, int(v * max_value))))
    return out


def lut_noisy(n: int, max_value: int) -> list[int]:
    """Identity plus a deterministic ripple -- non-monotone windows."""
    out = []
    s = 12345
    for i in range(n):
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        v = i + ((s >> 16) % 41) - 20
        out.append(max(0, min(max_value, v)))
    return out


def shipped_params() -> cx.ContrastParams:
    """Parse the real ``contrast-CNEnhanced.dpi`` this unit ships with."""
    here = Path(__file__).resolve()
    dpi = (here.parents[3] / "vendor/ansel/anselinstalldir/dataPathItems"
           / "contrast/contrast-CNEnhanced.dpi")
    return cx.parse_dpi(dpi.read_text())


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------


def _p(**kw) -> cx.ContrastParams:
    return cx.ContrastParams(**kw)


def cases() -> list[tuple[str, dict]]:
    ship = shipped_params()
    small = dict(lutSize=256, maxValue=255, midpointIn=100, midpointOut=100,
                 csLowerIndex=8, csFixedIndex=100, csUpperIndex=248,
                 csGranularity=8, csNSamples=4)
    out: list[tuple[str, dict]] = [
        ("mode1 COMBINE_WITH_SLOPE, identity, slope 1.0", dict(
            params=_p(), low=1.0, high=1.0, tone=("identity",),
            scene_type=3, x=1, keep=False)),
        ("mode1, identity, slope 0.5/2.0", dict(
            params=_p(), low=0.5, high=2.0, tone=("identity",),
            scene_type=3, x=1, keep=False)),
        ("mode1, crushed tone, slope 1.0", dict(
            params=_p(), low=1.0, high=1.0, tone=("crushed",),
            scene_type=3, x=1, keep=False)),
        ("mode1, crushed tone, slope 0.0 (flat-fill branch)", dict(
            params=_p(), low=0.0, high=0.0, tone=("crushed",),
            scene_type=3, x=1, keep=False)),
        ("mode1, identity, NEGATIVE slope (zero-fill branch)", dict(
            params=_p(), low=-0.5, high=-0.5, tone=("identity",),
            scene_type=3, x=1, keep=False)),
        ("mode1, identity, slope 8.0 (maxValue-fill branch)", dict(
            params=_p(), low=8.0, high=8.0, tone=("identity",),
            scene_type=3, x=1, keep=False)),
        ("mode1 + constrainSlope, crushed tone", dict(
            params=_p(bConstrainSlope=True), low=1.0, high=1.0,
            tone=("crushed",), scene_type=3, x=1, keep=False)),
        ("mode1 + constrainSlope, steep tone", dict(
            params=_p(bConstrainSlope=True), low=1.0, high=1.0,
            tone=("steep",), scene_type=3, x=1, keep=False)),
        ("mode1 + constrainSlope, noisy tone", dict(
            params=_p(bConstrainSlope=True), low=1.0, high=1.0,
            tone=("noisy",), scene_type=3, x=1, keep=False)),
        ("mode1 + constrainSlope, identity (nothing flagged)", dict(
            params=_p(bConstrainSlope=True), low=1.0, high=1.0,
            tone=("identity",), scene_type=3, x=1, keep=False)),
        ("mode0 NO_USER_INPUT, crushed", dict(
            params=_p(userInputMode=cx.MODE_NO_USER_INPUT), low=1.0, high=1.0,
            tone=("crushed",), scene_type=3, x=1, keep=False)),
        ("mode0 + constrainSlope, crushed", dict(
            params=_p(userInputMode=cx.MODE_NO_USER_INPUT,
                      bConstrainSlope=True),
            low=1.0, high=1.0, tone=("crushed",), scene_type=3, x=1,
            keep=False)),
        ("mode2 COMBINE_WITH_POINT, 4-point polyline", dict(
            params=_p(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                      points=[(0, 0), (800, 400), (3000, 3600), (4095, 4095)]),
            low=1.0, high=1.0, tone=("crushed",), scene_type=3, x=1,
            keep=False)),
        ("mode2, polyline with a flat run", dict(
            params=_p(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                      points=[(0, 0), (500, 500), (1500, 500), (4095, 4095)]),
            low=1.0, high=1.0, tone=("identity",), scene_type=3, x=1,
            keep=False)),
        ("mode2 + constrainSlope, crushed", dict(
            params=_p(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                      bConstrainSlope=True,
                      points=[(0, 0), (900, 300), (4095, 4095)]),
            low=1.0, high=1.0, tone=("crushed",), scene_type=3, x=1,
            keep=False)),
        ("mode3 OVERRIDE_WITH_SLOPE, tone=NULL", dict(
            params=_p(userInputMode=cx.MODE_OVERRIDE_WITH_SLOPE), low=1.3,
            high=0.7, tone=None, scene_type=3, x=1, keep=False)),
        ("mode3 OVERRIDE_WITH_SLOPE, tone present (ignored)", dict(
            params=_p(userInputMode=cx.MODE_OVERRIDE_WITH_SLOPE), low=1.3,
            high=0.7, tone=("crushed",), scene_type=3, x=1, keep=False)),
        ("mode4 OVERRIDE_WITH_POINT, tone=NULL", dict(
            params=_p(userInputMode=cx.MODE_OVERRIDE_WITH_POINT,
                      points=[(0, 0), (2000, 900), (4095, 4095)]),
            low=1.0, high=1.0, tone=None, scene_type=3, x=1, keep=False)),
        ("mode1, tone=NULL (bails out, builds nothing)", dict(
            params=_p(), low=1.0, high=1.0, tone=None, scene_type=3, x=1,
            keep=False)),
        ("keep_intermediates=1 (cap+0xe forced on)", dict(
            params=_p(bConstrainSlope=True), low=1.0, high=1.0,
            tone=("crushed",), scene_type=3, x=1, keep=True)),
        ("shipped contrast-CNEnhanced.dpi, crushed, sceneType 3", dict(
            params=ship, low=ship.lowInitialSlope, high=ship.highInitialSlope,
            tone=("crushed",), scene_type=3, x=1, keep=False)),
        ("shipped .dpi, crushed, sceneType 1 (band 0)", dict(
            params=ship, low=1.0, high=1.0, tone=("crushed",), scene_type=1,
            x=1, keep=False)),
        ("shipped .dpi, crushed, sceneType 2 (band 2)", dict(
            params=ship, low=1.0, high=1.0, tone=("crushed",), scene_type=2,
            x=1, keep=False)),
        ("shipped .dpi, crushed, sceneType 6 (band 6)", dict(
            params=ship, low=1.0, high=1.0, tone=("crushed",), scene_type=6,
            x=1, keep=False)),
        ("shipped .dpi, crushed, sceneType 0 x=2 (default -> band 1)", dict(
            params=ship, low=1.0, high=1.0, tone=("crushed",), scene_type=0,
            x=2, keep=False)),
        ("shipped .dpi, crushed, sceneType 9 x=1 (default -> band 0)", dict(
            params=ship, low=1.0, high=1.0, tone=("crushed",), scene_type=9,
            x=1, keep=False)),
        ("small LUT (256/255), mode1 + constrainSlope", dict(
            params=_p(bConstrainSlope=True, **small), low=1.0, high=1.0,
            tone=("crushed",), scene_type=3, x=1, keep=False)),
        ("small LUT, mode2 polyline", dict(
            params=_p(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                      points=[(0, 0), (60, 20), (255, 255)], **small),
            low=1.0, high=1.0, tone=("identity",), scene_type=3, x=1,
            keep=False)),
        ("midpoint off-centre (400, 2800)", dict(
            params=_p(midpointIn=400, midpointOut=2800), low=1.6, high=0.4,
            tone=("crushed",), scene_type=3, x=1, keep=False)),
    ]
    return out


TONE_MAKERS = {
    "identity": lut_identity,
    "crushed": lut_crushed,
    "steep": lut_steep,
    "noisy": lut_noisy,
}


def _tone(spec, p: cx.ContrastParams):
    if spec is None:
        return None
    return TONE_MAKERS[spec[0]](p.lutSize, p.maxValue)


def _diff(a: dict, b: dict) -> list[str]:
    bad = []
    for k in a:
        if k in ("thrown", "status_ok", "params_after", "logged"):
            continue
        av, bv = a[k], b.get(k)
        if isinstance(av, list) or isinstance(bv, list):
            if av is None or bv is None:
                if av is not bv:
                    bad.append(f"{k}: dll={'None' if av is None else 'list'} "
                               f"host={'None' if bv is None else 'list'}")
                continue
            if av != bv:
                i = next(j for j in range(min(len(av), len(bv)))
                         if av[j] != bv[j])
                bad.append(f"{k}: first diff at [{i}] dll={av[i]} host={bv[i]} "
                           f"({sum(1 for x, y in zip(av, bv) if x != y)} of "
                           f"{len(av)} differ)")
            continue
        if av != bv:
            bad.append(f"{k}: dll={av!r} host={bv!r}")
    return bad


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll.exists():
        print(f"{dll} not found — run "
              f"'python3 tools/re/reachability.py extract' first")
        return 2
    pe = dll.read_bytes()
    bad = 0

    for flag in ("CONTRAST_LUT_BUILD_PORTED", "CONTRAST_CONSTRAIN_SLOPE_PORTED",
                 "CONTRAST_SET_PARAMS_PORTED", "CONTRAST_ACQUIRE_PORTED",
                 "CONTRAST_DPI_PARSE_PORTED"):
        if not getattr(cx, flag):
            raise RuntimeError(f"{flag} is False — nothing to verify")

    # ---- 1. the vendor typo, straight out of the image ------------------
    print("== the csUpperIndex .dpi-key typo (replicated, not fixed) ==")
    emu = Emu(pe)
    key = emu.cstr(cx.DPI_KEY_CS_UPPER_INDEX_STR_VA, 32)
    ok = key == cx.DPI_KEY_CS_UPPER_INDEX
    bad += not ok
    print(f"  [{cx.DPI_KEY_CS_UPPER_INDEX_STR_VA:#x}] = {key!r}  "
          f"port says {cx.DPI_KEY_CS_UPPER_INDEX!r}  {'OK' if ok else 'FAIL'}")
    ship = shipped_params()
    ok = ("csupperindex" not in
          (line.split("=")[0].strip().lower()
           for line in ["x"]) and ship.csUpperIndex == 3999)
    bad += not ok
    print(f"  shipped contrast-CNEnhanced.dpi leaves csUpperIndex at its "
          f"ctor default: {ship.csUpperIndex}  {'OK' if ok else 'FAIL'}")
    probe = cx.parse_dpi("csUpperIndex = 1234\n")
    spelled = cx.parse_dpi("csumpperixedindex = 1234\n")
    ok = probe.csUpperIndex == 3999 and spelled.csUpperIndex == 1234
    bad += not ok
    print(f"  correctly-spelled key is REJECTED ({probe.csUpperIndex}), only "
          f"the typo takes ({spelled.csUpperIndex})  {'OK' if ok else 'FAIL'}")
    print()

    # ---- 2. cap+0xe's real default -------------------------------------
    print("== cap+0xe, the gating byte declareAutoTone never sets ==")
    b = bytes(emu.uc.mem_read(cx.CAP_CTOR_FLAG_E_STORE, 4))
    ok = b == b"\xc6\x46\x0e\x00"              # mov byte [esi+0xe], 0
    bad += not ok
    print(f"  {cx.CAP_CTOR_FLAG_E_STORE:#x}: {b.hex()} = "
          f"'mov byte [esi+0xe], 0' -> default "
          f"{cx.CONTRAST_KEEP_INTERMEDIATES_DEFAULT}  {'OK' if ok else 'FAIL'}")
    print()

    # ---- 3. validateParams' predicate ------------------------------------
    # Worth checking on its own because analyze *discards* the status setParams
    # returns (0x101d82a2), so the only way a wrong predicate shows up in the
    # LUT is through setParams' rollback -- which means a port that got the
    # bounds backwards would still produce the right LUT most of the time.
    print("== 0x101d3860 validateParams: host predicate vs DLL ==")
    for label, p in (
        ("defaults", cx.ContrastParams()),
        ("shipped .dpi", shipped_params()),
        ("midpoint.in = lutSize (one past the end)",
         cx.ContrastParams(midpointIn=4096)),
        ("midpoint.in = lutSize - 1", cx.ContrastParams(midpointIn=4095)),
        ("midpoint.in = -1", cx.ContrastParams(midpointIn=-1)),
        ("midpoint.out = maxValue", cx.ContrastParams(midpointOut=4095)),
        ("midpoint.out = maxValue + 1", cx.ContrastParams(midpointOut=4096)),
        ("midpoint.out = -1", cx.ContrastParams(midpointOut=-1)),
        ("lowInitialSlope = 0.1 (the bound itself)",
         cx.ContrastParams(lowInitialSlope=cx.SLOPE_MIN)),
        ("lowInitialSlope = 0.09", cx.ContrastParams(lowInitialSlope=0.09)),
        ("lowInitialSlope = 10.0 (the bound itself)",
         cx.ContrastParams(lowInitialSlope=10.0)),
        ("lowInitialSlope = 10.01", cx.ContrastParams(lowInitialSlope=10.01)),
        ("highInitialSlope = 0.0", cx.ContrastParams(highInitialSlope=0.0)),
        ("highInitialSlope = -1.0", cx.ContrastParams(highInitialSlope=-1.0)),
        ("mode 2 with no points",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT)),
        ("mode 2 with one point",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                           points=[(0, 0)])),
        ("mode 2 with two good points",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                           points=[(0, 0), (4095, 4095)])),
        ("mode 2, points decreasing in `in`",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                           points=[(0, 0), (2000, 500), (1000, 900)])),
        ("mode 2, point.in == lutSize",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                           points=[(0, 0), (4096, 4095)])),
        ("mode 2, point.out > maxValue",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                           points=[(0, 0), (4000, 4096)])),
        ("mode 2, negative point.out",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                           points=[(0, -1), (4000, 4000)])),
        ("mode 2 ignores a bad midpoint",
         cx.ContrastParams(userInputMode=cx.MODE_COMBINE_WITH_POINT,
                           midpointIn=9000,
                           points=[(0, 0), (4095, 4095)])),
        ("mode 4 ignores a bad slope",
         cx.ContrastParams(userInputMode=cx.MODE_OVERRIDE_WITH_POINT,
                           lowInitialSlope=0.0,
                           points=[(0, 0), (4095, 4095)])),
        ("mode 3 checks the slope",
         cx.ContrastParams(userInputMode=cx.MODE_OVERRIDE_WITH_SLOPE,
                           lowInitialSlope=0.0)),
    ):
        e = Emu(pe)
        impl = build_impl(e, p, cx.ContrastResults())
        sret = e.alloc(0x10)
        e.call(cx.VALIDATE_PARAMS, [sret, 0, 0, 800], ecx=impl)
        dll_ok = e.r32(sret) == 0
        host_ok = cx.validate_params(p) is None
        ok = dll_ok == host_ok
        bad += not ok
        print(f"  {label:<48} dll={'ok  ' if dll_ok else 'FAIL'} "
              f"host={'ok  ' if host_ok else 'FAIL'}  "
              f"{'OK' if ok else 'MISMATCH'}")
    print()

    # ---- 4. the LUT build ------------------------------------------------
    print("== 0x101d8240 analyze: host vs DLL ==")
    for label, kw in cases():
        p = kw["params"]
        tone = _tone(kw["tone"], p)
        res = cx.ContrastResults(lowSlope=cx._f32(kw["low"]),
                                 highSlope=cx._f32(kw["high"]))
        d = run_dll_analyze(pe, p, res, scene_type=kw["scene_type"],
                            x=kw["x"], tone=tone, keep=kw["keep"])
        h = run_host_analyze(p, cx.ContrastResults(
            lowSlope=cx._f32(kw["low"]), highSlope=cx._f32(kw["high"])),
            scene_type=kw["scene_type"], x=kw["x"], tone=tone,
            keep=kw["keep"])
        problems = _diff(d, h)
        if d["thrown"]:
            problems.append(f"threw {d['thrown']}")
        bad += bool(problems)
        n = len(d["OutToneLut"] or ())
        print(f"  {label:<58} out[{n}] "
              f"{'OK' if not problems else 'FAIL ' + '; '.join(problems[:2])}")
    print()

    # ---- 4. the front end -----------------------------------------------
    print("== 0x101d8880 acquire: holder + params ctor + selectParams + "
          "setParams + validateParams ==")
    ship = shipped_params()
    tone = lut_crushed(4096, 4095)
    front: list[tuple[str, dict]] = [
        ("selected = shipped .dpi (setParams runs for real)", dict(
            embedded=cx.ContrastParams(), selected=ship, tone=tone,
            scene_type=3, x=1, keep=False)),
        ("selected = defaults", dict(
            embedded=cx.ContrastParams(), selected=cx.ContrastParams(),
            tone=tone, scene_type=3, x=1, keep=False)),
        ("selected = OVERRIDE_WITH_POINT", dict(
            embedded=cx.ContrastParams(),
            selected=cx.ContrastParams(
                userInputMode=cx.MODE_OVERRIDE_WITH_POINT,
                points=[(0, 0), (1500, 700), (4095, 4095)]),
            tone=tone, scene_type=3, x=1, keep=False)),
        ("selected has an INVALID midpoint -> validate fails, rollback", dict(
            embedded=cx.ContrastParams(midpointIn=1000, midpointOut=1000),
            selected=cx.ContrastParams(midpointIn=9000, midpointOut=1000),
            tone=tone, scene_type=3, x=1, keep=False)),
        ("selected has slope 0.05 (< 0.1) -> validate fails, rollback", dict(
            embedded=cx.ContrastParams(),
            selected=cx.ContrastParams(lowInitialSlope=0.05),
            tone=tone, scene_type=3, x=1, keep=False)),
        ("selected has slope 12.0 (> 10.0) -> validate fails, rollback", dict(
            embedded=cx.ContrastParams(),
            selected=cx.ContrastParams(highInitialSlope=12.0),
            tone=tone, scene_type=3, x=1, keep=False)),
        ("keep_intermediates=1", dict(
            embedded=cx.ContrastParams(), selected=ship, tone=tone,
            scene_type=3, x=1, keep=True)),
    ]
    for label, kw in front:
        res = cx.ContrastResults()                # a fresh Impl: lowSlope -1.0
        d = run_dll_acquire(pe, kw["embedded"], kw["selected"], res,
                            scene_type=kw["scene_type"], x=kw["x"],
                            tone=kw["tone"], keep=kw["keep"])
        impl = cx.ContrastImpl(params=kw["embedded"].copy(),
                               results=cx.ContrastResults())
        r = impl.analyze(kw["selected"], kw["scene_type"], kw["x"],
                         kw["tone"], keep_intermediates=kw["keep"])
        h = host_results(r)
        problems = _diff(d, h)
        want_params = impl.params.to_bytes(
            points_ptr=struct.unpack_from("<I", d["params_after"], 0x60)[0])
        if d["params_after"][0x3A:0x60] != want_params[0x3A:0x60]:
            problems.append("params scalars after setParams differ")
        if d["params_after"][0x6C:0x180] != want_params[0x6C:0x180]:
            problems.append("params arrays after setParams differ")
        bad += bool(problems)
        print(f"  {label:<58} "
              f"{'OK' if not problems else 'FAIL ' + '; '.join(problems[:2])}")

    # the two error lines
    for label, kw, want_line in (
        ("holder resolve fails -> .cpp line 176",
         dict(fail_holder=True), cx.LINE_HOLDER_FAILED),
        ("selectParams fails -> .cpp line 185",
         dict(fail_select=True), cx.LINE_SELECT_PARAMS_FAILED),
    ):
        d = run_dll_acquire(pe, cx.ContrastParams(), ship,
                            cx.ContrastResults(), scene_type=3, x=1,
                            tone=tone, keep=False, **kw)
        lines = [ln for _f, ln in d["logged"]]
        ok = (want_line in lines and not d["status_ok"]
              and d["OutToneLut"] is None)
        bad += not ok
        print(f"  {label:<58} logged={lines} built={d['OutToneLut'] is not None}"
              f"  {'OK' if ok else 'FAIL'}")
    print()

    if bad:
        print(f"FAILED {bad} check(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
