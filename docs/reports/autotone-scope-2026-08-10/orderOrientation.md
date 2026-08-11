# orderOrientation (producer)

## Summary: `orderOrientation` capability (AnsOrderOrientationCapability / …Impl) in PakonIMAu.dll

DLL used: `research/sdk/PAKONF135.iso` → extracted `PakonIMAu.dll`, 7,598,080 bytes, MD5 `eea9dcf78ee21d4f7c515a6c2512242d` (matches docs/62's cited build). Tooling: radare2 6.1.8 + r2ghidra, plus raw byte-pattern scans (Python) for call/push-immediate sites where the shared analysis project was too contended to use interactively. `vaddr = file_offset + 0x10000000` confirmed repeatedly (multiple independent string hits landed on function starts already named in this repo's own docs).

### 1. Addresses — found, not assumed (and independently triple-checked)

Every address below was derived from my own r2/byte-scan work, then found to match exactly what already exists in `tools/ansel/python-pipeline/pakon_ane_order.py:206-210` ("OrderOrientation (separate) — Cap `0x101218c0` / Impl `0x102101d0` — from `analyzeAttributes` `0x100fb576`, not AneOrder dens") — an independent prior confirmation I only discovered after deriving the addresses myself.

| Method | Address | realsz (bytes) | direct calls out | callers in |
|---|---|---|---|---|
| `AnsOrderOrientationCapability` ctor (wires up Impl) | `0x10121570` | 469 | 15 | 1 |
| `AnsOrderOrientationCapability::initialize` | `0x10120f00` | 1640 | 55 | 3 |
| `AnsOrderOrientationCapability::acquire` | `0x10121bb0` | 1204 | 37 | 1 |
| `AnsOrderOrientationCapability::analyze` | `0x101218c0` | 329 | 9 | **1**, from `0x100fb576` |
| `AnsOrderOrientationCapabilityImpl` ctor | `0x1020fb20` | 1679 | 59 | 1 |
| `AnsOrderOrientationCapabilityImpl::analyze` | `0x102101d0` | 1169 (main try-block; r2's linear-sweep boundary stops right before an SEH catch/rethrow tail at ~`0x10210661…0x1021067f` that isn't merged in — real function is a little larger) | 24 | 1 |

Note on the task's cited `AnsCnEnhancedPath::declare (0x10064d70)`: that address is real but is a small (201-byte) POD-zeroing helper with in-degree 6, not the 30-capability dispatcher itself. The actual per-Path declare loop that pushes the `"AnsCnEnhancedPath::declare"` assert string is `method.AnsCnEnhancedPath.virtual_4` at `0x10064ff0` (2089 bytes, 108 BBs, out-degree 85) — `0x10064d70` is a helper it (and ~5 sibling Path classes' declare()s) call. Flagging this discrepancy rather than silently using the task's number.

### 2. Size — measured via the same "walk direct calls" method

BFS over direct (`E8`) calls from `AnsOrderOrientationCapabilityImpl::analyze` (`0x102101d0`), using the persisted r2 project (11,056 functions already analyzed), tallying unique callees, summed real function bytes, and indirect (`ircall`/register/vtable) call-site count per function:

**33 functions / 14,960 bytes / 96 indirect call sites.**

For calibration: Shasta's whole `CapabilityImpl::analyze` = 189/44,427/386; the entire 6-subsystem `analyzeAutoTone` chain = 166/67,896/615. OrderOrientation is ~1/6 the function count and code size of Shasta alone, and a small fraction of the whole tone chain — a modest, self-contained capability, dominated by one large shared 7,943-byte utility function (`0x10285f90`) plus its own ~1.2–1.7KB acquire/init/ctor/analyze bodies. This is a real measurement (`walk_result2.json` retained at `/tmp/pakon_scratch/walk_result2.json`), not an estimate.

### 3. Execution gate for AnsCnEnhancedPath (CN, i.e. a colour negative) — real, not just declared

- Declaration confirmed independently by disassembly: the CN-Enhanced-side registration code sequentially constructs and registers capability names …`afterSCPLutSba` → `area` → `orderOrientation`… (consecutive `std::string` ctor/dtor pairs at `0x10068614/0x10068644/0x10068674`), matching the order already documented in `docs/63` / `tools/ansel/pipeline/shasta.go` exactly (8th of 30).
- `AnsOrderOrientationCapability::analyze` (`0x101218c0`) has **exactly one caller in the whole DLL**: `0x100fb576`, a call site inside `ColorNegativePath::analyzeAttributes` (function entry ~`0x100fb3d0`, SEH-prologued).
- `analyzeAttributes` sits immediately before `ColorNegativePath::analyzeAutoTone` (`0x100fb730`, whose sole caller — independently re-confirmed by me via byte-pattern scan — is `0x10069a1d` inside `CnEnhanced_analyzeSceneSpecific`, exactly matching shasta.go's citation).
- Unlike Shasta (proven gated out for CN-Enhanced by a jump table with no CN-Premium case), I found **no analogous gate** excluding `orderOrientation` on this path — its declare-order, its unique caller, and its physical adjacency to the already-proven-live `analyzeAutoTone` all point the same way.
- Caveat: this is static reachability (call-graph + single-caller chains), the same evidentiary standard the rest of this repo's "ESTABLISHED" findings use, not a runtime/Unicorn trace — nothing was executed.

### 4. What it writes, and its bearing on tone/density math

The Impl's own DPI schema (`AnsOrderOrientationDPI::readAscii` field table, read via `strings`) is unambiguous: paired top/bottom (`t_`/`b_`) per-channel probability accumulators (`b_blui_a`, `t_grylw_x`, `b_rdmgw_x`, …), Bayesian machinery (`*_thresh`, `lowerproblimit`, `upperproblimit`, `prior`), and a `lndscp` (landscape) flag. Its two output fields, found right next to the Impl constructor, are **`orderOrientationProb`** and **`frameOrientationProb`** — confidence scores for an auto-rotation/flip classification, not RGB or density values. This is a scene-classification capability (sky/grass-style top-vs-bottom colour statistics used only as classifier *features*), functionally geometric/cosmetic, not a colour-transform.

Consumption trace: there are only two bare-name lookups of `"orderOrientation"` anywhere in the 7.6MB DLL — one inside `analyzeAttributes` itself (which also directly calls `Capability::analyze`), and one inside a function at `~0x100f93f0` that is called from three sites, one of which (`0x100653c7`) is inside `AnsCnEnhancedPath::declare`'s own body — consistent with this being (or being immediately adjacent to) `ColorNegativePath::declareAutoTone`. Importantly, **`analyzeAutoTone`'s own body never repeats that lookup**: its capability fetches (`0x100fb7b9…0x100fbd21`, all through the same generic accessor `0x10020a40`) are limited to exactly the seven producers shasta.go already documents (cna, dra, toneHelper, contrast, ast, citras, pfd) — `orderOrientation` is not among them.

**Verdict:** what `orderOrientation` publishes (rotation/orientation probabilities) looks disconnected from per-pixel RGB/density math — `analyzeAutoTone` itself doesn't read it. What I could **not** determine is whether `declareAutoTone`'s lookup of it is a genuine value-consuming dependency (e.g. gating which producers get enabled) or a no-op existence check; I did not trace far enough into that function's use of the lookup result to rule out a gating role with certainty.

### 5. Existing ported coverage — none

`grep -r "orderOrientation" tools/ansel/` finds zero implementation files — only three comment citations (`shasta.go`, `pakon_shasta.py`, `pakon_analyse_roll.py`) listing it as one of 16 possibly-relevant producers, plus the scoping note already discussed in `pakon_ane_order.py:206-210` that independently pins the same two addresses I found and explicitly separates it from what that file does port. No `pakon_order_orientation.py` or Go equivalent exists. `vendor/ansel/` also does not carry an OrderOrientation `.dpi`/map — only `cna/`, `dra/`, `toneHelper/` were copied in for the tone chain — so even the parameter file this capability needs is absent from the repo. By contrast (per the task's own comparison points), `fugc` (12/13 flags `True`, dedicated `pakon_fugc.py`/`.go`) and `scpLut` (3/4 flags `True`, `pakon_scp_lut.py`, `pakon_scp_lut_golden.py`) both have substantial verified ports — `orderOrientation` has none.

**Files/paths referenced:** `/Users/guy/www/pakon-mac/docs/62-colour-engine-consolidation.md`, `docs/63-port-status.md`, `tools/ansel/pipeline/shasta.go`, `tools/ansel/python-pipeline/pakon_shasta.py`, `pakon_ane_order.py`, `pakon_analyse_roll.py`, `vendor/README.md`. Extracted DLL and analysis artifacts: `/tmp/pakon_scratch/PakonIMAu.dll`, `/tmp/pakon_scratch/walk_result2.json`.