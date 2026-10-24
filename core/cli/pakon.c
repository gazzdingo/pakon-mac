#define _POSIX_C_SOURCE 200809L
/* pakon: the minimal command line of Task 10 (ruling C18): detect, load, vendor import, film, hw1. Task 22 extends it.
 * Output style: a plain sentence for the owner, then the technical detail on indented lines below it. */
#include <dirent.h>
#include <errno.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include "cli.h"
#include "calib/eeprom.h"
#include "device/eeprom_store.h"
#include "util/util.h"

#define LIBPAKON_VERSION "libpakon-rewrite-v2"

/* ------------------------------------------------------------------ small helpers */
volatile sig_atomic_t g_cli_intr = 0;
static void on_sigint(int sig) {
    (void)sig;
    g_cli_intr = 1;            /* flag only: every Ctrl-C lets the cleanup path stop the motor and switch the lamp off;
                                * Ctrl-\ (SIGQUIT) is the hard kill for a hung tool (HW-1 re-review R-I1) */
}
void cli_install_signals(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_sigint;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, NULL);      /* no SA_RESTART: blocking calls return so the flag is seen; the cleanup path then stops the motor and the lamp */
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);
    signal(SIGPIPE, SIG_IGN);
}

void cli_real_sleep(unsigned ms) {
    struct timespec ts = { (time_t)(ms / 1000u), (long)(ms % 1000u) * 1000000L };
    while (nanosleep(&ts, &ts) != 0 && errno == EINTR) {
        if (g_cli_intr) break;
    }
}
unsigned long long cli_now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (unsigned long long)ts.tv_sec * 1000ull + (unsigned long long)(ts.tv_nsec / 1000000L);
}
bool cli_wait(const cli_opts *o, unsigned ms) {
    if (o && o->fast) return !g_cli_intr;
    while (ms && !g_cli_intr) {
        unsigned sl = ms < 25u ? ms : 25u;
        cli_real_sleep(sl);
        ms -= sl;
    }
    return !g_cli_intr;
}

/* Console output is also written to the log file when one is open (cli_log_open), one line at a time, so an interrupted run keeps what it printed. */
static FILE *g_log;
static pthread_mutex_t g_out_lock = PTHREAD_MUTEX_INITIALIZER;
int cli_log_open(const char *path) {
    pthread_mutex_lock(&g_out_lock);
    if (g_log) fclose(g_log);
    g_log = fopen(path, "a");
    pthread_mutex_unlock(&g_out_lock);
    return g_log ? 0 : 1;
}
void cli_log_close(void) {
    pthread_mutex_lock(&g_out_lock);
    if (g_log) fclose(g_log);
    g_log = NULL;
    pthread_mutex_unlock(&g_out_lock);
}
static void emit_line(const char *prefix, const char *fmt, va_list ap) {
    char line[4096];
    vsnprintf(line, sizeof line, fmt, ap);
    pthread_mutex_lock(&g_out_lock);
    printf("%s%s\n", prefix, line);
    fflush(stdout);
    if (g_log) { fprintf(g_log, "%s%s\n", prefix, line); fflush(g_log); }
    pthread_mutex_unlock(&g_out_lock);
}
void cli_say(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    emit_line("", fmt, ap);
    va_end(ap);
}
void cli_detail(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    emit_line("    ", fmt, ap);
    va_end(ap);
}

const char *cli_explain(pk_status s) {
    switch (s) {
    case PK_OK: return "That worked.";
    case PK_E_DISCONNECTED: return "The scanner stopped answering, as if it had been unplugged or switched off.";
    case PK_E_TIMEOUT: return "The scanner did not answer in time.";
    case PK_E_TRANSPORT: return "The USB connection reported an error.";
    case PK_E_WRITE_FORBIDDEN: return "The safety guard refused to send that, and nothing was sent to the scanner. That is a fault in this tool, not in your scanner: tell Claude.";
    case PK_E_FIRMWARE_WEDGED: return "The scanner's firmware has locked up. Switch the scanner off, wait ten seconds, switch it on, and start again.";
    case PK_E_PROTOCOL: return "The scanner's reply was not what was expected.";
    case PK_E_DEVICE: return "The scanner reported an error.";
    case PK_E_LAMP_WARMUP: return "The lamp did not warm up properly (a temperature fault, or it took longer than 5 minutes).";
    case PK_E_CANCELLED: return "Stopped (Ctrl-C).";
    case PK_E_REPLAY_MISMATCH: return "The command did something different from what the recording shows.";
    case PK_E_VENDOR_MISSING: return "A Kodak driver file is missing from the vendor store. Run: pakon vendor import <folder>.";
    case PK_E_CORRUPT: return "A file or the scanner's data failed its checks.";
    case PK_E_NOT_FOUND: return "A file or record was not found.";
    case PK_E_LOADED_UNVERIFIED: return "The firmware is loaded and running, but the identity check afterwards could not be read.";
    case PK_E_FIRMWARE_MISMATCH: return "The scanner identifies itself differently from what its USB identity says.";
    case PK_E_FILM_IN_GUIDES: return "There is film in the scanner's entry or exit path. Remove the film from the exit path first, then from the entrance path, and scan again.";
    case PK_E_NO_FILM: return "The scanner timed out waiting for film. Start the scan again and insert the film.";
    case PK_E_BUSY: return "That is not possible in the scanner's current state.";
    case PK_E_UNSUPPORTED: return "This build or this scanner model does not support that.";
    case PK_E_IO: return "A file could not be written or read (disk problem, or the folder already exists).";
    case PK_E_ARG: return "A setting was refused as out of range, or the target already exists.";
    default: return "The operation failed.";
    }
}

void cli_report_status(const char *what, pk_status s, const pk_error *e) {
    cli_say("%s: %s", what, cli_explain(s));
    cli_detail("status %s", pk_status_str(s));
    if (e && e->context[0]) cli_detail("module %s: %s", e->module, e->context);
    if (e && e->n_last > 0) {
        for (int i = 0; i < e->n_last; i++) {
            char hex[3 * 64 + 1];
            int n = e->last[i].len < 24 ? e->last[i].len : 24, w = 0;
            for (int k = 0; k < n; k++) w += snprintf(hex + w, sizeof hex - (size_t)w, "%02X ", e->last[i].bytes[k]);
            cli_detail("%s %s", e->last[i].dir ? "sent    " : "received", hex);
        }
    }
}

int cli_home(const cli_opts *o, char *out, size_t cap) {
    const char *h = o->home;
    if (!h) h = getenv("PAKON_HOME");
    if (h && *h) { snprintf(out, cap, "%s", h); return 0; }
    const char *home = getenv("HOME");
    if (!home || !*home) return 1;
    snprintf(out, cap, "%s/Library/Application Support/PakonMac", home);   /* spec section F; pinned for Tasks 14, 15, 22 (S-R23 I-5) */
    return 0;
}

/* The unit key's model token: the models.def name with spaces as underscores (F-135, F-135_Plus), so a key is <name>-<serial>. */
const char *cli_model_tag(const pk_model *m) {
    static char tag[8][32];
    static int k;
    char *t = tag[k++ & 7];
    snprintf(t, 32, "%s", m ? m->name : "UNKNOWN");
    for (char *p = t; *p; p++) if (*p == ' ') *p = '_';
    return t;
}

static void unit_file(const cli_opts *o, char *path, size_t cap) {
    char home[1024];
    if (cli_home(o, home, sizeof home)) home[0] = 0;
    snprintf(path, cap, "%s/hw1-unit.txt", home);
}

/* Unit directories that hold an eeprom.log under <home>/units (the read-once record). Returns the count; the first name is kept. */
int cli_units_with_log(const cli_opts *o, char first[80]) {
    char home[1024], dir[1200];
    if (cli_home(o, home, sizeof home)) return 0;
    snprintf(dir, sizeof dir, "%s/units", home);
    DIR *d = opendir(dir);
    if (!d) return 0;
    int n = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (e->d_name[0] == '.') continue;
        char p[1500];
        snprintf(p, sizeof p, "%s/%s/eeprom/eeprom.log", dir, e->d_name);
        if (access(p, F_OK) == 0) { if (n == 0 && first) snprintf(first, 80, "%s", e->d_name); n++; }
    }
    closedir(d);
    return n;
}

int cli_unit_remembered(const cli_opts *o, char unit[80]) {
    if (o->unit) { snprintf(unit, 80, "%s", o->unit); return 1; }
    char path[1200];
    unit_file(o, path, sizeof path);
    uint8_t *d = NULL;
    size_t n = 0;
    if (pku_read_file(path, &d, &n) == PK_OK) {
        size_t k = 0;
        while (k < n && k < 79 && d[k] != '\n' && d[k] != '\r') { unit[k] = (char)d[k]; k++; }
        unit[k] = 0;
        free(d);
        if (k > 0) return 1;
    }
    return cli_units_with_log(o, unit) == 1;      /* no file: the one unit folder under the root, if there is exactly one */
}

const pk_model *cli_refine_from_store(const cli_opts *o, const pk_model *usb_model, char unit_out[80], char *why, size_t whycap) {
    if (o->model) {
        const pk_model *m = !strcmp(o->model, "plus") ? pk_model_get(PK_MODEL_F135_PLUS) : !strcmp(o->model, "f135") ? pk_model_get(PK_MODEL_F135) : NULL;
        if (!m) snprintf(why, whycap, "--model must be plus or f135");
        else unit_out[0] = 0;
        return m;
    }
    if (!cli_unit_remembered(o, unit_out)) {
        snprintf(why, whycap, "There is no saved calibration image yet. Run  pakon hw1 eeprom-read  first: it tells us which scanner this is.");
        return NULL;
    }
    char home[1024];
    if (cli_home(o, home, sizeof home)) { snprintf(why, whycap, "cannot find a home folder"); return NULL; }
    uint8_t *img = (uint8_t *)malloc(PKCAL_EEPROM_SIZE);
    if (!img) { snprintf(why, whycap, "out of memory"); return NULL; }
    int ok[PKCAL_NCOPIES];
    uint32_t type = 0;
    pk_status s = pk_eeprom_store_current(unit_out, home, img);
    if (s == PK_OK) s = pkcal_eeprom_validate(img, ok);
    if (s == PK_OK) s = pkcal_eeprom_identity(img, ok, &type, NULL, NULL);
    free(img);
    if (s != PK_OK) {
        snprintf(why, whycap, "The saved calibration image for %s cannot give a scanner type (%s). Tell Claude; do not read the chip again.", unit_out, pk_status_str(s));
        return NULL;
    }
    const pk_model *m = pk_model_refine(usb_model, type);
    if (!m) snprintf(why, whycap, "Scanner type 0x%X does not belong to the %s family. Tell Claude.", (unsigned)type, usb_model ? usb_model->name : "?");
    return m;
}

/* ------------------------------------------------------------------ sessions */
static pk_link_model link_model_of(const pk_model *m) {
    switch (m->id) {
    case PK_MODEL_F135: return PK_LINK_F135;
    case PK_MODEL_F135_PLUS: return PK_LINK_F135_PLUS;
    case PK_MODEL_F235: case PK_MODEL_F235C: return PK_LINK_F235;
    default: return PK_LINK_F335;
    }
}

static const pk_model *model_by_name(const char *name) {
    for (int i = 0; i < PK_MODEL__COUNT; i++) {
        const pk_model *m = pk_model_get((pk_model_id)i);
        if (m && !strcmp(m->name, name)) return m;
    }
    return NULL;
}

static const char *state_word(pk_dev_state st) {
    switch (st) {
    case PK_DEV_BARE: return "bare (no firmware, blank USB chip)";
    case PK_DEV_UNLOADED: return "unloaded (waiting for its firmware)";
    case PK_DEV_LOADED: return "loaded (firmware running)";
    default: return "not recognised";
    }
}

/* meta.json of a trace: model and the first firmware hash. */
static void read_trace_meta(const char *dir, char model[24], char fw[65]) {
    model[0] = fw[0] = 0;
    char path[1200];
    snprintf(path, sizeof path, "%s/meta.json", dir);
    uint8_t *raw = NULL;
    size_t n = 0;
    if (pku_read_file(path, &raw, &n) != PK_OK) return;
    char *z = (char *)realloc(raw, n + 1);
    if (!z) { free(raw); return; }
    z[n] = 0;
    pku_jl_kv kv[24];
    int k = pku_jl_parse(z, kv, 24);
    if (k >= 0) {
        const pku_jl_kv *m = pku_jl_get(kv, k, "model"), *f = pku_jl_get(kv, k, "fw_sha256_0");
        if (m && m->is_str) snprintf(model, 24, "%s", m->s);
        if (f && f->is_str) snprintf(fw, 65, "%s", f->s);
    }
    free(z);
}

static void fill_meta(const cli_opts *o, const pk_model *m, pk_trace_meta *meta) {
    memset(meta, 0, sizeof *meta);
    snprintf(meta->model, sizeof meta->model, "%s", m ? m->name : "unknown");
    snprintf(meta->libpakon_version, sizeof meta->libpakon_version, "%s", LIBPAKON_VERSION);
    struct utsname u;
    if (uname(&u) == 0) snprintf(meta->host_os, sizeof meta->host_os, "%s %s", u.sysname, u.release);
#ifndef NDEBUG
    if (o->fake) return;
#endif
    if (o->replay || !m) return;
    char home[1024], root[1100];
    if (cli_home(o, home, sizeof home)) return;
    snprintf(root, sizeof root, "%s/vendor", home);
    pk_vendor *v = NULL;
    if (pk_vendor_open(root, &v) == PK_OK) {
        if (pk_vendor_hash_only(v, m->firmware, meta->fw_sha256[0]) == PK_OK) meta->n_fw = 1;
        pk_vendor_close(v);
    }
}

static int explain_missing_device(const pk_dev_entry *e, size_t n, unsigned flags) {
    if (n == 0) {
        cli_say("No Pakon scanner was found on USB. Check that it is powered on, that the USB cable is plugged in, and that nothing else (such as the old PSI program) is holding it.");
        return 1;
    }
    for (size_t i = 0; i < n; i++)
        cli_say("Found a scanner that is %s, but this step needs one that is %s.", state_word(e[i].cls.state),
                (flags & CLI_UNLOADED) ? "unloaded" : "loaded");
    if (!(flags & CLI_UNLOADED)) cli_say("If it is unloaded, run  pakon load  first.");
    else cli_say("If it is already loaded you do not need  pakon load  again; switch the scanner off and on to start over.");
    return 1;
}

int cli_open(cli_opts *o, unsigned flags, cli_session *s) {
    memset(s, 0, sizeof *s);
    s->o = o;
    pk_status st;
    pk_transport *raw_or_guarded = NULL;
    bool is_raw = false;

    if (o->replay) {
        st = pk_transport_replay_open(o->replay, 0, &raw_or_guarded);
        if (st != PK_OK) { cli_report_status("Cannot open the trace to replay", st, NULL); return 1; }
        char mname[24], fw[65];
        read_trace_meta(o->replay, mname, fw);
        s->model = model_by_name(mname);
        s->usb_model = pk_model_get(PK_MODEL_F135);
        if (!s->model) s->model = s->usb_model;
        cli_say("Replaying %s against the current code (no scanner is touched).", o->replay);
        cli_detail("trace model: %s", s->model->name);
    }
#ifndef NDEBUG
    else if (o->fake) {
        o->fake_unloaded = (flags & CLI_UNLOADED) != 0;
        st = cli_fake_open(o, &raw_or_guarded);
        if (st != PK_OK) { cli_report_status("Cannot start the fake scanner", st, NULL); return 1; }
        is_raw = true;
        s->usb_model = pk_model_get(PK_MODEL_F135);
        if (o->fake_unloaded) { s->dev.info.vid = 0x0F05; s->dev.info.pid = 0xF235; s->dev.info.rev = 0xAA07; }
        else { s->dev.info.vid = 0x0F05; s->dev.info.pid = 0xF135; s->dev.info.rev = 0; }
        s->dev.cls = pk_device_classify(s->dev.info.vid, s->dev.info.pid, s->dev.info.rev);
        snprintf(s->serial, sizeof s->serial, "FAKE0001");
        cli_say("Using the SIMULATED scanner (--fake). Nothing here touches real hardware.");
    }
#endif
    else {
        pk_dev_entry ents[8];
        size_t n = 0;
        st = pk_device_discover(ents, 8, &n);
        if (st == PK_E_UNSUPPORTED) { cli_say("This copy of pakon was built without USB support (libusb is missing). Install libusb (brew install libusb pkg-config) and rebuild."); return 1; }
        if (st != PK_OK) { cli_report_status("Cannot list USB devices", st, NULL); return 1; }
        pk_dev_state want = (flags & CLI_UNLOADED) ? PK_DEV_UNLOADED : PK_DEV_LOADED;
        int pick = -1, matches = 0;
        for (size_t i = 0; i < n; i++)
            if (ents[i].cls.state == want) { if (pick < 0) pick = (int)i; matches++; }
        if (pick < 0) return explain_missing_device(ents, n, flags);
        if (matches > 1) { cli_say("More than one Pakon scanner is attached. HW-1 supports one at a time: unplug the others."); return 1; }
        s->dev = ents[pick];
        s->usb_model = s->dev.cls.model;
        if (!s->usb_model) { cli_say("This scanner's identity is not one the tool knows (USB %04X:%04X rev %04X).", s->dev.info.vid, s->dev.info.pid, s->dev.info.rev); return 1; }
        (void)pk_usb_read_serial(&s->dev.info, s->serial);   /* before the session opens the device */
        st = pk_usb_open(&s->dev.info, &raw_or_guarded);
        if (st != PK_OK) { cli_report_status("Cannot open the scanner over USB", st, NULL); return 1; }
    }

    /* the model the boards will be addressed as */
    if (!o->replay) {
        s->model = s->usb_model;
        if (flags & CLI_BOARDS) {
            char why[300];
            const pk_model *m = cli_refine_from_store(o, s->usb_model, s->unit, why, sizeof why);
            if (!m) {
                cli_say("%s", why);
                pk_transport_close(raw_or_guarded);
                return 1;
            }
            s->model = m;
        }
    } else if (flags & CLI_BOARDS) {
        /* the replay uses the trace's model */
    }

    /* record (splices under the guard; for a raw fake it also seals it) */
    if (o->trace) {
        pk_trace_meta meta;
        fill_meta(o, s->model, &meta);
        pk_transport *rec = NULL;
        st = pk_transport_record_open(raw_or_guarded, o->trace, &meta, &rec);
        if (st != PK_OK) {
            cli_say("Cannot start recording the trace into %s: %s", o->trace, st == PK_E_ARG ? "that trace folder already exists (choose a new name, or move the old one away)." : cli_explain(st));
            cli_detail("status %s", pk_status_str(st));
            pk_transport_close(raw_or_guarded);
            return 1;
        }
        s->t = rec;
        cli_say("Recording every transfer to %s", o->trace);
    } else if (is_raw) {
        st = pk_transport_guard_open(raw_or_guarded, &s->t);
        if (st != PK_OK) { cli_report_status("Cannot start the write guard", st, NULL); pk_transport_close(raw_or_guarded); return 1; }
        s->fake_raw = raw_or_guarded;
    } else {
        s->t = raw_or_guarded;
    }

    if (flags & CLI_BOARDS) {
        st = pk_link_open(s->t, link_model_of(s->model), &s->link);
        if (st == PK_OK) st = pk_boards_open(s->link, s->model, &s->b);
        if (st != PK_OK) { cli_report_status("Cannot open the scanner's boards", st, NULL); cli_close(s); return 1; }
        cli_detail("model %s: light board 0x%02X, motor board 0x%02X, host 0x%02X", s->model->name, s->model->roles.light, s->model->roles.motor, s->model->roles.host);
    }
    return 0;
}

void cli_close(cli_session *s) {
    if (s->b) pk_boards_close(s->b);     /* lamp off if it was switched on, motor stop if a move was running */
    if (s->link) pk_link_close(s->link);
    if (s->t) pk_transport_close(s->t);
    if (s->fake_raw) pk_transport_close(s->fake_raw);
    s->b = NULL; s->link = NULL; s->t = NULL; s->fake_raw = NULL;
}

/* ------------------------------------------------------------------ film moves on a worker thread */
struct cli_mover {
    pk_boards *b;
    pk_film_dir dir;
    unsigned ms;
    int speed;
    unsigned reg;           /* non-zero: the motor speed register as is (pk_film_move_register) */
    bool eject;
    pk_status st;
    int done;
    pthread_mutex_t mu;
    pthread_t th;
};

static void *mover_main(void *a) {
    cli_mover *m = (cli_mover *)a;
    pk_status st = m->eject ? pk_film_eject(m->b) : m->reg ? pk_film_move_register(m->b, m->dir, m->ms, m->reg) : pk_film_move(m->b, m->dir, m->ms, m->speed);
    pthread_mutex_lock(&m->mu);
    m->st = st;
    m->done = 1;
    pthread_mutex_unlock(&m->mu);
    return NULL;
}

static cli_mover *mover_begin(cli_session *s, pk_film_dir dir, unsigned ms, int speed, unsigned reg, bool eject) {
    cli_mover *m = (cli_mover *)calloc(1, sizeof *m);
    if (!m) return NULL;
    m->b = s->b; m->dir = dir; m->ms = ms; m->speed = speed; m->reg = reg; m->eject = eject;
    pthread_mutex_init(&m->mu, NULL);
    if (pthread_create(&m->th, NULL, mover_main, m) != 0) { pthread_mutex_destroy(&m->mu); free(m); return NULL; }
    return m;
}
cli_mover *cli_move_begin(cli_session *s, pk_film_dir dir, unsigned ms, int speed) { return mover_begin(s, dir, ms, speed, 0, false); }
cli_mover *cli_move_begin_register(cli_session *s, pk_film_dir dir, unsigned ms, unsigned reg) { return mover_begin(s, dir, ms, 0, reg, false); }
bool cli_move_done(cli_mover *m) {
    pthread_mutex_lock(&m->mu);
    int d = m->done;
    pthread_mutex_unlock(&m->mu);
    return d != 0;
}
pk_status cli_move_finish(cli_mover *m) {
    pthread_join(m->th, NULL);
    pk_status st = m->st;
    pthread_mutex_destroy(&m->mu);
    free(m);
    return st;
}

static pk_status move_for(cli_session *s, pk_film_dir dir, unsigned stop_after_ms, int speed, bool eject) {
    cli_mover *m = mover_begin(s, dir, 300000u, speed, 0, eject);
    if (!m) return PK_E_NOMEM;
    unsigned long long t0 = cli_now_ms();
    unsigned limit = (s->o->fast && stop_after_ms > 200u) ? 200u : stop_after_ms;   /* replay and fake runs do not wait out real time */
    bool timed = false, sent = false;
    unsigned long long last = 0;
    while (!cli_move_done(m)) {
        unsigned long long now = cli_now_ms();
        bool want = g_cli_intr || (limit && now - t0 >= limit);
        if (want && (!sent || now - last >= 1000)) {      /* once, and again each second only if the mover has not returned */
            (void)pk_film_stop(s->b);
            if (!g_cli_intr) timed = true;
            sent = true;
            last = now;
        }
        cli_real_sleep(20);
    }
    pk_status st = cli_move_finish(m);
    return (timed && !g_cli_intr && st == PK_E_CANCELLED) ? PK_OK : st;
}

pk_status cli_move_for(cli_session *s, pk_film_dir dir, unsigned stop_after_ms, int speed) { return move_for(s, dir, stop_after_ms, speed, false); }
/* PSI's EjectFilm: pk_film_eject on the worker (one 500 ms push); Ctrl-C stops it. */
pk_status cli_eject(cli_session *s) { return move_for(s, PK_FILM_FORWARD, 0, 0, true); }

/* ------------------------------------------------------------------ detect */
static int cmd_detect(cli_opts *o) {
    (void)o;
    pk_dev_entry e[8];
    size_t n = 0;
    pk_status st = pk_device_discover(e, 8, &n);
    if (st == PK_E_UNSUPPORTED) { cli_say("This copy of pakon was built without USB support (libusb is missing). Install libusb (brew install libusb pkg-config) and rebuild."); return 1; }
    if (st != PK_OK) { cli_report_status("Cannot list USB devices", st, NULL); return 1; }
    if (n == 0) {
        cli_say("No Pakon scanner was found on USB. Check that it is powered on and the USB cable is plugged in.");
        return 1;
    }
    for (size_t i = 0; i < n; i++) {
        char serial[32] = "";
        if (e[i].cls.state != PK_DEV_UNKNOWN) (void)pk_usb_read_serial(&e[i].info, serial);
        cli_say("Scanner %zu is %s.", i + 1, state_word(e[i].cls.state));
        cli_detail("USB %04X:%04X, revision %04X, bus %u address %u", e[i].info.vid, e[i].info.pid, e[i].info.rev, e[i].info.bus, e[i].info.addr);
        cli_detail("model from its USB identity: %s", e[i].cls.model ? e[i].cls.model->name : "(none)");
        cli_detail("iSerial: \"%s\"", serial);
        if (e[i].cls.state == PK_DEV_UNLOADED) cli_say("Write down the iSerial text above in the results file.");
    }
    return 0;
}

/* ------------------------------------------------------------------ vendor import */
static int cmd_vendor(cli_opts *o, int npos, const char **pos) {
    if (npos < 3 || strcmp(pos[1], "import")) { fputs("usage: pakon vendor import <folder>\n", stderr); return 2; }
    char home[1024], root[1100];
    if (cli_home(o, home, sizeof home)) { cli_say("Cannot find your home folder; use --home."); return 1; }
    snprintf(root, sizeof root, "%s/vendor", home);
    pk_vendor_report rep;
    memset(&rep, 0, sizeof rep);
    pk_status st = pk_vendor_import(pos[2], root, &rep);
    if (st != PK_OK) {
        cli_report_status("The Kodak files could not be imported", st, NULL);
        cli_detail("found ok %zu, missing %zu, mismatched %zu", rep.n_ok, rep.n_missing, rep.n_mismatch);
        for (int i = 0; i < 16 && rep.names[i][0]; i++) cli_detail("problem: %s", rep.names[i]);
        return 1;
    }
    cli_say("Imported the Kodak driver files into %s.", root);
    cli_detail("%zu files verified, %zu added now, %zu optional ones not present", rep.n_ok, rep.n_added, rep.n_missing);
    return 0;
}

/* ------------------------------------------------------------------ load */
int cli_cmd_load(cli_opts *o) {
    char home[1024], root[1100];
    if (cli_home(o, home, sizeof home)) { cli_say("Cannot find your home folder; use --home."); return 1; }
    snprintf(root, sizeof root, "%s/vendor", home);
    pk_vendor_report rep;
    memset(&rep, 0, sizeof rep);
    pk_vendor *v = NULL;
    pk_status st = pk_vendor_open_ex(root, &rep, &v);
    if (st != PK_OK) {
        cli_report_status("The vendor store is not ready", st, NULL);
        for (int i = 0; i < 16 && rep.names[i][0]; i++) cli_detail("problem: %s", rep.names[i]);
        cli_say("Run  pakon vendor import <folder with the Kodak install files>  first.");
        return 1;
    }
    cli_session s;
    int rc = cli_open(o, CLI_UNLOADED, &s);
    if (rc) { pk_vendor_close(v); return rc; }
    cli_say("Loading the %s firmware into the scanner's working memory. This only writes the chip's RAM, which is wiped at power-off; the scanner's permanent memory is not touched.", s.usb_model->name);
    pk_fw_opts fo = { 100, 10000, 500, o->image == 2004 };
    if (fo.image_2004) cli_say("DIAGNOSTIC: --image 2004 loads the OLD 2004 firmware (F-135/F135Driver/Pakon7.hex), not the 2006 one PSI 3.0.4.27 loads. Use it only when told to.");
    else cli_detail("firmware image: 2006 FX35Driver/Pakon7.hex (the one PSI 3.0.4.27 loads), pinned by SHA-256");
    cli_detail("loader: Kodak's own sequence (stage-1 loader from your F235Ldr.sys, then the firmware by A3 and A0), with a read-back of every byte before the scanner is released");
    pk_error err;
    memset(&err, 0, sizeof err);
    st = pk_device_load_firmware(s.t, s.usb_model, v, &fo, &err);
    int ret = 0;
    if (st == PK_OK) {
        cli_say("PASS: the firmware loaded, the scanner restarted as a loaded device (0F05:F135), and its stored identity agrees.");
        cli_detail("serial before loading: \"%s\"", s.serial);
    } else if (st == PK_E_LOADED_UNVERIFIED) {
        cli_report_status("The firmware is loaded and running", st, &err);
        cli_say("Do NOT load again. Carry on with the next step and tell Claude about this line.");
        ret = 1;
    } else {
        cli_report_status("The firmware load FAILED", st, &err);
        cli_say("Switch the scanner off, wait ten seconds, switch it on, and tell Claude before trying again. Do not retry in a loop.");
        ret = 1;
    }
    cli_close(&s);
    pk_vendor_close(v);
    return ret;
}

/* ------------------------------------------------------------------ film */
int cli_cmd_film(cli_opts *o, const char *sub) {
    cli_session s;
    int rc = cli_open(o, CLI_LOADED | CLI_BOARDS, &s);
    if (rc) return rc;
    pk_status st = PK_OK;
    int ret = 0;
    unsigned ms = o->seconds * 1000u;
    if (!strcmp(sub, "stop")) {
        st = pk_film_stop(s.b);
        cli_say(st == PK_OK ? "Stop sent. The film drive should be still." : "The stop could not be sent.");
    } else if (!strcmp(sub, "eject")) {
        /* PSI's EjectFilm (PTS Pakon.dll ScannerSettings.EjectFilm, scanner type 0x546 / 0x547) is one TLB AdvanceFilm(500 ms, speed 1000), the library's pk_film_eject:
         * a short slow push forward, with no sensor logic and no DX start. Run it again to push further, or use  film advance. */
        cli_say("Eject, as PSI does it: a short, slow push forward (half a second). Run it again to push further.");
        st = cli_eject(&s);
        cli_say(st == PK_OK || st == PK_E_CANCELLED ? "Push done; the film drive has been stopped." : "The push did not finish normally.");
        if (st == PK_E_CANCELLED && !g_cli_intr) st = PK_OK;
    } else {
        pk_film_dir d = !strcmp(sub, "advance") ? PK_FILM_FORWARD : PK_FILM_REVERSE;
        cli_say("Film %s at %s speed for %u seconds (Ctrl-C or  pakon film stop  stops it at once).", !strcmp(sub, "advance") ? "forward" : "backward",
                o->speed ? "the chosen" : "full", o->seconds ? o->seconds : 300u);
        st = cli_move_for(&s, d, ms, o->speed);
        if (st == PK_E_CANCELLED && !g_cli_intr) st = PK_OK;     /* our own timed stop */
        cli_say(st == PK_OK ? "Done; the film drive has been stopped." : "The move did not finish normally.");
    }
    if (st != PK_OK) {
        cli_report_status("Film command", st, pk_link_last_error(s.link));
        ret = st == PK_E_CANCELLED ? 130 : 1;
    }
    pk_status ss = pk_film_stop(s.b);     /* always end with a stop */
    cli_detail("final stop: %s", pk_status_str(ss));
    cli_close(&s);
    return ret;
}

static int cmd_film(cli_opts *o, int npos, const char **pos) {
    if (npos < 2 || (strcmp(pos[1], "advance") && strcmp(pos[1], "reverse") && strcmp(pos[1], "stop") && strcmp(pos[1], "eject"))) {
        fputs("usage: pakon film advance|reverse|stop|eject [--seconds N] [--speed N]\n", stderr);
        return 2;
    }
    return cli_cmd_film(o, pos[1]);
}

/* ------------------------------------------------------------------ main */
int main(int argc, char **argv) {
    cli_opts o;
    const char *pos[16];
    int npos = 0;
    int rc = cli_parse(argc, argv, &o, pos, 16, &npos);
    if (rc) return rc;
    if (npos == 0) { cli_usage(stderr); return 2; }
    cli_install_signals();
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (!strcmp(pos[0], "detect")) return cmd_detect(&o);
    if (!strcmp(pos[0], "vendor")) return cmd_vendor(&o, npos, pos);
    if (!strcmp(pos[0], "load")) return cli_cmd_load(&o);
    if (!strcmp(pos[0], "film")) return cmd_film(&o, npos, pos);
    if (!strcmp(pos[0], "decode")) return cli_cmd_decode(&o, npos, pos);
    if (!strcmp(pos[0], "hw1")) return cli_cmd_hw1(&o, npos, pos);
    if (!strcmp(pos[0], "hw2e")) return cli_cmd_hw2e(&o, npos, pos);
    cli_usage(stderr);
    return 2;
}
