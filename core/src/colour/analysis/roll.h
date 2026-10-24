#ifndef PAKON_COLOUR_ANALYSIS_ROLL_H
#define PAKON_COLOUR_ANALYSIS_ROLL_H
#include <stdint.h>
#include "internal.h"
#include "falloff.h"
#include "analysis/sba_measure.h"
#include "analysis/fos.h"
#include "analysis/scplut.h"
#include "analysis/sba_pref.h"
#include "analysis/flesh.h"
#include "analysis/fugc.h"

/* Kodak's roll analysis on PSI's default colour-negative path (CN-Enhanced class 1), from PIAnselAddScene to the scene
 * LUT PIAnselColorSceneBalancePlanar renders with. docs/re/24-roll-orchestration.md has the evidence; Kodak-exact at x87
 * PC53 on every truth roll of lab/rollbal/truth/t19 (scene LUT, exposure, falloff decision).
 *
 * One Kodak roll (one PIAnselStartNewRoll .. PIAnselAnalyzeRoll; TLB hands PakonIMAu at most 40 pictures per roll, RE 04:
 * pkc_roll_batches) runs phase by phase over its scenes -- every phase over every scene before the next:
 *   1. sba instance, pass 1 (analyzePass1, fcn.1028b8d0 kind 1), each scene: analysis image (RE 19) -> grid ->
 *      scene dmin = pkc_scene_dmin(ctx, grid) with ctx = the AddScene dmin -> pkc_ctx_dmin_pass1 -> the measure.
 *   2. FOS#1 (AnsFosCapabilityImpl, sba instance) over the first min(n, maxFramesToFos) scenes' pass-1 state; with fewer
 *      than mff scenes no FOS (not valid). A calc error (0x189d) ends the roll here: PIAnselAnalyzeRoll returns 0 (below).
 *   3. sba instance, pass 2, each scene: kind FOS2 with FOS#1 (mode 2) or SHORT2 without (mode 0); pkc_ctx_dmin_pass2;
 *      the triple A; the scene's SBA exposure (getSbaExposure reads this instance's word: RE 23); Preference(A).
 *   4. scpLut balance: the roll scpLut from FOS#1 (seven zero words without FOS: the identity with the shipped dpi), then
 *      each scene: the context dmin remap (modifyDmin) and the LUT applied to the scene's analysis image in place.
 *   5. afterSCPLut instance, pass 1, each scene, on the scpLut image's grid: scene dmin from the remapped context.
 *   6. FOS#2 over that instance's pass-1 state (a calc error fails the roll as in 2: the same Impl code; not observed).
 *   7. afterSCPLut instance, pass 2, each scene: kind and FOS as in 3 with FOS#2; pkc_ctx_dmin_pass2; triple B;
 *      Preference(B).
 *   8. per scene (analyzePostBalance, analyzeFugc): pre-flesh = setShifts (1,2)(A, B, scpLut); flesh on the scpLut
 *      image with the exposure of 3 -> total; FUGC dmin' from the context after 7; the FUGC LUT with the total shift.
 *   9. the scene LUT (PIAnselColorSceneBalancePlanar's single LUT op: the transform group's cascade of filmLut (the
 *      identity), scpLut, the flesh shift LUT clamp(i + total, 0, 4095) and FUGC; observed, docs/re/24 section 2):
 *          lut_s[c][i] = fugc[c][clamp(scplut[c][i] + total[c], 0, 4095)]
 *      and the falloff export gate on the exposure (pkc_falloff_enabled).
 * The Preference mode word is 0 on the default path (no userColorBalance / userNeutralBalance attribute). */

#define PKC_ROLL_BATCH 40          /* TLB's pictures per PakonIMAu roll (FUN_10034a60: 0x28; RE 04 Q4.3) */
#define PKC_ROLL_MAX 64            /* this port's bound on one PakonIMAu roll (>= PKC_ROLL_BATCH; FOS takes <= 40) */
#define PKC_ROLL_MIN_AIMG 107      /* an analysis image under 107 x 107 in either side is skipped by Kodak (flag at 0x100d47c4; RE 27) */

/* Every roll-static input, read once from the vendor tree (each loader's own checks apply) for one film: Kodak picks the
 * files per scene from its productCode / genCode (AddScene descriptor words 0x18 / 0x19) and the film ISO they give
 * (docs/re/24 section 8); TLB passes one pair per strip. */
#define PKC_DX_NONE (-1)           /* product / gen code TLB passes for a strip without a DX read (= PK_DX_NONE) */
typedef struct {
    int product_code, gen_code;    /* as given */
    int dx_none;                   /* both PKC_DX_NONE: the scene context has no productCode / genCode */
    int film_iso;                  /* pkc_film_iso (common-ProdCodeTable.dpi), 0 = unknown */
    char sba_key[64];              /* the sba.map row's key: ansel-sba-CN-default, ansel-sba-78-13, ... */
    pkc_sba_ctx sba;               /* the selected SBA dpi + pcode + PakonIMAu tables */
    pkc_fos_params fos;
    pkc_scplut_params scp;
    pkc_sba_pref pref;
    pkc_flesh_params flesh;
    int16_t seed[3][PKC_FUGC_N], tdmin[3], aim[3];   /* FUGC: the .lut seed and aTableDmin, aFilmAimDmin */
    pkc_falloff_params falloff;
    pkc_lut3 nra;                  /* NRA thresholds (render): the film ISO's noise table */
    /* TEST SEAM (0 in every loaded cfg): simulate Kodak's analysis error at one of the six sites the Task 22 pokes reached
     * (docs/re/26 section 1): 1 sba pass 1 (scene 0), 2 FOS#1 calc, 3 sba pass 2 (scene 0), 4 afterSCPLut pass 1 (scene 0),
     * 5 FOS#2 calc, 6 afterSCPLut pass 2 (scene 0). The roll then ends as Kodak's does (failed roll). Real data cannot reach
     * the sba-core sites in Kodak (its sba core fails on NULL / size arguments, plus two data-dependent exits RE 27 section 3
     * shows unreachable or load-time; the port's own pass-1 / triple error statuses are unported-branch or #DE cases and
     * stay loud errors, scoped to the batch). */
    int inject_fail;
} pkc_roll_cfg;

/* Load everything above for a film's codes (PKC_DX_NONE / PKC_DX_NONE: no DX read -- no ISO, sba.map's product rows
 * skipped, no FOS; 0 / 0 is a real code pair, the one every pre-Task-21 truth run used):
 *   - the film ISO from common-ProdCodeTable.dpi (pkc_film_iso);
 *   - the SBA dpi from sba/SbaDPI/sba.map, first match on (_AnselPath_ CN-Enhanced, sourceType 1, productCode,
 *     genCode), resolved by key (the shipped map: 78/13, 79/15, 96/any, 43/any have their own dpi, everything else
 *     ansel-sba-CN-default); every SBA loader reads that dpi;
 *   - FUGC by pkc_fugc_seed_film / pkc_fugc_aim_load_film; NRA by pkc_nra_prepare_film (the ISO's noise table).
 * Kodak-pinned on truth t19 runs_codes (all four product rows, ISO classes and their range ends, out-of-table codes).
 * PK_E_ARG on NULLs or product_code outside 0..32767; PK_E_UNSUPPORTED for gen_code outside 0..15 (Kodak's AddScene
 * fails for gen 20 and the scene renders through a NULL transform: observed, run c5g20; DX gen codes are 4 bits) and when
 * the SCPLut dpi selects a path this orchestration does not have: (ntdChoice, ctdChoice) other than (1, 2) (only setShifts
 * (1,2) is ported) or runSCPAfterLut false (the afterSCPLut instance would not run); the loaders' and selections' errors
 * otherwise (PK_E_VENDOR_DATA, PK_E_NOMEM, PK_E_UNSUPPORTED). On failure nothing is left allocated. */
pk_status pkc_roll_cfg_load(const char *vendor_root, const char *derived_root, int product_code, int gen_code, pkc_roll_cfg *cfg);
void pkc_roll_cfg_free(pkc_roll_cfg *cfg);

/* One scene as PIAnselAddScene receives it: the lo-res frame after TLB's LUT + 3x10 polynomial (12-bit, planar). */
typedef struct { int w, h; const uint16_t *p[3]; } pkc_roll_frame;

/* What the analysis leaves for one scene. */
typedef struct {
    pkc_lut3 lut_s;                /* the scene LUT */
    double exposure;               /* SBA exposure in stops (the float at scene ctx +0x4bc, exact) */
    int falloff;                   /* 1: the falloff op is exported (pkc_falloff_enabled(exposure)) */
    int failed;                    /* 1: Kodak's roll analysis failed (any of the six error sites of RE 26 section 1: the FOS#1 / FOS#2 calc, the sba core in either pass of either instance); see pkc_roll_analyse */
    pk_status status;              /* pkc_roll_batches only: PK_OK, or why the port refused this scene's whole batch (the other fields are 0) */
    int oob;                       /* 1: this scene's grid read past its image and was clamped (pkc_grid24x36_clamped; non-Kodak, R41); only set by pkc_roll_batches' analysis */
    int inexact;                   /* pkc_roll_batches only: 1 = the scene's batch holds an oob scene, so its statistics are not Kodak's (R41) */
    int skipped;                   /* 1: analysis image under 107 x 107 -- no SBA, no balance: lut_s is the identity, no falloff, no NRA (RE 27) */
    /* intermediates (diagnostics and tests) */
    int16_t shift_a[3], shift_b[3], preflesh[3], total[3], dmin_prime[3];
    int32_t triple_a[3], triple_b[3];
} pkc_roll_scene;

/* Roll-level results. */
typedef struct {
    int n_fos;                     /* scenes FOS analysed: min(n, maxFramesToFos), 0 when FOS did not run (< mff) */
    pkc_fos_result fos1, fos2;
    pkc_lut3 scplut;
    int failed;                    /* = the roll failed (a FOS calc error on the real path; the other sites only through the test seam) */
} pkc_roll_info;

/* One Kodak roll of n scenes (1 <= n <= PKC_ROLL_MAX); addscene_dmin[k] = scene k's AddScene dmin (descriptor words
 * 0x15..0x17: TLB passes the strip's film base after its LUT + poly to every scene; PakonIMAu keeps one per scene).
 * out[0..n) receives every scene; info (may be NULL) the roll-level results.
 * FOS calc error (0x189d): PIAnselAnalyzeRoll returns 0 and nothing after the failing FOS runs (observed: t15d). The
 * scenes then render with what PakonIMAu holds for them: the scene LUT is all zero (observed: Kodak's LUT op table on
 * t15d's balances) and the falloff gate sees exposure 0 (observed). This returns PK_OK with info->failed = 1 and every
 * out[k].failed = 1, lut_s all 0, exposure 0 and falloff = pkc_falloff_enabled(0).
 * Errors (out / info unspecified): PK_E_ARG on NULLs, n out of range, a frame with NULL planes, w or h < 1 or a sample
 * > 4095 (AddScene data is 12-bit); an analysis image under 107 x 107 is not an error: Kodak
 * skips the scene (scene.skipped, RE 27);
 * PK_E_UNSUPPORTED for a frame whose grid sampler would read past its analysis image (Kodak averages what follows its
 * buffer: docs/re/24 section 5); PK_E_NOMEM; any stage's error (PK_E_UNSUPPORTED / PK_E_VENDOR_DATA where Kodak takes a
 * branch the port lacks). */
pk_status pkc_roll_analyse(const pkc_roll_cfg *cfg, int n, const pkc_roll_frame *frames, const uint16_t (*addscene_dmin)[3],
                           pkc_roll_scene *out, pkc_roll_info *info);

/* TLB's batching (FUN_10034a60, RE 04 Q4.3): pictures 0..n-1 go to PakonIMAu in rolls of PKC_ROLL_BATCH, in order, the
 * last one shorter; every roll gets the same AddScene dmin (one film base per strip). Each batch is an independent
 * pkc_roll_analyse; a failed batch does not stop the next one (TLB logs error 2 / 0x14e and continues with the next
 * batch, 0x10034f8c..0x10034fb6). A batch the port refuses (pkc_roll_analyse returns an error other than PK_E_NOMEM: a grid
 * that would read past its image, a Kodak #DE case, ...: Kodak does not fail these, the port cannot reproduce them) gets
 * out[k].status = that error on each of its frames and is otherwise zero; the other batches are unaffected (RE 27).
 * PK_E_ARG on NULLs / n < 1; PK_E_NOMEM (nothing usable); PK_OK otherwise. */
pk_status pkc_roll_batches(const pkc_roll_cfg *cfg, int n, const pkc_roll_frame *frames, const uint16_t addscene_dmin[3],
                           pkc_roll_scene *out);

/* The scene LUT of step 9 (exposed for the tests). PK_E_ARG on NULLs. */
pk_status pkc_roll_scene_lut(const pkc_lut3 *scplut, const int16_t total[3], const pkc_lut3 *fugc, pkc_lut3 *out);
#endif
