#!/usr/bin/env python3
r"""docs/74 §36 -- live-Unicorn bracket of the pre-`analyzeAutoTone` chain, on
`test123.bin` frame 0's own real calibrated 14-bit data, the exact frame
§31-35 used for the real, matched-vendor-TIFF brightness-gap investigation.

WHAT THIS FILE IS
==================
§31-35 checked PolyPixel, the F-135 stage-2 inversion, and SBA balance-apply
entirely by READING the real DLL's disassembly (or, for `apply_balance_shifts`,
by citing a prior pass's disassembly reading in `pakon_sba_apply.py`'s own
module docstring) -- never by executing the real machine code live under
Unicorn on this specific frame's real data and diffing the result against the
Python port's own computation for the identical input. This file does that,
for the two stages that structurally CAN be done this way:

  A. PolyPixel (TLB.dll `0x1000d880`) -- reuses `pakon_color_golden.PolyGolden`
     COMPLETELY UNMODIFIED (only monkeypatches its `run()` method at runtime,
     in this process, the same "runtime relocation, not a file edit" pattern
     `pakon_full_colour_chain_golden.patch_unchecked_instruction_cap` already
     established in this project -- see `patch_polygolden_checked_run`'s own
     docstring for why this was necessary, a real, new instance of the exact
     bug class docs/74 §24 already found and fixed for a different golden).
     Run on the REAL, FULL, uncropped 3000x2000 calibrated-14-bit block for
     `test123.bin` frame 0 (`roll.slice14`, the same real production call
     §31/§33/§34 all used), with this unit's real EEPROM matrix
     (`pakon_color.load_unit_matrix`), and diffed against `pakon_color.poly_hwc`
     on the identical input.

  B. SBA balance-apply's own shift-LUT construction -- `pakon_sba_apply.py`'s
     own module docstring already cites the mechanism by address
     (`AnsAreaCapabilityImpl::applyBalanceShifts @ 0x1019a0c0`; master-clip-LUT
     ctor `0x100f42a0` called from `0x1056a470` as `(bits=0xc, floor=0,
     max=0xfff)`; LUT-build loop `0x1006c582`: `out[i] = master[i + shift]`)
     but NO existing golden file in this repo actually executes either
     function under Unicorn -- `pakon_shasta_aim_golden.py`'s own module
     docstring is explicit that this was a "host closed-form check", not a
     Unicorn run.  `SbaShiftLutGolden` below is new, additive code that does
     execute both real functions for the first time, using THIS roll's own
     real `setshifts_out` triple (`(683, 297, 151)`, read live from
     `roll.engine()`, not hardcoded), and diffs the resulting REAL 4096-entry
     per-channel LUTs -- every single entry, not a sample -- against
     `pakon_sba_apply.apply_balance_shifts`'s `clamp(code+shift, 0, 4095)`
     model.  See that class's own docstring for the full calling-convention
     derivation, including what is a genuine vendor call site (the ctor's own
     three argument values, confirmed byte-for-byte against the real
     `0x1056a470` call site) and what is an honestly-flagged modelling choice
     (a freshly-allocated `this` object standing in for the DLL's own static
     singleton at `0x106b5f74`, to avoid needing to run CRT init -- see the
     class docstring's own "NOT established" note).

THE GAP THIS FILE DOES **NOT** CLOSE, AND WHY
================================================
The F-135 stage-2 inversion (`f135_rom12_to_rpd12`, `F135_INVERT_PORTED =
False`) sits BETWEEN these two stages, and cannot be bracketed the same way:
docs/74 §32 already ran a from-scratch, first-of-its-kind, exhaustive
instruction-level search (every `fyl2x`/`fyl2xp1`/`f2xm1` site in TLB.dll, a
substantial spot-check of the much larger set in PakonIMAu.dll) for the one
x87 instruction this formula's own log-difference construction structurally
requires, and found no candidate site that resembles a per-pixel density
formula.  There is, after that search, no known DLL address to point Unicorn
at for this specific stage.  This file does not re-attempt that search --
§32's own verdict (closed without resolving the mystery, PakonIMAu.dll only
partially triaged) stands unchanged.  Because of this, this file brackets
the inversion rather than replacing it: it confirms, live, that the stage
BEFORE it (PolyPixel) and the mechanism USED downstream of it (the shift-LUT
math) are both correct, then applies the REAL, live-executed LUT to the
Python port's own (still `F135_INVERT_PORTED = False`) post-inversion array,
so the reader can see exactly how far live execution now reaches on each
side of the one stage that still can't be reached this way.

REAL DATA, REAL RULES
=======================
`test123.bin` frame 0, via the already-opened real workspace
(`~/Library/Caches/PakonScan/workspace/f4c91b62/roll.json`, the exact roll
docs/74 §31-35 used -- real `film_base=[3107,2490,2414]`,
`fpo=(879,1250,1386)`, `setshifts_out=(683,297,151)`), through the real,
unmodified `Roll.slice14`/`Roll.engine`/`pakon_color.load_unit_matrix`.  Only
aggregate percentile/count statistics are printed anywhere in this file's
output, per this project's rule against describing `captures/` (or, here,
the app cache's equivalent) contents at the pixel level.

DLLs: TLB.dll (`193d9b2ce0a4b77ae9b78262bd06c0fc`) for PolyPixel,
PakonIMAu.dll (`eea9dcf78ee21d4f7c515a6c2512242d`) for the SBA shift-LUT
functions -- the same two MD5s every other docs/74 section already cites,
both re-checked at the top of `main()`.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline:tools python3 \
  tools/ansel/python-pipeline/pakon_prechain_bracket_golden.py``
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
PIPELINE_DIR = HERE.parent                 # tools/ansel/python-pipeline
TOOLS_DIR = HERE.parents[2]                # tools
sys.path.insert(0, str(PIPELINE_DIR))
sys.path.insert(0, str(TOOLS_DIR))

import pakon_color as pc                    # noqa: E402
import pakon_color_golden as pcg            # noqa: E402
import pakon_render as pr                   # noqa: E402
import pakon_sba_apply as sba               # noqa: E402

import pefile                               # noqa: E402
from unicorn import (                       # noqa: E402
    Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UcError,
)
from unicorn.x86_const import (             # noqa: E402
    UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EBP, UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

TLB_DLL = Path("/Users/guy/pakon-windows-repair/COM-SERVER/TLB.dll")
TLB_MD5 = "193d9b2ce0a4b77ae9b78262bd06c0fc"
IMAU_DLL = Path("/Users/guy/pakon-windows-repair/COM-SERVER/PakonIMAu.dll")
IMAU_MD5 = "eea9dcf78ee21d4f7c515a6c2512242d"

ROLL_JSON = Path(
    "/Users/guy/Library/Caches/PakonScan/workspace/f4c91b62/roll.json")
FRAME_INDEX = 0   # the exact frame docs/74 §31-35 compared against AA001.tif

MASTER_CTOR = 0x100F42A0     # AnsAreaCapabilityImpl master-clip-LUT ctor
LUT_BUILD = 0x1006C4F0       # shift-LUT build (out[i] = master[i + shift])
OP_NEW = 0x104FFD78          # MSVCR71.dll operator new(size_t) thunk
OP_DELETE = 0x104FFE3E       # MSVCR71.dll operator delete(void*) thunk


def check_md5(path: Path, expected: str, label: str) -> bool:
    if not path.exists():
        print(f"  {label}: {path} NOT FOUND")
        return False
    got = hashlib.md5(path.read_bytes()).hexdigest()
    ok = got == expected
    print(f"  {label}: {path}  MD5={got}  "
          f"{'OK' if ok else 'MISMATCH (expected ' + expected + ')'}")
    return ok


# ---------------------------------------------------------------------------
# A. PolyPixel -- reuse pakon_color_golden.PolyGolden unmodified, monkeypatch
#    its run() at runtime for full-frame scale (same bug class as docs/74 §24)
# ---------------------------------------------------------------------------


def patch_polygolden_checked_run() -> None:
    """`PolyGolden.run` hard-codes `uc.emu_start(COLOR_CORRECT, STOP,
    count=40_000_000)` and never checks that EIP actually reached `STOP`
    afterward.  Every existing caller of this file (`term-order`, `vectors`,
    `random` with its default 2000-4000 pixels, `handoff`'s default 64x48=
    3072 pixels) stays comfortably under that budget, so this never mattered
    before.

    Confirmed empirically THIS pass, not assumed: a real 250x2000 (500,000
    pixel) crop of `test123.bin` frame 0's own real calibrated data hits the
    40,000,000-instruction cap silently -- `emu_start` returns normally (no
    exception) with EIP stopped mid-loop at `0x1000da4c`, not at `STOP`, and
    the unmodified `run()` has no way to notice and would have returned
    whatever partial/stale bytes happened to sit in the image buffer as if
    they were a completed run.  This is the exact bug SHAPE docs/74 §24 found
    in `pakon_autotone_shell_golden.Emu.call` (a hard-coded instruction cap,
    fine at every previously-tested scale, silently wrong at real full-frame
    scale) -- an independent instance of it, in a different golden file,
    found by the same method this pass uses throughout: checking completion
    explicitly instead of trusting a clean return.

    Does NOT modify `pakon_color_golden.py` on disk -- replaces the bound
    method on the already-imported class object at runtime, in this process
    only, mirroring `pakon_full_colour_chain_golden.
    patch_unchecked_instruction_cap`'s own precedent for the identical
    situation.
    """
    def run_checked(self, coeffs, pixels, film_class: int = 1,
                    width: int | None = None, height: int = 1,
                    count: int = 8_000_000_000):
        if len(coeffs) != 30:
            raise ValueError("need exactly 30 coefficients")
        off = pcg.MATRIX_COLREV if film_class == 2 else pcg.MATRIX_COLNEG
        self.uc.mem_write(pcg.THIS_OBJ + off, struct.pack("<30f", *coeffs))
        n = len(pixels)
        w = int(width) if width is not None else n
        h = int(height)
        if w * h != n:
            raise ValueError(f"width*height ({w}*{h}) != len(pixels) ({n})")
        planes = [bytearray(), bytearray(), bytearray()]
        for px in pixels:
            for c in range(3):
                planes[c] += struct.pack("<H", px[c] & 0xFFFF)
        self.uc.mem_write(pcg.IMAGE_BUF,
                          bytes(planes[0] + planes[1] + planes[2]))
        args = (0, pcg.IMAGE_BUF, film_class, w, h)
        esp = pcg.STACK_BASE + pcg.STACK_SIZE - 0x2000
        self._set_fpu_control_word()
        payload = b"".join(struct.pack("<I", a) for a in args)
        esp -= len(payload)
        self.uc.mem_write(esp, payload)
        esp -= 4
        self.uc.mem_write(esp, struct.pack("<I", pcg.STOP))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_EBP, esp)
        self.uc.reg_write(UC_X86_REG_ECX, pcg.THIS_OBJ)
        self.uc.emu_start(pcg.COLOR_CORRECT, pcg.STOP, count=count)
        eip = self.uc.reg_read(UC_X86_REG_EIP)
        if eip != pcg.STOP:
            raise RuntimeError(
                f"PolyPixel did not reach STOP (stopped at {eip:#x}) -- hit "
                f"the {count:,}-instruction cap mid-execution; this result "
                f"cannot be trusted")
        raw = self.uc.mem_read(pcg.IMAGE_BUF, n * 6)
        out = []
        for i in range(n):
            out.append(tuple(
                struct.unpack_from("<H", raw, (c * n + i) * 2)[0]
                for c in range(3)))
        return out

    pcg.PolyGolden.run = run_checked


def run_polypixel_full_frame(seg14: np.ndarray, coeffs) -> dict:
    """Real DLL PolyPixel, real full frame, vs `pakon_color.poly_hwc` on the
    identical real input.  Returns aggregate stats only (no per-pixel
    content), per this project's rule.
    """
    h, w = int(seg14.shape[0]), int(seg14.shape[1])
    n = h * w
    needed_bytes = n * 6
    g = pcg.PolyGolden(str(TLB_DLL))
    extra = needed_bytes - pcg.BUF_SIZE
    if extra > 0:
        extra = (extra + 0xFFF) & ~0xFFF
        g.uc.mem_map(pcg.IMAGE_BUF + pcg.BUF_SIZE, extra)

    pixels = [tuple(int(v) for v in seg14[y, x])
              for y in range(h) for x in range(w)]
    t0 = time.time()
    emu = g.run(coeffs, pixels, film_class=1, width=w, height=h)
    dt = time.time() - t0

    emu_arr = np.array(emu, dtype=np.uint16).reshape(h, w, 3)
    host_arr = pc.poly_hwc(seg14, coeffs, film_class=1)
    diff = emu_arr.astype(np.int64) - host_arr.astype(np.int64)
    bad = int(np.count_nonzero(diff))
    return {
        "pixels": n, "wall_s": dt, "bad": bad, "total_values": diff.size,
        "max_abs_diff": int(np.abs(diff).max()) if bad else 0,
        "emu_arr": emu_arr, "host_arr": host_arr,
    }


# ---------------------------------------------------------------------------
# B. SBA balance-apply shift-LUT construction -- new, real Unicorn execution
# ---------------------------------------------------------------------------


class SbaShiftLutGolden:
    """Real Unicorn execution of `AnsAreaCapabilityImpl`'s master-clip-LUT
    ctor (`0x100f42a0`) and shift-LUT builder (`0x1006c4f0`) in
    PakonIMAu.dll, the exact two functions `pakon_sba_apply.py`'s own module
    docstring already cites BY ADDRESS from a prior disassembly-reading pass
    but that no golden file has ever executed.

    CALLING CONVENTION -- derived fresh this pass, from live disassembly
    -------------------------------------------------------------------
    Both functions were fully disassembled (`aa; af; pdf`, r2 6.1.8, PE
    loaded at its real base `0x10000000`) this pass, not transcribed from any
    prior citation:

    ``0x100f42a0`` (the ctor): `ret 0xc` -- thiscall, 3 stack args. The REAL
    vendor call site that constructs the one live singleton this DLL ever
    uses (`0x1056a470`, read directly this pass) is:

        push 0xfff        ; arg3 (ebp+0x10) = max
        push 0             ; arg2 (ebp+0xc)  = floor
        push 0xc           ; arg1 (ebp+8)    = bits
        mov ecx, 0x106b5f74
        call 0x100f42a0

    matching `pakon_sba_apply.py`'s own citation exactly
    (``bits=0xc, floor=0, max=0xfff``) -- this is a genuine, byte-for-byte
    confirmed vendor call site, not a guess.  The ctor allocates
    ``0x20002`` bytes via `operator new`, stores the raw pointer at
    ``this+4``, ``this+8 = raw_ptr + 0x10000`` (the signed
    ``-0x8000..0x7fff``-indexable "usable" pointer the docstring already
    describes), then fills it: ``master[i]=0`` for ``i<=0``,
    ``master[i]=i`` for ``1..0xfff``, ``master[i]=0xfff`` for ``i>0xfff``.

    ``0x1006c4f0`` (the LUT builder): `ret 0x1c` -- thiscall, 7 stack args.
    The real caller, `applyBalanceShifts` itself (`0x1019a0c0`, also fully
    disassembled this pass), pushes, in order:

        push edx   ; shiftB   (ebp+0x14 at the caller -- the 4th real stack
                     arg `applyBalanceShifts` itself receives)
        push ecx   ; shiftG   (caller's ebp+0x10, its 3rd real stack arg)
        push eax   ; shiftR   (caller's ebp+0xc,  its 2nd real stack arg)
        push 0x1000            ; count
        push &out3-ptr-slot
        push &out2-ptr-slot
        push &out1-ptr-slot
        mov ecx, <the same 0x106b5f74 singleton the ctor built>
        call 0x1006c4f0

    i.e. ``0x1006c4f0``'s own real argument order (low to high `ebp`
    offset) is ``(&outLutR, &outLutG, &outLutB, count, shiftR, shiftG,
    shiftB)``. The three `&outLutN` slots are int16** -- the callee itself
    `operator new[]`s each 4096-entry buffer and writes the resulting
    pointer back through the caller-supplied slot (confirmed by direct
    disassembly of the allocation block at `0x1006c528`-`0x1006c565`, not
    inferred).  ``applyBalanceShifts``'s own arg2/arg3/arg4 (its 2nd/3rd/4th
    real stack params) are therefore confirmed, by this direct disassembly,
    to be the R/G/B shift values -- exactly what `pakon_sba_apply.py`'s own
    docstring already asserted from static reading, now independently
    confirmed by tracing the real call site's own register provenance.

    WHAT IS HONESTLY *NOT* ESTABLISHED
    -------------------------------------
    * This class builds its OWN fresh `this` object (via `build_master`)
      rather than reusing the DLL's own static singleton at `0x106b5f74`.
      This is a deliberate modelling choice, flagged plainly: reusing the
      real static address would require the DLL's own CRT/static
      initializers to have already run (the real call site is itself CRT
      init code, `0x1056a470`), which this harness does not attempt to
      replay (the same category of "not modelled" scope-bounding
      `pakon_full_colour_chain_golden.BalanceAreaImageCall`'s own docstring
      already uses for unknown vendor state).  The functions executed ARE
      the real vendor machine code, unmodified, with real vendor-cited
      argument VALUES for the ctor -- only the `this` object's own memory
      address is synthetic scaffolding, not vendor data.
    * `operator new`/`operator delete` (`0x104ffd78`/`0x104ffe3e`, both
      thunks into the unloaded `MSVCR71.dll`) are stubbed with a plain bump
      allocator / no-op respectively, rather than loading the real CRT DLL.
      This is a narrowly-scoped stub with an unambiguous standard-library
      contract (`void* operator new(size_t)`; `void operator delete(void*)`)
      -- not a guess about unknown vendor business logic -- and matches this
      project's own established practice for exactly this situation
      (`pakon_shasta_aim_golden.py`'s own module docstring: "stubbed
      operator new / malloc").
    """

    def __init__(self, dll_bytes: bytes):
        IMAGE_BASE = 0x10000000
        self.STACK_BASE = 0x70000000
        STACK_SIZE = 0x00100000
        self.STOP = 0x7FFFF000

        pe = pefile.PE(data=dll_bytes, fast_load=True)
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        uc.mem_map(IMAGE_BASE, size)
        uc.mem_write(IMAGE_BASE, pe.get_memory_mapped_image(ImageBase=IMAGE_BASE))
        for base, sz in ((self.STACK_BASE, STACK_SIZE),
                         (self.STOP & ~0xFFF, 0x1000), (0, 0x1000)):
            try:
                uc.mem_map(base, (sz + 0xFFF) & ~0xFFF)
            except UcError:
                pass

        def on_unmapped(uc, access, address, size, value, user):
            try:
                uc.mem_map(address & ~0xFFF, 0x1000)
            except UcError:
                pass
            return True
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, on_unmapped)

        self._bump_next = 0x50000000

        def hook_new(uc, address, size, user):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret_addr = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            sz = struct.unpack("<I", uc.mem_read(esp + 4, 4))[0]
            ptr = self._bump_next
            self._bump_next += (sz + 0xF) & ~0xF
            start = ptr & ~0xFFF
            end = (self._bump_next + 0xFFF) & ~0xFFF
            try:
                uc.mem_map(start, end - start)
            except UcError:
                pass
            uc.reg_write(UC_X86_REG_EAX, ptr)
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
            uc.reg_write(UC_X86_REG_EIP, ret_addr)

        def hook_delete(uc, address, size, user):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret_addr = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
            uc.reg_write(UC_X86_REG_EIP, ret_addr)

        uc.hook_add(UC_HOOK_CODE, hook_new, begin=OP_NEW, end=OP_NEW)
        uc.hook_add(UC_HOOK_CODE, hook_delete, begin=OP_DELETE, end=OP_DELETE)

        self.uc = uc
        self._scratch_next = 0x51000000

    def _scratch_alloc(self, n: int) -> int:
        p = self._scratch_next
        n = (n + 0xF) & ~0xF
        self._scratch_next += n
        start = p & ~0xFFF
        end = (self._scratch_next + 0xFFF) & ~0xFFF
        try:
            self.uc.mem_map(start, end - start)
        except UcError:
            pass
        return p

    def _call(self, va: int, args, ecx: int | None = None,
              count: int = 200_000_000) -> int:
        uc = self.uc
        esp = self.STACK_BASE + 0x00100000 - 0x2000
        payload = b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        esp -= len(payload)
        uc.mem_write(esp, payload)
        esp -= 4
        uc.mem_write(esp, struct.pack("<I", self.STOP))
        uc.reg_write(UC_X86_REG_ESP, esp)
        uc.reg_write(UC_X86_REG_EBP, esp)
        if ecx is not None:
            uc.reg_write(UC_X86_REG_ECX, ecx)
        uc.emu_start(va, self.STOP, count=count)
        eip = uc.reg_read(UC_X86_REG_EIP)
        if eip != self.STOP:
            raise RuntimeError(
                f"emu {va:#x} did not reach STOP (stopped at {eip:#x})")
        return uc.reg_read(UC_X86_REG_EAX)

    def build_master(self) -> int:
        """Real `0x100f42a0`, real vendor args `(bits=0xc, floor=0,
        max=0xfff)` matching the real `0x1056a470` call site exactly.
        Returns the fresh `this` pointer.
        """
        this = self._scratch_alloc(0x20)
        self.uc.mem_write(this, b"\x00" * 0x20)
        self._call(MASTER_CTOR, args=[0xC, 0, 0xFFF], ecx=this)
        return this

    def check_master_table_exhaustive(self, this: int) -> dict:
        """Every one of the 65,536 addressable entries (`-0x8000..0x7fff`),
        not a sample, against the closed form `pakon_sba_apply.py`'s own
        docstring already states.
        """
        field8 = struct.unpack("<I", self.uc.mem_read(this + 8, 4))[0]
        raw = self.uc.mem_read(field8 - 0x10000, 0x10000 * 2)
        table = np.frombuffer(raw, dtype="<i2").astype(np.int64)
        idx = np.arange(-0x8000, 0x8000, dtype=np.int64)
        expected = np.clip(idx, 0, 0xFFF)
        expected[idx <= 0] = 0
        bad = int(np.count_nonzero(table != expected))
        return {"entries": table.size, "bad": bad,
                "max_abs_diff": int(np.abs(table - expected).max()) if bad
                else 0}

    def build_shift_luts(self, this: int, shift_r: int, shift_g: int,
                         shift_b: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Real `0x1006c4f0`, real shift values, returns the three REAL
        4096-entry int16 LUTs the vendor code itself allocated and filled.
        """
        out1 = self._scratch_alloc(4)
        out2 = self._scratch_alloc(4)
        out3 = self._scratch_alloc(4)
        for p in (out1, out2, out3):
            self.uc.mem_write(p, b"\x00\x00\x00\x00")
        status = self._call(
            LUT_BUILD, args=[out1, out2, out3, 0x1000,
                             shift_r, shift_g, shift_b], ecx=this)
        if (status & 0xFFFF) != 0:
            raise RuntimeError(
                f"0x1006c4f0 returned non-zero status {status & 0xFFFF:#x}")
        p1, p2, p3 = (struct.unpack("<I", self.uc.mem_read(p, 4))[0]
                     for p in (out1, out2, out3))

        def read_lut(ptr: int) -> np.ndarray:
            raw = self.uc.mem_read(ptr, 0x1000 * 2)
            return np.frombuffer(raw, dtype="<i2").astype(np.int64)

        return read_lut(p1), read_lut(p2), read_lut(p3)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    print("== DLL provenance ==")
    ok_tlb = check_md5(TLB_DLL, TLB_MD5, "TLB.dll")
    ok_imau = check_md5(IMAU_DLL, IMAU_MD5, "PakonIMAu.dll")
    if not (ok_tlb and ok_imau):
        print("refusing to trust an unverified DLL copy")
        return 2
    print()

    if not ROLL_JSON.exists():
        print(f"{ROLL_JSON} not found -- this pass's real workspace is not "
              f"present on this machine")
        return 2

    print(f"== real roll/frame: {ROLL_JSON} frame {FRAME_INDEX} ==")
    with open(ROLL_JSON) as f:
        roll = pr.Roll.from_json(json.load(f))
    frame = roll.frames[FRAME_INDEX]
    seg14 = roll.slice14(frame.a, frame.b, 1)
    eng = roll.engine()
    coeffs = pc.load_unit_matrix(film_class=roll.film_class())
    print(f"  frame shape: {seg14.shape[0]}x{seg14.shape[1]} "
         f"({seg14.shape[0] * seg14.shape[1]:,} pixels)")
    print(f"  roll.film_base={[round(v) for v in roll.film_base]}  "
         f"fpo={eng.sba.fpo}  setshifts_out={eng.setshifts_out}")
    print()

    # -- Stage A: PolyPixel, real full frame, live Unicorn -----------------
    print("== Stage A: PolyPixel (TLB.dll 0x1000d880), REAL full frame, "
         "live Unicorn vs pakon_color.poly_hwc ==")
    patch_polygolden_checked_run()
    res_a = run_polypixel_full_frame(seg14, coeffs)
    print(f"  {res_a['pixels']:,} pixels, wall time {res_a['wall_s']:.1f}s "
         f"(execution confirmed to reach completion, not instruction-cap "
         f"truncated)")
    print(f"  values checked: {res_a['total_values']:,}  "
         f"mismatches: {res_a['bad']}  max_abs_diff: {res_a['max_abs_diff']}")
    if res_a["bad"] == 0:
        print("  => bit-exact: real DLL PolyPixel == pakon_color.poly_hwc, "
             "on this frame's real, full, calibrated 14-bit data.")
    else:
        print("  => REAL DIVERGENCE -- see per-channel breakdown below.")
        for c, name in enumerate("RGB"):
            d = (res_a["emu_arr"][:, :, c].astype(np.int64)
                -res_a["host_arr"][:, :, c].astype(np.int64))
            nz = d[d != 0]
            if nz.size:
                print(f"    {name}: {nz.size} mismatched, "
                     f"delta percentiles [1,50,99]="
                     f"{np.percentile(nz, [1, 50, 99]).round(2).tolist()}")
    print()

    # -- Stage B: SBA balance-apply shift-LUT, live Unicorn -----------------
    print("== Stage B: SBA shift-LUT (PakonIMAu.dll 0x100f42a0 + "
         "0x1006c4f0), live Unicorn, this roll's real setshifts_out ==")
    imau_bytes = IMAU_DLL.read_bytes()
    sba_golden = SbaShiftLutGolden(imau_bytes)
    this = sba_golden.build_master()
    master_check = sba_golden.check_master_table_exhaustive(this)
    print(f"  master-clip-LUT ctor (0x100f42a0): {master_check['entries']:,} "
         f"entries checked (exhaustive, -0x8000..0x7fff), "
         f"mismatches: {master_check['bad']}  "
         f"max_abs_diff: {master_check['max_abs_diff']}")

    sr, sg, sb = eng.setshifts_out
    lut_r, lut_g, lut_b = sba_golden.build_shift_luts(this, sr, sg, sb)
    idx = np.arange(0x1000, dtype=np.int64)
    total_bad = 0
    total_max = 0
    for name, lut, shift in (("R", lut_r, sr), ("G", lut_g, sg),
                             ("B", lut_b, sb)):
        expected = np.clip(idx + shift, 0, 0xFFF)
        d = lut - expected
        bad = int(np.count_nonzero(d))
        mx = int(np.abs(d).max()) if bad else 0
        total_bad += bad
        total_max = max(total_max, mx)
        print(f"  shift-LUT {name} (shift={shift}): 4096/4096 entries "
             f"checked, mismatches: {bad}  max_abs_diff: {mx}")
    if total_bad == 0:
        print("  => bit-exact, ALL 3x4096 LUT entries: real DLL shift-LUT "
             "construction == pakon_sba_apply.apply_balance_shifts's "
             "clamp(code+shift,0,4095) model, for this roll's real "
             "setshifts_out.")
    else:
        print(f"  => REAL DIVERGENCE -- {total_bad} total mismatched "
             f"entries, max_abs_diff={total_max}.")
    print()

    # -- Stage C: apply the REAL, live-executed LUT to this frame's real
    #    post-inversion RPD-12 array (Python port's own, still-unverified
    #    F135_INVERT_PORTED=False formula supplies that array; only the
    #    balance-APPLY step is being cross-checked here against real DLL
    #    output, not the inversion itself) --------------------------------
    print("== Stage C: apply the REAL vendor-executed LUT to this frame's "
         "real post-inversion RPD-12 array, vs pakon_sba_apply.py's "
         "pure-Python apply, on the IDENTICAL array ==")
    rpd12 = pr.scene_rpd12(seg14, roll.data_dir, np.zeros(3), roll.model, eng,
                           film_base=roll.film_base,
                           film_class=roll.film_class())
    print(f"  (rpd12 array from pr.scene_rpd12 -- the SAME still-unverified "
         f"F135_INVERT_PORTED=False formula every other docs/74 section "
         f"uses; only the balance-apply step below is being live-checked)")
    vendor_luts = {"R": lut_r, "G": lut_g, "B": lut_b}
    vendor_applied = np.empty_like(rpd12)
    for c, name in enumerate("RGB"):
        vendor_applied[:, :, c] = vendor_luts[name][
            np.clip(rpd12[:, :, c].astype(np.int64), 0, 0xFFF)]
    python_applied = sba.apply_balance_shifts(rpd12, eng.setshifts_out)
    diff_c = (vendor_applied.astype(np.int64)
             -python_applied.astype(np.int64))
    bad_c = int(np.count_nonzero(diff_c))
    print(f"  {diff_c.size:,} values checked  mismatches: {bad_c}  "
         f"max_abs_diff: {int(np.abs(diff_c).max()) if bad_c else 0}")
    if bad_c == 0:
        print("  => bit-exact on this real frame's real post-inversion "
             "array: applying the REAL, live-executed vendor LUT produces "
             "IDENTICAL output to pakon_sba_apply.apply_balance_shifts.")
    print()

    # -- Verdict --------------------------------------------------------
    print("== Verdict ==")
    a_ok = res_a["bad"] == 0
    b_ok = total_bad == 0 and master_check["bad"] == 0
    print(f"  PolyPixel (pre-inversion):  {'BIT-EXACT' if a_ok else 'DIVERGES'}"
         f"  -- live Unicorn, real full frame, first time on THIS capture")
    print(f"  SBA shift-LUT (post-inversion mechanism): "
         f"{'BIT-EXACT' if b_ok else 'DIVERGES'}"
         f"  -- live Unicorn, first time ever (previously citation-only)")
    print(f"  F-135 inversion (the stage BETWEEN them): NOT BRACKETABLE -- "
         f"no known DLL entry point exists to point Unicorn at (docs/74 "
         f"§32's own exhaustive TLB.dll search + partial PakonIMAu.dll "
         f"spot-check, unchanged by this pass)")
    return 0 if (a_ok and b_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
