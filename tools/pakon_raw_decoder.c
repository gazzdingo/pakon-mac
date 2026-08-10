/*
 * pakon_raw_decoder.c — Pure C Pakon F-135 EP 0x86 raw capture decoder.
 *
 * Cite: TLB.dll @ 0x1002f550 (acquisition worker line sync search @ 0x1002ff12)
 *       TLB.dll @ 0x100246d0 (stage 0 sensor correction)
 *       TLB.dll @ 0x1000d880 (stage 2 3x10 polynomial)
 *       PakonIMAu.dll @ 0x1028c780 (Preference mode 0x11)
 *       PakonIMAu.dll @ 0x10100a37 (setShifts)
 *       PakonIMAu.dll @ 0x1019a0c0 (applyBalanceShifts)
 *       PakonIMAu.dll @ 0x10293ee0 (Shasta ToneLUT builder)
 *       PakonIMAu.dll @ 0x1014dcc0 (Shasta apply)
 *       PakonIMAu.dll @ 0x101f82c0 (FUGC setLutInfo + apply)
 *       docs/58-colour-pipeline.md §1-10
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#include "pakon_color_c.c"
#include "pakon_shasta_c.c"
#include "pakon_icc_c.c"

#define PREF_PIVOT 1000
#define SCALE_0_001 0.001
#define SQRT_2_OVER_3 0.816496580927726
#define ONE_THIRD 0.3333333333333333
#define INV_SQRT3_P 0.5773502691896258
#define INV_SQRT6_P 0.4082482904638631
#define INV_SQRT2_P 0.7071067811865475

static inline int pref_ftol2(double x) {
    if (!isfinite(x)) return INT_MIN;
    return (int)trunc(x);
}

static void pref_rgb_to_yuv(double r, double g, double b, double *y, double *u, double *v) {
    *y = (r + g + b) * INV_SQRT3_P;
    *u = (2.0 * g - r - b) * INV_SQRT6_P;
    *v = (b - r) * INV_SQRT2_P;
}

static void pref_yuv_to_rgb(double y, double u, double v, double *r, double *g, double *b) {
    double ys = y * INV_SQRT3_P;
    double us = u * INV_SQRT6_P;
    double vs = v * INV_SQRT2_P;
    *r = ys - us - vs;
    *g = ys + u * SQRT_2_OVER_3;
    *b = ys - us + vs;
}

static void pref_helper(double r, double g, double b, double *m, double *o1, double *o2) {
    *m  = (r + g + b) * SCALE_0_001 * ONE_THIRD;
    *o1 = (g * SCALE_0_001 - *m) * INV_SQRT2_P;
    *o2 = (b * SCALE_0_001 - r * SCALE_0_001) * INV_SQRT6_P;
}

static double pref_clamp_s(double t, double lim46, double lo42, double hi44) {
    double s = lim46 - t;
    if (s < lo42) return lo42;
    if (s > hi44) return hi44;
    return s;
}

static void preference_mode11_shifts(
    const int fpo[3], const int fpa[3],
    double lim46, double lo42, double hi44,
    const int neu[3], const int neo[3],
    int non_flash_adj,
    int16_t shifts_out[3])
{
    double op_y, op_u, op_v;
    pref_rgb_to_yuv((double)fpo[0], (double)fpo[1], (double)fpo[2], &op_y, &op_u, &op_v);
    double fa_y, fa_u, fa_v;
    pref_rgb_to_yuv((double)fpa[0], (double)fpa[1], (double)fpa[2], &fa_y, &fa_u, &fa_v);

    double aim_y = op_y;
    double w1e   = 0.0;
    double d_y   = w1e + aim_y - op_y;

    const int *hrg = (d_y > 0.0) ? neo : neu;
    double m, o1, o2;
    pref_helper((double)hrg[0], (double)hrg[1], (double)hrg[2], &m, &o1, &o2);

    double scale = (double)non_flash_adj * SCALE_0_001;
    int i_dy = pref_ftol2(d_y);
    int i_du = 0;
    int i_dv = 0;

    double comb_y = op_y + fa_y + m * (double)i_dy;
    double comb_u = op_u + fa_u + scale * (double)i_du + o1 * (double)i_dy;
    double comb_v = op_v + fa_v + scale * (double)i_dv + o2 * (double)i_dy;

    double t = comb_y - w1e;
    double s_prime = pref_clamp_s(t, lim46, lo42, hi44);
    double sr, sg, sb;
    pref_yuv_to_rgb(s_prime, -comb_u, -comb_v, &sr, &sg, &sb);
    shifts_out[0] = (int16_t)pref_ftol2(sr);
    shifts_out[1] = (int16_t)pref_ftol2(sg);
    shifts_out[2] = (int16_t)pref_ftol2(sb);
}

static void setshifts_02(const int16_t a[3], const int16_t b[3], int16_t out[3]) {
    double ap[3], bp[3];
    for (int c = 0; c < 3; c++) {
        ap[c] = (double)(int16_t)(PREF_PIVOT - (int)a[c]);
        bp[c] = (double)(int16_t)(PREF_PIVOT - (int)b[c]);
    }
    double y, u_dummy, v_dummy, c1, c2, y_dummy;
    pref_rgb_to_yuv(ap[0], ap[1], ap[2], &y, &u_dummy, &v_dummy);
    pref_rgb_to_yuv(bp[0], bp[1], bp[2], &y_dummy, &c1, &c2);
    double rr, gg, bb;
    pref_yuv_to_rgb(y, c1, c2, &rr, &gg, &bb);
    out[0] = (int16_t)(PREF_PIVOT - pref_ftol2(rr));
    out[1] = (int16_t)(PREF_PIVOT - pref_ftol2(gg));
    out[2] = (int16_t)(PREF_PIVOT - pref_ftol2(bb));
}

static void apply_balance_shifts(int32_t *rpd, int num_pixels, const int16_t shifts[3]) {
    for (int i = 0; i < num_pixels; i++) {
        for (int c = 0; c < 3; c++) {
            int v = rpd[i*3+c] + (int)shifts[c];
            if (v < 0) v = 0;
            if (v > 4095) v = 4095;
            rpd[i*3+c] = v;
        }
    }
}

static void fugc_set_lut_info_chan(const int32_t *seed, int offset, int32_t *out, int n) {
    if (offset > n - 1) {
        for (int i = 0; i < n; i++) out[i] = i;
        return;
    }
    if (offset > 0)
        for (int i = 0; i < offset; i++) out[i] = offset;
    for (int i = offset < 0 ? 0 : offset; i < n; i++) {
        int src = i - offset;
        if (src < 0) src = 0;
        if (src >= n) src = n - 1;
        int v = (int)seed[src] + offset;
        if (v < 0) v = 0;
        if (v > n - 1) v = n - 1;
        out[i] = v;
    }
}

static void load_fugc_seed(const char *path, int32_t seed[4096][3], int atd[3]) {
    FILE *f = fopen(path, "r");
    if (!f) return;
    char line[256];
    int code, r, g, b;
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "aTableDmin", 10) == 0) {
            sscanf(line, "aTableDmin = %d %d %d", &atd[0], &atd[1], &atd[2]);
        } else if (sscanf(line, "%d %d %d %d", &code, &r, &g, &b) == 4) {
            if (code >= 0 && code < 4096) {
                seed[code][0] = r;
                seed[code][1] = g;
                seed[code][2] = b;
            }
        }
    }
    fclose(f);
}

static void estimate_frame_dmin(const int32_t *rpd, int num_pixels, int dmin_out[3]) {
    int thresh = (int)(num_pixels * 0.02);
    if (thresh < 1) thresh = 1;
    for (int c = 0; c < 3; c++) {
        int hist[4096] = {0};
        for (int i = 0; i < num_pixels; i++) {
            int v = rpd[i*3+c];
            if (v < 0) v = 0;
            if (v > 4095) v = 4095;
            hist[v]++;
        }
        int cum = 0, dmin = 0;
        for (int v = 0; v < 4096; v++) {
            cum += hist[v];
            if (cum >= thresh) { dmin = v; break; }
        }
        dmin_out[c] = dmin;
    }
}

static void fugc_apply(int32_t *rpd, int num_pixels,
                       const int32_t seed_rgb[][3],
                       const int a_table_dmin[3],
                       const int16_t setshifts_out[3],
                       const int frame_dmin[3],
                       const int afilm_aim_dmin[3])
{
    int use_ebp18 = 1;
    for (int c = 0; c < 3; c++) {
        double a = (double)frame_dmin[c];
        double p = (double)afilm_aim_dmin[c];
        if (!(0.2 * p <= a && a <= 2.0 * p)) { use_ebp18 = 0; break; }
    }
    int w60ec[3], w60f2[3], w60f8[3];
    for (int c = 0; c < 3; c++) {
        w60f8[c] = a_table_dmin[c];
        w60f2[c] = (int)setshifts_out[c];
        w60ec[c] = use_ebp18 ? frame_dmin[c] : afilm_aim_dmin[c];
    }
    static int32_t apply_lut[4096];
    for (int c = 0; c < 3; c++) {
        int16_t off = (int16_t)((int16_t)w60ec[c] - (int16_t)w60f8[c] + (int16_t)w60f2[c]);
        int32_t seed_chan[4096];
        for (int i = 0; i < 4096; i++) seed_chan[i] = seed_rgb[i][c];
        fugc_set_lut_info_chan(seed_chan, (int)off, apply_lut, 4096);
        for (int i = 0; i < num_pixels; i++) {
            int code = rpd[i*3+c];
            if (code < 0) code = 0;
            if (code > 4095) code = 4095;
            rpd[i*3+c] = apply_lut[code];
        }
    }
}

static void write_bmp_rgb24(const char *path, const uint8_t *rgb, int width, int height) {
    FILE *f = fopen(path, "wb");
    if (!f) return;

    int row_bytes = (width * 3 + 3) & ~3;
    uint32_t image_size = (uint32_t)row_bytes * (uint32_t)height;
    uint32_t file_size = 54 + image_size;

    uint8_t header[54] = {
        'B','M',
        file_size & 0xFF, (file_size >> 8) & 0xFF, (file_size >> 16) & 0xFF, (file_size >> 24) & 0xFF,
        0, 0, 0, 0,
        54, 0, 0, 0,
        40, 0, 0, 0,
        width & 0xFF, (width >> 8) & 0xFF, (width >> 16) & 0xFF, (width >> 24) & 0xFF,
        height & 0xFF, (height >> 8) & 0xFF, (height >> 16) & 0xFF, (height >> 24) & 0xFF,
        1, 0, 24, 0,
        0, 0, 0, 0,
        image_size & 0xFF, (image_size >> 8) & 0xFF, (image_size >> 16) & 0xFF, (image_size >> 24) & 0xFF,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    };

    fwrite(header, 1, 54, f);

    uint8_t *row_buf = (uint8_t *)calloc(1, row_bytes);
    for (int y = height - 1; y >= 0; y--) {
        const uint8_t *src_row = rgb + (size_t)y * (size_t)width * 3;
        for (int x = 0; x < width; x++) {
            row_buf[x * 3 + 0] = src_row[x * 3 + 2]; /* Blue */
            row_buf[x * 3 + 1] = src_row[x * 3 + 1]; /* Green */
            row_buf[x * 3 + 2] = src_row[x * 3 + 0]; /* Red */
        }
        fwrite(row_buf, 1, row_bytes, f);
    }
    free(row_buf);
    fclose(f);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <raw.bin> <output.bmp>\n", argv[0]);
        return 1;
    }

    const char *raw_path = argv[1];
    const char *out_path = argv[2];
    FILE *f_in = fopen(raw_path, "rb");
    if (!f_in) {
        perror("fopen raw");
        return 1;
    }
    fseek(f_in, 0, SEEK_END);
    long file_size = ftell(f_in);
    fseek(f_in, 0, SEEK_SET);

    size_t total_words = file_size / sizeof(uint16_t);
    uint16_t *raw_buf = malloc((size_t)file_size);
    fread(raw_buf, sizeof(uint16_t), total_words, f_in);
    fclose(f_in);

    /*
     * The raw USB EP 0x86 stream has a line stride of 6000 words (2000 pixels).
     * Lines 0..2123 contain mostly 0xFFFE padding (firmware idle pattern).
     * Line 2124 onwards contain a full 6000 valid words of interleaved BGR data.
     */
    int width = 2000;
    int line_stride = 6000;
    int padding_lines = 2124;
    int total_lines = (int)(total_words / line_stride);
    int height = total_lines - padding_lines;

    printf("  Geometry: %d width x %d height (%d total RGB pixels)\n", width, height, width * height);

    size_t num_pixels = (size_t)width * (size_t)height;
    uint16_t *active_raw = malloc(num_pixels * 3 * sizeof(uint16_t));
    int32_t  *rpd_buf    = (int32_t  *)malloc(num_pixels * 3 * sizeof(int32_t));
    uint8_t  *srgb_buf   = (uint8_t  *)malloc(num_pixels * 3 * sizeof(uint8_t));

    if (!active_raw || !rpd_buf || !srgb_buf) {
        fprintf(stderr, "OOM\n"); return 1;
    }

    /* Extract the active image area, skipping the padding lines */
    for (int y = 0; y < height; y++) {
        const uint16_t *pkt = raw_buf + (size_t)(y + padding_lines) * line_stride;
        uint16_t *dst = active_raw + (size_t)y * (size_t)width * 3;
        for (int i = 0; i < width * 3; i++) {
            /* Stage 0 sensor correction: default gain is Q16 0x4000 = raw / 4 */
            dst[i] = (pkt[i] & 0xFFFE) >> 2;
        }
    }
    free(raw_buf); raw_buf = NULL;

    const char *eeprom_path = "backups/eeprom-i2c/eeprom_52.bin";
    float coeffs_f135[30] = {0};
    FILE *ef = fopen(eeprom_path, "rb");
    if (ef) {
        fseek(ef, 0x25, SEEK_SET);
        fread(coeffs_f135, sizeof(float), 30, ef);
        fclose(ef);
        printf("[setup] Loaded EEPROM 3x10 polynomial coefficients\n");
    }

    long long sr = 0, sg = 0, sb = 0;
    for (size_t i = 0; i < num_pixels; i++) {
        sb += active_raw[i*3+0];
        sg += active_raw[i*3+1];
        sr += active_raw[i*3+2];
    }
    printf("[0] active_raw mean: B=%lld G=%lld R=%lld\n", sb/num_pixels, sg/num_pixels, sr/num_pixels);

    printf("[0] active_raw mean: B=%lld G=%lld R=%lld\n", sb/num_pixels, sg/num_pixels, sr/num_pixels);

    const char *perm = (argc > 3) ? argv[3] : "rgb";
    printf("[1/5] Stage-2 polynomial correction (%s)...\n", perm);
    if (strcmp(perm, "rgb") == 0) pakon_poly_rgb_hwc_c(active_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    else if (strcmp(perm, "rbg") == 0) pakon_poly_rbg_hwc_c(active_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    else if (strcmp(perm, "grb") == 0) pakon_poly_grb_hwc_c(active_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    else if (strcmp(perm, "gbr") == 0) pakon_poly_gbr_hwc_c(active_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    else if (strcmp(perm, "brg") == 0) pakon_poly_brg_hwc_c(active_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    else if (strcmp(perm, "bgr") == 0) pakon_poly_bgr_hwc_c(active_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    else pakon_poly_rgb_hwc_c(active_raw, rpd_buf, (int)num_pixels, coeffs_f135, 1);
    free(active_raw); active_raw = NULL;

    /* Debug RPD stats after Stage 2 */
    long long sum_r = 0, sum_g = 0, sum_b = 0;
    int min_r = 9999, max_r = -1;
    for (size_t i = 0; i < num_pixels; i++) {
        int r = rpd_buf[i*3+0], g = rpd_buf[i*3+1], b = rpd_buf[i*3+2];
        sum_r += r; sum_g += g; sum_b += b;
        if (r < min_r) min_r = r; if (r > max_r) max_r = r;
    }
    printf("  RPD post-stage2: R_mean=%.1f G_mean=%.1f B_mean=%.1f\n",
           (double)sum_r/num_pixels, (double)sum_g/num_pixels, (double)sum_b/num_pixels);

    const char *sba_dpi_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/sba/SbaDPI/sba-CN-default.dpi";
    int sba_fpo[3] = {879, 1250, 1386}, sba_fpa[3] = {-70, -55, -45};
    int sba_neu[3] = {975, 975, 975}, sba_neo[3] = {1010, 1010, 1010};
    int sba_non_flash_adj = 25, sba_neutral_button = 130, sba_nbp = 1550;
    double sba_neutral_under = -16.0, sba_neutral_over = 16.0;

    double lim46 = round((double)sba_nbp * sqrt(3.0));
    double lo42  = round((double)sba_neutral_button * sba_neutral_under);
    double hi44  = round((double)sba_neutral_button * sba_neutral_over);

    int16_t pref_shifts[3], ss_out[3];
    preference_mode11_shifts(sba_fpo, sba_fpa, lim46, lo42, hi44,
                              sba_neu, sba_neo, sba_non_flash_adj,
                              pref_shifts);
    setshifts_02(pref_shifts, pref_shifts, ss_out);

    printf("[2/5] SBA balance shifts: R=%d G=%d B=%d\n", ss_out[0], ss_out[1], ss_out[2]);
    apply_balance_shifts(rpd_buf, (int)num_pixels, ss_out);

    sum_r = 0; sum_g = 0; sum_b = 0;
    for (size_t i = 0; i < num_pixels; i++) {
        sum_r += rpd_buf[i*3+0]; sum_g += rpd_buf[i*3+1]; sum_b += rpd_buf[i*3+2];
    }
    printf("  RPD post-stage4a: R_mean=%.1f G_mean=%.1f B_mean=%.1f\n",
           (double)sum_r/num_pixels, (double)sum_g/num_pixels, (double)sum_b/num_pixels);

    printf("[3/5] Shasta ToneLUT analyze & apply...\n");
    ShastaDpi shasta_dpi;
    shasta_dpi_defaults(&shasta_dpi);
    int32_t tone_lut[4096];
    shasta_build_tone_lut(rpd_buf, (int)num_pixels, &shasta_dpi, ss_out, tone_lut);
    printf("  Shasta ToneLUT[2000]=%d, ToneLUT[3000]=%d\n", tone_lut[2000], tone_lut[3000]);
    shasta_apply_tone_lut(rpd_buf, (int)num_pixels, tone_lut);

    sum_r = 0; sum_g = 0; sum_b = 0;
    for (size_t i = 0; i < num_pixels; i++) {
        sum_r += rpd_buf[i*3+0]; sum_g += rpd_buf[i*3+1]; sum_b += rpd_buf[i*3+2];
    }
    printf("  RPD post-stage4b: R_mean=%.1f G_mean=%.1f B_mean=%.1f\n",
           (double)sum_r/num_pixels, (double)sum_g/num_pixels, (double)sum_b/num_pixels);

    printf("[4/5] FUGC LUT apply...\n");
    const char *fugc_lut_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/fugc/NoShift_fugc-generic0225.lut";
    static int32_t fugc_seed[4096][3];
    int fugc_atd[3] = {500, 500, 500};
    load_fugc_seed(fugc_lut_path, fugc_seed, fugc_atd);
    int frame_dmin[3], afilm_aim_dmin[3] = {500, 1000, 1000};
    estimate_frame_dmin(rpd_buf, (int)num_pixels, frame_dmin);
    printf("  frame dmin estimate: R=%d G=%d B=%d\n", frame_dmin[0], frame_dmin[1], frame_dmin[2]);
    fugc_apply(rpd_buf, (int)num_pixels, (const int32_t (*)[3])fugc_seed,
               fugc_atd, ss_out, frame_dmin, afilm_aim_dmin);

    sum_r = 0; sum_g = 0; sum_b = 0;
    for (size_t i = 0; i < num_pixels; i++) {
        sum_r += rpd_buf[i*3+0]; sum_g += rpd_buf[i*3+1]; sum_b += rpd_buf[i*3+2];
    }
    printf("  RPD post-stage4c: R_mean=%.1f G_mean=%.1f B_mean=%.1f\n",
           (double)sum_r/num_pixels, (double)sum_g/num_pixels, (double)sum_b/num_pixels);

    printf("[5/5] ICC CLUT render (RPD 12-bit -> sRGB 8-bit)...\n");
    const char *rpd2pcs_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/profile/Rpd2Pcs_HR200_QS_v5s10.pf";
    const char *srgb_path = "/Users/guy/Downloads/Pakon Update 2/fx35install"
        "/program files/Pakon/F-X35 COM SERVER"
        "/anselinstalldir/dataPathItems/profile/Srgb_v2.pf";

    IccMft2 rpd2pcs, srgb_profile;
    if (icc_load_profile(rpd2pcs_path, &rpd2pcs) == 0 &&
        icc_load_profile_b2a0(srgb_path, &srgb_profile) == 0) {
        for (size_t i = 0; i < num_pixels; i++) {
            icc_rpd12_to_srgb8(&rpd2pcs, &srgb_profile, &rpd_buf[i*3], &srgb_buf[i*3]);
        }
        icc_mft2_free(&rpd2pcs);
        icc_mft2_free(&srgb_profile);
    }

    free(rpd_buf); rpd_buf = NULL;

    printf("Writing output BMP %dx%d to %s...\n", width, height, out_path);
    write_bmp_rgb24(out_path, srgb_buf, width, height);
    
    long long sr_out = 0, sg_out = 0, sb_out = 0;
    for (size_t i = 0; i < num_pixels; i++) {
        sr_out += srgb_buf[i*3+0];
        sg_out += srgb_buf[i*3+1];
        sb_out += srgb_buf[i*3+2];
    }
    printf("  Final sRGB mean: R=%.1f G=%.1f B=%.1f\n", 
           (double)sr_out/num_pixels, (double)sg_out/num_pixels, (double)sb_out/num_pixels);
    
    free(srgb_buf);

    printf("=== Complete. %d lines processed. ===\n", height);
    return 0;
}
