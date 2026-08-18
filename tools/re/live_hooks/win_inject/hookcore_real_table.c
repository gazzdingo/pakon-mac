/*
 * hookcore_real_table.c -- the REAL 23-address PSI.exe hook table.
 *
 * This is a byte-for-byte transcription of `HOOKS` in `../agent.js` (the
 * prior Frida version) -- same 23 addresses, same ids, same dll names,
 * same citations, in the same order (so `HookCore_BuildRealTable`'s
 * implicit index assignment 0..22 for entryThunk = Thunk_00..Thunk_22
 * lines up 1:1 with agent.js's own HOOKS array position). Per the task
 * this was built for: "reuse that exact address list and citations,
 * don't re-derive from scratch" -- nothing below was re-derived; every
 * `va`/`cite` field is copied from agent.js verbatim.
 *
 * `check_table_sync.py` in this same directory automatically parses both
 * this file and agent.js and diffs their (dll, va, id) triples, so this
 * claim is mechanically checked, not just asserted in a comment.
 *
 * exitDefault: 1 for every confirmed-address hook (entry+exit attempted
 * by default), except the two `approximate: true` entries below, which
 * are DISABLED entirely by default (see HookCore_LoadConfig) regardless
 * of exitDefault, until verified live -- exitDefault is still set
 * honestly for them (matching the others) so enabling them via hooks.cfg
 * gets sensible behavior without a second edit.
 *
 * One extra runtime note not in agent.js: `tla_colneg_mmx_kernel` (index
 * 19) is described in agent.js's own citation as "the inner MMX kernel
 * itself" -- if that runs per-scanline or per-pixel-block rather than
 * once per frame, entry+exit hooking it live could be high-frequency
 * (large log volume, measurable slowdown). It defaults to exit-enabled
 * here like everything else, but hooks.cfg lets you turn it off
 * (`tla_colneg_mmx_kernel.exit=off` or `tla_colneg_mmx_kernel=off`
 * entirely) without a rebuild if a first live run shows it's too hot --
 * see README.md.
 *
 * hotPathDisabled (added after docs/74 SS32's real disassembly of
 * `tlb_polypixel`/0x1000d880): a second, DISTINCT reason a confirmed-real
 * hook can default to off, separate from `approximate`. `approximate`
 * means "this address was never independently re-confirmed as a real
 * function entry" -- `hotPathDisabled` means the opposite (the address IS
 * confirmed real, by direct disassembly) but the hook is still off by
 * default because it's a demonstrated per-pixel/per-scanline hot path AND
 * its original live-capture purpose has since been fully resolved
 * statically, leaving nothing left for a live trace to answer. Currently
 * only `tlb_polypixel` sets this -- see its own citation below for the
 * full reasoning, and hookcore.h for the field's contract.
 *
 * notCallReachable (added 2026-08-15, root-causing the "stops mid-loop
 * under load, no shutdown message" failure that persisted across two real
 * XP-box captures -- `live_hooks_20260814-110254.jsonl` (clean shutdown)
 * and `live_hooks_20260814-112642.jsonl` (no shutdown message) -- even
 * AFTER the FlushFileBuffers-on-every-line fix): a THIRD, separate reason,
 * found by re-running `r2 -c 'aaa; af @ <va>; axt @ <va>'` against the
 * MD5/sha256-verified vendor DLLs fresh (PakonIMAu.dll sha256
 * 0ede8d9813af4ee95dddd85e5adc495a27f014a8fd4817cfbc3b3b1e107f511f per
 * reachability.py; TLA.dll md5 33f7a247d79286a31b192e83d3c37425 and TLB.dll
 * md5 193d9b2ce0a4b77ae9b78262bd06c0fc, both freshly extracted from the
 * SAME `research/sdk/PAKONF135.iso` this pass -- not independently cited
 * anywhere before this, but same verified ISO every other MD5 in this repo
 * traces back to). Five of the (non-approximate) addresses in this table
 * turned out to NOT be independently call-reachable function entries at
 * all: `af` analysis starting from the documented VA walked back to an
 * earlier, different, real function entry, and `axt` found only CODE-type
 * (jmp/jcc) cross-references from within that enclosing function, never a
 * CALL-type one. Hooking such an address with this engine's
 * calling-convention-agnostic return-address-swap technique (hookstub.S)
 * is unsafe for a reason distinct from both `approximate` (uncertain
 * citation) and `hotPathDisabled` (certain but too hot to be worth it):
 * the engine's one hard precondition -- "the DWORD at [esp] when a hooked
 * address is reached is always a real return address, because the only way
 * to reach it is via `call`" -- is simply false for these five. Reached via
 * an internal jmp/jcc instead, [esp] holds whatever real local variable or
 * spilled register the ACTUAL enclosing function happened to put there,
 * and this engine's entry stub corrupts it by overwriting it with
 * `OnReturnThunk`'s address. `sba_set_shifts_12` (see its own citation) has
 * DIRECT LIVE EVIDENCE of exactly this happening, 3 times across the two
 * new captures, every single time via the identical mechanism. Disabled by
 * default regardless of `approximate`/`hotPathDisabled` -- see
 * hookcore.h's own comment on this field for why re-enabling any of these
 * five specific VAs is never correct (unlike `approximate`, there is
 * nothing to "verify live" that would turn this back on; a genuinely new,
 * independently call-reachable address for the underlying subsystem would
 * need to be re-derived first). A SEPARATE, general engine-level guard
 * (`LooksLikeCodeAddress` in hookcore.c, checked before every
 * return-address swap) was added the same pass specifically so a hook NOT
 * yet known to have this problem -- including any of the 5 TLA.dll/PakonIMAu.dll
 * hooks below with zero resolvable r2 xrefs at all (`icc_effect_op`,
 * `tla_baddscene`'s siblings' own callers, etc. -- indirect/vtable calls
 * this static pass could not resolve either way) -- can't cause the same
 * corruption; per-address disabling below is the confirmed-bad list, not
 * the complete guarantee.
 */

#include "hookcore.h"

void HookCore_BuildRealTable(HookEngine *eng) {
    static void *thunks[HOOKCORE_MAX_HOOKS] = {
        (void *)&Thunk_00, (void *)&Thunk_01, (void *)&Thunk_02,
        (void *)&Thunk_03, (void *)&Thunk_04, (void *)&Thunk_05,
        (void *)&Thunk_06, (void *)&Thunk_07, (void *)&Thunk_08,
        (void *)&Thunk_09, (void *)&Thunk_10, (void *)&Thunk_11,
        (void *)&Thunk_12, (void *)&Thunk_13, (void *)&Thunk_14,
        (void *)&Thunk_15, (void *)&Thunk_16, (void *)&Thunk_17,
        (void *)&Thunk_18, (void *)&Thunk_19, (void *)&Thunk_20,
        (void *)&Thunk_21, (void *)&Thunk_22, (void *)&Thunk_23,
        (void *)&Thunk_24, (void *)&Thunk_25, (void *)&Thunk_26,
        (void *)&Thunk_27, (void *)&Thunk_28, (void *)&Thunk_29,
        (void *)&Thunk_30, (void *)&Thunk_31,
        /* Thunk_23 fixes a real, latent NULL-entryThunk bug left by the
         * prior commit (6d2e36a) that inserted analyze_scp_lut_balance
         * mid-array without adding a matching thunk -- see hookstub.S's
         * own comment on Thunk_23 for the full account. Thunk_24 is the
         * new slot for this pass's own addition, area_image_apply_lut,
         * appended at the END of table[] below specifically so no
         * existing entry's index (and therefore no existing entry's
         * thunk assignment) moves again.
         *
         * Thunk_25/26/27 (docs/74 §49, 2026-08-15): same append-only
         * discipline, for the three new TLB.dll lamp/AFE-gain/CCD-
         * acquire-control hooks (tlb_lamp_on, tlb_afe_gain_write,
         * tlb_ccd_acquire_control) added at the very end of table[]
         * below. HOOKCORE_MAX_HOOKS bumped 25->28 in hookcore.h and the
         * matching DEFTHUNK 25/26/27 added to hookstub.S in the SAME
         * commit -- double-checked specifically against the Thunk_23
         * mistake this file's own comment above documents.
         *
         * Thunk_29 (docs/74 §72.7, v21): same append-only discipline, for
         * the one new PakonIMAu.dll hook (sba_order_fpo_calc, 0x1028b8d0)
         * appended at the very end of table[] below. HOOKCORE_MAX_HOOKS
         * bumped 29->30 in hookcore.h, `extern void Thunk_29(void)` added
         * there too, and the matching DEFTHUNK 29 added to hookstub.S --
         * all in the SAME pass, re-checked against the same Thunk_23
         * mistake. */
    };

    static const HookDef table[HOOKCORE_MAX_HOOKS] = {
        /* ---- Frame / stage boundaries ---- */
        { "PakonIMAu.dll", 0x10069490, "cn_enhanced_driver",
          "AnsCnEnhancedPath per-scene analyze driver (fcn.10069490) -- "
          "the real call-order spine: analyzeFugc -> balanceAreaImage -> "
          "analyzeArea -> analyzeAttributes -> analyzeFalloff -> "
          "analyzeAutoTone -> analyzeSharpening -> ...",
          "docs/74 SS11 (call order), docs/62 line ~201-202", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100fb730, "analyze_auto_tone",
          "ColorNegativePath::analyzeAutoTone -- the real 6-subsystem tone "
          "chain (cna/dra/toneHelper/contrast/ast/citras). Every subsystem "
          "individually Unicorn-verified bit-exact per docs/66; this "
          "boundary hook is for correlating a live call with the port's "
          "own real_auto_tone() on the same frame.",
          "docs/63, docs/65, docs/66, docs/74 (address repeated throughout)", 0, 1, 0, 0, 0 },

        /* ---- SBA / balance ---- */
        { "PakonIMAu.dll", 0x10100260, "sba_set_shifts",
          "ColorNegativePath::setShifts -- reads via getShifts, writes the "
          "3x int16 OUT balance-shift buffer this whole tone chain anchors "
          "to (the \"SBA neutral-balance output\" the task asks for). "
          "Re-confirmed 2026-08-15 as a genuine, independently call-reachable "
          "entry (r2 `axt` finds 3 real CALL xrefs, `af` resolves to its own "
          "address exactly) -- unlike sba_set_shifts_12 immediately below, "
          "which lives INSIDE this same function's body.",
          "tools/ansel/python-pipeline/pakon_sba_apply.py module docstring; "
          "r2 af/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x10100a37, "sba_set_shifts_12",
          "setShifts real closed-form entry for the shipped CN control "
          "words (ntdChoice,ctdChoice)=(1,2) -- PATH_SET_SHIFTS_12. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable function: "
          "`r2 -c 'aaa; axt @ 0x10100a37' PakonIMAu.dll` finds exactly ONE "
          "xref in the whole binary -- `fcn.10100260 0x101008e1 [CODE:--x] "
          "jne 0x10100a37` -- a plain conditional jump FROM WITHIN "
          "sba_set_shifts's (0x10100260) own body, zero CALL-type xrefs "
          "anywhere. Live evidence this actually corrupts data: in BOTH new "
          "2026-08-14 captures, every single time this hook fires (3 times "
          "total, tid 3020/3452 in the clean run, tid 1556 in the crashed "
          "run), the PARENT sba_set_shifts call's own shadow-stack frame is "
          "permanently orphaned right afterward -- its \"leave\" event never "
          "gets logged, and (in 2 of 3 cases) that OS thread never logs "
          "another hook event again for the rest of the capture. This "
          "engine's return-address-swap technique assumes [esp] holds a real "
          "return address at every hooked VA; reached via an internal `jne` "
          "instead of `call`, [esp] instead holds whatever real local "
          "variable/spilled register setShifts's OWN code put there, which "
          "gets overwritten with OnReturnThunk's address -- live memory "
          "corruption inside setShifts's own stack frame. DISABLED BY "
          "DEFAULT (notCallReachable) -- there is no live verification that "
          "would make hooking THIS address safe; a genuinely separate, "
          "call-reachable entry for the (1,2) closed-form path (if one is "
          "ever needed) would have to be found some other way.",
          "pakon_sba_apply.py: PATH_SET_SHIFTS_12 = 0x10100A37; "
          "live_hooks_20260814-110254.jsonl call_id 21/51 (orphaned), "
          "live_hooks_20260814-112642.jsonl call_id 20 (orphaned); "
          "r2 af/axt 2026-08-15", 0, 1, 0, 1, 0 },
        { "PakonIMAu.dll", 0x10124000, "sba_get_shifts",
          "getShifts -- copies 3x int16 from *(AnsSbaCapability+0x10)+0x3a38.",
          "pakon_sba_apply.py module docstring", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1028c780, "sba_preference",
          "Preference -- the ONLY confirmed writer of +0x3a38 (analyzePass2 "
          "@ 0x10216433 passes scene+0x3a30; fist-rounds 3x int16 into "
          "scene+0x3a38/+3a3a/+3a3c).",
          "pakon_sba_apply.py module docstring", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1019a0c0, "sba_apply_balance_shifts",
          "AnsAreaCapabilityImpl::applyBalanceShifts -- the real PER-PIXEL "
          "LUT apply (builds three 4096-entry LUTs via 0x1006c4f0, applies "
          "clamp(i+shift,0,4095) to every pixel). This is the closest real "
          "analogue of pakon_sba_apply.apply_balance_shifts() -- the "
          "pixel-buffer stage to diff, not just the scalar shifts.",
          "pakon_sba_apply.py module docstring", 0, 1, 0, 0, 0 },

        /* ---- FUGC ---- */
        { "PakonIMAu.dll", 0x100fed00, "fugc_analyze",
          "analyzeFugc -- FUGC analyze entry point in the real per-scene driver.",
          "docs/62 line ~201", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x101f82c0, "fugc_set_lut_info",
          "setLutInfo -- builds the FUGC apply LUT from ebp14 (setShifts "
          "OUT @ +0x4b6) and ebp18 (SceneContext \"dmin\" bag). Confirmed "
          "real-DLL-verified including the near-identity offsets=(0,-1,1) "
          "case, docs/74 SS10.",
          "docs/66 line ~1839; docs/74 SS10", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x101fc518, "fugc_mode_dispatch",
          "FUGC analyze / mode dispatch: Cap+0x60e8 == 2 -> metrics path, "
          "else -> setLutInfo. Address has a trailing \"...\" in its own "
          "source citation (approximate, not independently re-confirmed "
          "this pass) -- verify the exact entry live before trusting it. "
          "r2 `axt` 2026-08-15 finds ZERO xrefs of any kind (neither CALL "
          "nor CODE) -- inconclusive (consistent with an indirect/vtable "
          "call this static pass can't resolve, but does NOT positively "
          "confirm this is a real entry either) -- stays approximate/off.",
          "pakon_ansel.py comment near fugc_mode field (~line 657-658); "
          "r2 axt 2026-08-15 (inconclusive)", 1, 1, 0, 0, 0 },

        /* ---- falloff / area / attributes ---- */
        { "PakonIMAu.dll", 0x100fe960, "analyze_falloff",
          "analyzeFalloff -- per-pixel radial lens/scanner vignetting "
          "correction. The \"falloff output\" hook the task asks for.",
          "docs/62 line ~201-202; docs/74 SS11", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x10102b20, "balance_area_image",
          "balanceAreaImage -- opens with find(\"area\") idempotency guard "
          "(a HIT throws; a MISS falls through -- docs/74 SS11 already "
          "ruled out the find(\"area\") HIT path as a live data-consumption "
          "channel, but never read the miss-path body itself).",
          "docs/74 SS11", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100fd190, "analyze_scp_lut_balance",
          "ColorNegativePath::analyzeScpLutBalance -- the analyze-time "
          "path that casts to the same AnsSCPLutCapability type "
          "balanceAreaImage's miss-path composes with at apply time "
          "(docs/74 SS37/SS39). Added specifically to settle the one "
          "open question SS39 flagged: whether the [cast_result+0xc] "
          "gate controlling that whole compose block is actually "
          "non-zero on a real scan -- if this hook never fires, the "
          "SCPLut compose is dead on the real render path regardless "
          "of its data being confirmed correct.",
          "docs/74 SS37.4, SS39.2-39.3", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100e16d0, "analyze_area",
          "analyzeArea entry (732-function capability, 0% ported). docs/74 "
          "SS11-12 calls the four unreplicated stages -- this one included -- "
          "\"the sole remaining concrete software lead\" after every other "
          "mechanism was checked against the real DLL and confirmed correct.",
          "docs/74 SS11, SS12, SS\"What this changes about the open item list\" item 1", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100fb3d0, "analyze_attributes",
          "analyzeAttributes -- one of the four unreplicated stages between "
          "FUGC and autoTone, real call order per docs/74 SS11.",
          "docs/74 SS11", 0, 1, 0, 0, 0 },

        /* ---- ICC transform ---- */
        { "PakonIMAu.dll", 0x102f8420, "icc_xform_apply",
          "ImaICCXForm::apply -- builds source/dest descriptors and calls "
          "SpEvaluate @ 0x102f884c (kodakcms.dll import thunk 0x10500338). "
          "The \"ICC transform input/output\" hook the task asks for. "
          "Re-confirmed 2026-08-15: r2 `axt` finds 2 real CALL xrefs "
          "(one from `method.ImaICCEffectOp.virtual_40`, matching "
          "icc_effect_op's own citation exactly) -- a genuine, "
          "independently call-reachable entry, not the source of the "
          "2026-08-14 icc_effect_op/icc_xform_apply capture stopping "
          "mid-loop (every logged enter/leave pair for this hook across "
          "both new captures is perfectly balanced, right up to the last "
          "line before each log goes silent).",
          "docs/62 SS12.4.2; r2 af/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1016ede0, "icc_effect_op",
          "ImaICCEffectOp -- wraps apply, passes this+0x118 (source max) / "
          "this+0x120 (dest max) at 0x1016ee84-0x1016eef8. The scale "
          "(4095 vs 32767 vs Go's x65535/4095) is explicitly UNRESOLVED "
          "in docs/62 SS12.4.2 -- a live capture of this+0x118/this+0x120 "
          "settles it directly. Re-confirmed 2026-08-15: real disassembly "
          "shows an ordinary SEH prologue then `mov esi, ecx` -- a genuine "
          "__thiscall entry (this-pointer in ECX, matching esi+0x118/+0x120 "
          "used throughout the rest of the function) -- r2's own direct-call "
          "analysis finds zero xrefs here, consistent with this being "
          "reached only via indirect/vtable dispatch (the C++ method-call "
          "shape this class's own name implies), which is a static-analysis "
          "coverage gap, NOT evidence of a notCallReachable problem the way "
          "sba_set_shifts_12/icc_effect_op_ctor showed -- live capture data "
          "backs this up directly: every icc_effect_op enter/leave pair "
          "logged across both new captures is cleanly balanced, no orphaned "
          "frames, unlike the confirmed-bad hooks below.",
          "docs/62 SS12.4.2; r2 af/pdf/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1016e680, "icc_effect_op_ctor",
          "ImaICCEffectOp ctor -- the only writer found (static analysis) "
          "for this+0x118, loading the hardcoded 32767.0 from 0x1058fac0. "
          "A live hit here with a DIFFERENT value would directly disprove "
          "the \"no later setter\" assumption docs/62 flags as unconfirmed. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable function: "
          "`af @ 0x1016e680` resolves to a containing function starting at "
          "0x1016e4d0 (spanning through 0x1016ea3d), and the ONLY xref to "
          "0x1016e680 anywhere is `fcn.1016e4d0 0x1016e677 [CODE:--x] je "
          "0x1016e680` -- a conditional jump that skips a vtable/destructor "
          "call (`call dword [edx+4]`) and lands directly at 0x1016e680, "
          "which is simply the next straight-line instruction "
          "(`fld qword [0x1058fac0]` -- literally the hardcoded 32767.0 this "
          "citation already names), not any function's entry. Never actually "
          "fired in either 2026-08-14 capture (0 calls logged), so this is a "
          "latent bug, not one with direct live-corruption evidence like "
          "sba_set_shifts_12 -- but the same corruption mechanism applies the "
          "first time this code path executes. DISABLED BY DEFAULT "
          "(notCallReachable).",
          "docs/62 SS12.4.2; r2 af/axt 2026-08-15", 0, 1, 0, 1, 0 },

        /* ---- F-235 / TLA / TLB dmin-remap chain ---- */
        { "TLA.dll", 0x1003f7db, "tla_baddscene",
          "bAddScene -- the REAL writer of FUGC's \"dmin\" SceneContext bag: "
          "FindDmin on the raw PRE-balance frame words, then TLB's F-135 "
          "ColNeg poly remap, stored as \"dmin\" and read back via "
          "getCnContext. This port's own stand-in "
          "(pakon_ansel.py render_scene, `ebp18` / `raw_dmin` block) is "
          "flagged in its own comment as producing values OUTSIDE the "
          "accept band on every real frame tested -- a real, confirmed, "
          "currently-not-the-206-code-defect wiring bug worth diffing live. "
          "SUSPECT as of 2026-08-15: `af @ 0x1003f7db` against a freshly "
          "extracted TLA.dll (md5 33f7a247d79286a31b192e83d3c37425, from the "
          "same research/sdk/PAKONF135.iso every other MD5 in this table "
          "traces to) resolves to a containing function starting at "
          "0x1003f720, not 0x1003f7db itself, and the real disassembly AT "
          "0x1003f7db (`mov dx, word [ebx+0x6cac]`) is not any recognizable "
          "function prologue (no push ebp/sub esp/SEH setup) -- it reads "
          "from `ebx` as if that register was already established by an "
          "earlier prologue, i.e. it looks like a mid-function continuation, "
          "matching the SAME pattern independently confirmed for "
          "sba_set_shifts_12 and icc_effect_op_ctor below. UNLIKE those two, "
          "this was never exercised in either 2026-08-14 capture (TLA.dll "
          "never finished loading in that window -- see README \"why only "
          "17/23 hooks installed\") so there is no live corruption evidence "
          "either way, and no CALL/CODE xref was found at all (TLA.dll's "
          "in-degree count for the containing function suggests at least one "
          "caller elsewhere, not yet traced down to confirm/refute this "
          "specific sub-address). Downgraded to notCallReachable out of "
          "caution rather than left enabled on inconclusive evidence -- "
          "this project's own rule is \"if unsure, say so honestly rather "
          "than guessing,\" and this address does not currently meet the bar "
          "this pass set for the other 12 confirmed-real PakonIMAu.dll "
          "entries above (an actual CALL xref, or `af` resolving to its own "
          "address).",
          "tools/ansel/python-pipeline/pakon_ansel.py comment ~line 900-932; "
          "docs/66 golden-fleet section corroborates the surrounding TLA "
          "AddScene ColNeg leaf shape (zeroing @ 0x1003f7eb, width=4 push "
          "@ 0x1003f85d); r2 af/pd re-check 2026-08-15 (suspect, not "
          "definitively confirmed either way -- TLA.dll never loaded live)", 0, 1, 0, 1, 0 },
        { "TLA.dll", 0x100064d0, "tla_colneg_planar_scan",
          "PIColorCorrectColNegPlanarScan -- F-235 stage-2 entry, shuffles "
          "5 args into the MMX kernel's 7 at 0x1001c470. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable "
          "function: `axt @ 0x100064d0` finds exactly one xref -- "
          "`CODE XREF from fcn.10006320 @ 0x10006486` -- a jmp/jcc from "
          "within a DIFFERENT, larger function, not a call. Never fired "
          "live (TLA.dll never finished loading in either 2026-08-14 "
          "capture). DISABLED BY DEFAULT (notCallReachable), same reasoning "
          "as sba_set_shifts_12/icc_effect_op_ctor above.",
          "docs/65 line ~93; docs/66 golden-fleet section; "
          "r2 af/axt 2026-08-15", 0, 1, 0, 1, 0 },
        { "TLA.dll", 0x1001c470, "tla_colneg_mmx_kernel",
          "The inner MMX kernel itself (pmulhw x3, independently-truncated "
          "products, THEN summed -- the exact bug docs/66's \"golden "
          "fleet\" section fixed on the port side, one code high). NOTE: "
          "if this fires per-scanline/per-pixel-block rather than once per "
          "frame, it may be high-frequency live -- see hooks.cfg to "
          "disable if a first run shows it's too hot. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable "
          "function: `af @ 0x1001c470` resolves to a containing function "
          "spanning 0x1001b160-0x1001dec6 (11622 bytes) -- 0x1001c470 is "
          "deep inside that function's body, not its own entry. Never "
          "fired live (TLA.dll never finished loading in either 2026-08-14 "
          "capture). DISABLED BY DEFAULT (notCallReachable) -- this also "
          "retires the earlier \"may be high-frequency, disable via "
          "hooks.cfg if needed\" concern moot: it's off by default now for "
          "a stronger reason than heat.",
          "docs/66 \"6.2 -- golden fleet, colneg_1px remap TLA\"; "
          "r2 af 2026-08-15", 0, 1, 0, 1, 0 },

        { "TLB.dll", 0x10034b9b, "tlb_f135_poly_remap",
          "F-135 ColNeg polynomial remap used by bAddScene to turn the raw "
          "FindDmin walk into \"dmin\". NOTE: this port's own comment cites "
          "it as \"TLB.dll fcn.1000d880 @ 0x10034b9b\" -- an r2 auto-name/VA "
          "pair that looks inconsistent (fcn.<addr> normally names a "
          "function BY its own entry address) with docs/65's separate "
          "citation of \"TLB.dll:fcn.1000d880\" for the general stage-2 3x10 "
          "polynomial (PolyPixel). Both addresses are hooked (this one and "
          "tlb_polypixel) precisely so a live capture can resolve which is "
          "which rather than guessing. RESOLVED 2026-08-15, statically, no "
          "live capture needed: 0x10034b9b is not a function at all -- it "
          "is the literal byte address of the `call fcn.1000d880` opcode "
          "(`e8 e0 8c fd ff`) inside a DIFFERENT function, fcn.10034a60 "
          "(`mov ecx, dword [0x10075554]; push edx; add ecx, 0x16f4; call "
          "fcn.1000d880` at exactly 0x10034b9b; `test eax,eax; jne "
          "0x10034bc4` immediately after). This fully resolves the naming "
          "ambiguity this hook existed to settle: `tlb_polypixel` "
          "(0x1000d880) is the one and only real PolyPixel function; "
          "0x10034b9b is simply a CALL SITE that invokes it. This is worse "
          "than the other notCallReachable entries in this table -- hooking "
          "it would plant a JMP over live CALL-instruction bytes inside "
          "fcn.10034a60, silently rewriting that function's own control "
          "flow the moment MinHook installs the hook, independent of "
          "whether the hook ever even fires. `approximate` is kept set "
          "(it really was never independently re-confirmed, and now we know "
          "definitively why it never should be) alongside the new "
          "notCallReachable=1 for a complete, honest record of both how "
          "this was originally flagged and what was actually found.",
          "pakon_ansel.py comment ~line 903-904; r2 af/pd/axt 2026-08-15 "
          "(definitively resolved: this VA is a call-instruction's own "
          "address, not a function)", 1, 1, 0, 1, 0 },
        { "TLB.dll", 0x1000d880, "tlb_polypixel",
          "PolyPixel -- general stage-2 3x10 quadratic polynomial. Address "
          "confirmed (not just implied) by a real af+pdf disassembly, "
          "docs/74 SS32.2: 845 bytes, switch-dispatched on filmClass "
          "(case 2 -> this+0xc8 PosMatrix, matching check_film_class's own "
          "citation exactly), a tight fild/fmul/faddp per-pixel loop over "
          "10 stored coefficients per channel, zero fyl2x/log-family FPU "
          "instructions anywhere in the function. That same pass also "
          "resolved the naming ambiguity this hook (and tlb_f135_poly_remap "
          "above) originally existed to settle live -- both addresses are "
          "PolyPixel-family, statically, with no live capture needed. "
          "RE-ENABLED 2026-08-16 (hotPathDisabled was 1) with a real "
          "live-data question restored: the v8 area_image_apply_lut "
          "capture now yields the vendor's actual RPD12, but there is no "
          "matching raw capture to fit ROM12 -> RPD12 against, so this "
          "hook's own g_extraDumps[] row (poly_input_r) captures the raw "
          "14-bit R plane PolyPixel reads (stack_dwords[1] = buffer base "
          "at call site fcn.10026c90 @ 0x100270a5; planar, in-place). "
          "Entry-only (wantExitDefault=0) because the per-pixel loop "
          "(iterates up to 512 word-pixels per call, 0x1000d8f2-0x1000dab0) "
          "makes exit-hooking this a demonstrated hot path; the entry "
          "buffer dump is what the analysis needs. If per-scanline call "
          "volume turns out too large for a full roll, reduce the "
          "poly_input_r numBytes in g_extraDumps[] (only the first call's "
          "entry dump is pure pre-poly raw anyway -- later calls are "
          "in-place-contaminated). The prologue itself was checked directly "
          "and is NOT the concern: `push -1; push <SEH handler>; mov "
          "eax,fs:[0]; push eax; mov fs:[0],esp; sub esp,0x48` is an "
          "entirely ordinary MSVC/SEH prologue, a standard, safe MinHook "
          "trampoline target.",
          "docs/74 SS32.2-32.3, SS32.7", 0, 0, 0, 0, 0 },

        /* ---- AFE (device-side register write) ---- */
        { "TLB.dll", 0x100299c0, "tlb_afe_offset_write",
          "FN_bDrvPutCcdAtoDOffsets -- AD9826 offset register encoder "
          "(9-bit sign-magnitude; this port had a two's-complement bug "
          "here, fixed 2026-08-12, docs/72). This is the closest REAL, "
          "documented \"AFE\" hook available. NOTE: this is the OFFSET "
          "write, not GAIN -- no distinct address for a gain-register "
          "write function was found documented anywhere in docs/62-74. "
          "See README.md \"AFE gain -- honestly unresolved\". Re-confirmed "
          "2026-08-15: r2 `axt` finds 5 real CALL xrefs from 4 different "
          "functions -- a genuine, independently call-reachable entry, "
          "matching the clean/balanced enter+leave pairs this hook logged "
          "throughout both new 2026-08-14 captures.",
          "docs/72 SS1.3 (\"FN_bDrvPutCcdAtoDOffsets at 0x100299c0, "
          "[VERIFIED-FROM-BINARY]\"); r2 af/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },

        /* ---- Area image per-pixel LUT apply (docs/74 SS46) ---- */
        { "PakonIMAu.dll", 0x100d9340, "area_image_apply_lut",
          "AnsImageData::applyLut -- self-named by 4 embedded strings in "
          "its own body (\"AnsImageData::applyLut\" @ 0x10584320, "
          "\"Images must have 3 bands.\" @ 0x10584338, \"Source and "
          "destination have different packing.\" @ 0x105842f0, \"Source "
          "and destination are different sizes.\" @ 0x105842c4; path "
          "\"\\Atc\\ansel\\src\\libStub.ansel\\AnsImageData.cpp\" @ "
          "0x10584274) -- THE genuine per-pixel write this doc's own "
          "priority list (docs/74 SS27.4/SS37.7/SS45) had been missing: "
          "a real nested width/height-bounded loop (outer row loop "
          "0x100d97f0-0x100d98be, inner column loop 0x100d9822-0x100d986b, "
          "both `dec reg; jne`-terminated against edi->+0xc/+0x10, the "
          "same width/height offsets pakon_fugc.FUGC_IMG_DESC_WIDTH_OFF/"
          "HEIGHT_OFF already document for this same AnsImageData-shaped "
          "descriptor layout) doing, per pixel per row: `movsx "
          "ebx,word[src+idx]; mov bx,word[lutBase+ebx*2]; mov "
          "word[dst+idx2],bx` for R, G, and B against three SEPARATE "
          "caller-supplied 4096-entry LUTs (0x100d9822/0x100d9837/"
          "0x100d9846) -- a genuine `[base+index*stride]`-shaped indexed "
          "LUT lookup AND indexed pixel write inside an image-bounded "
          "loop, not a struct-field or capability-object write (the "
          "shape every other function read in this neighbourhood turned "
          "out to have -- AnsFugcCapabilityImpl::applyLut/0x101fa5b0 in "
          "SS28 had zero indexed writes in 705 instructions; "
          "analyzeScpLutBalance/0x100fd190 in SS40 never wrote its own "
          "flag byte at all). Called (E8 exhaustive .text scan, this "
          "pass, 10 real static callers total) 4x from balanceAreaImage "
          "(0x10103561/0x1010386a/0x101038f7/0x10103965, ALL on the "
          "AREA capability's own real \"AREA analysis image\" object -- "
          "the exact this+0x1a4 field SS27.3 already read via "
          "fcn.100dc060, confirmed here to be var_34h at each of these "
          "4 call sites, with LUT triples from the shift+SCPLut-composed "
          "buffer SS37.4/SS38-40 already traced), once from "
          "sba_apply_balance_shifts/0x1019a274 (currently gated off per "
          "SS37.3, 0/12 real fires), once from analyzePostBalance "
          "(0x100fdc40, per docs/62 SS2.5's own citation of the scene "
          "order \"analyzePostBalance 0x100fdc40 -> analyzeFugc -> "
          "balanceAreaImage\"), and 3x from AnsDcPremiumPath's own "
          "vtable method_12 (0x1006fa90 range -- the CN-Premium path, "
          "not this doc's own CN-Enhanced negative path per docs/64). "
          "Independently corroborated by THREE pre-existing docs this "
          "investigation had not cross-referenced before this pass: "
          "docs/62 SS2.5 (\"balanceAreaImage composes filmLut_c . "
          "scpLut_c . shift_c . fugc_c and applies it through "
          "AnsImageData::applyLut 0x100d9340\"), docs/64 (\"They compose "
          "into the pixel buffer in balanceAreaImage\"), and "
          "docs/reports/autotone-scope-2026-08-10/{fugc,filmLut}.md "
          "(\"applied to image pixels via AnsImageData::applyLut "
          "0x100d9340 -- genuine per-channel density math\"). The "
          "STILL-open question those same earlier docs flag and this "
          "pass does not resolve (docs/58 SS16.5 as quoted in docs/62 "
          "SS2.5): whether this \"AREA analysis image\" aliases the "
          "shared scene buffer cna/dra actually read, or is a private "
          "analysis-only copy -- exactly what this live hook is for. "
          "approximate=0: afij (1,505 realsz/473 ninstrs/106 nbbs, "
          "single real exit ebbs=1, minaddr/maxaddr span matches the "
          "full af+pdf read exactly) plus this section's own E8 scan "
          "(10 real CALL xrefs, not a guess) both independently confirm "
          "a genuine, independently call-reachable function entry, the "
          "same standard SS37.2/SS39.2/SS40 already established. "
          "wantExitDefault=1, hotPathDisabled=0: called a small, bounded "
          "number of times PER FRAME externally (<=4 from "
          "balanceAreaImage, <=1 each from the other real call sites) "
          "-- its own internal per-pixel loop is opaque to the external "
          "call count, unlike tlb_polypixel (called roughly every 15-45 "
          "ticks, i.e. externally once per scanline-batch) -- so full "
          "entry+exit tracing at this call frequency is not the "
          "high-volume hot-path risk hotPathDisabled exists for.",
          "docs/74 SS46; docs/62 SS2.5; docs/64; docs/58 SS16.5 (quoted "
          "in docs/62); docs/reports/autotone-scope-2026-08-10/"
          "{fugc,filmLut}.md", 0, 1, 0, 0, 0 },

        /* ---- Lamp / AFE-gain / CCD-acquire-control (docs/74 SS49) ----
         * Three new TLB.dll entries covering the real lamp warm-up + CCD
         * dark-offset-calibration bring-up sequence docs/55 and docs/59
         * captured on the wire, extending the existing tlb_afe_offset_write
         * hook above (which only covers the AFE OFFSET register write) to
         * the other two real, independently call-reachable driver
         * functions in that same sequence. All three re-derived and
         * confirmed fresh this pass against the hash-verified TLB.dll
         * (md5 193d9b2ce0a4b77ae9b78262bd06c0fc, same file every other
         * TLB.dll citation in this table traces to, extracted from
         * research/sdk/PAKONF135.iso and independently re-hashed this
         * pass) via `r2 -e bin.baddr=0x10000000 -c 'aaa; af @ <va>; axt @
         * <va>; pdf @ <va>'` -- not carried over from agent.js (agent.js
         * gained the same three entries, appended, in this same pass). */
        { "TLB.dll", 0x1002c5f0, "tlb_lamp_on",
          "FN_bDrvLampOn -- the real lamp enable+duty-write function: one "
          "call writes light-board reg 0x80 (enable mask), 0x81 (5-byte "
          "LED levels [B,Ir,R,0,G]) and 0x82 (12-byte PWM on-count sextet "
          "+ period N), matching docs/59's captured steps 16-18/80-82/100/"
          "114 and docs/40 SS3/SS12's own static derivation of this exact "
          "address (`FN_bDrvLampOn = fcn.1002c5f0`). Re-confirmed fresh "
          "this pass, independent of docs/40's citation: `af @ 0x1002c5f0` "
          "resolves to itself (minaddr==maxaddr-2175==0x1002c5f0, "
          "num-instrs=656), `axt` finds 8 genuine CALL-type xrefs from 6 "
          "distinct caller functions (0x1001e7b0 x3, 0x1001ec90, "
          "0x10020dc0, 0x1002d5c0, 0x1002d7f0 -- FN_bBeforeScan per docs/59's "
          "own header note, 0x1002dbd0), zero CODE-type/internal-jump "
          "xrefs -- the same axt-based safety check that found the 5 "
          "notCallReachable entries above finds nothing wrong here. "
          "Prologue is an entirely ordinary MSVC frame: `push ebp; mov "
          "ebp,esp; and esp,0xfffffff8; sub esp,0x54` (stack realignment "
          "for the function's own FPU/double-precision locals, per the "
          "immediately-following `fld qword [0x10067008]` -- no relative "
          "jump/call anywhere near the bytes MinHook needs to relocate). "
          "This hook observes the SAME register writes docs/59's "
          "`tools/lamp_replay_vendor.py` sends deliberately from the host "
          "side -- it does not send anything itself, only logs entry/exit "
          "when PSI's own code calls this function during a real scan.",
          "docs/40 SS3 (\"FN_bDrvLampOn = fcn.1002c5f0\"), SS12 (write-order "
          "correction: 0x80 first, then 0x81, then 0x82); docs/59 (captured "
          "wire sequence this function produces); fresh r2 af/axt/pdf "
          "2026-08-15 against TLB.dll md5 193d9b2ce0a4b77ae9b78262bd06c0fc",
          0, 1, 0, 0, 0 },
        { "TLB.dll", 0x100298b0, "tlb_afe_gain_write",
          "The AFE GAIN register write function -- the address README.md's "
          "\"AFE gain -- honestly unresolved\" section asked for, found "
          "this pass. Self-naming string \"FN_bDrvPutCcdAtoDGains\" exists "
          "in this exact binary at 0x10063b4c (found via `izz~AtoD`, "
          "alongside \"FN_bDrvPutCcdAtoDOffsets\" at 0x10063b18 -- the "
          "already-hooked tlb_afe_offset_write's own name), confirming the "
          "vendor's own FN_bDrv... naming convention includes this "
          "function; the string itself is referenced only from the shared "
          "name-lookup/logging dispatcher (fcn.100170b0, a big "
          "switch-on-command-id table that also references "
          "\"FN_bDrvLampOn\"'s and \"FN_bDrvCcdAcquireControl\"'s own name "
          "strings the same indirect way), NOT from inside 0x100298b0's "
          "own body -- so the name<->address link here is by STRUCTURAL "
          "match, not a literal in-body self-reference, same standard "
          "already used to identify tlb_afe_offset_write in the first "
          "place. That structural match is exact: 0x100298b0 sits "
          "immediately before tlb_afe_offset_write (0x100299c0) in .text, "
          "same shape (in-degree 8, cyclomatic-complexity 13 vs the "
          "offset function's 19), and writes CCD board reg 0x84 with "
          "indices 2, 3, 4 (`push 2/push 0x84`, `push 3/push 0x84`, "
          "`push 4/push 0x84`, each followed by a call to the same "
          "cache-check helper fcn.1000a5d0 then the same PutRegisterWord "
          "primitive fcn.1001acd0 the offset function also calls) -- "
          "exactly docs/55's captured steps 19-21 (`0x44 0x84 idx 2/3/4 "
          "= gain R/G/B`, all value 0x000D=13), as opposed to the offset "
          "function's idx 5/6/7. `axt` finds 8 genuine CALL-type xrefs "
          "from 8 real call sites (0x1001e242, 0x1001ff3b, 0x1001ffaf, "
          "0x100208f9, 0x10020fd0, 0x1002120a, 0x100213a9, 0x1002df92), "
          "the same call-reachability bar tlb_afe_offset_write meets. "
          "Prologue: `push ebx; mov ebx,[esp+8]` -- exactly 5 bytes, no "
          "relative jump/call, a clean MinHook target.",
          "README.md \"AFE gain -- honestly unresolved\" (the search "
          "strategy this hook is the result of); docs/55 steps 19-21 "
          "(captured 0x44/0x84 idx2/3/4 gain writes this function "
          "produces); fresh r2 izz/af/axt/pdf 2026-08-15 against TLB.dll "
          "md5 193d9b2ce0a4b77ae9b78262bd06c0fc",
          0, 1, 0, 0, 0 },
        { "TLB.dll", 0x1002c340, "tlb_ccd_acquire_control",
          "The CCD acquire-on/off toggle function docs/40 SS11 names "
          "\"FN_bDrvCcdAcquireControl\" (\"sets bit 0 of CCD register "
          "0x82\"), matching docs/55's captured steps 2/18/35/40/43 (board "
          "0x44 reg 0x82 idx 0: mask 0x0060 vs acquire-on 0x0061). LOWER "
          "CONFIDENCE ON THE NAME SPECIFICALLY than the other two new "
          "entries above: the self-naming string \"FN_bDrvCcdAcquireControl\" "
          "(0x10064220, found via the same `izz~bDrv` scan) is, like the "
          "other FN_bDrv* strings, referenced only from the shared "
          "name-lookup dispatcher fcn.100170b0 -- never from inside "
          "0x1002c340's own body -- so this address is identified by "
          "BEHAVIOR AND POSITION, not a direct citation: it validates "
          "exactly the CCD acquisition-window parameters this role "
          "implies (four embedded assert-message strings at 0x10066f38, "
          "0x10066efc, 0x10066e58, 0x10066e08, 0x10066ddc name "
          "`uiCcdPixelHeight`, `uiCcdPixelOffset`, `uiCalibrationOffset`, "
          "`uiCcdIntegrationTime` by name), then calls "
          "fcn.10029770 -- a small (149-byte, in-degree 4, real CALL "
          "xrefs only) shared primitive that merges a caller-supplied "
          "value into a cached word at [this+0x358] and writes it to reg "
          "0x82 idx 0 via the same fcn.1001acd0 PutRegisterWord primitive "
          "the gain/offset functions use -- TWICE, at 0x1002c4c3 and "
          "0x1002c518, consistent with one call setting the mask "
          "(0x0060-shaped base) and a later one toggling the acquire bit "
          "(0x0061). This function's own address range (0x1002c340-"
          "0x1002c5f0) ends EXACTLY where tlb_lamp_on/FN_bDrvLampOn "
          "begins -- the two are adjacent in the same translation unit, "
          "consistent with docs/40's own description of these as "
          "sibling FN_bDrv... driver functions. `axt` finds 8 genuine "
          "CALL-type xrefs from 6 distinct callers (0x1001fe10 x3, "
          "0x10020590, 0x10020dc0 x2, 0x1002d5c0, 0x1002dbd0 -- three of "
          "which, 0x1001fe10/0x10020dc0/0x1002dbd0, are also callers of "
          "tlb_lamp_on, i.e. the real driver dispatch layer calls both "
          "from the same handful of higher-level functions), zero "
          "CODE-type xrefs. Prologue: `push ecx; mov eax,[esp+0x1c]` -- "
          "exactly 5 bytes, no relative jump/call, a clean MinHook "
          "target. This is a real, confirmed, independently "
          "call-reachable entry by every mechanical test this project's "
          "own axt-based safety check applies -- flagged as "
          "behavior-inferred rather than address-cited only so a future "
          "reader knows the difference from tlb_lamp_on's docs/40-cited "
          "address above.",
           "docs/40 SS11 (\"FN_bDrvCcdAcquireControl sets bit 0 of CCD "
           "register 0x82\"); docs/55 steps 2/18/35/40/43 (captured "
           "0x44/0x82 idx0 mask/acquire writes this function produces); "
           "fresh r2 izz/af/axt/pdf 2026-08-15 against TLB.dll md5 "
           "193d9b2ce0a4b77ae9b78262bd06c0fc",
           0, 1, 0, 0, 0 },

        /* ---- AnsColorAdjustCapability density-adjust shift (docs/74 SS57) ---- */
        { "PakonIMAu.dll", 0x101b76d0, "color_adjust_shift",
          "The analyzePostBalance shift leaf (fcn.101b76d0, 282 B) -- "
          "computes the three int16 post-balance shifts as "
          "out_c = round((in_c - mean(in)) * M_c + S1*S2 + dmin_c), "
          "Unicorn-verified bit-exact (pakon_postbalance_golden.py). "
          "thiscall: ecx = AnsColorAdjustCapabilityImpl (the Impl at "
          "Cap+0x10); the Impl fields are M/S1/S2/dens/dmin at +0xc..+0x30 "
          "(M and S1 are ctor args defaulting 25/25/25/75; dens/S2/dmin are "
          "zeroed at construction -- their non-zero writer is the still-open "
          "question this hook exists to answer). Prologue "
          "`push ecx; push esi; mov esi,ecx` (5 B, no rel jmp/call) is a "
          "clean MinHook target; reached via two real CALL sites "
          "(fcn.100f13a0 @ 0x100f13c1, and fcn.101b7e90 @ 0x101b80ad), "
          "so notCallReachable=0. Entry-only (wantExitDefault=0): the OUT "
          "shifts are already covered by the verified formula; the unknown "
          "is the Impl field VALUES, captured by the impl_fields extra dump.",
          "docs/74 SS57; tools/ansel/python-pipeline/"
          "pakon_postbalance_golden.py", 0, 0, 0, 0, 0 },

        /* ---- Per-frame orderFpo candidate (docs/74 SS66/SS72, v21) ---- */
        { "PakonIMAu.dll", 0x1028b8d0, "sba_order_fpo_calc",
          "The function SS66 named as the per-frame orderFpo (scene+0x38a2) "
          "writer -- 2958 B, 13 cdecl args (callers clean up add esp,0x34), "
          "8 helper subroutines, called 5x per frame. SS72's full-body read "
          "found its own TOP-LEVEL code does NOT write the orderFpo Y/U/V "
          "triple (pref_data+0x0/+0x2/+0x4) on the case that provably fires "
          "live (switch selector arg 3 == 0 at both real call sites): it "
          "writes exactly ONE unrelated word at pref_data+0x3e, derived from "
          "two other already-present pref_data fields. Whether one of the 8 "
          "unread helpers is the real orderFpo writer -- with pref_data "
          "threaded in as a hidden argument -- is exactly what this hook "
          "exists to settle empirically. "
          "SAFETY (audited 2026-08-17, the same af+axt pass this table's own "
          "header describes): `axt` finds FIVE real CALL-type xrefs "
          "(fcn.102159c0 @ 0x10215d6a/0x10215fae/0x1021605b = "
          "AnsSbaCapabilityImpl::analyzePass2, and fcn.10218110 @ "
          "0x1021937b/0x102196a9) and ZERO CODE-type jmp/jcc entries, and "
          "`af` resolves to 0x1028b8d0 itself (its own entry, not a "
          "containing function) -- so the engine's return-address-swap "
          "precondition genuinely holds here, unlike the notCallReachable "
          "entries above. Prologue `mov eax,[esp+0xc]` (4 B) + "
          "`sub esp,0x2c0` (6 B) is position-independent with no rel32 "
          "jmp/call in the first 5 bytes, so it is a clean MinHook "
          "relocation target. notCallReachable=0, entry-only "
          "(wantExitDefault=0): the before/after question SS72.7 poses is "
          "answered by consecutive ENTRY dumps (see g_extraDumps below), so "
          "no exit hook is needed and none is taken.",
          "docs/74 SS66, SS72 (esp. SS72.2 arg table, SS72.3 case-0 read, "
          "SS72.7 capture spec); r2 af/axt safety audit 2026-08-17", 0, 0, 0, 0, 0 },

        /* ---- orderFpo chroma helper (docs/74 SS76, v24) ---- */
        { "PakonIMAu.dll", 0x1028ae00, "sba_order_fpo_helper",
          "fcn.1028ae00 (1897 B, 15 cdecl args) -- the helper 0x1028b8d0 "
          "calls at 0x1028c023 to compute the chroma residual that becomes "
          "the orderFpo U/V terms. SS76 derived the U/V arithmetic in full "
          "(a weighted mean over 864 dens samples, 50x83 int8 weight table, "
          "round-half-away-from-zero divide) and needs no emulation of it -- "
          "but could NOT statically derive the Y term, an int32 read from a "
          "stack slot (L[-0x200]) that nothing in 0x1028b8d0's own 912 "
          "instructions ever writes. SS76 traced it to this function's own "
          "arg 9. Hooking here captures that dword directly: the engine "
          "already logs the first 16 raw stack dwords on every entry, and "
          "this function's 15 args all fall inside that window, so arg 9 is "
          "captured with NO extra dump row at all -- and the same line "
          "cross-checks SS76's whole 15-arg reconstruction for free. "
          "SAFETY (r2 af+axt 2026-08-17, this table's own standard): exactly "
          "ONE real CALL-type xref (fcn.1028b8d0 @ 0x1028c023) and zero "
          "CODE-type jmp/jcc entries; `af` resolves to 0x1028ae00 itself, "
          "its own entry, not a containing function. Prologue "
          "`sub esp,0x5c` (3 B) + `movsx eax, word [esp+0x70]` (5 B) is "
          "position-independent with no rel32 in the first 5 bytes -- a "
          "clean MinHook relocation target. Entry-only (wantExitDefault=0): "
          "the wanted value is an INPUT argument, so the return adds "
          "nothing.",
          "docs/74 SS76 (U/V derivation, and Y's L[-0x200] traced to this "
          "function's arg 9); r2 af/axt safety audit 2026-08-17", 0, 0, 0, 0, 0 },

        /* ---- the bytecode interpreter (docs/74 SS78.2/SS86, v26) ---- */
        { "PakonIMAu.dll", 0x102aadf0, "sba_vm_interp",
          "fcn.102aadf0 (4423 B) -- the BYTECODE INTERPRETER SS78.2 found "
          "standing between a captured Y term and a computable one. Program "
          "pointer at [arg2+4], 16-bit opcodes, 0xff halt, two-stage dispatch "
          "(movzx from the 254-byte index table at 0x102ac018, then jmp "
          "through the table at 0x102abf4c). Static scoping (SS86): 254 "
          "opcodes collapse to 51 handler indices, and index 50 alone covers "
          "203 opcodes (the default/invalid case) -- so there are 50 real "
          "handlers, not 254. "
          "WHY THIS CAPTURE: dumping the PROGRAM rather than logging each "
          "dispatch answers both open questions offline and costs one dump "
          "per call instead of thousands of log lines. Comparing the program "
          "bytes across frames and across scans settles static-vs-generated; "
          "walking those bytes against the index table gives the exact set of "
          "opcodes this path actually uses, which is the number that decides "
          "whether porting the VM is a bounded job. "
          "SAFETY (r2 af+axt 2026-08-17, this table's own standard): exactly "
          "ONE real CALL-type xref (fcn.102ac140 @ 0x102ac15a), zero "
          "CODE-type jmp/jcc entries, and `af` resolves to 0x102aadf0 itself. "
          "Prologue `sub esp,0x2c` (3 B) + `push ebx` (1 B) + `push ebp` "
          "(1 B) is exactly 5 position-independent bytes with no rel32 -- a "
          "clean MinHook relocation target. Entry-only (wantExitDefault=0): "
          "the program and its context are inputs, so the return adds "
          "nothing. NOT hot-path disabled, but note this fires per "
          "interpreted run, not per pixel.",
          "docs/74 SS78.2 (interpreter identified), SS86 (static scoping: 50 "
          "real handlers); r2 af/axt safety audit 2026-08-17", 0, 0, 0, 0, 0 },
    };

    int i;
    eng->count = HOOKCORE_MAX_HOOKS;
    for (i = 0; i < HOOKCORE_MAX_HOOKS; i++) {
        eng->defs[i] = table[i];
        eng->defs[i].entryThunk = thunks[i];
    }
}

/* ---------------------------------------------------------------------
 * g_extraDumps[] -- docs/74 SS47's own re-derived calling convention for
 * area_image_apply_lut (0x100d9340), from a fresh af+pdf this pass (not
 * reused from SS46's transcription, which SS47.1 found had dropped a real
 * `push edi` instruction at the first balanceAreaImage call site). Stack
 * layout at entry, confirmed against BOTH the caller-side push order AND
 * the callee-side [esp+N] reads independently, and cross-checked live
 * (ecx == stack_dwords[4] on all 18 real captured calls, docs/74 SS47.2):
 *
 *   stack_dwords[0] = &status   (caller-owned out-param, NOT a buffer)
 *   stack_dwords[1] = R-band LUT pointer (4096 x int16 = 8192 bytes)
 *   stack_dwords[2] = G-band LUT pointer (= R + 0x2000 in every real
 *                      capture from balanceAreaImage's own compose chain,
 *                      but NOT assumed here -- read via its own pointer)
 *   stack_dwords[3] = B-band LUT pointer (= R + 0x4000, same caveat)
 *   stack_dwords[4] = dup-this: the SAME AnsImageData* as `this`/ecx
 *
 * Pixel-buffer dump: `this->0x20` is the AnsImageData pixel-data
 * base-pointer field. Originally SS47.1's own inference (traced via the
 * "if width/height/bands > 0: eax = [edi+0x20]; cache it for the loop"
 * block at 0x100d9650-0x100d9664); re-confirmed 2026-08-16 by a fresh
 * af+pdf of 0x100d9340 -- 0x100d9661 `mov eax,[edi+0x20]` is the real
 * per-pixel-loop source base, and the band-pointer arithmetic at
 * 0x100d967f-0x100d9708 shows the packing==0 layout is INTERLEAVED
 * 16-bit RGB (band 0 at base+0, band 1 at base+2, band 2 at base+4),
 * with width at this->0xc, height at this->0x10, bands at this->0x14,
 * packing at this->0x4, row stride at this->0x1c. Bumped from SS47's
 * 256-byte preview to the full 8192-byte row cap specifically so a
 * capture carries enough real RPD12 pixel values (4096 int16 = ~1365
 * interleaved RGB pixels) to fit the F-135 inversion curve
 * (ROM12 -> RPD12) against this port's own PolyPixel output on the same
 * frame -- the one unverified stage behind the washed-out defect
 * (docs/74 SS8/SS32/SS51/SS54). Still bounded at
 * HOOKCORE_EXTRA_DUMP_MAX_BYTES, and still IsBadReadPtr-guarded, so
 * this stays a per-CALL (not per-pixel) cost on the real box.
 */
/* ---------------------------------------------------------------------
 * tlb_polypixel (0x1000d880) extra dump -- captures the raw 14-bit R
 * plane the F-135 PolyPixel reads, so the inversion curve (ROM12 -> RPD12)
 * can be fit point-for-point against the area_image_apply_lut pixel_data
 * capture on the SAME frame.
 *
 * Calling convention (fresh af+pdf 2026-08-16, call site fcn.10026c90 @
 * 0x100270a5): `push eax; push esi; push edi; call fcn.1000d880`, i.e. at
 * entry stack_dwords[0]=edi, stack_dwords[1]=esi (= buffer base),
 * stack_dwords[2]=eax (filmClass). The buffer is PLANAR int16:
 * R at base, G at base + w*h*2, B at base + w*h*4, where w=stack_dwords[3]
 * and h=stack_dwords[4] (PolyPixel's own `imul eax,[esp+0x68],[esp+0x6c]`
 * then `lea ebx,[edx+eax*2]`/`lea ebp,[edx+eax*4]` at
 * 0x1000d8ce-0x1000d8e3). Confirmed live (v10, docs/74 SS59): the frame is
 * 245x367 (w=0xf5, h=0x16f), NOT 2000 px wide as this comment previously
 * guessed. PolyPixel is in-place, so at ENTRY the dump is the raw 14-bit
 * (pre-poly) plane; the port computes ROM12 = PolyPixel(raw) bit-exact.
 * First 8192 bytes of each plane = first 4096 pixels (~16.7 scanlines at
 * w=245). v12/v13 (docs/74 SS60) bumps poly_input_r to 0x84000 bytes
 * (540672 = the page-rounded committed frame size; 245x367x3 planes x2 =
 * 539490 = 0x83B62, R+G+B contiguous, since the planes are back-to-back at
 * w*h*2/4), so the whole frame is carried in ONE dump -- this is what
 * makes the raw<->RPD12 spatial relayout solvable by 2D cross-correlation
 * (the truncated tops of the two differently-laid-out buffers did not
 * overlap). poly_input_g/b are dropped (redundant with the full dump).
 * 0x90000 was tried first and came back IsBadReadPtr-failed on every row
 * (the inter-buffer stride is larger than the committed region), so 0x84000
 * is the read-safe ceiling. Bounded/IsBadReadPtr-guarded.
 *
 * area_image_apply_lut (0x100d9340) img_desc dump: 0x24 bytes of the
 * AnsImageData descriptor at this->0x0 -- packing@0x4, width@0xc,
 * height@0x10, bands@0x14, row stride@0x1c -- so the RPD12 pixel_data
 * layout (interleaved vs planar, stride) is read straight off the object
 * instead of guessed from the buffer stride.
 */
/*
 * color_adjust_shift (0x101b76d0) extra dump -- captures the raw
 * AnsColorAdjustCapabilityImpl field region so the still-open question
 * docs/74 SS57.5 flags (which code writes the non-zero dens/S2/dmin) can
 * be settled from live values instead of the noise-swamped static search.
 *
 * __thiscall: ecx = Impl. Field layout (verified, docs/74 SS57.2):
 *   +0x0c/+0x10/+0x14   M (3 x float)
 *   +0x18               S1 (float)
 *   +0x1c/+0x20/+0x24   dens a,b,c (3 x float)
 *   +0x28               S2 (float)
 *   +0x2c/+0x2e/+0x30   dmin (3 x int16)
 *
 * Dump 0x28 bytes from Impl+0x0c (M..dmin inclusive, 38 bytes + 2 pad) --
 * raw hex, so the floats/int16s parse offline against the already-ported
 * orderFpo/fosDmin. EXTRA_DUMP_THIS_OFFSET reads regs->ecx, so stackIndex
 * is ignored (0). 40 bytes per call, IsBadReadPtr-guarded like the rest.
 */
/*
 * sba_get_shifts (0x10124000) extra dump -- captures the 3 int16 that
 * getShifts copies out of *(AnsSbaCapability+0x10)+0x3a38 (the SBA Impl's
 * shift words) into its out buffer, so the per-frame +0x3a38 values the
 * balance actually reads can be read DIRECTLY instead of recovered by
 * inverting setshifts_12 (docs/74 SS62). __thiscall: ecx = AnsSbaCapability;
 * EXTRA_DUMP_THIS_DEREF_OFFSET reads *(ecx + 0x10) + 0x3a38 (6 bytes = 3
 * int16). This settles SS62.3's open contradiction -- whether +0x3a38 is
 * written per-frame by a second writer (it varies) or is constant (it
 * doesn't) -- and lets the per-frame values be correlated against the FOS
 * orderFpo/fosDmin the port already computes.
 */
/*
 * sba_preference (0x1028c780) extra dumps -- capture the Preference's own
 * INPUTS to find the source of the per-frame uniform luma offset Delta that
 * SS62.5 found is added to setshifts_12(+0x3a38) in the applied balance
 * shift. Calling convention (SS62): arg1 = scene+0x38a2 (preference data the
 * hi=0/hi=0x30 U/V-aim fields live in), arg2 = FOS (null live), arg3 =
 * scene+0x3a30 (shift out), arg4 = blob (the nested-fpo copy), arg5 = mode.
 * So pref_data dumps the per-frame preference words (orderFpo/fpo) and blob
 * dumps the nested-fpo struct -- enough to see whether the Delta tracks the
 * FOS orderFpo luma or the DPI constant.
 */
const ExtraDumpSpec g_extraDumps[] = {
    { "area_image_apply_lut", "r_lut", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 8192 },
    { "area_image_apply_lut", "g_lut", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 8192 },
    { "area_image_apply_lut", "b_lut", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 8192 },
    { "area_image_apply_lut", "img_desc", EXTRA_DUMP_THIS_OFFSET, 0, 0x0, 0, 0x24 },
    { "area_image_apply_lut", "pixel_data", EXTRA_DUMP_DEREF_PTR, 4, 0x20, 0, 0x80000 },
    { "tlb_polypixel", "poly_input_r", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x84000 },
    { "sba_get_shifts", "shifts_3a38", EXTRA_DUMP_THIS_DEREF_OFFSET, 0x10, 0x3a38, 0, 6 },
    { "sba_get_shifts", "pref_out_3a30", EXTRA_DUMP_THIS_DEREF_OFFSET, 0x10, 0x3a30, 0, 6 },
    /* docs/74 sec69: getShifts reads *(arg1+0x10)+0x3a38 (arg1 = sp[0]), NOT
     * *(this+0x10)+0x3a38 -- the two getShifts the setShifts body makes use
     * the same this/arg1, but the caller's third getShifts (0x10101ff6) has a
     * different arg1. Dump the real read to catch the per-frame Delta. */
    { "sba_get_shifts", "shifts_3a38_arg1", EXTRA_DUMP_STACK_DEREF2_OFFSET, 0, 0x10, 0x3a38, 6 },
    /* docs/74 sec67: the Preference's OUT proves it runs hi=0x30/lo=3 (out+2
     * matches), yet arg5(mode)=0 is captured. Dump the scene mode word
     * scene+0x5074 directly at getShifts to settle whether the live mode is
     * 0x33 (arg5 capture artifact) or 0 (Preference reads mode elsewhere). */
    { "sba_get_shifts", "mode_5074", EXTRA_DUMP_THIS_DEREF_OFFSET, 0x10, 0x5074, 0, 2 },
    { "sba_preference", "pref_data", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x64 },
    { "sba_preference", "blob", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x48 },
    /* v29 (docs/74 SS95) -- the inputs that produce the per-frame balance
     * scalar `k`.
     *
     * SS93/SS94 established the vendor's shift is `A[c] + k[f]`: A is a
     * per-channel constant stable across two rolls (agrees to 5 codes on G),
     * k is a per-scene scalar. Every offline candidate for k has been tested
     * and ruled out -- Y, U and V from the SS79-golden orderFpo triple (best
     * residual rms 33.0 against a k spread of 118), L itself, and every
     * int16/int32 field in this 0x64 pref_data window (nothing above |0.95|).
     *
     * WHY THE SEARCH COULD NOT HAVE SUCCEEDED. The call trace puts the
     * producer exactly here:
     *
     *     3300 sba_order_fpo_helper   (computes L)
     *     3301 sba_preference         <- consumes the triple, produces the shift
     *     3302 sba_set_shifts         (the shift is now set)
     *     3306 area_image_apply_lut   (applied; balance_shift_4b6 confirms
     *                                  the same six triples independently)
     *
     * but the scene structs are contiguous with a stride of 25820 bytes
     * (cn_enhanced_driver arg1: 150139080, 150164900, 150190720, ...), and
     * pref_data dumps 0x64 of them -- 0.4 %. The inputs driving k are almost
     * certainly outside that window, so the negative results above bound
     * where k ISN'T, not what it is.
     *
     * arg0 here sits ~0x3888 into the same scene struct fpo_calc's arg0
     * addresses, and orderFpo writes its triple at scene+0x38a2 -- just past
     * it, in a region fpo_calc's own arg0_big (0x3000) does not reach. 0x800
     * covers the triple and the fields around it. Same pointer already being
     * dumped, only larger: no new hook, no thunk, no HOOKCORE_MAX_HOOKS
     * change, and if the buffer is shorter than asked the row comes back
     * readable=false while the 0x64 row above still carries its data. */
    { "sba_preference", "pref_scene_big", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x800 },
    /* v29b (docs/74 SS97.3) -- arg 2, the ONE input the emulation is missing.
     *
     * SS97 executed fcn.1028c780 under Unicorn: it writes the balance shift to
     * arg2+0x08 and three of six frames reproduce within +-1 (FPU rounding).
     * The other three are short by a UNIFORM per-channel constant
     * (-92/-91/-91, -65/-65/-66, -39/-39/-40) -- pure luma by SS96's basis.
     *
     * A UC_HOOK_MEM_READ trace over the arg2 window then named the cause
     * exactly: the function reads **arg2+0x54**, and nothing else in that
     * region. arg2 has never been dumped -- only arg0 (pref_data, 0x64) and
     * arg3 (blob, 0x48) are -- and arg2 lies past the end of the pref_data
     * window, so the harness feeds it 0xCD poison. Frames 1-3 survive that;
     * frames 4-6 do not.
     *
     * So this is not a fishing expedition: one named offset, read on every
     * call, currently supplied as garbage, and the residual it would explain
     * is already measured and luma-shaped. 0x80 covers +0x54 with margin and
     * captures the shift/anchor slots the function WRITES at +0x02/+0x08 as
     * they stood on entry, which also gives a before/after pair for free. */
    { "sba_preference", "pref_arg2", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x80 },
    /* docs/74 sec68: balanceAreaImage reads the three ramp-shift words from
     * arg4+0x0a (0x10102f85..fa3). Dump them directly to pin scene+0x4b6 --
     * the setShifts OUT plus the per-frame uniform luma offset Delta that is
     * still unlocated (added between setShifts and this read). */
    { "balance_area_image", "balance_shift_4b6", EXTRA_DUMP_STACK_PTR_OFFSET, 3, 0xa, 0, 6 },
    { "color_adjust_shift", "impl_fields", EXTRA_DUMP_THIS_OFFSET, 0, 0x0c, 0, 0x28 },
    /* docs/74 SS72.7 (v21) -- sba_order_fpo_calc (0x1028b8d0) extra dumps.
     *
     * The question: SS72.3 proved this function's own top level writes only
     * pref_data+0x3e on the live-firing case, NOT the orderFpo Y/U/V triple
     * at pref_data+0x0/+0x2/+0x4. Either one of its 8 unread helpers writes
     * that triple (pref_data threaded in as a hidden arg), or something else
     * entirely does. This capture answers it empirically.
     *
     * WHY ENTRY-ONLY IS SUFFICIENT (a real deviation from SS72.7's own
     * proposed spec, made deliberately, not by oversight): LogExtraDumps is
     * called ONLY from HookEntryC (hookcore.c ~line 645), never from the
     * exit path -- extra dumps physically cannot fire on return with this
     * engine as built, and adding that would be a real engine change with
     * its own risk (at exit the args have been popped; sp no longer points
     * at a valid arg frame). It is not needed: this function is called 5x
     * per frame with the SAME pref_data pointer (arg 12, both call sites,
     * SS72.2), so consecutive ENTRY dumps give before/after across calls
     * 1->2, 2->3, 3->4, 4->5 directly, and the state AFTER the 5th call is
     * already captured by the existing `sba_preference`/`pref_data` row
     * above -- SS72.5 proved 0x1028b8d0's calls all precede Preference's own
     * single call in the same per-frame pass. Five entry dumps plus one
     * existing Preference dump = six observations of the same 0x64-byte blob
     * spanning all five calls, which is exactly the before/after series the
     * question needs.
     *
     * WHY NO 13 RAW-ARG ROWS (SS72.7 proposed 13x EXTRA_DUMP_STACK_PTR):
     * they would be redundant AND wrong-shaped. The engine already logs the
     * first STACK_DWORDS_LOGGED (=16, hookcore.c line 52) raw stack dwords on
     * every entry, and this function takes 13 args -- so all 13 raw arg
     * VALUES are captured for free in the existing "stack_dwords" field.
     * EXTRA_DUMP_STACK_PTR would instead DEREFERENCE each one, which is not
     * what SS72.7 wanted from those rows. Keeping them out also keeps this a
     * cheap addition on the real box.
     *
     * IMPORTANT -- this dump self-checks SS72.2's own arg table rather than
     * trusting it: SS72.2 rates its 13-arg mapping Tier 3 (static, cross-
     * checked two ways, NOT live-confirmed). If arg 12 is not really
     * scene+0x38a2, pref_data_before dumps something else and the mismatch is
     * itself the finding -- and the raw stack_dwords in the same JSONL line
     * give the ground truth to re-derive the real mapping from. Nothing here
     * assumes SS72.2 is right.
     *
     * arg 5 (the DPI-blob-copy-or-zero input SS72.4 traced) and arg 11
     * (fosDmin, scene+0x290c) are dumped too: SS72.4 found arg 5 has TWO
     * different provenances at the two call sites (a copy of the same
     * DPI-static blob Preference reads, vs explicitly zeroed), and which one
     * a real frame uses is one of the three unknowns SS72.6 named as
     * blocking a Unicorn harness. Dumping it settles that from real data. */
    { "sba_order_fpo_calc", "pref_data_before", EXTRA_DUMP_STACK_PTR, 12, 0, 0, 0x64 },
    { "sba_order_fpo_calc", "arg5_blob", EXTRA_DUMP_STACK_PTR, 5, 0, 0, 0x48 },
    { "sba_order_fpo_calc", "fos_dmin", EXTRA_DUMP_STACK_PTR, 11, 0, 0, 0x10 },
    /* v22 (docs/74 SS73/SS74) -- the remaining six POINTER arguments, so a
     * Unicorn harness can execute 0x1028b8d0 on real captured inputs and be
     * diffed bit-exact against the six known-good orderFpo triples SS73.2
     * already recorded. v21 dumped only args 5/11/12; args 0/1/2/6/7/10 are
     * pointers whose CONTENTS have never been captured, and a Unicorn run
     * cannot be built without them (SS72.6 refused to build one precisely
     * because inventing them is forbidden).
     *
     * Sizes are deliberately generous-but-bounded; every row is
     * IsBadReadPtr-guarded like the rest, so an over-large request degrades
     * to `"readable":false` rather than crashing. Total added ~1.5 KB per
     * call x 24 calls ~= 37 KB per capture -- negligible next to the
     * existing 0x84000-byte poly_input_r row.
     *
     * Arg->offset mapping below is LIVE-CONFIRMED from v21's own raw
     * stack_dwords (docs/74 SS73.4 and the scene-base arithmetic in SS75):
     * deriving the scene base from arg12 (= scene+0x38a2) and subtracting
     * shows args 0/1/2/7/11/12 land exactly on SS72.2's claimed offsets
     * (+0x1a, +0x3bc8, +0x388c, +0x3c34, +0x290c, +0x38a2). **arg 6 does
     * NOT** -- SS72.2 claimed scene+0x5978, but the real pointer sits
     * ~0xc65f0 BELOW the scene base, i.e. a separate allocation entirely.
     * It is dumped here as an unknown buffer rather than as a scene field,
     * and its size is a guess (0x100) for that reason -- if it comes back
     * truncated or unreadable, that is itself information.
     * args 5 and 10 are adjacent caller locals (arg10 == arg5 + 0x64). */
    { "sba_order_fpo_calc", "arg0_dens", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x40 },
    { "sba_order_fpo_calc", "arg1_cbank", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x400 },
    { "sba_order_fpo_calc", "arg2_388c", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x20 },
    { "sba_order_fpo_calc", "arg6_unknown", EXTRA_DUMP_STACK_PTR, 6, 0, 0, 0x100 },
    { "sba_order_fpo_calc", "arg7_3c34", EXTRA_DUMP_STACK_PTR, 7, 0, 0, 0x40 },
    { "sba_order_fpo_calc", "arg10_local2", EXTRA_DUMP_STACK_PTR, 10, 0, 0, 0x64 },
    /* v23 (docs/74 SS76) -- the v22 sizes were too small, proven by running
     * the real function under Unicorn on v22's own data: it early-exits with
     * return code 0x18bd at the bounds check at 0x1028b928/938/945/94e, which
     * reads `word [edx+0x104]` and `word [edx+0x106]` where edx == arg 6.
     * v22 dumped only 0x100 bytes of arg 6, so those two words fell outside
     * the capture and the harness read poison. That was the one size v22's
     * own comment flagged as a guess -- now measured, not guessed again.
     *
     * These rows are ADDITIVE alongside the v22 rows above, not replacements.
     * A larger request is IsBadReadPtr-guarded as a whole range, so if a
     * buffer turns out to be smaller than asked for, the big row comes back
     * `"readable":false` while the original small row still carries its data.
     * Belt and braces: cheap (~11.5 KB/call, ~276 KB per capture) against the
     * cost of another hardware round trip.
     *
     * Sizes derived from a mechanical scan of the function's own disassembly
     * for real memory operands (lea excluded -- it computes an address
     * without touching memory, and this function does use lea with very large
     * constants like +0x11436 as plain arithmetic, which would badly mislead
     * a naive grep): the deepest real accesses are [edx+0x106] (arg 6),
     * [edi+0x158], and a block of dword writes/reads spanning
     * [esi+0xb7c]..[esi+0xbac]. Which argument esi/edi hold at those points
     * is not yet pinned (both are reassigned several times), so arg 5 and
     * arg 7 are both sized past 0xbb0/0x158 respectively rather than
     * asserting a mapping this pass has not established. */
    /* v25: arg0 must reach 0x2880. docs/74 SS76.4's three dens arrays are at
     * arg0+0x1440, +0x1b00 and +0x21c0, each 864 x int16 = 0x6c0 bytes, so the
     * last one ends at 0x2880. v24's 0x1500 covered only the first ~96 of 864
     * densY samples -- confirmed exactly by the harness faulting at arg0+0x1440
     * and then arg0+0x1b00. 0x3000 leaves margin. */
    { "sba_order_fpo_calc", "arg0_big", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x3000 },
    { "sba_order_fpo_calc", "arg1_big", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x1000 },
    { "sba_order_fpo_calc", "arg2_big", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x200 },
    { "sba_order_fpo_calc", "arg5_big", EXTRA_DUMP_STACK_PTR, 5, 0, 0, 0xC00 },
    { "sba_order_fpo_calc", "arg6_big", EXTRA_DUMP_STACK_PTR, 6, 0, 0, 0x400 },
    { "sba_order_fpo_calc", "arg7_big", EXTRA_DUMP_STACK_PTR, 7, 0, 0, 0x1200 },
    { "sba_order_fpo_calc", "arg10_big", EXTRA_DUMP_STACK_PTR, 10, 0, 0, 0x200 },
    { "sba_order_fpo_calc", "arg11_big", EXTRA_DUMP_STACK_PTR, 11, 0, 0, 0x1200 },
    { "sba_order_fpo_calc", "arg12_big", EXTRA_DUMP_STACK_PTR, 12, 0, 0, 0x200 },
    /* v26 (docs/74 SS86) -- the interpreter's own context and PROGRAM.
     *
     * Calling convention (r2 af+pdf): args are sp[0..3]; `mov ebp,[arg_3ch]`
     * at 0x102aadf5 resolves by stack-delta (entry - 0x2c - 4 push, so
     * [esp+0x3c] == entry+0xc) to **arg index 2**, and `mov edi,[ebp+4]` at
     * 0x102aadfb is the program pointer. So:
     *   vm_ctx     = *sp[2]            -- the interpreter's context struct
     *   vm_program = *(*(sp[2] + 4))   -- the bytecode itself
     * EXTRA_DUMP_DEREF_PTR is exactly the second shape (deref the stack arg,
     * add the offset, deref again, dump from there).
     *
     * 0x1000 of program is a deliberate over-ask: the real length is unknown
     * (the halt opcode 0xff terminates it, so it is self-delimiting when
     * walked offline) and an over-read degrades to "readable":false rather
     * than truncating silently. If it comes back unreadable at 0x1000 the
     * smaller ctx dump still lands and the size can be stepped down. */
    /* v27 CORRECTION: v26 used stackIndex 2 and every dump came back
     * readable=false because sp[2] is 0. The prologue has TWO pushes before
     * the load, not one:
     *     0x102aadf3  push ebx
     *     0x102aadf4  push ebp        <- missed in the v26 derivation
     *     0x102aadf5  mov ebp,[esp+0x3c]
     * so esp = entry-0x2c-8 and [esp+0x3c] = entry+8 = ARG 1. The live
     * capture confirms it: sp[1] = 0x08e0e7c8 (a real pointer) while
     * sp[2] = 0x00000000.
     *
     * All four low indices are dumped rather than just the derived one.
     * This arg-index arithmetic has now been got wrong three times across
     * v22/v24/v26, each costing a hardware round trip; four small dumps cost
     * ~1 KB per call and remove the class of error entirely. Whichever index
     * is right lands, the rest come back readable=false and are ignored. */
    { "sba_vm_interp", "vm_ctx0", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x40 },
    { "sba_vm_interp", "vm_ctx1", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x40 },
    { "sba_vm_interp", "vm_ctx2", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x40 },
    { "sba_vm_interp", "vm_ctx3", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x40 },
    { "sba_vm_interp", "vm_prog0", EXTRA_DUMP_DEREF_PTR, 0, 4, 0, 0x800 },
    { "sba_vm_interp", "vm_prog1", EXTRA_DUMP_DEREF_PTR, 1, 4, 0, 0x800 },
    { "sba_vm_interp", "vm_prog2", EXTRA_DUMP_DEREF_PTR, 2, 4, 0, 0x800 },
    { "sba_vm_interp", "vm_prog3", EXTRA_DUMP_DEREF_PTR, 3, 4, 0, 0x800 },
    /* v28 (docs/74 SS88) -- the ONE row that unblocks Y's `L` term.
     *
     * SS88 ported the interpreter and located `L` exactly: the 23rd record
     * with type == 1 is record 156, whose whole body is `PUSH v133 ; STORE
     * v156`, so L == vars[133]. Computing it needs the input vector `in[]`,
     * which lives at (fpo_calc's arg 11) + 0x3c, 736 x u32.
     *
     * WHY NO EXISTING CAPTURE CAN SUPPLY IT. Extra dumps fire on ENTRY only
     * (LogExtraDumps is called solely from HookEntryC), and `in[]` is filled
     * later inside the same 0x1028b8d0 call, before fcn.102ac310 runs. The
     * region IS already inside arg11_big above -- and measured across all 48
     * arg11_big dumps of both v27 rolls it is 736 u32 of ZERO, with the whole
     * 4608-byte buffer holding just 5 non-zero words (indices 992..996,
     * outside in[]). So this is a timing gap, not a coverage gap, and no
     * re-reading of captures in hand can close it.
     *
     * sba_order_fpo_helper (0x1028ae00) already runs AFTER the fill -- it is
     * called from 0x1028c023, downstream of it -- and is already hooked, so
     * this needs no new hook, no thunk, and no HOOKCORE_MAX_HOOKS change:
     * one dump row only.
     *
     * WHICH ARG: MEASURED, NOT DERIVED. This arg-index arithmetic has been
     * got wrong three times (v22, v24, v26), each costing a hardware round
     * trip, so it was not derived from the prologue a fourth time. Both
     * hooks already log their first 16 raw stack dwords, so the answer was
     * read straight out of the v27 captures: for every helper call, exactly
     * ONE stack index equals the enclosing fpo_calc call's arg 11 --
     * index 1, uniquely, 12/12 on roll A and 12/12 on roll B. (argsPtr =
     * ebp+44 with the return address at ebp+40, hookstub.S:58-60, so
     * stack_dwords[0] is the FIRST argument.)
     *
     * WHY THE WHOLE BUFFER AND NOT arg1+0x3c. A STACK_PTR_OFFSET row at
     * +0x3c would re-stake the result on the offset being exactly right --
     * the same shape of assumption that cost v22 four bytes and v24 an
     * offset-vs-total misreading. Dumping from the base at 0x1200 subsumes
     * in[] wherever it starts (0x3c + 0xb80 = 0xbbc < 0x1200) and is byte-
     * for-byte comparable with arg11_big above: same buffer, same span, one
     * snapshot before the fill and one after. The diff of those two IS the
     * evidence that the fill happened. ~4.6 KB x 12 helper calls = ~55 KB
     * per capture. */
    { "sba_order_fpo_helper", "arg1_big_filled", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x1200 },
    { NULL, NULL, EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0 }, /* sentinel */
};
