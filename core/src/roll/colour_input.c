#define _POSIX_C_SOURCE 200809L
/* pk_roll_colour_input: the hand-off of decode and framing to the colour library in TLB's layout (spec section N). Pass 2 of a strip: for every frame rectangle the
 * kernel is re-run over the frame's lines (starting from the state pass 1 recorded), the corrected planar lines are staged and TLB's registered read-out
 * (FUN_100013b0, pkd_readout_planes) cuts the hi-res frame; the lo-res frame is the registered lo-res strip read at d = 1 and turned by 180 degrees. */
#include "roll/roll_internal.h"
#include "util/util.h"
#include <stdlib.h>
#include <string.h>

#define CHUNK_LINES 128u

struct pk_roll_input_storage {
    int n;
    pk_frame_linear *frames, *lores;
    uint16_t **hi;              /* per frame: planes x h x w words (the fourth plane is IR on an IR roll); NULL until pk_roll_colour_frame loads it */
    uint16_t **lo;              /* per frame: 3 x h x w */
    int *h, *w;                 /* hi-res size of each frame (for the IR accessor) */
    bool ir;
    const pk_roll *roll;        /* the roll and strip this storage was made from: pk_roll_colour_frame refuses any other */
    int strip_index;
    uint16_t *strip;            /* 3 x rows x width */
};

void pk_roll_input_storage_free(pk_roll_input_storage *k) {
    if (!k) return;
    for (int i = 0; i < k->n; i++) { if (k->hi) free(k->hi[i]); if (k->lo) free(k->lo[i]); }
    free(k->hi); free(k->lo); free(k->frames); free(k->lores); free(k->h); free(k->w); free(k->strip);
    free(k);
}

const uint16_t *pk_roll_input_storage_ir(const pk_roll_input_storage *k, int frame) {
    if (!k || !k->ir || frame < 0 || frame >= k->n || !k->hi[frame]) return NULL;
    return k->hi[frame] + (size_t)3 * (size_t)k->h[frame] * (size_t)k->w[frame];
}

static bool is_beta_family(const pk_model *m) {
    return m->id == PK_MODEL_F235 || m->id == PK_MODEL_F235C || m->id == PK_MODEL_F335 || m->id == PK_MODEL_F335C;
}

/* One hi-res frame into buf (planes x rows x hires_px words). */
static pk_status hires_crop(pk_roll *r, int k, const pk_frame_rect *rc, uint16_t *buf) {
    const pkr_geom *g = &r->geom;
    const pkr_strip *s = &r->st[k];
    const int d = g->ratio, planes = g->planes, n_px = g->hires_px;
    const size_t top = (size_t)rc->top + s->pre, rows = (size_t)(rc->bottom - rc->top + 1), stored = rows + (size_t)2 * (size_t)d;
    if (top + stored > s->pre + s->lines) return PK_E_CORRUPT;
    pk_status st = PK_OK;
    uint16_t *stage = (uint16_t *)malloc((size_t)planes * stored * (size_t)n_px * 2);
    uint16_t *raw = (uint16_t *)malloc((size_t)CHUNK_LINES * r->words_per_line * 2);
    uint16_t *line = (uint16_t *)malloc((size_t)r->words_per_line * 2);
    if (!stage || !raw || !line) st = PK_E_NOMEM;
    if (st == PK_OK) {
        pkd_kernel_cfg kc = { n_px, planes, g->ratio, &r->tables, r->ir ? r->ir_xtalk : 0 };
        pkd_kernel_state ks;
        pkd_kernel_init(&ks);
        if (top > 0) memcpy(ks.mean4, s->mean4[top - 1], sizeof ks.mean4);     /* the kernel's only state is the previous corrected line's mean (recorded by pass 1) */
        for (size_t i = 0; i < stored && st == PK_OK;) {
            size_t n = stored - i < CHUNK_LINES ? stored - i : CHUNK_LINES;
            if ((st = pkr_read_lines(r, k, top + i, n, raw)) != PK_OK) break;
            for (size_t j = 0; j < n && st == PK_OK; j++, i++) {
                if ((st = pkd_kernel_line(&kc, &ks, raw + j * r->words_per_line, line)) != PK_OK) break;
                for (int c = 0; c < planes; c++) memcpy(stage + ((size_t)c * stored + i) * (size_t)n_px, line + (size_t)c * (size_t)n_px, (size_t)n_px * 2);
            }
        }
    }
    if (st == PK_OK) {
        const uint16_t *in[4];
        uint16_t *out[4];
        for (int c = 0; c < planes; c++) { in[c] = stage + (size_t)c * stored * (size_t)n_px; out[c] = buf + (size_t)c * rows * (size_t)n_px; }
        st = pkd_readout_planes(in, planes, stored, n_px, 0, n_px, d, 0, rows, out);
    }
    free(stage); free(raw); free(line);
    return st;
}

pk_status pk_roll_colour_input(const pk_roll *cr, int strip, pk_roll_input *out, pk_roll_input_storage **keep) {
    pk_roll *r = (pk_roll *)cr;
    if (keep) *keep = NULL;
    if (!r || !out || !keep || strip < 0 || strip >= r->n_strips) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    if (is_beta_family(r->model)) return PK_E_UNSUPPORTED;                  /* C39b: pk_roll_input has no field for the F-235 / F-335 Dmin constants */
    pk_status st = pkr_decode_strip(r, strip);
    if (st != PK_OK) return st;
    pk_dx_strip dx;
    if ((st = pkr_dx(r, strip, &dx)) != PK_OK) return st;
    pkr_strip *s = &r->st[strip];
    const pkr_geom *g = &r->geom;
    pk_roll_input_storage *k = (pk_roll_input_storage *)calloc(1, sizeof *k);
    if (!k) return PK_E_NOMEM;
    k->ir = r->ir;
    k->roll = r;
    k->strip_index = strip;
    out->product_code = dx.product;
    out->gen_code = dx.specifier;                                          /* -1 / -1 is PK_DX_NONE, 0 / 0 a real unassigned pair: both pass through */
    if (s->lines == 0) { *keep = k; return PK_OK; }                         /* no film: n_frames 0 and no calibration needed */
    const int n = s->fr ? s->fr->n : 0;
    k->n = n;
    const size_t rows = (size_t)s->strip->rows, w = (size_t)s->strip->width;
    k->strip = (uint16_t *)malloc(3 * (rows + 0) * w * 2 + 2);
    if (!k->strip) { pk_roll_input_storage_free(k); return PK_E_NOMEM; }
    for (int c = 0; c < 3; c++) memcpy(k->strip + c * rows * w, s->strip->plane[c], rows * w * 2);
    out->strip.width = (int)w;
    out->strip.height = (int)rows;
    for (int c = 0; c < 3; c++) out->strip.linear14[c] = k->strip + c * rows * w;
    memcpy(out->poly_neg, r->ee->poly_neg, sizeof out->poly_neg);
    if (n > 0) {
        k->frames = (pk_frame_linear *)calloc((size_t)n, sizeof *k->frames);
        k->lores = (pk_frame_linear *)calloc((size_t)n, sizeof *k->lores);
        k->hi = (uint16_t **)calloc((size_t)n, sizeof *k->hi);
        k->lo = (uint16_t **)calloc((size_t)n, sizeof *k->lo);
        k->h = (int *)calloc((size_t)n, sizeof *k->h);
        k->w = (int *)calloc((size_t)n, sizeof *k->w);
        if (!k->frames || !k->lores || !k->hi || !k->lo || !k->h || !k->w) { pk_roll_input_storage_free(k); return PK_E_NOMEM; }
    }
    for (int i = 0; i < n && st == PK_OK; i++) {
        const pk_frame_rect *rc = &s->fr->rects[i];
        if ((st = pkr_check_rect(g, s->lines, rc)) != PK_OK) break;
        const size_t fh = (size_t)(rc->bottom - rc->top + 1), fw = (size_t)g->hires_px;
        k->h[i] = (int)fh; k->w[i] = (int)fw;
        k->frames[i].width = (int)fw;                                      /* the hi-res planes are filled on demand (pk_roll_colour_frame); the sizes are known now */
        k->frames[i].height = (int)fh;
        const size_t lh = (size_t)(rc->lo_bottom - rc->lo_top + 1), lw = (size_t)g->lores_px;
        k->lo[i] = (uint16_t *)malloc(3 * lh * lw * 2);
        if (!k->lo[i]) { st = PK_E_NOMEM; break; }
        uint16_t *lp[3] = { k->lo[i], k->lo[i] + lh * lw, k->lo[i] + 2 * lh * lw };
        if ((st = pkd_strip_read_lores(s->strip, (size_t)rc->lo_top, lh, lp)) != PK_OK) break;
        for (int c = 0; c < 3; c++) pkr_rotate180(lp[c], lw, lh);          /* PSI's default AnselOrientation 0x10E: the AddScene frame is turned by 180 degrees */
        k->lores[i].width = (int)lw;
        k->lores[i].height = (int)lh;
        for (int c = 0; c < 3; c++) k->lores[i].linear14[c] = lp[c];
    }
    if (st != PK_OK) { pk_roll_input_storage_free(k); memset(out, 0, sizeof *out); return st; }
    out->n_frames = n;
    out->frames = k->frames;
    out->lores = k->lores;
    *keep = k;
    return PK_OK;
}

pk_status pk_roll_colour_frame(const pk_roll *cr, int strip, int k, pk_roll_input *in, pk_roll_input_storage *keep) {
    pk_roll *r = (pk_roll *)cr;
    if (!r || !in || !keep || strip < 0 || strip >= r->n_strips || k < 0 || k >= keep->n || in->frames != keep->frames) return PK_E_ARG;
    if (keep->roll != cr || keep->strip_index != strip) return PK_E_ARG;      /* storage from another roll or strip: its frame sizes are not this strip's */
    const pkr_strip *s = &r->st[strip];
    if (!s->fr || k >= s->fr->n) return PK_E_ARG;
    if (keep->hi[k]) return PK_OK;                                           /* already loaded */
    const pk_frame_rect *rc = &s->fr->rects[k];
    const size_t fh = (size_t)keep->h[k], fw = (size_t)keep->w[k];
    if (pkr_check_rect(&r->geom, s->lines, rc) != PK_OK || (size_t)(rc->bottom - rc->top + 1) != fh || (size_t)r->geom.hires_px != fw) return PK_E_ARG;   /* never crop beyond the buffer */
    uint16_t *buf = (uint16_t *)malloc((size_t)r->geom.planes * fh * fw * 2);
    if (!buf) return PK_E_NOMEM;
    pk_status st = hires_crop(r, strip, rc, buf);
    if (st != PK_OK) { free(buf); return st; }
    keep->hi[k] = buf;
    for (int c = 0; c < 3; c++) keep->frames[k].linear14[c] = buf + (size_t)c * fh * fw;
    keep->frames[k].linear14[PK_PLANE_IR] = keep->ir ? buf + (size_t)3 * fh * fw : NULL;          /* S-R45 b: the IR plane rides with the frame; the caller sets pk_roll_input.ice to use it */
    return PK_OK;
}

void pk_roll_colour_frame_release(pk_roll_input *in, pk_roll_input_storage *keep, int k) {
    if (!keep || k < 0 || k >= keep->n || !keep->hi[k]) return;
    free(keep->hi[k]);
    keep->hi[k] = NULL;
    for (int c = 0; c < 3; c++) keep->frames[k].linear14[c] = NULL;
    keep->frames[k].linear14[PK_PLANE_IR] = NULL;
    (void)in;
}
