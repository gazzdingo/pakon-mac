#include "greatest.h"
#include "pkv.h"
#include "adjust.h"
#include "icc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Vectors: lab/oracle/scripts/adjust_grid.py (Kodak PIColorAdjustPlanar under Wine) packed by
 * lab/vectors/gen_adjust.py. cfg rows: r g b bri con sharp sat bnw film input. */
static pkv_file *g_f;
static int g_rows, g_w, g_h;

static enum greatest_test_res open_vectors(void) {
    if (!g_f) {
        g_f = pkv_open(PKV_DIR "/adjust.pkv"); ASSERT(g_f);
        const pkv_array *cfg = pkv_get(g_f, "cfg"), *in0 = pkv_get(g_f, "in0");
        ASSERT(cfg && in0); ASSERT_EQ(2, cfg->ndim); ASSERT_EQ(10, cfg->dims[1]);
        g_rows = cfg->dims[0]; g_h = in0->dims[1]; g_w = in0->dims[2];
    }
    PASS();
}
static const int32_t *cfg_row(int k) { return (const int32_t *)pkv_get(g_f, "cfg")->data + 10 * k; }
static pk_adjust adj_of(const int32_t *c) {
    pk_adjust a = { c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7] };
    return a;
}
static const pkv_array *row_arr(int k, const char *suffix) {
    char nm[32]; snprintf(nm, sizeof nm, "row%02d_%s", k, suffix);
    return pkv_get(g_f, nm);
}
/* a fresh copy of the row's input image */
static int load_input(int k, pkc_planes *img) {
    char nm[8]; snprintf(nm, sizeof nm, "in%d", cfg_row(k)[9]);
    const pkv_array *I = pkv_get(g_f, nm);
    size_t n = (size_t)g_w * g_h;
    if (!I || I->n != 3 * n) return 0;
    img->w = g_w; img->h = g_h;
    for (int c = 0; c < 3; c++) {
        img->p[c] = malloc(n * 2);
        if (!img->p[c]) return 0;
        memcpy(img->p[c], (const int16_t *)I->data + (size_t)c * n, n * 2);
    }
    return 1;
}
static void free_img(pkc_planes *img) { for (int c = 0; c < 3; c++) { free(img->p[c]); img->p[c] = NULL; } }

/* LUTs equal the dumps at 0x10014a69; the LUT stage runs exactly when Kodak's did */
TEST lut_matches_oracle(void) {
    CHECK_CALL(open_vectors());
    pkc_lut3 *l = malloc(sizeof *l); ASSERT(l);
    int nlut = 0, bad = -1;
    for (int k = 0; k < g_rows && bad < 0; k++) {
        pk_adjust a = adj_of(cfg_row(k)); int active = -1;
        pkc_adjust_lut(&a, l, &active);
        const pkv_array *L = row_arr(k, "lut");
        if (active != (L != NULL)) { bad = k; break; }
        if (L) {
            nlut++;
            if (L->n != 3 * 4096 || memcmp(L->data, l->t, sizeof l->t)) bad = k;
        }
    }
    free(l);
    if (bad >= 0) { fprintf(stderr, "row %d: LUT or LUT-stage gate differs\n", bad); FAIL(); }
    ASSERT(nlut >= 40);
    PASS();
}

/* RE 06's clamp-loop bug, through the oracle dump and through the port */
TEST bug_case_g4095_is_4222(void) {
    CHECK_CALL(open_vectors());
    int found = 0;
    for (int k = 0; k < g_rows; k++) {
        const int32_t *c = cfg_row(k);
        if (c[0] == 25 && c[1] == 0 && c[2] == 0 && c[3] == 0 && c[4] == 100 && c[9] == 0) {
            const pkv_array *L = row_arr(k, "lut"); ASSERT(L);
            ASSERT_EQ(4222, ((const int16_t *)L->data)[4096 + 4095]);
            found = 1;
        }
    }
    ASSERT(found);
    pk_adjust a = { 25, 0, 0, 0, 100, 0, 0, 0 };
    pkc_lut3 *l = malloc(sizeof *l); ASSERT(l); int active = 0;
    pkc_adjust_lut(&a, l, &active);
    int g = l->t[1][4095], b = l->t[2][4095], r = l->t[0][4095], g0 = l->t[1][0];
    free(l);
    ASSERT(active);
    ASSERT_EQ(4222, g); ASSERT_EQ(4222, b); ASSERT_EQ(4095, r);
    ASSERT_EQ(0, g0);  /* the leading negative run is clamped */
    PASS();
}

/* LUT -> USM output equals the ICC-stage input captured at kodakcms!SpEvaluate, border included */
TEST post_usm_matches_oracle(void) {
    CHECK_CALL(open_vectors());
    size_t n = (size_t)g_w * g_h; int npre = 0;
    for (int k = 0; k < g_rows; k++) {
        const pkv_array *P = row_arr(k, "pre");
        if (!P) continue;
        npre++;
        ASSERT(cfg_row(k)[5] != 0); ASSERT_EQ(3 * n, P->n);
        pkc_planes img; ASSERT(load_input(k, &img));
        pk_adjust a = adj_of(cfg_row(k));
        pk_status s = pkc_adjust_apply(&img, &a);
        int bad = 0;
        for (int c = 0; c < 3; c++)
            if (memcmp(img.p[c], (const int16_t *)P->data + (size_t)c * n, n * 2)) bad |= 1 << c;
        free_img(&img);
        ASSERT_EQ(PK_OK, s);
        if (bad) { fprintf(stderr, "row %d planes 0x%x differ\n", k, bad); FAIL(); }
    }
    ASSERT(npre >= 20);
    PASS();
}

/* RE 06 open item 3: the border is filtered (edge replicated), not passed through or zeroed */
TEST usm_border_is_filtered(void) {
    CHECK_CALL(open_vectors());
    int checked = 0;
    for (int k = 0; k < g_rows; k++) {
        const int32_t *c = cfg_row(k);
        if (!(c[5] == 100 && c[4] == 0 && c[0] == 0 && c[3] == 0 && c[9] == 0)) continue;
        const pkv_array *P = row_arr(k, "pre"), *I = pkv_get(g_f, "in0"); ASSERT(P && I);
        const int16_t *p = P->data, *in = I->data;
        int top = 0, left = 0;
        for (int x = 0; x < g_w; x++) top += p[x] != in[x];
        for (int y = 0; y < g_h; y++) left += p[(size_t)y * g_w] != in[(size_t)y * g_w];
        ASSERT(top > g_w / 2); ASSERT(left > g_h / 2);
        /* a corner by hand: replicate-padded 3x3 [1 2 1]x[1 2 1]/16, A = 16384, s = 16384 */
        int v0 = (4096 * in[0] + 8192 * in[0] + 4096 * in[g_w] + 8192) >> 14;
        int v1 = (4096 * in[1] + 8192 * in[1] + 4096 * in[g_w + 1] + 8192) >> 14;
        int blur = (4096 * v0 + 8192 * v0 + 4096 * v1 + 8192) >> 14;
        int t = ((in[0] - blur) * 16384 + 8192) >> 14;
        int o = in[0] + t; o = o < 0 ? 0 : o > 4095 ? 4095 : o;
        ASSERT_EQ(o, p[0]);
        checked = 1;
    }
    ASSERT(checked);
    PASS();
}

/* final u8 = ICC(apply(in)) equals the oracle's sRGB output for every grid point */
TEST final_u8_matches_oracle(void) {
    CHECK_CALL(open_vectors());
    size_t n = (size_t)g_w * g_h;
    uint8_t *o[3];
    for (int c = 0; c < 3; c++) { o[c] = malloc(n); ASSERT(o[c]); }
    int bad_row = -1; pk_status st = PK_OK;
    for (int k = 0; k < g_rows && bad_row < 0; k++) {
        const int32_t *c = cfg_row(k);
        const pkv_array *U = row_arr(k, "u8");
        if (!U || U->n != 3 * n) { bad_row = k; break; }
        pkc_planes img;
        if (!load_input(k, &img)) { bad_row = k; break; }
        pk_adjust a = adj_of(c);
        pkc_kct *t = NULL;
        st = pkc_adjust_apply(&img, &a);
        if (st == PK_OK) st = pkc_icc_select(DERIVED_ROOT, c[8], c[6], c[7], &t);
        if (st == PK_OK) {
            const int16_t *in[3] = { img.p[0], img.p[1], img.p[2] };
            pkc_icc_eval(t, in, o, n);
            for (int ch = 0; ch < 3; ch++)
                if (memcmp(o[ch], (const uint8_t *)U->data + (size_t)ch * n, n)) bad_row = k;
        } else bad_row = k;
        pkc_kct_free(t); free_img(&img);
    }
    for (int c = 0; c < 3; c++) free(o[c]);
    if (bad_row >= 0) { fprintf(stderr, "row %d differs (status %d)\n", bad_row, (int)st); FAIL(); }
    PASS();
}

/* Kodak never feeds the LUT out-of-range samples; the port clamps the index instead of reading OOB */
TEST lut_index_is_clamped(void) {
    int16_t r[9] = { -5, 0, 4095, 4096, 32767, -32768, 100, 2000, 3000 }, g[9], b[9];
    memcpy(g, r, sizeof r); memcpy(b, r, sizeof r);
    pkc_planes img = { 9, 1, { r, g, b } };
    pk_adjust a = { 25, 0, 0, 0, 100, 0, 0, 0 };
    ASSERT_EQ(PK_OK, pkc_adjust_apply(&img, &a));
    pkc_lut3 *l = malloc(sizeof *l); ASSERT(l); int active;
    pkc_adjust_lut(&a, l, &active);
    int e0 = l->t[1][0], e4095 = l->t[1][4095];
    free(l);
    ASSERT_EQ(e0, g[0]); ASSERT_EQ(e4095, g[3]); ASSERT_EQ(e4095, g[4]); ASSERT_EQ(e0, g[5]);
    PASS();
}

TEST bad_args(void) {
    static int16_t p[3][16];
    pkc_planes img = { 4, 4, { p[0], p[1], p[2] } }, tiny = { 2, 8, { p[0], p[1], p[2] } };
    pk_adjust ok = { 0 }, a;
    ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(NULL, &ok));
    ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, NULL));
    a = ok; a.r = 1001; ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, &a));
    a = ok; a.contrast = -1001; ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, &a));
    a = ok; a.brightness = 1001; ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, &a));
    a = ok; a.sharpness = -1; ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, &a));
    a = ok; a.sharpness = 2001; ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, &a));
    a = ok; a.saturation = 6; ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, &a));
    a = ok; a.bnw = 4; ASSERT_EQ(PK_E_ARG, pkc_adjust_apply(&img, &a));
    ASSERT_EQ(PK_E_ARG, pkc_adjust_usm(NULL, 25));
    ASSERT_EQ(PK_E_ARG, pkc_adjust_usm(&img, 2001));
    ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pkc_adjust_usm(&tiny, 25));
    ASSERT_EQ(PK_OK, pkc_adjust_usm(&tiny, 0));
    ASSERT_EQ(PK_OK, pkc_adjust_apply(&img, &ok));
    PASS();
}

SUITE(adjust) {
    RUN_TEST(lut_matches_oracle);
    RUN_TEST(bug_case_g4095_is_4222);
    RUN_TEST(post_usm_matches_oracle);
    RUN_TEST(usm_border_is_filtered);
    RUN_TEST(final_u8_matches_oracle);
    RUN_TEST(lut_index_is_clamped);
    RUN_TEST(bad_args);
}

GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(adjust);
    if (g_f) pkv_close(g_f);
    GREATEST_MAIN_END();
}
