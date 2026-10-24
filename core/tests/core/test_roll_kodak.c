/* core_roll_kodak: the hand-off of decode, framing and the colour library (plan Task 20). The strip, the frames and their lo-res crops that pk_roll_colour_input
 * hands to the colour library are byte-equal to the Unicorn composition of Kodak's own functions (lab/vectors/gen_roll_uc.py): FUN_100246d0 (kernel + lo-res strip) ->
 * FUN_100013b0 (registered read-out, hi-res d = ratio, lo-res d = 1) -> TLB's frame rectangles (FUN_100079c0) -> crop -> 180 degree turn of the lo-res frame.
 * Default: the imported r4 roll (tools/v1_import_roll.py); PK_ROLL_DIR / PK_ROLL_UC point at a real roll and its regenerated vector (HW-2). Exits 77 (skipped) when the roll
 * fixture is absent. Hi-res planes are compared by SHA-256 (C44); the strip and the lo-res crops in full. The crop_* cases are the read-out with a column offset and a stride
 * wider than the crop (Task 17 review): TLB's frame rectangles always start at column 0, so the roll's own crops never exercise it. */
#include "greatest.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pkv.h"
#include "pakon/roll.h"
#include "pakon/vendor.h"
#include "pakon/colour.h"
#include "util/util.h"
#include "decode/strip.h"
static pkv_file *U;
static const char *DIR;                  /* the roll directory of the variant being run */
/* default: the imported r4 roll; HW-2 points PK_ROLL_DIR (a roll directory) / PK_ROLL_UC at a real roll and its regenerated vector */
static pk_roll *open_gold(void) {
    char raw[512], cal[512];
    snprintf(raw, sizeof raw, "%s/roll.raw", DIR); snprintf(cal, sizeof cal, "%s/calstore", DIR);
    (void)pk_lores_weights_load(NULL, DERIVED_ROOT);
    pk_roll *r = NULL; return pk_roll_open(raw, cal, &r) ? NULL : r;
}
TEST colour_input_has_tlb_layout_and_equals_the_uc_composition(void) {
    pk_roll *r = open_gold(); ASSERT(r);
    pk_roll_input in; pk_roll_input_storage *keep; ASSERT_EQ(PK_OK, pk_roll_colour_input(r, 0, &in, &keep));
    const pkv_array *NF = pkv_get(U, "n_frames"), *SR = pkv_get(U, "strip_rows"), *SP = pkv_get(U, "strip"), *PC = pkv_get(U, "product_code"), *GC = pkv_get(U, "gen_code");
    ASSERT(NF && SR && SP && PC && GC);
    int nf = ((const int32_t *)NF->data)[0], rows = ((const int32_t *)SR->data)[0];
    ASSERT_EQ(nf, in.n_frames); ASSERT_EQ(250, in.strip.width); ASSERT_EQ(rows, in.strip.height);
    for (int c = 0; c < 3; c++) ASSERT_MEM_EQ(((const uint16_t *)SP->data + (size_t)c * rows * 250), in.strip.linear14[c], (size_t)rows * 250 * 2);   /* EXP parenthesised: the macro casts it to bytes before any + */
    for (int k = 0; k < nf && k < 3; k++) {
        char key[40]; snprintf(key, sizeof key, "frame%d.dims", k); const pkv_array *FD = pkv_get(U, key);
        snprintf(key, sizeof key, "frame%d.sha256", k); const pkv_array *FS = pkv_get(U, key);
        snprintf(key, sizeof key, "lores%d", k); const pkv_array *L = pkv_get(U, key); ASSERT(FD && FS && L);
        const int32_t *d = FD->data; ASSERT_EQ(3, d[0]); ASSERT_EQ(d[1], in.frames[k].height); ASSERT_EQ(d[2], in.frames[k].width);
        ASSERT_EQ(PK_OK, pk_roll_colour_frame(r, 0, k, &in, keep));          /* the hi-res planes are loaded on demand */
        for (int c = 0; c < 3; c++) {                                  /* hi-res planes are stored as SHA-256 (C44); still byte-exact */
            pku_sha256 h; uint8_t got[32]; pku_sha256_init(&h); pku_sha256_update(&h, in.frames[k].linear14[c], (size_t)d[1] * d[2] * 2); pku_sha256_final(&h, got);
            ASSERT_MEM_EQ(((const uint8_t *)FS->data + 32 * c), got, 32);
        }
        ASSERT_EQ(3, L->dims[0]); ASSERT_EQ(L->dims[1], in.lores[k].height); ASSERT_EQ(L->dims[2], in.lores[k].width);
        for (int c = 0; c < 3; c++) ASSERT_MEM_EQ(((const uint16_t *)L->data + (size_t)c * L->dims[1] * L->dims[2]), in.lores[k].linear14[c], (size_t)L->dims[1] * L->dims[2] * 2);
    }
    for (int k = 0; k < nf; k++) ASSERT(!in.frames[k].linear14[0] || k < 3);   /* frames beyond the three checked were never loaded */
    ASSERT_EQ(((const int32_t *)PC->data)[0], in.product_code); ASSERT_EQ(((const int32_t *)GC->data)[0], in.gen_code);
    pk_roll_input_storage_free(keep); pk_roll_close(r); PASS();
}
/* pkd_readout_planes with a column offset and a stride wider than the crop against FUN_100013b0 (the Task 17 review's open item; gen_roll_uc.py crop vectors). */
TEST readout_crops_with_a_column_offset_equal_tlb(void) {
    const pkv_array *CC = pkv_get(U, "crop_count"); ASSERT(CC);
    const int n = ((const int32_t *)CC->data)[0]; ASSERT(n > 0);
    for (int i = 0; i < n; i++) {
        char k[48]; snprintf(k, sizeof k, "crop%d.stored", i); const pkv_array *S = pkv_get(U, k); ASSERT(S);
        snprintf(k, sizeof k, "crop%d.params", i); const pkv_array *PA = pkv_get(U, k); ASSERT(PA); const int32_t *p = PA->data;
        snprintf(k, sizeof k, "crop%d.out", i); const pkv_array *O = pkv_get(U, k); ASSERT(O);
        const int P = S->dims[0], R = S->dims[1], W = S->dims[2], col = p[3], width = p[4]; const size_t rows = (size_t)p[2];
        ASSERT(col > 0 && width < W);
        const uint16_t *in[4]; uint16_t *out[4] = {0};
        for (int c = 0; c < P; c++) { in[c] = (const uint16_t *)S->data + (size_t)c * R * W; out[c] = calloc(rows * (size_t)width, 2); ASSERT(out[c]); }
        ASSERT_EQ((pk_status)p[5], pkd_readout_planes(in, P, (size_t)R, W, col, width, p[0], (size_t)p[1], rows, out));
        for (int c = 0; c < P; c++) { ASSERT_MEM_EQ(((const uint16_t *)O->data + (size_t)c * rows * width), out[c], rows * (size_t)width * 2); free(out[c]); }
    }
    PASS();
}
SUITE(variant) {
    RUN_TEST(colour_input_has_tlb_layout_and_equals_the_uc_composition);
    RUN_TEST(readout_crops_with_a_column_offset_equal_tlb);
}
GREATEST_MAIN_DEFS();
/* Two variants of the imported strip (fix round 1, S-R43): r4 (film detected at line 1448 of the segment, the kernel's block counter 0 mod 8) and r4b (film detected 3 lines later,
 * OFF the 8-line phase). The kernel starts at the segment's first synced line in both, as TLB's does. PK_ROLL_DIR / PK_ROLL_UC replace them with ONE real roll (HW-2). */
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    const char *envd = getenv("PK_ROLL_DIR"), *envu = getenv("PK_ROLL_UC");
    const char *dirs[2] = { envd ? envd : ROLLS_DIR "/r4", ROLLS_DIR "/r4b" }, *pkvs[2] = { envu ? envu : PKV_DIR "/roll_uc.pkv", PKV_DIR "/roll_uc_off.pkv" };
    int ran = 0;
    for (int v = 0; v < (envd ? 1 : 2); v++) {
        DIR = dirs[v]; U = pkv_open(pkvs[v]);
        if (!U) { fprintf(stderr, "%s missing\n", pkvs[v]); return 1; }
        pk_roll *probe = open_gold(); if (!probe) { fprintf(stderr, "roll fixture %s missing: skipped\n", DIR); if (v == 0) return 77; pkv_close(U); continue; } pk_roll_close(probe);
        RUN_SUITE(variant); ran++;
        pkv_close(U);
    }
    (void)ran;
    GREATEST_MAIN_END();
}
