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
        (void *)&Thunk_21, (void *)&Thunk_22,
    };

    static const HookDef table[HOOKCORE_MAX_HOOKS] = {
        /* ---- Frame / stage boundaries ---- */
        { "PakonIMAu.dll", 0x10069490, "cn_enhanced_driver",
          "AnsCnEnhancedPath per-scene analyze driver (fcn.10069490) -- "
          "the real call-order spine: analyzeFugc -> balanceAreaImage -> "
          "analyzeArea -> analyzeAttributes -> analyzeFalloff -> "
          "analyzeAutoTone -> analyzeSharpening -> ...",
          "docs/74 SS11 (call order), docs/62 line ~201-202", 0, 1, 0 },
        { "PakonIMAu.dll", 0x100fb730, "analyze_auto_tone",
          "ColorNegativePath::analyzeAutoTone -- the real 6-subsystem tone "
          "chain (cna/dra/toneHelper/contrast/ast/citras). Every subsystem "
          "individually Unicorn-verified bit-exact per docs/66; this "
          "boundary hook is for correlating a live call with the port's "
          "own real_auto_tone() on the same frame.",
          "docs/63, docs/65, docs/66, docs/74 (address repeated throughout)", 0, 1, 0 },

        /* ---- SBA / balance ---- */
        { "PakonIMAu.dll", 0x10100260, "sba_set_shifts",
          "ColorNegativePath::setShifts -- reads via getShifts, writes the "
          "3x int16 OUT balance-shift buffer this whole tone chain anchors "
          "to (the \"SBA neutral-balance output\" the task asks for).",
          "tools/ansel/python-pipeline/pakon_sba_apply.py module docstring", 0, 1, 0 },
        { "PakonIMAu.dll", 0x10100a37, "sba_set_shifts_12",
          "setShifts real closed-form entry for the shipped CN control "
          "words (ntdChoice,ctdChoice)=(1,2) -- PATH_SET_SHIFTS_12.",
          "pakon_sba_apply.py: PATH_SET_SHIFTS_12 = 0x10100A37", 0, 1, 0 },
        { "PakonIMAu.dll", 0x10124000, "sba_get_shifts",
          "getShifts -- copies 3x int16 from *(AnsSbaCapability+0x10)+0x3a38.",
          "pakon_sba_apply.py module docstring", 0, 1, 0 },
        { "PakonIMAu.dll", 0x1028c780, "sba_preference",
          "Preference -- the ONLY confirmed writer of +0x3a38 (analyzePass2 "
          "@ 0x10216433 passes scene+0x3a30; fist-rounds 3x int16 into "
          "scene+0x3a38/+3a3a/+3a3c).",
          "pakon_sba_apply.py module docstring", 0, 1, 0 },
        { "PakonIMAu.dll", 0x1019a0c0, "sba_apply_balance_shifts",
          "AnsAreaCapabilityImpl::applyBalanceShifts -- the real PER-PIXEL "
          "LUT apply (builds three 4096-entry LUTs via 0x1006c4f0, applies "
          "clamp(i+shift,0,4095) to every pixel). This is the closest real "
          "analogue of pakon_sba_apply.apply_balance_shifts() -- the "
          "pixel-buffer stage to diff, not just the scalar shifts.",
          "pakon_sba_apply.py module docstring", 0, 1, 0 },

        /* ---- FUGC ---- */
        { "PakonIMAu.dll", 0x100fed00, "fugc_analyze",
          "analyzeFugc -- FUGC analyze entry point in the real per-scene driver.",
          "docs/62 line ~201", 0, 1, 0 },
        { "PakonIMAu.dll", 0x101f82c0, "fugc_set_lut_info",
          "setLutInfo -- builds the FUGC apply LUT from ebp14 (setShifts "
          "OUT @ +0x4b6) and ebp18 (SceneContext \"dmin\" bag). Confirmed "
          "real-DLL-verified including the near-identity offsets=(0,-1,1) "
          "case, docs/74 SS10.",
          "docs/66 line ~1839; docs/74 SS10", 0, 1, 0 },
        { "PakonIMAu.dll", 0x101fc518, "fugc_mode_dispatch",
          "FUGC analyze / mode dispatch: Cap+0x60e8 == 2 -> metrics path, "
          "else -> setLutInfo. Address has a trailing \"...\" in its own "
          "source citation (approximate, not independently re-confirmed "
          "this pass) -- verify the exact entry live before trusting it.",
          "pakon_ansel.py comment near fugc_mode field (~line 657-658)", 1, 1, 0 },

        /* ---- falloff / area / attributes ---- */
        { "PakonIMAu.dll", 0x100fe960, "analyze_falloff",
          "analyzeFalloff -- per-pixel radial lens/scanner vignetting "
          "correction. The \"falloff output\" hook the task asks for.",
          "docs/62 line ~201-202; docs/74 SS11", 0, 1, 0 },
        { "PakonIMAu.dll", 0x10102b20, "balance_area_image",
          "balanceAreaImage -- opens with find(\"area\") idempotency guard "
          "(a HIT throws; a MISS falls through -- docs/74 SS11 already "
          "ruled out the find(\"area\") HIT path as a live data-consumption "
          "channel, but never read the miss-path body itself).",
          "docs/74 SS11", 0, 1, 0 },
        { "PakonIMAu.dll", 0x100e16d0, "analyze_area",
          "analyzeArea entry (732-function capability, 0% ported). docs/74 "
          "SS11-12 calls the four unreplicated stages -- this one included -- "
          "\"the sole remaining concrete software lead\" after every other "
          "mechanism was checked against the real DLL and confirmed correct.",
          "docs/74 SS11, SS12, SS\"What this changes about the open item list\" item 1", 0, 1, 0 },
        { "PakonIMAu.dll", 0x100fb3d0, "analyze_attributes",
          "analyzeAttributes -- one of the four unreplicated stages between "
          "FUGC and autoTone, real call order per docs/74 SS11.",
          "docs/74 SS11", 0, 1, 0 },

        /* ---- ICC transform ---- */
        { "PakonIMAu.dll", 0x102f8420, "icc_xform_apply",
          "ImaICCXForm::apply -- builds source/dest descriptors and calls "
          "SpEvaluate @ 0x102f884c (kodakcms.dll import thunk 0x10500338). "
          "The \"ICC transform input/output\" hook the task asks for.",
          "docs/62 SS12.4.2", 0, 1, 0 },
        { "PakonIMAu.dll", 0x1016ede0, "icc_effect_op",
          "ImaICCEffectOp -- wraps apply, passes this+0x118 (source max) / "
          "this+0x120 (dest max) at 0x1016ee84-0x1016eef8. The scale "
          "(4095 vs 32767 vs Go's x65535/4095) is explicitly UNRESOLVED "
          "in docs/62 SS12.4.2 -- a live capture of this+0x118/this+0x120 "
          "settles it directly.",
          "docs/62 SS12.4.2", 0, 1, 0 },
        { "PakonIMAu.dll", 0x1016e680, "icc_effect_op_ctor",
          "ImaICCEffectOp ctor -- the only writer found (static analysis) "
          "for this+0x118, loading the hardcoded 32767.0 from 0x1058fac0. "
          "A live hit here with a DIFFERENT value would directly disprove "
          "the \"no later setter\" assumption docs/62 flags as unconfirmed.",
          "docs/62 SS12.4.2", 0, 1, 0 },

        /* ---- F-235 / TLA / TLB dmin-remap chain ---- */
        { "TLA.dll", 0x1003f7db, "tla_baddscene",
          "bAddScene -- the REAL writer of FUGC's \"dmin\" SceneContext bag: "
          "FindDmin on the raw PRE-balance frame words, then TLB's F-135 "
          "ColNeg poly remap, stored as \"dmin\" and read back via "
          "getCnContext. This port's own stand-in "
          "(pakon_ansel.py render_scene, `ebp18` / `raw_dmin` block) is "
          "flagged in its own comment as producing values OUTSIDE the "
          "accept band on every real frame tested -- a real, confirmed, "
          "currently-not-the-206-code-defect wiring bug worth diffing live.",
          "tools/ansel/python-pipeline/pakon_ansel.py comment ~line 900-932; "
          "docs/66 golden-fleet section corroborates the surrounding TLA "
          "AddScene ColNeg leaf shape (zeroing @ 0x1003f7eb, width=4 push "
          "@ 0x1003f85d)", 0, 1, 0 },
        { "TLA.dll", 0x100064d0, "tla_colneg_planar_scan",
          "PIColorCorrectColNegPlanarScan -- F-235 stage-2 entry, shuffles "
          "5 args into the MMX kernel's 7 at 0x1001c470.",
          "docs/65 line ~93; docs/66 golden-fleet section", 0, 1, 0 },
        { "TLA.dll", 0x1001c470, "tla_colneg_mmx_kernel",
          "The inner MMX kernel itself (pmulhw x3, independently-truncated "
          "products, THEN summed -- the exact bug docs/66's \"golden "
          "fleet\" section fixed on the port side, one code high). NOTE: "
          "if this fires per-scanline/per-pixel-block rather than once per "
          "frame, it may be high-frequency live -- see hooks.cfg to "
          "disable if a first run shows it's too hot.",
          "docs/66 \"6.2 -- golden fleet, colneg_1px remap TLA\"", 0, 1, 0 },

        { "TLB.dll", 0x10034b9b, "tlb_f135_poly_remap",
          "F-135 ColNeg polynomial remap used by bAddScene to turn the raw "
          "FindDmin walk into \"dmin\". NOTE: this port's own comment cites "
          "it as \"TLB.dll fcn.1000d880 @ 0x10034b9b\" -- an r2 auto-name/VA "
          "pair that looks inconsistent (fcn.<addr> normally names a "
          "function BY its own entry address) with docs/65's separate "
          "citation of \"TLB.dll:fcn.1000d880\" for the general stage-2 3x10 "
          "polynomial (PolyPixel). Both addresses are hooked (this one and "
          "tlb_polypixel) precisely so a live capture can resolve which is "
          "which rather than guessing.",
          "pakon_ansel.py comment ~line 903-904", 1, 1, 0 },
        { "TLB.dll", 0x1000d880, "tlb_polypixel",
          "PolyPixel -- general stage-2 3x10 quadratic polynomial (the "
          "entry address implied directly by its own r2 auto-name, "
          "fcn.1000d880). See tlb_f135_poly_remap's note above -- hooked "
          "alongside it to resolve the naming ambiguity live.",
          "docs/65 line ~86; docs/62 line ~950", 0, 1, 0 },

        /* ---- AFE (device-side register write) ---- */
        { "TLB.dll", 0x100299c0, "tlb_afe_offset_write",
          "FN_bDrvPutCcdAtoDOffsets -- AD9826 offset register encoder "
          "(9-bit sign-magnitude; this port had a two's-complement bug "
          "here, fixed 2026-08-12, docs/72). This is the closest REAL, "
          "documented \"AFE\" hook available. NOTE: this is the OFFSET "
          "write, not GAIN -- no distinct address for a gain-register "
          "write function was found documented anywhere in docs/62-74. "
          "See README.md \"AFE gain -- honestly unresolved\".",
          "docs/72 SS1.3 (\"FN_bDrvPutCcdAtoDOffsets at 0x100299c0, "
          "[VERIFIED-FROM-BINARY]\")", 0, 1, 0 },
    };

    int i;
    eng->count = HOOKCORE_MAX_HOOKS;
    for (i = 0; i < HOOKCORE_MAX_HOOKS; i++) {
        eng->defs[i] = table[i];
        eng->defs[i].entryThunk = thunks[i];
    }
}
