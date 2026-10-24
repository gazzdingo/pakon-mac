#include "greatest.h"
#include "pkv.h"
#include "nra.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static pkc_lut3 g_thr;
static int g_have;

static enum greatest_test_res need_thr(void) {
    if (!g_have) { ASSERT_EQ(PK_OK, pkc_nra_prepare(VENDOR_ROOT, &g_thr)); g_have = 1; }
    PASS();
}

TEST thresholds_match(void) {
    pkv_file *f = pkv_open(PKV_DIR "/nra.pkv"); ASSERT(f);
    CHECK_CALL(need_thr());
    const pkv_array *L = pkv_get(f, "lut"); ASSERT(L);
    ASSERT_EQ(3 * 4096u, L->n);
    ASSERT_MEM_EQ(L->data, g_thr.t, sizeof g_thr.t);
    pkv_close(f); PASS();
}

static enum greatest_test_res check_img(const char *in_name, const char *out_name) {
    pkv_file *f = pkv_open(PKV_DIR "/nra.pkv"); ASSERT(f);
    CHECK_CALL(need_thr());
    const pkv_array *I = pkv_get(f, in_name), *O = pkv_get(f, out_name); ASSERT(I && O);
    int h = I->dims[1], w = I->dims[2]; size_t n = (size_t)w * h;
    pkc_planes in = { w, h, { 0 } }, out = { w, h, { 0 } };
    for (int c = 0; c < 3; c++) {
        in.p[c] = (int16_t *)I->data + (size_t)c * n;
        out.p[c] = calloc(n, 2); ASSERT(out.p[c]);
    }
    pk_status s = pkc_nra_apply(&in, &out, &g_thr);
    int bad = 0;
    for (int c = 0; c < 3; c++) {
        const int16_t *exp = (const int16_t *)O->data + (size_t)c * n;
        if (memcmp(exp, out.p[c], n * 2)) bad |= 1 << c;
        free(out.p[c]);
    }
    pkv_close(f);
    ASSERT_EQ(PK_OK, s);
    ASSERT_EQ(0, bad);
    PASS();
}
/* oracle: whole-image in-chain Kodak dumps */
TEST img_s1(void)   { return check_img("s1_in", "s1_out"); }
TEST img_s2(void)   { return check_img("s2_in", "s2_out"); }
TEST img_s3(void)   { return check_img("s3_in", "s3_out"); }
TEST img_ramp(void) { return check_img("ramp_in", "ramp_out"); }  /* corners 0 and 4095 */
/* reference-computed (nref.py) */
TEST img_real(void) { return check_img("real_in", "real_out"); }
TEST img_corner(void) { return check_img("corner_in", "corner_out"); }

TEST too_small(void) {
    CHECK_CALL(need_thr());
    static int16_t a[3][40 * 40], o[3][40 * 40];
    pkc_planes in = { 10, 40, { a[0], a[1], a[2] } }, out = { 10, 40, { o[0], o[1], o[2] } };
    ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pkc_nra_apply(&in, &out, &g_thr));
    in.w = out.w = 40; in.h = out.h = 10;
    ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pkc_nra_apply(&in, &out, &g_thr));
    in.w = out.w = 11; in.h = out.h = 11;   /* smallest legal */
    ASSERT_EQ(PK_OK, pkc_nra_apply(&in, &out, &g_thr));
    PASS();
}
TEST bad_args(void) {
    CHECK_CALL(need_thr());
    static int16_t a[3][121];
    pkc_planes in = { 11, 11, { a[0], a[1], a[2] } }, out = { 12, 11, { a[0], a[1], a[2] } };
    ASSERT_EQ(PK_E_ARG, pkc_nra_apply(&in, &out, &g_thr));
    ASSERT_EQ(PK_E_ARG, pkc_nra_apply(NULL, &out, &g_thr));
    ASSERT_EQ(PK_E_ARG, pkc_nra_prepare(NULL, &g_thr));
    PASS();
}

/* ---- prepare error paths, via temp files ---- */
static char *tmpfile_with(const char *text) {
    char *p = strdup("/tmp/pk_nra_XXXXXX"); int fd = mkstemp(p);
    if (fd < 0) { free(p); return NULL; }
    size_t n = strlen(text); ssize_t w = write(fd, text, n); close(fd);
    if (w != (ssize_t)n) { free(p); return NULL; }
    return p;
}
static const char *GOOD_DPI = "Key = x.dpi\nNoiseScale = 1.0\nWindowSize = 11\n";

static enum greatest_test_res prep_with(const char *tbl_txt, const char *dpi_txt, pk_status want) {
    char *t = tmpfile_with(tbl_txt), *d = tmpfile_with(dpi_txt); ASSERT(t && d);
    pkc_lut3 l; pk_status s = pkc_nra_prepare_files(t, d, &l);
    unlink(t); unlink(d); free(t); free(d);
    ASSERT_EQ(want, s);
    PASS();
}
static char *make_tbl(int rows) {
    size_t cap = 100 + (size_t)rows * 40; char *b = malloc(cap), *p = b;
    p += sprintf(p, "key = t.tbl\nBands = 3\nNoiseTable =\n");
    for (int i = 0; i < rows; i++) p += sprintf(p, "%d 17.041 18.245 23.743\n", i);
    return b;
}
TEST prepare_short_table(void) {
    char *t = make_tbl(100); enum greatest_test_res r = prep_with(t, GOOD_DPI, PK_E_VENDOR_DATA); free(t); return r;
}
TEST prepare_long_table(void) {
    char *t = make_tbl(4097); enum greatest_test_res r = prep_with(t, GOOD_DPI, PK_E_VENDOR_DATA); free(t); return r;
}
TEST prepare_ok_synthetic(void) {   /* flat sigma 17.041/18.245/23.743: falloff then round */
    char *t = make_tbl(4096); char *tp = tmpfile_with(t), *dp = tmpfile_with(GOOD_DPI); ASSERT(tp && dp);
    pkc_lut3 l; ASSERT_EQ(PK_OK, pkc_nra_prepare_files(tp, dp, &l));
    ASSERT_EQ(17, l.t[0][4095]); ASSERT_EQ(18, l.t[1][4095]); ASSERT_EQ(24, l.t[2][4095]);
    ASSERT_EQ(0, l.t[0][0]);   /* sigma ramped to zero below the knee */
    unlink(tp); unlink(dp); free(tp); free(dp); free(t); PASS();
}
TEST prepare_duplicate_code(void) {   /* 4096 rows but code 7 appears twice and code 8 never */
    size_t cap = 100 + 4096 * 40; char *b = malloc(cap), *p = b;
    p += sprintf(p, "key = t.tbl\nBands = 3\nNoiseTable =\n");
    for (int i = 0; i < 4096; i++) p += sprintf(p, "%d 17.041 18.245 23.743\n", i == 8 ? 7 : i);
    enum greatest_test_res r = prep_with(b, GOOD_DPI, PK_E_VENDOR_DATA); free(b); return r;
}
TEST out_of_range_samples(void) {
    CHECK_CALL(need_thr());
    pkv_file *f = pkv_open(PKV_DIR "/nra.pkv"); ASSERT(f);
    const pkv_array *I = pkv_get(f, "real_in"), *O = pkv_get(f, "real_out"); ASSERT(I && O);
    int h = I->dims[1], w = I->dims[2]; size_t n = (size_t)w * h;
    pkc_planes in = { w, h, { 0 } }, out = { w, h, { 0 } };
    for (int c = 0; c < 3; c++) {
        in.p[c] = malloc(n * 2); out.p[c] = calloc(n, 2); ASSERT(in.p[c] && out.p[c]);
        memcpy(in.p[c], (const int16_t *)I->data + (size_t)c * n, n * 2);
        in.p[c][0] = -5; in.p[c][w - 1] = 5000; in.p[c][n - w] = -32768; in.p[c][n - 1] = 32767;
    }
    pk_status s = pkc_nra_apply(&in, &out, &g_thr);
    int bad = 0;
    /* pixels >= 6 from every edge cannot see the corner samples (star window reach is 5) */
    for (int c = 0; c < 3; c++) {
        const int16_t *exp = (const int16_t *)O->data + (size_t)c * n;
        for (int y = 6; y < h - 6; y++)
            for (int x = 6; x < w - 6; x++) if (exp[y * w + x] != out.p[c][y * w + x]) bad++;
        free(in.p[c]); free(out.p[c]);
    }
    pkv_close(f);
    ASSERT_EQ(PK_OK, s);
    ASSERT_EQ(0, bad);
    PASS();
}
TEST prepare_missing_dpi_keys(void) {
    char *t = make_tbl(4096);
    enum greatest_test_res r = prep_with(t, "Key = x\nWindowSize = 11\n", PK_E_VENDOR_DATA);
    if (r == GREATEST_TEST_RES_PASS) r = prep_with(t, "Key = x\nNoiseScale = 1.0\n", PK_E_VENDOR_DATA);
    if (r == GREATEST_TEST_RES_PASS) r = prep_with(t, "Key = x\nNoiseScale = 1.0\nWindowSize = 9\n", PK_E_VENDOR_DATA);
    free(t); return r;
}
TEST prepare_missing_files(void) {
    pkc_lut3 l;
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_nra_prepare("/nonexistent/dir", &l));
    PASS();
}

SUITE(nra_suite) {
    RUN_TEST(thresholds_match);
    RUN_TEST(img_s1); RUN_TEST(img_s2); RUN_TEST(img_s3); RUN_TEST(img_ramp);
    RUN_TEST(img_real); RUN_TEST(img_corner);
    RUN_TEST(too_small); RUN_TEST(bad_args);
    RUN_TEST(prepare_short_table); RUN_TEST(prepare_long_table); RUN_TEST(prepare_ok_synthetic);
    RUN_TEST(prepare_duplicate_code); RUN_TEST(out_of_range_samples); RUN_TEST(prepare_missing_dpi_keys); RUN_TEST(prepare_missing_files);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); RUN_SUITE(nra_suite); GREATEST_MAIN_END();
}
