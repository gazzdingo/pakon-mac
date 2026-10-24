#define _POSIX_C_SOURCE 200809L
/* Session calibration (Task 15): the calibration entry points' bodies and the two scan hooks of S-R32 a / b. Policy, order and numbers are TLB's (docs/re/43-calibration-sequence.md);
 * rulings S-R32, S-R39. Nothing here writes scanner memory (no 0x08 / 0x0B / 0x94..0x98, no EEPROM or flash write; never TLB's destructor Adjust write, the wizard's CalibrationPut*,
 * or AdjustMotorSpeed). Every wait loop reaches pks_keepalive() and pks_cancelled() through cal_tick. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "calib/eeprom.h"
#include "calib/record.h"
#include "session/session_internal.h"

static int bidx(int dpi_base) { return dpi_base == 4 ? 0 : dpi_base == 8 ? 1 : 2; }
static pk_cal_scope scope_of(int dpi_base) { return dpi_base == 4 ? PK_SCOPE_BASE4 : dpi_base == 8 ? PK_SCOPE_BASE8 : PK_SCOPE_BASE16; }

/* ---------------------------------------------------------------- the pkcal_ctx of a session */
/* Every wait loop of a calibration: cancel, then the status pass. While a calibration runs TLB's DX board is in state 4 (RE 33 sec 5): the shared 0x02 / 0x90 pass services it, and film
 * sensed at either sensor aborts the run (RequireDxSensorsDuringLightCalibration = 1, the owner's value; the flags word has bit 0x10 clear for light calibration). */
static pk_status cal_tick(void *u) {
    pk_session *s = (pk_session *)u;
    if (pks_cancelled(s)) return PK_E_CANCELLED;
    if (!s->cal.dx) return pks_keepalive(s);
    pk_status st = pks_scan_poll(s, s->cal.dx);
    if (st != PK_OK) return st;
    if (pk_dx_calibration_abort(s->cal.dx)) {
        snprintf(s->diag, sizeof s->diag, "film was sensed at the entry or exit sensor during the calibration (EC 0x81): clear the film path and calibrate again");
        return PK_E_FILM_IN_GUIDES;
    }
    return PK_OK;
}

/* RE 43 S2 / E1: LIGHT 0x91 [S lo, S hi, 01] at the start, 0x92 at the end. TODO(RE 33 sec 5, branch 0x1002dfcb): whether TLB arms the abort for a scan-initiated calibration was not traced;
 * S-R40 I-4 rules it armed there too. For an in-scan calibration the 0x92 at its end is OURS (RE 41 row 7 lists none; the scan sends its own 0x91 later): S-R40 I-4, harmless. */
static pk_status dx_begin(pk_session *s, int dpi_base, bool ir) {
    pk_dx *d = NULL;
    pk_status st = pk_dx_new(&d);
    if (st != PK_OK) return st;
    const pk_dx_calibration c = { true, true, false };
    st = pk_dx_set_calibration(d, &c);
    const unsigned sp = pks_dx_speed(dpi_base, ir);
    if (st == PK_OK) st = pk_dx_start(s->b, sp, 1);
    if (st != PK_OK) { pk_dx_free(d); (void)pk_dx_stop(s->b); return st; }   /* the 0x91 may have gone out before the failure: stop the DX board, best effort (R1-m1) */
    s->cal.dx = d;
    s->cal.dx_speed = sp;
    return PK_OK;
}

static pk_status dx_end(pk_session *s) {
    if (!s->cal.dx) return PK_OK;
    pk_dx_free(s->cal.dx);
    s->cal.dx = NULL;
    pk_status st = pk_dx_stop(s->b);
    pkb_sleep_ms(20);                                          /* TLB waits 20 ms after 0x92 (FUN_10009da0) */
    return st;
}

static void cal_progress(void *u, int percent, const char *msg) {
    pk_session *s = (pk_session *)u;
    pk_event e;
    memset(&e, 0, sizeof e);
    e.kind = PK_EV_CAL_PROGRESS;
    e.state = pks_state(s);
    e.percent = percent;
    snprintf(e.text, sizeof e.text, "%s", msg);
    pks_emit(s, &e);
}

static pkcal_ctx make_ctx(pk_session *s) {
    pkcal_ctx c;
    memset(&c, 0, sizeof c);
    c.b = s->b;
    c.t = s->t;
    c.model = s->model;
    c.tick = cal_tick;
    c.progress = cal_progress;
    c.user = s;
    c.diag = s->diag;
    c.diag_cap = sizeof s->diag;
    return c;
}

/* ---------------------------------------------------------------- store, chip image, unit key */
void pks_cal_free(pk_session *s) {
    pk_calstore_close(s->cal.store);
    free(s->cal.ee);
    s->cal.store = NULL;
    s->cal.ee = NULL;
}

/* The unit key (S-R23): the model name with spaces as underscores, then the CalWiz serial. pk_eeprom_identify reads the 4-byte serial from the chip once per session and ADOPTS the
 * saved image of that serial (no other transfer); a serial no saved unit has is a different scanner (PK_E_CAL_FOREIGN), and an empty store is PK_E_NOT_FOUND: neither reads the chip in full, that is an explicit command only. Any failure adopts nothing (the unit stays unknown). */
static pk_status prepare(pk_session *s) {
    pks_calstate *c = &s->cal;
    if (c->have_unit) return PK_OK;
    pk_status st = PK_OK;
    if (!c->store && (st = pk_calstore_open(s->calstore_root[0] ? s->calstore_root : NULL, &c->store)) != PK_OK) return st;
    if (!c->ee && !(c->ee = (pk_eeprom *)calloc(1, sizeof *c->ee))) return PK_E_NOMEM;
    unsigned seen = 0;
    if ((st = pk_eeprom_identify(s->b, pkcal_store_root(c->store), c->ee, &seen)) != PK_OK) {
        if (st == PK_E_NOT_FOUND) snprintf(s->diag, sizeof s->diag, "no saved calibration chip image; run the explicit first-read command (hw1 eeprom-read)");
        else if (st == PK_E_CAL_FOREIGN) snprintf(s->diag, sizeof s->diag, "a different scanner (serial %u): run the explicit first-read command for it", seen);
        return st;
    }
    snprintf(c->unit, sizeof c->unit, "%s-%u", c->ee->scanner_type == 0x547 ? "F-135_Plus" : "F-135", c->ee->serial);
    if ((st = pk_calstore_set_local_unit(c->store, c->unit)) != PK_OK) return st;
    c->have_unit = true;
    return PK_OK;
}

/* Session open (owner decision 2026-10-22): the serial read, so the unit is known before any scan. Not fatal: on failure no unit is adopted and a later scan retries the same check. */
void pks_cal_identify(pk_session *s) { (void)prepare(s); }

/* The light settings of a stored calibration; PK_E_CAL_FOREIGN for another unit's, PK_E_NOT_FOUND / PK_E_CORRUPT from the store. */
static pk_status load_light(pk_session *s, const char *id, int dpi_base, bool ir, pk_cal_light *out) {
    pk_calibration *c = NULL;
    pk_status st = pk_calstore_get(s->cal.store, id, &c);
    if (st != PK_OK) return st;
    if (strcmp(pk_calibration_unit(c), s->cal.unit) != 0) st = PK_E_CAL_FOREIGN;
    else if (!pk_calibration_light(c) || pk_calibration_light(c)->dpi_base != dpi_base || pk_calibration_light(c)->ir != ir) st = PK_E_ARG;
    else *out = *pk_calibration_light(c);
    pk_calibration_free(c);
    return st;
}

static void seed_light(pk_session *s, int dpi_base, bool ir, pk_cal_light *out) {
    (void)pk_cal_light_seed(out, dpi_base, ir);
    out->px_offset = s->cal.ee->px_offset[bidx(dpi_base)];
}

/* Whether a stored IR calibration carries "ir_lineage" (pkcal_record_ir_lineage); 0 when it cannot be read. */
static int ir_lineage(pk_session *s, const char *id) {
    pk_calibration *c = NULL;
    if (pk_calstore_get(s->cal.store, id, &c) != PK_OK) return 0;
    int v = pkcal_record_ir_lineage(c);
    pk_calibration_free(c);
    return v;
}

/* The newest usable stored light of a config, with its id; PK_E_NOT_FOUND when there is none. An IR calibration without "ir_lineage" (written before the IR plane was read where
 * TLB reads it, HW 2026-10-22) is not usable: its currents are not TLB's, and a non-full run from them keeps them (TLB raises Current_Ir in the duty search only while the IR maximum
 * is below 10000, FUN_1001ec90 0x1001f2e9), so the next calibration must be a full search (OURS: TLB has no such records; RE 43 sec 4). id still names it (the parent). */
static pk_status newest_light(pk_session *s, int dpi_base, bool ir, pk_cal_light *out, char id[65]) {
    pk_status st = pk_calstore_resolve_ir(s->cal.store, s->cal.unit, scope_of(dpi_base), ir, id);
    if (st != PK_OK) return st;
    if ((st = load_light(s, id, dpi_base, ir, out)) != PK_OK) return st;
    return ir && !ir_lineage(s, id) ? PK_E_NOT_FOUND : PK_OK;
}

/* The time of the last full light search recorded for a config (FullLightCorrections is the one TLB value that survives a restart, RE 43 sec 1): read from the newest native
 * calibration's raw/ob.json, whose "full_utc" every record carries forward. */
static int64_t stored_last_full(pk_session *s, int dpi_base, bool ir) {
    char id[65];
    if (pk_calstore_resolve_ir(s->cal.store, s->cal.unit, scope_of(dpi_base), ir, id) != PK_OK) return 0;
    pk_calibration *c = NULL;
    if (pk_calstore_get(s->cal.store, id, &c) != PK_OK) return 0;
    int64_t t = pkcal_record_last_full(c);
    pk_calibration_free(c);
    return t;
}

/* ---------------------------------------------------------------- one config */
/* The session clocks of a measurement, applied only once its record is stored (R1-m3). */
typedef struct { int bi, ii; int64_t now; bool full; } caltime;
static void apply_times(pks_calstate *cs, const caltime *ct) {
    cs->last_run_s[ct->bi][ct->ii] = ct->now;
    if (ct->full) cs->last_full_s[ct->bi][ct->ii] = ct->now;
}

/* TLB FN_bCalibrateFindCorrections for one (base, ir): measure, store as a new calibration (parent = the selected one), remember the times. `stored` is the light settings a non-full
 * run starts from (NULL = none: a full search from the seeds). On success *light and id are the new calibration's. */
static pk_status cal_one(pk_session *s, int dpi_base, bool ir, bool full, const pk_cal_light *stored, const char *parent, const char *kind, pk_cal_light *light, char id[65],
                         caltime *ct, pk_calibration **defer /* non-NULL: the record is handed back unstored (stored later, lamp off; review m9) */) {
    pks_calstate *cs = &s->cal;
    pk_cal_light start;
    if (full || !stored) {
        seed_light(s, dpi_base, ir, &start);
        full = true;
    } else {
        start = *stored;
        if (!start.px_offset) start.px_offset = cs->ee->px_offset[bidx(dpi_base)];
    }
    if (!start.px_offset) { snprintf(s->diag, sizeof s->diag, "the calibration chip holds no CCD window start for base %d", dpi_base); return PK_E_CORRUPT; }
    pkcal_ctx ctx = make_ctx(s);
    pkcal_job job = { dpi_base, ir, full };
    pkcal_result res;
    const bool own_dx = !cs->dx;                              /* pk_calibrate starts the DX board before its warm-up (TLB's S2 precedes F3); an in-scan calibration starts it here */
    pk_status st = PK_OK;
    if (own_dx) st = dx_begin(s, dpi_base, ir);
    else if (cs->dx_speed != pks_dx_speed(dpi_base, ir)) {   /* a later base: TLB's S2 of its own ForceCorrections call */
        st = pk_dx_start(s->b, pks_dx_speed(dpi_base, ir), 1);
        if (st == PK_OK) cs->dx_speed = pks_dx_speed(dpi_base, ir);
    }
    if (st != PK_OK) return st;
    st = pkcal_measure(&ctx, &job, &start, &res);
    pk_status ds = own_dx ? dx_end(s) : PK_OK;
    if (st == PK_OK && ds != PK_OK) { pkcal_result_free(&res); st = ds; }
    if (st != PK_OK) return st;
    const int64_t now = (int64_t)time(NULL);
    const int bi = bidx(dpi_base), ii = ir ? 1 : 0;
    if (!cs->full_looked_up[bi][ii]) { cs->last_full_s[bi][ii] = stored_last_full(s, dpi_base, ir); cs->full_looked_up[bi][ii] = true; }
    pk_calibration *rec = NULL;
    res.parent_ir_lineage = ir && !full && parent && parent[0] && ir_lineage(s, parent);
    st = pkcal_build_record(&res, cs->unit, kind, parent && parent[0] ? parent : NULL, now, cs->last_full_s[bi][ii], &rec);
    if (st == PK_OK && defer) { *defer = rec; rec = NULL; id[0] = 0; }
    else if (st == PK_OK) st = pk_calstore_put(cs->store, rec, id);
    pk_calibration_free(rec);
    if (st == PK_OK) {
        *light = res.light;
        ct->bi = bi; ct->ii = ii; ct->now = now; ct->full = res.full;
        if (!defer) apply_times(cs, ct);                     /* stored: the session now counts as calibrated */
    }
    pkcal_result_free(&res);
    return st;
}

/* ---------------------------------------------------------------- the scan hooks (S-R32 a / b) */
pk_status pks_cal_resolve(pk_session *s, const pk_scan_config *cfg, pk_cal_light *out, char id[65]) {
    id[0] = 0;
    s->cal.pinned = false;
    pk_status st = prepare(s);
    if (st != PK_OK) return st;
    if (strcmp(cfg->calibration_pin, "auto") == 0) {
        st = newest_light(s, cfg->dpi_base, cfg->ir, out, id);
        if (st == PK_OK) return PK_OK;
        if (st != PK_E_NOT_FOUND) return st;
        id[0] = 0;                                           /* (an IR calibration without "ir_lineage" counts as none: newest_light) */
        seed_light(s, cfg->dpi_base, cfg->ir, out);          /* nothing usable stored: the scan calibrates first (a full search, pks_cal_scan_due) */
        return PK_OK;
    }
    s->cal.pinned = true;
    st = load_light(s, cfg->calibration_pin, cfg->dpi_base, cfg->ir, out);
    if (st == PK_OK) snprintf(id, 65, "%s", cfg->calibration_pin);
    return st;
}

pk_status pks_cal_scan_due(pk_session *s, const pk_scan_config *cfg, pk_cal_light *light, char id[65]) {
    pks_calstate *cs = &s->cal;
    if (!cs->have_unit) return PK_OK;                        /* pks_cal_resolve prepares the unit before the worker starts; a start with explicit light settings (internal entry) never calibrates */
    const int bi = bidx(cfg->dpi_base), ii = cfg->ir ? 1 : 0;
    if (!cs->full_looked_up[bi][ii]) { cs->last_full_s[bi][ii] = stored_last_full(s, cfg->dpi_base, cfg->ir); cs->full_looked_up[bi][ii] = true; }
    const int64_t now = (int64_t)time(NULL);
    pk_cal_policy pol;
    pthread_mutex_lock(&s->mu);
    pol = cs->policy;
    pthread_mutex_unlock(&s->mu);
    pk_cal_state st = { cs->last_run_s[bi][ii], cs->last_full_s[bi][ii], false };   /* a serial change is a different unit key here, so it never meets a stored full-search time */
    pk_cal_due due = pk_calibration_due(&pol, &st, now);
    const bool have_stored = id[0] != 0;
    if (!have_stored) { due.due = true; due.full_search = true; due.reason = "no calibration stored"; }   /* RE 43 sec 1: TLB never scans without tables */
    if (!due.due) return PK_OK;
    bool full = due.full_search;
    if (cs->pinned && have_stored) full = false;             /* a pinned calibration is never replaced by a full LED-current search from the seeds; C7 / C8 still re-search its duties, currents and gains from its values */
    pks_emit_msg(s, PK_EV_CAL_PROGRESS, PK_OK, 0, "calibrating before the scan: %s%s", due.reason, full ? " (full light search)" : "");
    pk_cal_light nl;
    char nid[65];
    caltime ct;
    const bool hov = s->host_overflow;                       /* host status bits seen while calibrating are not the scan's warnings (R1-m2) */
    const unsigned hun = s->host_unknown;
    pk_status r = cal_one(s, cfg->dpi_base, cfg->ir, full, have_stored ? light : NULL, have_stored ? id : NULL, "session", &nl, nid, &ct, NULL);
    s->host_overflow = hov;
    s->host_unknown = hun;
    if (r != PK_OK) return r;
    if ((r = pk_host_fifo_reset(s->b)) != PK_OK) return r;   /* RE 41 row 7: the calibration ends with HOST 0x84 = 2 + LIGHT 0x8A, so no calibration-width line reaches the scan stream */
    *light = nl;
    memcpy(id, nid, 65);
    return PK_OK;
}

/* ---------------------------------------------------------------- pk_calibrate / pk_track_test bodies */
pk_status pks_cal_track(pk_session *s, pk_film_format f, pk_track_result *out) {
    pkcal_ctx ctx = make_ctx(s);
    return pkcal_track_test(&ctx, f, out);
}

static pk_status run_inner(pk_session *s, const pk_cal_request *req, char out_id[65]) {
    pk_status st = prepare(s);
    if (st != PK_OK) return st;
    /* the gate must be empty (RE 43 sec 7; the DX sensors, read only) */
    pk_film_sensors fs;
    if ((st = pk_film_sense(s->b, &fs)) != PK_OK) return st;
    if (fs.entry || fs.exit) { snprintf(s->diag, sizeof s->diag, "film is over the entry or exit sensor: clear the film path before calibrating"); return PK_E_FILM_IN_GUIDES; }
    const bool gain = req->kind == PK_CAL_GAIN;
    /* PSI's Gain test runs FilmTrackTest only when its "Track Test" box is also ticked (RE 48b sec 1.2 row 8, OBSERVED); the default is unticked, so no Track test runs here. The
     * separate read-only pk_track_test is the app's Track job. (An empty path would run the Track test to its 100000-sample cap with the film motor on.) */
    /* RE 43 S2 precedes F3: the DX board is started before the lamp warm-up. The warm-up itself polls only the lamp bits, so film that arrived during it is picked up by one explicit 0x90
     * read afterwards (the abort of RE 33 sec 5 needs a packet to be fed). */
    static const int FIRST[3] = { 16, 8, 4 }, FMASK[3] = { PK_CAL_BASE_16, PK_CAL_BASE_8, PK_CAL_BASE_4 };
    int first_base = 16;
    for (int k = 0; k < 3; k++) if (req->dpi_base_mask & FMASK[k]) { first_base = FIRST[k]; break; }
    if ((st = dx_begin(s, first_base, req->ir)) != PK_OK) return st;
    if ((st = pks_warm_lamp(s)) != PK_OK) return st;
    if (pks_cancelled(s)) return PK_E_CANCELLED;
    {
        uint8_t nib = 0;
        if ((st = pk_dx_read_packet(s->b, s->cal.dx, &nib)) != PK_OK) return st;
        if (pk_dx_calibration_abort(s->cal.dx)) {
            snprintf(s->diag, sizeof s->diag, "film was sensed at the entry or exit sensor during the lamp warm-up (EC 0x81): clear the film path and calibrate again");
            return PK_E_FILM_IN_GUIDES;
        }
    }
    pks_set_state(s, PK_S_SCANNING);                         /* the lamp is warm; the measurement runs (the state tells the app the boards are busy) */
    static const int BASES[3] = { 16, 8, 4 };
    static const int MASK[3] = { PK_CAL_BASE_16, PK_CAL_BASE_8, PK_CAL_BASE_4 };
    pk_status first_err = PK_OK, run = PK_OK;
    pk_calibration *recs[3] = { NULL, NULL, NULL };
    caltime cts[3];
    for (int k = 0; k < 3 && run == PK_OK; k++) {
        if (!(req->dpi_base_mask & MASK[k])) continue;
        const int base = BASES[k];
        if (pks_cancelled(s)) { run = PK_E_CANCELLED; break; }
        pk_cal_light stored, nl;
        char pid[65] = "", nid[65];
        bool have = newest_light(s, base, req->ir, &stored, pid) == PK_OK;
        const int bi = bidx(base), ii = req->ir ? 1 : 0;
        if (!s->cal.full_looked_up[bi][ii]) { s->cal.last_full_s[bi][ii] = stored_last_full(s, base, req->ir); s->cal.full_looked_up[bi][ii] = true; }
        pk_cal_state cst = { 1, s->cal.last_full_s[bi][ii], false };       /* "just ran": only the 20 h rule can make a forced run full */
        pk_cal_policy pol;
        pthread_mutex_lock(&s->mu);
        pol = s->cal.policy;
        pthread_mutex_unlock(&s->mu);
        pk_cal_due due = pk_calibration_due(&pol, &cst, (int64_t)time(NULL));
        bool full = gain || !have || due.full_search;          /* the Gain test forces CALIBRATE_Light */
        char msg[96];
        snprintf(msg, sizeof msg, "calibrating base %d%s%s", base, req->ir ? " IR" : "", full ? " (full light search)" : "");
        cal_progress(s, 2, msg);
        /* the record is kept in memory and stored once the lamp is out: a store write (fsyncs) must not sit between lit-lamp keep-alives (review m9) */
        st = cal_one(s, base, req->ir, full, have ? &stored : NULL, pid, gain ? "gain" : "session", &nl, nid, &cts[k], &recs[k]);
        if (st == PK_OK) continue;
        if (st == PK_E_CAL_LIGHT && gain) {                    /* EC_InsufficientLight / the gain limit: the previous calibration is kept, the others are still tried (RE 43 sec 7) */
            if (first_err == PK_OK) first_err = st;
            pks_emit_msg(s, PK_EV_WARNING, st, 0, "base %d: %s", base, s->diag[0] ? s->diag : "not enough light");
            continue;
        }
        run = st;
    }
    /* E1: DX stop, then the lamp out; then the store writes */
    (void)dx_end(s);
    pk_status lo = pk_light_lamp_off(s->b);
    s->end_lamp_done = lo == PK_OK;
    for (int k = 0; k < 3; k++) {
        if (!recs[k]) continue;
        char nid[65];
        pk_status ps = pk_calstore_put(s->cal.store, recs[k], nid);
        if (ps == PK_OK) { memcpy(out_id, nid, 65); apply_times(&s->cal, &cts[k]); }   /* calibrated only once stored (R1-m3) */
        else if (run == PK_OK) run = ps;
        pk_calibration_free(recs[k]);
    }
    if (run == PK_OK && lo != PK_OK) run = lo;
    return run != PK_OK ? run : first_err;
}

pk_status pks_cal_run(pk_session *s, const pk_cal_request *req, char out_id[65]) {
    pk_status st = run_inner(s, req, out_id);
    (void)dx_end(s);                                         /* every early return: 0x92 best effort (a no-op once the normal path stopped it) */
    return st;
}
