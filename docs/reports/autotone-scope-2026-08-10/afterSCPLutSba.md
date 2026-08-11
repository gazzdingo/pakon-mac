# afterSCPLutSba (producer)

## Summary — "afterSCPLutSba" capability, ColorNegativePath::analyzeAutoTone dependency scope

Working copy: `/tmp/afterscplutsba/PakonIMAu.dll` (extracted from `research/sdk/PAKONF135.iso`, `fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`, 7,598,080 bytes, MD5 `eea9dcf78ee21d4f7c515a6c2512242d`). radare2 6.1.8, `bin.cache=true`/`bin.relocs.apply=true`. No r2ghidra decompilation was actually needed — the binary is unstripped and carries per-function C++ assert strings (source file + `Class::method`), which is what all addresses below are anchored to.

**Important correction to the framing I was given:** "afterSCPLutSba" is **not its own capability class**. `iz` shows exactly one occurrence of the literal string, at `0x10574124`, referenced from 9 code sites — none of them construct an `AnsAfterSCPLutSbaCapability`-type object (no such RTTI name exists anywhere in `.data`). It is a **context-key string** used to look up an alternate/adjusted set of scene-balance values, produced by the **SCPLut** capability (`AnsSCPLutCapability` / `AnsSCPLutCapabilityImpl`). This is also what the repo's own `tools/ansel/python-pipeline/pakon_scp_lut.py` and `pakon_analyse_roll.py` already document (see §5) — I independently re-derived the same chain from the binary before finding that.

### 1. Own function addresses (verified from the DLL, not assumed)

| Symbol | Address | How verified |
|---|---|---|
| `AnsSCPLutCapability::analyze` | `0x101226c0` | debug string `0x105887e0` xref'd 3× inside it; prologue confirmed |
| `AnsSCPLutCapability::acquire` | `0x10122b10` | debug string `0x10588800` xref'd 2× inside it; prologue confirmed |
| `AnsSCPLutCapabilityImpl::analyze` | `0x102128f0` | debug string `0x1059da00` xref'd 4× inside it — thin try/catch shell, delegates to → |
| — real analyze body | `0x102127d0` | called once from `0x102128f0` (`e8 …` at `0x10212970`); pure FPU math, no exceptions |
| `AnsSCPLutCapabilityImpl::initialize` | region `0x102123xx–0x102126xx` (debug string `0x1059d970` xrefs at `0x10212365`/`0x1021263a`) | matches repo's own pin at `0x10212130` |
| `AnsSCPLutCapabilityImpl` ctor | region `0x102131xx` (debug string `0x1059da24` xrefs at `0x1021313b`/`0x102131d0`) | not fully bounded, low priority |

`AnsSceneContext`-style lookups of "afterSCPLutSba" all call a function at **`0x10020a40`** immediately after constructing the string (verified at 3 of the 9 xref sites: `0x1005822b`, `0x1006adab`, and inline in `pakon_scp_lut.py`'s own citation for the sibling "scpLut" lookup). The task-given `0x10022a40` for `AnsSceneContext::find` is a *different* address I did not personally hit — plausibly a separate template instantiation (repo docs cite both, treating `0x10020a40` as the capability-pointer lookup and `0x10022a40` as a separate generic scene-value `find`). Not a contradiction I could resolve either way; flagging rather than reconciling.

**Discrepancy worth flagging:** the given `AnsCnEnhancedPath::declare` address `0x10064d70` is, in the binary, a small (~0xC8-byte) struct-zeroing routine called from 6 unrelated sites across the DLL (a shared default-descriptor constructor) — not `declare` itself. The actual `AnsCnEnhancedPath::declare` (own debug string `0x1057ac58`, file `CN-Enhanced.cpp`) starts at **`0x10064ff0`**. I disassembled it and found it explicitly constructs 13 named capabilities (`StandardAnalysisImage`, `area`, `orderOrientation`, `asea`, `falloff`, `fugc`, `sharpenAdjust`, `blemish`, `color`, +4 unnamed-in-window). **`scpLut`/SCPLut is not among them** — so I could not confirm `AnsCnEnhancedPath::declare` is what registers the capability behind "afterSCPLutSba"; it's more likely declared by a shared `ColorNegativePath`-level path (unresolved, not asserted either way).

### 2. Size — direct-call reachability from `AnsSCPLutCapabilityImpl::analyze` (`0x102128f0`)

Measured with the project's proven r2pipe BFS method (walk direct calls, unique callees, tally bytes, count indirect/vtable sites):

**FUNCS = 7, BYTES = 2310, INDIRECT_SITES = 0**

Chain: `0x102128f0` → `{0x100065e0, 0x102127d0, 0x100012e0}`; `0x102127d0` → `{0x10287eb0, 0x100065e0}`; `0x10287eb0` → `{0x1028c4e0, 0x104ffe44}`.

This is far smaller than the calibration points (Shasta 189/44,427/386; analyzeAutoTone whole-chain 166/67,896/615) — SCPLut's own `analyze` bottoms out in a small closed-form numeric routine, not an orchestrator. For calibration I also re-ran the whole-chain BFS from `analyzeAutoTone` (`0x100fb730`) myself: **166 funcs / 71,760 bytes / 300 indirect sites** — function count matches the quoted 166 exactly; bytes/indirect differ from the quoted 67,896/615 (likely script/thunk-handling differences), reported as measured, not reconciled. Critically, **`0x102128f0`/`0x101226c0`/`0x10122b10` do not appear anywhere in that 166-function set** — `analyzeAutoTone` never calls into SCPLut directly; it only reads the *published result* via `find()`, confirming the declare/acquire/analyze-then-find architecture.

### 3. Execution gate for AnsCnEnhancedPath — genuinely reachable, verified (not just declared)

Unlike the Shasta case (a real switch table with no CN-Premium arm — a provable dead branch), I found **direct, unconditional calls**, not a missing-case gate:

- `ColorNegativePath::analyzeScpLutBalance` (`0x100fd190`) has two direct callers: `0x1005a3e0` (inside `AnsCnPremiumPath::CnPremium_analyzeOrderWide`, per existing repo docs) **and** `0x100691cd`, which I traced to `fcn.10068bd0` — itself called at `0x10069dfc` (immediately after `AnsCnEnhancedPath::CnEnhanced_analyzeSceneSpecific`'s own debug-string references) and at `0x1006c040` (immediately after `AnsCnEnhancedPath::analyzeScene`'s own debug-string references).
- `ColorNegativePath::analyzeBalanceOrder` (`0x10101220`, whose "second pass" is what looks up `afterSCPLutSba`/`afterSCPLutFos` instead of `sba`/`fos`, per repo docs) has 6 direct callers; 2 are inside CN-Premium's orchestrator, at least 3 more (`0x10063c5b`, `0x10069139`, `0x10069221`) sit in the same `0x1006xxxx` address block as `AnsCnEnhancedPath::analyzeScene`.
- I independently found a third direct read of the literal string, at `0x1006adab`, inside `fcn.1006a160`, called at `0x1006bf69` — squarely inside `AnsCnEnhancedPath::analyzeScene`'s own address span (`0x1006bcd7`–`0x1006bea5`), immediately followed by the same `find()`-pattern call (`0x10020a40`) used at the CN-Premium consumption site.

**Verdict: reachable/executed for AnsCnEnhancedPath specifically**, not a CN-Premium-only dead branch. Caveat (also flagged by the repo's own docs as "coupling UNKNOWN," not just by me): whether the published value ever differs from plain `sba` depends on a runtime "SCPLut enabled" flag (`"SBA disabled with SCPLut enabled"` is a logged condition inside `analyzeScpLutBalance`) — a feature toggle, not a path gate. Whether SCPLut is on by default for F-135 CN scans is a config/runtime fact I could not settle statically.

### 4. What it writes and plausible tone effect

The `AnsSCPLutCapabilityImpl` result surface (`"AnsSCPLutResults:"` string, matches the fields the FPU code at `0x102127d0`→`0x10287eb0` writes to `Impl+0x68…+0xb0`) is: **`redSlope`/`greenSlope`/`blueSlope`, `redOffset`/`greenOffset`/`blueOffset`, `slopeDist`/`slopeLimiter`/`visualGamma`** — per-channel multiplicative gain and additive bias terms plus a distance/limiter/gamma scalar. This is squarely balance/tone math (same shape as the ordinary `sba` shifts), **not** geometric, orientation, or cosmetic data. Per `docs/62-colour-engine-consolidation.md` §12.4.1(c) (already in the repo, corroborated by uncommitted scratch notes at `/private/tmp/doc46_latest.md` which I treat only as corroboration, not ground truth), the same `color`/`flesh`/`afterSCPLutSba`/`sba` contributions feed a shift LUT inside `BalanceMethods_export` that is cascaded into the actual render-chain LUT — i.e., plausibly reaches per-pixel RGB, not just an internal analysis artifact.

**Not verified:** the exact instruction that *writes*/publishes the `"afterSCPLutSba"` key into the scene context. Every site I traced that builds this string either calls the `find()`-pattern function right after (a read) or builds it into a name list alongside `"area"`/`"afterSCPLutFos"` (a dependency-name list). The repo's own docs mark this the same way ("Whether SCPLut slopes/offsets rewrite SBA shifts / FOS FPO: UNKNOWN") — so this gap is pre-existing, not something I introduced.

### 5. Existing ported/verified coverage in `tools/ansel/`

Real, substantial existing coverage — **not a gap needing fresh porting from scratch**, but explicitly incomplete on the piece that matters:

- `tools/ansel/python-pipeline/pakon_scp_lut.py` already documents this exact chain (Path `0x100fd190`, Cap `0x101226c0`, Impl `0x102128f0`, acquire `0x10122b10`, initialize `0x10212130`) at a level of detail matching (and exceeding) what I re-derived. `SCP_LUT_DPI_PARSE_PORTED=True`, `THREE_BAND_LUT_ASCII_PORTED=True`, `SCP_LUT_ANALYZE_LEAVES_PORTED=True` (the opponent/slopeDist/clamp leaves of `0x10287eb0`) — but **`SCP_LUT_BALANCE_PORTED = False`**: the actual worker maths is explicitly not ported/verified.
- `tools/ansel/python-pipeline/pakon_analyse_roll.py` documents `analyzeBalanceOrder`'s `sba`/`fos` vs `afterSCPLutSba`/`afterSCPLutFos` two-pass naming, and likewise marks the pass1/FOS/pass2/accumulation maths **UNKNOWN**.
- `tools/ansel/python-pipeline/pakon_fos.py` references the sibling `afterSCPLutFos` string constant but doesn't implement the disable branch.
- No file implements a standalone "afterSCPLutSba" capability — there isn't one to implement (see §1). Coverage is folded entirely into the (partially-ported) SCPLut port.

This is unlike `fugc` (12/13 flags `True`, real verified code per `docs/63`) — `afterSCPLutSba`'s producing/consuming machinery is real, reachable for CN-Enhanced, and touches tone math, but the maths itself is a confirmed, flagged gap in the repo today.