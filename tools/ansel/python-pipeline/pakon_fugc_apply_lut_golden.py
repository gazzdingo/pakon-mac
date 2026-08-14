#!/usr/bin/env python3
r"""Real-DLL Unicorn probe: does ``AnsFugcCapabilityImpl::applyLut``
(``fcn.101fa5b0``, wrapper ``fcn.101186c0``) ever write into the pixel
buffer it is handed?  docs/74 §27 left this open (``FUGC_APPLY_LUT_GATE_
PORTED`` only covers the entry image-type gate; "full pixel path not
ported" -- ``pakon_fugc.py:107-109``); §28 answers it, both statically
(read in full, see docs/74) and here, dynamically.

WHAT THIS FILE DOES
====================
Calls the real ``applyLut`` (``0x101fa5b0``) directly under Unicorn --
bypassing the thin forwarding thunk (``0x101186c0``, already fully
disassembled in docs/74 §27.3/§28 and adds nothing but an indirection
through ``this->0x10``) -- with:

* ``ecx`` (this) = a real FUGC Impl object whose ``+0x6140`` field holds a
  REAL, non-identity per-channel apply LUT, built by this project's own
  already-Unicorn-verified ``pakon_fugc.set_lut_info`` (``FUGC_SET_LUT_
  INFO_PORTED = True``) -- not a synthetic placeholder table.
* ``arg1`` (``&status_out``) = a fresh local cell, matching the real
  calling convention derived in docs/74 §27/§28 from the wrapper's own
  disassembly (push order: wrapper's ``eax``=arg_ch=AREA_IMAGE ends up as
  ``applyLut``'s arg2; wrapper's ``esi``=arg_ch_2=``&status_out`` ends up
  as ``applyLut``'s arg1 -- confirmed by hand ESP/EBP arithmetic against
  the wrapper's own literal encoded displacements, not guessed).
* ``arg2`` (the "AREA image" descriptor) = a real, non-degenerate
  descriptor: ``+0x4=0`` (PIXEL layout, the type ``applyLut``'s own gate
  at ``0x101fa5e5`` accepts), ``+0xc``/``+0x10`` = real width/height,
  ``+0x20`` = a pointer to a REAL pixel buffer filled with a distinctive,
  fingerprintable non-zero pattern (not all-zero, so a write of "0" would
  still be visible as a change).

Watches ``UC_HOOK_MEM_WRITE`` on the exact pixel-buffer address range for
the WHOLE call, the same direct technique docs/74 §22/§24 already used for
``balanceAreaImage``.  If execution faults on a call target this project
has no existing characterization for, this file reports the fault
verbatim and stops -- it does not stub around unknown vendor arithmetic to
force a green result (same discipline as ``pakon_full_colour_chain_golden.
BalanceAreaImageCall``).

Reuses ``pakon_autotone_shell_golden.Emu`` completely unmodified for its
PE loader / bump heap / SEH page / ``operator new`` hook / fault collector
-- the same base class ``pakon_autotone_assembled_golden.AssembledEmu``
(and therefore ``pakon_full_colour_chain_golden.py``) already builds on.
Does not modify any existing golden file.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_fugc_apply_lut_golden.py [dll]``
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import pakon_fugc as fugc                          # noqa: E402
import pakon_autotone_shell_golden as shellg        # noqa: E402

from unicorn import UC_HOOK_MEM_WRITE               # noqa: E402

EXPECTED_MD5 = "eea9dcf78ee21d4f7c515a6c2512242d"

APPLY_LUT = 0x101FA5B0          # AnsFugcCapabilityImpl::applyLut
APPLY_LUT_WRAPPER = 0x101186C0  # thin forwarding thunk, this->0x10

IMG_DESC_TYPE_OFF = fugc.FUGC_IMG_DESC_TYPE_OFF     # 0x4
IMG_DESC_WIDTH_OFF = fugc.FUGC_IMG_DESC_WIDTH_OFF   # 0xc
IMG_DESC_HEIGHT_OFF = fugc.FUGC_IMG_DESC_HEIGHT_OFF  # 0x10
IMG_DESC_STRIDE_OFF = 0x14       # read at 0x101fa62e/0x101fa68e, unlabelled
                                 # elsewhere in pakon_fugc.py -- consumed
                                 # only as a 3rd constructor scalar, never
                                 # itself used to compute a pixel address
                                 # in applyLut's own body (docs/74 §28).
IMG_DESC_DATA_OFF = 0x20         # applyLut's own [esi+0x20] read, matching
                                 # cna's own acquire() convention already
                                 # cited by pakon_full_colour_chain_golden.
                                 # BalanceAreaImageCall for the same field.


def build_impl(e: "shellg.Emu", *, mode: int, seed_rgb: np.ndarray,
               offsets: tuple[int, int, int]) -> int:
    """A real FUGC Impl object: ``+0x6140`` holds a REAL, non-identity
    per-channel apply LUT from the already-verified ``pakon_fugc.
    set_lut_info`` (not a placeholder/identity table), ``+0x60e8`` holds
    the real mode selector applyLut's own gate at ``0x101fa775`` reads.
    """
    impl = e.alloc(0x14200)
    lut = fugc.set_lut_info(seed_rgb, offsets)  # (4096, 3) int32
    blob = bytearray(3 * fugc.FUGC_N * 2)
    for c in range(3):
        for i in range(fugc.FUGC_N):
            struct.pack_into("<h", blob, c * 2 * fugc.FUGC_N + i * 2,
                             int(np.int16(lut[i, c])))
    e.uc.mem_write(impl + fugc.CAP_APPLY_LUT, bytes(blob))
    e.wi32(impl + 0x60E8, mode)
    return impl, lut


def build_image_descriptor(e: "shellg.Emu", *, width: int, height: int,
                           pixels: np.ndarray, image_type: int = 0):
    """A real AREA-image-shaped descriptor.  ``pixels`` is written as
    signed int16 (the RPD-12-range convention every other stage in this
    project's own ported chain already uses for FUGC/AREA pixel data).
    """
    desc = e.alloc(0x30)
    e.wi32(desc + IMG_DESC_TYPE_OFF, image_type)
    e.wi32(desc + IMG_DESC_WIDTH_OFF, width)
    e.wi32(desc + IMG_DESC_HEIGHT_OFF, height)
    e.wi32(desc + IMG_DESC_STRIDE_OFF, width)
    pix_bytes = np.asarray(pixels, dtype="<i2").tobytes()
    pix_ptr = e.alloc(len(pix_bytes), pix_bytes)
    e.wu32(desc + IMG_DESC_DATA_OFF, pix_ptr)
    return desc, pix_ptr, len(pix_bytes)


def install_unbound_thunk_stubs(e: "shellg.Emu") -> None:
    """Stub the raw-RVA unbound IAT-thunk imports this DLL's own PE loader
    apparently leaves unbound in this project's minimal PE mapping --
    the SAME class of fix ``trace_v47``-``v50`` (this project's own prior
    scratch passes, cited in docs/74 §24/§27) already catalogued and fixed
    for a completely different call path (the citras driver).  Not guessed
    here: this pass hit the exact same fault shape (``UC_ERR_FETCH_
    UNMAPPED`` at the raw import-table RVA) live, at
    ``InitializeCriticalSection``'s own thunk address, and confirmed the
    identity the same way -- reading the raw PE bytes at that exact file
    offset (the ``{hint,name}`` import-table entry sitting at the "unbound"
    address, same pattern documented in every prior pass's own comments).
    """
    import unicorn

    def stub_ret(addr: int, pop: int):
        page = addr & ~0xFFF
        try:
            e.uc.mem_map(page, 0x1000)
        except unicorn.UcError:
            pass  # already mapped (shared page with another thunk)
        e.uc.mem_write(addr, b"\xC3")
        e.hook(addr, lambda emu, a, _pop=pop: (0, _pop))

    # InitializeCriticalSection/EnterCriticalSection/LeaveCriticalSection/
    # DeleteCriticalSection -- ordinary __stdcall Win32 APIs (callee pops
    # their one LPCRITICAL_SECTION arg), true no-ops for a single-threaded
    # emulated trace with no real contention to guard against (same
    # rationale trace_v50's own comment already gives for the identical
    # four thunks).
    for addr in (0x00687DE2, 0x00687E22, 0x00687E0A, 0x00687DCA):
        stub_ret(addr, 4)

    # `memmove` -- an unbound raw-RVA MSVCR71 thunk, same class as the four
    # above, found live at fault eip=0x68bd3a; confirmed by reading the raw
    # PE file bytes at that exact offset (the same "{hint,name} import-
    # table entry sitting at the unbound thunk address" pattern every prior
    # unbound-thunk fix in this project's own history has used):
    # ``b"f\x00\xe6\x02memmove\x00..."`` -- 2-byte hint + ASCIIZ name.  A
    # real implementation (not a no-op) is used here rather than stubbed
    # blind, since a genuine ``memmove`` on real operand-construction data
    # is exactly the kind of real vendor behaviour this probe should not
    # silently discard -- cdecl ``void* memmove(dest, src, n)``, caller
    # cleans up (0 pop), returns ``dest``.
    MEMMOVE = 0x0068BD3A
    mm_page = MEMMOVE & ~0xFFF
    try:
        e.uc.mem_map(mm_page, 0x1000)
    except unicorn.UcError:
        pass
    e.uc.mem_write(MEMMOVE, b"\xC3")

    def memmove_stub(emu, a):
        dest, src, n = emu.r32(a), emu.r32(a + 4), emu.r32(a + 8)
        ret = emu.r32(a - 4)
        print(f"    [memmove dest={dest:#x} src={src:#x} n={n:#x} "
             f"called-from={ret:#x}]")
        if n:
            emu.uc.mem_write(dest, bytes(emu.uc.mem_read(src, n)))
        return dest, 0
    e.hook(MEMMOVE, memmove_stub)


def run_apply_lut(e: "shellg.Emu", *, impl: int, desc: int,
                  pix_ptr: int, pix_len: int) -> dict:
    status_out = e.alloc(4)
    writes: list[tuple[int, int, int]] = []

    def watch(uc, access, address, size, value, _u):
        writes.append((address, size, value))
        return True

    hook = e.uc.hook_add(UC_HOOK_MEM_WRITE, watch,
                         begin=pix_ptr, end=pix_ptr + pix_len - 1)
    result = {"writes": writes, "fault": None, "status_ok": None}
    try:
        eax = e.call(APPLY_LUT, [status_out, desc], ecx=impl)
        result["eax"] = eax
        result["status_ok"] = True
        result["status_word"] = e.r32(status_out) if status_out else None
    except RuntimeError as exc:
        result["fault"] = str(exc)
        result["status_ok"] = False
    finally:
        e.uc.hook_del(hook)
    return result


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else shellg.DEFAULT_DLL
    if not dll_path.exists():
        print(f"{dll_path} not found")
        return 2
    pe = dll_path.read_bytes()
    got = hashlib.md5(pe).hexdigest()
    print(f"== DLL {dll_path}  MD5={got} ==")
    if got != EXPECTED_MD5:
        print(f"  MD5 MISMATCH -- expected {EXPECTED_MD5}; refusing to "
             f"trust this copy")
        return 2
    print("  MD5 verified against docs/74's own citation.\n")

    # A real, non-identity apply LUT: seed = identity ramp, offset = a real
    # nonzero per-channel shift (docs/66's own "FUGC is very close to a
    # no-op for THIS specific reference file" note is about one particular
    # capture's own small aim deltas, not a structural constraint -- other
    # frames/rolls can and do have larger deltas; this probe uses one large
    # enough (200 codes) to make any pixel-buffer mutation unmistakable if
    # it happens, not to claim this is THE real aim value for any specific
    # frame).
    seed = np.tile(np.arange(fugc.FUGC_N, dtype=np.int32)[:, None], (1, 3))
    offsets = (200, -150, 75)

    WIDTH, HEIGHT = 8, 8
    rng = np.random.default_rng(20260814)
    pixels = rng.integers(100, 3900, size=(HEIGHT, WIDTH), dtype=np.int32)
    print(f"real pixel buffer ({WIDTH}x{HEIGHT}), first row: "
         f"{pixels[0].tolist()}")

    e = shellg.Emu(pe)
    install_unbound_thunk_stubs(e)
    impl, lut = build_impl(e, mode=0, seed_rgb=seed, offsets=offsets)
    print(f"real apply LUT built via pakon_fugc.set_lut_info "
         f"(offsets={offsets}); non-identity check: "
         f"lut[0]={lut[0].tolist()} (identity would be [0,0,0]) -- "
         f"channel 0's offset=200 prefix-fill makes lut[0..199]==200, "
         f"not 0..199")
    desc, pix_ptr, pix_len = build_image_descriptor(
        e, width=WIDTH, height=HEIGHT, pixels=pixels)

    print(f"\ncalling real applyLut (0x101fa5b0) directly: "
         f"ecx=impl={impl:#x} arg1=&status_out arg2=desc={desc:#x} "
         f"pixel buffer={pix_ptr:#x}..{pix_ptr + pix_len:#x}\n")
    res = run_apply_lut(e, impl=impl, desc=desc, pix_ptr=pix_ptr,
                        pix_len=pix_len)

    if res["status_ok"]:
        print(f"ran to completion (no Unicorn fault). eax={res['eax']:#x} "
             f"status_word={res.get('status_word')!r}")
        print(f"pixel-buffer writes observed: {len(res['writes'])}")
        if res["writes"]:
            print("DID write into the pixel buffer -- first few:")
            for addr, size, val in res["writes"][:16]:
                off = addr - pix_ptr
                print(f"  +{off:#x} size={size} val={val:#x}")
        else:
            print("did NOT write into the pixel buffer on this real, "
                 "full-completion run.")
    else:
        print(f"BLOCKED -- did not run to completion: {res['fault']}")
        print(f"pixel-buffer writes observed before the fault: "
             f"{len(res['writes'])}")
        if res["writes"]:
            print("(writes DID occur before the fault -- not zero either "
                 "way):")
            for addr, size, val in res["writes"][:16]:
                off = addr - pix_ptr
                print(f"  +{off:#x} size={size} val={val:#x}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
