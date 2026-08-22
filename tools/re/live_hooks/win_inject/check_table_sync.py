#!/usr/bin/env python3
"""Mechanically verify that hookcore_real_table.c's 23-hook table is the
*same* (dll, va, id) list as ../agent.js's HOOKS array, in the same order.

Why this exists: the task this harness was built for required reusing
agent.js's exact address list "don't re-derive from scratch" -- this script
makes that a checked fact instead of an assertion in a comment. Run it any
time either file is edited:

    python3 tools/re/live_hooks/win_inject/check_table_sync.py

Exit code 0 and "OK" printed means every (dll, va, id) triple in
hookcore_real_table.c appears in agent.js's HOOKS array, at the same index,
with the same values. Any mismatch is printed and the script exits 1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_JS = HERE.parent / "agent.js"
TABLE_C = HERE / "hookcore_real_table.c"
HEADER_H = HERE / "hookcore.h"


def parse_agent_js(text: str) -> list[tuple[str, int, str]]:
    """Extract (dll, va, id) triples from agent.js's HOOKS array, in order."""
    # Each hook entry has `dll: 'X.dll', va: 0x....,` then later `id: 'y',`
    # within the same object literal. Scan block-by-block between `{` `}`
    # inside the HOOKS = [ ... ]; array.
    start = text.index("const HOOKS = [")
    end = text.index("\n];", start)
    body = text[start:end]

    entries = []
    # Split into individual object literals by top-level `{ ... }` blocks.
    depth = 0
    buf = []
    blocks = []
    for ch in body:
        if ch == "{":
            depth += 1
        if depth > 0:
            buf.append(ch)
        if ch == "}":
            depth -= 1
            if depth == 0:
                blocks.append("".join(buf))
                buf = []
    for block in blocks:
        dll_m = re.search(r"dll:\s*'([^']+)'", block)
        va_m = re.search(r"va:\s*(0x[0-9a-fA-F]+)", block)
        id_m = re.search(r"id:\s*'([^']+)'", block)
        if dll_m and va_m and id_m:
            entries.append((dll_m.group(1), int(va_m.group(1), 16), id_m.group(1)))
    return entries


def parse_max_hooks(text: str) -> int:
    """Read HOOKCORE_MAX_HOOKS out of hookcore.h."""
    m = re.search(r"^#define\s+HOOKCORE_MAX_HOOKS\s+(\d+)\s*$", text, re.M)
    if not m:
        raise SystemExit("could not find #define HOOKCORE_MAX_HOOKS in hookcore.h")
    return int(m.group(1))


def parse_table_c(text: str) -> list[tuple[str, int, str]]:
    """Extract (dll, va, id) triples from hookcore_real_table.c's `table[]`."""
    decl = "static const HookDef table[] = {"
    start = text.index(decl) + len(decl)  # skip the outer '{' itself so
    # brace-depth counting below stays balanced within `body`
    end = text.index("\n    };", start)
    body = text[start:end]

    entries = []
    depth = 0
    buf = []
    blocks = []
    for ch in body:
        if ch == "{":
            depth += 1
        if depth > 0:
            buf.append(ch)
        if ch == "}":
            depth -= 1
            if depth == 0:
                blocks.append("".join(buf))
                buf = []
    for block in blocks:
        m = re.match(
            r'\{\s*"([^"]+)",\s*(0x[0-9a-fA-F]+),\s*"([^"]+)"', block
        )
        if m:
            entries.append((m.group(1), int(m.group(2), 16), m.group(3)))
    return entries


def main() -> int:
    js_entries = parse_agent_js(AGENT_JS.read_text(encoding="utf-8"))
    c_entries = parse_table_c(TABLE_C.read_text(encoding="utf-8"))
    max_hooks = parse_max_hooks(HEADER_H.read_text(encoding="utf-8"))

    ok = True
    # v46: the check that would have caught the silent four-hook drop.
    # table[] used to be declared `HookDef table[HOOKCORE_MAX_HOOKS]`, so
    # 36 initialisers against a constant of 32 was a mere GCC warning
    # ("excess elements in array initializer") and the last four hooks --
    # color_adjust_shift, sba_order_fpo_calc, sba_order_fpo_helper,
    # sba_vm_interp -- were dropped from every DLL built. This script passed
    # throughout, because it only ever compared source text to agent.js.
    # table[] is unsized now and hookcore_real_table.c carries a compile-time
    # assert, but the same check is cheap here and fails with a readable
    # message instead of a template-style typedef error.
    if len(c_entries) > max_hooks:
        print(
            f"MISMATCH: hookcore_real_table.c has {len(c_entries)} hooks but "
            f"HOOKCORE_MAX_HOOKS is {max_hooks}. HookEngine.defs[]/rt[] and "
            f"thunks[] are sized by that constant, so the excess entries "
            f"would be dropped. Raise HOOKCORE_MAX_HOOKS, add the matching "
            f"`extern void Thunk_NN` (hookcore.h), `DEFTHUNK NN` (hookstub.S) "
            f"and thunks[] entry (hookcore_real_table.c) -- all four."
        )
        ok = False

    if len(js_entries) != len(c_entries):
        print(
            f"MISMATCH: agent.js has {len(js_entries)} hooks, "
            f"hookcore_real_table.c has {len(c_entries)}"
        )
        ok = False

    for i, (js_e, c_e) in enumerate(zip(js_entries, c_entries)):
        if js_e != c_e:
            print(f"MISMATCH at index {i}:")
            print(f"  agent.js:              dll={js_e[0]!r} va=0x{js_e[1]:08x} id={js_e[2]!r}")
            print(f"  hookcore_real_table.c: dll={c_e[0]!r} va=0x{c_e[1]:08x} id={c_e[2]!r}")
            ok = False

    if ok:
        print(
            f"OK: {len(js_entries)} hooks, identical (dll, va, id) in "
            f"identical order; {len(c_entries)}/{max_hooks} HOOKCORE_MAX_HOOKS "
            f"slots used."
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
