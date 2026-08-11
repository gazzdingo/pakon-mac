# contrast (subsystem)

## Summary — "contrast" subsystem of ColorNegativePath::analyzeAutoTone

Binary: `PakonIMAu.dll` (MD5 `eea9dcf78ee21d4f7c515a6c2512242d`, PE32, from `research/sdk/PAKONF135.iso` → `fx35install/program files/Pakon/F-X35 COM SERVER/`), analyzed with radare2 6.1.8 + r2ghidra in `/tmp/pakon_re_contrast/`.

**1. Reachability from `AnsContrastAdjustCapabilityImpl::analyze` (0x101d8240)**

Direct-call BFS from 0x101d8240 (same method as the whole-chain measurement, `pdfj`-based, `type=="call"` walked, `type=="ucall"` counted as indirect):

| metric | contrast | full 6-stage chain | share |
|---|---|---|---|
| functions | **44** | 166 | 26.5% |
| code bytes | **10,953** | 67,896 | 16.1% |
| indirect (vtable) call sites | **110** | 615 | 17.9% |

(`AnsContrastAdjustCapability::acquire` at 0x1010ad20 is trivial — a 2-instruction thiscall wrapper around fcn.10109d70, not folded separately.)

**2. What it reads and computes**

`contrast-CNEnhanced.dpi` (1966 bytes) is a text param file: `maxValue=4095`, `lutSize=4096`, `userInputMode=COMBINE_WITH_SLOPE`, `lowInitialSlope/highInitialSlope=1.0`, `midpoint=1550 1550`, `lowIncr/highIncr/allIncr=0.06`, `points = 0 0 / 4095 4095`, `bConstrainSlope=true`, `csFixedIndex=1550`, `aUpperMinSlope`/`aLowerMinSlope`/`aUpperMaxSlope`/`aLowerMaxSlope` (7-element per-band slope-limit arrays).

Verified in the binary (`iz`/string xrefs): `AnsContrastAdjustParameterReader::scanOneLine`/`scanManyLines` (0x1058a610/0x1058a064) and `AnsContrastAdjustDPI::readAscii`/`initializeFromBytes` (0x105a525c/0x105a5230) parse exactly those field names — every one of them appears as an `.rdata` string with a matching `" = "` label, so the fields are genuinely consumed, not just present in the file.

Computation: a **LUT build**, not a histogram/percentile stat. `AnsContrastAdjustCapability::constrainSlope` (0x105870bc) and `AnsContrastAdjustCapabilityImpl::changeContrast` (0x10599d74) build a slope-constrained piecewise-linear curve from the midpoint/slope/increment/min-max-slope fields into a 4096-entry (`lutSize`) table. `Impl::analyze` (0x101d8240, decompiled via `pdg`) itself does not touch histograms — it mode-dispatches (`iVar1` = 0..4) between allocating scratch pixel buffers, copying, and applying the LUT as a straight index lookup (`out[i] = lut[in[i]]`), i.e. it's the per-pixel *application* of an already-built curve, with the curve-build call chained in when `*(param_1+0x78)!=0`.

**3. Execution gate — confirmed genuinely reachable, single gate only**

Verified directly in the binary, independent of any prior notes:
- `ColorNegativePath::declareAutoTone` (0x100f95f0) pushes the string `"contrast"` at 0x100f9a43, then at **0x100f9b0e**: `mov byte [eax+0xc], 1` and at 0x100f9b16: `mov byte [ecx+0xd], 1` — immediately followed by the next stage's `"ast"` registration. This sets the capability's enable byte to 1, exactly as documented.
- `analyzeAutoTone` (0x100fb730) calls contrast's acquire (0x100fc6fb → fcn.1010ad20) directly, and at **0x100fc5f6**: `mov cl, byte [edi+0xc]; test cl,cl; je 0x100fc79e` gates entry to that whole block on the same byte.

Byte is 1 → branch not taken → contrast's acquire/analyze block runs. No further/hidden gate was found beyond this single `+0xc` test. This matches the CN-Enhanced-path claim exactly for "contrast" specifically.

**4. Existing ported/verified coverage in this repo — none for this subsystem**

`grep -rli contrast tools/ansel/` hits many files, but on inspection every real implementation ("contrast" appears in code, not just prose) is for a **different, unrelated "contrast"**:
- `tools/ansel/python-pipeline/pakon_color_adjust*.py` / `pakon_ansel_c.c` — the save-path `ImaContrastLutOperation` (0x100147ed, `ColorAdjust`), a user brightness/contrast slider, ported and Unicorn-verified (`COLOR_ADJUST_CONTRAST_LUT_PORTED = True`).
- `tools/ansel/python-pipeline/pakon_fugc.py`, `pakon_ansel_maps.py`, `tools/ansel/pipeline/maps.go` — "contrast" as a **film-stock selector float** used to pick a FUGC LUT filename (`setContrast` 0x101f9a00), unrelated to `AnsContrastAdjustCapability`.

The only references to the actual subsystem (`AnsContrastAdjustCapability`, 0x1010ad20/0x101d8240, `contrast-CNEnhanced.dpi`) are in `tools/ansel/pipeline/shasta.go`'s documentation block (the stage table and `AutoTonePorted = false` / `ShastaAnalyzePorted = false` constants) — notes, not an implementation. No Go or Python code parses `contrast-CNEnhanced.dpi` or builds/applies its curve. Coverage: **0%, unported.**

**What's verified vs. not**: all four numbers, the DPI field list, the acquire/analyze/declare disassembly and decompiles, and both gate-check addresses were read directly from the binary in this session. Not independently re-derived: the exact byte offsets of the LUT-build call inside `changeContrast`/`constrainSlope` (identified only by string/xref, not fully decompiled) and whether `points`/`aUpperMaxSlope`/`aLowerMaxSlope` are consumed by the same `scanOneLine` path or a second one — plausible from the string list but not traced instruction-by-instruction.