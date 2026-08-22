#!/usr/bin/env python3
"""Golden FLESH **detector** blocks vs the real PakonIMAu.dll (Unicorn).

`pakon_flesh_golden.py` proved the *adjust arithmetic* — the tail of
`fcn.10270280` that turns `(stat, nsum, fleshCount, area, exposure)` into
`docs/74` §178's per-frame `Delta`.  This harness proves the four blocks
*upstream* of it that are reachable with the shipped DPI, by executing the
real DLL bytes and diffing every output byte-for-byte:

1. **The analysis border** — `0x102706fe … 0x10270763`, both insets.
2. **The V1 LST / skin-probability loop** — `fcn.102a1500`'s per-row body,
   `0x102a1787 … 0x102a192a`: `L = R+G+B`, `S = R-B`, `T = 2G-R-B`, three
   clamped bin indices, and the separable product of the three shipped
   32-bin conditional-probability tables.
3. **The 0/10/20/255 clamp loop** — `0x102711a2 … 0x1027121b`, including
   the "any real flesh probability" flag byte that gates the reduction.
4. **The reduction loop** — `0x102712ac … 0x102714c7`, the whole 2-D walk:
   loop bounds, the threshold compare, the in-place binarisation to 0/255,
   the running max, and the `stat` / `nsum` / `fleshCount` accumulators.

Nothing in the DLL is patched.  The only calls inside these ranges are the
real two- and three-instruction image accessors (`0x104d4520` ->
`obj->[4]->[0x14]`, `0x104d4530` -> `obj->[4]->[0x18]`, `0x104d48f0` ->
`obj->[0x1c]`) and `_ftol` (`0x104ffe44`); all of them run for real,
satisfied by building the real object graph in guest memory.  The x87
control word is set to `0x027f` (53-bit precision), matching the MSVC7 CRT
startup, for the same reason as in `pakon_flesh_golden.py`.

What this proves, and what it does not
--------------------------------------

Proves, bit-exact: everything listed above, including that the `S`/`T`
axes are round-tripped through **float32** while `L` is not, that each axis
divide is by the **float32** narrowing of its scale, the double truncation
per axis, the `< 0 -> bin 0` short circuit that skips the divide, the
`> 31 -> 31` clamp, the multiply order `t * s * l`, the `< 0.001 -> 0.0`
floor, the asymmetric row bounds of the reduction, and the wrapping
32-bit `imul` in the statistic.

Does **not** prove, and this port does not have:

* the analysis-image construction (`0x104e8360`, `0x1014cc20`,
  `0x104e7880`) and the two 1-D LUT pre-passes at `0x10270920` /
  `0x10270b10`.
* which shipped conditional-probability table the vendor's loader puts in
  which of `P+0x38 / +0x3c / +0x40` (`fl.FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED`).
* the `useAdvanced != 0` and `oneDTable == 0` branches — both unreachable
  with the shipped DPI, asserted here rather than ported.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \\
    tools/ansel/python-pipeline/pakon_flesh_detector_golden.py [PakonIMAu.dll]``
"""
from __future__ import annotations

import hashlib
import struct
import sys
from dataclasses import replace
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_ECX,
    UC_X86_REG_EDX,
    UC_X86_REG_ESP,
    UC_X86_REG_FPCW,
)

import pakon_flesh as fl

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x200000
DATA_ADDR = 0x20000000
DATA_SIZE = 0x400000
FPCW_WIN32 = 0x027F

DEFAULT_DLL = (
    Path(__file__).resolve().parents[2] / "re" / "live_hooks" / "wine_host" / "PakonIMAu.dll"
)


# --- PE loading -------------------------------------------------------------


def _align_up(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


def load_pe_into_uc(uc: Uc, pe: bytes) -> None:
    e_lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
    num_sec = struct.unpack_from("<H", pe, e_lfanew + 6)[0]
    opt_size = struct.unpack_from("<H", pe, e_lfanew + 20)[0]
    opt = e_lfanew + 24
    size_image = struct.unpack_from("<I", pe, opt + 56)[0]
    uc.mem_map(IMAGE_BASE, _align_up(size_image))
    uc.mem_write(IMAGE_BASE, pe[:0x1000])
    sec_off = opt + opt_size
    for i in range(num_sec):
        o = sec_off + i * 40
        vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
        if rsz == 0 or raddr == 0:
            continue
        data = pe[raddr : raddr + rsz]
        if len(data) < vsz:
            data = data + b"\x00" * (vsz - len(data))
        uc.mem_write(IMAGE_BASE + va, data[: max(vsz, rsz)])


class Guest:
    """A freshly-loaded guest image with a bump allocator."""

    def __init__(self, dll: bytes) -> None:
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        load_pe_into_uc(self.uc, dll)
        self.uc.mem_map(STACK_ADDR, STACK_SIZE)
        self.uc.mem_map(DATA_ADDR, DATA_SIZE)
        self.uc.reg_write(UC_X86_REG_FPCW, FPCW_WIN32)
        self._cur = DATA_ADDR + 0x1000

    def alloc(self, n: int) -> int:
        a = self._cur
        self._cur = (self._cur + n + 15) & ~15
        if self._cur >= DATA_ADDR + DATA_SIZE:
            raise MemoryError("guest heap exhausted")
        return a

    def blob(self, data: bytes) -> int:
        a = self.alloc(len(data))
        self.uc.mem_write(a, data)
        return a

    def i16_rows(self, rows) -> tuple[int, list[int]]:
        """A plane-data block: ``[+0x18]`` -> row-pointer array."""
        data = self.alloc(0x40)
        ptrs = [self.blob(struct.pack("<%dh" % len(r), *r)) for r in rows]
        arr = self.blob(struct.pack("<%dI" % len(ptrs), *ptrs))
        self.uc.mem_write(data + 0x18, struct.pack("<I", arr))
        return data, ptrs

    def image(self, planes, width: int, height: int) -> int:
        """An ``object2``: ``[+0x14]`` rows, ``[+0x18]`` cols, ``[+0x1c]``
        plane count, ``[+0x20]`` -> plane array (stride 8, data at ``+4``)."""
        img = self.alloc(0x80)
        arr = self.alloc(8 * len(planes))
        for i, pl in enumerate(planes):
            d, _ = self.i16_rows(pl)
            self.uc.mem_write(arr + i * 8 + 4, struct.pack("<I", d))
        self.uc.mem_write(img + 0x14, struct.pack("<III", height, width, len(planes)))
        self.uc.mem_write(img + 0x20, struct.pack("<I", arr))
        return img

    def run(self, start: int, stop: int) -> None:
        self.uc.hook_add(
            UC_HOOK_CODE,
            lambda u, a, s, x: u.emu_stop() if a == stop else None,
            begin=stop,
            end=stop + 1,
        )
        try:
            self.uc.emu_start(start, 0, timeout=120_000_000)
        except UcError as e:  # pragma: no cover - diagnostics
            raise RuntimeError(f"unicorn @ {start:#x}: {e}") from e


# --- 1. the analysis border -------------------------------------------------


def run_dll_border(dll: bytes, params: fl.FleshParams, width: int, height: int) -> tuple[int, int]:
    """``0x102706fe … 0x10270763``.  Returns ``(b_inner, b_outer)``."""
    g = Guest(dll)
    p_addr = g.blob(bytes(params.to_bytes()))
    dims = g.alloc(0x40)
    g.uc.mem_write(dims + 0x14, struct.pack("<ii", int(height), int(width)))
    esp = STACK_ADDR + 0x100000
    g.uc.reg_write(UC_X86_REG_ESP, esp)
    g.uc.mem_write(esp + 0x58, struct.pack("<I", dims))  # object at esp+0x54, ->[4]
    g.uc.mem_write(esp + 0x1C88, struct.pack("<I", p_addr))
    g.uc.reg_write(UC_X86_REG_EDX, 0)  # edi is the zero the two `cmp`s use
    from unicorn.x86_const import UC_X86_REG_EDI

    g.uc.reg_write(UC_X86_REG_EDI, 0)
    g.run(fl.FLESH_BORDER_ENTRY, fl.FLESH_BORDER_EXIT)
    b_inner = struct.unpack("<i", g.uc.mem_read(esp + 0x64, 4))[0]
    b_outer = struct.unpack("<i", g.uc.mem_read(esp + 0xA0, 4))[0]
    return b_inner, b_outer


# --- 2. the LST / probability loop -----------------------------------------


def run_dll_lst_row(
    dll: bytes,
    params: fl.FleshParams,
    tables: fl.FleshCondProbTables,
    pixels,
) -> tuple[list[float], list[tuple[int, int, int]]]:
    """``0x102a1787 … 0x102a192a`` on one row.

    Returns the float32 probability row and, from a second run with
    ``oneDTable`` forced to 0, the ``(l, s, t)`` bin indices — which is the
    only way the DLL exposes them.
    """
    n = len(pixels)

    def one(oned: int):
        g = Guest(dll)
        pr = replace(params, one_d_table=oned)
        p_addr = g.blob(bytes(pr.to_bytes()))
        tl = g.blob(struct.pack("<%dd" % len(tables.l), *tables.l))
        ts = g.blob(struct.pack("<%dd" % len(tables.s), *tables.s))
        tt = g.blob(struct.pack("<%dd" % len(tables.t), *tables.t))
        g.uc.mem_write(p_addr + 0x38, struct.pack("<III", tl, ts, tt))

        row_a = g.blob(struct.pack("<%dh" % n, *[q[0] for q in pixels]))
        row_b = g.blob(struct.pack("<%dh" % n, *[q[1] for q in pixels]))
        row_c = g.blob(struct.pack("<%dh" % n, *[q[2] for q in pixels]))
        out_f = g.blob(b"\xcd" * (4 * n))
        out_l = g.blob(b"\xcd" * (2 * n))
        out_s = g.blob(b"\xcd" * (2 * n))
        out_t = g.blob(b"\xcd" * (2 * n))

        ebp = STACK_ADDR + 0x100000
        g.uc.reg_write(UC_X86_REG_ESP, ebp - 0x2000)
        g.uc.reg_write(UC_X86_REG_EBP, ebp)

        def w(off: int, fmt: str, val) -> None:
            g.uc.mem_write((ebp + off) & 0xFFFFFFFF, struct.pack(fmt, val))

        w(0x1C, "<I", p_addr)  # [ebp+0x1c] = the parameter struct
        w(0x08, "<I", out_l)  # int16 out rows (oneDTable == 0 only)
        w(-0x14, "<I", out_s)
        w(-0x4C, "<I", out_t)
        w(-0xD4, "<i", pr.loff)  # the three fild'd offsets
        w(-0x9C, "<i", pr.soff)
        w(-0xB8, "<i", pr.toff)
        w(-0xC4, "<f", pr.lscale)  # the three float32-narrowed scales
        w(-0xA8, "<f", pr.sscale)
        w(-0x94, "<f", pr.tscale)
        g.uc.mem_write((ebp - 0x15) & 0xFFFFFFFF, bytes([1 if pr.st_only else 0]))
        w(-0x7C, "<I", out_f)  # the float probability row
        w(-0x68, "<i", n)  # the column count
        w(-0x48, "<i", 0)  # x

        g.uc.reg_write(UC_X86_REG_EAX, row_b)  # plane1 is the base pointer
        g.uc.reg_write(UC_X86_REG_ECX, row_a)  # plane0
        g.uc.reg_write(UC_X86_REG_EDX, row_c)  # plane2
        g.run(fl.FLESH_LST_LOOP_ENTRY, fl.FLESH_LST_LOOP_EXIT)
        if oned:
            return list(struct.unpack("<%df" % n, g.uc.mem_read(out_f, 4 * n)))
        return list(
            zip(
                struct.unpack("<%dh" % n, g.uc.mem_read(out_l, 2 * n)),
                struct.unpack("<%dh" % n, g.uc.mem_read(out_s, 2 * n)),
                struct.unpack("<%dh" % n, g.uc.mem_read(out_t, 2 * n)),
            )
        )

    return one(1), one(0)


# --- 3. the clamp loop ------------------------------------------------------


def run_dll_clamp(dll: bytes, values) -> tuple[list, bool]:
    """``0x102711a2 … 0x1027121b`` — the V1 clamp of the probability plane.

    Not a per-row loop: it walks ``rows[0]`` of both images linearly for
    ``0x104d2e90`` = ``obj->[4]->[0x10] * obj->[4]->[0x14]`` samples, i.e.
    the whole plane as one flat buffer.
    """
    g = Guest(dll)
    n = len(values)

    def flat(vals):
        data = g.alloc(0x40)
        buf = g.blob(struct.pack("<%dh" % len(vals), *vals))
        arr = g.blob(struct.pack("<I", buf))
        g.uc.mem_write(data + 0x18, struct.pack("<I", arr))
        return data, buf

    src, _ = flat(values)
    dst, dst_buf = flat([0] * n)
    # The count accessor 0x104d2e90 reads [esp+0x28]->[4], and [esp+0x2c] is
    # that same slot -- i.e. the object's data block IS the source plane.
    g.uc.mem_write(src + 0x10, struct.pack("<ii", n, 1))  # [0x10]*[0x14] = n
    esp = STACK_ADDR + 0x100000
    g.uc.reg_write(UC_X86_REG_ESP, esp)
    g.uc.mem_write(esp + 0x50, struct.pack("<I", dst))  # dest plane data
    g.uc.mem_write(esp + 0x2C, struct.pack("<I", src))  # source plane data
    g.uc.mem_write(esp + 0x17, b"\x00")  # the "real flesh probability" flag
    g.run(fl.FLESH_CLAMP_LOOP_ENTRY, fl.FLESH_CLAMP_LOOP_EXIT)
    out = list(struct.unpack("<%dh" % n, g.uc.mem_read(dst_buf, 2 * n)))
    flag = g.uc.mem_read(esp + 0x17, 1)[0] != 0
    return out, flag


# --- 4. the reduction loop --------------------------------------------------


def run_dll_reduce(
    dll: bytes,
    params: fl.FleshParams,
    planes,
    weight,
    prob,
    threshold: float,
    b_inner: int,
    b_outer: int,
) -> dict:
    """``0x102712ac … 0x102714c7``, the whole 2-D reduction."""
    g = Guest(dll)
    height = len(prob)
    width = len(prob[0])
    p_addr = g.blob(bytes(params.to_bytes()))
    res = g.alloc(0x40)
    g.uc.mem_write(res + 0x28, struct.pack("<d", float(threshold)))
    img = g.image(planes, width, height)
    wdata, _ = g.i16_rows(weight)
    pdata, prob_rows = g.i16_rows(prob)

    esp = STACK_ADDR + 0x100000
    g.uc.reg_write(UC_X86_REG_ESP, esp)

    def w(off: int, fmt: str, val) -> None:
        g.uc.mem_write(esp + off, struct.pack(fmt, val))

    w(0x40, "<I", img)  # the 3-plane colour image (object at esp+0x3c)
    w(0x70, "<I", wdata)  # the weight plane's data block
    w(0x50, "<I", pdata)  # the probability plane's data block
    w(0xA0, "<i", int(b_outer))
    w(0x64, "<i", int(b_inner))
    w(0x24, "<i", 0)  # fleshCount
    w(0x1C, "<i", -1)  # running max probability
    w(0x78, "<d", 0.0)  # nsum
    w(0x94, "<d", 0.0)  # stat
    w(0x1C88, "<I", p_addr)
    w(0x1CB0, "<I", res)

    g.run(fl.FLESH_REDUCE_ENTRY, fl.FLESH_REDUCE_EXIT)
    return {
        "count": struct.unpack("<i", g.uc.mem_read(esp + 0x24, 4))[0],
        "max_prob": struct.unpack("<i", g.uc.mem_read(esp + 0x1C, 4))[0],
        "nsum": struct.unpack("<d", g.uc.mem_read(esp + 0x78, 8))[0],
        "stat": struct.unpack("<d", g.uc.mem_read(esp + 0x94, 8))[0],
        "prob": [
            list(struct.unpack("<%dh" % width, g.uc.mem_read(r, 2 * width))) for r in prob_rows
        ],
    }


# --- a deterministic PRNG so every run is reproducible ----------------------


class Rng:
    def __init__(self, seed: int) -> None:
        self.s = seed & 0x7FFFFFFF

    def next(self) -> int:
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s

    def between(self, lo: int, hi: int) -> int:
        return lo + self.next() % (hi - lo)


#: Corners, saturation, and the exact bin edges of the shipped DPI.
EDGE_PIXELS = (
    (0, 0, 0),
    (1, 1, 1),
    (-1, -1, -1),
    (2000, 1900, 1700),
    (542, 542, 542),
    (1626, 0, 0),
    (32767, 32767, 32767),
    (-32768, -32768, -32768),
    (32767, -32768, 32767),
    (-32768, 32767, -32768),
    (1000, 1200, 900),
    (700, 900, 600),
    (900, 800, 700),
)


def skin_pixels(rng: "Rng", n: int) -> list:
    """Pixels around the locus the three shipped tables actually peak at.

    The peaks are bins l=18, s=19, t=14, i.e. ``L ~= 1626 + 18*189 = 5028``,
    ``S ~= -85 + 19*17 = 238``, ``T ~= -600 + 14*30 = -180``, which solves to
    roughly ``(R, G, B) = (1825, 1616, 1587)``.  Sweeping a wide box around
    that is what makes the probability non-zero often enough for a table
    permutation to be detectable.
    """
    out = []
    for _ in range(n):
        r = 1825 + rng.between(-900, 900)
        g = 1616 + rng.between(-900, 900)
        b = 1587 + rng.between(-900, 900)
        out.append((r, g, b))
    return out


def rgb_from_lst(lv: int, sv: int, tv: int):
    """Invert ``L = R+G+B``, ``S = R-B``, ``T = 2G-R-B`` over the integers.

    Returns ``None`` when the target is not reachable with integer pixels.
    """
    if (lv + tv) % 3:
        return None
    g = (lv + tv) // 3
    rb = lv - g
    if (rb + sv) % 2:
        return None
    return ((rb + sv) // 2, g, (rb - sv) // 2)


def bin_edge_pixels(params: fl.FleshParams) -> list:
    """Pixels sitting exactly one below each bin boundary on each axis.

    Without these a `+/- 1` error in `L`, `S` or `T` is invisible: the bins
    are 189 / 17 / 30 wide, so a random sweep almost never straddles one.
    """
    out = []
    for k in range(1, fl.COND_PROB_BINS):
        for lv, sv, tv in (
            (params.loff + int(params.lscale) * k - 1, 238, -180),
            (5028, params.soff + int(params.sscale) * k - 1, -180),
            (5028, 238, params.toff + int(params.tscale) * k - 1),
        ):
            for d in range(6):
                got = rgb_from_lst(lv, sv + (d % 2), tv + d // 2)
                if got is not None:
                    out.append(got)
                    break
    return out


def _same(a: float, b: float) -> bool:
    return struct.pack("<d", a) == struct.pack("<d", b)


def _same32(a: float, b: float) -> bool:
    return struct.pack("<f", a) == struct.pack("<f", b)


# --- the harness ------------------------------------------------------------


def check_border(dll: bytes, base: fl.FleshParams) -> int:
    print("\n  [1] analysis border  0x102706fe … 0x10270763")
    fails = 0
    checked = 0
    variants = {
        "shipped clip=0.30": base,
        "clip=0.10": replace(base, clip_amount=0.10),
        "clip=0.00": replace(base, clip_amount=0.0),
        "clip=0.55": replace(base, clip_amount=0.55),
        "clip=-0.20": replace(base, clip_amount=-0.20),
    }
    rng = Rng(0x2468ACE)
    dims = [(1, 1), (2, 3), (7, 7), (13, 5), (256, 171), (1024, 683), (2000, 1333)]
    dims += [(rng.between(1, 3000), rng.between(1, 3000)) for _ in range(30)]
    for name, params in variants.items():
        for w, h in dims:
            bi, bo = run_dll_border(dll, params, w, h)
            hi = fl.flesh_border(w, params.clip_amount)
            ho = fl.flesh_border(h, params.clip_amount)
            checked += 1
            if (bi, bo) != (hi, ho):
                fails += 1
                if fails <= 6:
                    print(f"      FAIL [{name}] {w}x{h}: dll=({bi},{bo}) host=({hi},{ho})")
    print(f"      {checked} cases: {'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}")
    print("      (b_inner comes from 0x104d4530 = the WIDTH, b_outer from 0x104d4520 = "
          "the HEIGHT)")
    return fails


def check_lst(dll: bytes, base: fl.FleshParams, tabs: fl.FleshCondProbTables) -> int:
    print("\n  [2] LST + skin probability  0x102a1787 … 0x102a192a")
    rng = Rng(0x13579BDF)
    pixels = list(EDGE_PIXELS) + bin_edge_pixels(base) + skin_pixels(rng, 400) + [
        (rng.between(-32768, 32768), rng.between(-32768, 32768), rng.between(-32768, 32768))
        for _ in range(200)
    ]

    fails = 0
    checked = 0
    nonzero = 0
    variants = {
        "shipped": base,
        "stOnly=1": replace(base, st_only=1),
        "loff=0": replace(base, loff=0),
        "scales 1/1/1": replace(base, lscale=1.0, sscale=1.0, tscale=1.0),
        "scales 7.3/0.37/1e5": replace(base, lscale=7.3, sscale=0.37, tscale=1.0e5),
        "offsets swapped": replace(base, loff=-600, soff=1626, toff=-85),
    }
    for name, params in variants.items():
        probs, idxs = run_dll_lst_row(dll, params, tabs, pixels)
        for i, (r, g_, b) in enumerate(pixels):
            checked += 1
            host_idx = fl.flesh_lst_indices(r, g_, b, params)
            host_p = fl.flesh_skin_probability(r, g_, b, params, tabs)
            if probs[i]:
                nonzero += 1
            if tuple(idxs[i]) != host_idx or not _same32(probs[i], host_p):
                fails += 1
                if fails <= 8:
                    print(
                        f"      FAIL [{name}] rgb={(r, g_, b)}\n"
                        f"           dll  idx={tuple(idxs[i])} p={probs[i]!r}\n"
                        f"           host idx={host_idx} p={host_p!r}"
                    )
    print(
        f"      {checked} pixels over {len(variants)} parameter variants "
        f"({nonzero} with non-zero probability): "
        f"{'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}"
    )
    return fails


def check_clamp(dll: bytes) -> int:
    print("\n  [3] 0/10/20/255 clamp map  0x102711a2 … 0x1027121b")
    rows = [
        [0, 1, 9, 10, 11, 19, 20, 21, 254, 255, 256, 300, -1, -100, 32767, -32768],
        [0] * 16,
        [10] * 16,
        [20] * 16,
        [21] + [0] * 15,
    ]
    fails = 0
    for row in rows:
        out, flag = run_dll_clamp(dll, row)
        host_rows, hflag = fl.flesh_clamp_plane([row])
        host = host_rows[0]
        if out != host or flag != hflag:
            fails += 1
            print(f"      FAIL {row}\n           dll ={out} flag={flag}\n"
                  f"           host={host} flag={hflag}")
    print(f"      {len(rows)} rows: {'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}")
    return fails


def _reduce_host(planes, weight, prob, threshold, b_inner, b_outer):
    height = len(prob)
    width = len(prob[0])
    hp = [row[:] for row in prob]
    stat, nsum, count, maxp = fl.flesh_accumulate(
        hp,
        weight,
        planes,
        threshold,
        rows=fl.flesh_loop_rows(height, b_outer),
        cols=fl.flesh_loop_cols(width, b_inner),
    )
    return {"count": count, "max_prob": maxp, "nsum": nsum, "stat": stat, "prob": hp}


def check_reduce(dll: bytes, base: fl.FleshParams) -> tuple[int, list]:
    print("\n  [4] reduction loop  0x102712ac … 0x102714c7")
    rng = Rng(0x0BADC0DE)
    cases = []
    for w, h, bi, bo, th in (
        (12, 9, 2, 1, 40.0),
        (12, 9, 0, 1, 40.0),
        (33, 21, 4, 3, 0.0),
        (33, 21, 4, 3, 255.0),
        (33, 21, 4, 3, -1.0),
        (8, 8, 3, 3, 128.0),
        (64, 48, 9, 6, 10.5),
    ):
        planes = [
            [[rng.between(-3000, 3000) for _ in range(w)] for _ in range(h)] for _ in range(3)
        ]
        weight = [[rng.between(-40, 500) for _ in range(w)] for _ in range(h)]
        prob = [[rng.between(-5, 300) for _ in range(w)] for _ in range(h)]
        cases.append((planes, weight, prob, th, bi, bo))
    # one case built to overflow the 32-bit imul in the statistic
    w, h = 10, 8
    planes = [[[32000] * w for _ in range(h)] for _ in range(3)]
    weight = [[32000] * w for _ in range(h)]
    prob = [[100] * w for _ in range(h)]
    cases.append((planes, weight, prob, 10.0, 1, 1))

    fails = 0
    for planes, weight, prob, th, bi, bo in cases:
        got = run_dll_reduce(dll, base, planes, weight, prob, th, bi, bo)
        host = _reduce_host(planes, weight, prob, th, bi, bo)
        ok = (
            got["count"] == host["count"]
            and got["max_prob"] == host["max_prob"]
            and _same(got["nsum"], host["nsum"])
            and _same(got["stat"], host["stat"])
            and got["prob"] == host["prob"]
        )
        if not ok:
            fails += 1
            print(
                f"      FAIL {len(prob[0])}x{len(prob)} b=({bi},{bo}) th={th}\n"
                f"           dll  {{k: got[k] for k in ('count','max_prob','nsum','stat')}}\n"
                f"           dll ={ {k: got[k] for k in ('count', 'max_prob', 'nsum', 'stat')} }\n"
                f"           host={ {k: host[k] for k in ('count', 'max_prob', 'nsum', 'stat')} }\n"
                f"           plane match={got['prob'] == host['prob']}"
            )
    print(f"      {len(cases)} cases: {'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}")
    print("      NOTE, reproduced not corrected: the first row the vendor visits is")
    print("      `height - b_outer`, so with b_outer == 0 it indexes one row PAST the")
    print("      end (0x102712ac..0x102712c4 has no upper guard).  Emulating that case")
    print("      faults on an unmapped read, so it is excluded here; flesh_border keeps")
    print("      b_outer >= 1 for any height >= 7 at the shipped clipAmount = 0.30.")
    return fails, cases


# --- deliberate port bugs, the house standard -------------------------------


def check_teeth(dll: bytes, base: fl.FleshParams, tabs: fl.FleshCondProbTables, cases) -> int:
    print("\n  [5] deliberate port bugs — the harness must catch each one")
    rng = Rng(0x5EED1234)
    pixels = list(EDGE_PIXELS) + bin_edge_pixels(base) + skin_pixels(rng, 300)
    dll_probs, dll_idx = run_dll_lst_row(dll, base, tabs, pixels)
    # A second parameter point built so that the float32 narrowing of the
    # scale is decisive: 100.0000000001 narrows to exactly 100.0, so any
    # (value - off) that is an exact multiple of 100 lands on an integer
    # quotient under the narrowed divisor and just below it under the double.
    odd = replace(
        base, loff=0, soff=0, toff=0,
        lscale=100.0000000001, sscale=100.0000000001, tscale=100.0000000001,
    )
    odd_pixels = []
    for a in range(3, 32, 3):
        for b in range(0, 20, 2):
            got = rgb_from_lst(100 * a, 100 * b, 0)
            if got is not None:
                odd_pixels.append(got)
    odd_probs, odd_idx = run_dll_lst_row(dll, odd, tabs, odd_pixels)
    planes, weight, prob, th, bi, bo = cases[0]
    dll_red = run_dll_reduce(dll, base, planes, weight, prob, th, bi, bo)

    nz = sum(1 for p in dll_probs if p)
    print(f"      (probe set: {len(pixels)} pixels, {nz} with non-zero probability)")

    fails = 0

    def score(params, ref_idx, ref_probs, pxs=None) -> int:
        pxs = pixels if pxs is None else pxs
        return sum(
            1
            for i, (r, g_, b) in enumerate(pxs)
            if tuple(ref_idx[i]) != fl.flesh_lst_indices(r, g_, b, params)
            or not _same32(ref_probs[i], fl.flesh_skin_probability(r, g_, b, params, tabs))
        )

    def probe(label: str, caught: int) -> None:
        nonlocal fails
        print(f"      '{label}': caught on {caught}/{len(pixels)} pixels")
        if not caught:
            print("      FAILED: a deliberate port bug was invisible")
            fails += 1

    def _ftol_round(x: float) -> int:
        if x != x or x in (float("inf"), float("-inf")):
            return 0
        v = int(round(x))
        return ((v + 0x80000000) & 0xFFFFFFFF) - 0x80000000

    real = fl._ftol32
    fl._ftol32 = _ftol_round
    try:
        caught = score(base, dll_idx, dll_probs)
    finally:
        fl._ftol32 = real
    probe("_ftol32 -> round-to-nearest", caught)

    real = fl._f32
    fl._f32 = lambda x: float(x)
    try:
        caught_shipped = score(base, dll_idx, dll_probs)
        caught_odd = score(odd, odd_idx, odd_probs, odd_pixels)
    finally:
        fl._f32 = real
    print(
        f"      'float32 narrowing -> double': caught on {caught_shipped}/{len(pixels)} "
        f"pixels at the SHIPPED scales -- a negative result, not a gap: 189/17/30 and "
        f"every S/T here are exact in binary32, so the narrowing is unobservable at "
        f"this DPI.  At scale 100.0000000001 (which narrows to exactly 100.0) it is "
        f"caught on {caught_odd}/{len(odd_pixels)} pixels."
    )
    if not caught_odd:
        print("      FAILED: a deliberate port bug was invisible")
        fails += 1

    # LST algebra mutations: change the port's own formula, not a helper
    real_lst = fl.flesh_lst
    for label, mut in (
        ("S = B - R (sign flip)", lambda r, g, b: (r + g + b, b - r, 2 * g - b - r)),
        ("T = 2R - G - B (axis swap)", lambda r, g, b: (r + g + b, r - b, 2 * r - g - b)),
        ("L = R + G + B + 1", lambda r, g, b: (r + g + b + 1, r - b, 2 * g - b - r)),
        ("S and T swapped", lambda r, g, b: (r + g + b, 2 * g - b - r, r - b)),
    ):
        fl.flesh_lst = mut
        try:
            caught = score(base, dll_idx, dll_probs)
        finally:
            fl.flesh_lst = real_lst
        probe(label, caught)

    # table-order mutations
    for label, mut in (
        ("l/s tables swapped", fl.FleshCondProbTables(l=tabs.s, s=tabs.l, t=tabs.t)),
        ("s/t tables swapped", fl.FleshCondProbTables(l=tabs.l, s=tabs.t, t=tabs.s)),
        ("l/t tables swapped", fl.FleshCondProbTables(l=tabs.t, s=tabs.s, t=tabs.l)),
    ):
        probe(
            label,
            sum(
                1
                for i, (r, g_, b) in enumerate(pixels)
                if not _same32(dll_probs[i], fl.flesh_skin_probability(r, g_, b, base, mut))
            ),
        )

    # the 0.001 probability floor
    real_floor = fl.PROB_FLOOR
    fl.PROB_FLOOR = 0.0
    try:
        caught = sum(
            1
            for i, (r, g_, b) in enumerate(pixels)
            if not _same32(dll_probs[i], fl.flesh_skin_probability(r, g_, b, base, tabs))
        )
    finally:
        fl.PROB_FLOOR = real_floor
    probe("probability floor 0.001 -> 0.0", caught)

    # reduction-loop mutations
    def probe_red(label: str, host) -> None:
        nonlocal fails
        differ = (
            host["count"] != dll_red["count"]
            or host["max_prob"] != dll_red["max_prob"]
            or not _same(host["nsum"], dll_red["nsum"])
            or not _same(host["stat"], dll_red["stat"])
            or host["prob"] != dll_red["prob"]
        )
        print(f"      '{label}': {'caught' if differ else 'MISSED'}")
        if not differ:
            print("      FAILED: a deliberate port bug was invisible")
            fails += 1

    h2 = _reduce_host(planes, weight, prob, th, bi, bo)
    hp = [r[:] for r in prob]
    s, n, c, m = fl.flesh_accumulate(
        hp, weight, planes, th,
        rows=range(bo, len(prob) - bo),  # the "obvious" symmetric bound
        cols=fl.flesh_loop_cols(len(prob[0]), bi),
    )
    probe_red("symmetric row bounds", {"count": c, "max_prob": m, "nsum": n, "stat": s, "prob": hp})

    hp = [r[:] for r in prob]
    s, n, c, m = fl.flesh_accumulate(
        hp, weight, planes, th,
        rows=fl.flesh_loop_rows(len(prob), bi),  # borders crossed
        cols=fl.flesh_loop_cols(len(prob[0]), bo),
    )
    probe_red("b_inner/b_outer crossed", {"count": c, "max_prob": m, "nsum": n, "stat": s,
                                          "prob": hp})

    real_imul = fl._imul32
    fl._imul32 = lambda a, b: a * b  # no 32-bit wrap
    try:
        hp = [r[:] for r in prob]
        s, n, c, m = fl.flesh_accumulate(
            hp, weight, planes, th,
            rows=fl.flesh_loop_rows(len(prob), bo),
            cols=fl.flesh_loop_cols(len(prob[0]), bi),
        )
    finally:
        fl._imul32 = real_imul
    # the wrap only shows on the overflow case
    planes_o, weight_o, prob_o, th_o, bi_o, bo_o = cases[-1]
    dll_o = run_dll_reduce(dll, base, planes_o, weight_o, prob_o, th_o, bi_o, bo_o)
    fl._imul32 = lambda a, b: a * b
    try:
        hp = [r[:] for r in prob_o]
        s, n, c, m = fl.flesh_accumulate(
            hp, weight_o, planes_o, th_o,
            rows=fl.flesh_loop_rows(len(prob_o), bo_o),
            cols=fl.flesh_loop_cols(len(prob_o[0]), bi_o),
        )
    finally:
        fl._imul32 = real_imul
    differ = not _same(s, dll_o["stat"])
    print(f"      'imul without the 32-bit wrap': {'caught' if differ else 'MISSED'}")
    if not differ:
        print("      FAILED: a deliberate port bug was invisible")
        fails += 1
    return fails


# --- what is still missing --------------------------------------------------


def report_gap(base: fl.FleshParams) -> None:
    print("\n  [6] what is still NOT ported (stated as plainly as the positives)")
    print("      * fcn.1029ec50 (3575 B) + fcn.1029cad0 — the int16 0..255 plane and")
    print("        the INTEGER threshold at results+0x28 — is NO LONGER a gap: it is")
    print("        ported and bit-exact, see pakon_flesh_threshold_golden.py.")
    print("      * 0x104e7880 and the two 1-D LUT pre-passes at 0x10270920 /")
    print("        0x10270b10 are NO LONGER a gap either: 0x104e7880 is .\\IemPad.cpp")
    print("        and builds the reduction's WEIGHT plane (from fcn.10271bc0's")
    print("        Gaussian), and the pre-passes apply the shift triple's own LUTs.")
    print("        Both bit-exact — see pakon_flesh_weight_golden.py.")
    print("      * 0x104e8360 is dead on the shipped DPI (useSmallAnalysisImage = 0,")
    print("        tested at 0x102704a9), and 0x1014cc20 is a type-checked handle")
    print("        wrapper, not a pixel transform.  The BOUNDARY they leave —")
    print("        fcn.10270280's arg3/arg4, from AnsImageData::copyToIemImage")
    print("        (fcn.100db520) at 0x101c9bac / 0x101c9beb — is now read through:")
    print("        on the colour-negative path analyzePostBalance pushes the scene's")
    print("        ONE analysis image (scene+0x04) twice, at 0x100fe396/0x100fe397,")
    print("        so arg3 and arg4 are copies of the same AnsImageData (tier 3).")
    print("      * fcn.10270280 arg7, the `float` exposure the exposureLimit guard reads")
    print("        (= [scene+0x4ac+0x10], 0x100fe37b).  arg8, which decides whether the")
    print("        SECOND pre-pass runs, is the literal 1 pushed at 0x100fe392.")
    print("      * which shipped cond-prob table the loader puts at P+0x38/0x3c/0x40")
    print("        is now READ OUT OF THE LOADER: AnsFleshCapabilityImpl's ctor")
    print("        fcn.101c84f0 resolves lCondProbKey/sCondProbKey/tCondProbKey")
    print("        (impl+0x80/+0x1080/+0x2080 = DPI+0x68/+0x1068/+0x2068) into")
    print("        impl+0x50/+0x54/+0x58 = DPI+0x38/+0x3c/+0x40, in that order")
    print("        (0x101c8dd5 / 0x101c8edf / 0x101c9000), and the vendor's own")
    print("        DPI dump fcn.1026f5a0 labels the same three offsets lCondProb /")
    print("        sCondProb / tCondProb.  Both tier 3, agreeing with the tier-1")
    print("        consumer above.")
    assert base.use_advanced == 0, "shipped DPI must select V1"
    assert base.one_d_table == 1, "shipped DPI must select the separable tables"
    print("      Not needed for THIS DPI, and asserted rather than ported:")
    print("      * useAdvanced == 0 (0x10270cb2 mov eax,[ebp+0x44] / 0x10270cbf je")
    print("        0x102711a2) skips the whole Bayesian block: fcn.102a2550,")
    print("        fcn.102a2940, fcn.1029dbd0, fcn.1029c090, fcn.1029bcd0 and the")
    print("        region->probability map at 0x10271020.  skinSBA.bn is that block's")
    print("        input, so on this DPI it is never consulted.")
    print("      * oneDTable == 1 (0x102a18af) selects the separable three-table")
    print("        product; the shipped 3-D LUT ROMM_LST_SkinProb_041403_v5_pack is")
    print("        read only by the oneDTable == 0 branch at 0x102a18f2.")


def check_units(base: fl.FleshParams, tabs: fl.FleshCondProbTables) -> None:
    """Tier 4.  A units cross-check between the two halves now in hand.

    The reduction makes ``stat = sum(w * L)`` and ``nsum = sum(w)`` over the
    detected flesh pixels, and the adjust arithmetic makes
    ``X = stat * (1/1.732) / nsum``.  So ``X`` is exactly ``0.5773672`` times
    the weight-weighted mean of ``L = R+G+B`` over the flesh region -- which
    means `fleshNeutralAim` and the `l` conditional-probability table are
    measured in the same units and can be compared.  They have never been
    compared before, because until now the two halves were not both ported.
    """
    print("\n  [7] units cross-check (TIER 4 -- a consistency check, not a proof)")
    k = fl.INV_1732
    aim_l = base.flesh_neutral_aim / k
    peak = tabs.l.index(max(tabs.l))
    peak_l = base.loff + base.lscale * peak
    print(f"      X = {k:.7f} * weighted-mean(L) over the flesh region, so the")
    print(f"      aim {base.flesh_neutral_aim:g} corresponds to mean L = {aim_l:.0f} "
          f"(l bin {(aim_l - base.loff) / base.lscale:.2f}).")
    print(f"      The shipped l table peaks at bin {peak} = L {peak_l:.0f} "
          f"(X = {peak_l * k:.0f}).")
    xs = [fl.invert_delta_to_statistic(d, base)[1] for d in (-40, 34, 15, 35, -59, 13)]
    lo_l, hi_l = min(xs) / k, max(xs) / k
    print(f"      §178's six Deltas imply X in {min(xs):.0f}..{max(xs):.0f}, i.e. mean L in")
    print(f"      {lo_l:.0f}..{hi_l:.0f} = l bins "
          f"{(lo_l - base.loff) / base.lscale:.1f}..{(hi_l - base.loff) / base.lscale:.1f}, "
          f"where the table reads")
    b0 = int((lo_l - base.loff) / base.lscale)
    b1 = int((hi_l - base.loff) / base.lscale)
    print(f"      {[tabs.l[b] for b in range(max(0, b0), min(32, b1 + 2))]}.")
    print("      The aim, the six measured Deltas and the l table's own high-probability")
    print("      shoulder all land in the same place.  That is consistent; it is NOT a")
    print("      reproduction of the six values.  Since this harness was written the")
    print("      threshold stage HAS been ported (pakon_flesh_threshold_golden.py) and")
    print("      so has the weight plane (pakon_flesh_weight_golden.py), so Delta now")
    print("      computes forward from pixels via fl.flesh_forward_delta — but the six")
    print("      values still cannot be reproduced, because no capture pairs a measured")
    print("      Delta to the frame that produced it (the v45 capture's 37 labels")
    print("      contain none).  fcn.10270280's arg3/arg4 are no longer unknown: both")
    print("      are copies of the scene's one analysis image (see the module header).")


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll_path.is_file():
        print(f"FAILED: no DLL at {dll_path}")
        return 1
    dll = dll_path.read_bytes()
    md5 = hashlib.md5(dll).hexdigest()
    print(f"  {dll_path.name} md5 {md5}")
    if md5 != fl.PAKONIMAU_MD5:
        print(f"FAILED: expected md5 {fl.PAKONIMAU_MD5}")
        return 1
    dpi_md5 = hashlib.md5(fl.DEFAULT_DPI.read_bytes()).hexdigest()
    print(f"  {fl.DEFAULT_DPI.name} md5 {dpi_md5}")
    if dpi_md5 != fl.FLESH_DPI_DEFAULT_MD5:
        print(f"FAILED: expected DPI md5 {fl.FLESH_DPI_DEFAULT_MD5}")
        return 1
    for name, want in fl.COND_PROB_MD5.items():
        got = hashlib.md5((fl.COND_PROB_DIR / name).read_bytes()).hexdigest()
        print(f"  {name} md5 {got}")
        if got != want:
            print(f"FAILED: expected {want}")
            return 1

    base = fl.default_params()
    tabs = fl.default_cond_prob_tables(base)
    assert len(tabs.l) == len(tabs.s) == len(tabs.t) == fl.COND_PROB_BINS
    assert max(tabs.l) == max(tabs.s) == max(tabs.t) == 1.0

    fails = 0
    fails += check_border(dll, base)
    fails += check_lst(dll, base, tabs)
    fails += check_clamp(dll)
    red_fails, cases = check_reduce(dll, base)
    fails += red_fails
    fails += check_teeth(dll, base, tabs, cases)
    report_gap(base)
    check_units(base, tabs)

    print("\n  Porting state (pakon_flesh module flags):")
    print(fl.porting_state())

    assert fl.FLESH_LST_PROBABILITY_PORTED
    assert fl.FLESH_REDUCTION_LOOP_PORTED
    assert fl.FLESH_BORDER_PORTED
    assert fl.FLESH_CLAMP_MAP_PORTED
    assert fl.FLESH_THRESHOLD_PORTED
    assert fl.FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED
    assert fl.FLESH_DETECTOR_PORTED  # pakon_flesh_whole_golden.py
    assert not fl.FLESH_ADVANCED_PATH_PORTED
    assert not fl.FLESH_3DLUT_PATH_PORTED

    if fails:
        print(f"\nFAILED ({fails})")
        return 1
    print("\nFLESH detector golden: ALL OK (bit-exact on every ported block)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
