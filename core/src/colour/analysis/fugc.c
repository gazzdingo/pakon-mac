/* FUGC LUT and the context dmin it reads: docs/re/22, fugc.h. */
#include "data/diag.h"
#include "analysis/fugc.h"
#include "analysis/dmin.h"
#include "analysis/kint.h"
#include "data/kodak_text.h"
#include "data/kodak_map.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FUGC_DIR "anselinstalldir/dataPathItems/fugc/"

/* a whole token that is a plain decimal number (kodak_text's grammar) with a finite value */
static int dec_number(const char *s, double *v) {
    return pkc_kt_parse_number(s, v);
}

/* a token that is an integer in int16 range (%hd of the shipped values) */
static int i16_token(const char *s, int16_t *v) {
    double d;
    if (!dec_number(s, &d) || d != floor(d) || d < -32768.0 || d > 32767.0) return 0;
    for (const char *p = s; *p; p++) if (*p == '.' || *p == 'e' || *p == 'E') return 0;
    *v = (int16_t)d;
    return 1;
}

/* split s (modified: NUL-terminates each token) on blanks into at most max tokens; returns the count, or max + 1 if
 * there are more. Reentrant (no strtok). */
static int split(char *s, char **tok, int max) {
    int n = 0;
    for (char *t = pkc_kt_next_token(&s); t; t = pkc_kt_next_token(&s)) {
        if (n == max) return max + 1;
        tok[n++] = t;
    }
    return n;
}

/* AnsFugcLutDpi::readAscii (0x101f7180..0x101f75fc). key = the expected `key` value (the .lut file name). */
static pk_status read_lut(const char *path, const char *key, int16_t seed[3][PKC_FUGC_N], int16_t tdmin[3]) {
    FILE *f = pkc_fopen(path, "rb");
    if (!f) return PK_E_VENDOR_DATA;
    char line[512], tmp[512], *tok[8];
    int rows = 0, have_t = 0, have_key = 0;
    int32_t last[3] = { 0, 0, 0 };
    pk_status st = PK_OK;
    while (st == PK_OK && fgets(line, sizeof line, f)) {
        size_t len = strlen(line);
        if (len && line[len - 1] == '\n') line[--len] = 0;
        else if (!feof(f)) { st = PK_E_VENDOR_DATA; break; }          /* longer than the buffer */
        if (len > 255) { st = PK_E_VENDOR_DATA; break; }                /* getline(buf, 0x100) fails */
        if (len && line[len - 1] == '\r') line[--len] = 0;              /* the CR stays in Kodak's buffer; %s / %lf skip it */
        if (!line[0] || line[0] == '#' || line[0] == '*' || line[0] == '\r') continue;
        const char *q = line + strspn(line, " \t"), *q2 = q + strcspn(q, " \t=");
        if (rows == 0 && q2 > q && q2[strspn(q2, " \t")] == '=') {     /* header: sscanf("%s = %s") == 2 */
            char name[256]; snprintf(name, sizeof name, "%.*s", (int)(q2 - q), q);
            if (*q2 == '=') { st = PK_E_VENDOR_DATA; break; }               /* %s swallows the "=": no header, no row */
            strcpy(tmp, strchr(q2, '=') + 1);
            int nv = split(tmp, tok, 3);
            if (nv < 1) { st = PK_E_VENDOR_DATA; break; }
            if (!strcmp(name, "key")) { have_key = !strcmp(tok[0], key); continue; }
            if (!strcmp(name, "version")) continue;
            if (!strcmp(name, "aTableDmin")) {                          /* "%*s = %hd %hd %hd" must give 3 */
                if (nv < 3 || !i16_token(tok[0], &tdmin[0]) || !i16_token(tok[1], &tdmin[1]) || !i16_token(tok[2], &tdmin[2])) {
                    st = PK_E_VENDOR_DATA; break;
                }
                have_t = 1; continue;
            }
            st = PK_E_VENDOR_DATA; break;                               /* any other entry fails the row parse */
        }
        strcpy(tmp, line);
        int n = split(tmp, tok, 4);                                     /* "%lf %lf %lf %lf" -> 4 or 2 */
        double v[4];
        if (n != 4 && n != 2) { st = PK_E_VENDOR_DATA; break; }
        for (int k = 0; k < n; k++) if (!dec_number(tok[k], &v[k])) { st = PK_E_VENDOR_DATA; break; }
        if (st != PK_OK) break;
        if (rows >= PKC_FUGC_N) { st = PK_E_VENDOR_DATA; break; }        /* Kodak would write past its table */
        if (pkc_sx16(pkc_ftol64(v[0] + 0.5)) != (int16_t)rows) { st = PK_E_VENDOR_DATA; break; }   /* cmp ax, bp */
        last[0] = (int32_t)pkc_ftol64(v[1] + 0.5);                      /* _ftol2, eax kept */
        last[1] = n == 2 ? last[0] : (int32_t)pkc_ftol64(v[2] + 0.5);
        last[2] = n == 2 ? last[0] : (int32_t)pkc_ftol64(v[3] + 0.5);
        for (int c = 0; c < 3; c++) seed[c][rows] = pkc_sx16(last[c]);
        rows++;
    }
    if (ferror(f)) st = PK_E_VENDOR_DATA;
    fclose(f);
    if (st != PK_OK) return st;
    if (!rows || !have_t || !have_key) return PK_E_VENDOR_DATA;
    for (int i = rows; i < PKC_FUGC_N; i++)                             /* 0x101f754b: each channel goes on by +1 */
        for (int c = 0; c < 3; c++) { last[c] = pkc_wrap32((int64_t)last[c] + 1); seed[c][i] = pkc_sx16(last[c]); }
    for (int c = 0; c < 3; c++)                                         /* 0x101f758a: signed word clamp */
        for (int i = 0; i < PKC_FUGC_N; i++)
            seed[c][i] = seed[c][i] < 0 ? 0 : seed[c][i] > PKC_FUGC_N - 1 ? PKC_FUGC_N - 1 : seed[c][i];
    return PK_OK;
}

pk_status pkc_fugc_seed(const char *vendor_root, int16_t seed[3][PKC_FUGC_N], int16_t aTableDmin[3]) {
    return pkc_fugc_seed_film(vendor_root, 0, 0, 0, seed, aTableDmin);
}

/* film row r is (a, b, c) exactly (X = the literal wildcard token) */
static int film_row_is(char **t, int nc, int r, const char *a, const char *b, const char *c) {
    return nc >= 4 && !strcmp(t[r * nc], a) && !strcmp(t[r * nc + 1], b) && !strcmp(t[r * nc + 2], c);
}

pk_status pkc_fugc_seed_film(const char *vendor_root, int product_code, int gen_code, int film_iso,
                             int16_t seed[3][PKC_FUGC_N], int16_t aTableDmin[3]) {
    if (!vendor_root || !seed || !aTableDmin) return PK_E_ARG;
    char path[1024];
    pk_status st = pkc_vendor_path(vendor_root, FUGC_DIR "fugc-rgb-lutMap.map", path, sizeof path);
    if (st != PK_OK) return st;
    pkc_kt *kt = NULL;
    if ((st = pkc_kt_load(path, &kt)) != PK_OK) return st;
    char **t; int nc, nf = pkc_kt_rows(kt, "film", &t, &nc);
    double contrast = -1; int found = 0, step = -1;
    /* the constructor's cascade (0x101fbf03..0x101fc2d8, RE 22 section 4): (productCode, genCode), (productCode, X), the
     * film ISO, (X, X) -- each an exact key lookup, the first that exists wins */
    char pc[16], gc[16], iso[16];
    snprintf(pc, sizeof pc, "%d", (int16_t)product_code); snprintf(gc, sizeof gc, "%d", (int16_t)gen_code);
    snprintf(iso, sizeof iso, "%d", film_iso);
    const char *key[4][3] = { { pc, gc, "X" }, { pc, "X", "X" }, { "X", "X", iso }, { "X", "X", "X" } };
    for (int k = 0; k < 4 && !found; k++)
        for (int r = 0; r < nf && !found; r++) {
            if (!film_row_is(t, nc, r, key[k][0], key[k][1], key[k][2])) continue;
            if (!dec_number(t[r * nc + 3], &contrast) || contrast < 0) { k = 4; break; }
            found = 1; step = k;
        }
    /* only the wildcard step is Kodak-run (the shipped map has no other film row): a product / ISO row of an edited map
     * is refused rather than trusted to the decompile's key forms */
    if (found && step != 3) { pkc_kt_free(kt); return PK_E_UNSUPPORTED; }
    char lut[256] = "";
    if (found) {
        int ncon = pkc_kt_rows(kt, "contrast", &t, &nc);
        found = 0;
        for (int r = 0; r < ncon && !found && nc >= 2; r++) {
            double c;
            if (dec_number(t[r * nc], &c) && (float)c == (float)contrast && t[r * nc + 1][0]) {
                snprintf(lut, sizeof lut, "%s", t[r * nc + 1]); found = 1;
            }
        }
    }
    pkc_kt_free(kt);
    if (!found || strchr(lut, '/')) return PK_E_VENDOR_DATA;
    char rel[512];
    snprintf(rel, sizeof rel, FUGC_DIR "%s", lut);
    if ((st = pkc_vendor_path(vendor_root, rel, path, sizeof path)) != PK_OK) return st;
    return read_lut(path, lut, seed, aTableDmin);
}

pk_status pkc_fugc_aim_load(const char *vendor_root, int16_t aim[3]) {
    return pkc_fugc_aim_load_film(vendor_root, 0, 0, aim);
}

pk_status pkc_fugc_aim_load_film(const char *vendor_root, int product_code, int gen_code, int16_t aim[3]) {
    if (!vendor_root || !aim) return PK_E_ARG;
    char path[1024], dir[1024], key[64];
    pk_status st = pkc_vendor_path(vendor_root, FUGC_DIR, dir, sizeof dir);
    if (st != PK_OK) return st;
    /* the params dpi by key: fugc-<productCode>-<genCode>.dpi, else fugc-default-default.dpi (0x101fb340); no product dpi
     * is shipped -- one in an edited tree is refused (not Kodak-run) */
    snprintf(key, sizeof key, "fugc-%d-%d.dpi", (int16_t)product_code, (int16_t)gen_code);
    if (pkc_dpi_by_key(dir, key, path, sizeof path) == PK_OK) return PK_E_UNSUPPORTED;
    st = pkc_vendor_path(vendor_root, FUGC_DIR "fugc-defaultParams.dpi", path, sizeof path);
    if (st != PK_OK) return st;
    pkc_kt *kt = NULL;
    if ((st = pkc_kt_load(path, &kt)) != PK_OK) return st;
    const char *s = pkc_kt_str(kt, "aFilmAimDmin");
    char buf[256], *tok[4]; int16_t v[3];
    st = PK_E_VENDOR_DATA;
    if (s) {
        char **t; int nc, nr = pkc_kt_rows(kt, "aFilmAimDmin", &t, &nc);
        if (nr >= 1 && nc >= 3) {
            snprintf(buf, sizeof buf, "%s %s %s", t[0], t[1], t[2]);
            if (split(buf, tok, 3) == 3 && i16_token(tok[0], &v[0]) && i16_token(tok[1], &v[1]) && i16_token(tok[2], &v[2])) {
                memcpy(aim, v, sizeof v); st = PK_OK;
            }
        }
    }
    pkc_kt_free(kt);
    return st;
}

pk_status pkc_ctx_dmin_pass1(uint16_t ctx[3], const uint16_t scene[3]) {
    if (!ctx || !scene) return PK_E_ARG;
    int changed = 0;
    for (int c = 0; c < 3; c++)                                         /* pkc_scene_dmin's floor; 4095 alone is no change */
        if ((int16_t)scene[c] < pkc_dmin_ctx_floor(ctx[c], c)) changed = 1;   /* the grid minimum won (0x10219099...) */
    if (changed) memcpy(ctx, scene, 3 * sizeof *ctx);                   /* 0x102190da: the 6-byte entry write */
    return PK_OK;
}

pk_status pkc_ctx_dmin_pass2(uint16_t ctx[3], uint16_t scene[3], const pkc_fos_result *fos) {
    if (!ctx || !scene) return PK_E_ARG;
    if (!fos || !fos->valid) return PK_OK;                              /* 0x10215ea7 -> 0x10215ffa */
    int changed = 0;
    for (int c = 0; c < 3; c++)
        if ((int16_t)fos->dmin[c] <= (int16_t)scene[c]) { scene[c] = (uint16_t)(int16_t)fos->dmin[c]; changed = 1; }
    if (changed) memcpy(ctx, scene, 3 * sizeof *ctx);                   /* 0x10215efe */
    return PK_OK;
}

pk_status pkc_ctx_dmin_remap(uint16_t ctx[3], const pkc_scplut_params *p, const pkc_lut3 *scp) {
    if (!ctx || !p || !scp) return PK_E_ARG;
    if (!p->modify_dmin) return PK_OK;                                  /* 0x100fd95e */
    for (int c = 0; c < 3; c++) {
        int32_t i = (int16_t)ctx[c];
        i = i < 0 ? 0 : i > PKC_FUGC_N - 1 ? PKC_FUGC_N - 1 : i;
        ctx[c] = (uint16_t)scp->t[c][i];
    }
    return PK_OK;
}

pk_status pkc_fugc_dmin_prime(const uint16_t ctx[3], const int16_t aim[3], int16_t out[3]) {
    if (!ctx || !aim || !out) return PK_E_ARG;
    int in = 1;
    for (int c = 0; c < 3 && in; c++) {
        double d = (double)(int16_t)ctx[c], a = (double)aim[c];
        double lo = a * 0.2;                                            /* fmul [0x10588eb8], rounded to double at PC53 */
        if (d < lo || d > a + a) in = 0;                                /* 0x101fc3f5 jnp / 0x101fc40c je */
    }
    for (int c = 0; c < 3; c++) out[c] = in ? (int16_t)ctx[c] : aim[c];
    return PK_OK;
}

pk_status pkc_fugc_lut(const int16_t seed[3][PKC_FUGC_N], const int16_t dmin_prime[3], const int16_t aTableDmin[3],
                       const int16_t shift[3], pkc_lut3 *out) {
    if (!seed || !dmin_prime || !aTableDmin || !shift || !out) return PK_E_ARG;
    const int32_t n = PKC_FUGC_N;
    for (int c = 0; c < 3; c++) {
        int16_t *L = out->t[c];
        int32_t o = pkc_sx16((int64_t)dmin_prime[c] - aTableDmin[c] + shift[c]);   /* 0x101f8310..0x101f831b, words */
        if (o > n - 1) { for (int32_t i = 0; i < n; i++) L[i] = (int16_t)i; continue; }   /* cmp bx, ax; jle */
        int32_t i = 0;
        if (o > 0) for (; i < o; i++) L[i] = (int16_t)o;                 /* rep stosd / stosw */
        int32_t end = o + n < n ? o + n : n;
        for (; i < end; i++) {
            int16_t v = pkc_sx16((int64_t)seed[c][i - o] + o);          /* add cx, bx */
            L[i] = v < 0 ? 0 : v > n - 1 ? (int16_t)(n - 1) : v;       /* jns / cmp cx, si */
        }
        for (; i < n; i++) L[i] = (int16_t)i;
    }
    return PK_OK;
}
