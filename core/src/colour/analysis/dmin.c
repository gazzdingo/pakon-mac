/* RE 20: TLB.dll film-base finder FUN_10005ae0; RE 16/17: PakonIMAu scene dmin (analyzePass1 + createAlgData). */
#include "analysis/dmin.h"
#include <stdlib.h>

#define HBINS 0x4000u                    /* operator new(0x10000): 16384 u32 bins */

pk_status pkc_film_base(const uint16_t *strip_lores[3], int w, int rows, int dpi_base, uint16_t out[3]) {
    if (!strip_lores || !strip_lores[0] || !strip_lores[1] || !strip_lores[2] || !out || w < 1 || rows < 0 ||
        dpi_base < 1)
        return PK_E_ARG;
    /* vt+0x20 (0x10005590): stored rows - (planes - 1), 0 if fewer; Kodak's planes = 3 (strip+0x28) */
    uint32_t R = rows >= 2 ? (uint32_t)rows - 2u : 0u;
    /* 0x10005b0b..: all unsigned 32-bit, as the div/imul/lea sequence */
    uint32_t e = ((uint32_t)w * 25400u) / (uint32_t)dpi_base;
    uint32_t q = PKC_DMIN_FRAME_ROWS;              /* strip+0xc70 / vt+0x24 */
    out[0] = out[1] = out[2] = 0;                  /* strip+0x6cac..b4 as the ctor (FUN_10004df0) left them */
    if (R < q + 16u + e) return PK_OK;             /* jb 0x10005ccb: nothing written */
    uint32_t start = e >> 1;                       /* row-pointer table index */
    uint32_t c0 = (uint32_t)w >> 3, nc = ((uint32_t)w * 6u) >> 3;
    uint32_t n = R - e < 6u * q ? R - e : 6u * q;
    uint32_t thr = (n * nc) / 1000u;               /* mul 0x10624dd3, shr 6 */
    uint32_t *hist = malloc(HBINS * sizeof *hist);
    if (!hist) return PK_E_NOMEM;
    for (int c = 0; c < 3; c++) {
        for (uint32_t i = 0; i < HBINS; i++) hist[i] = 0;
        /* plane c starts (2 - c) rows below the table row: offset ((2-c)*planes + c)*w + c0 in TLB's row layout */
        const uint16_t *p = strip_lores[c] + ((size_t)start + 2u - (uint32_t)c) * (size_t)w + c0;
        for (uint32_t r = 0; r < n; r++, p += w)
            for (uint32_t x = 0; x < nc; x++) {
                if (p[x] >= HBINS) { free(hist); return PK_E_ARG; }
                hist[p[x]]++;
            }
        uint32_t cum = 0, v = HBINS - 1;           /* 0x10005c80..0x10005c95 */
        for (;;) {
            cum += hist[v];
            if (thr < cum) break;
            if (--v == 0) break;
        }
        out[c] = (uint16_t)(v == HBINS - 1 ? 0 : v);   /* sete/dec/and: 16383 -> 0 */
    }
    free(hist);
    return PK_OK;
}

void pkc_scene_dmin(const uint16_t ctx_dmin[3], const int32_t grid[3][PKC_GRID_N], uint16_t out[3]) {
    static const int32_t lim[3] = PKC_DMIN_LIMITS;     /* sba+0x4d58 */
    for (int c = 0; c < 3; c++) {
        int32_t gmin = 0x7d00;                          /* 0x1028cff0 seed */
        for (int i = 0; i < PKC_GRID_N; i++)
            if (grid[c][i] < gmin && grid[c][i] > lim[c]) gmin = grid[c][i];   /* 0x1028d500..0x1028d50e */
        int32_t d = pkc_dmin_ctx_floor(ctx_dmin[c], c);  /* movsx ctx, movzx limit; 0x10219058 */
        if (d > gmin) d = gmin;                         /* 0x10219094..0x1021909e */
        out[c] = (uint16_t)d;
    }
}
