#include "greatest.h"
#include "pkv.h"
#include "front.h"
#include <stdlib.h>

TEST density_lut_matches(void) {
    pkv_file *f = pkv_open(PKV_DIR "/front.pkv"); ASSERT(f);
    static uint16_t lut[16384]; pkc_density_lut(lut);
    ASSERT_EQ(16383, lut[0]);
    ASSERT_MEM_EQ(pkv_get(f, "lut")->data, lut, sizeof lut);
    pkv_close(f); PASS();
}
TEST poly_matches(void) {
    pkv_file *f = pkv_open(PKV_DIR "/front.pkv"); ASSERT(f);
    const pkv_array *L = pkv_get(f, "lin"), *R = pkv_get(f, "rpd"), *K = pkv_get(f, "k");
    ASSERT(L && R && K);
    size_t n = (size_t)L->dims[1]; const uint16_t *lin[3]; int16_t *out[3];
    for (int c = 0; c < 3; c++) { lin[c] = (const uint16_t *)L->data + c * n; out[c] = malloc(n * 2); }
    pkc_front((const float (*)[10])K->data, lin, out, n);
    for (int c = 0; c < 3; c++) {
        /* parenthesised: greatest casts EXP, so an unparenthesised sum would add bytes */
        ASSERT_MEM_EQ(((const int16_t *)R->data + c * n), out[c], n * 2);
        free(out[c]);
    }
    pkv_close(f); PASS();
}
SUITE(front_suite) { RUN_TEST(density_lut_matches); RUN_TEST(poly_matches); }
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); RUN_SUITE(front_suite); GREATEST_MAIN_END();
}
