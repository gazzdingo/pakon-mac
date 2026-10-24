#ifndef PAKON_CALIB_H
#define PAKON_CALIB_H
/* Calibration types seen by the session API (Task 12, Task 15). The three session entry points (pk_calibrate, pk_track_test,
 * pk_session_set_cal_policy) are declared in session.h. Nothing here writes scanner memory (RE 43 sec 10). */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "pakon/boards.h"
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_cal_request pk_cal_request;
typedef struct pk_track_result pk_track_result;
typedef struct pk_cal_policy pk_cal_policy;
typedef struct pk_cal_light pk_cal_light;

/* The light settings of one calibration (Task 13 declares them, Task 15 fills them): what TLB reads from the registry key
 * Scan\DpiBase<n>_35\ColNeg after a calibration (RE 41 sec 1). Only the scan sequence's inputs are here; Task 15 may add fields.
 * Channel order is R, G, B, IR in every array. */
struct pk_cal_light {
    unsigned version;           /* 1 */
    int dpi_base;               /* the base these settings are for */
    bool ir;                    /* the settings of an IR scan (TLB ColNegIr): lamp 0x80 = 3, the IR integration, FPGA control bit 0x100 */
    unsigned afe_gain[3];       /* Gain_R/G/B: AD9826 gain codes, at most 0x3F */
    int afe_offset[3];          /* Offset_R/G/B: AD9826 offsets, -254..255 */
    unsigned current[4];        /* Current_R/G/B/Ir: LED drive steps for light register 0x81 (clamped by pk_light_set_levels) */
    double duty_film[4];        /* DutyCycle_R/G/B/Ir: the with-film duty as a fraction of the PWM period (0..1) */
    double duty_open[4];        /* DutyCycleOpenGate_R/G/B/Ir: the empty-gate duty */
    unsigned integration;       /* FPGA index 6 (cfg+0x28): at most 0xFFD; non-IR 0x753 / 0xAFD / 0xFFD, IR 0x4E2 / 0x850 / 0x9C2 at base 4 / 8 / 16 (RE 42 sec 1.1) */
    unsigned px_offset;         /* the CCD window start of this unit (registry Offset, 55 on the owner's); 0 = the model's default */
    bool low_light;             /* LIGHT_DIM: TLB sets it after the duty search when any gain code is >= 0x33 (RE 41 sec 6) */
};

/* TLB's calibration SEEDS (Gain 13, Offset 0, Current 1, every duty 0.0, the per-base integration: RE 41 sec 1, RE 42 sec 1.1), for Task 15's
 * search to start from. NOT light settings to scan with: every duty is 0, so the lamp would be dark. PK_E_UNSUPPORTED for a base other than
 * 4, 8, 16; PK_E_ARG for a NULL out. */
pk_status pk_cal_light_seed(pk_cal_light *out, int dpi_base, bool ir);

/* ---------------------------------------------------------------- the calibration EEPROM image (Task 15, RE 30 sec 13.4) */
typedef struct {
    uint8_t raw[0x2000]; size_t len;        /* the whole chip 0x0000..0x1FFF (len = 0x2000) */
    bool copy_ok[4];                        /* per-copy {length, CRC32} validity: CalWiz A (0x000), CalWiz B (0x400), Adjust A (0x800), Adjust B (0xA00) */
    char sha256[65];
    unsigned scanner_type;                  /* CalWiz +0x0C: 0x546 (F-135) or 0x547 (F-135 Plus) */
    unsigned hw_version;                    /* CalWiz +0x08 */
    unsigned serial;                        /* CalWiz +0x10, the number TLB compares for "serial change" (RE 30 sec 13.6) */
    unsigned px_offset[3];                  /* CalWiz +0x14 / +0x1A / +0x20: the CCD window start for base 4 / 8 / 16 (27, 54, 55 on the owner's unit) */
    float poly_neg[3][10];                  /* CalWiz +0x26, 30 f32, three rows of ten */
    bool from_cache;                        /* adopted from the saved image: no transfer was made */
} pk_eeprom;
/* READ ONLY; there is no write function in any build. The chip is read ONCE PER SCANNER (owner decision 2026-10-14): when the store holds a current image for the unit it is
 * returned with from_cache = true and NO transfer is made, and no scan, calibration, session open or retry path re-reads it. `unit` is "<model name, spaces as underscores>-<serial>"
 * (S-R23), or NULL to adopt the saved unit when EXACTLY ONE unit exists under store_root (S-R40 I-2); with more than one saved unit an explicit unit is required (PK_E_BUSY); store_root is the calibration store root (units/<unit>/eeprom/). A live read is
 * made only when no eeprom.log exists anywhere under the root (the very first read of any scanner), or when reread is true and a current image exists (HW-2's one confirming re-read:
 * the new image becomes current only if byte-identical). Otherwise PK_E_BUSY (refused: nothing sent). The live read is TLB's exact shape (FUN_100160a0): per chunk of at most 0x20
 * bytes, 40/A4 wValue 0xA5 wIndex 0x1234, then C0/A9 wValue = offset wIndex 0x1234. A live image whose scanner type is not 0x546 / 0x547 or whose poly_neg is not finite is
 * PK_E_CORRUPT and is NOT stored (the chip is only ever read, so that read can be repeated). PK_E_CORRUPT also when the saved image fails these checks. The store is listed FAIL CLOSED (S-R40 I-1): any error listing units/ or checking an eeprom.log (permission, I/O, an odd file type, a path too long) is PK_E_IO with no transfer; only a clean empty store may read the chip. */
pk_status pk_eeprom_read(pk_boards*, const char *unit, const char *store_root, bool reread, pk_eeprom *out);
/* The automatic first read for a brand-new scanner (owner ruling 2026-10-23): pk_eeprom_read with no unit and reread = false, from a bare (guarded) transport and the USB-level model,
 * without opening boards. Reads only (chip select 40/A4 wValue 0xA5, then C0/A9 reads, TLB's shape); never writes the chip. Every refusal of pk_eeprom_read holds (a store that already has an
 * eeprom.log is never read again: the saved image is returned with from_cache = true or PK_E_BUSY). */
pk_status pk_eeprom_first_read(pk_transport *t, const pk_model *usb_model, const char *store_root, pk_eeprom *out);
/* The per-session identity check (owner decision 2026-10-22, closes S-R40 I-2). It NEVER makes a full chip read: the first full read of a scanner is only the explicit command
 * (hw1 eeprom-read / pakon calibrate --reread-eeprom, pk_eeprom_read). It reads two 4-byte CalWiz serials, copy A +0x10 and copy B 0x410 (TLB's shape: 40/A4 wValue 0xA5 wIndex 0x1234,
 * then C0/A9 length 4), and a match on either with a saved unit's key adopts that unit's image (from_cache = true, no other transfer; the two copies naming different saved units is
 * PK_E_CORRUPT). Results: PK_E_NOT_FOUND when no unit is saved at all ("no saved calibration chip image; run the explicit first-read command"); PK_E_CAL_FOREIGN when neither serial is a
 * saved unit, confirmed by a second pair of reads ("a different scanner, serial *seen_serial: run the explicit first-read command for it"); any read or store failure is returned and
 * adopts nothing. *seen_serial (optional) is the serial found. Never writes the chip. */
pk_status pk_eeprom_identify(pk_boards*, const char *store_root, pk_eeprom *out, unsigned *seen_serial);

/* ---------------------------------------------------------------- calibration requests, tests, policy (Task 15) */
typedef enum { PK_CAL_SESSION, PK_CAL_GAIN, PK_CAL_FOCUS, PK_CAL_TRACK } pk_cal_kind;
enum { PK_CAL_BASE_4 = 1, PK_CAL_BASE_8 = 2, PK_CAL_BASE_16 = 4 };      /* dpi_base_mask bits */
enum { PK_CAL_COLOUR_NEG = 1 };                                          /* film_colour_mask: only colour negative is calibrated (TLB refuses positive; B&W keys are not imported) */
/* SESSION: one calibration per ticked base now (a full LED-current search only when none is stored or one is due, S-R39 a). GAIN: the Gain test (a forced full
 * light search per ticked base; no Track test, as PSI's Gain page with "Track Test" unticked, RE 48b row 8). FOCUS: F-235/F-335 only (PK_E_UNSUPPORTED on the F-135 family). TRACK: use pk_track_test (PK_E_ARG). */
struct pk_cal_request { pk_cal_kind kind; int dpi_base_mask, film_colour_mask; bool ir; };

/* The read-only Track test (RE 43 sec 8.1): nothing is written; the thresholds TLB WOULD write are computed and reported, never sent. */
struct pk_track_result {
    bool clock_top_err, clock_bottom_err, data_top_err, data_bottom_err;   /* FILM_TRACK_TEST_ERRORS_* 1 / 4 / 2 / 8 (swing too small) */
    bool film_entry_err, film_exit_err;                                    /* TLB never ORs these in (RE 43 sec 8.1); always false */
    int thresholds[4];            /* DX thresholds TLB would store, [TopClock, TopData, BottomClock, BottomData]; -1 when the test stopped before the evaluation */
    int pots[4];                  /* the stored pot counts are not readable through any register TLB uses (RE 43 sec 8.3): always -1 */
    unsigned ec_codes[8]; size_t n_ec;   /* 0xC2 EC_DXNoFilmFound, 0xC5 EC_DXBadSwing */
    int no_film_thresholds[4];    /* the "no film" thresholds TLB would store; -1 as above */
    int level_min[4], level_mode[4], level_max[4], swing[4];   /* per sensor, from the histograms; -1 as above */
    unsigned result_word;         /* TLB's S+0x394 as FilmTrackTestResults returns it: 0xFF when it stopped early, else the OR of the error flags */
    unsigned samples;             /* 0x93 samples taken into the histograms (TLB's first, discarded read not counted) */
    bool complete;                /* the evaluation ran (TLB's end: the 72nd clear sample of the film phase, RE 43 sec 8.1 T4) */
    bool partial;                 /* the test stopped before TLB's evaluation (no film, cancel, the cap, a failure): the levels, swing_flags and both
                                     threshold sets above are still filled from the samples so far (>= 10), as a report; TLB computes nothing then */
    bool film_found;              /* T3 found film (all four sensors below max_c - DxCalibrationFilmOffset) */
    unsigned film_samples;        /* film-phase samples counted toward the 4001 before the end check (stops at 4001) */
    unsigned clear_samples;       /* film-phase samples with all four sensors >= max_c - 1 (the test ends at 72) */
    unsigned swing_flags;         /* the 1/2/4/8 flags the evaluation gives from these levels; result_word only when complete */
};

struct pk_cal_policy {
    unsigned dark_point_interval_min;   /* DarkPointCorrectIntervalMinutes: TLB 60, the owner's PSI 120 (RE 43 sec 6) */
    unsigned full_search_after_h;       /* 20 (TLB: 72000 s) */
    bool auto_at_power_on;              /* the first scan after the session opens calibrates (TLB's tables are RAM only) */
};
typedef struct { int64_t last_run_s, last_full_s;   /* unix seconds, 0 = never */ bool serial_changed; } pk_cal_state;
typedef struct { bool due; bool full_search; const char *reason; } pk_cal_due;
/* The defaults {120, 20, true}: the interval is the owner's PSI value (S-R39 a; TLB's own default is 60). */
void pk_cal_policy_default(pk_cal_policy *out);
/* TLB's rule (RE 43 sec 1, 6; FUN_10021590 / FUN_10010250), all comparisons strict as TLB's:
 *   no run yet this power-on (last_run_s == 0)            -> due (if auto_at_power_on), reason "power-on"
 *   now - last_run_s  > interval_min * 60                 -> due, "dark-point interval"
 *   now - last_full_s > full_search_after_h * 3600        -> due and full ("full light search"); last_full_s == 0 is "never"
 *   serial_changed                                        -> due and full
 * A due run is a full search whenever full is also due. reason is a static string. */
pk_cal_due pk_calibration_due(const pk_cal_policy*, const pk_cal_state*, int64_t now_s);

#ifdef __cplusplus
}
#endif
#endif
