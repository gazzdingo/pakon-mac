/* Performance bench (Task 23): not part of ctest. Build: cmake --build build --target colour_bench
 *   build/colour_bench <roll_dir> [n_frames=40]
 * roll_dir: a pk_roll_input directory (CORPUS.md; e.g. the e2e r4 roll). Times (1) pk_colour_analyse_roll over n_frames
 * scenes (the roll's frames' lo-res images repeated cyclically; the hi-res frames are not read for the analysis) and
 * (2) one full-size pk_colour_render of frame 0 (best of 3). Targets on the owner's Mac (M2 Max): analysis <= 5 s,
 * render <= 1 s. Prints both times; exit 1 when a target is missed. Numbers are recorded in PERF.md. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "pakon/colour.h"

#ifndef VENDOR_ROOT
#define VENDOR_ROOT ""
#endif
#ifndef DERIVED_ROOT
#define DERIVED_ROOT ""
#endif

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static char *slurp(const char *p, size_t *n) {
    FILE *f = fopen(p, "rb"); if (!f) return NULL;
    fseek(f, 0, SEEK_END); long l = ftell(f); fseek(f, 0, SEEK_SET);
    char *b = malloc((size_t)l + 1); if (!b || fread(b, 1, (size_t)l, f) != (size_t)l) { fclose(f); free(b); return NULL; }
    fclose(f); b[l] = 0; if (n) *n = (size_t)l; return b;
}
/* next occurrence of "key": after *p; returns pointer to the value or NULL */
static const char *find(const char **p, const char *key) {
    char k[64]; snprintf(k, sizeof k, "\"%s\":", key);
    const char *q = strstr(*p, k); if (!q) return NULL;
    q += strlen(k); while (*q == ' ') q++; *p = q; return q;
}
static int num(const char **p, const char *key) { const char *q = find(p, key); return q ? atoi(q) : -1; }
static int load(const char *dir, const char *file, int w, int h, pk_frame_linear *f) {
    char p[4096]; size_t len; snprintf(p, sizeof p, "%s/%s", dir, file);
    char *b = slurp(p, &len);
    if (!b || len != (size_t)w * h * 6) { fprintf(stderr, "bad %s\n", p); return 0; }
    uint16_t *s = (uint16_t *)(void *)b;
    for (size_t i = 0; i < (size_t)w * h * 3; i++) { const unsigned char *q = (const unsigned char *)&s[i]; s[i] = (uint16_t)(q[0] | q[1] << 8); }
    f->width = w; f->height = h; for (int c = 0; c < 3; c++) f->linear14[c] = s + (size_t)c * w * h;
    return 1;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: colour_bench <roll_dir> [n_frames] [rotation 0|90|180|270] [threads]\n"); return 2; }
    const char *dir = argv[1]; int N = argc > 2 ? atoi(argv[2]) : 40, ROT = argc > 3 ? atoi(argv[3]) : 0, THR = argc > 4 ? atoi(argv[4]) : 0;
    char p[4096]; snprintf(p, sizeof p, "%s/roll.json", dir);
    char *js = slurp(p, NULL); if (!js) { fprintf(stderr, "no roll.json\n"); return 2; }
    pk_roll_input in; memset(&in, 0, sizeof in);
    const char *q = js;
    int nf = num(&q, "n_frames"); in.product_code = num(&q, "product_code"); in.gen_code = num(&q, "gen_code");
    q = strstr(js, "\"poly_neg_bits\""); if (!q || !(q = strchr(q, '['))) return 2;
    for (int k = 0; k < 30; k++) {
        unsigned u; q = strchr(q, '"');
        if (!q || sscanf(q + 1, "%8x", &u) != 1) { fprintf(stderr, "poly_neg_bits\n"); return 2; }
        memcpy(&in.poly_neg[k / 10][k % 10], &u, 4); q = strchr(q + 1, '"') + 1;
    }
    q = strstr(js, "\"strip\""); if (!q) return 2;
    { int w = num(&q, "width"), h = num(&q, "height"); if (!load(dir, "strip.lin14", w, h, &in.strip)) return 2; }
    pk_frame_linear *hi = calloc((size_t)nf, sizeof *hi), *lo = calloc((size_t)N, sizeof *lo);
    q = strstr(js, "\"frames\"");
    for (int k = 0; k < nf; k++) {
        const char *f = find(&q, "file"); char name[256], lname[256];
        if (!f || sscanf(f, "\"%255[^\"]\"", name) != 1) return 2;
        int w = num(&q, "width"), h = num(&q, "height");
        const char *l = find(&q, "lo_file"); if (!l || sscanf(l, "\"%255[^\"]\"", lname) != 1) return 2;
        int lw = num(&q, "lo_width"), lh = num(&q, "lo_height");
        if (k == 0 && !load(dir, name, w, h, &hi[0])) return 2;
        if (!load(dir, lname, lw, lh, &lo[k])) return 2;
    }
    for (int k = nf; k < N; k++) lo[k] = lo[k % nf];
    in.frames = hi; in.lores = lo; in.n_frames = N;
    const char *vendor = getenv("PAKON_VENDOR_ROOT") ? getenv("PAKON_VENDOR_ROOT") : VENDOR_ROOT;
    const char *derived = getenv("PAKON_DERIVED_ROOT") ? getenv("PAKON_DERIVED_ROOT") : DERIVED_ROOT;
    pk_colour *c; pk_roll_result *res;
    pk_colour_options copt = { sizeof copt, THR };
    if (pk_colour_open_opts(vendor, derived, &copt, NULL, &c)) { fprintf(stderr, "open failed\n"); return 2; }
    double t = now();
    pk_status st = pk_colour_analyse_roll(c, &in, &res);
    double t_an = now() - t;
    if (st) { fprintf(stderr, "analyse: %s\n", pk_status_str(st)); return 1; }
    /* render needs hi-res for frame 0 only; the analysis result's frame 0 is the same scene as in the real roll */
    double best = 1e9; uint8_t *rgb = malloc((size_t)hi[0].width * hi[0].height * 3);
    for (int i = 0; i < 3; i++) {
        pk_image_u8 im = { 0, 0, rgb };
        t = now(); st = pk_colour_render_rotated(c, &in, res, 0, NULL, ROT, &im);   /* 270 = PSI's default save */ double d = now() - t;
        if (st) { fprintf(stderr, "render: %s\n", pk_status_str(st)); return 1; }
        if (d < best) best = d;
    }
    printf("analysis of %d frames: %.3f s (target <= 5 s)\nrender of one %dx%d frame (best of 3): %.3f s (target <= 1 s)\n",
           N, t_an, hi[0].width, hi[0].height, best);
    return (t_an <= 5.0 && best <= 1.0) ? 0 : 1;
}
