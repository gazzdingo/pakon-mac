#define _POSIX_C_SOURCE 200809L
/* The scan sequence (Task 13): TLB's order, from docs/re/41-scan-sequence.md (rows are cited as "row N" / "R/M/E" there). Ruling S-R31: where the spec or the
 * brief differ from TLB, TLB's order wins (owner rule: exact parity with Kodak PSI); the deviations are listed at the end of this comment and in the Task 13 report.
 *
 * Runs on the session worker, in state SCANNING with the lamp warm (session.c run()). Every loop calls pks_keepalive() (or pks_scan_poll(), which is the same
 * 0x02 read shared with the DX reader) and pks_cancelled(); the session runs session_leave after it returns, but the sequence ends the scan itself (TLB
 * FN_bEndScan: acquire off, lamp off, DX stop, motor stop) and tells leave so.
 *
 * Strip budget (C37, RE 41 M4, OBSERVED 0x10030a82..0x10030a90): when the strips counted by pk_scan_strip_budget are all done, TLB sets obj+0x4c = 0 and obj+0x40 = 1 and the
 * reader leaves its loop by the normal path: no error, no warning, film still in the transport is not scanned, the motor runs until EndScan's 0xA2. This file does the same
 * (the "M4" return in run_scan). Evidence tier OBSERVED (objdump of the reader thread).
 *
 * What the board sees, in order (base 16, non-IR, normal roll; * = a write that is skipped when the value is unchanged, as TLB's host-side shadows do):
 *   row 2   health gate (no traffic); row 3 forced status pass (HOST poll, light 0x02/0x06/0x90, motor 0x02/0x06) with the FilmInGuides refusal; row 4 HOST 0x84 = 2 + LIGHT 0x8A
 *   row 6-7 the calibration decision (Task 15 hook pks_cal_scan_due)
 *   row 9-11 FPGA index 0*, 6*, 4*, 5*, light 0x89*, AFE offsets 0x84 idx 5..7*, AFE gains idx 2..4*
 *   row 12  LIGHT 0x80* (3 for IR), 0x81*, 0x82* (the with-film set) and TLB's settle wait
 *   row 16  MOTOR 0xA5 speed, 0xA0 (does not wait)
 *   row 17-20 the bulk stream is armed
 *   row 21  FPGA index 0 = 0x0061 (0x0161 IR, 0x0063 base 4), then LIGHT 0x91 [S 00 01]
 *   R1-R7   status loop (HOST poll every PKS_SCAN_POLL_MS, board reads only on a host interrupt), film start / end from the image green mean, per-strip 0x91 re-send, end-of-strip 0x90 drain
 *   E2-E3   acquire off (0x0060); lamp off (pk_light_lamp_off); LIGHT 0x92 (+20 ms); MOTOR 0xA2
 * Deviations from TLB (each INFERRED to be harmless, each to be settled in HW-2): the zero-drive and the 0x83 read inside pk_light_lamp_off (RE 41 sec 4, U2); the status
 * loop runs at PKS_SCAN_POLL_MS = 1 ms like TLB's, but on this thread, with a 200 ms lamp-health read (0x83/0x84/0x88) added that TLB does not make; the LED writes are made
 * inline from this loop (the end-of-scan 0x4C hold is released by the session's idle status thread, idle.c, see end_scan); the first CCD write after a pk_boards is
 * v1's full sequence (pk_host_ccd_configure), not TLB's; `dx_branch` in the sidecar is OURS, not Kodak's (RE 42 sec 8): "dx", "sequential" or "manual". */
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "pakon/stream.h"
#include "session/session_internal.h"
#include "util/util.h"

/* ---------------------------------------------------------------- constants (TLB, RE 41) */
#define PKS_DETECT_FILM_G 54000u          /* DetectFilm_G, ColNeg: film starts when the green mean x4 falls below it (FUN_10010280; the owner's hive agrees) */
#define PKS_DETECT_WHITE_G 61000u         /* DetectWhite_G, ColNeg: film ends when the green mean x4 reaches it */
#define PKS_SENSE_SUM_LINES 3             /* iStack_60: the first three lines are summed for the rebase test (0x1002f550) */
#define PKS_REBASE_MARGIN 100u            /* White = sum / 3 - 100 */
#define PKS_DX_FORMAT_35MM 1u
#define PKS_PACKET_READY_MS 3000u         /* ScanPacketReadyTimeOut: TLB default and the owner's value (RE 41 row 22) */
#define PKS_SIDECAR_EVERY_MS 10000u       /* the sidecar is rewritten at least this often (C14) */
#define PKS_LINES_EVENT_MS 500u
#define PKS_SCAN_POLL_MS 1u               /* TLB's EventPollPPB wait while scanning (RE 42 sec 9) */
#define PKS_WAIT_FOR_LAMP_S 5.0           /* WaitForLamp_R/G/B (FUN_10010b60 default, the owner's hive) */
#define PKS_DX_STOP_SETTLE_MS 20u         /* TLB waits 20 ms under the board lock after 0x92 (FUN_10009da0) */

/* ---------------------------------------------------------------- film start / end from the image (R3, R4, R5, R6) */
/* The green mean x4 of one raw line, as the scan kernel FUN_100246d0 reports it in p8 (RE 30 sec 4.1: (sum_G x 4) / n_px, with G the corrected 14-bit value, so an empty gate
 * reads 64000). The kernel needs the calibration tables (Task 15) and is ported in Task 16; until then the tables are the identity: dark 0, gain unity (0x10000 >> 2), no smear,
 * where the corrected value is raw16 >> 2 (RE 30 sec 3.2). TODO(RE 41 R3, RE 30 UNRESOLVED 1): use the real corrected line. */
static uint32_t green_mean4(const uint8_t *line, unsigned n_px) {
    uint64_t sum = 0;
    for (unsigned p = 0; p < n_px; p++) {
        const uint8_t *w = line + ((size_t)p * 3 + 1) * 2;       /* channel order R, G, B per pixel (RE 04 stage 3) */
        sum += (unsigned)((w[0] | w[1] << 8) >> 2);
    }
    return (uint32_t)(sum * 4u / n_px);
}

typedef struct {
    pthread_mutex_t mu;
    unsigned segment;              /* the stream segment this strip reads (lines of any other are ignored) */
    unsigned n_px;
    bool armed;
    uint32_t film_thr, white_thr;  /* cfg+0x48, cfg+0x44 */
    int sum_left;
    uint64_t sum;
    int64_t budget;                /* iStack_cc: lines left */
    time_t deadline;
    bool started, ended, no_film, budget_hit;
    uint64_t start_line, start_off, end_line, end_off;
    unsigned wl_bytes;             /* bytes per line */
} detector;

static void det_begin(detector *d, unsigned segment, int64_t budget, unsigned no_film_s) {
    pthread_mutex_lock(&d->mu);
    d->segment = segment;
    d->armed = true;
    d->film_thr = PKS_DETECT_FILM_G;
    d->white_thr = PKS_DETECT_WHITE_G;
    d->sum_left = PKS_SENSE_SUM_LINES;
    d->sum = 0;
    d->budget = budget;
    d->deadline = time(NULL) + (time_t)no_film_s;     /* iStack_c = NoFilmTimeOut + _time32() */
    d->started = d->ended = d->no_film = d->budget_hit = false;
    pthread_mutex_unlock(&d->mu);
}

/* The reader's per-line test, 0x1002f550 lines 552-640 of the archived decompile (RE 41 R3-R6), SenseFilm on:
 *  - not started: the first three lines' green means are summed; on the third, if that line's mean is above the film threshold, White = sum / 3 - 100 and Film moves by the
 *    same amount; then the line starts the film if its mean is below the Film threshold (the start line counts against the budget); otherwise, if the deadline has passed,
 *    the strip ends with no film (strip 0 is an error, later strips a normal end).
 *  - started: the budget drops by one; at zero the strip ends with MAX_FILM_LENGTH_EXCEEDED; else it ends when the mean reaches White. The ending line belongs to the strip. */
static void det_line(void *user, unsigned seg, uint64_t line, uint64_t off, const uint8_t *data) {
    detector *d = (detector *)user;
    pthread_mutex_lock(&d->mu);
    if (!d->armed || seg != d->segment || d->ended) { pthread_mutex_unlock(&d->mu); return; }
    uint32_t a0 = green_mean4(data, d->n_px);
    if (!d->started) {
        if (d->sum_left > 0) {
            d->sum_left--;
            d->sum += a0;
            if (d->sum_left == 0 && d->film_thr < a0) {
                uint32_t diff = d->white_thr - d->film_thr;
                d->white_thr = (uint32_t)(d->sum / PKS_SENSE_SUM_LINES) - PKS_REBASE_MARGIN;
                d->film_thr = d->white_thr - diff;
            }
        }
        if (a0 < d->film_thr) {
            d->started = true;
            d->sum_left = 0;
            d->start_line = line;
            d->start_off = off;
            d->end_line = line;
            d->end_off = off + d->wl_bytes;
            d->budget--;
        } else if (time(NULL) >= d->deadline) {
            d->no_film = true;
            d->ended = true;
        }
    } else {
        /* TLB (archive scan decompile 607-650): the stop flag (bVar5) is set before the hi-res write pointer and the hand-off counter advance, so the ENDING line (the
         * budget running out, or the mean reaching White) is fed to the kernel but is not a hi-res line of the strip: it stays out of line_end / byte_end (S-R44). */
        d->budget--;
        if (d->budget == 0) { d->budget_hit = true; d->ended = true; }
        else if (a0 >= d->white_thr) d->ended = true;
        if (!d->ended) { d->end_line = line; d->end_off = off + d->wl_bytes; }
    }
    pthread_mutex_unlock(&d->mu);
}

typedef struct { bool started, ended, no_film, budget_hit; uint64_t start_line, start_off, end_line, end_off; time_t deadline; } det_snap;
static det_snap det_get(detector *d) {
    det_snap r;
    pthread_mutex_lock(&d->mu);
    r.started = d->started; r.ended = d->ended; r.no_film = d->no_film; r.budget_hit = d->budget_hit;
    r.start_line = d->start_line; r.start_off = d->start_off; r.end_line = d->end_line; r.end_off = d->end_off; r.deadline = d->deadline;
    pthread_mutex_unlock(&d->mu);
    return r;
}

/* The no-film deadline checked by the worker as well (not only on a line of the right segment): a strip with no film in time ends, whatever the lines do (review m8). */
static void det_check_deadline(detector *d) {
    pthread_mutex_lock(&d->mu);
    if (d->armed && !d->started && !d->ended && time(NULL) >= d->deadline) { d->no_film = true; d->ended = true; }
    pthread_mutex_unlock(&d->mu);
}

/* ---------------------------------------------------------------- the scan object */
typedef struct {
    pk_session *s;
    pk_boards *b;
    const pk_scan_config *cfg;
    pk_cal_light light;
    pk_ccd_cfg ccd;
    unsigned strips_max, lines_per_strip, words_per_line;
    char raw_path[PKS_PATH_MAX + 8], json_path[PKS_PATH_MAX + 8];
    pk_sidecar *sc;
    pk_stream *st;
    detector det;
    pk_dx *dx;
    unsigned strip, segment;       /* the strip being scanned; the stream segment it reads */
    bool motor_started, acquiring, dx_started, strip_open;   /* strip_open: film has started in this strip and it is not finished */
    unsigned long long last_write_ms, last_lines_ms, bytes_ms;
    uint64_t last_bytes;
    uint32_t last_status_word;
    uint32_t sw;                   /* the DX status word, kept across the per-strip DX objects (TLB's lives in the scanner status word)  */
    unsigned host_rep;             /* host status bits already reported */
    bool overflow_rep;
    unsigned strips_done;
    unsigned limit_mask;           /* strips that hit the film-length limit (bit = strip index) */
    int led_cur, led_want;         /* film LED phase 0..3 (RE 42 sec 6); -1 = unknown */
    char err[160];
    pk_status stop_st;             /* what pk_stream_stop reported */
} scan_t;

static void set_err(scan_t *x, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void set_err(scan_t *x, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(x->err, sizeof x->err, fmt, ap);
    va_end(ap);
}

static unsigned base_idx(int dpi_base) { return dpi_base == 4 ? 0u : dpi_base == 8 ? 1u : 2u; }

static unsigned hist_slot(const pk_scan_config *c) {
    return ((base_idx(c->dpi_base) * 2u + ((c->scan_control & PK_SC_HAS_FILM_DRAG) ? 1u : 0u)) * 2u + (c->ir ? 1u : 0u)) * 2u + (c->film_format == PK_FILM_24MM ? 1u : 0u);
}

/* MotorAdjust (or MotorAdjustDrag) x MotorSpeedPlus (or _Ir) / 1000 (RE 41 row 16, RE 42 sec 1.1): the owner's registry gives MotorAdjust 1000 / Drag 1008 at every base, and
 * MotorSpeedPlus 25802 / 11467 / 5917 (IR 19335 / 7580 / 4850) at base 4 / 8 / 16. */
static unsigned motor_register(const pk_model *m, const pk_scan_config *c) {
    (void)m;      /* film_speed is validated to 0 (S-R35): there is no caller speed */
    static const unsigned long long PLUS[2][3] = { { 25802u, 11467u, 5917u }, { 19335u, 7580u, 4850u } };
    unsigned long long adjust = (c->scan_control & PK_SC_HAS_FILM_DRAG) ? 1008u : 1000u;
    return (unsigned)(adjust * PLUS[c->ir ? 1 : 0][base_idx(c->dpi_base)] / 1000u);
}

/* The DX reader's S argument PB+0xac / PB+0xb0 (RE 42 sec 1.1, 1.2): computed by TLB from the integration, never read from the registry. */
unsigned pks_dx_speed(int dpi_base, bool ir) {
    static const unsigned S[2][3] = { { 263u, 117u, 60u }, { 197u, 77u, 49u } };
    return S[ir ? 1 : 0][base_idx(dpi_base)];
}
static unsigned dx_speed(const pk_scan_config *c) { return pks_dx_speed(c->dpi_base, c->ir); }

pk_status pks_scan_supported(const pk_model *m, const pk_scan_config *c, char *why, size_t cap) {
    const char *r = NULL;
    if (m->id != PK_MODEL_F135_PLUS) r = "the scan sequence is derived for the F-135 Plus only (the F-135's base board has no derived motor speed or integration)";
    else if (c->scan_control & PK_SC_PRESCAN) r = "prescan is not supported (RE 42 sec 3)";
    else if (c->film_format != PK_FILM_35MM) r = "24 mm film is not supported on the F-135 Plus";
    if (!r) return PK_OK;
    if (why && cap) snprintf(why, cap, "%s", r);
    return PK_E_UNSUPPORTED;
}

/* ---------------------------------------------------------------- LEDs (RE 42 sec 6) */
/* The film LED phases: 0 = 0x40, 1 film found = 0x42, 2 scanning = 0x48, 3 remove film = 0x4C (FUN_1000C420). From phase 3 the change to 0 is held while either sensor is covered, the
 * change to 2 while the exit sensor is covered. Writes are change-only (pk_led_set). An LED write that fails is a side effect, not a scan failure (review m10): only a lost scanner is. */
static uint32_t cur_sw(scan_t *x) {
    if (x->dx) {
        /* The sensor bits come from the first record of a packet with N >= 1 (RE 33 sec 4), so a fresh strip object reads 0 until its first record, not its first packet
         * (about 1 % of packets carry none): the old word stands until then (r-m1, r2-m1). */
        uint32_t tc[16], n = 0;
        pk_dx_record_counts(x->dx, tc);
        for (int i = 0; i < 16; i++) n += tc[i];
        if (n) x->sw = pk_dx_status_word(x->dx);
    }
    return x->sw;
}

static pk_status led_apply(scan_t *x) {
    static const pk_filmled PH[4] = { PK_FILMLED_OFF, PK_FILMLED_FOUND, PK_FILMLED_WAITING, PK_FILMLED_REMOVE };
    if (x->led_want < 0 || x->led_want == x->led_cur) return PK_OK;
    uint32_t sw = cur_sw(x);
    if (x->led_cur == 3 && x->led_want == 0 && (sw & 0xC0000000u)) return PK_OK;
    if (x->led_cur == 3 && x->led_want == 2 && (sw & 0x80000000u)) return PK_OK;
    pk_status st = pk_film_led(x->b, PH[x->led_want]);
    if (st == PK_OK) x->led_cur = x->led_want;
    return pkb_status_is_final(st) ? st : PK_OK;
}
static pk_status led_phase(scan_t *x, int phase) { x->led_want = phase; return led_apply(x); }
static pk_status led_status(scan_t *x, unsigned code) {
    pk_status st = pk_led_set(x->b, PK_LED_STATUS, code);
    return pkb_status_is_final(st) ? st : PK_OK;
}

/* ---------------------------------------------------------------- sidecar */
static void utc_now(char out[32]) {
    time_t t = time(NULL);
    struct tm tmv;
    gmtime_r(&t, &tmv);
    strftime(out, 32, "%Y-%m-%dT%H:%M:%SZ", &tmv);
}

/* One strip object. A finished strip carries its DX result; the strip in progress (partial) carries what is known so far: line_start once film has started, the DX packets so far,
 * ended_by "incomplete" (review I-3: a kill -9, a cancel or an error leaves it for Task 20). */
static pk_status strip_obj(scan_t *x, const det_snap *d, bool partial, const pk_dx_strip *res, const char *source, const char *branch, unsigned scanw,
                           const unsigned *bits, unsigned nb, char **out) {
    pku_jw *w = pku_jw_new();
    if (!w) return PK_E_NOMEM;
    pku_jw_obj_begin(w);
    pku_jw_key(w, "index"); pku_jw_uint(w, x->strips_done);
    pku_jw_key(w, "segment"); pku_jw_uint(w, x->segment);
    pku_jw_key(w, "product"); pku_jw_int(w, res ? res->product : -1);
    pku_jw_key(w, "specifier"); pku_jw_int(w, res ? res->specifier : -1);
    pku_jw_key(w, "dx_source"); pku_jw_str(w, source);
    pku_jw_key(w, "dx_branch"); pku_jw_str(w, branch);       /* OURS, not Kodak's (RE 42 sec 8) */
    pku_jw_key(w, "good_frame_marks"); pku_jw_int(w, res ? res->good_count : 0);
    pku_jw_key(w, "tail_first"); pku_jw_bool(w, res ? res->tail_first : false);
    pku_jw_key(w, "scanw"); pku_jw_uint(w, scanw);
    pku_jw_key(w, "warnings");
    pku_jw_arr_begin(w);
    for (unsigned i = 0; i < nb; i++) pku_jw_uint(w, bits[i]);
    pku_jw_arr_end(w);
    pku_jw_key(w, "line_start"); if (d->started) pku_jw_uint(w, d->start_line); else pku_jw_null(w);
    pku_jw_key(w, "line_end"); pku_jw_uint(w, d->end_line);
    uint64_t sg_off = 0, sg_line = 0;     /* the segment's first synced line from the stream (S-R44): where TLB's loop head initialises the kernel; line_start is where film was detected */
    const bool sg = d->started && x->st && pk_stream_segment_start(x->st, x->segment, &sg_off, &sg_line) == PK_OK;
    pku_jw_key(w, "segment_line_start"); if (sg) pku_jw_uint(w, sg_line); else pku_jw_null(w);
    pku_jw_key(w, "segment_byte_start"); if (sg) pku_jw_uint(w, sg_off); else pku_jw_null(w);
    pku_jw_key(w, "byte_start"); if (d->started) pku_jw_uint(w, d->start_off); else pku_jw_null(w);
    pku_jw_key(w, "byte_end"); pku_jw_uint(w, d->end_off);
    pku_jw_key(w, "ended_by"); pku_jw_str(w, partial ? "incomplete" : d->budget_hit ? "max_film_length" : "film_end");
    size_t np = 0;
    bool trunc = false;
    const uint8_t *pk = pk_dx_logged_packets(x->dx, &np, &trunc);
    pku_jw_key(w, "dx_packets_truncated"); pku_jw_bool(w, trunc);
    pku_jw_key(w, "dx_packets");
    pku_jw_arr_begin(w);
    for (size_t i = 0; i < np; i++) {
        char b64[48];
        pku_b64_encode(pk + i * PK_DX_PACKET_LEN, PK_DX_PACKET_LEN, b64, sizeof b64);
        pku_jw_str(w, b64);
    }
    pku_jw_arr_end(w);
    pku_jw_obj_end(w);
    size_t n = 0;
    const char *txt = pku_jw_finish(w, &n);
    char *copy = txt ? (char *)malloc(n + 1) : NULL;
    if (copy) { memcpy(copy, txt, n); copy[n] = 0; }
    pku_jw_free(w);
    if (!copy) return PK_E_NOMEM;
    *out = copy;
    return PK_OK;
}

static pk_status sidecar_flush(scan_t *x) {
    uint64_t bytes = 0, lines = 0;
    pk_status st;
    if (x->st) {
        (void)pk_stream_poll(x->st, &bytes, &lines);
        pk_sidecar_set_int(x->sc, "line_count", (long long)lines);
        pk_sidecar_set_int(x->sc, "raw_bytes", (long long)bytes);
    }
    pk_sidecar_set_int(x->sc, "host_status_bits", (long long)x->s->host_unknown);     /* HOST status bits TLB does not test (e.g. 0x20), seen during the run */
    pk_sidecar_set_bool(x->sc, "host_fifo_overflow", x->s->host_overflow);
    /* the strip in progress: rewritten at every flush while film is in it, dropped when there is none (I-3) */
    pk_sidecar_truncate_strips(x->sc, x->strips_done);
    if (x->strip_open && x->dx) {
        det_snap d = det_get(&x->det);
        if (d.started) {
            char *js = NULL;
            st = strip_obj(x, &d, true, NULL, "none", "sequential", 0, NULL, 0, &js);
            if (st != PK_OK) return st;
            st = pk_sidecar_set_strip_json(x->sc, x->strips_done, js);
            free(js);
            if (st != PK_OK) return st;
        }
    }
    x->last_write_ms = pkb_now_ms();
    return pk_sidecar_write(x->sc, x->json_path);
}

/* calibration_ids: the ids are built, not printed, so a store id with a quote cannot break the JSON (m5). Rewritten when a calibration runs inside the scan (Task 15). */
static pk_status sidecar_ids(scan_t *x) {
    pku_jw *w = pku_jw_new();
    if (!w) return PK_E_NOMEM;
    pku_jw_arr_begin(w);
    if (x->s->cal_id[0]) pku_jw_str(w, x->s->cal_id);
    pku_jw_arr_end(w);
    size_t n = 0;
    const char *ids = pku_jw_finish(w, &n);
    pk_status st = ids ? pk_sidecar_set_json(x->sc, "calibration_ids", ids) : PK_E_NOMEM;
    pku_jw_free(w);
    return st;
}

static pk_status sidecar_open(scan_t *x) {
    x->sc = pk_sidecar_new();
    if (!x->sc) return PK_E_NOMEM;
    char ts[32];
    utc_now(ts);
    char *cfgjson = NULL;
    pk_status st = pk_scan_config_to_json(x->cfg, &cfgjson);
    if (st != PK_OK) return st;
    pk_sidecar *sc = x->sc;
    st = pk_sidecar_set_str(sc, "model", x->s->model->name);
    if (st == PK_OK) st = pk_sidecar_set_str(sc, "started_utc", ts);
    if (st == PK_OK) st = pk_sidecar_set_str(sc, "ended_utc", NULL);
    if (st == PK_OK) st = pk_sidecar_set_int(sc, "dpi_base", x->cfg->dpi_base);
    if (st == PK_OK) st = pk_sidecar_set_int(sc, "channels", x->cfg->ir ? 4 : 3);
    if (st == PK_OK) st = pk_sidecar_set_int(sc, "words_per_line", x->words_per_line);
    if (st == PK_OK) st = pk_sidecar_set_str(sc, "pin_mode", x->cfg->calibration_pin);
    if (st == PK_OK) st = sidecar_ids(x);
    if (st == PK_OK) st = pk_sidecar_set_json(sc, "scan_config", cfgjson);
    if (st == PK_OK) st = pk_sidecar_set_int(sc, "line_count", 0);
    if (st == PK_OK) st = pk_sidecar_set_int(sc, "raw_bytes", 0);
    if (st == PK_OK) st = pk_sidecar_set_bool(sc, "complete", false);
    if (st == PK_OK) st = pk_sidecar_set_str(sc, "error", NULL);
    free(cfgjson);
    if (st != PK_OK) return st;
    return sidecar_flush(x);
}

static void emit_warning(scan_t *x, unsigned strip, unsigned bit) {
    pk_warning_text t = pk_warning_sentence_for(x->s->model, bit);
    pks_emit_msg(x->s, PK_EV_WARNING, PK_OK, bit, "strip %u: warning 0x%X", strip, bit);   /* the event text is short (96 bytes); the app looks the sentence up by code */
    char ev[240];
    snprintf(ev, sizeof ev, "strip %u warning 0x%X (PSI string %u): %s", strip, bit, t.psi_string_id, t.english);
    pk_sidecar_add_event(x->sc, ev);
}

/* ---------------------------------------------------------------- DX object per strip */
static pk_status dx_new_strip(scan_t *x) {
    pk_dx_geometry g;
    pk_status st = pk_dx_geometry_for(x->cfg->dpi_base, x->cfg->ir, &g);
    if (st != PK_OK) return st;
    g.single_strip = x->strips_max == 1;                 /* FN_bEndScan passes (strips == 1) as the speed-analysis flag */
    st = pk_dx_new_geometry(&g, &x->dx);
    if (st != PK_OK) return st;
    pk_dx_attach_speed_history(x->dx, &x->s->speed_hist[hist_slot(x->cfg)]);
    pk_dx_log_packets(x->dx, true);
    return PK_OK;
}

/* ---------------------------------------------------------------- one strip's end: R7 drain, hand-off, warnings, sidecar */
static pk_status strip_finish(scan_t *x, const det_snap *d) {
    pk_boards *b = x->b;
    uint8_t nib = 0;
    pk_status st = pk_dx_drain(b, x->dx, &nib);          /* R7: one eventless 0x02 read, 0x90 only if its value flags DX */
    if (st != PK_OK) return st;
    pk_dx_strip res;
    st = pk_dx_finish_strip(x->dx, true, &res);
    if (st != PK_OK) return st;
    const char *source = res.dx_source;
    if (res.product < 0 && x->cfg->manual_product >= 0) {   /* a strip with no DX read takes the caller's product (manual_product / manual_specifier) */
        res.product = x->cfg->manual_product;
        res.specifier = x->cfg->manual_specifier;
        source = "manual";
    }
    unsigned scanw = res.scanw;
    if (d->budget_hit) { scanw |= PK_SCANW_MAX_FILM_LENGTH_EXCEEDED; x->limit_mask |= 1u << x->strips_done; }
    if (x->strips_done == 0 && x->light.low_light) scanw |= PK_SCANW_LIGHT_DIM;      /* EndScan, first strip only (S+0x304) */
    unsigned bits[16], nb = 0;
    for (unsigned bit = 1; bit <= PK_SCANW_LIGHT_DIM; bit <<= 1) if (scanw & bit) bits[nb++] = bit;
    /* PSI status-word warnings (RE 42 sec 7.2): the F-135 and Plus show string 39 for the emulsion bit and 37 for tail first. */
    if (res.status_bit40_seen) bits[nb++] = PK_WARN_PSI_EMULSION_DOWN;
    if (res.tail_first) bits[nb++] = PK_WARN_PSI_TAIL_FIRST;
    const char *branch = !strcmp(source, "manual") ? "manual" : (res.product >= 0 && res.good_count > 0) ? "dx" : "sequential";   /* ours, not Kodak's (RE 42 sec 8) */
    char *js = NULL;
    st = strip_obj(x, d, false, &res, source, branch, scanw, bits, nb, &js);
    if (st != PK_OK) return st;
    st = pk_sidecar_set_strip_json(x->sc, x->strips_done, js);       /* replaces the partial strip the flushes kept */
    free(js);
    if (st != PK_OK) return st;
    /* 0x1000 is PSI's message only when the roll's strip count is not 1 (RE 42 sec 7.2): it is raised once the roll is over, from limit_mask. */
    for (unsigned i = 0; i < nb; i++)
        if (bits[i] != PK_SCANW_MAX_FILM_LENGTH_EXCEEDED) emit_warning(x, x->strips_done, bits[i]);
    pks_emit_msg(x->s, PK_EV_DX, PK_OK, (uint32_t)(res.product < 0 ? 0xFFFFu : (unsigned)res.product), "strip %u: product %d specifier %d, %d frame marks, source %s",
                 x->strips_done, res.product, res.specifier, res.good_count, source);
    x->strips_done++;
    x->strip_open = false;
    return sidecar_flush(x);
}

/* ---------------------------------------------------------------- lamp: row 12 */
static pk_status lamp_settle(scan_t *x, const uint16_t lv[4], const uint16_t on[4], unsigned period, bool had_lv, bool had_duty,
                             const uint16_t old_lv[4], const uint16_t old_on[4], unsigned old_period) {
    /* FUN_1002C5F0 (RE 41 row 12, RE 42 sec 2): T = max over the lit channels of
     *   channel newly enabled: Current_c / max_c x WaitForLamp x duty_c
     *   otherwise:             (rising current) / max_c x WaitForLamp x (rising duty)
     * with max_c = 4, 20, 20 ('D' board, IR off) or 8, 24, 24, 8 (IR on). "Enabled" is read as a previous on-count of zero (INFERRED); with no shadow the lamp is treated as newly enabled. */
    static const double MAX_RGB[4] = { 4.0, 20.0, 20.0, 0.0 }, MAX_IR[4] = { 8.0, 24.0, 24.0, 8.0 };
    const double *maxc = x->cfg->ir ? MAX_IR : MAX_RGB;
    int nch = x->cfg->ir ? 4 : 3;
    double T = 0.0;
    for (int c = 0; c < nch; c++) {
        double dnew = (double)on[c] / (double)period, t;
        bool fresh = !had_lv || !had_duty || old_on[c] == 0 || old_period == 0;
        if (fresh) t = (double)lv[c] / maxc[c] * PKS_WAIT_FOR_LAMP_S * dnew;
        else {
            double dc = (double)lv[c] - (double)old_lv[c], dd = dnew - (double)old_on[c] / (double)old_period;
            t = (dc > 0 ? dc : 0.0) / maxc[c] * PKS_WAIT_FOR_LAMP_S * (dd > 0 ? dd : 0.0);
        }
        if (t > T) T = t;
    }
    unsigned long long end = pkb_now_ms() + (unsigned long long)(1000.0 * T);
    while (pkb_now_ms() < end) {
        if (pks_cancelled(x->s)) return PK_E_CANCELLED;
        pk_status st = pks_keepalive(x->s);
        if (st != PK_OK) return st;
        pkb_sleep_ms(PKS_SCAN_POLL_MS * 10);
    }
    return PK_OK;
}

static pk_status lamp_for_scan(scan_t *x) {
    pk_boards *b = x->b;
    pk_status st;
    bool ir = x->cfg->ir;
    uint8_t want = (uint8_t)(1 | (ir ? 2 : 0));                                      /* 0x80 = (on) | (ir << 1) */
    if (b->lamp_mask != want && (st = pk_light_lamp_on(b, true, ir)) != PK_OK) return st;   /* only if it differs from what is written (TLB's shadow rule) */
    uint16_t lv[4] = { 0, 0, 0, 0 }, on[4] = { 0, 0, 0, 0 };
    for (int i = 0; i < 3; i++) { lv[i] = (uint16_t)x->light.current[i]; on[i] = x->ccd.on_counts[i]; }
    if (ir) {                                                                         /* the IR duty is forced to 0 when IR is off (FUN_1002C5F0) */
        lv[3] = (uint16_t)x->light.current[3];
        on[3] = (uint16_t)pkb_duty_on_count(x->ccd.lamp_period, x->light.duty_film[3]);
    }
    uint16_t period = x->ccd.lamp_period;
    bool had_lv = b->lamp_lv_known, had_duty = b->lamp_duty_known;
    uint16_t old_lv[4], old_on[4], old_period = b->lamp_period;
    memcpy(old_lv, b->lamp_lv, sizeof old_lv);
    memcpy(old_on, b->lamp_on_cnt, sizeof old_on);
    if ((!had_lv || memcmp(old_lv, lv, sizeof lv)) && (st = pk_light_set_levels(b, lv)) != PK_OK) return st;                        /* 0x81 if a current changed */
    if ((!had_duty || old_period != period || memcmp(old_on, on, sizeof on)) && (st = pk_light_set_duty(b, on, period)) != PK_OK) return st;   /* 0x82 if a duty changed */
    return lamp_settle(x, lv, on, period, had_lv, had_duty, old_lv, old_on, old_period);
}

/* ---------------------------------------------------------------- end of scan: E2, E3 */
/* TLB FN_bEndScan (RE 41 E2-E3): acquire off; lamp off; DX stop (+20 ms); motor stop. Each step is tried even if an earlier one failed. The lamp-off is pk_light_lamp_off
 * (zero-drive first, then TLB's 0x80 = 0, HOST 0x84 / LIGHT 0x8A, and the 0x83 confirmation): a documented deviation (RE 41 sec 4). The tail sets the film LED phase 0
 * (0x40), held at 0x4C while either sensor is covered (RE 42 sec 6 step 8). TLB's status thread releases that hold when the film clears: here the session's idle status thread does (idle.c),
 * and the held LED is kept lit through the session's leave (s->keep_film_led) until it is released, the next scan starts, or the session closes. */
static pk_status end_scan(scan_t *x) {
    pk_boards *b = x->b;
    pk_status first = PK_OK, st;
    if (x->acquiring && (st = pk_host_acquire(b, false)) != PK_OK && first == PK_OK) first = st;    /* E2: FPGA index 0 = 0x0060 */
    x->acquiring = false;
    if (x->st) {                                                                                    /* the driver ring is cancelled and joined; the raw file is complete */
        pks_set_state(x->s, PK_S_DRAINING);
        x->stop_st = pk_stream_stop(x->st, NULL);
    }
    st = pk_light_lamp_off(b);                                                                      /* E3 steps 1-3 */
    x->s->end_lamp_done = st == PK_OK;
    if (st != PK_OK && first == PK_OK) first = st;
    st = pk_dx_stop(b);                                                                             /* step 4: 0x92 */
    if (st != PK_OK && first == PK_OK) first = st;
    pkb_sleep_ms(PKS_DX_STOP_SETTLE_MS);
    x->dx_started = false;
    st = pk_film_stop(b);                                                                           /* step 5: 0xA2 */
    x->s->end_motor_done = st == PK_OK;
    if (st != PK_OK && first == PK_OK) first = st;
    x->motor_started = false;
    if (x->led_cur >= 0 && !x->s->keep_film_led) {                                                  /* the tail: phase 0, change-only, held while film covers a sensor */
        bool held = x->led_cur == 3 && (cur_sw(x) & 0xC0000000u) != 0;                              /* the hysteresis will keep 0x4C: only then is there a hold (a failed write is not one) */
        (void)led_phase(x, 0);
        if (held && x->led_cur == 3) pks_hold_film_led(x->s);
    }
    return first;
}

/* ---------------------------------------------------------------- the run */
static void snapshot_progress(scan_t *x, unsigned long long now) {
    if (now - x->last_lines_ms < PKS_LINES_EVENT_MS) return;
    x->last_lines_ms = now;
    uint64_t bytes, lines;
    if (pk_stream_poll(x->st, &bytes, &lines) == PK_E_ARG) return;
    pk_event e;
    memset(&e, 0, sizeof e);
    e.kind = PK_EV_LINES;
    e.state = pks_state(x->s);
    e.lines = lines;
    pks_emit(x->s, &e);
}

/* Row 3, TLB's forced status pass (RE 42 sec 5, FUN_1000BDD0 forced): the sticky warning bits are dropped, then HOST status (not tested), LIGHT 0x02 (+0x06), LIGHT 0x90, the forced
 * lamp judgement, MOTOR 0x02 (+0x06). The 0x90 packet goes to a DX reader in TLB's calibration state 3, which flags film over either sensor; with
 * RequireDxSensorsDuringLightCalibration (default 1) and the wizard flag clear that refuses the scan: EC_FilmInGuides 0x81 (PSI string 6 or 4). */
static pk_status forced_pass(scan_t *x) {
    pk_boards *b = x->b;
    pk_dx *probe = NULL;
    pk_status st = pk_dx_new(&probe);
    if (st != PK_OK) return st;
    const pk_dx_calibration cal = { true, true, false };
    pk_dx_set_calibration(probe, &cal);
    b->sticky &= PK_LIGHT_F_FAULT | PK_LIGHT_F_LAMP_FAULT | PK_LIGHT_F_MAIN_FAULT | PK_LIGHT_F_STATUS0;   /* status &= 0xC40548C0 */
    uint8_t hs = 0, nib = 0;
    uint32_t taken = 0;
    if ((st = pk_host_status(b, &hs)) == PK_OK && (st = pkb_irq_take_ex(b, 0x5Bu | 0xA4u, &taken, NULL, NULL)) == PK_OK &&
        (st = pk_dx_read_packet(b, probe, &nib)) == PK_OK && (st = pkb_lamp_monitor(b, taken & 0x5Bu, true, NULL)) == PK_OK &&
        (st = pk_host_status(b, &hs)) == PK_OK)                    /* TLB reads HOST status before each board (RE 42 sec 5) */
        st = pk_motor_irq_service(b, NULL);
    bool film = pk_dx_calibration_abort(probe);
    pk_dx_free(probe);
    if (st != PK_OK) return st;
    if (film) {
        (void)led_status(x, 4);                                    /* status 4, film LED phase 3 (0x4C): "remove film" */
        (void)led_phase(x, 3);
        if (x->led_cur == 3) pks_hold_film_led(x->s);                                                /* only if the 0x4C write really went out */
        x->s->keep_status_led = true;
        set_err(x, "film is over the scanner's entry or exit sensor: remove the film from the exit path first, then the entrance path (PSI string 6 or 4)");
        return PK_E_FILM_IN_GUIDES;
    }
    if ((st = led_status(x, 2)) != PK_OK) return st;               /* ready, phase 0 */
    return led_phase(x, 0);
}

/* The part of the scan from the status pass to the end of the last strip. Returns PK_OK when the roll ended normally (film end of the last strip, the strip budget, or the
 * no-film wait after at least one strip), else the failure. Anything it started is stopped by end_scan(). */
static pk_status run_scan(scan_t *x, bool *roll_ok) {
    pk_session *s = x->s;
    pk_boards *b = x->b;
    pk_status st;
    *roll_ok = false;
    /* (rows 2 and 3 run before the sidecar is opened, in pks_scan_sequence: a refusal leaves no roll files) */
    /* row 4: ResetFifos (HOST 0x84 = 2, LIGHT 0x8A) */
    if ((st = pk_host_fifo_reset(b)) != PK_OK) return st;
    /* rows 6-7: the calibration decision. Task 15 measures here when TLB's rule says it is due, and may replace the light settings. */
    /* An in-scan calibration brackets itself with LIGHT 0x91 ... 0x92 (cal.c). The 0x92 at its end is OURS (RE 41 row 7 lists none; the scan sends its own 0x91 later): S-R40 I-4. */
    if ((st = pks_cal_scan_due(s, x->cfg, &s->light, s->cal_id)) != PK_OK) return st;
    x->light = s->light;
    if ((st = sidecar_ids(x)) != PK_OK) return st;                        /* a calibration that ran here is the one this roll is scanned with */
    if (pks_cancelled(s)) return PK_E_CANCELLED;
    /* rows 9-11: the window, then the AFE offsets and gains (changed values only) */
    if ((st = pkb_ccd_cfg_from(s->model, &x->light, x->cfg->dpi_base, &x->ccd)) != PK_OK) return st;
    if ((st = pk_host_ccd_update(b, &x->ccd)) != PK_OK) return st;
    /* row 12: the with-film lamp set and the settle wait */
    if ((st = lamp_for_scan(x)) != PK_OK) return st;
    if (pks_cancelled(s)) return PK_E_CANCELLED;
    /* rows 14-15: the strip budget (computed by the caller) and the DX object of strip 0 */
    if ((st = dx_new_strip(x)) != PK_OK) return st;
    /* row 16: the motor starts now and does not wait. Row 18: status LED colour 8 and film LED phase 2 (scanning, 0x48). */
    if ((st = pk_film_start_register(b, PK_FILM_FORWARD, motor_register(s->model, x->cfg))) != PK_OK) return st;
    x->motor_started = true;
    if ((st = led_status(x, 8)) != PK_OK) return st;
    if ((st = led_phase(x, 2)) != PK_OK) return st;
    /* rows 17-20: the stream is armed before acquisition starts */
    x->det.n_px = x->words_per_line / (x->cfg->ir ? 4u : 3u);
    x->det.wl_bytes = x->words_per_line * 2u;
    x->segment = 0;
    det_begin(&x->det, 0, x->lines_per_strip, x->cfg->no_film_timeout_s);       /* armed BEFORE the stream starts: the threshold window counts from the strip's loop head, as TLB's does (S-R44 n3) */
    pk_stream_cfg sc = { 0, x->words_per_line, x->raw_path, 0, det_line, &x->det, PK_STREAM_STRIP0_SKIP_WORDS, false };   /* strip 0 searches from the third ring packet (RE 30 sec 2.2.1) */
    if ((st = pk_stream_start(s->t, &sc, &x->st)) != PK_OK) return st;
    /* row 21: acquire on (skipped when the FPGA already acquires), then LIGHT 0x91 */
    if (!(b->fpga_ctrl >= 0 && (b->fpga_ctrl & 1))) {
        if ((st = pk_host_acquire(b, true)) != PK_OK) return st;
    }
    x->acquiring = true;
    if ((st = pk_dx_start(b, dx_speed(x->cfg), PKS_DX_FORMAT_35MM)) != PK_OK) return st;
    x->dx_started = true;
    /* row 22: strip 0 begins (no-film deadline, film detection) */
    unsigned long long t0 = pkb_now_ms();
    x->bytes_ms = t0;
    x->last_write_ms = t0;
    x->last_lines_ms = t0;
    x->last_bytes = 0;
    s->last_keepalive_ms = 0;
    for (;;) {
        if (pks_cancelled(s)) return PK_E_CANCELLED;
        if ((st = pks_scan_poll(s, x->dx)) != PK_OK) return st;                                 /* R1: HOST status; the board reads and 0x90 only on an interrupt */
        uint32_t sw = cur_sw(x);
        if (sw != x->last_status_word) {
            x->last_status_word = sw;
            pks_emit_msg(s, PK_EV_FILM_SENSE, PK_OK, sw, "film sensors: entry %s, exit %s", (sw & 0x40000000u) ? "film" : "clear", (sw & 0x80000000u) ? "film" : "clear");
        }
        if (s->host_unknown != x->host_rep) {                                                   /* S-R36: unknown HOST status bits are recorded, never fatal */
            x->host_rep = s->host_unknown;
            char ev[96];
            snprintf(ev, sizeof ev, "HOST status bits 0x%X seen (not tested by TLB)", x->host_rep);
            pks_emit_msg(s, PK_EV_WARNING, PK_OK, x->host_rep, "%s", ev);
            pk_sidecar_add_event(x->sc, ev);
        }
        if (s->host_overflow && !x->overflow_rep) {                                             /* r-m3: reported even when the scan completes */
            x->overflow_rep = true;
            pks_emit_msg(s, PK_EV_WARNING, PK_OK, 0x02, "the host reported a FIFO overflow");
            pk_sidecar_add_event(x->sc, "HOST status reported a FIFO overflow (bit 1)");
        }
        if ((st = led_apply(x)) != PK_OK) return st;                                            /* releases the 0x4C hold when the sensors clear */
        uint64_t bytes = 0;
        st = pk_stream_poll(x->st, &bytes, NULL);
        if (st != PK_OK) {                                                                      /* R2: lost sync, ring or device overflow, transport error */
            char dg[96];
            pk_stream_diag(x->st, dg, sizeof dg);
            set_err(x, "%s%s", s->host_overflow ? "the host reported a FIFO overflow; " : "", dg[0] ? dg : "the scan stream failed");
            return st;
        }
        unsigned long long now = pkb_now_ms();
        if (bytes != x->last_bytes) { x->last_bytes = bytes; x->bytes_ms = now; }
        else if (now - x->bytes_ms > PKS_PACKET_READY_MS) {                                     /* EC_TimeOut 0x9f: no packet within ScanPacketReadyTimeOut */
            set_err(x, "no scan data for %u ms", PKS_PACKET_READY_MS);
            return PK_E_TIMEOUT;
        }
        det_check_deadline(&x->det);
        det_snap d = det_get(&x->det);
        if (d.started && !x->strip_open) {                                                      /* R3: film found (film LED phase 1) */
            x->strip_open = true;
            if ((st = led_phase(x, 1)) != PK_OK) return st;
        }
        if (d.ended) {
            if (d.no_film) {                                                                    /* R6 */
                if (x->strips_done == 0) { set_err(x, "no film within %u s", x->cfg->no_film_timeout_s); return PK_E_NO_FILM; }
                *roll_ok = true;                                                                // later strips: a normal end of the roll
                return PK_OK;
            }
            if ((st = led_phase(x, 3)) != PK_OK) return st;                                     /* R4 / R5: film end or the limit: phase 3 (0x4C) */
            if ((st = strip_finish(x, &d)) != PK_OK) return st;
            x->strip++;
            if (x->strip >= x->strips_max) { *roll_ok = true; return PK_OK; }                   /* M4: the budget is spent: a normal end, no error and no warning */
            /* M3: the next strip. The stream's sync search restarts and the lines buffered so far are not read; 0x91 is sent again (it also zeroes the DX counters). */
            pk_dx_free(x->dx);
            x->dx = NULL;
            if ((st = dx_new_strip(x)) != PK_OK) return st;
            x->segment++;
            det_begin(&x->det, x->segment, x->lines_per_strip, x->cfg->no_film_timeout_s);       /* armed before the re-arm (n3) */
            if ((st = pk_stream_rearm_sync(x->st)) != PK_OK) return st;
            if ((st = pk_dx_start(b, dx_speed(x->cfg), PKS_DX_FORMAT_35MM)) != PK_OK) return st;
            if ((st = led_phase(x, 2)) != PK_OK) return st;                                     /* phase 2 again (held at 0x4C while the exit sensor is covered) */
        }
        if (now - x->last_write_ms >= PKS_SIDECAR_EVERY_MS && (st = sidecar_flush(x)) != PK_OK) return st;
        snapshot_progress(x, now);
        pkb_sleep_ms(PKS_SCAN_POLL_MS);
    }
}

pk_status pks_scan_sequence(pk_session *s, const char *roll_base_path, const pk_scan_config *cfg) {
    const pk_model *m = s->model;
    s->diag[0] = 0;
    s->keep_film_led = s->keep_status_led = false;
    if (pks_scan_supported(m, cfg, s->diag, sizeof s->diag) != PK_OK) return PK_E_UNSUPPORTED;     /* also checked by pk_session_start, before the lamp-up */
    if (s->light.version != 1 || s->light.dpi_base != cfg->dpi_base || s->light.ir != cfg->ir) {
        snprintf(s->diag, sizeof s->diag, "the light settings are not for this base / IR setting");
        return PK_E_ARG;
    }
    scan_t *x = (scan_t *)calloc(1, sizeof *x);
    if (!x) return PK_E_NOMEM;
    x->s = s;
    x->b = s->b;
    x->cfg = cfg;
    x->light = s->light;
    x->led_cur = x->led_want = -1;
    x->words_per_line = pk_words_per_line(m, cfg->dpi_base, cfg->ir);
    pthread_mutex_init(&x->det.mu, NULL);
    snprintf(x->raw_path, sizeof x->raw_path, "%s.raw", roll_base_path);
    snprintf(x->json_path, sizeof x->json_path, "%s.json", roll_base_path);
    pk_status st = pk_scan_strip_budget(m, cfg, &x->strips_max, &x->lines_per_strip);
    /* U10: TLB divides by zero when the strip count is 0; validation refuses it, and so does this (a scan never starts with no strips) */
    if (st == PK_OK && (x->strips_max == 0 || x->lines_per_strip == 0 || x->words_per_line == 0)) st = PK_E_ARG;
    bool roll_ok = false;
    pk_status run = st;
    if (st == PK_OK) {
        /* row 2: the lamp health gate (TLB: S+0x38 & 0x040548C0 -> EC_LampError); host-side flags, no traffic. Row 3: the forced status pass with the FilmInGuides refusal.
         * Both come before any roll file exists (r-m8). */
        if (s->b->sticky & PKS_LAMP_FAULTS) { set_err(x, "the lamp board reports a fault"); st = PK_E_DEVICE; }
        else if (pks_cancelled(s)) st = PK_E_CANCELLED;
        else st = forced_pass(x);
    }
    if (st == PK_OK) st = sidecar_open(x);
    if (st == PK_OK) run = run_scan(x, &roll_ok);
    else run = st;
    pk_status end = end_scan(x);                       /* E2-E3, even after a failure (TLB runs EndScan(..., 1) after any BeforeScan failure) */
    /* PSI's 0x1000 message needs a strip count other than 1 (RE 42 sec 7.2): raised now that the roll is over */
    if (x->sc && x->strips_done != 1)
        for (unsigned i = 0; i < 15; i++) if (x->limit_mask & (1u << i)) emit_warning(x, i, PK_SCANW_MAX_FILM_LENGTH_EXCEEDED);
    /* the roll's last words: the data is complete only if the scan ran to a normal end (or its no-film wait after a strip) */
    if (x->sc) {
        char ts[32];
        utc_now(ts);
        pk_sidecar_set_str(x->sc, "ended_utc", ts);
        pk_sidecar_set_bool(x->sc, "complete", run == PK_OK && roll_ok);
        const char *msg = run == PK_OK ? NULL : x->err[0] ? x->err : pk_status_str(run);
        pk_sidecar_set_str(x->sc, "error", msg);
        pk_status w = sidecar_flush(x);                // the strip still open is written as incomplete (I-3)
        if (run == PK_OK && w != PK_OK) run = w;
    }
    /* Errors the stream raised after the last strip ended (a sync loss in trailing lines, a late overflow) do not touch the roll; a failed raw-file write does. */
    if (run == PK_OK && (x->stop_st == PK_E_IO || x->stop_st == PK_E_NOMEM)) {
        run = x->stop_st;
        if (x->sc) { pk_sidecar_set_bool(x->sc, "complete", false); pk_sidecar_set_str(x->sc, "error", pk_status_str(run)); (void)sidecar_flush(x); }
    }
    if (x->err[0]) snprintf(s->diag, sizeof s->diag, "%s", x->err);
    pk_dx_free(x->dx);
    pk_stream_free(x->st);
    pk_sidecar_free(x->sc);
    pthread_mutex_destroy(&x->det.mu);
    free(x);
    return run != PK_OK ? run : end;
}
