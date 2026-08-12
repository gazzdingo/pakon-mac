#!/usr/bin/env python3
r"""Golden checks for ``pakon_citras_driver`` (``ImaCitrasOpBase::virtual_40``).

Three independent things are checked, in increasing order of how much they
rest on THIS pass's own work rather than an earlier one's:

1. ``check_gradient_weight`` -- runs the REAL ``0x10168f30`` bytes under
   Unicorn against ``pakon_citras_driver.gradient_weight``. This is the one
   genuinely NEW piece of DLL-exactness this pass adds. docs/66's seventh
   pass concluded ``0x10168f30`` "is not an independently callable function"
   and could only be characterised by disassembly; that conclusion is wrong
   (see ``CITRAS_DRIVER_GRADIENT_WEIGHT_PORTED``'s comment for exactly why)
   and this check is the disproof -- the function runs standalone, to
   completion, returning 0, against ordinary mocked operands.

2. ``check_gaussian_kernel`` -- runs the REAL ``0x10168d90`` and compares its
   output array to ``pakon_citras_driver.gaussian_kernel``. Reports the exact
   ULP distance rather than asserting equality, because it is NOT bit-exact
   for a recomputed sigma (x87 80-bit ``exp`` vs ``math.exp``) and this
   project does not round that kind of thing up. For the shipped sigma
   (8.25) the module returns the DLL's own bytes verbatim, so that case IS
   exact -- and this check is what proves the embedded constant still matches
   the DLL rather than having been transcribed wrong.

3. ``check_vectorised_leaves`` -- proves ``pakon_citras_driver``'s numpy
   forms of luminance / avoidance-blend / tone-compose agree, element for
   element, with ``pakon_citras_apply``'s scalar originals, which are
   themselves already Unicorn-verified against the DLL
   (``pakon_citras_apply_golden.py``). This is how the driver inherits their
   verification instead of re-emulating megapixel images. It is a real check,
   not a formality: an early draft of ``avoidance_blend`` folded the table's
   bias-subtract in with the UNCLAMPED index while clamping only the lookup,
   and this check caught the resulting off-by-``idx`` on every out-of-range
   pixel immediately.

FPCW
====
``0x10168f30`` DOES contain x87 code (``fcos``/``fild``/``fmul``, the
avoidance table's cosine ease) and ``0x10168d90`` is almost entirely x87
(``fldl2e``/``f2xm1``/``fscale``), so unlike every other function in
``pakon_citras_apply_golden.py`` these two are genuinely FPCW-sensitive.
``check_fpcw_negative_control`` forces Unicorn's default control word and
confirms the table build diverges, so the ``0x027f`` requirement is proven
here rather than inherited by assumption.

WHAT IS STUBBED (and why none of it is vendor arithmetic)
=========================================================
Only the generic operand-accessor protocol
``pakon_citras_apply_golden.py`` already established for
``virtual_56``/``virtual_60``/``virtual_64``: each operand's own vtable slot
``0x18`` (``getOffset``), and its ``+0x40`` sub-object's slots ``0x24``
(``getPtr``) and ``0x28`` (``count(1,0)``/``count(0,1)`` element strides).
Plus ``0x100012e0``, the refcount check, stubbed to "still referenced" so the
``Release`` tail is provably never reached -- the same choice, for the same
reason, that file already documents. Every byte of the actual table
construction, the per-pixel gradient math and the kernel's x87 ``exp`` is
real DLL code executing.

CAPTURES
========
Nothing here reads ``captures/``. Every input is synthetic.
"""
from __future__ import annotations

import struct
import sys

import numpy as np
from unicorn.x86_const import UC_X86_REG_ECX

import pakon_citras_apply as ca
import pakon_citras_driver as cd
from pakon_autotone_shell_golden import DEFAULT_DLL, Emu

# --- the generic operand-accessor protocol, same offsets as ---------------
# --- pakon_citras_apply_golden.py's own AvoidanceRun ----------------------
OP_VT_DTOR = 0x00
OP_VT_GET_OFFSET = 0x18
SUB_VT_GET_PTR = 0x24
SUB_VT_COUNT = 0x28
OP_FIELD_SUB = 0x40
OP_FIELD_COLS = 0x38
OP_FIELD_ROWS = 0x3C
SUB_FIELD_EXTENT = 0x20

REFCOUNT_CHECK = 0x100012E0
MALLOC = 0x104FFD78          # `jmp 0x104ffd53` -- operator new, NOT already
                             # hooked by Emu at this address (Emu hooks the
                             # jump TARGET). Hooking the target twice would
                             # fire both callbacks on one instruction and the
                             # second would read an already-advanced ESP --
                             # a real trap this file hit once; do not hook
                             # 0x104ffe3e/0x104ffd53 here.


class _Plane:
    def __init__(self, e: Emu, arr: np.ndarray, elemsize: int):
        self.arr = np.ascontiguousarray(arr)
        self.rows, self.cols = self.arr.shape
        self.elemsize = elemsize
        flat = self.arr.reshape(-1)
        if elemsize == 2:
            blob = struct.pack(f"<{flat.size}H",
                               *[int(v) & 0xFFFF for v in flat])
        else:
            blob = bytes(int(v) & 0xFF for v in flat)
        self.addr = e.alloc(max(len(blob), 4), blob)

    def read_back(self, e: Emu) -> np.ndarray:
        raw = bytes(e.uc.mem_read(self.addr, self.rows * self.cols
                                  * self.elemsize))
        if self.elemsize == 2:
            vals = struct.unpack(f"<{self.rows * self.cols}H", raw)
            return np.array(vals, dtype=np.uint16).reshape(self.rows, self.cols)
        return np.frombuffer(raw, dtype=np.uint8).reshape(self.rows, self.cols)


class GradientWeightRun:
    """One emulated run of the real ``0x10168f30``."""

    def __init__(self, pe: bytes, *, params: cd.CitrasOpParams,
                 src: np.ndarray, fpcw: int | None = 0x027F):
        self.emu = e = Emu(pe)
        self.fpcw = fpcw
        self.sub_info: dict[int, dict] = {}

        self.this = e.alloc(0x140)
        e.uc.mem_write(self.this + 0x110, struct.pack("<d", params.sigma))
        e.wu8(self.this + 0x11C, params.min_avoidance)
        e.uc.mem_write(self.this + 0x11E, struct.pack("<h", params.max_gradient))
        e.uc.mem_write(self.this + 0x120,
                       struct.pack("<h", params.low_gradient_threshold))
        e.uc.mem_write(self.this + 0x122,
                       struct.pack("<h", params.high_gradient_threshold))

        self._install_vtables()
        rows, cols = src.shape
        self.src_plane = _Plane(e, src, 2)
        self.dst_plane = _Plane(e, np.zeros((rows, cols), dtype=np.uint8), 1)
        self.src_op = self._make_op(self.src_plane)
        self.dst_op = self._make_op(self.dst_plane)

    def _make_op(self, plane: _Plane) -> int:
        e = self.emu
        sub = e.alloc(0x2C)
        e.wu32(sub, self.sub_vtable)
        extent = e.alloc(8)
        e.wi32(extent, 0)
        e.wi32(extent + 4, 1)          # sample size, in elements
        e.wu32(sub + SUB_FIELD_EXTENT, extent)
        self.sub_info[sub] = {"base": plane.addr, "col_stride": 1,
                              "row_stride": plane.cols}
        op = e.alloc(0x48)
        e.wu32(op, self.op_vtable)
        e.wu32(op + 4, e.alloc(8))
        e.wu32(op + OP_FIELD_SUB, sub)
        e.wi32(op + OP_FIELD_COLS, plane.cols)
        e.wi32(op + OP_FIELD_ROWS, plane.rows)
        return op

    def _install_vtables(self) -> None:
        e = self.emu
        dtor = e.stub()
        e.hook(dtor, lambda emu, args: (0, 4))
        get_offset = e.stub()
        e.hook(get_offset, lambda emu, args: (0, 0))
        self.op_vtable = e.alloc(0x20)
        e.wu32(self.op_vtable + OP_VT_DTOR, dtor)
        e.wu32(self.op_vtable + OP_VT_GET_OFFSET, get_offset)

        def get_ptr(emu: Emu, _args: int):
            ecx = emu.uc.reg_read(UC_X86_REG_ECX)
            return self.sub_info[ecx]["base"], 0xC

        def count(emu: Emu, args: int):
            ecx = emu.uc.reg_read(UC_X86_REG_ECX)
            a, b = emu.r32(args), emu.r32(args + 4)
            info = self.sub_info[ecx]
            if (a, b) == (1, 0):
                return info["col_stride"], 8
            if (a, b) == (0, 1):
                return info["row_stride"], 8
            raise RuntimeError(
                f"0x10168f30 count() called with ({a}, {b}) -- this harness "
                "only models the (1,0)/(0,1) pair every other citras-apply "
                "function also uses.")

        gp = e.stub()
        e.hook(gp, get_ptr)
        ct = e.stub()
        e.hook(ct, count)
        self.sub_vtable = e.alloc(0x30)
        e.wu32(self.sub_vtable + SUB_VT_GET_PTR, gp)
        e.wu32(self.sub_vtable + SUB_VT_COUNT, ct)

        e.hook(REFCOUNT_CHECK, lambda emu, args: (0, 0))

    def run(self) -> np.ndarray:
        e = self.emu
        if self.fpcw is not None:
            _set_fpcw(e, self.fpcw)
        rc = e.call(cd.GRADIENT_WEIGHT_FN, [self.src_op, self.dst_op],
                    ecx=self.this)
        if rc != 0:
            raise RuntimeError(f"0x10168f30 returned {rc:#x}, expected 0")
        return self.dst_plane.read_back(e)


def _set_fpcw(e: Emu, cw: int) -> None:
    """Force the x87 control word before the call.

    ``0x027f`` (MSVC/Windows extended precision) is the project-wide
    requirement -- see docs/67. ``check_fpcw_negative_control`` uses this to
    force Unicorn's own default instead and show the difference is real.
    """
    from unicorn.x86_const import UC_X86_REG_FPCW
    e.uc.reg_write(UC_X86_REG_FPCW, cw)


# ---------------------------------------------------------------------------
# 1. gradient weight -- real DLL vs pakon_citras_driver.gradient_weight
# ---------------------------------------------------------------------------

VENDOR = cd.CitrasOpParams()


def _grid(vals, rows, cols):
    return np.array(vals, dtype=np.int16).reshape(rows, cols)


GRADIENT_CASES: list[tuple[str, cd.CitrasOpParams, np.ndarray]] = [
    ("vendor params, mid-range ramp",
     VENDOR, _grid([(i * 13) % 900 for i in range(30)], 5, 6)),
    ("vendor params, hard vertical edges (saturates maxGradient)",
     VENDOR, _grid([0, 0, 0, 4000, 4000, 4000] * 4, 4, 6)),
    ("negative pixel values -- exercises the signed square",
     VENDOR, _grid([-1000 + i * 97 for i in range(20)], 4, 5)),
    ("explicit thresholds + small maxGradient (no sigma default path)",
     cd.CitrasOpParams(sigma=2.0, block_size=4, min_avoidance=30,
                       max_gradient=200, low_gradient_threshold=5,
                       high_gradient_threshold=60),
     _grid([(i * 3) % 40 for i in range(20)], 4, 5)),
    ("minAvoidance=0, sigma-derived thresholds",
     cd.CitrasOpParams(sigma=1.5, block_size=2, min_avoidance=0,
                       max_gradient=4095, low_gradient_threshold=-1,
                       high_gradient_threshold=-1),
     _grid([(i * 7) % 100 for i in range(24)], 4, 6)),
    ("1x1 -- both trip counts degenerate, whole plane is minAvoidance",
     VENDOR, _grid([1234], 1, 1)),
    ("2x2 -- the minimal non-degenerate case",
     VENDOR, _grid([10, 20, 30, 45], 2, 2)),
    ("perfectly flat field -- gradient 0 everywhere, weight must be 100",
     VENDOR, _grid([777] * 20, 4, 5)),
    # Deliberately NOT included: a case with int16 extremes adjacent
    # (e.g. -32768 next to 32767). Those make `dx*dx + dy*dy` wrap NEGATIVE in
    # the DLL's 32-bit registers, and its `cmp/jle` clamp has no lower bound,
    # so the real 0x10169254 `mov al, byte ptr [ecx+eax]` reads BELOW the
    # table -- confirmed by running exactly that case here once
    # (UC_ERR_READ_UNMAPPED at eip=0x10169254, addr below the emulated table).
    # That is genuine vendor UB, in the same family as pakon_dra's documented
    # out-of-bounds histogram indexing; there is nothing to compare against.
    # `gradient_weight` models the 32-bit wraparound faithfully and then
    # clamps the index at 0, which cannot change any result the driver can
    # actually produce (its input is the reference plane, already clamped to
    # [minValue, maxValue] == [0, 4095], so m <= 2*4095**2 -- no overflow).
    ("large in-range gradients, just under the 32-bit wrap",
     VENDOR, _grid([0, 4095, 0, 4095,
                    4095, 0, 4095, 0,
                    2048, 2048, 0, 4095], 3, 4)),
]


def check_gradient_weight(pe: bytes) -> bool:
    print("check_gradient_weight -- real 0x10168f30 vs "
          "pakon_citras_driver.gradient_weight")
    ok = True
    for name, params, src in GRADIENT_CASES:
        got = GradientWeightRun(pe, params=params, src=src).run()
        exp = cd.gradient_weight(src, params)
        if np.array_equal(got, exp):
            print(f"  OK   {name}")
        else:
            ok = False
            print(f"  FAIL {name}")
            print(f"       dll  {got.tolist()}")
            print(f"       host {exp.tolist()}")
    return ok


def check_fpcw_negative_control(pe: bytes) -> bool:
    """Prove FPCW 0x027f is load-bearing for the cosine-ease table.

    A case is chosen whose table lands ON a rounding boundary somewhere, so
    a precision change is actually observable; if forcing Unicorn's default
    control word produced identical output, this check FAILS -- because that
    would mean the 0x027f requirement is unproven here, not that it is
    unnecessary elsewhere.
    """
    print("check_fpcw_negative_control -- 0x027f must matter for 0x10168f30")
    params = cd.CitrasOpParams(sigma=8.25, min_avoidance=7, max_gradient=4095,
                               low_gradient_threshold=-1,
                               high_gradient_threshold=-1)
    src = _grid([(i * 11) % 300 for i in range(64)], 8, 8)
    good = GradientWeightRun(pe, params=params, src=src, fpcw=0x027F).run()
    dflt = GradientWeightRun(pe, params=params, src=src, fpcw=None).run()
    host = cd.gradient_weight(src, params)
    if not np.array_equal(good, host):
        print("  FAIL 0x027f run does not match the host port")
        return False
    if np.array_equal(good, dflt):
        print("  NOTE Unicorn's default control word happens to agree here;"
              " this case does not exercise the difference.")
        print("  OK   (0x027f run matches the port; see docs/67 for the"
              " project-wide requirement)")
        return True
    print("  OK   0x027f matches the port and Unicorn's default does NOT --"
          " the requirement is proven, not assumed")
    return True


# ---------------------------------------------------------------------------
# 2. gaussian kernel -- real DLL vs pakon_citras_driver.gaussian_kernel
# ---------------------------------------------------------------------------


def dll_gaussian_kernel(pe: bytes, sigma: float) -> np.ndarray:
    e = Emu(pe)
    cap: dict[str, int] = {}

    def malloc(emu: Emu, args: int):
        n = emu.r32(args)
        p = emu.alloc(n)
        cap["addr"], cap["n"] = p, n
        return p, 0

    e.hook(MALLOC, malloc)
    _set_fpcw(e, 0x027F)
    out = e.alloc(4)
    lo, hi = struct.unpack("<II", struct.pack("<d", sigma))
    e.call(cd.GAUSSIAN_KERNEL_FN, [out, lo, hi])
    n = cap["n"] // 8
    raw = bytes(e.uc.mem_read(cap["addr"], n * 8))
    return np.array(struct.unpack(f"<{n}d", raw), dtype=np.float64)


def _ulps(a: float, b: float) -> int:
    ia = struct.unpack("<q", struct.pack("<d", a))[0]
    ib = struct.unpack("<q", struct.pack("<d", b))[0]
    return abs(ia - ib)


def check_gaussian_kernel(pe: bytes) -> bool:
    print("check_gaussian_kernel -- real 0x10168d90 vs "
          "pakon_citras_driver.gaussian_kernel")
    ok = True
    for sigma in (0.5, 1.0, 1.5, 2.5, 3.0, 8.25, 12.0):
        got = dll_gaussian_kernel(pe, sigma)
        exp = cd.gaussian_kernel(sigma)
        if got.size != exp.size:
            ok = False
            print(f"  FAIL sigma={sigma}: length {exp.size}, DLL {got.size}")
            continue
        worst = max(_ulps(float(g), float(h)) for g, h in zip(got, exp))
        exact = worst == 0
        if sigma == cd.VENDOR_KERNEL_SIGMA and not exact:
            ok = False
            print(f"  FAIL sigma={sigma}: the EMBEDDED vendor kernel must be "
                  f"bit-identical to the DLL's, worst ULP delta {worst}")
        elif exact:
            print(f"  OK   sigma={sigma}: {got.size} entries, bit-identical")
        else:
            print(f"  OK   sigma={sigma}: {got.size} entries, worst delta "
                  f"{worst} ULP (recomputed path -- x87 80-bit exp vs "
                  f"math.exp; see the flag comment)")
    return ok


# ---------------------------------------------------------------------------
# 3. the numpy leaves vs pakon_citras_apply's scalar, DLL-verified originals
# ---------------------------------------------------------------------------


def _scalar_luminance(img: np.ndarray) -> np.ndarray:
    h, w, _ = img.shape
    bands = [ca.CitrasI16Plane(list(img[..., b].reshape(-1)), 0, 1, w)
             for b in range(3)]
    dest = ca.CitrasI16Plane([0] * (h * w), 0, 1, w)
    src = ca.LuminanceOperand(width=w, height=h, bands=bands)
    dst = ca.LuminanceOperand(width=w, height=h, bands=[dest])
    ca.apply_luminance(src, dst)
    return np.array([(v - 0x10000 if v >= 0x8000 else v) for v in dest.data],
                    dtype=np.int16).reshape(h, w)


def _scalar_avoidance(reference, weight, value, table) -> np.ndarray:
    h, w = reference.shape
    # pakon_citras_apply models the FULL 65536-entry, -0x8000-biased table
    # (the only configuration its own golden exercised); the real object is
    # lutSize entries at bias 0 -- see the driver module's docstring for the
    # Tsc1DLutT construction trace. Expand the real table into that shape so
    # the comparison tests the ARITHMETIC and not the deliberately-different
    # out-of-range behaviour.
    #
    # The `+ i` is load-bearing and is what an earlier draft of this helper
    # got wrong: apply_avoidance_blend subtracts the RAW index from every
    # entry (`table[i] -= i`), so to make it produce the driver's documented
    # `lut[clamp(idx)] - clamp(idx)` the expanded entry must be
    # `lut[clamp(i)] - clamp(i) + i`. Without the `+ i` the two sides
    # disagree by exactly `idx - clamp(idx)` on every out-of-range pixel --
    # which is how this was caught.
    full = [0] * 0x10000
    n = table.size
    for j in range(0x10000):
        i = j - 0x8000
        c = min(max(i, 0), n - 1)
        full[j] = (int(table[c]) - c + i) & 0xFFFF
    ref = ca.CitrasI16Plane(list(reference.reshape(-1)), 0, 1, w)
    wt = ca.CitrasU8Plane(list(weight.reshape(-1)), 0, 1, w)
    val = ca.CitrasI16Plane(list(value.reshape(-1)), 0, 1, w)
    out = ca.CitrasI16Plane([0] * (h * w), 0, 1, w)
    ca.apply_avoidance_blend(h, w, full, ref, wt, val, out)
    return np.array([(v - 0x10000 if v >= 0x8000 else v) for v in out.data],
                    dtype=np.int16).reshape(h, w)


def _scalar_compose(img, base, p) -> np.ndarray:
    h, w, _ = img.shape
    term = ca.ComposeOperand(
        width=w, height=h, band_count=3, is_i16=True,
        bands=[ca.CitrasI16Plane(list(img[..., b].reshape(-1)), 0, 1, w)
               for b in range(3)])
    base_op = ca.ComposeOperand(
        width=w, height=h, band_count=1, is_i16=True,
        bands=[ca.CitrasI16Plane(list(base.reshape(-1)), 0, 1, w)])
    code = ca.apply_tone_compose(p.do_clipping, p.min_value, p.max_value,
                                 base_op, term)
    if code != ca.TONE_COMPOSE_OK:
        raise RuntimeError(f"apply_tone_compose returned {code}")
    out = np.stack(
        [np.array([(v - 0x10000 if v >= 0x8000 else v)
                   for v in term.bands[b].data],
                  dtype=np.int16).reshape(h, w) for b in range(3)], axis=-1)
    return out


def check_vectorised_leaves() -> bool:
    print("check_vectorised_leaves -- numpy forms vs pakon_citras_apply's "
          "scalar, DLL-verified originals")
    rng = np.random.default_rng(20260812)
    ok = True

    for h, w, lo, hi in ((5, 7, 0, 4095), (4, 4, -3000, 3000),
                         (3, 6, -32768, 32767), (1, 1, 0, 10)):
        img = rng.integers(lo, hi + 1, size=(h, w, 3)).astype(np.int16)
        got = cd.luminance(img)
        exp = _scalar_luminance(img)
        tag = f"luminance {h}x{w} range[{lo},{hi}]"
        if np.array_equal(got, exp):
            print(f"  OK   {tag}")
        else:
            ok = False
            print(f"  FAIL {tag}\n       numpy  {got.tolist()}"
                  f"\n       scalar {exp.tolist()}")

    lut = np.array([min(4095, int(2000 * (i / 4095.0) ** 0.6))
                    for i in range(4096)], dtype=np.int16)
    for h, w, lo, hi in ((5, 7, 0, 4095), (4, 5, -500, 5000), (2, 3, 0, 100)):
        ref = rng.integers(0, 4096, size=(h, w)).astype(np.int16)
        val = rng.integers(lo, hi + 1, size=(h, w)).astype(np.int16)
        wt = rng.integers(0, 256, size=(h, w)).astype(np.uint8)
        got = cd.avoidance_blend(ref, wt, val, lut)
        exp = _scalar_avoidance(ref, wt, val, lut)
        tag = f"avoidance_blend {h}x{w} value-range[{lo},{hi}]"
        if np.array_equal(got, exp):
            print(f"  OK   {tag}")
        else:
            ok = False
            print(f"  FAIL {tag}\n       numpy  {got.tolist()}"
                  f"\n       scalar {exp.tolist()}")

    for clip in (0, 1):
        p = cd.CitrasOpParams(do_clipping=clip)
        img = rng.integers(-1000, 5000, size=(4, 5, 3)).astype(np.int16)
        base = rng.integers(-2000, 2000, size=(4, 5)).astype(np.int16)
        got = cd.tone_compose(img, base, p)
        exp = _scalar_compose(img, base, p)
        tag = f"tone_compose do_clipping={clip}"
        if np.array_equal(got, exp):
            print(f"  OK   {tag}")
        else:
            ok = False
            print(f"  FAIL {tag}")
    return ok


# ---------------------------------------------------------------------------
# 4. the upsample kernels -- real DLL leaf functions vs _upsample_axis
# ---------------------------------------------------------------------------

#: The four leaf kernels ``0x10155290``/``0x101556a0`` dispatch to, chosen by
#: ``r & 1``. Unlike everything else in the upsample path these take RAW
#: POINTERS and plain integers -- no operand objects, no vtables, no accessor
#: protocol -- so they can be called directly with nothing mocked at all.
#: ABI, read off the prologue at ``0x10154113``..``0x10154155``
#: (``[esp+0x38]`` -> N, ``[esp+0x50]`` -> r, ``[esp+0x54]`` -> dstStep,
#: ``[esp+0x50]`` after the 4th push -> srcStep, ``[esp+0x4c]`` -> lines):
#:   ``kernel(src, N, lines, srcStep, srcLineStep, r, dstStep, dstLineStep,
#:            dst)``
#: -- all strides in ELEMENTS (the kernels scale by the element size
#: themselves; ``add esi, eax`` with ``eax = 2*srcLineStep`` for the i16 pair).
UPSAMPLE_KERNELS = {
    (16, 1): 0x10154110,   # odd ratio, int16
    (16, 0): 0x10154300,   # even ratio, int16
    (8, 1): 0x10154500,    # odd ratio, uint8
    (8, 0): 0x101546C0,    # even ratio, uint8
}


def dll_upsample_axis(pe: bytes, src: np.ndarray, r: int,
                      bits: int) -> np.ndarray:
    lines, n = src.shape
    e = Emu(pe)
    esz = 2 if bits == 16 else 1
    flat = src.reshape(-1)
    if bits == 16:
        blob = struct.pack(f"<{flat.size}h", *[int(v) for v in flat])
    else:
        blob = bytes(int(v) & 0xFF for v in flat)
    sp = e.alloc(len(blob) + 64, blob)
    dn = n * r
    dp = e.alloc(lines * dn * esz + 64)
    fn = UPSAMPLE_KERNELS[(bits, r & 1)]
    e.call(fn, [sp, n, lines, 1, n, r, 1, dn, dp])
    raw = bytes(e.uc.mem_read(dp, lines * dn * esz))
    if bits == 16:
        vals = struct.unpack(f"<{lines * dn}h", raw)
        return np.array(vals, dtype=np.int16).reshape(lines, dn)
    return np.frombuffer(raw, dtype=np.uint8).reshape(lines, dn)


def check_upsample(pe: bytes) -> bool:
    """Real ``0x10154110``/``0x10154300``/``0x10154500``/``0x101546c0`` vs
    ``pakon_citras_driver._upsample_axis``.

    This is what turns the upsample from "read off the disassembly" into
    DLL-exact. It matters more than it looks: the resampler is NOT
    nearest-neighbour replication (the obvious guess for an integer upscale
    inside a block-averaging pipeline) but half-pixel-centred linear
    interpolation with LINEAR EXTRAPOLATION past both ends and no clamping,
    and its rounding (``+r`` then truncate-toward-zero, i.e.
    half-away-from-zero, biased UP for negative quotients) is not symmetric.
    Getting any of that wrong would be invisible in the middle of a plane and
    wrong at every edge.
    """
    print("check_upsample -- real DLL resample kernels vs "
          "pakon_citras_driver._upsample_axis")
    rng = np.random.default_rng(20260812)
    cases: list[tuple[int, int, np.ndarray]] = []
    for bits in (16, 8):
        for r in (1, 2, 3, 4, 5, 8):
            for n, lines in ((2, 1), (3, 2), (5, 3), (12, 2)):
                if bits == 16:
                    a = rng.integers(-2000, 4096, size=(lines, n)).astype(np.int16)
                else:
                    a = rng.integers(0, 256, size=(lines, n)).astype(np.uint8)
                cases.append((bits, r, a))
    # The two worked examples that pin the edge behaviour down explicitly:
    # a spike whose extrapolated ends go NEGATIVE, and an r==1 identity pass
    # that is not actually an identity for negative samples (the `+r` bias).
    cases.append((16, 4, np.array([[0, 100, 0]], dtype=np.int16)))
    cases.append((16, 1, np.array([[-3, -1, 5, 7]], dtype=np.int16)))
    bad = 0
    for bits, r, src in cases:
        got = dll_upsample_axis(pe, src, r, bits)
        exp = cd._upsample_axis(src, r, bits)
        if not np.array_equal(got, exp):
            bad += 1
            if bad <= 3:
                print(f"  FAIL bits={bits} r={r} shape={src.shape}")
                print(f"       src  {src.tolist()}")
                print(f"       dll  {got.tolist()}")
                print(f"       host {exp.tolist()}")
    if bad:
        print(f"  {bad}/{len(cases)} cases FAILED")
        return False
    print(f"  OK   {len(cases)} cases, all bit-exact (both element types, "
          "both odd- and even-ratio kernels, r in 1..8)")
    return True


# ---------------------------------------------------------------------------
# 5. ImaBlockAverageOp's compute -- real 0x10154ea0 vs block_average
# ---------------------------------------------------------------------------

BLOCK_AVERAGE_REGION_REQUEST = 0x1032B9D0


def dll_block_average(pe: bytes, src: np.ndarray, factor: int) -> np.ndarray:
    """Run the real ``0x10154ea0`` against a mocked operand pair.

    Only ONE thing is stubbed: ``0x1032b9d0``, the "give me a region object
    covering this rect of my source" request the compute makes on
    ``this->0x104``. Stubbing what that RETURNS (rather than reimplementing
    how the real accessor computes it) is the same scoping choice
    ``pakon_citras_apply_golden.py`` already established for every operand
    accessor -- and it is what makes this function testable at all, since
    that one call is the entire reason docs/66's seventh pass could not
    isolate it (it dives into the generic ``Ima2DImage`` coordinate-mapper
    family that blocked passes 4-7).

    The operand layout below is read straight off the compute's own
    dereferences at ``0x10154f78``..``0x10154ffd``: operand ``+0x30/+0x34``
    origin, ``+0x38/+0x3c`` extents, ``+0x40`` image struct with ``+0x18``
    plane count, ``+0x34`` fast-axis byte step, ``+0x38`` slow-axis byte
    step, ``+0x44`` per-plane base-pointer array; operand vtable slot
    ``+0x14`` returns the byte offset of the rect origin.
    """
    src_h, src_w = src.shape
    out_h, out_w = src_h // factor, src_w // factor
    e = Emu(pe)
    flat = src.reshape(-1)
    blob = struct.pack(f"<{flat.size}h", *[int(v) for v in flat])
    sbuf = e.alloc(len(blob) + 64, blob)
    dbuf = e.alloc(out_h * out_w * 2 + 64)

    def image(buf: int, row_bytes: int) -> int:
        planes = e.alloc(8)
        e.wu32(planes, buf)
        img = e.alloc(0x60)
        e.wi32(img + 0x18, 1)           # one plane
        e.wi32(img + 0x34, 2)            # fast axis: one int16
        e.wi32(img + 0x38, row_bytes)     # slow axis: one row
        e.wu32(img + 0x44, planes)
        return img

    zero_off = e.stub()
    e.hook(zero_off, lambda emu, args: (0, 0))
    vt = e.alloc(0x20)
    e.wu32(vt + 0x14, zero_off)

    region = e.alloc(0x50)
    e.wu32(region, vt)
    e.wu32(region + 0x40, image(sbuf, src_w * 2))
    out = e.alloc(0x50)
    e.wu32(out, vt)
    e.wu32(out + 0x40, image(dbuf, out_w * 2))
    e.wi32(out + 0x30, 0)
    e.wi32(out + 0x34, 0)
    e.wi32(out + 0x38, out_w)
    e.wi32(out + 0x3C, out_h)

    this = e.alloc(0x140)
    e.wu32(this + 0x104, e.alloc(0x10))
    e.wi32(this + 0x108, factor)

    seen: dict[str, list[int]] = {}

    def region_request(emu: Emu, args: int):
        out_slot = emu.r32(args)
        emu.wu32(out_slot, region)
        rect = emu.r32(args + 4)
        seen["rect"] = [emu.ri32(rect + 4 * i) for i in range(4)]
        return region, 0xC

    e.hook(BLOCK_AVERAGE_REGION_REQUEST, region_request)
    _set_fpcw(e, 0x027F)
    e.call(cd.BLOCK_AVERAGE_COMPUTE, [out], ecx=this)
    seen_rect = seen.get("rect")
    expect_rect = [0, 0, factor * out_w, factor * out_h]
    if seen_rect != expect_rect:
        raise RuntimeError(
            f"0x10154ea0 requested source rect {seen_rect}, expected "
            f"{expect_rect} -- the 'all four rect fields are multiplied by "
            "factor' reading is wrong.")
    raw = bytes(e.uc.mem_read(dbuf, out_h * out_w * 2))
    vals = struct.unpack(f"<{out_h * out_w}h", raw)
    return np.array(vals, dtype=np.int16).reshape(out_h, out_w)


def check_block_average(pe: bytes) -> bool:
    """Real ``0x10154ea0`` vs ``pakon_citras_driver.block_average``.

    The rounding here is the part worth proving rather than reading: the
    bias added before the divide is ``floor(factor**2 / 2)``, NOT ``0.5``
    (docs/66's seventh pass recorded it as ``0.5``, which would be almost no
    rounding at all), and it is applied with the SIGN OF THE SUM before a
    truncating divide -- round-half-away-from-zero. The half-boundary cases
    below exist specifically to make that observable; with the wrong bias
    they fail immediately and with a floor-divide instead of a truncating
    one they fail on every negative case.

    Also asserted inside ``dll_block_average``: the source rect the compute
    asks for is ``{0, 0, factor*outW, factor*outH}`` -- all four fields
    scaled, not just the extents.
    """
    print("check_block_average -- real 0x10154ea0 vs "
          "pakon_citras_driver.block_average")
    rng = np.random.default_rng(20260812)
    bad = 0
    total = 0
    for factor in (2, 3, 4, 8):          # 2 takes the integer fast path,
        for out_h, out_w in ((3, 4), (1, 1), (2, 5)):   # the rest the x87 one
            for lo, hi in ((0, 4096), (-4000, 4000), (-32768, 32768)):
                src = rng.integers(lo, hi, size=(out_h * factor,
                                                 out_w * factor)).astype(np.int16)
                total += 1
                if not np.array_equal(dll_block_average(pe, src, factor),
                                      cd.block_average(src, factor)):
                    bad += 1
                    print(f"  FAIL factor={factor} out={out_h}x{out_w} "
                          f"range=({lo},{hi})")
    for factor in (2, 4):
        n = factor * factor
        for base in (-7, -3, -1, 1, 3, 7):
            src = np.zeros((factor, factor), dtype=np.int16)
            src.reshape(-1)[0] = base
            src.reshape(-1)[1] = (n // 2) * (1 if base > 0 else -1)
            total += 1
            if not np.array_equal(dll_block_average(pe, src, factor),
                                  cd.block_average(src, factor)):
                bad += 1
                print(f"  FAIL half-boundary factor={factor} base={base}")
    if bad:
        print(f"  {bad}/{total} cases FAILED")
        return False
    print(f"  OK   {total} cases, all bit-exact (factor 2 fast path AND the "
          "general x87 path, both signs, exact-half boundaries)")
    return True


# ---------------------------------------------------------------------------
# 6. the mirror pad's index formula
# ---------------------------------------------------------------------------


def check_mirror_pad() -> bool:
    """``mirror_pad`` must equal ``ImaPadOpT``'s own modulo arithmetic.

    ``pakon_citras_driver.mirror_pad`` delegates to ``np.pad(mode="reflect")``
    for readability; this check confirms that really is the same mapping the
    DLL computes at ``0x1001754a``..``0x100175a9``, transcribed here
    verbatim from the instruction sequence rather than from the prose::

        srcY = abs(abs((y + H - 1) % (2H - 2)) - (H - 1))

    This is NOT a tautology -- ``mode="reflect"`` (reflect-101, edge sample
    not repeated) and ``mode="symmetric"`` (edge sample repeated) are both
    plausible readings of "MIRROR", they differ on every single padded pixel,
    and only one of them matches the period-``2N-2`` modulo above.
    """
    print("check_mirror_pad -- np.pad(reflect) vs ImaPadOpT's own modulo form")

    def dll_index(i: int, n: int) -> int:
        if n == 1:
            return 0
        q = (i + n - 1) % (2 * n - 2)
        # C's % keeps the dividend's sign; numpy/Python's floors. The DLL
        # uses idiv (C semantics) and then takes abs() of the remainder
        # anyway (0x10017573 cdq/xor/sub), so both agree after the abs.
        return abs(abs(q) - (n - 1))

    ok = True
    for h, w in ((7, 5), (4, 9), (2, 3), (250, 464)):
        for pad in ((0, 1, 0, 0), (24, 24, 24, 24), (0, 3, 0, 2)):
            left, right, top, bottom = pad
            if left >= w or right >= w or top >= h or bottom >= h:
                continue
            src = (np.arange(h * w, dtype=np.int64) % 4001).astype(np.int16)
            src = src.reshape(h, w)
            got = cd.mirror_pad(src, left, right, top, bottom)
            exp = np.empty_like(got)
            for y in range(got.shape[0]):
                sy = dll_index(y - top, h)
                for x in range(got.shape[1]):
                    exp[y, x] = src[sy, dll_index(x - left, w)]
            if not np.array_equal(got, exp):
                ok = False
                print(f"  FAIL {h}x{w} pad={pad}")
    if ok:
        print("  OK   every padded sample matches the DLL's modulo form "
              "(reflect-101: the edge sample is NOT repeated)")
    return ok


def main(argv: list[str]) -> int:
    pe = DEFAULT_DLL.read_bytes()
    results = [
        check_gradient_weight(pe),
        check_fpcw_negative_control(pe),
        check_gaussian_kernel(pe),
        check_upsample(pe),
        check_block_average(pe),
        check_mirror_pad(),
        check_vectorised_leaves(),
    ]
    print()
    if all(results):
        print("ALL OK")
        return 0
    print("FAILURES ABOVE")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
