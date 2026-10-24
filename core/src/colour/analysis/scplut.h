#ifndef PAKON_COLOUR_ANALYSIS_SCPLUT_H
#define PAKON_COLOUR_ANALYSIS_SCPLUT_H
#include <stdint.h>
#include "internal.h"
#include "analysis/fos.h"

/* The roll scpLut: AnsSCPLutCapabilityImpl::analyze (0x102128f0) -> worker 0x102127d0 -> core FUN_10287eb0, called by
 * ColorNegativePath::analyzeScpLutBalance (0x100fd190) with FOS#1's words (docs/re/16 section 2). Kodak runs it once per
 * scene with the same roll-level inputs (identical LUTs, observed); the port builds it once per roll. Consumers: pass B
 * (afterSCPLutSba runs on scpLut(image)) and the FUGC dmin remap. */

/* AnsSCPLutDPI, as AnsSCPLutDPI::readAscii (0x101d03b0) fills it from
 * anselinstalldir/dataPathItems/SCPLut/SCPLut-scanner-prod-gen-default-default-default.dpi (Kodak reads the first file of
 * that directory; it is the only one shipped). Offsets are the dpi object's; Impl keeps a copy at +0x18. */
typedef struct {
    int16_t offset_option;     /* +0x32 offsetOption: 0 ANS_SCPLUT_SCP_OFFSET, 1 ANS_SCPLUT_DMIN_PIVOT, 2 ANS_SCPLUT_ZERO_PIVOT */
    uint8_t visual_weighting;  /* +0x36 visualWeighting (0/1) */
    uint8_t modify_dmin;       /* +0x30 modifyDmin: the dmin remap through the LUT (read by the FUGC path) */
    uint8_t run_after_lut;     /* +0x35 runSCPAfterLut: the afterSCPLut pass (read by pass B) */
    int16_t ntd_choice;        /* +0x38 ntdChoice: 0 ANS_FIRST_PASS, 1 ANS_LUT_FIRST_PASS, 2 ANS_SECOND_PASS (setShifts) */
    int16_t ctd_choice;        /* +0x3a ctdChoice: the same tokens */
    double prop;               /* +0x40 proportionalCorrection, Kodak checks [0, 2] */
    double thr;                /* +0x48 slopeDeltaThreshold, Kodak checks [0, 2] */
} pkc_scplut_params;           /* shipped: 2, 1, 1, 1, 1, 2, 0.7, 0.30 */

/* Read the dpi above. Values as readAscii takes them: a bool is 1 iff the token is "true" (any case), offsetOption must
 * be one of its three tokens (any case), an unknown ntd/ctd token gives 0 (0x101d082a / 0x101d08c5), prop and thr must
 * be finite and in [0, 2] (Kodak's readAscii fails otherwise and PIBegin returns -20: observed for prop 2.5).
 * On the shipped file and on the edited ones Kodak loaded in the truth runs (lab/rollbal/truth/t16/dpi) the result is
 * Kodak's Impl copy field for field. Where readAscii differs on other edited files (by disassembly, no Kodak run):
 *   - keys: Kodak lower-cases them; here they must have the shipped spelling (a re-cased key reads as missing);
 *   - an unknown key: Kodak's if-chain fails the read (0x101d0a5d, "Error during AnsSCPLutDPI::readAscii()"); ignored here;
 *   - a repeated key: Kodak keeps the last value; pkc_kt finds the first;
 *   - "key=value" without spaces: Kodak's sscanf("%s = %s") skips the line; pkc_kt parses it;
 *   - a value with trailing junk ("0.7x", "0x1"): Kodak's %lf takes the leading number; rejected here;
 *   - an unknown offsetOption token, a missing key or a value %lf cannot read: Kodak keeps the dpi constructor's value
 *     (not traced); rejected here.
 * PK_E_ARG on NULLs; PK_E_NOMEM if the parser runs out of memory; PK_E_VENDOR_DATA if the file or a key is missing, a
 * value breaks the rules above, or useSCPLut is not true: then AnsSCPLutCapability::analyze skips Impl::analyze
 * (0x1012272e..0x10122736 tests the byte it copied from the dpi; observed, dpi/vD.dpi), builds no LUT, and the path still
 * remaps the dmin through the capability's buffer -- not ported. (Impl::analyze's own test at 0x10212937, useSCPLut == 0
 * or no FOS results, only replaces the seven words by zeros and still runs the core.) */
pk_status pkc_scplut_params_load(const char *vendor_root, pkc_scplut_params *out);

/* AnsSCPLutResults (Impl+0x68..+0xb7): the core's nine doubles in Kodak's order, then the worker's tenth. */
typedef struct {
    double slope[3];           /* red/green/blue slope */
    double offset[3];          /* red/green/blue offset */
    double slope_dist;         /* sqrt of the slope spread (NaN never occurs for int16 words: q >= 0 over all of them) */
    double slope_limiter;      /* k = thr / slope_dist if slope_dist >= thr, else 1 (NaN for thr = slope_dist = 0) */
    double visual_gamma;       /* w = 1 / (0.414 dR + 0.079 dB + 0.507 dG) if visualWeighting, else 1 */
    double slope_spread;       /* Impl+0xb0: sqrt of the same spread over the final slopes (worker 0x10212899..0x102128bd);
                                * no consumer found -- kept because Kodak stores it next to the others */
} pkc_scplut_result;

/* The roll scpLut from FOS pass #1. fos1->valid: the seven words FOS wrote (gm_slope, gm_off, ill_slope, ill_off,
 * dmin[0..2]; low 16 bits, as Kodak's movsx reads them). !valid with calc_err == 0 (fewer than mff scenes): Kodak's path
 * passes seven zero words (FOS results pointer NULL, observed r1/r12/syns) and the core still runs -- with the shipped
 * dpi that gives the identity LUT, with slopeDeltaThreshold 0 an all-zero LUT (k = 0/0, observed). The LUT is
 *     out->t[c][i] = clamp(int16(trunc64(i * slope_c - offset_c + 0.5)), 0, 4095)
 * i.e. Kodak's _ftol2 (0x104ffe44) truncation to 64 bits (NaN -> 0x8000000000000000) and a word store before the clamp,
 * so values beyond int16 wrap (observed on crafted arguments). res (may be NULL) gets the ten result doubles.
 * Errors: PK_E_ARG on NULL p / fos1 / out, on params outside what readAscii can produce (offset_option not 0..2,
 * visual_weighting > 1, prop / thr not in [0, 2]), and on fos1->calc_err != 0: Kodak never builds the scpLut for such a
 * roll (PIAnselAnalyzeRoll returns 0 first, observed t15d) -- the caller must fail the roll. out is not written then. */
pk_status pkc_scplut_build(const pkc_scplut_params *p, const pkc_fos_result *fos1, pkc_lut3 *out, pkc_scplut_result *res);

/* analyzeScpLutBalance applying the LUT to the scene's analysis image (scene+0x04) in place: 0x100fdb49 -> 0x100eccc0 ->
 * 0x101b28c0 -> 0x100d9340, out_c = lut_c[in_c] per sample, the index read with movsx. Observed (lab/rollbal/truth/t14:
 * scpPre / scpPost / fleshCall dumps): on every scene of every truth roll, also under 4 frames (the identity LUT); the
 * image afterwards is what pass B's createAlgData and the flesh correction read. Kodak does not bounds-check the index
 * (an analysis image is 12-bit, so it never leaves the LUT); here a sample outside 0..4095 is clamped first (the plan's
 * LUT-index rule). in and out may be the same planes (in place, as Kodak); otherwise out->p[] must hold in->w * in->h
 * samples each and out->w / out->h are set. PK_E_ARG on NULLs, w or h < 1, or NULL planes. */
pk_status pkc_scplut_apply(const pkc_lut3 *lut, const pkc_planes *in, pkc_planes *out);
#endif
