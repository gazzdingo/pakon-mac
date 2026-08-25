#!/usr/bin/env python3
"""Golden **whole** ``fcn.102b7440`` vs the real PakonIMAu.dll (Unicorn).

`PakonIMAu.dll` md5 ``eea9dcf78ee21d4f7c515a6c2512242d``, PE base
``0x10000000``.

What is being executed
----------------------

`fcn.102b7440` is called at its own entry (`0x102b7440`), with its own ten
cdecl arguments, and left to run to its own ``ret``.  It is a *pure* leaf
(r2 ``afi``: ``is-pure: true``; three exits at ``0x102b7d81`` /
``0x102b807b`` / ``0x102b81c6``, all with the same ``add esp, 0x34``
epilogue), so there is nothing to stub — no imports, no callees, no
globals.  That is why it can be run whole without inventing anything.

The comparison is over **every byte the vendor writes into the SBA
object**, not a summary: the harness fills the object with a byte-level
poison pattern, runs the DLL, runs `pakon_sba_stats.sba_stats_pack` on a
byte-identical copy of the same inputs, and diffs the two objects
``memcmp``-style over the whole ``0x3c … 0xbbc`` vector plus the header
word at ``+0x18``.  A store the port misses shows up as surviving poison
on one side; a store it makes and the vendor does not shows up the same
way with the sides swapped.  It also diffs the two *scratch* buffers the
vendor mutates in place (``acc``, ``cnt``), which is where the
``0x102b7542`` mirror and the ``0x102b75e7`` count seeding live — those
are invisible in the object and were the reason for adding them.

Where the inputs come from — and the honest caveat
--------------------------------------------------

The v28 capture that carries a real ``in[]`` vector
(`live_hooks_20260818-080318.jsonl`, docs/74 §90.1) is **not on this
machine**, and no capture in hand hooks `fcn.102aece0` or `fcn.102b7440`.
So the inputs here are *not* real captured data: they are pseudo-random
``int32``/``int16`` fills over the exact buffer extents and with the
exact structural constraints the disassembly requires (non-zero
divisors, the ``0..6`` zone enables, the ``+0xe`` long-side words).

Per CLAUDE.md's hierarchy that makes this **tier 1 for equivalence and
not for provenance**: the vendor's own bytes execute and the port matches
them bit-exactly over a large randomised domain, which settles "does this
arithmetic match"; it does not settle "are these the values a real frame
produces".  Stated plainly rather than blurred: this harness proves the
port, not the input model.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 -m pakon_sba_stats_golden [dll]``
"""
from __future__ import annotations

import copy
import hashlib
import random
import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EIP, UC_X86_REG_ESP

from pakon_sba_stats import sba_stats_pack

IMAGE_BASE = 0x10000000
ENTRY = 0x102B7440

STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x00100000
HEAP_ADDR = 0x0C000000
HEAP_SIZE = 0x00100000
RET_MAGIC = 0x0DEAD000

DEFAULT_DLL = (
    Path(__file__).resolve().parents[3]
    / "tools/re/live_hooks/wine_host/PakonIMAu.dll"
)
EXPECT_MD5 = "eea9dcf78ee21d4f7c515a6c2512242d"

# Buffer extents, from the largest displacement each base is used with.
OBJ_SIZE = 0x1000  # writes reach +0xb78; +0xc20 mask lives beyond
ACC_SIZE = 0x0A40  # reads reach acc+0xa1c
CNT_SIZE = 0x0040  # words at +0x00..+0x22
EN_SIZE = 0x0020  # bytes at 2z / 2z+1 for z<7, word at +0x0e
PAR_SIZE = 0x0060  # words at +0x00..+0x06 and +0x0e

POISON = 0xA5

VECTOR_LO = 0x3C
VECTOR_HI = 0xBBC  # index 720 begins here; fcn.1028b8d0 owns 720..732


def _align_up(n: int, page: int = 0x1000) -> int:
    return (n + page - 1) & ~(page - 1)


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


# --- input construction ------------------------------------------------


class Case:
    """One set of the ten arguments, as plain Python buffers."""

    def __init__(self, name: str, seed: int, *, mode1: int, mode2: int,
                 long_side: bool, cnt20_zero: bool, enables: list[int],
                 en_word_e: int):
        rng = random.Random(seed)
        self.name = name
        self.mode1 = mode1
        self.mode2 = mode2

        self.blk75 = [rng.randint(-1 << 20, 1 << 20) for _ in range(75)]
        self.blk19 = [rng.randint(-1 << 20, 1 << 20) for _ in range(19)]
        self.blk9 = [rng.randint(-1 << 20, 1 << 20) for _ in range(9)]

        self.acc = bytearray(
            struct.pack("<%di" % (ACC_SIZE // 4),
                        *[rng.randint(-1 << 22, 1 << 22)
                          for _ in range(ACC_SIZE // 4)])
        )

        # counts: never zero (the vendor divides by them unguarded)
        cnt = bytearray(CNT_SIZE)
        for w in range(CNT_SIZE // 2):
            v = rng.choice([-1, 1]) * rng.randint(1, 900)
            struct.pack_into("<h", cnt, 2 * w, v)
        if cnt20_zero:
            struct.pack_into("<H", cnt, 0x20, 0)
        else:
            struct.pack_into("<h", cnt, 0x20, rng.randint(1, 900))
        self.cnt = cnt

        en = bytearray(EN_SIZE)
        for z in range(7):
            en[2 * z] = enables[2 * z]
            en[2 * z + 1] = enables[2 * z + 1]
        struct.pack_into("<H", en, 0x0E, en_word_e)
        self.en = en

        par = bytearray(PAR_SIZE)
        for w in range(PAR_SIZE // 2):
            struct.pack_into("<h", par, 2 * w, rng.randint(-2000, 2000))
        self.par = par

        # obj: poison everywhere, then plant the five header words the
        # prologue reads (0x102b7443..0x102b7477).
        obj = bytearray([POISON]) * OBJ_SIZE
        # ``long_side="eq"`` puts obj+0x06 exactly on par+0x0e, the
        # boundary of the 0x102b751a / 0x102b77cc signed compares.  Without
        # it a ``>`` -> ``>=`` mutation is invisible (see section [4]).
        hdr_long = 100 if long_side == "eq" else (4000 if long_side else 1)
        struct.pack_into("<H", obj, 0x06, hdr_long)
        struct.pack_into("<h", obj, 0x08, rng.choice([-1, 1]) * rng.randint(1, 900))
        struct.pack_into("<h", obj, 0x0A, rng.randint(-3000, 3000))
        struct.pack_into("<h", obj, 0x0C, rng.randint(-3000, 3000))
        struct.pack_into("<h", obj, 0x16, rng.randint(-3000, 3000))
        # par+0x0e is the long-side threshold the prologue compares to
        struct.pack_into("<h", par, 0x0E, 100)
        self.obj = obj

    def clone(self) -> "Case":
        return copy.deepcopy(self)


def _default_enables() -> list[int]:
    return [1] * 14


CASES: list[Case] = [
    Case("A/long/cnt20!=0/all-zones", 1, mode1=0, mode2=0, long_side=True,
         cnt20_zero=False, enables=_default_enables(), en_word_e=1),
    Case("A/long/cnt20==0/all-zones", 2, mode1=0, mode2=1, long_side=True,
         cnt20_zero=True, enables=_default_enables(), en_word_e=1),
    Case("A/short/all-zones", 3, mode1=0, mode2=0, long_side=False,
         cnt20_zero=False, enables=_default_enables(), en_word_e=1),
    Case("A/long/en[0x0e]==0", 4, mode1=2, mode2=1, long_side=True,
         cnt20_zero=False, enables=_default_enables(), en_word_e=0),
    Case("A/short/sparse zones", 5, mode1=8, mode2=0, long_side=False,
         cnt20_zero=False,
         enables=[1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 1, 1, 1], en_word_e=1),
    Case("B/long/cnt20!=0", 6, mode1=1, mode2=0, long_side=True,
         cnt20_zero=False, enables=_default_enables(), en_word_e=1),
    Case("B/long/cnt20==0", 7, mode1=1, mode2=1, long_side=True,
         cnt20_zero=True, enables=_default_enables(), en_word_e=1),
    Case("B/short", 8, mode1=1, mode2=0, long_side=False,
         cnt20_zero=False, enables=_default_enables(), en_word_e=1),
    Case("B/en[0x0e]==0", 9, mode1=1, mode2=0, long_side=True,
         cnt20_zero=False, enables=_default_enables(), en_word_e=0),
    Case("A/short/no zones enabled", 10, mode1=4, mode2=1, long_side=False,
         cnt20_zero=False, enables=[0] * 14, en_word_e=1),
    # the two boundary cases: obj+0x06 == par+0x0e exactly
    Case("A/EQ boundary", 51, mode1=0, mode2=0, long_side="eq",
         cnt20_zero=False, enables=_default_enables(), en_word_e=1),
    Case("B/EQ boundary", 52, mode1=1, mode2=1, long_side="eq",
         cnt20_zero=True, enables=_default_enables(), en_word_e=1),
]
# a broad randomised sweep on top of the hand-picked structural cases
for _s in range(11, 51):
    _rng = random.Random(_s * 7919)
    CASES.append(
        Case(
            "sweep/%d" % _s,
            _s,
            mode1=_rng.choice([0, 1, 2, 4, 8]),
            mode2=_rng.choice([0, 1, 2]),
            long_side=bool(_rng.getrandbits(1)),
            cnt20_zero=bool(_rng.getrandbits(1)),
            enables=[_rng.getrandbits(1) for _ in range(14)],
            en_word_e=_rng.choice([0, 1, 1, 1]),
        )
    )


# --- the DLL run -------------------------------------------------------


def run_dll(pe: bytes, case: Case) -> tuple[bytes, bytes, bytes]:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)

    p_blk75 = HEAP_ADDR + 0x0000
    p_blk19 = HEAP_ADDR + 0x0200
    p_blk9 = HEAP_ADDR + 0x0300
    p_acc = HEAP_ADDR + 0x1000
    p_cnt = HEAP_ADDR + 0x2000
    p_en = HEAP_ADDR + 0x2100
    p_par = HEAP_ADDR + 0x2200
    p_obj = HEAP_ADDR + 0x4000

    uc.mem_write(p_blk75, struct.pack("<75i", *case.blk75))
    uc.mem_write(p_blk19, struct.pack("<19i", *case.blk19))
    uc.mem_write(p_blk9, struct.pack("<9i", *case.blk9))
    uc.mem_write(p_acc, bytes(case.acc))
    uc.mem_write(p_cnt, bytes(case.cnt))
    uc.mem_write(p_en, bytes(case.en))
    uc.mem_write(p_par, bytes(case.par))
    uc.mem_write(p_obj, bytes(case.obj))

    args = [
        case.mode1, case.mode2, p_blk75, p_blk19, p_blk9,
        p_acc, p_cnt, p_en, p_par, p_obj,
    ]
    esp = STACK_ADDR + STACK_SIZE - 0x2000
    esp -= 4 * len(args)
    for i, a in enumerate(args):
        uc.mem_write(esp + 4 * i, struct.pack("<I", a & 0xFFFFFFFF))
    esp -= 4
    uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EIP, ENTRY)

    try:
        uc.emu_start(ENTRY, RET_MAGIC, count=20_000_000)
    except UcError as exc:
        raise RuntimeError(
            "%s: DLL faulted at eip=0x%08x: %s"
            % (case.name, uc.reg_read(UC_X86_REG_EIP), exc)
        ) from exc

    return (
        bytes(uc.mem_read(p_obj, OBJ_SIZE)),
        bytes(uc.mem_read(p_acc, ACC_SIZE)),
        bytes(uc.mem_read(p_cnt, CNT_SIZE)),
    )


def run_port(case: Case) -> tuple[bytes, bytes, bytes]:
    obj = bytearray(case.obj)
    acc = bytearray(case.acc)
    cnt = bytearray(case.cnt)
    sba_stats_pack(
        obj,
        mode1=case.mode1,
        mode2=case.mode2,
        blk75=case.blk75,
        blk19=case.blk19,
        blk9=case.blk9,
        acc=acc,
        cnt=cnt,
        en=case.en,
        par=case.par,
    )
    return bytes(obj), bytes(acc), bytes(cnt)


def _diff(a: bytes, b: bytes, lo: int, hi: int) -> list[int]:
    return [i for i in range(lo, hi) if a[i] != b[i]]


def compare(case: Case, pe: bytes) -> tuple[bool, str, int]:
    d_obj, d_acc, d_cnt = run_dll(pe, case)
    p_obj, p_acc, p_cnt = run_port(case)

    bad = []
    bad += [("obj+0x%03x" % i) for i in _diff(d_obj, p_obj, VECTOR_LO, VECTOR_HI)]
    bad += [("obj+0x%03x" % i) for i in _diff(d_obj, p_obj, 0x18, 0x1A)]
    bad += [("acc+0x%03x" % i) for i in _diff(d_acc, p_acc, 0, ACC_SIZE)]
    bad += [("cnt+0x%03x" % i) for i in _diff(d_cnt, p_cnt, 0, CNT_SIZE)]

    # how much of the vector the vendor actually touched (poison survivors
    # are slots neither side wrote, and must not be counted as "agreed")
    touched = sum(
        1 for i in range(VECTOR_LO, VECTOR_HI, 4)
        if d_obj[i:i + 4] != bytes([POISON]) * 4
    )
    if bad:
        return False, "%d byte(s) differ, first: %s" % (len(bad), ", ".join(bad[:6])), touched
    return True, "", touched


# --- [4] deliberate-mutation self-tests --------------------------------
#
# Each entry rewrites the *source* of ``pakon_sba_stats`` — not a wrapper
# around it — execs the mutant, and re-runs the same comparison.  A
# mutation the harness does not catch means the comparison is too weak,
# and is reported as NOT CAUGHT rather than quietly dropped.
#
# ``inert`` marks a mutation that is provably a no-op, with the reason;
# those are expected to survive and are not failures.

MUTATIONS: list[tuple[str, list[tuple[str, str]], str]] = [
    ("idiv -> floor division (truncation lost)",
     [("    q = abs(num) // abs(den)\n"
       "    if (num < 0) != (den < 0):\n"
       "        q = -q\n",
       "    q = num // den\n")], ""),
    ("_pack_block rows +0x18 and +0x30 transposed",
     [("        obj.set_i32(d + 0x18, acc.i32(p - 0x18))\n"
       "        obj.set_i32(d + 0x30, acc.i32(p))\n",
       "        obj.set_i32(d + 0x30, acc.i32(p - 0x18))\n"
       "        obj.set_i32(d + 0x18, acc.i32(p))\n")], ""),
    ("zone stride 0x110 -> 0x108",
     [("ZONE_STRIDE_OBJ = 0x110", "ZONE_STRIDE_OBJ = 0x108")], ""),
    ("_extras sources +0x04 and +0x0C transposed",
     [("    obj.set_i32(dst + 0x08, acc.i32(src + 0x0C))\n"
       "    obj.set_i32(dst + 0x04, acc.i32(src + 0x04))\n",
       "    obj.set_i32(dst + 0x08, acc.i32(src + 0x04))\n"
       "    obj.set_i32(dst + 0x04, acc.i32(src + 0x0C))\n")], ""),
    ("acc[0x7e0..] mirror loop dropped (0x102b7542)",
     [("            for k in range(18):\n"
       "                a.set_i32(0x7E0 + 4 * k, a.i32(4 * k))\n",
       "            pass\n")], ""),
    ("cnt[0x1c..0x22] seeding dropped (0x102b75e7)",
     [("            c.set_u16(0x1C, 0x360)\n"
       "            c.set_u16(0x1E, 0x360)\n"
       "            c.set_u16(0x20, c.u16(0x0A))\n"
       "            c.set_u16(0x22, c.u16(0x0A))\n",
       "            pass\n")], ""),
    ("long-side test > becomes >=",
     [("_i16(var_10) > p.i16(0x0E)", "_i16(var_10) >= p.i16(0x0E)")], ""),
    ("obj+0x18 round-half-away replaced by truncation",
     [("            if (num < 0) == (d1 < 0):\n"
       "                num2 = _i32(num + half)\n"
       "            else:\n"
       "                num2 = _i32(num - half)\n",
       "            num2 = num\n")], ""),
    ("branch-B early return at 0x102b8063 removed",
     [("                    o.set_i32(0x9CC, _i16(var_10))\n"
       "                    obj[:] = o.b\n"
       "                    return obj\n",
       "                    pass\n")], ""),
    ("group-0 divisor cnt[4z] -> cnt[2z]",
     [("c.i16(4 * z))", "c.i16(2 * z))")], ""),
    ("the two acc zero-guards reordered",
     [("    if a.i32(0x24) == 0:\n"
       "        a.set_i32(0x24, 1)\n"
       "    if a.i32(0x0C) == 0:\n"
       "        a.set_i32(0x0C, 1)\n",
       "    if a.i32(0x0C) == 0:\n"
       "        a.set_i32(0x0C, 1)\n"
       "    if a.i32(0x24) == 0:\n"
       "        a.set_i32(0x24, 1)\n")],
     "0x24 and 0x0c are distinct offsets with no data dependency; "
     "0x102b7d5c/0x102b7d66 are independent guards"),
]


def _mutant_pack(src: str, subs: list[tuple[str, str]]):
    for old, new in subs:
        if old not in src:
            raise AssertionError("mutation anchor not found: %r" % old[:60])
        src = src.replace(old, new)
    ns: dict = {"__name__": "pakon_sba_stats_mutant"}
    exec(compile(src, "<mutant>", "exec"), ns)
    return ns["sba_stats_pack"]


def run_mutations(pe: bytes) -> int:
    src = (Path(__file__).resolve().parent / "pakon_sba_stats.py").read_text()
    # cache the vendor side once per case
    vendor = {c.name: run_dll(pe, c) for c in CASES}

    print("[4] deliberate-mutation self-tests")
    print()
    bad = 0
    for name, subs, inert_reason in MUTATIONS:
        fn = _mutant_pack(src, subs)
        caught_on = []
        for case in CASES:
            d_obj, d_acc, d_cnt = vendor[case.name]
            obj = bytearray(case.obj)
            acc = bytearray(case.acc)
            cnt = bytearray(case.cnt)
            try:
                fn(obj, mode1=case.mode1, mode2=case.mode2,
                   blk75=case.blk75, blk19=case.blk19, blk9=case.blk9,
                   acc=acc, cnt=cnt, en=case.en, par=case.par)
            except Exception:
                caught_on.append(case.name)
                continue
            if (_diff(d_obj, bytes(obj), VECTOR_LO, VECTOR_HI)
                    or _diff(d_obj, bytes(obj), 0x18, 0x1A)
                    or _diff(d_acc, bytes(acc), 0, ACC_SIZE)
                    or _diff(d_cnt, bytes(cnt), 0, CNT_SIZE)):
                caught_on.append(case.name)
        if caught_on:
            verdict = "caught" if not inert_reason else "CAUGHT (expected inert!)"
            if inert_reason:
                bad += 1
            print("  %-22s %-46s  %d/%d cases"
                  % (verdict, name, len(caught_on), len(CASES)))
        elif inert_reason:
            print("  %-22s %-46s  %s"
                  % ("provably inert", name, inert_reason))
        else:
            bad += 1
            print("  %-22s %-46s  <-- comparison too weak"
                  % ("NOT CAUGHT", name))
    print()
    return bad


# --- [5] independent-port cross-check ----------------------------------
#
# `fcn.102b7440` was ported twice, independently and concurrently:
# `pakon_sba_stats.sba_stats_pack` (this harness's subject) and
# `pakon_orderfpo_vecpack.vecpack`.  Neither was written with sight of
# the other.  Two separate readings of the same 910 instructions agreeing
# byte-for-byte is worth keeping as a standing check, so it runs here.


def cross_check() -> int:
    try:
        from pakon_orderfpo_vecpack import VecPackFault, vecpack
    except ImportError:
        print("[5] independent-port cross-check: pakon_orderfpo_vecpack "
              "not present, skipped")
        return 0

    agree = 0
    bad_names = []
    for c in CASES:
        o1 = bytearray(c.obj)
        a1 = bytearray(c.acc)
        n1 = bytearray(c.cnt)
        sba_stats_pack(o1, mode1=c.mode1, mode2=c.mode2, blk75=c.blk75,
                       blk19=c.blk19, blk9=c.blk9, acc=a1, cnt=n1,
                       en=c.en, par=c.par)
        try:
            o2, a2, n2 = vecpack(
                bytearray(c.obj), mode=c.mode1, arg2=c.mode2,
                arg3=struct.pack("<75i", *c.blk75),
                arg4=struct.pack("<19i", *c.blk19),
                arg5=struct.pack("<9i", *c.blk9),
                arg6=bytearray(c.acc), arg7=bytearray(c.cnt),
                arg8=c.en, arg9=c.par,
            )
        except VecPackFault:
            bad_names.append(c.name + " (VecPackFault)")
            continue
        if (_diff(bytes(o1), bytes(o2), VECTOR_LO, VECTOR_HI)
                or _diff(bytes(o1), bytes(o2), 0x18, 0x1A)
                or _diff(bytes(a1), bytes(a2), 0, ACC_SIZE)
                or _diff(bytes(n1), bytes(n2), 0, CNT_SIZE)):
            bad_names.append(c.name)
        else:
            agree += 1
    print("[5] independent-port cross-check vs pakon_orderfpo_vecpack: "
          "%d/%d cases agree byte-for-byte" % (agree, len(CASES)))
    for n in bad_names[:5]:
        print("      DISAGREE  %s" % n)
    return len(bad_names)


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    pe = dll_path.read_bytes()
    md5 = hashlib.md5(pe).hexdigest()
    print("DLL   : %s" % dll_path)
    print("md5   : %s%s" % (md5, "" if md5 == EXPECT_MD5 else "  *** UNEXPECTED ***"))
    print("entry : fcn.102b7440 (whole function, own ret)")
    print()

    ok_n = 0
    total_touched = 0
    for case in CASES:
        ok, why, touched = compare(case, pe)
        total_touched += touched
        if ok:
            ok_n += 1
            print("  PASS  %-28s  %4d vendor-written dwords" % (case.name, touched))
        else:
            print("  FAIL  %-28s  %s" % (case.name, why))
    print()
    print("%d/%d cases bit-exact; %d compared vendor-written dwords in total"
          % (ok_n, len(CASES), total_touched))
    print()
    bad = run_mutations(pe)
    if bad:
        print("%d mutation(s) unaccounted for" % bad)
    bad += cross_check()
    return 0 if (ok_n == len(CASES) and bad == 0) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
