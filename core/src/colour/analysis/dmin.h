#ifndef PAKON_COLOUR_ANALYSIS_DMIN_H
#define PAKON_COLOUR_ANALYSIS_DMIN_H
#include <stdint.h>
#include "internal.h"
#include "analysis/image.h"

/* RE 20: TLB.dll's strip constants, the same at every scan resolution (FUN_10011a60 resolution entries):
 * strip+0xc6c = entry+0x60 = 0x5c94, and strip+0xc70 / ratio = 1603/4 = 2405/6 = 3206/8 = 400 lo-res rows. */
#define PKC_DMIN_DPI_BASE 23700
#define PKC_DMIN_FRAME_ROWS 400

/* RE 20: Kodak's film-base finder TLB FUN_10005ae0 (FN_bFindDmin), colour-negative path (film types 1/4/8).
 * strip_lores[c]: plane c of the lo-res strip AS TLB STORES IT -- `rows` rows of `w` samples (row stride w), raw
 * 14-bit linear (before the LUT and the 3x10 polynomial). TLB stores the planes un-registered: stored row r of plane
 * c is registered row r - c (RE 20 'Inputs'); this function does not re-register, exactly like Kodak.
 * rows = TLB's stored-row count (strip+0x14); dpi_base = strip+0xc6c (PKC_DMIN_DPI_BASE on every Kodak scan).
 * With R = rows - 2 and e = (uint32)(w*25400) / dpi_base:
 *   R < 400 + 16 + e  -> out = 0,0,0 (Kodak leaves the zeroed strip fields), PK_OK;
 *   otherwise per plane c a 16384-bin histogram of rows [e/2 + 2 - c, e/2 + 2 - c + n), n = min(2400, R - e),
 *   columns [w>>3, w>>3 + (6w)>>3); walk down from bin 16383 accumulating counts until the sum exceeds
 *   thr = n*ncols/1000 (bin 0 is never counted; the walk stops at 0); out = that bin, or 0 when it is 16383.
 * PK_E_ARG: NULL pointers, w < 1, rows < 0, dpi_base < 1, or a sample > 16383 inside the window (Kodak's histogram
 * has 16384 bins and would write out of bounds; TLB's scan-time clamp keeps stored samples <= 0x3fff). PK_E_NOMEM.
 * Every read stays inside the planes for any rows as long as w*25400 fits in 32 bits (w <= 169093); beyond that
 * Kodak's u32 arithmetic wraps, and so does this port's. On error out[] is unspecified. */
pk_status pkc_film_base(const uint16_t *strip_lores[3], int w, int rows, int dpi_base, uint16_t out[3]);

/* RE 16/17 (PakonIMAu analyzePass1 0x1021904b..0x102190d4, createAlgData min loop 0x1028d500):
 * d_c = 4095 if (int16)ctx_dmin[c] <= lim_c (lim = 180/550/700, sba+0x4d58) else ctx_dmin[c];
 * gridMin_c = min of grid[c][i] over cells strictly greater than lim_c (32000 if none, the loop's 0x7d00 seed);
 * out[c] = min(d_c, gridMin_c).  grid = pkc_grid24x36's bands 0-2 (values 0..4095). Pure; cannot fail.
 * Kodak holds the grid cells as int16 words and compares them signed; this port compares int32. The two agree for
 * every value in the documented 0..4095 domain (they would differ only for cells outside int16).
 * The limits 180/550/700 are runtime data in Kodak (sba+0x4d58); the oracle reads them at the sceneDmin bp (RE 20). */
/* The scene-dmin limits R/G/B (sba+0x4d58; Kodak-observed 180/550/700 on every run, RE 20 section 4). Shared with the
 * context-dmin write-back in fugc.c. */
#define PKC_DMIN_LIMITS { 180, 550, 700 }

/* analyzePass1's floor of a context value (0x1021904b..0x10219084): the word as int16 (movsx), or 4095 when it is at
 * or below the channel's limit (movzx limit, jg). Used by pkc_scene_dmin and by fugc.c's context write-back. */
static inline int32_t pkc_dmin_ctx_floor(uint16_t ctx, int c) {
    static const int32_t lim[3] = PKC_DMIN_LIMITS;
    int32_t d = (int16_t)ctx;
    return d <= lim[c] ? 0xfff : d;
}
void pkc_scene_dmin(const uint16_t ctx_dmin[3], const int32_t grid[3][PKC_GRID_N], uint16_t out[3]);
#endif
