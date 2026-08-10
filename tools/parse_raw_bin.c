/*
 * parse_raw_bin.c — C line-sync parser for Pakon F-135 EP 0x86 raw captures.
 *
 * Cite: TLB.dll @ 0x1002f550 (worker), 0x1002ff12 (test byte [edx], 1 line-start search),
 *       TLB.dll @ 0x100246d0 (sensor correction).
 * Docs: docs/58-colour-pipeline.md §2.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <raw.bin>\n", argv[0]);
        return 1;
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("fopen"); return 1; }

    fseek(f, 0, SEEK_END);
    long size_bytes = ftell(f);
    rewind(f);

    size_t total_words = size_bytes / 2;
    uint16_t *buf = (uint16_t *)malloc(size_bytes);
    if (!buf) { fprintf(stderr, "OOM\n"); return 1; }

    if (fread(buf, 2, total_words, f) != total_words) {
        fprintf(stderr, "Short read\n");
        return 1;
    }
    fclose(f);

    printf("File %s: %zu total u16 words (%ld bytes)\n", argv[1], total_words, size_bytes);

    /* Search for bit 0 line-start flags (TLB.dll @ 0x1002ff12) */
    size_t sync_count = 0;
    size_t first_sync = 0, last_sync = 0;
    for (size_t i = 0; i < total_words; i++) {
        if (buf[i] & 1) {
            if (sync_count == 0) first_sync = i;
            last_sync = i;
            sync_count++;
        }
    }

    printf("Line-start sync markers (bit 0 = 1): %zu found\n", sync_count);
    if (sync_count > 0) {
        printf("  First sync index: %zu (0x%zx)\n", first_sync, first_sync * 2);
        printf("  Last sync index:  %zu (0x%zx)\n", last_sync, last_sync * 2);
        if (sync_count > 1) {
            printf("  Avg stride between sync markers: %.2f words\n",
                   (double)(last_sync - first_sync) / (sync_count - 1));
        }
    }

    free(buf);
    return 0;
}
