#include "render.h"
#include "nra.h"
#include <stddef.h>
#include <stdlib.h>
#include <stdint.h>

pk_status pkc_render_scene(const pkc_planes *in, const pkc_lut3 *L, int fo,
                           const pkc_lut3 *thr, const pkc_falloff_params *fp, pkc_planes *out) {
    return pkc_render_scene_t(in, L, fo, thr, fp, out, 0);
}

pk_status pkc_render_scene_t(const pkc_planes *in, const pkc_lut3 *L, int fo,
                             const pkc_lut3 *thr, const pkc_falloff_params *fp, pkc_planes *out, int threads) {
    if (!in || !L || !thr || !out || (fo && !fp)) return PK_E_ARG;
    pk_status s = pkc_nra_apply_t(in, out, thr, threads);
    if (s) return s;
    size_t n = (size_t)in->w * in->h;
    for (int c = 0; c < 3; c++) for (size_t i = 0; i < n; i++) {
        int v = out->p[c][i]; v = v < 0 ? 0 : v > 4095 ? 4095 : v;   /* in-range per RE 15 */
        out->p[c][i] = L->t[c][v];
    }
    return fo ? pkc_falloff_apply(out, fp) : PK_OK;
}

/* ---- PIScaleAndRotatePlanar's bicubic resample (PakonIMAu ImaResampleOp, interpolationFcn 2; RE 39) ---- */

/* Index and fractional offset of every output sample on one axis: the table builder FUN_102fd350 (indices) and FUN_102fd560 (the
 * offsets), 32-bit integer arithmetic in Kodak (kept in 64 bits here; the caller refuses sizes where Kodak's would wrap):
 *   A[i] = (dst + src * (2i + 1)) / (2 dst) - 1,   t[i] = (double)(src * (2i + 1) - (2 A[i] + 1) * dst) / (double)(2 dst). */
static void axis_tables(int src, int dst, int *A, double *t) {
    for (int i = 0; i < dst; i++) {
        const int64_t num = (int64_t)src * (2 * (int64_t)i + 1);
        const int64_t a = (dst + num) / (2 * (int64_t)dst) - 1;
        A[i] = (int)a;
        t[i] = (double)(num - (2 * a + 1) * dst) / (double)(2 * (int64_t)dst);
    }
}

/* The four Catmull-Rom weights of the taps A-1, A, A+1, A+2 (FUN_102fd1c0 / 1e0 / 210 / 240), x87 code at PC53 = one IEEE
 * double rounding per operation, in this operand order. */
static void cubic_weights(double t, double w[4]) {
    const double t2 = t * t;
    w[0] = ((2.0 - t) * t * t - t) * 0.5;
    w[1] = (t2 * t * 3.0 - t2 * 5.0) * 0.5 + 1.0;
    w[2] = ((4.0 - t * 3.0) * t + 1.0) * t * 0.5;
    w[3] = (t2 * t - t2) * 0.5;
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

pk_status pkc_resample_bicubic(pkc_planes *img, int ow, int oh) {
    if (!img || !img->p[0] || ow < 1 || oh < 1 || img->w < 1 || img->h < 1) return PK_E_ARG;
    const int W = img->w, H = img->h;
    if (ow == W && oh == H) return PK_OK;                 /* FUN_1000ce50: source size == destination size copies the input */
    if ((int64_t)W * 2 * ow > INT32_MAX || (int64_t)H * 2 * oh > INT32_MAX) return PK_E_ARG;
    const size_t n_out = (size_t)ow * oh;
    int *ci = malloc((size_t)ow * sizeof *ci), *ri = malloc((size_t)oh * sizeof *ri);
    double *ct = malloc((size_t)ow * sizeof *ct), *rt = malloc((size_t)oh * sizeof *rt);
    double *cw = malloc((size_t)ow * 4 * sizeof *cw), *v = malloc((size_t)W * sizeof *v);
    int16_t *b = malloc(3 * n_out * sizeof *b);
    pk_status st = PK_E_NOMEM;
    if (!ci || !ri || !ct || !rt || !cw || !v || !b) goto done;
    axis_tables(W, ow, ci, ct);
    axis_tables(H, oh, ri, rt);
    for (int x = 0; x < ow; x++) cubic_weights(ct[x], cw + 4 * (size_t)x);
    for (int c = 0; c < 3; c++) {
        const int16_t *src = img->p[c];
        int16_t *dst = b + (size_t)c * n_out;
        for (int y = 0; y < oh; y++) {
            double w[4];
            cubic_weights(rt[y], w);
            /* rows A-1 .. A+2, edge rows replicated (the padding FUN_1000b980 copies in) */
            const int16_t *r0 = src + (size_t)clampi(ri[y] - 1, 0, H - 1) * W, *r1 = src + (size_t)clampi(ri[y], 0, H - 1) * W;
            const int16_t *r2 = src + (size_t)clampi(ri[y] + 1, 0, H - 1) * W, *r3 = src + (size_t)clampi(ri[y] + 2, 0, H - 1) * W;
            /* vertical pass, per source column: ((p[A+2] w3 + p[A+1] w2) + p[A-1] w0) + p[A] w1 */
            for (int x = 0; x < W; x++)
                v[x] = (((double)r3[x] * w[3] + (double)r2[x] * w[2]) + (double)r0[x] * w[0]) + (double)r1[x] * w[1];
            /* horizontal pass: ((a0 c0 + a1 c1) + a2 c2) + a3 c3, then the clamp to the 12-bit range and trunc(x + 0.5) */
            for (int x = 0; x < ow; x++) {
                const double *k = cw + 4 * (size_t)x;
                const int a = ci[x];
                const double s = (((v[clampi(a - 1, 0, W - 1)] * k[0] + v[clampi(a, 0, W - 1)] * k[1]) +
                                   v[clampi(a + 1, 0, W - 1)] * k[2]) + v[clampi(a + 2, 0, W - 1)] * k[3]);
                dst[(size_t)y * ow + x] = (int16_t)(s < 0.0 ? 0 : s > 4095.0 ? 4095 : (int)(s + 0.5));
            }
        }
    }
    free(img->p[0]);
    img->w = ow; img->h = oh;
    for (int c = 0; c < 3; c++) img->p[c] = b + (size_t)c * n_out;
    b = NULL;
    st = PK_OK;
done:
    free(ci); free(ri); free(ct); free(rt); free(cw); free(v); free(b);
    return st;
}
