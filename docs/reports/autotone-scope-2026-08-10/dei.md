# dei (producer)

## Summary — `dei` capability (AnsDeiCapability / AnsDeiCapabilityImpl), PakonIMAu.dll

Methodology: radare2 6.1.8 + r2ghidra, `PakonIMAu.dll` extracted from `research/sdk/PAKONF135.iso` (mounted at `/Volumes/Pakon 135 v3.0/fx35install/.../PakonIMAu.dll`, copied to `/tmp/pakon_work/`). Full `aaa` (~140–220s per run) + BFS over direct-call edges, then `realsz_check.py` + `indirect_classify.py` (text-based bracket/register-operand scan) on the resulting address list — the exact scripts and pipeline this project's earlier work used for Shasta (I reran that pipeline on `0x101e5250` as a self-check: it reproduced 189 functions / realsz 44,432 / text-indirect 386, matching the task's calibration numbers almost exactly, which validates the method before applying it to `dei`).

**1. Addresses found (not assumed) — all confirmed by disassembly, not string-grep alone**

| role | address | span/realsz | evidence |
|---|---|---|---|
| `AnsDeiCapability::acquire` | `0x10134270` | 1435/1220 B | body contains the `"AnsDeiCapability::acquire"` assert string; sole caller is `declareDei` |
| `AnsDeiCapability(Impl)::initialize` — the real per‑scene compute entry; **there is no separately‑named `::analyze` method anywhere in the DLL** for Dei (exhaustive string search on `Dei` confirms) | `0x10133960` | 1602/1602 B | body contains both `"AnsDeiCapability::initialize"` and a vendor typo `"AnsDeiCapabilty::initialize"`; sole caller is `method.AnsCnEnhancedPath.virtual_44` |
| `AnsDeiCapabilityImpl::AnsDeiCapabilityImpl` (ctor) | `0x10231130` | 1083/1083 B | body contains `"AnsArfCapabilityImpl::AnsDeiCapabilityImpl"` and `"AnsDeiCapabilityImpl::AnsDeiCapability::Impl"` — both vendor copy‑paste typos (Dei was cloned from Arf), harmless to behavior |
| `ColorNegativePath::declareDei` | `0x100f9e00` | 503 B | calls `acquire` (`0x10134270`) directly; sole caller is `method.AnsCnEnhancedPath.virtual_4` |
| `ColorNegativePath::CalcDei` | `0x101081e0` | 6748 B, 271 bbs, 148 calls | much larger orchestrator, not part of AnsDeiCapability itself — see §3/§4 |

Discrepancy worth flagging: the task's given `AnsCnEnhancedPath::declare` address, `0x10064d70`, disassembles to a 201‑byte, single‑block, **zero‑call**, `is‑pure` leaf with 6 callers scattered across the DLL (not just CN‑Enhanced) — it's a small shared registration primitive, not the 30‑capability orchestrator. The actual orchestrator matching that description is the adjacent vtable method `method.AnsCnEnhancedPath.virtual_4` at `0x10064ff0` (2089 B, 85 direct calls), which is what calls `declareDei`. `shasta.go`/`pakon_shasta.py` cite `0x10064d70` for this; I could not corroborate that specific address as the orchestrator from the binary — I can corroborate `virtual_4`.

**2. Size — measured, not guessed**, BFS from `0x10133960` (the Impl's own compute entry):

**91 functions / 22,364–22,434 bytes (realsz) / 349 indirect (text-based) call sites.**

(BFS's own tally: 91 / 22,364 realsz / 271 op-type-indirect; independent `realsz_check.py`+`indirect_classify.py` pass on the same 91-address list: 22,434 realsz / 349 text-based indirect / 412 direct call sites — the two realsz figures agree to within 70 bytes, same pattern of small residual seen on the Shasta self-check.) For scale: about half of Shasta's `analyze` (189/44,427/386) and roughly a third the size of the whole 6-subsystem `analyzeAutoTone` chain (166/67,896/615) — consistent with `dei` being one of ~16 producers feeding that chain, not a subsystem itself.

**3. Execution-gate verdict: genuinely reachable and called for AnsCnEnhancedPath — no gate found, and r2's own vtable/RTTI recovery (`avrr`) independently attributes both call sites to the `AnsCnEnhancedPath` class.**

- `declareDei` is called from `method.AnsCnEnhancedPath.virtual_4` (`0x10064ff0`) — the class-attributed declare orchestrator.
- `initialize` is called from `method.AnsCnEnhancedPath.virtual_44` (`0x10065b80`) — a distinct, later per-scene setup method, also class-attributed to `AnsCnEnhancedPath`.
- `ColorNegativePath::analyzeAutoTone` (`0x100fb730`) has exactly one caller, `0x10069a1d`, inside `fcn.10069490` — independently reproducing the prior finding in `shasta.go` verbatim.
- `ColorNegativePath::CalcDei` (`0x101081e0`) is called at `0x10069aca`, inside the *same* enclosing function `fcn.10069490`, immediately after the `analyzeAutoTone` call — i.e. after the whole 6-subsystem tone chain has already returned for that scene.

Unlike Shasta (whose only path is through a jump table with no CN-Premium case), I found no path-name/filmClass switch gating `dei`'s declare/initialize calls — they are unconditional direct calls from `AnsCnEnhancedPath`'s own methods. This is the strongest evidence available short of running the hardware.

**4. What it writes, and plausible effect on tone — partially verified, partially inferred**

Verified from strings/struct layout: `AnsDeiParams` (`DeiScpLut`, `DeiExpCorrHigh/Mid/Low`, `DeiFugcWorkHigh/Mid/Low/Total`, `DeiNeuFugc`, `DeiLumMin/Max`, `DeiExposureLevel`, `DeiEdgeMin/Max`, `DeiAggressiveness`, `DeiFleshButton`, its own `DeiDecisionTree`) are the *inputs* (DPI-file config), evaluated by `AnsDeiParams::checkDecisionNode`/`verifyDecisionTreee` (own internal decision tree, distinct from toneHelper's `deiTree1`). `AnsDeiResults` publishes a single scalar, `DeiResult`, plus a field literally named `adjToneHelperDeiValue`.

`vendor/ansel/.../toneHelper/` ships a decision tree file named `deiTree1`, and `toneHelper.map` selects `decisionTreeDei = deiTree1` for the toneHelper stage — i.e. toneHelper's own DPI config is *named* for consuming Dei's output, and `adjToneHelperDeiValue` is exactly the kind of field a tone-adjustment stage would apply. I could **not** directly confirm (by disassembly, given time budget) that toneHelper's own `Impl::analyze` (`0x101dcc50`) calls `AnsSceneContext::find` with a `"dei"` key — I checked only that `AnsDeiCapabilityImpl::initialize` and `ColorNegativePath::CalcDei` do **not** call the raw `find()` (`0x10022a40`) directly in their own bodies (0 hits each); `CalcDei` does call a nearby, unidentified helper (`0x10020a40`, 5×) that could be a typed find-and-cast wrapper, and separately calls toneHelper's own `acquire` (`0x1010c6a0`) directly — a byte-for-byte match to the address `shasta.go` independently cites as toneHelper's acquire. `AnsSceneContext::insert`'s own body was located (self-referential assert strings at `0x10023fd0…0x100243b3`) but its callers were not enumerated. **Net**: the naming and file evidence for a Dei→toneHelper data dependency is strong and internally consistent across two independent sources (this trace and `shasta.go`'s prior note), but the specific "toneHelper calls find(\"dei\")" link is inferred, not disassembly-proven. Everything Dei computes (`DeiResult`, `adjToneHelperDeiValue`, exposure/lum/edge params) is tone/exposure-shaped, not geometric or cosmetic — there is nothing in `AnsDeiParams`/`AnsDeiResults` resembling orientation or crop data.

**5. Existing coverage in this repo: none.**

`grep -rln -iE '\bdei\b' tools/` (and `docs/`) turns up exactly two files, `tools/ansel/pipeline/shasta.go` and `tools/ansel/python-pipeline/pakon_shasta.py` — both mention `dei` only as one name in the list of 16 producer capabilities `analyzeAutoTone` may read from; no `pakon_dei.py`, no `dei.go`, no ported/golden code exists. Contrast with `fugc` (extensive: `fugc.go`, `pakon_fugc.py`, `pakon_fugc_golden.py`, 12/13 flags `True` per `docs/63-port-status.md`) and `SCPLut` (`pakon_scp_lut.py`, `pakon_scp_lut_golden.py`, 3/4 flags `True`). `dei` is unstarted.

**Key files/paths**: `/tmp/pakon_work/PakonIMAu.dll` (working copy), `/tmp/pakon_work/dei_full.json`, `dei_stage3.json`, `dei_initialize_addrs.txt`, `dei_initialize_realsz.json`, `dei_initialize_indirect.json` (raw evidence for the numbers above); `/Users/guy/www/pakon-mac/tools/ansel/pipeline/shasta.go:85-97`, `/Users/guy/www/pakon-mac/tools/ansel/python-pipeline/pakon_shasta.py:530-541`, `/Users/guy/www/pakon-mac/docs/63-port-status.md`.