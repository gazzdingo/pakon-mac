#!/usr/bin/env python3
"""Golden: ``pakon_orderfpo_vecpack`` vs the real ``PakonIMAu.dll`` under Unicorn.

Target
------
``PakonIMAu.dll`` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``, ``fcn.102b7440``
(``0x102b7440``…``0x102b81c7``) — the function that fills the 720-int32
statistics vector at ``scene+0x3c`` that the vendor's pcode VM consumes to
produce ``L`` (docs/74 §88/§90).

The function makes no calls, imports nothing and reads no globals
(``afi``: ``is-pure: true``, ``out-degree: 0``), so the emulation needs no
stubs at all: map the image, map a stack, push ten cdecl arguments, run.
Nothing is patched.  What is diffed is the **whole** of the three buffers the
function mutates — ``scene`` (4608 B), ``arg6`` (the statistics block) and
``arg7`` (the count block) — byte for byte, not a selected slot list.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
   tools/ansel/python-pipeline/pakon_orderfpo_vecpack_golden.py [dll]``

What this does and does not establish
-------------------------------------
**Establishes** (tier 1): the port reproduces the real DLL's output bit-exactly
over the case set below, which drives both ``mode`` branches, both arms of the
``i16(scene+6) > i16(arg9+0xe)`` selector, both arms of the ``arg7+0x20``
selector, every one of the 14 ``arg8`` bank gates, and both signs of every
divisor and numerator.

**Does not establish** that ``L`` can now be computed from a scan.  It cannot:
every number this function packs is produced by ``fcn.102aece0`` (24475 B,
1766 basic blocks), which is **not ported**.  This closes the *packing*, not
the *measuring*.  The captured-vector cross-check below is a consistency test
of the recovered layout against real hardware data, not a port of the source.
"""
from __future__ import annotations

import hashlib
import random
import struct
import sys
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_MODE_32, Uc, UcError
from unicorn.x86_const import UC_X86_REG_ESP

import pakon_orderfpo_vecpack as V

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x00100000
DATA_ADDR = 0x0C000000
DATA_SIZE = 0x00100000
RET_ADDR = 0x0BE00000

FN = 0x102B7440

DEFAULT_DLL = (
    Path(__file__).resolve().parents[2] / "re" / "live_hooks" / "wine_host" / "PakonIMAu.dll"
)

SCENE_LEN = 4608  # the size the live hook dumps as arg11_big / arg1_big_filled
A6_LEN = 0x0B00
A7_LEN = 0x0040
A8_LEN = 0x0020
A9_LEN = 0x0020
A3_LEN = 0x4B * 4
A4_LEN = 0x13 * 4
A5_LEN = 9 * 4


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
            data += b"\x00" * (vsz - len(data))
        uc.mem_write(IMAGE_BASE + va, data[: max(vsz, rsz)])


class Case:
    """One full argument set for ``fcn.102b7440``."""

    def __init__(self, name: str, *, mode: int, arg2: int, scene: bytearray,
                 a3: bytes, a4: bytes, a5: bytes, a6: bytearray,
                 a7: bytearray, a8: bytes, a9: bytes) -> None:
        self.name = name
        self.mode = mode
        self.arg2 = arg2
        self.scene = scene
        self.a3, self.a4, self.a5 = a3, a4, a5
        self.a6, self.a7 = a6, a7
        self.a8, self.a9 = a8, a9


def run_dll(pe: bytes, c: Case) -> tuple[bytes, bytes, bytes]:
    """Execute the real DLL bytes; return (scene, arg6, arg7) after."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(DATA_ADDR, DATA_SIZE)
    uc.mem_map(RET_ADDR, 0x1000)

    p = DATA_ADDR + 0x1000
    addrs = {}
    for name, blob in (("scene", c.scene), ("a3", c.a3), ("a4", c.a4),
                       ("a5", c.a5), ("a6", c.a6), ("a7", c.a7),
                       ("a8", c.a8), ("a9", c.a9)):
        uc.mem_write(p, bytes(blob))
        addrs[name] = p
        p += _align_up(len(blob) + 0x40)

    args = [c.mode, c.arg2, addrs["a3"], addrs["a4"], addrs["a5"], addrs["a6"],
            addrs["a7"], addrs["a8"], addrs["a9"], addrs["scene"]]
    esp = STACK_ADDR + 0x80000
    esp -= 4 * len(args)
    for i, a in enumerate(args):
        uc.mem_write(esp + 4 * i, struct.pack("<I", a & 0xFFFFFFFF))
    esp -= 4
    uc.mem_write(esp, struct.pack("<I", RET_ADDR))
    uc.reg_write(UC_X86_REG_ESP, esp)

    try:
        uc.emu_start(FN, RET_ADDR, timeout=30_000_000)
    except UcError as e:
        raise RuntimeError("unicorn %s in case %s" % (e, c.name)) from e

    return (bytes(uc.mem_read(addrs["scene"], SCENE_LEN)),
            bytes(uc.mem_read(addrs["a6"], len(c.a6))),
            bytes(uc.mem_read(addrs["a7"], len(c.a7))))


def run_port(c: Case) -> tuple[bytes, bytes, bytes]:
    s, a6, a7 = V.vecpack(c.scene, mode=c.mode, arg2=c.arg2, arg3=c.a3,
                          arg4=c.a4, arg5=c.a5, arg6=c.a6, arg7=c.a7,
                          arg8=c.a8, arg9=c.a9)
    return bytes(s), bytes(a6), bytes(a7)


# ---------------------------------------------------------------- case builder


def _rand_i32(rng: random.Random, mag: int = 1 << 26) -> int:
    return rng.randint(-mag, mag)


def build_case(rng: random.Random, name: str, *, mode: int, arg2: int,
               high: bool, alt: bool, gates: int, neg_div: bool,
               thr_zero: bool = False, aim_low: bool = False) -> Case:
    """Construct a case that lands on a chosen combination of branches.

    ``high``  selects ``i16(scene+6) > i16(arg9+0xe)``.
    ``alt``   selects ``word[arg7+0x20] != 0`` (only reachable when ``high``).
    ``gates`` is the 14-bit mask of enabled ``arg8`` bank gates.
    """
    scene = bytearray(rng.randbytes(SCENE_LEN))
    a6 = bytearray(struct.pack("<%di" % (A6_LEN // 4),
                               *[_rand_i32(rng) for _ in range(A6_LEN // 4)]))
    a7 = bytearray(A7_LEN)
    a9 = bytearray(A9_LEN)
    a8 = bytearray(A8_LEN)

    # divisors: never zero (the DLL would #DE), both signs when asked
    for k in range(0, 0x24, 2):
        d = rng.randint(1, 900)
        if neg_div and rng.random() < 0.5:
            d = -d
        struct.pack_into("<h", a7, k, d)
    struct.pack_into("<h", a7, 0x20, rng.randint(1, 900) if alt else 0)

    # scene+6 vs arg9+0xe drives the selector; scene+8/+0xa/+0xc/+0x16 are
    # read as signed words and land in slots 612..615 and the +0x18 word.
    struct.pack_into("<h", scene, 0x06, 500)
    struct.pack_into("<h", a9, 0x0E, 100 if high else 900)
    struct.pack_into("<h", scene, 0x08, rng.randint(1, 4000))
    struct.pack_into("<h", scene, 0x0A, rng.randint(-4000, 4000))
    struct.pack_into("<h", scene, 0x0C, rng.randint(-4000, 4000))
    struct.pack_into("<h", scene, 0x16, 200 if aim_low else rng.randint(3000, 9000))

    # arg9 words 0..6 drive the scene+0x18 rounding division
    struct.pack_into("<h", a9, 0x00, 0 if thr_zero else rng.randint(-900, 900))
    struct.pack_into("<h", a9, 0x02, rng.choice([-1, 1]) * rng.randint(1, 700))
    struct.pack_into("<h", a9, 0x04, 0 if thr_zero else rng.randint(-900, 900))
    struct.pack_into("<h", a9, 0x06, rng.choice([-1, 1]) * rng.randint(1, 700))

    for i in range(7):
        for b in (0, 1):
            a8[2 * i + b] = 1 if (gates >> (2 * i + b)) & 1 else 0
    struct.pack_into("<h", a8, 0x0E, 1)

    a3 = struct.pack("<%di" % (A3_LEN // 4), *[_rand_i32(rng) for _ in range(A3_LEN // 4)])
    a4 = struct.pack("<%di" % (A4_LEN // 4), *[_rand_i32(rng) for _ in range(A4_LEN // 4)])
    a5 = struct.pack("<%di" % (A5_LEN // 4), *[_rand_i32(rng) for _ in range(A5_LEN // 4)])
    return Case(name, mode=mode, arg2=arg2, scene=scene, a3=a3, a4=a4, a5=a5,
                a6=a6, a7=a7, a8=a8, a9=a9)


def make_cases() -> list[Case]:
    rng = random.Random(0x102B7440)
    cases: list[Case] = []
    for mode in (0, 1, 2, 3):
        for high in (False, True):
            for alt in (False, True):
                for gates, gname in ((0x3FFF, "all"), (0x0000, "none"),
                                     (0x1555, "even"), (0x2AAA, "odd"),
                                     (0x0003, "rec0")):
                    for neg in (False, True):
                        cases.append(build_case(
                            rng,
                            "mode%d/%s/%s/%s/%sdiv" % (
                                mode, "high" if high else "low",
                                "alt" if alt else "plain", gname,
                                "neg" if neg else "pos"),
                            mode=mode, arg2=rng.choice([0, 1, 2]),
                            high=high, alt=alt, gates=gates, neg_div=neg))
    # edge cases for the scene+0x18 rounding division and its guards
    for i, (thr_zero, aim_low, arg2) in enumerate(
            [(True, False, 1), (True, False, 0), (False, True, 1),
             (False, True, 0), (False, False, 1), (False, False, 0)]):
        cases.append(build_case(rng, "edge%d/round" % i, mode=0, arg2=arg2,
                                high=False, alt=False, gates=0x3FFF,
                                neg_div=True, thr_zero=thr_zero,
                                aim_low=aim_low))
    # a case whose arg6[0x24] / arg6[0x0c] are zero (the two guards at 0x102b7d5c)
    c = build_case(rng, "edge/zeroguard", mode=0, arg2=1, high=False, alt=False,
                   gates=0x3FFF, neg_div=False)
    struct.pack_into("<i", c.a6, 0x24, 0)
    struct.pack_into("<i", c.a6, 0x0C, 0)
    cases.append(c)
    # a case with large magnitudes, to exercise the sign paths of idiv
    c = build_case(rng, "edge/large", mode=2, arg2=1, high=True, alt=True,
                   gates=0x3FFF, neg_div=True)
    for off in range(0, A6_LEN, 4):
        struct.pack_into("<i", c.a6, off, rng.choice([-(1 << 30), 1 << 30, -1, 0, 1]))
    cases.append(c)
    return cases


# ------------------------------------------------------------------- mutations


def _mut_idiv_round():
    orig = V._idiv

    def f(n, d):
        if d == 0:
            raise V.VecPackFault("idiv by zero")
        return int(round(n / d))
    return orig, f


def _mut_idiv_floor():
    orig = V._idiv

    def f(n, d):
        if d == 0:
            raise V.VecPackFault("idiv by zero")
        return n // d
    return orig, f


def _mut_div_unsigned():
    orig = V._i16

    def f(v):
        return v & 0xFFFF
    return orig, f


def _mut_rdiv_trunc():
    orig = V._rdiv_half_away

    def f(n, d):
        return V._idiv(n, d)
    return orig, f


def _mut_bank_divisor():
    orig = V._bank

    def f(scene, arg6, arg7, *, i, b):
        src = 0x120 * i + 0x90 * b
        dst = V.VEC_OFF + 4 * (68 * i + 34 * b)
        div = V._i16(arg7.w(4 * i))  # bank offset 2*b dropped
        for j in range(6):
            scene.setd(dst + 0x00 + 4 * j, V._idiv(arg6.d(src + 0x30 + 4 * j), div))
            scene.setd(dst + 0x18 + 4 * j, arg6.d(src + 0x00 + 4 * j))
            scene.setd(dst + 0x30 + 4 * j, arg6.d(src + 0x18 + 4 * j))
            scene.setd(dst + 0x48 + 4 * j, arg6.d(src + 0x30 + 4 * j))
            scene.setd(dst + 0x60 + 4 * j, arg6.d(src + 0x48 + 4 * j))
        scene.setd(dst + 0x78, arg6.d(src + 0x7C))
        scene.setd(dst + 0x7C, arg6.d(src + 0x80))
        scene.setd(dst + 0x80, arg6.d(src + 0x88))
        scene.setd(dst + 0x84, arg6.d(src + 0x8C))
    return orig, f


def _mut_quad_order():
    orig = V._quad

    def f(scene, arg6, *, slot, src):
        scene.setd(V.VEC_OFF + 4 * (slot + 0), arg6.d(src + 0x00))
        scene.setd(V.VEC_OFF + 4 * (slot + 1), arg6.d(src + 0x0C))  # swapped
        scene.setd(V.VEC_OFF + 4 * (slot + 2), arg6.d(src + 0x04))  # swapped
        scene.setd(V.VEC_OFF + 4 * (slot + 3), arg6.d(src + 0x10))
    return orig, f


MUTATIONS = [
    ("idiv -> round-to-nearest", "_idiv", _mut_idiv_round),
    ("idiv -> floor division", "_idiv", _mut_idiv_floor),
    ("divisor read unsigned (i16 -> u16)", "_i16", _mut_div_unsigned),
    ("scene+0x18 rounding -> plain truncation", "_rdiv_half_away", _mut_rdiv_trunc),
    ("bank divisor ignores the 2*b bank offset", "_bank", _mut_bank_divisor),
    ("quad scalar order +0x04/+0x0c swapped", "_quad", _mut_quad_order),
    ("FORCE_N 0x360 -> 0x361", "FORCE_N", lambda: (V.FORCE_N, 0x361)),
    ("VEC_OFF 0x3c -> 0x40", "VEC_OFF", lambda: (V.VEC_OFF, 0x40)),
]


# --------------------------------------------------- real captured-vector checks

CAPTURES = [
    # the v28 roll that first landed `arg1_big_filled` — docs/74 §90
    Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/live_hooks_20260818-080318.jsonl"),
    # the 39-scene roll used throughout docs/74 §157-§182
    Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/live_hooks_20260819-121153.jsonl"),
]


def _load_capture(path: Path):
    """Pair each ``sba_order_fpo_helper`` ``arg1_big_filled`` with the dumps of
    the ``sba_order_fpo_calc`` call that *contains* it.

    This is nesting inside one call, not the analysis-pass/render-pass ordering
    that docs/74 §161.1/§178.2/§186 warn about: the helper is invoked by the
    calc whose entry dumps immediately precede it in the stream.  The check
    below reports the distinct values seen per slot, so a wrong pairing shows
    up as suspiciously repeating values rather than passing silently.
    """
    pending, pairs = None, []
    for line in path.open(errors="replace"):
        if "sba_order_fpo" not in line:
            continue
        import json
        d = json.loads(line)
        hid = d.get("hook_id")
        if d.get("kind") == "call" and hid == "sba_order_fpo_calc" and d.get("event") == "enter":
            pending = {"sw": [int(x, 16) for x in (d.get("stack_dwords") or [])],
                       "cid": d["call_id"]}
        elif d.get("kind") == "buffer_dump" and pending is not None:
            if hid == "sba_order_fpo_calc" and d.get("readable") and d.get("call_id") == pending["cid"]:
                pending[d["label"]] = bytes.fromhex(d["hex"])
            elif (hid == "sba_order_fpo_helper" and d.get("label") == "arg1_big_filled"
                  and d.get("readable")):
                pairs.append((pending, bytes.fromhex(d["hex"])))
    return pairs


TAIL_SLOTS = (720, 721, 722, 723, 724, 725, 726, 727, 728, 729, 731, 732)


def _bank_divisor_exists(num: list[int], q: list[int], limit: int = 1 << 16) -> bool:
    """Is there ONE integer ``d`` with ``trunc(num[k]/d) == q[k]`` for all six?

    Derived rather than searched: the pair with the largest ``|q|`` pins
    ``|d|`` to the half-open interval ``(|n|/(|q|+1), |n|/|q|]``, which is a
    handful of integers.  Falls back to the whole ``±limit`` range only when
    every quotient is zero (which pins nothing).
    """
    pairs = [(n, y) for n, y in zip(num, q) if y != 0]
    if pairs:
        n, y = max(pairs, key=lambda p: abs(p[1]))
        lo = abs(n) // (abs(y) + 1)
        hi = abs(n) // abs(y) + 1
        mags = range(max(1, lo), min(hi + 2, limit) + 1)
    else:
        mags = range(1, limit + 1)
    for m in mags:
        for d in (m, -m):
            if all(V._idiv(x, d) == y for x, y in zip(num, q)):
                return True
    return False


def capture_checks_all() -> bool:
    ok = True
    ran = False
    for cap in CAPTURES:
        if not cap.exists():
            print("capture cross-checks SKIPPED (%s not present)" % cap.name)
            continue
        ran = True
        ok &= capture_checks(cap)
        print()
    if not ran:
        print("no captures present — the real-data half of this harness did not run")
    return ok


def capture_checks(CAPTURE: Path) -> bool:
    pairs = _load_capture(CAPTURE)
    print("real-capture cross-checks   %s" % CAPTURE.name)
    print("  filled scene buffers      %d" % len(pairs))
    ok = True

    # [A] slots 612..615 must equal four header words of the SAME dumped
    #     buffer.  Two independent regions of one hardware dump, no model.
    n = 0
    for _, scene in pairs:
        want = [struct.unpack_from("<h", scene, o)[0] for o in (0x06, 0x0A, 0x08, 0x0C)]
        got = V.read_vector(scene)[612:616]
        n += want == got
    print("  [A] slots 612..615 == scene words +0x06/+0x0a/+0x08/+0x0c   %d/%d"
          % (n, len(pairs)))
    ok &= n == len(pairs)

    # [B] every non-empty bank must satisfy slots[+0..5] == trunc(slots[+18..23]/d)
    #     for ONE integer d.  This is the layout's sharpest falsifiable claim:
    #     it ties two 6-element runs 18 slots apart through a single divisor.
    tot = good = 0
    for _, scene in pairs:
        v = V.read_vector(scene)
        for i in range(7):
            for b in (0, 1):
                base = 68 * i + 34 * b
                num, q = v[base + 18:base + 24], v[base:base + 6]
                if not any(num) and not any(q):
                    continue
                tot += 1
                if _bank_divisor_exists(num, q):
                    good += 1
    print("  [B] bank +0..5 == trunc(+18..23 / one d)                    %d/%d" % (good, tot))
    ok &= good == tot

    # [C] the fcn.1028b8d0 tail slots, predicted from that call's OWN dumped
    #     arguments and checked against the same call's filled vector.
    hit = {s: 0 for s in TAIL_SLOTS}
    obs = {s: set() for s in TAIL_SLOTS}
    usable = 0
    for p, scene in pairs:
        if not all(k in p for k in ("arg5_big", "arg6_big", "arg2_big")) or len(p["sw"]) < 5:
            continue
        usable += 1
        pred = V.vecpack_tail(arg6=p["arg5_big"], params=p["arg6_big"],
                              flags=p["arg2_big"], flagsword=p["sw"][4])
        vec = struct.unpack_from("<740i", scene, V.VEC_OFF)
        for s in TAIL_SLOTS:
            obs[s].add(vec[s])
            hit[s] += pred[s] == vec[s]
    print("  [C] tail slots 720..732 predicted from the call's own args   %d/%d each"
          % (min(hit.values()), usable))
    for s in TAIL_SLOTS:
        ok &= hit[s] == usable
    const = [s for s in TAIL_SLOTS if len(obs[s]) == 1]
    print("      CAVEAT: %d of the %d tail slots hold ONE value on this roll"
          % (len(const), len(TAIL_SLOTS)))
    print("      %s" % ", ".join("%d=%d" % (s, next(iter(obs[s]))) for s in const))
    print("      so [C] discriminates the source OFFSET, not the whole mapping;")
    print("      a roll that varies them would be a stronger test.")

    # [C-mut] source-offset mutations for the tail, on the same real data
    print("      offset mutations on [C]:")
    for label, kw in (("arg6 word +0x0c -> +0x0e", {"a": 0x0E}),
                      ("params word +0x10e -> +0x110", {"b": 0x110}),
                      ("x10 scale dropped", {"c": 1})):
        diff = 0
        for p, scene in pairs:
            if not all(k in p for k in ("arg5_big", "arg6_big", "arg2_big")):
                continue
            a6, pa = V._Buf(p["arg5_big"]), V._Buf(p["arg6_big"])
            vec = struct.unpack_from("<740i", scene, V.VEC_OFF)
            if "a" in kw:
                diff += V._i16(a6.w(kw["a"])) * 10 != vec[720]
            if "b" in kw:
                diff += V._i16(pa.w(kw["b"])) != vec[728]
            if "c" in kw:
                diff += V._i16(a6.w(0x0C)) * kw["c"] != vec[720]
        print("        %-32s %s (%d/%d frames differ)"
              % (label, "CAUGHT" if diff else "NOT CAUGHT", diff, usable))
        ok &= diff > 0
    return ok


# ------------------------------------------------------------------------ main


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    pe = dll.read_bytes()
    print("DLL   %s" % dll)
    print("md5   %s" % hashlib.md5(pe).hexdigest())
    print("fn    fcn.102b7440  0x102b7440..0x102b81c7  (3457 B, 90 bb, 910 insn)")
    print()

    cases = make_cases()
    refs = []
    bad = 0
    for c in cases:
        want = run_dll(pe, c)
        got = run_port(c)
        refs.append((c, want))
        if want != got:
            bad += 1
            for label, w, g in zip(("scene", "arg6", "arg7"), want, got):
                if w != g:
                    diffs = [i for i in range(len(w)) if w[i] != g[i]]
                    print("  MISMATCH %-38s %s: %d bytes, first @ 0x%x"
                          % (c.name, label, len(diffs), diffs[0]))
    print("cases                    %d" % len(cases))
    print("port == real DLL         %d/%d %s"
          % (len(cases) - bad, len(cases), "bit-exact" if bad == 0 else "FAIL"))
    print()

    # ---- deliberate-mutation self-tests
    print("deliberate-mutation self-tests")
    caught_n = inert_n = missed_n = 0
    for label, attr, factory in MUTATIONS:
        orig, repl = factory()
        setattr(V, attr, repl)
        try:
            n_diff = 0
            for c, want in refs:
                try:
                    if run_port(c) != want:
                        n_diff += 1
                except Exception:
                    n_diff += 1
        finally:
            setattr(V, attr, orig)
        if n_diff:
            caught_n += 1
            print("  CAUGHT       %-42s (%d/%d cases differ)" % (label, n_diff, len(refs)))
        else:
            missed_n += 1
            print("  NOT CAUGHT   %-42s" % label)
    print("  caught %d   provably inert %d   NOT CAUGHT %d"
          % (caught_n, inert_n, missed_n))
    print()

    cap_ok = capture_checks_all()

    ok = bad == 0 and missed_n == 0 and cap_ok
    print("RESULT %s" % ("ALL OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
