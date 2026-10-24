#ifndef PAKON_COLOUR_ANALYSIS_FLESH_H
#define PAKON_COLOUR_ANALYSIS_FLESH_H
#include <stdint.h>
#include "internal.h"

/* The flesh (skin-tone) correction: ColorNegativePath::analyzePostBalance (0x100fdc40) calls AnsFleshCapability::analyze
 * (0x100fe3ac) -> AnsFleshCapabilityImpl::analyze (0x101c92c0), which builds the weight map (fcn.10271bc0) and runs the
 * adjust calculator fcn.10270280 on the scene's analysis image (scene+0x04, pushed as both arg3 and arg4). That image is
 * the SBA analysis image (pkc_analysis_image) with the roll scpLut applied in place by analyzeScpLutBalance
 * (pkc_scplut_apply); the shift triple (arg6) is the pre-flesh balance scene+0x4b6 (pkc_setshifts_12's output); the
 * exposure (arg7) is scene+0x4bc, which getSbaExposure (0x101241a0, called at 0x100fdde9 before the flesh call) set to the
 * SBA exposure in stops. The calculator's delta, one word for all three channels, is added to the triple with three
 * 16-bit adds (0x100fe471 / 0x100fe479 / 0x100fe47d): total = pre-flesh + delta. Ported from the disassembly (the
 * frozen reference lab/reference/pakon_flesh*.py served as the lead) and pinned against Kodak at x87 PC53
 * (lab/rollbal/truth/t14, docs/re/16 section 8). */

#define PKC_FLESH_BINS 32   /* the conditional-probability tables' size; the axis index is clamped to 0..31 */

/* AnsFleshDPI as fleshParameterReader (fcn.10272380) fills it from
 * anselinstalldir/dataPathItems/flesh/FleshDPI/flesh-srcType-metric-default-default.dpi, plus the three
 * condProbTbl files its l/s/tCondProbKey name (anselinstalldir/dataPathItems/flesh/CondProbTables). Offsets are the dpi
 * struct's (fcn.10270280's arg1 = Impl+0x18). Kodak-observed equal, bit for bit, on every truth run. */
typedef struct {
    double axial_prob;          /* +0x08 axialProb: the weight map's Gaussian, sigma = (1 - clip) dim / sqrt(-8 ln p) */
    double clip_amount;         /* +0x10 clipAmount: the borders */
    int16_t loff, soff, toff;   /* +0x18 / +0x1a / +0x1c (%hd) */
    double lscale, sscale, tscale;  /* +0x20 / +0x28 / +0x30 (%lf; the detector divides by their float32 narrowing) */
    int32_t use_advanced;       /* +0x44: must be 0 (the Bayesian-net path is not ported) */
    double grow_threshold;      /* +0x48: read only by the oneDTable == 0 branch (not ported) */
    double region_threshold;    /* +0x50: read only by the useAdvanced branch (not ported) */
    int32_t st_only;            /* +0x58: drop the l table's factor */
    uint8_t t_space;            /* +0x5c: X uses 0.57736720554272514 (1/1.732) instead of 1/3 */
    int32_t one_d_table;        /* +0x60: must be non-zero (the 3-D LUT branch is not ported) */
    double beta;                /* +0x5068: copied into both factors below by readAscii */
    double front_lit_beta;      /* +0x5070: D's factor for X >= aim -- always = beta (readAscii 0x101ce26c..0x101ce285
                                 * overwrites the parsed frontLitBeta / backLitBeta with beta; observed) */
    double back_lit_beta;       /* +0x5078: ... for X < aim, = beta as well */
    double flesh_pref_adj;      /* +0x5080 */
    double flesh_neutral_aim;   /* +0x5088 */
    double flesh_count_thresh;  /* +0x5090: no correction when count / area is below it */
    double percent_flesh_adj;   /* +0x5098 */
    double exposure_limit;      /* +0x50a0: no correction when the exposure is below it */
    uint8_t write_intermediate_images;  /* +0x60a8: debug dumps only (no effect on the result) */
    uint8_t use_small_analysis_image;   /* +0x60a9: must be 0 (fcn.104e8360 is not ported) */
    uint8_t darken_only;        /* +0x60aa: no correction when D > 0 */
    double cond_l[PKC_FLESH_BINS], cond_s[PKC_FLESH_BINS], cond_t[PKC_FLESH_BINS];   /* dpi +0x38 / +0x3c / +0x40 */
} pkc_flesh_params;

/* Read the dpi and its tables. frontLitBeta and backLitBeta must parse but are replaced by beta, as readAscii does.
 * Values as Kodak's readers take them (%lf, %hd, %ld; tSpace, writeIntermediateImages,
 * useSmallAnalysisImage, darkenOnly scanned as an int and stored as (v != 0)); a table is "size = 32" then "vals ="
 * and 32 numbers (the shipped files' format; Kodak's table reader was not traced, its doubles equal strtod's on every
 * shipped value, observed). Keys need the shipped spelling (Kodak lower-cases them). PK_E_ARG on NULLs; PK_E_NOMEM;
 * PK_E_VENDOR_DATA if a file or a key is missing or a value does not parse, if axialProb is not in (0, 1) (Kodak's
 * weight map then fails, 0x10271d1d / 0x10271d63, or runs on a NaN sigma), if clipAmount is outside [0, 1) (negative
 * borders, or sigma 0) or an l / s / t scale's float32 narrowing is <= 0 or below about 2.1e-5 (a quotient would reach 2^31: a
 * negative index in Kodak), or a table is not 32 values;
 * PK_E_UNSUPPORTED if the dpi selects a branch that is not ported (useAdvanced != 0, oneDTable == 0,
 * useSmallAnalysisImage != 0: the shipped DIGITAL_CAMERA dpi does all three). out is zeroed on error. */
pk_status pkc_flesh_params_load(const char *vendor_root, pkc_flesh_params *out);
/* The same from a dpi file and the directory holding its tables (an edited dpi). */
pk_status pkc_flesh_params_read(const char *dpi_path, const char *tables_dir, pkc_flesh_params *out);

/* What fcn.10270280 computes, by its results struct (arg11 = Impl+0x60c8) and the locals behind it. */
typedef struct {
    double x;               /* +0x00: the flesh statistic, stat * (tSpace ? 0.57736720554272514 : 1/3) / nsum, or the
                             * neutral aim when nothing was counted */
    double nsum;            /* +0x08: the summed weights */
    double q;               /* +0x10: count / area (x87: NaN for 0 / 0) */
    double neg_d130;        /* +0x18: -(D * 1/130) */
    double max_prob255;     /* +0x20: maxProb * 1/255 */
    double threshold;       /* +0x28: the probability threshold fcn.1029ec50 chose (bin * 4; 256 when it found none) */
    int16_t adjust[3];      /* +0x30..+0x34: the delta, the same word three times */
    double stat;            /* the weighted sum of R + G + B */
    double d;               /* D = -((X - aim) * beta) */
    int32_t count;          /* fleshCount: binarised flesh pixels inside the window */
    int32_t max_prob;       /* 255 if any pixel was counted, -1 if flesh was found but none inside the window, 0 if
                             * no flesh was found (the reduction is skipped, 0x10271246) */
    int32_t area;           /* (cols - 2 b_outer) * (rows - 2 b_inner): crossed, as Kodak computes it (0x1027167f) */
    int32_t b_outer, b_inner;   /* the row and column borders */
    int any_flesh;          /* the clamp loop saw a value above 20 (0x102711f8) */
} pkc_flesh_result;

/* The flesh correction of one scene. img = the scene's analysis image with the roll scpLut applied (w = cols,
 * h = rows; samples 0..4095 -- Kodak indexes the shift LUTs with them unchecked, the port clamps the index); preflesh =
 * the scene's pre-flesh shift words; exposure = the scene's SBA exposure in stops, as the float Kodak passes
 * ((float) of pkc_sba_exposure_stops on the sba instance's pass-2 triple: exact, docs/re/23). total =
 * preflesh + delta as 16-bit words; res (may be NULL) gets every value above.
 * Errors (total / res not written): PK_E_ARG on NULLs or a params struct the loader cannot produce (the unported
 * branches, axialProb outside (0, 1), clipAmount outside [0, 1), an l / s / t scale outside the loader's bound); PK_E_IMAGE_TOO_SMALL if w or h < 3 (the Sobel / cleanup kernels; Kodak's path
 * refuses analysis images under 107 x 107 before this, 0x100d47c4) or if the row border is 0 (clipAmount * rows < 2:
 * Kodak's reduction would start on row h, past the image -- not reached with the shipped clipAmount); PK_E_NOMEM. */
pk_status pkc_flesh_delta(const pkc_flesh_params *p, const pkc_planes *img, const int16_t preflesh[3], float exposure,
                          int16_t total[3], pkc_flesh_result *res);

/* Kodak's weight-map exponential, 1000 e^z, at x87 PC53 (fcn.10271bc0 0x10271e1c..0x10271e3c): t = round53(z log2e_64),
 * n = rint(t), u = f2xm1(t - n) to 64 bits, v = round53(1 + u), P = round53(v 2^n 1000); the weight is _ftol(P). f2xm1 is
 * modelled as correctly rounded to 64 bits (computed in double-double and rounded with integers; *decided = 0 when the
 * double-double cannot settle the rounding -- never on a reachable shipped-dpi pixel). Needs unsigned __int128 (64-bit
 * clang / gcc; ruling R25: the shipped library targets 64-bit macOS). v / decided may be NULL. Exposed for the tests. */
double pkc_flesh_exp1000(double z, double *v, int *decided);

/* The weight plane the reduction reads: fcn.10271bc0's Gaussian map over [b_r, rows - b_r) x [b_c, cols - b_c) (peak 1000
 * at the centre, pkc_flesh_exp1000), padded back to rows x cols by edge replication (fcn.104e7880, operation 1; centred, so
 * the pad only fills the borders). out has rows * cols words, row-major. Exposed for the tests. PK_E_ARG on NULLs, on
 * rows / cols outside 1..32767 (Kodak's movsx) or on axialProb outside (0, 1) or clipAmount outside [0, 1). */
pk_status pkc_flesh_weight_plane(const pkc_flesh_params *p, int rows, int cols, int16_t *out);
#endif
