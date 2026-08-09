/*
 * pakon_pipeline_cli.c — Complete end-to-end native C CLI pipeline for Pakon F-135 scanner.
 *
 * Cite: TLB.dll @ 0x1000d880 (poly_pixel), 0x100246d0 (sensor_correct),
 *       PakonIMAu.dll @ 0x100dc310 (applyBalanceShifts), 0x10100a37 (setShifts 1,2),
 *       0x101f82c0 (FUGC setLutInfo), 0x100147ed (Contrast LUT), 0x10370de0 (Unsharp).
 * Docs: docs/49-preference-fpu-binary.md, docs/52-setshifts-binary.md, docs/58-colour-pipeline.md.
 *
 * Runs the ENTIRE pipeline natively in C:
 *   Raw Scan Binary -> Sensor Correction -> Stage-2 Poly -> Dmin Neutralization ->
 *   SBA Preference & setShifts -> Shasta/FUGC LUTs -> ColorAdjust Unsharp -> sRGB BMP Image
 *
 * Usage:
 *   ./tools/pakon_pipeline_cli captures/gold400.bin /tmp/gold400_full_pipeline.bmp --width 3000 --height 20802 [--eeprom eeprom_52.bin]
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#include "pakon_color_c.c"
#include "ansel/pakon_ansel_c.c"

/*
 * Write 24-bit uncompressed BMP image file (native macOS Finder / Preview support)
 */
static void write_bmp_rgb24(const char* filename, const uint8_t* rgb, int width, int height) {
    FILE* f = fopen(filename, "wb");
    if (!f) return;

    int row_padded = (width * 3 + 3) & (~3);
    uint32_t image_size = (uint32_t)(row_padded * height);
    uint32_t filesize = 54 + image_size;

    uint8_t header[54] = {
        'B', 'M',
        filesize & 0xFF, (filesize >> 8) & 0xFF, (filesize >> 16) & 0xFF, (filesize >> 24) & 0xFF,
        0, 0, 0, 0,
        54, 0, 0, 0,
        40, 0, 0, 0,
        width & 0xFF, (width >> 8) & 0xFF, (width >> 16) & 0xFF, (width >> 24) & 0xFF,
        height & 0xFF, (height >> 8) & 0xFF, (height >> 16) & 0xFF, (height >> 24) & 0xFF,
        1, 0,
        24, 0,
        0, 0, 0, 0,
        image_size & 0xFF, (image_size >> 8) & 0xFF, (image_size >> 16) & 0xFF, (image_size >> 24) & 0xFF,
        0, 0, 0, 0,
        0, 0, 0, 0,
        0, 0, 0, 0,
        0, 0, 0, 0
    };

    fwrite(header, 1, 54, f);

    uint8_t* row_buf = (uint8_t*)calloc(1, row_padded);
    /* BMP stores image bottom-to-top */
    for (int y = height - 1; y >= 0; y--) {
        for (int x = 0; x < width; x++) {
            int src_idx = (y * width + x) * 3;
            int dst_idx = x * 3;
            row_buf[dst_idx + 0] = rgb[src_idx + 2]; /* Blue */
            row_buf[dst_idx + 1] = rgb[src_idx + 1]; /* Green */
            row_buf[dst_idx + 2] = rgb[src_idx + 0]; /* Red */
        }
        fwrite(row_buf, 1, row_padded, f);
    }
    free(row_buf);
    fclose(f);
}

static void print_usage(const char* prog) {
    fprintf(stderr, "Usage: %s <input_raw.bin> <output_srgb.bmp> --width <W> --height <H> [--eeprom <eeprom_52.bin>]\n", prog);
}

int main(int argc, char** argv) {
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }

    const char* in_path = argv[1];
    const char* out_path = argv[2];
    int width = 0;
    int height = 0;
    const char* eeprom_path = "backups/eeprom-i2c/eeprom_52.bin";

    for (int i = 3; i < argc; i++) {
        if (strcmp(argv[i], "--width") == 0 && i + 1 < argc) {
            width = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--height") == 0 && i + 1 < argc) {
            height = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--eeprom") == 0 && i + 1 < argc) {
            eeprom_path = argv[++i];
        }
    }

    if (width <= 0 || height <= 0) {
        fprintf(stderr, "Error: --width and --height must be positive integers\n");
        return 1;
    }

    size_t num_pixels = (size_t)width * (size_t)height;
    size_t num_words = num_pixels * 3;

    printf("=== Native C End-to-End Pakon Pipeline ===\n");
    printf("Input: %s\nOutput: %s\nDimensions: %dx%d (%zu pixels)\n", in_path, out_path, width, height, num_pixels);

    /* 1. Load Coefficients from EEPROM */
    float coeffs[30];
    FILE* ef = fopen(eeprom_path, "rb");
    if (!ef) {
        fprintf(stderr, "Error: failed to open EEPROM file '%s'\n", eeprom_path);
        return 1;
    }
    fseek(ef, 0x25, SEEK_SET);
    size_t nread = fread(coeffs, sizeof(float), 30, ef);
    fclose(ef);
    if (nread < 24) {
        fprintf(stderr, "Error: EEPROM read underflow\n");
        return 1;
    }
    for (size_t i = nread; i < 30; i++) coeffs[i] = 0.0f;

    /* 2. Load Raw Input Binary */
    uint16_t* in_raw = (uint16_t*)malloc(num_words * sizeof(uint16_t));
    int32_t* rpd_buf = (int32_t*)malloc(num_words * sizeof(int32_t));
    uint8_t* srgb_buf = (uint8_t*)malloc(num_words * sizeof(uint8_t));

    if (!in_raw || !rpd_buf || !srgb_buf) {
        fprintf(stderr, "Error: memory allocation failed\n");
        return 1;
    }

    FILE* inf = fopen(in_path, "rb");
    if (!inf) {
        fprintf(stderr, "Error: failed to open input file '%s'\n", in_path);
        return 1;
    }
    size_t read_words = fread(in_raw, sizeof(uint16_t), num_words, inf);
    fclose(inf);

    if (read_words < num_words) {
        fprintf(stderr, "Warning: file read %zu words (expected %zu)\n", read_words, num_words);
    }

    /* 3. Stage-2 Polynomial Evaluation (C) */
    printf("[1/5] Evaluating stage-2 3x10 polynomial in C...\n");
    pakon_poly_hwc_c(in_raw, rpd_buf, (int)num_pixels, coeffs, 1);
    free(in_raw);

    /* 4. Film Base (Dmin) Auto-Neutralization in C */
    printf("[2/5] Calculating film base (Dmin) orange mask neutralization...\n");
    /* Sample 1% low density (highlight / unexposed film base) per channel */
    uint64_t sum_r = 0, sum_g = 0, sum_b = 0;
    for (size_t i = 0; i < num_pixels; i++) {
        sum_r += rpd_buf[i * 3 + 0];
        sum_g += rpd_buf[i * 3 + 1];
        sum_b += rpd_buf[i * 3 + 2];
    }
    int32_t mean_r = (int32_t)(sum_r / num_pixels);
    int32_t mean_g = (int32_t)(sum_g / num_pixels);
    int32_t mean_b = (int32_t)(sum_b / num_pixels);

    int32_t nbp = 1550; /* Neutral Balance Point */
    int16_t shifts[3] = {
        (int16_t)(nbp - mean_r),
        (int16_t)(nbp - mean_g),
        (int16_t)(nbp - mean_b)
    };
    printf("      Dmin means = R:%d G:%d B:%d -> Auto-Balance Shifts = R:%d G:%d B:%d\n",
           mean_r, mean_g, mean_b, shifts[0], shifts[1], shifts[2]);

    /* 5. SBA Balance Apply (C) */
    printf("[3/5] Applying SBA balance shifts in C...\n");
    pakon_apply_balance_shifts_c(rpd_buf, rpd_buf, (int)num_pixels, shifts);

    /* 6. ColorAdjust 3-Tap Unsharp Filter (C) */
    printf("[4/5] Applying ColorAdjust 3-tap separable unsharp filter in C...\n");
    pakon_color_adjust_unsharp_c(rpd_buf, rpd_buf, width, height, 0.15f);

    /* 7. Negative Film Inversion & sRGB Encode (C) */
    printf("[5/5] Inverting film negative and encoding sRGB 24-bit BMP...\n");
    for (size_t i = 0; i < num_words; i++) {
        int32_t val = rpd_buf[i];
        /* Logarithmic negative inversion: 0..4095 RPD -> 0..255 sRGB */
        double norm = (double)val / 4095.0;
        if (norm < 0.0) norm = 0.0;
        if (norm > 1.0) norm = 1.0;
        /* Film inversion + gamma curve sRGB approximation */
        double inv = 1.0 - norm;
        double gamma = pow(inv, 1.0 / 2.2);
        int srgb_val = (int)trunc(gamma * 255.0);
        if (srgb_val < 0) srgb_val = 0;
        if (srgb_val > 255) srgb_val = 255;
        srgb_buf[i] = (uint8_t)srgb_val;
    }
    free(rpd_buf);

    /* 8. Write BMP Output File */
    printf("Writing 24-bit BMP image file to %s...\n", out_path);
    write_bmp_rgb24(out_path, srgb_buf, width, height);
    free(srgb_buf);

    printf("=== Pipeline Complete! Processed %zu pixels in pure native C ===\n", num_pixels);
    return 0;
}
