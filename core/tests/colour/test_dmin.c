/* Task 11: TLB film-base finder (RE 20) vs vectors/dmin.pkv (lab/vectors/gen_dmin.py: Kodak's FUN_10005ae0 run under
 * Unicorn), and the scene-dmin rule (RE 16/17) vs vectors/analysis_<roll>.pkv (lab/vectors/gen_analysis.py). */
#include "greatest.h"
#include "pkv.h"
#include "analysis/dmin.h"
#include <stdlib.h>
#include <string.h>

static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }

static enum greatest_test_res expect_dmin(const uint16_t *pl[3], int w, int rows, int dpi, const int32_t *exp) {
    uint16_t out[3] = { 0xBEEF, 0xBEEF, 0xBEEF };
    ASSERT_EQ(PK_OK, pkc_film_base(pl, w, rows, dpi, out));
    for (int c = 0; c < 3; c++) ASSERT_EQ_FMT(exp[c], (int32_t)out[c], "%d");
    PASS();
}

/* Real strip: only the finder's window is stored; every other sample is 0xFFFF (the generator ran Kodak on this
 * same filled strip), so a port reading outside the window fails with PK_E_ARG. */
static enum greatest_test_res real_roll(const char *name) {
    pkv_file *f = pkv_open(PKV_DIR "/dmin.pkv"); ASSERT(f);
    char nm[64];
    snprintf(nm, sizeof nm, "%s_meta", name); const pkv_array *M = pkv_get(f, nm);
    snprintf(nm, sizeof nm, "%s_win", name); const pkv_array *WN = pkv_get(f, nm);
    snprintf(nm, sizeof nm, "%s_out", name); const pkv_array *O = pkv_get(f, nm);
    int rows = M ? i32(M)[0] : 0, w = M ? i32(M)[1] : 0, dpi = M ? i32(M)[2] : 0, r0 = M ? i32(M)[3] : 0;
    int wr = WN ? WN->dims[1] : 0, wc = WN ? WN->dims[2] : 0, c0 = w >> 3;
    int ok = M && WN && O && dpi == PKC_DMIN_DPI_BASE && w == 250 && wc == (6 * w) >> 3 && WN->dtype == 3 &&
             r0 >= 0 && r0 + wr <= rows;
    uint16_t *buf = ok ? malloc((size_t)3 * rows * w * sizeof *buf) : NULL;
    if (!buf) { pkv_close(f); FAILm("dmin.pkv real-roll arrays missing/inconsistent, or no memory"); }
    for (size_t i = 0; i < (size_t)3 * rows * w; i++) buf[i] = 0xFFFF;
    const uint16_t *pl[3];
    for (int c = 0; c < 3; c++) {
        uint16_t *p = buf + (size_t)c * rows * w;
        const uint16_t *src = (const uint16_t *)WN->data + (size_t)c * wr * wc;
        for (int r = 0; r < wr; r++) memcpy(p + (size_t)(r0 + r) * w + c0, src + (size_t)r * wc, (size_t)wc * 2);
        pl[c] = p;
    }
    enum greatest_test_res res = expect_dmin(pl, w, rows, dpi, i32(O));
    free(buf); pkv_close(f);
    return res;
}
TEST real_r4(void) { return real_roll("r4"); }
TEST real_r2(void) { return real_roll("r2"); }

/* Crafted strips: noise (both window-length branches), window-boundary markers per plane (stagger, first/last row,
 * columns, odd e), the 0x3fff rule and strict '>' of the walk, the walk ending at bin 0, the size guard. */
TEST crafted(void) {
    pkv_file *f = pkv_open(PKV_DIR "/dmin.pkv"); ASSERT(f);
    const pkv_array *N = pkv_get(f, "syn_n"); ASSERT(N);
    int skips = 0;
    for (int k = 0; k < i32(N)[0]; k++) {
        char nm[64];
        snprintf(nm, sizeof nm, "s%d_planes", k); const pkv_array *P = pkv_get(f, nm);
        snprintf(nm, sizeof nm, "s%d_meta", k); const pkv_array *M = pkv_get(f, nm);
        snprintf(nm, sizeof nm, "s%d_out", k); const pkv_array *O = pkv_get(f, nm);
        if (!(P && M && O)) { pkv_close(f); FAILm("dmin.pkv crafted arrays missing"); }
        int rows = P->dims[1], w = P->dims[2];
        const uint16_t *pl[3];
        for (int c = 0; c < 3; c++) pl[c] = (const uint16_t *)P->data + (size_t)c * rows * w;
        skips += i32(M)[1];
        int zero = !i32(M)[1] || (i32(O)[0] == 0 && i32(O)[1] == 0 && i32(O)[2] == 0);
        enum greatest_test_res r = zero ? expect_dmin(pl, w, rows, i32(M)[0], i32(O)) : GREATEST_TEST_RES_FAIL;
        if (r != GREATEST_TEST_RES_PASS) {
            static char msg[64]; snprintf(msg, sizeof msg, "crafted strip s%d differs from Kodak", k);
            pkv_close(f); FAILm(msg);
        }
    }
    pkv_close(f);
    ASSERT_EQ(2, skips);                 /* s6 (guard edge) and s9 (e beyond the strip) */
    PASS();
}

TEST film_base_errors(void) {
    enum { W = 16, ROWS = 700 };
    static uint16_t buf[3][ROWS * W];
    for (int c = 0; c < 3; c++) for (int i = 0; i < ROWS * W; i++) buf[c][i] = (uint16_t)(i % 16384);
    const uint16_t *pl[3] = { buf[0], buf[1], buf[2] };
    uint16_t out[3];
    ASSERT_EQ(PK_OK, pkc_film_base(pl, W, ROWS, PKC_DMIN_DPI_BASE, out));
    ASSERT_EQ(PK_E_ARG, pkc_film_base(NULL, W, ROWS, PKC_DMIN_DPI_BASE, out));
    ASSERT_EQ(PK_E_ARG, pkc_film_base(pl, W, ROWS, PKC_DMIN_DPI_BASE, NULL));
    const uint16_t *pn[3] = { buf[0], NULL, buf[2] };
    ASSERT_EQ(PK_E_ARG, pkc_film_base(pn, W, ROWS, PKC_DMIN_DPI_BASE, out));
    ASSERT_EQ(PK_E_ARG, pkc_film_base(pl, 0, ROWS, PKC_DMIN_DPI_BASE, out));
    ASSERT_EQ(PK_E_ARG, pkc_film_base(pl, W, -1, PKC_DMIN_DPI_BASE, out));
    ASSERT_EQ(PK_E_ARG, pkc_film_base(pl, W, ROWS, 0, out));
    /* rows 0..2: R = 0, guard skips -> zeros */
    for (int rows = 0; rows <= 2; rows++) {
        out[0] = out[1] = out[2] = 7;
        ASSERT_EQ(PK_OK, pkc_film_base(pl, W, rows, PKC_DMIN_DPI_BASE, out));
        ASSERT(out[0] == 0 && out[1] == 0 && out[2] == 0);
    }
    /* a sample > 16383 inside plane 1's window (e = 17, start 8: plane 1 rows 9.., cols 2..13) is rejected;
     * the same value outside every window is not read */
    buf[1][9 * W + 2] = 16384;
    ASSERT_EQ(PK_E_ARG, pkc_film_base(pl, W, ROWS, PKC_DMIN_DPI_BASE, out));
    buf[1][9 * W + 2] = 0;
    buf[1][8 * W + 2] = 0xFFFF; buf[1][9 * W + 1] = 0xFFFF; buf[0][9 * W + 2] = 0xFFFF;
    ASSERT_EQ(PK_OK, pkc_film_base(pl, W, ROWS, PKC_DMIN_DPI_BASE, out));
    PASS();
}

/* ---- scene dmin. The vectors' scene_dmin (pass 1: ctx_dmin, grid) and scene_dmin2 (pass 2 of FOS rolls: ctx2_dmin,
 * grid2) were asserted equal to Kodak's sba+0x3bc8 at PC53 when generated; ctx_dmin is Kodak's own film base (RE 20). */
typedef struct { int skipped, ctx_wins, grid_wins; } sd_stats;
static enum greatest_test_res scene_pass(const pkv_file *f, int k, const char *ctxname, const char *gname,
                                         const char *sdname, sd_stats *st) {
    static const int lim[3] = { 180, 550, 700 };
    char nm[32];
    const pkv_array *CTX = pkv_get(f, ctxname);
    snprintf(nm, sizeof nm, "s%d_%s", k, gname); const pkv_array *G = pkv_get(f, nm);
    snprintf(nm, sizeof nm, "s%d_%s", k, sdname); const pkv_array *SD = pkv_get(f, nm);
    ASSERT(CTX && G && SD);
    uint16_t ctx[3];
    for (int c = 0; c < 3; c++) ctx[c] = (uint16_t)i32(CTX)[c];
    int32_t (*g)[PKC_GRID_N] = malloc(sizeof(int32_t[3][PKC_GRID_N])); ASSERT(g);
    for (int c = 0; c < 3; c++) {
        int32_t plain = 0x7fff;
        for (int i = 0; i < PKC_GRID_N; i++) {
            g[c][i] = ((const int16_t *)G->data)[c * PKC_GRID_N + i];
            if (g[c][i] < plain) plain = g[c][i];
        }
        if (plain <= lim[c] && i32(SD)[c] > plain) st->skipped++;    /* the floor skipped the band's minimum */
        if (i32(SD)[c] == ctx[c] && ctx[c] < plain) st->ctx_wins++;
        if (i32(SD)[c] != ctx[c]) st->grid_wins++;
    }
    uint16_t out[3];
    pkc_scene_dmin(ctx, (const int32_t (*)[PKC_GRID_N])g, out);
    free(g);
    for (int c = 0; c < 3; c++) ASSERT_EQ_FMT(i32(SD)[c], (int32_t)out[c], "%d");
    PASS();
}
static enum greatest_test_res scene_roll(const char *name, sd_stats *st) {
    char p[512]; snprintf(p, sizeof p, PKV_DIR "/analysis_%s.pkv", name);
    pkv_file *f = pkv_open(p); ASSERT(f);
    const pkv_array *SF = pkv_get(f, "scan_frames"), *FV = pkv_get(f, "fos_valid");
    if (!(SF && FV)) { pkv_close(f); FAILm("analysis vectors lack scan_frames/fos_valid"); }
    for (int k = 0; k < (int)SF->n; k++) {
        enum greatest_test_res r = scene_pass(f, k, "ctx_dmin", "grid", "scene_dmin", st);
        if (r == GREATEST_TEST_RES_PASS && i32(FV)[0]) r = scene_pass(f, k, "ctx2_dmin", "grid2", "scene_dmin2", st);
        if (r != GREATEST_TEST_RES_PASS) { pkv_close(f); return r; }
    }
    pkv_close(f);
    PASS();
}
TEST scene_dmin_vectors(void) {
    sd_stats r4 = { 0, 0, 0 }, r2 = { 0, 0, 0 }, other = { 0, 0, 0 };
    CHECK_CALL(scene_roll("r4", &r4));
    CHECK_CALL(scene_roll("r1", &other));
    CHECK_CALL(scene_roll("r12", &other));
    CHECK_CALL(scene_roll("r2", &r2));
    ASSERT(r2.skipped > 0);              /* RE 17: r2 band B min 647 <= 700 is skipped (Kodak 701) */
    ASSERT(r4.ctx_wins > 0 && r2.ctx_wins > 0 && other.ctx_wins > 0);   /* Kodak's film base below the grid min */
    ASSERT(r4.grid_wins > 0 && r2.grid_wins > 0);
    PASS();
}

static void fill(int32_t g[3][PKC_GRID_N], int32_t v) {
    for (int c = 0; c < 3; c++) for (int i = 0; i < PKC_GRID_N; i++) g[c][i] = v;
}
/* Hand cases for the limits 180/550/700 (sba+0x4d58, read from Kodak at the sceneDmin bp: gen_analysis asserts them),
 * at and one above the limit for every channel, for both ctx and grid cells; and the 0x7d00 seed. */
TEST scene_dmin_rules(void) {
    static int32_t g[3][PKC_GRID_N];
    static const int lim[3] = { 180, 550, 700 };
    const int32_t (*cg)[PKC_GRID_N] = (const int32_t (*)[PKC_GRID_N])g;
    uint16_t out[3];
    /* ctx: at the limit -> 4095 (grid 3000 wins), one above -> kept */
    fill(g, 3000);
    uint16_t at[3] = { 180, 550, 700 }, above[3] = { 181, 551, 701 };
    pkc_scene_dmin(at, cg, out);
    for (int c = 0; c < 3; c++) ASSERT_EQ(3000, out[c]);
    pkc_scene_dmin(above, cg, out);
    for (int c = 0; c < 3; c++) ASSERT_EQ(lim[c] + 1, out[c]);
    /* grid: a cell at the limit is skipped, a cell one above counts (ctx 4000 everywhere) */
    uint16_t big[3] = { 4000, 4000, 4000 };
    for (int c = 0; c < 3; c++) g[c][5 + c] = lim[c];
    pkc_scene_dmin(big, cg, out);
    for (int c = 0; c < 3; c++) ASSERT_EQ(3000, out[c]);
    for (int c = 0; c < 3; c++) g[c][100 + c] = lim[c] + 1;
    pkc_scene_dmin(big, cg, out);
    for (int c = 0; c < 3; c++) ASSERT_EQ(lim[c] + 1, out[c]);
    /* no cell above the limit: gridMin stays at its 0x7d00 seed, so d wins; 4095 when ctx is at/below the limit */
    fill(g, 100);
    for (int c = 0; c < 3; c++) g[c][7] = lim[c];
    uint16_t lo[3] = { 50, 500, 650 };
    pkc_scene_dmin(lo, cg, out);
    for (int c = 0; c < 3; c++) ASSERT_EQ(4095, out[c]);
    uint16_t hi[3] = { 5000, 32000, 32001 };       /* the seed is exactly 0x7d00 = 32000 */
    pkc_scene_dmin(hi, cg, out);
    ASSERT_EQ(5000, out[0]); ASSERT_EQ(32000, out[1]); ASSERT_EQ(32000, out[2]);
    /* Kodak compares ctx as int16: 0x8000.. is negative -> <= limit -> 4095; 0x7FFF is capped by the seed */
    fill(g, 3000);
    uint16_t neg[3] = { 0x8000, 0xFFFF, 0x7FFF };
    pkc_scene_dmin(neg, cg, out);
    ASSERT_EQ(3000, out[0]); ASSERT_EQ(3000, out[1]); ASSERT_EQ(3000, out[2]);
    fill(g, 100);
    pkc_scene_dmin(neg, cg, out);
    ASSERT_EQ(4095, out[0]); ASSERT_EQ(4095, out[1]); ASSERT_EQ(32000, out[2]);
    PASS();
}

SUITE(dmin_suite) {
    RUN_TEST(real_r4); RUN_TEST(real_r2); RUN_TEST(crafted); RUN_TEST(film_base_errors);
    RUN_TEST(scene_dmin_vectors); RUN_TEST(scene_dmin_rules);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); RUN_SUITE(dmin_suite); GREATEST_MAIN_END();
}
