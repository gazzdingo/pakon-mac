/* Vendor manifest, import and open. Every vendor folder is hostile: paths are checked with pku_path_is_safe, files are
 * opened without following symlinks and must resolve inside the folder, sizes are checked against the manifest before a
 * byte is read, and every hash is verified. Import verifies everything in memory first, so a failure writes nothing. */
#include "vendor/vendor.h"
#include "util/util.h"
#include "decode/lores_weights.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define PKVN_STORE "3.0.4.27"
#define PKVN_MAX_ONE ((size_t)16 << 20)     /* a manifest row above this is a manifest bug */
#define PKVN_MAX_ALL ((size_t)128 << 20)
#define PKVN_PATH 2048

struct pk_vendor {
    const pkvn_row *rows;
    size_t n;
    unsigned char *present;
    char root[PKVN_PATH];
};

static const pkvn_row GEN_ROWS[] = {
#define PK_VENDOR(item, p1, p2, p3, p4, size, sha, ho, opt) { item, { p1, p2, p3, p4 }, size, sha, ho, opt },
#include "../../tables/vendor_manifest.def"
#undef PK_VENDOR
};

/* Where a pre-extracted layout may put the Pakon folder, relative to the folder the user names. */
static const char *const PREFIX[] = {
    "", "fx35install/", "fx35install/program files/Pakon/", "program files/Pakon/", "Program Files/Pakon/", "Pakon/"
};

static void report_add(pk_vendor_report *r, const pkvn_row *row) {
    if (!r) return;
    for (size_t k = 0; k < 16; k++)
        if (!r->names[k][0]) { snprintf(r->names[k], sizeof r->names[k], "%s", row->paths[0]); return; }
}

typedef enum { RD_OK, RD_ABSENT, RD_BAD, RD_HOSTILE, RD_ERR } rd_t;

static int hex_eq(const char *a, const char *b) {
    for (int i = 0; i < 64; i++) {
        char x = a[i], y = b[i];
        if (x >= 'A' && x <= 'F') x = (char)(x + 32);
        if (y >= 'A' && y <= 'F') y = (char)(y + 32);
        if (x != y || !x) return 0;
    }
    return 1;
}

/* Reads base/rel as a regular file of exactly `size` bytes with the given hash. *data is set only on RD_OK (and may be
 * NULL if want_data is 0). */
static rd_t read_verified(const char *base, const char *rel, size_t size, const char *sha, int want_data,
                          uint8_t **data, pk_status *err) {
    if (data) *data = NULL;
    char full[PKVN_PATH];
    if (snprintf(full, sizeof full, "%s/%s", base, rel) >= (int)sizeof full) return RD_HOSTILE;
    struct stat ls;
    if (lstat(full, &ls)) return errno == ENOENT || errno == ENOTDIR ? RD_ABSENT : RD_ERR;
    if (!S_ISREG(ls.st_mode)) return RD_HOSTILE;                  /* symlink, directory, device, fifo */
    char rb[PKVN_PATH], rf[PKVN_PATH];
    if (!realpath(base, rb) || !realpath(full, rf)) return RD_ERR;
    size_t lb = strlen(rb);
    if (strncmp(rb, rf, lb) != 0 || (lb > 1 && rf[lb] != '/')) return RD_HOSTILE;   /* a parent directory is a symlink out */
    int fd = open(full, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return errno == ELOOP ? RD_HOSTILE : RD_ERR;
    struct stat fs;
    rd_t rc = RD_ERR;
    uint8_t *buf = NULL;
    if (fstat(fd, &fs) || !S_ISREG(fs.st_mode) || fs.st_ino != ls.st_ino || fs.st_dev != ls.st_dev) { rc = RD_HOSTILE; goto out; }
    if (fs.st_size < 0 || (unsigned long long)fs.st_size != size) { rc = RD_BAD; goto out; }
    buf = malloc(size ? size + 1 : 1);
    if (!buf) { *err = PK_E_NOMEM; goto out; }
    size_t got = 0;
    while (got < size + 1) {                                       /* one byte more: the file must end at `size` */
        ssize_t r = read(fd, buf + got, size + 1 - got);
        if (r < 0 && errno == EINTR) continue;
        if (r < 0) goto out;
        if (r == 0) break;
        got += (size_t)r;
    }
    if (got != size) { rc = RD_BAD; goto out; }
    char hex[65];
    pku_sha256_hex(buf, size, hex);
    if (!hex_eq(hex, sha)) { rc = RD_BAD; goto out; }
    rc = RD_OK;
out:
    close(fd);
    if (rc == RD_OK && want_data && data) { *data = buf; buf = NULL; }
    free(buf);
    return rc;
}

static pk_status check_rows(const pkvn_row *rows, size_t n) {
    if (!rows && n) return PK_E_ARG;
    size_t total = 0;
    for (size_t i = 0; i < n; i++) {
        const pkvn_row *r = &rows[i];
        if (!r->paths[0] || !r->sha256 || strlen(r->sha256) != 64 || r->size > PKVN_MAX_ONE) return PK_E_CORRUPT;
        total += r->size;
        for (int k = 0; k < 4; k++)
            if (r->paths[k] && !pku_path_is_safe(r->paths[k])) return PK_E_CORRUPT;   /* a manifest bug must not escape */
    }
    return total > PKVN_MAX_ALL ? PK_E_CORRUPT : PK_OK;
}

static void rep_init(pk_vendor_report *r) { if (r) memset(r, 0, sizeof *r); }

/* Classifies one row's outcome into the report and the aggregate status. */
typedef struct { int hostile, bad, missing_req; } tally;
static void note(const pkvn_row *row, rd_t rc, pk_vendor_report *rep, tally *t) {
    switch (rc) {
    case RD_OK: if (rep) rep->n_ok++; break;
    case RD_ABSENT:
        if (rep) rep->n_missing++;
        if (!row->optional) { t->missing_req++; report_add(rep, row); }
        break;
    case RD_HOSTILE: t->hostile++; if (rep) rep->n_mismatch++; report_add(rep, row); break;
    default: t->bad++; if (rep) rep->n_mismatch++; report_add(rep, row); break;
    }
}
static pk_status verdict(const tally *t) {
    if (t->hostile) return PK_E_CORRUPT;
    if (t->bad || t->missing_req) return PK_E_VENDOR_MISSING;
    return PK_OK;
}

pk_status pkvn_open_rep_with(const pkvn_row *rows, size_t n, const char *dest_root, pk_vendor_report *rep, pk_vendor **out) {
    rep_init(rep);
    if (out) *out = NULL;
    if (!dest_root || !out) return PK_E_ARG;
    pk_status st = check_rows(rows, n);
    if (st) return st;
    pk_vendor *v = calloc(1, sizeof *v);
    if (!v) return PK_E_NOMEM;
    v->present = calloc(n ? n : 1, 1);
    if (!v->present || snprintf(v->root, sizeof v->root, "%s/" PKVN_STORE, dest_root) >= (int)sizeof v->root) {
        st = v->present ? PK_E_ARG : PK_E_NOMEM;
        goto fail;
    }
    v->rows = rows; v->n = n;
    tally t = {0, 0, 0};
    for (size_t i = 0; i < n; i++) {
        pk_status e = PK_OK;
        rd_t rc = read_verified(v->root, rows[i].paths[0], rows[i].size, rows[i].sha256, 0, NULL, &e);
        if (rc == RD_ERR) { st = e ? e : PK_E_IO; goto fail; }
        if (e) { st = e; goto fail; }
        v->present[i] = rc == RD_OK;
        note(&rows[i], rc, rep, &t);
    }
    st = verdict(&t);
    if (st) goto fail;
    *out = v;
    return PK_OK;
fail:
    if (v) { free(v->present); free(v); }
    return st;
}

pk_status pkvn_open_with(const pkvn_row *rows, size_t n, const char *dest_root, pk_vendor **out) {
    return pkvn_open_rep_with(rows, n, dest_root, NULL, out);
}

static const pkvn_row *find_row(const pk_vendor *v, int item, size_t *idx) {
    if (!v) return NULL;
    for (size_t i = 0; i < v->n; i++)
        if (v->rows[i].item == item) { if (idx) *idx = i; return &v->rows[i]; }
    return NULL;
}

pk_status pk_vendor_file(pk_vendor *v, pk_vendor_item item, pk_bytes *out) {
    if (out) { out->data = NULL; out->len = 0; }
    size_t i;
    const pkvn_row *r = find_row(v, (int)item, &i);
    if (!r || !out) return PK_E_ARG;
    if (r->hash_only) return PK_E_ARG;
    if (!v->present[i]) return PK_E_VENDOR_MISSING;
    pk_status e = PK_OK;
    uint8_t *d = NULL;
    rd_t rc = read_verified(v->root, r->paths[0], r->size, r->sha256, 1, &d, &e);
    if (rc == RD_OK) { out->data = d; out->len = r->size; return PK_OK; }
    if (e) return e;
    return rc == RD_HOSTILE ? PK_E_CORRUPT : rc == RD_ERR ? PK_E_IO : PK_E_VENDOR_MISSING;
}

pk_status pk_vendor_hash_only(pk_vendor *v, pk_vendor_item item, char sha256_hex[65]) {
    size_t i;
    const pkvn_row *r = find_row(v, (int)item, &i);
    if (!r || !sha256_hex) return PK_E_ARG;
    if (!v->present[i]) return PK_E_VENDOR_MISSING;
    memcpy(sha256_hex, r->sha256, 64);
    sha256_hex[64] = 0;
    for (int k = 0; k < 64; k++) if (sha256_hex[k] >= 'A' && sha256_hex[k] <= 'F') sha256_hex[k] = (char)(sha256_hex[k] + 32);
    return PK_OK;
}

int pk_vendor_has(const pk_vendor *v, pk_vendor_item item) {
    size_t i;
    return find_row(v, (int)item, &i) && v->present[i];
}

void pk_vendor_close(pk_vendor *v) {
    if (!v) return;
    free(v->present);
    free(v);
}

/* ---------------------------------------------------------------- import */

static pk_status ensure_dir_parent(const char *path) {
    char d[PKVN_PATH];
    if (snprintf(d, sizeof d, "%s", path) >= (int)sizeof d) return PK_E_ARG;
    char *s = strrchr(d, '/');
    if (!s) return PK_OK;
    *s = 0;
    return pku_mkdirs(d);
}

pk_status pkvn_import_with(const pkvn_row *rows, size_t n, const char *src_dir, const char *dest_root, pk_vendor_report *out) {
    rep_init(out);
    if (!src_dir || !dest_root) return PK_E_ARG;
    pk_status st = check_rows(rows, n);
    if (st) return st;
    uint8_t **bufs = calloc(n ? n : 1, sizeof *bufs);
    if (!bufs) return PK_E_NOMEM;
    tally t = {0, 0, 0};
    char final[PKVN_PATH];
    if (snprintf(final, sizeof final, "%s/" PKVN_STORE, dest_root) >= (int)sizeof final) { st = PK_E_ARG; goto done; }

    /* 1. find and verify every item in memory; nothing is written yet */
    for (size_t i = 0; i < n; i++) {
        const pkvn_row *r = &rows[i];
        rd_t rc = RD_ABSENT;
        for (int k = 0; k < 4 && r->paths[k] && rc == RD_ABSENT; k++)
            for (size_t p = 0; p < sizeof PREFIX / sizeof *PREFIX && rc == RD_ABSENT; p++) {
                char rel[PKVN_PATH];
                if (snprintf(rel, sizeof rel, "%s%s", PREFIX[p], r->paths[k]) >= (int)sizeof rel) { rc = RD_HOSTILE; break; }
                pk_status e = PK_OK;
                rc = read_verified(src_dir, rel, r->size, r->sha256, 1, &bufs[i], &e);
                if (e) { st = e; goto done; }
            }
        if (rc == RD_ERR) { st = PK_E_IO; goto done; }
        note(r, rc, out, &t);
    }
    st = verdict(&t);
    if (st) goto done;

    /* 2. an existing store gets the verified items it lacks (never replaced, never deleted). The store's own files are
     * checked first; a damaged one refuses the whole import before anything is written. */
    struct stat fs;
    if (lstat(final, &fs) == 0) {
        unsigned char *have = calloc(n ? n : 1, 1);
        if (!have) { st = PK_E_NOMEM; goto done; }
        pk_vendor_report fresh;
        rep_init(&fresh);
        tally ts = {0, 0, 0};
        for (size_t i = 0; i < n; i++) {
            pk_status e = PK_OK;
            rd_t rc = read_verified(final, rows[i].paths[0], rows[i].size, rows[i].sha256, 0, NULL, &e);
            if (e || rc == RD_ERR) { st = e ? e : PK_E_IO; free(have); goto done; }
            have[i] = rc == RD_OK;
            if (rc != RD_ABSENT) note(&rows[i], rc, &fresh, &ts);
        }
        if (ts.hostile || ts.bad) {                       /* damaged existing store: refuse; the owner removes it */
            if (out) { *out = fresh; }
            st = PK_E_CORRUPT;
            free(have);
            goto done;
        }
        for (size_t i = 0; i < n && !st; i++) {
            if (have[i]) continue;                        /* already counted in n_ok by the scan above */
            if (!bufs[i]) {
                fresh.n_missing++;
                if (!rows[i].optional) report_add(&fresh, &rows[i]);
                continue;
            }
            char dst[PKVN_PATH];
            if (snprintf(dst, sizeof dst, "%s/%s", final, rows[i].paths[0]) >= (int)sizeof dst) st = PK_E_ARG;
            else if (lstat(dst, &fs) == 0) st = PK_E_CORRUPT;   /* appeared meanwhile: never replace */
            else if (!(st = ensure_dir_parent(dst)) && !(st = pku_write_file_atomic(dst, bufs[i], rows[i].size))) {
                fresh.n_ok++; fresh.n_added++;
            }
        }
        if (out) *out = fresh;
        free(have);
        goto done;
    }

    /* 3. write into dest_root/.tmp.<pid>[.n]/, then one rename */
    if ((st = pku_mkdirs(dest_root))) goto done;
    char tmp[PKVN_PATH];
    int made = 0;
    for (int tries = 0; tries < 100 && !made; tries++) {
        if (snprintf(tmp, sizeof tmp, tries ? "%s/.tmp.%ld.%d" : "%s/.tmp.%ld", dest_root, (long)getpid(), tries) >= (int)sizeof tmp) {
            st = PK_E_ARG; goto done;
        }
        if (mkdir(tmp, 0755) == 0) made = 1;
        else if (errno != EEXIST) { st = PK_E_IO; goto done; }
    }
    if (!made) { st = PK_E_IO; goto done; }
    for (size_t i = 0; i < n; i++) {
        if (!bufs[i]) continue;
        char dst[PKVN_PATH];
        if (snprintf(dst, sizeof dst, "%s/%s", tmp, rows[i].paths[0]) >= (int)sizeof dst) { st = PK_E_ARG; goto done; }
        if ((st = ensure_dir_parent(dst)) || (st = pku_write_file_atomic(dst, bufs[i], rows[i].size))) goto done;
    }
    if (rename(tmp, final)) { st = PK_E_IO; goto done; }
    if (out) out->n_added = out->n_ok;
    st = PK_OK;
done:
    if (bufs) { for (size_t i = 0; i < n; i++) free(bufs[i]); free(bufs); }
    return st;
}

/* C9: TLB.dll (3.0.4.27) -> dest_root/3.0.4.27/lores_weights.bin. Not a manifest item: only 464 bytes of it are kept. */
#define TLB_SIZE 536576u
#define TLB_SHA "5866ec56776644e23c2c7e3755b4fc097761395db5731bf242998794a6f01647"
pk_status pk_lores_weights_import(const char *src_dir, const char *dest_root) {
    if (!src_dir || !dest_root) return PK_E_ARG;
    static const char *const REL[] = { "F-X35 COM SERVER/TLB.dll", "TLB.dll" };
    uint8_t *tlb = NULL;
    rd_t rc = RD_ABSENT;
    for (size_t p = 0; p < sizeof PREFIX / sizeof *PREFIX && rc != RD_OK; p++)
        for (size_t k = 0; k < 2 && rc != RD_OK; k++) {
            char rel[PKVN_PATH];
            if (snprintf(rel, sizeof rel, "%s%s", PREFIX[p], REL[k]) >= (int)sizeof rel) continue;
            pk_status e = PK_OK;
            rd_t r = read_verified(src_dir, rel, TLB_SIZE, TLB_SHA, 1, &tlb, &e);
            if (e) return e;
            if (r == RD_OK || rc == RD_ABSENT) rc = r;
        }
    if (rc == RD_ERR) return PK_E_IO;
    if (rc == RD_HOSTILE || rc == RD_BAD) return PK_E_CORRUPT;
    if (rc != RD_OK) return PK_E_VENDOR_MISSING;
    uint8_t blob[PKD_LORES_BLOB];
    pk_status st = pkd_lores_from_tlb(tlb, TLB_SIZE, blob);
    free(tlb);
    if (st) return st;
    char dst[PKVN_PATH];
    if (snprintf(dst, sizeof dst, "%s/" PKVN_STORE "/lores_weights.bin", dest_root) >= (int)sizeof dst) return PK_E_ARG;
    struct stat fs;
    if (lstat(dst, &fs) == 0) return PK_OK;                       /* never replaced */
    return pku_write_file_atomic(dst, blob, sizeof blob);
}

pk_status pk_lores_weights_load(const char *dest_root, const char *derived_root) {
    if (pkd_lores_ready()) return PK_OK;
    if (dest_root) {
        char path[PKVN_PATH];
        if (snprintf(path, sizeof path, "%s/" PKVN_STORE "/lores_weights.bin", dest_root) < (int)sizeof path &&
            pkd_lores_load_blob_file(path) == PK_OK) return PK_OK;
    }
    if (derived_root && pkd_lores_load_derived(derived_root) == PK_OK) return PK_OK;
    return PK_E_VENDOR_MISSING;
}
int pk_lores_weights_loaded(void) { return pkd_lores_ready(); }

pk_status pk_vendor_import(const char *src_dir, const char *dest_root, pk_vendor_report *out) {
    pk_status st = pkvn_import_with(GEN_ROWS, sizeof GEN_ROWS / sizeof *GEN_ROWS, src_dir, dest_root, out);
    if (st == PK_OK) (void)pk_lores_weights_import(src_dir, dest_root);
    return st;
}
pk_status pk_vendor_open_ex(const char *dest_root, pk_vendor_report *rep, pk_vendor **out) {
    return pkvn_open_rep_with(GEN_ROWS, sizeof GEN_ROWS / sizeof *GEN_ROWS, dest_root, rep, out);
}
pk_status pk_vendor_open(const char *dest_root, pk_vendor **out) { return pk_vendor_open_ex(dest_root, NULL, out); }
