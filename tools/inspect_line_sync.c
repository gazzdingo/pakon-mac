/*
 * inspect_line_sync.c — Inspect line sync markers and channel strides in C.
 * Cite: TLB.dll @ 0x1002f550 / 0x100246d0.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

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

    printf("Inspecting sync marker intervals:\n");
    size_t prev_sync = 0;
    int count = 0;
    for (size_t i = 0; i < total_words && count < 20; i++) {
        if (buf[i] & 1) {
            if (count > 0) {
                printf("  Sync %2d: index=%8zu (0x%08zx), delta=%zu words\n",
                       count, i, i * 2, i - prev_sync);
            } else {
                printf("  Sync %2d: index=%8zu (0x%08zx)\n", count, i, i * 2);
            }
            prev_sync = i;
            count++;
        }
    }

    free(buf);
    return 0;
}
