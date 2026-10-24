#include "greatest.h"
#include "pkv.h"
#include "icc.h"
#include "adjust.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define KCMS DERIVED_ROOT "/kcms/"
#define DEFAULT_KCT KCMS "default_rpd_unity_unity_srgb.kct"

static size_t blob_len(const pkc_kct *k) {
    size_t g = (size_t)k->gridN;
    return 3 * 4096 * 2 * 4 + g * g * g * 6 + 3 * 16384;
}
/* checks one (in,out) pair of vector sets against table `k` */
static enum greatest_test_res check_set(const pkv_file *f, const char *in_name, const char *out_name, const pkc_kct *k) {
    const pkv_array *I = pkv_get(f, in_name), *O = pkv_get(f, out_name);
    ASSERT(I && O);
    size_t n = (size_t)I->dims[1];
    const int16_t *in[3]; uint8_t *out[3];
    for (int c = 0; c < 3; c++) { in[c] = (const int16_t *)I->data + c * n; out[c] = malloc(n); ASSERT(out[c]); }
    pkc_icc_eval(k, in, out, n);
    for (int c = 0; c < 3; c++) {
        const uint8_t *exp = (const uint8_t *)O->data + c * n;
        int eq = memcmp(exp, out[c], n) == 0;
        free(out[c]);
        ASSERT(eq);
    }
    PASS();
}
static enum greatest_test_res check_stem(const char *in_name, const char *out_name, const char *file) {
    pkv_file *f = pkv_open(PKV_DIR "/icc.pkv"); ASSERT(f);
    pkc_kct *k = NULL; ASSERT_EQ(PK_OK, pkc_kct_load(file, &k)); ASSERT(k);
    enum greatest_test_res r = check_set(f, in_name, out_name, k);
    pkc_kct_free(k); pkv_close(f);
    return r;
}
TEST big_real_kodakcms(void) { CHECK_CALL(check_stem("big_in", "big_out", DEFAULT_KCT)); PASS(); }
TEST grey_and_corners(void) { CHECK_CALL(check_stem("grey_in", "grey_out", DEFAULT_KCT)); PASS(); }
TEST romm_unity_unity(void) { CHECK_CALL(check_stem("v1_in", "v1_out", KCMS "romm__unity__unity.kct")); PASS(); }
TEST rpd_satplus03_sepia(void) { CHECK_CALL(check_stem("v2_in", "v2_out", KCMS "rpd__satplus03__sepia.kct")); PASS(); }

TEST load_errors(void) {
    pkc_kct *k = NULL;
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_kct_load(KCMS "nope.kct", &k));
    FILE *s = fopen(DEFAULT_KCT, "rb"); ASSERT(s);
    static unsigned char buf[400000]; size_t n = fread(buf, 1, sizeof buf, s); fclose(s);
    ASSERT(n > 1000);
    FILE *t = fopen("/tmp/pk_icc_trunc.kct", "wb"); ASSERT(t); fwrite(buf, 1, 1000, t); fclose(t);
    ASSERT_EQ(PK_E_FORMAT, pkc_kct_load("/tmp/pk_icc_trunc.kct", &k));
    ASSERT_EQ(NULL, k);
    /* one byte short of complete */
    t = fopen("/tmp/pk_icc_trunc.kct", "wb"); ASSERT(t); fwrite(buf, 1, n - 1, t); fclose(t);
    ASSERT_EQ(PK_E_FORMAT, pkc_kct_load("/tmp/pk_icc_trunc.kct", &k));
    /* trailing garbage */
    buf[n] = 0;
    t = fopen("/tmp/pk_icc_trunc.kct", "wb"); ASSERT(t); fwrite(buf, 1, n + 1, t); fclose(t);
    ASSERT_EQ(PK_E_FORMAT, pkc_kct_load("/tmp/pk_icc_trunc.kct", &k));
    /* bad magic */
    buf[0] = 'X';
    t = fopen("/tmp/pk_icc_trunc.kct", "wb"); ASSERT(t); fwrite(buf, 1, n, t); fclose(t);
    ASSERT_EQ(PK_E_FORMAT, pkc_kct_load("/tmp/pk_icc_trunc.kct", &k));
    remove("/tmp/pk_icc_trunc.kct");
    PASS();
}

/* select(...) must load exactly the file named `stem` */
static enum greatest_test_res sel_is(int film, int sat, int bnw, const char *stem) {
    char path[512]; snprintf(path, sizeof path, KCMS "%s.kct", stem);
    pkc_kct *a = NULL, *b = NULL;
    ASSERT_EQ(PK_OK, pkc_icc_select(DERIVED_ROOT, film, sat, bnw, &a));
    ASSERT_EQ(PK_OK, pkc_kct_load(path, &b));
    int same = a->gridN == b->gridN && memcmp(a->blob, b->blob, blob_len(a)) == 0 &&
               a->offRGB == b->offRGB && a->offR == b->offR && a->offG == b->offG && a->offB == b->offB;
    pkc_kct_free(a); pkc_kct_free(b);
    ASSERT(same);
    PASS();
}
TEST select_mapping(void) {
    CHECK_CALL(sel_is(1, -5, 0, "rpd__satminus15__unity"));
    CHECK_CALL(sel_is(1, -4, 0, "rpd__satminus12__unity"));
    CHECK_CALL(sel_is(1, -3, 1, "rpd__satminus09__warm_bw"));
    CHECK_CALL(sel_is(1, -2, 2, "rpd__satminus06__cold_bw"));
    CHECK_CALL(sel_is(1, -1, 0, "rpd__satminus03__unity"));
    CHECK_CALL(sel_is(2, 0, 0, "rpd__unity__unity"));
    CHECK_CALL(sel_is(2, 1, 0, "rpd__satplus03__unity"));
    CHECK_CALL(sel_is(2, 2, 0, "rpd__satplus06__unity"));
    CHECK_CALL(sel_is(2, 3, 0, "rpd__satplus09__unity"));
    CHECK_CALL(sel_is(2, 4, 0, "rpd__satplus12__unity"));
    CHECK_CALL(sel_is(2, 5, 0, "rpd__satplus15__unity"));
    CHECK_CALL(sel_is(3, 3, 3, "rpd__satplus09__sepia"));
    CHECK_CALL(sel_is(0, 0, 0, "romm__unity__unity"));
    CHECK_CALL(sel_is(4, -5, 3, "romm__satminus15__sepia"));
    CHECK_CALL(sel_is(5, 0, 0, "rpd__unity__unity"));
    PASS();
}
TEST select_rpd_unity_is_default_table(void) {
    pkc_kct *a = NULL, *b = NULL;
    ASSERT_EQ(PK_OK, pkc_icc_select(DERIVED_ROOT, 1, 0, 0, &a));
    ASSERT_EQ(PK_OK, pkc_kct_load(DEFAULT_KCT, &b));
    int same = a->gridN == b->gridN && memcmp(a->blob, b->blob, blob_len(a)) == 0 &&
               a->offRGB == b->offRGB && a->offR == b->offR && a->offG == b->offG && a->offB == b->offB;
    pkc_kct_free(a); pkc_kct_free(b);
    ASSERT(same);
    PASS();
}
TEST select_all_88_load(void) {
    for (int film = 0; film < 2; film++)
        for (int sat = -5; sat <= 5; sat++)
            for (int bnw = 0; bnw < 4; bnw++) {
                pkc_kct *k = NULL;
                ASSERT_EQ(PK_OK, pkc_icc_select(DERIVED_ROOT, film ? 1 : 0, sat, bnw, &k));
                ASSERT(k); pkc_kct_free(k);
            }
    PASS();
}
TEST select_bad_args(void) {
    pkc_kct *k = NULL;
    ASSERT_EQ(PK_E_ARG, pkc_icc_select(DERIVED_ROOT, 1, -6, 0, &k));
    ASSERT_EQ(PK_E_ARG, pkc_icc_select(DERIVED_ROOT, 1, 6, 0, &k));
    ASSERT_EQ(PK_E_ARG, pkc_icc_select(DERIVED_ROOT, 1, 0, -1, &k));
    ASSERT_EQ(PK_E_ARG, pkc_icc_select(DERIVED_ROOT, 1, 0, 4, &k));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_icc_select("/nonexistent", 1, 0, 0, &k));
    PASS();
}

/* Task 21: kodakcms' small-call evaluator 0x100168d0 vs the real DLL in 499-pixel SpEvaluate calls (vectors/icc_small.pkv,
 * lab/vectors/gen_icc_small.py): 16 384 random 12-bit pixels + every edge triple incl. 16-bit values the 0xfff mask
 * folds, for PSI's default table and two adjusted ones. The ETI evaluator differs on some of them (both paths exist). */
TEST small_call_evaluator(void) {
    pkv_file *f = pkv_open(PKV_DIR "/icc_small.pkv"); ASSERT(f);
    const pkv_array *I = pkv_get(f, "small_in"); ASSERT(I);
    size_t n = (size_t)I->dims[1];
    static const int combo[3][2] = { { 0, 0 }, { 5, 3 }, { -3, 2 } };   /* (saturation, bnw): unity, satplus15 sepia, satminus09 cold */
    const int16_t *in[3]; uint8_t *out[3], *eti[3];
    for (int c = 0; c < 3; c++) { in[c] = (const int16_t *)I->data + c * n; out[c] = malloc(n); eti[c] = malloc(n); ASSERT(out[c] && eti[c]); }
    int bad = 0, eti_diff = 0;
    for (int k = 0; k < 3; k++) {
        pkc_kct *t = NULL;
        ASSERT_EQ(PK_OK, pkc_icc_select(DERIVED_ROOT, 1, combo[k][0], combo[k][1], &t));
        ASSERT(t->fut);
        char nm[32]; snprintf(nm, sizeof nm, "small_out%d", k);
        const pkv_array *O = pkv_get(f, nm); ASSERT(O);
        pkc_icc_eval_small(t->fut, in, out, n);
        pkc_icc_eval(t, in, eti, n);
        for (int c = 0; c < 3; c++) {
            const uint8_t *e = (const uint8_t *)O->data + c * n;
            for (size_t i = 0; i < n; i++) { bad += out[c][i] != e[i]; eti_diff += eti[c][i] != e[i]; }
        }
        pkc_kct_free(t);
    }
    for (int c = 0; c < 3; c++) { free(out[c]); free(eti[c]); }
    pkv_close(f);
    ASSERT_EQ(0, bad);
    ASSERT(eti_diff > 1000);
    PASS();
}

/* Task 21: PIColorAdjustPlanar's per-tile SpEvaluate calls (pkc_icc_eval_frame): crops of a real balanced frame through
 * Kodak's PIColorAdjustPlanar, shaped so that some Ima tiles are under 500 pixels (260 x 3 and 10 x 10 plain; 2000 x 5,
 * 5 x 700, 3 x 3, 130 x 131 sharpened at 500: the sharpening op moves the tile cuts), = pkc_adjust_apply + the tiled
 * ICC stage. The same crops through whole-frame ETI differ wherever a small tile is. */
TEST tiled_icc_stage(void) {
    pkv_file *f = pkv_open(PKV_DIR "/icc_small.pkv"); ASSERT(f);
    pkc_kct *k = NULL;
    ASSERT_EQ(PK_OK, pkc_icc_select(DERIVED_ROOT, 1, 0, 0, &k));
    static const char *const names[] = { "n1", "n2", "u1", "u2", "u3", "u4" };
    int bad = 0, untiled = 0;
    for (int t = 0; t < 6; t++) {
        char nm[48];
        snprintf(nm, sizeof nm, "tile_%s_cfg", names[t]); const int32_t *cfg = (const int32_t *)pkv_get(f, nm)->data;
        snprintf(nm, sizeof nm, "tile_%s_in", names[t]); const pkv_array *I = pkv_get(f, nm);
        snprintf(nm, sizeof nm, "tile_%s_out", names[t]); const pkv_array *O = pkv_get(f, nm);
        ASSERT(I && O);
        const int w = cfg[0], h = cfg[1];
        const size_t n = (size_t)w * h;
        int16_t *b = malloc(sizeof *b * 3 * n); uint8_t *o = malloc(3 * n), *u = malloc(3 * n);
        ASSERT(b && o && u);
        memcpy(b, I->data, sizeof *b * 3 * n);
        pkc_planes im = { w, h, { b, b + n, b + 2 * n } };
        pk_adjust a = { 0, 0, 0, 0, 0, cfg[2], 0, 0 };
        ASSERT_EQ(PK_OK, pkc_adjust_apply(&im, &a));
        uint8_t *op[3] = { o, o + n, o + 2 * n }, *up[3] = { u, u + n, u + 2 * n };
        ASSERT_EQ(PK_OK, pkc_icc_eval_frame(k, (const int16_t **)im.p, op, w, h, cfg[2] != 0));
        pkc_icc_eval(k, (const int16_t **)im.p, up, n);
        for (size_t i = 0; i < 3 * n; i++) { bad += o[i] != ((const uint8_t *)O->data)[i]; untiled += u[i] != ((const uint8_t *)O->data)[i]; }
        free(b); free(o); free(u);
    }
    pkc_kct_free(k);
    pkv_close(f);
    ASSERT_EQ(0, bad);
    ASSERT(untiled > 0);
    PASS();
}

TEST tiled_icc_errors(void) {
    pkc_kct *k = NULL;
    ASSERT_EQ(PK_OK, pkc_icc_select(DERIVED_ROOT, 0, 0, 0, &k));       /* romm: no fut tables */
    int16_t px[3] = { 100, 200, 300 }; uint8_t o[3];
    const int16_t *in[3] = { &px[0], &px[1], &px[2] }; uint8_t *op[3] = { &o[0], &o[1], &o[2] };
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_icc_eval_frame(k, in, op, 1, 1, 0));   /* a 1-pixel tile needs the small path */
    ASSERT_EQ(PK_E_ARG, pkc_icc_eval_frame(k, in, op, 0, 1, 0));
    ASSERT_EQ(PK_E_ARG, pkc_icc_eval_frame(NULL, in, op, 1, 1, 0));
    pkc_kct_free(k);
    PASS();
}

SUITE(icc_suite) {
    RUN_TEST(big_real_kodakcms); RUN_TEST(grey_and_corners); RUN_TEST(romm_unity_unity);
    RUN_TEST(rpd_satplus03_sepia); RUN_TEST(load_errors); RUN_TEST(select_mapping);
    RUN_TEST(select_rpd_unity_is_default_table); RUN_TEST(select_all_88_load); RUN_TEST(select_bad_args);
    RUN_TEST(small_call_evaluator); RUN_TEST(tiled_icc_stage); RUN_TEST(tiled_icc_errors);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); RUN_SUITE(icc_suite); GREATEST_MAIN_END();
}
