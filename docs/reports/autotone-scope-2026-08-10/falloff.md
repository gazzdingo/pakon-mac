# falloff (producer)

## `falloff` capability (AnsFalloffCapability / AnsFalloffCapabilityImpl) — scoping report

**Binary**: `PakonIMAu.dll` extracted from `research/sdk/PAKONF135.iso` (matches `docs/58`/`docs/62`'s build — same addresses cited there resolve correctly here). Tooling: radare2 6.1.8 + r2ghidra, plus a pre-existing r2 project (`~/.local/share/radare2/projects/pakon`, `rc.r2`) from earlier work on this same binary that carries demangled-string-derived function/class names (the DLL is not stripped — assert strings name the C++ methods directly), used to cross-check every address below by independent re-analysis, not just trusted as-is.

### 1. Capability's own addresses — verified, not assumed

| Method | Address | Evidence |
|---|---|---|
| `AnsFalloffCapability::initialize` | `0x1011c3d0` | own assert string `AnsFalloffCapability::initialize` / `AnsFalloffCapabilty::initialize` (sic, vendor typo) referenced inside |
| `AnsFalloffCapability::AnsFalloffCapability` (ctor) | `0x1011ca70` | own ctor assert string inside |
| `AnsFalloffCapability::analyze` | `0x1011ce20` | own assert string inside |
| `AnsFalloffCapability::acquire` | `0x1011d3a0` | own assert string + `"Failed in new AnsFalloffCapability"` inside |
| `AnsFalloffCapabilityImpl::AnsFalloffCapabilityImpl` (ctor) | `0x10202d40` | own ctor assert string inside |
| `AnsFalloffCapabilityImpl::applyFalloff` | `0x10203470` | own assert string inside |
| `AnsFalloffCapabilityImpl::export` | `0x102038f0` | own assert string inside |

Note: unlike Shasta, there is **no `AnsFalloffCapabilityImpl::analyze`** — no such string exists anywhere in the binary. The Impl class's substantive method is `applyFalloff`, not `analyze`.

**Correction to the task's premise**: `0x10064d70` is **not** `AnsCnEnhancedPath::declare`. Verified by disassembly: it's a 201-byte, single-basic-block POD field-zeroing routine (no capability-name strings, no calls) — almost certainly `AnsCnEnhancedPath`'s own trivial ctor. The real declare function — the one that pushes `"falloff"` and ~19 sibling capability-name strings, matching the same role `AnsCnPremiumPath`'s equivalent plays — is **`AnsCnEnhancedPath::virtual_20` @ `0x10068490`** (vtable slot 20; `virtual_16` at `0x10065990` is `exportParameterPack`, already cited in `docs/62`). Confirmed `"falloff"` is pushed at `0x100687c4` inside it.

Also verified: the task's `AnsSceneContext::find` address `0x10022a40` is correct and independently corroborated — it already appears in this repo's own `tools/ansel/python-pipeline/pakon_analyse_roll.py` as `SCENE_CONTEXT_FIND = 0x10022A40`, and it does appear (as a direct callee) inside `AnsFalloffCapability::acquire`'s reachable set. (`0x10020a40`, used by `ColorNegativePath::exportFalloff` to fetch the capability by name, is a distinct, smaller thunk into a `this+0x6028` map member — also named in that same file as `CAP_FIND_BY_NAME`.)

### 2. Size — measured, not guessed

Same BFS-over-direct-calls method as the calibration figures (walked with `/tmp/pakon_scratch/reachability.py`, the script already used for the 189/44,427/386 and 166/67,896/615 numbers). Because there is no `Impl::analyze` seed to match the calibration pattern exactly, I walked all three real entry points separately:

| Seed | Functions | Code bytes | Indirect call sites |
|---|---|---|---|
| `AnsFalloffCapability::acquire` @ `0x1011d3a0` | 74 | 17,550 | 280 |
| `AnsFalloffCapability::analyze` @ `0x1011ce20` | 4 | 920 | 6 |
| `AnsFalloffCapabilityImpl::applyFalloff` @ `0x10203470` | 23 | 3,393 | 76 |
| **Union (dedup by address)** | **80** | **19,511** | **362 (summed, not dedup'd — some indirect sites may double-count where the walks overlap)** |

`acquire`'s reachable set includes `AnsFalloffCapabilityImpl`'s ctor (`0x10202d40`) but not `applyFalloff` or `export` — those are reached only via vtable dispatch (tallied as indirect sites, not followed, per the proven method). `AnsFalloffCapabilityImpl::export` (`0x102038f0`, 1,053 bytes) is not direct-call-reachable from any of the three seeds at all — it's only invoked polymorphically.

**Bottom line: falloff is roughly 40–45% of Shasta's scale** (80 fns/19.5 KB vs. 189 fns/44.4 KB) and **well under 30%** of the whole 6-subsystem `analyzeAutoTone` chain (166 fns/67.9 KB) — a genuinely smaller subsystem, not a comparable-sized one.

### 3. Execution-gate verdict for `AnsCnEnhancedPath` (colour negative) — genuinely reachable, three independent confirmations, no gate found

1. **Declare**: `AnsCnEnhancedPath::virtual_20` (`0x10068490`) is a single basic block (`num-bbs: 1`, `cyclomatic-complexity: 1`, `is-lineal: true`) — an unconditional, straight-line list of ~20 capability registrations. `"falloff"` is pushed unconditionally at `0x100687c4`. No branch, no switch, no filmClass check anywhere in this function.
2. **Export pack**: already established in `docs/62` §12.4.1(b) from a separate function (`AnsCnEnhancedPath::exportParameterPack` @ `0x10065990`) — its pack is `noise, balance, FUGC, area, falloff, asea, autoTone, sharpening, defects`, and pack order was independently proven to equal render order (no reordering stage exists). Re-confirmed here that `falloff` and `autoTone` are **sibling entries in that list, not one feeding the other**.
3. **Direct call, newly found here**: a function inside `AnsCnEnhancedPath`'s own code range (`0x10069490`–`0x10069d80`, the CN-Enhanced per-scene-analyze routine, sibling to the already-documented `CnPremium_analyzeSceneSpecific` @ `0x10054800`) calls `ColorNegativePath::analyzeFalloff` (`0x100fe960`, already named `PATH_ANALYZE_FALLOFF` in this repo's own `pakon_analyse_roll.py`) directly via `E8` at `0x100699b5`, with no conditional branch guarding the call site. The same `analyzeFalloff` function is also called from `AnsCnPremiumPath`'s and `AnsCnOpticalPath`'s equivalents — unlike Shasta, there is **no missing-case switch table** excluding CN-Enhanced from this call.

Contrast with Shasta: Shasta was proven absent from CN-Enhanced's pack and gated out at the roll-start path-selector switch (`0x10002270`, no case yielding CN-Premium). **Falloff has none of that pattern** — declared unconditionally, exported unconditionally (order-proven), and its scene-analyze called directly and unconditionally from CN-Enhanced's own code. Verdict: **falloff genuinely executes on the CN-Enhanced (F-135 colour-negative) path**, not merely declared.

Caveat (not verified): I did not trace whether the containing per-scene-analyze function itself (`0x10069490`) is unconditionally invoked once per scene for every roll, only that the call to `analyzeFalloff` inside it is unconditional given that function runs.

### 4. What it writes, and its relevance to tone/density math

The class names verified in the binary — `ImaLensFalloffOperation`/`ImaLensFalloffOperationBase`, `AnsImaFalloffAggregate`, `AnsFalloffOperand`, `AnsFalloffDPI` — identify this unambiguously as a **lens/scanner radial vignetting (brightness falloff) correction**, not a scene-tone or exposure analysis. There is no percentile/histogram/aim-curve vocabulary anywhere in its strings (contrast with Shasta/`toneHelper`, which are full of that).

- `ColorNegativePath::exportFalloff` (`0x100ff400`) looks the capability up by name (`AnsSceneContext`-style find), and on success makes two **indirect (vtable) calls** into it — almost certainly `AnsFalloffCapability::export()`, which packages an `AnsImaFalloffAggregate`/`ImaLensFalloffOperation` graph node (built from `AnsFalloffDPI`-sourced calibration data, per-channel radial gain, per `AnsFalloffOperand`) into the render graph as its own operation.
- This **does** touch actual per-pixel RGB values (it's a multiplicative gain map applied to the image, not purely geometric/orientation metadata) — so it is not cosmetic/disconnected in the way orientation flags would be.
- However, it is a **fixed, position-dependent (radial) correction sourced from lens/scanner calibration data**, not content-derived scene tone math. I found **no evidence** that `analyzeAutoTone` (`0x100fb730`) or any of its 6 named tone subsystems (cna/dra/toneHelper/contrast/ast/citras) perform a name-keyed `"falloff"` lookup — none of the code sites that reference the `"falloff"` string fall inside `analyzeAutoTone`'s function body or in the address ranges of those subsystems (checked by exhaustive string-xref grep, not exhaustive disassembly of all 6). What is established instead (via the pack-order proof) is that falloff and autoTone are **parallel, independent stages composed on the same image**, in pack order `… area, falloff, asea, autoTone, sharpening, defects` — falloff's operation runs on the pixel stream *before* autoTone's, but autoTone does not appear to read a falloff-published *value* out of `AnsSceneContext`; it just processes whatever pixels result after falloff's operation already executed earlier in the transform graph.
- I could not fully rule out that one of the 6 tone subsystems consumes falloff-derived data through a non-name-keyed (positional/struct-offset) channel — that would not show up in a string-xref search and I did not have time to disassemble all 6 subsystems' full bodies to check.

**So: real per-pixel effect, real execution on CN-Enhanced — but it looks like a lens-calibration sibling stage to autoTone, not an input into autoTone's tone/exposure math**, contrary to what the task's phrasing implies. This should be reported to whatever is consuming `docs/63`'s §3 producer-capability list as a likely **prune candidate for the tone-math dependency scope**, pending someone checking the 6 subsystems directly.

### 5. Existing ported/verified coverage in this repo — none

```
grep -rli falloff tools/          → only comment mentions:
  tools/ansel/python-pipeline/pakon_analyse_roll.py  (PATH_ANALYZE_FALLOFF = 0x100FE960, listed as a name)
  tools/ansel/pipeline/request.go, shasta.go          (listed in a comment as a producer capability)
```
No `pakon_falloff.py`, no `falloff.go`, no `*_PORTED` flags for it anywhere, nothing in `tools/native-manifest.json`. Unlike `fugc` (`pakon_fugc.py`, 12/13 flags `True`) or `scpLut` (`pakon_scp_lut.py`, 3/4 `True`), **falloff has zero ported/verified code in this project** — it is currently pure vendor-binary knowledge, not implemented on either the Python or Go side.

---

**Verified from the binary**: all 7 capability-function addresses in §1; the declare-function correction and its unconditional single-block registration of `"falloff"`; the direct, unguarded call from CN-Enhanced's own scene-analyze code into `analyzeFalloff`; the size/reachability numbers in §2 (measured via the project's own proven BFS script, raw JSON left at `/tmp/pakon_scratch/reach_falloffCap_{acquire,analyze}.json` and `reach_falloffImpl_applyFalloff.json`); the class-name/vtable-call evidence for what it writes.

**Inferred, not directly proven**: that `applyFalloff`/`export` build/emit a radial gain map specifically (based on class names and call shape, not a full data-flow trace of the DPI table contents); that the containing scene-analyze function runs unconditionally once per roll.

**Could not determine in the time available**: whether any of `analyzeAutoTone`'s 6 tone subsystems consume falloff output through a non-name-keyed channel (would require disassembling all 6 subsystem bodies, not just string-xref search).