#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>
#include <unistd.h>
#include "transport/trace.h"
#include "util/util.h"

typedef struct { pkt_event *ev; size_t n, cur; int have_prev; uint64_t prev_t; } queue;

typedef struct {
    queue link, stream;
    pkt_event *all;
    size_t n_all;
    int stream_fd;
    uint64_t stream_size;
    unsigned flags;
    pthread_mutex_t mu;   /* the stream thread and the link thread interleave non-deterministically */
} rep;

static void sleep_us(uint64_t us) {
    struct timespec ts;
    ts.tv_sec = (time_t)(us / 1000000u);
    ts.tv_nsec = (long)(us % 1000000u) * 1000L;
    while (nanosleep(&ts, &ts) != 0) {}
}

/* Advances the queue and returns the delay to honour (0 unless PK_REPLAY_REALTIME). Caller holds the lock. */
static uint64_t advance(rep *r, queue *q) {
    const pkt_event *e = &q->ev[q->cur++];
    uint64_t d = 0;
    if ((r->flags & PK_REPLAY_REALTIME) && q->have_prev && e->t_us > q->prev_t) d = e->t_us - q->prev_t;
    q->have_prev = 1;
    q->prev_t = e->t_us;
    return d;
}

static pk_status mismatch(pk_transport *t, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static pk_status mismatch(pk_transport *t, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(t->diag, sizeof t->diag, fmt, ap);
    va_end(ap);
    return PK_E_REPLAY_MISMATCH;
}

/* The next link event, which must be `kind`. Caller holds the lock. */
static pk_status peek_link(pk_transport *t, rep *r, int kind, const pkt_event **out) {
    if (r->link.cur >= r->link.n)
        return mismatch(t, "trace exhausted after %zu link events; got %s", r->link.n, pkt_op_name(kind));
    const pkt_event *e = &r->link.ev[r->link.cur];
    if (e->kind != kind)
        return mismatch(t, "event %zu: trace has %s, got %s", e->seq, pkt_op_name(e->kind), pkt_op_name(kind));
    *out = e;
    return PK_OK;
}

/* An outbound payload must equal the recorded one (bytes, or the recorded sha256). */
static pk_status match_out(pk_transport *t, const pkt_event *e, const uint8_t *d, size_t n) {
    if (e->data) {
        size_t m = e->len < n ? e->len : n, i = 0;
        while (i < m && e->data[i] == d[i]) i++;
        if (i < m)
            return mismatch(t, "event %zu (%s): first difference at offset %zu: recorded 0x%02x, got 0x%02x",
                            e->seq, e->op, i, e->data[i], d[i]);
        if (e->len != n) {
            if (n > e->len)
                return mismatch(t, "event %zu (%s): got %zu bytes, recorded %zu; first difference at offset %zu: recorded end, got 0x%02x",
                                e->seq, e->op, n, e->len, m, d[m]);
            return mismatch(t, "event %zu (%s): got %zu bytes, recorded %zu; first difference at offset %zu: recorded 0x%02x, got end",
                            e->seq, e->op, n, e->len, m, e->data[m]);
        }
    } else {
        if (e->len != n) return mismatch(t, "event %zu (%s): got %zu bytes, recorded %zu", e->seq, e->op, n, e->len);
        if (e->sha[0]) {
            char h[65];
            pku_sha256_hex(d ? d : (const uint8_t *)"", n, h);
            if (strcasecmp(h, e->sha))
                return mismatch(t, "event %zu (%s): sha256 %s, recorded %s", e->seq, e->op, h, e->sha);
        }
    }
    return PK_OK;
}

static pk_status rp_bulk_out(pk_transport *t, uint8_t ep, const uint8_t *d, size_t n, unsigned to) {
    (void)to;
    rep *r = (rep *)t->impl;
    if (n && !d) return PK_E_ARG;
    const pkt_event *e;
    pthread_mutex_lock(&r->mu);
    pk_status s = peek_link(t, r, PKT_BULK_OUT, &e);
    if (s == PK_OK && e->ep != ep) s = mismatch(t, "event %zu: bulk_out endpoint 0x%02x, recorded 0x%02x", e->seq, ep, e->ep);
    if (s == PK_OK) s = match_out(t, e, d, n);
    uint64_t delay = 0;
    pk_status rec = PK_OK;
    if (s == PK_OK) { rec = (pk_status)e->status; delay = advance(r, &r->link); }
    pthread_mutex_unlock(&r->mu);
    if (s == PK_OK && delay) sleep_us(delay);
    return s != PK_OK ? s : rec;
}

static pk_status rp_bulk_in(pk_transport *t, uint8_t ep, uint8_t *d, size_t cap, size_t *got, unsigned to) {
    (void)to;
    rep *r = (rep *)t->impl;
    if (got) *got = 0;
    const pkt_event *e;
    pthread_mutex_lock(&r->mu);
    pk_status s = peek_link(t, r, PKT_BULK_IN, &e);
    if (s == PK_OK && e->ep != ep) s = mismatch(t, "event %zu: bulk_in endpoint 0x%02x, recorded 0x%02x", e->seq, ep, e->ep);
    if (s == PK_OK && e->len > cap)
        s = mismatch(t, "event %zu: bulk_in buffer %zu bytes, recorded read of %zu", e->seq, cap, e->len);
    uint64_t delay = 0;
    pk_status rec = PK_OK;
    if (s == PK_OK) {
        rec = (pk_status)e->status;
        if (rec == PK_OK && e->len) memcpy(d, e->data, e->len);
        if (rec == PK_OK && got) *got = e->len;
        delay = advance(r, &r->link);
    }
    pthread_mutex_unlock(&r->mu);
    if (s == PK_OK && delay) sleep_us(delay);
    return s != PK_OK ? s : rec;
}

static pk_status rp_control(pk_transport *t, uint8_t rt, uint8_t req, uint16_t val, uint16_t idx, uint8_t *d,
                            size_t n, unsigned to) {
    (void)to;
    rep *r = (rep *)t->impl;
    if (n && !d) return PK_E_ARG;
    const pkt_event *e;
    pthread_mutex_lock(&r->mu);
    pk_status s = peek_link(t, r, PKT_CONTROL, &e);
    if (s == PK_OK && (e->rt != rt || e->req != req || e->val != val || e->idx != idx))
        s = mismatch(t, "event %zu: control rt=0x%02x req=0x%02x val=0x%04x idx=0x%04x, recorded rt=0x%02x req=0x%02x val=0x%04x idx=0x%04x",
                     e->seq, rt, req, val, idx, e->rt, e->req, e->val, e->idx);
    if (s == PK_OK && (rt & 0x80)) {
        if (e->len != n) s = mismatch(t, "event %zu: control read of %zu bytes, recorded %zu", e->seq, n, e->len);
    } else if (s == PK_OK) {
        s = match_out(t, e, d, n);
    }
    uint64_t delay = 0;
    pk_status rec = PK_OK;
    if (s == PK_OK) {
        rec = (pk_status)e->status;
        if ((rt & 0x80) && rec == PK_OK && n) memcpy(d, e->data, n);
        delay = advance(r, &r->link);
    }
    pthread_mutex_unlock(&r->mu);
    if (s == PK_OK && delay) sleep_us(delay);
    return s != PK_OK ? s : rec;
}

static pk_status rp_stream(pk_transport *t, uint8_t *buf, size_t cap, size_t *got, unsigned to) {
    rep *r = (rep *)t->impl;
    if (got) *got = 0;
    pthread_mutex_lock(&r->mu);
    queue *q = &r->stream;
    if (q->cur >= q->n) {   /* recorded timeouts are not events, so an exhausted stream reads as an idle device */
        pthread_mutex_unlock(&r->mu);
        sleep_us((to < 10 ? to : 10) * 1000u);
        return PK_E_TIMEOUT;
    }
    const pkt_event *e = &q->ev[q->cur];   /* events are immutable: safe to use after unlocking */
    if (e->len > cap) {
        snprintf(t->sdiag, sizeof t->sdiag, "event %zu: stream buffer %zu bytes, recorded read of %zu", e->seq, cap, e->len);
        pthread_mutex_unlock(&r->mu);
        return PK_E_REPLAY_MISMATCH;
    }
    pk_status rec = (pk_status)e->status;
    uint64_t delay = advance(r, q);
    pthread_mutex_unlock(&r->mu);
    if (rec == PK_OK && e->len) {
        pk_status s = r->stream_fd >= 0 ? pkt_stream_read(r->stream_fd, e->off, buf, e->len) : PK_E_CORRUPT;
        if (s != PK_OK) {
            snprintf(t->sdiag, sizeof t->sdiag, "event %zu: cannot read stream.bin at offset %zu", e->seq, e->off);
            return s;
        }
    }
    if (rec == PK_OK && got) *got = e->len;
    if (delay) sleep_us(delay);
    return rec;
}

static pk_status rp_reopen(pk_transport *t, uint16_t vid, uint16_t pid, unsigned wait_ms) {
    (void)wait_ms;
    rep *r = (rep *)t->impl;
    const pkt_event *e;
    pthread_mutex_lock(&r->mu);
    pk_status s = peek_link(t, r, PKT_REOPEN, &e);
    if (s == PK_OK && (e->val != vid || e->idx != pid))
        s = mismatch(t, "event %zu: reopen %04x:%04x, recorded %04x:%04x", e->seq, vid, pid, e->val, e->idx);
    uint64_t delay = 0;
    pk_status rec = PK_OK;
    if (s == PK_OK) { rec = (pk_status)e->status; delay = advance(r, &r->link); }
    pthread_mutex_unlock(&r->mu);
    if (s == PK_OK && delay) sleep_us(delay);
    return s != PK_OK ? s : rec;
}

static void rp_close(pk_transport *t) {
    rep *r = (rep *)t->impl;
    if (!r) return;
    free(r->link.ev);
    free(r->stream.ev);
    pkt_free_events(r->all, r->n_all);
    if (r->stream_fd >= 0) close(r->stream_fd);
    pthread_mutex_destroy(&r->mu);
    free(r);
    t->impl = NULL;
}

static const pk_transport_ops REP_OPS = { rp_bulk_out, rp_bulk_in, rp_control, rp_stream, rp_reopen, rp_close };

static pk_status check_meta(const char *dir) {
    char path[1100];
    if (snprintf(path, sizeof path, "%s/meta.json", dir) >= (int)sizeof path) return PK_E_FORMAT;
    uint8_t *raw;
    size_t n;
    pk_status s = pku_read_file(path, &raw, &n);
    if (s != PK_OK) return s;
    char *z = (char *)realloc(raw, n + 1);   /* NUL-terminate for the parser */
    if (!z) { free(raw); return PK_E_NOMEM; }
    z[n] = 0;
    pku_jl_kv kv[24];
    int k = (n == strlen(z)) ? pku_jl_parse(z, kv, 24) : -1;
    const pku_jl_kv *f = k >= 0 ? pku_jl_get(kv, k, "format") : NULL;
    s = (f && !f->is_str && f->n == PKT_FORMAT_VERSION) ? PK_OK : PK_E_CORRUPT;
    free(z);
    return s;
}

pk_status pk_transport_replay_open(const char *trace_dir, unsigned flags, pk_transport **out) {
    if (out) *out = NULL;
    if (!trace_dir || !out || (flags & ~(unsigned)PK_REPLAY_REALTIME)) return PK_E_ARG;
    pk_status s = check_meta(trace_dir);
    if (s != PK_OK) return s;
    rep *r = (rep *)calloc(1, sizeof *r);
    pk_transport *t = (pk_transport *)calloc(1, sizeof *t);
    if (!r || !t) { free(r); free(t); return PK_E_NOMEM; }
    r->stream_fd = -1;
    pthread_mutex_init(&r->mu, NULL);
    s = pkt_load(trace_dir, &r->all, &r->n_all, &r->stream_fd, &r->stream_size);
    if (s == PK_OK) {
        /* the two queues are pointer-free copies split from the loaded array (data stays owned by r->all) */
        r->link.ev = (pkt_event *)malloc((r->n_all ? r->n_all : 1) * sizeof(pkt_event));
        r->stream.ev = (pkt_event *)malloc((r->n_all ? r->n_all : 1) * sizeof(pkt_event));
        if (!r->link.ev || !r->stream.ev) s = PK_E_NOMEM;
    }
    if (s != PK_OK) { rp_close(&(pk_transport){ .impl = r }); free(t); return s; }
    for (size_t i = 0; i < r->n_all; i++) {
        queue *q = r->all[i].kind == PKT_STREAM ? &r->stream : &r->link;
        q->ev[q->n++] = r->all[i];
    }
    r->flags = flags;
    t->ops = &REP_OPS;
    t->impl = r;
    s = pkt_seal(t, out);
    if (s != PK_OK) pk_transport_close(t);
    return s;
}
