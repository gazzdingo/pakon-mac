# dtt (producer)

## ColorNegativePath::analyzeAutoTone — "dtt" capability scoping report

**Method note:** All addresses below were found in the binary (string xrefs, RTTI vtable recovery via COL-pointer search, and `axt`/`afij`/`pdfj` call-graph queries against a private copy of `PakonIMAu.dll` from `research/sdk/PAKONF135.iso` → `fx35install/.../F-X35 COM SERVER/PakonIMAu.dll`, analyzed with r2+r2ghidra `aaa`), not assumed. Sizes were measured with a direct-call BFS (unique callees, summed `afij` size, tallied indirect/vtable call sites) — the same method already proven on this project; the whole-chain calibration number for `analyzeAutoTone` was independently cross-checked against `/tmp/pakon_scratch/reach_autoTone.json`, produced by a concurrent background triage already running on this exact task (166 functions / 615 indirect sites match; its byte count reads 71,760 vs. the 67,896 you cited — a small, unreconciled discrepancy I'm flagging rather than papering over, likely different-run drift in that concurrent job, not something I could account for in the time available).

### 1. Addresses (verified)

| Symbol | Address | Size | Notes |
|---|---|---|---|
| `AnsDttCapability::acquire` | `0x100f33a0` | 1421B (1206 realsz), 91 bbs, in‑degree 4 | Lazy get‑or‑construct singleton, mostly COM/exception‑safety boilerplate |
| `fcn.100f30b0` | `0x100f30b0` | — | Thin wrapper acquire() calls; does `new AnsDttCapabilityImpl` |
| `AnsDttCapabilityImpl::AnsDttCapabilityImpl` (ctor — the *de facto* "analyze") | `0x101bc3c0` | 1902B, 74 bbs, out‑degree 71 | Where the real computation runs |
| `AnsDttCapabilityImpl::checkParameters` | `0x101bc310` | 168B (165 realsz) | Single caller: the ctor above |
| dump/log fn (prints `AnsDttResults:` / `  DttResult = ` / `AnsDttParams:` / `AnsDttDPI`) | `0x101bcc40` | 106B | Called from `fcn.100f4010`, not from the ctor |
| `AnsDttCapabilityImpl` vtable | `0x105977f4` | 1 slot | Slot 0 is only the scalar‑deleting destructor (`0x101bcb50`) — **no virtual `analyze`, confirmed by walking the RTTI Complete‑Object‑Locator chain** |
| `ColorNegativePath::declareDtt` | `0x100fa000` | — | Called from `AnsCnEnhancedPath::declare`; itself calls `acquire()` directly |
| `AnsCnEnhancedPath::declare` (RTTI‑named `method.AnsCnEnhancedPath.virtual_4`) | `0x10064ff0` | 2089B | Straight‑line call into `declareDtt` at `0x10065559` |

**Architectural finding:** unlike Shasta, `AnsDttCapabilityImpl` has no separate, named or virtual `::analyze`. Its vtable has exactly one entry (the destructor). All the real work happens non‑virtually inside its **constructor**, invoked synchronously from `acquire()`.

### 2. Size (measured, direct-call BFS)

- From the Impl constructor `0x101bc3c0` (closest analog to "…CapabilityImpl::analyze"): **73 functions / 14,513 bytes / 252 indirect call sites**.
- From the outer `AnsDttCapability::acquire` `0x100f33a0` (the entry actually invoked by `declare()`): **91 functions / 19,161 bytes / 296 indirect call sites**.

Both are well under the Shasta calibration point (189/44,427/386) — consistent with dtt being a narrow classifier, not a tone engine.

### 3. Execution gate — genuinely reachable/executed for AnsCnEnhancedPath (stronger than "declared")

- `AnsCnEnhancedPath::declare` (`0x10064ff0`) makes a **direct, unconditional, straight-line** call to `declareDtt` (`0x100fa000`) — the only branch nearby is compiler-generated exception-unwind bookkeeping, not a filmClass/pathName gate.
- `declareDtt` itself **directly calls `AnsDttCapability::acquire`** (`0x100fa083 → 0x100f33a0`, confirmed by `axt`), which lazily constructs `AnsDttCapabilityImpl` right there — i.e. dtt's actual computation runs **synchronously inside `declare()`**, not deferred.
- Independently, `AnsCnEnhancedPath`'s `method.AnsCnEnhancedPath.virtual_20` (`0x10068490`, 1643B, **single basic block, cyclomatic complexity 1 — zero branches**) unconditionally lists all 16 producer-capability keys for this path — filmLut, flesh, pan, scpLut, area, orderOrientation, asea, noiseTable, pnr, nra, dei, **dtt**, falloff, fugc, toneHelper, contrast, citras — with `dtt` on identical unconditional footing to `fugc`/`filmLut`/`scpLut`. No jump table, no per‑filmClass exclusion of the kind that dropped Shasta from CN‑Premium.
- **Verdict: genuinely executed for AnsCnEnhancedPath, not merely declared.** This is a materially different (positive) result than the Shasta case.
- **Open question I could not resolve:** whether `analyzeAutoTone` (`0x100fb730`) itself, or its 6 tone subsystems, read the resulting `DttResult` back. Neither the "dtt" name constant (`0x10574100`) nor any address in dtt's compiled unit (`0x100f3xxx`/`0x101bcxxx`) appears anywhere in `analyzeAutoTone`'s own 166-function direct-call reachable set. `AnsSceneContext::find` (`0x10022a40`) *is* called from inside the Impl constructor (dtt reads context state as an input), but no `AnsSceneContext::insert` (`0x10023f10`) call was found in the constructor's direct-call list. Since this BFS only follows direct calls and the chain has 615 indirect/vtable sites, this is **not proof of non-consumption** — only that no direct-call path connects them. I could not determine the read side with confidence in the time available.

### 4. What it writes / plausible tone relevance

- Only one named field verified: **`DttResult`**, a scalar member of `AnsDttCapabilityImpl`, printed by the dump function as `"  DttResult = " << *(this+5...)`. No raw `AnsSceneContext::insert("dtt", …)` blob write was found (unlike the documented `"dmin"` bag pattern) — publication happens by caching the constructed object itself; a consumer would need to call `acquire()` again and read the member directly.
- Given the four `.dpi` variants it loads (`dtt-srcType-archive.dpi`, `-digital.dpi`, `-colorPositive.dpi`, `-colorNegative.dpi`), `DttResult` most plausibly encodes a **source-type classification** (archive scan / digital / colorPositive / colorNegative) — a film/media-class signal, not a geometric, orientation, or cosmetic value.
- I found where it's produced and named, but I could **not** trace a confirmed downstream consumer that folds `DttResult` into a tone/density/RGB formula. The only other callers of `acquire()` I found (`method.AnsArchivePath.virtual_4`, `fcn.100de810`, `fcn.1013d9e0`, plus `declareDtt`) all look like declare/construction-time call sites for other path classes, not tone-phase readers.
- **Assessment: plausibly relevant (a genuine film/source classifier, not cosmetic), but not confirmed wired into tone/exposure/density math** within what I could verify.

### 5. Existing coverage — none

`grep -rIn "AnsDtt|libDtt|\"dtt\"" tools/` across the whole repo (python-pipeline, Go pipeline, C sources) returns **zero hits**. Unlike `fugc` (12/13 flags `True`) or `SCPLut` (3/4 flags `True`, per `docs/63-port-status.md`), dtt has no ported or verified code anywhere in this project.

---

**Verified vs. inferred, explicitly:**
- Verified from the binary: all addresses/sizes in §1–2; the unconditional declare()→declareDtt→acquire() chain and the branch-free virtual_20 capability list in §3; the `DttResult` field name and dump format in §4; the acquire() caller list; the absence of ported code in §5.
- Inferred, not proven: that `DttResult` = source-type classification (strong circumstantial fit from the `.dpi` filenames, not read from a struct definition); that it plausibly-but-not-confirmedly feeds tone/density selection.
- Could not determine: whether `analyzeAutoTone`/its subsystems actually read `DttResult` back (direct-call BFS is negative; indirect/vtable paths were not traceable in the time available) — this is the one item I'm flagging as unresolved rather than guessing at.

Scratch work lives in `/tmp/pakon_r2work/` (private DLL copy, step*.r2 scripts/outputs, `dtt_bfs.py`, `dtt_bfs_implctor.json`, `dtt_bfs_acquire.json`) and a saved r2 project `dttproj` (`~/.local/share/radare2/projects/dttproj/`). Note: `/tmp/pakon_scratch/` and `/tmp/pakon_work/` are being concurrently written by another background triage job on this same binary/task — I only read from there, and my own dtt-specific analysis is entirely in `/tmp/pakon_r2work/`.