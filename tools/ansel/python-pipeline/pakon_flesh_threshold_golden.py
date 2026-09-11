#!/usr/bin/env python3
"""Golden FLESH **threshold chooser** vs the real PakonIMAu.dll (Unicorn).

`pakon_flesh_golden.py` proved the adjust arithmetic and
`pakon_flesh_detector_golden.py` proved the detector's LST/probability/
reduction blocks.  Both reported the same hole: `fcn.1029ec50`, the function
that turns the int16 0..255 probability plane into (a) a binary plane and
(b) the **integer threshold** that reaches ``results+0x28``.  Without that
integer the reduction loop has no threshold and `Delta` cannot be computed
forward from pixels.  This harness closes it.

Unlike the two earlier harnesses, which execute *ranges* of DLL bytes, this
one runs **the whole of `fcn.1029ec50`** — all 3575 bytes, its C++ image
classes, its convolutions, its `malloc`/`free` — inside Unicorn, and diffs
the answer against `pakon_flesh`'s port.  Making that possible needs three
things, all of which are stated here rather than hidden:

1. **A GDT**, so `fs:[0]` works and the SEH prologues of `fcn.1029ec50`,
   `fcn.1029cad0`, `fcn.104f3470`, `fcn.104dcbc0` … run unmodified.
2. **The import table redirected** to a trap page.  `malloc` / `calloc` /
   `free` / `operator new[]` / `operator delete[]` are serviced by a bump
   allocator, and `std::basic_string<char>`'s ctor/dtor/assign by a
   16-byte-SSO implementation matching MSVC7.1's layout (`_Bx` at +8,
   `_Mysize` at +0x18, `_Myres` at +0x1c — read straight out of the DLL's own
   ``cmp dword [x+0x1c], 0x10 / mov eax,[x+8]`` c_str() inlines).  Those
   strings only ever carry the debug text the vendor attaches to images
   (``"return convolve(inT, kernel)"``, ``"return inT1 + inT2"``), so they
   cannot affect an arithmetic result; nothing else is stubbed.
3. **Three `.data` singletons** — ``0x106c8250`` / ``0x106c8294`` /
   ``0x106c82d8`` — pointed at fabricated type tags.  The DLL reads only
   their first dword (`fcn.1008cd60` is literally ``mov eax,[ecx]; ret``) and
   dispatches on it: 2 -> 1 byte per sample, 3 -> 2 bytes (`fcn.104f2be0`
   ``shl ecx,1``), 4 -> 4 bytes (`fcn.104f2c60` ``shl ecx,2``).  The harness
   asserts the resulting row stride to prove it picked the right one instead
   of assuming.

Everything else — the Sobel convolutions, the abs/add/threshold maps, the
neighbour cleanup, the histogram, the smoothing, the peak/valley search and
the final ``mov dword [eax], ebp`` — is the vendor's own code.

What this proves, and what it does not
--------------------------------------

Proves, bit-exact against the DLL:

* `flesh_convolve` — the 3x3 correlation *and* its out-of-range index policy
  (reflection that does not repeat the edge sample), over random planes.
* `flesh_edge_clean` (`fcn.1029cad0`) — every pixel, including the zeroed
  border and the asymmetric ``== 0`` / ``> 0`` neighbour tests.
* `flesh_edge_mask` — the whole chain down to the byte mask the histogram is
  taken over, read out of guest memory at `0x1029f4c3`.
* `flesh_histogram` / `flesh_smooth_histogram` — all 64 float32 bins, read out
  of guest memory, including the two bins overwritten with zero.
* `flesh_threshold_from_plane` — the integer the vendor stores through arg4.
* `flesh_binarise` — the byte plane `fcn.1029ec50` returns.
* `flesh_prob_to_int16` — the ``* 255.0`` and the float->int16 cast that feed
  it (`0x104e2960` / `0x104de680`); the cast truncates toward zero and does
  not clamp, which section [1c] shows rather than assumes.

Does **not** prove, and this port still does not have:

* **[closed since]** the two 1-D LUT pre-passes at `0x10270920` /
  `0x10270b10` and the reduction's weight plane (`fcn.10271bc0`'s Gaussian,
  padded by `0x104e7880`) are both ported and bit-exact — see
  `pakon_flesh_weight_golden.py`.  `0x104e8360` turned out to be dead on the
  shipped DPI (`useSmallAnalysisImage = 0`) and `0x1014cc20` a type-checked
  handle wrapper.  The BOUNDARY beyond them has since been read through:
  `fcn.10270280`'s arg3/arg4 are two `AnsImageData::copyToIemImage`
  (`fcn.100db520`) copies of the SAME image — the scene's analysis image at
  `scene+0x04`, pushed twice by `analyzePostBalance` at
  `0x100fe396`/`0x100fe397` (tier 3; see `pakon_flesh.py`'s header);
* the *composition* `flesh_reduction_plane` — that `fcn.102a1500` copies
  `fcn.1029ec50`'s binary output, re-cleaned, into its arg2 — which is read
  out of `0x102a1e13 … 0x102a215e` and is tier 3, not executed here;
* `fcn.10270280`'s arg7, the `float` exposure the ``exposureLimit`` guard
  reads;
* the ``useAdvanced != 0`` and ``mode != 2`` branches of `fcn.1029ec50`
  itself — asserted unreachable on the shipped DPI, not ported;
* the store rounding of `flesh_convolve`.  With the shipped integer Sobel
  kernels every sum is exact, so the rule is **unobservable on this path**;
  section [1b] probes it with a deliberately fractional kernel and reports
  what the DLL does, as a fact about the DLL rather than as something the
  port depends on.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \\
    tools/ansel/python-pipeline/pakon_flesh_threshold_golden.py [PakonIMAu.dll]``
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_CS,
    UC_X86_REG_DS,
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ES,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
    UC_X86_REG_FPCW,
    UC_X86_REG_FS,
    UC_X86_REG_GDTR,
    UC_X86_REG_GS,
    UC_X86_REG_SS,
)

import pakon_flesh as fl

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x00400000
HEAP_ADDR = 0x30000000
HEAP_SIZE = 0x08000000
FS_ADDR = 0x40000000
TRAP_ADDR = 0x50000000
GDT_ADDR = 0x60000000
RETURN_MAGIC = 0x7FFF0000
FPCW_WIN32 = 0x027F

#: The three `.data` singletons whose first dword is the element-type tag.
G_TYPE_I16 = 0x106C8250
G_TYPE_U8 = 0x106C8294
G_TYPE_F32 = 0x106C82D8
TYPE_TAG_U8 = 2
TYPE_TAG_I16 = 3
TYPE_TAG_F32 = 4

#: `fcn.1029ec50` frame offsets, relative to the body ESP (i.e. after the
#: five prologue pushes and ``sub esp, 0x2d8``).  Every one of these is a
#: literal ``[esp+N]`` in the raw disassembly.
F_WIDTH = 0x10
F_HEIGHT = 0x14
F_HIST = 0x18
F_MASK_IMAGE_DATA = 0x48
F_SMOOTH = 0x4C
F_MASK_PLANE_DATA = 0x68
F_ARG2 = 0x2FC
F_ARG3 = 0x300
F_ARG5 = 0x308

DEFAULT_DLL = (
    Path(__file__).resolve().parents[2] / "re" / "live_hooks" / "wine_host" / "PakonIMAu.dll"
)

_STR = "?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@"


def _align_up(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


def _gdt_entry(base: int, limit: int, access: int, flags: int) -> bytes:
    v = limit & 0xFFFF
    v |= (base & 0xFFFFFF) << 16
    v |= (access & 0xFF) << 40
    v |= ((limit >> 16) & 0xF) << 48
    v |= (flags & 0xF) << 52
    v |= ((base >> 24) & 0xFF) << 56
    return struct.pack("<Q", v)


class Guest:
    """A loaded PakonIMAu with a working CRT surface."""

    def __init__(self, pe: bytes) -> None:
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        e = struct.unpack_from("<I", pe, 0x3C)[0]
        nsec = struct.unpack_from("<H", pe, e + 6)[0]
        optsz = struct.unpack_from("<H", pe, e + 20)[0]
        opt = e + 24
        uc.mem_map(IMAGE_BASE, _align_up(struct.unpack_from("<I", pe, opt + 56)[0]))
        uc.mem_write(IMAGE_BASE, pe[:0x1000])
        self.secs = []
        for i in range(nsec):
            o = opt + optsz + i * 40
            vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
            self.secs.append((va, max(vsz, rsz), raddr))
            if rsz == 0 or raddr == 0:
                continue
            d = pe[raddr : raddr + rsz]
            if len(d) < vsz:
                d += b"\0" * (vsz - len(d))
            uc.mem_write(IMAGE_BASE + va, d[: max(vsz, rsz)])
        uc.mem_map(STACK_ADDR, STACK_SIZE)
        uc.mem_map(HEAP_ADDR, HEAP_SIZE)
        uc.mem_map(FS_ADDR, 0x1000)
        uc.mem_map(TRAP_ADDR, 0x1000)
        uc.mem_map(GDT_ADDR, 0x1000)
        self._setup_gdt()
        uc.reg_write(UC_X86_REG_FPCW, FPCW_WIN32)
        self._brk = HEAP_ADDR + 0x1000
        self.traps: dict[int, str] = {}
        self._patch_imports(pe, opt)
        uc.hook_add(UC_HOOK_CODE, self._trap, begin=TRAP_ADDR, end=TRAP_ADDR + 0x1000)
        self._setup_type_singletons()

    # -- machine plumbing ---------------------------------------------------

    def _setup_gdt(self) -> None:
        uc = self.uc
        ent = [b"\0" * 8] * 8
        ent[1] = _gdt_entry(0, 0xFFFFF, 0x9B, 0xC)  # flat code
        ent[2] = _gdt_entry(0, 0xFFFFF, 0x93, 0xC)  # flat data
        ent[3] = _gdt_entry(FS_ADDR, 0xFFF, 0x93, 0x4)  # fs -> the SEH page
        uc.mem_write(GDT_ADDR, b"".join(ent))
        uc.reg_write(UC_X86_REG_GDTR, (0, GDT_ADDR, 8 * 8 - 1, 0))
        uc.reg_write(UC_X86_REG_CS, 1 << 3)
        for r in (UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_GS):
            uc.reg_write(r, 2 << 3)
        uc.reg_write(UC_X86_REG_FS, 3 << 3)

    def _rva2off(self, r: int):
        for va, sz, raddr in self.secs:
            if va <= r < va + sz:
                return raddr + (r - va)
        return None

    def _patch_imports(self, pe: bytes, opt: int) -> None:
        off = self._rva2off(struct.unpack_from("<I", pe, opt + 104)[0])
        i = n = 0
        while True:
            d = struct.unpack_from("<IIIII", pe, off + i * 20)
            if d == (0, 0, 0, 0, 0):
                break
            oft, _, _, name_rva, first = d
            lut = oft or first
            j = 0
            while True:
                ent = struct.unpack_from("<I", pe, self._rva2off(lut) + j * 4)[0]
                if ent == 0:
                    break
                if ent & 0x80000000:
                    nm = "#%d" % (ent & 0xFFFF)
                else:
                    q = self._rva2off(ent) + 2
                    nm = pe[q : pe.index(b"\0", q)].decode()
                addr = TRAP_ADDR + n * 8
                self.traps[addr] = nm
                self.uc.mem_write(IMAGE_BASE + first + j * 4, struct.pack("<I", addr))
                n += 1
                j += 1
            i += 1
        self.n_imports = n

    def _trap(self, uc, addr, size, ud) -> None:
        nm = self.traps.get(addr)
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        args = struct.unpack("<8I", uc.mem_read(esp + 4, 32))
        h = self._handlers().get(nm)
        if h is None:
            raise RuntimeError(
                "fcn.1029ec50 reached an unstubbed import %r (from %#x); the "
                "harness must not guess at it" % (nm, ret)
            )
        res, pops = h(args)
        uc.reg_write(UC_X86_REG_EAX, res or 0)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pops * 4)
        uc.reg_write(UC_X86_REG_EIP, ret)

    def _handlers(self):
        return {
            "malloc": lambda a: (self.alloc(a[0]), 0),
            "calloc": self._imp_calloc,
            "free": lambda a: (0, 0),
            "??_U@YAPAXI@Z": lambda a: (self.alloc(a[0]), 0),  # operator new[]
            "??2@YAPAXI@Z": lambda a: (self.alloc(a[0]), 0),  # operator new
            "??_V@YAXPAX@Z": lambda a: (0, 0),  # operator delete[]
            "??3@YAXPAX@Z": lambda a: (0, 0),  # operator delete
            "??0%s@QAE@PBD@Z" % _STR: self._str_ctor_cstr,
            "??0%s@QAE@XZ" % _STR: self._str_ctor_default,
            "??0%s@QAE@ABV01@Z" % _STR: self._str_ctor_copy,
            "??1%s@QAE@XZ" % _STR: lambda a: (0, 0),
            "??4%s@QAEAAV01@ABV01@Z" % _STR: self._str_assign,
            "?_Nomemory@std@@YAXXZ": lambda a: (0, 0),
        }

    def _imp_calloc(self, a):
        n = max(a[0] * a[1], 1)
        p = self.alloc(n)
        self.uc.mem_write(p, b"\0" * n)
        return p, 0

    # -- MSVC7.1 std::basic_string<char>: _Bx@+8, _Mysize@+0x18, _Myres@+0x1c
    def _str_read(self, p: int) -> bytes:
        size, res = struct.unpack("<II", self.uc.mem_read(p + 0x18, 8))
        if res >= 16:
            ptr = struct.unpack("<I", self.uc.mem_read(p + 8, 4))[0]
            return bytes(self.uc.mem_read(ptr, size))
        return bytes(self.uc.mem_read(p + 8, size))

    def _str_set(self, p: int, data: bytes) -> None:
        self.uc.mem_write(p, b"\0" * 0x20)
        if len(data) < 16:
            self.uc.mem_write(p + 8, data + b"\0" * (16 - len(data)))
            res = 15
        else:
            buf = self.alloc(len(data) + 1)
            self.uc.mem_write(buf, data + b"\0")
            self.uc.mem_write(p + 8, struct.pack("<I", buf))
            res = len(data)
        self.uc.mem_write(p + 0x18, struct.pack("<II", len(data), res))

    def _cstr(self, p: int) -> bytes:
        out = bytearray()
        while True:
            c = self.uc.mem_read(p + len(out), 1)[0]
            if c == 0:
                return bytes(out)
            out.append(c)

    def _str_ctor_cstr(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        self._str_set(this, self._cstr(a[0]))
        return this, 1

    def _str_ctor_default(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        self._str_set(this, b"")
        return this, 0

    def _str_ctor_copy(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        self._str_set(this, self._str_read(a[0]))
        return this, 1

    def _str_assign(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        self._str_set(this, self._str_read(a[0]))
        return this, 1

    # -- guest memory -------------------------------------------------------

    def alloc(self, n: int) -> int:
        p = self._brk
        self._brk = (self._brk + max(n, 1) + 31) & ~15
        if self._brk >= HEAP_ADDR + HEAP_SIZE:
            raise MemoryError("guest heap exhausted")
        self.uc.mem_write(p, b"\xcd" * max(n, 1))
        return p

    def _setup_type_singletons(self) -> None:
        self.type_obj = {}
        for g, tag in ((G_TYPE_I16, TYPE_TAG_I16), (G_TYPE_U8, TYPE_TAG_U8),
                       (G_TYPE_F32, TYPE_TAG_F32)):
            o = self.alloc(0x20)
            self.uc.mem_write(o, struct.pack("<I", tag) + b"\0" * 0x1C)
            self.uc.mem_write(g, struct.pack("<I", o))
            self.type_obj[tag] = o

    # -- calling into the guest --------------------------------------------

    def call(self, addr: int, ecx: int = 0, args=()) -> int:
        uc = self.uc
        esp = STACK_ADDR + STACK_SIZE - 0x40000
        for a in reversed(args):
            esp -= 4
            uc.mem_write(esp, struct.pack("<I", a & 0xFFFFFFFF))
        esp -= 4
        uc.mem_write(esp, struct.pack("<I", RETURN_MAGIC))
        uc.reg_write(UC_X86_REG_ESP, esp)
        uc.reg_write(UC_X86_REG_ECX, ecx)
        try:
            uc.emu_start(addr, RETURN_MAGIC, timeout=600_000_000)
        except UcError as ex:  # pragma: no cover - diagnostics
            raise RuntimeError(
                "unicorn @ %#x (eip %#x): %s" % (addr, uc.reg_read(UC_X86_REG_EIP), ex)
            ) from ex
        return uc.reg_read(UC_X86_REG_EAX)

    # -- image objects ------------------------------------------------------

    def new_image(self, rows, tag: int = TYPE_TAG_I16) -> int:
        """Build a real ``IemTImage`` with the DLL's own ctor, then fill it."""
        h = len(rows)
        w = len(rows[0])
        obj = self.alloc(16)
        self.call(0x104D2FC0, ecx=obj, args=(self.type_obj[tag], h, w, 0, 0))
        fmt = {1: "<%dB", 2: "<%dh", 4: "<%di"}[{2: 1, 3: 2, 4: 4}[tag]]
        for y, ptr in enumerate(self.row_ptrs(obj)):
            self.uc.mem_write(ptr, struct.pack(fmt % w, *rows[y]))
        return obj

    def img_data(self, obj: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(obj + 4, 4))[0]

    def dims(self, obj: int):
        d = self.img_data(obj)
        return struct.unpack("<ii", self.uc.mem_read(d + 0x10, 8))

    def row_ptrs(self, obj: int):
        d = self.img_data(obj)
        h = struct.unpack("<i", self.uc.mem_read(d + 0x10, 4))[0]
        rp = struct.unpack("<I", self.uc.mem_read(d + 0x18, 4))[0]
        return [struct.unpack("<I", self.uc.mem_read(rp + 4 * y, 4))[0] for y in range(h)]

    def read_i16(self, obj: int):
        h, w = self.dims(obj)
        return [
            list(struct.unpack("<%dh" % w, self.uc.mem_read(p, 2 * w)))
            for p in self.row_ptrs(obj)
        ]

    def make_kernel(self, vals) -> int:
        """`0x1029ecb3` — ``0x104dc4d0(3,3,0)`` then nine ``0x104d2eb0``."""
        k = self.alloc(0x40)
        self.call(0x104DC4D0, ecx=k, args=(3, 3, 0))
        for r in range(3):
            for c in range(3):
                bits = struct.unpack("<Q", struct.pack("<d", float(vals[r][c])))[0]
                self.call(0x104D2EB0, ecx=k, args=(r, c, bits & 0xFFFFFFFF, bits >> 32))
        return k


# --- running the real fcn.1029ec50 ------------------------------------------


def run_dll_threshold(pe: bytes, prob, *, mode: int = 2, use_advanced: int = 0):
    """Run the whole function and capture its intermediates.

    Returns ``{'threshold', 'mask', 'hist', 'smooth', 'binary'}``.  The mask
    and the histogram are read out of guest memory at `0x1029f4c3` — the
    instruction immediately after the histogram loop — and the smoothed bins
    at `0x1029f819`, so they are the vendor's own buffers, not a re-derivation.
    """
    g = Guest(pe)
    img = g.new_image(prob)
    out = g.alloc(16)
    thr = g.alloc(4)
    g.uc.mem_write(thr, struct.pack("<i", -0x0BAD))
    grabbed = {}

    def snap(uc, addr, size, ud):
        esp = uc.reg_read(UC_X86_REG_ESP)
        if addr == 0x1029F4C3 and "hist" not in grabbed:
            hp = struct.unpack("<I", uc.mem_read(esp + F_HIST, 4))[0]
            grabbed["hist"] = list(
                struct.unpack("<%df" % fl.HIST_BINS, uc.mem_read(hp, 4 * fl.HIST_BINS))
            )
            h = struct.unpack("<i", uc.mem_read(esp + F_HEIGHT, 4))[0]
            w = struct.unpack("<i", uc.mem_read(esp + F_WIDTH, 4))[0]
            pd = struct.unpack("<I", uc.mem_read(esp + F_MASK_PLANE_DATA, 4))[0]
            rp = struct.unpack("<I", uc.mem_read(pd + 0x18, 4))[0]
            rows = []
            for y in range(h):
                r = struct.unpack("<I", uc.mem_read(rp + 4 * y, 4))[0]
                rows.append(list(uc.mem_read(r, w)))
            grabbed["mask"] = rows
        elif addr == 0x1029F819 and "smooth" not in grabbed:
            # `esi` still holds the first of the two `malloc(0x100)`s at
            # `0x1029f4cc` / `0x1029f4d8` — the smoothed bins.  The second
            # (`[esp+0x4c]`) is only touched by the dead useAdvanced pass at
            # `0x1029f798`.
            sp = uc.reg_read(UC_X86_REG_ESI)
            grabbed["smooth"] = list(
                struct.unpack("<%df" % fl.HIST_BINS, uc.mem_read(sp, 4 * fl.HIST_BINS))
            )

    g.uc.hook_add(UC_HOOK_CODE, snap, begin=0x1029F4C3, end=0x1029F81A)
    ret = g.call(0x1029EC50, args=(out, img, mode, thr, use_advanced))
    binary = None
    if ret:
        h, w = g.dims(ret)
        binary = [list(g.uc.mem_read(p, w)) for p in g.row_ptrs(ret)]
    grabbed["threshold"] = struct.unpack("<i", g.uc.mem_read(thr, 4))[0]
    grabbed["binary"] = binary
    return grabbed


def run_dll_convolve(pe: bytes, plane, kernel):
    g = Guest(pe)
    img = g.new_image(plane)
    k = g.make_kernel(kernel)
    out = g.alloc(16)
    g.call(0x104DD9D0, ecx=k, args=(out, img))
    return g.read_i16(out)


def run_dll_edge_clean(pe: bytes, plane):
    """`fcn.1029cad0`, called exactly as `0x1029f02d` calls it (in place)."""
    g = Guest(pe)
    img = g.new_image(plane)
    g.call(0x1029CAD0, args=(img,))
    return g.read_i16(img)


# --- a deterministic PRNG ----------------------------------------------------


class Rng:
    def __init__(self, seed: int) -> None:
        self.s = seed & 0x7FFFFFFF

    def next(self) -> int:
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s

    def between(self, lo: int, hi: int) -> int:
        return lo + self.next() % (hi - lo)


def _prob_plane(rng: Rng, h: int, w: int, kind: str = "blobs"):
    """Planes shaped like a real skin-probability plane: mostly zero, with a
    few high-probability regions, so the histogram has a real peak and a real
    valley rather than a single spike."""
    if kind == "uniform":
        return [[rng.between(0, 256) for _ in range(w)] for _ in range(h)]
    if kind == "flat":
        v = rng.between(0, 256)
        return [[v] * w for _ in range(h)]
    plane = [[rng.between(0, 40) for _ in range(w)] for _ in range(h)]
    for _ in range(3):
        cy, cx = rng.between(0, h), rng.between(0, w)
        ry, rx = rng.between(1, max(2, h // 2)), rng.between(1, max(2, w // 2))
        lvl = rng.between(120, 256)
        for y in range(max(0, cy - ry), min(h, cy + ry)):
            for x in range(max(0, cx - rx), min(w, cx + rx)):
                plane[y][x] = min(255, lvl + rng.between(-20, 20))
    return plane


def _discriminating_plane(seed: int):
    """A plane, by recipe, chosen because it makes a specific mutation visible.

    Found by sweeping this recipe over seeds until each mutation's answer
    diverged; the seeds are recorded so the sweep never has to run again.
    """
    rng = Rng(seed * 7919)
    kind = ("blobs", "uniform", "blobs")[seed % 3]
    return _prob_plane(rng, 12 + (seed % 20), 12 + ((seed * 3) % 20), kind)


def _same32(a: float, b: float) -> bool:
    return struct.pack("<f", a) == struct.pack("<f", b)


# --- the checks --------------------------------------------------------------


def check_machine(pe: bytes) -> int:
    print("\n  [0] the emulated machine itself")
    g = Guest(pe)
    print("      %d imports redirected to the trap page" % g.n_imports)
    fails = 0
    for tag, want in ((TYPE_TAG_U8, 1), (TYPE_TAG_I16, 2), (TYPE_TAG_F32, 4)):
        obj = g.alloc(16)
        g.call(0x104D2FC0, ecx=obj, args=(g.type_obj[tag], 8, 11, 0, 0))
        rp = g.row_ptrs(obj)
        stride = rp[1] - rp[0]
        ok = stride == 11 * want
        fails += 0 if ok else 1
        print("      type tag %d -> row stride %d for width 11 (%d bytes/sample): %s"
              % (tag, stride, want, "ok" if ok else "WRONG"))
    return fails


def check_convolve(pe: bytes) -> int:
    print("\n  [1] 3x3 correlation  0x104dd9d0 -> fcn.104dcbc0 (int16)")
    rng = Rng(0x0C0FFEE1)
    cases = []
    # 3x3 is the smallest the vendor accepts: `0x104dcbfe` / `0x104dcc16`
    # bail to the error path when the kernel is larger than the image.
    for h, w in ((6, 7), (3, 3), (3, 9), (9, 3), (17, 13), (32, 24)):
        cases.append(([[rng.between(0, 256) for _ in range(w)] for _ in range(h)], "random"))
    imp = [[0] * 7 for _ in range(6)]
    imp[2][3] = 100
    cases.append((imp, "impulse"))
    cases.append(([[10 * y + x for x in range(7)] for y in range(6)], "ramp"))
    cases.append(([[255] * 9 for _ in range(9)], "saturated"))
    corner = [[0] * 5 for _ in range(5)]
    corner[0][0] = 255
    corner[4][4] = -255
    cases.append((corner, "corners"))

    fails = checked = 0
    for plane, label in cases:
        for kname, kern in (("SOBEL_X", fl.SOBEL_X), ("SOBEL_Y", fl.SOBEL_Y)):
            got = run_dll_convolve(pe, plane, kern)
            host = fl.flesh_convolve(plane, kern)
            checked += 1
            if got != host:
                fails += 1
                if fails <= 3:
                    print("      FAIL [%s %s] %dx%d\n         dll =%s\n         host=%s"
                          % (label, kname, len(plane[0]), len(plane), got, host))
    print("      %d planes x kernels: %s"
          % (checked, "ALL BIT-EXACT" if not fails else "%d FAILED" % fails))
    print("      (the out-of-range index policy this pins down is reflection that")
    print("       does NOT repeat the edge sample: -1 reads 1, n reads n-2)")
    return fails


def probe_convolve_rounding(pe: bytes) -> None:
    print("\n  [1b] the convolution's store rounding — a probe, not a dependency")
    frac = ((0.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 0.0))
    plane = [[0, 1, 2, 3, 5, 7, 9, -1, -3, -5], [0] * 10, [0] * 10]
    got = run_dll_convolve(pe, plane, frac)
    print("      kernel = 0.5 at the centre, row 0 in = %s" % plane[0])
    print("      dll out row 0                        = %s" % got[0])
    trunc = [int(v * 0.5) for v in plane[0]]
    nearest = [int(v * 0.5 + (0.5 if v >= 0 else -0.5)) for v in plane[0]]
    banker = [round(v * 0.5) for v in plane[0]]
    for nm, ref in (("truncate toward zero", trunc), ("round half away", nearest),
                    ("round half to even", banker)):
        print("      %-22s -> %s%s" % (nm, ref, "   <== matches" if ref == got[0] else ""))
    print("      With the shipped integer Sobel kernels every sum is exact, so this")
    print("      rule NEVER fires on the flesh path; it is recorded, not relied on.")


def check_prob_cast(pe: bytes) -> int:
    """[1c] the float probability plane -> the int16 0..255 plane."""
    print("\n  [1c] float plane -> int16 plane  0x104e2960 + 0x104de680")
    g = Guest(pe)
    vals = [0.0, 0.4, 0.5, 0.6, 1.0, 1.4, 1.5, 1.6, 2.5,
            -0.4, -0.5, -0.6, -1.5, 254.5, 255.0, 255.4, 300.0]
    n = len(vals)
    src = g.alloc(16)
    g.call(0x104D2FC0, ecx=src, args=(g.type_obj[TYPE_TAG_F32], 1, n, 0, 0))
    g.uc.mem_write(g.row_ptrs(src)[0], struct.pack("<%df" % n, *vals))
    t16 = g.alloc(0x80)
    g.call(0x104D4170, ecx=t16, args=(0x10574A28, 3))  # as 0x102a154a builds it
    out = g.alloc(16)
    flag = g.alloc(4)
    g.uc.mem_write(flag, struct.pack("<i", 0))
    ret = g.call(0x104DE680, args=(out, src, t16, flag))
    got = g.read_i16(ret)[0]
    host = [fl._to_i16(fl._ftol32(v)) for v in vals]
    ok = got == host
    print("      in   %s" % vals)
    print("      dll  %s" % got)
    print("      port %s%s" % (host, "" if ok else "   <== MISMATCH"))
    print("      -> truncation toward zero, and NO clamping (300.0 -> 300, not 255).")
    print("         Out of range cannot happen on this path: the probability is")
    print("         [0,1] by construction, so 255.0 * p lands in [0,255].")
    # and the in-place scale itself
    src2 = g.alloc(16)
    g.call(0x104D2FC0, ecx=src2, args=(g.type_obj[TYPE_TAG_F32], 1, 5, 0, 0))
    fvals = [0.0, 0.001, 0.5, 0.9999999, 1.0]
    g.uc.mem_write(g.row_ptrs(src2)[0], struct.pack("<5f", *fvals))
    bits = struct.unpack("<Q", struct.pack("<d", fl.PROB_PLANE_SCALE))[0]
    g.call(0x104E2960, args=(src2, bits & 0xFFFFFFFF, bits >> 32))
    scaled = list(struct.unpack("<5f", g.uc.mem_read(g.row_ptrs(src2)[0], 20)))
    host_scaled = [fl._f32(fl._f32(v) * fl.PROB_PLANE_SCALE) for v in fvals]
    ok2 = all(_same32(a, b) for a, b in zip(scaled, host_scaled))
    print("      scale-by-255 in place: dll %s" % scaled)
    print("                             port %s%s"
          % (host_scaled, "" if ok2 else "   <== MISMATCH"))
    return 0 if (ok and ok2) else 1


def check_edge_clean(pe: bytes) -> int:
    print("\n  [2] neighbour cleanup  fcn.1029cad0")
    rng = Rng(0x1BADF00D)
    cases = []
    for h, w in ((5, 6), (3, 3), (2, 9), (9, 2), (1, 1), (12, 15)):
        cases.append([[rng.between(0, 2) * 255 for _ in range(w)] for _ in range(h)])
    cases.append([[0] * 8 for _ in range(8)])
    cases.append([[255] * 8 for _ in range(8)])
    # negatives: the zero branch tests `== 0`, the non-zero branch tests `> 0`,
    # so a negative neighbour must count for neither.
    neg = [[rng.between(-3, 3) for _ in range(9)] for _ in range(9)]
    cases.append(neg)
    single = [[0] * 7 for _ in range(7)]
    single[3][3] = 255
    cases.append(single)
    fails = 0
    for plane in cases:
        got = run_dll_edge_clean(pe, plane)
        host = fl.flesh_edge_clean(plane)
        if got != host:
            fails += 1
            if fails <= 3:
                print("      FAIL %dx%d\n         dll =%s\n         host=%s"
                      % (len(plane[0]), len(plane), got, host))
    print("      %d planes: %s" % (len(cases), "ALL BIT-EXACT" if not fails else
                                   "%d FAILED" % fails))
    return fails


def check_threshold(pe: bytes):
    print("\n  [3] the whole fcn.1029ec50: mask, histogram, smoothing, threshold")
    rng = Rng(0x5A5A1234)
    cases = []
    for h, w in ((24, 32), (40, 30), (17, 23), (64, 48), (8, 10)):
        cases.append((_prob_plane(rng, h, w), "blobs %dx%d" % (w, h)))
    cases.append((_prob_plane(rng, 32, 32, "uniform"), "uniform noise 32x32"))
    cases.append((_prob_plane(rng, 20, 20, "flat"), "flat 20x20"))
    cases.append(([[0] * 16 for _ in range(16)], "all zero 16x16"))
    cases.append(([[255] * 16 for _ in range(16)], "all 255 16x16"))
    grad = [[min(255, x * 8) for x in range(32)] for _ in range(24)]
    cases.append((grad, "horizontal gradient 32x24"))

    fails = 0
    thresholds = []
    for plane, label in cases:
        got = run_dll_threshold(pe, plane)
        h_mask = fl.flesh_edge_mask(plane)
        h_hist = fl.flesh_histogram(plane, h_mask)
        h_smooth = fl.flesh_smooth_histogram(h_hist)
        h_thr = fl.flesh_pick_bin(h_smooth) * fl.THRESHOLD_BIN_SCALE
        h_bin = fl.flesh_binarise(plane, h_thr)
        bad = []
        if got["mask"] != h_mask:
            bad.append("mask")
        if not all(_same32(a, b) for a, b in zip(got["hist"], h_hist)):
            bad.append("hist")
        if not all(_same32(a, b) for a, b in zip(got["smooth"], h_smooth)):
            bad.append("smooth")
        if got["threshold"] != h_thr:
            bad.append("threshold(dll=%d host=%d)" % (got["threshold"], h_thr))
        if got["binary"] is not None and got["binary"] != h_bin:
            bad.append("binary")
        thresholds.append((label, got["threshold"], sum(r.count(255) for r in h_mask)))
        if bad:
            fails += 1
            print("      FAIL [%s]: %s" % (label, ", ".join(bad)))
    for label, t, n in thresholds:
        print("      %-24s threshold %3d  (%d edge pixels)" % (label, t, n))
    print("      %d planes: %s" % (len(cases), "ALL BIT-EXACT" if not fails else
                                   "%d FAILED" % fails))
    return fails, cases


def check_teeth(pe: bytes, cases) -> int:
    """Deliberate port bugs, each compared against the DLL at the level where
    it is actually observable — and, where a bug is genuinely invisible, that
    is reported as a fact rather than papered over."""
    print("\n  [4] deliberate port bugs — the harness must catch each one")
    fails = 0
    saved = {
        k: getattr(fl, k)
        for k in (
            "SOBEL_X",
            "SOBEL_Y",
            "EDGE_THRESHOLD",
            "SMOOTH_HALF_WIDTH",
            "THRESHOLD_BIN_SCALE",
            "THRESHOLD_BIN_DEFAULT",
            "_mirror",
            "_f32",
            "flesh_edge_clean",
            "flesh_pick_bin",
            "flesh_smooth_histogram",
        )
    }

    def restore():
        for k, v in saved.items():
            setattr(fl, k, v)

    # --- (a) convolution-level, against 0x104dd9d0 itself -------------------
    conv_planes = []
    rng = Rng(0x7E571234)
    for h, w in ((6, 7), (9, 11), (13, 8)):
        conv_planes.append([[rng.between(0, 256) for _ in range(w)] for _ in range(h)])
    conv_ref = [
        (p, k, run_dll_convolve(pe, p, k)) for p in conv_planes for k in (fl.SOBEL_X, fl.SOBEL_Y)
    ]

    def probe_conv(label: str) -> None:
        nonlocal fails
        n = sum(1 for p, k, ref in conv_ref if fl.flesh_convolve(p, k) != ref)
        print("      '%s': %s" % (label, "caught on %d/%d planes" % (n, len(conv_ref))
                                  if n else "MISSED"))
        if not n:
            print("      FAILED: a deliberate port bug was invisible")
            fails += 1

    fl._mirror = lambda i, n: 0 if i < 0 else (n - 1 if i >= n else i)
    probe_conv("border reflect -> clamp/replicate")
    restore()
    fl._mirror = lambda i, n: i % n
    probe_conv("border reflect -> wrap")
    restore()
    fl._mirror = lambda i, n: max(0, min(n - 1, abs(i)))
    probe_conv("border reflect repeats the edge sample (-1 -> 0, not 1)")
    restore()
    real_conv = fl.flesh_convolve
    fl.flesh_convolve = lambda p, k: real_conv(p, [row[::-1] for row in k[::-1]])
    probe_conv("correlation -> true convolution (kernel flipped)")
    restore()
    fl.flesh_convolve = real_conv
    fl.flesh_convolve = lambda p, k: real_conv(p, list(zip(*k)))
    probe_conv("kernel transposed")
    fl.flesh_convolve = real_conv
    restore()

    # --- (b) cleanup-level, against fcn.1029cad0 itself ---------------------
    rng = Rng(0x0DDBA11)
    clean_planes = [
        [[rng.between(0, 2) * 255 for _ in range(w)] for _ in range(h)]
        for h, w in ((9, 11), (12, 12))
    ]
    clean_ref = [(p, run_dll_edge_clean(pe, p)) for p in clean_planes]

    def probe_clean(label: str) -> None:
        nonlocal fails
        n = sum(1 for p, ref in clean_ref if fl.flesh_edge_clean(p) != ref)
        print("      '%s': %s" % (label, "caught on %d/%d planes" % (n, len(clean_ref))
                                  if n else "MISSED"))
        if not n:
            print("      FAILED: a deliberate port bug was invisible")
            fails += 1

    real_clean = saved["flesh_edge_clean"]

    def clean_diagonals(plane_):
        h = len(plane_)
        w = len(plane_[0])
        out = [[0] * w for _ in range(h)]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                v = plane_[y][x]
                nb = [plane_[y][x - 1], plane_[y - 1][x], plane_[y][x + 1], plane_[y + 1][x],
                      plane_[y - 1][x - 1], plane_[y + 1][x + 1]]
                if v == 0:
                    out[y][x] = 0 if sum(1 for q in nb if q == 0) >= 2 else 255
                else:
                    out[y][x] = 255 if sum(1 for q in nb if q > 0) >= 2 else 0
        return out

    fl.flesh_edge_clean = clean_diagonals
    probe_clean("cleanup reads 6 neighbours instead of the 4 orthogonal ones")
    restore()

    def clean_thresh3(plane_):
        h = len(plane_)
        w = len(plane_[0])
        out = [[0] * w for _ in range(h)]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                v = plane_[y][x]
                nb = [plane_[y][x - 1], plane_[y - 1][x], plane_[y][x + 1], plane_[y + 1][x]]
                if v == 0:
                    out[y][x] = 0 if sum(1 for q in nb if q == 0) >= 3 else 255
                else:
                    out[y][x] = 255 if sum(1 for q in nb if q > 0) >= 3 else 0
        return out

    fl.flesh_edge_clean = clean_thresh3
    probe_clean("cleanup's neighbour count 2 -> 3")
    restore()

    def clean_noborder(plane_):
        out = real_clean(plane_)
        h = len(plane_)
        w = len(plane_[0])
        for x in range(w):
            out[0][x] = plane_[0][x]
            out[h - 1][x] = plane_[h - 1][x]
        for y in range(h):
            out[y][0] = plane_[y][0]
            out[y][w - 1] = plane_[y][w - 1]
        return out

    fl.flesh_edge_clean = clean_noborder
    probe_clean("cleanup keeps the border instead of zeroing it")
    restore()

    def clean_inverted(plane_):
        return [[255 - v if v in (0, 255) else v for v in row] for row in real_clean(plane_)]

    fl.flesh_edge_clean = clean_inverted
    probe_clean("cleanup's 0/255 polarity inverted")
    restore()

    # --- (c) end to end, against the whole fcn.1029ec50 --------------------
    # Planes chosen (by recipe, seeds recorded) so that each mutation below
    # actually changes the answer somewhere.
    # `cases[7]` is the all-zero plane: it produces an empty mask, hence an
    # all-zero smoothed histogram, which is the only way to exercise the
    # "all four neighbours equal" corner and the no-valley default.
    e2e_planes = [cases[0][0], cases[1][0], cases[5][0], cases[7][0]] + [
        _discriminating_plane(s) for s in (1, 2, 16)
    ]
    e2e_ref = [(p, run_dll_threshold(pe, p)) for p in e2e_planes]

    def probe_e2e(label: str, expect_visible: bool = True, why: str = "") -> None:
        nonlocal fails
        hits = []
        for p, ref in e2e_ref:
            try:
                m = fl.flesh_edge_mask(p)
                hh = fl.flesh_histogram(p, m)
                ss = fl.flesh_smooth_histogram(hh)
                t = fl.flesh_pick_bin(ss) * fl.THRESHOLD_BIN_SCALE
            except Exception as ex:
                hits.append("raised " + type(ex).__name__)
                continue
            if m != ref["mask"]:
                hits.append("mask")
            elif not all(_same32(a, b) for a, b in zip(hh, ref["hist"])):
                hits.append("hist")
            elif not all(_same32(a, b) for a, b in zip(ss, ref["smooth"])):
                hits.append("smooth")
            elif t != ref["threshold"]:
                hits.append("threshold")
        if hits:
            print("      '%s': caught on %d/%d planes (%s)"
                  % (label, len(hits), len(e2e_ref), ", ".join(sorted(set(hits)))))
            return
        if expect_visible:
            print("      '%s': MISSED" % label)
            print("      FAILED: a deliberate port bug was invisible")
            fails += 1
        else:
            print("      '%s': NOT CAUGHT, and that is a real result, not a gap --" % label)
            for line in why.splitlines():
                print("        %s" % line)

    fl.EDGE_THRESHOLD = 401
    probe_e2e("edge threshold 400 -> 401")
    restore()
    fl.SMOOTH_HALF_WIDTH = 6
    probe_e2e("smoothing window 15 taps -> 13")
    restore()
    fl.THRESHOLD_BIN_SCALE = 1
    probe_e2e("threshold = bin instead of bin*4")
    restore()

    real_smooth = saved["flesh_smooth_histogram"]

    def keep_first_bins(hist):
        out = real_smooth(hist)
        out[0] = fl._f32(sum(hist[j] for j in range(0, 8)) / 8)
        out[1] = fl._f32(sum(hist[j] for j in range(0, 9)) / 9)
        return out

    fl.flesh_smooth_histogram = keep_first_bins
    probe_e2e("bins 0 and 1 not forced to zero")
    restore()

    def div_by_window(hist):
        out = [
            fl._f32(sum(hist[j] for j in range(i - 7, i + 8) if 0 <= j < fl.HIST_BINS) / 15.0)
            for i in range(fl.HIST_BINS)
        ]
        out[0] = out[1] = 0.0
        return out

    fl.flesh_smooth_histogram = div_by_window
    probe_e2e("mean divides by 15 instead of the in-range tap count")
    restore()

    def no_sticky(smooth):
        for i in range(2, fl.HIST_BINS - 2):
            g = e = 0
            for j in (i - 2, i - 1, i + 1, i + 2):
                g += smooth[j] > smooth[i]
                e += smooth[j] == smooth[i]
            if (e + g) == 4 and g:
                return i
        return fl.THRESHOLD_BIN_DEFAULT

    fl.flesh_pick_bin = no_sticky
    probe_e2e("valley search without the sticky 'a peak came first' gate")
    restore()

    def window1(smooth):
        seen = False
        for i in range(1, fl.HIST_BINS - 1):
            g = e = l = 0
            for j in (i - 1, i + 1):
                g += smooth[j] > smooth[i]
                e += smooth[j] == smooth[i]
                l += smooth[j] < smooth[i]
            if (e + l) == 2 and l:
                seen = True
            if seen and (e + g) == 2 and g:
                return i
        return fl.THRESHOLD_BIN_DEFAULT

    fl.flesh_pick_bin = window1
    probe_e2e("peak/valley window +/-2 -> +/-1")
    restore()

    def no_strict(smooth):
        seen = False
        for i in range(2, fl.HIST_BINS - 2):
            nb = [smooth[j] for j in (i - 2, i - 1, i + 1, i + 2)]
            if all(v <= smooth[i] for v in nb):
                seen = True
            if seen and all(v >= smooth[i] for v in nb):
                return i
        return fl.THRESHOLD_BIN_DEFAULT

    fl.flesh_pick_bin = no_strict
    probe_e2e("extremum tests drop the 'at least one strictly' requirement")
    restore()

    fl.THRESHOLD_BIN_DEFAULT = 63
    probe_e2e("no-valley default bin 64 -> 63")
    restore()

    fl.SOBEL_X = ((-1.0, 0.0, 1.0), (-2.0, 0.0, 2.0), (-1.0, 0.0, 1.0))
    probe_e2e(
        "Sobel X sign flipped",
        expect_visible=False,
        why=(
            "0x1029ef08 takes |gx| (the abs functor at 0x1029c2e0) before 0x1029ef50\n"
            "adds it to |gy|, so the sign of either kernel is destroyed before it can\n"
            "reach the mask.  Genuinely unobservable end to end -- and caught at the\n"
            "convolution level instead: see 'kernel transposed' and section [1], which\n"
            "diff flesh_convolve against 0x104dd9d0 directly, sign and all."
        ),
    )
    restore()

    fl.SOBEL_X, fl.SOBEL_Y = fl.SOBEL_Y, fl.SOBEL_X
    probe_e2e(
        "Sobel X and Y kernels swapped",
        expect_visible=False,
        why=(
            "|gx| + |gy| is symmetric in the two kernels, so swapping them cannot\n"
            "change the sum.  Same remedy: section [1] pins each kernel separately."
        ),
    )
    restore()
    return fails


def demonstrate_chain() -> None:
    """[6] the composed chain, from three analysis planes to Delta.

    Every stage here is individually bit-exact; the *composition* is tier 3
    (read out of `fcn.102a1500` and `fcn.10270280`, not executed as a whole).
    Its purpose is to show precisely where the remaining gap is: two inputs,
    not a stage.
    """
    print("\n  [6] the whole flesh chain, run forward on a synthetic analysis image")
    params = fl.default_params()
    tabs = fl.default_cond_prob_tables(params)
    rng = Rng(0x0FE54123)
    h, w = 48, 64
    # A frame with a skin-coloured patch: the l/s/t tables peak at bins
    # 18/19/14, i.e. roughly (R,G,B) = (1825, 1616, 1587).
    planes = [[[rng.between(400, 700) for _ in range(w)] for _ in range(h)]
              for _ in range(3)]
    for y in range(10, 34):
        for x in range(14, 46):
            planes[0][y][x] = 1825 + rng.between(-90, 90)
            planes[1][y][x] = 1616 + rng.between(-90, 90)
            planes[2][y][x] = 1587 + rng.between(-90, 90)

    prob_f = fl.flesh_probability_plane(planes, params, tabs)
    prob16 = fl.flesh_prob_to_int16(prob_f)
    threshold = fl.flesh_threshold_from_plane(prob16)
    plane = fl.flesh_reduction_plane(prob16, threshold)
    clamped, flag = fl.flesh_clamp_plane(plane)
    b_outer = fl.flesh_border(h, params.clip_amount)
    b_inner = fl.flesh_border(w, params.clip_amount)
    # The weight plane is now ported and bit-exact (fcn.10271bc0's Gaussian,
    # padded by 0x104e7880 -- pakon_flesh_weight_golden.py).  `w = 1` is kept
    # HERE deliberately, so this section's numbers stay comparable with the
    # ones it printed before that landed; fl.flesh_forward_delta uses the real
    # plane.  A placeholder that is labelled is not the same as a gap.
    weight = [[1] * w for _ in range(h)]
    stat, nsum, count, maxp = fl.flesh_accumulate(
        clamped, weight, planes, float(threshold),
        rows=fl.flesh_loop_rows(h, b_outer),
        cols=fl.flesh_loop_cols(w, b_inner),
    )
    area = fl.flesh_area(w, h, b_inner, b_outer)
    res = fl.flesh_results(stat=stat, nsum=nsum, flesh_count=count, max_prob=maxp,
                           area=area, exposure=1.0, params=params)
    print("      %dx%d analysis image, borders b_outer=%d b_inner=%d, area=%d"
          % (w, h, b_outer, b_inner, area))
    print("      threshold from fcn.1029ec50 = %d   (any-flesh flag = %s)"
          % (threshold, flag))
    print("      fleshCount=%d  nsum=%g  stat=%g  Q=%.5f (thresh %.5f)"
          % (count, nsum, stat, res["fraction"], params.flesh_count_thresh))
    print("      X = %.1f  (aim %.0f)   D = %.1f   -> Delta = %d"
          % (res["x"], params.flesh_neutral_aim, res["drive"], res["delta"]))
    print("      Every stage above is bit-exact.  The composition is NOT a")
    print("      reproduction of docs/74 §178's -40/+34/+15/+35/-59/+13, and cannot")
    print("      be, for two reasons that are inputs rather than stages:")
    print("        1. the three colour planes are synthetic — the vendor's arg3/arg4")
    print("           are copies of the scene's own analysis image (scene+0x04),")
    print("           pushed twice at 0x100fe396/0x100fe397 and copied by")
    print("           fcn.100db520 at 0x101c9bac / 0x101c9beb;")
    print("        2. the weight plane is the labelled `1` placeholder in THIS")
    print("           section — the real one (fcn.10271bc0's Gaussian, padded by")
    print("           0x104e7880) is now ported and bit-exact, and")
    print("           fl.flesh_forward_delta uses it.")
    k = fl.INV_1732
    xs = [fl.invert_delta_to_statistic(d, params)[1] for d in (-40, 34, 15, 35, -59, 13)]
    print("      For the record, §178's six Deltas still imply X in %.0f..%.0f, i.e."
          % (min(xs), max(xs)))
    print("      a weighted mean L of %.0f..%.0f (l bins %.1f..%.1f) — unchanged, and"
          % (min(xs) / k, max(xs) / k,
             (min(xs) / k - params.loff) / params.lscale,
             (max(xs) / k - params.loff) / params.lscale))
    print("      still tier 4.")


def report_gap() -> None:
    print("\n  [5] what is still NOT ported (stated as plainly as the positives)")
    print("      * the CONTENT of the source images.  Not a stage: 0x104e8360 is dead")
    print("        on the shipped DPI (useSmallAnalysisImage = 0, tested at")
    print("        0x102704a9) and 0x1014cc20 is IemTImage<T>::IemTImage(const")
    print("        IemImage&), a type-checked handle wrapper.  WHICH images they are")
    print("        is now read: arg3 and arg4 are two fcn.100db520 copies of the ONE")
    print("        AnsImageData at scene+0x04 (0x100fe396/0x100fe397), 3 bands, 12")
    print("        bits, >= 107x107 (apuCheckAnalysisImage 0x100d47c4).  The two 1-D")
    print("        LUT pre-passes at 0x10270920 / 0x10270b10, and the WEIGHT plane")
    print("        (fcn.10271bc0 padded by 0x104e7880 at 0x1027127e), ARE ported and")
    print("        bit-exact — pakon_flesh_weight_golden.py.")
    print("      * fcn.10270280 arg7 (the `float` exposure the exposureLimit guard")
    print("        reads, = [scene+0x4ac+0x10] at 0x100fe37b).  arg8 is NOT open: the")
    print("        colour-negative caller pushes the literal 1 at 0x100fe392.")
    print("      * fcn.1029ec50's own dead branches, asserted rather than ported:")
    print("        useAdvanced != 0 (0x1029f067) re-enables the 3x3 morphology at")
    print("        0x1029f06d and the second search at 0x1029f6cb; mode == 1")
    print("        (0x1029f566) is a different search.  fcn.102a1500 passes `push 2`")
    print("        at 0x102a1e1b and the shipped DPI sets useAdvanced = 0.")
    print("      * which shipped cond-prob table the loader puts at P+0x38/0x3c/0x40")
    print("        is CLOSED: AnsFleshCapabilityImpl's ctor fcn.101c84f0 stores the")
    print("        l/s/t lookups at DPI+0x38/+0x3c/+0x40 in that order, and the")
    print("        vendor's own DPI dump fcn.1026f5a0 prints those offsets as")
    print("        lCondProb / sCondProb / tCondProb.")
    print("      * the element-type tags this harness ASSERTS from row strides")
    print("        (2 = byte, 3 = short, 4 = float) are confirmed independently by")
    print("        the DLL's own IemType initialisers at 0x10570dc0…0x10570e20:")
    print("        ('unspecified',1) ('byte',2) ('short',3) ('float',4).")


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll_path.is_file():
        print("FAILED: no DLL at %s" % dll_path)
        return 1
    pe = dll_path.read_bytes()
    md5 = hashlib.md5(pe).hexdigest()
    print("  %s md5 %s" % (dll_path.name, md5))
    if md5 != fl.PAKONIMAU_MD5:
        print("FAILED: expected md5 %s" % fl.PAKONIMAU_MD5)
        return 1

    fails = 0
    fails += check_machine(pe)
    fails += check_convolve(pe)
    probe_convolve_rounding(pe)
    fails += check_prob_cast(pe)
    fails += check_edge_clean(pe)
    thr_fails, cases = check_threshold(pe)
    fails += thr_fails
    fails += check_teeth(pe, cases)
    report_gap()
    demonstrate_chain()

    print("\n  Porting state (pakon_flesh module flags):")
    print(fl.porting_state())

    assert fl.FLESH_THRESHOLD_PORTED
    assert fl.FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED
    assert fl.FLESH_DETECTOR_PORTED  # pakon_flesh_whole_golden.py
    assert not fl.FLESH_ADVANCED_PATH_PORTED
    assert not fl.FLESH_3DLUT_PATH_PORTED

    if fails:
        print("\nFAILED (%d)" % fails)
        return 1
    print("\nFLESH threshold golden: ALL OK (bit-exact on every ported block)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
