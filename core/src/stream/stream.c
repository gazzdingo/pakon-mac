#define _POSIX_C_SOURCE 200809L
/* Scan-stream capture: reader thread (stream_read -> sync check -> ring) and writer thread (ring -> raw file). */
#include "pakon/stream.h"
#include "stream/ring.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PKS_CHUNK ((size_t)256 << 10)
#define PKS_DEFAULT_RING ((size_t)120 << 20)
#define PKS_FLUSH_EVERY ((uint64_t)64 << 20)
#define PKS_WRITER_WAIT_MS 50u
/* First-sync search window in 16-bit words. TLB searches one driver ring packet (cfg+0x1600 bytes) for a word with bit 0
 * set; the field has no registry override and its constructor default FUN_10010b60 (0x10010c3f, mov [esi+0x60], 0x5000)
 * is 0x5000 bytes = 10240 words (RE 30 section 2.2.1; ruling S-R28). */
#define PKS_SYNC_WINDOW_WORDS 10240u

struct pk_stream {
    pk_transport *t;
    pk_ring *ring;
    FILE *raw;
    size_t line_bytes;
    unsigned timeout_ms;
    unsigned skip0_words;          /* segment 0 only: words dropped before the first-sync search (cfg first_skip_words) */
    int resync;                    /* cfg resync: TLB's calibration reader (no window, a missing line start searches again) */
    pthread_t reader, writer;
    int started, joined;
    pthread_mutex_t mu;            /* guards everything below */
    int stop;
    int rearm;                     /* set by pk_stream_rearm_sync, taken by the reader */
    pk_status fatal;
    uint64_t bytes;                /* bytes accepted into the ring (= bytes in the raw file) */
    int synced;                    /* a line start has been found since the last (re)arm */
    uint64_t origin;               /* stream byte offset of the current segment's first line start */
    uint64_t search_start;         /* even stream byte offset where the current search began */
    uint64_t search_cap;           /* bytes of the current search that can count as lead (skip + window; UINT64_MAX without a window) */
    uint64_t lines_base;           /* complete lines of earlier segments */
    uint64_t lead_bytes;           /* bytes outside any line: skipped by searches, plus partial lines left at a re-arm */
    char diag[96];
    pk_stream_line_cb line_cb;     /* reader-only state below: the line tap (Task 13) */
    void *line_user;
    uint8_t *pend;                 /* the head of a line that began in an earlier chunk */
    size_t pend_fill;
    uint64_t tap_next;             /* stream byte offset of the next line to deliver; TAP_UNSET until the grid is synced */
    uint64_t tap_line;             /* index of that line */
    unsigned tap_seg;
    uint64_t *seg_off, *seg_line;  /* per segment: the byte offset and line index of its first synced line (guarded by mu); seg_n entries known */
    unsigned seg_n, seg_cap;
};
#define TAP_UNSET UINT64_MAX

/* Reader-private search state (only the reader thread touches it). */
typedef struct { unsigned left, skip; } pks_search;

/* Records the first fatal error and, with it, the text that describes it (diag may be NULL). */
static void set_fatal_d(pk_stream *s, pk_status st, const char *diag) {
    pthread_mutex_lock(&s->mu);
    if (s->fatal == PK_OK) {
        s->fatal = st;
        if (diag) snprintf(s->diag, sizeof s->diag, "%s", diag);
    }
    pthread_mutex_unlock(&s->mu);
}
static void set_fatal(pk_stream *s, pk_status st) { set_fatal_d(s, st, NULL); }

/* Bytes of the current unsynced search that count as lead: everything accepted since it began, capped at the window.
 * Call with s->mu held. */
static uint64_t unsynced_span(const pk_stream *s) {
    if (s->synced || s->bytes <= s->search_start) return 0;
    uint64_t span = s->bytes - s->search_start;
    return span < s->search_cap ? span : s->search_cap;
}

static int should_quit(pk_stream *s) {
    pthread_mutex_lock(&s->mu);
    int q = s->stop || s->fatal != PK_OK;
    pthread_mutex_unlock(&s->mu);
    return q;
}

/* Syncs one chunk covering stream bytes [off, off + n). While searching, first drops the segment's skip words (TLB strip 0, RE 30 sec 2.2.1), then looks for the
 * first word with bit 0 set (words on the stream's own word grid, even byte offsets from capture start) inside the remaining window (no window in resync mode);
 * once a line start is found, every later line start at exactly line_bytes must have bit 0 set. *used is the bytes checked under one line grid: n, or in resync mode
 * the offset of a line start that lacks bit 0 (*broke = 1; the caller restarts the search there, as TLB FUN_1001d170 does at 0x1001d2b0). Returns PK_OK or
 * PK_E_LOST_SYNC. */
static pk_status sync_chunk(pk_stream *s, pks_search *se, const uint8_t *buf, size_t n, uint64_t off, size_t *used, int *broke, char *dg, size_t dgn) {
    size_t i = 0, lb = s->line_bytes;
    int seg_oom = 0;
    *used = n;
    *broke = 0;
    if (!s->synced) {
        i = (size_t)(off & 1u);
        for (; i < n && se->skip; i += 2) se->skip--;
        for (; i < n && (s->resync || se->left); i += 2) {
            if (!(buf[i] & 1u)) { if (!s->resync) se->left--; continue; }
            pthread_mutex_lock(&s->mu);
            s->origin = off + i;
            s->lead_bytes += s->origin - s->search_start;
            s->synced = 1;
            /* the segment's first synced line: where TLB's loop head initialises the kernel; indexed by segment, so an unsynced segment never shifts a later one.
             * A resync inside a segment keeps the segment's first line start. */
            if (s->tap_seg >= s->seg_cap) {
                unsigned nc = s->seg_cap ? s->seg_cap * 2 : 16;
                while (nc <= s->tap_seg) nc *= 2;
                uint64_t *a = (uint64_t *)realloc(s->seg_off, nc * sizeof *a), *b = (uint64_t *)realloc(s->seg_line, nc * sizeof *b);
                if (a) s->seg_off = a;
                if (b) s->seg_line = b;
                if (a && b) { for (unsigned k = s->seg_cap; k < nc; k++) s->seg_off[k] = UINT64_MAX; s->seg_cap = nc; }
            }
            if (s->tap_seg < s->seg_cap) {
                if (s->seg_off[s->tap_seg] == UINT64_MAX) {
                    s->seg_off[s->tap_seg] = s->origin; s->seg_line[s->tap_seg] = s->lines_base;
                    if (s->tap_seg >= s->seg_n) s->seg_n = s->tap_seg + 1;
                }
            } else seg_oom = 1;
            pthread_mutex_unlock(&s->mu);
            if (seg_oom) { snprintf(dg, dgn, "out of memory recording the segment start"); return PK_E_NOMEM; }
            break;
        }
        if (!s->synced) {
            if (s->resync || se->left) return PK_OK;   /* window not used up: keep searching in the next chunk */
            snprintf(dg, dgn, "first line start not found within %u words of the search start", PKS_SYNC_WINDOW_WORDS);
            return PK_E_LOST_SYNC;
        }
    } else {
        i = (size_t)((lb - (off - s->origin) % lb) % lb);   /* distance to the next line start */
    }
    for (; i < n; i += lb)
        if (!(buf[i] & 1u)) {
            if (s->resync) { *used = i; *broke = 1; return PK_OK; }
            snprintf(dg, dgn, "line sync lost: no line-start bit at stream byte %llu", (unsigned long long)(off + i));
            return PK_E_LOST_SYNC;
        }
    return PK_OK;
}

/* Resync mode: the line grid ended at stream byte pos (a line start without bit 0). Its whole lines are counted, and the search restarts at pos (reader thread). */
static void restart_search(pk_stream *s, uint64_t pos) {
    pthread_mutex_lock(&s->mu);
    uint64_t seg = pos - s->origin;
    s->lines_base += seg / s->line_bytes;
    s->lead_bytes += seg % s->line_bytes;
    s->synced = 0;
    s->search_start = pos;
    pthread_mutex_unlock(&s->mu);
    s->tap_next = TAP_UNSET;
    s->pend_fill = 0;
}

/* Delivers the complete lines of the bytes [off, off + n) that the sync check has accepted (reader thread only). A line that straddles two chunks is
 * assembled in pend. Bytes before tap_next (a skipped search, or the part of a line the chunk does not hold) are never delivered. */
static void tap_lines(pk_stream *s, const uint8_t *buf, size_t n, uint64_t off) {
    size_t lb = s->line_bytes;
    if (s->tap_next == TAP_UNSET) {
        pthread_mutex_lock(&s->mu);
        int synced = s->synced;
        uint64_t origin = s->origin, base = s->lines_base;
        pthread_mutex_unlock(&s->mu);
        if (!synced) return;
        s->tap_next = origin;
        s->tap_line = base;
        s->pend_fill = 0;
    }
    uint64_t end = off + n;
    while (s->tap_next + lb <= end || s->pend_fill) {
        if (s->pend_fill) {                          /* the head of this line came in an earlier chunk; its next byte is at off */
            size_t need = lb - s->pend_fill;
            if (need > n) { memcpy(s->pend + s->pend_fill, buf, n); s->pend_fill += n; return; }
            memcpy(s->pend + s->pend_fill, buf, need);
            s->line_cb(s->line_user, s->tap_seg, s->tap_line, s->tap_next, s->pend);
            s->tap_next += lb;
            s->tap_line++;
            s->pend_fill = 0;
            /* the rest of the chunk starts at buf + need: fall through to the whole lines below, now relative to that */
            buf += need; n -= need; off += need;
            end = off + n;
            continue;
        }
        if (s->tap_next < off) return;               /* cannot happen on a synced grid; never read before the chunk */
        s->line_cb(s->line_user, s->tap_seg, s->tap_line, s->tap_next, buf + (s->tap_next - off));
        s->tap_next += lb;
        s->tap_line++;
    }
    if (s->tap_next < end) {                         /* a partial line at the end of this chunk */
        s->pend_fill = (size_t)(end - s->tap_next);
        memcpy(s->pend, buf + (s->tap_next - off), s->pend_fill);
    }
}

static void *reader_main(void *arg) {
    pk_stream *s = (pk_stream *)arg;
    uint8_t *chunk = (uint8_t *)malloc(PKS_CHUNK);
    if (!chunk) { set_fatal(s, PK_E_NOMEM); return NULL; }
    pks_search se = { PKS_SYNC_WINDOW_WORDS, s->skip0_words };
    char dg[96];
    while (!should_quit(s)) {
        size_t got = 0;
        pk_status st = pk_t_stream_read(s->t, chunk, PKS_CHUNK, &got, s->timeout_ms);
        if (st == PK_E_TIMEOUT && !got) continue;
        if (got > PKS_CHUNK) got = PKS_CHUNK;
        pthread_mutex_lock(&s->mu);
        if (s->rearm) {                /* a new strip: search again from the next byte received */
            s->rearm = 0;
            if (s->synced) {
                uint64_t seg = s->bytes - s->origin;
                s->lines_base += seg / s->line_bytes;
                s->lead_bytes += seg % s->line_bytes;
            } else {
                s->lead_bytes += unsynced_span(s);   /* words of an unfinished search */
            }
            s->synced = 0;
            if (s->bytes & 1u) s->lead_bytes++;      /* keep the word grid of stream byte 0: the stray byte is lead */
            s->search_start = (s->bytes + 1) & ~(uint64_t)1;
            se.left = PKS_SYNC_WINDOW_WORDS;
            se.skip = 0;                             /* later strips search from their first packet (RE 30 sec 2.2.1) */
            s->search_cap = s->resync ? UINT64_MAX : (uint64_t)PKS_SYNC_WINDOW_WORDS * 2;
            s->tap_next = TAP_UNSET;               /* the tap restarts with the new segment; a half-delivered line is lead */
            s->pend_fill = 0;
            s->tap_seg++;
        }
        uint64_t off = s->bytes;       /* only this thread writes bytes */
        pthread_mutex_unlock(&s->mu);
        if (got) {
            size_t put = pkr_write(s->ring, chunk, got);   /* the raw file keeps every byte, skipped or not */
            dg[0] = 0;
            pk_status sy = PK_OK;
            for (size_t at = 0; at < put && sy == PK_OK;) {   /* only the bytes the ring took; one piece per line grid */
                size_t used = 0;
                int broke = 0;
                sy = sync_chunk(s, &se, chunk + at, put - at, off + at, &used, &broke, dg, sizeof dg);
                if (s->line_cb && sy == PK_OK) tap_lines(s, chunk + at, used, off + at);
                if (sy == PK_OK && broke) restart_search(s, off + at + used);
                at += used;
            }
            pthread_mutex_lock(&s->mu);
            s->bytes += put;
            pthread_mutex_unlock(&s->mu);
            if (put < got) set_fatal_d(s, PK_E_STREAM_OVERFLOW, "ring overflow: the writer fell behind the scanner");
            else if (sy != PK_OK) set_fatal_d(s, sy, dg);
        }
        if (st != PK_OK && st != PK_E_TIMEOUT) set_fatal(s, st);   /* data delivered with an error is kept above */
    }
    free(chunk);
    return NULL;
}

static void *writer_main(void *arg) {
    pk_stream *s = (pk_stream *)arg;
    uint8_t *chunk = (uint8_t *)malloc(PKS_CHUNK);
    if (!chunk) { set_fatal(s, PK_E_NOMEM); return NULL; }
    uint64_t since_flush = 0;
    int failed = 0;
    for (;;) {
        size_t n = pkr_read(s->ring, chunk, PKS_CHUNK, PKS_WRITER_WAIT_MS);
        if (!n) {
            if (pkr_drained(s->ring)) break;
            continue;
        }
        if (!s->raw || failed) continue;   /* keep draining so the reader is never starved by a dead file */
        if (fwrite(chunk, 1, n, s->raw) != n) { failed = 1; set_fatal(s, PK_E_IO); continue; }
        since_flush += n;
        if (since_flush >= PKS_FLUSH_EVERY) {
            since_flush = 0;
            if (fflush(s->raw)) { failed = 1; set_fatal(s, PK_E_IO); }
        }
    }
    free(chunk);
    return NULL;
}

pk_status pk_stream_start(pk_transport *t, const pk_stream_cfg *cfg, pk_stream **out) {
    if (out) *out = NULL;
    if (!t || !cfg || !out || !cfg->words_per_line) return PK_E_ARG;
    pk_stream *s = (pk_stream *)calloc(1, sizeof *s);
    if (!s) return PK_E_NOMEM;
    s->t = t;
    s->line_bytes = (size_t)cfg->words_per_line * 2;
    s->timeout_ms = cfg->read_timeout_ms ? cfg->read_timeout_ms : 100;
    s->skip0_words = cfg->first_skip_words;
    s->resync = cfg->resync ? 1 : 0;
    s->search_cap = s->resync ? UINT64_MAX : ((uint64_t)PKS_SYNC_WINDOW_WORDS + cfg->first_skip_words) * 2;
    s->line_cb = cfg->line_cb;
    s->line_user = cfg->line_user;
    s->tap_next = TAP_UNSET;
    if (s->line_cb) {
        s->pend = (uint8_t *)malloc(s->line_bytes);
        if (!s->pend) { free(s); return PK_E_NOMEM; }
    }
    pthread_mutex_init(&s->mu, NULL);
    s->ring = pkr_new(cfg->ring_bytes ? cfg->ring_bytes : PKS_DEFAULT_RING);
    pk_status st = PK_E_NOMEM;
    if (!s->ring) goto fail;
    if (cfg->raw_path) {
        s->raw = fopen(cfg->raw_path, "wb");
        if (!s->raw) { st = PK_E_IO; goto fail; }
    }
    if (pthread_create(&s->writer, NULL, writer_main, s)) { st = PK_E_NOMEM; goto fail; }
    if (pthread_create(&s->reader, NULL, reader_main, s)) {
        pkr_close(s->ring);
        pthread_join(s->writer, NULL);
        st = PK_E_NOMEM;
        goto fail;
    }
    s->started = 1;
    *out = s;
    return PK_OK;
fail:
    if (s->raw) fclose(s->raw);
    pkr_free(s->ring);
    pthread_mutex_destroy(&s->mu);
    free(s->pend);
    free(s);
    return st;
}

pk_status pk_stream_poll(pk_stream *s, uint64_t *bytes, uint64_t *lines) {
    if (!s) return PK_E_ARG;
    pthread_mutex_lock(&s->mu);
    if (bytes) *bytes = s->bytes;
    if (lines) *lines = s->lines_base + (s->synced && s->bytes > s->origin ? (s->bytes - s->origin) / s->line_bytes : 0);
    pk_status st = s->fatal;
    pthread_mutex_unlock(&s->mu);
    return st;
}

pk_status pk_stream_stop(pk_stream *s, uint64_t *total_bytes) {
    if (!s) return PK_E_ARG;
    if (s->started && !s->joined) {
        pthread_mutex_lock(&s->mu);
        s->stop = 1;
        pthread_mutex_unlock(&s->mu);
        pthread_join(s->reader, NULL);
        pkr_close(s->ring);
        pthread_join(s->writer, NULL);
        s->joined = 1;
        if (s->raw) {
            if (fflush(s->raw)) set_fatal(s, PK_E_IO);
            if (fclose(s->raw)) set_fatal(s, PK_E_IO);
            s->raw = NULL;
        }
        if (pkr_overflowed(s->ring)) set_fatal(s, PK_E_STREAM_OVERFLOW);
    }
    return pk_stream_poll(s, total_bytes, NULL);
}

unsigned pk_stream_tail_words(const pk_stream *cs) {
    pk_stream *s = (pk_stream *)cs;
    if (!s) return 0;
    pthread_mutex_lock(&s->mu);
    unsigned w = s->synced && s->bytes > s->origin ? (unsigned)(((s->bytes - s->origin) % s->line_bytes) / 2) : 0;
    pthread_mutex_unlock(&s->mu);
    return w;
}

uint64_t pk_stream_lead_words(const pk_stream *cs) {
    pk_stream *s = (pk_stream *)cs;
    if (!s) return 0;
    pthread_mutex_lock(&s->mu);
    uint64_t w = (s->lead_bytes + unsynced_span(s)) / 2;
    pthread_mutex_unlock(&s->mu);
    return w;
}

void pk_stream_diag(const pk_stream *cs, char *buf, size_t cap) {
    pk_stream *s = (pk_stream *)cs;
    if (!buf || !cap) return;
    buf[0] = 0;
    if (!s) return;
    pthread_mutex_lock(&s->mu);
    snprintf(buf, cap, "%s", s->diag);
    pthread_mutex_unlock(&s->mu);
}

pk_status pk_stream_segment_start(const pk_stream *cs, unsigned segment, uint64_t *byte_offset, uint64_t *line) {
    pk_stream *s = (pk_stream *)cs;
    if (!s) return PK_E_ARG;
    pthread_mutex_lock(&s->mu);
    pk_status st = segment < s->seg_n && s->seg_off[segment] != UINT64_MAX ? PK_OK : PK_E_NOT_FOUND;
    if (st == PK_OK) { if (byte_offset) *byte_offset = s->seg_off[segment]; if (line) *line = s->seg_line[segment]; }
    pthread_mutex_unlock(&s->mu);
    return st;
}

pk_status pk_stream_rearm_sync(pk_stream *s) {
    if (!s) return PK_E_ARG;
    pthread_mutex_lock(&s->mu);
    s->rearm = 1;
    pthread_mutex_unlock(&s->mu);
    return PK_OK;
}

void pk_stream_free(pk_stream *s) {
    if (!s) return;
    pk_stream_stop(s, NULL);
    pkr_free(s->ring);
    pthread_mutex_destroy(&s->mu);
    free(s->seg_off); free(s->seg_line);
    free(s->pend);
    free(s);
}
