/*
 * pakon_kcms_clut_c.c — C port of the Kodak CMM's 3-D CLUT interpolator,
 * ``kodakcms.dll`` ``fcn.10018160`` (md5 e4c8064a9dd3c3a5541d74b00a730e53).
 *
 * WHY THIS EXISTS
 * ===============
 * The other evaluator in this tree, ``pakon_icc_c.c``, is a **trilinear**,
 * double-precision, round-to-nearest ICC mft2 evaluator. docs/74 §176 drove
 * the real vendor CMM under Wine and established that the vendor is none of
 * those three things: it is **tetrahedral**, at **14-bit integer** precision,
 * with an **arithmetic shift** (truncation toward -inf) rather than rounding.
 * §176's negative controls measured what each wrong choice costs on a 32³
 * lattice of the input domain:
 *
 *     trilinear instead of tetrahedral   2037 / 98304 samples differ, max |d| 3
 *     round-to-nearest instead of SAR    1200 / 98304 samples differ, max |d| 1
 *
 * so ``pakon_icc_c.c``'s output is provably not the vendor's. This file is the
 * arithmetic that is.
 *
 * THE REFERENCE
 * =============
 * ``tools/ansel/python-pipeline/pakon_kcms_clut.py`` — bit-exact against the
 * real DLL over the **entire** u8 RGB input domain, all 16,777,216 triples /
 * 50,331,648 channel samples, zero differences
 * (``pakon_kcms_clut_golden.py``, docs/74 §176). This file is a transcription
 * of that module, and ``tools/test_kcms_clut_ports.py`` re-proves the
 * transcription exhaustively over the same 16,777,216 triples.
 *
 * THE ROUTINE, per pixel
 * ======================
 *     offR, wR = idx[0][r]        (8-byte records: i32 byte offset, i32 weight)
 *     offG, wG = idx[1][g]
 *     offB, wB = idx[2][b]
 *     base = offR + offG + offB
 *
 *     sort {wR, wG, wB} descending -> (w0, w1, w2); which of the six orderings
 *     holds selects one of six tetrahedra and with it two intermediate corner
 *     byte offsets (Pa, Pb)
 *
 *     for ch in 0, 1, 2:
 *         c = base + 2*ch
 *         A = clut[c];  C = clut[c + Pa];  B = clut[c + Pb];  D = clut[c + RGB]
 *         t = (D - B)*w2 + (C - A)*w0 + (B - C)*w1        (signed 32-bit)
 *         out[ch] = otab[ch][ 4*A + (t >> 14) ]           (SAR, i.e. floor)
 *
 * The grid index and the fraction are NOT computed per pixel: they are read
 * out of the precomputed 3 x 256 table at grid+0x8c, which also absorbs the
 * input curve. The 14-bit interpolation result is mapped to u8 through a
 * per-channel 16384-entry byte table (grid+0x154), so the output transfer
 * curve is exact rather than interpolated.
 *
 * Ranges, measured over the whole u8 domain (not assumed):
 *   CLUT word index   0 .. 89372   (table is 89373 words)  — always in range
 *   t                 -10,513,533 .. 41,730,541            — never overflows i32
 *   otab index        1024 .. 16152 (table is 16384)       — never negative
 * so no clamp is needed anywhere, and adding one would be a deviation from
 * the vendor rather than safety.
 */

#ifndef PAKON_KCMS_CLUT_C_INCLUDED
#define PAKON_KCMS_CLUT_C_INCLUDED

#include <math.h>
#include <stddef.h>
#include <stdint.h>

#include "pakon_kcms_clut_tables.h"

/*
 * Arithmetic shift right by 14, i.e. floor(v / 16384), written so it does not
 * depend on the implementation-defined behaviour of ``>>`` on a negative
 * signed value. Every mainstream compiler emits a plain SAR for this.
 */
static inline int32_t kcms_sar14(int32_t v) {
    return v >= 0 ? (v >> 14) : -(int32_t)((-(int64_t)v + 16383) >> 14);
}

/*
 * ``fcn.10018160`` on one interleaved RGB u8 triple.
 *
 * The six-way branch is the disassembly's own three signed compares in its own
 * order: 0x100182a4 cmp wR,wG / 0x100182ac cmp wG,wB / 0x100182c9 cmp wR,wB.
 * Ties go the way the vendor's ``jg``/``jle`` pairs send them — note the
 * asymmetry (``wR > wG`` but ``wB >= wR``); this is load-bearing and is what
 * the exhaustive test checks.
 */
static void kcms_clut_eval_u8(const uint8_t in[3], uint8_t out[3]) {
    const int32_t off_r = kcms_idx[0][in[0]][0], w_r = kcms_idx[0][in[0]][1];
    const int32_t off_g = kcms_idx[1][in[1]][0], w_g = kcms_idx[1][in[1]][1];
    const int32_t off_b = kcms_idx[2][in[2]][0], w_b = kcms_idx[2][in[2]][1];
    const int32_t base = off_r + off_g + off_b;

    int32_t w0, w1, w2, pa, pb;
    if (w_r > w_g) {
        if (w_g > w_b) {                    /* wR > wG > wB */
            w0 = w_r; w1 = w_g; w2 = w_b; pa = KCMS_OFF_R; pb = KCMS_OFF_RG;
        } else if (w_r > w_b) {             /* wR > wB >= wG */
            w0 = w_r; w1 = w_b; w2 = w_g; pa = KCMS_OFF_R; pb = KCMS_OFF_RB;
        } else {                            /* wB >= wR > wG */
            w0 = w_b; w1 = w_r; w2 = w_g; pa = KCMS_OFF_B; pb = KCMS_OFF_RB;
        }
    } else {
        if (w_g > w_b) {
            if (w_r > w_b) {                /* wG >= wR > wB */
                w0 = w_g; w1 = w_r; w2 = w_b; pa = KCMS_OFF_G; pb = KCMS_OFF_RG;
            } else {                        /* wG > wB >= wR */
                w0 = w_g; w1 = w_b; w2 = w_r; pa = KCMS_OFF_G; pb = KCMS_OFF_GB;
            }
        } else {                            /* wB >= wG >= wR */
            w0 = w_b; w1 = w_g; w2 = w_r; pa = KCMS_OFF_B; pb = KCMS_OFF_GB;
        }
    }

    for (int ch = 0; ch < 3; ch++) {
        const int32_t c = base + 2 * ch;
        const int32_t A = (int32_t)kcms_clut[c >> 1];
        const int32_t C = (int32_t)kcms_clut[(c + pa) >> 1];
        const int32_t B = (int32_t)kcms_clut[(c + pb) >> 1];
        const int32_t D = (int32_t)kcms_clut[(c + KCMS_OFF_RGB) >> 1];
        const int32_t t = (D - B) * w2 + (C - A) * w0 + (B - C) * w1;
        out[ch] = kcms_otab[ch][4 * A + kcms_sar14(t)];
    }
}

/*
 * 12-bit RPD -> u8, the encode the vendor's own profile-Rpd2Srgb.dpi implies
 * (dataType U8, colorSpaceMax 255) and the Python path performs in
 * ``pakon_ansel.rpd12_to_icc_u8``:
 *
 *     u8 = clip(rint(code * 255 / 4095), 0, 255)
 *
 * ``np.rint`` is round-half-to-even, and so is C's ``rint`` under the default
 * FE_TONEAREST rounding mode, on the identical double expression
 * ``code * (255.0/4095.0)``. This is NOT ``(int)(x + 0.5)``, which is what
 * ``pakon_icc_c.c``'s ``rpd12_to_u16`` and the Go ``IccRpd12ToSrgb8Depth`` do.
 * For integer codes 0..4095 no exact half-way value actually arises (255/4095
 * is not representable in binary, and even in exact arithmetic 17*code/273
 * is never an odd multiple of 1/2), so the tie rule is not load-bearing here —
 * it is written this way to match the reference expression rather than to
 * approximate it.
 *
 * Note a representational difference that this cannot close: on the Python
 * path ``rpd12`` at this point is float64 straight out of the tone chain,
 * whereas the C pipeline carries int32 RPD. That is a property of the two
 * pipelines, not of this encode.
 */
static uint8_t kcms_rpd12_to_u8(int32_t rpd12) {
    if (rpd12 <= 0) return 0;
    if (rpd12 >= 4095) return 255;
    const double v = rint((double)rpd12 * (255.0 / 4095.0));
    if (v <= 0.0) return 0;
    if (v >= 255.0) return 255;
    return (uint8_t)v;
}

/*
 * The whole ICC hop as the vendor performs it: 12-bit RPD in, 8-bit sRGB out.
 * This replaces ``icc_rpd12_to_srgb8`` (pakon_icc_c.c), which ran a trilinear
 * double-precision two-profile chain instead. It needs no .pf files at all —
 * SpCombineXforms already folded both profiles into the shipped tables.
 */
static void kcms_rpd12_to_srgb8(const int32_t rpd[3], uint8_t srgb_out[3]) {
    uint8_t u8[3];
    for (int c = 0; c < 3; c++) u8[c] = kcms_rpd12_to_u8(rpd[c]);
    kcms_clut_eval_u8(u8, srgb_out);
}

#endif /* PAKON_KCMS_CLUT_C_INCLUDED */
