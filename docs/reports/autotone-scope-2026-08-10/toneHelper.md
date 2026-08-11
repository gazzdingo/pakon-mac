# toneHelper (subsystem)

## toneHelper capability — scoping report

**Binary:** `PakonIMAu.dll` (32-bit, from `/Volumes/Pakon 135 v3.0/fx35install/.../F-X35 COM SERVER/`, mounted from `research/sdk/PAKONF135.iso`), disassembled read-only with radare2 6.1.8 + r2ghidra. Project repo: `/Users/guy/www/pakon-mac` (not under `shiny/` — this task's artifacts live there, e.g. `tools/ansel/pipeline/shasta.go:53-127`, `docs/63-port-status.md §3`).

### 1. Size — direct-call reachability from `AnsToneHelperCapabilityImpl::analyze` (0x101dcc50)

BFS over direct calls only (r2pipe, `type=="call"` with a resolved `jump`; everything else — `ucall`/`rcall`/`ircall`, i.e. register/vtable/IAT-thunk calls — counted as indirect), same method as the published 166/67,896/615 total for the whole 6-subsystem chain:

- **Functions: 49**
- **Code bytes: 20,386**
- **Indirect (vtable) call sites: 26**

That's ~30% of the chain's function count and code bytes, but only ~4% of its indirect calls — toneHelper is call-graph-heavy (its own DPI/tree loader `fcn.101db020` alone is 2,145 bytes) but comparatively light on virtual dispatch next to the chain average. `acquire` (0x1010c6a0) itself is a 2-instruction trampoline into `fcn.1010bb40`, which just `memcpy`s 47 dwords out of the loaded params struct — negligible size on top, not separately BFS'd per the task's "from its analyze entry" instruction.

### 2. What it reads and computes — verified via linked class/file names and literal strings in the DLL, not guessed

`strings` on the DLL surfaces the real source tree and symbol names (`\Atc\ansel\src\libToneHelper.ansel\{AnsToneHelperCapability,AnsToneHelperCapabilityImpl,AnsToneHelperDpi,AnsToneHelperParams,AnsHistogram}.cpp`):
- `AnsToneHelperDpi::readAscii` / `::readDecisionTree` / `::initializeFromBytes` / `::copyToBytes`
- `AnsToneHelperParams::checkDecisionNode` / `::verifyDecisionTree`
- `AnsHistogram::calcHistogram` / `::calcStats` / `::calcWork` / `::calcDistance` / `::init` / `::setlimits`

The literal DPI field-name strings (`maxValue`, `thresholdMultiplier`, `thresholdReductionFactor`, `minEdgeThreshold`, `minEdgeRatio`, `smoothingSizeFactor`, `smoothingSigma`, `lowToneRange`, `midLowToneRange`, `midHighToneRange`, `highToneRange`, `decisionTree`) and the full set of decision-tree metric names (`LUM_STDDEV`, `LUM_SKEW`, `LUM_WORK_{TOTAL,SUMHIGH,HIGH,MIDHIGH,SUMLOW,MIDLOW,LOW}`, `EDGE_WORK_{TOTAL,SUMHIGH,HIGH,MIDHIGH,SUMLOW,MIDLOW,LOW}`, `EXPOSURE`, `TERMINAL`) are all present verbatim in the binary and match `vendor/ansel/.../toneHelper/toneHelper-default.dpi` field-for-field.

**Kind of computation:** a histogram-derived statistical scene classifier, not a LUT build and not a simple scalar decision. `AnsHistogram` computes per-tone-band edge/luminance energy ("work") and stats (stddev, skew) over the image; `AnsToneHelperParams` then walks one of two shipped binary decision trees (`AllOnTree1` for the analyze pass, `deiTree1` for the DEI-consuming pass — both loaded by `decisionTree`/`decisionTreeDei`) keyed on those metrics, producing an integer scene class (2/3/4 in the shipped trees). `deiTree1`'s own header comment (in the vendor file) says this class feeds forward into whether a "Shasta recalculation" or "tone limit process" runs downstream — i.e. toneHelper's output is a classification flag steering later stages, not a curve or table itself. `Impl::analyze` (0x101dcc50) decompiled cleanly and is mostly params-load/validate/error-path scaffolding (field-count checks against `AnsToneHelperParams`, a `"Bad field(#N)…in AnsToneHelperParams structure!"` exception path) plus result copy-out; the real per-field/tree work sits in its largest callees (`fcn.101db020` 2,145B, `fcn.101dbc00` 1,803B, `fcn.101dabe0` 1,074B, `fcn.101db890` 751B), which I did not decompile line-by-line (see caveats).

### 3. Execution gate — reconfirmed specifically for toneHelper, no further gate found

Disassembled `ColorNegativePath::declareAutoTone` (0x100f95f0) in full: seven "declare capability" calls in order — `0x10132f00`(cna), `0x10131250`(dra), **`0x1010c730`(toneHelper)**, `0x1010ad50`(contrast), `0x1012f4d0`(ast), `0x1012c5a0`(citras), `0x1012a710`(pfd) — each immediately followed by its enable-byte store. toneHelper's is `mov byte [eax+0xc], 1` at **0x100f9a37**, third in sequence, structurally identical (same exception-safety nesting) to the other five `=1` stores; only pfd's pair (`0x100f9da2`/`0x100f9dad`) stores `0`. None of the six `=1` stores is guarded by a data-dependent branch that differs from its siblings.

Disassembled `ColorNegativePath::analyzeAutoTone` (0x100fb730) in full: found 7 tests of that same `+0xc` byte, one per stage, each `test cl,cl; je <skip>`. The third one (`0x100fc315` → `je 0x100fc5cd`) is the *only* gate guarding the function's single call to toneHelper's `acquire` (`0x1010c6a0`, at `0x100fc4cb`). Since the byte is unconditionally 1, the skip is never taken. **Confirmed: toneHelper genuinely runs for a colour negative via `AnsCnEnhancedPath`; no further/hidden gate exists specific to it.**

### 4. Existing repo coverage — none

`grep -rn toneHelper tools/ansel/` hits exactly two files, both documentation/comment blocks (`tools/ansel/pipeline/shasta.go:37-127`, `tools/ansel/python-pipeline/pakon_shasta.py:503-590`) recording `AutoTonePorted`/`AUTO_TONE_PORTED = false`. No parser, no decision-tree evaluator, no histogram/stat code anywhere under `tools/` reads `toneHelper-default.dpi`, `AllOnTree1`, or `deiTree1`. `vendor/README.md` independently states the same: "nothing reads them yet." **Zero existing ported/verified code for toneHelper.**

### What I could not determine (vs. verified)
Verified from the binary directly: the size numbers (BFS re-run, logic sanity-checked against r2's `type`/`jump` fields), all class/file/field/metric strings, the `declareAutoTone` enable-byte assignment order and value, and the `analyzeAutoTone` gate/call-site pairing. **Not verified / inferred only:** the exact arithmetic inside the four largest callees (`fcn.101db020`/`101dbc00`/`101dabe0`/`101db890`) — I did not fully decompile them, so "histogram + decision-tree classifier" is a strong inference from names/sizes/adjacency, not a hand-traced derivation; I also did not locate the specific call site(s) that invoke `AnsHistogram::calcWork`/`calcStats` within the reachable set, nor decode what the resulting class value (`param_1+0x134`/`+0x138`) is later consumed for beyond the `deiTree1` header's own comment. I also can't reconcile my 49/20,386/26 against the other five subsystems' individual shares (not measured here) to confirm they sum to the published 166/67,896/615 — likely some callees are shared across subsystems and would be double-counted in a naive sum regardless.