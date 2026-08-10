/*
 * inspect_line_active.c — Find exact active pixel count vs padding per line.
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

    /* Look at line 100 (stride = 6000 words starting at sync index 600001) */
    size_t line_start = 600001;
    printf("Inspecting words of line 100 (index %zu):\n", line_start);

    for (int i = 0; i < 6000; i += 300) {
        printf("  word %4d .. %4d: [0]=%5u [100]=%5u [200]=%5u\n",
               i, i + 299,
               buf[line_start + i],
               buf[line_start + i + 100],
               buf[line_start + i + 200]);
    }

    free(buf);
    return 0;
}
