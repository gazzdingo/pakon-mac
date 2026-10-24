#ifndef PAKON_DEVICE_EEPROM_STORE_H
#define PAKON_DEVICE_EEPROM_STORE_H
/* The calibration-EEPROM image store (internal). The 8 KB image of chip 0x52 is irreplaceable, so every image ever read is
 * kept, named by its SHA-256, and a re-read never replaces a good one.
 *
 *   <store_root>/units/<unit>/eeprom/<sha256>.bin   the whole chip 0x0000..0x1FFF (8192 bytes), valid or not
 *   <store_root>/units/<unit>/eeprom/eeprom.log     append-only; one text line per put; the LAST well-formed line that
 *                                                   says "current" names the current image (no mutable pointer file)
 *
 * Line format:  "pkeeprom1 <sha256 hex> <ok mask: 4 chars of 0/1 = CalWiz A, CalWiz B, Adjust A, Adjust B> <current|stored> <unix seconds>\n".
 * A torn or malformed line is skipped. `unit` is <model>-<serial> (plan C9). Nothing else writes the store (Task 15 and the
 * app use these functions). */
#include <stdint.h>
#include "pakon/status.h"
#include "calib/eeprom.h"

enum {
    PK_EEPROM_PUT_NEW = 1,         /* the image file did not exist before (otherwise an identical image was already stored) */
    PK_EEPROM_PUT_CURRENT = 2,     /* this image is now the current one */
    PK_EEPROM_PUT_DIFFERS = 4,     /* a current image exists and this image differs from it (never becomes current) */
    PK_EEPROM_PUT_NO_CURRENT = 8,  /* require_equal_to_current was set but there is no current image to compare with */
    PK_EEPROM_PUT_NO_CALWIZ = 16   /* neither CalWiz copy validates: stored, never current */
};

/* Stores the image (always, valid or not), appends a log line, and marks it current only when at least one CalWiz copy
 * validates (copy_ok[0] or copy_ok[1]) and the image is byte-identical to the current one if there is one: whenever a
 * current image exists EVERY put is a re-read, whatever require_equal_to_current says. The flag only makes "no current yet"
 * a reported condition (PK_EEPROM_PUT_NO_CURRENT, not current) for callers that expect a first read to exist. A differing re-read is stored and reported (flags_out) but never becomes current.
 * copy_ok is what pkcal_eeprom_validate returned for this image; it is re-derived here and a mismatch is PK_E_ARG.
 * `unit` must be 1..64 characters of [A-Za-z0-9._-] not starting with '.'. PK_E_IO on a write failure, PK_E_CORRUPT if the
 * store holds a file that is not what its name says. flags_out may be NULL. */
pk_status pk_eeprom_store_put(const char *unit, const char *store_root, const uint8_t image[PKCAL_EEPROM_SIZE],
                              const int copy_ok[PKCAL_NCOPIES], int require_equal_to_current, unsigned *flags_out);

/* The current image. PK_E_NOT_FOUND if the unit has none; PK_E_CORRUPT if the named image is missing or fails its hash. */
pk_status pk_eeprom_store_current(const char *unit, const char *store_root, uint8_t image_out[PKCAL_EEPROM_SIZE]);

#endif
