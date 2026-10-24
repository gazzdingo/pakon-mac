#ifndef PAKON_COLOUR_ANALYSIS_FOS_H
#define PAKON_COLOUR_ANALYSIS_FOS_H
#include <stdint.h>
#include "internal.h"
#include "analysis/sba_measure.h"

/* FOS, Kodak's roll analysis: AnsFosCapabilityImpl::analyze (0x1023ff80) -> SbaCalcFosResults (0x1028f570), with its
 * orderFpo helper (0x1028f250) and weight function (0x1028f1b0); docs/re/16 section 6. Run once per SBA instance of a roll:
 * FOS#1 on the scenes' pass-1 state (sba instance), FOS#2 on the afterSCPLut instance's pass-1 state. */

#define PKC_FOS_MAX_SCENES 64    /* this port's bound on min(n, max_frames); PSI's maxFramesToFos is 40 */

/* The dpi keys AnsFosCapabilityImpl copies (sba/SbaDPI/sba-CN-default.dpi; Kodak-observed at Impl+0x5c..0x64 /
 * +0x8c / +0x90 / +0x94 / +0x95 on every truth run): */
typedef struct {
    int16_t wtab[5];      /* orderFpoLowSatLimit, orderFpoHighSatLimit, orderFpoMinWeight, orderFpoMaxWeight,
                           * orderFpoUseExpandedSatLimit (250 900 0 100 1): the helper's distance weights */
    int32_t min_frames;   /* mff (4): fewer scenes -> no FOS */
    int32_t max_frames;   /* maxFramesToFos (40): only the first max_frames scenes are analysed */
    int fos_on;           /* 0: fosOn = 0 and useHistory = 0 -- FOS never calculates and every sba call (pass 1 included) takes
                           * pass kind 0 (analyzePass1 0x10219380 / analyzePass2 0x10215d6a, RE 26); 1 on every shipped CN dpi */
} pkc_fos_params;

/* Read the keys above from the dpi. PK_E_ARG on NULLs; PK_E_VENDOR_DATA if the file or a key is missing, if a value
 * breaks Kodak's own dpi checks (0 <= MinWeight < MaxWeight <= 100, 0 < LowSat < HighSat), if maxFramesToFos is not in
 * 1..PKC_FOS_MAX_SCENES, or if the dpi selects a path this port does not have: useHistory != 0 (the fos-history tables).
 * fosOn = 0 with useHistory = 0 is ported (fos_on = 0, RE 26: Kodak-pinned on an edited dpi). Kodak keeps fosOn as a byte
 * flag (any non-zero low byte is on); the port accepts the shipped 1 and 0. */
pk_status pkc_fos_params_load(const char *vendor_root, pkc_fos_params *out);
/* The same from a given SBA dpi (a product row's: sba-CN-default-78-13.dpi, ...; every shipped CN dpi has these keys). */
pk_status pkc_fos_params_read(const char *dpi, pkc_fos_params *out);

/* SbaFOSResults (Impl+0x18, 36 bytes): every field is Kodak's int16 word, sign-extended. */
typedef struct {
    int32_t order_fpo[3];   /* +0x00 Y/C1/C2: opening axes + helper deltas */
    int32_t order_avg[3];   /* +0x06 RGB */
    int32_t dmin[3];        /* +0x0c fosDmin: min over the scenes' dmin */
    int32_t gm_slope, gm_off, ill_slope, ill_off;     /* +0x12..+0x18 */
    int32_t ofpo_method;    /* +0x1c: 0 in-radius mean, 1 weighted mean, 2 dmin fallback */
    int32_t num_pixels;     /* +0x1e: accepted samples (low 16 bits) */
    int32_t gm_rsq, ill_rsq;/* +0x20 / +0x22 */
    int valid;              /* 1: Kodak's calc ran and returned 0 (Impl+0x88 = 1); 0: no FOS for this roll */
    int32_t calc_err;       /* Kodak's non-zero SbaCalcFosResults status (0x189d: eigen discriminant), else 0 */
} pkc_fos_result;

/* One FOS pass over a roll's first min(n, max_frames) scenes. Per scene k:
 *   grids[k]  = the pass's 24x36 grid (Task 10; Kodak's sba+0x1a planes 0-2); planes 3-5 (Y/C1/C2) are derived with
 *               pkc_sba_axes exactly as Kodak's measure image holds them;
 *   dmins[k]  = the scene dmin of that pass (Task 11 pkc_scene_dmin; sba+0x290c words 0..2);
 *   scenes[k] = the scene state after the pass-1 measure (pkc_sba_measure_scene PKC_SBA_PASS1): its mask
 *               (+0xc20) and vector slots 4/5 (+0x4c/+0x50), 480/481 (+0x7bc/+0x7c0) and 612 (+0x9cc).
 * ctx gives the opening (fpo), the dc words (params + 0xdc: 10/150/605/750/250/3/30 at +0xe/+0x18/+0x1c/+0x1e/+0x20/
 * +0x2c/+0x2e) and the flag bytes. Kodak's skip byte is per scene (byte[sba+0x388c+4] of each scene); the port's flags
 * are one ctx constant, so flags[4] == 1 skips every scene and a per-scene skip is not representable.
 * Fewer than min_frames scenes: out->valid = 0, PK_OK. Kodak's calc error (0x189d, the eigen discriminant): out->valid
 * = 0, out->calc_err = 0x189d, PK_OK; orderFpo / dmin / ofpo_method hold what Kodak wrote before failing. At Kodak the
 * roll analysis then fails: PIAnselAnalyzeRoll returns 0 and the afterSCPLut instance never runs (observed, crafted
 * roll t15d) -- callers must treat calc_err as a failed roll. With no accepted sample Kodak returns 0 but leaves
 * orderAvg and the two R^2 words unwritten; every roll gets a fresh, zeroed Impl (observed across rolls in one session,
 * bp_t15r.txt), so they are 0, which is what the port reports.
 * Errors: PK_E_ARG on NULLs, n < 0 or min(n, max_frames) > PKC_FOS_MAX_SCENES; PK_E_VENDOR_DATA if a vector slot FOS
 * reads is not known[] (ruling R18), or where Kodak's helper leaves a delta uninitialised (its distance overflowing
 * int32) or faults (a division by zero only a negative dc threshold reaches) -- neither reachable with the shipped dc
 * words and 12-bit grids. */
pk_status pkc_fos_roll(const pkc_sba_ctx *ctx, const pkc_fos_params *fp, int n, const int32_t (*grids)[3][PKC_GRID_N],
                       const uint16_t (*dmins)[3], const pkc_sba_scene *scenes, pkc_fos_result *out);
#endif
