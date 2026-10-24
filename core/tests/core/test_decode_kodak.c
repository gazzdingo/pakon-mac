/* core_decode_kodak: pkd_kernel_line against Kodak's scan-line kernel FUN_100246d0 (TLB.dll under Unicorn, lab/vectors/gen_kernel.py, RE 30).
 * Byte-equal on every line of every case: the planar output and the mean4 state after each line. Task 17 adds the lo-res strip, row profile, stored
 * row count and registered read-out (lab/vectors/gen_lores.py, lores.pkv): byte-equal to Kodak's strip, profile and read-out. */
#include "greatest.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pkv.h"
#include "decode/kernel.h"
#include "decode/lores_weights.h"
#include "pakon/vendor.h"
#include "decode/strip.h"
#include "util/util.h"
static pkv_file *V, *VL;
static const char *CASES[] = { "gold400_rgb", "roll_rgb", "base4_rgb", "crafted_rgb", "crafted_ir_rgbreal", "crafted_ir", "crafted_ir_xtalk",
                               "crafted_ir_xtalk255", "crafted_ir_xtalk_r6", "crafted_ir_xtalk_r4", "crafted_ir_xtalk1" };
static size_t lines_total;
#define K(sfx) (snprintf(k, sizeof k, "%s." sfx, name), k)
TEST kernel_case(const char *name) {
    char k[96];
    const pkv_array *CF = pkv_get(V, K("cfg")), *DK = pkv_get(V, K("dark")), *SC = pkv_get(V, K("smearc")), *RW = pkv_get(V, K("raw")),
                    *OU = pkv_get(V, K("out")), *WM = pkv_get(V, K("mean4")), *MI = pkv_get(V, K("mean4_init")), *GN = pkv_get(V, K("gain"));
    const pkv_array *sm = pkv_get(V, K("smear"));      /* absent in the RGB cases */
    ASSERT(CF && DK && SC && RW && OU && WM && MI && GN);
    ASSERT(CF->n == 5 && CF->dtype == 4);
    const int32_t *cfg = CF->data;
    const int n_px = cfg[0], ch = cfg[1], nl = cfg[3], ratio = cfg[4];
    const uint16_t *dark = DK->data, *smearc = SC->data, *raw = RW->data, *want = OU->data, *wm = WM->data;
    ASSERT(nl > 0 && n_px > 0 && (ch == 3 || ch == 4));
    ASSERT(DK->n == (size_t)ch * n_px && GN->n == (size_t)ch * n_px && SC->n == 3 && MI->n == 3);
    ASSERT(RW->n == (size_t)nl * ch * n_px && OU->n == RW->n && WM->n == (size_t)nl * 3);
    ASSERT(!sm || sm->n == (size_t)3 * n_px);
    const uint32_t *gain = GN->data;                   /* stored as i32 bit patterns */
    pk_cal_tables t; memset(&t, 0, sizeof t); t.n_px = n_px;
    for (int c = 0; c < ch; c++) { t.dark[c] = (uint16_t *)dark + (size_t)c * n_px; t.gain[c] = (uint32_t *)gain + (size_t)c * n_px; }
    for (int c = 0; c < 3; c++) { t.smearc[c] = smearc[c]; if (sm) t.smear[c] = (uint16_t *)sm->data + (size_t)c * n_px; }
    pkd_kernel_cfg kc = { n_px, ch, ratio, &t, (unsigned)cfg[2] };
    pkd_kernel_state st; pkd_kernel_init(&st); memcpy(st.mean4, MI->data, 6);
    uint16_t *out = malloc((size_t)ch * n_px * 2);
    ASSERT(out);
    for (int l = 0; l < nl; l++) {
        ASSERT_EQ(PK_OK, pkd_kernel_line(&kc, &st, raw + (size_t)l * ch * n_px, out));
        /* parenthesised: the macro casts EXP before any + */
        ASSERT_MEM_EQ((want + (size_t)l * ch * n_px), out, (size_t)ch * n_px * 2);
        ASSERT_MEM_EQ((wm + 3 * l), st.mean4, 6);
        lines_total++;
    }
    free(out); PASS();
}
static const char *LORES_CASES[] = { "r4", "r6", "r8", "crafted_const", "crafted_step", "crafted_partial", "crafted_filmstart", "crafted_stale_prof", "crafted_sat" };
static size_t strip_rows_total, readout_ok, readout_bad;
/* The crafted cases carry the hi-res lines; the real cases carry their SHA-256 (hires_sha, 96 lines at 55% of the capture, not the lines kernel.pkv holds). */
TEST lores_case(const char *name) {
    char k[96];
    const pkv_array *CF = pkv_get(VL, K("cfg")), *DK = pkv_get(VL, K("dark")), *SC = pkv_get(VL, K("smearc")), *RW = pkv_get(VL, K("raw")),
                    *GN = pkv_get(VL, K("gain")), *RO = pkv_get(VL, K("rows")), *ST = pkv_get(VL, K("strip")), *PR = pkv_get(VL, K("profile")),
                    *FS = pkv_get(VL, K("film_start"));
    const pkv_array *HI = pkv_get(VL, K("hires")), *HS = pkv_get(VL, K("hires_sha")), *PI = pkv_get(VL, K("prof_init"));      /* hires absent in the real cases */
    ASSERT(HI || HS); ASSERT(PI && PI->n == 3);
    ASSERT(CF && DK && SC && RW && GN && RO && ST && PR && FS);
    const int32_t *cfg = CF->data;
    const int n_px = cfg[0], ratio = cfg[1], nl = cfg[3], w = cfg[4], film_start = ((const int32_t *)FS->data)[0];
    const uint16_t *dark = DK->data, *smearc = SC->data, *raw = RW->data;
    const uint32_t *gain = GN->data;
    const int want_rows = ((const int32_t *)RO->data)[0];
    ASSERT(w * ratio == n_px && RW->n == (size_t)nl * 3 * n_px && ST->n == (size_t)3 * want_rows * w && PR->n == (size_t)want_rows * 3);
    pk_cal_tables t; memset(&t, 0, sizeof t); t.n_px = n_px;
    for (int c = 0; c < 3; c++) { t.dark[c] = (uint16_t *)dark + (size_t)c * n_px; t.gain[c] = (uint32_t *)gain + (size_t)c * n_px; t.smearc[c] = smearc[c]; }
    pkd_kernel_cfg kc = { n_px, 3, ratio, &t, 0 };
    pkd_kernel_state st; pkd_kernel_init(&st);
    pkd_strip *s; ASSERT_EQ(PK_OK, pkd_strip_new(ratio, w, (size_t)nl, &s));
    uint32_t roll_sums[3];                                /* S-R41: the roll-lifetime profile sums, stale from a previous strip (prof_init) */
    for (int c = 0; c < 3; c++) roll_sums[c] = (uint32_t)((const int32_t *)PI->data)[c];
    pkd_strip_share_profile_sums(s, roll_sums);
    uint16_t *hi = malloc((size_t)3 * n_px * 2); ASSERT(hi);
    for (int l = 0; l < nl; l++) {
        pkd_strip_set_film(s, l >= film_start);
        ASSERT_EQ(PK_OK, pkd_strip_feed(s, &kc, &st, raw + (size_t)l * 3 * n_px, hi));
        if (HI) ASSERT_MEM_EQ(((const uint16_t *)HI->data + (size_t)l * 3 * n_px), hi, (size_t)3 * n_px * 2);
        else { uint8_t dg[32]; pku_sha256 sh; pku_sha256_init(&sh); pku_sha256_update(&sh, hi, (size_t)3 * n_px * 2); pku_sha256_final(&sh, dg);
               ASSERT_MEM_EQ(((const uint8_t *)HS->data + (size_t)l * 32), dg, 32); }      /* little-endian host */
    }
    ASSERT_EQ(PK_OK, pkd_strip_finish(s)); ASSERT_EQ(want_rows, s->rows);
    const uint16_t *want = ST->data;
    for (int c = 0; c < 3; c++) ASSERT_MEM_EQ((want + (size_t)c * want_rows * w), s->plane[c], (size_t)want_rows * w * 2);
    ASSERT_MEM_EQ(PR->data, s->profile, (size_t)want_rows * 3);
    strip_rows_total += (size_t)want_rows;
    free(hi); pkd_strip_free(s); PASS();
}
/* More film lines than the window the strip was allocated for: finish refuses, leaves rows alone, and the lo-res read never passes the allocation. */
TEST strip_window_guard(void) {
    enum { NP = 8 };
    uint16_t dark[NP] = {0}; uint32_t gain[NP]; uint16_t raw[3 * NP] = {0}, hi[3 * NP];
    for (int i = 0; i < NP; i++) gain[i] = 0x10000;
    pk_cal_tables t; memset(&t, 0, sizeof t); t.n_px = NP;
    for (int c = 0; c < 3; c++) { t.dark[c] = dark; t.gain[c] = gain; }
    pkd_kernel_cfg kc = { NP, 3, 4, &t, 0 }; pkd_kernel_state st; pkd_kernel_init(&st);
    pkd_strip *s; ASSERT_EQ(PK_OK, pkd_strip_new(4, NP / 4, 8, &s));
    for (int l = 0; l < 16; l++) { pk_status r = pkd_strip_feed(s, &kc, &st, raw, hi); ASSERT(r == PK_OK || r == PK_E_ARG); }
    const int before = s->rows;
    ASSERT_EQ(PK_E_ARG, pkd_strip_finish(s)); ASSERT_EQ(before, s->rows);
    uint16_t o[3][4]; uint16_t *op[3] = { o[0], o[1], o[2] };
    ASSERT_EQ(PK_OK, pkd_strip_read_lores(s, 0, 2, op));
    s->rows = s->alloc_rows;                            /* a strip whose declared rows leave no room for the 2 zero rows */
    ASSERT_EQ(PK_E_ARG, pkd_strip_read_lores(s, 0, 2, op));
    pkd_strip_free(s); PASS();
}
TEST registered_readout_equals_tlb(void) {
    const pkv_array *RC = pkv_get(VL, "ro_count"); ASSERT(RC);
    const int n = ((const int32_t *)RC->data)[0];
    for (int i = 0; i < n; i++) {
        char k[64]; snprintf(k, sizeof k, "ro%d.stored", i); const pkv_array *S = pkv_get(VL, k); ASSERT(S);
        const int P = S->dims[0], R = S->dims[1], W = S->dims[2];
        snprintf(k, sizeof k, "ro%d.params", i); const pkv_array *PA = pkv_get(VL, k); ASSERT(PA); const int32_t *p = PA->data;
        const int extra = p[4]; const size_t rows = (size_t)p[2];
        /* TLB's allocation holds `extra` zero rows after the stored ones (lo-res: 2): copy the stored rows into a zero-padded block */
        const size_t pr = (size_t)(R + extra) * W;
        uint16_t *pad = calloc((size_t)P * pr, 2); ASSERT(pad);
        const uint16_t *planes[4]; uint16_t *outp[4] = {0};
        for (int c = 0; c < P; c++) { memcpy(pad + c * pr, (const uint16_t *)S->data + (size_t)c * R * W, (size_t)R * W * 2); planes[c] = pad + c * pr; }
        for (int c = 0; c < P; c++) outp[c] = calloc(rows ? rows * W : 1, 2);
        ASSERT_EQ((pk_status)p[3], pkd_readout_planes(planes, P, (size_t)(R + extra), W, 0, W, p[0], (size_t)p[1], rows, outp));
        if (p[3] == PK_OK) {
            snprintf(k, sizeof k, "ro%d.out", i); const pkv_array *OW = pkv_get(VL, k); ASSERT(OW);
            const uint16_t *want = OW->data;
            for (int c = 0; c < P; c++) ASSERT_MEM_EQ((want + (size_t)c * rows * W), outp[c], rows * W * 2);
            readout_ok++;
        } else readout_bad++;
        for (int c = 0; c < P; c++) free(outp[c]);
        free(pad);
    }
    PASS();
}
/* The closed forms against Kodak's tables: stored rows (FUN_10005660), readable rows (FUN_10005590), the weights (read from the DLL). */
TEST tables_equal_tlb(void) {
    const pkv_array *RT = pkv_get(VL, "rows_table"), *DT = pkv_get(VL, "readable_table");
    ASSERT(RT && DT && RT->n % 3 == 0 && RT->n > 0);
    for (size_t i = 0; i < RT->n / 3; i++) {
        const int32_t *e = (const int32_t *)RT->data + 3 * i;
        ASSERT_EQ(e[2], (int)pkd_strip_rows_for(e[0], (size_t)e[1]));
    }
    for (size_t i = 0; i < DT->n / 3; i++) { const int32_t *e = (const int32_t *)DT->data + 3 * i; ASSERT_EQ(e[2], (int)pkd_strip_readable_rows((size_t)e[1], e[0])); }
    const pkv_array *W4 = pkv_get(VL, "weights4"), *W6 = pkv_get(VL, "weights6"), *W8 = pkv_get(VL, "weights8");
    ASSERT(W4 && W6 && W8);
    for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) ASSERT_EQ(((const int32_t *)W4->data)[i * 4 + j], pkd_lores_row(4, i)[j]);
    for (int i = 0; i < 6; i++) for (int j = 0; j < 6; j++) ASSERT_EQ(((const int32_t *)W6->data)[i * 6 + j], pkd_lores_row(6, i)[j]);
    for (int i = 0; i < 8; i++) for (int j = 0; j < 8; j++) ASSERT_EQ(((const int32_t *)W8->data)[i * 8 + j], pkd_lores_row(8, i)[j]);
    PASS();
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    if (pk_lores_weights_load(NULL, DERIVED_ROOT) != PK_OK) { fprintf(stderr, "SKIP: lo-res weights not available (vendor/derived)\n"); return 77; }
    V = pkv_open(PKV_DIR "/kernel.pkv");
    if (!V) { fprintf(stderr, "kernel.pkv missing\n"); return 1; }
    for (size_t i = 0; i < sizeof CASES / sizeof CASES[0]; i++) RUN_TEST1(kernel_case, CASES[i]);
    printf("decode Kodak match: %zu lines byte-equal over %zu cases\n", lines_total, sizeof CASES / sizeof CASES[0]);
    VL = pkv_open(PKV_DIR "/lores.pkv");
    if (!VL) { fprintf(stderr, "lores.pkv missing\n"); return 1; }
    for (size_t i = 0; i < sizeof LORES_CASES / sizeof LORES_CASES[0]; i++) RUN_TEST1(lores_case, LORES_CASES[i]);
    RUN_TEST(strip_window_guard);
    RUN_TEST(registered_readout_equals_tlb);
    RUN_TEST(tables_equal_tlb);
    printf("decode Kodak match (lo-res): %zu cases, %zu strip rows with profile, %zu read-outs byte-equal (+%zu bounds refusals)\n",
           sizeof LORES_CASES / sizeof LORES_CASES[0], strip_rows_total, readout_ok, readout_bad);
    pkv_close(VL); pkv_close(V);
    GREATEST_MAIN_END();
}
