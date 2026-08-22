/*
 * test_kcms_clut_c.c — evaluator harness for the C port of
 * ``kodakcms.dll fcn.10018160`` (tools/pakon_kcms_clut_c.c).
 *
 * This program only produces output; the comparison against the reference is
 * done by ``tools/test_kcms_clut_ports.py``, which drives it and diffs the bytes
 * against ``tools/ansel/python-pipeline/pakon_kcms_clut.evaluate`` — the port
 * that is itself bit-exact against the real DLL over the whole u8 domain
 * (docs/74 §176).
 *
 * Modes
 * -----
 *   --exhaustive   write all 16,777,216 u8 RGB triples' outputs to stdout,
 *                  r slowest / b fastest (the golden harness's own order)
 *   --stream       read i32 count then count*3 u8 from stdin, write
 *                  count*3 u8 to stdout
 *   --tetra        write the per-tetrahedron hit counts over the whole domain
 *                  to stderr, to show all six branches are exercised
 *   --demo         a few human-readable triples on stdout
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#include "pakon_kcms_clut_c.c"

#define CHUNK_TRIPLES (1 << 16)

static void mode_exhaustive(void) {
    static uint8_t buf[CHUNK_TRIPLES * 3];
    size_t n = 0;
    uint8_t in[3];
    for (int r = 0; r < 256; r++) {
        in[0] = (uint8_t)r;
        for (int g = 0; g < 256; g++) {
            in[1] = (uint8_t)g;
            for (int b = 0; b < 256; b++) {
                in[2] = (uint8_t)b;
                kcms_clut_eval_u8(in, &buf[n * 3]);
                if (++n == CHUNK_TRIPLES) {
                    fwrite(buf, 3, n, stdout);
                    n = 0;
                }
            }
        }
    }
    if (n) fwrite(buf, 3, n, stdout);
}

static void mode_stream(void) {
    int32_t count = 0;
    if (fread(&count, sizeof(count), 1, stdin) != 1 || count < 0) return;
    uint8_t *in = (uint8_t *)malloc((size_t)count * 3);
    uint8_t *out = (uint8_t *)malloc((size_t)count * 3);
    if (!in || !out) { fprintf(stderr, "OOM\n"); exit(2); }
    if (fread(in, 3, (size_t)count, stdin) != (size_t)count) {
        fprintf(stderr, "short read\n");
        exit(2);
    }
    for (int32_t i = 0; i < count; i++)
        kcms_clut_eval_u8(&in[(size_t)i * 3], &out[(size_t)i * 3]);
    fwrite(out, 3, (size_t)count, stdout);
    free(in);
    free(out);
}

/* Which of the six weight orderings each input lands in — the same six-way
 * branch as kcms_clut_eval_u8, reported so the exhaustive run can show every
 * tetrahedron was actually visited rather than assumed. */
static int tetra_of(const uint8_t in[3]) {
    const int32_t wr = kcms_idx[0][in[0]][1];
    const int32_t wg = kcms_idx[1][in[1]][1];
    const int32_t wb = kcms_idx[2][in[2]][1];
    if (wr > wg) {
        if (wg > wb) return 0;
        if (wr > wb) return 1;
        return 2;
    }
    if (wg > wb) return (wr > wb) ? 4 : 3;
    return 5;
}

static void mode_tetra(void) {
    static const char *names[6] = {
        "wR>wG>wB", "wR>wB>=wG", "wB>=wR>wG",
        "wG>wB>=wR", "wG>=wR>wB", "wB>=wG>=wR",
    };
    long long hits[6] = {0, 0, 0, 0, 0, 0};
    uint8_t in[3];
    for (int r = 0; r < 256; r++) {
        in[0] = (uint8_t)r;
        for (int g = 0; g < 256; g++) {
            in[1] = (uint8_t)g;
            for (int b = 0; b < 256; b++) {
                in[2] = (uint8_t)b;
                hits[tetra_of(in)]++;
            }
        }
    }
    for (int i = 0; i < 6; i++)
        fprintf(stderr, "tetra %d %-10s %12lld  %6.2f %%\n", i, names[i],
                hits[i], 100.0 * (double)hits[i] / 16777216.0);
}

static void mode_demo(void) {
    static const uint8_t cases[][3] = {
        {0, 0, 0}, {255, 255, 255}, {128, 128, 128},
        {46, 53, 44}, {200, 17, 90}, {1, 254, 3},
    };
    uint8_t out[3];
    printf("tables npz md5 %s, grid %d^3, %d clut words\n",
           KCMS_CLUT_NPZ_MD5, KCMS_CLUT_GRID_N, KCMS_CLUT_WORDS);
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        kcms_clut_eval_u8(cases[i], out);
        printf("u8 (%3d,%3d,%3d) -> sRGB (%3d,%3d,%3d)\n",
               cases[i][0], cases[i][1], cases[i][2], out[0], out[1], out[2]);
    }
    /* the RPD-12 entry point the pipelines actually call */
    static const int32_t rpds[][3] = {
        {741, 855, 709}, {0, 0, 0}, {4095, 4095, 4095}, {2048, 1000, 3000},
    };
    for (size_t i = 0; i < sizeof(rpds) / sizeof(rpds[0]); i++) {
        kcms_rpd12_to_srgb8(rpds[i], out);
        printf("rpd12 (%4d,%4d,%4d) -> sRGB (%3d,%3d,%3d)\n",
               rpds[i][0], rpds[i][1], rpds[i][2], out[0], out[1], out[2]);
    }

    /* the sar14 helper must be a true arithmetic shift */
    if (kcms_sar14(-1) != -1 || kcms_sar14(-16384) != -1 ||
        kcms_sar14(-16385) != -2 || kcms_sar14(16383) != 0 ||
        kcms_sar14(16384) != 1) {
        printf("FAIL: kcms_sar14 is not floor(v/16384)\n");
        exit(1);
    }
    printf("kcms_sar14 floor semantics OK\n");
}

int main(int argc, char **argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    const char *mode = argc > 1 ? argv[1] : "--demo";
    if (!strcmp(mode, "--exhaustive")) mode_exhaustive();
    else if (!strcmp(mode, "--stream")) mode_stream();
    else if (!strcmp(mode, "--tetra")) mode_tetra();
    else if (!strcmp(mode, "--demo")) mode_demo();
    else { fprintf(stderr, "unknown mode %s\n", mode); return 2; }
    return 0;
}
