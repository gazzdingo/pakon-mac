#define _POSIX_C_SOURCE 200809L
/* The calibration store; layout and rules in pakon/calstore.h. No global or static mutable state. Nothing here deletes a calibration: the only
 * removals are of a put's own half-written <dir>.tmp.<pid> when that put fails in-process. */
#include "calib/record.h"
#include "util/util.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define ROOT_MAX 800
#define PATH_MAX_ 1400
#define DIRNAME_LEN 25      /* YYYYMMDDTHHMMSSZ_<id8> */

struct pk_calstore {
    char root[ROOT_MAX];
    char local[65];
    int has_local;
    char **stale;
    size_t n_stale;
};

/* ------------------------------------------------------------------ small helpers */
static int pathf(char *out, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static int pathf(char *out, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(out, PATH_MAX_, fmt, ap);
    va_end(ap);
    return n >= 0 && n < PATH_MAX_ ? 0 : -1;
}

static void now_utc(char out[24]) {
    time_t t = time(NULL);
    struct tm tm;
    gmtime_r(&t, &tm);
    strftime(out, 24, "%Y%m%dT%H%M%SZ", &tm);
}

static int exists(const char *p) { struct stat st; return lstat(p, &st) == 0; }

/* fsync, then F_FULLFSYNC where the platform has it (plain fsync on macOS does not reach the platters). */
static int sync_fd(int fd) {
    if (fsync(fd)) return -1;
#ifdef F_FULLFSYNC
    fcntl(fd, F_FULLFSYNC);      /* best effort: some filesystems refuse it */
#endif
    return 0;
}

static pk_status fsync_dir(const char *p) {
    int fd = open(p, O_RDONLY);
    if (fd < 0) return PK_E_IO;
    int r = sync_fd(fd);
    close(fd);
    return r ? PK_E_IO : PK_OK;
}

static int cmp_str(const void *a, const void *b) { return strcmp(*(char *const *)a, *(char *const *)b); }

static void names_free(char **v, size_t n) {
    for (size_t i = 0; i < n; i++) free(v[i]);
    free(v);
}

/* The names in a directory (not . or ..), sorted. A missing directory is an empty list. */
static pk_status list_dir(const char *path, char ***out, size_t *n) {
    *out = NULL; *n = 0;
    DIR *d = opendir(path);
    if (!d) return errno == ENOENT || errno == ENOTDIR ? PK_OK : PK_E_IO;
    char **v = NULL;
    size_t cnt = 0, cap = 0;
    struct dirent *e;
    pk_status st = PK_OK;
    while ((e = readdir(d)) != NULL) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        if (cnt == cap) {
            char **nv = (char **)realloc(v, (cap ? cap * 2 : 16) * sizeof *v);
            if (!nv) { st = PK_E_NOMEM; break; }
            v = nv; cap = cap ? cap * 2 : 16;
        }
        v[cnt] = strdup(e->d_name);
        if (!v[cnt]) { st = PK_E_NOMEM; break; }
        cnt++;
    }
    closedir(d);
    if (st != PK_OK) { names_free(v, cnt); return st; }
    if (cnt) qsort(v, cnt, sizeof *v, cmp_str);
    *out = v; *n = cnt;
    return PK_OK;
}

/* A regular file only (a symlink is never followed). */
static pk_status read_regular(const char *path, uint8_t **buf, size_t *n) {
    struct stat st;
    if (lstat(path, &st) != 0) return errno == ENOENT || errno == ENOTDIR ? PK_E_NOT_FOUND : PK_E_IO;
    if (!S_ISREG(st.st_mode)) return PK_E_CORRUPT;
    return pku_read_file(path, buf, n);
}

static pk_status write_all(int fd, const uint8_t *p, size_t n) {
    while (n) {
        ssize_t w = write(fd, p, n);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) return PK_E_IO;
        p += w; n -= (size_t)w;
    }
    return PK_OK;
}

/* Creates the file (it must not exist), fsyncs it, makes it read-only. */
static pk_status write_new(const char *path, const void *data, size_t n) {
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (fd < 0) return PK_E_IO;
    pk_status st = write_all(fd, (const uint8_t *)data, n);
    if (st == PK_OK && (fchmod(fd, 0444) || sync_fd(fd))) st = PK_E_IO;   /* the mode is made durable with the data */
    if (close(fd) && st == PK_OK) st = PK_E_IO;
    return st;
}

/* One line appended to an append-only log, after a newline if the log ends in a torn line. */
static pk_status append_line(const char *path, const char *line) {
    int fd = open(path, O_RDWR | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return PK_E_IO;
    pk_status st = PK_OK;
    off_t end = lseek(fd, 0, SEEK_END);
    char last = '\n';
    if (end > 0 && (pread(fd, &last, 1, end - 1) != 1)) st = PK_E_IO;
    if (st == PK_OK && last != '\n') st = write_all(fd, (const uint8_t *)"!\n", 2);   /* the '!' keeps a torn line invalid even if only its newline was missing */
    if (st == PK_OK) st = write_all(fd, (const uint8_t *)line, strlen(line));
    if (st == PK_OK && sync_fd(fd)) st = PK_E_IO;
    if (close(fd) && st == PK_OK) st = PK_E_IO;
    return st;
}

/* The next newline-terminated line of a log (a last line without its newline is torn and never returned). Lines over 255 bytes are skipped. */
static int next_line(const uint8_t *buf, size_t n, size_t *pos, char line[256]) {
    while (*pos < n) {
        size_t j = *pos;
        while (j < n && buf[j] != '\n') j++;
        if (j >= n) { *pos = n; return 0; }
        size_t len = j - *pos;
        const uint8_t *src = buf + *pos;
        *pos = j + 1;
        if (len < 256) { memcpy(line, src, len); line[len] = 0; return 1; }
    }
    return 0;
}

/* "a b c" into exactly three tokens, in place. */
static int split3(char *line, char *tok[3]) {
    for (int i = 0; i < 3; i++) {
        tok[i] = line;
        char *sp = strchr(line, ' ');
        if (i < 2) { if (!sp) return 0; *sp = 0; line = sp + 1; }
        else if (sp || !*line) return 0;
    }
    return tok[0][0] && tok[1][0];
}

/* ------------------------------------------------------------------ open / close */
static pk_status stale_add(pk_calstore *s, const char *path) {
    char **nv = (char **)realloc(s->stale, (s->n_stale + 1) * sizeof *nv);
    if (!nv) return PK_E_NOMEM;
    s->stale = nv;
    if (!(nv[s->n_stale] = strdup(path))) return PK_E_NOMEM;
    s->n_stale++;
    return PK_OK;
}

pk_status pk_calstore_open(const char *root, pk_calstore **out) {
    if (out) *out = NULL;
    if (!out) return PK_E_ARG;
    pk_calstore *s = (pk_calstore *)calloc(1, sizeof *s);
    if (!s) return PK_E_NOMEM;
    const char *home;
    int n;
    if (root && *root) n = snprintf(s->root, sizeof s->root, "%s", root);
    else if ((home = getenv("PAKON_HOME")) && *home) n = snprintf(s->root, sizeof s->root, "%s", home);
    else if ((home = getenv("HOME")) && *home) n = snprintf(s->root, sizeof s->root, "%s/Library/Application Support/PakonMac", home);
    else n = -1;
    if (n < 0 || n >= (int)sizeof s->root) { free(s); return PK_E_ARG; }
    while (n > 1 && s->root[n - 1] == '/') s->root[--n] = 0;
    /* report (never delete) what a crashed put left behind */
    char p[PATH_MAX_], **units, **cals;
    size_t nu, nc;
    pk_status st = PK_OK;
    if (pathf(p, "%s/units", s->root) == 0 && list_dir(p, &units, &nu) == PK_OK) {
        for (size_t i = 0; i < nu && st == PK_OK; i++) {
            if (!pkcal_unit_ok(units[i]) || pathf(p, "%s/units/%s/calibration", s->root, units[i])) continue;
            if (list_dir(p, &cals, &nc) != PK_OK) continue;
            for (size_t k = 0; k < nc && st == PK_OK; k++) {
                char q[PATH_MAX_];
                if (strstr(cals[k], ".tmp.") && pathf(q, "%s/%s", p, cals[k]) == 0) st = stale_add(s, q);
            }
            names_free(cals, nc);
            char **uf;                                            /* a crashed unit.json.tmp.<pid> and the like */
            size_t nf;
            if (pathf(p, "%s/units/%s", s->root, units[i]) == 0 && list_dir(p, &uf, &nf) == PK_OK) {
                for (size_t k = 0; k < nf && st == PK_OK; k++) {
                    char q[PATH_MAX_];
                    if (strstr(uf[k], ".tmp.") && pathf(q, "%s/%s", p, uf[k]) == 0) st = stale_add(s, q);
                }
                names_free(uf, nf);
            }
        }
        names_free(units, nu);
    }
    if (st != PK_OK) { pk_calstore_close(s); return st; }
    *out = s;
    return PK_OK;
}

void pk_calstore_close(pk_calstore *s) {
    if (!s) return;
    names_free(s->stale, s->n_stale);
    free(s);
}
const char *pkcal_store_root(const pk_calstore *s) { return s ? s->root : NULL; }
size_t pk_calstore_stale_count(const pk_calstore *s) { return s ? s->n_stale : 0; }
const char *pk_calstore_stale_path(const pk_calstore *s, size_t i) { return s && i < s->n_stale ? s->stale[i] : NULL; }

pk_status pk_calstore_set_local_unit(pk_calstore *s, const char *unit) {
    if (!s) return PK_E_ARG;
    if (!unit) { s->has_local = 0; s->local[0] = 0; return PK_OK; }
    if (!pkcal_unit_ok(unit)) return PK_E_ARG;
    strcpy(s->local, unit);
    s->has_local = 1;
    return PK_OK;
}

/* Fail closed (S-R37): with a local unit set, an entry is foreign if its unit differs; with none set nothing can be proved native except a
 * native-kind entry (session, gain, focus, track) of the very unit asked about, so imported kinds are foreign. */
static int is_foreign(const pk_calstore *s, const char *unit, const char *kind) {
    return s->has_local ? strcmp(unit, s->local) != 0 : pkcal_kind_imported(kind);
}
int pkcal_store_is_foreign(const pk_calstore *s, const char *unit, const char *kind) { return s && unit && is_foreign(s, unit, kind); }

static int unidentified(const char *unit) {
    size_t n = strlen(unit), k = strlen("-unidentified");
    return n >= k && strcmp(unit + n - k, "-unidentified") == 0;
}

/* local.log: "<utc> <id> local" for every id a local put is about to install (written and fsynced first). In a "-unidentified" unit only these may
 * be auto-selected, because two chips without an intact CalWiz copy share that name. */
static int log_local(const uint8_t *buf, size_t n, const char *id) {
    size_t pos = 0;
    char line[256], *t[3];
    while (next_line(buf, n, &pos, line))
        if (split3(line, t) && pkcal_utc_ok(t[0]) && strcmp(t[1], id) == 0 && strcmp(t[2], "local") == 0) return 1;
    return 0;
}

/* ------------------------------------------------------------------ reading entries */
static int dirname_ok(const char *d) {
    if (strlen(d) != DIRNAME_LEN || d[16] != '_') return 0;
    char u[17];
    memcpy(u, d, 16); u[16] = 0;
    return pkcal_utc_ok(u) && pkcal_is_hex(d + 17, 8) ;
}

/* Reads calibration.json and the MANIFEST of <unit>/calibration/<dirname>; PK_E_CORRUPT if the directory is not a well-formed entry of that unit. */
static pk_status read_entry(const pk_calstore *s, const char *unit, const char *dirname, pk_cal_entry *e) {
    char p[PATH_MAX_];
    if (!dirname_ok(dirname) || pathf(p, "%s/units/%s/calibration/%s/MANIFEST.sha256", s->root, unit, dirname)) return PK_E_CORRUPT;
    uint8_t *man = NULL;
    size_t mn;
    pk_status st = read_regular(p, &man, &mn);
    if (st != PK_OK) return st == PK_E_NOT_FOUND ? PK_E_CORRUPT : st;
    memset(e, 0, sizeof *e);
    pku_sha256_hex(man, mn, e->id);
    free(man);
    if (strncmp(e->id, dirname + 17, 8) != 0) return PK_E_CORRUPT;
    if (pathf(p, "%s/units/%s/calibration/%s/calibration.json", s->root, unit, dirname)) return PK_E_CORRUPT;
    uint8_t *cj = NULL;
    size_t cn;
    if ((st = read_regular(p, &cj, &cn)) != PK_OK) return st == PK_E_NOT_FOUND ? PK_E_CORRUPT : st;
    pku_json *j;
    st = pku_json_parse((const char *)cj, cn, &j);
    free(cj);
    if (st != PK_OK) return PK_E_CORRUPT;
    const char *ju = pku_json_str(pku_json_get(j, "unit")), *kind = pku_json_str(pku_json_get(j, "kind"));
    const char *utc = pku_json_str(pku_json_get(j, "utc")), *par = pku_json_str(pku_json_get(j, "parent"));
    const pku_json *db = pku_json_get(j, "dpi_base"), *ir = pku_json_get(j, "ir");
    st = PK_E_CORRUPT;
    if (ju && kind && utc && par && strcmp(ju, unit) == 0 && strncmp(utc, dirname, 16) == 0 && strlen(kind) < sizeof e->kind &&
        strlen(par) < sizeof e->parent && pku_json_is_int(db) && pku_json_type(ir) == PKU_J_BOOL) {
        strcpy(e->utc, utc); strcpy(e->kind, kind); strcpy(e->parent, par);
        e->dpi_base = (int)pku_json_int(db);
        e->ir = pku_json_bool(ir) != 0;
        st = PK_OK;
    }
    pku_json_free(j);
    return st;
}

static int cmp_entry_desc(const void *a, const void *b) {
    const pk_cal_entry *x = (const pk_cal_entry *)a, *y = (const pk_cal_entry *)b;
    int c = strcmp(y->utc, x->utc);
    return c ? c : strcmp(y->id, x->id);
}

/* last state of an id in hidden.log: 1 hidden, 0 otherwise */
static int log_hidden(const uint8_t *buf, size_t n, const char *id) {
    size_t pos = 0;
    char line[256], *t[3];
    int h = 0;
    while (next_line(buf, n, &pos, line)) {
        if (!split3(line, t) || !pkcal_utc_ok(t[0]) || strcmp(t[1], id) != 0) continue;
        if (strcmp(t[2], "hidden") == 0) h = 1;
        else if (strcmp(t[2], "unhidden") == 0) h = 0;
    }
    return h;
}

pk_status pk_calstore_list(pk_calstore *s, const char *unit, pk_cal_entry **out, size_t *n, bool include_hidden) {
    if (out) *out = NULL;
    if (n) *n = 0;
    if (!s || !unit || !out || !n || !pkcal_unit_ok(unit)) return PK_E_ARG;
    char p[PATH_MAX_], **names;
    size_t nn;
    if (pathf(p, "%s/units/%s/calibration", s->root, unit)) return PK_E_ARG;
    pk_status st = list_dir(p, &names, &nn);
    if (st != PK_OK) return st;
    pk_cal_entry *v = (pk_cal_entry *)malloc((nn ? nn : 1) * sizeof *v);
    if (!v) { names_free(names, nn); return PK_E_NOMEM; }
    uint8_t *hlog = NULL;
    size_t hn = 0;
    if (pathf(p, "%s/units/%s/hidden.log", s->root, unit) == 0 && read_regular(p, &hlog, &hn) != PK_OK) { hlog = NULL; hn = 0; }
    size_t cnt = 0;
    for (size_t i = 0; i < nn; i++) {
        if (!dirname_ok(names[i]) || read_entry(s, unit, names[i], &v[cnt]) != PK_OK) continue;   /* *.tmp.* and anything malformed is ignored */
        v[cnt].hidden = hlog && log_hidden(hlog, hn, v[cnt].id);
        v[cnt].foreign = is_foreign(s, unit, v[cnt].kind);
        if (v[cnt].hidden && !include_hidden) continue;
        cnt++;
    }
    free(hlog);
    names_free(names, nn);
    if (cnt) qsort(v, cnt, sizeof *v, cmp_entry_desc);
    if (!cnt) { free(v); v = NULL; }
    *out = v; *n = cnt;
    return PK_OK;
}

/* Finds an entry by id: its unit and directory name. PK_E_NOT_FOUND if there is none. */
static pk_status locate(const pk_calstore *s, const char *id, char unit[65], char dirname[DIRNAME_LEN + 1]) {
    if (!id || !pkcal_is_hex(id, 64)) return PK_E_ARG;
    char p[PATH_MAX_], **units, **cals;
    size_t nu, nc;
    if (pathf(p, "%s/units", s->root)) return PK_E_ARG;
    pk_status st = list_dir(p, &units, &nu);
    if (st != PK_OK) return st;
    st = PK_E_NOT_FOUND;
    for (size_t i = 0; i < nu && st == PK_E_NOT_FOUND; i++) {
        if (!pkcal_unit_ok(units[i]) || pathf(p, "%s/units/%s/calibration", s->root, units[i])) continue;
        if (list_dir(p, &cals, &nc) != PK_OK) continue;
        for (size_t k = 0; k < nc; k++) {
            pk_cal_entry e;
            if (!dirname_ok(cals[k]) || strncmp(cals[k] + 17, id, 8) != 0 || read_entry(s, units[i], cals[k], &e) != PK_OK || strcmp(e.id, id) != 0) continue;
            strcpy(unit, units[i]); strcpy(dirname, cals[k]);
            st = PK_OK;
            break;
        }
        names_free(cals, nc);
    }
    names_free(units, nu);
    return st;
}

static pk_status load_dir(const char *dir, pkcal_files *fs) {
    memset(fs, 0, sizeof *fs);
    pk_status st = PK_OK;
    for (size_t i = 0; pkcal_known_name(i) && st == PK_OK; i++) {
        char p[PATH_MAX_];
        uint8_t *b;
        size_t n;
        if (pathf(p, "%s/%s", dir, pkcal_known_name(i))) { st = PK_E_ARG; break; }
        pk_status r = read_regular(p, &b, &n);
        if (r == PK_E_NOT_FOUND) continue;
        if (r != PK_OK) { st = r; break; }
        st = pkcal_files_add(fs, pkcal_known_name(i), b, n);
        free(b);
    }
    if (st != PK_OK) pkcal_files_free(fs);
    return st;
}

pk_status pk_calstore_get(pk_calstore *s, const char *id, pk_calibration **out) {
    if (out) *out = NULL;
    if (!s || !id || !out) return PK_E_ARG;
    char unit[65], dn[DIRNAME_LEN + 1], p[PATH_MAX_], got[65];
    pk_status st = locate(s, id, unit, dn);
    if (st != PK_OK) return st;
    if (pathf(p, "%s/units/%s/calibration/%s", s->root, unit, dn)) return PK_E_ARG;
    pkcal_files fs;
    if ((st = load_dir(p, &fs)) != PK_OK) return st == PK_E_NOT_FOUND ? PK_E_CORRUPT : st;
    pk_calibration *c;
    st = pkcal_check_files(&fs, &c, got);
    pkcal_files_free(&fs);
    if (st != PK_OK) return st;
    if (strcmp(got, id) != 0 || strcmp(c->unit, unit) != 0) { pk_calibration_free(c); return PK_E_CORRUPT; }
    *out = c;
    return PK_OK;
}

/* ------------------------------------------------------------------ writing */
static void rm_tmp(const char *tmp, const pkcal_files *fs) {   /* this process's own half-written directory only */
    char p[PATH_MAX_];
    for (size_t i = 0; i < fs->n; i++) if (pathf(p, "%s/%s", tmp, fs->f[i].name) == 0) unlink(p);
    if (pathf(p, "%s/raw", tmp) == 0) rmdir(p);
    rmdir(tmp);
}

/* Writes the files as units/<unit>/calibration/<utc>_<id8>/ (tmp directory, fsync, MANIFEST last, rename). Already present = success. */
static pk_status install(pk_calstore *s, const pkcal_files *fs, const pk_calibration *c) {
    char p[PATH_MAX_], fin[PATH_MAX_], tmp[PATH_MAX_];
    if (pathf(p, "%s/units/%s/calibration", s->root, c->unit)) return PK_E_ARG;
    pk_status st = pku_mkdirs(p);
    if (st != PK_OK) return st;
    if (pathf(p, "%s/units/%s/unit.json", s->root, c->unit)) return PK_E_ARG;
    if (!exists(p)) {
        pku_jw *w = pku_jw_new();
        if (!w) return PK_E_NOMEM;
        pku_jw_obj_begin(w);
        pku_jw_key(w, "schema"); pku_jw_str(w, "pakonunit");
        pku_jw_key(w, "version"); pku_jw_int(w, 1);
        pku_jw_key(w, "unit"); pku_jw_str(w, c->unit);
        pku_jw_obj_end(w);
        size_t n;
        const char *t = pku_jw_finish(w, &n);
        st = t ? pku_write_file_atomic(p, t, n) : PK_E_NOMEM;
        pku_jw_free(w);
        if (st != PK_OK) return st;
        if (pathf(p, "%s/units/%s", s->root, c->unit) || (st = fsync_dir(p)) != PK_OK) return st ? st : PK_E_ARG;
    }
    if (pathf(fin, "%s/units/%s/calibration/%s_%.8s", s->root, c->unit, c->utc, c->id)) return PK_E_ARG;
    if (exists(fin)) {                                                   /* the same content: one entry, once it is proved to be this one */
        pk_cal_entry e;
        char dn[DIRNAME_LEN + 1];
        snprintf(dn, sizeof dn, "%s_%.8s", c->utc, c->id);
        return read_entry(s, c->unit, dn, &e) == PK_OK && strcmp(e.id, c->id) == 0 ? PK_OK : PK_E_CORRUPT;
    }
    if (pathf(tmp, "%s.tmp.%ld", fin, (long)getpid())) return PK_E_ARG;
    if (mkdir(tmp, 0755) != 0) return PK_E_IO;
    const pkcal_file *man = pkcal_files_find(fs, "MANIFEST.sha256");
    if (!man) { rmdir(tmp); return PK_E_ARG; }
    for (size_t i = 0; i <= fs->n && st == PK_OK; i++) {                 /* every file, the MANIFEST last */
        const pkcal_file *f = i < fs->n ? &fs->f[i] : man;
        if (i < fs->n && f == man) continue;
        if (pathf(p, "%s/%s", tmp, f->name)) { st = PK_E_ARG; break; }
        if (strchr(f->name, '/')) {
            char sub[PATH_MAX_];
            if (pathf(sub, "%s/raw", tmp) || (mkdir(sub, 0755) && errno != EEXIST)) { st = PK_E_IO; break; }
        }
        st = write_new(p, f->data, f->n);
    }
    if (st == PK_OK) {
        char sub[PATH_MAX_];
        if (pathf(sub, "%s/raw", tmp) == 0 && exists(sub)) st = fsync_dir(sub);
        if (st == PK_OK) st = fsync_dir(tmp);
        if (st == PK_OK && rename(tmp, fin) != 0) {
            pk_cal_entry e;
            char dn[DIRNAME_LEN + 1];                                   /* lost a race: fine only if what is there is this same entry */
            snprintf(dn, sizeof dn, "%s_%.8s", c->utc, c->id);
            if (!exists(fin)) st = PK_E_IO;
            else if (read_entry(s, c->unit, dn, &e) != PK_OK || strcmp(e.id, c->id) != 0) st = PK_E_CORRUPT;
        }
    }
    if (st != PK_OK || exists(tmp)) rm_tmp(tmp, fs);
    if (st == PK_OK) {
        if (pathf(p, "%s/units/%s/calibration", s->root, c->unit) == 0) st = fsync_dir(p);
        if (st == PK_OK && pathf(p, "%s/units/%s", s->root, c->unit) == 0) st = fsync_dir(p);
        if (st == PK_OK && pathf(p, "%s/units", s->root) == 0) st = fsync_dir(p);
    }
    return st;
}

/* A time later than now + 1 day is refused for a put and an import alike. */
static void future_limit(char out[24]) {
    time_t t = time(NULL) + 86400;
    struct tm tm;
    gmtime_r(&t, &tm);
    strftime(out, 24, "%Y%m%dT%H%M%SZ", &tm);
}

static pk_status put_impl(pk_calstore *s, const pk_calibration *c, char id_out[65], int is_local) {
    if (id_out) id_out[0] = 0;
    if (!s || !c || !c->have_light) return PK_E_ARG;
    char utc[24], limit[24];
    now_utc(utc);
    future_limit(limit);
    if (c->utc[0] && strcmp(c->utc, limit) > 0) return PK_E_ARG;
    pkcal_files fs;
    pk_status st = pkcal_build_files(c, utc, &fs);
    if (st != PK_OK) return st;
    pk_calibration *chk;
    char id[65];
    if ((st = pkcal_check_files(&fs, &chk, id)) == PK_OK) {      /* what is written is exactly what get returns */
        /* R2-I1/R3-I1: an id that may already be stored (an import read back and put again) never joins local.log. Fail closed: only a clean
         * "not found" from locate AND an ENOENT on the target directory (install's own test) count as new. */
        char lu[65], ldn[DIRNAME_LEN + 1], tgt[PATH_MAX_];
        struct stat tsb;
        bool stored = locate(s, id, lu, ldn) != PK_E_NOT_FOUND;
        if (!stored) {
            if (pathf(tgt, "%s/units/%s/calibration/%s_%.8s", s->root, chk->unit, chk->utc, id)) stored = true;
            else if (lstat(tgt, &tsb) == 0 || errno != ENOENT) stored = true;
        }
        if (is_local && !stored && unidentified(chk->unit)) {     /* write-ahead: the allowlist line is durable before the directory exists */
            char p[PATH_MAX_], line[160];
            snprintf(line, sizeof line, "%s %s local\n", utc, id);
            if (pathf(p, "%s/units/%s", s->root, chk->unit)) st = PK_E_ARG;
            else if ((st = pku_mkdirs(p)) == PK_OK && pathf(p, "%s/units/%s/local.log", s->root, chk->unit) == 0 && (st = append_line(p, line)) == PK_OK &&
                     pathf(p, "%s/units/%s", s->root, chk->unit) == 0)
                st = fsync_dir(p);
        }
        if (st == PK_OK) st = install(s, &fs, chk);
        pk_calibration_free(chk);
    }
    pkcal_files_free(&fs);
    if (st == PK_OK && id_out) memcpy(id_out, id, 65);
    return st;
}

pk_status pk_calstore_put(pk_calstore *s, const pk_calibration *c, char id_out[65]) { return put_impl(s, c, id_out, 1); }
/* The PSI importer's put: the entry is an import, so it never joins local.log. */
pk_status pkcal_store_put_imported(pk_calstore *s, const pk_calibration *c, char id_out[65]) { return put_impl(s, c, id_out, 0); }

/* ------------------------------------------------------------------ hide */
pk_status pk_calstore_hide(pk_calstore *s, const char *id, bool hidden) {
    if (!s || !id) return PK_E_ARG;
    char unit[65], dn[DIRNAME_LEN + 1], p[PATH_MAX_], line[160], utc[24];
    pk_status st = locate(s, id, unit, dn);
    if (st != PK_OK) return st;
    now_utc(utc);
    snprintf(line, sizeof line, "%s %s %s\n", utc, id, hidden ? "hidden" : "unhidden");
    if (pathf(p, "%s/units/%s/hidden.log", s->root, unit)) return PK_E_ARG;
    return append_line(p, line);
}

/* ------------------------------------------------------------------ selection */
static pk_status scope_key(pk_cal_scope sc, bool ir, char key[16]) {
    static const char *const K[] = { "all", "base4", "base8", "base16" };
    if ((unsigned)sc > PK_SCOPE_BASE16) return PK_E_ARG;
    snprintf(key, 16, "%s%s", K[sc], ir ? "-ir" : "");
    return PK_OK;
}
static int scope_base(pk_cal_scope sc) { return sc == PK_SCOPE_BASE4 ? 4 : sc == PK_SCOPE_BASE8 ? 8 : sc == PK_SCOPE_BASE16 ? 16 : 0; }

pk_status pk_calstore_selection_ir(pk_calstore *s, const char *unit, pk_cal_scope sc, bool ir, char id_out[65]) {
    if (id_out) strcpy(id_out, "auto");
    char key[16], p[PATH_MAX_];
    if (!s || !unit || !id_out || !pkcal_unit_ok(unit)) return PK_E_ARG;
    pk_status st = scope_key(sc, ir, key);
    if (st != PK_OK || pathf(p, "%s/units/%s/selection.log", s->root, unit)) return PK_E_ARG;
    uint8_t *buf;
    size_t n;
    if ((st = read_regular(p, &buf, &n)) != PK_OK) return st == PK_E_NOT_FOUND ? PK_OK : st;
    size_t pos = 0;
    char line[256], *t[3];
    while (next_line(buf, n, &pos, line))
        if (split3(line, t) && pkcal_utc_ok(t[0]) && strcmp(t[1], key) == 0 && (strcmp(t[2], "auto") == 0 || pkcal_is_hex(t[2], 64))) strcpy(id_out, t[2]);
    free(buf);
    return PK_OK;
}

/* A pinned entry must exist, belong to `unit` and not be foreign (PK_E_CAL_FOREIGN); hidden and imported ones are fine. */
static pk_status pin_entry(const pk_calstore *s, const char *unit, const char *id, pk_cal_entry *e) {
    char eu[65], dn[DIRNAME_LEN + 1];
    pk_status st = locate(s, id, eu, dn);
    if (st != PK_OK) return st;
    if ((st = read_entry(s, eu, dn, e)) != PK_OK) return st;
    if (strcmp(eu, unit) != 0 || is_foreign(s, eu, e->kind)) return PK_E_CAL_FOREIGN;
    return PK_OK;
}

pk_status pk_calstore_select_ir(pk_calstore *s, const char *unit, pk_cal_scope sc, bool ir, const char *id_or_auto) {
    char key[16], p[PATH_MAX_], line[200], utc[24];
    if (!s || !unit || !id_or_auto || !pkcal_unit_ok(unit)) return PK_E_ARG;
    pk_status st = scope_key(sc, ir, key);
    if (st != PK_OK) return st;
    if (strcmp(id_or_auto, "auto") != 0) {
        pk_cal_entry e;
        if ((st = pin_entry(s, unit, id_or_auto, &e)) != PK_OK) return st;
        if (e.ir != ir || (sc != PK_SCOPE_ALL && e.dpi_base != scope_base(sc))) return PK_E_ARG;
    }
    if (pathf(p, "%s/units/%s", s->root, unit)) return PK_E_ARG;
    if ((st = pku_mkdirs(p)) != PK_OK) return st;
    now_utc(utc);
    snprintf(line, sizeof line, "%s %s %s\n", utc, key, id_or_auto);
    if (pathf(p, "%s/units/%s/selection.log", s->root, unit)) return PK_E_ARG;
    return append_line(p, line);
}

/* Order: the scope's pin; else an "all" pin whose entry fits this base and ir; else auto = the newest native entry (session, gain, focus, track),
 * and only if there is none the newest imported one. Never hidden, never foreign; and in a "-unidentified" unit only an entry listed in local.log (an
 * allowlist: a missing, torn or unreadable log means none is auto-selected, never an error), though an explicit pin of any entry is allowed. */
pk_status pk_calstore_resolve_ir(pk_calstore *s, const char *unit, pk_cal_scope sc, bool ir, char id_out[65]) {
    if (id_out) id_out[0] = 0;
    if (!s || !unit || !id_out) return PK_E_ARG;
    char sel[65];
    pk_cal_entry e;
    pk_status st = pk_calstore_selection_ir(s, unit, sc, ir, sel);
    if (st != PK_OK) return st;
    if (strcmp(sel, "auto") != 0) {
        if ((st = pin_entry(s, unit, sel, &e)) != PK_OK) return st;
        strcpy(id_out, sel);
        return PK_OK;
    }
    if (sc != PK_SCOPE_ALL && pk_calstore_selection_ir(s, unit, PK_SCOPE_ALL, ir, sel) == PK_OK && strcmp(sel, "auto") != 0 &&
        pin_entry(s, unit, sel, &e) == PK_OK && e.ir == ir && e.dpi_base == scope_base(sc)) {
        strcpy(id_out, sel);
        return PK_OK;
    }
    pk_cal_entry *v;
    size_t n;
    if ((st = pk_calstore_list(s, unit, &v, &n, false)) != PK_OK) return st;
    uint8_t *llog = NULL;
    size_t lln = 0;
    char p[PATH_MAX_];
    int need_local = unidentified(unit);
    if (need_local && (pathf(p, "%s/units/%s/local.log", s->root, unit) || read_regular(p, &llog, &lln) != PK_OK)) { llog = NULL; lln = 0; }
    int saw_foreign = 0;
    st = PK_E_NOT_FOUND;
    for (int pass = 0; pass < 2 && st != PK_OK; pass++) {                 /* native first, then imported */
        for (size_t i = 0; i < n; i++) {
            if (v[i].ir != ir || (sc != PK_SCOPE_ALL && v[i].dpi_base != scope_base(sc)) || pkcal_kind_imported(v[i].kind) != pass) continue;
            if (v[i].foreign) { saw_foreign = 1; continue; }
            if (need_local && !(llog && log_local(llog, lln, v[i].id))) continue;
            strcpy(id_out, v[i].id);
            st = PK_OK;
            break;
        }
    }
    if (st != PK_OK && saw_foreign && !s->has_local) st = PK_E_CAL_FOREIGN;   /* nothing could be shown to be this scanner's */
    free(llog);
    free(v);
    return st;
}

pk_status pk_calstore_select(pk_calstore *s, const char *unit, pk_cal_scope sc, const char *id) { return pk_calstore_select_ir(s, unit, sc, false, id); }
pk_status pk_calstore_resolve(pk_calstore *s, const char *unit, pk_cal_scope sc, char id[65]) { return pk_calstore_resolve_ir(s, unit, sc, false, id); }
pk_status pk_calstore_selection(pk_calstore *s, const char *unit, pk_cal_scope sc, char id[65]) { return pk_calstore_selection_ir(s, unit, sc, false, id); }

/* ------------------------------------------------------------------ export / import */
pk_status pk_calstore_export(pk_calstore *s, const char *id, const char *path) {
    if (!s || !id || !path) return PK_E_ARG;
    char unit[65], dn[DIRNAME_LEN + 1], p[PATH_MAX_], got[65];
    pk_status st = locate(s, id, unit, dn);
    if (st != PK_OK) return st;
    if (pathf(p, "%s/units/%s/calibration/%s", s->root, unit, dn)) return PK_E_ARG;
    pkcal_files fs;
    if ((st = load_dir(p, &fs)) != PK_OK) return st == PK_E_NOT_FOUND ? PK_E_CORRUPT : st;
    uint8_t *zip = NULL;
    size_t zn = 0;
    if ((st = pkcal_check_files(&fs, NULL, got)) == PK_OK && strcmp(got, id) != 0) st = PK_E_CORRUPT;
    if (st == PK_OK) st = pkcal_pack(&fs, &zip, &zn);
    pkcal_files_free(&fs);
    if (st == PK_OK) st = pku_write_file_atomic(path, zip, zn);
    free(zip);
    return st;
}

pk_status pk_calstore_import(pk_calstore *s, const char *path, pk_cal_import_report *rep) {
    if (rep) memset(rep, 0, sizeof *rep);
    if (!s || !path) return PK_E_ARG;
    uint8_t *buf;
    size_t n;
    pk_status st = pku_read_file(path, &buf, &n);
    if (st != PK_OK) return st;
    pkcal_files fs;
    st = pkcal_unpack(buf, n, &fs);
    free(buf);
    if (st != PK_OK) return st;
    pk_calibration *c;
    char id[65];
    if ((st = pkcal_check_files(&fs, &c, id)) == PK_OK) {
        char limit[24];                                                 /* a file's own time is trusted no further than a day ahead */
        future_limit(limit);
        if (strcmp(c->utc, limit) > 0) st = PK_E_CORRUPT;
        else if ((st = install(s, &fs, c)) == PK_OK) {
            if (st == PK_OK && rep) {
                rep->n_files = fs.n;
                rep->foreign = is_foreign(s, c->unit, c->kind) != 0;
                memcpy(rep->id, id, 65);
            }
        }
        pk_calibration_free(c);
    }
    pkcal_files_free(&fs);
    return st;
}
