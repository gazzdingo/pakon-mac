# dra (subsystem)

## Summary — "dra" (AnsDraCapabilityImpl) subsystem of ColorNegativePath::analyzeAutoTone

**Environment**: `/Users/guy/www/pakon-mac` (found via `/Users/guy/www/` listing — not the shiny repo). DLL: extracted fresh from `research/sdk/PAKONF135.iso` (`fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`), md5 `eea9dcf78ee21d4f7c515a6c2512242d`, matching the copy already used in prior sessions (`/private/tmp/pakon_re/PakonIMAu.dll` etc., all identical). Tooling: radare2 6.1.8 + r2ghidra (installed), same BFS-over-direct-calls script used for prior measurements (`/private/tmp/pakon_scratch/reachability.py`).

### 1. Size / reachability (measured, not guessed)

Re-ran the exact same script against the fresh DLL, for both the seed the task specifies (analyze entry) and, as a cross-check, the whole 6-subsystem chain:

| seed | functions | code bytes | indirect call sites |
|---|---|---|---|
| whole chain, `analyzeAutoTone` 0x100fb730 (re-verified) | 166 | 71,760 | 615 |
| **dra analyze only, 0x1022af20** | **38** | **9,824** | **143** |
| dra acquire only, 0x10131100 | 42 | 10,307 | 140 |
| dra acquire+analyze combined (37 shared) | **43** | **11,850** | **161** |

Both dra sets are confirmed proper subsets of the whole chain's 166-function set (`issubset` verified programmatically). So dra's own share of the chain is **~23% of functions / ~23% of indirect call sites from analyze alone** (~26%/26% if you count acquire too) — a large but clearly partial slice of the 166/615 total.

Note: function-count (166) and indirect-count (615) reproduce the previously-quoted figures exactly; the byte count I get (71,760) differs slightly from the 67,896 quoted in `shasta.go`'s comment — same method, likely a different r2 analysis-pass/version at the time that comment was written. Flagging rather than silently reconciling.

### 2. What it reads and computes

`ansel-dra-default-default.dpi` (read directly from `vendor/ansel/anselinstalldir/dataPathItems/dra/`) has real, named fields — not opaque bytes:
`maxValue, lowFixedPoint, highFixedPoint, paperMin, paperMax, minSlope, maxSlope, binFactor, bDoAverage, lumWeighting, edgeWeighting, bIsBacklit, bIsFlash, flashFraction, backlitFraction, startingMinCumPoint, cumPctBelowMin, startingMaxCumPoint, cumPctAboveMax`, plus 6 filenames — `lowNormalTTC, highNormalTTC, lowBacklitTTC, highBacklitTTC, lowFrontlitTTC, highFrontlitTTC` — each pointing at one of the 6 `.ttc` files, which are literal `x y` tone-curve control-point pairs (e.g. `lowBacklit.ttc` has 12 breakpoints from `0 0` to `1 1`, `lowNormal.ttc`/`highNormal.ttc` are near-identity 3-point curves).

Decompiled `AnsDraCapabilityImpl::analyze` (0x1022af20, disassembled and read line-by-line, not just pseudocode): after a memoization check, it builds a **histogram**: loop at 0x1022b1a0–0x1022b1d6 reads pixel triples, computes `(v0+v1+v2+1)/3` via fixed-point reciprocal multiply (`0x55555556` = 1/3 in Q32), and bins the average into a histogram array over `width*height` samples. That, combined with the DPI's `cumPctBelowMin/AboveMax` + `startingMinCumPoint/MaxCumPoint`, is a **cumulative-histogram/percentile pass** (same family as Shasta's percentile stage), used with `paperMin/paperMax` and `minSlope/maxSlope` to pick anchor points, then select one of the 6 TTC curves by lighting classification (normal/backlit/frontlit × low/high) and build a LUT (`AnsDraCapabilityImpl::generateLut`, `draLut`) plus red-channel matrices (`draFwdMat`/`draInvMat`, strings `redRatio_`/`adjRedRatio_`/`midRangeMultiplier` also present). So: **histogram/percentile stat → tone-curve selection → LUT + matrix build**, not a simple scalar decision.

### 3. Execution gate for a colour negative

- **Enable byte**: independently disassembled `ColorNegativePath::declareAutoTone` at 0x100f98ad and confirmed `mov byte [ecx+0xc], 1` executes there (immediately preceding construction of the next stage, `toneHelper`) — this **does** set dra's +0xc enable byte to 1, consistent with the documented pattern for all six live stages.
- **The flagged "lighting" gate** (0x1022b2e1–0x1022b355, decision at 0x1022b35b): I disassembled this directly rather than trusting decompiler pseudocode. It's real and at the exact addresses previously documented. However, my own read of the branch polarity disagrees with the existing repo comment: the accessor feeding the entry check (`fcn.10021730` at 0x1022b1ef) provably always yields "not set," so the `find("lighting")` call is unconditionally reached; and at the decision point 0x1022b35b, the **miss** branch (`je 0x1022b3b0`) *skips* the logged "Failed in AnsSceneContext::find(...)" block and *continues into* the LUT-building call (0x1022ab50 → 0x1022b3cb) with a default value, while the **found** branch falls through into the error log + early return. That is the opposite of "miss is fatal." Since "lighting" is documented as absent from CN-Enhanced's declared capability list, a miss is exactly what would occur — and by my reading that's the *safe*, continuing path, not a dead end.
- I did **not** independently re-verify the "lighting is absent from CN-Enhanced's capability list" claim itself (would require decompiling the ~30-entry `declare` at 0x10064d70), so I can't fully close this loop — but I can say plainly: **I found no path by which dra fails to run and complete for a colour negative; the enable byte is confirmed set; the one flagged conditional, on my direct reading, doesn't gate dra out.** This conflicts with the existing "miss is fatal" comment in `shasta.go`, which is worth someone re-checking dynamically (e.g. under Wine) before trusting either reading fully — static reading of this SEH-laden MSVC output is genuinely error-prone.

### 4. Existing coverage in this repo

`grep -rn "AnsDra\|draLut\|draFwdMat\|draInvMat\|generateLut\|dra_default_default" tools/ansel/` returns **one hit total** — the comment in `shasta.go` itself (the "lighting" note quoted above). No parser, no LUT builder, no test — `vendor/ansel/.../dra/` data is present but, per `vendor/README.md`, "nothing reads them yet," which I confirmed holds for the actual code, not just the doc.

### What's verified vs. not

Verified directly from the binary this session: reachability counts (BFS re-run), DPI field names (read the actual file), TTC file contents (hexdumped), histogram computation (raw disassembly), enable-byte set at 0x100f98ad (raw disassembly), the "lighting" find construct and its exact addresses (raw disassembly), and zero existing ported coverage (grep).

Not independently verified this session: the claim that "lighting" is absent from CN-Enhanced's ~30-entry declared capability list (taken from prior repo documentation, not re-derived); the true intended semantics of `fcn.10021730`'s two output parameters (my polarity conclusion rests on one plausible but not dynamically-confirmed reading); and no dynamic/emulated execution was performed to settle the branch-direction disagreement.