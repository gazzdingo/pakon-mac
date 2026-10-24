/* pakon_render: render a roll directory through libpakon's public colour API (pakon/colour.h).
 *
 *   pakon_render <roll_dir> <out_dir> [--adjust JSON | --adjust @file] [--frames 0,3,..] [--rotate 0|90|180|270]
 *                [--ansel-orientation 0|270] [--save-size FIT,W,H[,NOUP]] [--picture-rotation 0..3]
 *                [--ice] [--no-sb] [--bits16] [--threads N] [--vendor DIR] [--derived DIR]
 *   --bits16 (C10, docs/re/50): needs --ansel-orientation. Besides the 8-bit file, renders every picture (and every --adjust set) again with
 *            pk_colour_render_saved_scaled16 and reduces each sample with Kodak's own 8-bit store, (v * 32640 + 4194303) >> 23; prints
 *            "bits16: <frames> renders, <N> differing pixels, <M> samples carrying more than the 8-bit code" and exits 1 if N != 0.
 *   --ice: Digital ICE on the save (TLB save bit 0x80, pk_roll_input.ice; docs/re/45 sec 4): needs f<i>.ir14 (one plane, width x height u16 LE; roll.json frame key
 *          "ir_file") for a frame to take effect; a frame without it renders as without --ice, silently. A frame ICE cannot run on (too small) is a PK_E_ARG with a message.
 *   --threads N: pk_colour_options.threads (0 = automatic, the default; 1 = render on the calling thread only); the output is identical.
 *
 * roll_dir is the pk_roll_input on-disk layout (core/tests/colour/CORPUS.md): roll.json + f<i>.lin14 + f<i>.lo +
 * strip.lin14, every image planar u16 little-endian (R plane, G plane, B plane).
 *
 * Writes, per frame i (all frames unless --frames):
 *   f<i>.srgb.u8   pk_colour_render with PSI's defaults: planar u8 (R plane, G plane, B plane), the layout Kodak's
 *                  PIColorAdjustPlanar writes, so the bytes (and SHA-256) compare directly with the oracle's file;
 *   f<i>.sb.u16    the 12-bit scene-balanced buffer before the KCMS stage (pk_colour_export_rpd16 >> 4, which undoes
 *                  its v * 16 + v / 256): planar u16 LE, the layout of the oracle's ColorSceneBalancePlanar output;
 *   with --adjust: f<i>.a<k>.srgb.u8 for adjustment set k (JSON object, or array of objects, with keys r g b brightness
 *                  contrast sharpness saturation bnw; integer values; missing keys are 0). --no-sb skips the .sb.u16 files.
 * --rotate: PSI's save rotation (pk_colour_render_rotated; PSI's default save is 270): the u8 files are in that geometry
 * and so is .sb.u16 (the same pixel rotation applied to the 12-bit buffer, the image PIColorAdjustPlanar receives).
 * --ansel-orientation 0 (Task 22): pk_colour_render_saved with AnselOrientation = 0 and picture rotation 0 (the hi-res frame is
 * rotated 270 BEFORE the balance, nothing after); the u8 files only (no .sb.u16), --rotate is then not allowed.
 * --save-size FIT,W,H[,NOUP] (RE 39): PSI's scaled save, pk_colour_render_saved_scaled with iSaveControl & 3 = FIT (1 or 2), the
 * bounding box W x H and, if NOUP is 1, the don't-scale-up bit 0x800; the u8 files are in the saved size (and, like
 * --ansel-orientation, there is no .sb.u16). It takes AnselOrientation 270 unless --ansel-orientation 0 is given; --rotate is
 * not allowed (the save rotation comes from the picture rotation code, --picture-rotation, default 0 = PSI's default 270).
 * and render.json: the film base / per-frame status, exposure, falloff and wall-clock times (analysis, each render), and per frame (Task 20) "exact"
 * (pk_roll_result_exact: 1 = bit-exact with Kodak; 0 flags a grid past a frame, i.e. a framing defect), "skipped" (pk_roll_result_skipped: Kodak skipped the
 * frame's analysis, so it is rendered unbalanced) and "framing_not_kodak_exact" (ruling S-R19: the roll.json of pakon_roll_export says the strip's framing read run
 * statistics that Kodak leaves uninitialised; report such a roll as 'framing not Kodak-exact'; 0 when roll.json has no such field).
 * Exit status: 0 when every requested output was written, 1 on an API error (printed with its pk_status name), 2 usage.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <ctype.h>
#include "pakon/colour.h"

#ifndef VENDOR_ROOT
#define VENDOR_ROOT ""
#endif
#ifndef DERIVED_ROOT
#define DERIVED_ROOT ""
#endif

/* ---- a minimal JSON reader (objects, arrays, strings without escapes beyond \" \\ \/, numbers, literals) ---- */
typedef struct jv { int type; char *key; char *str; double num; struct jv *kid, *next; } jv;   /* type: o a s n b z */
static const char *J;
static void jskip(void) { while (*J && isspace((unsigned char)*J)) J++; }
static void jfree(jv *v) { while (v) { jv *n = v->next; jfree(v->kid); free(v->key); free(v->str); free(v); v = n; } }
static char *jstr(void) {
    if (*J != '"') return NULL;
    const char *s = ++J; size_t n = 0;
    char *o = malloc(strlen(s) + 1);
    if (!o) return NULL;
    while (*J && *J != '"') { if (*J == '\\' && J[1]) J++; o[n++] = *J++; }
    if (*J != '"') { free(o); return NULL; }
    J++; o[n] = 0; return o;
}
static jv *jparse(void) {
    jskip();
    jv *v = calloc(1, sizeof *v);
    if (!v) return NULL;
    if (*J == '{' || *J == '[') {
        char close = *J == '{' ? '}' : ']';
        v->type = *J == '{' ? 'o' : 'a'; J++;
        jv **tail = &v->kid;
        jskip();
        if (*J == close) { J++; return v; }
        for (;;) {
            char *key = NULL;
            jskip();
            if (v->type == 'o') { if (!(key = jstr())) goto bad; jskip(); if (*J++ != ':') { free(key); goto bad; } }
            jv *k = jparse();
            if (!k) { free(key); goto bad; }
            k->key = key; *tail = k; tail = &k->next;
            jskip();
            if (*J == ',') { J++; continue; }
            if (*J == close) { J++; return v; }
            goto bad;
        }
    }
    if (*J == '"') { v->type = 's'; if (!(v->str = jstr())) goto bad; return v; }
    if (!strncmp(J, "true", 4)) { v->type = 'b'; v->num = 1; J += 4; return v; }
    if (!strncmp(J, "false", 5)) { v->type = 'b'; J += 5; return v; }
    if (!strncmp(J, "null", 4)) { v->type = 'z'; J += 4; return v; }
    { char *e; v->num = strtod(J, &e); if (e == J) goto bad; v->type = 'n'; J = e; return v; }
bad:
    jfree(v);
    return NULL;
}
static jv *jget(const jv *o, const char *key) {
    if (!o || o->type != 'o') return NULL;
    for (jv *k = o->kid; k; k = k->next) if (!strcmp(k->key, key)) return k;
    return NULL;
}
static int jint(const jv *o, const char *key, int *out) {
    jv *v = jget(o, key);
    if (!v || v->type != 'n' || v->num != (double)(int)v->num) return 0;   /* integers only */
    *out = (int)v->num;
    return 1;
}
static char *slurp(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *b = n >= 0 ? malloc((size_t)n + 1) : NULL;
    if (b && fread(b, 1, (size_t)n, f) != (size_t)n) { free(b); b = NULL; }
    fclose(f);
    if (b) { b[n] = 0; if (len) *len = (size_t)n; }
    return b;
}
static jv *jload_text(const char *text) {
    J = text;
    jv *v = jparse();
    jskip();
    if (v && *J) { jfree(v); v = NULL; }
    return v;
}

/* ---- roll directory ---- */
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

static int load_ir(const char *dir, const char *file, int w, int h, pk_frame_linear *f, uint16_t **keep) {
    char p[4096];
    snprintf(p, sizeof p, "%s/%s", dir, file);
    size_t len = 0, n = (size_t)w * h;
    char *b = slurp(p, &len);
    if (!b) { fprintf(stderr, "pakon_render: cannot read %s\n", p); return 0; }
    if (w < 1 || h < 1 || len != n * 2) { fprintf(stderr, "pakon_render: %s: %zu bytes, expected %d x %d x 2\n", p, len, w, h); free(b); return 0; }
    uint16_t *s = (uint16_t *)(void *)b;
    for (size_t i = 0; i < n; i++) { const unsigned char *q = (const unsigned char *)&s[i]; s[i] = (uint16_t)(q[0] | q[1] << 8); }
    f->linear14[PK_PLANE_IR] = s;
    *keep = s;
    return 1;
}

static int load_planes(const char *dir, const char *file, int w, int h, pk_frame_linear *f, uint16_t **keep) {
    char p[4096];
    snprintf(p, sizeof p, "%s/%s", dir, file);
    size_t len = 0, n = (size_t)w * h;
    char *b = slurp(p, &len);
    if (!b) { fprintf(stderr, "pakon_render: cannot read %s\n", p); return 0; }
    if (w < 1 || h < 1 || len != 3 * n * 2) { fprintf(stderr, "pakon_render: %s: %zu bytes, expected 3 x %d x %d x 2\n", p, len, w, h); free(b); return 0; }
    uint16_t *s = (uint16_t *)(void *)b;
    for (size_t i = 0; i < 3 * n; i++) { const unsigned char *q = (const unsigned char *)&s[i]; s[i] = (uint16_t)(q[0] | q[1] << 8); }
    f->width = w; f->height = h;
    for (int c = 0; c < 3; c++) f->linear14[c] = s + c * n;
    *keep = s;
    return 1;
}

static int write_file(const char *dir, const char *name, const void *b, size_t n) {
    char p[4096];
    snprintf(p, sizeof p, "%s/%s", dir, name);
    FILE *f = fopen(p, "wb");
    if (!f || fwrite(b, 1, n, f) != n) { fprintf(stderr, "pakon_render: cannot write %s\n", p); if (f) fclose(f); return 0; }
    return fclose(f) == 0;
}

static int parse_adjust(const jv *o, pk_adjust *a) {
    if (!o || o->type != 'o') return 0;
    memset(a, 0, sizeof *a);
    static const char *const known[] = { "r", "g", "b", "brightness", "contrast", "sharpness", "saturation", "bnw" };
    for (jv *k = o->kid; k; k = k->next) {
        int ok = 0;
        for (size_t i = 0; i < sizeof known / sizeof known[0]; i++) ok |= !strcmp(k->key, known[i]);
        if (!ok || k->type != 'n' || k->num != (double)(int)k->num) {
            fprintf(stderr, "pakon_render: --adjust: bad key or non-integer value '%s'\n", k->key); return 0; }
    }
    jint(o, "r", &a->r); jint(o, "g", &a->g); jint(o, "b", &a->b); jint(o, "brightness", &a->brightness);
    jint(o, "contrast", &a->contrast); jint(o, "sharpness", &a->sharpness); jint(o, "saturation", &a->saturation);
    jint(o, "bnw", &a->bnw);
    return 1;
}

static int usage(void) {
    fprintf(stderr, "usage: pakon_render <roll_dir> <out_dir> [--adjust JSON|@file] [--frames i,j,..] [--no-sb] "
                    "[--rotate 0|90|180|270 | --ansel-orientation 0|270] [--save-size FIT,W,H[,NOUP]] [--picture-rotation 0..3] "
                    "[--vendor DIR] [--derived DIR]\n");
    return 2;
}

int main(int argc, char **argv) {
    if (argc < 3) return usage();
    const char *dir = argv[1], *out = argv[2], *adjust_arg = NULL, *frames_arg = NULL;
    const char *vendor = getenv("PAKON_VENDOR_ROOT") ? getenv("PAKON_VENDOR_ROOT") : VENDOR_ROOT;
    const char *derived = getenv("PAKON_DERIVED_ROOT") ? getenv("PAKON_DERIVED_ROOT") : DERIVED_ROOT;
    int want_sb = 1, rotation = 0, ao = -1, threads = 0, prot = 0, ice = 0, bits16 = 0;
    long long b16_renders = 0, b16_diff = 0, b16_more = 0;
    pk_save_size ssz = { 0, 0, 0, 0 };
    for (int i = 3; i < argc; i++) {
        if (!strcmp(argv[i], "--adjust") && i + 1 < argc) adjust_arg = argv[++i];
        else if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames_arg = argv[++i];
        else if (!strcmp(argv[i], "--vendor") && i + 1 < argc) vendor = argv[++i];
        else if (!strcmp(argv[i], "--derived") && i + 1 < argc) derived = argv[++i];
        else if (!strcmp(argv[i], "--rotate") && i + 1 < argc) rotation = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--ansel-orientation") && i + 1 < argc) ao = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--picture-rotation") && i + 1 < argc) prot = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--save-size") && i + 1 < argc) {
            int nf = sscanf(argv[++i], "%d,%d,%d,%d", &ssz.fit, &ssz.bound_w, &ssz.bound_h, &ssz.no_upscale);
            if (nf < 3 || ssz.fit < 1) return usage();
        }
        else if (!strcmp(argv[i], "--no-sb")) want_sb = 0;
        else if (!strcmp(argv[i], "--ice")) ice = 1;
        else if (!strcmp(argv[i], "--bits16")) bits16 = 1;
        else return usage();
    }
    if (rotation != 0 && rotation != 90 && rotation != 180 && rotation != 270) return usage();
    if (prot < 0 || prot > 3 || (prot != 0 && !ssz.fit && ao == -1)) return usage();
    if (ssz.fit && (rotation != 0)) return usage();
    if (ssz.fit && ao == -1) ao = PK_ANSEL_ORIENTATION_PSI;
    if (ao != -1 && ((ao != 0 && ao != PK_ANSEL_ORIENTATION_PSI) || rotation != 0)) return usage();   /* picture rotation 0 */
    if (bits16 && ao == -1) return usage();
    if (ao != -1) want_sb = 0;                    /* u8 only: no AnselOrientation-aware 12-bit export */
    /* pk_colour_render_saved: the net rotation (before + after the balance) is (630, 540, 450, 360)[r] mod 360 for both
     * AnselOrientation values (270 for picture rotation 0), colour.h */
    static const int BASE[4] = { 630, 540, 450, 360 };
    const int net = ao >= 0 ? BASE[prot] % 360 : rotation;

    int rc = 2, nadj = 0, n = 0;
    pk_adjust *adj = NULL;
    jv *R = NULL;
    pk_frame_linear *hi = NULL, *lo = NULL;
    uint16_t **keep = NULL;
    char *want = NULL, p[4096];
    pk_colour *c = NULL;
    pk_roll_result *res = NULL;
    FILE *rj = NULL;
    uint8_t *rgb = NULL, *pl = NULL;
    uint16_t *r16 = NULL, *p16 = NULL;

    /* adjustment sets */
    if (adjust_arg) {
        char *text = adjust_arg[0] == '@' ? slurp(adjust_arg + 1, NULL) : strdup(adjust_arg);
        jv *a = text ? jload_text(text) : NULL;
        free(text);
        if (!a) { fprintf(stderr, "pakon_render: --adjust: not JSON\n"); goto done; }
        int na = a->type == 'o' ? 1 : 0;
        if (a->type == 'a') for (jv *k = a->kid; k; k = k->next) na++;
        adj = calloc(na ? (size_t)na : 1, sizeof *adj);
        int ok = adj != NULL;
        if (ok && a->type == 'o') ok = parse_adjust(a, &adj[nadj++]);
        else if (ok) for (jv *k = a->kid; k && ok; k = k->next) ok = parse_adjust(k, &adj[nadj++]);
        jfree(a);
        if (!ok || !nadj) { fprintf(stderr, "pakon_render: --adjust: no valid sets\n"); goto done; }
    }

    /* roll.json */
    snprintf(p, sizeof p, "%s/roll.json", dir);
    char *text = slurp(p, NULL);
    R = text ? jload_text(text) : NULL;
    free(text);
    if (!R) { fprintf(stderr, "pakon_render: cannot parse %s\n", p); goto done; }
    jv *frames = jget(R, "frames"), *strip = jget(R, "strip"), *bits = jget(R, "poly_neg_bits");
    int framing_nke = 0;
    jint(R, "framing_not_kodak_exact", &framing_nke);
    if (!jint(R, "n_frames", &n) || n < 1 || !frames || frames->type != 'a' || !strip || !bits || bits->type != 'a') {
        fprintf(stderr, "pakon_render: %s: missing n_frames / frames / strip / poly_neg_bits\n", p); goto done; }
    pk_roll_input in;
    memset(&in, 0, sizeof in);
    in.n_frames = n;
    if (!jint(R, "product_code", &in.product_code) || !jint(R, "gen_code", &in.gen_code)) {
        fprintf(stderr, "pakon_render: %s: missing product_code / gen_code\n", p); goto done; }
    {   int k = 0;
        for (jv *b = bits->kid; b; b = b->next, k++) {
            if (k >= 30 || b->type != 's') { k = 99; break; }
            uint32_t u = (uint32_t)strtoul(b->str, NULL, 16); float f; memcpy(&f, &u, 4);
            in.poly_neg[k / 10][k % 10] = f;
        }
        if (k != 30) { fprintf(stderr, "pakon_render: poly_neg_bits must hold 30 words\n"); goto done; } }
    hi = calloc((size_t)n, sizeof *hi); lo = calloc((size_t)n, sizeof *lo);
    keep = calloc((size_t)(3 * n + 1), sizeof *keep);      /* hi, lo per frame, then the strip, then the IR planes */
    want = calloc((size_t)n, 1);
    rc = 1;
    if (!hi || !lo || !keep || !want) { fprintf(stderr, "pakon_render: out of memory\n"); goto done; }
    rc = 2;
    {   int w, h; jv *f = jget(strip, "file");
        if (!f || f->type != 's' || !jint(strip, "width", &w) || !jint(strip, "height", &h) ||
            !load_planes(dir, f->str, w, h, &in.strip, &keep[2 * n])) goto done; }
    {   int k = 0;
        for (jv *f = frames->kid; f; f = f->next, k++) {
            int w, h, lw, lh; jv *hf = jget(f, "file"), *lf = jget(f, "lo_file");
            if (k >= n || !hf || !lf || !jint(f, "width", &w) || !jint(f, "height", &h) || !jint(f, "lo_width", &lw) ||
                !jint(f, "lo_height", &lh)) { fprintf(stderr, "pakon_render: frame %d entry incomplete\n", k); goto done; }
            if (!load_planes(dir, hf->str, w, h, &hi[k], &keep[2 * k]) || !load_planes(dir, lf->str, lw, lh, &lo[k], &keep[2 * k + 1]))
                goto done;
            jv *irf = jget(f, "ir_file");
            if (irf && irf->type == 's' && !load_ir(dir, irf->str, w, h, &hi[k], &keep[2 * n + 1 + k])) goto done;
        }
        if (k != n) { fprintf(stderr, "pakon_render: %d frame entries for n_frames %d\n", k, n); goto done; } }
    in.frames = hi; in.lores = lo; in.ice = ice;
    if (frames_arg) {
        const char *s = frames_arg;
        while (*s) {
            char *e; long v = strtol(s, &e, 10);
            if (e == s || v < 0 || v >= n) { fprintf(stderr, "pakon_render: bad --frames\n"); goto done; }
            want[v] = 1; s = *e == ',' ? e + 1 : e;
        }
    } else memset(want, 1, (size_t)n);

    rc = 1;
    double t0 = now();
    pk_colour_options copt = { sizeof copt, threads };
    pk_status st = pk_colour_open_opts(vendor, derived, &copt, NULL, &c);
    if (st) { fprintf(stderr, "pakon_render: pk_colour_open_opts(%s, %s): %s\n", vendor, derived, pk_status_str(st)); goto done; }
    double t_open = now() - t0;
    t0 = now();
    st = pk_colour_analyse_roll(c, &in, &res);
    double t_an = now() - t0;
    if (st) { fprintf(stderr, "pakon_render: pk_colour_analyse_roll: %s\n", pk_status_str(st)); goto done; }

    snprintf(p, sizeof p, "%s/render.json", out);
    if (!(rj = fopen(p, "w"))) { fprintf(stderr, "pakon_render: cannot write %s\n", p); goto done; }
    fprintf(rj, "{\n \"roll_dir\": \"%s\",\n \"product_code\": %d, \"gen_code\": %d, \"rotation\": %d,\n \"open_s\": %.3f, \"analyse_s\": %.3f,\n \"frames\": [",
            dir, in.product_code, in.gen_code, rotation, t_open, t_an);
    printf("analysed %d frames in %.2f s\n", n, t_an);
    if (framing_nke) printf("framing not Kodak-exact (ruling S-R19): the strip's frame detection read statistics Kodak leaves uninitialised\n");
    int first = 1;
    rc = 0;
    for (int k = 0; k < n && !rc; k++) {
        if (!want[k]) continue;
        const int w = hi[k].width, h = hi[k].height;
        int ow = net % 180 ? h : w, oh = net % 180 ? w : h;
        if (ssz.fit) {
            if ((st = pk_colour_saved_size(&in, k, prot, &ssz, &ow, &oh))) {
                fprintf(stderr, "pakon_render: frame %d saved size: %s\n", k, pk_status_str(st)); rc = 1; break; }
        }
        if (ice) {
            char why[300];
            if ((st = pk_colour_ice_check(&in, k, why, sizeof why))) { fprintf(stderr, "pakon_render: frame %d: %s: %s\n", k, pk_status_str(st), why); rc = 1; break; }
        }
        int fall = 0; double stops = 0;
        size_t np = (size_t)w * h;
        pk_status fs = pk_roll_result_status(res, k);
        int exact = 0, skipped = 0;
        pk_roll_result_exact(res, k, &exact);
        pk_roll_result_skipped(res, k, &skipped);
        pk_roll_result_falloff(res, k, &fall);
        pk_roll_result_exposure(res, k, &stops);
        const size_t npo = (size_t)ow * oh, nbuf = npo > np ? npo : np;
        rgb = malloc(nbuf * 3); pl = malloc(nbuf * 3);
        if (want_sb) { r16 = malloc(np * 3 * 2); p16 = malloc(np * 3 * 2); }
        if (!rgb || !pl || (want_sb && (!r16 || !p16))) { fprintf(stderr, "pakon_render: out of memory\n"); rc = 1; break; }
        double tr = 0, ts = 0;
        char name[64];
        for (int a = -1; a < nadj && !rc; a++) {
            pk_image_u8 im = { 0, 0, rgb };
            t0 = now();
            st = ao < 0 ? pk_colour_render_rotated(c, &in, res, k, a < 0 ? NULL : &adj[a], rotation, &im)
               : ssz.fit ? pk_colour_render_saved_scaled(c, &in, res, k, a < 0 ? NULL : &adj[a], ao, prot, &ssz, &im)
                         : pk_colour_render_saved(c, &in, res, k, a < 0 ? NULL : &adj[a], ao, prot, &im);
            if (a < 0) tr = now() - t0;
            if (st) { fprintf(stderr, "pakon_render: frame %d render%s: %s\n", k, a < 0 ? "" : " (adjusted)", pk_status_str(st)); rc = 1; break; }
            if (im.width != ow || im.height != oh) { fprintf(stderr, "pakon_render: frame %d: size %dx%d, expected %dx%d\n", k, im.width, im.height, ow, oh); rc = 1; break; }
            for (size_t i = 0; i < npo; i++) for (int ch = 0; ch < 3; ch++) pl[ch * npo + i] = rgb[i * 3 + ch];
            if (a < 0) snprintf(name, sizeof name, "f%d.srgb.u8", k); else snprintf(name, sizeof name, "f%d.a%d.srgb.u8", k, a);
            if (!write_file(out, name, pl, npo * 3)) rc = 1;
            if (bits16 && !rc) {       /* C10: the 16-bit Kodak output must reduce to the byte just rendered */
                uint16_t *r16k = malloc(npo * 3 * sizeof *r16k);
                pk_image_u16 im16 = { 0, 0, r16k };
                if (!r16k) { fprintf(stderr, "pakon_render: out of memory\n"); rc = 1; break; }
                st = pk_colour_render_saved_scaled16(c, &in, res, k, a < 0 ? NULL : &adj[a], ao, prot, &ssz, &im16);
                if (st || im16.width != ow || im16.height != oh) {
                    fprintf(stderr, "pakon_render: frame %d bits16: %s\n", k, pk_status_str(st)); free(r16k); rc = 1; break; }
                long long dpx = 0, more = 0;
                for (size_t i = 0; i < npo; i++) {
                    int bad = 0;
                    for (int ch = 0; ch < 3; ch++) {
                        const int64_t v = r16k[i * 3 + ch];
                        if ((uint8_t)((v * 32640 + 4194303) >> 23) != rgb[i * 3 + ch]) bad = 1;
                        if (v != rgb[i * 3 + ch] * 257) more++;
                    }
                    dpx += bad;
                }
                b16_renders++; b16_diff += dpx; b16_more += more;
                if (dpx) printf("bits16: frame %d%s: %lld differing pixels\n", k, a < 0 ? "" : " (adjusted)", dpx);
                free(r16k);
            }
        }
        if (want_sb && !rc) {
            pk_image_u16 im = { 0, 0, r16 };
            t0 = now();
            st = pk_colour_export_rpd16(c, &in, res, k, &im);
            ts = now() - t0;
            if (st) { fprintf(stderr, "pakon_render: frame %d rpd16: %s\n", k, pk_status_str(st)); rc = 1; }
            else {
                /* 12-bit planes in the save geometry: the same rotation as pk_colour_render_rotated (90 clockwise) */
                for (int y = 0; y < oh; y++)
                    for (int x = 0; x < ow; x++) {
                        int sx = x, sy = y;
                        if (rotation == 90) { sx = y; sy = h - 1 - x; }
                        else if (rotation == 180) { sx = w - 1 - x; sy = h - 1 - y; }
                        else if (rotation == 270) { sx = w - 1 - y; sy = x; }
                        for (int ch = 0; ch < 3; ch++) {
                            uint16_t v = (uint16_t)(r16[((size_t)sy * w + sx) * 3 + ch] >> 4);
                            unsigned char *q = (unsigned char *)&p16[ch * np + (size_t)y * ow + x];
                            q[0] = (unsigned char)(v & 0xff); q[1] = (unsigned char)(v >> 8);
                        }
                    }
                snprintf(name, sizeof name, "f%d.sb.u16", k);
                if (!write_file(out, name, p16, np * 6)) rc = 1;
            }
        }
        fprintf(rj, "%s\n  {\"frame\": %d, \"width\": %d, \"height\": %d, \"status\": \"%s\", \"exposure_stops\": %.1f, \"falloff\": %d, "
                    "\"exact\": %d, \"skipped\": %d, \"framing_not_kodak_exact\": %d, \"render_s\": %.3f, \"rpd16_s\": %.3f}",
                first ? "" : ",", k, ow, oh, pk_status_str(fs), stops, fall, exact, skipped, framing_nke, tr, ts);
        first = 0;
        printf("frame %d %dx%d %s exposure %+.1f falloff %d exact %d%s render %.2f s\n", k, ow, oh, pk_status_str(fs), stops, fall, exact, skipped ? " (analysis skipped)" : "", tr);
        free(rgb); free(pl); free(r16); free(p16); rgb = pl = NULL; r16 = p16 = NULL;
    }
    fprintf(rj, "\n ]\n}\n");
    if (bits16) {
        printf("bits16: %lld renders, %lld differing pixels, %lld samples carrying more than the 8-bit code\n", b16_renders, b16_diff, b16_more);
        if (b16_diff) rc = 1;
    }
done:
    if (rj) fclose(rj);
    free(rgb); free(pl); free(r16); free(p16);
    pk_roll_result_free(res);
    pk_colour_close(c);
    if (keep) for (int k = 0; k < 3 * n + 1; k++) free(keep[k]);
    free(keep); free(hi); free(lo); free(want); free(adj); jfree(R);
    return rc;
}
