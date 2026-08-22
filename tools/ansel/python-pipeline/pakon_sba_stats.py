#!/usr/bin/env python3
"""Port of ``fcn.102b7440`` — the SBA per-frame **statistics-vector packer**.

.. warning::

   **THIS IS THE REDUNDANT SECOND PORT.  It is not the deliverable.**

   ``pakon_orderfpo_vecpack.py`` ports the same function, was written first,
   and additionally covers the ``720…732`` tail that this module does not
   (its ``vecpack_tail``).  **Use that one.**  Two agents ported
   ``fcn.102b7440`` concurrently without seeing each other, because both
   files were untracked — see docs/74 §192.3.

   This module is kept for exactly one reason, and it is a good one: the two
   implementations were written **independently from the same 910
   instructions** and agree **byte-for-byte on all 52 cases**.  That
   cross-check is section ``[5]`` of ``pakon_sba_stats_golden.py`` and is a
   stronger statement than either port can make alone.  Deleting this file
   would delete that evidence, so it stays — labelled, not promoted.

`PakonIMAu.dll` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``, PE base
``0x10000000``.

What this function is
---------------------

`fcn.102b7440` is the tail call of `fcn.102aece0` (`0x102b4c5e`, 10 cdecl
args), and it is the code that actually **writes** the 720-entry ``int32``
statistics vector that lives at ``sba_obj + 0x3c`` — the vector docs/74
§88.6 identified as the p-code VM's ``in[]`` and §90 used to reproduce
``L`` (and hence ``orderFpo.Y``) 12/12 bit-exact.

Provenance of the layout, from the two ends:

* the packer's first destination store is ``[edi - 0x1c]`` with
  ``edi = obj + 0x54 + 4`` (`0x102b7615` / `0x102b766f`), i.e. **obj+0x3c
  is index 0** — the vector origin, derived, not assumed;
* the packer's last destination store is ``[ecx + 0xb78]``
  (`0x102b7d77`) = index **719**, and `fcn.1028b8d0`'s own top level
  writes ``[esi + 0xb7c] … [esi + 0xbac]`` = indices **720 … 732**
  (`0x1028beb5` onwards).  The two ranges abut exactly.

Arguments (cdecl, 10), as `fcn.102aece0` pushes them at
``0x102b4c23 … 0x102b4c5d``:

===  ======================  =========================================
#    caller expression       role here
===  ======================  =========================================
1    ``102aece0`` arg5       ``mode1`` word; ``==1`` selects branch B
2    ``102aece0`` arg4       ``mode2`` word; picks the ``par`` pair
3    ``&var_e84h``           75 ``int32``  -> ``obj+0x9dc``
4    ``&var_2f4h``           19 ``int32``  -> ``obj+0xb08``
5    ``&var_2d0h``            9 ``int32``  -> ``obj+0xb54``
6    ``&var_354h``           the accumulator block (``acc``)
7    ``&var_2a8h_2``         the sample-count table (``cnt``, ``int16``)
8    ``102aece0`` arg7       per-zone enable bytes (``en``)
9    ``102aece0`` arg8       the geometry/param struct (``par``)
10   ``102aece0`` arg10      the SBA object (``obj``) — the output
===  ======================  =========================================

The zone layout the code implies, per zone ``z`` in ``0..6``
(stride ``0x110``, base ``obj+0x3c``, i.e. vector index
``z*68``)::

    +0x000  6 x i32   group-0 mean   = acc[S0 + 4j] / cnt16[2z]
    +0x018  6 x i32   group-0 row 1  = acc[S0 - 0x30 + 4j]
    +0x030  6 x i32   group-0 row 2  = acc[S0 - 0x18 + 4j]
    +0x048  6 x i32   group-0 row 3  = acc[S0 + 4j]
    +0x060  6 x i32   group-0 row 4  = acc[S0 + 0x18 + 4j]
    +0x078  4 x i32   group-0 extras
    +0x088  6 x i32   group-1 mean   = acc[S1 + 4j] / cnt16[2z+1]
    +0x0a0  6 x i32   group-1 row 1
    +0x0b8  6 x i32   group-1 row 2
    +0x0d0  6 x i32   group-1 row 3
    +0x0e8  6 x i32   group-1 row 4
    +0x100  4 x i32   group-1 extras

with ``S0 = 0x30 + z*0x120`` and ``S1 = 0xc0 + z*0x120`` in ``acc``.  A
zone whose enable byte is zero is left untouched (it keeps whatever the
caller pre-initialised — `fcn.102aece0` seeds those slots with
``+10000`` / ``-10000`` min/max sentinels at `0x102af2d0`).

Everything here is transcribed from `af`+`pdf` at the real function
boundary; `pakon_sba_stats_golden.py` is what makes it a tier-1 claim.
"""
from __future__ import annotations

import struct
from typing import List

# --- little machine-integer helpers -----------------------------------


def _i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


def _i16(x: int) -> int:
    x &= 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def idiv32(num: int, den: int) -> int:
    """x86 ``idiv``: signed division truncating toward zero.

    Raises ZeroDivisionError on a zero divisor, exactly as the CPU raises
    #DE — the vendor never guards this, so neither do we.
    """
    if den == 0:
        raise ZeroDivisionError("idiv by zero (#DE)")
    q = abs(num) // abs(den)
    if (num < 0) != (den < 0):
        q = -q
    return _i32(q)


class _Mem:
    """A flat little-endian byte buffer with i32/i16 accessors."""

    __slots__ = ("b",)

    def __init__(self, data: bytes | bytearray, size: int | None = None):
        buf = bytearray(data)
        if size is not None and len(buf) < size:
            buf.extend(b"\x00" * (size - len(buf)))
        self.b = buf

    def i32(self, off: int) -> int:
        return struct.unpack_from("<i", self.b, off)[0]

    def u16(self, off: int) -> int:
        return struct.unpack_from("<H", self.b, off)[0]

    def i16(self, off: int) -> int:
        return struct.unpack_from("<h", self.b, off)[0]

    def u8(self, off: int) -> int:
        return self.b[off]

    def set_i32(self, off: int, v: int) -> None:
        struct.pack_into("<i", self.b, off, _i32(v))

    def set_u16(self, off: int, v: int) -> None:
        struct.pack_into("<H", self.b, off, v & 0xFFFF)


# --- the packer -------------------------------------------------------

ZONE_STRIDE_OBJ = 0x110
ZONE_STRIDE_ACC = 0x120
VECTOR_BASE = 0x3C
VECTOR_LAST_DWORD = 0xB78  # index 719, the packer's final store


def _pack_block(obj: _Mem, acc: _Mem, dst_row1: int, src: int, den: int) -> None:
    """The six-iteration inner loop that appears fourteen-plus times.

    ``dst_row1`` is the ``lea``'d destination (the assembly's ``ebx``/
    ``edi`` before the first ``add …, 4``); rows land at
    ``dst_row1 - 0x18`` (the mean) then ``dst_row1`` + 0/0x18/0x30/0x48.
    ``src`` is the assembly's source pointer at the top of iteration 0.
    """
    mean = dst_row1 - 0x18
    for j in range(6):
        p = src + 4 * j
        d = dst_row1 + 4 * j
        obj.set_i32(mean + 4 * j, idiv32(acc.i32(p), den))
        obj.set_i32(d + 0x00, acc.i32(p - 0x30))
        obj.set_i32(d + 0x18, acc.i32(p - 0x18))
        obj.set_i32(d + 0x30, acc.i32(p))
        obj.set_i32(d + 0x48, acc.i32(p + 0x18))


def _extras(obj: _Mem, acc: _Mem, dst: int, src: int) -> None:
    """The four trailing stores: ``+0/+8/+4/+0xc`` from ``src``."""
    obj.set_i32(dst + 0x00, acc.i32(src + 0x00))
    obj.set_i32(dst + 0x08, acc.i32(src + 0x0C))
    obj.set_i32(dst + 0x04, acc.i32(src + 0x04))
    obj.set_i32(dst + 0x0C, acc.i32(src + 0x10))


def sba_stats_pack(
    obj: bytearray,
    *,
    mode1: int,
    mode2: int,
    blk75: List[int],
    blk19: List[int],
    blk9: List[int],
    acc: bytes | bytearray,
    cnt: bytes | bytearray,
    en: bytes | bytearray,
    par: bytes | bytearray,
) -> bytearray:
    """Run `fcn.102b7440`.  ``obj`` is modified in place and returned."""
    o = _Mem(obj)
    a = _Mem(acc)
    c = _Mem(cnt)
    e = _Mem(en)
    p = _Mem(par)

    # prologue reads, 0x102b7443..0x102b747c
    var_10 = o.u16(0x06)  # zero-extended
    var_34 = o.u16(0x08)  # zero-extended
    var_38 = o.u16(0x0C)
    var_3c = o.u16(0x0A)
    var_40 = o.u16(0x16)

    branch_b = (mode1 & 0xFFFF) == 1
    var_2c = None

    if not branch_b:
        # --- 0x102b7486: the three straight block copies ---------------
        for i in range(75):
            o.set_i32(0x9DC + 4 * i, blk75[i])
        for i in range(19):
            o.set_i32(0xB08 + 4 * i, blk19[i])
        for i in range(9):
            o.set_i32(0xB54 + 4 * i, blk9[i])

        # --- 0x102b751a: the "long side" test --------------------------
        if _i16(var_10) > p.i16(0x0E):
            var_2c = idiv32(a.i32(0x8AC), _i16(var_34))
        else:
            var_2c = idiv32(a.i32(0x3C), c.i16(0x00))
            # 0x102b7542..0x102b75e6: mirror acc[0x00..0x44] -> acc[0x7e0..]
            for k in range(18):
                a.set_i32(0x7E0 + 4 * k, a.i32(4 * k))
            # 0x102b75e7: seed the four extra counts
            c.set_u16(0x1C, 0x360)
            c.set_u16(0x1E, 0x360)
            c.set_u16(0x20, c.u16(0x0A))
            c.set_u16(0x22, c.u16(0x0A))

    # --- the seven-zone loop, 0x102b7630 / 0x102b7dd0 -------------------
    for z in range(7):
        dz = z * ZONE_STRIDE_OBJ
        sz = z * ZONE_STRIDE_ACC
        if e.u8(2 * z) != 0:
            _pack_block(o, a, 0x54 + dz, 0x30 + sz, c.i16(4 * z))
            _extras(o, a, 0xB4 + dz, 0x7C + sz)
        if e.u8(2 * z + 1) != 0:
            _pack_block(o, a, 0xDC + dz, 0xC0 + sz, c.i16(4 * z + 2))
            _extras(o, a, 0x13C + dz, 0x10C + sz)

    # --- 0x102b77b4 / 0x102b7f38: the four whole-frame blocks -----------
    if e.u16(0x0E) != 0:
        long_side = _i16(var_10) > p.i16(0x0E)
        if branch_b:
            if long_side:
                _pack_block(o, a, 0x7C4, 0x810, c.i16(0x1C))
                _extras(o, a, 0x824, 0x85C)
                if c.u16(0x20) != 0:
                    _pack_block(o, a, 0x8D4, 0x930, c.i16(0x20))
                    _extras(o, a, 0x934, 0x97C)
                    # 0x102b8063: this path returns early
                    o.set_i32(0x9CC, _i16(var_10))
                    obj[:] = o.b
                    return obj
                _pack_block(o, a, 0x8D4, 0x300, c.i16(0x0A))
            else:
                _pack_block(o, a, 0x7C4, 0x030, c.i16(0x00))
                _extras(o, a, 0x824, 0x07C)
                _pack_block(o, a, 0x8D4, 0x300, c.i16(0x0A))
            _extras(o, a, 0x934, 0x34C)
        else:
            if long_side:
                _pack_block(o, a, 0x7C4, 0x810, c.i16(0x1C))
                _extras(o, a, 0x824, 0x85C)
                _pack_block(o, a, 0x84C, 0x8A0, c.i16(0x1E))
                _extras(o, a, 0x8AC, 0x8EC)
                if c.u16(0x20) != 0:
                    _pack_block(o, a, 0x8D4, 0x930, c.i16(0x20))
                    _extras(o, a, 0x934, 0x97C)
                    _pack_block(o, a, 0x95C, 0x9C0, c.i16(0x22))
                    _extras(o, a, 0x9BC, 0xA0C)
                else:
                    _pack_block(o, a, 0x8D4, 0x300, c.i16(0x0A))
                    _extras(o, a, 0x934, 0x34C)
                    _pack_block(o, a, 0x95C, 0x300, c.i16(0x0A))
                    _extras(o, a, 0x9BC, 0x34C)
            else:
                _pack_block(o, a, 0x7C4, 0x030, c.i16(0x00))
                _extras(o, a, 0x824, 0x07C)
                _pack_block(o, a, 0x8D4, 0x300, c.i16(0x0A))
                _extras(o, a, 0x934, 0x34C)
                _pack_block(o, a, 0x84C, 0x030, c.i16(0x00))
                _extras(o, a, 0x8AC, 0x07C)
                _pack_block(o, a, 0x95C, 0x300, c.i16(0x0A))
                _extras(o, a, 0x9BC, 0x34C)

    if branch_b:
        # 0x102b81b4
        o.set_i32(0x9CC, _i16(var_10))
        obj[:] = o.b
        return obj

    # --- 0x102b7ccc: the four scalar echoes -----------------------------
    o.set_i32(0x9D4, _i16(var_34))
    o.set_i32(0x9D8, _i16(var_38))
    o.set_i32(0x9CC, _i16(var_10))
    o.set_i32(0x9D0, _i16(var_3c))

    # --- 0x102b7cf1: obj+0x18, the aim word -----------------------------
    if (mode2 & 0xFFFF) == 1:
        d0, d1 = p.i16(0x00), p.i16(0x02)
    else:
        d0, d1 = p.i16(0x04), p.i16(0x06)

    if d0 == 0:
        o.set_u16(0x18, 1000)
    else:
        v = _i16(var_40)
        if v <= d0:
            o.set_u16(0x18, 0)
        else:
            num = _i32((v - d0) * 1000)
            half = idiv32(d1, 2)  # trunc(d1/2), via cdq/sub/sar
            if (num < 0) == (d1 < 0):
                num2 = _i32(num + half)
            else:
                num2 = _i32(num - half)
            o.set_u16(0x18, idiv32(num2, d1) & 0xFFFF)

    # --- 0x102b7d5c: two zero-guards on acc, then the return value ------
    if a.i32(0x24) == 0:
        a.set_i32(0x24, 1)
    if a.i32(0x0C) == 0:
        a.set_i32(0x0C, 1)
    o.set_i32(0xB78, var_2c)

    obj[:] = o.b
    if isinstance(acc, bytearray):
        acc[:] = a.b
    if isinstance(cnt, bytearray):
        cnt[:] = c.b
    return obj
