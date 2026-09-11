#!/usr/bin/env python3
"""Golden: ``fcn.102aece0`` run **as one function** under Unicorn.

Target
------
``PakonIMAu.dll`` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``, ``fcn.102aece0``
(``0x102aece0``…``0x102b4ca4``, 24,516 B, 6,643 instructions, 1,766 basic
blocks) — the producer of everything the SBA statistics vector carries.
docs/74 §192 mapped it; this harness *executes* it, in the
`pakon_flesh_whole_golden.py` style: its own entry, its own ten arguments,
its own ``ret``.

Only two of its three calls are stubbed, and both are libc:

* ``calloc`` (``0x102afa46``, via IAT ``0x10573430``) — 26 zeroed
  histogram buffers, sizes taken from the function's own descriptor table
  at frame ``+0x64``.
* ``free``   (``0x102b4c7c``, via IAT ``0x1057343c``).

The third, ``call 0x102b7440`` at ``0x102b4c5e``, is **left to run for
real** — it is the vector packer, already bit-exact (§192.3), so emulating
it costs nothing and keeps the object write path genuine.

The comparison target
---------------------
``fcn.102aece0``'s entire product is the argument block it hands to
``fcn.102b7440`` plus the two things it writes into the object itself.
Read off the push sequence at ``0x102b4c0e … 0x102b4c5e`` (esp tracked
through the ten pushes), the callee's arguments are:

===========  =======================  ==================================
callee arg   source                   this harness's name
===========  =======================  ==================================
arg1         our arg5                 mode
arg2         our arg4
arg3         frame ``+0xe84``         ``A3``  75 int32  (zeroed 0x102af756)
arg4         frame ``+0x2f4``         ``A4``  19 int32
arg5         frame ``+0x2d0``         ``A5``   9 int32
arg6         frame ``+0x344``         ``A6``  0xb00 B — the bank block
arg7         frame ``+0x2a8``         ``A7``  0x28 B — the count block
arg8         our arg7                 the gate array
arg9         our arg8                 the parameter struct
arg10        our arg10                the SBA object
===========  =======================  ==================================

The three sizes are not guesses: ``0x102af756 mov ecx,0x4b; rep stosd`` at
``+0xe84`` fixes A3 at exactly 75 dwords, ``0x102af76f…`` zeroes exactly the
19 dwords at ``+0x2f4`` and the 9 at ``+0x2d0``, and A7 runs to ``+0x2d0``
where A5 begins.  They also agree slot-for-slot with the independently
recovered argument lengths in `pakon_orderfpo_vecpack_golden.py`
(``A3_LEN = 0x4b*4``, ``A4_LEN = 0x13*4``, ``A5_LEN = 9*4``) — which were
derived from the *callee* side, months apart, without this frame.

So the port target captured here is ``(A3, A4, A5, A6, A7)`` at
``0x102b4c0e``, plus the object's 864-byte mask at ``+0xc20`` and its
header words, plus the whole object after the run.

Poisoning
---------
The object is filled with ``0xA5`` before the call and the whole 0x2000
extent is diffed, so a store the port misses shows up as surviving poison
rather than as a silent zero.

Tier
----
**Tier 1 for equivalence, not for provenance.**  No capture on this machine
hooks ``0x102aece0``; the inputs here are structured pseudo-random over the
exact buffer extents the function's own code fixes.  That settles *"does
this arithmetic match"*.  It does not settle *"are these the values a real
frame produces"*.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
    tools/ansel/python-pipeline/pakon_sba_measure_golden.py [dll]``
"""
from __future__ import annotations

import hashlib
import random
import struct
import sys
from pathlib import Path

from unicorn import (UC_ARCH_X86, UC_HOOK_BLOCK, UC_HOOK_CODE, UC_MODE_32,
                     Uc, UcError)
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP

try:
    import pakon_sba_measure as M
except ImportError:  # pragma: no cover - the port is optional for a DLL-only run
    M = None

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0B000000
STACK_SIZE = 0x00200000
DATA_ADDR = 0x0C000000
DATA_SIZE = 0x00400000
HEAP_ADDR = 0x0D000000
HEAP_SIZE = 0x00400000
STUB_ADDR = 0x0BE00000
RET_ADDR = STUB_ADDR + 0x10
CALLOC_STUB = STUB_ADDR + 0x20
FREE_STUB = STUB_ADDR + 0x30

IAT_CALLOC = 0x10573430
IAT_FREE = 0x1057343C

FN = 0x102AECE0
FN_END = 0x102B4CA4
#: ``0x102b4c0e`` — the first instruction of the tail-call push sequence, where
#: ESP is still the body ESP, so frame slots are literal displacements.
PRE_TAIL = 0x102B4C0E

EXIT_CALLOC_FAIL = 0x102AFAC8   # eax 0x18a0
EXIT_NO_SAMPLES = 0x102B48F3    # eax 0x189d
EXIT_SUCCESS = 0x102B4C93       # eax 0
EXIT_BAD_MODE = 0x102B4CA3      # eax 0x189c

RET_BAD_MODE = 0x189C
RET_NO_SAMPLES = 0x189D
RET_CALLOC_FAIL = 0x18A0

#: frame offsets of the five blocks handed to ``fcn.102b7440``
F_A7, A7_LEN = 0x2A8, 0x28
F_A5, A5_LEN = 0x2D0, 9 * 4
F_A4, A4_LEN = 0x2F4, 0x13 * 4
F_A6, A6_LEN = 0x344, 0x0B00
F_A3, A3_LEN = 0xE84, 0x4B * 4

OBJ_LEN = 0x2000
OBJ_MASK = 0xC20
MASK_LEN = 0x360           # 864 samples — `0x102aeda3 mov word [+0x2a8], 0x360`

#: 6 bands x 24 rows x 36 cols int16, plane stride 864
N_BANDS, N_ROWS, N_COLS = 6, 24, 36
N_SAMPLES = N_ROWS * N_COLS
PLANE_STRIDE = N_SAMPLES
IMG_WORDS = N_BANDS * N_SAMPLES

DEFAULT_DLL = (
    Path(__file__).resolve().parents[2] / "re" / "live_hooks" / "wine_host" / "PakonIMAu.dll"
)


def _align(n, a=0x1000):
    return (n + a - 1) & ~(a - 1)


# --------------------------------------------------------------------- guest


class Guest:
    def __init__(self, pe: bytes):
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        e = struct.unpack_from("<I", pe, 0x3C)[0]
        nsec = struct.unpack_from("<H", pe, e + 6)[0]
        optsz = struct.unpack_from("<H", pe, e + 20)[0]
        opt = e + 24
        size_image = struct.unpack_from("<I", pe, opt + 56)[0]
        uc.mem_map(IMAGE_BASE, _align(size_image))
        uc.mem_write(IMAGE_BASE, pe[:0x1000])
        so = opt + optsz
        for i in range(nsec):
            o = so + i * 40
            vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
            if rsz == 0 or raddr == 0:
                continue
            d = pe[raddr:raddr + rsz]
            if len(d) < vsz:
                d += b"\0" * (vsz - len(d))
            uc.mem_write(IMAGE_BASE + va, d[:max(vsz, rsz)])
        uc.mem_map(STACK_ADDR, STACK_SIZE)
        uc.mem_map(DATA_ADDR, DATA_SIZE)
        uc.mem_map(HEAP_ADDR, HEAP_SIZE)
        uc.mem_map(STUB_ADDR, 0x1000)
        uc.mem_write(IAT_CALLOC, struct.pack("<I", CALLOC_STUB))
        uc.mem_write(IAT_FREE, struct.pack("<I", FREE_STUB))
        uc.mem_write(CALLOC_STUB, b"\xc3")
        uc.mem_write(FREE_STUB, b"\xc3")
        self.heap = HEAP_ADDR + 0x1000
        self.p = DATA_ADDR + 0x1000
        self.callocs = []
        self.frees = []
        self.calloc_fail_after = None
        uc.hook_add(UC_HOOK_CODE, self._stub, begin=CALLOC_STUB, end=FREE_STUB + 8)

    def _stub(self, uc, addr, size, ud):
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        if addr == CALLOC_STUB:
            n, sz = struct.unpack("<II", uc.mem_read(esp + 4, 8))
            if (self.calloc_fail_after is not None
                    and len(self.callocs) >= self.calloc_fail_after):
                p = 0
            else:
                p = self.heap
                self.heap = (self.heap + max(n * sz, 16) + 0x40) & ~0xF
                uc.mem_write(p, b"\0" * (n * sz))
            self.callocs.append((n, sz, p))
            uc.reg_write(UC_X86_REG_EAX, p)
        elif addr == FREE_STUB:
            self.frees.append(struct.unpack("<I", uc.mem_read(esp + 4, 4))[0])
        else:
            return
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, ret)

    def blob(self, data: bytes) -> int:
        a = self.p
        self.uc.mem_write(a, bytes(data))
        self.p += _align(len(data) + 0x100, 0x100)
        return a


# ----------------------------------------------------------------- the case


class Case:
    """One complete argument set for ``fcn.102aece0``."""

    def __init__(self, name, *, image, offsets, sel, arg4, mode_pack, mode,
                 en, par, aim, obj_seed=0xA5, obj_pre=None):
        self.name = name
        self.image = image          # 6*864 int16, plane-major
        self.offsets = offsets      # six int32 (arg2)
        self.sel = sel              # arg3, 0..7
        self.arg4 = arg4            # arg4
        self.mode_pack = mode_pack  # arg5 -> fcn.102b7440's mode
        self.mode = mode            # arg6, one of 1/2/4/8
        self.en = en                # arg7  gate array
        self.par = par              # arg8  parameter struct
        self.aim = aim              # arg9  (may be None -> NULL)
        self.obj_seed = obj_seed
        #: {frame-relative object offset: int32} written into the object
        #: BEFORE the call.  `0x102b0da5` reads slot 479 at +0x7b8 — a real
        #: cross-call input, since fcn.1028b8d0 calls this three times.  A
        #: uniform poison fill cannot tell +0x7b8 from +0x7bc, so a case
        #: that seeds them differently is the only thing that pins it.
        self.obj_pre = dict(obj_pre or {})

    def fresh_obj(self):
        o = bytearray([self.obj_seed]) * OBJ_LEN
        for off, val in self.obj_pre.items():
            struct.pack_into("<i", o, off, val)
        return o


def run_dll(pe: bytes, c: Case, *, calloc_fail_after=None, count=False,
            blocks=None):
    """Execute ``fcn.102aece0`` whole.  Returns a dict of everything it wrote."""
    g = Guest(pe)
    uc = g.uc
    g.calloc_fail_after = calloc_fail_after

    p_img = g.blob(struct.pack("<%dh" % IMG_WORDS, *c.image))
    p_off = g.blob(struct.pack("<6i", *c.offsets))
    p_en = g.blob(bytes(c.en))
    p_par = g.blob(bytes(c.par))
    p_aim = 0 if c.aim is None else g.blob(bytes(c.aim))
    obj0 = bytearray([c.obj_seed]) * OBJ_LEN
    for off, val in c.obj_pre.items():
        struct.pack_into("<i", obj0, off, val)
    p_obj = g.blob(bytes(obj0))

    args = [p_img, p_off, c.sel, c.arg4, c.mode_pack, c.mode, p_en, p_par,
            p_aim, p_obj]
    esp = STACK_ADDR + STACK_SIZE - 0x40000
    esp -= 4 * len(args)
    for i, a in enumerate(args):
        uc.mem_write(esp + 4 * i, struct.pack("<I", a & 0xFFFFFFFF))
    esp -= 4
    uc.mem_write(esp, struct.pack("<I", RET_ADDR))
    uc.reg_write(UC_X86_REG_ESP, esp)

    grabbed = {}

    def snap(uc_, addr, size, ud):
        if addr != PRE_TAIL or "A6" in grabbed:
            return
        fesp = uc_.reg_read(UC_X86_REG_ESP)
        for nm, off, ln in (("A3", F_A3, A3_LEN), ("A4", F_A4, A4_LEN),
                            ("A5", F_A5, A5_LEN), ("A6", F_A6, A6_LEN),
                            ("A7", F_A7, A7_LEN)):
            grabbed[nm] = bytes(uc_.mem_read(fesp + off, ln))

    uc.hook_add(UC_HOOK_CODE, snap, begin=PRE_TAIL, end=PRE_TAIL + 4)
    n = [0]
    if count:
        def tick(uc_, a, s, u):
            n[0] += 1
        uc.hook_add(UC_HOOK_CODE, tick, begin=FN, end=FN_END)
    if blocks is not None:
        def blk(uc_, a, s, u):
            blocks.add(a)
        uc.hook_add(UC_HOOK_BLOCK, blk, begin=FN, end=FN_END)

    err = None
    try:
        uc.emu_start(FN, RET_ADDR, timeout=300_000_000)
    except UcError as ex:
        err = ex
    out = {
        "ret": uc.reg_read(UC_X86_REG_EAX) & 0xFFFFFFFF,
        "err": err,
        "obj": bytes(uc.mem_read(p_obj, OBJ_LEN)),
        "callocs": [(a, b) for a, b, _ in g.callocs],
        "n_free": len(g.frees),
        "insn": n[0],
    }
    out.update(grabbed)
    if "A6" in out:
        out["mask"] = out["obj"][OBJ_MASK:OBJ_MASK + MASK_LEN]
    return out


# ------------------------------------------------------------ case building


def _rng_image(rng, lo=0, hi=4095):
    return [rng.randint(lo, hi) for _ in range(IMG_WORDS)]


def default_en(all_on=True, hist=True):
    """The gate array (arg7).

    Words 0..6 carry the 14 zone gates as bytes (``test al,al`` /
    ``test ah,0xff`` at ``0x102af2bf``/``0x102af2ff``); word ``0x0e`` gates
    the whole-frame bank init at ``0x102af35a``; bytes ``0x10..0x13``,
    ``0x1e`` and ``0x24`` gate the six histogram accumulators — the only
    ``test byte [reg+imm],1`` sites in the whole function.
    """
    en = bytearray(0x40)
    if all_on:
        for i in range(7):
            struct.pack_into("<H", en, 2 * i, 0x0101)
        struct.pack_into("<H", en, 0x0E, 1)
        if hist:
            for o in (0x10, 0x11, 0x12, 0x13, 0x1E, 0x24):
                en[o] = 1
    return en


#: ``0x102af145`` — arg6 picks four parameter words: (hue lo, hue hi, chroma
#: lo, chroma hi).  Both chroma words are squared at ``0x102af261``.
MODE_PARAMS = {2: (0x4A, 0x4C, 0x46, 0x48), 1: (0x52, 0x54, 0x4E, 0x50),
               8: (0x3A, 0x3C, 0x36, 0x38), 4: (0x42, 0x44, 0x3E, 0x40)}


def smooth_image(rng, amp=12, slope_r=5, slope_c=3, dc=800):
    """A frame whose LOCAL 3x3 range is small and comparable to the threshold.

    Uniform noise over 0..4095 makes every 3x3 window's range enormous, so
    ``0x102b0a94 cmp ecx,edx`` is saturated and any window-geometry bug is
    invisible — that is exactly what the first version of this harness did,
    and section [4] caught it.  A gentle ramp plus small noise puts the range
    right on top of the threshold instead.
    """
    out = []
    for p in range(N_BANDS):
        for r in range(N_ROWS):
            for c in range(N_COLS):
                out.append(dc + 40 * p + slope_r * r + slope_c * c
                           + rng.randint(0, amp))
    return out


def build_par(rng, mode, *, thr=None, hue_lo=0, hue_hi=0x79, c_lo=1,
              c_hi=30000, bias=0):
    """A parameter struct with the fields the mask actually reads pinned.

    Random noise elsewhere, so a port that read the wrong offset would not
    accidentally read a plausible value.
    """
    par = bytearray(0x80)
    for i in range(0, 0x80, 2):
        struct.pack_into("<h", par, i, rng.randint(1, 3000))
    struct.pack_into("<h", par, 0x0C, 12 if thr is None else thr)
    lo, hi, cl, ch = MODE_PARAMS.get(mode, MODE_PARAMS[1])
    struct.pack_into("<h", par, lo, hue_lo)
    struct.pack_into("<h", par, hi, hue_hi)
    struct.pack_into("<h", par, cl, c_lo)
    struct.pack_into("<h", par, ch, c_hi)
    struct.pack_into("<h", par, 0x56, bias)
    return par


def build_case(rng, name, *, mode=1, mode_pack=0, sel=0, arg4=0, en=None,
               aim_null=False, image=None, offsets=None, par=None,
               obj_pre=None, **parkw):
    aim = None
    if not aim_null:
        aim = bytearray(0x40)
        for i in range(0, 0x40, 2):
            struct.pack_into("<h", aim, i, rng.randint(-200, 200))
    if en is None:
        en = default_en(hist=(mode_pack != 1))
    return Case(name, image=image if image is not None else smooth_image(rng),
                offsets=offsets or [rng.randint(-60, 60) for _ in range(6)],
                sel=sel, arg4=arg4, mode_pack=mode_pack, mode=mode, en=en,
                par=par if par is not None else build_par(rng, mode, **parkw),
                aim=aim, obj_pre=obj_pre)


def make_cases():
    rng = random.Random(0x102AECE0)
    cs = []
    for mode in (1, 2, 4, 8):
        for mp in (0, 2, 3):
            cs.append(build_case(rng, "mode%d/pack%d" % (mode, mp),
                                 mode=mode, mode_pack=mp))
    for sel in range(8):
        cs.append(build_case(rng, "sel%d" % sel, sel=sel))
    cs.append(build_case(rng, "arg4=1", arg4=1))
    cs.append(build_case(rng, "aim NULL", aim_null=True))
    # mode_pack == 1 skips the calloc block entirely (0x102af83a je), so the
    # histogram gates MUST be clear or the DLL derefs a null bin array.  That
    # is a real invariant of the caller, not a harness convenience.
    cs.append(build_case(rng, "pack1 (no histograms)", mode_pack=1,
                         en=default_en(hist=False)))
    # --- the local-contrast comparison, walked across its whole range -------
    # `0x102b0a94 cmp ecx,edx / jle` is a strict `>`.  A ramp of 5 per row and
    # 3 per column with no noise makes EVERY 3x3 window's range exactly 16, so
    # thr = 15/16/17 brackets the boundary and a `>` -> `>=` slip has to show.
    exact = smooth_image(random.Random(1), amp=0)
    for thr in (15, 16, 17):
        cs.append(build_case(rng, "exact range 16, thr=%d" % thr,
                             image=exact, thr=thr, offsets=[0] * 6))
    for thr in (0, 4, 8, 12, 20, 40, 4000):
        cs.append(build_case(rng, "smooth frame, thr=%d" % thr, thr=thr))
    cs.append(build_case(rng, "negative threshold", thr=-1))
    # `movsx word [esp+0x284]` — the threshold is SIGNED.  0x8001 is -32767
    # signed and 32769 unsigned, so a u16 read makes every sample fail the
    # test instead of passing it.
    cs.append(build_case(rng, "threshold word 0x8001 (signed)", thr=-32767))
    # a frame that is flat: every window range is 0, so `> thr` fails for
    # thr >= 0 and succeeds for thr < 0
    cs.append(build_case(rng, "flat frame", image=[1000] * IMG_WORDS, thr=-1))
    cs.append(build_case(rng, "flat frame, thr=0", image=[1000] * IMG_WORDS,
                         thr=0))
    # extremes of the int16 sample range, to reach the clamps and to make the
    # hue wheel's denominators large and its sextants all reachable
    cs.append(build_case(rng, "full int16 range",
                         image=[rng.choice([-32768, -1, 0, 1, 4095, 32767])
                                for _ in range(IMG_WORDS)], thr=4000))
    cs.append(build_case(rng, "zero offsets", offsets=[0] * 6))
    # --- stage 2: the hue/chroma window ------------------------------------
    # mode_pack == 2 skips stage 1 entirely (`0x102b09f6 je`), so every
    # A != 0 sample arrives at stage 2 with the mask byte still poison, i.e.
    # != 1, i.e. NOT short-circuited.  That is the case that exercises the
    # hue wheel across all six sextants at once.
    for hlo, hhi in ((0, 0x79), (0, 0x7A), (30, 90), (1, 2), (0x60, 0x79),
                     (-1, 0x79)):
        cs.append(build_case(rng, "pack2 hue window %d..%d" % (hlo, hhi),
                             mode_pack=2, hue_lo=hlo, hue_hi=hhi,
                             image=_hue_frame(rng), thr=0))
    for clo, chi in ((1, 30000), (1000, 30000), (1, 1200), (0, 1)):
        cs.append(build_case(rng, "pack2 chroma window %d..%d" % (clo, chi),
                             mode_pack=2, c_lo=clo, c_hi=chi,
                             image=_hue_frame(rng), thr=0))
    # a stage-2 case reached the OTHER way: stage 1 runs and writes 0, so the
    # mask byte is 0 (not poison) when `or bl,2` fires -> a mask byte of 2.
    cs.append(build_case(rng, "stage1 zeros then stage2 sets bit 1",
                         image=_hue_frame(rng), thr=100000 & 0x7FFF,
                         hue_lo=0, hue_hi=0x79))
    cs.append(build_case(rng, "stage2 with a huge positive bias",
                         mode_pack=2, bias=32000, image=_hue_frame(rng)))
    # the `0x102b0f89 cmp eax,0x79` wrap, densely
    for hlo, hhi in ((0, 0x79), (0, 3), (0x60, 0x79)):
        cs.append(build_case(rng, "pack2 hue WRAP, window %d..%d" % (hlo, hhi),
                             mode_pack=2, hue_lo=hlo, hue_hi=hhi,
                             image=_hue_frame_wrap(rng), thr=0))
    # --- the two stage-2 boundaries a uniform poison fill cannot reach ------
    # (a) chroma2 EXACTLY on a limit.  bands 4/5 = 3k/4k make chroma2 = (5k)^2,
    #     so par's chroma word can be put exactly on it and `0x102b0dd8 jge` /
    #     `0x102b0dd1 jle` are tested at equality rather than near it.
    pyth = _hue_frame(rng)
    for i in range(N_SAMPLES):
        pyth[PLANE_STRIDE * 4 + i] = 3 * (10 + i % 40)
        pyth[PLANE_STRIDE * 5 + i] = 4 * (10 + i % 40)
    for k in (10, 25, 49):
        cs.append(build_case(rng, "pack2 chroma2 == (5*%d)^2 exactly" % k,
                             mode_pack=2, image=pyth, offsets=[0] * 6,
                             c_lo=5 * k, c_hi=5 * k + 1, thr=0))
        cs.append(build_case(rng, "pack2 chroma2 == c_hi (5*%d)^2" % k,
                             mode_pack=2, image=pyth, offsets=[0] * 6,
                             c_lo=1, c_hi=5 * k, thr=0))
    # (b) the cross-call slot.  `0x102b0da5` reads obj+0x7b8 and adds par+0x56,
    #     then `0x102b0dbb jl` compares band3 against it.  With a uniform
    #     0xA5 fill +0x7b8 and +0x7bc are indistinguishable and the sum is so
    #     negative that the gate never rejects, so nothing pins either the
    #     offset or the bias.  Seeding the two slots differently, straddling
    #     band3 = 30000, pins both.
    for s479, bias in ((29000, 0), (30000, 0), (30001, 0), (29900, 100),
                       (29900, 101), (30500, -500), (30500, -501)):
        cs.append(build_case(
            rng, "pack2 slot479=%d bias=%d (band3 = 30000)" % (s479, bias),
            mode_pack=2, image=_hue_frame(rng), offsets=[0] * 6, thr=0,
            bias=bias, obj_pre={0x7B8: s479, 0x7BC: -s479}))
    for i, gates in enumerate((0x0000, 0x5555, 0xAAAA, 0x3FFF)):
        en = default_en()
        for k in range(14):
            en[k] = (gates >> k) & 1
        cs.append(build_case(rng, "gates%04x" % gates, en=en))
    en = default_en()
    struct.pack_into("<H", en, 0x0E, 0)
    cs.append(build_case(rng, "en[0x0e] = 0", en=en))
    en = default_en()
    struct.pack_into("<H", en, 0x0E, 0)
    en[0x0F] = 0x40
    cs.append(build_case(rng, "en[0x0e]=0 but en[0x0f]&0x40", en=en))
    en = default_en()
    struct.pack_into("<H", en, 0x0E, 0)
    en[0x14] = 0x40
    cs.append(build_case(rng, "en[0x0e]=0 but en[0x14]&0x40", en=en))
    return cs


def _hue_triples():
    """(band0, band1, band2) triples that reach every sextant AND the wrap.

    The first 720 sweep the circle.  The rest are the sextant-5 shapes
    ``s1 = s0 + 1 > s0 > s2`` — the only ones whose quotient can reach 20 and
    so drive ``0x65 + 20 == 0x79``, which ``0x102b0f89`` maps back to 1.
    Without them the ``>= 0x79`` wrap is never exercised and a port that
    dropped it would pass, which is exactly what section [4] reported before
    these were added.
    """
    trips = []
    for t in range(120):
        sext, frac = divmod(t, 20)
        hi, mid, lo = 3000, 1000 + 100 * frac, 1000
        trips.append(((hi, mid, lo), (hi, lo, mid), (mid, lo, hi),
                      (lo, mid, hi), (lo, hi, mid), (mid, hi, lo))[sext])
    for d in range(1, 80):
        trips.append((1000 + d, 1001 + d, 1000))     # s1 > s0 > s2, den = d+1
        trips.append((1000 + d, 1000 + d + 2, 1000))
    return trips


def _hue_frame(rng):
    """A frame whose bands 0/1/2 sweep the whole hue circle sextant by sextant.

    Bands 4 and 5 are given a wide magnitude sweep so the squared-chroma
    window has something to bite on, and band 3 is kept large so the
    ``[obj+0x7b8] + par[0x56]`` gate is not the thing doing the rejecting.
    """
    trips = _hue_triples()
    out = [0] * IMG_WORDS
    for i in range(N_SAMPLES):
        trip = trips[i % len(trips)]
        for p in range(3):
            out[PLANE_STRIDE * p + i] = trip[p]
        out[PLANE_STRIDE * 3 + i] = 30000
        out[PLANE_STRIDE * 4 + i] = (i * 7) % 900
        out[PLANE_STRIDE * 5 + i] = (i * 13) % 1100
    return out


def _hue_frame_wrap(rng):
    """Only the sextant-5 edge shapes, so the wrap is dense rather than rare."""
    trips = _hue_triples()[120:]
    out = [0] * IMG_WORDS
    for i in range(N_SAMPLES):
        trip = trips[i % len(trips)]
        for p in range(3):
            out[PLANE_STRIDE * p + i] = trip[p]
        out[PLANE_STRIDE * 3 + i] = 30000
        out[PLANE_STRIDE * 4 + i] = 300 + (i % 400)
        out[PLANE_STRIDE * 5 + i] = 200 + (i % 500)
    return out


# ------------------------------------------------------------- the compare

_BLOCKS = ("A3", "A4", "A5", "A6", "A7")


def compare(c: Case, dll: dict, port: dict, blocks):
    """Return ``(fails, samples, detail)`` over the blocks the port claims.

    A block the port does not return is *not* scored — it is reported as
    unported.  Scoring it as a failure would bury the blocks that are
    genuinely bit-exact; claiming it passes would be worse.
    """
    fails = samples = 0
    detail = []
    for nm in blocks:
        w = dll.get(nm)
        g = port.get(nm)
        if w is None or g is None:
            continue
        samples += len(w)
        bad = [i for i in range(len(w)) if w[i] != g[i]]
        if bad:
            fails += len(bad)
            detail.append((nm, len(bad), len(w), bad[0]))
    if dll["ret"] != port.get("ret"):
        fails += 1
        detail.append(("ret", 1, 1, None))
    samples += 1
    return fails, samples, detail


def run_port(c: Case):
    return M.measure(image=c.image, offsets=c.offsets, sel=c.sel, arg4=c.arg4,
                     mode_pack=c.mode_pack, mode=c.mode, en=bytes(c.en),
                     par=bytes(c.par), aim=None if c.aim is None else bytes(c.aim),
                     obj=c.fresh_obj())


def main(argv):
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    pe = dll_path.read_bytes()
    md5 = hashlib.md5(pe).hexdigest()
    print("DLL   %s" % dll_path)
    print("md5   %s%s" % (md5, "" if md5 == "eea9dcf78ee21d4f7c515a6c2512242d"
                          else "   *** NOT the documented build ***"))
    print("fn    fcn.102aece0  0x102aece0..0x102b4ca4  "
          "(24516 B, 1766 bb, 6643 insn)")
    print()

    cases = make_cases()

    # ---- [1] the DLL runs, whole, on every case -----------------------------
    print("  [1] fcn.102aece0 executed AS ONE FUNCTION, entry to ret")
    refs = []
    bad_run = 0
    total_insn = 0
    seen_blocks = set()
    for c in cases:
        d = run_dll(pe, c, count=True, blocks=seen_blocks)
        total_insn += d["insn"]
        if d["err"] is not None or d["ret"] != 0 or "A6" not in d:
            bad_run += 1
            print("      FAIL [%s] ret=%#x err=%s" % (c.name, d["ret"], d["err"]))
            continue
        refs.append((c, d))
    print("      %d/%d cases reached the success exit 0x102b4c93 (eax = 0)"
          % (len(refs), len(cases)))
    print("      %d instructions executed in total, %d calloc / %d free"
          % (total_insn, sum(len(d["callocs"]) for _, d in refs),
             sum(d["n_free"] for _, d in refs)))
    if refs:
        _, d0 = refs[0]
        poison = sum(1 for b in d0["obj"] if b == 0xA5)
        print("      object %d B: %d B written, %d B still 0xA5 poison"
              % (OBJ_LEN, OBJ_LEN - poison, poison))
        runs = []
        for i, b in enumerate(d0["obj"]):
            if b == 0xA5:
                continue
            if runs and runs[-1][1] == i:
                runs[-1][1] = i + 1
            else:
                runs.append([i, i + 1])
        print("      written extents: %s"
              % " ".join("+0x%x..+0x%x" % (a, b) for a, b in runs))
    print("      basic blocks entered across the case set: %d of 1766 (%.0f%%)"
          % (len(seen_blocks), 100.0 * len(seen_blocks) / 1766))

    # ---- [2] the other three exits are reachable ----------------------------
    print("\n  [2] negative controls: every one of the four ret sites is live")
    n_ctl = ok_ctl = 0
    rng = random.Random(0xBADF00D)
    c = build_case(rng, "bad mode", mode=3)
    d = run_dll(pe, c)
    n_ctl += 1
    ok_ctl += d["ret"] == RET_BAD_MODE
    print("      arg6 = 3 (not in {1,2,4,8}) -> ret %#x  (want %#x, 0x102b4ca3)"
          % (d["ret"], RET_BAD_MODE))
    c = build_case(rng, "calloc fails")
    d = run_dll(pe, c, calloc_fail_after=3)
    n_ctl += 1
    ok_ctl += d["ret"] == RET_CALLOC_FAIL
    print("      calloc #4 returns NULL       -> ret %#x  (want %#x, 0x102afac8)"
          % (d["ret"], RET_CALLOC_FAIL))
    print("      and control PROVABLY continues past 0x102afac8 on the normal")
    print("      path: 0x102afa8a is `je 0x102afac9`, one byte after that ret,")
    print("      and [1]'s cases all reach 0x102b4c93 instead (docs/74 §192.1a).")
    print("      NOT REACHED: the fourth ret, 0x102b48f3 (eax %#x).  Its guard is"
          % RET_NO_SAMPLES)
    print("      a scan of ONE calloc'd histogram (frame +0x208, i.e. descriptor")
    print("      21) that returns the code when no bin holds 2 or more counts —")
    print("      and a block hook shows 0x102b48c0 is not entered by ANY case in")
    print("      this set, so a whole region upstream of it is still unexercised.")
    print("      Stated as a coverage gap, not as a passed control.")

    # ---- [3] the port ------------------------------------------------------
    if M is None:
        print("\n  [3] pakon_sba_measure not importable — DLL side only")
        return 0 if (bad_run == 0 and ok_ctl == n_ctl) else 1

    print("\n  [3] pakon_sba_measure vs the real DLL, byte for byte")
    print("      ported:")
    for s in M.PORTED:
        print("        + %s" % s)
    print("      NOT ported (not scored below — absence is not a pass):")
    for s in M.NOT_PORTED:
        print("        - %s" % s)
    blocks = ("mask",)
    fails, samples, refs2 = _score(refs, blocks, label="port")
    print("      %d/%d bytes bit-exact over %d cases (%s)"
          % (samples - fails, samples, len(refs),
             "ALL BIT-EXACT" if not fails else "FAIL"))

    # ---- [4] deliberate port bugs -----------------------------------------
    print("\n  [4] deliberate port bugs — each must be caught by a VALUE diff")
    n_missed = _teeth(refs, blocks)

    # ---- [5] the dead white-balanced hue arm -------------------------------
    print("\n  [5] the white-balanced hue arm at 0x102b0b15 is dead in this build")
    tv = M.load_tables()["global_%x" % M.HUE_WB_GLOBAL]
    print("      [%#x] = %#x in the shipped image, and a byte scan of the whole"
          % (M.HUE_WB_GLOBAL, tv))
    print("      24 MB image finds exactly ONE occurrence of that address —")
    print("      the read at 0x102b0b09 itself.  No instruction in the DLL names")
    print("      it, so on the direct-reference evidence 0x102b0b15..0x102b0d95")
    print("      never executes and the raw-band arm at 0x102b0e75 is the one")
    print("      that runs.  CAVEAT: a byte scan rules out DIRECT references")
    print("      only — a computed pointer, or a write from another module, is")
    print("      not excluded, and no live capture has been checked against it.")
    print("      The port therefore refuses rather than guesses if it is ever")
    print("      handed a non-zero value.  That also settles what")
    print("      docs/74 §192 left open: the cross-call read of [obj+0x7b8] at")
    print("      0x102b0da5 IS live — it is reached from the 0x102b0e75 arm, not")
    print("      only from the dead one.")

    # ---- [6] the A6 bank block + A7 counts, vs the DLL, byte for byte -------
    print("\n  [6] measure_bank_block: A6 min/max/sum + A7 per-bank counts vs DLL")
    bank_bad = bank_tot = a7_bad = a7_tot = 0
    for c, d in refs:
        A6p, counts = M.measure_bank_block(image=c.image, offsets=c.offsets,
                                           sel=c.sel, en=bytes(c.en))
        A6d = d["A6"]
        for n in range(14):
            b = 0x120 * (n // 2) + 0x90 * (n % 2)
            for off in range(b, b + 0x48):       # min(+0) max(+0x18) sum(+0x30)
                bank_tot += 1
                if A6p[off] != A6d[off]:
                    bank_bad += 1
        A7d = d["A7"]
        for n in range(14):
            a7_tot += 1
            if (M.A7_BANK_DIVISORS[n] & 0xFFFF) != struct.unpack_from("<H", A7d, 2 * n)[0]:
                a7_bad += 1
    print("      A6 14-bank min/max/sum: %d/%d bytes bit-exact (%s)"
          % (bank_tot - bank_bad, bank_tot,
             "ALL BIT-EXACT" if not bank_bad else "FAIL"))
    print("      A7 per-bank counts:     %d/%d words bit-exact (%s)"
          % (a7_tot - a7_bad, a7_tot,
             "ALL BIT-EXACT" if not a7_bad else "FAIL"))
    print("      (whole-frame region, histograms and percentiles are verified"
          " against the six real cap.pkl frames — not on synthetic inputs,"
          " which drive no real mask/histograms.)")

    return 0 if (fails == 0 and bad_run == 0 and ok_ctl == n_ctl
                 and n_missed == 0 and bank_bad == 0 and a7_bad == 0) else 1


def _score(refs, blocks, label=""):
    fails = samples = 0
    per_block = {nm: [0, 0] for nm in blocks}
    for c, d in refs:
        p = run_port(c)
        f, n, detail = compare(c, d, p, blocks)
        fails += f
        samples += n
        for nm, nbad, ntot, first in detail:
            if nm in per_block:
                per_block[nm][0] += nbad
        for nm in per_block:
            if d.get(nm) is not None:
                per_block[nm][1] += len(d[nm])
        if f:
            print("      MISMATCH [%s]: %s" % (
                c.name, ", ".join("%s %d/%d B (first +0x%x)"
                                  % (nm, a, b, o if o is not None else 0)
                                  for nm, a, b, o in detail)))
    for nm in blocks:
        bad, tot = per_block[nm]
        if tot:
            print("        %-5s %7d/%-7d %s" % (nm, tot - bad, tot,
                                                "bit-exact" if not bad else "FAIL"))
    return fails, samples, refs


def _teeth(refs, blocks):
    """Break the port on purpose; report caught / provably inert / NOT CAUGHT."""
    caught = inert = missed = 0

    def probe(label, attr, repl, inert_reason=None):
        nonlocal caught, inert, missed
        orig = getattr(M, attr)
        setattr(M, attr, repl)
        n_case = n_byte = 0
        try:
            for c, d in refs:
                try:
                    p = run_port(c)
                except Exception:
                    # A mutation that only ever throws proves nothing about the
                    # comparison — §194.3's lesson.  Count it as not caught.
                    continue
                bad = sum(a != b for a, b in zip(d["mask"], p.get("mask", b"")))
                if bad:
                    n_case += 1
                    n_byte += bad
        finally:
            setattr(M, attr, orig)
        if n_case:
            caught += 1
            print("      CAUGHT             %-46s %d/%d cases, %d mask bytes"
                  % (label, n_case, len(refs), n_byte))
        elif inert_reason:
            inert += 1
            print("      PROVABLY INERT     %-46s %s" % (label, inert_reason))
        else:
            missed += 1
            print("      NOT CAUGHT         %-46s" % label)
            print("      FAILED: a deliberate port bug was invisible — the "
                  "comparison or the inputs are too weak")

    orig_win = M.WINDOW_BASE
    probe("3x3 window base 2555 -> 2556", "WINDOW_BASE", orig_win + 1)
    probe("3x3 window base 2555 -> 2592 (no -row-1col)", "WINDOW_BASE", 2592)
    probe("window row step 36 -> 35", "WINDOW_ROW", 35)

    o_i16 = M._i16
    probe("threshold read unsigned (i16 -> u16)", "_i16", lambda v: v & 0xFFFF)

    o_hue = M.hue_code
    probe("hue wheel: sextant bases all 1", "hue_code",
          lambda a, b, c: 1 if (a == b == c) else 1)
    probe("hue wheel: round-to-nearest term dropped", "hue_code",
          _hue_no_round)
    probe("hue wheel: >= 0x79 wrap removed", "hue_code", _hue_no_wrap)

    probe("idiv -> floor division", "_idiv",
          lambda n, d: (_ for _ in ()).throw(M.MeasureFault("d0")) if d == 0 else n // d,
          inert_reason="every sextant's guard forces numerator >= 0 and "
                       "denominator > 0 (the == case exits at 0x102b0ea0), so "
                       "trunc and floor coincide by construction")
    probe("sar 1 -> logical shift on negatives", "_sar1",
          lambda v: (v & 0xFFFFFFFF) >> 1,
          inert_reason="the only `sar reg,1` operand is that same positive "
                       "denominator, so the sign bit is never set")

    o_sel = dict(M.SEL_TABLES)
    swapped = dict(o_sel)
    swapped[0], swapped[1] = o_sel[1], o_sel[0]
    probe("arg3 byte tables 0 and 1 swapped", "SEL_TABLES", swapped)

    o_mask = M.selection_mask
    for label, kw in (
            ("stage-1 test `>` -> `>=`", {"ge": True}),
            ("stage-2 hue test `<=` -> `<`", {"hue_strict": True}),
            ("stage-2 chroma test `>=` -> `>`", {"chroma_loose": True}),
            ("stage-2 writes 2 instead of `b | 2`", {"assign": True}),
            ("[obj+0x7b8] read as +0x7bc (slot 480)", {"slot": 0x7BC}),
            ("chroma from bands 3,4 instead of 4,5", {"chroma_bands": (3, 4)}),
            ("hue from bands 1,2,0 instead of 0,1,2", {"hue_rot": True}),
            ("stage-2's `if b == 1: continue` dropped", {"no_short": True}),
            ("par+0x56 bias term dropped", {"no_bias": True}),
    ):
        probe(label, "selection_mask", _mutated_mask(o_mask, **kw))

    print("      caught %d   provably inert %d   NOT CAUGHT %d"
          % (caught, inert, missed))
    return missed


def _mutated_mask(_orig, *, ge=False, hue_strict=False, chroma_loose=False,
                  assign=False, slot=0x7B8, chroma_bands=(4, 5), hue_rot=False,
                  no_short=False, no_bias=False):
    """A deliberately-wrong `selection_mask`, one comparison or offset at a time."""
    def f(image, offsets, *, sel, mode, mode_pack, en, par, obj, tables=None,
          dll_path=None):
        t = tables or M.load_tables(dll_path)
        ta = t[M.SEL_TABLES.get(sel & 0xFFFF, M.SEL_DEFAULT)[0]]
        if not (en[0x0E] or (en[0x0F] & 0x40) or (en[0x14] & 0x40)):
            return obj
        a5 = mode_pack & 0xFFFF
        thr = M._i16(struct.unpack_from("<H", par, 0x0C)[0])
        hl, hh, cl, ch = M.MODE_PARAMS[mode]
        hue_lo = M._i16(struct.unpack_from("<H", par, hl)[0])
        hue_hi = M._i16(struct.unpack_from("<H", par, hh)[0])
        c_lo = M._i32(M._i16(struct.unpack_from("<H", par, cl)[0]) ** 2)
        c_hi = M._i32(M._i16(struct.unpack_from("<H", par, ch)[0]) ** 2)
        bias = 0 if no_bias else M._i16(struct.unpack_from("<H", par, 0x56)[0])
        s479 = M._i32(struct.unpack_from("<I", bytes(obj), slot)[0])
        for r in range(N_ROWS):
            for c in range(N_COLS):
                idx = N_COLS * r + c
                band = [M._i32(image[PLANE_STRIDE * p + idx] - offsets[p])
                        for p in range(N_BANDS)]
                a = ta[idx]
                if a5 != 2:
                    if a == 0:
                        obj[0xC20 + idx] = 0
                    else:
                        base = idx + M.WINDOW_BASE
                        mn = mx = image[base]
                        for k in range(3):
                            for row in (0, M.WINDOW_ROW, 2 * M.WINDOW_ROW):
                                v = image[base + row + k]
                                if v < mn:
                                    mn = v
                                elif v > mx:
                                    mx = v
                        rng_ = mx - mn
                        obj[0xC20 + idx] = 1 if (rng_ >= thr if ge
                                                 else rng_ > thr) else 0
                if a5 == 1 or a == 0:
                    continue
                b = obj[0xC20 + idx]
                if b == 1 and not no_short:
                    continue
                p0, p1 = chroma_bands
                chroma2 = M._i32(band[p0] * band[p0] + band[p1] * band[p1])
                h = (M.hue_code(band[1], band[2], band[0]) if hue_rot
                     else M.hue_code(band[0], band[1], band[2]))
                if band[3] < M._i32(s479 + bias):
                    continue
                if (h < hue_lo if hue_strict else h <= hue_lo) or h >= hue_hi:
                    continue
                if chroma2 <= c_lo or (chroma2 > c_hi if chroma_loose
                                       else chroma2 >= c_hi):
                    continue
                obj[0xC20 + idx] = 2 if assign else (b | 2)
        return obj
    return f


def _hue_no_round(s0, s1, s2):
    """`hue_code` with the vendor's ``+ (den >> 1)`` rounding term removed."""
    if s0 == s1 and s1 == s2:
        return 1
    arms = ((s0 >= s1 >= s2, 0x01, s0 - s2, 20 * (s0 - s1)),
            (s0 > s2 > s1, 0x15, s0 - s1, 20 * (s2 - s1)),
            (s2 >= s0 >= s1, 0x29, s2 - s1, 20 * (s2 - s0)),
            (s2 > s1 > s0, 0x3D, s2 - s0, 20 * (s1 - s0)),
            (s1 >= s2 >= s0, 0x51, s1 - s0, 20 * (s1 - s2)),
            (s1 > s0 > s2, 0x65, s1 - s2, 20 * (s0 - s2)))
    for ok, base, den, num in arms:
        if ok:
            h = base + M._idiv(num, den)
            return h if h < 0x79 else 1
    return 1


def _hue_no_wrap(s0, s1, s2):
    """`hue_code` without the ``0x102b0f89 cmp eax,0x79`` wrap."""
    if s0 == s1 and s1 == s2:
        return 1
    arms = ((s0 >= s1 >= s2, 0x01, s0 - s2, 20 * (s0 - s1)),
            (s0 > s2 > s1, 0x15, s0 - s1, 20 * (s2 - s1)),
            (s2 >= s0 >= s1, 0x29, s2 - s1, 20 * (s2 - s0)),
            (s2 > s1 > s0, 0x3D, s2 - s0, 20 * (s1 - s0)),
            (s1 >= s2 >= s0, 0x51, s1 - s0, 20 * (s1 - s2)),
            (s1 > s0 > s2, 0x65, s1 - s2, 20 * (s0 - s2)))
    for ok, base, den, num in arms:
        if ok:
            return base + M._idiv(M._sar1(den) + num, den)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
