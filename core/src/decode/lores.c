/* TLB.dll lo-res strip and row profile: the accumulate/emit tail of FUN_100246d0 (RE 30 sec 7, UC-exact), the stored-row count FUN_10005660
 * and the readable-row count FUN_10005590 (sec 8.2). */
#include <stdlib.h>
#include <string.h>
#include "decode/strip.h"
#include "decode/lores_weights.h"

size_t pkd_strip_rows_for(int ratio, size_t lines) { return (lines && ratio > 0) ? lines / (size_t)ratio + 1 : 0; }
size_t pkd_strip_readable_rows(size_t rows, int planes) { return planes > 0 && rows >= (size_t)(planes - 1) ? rows - (size_t)(planes - 1) : 0; }


void pkd_strip_free(pkd_strip *s) {
    if (!s) return;
    for (int c = 0; c < 3; c++) { free(s->plane[c]); free(s->acc[c]); }
    free(s->profile); free(s);
}

pk_status pkd_strip_new(int ratio, int width, size_t hires_lines, pkd_strip **out) {
    if (!out) return PK_E_ARG;
    *out = NULL;
    if ((ratio != 4 && ratio != 6 && ratio != 8) || width <= 0 || width > 4096 || hires_lines > ((size_t)1 << 28)) return PK_E_ARG;
    if (!pkd_lores_ready()) return PK_E_VENDOR_MISSING;       /* the weights come from the user's TLB.dll (pk_lores_weights_load) */
    pkd_strip *s = calloc(1, sizeof *s);
    if (!s) return PK_E_NOMEM;
    s->ratio = ratio; s->width = width; s->film = 1; s->count = ratio; s->prof_sum = s->own_sums;
    s->alloc_rows = (int)(hires_lines / (size_t)ratio) + 3;        /* window / ratio + 3 (UC FUN_10004f00); the 2 rows after `rows` are TLB's zero rows */
    s->rows = (int)pkd_strip_rows_for(ratio, hires_lines);
    const size_t n = (size_t)s->alloc_rows * (size_t)width;
    const size_t na = (size_t)width * (size_t)ratio / 2;
    for (int c = 0; c < 3; c++) {
        s->plane[c] = calloc(n, sizeof(uint16_t));
        s->acc[c] = calloc(na, sizeof(uint32_t));
    }
    s->profile = calloc((size_t)s->alloc_rows * 3, 1);
    if (!s->plane[0] || !s->plane[1] || !s->plane[2] || !s->acc[0] || !s->acc[1] || !s->acc[2] || !s->profile) { pkd_strip_free(s); return PK_E_NOMEM; }
    *out = s;
    return PK_OK;
}

void pkd_strip_share_profile_sums(pkd_strip *s, uint32_t sums[3]) { if (s && sums) s->prof_sum = sums; }
void pkd_strip_set_film(pkd_strip *s, int film) { if (s) s->film = film != 0; }

pk_status pkd_strip_feed(pkd_strip *s, const pkd_kernel_cfg *c, pkd_kernel_state *st, const uint16_t *raw, uint16_t *out) {
    if (!s || !c || !st || !out || c->ratio != s->ratio || c->n_px != s->width * s->ratio) return PK_E_ARG;
    if (s->count == 1 && s->wr >= (size_t)s->alloc_rows) return PK_E_ARG;           /* the emission would pass the allocation: refuse before touching state */
    pk_status r = pkd_kernel_line(c, st, raw, out);
    if (r != PK_OK) return r;
    const int n = c->n_px, ratio = s->ratio, w = s->width, half = ratio / 2;
    const uint16_t *wt = pkd_lores_row(ratio, s->row);
    for (int ch = 0; ch < 3; ch++) {
        const uint16_t *p = out + (size_t)ch * n;
        uint32_t *a = s->acc[ch];
        for (int k = 0; k < n / 2; k++)
            a[k] += (uint32_t)wt[(2 * k) % ratio] * p[2 * k] + (uint32_t)wt[(2 * k + 1) % ratio] * p[2 * k + 1];
        s->prof_sum[ch] += st->mean4[ch];
    }
    s->row++;
    if (s->film) s->film_lines++;
    if (--s->count == 0) {
        for (int ch = 0; ch < 3; ch++) {
            uint16_t *row = s->plane[ch] + s->wr * (size_t)w;
            for (int j = 0; j < w; j++) {
                uint32_t sum = 0;
                for (int i = 0; i < half; i++) sum += s->acc[ch][half * j + i];
                row[j] = (uint16_t)(sum >> 16);
            }
            memset(s->acc[ch], 0, (size_t)w * ratio / 2 * sizeof(uint32_t));
        }
        if (s->film) {
            uint8_t *pr = s->profile + s->wr * 3;
            pr[2] = (uint8_t)(s->prof_sum[0] / ((uint32_t)ratio << 8));        /* stored plane2, plane1, plane0 */
            pr[1] = (uint8_t)(s->prof_sum[1] / ((uint32_t)ratio << 8));
            pr[0] = (uint8_t)(s->prof_sum[2] / ((uint32_t)ratio << 8));
            s->wr++;
        }
        s->prof_sum[0] = s->prof_sum[1] = s->prof_sum[2] = 0;
        s->count = ratio; s->row = 0;
    }
    return PK_OK;
}

pk_status pkd_strip_finish(pkd_strip *s) {
    if (!s) return PK_E_ARG;
    const size_t rows = pkd_strip_rows_for(s->ratio, s->film_lines);
    if (rows + 2 > (size_t)s->alloc_rows) return PK_E_ARG;           /* the 2 zero rows after the declared ones must exist; rows stays as it was */
    s->rows = (int)rows;
    return PK_OK;
}
