#!/usr/bin/env python3
"""Acceptance check for the v46 REFERENCE TRACE, run BEFORE trusting any of it.

WHY THIS FILE IS NOT check_v44.py WITH ROWS ADDED
=================================================
A stale acceptance check has already thrown away a good capture once: check_v41
still required `post_shift_4b6`, a row that was REMOVED when its hook turned out
to sit mid-instruction, so run against a v42/v44 capture it REJECTed for a
reason that had nothing to do with the capture. check_v44 in turn hard-codes two
hooks and would reject v46 for the same shape of reason. This file is specific
to the v46 hook table and dump rows and to nothing else, and it says so in every
message it prints. If you are holding a capture from a different build, do not
run this; write the check for that build.

WHAT v46 IS
===========
The first capture that records the vendor's own state at BOTH ENDS of every
stage boundary on the same frames. Two engine changes make it possible:

  * ExtraDumpSpec.when -- rows can fire on EXIT as well as ENTRY, resolving
    their pointers from an entry-time snapshot held in the shadow-stack frame
    (never by re-reading the live stack, which is destroyed for any `ret N`
    callee by the time OnReturnThunk runs).
  * ExtraDumpSpec.maxDumps -- a per-row call cap, so a hot function can carry
    a big dump for its first N calls. v45 died for want of this: it hung ~96 KB
    of dumps on tlb_lut_apply, which fires 52,877 times.

Both were proven under Wine before this build shipped (selftest.c's
`v46 extra dumps` block: entry/exit content differs as the target mutates its
buffer, both sides report the real buffer address through a `ret 8` callee, and
a BOTH row capped at 6 emits exactly 3 enter + 3 leave).

WHAT IS CHECKED HERE
====================
That each row fired and that its data is SELF-CONSISTENT with data captured
independently elsewhere in the same file -- not that any finding holds. Every
test below is chosen so that a mis-specified stack index fails it loudly rather
than passing on plausible-looking garbage. The strongest ones are the
cross-row identities, because they cannot be satisfied by accident:

  1. lut_dst[i] must be an entry of lut_table, for every pixel.
     Validates THREE indices at once (arg1=dst=0, arg2=src=1, arg4=table=3)
     plus the EXIT mechanism, because the identity is
     `out[i] = table[in[i]]` and only holds if all of them are right.
  2. scene_in[0x4b6:0x4bc] must equal balance_shift_4b6 for the same frame.
     balance_shift_4b6 is an independently derived, already-proven row
     (docs/74 SS105/SS168). A whole-scene dump at a wrong stackIndex cannot
     reproduce it.
  3. The three shift_lut_builder EXIT LUTs must equal clamp(i+shift, 0, 4095)
     with shift read from the SAME call's raw stack_dwords[4..6]. The builder
     is bit-exact against the DLL (SS167.5), so this is an exact identity.
  4. poly_input_r and poly_output_r must report the SAME address and DIFFERENT
     contents. Same address proves the exit snapshot resolved the real pointer;
     different contents prove the dump was taken after the polynomial ran.
  5. No capped row may exceed its cap, and no EXIT-only label may ever appear
     with "event":"enter".

Usage:  python3 check_v46.py <capture.jsonl>
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

SCENE_BYTES = 0x64DC          # 25820; docs/74 SS95's live stride, and the
                              # last dword analyze_auto_tone writes is +0x64d0
SHIFT_OFF = 0x4b6             # the balance shift triple inside the scene

# label -> (expected byte length, expected side). Sizes are exact: a row that
# comes back short means IsBadReadPtr trimmed nothing but the numBytes in the
# table changed, i.e. this check is stale for the build that produced the file.
EXPECT = {
    "scene_in":       (SCENE_BYTES, "enter"),
    "scene_out":      (SCENE_BYTES, "leave"),
    "fugc_scene":     (SCENE_BYTES, None),
    "attr_scene":     (SCENE_BYTES, None),
    "fall_scene":     (SCENE_BYTES, None),
    "tone_scene":     (SCENE_BYTES, None),
    "area_shift_4b6": (6, None),
    "apb_shift_4ac":  (0x40, None),
    "apb_img_desc":   (0x40, None),
    "poly_input_r":   (0x84000, "enter"),
    "poly_output_r":  (0x84000, "leave"),
    "pixel_data":     (0x80000, "enter"),
    "pixel_data_out": (0x80000, "leave"),
    "lut_table":      (0x10000, "enter"),
    "lut_src":        (0x8000, "enter"),
    "lut_dst":        (0x8000, "leave"),
    "slb_lut_a":      (0x2000, "leave"),
    "slb_lut_b":      (0x2000, "leave"),
    "slb_lut_c":      (0x2000, "leave"),
    "r_lut":          (8192, "enter"),
    "g_lut":          (8192, "enter"),
    "b_lut":          (8192, "enter"),
    "balance_shift_4b6": (6, "enter"),
}

# Caps as written in hookcore_real_table.c. A row over its cap means the
# InterlockedIncrement accounting is broken; a row under it is normal (the
# scan simply had fewer calls).
CAPS = {
    "pixel_data": 20, "pixel_data_out": 20,
    "poly_input_r": 12, "poly_output_r": 12,
    "lut_table": 4, "lut_src": 24, "lut_dst": 24,
    "scpw_plane_r": 24, "scpw_plane_g": 24, "scpw_plane_b": 24,
}

# Rows that must NEVER appear on the entry side. Catches a `when` regression.
EXIT_ONLY = {"scene_out", "poly_output_r", "pixel_data_out", "lut_dst",
             "slb_lut_a", "slb_lut_b", "slb_lut_c"}


class Result:
    def __init__(self) -> None:
        self.ok = True
        self.notes: list[str] = []

    def check(self, cond: bool, msg: str, fatal: bool = True) -> bool:
        mark = "ok  " if cond else ("FAIL" if fatal else "warn")
        print(f"    [{mark}] {msg}")
        if not cond and fatal:
            self.ok = False
        return bool(cond)


def load(src: Path):
    """Read the capture once. Returns (dumps, calls).

    dumps: label -> list of dicts (call_id, event, addr, raw bytes)
    calls: hook_id -> list of dicts (call_id, stack_dwords as ints)
    """
    dumps = defaultdict(list)
    calls = defaultdict(list)
    bad = 0
    for line in src.open(errors="replace"):
        if '"hook_id"' not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            bad += 1
            continue
        kind = r.get("kind")
        if kind == "buffer_dump":
            hx = r.get("hex")
            dumps[r.get("label")].append({
                "call_id": r.get("call_id"),
                "event": r.get("event"),
                "addr": r.get("addr"),
                "hook": r.get("hook_id"),
                "readable": r.get("readable"),
                "raw": bytes.fromhex(hx) if isinstance(hx, str) else None,
            })
        elif kind == "call" and r.get("event") == "enter":
            sd = r.get("stack_dwords") or []
            calls[r.get("hook_id")].append({
                "call_id": r.get("call_id"),
                "sd": [int(x, 16) for x in sd if isinstance(x, str)
                       and x.startswith("0x")],
            })
    return dumps, calls, bad


def s16(b: bytes, off: int) -> int:
    v = int.from_bytes(b[off:off + 2], "little")
    return v - 0x10000 if v >= 0x8000 else v


def frame_windows(calls) -> list[tuple[int, int]]:
    """[(lo, hi)) call_id ranges, one per cn_enhanced_driver call.

    call_id is assigned at ENTRY and increases monotonically, so the driver's
    own id is the smallest in its frame and the next driver's id bounds it.
    This is index pairing, which docs/74 SS181.F warns has produced wrong
    conclusions three times -- it is sound HERE only because the driver
    brackets the whole per-frame pass by construction. It is used for
    cross-hook checks only, never to pair a dump with a rendered frame.
    """
    ids = sorted(c["call_id"] for c in calls.get("cn_enhanced_driver", []))
    return [(ids[i], ids[i + 1] if i + 1 < len(ids) else 1 << 62)
            for i in range(len(ids))]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    src = Path(argv[0])
    if not src.is_file():
        print(f"no such capture: {src}")
        return 2

    dumps, calls, bad = load(src)
    R = Result()
    print(f"capture: {src.name}  ({src.stat().st_size / 1e6:.1f} MB)")
    if bad:
        print(f"  {bad} unparseable lines -- a TRUNCATED log is the v45 "
              f"failure mode; check the tail before continuing")

    # ---- 0. is this actually a v46 capture? ------------------------------
    print("\n[0] build identification")
    any_event = any(d.get("event") for lst in dumps.values() for d in lst)
    R.check(any_event,
            'buffer_dump lines carry an "event" field (v46 or later); '
            "without it this is a pre-v46 capture and every EXIT-side test "
            "below is meaningless -- use check_v44.py instead")
    if not any_event:
        print("\nREJECT - wrong build, wrong check. Nothing else was tested.")
        return 1

    # ---- 1. presence, size, and side -------------------------------------
    print("\n[1] rows present, right size, right side of the call")
    for lbl, (nbytes, side) in EXPECT.items():
        rows = [d for d in dumps.get(lbl, []) if d["raw"] is not None]
        if not R.check(bool(rows), f"{lbl:16} present ({len(rows)} dumps)"):
            continue
        sizes = {len(d["raw"]) for d in rows}
        R.check(sizes == {nbytes},
                f"{lbl:16} all dumps are {nbytes} B (saw {sorted(sizes)})")
        if side:
            got = {d["event"] for d in rows}
            R.check(got == {side},
                    f"{lbl:16} fires only on {side!r} (saw {sorted(got)})")
        unread = [d for d in dumps.get(lbl, []) if d.get("readable") is False]
        R.check(not unread,
                f"{lbl:16} no IsBadReadPtr failures ({len(unread)} unreadable)",
                fatal=False)

    print("\n[1b] EXIT-only labels never appear on the entry side")
    for lbl in EXIT_ONLY:
        ev = {d["event"] for d in dumps.get(lbl, [])}
        R.check("enter" not in ev, f"{lbl:16} events = {sorted(ev)}")

    print("\n[1c] no capped row exceeded its cap")
    for lbl, cap in CAPS.items():
        n = len(dumps.get(lbl, []))
        R.check(n <= cap, f"{lbl:16} {n} dumps <= cap {cap}")

    # ---- 2. the scene struct --------------------------------------------
    print("\n[2] the scene: is stack_dwords[1] really the scene base?")
    sin = sorted([d for d in dumps.get("scene_in", []) if d["raw"]],
                 key=lambda d: d["call_id"])
    sout = {d["call_id"]: d for d in dumps.get("scene_out", []) if d["raw"]}
    if sin:
        R.check(len({d["raw"] for d in sin}) > 1,
                f"scene_in differs across frames ({len({d['raw'] for d in sin})}"
                f"/{len(sin)} distinct) -- a constant dump means a wrong pointer")
        paired = [(d, sout[d["call_id"]]) for d in sin if d["call_id"] in sout]
        R.check(len(paired) >= max(1, len(sin) - 1),
                f"scene_out pairs with scene_in by call_id "
                f"({len(paired)}/{len(sin)})")
        changed = sum(1 for a, b in paired if a["raw"] != b["raw"])
        R.check(changed > 0,
                f"the driver CHANGES the scene on {changed}/{len(paired)} "
                f"frames -- zero would mean the exit dump re-read entry state")

        # THE self-check: +0x4b6 against the independently-proven row.
        bs = defaultdict(list)
        for d in dumps.get("balance_shift_4b6", []):
            if d["raw"]:
                bs[d["call_id"]].append(d["raw"])
        wins = frame_windows(calls)
        hits = miss = 0
        for (lo, hi), d in zip(wins, sin):
            here = [v for cid, vs in bs.items() if lo <= cid < hi for v in vs]
            if not here:
                continue
            want = d["raw"][SHIFT_OFF:SHIFT_OFF + 6]
            if any(v == want for v in here):
                hits += 1
            else:
                miss += 1
        R.check(hits > 0 and miss == 0,
                f"scene_in[0x4b6:0x4bc] == balance_shift_4b6 on {hits} frames, "
                f"{miss} disagree  <-- the index self-check")
        if sin:
            t = sin[0]["raw"]
            print(f"    frame 0 shift triple at +0x4b6: "
                  f"{s16(t, SHIFT_OFF)}, {s16(t, SHIFT_OFF+2)}, "
                  f"{s16(t, SHIFT_OFF+4)}")

    # analyze_area was handed scene+0x4b6 directly; 6 bytes must match.
    ash = [d["raw"] for d in dumps.get("area_shift_4b6", []) if d["raw"]]
    if ash and sin:
        allowed = {d["raw"][SHIFT_OFF:SHIFT_OFF + 6] for d in sin}
        R.check(all(v in allowed for v in ash),
                f"analyze_area arg index 3 == scene+0x4b6 "
                f"({sum(v in allowed for v in ash)}/{len(ash)} match a frame)")

    # analyze_post_balance index 2 is scene+0x4ac, so +0x0a is the same triple.
    apb = [d["raw"] for d in dumps.get("apb_shift_4ac", []) if d["raw"]]
    if apb and sin:
        allowed = {d["raw"][SHIFT_OFF:SHIFT_OFF + 6] for d in sin}
        n = sum(1 for v in apb if v[0x0a:0x10] in allowed)
        R.check(n > 0,
                f"analyze_post_balance arg index 2 + 0x0a == scene+0x4b6 "
                f"({n}/{len(apb)}) -- corrects the SS168 apb_arg0/apb_arg1 rows")

    # ---- 3. the inversion ------------------------------------------------
    print("\n[3] tlb_lut_apply: out[i] == table[in[i]]")
    lt = [d["raw"] for d in dumps.get("lut_table", []) if d["raw"]]
    if lt:
        tab = np.frombuffer(lt[0], dtype="<u2")[::2].astype(np.int64)  # stride 4
        R.check(tab.size == 16384, f"table is {tab.size} entries (expect 16384)")
        dec = float((np.diff(tab[1:]) <= 0).mean()) * 100
        R.check(dec > 95, f"monotone decreasing on {dec:.1f}% of steps")
        exp = {1: 14750, 10: 11250, 100: 7750, 1000: 4250}
        agree = sum(1 for k, v in exp.items() if int(tab[k]) == v)
        R.check(agree >= 3, f"decade points match SS170 {exp}: {agree}/4")
        R.check(len({bytes(x) for x in lt}) == 1,
                f"all {len(lt)} table dumps identical (it is built once)")

        srcs = {d["call_id"]: d["raw"] for d in dumps.get("lut_src", []) if d["raw"]}
        dsts = {d["call_id"]: d["raw"] for d in dumps.get("lut_dst", []) if d["raw"]}
        common = sorted(set(srcs) & set(dsts))
        R.check(bool(common),
                f"lut_src and lut_dst pair by call_id ({len(common)} calls)")
        okn = badn = 0
        for cid in common[:8]:
            s = np.frombuffer(srcs[cid], dtype="<u2").astype(np.int64)
            o = np.frombuffer(dsts[cid], dtype="<u2").astype(np.int64)
            m = s < tab.size
            if not m.any():
                continue
            if np.array_equal(o[m], tab[s[m]]):
                okn += 1
            else:
                badn += 1
        R.check(okn > 0 and badn == 0,
                f"out[i] == table[in[i]] exactly on {okn} calls, {badn} "
                f"disagree  <-- validates dst/src/table indices AND the "
                f"EXIT mechanism in one identity")

    # ---- 4. stage 2, in and out in the same buffer ------------------------
    print("\n[4] tlb_polypixel: entry and exit of the same 0x84000 buffer")
    pin = {d["call_id"]: d for d in dumps.get("poly_input_r", []) if d["raw"]}
    pout = {d["call_id"]: d for d in dumps.get("poly_output_r", []) if d["raw"]}
    common = sorted(set(pin) & set(pout))
    if R.check(bool(common), f"paired by call_id on {len(common)} calls"):
        same_addr = sum(1 for c in common if pin[c]["addr"] == pout[c]["addr"])
        R.check(same_addr == len(common),
                f"same address at entry and exit on {same_addr}/{len(common)} "
                f"-- proves the exit dump used the entry-time snapshot, not a "
                f"re-read of a stack this harness had already overwritten")
        diff = sum(1 for c in common if pin[c]["raw"] != pout[c]["raw"])
        R.check(diff == len(common),
                f"contents DIFFER on {diff}/{len(common)} -- the polynomial "
                f"actually ran between the two dumps")

    print("\n[4b] area_image_apply_lut: pixel_data before and after")
    ain = {d["call_id"]: d for d in dumps.get("pixel_data", []) if d["raw"]}
    aout = {d["call_id"]: d for d in dumps.get("pixel_data_out", []) if d["raw"]}
    common = sorted(set(ain) & set(aout))
    if R.check(bool(common), f"paired by call_id on {len(common)} calls"):
        R.check(all(ain[c]["addr"] == aout[c]["addr"] for c in common),
                "same address at entry and exit")
        diff = sum(1 for c in common if ain[c]["raw"] != aout[c]["raw"])
        R.check(diff > 0,
                f"contents differ on {diff}/{len(common)} calls "
                f"(docs/74 SS167.3 found the vendor applied NO lut on any of "
                f"39 frames via balance_area_image, so a zero here is a real "
                f"result about THIS hook, not necessarily a broken row)",
                fatal=False)

    # ---- 5. the shift LUTs, against their own stack args ------------------
    print("\n[5] shift_lut_builder: built LUTs == clamp(i+shift, 0, 4095)")
    slb = {c["call_id"]: c["sd"] for c in calls.get("shift_lut_builder", [])}
    R.check(bool(slb), f"shift_lut_builder fired ({len(slb)} calls)")
    if slb:
        n1000 = sum(1 for sd in slb.values() if len(sd) > 3 and sd[3] == 0x1000)
        R.check(n1000 == len(slb),
                f"stack_dwords[3] == 0x1000 on {n1000}/{len(slb)} calls "
                f"-- the same self-check check_v44.py uses; if this fails the "
                f"index convention changed and nothing below is meaningful")
        idx = np.arange(4096, dtype=np.int64)
        for lbl, argn in (("slb_lut_a", 4), ("slb_lut_b", 5), ("slb_lut_c", 6)):
            good = bad_ = 0
            for d in dumps.get(lbl, []):
                sd = slb.get(d["call_id"])
                if not d["raw"] or not sd or len(sd) <= argn:
                    continue
                sh = sd[argn] & 0xFFFF
                sh -= 0x10000 if sh >= 0x8000 else 0
                got = np.frombuffer(d["raw"], dtype="<i2").astype(np.int64)
                if np.array_equal(got, np.clip(idx + sh, 0, 4095)):
                    good += 1
                else:
                    bad_ += 1
            R.check(good > 0 and bad_ == 0,
                    f"{lbl} == clamp(i + stack_dwords[{argn}], 0, 4095) on "
                    f"{good} calls, {bad_} disagree")

    # ---- 6. per-frame coverage summary -----------------------------------
    print("\n[6] coverage")
    nframes = len(calls.get("cn_enhanced_driver", []))
    print(f"    frames (cn_enhanced_driver calls): {nframes}")
    for lbl in ("scene_in", "tone_scene", "fugc_scene", "fall_scene",
                "attr_scene", "poly_input_r", "pixel_data", "lut_src"):
        print(f"    {lbl:16} {len(dumps.get(lbl, [])):5} dumps")
    R.check(nframes > 0, "at least one frame was captured")

    print(f"\n{'ACCEPT' if R.ok else 'REJECT'} - "
          f"{'usable as a reference trace' if R.ok else 'inspect before analysing'}")
    print("Reminder: this check is specific to the v46 hook table and dump "
          "rows. A REJECT from a stale check has already cost this project a "
          "good scan once (check_v41 vs the v42 capture) -- confirm the build "
          "before concluding the capture is bad.")
    return 0 if R.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
