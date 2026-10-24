#define _POSIX_C_SOURCE 200809L
/* The light calibration for one config (Task 15). Origin: TLB FN_bCalibrateLEDs FUN_10020dc0 with FN_bCalibrateFindDarkOffset FUN_1001e1c0, FN_bCalibrateFindLedCurrent FUN_1001e7b0,
 * FN_bCalibrateFindLedDutyCycle FUN_1001ec90, the duty recompute FUN_1001e020, FN_bCalibrateFixedPatternDark FUN_1001e4a0, FN_bCalibrateFixedPatternBright FUN_1001f550 and (IR)
 * FN_bCalibrateFixedPatternIrLag FUN_1001fb80, with the lamp writer FUN_1002c5f0; the row numbers C1..C11 are docs/re/43-calibration-sequence.md sec 2 (sec 4 for IR). v1's
 * equivalent (tools/calib_wizard.py, build_calibration.py) calibrated once and normalised the gain per channel; TLB's order and numbers are followed instead (owner rule: exact parity
 * with Kodak). An IR run (ColNegIr) is TLB's whole light calibration again in IR mode: its own black level, then R, G, B AND IR searched together with the IR LED lit (lamp 0x80 = 3),
 * so it yields a complete light set of its own.
 * Writes no scanner memory: the packets are the lamp (0x80 / 0x81 / 0x82), the CCD window and AFE (motor 0x82 / 0x84), light 0x89 and the FIFO reset, all existing rows. */
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "boards/boards.h"
#include "calib/calib.h"
#include "calib/record.h"
#include "pakon/calib.h"
#include "util/util.h"

#define LINES_SEARCH 32u                 /* FindLedCurrent / FindLedDutyCycle: a 32-line average per step */
#define LINES_TABLE PKCAL_TABLE_LINES    /* FixedPatternDark / Bright / IrLag: 128 */
#define DARK_ROUNDS 8u                   /* FindDarkOffset: at most 8 rounds */
#define DUTY_ROUNDS 32u                  /* FindLedDutyCycle: at most 32 rounds per call (0x1001edd4) */
#define DUTY_CONFIRM 2                   /* FindLedDutyCycle: rounds with every channel settled before it returns (0x1001ed87, 0x1001f301) */
#define CURRENT_STEPS_MAX 64u            /* OURS: a bound on FindLedCurrent (TLB's loop ends at the current limits, at most 24 steps) */
#define OUTER_MAX 256u                   /* OURS: a bound on the caller's raise-and-search loop (TLB's has none: current <= 24 and gain <= 62 end it) */
#define GAIN_START 13u
#define GAIN_FAIL_ABOVE 62u              /* C8: Gain_c > 62 -> EC_InsufficientLight */
#define LOW_LIGHT_GAIN 0x33u             /* C9: any gain code >= 51 */
#define IR_FLAG_BELOW 10000u             /* C7: a capped IR duty is flagged only while the IR maximum is below 0x2710 (0x1001f2e9) */
#define DUTY_SETTLE_MS 200u              /* FUN_10022f70(0xc8) before the confirming round (0x1001f318) */
#define IR_FPGA_BIT 0x100u               /* FPGA index 0 bit 0x100: the IR plane (FUN_10029860, RE 42 sec 2) */

static const char *const CH_NAME[4] = { "Red", "Green", "Blue", "Ir" };
static const double D_COLNEG[4] = { 0.144, 0.400, 0.715, 0.0 };   /* FUN_10020230, colour negative (RE 07 sec 1 item 5) */
static const double WAIT_FOR_LAMP_S[4] = { 5.0, 5.0, 5.0, 5.0 };   /* WaitForLamp_R/G/B/Ir, G+0x1630.. (owner 5.0, RE 42 sec 2) */
static const unsigned LIM_RGB[4] = { 4, 20, 20, 0 };              /* FUN_100203c0, 'D' board: LED current limits; IR off */
static const unsigned LIM_IR[4] = { 8, 24, 24, 8 };               /* IR on */

static void diag(const pkcal_ctx *c, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void diag(const pkcal_ctx *c, const char *fmt, ...) {
    if (!c->diag || !c->diag_cap) return;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(c->diag, c->diag_cap, fmt, ap);
    va_end(ap);
}

static unsigned base_idx(int dpi_base) { return dpi_base == 4 ? 0u : dpi_base == 8 ? 1u : 2u; }

/* ---------------------------------------------------------------- row C1: the calibration window
 * FUN_1002c340(height + Offset - 6, 6, LC+0x28, ir = 0, ...): index 4 = 6 (3 binned), index 5 = Offset + height, so the line holds wire = Offset + height - start CCD pixels and the
 * optical-black pixels are the first ob_px of it. The acquired pixel count scales with the base's line: n_acq = wire * hires_px / ccd_px_height (base 8: 2048 * 1500 / 2000 = 1536 =
 * PB+0x68 + (Offset - 6) * 1500/2000, RE 43 row C1), and the active pixels start after the gap (Offset - start) scaled the same way. The IR bit is NOT set here even for an IR run:
 * TLB's first window has ir = 0 and the black level runs on it; row C4 rewrites the window with the bit. */
static pk_status setup_window(pkcal_run *r, const pk_cal_light *l) {
    pkb_ccd_window w;
    pk_status st = pkb_ccd_window_for(r->c->model, r->dpi_base, &w);
    if (st != PK_OK) return st;
    const pk_base_geom *g = &r->c->model->geom[base_idx(r->dpi_base)];
    const unsigned off = l->px_offset ? l->px_offset : w.px_offset;
    const unsigned start = w.binned ? 3u : 6u;
    if (off < start) return PK_E_ARG;
    r->ob_px = (int)start;
    r->wire_px = off + w.px_height - start;
    r->n_acq = (int)((unsigned long)r->wire_px * (unsigned long)g->hires_px / (unsigned long)w.px_height);
    r->gap_px = (int)((unsigned long)(off - start) * (unsigned long)g->hires_px / (unsigned long)w.px_height);
    r->n_px = r->n_acq - r->gap_px;
    if (r->n_px != g->hires_px || r->gap_px < r->ob_px) return PK_E_UNSUPPORTED;      /* a base whose geometry does not fit TLB's arithmetic */
    memset(&r->ccd, 0, sizeof r->ccd);
    r->ccd.px_offset = (uint16_t)start;
    r->ccd.px_height = (uint16_t)r->wire_px;
    r->ccd.integration = (uint16_t)l->integration;
    r->ccd.fpga_ctrl = (uint16_t)0x0060u;
    r->ccd.binned = w.binned;
    r->ccd.light_89 = w.light_89;
    for (int c = 0; c < 3; c++) { r->ccd.afe_gain[c] = (uint8_t)l->afe_gain[c]; r->ccd.afe_offset[c] = (int16_t)l->afe_offset[c]; }
    r->period = pkb_pwm_period(l->integration);
    r->lnch = 3;
    return PK_OK;
}

/* ---------------------------------------------------------------- statistics over an acquisition (channel-major) */
/* FUN_1001d590 with average = 1: every dword divided by the line count, truncating. */
static pk_status acquire_avg(pkcal_run *r, unsigned lines, uint32_t *buf) {
    pk_status st = pkcal_acquire(r, lines, buf);
    if (st != PK_OK) return st;
    const size_t n = (size_t)r->lnch * (size_t)r->n_acq;
    for (size_t i = 0; i < n; i++) buf[i] /= lines;
    return PK_OK;
}

/* A channel's maximum over the active pixels [gap, n_acq) (FUN_1001e7b0 / FUN_1001ec90's max loops from param_8 / param_13). */
static unsigned active_max(const pkcal_run *r, const uint32_t *buf, int c) {
    const uint32_t *row = buf + (size_t)c * (size_t)r->n_acq;
    uint32_t m = 0;
    for (int p = r->gap_px; p < r->n_acq; p++)
        if (row[p] > m) m = row[p];
    return m;
}

/* ---------------------------------------------------------------- the lamp: TLB FUN_1002c5f0
 * 0x80 = (vis ? 1 : 0) | (ir ? 2 : 0), change-only. Currents clamped to FUN_100203c0's limits (the IR current and duty are 0 without IR), duties to [0, 1]. 0x81 when a current changed,
 * 0x82 when a duty changed (the on-count is min(ceil(N x duty), N - 2)). Then the settle wait, per lit channel (the R/G/B terms only when vis, the IR term only with IR):
 *   the channel's enable bit newly set:  Current / limit x WaitForLamp x duty
 *   current rising:                      (rise) / limit x WaitForLamp, times (duty rise) when the duty rises too
 *   only the duty rising:                (duty rise) x WaitForLamp
 * and the run waits the largest, in ms, when it is above zero (0x1002ce2e). The "last" values are those this run sent last (TLB's S+0x2a0.., S+0x2b8..). */
static pk_status lamp_apply(pkcal_run *r, bool vis, const unsigned cur_in[4], const double d_in[4]) {
    pk_boards *b = r->b;
    const unsigned *lim = r->ir ? LIM_IR : LIM_RGB;
    unsigned cur[4];
    double d[4];
    uint16_t lv[4], on[4];
    for (int c = 0; c < 4; c++) {
        cur[c] = cur_in[c] >= lim[c] ? lim[c] : cur_in[c];
        d[c] = d_in[c] >= 1.0 ? 1.0 : d_in[c] > 0.0 ? d_in[c] : 0.0;
        if (c == 3 && !r->ir) { cur[c] = 0; d[c] = 0.0; }
        lv[c] = (uint16_t)cur[c];
        on[c] = (uint16_t)pkb_duty_on_count(r->period, d[c]);
    }
    const uint8_t mask = (uint8_t)((vis ? 1 : 0) | (r->ir ? 2 : 0));
    const uint8_t old = b->lamp_on ? b->lamp_mask : 0;
    const bool new_vis = !(old & 1) && (mask & 1), new_ir = !(old & 2) && (mask & 2);
    pk_status st;
    if (old != mask && (st = pk_light_lamp_on(b, vis, r->ir)) != PK_OK) return st;
    if ((!b->lamp_lv_known || memcmp(b->lamp_lv, lv, sizeof lv)) && (st = pk_light_set_levels(b, lv)) != PK_OK) return st;
    bool dchg = !r->sent_valid || !b->lamp_duty_known || b->lamp_period != r->period || memcmp(b->lamp_on_cnt, on, sizeof on);
    for (int c = 0; c < 4 && !dchg; c++) dchg = d[c] != r->sent_d[c];
    if (dchg && (st = pk_light_set_duty(b, on, (uint16_t)r->period)) != PK_OK) return st;
    double T = -1.0;
    for (int c = 0; c < 4; c++) {
        if ((c < 3 && !vis) || (c == 3 && !r->ir) || lim[c] == 0) continue;
        const unsigned pc = r->sent_valid ? r->sent_cur[c] : 0;
        const double pd = r->sent_valid ? r->sent_d[c] : 0.0;
        double t = -1.0;
        if (c < 3 ? new_vis : new_ir) t = (double)cur[c] / (double)lim[c] * WAIT_FOR_LAMP_S[c] * d[c];
        else if (cur[c] > pc) {
            t = (double)(cur[c] - pc) * WAIT_FOR_LAMP_S[c] / (double)lim[c];
            if (d[c] > pd) t *= d[c] - pd;
        } else if (d[c] > pd) t = (d[c] - pd) * WAIT_FOR_LAMP_S[c];
        if (t > T) T = t;
    }
    for (int c = 0; c < 4; c++) { r->sent_cur[c] = cur[c]; r->sent_d[c] = d[c]; if (dchg) r->sent_on[c] = on[c]; }
    r->sent_valid = true;
    if (!(T > 0.0)) return PK_OK;
    unsigned long long end = pkb_now_ms() + (unsigned long long)(1000.0 * T);
    while (pkb_now_ms() < end) {
        if ((st = pkcal_tick(r->c)) != PK_OK) return st;
        pkb_sleep_ms(20);
    }
    return PK_OK;
}

static pk_status wait_ms(pkcal_run *r, unsigned ms) {
    unsigned long long end = pkb_now_ms() + ms;
    while (pkb_now_ms() < end) {
        pk_status st = pkcal_tick(r->c);
        if (st != PK_OK) return st;
        pkb_sleep_ms(10);
    }
    return PK_OK;
}

/* FUN_1001e7b0's end and FUN_1001e020: the duty that goes with a current n, maxDuty x (n - 1) / n, or maxDuty / 2 below 3. */
static double duty_for_current(double maxd, unsigned n) { return n < 3 ? maxd * 0.5 : maxd * (double)(n - 1) / (double)n; }

/* ---------------------------------------------------------------- row C6b: FindLedCurrent (FUN_1001e7b0, code 0x1f) */
/* All currents from 1 and every duty at 10^-D (the caller's 1.0 x FUN_10020230(1)); per step a 32-line average and each channel's active maximum: R, G stop above 64000, B above 65500,
 * IR above 40000 (IR only in an IR run; otherwise it starts stopped), else the current rises by one up to the limit. When every channel has stopped, duty = duty_for_current. */
static pk_status find_led_current(pkcal_run *r, unsigned cur[4], double duty[4], const double maxd[4]) {
    const unsigned *lim = r->ir ? LIM_IR : LIM_RGB;
    static const unsigned STOP_ABOVE[4] = { 0xfa00, 0xfa00, 0xffdc, 0x9c40 };
    bool stop[4] = { false, false, false, !r->ir };
    for (int c = 0; c < 4; c++) { cur[c] = 1; duty[c] = maxd[c]; }
    pk_status st = lamp_apply(r, true, cur, duty);
    for (unsigned step = 0; st == PK_OK; step++) {
        if (step >= CURRENT_STEPS_MAX) { diag(r->c, "the LED current search did not end after %u steps", CURRENT_STEPS_MAX); return PK_E_CAL_LIGHT; }
        if ((st = acquire_avg(r, LINES_SEARCH, r->acc)) != PK_OK) return st;
        for (int c = 0; c < r->nch; c++) {
            if (stop[c]) continue;
            const unsigned m = active_max(r, r->acc, c);
            if (m > STOP_ABOVE[c]) stop[c] = true;
            else if (cur[c] < lim[c]) cur[c]++;
            else stop[c] = true;
        }
        if (stop[0] && stop[1] && stop[2] && stop[3]) {
            for (int c = 0; c < 4; c++) duty[c] = duty_for_current(maxd[c], cur[c]);
            return lamp_apply(r, true, cur, duty);
        }
        pkcal_progress(r->c, 30 + (int)(step > 19 ? 19 : step), "LED current search step %u", step + 1);
        st = lamp_apply(r, true, cur, duty);
    }
    return st;
}

/* ---------------------------------------------------------------- row C7: FindLedDutyCycle (FUN_1001ec90, code 0x21) */
/* Up to 32 rounds of a 32-line average. Per channel (R, G, B; IR only in an IR run) with its maximum m and target window (63936..64000; IR 39936..40000):
 *   not yet settled: it settles when m is in the window, or its duty is above 1.0, or the on-count last sent equals one of the two before it (the duty no longer moves it);
 *                    otherwise duty = duty / m x 63968 (IR 39968), doubled when m = 0;
 *   settled:         duty = duty / m x 63968 (IR 39968) every round all the same;
 *   either way a duty above 10^-D settles the channel and becomes 10^-D + 0.001.
 * When every channel has settled, the channels whose duty is above 10^-D are flagged (IR only while its maximum is below 10000); a flag returns at once, otherwise the round is confirmed
 * once more after 200 ms. Every round that goes on writes the duties (FUN_1002c5f0, with its settle). At the end the duties are capped at 10^-D and kept as the open-gate duties; with no
 * flag the with-film duties are min(1, duty x 10^D) (FUN_10020230(0)) and LC+0x68 the IR maximum. */
static pk_status find_duty(pkcal_run *r, const unsigned cur[4], double d[4], const double maxd[4], double film[4], unsigned *flags, unsigned m_flag[4]) {
    *flags = 0;
    const int nc = r->ir ? 4 : 3;
    bool done[4] = { false, false, false, !r->ir };
    unsigned last[4] = { 0, 0, 0, 0 }, last2[4] = { 0, 0, 0, 0 }, m[4] = { 0, 0, 0, 0 };
    int confirm = DUTY_CONFIRM;
    for (unsigned round = 0; round < DUTY_ROUNDS; round++) {
        pk_status st = acquire_avg(r, LINES_SEARCH, r->acc);
        if (st != PK_OK) return st;
        for (int c = 0; c < nc; c++) {
            const bool irc = c == 3;
            const unsigned lo = irc ? 0x9c00u : 0xf9c0u, hi = irc ? 0x9c40u : 0xfa00u;
            const double T = irc ? 39968.0 : 63968.0;
            m[c] = active_max(r, r->acc, c);
            if (!done[c]) {
                if ((m[c] >= lo && m[c] <= hi) || d[c] > 1.0 || r->sent_on[c] == last[c] || r->sent_on[c] == last2[c]) done[c] = true;
                else if (m[c] == 0) d[c] += d[c];
                else d[c] = d[c] / (double)m[c] * T;
                last2[c] = last[c];
                last[c] = r->sent_on[c];
            } else d[c] = m[c] ? d[c] / (double)m[c] * T : HUGE_VAL;          /* x87 division by zero (masked): +inf, capped just below */
            if (d[c] > maxd[c]) { done[c] = true; d[c] = maxd[c] + 0.001; }
        }
        if (done[0] && done[1] && done[2] && done[3]) {
            for (int c = 0; c < 3; c++) if (d[c] > maxd[c]) { *flags |= 1u << c; m_flag[c] = m[c]; }
            if (r->ir && d[3] > maxd[3] && m[3] < IR_FLAG_BELOW) { *flags |= 8u; m_flag[3] = m[3]; }
            if (*flags || --confirm < 1) break;
            if ((st = wait_ms(r, DUTY_SETTLE_MS)) != PK_OK) return st;
        }
        if ((st = lamp_apply(r, true, cur, d)) != PK_OK) return st;
        pkcal_progress(r->c, 50 + (int)(round > 29 ? 29 : round), "duty search round %u", round + 1);
    }
    for (int c = 0; c < 4; c++) if (d[c] > maxd[c]) d[c] = maxd[c];
    if (!*flags) {
        for (int c = 0; c < 4; c++) {
            const double f = d[c] * pow(10.0, D_COLNEG[c]);
            film[c] = f > 1.0 ? 1.0 : f;
        }
        if (r->ir) r->max_ir = m[3];
    }
    return PK_OK;
}

/* ---------------------------------------------------------------- the whole run */
static void result_zero(pkcal_result *o) { memset(o, 0, sizeof *o); }

void pkcal_result_free(pkcal_result *o) {
    if (!o) return;
    pkcal_tables_free(&o->tables);
    free(o->dark1_sum);
    free(o->dark_sum);
    free(o->bright_sum);
    free(o->irlag_sum);
    result_zero(o);
}

/* channel-major acquisition sums (n_acq per channel) -> channel-major (ob_px + n_px) columns: the optical-black pixels, then the active ones (RE 30 sec 13.5 layout). */
static uint32_t *columns(const pkcal_run *r, const uint32_t *acq) {
    const int w = r->ob_px + r->n_px;
    uint32_t *o = (uint32_t *)malloc((size_t)r->nch * (size_t)w * sizeof *o);
    if (!o) return NULL;
    for (int c = 0; c < r->nch; c++)
        for (int j = 0; j < w; j++) {
            const int p = j < r->ob_px ? j : r->gap_px + (j - r->ob_px);
            o[(size_t)c * (size_t)w + (size_t)j] = acq[(size_t)c * (size_t)r->n_acq + (size_t)p];
        }
    return o;
}

/* Row C4 of an IR run: FUN_1002c340(..., ir = 1, ...) sets FPGA bit 0x100 and every line from then on carries the IR plane. OURS: the stream checks a fixed line length, so it is
 * restarted around the write (acquisition off, the window, the FIFO reset, a new 4-channel stream, acquisition on); TLB's ring reader resyncs on every line instead (0x1001d2b0). */
static pk_status switch_to_ir(pkcal_run *r, bool *acquiring) {
    pk_status st = pk_host_acquire(r->b, false);
    if (st != PK_OK) return st;
    *acquiring = false;
    pkcal_cap_close(r->cap);
    r->cap = NULL;
    r->ccd.fpga_ctrl = (uint16_t)(r->ccd.fpga_ctrl | IR_FPGA_BIT);
    if ((st = pk_host_ccd_update(r->b, &r->ccd)) != PK_OK) return st;
    if ((st = pk_host_fifo_reset(r->b)) != PK_OK) return st;
    r->lnch = 4;
    if ((st = pkcal_cap_open(r->c, 4u * (unsigned)r->n_acq, &r->cap)) != PK_OK) return st;
    if ((st = pk_host_acquire(r->b, true)) != PK_OK) return st;
    *acquiring = true;
    return PK_OK;
}

pk_status pkcal_measure(const pkcal_ctx *c, const pkcal_job *job, const pk_cal_light *start, pkcal_result *out) {
    if (!out) return PK_E_ARG;
    result_zero(out);
    if (!c || !c->b || !c->t || !c->model || !job || !start || start->version != 1 || start->dpi_base != job->dpi_base || start->ir != job->ir) return PK_E_ARG;
    if (c->model->id != PK_MODEL_F135_PLUS) return PK_E_UNSUPPORTED;        /* the 'D' board's limits and integrations are the only ones derived (RE 43 sec 0) */
    if (start->integration == 0 || start->integration > 0xFFDu) return PK_E_ARG;
    pk_status st = PK_OK;
    pkcal_run r;
    memset(&r, 0, sizeof r);
    r.c = c;
    r.b = c->b;
    r.dpi_base = job->dpi_base;
    r.ir = job->ir;
    r.nch = job->ir ? 4 : 3;
    r.light = *start;
    if ((st = setup_window(&r, start)) != PK_OK) return st;
    const size_t cnt = (size_t)r.nch * (size_t)r.n_acq;
    uint32_t *dark1 = NULL, *dark2 = NULL, *bright = NULL, *lag = NULL;
    r.acc = (uint32_t *)calloc(cnt, sizeof *r.acc);
    r.raw = (uint32_t *)calloc((size_t)4 * (size_t)r.n_acq, sizeof *r.raw);
    dark1 = (uint32_t *)calloc(cnt, sizeof *dark1);
    dark2 = (uint32_t *)calloc(cnt, sizeof *dark2);
    bright = (uint32_t *)calloc(cnt, sizeof *bright);
    if (r.ir) lag = (uint32_t *)calloc(cnt, sizeof *lag);
    uint32_t *c_dark1 = NULL, *c_dark2 = NULL, *c_bright = NULL, *c_lag = NULL;
    bool acquiring = false;
    const unsigned *lim = job->ir ? LIM_IR : LIM_RGB;
    double maxd[4], duty[4], film[4] = { 0, 0, 0, 0 };
    unsigned cur[4], mf[4] = { 0, 0, 0, 0 }, flags = 0;
    bool converged = false;
    if (!r.acc || !r.raw || !dark1 || !dark2 || !bright || (r.ir && !lag)) { st = PK_E_NOMEM; goto done; }

    pkcal_progress(c, 2, "calibration base %d%s: window", job->dpi_base, job->ir ? " IR" : "");
    /* C2 first (before the stream: pk_light_lamp_off resets the FIFOs), then C1's window (no IR bit yet) and the FIFO reset */
    if ((st = pk_light_lamp_off(r.b)) != PK_OK) goto done;
    if ((st = pk_host_ccd_update(r.b, &r.ccd)) != PK_OK) goto done;           /* a first call is the full v1 sequence; later ones send changed values only */
    if ((st = pk_host_fifo_reset(r.b)) != PK_OK) goto done;
    if ((st = pkcal_cap_open(c, 3u * (unsigned)r.n_acq, &r.cap)) != PK_OK) goto done;
    if ((st = pk_host_acquire(r.b, true)) != PK_OK) goto done;
    acquiring = true;

    /* C3: black level, LEDs off, on the 3-channel line (an IR run too: its own Offset_R/G/B). */
    pkcal_progress(c, 6, "black level");
    if ((st = pkcal_afe_converge(&r, DARK_ROUNDS)) != PK_OK) goto done;
    /* C4: gains 13 (set by the convergence); an IR run now sets the IR bit. */
    if (r.ir && (st = switch_to_ir(&r, &acquiring)) != PK_OK) goto done;
    /* C5: two dark passes of 128 lines (RE 43 row C5): pass 1 gives the Dark table (in an IR run only the IR one; C11 gives R, G, B), pass 2 the means. */
    pkcal_progress(c, 20, "dark frame");
    if ((st = pkcal_acquire(&r, LINES_TABLE, dark1)) != PK_OK) goto done;
    if ((st = pkcal_acquire(&r, LINES_TABLE, dark2)) != PK_OK) goto done;

    /* C6: the light. */
    for (int i = 0; i < 4; i++) maxd[i] = pow(10.0, -D_COLNEG[i]);
    out->full = job->full;
    if (job->full) {
        pkcal_progress(c, 30, "LED current search");
        if ((st = find_led_current(&r, cur, duty, maxd)) != PK_OK) goto done;
        for (int i = 0; i < 3; i++) r.ccd.afe_gain[i] = (uint8_t)GAIN_START;  /* LC gains = 13 (FUN_10020dc0 after FindLedCurrent; the AFE already holds 13, nothing is written) */
    } else {
        /* C6a: the stored currents, open-gate duties and gains of this config (FUN_1002c5f0 + FUN_100298b0) */
        for (int i = 0; i < 4; i++) {
            cur[i] = start->current[i] ? start->current[i] : 1u;
            if (lim[i] && cur[i] > lim[i]) cur[i] = lim[i];
            duty[i] = start->duty_open[i] > 0.0 ? (start->duty_open[i] > maxd[i] ? maxd[i] : start->duty_open[i]) : maxd[i] / 2.0;   /* OURS: a stored 0 starts at half */
        }
        pkcal_progress(c, 40, "lamp settle");
        if ((st = lamp_apply(&r, true, cur, duty)) != PK_OK) goto done;
        for (int i = 0; i < 3; i++) r.ccd.afe_gain[i] = (uint8_t)(start->afe_gain[i] > 0x3F ? 0x3F : start->afe_gain[i]);
        if ((st = pk_host_ccd_update(r.b, &r.ccd)) != PK_OK) goto done;
    }
    /* C7 / C8: the duty search, and the caller's raise loop (FUN_10020dc0 0x10021217..). */
    for (unsigned outer = 0; outer < OUTER_MAX && !converged; outer++) {
        if ((st = find_duty(&r, cur, duty, maxd, film, &flags, mf)) != PK_OK) goto done;
        if (!flags) { converged = true; break; }
        bool rgb_raised = false, ir_raised = false;
        for (int i = 0; i < 3; i++) {
            if (!(flags & (1u << i))) continue;
            if (cur[i] < lim[i]) { r.ccd.afe_gain[i] = (uint8_t)GAIN_START; cur[i]++; rgb_raised = true; }
            else if (r.ccd.afe_gain[i] > GAIN_FAIL_ABOVE) {
                diag(c, "%s cannot be lit: its brightest pixel reads %u at the highest LED current and AFE gain (EC_InsufficientLight 0xDA)", CH_NAME[i], mf[i]);
                st = PK_E_CAL_LIGHT;
                goto done;
            } else r.ccd.afe_gain[i]++;
        }
        if (flags & 8u) {
            if (cur[3] >= lim[3]) {
                diag(c, "%s cannot be lit: its brightest pixel reads %u at the highest LED current (EC_InsufficientLight 0xDA)", CH_NAME[3], mf[3]);
                st = PK_E_CAL_LIGHT;
                goto done;
            }
            cur[3]++;
            ir_raised = true;
        }
        if ((st = pk_host_ccd_update(r.b, &r.ccd)) != PK_OK) goto done;   /* FUN_100298b0(Gain_R/G/B) */
        /* FUN_1001e020: a raised current re-seeds the duties of ALL three colour channels (or the IR one); the lamp is written by the next duty search's first round */
        if (rgb_raised) for (int i = 0; i < 3; i++) duty[i] = duty_for_current(maxd[i], cur[i]);
        if (ir_raised) duty[3] = duty_for_current(maxd[3], cur[3]);
    }
    if (!converged) { diag(c, "the light search did not settle after %u raises", OUTER_MAX); st = PK_E_CAL_LIGHT; goto done; }

    /* C9: the low-light flag. */
    r.light.low_light = false;
    for (int i = 0; i < 3; i++) if (r.ccd.afe_gain[i] >= LOW_LIGHT_GAIN) r.light.low_light = true;
    /* C10: FixedPatternBright, 128 lines with the lamp as the duty search last wrote it. */
    pkcal_progress(c, 90, "flat frame");
    if ((st = pkcal_acquire(&r, LINES_TABLE, bright)) != PK_OK) goto done;
    for (int i = 0; i < r.nch; i++) {
        uint32_t m = 0;
        for (int p = r.gap_px; p < r.n_acq; p++) { const uint32_t v = bright[(size_t)i * (size_t)r.n_acq + (size_t)p] / LINES_TABLE; if (v > m) m = v; }
        out->max_active[i] = m;
    }
    /* C11 (IR): FixedPatternIrLag. FUN_1002d7f0(on = 0, ir = 1): 0x80 = 2, the IR LED alone at the with-film settings; 128 lines. */
    if (r.ir) {
        pkcal_progress(c, 92, "IR lag frame");
        if ((st = lamp_apply(&r, false, cur, film)) != PK_OK) goto done;
        if ((st = pkcal_acquire(&r, LINES_TABLE, lag)) != PK_OK) goto done;
    }

    /* F6: acquisition off, the stream torn down; then the tables. */
    st = pk_host_acquire(r.b, false);
    acquiring = false;
    if (st != PK_OK) goto done;
    pkcal_cap_close(r.cap);
    r.cap = NULL;
    pkcal_progress(c, 95, "tables");
    c_dark1 = columns(&r, dark1);
    c_dark2 = columns(&r, dark2);
    c_bright = columns(&r, bright);
    if (r.ir) c_lag = columns(&r, lag);
    if (!c_dark1 || !c_dark2 || !c_bright || (r.ir && !c_lag)) { st = PK_E_NOMEM; goto done; }
    if ((st = pkcal_derive_tables2(c_dark1, c_dark2, c_bright, (int)LINES_TABLE, r.n_px, r.nch, r.ob_px, &out->tables)) != PK_OK) goto done;
    if (r.ir && (st = pkcal_irlag_dark(c_lag, (int)LINES_TABLE, r.n_px, r.ob_px, &out->tables)) != PK_OK) goto done;
    out->dark1_sum = c_dark1;
    out->dark_sum = c_dark2;
    out->bright_sum = c_bright;
    out->irlag_sum = c_lag;
    c_dark1 = c_dark2 = c_bright = c_lag = NULL;
    out->nch = r.nch;
    out->max_ir = r.max_ir;
    out->ob_px = r.ob_px;
    out->n_px = r.n_px;
    for (int i = 0; i < 3; i++) { r.light.afe_gain[i] = r.ccd.afe_gain[i]; r.light.afe_offset[i] = r.ccd.afe_offset[i]; }
    for (int i = 0; i < 4; i++) {
        r.light.current[i] = cur[i];
        r.light.duty_open[i] = i < r.nch ? duty[i] : 0.0;
        r.light.duty_film[i] = i < r.nch ? film[i] : 0.0;
    }
    if (!r.ir) r.light.current[3] = start->current[3] ? start->current[3] : 1u;
    out->light = r.light;
    st = PK_OK;
done:
    if (acquiring) (void)pk_host_acquire(r.b, false);
    pkcal_cap_close(r.cap);
    free(r.acc);
    free(r.raw);
    free(dark1);
    free(dark2);
    free(bright);
    free(lag);
    free(c_dark1);
    free(c_dark2);
    free(c_bright);
    free(c_lag);
    if (st != PK_OK) pkcal_result_free(out);
    return st;
}

/* ---------------------------------------------------------------- the record */
static void put_le16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put_le32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }

pk_status pkcal_build_record(const pkcal_result *r, const char *unit, const char *kind, const char *parent, int64_t now_s, int64_t last_full_s, pk_calibration **out) {
    if (!r || !unit || !kind || !out) return PK_E_ARG;
    *out = NULL;
    pk_calibration *c = pkcal_new();
    if (!c) return PK_E_NOMEM;
    pk_status st = pkcal_set_meta(c, unit, kind, parent);
    if (st == PK_OK) st = pkcal_set_light(c, &r->light);
    const size_t n = (size_t)r->n_px, w = (size_t)(r->ob_px + r->n_px), nch = (size_t)r->nch;
    uint8_t *d1 = (uint8_t *)malloc(nch * w * 4), *dk = (uint8_t *)malloc(nch * n * 2), *gn = (uint8_t *)malloc(nch * n * 4), *ds = (uint8_t *)malloc(nch * w * 4), *bs = (uint8_t *)malloc(nch * w * 4);
    uint8_t *sm = r->nch == 4 ? (uint8_t *)malloc(3 * n * 2) : NULL;
    uint8_t *lg = r->irlag_sum ? (uint8_t *)malloc(nch * w * 4) : NULL;
    if (!d1 || !dk || !gn || !ds || !bs || (r->nch == 4 && !sm) || (r->irlag_sum && !lg)) st = st == PK_OK ? PK_E_NOMEM : st;
    if (st == PK_OK) {
        for (size_t ch = 0; ch < nch; ch++) {
            for (size_t i = 0; i < n; i++) { put_le16(dk + (ch * n + i) * 2, r->tables.dark[ch][i]); put_le32(gn + (ch * n + i) * 4, r->tables.gain[ch][i]); }
            for (size_t i = 0; i < w; i++) { put_le32(d1 + (ch * w + i) * 4, r->dark1_sum[ch * w + i]); put_le32(ds + (ch * w + i) * 4, r->dark_sum[ch * w + i]); put_le32(bs + (ch * w + i) * 4, r->bright_sum[ch * w + i]); }
            if (lg) for (size_t i = 0; i < w; i++) put_le32(lg + (ch * w + i) * 4, r->irlag_sum[ch * w + i]);
        }
        if (sm) for (size_t ch = 0; ch < 3; ch++) for (size_t i = 0; i < n; i++) put_le16(sm + (ch * n + i) * 2, r->tables.smear[ch][i]);
        pku_jw *j = pku_jw_new(), *k = pku_jw_new();
        if (!j || !k) st = PK_E_NOMEM;
        else {
            pku_jw_obj_begin(j);
            pku_jw_key(j, "smearc"); pku_jw_arr_begin(j); for (int ch = 0; ch < 3; ch++) pku_jw_uint(j, r->tables.smearc[ch]); pku_jw_arr_end(j);
            pku_jw_key(j, "channels"); pku_jw_uint(j, (unsigned)r->nch);
            pku_jw_obj_end(j);
            pku_jw_obj_begin(k);
            pku_jw_key(k, "channels"); pku_jw_uint(k, (unsigned)r->nch);
            pku_jw_key(k, "ob_px"); pku_jw_uint(k, (unsigned)r->ob_px);
            pku_jw_key(k, "n_px"); pku_jw_uint(k, (unsigned)r->n_px);
            pku_jw_key(k, "lines"); pku_jw_uint(k, PKCAL_TABLE_LINES);
            pku_jw_key(k, "px_offset"); pku_jw_uint(k, r->light.px_offset);
            pku_jw_key(k, "full"); pku_jw_bool(k, r->full);
            pku_jw_key(k, "run_utc"); pku_jw_int(k, now_s);
            pku_jw_key(k, "full_utc"); pku_jw_int(k, r->full ? now_s : last_full_s);
            pku_jw_key(k, "max_active"); pku_jw_arr_begin(k); for (int ch = 0; ch < r->nch; ch++) pku_jw_uint(k, r->max_active[ch]); pku_jw_arr_end(k);
            pku_jw_key(k, "dark1_sum"); pku_jw_str(k, "raw/dark1_sum.u32");     /* TLB's dark pass 1 (the Dark table) */
            pku_jw_key(k, "dark_sum"); pku_jw_str(k, "raw/dark_sum.u32");       /* TLB's dark pass 2 (the means and the gain) */
            if (lg) { pku_jw_key(k, "irlag_sum"); pku_jw_str(k, "raw/irlag_sum.u32"); }   /* TLB's FixedPatternIrLag (the R/G/B Dark tables of an IR build) */
            if (r->nch == 4) { pku_jw_key(k, "max_ir"); pku_jw_uint(k, r->max_ir); pku_jw_key(k, "ir_lineage"); pku_jw_bool(k, r->full || r->parent_ir_lineage); }       /* LC+0x68 (registry Max_Ir: UNKNOWN whether TLB saves this field there) */
            pku_jw_key(k, "unchecked"); pku_jw_arr_begin(k);
            if (r->nch == 4) pku_jw_str(k, "ir tables: gain constant 60000, smear ramp and IrLag dark ported from the listing, not checked against a Kodak vector");
            pku_jw_arr_end(k);
            pku_jw_obj_end(k);
            size_t jn = 0, kn = 0;
            const char *jt = pku_jw_finish(j, &jn), *kt = pku_jw_finish(k, &kn);
            if (!jt || !kt) st = PK_E_NOMEM;
            if (st == PK_OK) st = pkcal_add_blob(c, "dark.u16", dk, nch * n * 2);
            if (st == PK_OK) st = pkcal_add_blob(c, "gain.u32", gn, nch * n * 4);
            if (st == PK_OK) st = pkcal_add_blob(c, "smear.json", jt, jn);
            if (st == PK_OK && sm) st = pkcal_add_blob(c, "smear_ir.u16", sm, 3 * n * 2);
            if (st == PK_OK) st = pkcal_add_blob(c, "raw/dark1_sum.u32", d1, nch * w * 4);
            if (st == PK_OK) st = pkcal_add_blob(c, "raw/dark_sum.u32", ds, nch * w * 4);
            if (st == PK_OK) st = pkcal_add_blob(c, "raw/bright_sum.u32", bs, nch * w * 4);
            if (st == PK_OK && lg) st = pkcal_add_blob(c, "raw/irlag_sum.u32", lg, nch * w * 4);
            if (st == PK_OK) st = pkcal_add_blob(c, "raw/ob.json", kt, kn);
        }
        pku_jw_free(j);
        pku_jw_free(k);
    }
    free(d1); free(dk); free(gn); free(ds); free(bs); free(sm); free(lg);
    if (st != PK_OK) { pk_calibration_free(c); return st; }
    *out = c;
    return PK_OK;
}

int64_t pkcal_record_last_full(const pk_calibration *c) {
    size_t n = 0;
    const char *b = (const char *)pk_calibration_blob(c, "raw/ob.json", &n);
    if (!b || !n) return 0;
    pku_json *j = NULL;
    int64_t v = 0;
    if (pku_json_parse(b, n, &j) == PK_OK) {
        const pku_json *f = pku_json_get(j, "full_utc");
        if (f && pku_json_is_int(f)) v = (int64_t)pku_json_int(f);
        pku_json_free(j);
    }
    return v;
}

int pkcal_record_ir_lineage(const pk_calibration *c) {
    size_t n = 0;
    const char *b = (const char *)pk_calibration_blob(c, "raw/ob.json", &n);
    if (!b || !n) return 0;
    pku_json *j = NULL;
    int v = 0;
    if (pku_json_parse(b, n, &j) == PK_OK) {
        const pku_json *f = pku_json_get(j, "ir_lineage");
        v = f && pku_json_bool(f);                          /* 0 unless a JSON true */
        pku_json_free(j);
    }
    return v;
}

/* Re-derivation from the raw sums (review I-5): both dark passes, the bright sum and the geometry in raw/ob.json. */
pk_status pkcal_rederive(const pk_calibration *c, pk_cal_tables *out) {
    if (!c || !out) return PK_E_ARG;
    size_t nj = 0, n1 = 0, n2 = 0, nb = 0, nl = 0;
    const char *oj = (const char *)pk_calibration_blob(c, "raw/ob.json", &nj);
    const uint8_t *d1 = (const uint8_t *)pk_calibration_blob(c, "raw/dark1_sum.u32", &n1), *d2 = (const uint8_t *)pk_calibration_blob(c, "raw/dark_sum.u32", &n2),
                  *br = (const uint8_t *)pk_calibration_blob(c, "raw/bright_sum.u32", &nb), *lg = (const uint8_t *)pk_calibration_blob(c, "raw/irlag_sum.u32", &nl);
    if (!oj || !d2 || !br) return PK_E_CORRUPT;
    pku_json *j = NULL;
    if (pku_json_parse(oj, nj, &j) != PK_OK) return PK_E_CORRUPT;
    const pku_json *jc = pku_json_get(j, "channels"), *jo = pku_json_get(j, "ob_px"), *jn = pku_json_get(j, "n_px");
    long long nch = jc && pku_json_is_int(jc) ? pku_json_int(jc) : 0, ob = jo && pku_json_is_int(jo) ? pku_json_int(jo) : 0, np = jn && pku_json_is_int(jn) ? pku_json_int(jn) : 0;
    pku_json_free(j);
    if ((nch != 3 && nch != 4) || ob <= 0 || ob > 64 || np <= 0 || np > 0x10000) return PK_E_CORRUPT;
    const size_t cnt = (size_t)nch * (size_t)(ob + np);
    if (n2 != cnt * 4 || nb != cnt * 4 || (d1 && n1 != cnt * 4) || (lg && (nch != 4 || nl != cnt * 4))) return PK_E_CORRUPT;
    uint32_t *a = (uint32_t *)malloc(cnt * 4), *b = (uint32_t *)malloc(cnt * 4), *e = (uint32_t *)malloc(cnt * 4), *l = lg ? (uint32_t *)malloc(cnt * 4) : NULL;
    pk_status st = PK_E_NOMEM;
    if (a && b && e && (!lg || l)) {
        for (size_t i = 0; i < cnt; i++) {
            a[i] = (uint32_t)(d1 ? d1 : d2)[4 * i] | (uint32_t)(d1 ? d1 : d2)[4 * i + 1] << 8 | (uint32_t)(d1 ? d1 : d2)[4 * i + 2] << 16 | (uint32_t)(d1 ? d1 : d2)[4 * i + 3] << 24;
            b[i] = (uint32_t)d2[4 * i] | (uint32_t)d2[4 * i + 1] << 8 | (uint32_t)d2[4 * i + 2] << 16 | (uint32_t)d2[4 * i + 3] << 24;
            e[i] = (uint32_t)br[4 * i] | (uint32_t)br[4 * i + 1] << 8 | (uint32_t)br[4 * i + 2] << 16 | (uint32_t)br[4 * i + 3] << 24;
            if (l) l[i] = (uint32_t)lg[4 * i] | (uint32_t)lg[4 * i + 1] << 8 | (uint32_t)lg[4 * i + 2] << 16 | (uint32_t)lg[4 * i + 3] << 24;
        }
        st = pkcal_derive_tables2(a, b, e, (int)PKCAL_TABLE_LINES, (int)np, (int)nch, (int)ob, out);
        if (st == PK_OK && l && (st = pkcal_irlag_dark(l, (int)PKCAL_TABLE_LINES, (int)np, (int)ob, out)) != PK_OK) pkcal_tables_free(out);
    }
    free(a); free(b); free(e); free(l);
    return st;
}
