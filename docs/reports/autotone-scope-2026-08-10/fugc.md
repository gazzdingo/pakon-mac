# fugc (producer)

## Summary: `fugc` capability reachability from `ColorNegativePath::analyzeAutoTone`

**Method:** radare2 6.1.8 (`aaa` full analysis + `avrr` vtable recovery) on `PakonIMAu.dll` (7,598,080 bytes) extracted fresh from `research/sdk/PAKONF135.iso` (`fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`), loaded at `bin.baddr=0x10000000` — matches all addresses cited in the repo's existing docs. Size/reachability used the exact same direct-call-BFS + text-based-indirect-call-count method already on disk in this environment (`/tmp/pakon_work/bfs4.py` + `indirect_classify.py`, run earlier this session against the same DLL for Shasta/FOS/dei — its output for `AnsShastaCapabilityImpl::analyze` reproduces the calibration numbers you gave: 189 funcs / 386 indirect sites exactly, 44,432 vs 44,427 bytes). I reused that method, freshly, for fugc.

### 1. Addresses — found, not assumed (verified via debug-name string xrefs + call-graph, not taken from docs)

| Symbol | Address | How verified |
|---|---|---|
| `ColorNegativePath::declareFugc` | `0x100fa400` | string xref; callers = `AnsCnPremiumPath::virtual_4`@`0x100502ba` **and** `AnsCnEnhancedPath::virtual_4`@`0x100655fa` |
| `AnsFugcCapability::acquire` | `0x10119560` | string xref (3×); sole caller `declareFugc`@`0x100fa496` |
| `AnsFugcCapability::AnsFugcCapability` (ctor) | `0x10118890` | string xref |
| `ColorNegativePath::analyzeFugc` | `0x100fed00` | string xref; callers = `0x10055ad1` (inside CnPremium) **and** `0x100697ee` (inside CnEnhanced) |
| `AnsFugcCapability::analyze` (Cap wrapper) | `0x10118af0` | sole caller `analyzeFugc`@`0x100feee0` — matches the repo's own citation in `pakon_fugc.py` |
| **`AnsFugcCapabilityImpl::analyze`** | **`0x101fc370`** | string xref (3×); sole caller `0x10118af0`@`0x10118b6b` — matches `pakon_fugc.py`'s cited address, independently re-derived |
| `AnsFugcCapability::export` (virtual) | `0x10118dd0` | vtable method `AnsFugcCapability.virtual_24`, in-degree 0 direct (vtable-only) |
| `AnsFugcCapabilityImpl::export` | `0x101f9330` | string xref; sole caller = `virtual_24`@`0x10118e26` |
| `ColorNegativePath::exportFugc` | `0x100ff770` | string xref; callers = both Path variants' `virtual_16` |

### 2. Size — measured, direct-call BFS from `0x101fc370`

**106 functions / 29,134 bytes (`realsz`) / 200 r2-typed indirect sites; 312 text-based indirect call sites (bracket/register operand), of which 118 are true vtable/register calls and 194 go through import thunks.** For scale against your two calibration points: this is roughly **56% of Shasta's function count** (189) and **44% of its indirect-site count** (386) — a substantially smaller subsystem than Shasta, and about 16% of the whole 6-subsystem `analyzeAutoTone` chain by function count (106/166 would overstate it — note fugc is *not* one of the 6 tone subsystems, it's a separate producer capability upstream of them).

### 3. Execution gate for `AnsCnEnhancedPath` — VERIFIED genuinely executed, not just declared

- `declareFugc` is called from `AnsCnEnhancedPath::virtual_4` directly (its own vtable slot, distinct from CnPremium's).
- `analyzeFugc` is called at `0x100697ee`, inside `fcn.10069490`. I confirmed via `axt` that `fcn.10069490` is called from **`AnsCnEnhancedPath::virtual_8`** and **`AnsCnEnhancedPath::virtual_12`** — i.e., it is CnEnhanced's own scene-analysis body, reached through CnEnhanced's own vtable dispatch, not a shared/ambiguous routine.
- In that same function, the call to `analyzeFugc` (`0x697ee`) precedes the call to **`analyzeAutoTone`** (`0x69a1d`) in straight-line program order, with `balanceAreaImage` (`0x69854`) in between — matching the sequence this repo's docs already recorded. No enable-byte gate (of the kind `analyzeAutoTone` uses to disable its own `pfd` sub-capability) sits around the `analyzeFugc` call; it runs unconditionally on this path.
- **Correction to the repo's own docs:** `pakon_fugc.py`'s docstring labels *both* `analyzeFugc` call sites (`0x10055ad1` and `0x100697ee`) as `CnPremium_analyzeSceneSpecific`. That's wrong for the second one. I verified from the binary that `0x10055ad1` sits inside `fcn.10054800`, called from `AnsCnPremiumPath::virtual_8/12`, while `0x100697ee` sits inside the *different* function `fcn.10069490`, called from `AnsCnEnhancedPath::virtual_8/12`. So the call that matters for a colour negative is the CnEnhanced one, and it's real — worth fixing that comment.

### 4. What it writes, and what plausibly reaches tone/density math

- `AnsFugcCapabilityImpl::analyze` builds a per-channel (RGB), 4096-entry apply LUT at `Cap+0x6140` (the `setLutInfo` output, or a single-plane bias-shifted variant in mode 2) — operating directly on the RPD/density-metric pixel codes. This is squarely tone/density-relevant, not cosmetic.
- `AnsFugcCapabilityImpl::export` (`0x101f9330`, confirmed by disassembly) tags this result under one of two literal string keys depending on a type flag: **`"fugc-lut"`** or **`"fugc-ast"`** — both verified present in that exact function.
- **Verified consumer:** `ColorNegativePath::balanceAreaImage` (`0x10102b20`) retrieves the fugc capability object by the same `"fugc"` name (via the identical internal accessor `fcn.10020a40("fugc",...)` that `analyzeFugc` itself uses) and composes it into `filmLut_c ∘ scpLut_c ∘ shift_c ∘ fugc_c`, applied to image pixels via `AnsImageData::applyLut` (`0x100d9340`) — genuine per-channel density math, applied *before* `analyzeAutoTone` runs in the same function.
- **What I could not verify:** a direct `AnsSceneContext::find(0x10022a40)` call keyed `"fugc"`/`"fugc-lut"`/`"fugc-ast"` from inside `analyzeAutoTone` or its six subsystem `Impl::analyze` functions (`cna` `0x1022ea50`, `dra` `0x1022af20`, `toneHelper` `0x101dcc50`, `contrast` `0x101d8240`, `ast` `0x10227160`, `citras` `0x10223860`) — none of these reference the `"fugc"` string. So fugc's tone effect on this path looks like it reaches `analyzeAutoTone` **indirectly**, by `balanceAreaImage` baking fugc's LUT into the pixel data `analyzeAutoTone` subsequently analyzes/acts on — not via the scene-context bag the general "producers publish, autoTone finds()" description implies. Whether `balanceAreaImage`'s composed LUT reaches the *rendered* image, or only an analysis-image copy, remains the open question this repo's own docs (`docs/58` §16.5, cited via git history) already flag as unresolved; I did not resolve it either.

### 5. Existing ported coverage — already substantial and verified in this repo

`grep` confirms: `tools/ansel/python-pipeline/pakon_fugc.py` has 12 of 13 `FUGC_*_PORTED` flags `True` (only `FUGC_EXPORT_PORTED = False`), backed by a golden-test harness `pakon_fugc_golden.py`, plus a Go port `tools/ansel/pipeline/fugc.go`. Caveat, from this repo's own `docs/62-colour-engine-consolidation.md` (dated the same day): Go's `fugc.go` has several **established, documented defects** relative to the Python port — wrong `.map` file selected, wrong branch taken for F-135 (mode 2 vs `setLutInfo`), a wrong 3-term bias formula missing the per-channel floor/R/B terms, and the `ebp18` aim-policy branch never invoked. So "already ported" is true and strong on the Python side; the Go side is known-buggy and shouldn't be treated as equivalent coverage.

---
**What's verified vs inferred:** all addresses, call-graph edges, the CnEnhanced/CnPremium split, the size numbers, and the `"fugc"`/`"fugc-lut"`/`"fugc-ast"` strings are read directly off the binary this session (commands and r2 project available at `/tmp/pakon_extract/PakonIMAu.dll` + saved project `pakon_full`; BFS scripts/output at `/tmp/fugc_work/`). The claim that fugc's effect reaches `analyzeAutoTone` only *indirectly* (via `balanceAreaImage`'s pixel LUT, not a scene-context `find()`) is a finding, not an assumption — but I did not exhaustively rule out an indirect (vtable) path from autoTone's chain to a fugc lookup, since indirect call targets are by definition not resolvable by this method. Whether `balanceAreaImage`'s composited LUT reaches the final render (vs. analysis-image only) is inherited as still-open from this repo's own prior work, not something I settled.