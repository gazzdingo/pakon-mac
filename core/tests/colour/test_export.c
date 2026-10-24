/* Task 20: exports -- the u8 interleave of pk_colour_render and the 16-bit RPD / linear exports for DNG. */
#include "greatest.h"
#include "pkv.h"
#include "synframe.h"
#include "pakon/colour.h"
#include "export.h"
#include "front.h"
#include "render.h"
#include "nra.h"
#include "icc.h"
#include "analysis/roll.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

TEST interleave_u8(void) {
    const uint8_t pl[12] = { 1, 2, 3, 4,   10, 20, 30, 40,   100, 110, 120, 130 };   /* 2 x 2 planar */
    uint8_t o[12];
    pkc_interleave_u8(pl, 4, o);
    const uint8_t want[12] = { 1, 10, 100,  2, 20, 110,  3, 30, 120,  4, 40, 130 };
    ASSERT_MEM_EQ(want, o, 12);
    PASS();
}

TEST rpd_scaling(void) {
    int16_t r[4] = { 0, 1, 4095, 2048 }, g[4] = { 255, 256, 4094, -7 }, b[4] = { 4096, 17, 3, 9999 };
    const int16_t *p[3] = { r, g, b };
    uint16_t o[12];
    pkc_rpd12_to_u16(p, 4, o);
    ASSERT_EQ(0, o[0]); ASSERT_EQ(16, o[3]); ASSERT_EQ(65535, o[6]); ASSERT_EQ(2048 * 16 + 8, o[9]);
    ASSERT_EQ(255 * 16, o[1]); ASSERT_EQ(256 * 16 + 1, o[4]); ASSERT_EQ(4094 * 16 + 15, o[7]);
    ASSERT_EQ(0, o[10]);                       /* clamped below */
    ASSERT_EQ(65535, o[2]); ASSERT_EQ(65535, o[11]);   /* clamped above */
    /* exact end points and monotonic over all 4096 codes */
    int prev = -1;
    for (int v = 0; v < 4096; v++) {
        int16_t a = (int16_t)v; const int16_t *q[3] = { &a, &a, &a }; uint16_t w[3];
        pkc_rpd12_to_u16(q, 1, w);
        ASSERT_EQ(v * 16 + v / 256, w[0]); ASSERT(w[0] > prev); prev = w[0];
    }
    PASS();
}

TEST linear_scaling(void) {
    uint16_t r[3] = { 0, 16383, 1 }, g[3] = { 16383, 8000, 2 }, b[3] = { 16384, 65535, 3 };
    const uint16_t *p[3] = { r, g, b };
    uint16_t o[9];
    pkc_linear14_to_u16(p, 3, o);
    ASSERT_EQ(0, o[0]); ASSERT_EQ(65532, o[3]); ASSERT_EQ(4, o[6]);
    ASSERT_EQ(65532, o[1]); ASSERT_EQ(32000, o[4]); ASSERT_EQ(8, o[7]);
    ASSERT_EQ(65532, o[2]); ASSERT_EQ(65532, o[5]); ASSERT_EQ(12, o[8]);   /* above 16383 = 16383, as TLB's LUT */
    PASS();
}

/* r4 frame 1 of the existing render vectors (render.pkv scene 1: Kodak's 12-bit RPD in, its scene LUT, its balanced out):
 * the export's scaling of the stages' planar pre-ICC buffer, and of Kodak's own output */
TEST rpd_real_frame(void) {
    pkc_lut3 thr; pkc_falloff_params fp;
    ASSERT_EQ(PK_OK, pkc_nra_prepare(VENDOR_ROOT, &thr));
    ASSERT_EQ(PK_OK, pkc_falloff_params_load(VENDOR_ROOT, &fp));
    pkv_file *f = pkv_open(PKV_DIR "/render.pkv"); ASSERT(f);
    const pkv_array *LUT = pkv_get(f, "s1_lut"), *FO = pkv_get(f, "s1_fo"), *I = pkv_get(f, "s1_in"), *O = pkv_get(f, "s1_out");
    ASSERT(LUT && FO && I && O);
    int h = I->dims[1], w = I->dims[2]; size_t n = (size_t)w * h;
    pkc_lut3 *lut = malloc(sizeof *lut); ASSERT(lut); memcpy(lut, LUT->data, sizeof *lut);
    int16_t *bal = malloc(3 * n * sizeof *bal); uint16_t *got = malloc(3 * n * sizeof *got), *want = malloc(3 * n * sizeof *want);
    ASSERT(bal && got && want);
    pkc_planes in = { w, h, { (int16_t *)I->data, (int16_t *)I->data + n, (int16_t *)I->data + 2 * n } };
    pkc_planes out = { w, h, { bal, bal + n, bal + 2 * n } };
    ASSERT_EQ(PK_OK, pkc_render_scene(&in, lut, ((const int32_t *)FO->data)[0], &thr, &fp, &out));
    pkc_rpd12_to_u16((const int16_t *const *)out.p, n, got);
    for (size_t i = 0; i < n; i++) for (int c = 0; c < 3; c++) {
        int v = ((const int16_t *)O->data)[c * n + i];
        want[3 * i + c] = (uint16_t)(v * 16 + v / 256);
    }
    int same = !memcmp(got, want, 3 * n * sizeof *got);
    free(lut); free(bal); free(got); free(want); pkv_close(f);
    ASSERT(same);
    PASS();
}

/* ---- the public exports against the stages called directly ---- */
static float K[3][10];
static int need_k(void) {
    pkv_file *f = pkv_open(PKV_DIR "/front.pkv");
    const pkv_array *a = f ? pkv_get(f, "k") : NULL;
    int ok = a && a->n == 30;
    if (ok) memcpy(K, a->data, sizeof K);
    pkv_close(f);
    return ok;
}
static uint32_t xs(uint32_t *s) { uint32_t x = *s; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *s = x; }
static uint16_t *lin_frame(int w, int h, uint32_t seed, int base) {
    uint16_t *p = malloc((size_t)3 * w * h * sizeof *p);
    if (!p) return NULL;
    for (int c = 0; c < 3; c++) for (int y = 0; y < h; y++) for (int x = 0; x < w; x++)
        p[((size_t)c * h + y) * w + x] = (uint16_t)(base + 900 * c + 6 * x + 9 * y + (int)(xs(&seed) % 400));
    return p;
}
typedef struct { pk_roll_input in; pk_frame_linear *fr, *lo; uint16_t **buf; int nb; } api_roll;
static void api_free(api_roll *r) {
    if (r->buf) for (int i = 0; i < r->nb; i++) free(r->buf[i]);
    free(r->buf); free(r->fr); free(r->lo);
    memset(r, 0, sizeof *r);
}
static int api_make(api_roll *r, int n, int w, int h) {
    memset(r, 0, sizeof *r);
    r->fr = calloc((size_t)n, sizeof *r->fr); r->lo = calloc((size_t)n, sizeof *r->lo);
    r->buf = calloc((size_t)(2 * n + 1), sizeof *r->buf);
    if (!r->fr || !r->lo || !r->buf) return -1;
    for (int k = 0; k < n; k++) {
        uint16_t *hi = lin_frame(w, h, 7 + k, 2000 + 300 * (k % 5)), *lo = lin_frame(250, 375, 101 + k, 2000 + 300 * (k % 5));
        r->buf[r->nb++] = hi; r->buf[r->nb++] = lo;
        if (!hi || !lo) return -1;
        r->fr[k] = (pk_frame_linear){ w, h, { hi, hi + (size_t)w * h, hi + (size_t)2 * w * h } };
        r->lo[k] = (pk_frame_linear){ 250, 375, { lo, lo + 250 * 375, lo + 2 * 250 * 375 } };
    }
    uint16_t *st = lin_frame(250, 700, 999, 6000);
    r->buf[r->nb++] = st;
    if (!st) return -1;
    r->in.n_frames = n; r->in.frames = r->fr; r->in.lores = r->lo;
    r->in.strip = (pk_frame_linear){ 250, 700, { st, st + 250 * 700, st + 2 * 250 * 700 } };
    memcpy(r->in.poly_neg, K, sizeof K);
    return 0;
}

TEST api_exports(void) {
    pk_colour *c = NULL; pk_roll_result *res = NULL; api_roll r;
    const int n = 4, W = 64, H = 48; size_t np = (size_t)W * H;
    ASSERT(need_k());
    ASSERT_EQ(PK_OK, pk_colour_open(VENDOR_ROOT, DERIVED_ROOT, &c));
    ASSERT_EQ(0, api_make(&r, n, W, H));
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &r.in, &res));
    uint16_t *a = malloc(np * 3 * 2), *b = malloc(np * 3 * 2); uint8_t *u = malloc(np * 3);
    
    ASSERT(a && b && u);
    for (int k = 0; k < n; k++) {
        /* linear16: the samples times 4, interleaved */
        pk_image_u16 im = { 0, 0, a };
        ASSERT_EQ(PK_OK, pk_colour_export_linear16(&r.in, k, &im));
        ASSERT_EQ(W, im.width); ASSERT_EQ(H, im.height);
        for (size_t i = 0; i < np; i++) for (int ch = 0; ch < 3; ch++) ASSERT_EQ(4u * r.fr[k].linear14[ch][i], a[3 * i + ch]);
        /* rpd16: front -> NRA -> scene LUT -> falloff by hand, using the scene LUT the analysis gives (through the
         * stages), scaled. The scene LUT is not public: compare against the u8 render's own pre-ICC buffer instead --
         * recompute it via pkc_colour_balanced's definition (stages) with the roll's cfg. */
        ASSERT_EQ(PK_OK, pk_colour_export_rpd16(c, &r.in, res, k, &im));
        ASSERT_EQ(W, im.width); ASSERT_EQ(H, im.height);
        pkc_planes pb;
        ASSERT_EQ(PK_OK, pkc_colour_balanced(c, &r.in, res, k, NULL, 0, &pb));
        pkc_rpd12_to_u16((const int16_t *const *)pb.p, np, b);
        free(pb.p[0]);
        ASSERT_MEM_EQ(b, a, np * 3 * 2);
        /* the render's u8 is the ICC of exactly that buffer, interleaved */
        pk_image_u8 iu = { 0, 0, u };
        ASSERT_EQ(PK_OK, pk_colour_render(c, &r.in, res, k, NULL, &iu));
        ASSERT_EQ(W, iu.width);
    }
    /* the render with default adjustments reaches the same buffer: sample-by-sample the u8 follows the rpd16 order */
    {
        pkc_planes pb; ASSERT_EQ(PK_OK, pkc_colour_balanced(c, &r.in, res, 2, NULL, 0, &pb));
        pkc_kct *kct = NULL; ASSERT_EQ(PK_OK, pkc_icc_select(DERIVED_ROOT, 1, 0, 0, &kct));
        uint8_t *pl = malloc(np * 3); ASSERT(pl);
        uint8_t *o3[3] = { pl, pl + np, pl + 2 * np };
        ASSERT_EQ(PK_OK, pkc_icc_eval_frame(kct, (const int16_t **)pb.p, o3, pb.w, pb.h, 0));
        uint8_t *want = malloc(np * 3); ASSERT(want);
        pkc_interleave_u8(pl, np, want);
        pk_image_u8 iu = { 0, 0, u };
        ASSERT_EQ(PK_OK, pk_colour_render(c, &r.in, res, 2, NULL, &iu));
        int same = !memcmp(want, u, np * 3);
        pkc_kct_free(kct); free(pb.p[0]); free(pl); free(want);
        ASSERT(same);
    }
    /* adjustments are not part of the rpd16 export: a render with them changes u8 but not the export */
    {
        pk_image_u16 im = { 0, 0, a }, im2 = { 0, 0, b };
        uint8_t *u2 = malloc(np * 3); ASSERT(u2);
        pk_adjust adj = { 0, 0, 0, 0, 0, 0, 0, 0 };
        adj.brightness = 300; adj.contrast = 200;
        pk_image_u8 iu = { 0, 0, u }, iu2 = { 0, 0, u2 };
        ASSERT_EQ(PK_OK, pk_colour_export_rpd16(c, &r.in, res, 1, &im));
        ASSERT_EQ(PK_OK, pk_colour_render(c, &r.in, res, 1, NULL, &iu));
        ASSERT_EQ(PK_OK, pk_colour_render(c, &r.in, res, 1, &adj, &iu2));
        ASSERT(memcmp(u, u2, np * 3) != 0);                       /* the adjustments do change the render ... */
        ASSERT_EQ(PK_OK, pk_colour_export_rpd16(c, &r.in, res, 1, &im2));
        ASSERT_MEM_EQ(a, b, np * 3 * 2);                          /* ... and the export after them is the one before */
        free(u2);
    }
    /* errors */
    pk_image_u16 im = { 0, 0, a }, nul = { 0, 0, NULL };
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(NULL, &r.in, res, 0, &im));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, NULL, res, 0, &im));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, NULL, 0, &im));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, res, 0, NULL));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, res, 0, &nul));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, res, -1, &im));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, res, n, &im));
    r.in.n_frames = n - 1;
    ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, res, 0, &im));   /* a different roll size */
    r.in.n_frames = n;
    ASSERT_EQ(PK_E_ARG, pk_colour_export_linear16(NULL, 0, &im));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_linear16(&r.in, 0, NULL));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_linear16(&r.in, 0, &nul));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_linear16(&r.in, -1, &im));
    ASSERT_EQ(PK_E_ARG, pk_colour_export_linear16(&r.in, n, &im));
    { pk_frame_linear save = r.fr[0]; r.fr[0].height = 0;                 /* zero size */
      ASSERT_EQ(PK_E_ARG, pk_colour_export_linear16(&r.in, 0, &im));
      ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, res, 0, &im));
      r.fr[0] = save; r.fr[1].linear14[2] = NULL;                          /* NULL plane */
      ASSERT_EQ(PK_E_ARG, pk_colour_export_linear16(&r.in, 1, &im));
      ASSERT_EQ(PK_E_ARG, pk_colour_export_rpd16(c, &r.in, res, 1, &im));
      r.fr[1].linear14[2] = r.fr[1].linear14[0] + 2 * (size_t)W * H; }
    { pk_frame_linear save = r.fr[3]; r.fr[3].width = r.fr[3].height = 10;   /* under NRA's 11 x 11 */
      ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pk_colour_export_rpd16(c, &r.in, res, 3, &im));
      ASSERT_EQ(PK_OK, pk_colour_export_linear16(&r.in, 3, &im));        /* the linear export has no minimum */
      ASSERT_EQ(10, im.width);
      r.fr[3] = save; }
    free(a); free(b); free(u);
    pk_roll_result_free(res); pk_colour_close(c); api_free(&r);
    PASS();
}

/* a failed roll (every frame PK_E_ANALYSIS) exports as it renders: the all-zero scene LUT then falloff. Failure input:
 * Kodak's t15d lo-res frames, as test_roll's api_failed_roll builds it (the inverse of TLB's density LUT under the
 * identity polynomial). */
static pkv_file *T;
static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }
TEST failed_roll(void) {
    pk_colour *c = NULL; pk_roll_result *res = NULL; api_roll r; memset(&r, 0, sizeof r);
    uint16_t lut[16384], inv[4096]; uint16_t *got = NULL, *want = NULL; int16_t *bp = NULL, *rp = NULL; pkc_lut3 *z = NULL;
    pkc_roll_cfg *cfg = NULL;
    T = pkv_open(PKV_DIR "/roll_truth.pkv");
    ASSERT(T);
    int ri = pkv_list_index(T, "runs", "t15d"); ASSERT(ri >= 0);
    char nm[32];
    snprintf(nm, sizeof nm, "r%d_n", ri); int n = i32(pkv_get(T, nm))[0]; ASSERT_EQ(4, n);
    snprintf(nm, sizeof nm, "r%d_src", ri); const int32_t *src = i32(pkv_get(T, nm));
    snprintf(nm, sizeof nm, "r%d_dmin", ri); const int32_t *dm = i32(pkv_get(T, nm));
    pkc_density_lut(lut);
    for (int t = 0; t < 4096; t++) inv[t] = 0;
    for (int i = 16383; i >= 1; i--) if (lut[i] < 4096 && !inv[lut[i]]) inv[lut[i]] = (uint16_t)i;
    ASSERT_EQ(PK_OK, pk_colour_open(VENDOR_ROOT, DERIVED_ROOT, &c));
    ASSERT_EQ(0, api_make(&r, n, 32, 24));
    memset(r.in.poly_neg, 0, sizeof r.in.poly_neg);
    for (int ch = 0; ch < 3; ch++) r.in.poly_neg[ch][ch] = 1.0f;
    for (int k = 0; k < n; k++) {
        const int32_t *sr = src + 6 * k;
        uint16_t *fr12 = NULL; int fw = 0, fh = 0;
        if (sr[0] == 1) ASSERT_EQ(0, synframe_numpy((const double *)pkv_get(T, "npar")->data + (size_t)sr[1] * 20, &fr12, &fw, &fh));
        else if (sr[0] == 2) {
            const pkv_array *R = pkv_get(T, "recipe");
            ASSERT_EQ(0, synframe_recipe(i32(R) + (size_t)sr[1] * R->dims[1], i32(pkv_get(T, "recipe_len"))[sr[1]], &fr12, &fw, &fh));
        } else FAILm("t15d frame is not synthetic");
        ASSERT_EQ(250, fw); ASSERT_EQ(375, fh);
        uint16_t *lo = (uint16_t *)r.lo[k].linear14[0];
        for (size_t j = 0; j < (size_t)3 * 250 * 375; j++) {
            uint16_t t = fr12[j];
            if (!inv[t] || lut[inv[t]] != t) { free(fr12); FAILm("lo-res sample not on TLB's density LUT"); }
            lo[j] = inv[t];
        }
        free(fr12);
    }
    uint16_t *st = (uint16_t *)r.in.strip.linear14[0];
    for (int ch = 0; ch < 3; ch++) for (size_t j = 0; j < 250 * 700; j++) st[(size_t)ch * 250 * 700 + j] = inv[dm[ch]];
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &r.in, &res));
    size_t np = 32 * 24;
    got = malloc(np * 3 * 2); want = malloc(np * 3 * 2); bp = malloc(np * 3 * 2); rp = malloc(np * 3 * 2);
    z = calloc(1, sizeof *z); cfg = malloc(sizeof *cfg);
    ASSERT(got && want && bp && rp && z && cfg);
    ASSERT_EQ(PK_OK, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, 0, 0, cfg));
    for (int k = 0; k < n; k++) {
        ASSERT_EQ(PK_E_ANALYSIS, pk_roll_result_status(res, k));
        pk_image_u16 im = { 0, 0, got };
        ASSERT_EQ(PK_OK, pk_colour_export_rpd16(c, &r.in, res, k, &im));
        pkc_planes in = { 32, 24, { rp, rp + np, rp + 2 * np } }, out = { 32, 24, { bp, bp + np, bp + 2 * np } };
        const uint16_t *lk[3] = { r.fr[k].linear14[0], r.fr[k].linear14[1], r.fr[k].linear14[2] };
        pkc_front(r.in.poly_neg, lk, in.p, np);
        ASSERT_EQ(PK_OK, pkc_render_scene(&in, z, 1, &cfg->nra, &cfg->falloff, &out));
        pkc_rpd12_to_u16((const int16_t *const *)out.p, np, want);
        ASSERT_MEM_EQ(want, got, np * 3 * 2);
        ASSERT_EQ(PK_OK, pk_colour_export_linear16(&r.in, k, &im));   /* needs no analysis */
    }
    pkc_roll_cfg_free(cfg); free(cfg); free(z); free(got); free(want); free(bp); free(rp);
    pk_roll_result_free(res); pk_colour_close(c); api_free(&r);
    pkv_close(T);
    PASS();
}

/* Task 22 item 6: pk_colour_render_saved.  AnselOrientation 0 rotates the stored frame 270 BEFORE the balance (PIRotatePlanar)
 * and by (630, 540, 450, 360)[r] - 270 after it.  Mechanically: rendering frame F with (AnselOrientation 0, r 0) is rendering
 * G = rot270(F) with no rotation (the front end is per pixel, the scene is the roll's); the default AnselOrientation with
 * r 0 is pk_colour_render_rotated(.., 270, ..); the other codes give the TLB formula's output sizes. (Kodak-pinned on real
 * frames by lab/e2e/run_ao0.py + e2e.py, docs/re/26 section 6.) */
TEST api_saved_geometry(void) {
    pk_colour *c = NULL; pk_roll_result *res = NULL; api_roll r;
    const int W = 64, H = 48; const size_t np = (size_t)W * H;
    ASSERT(need_k());
    ASSERT_EQ(PK_OK, pk_colour_open(VENDOR_ROOT, DERIVED_ROOT, &c));
    ASSERT_EQ(0, api_make(&r, 4, W, H));
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &r.in, &res));
    /* lens falloff on for every frame: its floating-point position terms are not symmetric under the width / height swap, so
     * the order "rotate then balance" differs from "balance then rotate" on this 64 x 48 roll (found by a size probe) */
    for (int k = 0; k < 4; k++) ASSERT_EQ(PK_OK, pkc_roll_result_force_falloff(res, k, 1));
    uint8_t *a = malloc(np * 3), *b = malloc(np * 3), *e = malloc(np * 3);
    uint16_t *rot = malloc(np * 3 * sizeof *rot);
    ASSERT(a && b && e && rot);
    /* G = rot270(F) for frame 1: dst(x, y) = src(W - 1 - y, x), dst is H wide and W high */
    const pk_frame_linear *F = &r.fr[1];
    for (int ch = 0; ch < 3; ch++)
        for (int y = 0; y < W; y++)
            for (int x = 0; x < H; x++) rot[(size_t)ch * np + (size_t)y * H + x] = F->linear14[ch][(size_t)x * W + (W - 1 - y)];
    pk_frame_linear G = { H, W, { rot, rot + np, rot + 2 * np } };
    pk_frame_linear *saved = r.fr; r.fr = malloc(4 * sizeof *r.fr); ASSERT(r.fr);
    memcpy(r.fr, saved, 4 * sizeof *r.fr);
    r.in.frames = r.fr;
    r.fr[1] = G;
    pk_image_u8 ia = { 0, 0, a }, ib = { 0, 0, b };
    ASSERT_EQ(PK_OK, pk_colour_render(c, &r.in, res, 1, NULL, &ia));               /* the balance of G, no rotation */
    r.fr[1] = *F;
    ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &r.in, res, 1, NULL, 0, 0, &ib));   /* AnselOrientation 0, r 0 */
    ASSERT_EQ(H, ib.width); ASSERT_EQ(W, ib.height);
    ASSERT_EQ(H, ia.width); ASSERT_EQ(W, ia.height);
    ASSERT_MEM_EQ(a, b, np * 3);
    /* the default AnselOrientation, r 0 = pk_colour_render_rotated 270 (balance THEN rotate) -- which differs from
     * AnselOrientation 0 (rotate THEN balance) on this roll: this is what tells the two orders apart */
    memcpy(e, b, np * 3);                                                              /* AnselOrientation 0, r 0 */
    ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &r.in, res, 1, NULL, PK_ANSEL_ORIENTATION_PSI, 0, &ib));
    ASSERT_EQ(PK_OK, pk_colour_render_rotated(c, &r.in, res, 1, NULL, 270, &ia));
    ASSERT_MEM_EQ(a, b, np * 3); ASSERT_EQ(H, ib.width);
    ASSERT(memcmp(e, b, np * 3) != 0);
    /* the picture-rotation table (630, 540, 450, 360)[r] - (0x10E - AnselOrientation) mod 360, pinned by content: default
     * order post-rotations 270, 180, 90, 0 on F; AnselOrientation 0 post-rotations 0, 270, 180, 90 on G = rot270(F) */
    static const int POST_DEF[4] = { 270, 180, 90, 0 }, POST_AO0[4] = { 0, 270, 180, 90 };
    for (int pr = 0; pr < 4; pr++) {
        r.fr[1] = *F;
        ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &r.in, res, 1, NULL, PK_ANSEL_ORIENTATION_PSI, pr, &ib));
        ASSERT_EQ(PK_OK, pk_colour_render_rotated(c, &r.in, res, 1, NULL, POST_DEF[pr], &ia));
        ASSERT_MEM_EQ(a, b, np * 3);
        ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &r.in, res, 1, NULL, 0, pr, &ib));
        r.fr[1] = G;
        ASSERT_EQ(PK_OK, pk_colour_render_rotated(c, &r.in, res, 1, NULL, POST_AO0[pr], &ia));
        ASSERT_MEM_EQ(a, b, np * 3);
    }
    r.fr[1] = *F;
    static const int WD[2][4] = { { H, W, H, W }, { H, W, H, W } };   /* net rotation: 270, 180, 90, 0 -> width H, W, H, W */
    for (int ao = 0; ao < 2; ao++)
        for (int pr = 0; pr < 4; pr++) {
            ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &r.in, res, 1, NULL, ao ? PK_ANSEL_ORIENTATION_PSI : 0, pr, &ib));
            ASSERT_EQ(WD[ao][pr], ib.width);
        }
    /* AnselOrientation 0 with r 1..3 ends in the same orientation (pre 270, post 270 / 180 / 90) as the default */
    ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &r.in, res, 1, NULL, 0, 1, &ib));
    ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &r.in, res, 1, NULL, PK_ANSEL_ORIENTATION_PSI, 1, &ia));
    ASSERT_EQ(ia.width, ib.width); ASSERT_EQ(ia.height, ib.height);
    ASSERT_EQ(PK_E_ARG, pk_colour_render_saved(c, &r.in, res, 1, NULL, 90, 0, &ib));
    ASSERT_EQ(PK_E_ARG, pk_colour_render_saved(c, &r.in, res, 1, NULL, -1, 0, &ib));
    ASSERT_EQ(PK_E_ARG, pk_colour_render_saved(c, &r.in, res, 1, NULL, 0, 4, &ib));
    ASSERT_EQ(PK_E_ARG, pk_colour_render_saved(c, &r.in, res, 1, NULL, 0, -1, &ib));
    ASSERT_EQ(PK_E_ARG, pk_colour_render_saved(NULL, &r.in, res, 1, NULL, 0, 0, &ib));
    free(r.fr); r.fr = saved; r.in.frames = saved;
    free(a); free(b); free(e); free(rot);
    pk_roll_result_free(res); pk_colour_close(c); api_free(&r);
    PASS();
}

SUITE(export) { RUN_TEST(interleave_u8); RUN_TEST(rpd_scaling); RUN_TEST(linear_scaling); RUN_TEST(rpd_real_frame);
    RUN_TEST(api_exports); RUN_TEST(api_saved_geometry); RUN_TEST(failed_roll); }
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) { GREATEST_MAIN_BEGIN(); RUN_SUITE(export); GREATEST_MAIN_END(); }
