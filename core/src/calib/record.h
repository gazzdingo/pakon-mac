#ifndef PAKON_CALIB_RECORD_H
#define PAKON_CALIB_RECORD_H
/* The internal builder for pk_calibration (prefix pkcal_), shared by the calibration search (Task 15), psi_import.c and the roll importer, and the
 * file-set form used by the store and the .pakoncal layout. pk_calibration itself stays opaque in the public header. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "pakon/calstore.h"

#define PKCAL_NAME_MAX 24
#define PKCAL_MAX_BLOBS 12               /* >= the number of blob names (checked in record.c) */
#define PKCAL_SCHEMA "pakoncal"
#define PKCAL_VERSION 1
#define PKCAL_ZIP_MAX_ENTRIES 64u                     /* a .pakoncal: entry count and size limits */
#define PKCAL_ZIP_MAX_ENTRY ((size_t)256 << 20)
#define PKCAL_ZIP_MAX_TOTAL ((size_t)1 << 30)

struct pk_calibration {
    char unit[65], kind[16], utc[24], parent[65], id[65];
    int dpi_base;                    /* 0 only for a record without light settings of its own; 4, 8 or 16 once pkcal_set_light has run */
    bool ir;
    pk_cal_light light;
    bool have_light;
    size_t n_blob;
    struct { char name[PKCAL_NAME_MAX]; uint8_t *data; size_t n; } blob[PKCAL_MAX_BLOBS];
};

/* The files of one calibration directory (copies), in the order added. */
typedef struct { char name[PKCAL_NAME_MAX]; uint8_t *data; size_t n; } pkcal_file;
typedef struct { pkcal_file *f; size_t n, cap; } pkcal_files;
void pkcal_files_free(pkcal_files *fs);
pk_status pkcal_files_add(pkcal_files *fs, const char *name, const void *data, size_t n);
const pkcal_file *pkcal_files_find(const pkcal_files *fs, const char *name);

int pkcal_unit_ok(const char *unit);      /* 1..64 of [A-Za-z0-9._-], not starting with '.' */
int pkcal_name_ok(const char *name);      /* one of the fixed file names of a calibration directory */
int pkcal_blob_name_ok(const char *name); /* ... other than calibration.json, light.json, MANIFEST.sha256 */
const char *pkcal_known_name(size_t i);   /* the i-th of the fixed file names, NULL past the end */
int pkcal_utc_ok(const char *utc);         /* YYYYMMDDTHHMMSSZ */
int pkcal_is_hex(const char *s, size_t n); /* exactly n lowercase hex digits */

/* Builder. kind: session|gain|focus|track|imported-psi|imported-file. parent is NULL or a 64-hex id. */
pk_calibration *pkcal_new(void);
pk_status pkcal_set_meta(pk_calibration *c, const char *unit, const char *kind, const char *parent);
pk_status pkcal_set_utc(pk_calibration *c, const char *utc);       /* YYYYMMDDTHHMMSSZ; unset = the time of the put */
pk_status pkcal_set_light(pk_calibration *c, const pk_cal_light *l);   /* validates ranges; takes dpi_base and ir from it */
pk_status pkcal_add_blob(pk_calibration *c, const char *name, const void *data, size_t n);

/* c -> files: calibration.json, light.json, blobs, then MANIFEST.sha256 last. utc is used when c has none. PK_E_ARG if unit, kind or light is unset. */
pk_status pkcal_build_files(const pk_calibration *c, const char *utc, pkcal_files *out);
/* files -> verified record: MANIFEST present and exactly the files' hashes, known schema/version, every field in range. id = sha256(MANIFEST).
 * out may be NULL. PK_E_CORRUPT on any failure. */
pk_status pkcal_check_files(const pkcal_files *fs, pk_calibration **out, char id[65]);

/* The .pakoncal layout over pku_zip: one stored entry per file, the same names as the directory. Limits: 64 entries, 256 MiB each. */
pk_status pkcal_pack(const pkcal_files *fs, uint8_t **zip, size_t *n);
pk_status pkcal_unpack(const uint8_t *zip, size_t n, pkcal_files *fs);

/* store.c: whether an entry of `unit` is foreign to the store's local unit (never, while none is set). */
int pkcal_store_is_foreign(const pk_calstore *s, const char *unit, const char *kind);
pk_status pkcal_store_put_imported(pk_calstore *s, const pk_calibration *c, char id_out[65]);   /* put without joining local.log */
int pkcal_kind_imported(const char *kind);   /* imported-psi, imported-file */

/* store.c: the resolved root of an open store (the same root the EEPROM image store uses: units/<unit>/eeprom/). */
const char *pkcal_store_root(const pk_calstore *s);

/* PSI .reg parsing (psi_import.c): builds one record per calibrated ColNeg / ColNegIr key. */
pk_status pkcal_psi_from_reg(const uint8_t *reg, size_t n, const char *unit, pk_calibration ***out, size_t *count, size_t *skipped);

#endif
