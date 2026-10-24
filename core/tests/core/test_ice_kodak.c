/* core_ice_kodak: pk_ice_apply against Kodak's DMLDICEProcess (DMLDICELib.dll under the Wine oracle, lab/vectors/gen_ice_golden.py,
 * RE 44 sec. 9). Why it is kept: the 88 per-pixel routines, the statistics and the seam order are one long chain of float32 spill
 * points, and one wrong association changes a pixel by one code with no visible failure. All 42 vectors: narrow and wide families,
 * custom ROIs, tiny frames, the step-4 statistics frame, real RGB. Every output plane is compared byte for byte, and m, c0, A, B
 * (the f32 bits Kodak keeps in its object). */
#include "greatest.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pkv.h"
#include "pakon/ice.h"
#include "ice/ice_internal.h"
#include "util/util.h"
static pkv_file *V;
/* C9: the tables are computed at start-up from the RE 44 sec. 2.2 formulas (tables.c). They must equal the Wine oracle's dump of the
 * DMLDICELib object (lab/ice/gen_tables.py): SHA-256 of log[0..16383] as float32, then Ahi and Blo as int64, little endian. */
TEST computed_tables_equal_the_kodak_dump(void) {
    static const char want[] = "a60962a0b7c3b3c75ba8f2cf39bb71c0d2cf52416ea7b259ac63e5238a0208ff";
    pki_tables_init();
    uint8_t *b = malloc(16384 * 4 + 512 * 8);
    ASSERT(b);
    memcpy(b, pki_log, 16384 * 4);
    memcpy(b + 16384 * 4, pki_ahi, 256 * 8);
    memcpy(b + 16384 * 4 + 256 * 8, pki_alo, 256 * 8);
    char hex[65];
    pku_sha256_hex(b, 16384 * 4 + 512 * 8, hex);
    free(b);
    ASSERT_STR_EQ(want, hex);
    for (int i = 16384; i < 65536; i++) ASSERT_EQ(0.0f, pki_log[i]);
    PASS();
}
TEST every_vector_equals_kodak_bit_for_bit(void) {
    const pkv_array *names = pkv_get(V, "names");
    ASSERT(names);
    int nvec = pkv_list_count(V, "names"), identical = 0;
    ASSERT_EQ(42, nvec);
    for (int i = 0; i < nvec; i++) {
        char key[32];
        snprintf(key, sizeof key, "%02d_meta", i);  const pkv_array *meta = pkv_get(V, key);
        snprintf(key, sizeof key, "%02d_in", i);    const pkv_array *in = pkv_get(V, key);
        snprintf(key, sizeof key, "%02d_idx", i);   const pkv_array *idx = pkv_get(V, key);
        snprintf(key, sizeof key, "%02d_val", i);   const pkv_array *val = pkv_get(V, key);
        snprintf(key, sizeof key, "%02d_stats", i); const pkv_array *st = pkv_get(V, key);
        ASSERT(meta && in && idx && val && st);
        const int32_t *mt = meta->data;
        const int w = mt[0], h = mt[1];
        const size_t n = (size_t)w * h, ni = idx->n;
        uint16_t *got = malloc(4 * n * 2), *want = malloc(4 * n * 2);
        ASSERT(got && want);
        memcpy(got, in->data, 4 * n * 2);
        memcpy(want, in->data, 4 * n * 2);
        for (size_t j = 0; j < ni; j++)
            for (int p = 0; p < 4; p++) want[p * n + ((const int32_t *)idx->data)[j]] = ((const uint16_t *)val->data)[4 * j + p];
        pk_ice_opts o; memset(&o, 0, sizeof o);
        o.bits = 14; o.dpi = 300; o.neg = mt[2]; o.roi = mt[3]; o.x0 = mt[4]; o.y0 = mt[5]; o.x1 = mt[6]; o.y1 = mt[7];
        pk_ice_stats ps;
        pk_status rc = pk_ice_apply(got, got + n, got + 2 * n, got + 3 * n, w, h, (size_t)w, &o, &ps);
        int same = rc == PK_OK && memcmp(got, want, 4 * n * 2) == 0;
        const float *kst = st->data;
        const float mine[4] = { ps.m, ps.c0, ps.A, ps.B };
        same = same && memcmp(mine, kst, sizeof mine) == 0;
        if (!same) {
            size_t bad = 0;
            for (size_t j = 0; j < 4 * n; j++) bad += got[j] != want[j];
            fprintf(stderr, "vector %02d %dx%d differs: rc=%d, %zu samples, stats Kodak m=%a c0=%a A=%a B=%a mine m=%a c0=%a A=%a B=%a\n",
                    i, w, h, (int)rc, bad, kst[0], kst[1], kst[2], kst[3], mine[0], mine[1], mine[2], mine[3]);
        } else identical++;
        free(got); free(want);
    }
    printf("ice Kodak match: %d of %d vectors identical\n", identical, nvec);
    ASSERT_EQ(nvec, identical);
    PASS();
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); if (!pk_ice_available()) { fprintf(stderr, "SKIP: built without Digital ICE (PK_WITH_ICE=OFF)\n"); return 77; }
    V = pkv_open(PKV_DIR "/ice_golden.pkv"); if (!V) { fprintf(stderr, "ice_golden.pkv missing\n"); return 1; }
    RUN_TEST(computed_tables_equal_the_kodak_dump);
    RUN_TEST(every_vector_equals_kodak_bit_for_bit);
    pkv_close(V); GREATEST_MAIN_END();
}
