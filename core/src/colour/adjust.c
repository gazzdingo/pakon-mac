/* PSI adjustment controls: PIColorAdjustPlanar's LUT and unsharp-mask stages (RE 06 §2.2, §2.3).
 * Verified bit-exact against Kodak's PakonIMAu.dll under Wine (lab/oracle/scripts/adjust_grid.py). */
#include "adjust.h"
#include <stdlib.h>
#include <string.h>

static int clampi(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }
static int sat16(int32_t v) { return v < -32768 ? -32768 : v > 32767 ? 32767 : (int)v; }
/* arithmetic shift right (psrad / sar) without relying on implementation-defined >> of negatives */
static int32_t asr(int32_t v, int s) { return v >= 0 ? v >> s : ~((~v) >> s); }

void pkc_adjust_lut(const pk_adjust *a, pkc_lut3 *out, int *active) {
    /* PSI's TLB limits the r/g/b/brightness/contrast values to +-1000 (Kodak itself accepts up to +-2000 when a non-zero
     * defaults.ini scales them; pk_adjust is the TLB range) */
    int bri = clampi(a->brightness, -1000, 1000), con = clampi(a->contrast, -1000, 1000);
    int sum[3] = { clampi(a->r, -1000, 1000) + bri, clampi(a->g, -1000, 1000) + bri,
                   clampi(a->b, -1000, 1000) + bri };
    int c2 = con / 2, k = c2 + 1000;                 /* C division truncates toward 0, as cdq/sar */
    int any = sum[0] || sum[1] || sum[2];
    int16_t base[4096];
    *active = any || c2;
    if (!*active) {
        for (int c = 0; c < 3; c++) for (int i = 0; i < 4096; i++) out->t[c][i] = (int16_t)i;
        return;
    }
    for (int i = 0; i < 4096; i++) {
        int v = c2 ? (i - 1550) * k / 1000 + 1550 : i;  /* pivot 0x60e; |v| <= 5367, fits short */
        base[i] = (int16_t)(c2 && !any ? clampi(v, 0, 4095) : v);
    }
    for (int c = 0; c < 3; c++) {
        int16_t *L = out->t[c];
        memcpy(L, base, sizeof base);
        if (sum[c]) {
            int off = sum[c] * 4096 / 4000;
            for (int i = 0; i < 4096; i++) L[i] = (int16_t)clampi(L[i] + off, 0, 4095);
        } else {
            /* Kodak's clamp loop (0x10014a40): the pointer only advances past out-of-range entries,
             * so it stops at the first in-range one and later out-of-range entries survive. */
            for (int j = 0; j < 4096 && (L[j] < 0 || L[j] > 4095); j++) L[j] = (int16_t)(L[j] < 0 ? 0 : 4095);
        }
    }
}

/* ImaConvolutionUnsharpMaskOpI16p3Mmx gain (0x103d2650 / 0x1030dbe0): a = S*0.01 (double);
 * s = 16384 halved while _ftol(|a|*s + 0.2) > 16384; A = _ftol(s*a + 0.5); t = (d*A + s/2) >> log2(s). */
static void usm_gain(int sharpness, int32_t *A, int32_t *s_out, int *shift) {
    double a = sharpness * 0.01, aa = a < 0 ? -a : a;
    int32_t s = 16384; int sh = 14;
    while ((int32_t)(s * aa + 0.2) > 16384 && s > 1) { s /= 2; sh--; }
    *A = (int32_t)(s * a + 0.5);
    *s_out = s; *shift = sh;
}

pk_status pkc_adjust_usm(pkc_planes *img, int sharpness) {
    if (!img || sharpness < 0 || sharpness > 2000) return PK_E_ARG;
    if (sharpness == 0) return PK_OK;
    if (!img->p[0] || !img->p[1] || !img->p[2]) return PK_E_ARG;
    if (img->w < 3 || img->h < 3) return PK_E_IMAGE_TOO_SMALL;
    int w = img->w, h = img->h, shift;
    int32_t A, s; usm_gain(sharpness, &A, &s, &shift);
    int32_t rnd = s / 2;
    size_t n = (size_t)w * h;
    int16_t *src = malloc(n * sizeof *src), *v = malloc((size_t)w * sizeof *v);
    if (!src || !v) { free(src); free(v); return PK_E_NOMEM; }
    for (int c = 0; c < 3; c++) {
        int16_t *dst = img->p[c];
        memcpy(src, dst, n * sizeof *src);
        for (int y = 0; y < h; y++) {
            /* 1-pixel border: the image edge is replicated (oracle dumps, RE 06 open item 3) */
            const int16_t *up = src + (size_t)(y > 0 ? y - 1 : 0) * w, *mid = src + (size_t)y * w,
                          *dn = src + (size_t)(y < h - 1 ? y + 1 : h - 1) * w;
            for (int x = 0; x < w; x++)   /* vertical pass, packssdw-saturated */
                v[x] = (int16_t)sat16(asr(4096 * up[x] + 8192 * mid[x] + 4096 * dn[x] + 8192, 14));
            for (int x = 0; x < w; x++) {
                int xl = x > 0 ? x - 1 : 0, xr = x < w - 1 ? x + 1 : w - 1;
                int32_t blur = asr(4096 * v[xl] + 8192 * v[x] + 4096 * v[xr] + 8192, 14);
                int32_t t = asr(((int32_t)mid[x] - blur) * A + rnd, shift);
                dst[(size_t)y * w + x] = (int16_t)clampi(sat16((int32_t)mid[x] + t), 0, 4095);
            }
        }
    }
    free(src); free(v);
    return PK_OK;
}

pk_status pkc_adjust_apply(pkc_planes *img, const pk_adjust *a) {
    if (!img || !a || !img->p[0] || !img->p[1] || !img->p[2] || img->w < 1 || img->h < 1) return PK_E_ARG;
    if (a->r < -1000 || a->r > 1000 || a->g < -1000 || a->g > 1000 || a->b < -1000 || a->b > 1000 ||
        a->brightness < -1000 || a->brightness > 1000 || a->contrast < -1000 || a->contrast > 1000 ||
        a->sharpness < 0 || a->sharpness > 2000 || a->saturation < -5 || a->saturation > 5 ||
        a->bnw < 0 || a->bnw > 3)
        return PK_E_ARG;
    if (a->sharpness && (img->w < 3 || img->h < 3)) return PK_E_IMAGE_TOO_SMALL;
    pkc_lut3 *lut = malloc(sizeof *lut);
    if (!lut) return PK_E_NOMEM;
    int active;
    pkc_adjust_lut(a, lut, &active);
    if (active) {
        size_t n = (size_t)img->w * img->h;
        for (int c = 0; c < 3; c++) {
            int16_t *p = img->p[c]; const int16_t *L = lut->t[c];
            for (size_t i = 0; i < n; i++) p[i] = L[clampi(p[i], 0, 4095)];
        }
    }
    free(lut);
    return pkc_adjust_usm(img, a->sharpness);
}
