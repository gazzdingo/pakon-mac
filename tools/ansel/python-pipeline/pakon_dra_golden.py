#!/usr/bin/env python3
"""Golden ``dra`` leaves and branch polarity vs PakonIMAu.dll (Unicorn).

Every claim ``pakon_dra.py`` makes with a ``True`` flag that has executable
content is checked here by running **the real DLL bytes**, x86-32, PE mapped at
``IMAGE_BASE = 0x10000000``, against the port.

Ports under test
----------------
==============================  =====================================
``0x10228e00``                  ``dra.rebin``
``0x10228bc0``                  ``dra.cum_bounds``
``0x1022b191``..``0x1022b1d4``  ``dra.lum_histogram``   (variant A inline)
``0x1022bb0f``..``0x1022bb50``  ``dra.compose_tone``    (variant B inline)
``0x1022b2e1``/``0x1022b999``   ``dra.lighting_from_find`` (BOTH sites)
==============================  =====================================

The lighting cases are the point of this file.  ``AnsDraCapabilityImpl::
analyze``'s guarded ``find("lighting")`` was **mis-documented as "miss is
fatal"**.  It is not.  A miss **continues** to the LUT-building path, and the
branch flag encodes only whether ``find()`` hit an *internal* error.  Cases
``lighting-miss-*`` below exercise exactly that path — the real, unmocked
``AnsSceneContext::find`` over a real empty ``std::map`` — at **both** call
sites, and additionally assert the value the continue path then uses is **0**
(Normal), not garbage.  If a future edit silently reintroduces "miss is fatal",
these are the cases that fail.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_dra_golden.py [dll]``
"""
from __future__ import annotations

import copy
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
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDX,
    UC_X86_REG_ESI,
    UC_X86_REG_EDI,
    UC_X86_REG_EBP,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
    UC_X86_REG_FPCW,
)

import pakon_dra as dra

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x00400000
SCRATCH = 0x00100000
RET_MAGIC = 0x00110000

# Imports the dra snippets touch. None of them affect the arithmetic or the
# branch — they are CRT/OS plumbing.
IAT_STR_CTOR_PBD = 0x10573394     # MSVCP71 basic_string(const char*)
IAT_STR_DTOR = 0x10573418         # MSVCP71 ~basic_string()
IAT_ENTER_CS = 0x10573028         # KERNEL32 EnterCriticalSection
IAT_LEAVE_CS = 0x10573044         # KERNEL32 LeaveCriticalSection

DEFAULT_DLL = Path("/tmp/pakon_re/PakonIMAu.dll")
FALLBACK_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)

#: The Windows CRT's x87 control word: 53-bit mantissa, round to nearest.
#: Same convention as pakon_toneHelper_core_golden.py / pakon_contrast_lut_
#: golden.py: Unicorn *reports* FPCW==0 on a fresh Uc but behaves as 64-bit
#: extended until the register is written, so leaving it alone is not "the
#: default", it is a third, wrong thing.  keepMidPtLut's curve construction
#: is exactly the kind of x87 code (chained fmul/fdiv/fadd through a stored
#: float32 each time) where this is load-bearing -- see check_keep_midpt_lut's
#: FPCW-sensitivity negative control below.
FPCW_WINDOWS = 0x027F
FPCW_EXTENDED = 0x037F


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    """PE-into-Unicorn + bump allocator + CRT stubs, the house pattern."""

    def __init__(self, pe: bytes, fpcw: int = FPCW_WINDOWS):
        self.pe = pe
        self.fpcw = fpcw
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self._load()
        uc.mem_map(0, 0x1000)                 # flat FS base -> fs:[0]
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
        uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)

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

    def w32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", int(v) & 0xFFFFFFFF))

    def wb(self, a: int, v: int) -> None:
        self.uc.mem_write(a, bytes([int(v) & 0xFF]))

    def wi16(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<h", int(v)))

    def wf32(self, a: int, v: float) -> None:
        self.uc.mem_write(a, struct.pack("<f", float(v)))

    def r32(self, a: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def r16(self, a: int) -> int:
        return struct.unpack("<H", self.uc.mem_read(a, 2))[0]

    def rf32(self, a: int) -> float:
        return struct.unpack("<f", self.uc.mem_read(a, 4))[0]

    def hook_stdcall(self, va: int, fn) -> None:
        """``fn(emu, args_addr) -> (eax, extra_pop_bytes)``."""

        def cb(uc, address, size, _u):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            eax, pop = fn(self, esp + 4)
            if eax is not None:
                uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)

        self.uc.hook_add(UC_HOOK_CODE, cb, begin=va, end=va)

    def patch_iat_stub(self, iat_addr: int, fn) -> int:
        s = self.stub()
        self.w32(iat_addr, s)
        self.hook_stdcall(s, fn)
        return s

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"bad mem access={access} addr={address:#x} eip="
            f"{uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

    def run(self, start: int, until: int = 0, count: int = 4_000_000) -> None:
        self.faults = []
        try:
            self.uc.emu_start(start, until, timeout=0, count=count)
        except UcError as ex:
            raise RuntimeError(
                f"emu fault eip={self.uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
                + ("; " + "; ".join(self.faults[:4]) if self.faults else "")
            ) from ex


# ---------------------------------------------------------------------------
# MSVC7.1 basic_string<char>: union{buf[16]/ptr} + _Mysize + _Myres
# ---------------------------------------------------------------------------


def write_msvc_string(emu: Emu, obj: int, text: bytes) -> None:
    n = len(text)
    if n < 16:
        emu.uc.mem_write(obj, text + b"\x00" * (16 - n))
        emu.w32(obj + 16, n)
        emu.w32(obj + 20, 15)
    else:
        buf = emu.alloc(n + 1, text + b"\x00")
        emu.w32(obj, buf)
        emu.uc.mem_write(obj + 4, b"\x00" * 12)
        emu.w32(obj + 16, n)
        emu.w32(obj + 20, n)


def install_common_hooks(emu: Emu) -> None:
    def str_ctor(e: Emu, args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        src = e.r32(args)
        s = bytearray()
        p = src
        while True:
            b = e.uc.mem_read(p, 1)[0]
            if b == 0:
                break
            s.append(b)
            p += 1
        write_msvc_string(e, this, bytes(s))
        return this, 4

    emu.patch_iat_stub(IAT_STR_CTOR_PBD, str_ctor)
    emu.patch_iat_stub(IAT_STR_DTOR, lambda e, a: (None, 0))
    emu.patch_iat_stub(IAT_ENTER_CS, lambda e, a: (None, 4))
    emu.patch_iat_stub(IAT_LEAVE_CS, lambda e, a: (None, 4))


#: ``operator new`` / ``operator delete`` thunks the allocation-touching
#: functions (alloc, generateLut's toneLut-remap block, the two analyze
#: overloads' stale-LUT free) all funnel through. Both cdecl (caller pops).
VA_OP_NEW = 0x104FFD78
VA_OP_DELETE = 0x104FFE3E


def install_allocator_hooks(emu: Emu) -> None:
    """``operator new(size_t)`` -> the emulator's own bump allocator;
    ``operator delete(void*)`` -> no-op (Python never needs the free)."""

    def op_new(e: Emu, args: int):
        size = e.r32(args)
        return e.alloc(max(size, 4)), 0

    def op_delete(e: Emu, args: int):
        return None, 0

    emu.hook_stdcall(VA_OP_NEW, op_new)
    emu.hook_stdcall(VA_OP_DELETE, op_delete)


def install_scene_context_mock(emu: Emu, ctx: int) -> None:
    """Short-circuits ``GET_SCENE_CONTEXT`` (``0x10021730``) to hand back
    ``ctx`` (a real, working ``build_empty_scene_context()`` object, or any
    other real scene context) without needing to reconstruct the private
    wrapper object ``0x10021730`` itself expects as ``ecx`` (an
    ``AnsCapabilityImpl``-side field whose own setup lives outside dra
    entirely).  Read off ``0x10021730``'s own decompile: it always reports
    success (writes the ``STATUS_OK_GLOBAL`` contents, 0, into ``*param2``)
    and writes the resolved context pointer into ``*param3``; the two stack
    args at the callee's entry are, in push order, ``[esp+4]=param2``
    (status out, pushed last/closest) and ``[esp+8]=param3`` (ctx out,
    pushed first/farthest) -- this mock reproduces exactly that contract, so
    everything downstream (``find("lighting")``, in particular) runs for
    real, unmocked, against ``ctx``.
    """

    def mock(e: Emu, args: int):
        param2 = e.r32(args + 0)
        param3 = e.r32(args + 4)
        if param2:
            e.w32(param2, 0)      # STATUS_OK_GLOBAL contents
        if param3:
            e.w32(param3, ctx)
        return param2, 8

    emu.hook_stdcall(dra.GET_SCENE_CONTEXT, mock)


def build_dra_params_blob_into(emu: Emu, base: int, p: "dra.DraParams") -> None:
    """Writes a full ``0x1c78``-byte ``AnsDraParams`` image (matching
    ``DRA_PARAMS_LAYOUT``, including all six ``.ttc`` curve blocks) at
    ``base``."""
    for key, off, kind in dra.DRA_PARAMS_LAYOUT:
        v = p.values[key]
        if kind == "i16":
            emu.wi16(base + off, v)
        elif kind == "i32":
            emu.w32(base + off, v & 0xFFFFFFFF)
        elif kind == "f32":
            emu.wf32(base + off, v)
        elif kind == "bool":
            emu.wb(base + off, 1 if v else 0)
        elif kind == "ttc":
            c = p.curves[key]
            emu.w32(base + off, c.n_points)
            for i, x in enumerate(c.x):
                emu.wf32(base + off + 4 + 4 * i, x)
            for i, y in enumerate(c.y):
                emu.wf32(base + off + 4 + 0x190 + 4 * i, y)
            for i, s in enumerate(c.slope):
                emu.wf32(base + off + 4 + 0x320 + 4 * i, s)


def build_dra_params_blob(emu: Emu, p: "dra.DraParams") -> int:
    """Same as ``build_dra_params_blob_into``, into a fresh 0x1c78-byte
    allocation; returns its base address."""
    base = emu.alloc(0x1C78)
    build_dra_params_blob_into(emu, base, p)
    return base


def build_dra_impl(emu: Emu, p: "dra.DraParams") -> int:
    """A fresh ``impl`` object: params written at ``impl+0x10`` (so
    ``generateLut``'s ``eax+0x00`` == ``impl+0x10``, matching the real
    layout), room for ``AnsDraResults`` at ``impl+0x1c88``, and some slack.
    """
    impl = emu.alloc(0x10 + 0x1C78 + 0x40)
    build_dra_params_blob_into(emu, impl + 0x10, p)
    return impl


def build_empty_scene_context(emu: Emu) -> int:
    """A real, empty ``AnsSceneContext`` — a genuine ``find`` miss.

    0x2000 covers the bookkeeping fields (+0x1c8c/+0x1c9c/+0x1cc0 …) the abort
    path's context-release call ``0x102294d0`` reads; zeroed, so every one of
    them reads as "nothing cached".
    """
    ctx = emu.alloc(0x2000)
    head = emu.alloc(0x60)
    emu.w32(ctx + 0x10, head)     # map at ctx+0xc; map+4 == _Myhead
    emu.w32(head + 4, head)       # empty red-black tree: root == nil
    emu.wb(head + 0x4D, 1)        # _Myhead->_Isnil
    return ctx


# ---------------------------------------------------------------------------
# 1. the guarded find("lighting") — BOTH sites
# ---------------------------------------------------------------------------

#: variant -> (block_start, esp-rel of scene-ctx slot, esp-rel of outSlot ptr,
#:             esp-rel of the value buffer, extra esp-rel ctx slot or None)
#:
#: Derived by hand-tracing the push sequence from the block start to each
#: read, then confirmed by the runs below actually completing.
LIGHTING_FRAMES = {
    dra.DRA_ANALYZE_IMAGE: dict(
        start=0x1022B2E1, ctx_slot=0x10, out_slot=0x24, value=0x28,
        abort_ctx_slot=0x1C, zero_reg=UC_X86_REG_EDI, impl_reg=None),
    dra.DRA_ANALYZE_HIST: dict(
        start=0x1022B999, ctx_slot=0x18, out_slot=0x28, value=0x2C,
        abort_ctx_slot=None, zero_reg=UC_X86_REG_ESI,
        impl_reg=UC_X86_REG_EBP),
}


def run_lighting(pe: bytes, variant: int, *, mock_internal_error: bool):
    """Execute one variant's lighting block for real; report where it lands."""
    site = dra.DRA_LIGHTING_SITES[variant]
    _key, _find, _flag, _test, va_continue, va_abort, _line = site
    frame = LIGHTING_FRAMES[variant]

    emu = Emu(pe)
    install_common_hooks(emu)

    hit: dict[str, object] = {}

    def mark(name):
        def cb(uc, address, size, _u):
            hit["landed"] = name
            if name == "continue":
                # Snapshot the value the continue path is about to use.
                esp = uc.reg_read(UC_X86_REG_ESP)
                hit["out_slot"] = emu.r32(esp + frame["out_slot"])
            uc.emu_stop()
        return cb

    emu.uc.hook_add(UC_HOOK_CODE, mark("continue"),
                    begin=va_continue, end=va_continue)
    emu.uc.hook_add(UC_HOOK_CODE, mark("abort"), begin=va_abort, end=va_abort)

    if mock_internal_error:
        # find()'s OTHER documented contract: an internal-error object
        # (non-null field 0), copied from its own 0x10022b3f exit.
        def mock(e: Emu, _args):
            esp = e.uc.reg_read(UC_X86_REG_ESP)
            ret_struct = e.r32(esp + 4)
            e.w32(ret_struct, e.alloc(4, b"\x01\x00\x00\x00"))
            return ret_struct, 0x14
        emu.hook_stdcall(dra.SCENE_CONTEXT_FIND, mock)

    ctx = build_empty_scene_context(emu)
    impl = emu.alloc(0x2000)

    esp0 = STACK + 0x40000
    emu.uc.reg_write(UC_X86_REG_ESP, esp0)
    emu.uc.reg_write(frame["zero_reg"], 0)
    if frame["impl_reg"] is not None:
        emu.uc.reg_write(frame["impl_reg"], impl)
    emu.w32(esp0 + frame["ctx_slot"], ctx)
    if frame["abort_ctx_slot"] is not None:
        emu.w32(esp0 + frame["abort_ctx_slot"], ctx)

    emu.run(frame["start"])
    if "landed" not in hit:
        raise RuntimeError(f"no landing; faults={emu.faults[:4]}")

    value = None
    if hit["landed"] == "continue":
        # Replay the continue path's own fixup (0x1022b3b0 / 0x1022baa4):
        # if the out-slot pointer is NULL the value is forced to 0.
        value = 0 if hit["out_slot"] == 0 else emu.r16(
            esp0 + frame["value"])
    return hit["landed"], value


def check_lighting(pe: bytes) -> int:
    print("=== find(\"lighting\") branch polarity — BOTH call sites ===")
    print("    (a real, unmocked AnsSceneContext::find over a real EMPTY map:")
    print("     the actual runtime condition for every colour negative)")
    bad = 0
    for variant, label in ((dra.DRA_ANALYZE_IMAGE, "analyze(image)"),
                           (dra.DRA_ANALYZE_HIST, "analyze(hist) ")):
        site = dra.DRA_LIGHTING_SITES[variant]
        landed, value = run_lighting(pe, variant, mock_internal_error=False)
        port = dra.lighting_from_find(found=False)
        ok = (landed == "continue" and value == port == dra.LIGHTING_NORMAL)
        bad += not ok
        print(f"  {label} {variant:#x} MISS      -> dll={landed} "
              f"({site[4]:#x}) value={value}  port={port}  "
              f"{'OK' if ok else 'FAIL'}")

        landed2, _ = run_lighting(pe, variant, mock_internal_error=True)
        try:
            dra.lighting_from_find(found=False, internal_error=True)
            port2 = "continue"
        except dra.DraError:
            port2 = "abort"
        ok2 = (landed2 == "abort" and port2 == "abort")
        bad += not ok2
        print(f"  {label} {variant:#x} INTERNAL  -> dll={landed2} "
              f"({site[5]:#x}) port={port2}  {'OK' if ok2 else 'FAIL'}")
    if not bad:
        print("  => MISS CONTINUES at both sites, yielding lighting 0 "
              "(Normal); only a genuine internal find() error aborts.")
    return bad


# ---------------------------------------------------------------------------
# 2. 0x10228e00 — rebin
# ---------------------------------------------------------------------------

REBIN_CASES = [
    ([1, 2, 3, 4, 5, 6, 7, 8], 8, 4),
    ([0] * 16, 16, 4),
    (list(range(20)), 20, 4),
    (list(range(20)), 20, 1),
    (list(range(20)), 20, 2),
    ([100] * 12, 12, 3),
    (list(range(13)), 13, 4),          # non-multiple: idiv truncates
    ([1000000] * 8, 8, 4),
    ([-3, -2, -1, 0, 1, 2, 3, 4], 8, 2),
]


def run_rebin(pe: bytes, small: list[int], n_small: int, bf: int) -> list[int]:
    emu = Emu(pe)
    src = emu.alloc(max(len(small), 1) * 4,
                    b"".join(struct.pack("<i", v) for v in small))
    n_large = abs(n_small) // abs(bf) if bf else 0
    dst = emu.alloc(max(n_large, 1) * 4 + 0x40)
    emu.uc.reg_write(UC_X86_REG_ESP, STACK + 0x40000)
    emu.uc.mem_write(STACK + 0x40000, struct.pack("<I", RET_MAGIC))
    emu.uc.reg_write(UC_X86_REG_EAX, n_small & 0xFFFFFFFF)
    emu.uc.reg_write(UC_X86_REG_ECX, src)
    emu.uc.reg_write(UC_X86_REG_EDX, dst)
    emu.uc.reg_write(UC_X86_REG_ESI, bf & 0xFFFFFFFF)
    emu.run(dra.DRA_REBIN, RET_MAGIC)
    return [struct.unpack("<i", emu.uc.mem_read(dst + 4 * i, 4))[0]
            for i in range(n_large)]


def check_rebin(pe: bytes) -> int:
    print("=== 0x10228e00 / dra.rebin ===")
    bad = 0
    for small, n, bf in REBIN_CASES:
        ref = run_rebin(pe, small, n, bf)
        got = dra.rebin(small, n, bf)
        ok = got == ref
        bad += not ok
        print(f"  n={n:<3} binFactor={bf}  dll={ref}  port={got}  "
              f"{'OK' if ok else 'FAIL'}")
    return bad


# ---------------------------------------------------------------------------
# 3. 0x10228bc0 — cumulative-percentile bounds
# ---------------------------------------------------------------------------


def _params_blob(p: dict) -> bytes:
    """A params image, generateLut-relative, big enough for +0x30..+0x3c."""
    buf = bytearray(0x40)
    struct.pack_into("<i", buf, 0x14, int(p["binFactor"]))
    struct.pack_into("<f", buf, 0x30, float(p["startingMinCumPoint"]))
    struct.pack_into("<f", buf, 0x34, float(p["cumPctBelowMin"]))
    struct.pack_into("<f", buf, 0x38, float(p["startingMaxCumPoint"]))
    struct.pack_into("<f", buf, 0x3C, float(p["cumPctAboveMax"]))
    return bytes(buf)


def run_cum_bounds(pe: bytes, cum: list[int], large: list[int], n_large: int,
                   total: int, p: dict) -> tuple[int, int]:
    emu = Emu(pe)
    cum_a = emu.alloc(len(cum) * 4 + 0x40,
                      b"".join(struct.pack("<i", v) for v in cum))
    lg_a = emu.alloc(len(large) * 4 + 0x40,
                     b"".join(struct.pack("<i", v) for v in large))
    par = emu.alloc(0x40, _params_blob(p))
    out_lo = emu.alloc(4)
    out_hi = emu.alloc(4)
    esp = STACK + 0x40000
    emu.uc.mem_write(esp, struct.pack("<IIIIII", RET_MAGIC, lg_a, n_large,
                                      total, out_lo, out_hi))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_EAX, cum_a)
    emu.uc.reg_write(UC_X86_REG_EDI, par)
    emu.run(dra.DRA_CUM_BOUNDS, RET_MAGIC)
    lo = struct.unpack("<h", emu.uc.mem_read(out_lo, 2))[0]
    hi = struct.unpack("<h", emu.uc.mem_read(out_hi, 2))[0]
    return lo, hi


def _make_cum_case(rng: random.Random, n_large: int) -> tuple[list, list, int]:
    large = [rng.randint(0, 500) for _ in range(n_large)]
    cum, run = [], 0
    for v in large:
        run += v
        cum.append(run)
    return cum, large, run


def check_cum_bounds(pe: bytes) -> int:
    print("=== 0x10228bc0 / dra.cum_bounds ===")
    p = dict(binFactor=4, startingMinCumPoint=1.0, cumPctBelowMin=0.1,
             startingMaxCumPoint=90.0, cumPctAboveMax=0.2)
    rng = random.Random(0xD8A)
    cases = []
    for n in (16, 32, 64, 100, 256):
        cases.append(_make_cum_case(rng, n))
    # a flat histogram, and one with all mass at the bottom
    flat = [10] * 64
    cum = []
    r = 0
    for v in flat:
        r += v
        cum.append(r)
    cases.append((cum, flat, r))
    def _from_hist(h):
        c, r = [], 0
        for v in h:
            r += v
            c.append(r)
        return c, h, r

    # Shapes that specifically exercise the two 3-point walk-back loops.
    spike_lo = [0] * 64
    spike_lo[3] = 5000
    cases.append(_from_hist(spike_lo))
    spike_hi = [0] * 64
    spike_hi[60] = 5000
    cases.append(_from_hist(spike_hi))
    bimodal = [0] * 64
    bimodal[5] = bimodal[58] = 2000
    cases.append(_from_hist(bimodal))
    ramp_up = list(range(64))
    cases.append(_from_hist(ramp_up))
    ramp_down = list(reversed(range(64)))
    cases.append(_from_hist(ramp_down))
    # Long tails on both sides: mass in the middle, sparse noise at the edges.
    tailed = [1] * 64
    for i in range(24, 40):
        tailed[i] = 400
    cases.append(_from_hist(tailed))

    bad = 0
    for pp in (p, dict(p, binFactor=1), dict(p, binFactor=8),
               dict(p, startingMinCumPoint=5.0, startingMaxCumPoint=95.0)):
        for cum, large, total in cases:
            n = len(large)
            ref = run_cum_bounds(pe, cum, large, n, total, pp)
            got = dra.cum_bounds(cum, large, n, total, pp)
            ok = got == ref
            bad += not ok
            if not ok:
                print(f"  bf={pp['binFactor']} nLarge={n:<4} total={total:<7} "
                      f"dll={ref}  port={got}  FAIL")
    print(f"  {len(cases) * 4} cases across 4 param sets "
          f"(binFactor 4/1/8 and a 5..95 percentile pair): "
          f"{'all OK' if not bad else f'{bad} FAILED'}")
    for cum, large, total in cases[:6]:
        n = len(large)
        print(f"    nLarge={n:<4} total={total:<7} "
              f"dll={run_cum_bounds(pe, cum, large, n, total, p)}")
    return bad


# ---------------------------------------------------------------------------
# 4. 0x1022b191..0x1022b1d4 — variant A's own luminance histogram
# ---------------------------------------------------------------------------

VA_LUM_HIST_START = 0x1022B191   # rep stosd (zero) then the accumulate loop
VA_LUM_HIST_END = 0x1022B1D6     # xor edi,edi — first insn after the loop


def run_lum_histogram(pe: bytes, pixels: bytes, n_pixels: int,
                      n_bins: int) -> list[int]:
    emu = Emu(pe)
    hist = emu.alloc(n_bins * 4 + 0x400)
    px = emu.alloc(len(pixels) + 0x40, pixels)
    emu.uc.reg_write(UC_X86_REG_ESP, STACK + 0x40000)
    # 0x1022b191 is `rep stosd` with edi=hist, ecx=nBins, eax=0; then the loop
    # uses ebx=hist, edx=nPixels, esi=pixels (0x1022b17b..0x1022b195).
    emu.uc.reg_write(UC_X86_REG_EDI, hist)
    emu.uc.reg_write(UC_X86_REG_ECX, n_bins)
    emu.uc.reg_write(UC_X86_REG_EAX, 0)
    emu.uc.reg_write(UC_X86_REG_EBX, hist)
    emu.uc.reg_write(UC_X86_REG_EDX, n_pixels)
    emu.uc.reg_write(UC_X86_REG_ESI, px)
    emu.run(VA_LUM_HIST_START, VA_LUM_HIST_END)
    return [struct.unpack("<i", emu.uc.mem_read(hist + 4 * i, 4))[0]
            for i in range(n_bins)]


def check_lum_histogram(pe: bytes) -> int:
    print("=== 0x1022b191 / dra.lum_histogram (variant A inline) ===")
    rng = random.Random(0x1022B1A0)
    bad = 0
    cases = [
        ([(0, 0, 0)] * 4, 64),
        ([(10, 20, 30), (0, 0, 0), (63, 63, 63)], 64),
        ([(rng.randint(0, 200), rng.randint(0, 200), rng.randint(0, 200))
          for _ in range(64)], 256),
        ([(255, 255, 255)] * 8, 256),
        ([(1, 1, 1), (2, 2, 2), (3, 3, 4), (4, 4, 5)], 32),
    ]
    for triples, n_bins in cases:
        pixels = b"".join(struct.pack("<hhh", *t) for t in triples)
        n = len(triples)
        ref = run_lum_histogram(pe, pixels, n, n_bins)
        got = dra.lum_histogram(pixels, n, n_bins)
        ok = got == ref
        bad += not ok
        nz = [(i, v) for i, v in enumerate(ref) if v]
        print(f"  nPixels={n:<4} nBins={n_bins:<4} nonzero={nz[:6]}  "
              f"{'OK' if ok else 'FAIL'}")
    return bad


# ---------------------------------------------------------------------------
# 5. 0x1022bb0f..0x1022bb50 — variant B's compose-onto-tone block
# ---------------------------------------------------------------------------

VA_COMPOSE_START = 0x1022BB0F
VA_COMPOSE_END = 0x1022BB52


def run_compose(pe: bytes, dra_lut: list[int], tone: list[int],
                n: int) -> list[int]:
    emu = Emu(pe)
    impl = emu.alloc(0x2000)
    lut = emu.alloc(n * 2 + 0x200,
                    b"".join(struct.pack("<h", v) for v in dra_lut))
    scratch = emu.alloc(n * 2 + 0x200)
    tone_a = emu.alloc(n * 2 + 0x200,
                       b"".join(struct.pack("<h", v) for v in tone))
    emu.w32(impl + 0x1CB0, scratch)     # results.Scratch
    emu.w32(impl + 0x1CC0, lut)         # results.DraLut
    esp = STACK + 0x40000
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_EBP, impl)
    emu.uc.reg_write(UC_X86_REG_ESI, 1)          # `test esi,esi` gate: non-null
    emu.w32(esp + 0x30, n)                        # the element count
    emu.w32(esp + 0x74, tone_a)                   # the incoming tone LUT
    emu.run(VA_COMPOSE_START, VA_COMPOSE_END)
    return [struct.unpack("<h", emu.uc.mem_read(lut + 2 * i, 2))[0]
            for i in range(n)]


def check_compose(pe: bytes) -> int:
    print("=== 0x1022bb0f / dra.compose_tone (variant B inline) ===")
    rng = random.Random(0xC0FFEE)
    bad = 0
    cases = [
        (list(range(16)), list(range(16)), 16),                 # identity
        (list(range(16)), list(reversed(range(16))), 16),       # reversal
        ([i * 2 for i in range(32)], [31 - i for i in range(32)], 32),
        ([rng.randint(0, 4095) for _ in range(64)],
         [rng.randint(0, 63) for _ in range(64)], 64),
        ([0] * 8, [0] * 8, 8),
    ]
    for lut, tone, n in cases:
        ref = run_compose(pe, lut, tone, n)
        got = dra.compose_tone(lut, tone, n)
        ok = got[:n] == ref
        bad += not ok
        print(f"  n={n:<4} dll[:8]={ref[:8]}  port[:8]={got[:8]}  "
              f"{'OK' if ok else 'FAIL'}")
    return bad


# ---------------------------------------------------------------------------
# 6. 0x10228cd0 — effective bounds (both bDoAverage branches)
# ---------------------------------------------------------------------------


def run_eff_bounds(pe: bytes, lum_min, lum_max, edge_min, edge_max,
                   paper_min, paper_max, lum_w, edge_w, do_average,
                   fpcw=FPCW_WINDOWS):
    emu = Emu(pe, fpcw=fpcw)
    params = emu.alloc(0x40)
    emu.wi16(params + 0x06, paper_min)
    emu.wi16(params + 0x08, paper_max)
    emu.wf32(params + 0x1C, lum_w)
    emu.wf32(params + 0x20, edge_w)
    emu.wb(params + 0x18, 1 if do_average else 0)
    results = emu.alloc(0x40)
    emu.wi16(results + 0x2C, lum_min)
    emu.wi16(results + 0x2E, lum_max)
    emu.wi16(results + 0x30, edge_min)
    emu.wi16(results + 0x32, edge_max)
    esp = STACK + 0x40000
    emu.uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_EAX, params)
    emu.uc.reg_write(UC_X86_REG_ESI, results)
    emu.run(dra.DRA_EFF_BOUNDS, RET_MAGIC)
    eff_min = struct.unpack("<h", emu.uc.mem_read(results + 0x34, 2))[0]
    eff_max = struct.unpack("<h", emu.uc.mem_read(results + 0x36, 2))[0]
    return eff_min, eff_max


def check_eff_bounds(pe: bytes) -> int:
    print("=== 0x10228cd0 / dra.eff_bounds (both bDoAverage branches) ===")
    bad = 0
    rng = random.Random(0xEFB0)
    cases = []
    for _ in range(24):
        lum_min = rng.randint(-500, 500)
        lum_max = lum_min + rng.randint(0, 4000)
        edge_min = rng.randint(-500, 500)
        edge_max = edge_min + rng.randint(0, 4000)
        paper_min = rng.randint(-200, 200)
        paper_max = paper_min + rng.randint(500, 4000)
        lum_w = rng.uniform(0.0, 1.0)
        edge_w = 1.0 - lum_w
        cases.append((lum_min, lum_max, edge_min, edge_max, paper_min,
                      paper_max, lum_w, edge_w))
    # a couple of hand-picked cases that force the "paper lies between"
    # crossing branch on purpose (a-p)*(b-p) < 0.
    cases.append((-100, 5000, 200, 6000, 0, 5500, 0.3, 0.7))
    cases.append((-100, 5000, 200, 6000, 0, 5500, 0.7, 0.3))
    for do_average in (False, True):
        for c in cases:
            ref = run_eff_bounds(pe, *c, do_average=do_average)
            got = dra.eff_bounds(*c, do_average=do_average)
            ok = got == ref
            bad += not ok
            if not ok:
                print(f"  do_average={do_average} args={c}  dll={ref}  "
                      f"port={got}  FAIL")
    print(f"  {len(cases) * 2} cases (both branches): "
          f"{'all OK' if not bad else f'{bad} FAILED'}")
    return bad


# ---------------------------------------------------------------------------
# 7. 0x10227c60 — the .ttc parser leaf's slope computation
# ---------------------------------------------------------------------------

TTC_SLOPE_LEAF_FMT_STR = 0x1059F380   # "%f %f", per 0x10227e06


#: The isolated slope-computation snippet inside the .ttc parser leaf: given
#: the point just read (x_cur, y_cur) and the PRIOR point already stored in
#: the x/y arrays at index (bp-1), compute slope[bp-1] = (y_cur-y[bp-1]) /
#: (x_cur-x[bp-1]).  Slicing out just this snippet (instead of the whole
#: stream-reading function, which needs a real istream-shaped object to get
#: past its internal state-flag gate) still executes the real x87 bytes.
VA_TTC_SLOPE_SNIPPET = 0x10227E93
VA_TTC_SLOPE_SNIPPET_END = 0x10227EB2   # first insn AFTER the fstp (7 bytes)


def run_ttc_slope_leaf(pe: bytes, x_prev: float, y_prev: float,
                       x_cur: float, y_cur: float, index: int,
                       fpcw=FPCW_WINDOWS) -> float:
    """Execute the real ``0x10227e93``..``0x10227eab`` bytes: one slope."""
    emu = Emu(pe, fpcw=fpcw)
    esp = STACK + 0x40000
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    ecx = index * 4
    emu.wf32(esp + 0xC, x_cur)
    emu.wf32(esp + 0x10, y_cur)
    # The instructions' own displacements (0xac, 0x23c, 0x3cc) already carry
    # the "-4" (they are literally array_base-4); ecx=index*4 lands them on
    # x[index-1]/y[index-1]/slope[index-1] with no further skew needed here.
    emu.wf32(esp + ecx + 0xAC, x_prev)      # x[index-1]
    emu.wf32(esp + ecx + 0x23C, y_prev)     # y[index-1]
    emu.uc.reg_write(UC_X86_REG_ECX, ecx)
    emu.run(VA_TTC_SLOPE_SNIPPET, VA_TTC_SLOPE_SNIPPET_END)
    return emu.rf32(esp + ecx + 0x3CC)


def check_ttc_slopes(pe: bytes) -> int:
    print("=== 0x10227e93 / dra.build_ttc_slopes (.ttc slope snippet) ===")
    bad = 0
    cases = [
        (0.0, 0.0, 1.0, 1.0),
        (1.0, 1.0, 10.0, 10.0),
        (0.0, 0.0, 0.3, 0.15),
        (0.3, 0.15, 1.0, 1.0),
        (0.0, 0.05, 0.25, 0.1),
        (0.25, 0.1, 0.5, 0.6),
        (0.5, 0.6, 0.75, 0.9),
        (0.0, 0.0, 1.0 / 3.0, 0.2),
        (1.0 / 3.0, 0.2, 2.0 / 3.0, 0.8),
    ]
    for i, (xp, yp, xc, yc) in enumerate(cases, start=1):
        xp, yp, xc, yc = (dra._f32(v) for v in (xp, yp, xc, yc))
        ref = run_ttc_slope_leaf(pe, xp, yp, xc, yc, i)
        got = dra.build_ttc_slopes([xp, xc], [yp, yc])[0]
        ok = got == ref
        bad += not ok
        print(f"  (x{i-1},y{i-1})=({xp},{yp}) -> (x{i},y{i})=({xc},{yc})  "
              f"dll={ref}  port={got}  {'OK' if ok else 'FAIL'}")

    # end-to-end: a whole curve's slope array via the Python port directly
    # (build_ttc_slopes chains the same per-segment formula just verified).
    pts = [(0.0, 0.0), (0.3, 0.15), (1.0, 1.0), (10.0, 10.0)]
    x = [dra._f32(p[0]) for p in pts]
    y = [dra._f32(p[1]) for p in pts]
    port_slopes = dra.build_ttc_slopes(x, y)
    dll_slopes = [run_ttc_slope_leaf(pe, x[i], y[i], x[i + 1], y[i + 1], i + 1)
                 for i in range(len(x) - 1)]
    ok = port_slopes == dll_slopes
    bad += not ok
    print(f"  whole-curve chain: dll={dll_slopes}  port={port_slopes}  "
          f"{'OK' if ok else 'FAIL'}")
    return bad


# ---------------------------------------------------------------------------
# 8. 0x102290b0 — keepMidPtLut curve construction
# ---------------------------------------------------------------------------

#: (low block off, high block off) for the Normal (0) dispatch, used for all
#: cases below since the dispatch itself is DRA_LIGHTING_DISPATCH_PORTED
#: (already Unicorn-verified) -- this harness places the curve at whichever
#: offset the `lighting` argument under test actually dispatches to.


def _write_ttc_block(emu: Emu, base: int, off: int, curve) -> None:
    n = curve.n_points
    emu.w32(base + off, n)
    for i, v in enumerate(curve.x):
        emu.wf32(base + off + 4 + 4 * i, v)
    for i, v in enumerate(curve.y):
        emu.wf32(base + off + 4 + 0x190 + 4 * i, v)
    for i, v in enumerate(curve.slope):
        emu.wf32(base + off + 4 + 0x320 + 4 * i, v)


def run_keep_midpt_lut(pe: bytes, lighting: int, low, high, max_value: int,
                       low_fp: int, high_fp: int, paper_min: int,
                       paper_max: int, flash_fraction: float, eff_min: int,
                       eff_max: int, fpcw=FPCW_WINDOWS) -> list[int]:
    emu = Emu(pe, fpcw=fpcw)
    params = emu.alloc(0x2000)
    emu.wi16(params + 0x00, max_value)
    emu.wi16(params + 0x02, low_fp)
    emu.wi16(params + 0x04, high_fp)
    emu.wi16(params + 0x06, paper_min)
    emu.wi16(params + 0x08, paper_max)
    emu.wf32(params + 0x28, flash_fraction)
    _lo_off, _hi_off = dra.LIGHTING_DISPATCH.get(
        lighting, dra.LIGHTING_DISPATCH[dra.LIGHTING_NORMAL])[2:4]
    _write_ttc_block(emu, params, _lo_off, low)
    _write_ttc_block(emu, params, _hi_off, high)
    results = emu.alloc(0x40)
    emu.wi16(results + 0x34, eff_min)
    emu.wi16(results + 0x36, eff_max)
    out_lut = emu.alloc((max_value + 4) * 2 + 0x40)
    esp = STACK + 0x40000
    emu.uc.mem_write(esp, struct.pack("<III", RET_MAGIC, lighting, out_lut))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_EAX, params)
    emu.uc.reg_write(UC_X86_REG_ECX, results)
    emu.run(dra.DRA_KEEP_MIDPT_LUT, RET_MAGIC)
    return [struct.unpack("<h", emu.uc.mem_read(out_lut + 2 * i, 2))[0]
            for i in range(max_value + 1)]


def check_keep_midpt_lut(pe: bytes) -> int:
    print("=== 0x102290b0 / dra.keep_midpt_lut (curve construction) ===")
    bad = 0

    def ttc(pts, name="t"):
        c = dra.DraTtc(name=name)
        c.x = [dra._f32(p[0]) for p in pts]
        c.y = [dra._f32(p[1]) for p in pts]
        c.slope = dra.build_ttc_slopes(c.x, c.y)
        return c

    identity = ttc([(0.0, 0.0), (1.0, 1.0), (10.0, 10.0)])
    shaped_lo = ttc([(0.0, 0.0), (0.25, 0.05), (0.5, 0.3), (0.75, 0.7),
                     (1.0, 1.0), (10.0, 10.0)])
    shaped_hi = ttc([(0.0, 0.0), (0.3, 0.4), (0.6, 0.75), (1.0, 1.0),
                     (10.0, 10.0)])

    cases = [
        dict(lighting=0, low=identity, high=identity, max_value=255,
            low_fp=64, high_fp=192, paper_min=0, paper_max=255,
            flash_fraction=0.5, eff_min=10, eff_max=245),
        dict(lighting=0, low=shaped_lo, high=shaped_hi, max_value=255,
            low_fp=64, high_fp=192, paper_min=0, paper_max=255,
            flash_fraction=0.5, eff_min=10, eff_max=245),
        dict(lighting=1, low=shaped_lo, high=shaped_hi, max_value=1023,
            low_fp=200, high_fp=800, paper_min=0, paper_max=1023,
            flash_fraction=0.3, eff_min=5, eff_max=1010),
        dict(lighting=2, low=shaped_lo, high=shaped_hi, max_value=1023,
            low_fp=200, high_fp=800, paper_min=0, paper_max=900,
            flash_fraction=0.4, eff_min=5, eff_max=1010),  # effMax>paperMax,
                                                            # Frontlit adj live
        dict(lighting=0, low=shaped_lo, high=shaped_hi, max_value=255,
            low_fp=64, high_fp=192, paper_min=0, paper_max=200,
            flash_fraction=0.6, eff_min=-20, eff_max=300),  # both clamps live
    ]
    for c in cases:
        ref = run_keep_midpt_lut(pe, **c)
        got = dra.keep_midpt_lut(c["lighting"], c["low"], c["high"],
                                 c["max_value"], c["low_fp"], c["high_fp"],
                                 c["paper_min"], c["paper_max"],
                                 c["flash_fraction"], c["eff_min"],
                                 c["eff_max"])
        ok = got == ref
        bad += not ok
        mism = [] if ok else [(i, r, g) for i, (r, g) in
                              enumerate(zip(ref, got)) if r != g][:6]
        print(f"  lighting={c['lighting']} maxValue={c['max_value']:<5} "
              f"{'OK' if ok else f'FAIL mismatches={mism}'}")

    # ---- FPCW sensitivity: negative control ------------------------------
    print("  -- FPCW sensitivity (negative control) --")
    third_case = dict(lighting=1, low=shaped_lo, high=shaped_hi,
                      max_value=1023, low_fp=200, high_fp=800, paper_min=0,
                      paper_max=1023, flash_fraction=0.3, eff_min=5,
                      eff_max=1010)
    ref_windows = run_keep_midpt_lut(pe, fpcw=FPCW_WINDOWS, **third_case)
    ref_extended = run_keep_midpt_lut(pe, fpcw=FPCW_EXTENDED, **third_case)
    port = dra.keep_midpt_lut(third_case["lighting"], third_case["low"],
                              third_case["high"], third_case["max_value"],
                              third_case["low_fp"], third_case["high_fp"],
                              third_case["paper_min"], third_case["paper_max"],
                              third_case["flash_fraction"],
                              third_case["eff_min"], third_case["eff_max"])
    diverges = ref_windows != ref_extended
    matches_windows = port == ref_windows
    print(f"    0x027f vs 0x037f differ on this case: {diverges} "
          f"(the negative control has teeth iff this is True)")
    print(f"    port == dll@0x027f: {matches_windows}")
    if not diverges:
        print("    NOTE: this specific case did not diverge under FPCW -- "
              "not proof FPCW is irrelevant, just that this case doesn't "
              "probe it; see the case list before trusting FPCW=0x027f.")
    bad += not matches_windows
    return bad


# ---------------------------------------------------------------------------
# 9. 0x10228e40 — validate_params
# ---------------------------------------------------------------------------

#: Baseline values matching the shipped ``ansel-dra-default-default.dpi``.
_VP_BASELINE = dict(
    maxValue=4095, lowFixedPoint=1550, highFixedPoint=1550, paperMin=1200,
    paperMax=2000, minSlope=0.8, maxSlope=1.5, binFactor=4, bDoAverage=1,
    lumWeighting=0.5, edgeWeighting=0.5, bIsBacklit=0, bIsFlash=0,
    flashFraction=0.25, backlitFraction=0.25, startingMinCumPoint=1.0,
    cumPctBelowMin=0.1, startingMaxCumPoint=90.0, cumPctAboveMax=0.2)

_VP_FIELD_LAYOUT: dict[str, tuple[int, str]] = {
    "maxValue": (0x00, "i16"), "lowFixedPoint": (0x02, "i16"),
    "highFixedPoint": (0x04, "i16"), "paperMin": (0x06, "i16"),
    "paperMax": (0x08, "i16"), "minSlope": (0x0C, "f32"),
    "maxSlope": (0x10, "f32"), "binFactor": (0x14, "i32"),
    "bDoAverage": (0x18, "B"), "lumWeighting": (0x1C, "f32"),
    "edgeWeighting": (0x20, "f32"), "bIsBacklit": (0x24, "B"),
    "bIsFlash": (0x25, "B"), "flashFraction": (0x28, "f32"),
    "backlitFraction": (0x2C, "f32"), "startingMinCumPoint": (0x30, "f32"),
    "cumPctBelowMin": (0x34, "f32"), "startingMaxCumPoint": (0x38, "f32"),
    "cumPctAboveMax": (0x3C, "f32"),
}


def _vp_blob(overrides: dict | None = None) -> bytes:
    vals = dict(_VP_BASELINE)
    if overrides:
        vals.update(overrides)
    buf = bytearray(0x40)
    for key, (off, kind) in _VP_FIELD_LAYOUT.items():
        v = vals[key]
        if kind == "i16":
            struct.pack_into("<h", buf, off, v)
        elif kind == "i32":
            struct.pack_into("<i", buf, off, v)
        elif kind == "f32":
            struct.pack_into("<f", buf, off, v)
        elif kind == "B":
            struct.pack_into("<B", buf, off, v)
    return bytes(buf)


def _vp_dra_params(overrides: dict | None = None) -> dict:
    """The subset of ``DraParams``-shaped values ``dra.validate_params``
    reads, built from the same baseline/overrides as ``_vp_blob``."""
    vals = dict(_VP_BASELINE)
    if overrides:
        vals.update(overrides)
    return {k: bool(v) if _VP_FIELD_LAYOUT[k][1] == "B" and k != "binFactor"
           else v for k, v in vals.items()}


def run_validate_params(pe: bytes, overrides: dict | None = None):
    emu = Emu(pe)
    params = emu.alloc(0x40, _vp_blob(overrides))
    out_idx = emu.alloc(4, b"\x00\x00\x00\x00")
    esp = STACK + 0x40000
    emu.uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_ECX, params)
    emu.uc.reg_write(UC_X86_REG_EDI, out_idx)
    emu.run(dra.DRA_VALIDATE_PARAMS, RET_MAGIC)
    eax = emu.uc.reg_read(UC_X86_REG_EAX) & 0xFFFFFFFF
    ok = eax == 0
    idx = struct.unpack("<i", emu.uc.mem_read(out_idx, 4))[0]
    return ok, idx


def check_validate_params(pe: bytes) -> int:
    print("=== 0x10228e40 / dra.validate_params ===")
    print("    (every bound below was read off the real DLL -- a valid")
    print("     baseline plus single-field perturbations -- not decoded")
    print("     from the x87 comparison-flag bytes; see module docstring)")
    bad = 0
    cases: list[tuple[str, dict | None]] = [
        ("baseline (valid)", None),
        ("maxValue=0", dict(maxValue=0)),
        ("maxValue=-1", dict(maxValue=-1)),
        ("lowFixedPoint=-1", dict(lowFixedPoint=-1)),
        ("lowFixedPoint>maxValue", dict(lowFixedPoint=5000)),
        ("highFixedPoint<lowFixedPoint", dict(highFixedPoint=100)),
        ("highFixedPoint>maxValue", dict(highFixedPoint=5000)),
        ("paperMin=-1", dict(paperMin=-1)),
        ("paperMin>paperMax", dict(paperMin=2500)),
        ("paperMax>maxValue", dict(paperMax=5000)),
        ("minSlope=0 (boundary, valid)", dict(minSlope=0.0)),
        ("minSlope=-1", dict(minSlope=-1.0)),
        ("minSlope>maxSlope", dict(minSlope=2.0)),
        ("minSlope=maxSlope (boundary, valid)", dict(minSlope=1.5)),
        ("binFactor=0", dict(binFactor=0)),
        ("binFactor=-1", dict(binFactor=-1)),
        ("binFactor doesn't divide (maxValue+1)", dict(binFactor=7)),
        ("weights sum=1 (valid)", dict(lumWeighting=0.5, edgeWeighting=0.5)),
        ("weights sum=0.9", dict(lumWeighting=0.5, edgeWeighting=0.4)),
        ("weights sum=1.1", dict(lumWeighting=0.5, edgeWeighting=0.6)),
        ("flashFraction=-0.1", dict(flashFraction=-0.1)),
        ("flashFraction=0 (boundary, valid)", dict(flashFraction=0.0)),
        ("flashFraction=1 (boundary, valid)", dict(flashFraction=1.0)),
        ("flashFraction=1.1", dict(flashFraction=1.1)),
        ("backlitFraction=-0.1", dict(backlitFraction=-0.1)),
        ("backlitFraction=1.1", dict(backlitFraction=1.1)),
        ("startingMinCumPoint=-1", dict(startingMinCumPoint=-1.0)),
        ("startingMinCumPoint=50 (boundary, valid)",
         dict(startingMinCumPoint=50.0)),
        ("startingMinCumPoint=50.1", dict(startingMinCumPoint=50.1)),
        ("cumPctBelowMin=-1", dict(cumPctBelowMin=-1.0)),
        ("cumPctBelowMin=25 (boundary, valid)", dict(cumPctBelowMin=25.0)),
        ("cumPctBelowMin=25.1", dict(cumPctBelowMin=25.1)),
        ("startingMaxCumPoint=49.9", dict(startingMaxCumPoint=49.9)),
        ("startingMaxCumPoint=50 (boundary, valid)",
         dict(startingMaxCumPoint=50.0)),
        ("startingMaxCumPoint=100 (boundary, valid)",
         dict(startingMaxCumPoint=100.0)),
        ("startingMaxCumPoint=100.1", dict(startingMaxCumPoint=100.1)),
        ("cumPctAboveMax=-1", dict(cumPctAboveMax=-1.0)),
        ("cumPctAboveMax=25 (boundary, valid)", dict(cumPctAboveMax=25.0)),
        ("cumPctAboveMax=25.1", dict(cumPctAboveMax=25.1)),
        ("maxValue=99,binFactor=10 (exact -> valid)",
         dict(maxValue=99, binFactor=10, lowFixedPoint=0, highFixedPoint=99,
              paperMin=0, paperMax=99)),
        ("maxValue=100,binFactor=10 (101/10 not exact)",
         dict(maxValue=100, binFactor=10, lowFixedPoint=0, highFixedPoint=100,
              paperMin=0, paperMax=100)),
    ]
    for name, ov in cases:
        dll_ok, dll_idx = run_validate_params(pe, ov)
        got = dra.validate_params(_vp_dra_params(ov))
        port_ok = got == 0
        ok = (dll_ok == port_ok) and (dll_idx == got if not dll_ok else True)
        bad += not ok
        print(f"  {name:45s} dll=({dll_ok},{dll_idx})  port={got}  "
              f"{'OK' if ok else 'FAIL'}")
    print(f"  {len(cases)} cases: {'all OK' if not bad else f'{bad} FAILED'}")
    return bad


# ---------------------------------------------------------------------------
# 10. 0x1022a820 — alloc
# ---------------------------------------------------------------------------


def run_alloc(pe: bytes, n_small: int, alloc_lum: bool, alloc_edge: bool,
             bin_factor: int):
    emu = Emu(pe)
    install_allocator_hooks(emu)
    impl = emu.alloc(0x2000)
    emu.w32(impl + 0x24, bin_factor)   # generateLut/alloc's own binFactor
                                        # read, params-relative +0x14 == +0x24
    out_storage = emu.alloc(0x40)
    esp = STACK + 0x40000
    emu.uc.mem_write(
        esp, struct.pack("<IIIII", RET_MAGIC, out_storage, n_small,
                         1 if alloc_lum else 0, 1 if alloc_edge else 0))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_ECX, impl)
    emu.run(dra.DRA_ALLOC_BUFFERS, RET_MAGIC)
    R = impl + 0x1C88

    def ptr(off):
        return emu.r32(R + off)

    return dict(
        nSmallBins=emu.r32(R + 0x00), LumHist=ptr(0x04), EdgeHist=ptr(0x08),
        nLargeBins=struct.unpack("<i", emu.uc.mem_read(R + 0x0C, 4))[0],
        LumLargeHist=ptr(0x14), LumCumHist=ptr(0x18), EdgeLargeHist=ptr(0x20),
        EdgeCumHist=ptr(0x24), Scratch=ptr(0x28), DraLut=ptr(0x38))


def check_alloc(pe: bytes) -> int:
    print("=== 0x1022a820 / dra.alloc ===")
    print("    (ABI read off the real Cap-wrapper call sites, not guessed;")
    print("     operator new hooked to the emulator's bump allocator)")
    bad = 0
    for name, n_small, al, ae, bf in [
        ("lum-only (variant A shape)", 4096, True, False, 4),
        ("edge-only", 4096, False, True, 4),
        ("both (variant B shape)", 4096, True, True, 4),
        ("small, binFactor=1", 256, True, True, 1),
    ]:
        r = run_alloc(pe, n_small, al, ae, bf)
        port = dra.alloc(n_small, al, ae, bf)
        ok = (r["nSmallBins"] == port.nSmallBins == n_small
              and r["nLargeBins"] == port.nLargeBins
              and (r["LumHist"] != 0) == (port.LumHist is not None) == al
              and (r["EdgeHist"] != 0) == (port.EdgeHist is not None) == ae
              and (r["LumLargeHist"] != 0) == (port.LumLargeHist is not None) == al
              and (r["EdgeLargeHist"] != 0) == (port.EdgeLargeHist is not None) == ae
              and (r["LumCumHist"] != 0) == al
              and (r["EdgeCumHist"] != 0) == ae
              and r["Scratch"] != 0 and port.Scratch is not None
              and r["DraLut"] != 0 and port.DraLut is not None)
        bad += not ok
        print(f"  {name:28s} nLargeBins dll={r['nLargeBins']} "
              f"port={port.nLargeBins}  buffers-match={ok}  "
              f"{'OK' if ok else 'FAIL'}")
    print(f"  {'all OK' if not bad else f'{bad} FAILED'}")
    return bad


# ---------------------------------------------------------------------------
# 11. 0x1022ab50 — generateLut, called directly (not through analyze())
# ---------------------------------------------------------------------------


def run_generate_lut(pe: bytes, p: "dra.DraParams", n_small: int,
                     n_large: int, lum_hist, edge_hist, tone_lut, lighting):
    emu = Emu(pe)
    install_allocator_hooks(emu)
    impl = build_dra_impl(emu, p)
    R = impl + 0x1C88
    emu.w32(R + 0x00, n_small)
    emu.uc.mem_write(R + 0x0C, struct.pack("<i", n_large))
    if lum_hist is not None:
        lum_a = emu.alloc(4 * n_small,
                          b"".join(struct.pack("<i", v) for v in lum_hist))
        emu.w32(R + 0x04, lum_a)
        emu.w32(R + 0x14, emu.alloc(4 * max(n_large, 1)))
        emu.w32(R + 0x18, emu.alloc(4 * max(n_large, 1)))
    if edge_hist is not None:
        edge_a = emu.alloc(4 * n_small,
                           b"".join(struct.pack("<i", v) for v in edge_hist))
        emu.w32(R + 0x08, edge_a)
        emu.w32(R + 0x20, emu.alloc(4 * max(n_large, 1)))
        emu.w32(R + 0x24, emu.alloc(4 * max(n_large, 1)))
    emu.w32(R + 0x28, emu.alloc(4 * n_small))
    emu.w32(R + 0x38, emu.alloc(2 * n_small))
    tone_a = 0
    if tone_lut is not None:
        tone_a = emu.alloc(2 * n_small,
                           b"".join(struct.pack("<h", v) for v in tone_lut))
    esp = STACK + 0x40000
    out_storage = emu.alloc(0x40)
    emu.uc.mem_write(
        esp, struct.pack("<IIII", RET_MAGIC, out_storage, lighting, tone_a))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_ECX, impl)
    emu.run(dra.DRA_GENERATE_LUT, RET_MAGIC)
    lut_ptr = emu.r32(R + 0x38)
    lut = list(struct.unpack(f"<{n_small}h",
                             emu.uc.mem_read(lut_ptr, 2 * n_small)))
    eff_min = struct.unpack("<h", emu.uc.mem_read(R + 0x34, 2))[0]
    eff_max = struct.unpack("<h", emu.uc.mem_read(R + 0x36, 2))[0]
    return lut, eff_min, eff_max


def check_generate_lut(pe: bytes) -> int:
    print("=== 0x1022ab50 / dra.generate_lut (called directly) ===")
    print("    (the orchestration: toneLut-gated remap, rebin, cumulative")
    print("     sum, cum_bounds, the tri-state eff-bounds merge, then")
    print("     keepMidPtLut -- assembled from already-verified pieces)")
    bad = 0
    p = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    n_small = dra._s16(p["maxValue"]) + 1
    n_large = n_small // int(p["binFactor"])
    rng = random.Random(0x6E4)
    lum = [rng.randint(0, 60) for _ in range(n_small)]
    edge = [rng.randint(0, 60) for _ in range(n_small)]
    tone_nonid = [max(0, min(n_small - 1, int(i * 0.9))) for i in range(n_small)]
    cases = [
        ("both, lighting=0", lum, edge, None, 0),
        ("both, lighting=1 (Backlit)", lum, edge, None, 1),
        ("both, lighting=2 (Frontlit)", lum, edge, None, 2),
        ("lum-only (edge sentinel -1)", lum, None, None, 0),
        ("edge-only (lum sentinel -1)", None, edge, None, 0),
        ("both + toneLut remap live", lum, edge, tone_nonid, 0),
    ]
    for name, lh, eh, tl, lighting in cases:
        dll_lut, dll_min, dll_max = run_generate_lut(
            pe, p, n_small, n_large, lh, eh, tl, lighting)
        r = dra.alloc(n_small, lh is not None, eh is not None,
                      int(p["binFactor"]))
        if lh is not None:
            r.LumHist = list(lh)
        if eh is not None:
            r.EdgeHist = list(eh)
        port_lut = dra.generate_lut(r, p, lighting, tl)
        ok = (dll_lut == port_lut and dll_min == r.effMin
              and dll_max == r.effMax)
        bad += not ok
        print(f"  {name:32s} eff=({dll_min},{dll_max})  {'OK' if ok else 'FAIL'}")
        if not ok:
            mism = [(i, a, b) for i, (a, b) in enumerate(zip(dll_lut, port_lut))
                    if a != b][:6]
            print(f"    mismatches: {mism}")
    print(f"  {'all OK' if not bad else f'{bad} FAILED'}")
    return bad


# ---------------------------------------------------------------------------
# 12/13. 0x1022af20 / 0x1022b530 — the two analyze overloads, end to end
#
# Run from their TRUE entry points (not a mid-function slice like every
# other check above) -- ecx=impl, stack args as read off the real, compiled
# Cap-wrapper call sites (0x10131020 -> 0x1022af20 at 0x10131071;
# 0x10131100 -> 0x1022b530 at 0x1013115b). GET_SCENE_CONTEXT is mocked (see
# install_scene_context_mock) to hand back a real, working
# build_empty_scene_context() -- so find("lighting") itself still runs for
# real, unmocked, and (being a real empty map) always misses, landing on
# lighting=0/Normal, exactly DRA_LIGHTING_BRANCH_PORTED's "miss continues"
# finding. The refcounted "cap" argument is passed NULL, which every real
# use of it in both functions is unconditionally gated on -- confirmed by
# these runs completing without a fault, not assumed from the decompile.
# ---------------------------------------------------------------------------


def run_analyze_image(pe: bytes, p: "dra.DraParams", pixels: bytes,
                      width: int, height: int):
    emu = Emu(pe)
    install_common_hooks(emu)
    install_allocator_hooks(emu)
    ctx = build_empty_scene_context(emu)
    install_scene_context_mock(emu, ctx)
    impl = build_dra_impl(emu, p)

    img = emu.alloc(0x40)
    emu.w32(img + 0x0C, height)
    emu.w32(img + 0x10, width)
    px = emu.alloc(len(pixels), pixels)
    emu.w32(img + 0x20, px)

    esp = STACK + 0x40000
    out_storage = emu.alloc(0x40)
    emu.uc.mem_write(
        esp, struct.pack("<IIIII", RET_MAGIC, out_storage, 0, 0, img))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_ECX, impl)
    emu.run(dra.DRA_ANALYZE_IMAGE, RET_MAGIC)

    n_small = emu.r32(impl + 0x1C88)
    lut_ptr = emu.r32(impl + 0x1CC0)
    lut = list(struct.unpack(f"<{n_small}h",
                             emu.uc.mem_read(lut_ptr, 2 * n_small)))
    return lut, n_small


def check_analyze_image(pe: bytes) -> int:
    print("=== 0x1022af20 / dra.analyze_image, end to end from TRUE entry ===")
    bad = 0
    p = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    rng = random.Random(0x1A1)
    cases = [
        ("4x4 uniform", 4, 4, [(100, 100, 100)] * 16),
        ("8x6 random", 8, 6,
         [(rng.randint(0, 4000), rng.randint(0, 4000), rng.randint(0, 4000))
          for _ in range(48)]),
        # NOTE: pixel triples are kept within [0, maxValue] here on purpose.
        # A triple whose average lands outside [0, nSmallBins) makes the
        # real DLL's lum_histogram (0x1022b1a0) index *before* or *past* the
        # allocated histogram buffer -- genuine heap corruption in the real
        # code, not a divergence in the port. Confirmed directly: a
        # (-2000..4000)-range case produced avg-lum indices as low as -1206
        # (43 of 256 samples out of [0, 4095]), and the DLL's own
        # nearby-heap layout (not the algorithm) then determines the
        # "answer" -- not something a port can or should try to match
        # byte-for-byte. Real scan data never produces such values.
        ("16x16 random, wider spread", 16, 16,
         [(rng.randint(0, 4000), rng.randint(0, 4000), rng.randint(0, 4000))
          for _ in range(256)]),
    ]
    for name, w, h, triples in cases:
        pixels = b"".join(struct.pack("<hhh", *t) for t in triples)
        dll_lut, n_small = run_analyze_image(pe, p, pixels, w, h)
        port = dra.analyze_image(p, pixels, w, h, 0)
        ok = dll_lut == port.DraLut
        bad += not ok
        print(f"  {name:28s} n={n_small}  {'OK' if ok else 'FAIL'}")
        if not ok:
            mism = [(i, a, b) for i, (a, b) in
                    enumerate(zip(dll_lut, port.DraLut)) if a != b][:6]
            print(f"    mismatches: {mism} (of {n_small})")
    print(f"  {'all OK' if not bad else f'{bad} FAILED'}")
    return bad


def run_analyze_hist(pe: bytes, p: "dra.DraParams", lum_hist, edge_hist,
                     tone_lut, n_small: int):
    emu = Emu(pe)
    install_common_hooks(emu)
    install_allocator_hooks(emu)
    ctx = build_empty_scene_context(emu)
    install_scene_context_mock(emu, ctx)
    impl = build_dra_impl(emu, p)

    lum_a = edge_a = tone_a = 0
    if lum_hist is not None:
        lum_a = emu.alloc(4 * n_small,
                          b"".join(struct.pack("<i", v) for v in lum_hist))
    if edge_hist is not None:
        edge_a = emu.alloc(4 * n_small,
                           b"".join(struct.pack("<i", v) for v in edge_hist))
    if tone_lut is not None:
        tone_a = emu.alloc(2 * n_small,
                           b"".join(struct.pack("<h", v) for v in tone_lut))

    esp = STACK + 0x40000
    out_storage = emu.alloc(0x40)
    emu.uc.mem_write(
        esp, struct.pack("<IIIIIII", RET_MAGIC, out_storage, 0, 0, lum_a,
                         edge_a, tone_a))
    emu.uc.reg_write(UC_X86_REG_ESP, esp)
    emu.uc.reg_write(UC_X86_REG_ECX, impl)
    emu.run(dra.DRA_ANALYZE_HIST, RET_MAGIC)

    n_out = emu.r32(impl + 0x1C88)
    lut_ptr = emu.r32(impl + 0x1CC0)
    lut = list(struct.unpack(f"<{n_out}h",
                             emu.uc.mem_read(lut_ptr, 2 * n_out)))
    return lut


def check_analyze_hist(pe: bytes) -> int:
    print("=== 0x1022b530 / dra.analyze_hist, end to end from TRUE entry ===")
    bad = 0
    p = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    n_small = dra._s16(p["maxValue"]) + 1
    rng = random.Random(0x4D2)
    lum = [rng.randint(0, 50) for _ in range(n_small)]
    edge = [rng.randint(0, 50) for _ in range(n_small)]
    tone_nonid = [max(0, min(n_small - 1, int(i * 0.8))) for i in range(n_small)]
    spike = [0] * n_small
    spike[100] = 5000
    spike[3000] = 3000
    cases = [
        ("both, identity toneLut", lum, edge, list(range(n_small))),
        ("both, non-identity toneLut", lum, edge, tone_nonid),
        ("both, no toneLut", lum, edge, None),
        ("lum-only, no toneLut", lum, None, None),
        ("edge-only, no toneLut", None, edge, None),
        ("spiky lum-only", spike, None, None),
    ]
    for name, lh, eh, tl in cases:
        dll_lut = run_analyze_hist(pe, p, lh, eh, tl, n_small)
        port = dra.analyze_hist(p, lh, eh, tl, 0)
        ok = dll_lut == port.DraLut
        bad += not ok
        print(f"  {name:28s} {'OK' if ok else 'FAIL'}")
        if not ok:
            mism = [(i, a, b) for i, (a, b) in
                    enumerate(zip(dll_lut, port.DraLut)) if a != b][:6]
            print(f"    mismatches: {mism} (of {n_small})")

    print("  -- no-analysis-data throw (both histograms absent) --")
    try:
        dra.analyze_hist(p, None, None, None, 0)
        print("    port FAILED to raise")
        bad += 1
    except dra.DraError as exc:
        ok = "No analysis data was provided" in str(exc)
        bad += not ok
        print(f"    port raises DraError({exc!r})  {'OK' if ok else 'FAIL'}")
    print(f"  {'all OK' if not bad else f'{bad} FAILED'}")
    return bad


# ---------------------------------------------------------------------------
# 14. 0x102283d5..0x10228965 — the .dpi parser's per-line body
# ---------------------------------------------------------------------------

#: The loop body of ``AnsDraDPI::readAscii`` (``0x102283a0``): one already-read
#: line in, zero or one params-field write out.  Slicing the body (rather than
#: the whole function) is what makes this runnable at all — the enclosing
#: function is built around a live ``std::basic_ifstream``, whose ``getline``
#: and ``ios_base`` state machine would have to be reconstructed wholesale to
#: reach the same bytes.  The body itself is the entire parse semantics.
VA_DPI_LINE_TOP = 0x102283D5
VA_DPI_LINE_BOTTOM = 0x10228965

#: Frame offsets, read off the real ``lea``s (each one's ``esp`` displacement
#: corrected for the pushes in flight at that instruction — see the comments).
DPI_OFF_LINE = 0x30C      # 0x10228411 `lea edx,[esp+0x314]`, esp = F-8
DPI_OFF_KEY = 0x58        # 0x10228431 `lea esi,[esp+0x58]`,  esp = F
DPI_OFF_VALUE = 0x1F0     # 0x10228404 `lea eax,[esp+0x1f0]`, esp = F

#: ``ebp`` is the params object's base; every field lands at ``ebp+0x2c+off``
#: where ``off`` is DRA_PARAMS_LAYOUT's own (generateLut-relative) offset.
DPI_PARAMS_SKEW = dra.DRA_PARAMS_BASE_SKEW      # 0x2c
DPI_SCALAR_SPAN = 0x40    # maxValue .. cumPctAboveMax, the whole scalar image


def _c_sscanf(read_cstr, s: str, fmt: str, write) -> int:
    """A C ``sscanf`` for the five specifiers ``0x102283a0`` actually uses.

    This is CRT code, not vendor code: ``ebx`` holds the ``MSVCR71!sscanf``
    import and there is nothing of Kodak's inside it.  Hooking it is
    therefore not a gap in the verification of the *parser* — what the real
    DLL bytes are being asked here is which key matches, which destination
    offset that key's arm passes, and which format string it passes, and all
    three of those are executed for real.  Stated explicitly so this is not
    mistaken for a full emulation of the conversion itself.
    """
    si = fi = ai = n = 0
    ws = " \t\n\r\v\f"
    args = []

    def take_token() -> str | None:
        nonlocal si
        while si < len(s) and s[si] in ws:
            si += 1
        st = si
        while si < len(s) and s[si] not in ws:
            si += 1
        return s[st:si] if si > st else None

    while fi < len(fmt):
        c = fmt[fi]
        if c in ws:
            fi += 1
            while si < len(s) and s[si] in ws:
                si += 1
            continue
        if c != "%":
            if si < len(s) and s[si] == c:
                si += 1
                fi += 1
                continue
            return n
        fi += 1
        length = ""
        while fmt[fi] in "hl":
            length += fmt[fi]
            fi += 1
        conv = fmt[fi]
        fi += 1
        if conv == "s":
            tok = take_token()
            if tok is None:
                return n
            write(ai, tok.encode() + b"\x00")
        elif conv == "c":
            if si >= len(s):
                return n
            write(ai, s[si].encode())
            si += 1
        elif conv in "df":
            tok = take_token()
            if tok is None:
                return n
            if conv == "d":
                v = dra._sscanf_int(tok, 16 if length == "h" else 32)
                if v is None:
                    return n
                write(ai, struct.pack("<h" if length == "h" else "<i", v))
            else:
                v = dra._sscanf_float(tok)
                if v is None:
                    return n
                write(ai, struct.pack("<f", v))
        else:
            raise AssertionError(f"unhandled %{conv}")
        ai += 1
        n += 1
    del args
    return n


# MSVCP71 std::basic_string<char> imports the .ttc arm (0x102288bf..
# 0x1022894b) walks through to turn "<dpi dir>\" + "<value>" into a path.
IAT_STR_CTOR_VOID = 0x10573248     # basic_string()
IAT_STR_NPOS = 0x10573128          # &basic_string::npos (DATA, not a call)
IAT_STR_RFIND = 0x105732E8         # rfind(const char*, size_type, size_type)
IAT_STR_SUBSTR = 0x105732DC        # substr(&out, pos, count)
IAT_STR_ASSIGN = 0x10573134        # operator=(const basic_string&)
IAT_STR_APPEND_PBD = 0x105731D4    # operator+=(const char*)
IAT_STRSTR = 0x1057342C            # MSVCR71 strstr

#: Frame slot holding the ``.dpi``'s own path string — ``mov edi,[esp+0x420]``
#: at ``0x102288c6``, the object ``rfind``/``substr`` are called on.
DPI_OFF_PATH_OBJ = 0x420


def _read_cstr(emu: Emu, p: int) -> str:
    out = bytearray()
    while True:
        b = emu.uc.mem_read(p, 1)[0]
        if b == 0:
            break
        out.append(b)
        p += 1
    return out.decode("latin1")


# --- MSVCP71 basic_string<char>, as THIS DLL's own code addresses it -------
#
# The module-level write_msvc_string() above lays the object out as
# {union at +0x00, _Mysize +0x10, _Myres +0x14}.  The real code in the .ttc
# arm does not agree with that, and says so itself: the string is
# constructed at ``esp+0x20`` (0x10228803 `lea ecx,[esp+0x20]`) and then read
# back at 0x1022893a..0x10228945 as
#
#     cmp dword [esp+0x38], 0x10      ; _Myres, i.e. base+0x18
#     mov eax, dword [esp+0x24]       ; _Ptr,   i.e. base+0x04
#     jae  .have_ptr
#     lea eax, [esp+0x24]             ; _Buf,   i.e. base+0x04
#
# so this build's layout is {allocator +0x00, union +0x04, _Mysize +0x14,
# _Myres +0x18} -- the VC7.1 `_String_val` shape, where the (empty) allocator
# member still occupies the first 4 bytes.  Confirmed positively, not just
# structurally: with the +0x00 layout the real DLL hands 0x10227c60 an EMPTY
# path (it reads a C string out of the middle of the inline buffer, which is
# NUL for any string long enough to be heap-allocated); with the layout below
# it hands over the correct "<dpi dir>\<value>", which is what check_parse_dpi
# asserts.
STR_UNION_OFF = 0x04
STR_MYSIZE_OFF = 0x14
STR_MYRES_OFF = 0x18
STR_BUF_CAP = 16


def write_msvc_string_v71(emu: Emu, obj: int, text: bytes) -> None:
    n = len(text)
    emu.uc.mem_write(obj, b"\x00" * 4)
    if n < STR_BUF_CAP:
        emu.uc.mem_write(obj + STR_UNION_OFF, text + b"\x00" * (16 - n))
        emu.w32(obj + STR_MYRES_OFF, 15)
    else:
        buf = emu.alloc(n + 1, text + b"\x00")
        emu.w32(obj + STR_UNION_OFF, buf)
        emu.uc.mem_write(obj + STR_UNION_OFF + 4, b"\x00" * 12)
        emu.w32(obj + STR_MYRES_OFF, n)
    emu.w32(obj + STR_MYSIZE_OFF, n)


def _read_msvc_string(emu: Emu, obj: int) -> str:
    res = emu.r32(obj + STR_MYRES_OFF)
    return _read_cstr(
        emu,
        emu.r32(obj + STR_UNION_OFF) if res >= STR_BUF_CAP
        else obj + STR_UNION_OFF)


def run_parse_dpi_line(pe: bytes, line: str, seed: bytes,
                       dpi_path: str = r"C:\ansel\dra\ansel-dra.dpi"):
    """Execute the real per-line body on ``line``.

    Returns ``(scalar params image, sscanf calls, ttc calls)`` where the
    sscanf calls are ``(format, destination offset)`` — so a wrong
    destination is a visible diff rather than a silent one — and the ttc
    calls are ``(block offset, resolved path)`` captured at the real
    ``push esi; push eax; call 0x10227c60`` (``0x10228949``).
    """
    emu = Emu(pe)
    install_common_hooks(emu)
    frame = STACK + 0x300000
    params = HEAP + 0x100000
    emu.uc.mem_write(frame, b"\x00" * 0x600)
    emu.uc.mem_write(params - DPI_PARAMS_SKEW, b"\x00" * 0x400)
    emu.uc.mem_write(params, seed)
    emu.uc.mem_write(frame + DPI_OFF_LINE, line.encode() + b"\x00")

    # The .dpi's own path object, and the npos datum rfind is compared to.
    path_obj = emu.alloc(0x30)
    write_msvc_string_v71(emu, path_obj, dpi_path.encode())
    emu.w32(frame + DPI_OFF_PATH_OBJ, path_obj)
    npos_cell = emu.alloc(4)
    emu.w32(npos_cell, 0xFFFFFFFF)
    emu.w32(IAT_STR_NPOS, npos_cell)

    seen: list[tuple[str, int]] = []
    ttc: list[tuple[int, str]] = []

    def sscanf_stub(e: Emu, args: int):
        inp = e.r32(args + 0)
        fmt = _read_cstr(e, e.r32(args + 4))
        ptrs = [e.r32(args + 8 + 4 * i) for i in range(fmt.count("%"))]
        seen.append((fmt, ptrs[0] - params if ptrs else -1))
        rc = _c_sscanf(None, _read_cstr(e, inp), fmt,
                       lambda i, b: e.uc.mem_write(ptrs[i], b))
        return rc, 0            # cdecl: the caller's `add esp,N` pops

    stub = emu.stub()
    emu.hook_stdcall(stub, sscanf_stub)

    # --- the .ttc arm's std::string plumbing ------------------------------
    def str_ctor_void(e: Emu, args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        write_msvc_string_v71(e, this, b"")
        return this, 0

    def str_rfind(e: Emu, args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        s = _read_msvc_string(e, this)
        needle = _read_cstr(e, e.r32(args + 0))[:e.r32(args + 8)]
        idx = s.rfind(needle)
        return (0xFFFFFFFF if idx < 0 else idx), 12

    def str_substr(e: Emu, args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        out, pos, cnt = e.r32(args), e.r32(args + 4), e.r32(args + 8)
        write_msvc_string_v71(e, out,
                              _read_msvc_string(e, this)[pos:pos + cnt]
                              .encode())
        return out, 12

    def str_assign(e: Emu, args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        write_msvc_string_v71(e, this,
                              _read_msvc_string(e, e.r32(args)).encode())
        return this, 4

    def str_append_pbd(e: Emu, args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        write_msvc_string_v71(
            e, this,
            (_read_msvc_string(e, this) + _read_cstr(e, e.r32(args))).encode())
        return this, 4

    def strstr_stub(e: Emu, args: int):
        hay_p, ned_p = e.r32(args), e.r32(args + 4)
        i = _read_cstr(e, hay_p).find(_read_cstr(e, ned_p))
        return (0 if i < 0 else hay_p + i), 0        # cdecl

    emu.patch_iat_stub(IAT_STR_CTOR_VOID, str_ctor_void)
    emu.patch_iat_stub(IAT_STR_RFIND, str_rfind)
    emu.patch_iat_stub(IAT_STR_SUBSTR, str_substr)
    emu.patch_iat_stub(IAT_STR_ASSIGN, str_assign)
    emu.patch_iat_stub(IAT_STR_APPEND_PBD, str_append_pbd)
    emu.patch_iat_stub(IAT_STRSTR, strstr_stub)

    def ttc_leaf(e: Emu, args: int):
        # 0x10228949: `push esi` (the block base) then `push eax` (the path).
        block = e.uc.reg_read(UC_X86_REG_ESI)
        ttc.append((block - params, _read_cstr(e, e.r32(args))))
        return None, 0          # cdecl: `add esp,8` at 0x10228950 pops
    emu.hook_stdcall(dra.DRA_TTC_SLOPE_LEAF, ttc_leaf)

    emu.uc.reg_write(UC_X86_REG_ESP, frame)
    emu.uc.reg_write(UC_X86_REG_EBP, params - DPI_PARAMS_SKEW)
    emu.uc.reg_write(UC_X86_REG_EBX, stub)
    emu.run(VA_DPI_LINE_TOP, VA_DPI_LINE_BOTTOM)
    return bytes(emu.uc.mem_read(params, DPI_SCALAR_SPAN)), seen, ttc


def _port_scalar_image(values: dict, base: bytes) -> bytes:
    """The port's own params image over ``base``.

    Only keys the port actually stored are written, so a field whose
    conversion failed keeps ``base``'s bytes — which is precisely the real
    DLL's behaviour (a failed ``sscanf`` arm leaves the field alone), and is
    why the check seeds with non-zero bytes rather than zeros.
    """
    buf = bytearray(base)
    for key, off, kind in dra.DRA_PARAMS_LAYOUT:
        if kind == "ttc" or key not in values:
            continue
        v = values[key]
        if kind == "i16":
            struct.pack_into("<h", buf, off, int(v))
        elif kind == "i32":
            struct.pack_into("<i", buf, off, int(v))
        elif kind == "f32":
            struct.pack_into("<f", buf, off, float(v))
        elif kind == "bool":
            buf[off] = 1 if v else 0
    return bytes(buf)


#: Real shipped lines, plus the adversarial ones that separate an
#: sscanf-shaped parse from a ``str.split``-shaped one.
DPI_LINE_CASES: tuple[str, ...] = (
    # --- every line of the real ansel-dra-default-default.dpi -------------
    "# AnsDraDPI defaults",
    "maxValue = 4095",
    "lowFixedPoint = 1550",
    "highFixedPoint = 1550",
    "paperMin = 1200",
    "paperMax = 2000",
    "minSlope = 0.8",
    "maxSlope = 1.5",
    "binFactor = 4",
    "bDoAverage = true",
    "lumWeighting = 0.5",
    "edgeWeighting = 0.5",
    "bIsBacklit = false",
    "bIsFlash = false",
    "flashFraction = 0.25",
    "backlitFraction = 0.25",
    "startingMinCumPoint = 1",
    "cumPctBelowMin = 0.1",
    "startingMaxCumPoint = 90",
    "cumPctAboveMax = 0.2",
    # The six .ttc arms: block offset + resolved path, both checked.
    "lowNormalTTC = lowNormal.ttc",
    "highNormalTTC = highNormal.ttc",
    "lowBacklitTTC = lowBacklit.ttc",
    "highBacklitTTC = highBacklit.ttc",
    "lowFrontlitTTC = lowFrontlit.ttc",
    "highFrontlitTTC = highFrontlit.ttc",
    # strstr(key,"TTC") hits but no arm matches -> must not load a curve.
    "bogusTTCkey = x.ttc",
    # --- comment / blank rejection (0x102283d5..0x102283fe) ---------------
    "",
    "*starred",
    "\r",
    "# maxValue = 1",
    "  # maxValue = 1",        # NOT caught by the first-char test; caught
                               # by the 2-conversion test instead
    # --- the tokeniser (0x10228423 `cmp eax,2`) ---------------------------
    "maxValue=4095",           # 1 conversion -> line REJECTED
    "maxValue =4095",          # '=' matches, then %s -> 4095: ACCEPTED
    "maxValue= 4095",          # %s eats "maxValue=", then no '=': REJECTED
    "   maxValue   =   4095",  # leading/extra whitespace: ACCEPTED
    "maxValue",                # 1 conversion
    "maxValue =",              # 1 conversion (no value token)
    "maxValue = ",
    "maxValue == 4095",        # value token is "=", %hd then fails
    # --- the three bools (%c + `cmp 0x74`) --------------------------------
    "bDoAverage = true",
    "bDoAverage = false",
    "bDoAverage = True",       # capital T -> FALSE
    "bDoAverage = TRUE",       # -> FALSE
    "bDoAverage = t",          # -> TRUE
    "bDoAverage = tomato",     # -> TRUE
    "bDoAverage = 1",          # -> FALSE
    "bIsBacklit = true",
    "bIsFlash = true",
    "bIsFlash = f",
    # --- numeric conversion edge cases ------------------------------------
    "maxValue = 4095abc",      # %hd stops at the junk
    "maxValue = -1",
    "maxValue = 65535",        # %hd wraps into int16
    "maxValue = 70000",        # wraps
    "maxValue = abc",          # conversion FAILS -> field left untouched
    "binFactor = 100000",
    "binFactor = -7",
    "minSlope = .5",
    "minSlope = 1e2",
    "minSlope = -0.25",
    "minSlope = abc",          # fails -> untouched
    "cumPctAboveMax = 0.2",
    # --- unknown keys (strstr(key,"TTC") gate, 0x102287f2) ----------------
    "notAKey = 5",
    "maxValu = 4095",          # near-miss on the repe cmpsb
    "maxValues = 4095",        # longer: NUL byte makes cmpsb differ
)


def check_parse_dpi(pe: bytes) -> int:
    print("=== 0x102283d5..0x10228965 / dra.parse_dpi_line "
          "(.dpi per-line body) ===")
    print("    (the real repe-cmpsb key chain and the real destination\n"
          "     offsets execute for real; MSVCR71 sscanf is hooked, since\n"
          "     it is CRT and not vendor code -- see _c_sscanf)")
    # A non-zero seed proves "conversion failed -> field left UNWRITTEN":
    # with a zeroed params block a failed write and a written 0 look alike.
    seed = bytes((i * 37 + 11) & 0xFF for i in range(DPI_SCALAR_SPAN))
    bad = 0
    for line in DPI_LINE_CASES:
        ref, seen, ttc = run_parse_dpi_line(pe, line, seed)
        values: dict = {}
        dra.parse_dpi_line(line, values)
        got = _port_scalar_image(values, seed)
        ok = got == ref
        # The six *TTC arms: the block offset the real code hands
        # 0x10227c60 must be DRA_PARAMS_LAYOUT's own offset for that key,
        # and the path must be the .dpi's directory + the value token.
        port_ttc = [(off, r"C:\ansel\dra" + "\\" + str(values[k]))
                    for k, off, kind in dra.DRA_PARAMS_LAYOUT
                    if kind == "ttc" and k in values]
        ok_ttc = ttc == port_ttc
        ok = ok and ok_ttc
        bad += not ok
        note = ""
        if seen:
            note = "  sscanf" + "".join(
                f" {f!r}@{o:#x}" if o >= 0 else f" {f!r}" for f, o in seen)
        if ttc:
            note += "  ttc=" + ", ".join(f"{o:#x}:{p}" for o, p in ttc)
        print(f"  {line!r:30.30}  {'OK' if ok else 'FAIL'}{note}")
        if not ok:
            diff = [(i, ref[i], got[i]) for i in range(DPI_SCALAR_SPAN)
                    if ref[i] != got[i]]
            if diff:
                print(f"      byte diffs (off, dll, port): {diff[:8]}")
            if not ok_ttc:
                print(f"      ttc dll={ttc}  port={port_ttc}")

    # The whole shipped file, end to end, against the real body line by line.
    dpi = dra.VENDOR_DRA_DIR / "ansel-dra-default-default.dpi"
    if dpi.exists():
        acc = bytearray(DPI_SCALAR_SPAN)
        values: dict = {}
        for line in dpi.read_text().splitlines():
            ref, _s, _t = run_parse_dpi_line(pe, line, bytes(acc))
            acc = bytearray(ref)
            dra.parse_dpi_line(line, values)
        got = _port_scalar_image(values, bytes(DPI_SCALAR_SPAN))
        ok = got == bytes(acc)
        bad += not ok
        print(f"  whole shipped .dpi, line by line: "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            diff = [(i, acc[i], got[i]) for i in range(DPI_SCALAR_SPAN)
                    if acc[i] != got[i]]
            print(f"      byte diffs (off, dll, port): {diff[:8]}")
        # and that DraParams.load -- what every caller in the repo actually
        # uses -- lands on that same real-DLL-produced image.
        p = dra.DraParams.load(dra.VENDOR_DRA_DIR)
        ok2 = _port_scalar_image(
            p.values, bytes(DPI_SCALAR_SPAN)) == bytes(acc)
        bad += not ok2
        print(f"  DraParams.load == real DLL image:  "
              f"{'OK' if ok2 else 'FAIL'}")
    print(f"  {'all OK' if not bad else f'{bad} FAILED'}")
    return bad


# ---------------------------------------------------------------------------
# 15. what the DRA LUT actually DOES -- two properties, asserted against the
#     real DLL rather than reasoned about from the port
# ---------------------------------------------------------------------------


def _gauss_hist(n: int, mu: float, sigma: float, count: int,
                seed: int) -> list[int]:
    rng = random.Random(seed)
    h = [0] * n
    for _ in range(count):
        h[min(n - 1, max(0, int(rng.gauss(mu, sigma))))] += 1
    return h


def check_lut_behaviour(pe: bytes) -> int:
    """Two facts about ``generateLut``'s output, both read off the real DLL.

    They matter because the shape of the DRA LUT -- not just its
    arithmetic -- is what an integration has to get right, and both of these
    were previously assumed rather than measured.
    """
    print("=== what the DRA LUT does to pixels (real DLL, shipped params) ===")
    p = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    n = int(p["maxValue"]) + 1
    paper_min, paper_max = int(p["paperMin"]), int(p["paperMax"])
    bad = 0

    # --- (a) in-paper-range frames get the IDENTITY, exactly --------------
    # Not "approximately identity" and not "a gentle S": every one of the
    # 4096 entries equals its own index.  This is the property that makes
    # DRA a clamp rather than a stretch -- it has no branch that expands a
    # narrow range out to fill [paperMin, paperMax].
    print("  (a) effective range INSIDE [paperMin, paperMax] -> identity LUT")
    for mu, sigma, seed in ((1600, 60, 1), (1550, 90, 2), (1400, 40, 3),
                            (1750, 50, 4)):
        lum = _gauss_hist(n, mu, sigma, 40000, seed)
        lut, lo, hi = run_generate_lut(
            pe, p, n, n // int(p["binFactor"]), lum, None, None, 0)
        in_range = paper_min <= lo and hi <= paper_max
        ident = all(lut[i] == i for i in range(n))
        ok = (not in_range) or ident
        bad += not ok
        print(f"      hist~N({mu},{sigma})  eff=({lo},{hi})  "
              f"in-paper-range={in_range}  identity={ident}  "
              f"{'OK' if ok else 'FAIL'}")

    # --- (b) out-of-range frames are COMPRESSED toward 1550, never expanded
    print("  (b) effective range WIDER than the paper range -> compression")
    for mu, sigma, seed in ((2000, 900, 5), (1900, 1200, 6)):
        lum = _gauss_hist(n, mu, sigma, 60000, seed)
        lut, lo, hi = run_generate_lut(
            pe, p, n, n // int(p["binFactor"]), lum, None, None, 0)
        fp = int(p["highFixedPoint"])
        # the band the compression arm actually governs
        span = [i for i in range(fp + 1, min(hi, n))]
        shrinks = all(abs(lut[i] - fp) <= (i - fp) for i in span) if span else True
        pinned = lut[fp] == fp
        ok = shrinks and pinned
        bad += not ok
        print(f"      hist~N({mu},{sigma})  eff=({lo},{hi})  "
              f"LUT[{fp}]=={lut[fp]}  highs-pulled-in={shrinks}  "
              f"{'OK' if ok else 'FAIL'}")

    # --- (c) minSlope / maxSlope are DEAD in dra --------------------------
    # Their names promise slope limiting; generateLut (0x1022ab50) contains
    # no x87 instructions at all and keepMidPtLut (0x102290b0) reads only
    # params +0x00/+0x02/+0x04/+0x06/+0x08/+0x28 and the six .ttc blocks --
    # never +0x0c or +0x10.  Rather than rest on that (a negative claim from
    # static reading is exactly the kind this project distrusts), sweep both
    # parameters across their whole valid range on a case where dra is
    # genuinely working, and require the real DLL's LUT to be byte-identical.
    print("  (c) minSlope/maxSlope perturbation -> byte-identical LUT")
    lum = _gauss_hist(n, 2000, 900, 60000, 7)
    edge = _gauss_hist(n, 1900, 800, 60000, 8)
    ref = run_analyze_hist(pe, p, lum, edge, None, n)
    non_trivial = any(ref[i] != i for i in range(n))
    if not non_trivial:
        print("      SKIPPED: baseline LUT is the identity, so this sweep "
              "would be vacuous")
        bad += 1
    else:
        for ms, xs in ((0.0, 1.5), (0.8, 100.0), (0.0, 0.0), (1.5, 1.5),
                       (0.01, 99.0), (1.4, 1.5)):
            q = copy.deepcopy(p)
            q.values["minSlope"] = dra._f32(ms)
            q.values["maxSlope"] = dra._f32(xs)
            got = run_analyze_hist(pe, q, lum, edge, None, n)
            ok = got == ref
            bad += not ok
            print(f"      minSlope={ms:<5} maxSlope={xs:<6} identical={ok}  "
                  f"{'OK' if ok else 'FAIL'}")
    print(f"  {'all OK' if not bad else f'{bad} FAILED'}")
    return bad


# ---------------------------------------------------------------------------


def main() -> int:
    if len(sys.argv) > 1:
        dll = Path(sys.argv[1])
    elif DEFAULT_DLL.exists():
        dll = DEFAULT_DLL
    else:
        dll = FALLBACK_DLL
    if not dll.exists():
        print(f"DLL not found: {dll}\n"
              f"Extract it with: python3 tools/re/reachability.py extract")
        return 2
    pe = dll.read_bytes()
    print(f"DLL {dll}")
    print(f"  ENTRY_POINTS={dra.DRA_ENTRY_POINTS_PORTED} "
          f"LIGHTING_BRANCH={dra.DRA_LIGHTING_BRANCH_PORTED} "
          f"REBIN={dra.DRA_REBIN_PORTED} "
          f"LUM_HIST={dra.DRA_LUM_HISTOGRAM_PORTED} "
          f"COMPOSE={dra.DRA_COMPOSE_TONE_PORTED} "
          f"CUM_BOUNDS={dra.DRA_CUM_BOUNDS_PORTED}\n")

    bad = 0
    bad += check_lighting(pe)
    print()
    bad += check_rebin(pe)
    print()
    bad += check_lum_histogram(pe)
    print()
    bad += check_compose(pe)
    print()
    bad += check_cum_bounds(pe)
    print()
    bad += check_eff_bounds(pe)
    print()
    bad += check_ttc_slopes(pe)
    print()
    bad += check_keep_midpt_lut(pe)
    print()
    bad += check_validate_params(pe)
    print()
    bad += check_alloc(pe)
    print()
    bad += check_generate_lut(pe)
    print()
    bad += check_analyze_image(pe)
    print()
    bad += check_analyze_hist(pe)
    print()
    bad += check_parse_dpi(pe)
    print()
    bad += check_lut_behaviour(pe)
    print()
    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
