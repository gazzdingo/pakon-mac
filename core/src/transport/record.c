#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "transport/trace.h"
#include "link/guard.h"
#include "util/util.h"

typedef struct {
    pk_transport *inner;
    FILE *ev, *st;
    pthread_mutex_t mu;   /* the stream thread and the link thread both write */
    uint64_t t0_us;
    size_t stream_off;
    int failed;           /* latched by the first trace write error (guarded by mu) */
    char dir[1100];
} rec;

static uint64_t now_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000u + (uint64_t)ts.tv_nsec / 1000u;
}

static uint64_t rel_us(const rec *r) { return now_us() - r->t0_us; }

static void inherit_diag(pk_transport *t, const rec *r) {
    memcpy(t->diag, r->inner->diag, sizeof t->diag);
    t->diag[sizeof t->diag - 1] = 0;
}

static void inherit_sdiag(pk_transport *t, const rec *r) {
    memcpy(t->sdiag, r->inner->sdiag, sizeof t->sdiag);
    t->sdiag[sizeof t->sdiag - 1] = 0;
}

/* Latches the recorder and leaves a FAILED marker (best effort) so replay refuses the incomplete trace. Caller holds mu. */
static void latch_failed(rec *r) {
    r->failed = 1;
    char p[1200];
    if (snprintf(p, sizeof p, "%s/FAILED", r->dir) < (int)sizeof p) {
        FILE *f = fopen(p, "w");
        if (f) { fputs("a trace write failed; this trace is incomplete\n", f); fclose(f); }
    }
}

/* Writes one event under the lock. A trace that cannot be written is an error even when the transfer worked, and
 * after the first such error nothing more is written (every call returns PK_E_IO). `diag` is the caller's buffer. */
static pk_status emit(char *diag, size_t diag_cap, rec *r, pkt_event *e, const uint8_t *stream_bytes) {
    pk_status s;
    pthread_mutex_lock(&r->mu);
    if (r->failed) {
        pthread_mutex_unlock(&r->mu);
        snprintf(diag, diag_cap, "trace: recorder failed earlier, trace is incomplete");
        return PK_E_IO;
    }
    if (stream_bytes && e->len) {
        e->off = r->stream_off;
        if (fwrite(stream_bytes, 1, e->len, r->st) != e->len || fflush(r->st)) {
            latch_failed(r);
            pthread_mutex_unlock(&r->mu);
            snprintf(diag, diag_cap, "trace: cannot write stream.bin");
            return PK_E_IO;
        }
        r->stream_off += e->len;
    } else if (e->kind == PKT_STREAM) {
        e->off = r->stream_off;
    }
    s = pkt_write_event(r->ev, e);
    if (s != PK_OK) latch_failed(r);
    pthread_mutex_unlock(&r->mu);
    if (s != PK_OK) snprintf(diag, diag_cap, "trace: cannot write events.jsonl");
    return s;
}

static pk_status rec_bulk_out(pk_transport *t, uint8_t ep, const uint8_t *d, size_t n, unsigned to) {
    rec *r = (rec *)t->impl;
    if ((n && !d) || n > PK_TRANSPORT_MAX_XFER) return PK_E_ARG;
    pkt_event e;
    memset(&e, 0, sizeof e);
    e.kind = PKT_BULK_OUT; e.ep = ep; e.req = e.rt = e.val = e.idx = -1;
    e.t_us = rel_us(r);
    pk_status s = pk_t_bulk_out(r->inner, ep, d, n, to);
    e.status = (int)s; e.len = n; e.data = n ? (uint8_t *)d : NULL;
    if (s != PK_OK) inherit_diag(t, r);
    pk_status w = emit(t->diag, sizeof t->diag, r, &e, NULL);
    return s != PK_OK ? s : w;
}

static pk_status rec_bulk_in(pk_transport *t, uint8_t ep, uint8_t *d, size_t cap, size_t *got, unsigned to) {
    rec *r = (rec *)t->impl;
    size_t g = 0;
    pkt_event e;
    memset(&e, 0, sizeof e);
    e.kind = PKT_BULK_IN; e.ep = ep; e.req = e.rt = e.val = e.idx = -1;
    e.t_us = rel_us(r);
    if (cap > PK_TRANSPORT_MAX_XFER) cap = PK_TRANSPORT_MAX_XFER;
    pk_status s = pk_t_bulk_in(r->inner, ep, d, cap, &g, to);
    if (s != PK_OK) { g = 0; inherit_diag(t, r); }
    if (g > cap) g = 0, s = s != PK_OK ? s : PK_E_TRANSPORT;
    if (got) *got = g;
    e.status = (int)s; e.len = g; e.data = g ? d : NULL;
    pk_status w = emit(t->diag, sizeof t->diag, r, &e, NULL);
    return s != PK_OK ? s : w;
}

static pk_status rec_control(pk_transport *t, uint8_t rt, uint8_t req, uint16_t val, uint16_t idx, uint8_t *d,
                             size_t n, unsigned to) {
    rec *r = (rec *)t->impl;
    if ((n && !d) || n > PK_TRANSPORT_MAX_XFER) return PK_E_ARG;
    pkt_event e;
    memset(&e, 0, sizeof e);
    e.kind = PKT_CONTROL; e.ep = -1; e.req = req; e.rt = rt; e.val = val; e.idx = idx;
    e.t_us = rel_us(r);
    pk_status s = pk_t_control(r->inner, rt, req, val, idx, d, n, to);
    e.status = (int)s; e.len = n;
    if (s != PK_OK) inherit_diag(t, r);
    if (rt & 0x80) {
        e.data = (s == PK_OK && n) ? d : NULL;
    } else if (req == 0xA0 && n > 16) {   /* FX2 RAM download: hash only */
        pku_sha256_hex(d, n, e.sha);
    } else {
        e.data = n ? d : NULL;
    }
    pk_status w = emit(t->diag, sizeof t->diag, r, &e, NULL);
    return s != PK_OK ? s : w;
}

static pk_status rec_stream(pk_transport *t, uint8_t *buf, size_t cap, size_t *got, unsigned to) {
    rec *r = (rec *)t->impl;
    size_t g = 0;
    if (cap > PK_TRANSPORT_MAX_XFER) cap = PK_TRANSPORT_MAX_XFER;
    pk_status s = pk_t_stream_read(r->inner, buf, cap, &g, to);
    if (s != PK_OK) { g = 0; if (s != PK_E_TIMEOUT) inherit_sdiag(t, r); }
    if (g > cap) g = 0, s = s != PK_OK ? s : PK_E_TRANSPORT;
    if (got) *got = g;
    if (s == PK_E_TIMEOUT) return s;   /* an idle poll is not an event: it would bloat the trace; replay ends in a timeout too */
    pkt_event e;
    memset(&e, 0, sizeof e);
    e.kind = PKT_STREAM; e.ep = 0x86; e.req = e.rt = e.val = e.idx = -1;
    e.t_us = rel_us(r);   /* arrival time */
    e.status = (int)s; e.len = g;
    pk_status w = emit(t->sdiag, sizeof t->sdiag, r, &e, g ? buf : NULL);
    return s != PK_OK ? s : w;
}

static pk_status rec_reopen(pk_transport *t, uint16_t vid, uint16_t pid, unsigned wait_ms) {
    rec *r = (rec *)t->impl;
    pkt_event e;
    memset(&e, 0, sizeof e);
    e.kind = PKT_REOPEN; e.ep = e.req = e.rt = -1; e.val = vid; e.idx = pid;
    e.t_us = rel_us(r);
    pk_status s = pk_t_reopen(r->inner, vid, pid, wait_ms);
    e.status = (int)s;
    if (s != PK_OK) inherit_diag(t, r);
    pk_status w = emit(t->diag, sizeof t->diag, r, &e, NULL);
    return s != PK_OK ? s : w;
}

static void rec_close(pk_transport *t) {
    rec *r = (rec *)t->impl;
    if (!r) return;
    if (r->inner) pk_transport_close(r->inner);
    if (r->ev) fclose(r->ev);
    if (r->st) fclose(r->st);
    pthread_mutex_destroy(&r->mu);
    free(r);
    t->impl = NULL;
}

static const pk_transport_ops REC_OPS = { rec_bulk_out, rec_bulk_in, rec_control, rec_stream, rec_reopen, rec_close };

/* Appends "key":"value" with " and \ escaped and control characters replaced; bounded by the caller's buffer. */
static void put_str(char *dst, size_t cap, size_t *w, const char *key, const char *v, size_t vmax) {
    size_t i = 0;
    *w += (size_t)snprintf(dst + *w, cap - *w, "\"%s\":\"", key);
    for (; i < vmax && v[i]; i++) {
        char c = v[i];
        if ((unsigned char)c < 0x20 || (unsigned char)c > 0x7e) c = '?';
        if (c == '"' || c == '\\') dst[(*w)++] = '\\';
        dst[(*w)++] = c;
    }
    *w += (size_t)snprintf(dst + *w, cap - *w, "\",");
}

static pk_status write_meta(const char *dir, const pk_trace_meta *m) {
    char buf[2048], path[1100];   /* worst case with every string fully escaped is about 1000 bytes */
    size_t w = 0;
    time_t now = time(NULL);
    struct tm tm;
    char iso[32] = "";
    if (gmtime_r(&now, &tm)) strftime(iso, sizeof iso, "%Y-%m-%dT%H:%M:%SZ", &tm);
    w += (size_t)snprintf(buf, sizeof buf, "{\"format\":%d,", PKT_FORMAT_VERSION);
    put_str(buf, sizeof buf, &w, "libpakon_version", m->libpakon_version, sizeof m->libpakon_version);
    put_str(buf, sizeof buf, &w, "model", m->model, sizeof m->model);
    put_str(buf, sizeof buf, &w, "host_os", m->host_os, sizeof m->host_os);
    int nfw = m->n_fw < 0 ? 0 : m->n_fw > 4 ? 4 : m->n_fw;
    w += (size_t)snprintf(buf + w, sizeof buf - w, "\"n_fw\":%d,", nfw);
    for (int i = 0; i < nfw; i++) {
        char key[16];
        snprintf(key, sizeof key, "fw_sha256_%d", i);
        put_str(buf, sizeof buf, &w, key, m->fw_sha256[i], 64);
    }
    put_str(buf, sizeof buf, &w, "start_utc", iso, sizeof iso);
    w += (size_t)snprintf(buf + w, sizeof buf - w, "\"start_unix\":%lld}\n", (long long)now);
    if (w >= sizeof buf) return PK_E_FORMAT;
    if (snprintf(path, sizeof path, "%s/meta.json", dir) >= (int)sizeof path) return PK_E_FORMAT;
    return pku_write_file_atomic(path, buf, w);
}

static pk_status create_excl(const char *dir, const char *name, FILE **out) {
    char path[1100];
    if (snprintf(path, sizeof path, "%s/%s", dir, name) >= (int)sizeof path) return PK_E_FORMAT;
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (fd < 0) return errno == EEXIST ? PK_E_ARG : PK_E_IO;
    *out = fdopen(fd, "wb");
    if (!*out) { close(fd); return PK_E_IO; }
    return PK_OK;
}

pk_status pk_transport_record_open(pk_transport *inner, const char *trace_dir, const pk_trace_meta *meta,
                                   pk_transport **out) {
    if (out) *out = NULL;
    if (!inner || !trace_dir || !meta || !out) return PK_E_ARG;
    /* An already-guarded inner (what pk_usb_open returns): the recorder goes UNDER the guard, so one guard (one load
     * window, one A4 state) stays outermost and the recorder sees exactly what the guard let through. Only a guard that
     * owns its inner can be re-wrapped; a borrowing guard cannot hand its inner to the recorder. */
    pk_transport *guard = NULL;
    if (pkl_guard_is_guarded(inner)) {
        guard = inner;
        inner = pkl_guard_peek_inner(guard);
        if (!inner) return PK_E_ARG;
    }
    pk_status s = pku_mkdirs(trace_dir);
    if (s != PK_OK) return s;
    rec *r = (rec *)calloc(1, sizeof *r);
    pk_transport *t = (pk_transport *)calloc(1, sizeof *t);
    if (!r || !t) { free(r); free(t); return PK_E_NOMEM; }
    s = create_excl(trace_dir, "events.jsonl", &r->ev);
    int made_ev = r->ev != NULL;
    if (s == PK_OK) s = create_excl(trace_dir, "stream.bin", &r->st);
    if (s == PK_OK) s = write_meta(trace_dir, meta);
    if (s != PK_OK) {
        if (r->ev) fclose(r->ev);
        if (r->st) fclose(r->st);
        if (made_ev) {   /* remove what this call created, so a retry is not refused */
            char p[1100];
            if (snprintf(p, sizeof p, "%s/events.jsonl", trace_dir) < (int)sizeof p) unlink(p);
            if (r->st && snprintf(p, sizeof p, "%s/stream.bin", trace_dir) < (int)sizeof p) unlink(p);
        }
        free(r); free(t);
        return s;
    }
    pthread_mutex_init(&r->mu, NULL);
    snprintf(r->dir, sizeof r->dir, "%s", trace_dir);
    r->inner = inner;
    r->t0_us = now_us();
    t->ops = &REC_OPS;
    t->impl = r;
    if (guard) {
        pkl_guard_set_inner(guard, t);   /* the guard now holds the recorder, which owns the old inner */
        *out = guard;
        return PK_OK;
    }
    s = pkt_seal(t, out);
    if (s != PK_OK) {
        r->inner = NULL;   /* the caller keeps inner on failure */
        pk_transport_close(t);
        const char *const names[] = { "events.jsonl", "stream.bin", "meta.json" };
        for (int k = 0; k < 3; k++) {
            char p[1200];
            if (snprintf(p, sizeof p, "%s/%s", trace_dir, names[k]) < (int)sizeof p) unlink(p);
        }
    }
    return s;
}
