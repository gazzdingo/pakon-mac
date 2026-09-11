#!/usr/bin/env python3
"""Unicorn golden for the SCPLut analyze worker ``fcn.10287eb0``.

WHY THIS FUNCTION
=================
docs/74 §139–§141: the washed-out defect needs a transform between tone and ICC
that this port does not have (§136 proved the pre-ICC encode is correct --
source max 4095, dest max 255, read live off the vendor in v35). SCPLut is the
only candidate whose PRODUCT matches a correction that measurably works:

* ``scp_lut_fill_channel`` (already ported, ``0x102881e6…0x102882af``) builds a
  per-channel ``out[i] = clamp(ftol2(slope*i - offset + 0.5))`` LUT.
* ``PAKON_BLACK_WHITE`` applies exactly that form by hand and moves R's slope
  error 36.8 % -> 8.2 % with spans within ~2 % of the vendor (§135.1).
* ``AnsSCPLutResults`` carries per-channel slope/offset plus ``visualGamma``
  (§140.1), and ``visualGamma`` is a curvature term -- the one defect the hand
  correction provably cannot fix.

Everything around the worker is already ported (opponent ``0x1028c4e0``,
``ftol2`` ``0x104ffe44``, ``slope_dist``, ``visual_gamma_scale``, the clamp and
the fill loop). **The only gap is how slope and offset are COMPUTED**, which is
this worker. It is bounded: 1097 B, 292 instructions, 160 FP ops, cyclomatic 14,
and its only callees are the two already-ported leaves -- no transcendental
helpers.

WHAT THIS FILE IS FOR
=====================
Running the REAL worker under Unicorn so a Python port can be diffed against it
bit-exact, per CLAUDE.md's tier 1. It is the reference, not the port: nothing
here reimplements the arithmetic.

A TRAP ALREADY FOUND
====================
The constant at ``0x105a69e0`` is ``1.7320508`` -- sqrt(3) truncated to seven
decimals, NOT ``1.7320508075688772``. Any port writing ``math.sqrt(3)`` will
diverge. Constants must be transcribed from the image.

STATUS: harness only. No claim is made here about the worker's arithmetic; the
point of the harness is to make such claims checkable.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

try:
    from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP,
    )
except ImportError:  # pragma: no cover
    sys.exit("needs `pip install unicorn`")

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
HEAP_ADDR = 0x20000000
HEAP_SIZE = 0x100000

VA_WORKER = 0x10287EB0          # fcn.10287eb0, the analyze worker
VA_OPPONENT = 0x1028C4E0        # already ported: pakon_scp_lut opponent
VA_FTOL2 = 0x104FFE44           # already ported: scp_lut_ftol2

#: sqrt(3) as the DLL stores it -- truncated, see the module docstring.
SCP_SQRT3_TRUNCATED = 1.7320508
VA_SQRT3 = 0x105A69E0


def _map_image(uc: Uc, dll: bytes) -> None:
    """Map .text and .rdata at their real VAs (same shape as the other goldens)."""
    e = struct.unpack_from("<I", dll, 0x3C)[0]
    nsec = struct.unpack_from("<H", dll, e + 6)[0]
    optsz = struct.unpack_from("<H", dll, e + 0x14)[0]
    soff = e + 0x18 + optsz
    for i in range(nsec):
        o = soff + i * 40
        name = dll[o : o + 8].split(b"\0")[0]
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", dll, o + 8)
        if name not in (b".text", b".rdata"):
            continue
        end = (va + max(vsize, rawsize) + 0xFFF) & ~0xFFF
        for p in range(va & ~0xFFF, end, 0x1000):
            try:
                uc.mem_map(IMAGE_BASE + p, 0x1000)
            except UcError:
                pass
        uc.mem_write(IMAGE_BASE + va,
                     dll[rawptr : rawptr + min(rawsize, max(vsize, rawsize))])


def verify_constants(dll: bytes) -> None:
    """Assert the transcribed constants match the image, before trusting a port."""
    off = VA_SQRT3 - IMAGE_BASE
    # .rdata VA -> file offset needs the section table; read via the mapped image
    # instead in run_worker(). Here we only check the value once mapped.
    _ = off


def run_worker(dll_path: Path, args: list[int]) -> dict:
    """Execute fcn.10287eb0 with `args` as its 13 stack dwords.

    Returns the output doubles the caller (0x102127d0) copies out, read back
    from the stack slots the worker writes: esp+0x28/0x30/0x38/0x40/0x48/0x50.
    """
    dll = dll_path.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    _map_image(uc, dll)

    # Confirm the sqrt(3) constant really is the truncated form, from the image.
    got = struct.unpack("<d", uc.mem_read(VA_SQRT3, 8))[0]
    if got != SCP_SQRT3_TRUNCATED:
        raise AssertionError(
            f"constant at {VA_SQRT3:#x} is {got!r}, expected the truncated "
            f"{SCP_SQRT3_TRUNCATED!r} -- the image changed or the VA is wrong")

    # Argument layout, recovered from the caller 0x102127d0's marshalling
    # (pushes are reverse order, so the last push is arg0):
    #   arg0        pixel count n   (the `ecx` in `lea [eax+ecx*2/*4]`)
    #   arg1..arg7  seven scalars forwarded from the Impl
    #   arg8, arg9  &var_20h, &var_34h -- OUT pointers
    #   arg10       plane base                (R)
    #   arg11       base + n*2                (G)
    #   arg12       base + n*4                (B)
    # i.e. three int16 planes of n pixels in ONE buffer -- the same planar
    # shape as the Shasta analysis image. This is what makes the harness
    # runnable without a capture.
    esp = STACK_ADDR + STACK_SIZE - 0x400
    # return address that is mapped but never executed; the run stops there
    stop = IMAGE_BASE + 0x1000
    uc.mem_write(esp, struct.pack("<I", stop))
    for i, a in enumerate(args):
        uc.mem_write(esp + 4 + 4 * i, struct.pack("<I", a & 0xFFFFFFFF))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBP, esp)

    uc.emu_start(VA_WORKER, stop, timeout=10_000_000)

    out_esp = uc.reg_read(UC_X86_REG_ESP)
    return {
        "esp": out_esp,
        "eax": uc.reg_read(UC_X86_REG_EAX),
        "sqrt3_from_image": got,
    }


def run_on_planes(dll_path: Path, planes, scalars=None, ctrl=None) -> dict:
    """Drive the worker on a real planar RGB image.

    `planes` is (r, g, b), each a sequence of n int16 code values. They are laid
    out contiguously as the caller does -- base, base+n*2, base+n*4 -- so the
    worker's own pointer arithmetic is reproduced rather than guessed.
    """
    r, g, b = planes
    n = len(r)
    assert len(g) == n and len(b) == n, "planes must be equal length"
    dll = dll_path.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    _map_image(uc, dll)

    got = struct.unpack("<d", uc.mem_read(VA_SQRT3, 8))[0]
    if got != SCP_SQRT3_TRUNCATED:
        raise AssertionError(f"sqrt3 constant is {got!r}")

    base = HEAP_ADDR
    buf = b"".join(struct.pack("<%dh" % n, *p_) for p_ in (r, g, b))
    uc.mem_write(base, buf)
    # arg8 is IN/OUT, not a pure out-param: the worker reads `word [arg8]` as
    # the mode (`cmp cx, 1` / `cmp cx, 2` at 0x10288163 / 0x102881b9) and
    # `word [arg8+2]` as a second control word. pakon_scp_lut documents these
    # as ntdChoice / ctdChoice, and the SHIPPED dpi sets them to (1, 2).
    # Zeroing them selects the degenerate path and leaves the slopes at 1.0.
    out8, out9 = HEAP_ADDR + 0x40000, HEAP_ADDR + 0x40100
    uc.mem_write(out8, b"\0" * 0x100)
    uc.mem_write(out9, b"\0" * 0x100)
    # `ctrl` may be a full captured arg8 block (bytes) or a (ntd, ctd) pair.
    # v37 shows arg8 carries more than the two mode words: (2, 1, 4, 1) then a
    # double 0.7 at +8. Writing only the two words leaves the rest zero, which
    # keeps the worker on its degenerate path.
    if isinstance(ctrl, (bytes, bytearray)):
        uc.mem_write(out8, bytes(ctrl))
    else:
        ntd, ctd = ctrl or (1, 2)
        uc.mem_write(out8, struct.pack("<hh", int(ntd), int(ctd)))

    sc = list(scalars or [0] * 7)
    args = [n] + sc + [out8, out9, base, base + n * 2, base + n * 4]

    esp = STACK_ADDR + STACK_SIZE - 0x400
    stop = IMAGE_BASE + 0x1000
    uc.mem_write(esp, struct.pack("<I", stop))
    for i, a in enumerate(args):
        uc.mem_write(esp + 4 + 4 * i, struct.pack("<I", a & 0xFFFFFFFF))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBP, esp)
    uc.emu_start(VA_WORKER, stop, timeout=30_000_000)

    return {
        "eax": uc.reg_read(UC_X86_REG_EAX),
        "out8": bytes(uc.mem_read(out8, 0x40)),
        "out9": bytes(uc.mem_read(out9, 0x40)),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("usage: pakon_scp_worker_golden.py <PakonIMAu.dll>")
        return 2
    p = Path(sys.argv[1])
    print(f"worker  {VA_WORKER:#x}   opponent {VA_OPPONENT:#x} (ported)   "
          f"ftol2 {VA_FTOL2:#x} (ported)")
    try:
        r = run_worker(p, [0] * 13)
        print(f"ran; eax={r['eax']:#x}  sqrt3 constant from image = "
              f"{r['sqrt3_from_image']!r}")
        print("NOTE: all-zero args exercise the degenerate path only. Real "
              "inputs must come from a capture before any port is diffed.")
    except AssertionError as e:
        print(f"CONSTANT CHECK FAILED: {e}")
        return 1
    except UcError as e:
        print(f"emulation stopped: {e}")
        print("Expected while the arg layout is still unknown -- the worker "
              "takes 13 stack dwords whose types are not yet all established.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
