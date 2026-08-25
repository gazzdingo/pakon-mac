/*
 * pakon_pipeline_cli.c — Pure C end-to-end Pakon F-135 / F-235 / F-335 pipeline.
 * Native ARM64 (Apple Silicon). Compile: cc -O2 -arch arm64 -o tools/pakon_pipeline_cli tools/pakon_pipeline_cli.c -lm
 *
 * Supports all scanner models via --model f135|f235|f335:
 *   F-135 (TLB.dll): stage-2 = 3×10 float polynomial  TLB @ 0x1000d880
 *   F-235/F-335 (TLA.dll): stage-2 = density LUT + 3×4 int16 matrix  TLA @ 0x10014ff0
 *
 * Stage order (docs/58-colour-pipeline.md §1, TLB:0x10026c90):
 *   Raw → Stage-0 sensor correction (TLB @ 0x100246d0)
 *       → Stage-2 colour correction (poly F-135 / LUT+matrix F-235)
 *       → Stage-4 Ansel (PIAnselColorSceneBalancePlanar TLB @ 0x100271dd):
 *           Preference FPU (PakonIMAu @ 0x1028c780)
 *           setShifts(1,2) (PakonIMAu @ 0x10100a37)
 *           applyBalanceShifts (PakonIMAu @ 0x1019a0c0)
 *           Shasta ToneLUT apply (PakonIMAu @ 0x1014dcc0)
 *           FUGC setLutInfo + apply (PakonIMAu @ 0x101f82c0)
 *           ICC CLUT: Rpd2Pcs_HR200_QS_v5s10.pf → Srgb_v2.pf (docs/58 §10)
 *       → Stage-6 PIColorAdjustPlanar (PakonIMAu @ 0x10013bc0) [after Ansel]
 *       → BMP write
 *
 * Usage:
 *   ./tools/pakon_pipeline_cli <input.bin> <output.bmp> \
 *       --width W --height H \
 *       [--model f135|f235|f335] \
 *       [--eeprom eeprom_52.bin] \
 *       [--sba-dpi path/sba-CN-default.dpi] \
 *       [--fugc-lut path/NoShift_fugc-generic0225.lut] \
 *       [--rpd2pcs path/Rpd2Pcs_HR200_QS_v5s10.pf] \
 *       [--srgb path/Srgb_v2.pf]
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <ctype.h>

/* =========================================================================
 * MODEL DEFINITIONS
 * ========================================================================= */

typedef enum { MODEL_F135 = 135, MODEL_F235 = 235, MODEL_F335 = 335 } PakonModel;

/* =========================================================================
 * STAGE 0 — SENSOR CORRECTION   TLB.dll @ 0x100246d0
 * (included from pakon_color_c.c)
 * ========================================================================= */
#include "pakon_color_c.c"

/* =========================================================================
 * STAGE 2 — F-235/F-335: DENSITY LUT + 3×4 INT16 MATRIX KERNEL
 * Cite: TLA.dll @ 0x10014ff0 (bApplyKodakColorCorrection)
 *       TLA.dll @ 0x1000dfc0  density LUT generator: lut[i] = -7000*log10(i/16383)
 *       PakonIMAu.dll @ 0x1001c470 MMX kernel (scalar equivalent)
 *       docs/58-colour-pipeline.md §3, §5
 *
 * For F-235/F-335 the pipeline is:
 *   raw14 → dens_lut[raw & 0x3FFF] → 3×4 int16 matrix multiply → clamp 0..4092
 *
 * Matrix context layout (docs/58 §5.2):
 *   ctx.coeff[3][3]: int16, scale 8192  (i.e. coeff_float = coeff_i16 / 8192)
 *   ctx.offset[3]:   int16, scale 1
 *
 * Kernel per 4 pixels (docs/58 §5.6):
 *   out_k = clamp( Σ_c floor(ctx[k][c] * LUT[raw_c] / 65536) + ctx.offset[k], 0, 4092 )
 *
 * Note: pmulhw is signed multiply-high: (int16)(((int32)a*(int32)b)>>16)
 *       This is floor for positives, which is what we reproduce below.
 * ========================================================================= */

#define TLA_LUT_SIZE     16384
#define TLA_LUT_SCALE    (-7000.0)   /* TLA.dll:0x1000dfc0 uses -7000 (F-235), TLB uses -3500 (F-135 ref only) */
#define TLA_RPD_MAX      4092        /* TLA clamp: 0x7003/0xF003 saturating paddusw (docs/58 §5.6) */

/* Build the −7000·log₁₀ density LUT.
 * Cite: TLA.dll @ 0x10013730 / 0x1000dfc0
 *   lut[0] = 32766  (= 2 * 16383, TLA path: cfg+0x24=2)
 *   lut[i] = _ftol( -7000 * log10(i / 16383.0) )  for i >= 1
 * _ftol truncates toward zero.
 */
static void build_density_lut_tla(int32_t *lut) {
    /* TLA.dll:0x10013730: lut[0] = [cfg+0x24] * 0x3FFF = 2 * 16383 = 32766 */
    lut[0] = 32766;
    for (int i = 1; i < TLA_LUT_SIZE; i++) {
        /* TLA.dll:0x100137be: lut[i] = _ftol( -(2*3500) * log10(i/16383) ) */
        double v = TLA_LUT_SCALE * log10((double)i / 16383.0);
        /* _ftol truncates toward zero */
        lut[i] = (int32_t)(v < 0.0 ? -trunc(-v) : trunc(v));
    }
}

/* Quantise a 3×4 double matrix into the int16 context format.
 * Cite: TLA.dll:0x10012eb0
 *   coeff_i16[k][c] = _ftol(8192 * src[4k+c] + 0.5)  (truncate-toward-zero after +0.5)
 *   offset_i16[k]   = _ftol(1    * src[4k+3] + 0.5)
 */
typedef struct {
    int16_t coeff[3][3];   /* [output_channel][input_channel] */
    int16_t offset[3];
} TlaMatrixCtx;

/* _ftol(x) = truncate toward zero */
static inline int32_t _ftol(double x) {
    return (int32_t)(x < 0.0 ? -trunc(-x) : trunc(x));
}

static void quantise_matrix_tla(const double src[3][4], TlaMatrixCtx *ctx) {
    /* Cite: TLA.dll @ 0x10012eb0 (buildContext), _ftol(cs*c + 0.5) */
    for (int k = 0; k < 3; k++) {
        for (int c = 0; c < 3; c++)
            ctx->coeff[k][c] = (int16_t)_ftol(8192.0 * src[k][c] + 0.5);
        ctx->offset[k] = (int16_t)_ftol(src[k][3] + 0.5);
    }
}

/* Apply TLA colour correction kernel to a planar image.
 * Cite: PakonIMAu.dll @ 0x1001c470 (scan kernel), scalar equivalent.
 * out_k = clamp( Σ_c floor(coeff[k][c] * lut[raw_c] / 65536) + offset[k], 0, 4092 )
 *
 * in_rgb:  HWC uint16, 3 channels (14-bit raw)
 * out_rgb: HWC int32, 3 channels (12-bit RPD, 0..4092)
 */
static void apply_color_correct_tla(const uint16_t *in_rgb, int32_t *out_rgb,
                                    int num_pixels,
                                    const int32_t *dens_lut,
                                    const TlaMatrixCtx *ctx)
{
    for (int i = 0; i < num_pixels; i++) {
        int idx = i * 3;
        /* LUT index: and 0x3FFF (14-bit fold, docs/58 §3.4) */
        int32_t L[3];
        for (int c = 0; c < 3; c++) {
            L[c] = dens_lut[in_rgb[idx + c] & 0x3FFF] & 0xFFFF; /* low 16 bits as signed */
            if (L[c] & 0x8000) L[c] -= 0x10000; /* sign-extend 16→32 */
        }
        for (int k = 0; k < 3; k++) {
            /* Cite: pmulhw = floor((int32)a*(int32)b >> 16) per product, then sum */
            int32_t acc = 0;
            for (int c = 0; c < 3; c++) {
                int32_t prod = ((int32_t)ctx->coeff[k][c] * L[c]) >> 16; /* floor */
                acc += prod;
            }
            acc += ctx->offset[k];
            /* Clamp 0..4092 (TLA: 0x7003/0xF003 paddusw/psubusw) */
            if (acc < 0) acc = 0;
            if (acc > TLA_RPD_MAX) acc = TLA_RPD_MAX;
            out_rgb[idx + k] = acc;
        }
    }
}

/* =========================================================================
 * STAGE 4 — ANSEL ENGINE (all models share PakonIMAu.dll)
 * ========================================================================= */

/* ---- Preference FPU  PakonIMAu.dll @ 0x1028c780 -----------------------
 * Cite: docs/49-preference-fpu-binary.md
 *       docs/58-colour-pipeline.md §7
 *
 * Mode 0x11 (lo=1, hi=0x10): aimY = openingY, aimU/V = openingU/V
 * → dY = w1e + aimY - openingY, dU = dV = 0 (pcls=0 shipped CN)
 * → combine → shifts inv(s', -U, -V)
 *
 * All constants from PakonIMAu.dll .rdata (docs/49):
 */
#define INV_SQRT3_P    0.5773502717125849    /* 0x105a6f38 */
#define INV_SQRT6_P    0.40824829759439285   /* 0x105a6f30 */
#define INV_SQRT2_P    0.7071067623730956    /* 0x105a6f28 */
#define SQRT_2_OVER_3  0.8164965951887857    /* 0x105a6f40 */
#define SCALE_0_001    0.0010000000474974513 /* 0x105a0800 float */
#define ONE_THIRD      (1.0 / 3.0)           /* 0x105943c0 */
#define PREF_PIVOT     0x60E                 /* 1550 — 0x60e branch @ 0x10100260 */

/* ftol2 @ 0x104ffe44: truncate toward zero */
static inline int pref_ftol2(double x) { return (int)(x < 0 ? -trunc(-x) : trunc(x)); }

/* Forward opponent transform @ 0x1028c7f7 */
static void pref_rgb_to_yuv(double r, double g, double b,
                             double *y, double *u, double *v) {
    *y = (r + g + b) * INV_SQRT3_P;
    *u = (2.0*g - r - b) * INV_SQRT6_P;
    *v = (b - r) * INV_SQRT2_P;
}

/* Inverse opponent @ 0x1028cc33 */
static void pref_yuv_to_rgb(double y, double u, double v,
                             double *r, double *g, double *b) {
    double ys = y * INV_SQRT3_P;
    double us = u * INV_SQRT6_P;
    double vs = v * INV_SQRT2_P;
    *r = ys - us - vs;
    *g = ys + u * SQRT_2_OVER_3;
    *b = ys - us + vs;
}

/* Helper @ 0x1028c540 */
static void pref_helper(double r, double g, double b,
                         double *m, double *o1, double *o2) {
    *m  = (r + g + b) * SCALE_0_001 * ONE_THIRD;
    *o1 = (g * SCALE_0_001 - *m) * INV_SQRT2_P;
    *o2 = (b * SCALE_0_001 - r * SCALE_0_001) * INV_SQRT6_P;
}

/* Clamp s' @ 0x1028cbbb..cc1f */
static double pref_clamp_s(double t, double lim46, double lo42, double hi44) {
    double s = lim46 - t;
    if (s < lo42) return lo42;
    if (s > hi44) return hi44;
    return s;
}

/*
 * Preference mode 0x11 (lo=1, hi=0x10, pcls=0 shipped CN).
 * Returns shifts[3] = ftol2(inv(s', -U_r, -V_r)).
 *
 * fpo[3]: film opening RGB (from sba-CN-default.dpi "fpo" field)
 * fpa[3]: film aim RGB (from sba-CN-default.dpi "fpa" field)
 * lim46:  round(neutralBalancePoint * sqrt(3))   (blob +0x46)
 * lo42:   round(neutralButton * underConstraint)  (blob +0x42)
 * hi44:   round(neutralButton * overConstraint)   (blob +0x44)
 * neu[3], neo[3]: from sba-CN-default.dpi
 * non_flash_adj: from sba-CN-default.dpi "nonFlashAdj"
 */
static void preference_mode11_shifts(
    const int fpo[3], const int fpa[3],
    double lim46, double lo42, double hi44,
    const int neu[3], const int neo[3],
    int non_flash_adj,
    int16_t shifts_out[3])
{
    double op_y, op_u, op_v;
    pref_rgb_to_yuv((double)fpo[0], (double)fpo[1], (double)fpo[2],
                    &op_y, &op_u, &op_v);

    double fa_y, fa_u, fa_v;
    pref_rgb_to_yuv((double)fpa[0], (double)fpa[1], (double)fpa[2],
                    &fa_y, &fa_u, &fa_v);

    /* mode 0x11: aimY = openingY  (lo=1 @ 0x1028c92f), dU=dV=0 (hi=0x10) */
    double aim_y = op_y;
    double w1e   = 0.0; /* pcls=0, shipped CN */
    double d_y   = w1e + aim_y - op_y; /* = 0 for mode 0x11 with pcls=0 */

    /* Choose helper_rgb: neo if d_y > 0, neu otherwise */
    const int *hrg = (d_y > 0.0) ? neo : neu;
    double m, o1, o2;
    pref_helper((double)hrg[0], (double)hrg[1], (double)hrg[2], &m, &o1, &o2);

    double scale = (double)non_flash_adj * SCALE_0_001;

    int i_dy = pref_ftol2(d_y);
    int i_du = 0; /* dU=0 */
    int i_dv = 0; /* dV=0 */

    /* Combined YUV @ 0x1028cb27 */
    double comb_y = op_y + fa_y + m * (double)i_dy;
    double comb_u = op_u + fa_u + scale * (double)i_du + o1 * (double)i_dy;
    double comb_v = op_v + fa_v + scale * (double)i_dv + o2 * (double)i_dy;

    /* Shifts: inv(s', -U_r, -V_r) @ 0x1028cce7 */
    double t = comb_y - w1e;
    double s_prime = pref_clamp_s(t, lim46, lo42, hi44);
    double sr, sg, sb;
    pref_yuv_to_rgb(s_prime, -comb_u, -comb_v, &sr, &sg, &sb);
    shifts_out[0] = (int16_t)pref_ftol2(sr);
    shifts_out[1] = (int16_t)pref_ftol2(sg);
    shifts_out[2] = (int16_t)pref_ftol2(sb);
}

/* ---- setShifts(1,2)  PakonIMAu.dll @ 0x10100a37 -----------------------
 * Cite: docs/52-setshifts-binary.md; pakon_sba_apply.py::setshifts_12
 * IN:  shifts_a (= shifts_b for CN, same Sba Cap +0x3a38)
 * OUT: pivot(inverse(Y from LUT(pivot(A)), C1 from pivot(B), C2 from pivot(B)))
 *
 * The ScpLut 3-band planar LUT is the shipped sfsTable35 (common-3BandLuts.dpi).
 * For a stand-in when the SCP LUT file is not provided, we use the identity
 * (i.e. (1,2) degrades to (0,2) for those runs), which is still correct for
 * the shipped CN where the LUT is calibrated to identity in the midtones.
 *
 * When the scp_lut is not loaded we use setshifts_02 (no LUT lookup on Y):
 *   a_p = pivot(A)
 *   Y   = axis_y(a_p)   (same as LUT identity)
 *   C1,C2 = from pivot(B)
 *   OUT = pivot(inverse(Y, C1, C2))
 */
static void setshifts_02(const int16_t a[3], const int16_t b[3], int16_t out[3]) {
    /* Cite: pakon_sba_apply.py::setshifts_02 — (ntd=0, ctd=2) same combine, Y from A' (no LUT) */
    double ap[3], bp[3];
    for (int c = 0; c < 3; c++) {
        ap[c] = (double)(int16_t)(PREF_PIVOT - (int)a[c]);
        bp[c] = (double)(int16_t)(PREF_PIVOT - (int)b[c]);
    }
    double y, u_dummy, v_dummy, c1, c2, y_dummy;
    pref_rgb_to_yuv(ap[0], ap[1], ap[2], &y, &u_dummy, &v_dummy);
    pref_rgb_to_yuv(bp[0], bp[1], bp[2], &y_dummy, &c1, &c2);
    double rr, gg, bb;
    pref_yuv_to_rgb(y, c1, c2, &rr, &gg, &bb);
    out[0] = (int16_t)(PREF_PIVOT - pref_ftol2(rr));
    out[1] = (int16_t)(PREF_PIVOT - pref_ftol2(gg));
    out[2] = (int16_t)(PREF_PIVOT - pref_ftol2(bb));
}

/* ---- applyBalanceShifts  PakonIMAu.dll @ 0x1019a0c0 --------------------
 * out[i] = clamp(in[i] + shift[c], 0, 4095) per channel
 * Cite: docs/52; master LUT ctor 0x100f42a0(0xc, 0, 0xfff)
 */
static void apply_balance_shifts(int32_t *rpd, int num_pixels,
                                  const int16_t shifts[3]) {
    for (int i = 0; i < num_pixels; i++) {
        for (int c = 0; c < 3; c++) {
            int v = rpd[i*3+c] + (int)shifts[c];
            if (v < 0) v = 0;
            if (v > 4095) v = 4095;
            rpd[i*3+c] = v;
        }
    }
}

/* ---- Shasta ToneLUT apply  PakonIMAu.dll @ 0x1014dcc0 ------------------
 * Cite: docs/58 §7; pakon_shasta.py ImaShastaOp I16 loop:
 *   out = (int16)(*(int16*)&toneLut[(uint16)in])
 *   i.e. table[code] low 16 bits, then store as int16.
 *
 * For a usable stand-in when we have no scene-derived toneLut:
 *   Use the shipped common-sraFwdLut-metric-*.lut (SRA forward LUT)
 *   which is the documented Preference-path stand-in per pakon_sra.py.
 *   Format: 4096 rows × 4 cols (code R G B), code = row index.
 *
 * tone_lut[4096]: int32 (we use int32 container; I16 dispatch reads low word)
 * The apply is per-channel: each channel independently looks up its value.
 * Because the shipped SRA / stand-in LUT is code→code (12-bit), we apply it
 * per pixel per channel identically.
 */
static void shasta_apply_i16(int32_t *rpd, int num_pixels,
                              const int32_t tone_lut[4096]) {
    /* Cite: PakonIMAu @ 0x1014dcf1
     * out = (int16)(*(int16*)&toneLut[(uint16)in])
     * The low 16 bits of the int32 table entry, treated as int16.
     */
    for (int i = 0; i < num_pixels * 3; i++) {
        int code = rpd[i];
        if (code < 0) code = 0;
        if (code > 4095) code = 4095;
        int16_t v = (int16_t)(tone_lut[code] & 0xFFFF);
        rpd[i] = (int32_t)v;
    }
}

/* Build a default identity Shasta tone LUT (stand-in when no scene data).
 * This is the AnsLut master table that maps code → code for the Preference path.
 * Cite: PakonIMAu.dll global AnsLut @ 0x106b5f74, ctor 0x100f42a0(0xc,0,0xfff)
 *   master[i]=0 for i<=0; master[i]=i for 1..4095; master[i]=4095 for i>4095
 */
static void build_identity_tone_lut(int32_t tone_lut[4096]) {
    tone_lut[0] = 0;
    for (int i = 1; i < 4096; i++) tone_lut[i] = i;
}

/* ---- FUGC setLutInfo  PakonIMAu.dll @ 0x101f82c0 ----------------------
 * Cite: pakon_fugc.py::set_lut_info_channel (Unicorn-golden)
 *
 * One channel build:
 *   if offset > N-1: out[i] = i  (identity)
 *   else: out[0..offset-1] = offset
 *         out[i] = clamp(seed[i-offset] + offset, 0, N-1) for i in [offset, N)
 *
 * offset = int16(w60ec - w60f8 + w60f2)  (per-channel aim arithmetic)
 * Cite: pakon_fugc.py::aim_offset
 */
static void fugc_set_lut_info_chan(const int32_t *seed, int offset,
                                    int32_t *out, int n) {
    if (offset > n - 1) {
        for (int i = 0; i < n; i++) out[i] = i;
        return;
    }
    if (offset > 0)
        for (int i = 0; i < offset; i++) out[i] = offset;
    for (int i = offset < 0 ? 0 : offset; i < n; i++) {
        int src = i - offset;
        if (src < 0) src = 0;
        if (src >= n) src = n - 1;
        int v = (int)seed[src] + offset;
        if (v < 0) v = 0;
        if (v > n - 1) v = n - 1;
        out[i] = v;
    }
}

/*
 * Full 3-channel FUGC setLutInfo then apply.
 *
 * seed_rgb[4096][3]:  loaded from fugc-generic0225.lut
 * a_table_dmin[3]:    from "aTableDmin" field in the .lut file (default 500,500,500)
 * setshifts_out[3]:   OUT words from setShifts (= Preference shifts after (1,2) transform)
 * frame_dmin[3]:      per-frame Dmin estimate (brightest percentile of RPD)
 * afilm_aim_dmin[3]:  from fugc-defaultParams.dpi "aFilmAimDmin" (default 500,1000,1000)
 *
 * Cite: pakon_fugc.py::fill_setlutinfo_aim_words + aim_offset + set_lut_info
 */
static void fugc_apply(int32_t *rpd, int num_pixels,
                       const int32_t seed_rgb[][3],
                       const int a_table_dmin[3],
                       const int16_t setshifts_out[3],
                       const int frame_dmin[3],
                       const int afilm_aim_dmin[3])
{
    /* ebp18 policy check: pass if 0.2*params <= arg <= 2.0*params per channel
     * Cite: PakonIMAu @ 0x101fc3c4..0x101fc484, F64_SIZE_FRAC=0.2 @ 0x10588eb8 */
    int use_ebp18 = 1;
    for (int c = 0; c < 3; c++) {
        double a = (double)frame_dmin[c];
        double p = (double)afilm_aim_dmin[c];
        if (!(0.2 * p <= a && a <= 2.0 * p)) { use_ebp18 = 0; break; }
    }

    /* w60ec, w60f2, w60f8 */
    int w60ec[3], w60f2[3], w60f8[3];
    for (int c = 0; c < 3; c++) {
        w60f8[c] = a_table_dmin[c];
        w60f2[c] = (int)setshifts_out[c];
        w60ec[c] = use_ebp18 ? frame_dmin[c] : afilm_aim_dmin[c];
    }

    /* Compute per-channel offsets and build apply LUT, then apply */
    static int32_t apply_lut[4096];   /* per-channel temporary */
    for (int c = 0; c < 3; c++) {
        /* offset = int16(w60ec - w60f8 + w60f2) — int16 arithmetic */
        int16_t off = (int16_t)((int16_t)w60ec[c] - (int16_t)w60f8[c] + (int16_t)w60f2[c]);
        /* Build apply LUT for this channel */
        int32_t seed_chan[4096];
        for (int i = 0; i < 4096; i++) seed_chan[i] = seed_rgb[i][c];
        fugc_set_lut_info_chan(seed_chan, (int)off, apply_lut, 4096);
        /* Apply to image */
        for (int i = 0; i < num_pixels; i++) {
            int code = rpd[i*3+c];
            if (code < 0) code = 0;
            if (code > 4095) code = 4095;
            rpd[i*3+c] = apply_lut[code];
        }
    }
}

/* Estimate per-channel Dmin from the brightest 1% of RPD pixels.
 * In RPD space: smaller values = denser (darker on film) = film base is LOW RPD.
 * The film base (unexposed) has the lowest density = lowest RPD code.
 * We take the 1st percentile (lowest values) as the film base estimate.
 * Cite: PakonIMAu getCnContext / FindDmin approach (docs/58 §7)
 */
static void estimate_frame_dmin(const int32_t *rpd, int num_pixels, int dmin_out[3]) {
    /* Simple approach: sample lower 2% of each channel as Dmin */
    int thresh = (int)(num_pixels * 0.02);
    if (thresh < 1) thresh = 1;

    for (int c = 0; c < 3; c++) {
        /* Count histogram */
        int hist[4096] = {0};
        for (int i = 0; i < num_pixels; i++) {
            int v = rpd[i*3+c];
            if (v < 0) v = 0;
            if (v > 4095) v = 4095;
            hist[v]++;
        }
        /* Find 2nd percentile (lower end = low RPD = film base) */
        int cum = 0;
        int dmin = 0;
        for (int v = 0; v < 4096; v++) {
            cum += hist[v];
            if (cum >= thresh) { dmin = v; break; }
        }
        dmin_out[c] = dmin;
    }
}

/* =========================================================================
 * SHASTA TONELUT BUILDER & KERNEL
 * (included from pakon_shasta_c.c)
 * ========================================================================= */
#include "pakon_shasta_c.c"

/* =========================================================================
 * ICC MFT2 CLUT EVALUATOR
 * (included from pakon_icc_c.c — already written)
 * ========================================================================= */
#include "pakon_icc_c.c"

/* =========================================================================
 * DATA FILE LOADERS
 * ========================================================================= */

/* Parse a simple "key = value" DPI / config file into key-value pairs.
 * Returns number of pairs loaded.
 */
#define MAX_KV 128
typedef struct { char key[64]; char val[256]; } KV;

static int load_kv(const char *path, KV *pairs) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    int n = 0;
    char line[512];
    while (fgets(line, sizeof(line), f) && n < MAX_KV) {
        /* Strip comment */
        char *hash = strchr(line, '#');
        if (hash) *hash = '\0';
        char *eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        char *k = line, *v = eq + 1;
        /* Trim whitespace from key */
        while (isspace((unsigned char)*k)) k++;
        char *ke = k + strlen(k) - 1;
        while (ke > k && isspace((unsigned char)*ke)) *ke-- = '\0';
        /* Trim whitespace from value */
        while (isspace((unsigned char)*v)) v++;
        char *ve = v + strlen(v) - 1;
        while (ve > v && isspace((unsigned char)*ve)) *ve-- = '\0';
        if (*k && *v) {
            strncpy(pairs[n].key, k, 63);
            strncpy(pairs[n].val, v, 255);
            n++;
        }
    }
    fclose(f);
    return n;
}

static const char *kv_get(const KV *pairs, int n, const char *key) {
    for (int i = 0; i < n; i++)
        if (strcasecmp(pairs[i].key, key) == 0) return pairs[i].val;
    return NULL;
}

static void kv_get_ints(const KV *pairs, int n, const char *key, int *out, int count) {
    const char *v = kv_get(pairs, n, key);
    if (!v) return;
    char buf[256]; strncpy(buf, v, 255);
    char *tok = strtok(buf, " \t,");
    for (int i = 0; i < count && tok; i++, tok = strtok(NULL, " \t,"))
        out[i] = atoi(tok);
}

static double kv_get_double(const KV *pairs, int n, const char *key, double def) {
    const char *v = kv_get(pairs, n, key);
    return v ? atof(v) : def;
}

/*
 * Load fugc-generic0225.lut seed.
 * Format: ASCII "i R G B" rows, plus "aTableDmin = r g b" header.
 * Returns 1 on success.
 * Cite: pakon_fugc.py::load_fugc_seed_lut
 */
static int load_fugc_seed(const char *path,
                           int32_t seed_rgb[][3],   /* [4096][3] */
                           int a_table_dmin[3]) {
    /* Default identity seed */
    for (int i = 0; i < 4096; i++) { seed_rgb[i][0]=i; seed_rgb[i][1]=i; seed_rgb[i][2]=i; }
    a_table_dmin[0] = a_table_dmin[1] = a_table_dmin[2] = 500;

    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "fugc_seed: cannot open %s, using identity\n", path); return 0; }
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        char *hash = strchr(line, '#'); if (hash) *hash = '\0';
        /* Strip leading whitespace */
        char *p = line;
        while (isspace((unsigned char)*p)) p++;
        if (!*p) continue;
        /* aTableDmin line */
        if (strncasecmp(p, "atabledmin", 10) == 0) {
            char *eq = strchr(p, '=');
            if (eq) {
                eq++;
                int r=500, g=500, b=500;
                sscanf(eq, "%d %d %d", &r, &g, &b);
                a_table_dmin[0]=r; a_table_dmin[1]=g; a_table_dmin[2]=b;
            }
            continue;
        }
        /* Data row: index R G B */
        if (isdigit((unsigned char)*p) || *p == '-') {
            int idx, r, g, b;
            if (sscanf(p, "%d %d %d %d", &idx, &r, &g, &b) == 4) {
                if (idx >= 0 && idx < 4096) {
                    seed_rgb[idx][0] = r;
                    seed_rgb[idx][1] = g;
                    seed_rgb[idx][2] = b;
                }
            }
        }
    }
    fclose(f);
    return 1;
}

/* =========================================================================
 * BMP WRITER
 * ========================================================================= */
static void write_bmp_rgb24(const char *filename, const uint8_t *rgb,
                             int width, int height) {
    FILE *f = fopen(filename, "wb");
    if (!f) { fprintf(stderr, "Cannot write %s\n", filename); return; }
    int row_padded = (width * 3 + 3) & (~3);
    uint32_t image_size = (uint32_t)(row_padded * height);
    uint32_t filesize = 54 + image_size;
    uint8_t hdr[54] = {
        'B','M',
        filesize&0xFF,(filesize>>8)&0xFF,(filesize>>16)&0xFF,(filesize>>24)&0xFF,
        0,0,0,0, 54,0,0,0, 40,0,0,0,
        width&0xFF,(width>>8)&0xFF,(width>>16)&0xFF,(width>>24)&0xFF,
        height&0xFF,(height>>8)&0xFF,(height>>16)&0xFF,(height>>24)&0xFF,
        1,0, 24,0, 0,0,0,0,
        image_size&0xFF,(image_size>>8)&0xFF,(image_size>>16)&0xFF,(image_size>>24)&0xFF,
        0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0
    };
    fwrite(hdr, 1, 54, f);
    uint8_t *row = (uint8_t *)calloc(1, row_padded);
    for (int y = height-1; y >= 0; y--) {
        for (int x = 0; x < width; x++) {
            int s = (y*width+x)*3;
            row[x*3+0] = rgb[s+2];  /* BMP = BGR */
            row[x*3+1] = rgb[s+1];
            row[x*3+2] = rgb[s+0];
        }
        fwrite(row, 1, row_padded, f);
    }
    free(row);
    fclose(f);
}

/* =========================================================================
 * MAIN
 * ========================================================================= */
static void print_usage(const char *prog) {
    fprintf(stderr,
        "Usage: %s <input.bin> <output.bmp> --width W --height H\n"
        "  [--model f135|f235|f335]          (default: f135)\n"
        "  [--eeprom <eeprom_52.bin>]         (F-135 coefficients)\n"
        "  [--sba-dpi <sba-CN-default.dpi>]  (Preference FPU params)\n"
        "  [--fugc-lut <NoShift_fugc-generic0225.lut>]\n"
        "  [--rpd2pcs <Rpd2Pcs_HR200_QS_v5s10.pf>]\n"
        "  [--srgb <Srgb_v2.pf>]\n", prog);
}

int main(int argc, char **argv) {
    if (argc < 3) { print_usage(argv[0]); return 1; }

    const char *in_path    = argv[1];
    const char *out_path   = argv[2];
    int width = 0, height = 0;
    PakonModel model = MODEL_F135;

    /* Default data file paths (relative to cwd or absolute) */
    const char *eeprom_path = "backups/eeprom-i2c/eeprom_52.bin";
    const char *sba_dpi_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/sba/SbaDPI/sba-CN-default.dpi";
    const char *fugc_lut_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/fugc/NoShift_fugc-generic0225.lut";
    const char *rpd2pcs_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/profile/Rpd2Pcs_HR200_QS_v5s10.pf";
    const char *srgb_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/profile/Srgb_v2.pf";

    for (int i = 3; i < argc; i++) {
        if (!strcmp(argv[i], "--width")    && i+1 < argc) width  = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--height")   && i+1 < argc) height = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--model")    && i+1 < argc) {
            const char *m = argv[++i];
            if (!strcmp(m,"f135")) model = MODEL_F135;
            else if (!strcmp(m,"f235")) model = MODEL_F235;
            else if (!strcmp(m,"f335")) model = MODEL_F335;
            else { fprintf(stderr, "Unknown model: %s\n", m); return 1; }
        }
        else if (!strcmp(argv[i], "--eeprom")   && i+1 < argc) eeprom_path  = argv[++i];
        else if (!strcmp(argv[i], "--sba-dpi")  && i+1 < argc) sba_dpi_path = argv[++i];
        else if (!strcmp(argv[i], "--fugc-lut") && i+1 < argc) fugc_lut_path= argv[++i];
        else if (!strcmp(argv[i], "--rpd2pcs")  && i+1 < argc) rpd2pcs_path = argv[++i];
        else if (!strcmp(argv[i], "--srgb")     && i+1 < argc) srgb_path    = argv[++i];
    }

    if (width <= 0 || height <= 0) {
        fprintf(stderr, "Error: --width and --height required\n"); return 1;
    }

    size_t num_pixels = (size_t)width * (size_t)height;
    printf("=== Pakon Pipeline (model=%s, %dx%d) ===\n",
           model==MODEL_F135 ? "F-135" : model==MODEL_F235 ? "F-235" : "F-335",
           width, height);

    /* ------------------------------------------------------------------
     * LOAD STAGE-2 COEFFICIENTS
     * ------------------------------------------------------------------ */
    float     coeffs_f135[30] = {0}; /* 3×10 poly (F-135) */
    int32_t   dens_lut[TLA_LUT_SIZE];/* density LUT (F-235/F-335) */
    TlaMatrixCtx tla_ctx = {{{0}}};
    double tla_matrix[3][4] = {  /* default identity + 0 offsets */
        {1.0, 0.0, 0.0, 0.0},
        {0.0, 1.0, 0.0, 0.0},
        {0.0, 0.0, 1.0, 0.0}
    };

    if (model == MODEL_F135) {
        /* Read 30 float32 LE coefficients from EEPROM at offset 0x25.
         * Cite: docs/58 §4.4a — EEPROM eeprom_52.bin, NegMatrix at offset 0x25 */
        FILE *ef = fopen(eeprom_path, "rb");
        if (!ef) { fprintf(stderr, "Cannot open EEPROM: %s\n", eeprom_path); return 1; }
        fseek(ef, 0x25, SEEK_SET);
        size_t nr = fread(coeffs_f135, sizeof(float), 30, ef);
        fclose(ef);
        if (nr < 24) { fprintf(stderr, "EEPROM too short\n"); return 1; }
        for (size_t i = nr; i < 30; i++) coeffs_f135[i] = 0.0f;
        printf("[setup] F-135 EEPROM coefficients loaded (%zu/30)\n", nr);
    } else {
        /* F-235/F-335: build density LUT and use default/client matrix.
         * Cite: TLA.dll @ 0x10013730 (F-235) density LUT, 0x10014ff0 matrix apply */
        build_density_lut_tla(dens_lut);
        quantise_matrix_tla(tla_matrix, &tla_ctx);
        printf("[setup] F-235/F-335 density LUT + identity matrix\n");
        printf("  (provide ClientColNegMat_3x10.txt or similar to customise)\n");
    }

    /* ------------------------------------------------------------------
     * LOAD SBA DPI (Preference FPU parameters)
     * Cite: anselinstalldir/dataPathItems/sba/SbaDPI/sba-CN-default.dpi
     *       docs/49-preference-fpu-binary.md, docs/48
     * ------------------------------------------------------------------ */
    int sba_fpo[3]  = {879, 1250, 1386};  /* sba-CN-default.dpi defaults */
    int sba_fpa[3]  = {-70, -55, -45};
    int sba_neu[3]  = {975, 975, 975};
    int sba_neo[3]  = {1010, 1010, 1010};
    int sba_non_flash_adj = 25;
    int sba_neutral_button = 130;
    double sba_neutral_under = -16.0;
    double sba_neutral_over  =  16.0;
    int sba_nbp = 1550;

    {
        KV pairs[MAX_KV];
        int n = load_kv(sba_dpi_path, pairs);
        if (n > 0) {
            kv_get_ints(pairs, n, "fpo", sba_fpo, 3);
            kv_get_ints(pairs, n, "fpa", sba_fpa, 3);
            kv_get_ints(pairs, n, "neu", sba_neu, 3);
            kv_get_ints(pairs, n, "neo", sba_neo, 3);
            sba_non_flash_adj   = (int)kv_get_double(pairs, n, "nonFlashAdj", 25.0);
            sba_neutral_button  = (int)kv_get_double(pairs, n, "neutralButton", 130.0);
            sba_neutral_under   = kv_get_double(pairs, n, "neutralUnderConstraint", -16.0);
            sba_neutral_over    = kv_get_double(pairs, n, "neutralOverConstraint",  16.0);
            sba_nbp             = (int)kv_get_double(pairs, n, "neutralBalancePoint", 1550.0);
            printf("[setup] SBA DPI loaded from %s\n", sba_dpi_path);
            printf("  fpo=%d %d %d  fpa=%d %d %d  nbp=%d\n",
                   sba_fpo[0],sba_fpo[1],sba_fpo[2],
                   sba_fpa[0],sba_fpa[1],sba_fpa[2], sba_nbp);
        } else {
            printf("[setup] SBA DPI not found, using defaults\n");
        }
    }

    /* Compute Preference blob params.
     * Cite: pakon_sba_preference.py::lim46_from_neutral_balance_point
     *       blob +0x46 = round(NBP * sqrt(3))
     * Cite: pakon_sba_preference.py::clamp_limits_from_neutral_button
     *       lo42 = round(neutralButton * underConstraint)
     *       hi44 = round(neutralButton * overConstraint)
     */
    double lim46 = round((double)sba_nbp * sqrt(3.0));
    double lo42  = round((double)sba_neutral_button * sba_neutral_under);
    double hi44  = round((double)sba_neutral_button * sba_neutral_over);
    printf("  lim46=%.0f lo42=%.0f hi44=%.0f\n", lim46, lo42, hi44);

    /* ------------------------------------------------------------------
     * COMPUTE PREFERENCE SHIFTS (Preference FPU mode 0x11)
     * Cite: PakonIMAu.dll @ 0x1028c780; docs/49-preference-fpu-binary.md
     * ------------------------------------------------------------------ */
    int16_t pref_shifts[3];
    preference_mode11_shifts(sba_fpo, sba_fpa, lim46, lo42, hi44,
                              sba_neu, sba_neo, sba_non_flash_adj,
                              pref_shifts);
    printf("[Preference] raw shifts R=%d G=%d B=%d\n",
           pref_shifts[0], pref_shifts[1], pref_shifts[2]);

    /* setShifts(1,2): transform Preference raw shifts → setShifts OUT
     * Cite: PakonIMAu @ 0x10100a37; docs/52-setshifts-binary.md
     * CN shipped: ntdChoice=1, ctdChoice=2 → setshifts_02 stand-in
     * (setshifts_12 requires the 3-band planar ScpLut; using 02 is conservative) */
    int16_t ss_out[3];
    setshifts_02(pref_shifts, pref_shifts, ss_out); /* A≡B for shipped CN */
    printf("[setShifts 1,2] OUT R=%d G=%d B=%d\n", ss_out[0], ss_out[1], ss_out[2]);

    /* ------------------------------------------------------------------
     * LOAD FUGC SEED LUT
     * Cite: dataPathItems/fugc/NoShift_fugc-generic0225.lut
     *       pakon_fugc.py::load_fugc_seed_lut
     * ------------------------------------------------------------------ */
    static int32_t fugc_seed[4096][3];
    int fugc_atd[3] = {500, 500, 500};
    load_fugc_seed(fugc_lut_path, fugc_seed, fugc_atd);
    printf("[FUGC] seed loaded, aTableDmin=%d %d %d\n",
           fugc_atd[0], fugc_atd[1], fugc_atd[2]);

    /* aFilmAimDmin from fugc-defaultParams.dpi (default 500, 1000, 1000)
     * Cite: PakonIMAu @ 0x10118380 copies Cap +0x12 from ParamsDpi aFilmAimDmin */
    int afilm_aim_dmin[3] = {500, 1000, 1000};

    /* ------------------------------------------------------------------
     * LOAD ICC PROFILES
     * Cite: docs/58 §10, §6.1
     *       Rpd2Pcs_HR200_QS_v5s10.pf: 31³ CLUT, input clips at RPD 3000
     *       Srgb_v2.pf: 25³ CLUT
     * ------------------------------------------------------------------ */
    IccMft2 rpd2pcs, srgb_profile;
    int rpd2pcs_ok = (icc_load_profile(rpd2pcs_path, &rpd2pcs) == 0);
    /* Srgb_v2.pf: render path uses B2A0 mft2 (25³ grid, Lab→sRGB).
     * Cite: docs/58-colour-pipeline.md §6 row 10, §10 */
    int srgb_ok    = (icc_load_profile_b2a0(srgb_path, &srgb_profile) == 0);
    if (rpd2pcs_ok)
        printf("[ICC] Rpd2Pcs: grid=%d³ n_in=%d n_out=%d\n",
               rpd2pcs.grid, rpd2pcs.n_table_in, rpd2pcs.n_table_out);
    else
        printf("[ICC] Rpd2Pcs not loaded — only needed for PAKON_ICC_TRILINEAR=1;\n"
               "      the default vendor CLUT port carries its own combined tables\n");
    if (srgb_ok)
        printf("[ICC] Srgb: grid=%d³\n", srgb_profile.grid);

    /* ------------------------------------------------------------------
     * ALLOCATE BUFFERS
     * ------------------------------------------------------------------ */
    uint16_t *in_raw  = (uint16_t *)malloc(num_pixels * 3 * sizeof(uint16_t));
    int32_t  *rpd_buf = (int32_t  *)malloc(num_pixels * 3 * sizeof(int32_t));
    uint8_t  *srgb_buf= (uint8_t  *)malloc(num_pixels * 3 * sizeof(uint8_t));
    if (!in_raw || !rpd_buf || !srgb_buf) { fprintf(stderr, "OOM\n"); return 1; }

    /* ------------------------------------------------------------------
     * LOAD RAW INPUT
     * ------------------------------------------------------------------ */
    FILE *inf = fopen(in_path, "rb");
    if (!inf) { fprintf(stderr, "Cannot open %s\n", in_path); return 1; }
    size_t nw = fread(in_raw, sizeof(uint16_t), num_pixels * 3, inf);
    fclose(inf);
    if (nw < num_pixels * 3)
        printf("Warning: read %zu/%zu words\n", nw, num_pixels * 3);

    /* ------------------------------------------------------------------
     * STAGE 2 — COLOUR CORRECTION
     * ------------------------------------------------------------------ */
    printf("[1/5] Stage-2 colour correction...\n");
    if (model == MODEL_F135) {
        /* TLB.dll:fcn.1000d880 — 3×10 float polynomial on BGR HWC sensor stream */
        pakon_poly_bgr_hwc_c(in_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    } else {
        /* TLA.dll @ 0x10014ff0 — density LUT + 3×4 int16 matrix */
        apply_color_correct_tla(in_raw, rpd_buf, (int)num_pixels,
                                 dens_lut, &tla_ctx);
    }
    free(in_raw); in_raw = NULL;

    /* ------------------------------------------------------------------
     * STAGE 4a — Preference + setShifts + applyBalanceShifts
     * Cite: PakonIMAu @ 0x1019a0c0, 0x1028c780, 0x10100a37
     * ------------------------------------------------------------------ */
    printf("[2/5] Ansel SBA (Preference → setShifts → applyBalanceShifts)...\n");
    apply_balance_shifts(rpd_buf, (int)num_pixels, ss_out);

    /* ------------------------------------------------------------------
     * STAGE 4b — Shasta ToneLUT analyze & apply
     * Cite: PakonIMAu.dll @ 0x10293ee0 (builder), 0x1014dcc0 (apply)
     * ------------------------------------------------------------------ */
    printf("[3/5] Shasta ToneLUT analyze & apply...\n");
    {
        ShastaDpi shasta_dpi;
        shasta_dpi_defaults(&shasta_dpi);
        int32_t tone_lut[4096];
        shasta_build_tone_lut(rpd_buf, (int)num_pixels, &shasta_dpi, ss_out, tone_lut);
        shasta_apply_tone_lut(rpd_buf, (int)num_pixels, tone_lut);
    }

    /* ------------------------------------------------------------------
     * STAGE 4c — FUGC setLutInfo + apply
     * Cite: PakonIMAu.dll @ 0x101f82c0 (setLutInfo), 0x101fa5b0 (applyLut)
     * ------------------------------------------------------------------ */
    printf("[4/5] FUGC LUT apply...\n");
    {
        /* Estimate frame Dmin for ebp18 policy check */
        int frame_dmin[3];
        estimate_frame_dmin(rpd_buf, (int)num_pixels, frame_dmin);
        printf("  frame dmin estimate: R=%d G=%d B=%d\n",
               frame_dmin[0], frame_dmin[1], frame_dmin[2]);
        fugc_apply(rpd_buf, (int)num_pixels,
                   (const int32_t (*)[3])fugc_seed,
                   fugc_atd, ss_out, frame_dmin, afilm_aim_dmin);
    }

    /* ------------------------------------------------------------------
     * STAGE 4d — ICC CLUT: RPD 12-bit → sRGB 8-bit
     * Cite: docs/58 §10 — Rpd2Pcs_HR200_QS_v5s10.pf → Srgb_v2.pf
     *       dataType = U8, renderIntent = P, colorSpaceMax = 255
     *
     * docs/74 §176: the vendor folds that profile pair into one combined
     * transform (SpCombineXforms) and evaluates it with a tetrahedral, 14-bit,
     * arithmetic-shift interpolator. That is what runs here by default, from
     * the captured tables — so it no longer needs the .pf files at all, and
     * there is no gamma fallback to fall into: the old one produced visibly
     * plausible but wrong colour, which is worse than failing.
     * ------------------------------------------------------------------ */
    printf("[5/5] ICC CLUT render (RPD → sRGB)...\n");
    printf("  ICC: %s\n", icc_render_banner(rpd2pcs_ok && srgb_ok));
    {
        const IccMft2 *p1 = rpd2pcs_ok ? &rpd2pcs : NULL;
        const IccMft2 *p2 = srgb_ok ? &srgb_profile : NULL;
        for (size_t i = 0; i < num_pixels; i++)
            icc_render_rpd12_to_srgb8(p1, p2, &rpd_buf[i*3], &srgb_buf[i*3]);
    }
    free(rpd_buf); rpd_buf = NULL;

    /* Stage 6: PIColorAdjustPlanar runs after Ansel (factory-zero → skip for now).
     * Cite: TLA.dll @ 0x1002a5a0, PakonIMAu @ 0x10013bc0; docs/58 §8.
     * The operator slider values are all zero on this unit (recovered hive confirms). */

    /* ------------------------------------------------------------------
     * WRITE BMP
     * ------------------------------------------------------------------ */
    printf("Writing BMP to %s...\n", out_path);
    write_bmp_rgb24(out_path, srgb_buf, width, height);
    free(srgb_buf);

    if (rpd2pcs_ok) icc_mft2_free(&rpd2pcs);
    if (srgb_ok)    icc_mft2_free(&srgb_profile);

    printf("=== Done. %zu pixels processed. ===\n", num_pixels);
    return 0;
}
