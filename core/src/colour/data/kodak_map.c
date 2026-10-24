#define _POSIX_C_SOURCE 200809L   /* opendir / readdir under -std=c99 */
#include "data/diag.h"
#include "data/kodak_map.h"
#include "data/kodak_text.h"
#include <ctype.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

pk_status pkc_film_iso_load(const char *vendor_root, int16_t table[128][16]) {
    if (!vendor_root || !table) return PK_E_ARG;
    char path[1100];
    pk_status st = pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/common/common-ProdCodeTable.dpi", path, sizeof path);
    if (st != PK_OK) return st;
    FILE *f = pkc_fopen(path, "r");
    if (!f) return PK_E_VENDOR_DATA;
    char line[1024];
    int n = 0, bad = 0;
    while (!bad && fgets(line, sizeof line, f)) {
        char *h = strchr(line, '#');
        if (h) *h = 0;
        char *cur = line;
        for (char *t = pkc_kt_next_token(&cur); t && !bad; t = pkc_kt_next_token(&cur)) {
            char *e; long v = strtol(t, &e, 10);
            if (*e || v < -32768 || v > 32767 || n >= 2048) { bad = 1; break; }
            table[n / 16][n % 16] = (int16_t)v; n++;
        }
    }
    fclose(f);
    return !bad && n == 2048 ? PK_OK : PK_E_VENDOR_DATA;
}

int pkc_film_iso(const int16_t table[128][16], int pc, int gc) {
    int16_t p = (int16_t)pc, g = (int16_t)gc;          /* the lookup takes words and compares them signed */
    int v = (p >= 0 && p < 128 && g >= 0 && g < 16) ? table[p][g] : 0;
    return v > 0 ? v : 0;                               /* setle / dec / and: a non-positive ISO is 0 */
}

/* tokens of a map line: whitespace-separated, a parenthesised range "(a, b)" is one token; '#' starts a comment */
static int map_tokens(char *s, char **tok, int max) {
    char *h = strchr(s, '#');
    if (h) *h = 0;
    int n = 0;
    while (*s) {
        while (*s && isspace((unsigned char)*s)) s++;
        if (!*s) break;
        if (n == max) return -1;
        tok[n++] = s;
        if (*s == '(') { while (*s && *s != ')') s++; if (*s) s++; }
        else while (*s && !isspace((unsigned char)*s)) s++;
        if (*s) *s++ = 0;
    }
    return n;
}

static int parse_long(const char *s, long *v) {
    char *e;
    while (isspace((unsigned char)*s)) s++;
    *v = strtol(s, &e, 10);
    while (isspace((unsigned char)*e)) e++;
    return e != s && (*e == 0 || *e == ',' || *e == ')');
}

/* 1 match, 0 no match, -1 undecidable, -2 malformed */
static int cell_match(const char *c, const pkc_map_key *k) {
    if (!strcasecmp(c, "any")) return 1;
    if (!k || k->kind == PKC_MAP_UNKNOWN) return -1;
    if (k->kind == PKC_MAP_ABSENT) return 0;
    if (k->kind == PKC_MAP_STR) return !strcasecmp(c, k->s);
    long a, b;
    if (c[0] == '(') {
        const char *comma = strchr(c, ',');
        if (!comma || !parse_long(c + 1, &a) || !parse_long(comma + 1, &b)) return -2;
        return a <= k->v && k->v <= b;
    }
    if (!parse_long(c, &a)) return -2;
    return a == k->v;
}

pk_status pkc_map_select(const char *map_path, const pkc_map_key *keys, int nkeys, char *out, size_t cap) {
    if (!map_path || (!keys && nkeys) || !out || !cap) return PK_E_ARG;
    FILE *f = pkc_fopen(map_path, "r");
    if (!f) return PK_E_VENDOR_DATA;
    enum { MAXC = 16 };
    char line[1024], *tok[2 * MAXC + 2];
    const pkc_map_key *col[MAXC];
    int state = 0, ncol = 0;                            /* 0: before `mapping =`, 1: header next, 2: rows */
    pk_status st = PK_E_VENDOR_DATA;
    while (fgets(line, sizeof line, f)) {
        int n = map_tokens(line, tok, 2 * MAXC + 2);
        if (n < 0) { st = PK_E_VENDOR_DATA; break; }
        if (n == 0) continue;
        if (state == 0) {
            if (!strcmp(tok[0], "mapping")) state = 1;
            continue;
        }
        if (state == 1) {
            if (n % 2 || n / 2 > MAXC) break;
            ncol = n / 2;
            for (int c = 0; c < ncol; c++) {
                col[c] = NULL;
                for (int k = 0; k < nkeys; k++) if (!strcmp(keys[k].name, tok[2 * c])) col[c] = &keys[k];
            }
            state = 2;
            continue;
        }
        if (n != ncol + 1) { st = PK_E_VENDOR_DATA; break; }
        int m = 1;
        for (int c = 0; c < ncol && m == 1; c++) m = cell_match(tok[c], col[c]);
        if (m == -2) { st = PK_E_VENDOR_DATA; break; }
        if (m == -1) { st = PK_E_UNSUPPORTED; break; }
        if (m == 1) {
            st = strlen(tok[ncol]) < cap ? (strcpy(out, tok[ncol]), PK_OK) : PK_E_FORMAT;
            break;
        }
    }
    fclose(f);
    return st;
}

pk_status pkc_dpi_by_key(const char *dir, const char *key, char *out, size_t cap) {
    if (!dir || !key || !out || !cap) return PK_E_ARG;
    DIR *d = opendir(dir);
    if (!d) return PK_E_VENDOR_DATA;
    struct dirent *e;
    int found = 0;
    pk_status st = PK_OK;
    while ((e = readdir(d)) && st == PK_OK) {
        size_t l = strlen(e->d_name);
        if (l < 5 || strcasecmp(e->d_name + l - 4, ".dpi")) continue;
        char path[1200];
        if (snprintf(path, sizeof path, "%s/%s", dir, e->d_name) >= (int)sizeof path) { st = PK_E_FORMAT; break; }
        pkc_kt *kt = NULL;
        if (pkc_kt_load(path, &kt) != PK_OK) continue;      /* an unreadable file holds no key */
        const char *k = pkc_kt_str(kt, "key");
        if (k && !strcmp(k, key)) {
            if (found++) st = PK_E_VENDOR_DATA;               /* two files with one key: ambiguous */
            else if (strlen(path) >= cap) st = PK_E_FORMAT;
            else strcpy(out, path);
        }
        pkc_kt_free(kt);
    }
    closedir(d);
    if (st == PK_OK && !found) st = PK_E_VENDOR_DATA;
    return st;
}
