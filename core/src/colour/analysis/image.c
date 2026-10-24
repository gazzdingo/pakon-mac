/* RE 19: the SBA analysis image (PakonIMAu pathUtils::resampleAnslysisImage 0x100d8030 -> ImaResampleOp bilinear
 * kernel 0x100d5e40) and its 24x36 grid (createAlgData 0x1028ceb0 + block sampler 0x1028cd10).
 * x87 at PC53 (PSI's MSVC default, RE 03) == C double with -ffp-contract=off; _ftol == C truncation. */
#include <stdlib.h>
#include <string.h>
#include "analysis/image.h"

void pkc_analysis_dims(int w, int h, int *ow, int *oh) {
    int mx = w > h ? w : h;
    if (mx <= PKC_AIMG_SIZE) { *ow = w; *oh = h; return; }
    double s = 1.0 / ((double)mx / (double)PKC_AIMG_SIZE);    /* fild mx; fidiv 376; fdivr 1.0 */
    *ow = (int)((double)w * s + 0.5);
    *oh = (int)((double)h * s + 0.5);
}

/* Centre-aligned source taps for output i: i0 = floor(((2i+1)n_in - n_out) / (2 n_out)),
 * f = ((2i+1)n_in - (2 i0+1) n_out) / (2 n_out) as one int/int double division (0x100d64a1..0x100d64cd).
 * Only called to downscale (n_out <= n_in), so the numerator is >= 0 and i0 < n_in. */
static void taps(int n_in, int n_out, int *i0, int *i1, double *f) {
    for (int i = 0; i < n_out; i++) {
        long long num = (long long)(2 * i + 1) * n_in - n_out, den = 2LL * n_out;
        long long a = num / den;
        i0[i] = (int)a;
        i1[i] = a + 1 < n_in ? (int)a + 1 : n_in - 1;
        f[i] = (double)((long long)(2 * i + 1) * n_in - (2 * a + 1) * n_out) / (double)den;
    }
}

void pkc_analysis_image_free(pkc_planes *img) {
    if (!img) return;
    free(img->p[0]);
    img->p[0] = img->p[1] = img->p[2] = NULL;
}

pk_status pkc_analysis_image(const uint16_t *lores[3], int w, int h, pkc_planes *out) {
    if (!out) return PK_E_ARG;
    out->w = out->h = 0; out->p[0] = out->p[1] = out->p[2] = NULL;
    if (!lores || !lores[0] || !lores[1] || !lores[2] || w < 1 || h < 1) return PK_E_ARG;
    int ow, oh;
    pkc_analysis_dims(w, h, &ow, &oh);
    if (ow < 1 || oh < 1) return PK_E_IMAGE_TOO_SMALL;
    size_t n = (size_t)ow * oh;
    int16_t *blk = malloc(3 * n * sizeof *blk);
    if (!blk) return PK_E_NOMEM;
    if (ow == w && oh == h) {                      /* max(w,h) <= 376: Kodak uses the frame as-is */
        for (int c = 0; c < 3; c++)
            for (size_t i = 0; i < n; i++) blk[(size_t)c * n + i] = (int16_t)lores[c][i];
    } else {
        int *ix = malloc((size_t)(2 * ow + 2 * oh) * sizeof *ix);
        double *fx = malloc((size_t)(ow + oh) * sizeof *fx);
        if (!ix || !fx) { free(ix); free(fx); free(blk); return PK_E_NOMEM; }
        int *x0 = ix, *x1 = ix + ow, *y0 = ix + 2 * ow, *y1 = y0 + oh;
        double *fy = fx + ow;
        taps(w, ow, x0, x1, fx);
        taps(h, oh, y0, y1, fy);
        for (int c = 0; c < 3; c++) {
            const uint16_t *src = lores[c];
            int16_t *dst = blk + (size_t)c * n;
            for (int j = 0; j < oh; j++) {
                const uint16_t *r0 = src + (size_t)y0[j] * w, *r1 = src + (size_t)y1[j] * w;
                for (int i = 0; i < ow; i++) {
                    int p00 = (int16_t)r0[x0[i]], p01 = (int16_t)r0[x1[i]];      /* movswl */
                    int p10 = (int16_t)r1[x0[i]], p11 = (int16_t)r1[x1[i]];
                    double top = (double)(p01 - p00) * fx[i] + (double)p00;      /* 0x100d671d..0x100d673b */
                    double bot = (double)(p11 - p10) * fx[i] + (double)p10;
                    double v = (bot - top) * fy[j] + top;
                    /* fcom 0.0: v-0.5 if v < 0 else v+0.5, then _ftol. Kodak's fx==0 / fy==0 shortcuts give the
                     * same value (they skip only products with zero) and just avoid reading the unused tap. */
                    dst[(size_t)j * ow + i] = (int16_t)(int)(v < 0.0 ? v - 0.5 : v + 0.5);
                }
            }
        }
        free(ix); free(fx);
    }
    for (int c = 0; c < 3; c++) out->p[c] = blk + (size_t)c * n;
    out->w = ow; out->h = oh;
    return PK_OK;
}

/* clamp 0: a block reaching past the image is PK_E_UNSUPPORTED (Kodak's behaviour is unreproducible); clamp 1: see
 * pkc_grid24x36_clamped. *clamped (may be NULL) is set to whether any read was clamped. */
static pk_status grid_impl(const pkc_planes *img, int32_t grid[3][PKC_GRID_N], int clamp, int *clamped) {
    if (clamped) *clamped = 0;
    if (!img || !grid || !img->p[0] || !img->p[1] || !img->p[2]) return PK_E_ARG;
    const int w = img->w, h = img->h;
    const int so = h / PKC_GRID_ROWS, si = w / PKC_GRID_COLS;            /* step_outer (rows), step_inner (cols) */
    if (so < 1 || si < 1) return PK_E_IMAGE_TOO_SMALL;
    const int mo = (h - so * PKC_GRID_ROWS) / 2, mi = (w - si * PKC_GRID_COLS) / 2;
    /* the sampler's block is si rows x so cols (transposed w.r.t. the cell stride), addressed flat as row * w + col
     * (fcn.1028cd10 0x1028cdc6..0x1028cdd2: imul by the width, add the column): a block wider than the space left in a
     * row reads on into the next row (observed at Kodak: synf / syns, 252 x 240 frames, Task 19). A read past the
     * image's last sample leaves Kodak's buffer and averages heap contents into the grid (observed: t14w2's 356 x 123
     * frame, whose last grid row Kodak fills from beyond the image) -- not reproducible: PK_E_UNSUPPORTED */
    const int past = (long long)(mo + (PKC_GRID_ROWS - 1) * so + si - 1) * w + (mi + (PKC_GRID_COLS - 1) * si + so - 1) >= (long long)w * h;
    if (past && !clamp) return PK_E_UNSUPPORTED;
    if (clamped) *clamped = past;
    const long long cnt = (long long)si * so;
    for (int c = 0; c < 3; c++) {
        const int16_t *p = img->p[c];
        for (int gi = 0; gi < PKC_GRID_ROWS; gi++)
            for (int gj = 0; gj < PKC_GRID_COLS; gj++) {
                const int r0 = mo + gi * so, c0 = mi + gj * si;
                long long sum = 0;
                for (int y = r0; y < r0 + si; y++)
                    for (int x = c0; x < c0 + so; x++) {
                        size_t idx = (size_t)y * w + x;
                        if (past && idx >= (size_t)w * h) idx = (size_t)(h - 1) * w + idx % w;   /* OWNER CHOICE R41, see pkc_grid24x36_clamped */
                        sum += (uint16_t)p[idx];   /* movzx */
                    }
                long long v = sum / cnt;
                /* 0x1028d28c: any band mean > 0x7d00 (unsigned compare) makes createAlgData fail with -0x9b */
                if (v > 0x7d00) return PK_E_ARG;
                /* 0x1028d2bb: mean + per-channel offset (0 here, see image.h), clamped to 0..0xfff */
                grid[c][gi * PKC_GRID_COLS + gj] = (int32_t)(v > 4095 ? 4095 : v);
            }
    }
    return PK_OK;
}

pk_status pkc_grid24x36(const pkc_planes *img, int32_t grid[3][PKC_GRID_N]) { return grid_impl(img, grid, 0, NULL); }

/* NON-KODAK, OWNER'S CHOICE (ruling R41, 2026-10-15). Where Kodak's sampler reads past the image's last sample it averages
 * heap memory -- nothing exact exists. This helper replaces each such read by the same column of the image's last row (the
 * bottom edge replicated: the closest real image content), and reports it in *clamped. Reads that stay inside the plane,
 * including flat row wraps, are Kodak's. Used only by the batch statistics of pkc_roll_batches; the frame concerned is
 * refused and every other frame of its batch is flagged not Kodak-exact. */
pk_status pkc_grid24x36_clamped(const pkc_planes *img, int32_t grid[3][PKC_GRID_N], int *clamped) {
    return grid_impl(img, grid, 1, clamped);
}

pk_status pkc_splice_crop(const pkc_planes *img, int thr, int splice_pct, pkc_planes *out, pkc_splice *info) {
    if (!out) return PK_E_ARG;
    out->w = out->h = 0; out->p[0] = out->p[1] = out->p[2] = NULL;
    if (!img || !img->p[0] || !img->p[1] || !img->p[2] || img->w < 1 || img->h < 1) return PK_E_ARG;
    const int w = img->w, h = img->h;
    /* 0x102136c0: need = _ftol(h * 0.9 + 0.5) (fild; fmul 0.9; fadd 0.5 at PC53); a column counts when at least need
     * band-0 samples are > thr (movsx, cmp, jle) */
    double v = (double)h * 0.9;
    v = v + 0.5;
    const int need = (int)v;
    int count = 0, start = -1;
    for (int x = 0; x < w; x++) {
        int c = 0;
        for (int y = 0; y < h; y++) if ((int)img->p[0][(size_t)y * w + x] > thr) c++;
        if (c >= need) { if (start == -1) start = x; count++; }
    }
    /* 0x10218440..0x102184a3: ratio = fild count / fidiv w; crop when ratio > 0.0, ratio <= splicePct * 0.01 (fild, fmul
     * 0.01) and w - count >= 36 */
    const double ratio = (double)count / (double)w;
    const double lim = (double)splice_pct * 0.01;
    const int crop = ratio > 0.0 && ratio <= lim && w - count >= 36;
    if (info) { info->count = count; info->start = start; info->ratio = ratio; info->cropped = crop; }
    if (!crop) return PK_OK;
    /* 0x102184a9..0x102184d4: the first splice column right of w * 0.5 keeps [0, w - count), else [count, w) */
    const int x0 = (double)w * 0.5 < (double)start ? 0 : count, nw = w - count;
    int16_t *b = malloc(sizeof *b * 3 * (size_t)nw * h);
    if (!b) return PK_E_NOMEM;
    for (int c = 0; c < 3; c++) {
        out->p[c] = b + (size_t)c * nw * h;
        for (int y = 0; y < h; y++)
            memcpy(out->p[c] + (size_t)y * nw, img->p[c] + (size_t)y * w + x0, sizeof *b * (size_t)nw);
    }
    out->w = nw; out->h = h;
    return PK_OK;
}
