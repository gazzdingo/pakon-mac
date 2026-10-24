/* RE 15: Kodak NRA noise reduction (ImaNraOp<short>, operand 0x32d). Arithmetic is a verbatim
 * port of lab/nra/nra.c (bit-exact vs the in-chain oracle). */
#include "data/diag.h"
#include "nra.h"
#include "data/kodak_text.h"
#include "data/kodak_map.h"
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <stddef.h>
#include <unistd.h>

#define BANDS 3
#define ROWS 4096
#define WIN 11

/* useNoiseFalloff edit, FUN_10255c20 with the constants at 0x1020ce0f..29: x87 accumulates in
 * double, each step is stored as float; once the running value is < 0, entries 0..i are zeroed. */
static void noise_falloff(float sig[BANDS][ROWS])
{
    static const int K[BANDS] = { 700, 1000, 1300 };
    static const uint32_t S[BANDS] = { 0x3d1e54eau, 0x3d17689du, 0x3d2bb08du };
    for (int b = 0; b < BANDS; b++) {
        float s; memcpy(&s, &S[b], 4);
        double v = (double)sig[b][K[b] + 1];
        for (int i = K[b]; i > -1; i--) {
            v -= (double)s;
            if (v < 0.0) { for (int j = i; j >= 0; j--) sig[b][j] = 0.0f; break; }
            sig[b][i] = (float)v;
        }
    }
}

/* FUN_1017a6c0: (short)(int64)fistp(scale * sigma), round-half-even. */
static void build_lut(const float sig[BANDS][ROWS], float scale, pkc_lut3 *out)
{
    for (int b = 0; b < BANDS; b++)
        for (int i = 0; i < ROWS; i++) {
            double p = (double)scale * (double)sig[b][i];
            out->t[b][i] = (int16_t)(int64_t)nearbyint(p);
        }
}

pk_status pkc_nra_prepare_files(const char *tbl_path, const char *dpi_path, pkc_lut3 *thresholds)
{
    float local[BANDS][ROWS];
    if (!tbl_path || !dpi_path || !thresholds) return PK_E_ARG;

    pkc_kt *dpi = NULL, *tbl = NULL;
    pk_status st = pkc_kt_load(dpi_path, &dpi);
    if (st != PK_OK) return st;
    double scale_d, win_d;
    if (pkc_kt_num(dpi, "NoiseScale", &scale_d, 1) != 1 || pkc_kt_num(dpi, "WindowSize", &win_d, 1) != 1 ||
        win_d != (double)WIN || !(scale_d >= 0.0)) {
        pkc_kt_free(dpi);
        return PK_E_VENDOR_DATA;
    }
    pkc_kt_free(dpi);

    st = pkc_kt_load(tbl_path, &tbl);
    if (st != PK_OK) return st;
    /* 4 columns (code + 3 bands) x 4096 rows; ask for one more than expected to catch long tables. */
    double *v = malloc(sizeof(double) * (4 * ROWS + 1));
    if (!v) { pkc_kt_free(tbl); return PK_E_NOMEM; }
    int n = pkc_kt_num(tbl, "NoiseTable", v, 4 * ROWS + 1);
    pkc_kt_free(tbl);
    if (n != 4 * ROWS) { free(v); return PK_E_VENDOR_DATA; }
    unsigned char seen[ROWS];   /* every code 0..4095 must appear exactly once */
    memset(seen, 0, sizeof seen);
    for (int r = 0; r < ROWS; r++) {
        double code = v[4 * r];
        if (code < 0.0 || code >= (double)ROWS || code != (double)(int)code) { free(v); return PK_E_VENDOR_DATA; }
        if (seen[(int)code]) { free(v); return PK_E_VENDOR_DATA; }
        seen[(int)code] = 1;
        for (int b = 0; b < BANDS; b++) local[b][(int)code] = (float)v[4 * r + 1 + b];
    }
    free(v);

    noise_falloff(local);
    build_lut(local, (float)scale_d, thresholds);
    return PK_OK;
}

pk_status pkc_nra_prepare(const char *vendor_root, pkc_lut3 *thresholds)
{
    return pkc_nra_prepare_film(vendor_root, 0, thresholds);
}

pk_status pkc_nra_prepare_film(const char *vendor_root, int film_iso, pkc_lut3 *thresholds)
{
    if (!vendor_root || !thresholds) return PK_E_ARG;
    char map[1024], name[256], rel[400], tbl[1024], dpi[1024];
    pk_status st = pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/noiseTable/noiseTable.map", map, sizeof map);
    if (st != PK_OK) return st;
    /* noiseTable.map, first match: the path, sourceType 1 (35 mm negative) and the film ISO; scannerName, compression and
     * resolution are never needed by a row reached on this path (they are `any` there) */
    const pkc_map_key keys[3] = { { "_AnselPath_", PKC_MAP_STR, "CN-Enhanced", 0 }, { "sourceType", PKC_MAP_INT, NULL, 1 },
                                  { "filmIso", PKC_MAP_INT, NULL, film_iso } };
    if ((st = pkc_map_select(map, keys, 3, name, sizeof name)) != PK_OK) return st;
    if (strchr(name, '/')) return PK_E_VENDOR_DATA;
    snprintf(rel, sizeof rel, "anselinstalldir/dataPathItems/noiseTable/%s", name);
    if ((st = pkc_vendor_path(vendor_root, rel, tbl, sizeof tbl)) != PK_OK) return st;
    /* the nra dpi: nra-srcType-speed-negative35-<ISO, 4 digits>.dpi if there is one, else ...-default.dpi (RE 15, ctor
     * FUN_1020dbf0); the shipped negative35 files hold the same values */
    snprintf(rel, sizeof rel, "anselinstalldir/dataPathItems/nra/nra-srcType-speed-negative35-%04d.dpi", film_iso);
    if ((st = pkc_vendor_path(vendor_root, rel, dpi, sizeof dpi)) != PK_OK) return st;
    FILE *f = film_iso > 0 ? pkc_fopen(dpi, "r") : NULL;
    if (f) fclose(f);
    else if ((st = pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/nra/nra-srcType-speed-negative35-default.dpi", dpi, sizeof dpi)) != PK_OK)
        return st;
    return pkc_nra_prepare_files(tbl, dpi, thresholds);
}

static inline int refl101(int i, int n)   /* ImaPadOpT<short> mode 2 */
{
    if (i < 0) i = -i;
    if (i >= n) i = 2 * (n - 1) - i;
    return i;
}

/* One pixel with every tap reflected (ImaPadOpT mode 2). Used on the border band (h pixels wide) only. */
static void pixel_edge(const int16_t *in, int16_t *out, int W, int H, int x, int y, int T)
{
    const int h = WIN / 2, c = in[y * W + x];
    int32_t S = 0; int n = 0;
    for (int d = -h; d <= h; d++) {
        const int yy = refl101(y + d, H), xx = refl101(x + d, W), xm = refl101(x - d, W);
        int p;
        p = in[y * W + xx]; if (p - c < T && -T < p - c) { S += p; n++; }
        if (d == 0) continue;
        p = in[yy * W + x]; if (p - c < T && -T < p - c) { S += p; n++; }
        p = in[yy * W + xx]; if (p - c < T && -T < p - c) { S += p; n++; }
        p = in[yy * W + xm]; if (p - c < T && -T < p - c) { S += p; n++; }
    }
    out[y * W + x] = (int16_t)(S / n);
}

/* Rows [y0, y1) of one plane: 4N-3 tap star (row, column, both diagonals), centre counted once. Away from the border
 * (h <= x < W - h, h <= y < H - h) no tap reflects, so a row is done tap by tap over all its interior pixels (simple
 * loops the compiler vectorises); the sums are integers, so the order of the taps does not matter and the result is the
 * reflected walk's, bit for bit. A pixel whose threshold is <= 0 accepts no tap but its own centre (df = 0 is not < T), which
 * gives S / n = c: the same as Kodak's early copy. */
static void apply_rows(const int16_t *in, int16_t *out, int W, int H, const int16_t *lut, int y0, int y1)
{
    const int h = WIN / 2;
    int32_t *buf = NULL;
    const int nx = W - 2 * h;                                    /* interior columns */
    if (nx > 0 && y1 > h && y0 < H - h) buf = malloc((size_t)nx * 4 * sizeof *buf);
    int32_t *S = buf, *N = buf ? buf + nx : NULL, *C = buf ? buf + 2 * nx : NULL, *Tt = buf ? buf + 3 * nx : NULL;
    for (int y = y0; y < y1; y++) {
        const int16_t *row = in + (size_t)y * W;
        int16_t *orow = out + (size_t)y * W;
        const int interior_y = buf && y >= h && y < H - h;
        for (int x = 0; x < W; x++) {
            if (interior_y && x == h) x = W - h;                  /* the vector pass below covers h .. W - h - 1 */
            const int c = row[x];
            /* Kodak doesn't bounds-check; clamp only the LUT index (RE 15), comparisons use raw c */
            const int T = lut[c < 0 ? 0 : c > 4095 ? 4095 : c];
            if (T <= 0) { orow[x] = (int16_t)c; continue; }
            pixel_edge(in, out, W, H, x, y, T);
        }
        if (!interior_y) continue;
        for (int i = 0; i < nx; i++) {
            const int c = row[h + i];
            C[i] = c; Tt[i] = lut[c < 0 ? 0 : c > 4095 ? 4095 : c]; S[i] = c; N[i] = 1;
        }
        const int16_t *q = row + h;
        for (int d = 1; d <= h; d++) {
            const ptrdiff_t off[8] = { d, -d, (ptrdiff_t)d * W, -(ptrdiff_t)d * W, (ptrdiff_t)d * (W + 1), -(ptrdiff_t)d * (W + 1),
                                       (ptrdiff_t)d * (W - 1), -(ptrdiff_t)d * (W - 1) };
            for (int k = 0; k < 8; k++) {
                const int16_t *t = q + off[k];
                for (int i = 0; i < nx; i++) {
                    const int p = t[i], df = p - C[i], T = Tt[i];
                    const int ok = (df < T) & (-T < df);
                    S[i] += ok ? p : 0;
                    N[i] += ok;
                }
            }
        }
        for (int i = 0; i < nx; i++) orow[h + i] = (int16_t)(S[i] / N[i]);
    }
    free(buf);
}

/* Row bands of all three planes on up to PKC_NRA_THREADS threads: the output pixels are independent (each reads only the
 * input), so any split gives the same bits. Small images stay on the calling thread. */
#define PKC_NRA_THREADS 8
#define PKC_NRA_PAR_MIN 400000          /* pixels per plane below which a thread costs more than it saves */
typedef struct { const int16_t *in; int16_t *out; int W, H; const int16_t *lut; int y0, y1; } nra_task;
typedef struct { const nra_task *task; int n, first, step; } nra_worker;
static void *nra_run(void *arg)
{
    const nra_worker *w = arg;
    for (int k = w->first; k < w->n; k += w->step) {
        const nra_task *t = &w->task[k];
        apply_rows(t->in, t->out, t->W, t->H, t->lut, t->y0, t->y1);
    }
    return NULL;
}

static void apply_all(const pkc_planes *in, pkc_planes *out, const pkc_lut3 *thr, int threads)
{
    const int W = in->w, H = in->h;
    long ncpu = threads > 0 ? threads : sysconf(_SC_NPROCESSORS_ONLN);   /* threads: 0 = automatic, 1 = calling thread only */
    int nt = (int)(ncpu < 1 ? 1 : ncpu > PKC_NRA_THREADS ? PKC_NRA_THREADS : ncpu);
    if ((long long)W * H < PKC_NRA_PAR_MIN || nt < 2) {
        for (int b = 0; b < BANDS; b++) apply_rows(in->p[b], out->p[b], W, H, thr->t[b], 0, H);
        return;
    }
    enum { NB = 8, MAXTASK = BANDS * NB };               /* 8 row bands per plane: 24 tasks dealt over the workers */
    nra_task task[MAXTASK]; int nk = 0;
    for (int b = 0; b < BANDS; b++)
        for (int k = 0; k < NB; k++) {
            int y0 = (int)((long long)H * k / NB), y1 = (int)((long long)H * (k + 1) / NB);
            task[nk++] = (nra_task){ in->p[b], out->p[b], W, H, thr->t[b], y0, y1 };
        }
    nra_worker wk[PKC_NRA_THREADS]; pthread_t th[PKC_NRA_THREADS]; int live[PKC_NRA_THREADS] = { 0 };
    for (int w = 0; w < nt; w++) wk[w] = (nra_worker){ task, nk, w, nt };
    for (int w = 1; w < nt; w++) live[w] = pthread_create(&th[w], NULL, nra_run, &wk[w]) == 0;
    nra_run(&wk[0]);
    for (int w = 1; w < nt; w++) {
        if (live[w]) pthread_join(th[w], NULL);
        else nra_run(&wk[w]);                            /* no thread could be made: do its share here */
    }
}

pk_status pkc_nra_apply(const pkc_planes *in, pkc_planes *out, const pkc_lut3 *thr)
{
    return pkc_nra_apply_t(in, out, thr, 0);
}

pk_status pkc_nra_apply_t(const pkc_planes *in, pkc_planes *out, const pkc_lut3 *thr, int threads)
{
    if (threads < 0) return PK_E_ARG;
    if (!in || !out || !thr || in->w != out->w || in->h != out->h) return PK_E_ARG;
    for (int b = 0; b < BANDS; b++) if (!in->p[b] || !out->p[b] || in->p[b] == out->p[b]) return PK_E_ARG;
    if (in->w < WIN || in->h < WIN) return PK_E_IMAGE_TOO_SMALL;
    apply_all(in, out, thr, threads);
    return PK_OK;
}
