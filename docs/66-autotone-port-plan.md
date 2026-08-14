# Port `ColorNegativePath::analyzeAutoTone` — execution plan + live status

This is the working copy of the plan approved for this port. Unlike a
session-local plan file, this one lives in the repo so **any agent — a fresh
session, a different machine, a different Claude account — can pick this up
cold.** Keep it current: when a phase's status changes, edit its row here,
don't just leave it in a chat transcript.

**End goal this port serves**: a full native port of the F-135's real colour
science, not just this one stage. `analyzeAutoTone` is the current blocker
because it's the proven cause of the shadow-crush bug; once it's done, the
scanner still has real unported features (`docs/64`) — `area` (dust/scratch
removal, likely "Digital Ice") chief among them. See `docs/67` for what this
port has already learned that will transfer to that one.

## Live status (edit this table as phases complete)

| Phase | What | Status |
|---|---|---|
| 0a | Fix `dra` "miss is fatal" doc bug | done |
| 0b | Resolve whether `flesh` is a real input | done — OUT, see `docs/64` |
| 0c | Commit `tools/re/reachability.py`, restore Go parity CLI | done |
| 0d/0e | `contrast` + `ast` recon | done |
| 1 | Orchestration shell (`pakon_autotone.py`) | done, Unicorn-golden |
| 2a | `cna` subsystem | done, Unicorn-golden, all flags `True` |
| 2b | `dra` subsystem | **done**, Unicorn-golden, all flags `True` |
| 2c | `toneHelper` subsystem | done, Unicorn-golden (2 flags intentionally `False`, see note) |
| 2d | `contrast` subsystem | done, Unicorn-golden (1 flag intentionally `False`, see note) |
| 2e | `ast` subsystem | done, Unicorn-golden (2 flags intentionally `False`, see note) |
| 2f | `citras`-analyze | done, Unicorn-golden (`CITRAS_APPLY_PORTED` is separately Phase 3) |
| 3a | `citras`-apply scaffolding | **partial, honestly** — vtable/object layout + one mechanical bridge fn Unicorn-verified; `validate()` still not ported and the ctor/factory path still not sized, but `validate()` is no longer blocking Phase 3 as a whole (proven orthogonal to the pixel math, see below) |
| 3b | `citras`-apply tone-compose (`virtual_56`) | **done**, Unicorn-golden, `CITRAS_APPLY_TONE_COMPOSE_PORTED = True` (validation prefix + full per-pixel compute), see below |
| 3c | `citras`-apply avoidance-blend (`virtual_60`) | **done**, Unicorn-golden, `CITRAS_APPLY_AVOIDANCE_BLEND_PORTED = True`, see below |
| 3d | `citras`-apply luminance (`virtual_64`) | **done**, Unicorn-golden, `CITRAS_APPLY_LUMINANCE_PORTED = True`, see below |
| 3 (whole) | `citras`-apply, all together | **done** — `CITRAS_APPLY_PORTED = True` in `pakon_citras_apply.py`. `validate()` (`0x10167ae0`) stays `False`/unported but is deliberately excluded from the umbrella AND, with real evidence it's irrelevant to the ported math — see below |
| 4 | `flesh` port | n/a — Phase 0b ruled it out of scope |
| 5 | `docs/64` dei row cleanup | done |
| 6.1 | Assembled verification (this port's mandatory precedent step) | **done** (2026-08-11) — `AUTOTONE_ASSEMBLED_VERIFIED = True` in `pakon_autotone.py`; see below |
| 6.2 (Python-only pass) | Render-path swap (`pakon_ansel.py` only) + acceptance test | **attempted, NOT accepted** (2026-08-11) — `pakon_ansel.real_auto_tone()` landed and is wired behind `pakon_shasta.AUTO_TONE_PORTED`, which stays `False`; the shadow-clip NUMBER clears the noise band by a huge margin but the paired visual check (required by this doc's own "Verification summary") shows the rendered frame is visibly washed out / low-contrast, not a plausible correction — see below for the full evidence and why the switch was not flipped |
| 6.2 (stage-order investigation) | Root-cause pass on the washed-out result | **done (2026-08-11, second pass)** — found and fixed a real, independently-evidenced FUGC/tone stage-order bug in `render_scene` (see "6.2 continued" below), but confirmed by direct measurement that it does NOT explain the washed-out look on the reference frame. Extended Phase 6.1-style DLL verification to real-photo pixel data up to 1,048,576 real pixels — still bit-exact, further weakening "the port's analysis math is wrong" as an explanation. Found a new, more promising, NOT-yet-fixed lead: `real_auto_tone()` never calls the separately-ported `citras`-apply subsystem at all. `AUTO_TONE_PORTED` still stays as found (owner had it flipped `True` locally for comparison; not changed, not reverted, per this pass's brief) and the render still looks washed out. See below for the full evidence. |
| 6.2 (citras term/base driver recon) | Resolve how `analyzeAutoTone`'s tone LUT reaches `citras`-apply's `term`/`base` operands | **investigated, real mechanism found, NOT fixed, NOT flipped** (2026-08-11, third pass) — found and disassembled the actual citras render-time driver (`ImaCitrasOpBase`'s own `virtual_40`, vtable offset `0x28`/`0x10169350`, previously catalogued only as "inherited" with no further note) and the `AnsImaCitrasAggregate` constructor (`0x100ad7f0`) that wires an analyzed tone LUT into it via a `Tsc1DLutT` object. Neither of the task's two hypotheses is quite right — see "6.2 continued, third pass" below for the real, third answer, why it wasn't safe to port and land this session, and what was ruled out along the way. `real_auto_tone()` and `AUTO_TONE_PORTED` are both untouched by this pass. |
| 6.2 (citras driver operand wiring, live trace) | Live-Unicorn-trace `0x10169350` to pin down `virtual_60`'s `weight`/`reference`/`table` and `virtual_56`'s `term`/`base` | **fourth pass, real new live-execution evidence gathered, question NOT closed** (2026-08-11) — built a real Unicorn harness (canary `this`, forced past two live-confirmed validation gates) that got the genuine DLL bytes executing deeper into the driver than any prior pass, and pinned down, live, that the driver's own 2 stack args are operand-shaped (not `this`-fields) and that `this+0x110..0x128` is exactly citras's 8 scalar params at precise byte offsets. Also found strong static (self-naming, not yet live-pointer-confirmed) evidence of a real `ImaBlockAverageOp` block-blur between the luminance and avoidance-blend calls. Did NOT reach the three leaf calls -- blocked by a deep, multiply-chained generic "build an operand around an Ima2DImage" helper family (2000+ bytes across at least two functions) whose own field layout this pass did not finish mapping. See "6.2 continued, fourth pass" below. `real_auto_tone()` and `pakon_citras_apply.py` are both untouched -- no wiring landed, per this task's own explicit instruction not to guess. |
| 6.2 (citras driver operand wiring, live trace continued) | Finish mapping the accessor helper family the fourth pass got stuck in; reach the three leaf calls | **fifth pass, substantial new live-execution progress, `virtual_64` reached with real operand identities, `virtual_60`/`virtual_56` still NOT reached** (2026-08-11) — corrected a real bug in the fourth pass's own model (the coordinate-mapper object is `C`, the sub-object hanging off `B->0x28`, not `B` itself), found and fixed a project-wide latent bug in every prior pass's "dummy operand" mocks (bare-`ret` stub vtables silently corrupt the stack on any `push N; call [vtbl+slot]` pattern, of which this codebase has several), identified and stubbed four previously-unknown unbound CRT/Win32 import thunks (`time`, `InitializeCriticalSection`, plus reconfirmed `sprintf`/exception-ctor), and pushed the live trace deep enough to watch the real `virtual_64` (luminance) call fire with concrete operand identities, and past the exact point (`fcn.10168d90`/`fcn.100a4010`/`call [edx+0x34]`) the fourth pass named as its own recommended next step. Stopped at a NEW blocker inside `fcn.10328d20` (a real RTTI/status-validation gate on the block-average result) needing a properly RTTI-shaped dummy object this pass did not build in time. `virtual_60`/`virtual_56` were not reached; `real_auto_tone()` and `pakon_citras_apply.py` remain untouched, per the same explicit instruction. See "6.2 continued, fifth pass" below. |
| 6.2 (citras driver operand wiring, live trace continued again) | Get past `fcn.10328d20`'s gate; reach the three leaf calls | **sixth pass — pass 5's own diagnosis corrected, `fcn.10328d20`'s gate actually passed for the first time, but `virtual_60`/`virtual_56` still NOT reached** (2026-08-11) — single-stepped straight through the exact fault pass 5 attributed to "needs a properly RTTI-shaped dummy object" and found that diagnosis was wrong: the REAL cause was three more unbound CRT/C++-runtime thunks (`type_info::operator==`, `__RTDynamicCast`, `std::string::operator=`) plus a systemic bug in `make_smart_vtable` itself (`AddRef` hard-coded a `0` return instead of returning `this`, corrupting every dummy object's own smart-pointer chaining a few instructions after every single AddRef call — a real, generalizable fix, not case-specific). Fixing all four got `fcn.10328d20`'s RTTI gate to genuinely pass, then un-stubbing `fcn.100a3ed0`/`fcn.1032c0b0` (replacing them with stubs for the three live Registry APIs they call, `RegOpenKeyExW`/`RegQueryValueExW`/`RegCloseKey`, A/B-tested to confirm they're behaviorally inert) let real construction flow all the way through the real `ImaBlockAverageOp` ctor (`0x10154aa0`) and several real destructor-chain links (`0x1032a3c0`→`0x10359cc0`→`0x10359b50`→`0x1032da80`→`0x10338840`) — real, live-executing DLL bytes far beyond anything any prior pass reached. Stopped at a NEW, precisely-located blocker: a nested sub-object's own `+0x24` field, populated by one of three still-unexplored helper calls inside `fcn.1032c0b0` (`0x10343fa0`/`0x10359a60`/`0x10329f70`), holds a value whose own vtable slot 0 is a live DLL debug string's address rather than a function pointer — a real construction-completeness gap in this pass's own mock, not another unbound thunk. `virtual_60`/`virtual_56` were NOT reached; `real_auto_tone()` and `pakon_citras_apply.py` remain untouched. See "6.2 continued, sixth pass" below. |
| 6.2 (parallel track: FUGC/ColorAdjust/ICC range coverage, `scene_type`, histogram construction, `falloff`) | Four independent candidate-cause checks, run concurrently with the citras operand-wiring passes above, in files the citras passes don't touch | **done** (2026-08-11) — found and fixed a real gap (`pakon_fugc.set_lut_info_channel` raised on `offset < 0`; the real DLL handles it gracefully, live-Unicorn-confirmed bit-exact -32768..+5000; fixed, `pakon_fugc_golden.py` extended with 12 new cases, all pass); ruled out ColorAdjust (already full-domain-verified) and `scene_type` (well-evidenced as correct by elimination, and shown to have zero effect on `dra`'s separate lighting fork); re-confirmed the balance→FUGC→autoTone ordering into `real_auto_tone()` from a second, independent angle (the analyze-phase driver, not just the export-phase one the second pass used); found one new, not-yet-resolved lead (`analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff` all run between FUGC and `autoTone` in the real driver, none replicated here — unclear yet whether any mutate the pixel buffer `cna` subsequently reads); reasoned out `falloff` as a NEW-port-specific cause (equal-effect argument, as briefed); then, on explicit owner instruction to keep going rather than leave it as a tracked-but-open gap, traced `ImaICCXForm::apply`'s real caller chain (`PIFileOpenPlanar` → `0x100066d0` → `ImaICCEffectOperation`) and answered `docs/62` §12.6's ranked-#2 open question directly: the vendor's own literal DLL constants declare the ICC operand's domain as **[0.0, 65535.0]**, matching Go's `×65535/4095` choice, not a 12-bit or signed-16-bit domain — object construction live-Unicorn-confirmed, the final hop into `apply`'s own comparison inferred with high confidence but not itself live-traced (see below for exactly where the line is). None of this closes the washed-out mystery on its own — see "6.2 — parallel track" below for the full writeup. `pakon_ansel.py`/`pakon_citras_apply.py` untouched, per this pass's own scope. |
| 6.2 (top-down hypothesis pass: block-average + gradient-weight formulas) | Different strategy per this task's own brief — build a concrete hypothesis from all six passes' findings, isolate and directly disassemble the two still-unknown leaf computations instead of continuing the bottom-up driver trace, then try to verify live | **seventh pass, both formulas found and characterized by direct disassembly; live isolation attempted and blocked on a NEW, concrete structural finding for one of the two; full end-to-end driver bit-exact test NOT achieved** (2026-08-11) — found the real `ImaBlockAverageOp` compute body (`0x10154ea0`, vtable slot `0x28` off the block-average vtable `0x1058ddf4`) and confirmed by direct disassembly (two independent code paths: a `factor==2` fast path and the general `factor×factor` path) that block-average is a plain **non-overlapping box-filter downsample by `blockSize`**, correctly rounded. Found the real gradient/weight function (`0x10168f30`, called directly from the driver right after the block-average result is validated) and confirmed by disassembly that it (a) reads exactly `minAvoidance`/`maxGradient`/`lowGradientThreshold`/`highGradientThreshold`, (b) builds a byte lookup table via a cosine ease curve from 100 (full avoidance, smooth regions) down to `minAvoidance` (near edges) between the two thresholds, and (c) computes a per-pixel weight as `table[clamp(dx² + dy², 0, maxGradient)]` for two neighbour differences of an input plane — refining, not confirming verbatim, the task's own weight hypothesis (gradient-magnitude-driven, confirmed; exact neighbour offset/stride NOT pinned). Live single-function Unicorn isolation was attempted for both (per this task's explicit instruction to isolate rather than re-trace the whole driver) and hit two DIFFERENT concrete walls, both real findings in their own right: block-average's own subregion-accessor call dives straight into the same generic `Ima2DImage` coordinate-mapper machinery (`fcn.1032b9d0` → … → `0x1035d4fc`) that blocked passes 4-6, independently corroborating that this is the genuine bottleneck, not a lack of effort; the weight function turns out to be a compiler-outlined fragment sharing the DRIVER's own stack frame rather than an independently callable function (`ret 8` popping 8 bytes the driver's own call site never pushes; several of its "locals" are uninitialized outside the driver's exact call context) — a new, concrete structural fact, not present in any prior pass's writeup. Full end-to-end bit-exact driver verification (task step 2) was therefore NOT achieved. Per this task's strict instruction, `real_auto_tone()` was NOT wired to either formula (not verified bit-exact) and was not touched by this pass at all — see "6.2 continued, seventh pass" below for the full derivation, including the visual check of the current (orchestrator-landed, separately-documented) interim fix. |
| 6.2 (citras driver operand wiring, live trace — eighth pass) | Crack the shared coordinate-mapper / operand-accessor bottleneck four prior passes hit, OR run the gradient-weight fragment in native driver context instead of isolating it | **eighth pass — three new, concrete unbound-thunk bugs found and fixed (verified via targeted memory-write forensics, not guessing), live trace pushed substantially past the sixth/seventh pass's blocker into a SECOND full operand-wrapper construction that live-execution now shows builds a real, sigma-driven Gaussian-kernel table object — corroborating pass 7's disassembly-only gradient-weight/avoidance-table hypothesis with live evidence for the first time — but a NEW, precisely-located blocker stops it one level further in. `virtual_60`/`virtual_56` still NOT reached.** (2026-08-11) — see "6.2 continued, eighth pass" below. `real_auto_tone()` and `pakon_citras_apply.py` remain untouched, per the same standing instruction; no port code changed, only scratch harnesses in `/tmp/pakon_re/`. |
| 6.2 (citras driver operand wiring — ninth pass) | Close the operand wiring of `ImaCitrasOpBase::virtual_40` (`0x10169350`) and replace `real_auto_tone()`'s interim stand-in with the real mechanism | **RESOLVED and LANDED** (2026-08-12) — the wiring question eight prior passes could not close is answered, with instruction-level evidence, by *reading* the driver instead of trying to *run* it: full capstone disassembly of all 2,490 bytes with ESP tracked by hand through every `push`/`call`/`ret N` (the technique `CITRAS_APPLY_AVOIDANCE_BLEND_PORTED`'s own comment already records as mandatory in this function family), cross-checked against each of the four callees' own `ret N` — four independent agreements — plus a fifth check that the four operand TYPES the driver supplies match `virtual_60`'s already-verified per-slot roles one for one. Key finding: `virtual_60` writes a per-pixel luminance **DELTA** (its table is bias-subtracted for the duration of the call), which `virtual_56` then adds to all three bands and clamps — "process in luma, restore chroma", with the tone curve looked up not at the pixel's own luminance but at an index pulled toward a block-averaged/Gauss-blurred/upsampled reference by a gradient-driven weight. Also closes the third pass's open question about how a `setToneLut` LUT reaches a pixel (`AnsImaCitrasAggregate` ctor → `Tsc1DLutT<short>(ToneLut, lutSize, 1)`, bias 0, count `lutSize`, installed at `this->0x108`), and finds `bDoClipping` hard-coded to 1 by the op's ctor. **Four stages newly Unicorn-verified bit-exact**: the gradient-weight fragment `0x10168f30` (9 cases — pass 7's "not independently callable" conclusion disproved by simply calling it), `ImaBlockAverageOp`'s compute `0x10154ea0` (48 cases — and pass 7's rounding reading corrected: the bias is `floor(factor²/2)`, not `0.5`), all four upsample kernels (50 cases — and the resampler is bilinear-with-extrapolation, not nearest-neighbour), and the Gaussian kernel builder `0x10168d90` (exact for the shipped sigma, whose 49 doubles are embedded verbatim; NOT bit-exact for a recomputed sigma, x87 80-bit `exp`). `real_auto_tone()`'s interim block is **replaced wholesale** — the delta-broadcast turns out to have been the right shape, and the hand-tuned `0.90` darken is deleted, not replaced. Shadow-clip 25.45% → **0.13%**, 1266× the noise band. Visual check: the shadow crush this port exists to fix is genuinely gone and the frame is a plausible photograph, but it still reads too light — now cleanly isolated to the tone CURVE's output band vs the display mapping, with the apply mechanism eliminated and a new per-path-DPI hypothesis raised and measured out. See "6.2 continued, ninth pass" below. New files `pakon_citras_driver.py` / `pakon_citras_driver_golden.py`. |
| 6.2 (Go render-path swap) | `main.go`/`shasta.go` wiring | **explicitly deferred this pass**, not attempted — an owner-directed scope change kept this session Python-only so the port could be evaluated sooner; not cancelled |
| 6.2 (real-roll systemic crash, `cna.hist_resample`) | `pakon_cna.py`'s tone-analysis code raised `RuntimeError` on **100% of frames** (40/40) from a real scanned roll, distinct from and never triggered by the single `08_raw14.tiff` frame every earlier pass used | **fixed** (2026-08-11) — root-caused with live Unicorn tracing against the real DLL, using the actual real crashing histogram: a real dark-half edge-bucket histogram legitimately drives `hist_resample`'s `in_sigma` to NaN (a genuine x87 negative-variance rounding outcome, common on real photographic data, not rare — live-DLL-confirmed against the exact real histogram, not assumed). The real bug was that `hist_resample`'s resample loop kept `_ftol2`'s full 64-bit truncation result, where the real store (`0x1022ce98`, `mov dword [edx+esi*4], eax`) keeps only the low 32 bits — live-disassembly-confirmed, not inferred. Once NaN cascades through, that mismatch turned the real DLL's "integer indefinite" pattern (low dword 0, i.e. the resampled array comes back all zeros, live-DLL-confirmed) into `-2**63` per entry in the port, which is what made `analyze_image._half`'s crossing search walk unboundedly past `n_buckets` instead of converging at index 0 immediately, same as the real DLL does. Fixed by truncating to `i32(...)` at that store site. A second, adjacent bug in the same function was found and fixed along the way (not the crash itself, but the same class, in the same code path a NaN-sigma histogram reaches): `ratio`/`step`'s two divisions two lines down (`0x1022cdf5..0x1022ce07`, `0x1022ce33..0x1022ce3d`) were raw Python `/`, unwrapped by this file's own established `_x87_div` helper, so a `sig32 == 0.0` histogram raised `ZeroDivisionError` in the port where the real masked-exception x87 hardware produces a signed infinity/NaN — fixed the same way `_x87_div` already fixes this exact class of bug elsewhere in this file. Both fixes verified against the real DLL with the real crashing data (`hist_resample` called directly with the real 500-bucket histogram: DLL and fixed port agree exactly, 0/500 mismatches) and end-to-end (a real, unmodified, contiguous 1.8M-pixel crop run through the REAL `0x1022ddc0` top to bottom: `status=0`, real non-identity `ToneScaleLut`, port and DLL bit-identical). All 40 real frames re-rendered through the full Python colour chain after the fix: 0 crashes (was 40/40). Two new synthetic (not capture-derived) golden cases added to `pakon_cna_golden.py` reproducing the same real DLL behaviour bit-for-bit; the full existing golden suite (`pakon_cna_golden.py` plus all ten other fleet files) re-run clean, zero regressions. See `pakon_cna.py`'s `hist_resample`/`analyze_image._half` comments for the full derivation. |
| 6.2 (golden fleet — `colneg_1px remap TLA`) | The fleet's one standing failure, carried as "27 of 28 with a known off-by-one" since the second 6.2 pass | **RESOLVED and FIXED** (2026-08-12) — a real port bug in `pakon_scene_context.addscene_colneg_remap_dmin_rgb`, not a vendor quirk and not a tolerance issue. The case only ever compared two HOST functions to each other, so it could report a disagreement but never adjudicate it — that is precisely why it survived six passes as folklore. Root cause: the function re-derived F-235 stage 2 as `int(Σ_c coeff[k][c]*dens[c] / 8192 / 8 + offset[k])`, one division for the whole sum, where the kernel at `0x1001c684/87/8a` issues three independent `pmulhw` — each product truncated to its signed high word *before* the `paddsw`s. `Σ floor(x) ≤ floor(Σ x)`, so the old form ran exactly one code high whenever the three discarded fractions carried. The competing hypothesis (the x87 scalar tail at `0x1001c785`, documented as ±1 LSB) is **ruled out by evidence, not assumed**: TLA pushes `width=4` (`push 4` @ `0x1003f840`/`0x1003f85d`) and `0x1001c763`'s `and edx,0x80000003` + `je` skips the tail entirely when `width % 4 == 0`. Fixed by delegating to `pakon_color.render_pixel_f235`, whose own docstring had already flagged sum-then-divide as a different function (docs/58 §14.4). The golden case is upgraded from host-vs-host to a real Unicorn run of `PIColorCorrectColNegPlanarScan` (`0x100064d0`) on TLA's own planar `width=4`/`height=1` buffer, over 7 probes. Full fleet now 28/28; every other harness's output is byte-identical before and after. See "6.2 — golden fleet, `colneg_1px remap TLA`" below. |
| 6.3 | Go transcription of the six subsystems + `tools/pakon_parity.py` bit-exactness | **deferred this pass**, not attempted, for the same reason as above. Five parallel drafts (`autotone_cna.go`/`autotone_dra.go`/`autotone_tonehelper.go`/`autotone_contrast.go`/`autotone_ast.go`+`autotone_citras.go`+`autotone_citras_apply.go`) were produced and individually self-verified against Python by background agents earlier in this same session, then deliberately deleted (never committed) when the scope changed — nothing Go-related landed. Whoever resumes 6.3 is starting from a clean `tools/ansel/pipeline/` (verified `go build ./...` clean, `main.go`/`shasta.go` byte-identical to before this session), not from a half-finished state, but is also not inheriting that draft work — it was not preserved. Should almost certainly wait until 6.2's visual regression (below) is understood and fixed, so Go isn't transcribing a chain that produces a washed-out image. |

**Phase 2 is fully closed** (2026-08-11) — all six tone subsystems ported
and Unicorn-verified bit-exact against the real DLL: shell +
`cna`/`dra`/`toneHelper`/`contrast`/`ast`/`citras`-analyze.

**Phase 3 is now also fully closed** (2026-08-11, third pass) —
`CITRAS_APPLY_PORTED = True` in `pakon_citras_apply.py`. What's left for the
whole `analyzeAutoTone` port is **only Phase 6** (assembly + render swap +
acceptance test) — nothing else.

**Intentional `False` flags are not gaps.** `TONEHELPER_ACQUIRE_IMAGE_PORTED`,
`TONEHELPER_IMAGE_HISTOGRAM_PORTED`, `CONTRAST_SELECT_DPI_TREE_PORTED`,
`AST_DPI_PORTED`, `AST_EXPORT_PORTED` are all confirmed-dead-or-unreached
paths on `AnsCnEnhancedPath`, documented in their own file's comment next to
the flag. `CITRAS_APPLY_VALIDATE_PORTED` is a related but distinct case,
worth noting separately since it's the newest and rests on different
evidence: it is NOT confirmed dead/unreached (its real caller could not be
pinned down), but it IS confirmed to have zero field-level overlap with
anything the already-ported `citras`-apply math reads or writes, which is
why it's excluded from `CITRAS_APPLY_PORTED`'s AND — see its own comment in
`pakon_citras_apply.py` and the `citras`-apply section below. Don't "finish"
any of these without re-reading why they're `False` first.

### `dra` — closed out (Phase 2b)

`tools/ansel/python-pipeline/pakon_dra.py` has every flag `True`: entry
points, lighting branch/dispatch, DPI/TTC parse, results layout, rebin, lum
histogram, compose-tone, cumulative bounds, eff-bounds, `keepMidPtLut`, TTC
slope, `validate_params`, `alloc`, `generate_lut`, and both `analyze`
overloads — run from their **true entry points** (`0x1022af20`/`0x1022b530`)
under Unicorn, not a mid-function slice. `pakon_dra.py` now defines the
umbrella `DRA_ANALYZE_PORTED = True`, and `pakon_autotone.py` imports it
(`from pakon_dra import DRA_ANALYZE_PORTED`) rather than restating it — that
import was missing when the subsystem first landed (the file had a stale
hardcoded `False` with a comment claiming it was imported when it wasn't);
fixed directly once caught. `pakon_autotone_shell_golden.py`'s full suite
(including the not-found-fallback and `cap+0xf` checks across all seven
capability slots) passes with `dra` wired in live. Verify with:

```
PYTHONPATH=tools/ansel/python-pipeline python3 tools/ansel/python-pipeline/pakon_dra_golden.py
PYTHONPATH=tools/ansel/python-pipeline python3 tools/ansel/python-pipeline/pakon_autotone_shell_golden.py
```

One incidental finding from this pass, not a port bug: a synthetic
out-of-range pixel test (`[-2000, 4000]`) triggered genuine heap-adjacent
out-of-bounds histogram indexing **in the real DLL itself** — vendor
undefined behavior, not something the port introduced or needs to
replicate. Documented in the test, not "fixed."

### `citras`-apply — Phase 3 fully done (three passes, all 2026-08-11)

`tools/ansel/python-pipeline/pakon_citras_apply.py` +
`pakon_citras_apply_golden.py`. Reached from `ImaI16CitrasOp`'s vtable, not
from `analyzeAutoTone` — an entirely different call graph than every other
subsystem in this doc, confirmed and documented from scratch (class
hierarchy, COL/vtable addresses, per-slot roles).

**Second pass, cleanup of the two remaining `False` flags from the plan's
three named `virtual_56/60/64` candidates plus `validate()`:**
`CITRAS_APPLY_LUMINANCE_PORTED` landed (`virtual_64`, full re-derivation via
live Unicorn tracing, see below); `CITRAS_APPLY_VALIDATE_PORTED` was traced
substantially deeper but still did not land — a real, concrete blocker was
found (not just "ran out of time"), see below. A separate, genuinely stale
duplicate `CITRAS_APPLY_PORTED = False` that had accumulated in
`pakon_citras.py` (predating this file's existence as a split-out module,
with a comment claiming "still False and untouched") was also fixed this
pass: `pakon_citras.py` now imports the flag from `pakon_citras_apply.py`'s
own umbrella instead of restating it, the same pattern `pakon_autotone.py`
already uses for `pakon_dra.DRA_ANALYZE_PORTED` — see "Resolving the stale
`CITRAS_APPLY_PORTED` duplicate" below for why a plain top-of-file import
doesn't work here (a real circular-import hazard, confirmed by triggering
it, not just reasoned about) and how it was actually fixed.

**Third pass (this pass): asked whether `validate()` actually blocks
anything, rather than re-attempting the same full port.** Found real
evidence that it doesn't — see the `CITRAS_APPLY_VALIDATE_PORTED` bullet
below for the complete derivation. Result: the whole-file umbrella
`CITRAS_APPLY_PORTED` in `pakon_citras_apply.py` is now `True`. `validate()`
itself is still not ported and still raises if called — this is a claim
about the pixel math being real and bit-exact, not a claim that every
vtable slot has a body.

**What is Unicorn-verified (six `True`, `CITRAS_APPLY_PORTED` umbrella
`True`, `validate()` alone still `False` and deliberately excluded from that
umbrella):**

* `CITRAS_APPLY_OBJECT_LAYOUT_PORTED` — the full `ImaCitrasOperationBase ->
  ImaCitrasOperationT<short> -> ImaCitrasOpBase -> ImaI16CitrasOp` chain's
  COL/vtable addresses and `ImaI16CitrasOp`'s complete 17-slot table, located
  via the self-naming-RTTI-string method `docs/67` recommends (not static
  call-graph inference). Confirmed live: every slot dword, plus each COL's
  `pTypeDescriptor -> name` walk, read directly out of the loaded image under
  Unicorn. Four slots (offsets `0x18`/`0x38`/`0x3c`/`0x40`) override a
  `_purecall` thunk in the base — real binary confirmation of where the
  generic operand plumbing ends and the per-bit-depth pixel math begins.
* `CITRAS_APPLY_SET_TONE_LUT_PORTED` — `AnsCitrasOperand::setToneLut`
  (`0x10181ee0` — corrected from an initial `0x10181f00` guess that decoded
  mid-prologue and crashed the harness with an unset EBP; see the file's own
  docstring), the mechanical bridge that copies `citras`-analyze's already-
  verified LUT output into the apply-side operand. Structurally identical to
  `CITRAS_ANALYZE`'s own allocate+memcpy (same `operator new[]`, same error
  codes). 13 cases pass, including the "no realloc when lutSize is
  unchanged" behaviour and both error paths.
* `CITRAS_APPLY_AVOIDANCE_BLEND_PORTED` — **Phase 3c, done this pass.**
  `ImaI16CitrasOp::virtual_60` (`0x10168360`, 1,176 B). The Phase 3a recon
  one-liner ("a percentage-weighted, likely `minAvoidance`, gradient-
  avoidance blend") was treated as an unverified hypothesis per this task's
  instructions, and re-derived from scratch against the live disassembly —
  confirmed correct in overall shape but the exact formula, argument order
  and table-bias mechanics were NOT recoverable from that one-liner alone.
  Getting them right required manually walking ESP deltas through every
  push/call/`ret N` in the function with a capstone script, because both
  `r2 pdf` and `r2ghidra`'s `pdg` **mis-locate several stack locals** here
  (the function's ESP genuinely shifts underneath unbalanced push/call
  windows in a way neither tool's static analysis tracks correctly) — a new,
  concrete instance of `docs/67`'s "static reading invents patterns live
  execution disproves" lesson, this time catching the *tooling* rather than
  a one-off misread, worth folding back into `docs/67`.

  The real algorithm, per pixel: `diff = wrap16(value - reference)`;
  `weighted = weight*diff + 50`; `q = trunc_div(weighted, 100)` (confirmed
  bit-exact to the `0x51eb851f` magic-multiply idiom); `idx =
  wrap16(value - q)`; `out = table[idx]` — i.e. the avoidance blend and the
  shared tone/clamp table's lookup are fused into ONE pass, not two
  sequential steps as the recon phrasing implied. The table
  (`this->0x108`, a shared 65536-entry signed-int16 cache) is mutated in
  place for the call's duration (every entry's own index subtracted before
  the main loop, added back after) and the port replicates that exactly
  with a `try/finally`.

  Unicorn-verified bit-exact across 9 cases: weight=0 (identity-through-
  table), weight=100 and weight=255 with positive/negative diffs, per-pixel
  varying weight, non-contiguous strides (a sub-rectangle inside a larger
  canvas, proving the addressing generalizes beyond the trivial contiguous
  case), index wraparound past the int16 boundary, both `rows=0`/`cols=0`
  edge cases, and a larger 5x9 grid. One real bug caught by the golden
  harness itself before it passed: the table bias-subtract stored a SIGNED
  Python int where DLL memory holds an unsigned 16-bit word (`-24576` vs
  `40960` — the same bit pattern, wrong representation), causing exactly
  half the table's post-call entries to mismatch while every actual pixel
  output still matched; fixed by masking to `& 0xFFFF` on write. No FPCW
  concern — the function's disassembly contains zero x87 instructions.
  Generic COM-style refcount/Release cleanup at the function's tail
  (four `func_0x100012e0` calls) is deliberately not modelled: it has zero
  effect on any pixel value or the table's restored state, and the golden
  harness stubs it to always report "still referenced" so the associated
  `vtable[0]` Release calls are provably never reached, matching this same
  file's own `setToneLut` precedent.

* `CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED` — the null/type/dims/band-count
  VALIDATION PREFIX of `virtual_56` (`0x10167bf0`..`0x10167d38`) — all four
  of the function's own return codes (`-1`/`-2`/`-3`/`0`) and the exact
  six-check dims/band-count order, 12 cases passing. Carried over unchanged
  from the prior pass.
* `CITRAS_APPLY_TONE_COMPOSE_PORTED` — **Phase 3b, done this pass.**
  `ImaI16CitrasOp::virtual_56` (`0x10167bf0`, 1,897 B), the FULL function
  including the per-pixel compute the prior pass left unresolved. The
  blocker the prior pass left — whether `fcn.10092880`/`fcn.100928b0`
  return refcounted "locked resource" handles or plain integers — was
  closed with LIVE Unicorn single-stepping (constructed real operand/
  accessor objects with executing vtable stub code, not more disassembly
  reading), per this task's explicit instruction. Resolution: they are
  fully self-contained, fully-understood functions that each call the
  operand's own `count(a, b)` accessor (the SAME vtable slot
  `apply_avoidance_blend` already established) with a fixed `(1,0)`/`(0,1)`
  pair and divide the byte result by the sample size — i.e. plain unsigned
  ELEMENT-STRIDE integers (col-stride, row-stride), not handles. The prior
  pass's "handed to the same release routine as operand pointers" clue was a
  real observation but a wrong inference: what's actually released there
  are three LOCAL SMART-POINTER COPIES of `base`/`correction`/`term`
  themselves (confirmed live: `*ecx` at each of the three release calls was,
  in order, the real `base` pointer, NULL, and the real `term` pointer) — an
  ordinary "release my by-value smart-pointer argument copies" pattern,
  unconnected to `fcn.10092880`/`fcn.100928b0`.

  Live tracing also caught TWO real corrections to the prior pass's static
  reading, not just filled in the missing piece:
  1. **It is `term` (`arg_68h`) that is mutated in place, not `base`
     (`arg_60h`)** as previously documented — proven directly, not
     inferred: two operands were given independently-addressed real memory,
     the real DLL bytes executed, and only `term`'s buffers changed; `base`
     came back byte-for-byte identical in every case. A negative control
     confirmed this is load-bearing: temporarily swapping the port to write
     `base` instead made the golden harness fail immediately and
     specifically (both the "term differs" and "base should be read-only"
     checks fired), then was reverted.
  2. **Previously undocumented**: `term`'s band count is validated to be
     exactly 3, but `base`'s only has to be `<= 3`. When `base.band_count`
     is 1 or 2, the per-pixel loop still processes all 3 `term` bands, but
     reads `base` band `min(band, base.band_count - 1)` — i.e. base's LAST
     available band is broadcast across every term band it doesn't itself
     have, not skipped or zero-filled. Also confirmed load-bearing with its
     own negative control (swapping to `band % base.band_count` made the
     `band_count=2` case fail specifically, `band_count=1` still passed
     coincidentally — both reverted after confirming).

  The per-pixel formula, live-verified bit-exact across 7 cases (plain
  wraparound add both signs, inclusive clamp boundaries, negative clamp
  bounds, `base.band_count` in `{1, 2, 3}`, and a larger 6×5 grid), plus an
  invariant check that every `getPtr()` call the DLL made really was
  `(row=0, col=0, band)`:
  ```
  baseBand = min(band, base.band_count - 1)
  s = wrap16(term[r,c,band] + base[r,c,baseBand])   # 16-bit wraparound add
  if this->0x124 (byte) == 0: term[r,c,band] = s     # no clamp
  else: term[r,c,band] = clamp(s, movsx16(this->0x126), movsx16(this->0x128))
  ```
  (`this` really is the `ImaI16CitrasOp` object itself — confirmed live,
  including catching an off-by-one-instruction breakpoint-placement trap
  that briefly made it look like a different pointer.) The small-vs-large
  65536-entry-LUT clamp strategy the DLL sometimes takes internally is
  confirmed (by direct disassembly reading of the LUT-fill algorithm, a
  textbook saturating-clamp table) to produce identical output to the direct
  formula either way, so the port always uses the direct formula and does
  not model the internal LUT. No FPCW concern: the whole 1,897-byte function
  contains zero x87 instructions. Verify with
  `pakon_citras_apply_golden.py`'s `check_tone_compose_full`.
* `CITRAS_APPLY_LUMINANCE_PORTED` — **Phase 3d, done this pass.**
  `ImaI16CitrasOp::virtual_64` (`0x10168800`, 664 B). The Phase 3a recon
  one-liner ("its ABI takes a struct holding four nested, independently-
  vtable-dispatched operand objects") was proven WRONG once actually traced
  live under Unicorn — treated as a hypothesis per this task's own
  instructions, exactly the same lesson `virtual_56`'s "which operand
  mutates" correction already taught this file once. The real signature is
  `thiscall(this, source: 3-band I16 operand, dest: 1-band I16 operand)` —
  TWO operands, not four; `this` itself is never dereferenced for anything
  but the vtable dispatch that reached the function. The arithmetic WAS
  correctly guessed: `(R + G + B + 1) / 3`, truncating toward zero, the
  identical `0x55555556` magic-multiply idiom already ported in
  `pakon_dra.lum_histogram`. The real, previously-undocumented finding is
  the LOOP BOUNDS: they are `source`'s own width/height, not `dest`'s —
  confirmed with four independent live probes (dest smaller than source:
  the extra source pixels silently overwrite dest past its own declared
  size, using dest's own stride, a real vendor UB pattern in the same
  family as `dra`'s already-documented out-of-bounds histogram bug, not a
  port concern; source smaller than dest, with a padded sentinel region
  behind dest's buffer: proves the DLL's own writes stop exactly at
  source's dimensions, leaving cells within dest's own larger declared
  bounds provably untouched; both `rows=0`/`cols=0` edge cases; a 1x1 case).
  `getPtr()`/`getOffset()` addressing and the `count(1,0)`/`count(0,1)`
  stride accessors are the SAME protocol `virtual_56`/`virtual_60` already
  established (row/col args to `getPtr` are always `(0,0,band)`, base
  address is `getPtr() + getOffset()`), confirmed independently here too.
  No FPCW concern: the whole 664-byte function contains zero x87
  instructions. Unicorn-verified bit-exact across seven cases (plain grid,
  1x1 minimal, negative/boundary pixel values exercising the truncating
  division's sign correction, both zero-trip-count edges, and the two
  mismatched-dimension cases that pin down the source-bounds finding). See
  `pakon_citras_apply.py`'s `CITRAS_APPLY_LUMINANCE_PORTED` comment for the
  full derivation and `pakon_citras_apply_golden.py`'s `check_luminance`.

* `CITRAS_APPLY_VALIDATE_PORTED` (`0x10167ae0`, 261 B) — **still `False`,
  not ported, but now proven irrelevant to the pixel math and excluded from
  the umbrella (third pass, 2026-08-11).** The earlier passes' findings all
  stand and are not contradicted: a THIRD, earlier gate
  (`func_0x10328950(this->0x104, other_operand)`, checking `this->0x104`, an
  "Ima2DImage reference" no other citras-apply function touches) precedes
  the I16/band-count checks, and the "true" return path calls a 295-byte
  function (`func_0x10328560`) before returning. Reaching any failure path
  requires a full MSVCP71 STL exception/logging subsystem
  (`std::basic_ostringstream` formatting, `std::string` construction,
  `ctime`/`InitializeCriticalSection`), an order of magnitude past what any
  other citras-apply function needs mocked — still judged out of budget to
  fully port, and still not attempted.

  **This pass asked a different question instead of retrying the same full
  port, per its own instructions: does skipping `validate()` change anything
  the already-ported math (`tone_compose`/`apply_avoidance_blend`/
  `apply_luminance`) actually computes?** Two things were checked directly,
  not assumed:

  1. *Call-graph position* — genuinely could not be pinned down with
     confidence, reported honestly rather than rounded either way. `validate`
     has zero direct (E8) call sites anywhere in the 7,598,080-byte image
     (exhaustive scan, every section), and the literal vtable address
     `0x10580824` (`ImaI16CitrasOp`'s own) is referenced exactly once in the
     whole binary — its own constructor — so nothing statically narrows a
     pointer to "this is really an `ImaI16CitrasOp`" before dispatching
     through it. The real caller is therefore some generic, base-class-typed
     driver this pass went looking for and did not conclusively find. One
     near-miss worth recording in `docs/67`: a structurally identical-looking
     function (`0x10165a80`, reads a `+0x104` field, dispatches vtable
     offsets `0x38`/`0x3c`/`0x40` on `this`) turned out, via its own
     self-naming error string, to belong to `ImaArfOpBase` — an unrelated
     sibling class in the same generic template family — not
     `ImaCitrasOpBase`/`ImaI16CitrasOp`. Caught before being written down as
     a finding, a fresh, concrete instance of "coincidental structural
     resemblance across sibling classes" to add to `docs/67`'s existing
     "static reading invents patterns live execution disproves" lesson.
  2. *Field-level dependence* — this part WAS pinned down, directly. Every
     already-ported function's complete read/write set is independently
     known: `tone_compose` touches `term`/`base` pixel data plus
     `this->0x124/0x126/0x128`; `apply_avoidance_blend` touches its four
     operand planes plus `this->0x108`; `apply_luminance` touches only
     `source`/`dest` pixel data, no `this->` field at all. `validate()`
     gates on `this->0x104` — a field none of the three math functions
     reads. Its success path's only persistent-state write (read directly
     this pass) is a generic type-descriptor CACHE slot on the OTHER
     operand argument (not `this`), the same "lazily cache a type token on
     first use" idiom this file already treats as harmless elsewhere — not
     `this->0x108`/`0x124`/`0x126`/`0x128`. Checked the other direction too:
     `tone_compose` calls vtable offset `0x18` zero times; the eight offset-
     `0x18` calls inside `apply_avoidance_blend`/`apply_luminance` are all
     already-verified operand `getOffset()` accessor calls, never a call to
     `this`'s own `validate()` slot. Zero overlap, either direction, by
     direct inspection.

  Structural corroboration: each of the three already-ported math functions
  carries its own complete, independently Unicorn-verified input validation
  that duplicates what `validate()` also checks (I16 type, band-count==3) —
  they do not trust `validate()` to have already run. **Conclusion:** whether
  or not some unidentified caller invokes `validate()` first, doing so has
  proven zero effect on the already-ported pixel math's output. Calling
  `validate()` directly still raises — the function itself is not ported —
  but `CITRAS_APPLY_PORTED` no longer waits on it. See
  `pakon_citras_apply.py`'s `CITRAS_APPLY_VALIDATE_PORTED` comment for the
  complete evidence, and its `CITRAS_APPLY_PORTED` comment for how the
  umbrella now excludes it (the same "exclude a real, still-`False` flag from
  the umbrella, with a comment saying why" move `pakon_toneHelper.py`'s
  `TONEHELPER_ANALYZE_PORTED` already made for `TONEHELPER_ACQUIRE_IMAGE_
  PORTED` — except that precedent rests on provable dead-path unreachability,
  and this one rests on a field-level independence proof instead, since
  reachability itself could not be pinned down. Stated plainly, not blurred.)

**Resolving the stale `CITRAS_APPLY_PORTED` duplicate.** `pakon_citras.py`
(which existed before `pakon_citras_apply.py` was split out) had its own
hardcoded `CITRAS_APPLY_PORTED = False` with a comment claiming it was
"still False and untouched by this task" — stale and silently disagreeing
with (or coincidentally matching, by luck, since both happened to be
`False`) the real flag of the same name in `pakon_citras_apply.py`. Fixed by
having `pakon_citras.py` import the flag from `pakon_citras_apply.py`
instead of restating it, the same pattern `pakon_autotone.py` already uses
for `pakon_dra.DRA_ANALYZE_PORTED`. This was NOT a drop-in copy of that
pattern, though: a plain top-of-file import created a genuine circular
import (`pakon_citras_apply.py` itself did `from pakon_citras import
CitrasStatus` at ITS OWN module level) that deadlocked in one import order
— confirmed by actually triggering it (`import pakon_citras_apply` alone,
fresh interpreter, raised `ImportError`), not just reasoned about
abstractly. Fixed on the `pakon_citras_apply.py` side: `CitrasStatus` is now
imported lazily, inside `apply_set_tone_lut` itself (the only place that
file constructs one), not at module load time, which breaks the cycle
regardless of which module a caller imports first. Both orders re-verified
directly after the fix. `CITRAS_APPLY_PORTED` (the umbrella) is now `True`
in both files (`pakon_citras.py` imports it, doesn't restate it) — see the
`CITRAS_APPLY_VALIDATE_PORTED` bullet above for why excluding that one flag
from the umbrella is a real, evidenced conclusion, not a rounding-up.

**Honest gap, not a claim**: the direct-call closure of all five addresses
the prior pass found (validate/56/60/64/setToneLut) is 97 functions / 17,182
bytes (`tools/re/reachability.py walk`) — well under half of the previously-
reported 218 fn / 86,062 B for the whole apply subsystem. The remainder is
almost entirely behind indirect (vtable) dispatch through the generic
operand-accessor machinery, which a direct-call-only BFS cannot see; this
pass verified `virtual_60`'s own body bit-exact by mocking that generic
accessor protocol at the vtable-slot level (stubbing what each accessor
call RETURNS, not re-implementing how the real accessor computes it) rather
than tracing it, the same scoping choice `setToneLut` already established.
The object-construction/factory path that actually builds an
`ImaI16CitrasOp` was located (vtable install at `0x100ae947`) but not
sized — a linear-sweep probe landed inside one ~25 KB function span that is
very likely several merged functions (an `af`-boundary-detection artefact,
see `docs/67` §6), so no real size number for it is reported. Verify with:

```
PYTHONPATH=tools/ansel/python-pipeline python3 tools/ansel/python-pipeline/pakon_citras_apply_golden.py
```

## Context (why this port exists)

The F-135 colour pipeline's negative→positive inversion, polynomial, FUGC and
ICC stages are all verified correct. The one remaining confirmed defect is a
mislabelled two-anchor stand-in (`ShastaToneRpd` in Go,
`shasta_two_anchor_tone` in Python) sitting where the real vendor tone-curve
stage — `ColorNegativePath::analyzeAutoTone`, `PakonIMAu.dll` VA
`0x100fb730` — should be. It's the proven cause of a visible shadow crush in
every rendered frame: the stand-in clips 8.65% of its own toned output under
code 257, and a correct FUGC fix already proved the crush is downstream of
FUGC entirely (39.21%→39.19% shadow-region clipping — ruled a fail, not an
improvement).

**Scale, stated plainly:**

| | functions | bytes | indirect calls | vs. Shasta (189/44,427/386) |
|---|---|---|---|---|
| Confirmed scope (core 166 + citras-apply 218) | 384 | 157,822 | 879 | ~2.0× fn / ~3.6× bytes / ~2.3× indirect |

(`flesh` is confirmed OUT — see `docs/64` — so the earlier ~751-function
ceiling doesn't apply; this is a settled number, not a range.)

This is realistically 8–11 Shasta-sized-or-smaller sub-efforts plus one
mandatory assembled-verification pass. Shasta itself found 5 real bugs only
at that final assembled step, not leaf-by-leaf — budget for the same here.

## Conventions to follow exactly

- **Live stand-in call sites** (what gets replaced, only once verified): Go
  `tools/ansel/pipeline/main.go:565`, impl `tools/ansel/pipeline/shasta.go:223`.
  Python `tools/ansel/python-pipeline/pakon_ansel.py:690` (inside
  `render_scene`, guarded by `self.shasta_stand_in`), impl `pakon_shasta.py`.
  **Neither has been touched yet** — confirmed by direct grep, most recently
  2026-08-11. Do not touch either until Phase 6.
- **Unicorn "golden" harness, two shapes**: a simple leaf-call harness
  (`pakon_shasta_curve_golden.py`) for pure arithmetic, and a full-orchestrator
  `Emu`-class harness (`pakon_shasta_analyze_golden.py`) for real entry points
  with a bump-allocator heap, CRT stubs, and `hook()`/`watch()` interception.
- **FPCW must be `0x027F`** (MSVC/Windows extended precision) — Unicorn's
  default silently diverges from the real DLL on x87 code. Every subsystem
  ported so far needed this. See `docs/67` for the full pattern and how to
  prove it with a negative control.
- **File/flag convention**: one `pakon_<subsystem>.py` per subsystem (port +
  flags), paired with `pakon_<subsystem>_<piece>_golden.py` files split by
  verification difficulty. `SCREAMING_SNAKE_CASE_PORTED = True/False`, each
  `False` flag commented with exact VAs, reachability numbers, and why it
  isn't ported yet. `False`-flagged functions `raise RuntimeError` if called
  (pattern at `pakon_shasta.py:2404-2405`) — never silently no-op. **Python is
  the conversion path from the vendor DLL** — it's what Unicorn (a Python
  library) can verify bit-exact against real DLL execution — so all new
  reverse-engineering lands in Python first. Go gets the verified result
  ported over afterward, as terse constants, and compiled down for the
  performance the render path actually needs. This is a staged pipeline, not
  Python being a lesser or deprecated engine: **Go is currently lagging
  Python for the colour science** (see `docs/65`'s render-path row) simply
  because Phase 6's Go transcription hasn't happened yet for this port.
  Intentional asymmetry, already established by the Shasta port.
- **Binary access**: `research/sdk/PAKONF135.iso` (171MB, gitignored) is not
  pre-extracted anywhere — extract fresh to a scratch dir per task (`7z x` or
  mount+copy, both attested). Canonical path once extracted:
  `fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`, MD5
  `eea9dcf78ee21d4f7c515a6c2512242d`. `vendor/ansel/anselinstalldir/dataPathItems/{cna,dra,toneHelper,contrast}/`
  DPI data is already committed; `ast`/`citras` have no DPI files in a full
  install — confirmed built-in constants.
- **Tests**: no pytest — narrative "why this exists, root-caused to a real
  bug" comments (`dmin_test.go`, `cabi_test.go` style). Golden-file
  DLL-exactness stays separate from behaviour-regression tests.
- **Model tiering** (explicit user instruction): build with Sonnet, review
  with Opus only if needed. Cost-conscious by design — don't default to the
  most expensive model for mechanical port work.
- **Standing rules that apply to every task in this repo, not just this
  port**: never touch the physical scanner for any of this — it's all
  static/emulated (radare2 + Unicorn); `captures/` (the owner's personal
  photographs) never gets committed, pushed, or described in any report,
  ever; calibration data is never deleted, only timestamped; no autonomous
  `git push`/`gh pr create` without an explicit ask in the same
  conversation; check `git status`/`git diff` before any push, always as an
  explicit file list, never `git add -A`.

## Litter to check for before any commit

Scratch files from earlier sessions sometimes sit untracked at repo root —
seen so far: `patch_sed8.py`, `replace.txt`, `tools/ansel/pipeline/patch_main.py`,
`taps/`. These are one-off sed/patch scripts and scratch output, not part of
the port. Check `git status` and leave them out of any commit unless you've
confirmed they're meant to land.

## Phase definitions

**Phase 0** — prerequisites, see status table above; all done.

**Phase 1 — Orchestration shell.** `analyzeAutoTone` itself minus the six
subsystems' own bodies: the tone object threaded via `ctx+0x64d0` (seeded 0 at
`0x100fb787`) plus `ctx+0x4bc`; the six acquire→enable-byte(`+0xc`)→dispatch
blocks; `pfd`'s confirmed-dead seventh slot (acquire-but-skip, kept — its
absence may be load-bearing for object layout); the `AnsSceneContext::find`
lookup/RTTI/not-found-fallback pattern. Done — `pakon_autotone.py` +
`pakon_autotone_shell_golden.py`.

**Phase 2 — The six subsystems.**

| Task | Entry | Status |
|---|---|---|
| cna | `0x1022ea50` | done |
| dra | `0x1022af20` (image) / `0x1022b530` (hist) | in progress, see above |
| toneHelper | `0x101dd1b0` (live histogram-fed path — corrected from an earlier brief that had this backwards) | done |
| contrast | `0x101d8880` (wraps `0x101d8240`) | done |
| ast | `0x10227160` | done |
| citras-analyze | `0x10223a20` (corrected from `0x10223860`, which decodes to garbage mid-instruction) | done |

**Phase 3 — citras-apply** (218 fn / 86,062 bytes — bigger alone than
Shasta). Split explicitly, not attempted as one task: **3a** scaffolding
(class/vtable plumbing, object layout, whichever of `virtual_56/60/64` turns
out mechanical); **3b** (`virtual_56`, tone-compose), **3c** (`virtual_60`,
avoidance-blend) and **3d** (`virtual_64`, luminance) the three genuinely-
unnamed-math virtuals — independent recon-plus-port tasks, not
pre-estimated. Depends on 2f for the object shape it consumes. **3b, 3c, 3d
are all done** (2026-08-11); **3a stays partial** (`validate()` and the
object-construction/factory path are still not ported) **but no longer
blocks Phase 3 as a whole** — see below for why. **Phase 3 overall is done**,
`CITRAS_APPLY_PORTED = True`.

**3a is partial** (2026-08-11, all three passes) — see "`citras`-apply —
Phase 3 fully done" above for the full breakdown. Object/vtable layout is
Unicorn-verified; `AnsCitrasOperand::setToneLut` (the one genuinely
mechanical bridge function found) is ported and Unicorn-verified.
`validate()` (`0x10167ae0`) was traced substantially deeper in the second
pass (roughly a dozen of its ~83 reachable functions read directly, not
just the two already-known checks) and still NOT ported: the real blocker
is a full MSVCP71 STL exception/logging subsystem reachable from every
failure path, plus an only partially-mapped `this->0x104` dependency on the
success path. A third pass then asked whether that blocker actually matters
to the port's job (replicating the real per-pixel math bit-exact) rather
than re-attempting the same full port, and found real evidence it doesn't —
see "Resolving the stale `CITRAS_APPLY_PORTED` duplicate" and the
`CITRAS_APPLY_VALIDATE_PORTED` bullet above for the complete derivation. Of
the plan's three named candidate slots, all three are resolved:
`virtual_56` and `virtual_60` are the genuine math (1,897 B / 1,176 B own
body each, ported and Unicorn-verified); `virtual_64` looked mechanical (a
known, simple luminance formula) and turned out to genuinely BE mechanical
once the real (two-operand, not four-operand) ABI was traced live — also
ported and Unicorn-verified.

**3c is done** (2026-08-11) — `virtual_60` (avoidance-blend) ported and
Unicorn-verified bit-exact; see "`citras`-apply — Phase 3 fully done" above
for the full derivation and verification breakdown.
`CITRAS_APPLY_AVOIDANCE_BLEND_PORTED = True`.

**3b is done** (2026-08-11) — `virtual_56` (tone-compose) ported and
Unicorn-verified bit-exact, both the validation prefix
(`CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED = True`, carried over) and the
per-pixel compute the prior pass left unresolved
(`CITRAS_APPLY_TONE_COMPOSE_PORTED = True`, resolved via live Unicorn
tracing, not more static reading). Two real corrections to the prior pass's
recon came out of that live trace: it is `term` that gets mutated in place,
not `base`; and `base`'s band index is broadcast-clamped (`min(band,
base.band_count - 1)`) when it has fewer than 3 bands. Both confirmed
load-bearing with dedicated negative controls. See "`citras`-apply — Phase
3 fully done" above for the full derivation and verification breakdown.

**3d is done** (2026-08-11) — `virtual_64` (luminance) ported and
Unicorn-verified bit-exact, `CITRAS_APPLY_LUMINANCE_PORTED = True`. The
Phase 3a recon's four-operand ABI guess was disproven live (the real
signature takes two operands, source and dest); the real, previously
undocumented finding is that the loop bounds are `source`'s own
width/height, not `dest`'s. See "`citras`-apply — Phase 3 fully done"
above for the full derivation.

**Phase 3 as a whole is done** (2026-08-11, third pass) —
`CITRAS_APPLY_PORTED = True` in `pakon_citras_apply.py`. `validate()`
(Phase 3a) is still not ported, but a third pass proved its outcome and
success-path side effect have zero overlap with anything the already-ported
math reads or writes, so it is deliberately excluded from the umbrella's
AND rather than blocking it — see the `CITRAS_APPLY_VALIDATE_PORTED` bullet
above for the complete evidence. This closes out Phase 3 entirely; **only
Phase 6 remains for the whole `analyzeAutoTone` port.**

**Phase 4 — `flesh`.** Ruled out in Phase 0b. No work here.

**Phase 5 — `dei` doc cleanup.** Done, see `docs/64`.

**Phase 6 — Mandatory assembled verification (strictly last).**

**6.1 is done** (2026-08-11). Full Unicorn bit-exactness of the *assembled*
chain (Phase 1 shell + all six Phase 2 subsystems; Phase 3 `citras`-apply is
NOT reachable from `analyzeAutoTone` and is correctly out of scope here, see
its own section above) against real DLL execution, compared field-by-field
via `AUTOTONE_WORK_LAYOUT` plus every subsystem's own full result object and
every LUT/histogram array. `AUTOTONE_ASSEMBLED_VERIFIED = True` in
`pakon_autotone.py` — **not** the same flag as `pakon_shasta.AUTO_TONE_PORTED`
(still `False`, untouched; that one is Phase 6.2's job).

New file: `tools/ansel/python-pipeline/pakon_autotone_assembled_golden.py`.
Unlike every other golden file in this port, it drives the real DLL's
`0x100fb730` with **no subsystem entry points hooked or stubbed** — the real
Cap wrappers fall all the way through into the real `cna`/`dra`/`toneHelper`/
`contrast`/`ast`/`citras` Impl bodies for real, in one Unicorn call — and
compares that against `pakon_autotone.analyze_auto_tone` driving a real,
non-stub `AutoToneSubsystems` (its `*_acquire`/`*_analyze` methods already
call straight into the six ported subsystems once every `*_PORTED` flag is
`True` — nothing new had to be built there, Phase 2/3 already left it wired).
7 scenarios: flat/uniform, gradient, high-contrast banded, two pseudo-random
images at realistic pixel counts, and two `scene_type` variants — all pass.
FPCW `0x027f` re-confirmed load-bearing for the ASSEMBLED run specifically
with its own negative control (forcing Unicorn's default `0x0000` produces
real divergence in `dra`/`contrast`/`ast`/`citras`'s output), not just
inherited from each subsystem's own earlier proof. Verify with:

```
PYTHONPATH=tools/ansel/python-pipeline python3 tools/ansel/python-pipeline/pakon_autotone_assembled_golden.py
```

**Two real integration-class bugs were found and fixed** — exactly the kind
this step exists to catch, neither visible to any subsystem's own
leaf-level golden because each one's own synthetic test data happened to
avoid the degenerate shape:

1. `pakon_toneHelper.compute_metrics` divided `1.0f` by a histogram total
   that a genuinely edgeless (perfectly flat) real image makes 0 in cna's
   real `EdgeHist`. The real DLL does not trap (FPCW `0x027f` masks the x87
   zero-divide exception and yields a correctly-signed infinity); the port's
   plain Python `/` raised `ZeroDivisionError`. Fixed with a masked-division
   helper, `pakon_toneHelper._x87_div` (mirroring `pakon_ast._x87_div`, the
   same class of fix already made once before on this project), at both risk
   sites.
2. The identical class of bug, independently, in `pakon_cna.analyze_image`'s
   `_half` (`src[i]`/`den[i]` normalisation by a bucket-histogram sum that a
   pseudo-random image can legitimately zero in places) — fixed the same way,
   `pakon_cna._x87_div`.

Both fixes were re-verified against their own subsystem's complete
pre-existing golden suite (still 100% passing) before being counted, and the
whole existing golden fleet (all eleven other `pakon_*_golden.py` files in
this port, including the Phase-1 shell golden) was re-run clean after both
fixes — no regressions.

**One real, reproducible divergence was investigated and deliberately left
unfixed, with the evidence for why recorded rather than guessed at**: an
unrealistically tiny (100-pixel, 46-edge-pixel) synthetic image drove cna's
dark/light-half percentile-crossing search to land exactly at index 0, and
the real DLL's `ToneScaleLut` came back perfectly flat (the pivot value,
1550, repeated 5000 times) where the port computed a real varying curve.
Reproduced with `cna`'s OWN standalone golden harness too (`pakon_cna_golden
.dll_cap_analyze`), so it is not an artefact of the assembled wiring. Re-run
at every larger, still-"pseudo-random" size from 16x16 pixels (256 pixels)
up: zero divergence, every time. A real scanned frame is millions of pixels,
never ~100 — same standard as `pakon_dra_golden.py`'s own already-documented
out-of-range-pixel note (Phase 2b): a real, vendor-adjacent degenerate-input
finding, worth recording, not a blocking integration bug, and not "fixed" by
guessing at an untraced tie-break without a live trace to justify it.

6.2 Render-path swap at both call sites, flip `AutoTonePorted`/
`AUTO_TONE_PORTED` to true (note: `ShastaOnCnRenderPath` stays `false` —
Shasta genuinely never runs here). Re-render
`captures/out_test/frames/08_raw14.tiff` — **do not commit anything from
`captures/`**, this is a local check only.

**Hard acceptance criterion**: current shadow-region-under-code-16 is
39.21%; a correct FUGC-only fix moved it to 39.19% and that was ruled a
**fail** — noise, not improvement. The port is only accepted if the
shadow-clip percentage moves by a margin clearly outside that noise band.
Script this as a reusable, checked-in measurement rather than a one-off
manual number. Corroborate with a real visual check on the rendered image,
same standard already used for the inversion stage.

6.3 Go transcription — verify with `tools/pakon_parity.py` that Go and
Python agree bit-exact before calling this done.

### 6.2 — Python-only pass, attempted and NOT accepted (2026-08-11)

**Scope of this pass, by explicit owner-directed change mid-session**: wire
only `pakon_ansel.py`'s render path (the `PAKON_COLOUR_ENGINE=python`
fallback the app can be pointed at — `tools/pakon_render.py`'s
`colour_engine()`/`_render_colour_python`), not `main.go`/`shasta.go`. Five
Go-transcription drafts were already in flight from before the scope change;
they were let finish (background agents cannot be pre-empted mid-task), each
was self-verified against Python by its own agent, and then all of it was
deleted, uncommitted, once the scope narrowed — see the status table above.
`tools/ansel/pipeline/` is unmodified from before this session
(`main.go`/`shasta.go` byte-identical; confirmed with `git diff` and a clean
`go build ./...`).

**What landed**: `pakon_ansel.real_auto_tone(rpd12, scene_type=0)` — a pure
assembly of the six already-Unicorn-verified subsystems, using the same
"wire pointer→sequence callables to whatever the previous real stage
produced" pattern `pakon_autotone_assembled_golden.RealSubsystems` uses for
its own (independent) DLL-comparison harness, reimplemented rather than
imported so this render-path integration doesn't depend on a concurrently-
changing test file. `render_scene`'s stand-in call site
(`shasta_two_anchor_tone`) now branches on `pakon_shasta.AUTO_TONE_PORTED`;
that flag is untouched at `False`, so **production behaviour is unchanged**
— confirmed by `git diff tools/ansel/python-pipeline/pakon_shasta.py`
showing no edits to that file at all.

**Tooling built** (task explicitly asked to reuse an existing shadow-clip
script if one existed; none did — grepped for "shadow"/"39.21"/"39.19"
across `docs/` and `tools/` first and found only prose, no script):

* `tools/measure_shadow_clip.py` — engine-agnostic. Reads a tap-dir in the
  same format `tools/ansel/pipeline/taps.go` already writes (`manifest.json`
  + one array file per stage) and reports the percentage of channel samples
  under code 16 (8-bit `icc` tap) and under code 257 (12-bit `shasta`/`ansel`
  taps, the pre-existing convention from `shasta.go`'s own docstring).
  `--compare old new` prints the delta as a multiple of the ~0.02-point
  noise band.
* `tools/measure_python_autotone.py` — renders one real local frame through
  the Python engine twice (`AUTO_TONE_PORTED` monkeypatched `False` then
  `True` in-process; the file on disk is never edited by this script) and
  writes both to tap-dirs in that same format, so the script above can
  compare them. Includes a small hand-rolled TIFF reader
  (`read_raw14_tiff`) because PIL silently misreads this project's own
  16-bit-per-sample TIFFs as 8-bit RGB (confirmed empirically on the actual
  test frame: PIL reports mode "RGB", dtype uint8, max sample value 67 —
  wrong by two orders of magnitude).

**Measurement, on `captures/out_test/frames/08_raw14.tiff`** (read locally
only; nothing from it is committed, pushed, or described here beyond
aggregate statistics, per this project's hard rule — see the two thumbnails
this session generated under `/tmp`, not under `captures/`, and not
committed):

| | icc tap, % of samples < code 16 |
|---|---|
| OLD (two-anchor stand-in, current production behaviour) | 27.83% |
| NEW (real `analyzeAutoTone` chain) | 0.00% |
| delta | **−27.83 points, ≈1391× the 0.02-point noise band** |

(This session's own OLD baseline — 27.83% — differs from the 39.21% cited
earlier in this doc. Both are real measurements, not a contradiction: this
session's number used `film_base=None`/per-frame auto-measurement, since the
roll-wide film base used for the earlier 39.21% figure isn't recorded
anywhere in `docs/`; the two numbers are not from an identical methodology.
What matters for THIS pass's decision is the controlled OLD-vs-NEW delta
under one consistent methodology, which is what the table above is.)

**By the letter of the numeric criterion alone, this clears the noise band
by three orders of magnitude — but this pass does NOT call that accepted**,
because this doc's own "Verification summary" requires a real visual check
paired with the number, and that check found a real problem. Rendered
thumbnails of both `icc` taps were generated and actually viewed (not just
statistically summarized): the OLD stand-in shows genuine shadow crush
(blocked-up near-black regions), matching its known symptom. The NEW real
chain does not show a plausible correction — it shows a visibly washed-out,
low-contrast, foggy-looking image, with per-channel `icc` means of
191/212/220 (out of 255), close to the "far too light" bypass signature
`shasta.go`'s own docstring already documents as a FAILURE mode (215.7/
231.4/235.3, 0.00% under code 16, from bypassing the tone stage entirely) —
not identical to a bypass, but the same class of symptom: the shadow-clip
number improved for the same underlying reason a literal bypass would
improve it, by lifting everything, not by correctly compressing the film's
actual dynamic range into the display range.

**Root-caused, not just observed**: direct inspection of the intermediate
LUTs on the real frame (via `pakon_cna`/`pakon_dra`/`pakon_contrast` called
directly, same real params `real_auto_tone` uses) shows `cna` alone
compresses the frame's actual balanced-RPD12 span (1129–3809, span 2680)
down to roughly 1332–3247 (span 1915), and `dra`'s composed curve compresses
the high end further, down to about 2633 at the original top code — `dra`'s
own `effMin`/`effMax` (1690/2614) line up closely with the final render's
actual output range, which is consistent with `dra`'s documented job
(measuring the frame's *effective*, outlier-trimmed range and remapping the
whole curve to fit inside it — a real, intentional dynamic-range-compression
capability, not a bug in the arithmetic itself, corroborated by Phase 6.1's
DLL bit-exactness). What is NOT yet established is whether that compression
is supposed to look like this once the REST of the pipeline (FUGC, which
still runs after this stage unchanged, tuned against the OLD stand-in's
output range; `ColorAdjust`; the ICC hop) sees it — i.e. this may be a real,
correct `analyzeAutoTone` output that a downstream stage tuned for the
stand-in's different output shape then over-lightens, rather than a bug in
`analyzeAutoTone` itself. That question is NOT answered by this pass.

**Decision: `AUTO_TONE_PORTED` was NOT flipped.** It stays `False` in
`pakon_shasta.py`, byte-identical to before this session (confirmed by
`git diff`). The render-path wiring in `pakon_ansel.py` is landed, real, and
individually exercised (`pakon_ansel.real_auto_tone` runs cleanly end to end
on both synthetic and the real local frame, and the six subsystems it calls
are all independently Unicorn-verified, and Phase 6.1's own independent
DLL-comparison passes ALL OK) — but "the pieces are individually verified
and the pipe connecting them runs" is not the same claim as "the resulting
image is correct," and the visual check this doc itself requires did not
pass. This is the exact class of finding Phase 6 exists to catch (Shasta's
own precedent: 5 real bugs found only at assembly, none visible leaf-by-
leaf) — it just turned out to be one level further out than Phase 6.1's own
DLL-comparison, in how the tone stage's real output interacts with the
UNCHANGED rest of the pipeline, not in the tone stage's own arithmetic.

**To see this for yourself** (it will NOT show a fix — this is how to
reproduce the washed-out result above, not a recommendation to ship it):
set `PAKON_COLOUR_ENGINE=python` before running the app, AND temporarily
flip `AUTO_TONE_PORTED = True` in `tools/ansel/python-pipeline/pakon_shasta.py`
(a one-line local edit — not done by this pass, and not recommended to keep
set). `tools/pakon_render.py`'s `colour_engine()` reads the env var; with it
set to `python`, `render_frame` calls `_render_colour_python`, which raises
a `DeprecationWarning` (expected — this path is normally off) and then
renders through exactly the code path measured above.

**What would unblock 6.2 next**: understand whether the washed-out look is
FUGC (or another already-tuned-for-the-stand-in stage) fighting the new
tone curve's different shape, versus a real problem in `analyzeAutoTone`
itself that Phase 6.1's synthetic scenarios don't exercise (all of Phase
6.1's scenarios are small synthetic images; none of them is a real multi-
megapixel photograph with this frame's actual histogram shape). A profitable
next step is probably comparing `dra`'s `effMin`/`effMax` and cna's
`elmoOccured` behaviour across several more real local frames (never
committed) to see whether the compression this pass found is typical or
specific to this one frame, before touching FUGC or re-attempting the switch.

### 6.2 continued — stage-order fix (landed), and the real likely root cause (not fixed)

A follow-up pass (2026-08-11, same day) took the "profitable next step" list
above in a different order: settle the FUGC-vs-tone stage order with real
disassembly first, since it was flagged but never actually checked for the
CN-Enhanced path specifically (only cited, in `docs/65`, from
`AnsCnPremiumPath::exportParameterPack` — a path this render target does not
even take).

**Stage order, settled directly from the binary for CN-Enhanced (not
CN-Premium) this time.** `PakonIMAu.dll` (md5
`eea9dcf78ee21d4f7c515a6c2512242d`, same file `docs/62`/`docs/64` used, hash
re-confirmed this pass) was extracted fresh and disassembled live with r2.
`AnsCnEnhancedPath::exportParameterPack` (`0x10065990`) — confirmed live via
its own repeated self-naming string push (`"AnsCnEnhancedPath::
exportParameterPack"` / `"...CN-Enhanced.cpp"` at ten sites through the
function, the same self-naming method `docs/64` already used successfully) —
calls `ColorNegativePath::exportFugc` (`0x100ff770`) at instruction
`0x1006613d`, and only later calls `ColorNegativePath::exportAutoTone`
(`0x10106f30`, also self-named live, and confirmed to be the export-side
counterpart of `analyzeAutoTone` because it itself finds/exports the same
six `cna`/`dra`/`contrast`/`ast`/`pfd`/`citras` capabilities `analyzeAutoTone`
threads) at `0x100662d0`. FUGC's export call precedes autoTone's, in program
order, inside the one function. Combined with the already-established (and
independently re-confirmed this pass, at its "input"/"output" binding sites
`0x1003a9e3`/`0x1003aac3`) fact that pack order **is** render order
(`AnsImaBuilder::getImaTransformGroup`, `0x100346a0` — no reordering stage
exists), this settles it: **for CN-Enhanced, the vendor's real order is
balance → FUGC → … → autoTone, not autoTone → FUGC.** This is a second,
independent confirmation of the same direction `docs/62`'s CN-Premium
citation already pointed to — so the earlier concern that the citation might
not transfer to CN-Enhanced is resolved: it doesn't matter, both paths agree.

`render_scene`'s `shasta_stand_in` branch had this backwards (tone applied to
`x` before FUGC's `apply_1d_lut`, even though FUGC's own aim/bias inputs were
already correctly read from the pre-tone `balanced` array). **Fixed**: the
FUGC apply LUT is now computed once, right after balance, and applied to `x`
*before* the tone stage in the `shasta_stand_in` branch specifically (the
other two branches — `SHASTA_TONE_LUT_PORTED` and the `linked_percentile_tone`
fallback — are left in their previous order, since neither is what this
evidence is about and neither is confirmed to run on CN-Enhanced at all).
Verified: full golden fleet (all 27 `pakon_*_golden.py` files) re-run after
the change — 26 pass, 1 pre-existing unrelated failure
(`pakon_shasta_aim_golden.py`'s `colneg_1px remap TLA` case, off by one
code — confirmed via `git stash` that it fails identically with this pass's
edit removed, so it predates this pass and is not a regression from it; not
investigated further, out of scope).

**This fix does NOT explain the washed-out look — measured directly, not
assumed.** Rendered the same real reference frame
(`captures/out_test/frames/08_raw14.tiff`) four ways (OLD/NEW order ×
stand-in/real-autotone) using the exact same production functions, order
being the only variable:

| variant | icc mean R/G/B | %<16 R/G/B |
|---|---|---|
| OLD order + two-anchor stand-in (prior production) | 121.3/114.5/109.4 | 30.09/26.21/27.18 |
| OLD order + real `analyzeAutoTone` (docs/66's earlier "washed out" repro) | 191.3/211.7/220.2 | 0.00/0.00/0.00 |
| NEW order + two-anchor stand-in | 122.7/115.8/110.1 | 26.68/24.01/25.67 |
| NEW order + real `analyzeAutoTone` | 190.3/211.5/220.0 | 0.00/0.00/0.00 |

Reordering moves the numbers by about a point — noise, not a fix. Root
cause: this frame selects `NoShift_fugc-generic0225.lut`, and the built FUGC
apply LUT is confirmed (by direct inspection of the array) to be within ±1
code of identity across the entire density range this frame's balanced data
actually occupies (1129–3809) — i.e. FUGC is very close to a no-op for this
specific file, so its position relative to the tone stage barely matters
*for this frame*. The order fix is still real and correct (and would matter
far more for a FUGC file with an actual shaped curve — `docs/62`'s own
CN-Premium sensitivity numbers, a mean of 59–82 codes and up to 792, are for
a synthetic fixture spanning the full domain against a real shaped LUT), but
it is not what is causing this symptom on this frame.

**Item C (do not assume the compression is buggy) — extended, not just
asserted.** Phase 6.1's own scenarios are all small synthetic images; none
resembles a real photograph's histogram shape. This pass built a new,
one-off scenario (not checked in) reusing Phase 6.1's exact assembled
Unicorn harness (`pakon_autotone_assembled_golden.py`'s `build_dll`/
`host_run`/`RealCapset`, called directly, no math reimplemented) but fed it
REAL crops of this frame's actual post-balance data instead of synthetic
pixels — real correlated neighbouring pixels, a real skewed histogram, up to
1024×1024 (1,048,576 real pixels, ~430× Phase 6.1's largest synthetic
scenario). Six crops at 32×32/64×64/96×96/1024×1024, all at different real
locations in the frame: **all bit-exact against the real DLL, zero
mismatches**, including `dra`'s `effMin`/`effMax` and the full `citras`
`ToneLut`/`DraLut` arrays. Could not test the literal full 7,422,000-pixel
frame in one call: `pakon_autotone_shell_golden.py`'s emulated heap
(`HEAP_SZ = 0x02000000`, 32 MB) is smaller than one full-frame I16 pixel
buffer alone (~42.5 MB) — a real, concrete ceiling on this verification
method, not a corner cut, and worth widening in a future pass if this
question needs to be pushed further. Within that ceiling, this pass found
**no evidence of a port bug** in the six subsystems' own analysis math, even
under real-photo statistics — the compression to a narrow output band
(`dra` `effMin`/`effMax` around 1690–2614 on the full frame, output codes
sitting inside roughly 1332–2683 after the LUT is applied) looks like
genuine vendor behaviour for this frame, not a Python-port artefact.

**The more promising, unresolved lead: `real_auto_tone()` never calls
`citras`-apply.** `pakon_ansel.py` does not import `pakon_citras_apply`
anywhere (confirmed by grep — zero references). `real_auto_tone()` applies
the tone stage to pixels with a hand-written direct lookup,
`lut_arr[np.clip(np.rint(x), 0, lut_size - 1)]`, using
`contrast_state.results.OutToneLut` — not even `citras`-analyze's own
(separately computed) `ToneLut`. Its own docstring justifies this only by
analogy ("the same … contract every `*Lut` field in this chain already uses
internally"), not by tracing the real apply-time mechanism. That matters
because this project's own `citras`-apply research (Phase 3b, above) already
found, via live Unicorn tracing, that the real per-pixel apply mechanism
reached through `ImaI16CitrasOp::virtual_56` is **not** a monotonic
single-array lookup — it is `s = wrap16(term[pixel] + base[pixel])` (a
two-operand add, optionally clamped) — and `citras`-apply is reached from
`ImaI16CitrasOp`'s vtable, "an entirely different call graph than every
other subsystem in this doc" (Phase 3's own words), never exercised by
`analyzeAutoTone` or by Phase 6.1's assembled verification, which correctly
and explicitly scoped `citras`-apply OUT. Checked directly this pass: none
of the three already-ported `citras`-apply virtuals' documented formulas
(`tone_compose`, `apply_avoidance_blend`, `apply_luminance`) reference the
operand fields `AnsCitrasOperand::setToneLut` writes (`lut_size`/`tone_lut`,
offsets `0x30`/`0x34`) at all — so this project does not yet have a traced,
verified answer for how a tone LUT installed via `setToneLut` actually
reaches a pixel in the real DLL. `real_auto_tone`'s direct-index shortcut
may happen to be equivalent (e.g. if some other, unlocated call path applies
the LUT transparently and the `term+base` add's `base` operand is zero for
this render), or may not be — genuinely unresolved, not investigated
further this pass because doing so would mean locating and tracing the
`ImaI16CitrasOp` construction/dispatch path this project's own `docs/66`
Phase 3a already flagged as "not sized" — a real, large piece of work, not
attempted blind here per this task's own instruction. **This, not the
stage order and not the six subsystems' own analysis math, is this pass's
best-evidenced candidate for where the washed-out look actually comes
from**, and is the recommended starting point for whoever picks this back
up.

`AUTO_TONE_PORTED` was found `True` in `pakon_shasta.py` at the start of this
pass (the owner's own local flip for visual comparison, per this pass's
brief) and was left exactly as found — not reverted to `False`, not
otherwise touched. The render still looks washed out; this pass's fix
(stage order) is real but insufficient, and no further change was made to
the render path.

### 6.2 continued, third pass — the real citras term/base driver, found but not ported (2026-08-11, same day)

**Task**: resolve, with live evidence rather than more guessing, how
`analyzeAutoTone`'s composed tone curve (`contrast_state.results.OutToneLut`,
what `real_auto_tone()` currently applies with a naive `lut_arr[pixel]`
lookup) actually reaches pixels through `citras`-apply's real
`ImaI16CitrasOp::virtual_56` (`term + base`, Phase 3b) mechanism, and whether
that naive lookup is an accurate stand-in for it or is silently dropping real
per-pixel information. Two hypotheses were posed: (a) `base` is a delta image
(`toneLut[v] - v`) that makes `term + base` reconstruct `toneLut[term]`
exactly, meaning the current shortcut might already be correct; (b) `base` is
a genuinely separate correction signal the shortcut is missing.

**Extracted `PakonIMAu.dll` fresh** from `research/sdk/PAKONF135.iso`
(`tools/re/reachability.py extract`), MD5 re-confirmed
`eea9dcf78ee21d4f7c515a6c2512242d`, matching every prior pass. All work below
is live `radare2 6.1.8`/`r2ghidra` disassembly and decompilation of that
binary, cross-checked with self-naming C++ assert strings the same way
`docs/67` §4 recommends — **not** yet a live Unicorn trace of the driver
itself (see "what this pass did NOT do," below, for why that matters and
wasn't attempted this pass).

**Found the object-construction path Phase 3a flagged as "located but not
sized" (`0x100ae947`) and traced forward from it.** The vtable-install site
is inside `fcn.100ae6f0` (696 B) — `ImaI16CitrasOp`'s real constructor,
called from exactly one place, `ImaCitrasOperationT<short>::virtual_84`
(`0x100ae6a0`, vtable offset `0x54`/84 — a lazy get-or-create wrapper, not
citras-specific: the same offset is shared by dozens of unrelated
`Ima*OperationT<...>` classes' own vtables, confirmed by dumping the vtable
slot and finding it populated for every operation family in the DLL, not
just citras). The constructor itself pulls `citras`'s eight scalar DPI
fields (`sigma`, `blockSize`, `minAvoidance`, `maxGradient`,
`lowGradientThreshold`, `highGradientThreshold`, `bDoClipping`, `minValue`,
`maxValue` — the same eight the existing `citras.md` scope report already
found in `analyze()`'s own validator) from its first argument, and, in a
second constructor-helper (`fcn.100ae9b0`, called from the tail of
`fcn.100ae6f0`), writes three object fields directly, confirmed live from
raw disassembly rather than the (less reliable, per `docs/67` §6) decompile:

```
0x100ae9ef   mov dword [ebp + 0x104], ecx      ; this->0x104 = arg (Ima2DImage ref)
0x100aea02   mov dword [ebp + 0x108], ebx      ; this->0x108 = arg (the SAME "shared
                                                ;   clamp/tone table" pointer
                                                ;   virtual_60 already reads, per
                                                ;   pakon_citras_apply.py's own,
                                                ;   already-Unicorn-verified account)
0x100aea1d   fstp qword [ebp + 0x110]          ; this->0x110.. = a double + word/byte
                                                ;   descriptor, defaulted from
                                                ;   0x1058f4e8.. then optionally
                                                ;   overwritten (rep movsd, 8 dwords)
                                                ;   from a THIRD constructor argument
                                                ;   if non-null
```

This is a real, load-bearing finding on its own: `this->0x108` — the exact
field `CITRAS_APPLY_AVOIDANCE_BLEND_PORTED`'s own comment in
`pakon_citras_apply.py` already documents `virtual_60` reading as "a shared
65536-entry int16 clamp/tone table cache object" — is populated **at
construction time**, from a constructor argument, not built lazily inside
`virtual_60` itself as that file's own comment speculated ("resolved via
`func_0x104ffdd6`, a generic get-or-build accessor" — true, but now known to
be resolving a pointer that was already installed here, not conjuring one
from nothing).

**Found where that table's contents actually come from: `AnsImaCitrasAggregate`'s
own constructor, not `ImaI16CitrasOp`'s.** Self-named three times inside
`fcn.100ad7f0` (1,210 B, file `AnsImaCitras.cpp`) via the literal string
`"AnsImaCitrasAggregate::AnsImaCitrasAggregate"`. This function
`__RTDynamicCast`s a constructor argument (its own error string on failure:
`"AnsOperandPtr is wrong type."`) and, on success, reads eight fields at
fixed offsets from the casted object — **`+0x30` and `+0x34`**, confirmed by
direct offset match against `pakon_citras_apply.py`'s own already-verified
`AnsCitrasOperand::setToneLut` documentation (`lutSize`/`ToneLut`, the exact
two fields `setToneLut` writes) — and passes them to a second allocation
whose failure path's own bad_alloc string is `"Failed in 'new
Tsc1DLutT'."` — i.e. **the analyzed tone LUT (via an `AnsCitrasOperand`
carrying `setToneLut`'s output) is used, by field offset, to build a
`Tsc1DLutT` — a 1-D lookup-table object — inside the aggregate that owns the
citras render node**, not fed into `virtual_56`'s `term`/`base` operands at
all.

**Found the actual per-pixel driver that calls all three of `virtual_56`/`60`/`64`
— previously catalogued in `pakon_citras_apply.py`'s own `CITRAS_APPLY_SLOTS`
table as vtable offset `0x28`/`0x10169350`, "inherited," with no further
exploration.** It is not inert boilerplate: it self-names live as
`.\ImaCitrasOpBase.cpp` (five separate error strings, including
`"The CITRAS op can only produce entire images."` — genuinely citras-specific,
not shared framework code, despite the "inherited unchanged" vtable-diff
label, which only meant `ImaI16CitrasOp` doesn't *override* it, not that it's
generic). Direct disassembly of the full 2,490-byte function
(`0x10169350`-`0x10169d0a`) shows, after validating the input/output images
each have exactly 3 bands (reading `this->0x104`, the same field the
constructor above installs), **three separate indirect calls through `this`'s
own vtable, in this fixed program order**:

```
0x101696c6   call dword [edx + 0x40]     ; virtual_64 — luminance (Phase 3d)
   ...  (substantial operand-construction code in between)
0x10169bf3   call dword [edx + 0x3c]     ; virtual_60 — avoidance-blend (Phase 3c)
   ...
0x10169c30   call dword [edx + 0x38]     ; virtual_56 — tone-compose (Phase 3b)
```

**This resolves the task's two hypotheses — with a third answer, not a pick
between (a) and (b).** Hypothesis (a) (`base` is a per-pixel delta image that
makes `term + base` reconstruct `toneLut[term]`) is now well-evidenced
**false**: nothing in this driver, or in `virtual_56`'s own already-verified
body (which this project already confirmed has zero references to any
table/LUT field), builds or consumes a delta image anywhere in the traced
call graph — the tone LUT's only confirmed destination is the `Tsc1DLutT`
feeding `virtual_60`'s table, called **before** `virtual_56` in the same
function, on what the driver's own validated fields show is the same 3-band
image. Hypothesis (b) (`base` is a separate signal, not derived from the tone
curve) is closer to right but was under-specified: `virtual_56`'s `term`/
`base` operands are not shown to carry the tone curve **at all** — the real
per-pixel tone-LUT lookup, complete with `citras`'s own gradient-avoidance
blending (the `sigma`/`minAvoidance`/`maxGradient`/`*GradientThreshold`
parameters this whole capability is named for, and which `analyze()`'s own
validator requires `sigma > 0`, i.e. not an optional, usually-off feature),
happens in `virtual_60`, one call earlier. `virtual_56`'s own `term + base`
add most plausibly recombines that luminance-domain, avoidance-blended toned
result with the original per-channel chrominance (a "process in luma,
restore chroma" pattern common to colour-negative tone curves) — but that
specific role is an inference from call order and operand-count shape, **not
directly traced this pass**, and is reported as an inference, not a finding.

**What this means for `real_auto_tone()`'s current naive `lut_arr[pixel]`
lookup**: it reproduces **neither** of citras-apply's two real per-pixel
passes. It has no gradient-avoidance blending (so any local
posterization/banding-avoidance smoothing citras is specifically named for is
absent), and no `term + base` recombination step. Whether this specific gap
is *the* cause of the washed-out, globally-too-light look is **not
established this pass, and not claimed**: gradient-avoidance blending is a
local/spatial smoothing correction (it pulls values toward a locally-blurred
reference in smooth regions to hide contouring), which is not obviously the
kind of thing that shifts global per-channel means from ~121/115/109 (the
stand-in) toward ~190/212/220 (real `analyzeAutoTone` + naive lookup) the way
a wrong overall curve shape or a wrong recombination step could. It is a
confirmed, real, unreplicated piece of the vendor's actual pipeline, reported
honestly as such — not asserted as the root cause.

**A cheap alternative hypothesis was checked and ruled out this pass**: that
`real_auto_tone()`'s LUT indexing itself might be domain-mismatched (e.g. an
8-bit-sized table being indexed with 12-bit-range pixel values, which would
saturate every index to the table's top entry and directly produce a
too-light image). Checked directly: `contrast-CNEnhanced.dpi`'s `lutSize =
4096` comfortably covers the reference frame's actual balanced-pixel range
(1129–3809, per the prior pass's own measurement) with no saturation. Ruled
out, not just assumed.

**What this pass did NOT do, and why no fix landed**: the operand wiring
inside `0x10169350` — what real pixel/plane data actually reaches `virtual_60`'s
`s`/`opA`/`opB`/`opC` and `virtual_56`'s `term`/`base` in *this specific
driver* (as opposed to the two functions' own already-verified generic
per-pixel arithmetic, which doesn't change) — was **not** traced live this
pass. This project's own precedent for exactly this class of question is
unambiguous: Phase 3b's "which operand mutates" claim and Phase 3d's "how
many operands, and whose bounds" claim were **both** wrong when first read
statically, and were only corrected by live Unicorn single-stepping against
the real bytes (`pakon_citras_apply.py`'s own "CORRECTION #1"/"CORRECTION #2"
comments, and the `virtual_64` loop-bounds finding). Tracing this driver
(2,490 bytes, dozens of helper calls building operand wrapper objects via
`fcn.1003bf80` and friends, an `RTDynamicCast`-gated success/failure branch
in the aggregate constructor not fully explored) live, to the same standard,
is realistically its own dedicated pass — comparable in size to Phase 3b/3c/3d
combined, not a same-session addition. Landing a guess about what `term`/
`base`/`s`/`opA`/`opB`/`opC` contain here, without that live confirmation,
would risk exactly the "sounds right but wrong" failure `docs/67` already
warns about, in production code this time rather than a golden-test file.
**`real_auto_tone()` and `pakon_citras_apply.py` are both untouched by this
pass.** `AUTO_TONE_PORTED` was found `True` and stays `True`, unreverted, per
the same standing instruction as the prior two passes. Full golden fleet
re-run after this pass (no code changed): 26/27, the same single pre-existing
`pakon_shasta_aim_golden.py` failure as every prior pass, confirming zero
regressions from this investigation.

**Recommended next step for whoever picks this up**: live-Unicorn-trace
`0x10169350` specifically (construct a real `this` with `this->0x104`/`0x108`/
`0x110` pointing at recognizable sentinel buffers, the same canary technique
`pakon_citras_apply_golden.py` already uses for `term`/`base`), to pin down,
with the same certainty Phase 3b/3c/3d already achieved for the leaf math,
exactly what real pixel/plane data feeds each of the six operand slots across
the two dispatched calls — before attempting to wire `real_auto_tone()` to
the real mechanism. Until that's done, the washed-out look's root cause
remains open.

### 6.2 continued, fourth pass — live Unicorn trace of the driver, real progress, still not closed (2026-08-11, same day)

**Task, picking up exactly where the third pass stopped**: do the live
Unicorn trace of `0x10169350` the third pass explicitly deferred, to pin
down real operand identities (not more disassembly reading) for
`virtual_60`'s `weight`/`reference`/`table` and `virtual_56`'s `term`/
`base`, then wire `real_auto_tone()` to whatever's found — or, if the trace
doesn't fully resolve, leave the naive lookup in place rather than guess.

**Extracted `PakonIMAu.dll` fresh** from `research/sdk/PAKONF135.iso`
(already present at `/tmp/pakon_re/PakonIMAu.dll` from the prior pass, MD5
re-confirmed `eea9dcf78ee21d4f7c515a6c2512242d`). Built a scratch Unicorn
harness (`/tmp/pakon_re/trace_v40.py`, not part of the repo — investigative
tooling only, per this task's "work within tools/..." scope, kept out of the
tree) reusing `pakon_autotone_shell_golden.Emu` directly (the same bump-heap/
CRT-stub/hook infrastructure every other golden file in this port already
uses), plus a capstone-driven call-site scan of the driver's own 2,490-byte
body so every internal `call` instruction could be watched (logged, not
intercepted) for classification.

**What the live trace actually confirmed, execution-verified, not inferred:**

1. **The driver's own two stack arguments are operand-shaped, not
   `this`-relative fields.** The first documented static reading (third
   pass) assumed the "output image has N bands" check at `0x101693e5`
   dereferenced something hung off `this`. Live execution disproved that
   directly: with `this` alone populated, the real DLL bytes read exactly
   the harness's own **first stack argument** at that instruction (caught
   because the harness had seeded that argument with an obviously-foreign
   sentinel value, `0xaaaa0001`, which showed up unmodified inside the fault
   address). Once modelled as a real operand — `+0x40` → sub-object → `+0x18`
   band count, `+0x30/0x34/0x38/0x3c` as a `{row, col, width, height}` ROI
   rectangle — the SAME accessor protocol `virtual_56`/`virtual_60`/
   `virtual_64` already established for their own operands — the real DLL
   bytes executed cleanly through **two full validation gates**: the output
   band-count check, and `fcn.1032f4e0` (the "The CITRAS op can only produce
   entire images." gate), the latter confirmed live to compare a full
   `{0,0,width,height}` rect against that operand's own `+0x30..+0x3c`
   fields, not just a 2-field offset pair as a narrower reading would
   suggest.
2. **`this+0x110..0x128` is citras's own 8 scalar DPI parameters, at exact,
   now fully-pinned byte offsets** — extending, not just repeating, the
   third pass's rougher "reads eight scalar fields" characterization. Read
   directly from `fcn.10168aa0`'s full disassembly (`0x10168aa0`..
   `0x10168c1f`, all nine checks including the "no error." success tail,
   not just the first three the third pass saw) and independently
   confirmed by successful live execution once these offsets were
   populated with real-looking values:
   `sigma` `f64@0x110`, `blockSize` `i32@0x118`, `minAvoidance` `u8@0x11c`,
   `maxGradient` `i16@0x11e`, `lowGradientThreshold` `i16@0x120`,
   `highGradientThreshold` `i16@0x122`, `minValue` `i16@0x126`, `maxValue`
   `i16@0x128` — the check ORDER and MESSAGES are byte-identical to
   `pakon_citras.py`'s own already-verified `CITRAS_PARAM_CHECKS`. This
   directly confirms (not just by-coincidence-of-name) that
   `TONE_COMPOSE_FLAG_OFFSET`/`_LOW_OFFSET`/`_HIGH_OFFSET`
   (`this+0x124/0x126/0x128`, already Unicorn-verified by `virtual_56`'s own
   golden) really are citras's `bDoClipping`/`minValue`/`maxValue`, not
   independent fields that happen to sit nearby — the driver re-reads
   `minValue`/`maxValue` a second time itself, right before the
   `virtual_60` call (see point 4 below), from these same offsets.
3. **A genuine `ImaBlockAverageOpTT<short,double>` block-average (box-blur)
   operator is constructed and dispatched inside the driver**, positioned
   in program order strictly AFTER the `virtual_64` (luminance) call and
   strictly BEFORE the `virtual_60` (avoidance-blend) call. This is
   disassembly-confirmed via the same self-naming-string method `docs/67`
   §4 recommends, NOT yet live-pointer-confirmed: the vtable installed
   (`0x1058ddf4`/`0x10154e80`) is real and its own error string
   ("BlockAverage factor must be positive", file
   `R:\fw\ima\imaops\inc\ImaBlockAverageOp.h`) is unambiguous, and its
   constructor (`fcn.10154aa0`, itself confirmed live-executable and
   self-named via `vtable.ImaBlockAverageOpBase.0`) takes a "factor" field
   stored at its own `+0x108`, plus a source operand argument using the
   SAME `+0x30/0x34/0x38/0x3c` ROI-rectangle shape point 1 already
   established. This is strong, concrete, structural corroboration of this
   task's own hypothesis — a locally block-averaged plane, sized by
   citras's own `blockSize` param, sitting between luminance and
   avoidance-blend in program order is exactly what a "reference = smoothed
   version of the image" gradient-avoidance design would need — but it
   stops short of the standard this project holds itself to elsewhere in
   this file: it is corroborated by structure and position, not by
   watching a real pointer identity match `virtual_64`'s own dest buffer
   under execution. Reported as strong-but-not-fully-live-confirmed,
   explicitly, not rounded up.
4. **The driver re-reads `minValue`/`maxValue` from `this+0x126/0x128` a
   second time, immediately before the `virtual_60` call**, alongside a
   call to `fcn.10168d90(&local, sigma)` (a function this pass did not
   further trace) and further calls (`fcn.100a4010`, then a vtable dispatch
   at offset `0x34` on whatever `fcn.100a4010` returns) that look, by
   argument shape (the same `minValue`/`maxValue`/`sigma`-derived value
   feeding into a construction call), like they build a clamped or
   sigma-scaled companion object — plausibly the "reference" operand's own
   clamping, or a second table-like object distinct from `this->0x108`. This
   is disassembly-only (not reached live this pass) and is flagged here as
   an open, not-yet-even-hypothesized-confidently thread for whoever
   continues this, rather than folded into a guess.

**Where the live trace stopped, and why**: past the two validation gates in
point 1, the driver begins constructing the real operand wrappers for the
luminance/avoidance-blend/tone-compose calls via a family of deep, generic
"build an accessor around an `Ima2DImage`" helper functions — `fcn.1032ae60`
(2,055 bytes on its own) and, several calls deep inside it,
`fcn.1035d550`/`fcn.1035d520` (coordinate-to-index mapping helpers expecting
an object with origin fields at `+8`/`+0xc` and STRIDE fields at
`+0x10`/`+0x14`, which must be real, nonzero values or the real DLL's own
`idiv` instructions raise a genuine hardware divide fault under Unicorn,
exactly as they would on real silicon given the same bad input). This
pass's minimal `this->0x104` mock (populated only with width/height/band
count/RTTI-adjacent fields, informed by the earlier third pass's narrower
reading) was not sufficient — the object these deeper helpers actually
dereference for origin/stride is not confirmed to be the same "B" object
this pass populated, and time-boxed guessing at its layout (setting
plausible-looking unit strides on `B` directly) did not resolve the fault,
meaning the real object being dereferenced there was not correctly
identified this pass either. Fully mapping this generic operand-construction
machinery — realistically several more such helper functions, each with
its own undocumented field layout, chained an estimated 15–20 calls deep
before any of the three leaf calls are reached — is, as the third pass
already predicted, genuinely comparable in scope to Phase 3b/3c/3d combined,
not a same-session extension of this pass.

**Decision, per this task's own explicit instruction**: the operand-identity
questions this pass set out to resolve — what real pixel/plane data is
`virtual_60`'s `weight`(opA)/`reference`(s)/`table`, and what is
`virtual_56`'s `term`/`base` — are **still not resolved with the same
live-execution certainty Phase 3b/3c/3d achieved for the leaf math itself**.
Real, new, live-execution-confirmed ground was gained (points 1–2 above, and
the corroborating-but-not-conclusive point 3), genuinely narrowing the
problem and correcting one specific static-reading assumption from the
third pass (`this`-relative vs. stack-argument-relative for the "output"
band check) — but the three leaf calls themselves were never reached under
live emulation this pass, so no pointer identity for any of the six operand
slots was directly observed. Per this task's explicit brief: **`real_auto_
tone()` is NOT wired to any of this.** It still uses its pre-existing naive
`lut_arr[pixel]` lookup (unchanged), and `pakon_citras_apply.py` is
unmodified. `AUTO_TONE_PORTED` was found `True` in `pakon_shasta.py` (the
owner's own standing local flip for visual comparison, carried since the
first 6.2 pass) and is left exactly as found, per the same standing
instruction every 6.2 pass has followed. The rendered output is therefore
**unchanged from the third pass's own washed-out result** — this pass did
not re-render or re-measure, since nothing in the render path changed; the
third pass's own shadow-clip and visual findings still stand as the current,
accurate description of production behaviour under `AUTO_TONE_PORTED=True`.
Full golden fleet re-run after this pass (no port code changed): the same
26/27 as every prior pass, the one pre-existing, unrelated
`pakon_shasta_aim_golden.py` `colneg_1px remap TLA` failure — confirming
zero regressions, as expected for an investigation that landed no code
changes.

**Recommended next step for whoever picks this up next**: the harness this
pass built (`/tmp/pakon_re/trace_v40.py`, not committed) already gets real
DLL bytes executing past the driver's own validation prologue with a
`this`/`out_op` shape now known to be correct on two independently-checked
points — that's a real head start, not a dead end. The next concrete step is
mapping `fcn.1032ae60`'s own field-origin logic (specifically: what object
does it hand to `fcn.1035d550` as `ecx`, and where do that object's
`+8/+0xc/+0x10/+0x14` fields actually come from — `B` itself, a freshly
built sub-object, or something else) closely enough to give it real, nonzero
strides, the same "keep patching forward past each fault with a slightly
better mock, using the fault address itself as the map" method this pass
used successfully for the first two gates. Once past that helper family, the
three leaf calls (`0x10168800`/`0x10168360`/`0x10167bf0`, already hooked and
ready to log `ecx`+stack-args in this pass's harness) should be directly
reachable, and this task's real questions can finally be answered from
observed pointer identities rather than either static inference or another
partial live trace.

### 6.2 continued, fifth pass — live trace resumed, `virtual_64` reached, `virtual_60`/`virtual_56` still not (2026-08-11, same day)

**Task, picking up exactly where the fourth pass stopped**: finish mapping
`fcn.1032ae60`'s (and callees') field layout well enough to get the live
Unicorn trace of `0x10169350` past the fourth pass's fault and observe real
pointer identities at the three leaf calls (`virtual_64`/`virtual_60`/
`virtual_56`). Picked up the fourth pass's own harness
(`/tmp/pakon_re/trace_v40.py`) and extended it in place through several
numbered iterations (`trace_v41.py` .. `trace_v45.py`, all `/tmp/pakon_re/`,
not committed — same as every prior pass's scratch tooling, kept out of the
tree per this task's own scope).

**Root cause of the fourth pass's exact fault, found and fixed**:
`fcn.1032ae60` (confirmed, again, to be `fillRWBuffer()` via its own
self-naming error strings) does call `fcn.1016efa0` and then
`fcn.1035d550`/`fcn.1035d520` exactly as the fourth pass found — but a live
register/memory dump right at the `fcn.1016efa0` call site
(`0x1032aecb`) and its use site (`0x1032aee4`) showed, unambiguously, that
the object passed as `ecx` to `fcn.1035d550` (the coordinate-mapper whose
`+8/+0xc` origin and `+0x10/+0x14` stride fields feed its `idiv`) is **not
`B`** (the fourth pass's own mock target) **but `C`** — the object hanging
off `B+0x28`, which `fcn.1016efa0` turned out, on inspection
(`0x1016efa0`..`0x1016efc6`, 21 bytes), to be nothing more than a plain
getter-with-addref: `eax=[this+0x28]; if(eax) addref(eax); return eax;`.
The fourth pass's mock had populated `B`'s `+8/+0xc/+0x10/+0x14` with
plausible unit-stride values and left `C`'s equivalent fields at zero —
exactly the divide-by-zero the fourth pass's own `idiv` fault was reporting,
just on the wrong object. Moving those four fields onto `C` fixed the fault
immediately, live-confirmed (the previously-faulting `idiv dword [ecx+0x10]`
at `0x1035d564` now executes cleanly).

**A second, previously-unknown requirement on `C`, also found live**:
immediately after surviving the `idiv`, the real DLL bytes do a genuine
`C->vtable[0](1)` virtual dispatch — a `Release`-shaped call on the SAME
`C`, confirmed by a direct register/memory dump at `0x1032af0c`/`0x1032af10`
showing `edx = [C] = 0` (no vtable installed by this pass's mock) sending
the indirect call through address `0`, which under this harness's own
flat-`fs:[0]`-at-linear-address-`0` trick holds the *current ESP*, not a
null sentinel — producing a garbage-EIP fetch fault, not the expected
null-pointer-style failure. `C` needed a real vtable pointer, which the
fourth pass's mock never gave it (its own comment described `C` as "input
sub-object, ->0x18 = band count" — a plain struct, not a polymorphic
refcounted object, which is what it actually is).

**A systemic bug found and fixed across every prior pass's dummy-operand
mocks, worth flagging on its own**: once the trace was pushed further (see
below), a second, very similar-looking crash turned out NOT to be another
missing-vtable case but a **stack-accounting bug in how every dummy vtable
this and prior passes built was constructed**. This codebase repeatedly
calls a COM-style `Release(int)`/`AddRef()`/`CanRelease?()` trio through
operand-shaped objects' vtables (seen at `fcn.10366000`'s smart-pointer
assignment, `fcn.101548a0`'s teardown, and elsewhere) — critically,
`Release` is called as `push 1; call [vtbl+0]`, one real stack argument.
Every dummy vtable this investigation has built so far (this pass's own
first attempt included) filled every slot with a bare `e.stub()` — literal
`\xC3` (`ret`, pops 0 bytes). That silently leaves the pushed `1` on the
stack after a `Release` call through such a slot, which does not crash
immediately — it corrupts the stack just enough that a `ret` several
instructions later pops that stray `1` as a return address, producing a
`UC_ERR_INSN_INVALID` at `eip=0x1` (live-observed, exact value). Fixed with
a shared `make_smart_vtable(e)` helper (now in `trace_v45.py`) that gives
slots 0/1/2 real, convention-correct hooks (`Release`: pop 4;
`AddRef`/`CanRelease?`: pop 0, `CanRelease?` also returns `al=0` so the
`Release` branch is skipped entirely) and leaves the rest as bare stubs
only where no call has been observed to push arguments. This is a real,
transferable finding for whoever continues this work: **any future dummy
operand object needs `make_smart_vtable`, not a bare-stub vtable**, or the
same class of failure will resurface, mis-diagnosed as something else (it
cost this pass a full misdiagnosis cycle, initially blamed on "nested SEH
frame trouble" before the real cause was found by directly dumping
registers at the exact `Release` call site).

**Four unbound raw-RVA import thunks identified and stubbed this pass**
(same class `docs/66`'s fourth pass already handled for the exception
constructor and `sprintf` — this shipped `PakonIMAu.dll` links several CRT/
Win32 imports as raw, unbound thunk addresses rather than proper IAT
entries, so each one has to be found and stubbed individually the first
time the live trace actually reaches it):

  - `MSVCR71.dll time()` (IAT slot `0x105734f0`, raw thunk `0x0068bf72`) —
    called once by `ImaOp::ImaOp()`'s (`0x10009ae0`) own debug/assert-info
    sub-object constructor (`fcn.102bb760`), purely to stamp a timestamp
    nothing downstream reads. First stubbed to return `0x5F000000` (a
    "real-looking" but fake epoch value), which turned out to be actively
    dangerous — a separate, unrelated call site used the return value
    directly as a pointer, and `0x5F000000` looks enough like a valid
    32-bit address to pass an unmapped check and then fault on a *write*.
    Changed to return `0` (the actual Unix epoch), which is safe precisely
    because it is obviously not a real pointer.
  - `KERNEL32.dll InitializeCriticalSection` (IAT slot `0x1057301c`, raw
    thunk `0x00687de2`) — reached deep inside the real
    `ImaBlockAverageOpTT<short,double>` construction path
    (`fcn.10154ea0`/`fcn.10169876` region). Stubbed as `stdcall`, pop 4,
    void return.
  - The exception constructor (`0x0068bbd8`) and `sprintf` (`0x0068bd26`)
    unbound thunks the fourth pass already found were reused as-is.

**`ImaOp::ImaOp()` (`0x10009ae0`) and its destructor `~ImaOp()`
(`0x10009a50`) were stubbed as true no-ops** once their only real content
was confirmed (by disassembly, both are short — 94 and 151 bytes) to be
construction/teardown of the two debug/assert-info `std::string`
sub-objects, nothing pixel- or operand-related; the real
`ImaBlockAverageOp` ctor (`0x10154aa0`) immediately overwrites everything
`ImaOp::ImaOp()` sets at its own `esi+0` anyway with its own real vtable.

**Live-confirmed the real driver reaches `virtual_64` (luminance) with
concrete operand identities** — the actual finding this pass's whole point
was to get to. With the fixes above in place, the trace ran cleanly through
`fillRWBuffer` (stubbed once its own return value was confirmed, by reading
the driver's very next instructions, to not be consumed immediately — it
turned out to be a large, orthogonal tiled-image-cache warm-up on `B` for
`out_op`'s ROI, its own generic accessor machinery a separate rabbit hole
this pass deliberately did not fully map, see below), through the
`ImaBlockAverageOpTT` construction, and hit the driver's own
`call dword [edx+0x40]` (`0x101696c6`, `edx = [this]` = citras's own real
vtable `0x10580824`, confirmed by static read that slot `0x40` there is
exactly `0x10168800` = `VIRTUAL_64`) — a genuine, live, execution-confirmed
call to `virtual_64(this, out_op, blockAvgObj1)`, where `blockAvgObj1` is
this pass's own tagged dummy for whatever the FIRST of driver's two direct
calls to `fcn.1032d150` (at `0x101695f3`) constructs. This directly answers
one of this task's open questions with real evidence, not a guess:
`virtual_64`'s second argument (its own "source" operand) is **not** `B`/`C`
directly — it is a freshly-constructed operand wrapper built by
`fcn.1032d150`, which the driver constructs and hands off before the
luminance call, not the raw input reference.

**Live-confirmed `BLOCK_SIZE` (citras `this+0x118`) really does flow into
the real `ImaBlockAverageOp`'s own `factor` field (`this2+0x108`)** — the
second, THIRD invocation of `fcn.1032d150` (`0x101697f1`, giving
`blockAvgObj3`) feeds directly into the real ctor `0x10154aa0`'s own second
explicit stack argument, and a register dump at that exact call site showed
the value `0x2` (this pass's own `BLOCK_SIZE = 2` mock value) arriving
there unchanged — corroborating, now live rather than only by static
disassembly, the fourth pass's point 3 that a real block-average operator
is genuinely wired to citras's own DPI `blockSize` parameter.

**`fcn.100a3ed0`'s real job, found live**: this generic "build an
operand-shaped wrapper" helper (called several times around the block-
average construction) writes a real constructed-object pointer into its
own `this` — live-confirmed to be exactly what later becomes
`ImaBlockAverageOp`'s own `esi->0x104` "source" field (the field the real
ctor `0x10154aa0` double-dereferences its own `arg_18h` pointer-to-pointer
argument to obtain). No-opping `fcn.100a3ed0` entirely (this pass's first
attempt) leaves that field holding stale, uninitialized stack bytes instead
of a real pointer, which the ctor's own AddRef-shaped
`call [[esi->0x104]][+4]` then crashes on — a clean, live-observed
confirmation that this helper's side effect is real and load-bearing, not
incidental. Its own further dependency, `fcn.1032c0b0` (itself another
generic operand-constructor, ~350 bytes), was stubbed to return a fresh
dummy operand rather than let it run for real, once letting it run for real
was found to lead into genuine, live KERNEL32 **registry** API calls
(`RegOpenKeyExW`/`RegQueryValueExW`/`RegCloseKey`, identified by IAT-slot
address proximity to the crash site once the critical-section imports were
already stubbed) — almost certainly a one-time global config/logging lookup
gated by a critical section, confirmed structurally unrelated to per-call
pixel/operand identity, and not something this investigation should keep
chasing Win32 API by Win32 API.

**Reached, and got past, the exact point the fourth pass named as its own
recommended next step**: the trace continued through
`fcn.10168d90`/`fcn.100a4010` and the `call dword [edx+0x34]` vtable
dispatch the fourth pass's point 4 flagged as "not further traced" —
confirmed live (`CALL@0x101699d7`, `edx = 0x1057f9b0`, a real DLL vtable,
its own `+0x34` slot statically confirmed to hold `0x10328d20`) — genuinely
new ground beyond every prior pass.

**Where this pass stopped**: inside `fcn.10328d20` (945 bytes,
"status validation" for the just-constructed block-average result — its own
body includes the literal string `"Bad status reported by"`), which does a
`call dword [eax+0x1c]` on its own `this` where `eax = [this]` (a REAL
vtable dispatch requiring a properly RTTI-shaped object, not merely one
with a smart-pointer-compatible vtable). This pass's dummy operands
(`make_smart_vtable`'s bare-stub slots beyond 0/1/2) are not RTTI-shaped —
calling through an unmapped/wrong slot here sent EIP to the
`AnsCitrasOperand` RTTI `TypeDescriptor`'s own data address
(`0x106921b4`, the exact address this pass had earlier and separately
located via static RTTI-table parsing to identify the real `AnsCitrasOperand`
vtable, `0x1058386c`), then faulted trying to read `vft-4` off it — the
classic `__RTDynamicCast`-style "read the Complete Object Locator" access,
executing on data. Building a properly RTTI-shaped dummy object (a real
`AnsCitrasOperand`-family vtable plus a valid, if fake, COL/
ClassHierarchyDescriptor/TypeDescriptor chain) is a materially bigger lift
than anything else this pass fixed, and was not attempted this session.

**Decision, per this task's own explicit instruction**: `virtual_60` and
`virtual_56` — the two leaf calls whose `weight`/`reference`/`table`/`term`/
`base` operand identities this task set out to resolve — were **not
reached**. Only `virtual_64`'s own operands were observed live, and while
that is real, new, execution-confirmed evidence (not inferred), it answers
a narrower question than the task's central one. `real_auto_tone()` in
`pakon_ansel.py` is unchanged (confirmed by inspection — still the naive
`lut_arr[idx]` lookup at its tail), `pakon_citras_apply.py` is unchanged,
and `pakon_shasta.AUTO_TONE_PORTED` was found `True` and is left exactly as
found. The rendered output is therefore unchanged from every prior pass —
no re-render or re-measurement was done, since nothing in the render path
changed. Full golden fleet re-run after this pass (no port code changed):
the same 26/27 as every prior pass — `pakon_cna_golden.py`,
`pakon_dra_golden.py`, `pakon_toneHelper_core_golden.py`,
`pakon_toneHelper_tree_golden.py`, `pakon_contrast_lut_golden.py`,
`pakon_contrast_slope_golden.py`, `pakon_ast_golden.py`,
`pakon_citras_golden.py`, `pakon_citras_apply_golden.py`,
`pakon_autotone_shell_golden.py`, `pakon_autotone_assembled_golden.py` all
pass; `pakon_shasta_aim_golden.py` fails with the same single, pre-existing,
unrelated `colneg_1px remap TLA` mismatch every prior pass has also seen —
confirming zero regressions.

**Recommended next step for whoever picks this up next**: the harness this
pass left (`/tmp/pakon_re/trace_v45.py`, not committed) reaches real,
live-executing DLL bytes all the way to a genuine RTTI-validation gate on
the block-average result, one real leaf call (`virtual_64`) fully
identified, and is a materially better starting point than the fourth
pass's own harness was. The next concrete step is building a real, valid
RTTI chain for the dummy operand objects this pass's `make_smart_vtable`
only gives a smart-pointer-compatible (not RTTI-compatible) vtable to —
reusing the REAL `AnsCitrasOperand` vtable this pass already statically
located (`0x1058386c`, via its RTTI `TypeDescriptor` string
`.?AVAnsCitrasOperand@@` at `0x106921bc`, walked back through the standard
MSVC `{signature=0, offset, cdOffset, pTypeDescriptor, pClassDescriptor}`
Complete-Object-Locator layout this project's own `rt_dynamic_cast` helper
in `pakon_autotone_shell_golden.py` already implements) is very likely
sufficient — pair it with a genuine (even if minimal, one-entry)
`RTTIClassHierarchyDescriptor`/`RTTIBaseClassDescriptor` chain rather than
reusing the real one verbatim (the real one's base-class array points at
other real TypeDescriptors this mock doesn't want to have to also satisfy).
Once past `fcn.10328d20`'s status gate, this pass's own capstone-driven
"watch every driver call site" instrumentation (already in
`trace_v45.py`, extended from `trace_v40.py`) should make the remaining
distance to `virtual_60`/`virtual_56` fast to observe, the same "keep
patching forward past each fault with a slightly better mock, using the
fault address itself as the map" method that got this pass as far as it
got.

### 6.2 continued, sixth pass — `fcn.10328d20`'s gate actually passed, three more unbound thunks and a systemic AddRef bug found, still short of `virtual_60`/`virtual_56` (2026-08-11, same day)

**Task, picking up exactly where the fifth pass stopped**: build the
properly-RTTI-shaped dummy object pass 5 said `fcn.10328d20`'s gate needed,
get past it, and continue the live trace to `virtual_60`/`virtual_56`. Picked
up pass 5's own harness (`/tmp/pakon_re/trace_v45.py`) and extended it as
`/tmp/pakon_re/trace_v46.py` (`/tmp/pakon_re/`, not committed — same scratch
convention as every prior pass). Also wrote a small standalone disassembly
helper, `/tmp/pakon_re/disasm.py` (loads the DLL's sections into a flat
image and disassembles/reads strings from a given VA — used throughout this
pass to read raw `{hint, name}` import-table entries directly off disk,
the same technique that identified every unbound thunk below).

**Pass 5's own diagnosis was wrong, and this pass proved it by single-
stepping through the exact fault** rather than reasoning from static
disassembly alone. `fcn.10328d20`'s `call dword [eax+0x1c]` is a completely
ordinary, correctly-shaped virtual dispatch on a REAL, live-constructed DLL
object (not this pass's own dummy) — the object at that point (`edi`,
confirmed live to be `0xc6dfedc`, a driver-owned stack sub-object with a
REAL vtable, `0x1057f9b0`) was never a mock at all. A cheap, targeted
instruction-level ring-buffer tracer (`instr_trace` in an early iteration of
`trace_v46.py`, later replaced with the range-limited `mk_watch2` technique
below once it turned out to be too slow — see "a real performance lesson"
below) traced the call chain live: `fcn.10328d20` → `fcn.103289e0`
(`vtable[0x1c]`, a cached-status-check wrapper) → `fcn.100a4150` (a
this-adjustor thunk, `sub ecx,[ecx-4]`) → `fcn.102fe7a0` (a type/status
check) → `fcn.10328950` (the actual comparison, walking a small,
statically-fixed list of candidate RTTI `TypeDescriptor`s) → a tight loop
at `fcn.1031176x` calling `edi` (a function pointer) with a different
candidate `TypeDescriptor` pushed each iteration. `edi` at that call site
was confirmed live to be **exactly `0x68bcee`** — not a real function
address at all, but the raw `{hint, name}` import-table entry for
`??8type_info@@QBEHABV0@@Z` (`bool type_info::operator==(const type_info&)
const`), read directly off the PE file on disk (`b'\x6e\x02??4?$basic_
string...'`-style bytes at that exact offset — the same "raw unbound RVA
points straight at the unresolved import's own hint/name table entry"
mechanism the fourth and fifth passes already found for `sprintf`/`time`/
the exception ctor/`InitializeCriticalSection`, just never noticed for this
one). Left unhooked, `type_info::operator==`'s unbound thunk falls onto the
same shared zero page (`0x68b000`) as this pass's OWN existing
`SPRINTF_UNBOUND` stub and returns through *that* stub by pure address
proximity — a bare `\xC3`, 0-pop, which is silently wrong for `type_info::
operator==`'s real thiscall convention (one reference argument, needs
`ret 4`). Exactly the `make_smart_vtable` bug class pass 5 already diagnosed
once, just hitting a **real unbound import thunk** instead of a **dummy
vtable slot** this time: each botched call strands its one pushed argument
(a real `TypeDescriptor` pointer, e.g. `0x106a4054` →
`.?AVMixedClass@ImaDataType@@`, confirmed live-readable) on the stack, and
after 3–4 of these accumulate, a later, perfectly ordinary `ret`
(`0x103117b1`) pops one of them (`0x10692008`) as a return address — EIP
jumps directly into a live `TypeDescriptor`'s own raw bytes and "executes"
them as x86 until it dereferences `[reg-4]` with `reg==0`
(`addr=0xfffffffc`), the exact fault pass 5 hit and attributed to a missing
fake RTTI chain. **Fixed** by stubbing `0x0068BCEE` directly (same
technique as every other unbound thunk this investigation has found),
returning the real string-equality comparison against the two
`TypeDescriptor`s' own `+8` name fields (both are always real, live DLL
RTTI data at every call site observed — none of this pass's own dummy
operands are involved in this specific check).

**Two more unbound thunks, found the same way, one instruction fault at a
time, "patch forward and let the next fault name the next gap":**

  - **`__RTDynamicCast` (`0x104FFDD6`)** — genuinely the actual, direct root
    cause of what pass 5 saw, once the `type_info::operator==` fix let the
    trace get one level further. `fcn.102fee40` (called from `fcn.100a4010`
    at `0x100a40b2`, itself a real base-class initializer for the object
    `fcn.100a4010` constructs) does a textbook, direct, 5-argument cdecl
    `call 0x104ffdd6` (`__RTDynamicCast(inptr, vfDelta, srcType, targetType,
    isReference)` — confirmed live: `inptr=[esi+8]`, `vfDelta=0`,
    `srcType=0x106a38e8`, `targetType=0x106a3900`, `isReference=0`). This
    thunk was never hooked by any prior pass (`grep`'d `trace_v40.py`
    through `v45.py`: absent). Left unstubbed, its own unbound
    `jmp [0x105735c0]` lands on raw RVA `0x68bc14`, which — because it sits
    *before* this pass's own `type_info::operator==` stub on the same page
    — walks a couple hundred zero bytes and returns through that stub by
    the same address-proximity accident, this time with a **plausible-
    looking but wrong** return value (cdecl callee correctly does a 0-pop
    `ret`, but `eax` on return is just whatever it was at the call site —
    the original `inptr`, not a real cast result or a clean `NULL` for a
    failed cast). That bogus "cast result" gets stored and dereferenced a
    few instructions later, which is what actually walked the trace into
    the `addr=0xf000000`-area fetch fault this pass hit right after fixing
    `type_info::operator==` alone. **Fixed** by reusing, verbatim, this
    project's own `rt_dynamic_cast` (`pakon_autotone_shell_golden.py`) —
    the real RTTI-table-walking reimplementation already used for this
    exact thunk in the Phase-1 shell harness — imported directly rather
    than re-derived.
  - **`std::basic_string<char>::operator=` (`0x00688B68`,
    `??4?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@
    QAEAAV01@ABV01@@Z`)** — found one fault further, inside `fcn.100a4150`'s
    own body calling `fcn.102fe7a0`'s debug/assert-message-building side
    path (same family as `ImaOp`'s own debug sub-objects pass 5 already
    established as diagnostic-only, not pixel/operand data). Same fix
    shape: stub the raw address directly (confirmed via the exact same
    `{hint, name}` file-offset read as every other case here), matching
    the simplified "char* stored at `this+0`" std::string model
    `pakon_autotone_shell_golden.Emu` already uses for the ctor/dtor pair
    (this harness inherits that same `Emu` base class, so the ctor/dtor
    hooks were already active — only `operator=` was missing).

**A fourth, systemic bug — not another missing thunk, but a real defect in
`make_smart_vtable` itself, found by bisecting a live register trace call by
call.** Once the three thunks above were fixed, the trace reached, for the
first time ever in this investigation, real code deep inside
`fcn.1032c0b0` (the "build an operand-shaped wrapper" helper pass 5 had
stubbed out entirely). It faulted with `eip=0xf1a addr=0x1000` — a null-page
walk-off, same shape as before. Bisecting a register watch instruction by
instruction (`edi` specifically) across the suspect region pinned it to
**exactly one instruction**: `0x1032c19e: mov edi, eax`, immediately after
`0x1032c19b: call dword [eax+4]` — a real virtual `AddRef()` call on a
sub-object hanging off this pass's own `blockAvgObj+0x40` field (itself
freshly added this pass, see below). The real DLL code uses `AddRef()`'s
*return value* as the addref'd pointer itself (the common "AddRef returns
`this`, for chaining" C++ idiom) — but `make_smart_vtable`'s `AddRef` stub,
unchanged since pass 5, hard-codes a return of `0`. `edi` silently becomes
`NULL` one instruction after every single `AddRef()` call through any dummy
object built by `make_smart_vtable` — this and pass 5's harness both use it
for *every* dummy object, so this is a real, generalizable bug affecting
all of them, not a one-off. **Fixed**: `AddRef`'s hook now returns
`ecx` (the `this` it was called on), matching the idiom.

**Two more small, targeted fixes needed to keep the newly-real code paths
alive, both live-confirmed necessary (removing them reproduces the exact
fault each was added for):**

  - `blockavg_stub`'s own `obj+0x40` field (previously left at 0, matching
    the rest of the all-zero mock) needed to be a real, non-null,
    `make_smart_vtable`'d sub-pointer — `fcn.1032c0b0` dereferences
    `[[edi]+0x40]` as its own "source operand" sub-pointer, first via a
    plain (non-virtual) addref through `fcn.100065e0`, then later
    (`0x1032c192`..`0x1032c19b`) via a genuine virtual dispatch through
    *that* object's own vtable slot `+4`. Left null, the second use walks
    the null page exactly as described above (this was, in fact, the FIRST
    `eip=0xf1a` fault this pass hit, before the AddRef-return-value bug was
    found underneath it).
  - `fcn.100a3ed0`/`fcn.1032c0b0` (pass 5's own dummy-object stubs for
    "build an operand-shaped wrapper") were **un-stubbed** this pass and
    let run for real. Pass 5 had short-circuited them entirely because
    letting them run led into live KERNEL32 Registry API calls
    (`RegOpenKeyExW`/`RegQueryValueExW`/`RegCloseKey`) it correctly judged
    orthogonal to pixel/operand identity but didn't want to chase
    indefinitely. This pass found that the REAL problem was never these
    two functions' own construction logic — it was specifically those
    three Win32 calls, unstubbed. Located their own raw `{hint, name}`
    unbound-thunk addresses the same way as every other thunk in this
    report (`RegOpenKeyExW` @ `0x687e8e`, `RegQueryValueExW` @ `0x687e7a`,
    `RegCloseKey` @ `0x687e6c`, all on the same already-mapped page as
    `InitializeCriticalSection`'s own thunk), stubbed exactly those three
    (`RegOpenKeyExW`/`RegQueryValueExW` return `ERROR_FILE_NOT_FOUND`,
    `RegCloseKey` returns success), and let the real constructors run.
    **A/B-tested this choice directly**: an experimental variant
    (`/tmp/pakon_re/trace_v46_regtest.py`, not kept) made the two lookup
    APIs return success with a plausible fake `HKEY`/DWORD value instead of
    "not found" — the trace hit the exact same fault at the exact same
    instruction either way, confirming pass 5's own instinct that this is
    an inert, one-time config/logging lookup, not something whose outcome
    the operand-construction math depends on.

**Net result of all four+two fixes together: `fcn.10328d20`'s RTTI gate
genuinely passes for the first time in this investigation**, and the trace
continues into real, live-executing DLL bytes far beyond any prior pass —
through the real `ImaBlockAverageOp` constructor (`0x10154aa0`, confirmed
short and clean, only touches the already-handled `ImaOp::ImaOp()` stub and
a trivial `lock inc [eax+4]` addref) and into a chain of real C++ destructor
links this pass had never seen before: `0x1032ae40` (a "scalar deleting
destructor" wrapper) → `0x1032a3c0` (the real destructor body) →
`0x10359cc0`/`0x10359b50` (a further base-class destructor, correctly
skipping its own debug-logging side path — a global flag byte at
`0x106c4f1c`, statically and live-confirmed `0`) → `0x1032da80` (another
base-class teardown link, self-installing the vtable `fcn.1032d150`'s own
constructor uses, `0x10575d28`, confirming this is genuinely the same class
family) → `0x10338840` (what looks like the final, `ImaOp`-level base
destructor).

**Where this pass stopped**: inside `fcn.10338840`
(`0x10338872`..`0x10338876`), tearing down a nested sub-object living at
`this+0x24` of `fcn.1032c0b0`'s own local temp object (`ebp`, confirmed
live `0xd021aa0` — itself a real, `0x68`-byte, `operator new`'d object
`fcn.1032c0b0` constructs partway through its own body via three
still-unexplored helper calls, `0x10343fa0`/`0x10359a60`/`0x10329f70`,
none of which this pass disassembled). `[ebp+0x24]` holds a real-looking
heap pointer (`0xd021b40`) whose own first field ("vtable pointer") is
`0x105ba344` — itself a plausible DLL address — but `[0x105ba344]`
(vtable slot 0, "Release") is, live-confirmed by reading the raw DLL bytes
at that exact static address, **`0x6d53616d`** — not a function pointer at
all, but the literal mid-string address of a genuine DLL debug string
(`"...cardReference on a ImaSmartRenderedItem..."`, found by searching the
PE file directly for those four bytes as a little-endian dword). Calling
through it sends EIP straight into the string's own bytes, "executing" them
until an inevitable fault. **This is a different bug shape than every fix
above**: it is not a missing unbound-thunk stub (`0x105ba344` is real
`.rdata`, not an unbound import), and it is not a `make_smart_vtable`
stack-convention bug (the call site itself, `push 1; call [eax]`, is a
completely ordinary, correctly-popped Release). The most likely explanation,
not yet confirmed live: `[ebp+0x24]` is populated by whichever of the three
unexplored helper calls above, and the value it computes/stores there is
**wrong** given how sparse this pass's `C` (coordinate-mapper) mock still
is — `C`'s own `+0x30`/`+0x34`/`+0x38`/`+0x3c` fields (read by a *different*
bounding-box computation earlier in `fcn.1032c0b0`'s own body, at
`0x1032c128`..`0x1032c168`, which this pass traced and confirmed currently
evaluates cleanly to zero on both outputs given `C`'s current all-zero
shape there) were never populated by any prior pass, and it is plausible
one of the three unmapped helper functions performs a similar computation
that, fed sparse/zero inputs, produces a coincidentally-heap-address-shaped
but semantically wrong value rather than a clean `NULL`. This is a
**genuine construction-completeness gap in this pass's own mock** (`C`
needs real `+0x30..+0x3c` fields, and/or `0x10343fa0`/`0x10359a60`/
`0x10329f70` need to be read), not another one-line unbound-thunk fix —
distinguishing it from every other blocker this pass resolved.

**A real performance lesson, worth flagging for whoever continues**: this
pass's first attempt at deeper visibility was a single blanket
`e.uc.hook_add(UC_HOOK_CODE, cb)` with no `begin`/`end` — cheap-looking in
Python but forces a native-to-Python callback transition on **every single
instruction the whole emulation executes**, not just the region of
interest, since Unicorn only filters cheaply in C when a concrete
`begin`/`end` range is given. Once several of the fixes above changed
control flow, the real run started legitimately taking ~30 real seconds of
call-site-watch-only emulation before its next fault, and the blanket
per-instruction hook made that same run take minutes and time out. Fixed by
switching to the same per-address (`begin==addr, end==addr`) or narrow-
range (`begin`/`end` bounding just the one or two functions of interest)
watch technique `trace_v40` already used for the driver's own call sites —
cheap because Unicorn filters natively, and this pass extended it
incrementally, function by function, as each new fault named the next one
to add (`extra_ranges` in `trace_v46.py`, now covering ~10 functions deep).
This is the same "keep patching forward, let the fault address be the map"
method every pass has used, just applied to *instrumentation* this time,
not fixes.

**Decision, per this task's own explicit instruction**: `virtual_60` and
`virtual_56` were **not reached**. `real_auto_tone()` in `pakon_ansel.py` is
unchanged (still the naive `lut_arr[idx]` lookup), `pakon_citras_apply.py`
is unchanged, and `pakon_shasta.AUTO_TONE_PORTED` was found `True` and is
left exactly as found, per this task's own instruction. No render-path code
changed, so no re-render or re-measurement was performed — the rendered
output is unchanged from every prior pass (still washed out, unexplained by
this task's own central question). Full golden fleet re-run after this pass
(no port code changed, only the scratch trace harness): `pakon_cna_golden.py`,
`pakon_dra_golden.py`, `pakon_toneHelper_core_golden.py`,
`pakon_toneHelper_tree_golden.py`, `pakon_contrast_lut_golden.py`,
`pakon_contrast_slope_golden.py`, `pakon_ast_golden.py`,
`pakon_citras_golden.py`, `pakon_citras_apply_golden.py`,
`pakon_autotone_shell_golden.py`, `pakon_autotone_assembled_golden.py` all
pass; `pakon_shasta_aim_golden.py` fails with the same single, pre-existing,
unrelated `colneg_1px remap TLA` mismatch every prior pass has also seen —
confirming zero regressions.

**Recommended next step for whoever picks this up next**: the harness this
pass left (`/tmp/pakon_re/trace_v46.py`, not committed, built on pass 5's
`trace_v45.py`) reaches real, live-executing DLL bytes through the real
`ImaBlockAverageOp` constructor and four levels of real C++ destructor
chaining — a materially better starting point than pass 5's own harness.
The concrete next step is disassembling `fcn.10343fa0`, `fcn.10359a60`, and
`fcn.10329f70` (all called from inside `fcn.1032c0b0`, around
`0x1032c20e`..`0x1032c226`, on the local `ebp` object) to find exactly which
one writes `ebp+0x24`, and what real input field(s) that write depends on —
almost certainly tracing back to `C`'s own unset `+0x30`/`+0x34`/`+0x38`/
`+0x3c` fields, which is where this pass would look first. Once `ebp+0x24`
holds either a clean `NULL` or a properly-shaped real sub-object,
`fcn.10338840`'s own destructor should complete cleanly and the trace should
be very close to returning out of the whole `fcn.100a3ed0`/`fcn.1032d150`
construction chain and reaching the driver's own subsequent leaf calls —
this pass's own `extra_ranges`/`mk_watch2` instrumentation (see "a real
performance lesson" above) should make watching that final stretch fast.

### 6.2 — parallel track: three other candidate causes (2026-08-11, concurrent with the citras operand-wiring pass above)

This pass ran **alongside** (not instead of) the citras `term`/`base` operand-
wiring investigation above, on the owner's explicit instruction to check
three *different* candidate causes and not touch `pakon_ansel.py` or
`pakon_citras_apply.py` (that pass's own files, to avoid a collision). Four
things were checked: FUGC/ColorAdjust/ICC's own golden-test range coverage,
whether `scene_type=0` is really correct for this frame, whether
`real_auto_tone()`'s histograms are built the way the real vendor driver
would build them at this point in the pipeline, and (lower priority)
`falloff`'s plausibility as a contributor. Two real, evidenced findings came
out of this pass — one fixed and landed, one identified but not fixed (per
this pass's own scope). Two candidates are ruled out with real evidence. One
new, more specific, not-yet-fully-resolved lead was found and is reported for
whoever continues.

**Track 1 — FUGC/ColorAdjust golden-test range coverage: one real gap found,
fixed, and closed; ColorAdjust ruled out; ICC is a pre-existing, separately
tracked gap, not newly resolved here.**

* **FUGC's `setLutInfo` (`0x101f82c0`) — the function that actually builds
  the apply LUT on this render path's default (`fugc_mode=1`, i.e. mode≠2)
  branch — had ZERO Unicorn golden coverage anywhere in this repo before this
  pass**, despite `pakon_fugc.py`'s own module docstring calling its maths
  "VERIFIED @ 0x101f82c0". `pakon_fugc_golden.py` only ever exercised the
  mode==2 metrics leaves (work bias, thresholds, histogram accumulate, work
  percent) — confirmed by reading the whole file, not by a raw grep miss.
  Worse than a narrow-range gap: no range at all had a committed, repeatable
  DLL comparison.
* Built one (live Unicorn, real `PakonIMAu.dll` bytes, thiscall `ecx=Cap`
  object with `+0xe6` seed / `+0x60ec,+0x60f2,+0x60f8` aim words, matching
  the wrapper ABI `pakon_fugc.py`'s own docstring already described but never
  tested) and ran the previously-untested full offset domain against
  `pakon_fugc.set_lut_info`. **Found a real, load-bearing bug in the port**:
  `set_lut_info_channel` raised `ValueError` for any `offset < 0`, with a
  comment claiming that case was "not covered by verified fragment." Live
  execution shows the real DLL has **no separate negative-offset branch at
  all** — it is the exact same clamp loop the positive-offset path uses; a
  negative offset just makes the prefix-fill's own trip-count check false
  (skipping it) and can push the loop's end bound below its start (when
  `offset <= -N`), which the DLL's own signed loop-guard already turns into
  "zero real iterations, tail-fill the whole channel with identity" with no
  extra code. Confirmed bit-exact, live, for offsets from `-32768` (int16
  min) through `+5000`, including the `offset <= -n` all-identity edge and
  the exact `n-1`/`n` boundary — 12 cases, all `OK`, in the now-committed
  `check_set_lut_info` (`pakon_fugc_golden.py`). **Fixed**:
  `set_lut_info_channel` (`pakon_fugc.py`) now implements the general
  `lo = max(offset, 0)`, `hi = max(lo, min(offset + n, n))` shape instead of
  raising; zero behaviour change for `offset >= 0` (the new formula reduces
  identically to the old one there — re-confirmed by the same 12-case suite
  still passing on the previously-covered positive/zero cases). No caller in
  this repo depended on the old exception (grepped: `set_lut_info`/
  `set_lut_info_channel` have no other call sites outside `pakon_fugc.py`
  itself). Whether a real frame's own aim delta (`60ec − 60f8 + 60f2`) is
  ever actually negative was not established either way this pass — this
  reference frame's own FUGC LUT was already shown (prior 6.2 pass) to be
  within ±1 code of identity, consistent with a near-zero offset, not a
  large negative one — so this is a real, now-closed correctness gap, not
  demonstrated to be *this* frame's washed-out cause. `pakon_fugc_golden.py`
  re-run clean end to end after the fix (`PYTHONPATH=tools/ansel/python-pipeline
  python3 tools/ansel/python-pipeline/pakon_fugc_golden.py /tmp/pakon_re/PakonIMAu.dll`).
* **ColorAdjust — checked and ruled out, real evidence, no gap.**
  `pakon_color_adjust_golden.py`'s `run_fill`/`contrast_base_lut` comparison
  already compares the **entire 4096-entry LUT** (`LUT_LEN = 0x1000`), not a
  handful of samples, for every `contrast` value it tests — so the "narrow
  input range" framing doesn't apply the way it might for a histogram-driven
  function: the LUT is built once over its whole domain regardless of which
  sub-range a given frame's pixels actually land in, and that whole domain
  is already Unicorn-verified. No new test needed; nothing found.
* **ICC input scale — RESOLVED this pass (owner explicitly asked to keep
  going rather than leave this as a tracked-but-open gap).** `docs/65`'s
  "ICC evaluation | Verified faithful" row is a Go-vs-Python **cross-engine**
  agreement check (littleCMS vs. a hand-written evaluator, 0.3/255), not a
  live trace against the real vendor CMS — that part still stands as
  written. But `docs/62` §12.6's ranked-#2 open question ("4095 vs 32767 vs
  Go's `×65535/4095`") **is now answered, with real evidence**: **65535.0 —
  Go's own scale, not either of the other two candidates.**

  Traced `ImaICCXForm::apply` (`0x102f8420`, `PakonIMAu.dll`) — the function
  `docs/62` §12.4.2 already cites as doing the `fcomp qword [0x105a17e0]`
  (the literal constant `4096.0`) check that selects KCMS datatype 4
  (12-bit) vs. 5 (16-bit) based on "the caller's max value." That part was
  already established; what wasn't is what the real caller actually passes.
  `apply` has exactly two direct (`E8`) call sites in the whole 7,598,080-byte
  image: `0x1016eef8`, inside `ImaPnrOp<TYPE>::ApplyScrubbingMode`
  (self-named, pixel-noise-reduction-specific, not the render colour path —
  a real dead end, checked and set aside) and `0x10365ace`, inside a function
  self-evidenced as part of `ImaICCEffectOperation` (error strings
  `"ImaICCEffectOperation xform input has bad status"`,
  `".\ImaICCEffectOperation.cpp"`). That function's own sole caller is
  `0x100066d0`, whose own sole caller is inside the **exported**
  `PIFileOpenPlanar` (`0x1000ff30`) — i.e. this is the real render/scan-output
  setup path, not a debug or preview-only one.

  `0x100066d0` takes two incoming doubles (its own `[esp+0x14]`/`[esp+0x28]`
  at entry) and builds a 24-byte `ImaDataType`-shaped local object:
  `{vtable=<"short" type-tag, from the same 0x10311600 factory `docs/62`
  already cites>, size=2, max=<2nd double>, min=<1st double>}`. Its actual
  caller, `PIFileOpenPlanar` (`0x10010779`), loads those two doubles
  from **literal DLL data-section constants**, not computed values:
  `fld qword [0x10573c40]` → **0.0** and `fld qword [0x10575198]` → **65535.0**
  (both read directly out of the loaded PE image and confirmed by decoding
  the raw bytes, not inferred). **Live-Unicorn-verified**, not just read
  statically: built a minimal harness that executes the real `0x100066d0`
  bytes standalone with sentinel doubles (`1111.5`/`2222.5`, deliberately
  NOT the real constants, specifically so a wrong offset couldn't
  coincidentally look right) and read back the resulting 24-byte object —
  first attempt showed a mismatch (an off-by-one-dword bug in the harness's
  own stack bookkeeping, not the DLL), caught and fixed, then re-run:
  `{vtable=0x106908c0, size=2, max=2222.5, min=1111.5}` — exact match to the
  hand-derived layout. Re-running conceptually with the real constants in
  that same confirmed layout gives `{max=65535.0, min=0.0}`.

  This settles it: the real vendor code, for this call path, declares its
  ICC operand's pixel-value domain as **[0.0, 65535.0]** — the full unsigned
  16-bit range — not `[0, 4095]`/`[0, 4096]` and not `[0, 32767]`. Since
  `65535.0 != 4096.0`, `apply`'s own comparison takes the "not exactly
  4096.0" branch, i.e. **KCMS datatype 5 (full 16-bit)**, not datatype 4
  (12-bit). This directly matches Go's own `×65535/4095` rescale-to-16-bit
  choice as vendor-correct, and identifies the current Python `to_srgb()`'s
  approach (quantize straight to **U8** before handing pixels to littleCMS,
  `rpd12_to_icc_u8`) as a real, different-in-kind gap from what the vendor
  does — already flagged in `docs/62` §2.9 as "a PIL limitation," not newly
  discovered here, but now known to be a precision-loss gap on top of a
  domain the vendor treats as full 16-bit, not merely an 8-bit-vs-12-bit
  rounding question.

  **Confidence, stated precisely, not rounded up**: the object *construction*
  (`0x100066d0`, and the identity of the two literal constants its real
  caller uses) is live-Unicorn-confirmed against real DLL bytes, to the same
  standard this whole port already holds itself to. The *very last hop* —
  whether `ImaICCEffectOperation` (`0x10365510`) forwards this object's
  `max` field verbatim into `apply`'s own `[ebp+0x10]` double, rather than
  transforming it somehow first — was **not** itself live-traced: `0x10365510`
  dispatches through several vtable calls on its own `this` object right at
  entry (`[edi+0x20]`'s vtable slot `+0x1c`, then more on `[edi+0x3c]`),
  which would need a properly RTTI/vtable-shaped mock object to execute
  live — the same class of "generic operand-construction machinery" the
  concurrent citras-driver passes (above) found expensive to mock correctly,
  and attempting it here risked spending that same order of effort on a
  question this pass judged already well-answered structurally: the 24-byte
  object is shaped exactly like a range-bearing type descriptor (header +
  two doubles), `apply`'s own `[ebp+0x10]` read is a bare double with no
  other shape it could sensibly come from on this call path, and
  `ImaICCEffectOperation`'s whole documented job (per its own error strings)
  is to validate and forward exactly this kind of descriptor into the real
  xform — so the inference is reported as **high-confidence, not
  fully closed end-to-end**, an honest middle ground between "still open"
  (no longer accurate) and "fully live-verified every hop" (not attempted).
  `kodakcms.dll` itself (`/Users/guy/Downloads/Pakon Update 3/fx35install/System32/kodakcms.dll`)
  was not traced further — this pass's question was "what does PakonIMAu.dll
  tell KCMS," which is now answered; what KCMS's own CLUT interpolation
  then does with a 16-bit-domain input is `docs/62`'s separately-tracked
  ranked item #4, still open, not attempted here.

**Track 2 — `scene_type=0`: well-evidenced as correct, and shown to have
zero effect on `dra`'s lighting fork either way. No fix needed; nothing to
hand off.**

Read `pakon_autotone.py`'s own `CTX_SCENE_TYPE = 0x44` comment
("tested ==7 by the driver, ==1 in the epilogue") and `pakon_contrast.py`'s
`SLOPE_BAND_BY_SCENE_TYPE`, then went one level further than either file
does: live-disassembled the real scene driver
(`fcn.10069490`, `0x10069490`..`0x10069c07` — the function `docs/64` already
cites for `CalcDei`/`flesh`, re-used here rather than re-found) to see what
`ctx+0x44` actually gates *outside* `analyzeAutoTone`'s own body, and where
its non-default values lead:

* `[esi+0x44] == 7` (checked at `0x100699e7`, `esi` being this driver's own
  context) makes the driver call `0x100fb080` **instead of**
  `analyzeAutoTone` (`0x100fb730`) entirely — confirmed by self-naming
  string (`ColorNegativePath::analyzeAsea`), not inferred from proximity.
  So `scene_type == 7` doesn't feed `asea` data into `autoTone`; it replaces
  `autoTone` with `asea` for that scene, at the driver level, one call site
  earlier than `analyzeAutoTone`'s own frame. Since this whole port's
  premise (`docs/65`, `docs/66` throughout) is that `analyzeAutoTone` really
  is the stage that runs and needs fixing for this scanner's frames, `7` is
  not a candidate value for this render — if it were, `analyzeAutoTone`
  wouldn't be the function running at all.
* `scene_type == 1` (epilogue, already documented) nulls the produced tone
  object entirely (`ctx+0x64d0 = 0`) — i.e. "run the full chain, then throw
  the curve away, no correction applied." `real_auto_tone()` already handles
  this (passes `x` through unchanged). But the *measured* behaviour of the
  real chain on this frame is a strong, non-identity compression (dra
  `effMin`/`effMax` ≈ 1690–2614, prior 6.2 passes) — not a pass-through — so
  `1` is empirically inconsistent with what's actually being observed on
  this frame and is not a plausible value here either.
* `scene_type` in `{3..6}` is reset to `0` **before** `contrast.acquire` ever
  sees it (`pakon_autotone.py`'s own mid-flow fixup, already ported/verified)
  — so even if the real value were 3–6, `contrast`'s own slope-band selection
  behaves identically to `0` regardless.
* **`dra`'s separate Normal/Backlit/Frontlit lighting fork is NOT driven by
  `scene_type`/`ctx+0x44` at all** — it's a completely different mechanism,
  a `find("lighting")` capability-bag lookup, already independently
  documented in `pakon_dra.py` as confirmed to always MISS on this render
  path (nothing populates a `"lighting"` bag entry), which is *itself*
  defined to default to Normal (`lighting_from_find`, "a miss continues,
  yielding lighting 0"). This was pre-existing, verified work, not
  re-derived here — but it directly answers this track's own question:
  **changing `real_auto_tone()`'s `scene_type` parameter would not change
  `dra`'s effective lighting dispatch on this frame at all**, because that
  dispatch is fixed at Normal by a wholly separate, already-resolved code
  path. This rules `scene_type` out as an explanation for a wrong lighting
  curve specifically.

**Conclusion**: by elimination (`7` contradicts the port's own premise, `1`
contradicts the measured non-identity output, `3..6` collapse to `0` before
contrast reads them anyway, and `dra`'s lighting fork is unaffected by any of
this regardless), `0` — the vendor's own `AutoToneContext()` default and
what `real_auto_tone()` already hardcodes — is the best-evidenced value for
this frame. Not proven with a traced real-frame classifier (none was found;
this project has not identified where a legitimate non-zero, non-default
`scene_type` would come from for an ordinary colour-negative scan), but
every alternative is independently contradicted by existing evidence. No
edit recommended; nothing to hand off to `pakon_ansel.py`.

**Track 3 — histogram/image construction: the balance→FUGC ordering into
`real_auto_tone()` is independently re-confirmed correct from a SECOND angle;
one real, unresolved, well-scoped new lead found (not the ordering).**

Read `pakon_cna.py`'s own calling-convention docs (`arg2` = "the image
descriptor", `0x1022ea50`'s fourth stack argument) against
`pakon_ansel.render_scene`'s actual call site: `real_auto_tone(x)` is called
with `x` already balance-shifted AND already passed through
`apply_1d_lut(x, apply_lut)` (the FUGC apply LUT) — i.e. `cna`'s histograms
are built from the post-balance, post-FUGC array, matching the already-landed
stage-order fix from the second 6.2 pass above (which was based on the
EXPORT-phase pack order, `AnsCnEnhancedPath::exportParameterPack`).

This pass independently re-derived the same conclusion from the **ANALYZE**
phase instead, as a genuinely separate check (not just re-reading the same
evidence): live-disassembled `fcn.10069490` (the real
`CnEnhanced`-scene-specific analyze driver, self-named calls confirmed for
every stage below) and read off its full, real call order for the first
time — this project had previously only cited isolated pairs out of this
function (`analyzePostBalance`/`CalcDei` for `docs/64`'s `dei`/`flesh`
resolution), not the whole sequence:

```
analyzePostBalance (0x100fdc40)
  → analyzeFugc (0x100fed00)
  → balanceAreaImage (0x10102b20)     -- bakes filmLut∘scpLut∘shift∘fugc in
  → analyzeArea (0x100e16d0)
  → analyzeAttributes (0x100fb3d0)
  → analyzeNoise (0x10112f30)
  → analyzeFalloff (0x100fe960)
  → [scene_type==7: analyzeAsea (0x100fb080)  XOR  else: analyzeAutoTone (0x100fb730)]
  → analyzeSharpening (0x10106780)
  → CalcDei (0x101081e0)
  → analyzeDefects (0x100e04a0)
```

FUGC precedes `autoTone` here too — a second, independent confirmation (this
function, not the export-pack function the earlier fix used) that
`real_auto_tone()` receiving post-FUGC pixels is vendor-correct, not an
artefact of one citation. Good news, not a new bug, but worth having two
independent proofs of given how much the earlier washed-out symptom hinged
on getting this exact ordering right.

**The new lead**: `analyzeArea`, `analyzeAttributes`, `analyzeNoise` and
`analyzeFalloff` **all run strictly between FUGC's composition and
`analyzeAutoTone`**, in this real, live-confirmed order — and this is not an
analyze-phase-only artefact: `docs/62` §12.4.1(b)'s independently-derived
EXPORT pack order for the same path (`…, area, falloff, asea, autoTone,
sharpening, defects`) has area and falloff in the same relative position,
before autoTone, in a *different* function found by a *different* method —
so this isn't one citation being reused, it's two independent derivations
agreeing. `docs/64` already documents `falloff` as "a real per-pixel radial
lens/scanner vignetting correction... runs before the tone stage in the same
transform sequence" and 0% ported, and `area` as writing spatial
defect/correction metadata rather than RGB data. What **wasn't** previously
established, and still isn't after this pass: whether `falloff`/`area`/
`noise`/`attributes` mutate the SAME pixel buffer object that `cna`'s
histogram-building step subsequently reads through this analyze chain (in
which case `real_auto_tone()` is missing a real, pixel-affecting
pre-processing step — falloff especially, since it's explicitly a per-pixel
correction), or whether they operate on a separate object / only publish
side-channel metadata that autoTone's own `cna`/`dra` stages never see
either way. Resolving that would mean tracing what `analyzeFalloff`
specifically returns/mutates and whether that return value is what actually
threads into `analyzeAutoTone`'s own `arg2` — a real, concretely-scoped next
step, but not attempted further this pass (per the standing instruction not
to touch `pakon_ansel.py`, and because guessing at it without a live trace
would repeat the exact mistake `docs/67` already warns about). Also noted in
passing, not chased further: the real driver's own single stack argument
into `analyzeAutoTone` (`0x10069a1d`) is a pointer to a small 2-dword local
descriptor built from two registers whose own origin wasn't traced this
pass, consistent with this project's already-established
operand/capability-object architecture rather than a raw-pixel-array ABI —
worth keeping in mind for whoever traces the above, since "the same pixel
buffer" may not be a literal single pointer identity check.

**No edit made or recommended for `pakon_ansel.py`** — the ordering already
there is (now doubly) confirmed correct; the falloff/area/noise gap is real
but not resolved to a specific, mechanical fix this pass, so there is
nothing safe to hand off as a precise before/after yet.

**Track 4 — `falloff`'s plausibility as a NEW-port-specific cause: reasoned
out, not ported (as briefed).**

`falloff` is a per-pixel correction sourced from calibration data (radial
lens/scanner vignetting), applied — per both the analyze-order and
export-order evidence above — **before** whichever tone stage runs
afterward, identically regardless of which tone stage that is. Both the OLD
two-anchor stand-in and the NEW ported `analyzeAutoTone` chain derive their
own curves from the image's own measured statistics (percentiles / trimmed
histograms) rather than from fixed absolute reference points, so a missing,
spatially-smooth, typically-small vignetting correction shifts both
variants' own input statistics by a similar small amount — it is a shared
upstream bias on both variants' input, not a differential one. This matches
the task's own suggested reasoning: **falloff is not a plausible explanation
for a washed-out-specifically-for-the-new-port symptom**, and porting it was
correctly not attempted this pass.

### A second real roll — a genuine crash fixed, and a false lead corrected (2026-08-11)

While chasing the washed-out symptom, a completely different real scanned
roll (`scan-20260810-160500.bin`, 40 frames, workspace `d3e0dc32`) was tried
as a second data point, at the owner's request. Two real findings came out
of it, one fixed, one corrected after an initial wrong read:

**1. A genuine, now-fixed crash — `cna`'s crossing-walk on real photos.**
Every one of the 40 frames crashed `pakon_cna.py`'s `_half`/`hist_resample`
with `RuntimeError: the crossing walk ran past bucket N into the
uninitialised tail of the resample scratch`. Root-caused with live Unicorn
tracing against the real DLL, using this roll's actual data: a real x87
negative-variance NaN case (which the real DLL also hits) was truncated by
the port with a raw 64-bit `ftol2` result instead of the low 32 bits the
real store instruction (`0x1022ce98`) actually keeps — for the "integer
indefinite" NaN pattern the real low dword is `0`, but the port kept
`-2**63`, sending the crossing search off the end. Fixed in `pakon_cna.py`
(truncate to `i32(...)` at that store site), plus an adjacent same-class
`_x87_div` gap in the same function. Verified: `hist_resample` against the
real DLL on the actual crashing histogram (0/500 mismatches), the full real
`0x1022ddc0` on a real 1.8M-pixel crop (bit-identical), all 40 frames
re-rendered with zero crashes (was 40/40 failing), two new synthetic
regression cases added to `pakon_cna_golden.py`, full fleet re-run clean.
**This crash was invisible to every prior test on this project** — Phase
6.1's own synthetic scenarios and the single previously-used real frame
(`08_raw14.tiff`) never happened to hit this degenerate histogram shape.

**2. A false "this roll is overexposed" lead, corrected the same session.**
A first pass at rendering this roll found `FindDmin` reporting "no valid
Dmin" on 2 of 3 channels with the film-area window ~99%+ pinned at the 4095
ceiling, and concluded the roll itself was a bad, overexposed scan needing
a re-scan at lower gain — plausible-sounding, and wrong. A follow-up pass
re-did the measurement properly, through the pipeline's actual real
`segment_lines`/`to_rgb14`/`apply_unit_calibration`/CCD-deskew/`poly_hwc`
functions (not a hand-rolled raw-word read) over the *whole* roll, and found
**all three channels have valid, non-clipped Dmin** (`3440, 4086, 3627`,
clip fractions 0.000%/0.038%/0.004% — an order of magnitude under
`FindDmin`'s 0.1% threshold), statistically indistinguishable from the
known-good reference capture that produced `08_raw14.tiff`
(`3433, 4040, 3631`, clip fractions in the same range). The exposure triad
(`integration=4093, lamp_n=982, line_rate=60, pixel_offset=32`) matches
`calibration/README.json` exactly — not a stale-calibration issue either.
**The original "clipped/overexposed" finding does not reproduce and should
be treated as an artifact of that specific pass, not a property of this
scan.** Also checked, per the owner's explicit question, whether either
this project or the real vendor software has any per-roll/per-frame
auto-exposure mechanism: neither does. This project's `pakon_scan.py`
states outright that exposure is read fixed from `calibration/README.json`
and "not exposed as settings"; the vendor's own documented COM API surface
(`docs/04-api-surface.md`, 1,139 identifiers) puts exposure/gain/lamp
intensity under `ICalibrationWizard` (a technician calibration procedure),
and `ScanPictures`'s own control flags contain no exposure/gain/lamp
parameter — exposure is a fixed calibration-time operating point on both
sides, not a per-roll adjustment. Real and worth knowing, but not what was
happening on this roll.

**Net effect**: this roll is a genuine, valid second real-world test case,
not a bad scan — which strengthens rather than explains away the washed-out
finding, since the same low-contrast/washed-out symptom (per-channel `icc`
means ≈229/235/234, matching the "far too light" bypass signature) shows up
on it too, on completely different photographic content. The `citras`-apply
operand-wiring investigation (6 passes in, `docs/66`'s earlier sections)
remains the live, correct thread to pull on.

### Interim, deliberately-not-bit-exact fix for the desaturation symptom (2026-08-11) — **SUPERSEDED, no longer in the code**

> **Status as of 2026-08-12 (ninth pass, below): this whole section is
> history.** Both improvised parts described here are gone from
> `pakon_ansel.real_auto_tone()`. The luminance-delta broadcast turned out to
> be the *right shape for the wrong reason* — it really is what
> `virtual_56` does — and is now produced by the real traced mechanism rather
> than by hand; the `0.90` multiplicative darken is deleted and NOT replaced
> by another constant. `real_auto_tone()` contains no non-vendor-derived
> constants. Kept below unedited because the diagnosis in it (per-channel
> lookup desaturates; the delta form preserves channel separation) is what
> pointed at the right shape, and because the numbers here are the baseline
> the ninth pass measures against.

While the `citras`-apply operand trace continued in the background, actually
comparing rendered thumbnails side by side surfaced a sharper diagnosis than
"washed out": on the second roll, `real_auto_tone()`'s channels were
converging to within ~10-16/255 of each other (near-monochrome), versus
~90-120 apart on the stand-in — because the naive `lut_arr[pixel_value]`
lookup in `pakon_ansel.py` applies the tone curve to R, G, and B
**independently**, which drives all three toward the same output wherever
the curve is steep.

Landed a deliberately partial fix, using only already-Unicorn-verified
building blocks (`pakon_citras_apply.apply_luminance`'s formula,
`apply_tone_compose`'s "1-band base broadcasts to all bands" shape) but
**skipping** the still-unresolved gradient-aware avoidance-blend: tone the
luminance only, then add the resulting delta to all three original channels
equally, instead of running each channel through its own copy of the curve.
This is explicitly NOT the verified vendor mechanism — it's a stopgap so the
worst symptom stops blocking everything else, pending the real operand
trace.

**Measured on `08_raw14.tiff`** (`/tmp/pakon_re/interim_fix_out`, local
only): channel spread jumped from near-zero to 61.8 (vs. the stand-in's own
12.6) — real colour variation restored, not a wipe. Shadow-clip (icc,
code<16) moved 25.45% → 0.15% — critically, **not exactly 0.00%** the way
the earlier, fully-naive pass measured; a small non-zero residual is a more
plausible signature of a real correction than the suspicious total wipe
seen before.

**Visual check, the standard that actually matters here**: rendered and
looked at both images directly. Real, substantial improvement on the two
worst symptoms — the shadow crush is largely gone (the foreground building
and cars, previously near-black silhouettes, now show real detail), and the
bridge tower is correctly orange/red instead of washed toward grey. **Still
visibly wrong**: the sky's warm golden-hour gradient (blue at the top,
orange near the horizon in the stand-in) is flattened to a pale, near-
uniform light blue. That's the expected fingerprint of skipping the
gradient-aware blend specifically — a flat lookup treats a large smooth
gradient (sky) the same as anything else, while the real mechanism the
operand trace is chasing exists specifically to treat smooth regions
differently from detailed ones.

**Status**: landed in `pakon_ansel.py`'s `real_auto_tone()`, `AUTO_TONE_PORTED`
left at `True` (unchanged) for continued local comparison. This is real
progress, not a finished fix — replace with the actual traced mechanism
once the `citras`-apply operand wiring is resolved. Golden fleet re-checked
(`pakon_autotone_shell_golden.py`, `pakon_autotone_assembled_golden.py`) —
unaffected, as expected, since this only touches the render-path wiring,
not any Unicorn-verified subsystem.

**Follow-up same day**: with the crush/desaturation fixed, the remaining
visible problem was simpler — the whole frame reads measurably too light
overall (confirmed by eye, both on `08_raw14.tiff` and on the two
previously-completely-crushed frames from the second roll, `docs/66`'s
"second real roll" section above). At the owner's explicit direction to
pragmatically tune this rather than wait on the full mechanism, compared
the interim output at full strength vs. scaled by 0.95/0.90/0.85 by eye and
picked **0.90** — a flat multiplicative scale on `real_auto_tone()`'s own
output, applied in `pakon_ansel.py`, commented clearly as pragmatic and
not vendor-derived. **This is not a substitute for finishing the real
mechanism** — it's explicitly a stopgap so the render looks reasonable
while that work continues; remove it once the real gradient-avoidance
mechanism lands, since a correct implementation shouldn't need an
after-the-fact brightness fudge. Re-verified: golden fleet still clean,
`08_raw14.tiff` and the two second-roll frames all look like plausible,
coherently-colored photographs at this setting (previously near-black
foregrounds and a flat-zero blue channel respectively) — screenshots
reviewed directly, not just measured.

### The second roll's frame 10/20/30 garbling — root-caused, NOT a software bug (2026-08-11)

Closing the loop on the "second real roll" section above: frames 10/20/30's
flat, blocky, false-colored (mustard-yellow/dark-green) renders are **not**
a decode bug, a framing bug, or channel misalignment/deskew. Two hypotheses
were raised and directly disproven with evidence:

- **Phase-tracking/misalignment**: refuted. `Roll.slice14` does no
  decoding at all — the whole roll is decoded ONCE in `open_capture`
  (`segment_lines` → `to_rgb14` → `ccd_deskew`), cached in `rgb14.npy`, and
  slicing is a pure array-index operation with no phase state to get
  wrong. The "phase" concept from an earlier, unrelated finding belongs to
  a completely different code path (`pakon_ui.py`'s legacy preview tool),
  not the real render pipeline.
- **Leader/splice/gap under a blind frame boundary**: refuted. The bad
  signal isn't localized to a few frame-widths — it's continuous across
  ~93% of the entire roll (roughly line 600 to line 120,000 of 128,974),
  far too large to be a splice or gap.

**Real cause**: decoding the raw wire words directly (before any
calibration) shows the BLUE channel is **bit-exact zero** — `std=0, min=0,
max=0` across millions of samples — continuously through nearly the whole
roll, with green crushed to near-zero alongside it. Only the genuine
leader (first ~500 lines) and a bright tail (~124,000+) show healthy,
balanced colour. This is corroborated independently by the roll's own
precomputed green-channel trace in `roll.json` (22 of 40 frame values sit
exactly at a floor constant, re-verified directly) and traces to the
scan's own recorded LED on-counts (`R=492, G=239, B=104`) — blue and green
were genuinely starved of light for most of this scan. No frame-boundary
or decode fix can recover signal that was never captured; a true zero
stays zero no matter what gain is applied.

The same LED imbalance appears in the reference roll's sidecar too, but
`captures/out_test/frames/08_raw14.tiff` itself — used throughout this
whole investigation and visually confirmed correct many times — evidently
sits in a healthy window of that roll, not an affected one. So this
finding doesn't call the reference frame's validity into question; it
just means the *other* roll's frames 10/20/30 were never going to render
correctly regardless of any tone-curve or decode work, because the
underlying capture is genuinely missing most of its colour information
for that stretch of film. Out of scope for this project's decode/framing
code to fix — the real issue lives in scan-time exposure/calibration
(`pakon_scan.py`/`calibration/`), a separate concern from anything in this
document.

### 6.2 continued, seventh pass — top-down hypothesis, both formulas found by disassembly, live isolation blocked on two new concrete findings (2026-08-11)

**Task, a deliberately different strategy from passes 4-6**: rather than continue the bottom-up live trace of the driver (`0x10169350`) through its generic operand-construction machinery — six passes' worth of real effort that never reached `virtual_60`/`virtual_56` — build a concrete hypothesis from everything already established (see this pass's own brief, reproduced faithfully at the top of this task), then verify or correct it empirically: isolate and directly test JUST the two still-unknown leaf computations (block-average's real algorithm, the gradient-based weight formula), and separately attempt a full end-to-end bit-exact test of the real driver against a small synthetic case.

**Block-average: found and disassembly-confirmed.** The block-average vtable (`0x1058ddf4`, `ImaBlockAverageOpBase`'s own, self-named via `"BlockAverage factor must be positive"` / `ImaBlockAverageOp.h`) has its "compute/produce" slot — the SAME vtable offset (`0x28`) citras's own driver occupies on `ImaCitrasOpBase` — at `0x10154ea0` (~1000 bytes, `0x10154ea0`..`0x1015528e`). Full raw disassembly (not decompiler output — `pdg` on the general-factor branch produced an internally-inconsistent, clearly wrong reading here, a fresh instance of `docs/67`'s "decompiler invents patterns" lesson, caught by cross-checking against the raw bytes) shows TWO independent, mutually consistent code paths:

* **`factor == 2` fast path** (`0x10155050`..`0x101550d5`): sums exactly 4 neighbour taps (`A[0,0] + A[0,1] + A[1,0] + A[1,1]`-shaped, via two pointer bases offset by one column/row stride each), then applies the textbook two-step MSVC "correctly-rounded signed divide by 4" idiom (`sum += sum<0 ? -2 : +2; sum += (sum>>31)&3; result = sum >> 2` — verified against the exact opcode sequence, not inferred from a decompiler): **a plain rounded 2×2 box average.**
* **General `factor` path** (`0x10155127`..`0x1015521f`): a nested nested-loop x87 accumulation (`fld qword [0x10573c40]` — confirmed by reading that exact address in `.rdata`, the literal double **`0.0`** — then `factor²` `fild`/`faddp` adds), followed by `if (sum >= 0.0) sum += 0.5 else sum -= 0.5; result = sum / factor²`, converted with `func_0x104ffe44` — the SAME `_ftol2`-style truncating-to-64-bit-then-keep-low-word helper this project's `pakon_cna.hist_resample` fix already catalogued (`docs/66`'s "real-roll systemic crash" entry above) — with no explicit saturating clamp, matching this codebase's established "truncate to low 16 bits" convention elsewhere. **A plain rounded `factor×factor` box average**, i.e. the SAME algorithm as the fast path, just generalized.
* The setup code immediately before the branch (`0x10154f41`..`0x10155030`) builds a SOURCE rectangle as `{row: factor*outRow, col: factor*outCol, w: factor*outW, h: factor*outH}` — i.e. **block-average is a non-overlapping DOWNSAMPLE by `blockSize`**, not a same-resolution sliding-window blur. This means the "reference" plane `virtual_60` ultimately reads is very likely a coarse grid replicated/upsampled back to full resolution by a separate coordinate-mapping accessor (the same `origin`/`stride`-bearing object family passes 4-5 already found feeding `idiv`-based coordinate mapping), not a literal same-size array — a real refinement to the working hypothesis's step 2, not just a confirmation of "simple box filter."

This is strong, internally cross-validated (two independent code paths agree), byte-exact evidence — but it is **disassembly-confirmed, not live-single-function-Unicorn-confirmed**: an isolated Unicorn call to `0x10154ea0` (thiscall `this`=block-average op with `+0x108`=factor, one stack arg=an output-accessor operand with the already-established `{row,col,w,h}` ROI fields at `+0x30/0x34/0x38/0x3c`) was attempted and immediately dove into `func_0x1032b9d0` → … → `0x1035d4fc`, the SAME generic `Ima2DImage` coordinate-mapper/subregion-accessor machinery that stopped passes 4-6 cold. This independently corroborates — via a completely different entry point than the driver-first approach — that this generic accessor family really is the project's structural bottleneck for this question, not a gap in any prior pass's effort.

**Gradient/weight: found and characterized by disassembly; live isolation blocked on a genuinely new structural finding.** The driver's own disassembly (`0x10169350`..`0x10169d0a`), re-read specifically for "anything between the luminance and avoidance-blend calls that isn't the block-average constructor," turned up a direct (`E8`, not vtable) call to `0x10168f30` at `0x10169a9f`, immediately preceded by two `fcn.1032d150` operand-builder calls and immediately followed by cleanup — the same "build → compute → release" shape as every other per-call block in this driver. `0x10168f30` (`0x10168f30`..`0x10169347`, `ret 8`) reads `this+0x11c/0x11e/0x120/0x122` — **exactly** `minAvoidance`/`maxGradient`/`lowGradientThreshold`/`highGradientThreshold`, the four DPI fields the working hypothesis named for this exact role — at its very first instructions, live-execution-confirmed as far as that point (a bounded Unicorn probe with only those four fields populated on `this` ran cleanly through the parameter-clamping logic). Its body:

1. Builds a byte lookup table (size `maxGradient+1`) via a cosine ease curve (`fcos`, confirmed live x87 opcode, not a call) that fills `100` for indices at/below `lowGradientThreshold`, ramps smoothly from `100` down to `minAvoidance` between `lowGradientThreshold` and `highGradientThreshold`, and holds flat at `minAvoidance` above `highGradientThreshold`.
2. For each output pixel, computes `mag2 = (cur - neighbourA)² + (cur - neighbourB)²` from an input plane, clamps it to `[0, maxGradient]`, and writes `weight = table[mag2]`.

This is a real, coherent, well-evidenced refinement of the working hypothesis's step 3: **weight is gradient-magnitude-driven, via a precomputed cosine-eased table, not a hand-rolled per-pixel formula** — full weight (100%) in smooth regions, minimum (`minAvoidance`%) near edges, matching the qualitative "avoid blending across edges, blend freely in smooth regions" behaviour the hypothesis predicted. **What is NOT pinned down**: the exact neighbour offset (one vs. two pixel-strides — the address arithmetic feeding the two neighbour pointers involves a `×2` this pass could not resolve with confidence given the blocker below) and which plane (`lum` vs. the block-averaged `reference`) actually feeds it, though the driver's own call ordering (after block-average, before `virtual_60`) makes `reference` the more likely candidate.

**Why this pass stopped here, a genuinely new finding, not a repeat of passes 4-6's blocker**: an isolated Unicorn call to `0x10168f30` with only `ecx=this` (matching the driver's own call site exactly — `mov ecx, edi; call 0x10168f30`, zero pushes) reads memory at `[esp+0x70]` for its "input plane" pointer that is **never written anywhere in the function's own body** (confirmed by a live memory-write watchpoint across the entire ~1000-instruction execution — zero hits at the target address) — and the function's own epilogue is `ret 8`, popping 8 bytes of "arguments" the driver's real call site never pushes. Both facts together point to the same conclusion: **this is not an independently-callable function** — it is a compiler-outlined fragment (MSVC function-splitting/PGO-style) that shares the DRIVER's own stack frame directly, reading what look like "locals" that are really specific slots in the driver's own, much larger frame, populated by driver code far earlier than this fragment's own entry. Isolating it correctly would require reconstructing the relevant slice of the driver's own frame layout at the exact call site — realistically the same scope of work as the driver trace passes 4-6 already found too large for a single pass, and exactly what this task's brief said not to re-attempt. This is reported as a genuine, evidence-based blocker, not a shortfall of effort: two independent attempts (this pass's block-average probe, and this pass's weight-function probe) reached the SAME class of wall from two different directions, which is itself useful confirmation for whoever continues.

**Full end-to-end bit-exact driver test (task step 2): not achieved**, for the reasons above — both leaf computations needed for the synthetic test resist isolation the same way the full driver already did across six prior passes, and this pass's brief was explicit that re-attempting that exact bottom-up trace was out of scope.

**Decision, per this task's own explicit instruction**: neither formula is verified bit-exact against the real DLL (disassembly-confirmed only, a real but lower evidence tier than this project's own established live-Unicorn standard). `real_auto_tone()` was **not** touched by this pass — it was found already carrying a separately-landed interim fix (see "Interim, deliberately-not-bit-exact fix for the desaturation symptom," above this section, landed concurrently by the orchestrating session) that this pass re-read fresh, did not modify, and did not merge anything into. No new `PORTED = True` flag was added anywhere; no code changed in `pakon_citras_apply.py` or `pakon_ansel.py`. `pakon_shasta.AUTO_TONE_PORTED` was found `True` and left untouched, per standing instruction.

**Visual check of the CURRENT state** (the orchestrator's interim fix, `08_raw14.tiff`, rendered via `tools/measure_python_autotone.py` + `tools/measure_shadow_clip.py --compare`, both reused unmodified): shadow-clip (`icc`, code<16) moved from the stand-in's 25.45% to 0.15% (1265× the established 0.02-point noise band) — consistent with the interim-fix section's own already-recorded number. Looking at the actual rendered thumbnail directly (both old-stand-in and new-interim, side by side): the shadow crush is genuinely gone — the foreground that was a near-black silhouette in the stand-in now shows real, plausible detail, and the bridge tower reads correctly orange rather than washed to grey. The sky's gradient is **present, not flattened to a hard band or a single flat tone** — there is a visible light-to-slightly-different-light transition from top to horizon — but the whole frame reads **too light and low-contrast overall**: the sky is a pale, milky blue-white rather than a clear saturated blue, and the general tonal range sits high. This matches the interim-fix section's own diagnosis exactly (a flat luminance lookup, lacking the gradient-aware avoidance-blend this pass's two formulas describe, cannot locally moderate how much lift a smooth region like open sky receives) and does not change the overall picture: real, measurable, visually-confirmed improvement over the old stand-in's shadow crush, but not yet a fully plausible-looking correction, and not the bit-exact vendor mechanism.

**Recommended next step for whoever picks this up**: this pass's two disassembly findings (block-average's exact algorithm, the weight table's exact construction and general shape) are solid, reusable ground truth even without live confirmation — they narrow what a future live-trace pass needs to prove, rather than starting from the task's original three-parameter hypothesis. The concrete next step for LIVE verification is not "isolate `0x10168f30` alone" (shown this pass to be structurally impossible without reconstructing driver frame state) but either (a) resume the driver-first live trace passes 4-6 already had deep into `ImaBlockAverageOp` construction, now with a known target shape to check the result against once the driver reaches `0x10169a9f`, or (b) find the driver's OWN stack-slot assignment for the two-neighbour-pixel-difference inputs by watching live memory writes to the exact physical addresses `0x10168f30` reads (`[esp+0x70]`/`[esp+0x74]`-nominal, i.e. driver-frame-relative, not fragment-relative) during a driver-first trace, which sidesteps needing the fragment to be independently callable at all.

### 6.2 continued, eighth pass — three new unbound-thunk bugs found and fixed, live trace pushed substantially deeper, a real Gaussian-kernel table construction found live, new precise blocker (2026-08-11)

**Task, per this pass's own brief**: pick one of two strategies — (A) finally crack the shared coordinate-mapper/operand-accessor family that four prior passes (4, 5, 6, 7) hit from different angles, via live single-stepping rather than more static reading, or (B) run the gradient-weight fragment (`0x10168f30`, established by pass 7 to share the driver's own stack frame and be un-isolatable) in its real, native driver context instead of trying to call it standalone. Picked up pass 6's own harness (`/tmp/pakon_re/trace_v46.py`, confirmed still reproducing the exact sixth/seventh-pass blocker byte-for-byte on a fresh run) and extended it in place through `trace_v47.py`..`trace_v50.py` (all `/tmp/pakon_re/`, scratch only, not committed, same convention as every prior pass).

**First: pass 6's own diagnosis of its own blocker was wrong, found by memory-write forensics instead of more static reading.** Pass 6 stopped at `0x10338876` (`call dword ptr [eax]` inside a destructor, `0x10338840`), where `[ebp+0x24]`'s own first field read as `0x105ba344` — a live DLL debug string's address (`"...cardReference on a ImaSmartRenderedItem..."`), not a function pointer — and attributed this to "a construction-completeness gap in this pass's own mock" (under-populated fields on `C`, the coordinate-mapper). This pass added a `UC_HOOK_MEM_WRITE` watch across the entire heap region for the literal value `0x105ba344`, and separately a watch on the exact fault address (`0xd021b40`), and reran. **The watch showed pass 6's diagnosis was wrong**: the object at `0xd021b40` legitimately receives a REAL, correct vtable (`0x105ba304`, confirmed live via the exact write instruction, `0x1035b384: mov dword ptr [esi], 0x105ba304`, matching a `1035b360`/`103440b0` real base+derived constructor pair disassembled to confirm). The corruption happens LATER: dozens of single-BYTE writes at instruction addresses `0x687e22..0x687e6a` overwrite the object's own vtable field one byte at a time with cycling garbage, eventually landing on `0x44` and turning the valid `0x105ba304` into the observed `0x105ba344`. Reading the raw PE file at `0x687e22` directly (`\x8f\x00EnterCriticalSection\x00\x00`) identified the cause: **`EnterCriticalSection` (`0x687e22`) is an EIGHTH unbound raw-RVA import thunk**, never stubbed by any prior pass (grepped `trace_v40`..`v46`: absent) — left unbound, its unbound jump target's raw `{hint,name}` table bytes get "executed" as x86 instructions, corrupting nearby heap memory before limping back into an already-mapped stub by address proximity, the exact same failure shape every prior unbound-thunk bug in this investigation has had. Reading `0x687e0a` the same way found a **ninth**, `LeaveCriticalSection` (matching `EnterCriticalSection` as a guard pair, both presumably wrapping the same registry/config lookup pass 5/6 already established as inert). Stubbing both (no-op, `stdcall`, pop 4) as `0x1032c0b0`/`0x10338840`'s own vtable-install sequence and rerunning the SAME memory-write watch found the corruption gone but a **tenth** unbound thunk, `DeleteCriticalSection` (`0x687dca`, the natural teardown counterpart of the already-stubbed `InitializeCriticalSection`), corrupting the SAME object one destructor-call further down. Stubbing all three together fully resolved the `0xd021b40` corruption (confirmed: the memory-write watch log for that address now shows only the two legitimate vtable installs and nothing else) and the trace advanced substantially past pass 6/7's exact stopping point.

**With those three fixes, the trace reached real, live-executing DLL bytes far beyond any prior pass**, including:

1. **The real block-average per-pixel compute dispatch, confirmed live**: driver call site `0x10169922` (`call dword ptr [edx+0x28]`, `edx = 0x10575b20`, the block-average vtable) dispatches into `fcn.10016d60` — matching pass 6's own static identification of this as `ImaBlockAverageOpTT`'s real per-block averaging body, now confirmed to actually execute (previously only reached via disassembly).
2. **A second, complete operand-wrapper construction cycle** (`fcn.100a3ed0` → `fcn.1032c0b0`, the same generic accessor family used for the block-average operand), this time for a DIFFERENT input — traced back to the driver reading `minValue`/`maxValue` a second time from `this+0x126/0x128` (exactly matching pass 4's own point 4, "the driver re-reads minValue/maxValue... alongside a call to `fcn.10168d90(&local, sigma)`", now reached live for the first time) and calling `fcn.10168d90(&output_slot, sigma)` directly (not through a vtable).
3. **`fcn.10168d90`, fully disassembled and confirmed live-executing, builds a genuine 1D Gaussian kernel table from citras's own `sigma` parameter**: the x87 code computes a kernel radius from `sigma`, allocates a `radius*2+1`-entry double array, and fills it via a manual `exp()` implementation (`fldl2e`/`f2xm1`/`fscale`, the standard `2^(x·log2(e))` trick for `exp(x)` on x87 hardware with no direct exponential instruction) — unambiguously a Gaussian blur/falloff kernel, not block-average or luminance math. It wraps the raw kernel array in a heap object (`operator new(0x1c)`, constructed via `fcn.102ff710`, itself built on a base object from `fcn.10300320`) with a REAL, confirmed vtable (`0x105ae2a4` derived, `0x105ae428` base — both read directly from `.rdata` and confirmed to contain real code addresses, not data), then writes that object's pointer directly into the driver's own output slot (`*output_ptr = kernel_object`, confirmed via the `mov dword ptr [ebp], esi` write at `0x10168ee0`, `ebp` = the driver's passed-in output pointer). This is the **first live-execution corroboration** of pass 7's disassembly-only gradient-weight/cosine-ease-table hypothesis — the driver genuinely does build a real, sigma-driven per-pixel weighting table at exactly the point in program order pass 7 predicted (between the block-average result and the `virtual_60` avoidance-blend call), using citras's own DPI parameters, confirmed by watching real DLL bytes execute, not by reading disassembly alone.

**Where this pass stopped, a new, precisely-located blocker**: the driver copies the just-built kernel-table object pointer into a self-referencing local wrapper struct (`temp_struct`, on the driver's own stack; the driver writes `temp_struct+0x40 = &temp_struct` — confirmed via three independent memory watches agreeing on the same value chain: `[arg]=temp_struct+4`'s neighbourhood, `[[arg]+0x40]=temp_struct` itself, `[temp_struct+0]=kernel_object`), then calls the SAME generic `fcn.1032c0b0`/`fcn.100a3ed0` operand-wrapper machinery on it. That machinery's virtual-AddRef step (`0x1032c192`..`0x1032c19b`: `ecx=[esi+0x28]`; `eax=[ecx]`; `call dword ptr [eax+4]`) resolves `eax` to the kernel-table object itself (`0xd021e50` in this run) and calls through its own `+4` field as if it were a function pointer. Disassembling the kernel-table object's real constructors (`fcn.10300320`, called first, base class) shows this field is **explicitly, deliberately set to zero** (`mov dword ptr [eax + 4], 0` at `0x10300346`) — never written again by `fcn.102ff710` afterward. A `call dword ptr [0]` is not something genuine, bug-free DLL execution would do, which means the real, correct code path does NOT reach this exact virtual-AddRef call for a self-referencing-wrapper-shaped operand the way it does for the block-average operand's heap-allocated sub-object — i.e., **this pass's mock is very likely taking a control-flow branch inside `fcn.1032c0b0` (between `0x1032c10c` and `0x1032c192`) that the real DLL, given a genuinely correctly-shaped upstream operand, would not take for this second construction** — most likely because some field this pass's mock leaves at zero (on `this`, on the driver-frame locals `fcn.1032c0b0` reads via its `arg` parameter, or on the still-largely-unmapped ROI-rect fields at `[esi+0x18..0x24]`) differs between the block-average-shaped first call (which reaches this same code and succeeds, addref'ing a smart-vtable'd dummy `sub`-object cleanly) and this second, kernel-table-shaped call. This is a genuinely NEW, more precisely bounded blocker than pass 6/7's — it is no longer "which generic accessor field is unmapped" in the abstract, it is "which specific branch condition inside `fcn.1032c0b0`'s already-disassembled 0x1c4-byte body diverges between these two call shapes," a much smaller, well-scoped follow-up than re-deriving the whole accessor family from scratch.

**Both task strategies were, in effect, pursued together and both yielded real progress**: strategy A (crack the coordinate-mapper) is what the memory-write-forensics technique (watching writes to a specific bad value/address rather than re-reading static disassembly) actually cracked — not the `Ima2DImage` origin/stride accessor itself (still not reached; the driver's second construction diverged before getting there), but the closely related "generic operand-wrapper" family blocking it. Strategy B (run the gradient-weight fragment natively) was subsumed once it became clear the fragment (`0x10168f30`) is fed by a wholly different, now much-better-understood upstream construction (`fcn.10168d90`'s Gaussian-kernel table) than originally guessed — this pass did not need to reach `0x10168f30` itself to make real progress, because the object-graph work upstream of it turned out to be the actual bottleneck.

**Decision, per this task's own explicit instruction**: `virtual_60`/`virtual_56` were **not reached**; no operand identity for `weight`/`reference`/`table`/`term`/`base` was directly observed. `real_auto_tone()` in `pakon_ansel.py` and `pakon_citras_apply.py` are both unchanged — nothing in this pass's findings is a bit-exact, end-to-end verified mechanism, and the task's own standing instruction is explicit that nothing half-confirmed gets wired. `pakon_shasta.AUTO_TONE_PORTED` was found `True` and left untouched. No render-path code changed, so no new render/measurement was performed — the current interim-fix render (documented in the seventh pass's own visual check above) is unchanged. Full golden fleet re-run after this pass (no port code changed, only scratch trace harnesses in `/tmp/pakon_re/`): `pakon_cna_golden.py`, `pakon_dra_golden.py`, `pakon_toneHelper_core_golden.py`, `pakon_toneHelper_tree_golden.py`, `pakon_contrast_lut_golden.py`, `pakon_contrast_slope_golden.py`, `pakon_ast_golden.py`, `pakon_citras_golden.py`, `pakon_citras_apply_golden.py`, `pakon_autotone_shell_golden.py`, `pakon_autotone_assembled_golden.py` all pass; `pakon_shasta_aim_golden.py` fails with the same single, pre-existing, unrelated `colneg_1px remap TLA` mismatch every prior pass has also seen — confirming zero regressions.

**Recommended next step for whoever picks this up next**: three real, generalizable, load-bearing fixes now exist for any future pass reusing this harness lineage — `EnterCriticalSection`/`LeaveCriticalSection` (`0x687e22`/`0x687e0a`) and `DeleteCriticalSection` (`0x687dca`), all stubbed as inert no-ops in `trace_v48.py` onward, the same way `InitializeCriticalSection` already was. The concrete next step is narrower than any prior pass's recommendation: with `trace_v48.py` (or later) as a starting point, single-step `fcn.1032c0b0`'s body specifically between `0x1032c10c` and `0x1032c18d` (the ROI-rect intersection computation reading `[[arg]+0]`'s own `+0x30/+0x38/+0x48/+0x34/+0x3c/+0x4c` fields) for BOTH the block-average call (which succeeds) and this second, kernel-table call (which doesn't), diffing exactly which field values differ between the two runs and which of the several `je`/`jae` branches in that range consume them — the goal being to find the ONE conditional that should route the kernel-table-shaped operand around the `0x1032c192` virtual-AddRef entirely (or through a DIFFERENT one that correctly double-dereferences through the kernel object's OWN vtable, `0x105ae2a4`, rather than treating the object's `+4` field as a function pointer directly). This is a much smaller, well-bounded task than "map the whole accessor family," since the two comparison runs (block-average vs. kernel-table) are now both reachable in the same harness and can be directly diffed instruction-by-instruction.

### 6.2 continued, ninth pass — **the operand wiring is RESOLVED**; the interim hack is gone and the real vendor apply is in the render path (2026-08-12)

**Task**: finish the citras-apply per-pixel stage — pin down the operand
wiring inside `ImaCitrasOpBase::virtual_40` (`0x10169350`) that eight prior
passes narrowed but never closed, then replace `pakon_ansel.real_auto_tone`'s
explicitly-interim stand-in (luminance-delta broadcast + a hand-tuned `0.90`
darken) with the real mechanism, and put it through this doc's own
shadow-clip + visual acceptance gate.

**Result: the wiring is resolved, with instruction-level evidence, and it is
landed.** Four of the stages the driver builds between its leaf calls are now
ALSO Unicorn-verified bit-exact against the real DLL for the first time,
including two that pass 7 explicitly reported as un-isolatable or
mis-characterised.

#### How it was cracked: stop tracing the driver, read it

Passes 4-8 all tried to get the driver *executing* under Unicorn, and each
one drowned in the generic operand-construction machinery (six passes,
roughly a dozen unbound-thunk stubs, an RTTI gate, two full wrapper
constructions). That was never necessary for the actual question. **The
operand wiring is entirely determined by the driver's own stack frame**, and
that can be read statically — provided you track ESP by hand, which is
exactly what `CITRAS_APPLY_AVOIDANCE_BLEND_PORTED`'s own comment already
records as mandatory in this function family (both `r2 pdf` and r2ghidra's
`pdg` mis-locate stack locals here).

The whole 2,490-byte body was disassembled with capstone and ESP walked
through every `push`/`call`/`ret N`. Letting `F` be ESP after the prologue
(`sub esp,0x2dc` + four register pushes), the driver's own two stack args are
`[F+0x2fc]` and `[F+0x300]`, and every SEH-state store in the body
(`mov byte ptr [esp+0x2f4], N`) is an independent ESP anchor that re-confirms
the arithmetic at ~25 points through the function.

**The cross-check that makes this a finding rather than a plausible reading**:
each of the four dispatched callees' own `ret N` matches the number of dwords
this reading says the driver pushes for it — `virtual_56` `ret 0xc` (3 args
pushed), `virtual_60` `ret 0x10` (4), `virtual_64` `ret 8` (2), the gradient
fragment `0x10168f30` `ret 8` (2). Four independent agreements, none of them
free.

The reason the pushes are easy to miss (and why pass 7 concluded
`0x10168f30`'s two args "the driver's real call site never pushes"): every
operand argument in this function is passed via the smart-pointer
copy-construct idiom `push ecx; mov ecx,esp; push &src; call 0x1003bf80`,
where the pushed value is immediately overwritten by the copy ctor
(`0x1003bf80`, `ret 4`, `*this = *src` + AddRef). The `push` that reserves
the argument slot does not look like an argument.

#### The mechanism, stage by stage (every line has its VA)

```
bs   = this->0x118                       # blockSize            0x10169555
r    = trunc(sigma * 3.0)                 # Gaussian radius      0x1016958f..a6
BW   = ceil(W/bs); BH = ceil(H/bs)         #                     0x10169561..8b
padW = BW*bs;      padH = BH*bs

obj1 = new plane(W, H, i16)                #                     0x101695f3
obj2 = new plane(max(padW,BW+2r),           # SCRATCH, reused 3x  0x10169685
                 max(padH,BH+2r), i16)
virtual_64(this, img, obj1)                  # lum = luminance()  0x101696c6
P    = mirrorPad(obj1 -> obj2, right=padW-W, bottom=padH-H)     # 0x1016977c
obj3 = new plane(BW, BH, i16)                #                    0x101697f1
obj3 = blockAverage(P, factor=bs)             # ctor 0x10169842 + slot 0x28
                                               #                   at 0x10169861
E    = mirrorPad(obj3 -> obj2, margin=r)       #                   0x10169922
K    = gaussianKernel(sigma)                    #                  0x1016994a
S    = gaussBlur(E, K)                           # "valid" conv     0x101699d7
obj4 = new plane(BW, BH, u8)                      #                 0x10169a60
gradientWeight(this, S, obj4)                      #                0x10169a9f
obj2 = upsample(S,    bs, bs); obj2.roi = {0,0,W,H} # 0x10169af7 / 0x10169ba6
obj5 = upsample(obj4, bs, bs)                        #              0x10169b7d
virtual_60(this, s=obj2, opA=obj5, opB=obj1, opC=obj2)   #          0x10169bf3
virtual_56(this, base=obj2, correction=obj1, term=img)    #         0x10169c30
```

Reading off the per-operand roles `CITRAS_APPLY_AVOIDANCE_BLEND_PORTED`
already established (`s` = i16 reference, `opA` = u8 weight, `opB` = i16
value, `opC` = i16 output), the four argument TYPES the driver supplies match
one-for-one — the byte plane really does land in the byte slot. That is a
fifth independent consistency check, not a restatement.

**`s` and `opC` are the same object.** The avoidance blend runs in place over
the reference plane. Both slots are copy-constructed from `obj2`
(`[F+0x20]` at `0x10169bde` and `[F+0x14]` at `0x10169bb7`, both holding
`obj2`). Safe because the loop reads `s[r][c]` before writing `opC[r][c]`,
which `pakon_citras_apply.apply_avoidance_blend` already happens to do.

#### Why the output is a DELTA — this is the piece that had been missing

`virtual_60` bias-subtracts the shared tone table for the duration of its own
call (`table[i] -= i` before the loop, `+= i` after — already Unicorn-verified
in `pakon_citras_apply.py`, but never connected to the driver before). So what
it writes is `toneLut[idx] - idx`: a **per-pixel luminance DELTA**, not a
toned value. `virtual_56` then adds that 1-band delta to all three bands
(base's single band broadcasts — also already verified) and clamps. Net:

```
out_rgb = clamp(rgb + (toneLut[idx] - idx), minValue, maxValue)
idx     = lum - trunc((weight*(lum - reference) + 50) / 100)
```

**Process in luma, restore chroma** — the third pass's inference, now
established rather than inferred, and with the missing detail supplied: the
curve is looked up not at the pixel's own luminance but at an index pulled
toward a heavily smoothed reference by `weight` percent. `weight == 100`
(smooth) applies the curve to the smoothed luminance; `weight ==
minAvoidance` (near an edge) applies it close to the pixel's own.

This means the interim fix's delta-broadcast was **the right shape for the
wrong reason** — it really is what `virtual_56` does — and what it was
missing was the index, not the recombination.

#### The shared tone table — docs/66's third-pass open question, closed

The third pass found the tone LUT's destination is a `Tsc1DLutT` and stopped
there. Traced the rest this pass: `AnsImaCitrasAggregate`'s ctor
(`0x100ad7f0`) reads the `AnsCitrasOperand`'s `+0x30`/`+0x34` — exactly the
`lutSize`/`ToneLut` pair `apply_set_tone_lut` writes — at `0x100ad971`, and
constructs `Tsc1DLutT<short>(ToneLut, lutSize, 1)` at `0x100ad9b8`
(`0x10099a40`). Its base ctor `0x102f4b10` stores **count = lutSize** at
`+0xc` and **bias = 0** at `+0x10`; the body copies `lutSize` words into a
fresh array behind the `+0x18` double indirection. `ImaI16CitrasOp`'s ctor
installs that object at `this->0x108` (`0x100aea02`), which is precisely what
`virtual_60` looks up. **So the analyzed tone LUT reaches a pixel through
`virtual_60`'s table, indexed directly, bias 0, count 4096.** Note this
corrects the configuration `pakon_citras_apply_golden.py` assumed
(bias `-0x8000`, count `0x10000`) — that harness tested a real DLL capability,
just not the one the shipped op uses.

One deliberate divergence, flagged not hidden: the DLL indexes that array
with a raw wrapped int16 and no bounds check, so a luminance outside
`[0, lutSize-1]` reads adjacent heap — genuine vendor UB, same family as
`pakon_dra`'s documented out-of-bounds histogram indexing. The port clamps
instead, for both the lookup and the `- idx` term so the pair stays
consistent.

#### `bDoClipping` — where it actually comes from

`ImaI16CitrasOp`'s ctor (`0x100ae9b0`) defaults `this->0x110..0x128` from the
literal block at `0x1058f4e8` (read straight out of `.rdata` this pass:
`sigma 8.25`, `blockSize 8`, `minAvoidance 70`, `maxGradient 4095`,
`lowGradientThreshold -1`, `highGradientThreshold -1`, `minValue 0`,
`maxValue 4095` — matching `pakon_citras.CITRAS_PARAMS_LAYOUT` exactly). It
additionally **hard-codes `this->0x124` (`bDoClipping`) to 1** at
`0x100aea5d` (`mov byte ptr [edi+0x14], 1`, `edi == this+0x110`). That field
is not part of `AnsCitrasParams` and has no `.dpi` source, which is why it
never showed up in the params work — the clamp in `virtual_56` is
unconditionally ON for this op.

#### Four stages newly Unicorn-verified bit-exact

New file `tools/ansel/python-pipeline/pakon_citras_driver_golden.py`. Run with:

```
PYTHONPATH=tools/ansel/python-pipeline python3 tools/ansel/python-pipeline/pakon_citras_driver_golden.py
```

1. **`0x10168f30`, the gradient-weight fragment — 9 cases, bit-exact.**
   Pass 7 concluded this "is not an independently callable function ... a
   compiler-outlined fragment sharing the DRIVER's own stack frame", on two
   real observations that were both misread. (a) The driver DOES push its two
   arguments, at `0x10169a87`/`0x10169a98`, via the copy-construct idiom
   above. (b) `[esp+0x70]` is not an uninitialised local — the function's own
   prologue (`sub esp,0x50` + four pushes) puts arg0 at exactly `[esp+0x70]`
   and arg1 at `[esp+0x74]`, and it reads the latter too, at `0x10169112`.
   Called standalone with the ordinary operand mocking
   `pakon_citras_apply_golden.py` already uses, it runs to completion and
   returns 0. Its real body: build a `maxGradient+1`-entry byte table (flat
   `100` to `lowThreshold`, cosine ease down to `minAvoidance`, flat above
   `highThreshold`, both thresholds sigma-defaulted when negative — the exact
   constants are `8057.2168125`, `0.1273`, `18.0`, `pi`, `0.5`, all read from
   `.rdata`), then per pixel `weight = table[min((cur-right)^2 + (cur-down)^2,
   maxGradient)]`, with the last column of every row and the whole last row
   set to `minAvoidance` instead (no forward neighbour). Pass 7's open
   question — one vs two pixel strides, and which plane feeds it — is
   answered: one pixel, and the plane is the **Gauss-blurred low-res
   reference**, which was pass 7's own guess.
2. **`0x10154ea0`, `ImaBlockAverageOp`'s compute — 48 cases, bit-exact**
   (both the `factor==2` integer fast path and the general x87 path, both
   signs, exact-half boundaries). Isolating it needed exactly one stub: its
   `0x1032b9d0` "give me a region covering this rect" request — the single
   call that dives into the coordinate-mapper family that blocked passes 4-7.
   Stubbing what it RETURNS rather than reimplementing it is the same scoping
   choice this project already made for every operand accessor, and it is
   what makes the function testable at all. **This corrects pass 7's rounding
   reading**: the bias added before the divide is `floor(factor**2 / 2)`, not
   `0.5` (pass 7 recorded `0.5`, which would be no rounding at all), applied
   with the sign of the sum, then a truncating divide — round-half-away-from-
   zero, agreeing with the fast path's constant-folded `+2`. The harness also
   asserts the requested source rect is `{0, 0, factor*outW, factor*outH}` —
   all four fields scaled.
3. **The four upsample kernels (`0x10154110`/`0x10154300` i16,
   `0x10154500`/`0x101546c0` u8) — 50 cases, bit-exact.** These take raw
   pointers and plain integers, no operand objects at all, so they need
   nothing mocked. Worth proving rather than assuming: the resampler is NOT
   nearest-neighbour replication (the obvious guess for an integer upscale in
   a block-averaging pipeline) but half-pixel-centred **linear interpolation
   with linear EXTRAPOLATION past both ends and no clamping**, and its
   rounding (`+r` then truncate toward zero) is asymmetric. Closed form,
   verified against all four kernels: `i = clamp(floor((2j+1-r)/(2r)), 0,
   N-2)`; `out[j] = trunc((2r*s[i] + (2j+1-r-2r*i)*(s[i+1]-s[i]) + r) / (2r))`.
4. **`0x10168d90`, the Gaussian kernel — verified, and NOT claimed bit-exact
   for a recomputed sigma.** Length, the `exp` argument and the
   sum-normalisation are all exact for every sigma tested (0.5 … 12.0), but
   the DLL's x87 80-bit `fldl2e`/`f2xm1`/`fscale` `exp` differs from
   `math.exp` by up to 4 ULP. For the ONE sigma the shipped op uses (8.25, a
   built-in constant with no `.dpi` source) the 49 DLL-produced doubles are
   embedded verbatim, so the production path IS bit-exact; the golden
   re-derives them from the DLL on every run so the constant cannot silently
   rot. **FPCW `0x027f` is load-bearing here specifically** — the constant was
   first captured under Unicorn's default control word and differed by 3 ULP,
   caught by this very check.

Also settled, from disassembly (`ImaPadOpT<short>`, `0x1014f7d0`/`0x10016d60`):
the literal `2` both pad constructions pass is **`MIRROR`**, per the mode-name
table at `0x106a3924` that the string-to-enum parser at `0x10300150` walks,
and the compute's own jump table at `0x10017c10`. The index arithmetic at
`0x1001754a`..`0x100175a9` is `srcX = abs(abs((x+W-1) % (2W-2)) - (W-1))` —
period `2N-2`, i.e. **reflect-101, edge sample NOT repeated**. The golden
checks the port's `np.pad(mode="reflect")` against that modulo form directly,
which is not a tautology: `mode="symmetric"` is an equally plausible reading
of "MIRROR" and differs on every padded pixel.

#### The one stage that is NOT bit-exact, stated plainly

`ImaConvolutionSeparableOpT<short>`'s compute (`0x100a4220`, reached through
`0x100a4010` + vtable slot `0x34`). Everything structural is established:
"valid" separable convolution, output `srcH-kh+1` x `srcW-kw+1` (so it just
consumes the `r`-pixel mirror pad and comes back the block grid's size),
**vertical pass first** into a `double` line buffer then horizontal, the same
1-D kernel on both axes (`0x10168d90` passes the same array twice at
`0x10168eb8`), write-back `acc +/- 0.5` by sign then `_ftol2` truncation
(round-half-away-from-zero), `mov word ptr`, no saturation. And a real trap
avoided: `minValue`/`maxValue` ARE passed to the ctor but **the clip flag is
0** (`this->0x13`, from the sixth ctor arg, which the driver supplies as
`esi` — still `0` from the `xor esi,esi` at `0x1016989f`), so the branch at
`0x100a4457` always skips the clamp and those two bounds are stored and never
applied. Passing two parameters and then not using them is exactly the shape
that invites a wrong guess.

What is NOT bit-exact: the DLL accumulates both passes on the x87 stack in
80-bit extended precision; the port accumulates in float64. The tap ORDER is
identical, so the only difference is intermediate rounding (~1e-13 absolute
at these magnitudes), which can only change an output where the accumulator
lands within that distance of a `.5` boundary. Not claimed to be exact, and
not hidden behind a `True` flag that means something else.

#### What changed, file by file

* **`tools/ansel/python-pipeline/pakon_citras_driver.py`** (new) — the driver
  itself. Kept separate from `pakon_citras_apply.py` deliberately: that file
  is the Unicorn-verified LEAF file and is stdlib-only with scalar per-pixel
  loops (right for emulating a few hundred pixels, hopeless for 7.4M), and it
  should not acquire a numpy dependency. Three flags:
  `CITRAS_DRIVER_WIRING_PORTED`, `CITRAS_DRIVER_GRADIENT_WEIGHT_PORTED`,
  `CITRAS_DRIVER_GAUSSIAN_KERNEL_PORTED`, all `True`, each with the evidence
  and (for the kernel) the explicit non-bit-exactness caveat in its comment.
* **`tools/ansel/python-pipeline/pakon_citras_driver_golden.py`** (new) — the
  seven checks above.
* **`tools/ansel/python-pipeline/pakon_ansel.py`** — `real_auto_tone`'s
  interim block **replaced wholesale**. Both improvised parts are gone: the
  luminance-delta broadcast (kept in effect, but now as `virtual_56`'s real
  `term + base`, fed by the real gradient-avoidance index rather than the raw
  per-pixel luminance) and the hand-tuned `0.90` darken, which is **deleted
  and not replaced by another constant** — it existed to compensate for the
  missing gradient-avoidance stage, which now exists.
* **`tools/measure_python_autotone.py`** — one real bug in the instrument: it
  `assert`ed `AUTO_TONE_PORTED is False` before rendering, which has been
  failing outright since the owner flipped that flag locally. Now forces the
  flag for the OLD render and restores it afterward; the file on disk is
  still never edited by the script.

#### Acceptance test

`tools/measure_python_autotone.py` + `tools/measure_shadow_clip.py --compare`,
on `captures/out_test/frames/08_raw14.tiff` (read locally only; nothing from
`captures/` is committed, and nothing below describes its content beyond
aggregate statistics):

| | icc tap, % of samples < code 16 |
|---|---|
| OLD (two-anchor stand-in) | 25.4533% |
| interim hack (delta-broadcast + 0.90), for reference | 0.5290% |
| NEW (real `virtual_40` mechanism) | 0.1326% |
| delta vs stand-in | **−25.32 points, 1266x the 0.02-point noise band** |

Clears the numeric gate by three orders of magnitude. But this doc's own rule
is that the number alone is not enough, and it isn't here either.

**Visual check, done by actually rendering and looking at all three, not by
reading the numbers.** Real, large, unambiguous improvement over the stand-in
on the defect this port exists to fix: the stand-in's blocked-up near-black
foreground is gone and shows genuine detail, and colours read coherently
(the bridge tower orange, not grey). The frame is a plausible photograph, not
a bypass-shaped wash. **Remaining problem, unchanged in kind from what the
2nd/7th passes already recorded: the whole frame still reads too light and
low-contrast** — icc means 159.7/205.5/220.5, p5 = 113, and the sky's
golden-hour gradient is flattened to a pale cyan. It is measurably better
than the fully-naive per-channel version those passes measured
(191.3/211.7/220.2) and worse-looking than the interim's hand-darkened
render, which is expected — the `0.90` was a deliberate brightness fudge and
removing it is what was asked.

**Root cause of the residual, and why it is NOT this pass's mechanism.**
Every intermediate the driver builds was dumped on the real frame and is
coherent: `lum` 986..2598, `blockAvg` 1072..2503, `smooth` 1268..2124,
`weight` 57..100 with median 100 (the `57` is the upsample's documented
edge extrapolation undershooting `minAvoidance`, not a bug). The toned
pre-ICC RPD-12 comes out at p1 1450 / p50 1905 / p99 2222 — a ~770-code band
— while this scene's own display mapping puts gray at 1618 and white at 3000.
The tone stage is placing the frame's midtone ~290 codes above the display's
gray point and its white ~780 below the display's white; that is the
`analyzeAutoTone` CURVE's output band versus the downstream sRGB mapping,
not the apply. It is the same thing the 1st and 2nd passes root-caused
(`cna` compresses 1129..3809 to ~1332..3247, `dra`'s `effMin`/`effMax`
1690/2614 line up with the final render's range) and it sits in code that is
Unicorn-verified bit-exact, including against real-photo pixel data up to
1,048,576 real pixels.

**One new candidate for that residual was raised and RULED OUT by direct
measurement this pass** (worth recording so nobody re-runs it): this scene
resolves to `path=CN-Premium` (the engine's own `Ansel map` line), and the
vendor's `contrast.map` and `toneHelper.map` both select CN-Premium variants
for it — but `real_auto_tone` hardcodes `contrast-CNEnhanced.dpi` and
`toneHelper-default.dpi`. That IS a real wiring inconsistency (the two
contrast DPIs differ in `csFixedIndex`, 1550 vs 1618 — and 1618 is exactly
this scene's gray point — and in their `aLowerMinSlope` limits). It is not
this symptom's cause: rendered both ways under one methodology, the toned
band moves from p1/p50/p99 = 934/1814/2337 to 920/1848/2387. About 35 codes.
Noise against a ~290-code discrepancy. Left unchanged rather than "fixed",
because changing it would alter the analysis on no evidence of benefit.

#### State of the flags

`pakon_shasta.AUTO_TONE_PORTED` was found `True` (the owner's own standing
local flip, carried since the first 6.2 pass) and is **left exactly as
found**, same as every prior pass. What changed underneath it is that the
`True` path now runs the real vendor mechanism instead of an admitted
stand-in. `real_auto_tone` contains **no non-vendor-derived constants and no
interim block** any more — that part of Phase 6.2 is finished. The full
golden fleet was re-run after every change: 27 of 28 pass, the one failure
being the same pre-existing, unrelated `pakon_shasta_aim_golden.py`
`colneg_1px remap TLA` off-by-one-code every pass since the second has also
seen. Zero regressions.
[Resolved 2026-08-12 — it was a real port bug, see the
`colneg_1px remap TLA` section at the end of this doc. The fleet is 28/28.]

#### What is still open

1. **The over-lightness.** Now cleanly isolated to the tone CURVE's output
   band versus the downstream display mapping, with the apply mechanism
   eliminated as a suspect and the per-path-DPI hypothesis measured and
   ruled out. The next concrete step is to establish what output range
   `analyzeAutoTone` is *supposed* to produce for a CN path — i.e. whether
   some stage between `exportAutoTone` and the ICC hop rescales, or whether
   `dra`'s `effMin`/`effMax` band is meant to be mapped onto gray/white
   rather than used as absolute codes. Note the 2nd pass's still-open lead
   that `analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff` all
   run between FUGC and `autoTone` in the real driver and none is replicated
   here.
2. **`gauss_blur`'s x87-vs-float64 residual**, quantified above. Closing it
   means either an 80-bit software float or live-emulating `0x100a4220`
   (which needs the plane-descriptor construction at `0x10329300` mocked —
   larger than the block-average stub but the same shape, and now clearly
   worth doing since it is the last unverified arithmetic in the chain).
3. **`ImaConvolutionSeparableOpT`'s `obj+0x11` argument** (the ctor's 4th),
   traced to a request-forwarding fallback at `0x102ff48d` and not pinned
   down. It does not touch the pixel arithmetic.
4. **Go transcription (6.3)** — untouched, and now unblocked in the sense
   that the Python side has a real mechanism to transcribe, but see (1)
   before transcribing a chain whose render still reads too light.
5. The `contrast`/`toneHelper` per-path DPI inconsistency in item 1's
   paragraph above — real, measured as immaterial for this symptom, but
   probably still worth correcting on its own terms.

## Verification summary

Every phase ends in a Unicorn-golden comparison against real DLL execution.
The project-wide acceptance test is Phase 6.2's shadow-clip measurement plus
a direct visual check on the reference frame — nothing is called "fixed"
without both.

## 6.2 — golden fleet, `colneg_1px remap TLA` (2026-08-12)

The fleet's one permanent failure. Every pass since the second recorded it
as "27 of 28, the one failure being the same pre-existing, unrelated
off-by-one" and moved on. It was neither unrelated nor unexplainable: it
was a real bug in the port, one code high, and it is fixed.

### Why it stayed folklore

The case compared `pakon_scene_context.addscene_colneg_remap_dmin_rgb`
against `pakon_color.render_pixel_f235`. Both are host Python. **Neither
side was ground truth**, so the harness could report that they disagreed
but could never say which one was wrong — and a check that cannot
adjudicate its own failure is a check that gets ignored. That is the actual
process lesson here, more than the arithmetic: a "golden" file that never
executes the DLL is not golden.

### Root cause

`addscene_colneg_remap_dmin_rgb` re-derived F-235 stage 2 as a float
closed form:

    acc = Σ_c coeff[k][c] * dens[c] / 8192
    v   = int(acc / 8 + offset[k])          # one division for the whole sum

The kernel does not sum first. `PakonIMAu.dll:0x1001c470`:

    0x1001c679  movq   mm3, [edx]          ; coeff[k][0] broadcast
    0x1001c67c  movq   mm4, [edx+8]        ; coeff[k][1]
    0x1001c680  movq   mm5, [edx+0x10]     ; coeff[k][2]
    0x1001c684  pmulhw mm4, mm1            ; ← each product truncated to its
    0x1001c687  pmulhw mm3, mm0            ;   signed HIGH WORD, independently
    0x1001c68a  pmulhw mm5, mm2
    0x1001c68d  paddsw mm3, mm4            ; only now are they added
    0x1001c694  paddsw mm3, mm5
    0x1001c697  paddsw mm3, [edx+0x60]     ; + offset[k]
    0x1001c69f  paddw  mm3, mm7            ; 0x8000
    0x1001c6a2  paddusw mm3, mm6           ; 0x7003   } clamp 0…4092
    0x1001c6a5  psubusw mm3, [edx+0x58]    ; 0xf003   }

`pmulhw` is `floor(a*b / 65536)` per lane. Since `Σ floor(x_c) ≤ floor(Σ
x_c)`, summing first and dividing once is systematically HIGH — by exactly
one code whenever the three discarded fractions carry. On the harness's own
vector, seeded dmin `(8000, 9000, 10000)`, dens `(1089, 910, 750)` and
coeff row 0 `(9165, -829, -94)`:

| product | exact | `pmulhw` (floor) |
|---------|-------|------------------|
| 9165 × 1089 | 152.29 | 152 |
| −829 × 910 | −11.51 | **−12** |
| −94 × 750 | −1.076 | **−2** |

Σ floors = 138, + offset −82 → **56**. Sum-then-divide gives 1117.65 / 8 −
82 = 57.7 → truncates to **57**. That is the entire off-by-one.

`pakon_color.render_pixel_f235`'s docstring had already warned that
"summing first and dividing once is a different function -- see docs/58
section 14.4". `addscene_colneg_remap_dmin_rgb`'s docstring claimed to
implement the same arithmetic, and then did the other thing.

### The competing hypothesis, ruled out by evidence

The obvious alternative was that the vendor genuinely produces 57 via the
x87 scalar tail at `0x1001c785`, which `render_pixel_f235` explicitly
documents as a different rounding path that "can differ by 1 LSB". If that
were the path taken, the *expectation* would have been the wrong side and
the fix would have been the opposite one. It is not the path taken:

* TLA's AddScene ColNeg leaf pushes `width = 4` — `push 4` at
  `0x1003f840` (ColRev `JT+0x4c`) and `0x1003f85d` (ColNeg `JT+0x44`),
  with `height = 1` in `edi` and the three planes in-place at
  `esp+0x34/+0x3c/+0x44`, i.e. `buf+0/+8/+16` (`0x1003f7eb…0x1003f818`
  zeroes 6 dwords = 3 planes × 4 int16, then seeds pixel 0 only).
* `0x1001c4cc` `shr ecx, 2` → the MMX block runs `width>>2` = **1**
  iteration, covering all four pixels.
* `0x1001c763` `and edx, 0x80000003` on the width, then `0x1001c776`
  `je 0x1001ca09` — with `width % 4 == 0` the scalar tail is **skipped
  entirely**. It runs zero times.

So MMX rounding *is* the vendor answer for this call site, and the 1-LSB
tail is a red herring for it.

### Verification

Ground truth is now in the harness, not in a second host function.
`pakon_shasta_aim_golden.run_colneg_planar_1px` maps PakonIMAu (MD5
`eea9dcf78ee21d4f7c515a6c2512242d`, extracted fresh from
`research/sdk/PAKONF135.iso`), nops the export's `fs:[0]` SEH prologue, and
calls the real `PIColorCorrectColNegPlanarScan` (`0x100064d0`, which
shuffles its five args into `0x1001c470`'s seven) with TLA's exact call
shape. The context block is `buildContext`'s layout, confirmed by reading
TLA `0x10012eb0`: 18 broadcast quadwords, coeff `[k][c]` at `0x18*k + 8*c`,
offsets at `0x60 + 8*k`, `+0x48/+0x50/+0x58` left for the kernel prologue
to fill with `0x8000`/`0x7003`/`0xf003`.

One mapping subtlety worth recording, since the other harnesses in this
file use a flat file→VA map: for PakonIMAu that map is exact for
`.text`/`.rdata`/`.data` raw (all three have `PointerToRawData ==
VirtualAddress`), but `.data`'s BSS tail, RVA `0x6b2000…0x6c8428`, has
`.rsrc`/`.reloc` bytes underneath it in the file — and the kernel's scratch
globals (`0x106b5b30…0x106b5b6c`) live in exactly that window. The harness
zeroes it.

Result over 7 probes, real DLL vs host:

| dmin RGB | DLL | fixed host | old host |
|----------|-----|-----------|----------|
| (8000, 9000, 10000) | (56, 0, 0) | (56, 0, 0) | (57, 0, 0) |
| (0, 0, 0) | (1977, 1495, 1369) | = | (1978, 1496, 1370) |
| (100, 200, 300) | (907, 228, 42) | = | (908, 229, 43) |
| (4000, 4000, 4000) | (185, 0, 0) | = | (187, 0, 0) |
| (1, 2, 3) | (1787, 1118, 930) | = | (1788, 1119, 931) |
| (12345, 6789, 1024) | (0, 0, 0) | = | (0, 0, 0) |
| (16383, 16383, 16383) | (0, 0, 0) | = | (0, 0, 0) |

The old body was wrong on 5 of 7 — the two agreements are both cases the
clamp floors to 0, which is why a single-vector check made it look like a
one-off curiosity rather than a systematic error.

### Blast radius

`addscene_colneg_remap_dmin_rgb` has **no callers outside
`pakon_scene_context.py` itself and the golden harness** (its only internal
caller, `addscene_dmin_rgb_from_frame`, is likewise uncalled). The F-235
dmin-prime path is not wired into any render yet, so no rendered output
changes. The Go transcription has no F-235 3×4/MMX stage 2 at all — it is
the F-135 poly path only — so there is no parallel bug to fix there.

### Fleet

Before: 27/28 (`pakon_shasta_aim_golden` failing, exactly the historical
`(57,0,0)` vs `(56,0,0)`). After: **28/28**. Every other harness's captured
output is byte-identical before and after; the only log that differs is
`pakon_shasta_aim_golden`'s.

(Note for anyone re-running: `pakon_contrast_lut_golden` prints the literal
string `FAIL` 30 times as *expected-value labels* — `dll=FAIL host=FAIL
OK` — and exits 0 with `ALL OK`. Grepping the fleet for `FAIL` will
mis-report it. Use the exit code.)
