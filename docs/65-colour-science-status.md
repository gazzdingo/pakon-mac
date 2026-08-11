# Kodak colour science — living status

**This document is meant to be edited in place as work lands, not
rewritten.** When something moves from "not done" to "done": cut its row
from §2, add it to §1 with the same evidence links, and update the TL;DR.
Last touched: 2026-08-11 (Phase 2 of the `analyzeAutoTone` port — all six
tone subsystems now done; Phase 3 next).

Scope is the **colour rendering pipeline** specifically — raw sensor data to
final sRGB. Capture, transport, hardware safety and the app UI have their own
status elsewhere (`docs/54`, `docs/59`) and aren't repeated here.

## 0. If you're picking this up cold

The end goal is a **full native port of the F-135's colour science** — this
doc tracks progress toward that, not just one bug fix. Read in this order:

1. **`docs/66-autotone-port-plan.md`** — the current, actively-maintained
   execution plan for the in-progress `analyzeAutoTone` port, with a live
   phase-status table and exact resume instructions for whatever's
   incomplete right now (Phase 3, `citras`-apply, as of last touch). Start
   there, not here, if you're resuming that specific work.
2. **`docs/67-re-playbook.md`** — reusable patterns from this port that
   apply to the *next* one. Written with `area` (dust/scratch removal,
   likely "Digital Ice") specifically in mind, since that's the largest
   confirmed-real unported capability (`docs/64`).
3. This doc (`docs/65`) — the overall dashboard: what's done, what isn't,
   and why each gap matters.

Standing rules that apply to every task in this repo: never touch the
physical scanner (all RE work is static/emulated, radare2 + Unicorn);
`captures/` (the owner's personal photos) never gets committed, pushed, or
described in a report; calibrations are timestamped, never deleted; no
autonomous `git push`/PR without an explicit ask in the same conversation.

## TL;DR

The negative→positive inversion, the polynomial, FUGC, and the ICC step are
all verified working. The **one confirmed, currently-open defect** is the
tone stage: a mislabelled two-anchor stand-in is live where the real vendor
code (`ColorNegativePath::analyzeAutoTone`) should be, and it's the proven
cause of a visible shadow crush in every rendered frame. A cheap fix (FUGC)
was tried and measurably did not touch it — confirmed by a controlled
before/after test, not assumed. The real fix is a large reverse-engineering
project, currently being scoped (§3).

**Update, 2026-08-11**: the real port is now well underway, not just
scoped. The orchestration shell and **all six** tone subsystems (`cna`,
`dra`, `toneHelper`, `contrast`, `ast`, `citras`-analyze) are fully ported
and Unicorn-verified bit-exact against the real DLL — Phase 2 is closed.
What's left is `citras`-apply (Phase 3, 218 fn / 86,062 B) and the mandatory
assembled verification + render-path swap (Phase 6) — see `docs/66` for
exact status. None of this is wired into the render path yet by design (see
§2's first row); that happens only at the final assembled-verification
phase, deliberately last, matching how Shasta's port found its real bugs
only once everything ran together rather than leaf-by-leaf.

Separately, a scoping pass to find that fix's true size surfaced **14 more
capabilities** that are real, mostly-executing features of the scanner —
dust/scratch removal, vignetting correction, auto-rotation, sharpening,
source-type detection — that are currently 0% ported and simply do nothing.
None of them are on the critical path to fixing the crush, but they're real
functionality sitting unbuilt (§4), and the largest one (`area`,
dust/scratch/blemish removal — likely "Digital Ice") already has a
findings playbook waiting for whoever starts it (`docs/67`).

## 1. Done — verified, with evidence

| Stage | What's verified | Evidence |
|---|---|---|
| Sync / unpack | 6000 words/line, bit-0 sync flag, per-pixel R,G,B interleave (`plane_k = line[k::3]`) | `docs/45` |
| Per-pixel dark×gain | Mandatory for basic recognisability; column PRNU + lamp falloff dominate raw signal | `docs/46` |
| CCD trilinear deskew | R/G/B sensed on physically separate rows; measured offset (not vendor-derived — `CCD_DESKEW_PORTED=False` by design, there's no vendor table to match), both engines agree | `docs/46`, verified in both `pakon_decode.py` and `main.go` |
| Frame orientation | 180° lens rotation, settled by legible text (a shop sign reads correctly only rotated) — not a guess | this session, `ROTATE_180_FOR_LENS` |
| Stage-2 polynomial | `PolyPixel`, `TLB.dll:fcn.1000d880`, 3×10 quadratic — `c7=R·B`/`c8=G·B` (corrected from an earlier swapped citation), `R²`/`G²` kept unrounded on the x87 stack | `docs/58` §4 |
| Negative→positive inversion | The `c9` log formula: `rpd12 = fpo + 1000·(log10(base−c9) − log10(poly−c9))`. Not a DLL call site (`F135_INVERT_PORTED=False`) but empirically verified — confirmed correct by the owner's own eye on a real photo, and the literal alternative (apply the SRA LUT alone, as an earlier handover doc specified) was proven to produce a fully black image | `docs/58` §3.5/§16, this session |
| Film base measurement | `FindDmin`'s clipping window fixed — was reading CCD columns the vendor's own capture window never digitises (columns 0–29 at the wrong `pixel_offset`), now correctly measures inside the real film area | `docs/58` §3.4, `FILM_BASE_WINDOW_PORTED=False` (ours, verified, no vendor table to match) |
| SBA / Preference shifts | `PREFERENCE_SHIFTS_PORTED=True`, `SETSHIFTS_12_PORTED=True` — Unicorn-golden | `pakon_sba_preference.py`, `pakon_sba_apply.py` |
| FUGC | 12/13 flags ported. Two Go-side bugs (wrong map file, wrong bias formula) were already fixed; the third (a hardcoded branch that always took the unported mode-2 path) was found and fixed this session, verified bit-exact against the Python reference over 25 input combinations | `docs/62` §12.2, this session |
| ICC evaluation | Verified faithful: Go's hand-written evaluator and Python's littleCMS agree to within 0.3/255 on identical input, both rendering intents give identical results — the crush is proven **not** an ICC defect | this session |
| Stage order | `balance → FUGC → Shasta` is the vendor's real order, established from `AnsImaBuilder::getImaTransformGroup` / `AnsCnPremiumPath::exportParameterPack` — Go had it right, Python's `balance → Shasta → FUGC` was wrong and cost 90.7% of samples, mean 59–82 RPD codes, up to 792 | `docs/62` §12 |
| Ane / FOS / ColorAdjust / SceneContext infrastructure | ~79 individual `*_PORTED` flags across this machinery, Unicorn- or closed-form-verified | `docs/63` §4 |
| Shasta's own analyze **inner stage** | Fully Unicorn-verified end to end (not just leaf-by-leaf) — moot for rendering since Shasta is proven not on the colour-negative path at all, but the port itself is real and correct | `docs/63`, `pakon_shasta.py` |
| App renders through Go | The Electron app's real render path (`render_frame → _render_colour_go`) goes through a c-shared dylib via ctypes, not Python. Verified end-to-end on a real capture, not just the CLI. Python kept as an explicit, deprecated fallback (`PAKON_COLOUR_ENGINE=python`) | `docs/62` §12, `tools/pakon_colour_go.py` |

## 2. Not done — what it unlocks, and where the research is

### The one thing actually blocking accurate colour

| Gap | Unlocks | Status | Research |
|---|---|---|---|
| `ColorNegativePath::analyzeAutoTone` (`0x100fb730`) | **The actual fix for the shadow crush.** Confirmed the cause — the live stand-in clips 8.65% of its own toned output under code 257, and the crush measurably survives a correct FUGC (39.21%→39.19% shadow-region clipping, no real change) | **In progress, not a scoping exercise anymore.** Scope settled at 384 fns / 157,822 bytes / 879 indirect calls (not a range — `flesh` proven out of scope). Shell + all 6 subsystems done and Unicorn-verified (Phase 2 closed 2026-08-11); `citras`-apply (Phase 3) and assembled verification + render-path swap (Phase 6) not started. Nothing wired into the render path yet — deliberate, happens last. | `docs/66` (live plan + status), `docs/63`, `docs/64`, `docs/reports/autotone-scope-2026-08-10/` (22 raw reports) |

### Real scanner features currently doing nothing

Found while scoping the tone-stage port above — each of these is declared and (mostly) genuinely executing on the colour-negative path, just entirely unported. None block the crush fix; each is its own small-to-large project.

| Gap | Unlocks | Size | Research |
|---|---|---|---|
| `area` (`AnsAreaCapability` / `libAREA.ansel`) | **Dust, scratch and blemish detection/removal — almost certainly what the scanner's own "Frosty — Digital Ice Technology" badge refers to.** Confirmed running unconditionally on the colour-negative path. Currently entirely inert. | **732 functions / 299,737 bytes / 1,405 indirect calls — the single largest capability found on this project, 3.9× the whole tone chain** | `docs/64` |
| `falloff` | Per-pixel radial lens/scanner vignetting correction, sourced from calibration data. Unconditional, no film-class gate. | not yet measured in isolation | `docs/64` |
| `orderOrientation` | Auto-rotation classifier (`orderOrientationProb`/`frameOrientationProb`) | small — ~1/6 of Shasta's size | `docs/64` |
| `noiseTable` / `pnr` / `nra` | Sharpening and noise reduction — two distinct denoise operators (`pnr` a Laplacian-pyramid chroma/luma suppressor, `nra` a separate spatial kernel) plus the adaptive-sharpening amount table | `nra` ≈ 39 fns / 8.5K bytes; others unmeasured | `docs/64` |
| `dtt` | Source-type auto-classification (archive / digital / colour-positive / colour-negative) — confirmed genuinely executing | unmeasured | `docs/64` |
| `pan` | Panorama (letterboxed-frame) auto-detection | unmeasured | `docs/64` |
| `asea` | Real per-channel RGB LUT plus flare/contrast — genuinely tone-shaped, applied via a parallel path rather than the balance stage | unmeasured | `docs/64` |
| `filmLut` | Per-(scanner, product, generation) static 3-band LUT. Fatal-gated so it can't be skipped, but the shipped file is confirmed pure identity — a live no-op on this unit today, not a missing feature | 113 fns / 139,375 bytes (its acquire path) | `docs/64` |

### Balance / SBA / ColorAdjust — narrower gaps in otherwise-ported files

| Gap | Unlocks | Research |
|---|---|---|
| `SBA_CORE_PORTED` | The SBA orchestration core (the shift maths around it are already ported) | `docs/63` §1 |
| `ANALYSE_ROLL_PORTED` | Whole-roll balance/FPO/Preference maths | `docs/63` §1 |
| `SCP_LUT_BALANCE_PORTED` | SCP-LUT balance application (parsing and analyze leaves are already ported) | `docs/63` §1 |
| Kodak `SpCombineXforms` | One compose step inside the otherwise-ported ColorAdjust chain | `docs/63` §1 |
| `ImaUnsharpMaskOperation` apply | The unsharp-mask operator itself (its parameters/gate are already ported) | `docs/63` §1 |

### Infrastructure that unlocks *verifying* all of the above

| Gap | Unlocks | Research |
|---|---|---|
| Go CLI's full flag surface | `tools/pakon_parity.py` (the Go-vs-Python per-stage comparison harness) currently cannot run against the Go binary at all — a prior rebuild of `main.go` left only `-model`/`-tap-dir`. Restoring it unlocks continuous, automated proof that the two engines agree, catching the next regression before it ships rather than after | this session (`fugc` fix report) |

## 3. Open questions inside the `analyzeAutoTone` scope itself — RESOLVED

All of the below were open as of the original scoping pass and have since
been closed; kept here as a record, not a live list. For what's still
actually outstanding (implementation, not open questions), see `docs/66`'s
live status table.

- ~~Whether the 6 tone subsystems' own reachable code overlaps with the 166-function orchestrator already measured, or is fully additive~~ — resolved: all 6 are strict subsets, not additive. Core size is 166 fn / 71,760 B / 615 indirect, settled.
- ~~Whether `dei` is a genuine, silently-missing dependency of `toneHelper`~~ — resolved OUT, by execution order (`CalcDei` runs *after* `analyzeAutoTone` in the scene driver). `docs/64`.
- ~~A disputed branch in `dra`~~ — resolved by live Unicorn execution: a miss on `find("lighting")` continues normally, it isn't fatal. `docs/66`.
- ~~`flesh`~~ — resolved OUT, by exhaustive consumer-side proof (all 13 driver-state reads + all 73 indirect calls checked by hand). Not dead weight though — it's a real, already-located dependency of `area` if that ever gets ported. `docs/64` §"flesh — OUT", `docs/67` §8.
- ~~`citras`'s real per-pixel apply-time code~~ — confirmed real and separate (218 fn / 86,062 B, `CITRAS_APPLY_PORTED`), scheduled as Phase 3 in `docs/66`, not started yet.

## 4. Research index

| Doc | Contents |
|---|---|
| `docs/58-colour-pipeline.md` | The deep original trace — polynomial coefficients, TLA/TLB identification, stage citations |
| `docs/62-colour-engine-consolidation.md` | Go-vs-Python decision record, stage-order proof, ICC precision findings |
| `docs/63-port-status.md` | Full inventory of every `*_PORTED` flag in the tree (95 markers, 16 open) |
| `docs/64-pruned-tone-producers.md` | What each pruned capability actually does, in plain terms |
| `docs/reports/autotone-scope-2026-08-10/` | The 22 raw agent reports behind `docs/63`/`docs/64` — full addresses, byte counts, disassembly evidence |
| `docs/66-autotone-port-plan.md` | **Live** execution plan for the port in progress — phase status, exact resume instructions, conventions |
| `docs/67-re-playbook.md` | Reusable RE/verification patterns from this port, written for whoever ports `area` (digital ice / scratch removal) next |
