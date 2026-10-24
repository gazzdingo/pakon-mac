#ifndef PAKON_SESSION_INTERNAL_H
#define PAKON_SESSION_INTERNAL_H
/* Internal to the session module (pks_ prefix). */
#include <pthread.h>
#include <stdarg.h>
#include "boards/boards.h"
#include "calib/calib.h"
#include "pakon/dx.h"
#include "pakon/session.h"

#define PKS_KEEPALIVE_MS 200u          /* TLB's status thread polls every 200 ms; the light board drops the lamp ~60 s after the last packet (HW-1) */
#define PKS_LEAVE_STEP_MS 500u         /* session_leave: each step's budget */
#define PKS_IDLE_POLL_MS 200u          /* TLB's status thread when no scan runs: WaitForSingleObject(EventPollPPB, 200 ms) (RE 42 sec 9) */
#define PKS_IDLE_XFER_MS 500u          /* the idle thread's transfer cap (single attempt each) */
#define PKS_EJECT_DELAY_MS 300u        /* PSI's Sleep(300) before AdvanceFilm (RE 47 sec 1) */
#define PKS_PATH_MAX 512
#define PKS_LAMP_FAULTS (PK_LIGHT_F_FAULT | PK_LIGHT_F_LAMP_FAULT | PK_LIGHT_F_MAIN_FAULT | PK_LIGHT_F_STATUS0)   /* the sticky bits that abort a warm-up or a scan */

/* Task 15: the calibration state a session keeps (cal.c). Everything here is RAM: TLB's tables and last-calibration clock are RAM only, so the first scan of each session calibrates. */
typedef struct {
    pk_calstore *store;                /* opened by pks_cal_prepare */
    char unit[65];                     /* F-135_Plus-<serial> (CalWiz 0x10); set with the store's local unit */
    bool have_unit;
    pk_eeprom *ee;                     /* the adopted calibration-chip image (never read twice) */
    pk_cal_policy policy;
    int64_t last_run_s[3][2], last_full_s[3][2];   /* [base 4/8/16][ir]: unix seconds, 0 = never this session / not yet looked up in the store */
    bool full_looked_up[3][2];
    unsigned dx_speed;                 /* the 0x91 argument last sent */
    pk_dx *dx;                         /* the DX reader of a running calibration (TLB board state 4): serviced by cal_tick, which aborts on film (RE 33 sec 5) */
    bool pinned;                       /* the running scan's calibration_pin is an explicit id: no full LED-current search from the seeds replaces its light settings (C7 / C8 still re-search them from its values) */
} pks_calstate;

struct pk_session {
    pk_transport *t;                   /* guarded; borrowed from the caller unless own_guard */
    bool own_guard;
    pk_link *link;
    pk_boards *b;
    const pk_model *model;
    pk_session_opts opts;              /* the string fields point into the buffers below */
    char work_dir[PKS_PATH_MAX], calstore_root[PKS_PATH_MAX], vendor_root[PKS_PATH_MAX], marker_path[PKS_PATH_MAX + 16];
    int fw_class, fw_fw, fw_hw;        /* light board devinfo[0], [1], [2] (RE 29 sec 9); -1 if unread */

    pthread_mutex_t mu;                /* guards hw_busy, running, joinable, final; state and cancel are atomic */
    pthread_cond_t cv;
    int state;                         /* pk_state, atomic */
    int cancel;                        /* atomic; read by pk_lamp_warmup through a volatile pointer */
    bool hw_busy;                      /* the worker, or one manual control, is using the boards */
    bool running, joinable;
    pthread_t th;
    pk_status final;
    bool marker_present;

    pk_events_cb cb;
    void *cb_user;
    char roll_base[PKS_PATH_MAX];
    const pk_scan_config *cfg;         /* borrowed until pk_session_wait returns */
    unsigned long long last_keepalive_ms;
    /* Task 13 */
    pk_cal_light light;                /* the light settings this run scans with (resolved by pk_session_start) */
    char cal_id[65];                   /* the selected calibration's id ("" for settings passed in directly) */
    bool end_motor_done, end_lamp_done;   /* the scan sequence's own end (TLB EndScan) stopped the motor / confirmed the lamp off: session_leave need not repeat it */
    char diag[160];                    /* the scan sequence's own failure text, for the PK_EV_ERROR event */
    pk_scan_config prev_cfg;           /* the last config a run was started with (the roll-mode BUSY rule) */
    bool have_prev;
    bool keep_status_led;              /* ... and the status LED at 4 after a FilmInGuides refusal */
    bool keep_film_led;                /* the "remove film" hold (RE 47 sec 5): the film LED stays at 0x4C, blinking yellow, while film is over either sensor. Set by the scan's end (or a FilmInGuides refusal), kept through
                                        * leave, released by the idle status thread when a 0x90 record newer than the hold shows both sensors clear, or by close. Atomic */
    unsigned hold_seq;                 /* boards->dx_rec_seq when the hold was set: only a newer record may release it */
    /* RE 47 / S-R48: the idle status thread (idle.c). It polls every PKS_IDLE_POLL_MS whenever the session is open and nothing else owns the boards. */
    pthread_t idle_th;
    bool idle_started;
    int idle_stop;                     /* atomic */
    bool idle_active;                  /* under mu: a poll is on the bus; pks_claim and the worker's start wait for it to finish */
    bool film_manual;                  /* under mu: the claim is a manual film move / eject, which the idle poll may run beside (it keeps the lamp and the LED alive) */
    int idle_dead;                     /* atomic: the idle thread has left for good (final link status); the hold cannot be released any more */
    int closing;                       /* atomic: pk_session_close has begun; the eject stops at once */
    unsigned idle_polls;               /* polls made (diagnostic) */
    unsigned host_unknown;             /* OR of the HOST status bits other than 0x80 / 0x02 seen during the run */
    bool host_overflow;                /* the HOST status reported a FIFO overflow during the run (TLB 0x3ee) */
    pks_calstate cal;                  /* Task 15 */
    pk_dx_speed_history speed_hist[24];   /* TLB scanner+0x398, one five-slot history per (base, drag, IR, format) (FUN_10031570) */
};

/* events.c */
void pks_emit(pk_session *, const pk_event *);
void pks_emit_state(pk_session *, pk_state);
void pks_emit_msg(pk_session *, pk_event_kind, pk_status, uint32_t code, const char *fmt, ...);
void pks_emit_progress(pk_session *, int percent);

/* session.c: for the scan sequence (Task 13) */
pk_state pks_state(const pk_session *);
void pks_set_state(pk_session *, pk_state);          /* stores and emits PK_EV_STATE */
bool pks_cancelled(const pk_session *);
/* The lamp keep-alive: at most one light-board status pass per PKS_KEEPALIVE_MS, called from the scan sequence's loops (and nowhere else
 * may a long wait sit without it while the lamp is on). PK_E_DISCONNECTED etc. from the transport; PK_E_DEVICE (with a PK_EV_LAMP_HEALTH
 * event) when the lamp board has latched a fault. */
pk_status pks_keepalive(pk_session *);
/* The scan loop's status pass (see session.c): one register-0x02 read serving the lamp judgement and the DX reader (dx may be NULL). Replaces pks_keepalive while a DX
 * reader runs. Same errors as pks_keepalive, plus the DX read's. */
pk_status pks_scan_poll(pk_session *, pk_dx *dx);
/* What the scan sequence can do (scan.c): the F-135 Plus ('D' motor board) only, 35 mm, no prescan. PK_E_UNSUPPORTED with a reason in why. Called by pk_session_start, so an
 * unsupported scan is refused before the lamp is lit. */
pk_status pks_scan_supported(const pk_model *, const pk_scan_config *, char *why, size_t cap);

/* scan.c: the scan sequence (Task 13). Runs on the worker in state SCANNING with the lamp warm; moves to DRAINING itself via pks_set_state
 * if it needs to; returns PK_OK, PK_E_CANCELLED (pks_cancelled) or the failure. session_leave runs after it whatever it returns. */
pk_status pks_scan_sequence(pk_session *, const char *roll_base_path, const pk_scan_config *);

/* ---- Task 15 hooks (S-R32 a / b, implemented in cal.c): TLB never scans uncalibrated, and re-measures only when its rule says it is due.
 * pks_cal_scan_due is called by the scan sequence where TLB decides (RE 41 rows 6-7), before the window and lamp are set; it may replace *light and id. ---- */
/* cal.c (Task 15). pks_cal_resolve: "auto" = the newest usable stored light settings, else TLB's seeds with out id "" (the scan then calibrates first); a pin = that
 * calibration's light settings (PK_E_NOT_FOUND / PK_E_CAL_FOREIGN). pks_cal_scan_due applies pk_calibration_due and measures (stores a new "session" calibration, parent = the
 * selected id) when due. pks_cal_free releases the state at close. pks_cal_run / pks_cal_track are pk_calibrate / pk_track_test's bodies, called with the boards claimed and
 * (for the first) the lamp warm. */
pk_status pks_cal_resolve(pk_session *, const pk_scan_config *, pk_cal_light *out, char id[65]);
pk_status pks_cal_scan_due(pk_session *, const pk_scan_config *, pk_cal_light *light, char id[65]);
void pks_cal_free(pk_session *);
void pks_cal_identify(pk_session *);   /* the per-session CalWiz serial read (only when the session has an explicit calstore_root; otherwise the first scan does it) */
pk_status pks_cal_run(pk_session *, const pk_cal_request *, char out_id[65]);
pk_status pks_cal_track(pk_session *, pk_film_format, pk_track_result *);
/* idle.c (RE 47, S-R48): the status thread of an open session with no scan running. pks_idle_start after the open's init, pks_idle_stop (joins) before the session's leave. pks_hold_film_led records
 * the "remove film" hold (keep_film_led, with the current DX record count). */
void pks_idle_start(pk_session *);
void pks_idle_stop(pk_session *);
void pks_hold_film_led(pk_session *);
/* session.c: the bodies of the synchronous operations (calibration, track test) share these with the manual controls. */
pk_status pks_claim(pk_session *, bool gated);         /* PK_E_BUSY unless IDLE / READY (gated) and the boards are free; takes the boards */
void pks_release(pk_session *);
pk_status pks_warm_lamp(pk_session *);                 /* lamp on at the warm-up set, then TLB's stability wait (events; cancellable) */
pk_status pks_marker_begin(pk_session *);              /* the crash marker, written before anything is lit or moved */
pk_status pks_sync_end(pk_session *, pk_status run_status);   /* TLB's ForceCorrections end: leave (lamp off ...), marker cleared when confirmed; state back to IDLE, or FAULTED when a stop was not confirmed or run_status is a hardware failure */
unsigned pks_dx_speed(int dpi_base, bool ir);          /* scan.c: the DX start argument S (PB+0xac / PB+0xb0, RE 42 sec 1.2) */

/* Internal / test entry point (not in the public header): pk_session_start with the light settings given, so the whole sequence runs without Task 15.
 * Same checks and the same worker as pk_session_start; `light` is copied. */
pk_status pks_session_start_with_light(pk_session *, const char *roll_base_path, const pk_scan_config *, const pk_cal_light *light,
                                       pk_events_cb, void *user);

#endif
