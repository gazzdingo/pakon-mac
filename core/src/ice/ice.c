/* Digital ICE (DMLDICELib.dll DMLDICEProcess), RE 44. This file: the tables Begin builds (0x10001380), the statistics pass
 * (0x10001550 / 0x10001720), the weight map (0x10001220), the per-routine setup (0x100021e0..), the defect test and the
 * scan order. The per-pixel corrections are the 88 generated routines in variants.c (lab/ice/gen_c.py).
 * Arithmetic: x87 at PC53 is IEEE double, with a float32 store wherever Kodak has an fst dword (RE 44 sec. 7). */
#include "pakon/ice.h"
#include <math.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>
#include "ice/ice_internal.h"

#define M14 16383.0

static inline double f32(double x) { return (double)(float)x; }

/* quadrant sums, Kodak's addition order, index = 8 * row + col (RE 44 sec. 2.3) */
static const uint8_t SUMQ[4][16] = {
    { 27, 26, 25, 24, 19, 18, 17, 16, 11, 10, 9, 8, 3, 2, 1, 0 },
    { 31, 30, 29, 28, 23, 22, 21, 20, 15, 14, 13, 12, 7, 6, 5, 4 },
    { 59, 58, 57, 56, 51, 50, 49, 48, 43, 42, 41, 40, 35, 34, 33, 32 },
    { 63, 62, 61, 60, 55, 54, 53, 52, 47, 46, 45, 44, 39, 38, 37, 36 } };

static double qsum(const double *a, const uint8_t *idx) {
    double s = a[idx[0]];
    for (int i = 1; i < 16; i++) s = s + a[idx[i]];
    return s * 0.0625;
}

/* 0x10001550: m (+0x28ac) and c0 (+0x28b0). *c0_nan = 1 when no sample was valid (x87 default NaN). */
static void statistics(const pki_ctx *t, const uint16_t *R, const uint16_t *I, size_t stride, int step, int x0, int y0,
                       int rw, int rh, double *m_out, double *c0_out, int *c0_nan) {
    const int npx = (rw / 8) / step, npy = (rh / 8) / step;
    double sw = 0, swr = 0, sLR = 0, sLI = 0, sv2 = 0;
    const double q7 = (double)0.70710677f, r_hi = (double)0.425f;
    for (int py = 0; py < npy; py++) {
        uint32_t csum = 0;                                   /* per patch row (one call of 0x10001720) */
        for (int px = 0; px < npx; px++) {
            int ok = 1;
            double LR[64] = { 0 }, LI[64] = { 0 };
            for (int r = 0; r < 8; r++) {
                const size_t y = (size_t)(y0 + (py * 8 + r) * step);
                for (int c = 0; c < 8; c++) {
                    const size_t x = (size_t)(x0 + (px * 8 + c) * step);
                    const uint32_t v = I[y * stride + x];
                    if (!(v > 0)) { ok = 0; continue; }       /* v > 0.007335f */
                    csum += v;
                    const double li = (double)t->L[v], lr = (double)t->L[R[y * stride + x]];
                    LI[r * 8 + c] = li;
                    LR[r * 8 + c] = lr;
                    const double v2 = (double)(int32_t)(v * v);   /* imul 32 bit, fild dword */
                    sLR = lr * v2 + sLR;
                    sLI = li * v2 + sLI;
                    sv2 = v2 + sv2;
                }
            }
            if (!ok) continue;
            const double qR0 = qsum(LR, SUMQ[0]);              /* stays on the x87 stack, not rounded */
            const double qR[4] = { qR0, f32(qsum(LR, SUMQ[1])), f32(qsum(LR, SUMQ[2])), f32(qsum(LR, SUMQ[3])) };
            const double qI[4] = { f32(qsum(LI, SUMQ[0])), f32(qsum(LI, SUMQ[1])), f32(qsum(LI, SUMQ[2])), f32(qsum(LI, SUMQ[3])) };
            const double mR = f32((((qR[3] + qR[2]) + qR[1]) + qR0) * 0.25);
            const double mI = f32((((qI[3] + qI[2]) + qI[1]) + qI[0]) * 0.25);
            double dR[4], dI[4];
            dR[0] = f32(qR0 - mR);
            dI[0] = qI[0] - mI;                                 /* unrounded */
            for (int k = 1; k < 4; k++) { dR[k] = f32(qR[k] - mR); dI[k] = f32(qI[k] - mI); }
            for (int k = 0; k < 4; k++) {
                if (dR[k] == 0.0) continue;
                const double ratio = dI[k] / dR[k], r32 = f32(ratio);
                if (ratio < -0.125 || r32 > r_hi) continue;     /* -0.125 on the unrounded quotient, 0.425f on the f32 */
                const double q = dR[k] * q7, S = (double)csum;
                const double W = q * ((S * S) * q);
                sw = W + sw;
                swr = r32 * W + swr;
            }
        }
    }
    const double m = sw == 0.0 ? 0.0 : f32(swr / sw);
    *m_out = m;
    *c0_nan = 0;
    if (sv2 == 0.0) { *c0_nan = 1; *c0_out = 0.0; return; }
    const double a = sLI / sv2, b = sLR / sv2, one_m = 1.0 - m;
    const double inv = one_m != 0.0 ? 1.0 / one_m : (double)INFINITY;
    *c0_out = f32((a - b * m) * inv);
}

int pk_ice_available(void) { return 1; }

pk_status pk_ice_apply(uint16_t *r, uint16_t *g, uint16_t *b, uint16_t *ir, int w, int h, size_t stride,
                       const pk_ice_opts *opts, pk_ice_stats *out) {
    static const pk_ice_opts tlb = { 0 };
    if (!opts) opts = &tlb;
    if (!r || !g || !b || !ir || w < 1 || h < 1 || stride < (size_t)w) return PK_E_ARG;
    if (opts->bits != 0 && opts->bits != 14) return PK_E_UNSUPPORTED;
    const int roi = opts->roi != 0;
    const int x0 = roi ? opts->x0 : 0, y0 = roi ? opts->y0 : 0, x1 = roi ? opts->x1 : w - 1, y1 = roi ? opts->y1 : h - 1;
    if (x0 < 0 || y0 < 0 || x1 < x0 || y1 < y0 || x1 >= w || y1 >= h) return PK_E_ARG;
    const int rw = x1 - x0 + 1, rh = y1 - y0 + 1;
    const int step = (int64_t)w * h < 1000000 ? 1 : 4;            /* of the IMAGE (vtable +0x14); Kodak's product is 32 bit, so it differs only from 4 gigapixels */
    if (rh / 8 / step == 0 || rw <= 3) return PK_E_ARG;           /* Kodak crashes: npy == 0, interior column count */
    if (w == INT_MAX || h == INT_MAX || stride > (size_t)PTRDIFF_MAX / (size_t)h) return PK_E_ARG;   /* int / offset overflow */

    pki_ctx ctx, *s = &ctx;
    pki_tables_init();
    s->L = pki_log; s->ahi = pki_ahi; s->alo = pki_alo;
    const pki_ctx *t = s;

    double m, c0;
    int c0_nan;
    statistics(t, r, ir, stride, step, x0, y0, rw, rh, &m, &c0, &c0_nan);

    /* weight map, 0x10001220 */
    const double a = (double)t->L[(int32_t)(M14 * (double)0.606f)] - (double)t->L[16383];
    const double X = a - ((double)t->L[(int32_t)(M14 * (double)0.99f)] - (double)t->L[16383]);
    double A, B;
    if (X == 0.0) { A = -f32(M14); B = 1.0; }
    else { const double inv = 1.0 / X; A = f32(inv); B = f32(inv * a); }

    /* per routine setup, 0x100021e0.. */
    const double m1 = m != 1.0 ? m : (double)0.99999f;
    const double k = f32(1.0 / (1.0 - m1));
    const double thr = m > (double)0.035f ? pki_thr_high_slope : pki_thr_low_slope;      /* RE 44 sec. 2.4 */
    s->m = m; s->c0 = c0; s->A = A; s->B = B;
    s->gain_cls = m >= (double)0.035f;

    int64_t nd = 0;
    if (!c0_nan) {
        uint16_t *const P[4] = { r, g, b, ir };
        const pki_variants *tab = pki_variant_table[(w >= 2000 ? 1 : 0) + (roi ? 2 : 0)];
        const int hs = (rh >> 1) + (rh & 1);                          /* main thread [0, hs), worker [hs, rh) */
        for (int pass = 0; pass < 2; pass++) {                /* the worker half first (RE 44 sec. 6.1) */
            const int worker = pass == 0;                      /* tab[0] = main, tab[1] = worker */
            const int ya = worker ? hs : 0, yb = worker ? rh : hs;
            const pki_variants *v = &tab[worker ? 1 : 0];
            for (int ry = ya; ry < yb; ry++) {
                const int y = y0 + ry;
                const pki_fn *row = NULL;
                if (worker) row = ry == rh - 2 ? v->a : ry == rh - 1 ? v->b : NULL;
                else row = ry == 0 ? v->a : ry == 1 ? v->b : NULL;
                const uint16_t *pr = r + (size_t)y * stride, *pi = ir + (size_t)y * stride;
                for (int rx = 0; rx < rw; rx++) {
                    const int x = x0 + rx;
                    const double D = ((double)t->L[pi[x]] - m1 * (double)t->L[pr[x]]) * k;
                    if (!(c0 - D > thr)) continue;
                    nd++;
                    pki_fn f;
                    if (row) f = rx == 0 ? row[0] : rx == rw - 1 ? row[2] : row[1];
                    else f = rx == 0 ? v->mid[0] : rx == 1 ? v->mid[1] : rx == rw - 1 ? v->mid[4] : rx == rw - 2 ? v->mid[3] : v->mid[2];
                    f(s, P, (ptrdiff_t)stride, x, y);
                }
            }
        }
    }
    if (out) {
        out->m = (float)m;
        out->c0 = (float)c0;
        if (c0_nan) { const uint32_t nan = 0xffc00000u; memcpy(&out->c0, &nan, 4); }
        out->A = (float)A; out->B = (float)B; out->thr = (float)thr; out->ndefect = nd;
    }
    return PK_OK;
}
