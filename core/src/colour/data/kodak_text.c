#ifndef _GNU_SOURCE
#define _GNU_SOURCE                     /* strtod_l / newlocale on glibc; Darwin has them in <xlocale.h> */
#endif
#include "data/diag.h"
#include "data/kodak_text.h"
#include <ctype.h>
#include <errno.h>
#include <locale.h>
#include <math.h>
#include <pthread.h>
#ifdef __APPLE__
#include <xlocale.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Numbers are parsed with strtod_l against a private C-locale object (pkc_kt_parse_number): the host owns the process
 * locale (setlocale / a GUI toolkit), and a comma-decimal LC_NUMERIC would truncate every fractional Kodak value
 * ("2.25" -> 2) without any error. */

typedef struct { char *key; char **tok; int n, cap; } kt_entry;
struct pkc_kt { kt_entry *e; int n, cap; char ***views; int nviews; };

static char *dupn(const char *s, size_t n) {
    char *d = malloc(n + 1);
    if (!d) return NULL;
    memcpy(d, s, n); d[n] = 0;
    return d;
}

static pthread_once_t c_once = PTHREAD_ONCE_INIT;
static locale_t c_loc;
static void make_c_locale(void) { c_loc = newlocale(LC_ALL_MASK, "C", (locale_t)0); }

int pkc_kt_parse_number(const char *s, double *v) {
    if (!s || !v || !pkc_kt_is_number(s)) return 0;
    pthread_once(&c_once, make_c_locale);
    if (!c_loc) return 0;
    char *end = NULL;
    errno = 0;
    double d = strtod_l(s, &end, c_loc);
    if (errno != 0 || end != s + strlen(s) || !isfinite(d)) return 0;     /* the whole token, finite */
    *v = d;
    return 1;
}

/* Decimal numbers only: [+-]digits[.digits][(e|E)[+-]digits]. Rejects
 * nan/inf/hex that strtod would accept. (kodak_text.h; shared with fugc.c's .lut reader.) */
int pkc_kt_is_number(const char *s) {
    int digits = 0;
    if (*s == '+' || *s == '-') s++;
    while (isdigit((unsigned char)*s)) { s++; digits++; }
    if (*s == '.') { s++; while (isdigit((unsigned char)*s)) { s++; digits++; } }
    if (!digits) return 0;
    if (*s == 'e' || *s == 'E') {
        s++;
        if (*s == '+' || *s == '-') s++;
        if (!isdigit((unsigned char)*s)) return 0;
        while (isdigit((unsigned char)*s)) s++;
    }
    return *s == 0;
}

static pk_status entry_add_tok(kt_entry *e, const char *s, size_t n) {
    if (e->n == e->cap) {
        int nc = e->cap ? e->cap * 2 : 8;
        char **t = realloc(e->tok, (size_t)nc * sizeof *t);
        if (!t) return PK_E_NOMEM;
        e->tok = t; e->cap = nc;
    }
    char *d = dupn(s, n);
    if (!d) return PK_E_NOMEM;
    e->tok[e->n++] = d;
    return PK_OK;
}

void pkc_kt_free(pkc_kt *kt) {
    if (!kt) return;
    for (int i = 0; i < kt->n; i++) {
        for (int j = 0; j < kt->e[i].n; j++) free(kt->e[i].tok[j]);
        free(kt->e[i].tok); free(kt->e[i].key);
    }
    for (int i = 0; i < kt->nviews; i++) free(kt->views[i]);
    free(kt->views); free(kt->e); free(kt);
}

/* Split a (comment-stripped) line into tokens on whitespace and '='. */
static pk_status parse_line(pkc_kt *kt, const char *line, size_t len) {
    int has_eq = memchr(line, '=', len) != NULL;
    size_t i = 0;
    int first = 1;
    kt_entry *cur = NULL;
    /* Pre-scan: a line with no '=' is a continuation only if all numeric. */
    if (!has_eq) {
        if (kt->n == 0) return PK_OK;
        size_t j = i;
        while (j < len) {
            while (j < len && isspace((unsigned char)line[j])) j++;
            size_t s = j;
            while (j < len && !isspace((unsigned char)line[j])) j++;
            if (j > s) {
                char *t = dupn(line + s, j - s);
                if (!t) return PK_E_NOMEM;
                int ok = pkc_kt_is_number(t); free(t);
                if (!ok) return PK_OK;
            }
        }
        cur = &kt->e[kt->n - 1]; first = 0;
    }
    while (i < len) {
        while (i < len && (isspace((unsigned char)line[i]) || line[i] == '=')) i++;
        size_t s = i;
        while (i < len && !isspace((unsigned char)line[i]) && line[i] != '=') i++;
        if (i == s) break;
        if (first) {
            if (kt->n == kt->cap) {
                int nc = kt->cap ? kt->cap * 2 : 16;
                kt_entry *e = realloc(kt->e, (size_t)nc * sizeof *e);
                if (!e) return PK_E_NOMEM;
                kt->e = e; kt->cap = nc;
            }
            cur = &kt->e[kt->n];
            memset(cur, 0, sizeof *cur);
            cur->key = dupn(line + s, i - s);
            if (!cur->key) return PK_E_NOMEM;
            kt->n++;
            first = 0;
        } else {
            pk_status st = entry_add_tok(cur, line + s, i - s);
            if (st != PK_OK) return st;
        }
    }
    return PK_OK;
}

pk_status pkc_kt_load(const char *path, pkc_kt **out) {
    if (!path || !out) return PK_E_ARG;
    *out = NULL;
    FILE *f = pkc_fopen(path, "rb");
    if (!f) return PK_E_VENDOR_DATA;
    pkc_kt *kt = calloc(1, sizeof *kt);
    if (!kt) { fclose(f); return PK_E_NOMEM; }
    char *buf = NULL; size_t cap = 0, len = 0;
    pk_status st = PK_OK;
    int c;
    for (;;) {
        c = fgetc(f);
        if (c == EOF || c == '\n') {
            if (len || c != EOF) {
                size_t end = len;
                char *hash = memchr(buf ? buf : "", '#', len);
                if (hash) end = (size_t)(hash - buf);
                if (end) { st = parse_line(kt, buf, end); if (st != PK_OK) break; }
                len = 0;
            }
            if (c == EOF) break;
            continue;
        }
        if (c == '\r') continue;
        if (len + 1 > cap) {
            size_t nc = cap ? cap * 2 : 256;
            char *b = realloc(buf, nc);
            if (!b) { st = PK_E_NOMEM; break; }
            buf = b; cap = nc;
        }
        buf[len++] = (char)c;
    }
    int rerr = ferror(f);
    fclose(f); free(buf);
    if (st == PK_OK && (rerr || kt->n == 0)) st = PK_E_VENDOR_DATA;
    if (st != PK_OK) { pkc_kt_free(kt); return st; }
    *out = kt;
    return PK_OK;
}

static const kt_entry *find(const pkc_kt *kt, const char *key) {
    if (!kt || !key) return NULL;
    for (int i = 0; i < kt->n; i++)
        if (strcmp(kt->e[i].key, key) == 0) return &kt->e[i];
    return NULL;
}

const char *pkc_kt_str(const pkc_kt *kt, const char *key) {
    const kt_entry *e = find(kt, key);
    return e && e->n > 0 ? e->tok[0] : NULL;
}

int pkc_kt_num(const pkc_kt *kt, const char *key, double *vals, int max) {
    const kt_entry *e = find(kt, key);
    int n = 0;
    if (!e || !vals) return 0;
    for (int i = 0; i < e->n && n < max; i++) {
        double d;
        if (!pkc_kt_parse_number(e->tok[i], &d)) break;
        vals[n++] = d;
    }
    return n;
}

int pkc_kt_rows(const pkc_kt *kt, const char *key, char ***tokens, int *ncols) {
    int rows = 0, nc = 0;
    if (tokens) *tokens = NULL;
    if (ncols) *ncols = 0;
    if (!kt || !key || !tokens || !ncols) return 0;
    for (int i = 0; i < kt->n; i++)
        if (strcmp(kt->e[i].key, key) == 0) {
            rows++;
            if (kt->e[i].n > nc) nc = kt->e[i].n;
        }
    if (!rows || !nc) return rows;
    /* The flat view is owned by kt (freed in pkc_kt_free); const is cast away
     * only to register it. */
    pkc_kt *m = (pkc_kt *)kt;
    char **flat = calloc((size_t)rows * (size_t)nc, sizeof *flat);
    char ***vs = realloc(m->views, (size_t)(m->nviews + 1) * sizeof *vs);
    if (!vs || !flat) { free(flat); if (vs) m->views = vs; return 0; }
    m->views = vs; m->views[m->nviews++] = flat;
    int r = 0;
    for (int i = 0; i < kt->n; i++) {
        if (strcmp(kt->e[i].key, key) != 0) continue;
        for (int c = 0; c < nc; c++)
            flat[r * nc + c] = c < kt->e[i].n ? kt->e[i].tok[c] : (char *)"";
        r++;
    }
    *tokens = flat; *ncols = nc;
    return rows;
}

pk_status pkc_vendor_path(const char *vendor_root, const char *rel, char *out, size_t cap) {
    if (!vendor_root || !rel || !out || !cap) return PK_E_ARG;
    size_t a = strlen(vendor_root), b = strlen(rel);
    int slash = a && vendor_root[a - 1] != '/';
    if (a + (size_t)slash + b + 1 > cap) return PK_E_FORMAT;
    memcpy(out, vendor_root, a);
    if (slash) out[a] = '/';
    memcpy(out + a + slash, rel, b + 1);
    return PK_OK;
}

char *pkc_kt_next_token(char **cur) {
    char *s = *cur;
    while (*s == ' ' || *s == '\t' || *s == '\r' || *s == '\n') s++;
    if (!*s) { *cur = s; return NULL; }
    char *t = s;
    while (*s && *s != ' ' && *s != '\t' && *s != '\r' && *s != '\n') s++;
    if (*s) *s++ = 0;
    *cur = s;
    return t;
}
