#!/usr/bin/env python3
"""Golden harness: ``tools/pakon_framing.py``'s vendor helpers vs the real DLL.

WHAT IS UNDER TEST, AND WHAT IS NOT
-----------------------------------
``TLB.dll`` (md5 ``193d9b2ce0a4b77ae9b78262bd06c0fc``, PE base 0x10000000,
built 2007-04-18) is loaded into Unicorn and its **own machine code** is
executed on the same inputs the Python port is given. Nothing is
re-implemented on the emulator side; the reference is the vendor's
instructions.

Sixteen functions, every one with a real ``af``+``pdf`` boundary and its full
body read:

    fcn.10006870  0x10006870-0x10006922   per-line framing trace
    fcn.10005ce0  0x10005ce0-0x10005d1b   256-bin histogram of the trace
    fcn.10005d20  0x10005d20-0x1000613b   threshold choice + binarise
    fcn.10006140  0x10006140-0x10006308   ones -> run records + LoLim/HiLim bins
    fcn.10013960  0x10013960-0x10013978   film-edge-mark accessor
    fcn.10006310  0x10006310-0x100063c4   per-candidate film-edge validity test
    fcn.10006630  0x10006630-0x10006712   "is there room out there" predicate
    fcn.100064e0  0x100064e0-0x1000662d   sliding-window density search
    fcn.10006930  0x10006930-0x10006ade   phase 1, LookForNicePictures
    fcn.100063d0  0x100063d0-0x100064ce   phase 2, FramingLookInBetweenEnds
    fcn.10006ae0  0x10006ae0-0x10006c98   phase 3, LookAtEnd
    fcn.10006ca0  0x10006ca0-0x10006e60   phase 4, LookAtBeginning
    fcn.10006720  0x10006720-0x10006860   phase 5, FramingBlindlyPlacePictures
    fcn.10006e70  0x10006e70-0x100072b2   the four-phase cascade driver
    fcn.100072c0  0x100072c0-0x100079ae   the framing entry, search included
    fcn.100079c0  0x100079c0-0x10007f11   the roll caller: cascade vs blind

The last three are what make this more than a bag of parts: ``fcn.10006e70``
is the cascade as a whole, ``fcn.100072c0`` is the whole subsystem from a
per-line RGB summary to a placed frame list and a ``SCAN_WARNINGS`` word, and
``fcn.100079c0`` is the roll — it sizes the slot array, picks the cascade or
blind placement, and turns the slots into the ``CiPicLoc`` list the rest of
TLB.dll actually consumes. Each is diffed against the port's own single call.

``pakon_framing.FRAMING_PORTED`` is still ``False``, and for a reason that is
NOT "the arithmetic is unverified" any more — read the flag's own comment.
Short version: nothing in ``pakon_framing`` calls the verified chain
(``find_frames`` is still the Otsu heuristic), and nothing can feed it until
the vendor's own 8-bit per-line RGB summary is captured from real hardware.
The roll caller being ported changes neither of those.

HOW THE VENDOR IS HOSTED
------------------------
Stubbed, and nothing else is: the CRT (``fcn.100479f2`` malloc,
``fcn.10046d48`` free), the error reporter (``fcn.1001acd0``), MSVC's vector
destructor, the three ``DXCode.txt`` log calls, and five KERNEL32 imports
(``VirtualAlloc`` / ``VirtualLock`` / ``VirtualUnlock`` / ``VirtualFree`` /
``GetLastError``) patched into the IAT. The allocator is a bump allocator, the
log calls are no-ops, the rest return success. Every arithmetic instruction in
every function under test runs for real, including ``fcn.10005d20``'s x87.

``fcn.10006870`` makes two virtual calls through the object's own vtable
(``[vt+0x20]`` line count, ``[vt+0x34]`` mode); those go to stub addresses
this harness owns, which is how the mode-2 branch is exercised at all.
``fcn.100079c0`` adds three more (``[vt+0x10]`` margin units, ``[vt+0x24]``
line scale, ``[vt+0x80]`` -> the destination image, whose own ``[vt+0x20]``
is the row count) plus ``operator new``; it is also the first function here
with an SEH frame, so FS is given a real GDT descriptor. Its ``CiPicLoc``
construction, list insertion and list teardown are NOT stubbed — they are
``fcn.100245e0``, ``fcn.100244d0`` and ``fcn.100244a0`` running for real, and
the pictures are read back out of the list the vendor itself linked.

``fcn.10006930`` calls ``fcn.10006310`` only when ``this+0xca4`` is
non-zero. This harness drives the ``this+0xca4 == 0`` path — the path the
port models — and separately asserts that with ``this+0xca4 != 0`` and
``this+0xdc != 0`` (the "no edge data" bypass, 0x10006311) the vendor's
answer is unchanged, which is what makes the port's silence about
``fcn.10006310`` a documented restriction rather than a hidden difference.

MUTATION SELF-TESTS
-------------------
``--mutate`` deliberately breaks the port and reports each row as CAUGHT,
INERT (provably cannot change any output) or NOT CAUGHT. Run it; it is the
only thing that says the corpora are worth anything. Two rows are inert and
the harness says which and why.

It re-runs the whole comparison once per mutation, so ``run_all`` rewinds the
bump allocator on entry. Without that the heap runs dry partway down the list
and every later row reports CAUGHT because of a ``MemoryError`` rather than a
real difference — which would be a lie about coverage, and was one until the
rewind was added.

USAGE
-----
    python3 tools/ansel/python-pipeline/pakon_framing_golden.py
    python3 tools/ansel/python-pipeline/pakon_framing_golden.py --mutate
    python3 tools/ansel/python-pipeline/pakon_framing_golden.py --dll PATH
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

import numpy as np

_TOOLS = Path(__file__).resolve().parents[2]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import pakon_framing as pf  # noqa: E402

TLB_MD5 = "193d9b2ce0a4b77ae9b78262bd06c0fc"
DEFAULT_DLL_CANDIDATES = (
    "/tmp/pakon_re/TLB.dll",
    "/Users/guy/Downloads/Pakon Update 3/fx35install/System32/TLB.dll",
)

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x00200000
HEAP_ADDR = 0x30000000
HEAP_SIZE = 0x10000000
STUB_PAGE = 0x00100000
RET_MAGIC = 0x00200000
#: ``fcn.100079c0`` is the first function in this harness with an SEH frame:
#: 0x100079c7 reads ``fs:[0]`` and 0x100079ce writes it back. Unicorn's 32-bit
#: x86 has no ``FS_BASE`` register, so FS is pointed at a scratch TEB through a
#: real GDT descriptor. Nothing ever raises, so the chain is only ever pushed
#: and popped; what matters is that both accesses land on mapped memory.
GDT_ADDR = 0x0D000000
TEB_ADDR = 0x0D002000
FS_GDT_INDEX = 16
CODE_GDT_INDEX = 17
DATA_GDT_INDEX = 18

FN_TRACE = 0x10006870        # per-line framing scalar
FN_HIST = 0x10005CE0         # 256-bin histogram
FN_RUNS = 0x10006140         # ones -> runs + bins
FN_NICE = 0x10006930         # phase 1
FN_BETWEEN = 0x100063D0      # phase 2, FramingLookInBetweenEnds
FN_BLIND = 0x10006720        # phase 5, FramingBlindlyPlacePictures
FN_AT = 0x10013960           # film-edge-mark accessor
FN_VALID = 0x10006310        # per-candidate film-edge validity test
FN_GAPOK = 0x10006630        # "is there room out there" predicate
FN_BESTWIN = 0x100064E0      # sliding-window density search
FN_ATEND = 0x10006AE0        # phase 3, LookAtEnd
FN_ATBEG = 0x10006CA0        # phase 4, LookAtBeginning
FN_DRIVER = 0x10006E70       # the four-phase cascade driver
FN_THRESH = 0x10005D20       # threshold choice + binarise into the ones array
FN_ENTRY = 0x100072C0        # the framing entry: alloc, threshold search, cascade
FN_ROLL = 0x100079C0         # the roll caller: cascade-vs-blind, the CiPicLoc list

#: ``fcn.100072c0`` reaches KERNEL32 through the IAT. The PE is mapped flat
#: with no imports resolved, so these slots are overwritten with harness stub
#: addresses. The three buffers it wants are page-aligned scratch; nothing
#: about the framing arithmetic depends on where they land.
IAT_VIRTUALALLOC = 0x1005B05C
IAT_VIRTUALLOCK = 0x1005B060
IAT_GETLASTERROR = 0x1005B028
IAT_VIRTUALUNLOCK = 0x1005B064
IAT_VIRTUALFREE = 0x1005B0D8

STUB_VALLOC = STUB_PAGE + 0x300
STUB_VLOCK = STUB_PAGE + 0x400
STUB_GLE = STUB_PAGE + 0x500
STUB_VUNLOCK = STUB_PAGE + 0x600
STUB_VFREE = STUB_PAGE + 0x700
FN_MALLOC = 0x100479F2
FN_FREE = 0x10046D48
FN_ERRREPORT = 0x1001ACD0
#: The DXCode.txt logging trio ``fcn.10006720`` calls on its way out — open,
#: printf, close. Every placement and every ``tag = 9`` stamp is already in
#: the slot array before the first of them runs (0x100067c5 is past the whole
#: placement body), so stubbing them cannot move an answer under test.
FN_LOG_OPEN = 0x10047FB6
FN_LOG_PRINTF = 0x10047EFC
FN_LOG_CLOSE = 0x10047EAB
#: MSVC's vector-destructor helper. ``fcn.10006870`` calls it on the way out
#: to tear down ``this+0x6c`` — *after* every output value has been written,
#: so stubbing it cannot change the answer under test. Left as a no-op rather
#: than given a real allocator record, which is the only other option.
FN_VECTOR_DTOR = 0x10047A55
#: ``operator new``. A five-byte thunk into the CRT allocator, which has no
#: initialised heap under this harness, so it is stubbed onto the same bump
#: allocator ``FN_MALLOC`` uses. ``fcn.100079c0`` is the only function under
#: test that reaches it; every earlier check ran with it unhooked and is
#: unaffected (verified: the check count and every value are unchanged).
FN_NEW = 0x1004792F
#: ``fcn.10046d48`` is itself only ``jmp fcn.10046d4d``, and ``CiPicLoc``'s
#: scalar deleting destructor calls the inner label directly (0x10024680). So
#: the free stub has to sit on BOTH, or the picture-list teardown that
#: ``fcn.100079c0``'s ``operator new`` failure limb performs runs the real CRT
#: free on an uninitialised heap.
FN_FREE_INNER = 0x10046D4D

VT_LINES = STUB_PAGE + 0x100     # stands in for vtable[0x20]
VT_MODE = STUB_PAGE + 0x200      # stands in for vtable[0x34]
VT_MARGIN = STUB_PAGE + 0x800    # stands in for vtable[0x10]
VT_SCALE = STUB_PAGE + 0x900     # stands in for vtable[0x24]
VT_IMAGE = STUB_PAGE + 0xA00     # stands in for vtable[0x80]
VT_IMAGE_ROWS = STUB_PAGE + 0xB00  # the returned image's own vtable[0x20]

#: ``CiPicLoc``'s real vtable (0x10024613 stores it). The pre-existing picture
#: list this harness hands ``fcn.100079c0`` uses it too, so the list teardown
#: at 0x10007a52 runs the vendor's own destructor rather than a stub.
VT_CIPICLOC = 0x1006610C


# --------------------------------------------------------------------------
# Unicorn host
# --------------------------------------------------------------------------

def _align_up(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


def _gdt_entry(base: int, limit: int, access: int, flags: int) -> bytes:
    """One 8-byte x86 segment descriptor."""
    v = limit & 0xFFFF
    v |= (base & 0xFFFFFF) << 16
    v |= (access & 0xFF) << 40
    v |= ((limit >> 16) & 0xF) << 48
    v |= (flags & 0xF) << 52
    v |= ((base >> 24) & 0xFF) << 56
    return struct.pack("<Q", v)


class TlbHost:
    """Loads TLB.dll flat at its preferred base and calls into it."""

    def __init__(self, dll: Path):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
        from unicorn.x86_const import (UC_X86_REG_ESP, UC_X86_REG_ECX,
                                       UC_X86_REG_FS, UC_X86_REG_GDTR,
                                       UC_X86_REG_CS, UC_X86_REG_DS,
                                       UC_X86_REG_ES, UC_X86_REG_SS,
                                       UC_X86_REG_GS)
        self._REG_ESP = UC_X86_REG_ESP
        self._REG_ECX = UC_X86_REG_ECX
        pe = dll.read_bytes()
        self.md5 = hashlib.md5(pe).hexdigest()
        uc = self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        e = struct.unpack_from("<I", pe, 0x3C)[0]
        nsec = struct.unpack_from("<H", pe, e + 6)[0]
        optsz = struct.unpack_from("<H", pe, e + 20)[0]
        size_image = struct.unpack_from("<I", pe, e + 24 + 56)[0]
        uc.mem_map(IMAGE_BASE, _align_up(size_image))
        uc.mem_write(IMAGE_BASE, pe[:0x1000])
        sec = e + 24 + optsz
        for i in range(nsec):
            o = sec + i * 40
            _vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
            if rsz and raddr:
                uc.mem_write(IMAGE_BASE + va, pe[raddr:raddr + rsz])
        uc.mem_map(STACK_ADDR, STACK_SIZE)
        uc.mem_map(HEAP_ADDR, HEAP_SIZE)
        uc.mem_map(STUB_PAGE, 0x1000)
        uc.mem_map(RET_MAGIC, 0x1000)
        uc.mem_write(STUB_PAGE, b"\xc3" * 0x1000)
        uc.mem_write(RET_MAGIC, b"\xc3" * 0x1000)
        # FS -> a scratch TEB, for fcn.100079c0's SEH prologue/epilogue.
        # Loading GDTR at all means every other selector has to be described
        # too — the flat CS/DS/ES/SS/GS Unicorn starts with are cached
        # descriptors that a real GDT replaces.
        uc.mem_map(GDT_ADDR, 0x4000)
        uc.reg_write(UC_X86_REG_GDTR, (0, GDT_ADDR, 0x1000 - 1, 0))
        uc.mem_write(GDT_ADDR + FS_GDT_INDEX * 8,
                     _gdt_entry(TEB_ADDR, 0xFFFFF, 0x92, 0xC))
        uc.mem_write(GDT_ADDR + CODE_GDT_INDEX * 8,
                     _gdt_entry(0, 0xFFFFF, 0x9A, 0xC))
        uc.mem_write(GDT_ADDR + DATA_GDT_INDEX * 8,
                     _gdt_entry(0, 0xFFFFF, 0x92, 0xC))
        uc.reg_write(UC_X86_REG_CS, CODE_GDT_INDEX << 3)
        for reg in (UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS,
                    UC_X86_REG_GS):
            uc.reg_write(reg, DATA_GDT_INDEX << 3)
        uc.reg_write(UC_X86_REG_FS, FS_GDT_INDEX << 3)
        self.bump = HEAP_ADDR + 0x1000
        self.errors = 0
        self.n_lines = 0
        self.mode = 0
        self.line_scale = 1
        self.margin_units = 0
        self.image_rows = 0
        self.image_obj = 0
        self.malloc_fail_once = False
        self.new_calls = 0
        self.new_fail_at = None
        self.hooks = {
            FN_MALLOC: self._malloc,
            FN_NEW: self._new,
            FN_FREE: self._free,
            FN_FREE_INNER: self._free,
            FN_ERRREPORT: self._errreport,
            FN_VECTOR_DTOR: self._vector_dtor,
            FN_LOG_OPEN: self._log_noop,
            FN_LOG_PRINTF: self._log_noop,
            FN_LOG_CLOSE: self._log_noop,
            STUB_VALLOC: self._virtual_alloc,
            STUB_VLOCK: self._ret_true_8,
            STUB_GLE: self._get_last_error,
            STUB_VUNLOCK: self._ret_true_8,
            STUB_VFREE: self._ret_true_12,
            VT_LINES: self._vt_lines,
            VT_MODE: self._vt_mode,
            VT_MARGIN: self._vt_margin,
            VT_SCALE: self._vt_scale,
            VT_IMAGE: self._vt_image,
            VT_IMAGE_ROWS: self._vt_image_rows,
        }
        for slot, stub in ((IAT_VIRTUALALLOC, STUB_VALLOC),
                           (IAT_VIRTUALLOCK, STUB_VLOCK),
                           (IAT_GETLASTERROR, STUB_GLE),
                           (IAT_VIRTUALUNLOCK, STUB_VUNLOCK),
                           (IAT_VIRTUALFREE, STUB_VFREE)):
            uc.mem_write(slot, struct.pack("<I", stub))
        uc.hook_add(UC_HOOK_CODE, self._on_code)

    # -- stubs ----------------------------------------------------------
    def _malloc(self):
        if self.malloc_fail_once:
            self.malloc_fail_once = False
            self.ret(0, 0)
        else:
            self.ret(0, self.alloc(self.arg(0)))

    def _new(self):
        """``operator new``, cdecl, one argument. Fails on demand.

        ``fcn.100079c0`` builds every ``CiPicLoc`` through this, and has a
        distinct error limb per geometry model for a NULL return (0x10007cca
        and 0x10007eeb). Failing the k-th call is how those limbs get driven
        against the real code instead of being declared unreachable.
        """
        k, self.new_calls = self.new_calls, self.new_calls + 1
        if self.new_fail_at is not None and k == self.new_fail_at:
            self.ret(0, 0)
        else:
            self.ret(0, self.alloc(self.arg(0)))

    def _free(self):
        self.ret(0, 0)

    def _errreport(self):
        self.errors += 1
        self.ret(0x18, 0)

    def _vector_dtor(self):
        self.ret(0x10, 0)

    def _log_noop(self):
        """cdecl — the caller cleans, so pop nothing but the return address."""
        self.ret(0, 0)

    def _virtual_alloc(self):
        """VirtualAlloc(lpAddress, dwSize, flAllocationType, flProtect).

        PAGE-GRANULAR AND ZERO-FILLED, and that is load-bearing rather than
        tidiness. ``fcn.100064e0``'s window search reads ``data[start + i + j]``
        for ``j < width`` and ``i < pitch - width``, i.e. up to ``pitch``
        int32s PAST the end of the ones buffer ``fcn.100072c0`` sized at
        exactly ``4 * n_lines``. On real Windows that overrun lands in the
        zero-filled tail of the committed page and reads 0. With a packed bump
        allocator it lands in the previous case's data, and the vendor's answer
        then depends on emulator history — two rolls in this corpus changed
        their frame count between a fresh host and a shared one before this
        stub was made page-granular. Matching VirtualAlloc's real granularity
        is what makes those rolls deterministic and comparable at all.
        """
        size = self.arg(1)
        self.bump = (self.bump + 0xFFF) & ~0xFFF
        base = self.alloc(_align_up(max(int(size), 1)))
        self.bump = (self.bump + 0xFFF) & ~0xFFF
        self.ret(16, base)

    def _ret_true_8(self):
        self.ret(8, 1)

    def _ret_true_12(self):
        self.ret(12, 1)

    def _get_last_error(self):
        self.ret(0, 0)

    def _vt_lines(self):
        self.ret(0, self.n_lines)

    def _vt_mode(self):
        self.ret(0, self.mode)

    def _vt_margin(self):
        self.ret(0, self.margin_units)

    def _vt_scale(self):
        self.ret(0, self.line_scale)

    def _vt_image(self):
        self.ret(0, self.image_obj)

    def _vt_image_rows(self):
        self.ret(0, self.image_rows)

    def _on_code(self, uc, address, size, user):
        fn = self.hooks.get(address)
        if fn is not None:
            fn()

    # -- memory / ABI ---------------------------------------------------
    def alloc(self, n: int) -> int:
        n = max(int(n), 1)
        a = (self.bump + 15) & ~15
        self.bump = a + n + 64
        if self.bump >= HEAP_ADDR + HEAP_SIZE:
            raise MemoryError("Unicorn TLB heap exhausted")
        self.uc.mem_write(a, b"\x00" * n)
        return a

    def alloc_i32(self, values) -> int:
        v = list(int(x) for x in values)
        a = self.alloc(4 * max(len(v), 1))
        if v:
            self.uc.mem_write(a, struct.pack("<%di" % len(v), *v))
        return a

    def read_i32(self, addr: int, n: int):
        return list(struct.unpack("<%di" % n, self.uc.mem_read(addr, 4 * n)))

    def read_u32(self, addr: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def arg(self, i: int) -> int:
        esp = self.uc.reg_read(self._REG_ESP)
        return struct.unpack("<I", self.uc.mem_read(esp + 4 + 4 * i, 4))[0]

    def ret(self, popbytes: int, eax: int = 0) -> None:
        from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP
        esp = self.uc.reg_read(self._REG_ESP)
        r = struct.unpack("<I", self.uc.mem_read(esp, 4))[0]
        self.uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
        self.uc.reg_write(self._REG_ESP, esp + 4 + popbytes)
        self.uc.reg_write(UC_X86_REG_EIP, r)

    #: How much stack to scrub below the frame before every call.
    #: ``fcn.100072c0``'s frame is 0x44c bytes and everything it calls nests
    #: inside that, so 0x8000 covers the deepest chain with room to spare.
    STACK_SCRUB = 0x8000

    def call(self, addr: int, args, ecx: int | None = None) -> int:
        """Call into the DLL with a ZEROED stack frame.

        The zeroing is not hygiene, it is what makes the reference well
        defined. ``fcn.100072c0`` keeps its ``bins`` block as a stack local and
        hands its address to ``fcn.10006140``, which on its refusal limb
        (0x10006185, ``ones[first] == n_runs``) returns WITHOUT writing it. On
        an input where the very first extraction refuses — and this corpus has
        three — the threshold search then steers on whatever the caller left on
        the stack. Measured, not theorised: with a dirty stack the same roll
        returned 0, 11 and 12 frames on three otherwise identical runs, and
        flipped the moment a single unrelated call had run first.

        So on those inputs the vendor has no single right answer; it has an
        answer per caller. This harness pins the only defensible one — the
        zero-initialised reading, which is what the port computes — and says
        out loud that it is a choice. A real F-135 could differ.
        """
        from unicorn.x86_const import UC_X86_REG_EAX
        uc = self.uc
        esp = STACK_ADDR + STACK_SIZE - 0x20000
        uc.mem_write(esp - self.STACK_SCRUB, b"\x00" * self.STACK_SCRUB)
        for v in reversed(args):
            esp -= 4
            uc.mem_write(esp, struct.pack("<I", int(v) & 0xFFFFFFFF))
        esp -= 4
        uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
        uc.reg_write(self._REG_ESP, esp)
        if ecx is not None:
            uc.reg_write(self._REG_ECX, ecx)
        uc.emu_start(addr, RET_MAGIC, count=400_000_000)
        eax = uc.reg_read(UC_X86_REG_EAX)
        return struct.unpack("<i", struct.pack("<I", eax))[0]

    # -- the four vendor entry points -----------------------------------
    def make_object(self, ca4: int = 0, dc: int = 0, roll: bool = False) -> int:
        """A ``this`` big enough for every field the framing code touches.

        ``roll=True`` widens the vtable and wires the three extra slots only
        ``fcn.100079c0`` calls. The default is byte-for-byte the object every
        other check in this harness has always been given, allocation sizes
        included, so adding the roll caller cannot move an earlier answer.
        """
        this = self.alloc(0x8000)
        vt = self.alloc(0x100 if roll else 0x80)
        self.uc.mem_write(vt + 0x20, struct.pack("<I", VT_LINES))
        self.uc.mem_write(vt + 0x34, struct.pack("<I", VT_MODE))
        if roll:
            self.uc.mem_write(vt + 0x10, struct.pack("<I", VT_MARGIN))
            self.uc.mem_write(vt + 0x24, struct.pack("<I", VT_SCALE))
            self.uc.mem_write(vt + 0x80, struct.pack("<I", VT_IMAGE))
        self.uc.mem_write(this, struct.pack("<I", vt))
        self.uc.mem_write(this + 0xCA4, struct.pack("<I", ca4))
        self.uc.mem_write(this + 0xDC, struct.pack("<I", dc))
        return this

    def vendor_trace(self, rgb_u8: np.ndarray, mode: int) -> list[int]:
        n = int(rgb_u8.shape[0])
        this = self.make_object()
        src = self.alloc(3 * n + 16)
        self.uc.mem_write(src, np.ascontiguousarray(
            rgb_u8.astype(np.uint8)).tobytes())
        # this+0x6c is freed by the function; give it a pointer whose -4 slot
        # holds a plausible element count so the vendor's own array teardown
        # (fcn.10047a55) has something sane to read.
        holder = self.alloc(3 * n + 32)
        self.uc.mem_write(holder, struct.pack("<I", n))
        self.uc.mem_write(holder + 4, np.ascontiguousarray(
            rgb_u8.astype(np.uint8)).tobytes())
        self.uc.mem_write(this + 0x6C, struct.pack("<I", holder + 4))
        out = self.alloc(4 * n + 64)
        self.n_lines = n
        self.mode = mode
        self.call(FN_TRACE, [out], ecx=this)
        return self.read_i32(out, n)

    def vendor_hist(self, trace, first: int, last: int) -> list[int]:
        hist = self.alloc(256 * 4)
        tr = self.alloc_i32(trace)
        self.call(FN_HIST, [hist, tr, first, last])
        return self.read_i32(hist, 256)

    def vendor_runs(self, ones, first: int, last: int, width: int):
        this = self.make_object()
        a_ones = self.alloc_i32(ones)
        a_pp = self.alloc(4)
        a_bins = self.alloc(12)
        r = self.call(FN_RUNS, [a_ones, a_pp, a_bins, first, last, width],
                      ecx=this)
        bins = self.read_i32(a_bins, 3)
        recs = []
        if r > 0:
            base = self.read_u32(a_pp)
            for i in range(r):
                recs.append(self.read_i32(base + 12 * i, 3))
        return r, bins, recs

    def vendor_runs_shared(self, seq, width):
        """``fcn.10006140`` called repeatedly on ONE bins block and ``pp``.

        The refusal limb (0x10006185) returns before writing either output, so
        a shared block keeps its previous contents. A per-call freshly-zeroed
        block — which is what every other check here uses — cannot tell that
        apart from "writes zeros", and the port had it wrong.
        """
        this = self.make_object()
        a_pp = self.alloc(4)
        a_bins = self.alloc(12)
        out = []
        live = 0        # records the block is known to hold right now
        for ones, first, last in seq:
            a_ones = self.alloc_i32(ones)
            r = self.call(FN_RUNS, [a_ones, a_pp, a_bins, first, last, width],
                          ecx=this)
            if r > 0:
                live = r
            # Read through the CURRENT *pp using the count the block is known
            # to hold, not the call's return. On a refusal the vendor never
            # touched *pp, so this reads the previous call's table back — which
            # is precisely the claim under test.
            recs = []
            base = self.read_u32(a_pp)
            if base:
                for i in range(live):
                    recs.append(self.read_i32(base + 12 * i, 3))
            out.append((r, self.read_i32(a_bins, 3), recs))
        return out

    def vendor_nice(self, records, n_runs: int, pitch: int, width: int,
                    left_bound: int, right_bound: int, n_slots: int,
                    ca4: int = 0, dc: int = 0, edges=()):
        this = self.make_object(ca4=ca4, dc=dc)
        self.uc.mem_write(this + 0x8B4, struct.pack("<i", len(edges)))
        if edges:
            self.uc.mem_write(this + 0x8B8, struct.pack(
                "<%di" % len(edges), *[int(v) for v in edges]))
        flat = []
        for rec in records:
            flat.extend(int(v) for v in rec)
        a_recs = self.alloc_i32(flat) if flat else self.alloc(12)
        a_out = self.alloc(12 * n_slots + 64)
        a_count = self.alloc(4)
        self.call(FN_NICE, [a_recs, a_out, pitch, width, n_runs, a_count,
                            left_bound, right_bound], ecx=this)
        count = self.read_i32(a_count, 1)[0]
        placements = {}
        for i in range(n_slots):
            left, w, _tag = self.read_i32(a_out + 12 * i, 3)
            if left or w:
                placements[i] = (left, w)
        return placements, count

    def _write_slots(self, slots):
        flat = []
        for s in slots:
            flat.extend(int(v) for v in s)
        return self.alloc_i32(flat)

    def vendor_between(self, slots, pitch: int, width: int,
                       first: int, last: int):
        """``fcn.100063d0`` — stdcall, six args, no ``this``.

        The slot array is read AND written in place, so the whole array comes
        back out, not just a placement dict.
        """
        n = len(slots)
        a_slots = self._write_slots(slots)
        a_count = self.alloc(4)
        self.call(FN_BETWEEN, [a_slots, pitch, width, a_count, first, last])
        count = self.read_i32(a_count, 1)[0]
        out = [self.read_i32(a_slots + 12 * i, 3) for i in range(n)]
        return out, count

    def vendor_at(self, edges, i: int) -> int:
        """``fcn.10013960`` on a container laid out the way ``this+0x78`` is."""
        this = self.make_object()
        self.uc.mem_write(this + 0x8B4, struct.pack("<i", len(edges)))
        if edges:
            self.uc.mem_write(this + 0x8B8, struct.pack(
                "<%di" % len(edges), *[int(v) for v in edges]))
        return self.call(FN_AT, [i], ecx=this + 0x78)

    def vendor_valid(self, rec, edges, dc: int = 0):
        """``fcn.10006310`` — returns (verdict, record-after), record mutated."""
        this = self.make_object(dc=dc)
        self.uc.mem_write(this + 0x8B4, struct.pack("<i", len(edges)))
        if edges:
            self.uc.mem_write(this + 0x8B8, struct.pack(
                "<%di" % len(edges), *[int(v) for v in edges]))
        a_rec = self.alloc_i32(rec)
        r = self.call(FN_VALID, [a_rec], ecx=this)
        return r, self.read_i32(a_rec, 3)

    def vendor_gapok(self, records, n_runs, a, b, slack) -> int:
        flat = []
        for rec in records:
            flat.extend(int(v) for v in rec)
        a_recs = self.alloc_i32(flat) if flat else self.alloc(12)
        return self.call(FN_GAPOK, [a_recs, n_runs, a, b, slack])

    def vendor_bestwin(self, win, n, data, start):
        """``fcn.100064e0`` — returns (best offset, the sums it wrote)."""
        this = self.make_object()
        a_data = self.alloc_i32(data)
        a_sums = self.alloc(4 * max(n, 1) + 64)
        r = self.call(FN_BESTWIN, [win, n, a_data, a_sums, start], ecx=this)
        return r, self.read_i32(a_sums, max(n, 0))

    def vendor_thresh(self, hist, trace, first, last, forced, unused=0):
        """``fcn.10005d20`` — returns (threshold, ones-array-after)."""
        n = len(trace)
        a_ones = self.alloc_i32([0] * max(n, 1))
        a_hist = self.alloc_i32(list(hist) + [0] * max(0, 256 - len(hist)))
        a_trace = self.alloc_i32(trace)
        r = self.call(FN_THRESH, [a_ones, a_hist, a_trace, unused, first,
                                  last, forced])
        return r, self.read_i32(a_ones, n)

    def vendor_entry(self, rgb_u8, n_slots, pitch, width, first, tail_margin,
                     skip_gapok, mode=0, ca4=0, edges=(), dc=0):
        """``fcn.100072c0`` — returns (retval, slots-after, warn)."""
        n = int(rgb_u8.shape[0])
        this = self.make_object(ca4=ca4, dc=dc)
        self._put_edges(this, edges)
        self.uc.mem_write(this + 0x6CA8, struct.pack("<i", 0))
        self.uc.mem_write(this + 0x6CBC, struct.pack("<i", 0))
        holder = self.alloc(3 * n + 32)
        self.uc.mem_write(holder, struct.pack("<I", n))
        self.uc.mem_write(holder + 4, np.ascontiguousarray(
            rgb_u8.astype(np.uint8)).tobytes())
        self.uc.mem_write(this + 0x6C, struct.pack("<I", holder + 4))
        a_slots = self.alloc(12 * n_slots + 64)
        self.n_lines = n
        self.mode = mode
        r = self.call(FN_ENTRY, [skip_gapok, n_slots, a_slots, pitch, width,
                                 first, tail_margin], ecx=this)
        out = [self.read_i32(a_slots + 12 * i, 3) for i in range(n_slots)]
        warn = struct.unpack("<i", self.uc.mem_read(this + 0x6CA8, 4))[0]
        return r, out, warn

    def _put_edges(self, this, edges):
        self.uc.mem_write(this + 0x8B4, struct.pack("<i", len(edges)))
        if edges:
            self.uc.mem_write(this + 0x8B8, struct.pack(
                "<%di" % len(edges), *[int(v) for v in edges]))

    def vendor_driver(self, slots, data, records, n_runs, left_bound,
                      right_bound, n_slots, pitch, width, skip_gapok,
                      ca4=0, edges=(), dc=0):
        """``fcn.10006e70`` — eleven stdcall args + this.

        Returns (retval, slots-after, count, this+0x6ca8).
        """
        this = self.make_object(ca4=ca4, dc=dc)
        self._put_edges(this, edges)
        self.uc.mem_write(this + 0x6CA8, struct.pack("<i", 0))
        self.uc.mem_write(this + 0x6CBC, struct.pack("<i", 0))
        a_slots = self._write_slots(slots)
        a_data = self.alloc_i32(data)
        a_sums = self.alloc(4 * max(pitch - width, 1) + 256)
        flat = []
        for rec in records:
            flat.extend(int(v) for v in rec)
        a_recs = self.alloc_i32(flat) if flat else self.alloc(12)
        r = self.call(FN_DRIVER, [a_data, a_sums, a_recs, n_runs, left_bound,
                                  right_bound, a_slots, n_slots, pitch, width,
                                  skip_gapok], ecx=this)
        out = [self.read_i32(a_slots + 12 * i, 3) for i in range(len(slots))]
        warn = struct.unpack("<i", self.uc.mem_read(this + 0x6CA8, 4))[0]
        return r, out, warn

    def vendor_phase34(self, addr, slots, data, records, n_runs, pitch, width,
                       count_in, start, bound, skip_gapok, edges=(), dc=0):
        """``fcn.10006ae0`` / ``fcn.10006ca0`` — eleven stdcall args + this."""
        this = self.make_object(dc=dc)
        self.uc.mem_write(this + 0x8B4, struct.pack("<i", len(edges)))
        if edges:
            self.uc.mem_write(this + 0x8B8, struct.pack(
                "<%di" % len(edges), *[int(v) for v in edges]))
        a_slots = self._write_slots(slots)
        a_data = self.alloc_i32(data)
        a_sums = self.alloc(4 * max(pitch - width, 1) + 256)
        flat = []
        for rec in records:
            flat.extend(int(v) for v in rec)
        a_recs = self.alloc_i32(flat) if flat else self.alloc(12)
        a_count = self.alloc_i32([count_in])
        r = self.call(addr, [a_slots, a_data, a_sums, a_recs, n_runs, pitch,
                             width, a_count, start, bound, skip_gapok],
                      ecx=this)
        out = [self.read_i32(a_slots + 12 * i, 3) for i in range(len(slots))]
        return r, out, self.read_i32(a_count, 1)[0]

    def vendor_blind(self, n_slots: int, pitch: int, width: int,
                     n_lines: int, count_in: int = 0):
        """``fcn.10006720`` — thiscall, three args; line count via [vt+0x20]."""
        this = self.make_object()
        self.uc.mem_write(this + 0xC9C, struct.pack("<i", int(count_in)))
        a_slots = self.alloc(12 * n_slots + 64)
        self.n_lines = n_lines
        self.call(FN_BLIND, [a_slots, pitch, width], ecx=this)
        count = struct.unpack("<i", self.uc.mem_read(this + 0xC9C, 4))[0]
        out = [self.read_i32(a_slots + 12 * i, 3) for i in range(n_slots)]
        return out, count

    def _make_picloc_list(self, pictures):
        """A ``CiPicLoc`` chain laid out the way ``fcn.100244d0`` builds one.

        Real ``CiPicLoc`` vtable, so 0x10007a52's ``[vt+8]`` teardown of a
        pre-existing list runs the vendor's own destructor chain
        (``fcn.100244a0`` -> ``fcn.10024670`` -> ``fcn.10024530`` + free).
        """
        nodes = []
        for pic in pictures:
            a = self.alloc(0x24)
            self.uc.mem_write(a, struct.pack("<I", VT_CIPICLOC))
            self.uc.mem_write(a + 0x0C, struct.pack("<6i", *[int(v)
                                                             for v in pic]))
            nodes.append(a)
        for i, a in enumerate(nodes):
            nxt = nodes[i + 1] if i + 1 < len(nodes) else 0
            prv = nodes[i - 1] if i else 0
            self.uc.mem_write(a + 4, struct.pack("<II", nxt, prv))
        return nodes[0] if nodes else 0

    def _read_picloc_list(self, head):
        out = []
        seen = set()
        while head:
            if head in seen or len(out) > 4096:
                raise RuntimeError("CiPicLoc list is cyclic")
            seen.add(head)
            out.append(tuple(struct.unpack(
                "<6i", self.uc.mem_read(head + 0x0C, 24))))
            head = self.read_u32(head + 4)
        return out

    def vendor_roll(self, rgb_u8, *, skip_gapok, place_blindly, no_tail_margin,
                    line_scale, image_rows, margin_units, pitch_raw, width_raw,
                    margin_divisor, crop, frame_bottom, end_anchored,
                    pictures_in=(), count_in=0, warn_in=0, mode=0, ca4=0,
                    edges=(), dc=0, malloc_fails=False, new_fails_at=None):
        """``fcn.100079c0`` — thiscall, three args, ``ret 0xc``.

        Returns ``(retval, pictures, count, warn, errors)``.
        """
        n = int(rgb_u8.shape[0])
        this = self.make_object(ca4=ca4, dc=dc, roll=True)
        self._put_edges(this, edges)
        holder = self.alloc(3 * n + 32)
        self.uc.mem_write(holder, struct.pack("<I", n))
        self.uc.mem_write(holder + 4, np.ascontiguousarray(
            rgb_u8.astype(np.uint8)).tobytes())
        self.uc.mem_write(this + 0x6C, struct.pack("<I", holder + 4))
        self.uc.mem_write(this + 0x70, struct.pack(
            "<I", self._make_picloc_list(pictures_in)))
        self.uc.mem_write(this + 0xC6C, struct.pack("<i", int(margin_divisor)))
        self.uc.mem_write(this + 0xC70, struct.pack("<i", int(pitch_raw)))
        self.uc.mem_write(this + 0xC74, struct.pack("<i", int(width_raw)))
        self.uc.mem_write(this + 0xC80, struct.pack("<i", int(frame_bottom)))
        self.uc.mem_write(this + 0xC88, struct.pack(
            "<4i", *[int(v) for v in crop]))
        self.uc.mem_write(this + 0xC98, struct.pack("<i", int(end_anchored)))
        self.uc.mem_write(this + 0xC9C, struct.pack("<i", int(count_in)))
        self.uc.mem_write(this + 0x6CA8, struct.pack("<i", int(warn_in)))
        self.uc.mem_write(this + 0x6CBC, struct.pack("<i", 0))
        # the image object [vt+0x80] hands back, whose own [vt+0x20] is the
        # row count every picture's bottom edge is clamped against
        img = self.alloc(0x40)
        imgvt = self.alloc(0x40)
        self.uc.mem_write(imgvt + 0x20, struct.pack("<I", VT_IMAGE_ROWS))
        self.uc.mem_write(img, struct.pack("<I", imgvt))
        self.image_obj = img
        self.image_rows = int(image_rows)
        self.line_scale = int(line_scale)
        self.margin_units = int(margin_units)
        self.n_lines = n
        self.mode = mode
        self.malloc_fail_once = bool(malloc_fails)
        self.new_calls = 0
        self.new_fail_at = new_fails_at
        before = self.errors
        try:
            r = self.call(FN_ROLL, [skip_gapok, place_blindly, no_tail_margin],
                          ecx=this)
        finally:
            self.malloc_fail_once = False
            self.new_fail_at = None
        pics = self._read_picloc_list(self.read_u32(this + 0x70))
        count = struct.unpack("<i", self.uc.mem_read(this + 0xC9C, 4))[0]
        warn = struct.unpack("<i", self.uc.mem_read(this + 0x6CA8, 4))[0]
        return r, pics, count, warn, self.errors - before


# --------------------------------------------------------------------------
# Corpora
# --------------------------------------------------------------------------

def _rng(seed: int):
    return np.random.default_rng(seed)


def ones_corpus():
    """Real-shaped and adversarial ones arrays: (ones, first, last, width)."""
    cases = []
    # 1. textbook roll: six clean frames at a 200-line pitch, 190 wide
    o = np.zeros(1400, dtype=np.int32)
    for k in range(6):
        o[40 + 200 * k: 40 + 200 * k + 190] = 1
    cases.append(("clean-6", o, 0, 1399, 190))
    # 2. a missed gap: frames 2 and 3 merge into one run
    o = o.copy()
    o[40 + 200 * 2 + 190: 40 + 200 * 3] = 1
    cases.append(("merged-pair", o, 0, 1399, 190))
    # 3. run starting exactly at `first` (hits the return-0 quirk)
    o = np.zeros(500, dtype=np.int32)
    o[0:190] = 1
    cases.append(("run-at-first-only", o, 0, 499, 190))
    o = o.copy()
    o[300:490] = 1
    cases.append(("run-at-first-plus-one", o, 0, 499, 190))
    # 4. all ones / all zeros
    cases.append(("all-zero", np.zeros(300, dtype=np.int32), 0, 299, 100))
    cases.append(("all-one", np.ones(300, dtype=np.int32), 0, 299, 100))
    # 5. boundary lengths: exactly LoLim and exactly HiLim
    lo, hi = pf.vendor_limits(190)
    o = np.zeros(1200, dtype=np.int32)
    o[50:50 + lo] = 1
    o[400:400 + hi] = 1
    o[800:800 + (lo + hi) // 2] = 1
    cases.append(("exact-limits", o, 0, 1199, 190))
    # 6. single-line runs and 1-line gaps
    o = np.zeros(400, dtype=np.int32)
    o[1::2] = 1
    cases.append(("comb", o, 0, 399, 4))
    # 7. window not the whole array
    o = np.zeros(1000, dtype=np.int32)
    o[100:290] = 1
    o[400:590] = 1
    o[700:890] = 1
    cases.append(("window-inside", o, 80, 900, 190))
    cases.append(("window-cuts-run", o, 150, 500, 190))
    # 8. randomised, several densities and block sizes
    for seed in range(16):
        r = _rng(seed)
        n = int(r.integers(60, 3000))
        blk = int(r.integers(1, 120))
        p = float(r.uniform(0.1, 0.9))
        raw = (r.random((n + blk - 1) // blk) < p).astype(np.int32)
        o = np.repeat(raw, blk)[:n]
        first = int(r.integers(0, max(1, n // 4)))
        last = int(r.integers(first, n))
        width = int(r.integers(1, max(2, n // 3)))
        cases.append((f"random-{seed}", o, first, last, width))
    return cases


def nice_corpus():
    """(records, n_runs, pitch, width, left_bound, right_bound, n_slots)."""
    cases = []
    # derived from the ones corpus, so the phase-1 inputs are ones the vendor
    # run extractor really produces
    cases.append(("hand-single",
                  [[100, 190, 0]], 1, 200, 190, 0, 5000, 200))
    cases.append(("hand-double",
                  [[100, 385, 0]], 1, 200, 190, 0, 5000, 200))
    cases.append(("hand-short", [[100, 5, 0]], 1, 200, 190, 0, 5000, 200))
    cases.append(("hand-long", [[100, 4000, 0]], 1, 200, 190, 0, 5000, 200))
    # clamps
    cases.append(("clamp-left", [[10, 190, 0]], 1, 200, 190, 60, 5000, 200))
    cases.append(("clamp-right", [[4900, 190, 0]], 1, 200, 190, 0, 4950, 200))
    cases.append(("clamp-both", [[10, 190, 0]], 1, 200, 190, 60, 300, 200))
    # exact boundary cases: left lands exactly on left_bound, and the frame
    # ends exactly on right_bound. Both comparisons in the vendor are one-sided
    # (``jg`` @ 0x100069c3 and ``jge`` @ 0x100069df), so without these two the
    # off-by-one mutations on either clamp are unobservable.
    cases.append(("clamp-left-exact", [[100, 190, 0]], 1, 200, 190,
                  100, 5000, 200))
    cases.append(("clamp-right-exact", [[100, 190, 0]], 1, 200, 190,
                  0, 290, 200))
    cases.append(("clamp-right-exact-plus1", [[100, 190, 0]], 1, 200, 190,
                  0, 291, 200))
    # negative slack: run shorter than width but still inside the window
    lo, _hi = pf.vendor_limits(190)
    cases.append(("negative-slack",
                  [[100, lo + 1, 0]], 1, 200, 190, 0, 5000, 200))
    # many runs, colliding slots
    recs = [[40 + 200 * k, 190, 0] for k in range(6)]
    cases.append(("six-frames", recs, 6, 200, 190, 0, 5000, 200))
    recs2 = [[40 + 200 * k, 385, 0] for k in range(4)]
    cases.append(("four-doubles", recs2, 4, 200, 190, 0, 5000, 200))
    # randomised. Lengths are deliberately biased onto and around the two
    # acceptance windows — a uniform draw over 1..3*width almost never lands
    # inside a 20%-wide band, so an unbiased corpus would exercise the two
    # placement branches a handful of times in a hundred cases.
    for seed in range(40):
        r = _rng(1000 + seed)
        pitch = int(r.integers(4, 400))
        width = int(r.integers(2, pitch + 40))
        lo, hi = pf.vendor_limits(width)
        n = int(r.integers(1, 12))
        recs = []
        pos = int(r.integers(0, 500))
        for _ in range(n):
            pick = r.integers(0, 4)
            if pick == 0:
                length = int(r.integers(max(1, lo - 2), hi + 3))
            elif pick == 1:
                length = int(r.integers(max(1, lo + pitch - 2),
                                        hi + pitch + 3))
            elif pick == 2:
                length = int(r.integers(1, max(2, 3 * width + 5)))
            else:
                length = int(r.choice([lo, lo + 1, hi - 1, hi,
                                       lo + pitch, hi + pitch]))
            recs.append([pos, max(1, length), 0])
            pos += int(r.integers(1, 3 * pitch + 5))
        lb = int(r.integers(-50, 200))
        rb = int(r.integers(pos, pos + 4000))
        cases.append((f"random-{seed}", recs, n, pitch, width, lb, rb,
                      max(2, 2 * (pos + 4000) // pitch + 8)))
    return cases


def _slots_from(entries, pitch, n_slots):
    """Lay ``(left, width)`` pairs into a slot array the vendor's own way.

    Phase 1 indexes its output by ``(2*left)/pitch`` (0x100069c8), so a phase-2
    input that did not come from that rule would not be a shape the vendor can
    actually produce. Entries whose slot collides or falls outside the array
    are dropped rather than clamped.
    """
    slots = [[0, 0, 0] for _ in range(n_slots)]
    for left, width in entries:
        idx = pf._cdiv(2 * int(left), pitch)
        if 0 <= idx < n_slots:
            slots[idx] = [int(left), int(width), 0]
    return slots


def between_corpus():
    """(slots, pitch, width, first, last) for fcn.100063d0.

    ``n_slots`` is always at least ``2*max_left/pitch + 8``. That is a real
    bound, not padding: every left this function writes lies between the two
    bracketing lefts (``step = span/(k+1)`` with ``j <= k``), so no write can
    index past the last populated slot's neighbourhood, and the emulator
    cannot be scribbling outside the buffer while the port raises IndexError.
    """
    cases = []

    def add(name, entries, pitch, width, first, last, pad=8):
        max_left = max([int(e[0]) for e in entries] + [0])
        n_slots = 2 * max_left // max(pitch, 1) + pad
        # ``last`` is an inclusive slot index the vendor dereferences without a
        # bounds check; keeping it inside the array is the harness's job, not a
        # behaviour of the function.
        cases.append((name, _slots_from(entries, pitch, n_slots),
                      pitch, width, first, min(last, n_slots - 1)))

    # one clean gap of exactly two pitches: one frame belongs in the middle
    add("gap-2", [(1000, 190), (1400, 190)], 200, 190, 0, 40)
    # three pitches: two frames
    add("gap-3", [(1000, 190), (1600, 190)], 200, 190, 0, 40)
    # adjacent frames, nothing to fill
    add("gap-1", [(1000, 190), (1200, 190)], 200, 190, 0, 40)
    # remainder just under / just over the pitch/4 rule that decrements k
    for extra in (0, 49, 50, 51, 99, 100, 149, 150, 151, 199):
        add(f"quarter-{extra}", [(1000, 190), (1400 + extra, 190)],
            200, 190, 0, 60)
    # unequal widths, so the centre-to-centre span is not the left-edge span
    add("uneven-widths", [(1000, 40), (1600, 300)], 200, 190, 0, 40)
    add("uneven-widths-2", [(1000, 301), (1600, 41)], 200, 190, 0, 40)
    # an invalid slot between two valid ones: the ``p`` cursor must skip it
    s = _slots_from([(1000, 190), (1400, 0), (1800, 190)], 200, 40)
    cases.append(("zero-width-middle", s, 200, 190, 0, 39))
    s = _slots_from([(1000, 190), (1800, 190)], 200, 40)
    s[14] = [0, 190, 0]
    cases.append(("zero-left-middle", s, 200, 190, 0, 39))
    # first/last windows that exclude real entries
    add("window-tight", [(1000, 190), (1600, 190)], 200, 190, 10, 16)
    add("window-empty", [(1000, 190), (1600, 190)], 200, 190, 12, 12)
    add("window-inverted", [(1000, 190), (1600, 190)], 200, 190, 20, 5)
    # six real frames with two missing in the middle
    add("six-with-holes",
        [(0, 190), (200, 190), (800, 190), (1000, 190), (1600, 190)],
        200, 190, 0, 30)
    # randomised
    for seed in range(30):
        r = _rng(2000 + seed)
        pitch = int(r.integers(8, 400))
        width = int(r.integers(2, pitch + 40))
        n = int(r.integers(2, 8))
        pos = int(r.integers(1, 3 * pitch))
        entries = []
        for _ in range(n):
            entries.append((pos, int(r.integers(1, 3 * width + 2))))
            pos += int(r.integers(1, 4)) * pitch + int(r.integers(-pitch // 2,
                                                                 pitch // 2 + 1))
            pos = max(pos, 1)
        max_left = max(e[0] for e in entries)
        n_slots = 2 * max_left // pitch + 16
        first = int(r.integers(0, 4))
        last = int(r.integers(first, n_slots))
        cases.append((f"random-{seed}", _slots_from(entries, pitch, n_slots),
                      pitch, width, first, last))
    return cases


def blind_corpus():
    """(n_slots, pitch, width, n_lines, count_in) for fcn.10006720."""
    cases = []

    def add(name, pitch, width, n_lines, count_in=0):
        n_slots = n_lines // max(pitch, 1) + 16 + count_in
        cases.append((name, n_slots, pitch, width, n_lines, count_in))

    add("roll-6", 200, 190, 1400)
    add("roll-36", 2123, 1900, 80000)
    # n_lines - 1 exactly at, just under and just over the pitch+4 guard
    for d in (-2, -1, 0, 1, 2):
        add(f"guard{d:+d}", 200, 190, 205 + d)
    # the trailing-frame test: width/2 vs remaining, at the boundary
    for d in (-2, -1, 0, 1, 2):
        add(f"tail{d:+d}", 200, 190, 1 + 95 + d)
    # degenerate line counts
    add("lines-0", 200, 190, 0)
    add("lines-1", 200, 190, 1)
    add("lines-2", 200, 190, 2)
    # width larger than pitch, so ``half`` is negative
    add("width-gt-pitch", 100, 190, 1400)
    # a nonzero running count coming in
    add("count-in-3", 200, 190, 1400, count_in=3)
    add("count-in-1", 2123, 1900, 80000, count_in=1)
    for seed in range(24):
        r = _rng(3000 + seed)
        pitch = int(r.integers(1, 600))
        width = int(r.integers(1, 900))
        n_lines = int(r.integers(0, 40000))
        add(f"random-{seed}", pitch, width, n_lines,
            count_in=int(r.integers(0, 3)))
    return cases


def valid_corpus():
    """(rec, edges, dc) for fcn.10006310, and (edges, i) for fcn.10013960."""
    cases = []
    # a textbook accept: marks at the first and last quarter of a 190 frame
    cases.append(("accept", [100, 190, 0], [140, 250], 0))
    # each of the five comparisons failed one at a time, on and off by one
    lo_q = 100 + 190 // 4          # 147
    hi_q = 100 + (3 * 190) // 4    # 242
    cases.append(("first-mark-before-left", [100, 190, 0], [99, 250], 0))
    cases.append(("first-mark-at-left", [100, 190, 0], [100, 250], 0))
    cases.append(("first-mark-at-quarter", [100, 190, 0], [lo_q, 250], 0))
    cases.append(("first-mark-past-quarter", [100, 190, 0], [lo_q + 1, 250], 0))
    cases.append(("second-mark-at-3q", [100, 190, 0], [140, hi_q], 0))
    cases.append(("second-mark-below-3q", [100, 190, 0], [140, hi_q - 1], 0))
    cases.append(("second-mark-at-right", [100, 190, 0], [140, 290], 0))
    cases.append(("second-mark-past-right", [100, 190, 0], [140, 291], 0))
    # the last mark's partner reads 0 out of range
    cases.append(("one-mark-only", [100, 190, 0], [140], 0))
    cases.append(("no-marks", [100, 190, 0], [], 0))
    # a later pair works after earlier ones fail
    cases.append(("third-pair-wins", [100, 190, 0],
                  [1, 2, 3, 140, 250], 0))
    # the bypass
    cases.append(("bypass", [100, 190, 0], [], 1))
    cases.append(("bypass-with-marks", [100, 190, 0], [9999], 7))
    # degenerate geometry
    cases.append(("zero-width", [100, 0, 0], [100, 100], 0))
    cases.append(("negative-width", [100, -40, 0], [100, 90], 0))
    cases.append(("zero-left", [0, 190, 0], [0, 190], 0))
    cases.append(("negative-left", [-50, 190, 0], [-20, 100], 0))
    for seed in range(30):
        r = _rng(4000 + seed)
        left = int(r.integers(-40, 600))
        width = int(r.integers(-20, 400))
        m = int(r.integers(0, 6))
        edges = sorted(int(r.integers(-40, 900)) for _ in range(m))
        cases.append((f"random-{seed}", [left, width, 0], edges,
                      int(r.integers(0, 2))))
    return cases


def gapok_corpus():
    """(records, n_runs, a, b, slack) for fcn.10006630.

    ``n_runs >= 1`` throughout: with 0 the vendor reads ``records[-1]``,
    which is a real out-of-bounds read in TLB.dll (see the port's docstring),
    not something to bit-compare against.
    """
    cases = []
    recs6 = [[40 + 200 * k, 190, 0] for k in range(6)]
    for a, b in ((0, 2000), (300, 2000), (1300, 2000), (1300, 1400),
                 (1240, 1241), (500, 500), (2000, 300), (1300, 100),
                 (1300, 1299), (60, 10), (240, 30)):
        for slack in (0, 1, 5, 190, 1000):
            cases.append((f"six[{a},{b},s{slack}]", recs6, 6, a, b, slack))
    # single run, so both "ran off the end" limbs are reachable
    for a, b in ((0, 100), (0, 300), (500, 900), (900, 100), (100, 100)):
        for slack in (0, 3, 50):
            cases.append((f"one[{a},{b},s{slack}]",
                          [[100, 190, 0]], 1, a, b, slack))
    # The forward limb's ``20*slack >= records[i].left - a`` test. Without
    # these the `20*slack -> 2*slack` mutation is not observable at all: every
    # other case in this corpus lands the same side of that comparison for
    # both multipliers. Found by search, then confirmed against the DLL.
    for recs, n, a, b, s in (
            ([[4, 162, 0], [37, 89, 0], [229, 126, 0]], 3, -7, 4, 8),
            ([[2, 35, 0], [347, 24, 0], [739, 248, 0]], 3, 508, 806, 31),
            ([[173, 252, 0], [346, 151, 0]], 2, 82, 84, 27),
            ([[171, 220, 0], [203, 28, 0]], 2, 63, 393, 16),
            ([[172, 295, 0], [199, 180, 0], [587, 272, 0]], 3, 503, 597, 17),
            ([[86, 98, 0]], 1, 47, 128, 11)):
        cases.append((f"slack20[{a},{b},s{s}]", recs, n, a, b, s))
        cases.append((f"slack2[{a},{b},s{s}]", recs, n, a, b, s // 10))
    # the bare +/-10 constants, straddled
    for d in (-2, -1, 0, 1, 2):
        cases.append((f"ten{d:+d}", [[10 + d, 190, 0]], 1, 900, 100, 0))
        cases.append((f"minus-ten{d:+d}", [[0, 190, 0]], 1, 100,
                      200 + 10 + d, 0))
    for seed in range(40):
        r = _rng(5000 + seed)
        n = int(r.integers(1, 8))
        pos = int(r.integers(0, 200))
        recs = []
        for _ in range(n):
            recs.append([pos, int(r.integers(0, 400)), 0])
            pos += int(r.integers(1, 500))
        cases.append((f"random-{seed}", recs, n,
                      int(r.integers(-100, 3000)),
                      int(r.integers(-100, 3000)),
                      int(r.integers(0, 300))))
    return cases


def bestwin_corpus():
    """(win, n, data, start) for fcn.100064e0."""
    cases = []
    # a single dense block: the window should centre on it
    d = [0] * 600
    for i in range(200, 390):
        d[i] = 1
    cases.append(("one-block", 190, 200, d, 100))
    # two equal blocks -> the tie-break toward the centre decides
    d = [0] * 900
    for i in range(100, 290):
        d[i] = 1
    for i in range(500, 690):
        d[i] = 1
    cases.append(("two-blocks", 190, 400, d, 50))
    # all zero -> returns start + n/2
    cases.append(("all-zero", 50, 101, [0] * 400, 10))
    cases.append(("all-zero-even-n", 50, 100, [0] * 400, 10))
    # flat non-zero -> every sum equal, centre wins
    cases.append(("flat", 10, 41, [1] * 200, 5))
    cases.append(("flat-even-n", 10, 40, [1] * 200, 5))
    # negative data, which is where the unsigned compare shows
    d = [1] * 400
    d[120] = -1
    cases.append(("one-negative", 10, 60, d, 100))
    d = [0] * 400
    d[130] = -5
    cases.append(("only-negative", 10, 60, d, 100))
    # degenerate n / win
    cases.append(("n-1", 10, 1, [3] * 50, 0))
    cases.append(("n-0", 10, 0, [3] * 50, 0))
    cases.append(("win-0", 0, 20, [3] * 50, 0))
    cases.append(("win-1", 1, 20, list(range(50)), 0))
    for seed in range(24):
        r = _rng(6000 + seed)
        n = int(r.integers(1, 120))
        win = int(r.integers(0, 60))
        start = int(r.integers(0, 30))
        d = list(int(v) for v in r.integers(-3, 6, start + n + win + 4))
        cases.append((f"random-{seed}", win, n, d, start))
    return cases


def _ones_strip(n, first, pitch, width, n_frames, rng=None):
    d = [0] * n
    for k in range(n_frames):
        s = first + pitch * k
        for i in range(s, min(s + width, n)):
            d[i] = 1
    if rng is not None:
        for _ in range(int(rng.integers(0, 40))):
            d[int(rng.integers(0, n))] ^= 1
    return d


def phase34_corpus():
    """(slots, data, records, n_runs, pitch, width, count_in, start, bound,
    skip_gapok, edges, dc) for fcn.10006ae0 and fcn.10006ca0.

    Constraints that are the harness's, not the function's, and why:

    * ``pitch > width`` so ``(pitch-width)/2`` is non-negative and the search
      has at least one offset. A negative span is a caller error, not a
      behaviour worth bit-comparing.
    * ``bound >= pitch`` on the phase-4 side, so the backward window search
      (``start = pos - pitch``) never indexes before ``data[0]``. The vendor
      does not bounds-check it; letting it read out of the buffer would be
      comparing against undefined memory, not against TLB.dll.
    * ``data`` is sized ``bound + 2*pitch``: the search reads up to
      ``start + pitch - 2``.
    """
    cases = []

    def add(name, pitch, width, first, n_frames, start, bound,
            skip_gapok, edges=(), dc=0, count_in=0, seed=None):
        n = bound + 2 * pitch + 16
        rng = _rng(seed) if seed is not None else None
        data = _ones_strip(n, first, pitch, width, n_frames, rng)
        records = [[first + pitch * k, width, 0] for k in range(n_frames)]
        n_slots = 2 * (bound + pitch) // pitch + 12
        slots = [[0, 0, 0] for _ in range(n_slots)]
        for k in range(n_frames):
            idx = pf._cdiv(2 * (first + pitch * k), pitch)
            if 0 <= idx < n_slots:
                slots[idx] = [first + pitch * k, width, 0]
        cases.append((name, slots, data, records, n_frames, pitch, width,
                      count_in, start, bound, skip_gapok, list(edges), dc))

    # the everyday shape: six frames placed, plenty of film left
    add("six-then-room", 200, 190, 40, 6, 1240, 4000, 1, dc=1)
    add("six-then-room-gapok", 200, 190, 40, 6, 1240, 4000, 0, dc=1)
    # no edge-mark bypass and no marks: the validity test rejects the first
    # candidate, zeroes it, and the phase stops. dc=0 is the path phase 1's
    # own harness has never been able to exercise.
    add("no-bypass-no-marks", 200, 190, 40, 6, 1240, 4000, 1, dc=0)
    # real marks straddling where the next frame lands
    add("with-marks", 200, 190, 40, 6, 1240, 4000, 1,
        edges=[1290, 1400, 1490, 1600, 1690, 1800], dc=0)
    # barely any room: forces the single stepped tail frame
    for slack in (0, 100, 195, 200, 205, 300, 400):
        add(f"tail-{slack}", 200, 190, 40, 6, 1240, 1240 + slack, 1, dc=1)
        add(f"tail-{slack}-gapok", 200, 190, 40, 6, 1240, 1240 + slack, 0,
            dc=1)
    # no room at all / inverted bound
    add("bound-at-start", 200, 190, 40, 6, 1240, 1240, 1, dc=1)
    add("bound-before-start", 200, 190, 40, 6, 1240, 900, 1, dc=1)
    # a running count that must be added to, not replaced
    add("count-in", 200, 190, 40, 6, 1240, 4000, 1, dc=1, count_in=5)
    # odd pitches, so every truncation is exercised on an odd numerator
    add("odd-pitch", 201, 189, 41, 5, 1046, 3011, 1, dc=1)
    add("odd-pitch-gapok", 201, 189, 41, 5, 1046, 3011, 0, dc=1)
    add("wide-gap", 400, 190, 40, 4, 1640, 5000, 1, dc=1)
    add("narrow-gap", 200, 199, 40, 6, 1240, 4000, 1, dc=1)
    for seed in range(20):
        r = _rng(7000 + seed)
        pitch = int(r.integers(20, 400))
        width = int(r.integers(4, pitch))
        first = int(r.integers(0, pitch))
        n_frames = int(r.integers(1, 7))
        bound = int(r.integers(pitch + 40, 6000))
        start = int(r.integers(0, bound + 200))
        add(f"random-{seed}", pitch, width, first, n_frames, start, bound,
            int(r.integers(0, 2)),
            edges=sorted(int(r.integers(0, bound)) for _ in
                         range(int(r.integers(0, 5)))),
            dc=int(r.integers(0, 2)), count_in=int(r.integers(0, 3)),
            seed=8000 + seed)
    return cases


def thresh_corpus():
    """(hist, trace, first, last, forced) for fcn.10005d20."""
    cases = []

    def add(name, trace, first, last, forced):
        h = [0] * 256
        for i in range(first, min(last + 1, len(trace))):
            v = trace[i]
            if 0 <= v < 256:
                h[v] += 1
        cases.append((name, h, trace, first, last, forced))

    # a real-shaped trace: a low film-base mode plus a broad image lobe
    r = _rng(11)
    base = list(int(v) for v in r.integers(28, 42, 1400))
    for k in range(6):
        for i in range(40 + 200 * k, 40 + 200 * k + 190):
            base[i] = int(r.integers(110, 210))
    for forced in (0, -1, -7, 1, 60, 128, 255, 300):
        add(f"roll-{forced}", base, 0, 1399, forced)
        add(f"roll-window-{forced}", base, 200, 900, forced)
    # a single perfectly flat trace: every bin equal, then all in one bin
    add("flat-one-bin", [77] * 800, 0, 799, 0)
    add("flat-one-bin-pct", [77] * 800, 0, 799, -1)
    add("uniform", list(range(256)) * 4, 0, 1023, 0)
    add("uniform-pct", list(range(256)) * 4, 0, 1023, -1)
    # the peak at the very ends of the scanned range
    add("peak-at-0", [0] * 600, 0, 599, 0)
    add("peak-at-0-pct", [0] * 600, 0, 599, -1)
    add("peak-at-249", [249] * 600, 0, 599, 0)
    add("peak-at-255", [255] * 600, 0, 599, 0)
    add("peak-at-255-pct", [255] * 600, 0, 599, -1)
    # bins 250..255 are outside the scan: a mode parked there must be missed
    add("mode-above-249", [252] * 500 + [30] * 100, 0, 599, 0)
    # empty / degenerate windows
    add("empty-window", [50] * 100, 40, 39, 0)
    add("one-line", [50] * 100, 10, 10, 0)
    add("one-line-pct", [50] * 100, 10, 10, -1)
    # a histogram big enough that the 0.02f product needs more than 53 bits,
    # which is where a float64 intermediate would double-round
    big = [0] * 256
    big[10] = 0x3FFFFFFF
    big[11] = 0x3FFFFFFF
    big[12] = 0x3FFFFFFF
    big[13] = 0x3FFFFFFF
    cases.append(("huge-bins-pct", big, [12] * 40, 0, 39, -1))
    cases.append(("huge-bins-modal", big, [12] * 40, 0, 39, 0))
    # negative bin counts, so the unsigned fixup path is exercised
    neg = [0] * 256
    neg[5] = -3
    neg[6] = 17
    neg[200] = -1
    cases.append(("negative-bins-pct", neg, [6] * 40, 0, 39, -1))
    cases.append(("negative-bins-modal", neg, [6] * 40, 0, 39, 0))
    for seed in range(30):
        rr = _rng(12000 + seed)
        n = int(rr.integers(20, 900))
        tr = list(int(v) for v in rr.integers(0, 256, n))
        first = int(rr.integers(0, n))
        last = int(rr.integers(first, n))
        forced = int(rr.choice([0, 0, 0, -1, -1, 1, 33, 200]))
        add(f"random-{seed}", tr, first, last, forced)
        # and the same histogram driven from a hand-made one, so the bins are
        # not constrained to be a real histogram of the trace
        h = list(int(v) for v in rr.integers(0, 5000, 256))
        cases.append((f"synth-{seed}", h, tr, first, last, forced))
    return cases


def driver_corpus():
    """(data, records, n_runs, left, right, n_slots, pitch, width, skip,
    ca4, edges, dc) for fcn.10006e70."""
    cases = []

    def add(name, pitch, width, first, n_frames, left, right, skip,
            ca4=0, edges=(), dc=0, seed=None, drop=()):
        n = right + 2 * pitch + 16
        rng = _rng(seed) if seed is not None else None
        data = _ones_strip(n, first, pitch, width, n_frames, rng)
        records = [[first + pitch * k, width, 0] for k in range(n_frames)
                   if k not in drop]
        n_slots = 2 * right // pitch + 6
        cases.append((name, data, records, len(records), left, right, n_slots,
                      pitch, width, skip, ca4, list(edges), dc))

    # six clean frames in the middle of a long strip: phases 3 and 4 both
    # have room, phase 2 has nothing to do
    add("six-centred", 200, 190, 800, 6, 0, 4000, 1)
    add("six-centred-gapok", 200, 190, 800, 6, 0, 4000, 0)
    # a hole in the middle, so phase 2 fires and the 0x100 bit is set
    add("hole", 200, 190, 800, 6, 0, 4000, 1, drop=(2, 3))
    add("hole-gapok", 200, 190, 800, 6, 0, 4000, 0, drop=(2, 3))
    # phase 1 finds nothing -> the driver must bail before phases 3 and 4
    add("no-frames", 200, 190, 800, 0, 0, 4000, 1)
    # exactly one frame: phase 2 is gated off (count < 2)
    add("one-frame", 200, 190, 800, 1, 0, 4000, 1)
    add("two-frames", 200, 190, 800, 2, 0, 4000, 1)
    # tight bounds, so phases 3/4 hit their stepped-tail limbs
    add("tight", 200, 190, 800, 6, 700, 2100, 1)
    add("tight-gapok", 200, 190, 800, 6, 700, 2100, 0)
    # the phase-1 edge-validity switch, the path that was never modelled
    add("ca4-no-marks", 200, 190, 800, 6, 0, 4000, 1, ca4=1, dc=0)
    add("ca4-bypass", 200, 190, 800, 6, 0, 4000, 1, ca4=1, dc=1)
    add("ca4-marks", 200, 190, 800, 6, 0, 4000, 1, ca4=1, dc=0,
        edges=[810, 980, 1010, 1180, 1210, 1380, 1410, 1580])
    # marks with phases 3/4 consulting them too (dc = 0 always consults there)
    add("marks-dc0", 200, 190, 800, 6, 0, 4000, 1, ca4=0, dc=0,
        edges=[810, 980, 1010, 1180, 2010, 2180])
    add("odd", 201, 189, 803, 5, 3, 3311, 1)
    add("odd-gapok", 201, 189, 803, 5, 3, 3311, 0)
    for seed in range(18):
        r = _rng(9000 + seed)
        pitch = int(r.integers(30, 400))
        width = int(r.integers(8, pitch))
        n_frames = int(r.integers(0, 8))
        first = int(r.integers(1, 600))
        right = max(first + pitch * (n_frames + 2) + 40,
                    int(r.integers(1200, 6000)))
        left = int(r.integers(0, max(1, first)))
        drop = tuple(int(v) for v in r.integers(0, max(n_frames, 1),
                                                int(r.integers(0, 3))))
        add(f"random-{seed}", pitch, width, first, n_frames, left, right,
            int(r.integers(0, 2)), ca4=int(r.integers(0, 2)),
            edges=sorted(int(r.integers(0, right)) for _ in
                         range(int(r.integers(0, 6)))),
            dc=int(r.integers(0, 2)), seed=9500 + seed, drop=drop)
    return cases


def _strip(pitch, width, n_frames, lead, n_lines, gap=205, img=60,
           seed=None, noise=0):
    """A synthetic per-line RGB summary: ``n_frames`` dark frames on a gap."""
    r = _rng(seed) if seed is not None else None
    g = np.full(n_lines, gap, dtype=np.int32)
    for k in range(n_frames):
        s = lead + pitch * k
        e = min(s + width, n_lines)
        if s < n_lines:
            g[s:e] = img
    if r is not None and noise:
        g = g + r.integers(-noise, noise + 1, n_lines)
    g = np.clip(g, 0, 255)
    return np.stack([g, g, g], axis=1).astype(np.uint8)


def entry_corpus():
    """(rgb, n_slots, pitch, width, first, tail, skip, mode, ca4, edges, dc)."""
    cases = []

    def add(name, pitch, width, n_frames, lead, n_lines, first, tail, skip,
            mode=0, ca4=0, edges=(), dc=1, seed=None, gap=205, img=60,
            noise=0):
        rgb = _strip(pitch, width, n_frames, lead, n_lines, gap, img, seed,
                     noise)
        last = n_lines - tail - 1
        n_slots = 2 * max(last, 1) // pitch + 8
        cases.append((name, rgb, n_slots, pitch, width, first, tail, skip,
                      mode, ca4, list(edges), dc))

    # a clean six-frame roll: the modal rule should land it in one pass
    add("clean-6", 200, 190, 6, 100, 1500, 0, 0, 1)
    add("clean-6-gapok", 200, 190, 6, 100, 1500, 0, 0, 0)
    add("clean-6-noisy", 200, 190, 6, 100, 1500, 0, 0, 1, seed=31, noise=18)
    add("clean-6-window", 200, 190, 6, 100, 1500, 60, 40, 1)
    # merged frames (no gap between 2 and 3): drives the upward search
    g = np.full(1500, 205, dtype=np.int32)
    for k in range(6):
        s = 100 + 200 * k
        g[s:s + 190] = 60
    g[100 + 400 + 190: 100 + 600] = 62      # fill one interframe gap
    rgb = np.stack([g, g, g], axis=1).astype(np.uint8)
    cases.append(("merged-pair", rgb, 2 * 1499 // 200 + 8, 200, 190, 0, 0, 1,
                  0, 0, [], 1))
    # a low-contrast roll, so the first binarisation finds too few runs and
    # the percentile fallback has to fire
    add("low-contrast", 200, 190, 6, 100, 1500, 0, 0, 1, gap=130, img=124)
    add("flat", 200, 190, 0, 100, 1500, 0, 0, 1, gap=140, img=140)
    add("all-image", 200, 190, 1, 0, 1500, 0, 0, 1, gap=60, img=60)
    # short strips and odd geometry
    add("short", 200, 190, 2, 20, 500, 0, 0, 1)
    add("tiny", 200, 190, 1, 5, 260, 0, 0, 1)
    add("odd-pitch", 201, 189, 5, 97, 1400, 3, 5, 1, seed=57, noise=9)
    add("wide-gap", 400, 190, 3, 100, 1500, 0, 0, 1)
    # the vtable mode-2 trace (no 255- inversion) feeding the whole cascade
    add("mode2", 200, 190, 6, 100, 1500, 0, 0, 1, mode=2)
    add("mode2-inverted-film", 200, 190, 6, 100, 1500, 0, 0, 1, mode=2,
        gap=50, img=195)
    # the phase-1 edge-validity switch, end to end
    add("ca4-no-marks", 200, 190, 6, 100, 1500, 0, 0, 1, ca4=1, dc=0)
    add("ca4-marks", 200, 190, 6, 100, 1500, 0, 0, 1, ca4=1, dc=0,
        edges=[110, 280, 310, 480, 510, 680, 710, 880])
    add("dc0-phases34", 200, 190, 6, 100, 1500, 0, 0, 1, ca4=0, dc=0,
        edges=[1310, 1480])
    # --- cases that exist ONLY to pin the search's own decisions ---------
    # Each was found by searching for an input where the corresponding
    # mutation in MUTATIONS changes the answer, then confirmed against the
    # real DLL. Without them those four decisions are asserted, not tested:
    # every other roll here lands the same way whichever choice the port
    # makes, and --mutate said so.
    #
    # (a) the turnaround re-binarises at the INITIAL threshold, not the best
    # (b) it resets the plateau tracker but NOT the best count
    add("turnaround-a", 240, 17, 4, 0, 1722, 14, 16, 0, dc=0, seed=895469,
        noise=48, gap=195, img=179)
    add("turnaround-b", 139, 137, 5, 102, 1784, 10, 13, 0, dc=0, seed=114381,
        noise=30, gap=13, img=167)
    add("turnaround-c", 130, 12, 8, 43, 709, 16, 7, 1, dc=0, seed=326164,
        noise=22, gap=176, img=41)
    add("reset-best-a", 293, 241, 8, 106, 1739, 17, 9, 1, dc=0, seed=314401,
        noise=43, gap=83, img=21)
    add("reset-best-b", 61, 12, 0, 30, 1028, 11, 12, 1, dc=0, seed=164240,
        noise=12, gap=166, img=169)
    add("reset-best-c", 40, 23, 0, 32, 1898, 3, 5, 1, dc=0, seed=11401,
        noise=13, gap=151, img=82)
    # (c) the upward leg caps at 250, the downward one at 256. Reaching that
    # cap at all needs near-black frames (trace above 250) AND content that
    # still re-binarises in the 248..255 band, or the extra iterations cannot
    # move anything. This roll does both; the search that produced it needed
    # 60 000 random tries to find one, which is itself the reason the row was
    # NOT CAUGHT before.
    def _cap_strip(n_lines, pitch, width, n_frames, lead, seed, n_speckle):
        r = _rng(seed)
        v = np.full(n_lines, 230, dtype=np.int32)
        for k in range(n_frames):
            s = lead + pitch * k
            v[s:min(s + width, n_lines)] = 1
        for _ in range(n_speckle):
            v[int(r.integers(0, n_lines))] = int(r.integers(0, 7))
        return np.stack([v, v, v], axis=1).astype(np.uint8)

    cases.append(("up-cap-250", _cap_strip(1306, 36, 9, 2, 34, 0, 25),
                  2 * 1304 // 36 + 8, 36, 9, 3, 1, 0, 0, 0, [], 0))

    for seed in range(14):
        rr = _rng(13000 + seed)
        pitch = int(rr.integers(60, 300))
        width = int(rr.integers(20, pitch))
        n_lines = int(rr.integers(400, 2200))
        n_frames = int(rr.integers(0, 8))
        add(f"random-{seed}", pitch, width, n_frames,
            int(rr.integers(0, pitch)), n_lines,
            int(rr.integers(0, 30)), int(rr.integers(0, 30)),
            int(rr.integers(0, 2)), mode=int(rr.choice([0, 2])),
            ca4=int(rr.integers(0, 2)), dc=int(rr.integers(0, 2)),
            edges=sorted(int(rr.integers(0, n_lines))
                         for _ in range(int(rr.integers(0, 5)))),
            seed=14000 + seed, noise=int(rr.integers(0, 30)),
            gap=int(rr.integers(120, 250)), img=int(rr.integers(20, 110)))
    return cases


def roll_corpus():
    """``(name, kwargs)`` for ``fcn.100079c0``.

    Every knob the function reads is swept: both geometry models
    (``this->0xc98``), both branch arms (argument 2), both margin regimes (the
    ``10 * pitch < n_lines`` gate), the dead third argument, the ``n_slots <=
    0`` bail-out, a pre-existing picture list, and both allocation-failure
    limbs — driven by failing the vendor's OWN allocator, not by asserting the
    limb is unreachable.
    """
    cases = []

    def add(name, *, n_lines=1500, pitch=200, width=190, n_frames=6, lead=100,
            gap=205, img=60, seed=None, noise=0, rgb=None,
            skip_gapok=1, place_blindly=0, no_tail_margin=0,
            line_scale=2, margin_units=1, margin_divisor=2540,
            crop=None, frame_bottom=None, end_anchored=0, image_rows=None,
            pictures_in=(), count_in=0, warn_in=0, mode=0, ca4=0, edges=(),
            dc=1, pitch_raw=None, width_raw=None,
            malloc_fails=False, new_fails_at=None):
        if rgb is None:
            rgb = _strip(pitch, width, n_frames, lead, n_lines, gap, img,
                         seed, noise)
        n_lines = int(rgb.shape[0])
        if crop is None:
            # (top, left, bottom, right): a frame-relative row band and an
            # absolute column band, the way this+0xc88..0xc94 is used.
            crop = (6, 40, 6 + line_scale * width - 12, 40 + 900)
        if frame_bottom is None:
            frame_bottom = crop[2] + 5
        if image_rows is None:
            image_rows = line_scale * n_lines
        cases.append((name, dict(
            rgb_u8=rgb, skip_gapok=skip_gapok, place_blindly=place_blindly,
            no_tail_margin=no_tail_margin, line_scale=line_scale,
            image_rows=image_rows, margin_units=margin_units,
            pitch_raw=pitch * line_scale if pitch_raw is None else pitch_raw,
            width_raw=width * line_scale if width_raw is None else width_raw,
            margin_divisor=margin_divisor, crop=tuple(crop),
            frame_bottom=frame_bottom, end_anchored=end_anchored,
            pictures_in=[tuple(p) for p in pictures_in], count_in=count_in,
            warn_in=warn_in, mode=mode, ca4=ca4, edges=list(edges), dc=dc,
            malloc_fails=malloc_fails, new_fails_at=new_fails_at)))

    # --- the two geometry models x the two branch arms -------------------
    add("clean-6")
    add("clean-6-blind", place_blindly=1)
    add("clean-6-anchored", end_anchored=1)
    add("clean-6-anchored-blind", end_anchored=1, place_blindly=1)
    add("clean-6-blind-warn-in", place_blindly=1, warn_in=0x401)
    add("clean-6-count-in", count_in=77, warn_in=0x40)
    add("clean-6-gapok", skip_gapok=0)
    add("clean-6-scale1", line_scale=1)
    add("clean-6-scale5", line_scale=5)
    # a pitch that is not a whole multiple of the scale: the two unsigned
    # divs at 0x100079f5 / 0x10007a0a truncate
    add("ragged-scale", line_scale=3, pitch_raw=200 * 3 + 2,
        width_raw=190 * 3 + 1)

    # --- the margin gate: 10*pitch < n_lines (0x10007ae0) -----------------
    # default rolls are 1500 lines at pitch 200, so 2000 >= 1500 and BOTH
    # margins stay zero. These are long enough to turn it on.
    add("margin-on", n_lines=2600, n_frames=11)
    add("margin-on-no-tail", n_lines=2600, n_frames=11, no_tail_margin=1)
    add("margin-on-big", n_lines=2600, n_frames=11, margin_divisor=1270)
    # the same pair with the end-anchored model, which hardcodes first=tail=0
    # at 0x10007d57 and must therefore be INSENSITIVE to both
    add("margin-anchored", n_lines=2600, n_frames=11, end_anchored=1)
    add("margin-anchored-no-tail", n_lines=2600, n_frames=11, end_anchored=1,
        no_tail_margin=1)
    add("margin-boundary", n_lines=2000, n_frames=9)     # 10*pitch == n_lines
    # Every case above answers the same whether the gate is 9*pitch or
    # 10*pitch, and --mutate said so: a ten-line margin moves nothing on a
    # roll whose frames sit a hundred lines from either end. These four were
    # built to make the three margin decisions observable — a margin big
    # enough to swallow a frame (margin_divisor 254 -> 100 lines) on a roll
    # that lands strictly between 9*pitch and 10*pitch, with frames right up
    # against both ends. Confirmed against the DLL, not just against the port.
    add("margin-gate-9v10", n_lines=1900, n_frames=10, lead=5,
        margin_divisor=254)
    add("margin-gate-9v10-b", n_lines=1900, n_frames=10, lead=120,
        margin_divisor=254)
    # the tail leg on its own: gate ON, and a last frame that only survives
    # when the tail is NOT trimmed
    add("tail-margin-matters", n_lines=2600, n_frames=12, lead=150,
        margin_divisor=254)
    add("tail-margin-matters-off", n_lines=2600, n_frames=12, lead=150,
        margin_divisor=254, no_tail_margin=1)
    add("tail-margin-matters-b", n_lines=2440, n_frames=11, lead=150,
        margin_divisor=254)
    add("tail-margin-matters-b-off", n_lines=2440, n_frames=11, lead=150,
        margin_divisor=254, no_tail_margin=1)
    # and the same rolls under the end-anchored model, which must ignore the
    # margin entirely (0x10007d57 pushes two literal zeroes)
    add("margin-anchored-matters", n_lines=1900, n_frames=10, lead=5,
        margin_divisor=254, end_anchored=1)
    add("margin-anchored-matters-b", n_lines=2600, n_frames=12, lead=150,
        margin_divisor=254, end_anchored=1)

    # --- the n_slots <= 0 bail-out (0x10007a29) --------------------------
    # (2*n_lines)/pitch == 0. The pre-existing list must SURVIVE this exit and
    # this->0xc9c must keep its old value — the one path that does not reset.
    add("no-slots", n_lines=500, pitch=1200, width=1100, n_frames=0,
        count_in=42, pictures_in=[(1, 2, 3, 4, 2, 1), (5, 6, 7, 8, 9, 4)])
    add("no-slots-blind", n_lines=500, pitch=1200, width=1100, n_frames=0,
        place_blindly=1, count_in=42, warn_in=0x200)

    # --- a pre-existing list on a path that DOES reset --------------------
    add("replaces-list", pictures_in=[(1, 2, 3, 4, 2, 1), (5, 6, 7, 8, 9, 4),
                                      (9, 9, 9, 9, 1, 0)], count_in=13)
    add("replaces-list-anchored", end_anchored=1, count_in=13,
        pictures_in=[(11, 22, 33, 44, 4, 1)])

    # --- allocation failures, driven through the vendor's own allocator ---
    add("malloc-fails", malloc_fails=True, count_in=5,
        pictures_in=[(1, 2, 3, 4, 2, 1)])
    add("new-fails-first", new_fails_at=0)
    add("new-fails-third", new_fails_at=2)
    add("new-fails-anchored", end_anchored=1, new_fails_at=1)
    add("new-fails-blind", place_blindly=1, new_fails_at=2)

    # --- slots the loop DISCARDS: left == 0 (0x10007b9e / 0x10007de1) -----
    # blind placement with pitch == width puts its first slot at left 0, and
    # that picture is then thrown away rather than placed at row crop_top.
    add("blind-left-zero", pitch=200, width=200, place_blindly=1)
    add("blind-left-zero-anchored", pitch=200, width=200, place_blindly=1,
        end_anchored=1)

    # --- the clamps -------------------------------------------------------
    add("clamp-bottom", image_rows=900)
    add("clamp-bottom-anchored", image_rows=900, end_anchored=1)
    add("clamp-top-negative", crop=(-500, 40, -500 + 2 * 190 - 12, 940))
    add("clamp-top-negative-anchored", end_anchored=1,
        crop=(-500, 40, -500 + 2 * 190 - 12, 940), frame_bottom=-100)
    add("clamp-both", image_rows=300, crop=(-40, 40, 300, 940))

    # --- the end-anchored model's leading-partial-frame limb --------------
    # 0x10007df2 needs a slot that BOTH starts inside the first five lines and
    # is shorter than the nominal width. A clipped dark band at the head of the
    # strip does NOT produce one: phase 1 normalises every slot it places to
    # exactly `width`, so the measured run length never survives into the slot.
    # The only producer in the whole cascade is phase 4's pin (0x10006dce,
    # `vendor_look_at_beginning`'s `left_bound + 1` limb), which fires when the
    # leftmost placed frame leaves a gap too small for a nominal frame:
    # `half + pitch > left_edge - half >= pitch/2 + half`. With pitch 200,
    # width 190 and left_bound 0 that means a first frame at 110..200 lines in.
    # It then writes `left = 1, length = left_edge - half - 1` — 139 here — and
    # needs this+0xdc != 0, or the edge test zeroes the record again.
    # This corpus had no such roll until the limb was measured uncovered.
    lead4 = 150
    g = np.full(1500, 205, dtype=np.int32)
    for k in range(6):
        g[lead4 + 200 * k: lead4 + 200 * k + 190] = 60
    part = dict(rgb=np.stack([g, g, g], axis=1).astype(np.uint8), dc=1)
    add("anchored-pin-partial", end_anchored=1, **part)
    add("anchored-pin-partial-start", end_anchored=0, **part)
    add("anchored-pin-partial-margin", end_anchored=1, frame_bottom=400,
        **part)
    add("anchored-pin-partial-clamped", end_anchored=1, image_rows=600,
        **part)
    # The OTHER side of 0x10007deb's test: a slot whose left edge is inside the
    # first five lines but whose length is EXACTLY the nominal width, which is
    # what phase 1 writes for every frame it places. `jae` sends it to the
    # ordinary limb; a `<=` there would send it to the partial one. Nothing in
    # this corpus pinned that boundary until --mutate reported the row NOT
    # CAUGHT. A frame at line 1..4 is all it takes.
    for _lead in (1, 4):
        add(f"anchored-lead-{_lead}", lead=_lead, end_anchored=1)
        add(f"anchored-lead-{_lead}-minh", lead=_lead, end_anchored=1,
            line_scale=4, crop=(6, 40, 26, 940))
    add("anchored-lead-5", lead=5, end_anchored=1)

    # --- the end-anchored model's 16*line_scale minimum height ------------
    # crop_bottom - crop_top + 1 deliberately below 16*line_scale, so every
    # picture hits 0x10007e48 and is stretched. The DIRECTION depends on the
    # slot's left edge (0x10007e50), so the pinned partial above is what covers
    # the `left < 5` half; every ordinary roll covers the other.
    add("anchored-min-height", end_anchored=1, line_scale=4,
        crop=(6, 40, 26, 940))
    add("anchored-min-height-pin", end_anchored=1, line_scale=4,
        crop=(6, 40, 26, 940), **part)
    add("anchored-min-height-pin-wide", end_anchored=1, line_scale=9,
        crop=(6, 40, 60, 940), **part)
    add("anchored-min-height-clamped", end_anchored=1, line_scale=4,
        crop=(6, 40, 26, 940), image_rows=700)

    # --- shapes that stress the cascade underneath ------------------------
    # a dropped middle frame, so phase 2 fires and a tag-2 slot reaches the
    # CiPicLoc constructor's grade switch
    g2 = np.full(1500, 205, dtype=np.int32)
    for k in (0, 1, 2, 4, 5, 6):
        g2[100 + 200 * k: 100 + 200 * k + 190] = 60
    dropped = np.stack([g2, g2, g2], axis=1).astype(np.uint8)
    add("phase2-fill", rgb=dropped, dc=1)
    add("phase2-fill-anchored", rgb=dropped, dc=1, end_anchored=1)
    add("flat", gap=140, img=140, n_frames=0)
    add("flat-blind", gap=140, img=140, n_frames=0, place_blindly=1)
    add("low-contrast", gap=130, img=124)
    add("mode2", mode=2)
    add("noisy", seed=31, noise=18)
    add("edges", ca4=1, dc=0, edges=[110, 280, 310, 480, 510, 680])

    for seed in range(10):
        rr = _rng(19000 + seed)
        pitch = int(rr.integers(60, 300))
        width = int(rr.integers(20, pitch))
        n_lines = int(rr.integers(400, 2600))
        scale = int(rr.integers(1, 6))
        ct = int(rr.integers(-60, 60))
        add(f"random-{seed}", pitch=pitch, width=width, n_lines=n_lines,
            n_frames=int(rr.integers(0, 9)), lead=int(rr.integers(0, pitch)),
            line_scale=scale, end_anchored=int(rr.integers(0, 2)),
            place_blindly=int(rr.integers(0, 2)),
            no_tail_margin=int(rr.integers(0, 2)),
            skip_gapok=int(rr.integers(0, 2)),
            margin_divisor=int(rr.choice([1270, 2540, 5080, 25400])),
            margin_units=int(rr.integers(1, 4)),
            crop=(ct, int(rr.integers(0, 200)),
                  ct + int(rr.integers(4, scale * width + 40)),
                  int(rr.integers(400, 1400))),
            frame_bottom=ct + int(rr.integers(4, scale * width + 80)),
            image_rows=int(rr.integers(200, scale * n_lines + 200)),
            count_in=int(rr.integers(0, 40)),
            warn_in=int(rr.choice([0, 0x40, 0x401])),
            mode=int(rr.choice([0, 2])), ca4=int(rr.integers(0, 2)),
            dc=int(rr.integers(0, 2)), seed=20000 + seed,
            noise=int(rr.integers(0, 30)), gap=int(rr.integers(120, 250)),
            img=int(rr.integers(20, 110)))
    return cases


def trace_corpus():
    cases = []
    cases.append(("ramp", np.stack([np.arange(256) % 256] * 3, axis=1)
                  .astype(np.uint8)))
    r = _rng(7)
    cases.append(("random-1000", r.integers(0, 256, (1000, 3)).astype(np.uint8)))
    cases.append(("extremes", np.array(
        [[0, 0, 0], [255, 255, 255], [255, 0, 0], [0, 255, 255],
         [1, 1, 2], [254, 255, 255], [128, 128, 127]], dtype=np.uint8)))
    return cases


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

class Result:
    def __init__(self):
        self.checks = 0
        self.fails: list[str] = []

    def eq(self, name, got, want):
        self.checks += 1
        if got != want:
            self.fails.append(f"{name}: port={got!r} vendor={want!r}")


def run_all(host: TlbHost, res: Result, verbose: bool = True) -> None:
    # Rewind the bump allocator. --mutate runs this whole function once per
    # mutation, and without the rewind the heap runs out partway through and
    # every later row reports CAUGHT because of a MemoryError rather than
    # because of a real difference — which would be a lie about coverage.
    host.bump = HEAP_ADDR + 0x1000
    host.errors = 0
    # -- fcn.10006870 : the per-line trace ------------------------------
    n_tr = 0
    for name, rgb in trace_corpus():
        for mode in (0, 2):
            want = host.vendor_trace(rgb, mode)
            got = list(int(v) for v in
                       pf.vendor_framing_trace(rgb, invert=(mode != 2)))
            res.eq(f"trace[{name},mode={mode}]", got, want)
            n_tr += len(want)
    if verbose:
        print(f"  fcn.10006870  per-line trace         "
              f"{n_tr:8d} lines compared")

    # -- fcn.10005ce0 : the histogram -----------------------------------
    n_h = 0
    for name, rgb in trace_corpus():
        tr = [int(v) for v in pf.vendor_framing_trace(rgb)]
        for first, last in ((0, len(tr) - 1), (0, 0),
                            (len(tr) // 3, 2 * len(tr) // 3)):
            want = host.vendor_hist(tr, first, last)
            got = [int(v) for v in
                   pf.vendor_line_histogram(np.asarray(tr), first, last)]
            res.eq(f"hist[{name},{first},{last}]", got, want)
            n_h += 1
    if verbose:
        print(f"  fcn.10005ce0  256-bin histogram      "
              f"{n_h:8d} windows compared")

    # -- fcn.10006140 : runs + bins -------------------------------------
    n_r = n_rec = 0
    for name, o, first, last, width in ones_corpus():
        vr, vbins, vrecs = host.vendor_runs(o, first, last, width)
        pr, pbins, precs = pf.vendor_ones_runs(o, first, last, width)
        res.eq(f"runs[{name}].n", pr, vr)
        res.eq(f"runs[{name}].bins", list(pbins), list(vbins))
        res.eq(f"runs[{name}].recs", [list(x) for x in precs],
               [list(x) for x in vrecs])
        n_r += 1
        n_rec += len(vrecs)
    # the shared-block semantics: a refusing call must leave both outputs
    # exactly as the previous call left them
    good = np.zeros(1400, dtype=np.int32)
    for k in range(6):
        good[40 + 200 * k: 40 + 200 * k + 190] = 1
    short = np.zeros(1400, dtype=np.int32)
    short[0:190] = 1                       # ones[first]==1, one run -> refuse
    empty = np.zeros(1400, dtype=np.int32)  # ones[first]==0, no runs -> refuse
    for tag, seq in (("good-then-refuse-1",
                      [(good, 0, 1399), (short, 0, 1399), (good, 0, 1399)]),
                     ("good-then-refuse-0",
                      [(good, 0, 1399), (empty, 0, 1399)]),
                     ("refuse-first", [(empty, 0, 1399), (good, 0, 1399)])):
        want = host.vendor_runs_shared(seq, 190)
        bins = [0, 0, 0]
        pp = [[]]
        got = []
        for ones, first, last in seq:
            r, b, recs = pf.vendor_ones_runs(ones, first, last, 190, bins, pp)
            got.append((r, list(b), [list(x) for x in recs]))
        res.eq(f"runs[shared:{tag}]", got, want)
    if verbose:
        print(f"  fcn.10006140  runs + LoLim/HiLim     "
              f"{n_r:8d} arrays, {n_rec} run records compared"
              f"  (+3 shared-block sequences)")

    # -- fcn.10006930 : phase 1 -----------------------------------------
    n_n = n_pl = 0
    for (name, recs, n_runs, pitch, width, lb, rb, nslots) in nice_corpus():
        vpl, vcount = host.vendor_nice(recs, n_runs, pitch, width, lb, rb,
                                       nslots)
        ppl, pcount = pf.vendor_look_for_nice_pictures(
            recs, n_runs, pitch, width, lb, rb)
        ppl = {k: v for k, v in ppl.items() if 0 <= k < nslots}
        res.eq(f"nice[{name}].count", pcount, vcount)
        res.eq(f"nice[{name}].placements",
               sorted(ppl.items()), sorted(vpl.items()))
        n_n += 1
        n_pl += len(vpl)
        # the documented restriction: with the edge test enabled but bypassed
        # (this+0xdc != 0) the vendor's answer must not move
        vpl2, vcount2 = host.vendor_nice(recs, n_runs, pitch, width, lb, rb,
                                         nslots, ca4=1, dc=1)
        res.eq(f"nice[{name}].edge-bypass",
               sorted(vpl2.items()) + [("count", vcount2)],
               sorted(vpl.items()) + [("count", vcount)])
        # ca4 != 0 with dc == 0: the edge test really runs. This used to be
        # the port's one documented blind spot in phase 1.
        for tag, edges in (("no-marks", []),
                           ("marks", [110, 260, 400, 700, 1500, 1700])):
            vpl3, vcount3 = host.vendor_nice(recs, n_runs, pitch, width, lb,
                                             rb, nslots, ca4=1, dc=0,
                                             edges=edges)
            ppl3, pcount3 = pf.vendor_look_for_nice_pictures(
                recs, n_runs, pitch, width, lb, rb, 1, edges, 0)
            ppl3 = {k: v for k, v in ppl3.items()
                    if 0 <= k < nslots and (v[0] or v[1])}
            res.eq(f"nice[{name}].ca4-{tag}",
                   (pcount3, sorted(ppl3.items())),
                   (vcount3, sorted(vpl3.items())))
    if verbose:
        print(f"  fcn.10006930  LookForNicePictures    "
              f"{n_n:8d} cases, {n_pl} placements compared")

    # -- fcn.100063d0 : phase 2 -----------------------------------------
    # The whole slot array is compared, not just the entries the function
    # placed: phase 2 writes back into its own input, so an off-by-one slot
    # index or a stray write is only visible array-wide.
    n_b = n_bs = 0
    for (name, slots, pitch, width, first, last) in between_corpus():
        vslots, vcount = host.vendor_between(slots, pitch, width, first, last)
        pslots = [list(s) for s in slots]
        pcount = pf.vendor_look_in_between_ends(pslots, pitch, width,
                                                first, last)
        res.eq(f"between[{name}].count", pcount, vcount)
        res.eq(f"between[{name}].slots", pslots, vslots)
        n_b += 1
        n_bs += len(vslots)
    if verbose:
        print(f"  fcn.100063d0  LookInBetweenEnds      "
              f"{n_b:8d} cases, {n_bs} slots compared")

    # -- fcn.10006720 : phase 5 -----------------------------------------
    n_bl = n_bls = 0
    for (name, n_slots, pitch, width, n_lines, count_in) in blind_corpus():
        vslots, vcount = host.vendor_blind(n_slots, pitch, width, n_lines,
                                           count_in)
        pslots = [[0, 0, 0] for _ in range(n_slots)]
        pcount = pf.vendor_blindly_place_pictures(pslots, pitch, width,
                                                  n_lines, count_in)
        res.eq(f"blind[{name}].count", pcount, vcount)
        res.eq(f"blind[{name}].slots", pslots, vslots)
        n_bl += 1
        n_bls += len(vslots)
    if verbose:
        print(f"  fcn.10006720  BlindlyPlacePictures   "
              f"{n_bl:8d} cases, {n_bls} slots compared")

    # -- fcn.10013960 / fcn.10006310 : the film-edge validity test ------
    n_at = 0
    for name, rec, edges, dc in valid_corpus():
        for i in (-0, 0, 1, len(edges) - 1, len(edges), len(edges) + 1):
            if i < 0:
                continue
            res.eq(f"at[{name},{i}]", pf.vendor_edge_at(edges, i),
                   host.vendor_at(edges, i))
            n_at += 1
    if verbose:
        print(f"  fcn.10013960  edge-mark accessor     "
              f"{n_at:8d} lookups compared")

    n_v = 0
    for name, rec, edges, dc in valid_corpus():
        vr, vrec = host.vendor_valid(rec, edges, dc)
        prec = list(rec)
        pr = pf.vendor_candidate_valid(prec, edges, dc)
        # The record is an output: rejection zeroes it in place, and a port
        # that returned the right verdict without zeroing would still break
        # every caller.
        res.eq(f"valid[{name}]", (pr, prec), (vr, vrec))
        n_v += 1
    if verbose:
        print(f"  fcn.10006310  candidate validity     "
              f"{n_v:8d} candidates compared")

    # -- fcn.10006630 : the room-out-there predicate --------------------
    n_g = 0
    for name, recs, n_runs, a, b, slack in gapok_corpus():
        res.eq(f"gapok[{name}]",
               pf.vendor_gap_admissible(recs, n_runs, a, b, slack),
               host.vendor_gapok(recs, n_runs, a, b, slack))
        n_g += 1
    if verbose:
        print(f"  fcn.10006630  gap admissible         "
              f"{n_g:8d} cases compared")

    # -- fcn.100064e0 : the sliding-window search -----------------------
    n_w = n_ws = 0
    for name, win, n, data, start in bestwin_corpus():
        vr, vsums = host.vendor_bestwin(win, n, data, start)
        psums = [0] * max(n, 0)
        pr = pf.vendor_best_window(win, n, data, psums, start)
        res.eq(f"bestwin[{name}].pos", pr, vr)
        res.eq(f"bestwin[{name}].sums", psums, vsums)
        n_w += 1
        n_ws += len(vsums)
    if verbose:
        print(f"  fcn.100064e0  best-window search     "
              f"{n_w:8d} cases, {n_ws} sums compared")

    # -- fcn.10006ae0 / fcn.10006ca0 : phases 3 and 4 -------------------
    # Phase 4's backward search reads ``data[pos - pitch ...]``, so its
    # ``start``/``bound`` are pushed clear of the array's front rather than
    # letting the vendor read undefined memory. Everything else is shared.
    for label, addr, port in (
            ("atend", FN_ATEND, pf.vendor_look_at_end),
            ("atbeg", FN_ATBEG, pf.vendor_look_at_beginning)):
        n_p = n_ps = 0
        for (name, slots, data, records, n_runs, pitch, width, count_in,
             start, bound, skip, edges, dc) in phase34_corpus():
            if label == "atbeg":
                start, bound = bound, max(pitch, 0)
            vr, vslots, vcount = host.vendor_phase34(
                addr, slots, data, records, n_runs, pitch, width, count_in,
                start, bound, skip, edges, dc)
            pslots = [list(s) for s in slots]
            pcount = [count_in]
            psums = [0] * max(pitch - width, 1)
            pr = port(pslots, data, psums, records, n_runs, pitch, width,
                      pcount, start, bound, skip, edges, dc)
            res.eq(f"{label}[{name}]", (pr, pcount[0], pslots),
                   (vr, vcount, vslots))
            n_p += 1
            n_ps += len(vslots)
        if verbose:
            print(f"  {'fcn.10006ae0' if label == 'atend' else 'fcn.10006ca0'}"
                  f"  {'LookAtEnd           ' if label == 'atend' else 'LookAtBeginning     '}"
                  f"  {n_p:8d} cases, {n_ps} slots compared")

    # -- fcn.10005d20 : threshold choice + binarise ---------------------
    n_t = n_tb = 0
    for name, hist, trace, first, last, forced in thresh_corpus():
        vthr, vones = host.vendor_thresh(hist, trace, first, last, forced)
        pones = [0] * len(trace)
        pthr = pf.vendor_pick_threshold(pones, hist, trace, first, last,
                                        forced)
        res.eq(f"thresh[{name}]", (pthr, pones), (vthr, vones))
        # the fourth argument is never read: prove it rather than assert it
        vthr2, vones2 = host.vendor_thresh(hist, trace, first, last, forced,
                                           unused=0x5A5A5A5A)
        res.eq(f"thresh[{name}].arg3-unused", (vthr2, vones2), (vthr, vones))
        n_t += 1
        n_tb += len(vones)
    if verbose:
        print(f"  fcn.10005d20  threshold + binarise   "
              f"{n_t:8d} cases, {n_tb} lines binarised")

    # -- fcn.10006e70 : the four-phase cascade driver -------------------
    # This is the first check in this harness that is about the CASCADE and
    # not a part of it: one call, phases 1-4 in the vendor's own order, its
    # own bound-scan between 1 and 2, its own tag stamps and its own
    # SCAN_WARNINGS accumulator, all compared against the port's driver.
    n_d = n_ds = 0
    for (name, data, records, n_runs, lb, rb, n_slots, pitch, width, skip,
         ca4, edges, dc) in driver_corpus():
        slots = [[0, 0, 0] for _ in range(n_slots)]
        vr, vslots, vwarn = host.vendor_driver(
            slots, data, records, n_runs, lb, rb, n_slots, pitch, width,
            skip, ca4, edges, dc)
        pslots = [[0, 0, 0] for _ in range(n_slots)]
        psums = [0] * max(pitch - width, 1)
        pwarn = [0]
        pr = pf.vendor_framing_driver(pslots, data, psums, records, n_runs,
                                      lb, rb, n_slots, pitch, width, skip,
                                      pwarn, ca4, edges, dc)
        res.eq(f"driver[{name}]", (pr, pwarn[0], pslots),
               (vr, vwarn, vslots))
        n_d += 1
        n_ds += len(vslots)
    if verbose:
        print(f"  fcn.10006e70  cascade driver (1-4)   "
              f"{n_d:8d} cascades, {n_ds} slots compared")

    # -- fcn.100072c0 : the framing entry, end to end -------------------
    # From an object holding nothing but a per-line RGB summary through the
    # trace reduction, the histogram, BOTH threshold rules, the two-legged
    # threshold search and the whole four-phase cascade, in one call.
    n_e = n_es = 0
    for (name, rgb, n_slots, pitch, width, first, tail, skip, mode, ca4,
         edges, dc) in entry_corpus():
        vr, vslots, vwarn = host.vendor_entry(rgb, n_slots, pitch, width,
                                              first, tail, skip, mode, ca4,
                                              edges, dc)
        pslots = [[0, 0, 0] for _ in range(n_slots)]
        pwarn = [0]
        pr, _pones, _pt, _pn = pf.vendor_framing_entry(
            rgb, pslots, n_slots, pitch, width, first, tail, skip, pwarn,
            invert=(mode != 2), check_edges=ca4, edges=edges,
            no_edge_data=dc)
        res.eq(f"entry[{name}]", (pr, pwarn[0], pslots),
               (vr, vwarn, vslots))
        n_e += 1
        n_es += len(vslots)
    if verbose:
        print(f"  fcn.100072c0  framing entry (all)    "
              f"{n_e:8d} rolls, {n_es} slots compared")

    # -- fcn.100079c0 : the roll caller ---------------------------------
    # One call per roll, from an object holding a per-line RGB summary and a
    # crop rectangle to the CiPicLoc list the rest of TLB.dll consumes. Every
    # observable is compared: the return value, the whole list in order (all
    # six fields of every node, the constructor's tag->grade included),
    # this->0xc9c, this->0x6ca8 and how many times the error reporter fired.
    n_rc = n_rp = 0
    for name, kw in roll_corpus():
        vr, vpics, vcount, vwarn, verrs = host.vendor_roll(**kw)
        pwarn = [kw["warn_in"]]
        pr, ppics, pcount, perrs = pf.vendor_place_roll_pictures(
            kw["rgb_u8"], pwarn,
            skip_gapok=kw["skip_gapok"], place_blindly=kw["place_blindly"],
            no_tail_margin=kw["no_tail_margin"],
            n_lines=int(kw["rgb_u8"].shape[0]), line_scale=kw["line_scale"],
            image_rows=kw["image_rows"], margin_units=kw["margin_units"],
            pitch_raw=kw["pitch_raw"], width_raw=kw["width_raw"],
            margin_divisor=kw["margin_divisor"],
            crop_top=kw["crop"][0], crop_left=kw["crop"][1],
            crop_bottom=kw["crop"][2], crop_right=kw["crop"][3],
            frame_bottom=kw["frame_bottom"], end_anchored=kw["end_anchored"],
            pictures_in=kw["pictures_in"], count_in=kw["count_in"],
            malloc_fails=kw["malloc_fails"], new_fails_at=kw["new_fails_at"],
            invert=(kw["mode"] != 2), check_edges=kw["ca4"],
            edges=kw["edges"], no_edge_data=kw["dc"])
        res.eq(f"roll[{name}]",
               (pr, [tuple(p) for p in ppics], pcount, pwarn[0], perrs),
               (vr, [tuple(p) for p in vpics], vcount, vwarn, verrs))
        n_rc += 1
        n_rp += len(vpics)
    if verbose:
        print(f"  fcn.100079c0  roll caller (all)      "
              f"{n_rc:8d} rolls, {n_rp} pictures compared")


# --------------------------------------------------------------------------
# Mutation self-test
# --------------------------------------------------------------------------

MUTATIONS = []


def _mut(name, note=""):
    def deco(fn):
        MUTATIONS.append((name, note, fn))
        return fn
    return deco


@_mut("limits: 95/115 -> 96/115")
def _m1():
    orig = pf.vendor_limits
    pf.vendor_limits = lambda w: (pf._cdiv(w * 96, 100), pf._cdiv(w * 115, 100))
    return lambda: setattr(pf, "vendor_limits", orig)


@_mut("limits: truncate -> round")
def _m2():
    orig = pf.vendor_limits
    pf.vendor_limits = lambda w: (int(round(w * 0.95)), int(round(w * 1.15)))
    return lambda: setattr(pf, "vendor_limits", orig)


@_mut("bins: <= LoLim -> < LoLim")
def _m3():
    orig = pf.vendor_ones_runs

    def patched(ones, first, last, width):
        n, bins, recs = orig(ones, first, last, width)
        lo, hi = pf.vendor_limits(width)
        bins = [0, 0, 0]
        for k in range(n):
            L = recs[k][1]
            if L < lo:
                bins[2] += 1
            elif L >= hi:
                bins[1] += 1
            else:
                bins[0] += 1
        return n, bins, recs
    pf.vendor_ones_runs = patched
    return lambda: setattr(pf, "vendor_ones_runs", orig)


@_mut("runs: drop the ones[first]==n_runs early return")
def _m4():
    orig = pf.vendor_ones_runs

    def patched(ones, first, last, width):
        o = [int(v) for v in np.asarray(ones).ravel()]
        save = o[first]
        o[first] = -1 if save == 0 else save
        return orig(ones, first, last, width)
    # a genuine re-implementation without the early return
    def patched2(ones, first, last, width):
        o = [int(v) for v in np.asarray(ones).ravel()]
        n = o[first] + sum(1 for i in range(first, last) if o[i] < o[i + 1])
        recs = [[0, 0, 0] for _ in range(max(n, 0))]
        if n > 0:
            recs[0][0] = first
        prev, j, cur = o[first], 0, 1
        for i in range(first, last + 1):
            if o[i] == prev:
                cur += 1
            else:
                prev = o[i]
                if prev == 0:
                    recs[j][1] = cur
                    j += 1
                else:
                    recs[j][0] = i
                cur = 1
        if prev == 1 and n > 0:
            recs[j][1] = cur
        lo, hi = pf.vendor_limits(width)
        bins = [0, 0, 0]
        for k in range(n):
            L = recs[k][1]
            bins[2 if L <= lo else (1 if L >= hi else 0)] += 1
        return n, bins, recs
    pf.vendor_ones_runs = patched2
    return lambda: setattr(pf, "vendor_ones_runs", orig)


@_mut("runs: drop the trailing-run close-out")
def _m5():
    orig = pf.vendor_ones_runs

    def patched(ones, first, last, width):
        n, bins, recs = orig(ones, first, last, width)
        o = np.asarray(ones).ravel()
        if n > 0 and o[last]:
            recs = [list(r) for r in recs]
            recs[-1][1] = 0
        return n, bins, recs
    pf.vendor_ones_runs = patched
    return lambda: setattr(pf, "vendor_ones_runs", orig)


@_mut("nice: place at run.left, not left + (len-width)/3")
def _m6():
    orig = pf.vendor_look_for_nice_pictures

    def patched(records, n_runs, pitch, width, lb, rb, ce=0, ed=(), nd=0):
        recs = [[r[0], r[1], r[2] if len(r) > 2 else 0] for r in records]
        out, count = {}, 0
        lo, hi = pf.vendor_limits(width)
        for k in range(n_runs):
            left, length = recs[k][0], recs[k][1]
            if lo < length < hi:
                cands = [left]
            elif (lo + pitch) < length < (hi + pitch):
                cands = [left, left + pitch]
            else:
                continue
            for c in cands:
                if c <= lb:
                    c = lb + 1
                idx = pf._cdiv(2 * c, pitch)
                w = width if (c + width) < rb else (rb - c - 1)
                out[idx] = (c, w)
                count += 1
        return out, count
    pf.vendor_look_for_nice_pictures = patched
    return lambda: setattr(pf, "vendor_look_for_nice_pictures", orig)


@_mut("nice: (len-width)/3 with Python floor division")
def _m7():
    orig = pf._cdiv
    pf._cdiv = lambda a, b: a // b
    return lambda: setattr(pf, "_cdiv", orig)


@_mut("nice: slot index left/pitch instead of 2*left/pitch")
def _m8():
    orig = pf.vendor_look_for_nice_pictures

    def patched(records, n_runs, pitch, width, lb, rb, ce=0, ed=(), nd=0):
        out, count = orig(records, n_runs, pitch, width, lb, rb)
        return ({pf._cdiv(v[0], pitch): v for v in out.values()}, count)
    pf.vendor_look_for_nice_pictures = patched
    return lambda: setattr(pf, "vendor_look_for_nice_pictures", orig)


@_mut("nice: drop the double-frame branch entirely")
def _m9():
    orig = pf.vendor_look_for_nice_pictures

    def patched(records, n_runs, pitch, width, lb, rb, ce=0, ed=(), nd=0):
        recs = [r for r in records]
        out, count = {}, 0
        lo, hi = pf.vendor_limits(width)
        for k in range(n_runs):
            left, length = recs[k][0], recs[k][1]
            if lo < length < hi:
                c = left + pf._cdiv(length - width, 3)
                if c <= lb:
                    c = lb + 1
                idx = pf._cdiv(2 * c, pitch)
                w = width if (c + width) < rb else (rb - c - 1)
                out[idx] = (c, w)
                count += 1
        return out, count
    pf.vendor_look_for_nice_pictures = patched
    return lambda: setattr(pf, "vendor_look_for_nice_pictures", orig)


@_mut("trace: 255-avg -> 256-avg")
def _m10():
    orig = pf.vendor_framing_trace

    def patched(rgb, invert=True):
        v = orig(rgb, invert=invert)
        return (v + 1).astype(v.dtype) if invert else v
    pf.vendor_framing_trace = patched
    return lambda: setattr(pf, "vendor_framing_trace", orig)


@_mut("nice: right clamp uses >= rb, not > rb-1")
def _m11():
    orig = pf.vendor_look_for_nice_pictures

    def patched(records, n_runs, pitch, width, lb, rb, ce=0, ed=(), nd=0):
        out, count = {}, 0
        lo, hi = pf.vendor_limits(width)
        for k in range(n_runs):
            left, length = records[k][0], records[k][1]
            if lo < length < hi:
                cands = [left + pf._cdiv(length - width, 3)]
            elif (lo + pitch) < length < (hi + pitch):
                cands = [left + pf._cdiv(length - pitch - width, 3),
                         left + pitch]
            else:
                continue
            for c in cands:
                if c <= lb:
                    c = lb + 1
                idx = pf._cdiv(2 * c, pitch)
                w = width if (c + width) <= rb else (rb - c - 1)
                out[idx] = (c, w)
                count += 1
        return out, count
    pf.vendor_look_for_nice_pictures = patched
    return lambda: setattr(pf, "vendor_look_for_nice_pictures", orig)


@_mut("nice: make the film-edge validity test reject everything",
      "INERT BY CONSTRUCTION, and the most important disclosure here. The "
      "vendor calls fcn.10006310 only when this+0xca4 != 0; this harness "
      "drives the ca4 == 0 path, which is the path the port models, so no "
      "mutation of that test can be observed. The vendor's real behaviour "
      "there — validating each candidate against detected film edge marks "
      "(this+0x78 / this+0x8b4) and ZEROING the record when it fails — is "
      "read and documented but NOT ported and NOT verified. If a real "
      "F-135 scan runs with ca4 != 0 and dc == 0, phase 1 on real hardware "
      "places fewer frames than this port does, and nothing here would say "
      "so.")
def _m12():
    orig = pf.vendor_look_for_nice_pictures

    def patched(records, n_runs, pitch, width, lb, rb, ce=0, ed=(), nd=0):
        _out, _count = orig(records, n_runs, pitch, width, lb, rb)
        return {}, 0        # "every candidate rejected by the edge test"
    # deliberately NOT installed: the port has no edge-test hook to break.
    # Installing the above would trivially fail, which would be a lie about
    # coverage. Instead the port is left untouched, so this row must read
    # NOT CAUGHT — that is the honest answer.
    del patched
    return lambda: setattr(pf, "vendor_look_for_nice_pictures", orig)


@_mut("runs: report the allocation-failure return (-1)",
      "INERT: the vendor returns -1 and raises error 0xb1/0x8d only when its "
      "malloc (fcn.100479f2) fails. This harness's bump allocator cannot "
      "fail, so the whole failure limb of fcn.10006140 (0x100061be-0x100061e6) "
      "is unreachable under test and the port's silence about it is "
      "unverified rather than verified.")
def _m13():
    return lambda: None


@_mut("runs: zero the bins block on the refusal return")
def _m14():
    """The bug this port really had until the shared-block check was added."""
    orig = pf.vendor_ones_runs

    def patched(ones, first, last, width, bins=None, pp=None):
        n, b, recs = orig(ones, first, last, width, bins, pp)
        if n == 0 and bins is not None:
            bins[0] = bins[1] = bins[2] = 0
        return n, b, recs
    pf.vendor_ones_runs = patched
    return lambda: setattr(pf, "vendor_ones_runs", orig)


@_mut("between: left-edge span instead of centre-to-centre")
def _m15():
    orig = pf.vendor_look_in_between_ends

    def patched(slots, pitch, width, first, last):
        count = 0
        if first + 1 > last:
            return 0
        p = first
        for c in range(first + 1, last + 1):
            cl, cw = int(slots[c][0]), int(slots[c][1])
            if cl == 0 or cw == 0:
                continue
            pl = int(slots[p][0])
            span = cl - pl
            k = pf._cdiv(span, pitch)
            if (span - k * pitch) < pf._cdiv(pitch, 4):
                k -= 1
            if k > 0:
                step = pf._cdiv(span, k + 1)
                left = pl + step
                for _ in range(k):
                    slots[pf._cdiv(2 * left, pitch)][0] = left
                    slots[pf._cdiv(2 * left, pitch)][1] = width
                    count += 1
                    left += step
            p = c
        return count
    pf.vendor_look_in_between_ends = patched
    return lambda: setattr(pf, "vendor_look_in_between_ends", orig)


@_mut("between: step at the nominal pitch, not span/(k+1)")
def _m16():
    orig = pf.vendor_look_in_between_ends

    def patched(slots, pitch, width, first, last):
        count = 0
        if first + 1 > last:
            return 0
        p = first
        for c in range(first + 1, last + 1):
            cl, cw = int(slots[c][0]), int(slots[c][1])
            if cl == 0 or cw == 0:
                continue
            pl, pw = int(slots[p][0]), int(slots[p][1])
            span = cl + pf._cdiv(cw, 2) - pl - pf._cdiv(pw, 2)
            k = pf._cdiv(span, pitch)
            if (span - k * pitch) < pf._cdiv(pitch, 4):
                k -= 1
            left = pl + pitch
            for _ in range(max(k, 0)):
                slots[pf._cdiv(2 * left, pitch)][0] = left
                slots[pf._cdiv(2 * left, pitch)][1] = width
                count += 1
                left += pitch
            p = c
        return count
    pf.vendor_look_in_between_ends = patched
    return lambda: setattr(pf, "vendor_look_in_between_ends", orig)


@_mut("blind: let the loop-guard +4 compound into the pitch")
def _m17():
    orig = pf.vendor_blindly_place_pictures

    def patched(slots, pitch, width, n_lines, count_in=0):
        count = count_in
        half = pf._cdiv(pitch - width, 2)
        pos = placed = 0
        p = pitch
        remaining = n_lines - 1
        if remaining > 0:
            if (p + 4) < remaining:
                while True:
                    slots[placed][0] = pos + half
                    slots[placed][1] = width
                    remaining -= p
                    count += 1
                    pos += p
                    placed += 1
                    p += 4                       # the misreading
                    if not (remaining > p):
                        break
            if pf._cdiv(width, 2) < remaining:
                pos += half
                slots[placed][0] = pos
                slots[placed][1] = (n_lines - 1) - pos - 4
                count += 1
        for k in range(count):
            if slots[k][1] > 0 and slots[k][2] == 0:
                slots[k][2] = 9
        return count
    pf.vendor_blindly_place_pictures = patched
    return lambda: setattr(pf, "vendor_blindly_place_pictures", orig)


@_mut("blind: stamp tag 3 instead of 9")
def _m18():
    orig = pf.vendor_blindly_place_pictures

    def patched(slots, pitch, width, n_lines, count_in=0):
        c = orig(slots, pitch, width, n_lines, count_in)
        for k in range(c):
            if slots[k][2] == 9:
                slots[k][2] = 3
        return c
    pf.vendor_blindly_place_pictures = patched
    return lambda: setattr(pf, "vendor_blindly_place_pictures", orig)


@_mut("bestwin: compare sums signed instead of unsigned")
def _m19():
    orig = pf.vendor_best_window

    def patched(win, n, data, sums, start):
        half = pf._cdiv(n, 2)
        best_sum = 0
        best_pos = 0
        best_w = half
        for i in range(n):
            w = (i - half) if i > half else (half - i)
            s = sum(int(data[start + i + j]) for j in range(win))
            s &= 0xFFFFFFFF
            sv = s if s < 0x80000000 else s - 0x100000000
            sums[i] = sv
            if sv > best_sum or (sv == best_sum and w < best_w):
                best_sum, best_pos, best_w = sv, start + i, w
        return start + half if best_sum == 0 else best_pos
    pf.vendor_best_window = patched
    return lambda: setattr(pf, "vendor_best_window", orig)


@_mut("bestwin: break ties toward the first offset, not the centre")
def _m20():
    orig = pf.vendor_best_window

    def patched(win, n, data, sums, start):
        best_sum = 0
        best_pos = 0
        for i in range(n):
            s = sum(int(data[start + i + j]) for j in range(win)) & 0xFFFFFFFF
            sums[i] = s if s < 0x80000000 else s - 0x100000000
            if s > best_sum:
                best_sum, best_pos = s, start + i
        return start + pf._cdiv(n, 2) if best_sum == 0 else best_pos
    pf.vendor_best_window = patched
    return lambda: setattr(pf, "vendor_best_window", orig)


@_mut("validity: return the verdict but stop zeroing the rejected record")
def _m21():
    orig = pf.vendor_candidate_valid

    def patched(rec, edges, no_edge_data=0):
        keep = list(rec)
        r = orig(rec, edges, no_edge_data)
        if r == 0:
            rec[0], rec[1] = keep[0], keep[1]
        return r
    pf.vendor_candidate_valid = patched
    return lambda: setattr(pf, "vendor_candidate_valid", orig)


@_mut("validity: last mark's partner clamps instead of reading 0")
def _m22():
    orig = pf.vendor_edge_at
    pf.vendor_edge_at = (lambda edges, i:
                         int(edges[min(i, len(edges) - 1)]) if len(edges)
                         else 0)
    return lambda: setattr(pf, "vendor_edge_at", orig)


@_mut("gapok: 20*slack -> 2*slack in the forward limb")
def _m23():
    orig = pf.vendor_gap_admissible

    def patched(records, n_runs, a, b, slack):
        return orig(records, n_runs, a, b, slack // 10 if b > a else slack)
    pf.vendor_gap_admissible = patched
    return lambda: setattr(pf, "vendor_gap_admissible", orig)


@_mut("atend: stop clipping the frame at right_bound")
def _m24():
    orig = pf.vendor_look_at_end

    def patched(slots, data, sums, records, n_runs, pitch, width, count,
                start, right_bound, skip_gapok, edges=(), no_edge_data=0):
        return orig(slots, data, sums, records, n_runs, pitch, width, count,
                    start, right_bound + 10 ** 6, skip_gapok, edges,
                    no_edge_data)
    pf.vendor_look_at_end = patched
    return lambda: setattr(pf, "vendor_look_at_end", orig)


@_mut("atbeg: clip the searched frame the way atend does")
def _m25():
    orig = pf.vendor_look_at_beginning

    def patched(slots, data, sums, records, n_runs, pitch, width, count,
                start, left_bound, skip_gapok, edges=(), no_edge_data=0):
        r = orig(slots, data, sums, records, n_runs, pitch, width, count,
                 start, left_bound, skip_gapok, edges, no_edge_data)
        for s in slots:
            if s[0] and s[1] and s[0] < left_bound + width:
                s[1] = max(s[1] - 1, 0)
        return r
    pf.vendor_look_at_beginning = patched
    return lambda: setattr(pf, "vendor_look_at_beginning", orig)


@_mut("driver: number the phase tags 1,2,3,4 instead of 1,2,4,3")
def _m26():
    orig = pf.vendor_framing_driver

    def patched(slots, *a, **k):
        r = orig(slots, *a, **k)
        for s in slots:
            if s[2] == 3:
                s[2] = 4
            elif s[2] == 4:
                s[2] = 3
        return r
    pf.vendor_framing_driver = patched
    return lambda: setattr(pf, "vendor_framing_driver", orig)


@_mut("driver: run phase 2 whenever phase 1 found anything (>=1, not >=2)")
def _m27():
    orig = pf.vendor_look_in_between_ends
    state = {"n": 0}

    def patched(slots, pitch, width, first, last):
        state["n"] += 1
        return orig(slots, pitch, width, max(first - 1, 0), last)
    pf.vendor_look_in_between_ends = patched
    return lambda: setattr(pf, "vendor_look_in_between_ends", orig)


@_mut("threshold: count/150 by rounding instead of the real 0x1B4E81B5>>36")
def _m28():
    orig = pf.vendor_pick_threshold

    def patched(ones, hist, trace, first, last, forced):
        if forced == 0:
            count = pf._u32(last - first + 1)
            t = pf._pick_threshold_modal(hist, (count + 75) // 150)
            if first <= last:
                for i in range(first, first + count):
                    ones[i] = 1 if pf._u32(t) < pf._u32(trace[i]) else 0
            return t
        return orig(ones, hist, trace, first, last, forced)
    pf.vendor_pick_threshold = patched
    return lambda: setattr(pf, "vendor_pick_threshold", orig)


@_mut("threshold: binarise with >= instead of >")
def _m29():
    orig = pf.vendor_pick_threshold

    def patched(ones, hist, trace, first, last, forced):
        t = orig(ones, hist, trace, first, last, forced)
        count = pf._u32(last - first + 1)
        if first <= last:
            for i in range(first, first + count):
                ones[i] = 1 if pf._u32(t) <= pf._u32(trace[i]) else 0
        return t
    pf.vendor_pick_threshold = patched
    return lambda: setattr(pf, "vendor_pick_threshold", orig)


@_mut("threshold: 2nd percentile per-bin instead of cumulative")
def _m30():
    orig = pf._pick_threshold_percentile

    def patched(hist):
        total = sum(pf._u32(v) for v in hist[:256])
        limit = pf._round_f32(total * pf._THRESH_PCT_NUM, pf._THRESH_PCT_DEN)
        for i in range(250):
            if pf._u32(hist[i]) > limit:
                return i
        return 250
    pf._pick_threshold_percentile = patched
    return lambda: setattr(pf, "_pick_threshold_percentile", orig)


def _entry_variant(turnaround_uses_best=False, reset_best_at_turnaround=False,
                   down_step=-2, up_cap=250):
    """A knowingly-wrong ``fcn.100072c0``, for the mutation rows below.

    Same body as ``pf.vendor_framing_entry`` with one decision changed, so a
    failure localises to that decision instead of to "the entry differs".
    """
    def entry(rgb_u8, slots, n_slots, pitch, width, first, tail_margin,
              skip_gapok, warn, invert=1, check_edges=0, edges=(),
              no_edge_data=0):
        n_lines = len(rgb_u8)
        trace = [int(v) for v in pf.vendor_framing_trace(rgb_u8,
                                                         invert=bool(invert))]
        ones = [0] * n_lines
        sums = [0] * n_lines
        last = n_lines - tail_margin - 1
        hist = [int(v) for v in pf.vendor_line_histogram(np.asarray(trace),
                                                         first, last)]
        bins = [0, 0, 0]
        pp = [[]]

        def extract():
            return pf.vendor_ones_runs(ones, first, last, width, bins, pp)[0]

        def binarise(forced):
            return pf.vendor_pick_threshold(ones, hist, trace, first, last,
                                            forced)

        t0 = binarise(0)
        n = extract()
        if n < 2:
            if n < 0:
                return -1, ones, t0, n
            t0 = binarise(-1)
        else:
            n = extract()
            if n == 0:
                return 0, ones, t0, n
            if n < 0:
                return -1, ones, t0, n
        best_t = t0
        best_bins0 = plateau = bins[0]
        t = t0
        if t > 0:
            while True:
                if t >= up_cap or bins[1] <= 0:
                    break
                t = binarise(t + 2)
                n = extract()
                if n < 0:
                    return -1, ones, t, n
                if bins[0] > best_bins0:
                    best_bins0 = plateau = bins[0]
                    best_t = t
                elif bins[0] < plateau:
                    break
                if t <= 0:
                    break
        t = binarise(best_t if turnaround_uses_best else t0)
        n = extract()
        if n < 0:
            return -1, ones, t, n
        plateau = bins[0]
        if reset_best_at_turnaround:
            best_bins0 = bins[0]
        if t > 25:
            while True:
                if t >= 256:
                    break
                if not (bins[2] > 0 or n <= 1):
                    break
                t = binarise(t + down_step)
                n = extract()
                if n < 0:
                    return -1, ones, t, n
                if bins[0] > best_bins0:
                    best_t = t
                    best_bins0 = plateau = bins[0]
                elif bins[0] < plateau:
                    break
                if t <= 25:
                    break
        t = binarise(best_t)
        n_runs = extract()
        if n_runs < 0:
            return -1, ones, t, n_runs
        ret = pf.vendor_framing_driver(slots, ones, sums, pp[0], n_runs, first,
                                       last, n_slots, pitch, width,
                                       skip_gapok, warn, check_edges, edges,
                                       no_edge_data)
        return ret, ones, t, n_runs
    return entry


@_mut("entry: turn around from the BEST threshold, not the initial one")
def _m31():
    orig = pf.vendor_framing_entry
    pf.vendor_framing_entry = _entry_variant(turnaround_uses_best=True)
    return lambda: setattr(pf, "vendor_framing_entry", orig)


@_mut("entry: also reset the best count at the turnaround")
def _m32():
    orig = pf.vendor_framing_entry
    pf.vendor_framing_entry = _entry_variant(reset_best_at_turnaround=True)
    return lambda: setattr(pf, "vendor_framing_entry", orig)


@_mut("entry: step the second leg upward too (+2, not -2)")
def _m33():
    orig = pf.vendor_framing_entry
    pf.vendor_framing_entry = _entry_variant(down_step=+2)
    return lambda: setattr(pf, "vendor_framing_entry", orig)


@_mut("entry: cap the upward leg at 256 like the downward one")
def _m34():
    orig = pf.vendor_framing_entry
    pf.vendor_framing_entry = _entry_variant(up_cap=256)
    return lambda: setattr(pf, "vendor_framing_entry", orig)


def _roll_variant(*, slot_factor=2, guard_lt=False, keep_left_zero=False,
                  margin_mul=10, ignore_no_tail=False,
                  anchored_computes_margin=False, no_warn_bit=False,
                  no_double_count=False, partial_left_lt=5,
                  partial_len_le=False, partial_len_signed=False,
                  partial_adds_crop_top=False,
                  span_mul=16, swap_stretch=False, bottom_after_clamp=False,
                  bottom_off_by_one=False, no_slots_clears_list=False):
    """``pf.vendor_place_roll_pictures`` with one decision deliberately wrong.

    A transcription of the port with knobs, the same shape ``_entry_variant``
    uses for ``fcn.100072c0``. Keeping it a separate body rather than a set of
    wrappers is what lets a mutation reach a decision that is inline in the
    loop and has no seam to wrap.
    """
    def roll(rgb_u8, warn, *, skip_gapok, place_blindly, no_tail_margin,
             n_lines, line_scale, image_rows, margin_units, pitch_raw,
             width_raw, margin_divisor, crop_top, crop_left, crop_bottom,
             crop_right, frame_bottom, end_anchored, pictures_in=(),
             count_in=0, malloc_fails=False, new_fails_at=None, invert=1,
             check_edges=0, edges=(), no_edge_data=0):
        i32, u32, udiv = pf._i32, pf._u32, pf._udiv
        pictures = list(pictures_in)
        count = int(count_in)
        pitch = udiv(pitch_raw, line_scale)
        width = udiv(width_raw, line_scale)
        n_slots = udiv(u32(slot_factor * u32(n_lines)), pitch)
        if (i32(n_slots) < 0) if guard_lt else (i32(n_slots) <= 0):
            return 0, ([] if no_slots_clears_list else pictures), count, 0
        pictures = []
        count = 0
        if malloc_fails:
            return -1, pictures, count, 1
        slots = [[0, 0, 0] for _ in range(n_slots)]
        n_new = 0

        def build(top, bottom, tag):
            nonlocal n_new
            k, n_new = n_new, n_new + 1
            if new_fails_at is not None and k == new_fails_at:
                return False
            pictures.append((i32(top), i32(crop_left), i32(bottom),
                             i32(crop_right), i32(tag),
                             pf.vendor_picloc_grade(tag)))
            return True

        first = tail = 0
        if (not end_anchored) or anchored_computes_margin:
            if u32(margin_mul * pitch) < u32(n_lines):
                first = udiv(u32(margin_units * 0x6338), margin_divisor)
                if ignore_no_tail or not no_tail_margin:
                    tail = first
        if place_blindly:
            if not no_warn_bit:
                warn[0] = i32(u32(warn[0]) | 0x800)
            n = pf.vendor_blindly_place_pictures(slots, pitch, width, n_lines,
                                                 count)
            count = count if no_double_count else n
        else:
            rc = pf.vendor_framing_entry(rgb_u8, slots, n_slots, pitch, width,
                                         first, tail, skip_gapok, warn,
                                         invert=invert,
                                         check_edges=check_edges, edges=edges,
                                         no_edge_data=no_edge_data)[0]
            if rc < 0:
                return -1, pictures, count, 1

        height = i32(crop_bottom - crop_top + 1)
        bottom_margin = i32(frame_bottom - crop_bottom)
        span = i32(line_scale * span_mul)
        for left, length, tag in slots:
            if length == 0:
                continue
            if left == 0 and not keep_left_zero:
                continue
            if partial_len_le:
                short = u32(length) <= u32(width)
            elif partial_len_signed:
                short = i32(length) < i32(width)
            else:
                short = u32(length) < u32(width)
            if end_anchored and short and i32(left) < partial_left_lt:
                bottom = i32(i32(line_scale * i32(left + length))
                             - bottom_margin)
                if partial_adds_crop_top:
                    bottom = i32(bottom + crop_top)
                top = i32(bottom - height)
            else:
                top = i32(line_scale * left + crop_top)
                bottom = i32(top + height - 1)
            if top < 0:
                top = 0
                if bottom_after_clamp:
                    bottom = i32(top + height - 1)
            if not i32(image_rows) > bottom:
                bottom = i32(image_rows if bottom_off_by_one
                             else image_rows - 1)
            if end_anchored and not i32(bottom - top) >= span:
                down = i32(left) < 5
                if down != swap_stretch:
                    bottom = i32(top + span)
                else:
                    top = i32(bottom - span)
            if not build(top, bottom, tag):
                return -1, [], count, 1
            count = i32(count + 1)
        return count, pictures, count, 0
    return roll


def _roll_mut(name, note="", **kw):
    def factory():
        orig = pf.vendor_place_roll_pictures
        pf.vendor_place_roll_pictures = _roll_variant(**kw)
        return lambda: setattr(pf, "vendor_place_roll_pictures", orig)
    MUTATIONS.append((name, note, factory))


_roll_mut("roll: n_slots = n_lines/pitch, not 2*n_lines/pitch", slot_factor=1)
_roll_mut("roll: bail out on n_slots < 0, not <= 0", guard_lt=True)
_roll_mut("roll: keep the slots whose left edge is 0", keep_left_zero=True)
_roll_mut("roll: margin gate at 9*pitch, not 10*pitch", margin_mul=9)
_roll_mut("roll: ignore argument 3 (tail margin always = head margin)",
          ignore_no_tail=True)
_roll_mut("roll: end-anchored model computes a margin too",
          anchored_computes_margin=True)
_roll_mut("roll: blind path does not OR the 0x800 warning", no_warn_bit=True)
_roll_mut("roll: blind path does not double-count this->0xc9c",
          no_double_count=True)
_roll_mut(
    "roll: leading-partial limb needs left < 1, not left < 5",
    "the constant itself is only partly falsifiable — see the note below",
    partial_left_lt=1)
_roll_mut("roll: leading-partial length test <=, not <", partial_len_le=True)
_roll_mut(
    "roll: leading-partial length test signed, not unsigned",
    "INERT, and provably so rather than for want of trying. 0x10007deb is "
    "`jae`, i.e. unsigned, and 0x10007df0 is `jge`, i.e. signed — but a slot "
    "length and a slot left edge are both written by the cascade and both are "
    "non-negative in every reachable state, so the two readings cannot "
    "disagree. The port follows the instructions; the corpus cannot confirm "
    "it, and no corpus can.",
    partial_len_signed=True)
_roll_mut("roll: leading-partial bottom adds crop_top",
          partial_adds_crop_top=True)
_roll_mut("roll: minimum height 15*line_scale, not 16*", span_mul=15)
_roll_mut("roll: minimum-height stretch direction swapped", swap_stretch=True)
_roll_mut("roll: bottom computed after the top clamp, not before",
          bottom_after_clamp=True)
_roll_mut("roll: bottom clamped to image_rows, not image_rows - 1",
          bottom_off_by_one=True)


@_mut("roll: CiPicLoc grade table shifted (tag 9 -> 3)")
def _m50():
    orig = pf.vendor_picloc_grade
    pf.vendor_picloc_grade = lambda t: {2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 3,
                                        8: 3, 9: 3}.get(pf._i32(t), 0)
    return lambda: setattr(pf, "vendor_picloc_grade", orig)


@_mut("roll: phase-1 tag 1 grades as 1, not 0")
def _m51():
    orig = pf.vendor_picloc_grade
    pf.vendor_picloc_grade = lambda t: {1: 1, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2,
                                        7: 3, 8: 3, 9: 4}.get(pf._i32(t), 0)
    return lambda: setattr(pf, "vendor_picloc_grade", orig)


def mutate(host: TlbHost) -> int:
    print("\nmutation self-test — each row breaks the port on purpose\n")
    not_caught = []
    for name, note, factory in MUTATIONS:
        undo = factory()
        try:
            res = Result()
            try:
                run_all(host, res, verbose=False)
            except Exception as exc:                    # noqa: BLE001
                res.fails.append(f"raised {type(exc).__name__}: {exc}")
            caught = bool(res.fails)
        finally:
            undo()
        if caught:
            first = res.fails[0]
            if len(first) > 88:
                first = first[:85] + "..."
            print(f"  CAUGHT      {name}")
            print(f"              {len(res.fails)} check(s); first: {first}")
        else:
            not_caught.append((name, note))
            print(f"  NOT CAUGHT  {name}")
            if note:
                print(f"              {note}")
    print()
    real = [n for n, note in not_caught if not note.startswith("INERT")]
    print(f"{len(MUTATIONS) - len(not_caught)} CAUGHT, "
          f"{len(not_caught) - len(real)} PROVABLY INERT (see notes), "
          f"{len(real)} NOT CAUGHT")
    if real:
        print("NOT CAUGHT and not explained: " + ", ".join(real))
        return 1
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def find_dll(explicit: str | None) -> Path:
    cands = [explicit] if explicit else list(DEFAULT_DLL_CANDIDATES)
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    raise SystemExit(
        "TLB.dll not found. Pass --dll. Expected md5 " + TLB_MD5)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dll", default=None)
    ap.add_argument("--mutate", action="store_true")
    args = ap.parse_args(argv)

    dll = find_dll(args.dll)
    host = TlbHost(dll)
    print(f"TLB.dll {dll}")
    print(f"  md5 {host.md5}"
          f"{'  (expected)' if host.md5 == TLB_MD5 else '  *** NOT the DLL this harness was written against ***'}")
    print(f"  base 0x{IMAGE_BASE:08x}, executing real vendor code under Unicorn\n")

    res = Result()
    run_all(host, res)
    print()
    if res.fails:
        print(f"{len(res.fails)} of {res.checks} checks FAILED:")
        for f in res.fails[:20]:
            print("  " + f)
        if len(res.fails) > 20:
            print(f"  ... and {len(res.fails) - 20} more")
        return 1
    print(f"all {res.checks} checks bit-exact against the real DLL")
    print(f"  pakon_framing.FRAMING_PORTED              = {pf.FRAMING_PORTED}"
          "   (the cascade as a whole: NOT verified)")
    print(f"  pakon_framing.VENDOR_TRACE_PORTED         = {pf.VENDOR_TRACE_PORTED}")
    print(f"  pakon_framing.VENDOR_HISTOGRAM_PORTED     = {pf.VENDOR_HISTOGRAM_PORTED}")
    print(f"  pakon_framing.VENDOR_RUNS_PORTED          = {pf.VENDOR_RUNS_PORTED}")
    print(f"  pakon_framing.VENDOR_NICE_PICTURES_PORTED = {pf.VENDOR_NICE_PICTURES_PORTED}")
    print(f"  pakon_framing.VENDOR_IN_BETWEEN_PORTED    = {pf.VENDOR_IN_BETWEEN_PORTED}")
    print(f"  pakon_framing.VENDOR_BLIND_PORTED         = {pf.VENDOR_BLIND_PORTED}")
    print(f"  pakon_framing.VENDOR_AT_END_PORTED        = {pf.VENDOR_AT_END_PORTED}")
    print(f"  pakon_framing.VENDOR_AT_BEGINNING_PORTED  = {pf.VENDOR_AT_BEGINNING_PORTED}")
    print(f"  pakon_framing.VENDOR_EDGE_VALIDITY_PORTED = {pf.VENDOR_EDGE_VALIDITY_PORTED}")
    print(f"  pakon_framing.VENDOR_GAP_ADMISSIBLE_PORTED= {pf.VENDOR_GAP_ADMISSIBLE_PORTED}")
    print(f"  pakon_framing.VENDOR_BEST_WINDOW_PORTED   = {pf.VENDOR_BEST_WINDOW_PORTED}")
    print(f"  pakon_framing.VENDOR_EDGE_AT_PORTED       = {pf.VENDOR_EDGE_AT_PORTED}")
    print(f"  pakon_framing.VENDOR_CASCADE_DRIVER_PORTED= {pf.VENDOR_CASCADE_DRIVER_PORTED}")
    print(f"  pakon_framing.VENDOR_THRESHOLD_PORTED     = {pf.VENDOR_THRESHOLD_PORTED}")
    print(f"  pakon_framing.VENDOR_ENTRY_PORTED         = {pf.VENDOR_ENTRY_PORTED}")
    print(f"  pakon_framing.VENDOR_ROLL_PICTURES_PORTED = "
          f"{pf.VENDOR_ROLL_PICTURES_PORTED}")

    if args.mutate:
        return mutate(host)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
