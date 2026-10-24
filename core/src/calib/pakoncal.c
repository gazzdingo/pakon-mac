/* The .pakoncal file: a stored-only zip of one calibration directory's files, entry names identical to the directory's (calibration.json, light.json,
 * the table blobs, MANIFEST.sha256 last). Written deterministically, so export then import is byte-identical. */
#include "calib/record.h"
#include "util/util.h"
#include <stdlib.h>
#include <string.h>

pk_status pkcal_pack(const pkcal_files *fs, uint8_t **zip, size_t *n) {
    if (zip) *zip = NULL;
    if (n) *n = 0;
    if (!fs || !zip || !n) return PK_E_ARG;
    pku_zipw *w = pku_zipw_new();
    if (!w) return PK_E_NOMEM;
    pk_status st = PK_OK;
    for (size_t i = 0; i < fs->n && st == PK_OK; i++)    /* the MANIFEST last, as in the directory */
        if (strcmp(fs->f[i].name, "MANIFEST.sha256") != 0) st = pku_zipw_add(w, fs->f[i].name, fs->f[i].data, fs->f[i].n);
    const pkcal_file *m = pkcal_files_find(fs, "MANIFEST.sha256");
    if (st == PK_OK && m) st = pku_zipw_add(w, m->name, m->data, m->n);
    if (st == PK_OK) st = pku_zipw_finish(w, zip, n);
    pku_zipw_free(w);
    return st;
}

pk_status pkcal_unpack(const uint8_t *zip, size_t n, pkcal_files *fs) {
    if (!fs) return PK_E_ARG;
    memset(fs, 0, sizeof *fs);
    pku_zip *z;
    pk_status st = pku_zip_open(zip, n, PKCAL_ZIP_MAX_ENTRIES, PKCAL_ZIP_MAX_ENTRY, PKCAL_ZIP_MAX_TOTAL, &z);
    if (st != PK_OK) return st;
    for (size_t i = 0; i < pku_zip_count(z) && st == PK_OK; i++) {
        const pku_zip_entry *e = pku_zip_at(z, i);
        if (!pkcal_name_ok(e->name)) st = PK_E_CORRUPT;           /* an unknown file name is a format this build does not know */
        else st = pkcal_files_add(fs, e->name, e->data, e->size);
    }
    pku_zip_close(z);
    if (st != PK_OK) pkcal_files_free(fs);
    return st;
}
