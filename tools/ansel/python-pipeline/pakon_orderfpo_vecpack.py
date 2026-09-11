#!/usr/bin/env python3
"""The producer of the 720-int32 SBA statistics vector at ``scene+0x3c``.

``PakonIMAu.dll`` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``, ``fcn.102b7440``
(``0x102b7440`` … ``0x102b81c7``, 3457 B, 90 basic blocks, 910 instructions,
**no calls, no imports, no globals** — ``afi`` reports ``is-pure: true``,
``out-degree: 0``).

Why this function
-----------------
docs/74 §88/§89/§90 located the vendor's ``L`` term as ``vars[133]`` of the
``pcode-dls_1.7`` program, run by the already-ported VM (``pakon_vm.py``) over
an input vector at ``(sba_order_fpo_calc arg11) + 0x3c``.  §90 proved the VM
port reproduces ``L`` 12/12 bit-exact **from a captured vector**, leaving the
vector's producer as the blocker.  The call chain, read out of the binary:

    fcn.1028b8d0   (sba_order_fpo_calc, 2958 B)
      ├─ fcn.102aece0        24475 B — the per-sample statistics engine
      │    └─ fcn.102b7440    3457 B — THIS: packs those statistics into
      │                                the VM's input vector at scene+0x3c
      └─ fcn.102ac310  @0x1028bfa8   — VM driver; stores
             params[+0x198] = 0x2d0        (= 720 input slots)
             params[+0x19c] = scene+0x3c   (= the vector)
           └─ fcn.102ac140 → fcn.102aadf0  (the pcode VM, ported)

So ``fcn.1028b8d0`` does **not** contain the producer; it contains the two
calls above.  This module ports the packer only.  ``fcn.102aece0`` — which
computes the statistics this packer consumes — is **not** ported.

On the vector's length.  The last store this function makes is
``mov [ecx+0xb78], eax`` at ``0x102b7d77`` — slot ``(0xb78-0x3c)/4 == 719`` —
so ``fcn.102b7440`` owns exactly slots 0…719.  Slots 720…732
(``scene+0xb7c``…``+0xbac``) are written by ``fcn.1028b8d0``'s own top level
and are ported separately below (``vecpack_tail``).  ``pakon_vm``'s dependency
closure for ``L`` reads indices up to **732**, so the vector *as consumed* is
at least 733 long; docs/74 §89.3/§90.1 dumped ``0xb80`` bytes and called it
736.  ``push 0x2d0`` at ``0x1028bfa0`` (= 720) lands in ``params[+0x198]`` and
matches this function's span exactly — suggestive, but what reads ``+0x198``
was **not** traced, so it is not offered as a second proof of the length.

Layout recovered (all indices are int32 slots from ``scene+0x3c``)
------------------------------------------------------------------
``arg6`` is an array of **7 records × 0x120 B**, each record two ``0x90``-byte
half-records ("banks").  Bank *b* of record *i* is at ``arg6 + 0x120*i +
0x90*b`` and holds four 6-dword rows at ``+0x00 +0x18 +0x30 +0x48`` and four
scalars at ``+0x7c +0x80 +0x88 +0x8c``.  Each bank fills 34 consecutive slots
starting at ``68*i + 34*b``:

    +0 … +5    row(+0x30)[j] // i16(word[arg7 + 4*i + 2*b])   <- the only
    +6 … +11   row(+0x00)[j]                                     division
    +12 … +17  row(+0x18)[j]
    +18 … +23  row(+0x30)[j]        (the same row, undivided)
    +24 … +29  row(+0x48)[j]
    +30 … +33  scalars +0x7c +0x80 +0x88 +0x8c

Bank *b* of record *i* is written only when ``arg8[2*i + b] != 0``.  That
accounts for slots 0…475.  Slots 476…611 are a second, differently-sourced
group of five banks gated on ``word[arg8+0xe] != 0`` and selected by
``i16(word[scene+6]) > i16(word[arg9+0xe])``; 612…615 are four header words of
``scene``; 616…690 a verbatim copy of ``arg3[0:75]``; 691…709 of
``arg4[0:19]``; 710…718 of ``arg5[0:9]``; 719 a single divided scalar.

Evidence status
---------------
Tier 1 for the arithmetic: ``pakon_orderfpo_vecpack_golden.py`` executes the
real DLL bytes under Unicorn and diffs the whole 4608-byte scene buffer
byte-for-byte against this port.  Two slot fragments of this same function
were independently ported earlier (``pakon_fos.fos_postfill_c_low`` /
``fos_postfill_c_high``, ``FOS_POSTFILL_C_PORTED``); their mapping agrees with
the one derived here, which is a second, independent reading of the same code.

**Not claimed:** that this closes ``L``.  It does not — ``fcn.102aece0``
produces every number this function packs, and it is unported.  See the module
docstring of the golden harness for what is and is not established.
"""
from __future__ import annotations

import struct

VECPACK_PORTED = True  # PakonIMAu.dll @ 0x102b7440, whole function

VEC_OFF = 0x3C  # PakonIMAu.dll: scene+0x3c, from `lea eax,[esi+0x3c]` @ 0x1028bf9c
VEC_SLOTS = 0x2D0  # PakonIMAu.dll: `push 0x2d0` @ 0x1028bfa0 -> params[+0x198]
FORCE_N = 0x360  # PakonIMAu.dll @ 0x102b75e7 `mov eax, 0x360`


class VecPackFault(Exception):
    """The DLL would raise #DE (idiv by zero) on these inputs."""


def _i16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def _idiv(n: int, d: int) -> int:
    """``cdq; idiv`` — truncate toward zero.  #DE on d == 0 or quotient
    overflow, both of which the DLL would raise rather than wrap."""
    if d == 0:
        raise VecPackFault("idiv by zero")
    q = abs(n) // abs(d)
    q = -q if (n < 0) ^ (d < 0) else q
    if not -0x80000000 <= q <= 0x7FFFFFFF:
        raise VecPackFault("idiv quotient overflow")
    return q


def _rdiv_half_away(n: int, d: int) -> int:
    """PakonIMAu.dll ``0x102b7d40…0x102b7d90`` — round half away from zero.

    The DLL computes ``half = (d - (d >> 31)) >> 1`` and then adds it to the
    numerator when ``sign(n) == sign(d)``, subtracts it otherwise, before a
    plain truncating ``idiv``.  Both branches are exercised by the harness.
    """
    if d == 0:
        raise VecPackFault("idiv by zero")
    half = (d - (d >> 31)) >> 1  # arithmetic shift, matches `cdq; sub; sar 1`
    n = _i32(n + half) if (n >= 0) == (d >= 0) else _i32(n - half)
    return _idiv(n, d)


class _Buf:
    """A little-endian view over a bytearray, mirroring the DLL's accesses."""

    __slots__ = ("b",)

    def __init__(self, b: bytearray | bytes) -> None:
        self.b = bytearray(b)

    def d(self, off: int) -> int:
        return struct.unpack_from("<i", self.b, off)[0]

    def setd(self, off: int, v: int) -> None:
        struct.pack_into("<i", self.b, off, _i32(v))

    def w(self, off: int) -> int:
        return struct.unpack_from("<h", self.b, off)[0]

    def setw(self, off: int, v: int) -> None:
        struct.pack_into("<H", self.b, off, v & 0xFFFF)

    def bt(self, off: int) -> int:
        return self.b[off]


def _bank(scene: _Buf, arg6: _Buf, arg7: _Buf, *, i: int, b: int) -> None:
    """One 34-slot bank — PakonIMAu.dll block A ``0x102b763f…0x102b76d1``
    (``b == 0``) / block B ``0x102b76e8…0x102b777f`` (``b == 1``).

    Both blocks are byte-identical in structure; only the source base
    (``+0x90*b``) and the divisor word (``arg7 + 4*i + 2*b``) differ.
    """
    src = 0x120 * i + 0x90 * b
    dst = VEC_OFF + 4 * (68 * i + 34 * b)
    div = _i16(arg7.w(4 * i + 2 * b))
    for j in range(6):
        scene.setd(dst + 0x00 + 4 * j, _idiv(arg6.d(src + 0x30 + 4 * j), div))
        scene.setd(dst + 0x18 + 4 * j, arg6.d(src + 0x00 + 4 * j))
        scene.setd(dst + 0x30 + 4 * j, arg6.d(src + 0x18 + 4 * j))
        scene.setd(dst + 0x48 + 4 * j, arg6.d(src + 0x30 + 4 * j))
        scene.setd(dst + 0x60 + 4 * j, arg6.d(src + 0x48 + 4 * j))
    scene.setd(dst + 0x78, arg6.d(src + 0x7C))
    scene.setd(dst + 0x7C, arg6.d(src + 0x80))
    scene.setd(dst + 0x80, arg6.d(src + 0x88))
    scene.setd(dst + 0x84, arg6.d(src + 0x8C))


def _group(scene: _Buf, arg6: _Buf, *, slot: int, src: int, div: int) -> None:
    """One 30-slot group of the 476…611 region — the ``0x102b77f0`` loop shape.

    Same five-store body as ``_bank`` but reached with a different dest stride,
    and the four trailing scalars are written by the caller because their
    source offsets differ between the two selector branches.
    """
    dst = VEC_OFF + 4 * slot
    for j in range(6):
        scene.setd(dst + 0x00 + 4 * j, _idiv(arg6.d(src + 4 * j), div))
        scene.setd(dst + 0x18 + 4 * j, arg6.d(src - 0x30 + 4 * j))
        scene.setd(dst + 0x30 + 4 * j, arg6.d(src - 0x18 + 4 * j))
        scene.setd(dst + 0x48 + 4 * j, arg6.d(src + 4 * j))
        scene.setd(dst + 0x60 + 4 * j, arg6.d(src + 0x18 + 4 * j))


def _quad(scene: _Buf, arg6: _Buf, *, slot: int, src: int) -> None:
    """The four scalars that follow a ``_group`` — stored out of slot order by
    the DLL (``+0, +2, +1, +3``); the values are what matter."""
    scene.setd(VEC_OFF + 4 * (slot + 0), arg6.d(src + 0x00))
    scene.setd(VEC_OFF + 4 * (slot + 1), arg6.d(src + 0x04))
    scene.setd(VEC_OFF + 4 * (slot + 2), arg6.d(src + 0x0C))
    scene.setd(VEC_OFF + 4 * (slot + 3), arg6.d(src + 0x10))


def vecpack(
    scene: bytes | bytearray,
    *,
    mode: int,
    arg2: int,
    arg3: bytes | bytearray,
    arg4: bytes | bytearray,
    arg5: bytes | bytearray,
    arg6: bytes | bytearray,
    arg7: bytes | bytearray,
    arg8: bytes | bytearray,
    arg9: bytes | bytearray,
) -> tuple[bytearray, bytearray, bytearray]:
    """Port of ``PakonIMAu.dll`` ``fcn.102b7440``.

    Argument names are positional index in the DLL's own cdecl frame
    (``arg1`` = ``mode`` = ``[esp+4]`` at entry … ``arg10`` = ``scene``).
    Returns ``(scene, arg6, arg7)`` — the function mutates all three.
    """
    S = _Buf(scene)
    A6 = _Buf(arg6)
    A7 = _Buf(arg7)
    A8 = _Buf(arg8)
    A9 = _Buf(arg9)

    # PakonIMAu.dll @ 0x102b7443…0x102b747c — five header reads, saved before
    # anything below can overwrite them.
    v38 = S.w(0x0C)
    v3c = S.w(0x0A)
    v10 = S.w(0x06)
    v34 = S.w(0x08)
    v40 = S.w(0x16)

    mode1 = (mode & 0xFFFF) == 1  # PakonIMAu.dll @ 0x102b745b `cmp word,1`
    last = 0  # PakonIMAu.dll: eax at ret; only meaningful on the mode!=1 path

    if not mode1:
        # -- 616…690: verbatim arg3[0:75] — PakonIMAu.dll @ 0x102b7486
        for a in range(0x4B):
            S.setd(0x9DC + 4 * a, struct.unpack_from("<i", arg3, 4 * a)[0])
        # -- 691…709: verbatim arg4[0:19] — @ 0x102b74a0
        for a in range(0x13):
            S.setd(0xB08 + 4 * a, struct.unpack_from("<i", arg4, 4 * a)[0])
        # -- 710…718: verbatim arg5[0:9] — @ 0x102b74be
        for a in range(9):
            S.setd(0xB54 + 4 * a, struct.unpack_from("<i", arg5, 4 * a)[0])

        # -- slot 719's numerator, and (on the low branch only) a shuffle of
        #    arg6's own 0x7e0… region — PakonIMAu.dll @ 0x102b751a
        if _i16(v10) > _i16(A9.w(0x0E)):
            last = _idiv(A6.d(0x8AC), _i16(v34))
        else:
            last = _idiv(A6.d(0x3C), _i16(A7.w(0x00)))
            # @ 0x102b7542…0x102b75e1 — 18 dwords copied arg6[k] -> arg6[0x7e0+k]
            for k in range(0x12):
                A6.setd(0x7E0 + 4 * k, A6.d(4 * k))
            # @ 0x102b75e7 — the vendor forces these four counts
            A7.setw(0x1C, FORCE_N)
            A7.setw(0x1E, FORCE_N)
            A7.setw(0x20, A7.w(0x0A))
            A7.setw(0x22, A7.w(0x0A))

    # -- slots 0…475: 7 records × 2 banks, each gated by its own arg8 byte.
    #    PakonIMAu.dll @ 0x102b7630…0x102b77ae (mode!=1) and
    #    @ 0x102b7dd0…0x102b7f32 (mode==1) — identical bodies.
    for i in range(7):
        for b in (0, 1):
            if A8.bt(2 * i + b) != 0:
                _bank(S, A6, A7, i=i, b=b)

    # -- slots 476…611.  @ 0x102b77b4 (mode!=1) / @ 0x102b7f38 (mode==1)
    if A8.w(0x0E) != 0:
        high = _i16(v10) > _i16(A9.w(0x0E))
        alt = A7.w(0x20) != 0
        if high:
            _group(S, A6, slot=476, src=0x810, div=_i16(A7.w(0x1C)))
            _quad(S, A6, slot=506, src=0x85C)
            if mode1:
                # @ 0x102b7fdd — the mode-1 path stops after ONE more group
                # and never writes 510…543 or 578…611.
                if alt:
                    _group(S, A6, slot=544, src=0x930, div=_i16(A7.w(0x20)))
                    _quad(S, A6, slot=574, src=0x97C)
                else:
                    _group(S, A6, slot=544, src=0x300, div=_i16(A7.w(0x0A)))
                    _quad(S, A6, slot=574, src=0x34C)
            else:
                _group(S, A6, slot=510, src=0x8A0, div=_i16(A7.w(0x1E)))
                _quad(S, A6, slot=540, src=0x8EC)
                if alt:  # @ 0x102b78e0 `cmp word [arg7+0x20], 0`
                    _group(S, A6, slot=544, src=0x930, div=_i16(A7.w(0x20)))
                    _quad(S, A6, slot=574, src=0x97C)
                    _group(S, A6, slot=578, src=0x9C0, div=_i16(A7.w(0x22)))
                    _quad(S, A6, slot=608, src=0xA0C)
                else:
                    _group(S, A6, slot=544, src=0x300, div=_i16(A7.w(0x0A)))
                    _quad(S, A6, slot=574, src=0x34C)
                    _group(S, A6, slot=578, src=0x300, div=_i16(A7.w(0x0A)))
                    _quad(S, A6, slot=608, src=0x34C)
        else:
            _group(S, A6, slot=476, src=0x030, div=_i16(A7.w(0x00)))
            _quad(S, A6, slot=506, src=0x07C)
            _group(S, A6, slot=544, src=0x300, div=_i16(A7.w(0x0A)))
            _quad(S, A6, slot=574, src=0x34C)
            if not mode1:
                _group(S, A6, slot=510, src=0x030, div=_i16(A7.w(0x00)))
                _quad(S, A6, slot=540, src=0x07C)
                _group(S, A6, slot=578, src=0x300, div=_i16(A7.w(0x0A)))
                _quad(S, A6, slot=608, src=0x34C)

    if mode1:
        # @ 0x102b81b4 — the mode-1 path writes exactly one header slot.
        S.setd(0x9CC, _i16(v10))
        return S.b, A6.b, A7.b

    # -- slots 612…615 — @ 0x102b7ccc
    S.setd(0x9D4, _i16(v34))  # 614
    S.setd(0x9D8, _i16(v38))  # 615
    S.setd(0x9CC, _i16(v10))  # 612
    S.setd(0x9D0, _i16(v3c))  # 613

    # -- scene+0x18 (a header word, NOT part of the vector) — @ 0x102b7cf1
    if (arg2 & 0xFFFF) == 1:
        thr, den = _i16(A9.w(0x00)), _i16(A9.w(0x02))
    else:
        thr, den = _i16(A9.w(0x04)), _i16(A9.w(0x06))
    if thr == 0:
        S.setw(0x18, 1000)  # @ 0x102b7d1d
    elif _i16(v40) <= thr:
        S.setw(0x18, 0)  # @ 0x102b7d2e
    else:
        num = _i32((_i16(v40) - thr) * 1000)
        S.setw(0x18, _rdiv_half_away(num, den) & 0xFFFF)

    # @ 0x102b7d5c — two zero-guards on arg6 itself
    if A6.d(0x24) == 0:
        A6.setd(0x24, 1)
    if A6.d(0x0C) == 0:
        A6.setd(0x0C, 1)

    S.setd(0xB78, last)  # slot 719 — @ 0x102b7d77
    return S.b, A6.b, A7.b


VECPACK_TAIL_PORTED = True  # PakonIMAu.dll @ 0x1028bb05 and @ 0x1028bea5

# ``pakon_vm``'s dependency closure for ``L`` (``vars[133]``) reads 85 distinct
# ``in[]`` slots, the highest being **732** — past the 720 that
# ``fcn.102b7440`` writes.  Slots 720…732 are written by ``fcn.1028b8d0``'s own
# top level, in two straight-line stretches, from arguments the live capture
# already dumps.  Ported here so the vector has exactly one owner per slot.
#
#   slot  scene    written at        value
#   720   +0xb7c   0x1028beb5        i16(arg6.w[0x0c]) * 10
#   721   +0xb80   0x1028bf2e/bf36   i8(flags[1])  or -1 for 0xfc..0xff
#   722   +0xb84   0x1028bf03/bf11   i8(flags[2])  or -1 for 0xfe/0xff
#   723   +0xb88   0x1028bf4c/bf54   i8(flags[3])  or -1 for 0xfe/0xff
#   724   +0xb8c   0x1028bf6c        i8(flags[4])  or -1 for 0xfe/0xff
#   725   +0xb90   0x1028bf79        flags[6] == 1
#   726   +0xb94   0x1028bec4        i16(arg6.w[0x0e]) * 10
#   727   +0xb98   0x1028bed3        i16(arg6.w[0x10]) * 10
#   728   +0xb9c   0x1028bee0        i16(params.w[0x10e])
#   729   +0xba0   0x1028beed        i16(params.w[0x110])
#   730   +0xba4   0x1028bcf5 …      1 / 2 / 4 / 8 selector — NOT ported here
#   731   +0xba8   0x1028bb0d        (flagsword & 0x800) != 0
#   732   +0xbac   0x1028bb1f        (i16(flagsword) & 0x1000) >> 12
#
# ``arg6`` / ``params`` / ``flags`` are ``fcn.1028b8d0``'s 1-based args 6, 7
# and 3 — the live-hook labels ``arg5_big``, ``arg6_big`` and ``arg2_big``.
# ``flagsword`` is its arg 5, i.e. ``stack_dwords[4]``.  ``arg6`` is read from
# the *argument* slot ``[esp+0x2e8]`` (raw bytes ``8b 94 24 e8 02 00 00``);
# both call paths spill ``params+0xdc`` to a stack **local** at ``[esp+0x28]``
# instead, so the argument is never clobbered.  Slot 730 needs the 4-way switch
# selector and is not in ``L``'s closure, so it is left out rather than guessed.

_SENTINEL4 = (0xFC, 0xFD, 0xFE, 0xFF)
_SENTINEL2 = (0xFE, 0xFF)


def _i8(v: int) -> int:
    v &= 0xFF
    return v - 0x100 if v & 0x80 else v


def vecpack_tail(*, arg6: bytes | bytearray, params: bytes | bytearray,
                 flags: bytes | bytearray, flagsword: int) -> dict[int, int]:
    """Slots 720…729, 731, 732 — ``fcn.1028b8d0``'s own contribution."""
    a6, pa = _Buf(arg6), _Buf(params)
    out = {
        720: _i32(_i16(a6.w(0x0C)) * 10),
        726: _i32(_i16(a6.w(0x0E)) * 10),
        727: _i32(_i16(a6.w(0x10)) * 10),
        728: _i16(pa.w(0x10E)),
        729: _i16(pa.w(0x110)),
        721: -1 if flags[1] in _SENTINEL4 else _i8(flags[1]),
        722: -1 if flags[2] in _SENTINEL2 else _i8(flags[2]),
        723: -1 if flags[3] in _SENTINEL2 else _i8(flags[3]),
        724: -1 if flags[4] in _SENTINEL2 else _i8(flags[4]),
        725: 1 if flags[6] == 1 else 0,
        731: 1 if (flagsword & 0x800) & 0xFFFF else 0,
        732: (_i16(flagsword) & 0x1000) >> 12,
    }
    return out


def read_vector(scene: bytes | bytearray) -> list[int]:
    """The 720 int32 slots the pcode VM is handed (``params[+0x19c]``)."""
    return list(struct.unpack_from("<%di" % VEC_SLOTS, scene, VEC_OFF))


def slot_source(slot: int) -> str:
    """Human-readable provenance of one slot — for decoding real captures."""
    if 0 <= slot < 476:
        i, r = divmod(slot, 68)
        b, k = divmod(r, 34)
        base = "arg6[rec %d bank %d]" % (i, b)
        if k < 6:
            return "%s row+0x30[%d] / i16(arg7.w[0x%02x])" % (base, k, 4 * i + 2 * b)
        if k < 12:
            return "%s row+0x00[%d]" % (base, k - 6)
        if k < 18:
            return "%s row+0x18[%d]" % (base, k - 12)
        if k < 24:
            return "%s row+0x30[%d]" % (base, k - 18)
        if k < 30:
            return "%s row+0x48[%d]" % (base, k - 24)
        return "%s scalar+0x%02x" % (base, (0x7C, 0x80, 0x88, 0x8C)[k - 30])
    for lo, name in ((476, "grpA"), (510, "grpB"), (544, "grpC"), (578, "grpD")):
        if lo <= slot < lo + 34:
            k = slot - lo
            if k < 6:
                return "%s divided[%d]" % (name, k)
            if k < 30:
                return "%s raw[%d]" % (name, k - 6)
            return "%s scalar[%d]" % (name, k - 30)
    if 612 <= slot < 616:
        return "scene header word +0x%02x" % (0x06, 0x0A, 0x08, 0x0C)[slot - 612]
    if 616 <= slot < 691:
        return "arg3[%d] verbatim" % (slot - 616)
    if 691 <= slot < 710:
        return "arg4[%d] verbatim" % (slot - 691)
    if 710 <= slot < 719:
        return "arg5[%d] verbatim" % (slot - 710)
    if slot == 719:
        return "divided scalar (arg6[0x8ac] or arg6[0x3c])"
    return "unwritten"
