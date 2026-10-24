/* RE 11: PakonIMAu ImaLensFalloffOperation (short variant, ctor FUN_102de380, render FUN_102df430).
 * Arithmetic ported verbatim from lab/falloff/c/falloff.c (kodak_falloff_i16). */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include "data/diag.h"
#include "falloff.h"
#include "data/kodak_text.h"

pk_status pkc_falloff_params_load(const char *vendor_root, pkc_falloff_params *p) {
    if (!vendor_root || !p) return PK_E_ARG;
    char path[1024];
    pk_status st = pkc_vendor_path(vendor_root,
        "anselinstalldir/dataPathItems/falloff/falloff-srcType-SUC-NEGATIVE_35-NO.dpi", path, sizeof path);
    if (st != PK_OK) return st;
    pkc_kt *kt;
    st = pkc_kt_load(path, &kt);
    if (st != PK_OK) return st;
    double scale, mx, stops, lo, hi;
    int ok = pkc_kt_num(kt, "scale", &scale, 1) == 1 && pkc_kt_num(kt, "max", &mx, 1) == 1 &&
             pkc_kt_num(kt, "stops", &stops, 1) == 1 && pkc_kt_num(kt, "exposure_min", &lo, 1) == 1 &&
             pkc_kt_num(kt, "exposure_max", &hi, 1) == 1;
    pkc_kt_free(kt);
    if (!ok) return PK_E_VENDOR_DATA;
    p->scale = (int)scale;
    p->max = (int)mx;
    p->stops = (float)stops;
    p->exp_min = (float)lo;
    p->exp_max = (float)hi;
    return PK_OK;
}

int pkc_falloff_enabled(const pkc_falloff_params *p, double e) {
    if (!p) return 0;
    const float ef = (float)e;
    return p->scale > 0 && p->stops > 0x1p-23f && p->exp_min <= ef && ef <= p->exp_max;
}

pk_status pkc_falloff_apply(pkc_planes *img, const pkc_falloff_params *p) {
    if (!img || !p) return PK_E_ARG;
    const int W = img->w, H = img->h, scale = p->scale, maxv = p->max;
    const float stops = p->stops;
    if (W <= 0 || H <= 0) return PK_E_ARG;
    if (scale <= 0 || !(stops > 0.0f)) return PK_OK;
    const int cx = W / 2, cy = H / 2;
    const int N = (int)(sqrt((double)(cx * cx + cy * cy)) + 1.0);
    const double diag = sqrt((double)(W * W + H * H));
    const double th = acos(pow(0.5, (double)stops * 0.25));
    const int d = (int)(diag / (tan(th) + tan(th)));
    const int d2 = d * d;
    int32_t *corr = malloc(sizeof *corr * (size_t)N);
    if (!corr) return PK_E_NOMEM;
    for (int i = 0; i < N; i++)
        corr[i] = (int32_t)((double)scale * log10((double)(d2 + i * i) / (double)d2));
    for (int b = 0; b < 3; b++) {
        if (!img->p[b]) continue;
        for (int y = 0; y < H; y++) {
            const int dy = y - cy;
            int16_t *row = img->p[b] + (size_t)y * W;
            for (int x = 0; x < W; x++) {
                const int dx = x - cx;
                const int r = (int)sqrt((double)(dx * dx + dy * dy));
                const int c = corr[r];
                const int s = row[x];
                row[x] = (int16_t)(s > maxv - c ? maxv : s + c);
            }
        }
    }
    free(corr);
    return PK_OK;
}
