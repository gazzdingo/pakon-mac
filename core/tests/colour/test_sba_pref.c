/* Task 13: the SBA triple (FUN_1028ae00 + the FOS-pointer count / weight), Preference (mode 0) and setShifts (1,2)
 * against Kodak at x87 PC53 (vectors/sba_pref_truth.pkv, lab/vectors/gen_t13_truth.py, lab/rollbal/truth/t13).
 * Entries: r4 / r2 / r1 / r12 (Task 11's Kodak film base), r4v1 / r2v1 (v1's film base: RE 16 / 17, the brief's numbers),
 * synf / syns (Task 12's crafted rolls), t15w..t15q (Task 15's), t13g / t13b (FOS#1 gmSlope 1667 / illSlope 2550: the
 * slope-limit fallback, lab/rollbal/gen_t13syn.py) and p13 (r4 with the slope words poked to +-1500 / +-1501 at single
 * calls: the fallback's exact boundaries), q13m / q13s / q13r (crafted arguments poked into Kodak's calls by
 * lab/rollbal/gen_t13poke.py: the selected count at par[9], a sample at a^2 + b^2 = 2000^2, s3 = 30 / 80, twelve crafted
 * Preference inputs -- every boundary of these functions no roll reaches). Makesfs: the shipped sfsTable35 and four other shipped row files, each
 * Kodak's table. Grids of the rolls Task 15 covers come from fos_truth.pkv (asserted equal by the generator). */
#include "greatest.h"
#include "pkv.h"
#include "analysis/sba_pref.h"
#include "analysis/scplut.h"
#include "analysis/exposure.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static pkc_sba_ctx CTX;
static pkc_fos_params FP;
static pkc_scplut_params SP;
static pkc_sba_pref PREF;
static int ctx_ok;
static int need_ctx(void) {
    if (!ctx_ok)
        ctx_ok = pkc_sba_ctx_load(VENDOR_ROOT, DERIVED_ROOT, &CTX) == PK_OK && pkc_fos_params_load(VENDOR_ROOT, &FP) == PK_OK &&
                 pkc_scplut_params_load(VENDOR_ROOT, &SP) == PK_OK && pkc_sba_pref_load(VENDOR_ROOT, DERIVED_ROOT, &PREF) == PK_OK;
    return ctx_ok;
}
static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }
static const int16_t *i16(const pkv_array *a) { return (const int16_t *)a->data; }
static const uint8_t *u8(const pkv_array *a) { return (const uint8_t *)a->data; }

#define CHECK(cond) do { if (!(cond)) { fail_line = __LINE__; fail_expr = #cond; goto done; } } while (0)
#define FINISH() do { if (fail_line) { static char fmsg[300]; snprintf(fmsg, sizeof fmsg, "line %d: %s (%s)", fail_line, fail_expr, detail); FAILm(fmsg); } PASS(); } while (0)
#define NENT 20
static const char *const ROLLS[NENT] = { "r4", "r2", "r1", "r12", "r4v1", "synf", "syns", "t15w", "t15t", "t15s", "t15e", "t15p",
                                         "t15q", "t13g", "t13b", "p13", "q13m", "q13s", "q13r", "r2v1" };

/* one truth entry */
typedef struct {
    int n, mode, kind;                 /* kind: 0 a plain run, 1..4 crafted arguments (sba_pref_truth meta[3]) */
    const int16_t *bands, *par, *ptri, *pblob;   /* kind 2 / 3 / 4: what the poked calls read */
    const int16_t *grid[2];            /* per instance: n x 3 x 864 */
    const int16_t *hdr, *fos, *pref, *ss, *lutv;
    const int32_t *vec8, *L, *uv;
    const uint8_t *mask;
} entry;
static int get_entry(const pkv_file *t, const pkv_file *ft, int e, entry *x) {
    char nm[48];
#define GET(sfx) (snprintf(nm, sizeof nm, "e%d_%s", e, sfx), pkv_get(t, nm))
    const pkv_array *meta = GET("meta");
    if (!meta || meta->n != 6) return 0;
    const int32_t *m = i32(meta);
    x->n = m[1]; x->mode = m[2]; x->kind = m[3];
    x->bands = x->par = x->ptri = x->pblob = NULL;
    const pkv_array *o;
    if (x->kind == 2) { if (!(o = GET("bands")) || (int)o->n != 2 * x->n * 3 * PKC_GRID_N) return 0; x->bands = i16(o); }
    if (x->kind == 3) { if (!(o = GET("par")) || (int)o->n != 2 * x->n * 28) return 0; x->par = i16(o); }
    if (x->kind == 4) {
        if (!(o = GET("ptri")) || (int)o->n != 2 * x->n * 3) return 0;
        x->ptri = i16(o);
        if (!(o = GET("pblob")) || (int)o->n != 2 * x->n * 36) return 0;
        x->pblob = i16(o);
    }
    if (m[4] < 0) {
        const pkv_array *g = GET("grid");
        if (!g || (int)g->n != 2 * x->n * 3 * PKC_GRID_N) return 0;
        x->grid[0] = i16(g); x->grid[1] = i16(g) + x->n * 3 * PKC_GRID_N;
    } else {
        for (int i = 0; i < 2; i++) {
            snprintf(nm, sizeof nm, "f%d_grid", m[4 + i]);
            const pkv_array *g = pkv_get(ft, nm);
            if (!g || (int)g->n != x->n * 3 * PKC_GRID_N) return 0;
            x->grid[i] = i16(g);
        }
    }
    const pkv_array *a[10] = { GET("hdr"), GET("fos"), GET("pref"), GET("ss"), GET("lutv"), GET("vec8"), GET("L"), GET("uv"), GET("mask"), NULL };
    for (int i = 0; i < 9; i++) if (!a[i]) return 0;
    int h = 2 * x->n;
    if ((int)a[0]->n != h * 16 || (int)a[1]->n != h * 18 || (int)a[2]->n != h * 10 || (int)a[3]->n != x->n * 9 ||
        (int)a[4]->n != x->n * 3 || (int)a[5]->n != h * 8 || (int)a[6]->n != h || (int)a[7]->n != h * 6 || (int)a[8]->n != h * PKC_GRID_N)
        return 0;
    x->hdr = i16(a[0]); x->fos = i16(a[1]); x->pref = i16(a[2]); x->ss = i16(a[3]); x->lutv = i16(a[4]);
    x->vec8 = i32(a[5]); x->L = i32(a[6]); x->uv = i32(a[7]); x->mask = u8(a[8]);
#undef GET
    return 1;
}
static void fos_from_words(const int16_t *w, pkc_fos_result *f) {
    memset(f, 0, sizeof *f);
    for (int c = 0; c < 3; c++) { f->order_fpo[c] = w[c]; f->order_avg[c] = w[3 + c]; f->dmin[c] = w[6 + c]; }
    f->gm_slope = w[9]; f->gm_off = w[10]; f->ill_slope = w[11]; f->ill_off = w[12];
    f->ofpo_method = w[14]; f->num_pixels = w[15]; f->gm_rsq = w[16]; f->ill_rsq = w[17]; f->valid = 1;
}
/* the measure output for a grid: bands = the opening axes per sample (Kodak's measure image planes 3-5) */
static void bands_from_grid(const int16_t *g, pkc_sba_measure *m) {
    for (int i = 0; i < PKC_GRID_N; i++)
        pkc_sba_axes(g[i], g[PKC_GRID_N + i], g[2 * PKC_GRID_N + i], &m->Yband[i], &m->C1band[i], &m->C2band[i]);
}
/* compare a triple result with Kodak's hit h of entry x */
static int same_triple(const pkc_sba_triple_out *o, const entry *x, int h, char *detail, size_t cap, const char *what) {
    const int32_t *uv = x->uv + 6 * h; const int16_t *pr = x->pref + 10 * h, *hd = x->hdr + 16 * h;
    int32_t got[11] = { o->triple[0], o->triple[1], o->triple[2], o->out4, o->out8, o->nsel, o->p15[0], o->p15[1], o->p15[2], o->flag, x->mode ? o->count : 0 };
    int32_t want[11] = { pr[0], pr[1], pr[2], uv[0], uv[1], uv[2], uv[3], uv[4], uv[5], pr[3], hd[11] };
    static const char *const nm[11] = { "Y", "C1", "C2", "out4", "out8", "nsel", "p15.0", "p15.1", "p15.2", "flag", "count" };
    for (int j = 0; j < 11; j++)
        if (got[j] != want[j]) { snprintf(detail, cap, "%s hit %d %s: port %d kodak %d", what, h, nm[j], (int)got[j], (int)want[j]); return 0; }
    if (x->mode && o->s2 != hd[12]) { snprintf(detail, cap, "%s hit %d s2: port %d kodak %d", what, h, (int)o->s2, hd[12]); return 0; }
    return 1;
}
static int same_pref(const int32_t triple[3], const entry *x, int h, char *detail, size_t cap) {
    int16_t sh[3], an[3]; const int16_t *pr = x->pref + 10 * h;
    pkc_sba_pref pf = PREF; int32_t t[3] = { triple[0], triple[1], triple[2] };
    if (x->kind == 4) {                                     /* Preference read a crafted triple and block */
        for (int c = 0; c < 3; c++) t[c] = x->ptri[3 * h + c];
        memcpy(pf.blob, x->pblob + 36 * h, sizeof pf.blob);
    }
    if (pkc_preference_shift(t, &pf, 0, sh, an) != PK_OK) { snprintf(detail, cap, "hit %d Preference failed", h); return 0; }
    for (int c = 0; c < 3; c++)
        if (an[c] != pr[4 + c] || sh[c] != pr[7 + c]) {
            snprintf(detail, cap, "hit %d Preference ch %d: anchor %d/%d shift %d/%d (port/kodak)", h, c, an[c], pr[4 + c], sh[c], pr[7 + c]);
            return 0;
        }
    return 1;
}

/* Kodak's inputs to FUN_1028ae00 (its grid -> bands, L, scene slots 0..7 and mask, the FOS words it read) -> the port's
 * triple, U / V terms, counts, flag, count / s2 = Kodak's; Preference on Kodak's triple = Kodak's anchor and shift
 * words; setShifts on Kodak's A / B and the scpLut entries Kodak read = Kodak's OUT. Every hit of every entry. */
TEST kodak_core(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[200] = "";
    pkv_file *t = NULL, *ft = NULL; pkc_sba_measure *m = NULL; pkc_sba_scene *sc = NULL; pkc_lut3 *lut = NULL; pkc_sba_ctx *cx = NULL;
    int nhit = 0, nflag[4] = { 0, 0, 0, 0 }, nblend = 0;
    if (!need_ctx()) FAILm("load failed");
    t = pkv_open(PKV_DIR "/sba_pref_truth.pkv"); CHECK(t);
    ft = pkv_open(PKV_DIR "/fos_truth.pkv"); CHECK(ft);
    m = malloc(sizeof *m); sc = malloc(sizeof *sc); lut = calloc(1, sizeof *lut); cx = malloc(sizeof *cx); CHECK(m && sc && lut && cx);
    const pkv_array *NE = pkv_get(t, "n"); CHECK(NE && i32(NE)[0] == NENT);
    for (int e = 0; e < NENT; e++) {
        entry x; CHECK(get_entry(t, ft, e, &x));
        for (int h = 0; h < 2 * x.n; h++) {
            snprintf(detail, sizeof detail, "%s hit %d", ROLLS[e], h);
            bands_from_grid(x.grid[h / x.n] + (h % x.n) * 3 * PKC_GRID_N, m);
            if (x.kind == 2)                                /* the measure image's bands as Kodak read them (two words poked) */
                for (int i = 0; i < PKC_GRID_N; i++) {
                    const int16_t *b = x.bands + h * 3 * PKC_GRID_N;
                    m->Yband[i] = b[i]; m->C1band[i] = b[PKC_GRID_N + i]; m->C2band[i] = b[2 * PKC_GRID_N + i];
                }
            *cx = CTX;                                      /* (shares CTX's p-code program; never freed) */
            if (x.kind == 3)
                for (int j = 0; j < 28; j++) { uint16_t w = (uint16_t)x.par[28 * h + j]; cx->params[0xDC + 2 * j] = (uint8_t)w; cx->params[0xDD + 2 * j] = (uint8_t)(w >> 8); }
            m->L = x.L[h];
            pkc_sba_scene_init(sc);
            for (int j = 0; j < 8; j++) sc->vec[j] = x.vec8[8 * h + j];
            memcpy(sc->mask, x.mask + h * PKC_GRID_N, PKC_GRID_N);
            pkc_fos_result f; fos_from_words(x.fos + 18 * h, &f);
            pkc_sba_triple_out o;
            CHECK(pkc_sba_triple(m, sc, cx, &PREF, x.mode ? PKC_SBA_FOS2 : PKC_SBA_SHORT2, x.mode ? &f : NULL, &o) == PK_OK);
            if (!same_triple(&o, &x, h, detail, sizeof detail, ROLLS[e])) CHECK(0);
            if (!same_pref(o.triple, &x, h, detail, sizeof detail)) CHECK(0);
            nflag[o.flag == 0 ? 0 : o.flag == 100 ? 1 : o.flag == 200 ? 2 : 3]++;
            if (x.mode && o.s2 > 0) nblend++;
            nhit++;
        }
        for (int k = 0; k < x.n; k++) {
            const int16_t *s = x.ss + 9 * k;
            for (int c = 0; c < 3; c++) lut->t[c][1550 - s[c]] = x.lutv[3 * k + c];
            int16_t out[3];
            CHECK(pkc_setshifts_12(s, s + 3, lut, out) == PK_OK);
            snprintf(detail, sizeof detail, "%s scene %d setShifts: port %d %d %d kodak %d %d %d", ROLLS[e], k, out[0], out[1], out[2], s[6], s[7], s[8]);
            CHECK(out[0] == s[6] && out[1] == s[7] && out[2] == s[8]);
            for (int c = 0; c < 3; c++) lut->t[c][1550 - s[c]] = 0;
        }
    }
    /* every arm Kodak ran is covered: FOS lines (flag 0), slope-limit fallback (100), mode 0 (200); s2 > 0 blends */
    snprintf(detail, sizeof detail, "%d hits, flags 0:%d 100:%d 200:%d other:%d, %d blends", nhit, nflag[0], nflag[1], nflag[2], nflag[3], nblend);
    CHECK(nhit == 160 && nflag[0] == 128 && nflag[1] == 16 && nflag[2] == 16 && !nflag[3] && nblend == 20);
done:
    free(m); free(sc); free(lut); free(cx); pkv_close(t); pkv_close(ft);
    FINISH();
}

/* Kodak's exposure words (scene+0x38fc) of roll `id`'s 2n writer calls (exposure_truth.pkv, Task 18), or NULL */
static const int32_t *exposure_words(const pkv_file *xt, const char *id, int n) {
    char nm[32]; snprintf(nm, sizeof nm, "e%d_hs", pkv_list_index(xt, "names", id));
    const pkv_array *a = pkv_get(xt, nm);
    return a && a->dtype == 4 && (int)a->n == 2 * n ? i32(a) : NULL;
}

/* The whole roll feed from Kodak's grids: the port's pass 1 (Task 12) on every scene of an instance, FOS (Task 15) on
 * those states (its 18 words = what Kodak's triple read), the port's pass 2 (vector slots 3..5, mask and L = Kodak's
 * scene object), the triple and its exposure word (Task 18: Kodak's scene+0x38fc, exposure_truth.pkv), Preference;
 * then the roll scpLut from FOS#1 (Task 16; the entries setShifts reads = Kodak's) and setShifts on the port's two shift
 * triples = Kodak's pre-flesh words. Every entry but the poke run. */
TEST kodak_chain(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[200] = "";
    pkv_file *t = NULL, *ft = NULL, *xt = NULL; pkc_sba_measure *m = NULL; pkc_sba_scene *sc = NULL; pkc_lut3 *lut = NULL;
    int32_t (*grid)[3][PKC_GRID_N] = NULL; uint16_t (*dm)[3] = NULL;
    int nscene = 0;
    if (!need_ctx()) FAILm("load failed");
    t = pkv_open(PKV_DIR "/sba_pref_truth.pkv"); CHECK(t);
    ft = pkv_open(PKV_DIR "/fos_truth.pkv"); CHECK(ft);
    xt = pkv_open(PKV_DIR "/exposure_truth.pkv"); CHECK(xt);
    m = malloc(sizeof *m); sc = calloc(8, sizeof *sc); lut = malloc(sizeof *lut); grid = calloc(8, sizeof *grid); dm = calloc(8, sizeof *dm);
    CHECK(m && sc && lut && grid && dm);
    for (int e = 0; e < NENT; e++) {
        entry x; CHECK(get_entry(t, ft, e, &x));
        if (x.kind) continue;
        CHECK(x.n <= 8);
        const int32_t *xw = exposure_words(xt, ROLLS[e], x.n);
        snprintf(detail, sizeof detail, "%s: no exposure truth", ROLLS[e]);
        CHECK(xw);
        int16_t shift[2][8][3];
        pkc_fos_result fos1; memset(&fos1, 0, sizeof fos1);
        for (int inst = 0; inst < 2; inst++) {
            for (int k = 0; k < x.n; k++) {
                const int16_t *g = x.grid[inst] + k * 3 * PKC_GRID_N;
                for (int i = 0; i < 3 * PKC_GRID_N; i++) grid[k][i / PKC_GRID_N][i % PKC_GRID_N] = g[i];
                for (int c = 0; c < 3; c++) dm[k][c] = (uint16_t)x.hdr[16 * (inst * x.n + k) + c];
                pkc_sba_scene_init(&sc[k]);
                CHECK(pkc_sba_measure_scene(NULL, (const int32_t (*)[PKC_GRID_N])grid[k], NULL, &CTX, PKC_SBA_PASS1, &sc[k], m) == PK_OK);
            }
            pkc_fos_result f; memset(&f, 0, sizeof f);
            if (x.mode) {
                CHECK(pkc_fos_roll(&CTX, &FP, x.n, (const int32_t (*)[3][PKC_GRID_N])grid, (const uint16_t (*)[3])dm, sc, &f) == PK_OK);
                const int16_t *w = x.fos + 18 * inst * x.n;
                int32_t got[13] = { f.order_fpo[0], f.order_fpo[1], f.order_fpo[2], f.order_avg[0], f.order_avg[1], f.order_avg[2],
                                    f.dmin[0], f.dmin[1], f.dmin[2], f.gm_slope, f.gm_off, f.ill_slope, f.ill_off };
                for (int j = 0; j < 13; j++) {
                    snprintf(detail, sizeof detail, "%s FOS#%d word %d: port %d kodak %d", ROLLS[e], inst + 1, j, (int)got[j], w[j]);
                    CHECK(got[j] == w[j]);
                }
                CHECK(f.valid);
                if (inst == 0) fos1 = f;
            }
            for (int k = 0; k < x.n; k++) {
                int h = inst * x.n + k;
                snprintf(detail, sizeof detail, "%s hit %d pass 2", ROLLS[e], h);
                CHECK(pkc_sba_measure_scene(NULL, (const int32_t (*)[PKC_GRID_N])grid[k], NULL, &CTX, x.mode ? PKC_SBA_FOS2 : PKC_SBA_SHORT2, &sc[k], m) == PK_OK);
                CHECK(m->L == x.L[h] && !memcmp(sc[k].mask, x.mask + h * PKC_GRID_N, PKC_GRID_N));
                for (int j = 3; j < 6; j++) CHECK(sc[k].known[j] && sc[k].vec[j] == x.vec8[8 * h + j]);
                pkc_sba_triple_out o;
                CHECK(pkc_sba_triple(m, &sc[k], &CTX, &PREF, x.mode ? PKC_SBA_FOS2 : PKC_SBA_SHORT2, x.mode ? &f : NULL, &o) == PK_OK);
                if (!same_triple(&o, &x, h, detail, sizeof detail, ROLLS[e])) CHECK(0);
                if (!same_pref(o.triple, &x, h, detail, sizeof detail)) CHECK(0);
                double st = 99;
                CHECK(pkc_sba_exposure_stops(&o, &CTX, &st) == PK_OK);
                snprintf(detail, sizeof detail, "%s hit %d exposure: port %g kodak %d half-stops", ROLLS[e], h, st, xw[h]);
                CHECK(st == xw[h] * 0.5);
                CHECK(pkc_preference_shift(o.triple, &PREF, 0, shift[inst][k], NULL) == PK_OK);
                nscene++;
            }
        }
        /* the roll scpLut (no FOS: seven zero words -> identity) and setShifts */
        CHECK(pkc_scplut_build(&SP, &fos1, lut, NULL) == PK_OK);
        for (int k = 0; k < x.n; k++) {
            const int16_t *s = x.ss + 9 * k;
            for (int c = 0; c < 3; c++) {
                snprintf(detail, sizeof detail, "%s scene %d ch %d: scpLut[%d] port %d kodak %d", ROLLS[e], k, c, 1550 - s[c], lut->t[c][1550 - s[c]], x.lutv[3 * k + c]);
                CHECK(shift[0][k][c] == s[c] && shift[1][k][c] == s[3 + c] && lut->t[c][1550 - s[c]] == x.lutv[3 * k + c]);
            }
            int16_t out[3];
            CHECK(pkc_setshifts_12(shift[0][k], shift[1][k], lut, out) == PK_OK);
            snprintf(detail, sizeof detail, "%s scene %d pre-flesh: port %d %d %d kodak %d %d %d", ROLLS[e], k, out[0], out[1], out[2], s[6], s[7], s[8]);
            CHECK(out[0] == s[6] && out[1] == s[7] && out[2] == s[8]);
        }
    }
    snprintf(detail, sizeof detail, "%d scene passes", nscene);
    CHECK(nscene == 128);
done:
    free(m); free(sc); free(lut); free(grid); free(dm); pkv_close(t); pkv_close(ft); pkv_close(xt);
    FINISH();
}

/* RE 16 section 3's table and RE 17's r2 blend weights (the brief's numbers, recorded at PC64 on v1's film base): Kodak's
 * at PC53 too -- entries r4v1 and r2v1. */
TEST brief_numbers(void) {
    pkv_file *t = pkv_open(PKV_DIR "/sba_pref_truth.pkv"), *ft = pkv_open(PKV_DIR "/fos_truth.pkv");
    entry x; int ok = t && ft && get_entry(t, ft, 4, &x) && x.n == 4;
    static const int16_t TA[4][3] = { { 2099, 57, 514 }, { 1855, 50, 518 }, { 1689, 63, 498 }, { 2284, 51, 487 } };
    static const int16_t TB[4][3] = { { 2052, 96, 452 }, { 1795, 84, 460 }, { 1635, 94, 444 }, { 2218, 91, 422 } };
    static const int16_t SA[4][3] = { { 795, 345, 43 }, { 933, 489, 176 }, { 1017, 572, 289 }, { 665, 242, -47 } };
    static const int16_t SB[4][3] = { { 794, 342, 130 }, { 939, 495, 264 }, { 1022, 577, 370 }, { 674, 248, 53 } };
    static const int16_t PF[4][3] = { { 792, 340, 128 }, { 929, 485, 255 }, { 1014, 569, 362 }, { 662, 237, 42 } };
    for (int k = 0; ok && k < 4; k++)
        for (int c = 0; c < 3; c++)
            ok = ok && x.pref[10 * k + c] == TA[k][c] && x.pref[10 * (4 + k) + c] == TB[k][c] && x.ss[9 * k + c] == SA[k][c] &&
                 x.ss[9 * k + 3 + c] == SB[k][c] && x.ss[9 * k + 6 + c] == PF[k][c];
    /* RE 17's r2 blend weights s2 = 864 / 90 (sba instance, scenes 1 / 2) and 850 / 78 (afterSCPLut): r2v1, the same
     * v1-film-base inputs (entry 19) */
    entry r; ok = ok && get_entry(t, ft, 19, &r) && r.n == 6;
    static const int16_t S2[12] = { 0, 864, 90, 0, 0, 0, 0, 850, 78, 0, 0, 0 };
    for (int h = 0; ok && h < 12; h++) ok = r.hdr[16 * h + 12] == S2[h];
    pkv_close(t); pkv_close(ft);
    ASSERT(ok);
    PASS();
}

/* The slope-limit fallback (RE 17 C, 0x1028af23..0x1028af86): |gmSlope| or |illSlope| > par[24] = 1500 -> slopes 0,
 * offsets = FOS orderFpo U / V - opening, flag 100. Kodak-pinned: t13g (gm 1667) / t13b (ill 2550) take it on their sba
 * instance; p13's pokes: +-1500 stays on the lines (flag 0), +-1501 falls back (flag 100), for gm and ill alike. */
TEST slope_limit(void) {
    pkv_file *t = pkv_open(PKV_DIR "/sba_pref_truth.pkv"), *ft = pkv_open(PKV_DIR "/fos_truth.pkv");
    entry g, b, p; int ok = t && ft && get_entry(t, ft, 13, &g) && get_entry(t, ft, 14, &b) && get_entry(t, ft, 15, &p);
    for (int h = 0; ok && h < 4; h++)
        ok = g.fos[18 * h + 9] == 1667 && g.pref[10 * h + 3] == 100 && b.fos[18 * h + 11] == 2550 && b.pref[10 * h + 3] == 100 &&
             g.uv[6 * h + 4] == g.fos[18 * h + 1] && g.uv[6 * h + 5] == g.fos[18 * h + 2];   /* C1o + l5c = orderFpo U */
    static const int16_t PW[8] = { 1500, 1501, -1500, -1501, 1500, 1501, -1500, -1501 };
    for (int h = 0; ok && h < 8; h++)
        ok = p.fos[18 * h + (h < 4 ? 9 : 11)] == PW[h] && p.pref[10 * h + 3] == (h % 2 ? 100 : 0);
    pkv_close(t); pkv_close(ft);
    ASSERT(ok);
    PASS();
}

/* The crafted-argument runs (lab/rollbal/gen_t13poke.py) reached what they were built for, at Kodak: q13m selects exactly
 * par[9] = 30 samples (means over 30 * 100), 29 (the all-sample sums over 864 * 100), and a mask-1 sample at
 * a^2 + b^2 = 2000^2 is left out (309 of 310 mask-1 samples) while one at a = 1999 counts (all 304); q13s's calls 3 / 7
 * read s3 = 30 / 80 with s2 > 0; q13r's twelve Preference calls read twelve crafted (triple, block) pairs. kodak_core
 * checks the port on all of them. */
TEST crafted_boundaries(void) {
    pkv_file *t = pkv_open(PKV_DIR "/sba_pref_truth.pkv"), *ft = pkv_open(PKV_DIR "/fos_truth.pkv");
    entry m, s, r; int ok = t && ft && get_entry(t, ft, 16, &m) && get_entry(t, ft, 17, &s) && get_entry(t, ft, 18, &r);
    ok = ok && m.kind == 2 && s.kind == 3 && r.kind == 4 && m.mode == 0 && s.mode == 2;
    int ones[4] = { 0, 0, 0, 0 };
    for (int h = 0; ok && h < 4; h++) for (int i = 0; i < PKC_GRID_N; i++) ones[h] += m.mask[h * PKC_GRID_N + i] == 1;
    ok = ok && m.uv[2] == 30 && m.uv[6 + 2] == 29 && ones[0] == 30 && ones[1] == 29 && m.uv[12 + 2] == ones[2] - 1 && m.uv[18 + 2] == ones[3];
    for (int h = 0; ok && h < 4; h++) ok = m.vec8[8 * h + 3] == 32767;
    ok = ok && s.par[28 * 2 + 17] == 30 && s.par[28 * 6 + 17] == 80 && s.par[17] == 50 && s.hdr[16 * 2 + 12] > 0 && s.hdr[16 * 6 + 12] > 0;
    ok = ok && r.n == 6 && r.ptri[0] == 1729 && r.pblob[36 * 11 + 35] == 2400;
    pkv_close(t); pkv_close(ft);
    ASSERT(ok);
    PASS();
}

/* dpi loader: the blob = Kodak's (bar the +0x2c pointer), the pcode params the triple reads = Kodak's, the SFS table =
 * Kodak's for the shipped row file and four other shipped ones (Kodak ran each in place of sfsTable35). */
TEST pref_load(void) {
    if (!need_ctx()) FAILm("load failed");
    pkv_file *t = pkv_open(PKV_DIR "/sba_pref_truth.pkv"); ASSERT(t);
    const pkv_array *B = pkv_get(t, "blob"), *P = pkv_get(t, "par"), *W = pkv_get(t, "sfs_sfsTable35");
    int ok = B && B->n == 36 && P && P->n == 28 && W && W->n == PKC_SFS_N;
    ok = ok && !memcmp(i16(B), PREF.blob, sizeof PREF.blob) && !memcmp(u8(W), PREF.sfs, PKC_SFS_N);
    for (int j = 0; ok && j < 28; j++) ok = (int16_t)(uint16_t)(CTX.params[0xDC + 2 * j] | CTX.params[0xDD + 2 * j] << 8) == i16(P)[j];
    static const char *const F[4] = { "sfsTable35.orig", "sfsTable2.new", "sfsTableDC_geoff", "sfsTable_small2new" };
    for (int i = 0; ok && i < 4; i++) {
        char path[1200], nm[64]; int8_t tab[PKC_SFS_N];
        snprintf(path, sizeof path, "%s/anselinstalldir/dataPathItems/sba/Sfs/%s", VENDOR_ROOT, F[i]);
        snprintf(nm, sizeof nm, "sfs_%s", F[i]);
        for (char *q = nm; *q; q++) if (*q == '.') *q = '_';
        const pkv_array *K = pkv_get(t, nm);
        ok = K && K->n == PKC_SFS_N && pkc_sfs_table(path, DERIVED_ROOT, tab) == PK_OK && !memcmp(tab, u8(K), PKC_SFS_N);
    }
    pkv_close(t);
    ASSERT(ok);
    pkc_sba_pref p;
    ASSERT_EQ(PK_E_ARG, pkc_sba_pref_load(NULL, DERIVED_ROOT, &p));
    ASSERT_EQ(PK_E_ARG, pkc_sba_pref_load(VENDOR_ROOT, NULL, &p));
    ASSERT_EQ(PK_E_ARG, pkc_sba_pref_load(VENDOR_ROOT, DERIVED_ROOT, NULL));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_sba_pref_load("/nonexistent", DERIVED_ROOT, &p));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_sba_pref_load(VENDOR_ROOT, "/nonexistent", &p));
    PASS();
}

/* Makesfs' row check (fcn.102b7280) and reader (0x102ac8c0) on crafted rows / files: every rejection is PK_E_VENDOR_DATA */
static pk_status build_rows(const int16_t r[6][4]) {
    int16_t sn[31]; int8_t tab[PKC_SFS_N];
    for (int k = 0; k <= 30; k++) sn[k] = (int16_t)k;           /* any sine table: only the checks matter here */
    return pkc_sfs_build(r, sn, tab);
}
static pk_status file_rows(const char *text) {
    char path[] = "/tmp/pk_t13_sfsXXXXXX"; int fd = mkstemp(path); int8_t tab[PKC_SFS_N];
    if (fd < 0) return PK_E_IO;
    FILE *f = fdopen(fd, "w"); if (!f) { close(fd); unlink(path); return PK_E_IO; }
    fputs(text, f); fclose(f);
    pk_status st = pkc_sfs_table(path, DERIVED_ROOT, tab);
    unlink(path);
    return st;
}
TEST sfs_checks(void) {
    static const int16_t ok_[6][4] = { { 10, 400, 15, 0 }, { 21, 25, 31, 0 }, { 39, 100, 42, 0 }, { 69, 55, 71, 0 }, { 100, 10, 114, 0 }, { 0, 0, 0, 0 } };
    ASSERT_EQ(PK_OK, build_rows(ok_));
    int16_t r[6][4];
#define MUT(row, col, val) do { memcpy(r, ok_, sizeof r); r[row][col] = (int16_t)(val); } while (0)
    MUT(0, 0, 0); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));            /* 0xe: no first row */
    MUT(1, 0, 121); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));          /* hue start beyond 120 */
    MUT(1, 2, 0); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));            /* 6: a half-empty row */
    MUT(1, 1, 2001); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));         /* radius beyond 2000 */
    MUT(1, 3, 101); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));          /* floor beyond 100 */
    MUT(5, 3, 1); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));            /* 6: junk in the end row */
    MUT(2, 0, 20); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));           /* 7: starts not increasing */
    MUT(2, 2, 70); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));           /* 9: a span runs into the next row */
    MUT(4, 2, 12); ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(r));           /* 9: the last span wraps over row 0's start */
    MUT(4, 2, 7); ASSERT_EQ(PK_OK, build_rows(r));                       /* ... ending before it is fine */
    static const int16_t gap[6][4] = { { 10, 400, 15, 0 }, { 80, 25, 90, 0 } };
    ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(gap));                         /* 8: a gap of 60 hues or more (15 -> 80) */
    static const int16_t one[6][4] = { { 10, 400, 30, 0 } };
    ASSERT_EQ(PK_E_VENDOR_DATA, build_rows(one));                         /* 8: a single row must span >= 60 hues */
    static const int16_t one_ok[6][4] = { { 10, 400, 80, 0 } };
    ASSERT_EQ(PK_OK, build_rows(one_ok));
    ASSERT_EQ(PK_OK, file_rows("10 400 15 0\n21 25 31 0\n39 100 42 0\n69 55 71 0\n100 10 114 0\n0 0 0 0\n"));
    ASSERT_EQ(PK_E_VENDOR_DATA, file_rows("10 400 15 0\n21 25 31 0\n39 100 42 0\n69 55 71 0\n100 10 114 0\n0 0 0 0"));   /* eof in a number */
    ASSERT_EQ(PK_E_VENDOR_DATA, file_rows("10 400 15 0\n21 25 31 0\n39 100 42 0\n"));
    {   /* no size limit (an istream): 8 KB of blank lines before the rows, and junk after the 24 numbers */
        static char big[9000];
        memset(big, '\n', 8192); big[8192] = 0;
        strcat(big, "10 400 15 0\n21 25 31 0\n39 100 42 0\n69 55 71 0\n100 10 114 0\n0 0 0 0\nnot read\n");
        ASSERT_EQ(PK_OK, file_rows(big));
    }
    ASSERT_EQ(PK_E_VENDOR_DATA, file_rows("10 400 15 0\n21 25 x 0\n39 100 42 0\n69 55 71 0\n100 10 114 0\n0 0 0 0\n"));
    ASSERT_EQ(PK_E_VENDOR_DATA, file_rows("10 400 15 0\n21 25 31 0\n39 100 42 0\n69 55 71 0\n100 10 114 0\n0 0 0 40000\n"));
    int8_t tab[PKC_SFS_N];
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_sfs_table("/nonexistent", DERIVED_ROOT, tab));
    ASSERT_EQ(PK_E_ARG, pkc_sfs_build(NULL, NULL, tab));
    PASS();
}

/* Crafted SFS row files Kodak ran in place of sfsTable35 (lab/rollbal/gen_t13poke.py SFS_CASES): a gap of 2 (one blended
 * hue), gaps of 60 (rejected: PIBegin -20) and 59, a wrapping span ending on row 0's start (rejected) and one before it,
 * a plain span ending on the next row's start (rejected) and one before it, floors 50 -> 49 across a gap of 2 (the
 * blended floor's half-away rounding of -1/2).
 * The port's reader + Makesfs accept exactly what Kodak accepted, with Kodak's table. */
TEST sfs_crafted(void) {
    pkv_file *t = pkv_open(PKV_DIR "/sba_pref_truth.pkv"); ASSERT(t);
    static const char *const C[8] = { "gap2", "gap60", "gap59", "wrap9", "wrap8", "touch9", "touch8", "floor49" };
    int ok = 1, nacc = 0;
    for (int i = 0; ok && i < 8; i++) {
        char nm[48], text[400] = ""; int8_t tab[PKC_SFS_N];
        snprintf(nm, sizeof nm, "sfsc_%s_rows", C[i]);
        const pkv_array *R = pkv_get(t, nm);
        snprintf(nm, sizeof nm, "sfsc_%s_tab", C[i]);
        const pkv_array *K = pkv_get(t, nm);
        ok = R && R->n == 24;
        for (int k = 0; ok && k < 6; k++) {
            char line[64]; const int16_t *r = i16(R) + 4 * k;
            snprintf(line, sizeof line, "%d %d %d %d\n", r[0], r[1], r[2], r[3]); strcat(text, line);
        }
        char path[] = "/tmp/pk_t13_sfscXXXXXX"; int fd = ok ? mkstemp(path) : -1;
        FILE *f = fd >= 0 ? fdopen(fd, "w") : NULL;
        ok = ok && f; if (f) { fputs(text, f); fclose(f); }
        pk_status st = ok ? pkc_sfs_table(path, DERIVED_ROOT, tab) : PK_E_IO;
        if (fd >= 0) unlink(path);
        if (K) { ok = ok && st == PK_OK && K->n == PKC_SFS_N && !memcmp(tab, u8(K), PKC_SFS_N); nacc++; }
        else ok = ok && st == PK_E_VENDOR_DATA;
    }
    pkv_close(t);
    ASSERT(ok);
    ASSERT_EQ(5, nacc);
    PASS();
}

/* R18: the triple reads vector slots 3, 4 and 5; each must be known[] */
TEST unknown_slot(void) {
    if (!need_ctx()) FAILm("load failed");
    pkc_sba_measure *m = calloc(1, sizeof *m); pkc_sba_scene *sc = malloc(sizeof *sc);
    pkc_fos_result f; memset(&f, 0, sizeof f); f.valid = 1;
    pkc_sba_triple_out o; int ok = m && sc;
    if (ok) pkc_sba_scene_init(sc);
    ok = ok && pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_OK;
    for (int j = 3; ok && j < 6; j++) {
        sc->known[j] = 0;
        ok = pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_E_VENDOR_DATA &&
             pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_FOS2, &f, &o) == PK_E_VENDOR_DATA;
        sc->known[j] = 1;
    }
    free(m); free(sc);
    ASSERT(ok);
    PASS();
}

/* argument and data guards; the no-table arm (flag word 0x2000, from the disassembly: no Kodak run sets it) */
TEST bad_args(void) {
    if (!need_ctx()) FAILm("load failed");
    pkc_sba_measure *m = calloc(1, sizeof *m); pkc_sba_scene *sc = malloc(sizeof *sc); pkc_sba_ctx *c2 = malloc(sizeof *c2);
    ASSERT(m && sc && c2);
    pkc_sba_scene_init(sc);
    pkc_fos_result f; memset(&f, 0, sizeof f); f.valid = 1;
    pkc_sba_triple_out o;
    int ok = pkc_sba_triple(NULL, sc, &CTX, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_E_ARG &&
             pkc_sba_triple(m, NULL, &CTX, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_E_ARG &&
             pkc_sba_triple(m, sc, NULL, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_E_ARG &&
             pkc_sba_triple(m, sc, &CTX, NULL, PKC_SBA_SHORT2, NULL, &o) == PK_E_ARG &&
             pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_SHORT2, NULL, NULL) == PK_E_ARG &&
             pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_PASS1, &f, &o) == PK_E_ARG &&
             pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_FOS2, NULL, &o) == PK_E_ARG;
    f.valid = 0; ok = ok && pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_FOS2, &f, &o) == PK_E_ARG; f.valid = 1;
    m->Yband[5] = 32768; ok = ok && pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_E_ARG;
    m->Yband[5] = 0; m->C2band[7] = -32769; ok = ok && pkc_sba_triple(m, sc, &CTX, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_E_ARG;
    m->C2band[7] = 0;
    /* the alternative weight tables (flags[3] 1..3 with flags[2] 0) are not extracted (R12) */
    *c2 = CTX; c2->flags[3] = 1; c2->flags[2] = 0;
    ok = ok && pkc_sba_triple(m, sc, c2, &PREF, PKC_SBA_FOS2, &f, &o) == PK_E_VENDOR_DATA &&
         pkc_sba_triple(m, sc, c2, &PREF, PKC_SBA_SHORT2, NULL, &o) == PK_OK;     /* mode 0 never switches tables */
    *c2 = CTX; c2->flags[3] = 3; c2->flags[2] = 1; c2->flags[4] = 1;
    ok = ok && pkc_sba_triple(m, sc, c2, &PREF, PKC_SBA_FOS2, &f, &o) == PK_E_VENDOR_DATA;
    *c2 = CTX; c2->flags[3] = 2; c2->flags[2] = 1;                                  /* flags[4] != 1: default table */
    ok = ok && pkc_sba_triple(m, sc, c2, &PREF, PKC_SBA_FOS2, &f, &o) == PK_OK;
    /* flag word 0x2000: no weight table -> out4 / out8 = slots 4 / 5, p15 = the opening axes, flag 0xcb */
    *c2 = CTX; c2->flagsword = 0x2000; sc->vec[4] = -27; sc->vec[5] = 310; m->L = 70;
    ok = ok && pkc_sba_triple(m, sc, c2, &PREF, PKC_SBA_FOS2, &f, &o) == PK_OK && o.out4 == -27 && o.out8 == 310 && o.flag == 0xcb &&
         o.triple[0] == 2099 && o.triple[1] == 96 - 27 && o.triple[2] == 359 + 310 && o.p15[0] == 2029 && o.p15[2] == 359;
    free(m); free(sc); free(c2);
    ASSERT(ok);
    PASS();
}

/* setShifts reads the scpLut as one flat table (docs/re/26 section 4; the Kodak pokes are in test_branches): an index off
 * its band reads the neighbouring band, one outside the 3 x 4096 table is refused (Kodak reads its heap) */
TEST setshifts_index(void) {
    pkc_lut3 *lut = malloc(sizeof *lut); ASSERT(lut);
    int16_t *flat = &lut->t[0][0];
    for (int i = 0; i < 3 * 4096; i++) flat[i] = (int16_t)((i * 7) % 2000 - 1000);   /* distinct per flat index (mod 2000) */
    const int16_t B[3] = { 0, 0, 0 };
    int16_t o1[3], o2[3], keep[3] = { 77, 77, 77 };
    /* in-table spills: (ar, ag, ab) = (4096, -1, -1) reads flat 4096, 4095, 8191 -- the same values a table m reads at its
     * plain in-band index 0 (A2) once m's entries there are set to those flat values */
    const int16_t A1[3] = { 1550 - 4096, 1550 + 1, 1550 + 1 }, A2[3] = { 1550, 1550, 1550 };
    ASSERT_EQ(PK_OK, pkc_setshifts_12(A1, B, lut, o1));
    pkc_lut3 *m = malloc(sizeof *m); ASSERT(m);
    memcpy(m, lut, sizeof *m);
    m->t[0][0] = flat[4096]; m->t[1][0] = flat[4095]; m->t[2][0] = flat[8191];
    ASSERT_EQ(PK_OK, pkc_setshifts_12(A2, B, m, o2));
    ASSERT_MEM_EQ(o2, o1, sizeof o1);
    /* the edges of the table: flat 0 (plane 0 index 0) and 12287 (plane 2 index 4095) are in, -1 and 12288 are out */
    const int16_t E1[3] = { 1550, 1550 - 4095 + 4096 * 0, 1550 - 4095 }, E2[3] = { 1551, 1550, 1550 }, E3[3] = { 1550, 1550, 1550 - 4096 };
    ASSERT_EQ(PK_OK, pkc_setshifts_12(E1, B, lut, o1));
    memcpy(o1, keep, sizeof keep);
    ASSERT_EQ(PK_E_UNSUPPORTED, pkc_setshifts_12(E2, B, lut, o1));      /* ar = -1: flat -1 */
    ASSERT_MEM_EQ(keep, o1, sizeof keep);
    ASSERT_EQ(PK_E_UNSUPPORTED, pkc_setshifts_12(E3, B, lut, o1));      /* ab = 4096: flat 12288 */
    ASSERT_MEM_EQ(keep, o1, sizeof keep);
    const int16_t E4[3] = { 1550 - 4095, 1551, 1550 - 4096 + 1 };         /* flat 4095, 4095, 12287 */
    ASSERT_EQ(PK_OK, pkc_setshifts_12(E4, B, lut, o1));
    ASSERT_EQ(PK_E_ARG, pkc_setshifts_12(NULL, B, lut, o1)); ASSERT_EQ(PK_E_ARG, pkc_setshifts_12(A1, NULL, lut, o1));
    ASSERT_EQ(PK_E_ARG, pkc_setshifts_12(A1, B, NULL, o1)); ASSERT_EQ(PK_E_ARG, pkc_setshifts_12(A1, B, lut, NULL));
    free(lut); free(m);
    PASS();
}

/* R24: Preference takes Kodak's mode word (scene+0x5074); only mode 0 is ported. Kodak reads the low byte only (lo =
 * mode & 0x0f, hi = mode & 0xf0), so bits above it change nothing; any other low byte is PK_E_UNSUPPORTED, untouched
 * outputs. */
TEST preference_mode(void) {
    if (!need_ctx()) FAILm("load failed");
    const int32_t tri[3] = { 2099, 57, 514 };
    int16_t s0[3], a0[3], s1[3] = { 7, 7, 7 }, a1[3] = { 7, 7, 7 };
    ASSERT_EQ(PK_OK, pkc_preference_shift(tri, &PREF, 0, s0, a0));
    static const int16_t want[3] = { 795, 345, 43 };      /* r4 scene 0 (Kodak) */
    ASSERT_MEM_EQ(want, s0, sizeof want);
    ASSERT_EQ(PK_OK, pkc_preference_shift(tri, &PREF, 0x100, s1, a1));
    ASSERT_MEM_EQ(s0, s1, sizeof s0);
    ASSERT_MEM_EQ(a0, a1, sizeof a0);
    static const int modes[6] = { 1, 4, 0x10, 0x11, 0x40, 0xff };
    for (int i = 0; i < 6; i++) {
        int16_t s[3] = { 7, 7, 7 };
        ASSERT_EQ(PK_E_UNSUPPORTED, pkc_preference_shift(tri, &PREF, modes[i], s, NULL));
        ASSERT(s[0] == 7 && s[1] == 7 && s[2] == 7);
    }
    ASSERT_EQ(PK_E_ARG, pkc_preference_shift(NULL, &PREF, 0, s0, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_preference_shift(tri, NULL, 0, s0, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_preference_shift(tri, &PREF, 0, NULL, NULL));
    ASSERT_STR_EQ("PK_E_UNSUPPORTED", pk_status_str(PK_E_UNSUPPORTED));
    ASSERT_STR_EQ("PK_OK", pk_status_str(PK_OK));
    PASS();
}

SUITE(sba_pref) {
    RUN_TEST(kodak_core); RUN_TEST(kodak_chain); RUN_TEST(brief_numbers); RUN_TEST(slope_limit); RUN_TEST(crafted_boundaries); RUN_TEST(pref_load);
    RUN_TEST(sfs_checks); RUN_TEST(sfs_crafted); RUN_TEST(unknown_slot); RUN_TEST(bad_args); RUN_TEST(setshifts_index); RUN_TEST(preference_mode);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(sba_pref);
    GREATEST_MAIN_END();
}
