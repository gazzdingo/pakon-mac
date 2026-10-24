#ifndef PAKON_BOARDS_H
#define PAKON_BOARDS_H
/* Typed board commands (Task 7): light board, motor basics, host / AFE / CCD. Thin wrappers over pk_link_*; every packet
 * goes through the link and the write guard, so a forbidden register is refused (PK_E_WRITE_FORBIDDEN) whatever is
 * passed here. Nothing in this header writes scanner memory. The allowed packets are the rows of core/tables/commands.def
 * (rendered in docs/protocol.md); each byte layout is ported from the v1 function named beside it.
 *
 * One pk_boards may be used by one thread. Board addresses come from the model (pk_model.roles), never from the caller. */
#include <stdbool.h>
#include <stdint.h>
#include "pakon/device.h"
#include "pakon/link.h"
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_boards pk_boards;

/* Borrows link and model (the caller keeps both alive). PK_E_ARG for NULL, or for a model with no light, motor and host
 * role (the beta models: their boards are refused wholesale until Task 21). */
pk_status pk_boards_open(pk_link *, const pk_model *, pk_boards **out);
/* Turns the lamp off (pk_light_lamp_off) if a lamp-on succeeded and no lamp-off has since put the enables off, and stops a running move. The caller must have joined any thread inside pk_film_move / pk_film_eject first. */
void pk_boards_close(pk_boards *);
/* Leave mode (S-R29): on, the lamp-off and motor-stop loops make one attempt per step and the link caps every transfer at 500 ms within budget_ms
 * in all (pk_link_set_leave_mode). The session sets it around session_leave and open-failure cleanup; off restores the normal limits. */
void pk_boards_set_leave_mode(pk_boards *, bool on, unsigned budget_ms);
pk_link *pk_boards_link(pk_boards *);
const pk_model *pk_boards_model(const pk_boards *);

/* ---------------------------------------------------------------- light board (channel order is R, G, B, IR in every array here) */
/* v1 lamp_init_thresholds: registers 0x8F, 0x8C, 0x8B, 0x8D (monitor thresholds), then 0xD0 = 0 and 0xD1 = 1. Never sends 0x8E. */
pk_status pk_light_lamp_init_thresholds(pk_boards *);
/* Register 0x80 = (visible ? 1 : 0) | (ir ? 2 : 0): an enable, not a brightness. Nothing is cached across a lamp-off: every lamp-on must be followed
 * by pk_light_set_levels (0x81) and pk_light_set_duty (0x82) again (TLB's order 0x80, 0x81, 0x82; S-R26). The driver never skips them. */
pk_status pk_light_lamp_on(pk_boards *, bool visible, bool ir);
/* Register 0x81, payload [B, Ir, R, 0, G]. levels = R, G, B, IR drive steps, each at most the hardware clamp TLB applies
 * (v1 LED_LEVEL_MAX for the board; PK_E_ARG above it, nothing sent). The IR clamp set applies when levels[3] > 0. */
pk_status pk_light_set_levels(pk_boards *, const uint16_t levels[4]);
/* Register 0x82, six u16 LE [on_B, on_Ir, on_R, 0, on_G, period]. on_counts = R, G, B, IR PWM on-counts, each at most
 * period - 2 (the driver's ceiling); PK_E_ARG above it or for period < 2, nothing sent. */
pk_status pk_light_set_duty(pk_boards *, const uint16_t on_counts[4], uint16_t period);
/* Remembers the with-film duty for pk_light_scan_duty (same limits as pk_light_set_duty); sends nothing. */
pk_status pk_light_set_scan_duty(pk_boards *, const uint16_t on_counts[4], uint16_t period);
/* Writes the duty remembered by pk_light_set_scan_duty (v1 lamp_switch_to_scan_duty: only register 0x82 changes).
 * PK_E_BUSY if none was set. */
pk_status pk_light_scan_duty(pk_boards *);
/* THE lamp-off (ruling S-R26): every lamp-off in the driver goes through it (pk_boards_close, warm-up cancel or fault, film and scan
 * cleanup, the CLI steps, Ctrl-C cleanup). TLB's FN_bEndScan sequence, exactly:
 *   1. LIGHT 0x80 = 0                       02 04 40 01 80 00
 *   2. FN_bDrvResetFifos: HOST 0x84 = 2     02 04 10 01 84 02
 *      then LIGHT type-4 command 0x8A       04 03 40 00 8A    (the light board reloads its PWM chip; a bare 0x80 = 0 did not put
 *                                                              the lamp out on the F-135 Plus, HW-1 2026-10-19)
 *   3. read LIGHT 0x83 and check data bit 4 set (all LED levels zero) and bit 1 clear (not stable).
 * Steps 1 and 2 are each tried up to 4 times like v1 lamp_off. Returns PK_OK only when step 3 confirms. A failed step returns its status
 * (step 1 failing leaves the lamp-on flag set, so pk_boards_close tries again); step 3 not confirming returns PK_E_DEVICE after four reads, with the
 * packets already sent: callers must report "not confirmed" and ask the user to look at the lamp. TLB's calibration-end and destructor paths,
 * which send no reload, are deliberately not copied. Sends no scanner-memory write; safe in any state. */
pk_status pk_light_lamp_off(pk_boards *);
/* Same, and returns the last 0x83 byte read in *status83 (0 if none was read). status83 may be NULL. */
pk_status pk_light_lamp_off_ex(pk_boards *, uint8_t *status83);
enum {
    PK_LIGHT_F_FAULT = 1,            /* status bit 5 or 6 set (v1 LAMP_STATUS_FAULT_MASK 0x60) */
    PK_LIGHT_F_TEMP_VALID = 2,       /* status bit 3: the board says its temperature readings are valid */
    PK_LIGHT_F_TEMP_UNREAD = 4,      /* register 0x84 or 0x88 could not be read; the temperature fields are -1 */
    PK_LIGHT_F_LAMP_WARN = 8,        /* measured lamp temperature beyond the setpoint +-24 (1.5 degC): the 0x8F warning band */
    PK_LIGHT_F_LAMP_FAULT = 16,      /* ... beyond the setpoint +-32 (2 degC): the 0x8C fault band */
    PK_LIGHT_F_MAIN_WARN = 32,       /* main board outside 240..800 (15..50 degC): the 0x8B band */
    PK_LIGHT_F_MAIN_FAULT = 64,      /* main board outside 160..880 (10..55 degC): the 0x8D band */
    PK_LIGHT_F_STATUS0 = 128         /* TLB flag 0x4000: 0x83 bit 0 with the light firmware version byte above 3 (set by the warm-up / reset, not by pk_light_health_poll); the version byte is the light board's devinfo[2] */
};
typedef struct {
    uint32_t status;        /* register 0x83 */
    int lamp_temp_raw;      /* register 0x88 low word: measured lamp-board temperature, 1/16 degC; -1 if unread */
    bool ok;                /* neither PK_LIGHT_F_FAULT nor a *_FAULT flag */
    uint32_t flags;         /* PK_LIGHT_F_* */
    int setpoint_raw;       /* register 0x84: the lamp temperature setpoint readback (default 0x280 = 40.0 degC); -1 if unread */
    int main_temp_raw;      /* register 0x88 high word: measured main-board temperature; -1 if unread */
} pk_light_health;
/* One poll, TLB's reads (FN_bDrvGetHardwareStatusLamp FUN_1000B890): 0x83, then 0x84 (setpoint), then 0x88 (measured lamp and
 * main-board temperatures). The lamp temperature is judged against the setpoint with the bands the thresholds in
 * pk_light_lamp_init_thresholds set (0x8F warning +-24, 0x8C fault +-32), the main board absolutely (0x8B, 0x8D); these are also TLB's
 * own margins (cfg defaults, FUN_10010B60), and each side sets WARN or FAULT, never both (TLB's if / else if). This call judges on every
 * poll (telemetry); TLB judges only on the board-raised path, so the warm-up and pk_leds_reset use the gated judgement (lamp.c). An error on 0x83 is returned (the primary
 * lamp-failure detector); a failed 0x84 / 0x88 only sets PK_LIGHT_F_TEMP_UNREAD, except a guard refusal or a wedged
 * firmware, which are returned. *out is cleared first. */
pk_status pk_light_health_poll(pk_boards *, pk_light_health *out);

/* ---------------------------------------------------------------- motor board */
/* Command 0xA2 on the motor board, tried up to 4 times; allowed in every state. */
pk_status pk_motor_stop(pk_boards *);
/* There is no jog: PSI has none. Advance / Reverse film is AdvanceFilm(300000, +-1000) = maximum speed until Stop (Task 8,
 * pk_film_move); Stop is pk_motor_stop. */

/* ---------------------------------------------------------------- host / AFE / CCD */
/* The CCD, FPGA and AFE (AD9826) settings of one scan: one field per register v1 pakon_scan.py ccd_configure writes. */
typedef struct {
    uint16_t px_offset;       /* FPGA index 4: first pixel of the window (6 during calibration; TLB's per-base value for a scan) */
    uint16_t px_height;       /* FPGA index 5 = px_offset + px_height: pixels per line on the wire */
    uint16_t integration;     /* FPGA index 6, at most 0xFFD (4093) */
    uint8_t afe_gain[3];      /* AD9826 indices 2..4 (R, G, B), at most 0x3F */
    int16_t afe_offset[3];    /* AD9826 indices 5..7 (R, G, B); 9-bit sign-magnitude on the wire; -255 and below refused, 255 and above clamped */
    uint16_t fpga_ctrl;       /* FPGA index 0 control word (10 bits); the acquire bit (0x001) is masked out and set only by pk_host_acquire */
    bool binned;              /* TLB's binning flag (base 4): sets FPGA control bit 0x002 (FUN_1002C340 -> FUN_10029770(2, binned)) and the window limits become 3..0x424 instead of 6..0x848 */
    uint8_t light_89;         /* light-board register 0x89, TLB's per-base flag (1 at base 8, else 0); when non-zero px_height must be a multiple of 4 */
    /* The exposure triad of the light settings (v1 ScanConfig.lamp_n and on_counts): carried with the CCD settings,
     * written by the light calls, not by pk_host_ccd_configure. */
    uint16_t lamp_period;
    uint16_t on_counts[3];    /* R, G, B */
} pk_ccd_cfg;
/* Validates everything first (PK_E_ARG, nothing sent), then writes v1's sequence (v1's order, which repeats the FPGA 1..3 / 0x0A and AD9826 0/1 writes TLB makes once at init; not PSI's): FPGA 4, 5, 6, 0x0B = 0, 1..3 = 0, 0x0A =
 * 0x400; AD9826 0 = 0x78, 1 = 0x80, gains, offsets; light 0x89 when it differs from the last value written (TLB's rule); FPGA control = (fpga_ctrl & 0x3FF & ~1) with bit 0x002 = binned. Acquire stays off. */
pk_status pk_host_ccd_configure(pk_boards *, const pk_ccd_cfg *);
/* TLB's per-scan update of the window and the AFE (FUN_1002C340, FUN_100299C0, FUN_100298B0; RE 41 rows 9-11): the same validation as
 * pk_host_ccd_configure, then only the values that differ from what this pk_boards last wrote are sent, in TLB's order: FPGA control (a changed IR or binning bit), index 6,
 * index 4, index 5, light 0x89, the AFE offsets (0x84 index 5..7), then the gains (index 2..4). Before any configure or after a failed write the shadows are unknown and
 * this is pk_host_ccd_configure (v1's full sequence). The acquire bit is left as it is. */
pk_status pk_host_ccd_update(pk_boards *, const pk_ccd_cfg *);
/* FPGA control bit 0 on or off, on the shadow pk_host_ccd_configure left. PK_E_BUSY before any configure (the control word
 * cannot be read back). */
pk_status pk_host_acquire(pk_boards *, bool on);
/* bDrvResetFifos: host 0x84 = 2, then light command 0x8A. Both are attempted; the first failure is returned. */
pk_status pk_host_fifo_reset(pk_boards *);
/* Light-board register 0x02 (TLB FN_bDrvGetPpbInterruptStatus): what needs servicing. DX bits 0xA4, lamp bits 0x5B. As TLB does (FUN_1000BDD0), a read
 * whose response status byte has bit 7 is acknowledged with 0x06 = [00, v] (0xFF if v is 0) and v is a one-shot event; with bit 7 clear it is not an
 * event (0). The acknowledged bits are kept for the consumers (lamp, DX); this call is a peek: it returns every pending bit and clears none, so a
 * caller cannot steal a lamp or DX event. */
pk_status pk_host_interrupt_status(pk_boards *, uint32_t *out);


/* TLB's HOST status read (FUN_10008D70, RE 42 sec 9): a type-3 poll to the FX2. *status bit 7 = a board has an interrupt pending, bit 1 = the host FIFO overflowed. */
pk_status pk_host_status(pk_boards *, uint8_t *status);
/* The motor board's share of TLB's interrupt service (FUN_1000BDD0): read motor register 0x02 and, when the response status byte has bit 7, acknowledge with 0x06 = [00, v]
 * (v = the value read, 0xFF if 0). *value (may be NULL) = what was read. No motor bit is acted on (the 'D' board case is empty in TLB). */
pk_status pk_motor_irq_service(pk_boards *, uint8_t *value);

/* Opens the LED gate: motor register 0x97 = 1 (TLB FUN_1001C3E0 sets lamp object +0xC0 right after this write succeeds at session open).
 * Until it has succeeded every LED write is a no-op returning PK_OK (TLB FUN_1000C1F0 returns without writing while +0xC0 == 0).
 * Task 12's session open calls this. */
pk_status pk_boards_open_led_gate(pk_boards *);

/* ---------------------------------------------------------------- film transport (Task 9, spec A)
 * There is no jog: a film move is PSI's AdvanceFilm(300000, +-1000) = the board's maximum speed until Stop or 300 s.
 * pk_film_stop is thread-safe and may be called from another thread while pk_film_move / pk_film_eject waits: it sends the
 * stop packet itself (serialised with the mover's own packets) and the mover returns PK_E_CANCELLED. Every other call on one
 * pk_boards is for one thread at a time (the session serialises them): a Stop from the UI thread that lands during another call's
 * packets on the session thread races the (non-thread-safe) link, so the app must call pk_film_stop from the session thread's
 * command queue or only while it is blocked in pk_film_move / pk_film_eject. */
typedef enum { PK_FILM_FORWARD, PK_FILM_REVERSE } pk_film_dir;
/* The film sensors (the DX status nibble, TLB FN_bDrvGetHardwareStatusDx FUN_10009790): a set bit means film present there.
 */
typedef struct { bool entry, exit, emulsion_down, tail_first; } pk_film_sensors;
/* Register 0xA5 = speed, then command 0xA0 (forward) / 0xA1 (reverse) on the motor board. speed 0 = the maximum (0x7FFE Plus, 0x251C
 * base); a caller speed v > 0 is v x 100 clamped to 1000..32766 (Plus) / 400..9500 (base); v < 0 is PK_E_ARG. max_ms 0 = 300000;
 * above 300000 is PK_E_ARG. Blocks until pk_film_stop (PK_E_CANCELLED) or max_ms (stop sent, PK_OK). PK_E_BUSY if a move is running. */
pk_status pk_film_move(pk_boards *, pk_film_dir, unsigned max_ms, int speed);
/* The same move with the motor speed REGISTER value given as is, clamped as TLB FUN_1000B6D0 does (Plus 1000..32766, base 400..9500). PSI's scan
 * speed for base 16 is MotorSpeedPlus = 5917, which a caller speed x 100 cannot express (S-R24 m5). */
pk_status pk_film_move_register(pk_boards *, pk_film_dir, unsigned max_ms, unsigned reg);
/* TLB's non-blocking motor start (FUN_1000B6D0 with wait = 0, RE 41 row 16): register 0xA5 = reg (clamped as pk_film_move_register), then command 0xA0 / 0xA1, and
 * returns at once; the film runs until pk_film_stop. No mover is running afterwards (pk_film_is_moving stays false), so the caller owns the stop. PK_E_BUSY if a move is running. */
pk_status pk_film_start_register(pk_boards *, pk_film_dir, unsigned reg);
/* Command 0xA2 (tried up to 4 times), any state, idempotent. */
pk_status pk_film_stop(pk_boards *);
/* True once a move has taken the film lock, which it holds while it sends the speed (A5) and the start (A0); so a caller that sees true knows both
 * packets are on the wire. Also true while the move runs; false again when it has ended (including when a start packet failed). */
bool pk_film_is_moving(pk_boards *);
/* Exactly PSI (owner decision 2026-10-19, S-R24): PSI's EjectFilm (PTS ScannerSettings.EjectFilm, scanner types 0x546 / 0x547) is one TLB
 * AdvanceFilm(500 ms, speed 1000): forward at speed register 1000 for half a second, then the mover's own stop. No sensor loop, no DX
 * start, no 300 s cap. Cancellable by pk_film_stop (PK_E_CANCELLED); PK_E_BUSY if a move is running. Push again for more. */
pk_status pk_film_eject(pk_boards *);
/* Latest sensor state: register 0x02, then register 0x90 when its DX bits (0xA4) are pending (the first call, with nothing known
 * yet, reads 0x90 unconditionally); otherwise the last state read. */
pk_status pk_film_sense(pk_boards *, pk_film_sensors *out);
/* Pure: the motor speed register for a model and a caller speed (see pk_film_move). */
unsigned pkb_speed_register(const pk_model *, int caller_speed);

/* ---------------------------------------------------------------- status LED, film LED (Task 9, spec B) */
typedef enum { PK_LED_STATUS = 0x00, PK_LED_FILM = 0x40 } pk_led_which;
typedef struct { uint16_t shadow; bool enabled; /* TlaControlLeds, default true */ } pk_led_state;
/* codes 0,1,2,3,4,8,0xC (TLB FUN_1000C1F0); any other is PK_E_ARG. A packet (FPGA index 9 of motor register 0x82) goes out only when
 * the 16-bit shadow word changes. With pk_leds_enable(false) every write is a no-op returning PK_OK. */
pk_status pk_led_set(pk_boards *, pk_led_which, unsigned colour_code);
pk_status pk_leds_enable(pk_boards *, bool);
/* The film LED phases and what the owner sees (RE 47 sec 5.1: the board blinks it from static mode bits in the LED word; manual legend "blinking green: insert film, blinking yellow: remove film"):
 * OFF = 0x40; FOUND = 0x42, steady green (film found, a strip is being scanned); WAITING = 0x48, blinking green ("insert film": the scan waits for film or the next strip);
 * REMOVE = 0x4C, blinking yellow. The wire codes match TLB (RE 42 sec 6); the names FOUND / WAITING replace the earlier INSERT (0x42) / SCANNING (0x48), which were swapped. */
typedef enum { PK_FILMLED_OFF, PK_FILMLED_FOUND, PK_FILMLED_WAITING, PK_FILMLED_REMOVE } pk_filmled;
pk_status pk_film_led(pk_boards *, pk_filmled);
/* PSI ResetStatusLeds: host-side. Drops the sticky warning flags (TLB flags &= 0xC40548C0 keeps only the fault bits), re-reads
 * light register 0x83, and rewrites the status LED (2 ready / 4 pending) when it was showing one of those. Sends no reset packet. */
pk_status pk_leds_reset(pk_boards *);
/* Pure: the new LED word. *ok = false (word returned unchanged) for an unknown code or LED. */
uint16_t pkb_led_word(uint16_t old, pk_led_which, unsigned code, bool *ok);

/* ---------------------------------------------------------------- lamp (Task 9, spec C) */
typedef enum { PK_LAMP_OFF, PK_LAMP_STANDBY, PK_LAMP_ON } pk_lamp_level;
typedef struct { unsigned poll_ms, timeout_ms; /* 0 = 250, 300000 */ } pk_warmup_opts;
typedef void (*pk_progress_cb)(void *user, int percent, const pk_light_health *);
/* F-135: polls (register 0x02, then pk_light_health_poll) every poll_ms until TLB's lamp-stable condition (FN_bLampTemperatureStable
 * FUN_1002CF10): register 0x02 bit 1, or (0x02 & 0x18 and 0x83 bit 1 with bit 6 clear). Aborts with PK_E_LAMP_WARMUP on a fault
 * (TLB's mask 0x040548C0: 0x83 bits 5/6, lamp temperature beyond setpoint +-32, main board outside 160..880) or after timeout_ms;
 * the caller turns the lamp off. *cancel non-zero = PK_E_CANCELLED. percent is TLB's formula (FUN_10032580, 1000 + per-mille of the 300 s timer,
 * every 3 s) as a percent, 100 at the end. TLB judges faults and the stable state only on the board-raised path (register 0x02 & 0x18), so a
 * cold lamp keeps warming; the stable state latches for the life of the pk_boards (a later warm-up returns at once, as TLB's), and on the
 * base board (TLB never polls health there: ScannerVersionHw < 200) it returns at once. */
pk_status pk_lamp_warmup(pk_boards *, const pk_warmup_opts *, pk_progress_cb, void *user, const volatile int *cancel);
/* Keep-alive. The light board's firmware idle counter reloads on every host packet; the session
 * calls this at least once a second while the lamp is on. It reads register 0x02 (acknowledging an event as TLB does), runs the gated lamp judgement on
 * that event, and reads 0x83 as a plain keep-alive packet (its value is not judged: lamp faults come only through the 0x02-gated TLB path, for
 * PSI parity; v1's ungated per-second bits 5/6 check is not used). TLB's status thread reads FX2 host status every 200 ms, 1 ms while scanning,
 * and goes to the light board only when that says so. */
pk_status pk_lamp_keepalive(pk_boards *);
/* F-235 only (PK_CAP_LAMP_LEVELS, beta); PK_E_UNSUPPORTED elsewhere, and for PK_LAMP_ON until Task 21 derives its level. */
pk_status pk_lamp_set(pk_boards *, pk_lamp_level);
/* F-235 / F-335 only; 1..600 s or 0 = never (PK_E_ARG otherwise). Stores the timers; F-335's wire format is Task 21's. */
pk_status pk_lamp_saver(pk_boards *, unsigned standby_after_s, unsigned off_after_s);
/* Pure: level clamped to 0x3A34, little-endian. */
void pkb_lamp235_level_bytes(unsigned level, uint8_t out[2]);

/* ---------------------------------------------------------------- film guides and pressure rollers (Task 9, spec D; beta) */
typedef enum { PK_FILM_35MM, PK_FILM_24MM } pk_film_format;
typedef void (*pk_guide_fault_cb)(void *user);     /* HARDWARE_CB_MOTOR_FILM_GUIDE */
void pk_boards_set_guide_fault_cb(pk_boards *, pk_guide_fault_cb, void *user);
pk_status pk_film_guide_set(pk_boards *, pk_film_format);       /* PK_E_UNSUPPORTED without PK_CAP_GUIDES */
pk_status pk_film_guide_get(pk_boards *, pk_film_format *);     /* last commanded position; PK_E_NOT_FOUND if none yet */
pk_status pk_pressure_rollers(pk_boards *, bool engage);        /* 3 = engage, 0 = release; PK_E_UNSUPPORTED without PK_CAP_ROLLERS */

#ifdef __cplusplus
}
#endif
#endif
