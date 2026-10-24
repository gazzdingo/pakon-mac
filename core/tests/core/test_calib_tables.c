/* core_calib_tables (Task 15 step 2, Kodak-match): pkcal_derive_tables against TLB's own table builder (FUN_1001e4a0 +
 * FUN_1001f550 under Unicorn, lab/vectors/gen_calib_golden.py). Why it is kept: a silent error in the dark/gain arithmetic corrupts
 * the colour of every scan and cannot be seen on hardware until pictures are wrong. */
#include "greatest.h"
#include "pkv.h"
#include "pakon/calib.h"
#include "calib/calib.h"
static pkv_file *G;
TEST derived_tables_equal_tlb_bit_for_bit(void) {
    const pkv_array *ds = pkv_get(G, "dark_sum"), *bs = pkv_get(G, "bright_sum"), *np = pkv_get(G, "n_px"), *op = pkv_get(G, "ob_px"),
                    *td = pkv_get(G, "tlb_dark"), *tg = pkv_get(G, "tlb_gain"), *ts = pkv_get(G, "tlb_smearc");
    ASSERT(ds && bs && np && op && td && tg && ts);
    int n_px = ((const int32_t *)np->data)[0], ob = ((const int32_t *)op->data)[0];
    pk_cal_tables t; ASSERT_EQ(PK_OK, pkcal_derive_tables(ds->data, bs->data, 128, n_px, 3, ob, &t));
    for (int c = 0; c < 3; c++) {
        ASSERT_MEM_EQ(((const uint16_t *)td->data + c * n_px), t.dark[c], (size_t)n_px * 2);   /* parenthesised: greatest casts EXP to bytes */
        ASSERT_MEM_EQ(((const uint32_t *)tg->data + c * n_px), t.gain[c], (size_t)n_px * 4);
        ASSERT_EQ(((const uint16_t *)ts->data)[c], t.smearc[c]);
    }
    pkcal_tables_free(&t);
    PASS();
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); G = pkv_open(PKV_DIR "/calib_golden.pkv"); if (!G) { fprintf(stderr, "calib_golden.pkv missing\n"); return 1; }
    RUN_TEST(derived_tables_equal_tlb_bit_for_bit);
    pkv_close(G); GREATEST_MAIN_END();
}
