#include "greatest.h"
#include "pkv.h"
#include "render.h"
#include "nra.h"
#include "analysis/exposure.h"
#include <stdlib.h>
#include <string.h>

static pkc_lut3 g_thr;
static pkc_falloff_params g_fp;
static pkc_sba_ctx g_ctx;
static int g_have;
static enum greatest_test_res need(void) {
    if (!g_have) {
        ASSERT_EQ(PK_OK, pkc_nra_prepare(VENDOR_ROOT, &g_thr));
        ASSERT_EQ(PK_OK, pkc_falloff_params_load(VENDOR_ROOT, &g_fp));
        ASSERT_EQ(PK_OK, pkc_sba_ctx_load(VENDOR_ROOT, DERIVED_ROOT, &g_ctx));
        g_have = 1;
    }
    PASS();
}

/* Scene k's SBA exposure in stops, computed (Task 18): the sba instance's pass-2 triple Y word Kodak produced for this
 * roll on v1's film base (exposure_truth.pkv run r4v1 = scan-20260828-163034, the frames of render.pkv) through
 * pkc_sba_exposure_stops. */
static enum greatest_test_res exposure(int k, double *st) {
    pkv_file *x = pkv_open(PKV_DIR "/exposure_truth.pkv"); ASSERT(x);
    char nm[32]; snprintf(nm, sizeof nm, "e%d_y", pkv_list_index(x, "names", "r4v1"));
    const pkv_array *Y = pkv_get(x, nm);
    pkc_sba_triple_out t; memset(&t, 0, sizeof t);
    int ok = Y && Y->dtype == 4 && Y->n == 8;
    if (ok) t.triple[0] = ((const int32_t *)Y->data)[k];
    pkv_close(x);
    ASSERT(ok);
    ASSERT_EQ(PK_OK, pkc_sba_exposure_stops(&t, &g_ctx, st));
    PASS();
}

static enum greatest_test_res scene(int k) {
    char nm[32];
    CHECK_CALL(need());
    pkv_file *f = pkv_open(PKV_DIR "/render.pkv"); ASSERT(f);
    #define GET(var, suffix) snprintf(nm, sizeof nm, "s%d_" suffix, k); \
        const pkv_array *var = pkv_get(f, nm); ASSERT(var)
    GET(LUT, "lut"); GET(FO, "fo"); GET(EXP, "exp"); GET(I, "in"); GET(O, "out");
    int fo = ((const int32_t *)FO->data)[0];
    /* the flag must follow from the scene's SBA exposure through the Kodak gate: the computed exposure (= the half-stops
     * the vector recorded from the oracle) */
    double st = 99;
    CHECK_CALL(exposure(k, &st));
    ASSERT_EQ(((const int32_t *)EXP->data)[0] * 0.5, st);
    ASSERT_EQ(fo, pkc_falloff_enabled(&g_fp, st));
    int h = I->dims[1], w = I->dims[2]; size_t n = (size_t)w * h;
    ASSERT_EQ(3 * 4096u, LUT->n);
    pkc_lut3 *lut = malloc(sizeof *lut); ASSERT(lut);
    memcpy(lut, LUT->data, sizeof *lut);
    pkc_planes in = { w, h, { 0 } }, out = { w, h, { 0 } };
    for (int c = 0; c < 3; c++) {
        in.p[c] = (int16_t *)I->data + (size_t)c * n;
        out.p[c] = calloc(n, 2); ASSERT(out.p[c]);
    }
    pk_status s = pkc_render_scene(&in, lut, fo, &g_thr, &g_fp, &out);
    int bad = 0;
    for (int c = 0; c < 3; c++) {
        const int16_t *exp = (const int16_t *)O->data + (size_t)c * n;
        if (memcmp(exp, out.p[c], n * 2)) bad |= 1 << c;
        free(out.p[c]);
    }
    free(lut); pkv_close(f);
    ASSERT_EQ(PK_OK, s);
    ASSERT_EQ(0, bad);
    PASS();
}
TEST scene0(void) { return scene(0); }
TEST scene1(void) { return scene(1); }
TEST scene2_falloff_off(void) { return scene(2); }
TEST scene3(void) { return scene(3); }

/* falloff must actually matter for the vectors that enable it, and not for the one that disables it */
TEST falloff_flag_is_load_bearing(void) {
    CHECK_CALL(need());
    pkv_file *f = pkv_open(PKV_DIR "/render.pkv"); ASSERT(f);
    const pkv_array *LUT = pkv_get(f, "s1_lut"), *I = pkv_get(f, "s1_in"); ASSERT(LUT && I);
    int h = I->dims[1], w = I->dims[2]; size_t n = (size_t)w * h;
    pkc_lut3 *lut = malloc(sizeof *lut); ASSERT(lut); memcpy(lut, LUT->data, sizeof *lut);
    pkc_planes in = { w, h, { 0 } }, a = { w, h, { 0 } }, b = { w, h, { 0 } };
    for (int c = 0; c < 3; c++) {
        in.p[c] = (int16_t *)I->data + (size_t)c * n; a.p[c] = calloc(n, 2); b.p[c] = calloc(n, 2);
        ASSERT(a.p[c] && b.p[c]);
    }
    ASSERT_EQ(PK_OK, pkc_render_scene(&in, lut, 0, &g_thr, &g_fp, &a));
    ASSERT_EQ(PK_OK, pkc_render_scene(&in, lut, 1, &g_thr, &g_fp, &b));
    int differs = 0;
    for (int c = 0; c < 3; c++) { differs |= memcmp(a.p[c], b.p[c], n * 2) != 0; free(a.p[c]); free(b.p[c]); }
    free(lut); pkv_close(f);
    ASSERT(differs);
    PASS();
}

TEST bad_args(void) {
    CHECK_CALL(need());
    static int16_t a[3][121], o[3][121];
    static pkc_lut3 l;
    pkc_planes in = { 11, 11, { a[0], a[1], a[2] } }, out = { 11, 11, { o[0], o[1], o[2] } };
    ASSERT_EQ(PK_E_ARG, pkc_render_scene(NULL, &l, 0, &g_thr, &g_fp, &out));
    ASSERT_EQ(PK_E_ARG, pkc_render_scene(&in, NULL, 0, &g_thr, &g_fp, &out));
    ASSERT_EQ(PK_E_ARG, pkc_render_scene(&in, &l, 1, &g_thr, NULL, &out));
    ASSERT_EQ(PK_E_ARG, pkc_render_scene(&in, &l, 0, &g_thr, &g_fp, &in));   /* aliasing */
    in.w = out.w = 10;
    ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pkc_render_scene(&in, &l, 0, &g_thr, &g_fp, &out));
    PASS();
}

SUITE(render_suite) {
    RUN_TEST(scene0); RUN_TEST(scene1); RUN_TEST(scene2_falloff_off); RUN_TEST(scene3);
    RUN_TEST(falloff_flag_is_load_bearing); RUN_TEST(bad_args);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); RUN_SUITE(render_suite); pkc_sba_ctx_free(&g_ctx); GREATEST_MAIN_END();
}
