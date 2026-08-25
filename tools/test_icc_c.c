#include <stdio.h>
#include <stdlib.h>
#include "pakon_icc_c.c"

int main() {
    const char *rpd2pcs_path = "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/profile/Rpd2Pcs_HR200_QS_v5s10.pf";
    const char *srgb_path = "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/profile/Srgb_v2.pf";

    IccMft2 rpd2pcs, srgb;
    if (icc_load_profile(rpd2pcs_path, &rpd2pcs) != 0 || icc_load_profile_b2a0(srgb_path, &srgb) != 0) {
        printf("Failed to load profiles\n");
        return 1;
    }

    int32_t rpd[3] = {741, 855, 709};
    uint8_t srgb_out[3] = {0};

    icc_rpd12_to_srgb8(&rpd2pcs, &srgb, rpd, srgb_out);
    printf("RPD (%d, %d, %d) -> sRGB (%d, %d, %d)\n", rpd[0], rpd[1], rpd[2], srgb_out[0], srgb_out[1], srgb_out[2]);

    int32_t rpd_black[3] = {4095, 4095, 4095};
    icc_rpd12_to_srgb8(&rpd2pcs, &srgb, rpd_black, srgb_out);
    printf("RPD (%d, %d, %d) -> sRGB (%d, %d, %d)\n", rpd_black[0], rpd_black[1], rpd_black[2], srgb_out[0], srgb_out[1], srgb_out[2]);
    
    int32_t rpd_white[3] = {0, 0, 0};
    icc_rpd12_to_srgb8(&rpd2pcs, &srgb, rpd_white, srgb_out);
    printf("RPD (%d, %d, %d) -> sRGB (%d, %d, %d)\n", rpd_white[0], rpd_white[1], rpd_white[2], srgb_out[0], srgb_out[1], srgb_out[2]);

    /* The two evaluators side by side. The trilinear one above is this file's
     * historical subject; the vendor's own (kodakcms.dll fcn.10018160, ported
     * in pakon_kcms_clut_c.c and bit-exact over all 16.7 M u8 triples per
     * tools/test_kcms_clut_ports.py) is what icc_render_rpd12_to_srgb8 now runs by
     * default. They are NOT the same transform — docs/74 §176. */
    printf("\n%-22s %-16s %-16s\n", "RPD 12-bit", "trilinear (old)", "vendor CLUT");
    int32_t cases[][3] = {
        {741, 855, 709}, {0, 0, 0}, {4095, 4095, 4095},
        {2048, 1000, 3000}, {512, 2500, 1800}, {3000, 3000, 3000},
    };
    for (size_t i = 0; i < sizeof(cases)/sizeof(cases[0]); i++) {
        uint8_t tri[3], ven[3];
        icc_rpd12_to_srgb8(&rpd2pcs, &srgb, cases[i], tri);
        kcms_rpd12_to_srgb8(cases[i], ven);
        printf("(%4d,%4d,%4d)         (%3d,%3d,%3d)    (%3d,%3d,%3d)%s\n",
               cases[i][0], cases[i][1], cases[i][2],
               tri[0], tri[1], tri[2], ven[0], ven[1], ven[2],
               (tri[0]==ven[0] && tri[1]==ven[1] && tri[2]==ven[2]) ? "" : "   <- differ");
    }

    return 0;
}
