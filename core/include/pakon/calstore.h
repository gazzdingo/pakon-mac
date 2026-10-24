#ifndef PAKON_CALSTORE_H
#define PAKON_CALSTORE_H
/* The calibration store (spec section F, plan Task 14): an immutable, hide-only history of calibrations per scanner unit, and the .pakoncal
 * file that moves one between stores. There is no delete function. Layout under <root>/units/<unit>/ (the same root and unit key as the
 * EEPROM image store, S-R23): unit.json, eeprom/ (not this module's), calibration/<UTC>_<id8>/ with calibration.json, light.json, the table
 * blobs and MANIFEST.sha256 (id = sha256 of the MANIFEST), and the append-only selection.log and hidden.log. <UTC> is YYYYMMDDTHHMMSSZ. */

#include <stdbool.h>
#include <stddef.h>
#include "pakon/calib.h"
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_calstore pk_calstore;
typedef struct pk_calibration pk_calibration;     /* opaque: built only through the internal pkcal_ builder (src/calib/record.h) */
typedef enum { PK_SCOPE_ALL, PK_SCOPE_BASE4, PK_SCOPE_BASE8, PK_SCOPE_BASE16 } pk_cal_scope;   /* per dpi base; film colour / IR carried in the entry */
typedef struct { char id[65]; char utc[24]; char kind[16]; /* session|gain|focus|track|imported-psi|imported-file */
                 int dpi_base; bool ir, hidden, foreign; char parent[65]; } pk_cal_entry;
typedef struct { size_t n_files; bool foreign; char id[65]; } pk_cal_import_report;

/* root NULL or "": $PAKON_HOME, else ~/Library/Application Support/PakonMac. The root need not exist yet. Leftover <dir>.tmp.<pid> directories from a
 * crashed put are counted (and never touched). */
pk_status pk_calstore_open  (const char *root, pk_calstore **out);
void      pk_calstore_close (pk_calstore*);
size_t    pk_calstore_stale_count(const pk_calstore*);
const char *pk_calstore_stale_path(const pk_calstore*, size_t i);        /* NULL past the end */

/* The entries of one unit, newest first; caller frees *out with free(). */
pk_status pk_calstore_list  (pk_calstore*, const char *unit, pk_cal_entry **out, size_t *n, bool include_hidden);
/* Verifies the entry against its MANIFEST (PK_E_CORRUPT on any mismatch). Hidden entries stay readable. */
pk_status pk_calstore_get   (pk_calstore*, const char *id, pk_calibration **out);
pk_status pk_calstore_put   (pk_calstore*, const pk_calibration*, char id_out[65]);       /* new directory only; the same content twice is one entry */
/* id_or_auto "auto" clears the pin. A pin must belong to `unit`, match the scope and ir, and not be foreign (PK_E_CAL_FOREIGN). The _ir variants
 * address the IR light settings (TLB ColNegIr), which are a separate pin and a separate auto-pick; the plain ones are the non-IR settings. */
pk_status pk_calstore_select(pk_calstore*, const char *unit, pk_cal_scope, const char *id_or_auto);
pk_status pk_calstore_set_local_unit(pk_calstore*, const char *unit);                    /* NULL clears; with none set no entry is foreign */
pk_status pk_calstore_resolve(pk_calstore*, const char *unit, pk_cal_scope, char id_out[65]);  /* explicit selection, else newest non-hidden non-foreign */
pk_status pk_calstore_selection(pk_calstore*, const char *unit, pk_cal_scope, char id_out[65]);  /* last selection.log line, "auto" if none */
pk_status pk_calstore_select_ir(pk_calstore*, const char *unit, pk_cal_scope, bool ir, const char *id_or_auto);
pk_status pk_calstore_resolve_ir(pk_calstore*, const char *unit, pk_cal_scope, bool ir, char id_out[65]);
pk_status pk_calstore_selection_ir(pk_calstore*, const char *unit, pk_cal_scope, bool ir, char id_out[65]);
pk_status pk_calstore_hide  (pk_calstore*, const char *id, bool hidden);
pk_status pk_calstore_export(pk_calstore*, const char *id, const char *pakoncal_path);
/* Copies the bytes unchanged into units/<the entry's unit>/. PK_E_CORRUPT for anything the format does not allow; report may be NULL. */
pk_status pk_calstore_import(pk_calstore*, const char *path, pk_cal_import_report*);

/* A PSI .reg export (HKLM\SOFTWARE\Pakon\TLB\Scan\DpiBase{4,8,16}_35\{ColNeg,ColNegIr}, UTF-16LE or ANSI) becomes one imported-psi entry per calibrated
 * key under `unit` (the export does not carry the serial). Keys still at TLB's seed (every duty 0), BnW* keys, and keys missing a required value are
 * skipped (*skipped, may be NULL, counts the ColNeg/ColNegIr keys left out). BnW, BnWIr and BnW_C41* data is not imported. Each entry's utc is the key's
 * FullLightCorrections (Unix time), so it ranks as old as it is. *reports is malloc'd (NULL when nothing was imported). All keys are validated before any is stored. */
pk_status pk_calstore_import_psi(pk_calstore*, const char *unit, const char *reg_path, pk_cal_import_report **reports, size_t *n, size_t *skipped);

void pk_calibration_free(pk_calibration*);
const pk_cal_light *pk_calibration_light(const pk_calibration*);
const char *pk_calibration_unit(const pk_calibration*);
const char *pk_calibration_kind(const pk_calibration*);
const char *pk_calibration_id(const pk_calibration*);                    /* "" until stored or read back */
const void *pk_calibration_blob(const pk_calibration*, const char *name, size_t *n);   /* NULL if absent, e.g. "dark.u16" */

#ifdef __cplusplus
}
#endif
#endif
