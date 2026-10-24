#define _POSIX_C_SOURCE 200809L
/* The roll object: sidecar, raw file, calibration, lazy strip decode (pass 1), DX re-feed, frame list. Hi-res crops are colour_input.c. */
#include "roll/roll_internal.h"
#include "pakon/session.h"
#include "pakon/vendor.h"
#include "calib/eeprom.h"
#include "calib/record.h"
#include "framing/frame.h"
#include "device/eeprom_store.h"
#include "util/util.h"
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#define CHUNK_LINES 128u

/* ------------------------------------------------------------------ open / close */
static const pk_model *model_by_name(const char *name) {
    if (!name) return NULL;
    for (int i = 0; i < (int)PK_MODEL__COUNT; i++) {
        const pk_model *m = pk_model_get((pk_model_id)i);
        if (m && strcmp(m->name, name) == 0) return m;
    }
    return NULL;
}

static bool num_field(const pku_json *o, const char *k, long long *v) {
    const pku_json *j = pku_json_get(o, k);
    if (!j || pku_json_type(j) != PKU_J_NUM || !pku_json_is_int(j)) return false;
    *v = pku_json_int(j);
    return true;
}

void pk_roll_close(pk_roll *r) {
    if (!r) return;
    for (int i = 0; i < r->n_strips; i++) {
        pkd_strip_free(r->st[i].strip);
        free(r->st[i].mean4);
        pk_framing_free(r->st[i].fr);
        pk_dx_free(r->st[i].dx);
    }
    free(r->st);
    pkcal_tables_free(&r->tables);
    pk_calibration_free(r->cal);
    free(r->ee);
    pk_calstore_close(r->store);
    pk_sidecar_free(r->sc);
    if (r->fp) fclose(r->fp);
    free(r);
}

pk_status pk_roll_open(const char *raw_path, const char *calstore_root, pk_roll **out) {
    if (out) *out = NULL;
    if (!raw_path || !out) return PK_E_ARG;
    if (calstore_root && !pk_lores_weights_loaded()) {         /* C9: the app keeps its vendor store at <calstore_root>/vendor; a caller with the weights elsewhere has loaded them */
        char vroot[1100];
        if (snprintf(vroot, sizeof vroot, "%s/vendor", calstore_root) < (int)sizeof vroot) (void)pk_lores_weights_load(vroot, NULL);
    }
    const size_t n = strlen(raw_path);
    if (n < 5 || n >= sizeof(((pk_roll *)0)->raw_path) - 4 || strcmp(raw_path + n - 4, ".raw") != 0) return PK_E_ARG;
    pk_roll *r = (pk_roll *)calloc(1, sizeof *r);
    if (!r) return PK_E_NOMEM;
    pk_status st = PK_OK;
    memcpy(r->raw_path, raw_path, n + 1);
    char json_path[1100];
    snprintf(json_path, sizeof json_path, "%.*s.json", (int)(n - 4), raw_path);
    if ((st = pk_sidecar_read(json_path, &r->sc)) != PK_OK) goto fail;
    r->fp = fopen(raw_path, "rb");
    if (!r->fp) { st = (errno == ENOENT ? PK_E_NOT_FOUND : PK_E_IO); goto fail; }
    if (fseeko(r->fp, 0, SEEK_END) != 0) { st = PK_E_IO; goto fail; }
    off_t sz = ftello(r->fp);
    if (sz < 0) { st = PK_E_IO; goto fail; }
    r->raw_size = (uint64_t)sz;
    const pku_json *root = pk_sidecar_json(r->sc);
    r->model = model_by_name(pk_sidecar_get_str(r->sc, "model"));
    r->dpi_base = (int)pk_sidecar_get_int(r->sc, "dpi_base", 0);
    const long long channels = pk_sidecar_get_int(r->sc, "channels", 3);
    if (!r->model || (channels != 3 && channels != 4)) { st = r->model ? PK_E_FORMAT : PK_E_UNSUPPORTED; goto fail; }
    r->ir = channels == 4;
    {   /* S-R45 a: the scan's IR cross-talk factor; a sidecar without it (an old scan, an import) is TLB's default 10 */
        long long f = PK_IR_CROSSTALK_DEFAULT;
        const pku_json *sc = root ? pku_json_get(root, "scan_config") : NULL;
        if (sc && pku_json_type(sc) == PKU_J_OBJ && pku_json_get(sc, "ir_crosstalk_factor")) {
            if (!num_field(sc, "ir_crosstalk_factor", &f)) { st = PK_E_CORRUPT; goto fail; }
        }
        r->ir_xtalk = f < (long long)PK_IR_CROSSTALK_MIN ? PK_IR_CROSSTALK_MIN : f > (long long)PK_IR_CROSSTALK_MAX ? PK_IR_CROSSTALK_MAX : (unsigned)f;
    }
    r->complete = pk_sidecar_get_bool(r->sc, "complete", false);
    if ((st = pkr_geometry(r->model, r->dpi_base, r->ir, &r->geom)) != PK_OK) goto fail;
    r->words_per_line = pk_words_per_line(r->model, r->dpi_base, r->ir);
    long long wpl = (long long)r->words_per_line;
    if (!num_field(root, "words_per_line", &wpl)) wpl = -1;                                // present but not an integer, or absent: refused
    if (r->words_per_line == 0 || wpl != (long long)r->words_per_line) { st = PK_E_FORMAT; goto fail; }
    const pku_json *strips = pku_json_get(root, "strips");
    const size_t ns = strips && pku_json_type(strips) == PKU_J_ARR ? pku_json_len(strips) : 0;
    if (ns > 4096) { st = PK_E_FORMAT; goto fail; }
    r->n_strips = (int)ns;
    r->st = (pkr_strip *)calloc(ns ? ns : 1, sizeof *r->st);
    if (!r->st) { st = PK_E_NOMEM; goto fail; }
    const uint64_t wl_bytes = (uint64_t)r->words_per_line * 2u;
    for (size_t i = 0; i < ns; i++) {
        pkr_strip *s = &r->st[i];
        const pku_json *js = pku_json_at(strips, i);
        if (pku_json_type(js) != PKU_J_OBJ) { st = PK_E_CORRUPT; goto fail; }
        s->js = js;
        long long bs = 0, be = 0, sg = 0;
        if (num_field(js, "byte_start", &bs) && bs >= 0) {
            if (!num_field(js, "byte_end", &be) || be < bs) be = bs;
            if (!pku_json_get(js, "segment_byte_start")) sg = bs;                    /* ABSENT: a sidecar from before fix round 1, no pre-film lines */
            else if (!num_field(js, "segment_byte_start", &sg)) { st = PK_E_CORRUPT; goto fail; }   /* present but null or not an integer: not a sidecar we can read as Kodak does */
            if (sg < 0 || sg > bs || (uint64_t)(bs - sg) % wl_bytes != 0) { st = PK_E_CORRUPT; goto fail; }
            s->byte_start = (uint64_t)bs;
            s->seg_start = (uint64_t)sg;
            s->pre = (size_t)((uint64_t)(bs - sg) / wl_bytes);
            uint64_t end = (uint64_t)be < r->raw_size ? (uint64_t)be : r->raw_size;      /* a partial roll: whatever the file holds */
            s->lines = end > s->byte_start ? (size_t)((end - s->byte_start) / wl_bytes) : 0;
            if (s->lines && s->seg_start > r->raw_size) { st = PK_E_CORRUPT; goto fail; }
            const char *eb = pku_json_str(pku_json_get(js, "ended_by"));
            if (eb && strcmp(eb, "incomplete") != 0 && s->lines && end == (uint64_t)be && end + wl_bytes <= r->raw_size) s->tail = 1;   /* the ending line is in the file */
        }
    }
    if ((st = pk_calstore_open(calstore_root, &r->store)) != PK_OK) goto fail;
    memset(r->sums, 0, sizeof r->sums);        /* S-R41: the roll's profile sums start at zero when the roll is opened */
    *out = r;
    return PK_OK;
fail:
    pk_roll_close(r);
    return st;
}

int  pk_roll_strip_count(const pk_roll *r) { return r ? r->n_strips : 0; }
bool pk_roll_complete(const pk_roll *r) { return r && r->complete; }
int  pk_roll_dpi_base(const pk_roll *r) { return r ? r->dpi_base : 0; }
bool pk_roll_ir(const pk_roll *r) { return r && r->ir; }

pk_status pk_roll_strip_lines(const pk_roll *r, int strip, size_t *lines) {
    if (!r || !lines || strip < 0 || strip >= r->n_strips) return PK_E_ARG;
    *lines = r->st[strip].lines;
    return PK_OK;
}

/* ------------------------------------------------------------------ calibration and EEPROM */
static pk_status le_blob(const pk_calibration *c, const char *name, size_t unit, size_t count, uint8_t **buf) {
    size_t n = 0;
    const uint8_t *b = (const uint8_t *)pk_calibration_blob(c, name, &n);
    if (!b) return PK_E_NOT_FOUND;
    if (n != count * unit) return PK_E_CORRUPT;
    *buf = (uint8_t *)b;
    return PK_OK;
}

/* Tables from the stored dark.u16 / gain.u32 / smear.json (a calibration without raw sums: imported-file). Channel-major, n_px each, little-endian. */
static pk_status tables_from_blobs(const pk_calibration *c, int nch, int n_px, pk_cal_tables *t) {
    memset(t, 0, sizeof *t);
    t->n_px = n_px;
    const uint8_t *dk, *gn;
    pk_status st = le_blob(c, "dark.u16", 2, (size_t)nch * n_px, (uint8_t **)&dk);
    if (st == PK_OK) st = le_blob(c, "gain.u32", 4, (size_t)nch * n_px, (uint8_t **)&gn);
    if (st != PK_OK) return st == PK_E_NOT_FOUND ? PK_E_CORRUPT : st;
    for (int ch = 0; ch < nch && st == PK_OK; ch++) {
        t->dark[ch] = (uint16_t *)malloc((size_t)n_px * 2);
        t->gain[ch] = (uint32_t *)malloc((size_t)n_px * 4);
        if (!t->dark[ch] || !t->gain[ch]) { st = PK_E_NOMEM; break; }
        for (int i = 0; i < n_px; i++) {
            const uint8_t *p = dk + 2 * ((size_t)ch * n_px + i), *q = gn + 4 * ((size_t)ch * n_px + i);
            t->dark[ch][i] = (uint16_t)(p[0] | p[1] << 8);
            t->gain[ch][i] = (uint32_t)q[0] | (uint32_t)q[1] << 8 | (uint32_t)q[2] << 16 | (uint32_t)q[3] << 24;
        }
    }
    size_t sn = 0;
    const char *sj = (const char *)pk_calibration_blob(c, "smear.json", &sn);
    pku_json *j = NULL;
    if (st == PK_OK && (!sj || pku_json_parse(sj, sn, &j) != PK_OK)) { j = NULL; st = PK_E_CORRUPT; }
    if (st == PK_OK) {
        const pku_json *a = pku_json_get(j, "smearc");
        if (!a || pku_json_type(a) != PKU_J_ARR || pku_json_len(a) != 3) st = PK_E_CORRUPT;
        for (size_t i = 0; st == PK_OK && i < 3; i++) {
            const pku_json *e = pku_json_at(a, i);
            if (!pku_json_is_int(e) || pku_json_int(e) < 0 || pku_json_int(e) > 0xFFFF) st = PK_E_CORRUPT; else t->smearc[i] = (uint16_t)pku_json_int(e);
        }
    }
    pku_json_free(j);
    if (st == PK_OK && nch == 4) {
        const uint8_t *sm;
        st = le_blob(c, "smear_ir.u16", 2, (size_t)3 * n_px, (uint8_t **)&sm);
        for (int ch = 0; ch < 3 && st == PK_OK; ch++) {
            t->smear[ch] = (uint16_t *)malloc((size_t)n_px * 2);
            if (!t->smear[ch]) { st = PK_E_NOMEM; break; }
            for (int i = 0; i < n_px; i++) { const uint8_t *p = sm + 2 * ((size_t)ch * n_px + i); t->smear[ch][i] = (uint16_t)(p[0] | p[1] << 8); }
        }
    }
    if (st != PK_OK) pkcal_tables_free(t);
    return st;
}

pk_status pkr_load_calibration(pk_roll *r) {
    if (r->cal_loaded) return PK_OK;
    const pku_json *ids = pku_json_get(pk_sidecar_json(r->sc), "calibration_ids");
    const size_t ni = ids && pku_json_type(ids) == PKU_J_ARR ? pku_json_len(ids) : 0;
    const char *id = ni ? pku_json_str(pku_json_at(ids, ni - 1)) : NULL;       /* the child session calibration is last: it holds this scan's own dark and flat */
    if (!id || !*id) return PK_E_NOT_FOUND;
    pk_calibration *c = NULL;
    pk_status st = pk_calstore_get(r->store, id, &c);
    if (st != PK_OK) return st;
    const pk_cal_light *l = pk_calibration_light(c);
    const int nch = r->ir ? 4 : 3;
    pk_cal_tables t;
    memset(&t, 0, sizeof t);
    if (!l || l->dpi_base != r->dpi_base || l->ir != r->ir) st = PK_E_FORMAT;           /* a calibration of another base or IR setting has other tables */
    if (st == PK_OK) {
        if (pk_calibration_blob(c, "raw/dark_sum.u32", NULL)) st = pkcal_rederive(c, &t);
        else st = tables_from_blobs(c, nch, r->geom.hires_px, &t);
    }
    if (st == PK_OK && t.n_px != r->geom.hires_px) { pkcal_tables_free(&t); st = PK_E_FORMAT; }
    if (st != PK_OK) { pk_calibration_free(c); return st; }
    /* the unit's saved EEPROM image */
    pk_eeprom *ee = (pk_eeprom *)malloc(sizeof *ee);
    uint8_t *img = (uint8_t *)malloc(PKCAL_EEPROM_SIZE);
    if (!ee || !img) st = PK_E_NOMEM;
    if (st == PK_OK) st = pk_eeprom_store_current(pk_calibration_unit(c), pkcal_store_root(r->store), img);
    if (st == PK_OK) st = pkcal_eeprom_parse(img, ee);
    free(img);
    if (st != PK_OK) { free(ee); pkcal_tables_free(&t); pk_calibration_free(c); return st; }
    r->cal = c; r->tables = t; r->ee = ee; r->cal_loaded = true;
    return PK_OK;
}

/* ------------------------------------------------------------------ raw lines */
pk_status pkr_read_lines(pk_roll *r, int strip, size_t first, size_t n, uint16_t *out) {
    const pkr_strip *s = &r->st[strip];
    if (first + n > s->pre + s->lines + s->tail) return PK_E_ARG;
    const size_t words = n * r->words_per_line;
    const uint64_t at = s->seg_start + (uint64_t)first * r->words_per_line * 2u;
    if (fseeko(r->fp, (off_t)at, SEEK_SET) != 0) return PK_E_IO;
    uint8_t *tmp = (uint8_t *)malloc(words * 2);
    if (!tmp) return PK_E_NOMEM;
    if (fread(tmp, 1, words * 2, r->fp) != words * 2) { free(tmp); return PK_E_IO; }
    for (size_t i = 0; i < words; i++) out[i] = (uint16_t)(tmp[2 * i] | tmp[2 * i + 1] << 8);       /* the stream is little-endian on every host */
    free(tmp);
    for (size_t l = 0; l < n; l++) if (!(out[l * r->words_per_line] & 1)) return PK_E_CORRUPT;      /* every line starts with a sync word: a misaligned offset is not decodable */
    return PK_OK;
}

/* ------------------------------------------------------------------ pass 1 */
pk_status pkr_decode_strip(pk_roll *r, int k) {
    pkr_strip *s = &r->st[k];
    if (s->decoded) return PK_OK;
    pk_status st;
    if (k > 0 && (st = pkr_decode_strip(r, k - 1)) != PK_OK) return st;      /* S-R41: the sums run in strip order whatever the caller asks for */
    memcpy(s->sums_end, k > 0 ? r->st[k - 1].sums_end : r->sums, sizeof s->sums_end);
    if (s->lines == 0) { s->decoded = true; return PK_OK; }
    if ((st = pkr_load_calibration(r)) != PK_OK) return st;
    const pkr_geom *g = &r->geom;
    const size_t total = s->pre + s->lines + s->tail;       /* every synced line from the segment start, the ending line included */
    pkd_strip *ps = NULL;
    uint16_t *raw = NULL, *hi = NULL;
    uint16_t (*m4)[3] = NULL;
    pk_framing *fr = NULL;
    st = pkd_strip_new(g->ratio, g->lores_px, s->lines, &ps);
    if (st == PK_OK) {
        raw = (uint16_t *)malloc((size_t)CHUNK_LINES * r->words_per_line * 2);
        hi = (uint16_t *)malloc((size_t)r->words_per_line * 2);
        m4 = (uint16_t(*)[3])malloc(total * sizeof *m4);
        if (!raw || !hi || !m4) st = PK_E_NOMEM;
    }
    if (st == PK_OK) {
        /* TLB's per-strip loop (archive scan decompile 200-231, 552-582; RE 30 sec 4.3 / 4.4): the kernel is initialised (init = 1) at the segment's first synced line and
         * EVERY line from there is fed, with film = (film found && not stopped). Film is found by the call that reads the detect line, so that line itself is fed with
         * film 0 (it is the first hi-res line) and film is 1 from the next line on; the block counter runs from the segment start, so a stored row may hold up to
         * ratio-1 pre-film lines. The ENDING line (line_end + 1) is fed too, with film 1: the stop flag is set after its call but before the hi-res advance (decompile 607-650),
         * so it is in the lo-res strip but not in the hi-res lines or the hand-off count. */
        pkd_kernel_cfg kc = { g->hires_px, g->planes, g->ratio, &r->tables, r->ir ? r->ir_xtalk : 0 };
        pkd_kernel_state ks;
        pkd_kernel_init(&ks);
        pkd_strip_share_profile_sums(ps, s->sums_end);
        pkd_strip_set_film(ps, 0);
        for (size_t l = 0; l < total && st == PK_OK;) {
            size_t n = total - l < CHUNK_LINES ? total - l : CHUNK_LINES;
            if ((st = pkr_read_lines(r, k, l, n, raw)) != PK_OK) break;
            for (size_t i = 0; i < n && st == PK_OK; i++, l++) {
                if (l == s->pre + 1) pkd_strip_set_film(ps, 1);
                st = pkd_strip_feed(ps, &kc, &ks, raw + i * r->words_per_line, hi);
                memcpy(m4[l], ks.mean4, sizeof m4[l]);
            }
        }
    }
    if (st == PK_OK) {
        ps->film_lines = s->lines;      /* the hand-off count (strip+0xca0, RE 30 UNRESOLVED 2) is the write thread's counter, which counts the detect line too (decompile 643-650): L, not L - 1 */
        st = pkd_strip_finish(ps);
    }
    const size_t readable = pkr_hires_readable_lines(s->lines, g->ratio, g->planes);
    if (st == PK_OK && readable > 0) {                  /* a strip too short to frame (1..2d lines) has no frames and must not stop the strips after it */
        pk_frame_params fp = { g->frame_lines, (int)readable, g->ratio, false, NULL, 0 };
        st = pkf_frame_strip(ps, g->planes, &fp, NULL, &fr);
    }
    free(raw); free(hi);
    if (st != PK_OK) { pkd_strip_free(ps); free(m4); return st; }
    s->strip = ps; s->mean4 = m4; s->fr = fr; s->decoded = true;
    return PK_OK;
}

/* ------------------------------------------------------------------ frames */
pk_status pk_roll_frames(const pk_roll *cr, int strip, const pk_frame_rect **rects, int *n) {
    pk_roll *r = (pk_roll *)cr;
    if (!r || !rects || !n || strip < 0 || strip >= r->n_strips) return PK_E_ARG;
    pk_status st = pkr_decode_strip(r, strip);
    if (st != PK_OK) return st;
    const pk_framing *f = r->st[strip].fr;
    *rects = f ? f->rects : NULL;
    *n = f ? f->n : 0;
    return PK_OK;
}

pk_status pk_roll_framing_info_get(const pk_roll *cr, int strip, pk_roll_framing_info *out) {
    pk_roll *r = (pk_roll *)cr;
    if (!r || !out || strip < 0 || strip >= r->n_strips) return PK_E_ARG;
    pk_status st = pkr_decode_strip(r, strip);
    if (st != PK_OK) return st;
    const pk_framing *f = r->st[strip].fr;
    out->n_frames = f ? f->n : 0;
    out->scanw = f ? f->scanw : 0;
    out->not_kodak_exact = f ? f->not_kodak_exact : false;
    return PK_OK;
}

/* ------------------------------------------------------------------ DX */
pk_status pkr_dx_object(pk_roll *r, int k, pk_dx **dx) {
    pkr_strip *s = &r->st[k];
    if (!s->dx) {
        pk_dx_geometry g;
        pk_status st = pk_dx_geometry_for(r->dpi_base, r->ir, &g);
        if (st != PK_OK) return st;
        g.single_strip = r->n_strips == 1;              /* FN_bEndScan passes (strips == 1) as the speed-analysis flag */
        pk_dx *d = NULL;
        if ((st = pk_dx_new_geometry(&g, &d)) != PK_OK) return st;
        const pku_json *pk = pku_json_get(s->js, "dx_packets");
        const size_t np = pk && pku_json_type(pk) == PKU_J_ARR ? pku_json_len(pk) : 0;
        for (size_t i = 0; i < np && st == PK_OK; i++) {
            const char *b64 = pku_json_str(pku_json_at(pk, i));
            uint8_t buf[PK_DX_PACKET_LEN + 4];
            size_t got = 0;
            if (!b64 || pku_b64_decode(b64, strlen(b64), buf, sizeof buf, &got) != PK_OK || got != PK_DX_PACKET_LEN) st = PK_E_CORRUPT;
            else if (pk_dx_feed_packet(d, buf, got) != PK_OK) st = PK_E_CORRUPT;       /* a packet pk_dx refuses is not a protocol event of this call: the sidecar is bad */
        }
        if (st != PK_OK) { pk_dx_free(d); return st; }
        s->dx = d;
    }
    *dx = s->dx;
    return PK_OK;
}

pk_status pkr_dx(pk_roll *r, int k, pk_dx_strip *out) {
    pkr_strip *s = &r->st[k];
    if (!s->dx_done) {
        pk_dx *d;
        pk_status st = pkr_dx_object(r, k, &d);
        if (st != PK_OK) return st;
        pk_dx_strip res;
        if ((st = pk_dx_finish_strip(d, true, &res)) != PK_OK) return st;
        long long p = 0, sp = 0;
        const char *src = pku_json_str(pku_json_get(s->js, "dx_source"));
        if (res.product < 0 && src && strcmp(src, "manual") == 0 && num_field(s->js, "product", &p) && num_field(s->js, "specifier", &sp) && p >= 0 && p <= 32767 && sp >= 0 && sp <= 15) {
            res.product = (int)p;                        /* the scan took the caller's film: the packets gave none */
            res.specifier = (int)sp;
            strcpy(res.dx_source, "manual");
        }
        s->dxr = res;
        s->dx_done = true;
    }
    *out = s->dxr;
    if (s->manual) { out->product = s->man_product; out->specifier = s->man_spec; strcpy(out->dx_source, "manual"); }
    return PK_OK;
}

pk_status pk_roll_dx(const pk_roll *cr, int strip, pk_dx_strip *out) {
    pk_roll *r = (pk_roll *)cr;
    if (!r || !out || strip < 0 || strip >= r->n_strips) return PK_E_ARG;
    return pkr_dx(r, strip, out);
}

pk_status pk_roll_set_manual_film(pk_roll *r, int strip, int product, int specifier) {
    if (!r || strip < 0 || strip >= r->n_strips) return PK_E_ARG;
    const bool none = product == PK_DX_NONE && specifier == PK_DX_NONE;
    if (!none && (product < 0 || product > 32767 || specifier < 0 || specifier > 15)) return PK_E_ARG;
    r->st[strip].manual = true;
    r->st[strip].man_product = product;
    r->st[strip].man_spec = specifier;
    return PK_OK;
}

pk_status pk_roll_frame_number(const pk_roll *cr, int frame, int *half_frames, bool *read_not_extrapolated) {
    pk_roll *r = (pk_roll *)cr;
    if (!r || !half_frames || frame < 0) return PK_E_ARG;
    int base = 0;
    for (int k = 0; k < r->n_strips; k++) {
        pk_status st = pkr_decode_strip(r, k);
        if (st != PK_OK) return st;
        const int nf = r->st[k].fr ? r->st[k].fr->n : 0;
        if (frame < base + nf) {
            pk_dx *d;
            if ((st = pkr_dx_object(r, k, &d)) != PK_OK) return st;
            pk_dx_strip tmp;
            if ((st = pkr_dx(r, k, &tmp)) != PK_OK) return st;                  /* the end-of-strip analysis runs once, in finish_strip */
            bool rd = false;
            *half_frames = pk_dx_frame_half_frames(d, frame - base, &rd);
            if (read_not_extrapolated) *read_not_extrapolated = rd;
            return PK_OK;
        }
        base += nf;
    }
    return PK_E_ARG;
}
