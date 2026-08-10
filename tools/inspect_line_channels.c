/*
 * inspect_line_channels.c — Determine exact channel layout within 6000-word line.
 * Cite: TLB.dll @ 0x100246d0 (sensor correction).
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>

static double calc_mean(const uint16_t *data, size_t n, size_t offset, size_t stride) {
    double sum = 0.0;
    size_t count = 0;
    for (size_t i = offset; i < n; i += stride) {
        sum += (double)(data[i] & 0xFFFE); /* mask out bit 0 sync flag */
        count++;
    }
    return count > 0 ? sum / (double)count : 0.0;
}

int main(int argc, char **argv) {
    if (argc < 2) return 1;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;

    fseek(f, 0, SEEK_END);
    long size_bytes = ftell(f);
    rewind(f);

    size_t total_words = size_bytes / 2;
    uint16_t *buf = (uint16_t *)malloc(size_bytes);
    fread(buf, 2, total_words, f);
    fclose(f);

    printf("=== Test 1: Interleaved stride 3 (2000 pixels x 3 channels) ===\n");
    printf("  Ch 0 mean: %.1f\n", calc_mean(buf, 6000*100, 0, 3));
    printf("  Ch 1 mean: %.1f\n", calc_mean(buf, 6000*100, 1, 3));
    printf("  Ch 2 mean: %.1f\n", calc_mean(buf, 6000*100, 2, 3));

    printf("\n=== Test 2: Interleaved stride 4 (1500 pixels x 4 channels R,G,B,IR) ===\n");
    printf("  Ch 0 mean: %.1f\n", calc_mean(buf, 6000*100, 0, 4));
    printf("  Ch 1 mean: %.1f\n", calc_mean(buf, 6000*100, 1, 4));
    printf("  Ch 2 mean: %.1f\n", calc_mean(buf, 6000*100, 2, 4));
    printf("  Ch 3 mean: %.1f\n", calc_mean(buf, 6000*100, 3, 4));

    printf("\n=== Test 3: Line-Planar (3 planes of 2000 words) ===\n");
    printf("  Plane 0 (0..1999)    mean: %.1f\n", calc_mean(buf + 1, 2000, 0, 1));
    printf("  Plane 1 (2000..3999) mean: %.1f\n", calc_mean(buf + 2001, 2000, 0, 1));
    printf("  Plane 2 (4000..5999) mean: %.1f\n", calc_mean(buf + 4001, 2000, 0, 1));

    printf("\n=== Test 4: Line-Planar (4 planes of 1500 words) ===\n");
    printf("  Plane 0 (0..1499)    mean: %.1f\n", calc_mean(buf + 1, 1500, 0, 1));
    printf("  Plane 1 (1500..2999) mean: %.1f\n", calc_mean(buf + 1501, 1500, 0, 1));
    printf("  Plane 2 (3000..4499) mean: %.1f\n", calc_mean(buf + 3001, 1500, 0, 1));
    printf("  Plane 3 (4500..5999) mean: %.1f\n", calc_mean(buf + 4501, 1500, 0, 1));

    free(buf);
    return 0;
}
