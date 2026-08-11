# area (producer)

## Summary — `AnsAreaCapability` scoping for `ColorNegativePath::analyzeAutoTone`

**Binary:** `PakonIMAu.dll` (x86, 32-bit, PE, baddr `0x10000000`), pulled from `research/sdk/PAKONF135.iso` → `fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`, analyzed with radare2 6.1.8 + r2ghidra (installed) via `aa`/`aaa` and cross-checked with raw PE byte-offset scans (own scripts, no r2) to catch analysis artefacts. Note: heavy concurrent r2 activity from other sessions was present on this machine throughout (shared `/tmp/pakon_scratch`); I reused its existing, already-correct calibration numbers for `analyzeAutoTone` (166 fns / 71,760 bytes / 615 indirect) after sanity-checking them myself, and ran all new "area"-specific analysis independently.

### 1. Addresses — found, not assumed (VERIFIED)
All confirmed via the embedded vendor debug/trace strings (`AnsAreaCapabiltyImpl::analyze` / `::initialize` — note the vendor's own typo, missing an "i" — plus `\Atc\ansel\src\libAREA.ansel\...cpp` path strings) and confirmed as true function entries by finding a clean `ret; int3×n` boundary immediately before the prologue (cross-checked against r2's own `aaa` result, which agreed exactly):

| Function | Address | Size |
|---|---|---|
| `AnsAreaCapabilityImpl::analyze` | `0x1019e5f0` | 2606 B |
| `AnsAreaCapabilityImpl::initialize` | `0x1019c950` | 6791 B |
| `AnsAreaCapabilityImpl::applyBalanceShifts` | `0x1019a0c0` | 1086 B |
| `AnsAreaCapabilityImpl::AnsAreaCapabilityImpl` (ctor) | `0x1019c240` | 1254 B |
| `AnsAreaCapabilityImpl::export` | `0x1019b470` | 1473 B |
| `AnsAreaCapability::acquire` (non-Impl wrapper) | `0x100dc180` | 28 B — pure forward to `Impl::initialize` |
| `AnsAreaCapability::analyze` (non-Impl wrapper) | `0x100dc2f0` | 3578 B — calls both `Impl::applyBalanceShifts` and `Impl::analyze` |

`applyBalanceShifts` at `0x1019a0c0` was already an established address in this project (cited in `docs58`/`pakon_sba_apply.py`) — I independently re-derived it and it matches exactly.

### 2. Size — measured (VERIFIED, with a correction along the way)
Direct-call reachability walk from `AnsAreaCapabilityImpl::analyze @ 0x1019e5f0`, same BFS-over-E8-calls method used for the Shasta/autoTone calibration numbers:

- **First attempt (lean `aa` mode, the project's default fast method) gave a corrupted result**: 732 fns / 5,763,431 bytes / 1,408 indirect. I did not trust this — cross-checked the two largest "functions" at the raw byte level and found r2's shallow recursive-descent had mis-bounded them (`0x104d4510` reported as 4,094,296 bytes, actually 265; `0x10199110` reported as 1,349,190 bytes, actually 1,050).
- **Re-run with full `aaa` analysis** (same seed, same walk logic) gives the trustworthy number:

  **`AnsAreaCapabilityImpl::analyze`: 732 functions / 299,737 code bytes / 1,405 indirect (vtable) call sites.**

For calibration: Shasta's analyze = 189/44,427/386; the whole 6-subsystem `analyzeAutoTone` chain = 166/71,760/615 (I reproduced this myself and it has no mis-bounding artefact, byte count differs slightly — ~6% — from the previously-published 67,896, likely run-to-run relocation/state variance). So **`AnsAreaCapabilityImpl::analyze` alone is ~3.9× the size of the whole 6-subsystem tone chain**, and larger than any previously-measured piece — it's a large, separately-shipped vendor library (`libAREA.ansel`) for interactive defect detection/correction, not a small helper.

### 3. Execution gate — genuinely different from Shasta (mixed: parts VERIFIED, parts inferred)
**VERIFIED, doubly:** `analyzeAutoTone`'s own 166-function reachable set never touches "area" — (a) none of `AnsAreaCapability`'s four addresses above appear in that 166-function set; (b) `analyzeAutoTone`'s own body directly pushes only `"cna"/"dra"/"toneHelper"/"contrast"/"citras"/"pfd"` — never `"area"` or any of the other 15 producer names. So the docs/63 framing ("autoTone may read from area") is **not supported** as a *direct* read.

**But unlike Shasta, "area" is not orphaned off the CN-Enhanced path — quite the opposite:**
- `AnsCnEnhancedPath`'s own declare code (`virtual_52`) references `"area"` twice, and its acquire-dispatch code references it again immediately before its scene-specific chain (`CnEnhanced_analyzeSceneSpecific`) begins.
- `AnsAreaCapability::acquire (0x100dc180)` is called **directly and unconditionally** from inside `AnsCnEnhancedPath`'s own code, at `0x10067175` — verified by E8-scan: this is one of exactly **12** direct callers of `acquire()` across the whole binary, matching **exactly** the 12 concrete `AnsXxxPath` classes (CpRestore, CpLockbeam, CpBalance, CnPremium, CnOptical, CnLockbeam, **CnEnhanced**, DcPremium, DcLockbeam, DcEnhanced, DcBalance, Archive) that each reference `"area"` in their own declare/acquire code.
- `ColorNegativePath::balanceAreaImage (0x10102b20)` — a real, earlier stage of the same CN-Enhanced scene sequence that runs before `analyzeAutoTone` — itself references `"area"` via a name-keyed lookup call.

There is **no jump-table gate excluding CN-Enhanced** the way there was for Shasta (no case ever producing "CN-Premium"). **Not fully determined:** the non-Impl `AnsAreaCapability::analyze()` wrapper (`0x100dc2f0`) has **zero direct callers anywhere** — it's reached only via indirect/vtable dispatch, which I did not statically resolve, so I cannot *prove* `analyze()` itself fires for CN-Enhanced (only that `acquire()`/`initialize()` provably do). This is architecturally consistent with the same generic per-capability dispatch loop this project already treats as live for sibling producers, but that's inference, not a traced call.

### 4. What it writes, and its plausible effect on tone (mostly inferred from strings, not from tracing `export`'s field stores)
`AnsAreaCapabilityImpl`'s own DPI parameters and sibling classes (`libAREA.ansel`) are: `modifyAreaPercent`, `nonBlemAreaPct`, `minArea4BaseHeight`, `minArea4BaseWidth`, `AnsAreaDefect` (has a `center=(...)` 2D coordinate), `AnsAreaCorrection`/`AnsAreaCorrectionImpl::getSeed`/`getAutomaticIsCanceled`/`getAutomaticCorrectionLevels`/`getManualCorrectionLevel`, `AnsAreaCandidate`, `AnsAreaOperand` (with a `convertAnsImageToJImage` bridge and a `"Color maskAreaPercent ="` debug line). This is a **spatial dust/scratch/blemish detection-and-retouching feature** (defect candidate regions, seed points, correction levels, percentage of frame masked) — the kind of thing exposed in the vendor GUI for manual/automatic defect removal — not colour or density values.

The one `AnsArea` function that does touch a LUT-like structure, `applyBalanceShifts`, was already independently established and ported in this project (`docs58` §16.3, `pakon_sba_apply.py`) to build exactly three 4096-entry per-channel LUTs of the shape `out[i] = clamp(i + shift, 0, 4095)` — one shared master curve plus three integer offsets — **provably shape-null for contrast** (same category as the already-ruled-out `makeSRALUTS`).

**Net:** what "area" plausibly publishes is geometric/cosmetic defect data, disconnected from per-pixel RGB/density math, and I found no read path by which `analyzeAutoTone`'s own code consumes it.

### 5. Existing coverage in this repo (VERIFIED via grep)
Only `AnsAreaCapabilityImpl::applyBalanceShifts @ 0x1019a0c0` is ported/cited — in `tools/ansel/python-pipeline/pakon_sba_apply.py`, `pakon_sba_preference.py`, `pakon_ansel_c.c`, `tools/pakon_pipeline_cli.c`, `tools/pakon_raw_decoder.c` — for its already-proven shape-null LUT role, not for anything density-related. Zero hits anywhere in `tools/` for `AnsAreaCapability`, `AnsAreaParameters`, `AnsAreaCorrection`, `AnsAreaDefect`, `AnsAreaCandidate`, or `AnsAreaOperand`. Unlike `fugc` (extensively ported) or `scpLut` (partially ported, being worked concurrently elsewhere on this machine right now), "area" has essentially no prior porting effort beyond that one incidental function.