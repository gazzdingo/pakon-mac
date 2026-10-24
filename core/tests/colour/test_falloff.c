#include "greatest.h"
#include "pkv.h"
#include "falloff.h"
#include <stdlib.h>
#include <string.h>

static pkc_falloff_params P;

static enum greatest_test_res need_params(void) {
    ASSERT_EQ(PK_OK, pkc_falloff_params_load(VENDOR_ROOT, &P));
    PASS();
}

TEST params(void) {
    CHECK_CALL(need_params());
    ASSERT_EQ(1250, P.scale);
    ASSERT_EQ(4095, P.max);
    ASSERT_EQ(0.7f, P.stops);
    ASSERT_EQ(-0.5, P.exp_min);
    ASSERT_EQ(7.0, P.exp_max);
    ASSERT_EQ(PK_E_ARG, pkc_falloff_params_load(NULL, &P));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_falloff_params_load("/nonexistent", &P));
    PASS();
}

static enum greatest_test_res check(int w, int h) {
    char in_n[32], out_n[32];
    snprintf(in_n, sizeof in_n, "in_%dx%d", w, h);
    snprintf(out_n, sizeof out_n, "out_%dx%d", w, h);
    CHECK_CALL(need_params());
    pkv_file *f = pkv_open(PKV_DIR "/falloff.pkv"); ASSERT(f);
    const pkv_array *I = pkv_get(f, in_n), *O = pkv_get(f, out_n); ASSERT(I && O);
    size_t n = (size_t)w * h;
    ASSERT_EQ(3 * n, I->n);
    int16_t *buf = malloc(3 * n * 2); ASSERT(buf);
    memcpy(buf, I->data, 3 * n * 2);
    pkc_planes img = { w, h, { buf, buf + n, buf + 2 * n } };
    ASSERT_EQ(PK_OK, pkc_falloff_apply(&img, &P));
    int diff = memcmp(buf, O->data, 3 * n * 2) != 0;
    free(buf); pkv_close(f);
    ASSERT_EQ(0, diff);
    PASS();
}
TEST img_1x1(void)    { return check(1, 1); }
TEST img_2x2(void)    { return check(2, 2); }
TEST img_7x3(void)    { return check(7, 3); }
TEST img_63x47(void)  { return check(63, 47); }
TEST img_300x200(void){ return check(300, 200); }
TEST img_2100x10(void){ return check(2100, 10); }   /* non-cache table path */
TEST img_10x2100(void){ return check(10, 2100); }

TEST gate(void) {
    CHECK_CALL(need_params());
    ASSERT_EQ(1, pkc_falloff_enabled(&P, -0.5));
    ASSERT_EQ(1, pkc_falloff_enabled(&P, 0.0));
    ASSERT_EQ(1, pkc_falloff_enabled(&P, 7.0));
    ASSERT_EQ(0, pkc_falloff_enabled(&P, -0.51));
    ASSERT_EQ(0, pkc_falloff_enabled(&P, -1.0));
    ASSERT_EQ(0, pkc_falloff_enabled(&P, 7.01));
    pkc_falloff_params q = P;
    q.scale = 0; ASSERT_EQ(0, pkc_falloff_enabled(&q, 0.0));
    q = P; q.stops = 1.0e-7f; ASSERT_EQ(0, pkc_falloff_enabled(&q, 0.0));
    ASSERT_EQ(0, pkc_falloff_enabled(NULL, 0.0));
    PASS();
}

/* 4095 stays 4095; 4094 + correction >= 1 saturates to 4095; zero correction at centre keeps value. */
TEST saturation(void) {
    CHECK_CALL(need_params());
    enum { W = 63, H = 47 };
    static int16_t a[3][W * H];
    for (int b = 0; b < 3; b++)
        for (int i = 0; i < W * H; i++) a[b][i] = (b == 0) ? 4095 : (b == 1) ? 4094 : 0;
    pkc_planes img = { W, H, { a[0], a[1], a[2] } };
    ASSERT_EQ(PK_OK, pkc_falloff_apply(&img, &P));
    int centre = (H / 2) * W + W / 2;
    int corner_c1 = 0;
    for (int i = 0; i < W * H; i++) {
        ASSERT_EQ(4095, a[0][i]);
        ASSERT(a[2][i] >= 0);
        if (a[2][i] >= 1) { ASSERT_EQ(4095, a[1][i]); corner_c1++; }
        else ASSERT_EQ(4094, a[1][i]);
    }
    ASSERT(corner_c1 > 0);
    ASSERT_EQ(0, a[2][centre]);
    ASSERT_EQ(4094, a[1][centre]);
    PASS();
}

TEST identity_and_args(void) {
    CHECK_CALL(need_params());
    int16_t a[3][4] = { {1,2,3,4}, {5,6,7,8}, {9,10,11,12} }, b[3][4];
    memcpy(b, a, sizeof a);
    pkc_planes img = { 2, 2, { a[0], a[1], a[2] } };
    pkc_falloff_params q = P; q.scale = 0;
    ASSERT_EQ(PK_OK, pkc_falloff_apply(&img, &q));
    ASSERT_MEM_EQ(b, a, sizeof a);
    q = P; q.stops = 0.0f;
    ASSERT_EQ(PK_OK, pkc_falloff_apply(&img, &q));
    ASSERT_MEM_EQ(b, a, sizeof a);
    ASSERT_EQ(PK_E_ARG, pkc_falloff_apply(NULL, &P));
    ASSERT_EQ(PK_E_ARG, pkc_falloff_apply(&img, NULL));
    img.w = 0;
    ASSERT_EQ(PK_E_ARG, pkc_falloff_apply(&img, &P));
    PASS();
}

SUITE(falloff_suite) {
    RUN_TEST(params);
    RUN_TEST(img_1x1); RUN_TEST(img_2x2); RUN_TEST(img_7x3); RUN_TEST(img_63x47);
    RUN_TEST(img_300x200); RUN_TEST(img_2100x10); RUN_TEST(img_10x2100);
    RUN_TEST(gate); RUN_TEST(saturation); RUN_TEST(identity_and_args);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(falloff_suite);
    GREATEST_MAIN_END();
}
