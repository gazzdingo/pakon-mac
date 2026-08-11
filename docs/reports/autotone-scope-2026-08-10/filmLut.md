# filmLut (producer)

## Summary: `filmLut` capability (AnsFilmLutCapability) — CN-Enhanced colour-negative path

**Binary:** `PakonIMAu.dll`, base `0x10000000`, 7,598,080 bytes (md5 `eea9dcf7…`, matches the size docs/62 §12.4 already cites), extracted from `research/sdk/PAKONF135.iso` per `vendor/README.md`. Tooling: radare2 6.1.8 + r2ghidra, using an existing saved r2 project (`~/.local/share/radare2/projects/pakon`) and this project's own BFS reachability script (`/tmp/pakon_scratch/reachability.py`), the same method cited for the Shasta/autoTone calibration numbers.

### 1. Correction to the repo's own citation, then the real addresses

**`AnsCnEnhancedPath::declare` is not at `0x10064d70`.** I disassembled it in full: 201 bytes, one basic block, 51 instructions, zero CALL instructions — it's a plain member-zeroing constructor/reset (six unrelated callers elsewhere in the DLL use it too). This address is currently asserted as `declare` in `tools/ansel/pipeline/shasta.go:92` and `tools/ansel/python-pipeline/pakon_shasta.py:537` (and inherited into this task's own framing) — that citation is wrong.

The real `declare()` is **`method.AnsCnEnhancedPath.virtual_20 @ 0x10068490`** (1,643 bytes). Confirmed two ways: (a) the self-referential assert-string `"AnsCnEnhancedPath::declare"` is pushed repeatedly inside/adjacent to it; (b) its body is a literal, ordered sequence of 32 `push <capability-name-string>; call fcn.10025cd0` blocks — `fcn.10025cd0` (136 bytes, 315 callers binary-wide) is the generic declare-by-name primitive. Full order read off the disassembly: **sba, color, filmLut, flesh, pan, fos, scpLut, afterSCPLutSba, area, orderOrientation, asea, noiseTable, pnr, nra, dei, dtt, falloff, fugc, cna, dra, toneHelper, contrast, ast, citras, pfd, sharpenAdjust, adaptSharp, blemish, date, dust, scratch, redeye**. `filmLut` is 3rd of 32 (not 1st as the existing comment states — it precedes `sba`/`color`), well before the tone-chain names (`cna`…`citras`, positions 19–24).

**filmLut's own class**, from per-function assert strings + xrefs (source path `\Atc\ansel\src\libFilmLut.ansel\` is in the binary's own strings):

| symbol | address |
|---|---|
| `AnsFilmLutCapability::acquire` | `0x101273e0` |
| `AnsFilmLutCapability::AnsFilmLutCapability` (ctor) | `0x101270d0` |
| `AnsFilmLutCapabilityImpl::AnsFilmLutCapabilityImpl` (ctor; parses `AnsFilmLutParams` from `AnsCommon3BandLutDPI`) | `0x1021f5d0` |
| `AnsFilmLutCapabilityImpl::initialize()` (loads `filmLut-scanner-prod-gen-*.lut`) | `0x1021eb40` |

No `AnsFilmLutCapability::analyze` / `AnsFilmLutCapabilityImpl::analyze` assert string exists anywhere in the binary (checked the full string table) — **filmLut has no per-scene analyze step.** It's declare → acquire → construct → `initialize()` (one static file load), full stop.

### 2. Size — measured, not guessed

Using this project's own BFS direct-call walk script:

| seed | functions | code bytes | indirect call sites |
|---|---|---|---|
| `AnsFilmLutCapability::acquire` (`0x101273e0`) | 113 | 139,375 | 451 |
| `AnsFilmLutCapabilityImpl::initialize` (`0x1021eb40`) | 77 | 125,754 | 243 |
| *calibration, re-measured myself:* `analyzeAutoTone` (`0x100fb730`) | 166 | 71,760 | 615 |
| *calibration:* `AnsSCPLutCapabilityImpl::analyze` (`0x102128f0`) | 7 | 2,310 | 3 |

The autoTone re-measurement matches the cited 166/615 exactly; bytes differ from the cited 67,896 by ~6% (tool/run variance, not a correction). filmLut's acquire path is large in bytes despite fewer functions than Shasta/autoTone — dominated by shared MSVC STL string ops and the generic 3-band-DPI/file-loading path, not filmLut-specific math.

### 3. Execution-gate verdict: declared **and genuinely executed**, but never reached *from* `analyzeAutoTone`

Real, fatal-gated lookup sites (`push "filmLut"` → `call fcn.10020a40` [the generic get-capability-by-name primitive, **not** `AnsSceneContext::find`] → hard-fails with `"FilmLut capability not found."` on miss):

- `ColorNegativePath::analyzePreBalance` (`0x100fcd70`), site `0x100fce92`
- `ColorNegativePath::balanceAreaImage` (`0x10102b20`), site `0x10102cad`
- `BalanceMethods_export` (`0x101142a0`), site `0x101142fb`
- one unidentified 1,858-byte sibling (`fcn.10113b50`) and one CN-Premium-side site (`fcn.100575e0`) — not pinned to a C++ name this session

`analyzePreBalance` and `balanceAreaImage` are steps this repo's own prior [VERIFIED] work (`docs/58` §16.3, mirrored in `/private/tmp/doc58.md`) already places directly inside `AnsCnEnhancedPath::CnEnhanced_analyzeSceneSpecific` (`0x10068bd0`)'s own scene order, ahead of `analyzeAutoTone` in the same sequence — that specific call-sequence citation I relied on rather than re-derived myself this session. On that basis: **filmLut is genuinely acquired and applied on the CN-Enhanced (colour-negative) path, not merely declared** — it's fatal-gated, so a real 135-negative run cannot skip it.

But directly checking `analyzeAutoTone`'s own 166-function reachable set: **none of filmLut's acquire/ctor/initialize addresses, nor `analyzePreBalance`/`balanceAreaImage`/`BalanceMethods_export`, appear in it.** `analyzeAutoTone` never calls `AnsFilmLutCapability::acquire` and never pushes `"filmLut"` anywhere in its own reachable code. So the task's framing ("`analyzeAutoTone` reads what filmLut published via `AnsSceneContext::find`") doesn't hold literally for filmLut: filmLut runs and finishes **earlier in the same scene pass**, and its effect (if any) is already baked into the pixel buffer `analyzeAutoTone` receives, not read live by it.

### 4. What it writes, and its plausible tone effect

filmLut's payload is a static per-(scanner, product, gen) **3-band (R,G,B), 4096-entry, 12-bit LUT**, loaded once by `Impl::initialize()`. It is **not** published into `AnsSceneContext` — I confirmed neither `acquire`'s nor `Impl::initialize`'s reachable set calls `AnsSceneContext::insert` (`0x10023f10`); `acquire`'s set does reach `AnsSceneContext::find` (read-only, incidental) but never writes. Instead, its capability object is fetched directly (by name, via the generic registry) and `balanceAreaImage` composes it — `filmLut_c ∘ scpLut_c ∘ shift_c ∘ fugc_c` per channel, per this repo's prior work — into one combined 3-band LUT applied straight to the area image's per-pixel RGB via `AnsImageData::applyLut` (`0x100d9340`). That is squarely per-pixel RGB/density math, in the same family as scpLut/sba-shift/fugc — not geometric, cosmetic, or orientation.

**On the shipped install specifically, its numeric effect is null**: `filmLut-scanner-prod-gen-default-default-default.lut` is previously established (`docs/58` row 17) as pure identity on all bands. So filmLut today is a real, executed, fatal-gated stage that currently contributes nothing numerically — a live no-op, not dead code.

### 5. Existing coverage in this repo: none

`grep -rn filmLut tools/` finds it only in comments (3 lines, `pakon_shasta.py:537`, `shasta.go:93`, `request.go:41/47`) — all citing the incorrect `0x10064d70` address, none of them ported code. No `pakon_filmlut.py`, no function, no test. Contrast with `fugc` (12/13 flags ported, real code) and `scpLut` (3/4 ported, real code in `pakon_scp_lut.py`).

### Verified vs. relied-on vs. undetermined
- **Verified by me this session, from the binary:** the `0x10064d70` correction, the real `declare()` address and its full 32-name order, filmLut's four class addresses, the absence of any analyze function, the 6 lookup sites and their gating string, all reachability numbers, and the (non-)overlap between filmLut's and `analyzeAutoTone`'s reachable sets.
- **Relied on from this repo's own prior [VERIFIED] work**, not re-derived this session: that `balanceAreaImage` composes and applies the 4-stage LUT via `AnsImageData::applyLut`; that `analyzePreBalance`/`balanceAreaImage` are literal steps of `CnEnhanced_analyzeSceneSpecific`'s scene order ahead of `analyzeAutoTone`; that CN-Enhanced (not CN-Premium) is what a 135 negative actually takes; that the shipped filmLut LUT is identity.
- **Could not determine:** the C++ identity of `fcn.1006a160` and `fcn.10113b50`; whether `balanceAreaImage`'s composed LUT reaches the final rendered output or only the scene-analysis pass (flagged open in `docs/58` §16.5 generally).