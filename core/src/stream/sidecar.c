/* Roll sidecar (<roll>.json, version 1): an ordered key/value list plus the events and strips arrays, kept as typed entries
 * so the setters and getters never reparse; the DOM for pk_sidecar_json is built on demand. */
#include "pakon/stream.h"
#include "util/util.h"
#include <stdlib.h>
#include <string.h>

typedef enum { SE_STR, SE_INT, SE_BOOL, SE_JSON } se_type;
typedef struct { char *key; se_type type; char *s; long long i; } se;   /* s: SE_STR (NULL = null) or SE_JSON text; i: int / bool */

struct pk_sidecar {
    se *e;
    size_t n, cap;
    char **events, **strips;     /* events: plain text; strips: JSON object text */
    size_t n_events, n_strips;
    pku_json *dom;               /* cache, dropped on every change */
};

static char *dup(const char *s) {
    size_t n = strlen(s) + 1;
    char *p = (char *)malloc(n);
    if (p) memcpy(p, s, n);
    return p;
}

pk_sidecar *pk_sidecar_new(void) {
    pk_sidecar *sc = (pk_sidecar *)calloc(1, sizeof *sc);
    if (sc) pk_sidecar_set_int(sc, "format_version", PK_SIDECAR_VERSION);
    return sc;
}

void pk_sidecar_free(pk_sidecar *sc) {
    if (!sc) return;
    for (size_t k = 0; k < sc->n; k++) { free(sc->e[k].key); free(sc->e[k].s); }
    for (size_t k = 0; k < sc->n_events; k++) free(sc->events[k]);
    for (size_t k = 0; k < sc->n_strips; k++) free(sc->strips[k]);
    free(sc->e); free(sc->events); free(sc->strips);
    pku_json_free(sc->dom);
    free(sc);
}

static se *find(const pk_sidecar *sc, const char *key) {
    for (size_t k = 0; k < sc->n; k++) if (!strcmp(sc->e[k].key, key)) return &sc->e[k];
    return NULL;
}

/* Takes ownership of s on success; frees it on failure. */
static pk_status put_entry(pk_sidecar *sc, const char *key, se_type type, char *s, long long i) {
    if (!sc || !key || !*key || !strcmp(key, "events") || !strcmp(key, "strips")) { free(s); return PK_E_ARG; }
    se *e = find(sc, key);
    if (!e) {
        if (sc->n == sc->cap) {
            size_t nc = sc->cap ? sc->cap * 2 : 16;
            se *ne = (se *)realloc(sc->e, nc * sizeof *ne);
            if (!ne) { free(s); return PK_E_NOMEM; }
            sc->e = ne; sc->cap = nc;
        }
        char *k = dup(key);
        if (!k) { free(s); return PK_E_NOMEM; }
        e = &sc->e[sc->n++];
        memset(e, 0, sizeof *e);
        e->key = k;
    }
    free(e->s);
    e->type = type; e->s = s; e->i = i;
    pku_json_free(sc->dom);
    sc->dom = NULL;
    return PK_OK;
}

pk_status pk_sidecar_set_str(pk_sidecar *sc, const char *key, const char *val) {
    char *d = NULL;
    if (val && !(d = dup(val))) return PK_E_NOMEM;
    return put_entry(sc, key, SE_STR, d, 0);
}
pk_status pk_sidecar_set_int(pk_sidecar *sc, const char *key, long long val) { return put_entry(sc, key, SE_INT, NULL, val); }
pk_status pk_sidecar_set_bool(pk_sidecar *sc, const char *key, bool val) { return put_entry(sc, key, SE_BOOL, NULL, val ? 1 : 0); }

/* base_depth: containers the value sits inside in the written file (the root object is 1). */
static pk_status checked_copy(const char *json, int base_depth, char **out) {
    pku_json *j = NULL;
    if (!json) return PK_E_ARG;
    if (pku_json_parse_at(json, strlen(json), base_depth, &j) != PK_OK) return PK_E_ARG;
    pku_json_free(j);
    *out = dup(json);
    return *out ? PK_OK : PK_E_NOMEM;
}

pk_status pk_sidecar_set_json(pk_sidecar *sc, const char *key, const char *json_text) {
    char *d;
    pk_status st = checked_copy(json_text, 1, &d);
    return st == PK_OK ? put_entry(sc, key, SE_JSON, d, 0) : st;
}

static pk_status append(pk_sidecar *sc, char ***list, size_t *n, char *item) {
    char **nl = (char **)realloc(*list, (*n + 1) * sizeof *nl);
    if (!nl) { free(item); return PK_E_NOMEM; }
    nl[(*n)++] = item;
    *list = nl;
    pku_json_free(sc->dom);
    sc->dom = NULL;
    return PK_OK;
}

pk_status pk_sidecar_add_event(pk_sidecar *sc, const char *text) {
    if (!sc || !text) return PK_E_ARG;
    char *d = dup(text);
    return d ? append(sc, &sc->events, &sc->n_events, d) : PK_E_NOMEM;
}

pk_status pk_sidecar_add_strip_json(pk_sidecar *sc, const char *json_object) {
    if (!sc || !json_object) return PK_E_ARG;
    pku_json *j = NULL;
    if (pku_json_parse_at(json_object, strlen(json_object), 2, &j) != PK_OK)   /* root object > strips array > strip */ return PK_E_ARG;
    int obj = pku_json_type(j) == PKU_J_OBJ;
    pku_json_free(j);
    if (!obj) return PK_E_ARG;
    char *d = dup(json_object);
    return d ? append(sc, &sc->strips, &sc->n_strips, d) : PK_E_NOMEM;
}

pk_status pk_sidecar_set_strip_json(pk_sidecar *sc, size_t index, const char *json_object) {
    if (!sc || !json_object || index > sc->n_strips) return PK_E_ARG;
    if (index == sc->n_strips) return pk_sidecar_add_strip_json(sc, json_object);
    pku_json *j = NULL;
    if (pku_json_parse_at(json_object, strlen(json_object), 2, &j) != PK_OK) return PK_E_ARG;
    int obj = pku_json_type(j) == PKU_J_OBJ;
    pku_json_free(j);
    if (!obj) return PK_E_ARG;
    char *d = dup(json_object);
    if (!d) return PK_E_NOMEM;
    free(sc->strips[index]);
    sc->strips[index] = d;
    pku_json_free(sc->dom);
    sc->dom = NULL;
    return PK_OK;
}

void pk_sidecar_truncate_strips(pk_sidecar *sc, size_t n) {
    if (!sc) return;
    while (sc->n_strips > n) free(sc->strips[--sc->n_strips]);
    pku_json_free(sc->dom);
    sc->dom = NULL;
}

const char *pk_sidecar_get_str(const pk_sidecar *sc, const char *key) {
    const se *e = sc && key ? find(sc, key) : NULL;
    return e && e->type == SE_STR ? e->s : NULL;
}
long long pk_sidecar_get_int(const pk_sidecar *sc, const char *key, long long dflt) {
    const se *e = sc && key ? find(sc, key) : NULL;
    return e && e->type == SE_INT ? e->i : dflt;
}
bool pk_sidecar_get_bool(const pk_sidecar *sc, const char *key, bool dflt) {
    const se *e = sc && key ? find(sc, key) : NULL;
    if (!e && key && !strcmp(key, "complete")) return false;   /* a roll that never recorded `complete` is not complete, whatever dflt says */
    return e && e->type == SE_BOOL ? e->i != 0 : dflt;
}

/* Serialises the sidecar; the buffer belongs to w. */
static const char *render(const pk_sidecar *sc, pku_jw *w, size_t *len) {
    pku_jw_obj_begin(w);
    for (size_t k = 0; k < sc->n; k++) {
        const se *e = &sc->e[k];
        pku_jw_key(w, e->key);
        switch (e->type) {
        case SE_STR: pku_jw_str(w, e->s); break;
        case SE_INT: pku_jw_int(w, e->i); break;
        case SE_BOOL: pku_jw_bool(w, (int)e->i); break;
        case SE_JSON: pku_jw_raw(w, e->s); break;
        }
    }
    pku_jw_key(w, "events");
    pku_jw_arr_begin(w);
    for (size_t k = 0; k < sc->n_events; k++) pku_jw_str(w, sc->events[k]);
    pku_jw_arr_end(w);
    pku_jw_key(w, "strips");
    pku_jw_arr_begin(w);
    for (size_t k = 0; k < sc->n_strips; k++) pku_jw_raw(w, sc->strips[k]);
    pku_jw_arr_end(w);
    pku_jw_obj_end(w);
    return pku_jw_finish(w, len);
}

const pku_json *pk_sidecar_json(const pk_sidecar *sc) {
    if (!sc) return NULL;
    if (!sc->dom) {
        pku_jw *w = pku_jw_new();
        size_t len;
        const char *txt = w ? render(sc, w, &len) : NULL;
        if (txt) pku_json_parse(txt, len, &((pk_sidecar *)sc)->dom);
        pku_jw_free(w);
    }
    return sc->dom;
}

pk_status pk_sidecar_write(const pk_sidecar *sc, const char *path) {
    if (!sc || !path) return PK_E_ARG;
    pku_jw *w = pku_jw_new();
    if (!w) return PK_E_NOMEM;
    size_t len;
    const char *txt = render(sc, w, &len);
    pk_status st = txt ? pku_write_file_atomic(path, txt, len) : PK_E_NOMEM;
    pku_jw_free(w);
    return st;
}

static void emit(pku_jw *w, const pku_json *j) {
    switch (pku_json_type(j)) {
    case PKU_J_NULL: pku_jw_null(w); break;
    case PKU_J_BOOL: pku_jw_bool(w, pku_json_bool(j)); break;
    case PKU_J_NUM:
        if (pku_json_is_int(j)) pku_jw_int(w, pku_json_int(j)); else pku_jw_num(w, pku_json_num(j));
        break;
    case PKU_J_STR: pku_jw_str(w, pku_json_str(j)); break;
    case PKU_J_ARR:
        pku_jw_arr_begin(w);
        for (size_t k = 0; k < pku_json_len(j); k++) emit(w, pku_json_at(j, k));
        pku_jw_arr_end(w);
        break;
    case PKU_J_OBJ:
        pku_jw_obj_begin(w);
        for (size_t k = 0; k < pku_json_len(j); k++) { pku_jw_key(w, pku_json_key(j, k)); emit(w, pku_json_at(j, k)); }
        pku_jw_obj_end(w);
        break;
    }
}

static char *dump(const pku_json *j) {
    pku_jw *w = pku_jw_new();
    if (!w) return NULL;
    emit(w, j);
    const char *t = pku_jw_finish(w, NULL);
    char *out = t ? dup(t) : NULL;
    pku_jw_free(w);
    return out;
}

pk_status pk_sidecar_read(const char *path, pk_sidecar **out) {
    if (out) *out = NULL;
    if (!path || !out) return PK_E_ARG;
    uint8_t *data;
    size_t n;
    pk_status st = pku_read_file(path, &data, &n);
    if (st != PK_OK) return st;
    pku_json *root = NULL;
    st = pku_json_parse((const char *)data, n, &root);
    free(data);
    if (st != PK_OK) return st;
    pk_sidecar *sc = NULL;
    const pku_json *ver = pku_json_get(root, "format_version");
    if (pku_json_type(root) != PKU_J_OBJ) { st = PK_E_CORRUPT; goto done; }
    if (!ver || !pku_json_is_int(ver) || pku_json_int(ver) != PK_SIDECAR_VERSION) { st = PK_E_FORMAT; goto done; }
    sc = pk_sidecar_new();
    if (!sc) { st = PK_E_NOMEM; goto done; }
    for (size_t k = 0; k < pku_json_len(root) && st == PK_OK; k++) {
        const char *key = pku_json_key(root, k);
        const pku_json *v = pku_json_at(root, k);
        if (!strcmp(key, "format_version")) continue;
        if (!strcmp(key, "events") || !strcmp(key, "strips")) {
            if (pku_json_type(v) != PKU_J_ARR) { st = PK_E_CORRUPT; break; }
            for (size_t m = 0; m < pku_json_len(v) && st == PK_OK; m++) {
                const pku_json *it = pku_json_at(v, m);
                if (key[0] == 'e') {
                    const char *t = pku_json_str(it);
                    st = t ? pk_sidecar_add_event(sc, t) : PK_E_CORRUPT;
                } else {
                    char *d = pku_json_type(it) == PKU_J_OBJ ? dump(it) : NULL;
                    st = d ? pk_sidecar_add_strip_json(sc, d) : PK_E_CORRUPT;
                    free(d);
                }
            }
            continue;
        }
        switch (pku_json_type(v)) {
        case PKU_J_NULL: st = pk_sidecar_set_str(sc, key, NULL); break;
        case PKU_J_STR: st = pk_sidecar_set_str(sc, key, pku_json_str(v)); break;
        case PKU_J_BOOL: st = pk_sidecar_set_bool(sc, key, pku_json_bool(v)); break;
        case PKU_J_NUM:
            if (pku_json_is_int(v)) { st = pk_sidecar_set_int(sc, key, pku_json_int(v)); break; }
            /* fall through */
        default: {
            char *d = dump(v);
            st = d ? pk_sidecar_set_json(sc, key, d) : PK_E_NOMEM;
            free(d);
        }
        }
    }
done:
    pku_json_free(root);
    if (st != PK_OK) { pk_sidecar_free(sc); return st; }
    *out = sc;
    return PK_OK;
}
