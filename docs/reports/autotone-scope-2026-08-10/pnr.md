# pnr (producer)

# ColorNegativePath::analyzeAutoTone — "pnr" capability scoping report

Working environment: `PakonIMAu.dll` extracted from `research/sdk/PAKONF135.iso` (`fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`, 7,598,080 bytes), analyzed with radare2 6.1.8 + r2ghidra, in an isolated scratch copy (`/tmp/pakon_pnr_scratch/`) after noticing a sibling agent already using the shared `/tmp/pakon_scratch/` for the same task family. All addresses below were located by string+xref (the same method already proven on this project, e.g. for `dmin`), then confirmed by `af`/`afij` function boundaries and, where noted, by r2's own RTTI/vtable-name recovery (`avrr`) — not copied from existing docs.

## 1. Function addresses (verified, not assumed)

| Symbol | Address | Size | How confirmed |
|---|---|---|---|
| `AnsPnrCapability::acquire` | `0x1011e840` | 1,792 B | string `"AnsPnrCapability::acquire"` (0x10588274) → xref → prologue boundary |
| `AnsPnrCapability::analyze` (outer wrapper) | `0x1011e1f0` | 928 B | same method, string 0x1058823c |
| `AnsPnrCapability::export` | `0x1011e590` | 688 B | string 0x10588258 |
| `AnsPnrCapabilityImpl::export` | `0x10204df0` | 2,752 B | string 0x1059cba4 |
| **`AnsPnrCapabilityImpl::analyze`** (the task's real target) | **`0x10206c50`** | **2,177 B** (`afij`) | string 0x1059cc84, boundary confirmed by `af` |
| `AnsCnEnhancedPath::declare` | `0x10064ff0` | 2,464 B | see correction below |

**Correction to an existing in-repo comment:** `tools/ansel/pipeline/shasta.go` (and `docs/63`) cite `0x10064d70` for `AnsCnEnhancedPath::declare`. I disassembled that address directly: it's a 201-byte leaf function that only zero-fills a struct and returns — no calls, no capability registration, not `declare()`. The real `declare()` body — the one that embeds nine literal `"AnsCnEnhancedPath::declare"` assert-context strings and ends immediately before `AnsCnEnhancedPath::exportParameterPack` (`0x10065990`, matching docs/62) — starts at `0x10064ff0`. r2's own vtable/RTTI recovery independently labels this address `method.AnsCnEnhancedPath.virtual_4`, and the *same* virtual slot exists (and is called) for `AnsCnPremiumPath`, `AnsCnOpticalPath`, `AnsDcPremiumPath`, `AnsArchivePath`, and one more path class — i.e. `declare()` is a shared virtual override, `0x10064ff0` is correct.

## 2. Size — direct-call reachability from `AnsPnrCapabilityImpl::analyze` (0x10206c50)

Measured by BFS over direct call edges only (r2pipe, `pdfj` per function, following `jump` targets of `call` ops; instructions typed `call` with no resolvable `jump` — i.e. `call reg`/`call [mem]`, vtable dispatch — tallied as indirect sites, not followed):

- **Functions: 99**
- **Code bytes: 26,380**
- **Indirect (vtable) call sites: 437**

For calibration against the numbers already established on this project: Shasta's whole `analyze` = 189 / 44,427 / 386; the full 6-subsystem `analyzeAutoTone` chain = 166 / 67,896 / 615. PNR alone is roughly half of Shasta's function count and ~60% of its code, but has *more* indirect sites than all of Shasta — consistent with the `ImaPnrOp<E>`/`<F>`/`<M>` template-per-pixel-type + `ImaPnrOperationRegistryEntry` factory/registry pattern visible in the mangled symbol strings (BYTE/short/float pyramid operations dispatched through a registry, not straight-line code).

## 3. Execution-gate verdict for AnsCnEnhancedPath (a colour negative): **genuinely executed, no gate found**

Two chains, both traced by binary xref (not inferred from declaration order):

- **Acquire chain:** `AnsPnrCapability::acquire` (0x1011e840) has exactly one caller, a small wrapper `fcn.10111e00`, which is called from six different path classes' `declare()` vtable slots — including, by r2's RTTI naming, `method.AnsCnEnhancedPath.virtual_4` (i.e. `AnsCnEnhancedPath::declare` itself, at `0x10064ff0`). Inside `declare()`, the call sequence that reaches pnr's acquire (`push "2"; call 0x10006880; call 0x10111e00`) sits on a straight-line path. The only branches around it are the same generic "if the previous producer's acquire returned null, throw" pattern repeated identically before and after every other producer in the function — not a film-class or path-name conditional. I found **no jump table or string comparison gating pnr's registration**, unlike the previously-documented Shasta case (gated in an entirely separate function, `PIAnselStartNewRoll`'s 5-way switch, which has no CN-Premium case at all).
- **Analyze chain:** `AnsPnrCapability::analyze` (0x1011e1f0) → `AnsPnrCapabilityImpl::analyze` (0x10206c50) is called from a small driver `fcn.10112f30`, whose callers include `fcn.10054800` (already identified in docs/62 as `CnPremium_analyzeSceneSpecific`) and `fcn.10069490`. `0x10069490` is the function whose bounds contain `0x10069a1d` — the address `shasta.go` already cites as the sole call site of `analyzeAutoTone`, "inside `AnsCnEnhancedPath::CnEnhanced_analyzeSceneSpecific`." That's two independent binary facts converging on the same function, so pnr's `analyze()` runs from the same `CnEnhanced_analyzeSceneSpecific` that later invokes the tone stage — before it, in the same scene-specific pass. (I did not get r2 to resolve `0x10069490` to an RTTI name directly the way it did for `declare()`'s slot; this identification rests on address-range containment, which I consider solid but flag as slightly less direct than the `declare()` finding.)

Combined with docs/62's own binary-derived finding that a real F-135 colour negative selects CN-Enhanced (CN-Premium's enum case doesn't exist in the path selector), pnr is not merely declared — it is acquired and analyzed on the actual render path.

## 4. What it writes to AnsSceneContext, and plausible relevance to tone

- **Write:** exactly one `AnsSceneContext::insert` (0x10023f10) is reachable from `AnsPnrCapabilityImpl::analyze`, in a callee `fcn.10206840` (single caller — only reached from `analyze`, so this fires on the real execution path, not just export/debug). The key string pushed immediately before the insert is **`"mode"`**, and the value is a 4-byte scalar. I checked how common that key is: `"mode"` is used as an `insert`/`find` key at roughly ten unrelated call sites scattered across the DLL — it reads as a generic per-capability status/operating-mode flag (plausibly feeding the host's documented processing-status bitmask, which has an explicit "Bit 6 — Noise Reduction complete" bit), not a distinctive cross-capability contract.
- **Read:** within its own `analyze`, pnr calls `AnsSceneContext::find` for **`"sourceType"`** — but that key is used at 40+ sites across many unrelated capabilities (fos, scpLut, colorAdjust, and functions that sit inside the shasta/contrast/citras address ranges), so it's a shared upstream classifier lookup pnr consumes like everyone else, not something specific to pnr's output.
- I found **no evidence** that any of the six `analyzeAutoTone` subsystems (`cna`, `dra`, `toneHelper`, `contrast`, `ast`, `citras`) reads a `"mode"`-keyed or otherwise pnr-scoped value — I did not exhaustively disassemble all six subsystems to prove a negative, but the one field pnr writes doesn't resemble the shape of the one confirmed cross-capability tone input already documented on this project (`"dmin"`, a 6-byte RGB triple that directly feeds `ColorNegativePath::analyzeScpLutBalance` / `genShastaImages` density math).
- Separately, pnr's own DPI parameter set (`AnsPnrParams`/`AnsPnrResults` field-name strings: `aDefaultSigma`, `nSigmaBands`, `chrFactor`, `lumFactor`, `pyrNoiseFactor`, `numPyrLevels`, `windowSize`, `min/maxLowStopExposure`, `min/maxHighStopExposure`, `profilePath`) describes a Laplacian-pyramid chroma/luminance noise (grain) suppression filter, exposure-zone-scaled. It does operate directly on per-pixel RGB values as a *denoiser* — but that's a separate fact from what it publishes to context for the tone stage to read, which (per the above) looks geometric/status, not tone/density.

**Verdict: what it writes to AnsSceneContext (`"mode"`) does not plausibly feed tone/exposure/density math** — it reads as a generic status scalar, unlike the one already-confirmed tone-relevant field (`dmin`) on this project. This is evidence-based but not exhaustive (six subsystem functions not fully searched for a `"mode"` reader).

## 5. Existing ported/verified coverage in this project: **none**

`grep -rn "Pnr\|AnsPnr" tools/` finds only the one listing line in `shasta.go`'s comment (pnr named as one of the 16 unexamined producers). `tools/ansel/python-pipeline/` has no `pakon_pnr*.py` and no golden fixture, unlike `scpLut` (`pakon_scp_lut.py` + `pakon_scp_lut_golden.py`, 3/4 flags `True` per docs/63) and `fugc` (`pakon_fugc.py`, 12/13 flags `True`). Zero prior work exists on pnr specifically.

## Summary

| Item | Status |
|---|---|
| Addresses | Verified from binary (see table); one correction to an existing repo comment (declare() is at 0x10064ff0, not 0x10064d70) |
| Size from `Impl::analyze` | Measured: 99 functions / 26,380 bytes / 437 indirect sites |
| Executes for CN-Enhanced | Verified: both acquire and analyze chains trace unconditionally into CN-Enhanced's `declare()` and `CnEnhanced_analyzeSceneSpecific`; no film-class/path gate found |
| Tone relevance of what it publishes | Verified it writes one field (`"mode"`, 4 bytes); inferred (not exhaustively proven) that this is a generic status scalar unrelated to tone/density, based on the field's genericness and contrast with the confirmed tone-relevant `"dmin"` precedent |
| Existing port coverage | Verified: none |

Scratch files (BFS scripts, raw r2 dumps, JSON results) are in `/tmp/pakon_pnr_scratch/` if the orchestrator wants to re-run or extend the queries (`reach2.py` is the reachability BFS, `query3.py` the insert/find call-site dump).