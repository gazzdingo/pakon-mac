/* The public colour API (pakon/colour.h): TLB's front end and film base, PakonIMAu's roll analysis (analysis/roll.c),
 * and the render chain front -> NRA -> scene LUT -> falloff -> adjust -> KCMS -> u8. docs/re/24. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "pakon/colour.h"
#include "pakon/ice.h"
#include "internal.h"
#include "front.h"
#include "render.h"
#include "adjust.h"
#include "icc.h"
#include "export.h"
#include "analysis/roll.h"
#include "analysis/dmin.h"
#include "data/diag.h"

typedef char pk_dx_none_matches_pkc[(PK_DX_NONE == PKC_DX_NONE) ? 1 : -1];

#define PK_FILM_CLASS 1      /* PIAnselStartNewRoll class 1: colour negative (CN-Enhanced); RE 06 picks the rpd tables */

struct pk_colour {
    char vendor_root[1024], derived_root[1024];
    pkc_roll_cfg cfg;
    pkc_kct *kct_default;    /* rpd, saturation 0, no B&W: PSI's default output transform */
    int threads;             /* render worker threads (pk_colour_options.threads); fixed at open */
};

struct pk_roll_result {
    int n;
    pkc_roll_scene *scene;
    pkc_lut3 nra;            /* the film's NRA thresholds (its ISO's noise table), for pk_colour_render */
};

/* R6: name the file a failed load stopped on. The diag record lives on this call's stack and is bound to this thread only
 * for the duration of the call. */
static void fill_error(pk_load_error *err, const pkc_diag *d, pk_status st) {
    if (!err) return;
    err->path[0] = err->reason[0] = 0;
    const char *why;
    if (d->have && (st == PK_E_VENDOR_DATA || st == PK_E_FORMAT || st == PK_E_IO)) {
        snprintf(err->path, sizeof err->path, "%s", d->path);
        why = d->opened ? "content rejected" : "cannot be opened";
    } else why = st == PK_E_UNSUPPORTED ? "unsupported selection" : st == PK_E_NOMEM ? "out of memory" : "no file involved";
    snprintf(err->reason, sizeof err->reason, "%s", why);
}

pk_status pk_colour_open(const char *vendor_root, const char *derived_root, pk_colour **out) {
    return pk_colour_open_opts(vendor_root, derived_root, NULL, NULL, out);
}

static pk_status open_impl(const char *vendor_root, const char *derived_root, int threads, pk_colour **out);
pk_status pk_colour_open_ex(const char *vendor_root, const char *derived_root, pk_load_error *err, pk_colour **out) {
    return pk_colour_open_opts(vendor_root, derived_root, NULL, err, out);
}

pk_status pk_colour_open_opts(const char *vendor_root, const char *derived_root, const pk_colour_options *opt,
                              pk_load_error *err, pk_colour **out) {
    pkc_diag d;
    if (err) err->path[0] = err->reason[0] = 0;
    pkc_diag_bind(&d);
    pk_status st = opt && (opt->size < sizeof(size_t) + sizeof(int) || opt->size > sizeof *opt || opt->threads < 0)
                 ? (out ? (*out = NULL, PK_E_ARG) : PK_E_ARG)
                 : open_impl(vendor_root, derived_root, opt ? opt->threads : 0, out);
    pkc_diag_bind(NULL);
    if (st) fill_error(err, &d, st);
    return st;
}

static pk_status open_impl(const char *vendor_root, const char *derived_root, int threads, pk_colour **out) {
    if (!out) return PK_E_ARG;
    *out = NULL;
    if (!vendor_root || !derived_root) return PK_E_ARG;
    if (strlen(derived_root) >= sizeof ((pk_colour *)0)->derived_root || strlen(vendor_root) >= sizeof ((pk_colour *)0)->vendor_root)
        return PK_E_ARG;
    pk_colour *c = calloc(1, sizeof *c);
    if (!c) return PK_E_NOMEM;
    c->threads = threads;
    strcpy(c->derived_root, derived_root);
    strcpy(c->vendor_root, vendor_root);
    pk_status st = pkc_roll_cfg_load(vendor_root, derived_root, 0, 0, &c->cfg);
    if (st) { free(c); return st; }
    if ((st = pkc_icc_select(derived_root, PK_FILM_CLASS, 0, 0, &c->kct_default))) { pkc_roll_cfg_free(&c->cfg); free(c); return st; }
    *out = c;
    return PK_OK;
}

void pk_colour_close(pk_colour *c) {
    if (!c) return;
    pkc_kct_free(c->kct_default);
    pkc_roll_cfg_free(&c->cfg);
    free(c);
}

static int frame_ok(const pk_frame_linear *f) {
    return f && f->width >= 1 && f->height >= 1 && f->linear14[0] && f->linear14[1] && f->linear14[2];
}

/* TLB's LUT + 3x10 polynomial on a linear image -> 12-bit planes (malloc'd, one block) */
static pk_status front_planes(const float k[3][10], const pk_frame_linear *f, int16_t *p[3]) {
    size_t n = (size_t)f->width * f->height;
    int16_t *b = malloc(3 * n * sizeof *b);
    if (!b) return PK_E_NOMEM;
    for (int c = 0; c < 3; c++) p[c] = b + c * n;
    const uint16_t *lin[3] = { f->linear14[0], f->linear14[1], f->linear14[2] };
    pkc_front(k, lin, p, n);
    return PK_OK;
}

/* ---- Digital ICE on the save (S-R45 b / c, RE 45 sec 4) ---- */

/* The sizes Kodak's DMLDICEProcess crashes on (RE 44 sec 4.1), which pk_ice_apply refuses with PK_E_ARG: width <= 3, height < 8, and height < 32 when the image has
 * 1,000,000 pixels or more (the statistics step is then 4). TLB has no guard of its own, so there is no Kodak result for them (RE 45 sec 4.2). */
static int ice_size_ok(int w, int h) {
    if (w <= 3 || h < 8) return 0;
    return !((int64_t)w * h >= 1000000 && h < 32);
}

/* The ICE step shared by the renders and pk_colour_export_linear16 (RE 45 sec 4): when in->ice is set and the frame has an IR plane, ICE on a scratch copy of the crop's planes.
 * *scratch is then the malloc'd block (3 colour planes in iced->linear14[0..2]; the caller frees it); NULL when ICE does not apply (nothing allocated, *iced untouched). */
pk_status pkc_ice_crop(const pk_roll_input *in, const pk_frame_linear *f, pk_frame_linear *iced, uint16_t **scratch) {
    *scratch = NULL;
    if (!in->ice || !f->linear14[PK_PLANE_IR]) return PK_OK;
    if (!ice_size_ok(f->width, f->height)) return PK_E_ARG;
    size_t n = (size_t)f->width * f->height;
    uint16_t *sc = malloc(4 * n * sizeof *sc);
    if (!sc) return PK_E_NOMEM;
    for (int ch = 0; ch < 3; ch++) memcpy(sc + ch * n, f->linear14[ch], n * sizeof *sc);
    memcpy(sc + 3 * n, f->linear14[PK_PLANE_IR], n * sizeof *sc);
    pk_status si = pk_ice_apply(sc, sc + n, sc + 2 * n, sc + 3 * n, f->width, f->height, (size_t)f->width, NULL, NULL);
    if (si) { free(sc); return si; }
    iced->width = f->width; iced->height = f->height; iced->linear14[PK_PLANE_IR] = NULL;
    for (int ch = 0; ch < 3; ch++) iced->linear14[ch] = sc + ch * n;
    *scratch = sc;
    return PK_OK;
}

pk_status pk_colour_ice_check(const pk_roll_input *in, int frame, char *msg, size_t cap) {
    if (msg && cap) msg[0] = 0;
    if (!in || !in->frames || frame < 0 || frame >= in->n_frames) return PK_E_ARG;
    const pk_frame_linear *f = &in->frames[frame];
    if (!in->ice || !f->linear14[PK_PLANE_IR] || ice_size_ok(f->width, f->height)) return PK_OK;
    if (msg && cap)
        snprintf(msg, cap, "Digital ICE cannot run on a %d x %d frame (the library needs a width of at least 4 and a height of at least 8, or 32 from 1,000,000 pixels); "
                           "the frame is not saved without ICE", f->width, f->height);
    return PK_E_ARG;
}

static pk_status analyse_impl(const pk_colour *c, const pk_roll_input *in, pk_roll_result **out);
pk_status pk_colour_analyse_roll(const pk_colour *c, const pk_roll_input *in, pk_roll_result **out) {
    return pk_colour_analyse_roll_ex(c, in, NULL, out);
}
pk_status pk_colour_analyse_roll_ex(const pk_colour *c, const pk_roll_input *in, pk_load_error *err, pk_roll_result **out) {
    pkc_diag d;
    if (err) err->path[0] = err->reason[0] = 0;
    pkc_diag_bind(&d);
    pk_status st = analyse_impl(c, in, out);
    pkc_diag_bind(NULL);
    if (st) fill_error(err, &d, st);
    return st;
}

static pk_status analyse_impl(const pk_colour *c, const pk_roll_input *in, pk_roll_result **out) {
    if (!out) return PK_E_ARG;
    *out = NULL;
    if (!c || !in || in->n_frames < 1 || !in->lores || !frame_ok(&in->strip)) return PK_E_ARG;
    for (int k = 0; k < in->n_frames; k++) if (!frame_ok(&in->lores[k])) return PK_E_ARG;
    /* a film with DX codes: Kodak's selections for it (sba.map row, ISO noise table, FUGC lookups), read per call so the
     * handle stays immutable; 0 / 0 is the handle's own */
    pkc_roll_cfg *own = NULL;
    const pkc_roll_cfg *cfg = &c->cfg;
    if (in->product_code != 0 || in->gen_code != 0) {
        if (!(own = malloc(sizeof *own))) return PK_E_NOMEM;
        pk_status sc = pkc_roll_cfg_load(c->vendor_root, c->derived_root, in->product_code, in->gen_code, own);
        if (sc) { free(own); return sc; }
        cfg = own;
    }

    /* the film base: TLB's finder on the stored strip (RE 20), then the 4x1 image [R,0,0,0 | G.. | B..] through the LUT
     * and the polynomial (RE 04 Q4.1): only pixel 0 is read back */
    uint16_t fb14[3], dmin[3];
    const uint16_t *sp[3] = { in->strip.linear14[0], in->strip.linear14[1], in->strip.linear14[2] };
    pk_status st = pkc_film_base(sp, in->strip.width, in->strip.height, PKC_DMIN_DPI_BASE, fb14);
    if (st) { if (own) { pkc_roll_cfg_free(own); free(own); } return st; }
    {
        const uint16_t *lin[3] = { &fb14[0], &fb14[1], &fb14[2] };
        int16_t o[3], *op[3] = { &o[0], &o[1], &o[2] };
        pkc_front(in->poly_neg, lin, op, 1);
        for (int ch = 0; ch < 3; ch++) dmin[ch] = (uint16_t)o[ch];
    }
    int n = in->n_frames;
    pk_roll_result *r = calloc(1, sizeof *r);
    pkc_roll_frame *fr = calloc((size_t)n, sizeof *fr);
    int16_t **blk = calloc((size_t)n, sizeof *blk);
    if (r) r->scene = malloc((size_t)n * sizeof *r->scene);
    st = PK_E_NOMEM;
    if (!r || !fr || !blk || !r->scene) goto done;
    for (int k = 0; k < n; k++) {
        int16_t *p[3];
        if ((st = front_planes(in->poly_neg, &in->lores[k], p))) goto done;
        blk[k] = p[0];
        fr[k].w = in->lores[k].width; fr[k].h = in->lores[k].height;
        for (int ch = 0; ch < 3; ch++) fr[k].p[ch] = (const uint16_t *)p[ch];   /* 0..4095 after the polynomial */
    }
    r->n = n;
    r->nra = cfg->nra;
    st = pkc_roll_batches(cfg, n, fr, dmin, r->scene);
done:
    if (blk) for (int k = 0; k < n; k++) free(blk[k]);
    free(blk); free(fr);
    if (own) { pkc_roll_cfg_free(own); free(own); }
    if (st) { pk_roll_result_free(r); return st; }
    *out = r;
    return PK_OK;
}

void pk_roll_result_free(pk_roll_result *r) {
    if (!r) return;
    free(r->scene);
    free(r);
}

pk_status pk_roll_result_frames(const pk_roll_result *r, int *n) {
    if (!r || !n) return PK_E_ARG;
    *n = r->n;
    return PK_OK;
}

pk_status pk_roll_result_status(const pk_roll_result *r, int frame) {
    if (!r || frame < 0 || frame >= r->n) return PK_E_ARG;
    if (r->scene[frame].status) return r->scene[frame].status;
    return r->scene[frame].failed ? PK_E_ANALYSIS : PK_OK;
}

pk_status pk_roll_result_skipped(const pk_roll_result *r, int frame, int *skipped) {
    if (!r || !skipped || frame < 0 || frame >= r->n) return PK_E_ARG;
    *skipped = r->scene[frame].skipped ? 1 : 0;
    return PK_OK;
}

pk_status pk_roll_result_exact(const pk_roll_result *r, int frame, int *exact) {
    if (!r || !exact || frame < 0 || frame >= r->n) return PK_E_ARG;
    *exact = (r->scene[frame].inexact || r->scene[frame].status) ? 0 : 1;
    return PK_OK;
}

pk_status pk_roll_result_falloff(const pk_roll_result *r, int frame, int *on) {
    if (!r || !on || frame < 0 || frame >= r->n) return PK_E_ARG;
    *on = r->scene[frame].falloff;
    return PK_OK;
}

/* test seam (export.h): force the lens-falloff decision of a frame */
pk_status pkc_roll_result_force_falloff(pk_roll_result *r, int frame, int on) {
    if (!r || frame < 0 || frame >= r->n) return PK_E_ARG;
    r->scene[frame].falloff = on != 0;
    return PK_OK;
}

pk_status pk_roll_result_exposure(const pk_roll_result *r, int frame, double *stops) {
    if (!r || !stops || frame < 0 || frame >= r->n) return PK_E_ARG;
    *stops = r->scene[frame].exposure;
    return PK_OK;
}

/* PIScaleAndRotatePlanar at scale 1 (TLB's save path: FUN_10026c90 -> FUN_10023560, docs/re/02): a pixel rotation, no
 * resampling (Kodak-pinned: Task 21 truth, every angle and interpolation mode equals an index permutation). 90 turns the
 * image clockwise, 270 counter-clockwise. */
static pk_status rotate_planes(pkc_planes *img, int rotation) {
    if (rotation == 0) return PK_OK;
    const int W = img->w, H = img->h, ow = rotation == 180 ? W : H, oh = rotation == 180 ? H : W;
    const size_t n = (size_t)W * H;
    int16_t *b = malloc(3 * n * sizeof *b);
    if (!b) return PK_E_NOMEM;
    for (int c = 0; c < 3; c++) {
        const int16_t *src = img->p[c];
        int16_t *dst = b + (size_t)c * n;
        for (int y = 0; y < oh; y++)
            for (int x = 0; x < ow; x++) {
                int sx, sy;
                if (rotation == 90) { sx = y; sy = H - 1 - x; }
                else if (rotation == 180) { sx = W - 1 - x; sy = H - 1 - y; }
                else { sx = W - 1 - y; sy = x; }
                dst[(size_t)y * ow + x] = src[(size_t)sy * W + sx];
            }
    }
    free(img->p[0]);
    img->w = ow; img->h = oh;
    for (int c = 0; c < 3; c++) img->p[c] = b + (size_t)c * n;
    return PK_OK;
}

/* The frame's validation and its render chain up to the KCMS input (shared by pk_colour_render and the 16-bit RPD
 * export): TLB's LUT + polynomial, NRA, the scene LUT, falloff, the save rotation, then PSI's adjustments (a NULL =
 * none). *bal gets 3 planes in one malloc'd block (free bal->p[0]); the scene is the failed-batch scene for a
 * PK_E_ANALYSIS frame. */
static pk_status balanced_pre(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                              const pk_adjust *adj, int pre, int rotation, int ow, int oh, pkc_planes *bal);
pk_status pkc_colour_balanced(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                              const pk_adjust *adj, int rotation, pkc_planes *bal) {
    return balanced_pre(c, in, r, frame, adj, 0, rotation, 0, 0, bal);
}

/* pre: the rotation PIRotatePlanar applies to the stored frame BEFORE the scene balance (TLB FUN_10026c90 step 5.1,
 * 0x10E - AnselOrientation: 0 or 270 here); rotation: the one PIScaleAndRotatePlanar applies after it. The front end
 * (LUT + polynomial) is per pixel, so rotating its output is the same as rotating its input.
 * ow x oh (both > 0): PIScaleAndRotatePlanar's output size (the FINAL, rotated size; 0 x 0 = no scaling): the balanced image is
 * resampled to it before the rotation, to (ow, oh) for 0 / 180 and to (oh, ow) for 90 / 270 (RE 39 section 3). */
static pk_status balanced_pre(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                              const pk_adjust *adj, int pre, int rotation, int ow, int oh, pkc_planes *bal) {
    static const pk_adjust none = { 0, 0, 0, 0, 0, 0, 0, 0 };
    if (!c || !in || !r || !bal || !in->frames || frame < 0 || frame >= r->n || r->n != in->n_frames) return PK_E_ARG;
    if (rotation != 0 && rotation != 90 && rotation != 180 && rotation != 270) return PK_E_ARG;
    if (pre != 0 && pre != 270) return PK_E_ARG;
    const pk_frame_linear *f = &in->frames[frame];
    if (!frame_ok(f)) return PK_E_ARG;
    const pk_adjust *a = adj ? adj : &none;
    if (a->saturation < -5 || a->saturation > 5 || a->bnw < 0 || a->bnw > 3) return PK_E_ARG;
    const pkc_roll_scene *s = &r->scene[frame];
    if (s->status) return s->status;                 /* the port refused this frame's batch (RE 27) */
    size_t n = (size_t)f->width * f->height;
    pkc_planes rpd = { f->width, f->height, { NULL, NULL, NULL } };
    /* Digital ICE (TLB FUN_10026c90 step 7): on the frame as stored, linear, before the LUT and the polynomial (step 8-9), on a scratch copy because the input is const.
     * The gate is the save bit AND an IR plane; a frame ICE cannot run on fails here, never silently saved without it. */
    pk_frame_linear iced;
    const pk_frame_linear *src = f;
    uint16_t *scratch = NULL;
    pk_status sice = pkc_ice_crop(in, f, &iced, &scratch);
    if (sice) return sice;
    if (scratch) src = &iced;
    pk_status st = front_planes(in->poly_neg, src, rpd.p);
    free(scratch);
    if (st) return st;
    if (pre && (st = rotate_planes(&rpd, pre))) { free(rpd.p[0]); return st; }
    int16_t *ob = malloc(3 * n * sizeof *ob);
    if (!ob) { free(rpd.p[0]); return PK_E_NOMEM; }
    pkc_planes out = { rpd.w, rpd.h, { ob, ob + n, ob + 2 * n } };
    if (s->skipped) {                                /* Kodak builds no transform for it: the frame passes untouched (RE 27) */
        memcpy(ob, rpd.p[0], 3 * n * sizeof *ob);
        st = PK_OK;
    } else
        st = pkc_render_scene_t(&rpd, &s->lut_s, s->falloff, &r->nra, &c->cfg.falloff, &out, c->threads);
    free(rpd.p[0]);
    if (!st && ow > 0 && oh > 0) {
        const int quarter = rotation == 90 || rotation == 270;
        st = pkc_resample_bicubic(&out, quarter ? oh : ow, quarter ? ow : oh);
    }
    if (!st) st = rotate_planes(&out, rotation);
    if (!st) st = pkc_adjust_apply(&out, a);
    if (st) { free(out.p[0]); return st; }
    *bal = out;
    return PK_OK;
}

pk_status pk_colour_render(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                           const pk_adjust *adj, pk_image_u8 *out) {
    return pk_colour_render_rotated(c, in, r, frame, adj, 0, out);
}

/* out (8-bit, Kodak's own store) or out16 (the 16-bit Kodak output, docs/re/50): exactly one is non-NULL. */
static pk_status render_geom(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                             const pk_adjust *adj, int pre, int rotation, int sw, int sh, pk_image_u8 *out, pk_image_u16 *out16) {
    if (out16 ? !out16->rgb : (!out || !out->rgb)) return PK_E_ARG;
    pkc_planes bal;
    pk_status st = balanced_pre(c, in, r, frame, adj, pre, rotation, sw, sh, &bal);
    if (st) return st;
    static const pk_adjust none = { 0, 0, 0, 0, 0, 0, 0, 0 };
    const pk_adjust *a = adj ? adj : &none;
    size_t n = (size_t)bal.w * bal.h;
    uint8_t *u8 = NULL;
    uint16_t *u16 = NULL;
    pkc_kct *kct = NULL;
    st = PK_E_NOMEM;
    if (out16) { u16 = malloc(3 * n * sizeof *u16); if (!u16) goto done; }
    else { u8 = malloc(3 * n); if (!u8) goto done; }
    const pkc_kct *k = c->kct_default;
    if (a->saturation != 0 || a->bnw != 0) {
        if ((st = pkc_icc_select(c->derived_root, PK_FILM_CLASS, a->saturation, a->bnw, &kct))) goto done;
        k = kct;
    }
    /* Kodak's SpEvaluate calls are per Ima tile; the sharpening op shifts the tiles (pkc_icc_eval_frame) */
    if (out16) {
        uint16_t *op[3] = { u16, u16 + n, u16 + 2 * n };
        if ((st = pkc_icc_eval_frame16(k, (const int16_t **)bal.p, op, bal.w, bal.h, a->sharpness != 0))) goto done;
        pkc_interleave_u16(u16, n, out16->rgb);
        out16->width = bal.w; out16->height = bal.h;
    } else {
        uint8_t *op[3] = { u8, u8 + n, u8 + 2 * n };
        if ((st = pkc_icc_eval_frame(k, (const int16_t **)bal.p, op, bal.w, bal.h, a->sharpness != 0))) goto done;
        pkc_interleave_u8(u8, n, out->rgb);
        out->width = bal.w; out->height = bal.h;
    }
    st = PK_OK;
done:
    pkc_kct_free(kct);
    free(bal.p[0]); free(u8); free(u16);
    return st;
}

pk_status pk_colour_render_rotated(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                   const pk_adjust *adj, int rotation, pk_image_u8 *out) {
    return render_geom(c, in, r, frame, adj, 0, rotation, 0, 0, out, NULL);
}

pk_status pk_colour_render_saved(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                 const pk_adjust *adj, int ansel_orientation, int picture_rotation, pk_image_u8 *out) {
    static const int BASE[4] = { 630, 540, 450, 360 };
    if (ansel_orientation != 0 && ansel_orientation != PK_ANSEL_ORIENTATION_PSI) return PK_E_ARG;
    if (picture_rotation < 0 || picture_rotation > 3) return PK_E_ARG;
    const int pre = PK_ANSEL_ORIENTATION_PSI - ansel_orientation;                   /* 0x10E - AnselOrientation */
    return render_geom(c, in, r, frame, adj, pre, (BASE[picture_rotation] - pre) % 360, 0, 0, out, NULL);
}

/* TLB's save-size planner, FUN_100267a0 (RE 39 section 2), for the hi-res frame. The planner works on the picture's rectangle,
 * which is the transpose of the working image (FUN_10026c90 allocates the image as the rectangle's height x width), so the
 * rectangle is (frame height) x (frame width); its output is the size of the saved picture, in the saved orientation. All
 * integer arithmetic truncates (C division, as the 32-bit code). */
static int plan_size(int fw, int fh, int rot, const pk_save_size *sz, int *ow, int *oh) {
    const int rw = fh, rh = fw;                                       /* the rectangle */
    const int sw = (rot & 1) ? rh : rw, sh = (rot & 1) ? rw : rh;      /* the picture in its saved orientation */
    *ow = sw; *oh = sh;
    if (!sz || sz->fit == 0) return 1;
    int bw = sz->bound_w, bh = sz->bound_h;
    double d1 = (double)bw / (double)bh;
    const double d2 = (double)sw / (double)sh;
    if (sz->fit == 2 && ((d1 < 1.0) != (d2 < 1.0))) { const int t = bw; bw = bh; bh = t; d1 = 1.0 / d1; }
    if (d2 > d1) {                                                    /* fit the width */
        if (sw == bw || (sz->no_upscale && sw < bw)) return 1;
        if ((int64_t)sh * bw > INT32_MAX) return 0;                   /* Kodak's product would wrap */
        *ow = bw; *oh = (int)(((int64_t)sh * bw) / sw);
    } else {                                                          /* fit the height */
        if (sh == bh || (sz->no_upscale && sh < bh)) return 1;
        if ((int64_t)sw * bh > INT32_MAX) return 0;
        *oh = bh; *ow = (int)(((int64_t)sw * bh) / sh);
    }
    return 1;
}

static pk_status saved_size(const pk_roll_input *in, int frame, int picture_rotation, const pk_save_size *sz, int *w, int *h) {
    if (!in || !in->frames || !w || !h || frame < 0 || frame >= in->n_frames) return PK_E_ARG;
    if (picture_rotation < 0 || picture_rotation > 3) return PK_E_ARG;
    const pk_frame_linear *f = &in->frames[frame];
    if (!f || f->width < 1 || f->height < 1) return PK_E_ARG;          /* the size alone: no planes needed (Task 20 fix round 3, n4); the renders check their planes themselves */
    if (sz) {
        if (sz->fit < 0 || sz->fit > 2 || sz->no_upscale < 0 || sz->no_upscale > 1) return PK_E_ARG;
        if (sz->fit != 0 && (sz->bound_w < 17 || sz->bound_h < 17 || sz->bound_w > 65535 || sz->bound_h > 65535)) return PK_E_ARG;
    }
    if (!plan_size(f->width, f->height, picture_rotation, sz, w, h)) return PK_E_ARG;
    return *w < 1 || *h < 1 ? PK_E_ARG : PK_OK;                        /* a degenerate aspect ratio can round a side to 0 */
}

pk_status pk_colour_saved_size(const pk_roll_input *in, int frame, int picture_rotation, const pk_save_size *size,
                               int *width, int *height) {
    return saved_size(in, frame, picture_rotation, size, width, height);
}

pk_status pk_colour_render_saved_scaled(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                        const pk_adjust *adj, int ansel_orientation, int picture_rotation,
                                        const pk_save_size *size, pk_image_u8 *out) {
    static const int BASE[4] = { 630, 540, 450, 360 };
    if (ansel_orientation != 0 && ansel_orientation != PK_ANSEL_ORIENTATION_PSI) return PK_E_ARG;
    int ow, oh;
    pk_status st = saved_size(in, frame, picture_rotation, size, &ow, &oh);
    if (st) return st;
    const int pre = PK_ANSEL_ORIENTATION_PSI - ansel_orientation;
    const int fit = size && size->fit != 0;
    return render_geom(c, in, r, frame, adj, pre, (BASE[picture_rotation] - pre) % 360, fit ? ow : 0, fit ? oh : 0, out, NULL);
}

pk_status pk_colour_render_saved_scaled16(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                          const pk_adjust *adj, int ansel_orientation, int picture_rotation,
                                          const pk_save_size *size, pk_image_u16 *out) {
    static const int BASE[4] = { 630, 540, 450, 360 };
    if (!out || (ansel_orientation != 0 && ansel_orientation != PK_ANSEL_ORIENTATION_PSI)) return PK_E_ARG;
    int ow, oh;
    pk_status st = saved_size(in, frame, picture_rotation, size, &ow, &oh);
    if (st) return st;
    const int pre = PK_ANSEL_ORIENTATION_PSI - ansel_orientation;
    const int fit = size && size->fit != 0;
    return render_geom(c, in, r, frame, adj, pre, (BASE[picture_rotation] - pre) % 360, fit ? ow : 0, fit ? oh : 0, NULL, out);
}
