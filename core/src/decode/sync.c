/* Line sync, ported from v1 tools/pakon_decode.py segment_lines (RE 30 sec 2.1). */
#include <stdlib.h>
#include <string.h>
#include "decode/kernel.h"

pk_status pkd_sync_lines(const uint16_t *words, size_t n, unsigned wpl, uint16_t **lines_out, pkd_sync_report *rep) {
    if (!words || !lines_out || !wpl) return PK_E_ARG;
    pkd_sync_report r = {0, 0, 0, 0};
    *lines_out = NULL;
    size_t cap = n / wpl + 1;
    uint16_t *buf = malloc(cap * wpl * sizeof *buf);
    if (!buf) return PK_E_NOMEM;
    size_t prev = 0; int have = 0;
    for (size_t i = 0; i < n; i++) {
        if (!(words[i] & 1)) continue;
        if (have) {
            if (i - prev == wpl) { memcpy(buf + r.lines * wpl, words + prev, wpl * sizeof *buf); r.lines++; }
            else { size_t m = (i - prev) / wpl; r.resyncs += m ? m : 1; }
        }
        if (!have) r.lead_words = i;
        prev = i; have = 1;
    }
    if (have) {   /* the last start: a line only when a whole line follows it */
        if (n - prev >= wpl) { memcpy(buf + r.lines * wpl, words + prev, wpl * sizeof *buf); r.lines++; r.partial_tail_words = n - prev - wpl; }
        else r.partial_tail_words = n - prev;
    }
    if (!have) r.lead_words = n;
    if (r.lines) *lines_out = buf; else free(buf);
    if (rep) *rep = r;
    return PK_OK;
}
