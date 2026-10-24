#define _POSIX_C_SOURCE 200809L
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1      /* sys/sysctl.h needs u_int and friends */
#endif
/* The scan session (Task 12). A state machine on a worker thread; session_leave is the only way out of Warmup, Ready and Scanning; a marker
 * file lets the next process stop a scanner that a dead one left running (ported from v1 tools/pakon_scan.py safe_stop / marker_*).
 * Nothing here writes scanner memory, and nothing sends 0x08, 0x94..0x98 to the light board. */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#ifdef __APPLE__
#include <sys/sysctl.h>
#endif
#include <time.h>
#include <unistd.h>
#include "pakon/dx.h"
#include "session/session_internal.h"
#include "util/util.h"

#define LOAD(p) __atomic_load_n(&(p), __ATOMIC_SEQ_CST)
#define STORE(p, v) __atomic_store_n(&(p), (v), __ATOMIC_SEQ_CST)

#define PKS_DEFAULT_WARMUP_MS 300000u
#define PKS_LEAVE_BUDGET_MS 1600u          /* S-R29: the whole of session_leave / open-failure cleanup; with the last transfer and the drains it ends under 2 s */
#define PKS_PID_SLACK_S 2                  /* a marker's whole-second start time against a process start time with sub-second resolution */

/* PSI's open-gate lamp set on the owner's unit (v1 docs/59 steps 81/82; hw1.c LAMP_LEVELS / LAMP_ON): levels R3 G11 B7, on-counts R654 G374 B156,
 * period 982. The warm-up only needs the lamp lit and stable; Task 13/15 replace this with the calibration-derived set. */
static const uint16_t WARM_LEVELS[4] = { 3, 11, 7, 0 };
static const uint16_t WARM_ON[4] = { 654, 374, 156, 0 };
#define WARM_PERIOD 982

/* ------------------------------------------------------------------ state, events */
pk_state pks_state(const pk_session *s) { return (pk_state)__atomic_load_n(&s->state, __ATOMIC_SEQ_CST); }
void pks_set_state(pk_session *s, pk_state st) { STORE(s->state, (int)st); pks_emit_state(s, st); }
bool pks_cancelled(const pk_session *s) { return __atomic_load_n(&s->cancel, __ATOMIC_SEQ_CST) != 0; }
pk_state pk_session_state(const pk_session *s) { return s ? pks_state(s) : PK_S_IDLE; }
pk_boards *pk_session_boards(pk_session *s) { return s ? s->b : NULL; }

pk_status pks_keepalive(pk_session *s) {
    if (s->opts.no_keepalive) return PK_OK;
    unsigned long long now = pkb_now_ms();
    if (s->last_keepalive_ms && now - s->last_keepalive_ms < PKS_KEEPALIVE_MS) return PK_OK;
    s->last_keepalive_ms = now;
    pk_status st = pk_lamp_keepalive(s->b);
    if (st != PK_OK) return st;
    if (s->b->sticky & PKS_LAMP_FAULTS) {
        pks_emit_msg(s, PK_EV_LAMP_HEALTH, PK_E_DEVICE, s->b->sticky, "the lamp board reports a fault");
        return PK_E_DEVICE;
    }
    return PK_OK;
}

/* One status pass of the scan loop, TLB's non-forced FUN_1000BDD0 (RE 42 sec 9), called every PKS_SCAN_POLL_MS (TLB: 1 ms):
 *   HOST status (type-3 poll to the FX2). Bit 1 = FIFO overflow is remembered (TLB reports 0x3ee instead of 0x3eb); bit 7 clear = nothing else is read.
 *   Bit 7 set: LIGHT register 0x02 once (+ the 0x06 acknowledge); its bits serve both consumers: the lamp judgement (0x5B, the gated TLB path) and the DX reader (an event reads
 *   0x90 whatever the value, as TLB does). Then HOST status again if the light had an event, and MOTOR 0x02 (+ 0x06) while the host still reports an interrupt.
 * Plus the 200 ms lamp-health read (0x83, 0x84, 0x88: telemetry only, the TLB path judges only on a board-raised event), which with the 1 ms host poll keeps the light board's
 * idle counter fed far more often than once a second. Calling pks_keepalive and pk_dx_poll_event back to back would let the first swallow the event the second needs. */
pk_status pks_scan_poll(pk_session *s, pk_dx *dx) {
    pk_boards *b = s->b;
    uint8_t hs = 0;
    pk_status st = pk_host_status(b, &hs);
    if (st != PK_OK) return st;
    if (hs & 0x02) s->host_overflow = true;
    s->host_unknown |= (unsigned)hs & ~0x8Au;          /* bits TLB does not test (v1: 0x20 = sticky host fault): recorded, never fatal (S-R36). 0x08 is set in every
                                                        * normal reply of this unit (v1 docs/03-protocol.md: 03 04 10 08 aa aa), so it is not recorded */
    if (hs & 0x80) {
        uint32_t taken = 0;
        bool ev = false;
        st = pkb_irq_take_ex(b, 0x5Bu | 0xA4u, &taken, NULL, &ev);
        if (st != PK_OK) return st;
        st = pkb_lamp_monitor(b, taken & 0x5Bu, false, NULL);
        if (st != PK_OK) return st;
        bool more = true;
        if (ev) {
            if (dx) {
                uint8_t nib = 0;
                st = pk_dx_read_packet(b, dx, &nib);
                if (st != PK_OK) return st;
            }
            st = pk_host_status(b, &hs);
            if (st != PK_OK) return st;
            more = (hs & 0x80) != 0;
        }
        if (more && (st = pk_motor_irq_service(b, NULL)) != PK_OK) return st;
    }
    unsigned long long now = pkb_now_ms();
    if (!s->opts.no_keepalive && (!s->last_keepalive_ms || now - s->last_keepalive_ms >= PKS_KEEPALIVE_MS)) {
        pk_light_health h;
        s->last_keepalive_ms = now;
        st = pk_light_health_poll(b, &h);
        if (st != PK_OK) return st;
    }
    if (b->sticky & PKS_LAMP_FAULTS) {
        pks_emit_msg(s, PK_EV_LAMP_HEALTH, PK_E_DEVICE, b->sticky, "the lamp board reports a fault");
        return PK_E_DEVICE;
    }
    return PK_OK;
}

/* ------------------------------------------------------------------ the crash marker */
static bool file_exists(const char *p) { struct stat sb; return stat(p, &sb) == 0; }

/* {"pid", "started", "model"}; written before the lamp is lit, removed when the run has put the scanner in a stopped state. */
static pk_status marker_write(pk_session *s) {
    pku_jw *w = pku_jw_new();
    if (!w) return PK_E_NOMEM;
    pku_jw_obj_begin(w);
    pku_jw_key(w, "pid"); pku_jw_int(w, (long long)getpid());
    pku_jw_key(w, "started"); pku_jw_int(w, (long long)time(NULL));
    pku_jw_key(w, "model"); pku_jw_str(w, s->model->name);
    pku_jw_obj_end(w);
    size_t n = 0;
    const char *txt = pku_jw_finish(w, &n);
    pk_status st = txt ? pku_write_file_atomic(s->marker_path, txt, n) : PK_E_NOMEM;
    pku_jw_free(w);
    if (st == PK_OK) s->marker_present = true;
    return st;
}

static void marker_remove(pk_session *s) {
    if (unlink(s->marker_path) == 0 || errno == ENOENT) s->marker_present = false;
}

/* The pid and start time (unix seconds) in a marker; pid 0 if the file is unreadable or has none (v1: a damaged marker is stale). */
static long marker_read(const char *path, long long *started) {
    uint8_t *d = NULL;
    size_t n = 0;
    long pid = 0;
    *started = 0;
    if (pku_read_file(path, &d, &n) != PK_OK) return 0;
    pku_json *j = NULL;
    if (pku_json_parse((const char *)d, n, &j) == PK_OK) {
        const pku_json *p = pku_json_get(j, "pid"), *st = pku_json_get(j, "started");
        if (p && pku_json_is_int(p)) pid = (long)pku_json_int(p);
        if (st && pku_json_is_int(st)) *started = pku_json_int(st);
        pku_json_free(j);
    }
    free(d);
    return pid;
}

/* The start time of a process, unix seconds; false if it cannot be had (then the pid alone decides). macOS: sysctl KERN_PROC_PID p_starttime. */
static bool proc_start_time(long pid, long long *t) {
#ifdef __APPLE__
    int mib[4] = { CTL_KERN, KERN_PROC, KERN_PROC_PID, (int)pid };
    struct kinfo_proc kp;
    size_t len = sizeof kp;
    memset(&kp, 0, sizeof kp);
    if (sysctl(mib, 4, &kp, &len, NULL, 0) != 0 || len < sizeof kp || kp.kp_proc.p_pid != (pid_t)pid) return false;
    *t = (long long)kp.kp_proc.p_starttime.tv_sec;
    return true;
#else
    (void)pid; (void)t;
    return false;
#endif
}

/* v1 check_stale, plus pid reuse (S-R30 m1): a pid that is not ours and exists is the marker's owner only if it started no later than the marker
 * was written. A process that started after is a different process that was handed the dead owner's pid: the marker is stale. EPERM means it exists. */
static bool pid_alive(long pid, long long marker_started) {
    if (pid <= 0 || pid == (long)getpid()) return false;
    if (kill((pid_t)pid, 0) != 0 && errno != EPERM) return false;
    long long ps;
    if (marker_started > 0 && proc_start_time(pid, &ps) && ps > marker_started + PKS_PID_SLACK_S) return false;
    return true;
}

typedef struct { bool motor, lamp, absent; } stopped;

/* v1 safe_stop: motor first (film movement is what damages film), then lamp, then the DX stop. v1's acquire-off needs a configured CCD here
 * (pk_host_acquire is PK_E_BUSY before any configure), and the 0x98 illuminator mask is never sent (RE 29: dropped). */
static stopped safe_stop(pk_boards *b) {
    stopped r = { false, false, false };
    pk_status m = pk_motor_stop(b);
    r.motor = m == PK_OK;
    pk_status l = pk_light_lamp_off(b);
    r.lamp = l == PK_OK;
    pk_status d = pk_dx_stop(b);
    r.absent = m == PK_E_DISCONNECTED || l == PK_E_DISCONNECTED || d == PK_E_DISCONNECTED;
    return r;
}

/* v1 marker_should_clear: the motor stop was acknowledged, or the scanner is not on the bus at all. */
static bool marker_should_clear(const stopped *r) { return r->motor || r->absent; }

/* ------------------------------------------------------------------ session_leave */
/* The only path out of Warmup, Ready and Scanning. Best effort, in this order: acquire off, motor stop, lamp off, then film LED off, status LED
 * off. A failed step never skips the next. Truly bounded (S-R29) by leave mode in the link and boards: every transfer at most 500 ms, one link
 * attempt and one board attempt per step, no wedge ping, and PKS_LEAVE_BUDGET_MS for the whole leave (calls after that fail at once, still in
 * order). A pulled cable is PK_E_DISCONNECTED, which is final everywhere. A step that overruns 500 ms is reported as a warning. Returns the
 * first failure; *r reports what was achieved. */
static pk_status leave(pk_session *s, stopped *r) {
    pk_boards *b = s->b;
    pk_status first = PK_OK;
    r->motor = r->lamp = r->absent = false;
    pk_boards_set_leave_mode(b, true, PKS_LEAVE_BUDGET_MS);          /* S-R29: 500 ms transfers, one attempt per step, 1.6 s in all */
    for (int step = 0; step < 5; step++) {
        static const char *const NAME[5] = { "acquire off", "motor stop", "lamp off", "film LED off", "status LED off" };
        unsigned long long t0 = pkb_now_ms();
        pk_status st;
        switch (step) {
        case 0:                                    /* acquire off: only if the FPGA is known to be acquiring (the scan sequence's own end has done it otherwise) */
            if (b->fpga_ctrl >= 0 && (b->fpga_ctrl & 1)) { st = pk_host_acquire(b, false); if (st == PK_E_BUSY) st = PK_OK; }
            else st = PK_OK;
            break;
        case 1:                                    /* the scan sequence's EndScan already stopped the motor (TLB E3 step 5): not repeated */
            if (s->end_motor_done) { st = PK_OK; r->motor = true; }
            else { st = pk_film_stop(b); r->motor = st == PK_OK; }
            break;
        case 2:
            if (s->end_lamp_done) { st = PK_OK; r->lamp = true; }
            else { st = pk_light_lamp_off(b); r->lamp = st == PK_OK; }
            break;
        case 3: st = s->keep_film_led ? PK_OK : pk_film_led(b, PK_FILMLED_OFF); break;   /* a held 0x4C (film still over a sensor) stays lit */
        default: st = s->keep_status_led ? PK_OK : pk_led_set(b, PK_LED_STATUS, 0); break;   /* TLB leaves status 4 after FilmInGuides */
        }
        unsigned long long el = pkb_now_ms() - t0;
        if (el > PKS_LEAVE_STEP_MS) pks_emit_msg(s, PK_EV_WARNING, st, (uint32_t)el, "leave: %s took %llu ms", NAME[step], el);
        if (st == PK_E_DISCONNECTED) r->absent = true;
        if (st != PK_OK && first == PK_OK) first = st;
    }
    pk_boards_set_leave_mode(b, false, 0);
    return first;
}

/* ------------------------------------------------------------------ firmware version warning (RE 29 sec 9) */
static const char *const ITEM_NAME[] = {
#define PKV_ITEM(n) #n,
#include "../../tables/vendor_items.def"
#undef PKV_ITEM
};

/* TLB's file search is %s%s%02x??.hex with xx = devinfo[2] and takes the highest yy found, comparing it with devinfo[1] (RE 29 sec 9). The
 * prefix is derived there only for the light board: class byte 0x0F is "NL" (PICL Plus), 0x08 is "PL". The motor, DX and APS boards' version
 * registers are NOT derived (RE 29 sec 9, last sentence: "Task 12 reads them on hardware; read-only"), so nothing is sent to them.
 * TODO(RE 29 sec 9): read and compare the motor and DX versions once a read-only register is established for them. A mismatch is a warning only. */
static void check_firmware(pk_session *s) {
    if (s->fw_class < 0 || !s->vendor_root[0]) return;
    const char *pre = s->fw_class == 0x0F ? "NL" : s->fw_class == 0x08 ? "PL" : NULL;
    if (!pre) return;
    pk_vendor *v = NULL;
    if (pk_vendor_open(s->vendor_root, &v) != PK_OK) return;      /* no vendor store: no comparison */
    int best = -1;
    char want[16];
    snprintf(want, sizeof want, "PKV_FW_%s%02X", pre, s->fw_hw & 0xFF);
    for (size_t i = 0; i < sizeof ITEM_NAME / sizeof ITEM_NAME[0]; i++) {
        unsigned yy;
        if (strncmp(ITEM_NAME[i], want, strlen(want)) == 0 && sscanf(ITEM_NAME[i] + strlen(want), "%2x_HEX", &yy) == 1 && pk_vendor_has(v, (pk_vendor_item)i) && (int)yy > best)
            best = (int)yy;
    }
    pk_vendor_close(v);
    if (best >= 0 && best != s->fw_fw)
        pks_emit_msg(s, PK_EV_FW_VERSION_WARNING, PK_OK, (uint32_t)(((s->fw_hw & 0xFF) << 8) | (s->fw_fw & 0xFF)),
                     "light board firmware %02X%02X, newest %s%02X%02X.hex in Config/Firmware", s->fw_hw & 0xFF, s->fw_fw & 0xFF, pre, s->fw_hw & 0xFF, best);
}

/* ------------------------------------------------------------------ the worker */
static void warm_cb(void *user, int percent, const pk_light_health *h) {
    pk_session *s = (pk_session *)user;
    pks_emit_progress(s, percent);
    if (h) {
        if (h->lamp_temp_raw >= 0)
            pks_emit_msg(s, PK_EV_LAMP_HEALTH, PK_OK, h->flags, "lamp %.1f C", h->lamp_temp_raw / 16.0);
        else
            pks_emit_msg(s, PK_EV_LAMP_HEALTH, PK_OK, h->flags, "lamp temperature not read");
    }
}

/* A hardware failure leaves the session FAULTED; the rest (cancel, a refused request, a missing scan sequence) returns to IDLE. */
static bool is_hw_fault(pk_status st) {
    switch (st) {
    case PK_E_DISCONNECTED: case PK_E_FIRMWARE_WEDGED: case PK_E_TRANSPORT: case PK_E_TIMEOUT: case PK_E_PROTOCOL:
    case PK_E_DEVICE: case PK_E_LAMP_WARMUP: case PK_E_FIRMWARE_MISMATCH: return true;
    default: return false;
    }
}

/* The lamp up and warm (the warm-up of a scan and of a calibration alike). */
pk_status pks_warm_lamp(pk_session *s) {
    pk_boards *b = s->b;
    pk_status st = pk_light_lamp_on(b, true, false);                 /* every lamp-on resends 0x81 and 0x82 (S-R26) */
    if (st == PK_OK) st = pk_light_set_levels(b, WARM_LEVELS);
    if (st == PK_OK) st = pk_light_set_duty(b, WARM_ON, WARM_PERIOD);
    if (st != PK_OK) return st;
    pk_warmup_opts wo = { PKS_KEEPALIVE_MS, s->opts.warmup_timeout_ms ? s->opts.warmup_timeout_ms : PKS_DEFAULT_WARMUP_MS };
    return pk_lamp_warmup(b, &wo, warm_cb, s, (const volatile int *)&s->cancel);   /* polls light register 0x02 every 200 ms: the keep-alive while warming */
}

static pk_status run(pk_session *s) {
    check_firmware(s);
    pk_status st = pks_warm_lamp(s);
    if (st != PK_OK) return st;
    if (pks_cancelled(s)) return PK_E_CANCELLED;
    pks_set_state(s, PK_S_READY);
    if (pks_cancelled(s)) return PK_E_CANCELLED;
    pks_set_state(s, PK_S_SCANNING);
    return pks_scan_sequence(s, s->roll_base, s->cfg);
}

/* PSI's end-of-scan eject (RE 47 sec 1, S-R48 / S-R49): PSI ejects whenever a scan job it accepted ends (its UI state 1..8, RE 48a C1): normal end, error, cancel, and also a warm-up or calibration
 * failure and a FilmInGuides refusal. Once per job: Sleep(300), then AdvanceFilm by FeedMode (FUN_00447440). FeedMode 0 (the F-135 Plus, the owner's value) = 500 ms forward at speed 1000 (MOTOR 0xA5 0x7FFE,
 * 0xA0, 500 ms, 0xA2, exactly pk_film_eject's packets); 1 = 1500 ms reverse; 2 = SpliceAdvance ms forward. No sensor is read and nothing waits for the film to go.
 * It runs after the run's own end and the session's leave, so the lamp is off and the motor was stopped (the caller checks both were confirmed). Close stops it within 20 ms (s->closing); a cancel does NOT:
 * PSI's push is not cancellable by the scan's cancel either way (documented, RE 48a D1 is INFERRED). The motor is stopped on every path; *stopped = that 0xA2 was confirmed. */
static pk_status eject_push(pk_session *s, const pk_scan_config *c, bool *stopped) {
    pk_boards *b = s->b;
    *stopped = true;
    for (unsigned w = 0; w < PKS_EJECT_DELAY_MS && !LOAD(s->closing); w += 20) pkb_sleep_ms(20);
    if (LOAD(s->closing)) return PK_E_CANCELLED;
    pk_film_dir dir = c->feed_mode == 1 ? PK_FILM_REVERSE : PK_FILM_FORWARD;
    unsigned ms = c->feed_mode == 1 ? 1500u : c->feed_mode == 2 ? c->splice_advance_ms : 500u;
    pk_status st = pk_film_start_register(b, dir, pkb_speed_register(s->model, 1000));
    if (st == PK_OK) {
        unsigned long long t0 = pkb_now_ms();
        while (pkb_now_ms() - t0 < ms && !LOAD(s->closing)) pkb_sleep_ms(20);
    }
    pk_status sp = pk_film_stop(b);                                   /* always: 0xA2 */
    *stopped = sp == PK_OK;
    return st != PK_OK ? st : sp;
}

static void *worker(void *arg) {
    pk_session *s = (pk_session *)arg;
    pks_emit_state(s, PK_S_WARMUP);
    pk_status st = run(s);
    pks_set_state(s, PK_S_STOPPING);
    stopped r;
    pk_status lv = leave(s, &r);
    s->end_motor_done = s->end_lamp_done = false;                     /* only valid for the leave right after the scan sequence */
    s->keep_status_led = false;                                       /* keep_film_led is the remove-film hold: it outlives the run, the idle status thread releases it (RE 47) */
    pk_status final = st;
    if (lv != PK_OK && !is_hw_fault(st)) final = lv;                  /* a failed leave step outranks a cancel or a refusal */
    if (final != PK_OK && final != PK_E_CANCELLED) {
        pk_error e;
        pk_link_last_error_copy(s->link, &e);                        /* under the link's lock: a Stop may be using the link */
        const char *ctx = s->diag[0] ? s->diag : e.context;       /* the scan sequence's own text (stream sync, stall, no film) first */
        pks_emit_msg(s, PK_EV_ERROR, final, 0, "%s%s%s", pk_status_str(final), ctx[0] ? ": " : "", ctx);
    }
    /* the eject (S-R49 I-1, I-3): not after a no-film timeout (PSI resets to Idle first, RE 48a C5), not with a gone scanner or a final status, and only when the motor stop and the lamp-off are confirmed */
    if (st != PK_E_NO_FILM && !pkb_status_is_final(st) && !r.absent && r.motor && r.lamp && !LOAD(s->closing) && s->cfg) {
        bool stopped;
        pks_emit_msg(s, PK_EV_EJECT, PK_OK, 0, "end-of-scan eject");
        pk_status ej = eject_push(s, s->cfg, &stopped);
        if (!stopped) r.motor = false;                                // an unconfirmed stop keeps the marker and the fault
        if (ej != PK_OK && ej != PK_E_CANCELLED) {
            pks_emit_msg(s, PK_EV_WARNING, ej, 0, "the end-of-scan eject failed: %s", pk_status_str(ej));
            if (pkb_status_is_final(ej)) {
                r.absent = ej == PK_E_DISCONNECTED || r.absent;
                if (!is_hw_fault(final)) final = ej;                      // the scanner went during the push: the session ends FAULTED like any other hardware loss (N-1)
            }
        }
    }
    bool clear = (r.motor && r.lamp) || r.absent;                    /* after a run the lamp-off must be confirmed too: an unconfirmed one keeps the marker and the fault (R-I1) */
    if (clear) marker_remove(s);
    pk_state end = is_hw_fault(final) || !clear ? PK_S_FAULTED : PK_S_IDLE;   /* an unacknowledged motor stop or lamp-off keeps the marker and the fault */
    if (end == PK_S_FAULTED || r.absent) {
        bool was_held = LOAD(s->keep_film_led);
        STORE(s->keep_film_led, false);
        if (was_held && !r.absent) {                                      /* N-3: best effort, bounded: the film LED must not go on blinking "remove film" in a FAULTED session */
            pk_boards_set_leave_mode(s->b, true, PKS_LEAVE_BUDGET_MS);
            (void)pk_film_led(s->b, PK_FILMLED_OFF);
            pk_boards_set_leave_mode(s->b, false, 0);
        }
    }      /* nothing can release the remove-film hold in a FAULTED session or on a gone scanner (S-R49 I-2) */
    pthread_mutex_lock(&s->mu);
    STORE(s->state, (int)end);
    s->final = final;
    s->hw_busy = false;
    pthread_mutex_unlock(&s->mu);
    pks_emit_state(s, end);
    pthread_mutex_lock(&s->mu);
    s->running = false;
    pthread_cond_broadcast(&s->cv);
    pthread_mutex_unlock(&s->mu);
    return NULL;
}

/* ------------------------------------------------------------------ open / start / cancel / wait / close */
static pk_link_model link_model_of(const pk_model *m) {
    switch (m->id) {
    case PK_MODEL_F135: return PK_LINK_F135;
    case PK_MODEL_F135_PLUS: return PK_LINK_F135_PLUS;
    case PK_MODEL_F235: case PK_MODEL_F235C: return PK_LINK_F235;
    default: return PK_LINK_F335;
    }
}

static void destroy(pk_session *s) {
    if (s->b) {
        pk_boards_set_leave_mode(s->b, true, PKS_LEAVE_BUDGET_MS);   /* pk_boards_close may still try a lamp-off: bounded too (S-R29) */
        pk_boards_close(s->b);
    }
    if (s->link) pk_link_close(s->link);
    pks_cal_free(s);
    pthread_cond_destroy(&s->cv);
    pthread_mutex_destroy(&s->mu);
    free(s);
}

static bool copy_str(char *dst, const char *src) {
    if (!src) { dst[0] = 0; return true; }
    size_t n = strlen(src);
    if (n >= PKS_PATH_MAX) return false;
    memcpy(dst, src, n + 1);
    return true;
}

/* Open-failure cleanup (I-2 / S-R29): once 0x80 = 1 may have gone out, a failed open puts the lamp out again, bounded like session_leave. */
static void lamp_off_bounded(pk_session *s) {
    pk_boards_set_leave_mode(s->b, true, PKS_LEAVE_BUDGET_MS);
    (void)pk_light_lamp_off(s->b);
    pk_boards_set_leave_mode(s->b, false, 0);
}

/* TLB's init order, once (S-R26): 0x87 = 00 00, 0x80 = 1, 0x82 all-zero (N = 982), lamp-off, 0x89 = 0. The monitor thresholds (with 0xD0 = 0 and
 * 0xD1 = 1, RE 29 sec 4: allowed, TLB sends them at init) go first so a lamp is never lit without them. The lamp-off is pk_light_lamp_off, which
 * zeroes the drive, writes 0x80 = 0, reloads and confirms (the session never writes 0x80 = 0 itself). */
static pk_status init_scanner(pk_session *s) {
    pk_boards *b = s->b;
    static const uint8_t zero2[2] = { 0, 0 };
    static const uint16_t zero4[4] = { 0, 0, 0, 0 };
    bool lamp_tried = false;
    pk_status st = pk_link_write(s->link, b->light, PKB_REG_LIGHT_87, zero2, 2);
    if (st == PK_OK) st = pk_light_lamp_init_thresholds(b);
    if (st == PK_OK) { lamp_tried = true; st = pk_light_lamp_on(b, true, false); }
    if (st == PK_OK) st = pk_light_set_duty(b, zero4, WARM_PERIOD);
    if (st == PK_OK) st = pk_light_lamp_off(b);
    if (st == PK_OK) { st = pk_link_write(s->link, b->light, PKB_REG_LIGHT_89, zero2, 1); if (st == PK_OK) b->light_89 = 0; }
    if (st == PK_OK) st = pk_boards_open_led_gate(b);                 /* TLB opens the LED gate at session open (S-R20 I-5) */
    if (st == PK_OK) st = pk_leds_enable(b, s->opts.leds_enabled);
    uint32_t drained = 0;
    uint8_t d[12];
    if (st == PK_OK) st = pkb_irq_take(b, 0xFFu, &drained);          /* latched register 0x02 bits: read and acknowledged, not judged (TLB's monitor drains from open) */
    if (st == PK_OK) st = pkb_light_devinfo(b, d);                   /* RE 29 sec 9 */
    if (st != PK_OK) {
        if (lamp_tried) lamp_off_bounded(s);                         /* whatever the failure was: the lamp may be enabled */
        return st;
    }
    s->fw_class = d[0]; s->fw_fw = d[1]; s->fw_hw = d[2];
    return PK_OK;
}

pk_status pk_session_open(pk_transport *t, const pk_session_opts *o, pk_session **out) {
    if (!out) return PK_E_ARG;
    *out = NULL;
    if (!t || !o || !o->work_dir || !o->work_dir[0]) return PK_E_ARG;
    const pk_model *m = pk_model_get(o->model);
    if (!m || o->warmup_timeout_ms > PKS_DEFAULT_WARMUP_MS) return PK_E_ARG;   /* TLB's warm-up timer is fixed at 300000 (pk_lamp_warmup refuses more) */
    if (!m->roles.light || !m->roles.motor || !m->roles.host) return PK_E_UNSUPPORTED;   /* beta models: their boards are refused until Task 21 */
    pk_session *s = (pk_session *)calloc(1, sizeof *s);
    if (!s) return PK_E_NOMEM;
    pthread_mutex_init(&s->mu, NULL);
    pthread_cond_init(&s->cv, NULL);
    if (!copy_str(s->work_dir, o->work_dir) || !copy_str(s->calstore_root, o->calstore_root) || !copy_str(s->vendor_root, o->vendor_root) ||
        snprintf(s->marker_path, sizeof s->marker_path, "%s/session.active", s->work_dir) >= (int)sizeof s->marker_path) {
        destroy(s);
        return PK_E_ARG;
    }
    s->opts = *o;
    s->opts.work_dir = s->work_dir;
    s->opts.calstore_root = s->calstore_root;
    s->opts.vendor_root = s->vendor_root;
    s->t = t;
    s->model = m;
    s->fw_class = s->fw_fw = s->fw_hw = -1;
    pk_cal_policy_default(&s->cal.policy);
    s->final = PK_OK;
    STORE(s->state, (int)PK_S_IDLE);
    pk_status st = pku_mkdirs(s->work_dir);
    if (st != PK_OK) { destroy(s); return st; }
    /* A live owner is checked before anything is sent (v1 check_stale). */
    bool stale = file_exists(s->marker_path);
    if (stale) {
        long long started;
        long pid = marker_read(s->marker_path, &started);
        if (pid_alive(pid, started)) { destroy(s); return PK_E_BUSY; }
    }
    st = pk_link_open(t, link_model_of(m), &s->link);                /* wraps the transport with the write guard (idempotent) */
    if (st == PK_OK) st = pk_boards_open(s->link, m, &s->b);
    if (st != PK_OK) { destroy(s); return st; }
    s->marker_present = stale;
    if (stale) {                                                     /* a dead process left a scan in flight: stop everything first */
        stopped r = safe_stop(s->b);
        if (!marker_should_clear(&r)) { destroy(s); return PK_E_DEVICE; }   /* the marker stays, so the next open retries */
        marker_remove(s);
    }
    st = init_scanner(s);
    if (st != PK_OK) { destroy(s); return st; }
    if (s->calstore_root[0]) pks_cal_identify(s);                    /* 4-byte CalWiz serial: which scanner this is (a failure adopts nothing) */
    pks_idle_start(s);                                               /* TLB's status thread runs whenever the scanner is open (RE 47 sec 5.3) */
    *out = s;
    return PK_OK;
}

/* PK_OK when a run may start now; the state errors of pk_session_start. */
static pk_status start_state(pk_session *s) {
    pthread_mutex_lock(&s->mu);
    pk_state cur = pks_state(s);
    pk_status r = PK_OK;
    if (cur == PK_S_FAULTED) r = s->final != PK_OK ? s->final : PK_E_DEVICE;   /* not BUSY: the app must reopen */
    else if (cur != PK_S_IDLE || s->hw_busy || s->running) r = PK_E_BUSY;
    pthread_mutex_unlock(&s->mu);
    return r;
}

static pk_status start_common(pk_session *s, const char *roll_base_path, const pk_scan_config *cfg, const pk_cal_light *light, pk_events_cb cb, void *user) {
    if (!s || !roll_base_path || !roll_base_path[0] || !cfg) return PK_E_ARG;
    if (strlen(roll_base_path) >= PKS_PATH_MAX) return PK_E_ARG;
    pk_status st = start_state(s);                                   /* the state first: BUSY / FAULTED outrank a bad config */
    if (st != PK_OK) return st;
    bool loaded = false;
    if (s->have_prev && s->prev_cfg.roll_mode != cfg->roll_mode) {        /* the roll mode may not change while film is loaded: read the sensors (idle: the bus is ours) */
        pk_film_sensors fs;
        if (pk_film_sense(s->b, &fs) == PK_OK) loaded = fs.entry || fs.exit;
    }
    st = pk_scan_config_validate(s->model, cfg, s->have_prev ? &s->prev_cfg : NULL, loaded);
    if (st != PK_OK) return st;
    char why[160] = "";
    st = pks_scan_supported(s->model, cfg, why, sizeof why);        /* before any lamp-up (m1) */
    if (st != PK_OK) {
        if (cb) {
            pk_event e;
            memset(&e, 0, sizeof e);
            e.kind = PK_EV_ERROR; e.state = pks_state(s); e.status = st;
            snprintf(e.text, sizeof e.text, "%s", why);
            cb(user, &e);
        }
        return st;
    }
    pk_cal_light cal;
    char id[65] = "";
    if (light) cal = *light;
    else {
        st = pks_cal_resolve(s, cfg, &cal, id);
        if (st == PK_E_NOT_FOUND && cb) {                            /* sent to the caller directly: no run, so no worker owns s->cb */
            pk_event e;
            memset(&e, 0, sizeof e);
            e.kind = PK_EV_ERROR;
            e.state = pks_state(s);
            e.status = st;
            snprintf(e.text, sizeof e.text, "no calibration yet: the scanner must be calibrated before a scan (calibration \"%.40s\")", cfg->calibration_pin);
            cb(user, &e);
        }
        if (st != PK_OK) return st;
    }
    if (cal.version != 1 || cal.dpi_base != cfg->dpi_base || cal.ir != cfg->ir) {   /* before any lamp-up (r-m5) */
        if (cb) {
            pk_event e;
            memset(&e, 0, sizeof e);
            e.kind = PK_EV_ERROR; e.state = pks_state(s); e.status = PK_E_ARG;
            snprintf(e.text, sizeof e.text, "the light settings are not for this base / IR setting");
            cb(user, &e);
        }
        return PK_E_ARG;
    }
    pthread_mutex_lock(&s->mu);                                      /* nothing of the session is touched before the state is checked (a run owns roll_base) */
    if (s->joinable && !s->running) { pthread_t old = s->th; s->joinable = false; pthread_mutex_unlock(&s->mu); pthread_join(old, NULL); pthread_mutex_lock(&s->mu); }   /* a finished run not yet waited for */
    while (s->idle_active) pthread_cond_wait(&s->cv, &s->mu);        /* an idle status poll in progress finishes first; running is set below under this same hold of mu (no unlock between this wait and the spawn), so none starts after */
    pk_state cur = pks_state(s);
    if (cur == PK_S_FAULTED) { pk_status f = s->final; pthread_mutex_unlock(&s->mu); return f != PK_OK ? f : PK_E_DEVICE; }   /* not BUSY: the app must reopen */
    if (cur != PK_S_IDLE || s->hw_busy || s->running) { pthread_mutex_unlock(&s->mu); return PK_E_BUSY; }
    (void)copy_str(s->roll_base, roll_base_path);
    st = marker_write(s);                                            /* before the lamp: a crash from here on is recoverable */
    if (st != PK_OK) { pthread_mutex_unlock(&s->mu); return st; }
    s->cb = cb;
    s->cb_user = user;
    s->cfg = cfg;
    s->prev_cfg = *cfg;
    s->have_prev = true;
    s->host_overflow = false;
    s->host_unknown = 0;
    s->light = cal;
    memcpy(s->cal_id, id, sizeof s->cal_id);
    s->end_motor_done = s->end_lamp_done = false;
    s->diag[0] = 0;
    s->last_keepalive_ms = 0;
    s->final = PK_OK;
    STORE(s->cancel, 0);
    STORE(s->state, (int)PK_S_WARMUP);
    s->hw_busy = true;
    s->running = true;
    if (pthread_create(&s->th, NULL, worker, s) != 0) {
        STORE(s->state, (int)PK_S_IDLE);
        s->hw_busy = false;
        s->running = false;
        marker_remove(s);
        pthread_mutex_unlock(&s->mu);
        return PK_E_NOMEM;
    }
    s->joinable = true;
    pthread_mutex_unlock(&s->mu);
    return PK_OK;
}

pk_status pk_session_start(pk_session *s, const char *roll_base_path, const pk_scan_config *cfg, pk_events_cb cb, void *user) {
    return start_common(s, roll_base_path, cfg, NULL, cb, user);
}

pk_status pks_session_start_with_light(pk_session *s, const char *roll_base_path, const pk_scan_config *cfg, const pk_cal_light *light, pk_events_cb cb, void *user) {
    return light ? start_common(s, roll_base_path, cfg, light, cb, user) : PK_E_ARG;
}

pk_status pk_session_cancel(pk_session *s) {
    if (!s) return PK_E_ARG;
    STORE(s->cancel, 1);
    return PK_OK;
}

pk_status pk_session_wait(pk_session *s, pk_status *final) {
    if (!s) return PK_E_ARG;
    pthread_mutex_lock(&s->mu);
    while (s->running) pthread_cond_wait(&s->cv, &s->mu);
    if (s->joinable) { pthread_t th = s->th; s->joinable = false; pthread_mutex_unlock(&s->mu); pthread_join(th, NULL); pthread_mutex_lock(&s->mu); }
    if (final) *final = s->final;
    pthread_mutex_unlock(&s->mu);
    return PK_OK;
}

void pk_session_close(pk_session *s) {
    if (!s) return;
    STORE(s->closing, 1);                                            /* an eject in progress ends within 20 ms (S-R49 I-4) */
    pk_session_cancel(s);
    (void)pk_session_wait(s, NULL);
    pk_boards_set_leave_mode(s->b, true, PKS_LEAVE_BUDGET_MS);       /* S-R29: an idle poll still in flight gets capped single attempts (the leave below sets its own budget) */
    pks_idle_stop(s);                                                /* the status thread ends before the final leave; closing releases the remove-film hold (the LED goes off) */
    STORE(s->keep_film_led, false);
    stopped r;
    (void)leave(s, &r);                                              /* lamp off, LEDs off (idempotent; fails fast on a gone scanner) */
    if (s->marker_present && ((r.motor && r.lamp) || r.absent)) marker_remove(s);
    s->b->lamp_on = false;                                           /* leave just tried the lamp-off within its budget; pk_boards_close must not spend a second one */
    destroy(s);
}

/* ------------------------------------------------------------------ manual controls */
/* gated: IDLE or READY only. Every control claims the boards for its duration; a run (or another control) in progress is PK_E_BUSY. */
pk_status pks_claim(pk_session *s, bool gated) {
    if (!s) return PK_E_ARG;
    pk_status r = PK_OK;
    pthread_mutex_lock(&s->mu);
    pk_state st = pks_state(s);
    if (gated && st != PK_S_IDLE && st != PK_S_READY) r = PK_E_BUSY;
    else if (s->hw_busy) r = PK_E_BUSY;
    else {
        s->hw_busy = true;
        while (s->idle_active) pthread_cond_wait(&s->cv, &s->mu);    /* the idle status poll in progress ends first (a few ms); hw_busy now keeps new ones out */
    }
    pthread_mutex_unlock(&s->mu);
    return r;
}

/* A manual film move / eject: claims like pks_claim but does not wait for the idle poll and lets it keep running beside the move (see idle.c). */
static pk_status claim_film(pk_session *s) {
    if (!s) return PK_E_ARG;
    pk_status r = PK_OK;
    pthread_mutex_lock(&s->mu);
    pk_state st = pks_state(s);
    if (st != PK_S_IDLE && st != PK_S_READY) r = PK_E_BUSY;
    else if (s->hw_busy) r = PK_E_BUSY;
    else { s->hw_busy = true; s->film_manual = true; }
    pthread_mutex_unlock(&s->mu);
    return r;
}

void pks_release(pk_session *s) {
    pthread_mutex_lock(&s->mu);
    s->hw_busy = false;
    s->film_manual = false;
    pthread_mutex_unlock(&s->mu);
}

pk_status pk_session_film_move(pk_session *s, pk_film_dir dir, unsigned max_ms, int speed) {
    pk_status st = claim_film(s);
    if (st != PK_OK) return st;
    st = pk_film_move(s->b, dir, max_ms, speed);
    pks_release(s);
    return st;
}

pk_status pk_session_film_stop(pk_session *s) { return s ? pk_film_stop(s->b) : PK_E_ARG; }   /* any state; thread-safe against a running move */

pk_status pk_session_film_eject(pk_session *s) {
    pk_status st = claim_film(s);
    if (st != PK_OK) return st;
    st = pk_film_eject(s->b);
    pks_release(s);
    return st;
}

pk_status pk_session_leds_reset(pk_session *s) {
    pk_status st = pks_claim(s, true);
    if (st != PK_OK) return st;
    st = pk_leds_reset(s->b);
    pks_release(s);
    return st;
}

pk_status pk_session_lamp_set(pk_session *s, pk_lamp_level level) {
    pk_status st = pks_claim(s, true);
    if (st != PK_OK) return st;
    st = pk_lamp_set(s->b, level);
    pks_release(s);
    return st;
}

pk_status pk_session_guide_set(pk_session *s, pk_film_format f) {
    pk_status st = pks_claim(s, true);
    if (st != PK_OK) return st;
    st = pk_film_guide_set(s->b, f);
    pks_release(s);
    return st;
}

/* Read-only calls work in any state (S-R30 m3): the link serialises each exchange, and the boards guard the interrupt-pending mask and the
 * DX nibble cache with their own locks, so they may run beside the worker. */
/* While a scan runs the scan's own DX reader owns register 0x90 and the one-shot 0x02 events (RE 42 sec 9); a second reader would consume packets it never sees, so the sensors come
 * from the cache the reader keeps current (b->dx_nibble) and nothing goes on the bus. */
pk_status pk_session_film_sense(pk_session *s, pk_film_sensors *out) {
    if (!s || !out) return PK_E_ARG;
    pk_state st = pks_state(s);
    if (st != PK_S_SCANNING && st != PK_S_DRAINING) return pk_film_sense(s->b, out);
    pthread_mutex_lock(&s->b->nib_mu);
    int n = s->b->dx_nibble < 0 ? 0 : s->b->dx_nibble;
    pthread_mutex_unlock(&s->b->nib_mu);
    out->exit = (n & 0x10) != 0;
    out->entry = (n & 0x20) != 0;
    out->emulsion_down = (n & 0x40) != 0;
    out->tail_first = (n & 0x80) != 0;
    return PK_OK;
}
pk_status pk_session_guide_get(pk_session *s, pk_film_format *out) { return s ? pk_film_guide_get(s->b, out) : PK_E_ARG; }

void pk_session_opts_default(pk_session_opts *o) {
    if (!o) return;
    memset(o, 0, sizeof *o);
    o->leds_enabled = true;
    o->warmup_timeout_ms = PKS_DEFAULT_WARMUP_MS;
}

pk_status pk_session_rollers(pk_session *s, bool engage) {
    pk_status st = pks_claim(s, true);
    if (st != PK_OK) return st;
    st = pk_pressure_rollers(s->b, engage);
    pks_release(s);
    return st;
}

pk_status pk_session_lamp_saver(pk_session *s, unsigned standby_after_s, unsigned off_after_s) {
    pk_status st = pks_claim(s, true);
    if (st != PK_OK) return st;
    st = pk_lamp_saver(s->b, standby_after_s, off_after_s);
    pks_release(s);
    return st;
}

/* ------------------------------------------------------------------ calibration (Task 15) */
pk_status pks_marker_begin(pk_session *s) { return marker_write(s); }

/* TLB's ForceCorrections end (RE 43 row E1) and the session's own leave: the lamp out, the motor stopped, the LEDs off, the marker cleared once the motor stop and the lamp-off are
 * confirmed; the state goes back to IDLE (FAULTED when the scanner could not be put in a stopped state, or the failure was the hardware's). */
pk_status pks_sync_end(pk_session *s, pk_status run_status) {
    pks_set_state(s, PK_S_STOPPING);
    stopped r;
    STORE(s->keep_film_led, false);                              /* a calibration starts from film LED phase 0 (RE 42 sec 6 row 2): no remove-film hold survives it */
    pk_status lv = leave(s, &r);
    s->end_motor_done = s->end_lamp_done = false;
    s->keep_status_led = false;
    bool clear = (r.motor && r.lamp) || r.absent;
    if (clear) marker_remove(s);
    pks_set_state(s, clear && !is_hw_fault(run_status) ? PK_S_IDLE : PK_S_FAULTED);
    return lv;
}

/* The Calibrate calls take the boards (IDLE or READY, PK_E_BUSY otherwise), run on the calling thread, and give them back. pk_session_cancel stops them within a polling step. */
pk_status pk_calibrate(pk_session *s, const pk_cal_request *req, pk_events_cb cb, void *user, char out_id[65]) {
    if (out_id) out_id[0] = 0;
    if (!s || !req || !out_id) return PK_E_ARG;
    if (req->kind == PK_CAL_FOCUS) return PK_E_UNSUPPORTED;      /* F-235 / F-335 only; the session refuses those models (beta) */
    if (req->kind == PK_CAL_TRACK) return PK_E_ARG;              /* the Track test has its own call and nothing to store */
    if (req->kind != PK_CAL_SESSION && req->kind != PK_CAL_GAIN) return PK_E_ARG;
    if (!(req->dpi_base_mask & (PK_CAL_BASE_4 | PK_CAL_BASE_8 | PK_CAL_BASE_16)) || (req->dpi_base_mask & ~(PK_CAL_BASE_4 | PK_CAL_BASE_8 | PK_CAL_BASE_16))) return PK_E_ARG;
    if (req->film_colour_mask != 0 && req->film_colour_mask != PK_CAL_COLOUR_NEG) return PK_E_UNSUPPORTED;
    pk_status st = pks_claim(s, true);
    if (st != PK_OK) return st;
    s->cb = cb;
    s->cb_user = user;
    STORE(s->cancel, 0);
    s->last_keepalive_ms = 0;
    s->diag[0] = 0;
    bool lit = false;
    if ((st = marker_write(s)) == PK_OK) {                       /* before anything is lit or moved */
        pks_set_state(s, PK_S_WARMUP);
        lit = true;
        st = pks_cal_run(s, req, out_id);
    }
    pk_status end = PK_OK;
    if (lit) end = pks_sync_end(s, st);
    if (st != PK_OK && st != PK_E_CANCELLED) {
        pk_error e;
        pk_link_last_error_copy(s->link, &e);
        const char *ctx = s->diag[0] ? s->diag : e.context;
        pks_emit_msg(s, PK_EV_ERROR, st, 0, "%s%s%s", pk_status_str(st), ctx[0] ? ": " : "", ctx);
    }
    s->cb = NULL;
    s->cb_user = NULL;
    pks_release(s);
    return st != PK_OK ? st : end;
}

pk_status pk_track_test(pk_session *s, pk_film_format f, pk_track_result *out) {
    if (!s || !out) return PK_E_ARG;
    pk_status st = pks_claim(s, true);
    if (st != PK_OK) return st;
    STORE(s->cancel, 0);
    s->last_keepalive_ms = 0;
    if ((st = marker_write(s)) == PK_OK) {                       /* the motor runs: a dead process must be recoverable */
        st = pks_cal_track(s, f, out);
        stopped r;
        r.motor = r.lamp = r.absent = false;
        pk_status ms = pk_film_stop(s->b);                       /* idempotent: the test stopped the motor itself on every path that started it */
        r.motor = ms == PK_OK;
        r.absent = ms == PK_E_DISCONNECTED;
        if (marker_should_clear(&r)) marker_remove(s);
        if (st == PK_OK) st = ms;
    }
    pks_release(s);
    return st;
}

pk_status pk_session_set_cal_policy(pk_session *s, const pk_cal_policy *p) {
    if (!s) return PK_E_ARG;
    if (!p) { pk_cal_policy_default(&s->cal.policy); return PK_OK; }
    if (p->dark_point_interval_min < 1 || p->dark_point_interval_min > 525600u || p->full_search_after_h < 1 || p->full_search_after_h > 8760u) return PK_E_ARG;   /* PSI: 1..525600 min */
    pthread_mutex_lock(&s->mu);
    s->cal.policy = *p;
    pthread_mutex_unlock(&s->mu);
    return PK_OK;
}
