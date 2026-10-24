#include "calib/record.h"
#include "util/util.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *const BLOBS[] = { "dark.u16", "gain.u32", "smear.json", "smear_ir.u16", "raw/dark_sum.u32", "raw/bright_sum.u32", "raw/ob.json",
                                     "dx.json", "focus.json", "psi.json", "raw/dark1_sum.u32", "raw/irlag_sum.u32" };
#define N_BLOBNAMES (sizeof BLOBS / sizeof BLOBS[0])
typedef char pkcal_blob_room[N_BLOBNAMES <= PKCAL_MAX_BLOBS ? 1 : -1];
static const char *const KINDS[] = { "session", "gain", "focus", "track", "imported-psi", "imported-file" };

int pkcal_unit_ok(const char *u) {
    size_t n = u ? strlen(u) : 0;
    if (n == 0 || n > 64 || u[0] == '.') return 0;
    for (size_t i = 0; i < n; i++) {
        char c = u[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) return 0;
    }
    return 1;
}

int pkcal_blob_name_ok(const char *name) {
    if (!name) return 0;
    for (size_t i = 0; i < N_BLOBNAMES; i++) if (strcmp(name, BLOBS[i]) == 0) return 1;
    return 0;
}

int pkcal_name_ok(const char *name) {
    return name && (pkcal_blob_name_ok(name) || strcmp(name, "calibration.json") == 0 || strcmp(name, "light.json") == 0 ||
                    strcmp(name, "MANIFEST.sha256") == 0);
}

static int kind_ok(const char *k) {
    for (size_t i = 0; i < sizeof KINDS / sizeof KINDS[0]; i++) if (k && strcmp(k, KINDS[i]) == 0) return 1;
    return 0;
}

int pkcal_is_hex(const char *s, size_t n) {
    if (strlen(s) != n) return 0;
    for (size_t i = 0; i < n; i++) if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f'))) return 0;
    return 1;
}

int pkcal_utc_ok(const char *u) {   /* YYYYMMDDTHHMMSSZ, a real calendar time from 1970 */
    if (!u || strlen(u) != 16) return 0;
    for (int i = 0; i < 16; i++) {
        if (i == 8) { if (u[i] != 'T') return 0; }
        else if (i == 15) { if (u[i] != 'Z') return 0; }
        else if (u[i] < '0' || u[i] > '9') return 0;
    }
    #define D2(k) ((u[k] - '0') * 10 + (u[k + 1] - '0'))
    int y = D2(0) * 100 + D2(2), mo = D2(4), d = D2(6), h = D2(9), mi = D2(11), s = D2(13);
    static const int DIM[12] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
    if (y < 1970 || mo < 1 || mo > 12 || h > 23 || mi > 59 || s > 59) return 0;
    int dim = DIM[mo - 1] + (mo == 2 && (y % 4 == 0 && (y % 100 != 0 || y % 400 == 0)));
    #undef D2
    return d >= 1 && d <= dim;
}

int pkcal_kind_imported(const char *kind) { return kind && strncmp(kind, "imported-", 9) == 0; }

/* ------------------------------------------------------------------ file sets */
void pkcal_files_free(pkcal_files *fs) {
    if (!fs) return;
    for (size_t i = 0; i < fs->n; i++) free(fs->f[i].data);
    free(fs->f);
    memset(fs, 0, sizeof *fs);
}

pk_status pkcal_files_add(pkcal_files *fs, const char *name, const void *data, size_t n) {
    if (!fs || !name || strlen(name) >= PKCAL_NAME_MAX || (n && !data)) return PK_E_ARG;
    if (fs->n == fs->cap) {
        size_t nc = fs->cap ? fs->cap * 2 : 16;
        pkcal_file *nf = (pkcal_file *)realloc(fs->f, nc * sizeof *nf);
        if (!nf) return PK_E_NOMEM;
        fs->f = nf; fs->cap = nc;
    }
    uint8_t *d = (uint8_t *)malloc(n ? n : 1);
    if (!d) return PK_E_NOMEM;
    if (n) memcpy(d, data, n);
    pkcal_file *f = &fs->f[fs->n++];
    strcpy(f->name, name);
    f->data = d; f->n = n;
    return PK_OK;
}

const pkcal_file *pkcal_files_find(const pkcal_files *fs, const char *name) {
    if (!fs || !name) return NULL;
    for (size_t i = 0; i < fs->n; i++) if (strcmp(fs->f[i].name, name) == 0) return &fs->f[i];
    return NULL;
}

/* ------------------------------------------------------------------ the record */
pk_calibration *pkcal_new(void) { return (pk_calibration *)calloc(1, sizeof(pk_calibration)); }

void pk_calibration_free(pk_calibration *c) {
    if (!c) return;
    for (size_t i = 0; i < c->n_blob; i++) free(c->blob[i].data);
    free(c);
}
const pk_cal_light *pk_calibration_light(const pk_calibration *c) { return c && c->have_light ? &c->light : NULL; }
const char *pk_calibration_unit(const pk_calibration *c) { return c ? c->unit : NULL; }
const char *pk_calibration_kind(const pk_calibration *c) { return c ? c->kind : NULL; }
const char *pk_calibration_id(const pk_calibration *c) { return c ? c->id : NULL; }
const void *pk_calibration_blob(const pk_calibration *c, const char *name, size_t *n) {
    if (n) *n = 0;
    if (!c || !name) return NULL;
    for (size_t i = 0; i < c->n_blob; i++) if (strcmp(c->blob[i].name, name) == 0) { if (n) *n = c->blob[i].n; return c->blob[i].data; }
    return NULL;
}

pk_status pkcal_set_meta(pk_calibration *c, const char *unit, const char *kind, const char *parent) {
    if (!c || !pkcal_unit_ok(unit) || !kind_ok(kind)) return PK_E_ARG;
    if (parent && *parent && !pkcal_is_hex(parent, 64)) return PK_E_ARG;
    strcpy(c->unit, unit);
    strcpy(c->kind, kind);
    strcpy(c->parent, parent ? parent : "");
    return PK_OK;
}

pk_status pkcal_set_utc(pk_calibration *c, const char *utc) {
    if (!c || !pkcal_utc_ok(utc)) return PK_E_ARG;
    strcpy(c->utc, utc);
    return PK_OK;
}

static int light_ok(const pk_cal_light *l) {
    if (l->version != 1 || (l->dpi_base != 4 && l->dpi_base != 8 && l->dpi_base != 16)) return 0;
    for (int i = 0; i < 3; i++) if (l->afe_gain[i] > 0x3F || l->afe_offset[i] < -254 || l->afe_offset[i] > 255) return 0;
    for (int i = 0; i < 4; i++) {
        if (l->current[i] > 0xFF) return 0;
        if (!(l->duty_film[i] >= 0 && l->duty_film[i] <= 1) || !(l->duty_open[i] >= 0 && l->duty_open[i] <= 1)) return 0;
    }
    return l->integration <= 0xFFD && l->px_offset <= 0xFFFF;
}

pk_status pkcal_set_light(pk_calibration *c, const pk_cal_light *l) {
    if (!c || !l || !light_ok(l)) return PK_E_ARG;
    c->light = *l;
    c->have_light = true;
    c->dpi_base = l->dpi_base;
    c->ir = l->ir;
    return PK_OK;
}

pk_status pkcal_add_blob(pk_calibration *c, const char *name, const void *data, size_t n) {
    if (!c || !pkcal_blob_name_ok(name) || (n && !data) || n > PKCAL_ZIP_MAX_ENTRY) return PK_E_ARG;
    if (pk_calibration_blob(c, name, NULL) || c->n_blob >= PKCAL_MAX_BLOBS) return PK_E_ARG;   /* a name once */
    uint8_t *d = (uint8_t *)malloc(n ? n : 1);
    if (!d) return PK_E_NOMEM;
    if (n) memcpy(d, data, n);
    strcpy(c->blob[c->n_blob].name, name);
    c->blob[c->n_blob].data = d;
    c->blob[c->n_blob].n = n;
    c->n_blob++;
    return PK_OK;
}

/* ------------------------------------------------------------------ serialisation */
static void jw_uarr(pku_jw *w, const unsigned *a, int n) { pku_jw_arr_begin(w); for (int i = 0; i < n; i++) pku_jw_uint(w, a[i]); pku_jw_arr_end(w); }
static void jw_darr(pku_jw *w, const double *a, int n) { pku_jw_arr_begin(w); for (int i = 0; i < n; i++) pku_jw_num(w, a[i]); pku_jw_arr_end(w); }

static pk_status add_json(pkcal_files *out, const char *name, pku_jw *w) {
    size_t n;
    const char *t = pku_jw_finish(w, &n);
    pk_status st = t ? pkcal_files_add(out, name, t, n) : PK_E_NOMEM;
    pku_jw_free(w);
    return st;
}

static int cmp_names(const void *a, const void *b) { return strcmp(*(const char *const *)a, *(const char *const *)b); }

/* "<sha256>  <name>\n" per file, names in byte order; the MANIFEST is not in it. */
static pk_status make_manifest(const pkcal_files *fs, char **text, size_t *len) {
    const char **names = (const char **)malloc((fs->n + 1) * sizeof *names);
    if (!names) return PK_E_NOMEM;
    size_t k = 0;
    for (size_t i = 0; i < fs->n; i++) if (strcmp(fs->f[i].name, "MANIFEST.sha256") != 0) names[k++] = fs->f[i].name;
    qsort(names, k, sizeof *names, cmp_names);
    char *t = (char *)malloc(k * (64 + 2 + PKCAL_NAME_MAX + 1) + 1);
    if (!t) { free(names); return PK_E_NOMEM; }
    size_t o = 0;
    for (size_t i = 0; i < k; i++) {
        const pkcal_file *f = pkcal_files_find(fs, names[i]);
        char hex[65];
        pku_sha256_hex(f->data, f->n, hex);
        o += (size_t)sprintf(t + o, "%s  %s\n", hex, f->name);
    }
    t[o] = 0;
    free(names);
    *text = t; *len = o;
    return PK_OK;
}

pk_status pkcal_build_files(const pk_calibration *c, const char *utc, pkcal_files *out) {
    if (!c || !out || !c->unit[0] || !c->kind[0] || !c->have_light) return PK_E_ARG;
    const char *u = c->utc[0] ? c->utc : utc;
    if (!pkcal_utc_ok(u)) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    pk_status st;
    pku_jw *w = pku_jw_new();
    if (!w) return PK_E_NOMEM;
    pku_jw_obj_begin(w);
    pku_jw_key(w, "schema"); pku_jw_str(w, PKCAL_SCHEMA);
    pku_jw_key(w, "version"); pku_jw_int(w, PKCAL_VERSION);
    pku_jw_key(w, "unit"); pku_jw_str(w, c->unit);
    pku_jw_key(w, "kind"); pku_jw_str(w, c->kind);
    pku_jw_key(w, "utc"); pku_jw_str(w, u);
    pku_jw_key(w, "dpi_base"); pku_jw_int(w, c->dpi_base);
    pku_jw_key(w, "ir"); pku_jw_bool(w, c->ir);
    pku_jw_key(w, "parent"); pku_jw_str(w, c->parent);
    pku_jw_obj_end(w);
    if ((st = add_json(out, "calibration.json", w)) != PK_OK) goto fail;

    const pk_cal_light *l = &c->light;
    w = pku_jw_new();
    if (!w) { st = PK_E_NOMEM; goto fail; }
    pku_jw_obj_begin(w);
    pku_jw_key(w, "version"); pku_jw_uint(w, l->version);
    pku_jw_key(w, "dpi_base"); pku_jw_int(w, l->dpi_base);
    pku_jw_key(w, "ir"); pku_jw_bool(w, l->ir);
    pku_jw_key(w, "afe_gain"); jw_uarr(w, l->afe_gain, 3);
    pku_jw_key(w, "afe_offset"); pku_jw_arr_begin(w); for (int i = 0; i < 3; i++) pku_jw_int(w, l->afe_offset[i]); pku_jw_arr_end(w);
    pku_jw_key(w, "current"); jw_uarr(w, l->current, 4);
    pku_jw_key(w, "duty_film"); jw_darr(w, l->duty_film, 4);
    pku_jw_key(w, "duty_open"); jw_darr(w, l->duty_open, 4);
    pku_jw_key(w, "integration"); pku_jw_uint(w, l->integration);
    pku_jw_key(w, "px_offset"); pku_jw_uint(w, l->px_offset);
    pku_jw_key(w, "low_light"); pku_jw_bool(w, l->low_light);
    pku_jw_obj_end(w);
    if ((st = add_json(out, "light.json", w)) != PK_OK) goto fail;

    for (size_t i = 0; i < c->n_blob; i++)
        if ((st = pkcal_files_add(out, c->blob[i].name, c->blob[i].data, c->blob[i].n)) != PK_OK) goto fail;
    char *m;
    size_t mn;
    if ((st = make_manifest(out, &m, &mn)) != PK_OK) goto fail;
    st = pkcal_files_add(out, "MANIFEST.sha256", m, mn);
    free(m);
    if (st != PK_OK) goto fail;
    return PK_OK;
fail:
    pkcal_files_free(out);
    return st;
}

/* ------------------------------------------------------------------ parsing */
static int get_int(const pku_json *o, const char *k, long long lo, long long hi, long long *v) {
    const pku_json *j = pku_json_get(o, k);
    if (!j || pku_json_type(j) != PKU_J_NUM || !pku_json_is_int(j)) return 0;
    *v = pku_json_int(j);
    return *v >= lo && *v <= hi;
}
static int get_bool(const pku_json *o, const char *k, bool *v) {
    const pku_json *j = pku_json_get(o, k);
    if (!j || pku_json_type(j) != PKU_J_BOOL) return 0;
    *v = pku_json_bool(j) != 0;
    return 1;
}
static const pku_json *get_arr(const pku_json *o, const char *k, size_t n) {
    const pku_json *j = pku_json_get(o, k);
    return j && pku_json_type(j) == PKU_J_ARR && pku_json_len(j) == n ? j : NULL;
}

static int parse_light(const pkcal_file *f, pk_cal_light *l) {
    pku_json *j;
    if (pku_json_parse((const char *)f->data, f->n, &j) != PK_OK) return 0;
    int ok = 0;
    long long v;
    const pku_json *a;
    memset(l, 0, sizeof *l);
    if (pku_json_type(j) != PKU_J_OBJ) goto done;
    if (!get_int(j, "version", 1, 1, &v)) goto done;
    l->version = (unsigned)v;
    if (!get_int(j, "dpi_base", 4, 16, &v)) goto done;
    l->dpi_base = (int)v;
    if (!get_bool(j, "ir", &l->ir) || !get_bool(j, "low_light", &l->low_light)) goto done;
    if (!(a = get_arr(j, "afe_gain", 3))) goto done;
    for (size_t i = 0; i < 3; i++) { const pku_json *e = pku_json_at(a, i); if (!pku_json_is_int(e) || pku_json_int(e) < 0 || pku_json_int(e) > 0x3F) goto done; l->afe_gain[i] = (unsigned)pku_json_int(e); }
    if (!(a = get_arr(j, "afe_offset", 3))) goto done;
    for (size_t i = 0; i < 3; i++) { const pku_json *e = pku_json_at(a, i); if (!pku_json_is_int(e) || pku_json_int(e) < -254 || pku_json_int(e) > 255) goto done; l->afe_offset[i] = (int)pku_json_int(e); }
    if (!(a = get_arr(j, "current", 4))) goto done;
    for (size_t i = 0; i < 4; i++) { const pku_json *e = pku_json_at(a, i); if (!pku_json_is_int(e) || pku_json_int(e) < 0 || pku_json_int(e) > 0xFF) goto done; l->current[i] = (unsigned)pku_json_int(e); }
    for (int d = 0; d < 2; d++) {
        if (!(a = get_arr(j, d ? "duty_open" : "duty_film", 4))) goto done;
        for (size_t i = 0; i < 4; i++) {
            const pku_json *e = pku_json_at(a, i);
            double x = pku_json_type(e) == PKU_J_NUM ? pku_json_num(e) : -1;
            if (!(x >= 0 && x <= 1)) goto done;
            (d ? l->duty_open : l->duty_film)[i] = x;
        }
    }
    if (!get_int(j, "integration", 0, 0xFFD, &v)) goto done;
    l->integration = (unsigned)v;
    if (!get_int(j, "px_offset", 0, 0xFFFF, &v)) goto done;
    l->px_offset = (unsigned)v;
    ok = 1;
done:
    pku_json_free(j);
    return ok;
}

pk_status pkcal_check_files(const pkcal_files *fs, pk_calibration **out, char id[65]) {
    if (out) *out = NULL;
    if (!fs) return PK_E_ARG;
    for (size_t i = 0; i < fs->n; i++) if (!pkcal_name_ok(fs->f[i].name)) return PK_E_CORRUPT;
    const pkcal_file *man = pkcal_files_find(fs, "MANIFEST.sha256");
    const pkcal_file *cj = pkcal_files_find(fs, "calibration.json"), *lj = pkcal_files_find(fs, "light.json");
    if (!man || !cj || !lj) return PK_E_CORRUPT;
    char *want;
    size_t wn;
    pk_status st = make_manifest(fs, &want, &wn);
    if (st != PK_OK) return st;
    int same = wn == man->n && memcmp(want, man->data, wn) == 0;
    free(want);
    if (!same) return PK_E_CORRUPT;

    pk_calibration *c = pkcal_new();
    if (!c) return PK_E_NOMEM;
    st = PK_E_CORRUPT;
    pku_json *j = NULL;
    if (pku_json_parse((const char *)cj->data, cj->n, &j) != PK_OK) { j = NULL; goto fail; }
    long long v;
    const pku_json *s;
    if (pku_json_type(j) != PKU_J_OBJ) goto fail;
    s = pku_json_get(j, "schema");
    if (!pku_json_str(s) || strcmp(pku_json_str(s), PKCAL_SCHEMA) != 0) goto fail;
    if (!get_int(j, "version", PKCAL_VERSION, PKCAL_VERSION, &v)) goto fail;
    const char *unit = pku_json_str(pku_json_get(j, "unit")), *kind = pku_json_str(pku_json_get(j, "kind"));
    const char *utc = pku_json_str(pku_json_get(j, "utc")), *parent = pku_json_str(pku_json_get(j, "parent"));
    if (!pkcal_unit_ok(unit) || !kind_ok(kind) || !pkcal_utc_ok(utc) || !parent || (*parent && !pkcal_is_hex(parent, 64))) goto fail;
    strcpy(c->unit, unit); strcpy(c->kind, kind); strcpy(c->utc, utc); strcpy(c->parent, parent);
    if (!get_int(j, "dpi_base", 4, 16, &v) || (v != 4 && v != 8 && v != 16)) goto fail;
    c->dpi_base = (int)v;
    if (!get_bool(j, "ir", &c->ir)) goto fail;
    if (!parse_light(lj, &c->light) || c->light.dpi_base != c->dpi_base || c->light.ir != c->ir) goto fail;
    c->have_light = true;
    for (size_t i = 0; i < fs->n; i++) {
        if (!pkcal_blob_name_ok(fs->f[i].name)) continue;
        if (pkcal_add_blob(c, fs->f[i].name, fs->f[i].data, fs->f[i].n) != PK_OK) goto fail;
    }
    pku_sha256_hex(man->data, man->n, c->id);
    if (id) memcpy(id, c->id, 65);
    pku_json_free(j);
    if (out) *out = c; else pk_calibration_free(c);
    return PK_OK;
fail:
    pku_json_free(j);
    pk_calibration_free(c);
    return st;
}

const char *pkcal_known_name(size_t i) {
    static const char *const fixed[] = { "calibration.json", "light.json", "MANIFEST.sha256" };
    if (i < 3) return fixed[i];
    return i - 3 < N_BLOBNAMES ? BLOBS[i - 3] : NULL;
}
