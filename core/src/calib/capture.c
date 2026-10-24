#define _POSIX_C_SOURCE 200809L
/* Calibration line acquisition (Task 15). Origin: TLB FN_bCalibrateAcquireAndAverageLines FUN_1001d590 and its worker FUN_1001d170 (RE 43 sec 2 notes; RE 30 sec 13.1): zero a
 * buffer, then add the next N lines word by word, taking lines from the USB ring at the word with bit 0 set (the line sync), 6000 ms worker handshake. v1 had no live acquisition of
 * its own (tools/calib_wizard.py read the stream through pakon_scan.py's reader); the stream here is the Task 11 one. */
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "boards/boards.h"
#include "calib/calib.h"
#include "pakon/stream.h"

#define PKCAL_CAP_RING ((size_t)16 << 20)

struct pkcal_cap {
    const pkcal_ctx *c;
    pk_stream *st;
    unsigned wpl;
    pthread_mutex_t mu;
    unsigned want_seg;           /* the stream segment this acquisition reads (every pk_stream_rearm_sync starts a new one) */
    uint32_t *sum;
    unsigned need, skip, got;
    bool active;
    bool probing, probe_seen;    /* the first re-arm's segment is only watched for: its first chunk may have been in flight before the setting changed */
};

pk_status pkcal_tick(const pkcal_ctx *c) { return c && c->tick ? c->tick(c->user) : PK_OK; }

void pkcal_progress(const pkcal_ctx *c, int percent, const char *fmt, ...) {
    if (!c || !c->progress) return;
    char msg[96];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(msg, sizeof msg, fmt, ap);
    va_end(ap);
    c->progress(c->user, percent, msg);
}

/* Runs on the stream's reader thread for every complete line once the grid is synced. */
static void on_line(void *user, unsigned seg, uint64_t line, uint64_t off, const uint8_t *data) {
    pkcal_cap *p = (pkcal_cap *)user;
    (void)line; (void)off;
    pthread_mutex_lock(&p->mu);
    if (p->probing && seg == p->want_seg) p->probe_seen = true;
    if (p->active && seg == p->want_seg) {
        if (p->skip) p->skip--;
        else if (p->got < p->need) {
            for (unsigned w = 0; w < p->wpl; w++) p->sum[w] += (uint32_t)(data[2 * w] | data[2 * w + 1] << 8);
            p->got++;
        }
    }
    pthread_mutex_unlock(&p->mu);
}

pk_status pkcal_cap_open(const pkcal_ctx *c, unsigned words_per_line, pkcal_cap **out) {
    if (out) *out = NULL;
    if (!c || !c->t || !words_per_line || !out) return PK_E_ARG;
    pkcal_cap *p = (pkcal_cap *)calloc(1, sizeof *p);
    if (!p) return PK_E_NOMEM;
    p->c = c;
    p->wpl = words_per_line;
    pthread_mutex_init(&p->mu, NULL);
    pk_stream_cfg sc = { PKCAL_CAP_RING, words_per_line, NULL, 0, on_line, p, 0, true };   /* TLB FUN_1001d170: no first-sync window, resync per line (HW 2026-10-22) */
    pk_status st = pk_stream_start(c->t, &sc, &p->st);
    if (st != PK_OK) { pthread_mutex_destroy(&p->mu); free(p); return st; }
    *out = p;
    return PK_OK;
}

void pkcal_cap_close(pkcal_cap *p) {
    if (!p) return;
    if (p->st) { (void)pk_stream_stop(p->st, NULL); pk_stream_free(p->st); }
    pthread_mutex_destroy(&p->mu);
    free(p);
}

/* Waits until *flag (read under the mutex) is set, a line count reaches need, the stream fails, the tick fails, or no progress is made for PKCAL_LINE_TIMEOUT_MS. */
static pk_status wait_for(pkcal_cap *p, const bool *flag, unsigned need) {
    unsigned last = 0;
    unsigned long long since = pkb_now_ms();
    for (;;) {
        pthread_mutex_lock(&p->mu);
        unsigned got = p->got;
        bool done = flag ? *flag : got >= need;
        pthread_mutex_unlock(&p->mu);
        if (done) return PK_OK;
        if (got != last) { last = got; since = pkb_now_ms(); }
        else if (pkb_now_ms() - since > PKCAL_LINE_TIMEOUT_MS) return PK_E_TIMEOUT;
        pk_status st = pkcal_tick(p->c);
        if (st == PK_OK) st = pk_stream_poll(p->st, NULL, NULL);
        if (st != PK_OK) return st;
        pkb_sleep_ms(2);
    }
}

/* The stream reader classifies a whole chunk (up to 256 KB, 20 lines) under the segment that is current when the chunk RETURNS, and a read that returns just after a setting was
 * written may hold lines exposed before it. So the first re-arm only starts a segment that is watched for; once a line of it has arrived the chunk boundary has passed, and a second
 * re-arm starts the segment the sums are taken from (its first chunk began after the write). PKCAL_SETTLE_LINES more lines absorb what the device itself had buffered. */
pk_status pkcal_cap_lines(pkcal_cap *p, unsigned n_lines, uint32_t *sum) {
    if (!p || !sum || !n_lines) return PK_E_ARG;
    memset(sum, 0, (size_t)p->wpl * sizeof *sum);
    pthread_mutex_lock(&p->mu);
    p->sum = NULL;
    p->active = false;
    p->probing = true;
    p->probe_seen = false;
    p->got = 0;
    p->want_seg++;
    pthread_mutex_unlock(&p->mu);
    pk_status st = pk_stream_rearm_sync(p->st);
    if (st == PK_OK) st = wait_for(p, &p->probe_seen, 0);
    if (st == PK_OK) {
        pthread_mutex_lock(&p->mu);
        p->probing = false;
        p->sum = sum;
        p->need = n_lines;
        p->got = 0;
        p->skip = PKCAL_SETTLE_LINES;
        p->want_seg++;
        p->active = true;
        pthread_mutex_unlock(&p->mu);
        st = pk_stream_rearm_sync(p->st);
        if (st == PK_OK) st = wait_for(p, NULL, n_lines);
    }
    pthread_mutex_lock(&p->mu);                       /* from here the reader no longer touches sum */
    p->probing = false;
    p->active = false;
    p->sum = NULL;
    pthread_mutex_unlock(&p->mu);
    return st;
}

/* TLB FUN_1001d170's accumulation (0x1001d300 R G B from the triplets at line + 6 x pixel; 0x1001d352 IR from line + 2 x (3 x n_acq + pixel)): the wire line is n_acq R G B triplets,
 * then, with the IR bit set, n_acq IR words. The sums are handed back channel-major as TLB keeps them. */
pk_status pkcal_acquire(pkcal_run *r, unsigned n_lines, uint32_t *sum) {
    if (!r || !sum || (r->lnch != 3 && r->lnch != 4)) return PK_E_ARG;
    pk_status st = pkcal_cap_lines(r->cap, n_lines, r->raw);
    if (st != PK_OK) return st;
    const size_t n = (size_t)r->n_acq;
    for (size_t p = 0; p < n; p++)
        for (size_t c = 0; c < 3; c++) sum[c * n + p] = r->raw[p * 3 + c];
    if (r->lnch == 4) memcpy(sum + 3 * n, r->raw + 3 * n, n * sizeof *sum);
    return PK_OK;
}
