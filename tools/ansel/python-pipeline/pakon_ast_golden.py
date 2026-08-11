#!/usr/bin/env python3
"""Golden ``AnsAstCapabilityImpl::analyze`` vs PakonIMAu.dll — bit-exact.

Phase 2e's proof obligation: not "the port agrees with the pseudocode", but
"every dword the real ``0x10227160`` writes is the dword ``pakon_ast`` writes".

WHAT RUNS FOR REAL
==================
Essentially all of it.  ``ast`` turns out to be almost stub-free — the OK-status
global ``[0x106b5bd4]`` is ``0`` in the shipped image, so every refcount guard
in the function takes its null branch and no smart-pointer machinery is needed.
The only two hooks are the CRT allocator pair::

    0x104ffd53  operator new        (0x104ffd78 operator new[] jmps here)
    0x104ffe3e  operator delete[]   -- recorded, made a no-op so the freed
                                       curve table stays readable

Everything else executes: ``0x10227160`` itself, the parameter validator
``0x10225bb0``, ``AnsAstCapabilityImpl::allocateMemory`` ``0x10226ef0``, the
curve-table holder ``0x10226380``, MSVC ``_ftol`` ``0x104ffe44``, and every x87
instruction of the slope loop, the ``fchs`` abs-value sequence and the response
curve.  ``0x10227160`` is entered at the Impl level with the four-argument list
its Cap wrapper ``0x1012f3f0`` builds — ``(&status, holder, capability,
short* toneLut)`` — so the ``cap+0xe`` teardown branch is exercised too.

THE THREE ARRAYS COMPARED
=========================
======  ================  =========================================
 work    ``Impl+0x38``     the int32 slope indices, ``4n`` bytes
 curve   scratch           the float response table, ``4n`` bytes --
                           ``delete[]``-d at ``0x10227553``, so it is
                           snapshotted live at ``0x1022751c`` where
                           ``esi`` still holds it
 out     ``Impl+0x3c``     the float output LUT, ``4n`` bytes
======  ================  =========================================

``curve`` is the one that actually tests the floating point: it is ``n``
independent divisions and multiply-adds, one per index, and it is where a
wrong rounding model shows up first.

THE X87 CONTROL WORD IS LOAD-BEARING
====================================
Unicorn starts with ``FPCW == 0x0000``.  ``PC`` (bits 8-9) of ``0`` is **24-bit
single precision**, which is not what any Windows process runs and produces
visibly wrong intermediate values.  Windows initialises the x87 CW to
``0x027f`` — 53-bit precision, round-to-nearest-even — which is exactly the
precision of a Python ``float``, and that is why ``pakon_ast`` can compute in
doubles at all.  This harness sets ``0x027f`` and then **re-runs every case at
``0x037f`` (64-bit extended)** and reports whether any output moves, so the
choice is measured rather than assumed.

NEGATIVE CONTROLS
=================
A comparison that cannot fail proves nothing, so ``--mutate`` re-runs the
matrix against four deliberately-wrong variants of the port and requires each
to be caught:

    truncate -> round-half-even    the ``_ftol`` / ``+0.5`` interpretation
    edge replication -> mirroring  step 2
    float32 store -> full double   the ``fstp dword`` narrowing
    clamp before abs -> after      the ``fchs`` sequence's position

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_ast_golden.py [--mutate] [dll]``

The DLL is not in the repo.  Extract it with
``python3 tools/re/reachability.py extract`` (default ``/tmp/pakon_re``).
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
    UC_X86_REG_EDI,
    UC_X86_REG_EIP,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
    UC_X86_REG_FPCW,
)

import pakon_ast as ast

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x02000000   # 0x0d000000..0x0f000000 -- must stay below IMAGE_BASE
RET_MAGIC = 0x00110000

#: Windows' x87 control word: round-to-nearest-even, 53-bit precision control.
FPCW_WINDOWS = 0x027F
#: 64-bit extended precision -- the sensitivity check, not the model.
FPCW_EXTENDED = 0x037F

#: The curve-table snapshot point: the first instruction after the response
#: curve loop, where esi still holds the scratch table and edi the work array.
VA_CURVE_SNAPSHOT = 0x1022751C

DEFAULT_DLL = Path("/tmp/pakon_re/PakonIMAu.dll")


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    """Minimal PakonIMAu.dll emulator — PE load, bump heap, flat SEH head."""

    def __init__(self, pe: bytes, fpcw: int = FPCW_WINDOWS):
        self.pe = pe
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self._load()
        uc.mem_map(0, 0x1000)              # flat FS base -> fs:[0] SEH head
        uc.mem_map(STACK, STACK_SZ)
        uc.mem_map(HEAP, HEAP_SZ)
        uc.mem_map(RET_MAGIC & ~0xFFF, 0x1000)
        uc.mem_write(RET_MAGIC, b"\xC3")
        uc.mem_write(0, struct.pack("<I", 0xFFFFFFFF))
        self.brk = HEAP + 0x1000
        self.faults: list[str] = []
        self.frees: list[int] = []
        uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)

        # The x87 control word. Unicorn's default of 0 is 24-bit precision.
        uc.reg_write(UC_X86_REG_FPCW, fpcw)
        self.fpcw = fpcw

        # operator new -- 0x104ffd78 (operator new[]) is a jmp onto this.
        self.hook(ast.OP_NEW, lambda e, a: (e.alloc(max(e.r32(a), 4)), 0))

        def _free(e: "Emu", a: int):
            e.frees.append(e.r32(a))
            return None, 0
        self.hook(ast.OP_DELETE_ARR, _free)

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
        # Poison, not zero: an under-filled output array must not look right
        # by accident.
        self.uc.mem_write(p, b"\xCD" * size)
        if fill:
            self.uc.mem_write(p, fill)
        return p

    def wu32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", int(v) & 0xFFFFFFFF))

    def wu16(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<H", int(v) & 0xFFFF))

    def wu8(self, a: int, v: int) -> None:
        self.uc.mem_write(a, bytes([int(v) & 0xFF]))

    def r32(self, a: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def blob(self, a: int, n: int) -> bytes:
        return bytes(self.uc.mem_read(a, n))

    # -- hooks -------------------------------------------------------------
    def hook(self, va: int, fn) -> None:
        """Replace the function at ``va``: run ``fn``, then return to caller."""
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
        """Observe at ``va`` without intercepting — execution continues."""
        self.uc.hook_add(UC_HOOK_CODE,
                         lambda uc, a, s, u: fn(self, uc), begin=va, end=va)

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"bad mem access={access} addr={address:#x} eip="
            f"{uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

    # -- calling -----------------------------------------------------------
    def call(self, va: int, args=(), ecx: int | None = None,
             esi: int | None = None) -> int:
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
        if esi is not None:
            uc.reg_write(UC_X86_REG_ESI, esi)
        self.faults = []
        try:
            uc.emu_start(va, RET_MAGIC, timeout=0, count=500_000_000)
        except UcError as ex:
            raise RuntimeError(
                f"emu {va:#x} eip={uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
                + ("; " + "; ".join(self.faults[:2]) if self.faults else "")
            ) from ex
        if self.faults:
            raise RuntimeError(f"emu {va:#x} faults: {self.faults[:2]}")
        return uc.reg_read(UC_X86_REG_EAX)


# ---------------------------------------------------------------------------
# one emulated analyze
# ---------------------------------------------------------------------------


class AstRun:
    """Build an ``AnsAstCapabilityImpl``, run the real analyze, read it back."""

    def __init__(self, pe: bytes, params: ast.AstParams, tone_lut,
                 *, keep_work: bool = True, fpcw: int = FPCW_WINDOWS):
        self.emu = Emu(pe, fpcw=fpcw)
        e = self.emu
        self.params = params
        self.keep_work = keep_work
        self.curve_ptr = 0
        self.work_ptr_live = 0

        # The Impl. 0x10227160 reads +0x10..+0x2c (params) and +0x30..+0x3c
        # (the working set); it never touches the vtable at +0.
        self.impl = e.alloc(0x60, fill=b"\x00" * 0x60)
        e.uc.mem_write(self.impl + ast.IMPL_PARAMS, params.to_bytes())
        for off in (ast.IMPL_LENGTH, ast.IMPL_PADDED, ast.IMPL_WORK,
                    ast.IMPL_OUT):
            e.wu32(self.impl + off, 0)

        # The capability: only byte +0xe is read (0x10227535).
        self.cap = e.alloc(0x40, fill=b"\x00" * 0x40)
        e.wu8(self.cap + ast.CAP_KEEP_WORK_BYTE, 1 if keep_work else 0)

        # The tone LUT -- short*, read-only to this stage.
        if tone_lut is None:
            self.tone = 0
            self.n = 0
        else:
            self.n = params.max_value + 1
            data = b"".join(struct.pack("<h", int(v)) for v in tone_lut[:self.n])
            self.tone = e.alloc(len(data) + 0x40, fill=data)

        def snap(em: Emu, uc):
            self.curve_ptr = uc.reg_read(UC_X86_REG_ESI)
            self.work_ptr_live = uc.reg_read(UC_X86_REG_EDI)
        e.watch(VA_CURVE_SNAPSHOT, snap)

    def run(self) -> dict:
        e = self.emu
        sret = e.alloc(0x10, fill=b"\x00" * 0x10)
        # The four-argument list 0x1012f3f0 builds for the Impl:
        # (&status, holder, capability, short* toneLut). holder is null --
        # analyze only ever refcount-releases it, never reads through it.
        holder = 0
        e.call(ast.AST_ANALYZE_IMPL,
               [sret, holder, self.cap, self.tone], ecx=self.impl)
        n = e.r32(self.impl + ast.IMPL_LENGTH)
        out_ptr = e.r32(self.impl + ast.IMPL_OUT)
        work_ptr = e.r32(self.impl + ast.IMPL_WORK)
        return {
            "status": e.r32(sret),
            "length": n,
            "out": e.blob(out_ptr, 4 * n) if out_ptr and n else b"",
            "work_ptr": work_ptr,
            "work": (e.blob(self.work_ptr_live, 4 * n)
                     if self.work_ptr_live and n else b""),
            "curve": (e.blob(self.curve_ptr, 4 * n)
                      if self.curve_ptr and n else b""),
            "frees": list(e.frees),
        }


# ---------------------------------------------------------------------------
# the case matrix
# ---------------------------------------------------------------------------


def _params(**kw) -> ast.AstParams:
    p = ast.AstParams.defaults()
    for k, v in kw.items():
        setattr(p, k, v)
    return p


PARAM_CASES = {
    "shipped defaults": ast.AstParams.defaults(),
    # A different everything: smaller LUT, half knee, delta 3, factor 100.
    "n=1024 K=0.5 d=3 f=100": _params(
        max_value=1023, nominal_slope=0.5, slope_delta=3, min_slope=-4.0,
        max_slope=4.0, low_slope_response=0.25, high_slope_response=0.75,
        slope_factor=100.0),
    # delta at its minimum, knee above 1, responses at both bounds.
    "K=2 d=1 low=1 high=0": _params(
        nominal_slope=2.0, slope_delta=1, low_slope_response=1.0,
        high_slope_response=0.0),
    # nominalSlope == 0 -- the validator accepts it, and it makes curve[0]
    # a 0.0/0.0 division. This is the case Python would raise on.
    "K=0 (0/0 at j==0)": _params(nominal_slope=0.0),
    # delta at its maximum, factor 1 -- almost every index collapses to 0..8.
    "d=100 f=1": _params(slope_delta=100, slope_factor=1.0),
    # A small LUT: n=256, and the field-6 product right at its bound.
    "n=256 f=30": _params(max_value=255, slope_delta=10, slope_factor=30.0),
}


def tone_cases(n: int) -> dict:
    """Input LUTs chosen to reach every branch of the slope loop."""
    rnd = random.Random(0x105 * 0x1059EE4C)
    ramp = list(range(n))
    return {
        # s == 1.0 exactly -> lands on the knee.
        "identity ramp": ramp,
        # s == 0 -> index 0, the low branch of the curve at its extreme.
        "flat": [1000] * n,
        # s < 0 everywhere -> the fchs path on every index.
        "descending": [n - 1 - i for i in range(n)],
        # s == 4 -> well into the roll-off, no clamping.
        "4x steep": [min(32767, 4 * i) for i in range(n)],
        # s == 40 -> clamped to maxSlope on every index.
        "40x (clamps high)": [min(32767, 40 * i) for i in range(n)],
        # s == -40 -> clamped to minSlope, then abs.
        "-40x (clamps low)": [max(-32768, -40 * i) for i in range(n)],
        # Alternating -> the sign flips index to index, exercising both
        # clamps and the abs in the same run.
        "sawtooth": [(-1) ** i * (i % 977) * 33 for i in range(n)],
        # An S-curve: a plausible real tone LUT, slope varying smoothly
        # through the knee, so most curve indices are hit with fractions.
        "s-curve": [
            int(32767 * (3 * (i / max(n - 1, 1)) ** 2
                         - 2 * (i / max(n - 1, 1)) ** 3) - 16384)
            for i in range(n)],
        # Noise: the real precision test -- ~n distinct non-round slopes.
        "random": [rnd.randint(-32768, 32767) for _ in range(n)],
        # Every entry the same extreme, then a single step: edge replication
        # has to copy the right two values outward.
        "single step": [0] * (n // 2) + [32767] * (n - n // 2),
    }


# ---------------------------------------------------------------------------
# port-side mutations (negative controls)
# ---------------------------------------------------------------------------


def mutated_analyze(kind: str):
    """Return a deliberately wrong ``ast_analyze``.

    ``abs-before-clamp`` is deliberately **absent** from this list.  It was
    tried and is not a valid control: the validator's field-4 test forces
    ``maxSlope == -minSlope``, and for a symmetric interval
    ``abs(clamp(s)) == clamp(abs(s))`` identically, so the two orderings are
    indistinguishable by construction rather than by a weak test matrix.
    ``no-abs`` replaces it as the mutation that actually probes that region.
    """

    def run(params: ast.AstParams, tone_lut, *, keep_work=True):
        n = params.max_value + 1
        delta = params.slope_delta
        padded = [int(v) for v in tone_lut[:n]]
        two_delta = float(2 * delta)
        lo = ast._f32(params.min_slope)
        hi = ast._f32(params.max_slope)
        fac = ast._f32(params.slope_factor)
        K = ast._f32(params.nominal_slope)
        lr = ast._f32(params.low_slope_response)
        hr = ast._f32(params.high_slope_response)

        work = [0] * n
        for i in range(delta, n - delta):
            s = (padded[i + delta] - padded[i - delta]) / two_delta
            if s < lo:
                s = lo
            elif s > hi:
                s = hi
            if kind != "no-abs":
                s = abs(s)
            v = s * fac + 0.5
            work[i] = (round(v - 0.5) if kind == "round-half-even"
                       else int(v))
        if kind == "mirror-pad":
            for c in range(delta):
                work[c] = work[2 * delta - c]
                work[n - 1 - c] = work[n - 1 - 2 * delta + c]
        else:
            first, last = work[delta], work[n - delta - 1]
            for c in range(delta):
                work[c] = first
                work[n - 1 - c] = last

        curve = [0.0] * n
        for j in range(n):
            x = ast._x87_div(float(j), fac)
            if x < K:
                v = (x - K) * lr + K
            else:
                v = ast._x87_div(K * x, (K - x) * hr + x)
            curve[j] = v if kind == "no-f32-store" else ast._f32(v)
        out = [curve[work[i]] for i in range(n)]
        return ast.AstResult(n, padded, work, out, curve)

    return run


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------


def _pack_f32(vals) -> bytes:
    return b"".join(struct.pack("<f", v) for v in vals)


def _pack_i32(vals) -> bytes:
    """Pack as raw dwords — ``Impl+0x38`` is compared byte-for-byte, and a
    mutated port may put values outside int32 there."""
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in vals)


def _first_diff(a: bytes, b: bytes) -> str:
    if len(a) != len(b):
        return f"length {len(a)} vs {len(b)}"
    for i in range(0, len(a), 4):
        if a[i:i + 4] != b[i:i + 4]:
            return (f"index {i // 4}: dll {a[i:i+4].hex()} "
                    f"port {b[i:i+4].hex()} "
                    f"({struct.unpack('<f', a[i:i+4])[0]!r} vs "
                    f"{struct.unpack('<f', b[i:i+4])[0]!r})")
    return "identical"


_DLL_CACHE: dict[tuple, dict] = {}


def dll_run(pe: bytes, key: str, params: ast.AstParams, lut,
            *, keep_work: bool = True, fpcw: int = FPCW_WINDOWS) -> dict:
    """Emulate one analyze, memoised — the DLL side does not vary per port."""
    ck = (key, keep_work, fpcw)
    if ck not in _DLL_CACHE:
        _DLL_CACHE[ck] = AstRun(pe, params, lut, keep_work=keep_work,
                                fpcw=fpcw).run()
    return _DLL_CACHE[ck]


def _f32_exact(vals) -> int | None:
    """Index of the first value that is not exactly ``float32``-representable.

    Needed because ``_pack_f32`` narrows on the way into the comparison, so a
    port that skipped the DLL's ``fstp dword`` would still produce identical
    *bytes* (rounding to float32 twice is rounding to float32 once).  The
    difference is only visible in what the port hands its own callers, so it
    is checked here as an invariant rather than as a diff.
    """
    for i, v in enumerate(vals):
        if v != v:                       # NaN: sign is checked by the diff
            continue
        if v != ast._f32(v):
            return i
    return None


def compare(pe: bytes, label: str, params: ast.AstParams, lut,
            *, key: str, analyze=None, keep_work: bool = True,
            fpcw: int = FPCW_WINDOWS) -> list[str]:
    """One case: run the DLL and the port, diff all three arrays."""
    fn = analyze if analyze is not None else ast.ast_analyze
    dll = dll_run(pe, key, params, lut, keep_work=keep_work, fpcw=fpcw)
    port = fn(params, lut, keep_work=keep_work)

    fails = []
    if dll["length"] != port.length:
        fails.append(f"{label}: Impl+0x30 {dll['length']} != {port.length}")
    d = _first_diff(dll["work"], _pack_i32(port.work if port.work
                                          else [0] * port.length))
    if d != "identical":
        fails.append(f"{label}: work[] {d}")
    d = _first_diff(dll["curve"], _pack_f32(port.curve))
    if d != "identical":
        fails.append(f"{label}: curve[] {d}")
    d = _first_diff(dll["out"], _pack_f32(port.out))
    if d != "identical":
        fails.append(f"{label}: out[] {d}")
    for what, vals in (("curve", port.curve), ("out", port.out)):
        i = _f32_exact(vals)
        if i is not None:
            fails.append(f"{label}: {what}[{i}] == {vals[i]!r} is not a "
                         f"float32 value; the DLL stores this array with "
                         f"fstp dword")
    return fails


VALIDATOR_CASES = [
    ("shipped defaults", ast.AstParams.defaults(), 0),
    ("maxValue 0", _params(max_value=0), 1),
    ("maxValue -1", _params(max_value=-1), 1),
    ("maxValue 1", _params(max_value=1, slope_factor=0.0), 0),
    ("nominalSlope -0.001", _params(nominal_slope=-0.001), 2),
    ("nominalSlope > maxValue", _params(nominal_slope=5000.0), 2),
    ("nominalSlope == maxValue", _params(nominal_slope=4095.0), 0),
    ("slopeDelta 0", _params(slope_delta=0), 3),
    ("slopeDelta 101", _params(slope_delta=101), 3),
    ("slopeDelta 100", _params(slope_delta=100), 0),
    ("minSlope 0", _params(min_slope=0.0, max_slope=0.0), 4),
    ("minSlope +8", _params(min_slope=8.0), 4),
    ("maxSlope != -minSlope", _params(max_slope=7.0), 4),
    ("lowResponse -0.1", _params(low_slope_response=-0.1), 5),
    ("lowResponse 1.1", _params(low_slope_response=1.1), 5),
    ("lowResponse 1.0", _params(low_slope_response=1.0), 0),
    ("highResponse -0.1", _params(high_slope_response=-0.1), 6),
    ("highResponse 1.1", _params(high_slope_response=1.1), 6),
    ("slopeFactor -1", _params(slope_factor=-1.0), 6),
    ("factor*maxSlope > maxValue", _params(slope_factor=600.0), 6),
    ("factor*maxSlope == maxValue", _params(slope_factor=511.875), 0),
]


def run_validator(pe: bytes) -> list[str]:
    """Call the real ``0x10225bb0`` — ``ecx`` = params, ``esi`` = out code."""
    fails = []
    for label, p, expect in VALIDATOR_CASES:
        emu = Emu(pe)
        pblk = emu.alloc(0x40, fill=p.to_bytes())
        outp = emu.alloc(0x10, fill=b"\x00" * 0x10)
        rc = emu.call(ast.AST_VALIDATE, [], ecx=pblk, esi=outp)
        rc = struct.unpack("<i", struct.pack("<I", rc & 0xFFFFFFFF))[0]
        dll_code = emu.r32(outp) if rc != 0 else 0
        port_code = ast.validate_params(p)
        if dll_code != port_code:
            fails.append(f"validator {label}: dll #{dll_code} "
                         f"port #{port_code}")
        elif dll_code != expect:
            fails.append(f"validator {label}: both said #{dll_code}, "
                         f"case expected #{expect}")
        if (rc != 0) != (dll_code != 0):
            fails.append(f"validator {label}: eax {rc} disagrees with "
                         f"esi code #{dll_code}")
    return fails


def run_null_tone(pe: bytes) -> list[str]:
    """``0x102271e8`` — a null tone LUT is a no-op, not an error."""
    p = ast.AstParams.defaults()
    dll = AstRun(pe, p, None).run()
    port = ast.ast_analyze(p, None)
    fails = []
    if port is not None:
        fails.append("null tone: port did not take the early-out")
    if dll["status"] != 0:
        fails.append(f"null tone: dll status {dll['status']:#x}, expected OK")
    if dll["length"] != 0:
        fails.append(f"null tone: Impl+0x30 == {dll['length']}, expected 0")
    return fails


def run_keep_work(pe: bytes) -> list[str]:
    """``cap+0xe`` clear -> the int32 work array is freed and ``+0x38`` nulled."""
    p = ast.AstParams.defaults()
    lut = list(range(p.max_value + 1))
    fails = []
    for keep in (True, False):
        dll = AstRun(pe, p, lut, keep_work=keep).run()
        port = ast.ast_analyze(p, lut, keep_work=keep)
        kept = dll["work_ptr"] != 0
        if kept != keep:
            fails.append(f"cap+0xe={int(keep)}: Impl+0x38 "
                         f"{'kept' if kept else 'nulled'}, expected the other")
        if (port.work is None) == keep:
            fails.append(f"cap+0xe={int(keep)}: port work retention disagrees")
        if not keep and dll["work_ptr"] != 0:
            fails.append("cap+0xe=0: work pointer not cleared")
    return fails


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    do_mutate = "--mutate" in argv
    dll_path = Path(args[0]) if args else DEFAULT_DLL
    if not dll_path.exists():
        print(f"DLL not found at {dll_path}.\n"
              f"Extract it with: python3 tools/re/reachability.py extract")
        return 2
    pe = dll_path.read_bytes()

    print(f"golden ast: {ast.AST_ANALYZE_IMPL:#x} vs pakon_ast, "
          f"{dll_path}")
    print(f"  FPCW {FPCW_WINDOWS:#06x} (53-bit, Windows default); "
          f"unicorn's own default is 0x0000 == 24-bit\n")

    fails: list[str] = []
    checked = 0

    print("  -- 0x10225bb0 parameter validator " + "-" * 38)
    v = run_validator(pe)
    checked += len(VALIDATOR_CASES)
    fails += v
    print(f"     {len(VALIDATOR_CASES)} cases, "
          f"{'OK' if not v else str(len(v)) + ' FAILED'}")

    print("  -- 0x102271e8 null tone LUT early-out " + "-" * 33)
    n0 = run_null_tone(pe)
    checked += 1
    fails += n0
    print(f"     {'OK' if not n0 else 'FAILED'}")

    print("  -- 0x10227532 cap+0xe work retention " + "-" * 34)
    kw = run_keep_work(pe)
    checked += 2
    fails += kw
    print(f"     {'OK' if not kw else 'FAILED'}")

    print("  -- 0x10227160 analyze, work[] / curve[] / out[] " + "-" * 23)
    for pname, params in PARAM_CASES.items():
        n = params.max_value + 1
        bad = []
        for tname, lut in tone_cases(n).items():
            f = compare(pe, f"{pname} / {tname}", params, lut,
                        key=f"{pname}|{tname}")
            bad += f
            checked += 1
        fails += bad
        print(f"     {pname:<26} n={n:<5} "
              f"{len(tone_cases(n))} LUTs  "
              f"{'OK' if not bad else str(len(bad)) + ' FAILED'}")
        for f in bad[:3]:
            print(f"        {f}")

    print("  -- FPCW sensitivity " + "-" * 51)
    p = ast.AstParams.defaults()
    luts = tone_cases(p.max_value + 1)
    base = {t: AstRun(pe, p, l, fpcw=FPCW_WINDOWS).run() for t, l in luts.items()}

    def moved_at(cw: int) -> int:
        n = 0
        for t, lut in luts.items():
            r = AstRun(pe, p, lut, fpcw=cw).run()
            a = base[t]
            if (r["curve"], r["out"], r["work"]) != (a["curve"], a["out"],
                                                    a["work"]):
                n += 1
        return n

    ext = moved_at(FPCW_EXTENDED)
    print(f"     0x037f (64-bit extended): {ext}/{len(luts)} LUTs move — "
          f"53- and 64-bit agree here, so the double model is safe either way")
    # The control. If this does NOT move, the harness is not actually running
    # the x87 at the precision it thinks it is and the line above proves
    # nothing.
    single = moved_at(0x0000)
    print(f"     0x0000 (24-bit single, unicorn's default): "
          f"{single}/{len(luts)} LUTs move"
          + ("" if single else "   <-- CONTROL FAILED, FPCW is not taking"
                               " effect"))
    if not single:
        fails.append("FPCW control: 24-bit precision changed nothing, so the "
                     "precision-control comparison is not measuring anything")

    if do_mutate:
        print("  -- negative controls: each mutation MUST be caught " + "-" * 20)
        for kind in ("round-half-even", "mirror-pad", "no-f32-store",
                     "no-abs"):
            fn = mutated_analyze(kind)
            caught = total = 0
            where = []
            for pname, params in PARAM_CASES.items():
                for tname, lut in tone_cases(params.max_value + 1).items():
                    total += 1
                    if compare(pe, kind, params, lut, analyze=fn,
                               key=f"{pname}|{tname}"):
                        caught += 1
                        if len(where) < 1:
                            where.append(f"{pname} / {tname}")
            ok = caught > 0
            print(f"     {kind:<18} caught on {caught}/{total} cases  "
                  f"{'OK' if ok else 'NOT CAUGHT -- the test is blind here'}"
                  + (f"   (first: {where[0]})" if where else ""))
            if not ok:
                fails.append(f"negative control {kind} was not caught")

    print()
    if fails:
        print(f"FAIL — {len(fails)} mismatch(es) over {checked} checks")
        for f in fails[:20]:
            print(f"  {f}")
        return 1
    print(f"PASS — {checked} checks, every dword of work[], curve[] and "
          f"out[] bit-identical to the DLL")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
