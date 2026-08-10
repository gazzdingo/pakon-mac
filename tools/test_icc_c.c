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

    return 0;
}
