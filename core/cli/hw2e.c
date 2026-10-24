#define _POSIX_C_SOURCE 200809L
/* pakon hw2e: the early owner hardware tests (calibrate, read-only track, raw scan). Only the session and calibration API is used:
 * nothing here writes scanner memory (the write guard under the session refuses it anyway). Ctrl-C is flag-only; a small watcher
 * thread turns the flag into pk_session_cancel, so the session's own cancel stops the motor and switches the lamp off. */
#include <errno.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include "cli.h"
#include "pakon/calstore.h"
#include "pakon/session.h"
#include "transport/trace.h"
#include "util/util.h"

#define INTR (g_cli_intr != 0)

/* ------------------------------------------------------------------ what the trace shows about light-board register 0x02 (same count as hw1) */
static void trace_observation(const char *dir, uint8_t light) {
    if (!dir) { cli_say("No trace was recorded, so the light-board status replies could not be counted."); return; }
    pkt_event *ev = NULL;
    size_t n = 0;
    int fd = -1;
    uint64_t ssz = 0;
    pk_status st = pkt_load(dir, &ev, &n, &fd, &ssz);
    if (st != PK_OK) { cli_say("Could not read back the trace to count status replies (%s).", pk_status_str(st)); return; }
    unsigned reads = 0, ev7 = 0, silent = 0, packets = 0;
    int armed = 0;
    for (size_t i = 0; i < n; i++) {
        const pkt_event *e = &ev[i];
        if (e->kind == PKT_BULK_OUT) {
            packets++;
            armed = (e->data && e->len >= 5 && e->data[0] == 1 && e->data[2] == light && e->data[4] == 0x02 && e->status == PK_OK);
        } else if (e->kind == PKT_BULK_IN) {
            if (armed && e->data && e->len >= 5 && e->status == PK_OK) {
                reads++;
                if (e->data[3] & 0x80) ev7++;
                else if (e->data[4] != 0) silent++;
            }
            armed = 0;
        }
    }
    pkt_free_events(ev, n);
    if (fd >= 0) close(fd);
    if (reads == 0) return;
    cli_say("Light-board status replies in this run: %u. Of these %u carried an event flag, and %u had a non-zero value WITHOUT the event flag (write that last number in the results file).", reads, ev7, silent);
    cli_detail("light board register 0x02 reads: %u; reply status bit 7 set: %u; value non-zero with status bit 7 clear: %u; packets sent in total: %u", reads, ev7, silent, packets);
}

/* ------------------------------------------------------------------ Ctrl-C watcher */
typedef struct { pk_session *s; volatile int stop; pthread_t th; bool started; } watcher;
static void *watch_main(void *p) {
    watcher *w = (watcher *)p;
    bool sent = false;
    while (!w->stop) {
        if (INTR && !sent) { (void)pk_session_cancel(w->s); sent = true; }
        else if (INTR) (void)pk_session_cancel(w->s);        /* idempotent: a further Ctrl-C is just as safe */
        cli_real_sleep(50);
        if (g_cli_intr && !w->stop) { /* keep polling */ }
    }
    return NULL;
}
static void watch_begin(watcher *w, pk_session *s) {
    w->s = s; w->stop = 0;
    w->started = pthread_create(&w->th, NULL, watch_main, w) == 0;
}
static void watch_end(watcher *w) {
    w->stop = 1;
    if (w->started) pthread_join(w->th, NULL);
    w->started = false;
}

/* ------------------------------------------------------------------ the session */
typedef struct {
    cli_session cs;
    pk_session *sess;
    char home[1024], work[1100], vendor[1100], unit[80];
    const pk_model *model;
} h2;

static int h2_open(cli_opts *o, h2 *h) {
    memset(h, 0, sizeof *h);
    if (o->replay) { cli_say("hw2e commands do not run against a recording (--replay)."); return 2; }
    if (cli_home(o, h->home, sizeof h->home)) { cli_say("Cannot find your home folder; use --home."); return 1; }
    snprintf(h->work, sizeof h->work, "%s/session", h->home);
    snprintf(h->vendor, sizeof h->vendor, "%s/vendor", h->home);
    if (cli_open(o, CLI_LOADED, &h->cs)) return 1;
    char why[300];
    h->model = cli_refine_from_store(o, h->cs.usb_model, h->unit, why, sizeof why);
    if (!h->model) { cli_say("%s", why); cli_close(&h->cs); return 1; }
    pk_session_opts so;
    pk_session_opts_default(&so);
    so.work_dir = h->work; so.calstore_root = h->home; so.vendor_root = h->vendor;
    so.model = h->model->id;
    so.leds_enabled = !o->no_leds;
    pk_status st = pk_session_open(h->cs.t, &so, &h->sess);
    if (st != PK_OK) {
        cli_report_status("Cannot open the scan session", st, NULL);
        if (st == PK_E_BUSY) cli_say("Another copy of pakon (or PSI) may be using the scanner, or a previous run is still stopping.");
        cli_close(&h->cs);
        return 1;
    }
    cli_say("Scan session open on the %s.", h->model->name);
    return 0;
}
static void h2_close(h2 *h) {
    if (h->sess) pk_session_close(h->sess);       /* lamp off, LEDs off, marker cleared */
    h->sess = NULL;
    cli_close(&h->cs);
}

/* ------------------------------------------------------------------ events */
typedef struct { unsigned black_rounds, warnings, dx_events, errors; int last_warm; uint64_t lines; unsigned long long last_lines_ms; } evstate;
static void on_event(void *user, const pk_event *e) {
    evstate *x = (evstate *)user;
    switch (e->kind) {
    case PK_EV_STATE: {
        static const char *const nm[] = { "idle", "warming up the lamp", "ready", "scanning", "finishing the scan", "stopping", "FAULTED" };
        cli_say("Scanner state: %s.", (unsigned)e->state < 7 ? nm[e->state] : "?");
        break;
    }
    case PK_EV_WARMUP_PROGRESS:
        if (e->percent >= x->last_warm + 10 || e->percent >= 100) { x->last_warm = e->percent; cli_say("Lamp warm-up: %d%%", e->percent); }
        break;
    case PK_EV_LAMP_HEALTH: if (e->code) cli_say("Lamp health flags: 0x%X (tell Claude if the lamp looks wrong).", (unsigned)e->code); break;
    case PK_EV_CAL_PROGRESS:
        if (!strncmp(e->text, "black level round", 17)) x->black_rounds++;
        cli_say("Calibration %3d%%: %s", e->percent, e->text);
        break;
    case PK_EV_LINES: {
        unsigned long long now = cli_now_ms();
        x->lines = e->lines;
        if (now - x->last_lines_ms >= 5000) { x->last_lines_ms = now; cli_say("Scanned %llu lines so far.", (unsigned long long)e->lines); }
        break;
    }
    case PK_EV_WARNING: {
        x->warnings++;
        pk_warning_text w = pk_warning_sentence(e->code);
        cli_say("Warning: %s%s%s", e->text, w.english && w.english[0] ? " -- " : "", w.english ? w.english : "");
        break;
    }
    case PK_EV_DX: x->dx_events++; cli_say("Film: %s", e->text); break;
    case PK_EV_FILM_SENSE: case PK_EV_EJECT: break;
    case PK_EV_FW_VERSION_WARNING: cli_say("Note: %s", e->text); break;
    case PK_EV_ERROR: x->errors++; cli_say("Problem: %s (%s)", e->text, cli_explain(e->status)); break;
    }
}

static int finish_code(pk_status st) { return st == PK_OK ? 0 : st == PK_E_CANCELLED ? 130 : 1; }

static void explain_cal_failure(pk_status st) {
    cli_say("The calibration did not finish: %s", cli_explain(st));
    if (st == PK_E_CAL_LIGHT) cli_say("One of the LED colours could not be made bright enough. Check that the scanner really is EMPTY, that the film path is clean, and that the lamp is warm; then tell Claude. Do not keep retrying.");
    else if (st == PK_E_NOT_FOUND) cli_say("There is no saved calibration image or store for this scanner under your home folder. Run  pakon hw1 eeprom-read  first (only if it has never been run), or use the same --home as before.");
    else if (st == PK_E_BUSY) cli_say("The session or the scanner was busy. Close any other program using the scanner and try again.");
    else if (st == PK_E_FILM_IN_GUIDES || st == PK_E_NO_FILM) cli_say("Film seems to be in the scanner. Take it out and try again.");
    else if (st == PK_E_CANCELLED) cli_say("You pressed Ctrl-C; the motor and lamp were stopped.");
    else cli_say("Tell Claude and copy the lines above.");
}

/* ------------------------------------------------------------------ calibrate */
static void show_light(const char *id, const char *home, const evstate *x) {
    pk_calstore *cs = NULL;
    pk_calibration *c = NULL;
    if (pk_calstore_open(home, &cs) != PK_OK) { cli_say("Saved as calibration %s (could not reopen the store to show it).", id); return; }
    if (pk_calstore_get(cs, id, &c) != PK_OK) { cli_say("Saved as calibration %s (could not read it back to show it).", id); pk_calstore_close(cs); return; }
    const pk_cal_light *l = pk_calibration_light(c);
    static const char *const ch[4] = { "red", "green", "blue", "IR" };
    cli_say("Result for base %d%s (calibration kind: %s):", l->dpi_base, l->ir ? ", IR" : "", pk_calibration_kind(c));
    /* an IR calibration is TLB's ColNegIr set: its own black level, and R, G, B re-tuned with the IR LED lit, plus the IR LED (RE 43 sec 4) */
    cli_say("  Black-level (AFE) offsets: red %d, green %d, blue %d; gain codes %u, %u, %u.", l->afe_offset[0], l->afe_offset[1], l->afe_offset[2], l->afe_gain[0], l->afe_gain[1], l->afe_gain[2]);
    cli_say("  Black-level search ran %u round(s) (at most 8). %s", x->black_rounds,
            x->black_rounds >= 8 ? "It used all 8: the offsets probably did NOT settle inside the target band (not an error; write it down)." :
            x->black_rounds == 0 ? "It needed no change from the start values, or it was not run for this calibration." : "It stopped early, so the offsets settled.");
    for (int k = 0; k < (l->ir ? 4 : 3); k++)
        cli_say("  %-5s LED current step %u, duty with film %.4f, duty empty gate %.4f", ch[k], l->current[k], l->duty_film[k], l->duty_open[k]);
    cli_say("  Integration 0x%X, CCD window start %u.", l->integration, l->px_offset);
    cli_say("  Low-light flag: %s", l->low_light ? "SET (a gain code reached 0x33 or more: the lamp is dim; write it down)" : "not set (light is fine)");
    cli_detail("calibration id %s", id);
    pk_calibration_free(c);
    pk_calstore_close(cs);
}

static int calibrate_pass(cli_opts *o, h2 *h, bool ir) {
    pk_cal_request rq;
    memset(&rq, 0, sizeof rq);
    rq.kind = PK_CAL_SESSION; rq.dpi_base_mask = PK_CAL_BASE_16; rq.film_colour_mask = PK_CAL_COLOUR_NEG; rq.ir = ir;
    evstate x;
    memset(&x, 0, sizeof x);
    char id[65] = "";
    cli_say(ir ? "Calibrating IR at base 16 (the lamp warms up first, then the light search runs; it can take several minutes)..."
               : "Calibrating RGB at base 16 (the lamp warms up first, then the light search runs; it can take several minutes)...");
    watcher w;
    watch_begin(&w, h->sess);
    pk_status st = pk_calibrate(h->sess, &rq, on_event, &x, id);
    watch_end(&w);
    (void)o;
    if (st != PK_OK) { explain_cal_failure(st); return finish_code(st); }
    show_light(id, h->home, &x);
    cli_say("Calibration id saved: %s", id);
    cli_say("Calibration store: %s/units/%s/calibration/", h->home, h->unit);
    return 0;
}

static int cmd_calibrate(cli_opts *o) {
    h2 h;
    int rc = h2_open(o, &h);
    if (rc) return rc;
    cli_say("The scanner must be EMPTY (no film in the entrance or exit). Press Ctrl-C at any time to stop safely.");
    rc = calibrate_pass(o, &h, false);
    if (rc == 0 && o->ir) rc = calibrate_pass(o, &h, true);
    if (rc == 0) cli_say("Calibration finished. Nothing was written to the scanner's memory.");
    uint8_t light = h.model->roles.light;
    h2_close(&h);
    trace_observation(o->trace, light);
    return rc;
}

/* ------------------------------------------------------------------ track (read only) */
static void flag_line(const char *name, bool bad) { cli_say("  %-26s %s", name, bad ? "ERROR (swing too small)" : "ok"); }

/* The levels and thresholds, also after a stop before TLB's evaluation (no film, Ctrl-C, the time limit): then they are what the samples
 * so far give, marked as partial. */
static void track_levels(const pk_track_result *r) {
    static const char *const SN[4] = { "TopClock", "TopData", "BottomClock", "BottomData" };
    cli_say("Film found: %s. Film-phase readings: %u (the end check starts after 4001); readings with all four sensors clear again: %u of the 72 that end the test.",
            r->film_found ? "yes" : "NO (every sensor must drop below its no-film level minus 5 at the same time)", r->film_samples, r->clear_samples);
    if (r->level_max[0] < 0) { cli_say("Too few sensor readings to work any level out."); return; }
    if (r->partial) cli_say("PARTIAL: the test stopped before its own evaluation. The values below come from the %u readings taken so far.", r->samples);
    cli_say("Sensor (0x93) levels measured, per sensor:");
    for (int k = 0; k < 4; k++)
        cli_say("  %-12s min %3d  mode %3d  max %3d  swing %3d  swing check %s", SN[k], r->level_min[k], r->level_mode[k], r->level_max[k], r->swing[k],
                (r->swing_flags >> k) & 1u ? "FAILS" : "passes");
    static const int BOARD[4] = { 248, 128, 7, 0 };
    cli_say("DX thresholds: what PSI WOULD store from %s, beside what the board holds now (from the EEPROM dump):", r->partial ? "these readings" : "this strip");
    cli_say("  %-12s %12s %12s", "", "would store", "board has");
    for (int k = 0; k < 4; k++) cli_say("  %-12s %12d %12d", SN[k], r->thresholds[k], BOARD[k]);
    cli_say("No-film thresholds it would store: %d, %d, %d, %d", r->no_film_thresholds[0], r->no_film_thresholds[1], r->no_film_thresholds[2], r->no_film_thresholds[3]);
    if (r->swing_flags) cli_say("PSI stores nothing when any swing check fails.");
    cli_say("NOTHING WAS WRITTEN: the thresholds above were only calculated and shown. The scanner's stored thresholds are unchanged.");
}

static int cmd_track(cli_opts *o) {
    h2 h;
    int rc = h2_open(o, &h);
    if (rc) return rc;
    cli_say("Track test (READ ONLY). Load the Gold 400 strip as the F-135 manual says. Press Ctrl-C at any time to stop safely; the levels so far are shown.");
    cli_say("When the strip has gone through and stops with its tail in the exit, lift it out: the test ends once all four sensors see no film again.");
    cli_say("If the sensors never all see the film, the test ends by itself after 100000 readings (several minutes) with \"no film found\", as PSI's does.");
    pk_track_result r;
    memset(&r, 0, sizeof r);
    watcher w;
    watch_begin(&w, h.sess);
    pk_status st = pk_track_test(h.sess, PK_FILM_35MM, &r);
    watch_end(&w);
    if (st != PK_OK) {
        cli_say("The track test did not finish: %s", cli_explain(st));
        if (st == PK_E_NO_FILM) cli_say("No film was found. Load the strip and run it again.");
        else if (st == PK_E_FILM_IN_GUIDES) cli_say("Film is in the entry or exit path in a way the test does not allow.");
        else if (st == PK_E_TIMEOUT && r.film_found) cli_say("The film phase reached its time limit before all four sensors saw no film again (was the strip lifted out?).");
        else if (st != PK_E_CANCELLED) cli_say("Tell Claude and copy the lines above.");
        if (r.samples) track_levels(&r);
        rc = finish_code(st);
    } else {
        cli_say("Test %s (%u sensor readings, result word 0x%X).", r.complete ? "completed" : "STOPPED EARLY (no evaluation by the test itself)", r.samples, r.result_word);
        if (r.complete) {
            cli_say("Error flags:");
            flag_line("Top clock", r.clock_top_err); flag_line("Top data", r.data_top_err);
            flag_line("Bottom clock", r.clock_bottom_err); flag_line("Bottom data", r.data_bottom_err);
            cli_say("FilmEntry error: %s; FilmExit error: %s (the library never sets these two).", r.film_entry_err ? "yes" : "no", r.film_exit_err ? "yes" : "no");
        }
        if (r.n_ec == 0) cli_say("EC_DX codes: none");
        for (size_t i = 0; i < r.n_ec && i < 8; i++)
            cli_say("EC_DX code 0x%02X%s", r.ec_codes[i], r.ec_codes[i] == 0xC2 ? " (no DX film found)" : r.ec_codes[i] == 0xC5 ? " (bad swing)" : "");
        track_levels(&r);
    }
    uint8_t light = h.model->roles.light;
    h2_close(&h);
    trace_observation(o->trace, light);
    return rc;
}

/* ------------------------------------------------------------------ scan */
static int mkdirs(const char *p) {
    char b[1100];
    snprintf(b, sizeof b, "%s", p);
    for (char *c = b + 1; *c; c++)
        if (*c == '/') { *c = 0; if (mkdir(b, 0777) && errno != EEXIST) return -1; *c = '/'; }
    return (mkdir(b, 0777) && errno != EEXIST) ? -1 : 0;
}
static bool exists(const char *p) { struct stat st; return stat(p, &st) == 0; }

/* default <date>-<n> under ~/Pictures/PakonMac-raw */
static int default_base(char *out, size_t cap) {
    const char *home = getenv("HOME");
    if (!home || !*home) return 1;
    char dir[900], day[16];
    snprintf(dir, sizeof dir, "%s/Pictures/PakonMac-raw", home);
    if (mkdirs(dir)) return 1;
    time_t t = time(NULL);
    struct tm tm;
    localtime_r(&t, &tm);
    strftime(day, sizeof day, "%Y-%m-%d", &tm);
    for (int n = 1; n < 1000; n++) {
        char raw[1100], js[1100];
        snprintf(out, cap, "%s/%s-%d", dir, day, n);
        snprintf(raw, sizeof raw, "%s.raw", out); snprintf(js, sizeof js, "%s.json", out);
        if (!exists(raw) && !exists(js)) return 0;
    }
    return 1;
}

static void sidecar_summary(const char *json_path) {
    FILE *f = fopen(json_path, "rb");
    if (!f) { cli_say("Sidecar: %s (could not be read back).", json_path); return; }
    char *buf = (char *)malloc(1 << 20);
    size_t n = buf ? fread(buf, 1, (1 << 20) - 1, f) : 0;
    fclose(f);
    if (buf) {
        buf[n] = 0;
        const char *k = strstr(buf, "\"line_count\"");
        if (k && (k = strchr(k, ':'))) cli_say("Sidecar records %lld lines.", atoll(k + 1));
        cli_say("Sidecar says the scan %s.", strstr(buf, "\"complete\":true") || strstr(buf, "\"complete\": true") ? "COMPLETED" : "did NOT complete");
    }
    free(buf);
}

static int cmd_scan(cli_opts *o, int npos, const char **pos) {
    char base[1100];
    const char *want = o->out ? o->out : (npos >= 3 ? pos[2] : NULL);
    int base_dpi = o->base ? o->base : 16;
    if (base_dpi != 4 && base_dpi != 8 && base_dpi != 16) { cli_say("--base must be 4, 8 or 16."); return 2; }
    if (o->strips != 0 && o->strips != 4 && o->strips != 5 && o->strips != 6) { cli_say("--strips must be 0 (whole roll), 4, 5 or 6."); return 2; }
    if (want) {
        snprintf(base, sizeof base, "%s", want);
        size_t l = strlen(base);
        if (l > 4 && !strcmp(base + l - 4, ".raw")) base[l - 4] = 0;
        char *sl = strrchr(base, '/');
        if (sl && sl != base) { *sl = 0; if (mkdirs(base)) { cli_say("Cannot create the folder %s.", base); return 1; } *sl = '/'; }
    } else if (default_base(base, sizeof base)) { cli_say("Cannot make the default folder ~/Pictures/PakonMac-raw."); return 1; }
    char rawp[1120], jsp[1120];
    snprintf(rawp, sizeof rawp, "%s.raw", base); snprintf(jsp, sizeof jsp, "%s.json", base);
    if (exists(rawp) || exists(jsp)) { cli_say("%s already exists; choose another name (nothing was overwritten).", exists(rawp) ? rawp : jsp); return 1; }

    h2 h;
    int rc = h2_open(o, &h);
    if (rc) return rc;
    pk_scan_config cfg;
    pk_status st = pk_scan_config_default(h.model, &cfg);
    if (st == PK_OK) {
        cfg.dpi_base = base_dpi;
        cfg.strip_mode = (pk_strip_mode)o->strips;
        if (o->ir) { cfg.ir = true; cfg.scan_control |= PK_SC_SCRATCH_REMOVAL; }
        snprintf(cfg.calibration_pin, sizeof cfg.calibration_pin, "auto");
        st = pk_scan_config_validate(h.model, &cfg, NULL, false);
    }
    if (st != PK_OK) {
        cli_say("This scan setting is not possible on the %s: %s", h.model->name, cli_explain(st));
        h2_close(&h);
        return st == PK_E_UNSUPPORTED ? 1 : 2;
    }
    cli_say("Raw scan: base %d%s, %s, calibration \"auto\" (it calibrates first if needed, which can take minutes).", cfg.dpi_base, cfg.ir ? " with IR" : "",
            o->strips ? "multi-strip" : "whole roll");
    cli_say("Writing %s and %s", rawp, jsp);
    cli_say("Insert the film when the scanner asks (it waits up to %u seconds). Press Ctrl-C at any time to stop safely.", cfg.no_film_timeout_s);
    evstate x;
    memset(&x, 0, sizeof x);
    watcher w;
    watch_begin(&w, h.sess);
    st = pk_session_start(h.sess, base, &cfg, on_event, &x);
    pk_status fin = PK_OK;
    if (st == PK_OK) st = pk_session_wait(h.sess, &fin), st = st == PK_OK ? fin : st;
    watch_end(&w);
    if (st != PK_OK) {
        cli_say("The scan did not finish: %s", cli_explain(st));
        if (st == PK_E_NOT_FOUND) cli_say("There is no stored calibration and automatic calibration could not run. Run  pakon hw2e calibrate  first.");
        else if (st == PK_E_CAL_LIGHT) cli_say("Calibration could not light a channel. Empty the scanner and run  pakon hw2e calibrate  and tell Claude.");
        else if (st != PK_E_CANCELLED) cli_say("Tell Claude and copy the lines above.");
        rc = finish_code(st);
    } else cli_say("The scan finished.");
    cli_say("Summary: %u strip(s) reported by the DX reader, %llu lines streamed, %u warning(s), %u problem(s).", x.dx_events, (unsigned long long)x.lines, x.warnings, x.errors);
    if (exists(jsp)) { sidecar_summary(jsp); cli_say("Sidecar: %s", jsp); }
    if (exists(rawp)) cli_say("Raw data: %s", rawp);
    /* PSI's scan end leaves the film LED blinking yellow ("remove film") while film is over a sensor; closing the session would switch it off. The session's idle status thread releases it
     * when it sees both sensors clear (RE 47): stay open until then, or until Ctrl-C (a Ctrl-C that already stopped the scan does not wait). */
    if (!INTR && pk_session_remove_film_pending(h.sess)) {
        cli_say(o->no_leds ? "Remove the film" : "Remove the film (the light is blinking)");
        cli_say("The session stays open until the scanner sees the film is gone. Press Ctrl-C to close it now.");
        while (!INTR && pk_session_remove_film_pending(h.sess)) cli_real_sleep(100);
        if (INTR) { g_cli_intr = 0; cli_say("Closing the session."); }
        else if (pk_session_state(h.sess) != PK_S_IDLE || !pk_session_idle_alive(h.sess)) cli_say("The scanner stopped answering or the session faulted, so the film cannot be watched any more. Closing the session; check that the film is out.");
        else cli_say("Film removed");
    }
    uint8_t light = h.model->roles.light;
    h2_close(&h);
    trace_observation(o->trace, light);
    return rc;
}

int cli_cmd_hw2e(cli_opts *o, int npos, const char **pos) {
    if (npos < 2) { fputs("usage: pakon hw2e calibrate [--ir] | track | scan [PATH] [--ir] [--base 8|4] [--strips 0|4|5|6]  (each with --trace DIR)\n", stderr); return 2; }
    int rc;
    /* the whole console output also goes to <trace>.log, next to the trace folder, so an interrupted run keeps what it printed */
    char logp[1200];
    bool logging = false;
    if (o->trace && *o->trace) {
        size_t n = strlen(o->trace);
        while (n > 1 && o->trace[n - 1] == '/') n--;
        snprintf(logp, sizeof logp, "%.*s.log", (int)n, o->trace);
        logging = cli_log_open(logp) == 0;
        if (logging) cli_say("This run's output is also saved to %s", logp);
        else cli_say("Could not open %s for the output log; carrying on without it.", logp);
    }
    if (!strcmp(pos[1], "calibrate")) rc = cmd_calibrate(o);
    else if (!strcmp(pos[1], "track")) rc = cmd_track(o);
    else if (!strcmp(pos[1], "scan")) rc = cmd_scan(o, npos, pos);
    else { fprintf(stderr, "pakon hw2e: unknown step %s (calibrate, track, scan)\n", pos[1]); cli_log_close(); return 2; }
    cli_log_close();
    return g_cli_intr && rc == 0 ? 130 : rc;
}
