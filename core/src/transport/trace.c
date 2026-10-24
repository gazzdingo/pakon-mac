#define _POSIX_C_SOURCE 200809L
#include "transport/trace.h"
#include "link/guard.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include "util/util.h"

static const char *const OPS[] = { "bulk_out", "bulk_in", "control", "stream", "reopen" };

const char *pkt_op_name(int kind) { return kind >= 0 && kind <= PKT_REOPEN ? OPS[kind] : "?"; }

pk_status pkt_seal(pk_transport *raw, pk_transport **out) {
    return pkl_guard_adopt(raw, out);   /* ruling C4: the guard now holds raw for good */
}

void pk_transport_close(pk_transport *t) {
    if (!t) return;
    if (t->ops && t->ops->close) t->ops->close(t);
    free(t);
}

void pkt_free_events(pkt_event *events, size_t n) {
    if (!events) return;
    for (size_t i = 0; i < n; i++) free(events[i].data);
    free(events);
}

static int is_hex64(const char *s) {
    size_t i = 0;
    for (; s[i]; i++) {
        char c = s[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) return 0;
    }
    return i == 64;
}

/* Integer field in [lo, hi], or `absent` if the key is missing. Sets *bad on a wrong type / out of range. */
static long long num(const pku_jl_kv *kv, int n, const char *key, long long lo, long long hi, long long absent,
                     int *bad) {
    const pku_jl_kv *e = pku_jl_get(kv, n, key);
    if (!e) return absent;
    if (e->is_str || e->n < lo || e->n > hi) { *bad = 1; return absent; }
    return e->n;
}

static pk_status parse_event(char *line, size_t seq, uint64_t stream_len, pkt_event *ev) {
    pku_jl_kv kv[16];
    int n = pku_jl_parse(line, kv, 16), bad = 0;
    if (n < 0) return PK_E_CORRUPT;
    memset(ev, 0, sizeof *ev);
    ev->seq = seq;
    const pku_jl_kv *op = pku_jl_get(kv, n, "op");
    if (!op || !op->is_str) return PK_E_CORRUPT;
    ev->kind = -1;
    for (int i = 0; i <= PKT_REOPEN; i++)
        if (strcmp(op->s, OPS[i]) == 0) ev->kind = i;
    if (ev->kind < 0) return PK_E_CORRUPT;
    strcpy(ev->op, OPS[ev->kind]);
    ev->t_us = (uint64_t)num(kv, n, "t_us", 0, INT64_MAX, -1, &bad);
    long long len = num(kv, n, "len", 0, (long long)PKT_MAX_LEN, -1, &bad);
    long long status = num(kv, n, "status", 0, PK_E__COUNT - 1, -1, &bad);
    ev->ep = (int)num(kv, n, "ep", 0, 255, -1, &bad);
    ev->req = (int)num(kv, n, "req", 0, 255, -1, &bad);
    ev->rt = (int)num(kv, n, "rt", 0, 255, -1, &bad);
    ev->val = (int)num(kv, n, "val", 0, 65535, -1, &bad);
    ev->idx = (int)num(kv, n, "idx", 0, 65535, -1, &bad);
    long long off = num(kv, n, "off", 0, INT64_MAX, -1, &bad);
    if (bad || len < 0 || status < 0 || !pku_jl_get(kv, n, "t_us")) return PK_E_CORRUPT;
    ev->len = (size_t)len;
    ev->status = (int)status;
    ev->off = (size_t)(off < 0 ? 0 : off);

    const pku_jl_kv *d = pku_jl_get(kv, n, "data"), *sh = pku_jl_get(kv, n, "sha256");
    if ((d && !d->is_str) || (sh && !sh->is_str) || (d && sh)) return PK_E_CORRUPT;
    if (sh) {
        if (!is_hex64(sh->s)) return PK_E_CORRUPT;
        strcpy(ev->sha, sh->s);
    }
    if (d) {
        size_t cap = ev->len ? ev->len : 1, got = 0;
        ev->data = (uint8_t *)malloc(cap);
        if (!ev->data) return PK_E_NOMEM;
        pk_status st = pku_b64_decode(d->s, strlen(d->s), ev->data, cap, &got);
        if (st != PK_OK) return st == PK_E_NOMEM ? st : PK_E_CORRUPT;
        if (got != ev->len) return PK_E_CORRUPT;
    }

    int ok = ev->status == PK_OK, payload = d || sh;
    switch (ev->kind) {
    case PKT_BULK_OUT:
        if (ev->ep < 0 || (ev->len && !payload)) return PK_E_CORRUPT;
        break;
    case PKT_BULK_IN:
        if (ev->ep < 0 || sh || (ok && ev->len && !d) || (!ok && ev->len)) return PK_E_CORRUPT;
        break;
    case PKT_CONTROL:
        if (ev->req < 0 || ev->rt < 0 || ev->val < 0 || ev->idx < 0) return PK_E_CORRUPT;
        if (ev->rt & 0x80) {   /* device to host: data only on success */
            if (sh || (ok && ev->len && !d) || (!ok && d)) return PK_E_CORRUPT;
        } else if (ev->len && !payload) {
            return PK_E_CORRUPT;
        }
        break;
    case PKT_STREAM:
        if (payload || off < 0 || (!ok && ev->len)) return PK_E_CORRUPT;
        if ((uint64_t)ev->off > stream_len || (uint64_t)ev->len > stream_len - (uint64_t)ev->off) return PK_E_CORRUPT;
        break;
    case PKT_REOPEN:
        if (ev->val < 0 || ev->idx < 0 || payload) return PK_E_CORRUPT;
        break;
    }
    return PK_OK;
}

pk_status pkt_stream_read(int fd, uint64_t off, uint8_t *buf, size_t len) {
    size_t done = 0;
    while (done < len) {
        ssize_t r = pread(fd, buf + done, len - done, (off_t)(off + done));
        if (r < 0 && errno == EINTR) continue;
        if (r < 0) return PK_E_IO;
        if (r == 0) return PK_E_CORRUPT;
        done += (size_t)r;
    }
    return PK_OK;
}

pk_status pkt_load(const char *dir, pkt_event **events, size_t *n, int *stream_fd, uint64_t *stream_size) {
    if (events) *events = NULL;
    if (n) *n = 0;
    if (stream_fd) *stream_fd = -1;
    if (stream_size) *stream_size = 0;
    if (!dir || !events || !n || !stream_fd || !stream_size) return PK_E_ARG;
    char path[1100];
    if (snprintf(path, sizeof path, "%s/FAILED", dir) >= (int)sizeof path) return PK_E_FORMAT;
    if (access(path, F_OK) == 0) return PK_E_CORRUPT;   /* the recorder hit a write error: the trace is incomplete */
    if (snprintf(path, sizeof path, "%s/stream.bin", dir) >= (int)sizeof path) return PK_E_FORMAT;
    int sfd = open(path, O_RDONLY);
    uint64_t sl = 0;
    if (sfd < 0 && errno != ENOENT && errno != ENOTDIR) return PK_E_IO;
    if (sfd >= 0) {
        struct stat sb;
        if (fstat(sfd, &sb) != 0 || !S_ISREG(sb.st_mode)) { close(sfd); return PK_E_IO; }
        sl = (uint64_t)sb.st_size;
    }
    if (snprintf(path, sizeof path, "%s/events.jsonl", dir) >= (int)sizeof path) { if (sfd >= 0) close(sfd); return PK_E_FORMAT; }
    FILE *f = fopen(path, "rb");
    if (!f) { if (sfd >= 0) close(sfd); return errno == ENOENT || errno == ENOTDIR ? PK_E_NOT_FOUND : PK_E_IO; }

    pk_status st = PK_OK;
    pkt_event *ev = NULL;
    size_t cnt = 0, cap = 0, seq = 0;
    char *line = NULL;
    size_t lcap = 0;
    st = PK_OK;
    for (;;) {
        errno = 0;
        ssize_t r = getline(&line, &lcap, f);
        if (r < 0) { if (ferror(f)) st = errno == ENOMEM ? PK_E_NOMEM : PK_E_IO; break; }
        if (memchr(line, 0, (size_t)r)) { st = PK_E_CORRUPT; break; }
        char *p = line;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (!*p) continue;
        if (cnt == cap) {
            size_t nc = cap ? cap * 2 : 256;
            if (nc > (size_t)-1 / sizeof *ev) { st = PK_E_NOMEM; break; }
            pkt_event *t = (pkt_event *)realloc(ev, nc * sizeof *ev);
            if (!t) { st = PK_E_NOMEM; break; }
            ev = t; cap = nc;
        }
        memset(&ev[cnt], 0, sizeof ev[cnt]);
        st = parse_event(line, seq++, sl, &ev[cnt]);
        if (st == PK_OK || ev[cnt].data) cnt++;   /* keep a partly built event so its data is freed */
        if (st != PK_OK) break;
    }
    free(line);
    fclose(f);
    if (st != PK_OK) { pkt_free_events(ev, cnt); if (sfd >= 0) close(sfd); return st; }
    *events = ev; *n = cnt; *stream_fd = sfd; *stream_size = sl;
    return PK_OK;
}

pk_status pkt_write_event(FILE *f, const pkt_event *e) {
    if (!f || !e) return PK_E_ARG;
    char *b64 = NULL;
    if (e->data) {
        size_t cap = 4 * ((e->len + 2) / 3) + 1;
        b64 = (char *)malloc(cap);
        if (!b64) return PK_E_NOMEM;
        if (e->len) pku_b64_encode(e->data, e->len, b64, cap); else b64[0] = 0;
    }
    int rc = fprintf(f, "{\"t_us\":%llu,\"op\":\"%s\"", (unsigned long long)e->t_us, pkt_op_name(e->kind));
    if (rc >= 0) {
        switch (e->kind) {
        case PKT_BULK_OUT: case PKT_BULK_IN: rc = fprintf(f, ",\"ep\":%d", e->ep); break;
        case PKT_CONTROL: rc = fprintf(f, ",\"req\":%d,\"rt\":%d,\"val\":%d,\"idx\":%d", e->req, e->rt, e->val, e->idx); break;
        case PKT_REOPEN: rc = fprintf(f, ",\"val\":%d,\"idx\":%d", e->val, e->idx); break;
        default: break;
        }
    }
    if (rc >= 0) rc = fprintf(f, ",\"len\":%zu,\"status\":%d", e->len, e->status);
    if (rc >= 0 && e->kind == PKT_STREAM) rc = fprintf(f, ",\"off\":%zu", e->off);
    else if (rc >= 0 && b64) rc = fprintf(f, ",\"data\":\"%s\"", b64);
    else if (rc >= 0 && e->sha[0]) rc = fprintf(f, ",\"sha256\":\"%s\"", e->sha);
    if (rc >= 0) rc = fputs("}\n", f);
    free(b64);
    if (rc < 0 || fflush(f)) return PK_E_IO;
    return PK_OK;
}
