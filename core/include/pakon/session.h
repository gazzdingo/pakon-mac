#ifndef PAKON_SESSION_H
#define PAKON_SESSION_H
/* The scan session (Task 12): a state machine whose work runs on one worker thread, events to the caller, the only path out of
 * Warmup / Ready / Scanning (session_leave), a crash marker, and gating of the manual controls.
 *
 * Threads: pk_session_open / start / wait / close and the manual controls are called from one controlling thread. pk_session_cancel,
 * pk_session_state and pk_session_film_stop may be called from any thread. The event callback runs on the worker thread, with no session
 * lock held; it must not call back into the session except pk_session_cancel and pk_session_state.
 *
 * The worker owns the boards from pk_session_start until the state is back to IDLE (or FAULTED). In that time the manual controls return
 * PK_E_BUSY. pk_session_film_stop and the read-only calls (film_sense, guide_get) work in any state: the link serialises every exchange and the
 * boards lock the interrupt-pending mask and the DX nibble cache.
 *
 * Nothing here writes scanner memory. The transport is borrowed: the caller closes it after pk_session_close. */
#include <stdbool.h>
#include <stdint.h>
#include "pakon/boards.h"
#include "pakon/calib.h"
#include "pakon/device.h"
#include "pakon/status.h"
#include "pakon/transport.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---------------------------------------------------------------- scan configuration (Task 13) */
typedef enum { PK_STRIPS_FULL_ROLL = 0, PK_STRIPS_MULTI_4 = 4, PK_STRIPS_MULTI_5 = 5, PK_STRIPS_MULTI_6 = 6 } pk_strip_mode;
typedef enum { PK_ROLL_NORMAL, PK_ROLL_LONG, PK_ROLL_SPLICED } pk_roll_mode;
enum { PK_SC_AGGRESSIVE_FRAMING = 0x2, PK_SC_RFT_SENSE_SPLICE = 0x4, PK_SC_SCRATCH_REMOVAL = 0x8, PK_SC_USE_24MM_AUTOLOADER = 0x10,
       PK_SC_HAS_FILM_DRAG = 0x1000, PK_SC_PRESCAN = 0x10000, PK_SC_PREMIUM_COLOUR = 0x100000 };
typedef struct pk_scan_config {
    unsigned version;                 /* 1 */
    int dpi_base;                     /* 4, 8, 16 (the F-135 Plus has all three; the F-135 has 4 and 8) */
    bool ir;                          /* IR channel captured (RGB+IR words per line). TLB has no model or base gate (RE 42 sec 2), so any base the model has accepts it; it must agree with PK_SC_SCRATCH_REMOVAL, TLB's one IR switch (scan_control & 8) */
    pk_film_format film_format;       /* 35 mm default */
    pk_strip_mode strip_mode;
    pk_roll_mode roll_mode;
    unsigned max_film_length_mm;      /* 24..6400 (TLB validates exactly this); default 1670 = PSI's NormalRollMaxFilmLength_mm (RE 41 sec 3.1) */
    unsigned no_film_timeout_s;       /* 10..300 (TLB 0x10041485); default 120 = the owner's PSI value (TLB's own default is 60) */
    unsigned scan_control;            /* PK_SC_* */
    int film_speed;                   /* must be 0 (S-R35): the scan runs at PSI's speed, registry MotorAdjust x MotorSpeedPlus / 1000 per base and IR (5917 at base 16); anything else is PK_E_ARG */
    char calibration_pin[65];         /* "auto" or a calibration id (light settings only) */
    int manual_product, manual_specifier;   /* -1/-1 = none; otherwise stamps dx_source "manual" on strips with no DX read */
    unsigned feed_mode;               /* PSI Scanner Settings\FeedMode (RE 47 sec 2): what the end-of-scan eject does. 0 = 500 ms forward at speed 1000 (the owner's value, default), 1 = 1500 ms reverse, 2 = splice_advance_ms forward */
    unsigned splice_advance_ms;       /* PSI SpliceAdvance: the FeedMode 2 push, 1..300000 ms; default 750 (the owner's hive). Ignored for the other modes */
    unsigned ir_crosstalk_factor;     /* TLB's registry value IrCrossTalkFactor (RE 45 sec 4.1, S-R45 a): default 10 (the owner's value), clamped to 1..20 as TLB does (a 0 becomes 1). Only an IR scan uses it:
                                       * the decode kernel subtracts R * (65536 / factor) >> 16 from the IR plane. The roll sidecar records it; a sidecar without the field decodes with 10 */
} pk_scan_config;
#define PK_IR_CROSSTALK_DEFAULT 10u
#define PK_IR_CROSSTALK_MIN 1u
#define PK_IR_CROSSTALK_MAX 20u
pk_status pk_scan_config_default(const pk_model*, pk_scan_config *out);
/* PK_E_UNSUPPORTED (a base, roll mode, film format or option the model lacks; prescan, S-R34 b) / PK_E_BUSY (roll_mode changed from prev while film is
 * loaded) / PK_E_ARG (everything else out of range, including a multi-strip mode whose film-length limit leaves TLB's strip count at 0: RE 41 U10). */
pk_status pk_scan_config_validate(const pk_model*, const pk_scan_config*, const pk_scan_config *prev /* NULL = none */, bool film_loaded);
/* The film-length limit in hi-res lines: trunc(mm x hires_px x 1000.0 / 23700), TLB 0x1002e1fa..0x1002e247 (1670 mm at base 16 gives 140928). 0 for an unsupported base. */
unsigned  pk_scan_length_limit_lines(const pk_model*, int dpi_base, unsigned mm);
/* TLB's strip budget (0x1002e26b..0x1002e2c0): full roll = 1 strip of the whole limit; MULTI_n = (mm x 1000) / (n x u + u / 4) strips, u = frame window x 23700 / hires_px,
 * capped at 15, each with limit / strips lines. *strips = 0 is TLB's unguarded divide-by-zero: validation refuses it. PK_E_ARG on a bad argument. */
pk_status pk_scan_strip_budget(const pk_model*, const pk_scan_config*, unsigned *strips, unsigned *lines_per_strip);
pk_status pk_scan_config_to_json(const pk_scan_config*, char **json);                        /* malloc'd */
pk_status pk_scan_config_from_sidecar(const char *sidecar_path, pk_scan_config *out);        /* PSI Ctrl-Shift-S */

/* ---------------------------------------------------------------- warnings (Task 13, spec sec K) */
/* Strip warning bits (TLB strip+0x6ca8) plus the two PSI status-word warnings (RE 41 sec 6). */
enum {
    PK_SCANW_DX_BAD = 0x1, PK_SCANW_FILM_PRODUCT_AND_SPECIFIER_BAD = 0x2,
    PK_SCANW_SPEED_SLOW_HALF = 0x10, PK_SCANW_SPEED_SLOW_ONE = 0x20, PK_SCANW_SPEED_FAST_HALF = 0x40, PK_SCANW_SPEED_FAST_ONE = 0x80,   /* +-0.5 %, +-1 % (RE 33 sec 7; thresholds INFERRED there) */
    PK_SCANW_FRAMING_100 = 0x100, PK_SCANW_FRAMING_200 = 0x200, PK_SCANW_FRAMING_400 = 0x400, PK_SCANW_FRAMING_800 = 0x800,   /* set by Task 19 */
    PK_SCANW_MAX_FILM_LENGTH_EXCEEDED = 0x1000, PK_SCANW_LIGHT_DIM = 0x2000,
    PK_WARN_PSI_EMULSION_DOWN = 0x10000000u,   /* HARDWARE_CB_FILM_EMULSION_DOWN, the DX status nibble bit 0x40: PSI string 39 (F-135 family) or 36 */
    PK_WARN_PSI_TAIL_FIRST = 0x20000000u       /* HARDWARE_CB_FILM_TAIL_FIRST, the DX status nibble bit 0x80: PSI string 37 */
};
typedef struct { unsigned psi_string_id; const char *english; } pk_warning_text;
/* The sentence for one warning bit; the core holds no display text of its own beyond this default and the app may replace it (C53). psi_string_id 0 = PSI's
 * message for this bit (RE 42 sec 7.2). An unknown bit returns { 0, "" }. */
pk_warning_text pk_warning_sentence(unsigned bit);
/* The same with the model's wording: PK_WARN_PSI_EMULSION_DOWN is PSI string 39 ("emulsion side out") on the F-135 / F-135 Plus and string 36 ("emulsion side down") on the F-235 / F-335 family
 * (RE 42 sec 7.2). pk_warning_sentence(bit) is this with the F-135 family. Texts are PSI's own (RE 42 sec 7.3). 0x1000 is string 44 and PSI shows it only when the roll's strip count is not 1;
 * 0x20 / 0x80 (the 1 % speed bits) are a warning only: PSI's AdjustMotorSpeed is an EEPROM write and is never called. */
pk_warning_text pk_warning_sentence_for(const pk_model*, unsigned bit);


typedef enum { PK_S_IDLE, PK_S_WARMUP, PK_S_READY, PK_S_SCANNING, PK_S_DRAINING, PK_S_STOPPING, PK_S_FAULTED } pk_state;
typedef enum { PK_EV_STATE, PK_EV_WARMUP_PROGRESS, PK_EV_LAMP_HEALTH, PK_EV_FILM_SENSE, PK_EV_LINES, PK_EV_WARNING,
               PK_EV_DX, PK_EV_CAL_PROGRESS, PK_EV_FW_VERSION_WARNING, PK_EV_ERROR,
               PK_EV_EJECT } pk_event_kind;
/* Fields used per kind: STATE (state), WARMUP_PROGRESS (percent), LAMP_HEALTH (code = PK_LIGHT_F_* flags, percent unused), FW_VERSION_WARNING
 * (code = (hardware version << 8) | firmware version read from the light board, text), WARNING and ERROR (status, text).
 * EJECT (no fields): PSI's end-of-scan eject push is about to start ("Advancing Film", PSI string 154; RE 48a C1). It is sent only when the push really runs (not after a
 * no-film timeout, a gone scanner or an unconfirmed motor stop / lamp-off); the run's end (the STATE event to IDLE or FAULTED) closes it. */
typedef struct { pk_event_kind kind; pk_state state; int percent; uint64_t lines; uint32_t code; pk_status status; char text[96]; } pk_event;
typedef void (*pk_events_cb)(void *user, const pk_event*);
typedef struct { const char *work_dir; /* stale-session marker session.active lives here */ const char *calstore_root; const char *vendor_root;
                 pk_model_id model;      /* the USB-identity model from pk_device_classify (refined by the EEPROM scanner type once read) */
                 bool leds_enabled;      /* default true (TlaControlLeds shipped default 1) */
                 unsigned warmup_timeout_ms;   /* default 300000 */
                 bool no_keepalive;      /* diagnostic only (HW-1 lamp idle experiment): skips the >= 1/s lamp keepalive */ } pk_session_opts;
typedef struct pk_session pk_session;
/* The defaults: leds_enabled true, warmup_timeout_ms 300000, no_keepalive false, everything else zero. A zeroed struct has the LEDs disabled. */
void pk_session_opts_default(pk_session_opts *);

/* Wraps the transport with pk_transport_guard_open (idempotent), opens the link and boards, and runs a safe-stop FIRST if a stale marker
 * <work_dir>/session.active exists (v1 safe_stop: motor stop, lamp off, DX stop; the marker is removed only if the motor stop was acknowledged or
 * the scanner is gone). A marker whose process is alive (and is not this one) is PK_E_BUSY and nothing is sent. Then sends TLB's init once:
 * light 0x87 = 00 00, the monitor thresholds (with 0xD0 = 0, 0xD1 = 1, RE 29 sec 4), 0x80 = 1, 0x82 all-zero (N = 982), lamp-off through
 * pk_light_lamp_off, 0x89 = 0; opens the LED gate (motor 0x97 = 1), drains the latched light 0x02 bits, and reads the light board's
 * version bytes. Beta models are PK_E_UNSUPPORTED. work_dir must exist or be creatable. */
pk_status pk_session_open (pk_transport*, const pk_session_opts*, pk_session **out);
/* Validates the config (pk_scan_config_validate), then resolves the light settings (RE 41 sec 1, S-R32 a): TLB never scans uncalibrated, so with "auto" and no stored or
 * usable light settings this returns PK_E_NOT_FOUND ("no calibration yet", also sent as a PK_EV_ERROR event to the callback before returning) until Task 15 calibrates.
 * Validates (PK_E_BUSY unless IDLE; PK_E_ARG for a NULL session, path, or config; in FAULTED the failure that caused it, since only closing and reopening helps), writes the marker, starts the worker and returns at once.
 * The worker warms the lamp up (events), then runs the scan sequence (Task 13), then session_leave. The outcome is reported by pk_session_wait.
 * The scan sequence (core/src/session/scan.c) follows TLB's order (docs/re/41-scan-sequence.md); the sidecar <base>.json is written at start, at each strip end, every 10 s and last with complete:true. */
pk_status pk_session_start(pk_session*, const char *roll_base_path /* writes <base>.raw and <base>.json */, const pk_scan_config*, pk_events_cb, void *user);
/* Thread-safe, idempotent, never blocks on hardware: sets a flag the worker polls (within 50 ms in warm-up). PK_OK when nothing is running.
 * The end-of-scan eject (PSI AdvanceFilm, 300 ms after the run ends, RE 47 / S-R49) is not cancellable by this call, as in PSI; pk_session_film_stop and pk_session_close stop it at once. */
pk_status pk_session_cancel(pk_session*);
/* Blocks until the worker has finished; *final = how the run ended (PK_OK, PK_E_CANCELLED, or the failure). PK_OK and *final = PK_OK if no run was started. */
pk_status pk_session_wait (pk_session*, pk_status *final);
pk_state  pk_session_state(const pk_session*);
void      pk_session_close(pk_session*);      /* lamp off, LEDs off, marker cleared */
pk_boards *pk_session_boards(pk_session*);
/* manual controls: PK_E_BUSY unless state is IDLE or READY; Stop (pk_session_film_stop) works in any state */
pk_status pk_session_film_move (pk_session*, pk_film_dir, unsigned max_ms, int speed);
pk_status pk_session_film_stop (pk_session*);
pk_status pk_session_film_eject(pk_session*);   /* one PSI push: AdvanceFilm(500 ms, 1000) */
pk_status pk_session_leds_reset(pk_session*);
pk_status pk_session_lamp_set  (pk_session*, pk_lamp_level);
pk_status pk_session_guide_set (pk_session*, pk_film_format);
pk_status pk_session_film_sense(pk_session*, pk_film_sensors *out);                /* read-only: any state */
/* True while the film LED is held at "remove film" (blinking yellow, 0x4C) after a scan or a FilmInGuides refusal: film was over a sensor. The idle status thread (every 200 ms, RE 47) releases the hold when a
 * 0x90 record shows both sensors clear; it stays true until then. If the light board sends no sensor record while no scan runs (UNKNOWN, RE 47 U2), the thread never releases it: no timer is used. The hold also ends
 * (this returns false) when the session leaves IDLE (FAULTED, a new run), when the scanner is gone, at the next scan start, and at pk_session_close. A failed LED write never sets it. Read-only, any state. */
bool pk_session_remove_film_pending(pk_session*);
/* False once the idle status thread has stopped for good (the scanner is gone or a write was refused): nothing watches the sensors then. */
bool pk_session_idle_alive(pk_session*);
pk_status pk_session_guide_get (pk_session*, pk_film_format *out);                 /* read-only: any state */
pk_status pk_session_rollers   (pk_session*, bool engage);                         /* IDLE or READY gate */
pk_status pk_session_lamp_saver(pk_session*, unsigned standby_after_s, unsigned off_after_s);   /* IDLE or READY gate */
/* calibration entry points on a session (C32; Task 15, docs/re/43-calibration-sequence.md). They claim the boards like the manual controls (PK_E_BUSY unless IDLE or READY), run on the calling
 * thread, and send nothing that writes scanner memory. pk_calibrate: req->kind SESSION (a calibration per ticked base now: a full LED-current search only when none is stored or the 20 h rule says so)
 * or GAIN (a forced full search per base, no Track test); FOCUS is PK_E_UNSUPPORTED on the F-135 family; TRACK is PK_E_ARG (use pk_track_test). Each result is stored through the calibration
 * store (kind session or gain, parent = the previous selection) and out_id is the last one's id; PK_E_CAL_LIGHT when a channel cannot be lit (EC_InsufficientLight; in a Gain test the other bases still run and
 * the failure is returned at the end). pk_session_cancel stops it. Progress arrives as PK_EV_CAL_PROGRESS. pk_track_test is TLB's FilmTrackTest with every write removed: it reports the thresholds TLB WOULD
 * store and never sends them. A scan with calibration_pin "auto" calibrates first (inside pk_session_start's worker) when nothing is stored, at the session's first scan, and when the policy says it is due. */
pk_status pk_calibrate(pk_session*, const pk_cal_request*, pk_events_cb, void *user, char out_id[65]);
pk_status pk_track_test(pk_session*, pk_film_format, pk_track_result*);
pk_status pk_session_set_cal_policy(pk_session*, const pk_cal_policy*);

#ifdef __cplusplus
}
#endif
#endif
