#ifndef PAKON_DEVICE_H
#define PAKON_DEVICE_H
/* Scanner models, USB discovery, Intel-HEX images and the firmware load (Task 6).
 *
 * NEVER-WRITE RULE (owner): scanner memory is never written. The load only writes the FX2's volatile RAM, and only
 * through the guard's load window (link.h): pk_device_load_firmware opens the window itself and every A0 it sends is one the
 * window allows. Discovery lists devices from their descriptors and opens nothing. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "pakon/error.h"
#include "pakon/image.h"
#include "pakon/link.h"
#include "pakon/transport.h"
#include "pakon/vendor.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { PK_DEV_BARE, PK_DEV_UNLOADED, PK_DEV_LOADED, PK_DEV_UNKNOWN } pk_dev_state;
typedef enum { PK_MODEL_F135, PK_MODEL_F135_PLUS, PK_MODEL_F235, PK_MODEL_F235C, PK_MODEL_F335, PK_MODEL_F335C,
               PK_MODEL__COUNT } pk_model_id;
typedef enum { PK_SUPPORT_VERIFIED, PK_SUPPORT_BETA } pk_support;

/* One resolution of one film format. A zero row means the model lacks that base. */
typedef struct {
    int hires_px, frame_lines, window_lines, lores_decim, lores_px, dmin_base;
    int ccd_px_offset, ccd_px_height;   /* CCD window from TLB FN_bBeforeScan (Task 7, RE 29 sec 12): ccd_px_height = pixels per line on the wire, ccd_px_offset = TLB's default start pixel (the unit's own value replaces it); 0 = not derived (beta models) */
} pk_base_geom;

enum { PK_CAP_GUIDES = 1, PK_CAP_ROLLERS = 2, PK_CAP_FOCUS = 4, PK_CAP_LONG_ROLL = 8, PK_CAP_SPLICE = 16,
       PK_CAP_APS_CARTRIDGE = 32, PK_CAP_LAMP_LEVELS = 64, PK_CAP_APS_24MM = 128, PK_CAP_LAMP_SAVER = 256 };

typedef struct {
    pk_model_id id;
    const char *name;
    pk_support support;
    pk_vendor_item firmware;
    pk_link_roles roles;
    unsigned bases_mask;            /* bit0 base 4, bit1 base 8, bit2 base 16 */
    pk_base_geom geom[3];           /* [0] base 4, [1] base 8, [2] base 16, 35 mm */
    pk_base_geom geom24[3];         /* APS 24 mm; zero on models without it */
    unsigned caps;
    unsigned scanner_type[2];       /* EEPROM scanner-type values (the second is 0 when the model has one) */
} pk_model;

typedef struct {
    pk_dev_state state;
    const pk_model *model;          /* the USB-identity model (F135 for both F-135s); NULL for bare, unknown, or an unloaded REV with no known firmware */
} pk_dev_class;

/* Classification from the USB descriptor values only. Bare: 04B4:8613, 0547:1002. Unloaded: 0F05:F235 with a REV whose
 * high byte is 0xAA (AA07 -> F135, AA05 -> F235, AA08 -> F335; any other 0xAAxx is UNLOADED with model NULL, so no
 * firmware is ever chosen for it). Loaded: 0F05:F135 (F-135), 0F05:35F2 (F-235), 0F05:F335 (F-335). Else UNKNOWN. */
pk_dev_class pk_device_classify(uint16_t vid, uint16_t pid, uint16_t rev);
const pk_model *pk_model_get(pk_model_id);   /* NULL for an id outside the table */
/* F135 -> F135_PLUS on 0x547 (and F135 on 0x546), F235 -> F235C on 8 (F235 on 7), F335 -> F335C on 0xD17 (F335 on 0xD16);
 * NULL if the scanner type does not belong to the USB-identity model's family. Never guesses. */
const pk_model *pk_model_refine(const pk_model *usb_model, unsigned eeprom_scanner_type);
pk_status pk_model_check_base(const pk_model *, int dpi_base);   /* dpi_base 4, 8 or 16; PK_E_UNSUPPORTED if the model lacks it */
/* channels (3, or 4 with IR) x the base's hi-res pixels per line (TLB PB+0x68; F-135 / Plus RGB: base 4 3000, base 8 4500, base 16 6000; with IR 4000 / 6000 / 8000);
 * 0 if the base is unsupported. */
unsigned pk_words_per_line(const pk_model *, int dpi_base, bool ir);

/* ------------------------------------------------------------------ discovery (lists only, opens nothing) */
typedef struct { pk_usb_info info; pk_dev_class cls; } pk_dev_entry;
/* Lists the attached Pakon-family devices from their descriptors (pk_usb_list) and classifies each. Writes at most cap
 * entries; *n = entries written. No device is opened and no serial is read. PK_E_UNSUPPORTED without libusb. */
pk_status pk_device_discover(pk_dev_entry *out, size_t cap, size_t *n);

/* ------------------------------------------------------------------ Intel-HEX */
/* Record types 00 (data), 01 (end of file, required), 02 and 04 (extended addresses, folded into a 64 KiB image).
 * The checksum of every record is verified. PK_E_FORMAT for anything else: a bad character, length or checksum, record
 * types 03/05, data above 0xFFFF, a byte set twice, data after the end record, no end record, or no data at all.
 * Lowercase and uppercase hex, CRLF and blank lines are accepted. *out is heap-allocated (pk_image_free). */
pk_status pk_ihex_parse(const uint8_t *text, size_t n, pk_image **out);
void pk_image_free(pk_image *);
/* The same parse, plus the data records in FILE ORDER (S-R25: Kodak sends records in file order, 16 bytes at most each; a longer
 * record is split into 16-byte pieces). *recs is heap-allocated (free()). */
typedef struct { uint16_t addr; uint8_t len; uint8_t data[16]; } pk_ihex_rec;
pk_status pk_ihex_parse_records(const uint8_t *text, size_t n, pk_image **out, pk_ihex_rec **recs, size_t *nrecs);

/* ------------------------------------------------------------------ firmware load */
/* defaults 100, 10000, 500, 0 (NULL = defaults). s1_wait_ms is the wait after the stage-1 release (0 means the default 500: it is
 * never skipped). image_2004 is a DIAGNOSTIC for a controlled second retry (hw1-load-debug.md sec 8, retry B): it loads the 2004
 * F135Driver/Pakon7.hex (pinned, 10326 bytes) instead of the 2006 FX35Driver/Pakon7.hex that models.def selects (S-R14). F-135 and
 * F-135 Plus only; PK_E_UNSUPPORTED for any other model. Off by default. */
typedef struct { unsigned reset_hold_ms, reenum_wait_ms, s1_wait_ms; int image_2004; } pk_fw_opts;

/* Loads the model's firmware into an unloaded FX2 by Kodak's own sequence (S-R25). The caller supplies NO image bytes (S-R13):
 * the loader reads usb_model->firmware AND Kodak's stage-1 loader (cut out of the store's F235Ldr.sys) from the verified vendor
 * store (pk_vendor_file re-verifies each SHA-256), parses them into memory the library owns, and checks both against compiled-in
 * canonical SHA-256 pins before any transfer (PK_E_CORRUPT otherwise; PK_E_VENDOR_MISSING if the store lacks an item;
 * PK_E_UNSUPPORTED for a model whose firmware has no pinned hash). Only those library-owned images reach the guard's load window.
 * Sequence (steps 1-11 run inside the guard's load window, opened and closed here on every exit path):
 * (1) hold the 8051, (2) send the stage-1 records by A0, (3) release, (4) wait s1_wait_ms (500), (5) send every firmware record
 * above 0x1B3F by A3 (16 bytes at most per transfer, file order, the stage-1 running), (6) read all of it back by A3 IN,
 * (7) hold, (8) send the records at or below 0x1B3F by A0, (9) read every byte below 0x4000 back by A0 IN, (10) on any mismatch
 * stay held and return PK_E_DEVICE, (11) hold and release. Then (12) reopen under the loaded identity (bounded by reenum_wait_ms) and
 * (13) read the boot EEPROM personality on the reopened device and compare bytes 1..6 (VID, PID, device ID AA05/AA07/AA08) with the
 * unloaded identity. Statuses: PK_E_FIRMWARE_MISMATCH if they disagree; PK_E_LOADED_UNVERIFIED if the load and the reopen succeeded
 * but the personality could not be read (the device is loaded; do not reload). A failure of the reopen itself means the firmware
 * is already running: rediscover the device, do not reload. A failure before the reopen leaves the 8051 held, running the
 * stage-1 or half loaded: power-cycle the scanner. `t` must be a guarded transport (every opener returns one). err may be NULL. */
pk_status pk_device_load_firmware(pk_transport *t, const pk_model *usb_model, pk_vendor *vendor, const pk_fw_opts *opts,
                                  pk_error *err);

#define PK_PERSONALITY_SELECT_WVALUE 0xA3   /* A4 wValue: config EEPROM 0x51, read; PK_EEPROM_SELECT_WVALUE (0xA5, calibration chip 0x52) lives in calib/eeprom.h; the guard's A4 allowlist is exactly these two */
/* TLB's shape (S-R6): 40/A4 wValue 0xA3 (select the 0x51 boot EEPROM for read), then C0/A9 wValue 0, 8 bytes; VID (bytes 1..2), PID
 * (3..4) and device ID (5..6, little-endian) are returned, never the EEPROM-type byte [0]. */
pk_status pk_device_personality(pk_transport *t, uint16_t *vid_out, uint16_t *pid_out, uint16_t *did_out /* may be NULL */);

#ifdef __cplusplus
}
#endif
#endif
