#!/usr/bin/env python3
"""Validate a hooks.cfg against the real hook table BEFORE it reaches the box.

WHY
===
A typo in hooks.cfg is silent. An unknown hook id is simply ignored, so
`tlb_framing_line_reduce=on` misspelt means the one row the framing capture
exists for never fires — and you find out after the scan, on hardware that is
irreplaceable and a roll of the owner's film that has already been through the
gate.

This project has lost real hardware round trips to exactly this class of
thing: v22/v24/v26 to a derived offset, v41 to a mid-instruction address, and
§178.1 to a capture that was still uploading. A config checker is cheap.

Checks:
  1. every hook id named in the cfg exists in hookcore_real_table.c;
  2. every `<id>.exit` names a real hook too;
  3. the syntax is one of the four documented forms;
  4. reports which hooks will actually be ENABLED, resolving defaults —
     so "what will this capture record" is answered before the scan, not after.

Usage:
    python3 check_hooks_cfg.py hooks.cfg.framing
    python3 check_hooks_cfg.py hooks.cfg.reference
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / "hookcore_real_table.c"

ROW = re.compile(
    r'\{\s*"(?:PakonIMAu|TLB|TLA|kodakcms)\.dll"\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*"([a-z_0-9]+)"',
)
# The five trailing flags — approximate, wantExitDefault, hotPathDisabled,
# notCallReachable, spare — end the row. They may sit on their own line OR
# share a line with the closing citation string, e.g.
#     "r2 af/axt 2026-08-15", 0, 1, 0, 1, 0 },
# An earlier version of this anchored the match to the start of a line, so
# every row of the second form silently fell back to a (0,1,0,0) DEFAULT —
# and the checker then reported the four notCallReachable hooks, the ones
# that reintroduce the v41 stack-corruption mechanism, as ENABLED. A checker
# that mis-reports which hooks are live is worse than no checker, so this now
# takes the LAST five integers before the row's own closing brace.
FLAGS = re.compile(r'(\d)\s*,\s*(\d)\s*,\s*(\d)\s*,\s*(\d)\s*,\s*(\d)\s*\}\s*,')


def load_table() -> dict[str, dict]:
    src = TABLE.read_text()
    hooks: dict[str, dict] = {}
    starts = [(m.start(), m.group(1), m.group(2)) for m in ROW.finditer(src)]
    for i, (pos, va, hid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(src)
        f = FLAGS.search(src, pos, end)
        if f is None:
            raise SystemExit(
                f"could not parse the trailing flags for hook {hid!r} — "
                f"refusing to guess, because a wrong default here decides "
                f"whether a dangerous hook is reported as live")
        approx, wantexit, hot, notreach = (int(f.group(n)) for n in range(1, 5))
        hooks[hid] = {
            "va": va,
            "approximate": approx,
            "wantExitDefault": wantexit,
            "hotPathDisabled": hot,
            "notCallReachable": notreach,
        }
    return hooks


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    cfg = Path(argv[0])
    if not cfg.is_absolute():
        cfg = HERE / cfg
    if not cfg.is_file():
        print(f"FAIL: no such config: {cfg}")
        return 1

    hooks = load_table()
    print(f"hook table: {len(hooks)} hooks from {TABLE.name}")
    print(f"config:     {cfg.name}\n")

    # Resolve defaults first.
    enabled = {
        h: not (v["approximate"] or v["hotPathDisabled"] or v["notCallReachable"])
        for h, v in hooks.items()
    }
    explicit: set[str] = set()
    fails: list[str] = []
    global_exit: bool | None = None

    for n, raw in enumerate(cfg.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" not in line:
            fails.append(f"line {n}: not `key=value`: {raw.strip()!r}")
            continue
        key, val = (p.strip() for p in line.split("=", 1))
        if val not in ("on", "off"):
            fails.append(f"line {n}: value must be on|off, got {val!r}")
            continue
        if key == "EXIT":
            global_exit = val == "on"
            continue
        base = key[:-5] if key.endswith(".exit") else key
        if base not in hooks:
            fails.append(
                f"line {n}: unknown hook id {base!r} — it will be SILENTLY "
                f"IGNORED on the box, and whatever you wanted it to record "
                f"will not be recorded")
            continue
        if not key.endswith(".exit"):
            enabled[base] = val == "on"
            explicit.add(base)

    on = sorted(h for h, e in enabled.items() if e)
    off = sorted(h for h, e in enabled.items() if not e)

    print(f"WILL RECORD ({len(on)}):")
    for h in on:
        mark = "" if h in explicit else "   (by default, not named in the cfg)"
        print(f"    {h:<28} {hooks[h]['va']}{mark}")
    print(f"\nWILL NOT RECORD ({len(off)}):")
    print("    " + ", ".join(off) if off else "    (none)")
    if global_exit is not None:
        print(f"\nglobal EXIT default: {'on' if global_exit else 'off'}")

    print()
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print("PASS: every hook id in this config exists in the real hook table.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
