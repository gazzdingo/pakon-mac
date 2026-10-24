/* Scan configuration (Task 13): defaults, validation, the film-length limit and strip budget (TLB 0x1002e1fa..0x1002e2c0), and the JSON round trip
 * the roll sidecar uses. Nothing here touches hardware. */
#include <stdlib.h>
#include <string.h>
#include "pakon/session.h"
#include "pakon/stream.h"
#include "util/util.h"

#define PK_SC_KNOWN (PK_SC_AGGRESSIVE_FRAMING | PK_SC_RFT_SENSE_SPLICE | PK_SC_SCRATCH_REMOVAL | PK_SC_USE_24MM_AUTOLOADER | PK_SC_HAS_FILM_DRAG | PK_SC_PRESCAN | PK_SC_PREMIUM_COLOUR)
#define PKS_LEN_PX_DIV 23700u            /* PB+0x60 = 0x5C94: the same constant at every base (RE 41 sec 3.2) */
#define PKS_MAX_STRIPS 15u               /* 0x1002e2ab..0x1002e2b6 */

static const pk_base_geom *geom_of(const pk_model *m, int dpi_base) {
    if (!m || pk_model_check_base(m, dpi_base) != PK_OK) return NULL;
    return &m->geom[dpi_base == 4 ? 0 : dpi_base == 8 ? 1 : 2];
}

pk_status pk_scan_config_default(const pk_model *m, pk_scan_config *out) {
    if (!m || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    out->version = 1;
    out->dpi_base = pk_model_check_base(m, 16) == PK_OK ? 16 : pk_model_check_base(m, 8) == PK_OK ? 8 : 4;
    out->film_format = PK_FILM_35MM;
    out->strip_mode = PK_STRIPS_FULL_ROLL;
    out->roll_mode = PK_ROLL_NORMAL;
    out->max_film_length_mm = 1670;      /* PSI rewrites TLB's 1600 to 1670 (PSI FUN_00448750); the owner's hive holds 1670 (RE 41 sec 3.1) */
    out->no_film_timeout_s = 120;        /* the owner's PSI NoFilmTimeOut; TLB's own default is 60 */
    out->film_speed = 0;
    strcpy(out->calibration_pin, "auto");
    out->manual_product = out->manual_specifier = -1;
    out->feed_mode = 0;
    out->splice_advance_ms = 750;
    out->ir_crosstalk_factor = PK_IR_CROSSTALK_DEFAULT;
    return PK_OK;
}

unsigned pk_scan_length_limit_lines(const pk_model *m, int dpi_base, unsigned mm) {
    const pk_base_geom *g = geom_of(m, dpi_base);
    if (!g || g->hires_px <= 0) return 0;
    /* lines = trunc((double)maxmm x PB+0x68 x 1000.0 / PB+0x60) through _ftol (truncation, RE 04) */
    return (unsigned)((double)mm * (double)g->hires_px * 1000.0 / (double)PKS_LEN_PX_DIV);
}

pk_status pk_scan_strip_budget(const pk_model *m, const pk_scan_config *c, unsigned *strips, unsigned *lines_per_strip) {
    if (!m || !c || !strips || !lines_per_strip) return PK_E_ARG;
    const pk_base_geom *g = geom_of(m, c->dpi_base);
    if (!g || g->hires_px <= 0 || g->window_lines <= 0) return PK_E_ARG;
    unsigned lines = pk_scan_length_limit_lines(m, c->dpi_base, c->max_film_length_mm);
    if (c->strip_mode == PK_STRIPS_FULL_ROLL) {
        *strips = 1;
        *lines_per_strip = lines;
        return PK_OK;
    }
    if (c->strip_mode != PK_STRIPS_MULTI_4 && c->strip_mode != PK_STRIPS_MULTI_5 && c->strip_mode != PK_STRIPS_MULTI_6) return PK_E_ARG;
    unsigned f = (unsigned)c->strip_mode;
    unsigned u = ((unsigned)g->window_lines * PKS_LEN_PX_DIV) / (unsigned)g->hires_px;    /* one frame window in um (37991 at every base), unsigned division */
    unsigned n = (c->max_film_length_mm * 1000u) / (f * u + u / 4u);
    if (n > PKS_MAX_STRIPS) n = PKS_MAX_STRIPS;
    *strips = n;
    *lines_per_strip = n ? lines / n : 0;      /* TLB divides by n unguarded; n = 0 is refused by validation (RE 41 U10) */
    return PK_OK;
}

/* TLB clamps the registry value right after reading it: < 1 -> 1, > 20 -> 20 (0x10010da7..0x10010dbb, RE 45 sec 4.1). */
static unsigned xtalk_clamp(long long v) {
    return v < (long long)PK_IR_CROSSTALK_MIN ? PK_IR_CROSSTALK_MIN : v > (long long)PK_IR_CROSSTALK_MAX ? PK_IR_CROSSTALK_MAX : (unsigned)v;
}

static bool pin_ok(const char *p) {
    size_t n = memchr(p, 0, 65) ? strlen(p) : 65;
    if (n == 0 || n > 64) return false;
    for (size_t i = 0; i < n; i++) {
        char ch = p[i];
        if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch == '_' || ch == '-' || ch == '.')) return false;
    }
    return true;
}

pk_status pk_scan_config_validate(const pk_model *m, const pk_scan_config *c, const pk_scan_config *prev, bool film_loaded) {
    if (!m || !c) return PK_E_ARG;
    if (c->version != 1) return PK_E_ARG;
    /* malformed values first (PK_E_ARG) ... */
    if (c->strip_mode != PK_STRIPS_FULL_ROLL && c->strip_mode != PK_STRIPS_MULTI_4 && c->strip_mode != PK_STRIPS_MULTI_5 && c->strip_mode != PK_STRIPS_MULTI_6) return PK_E_ARG;
    if (c->roll_mode != PK_ROLL_NORMAL && c->roll_mode != PK_ROLL_LONG && c->roll_mode != PK_ROLL_SPLICED) return PK_E_ARG;
    if (c->film_format != PK_FILM_35MM && c->film_format != PK_FILM_24MM) return PK_E_ARG;
    if (c->scan_control & ~(unsigned)PK_SC_KNOWN) return PK_E_ARG;
    if ((c->scan_control & PK_SC_RFT_SENSE_SPLICE) && (c->scan_control & PK_SC_SCRATCH_REMOVAL)) return PK_E_ARG;   /* TLB validation 0x1003c2db */
    /* TLB's one IR switch is scan_control & 8 (BeforeScan S+0x378 = ctl & 8, RE 42 sec 2): an IR capture and "scratch removal" are the same bit, so the two fields must agree. */
    if (c->ir != ((c->scan_control & PK_SC_SCRATCH_REMOVAL) != 0)) return PK_E_ARG;
    if (c->max_film_length_mm < 24 || c->max_film_length_mm > 6400) return PK_E_ARG;                            /* TLB 0x1004174c, string iMaxFilmLength_mm */
    if (c->no_film_timeout_s < 10 || c->no_film_timeout_s > 300) return PK_E_ARG;                               /* TLB 0x10041485 */
    if (c->feed_mode > 2) return PK_E_ARG;                                                                      /* PSI FeedMode 0..2 (RE 47 sec 2) */
    if (c->feed_mode == 2 && (c->splice_advance_ms < 1 || c->splice_advance_ms > 300000u)) return PK_E_ARG;     /* AdvanceFilm validates 1..300000 ms */
    if (c->film_speed != 0) return PK_E_ARG;          /* S-R35: PSI exposes no scan speed; the scan always runs at its per-base MotorAdjust x MotorSpeedPlus */
    if (!pin_ok(c->calibration_pin)) return PK_E_ARG;
    if (!((c->manual_product == -1 && c->manual_specifier == -1) || (c->manual_product >= 0 && c->manual_specifier >= 0))) return PK_E_ARG;
    /* ... then what this model lacks (PK_E_UNSUPPORTED) ... */
    pk_status s = pk_model_check_base(m, c->dpi_base);
    if (s != PK_OK) return s;
    if (c->roll_mode == PK_ROLL_LONG && !(m->caps & PK_CAP_LONG_ROLL)) return PK_E_UNSUPPORTED;
    if (c->roll_mode == PK_ROLL_SPLICED && !(m->caps & PK_CAP_SPLICE)) return PK_E_UNSUPPORTED;
    if (c->film_format == PK_FILM_24MM && (!(m->caps & PK_CAP_APS_24MM) || !(m->caps & PK_CAP_GUIDES))) return PK_E_UNSUPPORTED;
    if ((c->scan_control & PK_SC_USE_24MM_AUTOLOADER) && !(m->caps & PK_CAP_APS_24MM)) return PK_E_UNSUPPORTED;
    /* TLB has no model or base gate for IR (RE 42 sec 2): any model and base with a line width can capture it. The F-135 Plus is the one the scan sequence supports. */
    if (c->ir && pk_words_per_line(m, c->dpi_base, true) == 0) return PK_E_UNSUPPORTED;
    /* Prescan is refused (S-R34 b, RE 42 sec 3): TLB's prescan stops after the lamp-on and never runs EndScan, leaving the lamp lit, and PSI's use of it is UNRESOLVED. */
    if (c->scan_control & PK_SC_PRESCAN) return PK_E_UNSUPPORTED;
    /* ... then the strip budget (TLB divides by zero here, RE 41 U10) ... */
    unsigned strips, lps;
    if (pk_scan_strip_budget(m, c, &strips, &lps) != PK_OK || strips == 0 || lps == 0) return PK_E_ARG;
    /* ... and last the state-dependent rule. */
    if (prev && film_loaded && prev->roll_mode != c->roll_mode) return PK_E_BUSY;
    return PK_OK;
}

/* ---------------------------------------------------------------- JSON */
static const char *const ROLL_NAME[] = { "normal", "long", "spliced" };

pk_status pk_scan_config_to_json(const pk_scan_config *c, char **json) {
    if (!c || !json) return PK_E_ARG;
    *json = NULL;
    pku_jw *w = pku_jw_new();
    if (!w) return PK_E_NOMEM;
    pku_jw_obj_begin(w);
    pku_jw_key(w, "version"); pku_jw_uint(w, c->version);
    pku_jw_key(w, "dpi_base"); pku_jw_int(w, c->dpi_base);
    pku_jw_key(w, "ir"); pku_jw_bool(w, c->ir);
    pku_jw_key(w, "film_format"); pku_jw_str(w, c->film_format == PK_FILM_24MM ? "24mm" : "35mm");
    pku_jw_key(w, "strip_mode"); pku_jw_int(w, (int)c->strip_mode);
    pku_jw_key(w, "roll_mode"); pku_jw_str(w, (unsigned)c->roll_mode < 3 ? ROLL_NAME[c->roll_mode] : "normal");
    pku_jw_key(w, "max_film_length_mm"); pku_jw_uint(w, c->max_film_length_mm);
    pku_jw_key(w, "no_film_timeout_s"); pku_jw_uint(w, c->no_film_timeout_s);
    pku_jw_key(w, "scan_control"); pku_jw_uint(w, c->scan_control);
    pku_jw_key(w, "film_speed"); pku_jw_int(w, c->film_speed);
    pku_jw_key(w, "calibration_pin"); pku_jw_str(w, c->calibration_pin);
    pku_jw_key(w, "manual_product"); pku_jw_int(w, c->manual_product);
    pku_jw_key(w, "manual_specifier"); pku_jw_int(w, c->manual_specifier);
    pku_jw_key(w, "feed_mode"); pku_jw_uint(w, c->feed_mode);
    pku_jw_key(w, "splice_advance_ms"); pku_jw_uint(w, c->splice_advance_ms);
    pku_jw_key(w, "ir_crosstalk_factor"); pku_jw_uint(w, xtalk_clamp((long long)c->ir_crosstalk_factor));
    pku_jw_obj_end(w);
    size_t n = 0;
    const char *txt = pku_jw_finish(w, &n);
    char *out = txt ? (char *)malloc(n + 1) : NULL;
    if (out) { memcpy(out, txt, n); out[n] = 0; }
    pku_jw_free(w);
    if (!out) return PK_E_NOMEM;
    *json = out;
    return PK_OK;
}

static bool get_int(const pku_json *o, const char *key, long long *v) {
    const pku_json *j = pku_json_get(o, key);
    if (!j || !pku_json_is_int(j)) return false;
    *v = pku_json_int(j);
    return true;
}

/* Reads a scan_config object (keys as pk_scan_config_to_json writes them). Every key must be present and well-typed: PK_E_CORRUPT otherwise. */
static pk_status config_from_json(const pku_json *o, pk_scan_config *out) {
    if (!o || pku_json_type(o) != PKU_J_OBJ) return PK_E_CORRUPT;
    pk_scan_config c;
    memset(&c, 0, sizeof c);
    long long v;
    const pku_json *j;
    if (!get_int(o, "version", &v) || v != 1) return PK_E_CORRUPT;
    c.version = 1;
    if (!get_int(o, "dpi_base", &v)) return PK_E_CORRUPT; c.dpi_base = (int)v;
    if (!(j = pku_json_get(o, "ir")) || pku_json_type(j) != PKU_J_BOOL) return PK_E_CORRUPT; c.ir = pku_json_bool(j) != 0;
    if (!(j = pku_json_get(o, "film_format")) || !pku_json_str(j)) return PK_E_CORRUPT;
    if (!strcmp(pku_json_str(j), "35mm")) c.film_format = PK_FILM_35MM; else if (!strcmp(pku_json_str(j), "24mm")) c.film_format = PK_FILM_24MM; else return PK_E_CORRUPT;
    if (!get_int(o, "strip_mode", &v)) return PK_E_CORRUPT; c.strip_mode = (pk_strip_mode)v;
    if (!(j = pku_json_get(o, "roll_mode")) || !pku_json_str(j)) return PK_E_CORRUPT;
    int rm = -1;
    for (int i = 0; i < 3; i++) if (!strcmp(pku_json_str(j), ROLL_NAME[i])) rm = i;
    if (rm < 0) return PK_E_CORRUPT;
    c.roll_mode = (pk_roll_mode)rm;
    if (!get_int(o, "max_film_length_mm", &v) || v < 0 || v > 0xFFFFFFFFll) return PK_E_CORRUPT; c.max_film_length_mm = (unsigned)v;
    if (!get_int(o, "no_film_timeout_s", &v) || v < 0 || v > 0xFFFFFFFFll) return PK_E_CORRUPT; c.no_film_timeout_s = (unsigned)v;
    if (!get_int(o, "scan_control", &v) || v < 0 || v > 0xFFFFFFFFll) return PK_E_CORRUPT; c.scan_control = (unsigned)v;
    if (!get_int(o, "film_speed", &v) || v < -0x7FFFFFFFll || v > 0x7FFFFFFFll) return PK_E_CORRUPT; c.film_speed = (int)v;
    if (!(j = pku_json_get(o, "calibration_pin")) || !pku_json_str(j) || strlen(pku_json_str(j)) > 64) return PK_E_CORRUPT;
    strcpy(c.calibration_pin, pku_json_str(j));
    if (!get_int(o, "manual_product", &v) || v < -0x7FFFFFFFll || v > 0x7FFFFFFFll) return PK_E_CORRUPT; c.manual_product = (int)v;
    if (!get_int(o, "manual_specifier", &v) || v < -0x7FFFFFFFll || v > 0x7FFFFFFFll) return PK_E_CORRUPT; c.manual_specifier = (int)v;
    c.feed_mode = 0; c.splice_advance_ms = 750;                      /* a sidecar from before RE 47 has neither: the owner's values */
    if (pku_json_get(o, "feed_mode")) { if (!get_int(o, "feed_mode", &v) || v < 0 || v > 0xFFFFFFFFll) return PK_E_CORRUPT; c.feed_mode = (unsigned)v; }
    if (pku_json_get(o, "splice_advance_ms")) { if (!get_int(o, "splice_advance_ms", &v) || v < 0 || v > 0xFFFFFFFFll) return PK_E_CORRUPT; c.splice_advance_ms = (unsigned)v; }
    c.ir_crosstalk_factor = PK_IR_CROSSTALK_DEFAULT;                 /* a sidecar from before S-R45 a has no such key: TLB's default */
    if (pku_json_get(o, "ir_crosstalk_factor")) {
        if (!get_int(o, "ir_crosstalk_factor", &v)) return PK_E_CORRUPT;
        c.ir_crosstalk_factor = xtalk_clamp(v);
    }
    *out = c;
    return PK_OK;
}

pk_status pk_scan_config_from_sidecar(const char *sidecar_path, pk_scan_config *out) {
    if (!sidecar_path || !out) return PK_E_ARG;
    pk_sidecar *sc = NULL;
    pk_status s = pk_sidecar_read(sidecar_path, &sc);
    if (s != PK_OK) return s;
    const pku_json *root = pk_sidecar_json(sc);
    const pku_json *cj = root ? pku_json_get(root, "scan_config") : NULL;
    s = !root ? PK_E_NOMEM : !cj ? PK_E_NOT_FOUND : config_from_json(cj, out);
    pk_sidecar_free(sc);
    return s;
}
