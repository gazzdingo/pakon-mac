# noiseTable (producer)

## Summary: `noiseTable` capability (`AnsNoiseTableCapability` / `AnsNoiseTableCapabilityImpl`)

All addresses below were read directly out of `PakonIMAu.dll` (copied from `research/sdk/PAKONF135.iso` → `.../F-X35 COM SERVER/PakonIMAu.dll`) with radare2 + r2ghidra/avrr (RTTI-based C++ class/vtable recovery), not assumed. Where I inferred rather than verified, it's marked.

### 1. Acquire / analyze / Impl addresses — found, not assumed

Class confirmed via MSVC RTTI type descriptors (raw bytes dumped, not guessed): `AnsNoiseTableCapability` (`.?AVAnsNoiseTableCapability@@` @ `0x1069788c`, base `AnsCapability`) and `AnsNoiseTableCapabilityImpl` (string @ `0x1059ccd8`, source file cited throughout as `\Atc\ansel\src\libNoiseTable.ansel\AnsNoiseTableCapabilityImpl.cpp`).

| Role | Address | Evidence |
|---|---|---|
| **declare()** | `0x10068490` (`method.AnsCnEnhancedPath.virtual_20`, 1643 B, ends `0x10068afb`) | Pushes `"sba"`, `"color"`, `"filmLut"`, `"flesh"`, `"pan"`, `"fos"`, `"scpLut"`, … , `"noiseTable"`, … in a single branch-free block (cyclomatic complexity 1 — no gating at all) into a generic vector via `fcn.10025cd0`. **Correction to the task premise:** `0x10064d70` is *not* this function — it's a 201-byte, zero-call, single-block POD field-zeroing constructor with no capability-name references at all. I verified this directly; the real declare() is `0x10068490`. |
| **acquire** | `fcn.10111e00` (`0x10111e00`–`0x101124d3`, 1747 B) | Builds the `"noiseTable"` string, does a find/QI-style lookup. Called from exactly 6 sites, one per Path class's own `virtual_4`: CnPremium, CnOptical, **CnEnhanced** (call site `0x100654bf`), DcPremium, Archive, +1 plain fcn. |
| **Impl::initialize** (heaviest Impl code — the closest analogue to `…CapabilityImpl::analyze`) | `fcn.1020a2b0` (`0x1020a2b0`–`0x1020b963`, 5811 B, 313 BBs, cyclomatic complexity 176) | Self-cites `"AnsNoiseTableCapabilityImpl::initialize"` throughout; resolves `dataPathItems/noiseTable`, parses `noiseTable.map`, finds the default-key DPI. Reached from **CnEnhanced** via `virtual_44` (`0x100673bb`) → `fcn.1011ed80` (stub) → `fcn.1020bb80` (dir/precondition check, same initialize) → `fcn.1020a2b0`. |
| Impl::installDpi | `0x102098d0` (787 B) | Self-cited string; called 2× from initialize. |
| Impl::generateKey | `0x102092a0` (419 B) | Self-cited string; called from installDpi. |
| **The actual per-scene numeric consumer** (different class, `noiseMethods.cpp`) | `NoiseMethods::analyzeNoise` = `fcn.10112f30` (1449 B); `NoiseMethods::getNoiseTable` = `0x10112980` (1450 B) | Both self-cite `"analyzeNoise"` / `"NoiseMethods::getNoiseTable"` + `noiseMethods.cpp`. |

No function is literally named `AnsNoiseTableCapabilityImpl::analyze` in the binary — the DPI/setup work is `::initialize`, and the actual per-scene value production/consumption is done by the sibling `NoiseMethods` class. I could not find a heavier "analyze" beyond these; flagging this as the honest limit of what I traced rather than guessing a name.

### 2. Size — measured (bfs_reach2.py, the proven direct-call-walk method, thunk-safe, 0 errors each run)

| Entry | Functions | Bytes | Indirect call sites |
|---|---|---|---|
| `AnsNoiseTableCapabilityImpl::initialize` (`0x1020a2b0`) — best analogue to the calibration's `…Impl::analyze` | **163** | **46,316** | **601** |
| acquire (`0x10111e00`) | 97 | 29,769 | 316 |
| `NoiseMethods::getNoiseTable` (`0x10112980`) | 107 | 21,432 | 243 |

For calibration: `AnsShastaCapabilityImpl::analyze` = 189/44,427/386; the whole 6-subsystem `analyzeAutoTone` chain = 166/67,896/615. `noiseTable`'s Impl (163/46,316/601) is comparable in scale to a single full capability like Shasta — not small, but far short of the whole tone chain.

### 3. Genuinely executed for AnsCnEnhancedPath — yes, verified, not gated

Unlike Shasta (proven dead for CN-Enhanced via a jump table with no CN-Premium case), `noiseTable` is **not** gated out:
- `declare()` registers it unconditionally (no branch).
- `acquire` (`fcn.10111e00`) is called from `AnsCnEnhancedPath::virtual_4`.
- `initialize` (`fcn.1020a2b0`) is called from `AnsCnEnhancedPath::virtual_44`.
- `CnEnhanced_analyzeSceneSpecific` (`fcn.10069490`, confirmed by its own callers being `AnsCnEnhancedPath::virtual_8`/`virtual_12`) unconditionally calls `NoiseMethods::analyzeNoise` (`0x1006996f`, right *before* the `analyzeAutoTone` call at `0x10069a1d`) and, right after `analyzeAutoTone` returns (`0x10069a67`), calls `fcn.10106780` = **`ColorNegativePath::analyzeSharpening`** (confirmed by self-citing strings), which itself calls `NoiseMethods::getNoiseTable`.

**Nuance for the specific question asked:** I searched all 16 code cross-references to the `"noiseTable"` string in the whole DLL and none fall inside `analyzeAutoTone` (`0x100fb730`) itself or inside any of its 6 subsystem `Impl::analyze` functions (cna `0x1022ea50`, dra `0x1022af20`, toneHelper `0x101dcc50`, contrast `0x101d8240`, ast `0x10227160`, citras `0x10223860`). So on the evidence I gathered, `analyzeAutoTone`'s own producer chain does **not** itself call `find("noiseTable")` — the confirmed consumer is `ColorNegativePath::analyzeSharpening`, a sibling step in the same `CnEnhanced_analyzeSceneSpecific` sequence, not a callee of `analyzeAutoTone`.

### 4. What it writes and where it plausibly reaches

This repo's own already-ported `pakon_ane_order.py` (independently verified, `ANE_NOISE_TABLE_LAYOUT_PORTED = True`, `ANE_GET_RESULTS_FILL_PORTED = True`) documents the object `NoiseMethods::getNoiseTable` produces/returns: a `NoiseTable` with `+0x44` = table length per plane, `+0x48` = plane count, `+0x4c` = `float*` dens base, and per channel `dens_i = ftol2(table[idx] * blackNoiseSigmaMult)`. `blackNoiseSigmaMult` is explicitly a **density** term (and the same parameter name Shasta uses at `SHASTA_PARAMS_BLACK_NOISE_SIGMA_MULT_OFF`). That doc frames the primary use as CnPremium **mid-aim** (tone-curve aim-point). My own trace adds a second confirmed use for CN-Enhanced specifically: as an input to `ColorNegativePath::analyzeSharpening` (adaptive/noise-aware sharpening amount) — plausibly image-quality-relevant but distinct from the base tone/exposure curve. I did not fully trace whether `analyzeNoise` itself writes anything further into `AnsSceneContext` beyond feeding these two consumers, so I can't rule out additional downstream reads I didn't find. Nothing I found is geometric/orientation/cosmetic — everything traced is density-typed (per-channel `dens` array).

### 5. Existing ported coverage — none for the capability itself

`grep -r noiseTable tools/ansel/` finds only comments/citations (in `pakon_ane_order.py`, `pakon_shasta.py`, `shasta.go`, `docs/63-port-status.md`, `vendor/README.md`) — no `pakon_noise_table.py` and no Unicorn-golden harness for `AnsNoiseTableCapabilityImpl::initialize`/`generateKey`/`installDpi`/`NoiseMethods::analyzeNoise`. `vendor/ansel/` explicitly does **not** include the `noiseTable/` DPI data directory (called out by name in `vendor/README.md` as one of the un-copied dirs), consistent with what I found: its `.map`/DPI resolution machinery is real and unfilled. What *is* already ported is only the generic host-side `NoiseTable` layout/fill helper class in `pakon_ane_order.py` (used to interpret whatever a `NoiseTable` object contains) — the capability's own vendor analyze/initialize logic has zero port coverage. Compare `fugc`, which does have real ported code throughout `tools/ansel/`.

Files touched (read-only): `/tmp/pakon_work/PakonIMAu.dll`, `/tmp/pakon_work/bfs_reach2.py`, `/tmp/pakon_work/bfs_noisetable_*.log`, `/tmp/pakon_work/step*_out.txt` (raw r2 disassembly transcripts backing every address above); repo docs read: `/Users/guy/www/pakon-mac/tools/ansel/pipeline/shasta.go`, `/Users/guy/www/pakon-mac/tools/ansel/python-pipeline/pakon_shasta.py`, `/Users/guy/www/pakon-mac/tools/ansel/python-pipeline/pakon_ane_order.py`, `/Users/guy/www/pakon-mac/docs/63-port-status.md`, `/Users/guy/www/pakon-mac/vendor/README.md`.