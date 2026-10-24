#include "util/util.h"
#include <string.h>

static char *ws(char *p) { while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++; return p; }

/* Parses a string starting after the opening quote; terminates it in place (compacting \" and \\). Returns the
 * pointer after the closing quote, or NULL. */
static char *str(char *p, char **start) {
    char *w = p;
    *start = p;
    for (;;) {
        char c = *p;
        if (c == 0) return NULL;
        if (c == '"') { *w = 0; return p + 1; }
        if (c == '\\') {
            if (p[1] != '"' && p[1] != '\\') return NULL;
            *w++ = p[1]; p += 2;
        } else {
            *w++ = c; p++;
        }
    }
}

int pku_jl_parse(char *line, pku_jl_kv *kv, int max) {
    if (!line) return -1;
    char *p = ws(line);
    int n = 0;
    if (*p++ != '{') return -1;
    p = ws(p);
    if (*p == '}') { p++; goto tail; }
    for (;;) {
        p = ws(p);
        if (*p++ != '"') return -1;
        char *key;
        if (!(p = str(p, &key))) return -1;
        p = ws(p);
        if (*p++ != ':') return -1;
        p = ws(p);
        if (n >= max) return -1;
        pku_jl_kv *e = &kv[n];
        e->key = key; e->s = NULL; e->n = 0; e->is_str = 0;
        if (*p == '"') {
            char *s;
            if (!(p = str(p + 1, &s))) return -1;
            e->s = s; e->is_str = 1;
        } else if (*p == '-' || (*p >= '0' && *p <= '9')) {
            int neg = *p == '-';
            if (neg) p++;
            if (*p < '0' || *p > '9') return -1;
            unsigned long long v = 0, lim = neg ? 9223372036854775808ULL : 9223372036854775807ULL;
            for (; *p >= '0' && *p <= '9'; p++) {
                unsigned d = (unsigned)(*p - '0');
                if (v > (lim - d) / 10) return -1;
                v = v * 10 + d;
            }
            e->n = neg ? (long long)(0 - v) : (long long)v;
        } else if (strncmp(p, "null", 4) == 0) {
            p += 4;
        } else {
            return -1;
        }
        n++;
        p = ws(p);
        if (*p == ',') { p++; continue; }
        if (*p == '}') { p++; break; }
        return -1;
    }
tail:
    p = ws(p);
    return *p ? -1 : n;
}

const pku_jl_kv *pku_jl_get(const pku_jl_kv *kv, int n, const char *key) {
    for (int i = 0; i < n; i++) if (!strcmp(kv[i].key, key)) return &kv[i];
    return NULL;
}
