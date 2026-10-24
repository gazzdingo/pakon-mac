/* core_eeprom_header_kodak (S-R10): pkcal_eeprom_validate against TLB's own FUN_10016A90 (run under Unicorn by
 * lab/vectors/gen_eeprom_header.py). Why it is kept: a wrong length bound or CRC rule would silently misclassify the
 * irreplaceable calibration copies at the single HW-1 read and change which image becomes current. Each case isolates one
 * copy (its partner invalid), so TLB's acceptance is that copy's validity. */
#include "greatest.h"
#include "pkv.h"
#include "calib/eeprom.h"
#include <stdint.h>
#include <string.h>

TEST header_matches_tlb(void) {
    pkv_file *f = pkv_open(PKV_DIR "/eeprom_header.pkv");
    ASSERT(f);
    const pkv_array *im = pkv_get(f, "images"), *pa = pkv_get(f, "params"), *acc = pkv_get(f, "tlb_accept");
    const pkv_array *cw = pkv_get(f, "tlb_cw"), *cwn = pkv_get(f, "tlb_cw_n"), *ad = pkv_get(f, "tlb_adj"), *adn = pkv_get(f, "tlb_adj_n");
    ASSERT(im && pa && acc && cw && cwn && ad && adn);
    int n = im->dims[0];
    ASSERT_EQ(PKCAL_EEPROM_SIZE, (unsigned)im->dims[1]);
    ASSERT(n >= 100);
    const uint8_t *img = (const uint8_t *)im->data;
    const int32_t *par = (const int32_t *)pa->data, *ac = (const int32_t *)acc->data, *cn = (const int32_t *)cwn->data,
                  *an = (const int32_t *)adn->data;
    const pkv_array *ov = pkv_get(f, "tlb_overrun");
    ASSERT(ov);
    const int32_t *ovr = (const int32_t *)ov->data;
    int accepted = 0;
    for (int i = 0; i < n; i++) {
        int copy = par[4 * i], length = par[4 * i + 1], good = par[4 * i + 2];
        int ok[PKCAL_NCOPIES];
        ASSERT_EQ(PK_OK, pkcal_eeprom_validate(img + (size_t)i * PKCAL_EEPROM_SIZE, ok));
        if (ok[copy] != ac[i]) {
            printf("case %d: copy %d length 0x%X crc %s: TLB accepts %d, we say %d\n", i, copy, length, good ? "good" : "bad", ac[i], ok[copy]);
            FAIL();
        }
        /* length 1..7 is not a Kodak verdict: TLB's header test passes and it then reads ~4 GiB into a 1 KB stack buffer
         * (the generator marks the overrun and records "not accepted"); ours refuses 0..7. Assert that exact set. */
        ASSERT_EQ(length >= 1 && length <= 7, ovr[i] != 0);
        accepted += ac[i];
        if (ac[i]) {   /* the bytes TLB hands on equal ours */
            uint8_t b[PKCAL_CALWIZ_STRUCT];
            size_t got = pkcal_eeprom_copy(img + (size_t)i * PKCAL_EEPROM_SIZE, copy, b, sizeof b);
            const uint8_t *tb = copy < 2 ? (const uint8_t *)cw->data + (size_t)i * PKCAL_CALWIZ_STRUCT : (const uint8_t *)ad->data + (size_t)i * PKCAL_ADJUST_STRUCT;
            size_t tn = (size_t)(copy < 2 ? cn[i] : an[i]);
            ASSERT_EQ(tn, got);
            ASSERT_EQ(0, memcmp(b, tb, tn));
        }
    }
    ASSERT(accepted > 0);
    pkv_close(f);
    PASS();
}

SUITE(eeprom_header_suite) { RUN_TEST(header_matches_tlb); }
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(eeprom_header_suite);
    GREATEST_MAIN_END();
}
