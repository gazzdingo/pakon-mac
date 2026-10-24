#include "util/util.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PKU_JSON_MAX_DEPTH 32
#define PKU_JSON_MAX_BYTES ((size_t)64 << 20)

struct pku_json {
    pku_jtype type;
    int b, is_int;
    double d;
    long long i;
    char *s;
    size_t n, cap;
    char **keys;           /* objects only */
    struct pku_json **kids;
};

typedef struct { const char *p, *end; } jp;

void pku_json_free(pku_json *j) {
    if (!j) return;
    for (size_t k = 0; k < j->n; k++) {
        if (j->keys) free(j->keys[k]);
        pku_json_free(j->kids[k]);
    }
    free(j->keys);
    free(j->kids);
    free(j->s);
    free(j);
}

static void skip_ws(jp *p) {
    while (p->p < p->end && (*p->p == ' ' || *p->p == '\t' || *p->p == '\n' || *p->p == '\r')) p->p++;
}

static int hex4(const char *s, unsigned *out) {
    unsigned v = 0;
    for (int k = 0; k < 4; k++) {
        char c = s[k];
        v <<= 4;
        if (c >= '0' && c <= '9') v |= (unsigned)(c - '0');
        else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10);
        else return 0;
    }
    *out = v;
    return 1;
}

static size_t utf8(unsigned cp, char *o) {
    if (cp < 0x80) { o[0] = (char)cp; return 1; }
    if (cp < 0x800) { o[0] = (char)(0xC0 | (cp >> 6)); o[1] = (char)(0x80 | (cp & 0x3F)); return 2; }
    if (cp < 0x10000) {
        o[0] = (char)(0xE0 | (cp >> 12)); o[1] = (char)(0x80 | ((cp >> 6) & 0x3F)); o[2] = (char)(0x80 | (cp & 0x3F));
        return 3;
    }
    o[0] = (char)(0xF0 | (cp >> 18)); o[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
    o[2] = (char)(0x80 | ((cp >> 6) & 0x3F)); o[3] = (char)(0x80 | (cp & 0x3F));
    return 4;
}

/* p->p is at the opening quote; returns a malloc'd unescaped string. */
static pk_status parse_string(jp *p, char **out) {
    p->p++;
    const char *q = p->p;
    const char *close = q;                                   /* size the buffer to this string, not to the rest of the input */
    while (close < p->end && *close != '"') close += (*close == '\\' && close + 1 < p->end) ? 2 : 1;
    if (close >= p->end) return PK_E_CORRUPT;
    char *buf = (char *)malloc((size_t)(close - q) + 1);     /* unescaping never grows */
    if (!buf) return PK_E_NOMEM;
    size_t n = 0;
    while (q < p->end && *q != '"') {
        unsigned char c = (unsigned char)*q;
        if (c < 0x20) goto bad;
        if (c != '\\') { buf[n++] = (char)c; q++; continue; }
        if (++q >= p->end) goto bad;
        switch (*q) {
        case '"': buf[n++] = '"'; q++; break;
        case '\\': buf[n++] = '\\'; q++; break;
        case '/': buf[n++] = '/'; q++; break;
        case 'n': buf[n++] = '\n'; q++; break;
        case 't': buf[n++] = '\t'; q++; break;
        case 'u': {
            unsigned cp;
            if (p->end - q < 5 || !hex4(q + 1, &cp)) goto bad;
            q += 5;
            if (cp >= 0xD800 && cp < 0xDC00) {
                unsigned lo;
                if (p->end - q < 6 || q[0] != '\\' || q[1] != 'u' || !hex4(q + 2, &lo) || lo < 0xDC00 || lo > 0xDFFF) goto bad;
                cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                q += 6;
            } else if (cp >= 0xDC00 && cp <= 0xDFFF) goto bad;
            if (cp == 0) goto bad;
            n += utf8(cp, buf + n);
            break;
        }
        default: goto bad;
        }
    }
    if (q >= p->end) goto bad;
    buf[n] = 0;
    p->p = q + 1;
    *out = buf;
    return PK_OK;
bad:
    free(buf);
    return PK_E_CORRUPT;
}

static pk_status push(pku_json *c, char *key, pku_json *kid) {
    if (c->n == c->cap) {
        size_t nc = c->cap ? c->cap * 2 : 4;
        pku_json **nk = (pku_json **)realloc(c->kids, nc * sizeof *nk);
        if (!nk) return PK_E_NOMEM;
        c->kids = nk;
        if (c->type == PKU_J_OBJ) {
            char **nkeys = (char **)realloc(c->keys, nc * sizeof *nkeys);
            if (!nkeys) return PK_E_NOMEM;
            c->keys = nkeys;
        }
        c->cap = nc;
    }
    if (c->type == PKU_J_OBJ) c->keys[c->n] = key;
    c->kids[c->n++] = kid;
    return PK_OK;
}

static pk_status parse_value(jp *p, int depth, pku_json **out);

static pk_status parse_container(jp *p, int depth, pku_json *c) {
    char close = c->type == PKU_J_OBJ ? '}' : ']';
    p->p++;
    skip_ws(p);
    if (p->p < p->end && *p->p == close) { p->p++; return PK_OK; }
    for (;;) {
        char *key = NULL;
        pk_status st;
        skip_ws(p);
        if (c->type == PKU_J_OBJ) {
            if (p->p >= p->end || *p->p != '"') return PK_E_CORRUPT;
            if ((st = parse_string(p, &key)) != PK_OK) return st;
            skip_ws(p);
            if (p->p >= p->end || *p->p != ':') { free(key); return PK_E_CORRUPT; }
            p->p++;
        }
        pku_json *kid = NULL;
        if ((st = parse_value(p, depth + 1, &kid)) != PK_OK) { free(key); return st; }
        if ((st = push(c, key, kid)) != PK_OK) { free(key); pku_json_free(kid); return st; }
        skip_ws(p);
        if (p->p >= p->end) return PK_E_CORRUPT;
        if (*p->p == ',') { p->p++; continue; }
        if (*p->p == close) { p->p++; return PK_OK; }
        return PK_E_CORRUPT;
    }
}

static pk_status parse_value(jp *p, int depth, pku_json **out) {
    skip_ws(p);
    if (p->p >= p->end) return PK_E_CORRUPT;
    pku_json *j = (pku_json *)calloc(1, sizeof *j);
    if (!j) return PK_E_NOMEM;
    pk_status st = PK_E_CORRUPT;
    char c = *p->p;
    size_t left = (size_t)(p->end - p->p);
    if (c == '{' || c == '[') {
        if (depth > PKU_JSON_MAX_DEPTH) { pku_json_free(j); return PK_E_CORRUPT; }   /* depth = this container's nesting level */
        j->type = c == '{' ? PKU_J_OBJ : PKU_J_ARR;
        st = parse_container(p, depth, j);
    } else if (c == '"') {
        j->type = PKU_J_STR;
        st = parse_string(p, &j->s);
    } else if (left >= 4 && !memcmp(p->p, "true", 4)) {
        j->type = PKU_J_BOOL; j->b = 1; p->p += 4; st = PK_OK;
    } else if (left >= 5 && !memcmp(p->p, "false", 5)) {
        j->type = PKU_J_BOOL; p->p += 5; st = PK_OK;
    } else if (left >= 4 && !memcmp(p->p, "null", 4)) {
        j->type = PKU_J_NULL; p->p += 4; st = PK_OK;
    } else if (c == '-' || (c >= '0' && c <= '9')) {
        char tok[64];
        size_t n = 0;
        int plain = 1;
        while (p->p + n < p->end && n < sizeof tok - 1) {
            char t = p->p[n];
            if (t == '.' || t == 'e' || t == 'E') plain = 0;
            else if (!(t == '-' || t == '+' || (t >= '0' && t <= '9'))) break;
            tok[n++] = t;
        }
        tok[n] = 0;
        char *e;
        j->d = strtod(tok, &e);
        if (n && !*e && isfinite(j->d)) {
            j->type = PKU_J_NUM;
            if (plain && n < 19) { j->is_int = 1; j->i = strtoll(tok, NULL, 10); }
            p->p += n;
            st = PK_OK;
        }
    }
    if (st != PK_OK) { pku_json_free(j); return st; }
    *out = j;
    return PK_OK;
}

pk_status pku_json_parse(const char *text, size_t n, pku_json **root) { return pku_json_parse_at(text, n, 0, root); }

pk_status pku_json_parse_at(const char *text, size_t n, int base_depth, pku_json **root) {
    if (root) *root = NULL;
    if (!text || !root || base_depth < 0) return PK_E_ARG;
    if (n > PKU_JSON_MAX_BYTES) return PK_E_CORRUPT;
    jp p = { text, text + n };
    pku_json *j = NULL;
    pk_status st = parse_value(&p, base_depth + 1, &j);
    if (st == PK_OK) {
        skip_ws(&p);
        if (p.p != p.end) st = PK_E_CORRUPT;
    }
    if (st != PK_OK) { pku_json_free(j); return st; }
    *root = j;
    return PK_OK;
}

pku_jtype pku_json_type(const pku_json *j) { return j ? j->type : PKU_J_NULL; }
size_t pku_json_len(const pku_json *j) { return j && (j->type == PKU_J_ARR || j->type == PKU_J_OBJ) ? j->n : 0; }
const pku_json *pku_json_at(const pku_json *j, size_t i) { return i < pku_json_len(j) ? j->kids[i] : NULL; }
const char *pku_json_key(const pku_json *j, size_t i) { return j && j->type == PKU_J_OBJ && i < j->n ? j->keys[i] : NULL; }
const pku_json *pku_json_get(const pku_json *j, const char *key) {
    if (!j || j->type != PKU_J_OBJ || !key) return NULL;
    for (size_t k = 0; k < j->n; k++) if (!strcmp(j->keys[k], key)) return j->kids[k];
    return NULL;
}
const char *pku_json_str(const pku_json *j) { return j && j->type == PKU_J_STR ? j->s : NULL; }
double pku_json_num(const pku_json *j) { return j && j->type == PKU_J_NUM ? j->d : 0; }
int pku_json_is_int(const pku_json *j) { return j && j->type == PKU_J_NUM && j->is_int; }
long long pku_json_int(const pku_json *j) { return j && j->type == PKU_J_NUM ? (j->is_int ? j->i : (long long)j->d) : 0; }
int pku_json_bool(const pku_json *j) { return j && j->type == PKU_J_BOOL && j->b; }

/* ---- writer ---- */

struct pku_jw {
    char *buf;
    size_t len, cap;
    int depth, err, after_key;
    unsigned char first[PKU_JSON_MAX_DEPTH + 2];
    char closer[PKU_JSON_MAX_DEPTH + 2];
};

pku_jw *pku_jw_new(void) { return (pku_jw *)calloc(1, sizeof(pku_jw)); }
void pku_jw_free(pku_jw *w) { if (w) { free(w->buf); free(w); } }

static void put(pku_jw *w, const char *s, size_t n) {
    if (w->err) return;
    if (w->len + n + 1 > w->cap) {
        size_t nc = w->cap ? w->cap : 256;
        while (nc < w->len + n + 1) nc *= 2;
        char *nb = (char *)realloc(w->buf, nc);
        if (!nb) { w->err = 1; return; }
        w->buf = nb; w->cap = nc;
    }
    memcpy(w->buf + w->len, s, n);
    w->len += n;
    w->buf[w->len] = 0;
}
static void puts_(pku_jw *w, const char *s) { put(w, s, strlen(s)); }

static void before_value(pku_jw *w) {
    if (w->after_key) { w->after_key = 0; return; }
    if (w->depth > 0) {
        if (!w->first[w->depth]) put(w, ",", 1);
        w->first[w->depth] = 0;
    }
}

static void begin(pku_jw *w, char open, char close) {
    before_value(w);
    if (w->depth >= PKU_JSON_MAX_DEPTH) { w->err = 1; return; }
    put(w, &open, 1);
    w->depth++;
    w->first[w->depth] = 1;
    w->closer[w->depth] = close;
}

static void end(pku_jw *w, char close) {
    if (w->depth == 0 || w->closer[w->depth] != close || w->after_key) { w->err = 1; return; }
    w->depth--;
    put(w, &close, 1);
}

void pku_jw_obj_begin(pku_jw *w) { begin(w, '{', '}'); }
void pku_jw_obj_end(pku_jw *w) { end(w, '}'); }
void pku_jw_arr_begin(pku_jw *w) { begin(w, '[', ']'); }
void pku_jw_arr_end(pku_jw *w) { end(w, ']'); }

static void quoted(pku_jw *w, const char *s) {
    put(w, "\"", 1);
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        char esc[8];
        if (c == '"') puts_(w, "\\\"");
        else if (c == '\\') puts_(w, "\\\\");
        else if (c == '\n') puts_(w, "\\n");
        else if (c == '\t') puts_(w, "\\t");
        else if (c < 0x20) { snprintf(esc, sizeof esc, "\\u%04x", c); puts_(w, esc); }
        else put(w, s, 1);
    }
    put(w, "\"", 1);
}

void pku_jw_key(pku_jw *w, const char *key) {
    if (w->depth == 0 || w->closer[w->depth] != '}' || w->after_key) { w->err = 1; return; }
    before_value(w);
    quoted(w, key);
    put(w, ":", 1);
    w->after_key = 1;
}

void pku_jw_str(pku_jw *w, const char *s) { if (!s) { pku_jw_null(w); return; } before_value(w); quoted(w, s); }
void pku_jw_null(pku_jw *w) { before_value(w); puts_(w, "null"); }
void pku_jw_bool(pku_jw *w, int v) { before_value(w); puts_(w, v ? "true" : "false"); }
void pku_jw_int(pku_jw *w, long long v) { char t[32]; before_value(w); snprintf(t, sizeof t, "%lld", v); puts_(w, t); }
void pku_jw_uint(pku_jw *w, unsigned long long v) { char t[32]; before_value(w); snprintf(t, sizeof t, "%llu", v); puts_(w, t); }
void pku_jw_num(pku_jw *w, double v) {
    char t[40];
    if (!isfinite(v)) { pku_jw_null(w); return; }
    before_value(w);
    snprintf(t, sizeof t, "%.17g", v);
    puts_(w, t);
}
void pku_jw_raw(pku_jw *w, const char *json) { before_value(w); puts_(w, json); }

const char *pku_jw_finish(pku_jw *w, size_t *len) {
    if (len) *len = 0;
    if (!w || w->err || w->depth != 0 || w->after_key || !w->buf) return NULL;
    if (len) *len = w->len;
    return w->buf;
}
