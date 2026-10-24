/* Task 10: analysis image (RE 19 resize) + 24x36 grid vs vectors/analysis_<roll>.pkv (lab/vectors/gen_analysis.py).
 * The vector images/grids were asserted equal to Kodak's own (PC53 oracle dumps) when generated. */
#include "greatest.h"
#include "pkv.h"
#include "analysis/image.h"
#include <stdlib.h>
#include <string.h>

static uint64_t fnv64(const pkc_planes *im) {
    uint64_t h = 0xcbf29ce484222325ull;
    size_t n = (size_t)im->w * im->h;
    for (int c = 0; c < 3; c++)
        for (size_t i = 0; i < n; i++) {
            uint16_t v = (uint16_t)im->p[c][i];
            h = (h ^ (v & 0xffu)) * 0x100000001b3ull;
            h = (h ^ (v >> 8)) * 0x100000001b3ull;
        }
    return h;
}
static uint64_t le64(const pkv_array *a) {
    uint64_t h = 0;
    for (int i = 7; i >= 0; i--) h = h << 8 | ((const uint8_t *)a->data)[i];
    return h;
}
static const pkv_array *getk(const pkv_file *f, int k, const char *suffix) {
    char nm[64]; snprintf(nm, sizeof nm, "s%d_%s", k, suffix);
    return pkv_get(f, nm);
}
static enum greatest_test_res check_grid(const pkc_planes *im, const pkv_array *G) {
    int32_t (*g)[PKC_GRID_N] = malloc(sizeof(int32_t[3][PKC_GRID_N])); ASSERT(g);
    pk_status s = pkc_grid24x36(im, g);
    int bad = 0;
    for (int c = 0; c < 3; c++)
        for (int i = 0; i < PKC_GRID_N; i++)
            bad += g[c][i] != ((const int16_t *)G->data)[c * PKC_GRID_N + i];
    free(g);
    ASSERT_EQ(PK_OK, s);
    ASSERT_EQ(0, bad);
    PASS();
}

/* every scene of a roll: dims, the resized image (full compare where stored, FNV-1a otherwise), the pass-1 grid,
 * and (FOS rolls) the pass-2 grid of the scpLut-mapped analysis image */
static enum greatest_test_res roll(const char *name, const char *scan) {
    char p[512];
    snprintf(p, sizeof p, PKV_DIR "/analysis_%s.pkv", name);
    pkv_file *f = pkv_open(p); ASSERT(f);
    snprintf(p, sizeof p, PKV_DIR "/analysis_%s.pkv", scan);
    pkv_file *fs = pkv_open(p); ASSERT(fs);
    const pkv_array *SF = pkv_get(f, "scan_frames"), *SCP = pkv_get(f, "scplut"), *FV = pkv_get(f, "fos_valid");
    ASSERT(SF && SCP && FV);
    int fos = ((const int32_t *)FV->data)[0];
    for (int k = 0; k < (int)SF->n; k++) {
        char nm[32]; snprintf(nm, sizeof nm, "f%d_lo", ((const int32_t *)SF->data)[k]);
        const pkv_array *LO = pkv_get(fs, nm); ASSERT(LO);
        int h = LO->dims[1], w = LO->dims[2];
        const uint16_t *lo[3];
        for (int c = 0; c < 3; c++) lo[c] = (const uint16_t *)LO->data + (size_t)c * w * h;
        const pkv_array *HW = getk(f, k, "img_hw"), *IMG = getk(f, k, "img"), *FNV = getk(f, k, "img_fnv"),
                        *G = getk(f, k, "grid"), *G2 = getk(f, k, "grid2");
        ASSERT(HW && FNV && G);
        int oh, ow; pkc_analysis_dims(w, h, &ow, &oh);
        ASSERT_EQ(((const int32_t *)HW->data)[0], oh);
        ASSERT_EQ(((const int32_t *)HW->data)[1], ow);
        pkc_planes im = { 0, 0, { 0 } };
        ASSERT_EQ(PK_OK, pkc_analysis_image(lo, w, h, &im));
        ASSERT_EQ(ow, im.w); ASSERT_EQ(oh, im.h);
        size_t n = (size_t)ow * oh;
        if (IMG) {
            int bad = 0;
            for (int c = 0; c < 3; c++) {
                const int16_t *exp = (const int16_t *)IMG->data + (size_t)c * n;
                bad |= memcmp(exp, im.p[c], n * 2) != 0;
            }
            ASSERT_EQ_FMT(0, bad, "%d");
        }
        ASSERT_EQ_FMT((unsigned long long)le64(FNV), (unsigned long long)fnv64(&im), "%llx");
        CHECK_CALL(check_grid(&im, G));
        if (fos) {                          /* pass 2: grid of scpLut[analysis image] */
            ASSERT(G2);
            pkc_planes im2 = { im.w, im.h, { 0 } };
            int16_t *blk = malloc(3 * n * sizeof *blk); ASSERT(blk);
            for (int c = 0; c < 3; c++) {
                const int16_t *L = (const int16_t *)SCP->data + c * 4096;
                im2.p[c] = blk + (size_t)c * n;
                for (size_t i = 0; i < n; i++) {
                    int v = im.p[c][i];
                    im2.p[c][i] = L[v < 0 ? 0 : v > 4095 ? 4095 : v];
                }
            }
            enum greatest_test_res r = check_grid(&im2, G2);
            free(blk);
            if (r != GREATEST_TEST_RES_PASS) { pkc_analysis_image_free(&im); return r; }
        } else {
            ASSERT_EQ(NULL, G2);
        }
        pkc_analysis_image_free(&im);
        ASSERT_EQ(NULL, im.p[0]);
    }
    pkv_close(fs); pkv_close(f);
    PASS();
}
TEST roll_r4(void) { return roll("r4", "r4"); }
TEST roll_r1(void) { return roll("r1", "r4"); }
TEST roll_r12(void) { return roll("r12", "r4"); }
TEST roll_r2(void) { return roll("r2", "r2"); }

/* Kodak-resampled synthetic shapes (RE 19): 250x387 (dims round: 243 not 242) and a 400x300 landscape frame */
TEST synthetic_shapes(void) {
    pkv_file *f = pkv_open(PKV_DIR "/analysis_r4.pkv"); ASSERT(f);
    const pkv_array *LO = pkv_get(f, "f0_lo"); ASSERT(LO);
    ASSERT_EQ(380, LO->dims[1]); ASSERT_EQ(250, LO->dims[2]);
    const uint16_t *f0 = LO->data;
    for (int t = 0; t < 2; t++) {
        int w = t ? 400 : 250, h = t ? 300 : 387;
        uint16_t *blk = malloc((size_t)3 * w * h * 2); ASSERT(blk);
        const uint16_t *lo[3];
        for (int c = 0; c < 3; c++) {
            const uint16_t *src = f0 + (size_t)c * 380 * 250;
            uint16_t *d = blk + (size_t)c * w * h; lo[c] = d;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++) {
                    int sy = t ? y : (y < 380 ? y : 379 - (y - 380));          /* p387: rows 379..373 appended */
                    int sx = t ? (x < 250 ? x : 149 - (x - 250)) : x;          /* l400: cols 149..0 appended */
                    d[(size_t)y * w + x] = src[(size_t)sy * 250 + sx];
                }
        }
        const pkv_array *HW = pkv_get(f, t ? "syn_l400_hw" : "syn_p387_hw"),
                        *FNV = pkv_get(f, t ? "syn_l400_fnv" : "syn_p387_fnv");
        ASSERT(HW && FNV);
        pkc_planes im = { 0, 0, { 0 } };
        ASSERT_EQ(PK_OK, pkc_analysis_image(lo, w, h, &im));
        free(blk);
        ASSERT_EQ(((const int32_t *)HW->data)[0], im.h);
        ASSERT_EQ(((const int32_t *)HW->data)[1], im.w);
        ASSERT_EQ_FMT((unsigned long long)le64(FNV), (unsigned long long)fnv64(&im), "%llx");
        pkc_analysis_image_free(&im);
    }
    pkv_close(f);
    PASS();
}

TEST dims_rule(void) {
    static const int c[][4] = { {250, 380, 247, 376}, {250, 377, 249, 376}, {250, 387, 243, 376},
                                {400, 300, 376, 282}, {250, 376, 250, 376}, {250, 301, 250, 301},
                                {376, 376, 376, 376}, {377, 377, 376, 376}, {2, 752, 1, 376},
                                /* kill w*376.0/mx+0.5 (243x432: 212) and rint(w*s) (72x384: 70) */
                                {243, 432, 211, 376}, {432, 243, 376, 211}, {72, 384, 71, 376}, {384, 72, 376, 71} };
    for (size_t i = 0; i < sizeof c / sizeof c[0]; i++) {
        int ow = -1, oh = -1; pkc_analysis_dims(c[i][0], c[i][1], &ow, &oh);
        ASSERT_EQ(c[i][2], ow); ASSERT_EQ(c[i][3], oh);
    }
    PASS();
}

/* 2x752 -> 1x376: every output is the mean of a 2x2 block (fx = fy = 0.5), rounded half away from zero;
 * samples above 0x7fff are read as negative int16 (movswl) */
TEST rounding_and_sign(void) {
    enum { W = 2, H = 752 };
    static uint16_t pl[3][W * H];
    static const int16_t blocks[][5] = {          /* p00 p01 p10 p11 expected */
        {0, 1, 0, 0, 0}, {1, 1, 1, 0, 1}, {1, 0, 0, 1, 1}, {1, 0, 0, 0, 0}, {2, 1, 0, 0, 1},
        {-1, 0, 0, 0, 0}, {-1, -1, 0, 0, -1}, {-1, -1, -1, 0, -1}, {-3, -2, 0, 0, -1}, {4095, 4094, 4095, 4094, 4095} };
    const int nb = sizeof blocks / sizeof blocks[0];
    for (int c = 0; c < 3; c++)
        for (int j = 0; j < H / 2; j++) {
            const int16_t *b = blocks[j % nb];
            pl[c][(2 * j) * W] = (uint16_t)b[0]; pl[c][(2 * j) * W + 1] = (uint16_t)b[1];
            pl[c][(2 * j + 1) * W] = (uint16_t)b[2]; pl[c][(2 * j + 1) * W + 1] = (uint16_t)b[3];
        }
    const uint16_t *lo[3] = { pl[0], pl[1], pl[2] };
    pkc_planes im = { 0, 0, { 0 } };
    ASSERT_EQ(PK_OK, pkc_analysis_image(lo, W, H, &im));
    ASSERT_EQ(1, im.w); ASSERT_EQ(376, im.h);
    for (int c = 0; c < 3; c++)
        for (int j = 0; j < 376; j++) ASSERT_EQ_FMT((int)blocks[j % nb][4], (int)im.p[c][j], "%d");
    pkc_analysis_image_free(&im);
    PASS();
}

/* Interpolation order (x first, then y): a crafted 11x1000 frame whose first output sample is a tie that rounds
 * 699 x-first and 698 y-first. Kodak (PC53 oracle, lab/rollbal/jobs/rz_ax11.txt, docs/re/19) gives 699 and 0
 * everywhere else. */
TEST interpolation_order(void) {
    enum { W = 11, H = 1000 };
    static uint16_t pl[3][W * H];
    for (int c = 0; c < 3; c++) { pl[c][0] = 85; pl[c][1] = 3895; pl[c][W] = 732; pl[c][W + 1] = 56; }
    const uint16_t *lo[3] = { pl[0], pl[1], pl[2] };
    pkc_planes im = { 0, 0, { 0 } };
    ASSERT_EQ(PK_OK, pkc_analysis_image(lo, W, H, &im));
    ASSERT_EQ(4, im.w); ASSERT_EQ(376, im.h);
    for (int c = 0; c < 3; c++)
        for (int i = 0; i < 4 * 376; i++) ASSERT_EQ_FMT(i ? 0 : 699, (int)im.p[c][i], "%d");
    pkc_analysis_image_free(&im);
    PASS();
}

TEST copy_when_small_and_errors(void) {
    static uint16_t pl[3][40 * 30];
    for (int c = 0; c < 3; c++) for (int i = 0; i < 40 * 30; i++) pl[c][i] = (uint16_t)(i * 7 + c * 1000 + (c == 0 && i == 125 ? 32000 - 875 : 0));
    const uint16_t *lo[3] = { pl[0], pl[1], pl[2] };
    pkc_planes im = { 0, 0, { 0 } };
    ASSERT_EQ(PK_OK, pkc_analysis_image(lo, 40, 30, &im));        /* max <= 376: bit copy */
    ASSERT_EQ(40, im.w); ASSERT_EQ(30, im.h);
    for (int c = 0; c < 3; c++) ASSERT_EQ(0, memcmp(pl[c], im.p[c], sizeof pl[c]));
    int32_t g[3][PKC_GRID_N];
    ASSERT_EQ(PK_OK, pkc_grid24x36(&im, g));    /* 40x30: 1x1 blocks at row 3+i, col 2+j (margins 3, 2) */
    ASSERT_EQ(3 * 40 + 2, g[0][0] / 7);
    ASSERT_EQ(4095, g[0][3]);                    /* mean 0x7d00 at (3,5): still accepted, clamped to 0xfff */
    ASSERT_EQ((3 * 40 + 3) * 7 + 1000, g[1][1]);
    ASSERT_EQ(4095, g[2][PKC_GRID_N - 1]);       /* (26*40+37)*7+2000 = 9539 > 0xfff */
    im.p[0][125] = 32001;                        /* one block mean > 0x7d00: createAlgData's -0x9b */
    ASSERT_EQ(PK_E_ARG, pkc_grid24x36(&im, g));
    im.p[0][125] = (int16_t)(uint16_t)40000;     /* read unsigned (movzx): 40000 > 0x7d00, not negative */
    ASSERT_EQ(PK_E_ARG, pkc_grid24x36(&im, g));
    pkc_analysis_image_free(&im);
    pkc_analysis_image_free(&im);                                     /* idempotent */

    ASSERT_EQ(PK_E_ARG, pkc_analysis_image(NULL, 40, 30, &im));
    ASSERT_EQ(PK_E_ARG, pkc_analysis_image(lo, 40, 30, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_analysis_image(lo, 0, 30, &im));
    const uint16_t *lon[3] = { pl[0], NULL, pl[2] };
    ASSERT_EQ(PK_E_ARG, pkc_analysis_image(lon, 40, 30, &im));
    ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pkc_analysis_image(lo, 1, 1000, &im));   /* width would resample to 0 */
    ASSERT_EQ(NULL, im.p[0]);

    pkc_planes small = { 35, 30, { (int16_t *)pl[0], (int16_t *)pl[1], (int16_t *)pl[2] } };
    ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pkc_grid24x36(&small, g));
    small.w = 40; small.h = 23;
    ASSERT_EQ(PK_E_IMAGE_TOO_SMALL, pkc_grid24x36(&small, g));
    pkc_planes skew = { 1000, 24, { (int16_t *)pl[0], (int16_t *)pl[1], (int16_t *)pl[2] } };  /* blocks 27 rows tall */
    ASSERT_EQ(PK_E_UNSUPPORTED, pkc_grid24x36(&skew, g));   /* reads past the image: Kodak averages heap contents */
    {   /* 252 x 240 (t12's crafted frames): so = 10, si = 7, the last column's 7 x 10 block spans cols 245..254, i.e.
         * reads on into the next row, flat (row * w + col) as Kodak's fcn.1028cd10; Kodak-pinned end to end by
         * test_roll (synf / syns) */
        static int16_t wp[3][252 * 240];
        for (int c = 0; c < 3; c++) for (int i = 0; i < 252 * 240; i++) wp[c][i] = (int16_t)((i * 13 + c * 77) % 4000);
        pkc_planes wide = { 252, 240, { wp[0], wp[1], wp[2] } };
        ASSERT_EQ(PK_OK, pkc_grid24x36(&wide, g));
        for (int c = 0; c < 3; c++) {
            long long sum = 0;
            for (int y = 0; y < 7; y++) for (int x = 245; x < 255; x++) sum += wp[c][y * 252 + x];
            ASSERT_EQ(sum / 70, g[c][35]);
        }
    }
    ASSERT_EQ(PK_E_ARG, pkc_grid24x36(NULL, g));
    ASSERT_EQ(PK_E_ARG, pkc_grid24x36(&small, NULL));
    PASS();
}


/* Task 21: analyzePass1's splice crop (docs/re/19 "Splice crop"), vectors/splice.pkv (lab/rollbal/gen_t21splice.py):
 * Kodak's count of splice columns, first splice column, the width createAlgData then saw and its grid, for r2 frame 30's
 * analysis image (right splice), its mirror (left splice) and crafted frames pinning ratio == / > splicePct, the 90 %
 * row rule (338 of 376; 254 of 282, where the +0.5 counts), the > thr compare and the first column at exactly w * 0.5. thr = fpo R 879 + fog 1000 + 100. */
/* the crafted cases' images (lab/rollbal/gen_t21splice.py frames()): s1 = s0 mirrored; s2.. R / B 1000, G 600 + 3x, R columns */
static int16_t *splice_case(int k, const pkv_array *s0, int *w, int *hp) {
    const int h = k == 6 ? 282 : 376, w0 = s0->dims[2];
    *w = k < 2 ? w0 : k == 6 ? 376 : 200; *hp = h;
    int16_t *a = malloc(sizeof *a * 3 * (size_t)*w * h);
    if (!a) return NULL;
    const int16_t *b = (const int16_t *)s0->data;
    for (int c = 0; c < 3; c++)
        for (int y = 0; y < h; y++)
            for (int x = 0; x < *w; x++) {
                int16_t *o = &a[((size_t)c * h + y) * *w + x];
                if (k < 2) { *o = b[((size_t)c * h + y) * w0 + (k ? w0 - 1 - x : x)]; continue; }
                *o = (int16_t)(c == 1 ? (k == 6 ? 600 + 2 * x : 600 + 3 * x) : 1000);
                if (c) continue;
                if (k == 6 && ((x == 300 && y < 253) || (x == 301 && y < 254) || x >= 370)) *o = 3000;
                if ((k == 2 && x >= 90) || (k == 3 && x >= 89)) *o = 3000;
                if (k == 4 && ((x == 180 && y < 338) || x >= 195)) *o = 1980;
                if (k == 4 && x == 181) *o = 1979;
                if (k == 4 && x == 182 && y < 337) *o = 4000;
                if (k == 5 && x == 100) *o = 3000;
            }
    return a;
}

TEST splice_crop(void) {
    pkv_file *f = pkv_open(PKV_DIR "/splice.pkv"); ASSERT(f);
    const int n = *(const int32_t *)pkv_get(f, "n")->data;
    const pkv_array *S0 = pkv_get(f, "s0_img");
    ASSERT_EQ(7, n); ASSERT(S0 && S0->ndim == 3 && S0->dims[1] == 376);
    for (int k = 0; k < n; k++) {
        char nm[64];
        snprintf(nm, sizeof nm, "s%d_res", k); const int32_t *res = (const int32_t *)pkv_get(f, nm)->data;
        snprintf(nm, sizeof nm, "s%d_grid", k); const pkv_array *G = pkv_get(f, nm);
        int w, h; int16_t *a = splice_case(k, S0, &w, &h);
        ASSERT(a && G);
        pkc_planes im = { w, h, { a, a + (size_t)w * h, a + (size_t)2 * w * h } };
        pkc_planes crop; pkc_splice sp;
        pk_status st = pkc_splice_crop(&im, 879 + 1000 + 100, 55, &crop, &sp);
        const pkc_planes *g = sp.cropped ? &crop : &im;
        enum greatest_test_res r = st == PK_OK && sp.count == res[0] && sp.start == res[1] && g->w == res[2] &&
                                   sp.cropped == (res[2] != w) ? check_grid(g, G) : GREATEST_TEST_RES_FAIL;
        pkc_analysis_image_free(&crop); free(a);
        if (r != GREATEST_TEST_RES_PASS) { pkv_close(f); FAILm("splice case differs from Kodak"); }
    }
    /* no splice column: nothing allocated; bad args */
    int16_t flat[3 * 40 * 30];
    for (size_t i = 0; i < sizeof flat / sizeof flat[0]; i++) flat[i] = 1000;
    pkc_planes im = { 40, 30, { flat, flat + 1200, flat + 2400 } }, crop; pkc_splice sp;
    ASSERT_EQ(PK_OK, pkc_splice_crop(&im, 1979, 55, &crop, &sp));
    ASSERT(!sp.cropped && sp.count == 0 && sp.start == -1 && crop.p[0] == NULL);
    ASSERT_EQ(PK_E_ARG, pkc_splice_crop(NULL, 1979, 55, &crop, &sp));
    ASSERT_EQ(PK_E_ARG, pkc_splice_crop(&im, 1979, 55, NULL, &sp));
    pkv_close(f);
    PASS();
}

SUITE(analysis_image_suite) {
    RUN_TEST(roll_r4); RUN_TEST(roll_r1); RUN_TEST(roll_r12); RUN_TEST(roll_r2);
    RUN_TEST(synthetic_shapes); RUN_TEST(dims_rule); RUN_TEST(rounding_and_sign); RUN_TEST(interpolation_order);
    RUN_TEST(copy_when_small_and_errors); RUN_TEST(splice_crop);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); RUN_SUITE(analysis_image_suite); GREATEST_MAIN_END();
}
