/*
 * pakon_color_cli.c — Standalone C CLI tool for F-135 stage-2 colour polynomial.
 *
 * Cite: TLB.dll @ 0x1000d880 (fcn.1000d880 polynomial) & eeprom_52.bin page layout.
 * Docs: docs/58-colour-pipeline.md §4.
 *
 * Usage:
 *   ./tools/pakon_color_cli raw.bin out.bin --width 3000 --height 2000 [--eeprom eeprom_52.bin]
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "pakon_color_c.c"

static void print_usage(const char* prog) {
    fprintf(stderr, "Usage: %s <input_raw.bin> <output_rpd12.bin> --width <W> --height <H> [--eeprom <eeprom_52.bin>]\n", prog);
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

    /* Load 30 float32 coefficients from eeprom_52.bin (NegMatrix offset 0x25 = byte 37) */
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
        fprintf(stderr, "Error: EEPROM read underflow (%zu floats read)\n", nread);
        return 1;
    }
    for (size_t i = nread; i < 30; i++) {
        coeffs[i] = 0.0f; /* zero-fill tail past byte 256 */
    }

    /* Load raw uint16 RGB triplets */
    size_t num_pixels = (size_t)width * (size_t)height;
    size_t num_words = num_pixels * 3;
    uint16_t* in_buf = (uint16_t*)malloc(num_words * sizeof(uint16_t));
    int32_t* out_buf = (int32_t*)malloc(num_words * sizeof(int32_t));

    if (!in_buf || !out_buf) {
        fprintf(stderr, "Error: memory allocation failed\n");
        return 1;
    }

    FILE* inf = fopen(in_path, "rb");
    if (!inf) {
        fprintf(stderr, "Error: failed to open input file '%s'\n", in_path);
        return 1;
    }
    size_t read_words = fread(in_buf, sizeof(uint16_t), num_words, inf);
    fclose(inf);

    if (read_words < num_words) {
        fprintf(stderr, "Warning: input file smaller than specified dimensions (%zu < %zu words)\n", read_words, num_words);
    }

    printf("Executing F-135 stage-2 C poly evaluation for %dx%d image...\n", width, height);
    pakon_poly_hwc_c(in_buf, out_buf, (int)num_pixels, coeffs, 1);

    FILE* outf = fopen(out_path, "wb");
    if (!outf) {
        fprintf(stderr, "Error: failed to open output file '%s'\n", out_path);
        return 1;
    }
    /* Write 16-bit word RPD output (scaled or raw 12-bit int32 converted to uint16) */
    uint16_t* out_u16 = (uint16_t*)malloc(num_words * sizeof(uint16_t));
    for (size_t i = 0; i < num_words; i++) {
        out_u16[i] = (uint16_t)(out_buf[i] & 0xFFFF);
    }
    fwrite(out_u16, sizeof(uint16_t), num_words, outf);
    fclose(outf);

    free(in_buf);
    free(out_buf);
    free(out_u16);

    printf("Done. Wrote RPD12 data to %s\n", out_path);
    return 0;
}
