# ast (subsystem)

## AST capability scoping — `ColorNegativePath::analyzeAutoTone` stage 5

**Target:** `AnsAstCapabilityImpl::analyze` (0x10227160), `AnsAstCapability::acquire` (0x1012f3f0), in `PakonIMAu.dll` (PE32, x86, baddr 0x10000000) from `research/sdk/PAKONF135.iso` → `fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`. Tooling: radare2 6.1.8 + r2ghidra (`pdg`), full `aaa`, plus a custom BFS script (r2pipe) following only direct (immediate-target) `call` edges from the analyze entry, summing `afij` function sizes and separately logging every non-immediate-target call as a candidate "indirect" site.

### 1. Size, measured from the analyze entry (0x10227160)

| metric | value |
|---|---|
| functions reached (direct-call BFS) | **27** |
| code bytes (sum of `afij.size`) | **4,814** |
| indirect call sites, broad (any call whose target isn't an immediate) | **88** |

Caveat, found by inspecting the 88 sites individually: **83 of the 88** are `call dword [sym.imp.MSVCP71.dll_...]` / `MSVCR71.dll_...` — statically-known IAT thunks for `std::string` ctor/dtor and `sprintf` (this function does a lot of "Bad field(#N) in AnsAstParameter structure!" diagnostic string-building on its error path). Only **5** are genuine register-relative/vtable-style calls (`call edi`, all inside one shared helper `fcn.102bbd80`). I could not recover the script that produced the earlier 166/67,896/615 total, so I can't be 100% sure which definition it used — but 88/27 ≈ 3.3 indirect calls per function tracks the whole-chain's 615/166 ≈ 3.7 much better than 5/27 ≈ 0.2 does, so the broad count is very likely the comparable number. Reporting both so this isn't silently miscounted either way.

Directly measured, not scaled or estimated. This is ast's own reachable subtree only (starting at the analyze entry, per the task's own framing) — it does not include `acquire` (0x1012f3f0) or any of the other five subsystems.

### 2. What it reads and computes

No `dataPathItems/ast/` directory exists anywhere in the mounted F-X35 COM SERVER install (checked the full `anselinstalldir/dataPathItems/*` listing — `cna`, `dra`, `toneHelper`, `contrast` all have dirs; `ast` and `citras` don't). `AnsAstDPI` (`libAst.ansel/AnsAstDPI.cpp`) has both `readAscii` (file path, unused here) and `initializeFromBytes`; the string `ast-default-default` is its DPI key, resolved from a compiled-in default byte blob, not a file on disk. This matches the task's own "(no dataPathItems dir — built-in defaults)" note.

`AnsAstParams` fields (from strings adjacent to the DPI/Params symbols): **`nBins`, `nominalSlope`, `slopeFactor`, `lowSlopeResponse`, `highSlopeResponse`, `slopeDelta`** — a handful of scalars, not per-scene image statistics.

The decompiled `Impl::analyze` (pdg) confirms this shape: it validates a small int16 "band" array (≥1 entry required, else it throws `"Bad field(#N) ... in AnsAstParameter structure!"` / sets error and leaves `bAstOn` unset), copies it into an int32 working array, mirror-pads both ends by replicating the first/last value, then walks `nBins` normalized positions and blends two closed-form curve segments around a knee at `nominalSlope`:
- below the knee: `nominalSlope + (pos - nominalSlope) * lowSlopeResponse`-style linear blend,
- at/above the knee: a rational/hyperbolic blend `(nominalSlope * pos) / ((nominalSlope - pos) * highSlopeResponse + pos)`,

then remaps through an index table to produce the output LUT and sets the `bAstOn` boolean. There is no width×height pixel loop, no plane pointer, no percentile/histogram pass anywhere in this function — it's **a small parametric LUT build from ~6 built-in scalars**, not a histogram/percentile stat. Output fields (`results.astLut`, `results.bAstOn`, seen alongside sibling `ataLut`/`slopeLut` in a shared tone-results dump struct) are consumed downstream by whatever else in `analyzeAutoTone`'s chain reads the CN context, not by Shasta on this path (Shasta doesn't run for CN-Enhanced per `shasta.go`'s own documented jump-table trace).

### 3. Execution gate — confirmed, no further gate found

Independently disassembled `ColorNegativePath::declareAutoTone` around the address the project's own comment cites (0x100f9be5), not just trusted the comment:

```
0x100f9be1  mov eax, [esp+0x14]
0x100f9be5  mov byte [eax+0xc], 1      ; ast's own enable byte -> 1
0x100f9be9  mov ecx, [esp+0x14]
0x100f9bed  mov byte [ecx+0xd], 1
0x100f9bf1  push str.citras            ; next stage begins right after
```

This matches the documented claim exactly: ast's `+0xc` enable byte is set to 1, same as cna/dra/toneHelper/contrast/citras, distinct from pfd's `+0xc`/`+0xd` = 0. `analyzeAutoTone` is called from exactly one caller (`AnsCnEnhancedPath::CnEnhanced_analyzeSceneSpecific`, 0x10069a1d) per the earlier project analysis. I found no additional conditional guarding ast specifically beyond this shared per-stage flag test — the stage-dispatch itself is invoked through vtable/indirect calls (no direct xref to 0x10227160 turns up even after full `aaa`), consistent with capability polymorphism rather than a special-case skip for ast. **Verdict: genuinely reachable/executed for a colour negative, no further gate found.**

### 4. Existing coverage in this project — none

`grep -rniE "AnsAst|astLut|bAstOn|slopeFactor|nominalSlope|highSlopeResponse|lowSlopeResponse|slopeDelta|0x10227160|0x1012f3f0" tools/ansel/ vendor/` turns up only:
- `tools/ansel/pipeline/shasta.go:72` and `tools/ansel/python-pipeline/pakon_shasta.py:521` — the documentation table entry itself, not an implementation.
- `pakon_shasta.py:42` — a struct-layout note that `astLut` sits at `+0x3f0` as a *sibling* field on Shasta's own Generate object; it documents where AST's output lands in a shared dump, not AST's computation.
- One unrelated false-positive hit (`slopeDeltaThreshold` in `pakon_scp_lut.py`/SCPLut's own dpi — a different subsystem, coincidental substring match).

No `_PORTED` flag, no golden test, no Python/Go function implements ast's slope-LUT build. **Verdict: zero existing coverage** — it's referenced only as a line in the six-subsystem inventory table.

### Verified vs. not

Verified directly from the binary this session: function/byte/indirect-call counts (BFS over live disassembly), the `AnsAstParams` field names and DPI-key string, the two-segment LUT-build shape in the decompiled `analyze`, the absence of an `ast/` data directory in the mounted ISO's full install, and the `+0xc = 1` gate byte at 0x100f9be5. Not independently re-derived this session (taken from the project's prior documented trace, itself sourced from the binary): that `analyzeAutoTone` has exactly one caller and that pfd's `+0xc/+0xd` are the only ones zeroed. Not determined: which exact indirect-call definition (broad vs. register-only) the earlier 166/67,896/615 total used — flagged above rather than guessed at.