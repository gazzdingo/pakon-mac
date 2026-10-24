#define _POSIX_C_SOURCE 200809L
/* pakon_roll_export: a libpakon roll (<name>.raw + <name>.json + a calibration store) to the on-disk roll directory of core/tests/colour/CORPUS.md.
 *
 *   pakon_roll_export <roll.raw> <calstore_root> <roll_dir> [--strip N] [--film P/G]
 *   --film P/G: pk_roll_set_manual_film (a hand-picked DX product / specifier, e.g. 4/4 to compare with the corpus roll r4, whose codes came from the v1 board's vote).
 *
 * Decodes strip N (default 0) through pk_roll_colour_input (core/include/pakon/roll.h) and writes <roll_dir>/roll.json, strip.lin14, f<i>.lin14 and f<i>.lo, every image
 * planar u16 little-endian (R plane, G plane, B plane). The existing `pakon_render <roll_dir> <out_dir>` renders it: there is no second renderer (C40).
 * Beyond the corpus fields roll.json carries, for the render report: "framing_not_kodak_exact" (ruling S-R19: report such a strip as 'framing not Kodak-exact'),
 * "framing_scanw", "dx_source", "complete" and the strip's film lines. Uses only the public headers pakon/roll.h and pakon/colour.h (and what they include).
 * Exit status: 0 on success, 1 on an API or I/O error, 2 on usage. */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "pakon/roll.h"
#include "pakon/vendor.h"
#include "pakon/colour.h"

static int write_planes(const char *dir, const char *name, const pk_frame_linear *f) {
    char p[4096];
    snprintf(p, sizeof p, "%s/%s", dir, name);
    FILE *fp = fopen(p, "wb");
    if (!fp) { fprintf(stderr, "pakon_roll_export: cannot write %s: %s\n", p, strerror(errno)); return 0; }
    const size_t n = (size_t)f->width * (size_t)f->height;
    int ok = 1;
    for (int c = 0; c < 3 && ok; c++) {
        for (size_t i = 0; i < n && ok; i += 4096) {
            const size_t m = n - i < 4096 ? n - i : 4096;
            unsigned char buf[8192];
            for (size_t j = 0; j < m; j++) { buf[2 * j] = (unsigned char)(f->linear14[c][i + j] & 0xff); buf[2 * j + 1] = (unsigned char)(f->linear14[c][i + j] >> 8); }
            ok = fwrite(buf, 2, m, fp) == m;
        }
    }
    if (fclose(fp) != 0) ok = 0;
    if (!ok) fprintf(stderr, "pakon_roll_export: write error on %s\n", p);
    return ok;
}

/* The frame's IR plane (an IR roll): one plane of width x height u16 little-endian, f<i>.ir14. */
static int write_ir(const char *dir, const char *name, const pk_frame_linear *f) {
    char p[4096];
    snprintf(p, sizeof p, "%s/%s", dir, name);
    FILE *fp = fopen(p, "wb");
    if (!fp) { fprintf(stderr, "pakon_roll_export: cannot write %s: %s\n", p, strerror(errno)); return 0; }
    const size_t n = (size_t)f->width * (size_t)f->height;
    int ok = 1;
    for (size_t i = 0; i < n && ok; i += 4096) {
        const size_t m = n - i < 4096 ? n - i : 4096;
        unsigned char buf[8192];
        for (size_t j = 0; j < m; j++) { buf[2 * j] = (unsigned char)(f->linear14[PK_PLANE_IR][i + j] & 0xff); buf[2 * j + 1] = (unsigned char)(f->linear14[PK_PLANE_IR][i + j] >> 8); }
        ok = fwrite(buf, 2, m, fp) == m;
    }
    if (fclose(fp) != 0) ok = 0;
    if (!ok) fprintf(stderr, "pakon_roll_export: write error on %s\n", p);
    return ok;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: pakon_roll_export <roll.raw> <calstore_root> <roll_dir> [--strip N] [--film P/G]\n"); return 2; }
    const char *raw = argv[1], *store = argv[2], *dir = argv[3];
    int strip = 0, fp = -2, fg = -2;
    for (int i = 4; i < argc; i++) {
        if (!strcmp(argv[i], "--strip") && i + 1 < argc) { char *e; long v = strtol(argv[++i], &e, 10); if (*argv[i] == 0 || *e || v < 0 || v > 100000) { fprintf(stderr, "pakon_roll_export: --strip needs a number\n"); return 2; } strip = (int)v; }
        else if (!strcmp(argv[i], "--film") && i + 1 < argc) { if (sscanf(argv[++i], "%d/%d", &fp, &fg) != 2) { fprintf(stderr, "pakon_roll_export: --film P/G\n"); return 2; } }
        else { fprintf(stderr, "usage: pakon_roll_export <roll.raw> <calstore_root> <roll_dir> [--strip N] [--film P/G]\n"); return 2; }
    }
    int rc = 1;
    pk_roll *r = NULL;
    pk_roll_input in;
    pk_roll_input_storage *keep = NULL;
    (void)pk_lores_weights_load(NULL, DERIVED_ROOT);        /* the owner build's derived copy of TLB's lo-res weights; a store with its own was tried by pk_roll_open */
    pk_status st = pk_roll_open(raw, store, &r);
    if (st) { fprintf(stderr, "pakon_roll_export: pk_roll_open(%s): %s\n", raw, pk_status_str(st)); return 1; }
    if (strip < 0 || strip >= pk_roll_strip_count(r)) { fprintf(stderr, "pakon_roll_export: strip %d: the roll has %d\n", strip, pk_roll_strip_count(r)); goto done; }
    if (fp != -2 && (st = pk_roll_set_manual_film(r, strip, fp, fg))) { fprintf(stderr, "pakon_roll_export: --film %d/%d: %s\n", fp, fg, pk_status_str(st)); goto done; }
    if ((st = pk_roll_colour_input(r, strip, &in, &keep))) { fprintf(stderr, "pakon_roll_export: pk_roll_colour_input: %s\n", pk_status_str(st)); goto done; }
    if (in.n_frames < 1) { fprintf(stderr, "pakon_roll_export: no frames in strip %d\n", strip); goto done; }
    pk_roll_framing_info fi;
    pk_dx_strip dx;
    size_t lines = 0;
    if ((st = pk_roll_framing_info_get(r, strip, &fi)) || (st = pk_roll_dx(r, strip, &dx)) || (st = pk_roll_strip_lines(r, strip, &lines))) {
        fprintf(stderr, "pakon_roll_export: %s\n", pk_status_str(st)); goto done; }
    if (mkdir(dir, 0777) != 0 && errno != EEXIST) { fprintf(stderr, "pakon_roll_export: cannot create %s: %s\n", dir, strerror(errno)); goto done; }
    char p[4096], name[64];
    if (!write_planes(dir, "strip.lin14", &in.strip)) goto done;
    for (int k = 0; k < in.n_frames; k++) {
        snprintf(name, sizeof name, "f%d.lin14", k);
        if ((st = pk_roll_colour_frame(r, strip, k, &in, keep))) { fprintf(stderr, "pakon_roll_export: frame %d: %s\n", k, pk_status_str(st)); goto done; }
        int ok = write_planes(dir, name, &in.frames[k]);
        if (ok && in.frames[k].linear14[PK_PLANE_IR]) { snprintf(name, sizeof name, "f%d.ir14", k); ok = write_ir(dir, name, &in.frames[k]); }   /* S-R45 b: pakon_render --ice reads it */
        pk_roll_colour_frame_release(&in, keep, k);                          /* one hi-res frame in memory at a time */
        if (!ok) goto done;
        snprintf(name, sizeof name, "f%d.lo", k);
        if (!write_planes(dir, name, &in.lores[k])) goto done;
    }
    const pk_frame_rect *rects;
    int nr;
    if ((st = pk_roll_frames(r, strip, &rects, &nr)) || nr != in.n_frames) { fprintf(stderr, "pakon_roll_export: frame list: %s\n", pk_status_str(st)); goto done; }
    snprintf(p, sizeof p, "%s/roll.json", dir);
    FILE *j = fopen(p, "w");
    if (!j) { fprintf(stderr, "pakon_roll_export: cannot write %s\n", p); goto done; }
    fprintf(j, "{\n \"format\": \"pk_roll_input 1\",\n \"n_frames\": %d,\n \"product_code\": %d, \"gen_code\": %d,\n", in.n_frames, in.product_code, in.gen_code);
    fprintf(j, " \"ansel_orientation\": 270, \"lores_rotation\": 180, \"save_rotation\": 270, \"dpi_base\": %d,\n", pk_roll_dpi_base(r));
    fprintf(j, " \"poly_neg_bits\": [");
    for (int i = 0; i < 30; i++) { unsigned u; memcpy(&u, &in.poly_neg[i / 10][i % 10], 4); fprintf(j, "%s\"%08x\"", i ? ", " : "", u); }
    fprintf(j, "],\n \"poly_neg\": [");
    for (int i = 0; i < 3; i++) {
        fprintf(j, "%s[", i ? ", " : "");
        for (int k = 0; k < 10; k++) fprintf(j, "%s%.9g", k ? ", " : "", (double)in.poly_neg[i][k]);
        fprintf(j, "]");
    }
    fprintf(j, "],\n \"strip\": {\"file\": \"strip.lin14\", \"width\": %d, \"height\": %d},\n \"frames\": [", in.strip.width, in.strip.height);
    for (int k = 0; k < in.n_frames; k++)
    {
        char irf[64] = "";
        if (pk_roll_ir(r)) snprintf(irf, sizeof irf, "\"ir_file\": \"f%d.ir14\", ", k);
        fprintf(j, "%s\n  {\"file\": \"f%d.lin14\", %s\"width\": %d, \"height\": %d, \"lo_file\": \"f%d.lo\", \"lo_width\": %d, \"lo_height\": %d, "
                   "\"source\": {\"lines\": [%d, %d], \"lo_rows\": [%d, %d], \"rect_type\": %d}}",
                k ? "," : "", k, irf, in.frames[k].width, in.frames[k].height, k, in.lores[k].width, in.lores[k].height,
                rects[k].top, rects[k].bottom, rects[k].lo_top, rects[k].lo_bottom, (int)rects[k].type);
    }
    fprintf(j, "\n ],\n \"framing_not_kodak_exact\": %d,\n \"framing_scanw\": %u,\n \"dx_source\": \"%s\",\n \"complete\": %d,\n"
               " \"source\": {\"raw\": \"%s\", \"calstore\": \"%s\", \"strip\": %d, \"film_lines\": %zu, \"exporter\": \"tools/pakon_roll_export.c\"}\n}\n",
            fi.not_kodak_exact ? 1 : 0, fi.scanw, dx.dx_source, pk_roll_complete(r) ? 1 : 0, raw, store, strip, lines);
    if (fclose(j) != 0) goto done;
    printf("strip %d: %d frames, codes %d/%d (%s)%s -> %s\n", strip, in.n_frames, in.product_code, in.gen_code, dx.dx_source,
           fi.not_kodak_exact ? ", framing not Kodak-exact" : "", dir);
    rc = 0;
done:
    pk_roll_input_storage_free(keep);
    pk_roll_close(r);
    return rc;
}
