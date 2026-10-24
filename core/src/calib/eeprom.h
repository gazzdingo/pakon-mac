#ifndef PAKON_CALIB_EEPROM_H
#define PAKON_CALIB_EEPROM_H
/* The 8 KB calibration EEPROM image (chip 0x52) and its four copies. Task 6 owns the header rules and the scanner-type
 * fields (this file); Task 15 extends the file with the calibration-table side (the CalWiz/Adjust fields beyond the
 * identity). Evidence: docs/re/29-write-guard-audit.md sections 7.4 and 7.7. */
#include <stddef.h>
#include <stdint.h>
#include "pakon/calib.h"
#include "pakon/status.h"

#define PK_EEPROM_SELECT_WVALUE 0xA5   /* A4 wValue: calibration chip 0x52, read (the guard's allowlist is this and 0xA3) */
#define PKCAL_EEPROM_SIZE 0x2000u      /* the whole chip, 0x0000..0x1FFF */

/* Copy indices: CalWiz at 0x000 and 0x400, Adjust at 0x800 and 0xA00. */
enum { PKCAL_CALWIZ_A, PKCAL_CALWIZ_B, PKCAL_ADJUST_A, PKCAL_ADJUST_B, PKCAL_NCOPIES };

#define PKCAL_CALWIZ_STRUCT 0x18Eu   /* TLB truncates a CalWiz copy into this many bytes (header included) */
#define PKCAL_ADJUST_STRUCT 0x24u

/* Per-copy header (TLB FUN_100163c0 / FUN_10016A90): bytes 0..3 little-endian length (includes the 8-byte header), bytes
 * 4..7 little-endian CRC-32 over the length-8 bytes that follow. Valid iff 8 <= length <= bound (0x400 CalWiz, 0x200
 * Adjust) and the CRC matches. copy_ok[i] = 1 or 0 for each of the four copies. PK_E_ARG on a NULL argument. */
pk_status pkcal_eeprom_validate(const uint8_t image[PKCAL_EEPROM_SIZE], int copy_ok[PKCAL_NCOPIES]);

/* The bytes TLB hands on for a valid copy: the first min(length, struct size) bytes (header included). Returns the count,
 * or 0 if copy i is not valid or cap is too small. */
size_t pkcal_eeprom_copy(const uint8_t image[PKCAL_EEPROM_SIZE], int copy, uint8_t *out, size_t cap);

/* Identity fields of the first valid CalWiz copy (A, then B), at copy offsets 0x08 (hardware version), 0x0C (scanner
 * type), 0x10 (serial), little-endian dwords (RE 29 section 7.7). PK_E_CORRUPT if neither CalWiz copy is valid or the
 * valid copy is shorter than 0x14 bytes. Any out pointer may be NULL. */
pk_status pkcal_eeprom_identity(const uint8_t image[PKCAL_EEPROM_SIZE], const int copy_ok[PKCAL_NCOPIES],
                                uint32_t *scanner_type, uint32_t *hw_version, uint32_t *serial);


/* The fields of the first valid CalWiz copy of a saved image (identity, px_offset, poly_neg, copy_ok, sha256) exactly as pk_eeprom_read parses a live read; from_cache is
 * left false. PK_E_CORRUPT when no CalWiz copy validates, the scanner type is not 0x546 / 0x547 or poly_neg is not finite. No I/O. */
pk_status pkcal_eeprom_parse(const uint8_t image[PKCAL_EEPROM_SIZE], pk_eeprom *out);

#endif
