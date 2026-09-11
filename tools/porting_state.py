#!/usr/bin/env python3
"""The porting-state ledger: every ``_PORTED`` flag in the tree, and its value.

WHY THIS EXISTS
===============
This project's central claim is per-function bit-exactness against the real
vendor DLLs, and the ``*_PORTED`` flags are where each module records whether it
has actually earned that claim. Until now that state was scattered across ~20
modules and recounted from memory in docs and summaries, which is exactly how a
stale claim survives — docs/74 §182.1 found CLAUDE.md asserting the wrong render
engine was the default, and §173.2 found an "exact to rounding" claim that was
only 86.8 % exact.

So the state is generated, not narrated. Run this and paste the output; do not
hand-maintain a list.

A flag being False is NOT automatically a defect. Three distinct meanings, and
the ledger keeps them apart because conflating them overstates the problem:

  * **stand-in**      something substitutes silently — a real gap in a render
  * **raise-guard**   the code raises if that path is reached, so a live render
                      cannot be quietly wrong through it
  * **unreachable**   the branch cannot execute with the shipped config
                      (e.g. flesh's Bayesian path: useAdvanced = 0)
  * **boundary**      not our code at all — the value arrives from elsewhere

Usage:
    python3 tools/porting_state.py            # human-readable
    python3 tools/porting_state.py --md       # markdown, for pasting into docs
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = [ROOT / "tools", ROOT / "tools" / "ansel" / "python-pipeline"]

FLAG_RE = re.compile(r"^([A-Z][A-Z0-9_]*_PORTED)\s*(?::\s*bool\s*)?=\s*(True|False)",
                     re.M)

#: Why a False flag is False, where that has been established. Keyed by flag.
#: Anything absent is reported as "unclassified" rather than assumed benign.
WHY = {
    "F135_INVERT_PORTED":
        ("superseded", "vendor's own inversion recovered (docs/74 §170) and "
                       "wired as PAKON_VENDOR_INVERT; opt-in, not default"),
    # FLESH_DETECTOR_PORTED and FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED were
    # both False here ("assembly" / "unproven").  Both are now True:
    # pakon_flesh_whole_golden.py runs fcn.10270280 as ONE function, and the
    # loader (fcn.101c84f0) plus the vendor's own DPI dump (fcn.1026f5a0)
    # both name P+0x38/+0x3c/+0x40 as l/s/t.
    "FLESH_ANALYSIS_IMAGE_PORTED":
        ("boundary", "arg3/arg4 are not built in the flesh block; §187 showed "
                     "they are the same pointer, from copyToIemImage"),
    "FLESH_ADVANCED_PATH_PORTED":
        ("unreachable", "useAdvanced = 0 in the shipped DPI"),
    "FLESH_3DLUT_PATH_PORTED":
        ("unreachable", "oneDTable = 1 in the shipped DPI"),
    "FRAMING_PORTED":
        ("stand-in", "the whole vendor chain IS bit-exact now — 16 functions "
                     "up to and including fcn.100072c0 (the entry, threshold "
                     "search included) and fcn.100079c0 (the roll caller), "
                     "1500 golden checks. UPDATED 2026-08-21: the vendor's own "
                     "8-bit per-line RGB summary IS now captured (docs/74 "
                     "§198) and the port returns the same 6 frames and the "
                     "same warning word as the vendor on it. Two things still "
                     "hold the flag False, and neither is arithmetic: "
                     "find_frames does not call the cascade (still Otsu), and "
                     "the vendor's frame POSITIONS are unconfirmed — the entry "
                     "writes its list into the caller's buffer, which that "
                     "capture did not dump. A v49 row dumps it"),
    "TONEHELPER_ACQUIRE_IMAGE_PORTED":
        ("raise-guard", "_unported() raises if reached"),
    "PFD_ANALYZE_PORTED":
        ("raise-guard", "_unported() raises if reached"),
    "F135_REVERSAL_PORTED":
        ("raise-guard", "guarded in pakon_decode.py:902"),
    "SCP_LUT_BALANCE_PORTED":
        ("raise-guard", "asserted False in its own golden"),
    "SBA_CORE_PORTED":
        ("superseded", "preference_full is ported bit-exact (§182.2); this "
                       "flag predates it and nothing branches on it"),
    "ANALYSE_ROLL_PORTED":
        ("doc-only", "nothing branches on it; module states it carries no "
                     "balance, FPO or Preference maths"),
    "AST_DPI_PORTED":
        ("doc-only", "nothing branches on it"),
    "AST_EXPORT_PORTED":
        ("doc-only", "nothing branches on it"),
    "CONTRAST_SELECT_DPI_TREE_PORTED":
        ("doc-only", "modelled as a host-side registry, as the Python does"),
    "FILM_BASE_WINDOW_PORTED":
        ("doc-only", "nothing branches on it"),
    "SRA_MAKE_LUTS_PORTED":
        ("doc-only", "makeSRALUTS @ 0x10594b78; the SRA forward table is no "
                     "longer applied at all (docs/58 §16)"),
    "TONEHELPER_IMAGE_HISTOGRAM_PORTED":
        ("doc-only", "nothing branches on it"),
    "CITRAS_APPLY_VALIDATE_PORTED":
        ("doc-only", "printed only, never branched on"),
    "CCD_DESKEW_PORTED":
        ("measured", "deskew is measured here rather than read from a vendor "
                     "table; nothing branches on it"),
    "FUGC_EXPORT_PORTED":
        ("doc-only", "unused"),
    "SHASTA_TWO_ANCHOR_PORTED":
        ("superseded", "the two-anchor stand-in is replaced by "
                       "real_auto_tone; unused"),
    "AUTO_TONE_PORTED":
        ("test-only", "set False inside measure_python_autotone.py"),
}


def collect() -> dict[str, list[tuple[str, bool, int]]]:
    seen: dict[str, list[tuple[str, bool, int]]] = {}
    for d in SCAN:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.py")):
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            for m in FLAG_RE.finditer(text):
                line = text[:m.start()].count("\n") + 1
                rel = f.relative_to(ROOT).as_posix()
                seen.setdefault(m.group(1), []).append(
                    (rel, m.group(2) == "True", line))
    return seen


def main(argv: list[str]) -> int:
    md = "--md" in argv
    flags = collect()
    true = {k: v for k, v in flags.items() if any(t for _, t, _ in v)}
    false = {k: v for k, v in flags.items() if not any(t for _, t, _ in v)}

    if md:
        print(f"| flag | state | why |")
        print(f"|---|---|---|")
        for k in sorted(true):
            print(f"| `{k}` | **True** | bit-exact |")
        for k in sorted(false):
            kind, why = WHY.get(k, ("unclassified", "not yet classified"))
            print(f"| `{k}` | False &mdash; {kind} | {why} |")
        return 0

    print(f"PORTING STATE — {len(flags)} flags across "
          f"{len({p for v in flags.values() for p, _, _ in v})} modules\n")
    print(f"TRUE ({len(true)}) — verified bit-exact against the vendor DLL")
    for k in sorted(true):
        print(f"   {k}")
    print(f"\nFALSE ({len(false)}) — grouped by WHY, because 'False' alone "
          f"overstates the problem")
    by_kind: dict[str, list[str]] = {}
    for k in false:
        kind = WHY.get(k, ("unclassified", ""))[0]
        by_kind.setdefault(kind, []).append(k)
    order = ["stand-in", "assembly", "unproven", "raise-guard", "unreachable",
             "boundary", "doc-only", "measured", "superseded", "test-only",
             "unclassified"]
    for kind in order:
        if kind not in by_kind:
            continue
        print(f"\n  [{kind}]")
        for k in sorted(by_kind[kind]):
            print(f"     {k}")
            print(f"       {WHY.get(k, ('', 'not yet classified'))[1]}")
    extra = set(by_kind) - set(order)
    for kind in sorted(extra):
        print(f"\n  [{kind}]  {sorted(by_kind[kind])}")

    print(f"\nOnly [stand-in], [assembly] and [unproven] are gaps that can "
          f"affect a render.")
    print(f"[raise-guard] fails loudly rather than substituting; "
          f"[unreachable] cannot execute with the shipped config;")
    print(f"[boundary] is not this port's code; [superseded] has been "
          f"replaced by a verified path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
