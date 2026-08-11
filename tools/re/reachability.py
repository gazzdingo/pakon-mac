#!/usr/bin/env python3
"""Direct-call reachability walk over ``PakonIMAu.dll`` — the canonical version.

WHY THIS FILE EXISTS
--------------------
Every scoping/verification pass on this project has rebuilt this same tool from
scratch in an ephemeral scratch directory (``/tmp/pakon_scratch/reachability.py``,
``/tmp/pakon_work/master_bfs.py``, ``/private/tmp/pakon_re/…``, and so on), and
every one of them then had to re-derive the calibration numbers before it could
trust its own copy.  All of the "N functions / M bytes / K indirect call sites"
figures in ``docs/reports/autotone-scope-2026-08-10/*.md`` came out of one of
those throwaway copies.  This is that tool, committed once, so a future report
is diffable against a past one instead of against a script nobody kept.

WHAT IT MEASURES
----------------
A breadth-first walk over **direct call edges only** starting from one or more
seed VAs.  An edge exists when radare2 reports an op of type ``call`` with a
resolved ``jump`` target — i.e. an ``E8 rel32`` in this 32-bit x86 PE.  Indirect
calls (``call eax``, ``call dword [ecx + 0x1c]``, vtable dispatch, IAT thunks)
are **not** followed, because their targets are not statically known; instead
every indirect call *instruction* found inside any function in the reachable set
is tallied.  That tally is the interesting number on its own: it is a lower
bound on how much of a subsystem's behaviour is hidden behind vtable dispatch
and therefore invisible to a static call graph.

For each reachable function the walk records its canonical entry address (from
``afij``) and its size.

THE CALIBRATION POINT — RUN THIS BEFORE TRUSTING A NEW NUMBER
-------------------------------------------------------------
``AnsShastaCapabilityImpl::analyze`` at ``0x101e5250`` is the project's
calibration point, published as::

    189 functions / 44,427 bytes / 386 indirect call sites

Check a fresh checkout, or a change to this file, with::

    python3 tools/re/reachability.py calibrate

which runs both passes and asserts the reproducible parts.  What "reproduces"
means here is worth being exact about, because the three published figures do
not all come from one pass, and that is why the reports quote a byte range:

* **189 functions — exact, and set-identical.**  The walk's address set is
  byte-for-byte the same 189 addresses the earlier passes recorded.  This is
  the load-bearing number and it is completely stable: it does not move across
  ``aa`` / ``aaa`` / ``aaaa``, ``avrr``, prelude scan, ``anal.hasnext``,
  ``bin.cache``, or BFS-vs-DFS order.  Every direct call target in the set
  lands on a function entry, so there is no mid-function-target ambiguity.
* **386 indirect call sites — exact, from the SECOND pass.**  The walk's own
  op-type tally is 385 (130 register/memory-indirect + 255 IAT thunks).  386 is
  what the *text-based* classifier gets when it re-reads the same 189 addresses
  under a per-address ``af`` (see ``classify`` mode): ``af`` merges three CRT
  thunks and one extra ``call dword [...]`` falls inside the merged bodies.
  ``classify`` reproduces 386 exactly.
* **44,427 bytes — inside a ±54-byte band, not a fixed point.**  Measured
  values, all real and all from this exact binary
  (sha256 ``0ede8d98…``, one build — every copy on this machine hashes the
  same, so this is not a build difference):

  ==========================================  ==========
  pass                                        realsz sum
  ==========================================  ==========
  ``walk`` (full ``aaa`` state) — canonical       44,378
  ``classify`` converged ``af`` fixed point       44,390
  ``classify`` single ``af`` pass, walk order     44,432
  the published figure                            44,427
  ==========================================  ==========

  The whole 54-byte spread (0.12 %) is five MSVCR71/CRT thunks whose extent
  ``af`` merges into their neighbour when it defines them cold:
  ``0x104ffd78`` (5 vs 42), ``0x104ffd53`` (37 vs 42), and ``0x104d4520`` /
  ``0x104d4530`` / ``0x104eea00`` (8 vs 12 each).  Nothing in the subsystem
  itself moves.  The published 44,427 is the single-``af``-pass number with
  ``0x104ffd53`` resolved at 37 rather than 42 — i.e. it was analysed after its
  neighbour rather than before.  That is reproducible on demand
  (``classify --defer 0x104ffd53`` prints exactly 44,427) but it is an
  artefact of visit order in the original run, not a property of the code, and
  the converged fixed point is 44,390.

  **So: quote the walk's own 44,378 for new work, and expect ±0.12 % against
  any previously published byte figure.**  Do NOT chase the last few bytes —
  chase the function count and the indirect count, which are exact.

The two knobs that genuinely break the walk, as opposed to wobbling it:

* ``--analysis aa`` (fast, shallow recursive descent) mis-bounds functions: the
  ``area`` report caught ``0x104d4510`` reported as 4,094,296 bytes when it is
  actually 265.  Full ``aaa`` is the default here for that reason.
* Size accounting.  ``afij``'s ``size`` is the entry-to-last-byte SPAN and is
  meaningless when a stray far edge is attached — for this very seed it sums to
  137,312, three times the real figure, because two CRT thunks each claim a
  ~46 KB span for a ~55-byte body.  ``realsz`` sums the actual basic blocks and
  is the default here.  Both are always in the JSON.

THE BINARY — EXTRACT IT FRESH, EVERY RUN
-----------------------------------------
``research/sdk/PAKONF135.iso`` is **gitignored** (``.gitignore`` line 10:
``research/sdk/*.iso``) and the DLL is **not** pre-extracted anywhere in the
repo.  There is no checked-in copy to fall back on.  Extract it yourself::

    7z e -y research/sdk/PAKONF135.iso -o/tmp/pakon_re \
        "fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll"

The canonical path inside the ISO is::

    fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll

and the extracted file is 7,598,080 bytes, sha256
``0ede8d9813af4ee95dddd85e5adc495a27f014a8fd4817cfbc3b3b1e107f511f``.  It loads
at ``bin.baddr=0x10000000``, which is what makes every VA in ``docs/`` line up.

``extract`` mode below does the extraction and the checksum verification for
you; ``walk`` calls it automatically when the DLL is missing.

USAGE
-----
::

    # prove the tool still works (extracts the DLL, walks Shasta, checks it)
    python3 tools/re/reachability.py calibrate

    # extract the DLL (idempotent; verifies sha256)
    python3 tools/re/reachability.py extract

    # walk one seed
    python3 tools/re/reachability.py walk 0x101e5250 --label shasta

    # the second pass the published 386 comes from, over a saved walk
    python3 tools/re/reachability.py classify out/reach_shasta.json

    # walk several seeds as one combined set (e.g. acquire + analyze)
    python3 tools/re/reachability.py walk 0x1022af20 0x10131100 --label dra

    # set algebra over saved walks — is Shasta's set inside autoTone's?
    python3 tools/re/reachability.py setops out/shasta.json out/autotone.json

    # just the one question, exit status 0/1 for scripting
    python3 tools/re/reachability.py setops A.json B.json --op subset --quiet

Walk results are written as JSON (``--out``, default
``<scratch>/reach_<label>.json``) in the same shape the existing reports quote,
so a future run can be diffed against a past one.  ``setops`` consumes those
JSONs directly — the subset/intersection/difference questions that the
``overlap-resolution`` pass answered by hand-editing a script are a documented
mode here, not an edit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEFAULT_ISO = REPO / "research" / "sdk" / "PAKONF135.iso"
ISO_MEMBER = "fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll"
DLL_SHA256 = "0ede8d9813af4ee95dddd85e5adc495a27f014a8fd4817cfbc3b3b1e107f511f"
DLL_SIZE = 7598080
BADDR = 0x10000000

# Scratch, never the repo: the DLL is vendor code and the ISO is gitignored.
DEFAULT_SCRATCH = Path(os.environ.get("PAKON_RE_SCRATCH", "/tmp/pakon_re"))


# --------------------------------------------------------------------------
# the binary
# --------------------------------------------------------------------------

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_dll(iso: Path, dest_dir: Path, force: bool = False,
                quiet: bool = False) -> Path:
    """Extract PakonIMAu.dll from the SDK ISO into ``dest_dir``.

    Idempotent: an already-extracted file with the right sha256 is left alone.
    A file with the WRONG sha256 is an error, not something to work around —
    every VA in docs/ is keyed to this exact build.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dll = dest_dir / "PakonIMAu.dll"

    if dll.exists() and not force:
        got = sha256(dll)
        if got == DLL_SHA256:
            if not quiet:
                print(f"  {dll} already extracted (sha256 ok)")
            return dll
        raise SystemExit(
            f"{dll} exists but its sha256 is {got}, not {DLL_SHA256}.\n"
            "That is not the build every address in docs/ was derived against. "
            "Delete it and re-extract, or pass --force.")

    if not iso.exists():
        raise SystemExit(
            f"{iso} not found.\n"
            "research/sdk/*.iso is gitignored — the ISO is not in the repo and "
            "the DLL is not pre-extracted anywhere. Put PAKONF135.iso at that "
            "path (or pass --iso) and re-run.")

    if shutil.which("7z") is None:
        raise SystemExit("7z not found on PATH (brew install p7zip).")

    if not quiet:
        print(f"  extracting {ISO_MEMBER} from {iso.name} …")
    proc = subprocess.run(
        ["7z", "e", "-y", str(iso), f"-o{dest_dir}", ISO_MEMBER],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0 or not dll.exists():
        sys.stderr.write(proc.stdout.decode(errors="replace"))
        raise SystemExit(f"7z extraction failed ({proc.returncode})")

    size, got = dll.stat().st_size, sha256(dll)
    if size != DLL_SIZE or got != DLL_SHA256:
        raise SystemExit(
            f"extracted {dll} is {size} bytes / sha256 {got}; "
            f"expected {DLL_SIZE} / {DLL_SHA256}")
    if not quiet:
        print(f"  {dll} ({size} bytes, sha256 ok)")
    return dll


def resolve_dll(args, quiet: bool = False) -> Path:
    if args.dll:
        dll = Path(args.dll)
        if not dll.exists():
            raise SystemExit(f"--dll {dll} does not exist")
        return dll
    return extract_dll(Path(args.iso), Path(args.scratch), quiet=quiet)


# --------------------------------------------------------------------------
# call classification
# --------------------------------------------------------------------------

# r2 op types that are a call with a target it could not resolve statically.
INDIRECT_TYPES = {"ucall", "icall", "rcall", "ircall", "ucjmp"}

_CALL_RE = re.compile(r"^\s*(?:bnd\s+|lock\s+|rep\s+)?call\b\s*(.*)$", re.I)
# A direct target: an absolute address, or a flag name r2 resolved to one.
_DIRECT_OPERAND_RE = re.compile(
    r"^(?:0x[0-9a-f]+|(?:fcn|sub|sym|loc|method|entry|case)\.[\w.:$@]+|"
    r"[\w.:$@]*\d[\w.:$@]*)$", re.I)


def classify_call(op: dict) -> str | None:
    """Return 'direct', 'indirect', 'iat' — or None if this op is not a call.

    Two classifications are kept apart because past reports differed on it:

    * 'indirect' — ``call eax`` / ``call dword [ecx + 0x1c]`` / vtable dispatch.
      The target is a runtime value.
    * 'iat'      — ``call dword [sym.imp.KERNEL32.dll_…]``, an import thunk.
      Also a memory-indirect call, but its target is statically known and it
      leaves the module, so counting it is a judgement call.

    The headline "indirect call sites" figure in this project's reports counts
    'indirect' only — that is what reproduces 386 on the Shasta calibration.
    Both are in the JSON so a future run can ask the other question.
    """
    typ = (op.get("type") or "").lower()
    disasm = (op.get("disasm") or op.get("opcode") or "")
    m = _CALL_RE.match(disasm)

    if not m and typ not in INDIRECT_TYPES and typ != "call":
        return None

    if typ in INDIRECT_TYPES:
        return "iat" if _is_iat(m.group(1) if m else "") else "indirect"

    if typ == "call":
        # r2 resolved it, or it is text-indirect and r2 mislabelled the type.
        operand = (m.group(1) if m else "").strip()
        if op.get("jump") is not None and not _looks_indirect(operand):
            return "direct"
        if _is_iat(operand):
            return "iat"
        return "indirect" if _looks_indirect(operand) else "direct"

    # No usable type, but the text says "call".
    operand = (m.group(1) if m else "").strip()
    if _is_iat(operand):
        return "iat"
    return "indirect" if _looks_indirect(operand) else "direct"


def _looks_indirect(operand: str) -> bool:
    operand = operand.split(";")[0].strip()
    if not operand:
        return False
    if "[" in operand:
        return True
    return not _DIRECT_OPERAND_RE.match(operand)


def _is_iat(operand: str) -> bool:
    return "sym.imp." in (operand or "")


# --------------------------------------------------------------------------
# the walk
# --------------------------------------------------------------------------

def open_r2(dll: Path, analysis: str, quiet: bool = False):
    try:
        import r2pipe
    except ImportError:
        raise SystemExit("r2pipe not installed (pip3 install r2pipe)")

    r2 = r2pipe.open(str(dll), flags=[
        "-e", f"bin.baddr={BADDR:#x}",
        "-e", "bin.relocs.apply=true",
        "-e", "scr.color=0",
        "-2",
    ])
    if analysis != "none":
        t0 = time.time()
        if not quiet:
            print(f"  r2 {analysis} on {dll.name} (this takes minutes) …",
                  flush=True)
        r2.cmd(analysis)
        if not quiet:
            print(f"  {analysis} done in {time.time() - t0:.0f}s", flush=True)
    return r2


def walk(r2, seeds: list[int], quiet: bool = False) -> dict:
    """BFS over direct call edges from ``seeds``.

    Returns the result dict that gets serialised — the same shape every report
    on this project quotes from.
    """
    visited: dict[int, dict] = {}   # canonical entry VA -> {size, realsz, name}
    enqueued: set[int] = set(seeds)
    frontier: list[int] = list(seeds)
    counts = {"direct": 0, "indirect": 0, "iat": 0}
    unresolved: list[int] = []

    while frontier:
        addr = frontier.pop(0)      # breadth-first, not depth-first
        r2.cmd(f"s {addr:#x}")
        info = r2.cmdj("afij")
        if not info:
            r2.cmd("af")
            info = r2.cmdj("afij")
        if not info:
            unresolved.append(addr)
            continue

        fi = info[0]
        entry = fi.get("offset", addr)
        if entry in visited:
            continue
        visited[entry] = {
            "size": fi.get("size", 0) or 0,
            "realsz": fi.get("realsz", fi.get("size", 0)) or 0,
            "name": fi.get("name", ""),
        }

        body = r2.cmdj(f"pdfj @ {entry:#x}") or {}
        for op in body.get("ops", []):
            kind = classify_call(op)
            if kind is None:
                continue
            counts[kind] += 1
            if kind != "direct":
                continue
            target = op.get("jump")
            if target is None:
                continue
            if target in visited or target in enqueued:
                continue
            enqueued.add(target)
            frontier.append(target)

        if not quiet and len(visited) % 50 == 0:
            print(f"    … {len(visited)} functions, {len(frontier)} queued",
                  flush=True)

    return {
        "seeds": [f"{s:#x}" for s in seeds],
        "func_count": len(visited),
        # Insertion order == BFS discovery order. `classify` replays it,
        # because a per-address `af` pass is order-sensitive (see docstring).
        "discovery_order": [f"{a:#x}" for a in visited],
        "bytes_size": sum(v["size"] for v in visited.values()),
        "bytes_realsz": sum(v["realsz"] for v in visited.values()),
        "indirect_call_sites": counts["indirect"],
        "iat_call_sites": counts["iat"],
        "direct_call_sites": counts["direct"],
        "functions": {
            f"{a:#x}": visited[a] for a in sorted(visited)
        },
        "unresolved_targets": [f"{a:#x}" for a in sorted(set(unresolved))],
    }


def cmd_walk(args) -> int:
    seeds = [int(s, 0) for s in args.seed]
    dll = resolve_dll(args, quiet=args.quiet)

    r2 = open_r2(dll, args.analysis, quiet=args.quiet)
    t0 = time.time()
    result = walk(r2, seeds, quiet=args.quiet)
    r2.quit()

    label = args.label or "_".join(f"{s:#x}" for s in seeds)
    result["label"] = label
    result["dll"] = str(dll)
    result["dll_sha256"] = DLL_SHA256
    result["analysis"] = args.analysis
    result["size_field"] = args.size_field
    result["bytes"] = result[f"bytes_{args.size_field}"]
    result["walk_seconds"] = round(time.time() - t0, 1)

    out = Path(args.out) if args.out else Path(args.scratch) / f"reach_{label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))

    print(f"=== reachability from {label} "
          f"seeds {result['seeds']} ===")
    print(f"functions reached  : {result['func_count']}")
    print(f"code bytes ({args.size_field:<6}): {result['bytes']:,}")
    print(f"  (size span sum)  : {result['bytes_size']:,}")
    print(f"  (realsz sum)     : {result['bytes_realsz']:,}")
    print(f"indirect call sites: {result['indirect_call_sites']}")
    print(f"  IAT thunk calls  : {result['iat_call_sites']} (not counted above)")
    print(f"direct call sites  : {result['direct_call_sites']}")
    if result["unresolved_targets"]:
        print(f"unresolved targets : {len(result['unresolved_targets'])}")
    print(f"written to {out}")
    return 0


# --------------------------------------------------------------------------
# the second pass — where the published 386 comes from
# --------------------------------------------------------------------------

_TEXT_REGS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")


def classify_pass(dll: Path, order: list[int], converge: bool = False,
                  defer: list[int] | None = None, quiet: bool = False) -> dict:
    """Re-read a known address list under a per-address ``af``.

    This is deliberately NOT the walk.  It is the independent second pass the
    published 386 came from: no ``aaa``, just ``af`` at each address in turn,
    then a purely TEXTUAL classification of every ``call`` (bracket or bare
    register operand → indirect).  Keeping it separate is the point — it is a
    cross-check on the walk's own op-type tally, and when the two disagree the
    disagreement is the finding.

    ``converge`` repeats the pass until the byte total stops moving, which
    removes the visit-order sensitivity (fixed point: 44,390 on the Shasta
    calibration).  ``defer`` moves the given addresses to the end of the order,
    which is how the published 44,427 is reproduced exactly.
    """
    try:
        import r2pipe
    except ImportError:
        raise SystemExit("r2pipe not installed (pip3 install r2pipe)")

    if defer:
        tail = [a for a in order if a in set(defer)]
        order = [a for a in order if a not in set(defer)] + tail

    r2 = r2pipe.open(str(dll), flags=["-2"])
    r2.cmd("e bin.cache=true")
    r2.cmd("e anal.timeout=30")

    prev_total = None
    for it in range(1, 9):
        sizes: dict[int, dict] = {}
        counts = {"direct": 0, "indirect": 0, "indirect_noimp": 0}
        for a in order:
            r2.cmd(f"af @ {a:#x}")
            fi = r2.cmdj(f"afij @ {a:#x}")
            if not fi:
                continue
            fi = fi[0]
            sizes[a] = {"size": fi.get("size", 0) or 0,
                        "realsz": fi.get("realsz", fi.get("size", 0)) or 0}
            body = r2.cmdj(f"pdfj @ {fi.get('offset', a):#x}") or {}
            for op in body.get("ops", []):
                disasm = op.get("disasm", "") or ""
                if not disasm.startswith("call"):
                    continue
                operand = disasm[len("call"):].strip()
                if "[" in operand or operand in _TEXT_REGS:
                    counts["indirect"] += 1
                    if "sym.imp" not in disasm:
                        counts["indirect_noimp"] += 1
                else:
                    counts["direct"] += 1
        total = sum(v["realsz"] for v in sizes.values())
        if not quiet and converge:
            print(f"    pass {it}: realsz {total:,}", flush=True)
        if not converge or total == prev_total:
            break
        prev_total = total
    r2.quit()

    return {
        "func_count": len(sizes),
        "bytes_realsz": sum(v["realsz"] for v in sizes.values()),
        "bytes_size": sum(v["size"] for v in sizes.values()),
        "indirect_call_sites": counts["indirect"],
        "indirect_excl_imports": counts["indirect_noimp"],
        "direct_call_sites": counts["direct"],
        "converged": converge,
        "deferred": [f"{a:#x}" for a in (defer or [])],
    }


def order_from_walk(data: dict) -> list[int]:
    if data.get("discovery_order"):
        return [int(a, 16) for a in data["discovery_order"]]
    return sorted(int(a, 16) for a in data["functions"])


def cmd_classify(args) -> int:
    data = json.loads(Path(args.walk).read_text())
    order = order_from_walk(data)
    dll = resolve_dll(args, quiet=args.quiet)
    defer = [int(a, 0) for a in (args.defer or [])]

    res = classify_pass(dll, order, converge=args.converge, defer=defer,
                        quiet=args.quiet)
    print(f"=== classify pass over {data.get('label', args.walk)} "
          f"({len(order)} addresses) ===")
    print(f"functions resolved   : {res['func_count']}")
    print(f"code bytes (realsz)  : {res['bytes_realsz']:,}")
    print(f"indirect call sites  : {res['indirect_call_sites']}")
    print(f"  excluding IAT      : {res['indirect_excl_imports']}")
    print(f"direct call sites    : {res['direct_call_sites']}")
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2))
        print(f"written to {args.out}")
    return 0


# --------------------------------------------------------------------------
# the self-check
# --------------------------------------------------------------------------

CAL_SEED = 0x101E5250
CAL_FUNCS = 189
CAL_INDIRECT = 386
CAL_BYTES_PUBLISHED = 44427
CAL_BYTES_BAND = (44378, 44432)


def cmd_calibrate(args) -> int:
    """Walk + classify AnsShastaCapabilityImpl::analyze and check the result.

    Exits non-zero if the exact parts (function count, indirect count) do not
    reproduce, or if the byte total leaves the known ±54-byte thunk band.
    """
    dll = resolve_dll(args, quiet=args.quiet)
    r2 = open_r2(dll, args.analysis, quiet=args.quiet)
    w = walk(r2, [CAL_SEED], quiet=True)
    r2.quit()
    order = [int(a, 16) for a in w["discovery_order"]]

    print(f"  walk  ({args.analysis}): {w['func_count']} functions, "
          f"{w['bytes_realsz']:,} realsz, "
          f"{w['indirect_call_sites']}+{w['iat_call_sites']}="
          f"{w['indirect_call_sites'] + w['iat_call_sites']} indirect(op-type)")

    c = classify_pass(dll, order, quiet=True)
    print(f"  classify (af pass): {c['func_count']} functions, "
          f"{c['bytes_realsz']:,} realsz, "
          f"{c['indirect_call_sites']} indirect(text)")

    cd = classify_pass(dll, order, defer=[0x104FFD53], quiet=True)
    print(f"  classify --defer 0x104ffd53: {cd['bytes_realsz']:,} realsz "
          f"(the published byte figure's visit order)")

    ok = True

    def check(label, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print(f"  [{'PASS' if good else 'FAIL'}] {label}: {got} "
              f"(published {want})")

    check("function count", w["func_count"], CAL_FUNCS)
    check("indirect call sites (classify pass)",
          c["indirect_call_sites"], CAL_INDIRECT)
    check("published byte figure reproduced by --defer 0x104ffd53",
          cd["bytes_realsz"], CAL_BYTES_PUBLISHED)

    lo, hi = CAL_BYTES_BAND
    in_band = lo <= w["bytes_realsz"] <= hi
    ok = ok and in_band
    print(f"  [{'PASS' if in_band else 'FAIL'}] walk byte total "
          f"{w['bytes_realsz']:,} within the known thunk band "
          f"{lo:,}–{hi:,} of the published {CAL_BYTES_PUBLISHED:,}")

    print("CALIBRATION " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


# --------------------------------------------------------------------------
# set algebra over saved walks
# --------------------------------------------------------------------------

def load_walk(path: Path) -> tuple[str, set[int], dict]:
    data = json.loads(Path(path).read_text())
    if "functions" in data and isinstance(data["functions"], dict):
        addrs = {int(a, 16) for a in data["functions"]}
    elif "func_list" in data:                      # older scratch format
        addrs = {int(a, 16) for a in data["func_list"]}
    else:
        raise SystemExit(f"{path}: no function list in this JSON")
    return data.get("label", Path(path).stem), addrs, data


def cmd_setops(args) -> int:
    loaded = [load_walk(Path(p)) for p in args.walks]
    if len(loaded) < 2:
        raise SystemExit("setops needs at least two walk JSONs")

    names = [n for n, _, _ in loaded]
    sets = [s for _, s, _ in loaded]

    def fmt(addrs: set[int], limit: int | None) -> str:
        out = [f"{a:#x}" for a in sorted(addrs)]
        if limit is not None and len(out) > limit:
            return ", ".join(out[:limit]) + f", … (+{len(out) - limit} more)"
        return ", ".join(out) or "(none)"

    a_name, a = names[0], sets[0]
    b_name, b = names[1], sets[1]

    if args.op == "subset":
        ok = a.issubset(b)
        if not args.quiet:
            print(f"{a_name} ({len(a)}) ⊆ {b_name} ({len(b)}): {ok}")
            if not ok:
                extra = a - b
                print(f"  {len(extra)} in {a_name} but not {b_name}: "
                      f"{fmt(extra, args.limit)}")
        return 0 if ok else 1

    if args.op == "intersection":
        inter = set.intersection(*sets)
        print(f"|{'  ∩  '.join(names)}| = {len(inter)}")
        print(f"  {fmt(inter, args.limit)}")
        return 0

    if args.op == "difference":
        diff = a.difference(*sets[1:])
        print(f"|{a_name} \\ {' , '.join(names[1:])}| = {len(diff)}")
        print(f"  {fmt(diff, args.limit)}")
        return 0

    # "report": everything at once, which is what the overlap passes wanted.
    print("=== reachable-set relations ===")
    for n, s, d in loaded:
        b_ = d.get("bytes", d.get("bytes_size", 0))
        print(f"  {n:<28} {len(s):>5} functions  {b_:>9,} bytes  "
              f"{d.get('indirect_call_sites', '?')} indirect")
    print()
    for i, (ni, si, _) in enumerate(loaded):
        for j, (nj, sj, _) in enumerate(loaded):
            if i >= j:
                continue
            inter = si & sj
            print(f"  {ni} ∩ {nj}: {len(inter)}")
            print(f"    {ni} ⊆ {nj}: {si.issubset(sj)}"
                  f"   {nj} ⊆ {ni}: {sj.issubset(si)}")
            print(f"    {ni} only: {len(si - sj)}   {nj} only: {len(sj - si)}")
            if args.limit != 0 and inter:
                print(f"    shared: {fmt(inter, args.limit)}")
    return 0


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="reachability.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_binary_flags(p):
        p.add_argument("--dll", default=os.environ.get("PAKON_DLL"),
                       help="path to an already-extracted PakonIMAu.dll "
                            "(default: extract from --iso into --scratch)")
        p.add_argument("--iso", default=str(DEFAULT_ISO),
                       help=f"SDK ISO (default {DEFAULT_ISO}) — gitignored, "
                            "must be present locally")
        p.add_argument("--scratch", default=str(DEFAULT_SCRATCH),
                       help=f"scratch dir for the DLL and results "
                            f"(default {DEFAULT_SCRATCH})")

    pe = sub.add_parser("extract", help="extract PakonIMAu.dll from the ISO")
    add_binary_flags(pe)
    pe.add_argument("--force", action="store_true",
                    help="re-extract even if a file is already there")
    pe.add_argument("--quiet", action="store_true")

    pw = sub.add_parser("walk", help="BFS over direct call edges from seed VAs")
    add_binary_flags(pw)
    pw.add_argument("seed", nargs="+",
                    help="seed VA(s), e.g. 0x101e5250. Several seeds are "
                         "walked into ONE combined reachable set.")
    pw.add_argument("--label", help="name for this walk (used in the filename)")
    pw.add_argument("--out", help="output JSON path")
    pw.add_argument("--analysis", default="aaa",
                    choices=["none", "aa", "aaa", "aaaa"],
                    help="r2 analysis depth. Default aaa: 'aa' mis-bounds "
                         "functions and inflates the byte count by ~20x "
                         "(see docstring).")
    pw.add_argument("--size-field", default="realsz", choices=["size", "realsz"],
                    help="which afij field the headline byte count sums. "
                         "'realsz' (default) sums the real basic blocks; "
                         "'size' is the entry-to-last-byte span and is junk "
                         "wherever a stray far edge is attached. Both are "
                         "always in the JSON.")
    pw.add_argument("--quiet", action="store_true")

    pc = sub.add_parser("classify",
                        help="second pass over a saved walk's address list "
                             "(per-address af + text classification) — this is "
                             "the pass the published indirect figure comes from")
    add_binary_flags(pc)
    pc.add_argument("walk", help="a walk JSON")
    pc.add_argument("--out", help="write the result here")
    pc.add_argument("--converge", action="store_true",
                    help="repeat until the byte total stops moving, removing "
                         "the visit-order sensitivity")
    pc.add_argument("--defer", nargs="*",
                    help="analyse these addresses LAST. Only needed to "
                         "reproduce a historical byte figure exactly")
    pc.add_argument("--quiet", action="store_true")

    pk = sub.add_parser("calibrate",
                        help="self-check against the published Shasta figures")
    add_binary_flags(pk)
    pk.add_argument("--analysis", default="aaa",
                    choices=["none", "aa", "aaa", "aaaa"])
    pk.add_argument("--quiet", action="store_true")

    ps = sub.add_parser("setops",
                        help="subset / intersection / difference over walk JSONs")
    ps.add_argument("walks", nargs="+", help="walk JSON files")
    ps.add_argument("--op", default="report",
                    choices=["report", "subset", "intersection", "difference"],
                    help="'subset' exits 0 if walks[0] ⊆ walks[1], else 1")
    ps.add_argument("--limit", type=int, default=20,
                    help="max addresses to print per set (0 = none, -1 = all)")
    ps.add_argument("--quiet", action="store_true")

    args = ap.parse_args(argv)
    if getattr(args, "limit", None) == -1:
        args.limit = None

    if args.cmd == "extract":
        extract_dll(Path(args.iso), Path(args.scratch), force=args.force,
                    quiet=args.quiet)
        return 0
    if args.cmd == "walk":
        return cmd_walk(args)
    if args.cmd == "classify":
        return cmd_classify(args)
    if args.cmd == "calibrate":
        return cmd_calibrate(args)
    return cmd_setops(args)


if __name__ == "__main__":
    sys.exit(main())
