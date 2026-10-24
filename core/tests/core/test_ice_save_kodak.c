/* core_ice_save_kodak: the Digital ICE SAVE composition against Kodak (docs/re/45 sec 4.4, ruling S-R45 d). The vector (lab/vectors/gen_ice_save_golden.py) is
 * Kodak's chain on three r4 frame crops with crafted IR planes: DMLDICELib's DMLDICEProcess (the real DLL under Wine), then TLB's LUT + 3x10 polynomial, then
 * PakonIMAu's scene balance, the default-geometry rotation and the colour adjustment, on a roll analysed from the un-ICE'd lo-res frames. The port renders the same
 * frames with pk_roll_input.ice set through pk_colour_render_saved (AnselOrientation 270, picture rotation 0) and every byte of the 8-bit result must equal Kodak's.
 * A second assertion keeps the vector honest: the same frames rendered with ICE off must differ from Kodak's output, i.e. the defects survive without ICE. */
#include "greatest.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pkv.h"
#include "pakon/colour.h"
#include "pakon/ice.h"

static pkv_file *V;

TEST ice_save_equals_kodak_byte_for_byte(void) {
    const pkv_array *strip = pkv_get(V, "strip"), *poly = pkv_get(V, "poly_neg"), *codes = pkv_get(V, "codes"), *fr = pkv_get(V, "frames"), *nf = pkv_get(V, "n_frames");
    ASSERT(strip && poly && codes && fr && nf && poly->n == 30 && codes->n == 2 && fr->n == 3);
    const int n = ((const int32_t *)nf->data)[0];
    pk_frame_linear *hires = calloc((size_t)n, sizeof *hires), *lores = calloc((size_t)n, sizeof *lores);
    ASSERT(hires && lores);
    for (int k = 0; k < n; k++) {
        char key[16];
        snprintf(key, sizeof key, "lo%d", k);
        const pkv_array *lo = pkv_get(V, key);
        ASSERT(lo && lo->ndim == 3 && lo->dims[0] == 3);
        const size_t np = (size_t)lo->dims[1] * lo->dims[2];
        lores[k].width = lo->dims[2]; lores[k].height = lo->dims[1];
        for (int c = 0; c < 3; c++) lores[k].linear14[c] = (const uint16_t *)lo->data + c * np;
        hires[k].width = 4000; hires[k].height = 4000;      /* the frames not saved here: only their size is read, and by nothing */
    }
    for (int i = 0; i < 3; i++) {
        const int k = ((const int32_t *)fr->data)[i];
        char key[16];
        snprintf(key, sizeof key, "hi%d", k);
        const pkv_array *hi = pkv_get(V, key);
        ASSERT(hi && hi->ndim == 3 && hi->dims[0] == 4);
        const size_t np = (size_t)hi->dims[1] * hi->dims[2];
        hires[k].width = hi->dims[2]; hires[k].height = hi->dims[1];
        for (int c = 0; c < 4; c++) hires[k].linear14[c] = (const uint16_t *)hi->data + c * np;      /* R, G, B and the IR plane */
    }
    pk_roll_input in;
    memset(&in, 0, sizeof in);
    in.n_frames = n; in.frames = hires; in.lores = lores;
    in.strip.width = strip->dims[2]; in.strip.height = strip->dims[1];
    for (int c = 0; c < 3; c++) in.strip.linear14[c] = (const uint16_t *)strip->data + (size_t)c * strip->dims[1] * strip->dims[2];
    memcpy(in.poly_neg, poly->data, sizeof in.poly_neg);
    in.product_code = ((const int32_t *)codes->data)[0]; in.gen_code = ((const int32_t *)codes->data)[1];

    pk_colour *c = NULL;
    ASSERT_EQ(PK_OK, pk_colour_open(VENDOR_ROOT "/F-X35 COM SERVER", DERIVED_ROOT, &c));
    pk_roll_result *res = NULL;
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &in, &res));
    int identical = 0;
    for (int i = 0; i < 3; i++) {
        const int k = ((const int32_t *)fr->data)[i];
        char key[16];
        snprintf(key, sizeof key, "out%d", k);
        const pkv_array *out = pkv_get(V, key);
        ASSERT(out && out->ndim == 3 && out->dims[0] == 3);
        const int ow = out->dims[2], oh = out->dims[1];
        const size_t n_out = (size_t)ow * oh;
        uint8_t *rgb = malloc(n_out * 3);
        ASSERT(rgb);
        pk_image_u8 im = { 0, 0, rgb };
        ASSERT_EQ(PK_OK, pk_colour_ice_check(&in, k, NULL, 0));
        in.ice = 1;
        pk_status st = pk_colour_render_saved(c, &in, res, k, NULL, PK_ANSEL_ORIENTATION_PSI, 0, &im);
        ASSERT_EQ(PK_OK, st);
        ASSERT_EQ(ow, im.width); ASSERT_EQ(oh, im.height);
        size_t bad = 0;
        const uint8_t *want = out->data;
        for (size_t j = 0; j < n_out; j++) for (int ch = 0; ch < 3; ch++) bad += rgb[3 * j + ch] != want[ch * n_out + j];
        in.ice = 0;
        ASSERT_EQ(PK_OK, pk_colour_render_saved(c, &in, res, k, NULL, PK_ANSEL_ORIENTATION_PSI, 0, &im));
        size_t without = 0;
        for (size_t j = 0; j < n_out; j++) for (int ch = 0; ch < 3; ch++) without += rgb[3 * j + ch] != want[ch * n_out + j];
        printf("frame %d %dx%d: ICE render differs from Kodak in %zu of %zu bytes; the same render without ICE in %zu\n", k, ow, oh, bad, 3 * n_out, without);
        if (bad == 0) identical++;
        ASSERT(without > 1000);                  /* the vector has teeth: the defects are visible without ICE */
        free(rgb);
    }
    pk_roll_result_free(res); pk_colour_close(c);
    free(hires); free(lores);
    ASSERT_EQ(3, identical);
    PASS();
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); if (!pk_ice_available()) { fprintf(stderr, "SKIP: built without Digital ICE (PK_WITH_ICE=OFF)\n"); return 77; }
    V = pkv_open(PKV_DIR "/ice_save_golden.pkv"); if (!V) { fprintf(stderr, "ice_save_golden.pkv missing\n"); return 1; }
    RUN_TEST(ice_save_equals_kodak_byte_for_byte);
    pkv_close(V); GREATEST_MAIN_END();
}
