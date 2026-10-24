/* The read-only Track test (Task 15). Origin: TLB FN_bFilmTrackTest FUN_1002b620 (job type 0x10), docs/re/43-calibration-sequence.md sec 8.1, steps T1-T9 -- ONLY the sampling and
 * the evaluation. The parts that WRITE are not ported and are never sent (RE 43 sec 8.2, S-R39 b/c): the DX threshold write 0x94 at the end of every successful TLB run, the pot adjust
 * 0x96 and its commit 0x97, and the log file T0. The thresholds TLB would store are computed and reported only. v1 had no Track test. */
#include <stdlib.h>
#include <string.h>
#include "boards/boards.h"
#include "calib/calib.h"
#include "pakon/dx.h"

#define TR_SEARCH_SAMPLES 100000u        /* T3: no film by the 100000th sample -> EC_DXNoFilmFound (counter 0x186A0 at 0x1002b96a, SETZ at 0x1002bb88) */
#define TR_SKIP_SAMPLES 101u             /* T3: the first 101 samples never find film (counter >= 0x1863C, 0x1002bb2e) */
#define TR_FILM_OFFSET 5u                /* DxCalibrationFilmOffset (Scan\\Test, owner 5; TLB default 5) */
#define TR_FAST_AFTER 4000u              /* T4: the speed change at the 4000th film-phase sample (0x1002ba7c) */
#define TR_CHECK_AFTER 4001u             /* T4: the counter stops at 4001 (JLE 0xfa0, 0x1002ba22); the end check runs from the 4002nd sample */
#define TR_END_COUNT 72u                 /* T4: the 72nd qualifying sample, counted cumulatively, not consecutively (CMP 0x46, 0x1002ba5b) */
/* OURS, not TLB's (TLB's film phase has no bound: it ends only on the 72 clear samples or a cancel, RE 43 sec 8.1.1). A seconds bound on the film
 * phase: the longest strip PSI accepts (NormalRollMaxFilmLength_mm 1670, RE 41) at the fast film-phase speed 25000, about 27 mm/s (INFERRED:
 * the owner's strip, taken as a 6-frame 228 mm strip, cleared the entry pair in about 55 s at 3800 in hw2e-track2, and the speed is taken as
 * linear in the 0xA5 value), is about 62 s; the 4001 slow samples take about 11 s at the 355 reads/s seen; plus 60 s for the owner to lift
 * the tail off the exit head, which the end condition needs. 133 s, rounded up. */
#define TR_FILM_CAP_MS 150000u
#define TR_SPEED_FIND 3800u              /* 0xED8 */
#define TR_SPEED_FILM 2400u              /* 0x960 */
#define TR_SPEED_FAST 25000u             /* 'D' board (10000 otherwise) */
#define TR_STOP_WAIT_MS 1000u            /* T8: FUN_10023000 */
#define TR_MAX_BAD_READS 50u

typedef struct { uint32_t h[4][256]; } hists;

/* max_c: one below the bin where the count from 255 downward reaches 4, not below 0x80 (T3), recomputed on demand from the histogram. */
static int sensor_max(const uint32_t *h) {
    unsigned acc = 0;
    for (int b = 255; b >= 0; b--) {
        acc += h[b];
        if (acc >= 4) { int m = b - 1; return m < 0x80 ? 0x80 : m; }
    }
    return 0x80;
}

/* FUN_1002a790: the most frequent value in [(top - 6) / 2, top - 6), top = the highest non-empty bin (ties: the lowest bin; INFERRED, the tie rule was not read). */
static int sensor_mode(const uint32_t *h) {
    int top = -1;
    for (int b = 255; b >= 0; b--) if (h[b]) { top = b; break; }
    if (top < 0) return 0;
    int lo = (top - 6) / 2, hi = top - 6, best = lo < 0 ? 0 : lo;
    uint32_t bc = 0;
    for (int b = lo < 0 ? 0 : lo; b < hi; b++) if (h[b] > bc) { bc = h[b]; best = b; }
    return best;
}

/* T5: min_c = one above the bin where the count from 0 upward reaches 10. */
static int sensor_min(const uint32_t *h) {
    unsigned acc = 0;
    for (int b = 0; b < 256; b++) { acc += h[b]; if (acc >= 10) return b + 1; }
    return 255;
}

static void add_ec(pk_track_result *o, unsigned code) { if (o->n_ec < sizeof o->ec_codes / sizeof o->ec_codes[0]) o->ec_codes[o->n_ec++] = code; }

/* T5 / T6 over the histograms so far: the levels, the swing flags and the thresholds TLB would write (never written here). Also run on a
 * stop before TLB's evaluation (no film, cancel, the cap), where TLB evaluates nothing: then it is a report only and o->partial is set. */
static void evaluate(const hists *h, unsigned n, pk_track_result *o) {
    if (n < 10) return;                                               /* min_c needs 10 samples (TLB's loop has no other bound) */
    o->swing_flags = 0;
    for (int i = 0; i < 4; i++) {
        const int mx = sensor_max(h->h[i]), mode = sensor_mode(h->h[i]), mn = sensor_min(h->h[i]), sw = mode - mn;
        o->level_max[i] = mx; o->level_mode[i] = mode; o->level_min[i] = mn; o->swing[i] = sw;
        o->thresholds[i] = (mn + (sw >> 2)) & 0xFF;
        o->no_film_thresholds[i] = ((mode + 1 + mx) / 2) & 0xFF;
        if (sw < 0x50 && (mx >> 1) < 0x50) o->swing_flags |= 1u << i;
    }
}

pk_status pkcal_track_test(const pkcal_ctx *c, pk_film_format fmt, pk_track_result *o) {
    if (!o) return PK_E_ARG;
    memset(o, 0, sizeof *o);
    for (int i = 0; i < 4; i++) {
        o->thresholds[i] = o->no_film_thresholds[i] = o->pots[i] = -1;
        o->level_min[i] = o->level_mode[i] = o->level_max[i] = o->swing[i] = -1;
    }
    o->result_word = 0xFF;                                            /* T0: S+0x394 = 0xFF until the evaluation runs */
    if (!c || !c->b) return PK_E_ARG;
    if (fmt != PK_FILM_35MM) return PK_E_UNSUPPORTED;                 /* FilmTrackTest(_, 1) is the 35 mm format */
    pk_boards *b = c->b;
    hists *h = (hists *)calloc(1, sizeof *h);
    if (!h) return PK_E_NOMEM;
    pk_status st = pk_film_start_register(b, PK_FILM_FORWARD, TR_SPEED_FIND);          /* T1: MOTOR 0xA5 = 0xED8, forward */
    bool motor = st == PK_OK;
    unsigned bad = 0, n = 0, search = TR_SEARCH_SAMPLES, film_n = 0, qual = 0;
    bool primed = false, found = false, finished = false, no_film = false;
    int mx[4] = { 0, 0, 0, 0 };                                       /* TLB's max_c bytes start at 0 and are recomputed at the END of each sample */
    unsigned long long film_t0 = 0;
    while (st == PK_OK && !finished) {
        if ((st = pkcal_tick(c)) != PK_OK) break;                     /* a cancel is checked at the top of TLB's loop too (0x1002b99c) */
        uint8_t v[4];
        pk_status rs = pk_dx_read_levels(b, v);                       /* T2: LIGHT 0x93, 4 bytes (read only) */
        if (rs == PK_E_PROTOCOL) { if (++bad > TR_MAX_BAD_READS) { st = rs; break; } continue; }    /* a status-0x29 reply is not sensor data (HW-1 run 4) */
        if (rs != PK_OK) { st = rs; break; }
        bad = 0;
        if (!primed) { primed = true; continue; }                     /* TLB reads 0x93 once after the motor start (0x1002b8fb) and keeps nothing of it */
        n++;
        for (int i = 0; i < 4; i++) h->h[i][v[i]]++;
        if (!found) {                                                 /* T3: the film search, against max_c of the samples BEFORE this one */
            if (search < TR_SEARCH_SAMPLES - TR_SKIP_SAMPLES + 1u) {  /* counter (100000 - n + 1) below 99900 */
                bool all = true;
                for (int i = 0; i < 4; i++) if (!((unsigned)(mx[i] - (int)TR_FILM_OFFSET) > (unsigned)v[i])) all = false;   /* unsigned, JBE 0x1002bb43.. */
                found = all;
            }
            if (--search == 0) { no_film = true; finished = true; }  /* the 100000th sample ends the search even when it found film */
            else if (found) {
                if ((st = pk_film_start_register(b, PK_FILM_FORWARD, TR_SPEED_FILM)) != PK_OK) break;
                o->film_found = true;
                film_t0 = pkb_now_ms();
            }
        } else {                                                      /* T4: the film phase */
            if (film_n < TR_CHECK_AFTER) film_n++;
            else {                                                    /* every sensor back at clear film or no film: v >= max_c - 1 (signed) */
                bool all = true;
                for (int i = 0; i < 4; i++) if (!((int)v[i] >= mx[i] - 1)) all = false;
                if (all && ++qual >= TR_END_COUNT) finished = true;
            }
            /* film_n equals 4000 on exactly one sample (it becomes 4001 on the next and stays): the one speed change */
            if (film_n == TR_FAST_AFTER && (st = pk_film_start_register(b, PK_FILM_FORWARD, TR_SPEED_FAST)) != PK_OK) break;
            o->film_samples = film_n;
            o->clear_samples = qual;
            if (!finished && pkb_now_ms() - film_t0 >= TR_FILM_CAP_MS) { st = PK_E_TIMEOUT; break; }
        }
        for (int i = 0; i < 4; i++) mx[i] = sensor_max(h->h[i]);
    }
    o->samples = n;
    if (st == PK_OK && no_film) {
        add_ec(o, 0xC2);                                              /* EC_DXNoFilmFound: motor stop, return (result word stays 0xFF) */
        evaluate(h, n, o);                                            /* report only: TLB evaluates nothing here */
        o->partial = true;
        st = pk_film_stop(b);
        free(h);
        return st;
    }
    if (st != PK_OK) {                                                /* cancelled, the cap, transport or protocol failure: stop the motor, best effort */
        if (motor) (void)pk_film_stop(b);
        evaluate(h, n, o);                                            /* the levels so far and the thresholds they would give (report only) */
        o->partial = true;
        free(h);
        return st;
    }
    /* T5 / T6: the evaluation and the thresholds TLB would write (never written here) */
    evaluate(h, n, o);
    o->result_word = o->swing_flags;                                  /* S+0x394 = 0, then |1 |2 |4 |8 */
    o->clock_top_err = (o->result_word & 1u) != 0;
    o->data_top_err = (o->result_word & 2u) != 0;
    o->clock_bottom_err = (o->result_word & 4u) != 0;
    o->data_bottom_err = (o->result_word & 8u) != 0;
    if (o->result_word) add_ec(o, 0xC5);                              /* EC_DXBadSwing */
    o->complete = true;
    free(h);
    /* T8: wait 1000 ms, then MOTOR 0xA2 */
    unsigned long long end = pkb_now_ms() + TR_STOP_WAIT_MS;
    pk_status wst = PK_OK;
    while (pkb_now_ms() < end && wst == PK_OK) { wst = pkcal_tick(c); pkb_sleep_ms(10); }
    pk_status ss = pk_film_stop(b);
    return wst != PK_OK ? wst : ss;
}
