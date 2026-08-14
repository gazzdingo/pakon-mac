/*
 * Shared hook table for the native (Frida-free) XP-compatible harness.
 *
 * This is a hand-kept DUPLICATE of the HOOKS[] table in ../agent.js -- the
 * Frida path and this native path are two independent execution mechanisms
 * for the same idea (see ../README.md "Does this run on Windows XP" for why
 * both exist: Frida requires Python 3.5+, which requires Windows Vista+;
 * this native path targets genuine 32-bit Windows XP directly). There is no
 * automatic sharing between the JS and C versions -- if you add/change a
 * hook in one, update the other by hand, and keep the citations honest.
 *
 * Every VA is quoted the same way the rest of this project's docs quote it:
 * assuming the owning DLL loads at 0x10000000 (confirmed for PakonIMAu.dll
 * by tools/re/reachability.py's own header and docs/62 line ~1246; assumed,
 * not independently re-confirmed, for TLA.dll/TLB.dll -- see ../README.md).
 * hookdll.c NEVER treats a documented VA as a literal runtime address -- it
 * always resolves runtime_addr = module_base + (documented_VA - 0x10000000)
 * against wherever this specific process actually loaded that DLL.
 */
#ifndef PAKON_HOOKS_COMMON_H
#define PAKON_HOOKS_COMMON_H

#include <windows.h>

#define ASSUMED_BASE 0x10000000UL

typedef struct {
    const char *dll;     /* module file name, e.g. "PakonIMAu.dll" */
    DWORD va;             /* documented VA, assumed base 0x10000000 -- ignored if resolve_by_export */
    const char *id;       /* short stable id, matches agent.js's hook id */
    const char *desc;     /* one-line description */
    const char *cite;     /* doc/file citation */
    int frame_boundary;   /* 1 == bump the frame counter on entry */
    int approximate;      /* 1 == address is flagged approximate/ambiguous in its own source */
    int resolve_by_export; /* 1 == resolve via GetProcAddress(dll, export_name), not VA rebasing */
    const char *export_name;
} HookDef;

/* Keep this list in the same order, with the same ids, as agent.js's
   HOOKS[] -- see that file for the full citation text (trimmed here for
   size; ../README.md's hook table has the full version of each one). */
static const HookDef g_hookDefs[] = {
    { "PakonIMAu.dll", 0x10069490, "cn_enhanced_driver",
      "AnsCnEnhancedPath per-scene driver -- frame boundary",
      "docs/74 section 11; docs/62 line ~201-202", 1, 0 },
    { "PakonIMAu.dll", 0x100fb730, "analyze_auto_tone",
      "ColorNegativePath::analyzeAutoTone -- tone-chain boundary",
      "docs/63, docs/65, docs/66, docs/74", 0, 0 },

    { "PakonIMAu.dll", 0x10100260, "sba_set_shifts",
      "ColorNegativePath::setShifts -- SBA neutral-balance OUT",
      "pakon_sba_apply.py module docstring", 0, 0 },
    { "PakonIMAu.dll", 0x10100a37, "sba_set_shifts_12",
      "setShifts shipped CN (1,2) closed-form entry, PATH_SET_SHIFTS_12",
      "pakon_sba_apply.py: PATH_SET_SHIFTS_12 = 0x10100A37", 0, 0 },
    { "PakonIMAu.dll", 0x10124000, "sba_get_shifts",
      "getShifts -- copies 3x int16 from AnsSbaCapability+0x10+0x3a38",
      "pakon_sba_apply.py module docstring", 0, 0 },
    { "PakonIMAu.dll", 0x1028c780, "sba_preference",
      "Preference -- confirmed sole writer of +0x3a38",
      "pakon_sba_apply.py module docstring", 0, 0 },
    { "PakonIMAu.dll", 0x1019a0c0, "sba_apply_balance_shifts",
      "AnsAreaCapabilityImpl::applyBalanceShifts -- real per-pixel LUT apply",
      "pakon_sba_apply.py module docstring", 0, 0 },

    { "PakonIMAu.dll", 0x100fed00, "fugc_analyze",
      "analyzeFugc",
      "docs/62 line ~201", 0, 0 },
    { "PakonIMAu.dll", 0x101f82c0, "fugc_set_lut_info",
      "setLutInfo -- FUGC real apply-LUT build",
      "docs/66 line ~1839; docs/74 section 10", 0, 0 },
    { "PakonIMAu.dll", 0x101fc518, "fugc_mode_dispatch",
      "FUGC analyze/mode dispatch (Cap+0x60e8==2 -> metrics else setLutInfo)",
      "pakon_ansel.py comment ~line 657-658 (approximate)", 0, 1 },

    { "PakonIMAu.dll", 0x100fe960, "analyze_falloff",
      "analyzeFalloff -- per-pixel radial vignetting correction",
      "docs/62 line ~201-202; docs/74 section 11", 0, 0 },
    { "PakonIMAu.dll", 0x10102b20, "balance_area_image",
      "balanceAreaImage",
      "docs/74 section 11", 0, 0 },
    { "PakonIMAu.dll", 0x100e16d0, "analyze_area",
      "analyzeArea entry -- docs/74's top remaining software suspect",
      "docs/74 section 11, section 12", 0, 0 },
    { "PakonIMAu.dll", 0x100fb3d0, "analyze_attributes",
      "analyzeAttributes",
      "docs/74 section 11", 0, 0 },

    { "PakonIMAu.dll", 0x102f8420, "icc_xform_apply",
      "ImaICCXForm::apply -- ICC transform, calls SpEvaluate",
      "docs/62 section 12.4.2", 0, 0 },
    { "PakonIMAu.dll", 0x1016ede0, "icc_effect_op",
      "ImaICCEffectOp -- source/dest max scale (4095 vs 32767, unresolved)",
      "docs/62 section 12.4.2", 0, 0 },
    { "PakonIMAu.dll", 0x1016e680, "icc_effect_op_ctor",
      "ImaICCEffectOp ctor -- writes this+0x118 = 32767.0 hardcoded",
      "docs/62 section 12.4.2", 0, 0 },

    { "TLA.dll", 0x1003f7db, "tla_baddscene",
      "bAddScene -- real writer of FUGC's dmin SceneContext bag",
      "pakon_ansel.py comment ~line 900-932", 0, 0 },
    { "TLA.dll", 0x100064d0, "tla_colneg_planar_scan",
      "PIColorCorrectColNegPlanarScan -- F-235 stage-2 entry",
      "docs/65 line ~93; docs/66 golden-fleet section", 0, 0 },
    { "TLA.dll", 0x1001c470, "tla_colneg_mmx_kernel",
      "Inner MMX kernel (pmulhw x3, independently truncated, then summed)",
      "docs/66 \"6.2 -- golden fleet, colneg_1px remap TLA\"", 0, 0 },

    { "TLB.dll", 0x10034b9b, "tlb_f135_poly_remap",
      "F-135 ColNeg poly remap used by bAddScene -- naming ambiguity, see README",
      "pakon_ansel.py comment ~line 903-904 (approximate)", 0, 1 },
    { "TLB.dll", 0x1000d880, "tlb_polypixel",
      "PolyPixel -- general stage-2 3x10 quadratic",
      "docs/65 line ~86; docs/62 line ~950", 0, 0 },

    { "TLB.dll", 0x100299c0, "tlb_afe_offset_write",
      "FN_bDrvPutCcdAtoDOffsets -- AD9826 offset register (NOT gain; see README)",
      "docs/72 section 1.3", 0, 0 },

    /* Self-test hook: resolved live via GetProcAddress, NOT the
       VA+assumed-base scheme every hook above uses (kernel32.dll's real
       load address has nothing to do with 0x10000000). GetTickCount is
       called constantly by almost any real Windows process, so this
       fires within seconds of injection into ANY target -- including a
       harmless one like notepad.exe -- letting you confirm the whole
       inject -> breakpoint -> VEH -> log -> single-step -> re-arm
       pipeline actually works on your specific machine before ever
       pointing this at a real scan. See README.md "self-test before the
       real thing". */
    { "kernel32.dll", 0, "selftest_gettickcount",
      "GetTickCount -- harmless, high-frequency, present in every process; "
      "proves the hook pipeline itself works before you trust it on a real scan",
      "n/a -- diagnostic self-test, not part of the Pakon pipeline", 0, 0,
      1, "GetTickCount" },
};

#define NUM_HOOKS ((int)(sizeof(g_hookDefs) / sizeof(g_hookDefs[0])))

/* Known-constant heuristic annotation table -- mirrors agent.js's
   KNOWN_CONSTANTS. Values from docs/74 section 1 / section 9. */
typedef struct {
    short value;
    const char *meaning;
} KnownConst;

static const KnownConst g_knownConsts[] = {
    { 1550, "neutralBalancePoint/lowFixedPoint/highFixedPoint/setShifts pivot 0x60E (docs/74 s1)" },
    { 1200, "paperMin (docs/74 s1)" },
    { 2000, "paperMax (docs/74 s1)" },
    { 4095, "12-bit domain max" },
    { 879,  "fpo R shipped CN default (docs/74 s9)" },
    { 1250, "fpo G shipped CN default (docs/74 s9)" },
    { 1386, "fpo B shipped CN default (docs/74 s9)" },
    { 683,  "setShifts_out R example, docs/74 s9 (confirm per-frame, not universal)" },
    { 297,  "setShifts_out G example, docs/74 s9" },
    { 151,  "setShifts_out B example, docs/74 s9" },
};
#define NUM_KNOWN_CONSTS ((int)(sizeof(g_knownConsts) / sizeof(g_knownConsts[0])))

#endif /* PAKON_HOOKS_COMMON_H */
