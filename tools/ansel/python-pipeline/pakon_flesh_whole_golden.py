#!/usr/bin/env python3
"""Golden **whole** ``fcn.10270280`` vs the real PakonIMAu.dll (Unicorn).

The four earlier flesh harnesses each proved one *stage* of the flesh
block bit-exact and each named the same remaining gap: `fcn.10270280`
(6451 B) had never been executed **as one function**.  `flesh_forward_delta`
assembled the proven stages, but the assembly itself — which stage feeds
which, in which order, with which buffers — was read out of the
instruction stream and was therefore tier 3.  This harness closes that:
it calls `fcn.10270280` at its own entry point, with its own twelve
arguments, and lets it run to its own `ret`.

`PakonIMAu.dll` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``.

How the twelve arguments are built — no fabricated objects
-----------------------------------------------------------

* **arg3 / arg4** (the two analysis images) are produced by the vendor's
  own `AnsImageData::copyToIemImage` (`fcn.100db520`), driven from a plain
  POD laid out as §180's reading of it says (``+0x0c`` cols, ``+0x10``
  rows, ``+0x14`` nBands, ``+0x18`` bit depth, ``+0x20`` interleaved
  int16 data).  That is exactly how `AnsFleshCapabilityImpl::analyze`
  makes them (`0x101c9bac` / `0x101c9beb`), so the harness does not have
  to know `IemImage`'s internals at all.  On the colour-negative path the
  vendor passes the SAME image twice (`0x100fe396`/`0x100fe397`), which is
  the default here; one case passes two different images to exercise the
  split the DC_Premium path uses.
* **arg5** (the weight map) is built by the vendor's own `fcn.10271bc0`,
  called with the same ``(rows, cols, params, &obj)`` the impl calls it
  with at `0x101c99f0`.
* **arg1** is `pakon_flesh`'s `FleshParams.to_bytes()` — the layout the
  vendor's own DPI dump `fcn.1026f5a0` confirms field by field — with
  ``+0x38 / +0x3c / +0x40`` pointed at the three shipped 32-entry
  ``double`` tables, ``l / s / t`` in that order (see below).
* **arg7** is the ``float`` exposure the ``exposureLimit`` guard reads,
  **arg8** the literal ``1`` the CN caller pushes at `0x100fe392`.
* **arg9 / arg10 / arg12** are only read under
  ``writeIntermediateImages`` (`0x10271760 test al,al` on
  ``params+0x60a8``) and the arg12 debug branch at `0x1027182c`; the
  shipped DPI clears both, so they are passed as 0 and the harness proves
  they are unread by running with them zero and getting a clean `ret`.
* **arg2** is the by-value refcounted handle the caller addrefs at
  `0x101c9d06`; `fcn.10270280` only destroys it (`0x1027047a` /
  `0x10271a9b`), so 0 is passed and the destructor's null check is taken.

Two globals had to be *initialised*, not invented: the DLL's four
``IemType`` statics.  The harness runs the vendor's own constructor
`fcn.104d4170` with the vendor's own arguments, read straight out of the
static initialisers at `0x10570dc0 … 0x10570e60`::

    0x106c8254 = ("unspecified", 1)     [0x106c8294] = 0x106c8298   "byte"
    0x106c8298 = ("byte",        2)     [0x106c8250] = 0x106c82dc   "short"
    0x106c82dc = ("short",       3)     [0x106c82d8] = 0x106c82b8   "float"
    0x106c82b8 = ("float",       4)

which is also an independent confirmation of the element-type tags
`pakon_flesh_threshold_golden.py` had to *assert* from row strides
(2 = byte, 3 = short, 4 = float).  `fcn.10270280`'s own type guard at
`0x1027037a … 0x102703d8` accepts only ``byte`` and ``short`` and returns
``0xfffa`` otherwise; the int16 images built here are ``short``, and the
harness runs a negative control that shows the guard really does fire.

What this proves
----------------

Run on the same inputs, `fcn.10270280`'s own results struct (arg11) and
`flesh_forward_delta` agree bit-exactly on every field —
``X``, ``nsum``, ``Q``, ``-D/130``, ``maxProb/255``, the threshold and
the three ``m_fleshAdjust`` words — and four of its internal buffers,
read out of guest memory, agree sample for sample.  Three come from
`0x102712ac`, the reduction's own row-bound setup, where ESP is the body
ESP:

* the three colour planes after the 1-D shift-LUT pre-passes
  (``[esp+0x40]`` -> ``impl+0x20`` -> the three band impls' ``+0x18``
  row-pointer tables);
* the padded weight plane (``[esp+0x70]``);
* the probability plane after the 0/10/20/255 clamp map (``[esp+0x50]``),
  i.e. the plane the reduction is about to walk and binarise in place.

The fourth is taken at `0x102a1e25`, `fcn.102a1500`'s call to the
threshold chooser: its arg2 is the **int16 probability plane before
thresholding**.  That one matters more than it looks: the peak/valley
search only sees the *order* of the probability levels, so the
thresholded mask can be completely blind to a change the int16 plane
records — section [4] shows exactly that for an l<->s table swap.

So `flesh_forward_delta` is no longer a tier-3 assembly of tier-1 stages:
the assembly is now tier 1 too.  Running it also found one real port bug
that no stage harness could: the no-flesh branch reports ``maxProb = 0``
(`0x1027122c` / `0x10271607`), not the -1 the accumulator is seeded with
at `0x1027123e`.

What this does **not** prove
----------------------------

* Nothing about **which frame** the vendor hands in.  §178's six measured
  Deltas are still unpaired with the frames that produced them, so a
  forward run is still tier 4 *against §178*.  This harness proves the
  port computes what the DLL computes from the same pixels; it does not
  prove the pixels are the vendor's.
* The ``useAdvanced != 0`` branch (`skinSBA.bn`), the ``oneDTable == 0``
  3-D LUT branch, and the ``useSmallAnalysisImage != 0`` branch remain
  unported and unexecuted — the shipped DPI clears all three.
* ``writeIntermediateImages`` is never set here, so the arg9/arg10/arg12
  debug path is executed by neither engine.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \\
    tools/ansel/python-pipeline/pakon_flesh_whole_golden.py [PakonIMAu.dll]``
"""
from __future__ import annotations

import hashlib
import struct
import sys
from dataclasses import replace
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP

import pakon_flesh as fl
import pakon_flesh_threshold_golden as thr
import pakon_flesh_weight_golden as wg

_S = thr._STR

#: ``fcn.104d4170(this, name, tag)`` — the ``IemType`` ctor the static
#: initialisers at ``0x10570dc0 … 0x10570e20`` call.
IEM_TYPE_CTOR = 0x104D4170
#: ``(object address, name, tag)`` for each of the DLL's four IemType
#: statics, and the three ``.data`` slots that point at three of them.
IEM_TYPES = (
    (0x106C8254, b"unspecified", 1),
    (0x106C8298, b"byte", 2),
    (0x106C82DC, b"short", 3),
    (0x106C82B8, b"float", 4),
)
IEM_TYPE_SLOTS = ((0x106C8294, 0x106C8298), (0x106C8250, 0x106C82DC),
                  (0x106C82D8, 0x106C82B8))

#: ``AnsImageData::copyToIemImage``; the IemImage handle ctor and its vtable.
COPY_TO_IEM_IMAGE = 0x100DB520
IEM_IMAGE_HANDLE_CTOR = 0x104D46B0
IEM_IMAGE_VTABLE = 0x1057B10C

#: ``fcn.10270280``'s reduction row-bound setup.  ESP is the body ESP here
#: (``0x10271283 add esp,0x1c`` restored it and the one intervening
#: ``push``/thiscall pair balances), so these are literal frame slots.
REDUCE_SETUP = 0x102712AC
F_IMAGE_IMPL = 0x40
F_PROB_IMPL = 0x50
F_WEIGHT_IMPL = 0x70

#: The type guard's rejection code, ``0x1027047f mov ax, 0xfffa``.
WRONG_TYPE = 0xFFFA

#: `fcn.102a1500`'s single call to the threshold chooser.  Its arg2
#: (``[esp+4]`` at the call) is the int16 probability image, still
#: unthresholded — the most sensitive buffer the whole run exposes.
PROB_I16_CALL = 0x102A1E25


class Guest(thr.Guest):
    """`pakon_flesh_threshold_golden`'s guest, plus what the whole function needs.

    The extra import handlers are all `std::basic_string<char>` members the
    smaller harnesses never reached.  They carry only the debug text the
    vendor attaches to images and the element-type *names* the type guard
    compares, so none of them can move an arithmetic result — and the type
    guard's negative control in section [3] shows the comparison it feeds
    is live rather than vacuous.
    """

    def __init__(self, pe: bytes) -> None:
        super().__init__(pe)
        for obj, name, tag in IEM_TYPES:
            p = self.alloc(len(name) + 1)
            self.uc.mem_write(p, name + b"\0")
            self.call(IEM_TYPE_CTOR, ecx=obj, args=(p, tag))
        for slot, obj in IEM_TYPE_SLOTS:
            self.uc.mem_write(slot, struct.pack("<I", obj))

    def _handlers(self):
        h = super()._handlers()
        # MSVC7.1 decorates the copy ctor / by-reference assign with a
        # trailing "@@Z", which the earlier harnesses' table spells "@Z";
        # those entries are dead, these are the names actually imported.
        h["??0%s@QAE@ABV01@@Z" % _S] = self._str_ctor_copy
        h["??4%s@QAEAAV01@ABV01@@Z" % _S] = self._str_assign
        h["??4%s@QAEAAV01@PBD@Z" % _S] = self._str_assign_cstr
        h["?c_str@%s@QBEPBDXZ" % _S] = self._str_c_str
        h["?size@%s@QBEIXZ" % _S] = self._str_size
        h["??Y%s@QAEAAV01@ABV01@@Z" % _S] = self._str_append
        h["??Y%s@QAEAAV01@PBD@Z" % _S] = self._str_append_cstr
        return h

    def _str_assign_cstr(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        self._str_set(this, self._cstr(a[0]))
        return this, 1

    def _str_c_str(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        d = self._str_read(this)
        p = self.alloc(len(d) + 1)
        self.uc.mem_write(p, d + b"\0")
        return p, 0

    def _str_size(self, a):
        return len(self._str_read(self.uc.reg_read(UC_X86_REG_ECX))), 0

    def _str_append(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        self._str_set(this, self._str_read(this) + self._str_read(a[0]))
        return this, 1

    def _str_append_cstr(self, a):
        this = self.uc.reg_read(UC_X86_REG_ECX)
        self._str_set(this, self._str_read(this) + self._cstr(a[0]))
        return this, 1

    # -- guest helpers ------------------------------------------------------

    def blob(self, data: bytes) -> int:
        p = self.alloc(len(data))
        self.uc.mem_write(p, data)
        return p

    def rows_i16(self, impl: int, h: int, w: int):
        """Read an ``IemImageData``'s ``+0x18`` row-pointer table as int16."""
        rp = struct.unpack("<I", self.uc.mem_read(impl + 0x18, 4))[0]
        out = []
        for y in range(h):
            p = struct.unpack("<I", self.uc.mem_read(rp + 4 * y, 4))[0]
            out.append(list(struct.unpack("<%dh" % w, self.uc.mem_read(p, 2 * w))))
        return out

    def image_data_pod(self, planes, *, bit_depth: int = 12, bands: int | None = None) -> int:
        """The `AnsImageData` fields `fcn.100db520` reads, and nothing else."""
        h, w = len(planes[0]), len(planes[0][0])
        n = len(planes) if bands is None else bands
        inter = bytearray()
        for y in range(h):
            for x in range(w):
                for p in planes:
                    inter += struct.pack("<h", p[y][x])
        data = self.blob(bytes(inter))
        pod = self.alloc(0x40)
        self.uc.mem_write(pod, b"\0" * 0x40)
        self.uc.mem_write(pod + 0x0C, struct.pack("<ii", w, h))
        self.uc.mem_write(pod + 0x14, struct.pack("<i", n))
        self.uc.mem_write(pod + 0x18, struct.pack("<i", bit_depth))
        self.uc.mem_write(pod + 0x20, struct.pack("<I", data))
        return pod

    def iem_image(self, pod: int) -> int:
        """`AnsImageData::copyToIemImage` — the vendor's own producer."""
        img = self.alloc(16)
        self.uc.mem_write(img, b"\0" * 16)
        self.call(IEM_IMAGE_HANDLE_CTOR, ecx=img)
        self.uc.mem_write(img, struct.pack("<I", IEM_IMAGE_VTABLE))
        err = self.alloc(4)
        self.uc.mem_write(err, b"\0" * 4)
        self.call(COPY_TO_IEM_IMAGE, ecx=pod, args=(err, img))
        status = struct.unpack("<I", self.uc.mem_read(err, 4))[0]
        if status:
            raise RuntimeError("copyToIemImage returned %#x" % status)
        return img


# --- running the whole function ---------------------------------------------


def run_dll_whole(pe: bytes, lst_planes, stat_planes, shifts, params, tables, *,
                  exposure: float = 0.0, arg8: int = 1, force_type: int | None = None):
    """`fcn.10270280(arg1 … arg12)` end to end.

    Returns ``{'ret', 'results', 'adjust', 'colour', 'weight', 'prob_i16',
    'prob'}``.  The planes are the vendor's own buffers, read at
    `0x102a1e25` (``prob_i16``) and `0x102712ac` (the rest).  On a frame
    where the clamp map finds no flesh, `0x10271246 je 0x10271607` skips the
    reduction entirely, so the `0x102712ac` buffers are simply absent.
    """
    g = Guest(pe)
    uc = g.uc
    h, w = len(stat_planes[0]), len(stat_planes[0][0])

    img_lst = g.iem_image(g.image_data_pod(lst_planes))
    img_stat = (img_lst if stat_planes is lst_planes
                else g.iem_image(g.image_data_pod(stat_planes)))

    p_addr = g.blob(bytes(params.to_bytes()))
    uc.mem_write(p_addr + 0x38, struct.pack(
        "<III",
        g.blob(struct.pack("<%dd" % len(tables.l), *tables.l)),
        g.blob(struct.pack("<%dd" % len(tables.s), *tables.s)),
        g.blob(struct.pack("<%dd" % len(tables.t), *tables.t)),
    ))

    weight = g.alloc(16)
    uc.mem_write(weight, b"\0" * 16)
    st = g.call(fl.FLESH_WEIGHT_MAP_FN,
                args=(len(lst_planes[0]), len(lst_planes[0][0]), p_addr, weight)) & 0xFFFF
    if st:
        raise RuntimeError("fcn.10271bc0 (weight map) returned %#x" % st)

    results = g.alloc(0x80)
    uc.mem_write(results, b"\0" * 0x80)
    grabbed: dict = {}

    def snap_prob(uc_, addr, size, ud):
        if addr != PROB_I16_CALL or "prob_i16" in grabbed:
            return
        esp = uc_.reg_read(UC_X86_REG_ESP)
        img = struct.unpack("<I", uc_.mem_read(esp + 4, 4))[0]
        impl = struct.unpack("<I", uc_.mem_read(img + 4, 4))[0]
        ih, iw = struct.unpack("<ii", uc_.mem_read(impl + 0x10, 8))
        grabbed["prob_i16"] = g.rows_i16(impl, ih, iw)

    def snap(uc_, addr, size, ud):
        if addr != REDUCE_SETUP or "colour" in grabbed:
            return
        esp = uc_.reg_read(UC_X86_REG_ESP)
        slot = lambda o: struct.unpack("<I", uc_.mem_read(esp + o, 4))[0]
        impl = slot(F_IMAGE_IMPL)
        bands = struct.unpack("<I", uc_.mem_read(impl + 0x20, 4))[0]
        grabbed["colour"] = [
            g.rows_i16(struct.unpack("<I", uc_.mem_read(bands + 8 * k + 4, 4))[0], h, w)
            for k in range(3)
        ]
        grabbed["weight"] = g.rows_i16(slot(F_WEIGHT_IMPL), h, w)
        grabbed["prob"] = g.rows_i16(slot(F_PROB_IMPL), h, w)

    uc.hook_add(UC_HOOK_CODE, snap, begin=REDUCE_SETUP, end=REDUCE_SETUP + 4)
    uc.hook_add(UC_HOOK_CODE, snap_prob, begin=PROB_I16_CALL, end=PROB_I16_CALL + 4)
    if force_type is not None:
        # `0x104d4510` is ``mov ecx,[ecx+4]; jmp 0x100ecbc0`` and `0x100ecbc0`
        # is ``mov eax,[ecx+0x10]; ret`` — the element type lives at
        # ``IemImageData+0x10``.  Retyping it AFTER the weight map is built
        # (which needs the real 'short') is the negative control for the guard.
        for img in {img_lst, img_stat}:
            impl = struct.unpack("<I", uc.mem_read(img + 4, 4))[0]
            uc.mem_write(impl + 0x10, struct.pack("<I", force_type))
    ret = g.call(0x10270280, args=(
        p_addr, 0, img_lst, img_stat, weight,
        g.blob(struct.pack("<3h", *shifts)),
        struct.unpack("<I", struct.pack("<f", exposure))[0],
        1 if arg8 else 0, 0, 0, results, 0,
    )) & 0xFFFF
    out = {
        "ret": ret,
        "results": struct.unpack("<7d", uc.mem_read(results, 56)),
        "adjust": struct.unpack("<3h", uc.mem_read(results + 0x30, 6)),
    }
    out.update(grabbed)
    return out


# --- the comparison ---------------------------------------------------------

#: ``(label, height, width, shift triple, exposure, arg8, param overrides)``
CASES = (
    ("synthetic on the tables' peak", 40, 52, wg.ENTRY_TRIPLES[0], 1e9, 1, {}),
    ("same, second pre-pass off (arg8 = 0)", 40, 52, wg.ENTRY_TRIPLES[0], 1e9, 0, {}),
    ("a second entry triple", 33, 47, wg.ENTRY_TRIPLES[1], 1e9, 1, {}),
    ("stOnly = 1 (the l table is skipped)", 28, 36, wg.ENTRY_TRIPLES[0], 1e9, 1,
     {"st_only": 1}),
    # the shipped DPI already sets tSpace = 1, so the variant is tSpace = 0
    ("tSpace = 0 (X scaled by 1/3, not 0.5773672…)", 28, 36, wg.ENTRY_TRIPLES[0],
     1e9, 1, {"t_space": 0}),
    ("darkenOnly = 1", 28, 36, wg.ENTRY_TRIPLES[0], 1e9, 1, {"darken_only": 1}),
    ("exposure below exposureLimit", 28, 36, wg.ENTRY_TRIPLES[0], -1e9, 1, {}),
    ("odd dimensions", 17, 23, wg.ENTRY_TRIPLES[2], 1e9, 1, {}),
    ("a frame with no flesh at all", 24, 32, wg.ENTRY_TRIPLES[0], 1e9, 1, {}),
)

_RESULT_FIELDS = ("x", "nsum", "fraction", "drive", "max_prob", "threshold")


def _flat_frame(shifts, h, w, seed=0x2B1D):
    """Uniform grey plus noise — nowhere near the tables' peak."""
    rng = wg.Rng(seed)
    return [[[900 - s + rng.between(-30, 30) for _ in range(w)] for _ in range(h)]
            for s in shifts]


def _compare(label, dll, host) -> tuple[int, int]:
    """Return ``(failures, samples)``."""
    fails = 0
    x, nsum, frac, dneg, maxp, thr = dll["results"][:6]
    checks = [
        ("X", x, host["x"]),
        ("nsum", nsum, host["nsum"]),
        ("Q", frac, host["fraction"]),
        # `0x10271659 fmul qword [0x105a4c88]` and `0x1027166c fmul qword
        # [0x105a1778]` — the DLL MULTIPLIES by the doubles nearest 1/130
        # and 1/255; dividing by 130.0 here differs by 1 ulp on some frames.
        ("-D/130", dneg, host["neg_drive_over_130"]),
        ("maxProb/255", maxp, host["max_prob_over_255"]),
        ("threshold", thr, float(host["threshold"])),
        ("adjust[0]", dll["adjust"][0], host["delta"]),
        ("adjust[1]", dll["adjust"][1], host["delta"]),
        ("adjust[2]", dll["adjust"][2], host["delta"]),
    ]
    for name, a, b in checks:
        if a != b:
            fails += 1
            print(f"      FAIL [{label}] {name}: dll={a!r} host={b!r}")
    samples = len(checks)
    for name, key, ref in (("colour planes", "colour", host["_colour"]),
                           ("weight plane", "weight", host["_weight"]),
                           ("int16 probability plane", "prob_i16", host["_prob_i16"]),
                           ("clamped probability plane", "prob", host["_prob"])):
        got = dll.get(key)
        if got is None:
            continue
        if key == "colour":
            n = sum(len(p) * len(p[0]) for p in ref)
            bad = sum(a != b for pa, pb in zip(got, ref)
                      for ra, rb in zip(pa, pb) for a, b in zip(ra, rb))
        else:
            n = len(ref) * len(ref[0])
            bad = sum(a != b for ra, rb in zip(got, ref) for a, b in zip(ra, rb))
        samples += n
        if bad:
            fails += 1
            print(f"      FAIL [{label}] {name}: {bad}/{n} samples differ")
    return fails, samples


def _host_forward(planes_lst, planes_stat, shifts, params, tables, exposure, arg8):
    """`flesh_forward_delta` plus the three intermediates the DLL exposes."""
    res = fl.flesh_forward_delta(planes_lst, planes_stat, shifts, params=params,
                                 tables=tables, exposure=exposure,
                                 second_prepass=bool(arg8))
    luts = fl.flesh_shift_luts(shifts)
    h, w = len(planes_stat[0]), len(planes_stat[0][0])
    res["_colour"] = fl.flesh_apply_shift_luts(planes_stat, luts)
    res["_weight"] = fl.flesh_reduction_weight_plane(h, w, params)
    lst = fl.flesh_apply_shift_luts(planes_lst, luts) if arg8 else planes_lst
    prob_i = fl.flesh_prob_to_int16(fl.flesh_probability_plane(lst, params, tables))
    thr_ = fl.flesh_threshold_from_plane(prob_i)
    res["_prob_i16"] = prob_i
    res["_prob"] = fl.flesh_clamp_plane(fl.flesh_reduction_plane(prob_i, thr_))[0]
    return res


def check_cases(pe: bytes, base, tables) -> tuple[int, int, list]:
    print("\n  [1] fcn.10270280 as ONE function, against flesh_forward_delta")
    fails = samples = 0
    kept = []
    for label, h, w, shifts, expo, arg8, over in CASES:
        params = replace(base, **over) if over else base
        planes = (_flat_frame(shifts, h, w) if "no flesh" in label
                  else wg._synthetic_frame(shifts, h=h, w=w))
        dll = run_dll_whole(pe, planes, planes, shifts, params, tables,
                            exposure=expo, arg8=arg8)
        if dll["ret"]:
            fails += 1
            print(f"      FAIL [{label}] fcn.10270280 returned {dll['ret']:#x}")
            continue
        host = _host_forward(planes, planes, shifts, params, tables, expo, arg8)
        f, n = _compare(label, dll, host)
        fails += f
        samples += n
        kept.append((label, planes, shifts, params, expo, arg8, dll, host))
        print(f"      {label}: thr={host['threshold']} count={host['flesh_count']} "
              f"Delta={host['delta']:+d}  ({n} samples"
              f"{'' if not f else f', {f} MISMATCHED'})")
    return fails, samples, kept


def check_split_images(pe: bytes, base, tables) -> tuple[int, int]:
    """arg3 != arg4 — the DC_Premium shape, which the CN path never takes."""
    print("\n  [2] arg3 != arg4 (the DC_Premium shape; CN passes one image twice)")
    shifts = wg.ENTRY_TRIPLES[0]
    lst = wg._synthetic_frame(shifts, h=30, w=40, seed=0x51D2)
    stat = wg._synthetic_frame(shifts, h=30, w=40, seed=0x9E37)
    dll = run_dll_whole(pe, lst, stat, shifts, base, tables, exposure=1e9)
    if dll["ret"]:
        print(f"      FAIL: fcn.10270280 returned {dll['ret']:#x}")
        return 1, 0
    host = _host_forward(lst, stat, shifts, base, tables, 1e9, 1)
    fails, n = _compare("split images", dll, host)
    print(f"      thr={host['threshold']} count={host['flesh_count']} "
          f"Delta={host['delta']:+d}  ({n} samples)")
    print("      The pad is NOT an identity in this shape, and the LST image and")
    print("      the summed image differ — which is why this case is worth running")
    print("      even though `analyzePostBalance` never produces it.")
    return fails, n


def check_type_guard(pe: bytes, base, tables) -> int:
    """The guard at `0x1027037a … 0x102703d8` must actually reject."""
    print("\n  [3] negative control: the element-type guard is live")
    shifts = wg.ENTRY_TRIPLES[0]
    planes = wg._synthetic_frame(shifts, h=16, w=20)
    dll = run_dll_whole(pe, planes, planes, shifts, base, tables,
                        exposure=1e9, force_type=0x106C8254)  # "unspecified"
    if dll["ret"] != WRONG_TYPE:
        print(f"      FAILED: with the image retyped 'unspecified' the DLL "
              f"returned {dll['ret']:#x}, not {WRONG_TYPE:#x}")
        return 1
    print(f"      image retyped 'unspecified' -> ret = {dll['ret']:#x} "
          f"(0x1027047f mov ax,0xfffa), as it must.")
    print("      So the 'short' the harness builds is checked, not assumed.")
    return 0


def check_slot_assignment(pe: bytes, base, tables) -> int:
    """`P+0x38 / +0x3c / +0x40` = l / s / t — now executable, not just read."""
    print("\n  [4] the conditional-probability slot assignment, executed")
    shifts = wg.ENTRY_TRIPLES[0]
    planes = wg._synthetic_frame(shifts, h=28, w=36)
    ok = run_dll_whole(pe, planes, planes, shifts, base, tables, exposure=1e9)
    n_plane = len(ok["prob_i16"]) * len(ok["prob_i16"][0])
    fails = 0
    for name, swapped in (
        ("s and t tables swapped",
         fl.FleshCondProbTables(l=tables.l, s=tables.t, t=tables.s)),
        ("l and s tables swapped",
         fl.FleshCondProbTables(l=tables.s, s=tables.l, t=tables.t)),
        ("l and t tables swapped",
         fl.FleshCondProbTables(l=tables.t, s=tables.s, t=tables.l)),
    ):
        bad = run_dll_whole(pe, planes, planes, shifts, base, swapped, exposure=1e9)
        moved = sum(a != b for ra, rb in zip(ok["prob_i16"], bad["prob_i16"])
                    for a, b in zip(ra, rb))
        mask = sum(a != b for ra, rb in zip(ok["prob"], bad["prob"])
                   for a, b in zip(ra, rb)) if "prob" in bad else None
        if not moved:
            print(f"      FAILED: '{name}' changed nothing in the DLL — the "
                  f"harness cannot tell the slots apart")
            fails += 1
        else:
            print(f"      '{name}': the DLL's own int16 probability plane moves "
                  f"on {moved}/{n_plane} samples; the thresholded mask moves on "
                  f"{'—' if mask is None else mask} "
                  f"(Delta {ok['adjust'][0]:+d} -> {bad['adjust'][0]:+d})")
    print("      Note the thresholded mask can be blind to the l<->s swap while")
    print("      the int16 plane is not: the peak/valley search only sees the")
    print("      ORDER of the probability levels, and on a two-region frame the")
    print("      swap preserves it.  That is why the buffer captured at the call")
    print("      to fcn.1029ec50 (0x102a1e25) — before thresholding — is the one")
    print("      that decides this, and why scoring only Delta would not have.")
    print("      Which loaded table lands in which slot is settled on the LOADER")
    print("      side by `AnsFleshCapabilityImpl::AnsFleshCapabilityImpl`")
    print("      (fcn.101c84f0): it looks up impl+0x80 / +0x1080 / +0x2080 —")
    print("      i.e. DPI+0x68 / +0x1068 / +0x2068 = lCondProbKey / sCondProbKey /")
    print("      tCondProbKey — and stores each result at impl+0x50 / +0x54 /")
    print("      +0x58 (0x101c8dd5 / 0x101c8edf / 0x101c9000).  The DPI sits at")
    print("      impl+0x18, so those are DPI+0x38 / +0x3c / +0x40.  The vendor's")
    print("      own DPI dump fcn.1026f5a0 prints the same three offsets as")
    print("      'lCondProb' / 'sCondProb' / 'tCondProb' (0x1026f6ef / 0x1026f71d /")
    print("      0x1026f74c).  Both are tier 3, and they agree with the tier-1")
    print("      consumer (fcn.102a1500: +0x38 is the slot stOnly skips).")
    return fails


def check_teeth(pe: bytes, base, tables, kept) -> int:
    print("\n  [5] deliberate port bugs — the harness must catch each one")
    fails = 0

    def probe(label: str, caught, total=None, inert_reason: str | None = None):
        nonlocal fails
        n = caught if isinstance(caught, int) else int(bool(caught))
        tail = f"{n}" + (f"/{total}" if total else "")
        if n:
            print(f"      '{label}': caught on {tail} differing values")
        elif inert_reason:
            print(f"      '{label}': PROVABLY INERT on this path — {inert_reason}")
        else:
            print(f"      '{label}': NOT CAUGHT\n      FAILED: a deliberate port "
                  f"bug was invisible to this harness")
            fails += 1

    label, planes, shifts, params, expo, arg8, dll, host = kept[0]

    def score(mutated) -> int:
        """How many of the DLL's own outputs the mutated port now disagrees with.

        Both the five headline scalars AND every sample of the probability
        plane the DLL exposes at `0x102712ac` — a table swap can leave the
        thresholded scalars alone while moving the plane, so scoring only
        the scalars would under-report.
        """
        n = 0
        ref = (dll["results"][0], dll["results"][1], dll["results"][2],
               dll["results"][5], float(dll["adjust"][0]))
        got = (mutated["x"], mutated["nsum"], mutated["fraction"],
               float(mutated["threshold"]), float(mutated["delta"]))
        for a, b in zip(ref, got):
            n += a != b
        n += sum(a != b for ra, rb in zip(dll["prob_i16"], mutated["_prob_i16"])
                 for a, b in zip(ra, rb))
        n += sum(a != b for ra, rb in zip(dll["prob"], mutated["_prob"])
                 for a, b in zip(ra, rb))
        return n

    # 1. the shift triple applied with the wrong sign
    probe("shift LUTs built from -shift instead of +shift",
          score(_host_forward(planes, planes, tuple(-s for s in shifts), params,
                              tables, expo, arg8)))
    # 2. the second pre-pass skipped
    probe("second pre-pass (arg8) skipped",
          score(_host_forward(planes, planes, shifts, params, tables, expo, 0)))
    # 3. s and t axes swapped
    probe("s and t conditional-probability tables swapped",
          score(_host_forward(planes, planes, shifts, params,
                              fl.FleshCondProbTables(l=tables.l, s=tables.t,
                                                     t=tables.s), expo, arg8)))
    # 4. l and s axes swapped
    probe("l and s conditional-probability tables swapped",
          score(_host_forward(planes, planes, shifts, params,
                              fl.FleshCondProbTables(l=tables.s, s=tables.l,
                                                     t=tables.t), expo, arg8)))
    # 5. stOnly ignored
    probe("stOnly ignored (l table always multiplied in)",
          score(_host_forward(planes, planes, shifts, replace(params, st_only=1),
                              tables, expo, arg8)),
          inert_reason=None)
    # 6. the weight plane replaced by a flat 1000
    flat = [[1000] * len(planes[0][0]) for _ in range(len(planes[0]))]
    mut = fl.flesh_forward_delta(planes, planes, shifts, params=params,
                                 tables=tables, exposure=expo,
                                 second_prepass=bool(arg8), weight=flat)
    probe("weight plane flat 1000 instead of the Gaussian",
          sum(a != b for a, b in ((dll["results"][0], mut["x"]),
                                  (dll["results"][1], mut["nsum"]),
                                  (float(dll["adjust"][0]), float(mut["delta"])))))
    # 7. exposure guard removed
    lo = _host_forward(planes, planes, shifts, params, tables, -1e9, arg8)
    probe("exposureLimit guard removed", int(lo["delta"] != host["delta"]),
          inert_reason=None)
    # 8. darkenOnly ignored
    dark = _host_forward(planes, planes, shifts, replace(params, darken_only=1),
                         tables, expo, arg8)
    probe("darkenOnly ignored", int(dark["delta"] != host["delta"]),
          inert_reason="on this frame D < 0, so `darkenOnly && D > 0` cannot fire; "
                       "the DLL agrees — its own Delta is unchanged too "
                       "(case 'darkenOnly = 1' in section [1])")
    return fails


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else thr.DEFAULT_DLL
    pe = path.read_bytes()
    md5 = hashlib.md5(pe).hexdigest()
    print(f"PakonIMAu.dll {path}\n  md5 {md5}"
          f"{'' if md5 == fl.PAKONIMAU_MD5 else '   *** NOT the documented build ***'}")
    base = fl.default_params()
    tables = fl.default_cond_prob_tables(base)

    fails = 0
    f, samples, kept = check_cases(pe, base, tables)
    fails += f
    f2, n2 = check_split_images(pe, base, tables)
    fails += f2
    samples += n2
    fails += check_type_guard(pe, base, tables)
    fails += check_slot_assignment(pe, base, tables)
    fails += check_teeth(pe, base, tables, kept)

    print(f"\n  {samples} values compared against the real DLL: "
          f"{'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}")
    print("\n  Porting state after this run (pakon_flesh module flags):")
    for name in sorted(n for n in dir(fl) if n.endswith("_PORTED")):
        print(f"        {name} = {getattr(fl, name)}")
    print("\n  fcn.10270280 has now been executed AS ONE FUNCTION.  Its results")
    print("  struct and four of its internal buffers match flesh_forward_delta")
    print("  bit-exactly, so the assembly is tier 1, not tier 3.  What it does")
    print("  NOT settle: which frame the vendor hands in.  §178's six measured")
    print("  Deltas are still unpaired with their frames, so any comparison")
    print("  against those numbers remains tier 4.")

    assert fl.FLESH_ADJUST_ARITHMETIC_PORTED
    assert fl.FLESH_LST_PROBABILITY_PORTED
    assert fl.FLESH_REDUCTION_LOOP_PORTED
    assert fl.FLESH_BORDER_PORTED
    assert fl.FLESH_CLAMP_MAP_PORTED
    assert fl.FLESH_THRESHOLD_PORTED
    assert fl.FLESH_WEIGHT_MAP_PORTED
    assert fl.FLESH_PAD_PORTED
    assert fl.FLESH_SHIFT_LUT_PORTED
    assert fl.FLESH_PREPASS_PORTED
    assert fl.FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED
    assert fl.FLESH_DETECTOR_PORTED
    assert not fl.FLESH_ANALYSIS_IMAGE_PORTED
    assert not fl.FLESH_ADVANCED_PATH_PORTED
    assert not fl.FLESH_3DLUT_PATH_PORTED
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
