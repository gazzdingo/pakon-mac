# nra (producer)

## AnsNraCapability — static-triage findings (CN-Enhanced / colour-negative path)

**Binary examined:** `PakonIMAu.dll` (MD5 `eea9dcf78ee21d4f7c515a6c2512242d`) extracted from `research/sdk/PAKONF135.iso` → `fx35install/.../F-X35 COM SERVER/PakonIMAu.dll`, base `0x10000000` (matches all cited addresses). Tooling: radare2 6.1.8, r2pipe, `pdfj`/`afij` walks — no r2ghidra was actually needed for this scope. Vendor `.dpi` data pulled directly from the mounted ISO (`.../anselinstalldir/dataPathItems/nra/*.dpi`), not from this repo's `vendor/` (nra/ was never copied here).

### 1. Function addresses (verified from binary, not assumed)

| Symbol | Address | Evidence |
|---|---|---|
| `AnsNraCapabilityImpl::analyze` | **0x1020cc80** | Self-cites its own name string 5× internally; called from the wrapper below at `0x1012033a` |
| `AnsNraCapabilityImpl::export` | **0x1020c650** | Self-cites its own name string; single direct-call caller from `~0x1011f6a6` |
| `AnsNraCapability::analyze` (wrapper) | **0x101202b0** | Contains the call to `0x1020cc80` |
| `AnsNraCapability::acquire` (wrapper) | **0x10120930** | Cites `"AnsNraCapability::acquire"` at `0x10120b67` |
| `AnsNraCapability::export` (wrapper) | bounded to **~0x101205b0–0x10120930** (self-cites 4×, at `0x10120723/0x101207b4/0x101207fc/0x10120856`) | Exact prologue not individually re-confirmed — bounded by the neighboring analyze/acquire wrappers, not guessed from scratch |
| `AnsNraCapabilityImpl::AnsNraCapabilityImpl` (ctor) | `0x1059d094` region (string only; address of code not chased) | — |

There is **no separate `AnsNraCapabilityImpl::acquire`** — only the capability-level wrapper acquires (reads the `.dpi`); the Impl exposes analyze/export only. This matches the string table (`AnsNraCapabilityImpl::analyze`, `::export`, `::AnsNraCapabilityImpl` — no `::acquire`).

### 2. Size — measured, not estimated

Direct-call BFS from `AnsNraCapabilityImpl::analyze` (0x1020cc80), same method used for the cited calibration numbers (reproduced it on Shasta first: my run gave 189 funcs / 44,432 realsz-bytes / 386 text-based indirect sites, vs. the cited 189/44,427/386 — matches within noise):

| | Nra (0x1020cc80) | Shasta analyze (calibration) | Whole 6-subsystem chain (calibration) |
|---|---|---|---|
| functions | **39** | 189 | 166 |
| code bytes (realsz sum) | **8,481** (span 8,610) | 44,427–44,432 | 67,896 |
| indirect (vtable) call sites, text-based convention | **181** (65 non-import) | 386 | 615 |

Nra's own reachability is roughly **1/5 the size of Shasta and 1/8 the size of the whole autoTone chain** — it's a small, self-contained producer, not a subsystem-scale piece.

### 3. Execution-gate verdict

- **Declaration is unconditional for this exact path.** `AnsCnEnhancedPath::declare` is `method.AnsCnEnhancedPath.virtual_20` at `0x10068490` — RTTI-recovered as belonging to this literal class (matches the path named in the task). Disassembled in full: **one basic block, zero branches, zero conditional edges** (`num-bbs:1`, `edges:0`). It pushes 32 capability-name strings in a straight-line sequence with no jump table and no filmClass test anywhere in the function. `"nra"` is the **14th** string pushed, immediately after `"pnr"` and before `"dei"` — consistent with (though not identically counted as) the "17th of 30" language in the existing shasta.go/pakon_shasta.py comments; my directly-measured count is 32 names, not 30 (minor discrepancy with that older prose, worth a note but not a contradiction of substance). This is the opposite structure from the Shasta case — Shasta's problem was a **switch table with no CN-Premium arm** in the path-selector; here there is no switch at all, so nothing to route around.
- **The wrapper unconditionally calls the Impl.** `AnsNraCapability::analyze` (0x101202b0) calls `Impl::analyze` (0x1020cc80) with no enable-flag test guarding the call (unlike the pfd-disable pattern found in declareAutoTone). If `AnsNraCapability::analyze()` runs at all for a scene, `Impl::analyze` runs.
- **A real, data-dependent gate exists, but it's inside Nra, not around it.** The `AnsNraResults` struct (dumped fields, confirmed via the debug-print function at `0x10285590`) has a field literally named **`performNra`** — a computed decide-whether-to-denoise flag. `AnsNraParams` (dumped at `0x10285640`) carries `maxHighStopExposure / minHighStopExposure / minLowStopExposure / maxLowStopExposure`, matching the vendor `.dpi` fields exactly (see below). So Nra evaluates the frame's measured exposure against its own ISO/film-bucket thresholds and can turn itself off *per frame*, on data — not the static per-path jump-table gate the Shasta precedent used. I did not trace where `performNra` is read back downstream (out of budget), so I can't say what happens if it comes out false beyond "Nra presumably skips building its operand."
- **Verified:** unconditional declare, unconditional wrapper→Impl call, RTTI-confirmed class ownership. **Inferred, not fully traced:** that some generic "for each declared capability, call acquire()+analyze()" driver is what actually invokes the wrapper for a live CN-Enhanced scene — I found the declare-time registration and the wrapper's own unconditional inner call, but did not locate and disassemble that outer generic driver loop itself.

### 4. What it publishes, and its plausible relevance to tone/density

`AnsNraCapabilityImpl::export` (0x1020c650) constructs a `std::string("nra")` label, allocates an `AnsCapabilityParameterPack`, then — gated on a per-instance byte at `this+0x71` — builds a `new AnsNraOperand` from image width/height/type fields at `this+0x44/0x48/0x4c/0x54/0x58` and calls into `0x10194aa0`. This is a genuine **per-pixel image operator** (`ImaNraOp.cpp` / `ImaNraOperation` in the string table), not metadata.

Fields, cross-checked against the real vendor `.dpi` (e.g. `nra-srcType-speed-negative35-0400.dpi`, pulled off the mounted F-X35 ISO) and the binary's own debug-dump strings — both agree exactly:

- `NoiseScale` / `scaleFactor`
- `WindowSize` / `windowSize` (spatial filter window, e.g. `11`)
- `SigmaBands` / `nSigmaBands`, `DefaultSigma` / `aDefaultSigma[]` — per-channel denoise strength (e.g. `33 44.12 55.0`)
- `MaxHighStopExposure`, `MinHighStopExposure`, `MinLowStopExposure`, `MaxLowStopExposure` — **inputs**, not outputs: thresholds Nra compares the frame's measured exposure against to decide `performNra`
- `bUseFalloff`, `noiseTablePtr` — evidence Nra itself *reads* the `falloff` and `noiseTable` capabilities' published data as inputs (consistent with `Impl::analyze` directly reaching `AnsSceneContext::find`, 0x10022a40, confirmed present in its 39-function reachable set)

**Verdict on tone relevance:** Nra's own output is a **spatial noise-reduction (denoise) kernel/operand**, not a tone, exposure, or density transform. It's not "purely cosmetic/geometric" — it does touch per-pixel RGB values directly — but its effect is grain/noise smoothing, and it *consumes* exposure as an input to gate its own strength rather than producing exposure or density values for others. I searched for every code reference to the literal string `"nra"` across the binary (full `aa`-analyzed project) and found only: the 8-ish per-path `declare()` implementations registering it by name, and its own `export()` self-labeling. **I found no call site anywhere that pushes `"nra"` and then calls `AnsSceneContext::find`** — i.e., no evidence that `analyzeAutoTone` or any tone subsystem reads Nra's output back by name. Its output instead travels through `AnsCnEnhancedPath::exportParameterPack` (`0x10065990`, RTTI-confirmed, 2,862 bytes, ~9 sub-export calls matching docs/62's already-established "noise, balance, FUGC, area, falloff, asea, autoTone, sharpening, defects" list) — a sibling of the autoTone export, not an input to it. I could not conclusively pin exactly which of exportParameterPack's indirect (vtable) calls is Nra's, since dispatch there is through capability-object vtables rather than named calls — that specific link is inferred/circumstantial (matching prior project research in docs/62), not independently nailed down bit-for-bit.

### 5. Existing ported/verified coverage in this repo

**None.** `grep -rn "AnsNraCapability\|AnsImaNraAggregate\|ImaNraOp\|NRA_PORTED\|performNra\|noiseTablePtr" tools/ansel/ tools/*.py` returns zero hits. The only two mentions of `nra` anywhere in `tools/` are the dependency-list comments in `tools/ansel/pipeline/shasta.go:92` and `tools/ansel/python-pipeline/pakon_shasta.py:537`, both just naming it as one of the 16 producer capabilities `analyzeAutoTone` *may* read from — no code exists for it. Unlike `fugc` (`tools/ansel/pipeline/fugc.go`, `pakon_fugc.py` — extensively ported) or `scpLut` (`tools/ansel/pipeline/scplut.go`, `pakon_scp_lut.py`), Nra has zero port surface. `vendor/ansel/` also never copied `dataPathItems/nra/` — those `.dpi` files exist only on the mounted ISO, not in this repo.

### Bottom line

Nra is small (39 fns / 8.5 KB / 181 indirect sites — far smaller than Shasta or the whole autoTone chain), unconditionally declared and unconditionally wrapper-invoked for CN-Enhanced with no path-level jump-table gate (verified: `declare()` is one branchless basic block), but carries its own data-dependent `performNra` on/off decision per frame (verified from struct dump, not traced further). What it publishes is a spatial noise-reduction kernel, not tone/density math, and I found no evidence the tone stage reads it back — it looks like a sibling output in the same export pack as autoTone, not an input to it. No code in this repo covers it today.