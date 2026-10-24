#define _POSIX_C_SOURCE 200809L
/* pakon hw1: the temporary driver for the first hardware session (Task 10; Task 22 replaces it with the real commands).
 * Every subcommand talks to the scanner only through the public library and the write guard. Nothing here writes scanner memory:
 * the only transfers that are not board packets are the read-only calibration-chip reads (40/A4 wValue 0xA5, C0/A9) that
 * the guard allows. Ctrl-C always ends in the cleanup path: motor stop, lamp off. */
#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include "cli.h"
#include "calib/eeprom.h"
#include "device/eeprom_store.h"
#include "pakon/dx.h"
#include "transport/trace.h"
#include "util/util.h"

char *mkdtemp(char *);   /* POSIX 2008; hidden by -std=c99 on some libcs */
#define INTR (g_cli_intr != 0)

/* ------------------------------------------------------------------ what the trace shows about light-board register 0x02 */
/* The DX state-1 question (task 9 re-review 2): how often does the light board answer register 0x02 with a non-zero value whose
 * response status byte has bit 7 clear? TLB acts only on bit-7 replies; the port ignores the rest. Counted from the recorded trace, which is
 * what the scanner really said. */
static void trace_observation(const char *dir, uint8_t light) {
    if (!dir) { cli_say("No trace was recorded, so the light-board status replies could not be counted."); return; }
    pkt_event *ev = NULL;
    size_t n = 0;
    int fd = -1;
    uint64_t ssz = 0;
    pk_status st = pkt_load(dir, &ev, &n, &fd, &ssz);
    if (st != PK_OK) { cli_say("Could not read back the trace to count status replies (%s).", pk_status_str(st)); return; }
    unsigned reads = 0, ev7 = 0, silent = 0, packets = 0;
    unsigned silent_vals[16];
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
                else if (e->data[4] != 0) { if (silent < 16) silent_vals[silent] = e->data[4]; silent++; }
            }
            armed = 0;
        }
    }
    pkt_free_events(ev, n);
    if (fd >= 0) close(fd);
    if (reads == 0) return;
    cli_say("Light-board status replies in this run: %u. Of these %u carried an event flag, and %u had a non-zero value WITHOUT the event flag (write that last number in the results file).", reads, ev7, silent);
    cli_detail("light board register 0x02 reads: %u; reply status bit 7 set: %u; value non-zero with status bit 7 clear: %u; packets sent in total: %u", reads, ev7, silent, packets);
    for (unsigned k = 0; k < silent && k < 16; k++) cli_detail("silent value #%u: 0x%02X", k + 1, silent_vals[k]);
}

/* ------------------------------------------------------------------ eeprom */
static uint32_t rd32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static const char *const COPY_NAME[PKCAL_NCOPIES] = { "CalWiz copy A (at 0x0000)", "CalWiz copy B (at 0x0400)", "Adjust copy A (at 0x0800)", "Adjust copy B (at 0x0A00)" };
static const unsigned COPY_OFF[PKCAL_NCOPIES] = { 0x000, 0x400, 0x800, 0xA00 };

static void print_copies(const uint8_t *img, const int ok[PKCAL_NCOPIES]) {
    int calwiz_ok = ok[0] + ok[1], adjust_ok = ok[2] + ok[3];
    cli_say("The calibration chip holds four copies of its data. Intact means the copy's own length and checksum agree:");
    for (int i = 0; i < PKCAL_NCOPIES; i++) {
        cli_say("  %-26s %s", COPY_NAME[i], ok[i] ? "intact" : "NOT intact (its length or checksum is wrong)");
        cli_detail("header at 0x%04X: length %u, stored CRC-32 0x%08X", COPY_OFF[i], (unsigned)rd32(img + COPY_OFF[i]), (unsigned)rd32(img + COPY_OFF[i] + 4));
    }
    if (!ok[0] && ok[1])
        cli_say("CalWiz copy A is damaged and copy B is fine. That is what we expected: the old Python tool probably wrote into this chip. Copy B (and the Adjust copies) are enough to carry on.");
    else if (calwiz_ok == 2 && adjust_ok == 2)
        cli_say("All four copies are intact.");
    else if (calwiz_ok == 0)
        cli_say("Neither CalWiz copy is intact. The image has been kept, but it is NOT saved as the current calibration. Tell Claude before doing anything else.");
    else
        cli_say("%d of 4 copies are intact; at least one CalWiz copy is, which is enough to identify the scanner.", calwiz_ok + adjust_ok);
}

static void put_flag_words(unsigned f, bool had_current) {
    if (had_current && (f & PK_EEPROM_PUT_CURRENT)) cli_say("CONFIRMED: this second read matches the saved image byte for byte, so the chip content is stable. Nothing was replaced.");
    else if (f & PK_EEPROM_PUT_NEW) cli_say("Saved a new image file.");
    else cli_say("This image was already saved, byte for byte.");
    if (!had_current && (f & PK_EEPROM_PUT_CURRENT)) cli_say("This image is now the saved calibration image for this scanner; it will not be read from the chip again.");
    if (f & PK_EEPROM_PUT_DIFFERS) cli_say("WARNING: this read DIFFERS from the saved image. Nothing was replaced. Tell Claude: the chip content may be changing.");
    if (f & PK_EEPROM_PUT_NO_CALWIZ) cli_say("Neither CalWiz copy validates, so this image was stored but NOT made current.");
    if ((f & PK_EEPROM_PUT_NO_CURRENT) && had_current) cli_say("Unexpected: there was no current image to compare with.");
    cli_detail("store flags 0x%X", f);
}

static int write_unit_file(const cli_opts *o, const char *unit) {
    char home[1024], path[1200], line[100];
    if (cli_home(o, home, sizeof home)) return 1;
    if (pku_mkdirs(home) != PK_OK) return 1;
    snprintf(path, sizeof path, "%s/hw1-unit.txt", home);
    int n = snprintf(line, sizeof line, "%s\n", unit);
    return pku_write_file_atomic(path, line, (size_t)n) == PK_OK ? 0 : 1;
}

static void sanitize_serial(const char *in, char *out, size_t cap) {
    size_t k = 0;
    for (; *in && k + 1 < cap; in++) out[k++] = (isalnum((unsigned char)*in) || *in == '.' || *in == '_') ? *in : '_';
    out[k] = 0;
}

static int hw1_eeprom_read(cli_opts *o) {
    char home[1024];
    if (cli_home(o, home, sizeof home)) { cli_say("Cannot find your home folder; use --home."); return 1; }
    if (geteuid() == 0) { cli_say("REFUSED: do not run this as root (sudo): it would use a different saved-data folder and could read the chip a second time."); return 1; }
    cli_say("Saved calibration data lives in: %s", home);
    char unit0[80] = "";
    int nlogs = cli_units_with_log(o, unit0);          /* any eeprom.log, current image or not, means the chip has been read */
    bool have_unit = cli_unit_remembered(o, unit0) != 0, have_current = false;
    uint8_t *cur = (uint8_t *)malloc(PKCAL_EEPROM_SIZE), *img = (uint8_t *)malloc(PKCAL_EEPROM_SIZE);
    if (!cur || !img) { free(cur); free(img); return 1; }
    int ret = 1;
    if (nlogs > 0 && !o->confirm_reread) {
        cli_say("REFUSED: the chip has already been read once (%d saved unit%s found under %s), and it is only ever read once. Nothing was done.", nlogs, nlogs == 1 ? "" : "s", home);
        cli_detail("A second read needs the flag --confirm-reread, and belongs to hardware session HW-2.");
        ret = 0;
        goto out;
    }
    if (o->confirm_reread && nlogs == 0) {
        cli_say("REFUSED: --confirm-reread only applies when a saved image exists to confirm, and none was found under %s.", home);
        goto out;
    }
    if (o->confirm_reread && !have_unit) { cli_say("More than one saved unit exists; say which with --unit."); goto out; }
    if (have_unit) {
        pk_status c = pk_eeprom_store_current(unit0, home, cur);
        if (c == PK_OK) have_current = true;
        else if (c != PK_E_NOT_FOUND) {
            cli_report_status("The saved calibration image for this scanner cannot be used", c, NULL);
            cli_say("Do not read the chip again. Tell Claude.");
            goto out;
        }
    }

    cli_session s;
    if (cli_open(o, CLI_LOADED, &s)) goto out;
    cli_say("Reading the calibration chip, all 8 KB (0x0000 to 0x1FFF), once. This only READS; nothing can be written to the scanner by this step.");
    cli_detail("256 steps of: select the chip (40/A4 wValue 0xA5 wIndex 0x1234), then read 32 bytes (C0/A9 wValue = offset wIndex 0x1234), TLB's exact shape");
    unsigned long long t0 = cli_now_ms();
    pk_status st = PK_OK;
    for (unsigned off = 0; off < PKCAL_EEPROM_SIZE && st == PK_OK; off += 0x20) {
        if (INTR) { st = PK_E_CANCELLED; break; }
        st = pk_t_control(s.t, 0x40, 0xA4, PK_EEPROM_SELECT_WVALUE, 0x1234, NULL, 0, 2000);
        if (st == PK_OK) st = pk_t_control(s.t, 0xC0, 0xA9, (uint16_t)off, 0x1234, img + off, 0x20, 2000);
        if (st == PK_OK && (off & 0x7FF) == 0x7E0) cli_detail("read up to 0x%04X of 0x2000", off + 0x20);
    }
    unsigned long long ms = cli_now_ms() - t0;
    if (st != PK_OK) {
        cli_report_status("The read stopped early, so no image was saved", st, NULL);
        if (s.t->diag[0]) cli_detail("transport: %s", s.t->diag);
        cli_say("Nothing was written anywhere. It is safe to run this step again.");
        cli_close(&s);
        ret = st == PK_E_CANCELLED ? 130 : 1;
        goto out;
    }
    cli_say("Read all 8192 bytes in %llu ms.", ms);
    bool all_ff = true, all_00 = true;
    for (size_t i = 0; i < PKCAL_EEPROM_SIZE; i++) { if (img[i] != 0xFF) all_ff = false; if (img[i]) all_00 = false; }
    if (all_ff || all_00) cli_say("WARNING: the chip answered with all %s bytes. That is not real data. Tell Claude.", all_ff ? "0xFF" : "0x00");

    int ok[PKCAL_NCOPIES] = { 0 };
    st = pkcal_eeprom_validate(img, ok);
    print_copies(img, ok);
    uint32_t type = 0, hwv = 0, serial = 0;
    pk_status is = pkcal_eeprom_identity(img, ok, &type, &hwv, &serial);
    const pk_model *refined = NULL;
    char unit[80];
    if (is == PK_OK) {
        refined = pk_model_refine(s.usb_model, type);
        cli_say("The scanner identifies itself as type 0x%X%s, hardware version %u, serial %u.", (unsigned)type,
                refined ? (refined->id == PK_MODEL_F135_PLUS ? " (an F-135 Plus)" : " (an F-135)") : " (not an F-135 family type!)", (unsigned)hwv, (unsigned)serial);
        cli_detail("scanner_type 0x%X, hardware version %u, serial %u, model after refinement: %s", (unsigned)type, (unsigned)hwv, (unsigned)serial, refined ? refined->name : "(none)");
        if (type != 0x547) cli_say("Note: we expected 0x547 for the F-135 Plus. Tell Claude.");
        snprintf(unit, sizeof unit, "%s-%u", cli_model_tag(refined ? refined : s.usb_model), (unsigned)serial);
    } else {
        char sn[40];
        sanitize_serial(s.serial, sn, sizeof sn);
        cli_say("No intact CalWiz copy, so the scanner type and serial could not be read from the chip.");
        snprintf(unit, sizeof unit, "%s-unidentified", cli_model_tag(s.usb_model));
        (void)sn;
    }
    const char *use_unit = have_unit ? unit0 : unit;
    if (have_unit && strcmp(unit0, unit)) cli_say("WARNING: this chip's unit key is %s but the saved one is %s. Tell Claude.", unit, unit0);
    unsigned flags = 0;
    pk_status ps = pk_eeprom_store_put(use_unit, home, img, ok, have_current ? 1 : 0, &flags);
    if (ps != PK_OK) {
        cli_report_status("The image could NOT be saved", ps, NULL);
        cli_say("Tell Claude. Do not read the chip again until we have a plan.");
        cli_close(&s);
        goto out;
    }
    char sha[65];
    pku_sha256_hex(img, PKCAL_EEPROM_SIZE, sha);
    cli_say("Calibration image saved for scanner %s.", use_unit);
    cli_detail("file: %s/units/%s/eeprom/%s.bin (kept for ever, never overwritten)", home, use_unit, sha);
    put_flag_words(flags, have_current);
    if (!have_unit && (flags & PK_EEPROM_PUT_CURRENT) && write_unit_file(o, use_unit) != 0)
        cli_say("WARNING: the unit key could not be remembered (%s/hw1-unit.txt). Later steps will need  --unit %s.", home, use_unit);
    else if (!have_unit && (flags & PK_EEPROM_PUT_CURRENT))
        cli_detail("remembered unit key in %s/hw1-unit.txt", home);
    if (!have_current && refined && (flags & PK_EEPROM_PUT_CURRENT)) cli_say("Next step: pakon hw1 ping");
    cli_close(&s);
    ret = 0;
out:
    free(cur);
    free(img);
    return ret;
}

static int hw1_scanner_type(cli_opts *o) {
    char home[1024], unit[80];
    if (cli_home(o, home, sizeof home)) { cli_say("Cannot find your home folder; use --home."); return 1; }
    if (!cli_unit_remembered(o, unit)) { cli_say("There is no saved calibration image yet. Run  pakon hw1 eeprom-read  first."); return 1; }
    uint8_t *img = (uint8_t *)malloc(PKCAL_EEPROM_SIZE);
    if (!img) return 1;
    int ok[PKCAL_NCOPIES], ret = 1;
    pk_status st = pk_eeprom_store_current(unit, home, img);
    if (st != PK_OK) { cli_report_status("No usable saved image", st, NULL); goto out; }
    (void)pkcal_eeprom_validate(img, ok);
    cli_say("Reading the SAVED copy for %s. No transfer to the scanner is made.", unit);
    uint32_t type = 0, hwv = 0, serial = 0;
    st = pkcal_eeprom_identity(img, ok, &type, &hwv, &serial);
    if (st != PK_OK) { cli_report_status("The saved image has no intact CalWiz copy", st, NULL); goto out; }
    const pk_model *usb = pk_model_get(PK_MODEL_F135), *m = pk_model_refine(usb, type);
    cli_say("Scanner type 0x%X: %s. Hardware version %u, serial %u.", (unsigned)type, m ? m->name : "not an F-135 family type", (unsigned)hwv, (unsigned)serial);
    cli_detail("intact copies: CalWiz A %d, CalWiz B %d, Adjust A %d, Adjust B %d", ok[0], ok[1], ok[2], ok[3]);
    if (m) cli_detail("board addresses: light 0x%02X, motor 0x%02X, host 0x%02X", m->roles.light, m->roles.motor, m->roles.host);
    ret = m ? 0 : 1;
out:
    free(img);
    return ret;
}

/* ------------------------------------------------------------------ ping */
static int hw1_ping(cli_opts *o) {
    cli_session s;
    if (cli_open(o, CLI_LOADED | CLI_BOARDS, &s)) return 1;
    uint8_t light = s.model->roles.light;
    struct { const char *name; uint8_t addr; } r[3] = { { "light board", s.model->roles.light }, { "motor board", s.model->roles.motor }, { "host board", s.model->roles.host } };
    cli_say("Pinging the scanner's boards at the addresses of the %s (a ping is a harmless 'are you there'):", s.model->name);
    int bad = 0;
    for (int i = 0; i < 3 && !INTR; i++) {
        if (!r[i].addr) continue;
        pk_status st = pk_link_ping(s.link, r[i].addr);
        cli_say("  %-12s at 0x%02X: %s", r[i].name, r[i].addr, st == PK_OK ? "answered" : "NO ANSWER");
        if (st != PK_OK) { bad++; cli_detail("status %s", pk_status_str(st)); const pk_error *e = pk_link_last_error(s.link); if (e && e->context[0]) cli_detail("%s", e->context); }
    }
    cli_say(bad ? "%d board(s) did not answer. Tell Claude before going further." : "All boards answered.", bad);
    cli_close(&s);
    trace_observation(o->trace, light);
    return bad ? 1 : (INTR ? 130 : 0);
}

/* ------------------------------------------------------------------ motor */
static int stop_report(cli_session *s) {
    pk_status st = pk_film_stop(s->b);
    cli_detail("stop sent: %s", pk_status_str(st));
    return st == PK_OK ? 0 : 1;
}

static int hw1_motor(cli_opts *o) {
    cli_session s;
    if (cli_open(o, CLI_LOADED | CLI_BOARDS, &s)) return 1;
    uint8_t light = s.model->roles.light;
    cli_say("Motor test with the scanner EMPTY: the film drive runs forward for 2 seconds, stops, runs backward for 2 seconds, stops. Listen for it. Ctrl-C stops it at once.");
    int ret = 0;
    static const struct { pk_film_dir d; const char *name; } steps[2] = { { PK_FILM_FORWARD, "forward" }, { PK_FILM_REVERSE, "backward" } };
    for (int i = 0; i < 2 && ret == 0; i++) {
        cli_say("Now: motor %s for 2 seconds...", steps[i].name);
        pk_status st = cli_move_for(&s, steps[i].d, 2000, 0);
        if (st != PK_OK) {
            cli_report_status("The motor step", st, pk_link_last_error(s.link));
            ret = st == PK_E_CANCELLED ? 130 : 1;
            break;
        }
        cli_say("Stopped. (Did you hear it run %s, and stop?)", steps[i].name);
        if (stop_report(&s)) { ret = 1; break; }
        if (!cli_wait(o, 1000)) { ret = 130; break; }
    }
    if (ret) { cli_say("Making sure the motor is stopped."); (void)stop_report(&s); }
    else cli_say("Motor test finished.");
    cli_close(&s);
    trace_observation(o->trace, light);
    return ret;
}

/* ------------------------------------------------------------------ leds */
static int hw1_leds(cli_opts *o) {
    cli_session s;
    if (cli_open(o, CLI_LOADED | CLI_BOARDS, &s)) return 1;
    uint8_t light = s.model->roles.light;
    int ret = 0;
    pk_status st = PK_OK;
    if (o->no_leds) {
        st = pk_leds_enable(s.b, false);
        cli_say("LEDs are DISABLED for this run (--no-leds): the steps below send nothing, so you should see no change at all.");
    } else {
        st = pk_boards_open_led_gate(s.b);
        cli_detail("opened the LED gate: %s", pk_status_str(st));
    }
    static const unsigned codes[5] = { 2, 4, 8, 0xC, 0 };
    for (int i = 0; i < 5 && st == PK_OK && !INTR; i++) {
        cli_say("STATUS LED, colour code 0x%X. Look at the status LED now and write down what it shows (colour, steady or flashing).", codes[i]);
        st = pk_led_set(s.b, PK_LED_STATUS, codes[i]);
        if (st == PK_OK && !cli_wait(o, 6000)) break;
    }
    static const struct { pk_filmled f; const char *name; } fl[4] = { { PK_FILMLED_OFF, "OFF" }, { PK_FILMLED_FOUND, "FOUND (0x42, expect steady green)" }, { PK_FILMLED_WAITING, "WAITING (0x48, expect blinking green)" }, { PK_FILMLED_REMOVE, "REMOVE" } };
    for (int i = 0; i < 4 && st == PK_OK && !INTR; i++) {
        cli_say("FILM LED, state %s. Look at the film LED and write down what it shows.", fl[i].name);
        st = pk_film_led(s.b, fl[i].f);
        if (st == PK_OK && !cli_wait(o, 6000)) break;
    }
    if (st != PK_OK) { cli_report_status("An LED step", st, pk_link_last_error(s.link)); ret = 1; }
    if (INTR) ret = 130;
    cli_say("Putting both LEDs back to off.");
    (void)pk_led_set(s.b, PK_LED_STATUS, 0);
    (void)pk_film_led(s.b, PK_FILMLED_OFF);
    cli_say(ret ? "LED test did not finish." : "LED test finished.");
    cli_close(&s);
    trace_observation(o->trace, light);
    return ret;
}

/* ------------------------------------------------------------------ lamp */
/* PSI's open-gate lamp set on this unit (v1 docs/59 wire capture, steps 81/82; TLB FN_bBeforeScan uses it while no film is in the gate):
 * levels R3 G11 B7, on-counts R654 G374 B156, period 982. Order is TLB's: monitor thresholds, then enable (0x80), levels (0x81), duty (0x82)
 * (S-R23). All within TLB's clamps (R <= 4, G <= 20, B <= 20; on-count <= N-2). */
static const uint16_t LAMP_LEVELS[4] = { 3, 11, 7, 0 };
static const uint16_t LAMP_ON[4] = { 654, 374, 156, 0 };
#define LAMP_PERIOD 982
/* PSI's with-film duty (FN_bBeforeScan -> FUN_1002d7f0(...,1,...)), from the v1 wire capture docs/59 step 100: light 0x82 = 24 03 00 00 90 03 00 00 AA 03 D6 03,
 * i.e. on-counts B 804, Ir 0, R 912, G 938, period 982 (same {R, G, B, Ir} order as LAMP_ON). Fixed here; the real driver computes it from the calibration (Task 15). */
static const uint16_t LAMP_ON_FILM[4] = { 912, 938, 804, 0 };

static pk_status lamp_up(cli_session *s) {
    pk_status st = pk_light_lamp_init_thresholds(s->b);
    if (st == PK_OK) st = pk_light_lamp_on(s->b, true, false);
    if (st == PK_OK) st = pk_light_set_levels(s->b, LAMP_LEVELS);
    if (st == PK_OK) st = pk_light_set_duty(s->b, LAMP_ON, LAMP_PERIOD);
    return st;
}

static void progress(void *user, int pct, const pk_light_health *h) {
    (void)user;
    if (h && h->lamp_temp_raw >= 0)
        cli_say("  warming up: %d%%   lamp %.1f C (target %.1f C), main board %.1f C", pct, h->lamp_temp_raw / 16.0, h->setpoint_raw / 16.0, h->main_temp_raw / 16.0);
    else cli_say("  warming up: %d%%", pct);
}

static const char *health_word(const pk_light_health *h) {
    if (!h->ok) return "FAULT";
    if (h->flags & (PK_LIGHT_F_LAMP_WARN | PK_LIGHT_F_MAIN_WARN)) return "warning";
    return "ok";
}

static void health_line(const char *tag, const pk_light_health *h) {
    cli_say("  %s: lamp %.1f C (target %.1f C), main board %.1f C, status %s", tag, h->lamp_temp_raw / 16.0, h->setpoint_raw / 16.0, h->main_temp_raw / 16.0, health_word(h));
    if (h->flags & ~(unsigned)PK_LIGHT_F_TEMP_VALID) cli_detail("register 0x83 = 0x%02X, flags 0x%X, raw lamp %d setpoint %d main %d", (unsigned)h->status, (unsigned)h->flags, h->lamp_temp_raw, h->setpoint_raw, h->main_temp_raw);
}

static bool enter_pressed(void) {
    fd_set fds;
    struct timeval tv = { 0, 0 };
    FD_ZERO(&fds);
    FD_SET(0, &fds);
    if (!isatty(0) || select(1, &fds, NULL, NULL, &tv) <= 0) return false;
    char buf[64];
    return read(0, buf, sizeof buf) > 0;
}

static int hw1_lamp(cli_opts *o) {
    cli_session s;
    if (cli_open(o, CLI_LOADED | CLI_BOARDS, &s)) return 1;
    uint8_t light = s.model->roles.light;
    int ret = 0;
    pk_status st;
    pk_light_health h;
    cli_say("Lamp test. The lamp will come on at PSI's own open-gate settings. Ctrl-C switches it off at once.");
    st = lamp_up(&s);
    if (st != PK_OK) { cli_report_status("Could not switch the lamp on", st, pk_link_last_error(s.link)); ret = 1; goto done; }
    cli_say("Lamp switched on. Waiting for it to warm up (up to 5 minutes)...");
    st = pk_lamp_warmup(s.b, NULL, progress, NULL, (const volatile int *)&g_cli_intr);
    if (st != PK_OK) { cli_report_status("Warm-up", st, pk_link_last_error(s.link)); ret = st == PK_E_CANCELLED ? 130 : 1; goto done; }
    cli_say("The lamp reports that it is warm and stable.");

    if (o->no_keepalive) {
        cli_say("IDLE-TIMEOUT TEST: for the next 5 minutes this tool sends NOTHING to the light board. Watch the lamp. The moment it goes dark, press Enter and write down the time on the countdown below. If it stays on, just wait.");
        while (enter_pressed()) {}          /* drop any Enter pressed during the warm-up */
        unsigned long long t0 = cli_now_ms();
        int off_at = -1;
        for (int sec = 10; sec <= 300 && !INTR; sec += 10) {
            if (!cli_wait(o, 10000)) break;
            if (enter_pressed() && off_at < 0) { off_at = sec; cli_say("  noted: Enter pressed at about %d s.", sec); }
            cli_say("  idle %3d of 300 s, nothing sent%s", sec, off_at >= 0 ? " (you reported the lamp went dark)" : "");
        }
        if (INTR) { ret = 130; goto done; }
        cli_say("Idle time is over (%llu s of wall clock). Reading the lamp status now; this is the first packet in 5 minutes.", (cli_now_ms() - t0) / 1000ull);
        st = pk_light_health_poll(s.b, &h);
        if (st == PK_OK) health_line("status after idling", &h); else cli_report_status("Status read", st, pk_link_last_error(s.link));
        cli_say(off_at < 0 ? "Write down: the lamp STAYED ON for 5 idle minutes (if that is what you saw)." : "Write down: the lamp went dark after about %d seconds.", off_at);
        goto done;
    }

    cli_say("Checking the lamp for 60 seconds: a keep-alive every second (judged only through TLB's board-event path, as in PSI), and a temperature reading every 10 seconds for your information.");
    for (int i = 0; i < 60 && !INTR; i++) {
        st = pk_lamp_keepalive(s.b);
        if (st != PK_OK) { cli_report_status("Lamp keep-alive", st, pk_link_last_error(s.link)); ret = 1; goto done; }
        if (i % 10 == 0 && pk_light_health_poll(s.b, &h) == PK_OK) {
            health_line("temperatures", &h);
            if (!h.ok) cli_say("  The board status register shows a fault bit. Not judged by TLB's rule, so the run continues; write it down.");
        }
        if (!cli_wait(o, 1000)) break;
    }
    if (INTR) { ret = 130; goto done; }
    st = pk_light_lamp_off(s.b);
    cli_say("Lamp switched off (%s).", pk_status_str(st));
    cli_wait(o, 2000);
    cli_say("KEEP-ALIVE TEST: lamp on again for 5 minutes with the tool sending a keep-alive twice a second. It should STAY ON the whole time. Tell me if it goes dark.");
    st = lamp_up(&s);
    if (st != PK_OK) { cli_report_status("Could not switch the lamp on again", st, pk_link_last_error(s.link)); ret = 1; goto done; }
    for (int i = 1; i <= 600 && !INTR; i++) {
        st = pk_lamp_keepalive(s.b);
        if (st != PK_OK) { cli_report_status("Keep-alive", st, pk_link_last_error(s.link)); ret = 1; goto done; }
        if (i % 60 == 0) {
            if (pk_light_health_poll(s.b, &h) == PK_OK) { char tag[40]; snprintf(tag, sizeof tag, "keep-alive %3d of 300 s", i / 2); health_line(tag, &h); }
        }
        if (!cli_wait(o, 500)) break;
    }
    if (INTR) ret = 130;
    else cli_say("Write down whether the lamp stayed on for the full 5 minutes.");
done:
    cli_say("Switching the lamp off.");
    st = pk_light_lamp_off(s.b);
    cli_detail("lamp off: %s", pk_status_str(st));
    if (st != PK_OK) { cli_say("The lamp-off could NOT be confirmed. Look at the lamp; if it is lit, switch the scanner off at its power switch."); if (!ret) ret = 1; }
    cli_close(&s);
    trace_observation(o->trace, light);
    return ret;
}

/* ------------------------------------------------------------------ dx */
/* Reads the raw DX sensor levels (light register 0x93, AN0..AN3) and prints them. */
static pk_status dx_levels(cli_session *s, const char *tag, uint8_t v[4]) {
    pk_status st = pk_dx_read_levels(s->b, v);
    if (st != PK_OK) cli_say("  sensor levels (%s): could not read: %s", tag, cli_explain(st));
    else cli_say("  sensor levels (%s): AN0 %u, AN1 %u, AN2 %u, AN3 %u", tag, v[0], v[1], v[2], v[3]);
    return st;
}

/* Lowest and highest level per channel over the in-loop polls; r[0] = polls with no film at a sensor, r[1] = polls with film at a sensor. */
typedef struct { uint8_t lo[4], hi[4]; unsigned n; } dx_range;
static void dx_range_add(dx_range *r, const uint8_t v[4]) {
    for (int i = 0; i < 4; i++) {
        if (!r->n || v[i] < r->lo[i]) r->lo[i] = v[i];
        if (!r->n || v[i] > r->hi[i]) r->hi[i] = v[i];
    }
    r->n++;
}

static int hw1_dx(cli_opts *o) {
    cli_session s;
    if (cli_open(o, CLI_LOADED | CLI_BOARDS, &s)) return 1;
    uint8_t light = s.model->roles.light;
    int ret = 0;
    pk_dx *dx = NULL;
    cli_mover *mv = NULL;
    bool dx_started = false;
    dx_range rng[2] = {{{0}, {0}, 0}, {{0}, {0}, 0}};
    unsigned lv_skipped = 0;            /* 0x93 replies that were not sensor data (status other than 0x08) */
    bool levels_ok = true;              /* cleared at the first failed in-loop 0x93 read: 0x93 is then not read again */
    pk_status st = pk_dx_new(&dx);
    if (st != PK_OK) { cli_report_status("DX reader setup", st, NULL); cli_close(&s); return 1; }
    unsigned cap_s = o->seconds ? o->seconds : 90u;
    /* PSI base-16 scan speed: registry MotorSpeedPlus = 5917 (TLB FUN_10010430 reads it unchanged into cfg+0x3c; FUN_1003D9F0 stores iMotorSpeed in
     * 1000..0x7FFE as is, and FUN_1000B6D0 / FUN_10009D40 write it raw to motor register 0xA5): a register value, not a caller speed x 100. */
    unsigned reg = o->speed ? (unsigned)o->speed * 100u : 5917u;
    cli_say("The strip waits at the entry slot, so the film gate is empty. Reading the DX sensor levels before anything moves.");
    uint8_t base[4];
    (void)dx_levels(&s, "lamp off", base);
    if (!o->no_lamp) {
        cli_say("Lamp on first, as PSI does before a DX scan (use --no-lamp for the extra no-lamp observation).");
        st = lamp_up(&s);
        if (st == PK_OK) st = pk_lamp_warmup(s.b, NULL, progress, NULL, (const volatile int *)&g_cli_intr);
        if (st != PK_OK) { cli_report_status("Lamp", st, pk_link_last_error(s.link)); ret = st == PK_E_CANCELLED ? 130 : 1; goto done; }
        (void)dx_levels(&s, "lamp on, open-gate setting", base);
        /* PSI switches to the with-film lamp setting before the DX reader starts (FN_bBeforeScan); 0x81 stays as it is. */
        cli_say("Switching the lamp to PSI's with-film setting, as PSI does just before a scan.");
        st = pk_light_set_duty(s.b, LAMP_ON_FILM, LAMP_PERIOD);
        if (st != PK_OK) { cli_report_status("Lamp with-film setting", st, pk_link_last_error(s.link)); ret = 1; goto done; }
        cli_real_sleep(500);                /* let the new drive settle before reading the levels */
        if (!INTR) (void)dx_levels(&s, "lamp on, with-film setting", base);
    }
    if (INTR) { ret = 130; goto done; }     /* Ctrl-C so far: the film must not start moving */
    cli_say("DX test: the strip must already be in the entry slot. The film now runs forward at a scan-like speed (about %u seconds at most) while the DX reader is read about ten times a second. Ctrl-C stops it.", cap_s);
    /* PSI starts the motor first and sends 0x91 afterwards (hw1-dx-debug.md sec 2, rows 7 and 9). The mover thread holds the film lock while it sends
     * A5 and A0, so once pk_film_is_moving is true both are on the wire; only then is 0x91 sent. */
    mv = cli_move_begin_register(&s, PK_FILM_FORWARD, 300000u, reg);   /* ended only by pk_film_stop from this thread */
    if (!mv) { ret = 1; goto done; }
    /* No INTR test here: a pk_film_stop sent before the mover holds the film lock would be lost (run() clears film_stop_req) and the motor would
     * run for 300 s. The mover always sets done or moving, so this cannot hang; a Ctrl-C is acted on below, once the stop can take effect. */
    while (!cli_move_done(mv) && !pk_film_is_moving(s.b)) cli_real_sleep(5);
    if (INTR) { ret = 130; goto done; }
    if (cli_move_done(mv)) { cli_say("The film could not be started."); ret = 1; goto done; }
    st = pk_dx_start(s.b, 60, 1);          /* PSI on this unit: 91 [3C 00 01], speed 60, format 1 (v1 docs/59 step 107; TLB FN_bDrvDxStart) */
    if (st != PK_OK) { (void)pk_film_stop(s.b); cli_report_status("Starting the DX reader", st, pk_link_last_error(s.link)); ret = 1; goto done; }
    dx_started = true;
    {
        uint32_t last_sw = 0xFFFFFFFFu;
        unsigned polls = 0, data_polls = 0, clear_run = 0;
        bool seen = false;
        while (!INTR && !cli_move_done(mv)) {
            uint8_t nib = 0;
            st = pk_dx_poll_event(s.b, dx, &nib, NULL);     /* TLB reads 0x90 on every board event */
            if (st != PK_OK) { cli_report_status("Reading the DX reader", st, pk_link_last_error(s.link)); ret = 1; break; }
            if (levels_ok) {
                uint8_t v[4];
                pk_status ls = pk_dx_read_levels(s.b, v);
                if (ls == PK_OK) dx_range_add(&rng[(pk_dx_status_word(dx) & 0xC0000000u) ? 1 : 0], v);
                else if (ls == PK_E_PROTOCOL) lv_skipped++;   /* a reply that is not sensor data: dropped, the next poll reads again */
                else {
                    levels_ok = false;
                    cli_say("The sensor level read failed at poll %u (%s); not reading the levels any more. The DX reading carries on.", polls + 1, cli_explain(ls));
                }
            }
            polls++;
            if (nib) data_polls++;
            uint32_t sw = pk_dx_status_word(dx);
            if (sw != last_sw) {
                cli_say("  film sensors: entry %s, exit %s", (sw & 0x40000000u) ? "FILM" : "clear", (sw & 0x80000000u) ? "FILM" : "clear");
                cli_detail("status nibble 0x%02X, status word 0x%08X, after %u polls", nib, (unsigned)sw, polls);
                last_sw = sw;
            }
            if (sw & 0xC0000000u) { seen = true; clear_run = 0; } else if (seen) clear_run++;
            if (seen && clear_run >= 20) { cli_say("The film has passed through both sensors."); break; }
            if (polls >= cap_s * 10u) break;
            if (!cli_wait(o, 100)) break;
        }
        cli_detail("DX polls: %u, polls that returned a packet with records: %u", polls, data_polls);
    }
    if (INTR) ret = 130;
done:
    cli_say("Stopping the film and the DX reader.");
    (void)pk_film_stop(s.b);
    if (mv) { st = cli_move_finish(mv); cli_detail("mover finished: %s", pk_status_str(st)); }
    if (dx_started && dx) {                 /* TLB's one gated drain read after the strip has left, before the stop (0x92) */
        uint8_t nib = 0;
        st = pk_dx_drain(s.b, dx, &nib);
        cli_detail("DX final drain: %s", pk_status_str(st));
    }
    if (dx_started) { st = pk_dx_stop(s.b); cli_detail("DX stop: %s", pk_status_str(st)); }
    (void)pk_film_stop(s.b);
    if (!o->no_lamp) (void)pk_light_lamp_off(s.b);
    if (dx && dx_started) {
        static const char *const AN[4] = { "AN0 (clock 1)", "AN1 (data 1) ", "AN2 (clock 2)", "AN3 (data 2) " };
        static const char *const THR[4] = { "248, presence 32", "128", "7, presence 97", "lowest + 16" };
        for (int k = 1; k >= 0; k--) {
            if (!rng[k].n) continue;
            cli_say("Sensor levels during the run, polls with %s (%u polls), lowest to highest, with the thresholds from the 2026-08 EEPROM dump:", k ? "film at a sensor" : "no film at a sensor", rng[k].n);
            for (int i = 0; i < 4; i++) cli_say("  %s %u to %u   (threshold %s)", AN[i], rng[k].lo[i], rng[k].hi[i], THR[i]);
        }
        if (lv_skipped) cli_detail("sensor level replies dropped because they were not sensor data: %u", lv_skipped);
        uint32_t tc[16];
        pk_dx_record_counts(dx, tc);
        char line[200];
        size_t n = 0;
        for (int i = 0; i < 16 && n < sizeof line; i++) n += (size_t)snprintf(line + n, sizeof line - n, "%s%d:%u", i ? "  " : "", i, (unsigned)tc[i]);
        cli_say("Records read from the DX reader, by type: %s", line);
    } else cli_say("The DX test did not run (see the message above).");
    if (dx) {
        pk_dx_strip strip;
        if (dx_started && pk_dx_finish_strip(dx, true, &strip) == PK_OK) {
            if (strip.good_count > 0 && strip.product >= 0)
                cli_say("The DX reader decoded edge codes: film product code %d, specifier %d, %d frame marks read from the film. Write these down and compare with the film's edge print.", strip.product, strip.specifier, strip.good_count);
            else cli_say("The DX reader decoded NO usable edge code in this run (expected for an uncoded strip; for a coded strip this is a failure).");
            cli_detail("winning vote product %d specifier %d, good frame marks %d, source \"%s\", tail-first %d, scan-warning bits 0x%X", strip.product, strip.specifier, strip.good_count, strip.dx_source, strip.tail_first, strip.scanw);
            for (int i = 0; i < 4; i++) if (strip.votes[i][2] > 0) cli_detail("vote slot %d: product %d specifier %d count %d", i, strip.votes[i][0], strip.votes[i][1], strip.votes[i][2]);
        }
        pk_dx_free(dx);
    }
    cli_close(&s);
    trace_observation(o->trace, light);
    return ret;
}

/* ------------------------------------------------------------------ unplug-watch */
static int hw1_unplug(cli_opts *o) {
    cli_session s;
    if (cli_open(o, CLI_LOADED | CLI_BOARDS, &s)) return 1;
    uint8_t light = s.model->roles.light;
    cli_say("UNPLUG TEST (scanner empty): the motor runs forward for up to 60 seconds. When you hear it running, PULL THE USB CABLE out of the scanner. The motor will NOT stop by itself: SWITCH THE SCANNER OFF at its power switch at once. Then press Ctrl-C here.");
    pk_status st = cli_move_for(&s, PK_FILM_FORWARD, 60000, 0);
    cli_say("Sending the motor stop...");
    pk_status ss = pk_film_stop(s.b);
    cli_detail("move ended with %s; final stop: %s", pk_status_str(st), pk_status_str(ss));
    int ret = 0;
    if (ss != PK_OK || (st != PK_OK && st != PK_E_CANCELLED)) {
        cli_say("Lost the scanner: %s", cli_explain(ss != PK_OK ? ss : st));
        cli_say("Write down whether the motor kept running until you switched the scanner off (expected: it does).");
    } else {
        cli_say("The stop was delivered, so the cable was NOT pulled. The test did not happen.");
        ret = 1;
    }
    cli_close(&s);
    trace_observation(o->trace, light);
    return g_cli_intr && ret == 0 ? 0 : ret;
}

/* ------------------------------------------------------------------ replay */
static int rm_tree(const char *dir) {
    static const char *const names[] = { "meta.json", "events.jsonl", "stream.bin", "FAILED" };
    char p[1300];
    for (size_t i = 0; i < sizeof names / sizeof names[0]; i++) { snprintf(p, sizeof p, "%s/%s", dir, names[i]); unlink(p); }
    return rmdir(dir);
}

static bool same_event(const pkt_event *a, const pkt_event *b) {
    if (a->kind != b->kind || a->ep != b->ep || a->req != b->req || a->rt != b->rt || a->val != b->val || a->idx != b->idx ||
        a->len != b->len || a->status != b->status) return false;
    if (a->data && b->data) return memcmp(a->data, b->data, a->len) == 0;
    if (!a->data && !b->data) return strcmp(a->sha, b->sha) == 0 && a->off == b->off;
    return false;
}

static int compare_traces(const char *want, const char *got) {
    pkt_event *a = NULL, *b = NULL;
    size_t na = 0, nb = 0;
    int fa = -1, fb = -1;
    uint64_t sa = 0, sb = 0;
    if (pkt_load(want, &a, &na, &fa, &sa) != PK_OK || pkt_load(got, &b, &nb, &fb, &sb) != PK_OK) {
        cli_say("Could not read one of the traces back for comparison.");
        return 1;
    }
    size_t i = 0;
    for (; i < na && i < nb; i++) if (!same_event(&a[i], &b[i])) break;
    int ret = 0;
    if (i == na && i == nb) cli_say("REPLAY GREEN: all %zu recorded transfers were reproduced, in the same order, byte for byte.", na);
    else {
        ret = 1;
        cli_say("REPLAY DIFFERS at transfer number %zu (the recording has %zu transfers, this run made %zu).", i, na, nb);
        if (i < na) cli_detail("recorded: %s ep %d req 0x%02X val 0x%04X len %zu status %d", a[i].op, a[i].ep, a[i].req & 0xFF, a[i].val & 0xFFFF, a[i].len, a[i].status);
        if (i < nb) cli_detail("this run: %s ep %d req 0x%02X val 0x%04X len %zu status %d", b[i].op, b[i].ep, b[i].req & 0xFF, b[i].val & 0xFFFF, b[i].len, b[i].status);
    }
    pkt_free_events(a, na); pkt_free_events(b, nb);
    if (fa >= 0) close(fa);
    if (fb >= 0) close(fb);
    return ret;
}

static void sha_of_file(const char *dir, const char *name, char out[65]) {
    char p[1300];
    uint8_t *d = NULL;
    size_t n = 0;
    snprintf(p, sizeof p, "%s/%s", dir, name);
    if (pku_read_file(p, &d, &n) != PK_OK) { d = NULL; n = 0; }
    pku_sha256_hex(d ? d : (const uint8_t *)"", n, out);
    free(d);
}

static int register_trace(const char *dir, const char *name) {
    char ev[65], st[65], mname[24] = "", fw[65] = "";
    sha_of_file(dir, "events.jsonl", ev);
    sha_of_file(dir, "stream.bin", st);
    {
        char path[1300];
        snprintf(path, sizeof path, "%s/meta.json", dir);
        uint8_t *raw = NULL;
        size_t n = 0;
        if (pku_read_file(path, &raw, &n) == PK_OK) {
            char *z = (char *)realloc(raw, n + 1);
            if (z) {
                z[n] = 0;
                pku_jl_kv kv[24];
                int k = pku_jl_parse(z, kv, 24);
                const pku_jl_kv *m = k >= 0 ? pku_jl_get(kv, k, "model") : NULL, *f = k >= 0 ? pku_jl_get(kv, k, "fw_sha256_0") : NULL;
                if (m && m->is_str) snprintf(mname, sizeof mname, "%s", m->s);
                if (f && f->is_str) snprintf(fw, sizeof fw, "%s", f->s);
                free(z);
            } else free(raw);
        }
    }
    uint8_t *man = NULL;
    size_t mn = 0;
    const char *mpath = "corpus/manifest.json";
    if (pku_read_file(mpath, &man, &mn) != PK_OK) { cli_say("Cannot read corpus/manifest.json: run this from the repository folder."); return 1; }
    char *txt = (char *)malloc(mn + 1024);
    if (!txt) { free(man); return 1; }
    memcpy(txt, man, mn);
    txt[mn] = 0;
    free(man);
    char key[200];
    snprintf(key, sizeof key, "\"name\": \"%s\"", name);
    if (strstr(txt, key)) { cli_say("corpus/manifest.json already lists %s; not added twice.", name); free(txt); return 1; }
    char *ent = strstr(txt, "\"entries\"");
    char *open = ent ? strchr(ent, '[') : NULL;
    char *close_ = NULL;
    for (char *p = txt + mn - 1; p > txt; p--) if (*p == ']') { close_ = p; break; }
    if (!open || !close_ || close_ < open) { cli_say("corpus/manifest.json has an unexpected shape."); free(txt); return 1; }
    bool empty = true;
    for (char *p = open + 1; p < close_; p++) if (!isspace((unsigned char)*p)) { empty = false; break; }
    char line[900];
    int ln = snprintf(line, sizeof line, "%s\n    {\"name\": \"%s\", \"sha256_of_events\": \"%s\", \"sha256_of_stream\": \"%s\", \"model\": \"%s\", \"firmware_sha256\": \"%s\"}\n  ",
                      empty ? "" : ",", name, ev, st, mname, fw);
    char *out = (char *)malloc(mn + 1024);
    if (!out) { free(txt); return 1; }
    size_t head = (size_t)(open + 1 - txt);
    size_t w = 0;
    if (!empty) {
        char *last = close_;
        while (last > open + 1 && isspace((unsigned char)last[-1])) last--;
        memcpy(out, txt, (size_t)(last - txt)); w = (size_t)(last - txt);
    } else { memcpy(out, txt, head); w = head; }
    memcpy(out + w, line, (size_t)ln); w += (size_t)ln;
    size_t tail = mn - (size_t)(close_ - txt);
    memcpy(out + w, close_, tail); w += tail;
    int rc = pku_write_file_atomic(mpath, out, w) == PK_OK ? 0 : 1;
    free(out); free(txt);
    if (rc == 0) {
        cli_say("Registered %s in corpus/manifest.json.", name);
        cli_detail("events %s", ev); cli_detail("stream %s", st); cli_detail("model \"%s\" firmware %s", mname, fw);
    } else cli_say("Could not write corpus/manifest.json.");
    return rc;
}

static int hw1_dispatch(cli_opts *o, const char *sub);

static int hw1_replay(cli_opts *o, const char *trace) {
    char stem[200];
    const char *base = strrchr(trace, '/');
    base = base ? base + 1 : trace;
    if (!*base) {                      /* trailing slash */
        size_t l = strlen(trace);
        while (l > 1 && trace[l - 1] == '/') l--;
        size_t k = l;
        while (k > 0 && trace[k - 1] != '/') k--;
        snprintf(stem, sizeof stem, "%.*s", (int)(l - k), trace + k);
    } else snprintf(stem, sizeof stem, "%s", base);
    char *dot = strstr(stem, ".ptrace");
    if (dot) *dot = 0;
    const char *sub = NULL;
    if (strstr(stem, "load")) sub = "load";
    else if (strstr(stem, "eeprom")) sub = "eeprom-read";
    else if (strstr(stem, "ping")) sub = "ping";
    else if (strstr(stem, "unplug")) sub = "unplug-watch";
    else if (strstr(stem, "motor")) sub = "motor";
    else if (strstr(stem, "leds")) { sub = "leds"; if (strstr(stem, "off")) o->no_leds = true; }
    else if (strstr(stem, "dx")) { sub = "dx"; if (strstr(stem, "nolamp")) o->no_lamp = true; }   /* before "lamp": hw1-dx-nolamp (R-I2) */
    else if (strstr(stem, "lampoff")) sub = strstr(stem, "zero") ? "lamp-off-zero" : "lamp-off";   /* hw1-lampoff*, hw1-lampoff-zero* (S-R26 diagnostics) */
    else if (strstr(stem, "lamp")) { sub = "lamp"; if (strstr(stem, "idle")) o->no_keepalive = true; }
    else if (strstr(stem, "eject")) sub = "eject";
    if (!sub) { cli_say("Cannot tell which command made %s from its name (expected hw1-load, hw1-eeprom, hw1-ping, hw1-motor, hw1-leds, hw1-lamp, hw1-dx, hw1-unplug, hw1-eject).", trace); return 2; }
    char tmpl[] = "/tmp/pakon-replay-XXXXXX";
    char *tmp = mkdtemp(tmpl);
    if (!tmp) { cli_say("Cannot make a scratch folder in /tmp."); return 1; }
    char again[1100], home[1100];
    snprintf(again, sizeof again, "%s/again.ptrace", tmp);
    snprintf(home, sizeof home, "%s/home", tmp);
    o->replay = trace;
    o->trace = again;
    o->fast = true;
    if (!strcmp(sub, "eeprom-read")) { o->home = home; o->unit = NULL; }
    cli_say("Replaying %s as the command \"%s\"; the output below is that command running against the recording.", trace, sub);
    int cmd_rc = hw1_dispatch(o, sub);
    char tmp_events[1200];
    snprintf(tmp_events, sizeof tmp_events, "%s/events.jsonl", again);
    int rc = 1;
    if (access(tmp_events, R_OK) == 0) rc = compare_traces(trace, again);
    else cli_say("The replay run did not produce a trace (it failed before any transfer: exit code %d).", cmd_rc);
    if (rc == 0) cli_detail("the command itself ended with exit code %d (a recorded failure, such as the unplug test, replays as the same failure)", cmd_rc);
    if (rc == 0 && o->do_register) {
        char nm[200];
        snprintf(nm, sizeof nm, "%s", stem);
        rc = register_trace(trace, nm);
    }
    rm_tree(again);
    if (!strcmp(sub, "eeprom-read")) {
        char p[1300];
        snprintf(p, sizeof p, "%s/hw1-unit.txt", home); unlink(p);
    }
    return rc;
}

/* ------------------------------------------------------------------ dispatch */
/* HW-1 2026-10-19: after hw1 lamp the lamp stayed lit although a bare 0x80 = 0 was acknowledged. S-R26: pk_light_lamp_off is now TLB's
 * FN_bEndScan sequence (0x80 = 0, HOST 0x84 = 2, LIGHT 0x8A, then a 0x83 read). "lamp-off" sends exactly that, for use right after "lamp"
 * (and as the step-0 check of the HW-1 follow-up). "lamp-off-zero" is the documented FALLBACK DIAGNOSTIC, only if "lamp-off" leaves the lamp
 * lit: it first sets the drive to zero (0x82 all zero, period 982; PSI's init, v1 docs/59 steps 16-18). Both are ordinary allowed light-board packets. */
static int hw1_lamp_off(cli_opts *o, bool zero_drive) {
    cli_session s;
    if (cli_open(o, CLI_LOADED | CLI_BOARDS, &s)) return 1;
    pk_status st = PK_OK;
    if (zero_drive) {
        const uint16_t zero[4] = { 0, 0, 0, 0 };
        st = pk_light_set_duty(s.b, zero, 982);
        cli_say("Lamp drive set to zero (register 0x82, as PSI's start-up does): %s", pk_status_str(st));
    }
    uint8_t st83 = 0;
    pk_status off = pk_light_lamp_off_ex(s.b, &st83);
    cli_detail("lamp-off read-back: register 0x83 = 0x%02X (wanted bit 4 set, bit 1 clear)", (unsigned)st83);
    if (off == PK_OK) cli_say("Lamp off sent as Kodak's scan-end does (0x80 = 0, then the FIFO reset 0x84 / 0x8A) and the board confirms it. Look into the film path: is the lamp dark now?");
    else if (off == PK_E_DEVICE) cli_say("Lamp off sent (0x80 = 0, then the FIFO reset 0x84 / 0x8A) but the board did NOT confirm it (register 0x83 = 0x%02X). Look into the film path: is the lamp dark? If it is lit, switch the scanner off at its power switch.", (unsigned)st83);
    else cli_say("Lamp off FAILED: %s. If the lamp is lit, switch the scanner off at its power switch.", pk_status_str(off));
    cli_close(&s);
    return (st == PK_OK && off == PK_OK) ? 0 : 1;
}

static int hw1_dispatch(cli_opts *o, const char *sub) {
    if (!strcmp(sub, "lamp-off")) return hw1_lamp_off(o, false);
    if (!strcmp(sub, "lamp-off-zero")) return hw1_lamp_off(o, true);
    if (!strcmp(sub, "eeprom-read")) return hw1_eeprom_read(o);
    if (!strcmp(sub, "eeprom-scanner-type")) return hw1_scanner_type(o);
    if (!strcmp(sub, "ping")) return hw1_ping(o);
    if (!strcmp(sub, "motor")) return hw1_motor(o);
    if (!strcmp(sub, "leds")) return hw1_leds(o);
    if (!strcmp(sub, "lamp")) return hw1_lamp(o);
    if (!strcmp(sub, "dx")) return hw1_dx(o);
    if (!strcmp(sub, "unplug-watch")) return hw1_unplug(o);
    if (!strcmp(sub, "load")) return cli_cmd_load(o);
    if (!strcmp(sub, "eject")) return cli_cmd_film(o, "eject");
    fprintf(stderr, "pakon hw1: unknown step %s (try pakon --help)\n", sub);
    return 2;
}

int cli_cmd_hw1(cli_opts *o, int npos, const char **pos) {
    if (npos < 2) { cli_usage(stderr); return 2; }
    if (!strcmp(pos[1], "replay")) {
        if (npos < 3) { fputs("usage: pakon hw1 replay <trace> [--register]\n", stderr); return 2; }
        return hw1_replay(o, pos[2]);
    }
    int rc = hw1_dispatch(o, pos[1]);
    return g_cli_intr && rc == 0 ? 130 : rc;
}
