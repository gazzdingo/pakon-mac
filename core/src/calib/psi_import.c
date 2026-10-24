#define _POSIX_C_SOURCE 200809L
/* PSI import: the registry export (.reg) of the TLB light settings becomes imported-psi calibrations. Value names are TLB's own (RE 07 sec 2, load
 * routine FUN_1000fd80, checked against the owner's offline hive extract): under HKLM\SOFTWARE\Pakon\TLB\Scan\DpiBase<4|8|16>_35\<ColNeg|ColNegIr>
 *   Gain_R/G/B, Offset_R/G/B (REG_DWORD, offsets signed), Current_R/G/B/Ir (REG_DWORD),
 *   DutyCycle_R/G/B/Ir and DutyCycleOpenGate_R/G/B/Ir (REG_SZ decimal text), plus FullLightCorrections, Max_Ir, SpliceDarkness, DetectWhite_G, DetectFilm_G
 * and, one level up in DpiBase<n>_35, Offset (the CCD window start, the entry's px_offset). Every value of the key is kept verbatim in psi.json. */
#include "calib/record.h"
#include "util/util.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define REG_MAX_INPUT ((size_t)128 << 20)
#define MAX_VALS 64
#define KEY_MAX 240

enum { T_OTHER = 0, T_SZ = 1, T_DWORD = 4 };
typedef struct { char name[40]; int type; uint32_t dw; char str[48]; } regval;
typedef struct { int seen; char key[KEY_MAX]; regval v[MAX_VALS]; int n; } slot;

typedef struct {
    slot s[3][2];           /* [dpi base index][ColNeg, ColNegIr] */
    int px_offset[3];       /* -1 = not in the export */
    char cur[KEY_MAX];
    int cur_kind;           /* 0 irrelevant key, 1 a ColNeg/ColNegIr key, 2 a DpiBase key */
    int cur_bi, cur_var;
} reg;

static int ieq(const char *a, const char *b) {
    for (; *a && *b; a++, b++) if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0;
    return *a == *b;
}

/* ------------------------------------------------------------------ text decoding */
static pk_status to_utf8(const uint8_t *in, size_t n, char **out, size_t *outn) {
    char *o = (char *)malloc(n * 3 / 2 + 8);
    if (!o) return PK_E_NOMEM;
    size_t k = 0;
    if (n >= 2 && in[0] == 0xFF && in[1] == 0xFE) {
        for (size_t i = 2; i + 1 < n; i += 2) {
            unsigned u = in[i] | (unsigned)in[i + 1] << 8;
            if (u >= 0xD800 && u < 0xDC00 && i + 3 < n) {
                unsigned lo = in[i + 2] | (unsigned)in[i + 3] << 8;
                if (lo >= 0xDC00 && lo < 0xE000) { u = 0x10000 + ((u - 0xD800) << 10) + (lo - 0xDC00); i += 2; }
                else u = 0xFFFD;
            } else if (u >= 0xD800 && u < 0xE000) u = 0xFFFD;
            if (u == 0) continue;
            if (u < 0x80) o[k++] = (char)u;
            else if (u < 0x800) { o[k++] = (char)(0xC0 | u >> 6); o[k++] = (char)(0x80 | (u & 63)); }
            else if (u < 0x10000) { o[k++] = (char)(0xE0 | u >> 12); o[k++] = (char)(0x80 | ((u >> 6) & 63)); o[k++] = (char)(0x80 | (u & 63)); }
            else { o[k++] = (char)(0xF0 | u >> 18); o[k++] = (char)(0x80 | ((u >> 12) & 63)); o[k++] = (char)(0x80 | ((u >> 6) & 63)); o[k++] = (char)(0x80 | (u & 63)); }
        }
    } else if (n >= 2 && in[0] == 0xFE && in[1] == 0xFF) {
        free(o);
        return PK_E_CORRUPT;                               /* big-endian UTF-16 is not what regedit writes */
    } else {
        size_t i = n >= 3 && in[0] == 0xEF && in[1] == 0xBB && in[2] == 0xBF ? 3 : 0;   /* UTF-8 BOM, or REGEDIT4's ANSI text */
        for (; i < n; i++) if (in[i]) o[k++] = (char)in[i];
    }
    o[k] = 0;
    *out = o; *outn = k;
    return PK_OK;
}

/* ------------------------------------------------------------------ line parsing */
static int hexv(int c) { return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1; }

/* A quoted string at *p (on the opening quote) with \\ and \" escapes; advances past the closing quote. 0 on malformed or over cap. */
static int quoted(const char **p, char *out, size_t cap) {
    const char *s = *p;
    if (*s != '"') return 0;
    s++;
    size_t k = 0;
    while (*s && *s != '"') {
        char c = *s++;
        if (c == '\\') {
            if (*s != '\\' && *s != '"') return 0;
            c = *s++;
        }
        if (k + 1 >= cap) return 0;
        out[k++] = c;
    }
    if (*s != '"') return 0;
    out[k] = 0;
    *p = s + 1;
    return 1;
}

static void classify_key(reg *r, const char *key) {
    r->cur_kind = 0;
    if (strlen(key) >= KEY_MAX) return;
    char b[KEY_MAX];
    strcpy(b, key);
    char *c[32];
    int nc = 0;
    for (char *t = b; nc < 32;) { c[nc++] = t; char *sl = strchr(t, '\\'); if (!sl) break; *sl = 0; t = sl + 1; }
    int tlb = 0;
    for (int i = 0; i + 1 < nc; i++) if (ieq(c[i], "Pakon") && ieq(c[i + 1], "TLB")) tlb = 1;
    if (!tlb) return;
    int bi = -1, var = -1, kind = 0;
    for (int back = 0; back < 2 && nc > back; back++) {
        int base;
        char tail;
        const char *d = c[nc - 1 - back];
        if (strlen(d) > 12 || sscanf(d, "DpiBase%d_3%c", &base, &tail) != 2 || tail != '5') continue;
        if (!ieq(d, base == 4 ? "DpiBase4_35" : base == 8 ? "DpiBase8_35" : base == 16 ? "DpiBase16_35" : "?")) continue;
        bi = base == 4 ? 0 : base == 8 ? 1 : 2;
        if (back == 0) kind = 2;
        else if (ieq(c[nc - 1], "ColNeg")) { kind = 1; var = 0; }
        else if (ieq(c[nc - 1], "ColNegIr")) { kind = 1; var = 1; }
        break;
    }
    if (!kind) return;
    r->cur_kind = kind; r->cur_bi = bi; r->cur_var = var;
    if (kind == 1) {
        slot *s = &r->s[bi][var];
        s->seen = 1;
        strcpy(s->key, key);
    }
}

static void set_val(reg *r, const regval *v) {
    if (r->cur_kind == 2) {
        if (ieq(v->name, "Offset") && v->type == T_DWORD) r->px_offset[r->cur_bi] = (int)v->dw;
        return;
    }
    slot *s = &r->s[r->cur_bi][r->cur_var];
    for (int i = 0; i < s->n; i++) if (ieq(s->v[i].name, v->name)) { s->v[i] = *v; return; }
    if (s->n < MAX_VALS) s->v[s->n++] = *v;
}

/* One logical line. A malformed value inside a relevant key is PK_E_CORRUPT; anywhere else it is ignored. */
static pk_status do_line(reg *r, char *line) {
    while (*line == ' ' || *line == '\t') line++;
    if (!*line || *line == ';') return PK_OK;
    if (*line == '[') {
        char *e = strrchr(line, ']');
        if (!e) { r->cur_kind = 0; return PK_OK; }
        *e = 0;
        if (line[1] == '-') r->cur_kind = 0;
        else classify_key(r, line + 1);
        return PK_OK;
    }
    if (*line != '"' || r->cur_kind == 0) return PK_OK;
    regval v;
    memset(&v, 0, sizeof v);
    const char *p = line;
    if (!quoted(&p, v.name, sizeof v.name)) return PK_E_CORRUPT;
    while (*p == ' ') p++;
    if (*p++ != '=') return PK_E_CORRUPT;
    while (*p == ' ') p++;
    if (strncmp(p, "dword:", 6) == 0) {
        p += 6;
        uint32_t x = 0;
        int nd = 0;
        for (; hexv(*p) >= 0; p++, nd++) x = x << 4 | (uint32_t)hexv(*p);
        if (nd != 8 || (*p && *p != ' ' && *p != ';')) return PK_E_CORRUPT;
        v.type = T_DWORD; v.dw = x;
    } else if (*p == '"') {
        char tmp[512];
        if (!quoted(&p, tmp, sizeof tmp)) return PK_E_CORRUPT;
        v.type = T_SZ;
        snprintf(v.str, sizeof v.str, "%s", tmp);
    } else if (strncmp(p, "hex", 3) == 0) {
        p += 3;
        int t = 3;
        if (*p == '(') { char *end; t = (int)strtol(p + 1, &end, 16); if (*end != ')') return PK_E_CORRUPT; p = end + 1; }
        if (*p++ != ':') return PK_E_CORRUPT;
        uint8_t bytes[1024];
        size_t nb = 0;
        for (;;) {
            while (*p == ' ' || *p == ',') p++;
            if (!*p || *p == ';') break;
            if (hexv(p[0]) < 0 || hexv(p[1]) < 0 || nb >= sizeof bytes) return PK_E_CORRUPT;
            bytes[nb++] = (uint8_t)(hexv(p[0]) << 4 | hexv(p[1]));
            p += 2;
        }
        if (t == 4 && nb == 4) { v.type = T_DWORD; v.dw = bytes[0] | (uint32_t)bytes[1] << 8 | (uint32_t)bytes[2] << 16 | (uint32_t)bytes[3] << 24; }
        else if (t == 1 || t == 2) {              /* UTF-16LE text, NUL terminated: ASCII range is all the light settings use */
            size_t k = 0;
            for (size_t i = 0; i + 1 < nb && k + 1 < sizeof v.str; i += 2) { if (!bytes[i] && !bytes[i + 1]) break; v.str[k++] = bytes[i + 1] ? '?' : (char)bytes[i]; }
            v.type = T_SZ;
        }
    } else if (*p == '-') return PK_OK;           /* "name"=- deletes the value in a merge; nothing to import */
    else return PK_E_CORRUPT;
    set_val(r, &v);
    return PK_OK;
}

static pk_status parse_reg(const char *t, size_t n, reg *r) {
    for (int b = 0; b < 3; b++) { r->px_offset[b] = -1; }
    /* header */
    size_t i = 0;
    while (i < n && (t[i] == '\r' || t[i] == '\n')) i++;
    if (strncmp(t + i, "Windows Registry Editor Version 5.00", 36) != 0 && strncmp(t + i, "REGEDIT4", 8) != 0) return PK_E_CORRUPT;
    char *line = NULL;
    size_t lcap = 0, llen = 0;
    pk_status st = PK_OK;
    int cont = 0;
    while (i < n && st == PK_OK) {
        size_t j = i;
        while (j < n && t[j] != '\n') j++;
        size_t e = j;
        while (e > i && (t[e - 1] == '\r' || t[e - 1] == ' ' || t[e - 1] == '\t')) e--;
        size_t s0 = i;
        if (cont) while (s0 < e && (t[s0] == ' ' || t[s0] == '\t')) s0++;
        int more = e > s0 && t[e - 1] == '\\';
        size_t seg = e - s0 - (more ? 1 : 0);
        if (llen + seg + 1 > lcap) {
            size_t nc = (llen + seg + 1) * 2;
            char *nl = (char *)realloc(line, nc);
            if (!nl) { st = PK_E_NOMEM; break; }
            line = nl; lcap = nc;
        }
        memcpy(line + llen, t + s0, seg);
        llen += seg;
        line[llen] = 0;
        /* a trailing backslash continues only a hex value; in a string it is the string's own */
        if (more && !(strstr(line, "=hex") != NULL && line[0] == '"')) { line[llen++] = '\\'; line[llen] = 0; more = 0; }
        if (more) cont = 1;
        else { cont = 0; st = do_line(r, line); llen = 0; }
        i = j + 1;
    }
    if (st == PK_OK && cont) st = do_line(r, line);
    free(line);
    return st;
}

/* ------------------------------------------------------------------ settings */
static const regval *find(const slot *s, const char *name) {
    for (int i = 0; i < s->n; i++) if (ieq(s->v[i].name, name)) return &s->v[i];
    return NULL;
}

static int get_dw(const slot *s, const char *name, uint32_t *x) {
    const regval *v = find(s, name);
    if (!v || v->type != T_DWORD) return 0;
    *x = v->dw;
    return 1;
}

static int get_dec(const slot *s, const char *name, double *x) {
    const regval *v = find(s, name);
    if (!v || v->type != T_SZ || !v->str[0]) return 0;
    /* plain decimal text, parsed without strtod (which follows the locale): integer / 10^k is correctly rounded for up to 15 digits */
    const char *p = v->str;
    uint64_t num = 0;
    int digits = 0, frac = -1;
    for (; *p; p++) {
        if (*p == '.' && frac < 0) { frac = 0; continue; }
        if (*p < '0' || *p > '9' || ++digits > 15) return 0;
        num = num * 10 + (uint64_t)(*p - '0');
        if (frac >= 0) frac++;
    }
    if (!digits) return 0;
    double d = (double)num;
    if (frac > 0) { double pw = 1; for (int i = 0; i < frac; i++) pw *= 10; d = (double)num / pw; }
    *x = d;
    return 1;
}

/* 0 = the key lacks a required value; 1 = ok; -1 = out of range */
static int build_light(const slot *s, int base, int var, int px_offset, pk_cal_light *l) {
    static const char *const CH[3] = { "R", "G", "B" }, *const CH4[4] = { "R", "G", "B", "Ir" };
    pk_cal_light_seed(l, base, var != 0);
    char nm[40];
    uint32_t x;
    for (int i = 0; i < 3; i++) {
        snprintf(nm, sizeof nm, "Gain_%s", CH[i]);
        if (!get_dw(s, nm, &x)) return 0;
        if (x > 0x3F) return -1;
        l->afe_gain[i] = x;
        snprintf(nm, sizeof nm, "Offset_%s", CH[i]);
        if (!get_dw(s, nm, &x)) return 0;
        int32_t o = (int32_t)x;
        if (o < -254 || o > 255) return -1;
        l->afe_offset[i] = o;
    }
    for (int i = 0; i < 4; i++) {
        double d;
        snprintf(nm, sizeof nm, "Current_%s", CH4[i]);
        if (!get_dw(s, nm, &x)) return 0;
        if (x > 0xFF) return -1;
        l->current[i] = x;
        snprintf(nm, sizeof nm, "DutyCycle_%s", CH4[i]);
        if (!get_dec(s, nm, &d)) return 0;
        if (!(d >= 0 && d <= 1)) return -1;
        l->duty_film[i] = d;
        snprintf(nm, sizeof nm, "DutyCycleOpenGate_%s", CH4[i]);
        if (!get_dec(s, nm, &d)) return 0;
        if (!(d >= 0 && d <= 1)) return -1;
        l->duty_open[i] = d;
    }
    if (px_offset >= 0) {
        if (px_offset > 0xFFFF) return -1;
        l->px_offset = (unsigned)px_offset;
    }
    l->low_light = l->afe_gain[0] >= 0x33 || l->afe_gain[1] >= 0x33 || l->afe_gain[2] >= 0x33;    /* RE 41 sec 6 */
    return 1;
}

static pk_status psi_blob(const slot *s, pk_calibration *c) {
    pku_jw *w = pku_jw_new();
    if (!w) return PK_E_NOMEM;
    pku_jw_obj_begin(w);
    pku_jw_key(w, "source"); pku_jw_str(w, "reg");
    pku_jw_key(w, "key"); pku_jw_str(w, s->key);
    pku_jw_key(w, "values");
    pku_jw_obj_begin(w);
    for (int i = 0; i < s->n; i++) {
        if (s->v[i].type == T_OTHER) continue;
        pku_jw_key(w, s->v[i].name);
        if (s->v[i].type == T_DWORD) pku_jw_uint(w, s->v[i].dw);
        else pku_jw_str(w, s->v[i].str);
    }
    pku_jw_obj_end(w);
    pku_jw_obj_end(w);
    size_t n;
    const char *t = pku_jw_finish(w, &n);
    pk_status st = t ? pkcal_add_blob(c, "psi.json", t, n) : PK_E_NOMEM;
    pku_jw_free(w);
    return st;
}

pk_status pkcal_psi_from_reg(const uint8_t *reg_bytes, size_t n, const char *unit, pk_calibration ***out, size_t *count, size_t *skipped) {
    if (out) *out = NULL;
    if (count) *count = 0;
    if (skipped) *skipped = 0;
    size_t nskip = 0;
    if (!reg_bytes || !pkcal_unit_ok(unit) || !out || !count) return PK_E_ARG;
    if (n > REG_MAX_INPUT) return PK_E_CORRUPT;
    char *text;
    size_t tn;
    pk_status st = to_utf8(reg_bytes, n, &text, &tn);
    if (st != PK_OK) return st;
    reg *r = (reg *)calloc(1, sizeof *r);
    pk_calibration **v = (pk_calibration **)calloc(6, sizeof *v);
    if (!r || !v) { free(text); free(r); free(v); return PK_E_NOMEM; }
    st = parse_reg(text, tn, r);
    free(text);
    size_t k = 0;
    static const int BASES[3] = { 4, 8, 16 };
    for (int bi = 0; bi < 3 && st == PK_OK; bi++) {
        for (int var = 0; var < 2 && st == PK_OK; var++) {
            const slot *s = &r->s[bi][var];
            pk_cal_light l;
            if (!s->seen) continue;
            int ok = build_light(s, BASES[bi], var, r->px_offset[bi], &l);
            if (ok < 0) { st = PK_E_CORRUPT; break; }
            if (ok == 0 || (l.duty_film[0] == 0 && l.duty_film[1] == 0 && l.duty_film[2] == 0 && l.duty_film[3] == 0)) { nskip++; continue; }   /* incomplete, or still TLB's seed */
            pk_calibration *c = pkcal_new();
            if (!c) { st = PK_E_NOMEM; break; }
            /* the entry's time is when TLB last ran the full light search (FullLightCorrections, Unix time), so a 2022 export ranks as 2022 */
            uint32_t flc = 0;
            char utc[24];
            time_t now = time(NULL);
            if (!get_dw(s, "FullLightCorrections", &flc) || flc == 0 || (time_t)flc > now + 86400) flc = (uint32_t)now;
            time_t t = (time_t)flc;
            struct tm tm;
            gmtime_r(&t, &tm);
            strftime(utc, sizeof utc, "%Y%m%dT%H%M%SZ", &tm);
            if ((st = pkcal_set_meta(c, unit, "imported-psi", NULL)) == PK_OK && (st = pkcal_set_utc(c, utc)) == PK_OK && (st = pkcal_set_light(c, &l)) == PK_OK)
                st = psi_blob(s, c);
            if (st != PK_OK) { pk_calibration_free(c); break; }
            v[k++] = c;
        }
    }
    free(r);
    if (st != PK_OK) {
        for (size_t i = 0; i < k; i++) pk_calibration_free(v[i]);
        free(v);
        return st;
    }
    if (!k) { free(v); v = NULL; }
    *out = v; *count = k;
    if (skipped) *skipped = nskip;
    return PK_OK;
}

pk_status pk_calstore_import_psi(pk_calstore *s, const char *unit, const char *reg_path, pk_cal_import_report **reports, size_t *n, size_t *skipped) {
    if (reports) *reports = NULL;
    if (n) *n = 0;
    if (skipped) *skipped = 0;
    if (!s || !unit || !reg_path || !reports || !n) return PK_E_ARG;
    uint8_t *buf;
    size_t bn;
    pk_status st = pku_read_file(reg_path, &buf, &bn);
    if (st != PK_OK) return st;
    pk_calibration **recs;
    size_t cnt;
    st = pkcal_psi_from_reg(buf, bn, unit, &recs, &cnt, skipped);
    free(buf);
    if (st != PK_OK) return st;
    pk_cal_import_report *rep = (pk_cal_import_report *)calloc(cnt ? cnt : 1, sizeof *rep);
    if (!rep) st = PK_E_NOMEM;
    for (size_t i = 0; i < cnt && st == PK_OK; i++) {
        st = pkcal_store_put_imported(s, recs[i], rep[i].id);
        rep[i].n_files = recs[i]->n_blob + 3;
        rep[i].foreign = pkcal_store_is_foreign(s, unit, recs[i]->kind) != 0;
    }
    for (size_t i = 0; i < cnt; i++) pk_calibration_free(recs[i]);
    free(recs);
    if (st != PK_OK || !cnt) { free(rep); return st; }
    *reports = rep; *n = cnt;
    return PK_OK;
}
