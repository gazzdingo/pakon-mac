/* Task 22: the branches the real corpus never exercises (docs/re/26-unexercised-branches.md).  Kodak truth in
 * vectors/branches.pkv (lab/vectors/gen_branches.py, lab/rollbal/truth/t22, lab/rollbal/gen_t22.py), every run at x87 PC53. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "greatest.h"
#include "pkv.h"
#include "pakon/colour.h"
#include "analysis/roll.h"
#include "synframe.h"
#include "icc.h"
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "edtree.h"

static pkv_file *B, *RT, *A4, *A2;

static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }
static uint64_t fnv_bytes(const void *p, size_t n) {
    const unsigned char *b = p; uint64_t h = 0xcbf29ce484222325ull;
    for (size_t i = 0; i < n; i++) { h ^= b[i]; h *= 0x100000001b3ull; }
    return h;
}
static uint64_t le64(const uint8_t *b) { uint64_t v = 0; for (int i = 7; i >= 0; i--) v = v << 8 | b[i]; return v; }
static uint32_t fbits(float f) { uint32_t u; memcpy(&u, &f, sizeof u); return u; }

/* index of run `id` in roll_truth.pkv's "runs" list, -1 if absent */
static int rt_run(const char *id) { return pkv_list_index(RT, "runs", id); }

typedef struct { int n; uint16_t **lo; pkc_roll_frame *fr; uint16_t (*dmin)[3]; } roll_in;
static void roll_free(roll_in *r) {
    if (r->lo) for (int k = 0; k < r->n; k++) free(r->lo[k]);
    free(r->lo); free(r->fr); free(r->dmin);
    memset(r, 0, sizeof *r);
}
/* the real-frame rolls of roll_truth.pkv (source kind 0: analysis_r4 / r2.pkv f<k>_lo); 0 = ok */
static int rt_load(const char *id, roll_in *r) {
    memset(r, 0, sizeof *r);
    int i = rt_run(id);
    char nm[48];
    if (i < 0) return 1;
    snprintf(nm, sizeof nm, "r%d_n", i); r->n = i32(pkv_get(RT, nm))[0];
    r->lo = calloc((size_t)r->n, sizeof *r->lo); r->fr = calloc((size_t)r->n, sizeof *r->fr);
    r->dmin = malloc((size_t)r->n * sizeof *r->dmin);
    if (!r->lo || !r->fr || !r->dmin) return 1;
    snprintf(nm, sizeof nm, "r%d_src", i); const int32_t *src = i32(pkv_get(RT, nm));
    snprintf(nm, sizeof nm, "r%d_dmin", i); const int32_t *dm = i32(pkv_get(RT, nm));
    for (int k = 0; k < r->n; k++) {
        const int32_t *s = src + 6 * k;
        if (s[0] == 1) {                               /* numpy-crafted frame (gen_t15syn.py ...) */
            int w, h;
            if (synframe_numpy((const double *)pkv_get(RT, "npar")->data + (size_t)s[1] * 20, &r->lo[k], &w, &h)) return 1;
            r->fr[k].w = w; r->fr[k].h = h;
            for (int c = 0; c < 3; c++) { r->fr[k].p[c] = r->lo[k] + (size_t)c * w * h; r->dmin[k][c] = (uint16_t)dm[3 * k + c]; }
            continue;
        }
        if (s[0] != 0) return 1;
        snprintf(nm, sizeof nm, "f%d_lo", s[2]);
        const pkv_array *a = pkv_get(s[1] == 4 ? A4 : A2, nm);
        if (!a) return 1;
        int h = a->dims[1], w = a->dims[2];
        size_t np = (size_t)w * h;
        if (!(r->lo[k] = malloc(a->n * sizeof(uint16_t)))) return 1;
        memcpy(r->lo[k], a->data, a->n * sizeof(uint16_t));
        r->fr[k].w = w; r->fr[k].h = h;
        for (int c = 0; c < 3; c++) { r->fr[k].p[c] = r->lo[k] + c * np; r->dmin[k][c] = (uint16_t)dm[3 * k + c]; }
    }
    return 0;
}

/* ---- item 1: every analysis error ends the roll alike.  Kodak (truth/t22 err_*: FOS#1, FOS#2, a triple error in either
 * instance's pass 2, a pass-1 error in either instance) returns 0 from PIAnselAnalyzeRoll, never reaches getSbaExposure,
 * and its balances then run through an all-zero scene LUT with the falloff gate at exposure 0 (op exported) -- what t15d
 * (FOS#1's eigen discriminant error) did.  The port's failed roll is that, whichever step fails. ---- */
TEST failed_roll(void) {
    roll_in r;
    pkc_roll_cfg cfg;
    ASSERT_EQ(PK_OK, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, 0, 0, &cfg));
    ASSERT_EQ_FMT(0, rt_load("t15d", &r), "%d");
    pkc_roll_scene *out = malloc((size_t)r.n * sizeof *out);
    pkc_roll_info info;
    ASSERT(out);
    ASSERT_EQ(PK_OK, pkc_roll_analyse(&cfg, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, &info));
    ASSERT(info.failed);
    ASSERT_EQ(4, r.n);
    static const pkc_lut3 zero;
    ASSERT_EQ(6, pkv_list_count(B, "err_runs"));
    for (int k = 0; k < r.n; k++) {
        ASSERT(out[k].failed);
        ASSERT_MEM_EQ(&zero, &out[k].lut_s, sizeof zero);
        ASSERT(out[k].exposure == 0.0);
        ASSERT_EQ(1, out[k].falloff);                 /* Kodak: fgOn for every scene of every err_* run */
    }
    free(out); roll_free(&r);
    /* the six sites Kodak was poked at (truth err_*_r4), simulated in the port by the cfg's test seam, on the same roll (r4):
     * every site ends in the same failed roll -- zero LUTs, exposure 0 (Kodak's gate saw bits 0), falloff exported -- and the
     * unpoked roll does not fail */
    static const char *const nm[6] = { "fos1", "fos2", "tri1", "tri2", "pass1", "pass1b" };
    static const int site[6] = { 2, 5, 3, 6, 1, 4 };
    ASSERT_EQ_FMT(0, rt_load("r4", &r), "%d");
    out = malloc((size_t)r.n * sizeof *out);
    ASSERT(out);
    ASSERT_EQ(PK_OK, pkc_roll_analyse(&cfg, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, &info));
    ASSERT(!info.failed && !out[0].failed);
    for (int q = 0; q < 6; q++) {
        char key[40]; snprintf(key, sizeof key, "err_%s_facts", nm[q]);
        const int32_t *f = i32(pkv_get(B, key));
        cfg.inject_fail = site[q];
        ASSERT_EQ(PK_OK, pkc_roll_analyse(&cfg, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, &info));
        char msg[100]; snprintf(msg, sizeof msg, "site %s", nm[q]);
        if (!info.failed) FAILm(msg);
        for (int k = 0; k < r.n; k++) {
            if (!out[k].failed || memcmp(&zero, &out[k].lut_s, sizeof zero) || !f[3 * k] || fbits((float)out[k].exposure) != (uint32_t)f[3 * k + 1] ||
                out[k].falloff != f[3 * k + 2]) FAILm(msg);
        }
    }
    cfg.inject_fail = 0;
    free(out); roll_free(&r); pkc_roll_cfg_free(&cfg);
    PASS();
}

/* ---- item 2: fosOn = 0 (the third pass-2 call site 0x10215d6a, and pass 1 at kind 0): an edited dpi, Kodak's roll ---- */
TEST fos_off(void) {
    static const char *const ids[4] = { "r4", "r2", "r12", "r1" };
    char root[64];
    ASSERT_EQ(0, ed_tree(root, "sba/SbaDPI/sba-CN-default.dpi", "fosOn = 1", "fosOn = 0"));
    pkc_roll_cfg cfg;
    pk_status st = pkc_roll_cfg_load(root, DERIVED_ROOT, 0, 0, &cfg);
    ed_rm(root);                                   /* the cfg holds everything it read: no leak on a later failure */
    ASSERT_EQ(PK_OK, st);
    ASSERT_EQ(0, cfg.fos.fos_on);
    int nscene = 0;
    for (int q = 0; q < 4; q++) {
        char nm[48]; roll_in r;
        ASSERT_EQ_FMT(0, rt_load(ids[q], &r), "%d");
        pkc_roll_scene *out = malloc((size_t)r.n * sizeof *out);
        pkc_roll_info info;
        ASSERT(out);
        ASSERT_EQ(PK_OK, pkc_roll_analyse(&cfg, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, &info));
        ASSERT_EQ(0, info.n_fos);
        ASSERT_EQ(0, info.fos1.valid);
        snprintf(nm, sizeof nm, "fos0_%s_lfnv", ids[q]); const uint8_t *lf = (const uint8_t *)pkv_get(B, nm)->data;
        snprintf(nm, sizeof nm, "fos0_%s_expo", ids[q]); const int32_t *ex = i32(pkv_get(B, nm));
        snprintf(nm, sizeof nm, "fos0_%s_gate", ids[q]); const int32_t *g = i32(pkv_get(B, nm));
        for (int k = 0; k < r.n; k++) {
            char msg[200];
            snprintf(msg, sizeof msg, "%s scene %d: scene LUT (exposure %g)", ids[q], k, out[k].exposure);
            if (fnv_bytes(out[k].lut_s.t, sizeof out[k].lut_s.t) != le64(lf + 8 * k)) FAILm(msg);
            snprintf(msg, sizeof msg, "%s scene %d: exposure %g, Kodak bits %08x", ids[q], k, out[k].exposure, (unsigned)ex[k]);
            if (fbits((float)out[k].exposure) != (uint32_t)ex[k]) FAILm(msg);
            ASSERT_EQ(g[2 * k + 1], out[k].falloff);
            nscene++;
        }
        free(out); roll_free(&r);
    }
    pkc_roll_cfg_free(&cfg);
    ASSERT_EQ(13, nscene);
    PASS();
}

/* ---- item 3b: the flag word 0x2000 (no weight table in FUN_1028ae00), poked into every pass-2 call ---- */
TEST flag_2000(void) {
    static const char *const ids[4] = { "r4", "r2", "r12", "r1" };
    pkc_roll_cfg cfg;
    static const uint8_t FL[8] = { 0xFE, 0xFE, 0xFE, 0xFF, 0xFF, 0xFE, 0x00, 0xFE };   /* the ctor's flag bytes (RE 21) */
    ASSERT_EQ(PK_OK, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, 0, 0, &cfg));
    ASSERT_EQ(PK_OK, pkc_sba_ctx_set_flags(&cfg.sba, FL, 0x2000));
    int nscene = 0, ndiff = 0;
    pkc_roll_cfg plain;
    ASSERT_EQ(PK_OK, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, 0, 0, &plain));
    for (int q = 0; q < 4; q++) {
        char nm[48]; roll_in r;
        ASSERT_EQ_FMT(0, rt_load(ids[q], &r), "%d");
        pkc_roll_scene *out = malloc((size_t)r.n * sizeof *out), *base = malloc((size_t)r.n * sizeof *base);
        ASSERT(out && base);
        ASSERT_EQ(PK_OK, pkc_roll_analyse(&cfg, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, NULL));
        ASSERT_EQ(PK_OK, pkc_roll_analyse(&plain, r.n, r.fr, (const uint16_t (*)[3])r.dmin, base, NULL));
        snprintf(nm, sizeof nm, "flag2000_%s_lfnv", ids[q]); const uint8_t *lf = (const uint8_t *)pkv_get(B, nm)->data;
        snprintf(nm, sizeof nm, "flag2000_%s_expo", ids[q]); const int32_t *ex = i32(pkv_get(B, nm));
        snprintf(nm, sizeof nm, "flag2000_%s_gate", ids[q]); const int32_t *g = i32(pkv_get(B, nm));
        for (int k = 0; k < r.n; k++) {
            char msg[200];
            snprintf(msg, sizeof msg, "%s scene %d: scene LUT (exposure %g)", ids[q], k, out[k].exposure);
            if (fnv_bytes(out[k].lut_s.t, sizeof out[k].lut_s.t) != le64(lf + 8 * k)) FAILm(msg);
            snprintf(msg, sizeof msg, "%s scene %d: exposure %g, Kodak bits %08x", ids[q], k, out[k].exposure, (unsigned)ex[k]);
            if (fbits((float)out[k].exposure) != (uint32_t)ex[k]) FAILm(msg);
            ASSERT_EQ(g[2 * k + 1], out[k].falloff);
            ndiff += memcmp(out[k].lut_s.t, base[k].lut_s.t, sizeof out[k].lut_s.t) != 0;   /* the poke must matter */
            nscene++;
        }
        free(out); free(base); roll_free(&r);
    }
    pkc_roll_cfg_free(&cfg); pkc_roll_cfg_free(&plain);
    ASSERT_EQ(13, nscene);
    ASSERT(ndiff >= 10);
    PASS();
}

/* ---- item 5: the splice warning word / peak search.  Kodak sets scene+0x38e0 (10 on the two frames with 110 / 111 bright
 * right-hand columns of 200).  It is NOT unread: the getter 0x101243c3 puts (word == 0) into byte +0x6020 of the 0x6024-byte
 * balance record (copied @0x1004f8dc), FUN_100f8340 reads it @0x100f836b and the AREA (red-eye) triage predicate 0x100dc0c0
 * uses it @0x100dc0d7.  It is inert on PSI's default path because AREA is off in class 1 (RE 05); a Premium / area port
 * must model it.  The port, which has no such word, gives Kodak's scene LUT, exposure and falloff on all seven frames (and
 * Kodak's own are unchanged when the word is poked, truth/t22 splice_w10 / w15). ---- */
static int16_t *splice_frame(int k, const pkv_array *s0, int *w, int *hp) {   /* as test_analysis_image.c splice_case */
    const int h = k == 6 ? 282 : 376, w0 = s0->dims[2];
    *w = k < 2 ? w0 : k == 6 ? 376 : 200; *hp = h;
    int16_t *a = malloc(sizeof *a * 3 * (size_t)*w * h);
    if (!a) return NULL;
    const int16_t *b = (const int16_t *)s0->data;
    for (int c = 0; c < 3; c++)
        for (int y = 0; y < h; y++)
            for (int x = 0; x < *w; x++) {
                int16_t *o = &a[((size_t)c * h + y) * *w + x];
                if (k < 2) { *o = b[((size_t)c * h + y) * w0 + (k ? w0 - 1 - x : x)]; continue; }
                *o = (int16_t)(c == 1 ? (k == 6 ? 600 + 2 * x : 600 + 3 * x) : 1000);
                if (c) continue;
                if (k == 6 && ((x == 300 && y < 253) || (x == 301 && y < 254) || x >= 370)) *o = 3000;
                if ((k == 2 && x >= 90) || (k == 3 && x >= 89)) *o = 3000;
                if (k == 4 && ((x == 180 && y < 338) || x >= 195)) *o = 1980;
                if (k == 4 && x == 181) *o = 1979;
                if (k == 4 && x == 182 && y < 337) *o = 4000;
                if (k == 5 && x == 100) *o = 3000;
            }
    return a;
}
TEST splice_warning_inert(void) {
    pkv_file *sp = pkv_open(PKV_DIR "/splice.pkv");
    pkc_roll_cfg cfg;
    ASSERT(sp);
    ASSERT_EQ(PK_OK, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, 0, 0, &cfg));
    const pkv_array *S0 = pkv_get(sp, "s0_img");
    int16_t *img[7]; uint16_t *pl[7]; pkc_roll_frame fr[7]; uint16_t dm[7][3];
    for (int k = 0; k < 7; k++) {
        int w, h;
        img[k] = splice_frame(k, S0, &w, &h);
        ASSERT(img[k]);
        pl[k] = (uint16_t *)img[k];
        fr[k].w = w; fr[k].h = h;
        for (int c = 0; c < 3; c++) fr[k].p[c] = pl[k] + (size_t)c * w * h;
        dm[k][0] = 525; dm[k][1] = 653; dm[k][2] = 647;
    }
    pkc_roll_scene out[7];
    ASSERT_EQ(PK_OK, pkc_roll_analyse(&cfg, 7, fr, (const uint16_t (*)[3])dm, out, NULL));
    const uint8_t *lf = (const uint8_t *)pkv_get(B, "splice_lfnv")->data;
    const int32_t *ex = i32(pkv_get(B, "splice_expo")), *g = i32(pkv_get(B, "splice_gate"));
    for (int k = 0; k < 7; k++) {
        char msg[160];
        snprintf(msg, sizeof msg, "splice frame %d: scene LUT (exposure %g)", k, out[k].exposure);
        if (fnv_bytes(out[k].lut_s.t, sizeof out[k].lut_s.t) != le64(lf + 8 * k)) FAILm(msg);
        snprintf(msg, sizeof msg, "splice frame %d: exposure %g, Kodak bits %08x", k, out[k].exposure, (unsigned)ex[k]);
        if (fbits((float)out[k].exposure) != (uint32_t)ex[k]) FAILm(msg);
        ASSERT_EQ(g[2 * k + 1], out[k].falloff);
    }
    const pkv_array *W = pkv_get(B, "splice_warn");      /* Kodak's words: both instances' seven scenes */
    ASSERT_EQ(14, (int)W->n);
    for (int k = 0; k < 7; k++) { ASSERT_EQ(((const int16_t *)W->data)[k], ((const int16_t *)W->data)[7 + k]); }
    ASSERT_EQ(10, ((const int16_t *)W->data)[2]); ASSERT_EQ(10, ((const int16_t *)W->data)[3]); ASSERT_EQ(0, ((const int16_t *)W->data)[0]);
    for (int k = 0; k < 7; k++) free(img[k]);
    pkc_roll_cfg_free(&cfg); pkv_close(sp);
    PASS();
}

/* ---- item 4: setShifts' scpLut index outside its band: Kodak reads the neighbouring band (flat table) ---- */
TEST setshifts_flat(void) {
    static const char *const ids[2] = { "r2", "r4" };
    int ncall = 0, nspill = 0;
    for (int q = 0; q < 2; q++) {
        char nm[32];
        snprintf(nm, sizeof nm, "ss_%s_A", ids[q]); const pkv_array *Aa = pkv_get(B, nm);
        snprintf(nm, sizeof nm, "ss_%s_B", ids[q]); const int16_t *Bs = (const int16_t *)pkv_get(B, nm)->data;
        snprintf(nm, sizeof nm, "ss_%s_out", ids[q]); const int16_t *Os = (const int16_t *)pkv_get(B, nm)->data;
        snprintf(nm, sizeof nm, "ss_%s_tab", ids[q]); const pkv_array *Tt = pkv_get(B, nm);
        ASSERT(Aa && Tt && Tt->n == 3 * 4096);
        pkc_lut3 *lut = malloc(sizeof *lut); ASSERT(lut);
        memcpy(lut, Tt->data, sizeof *lut);
        const int16_t *As = (const int16_t *)Aa->data;
        for (int c = 0; c < (int)Aa->dims[0]; c++) {
            int16_t o[3] = { 0, 0, 0 };
            char msg[160];
            ASSERT_EQ(PK_OK, pkc_setshifts_12(As + 3 * c, Bs + 3 * c, lut, o));
            snprintf(msg, sizeof msg, "%s call %d: A %d %d %d -> %d %d %d, Kodak %d %d %d", ids[q], c, As[3 * c], As[3 * c + 1],
                     As[3 * c + 2], o[0], o[1], o[2], Os[3 * c], Os[3 * c + 1], Os[3 * c + 2]);
            if (memcmp(o, Os + 3 * c, sizeof o)) FAILm(msg);
            for (int k = 0; k < 3; k++) { int ix = 1550 - As[3 * c + k]; nspill += ix < 0 || ix > 4095; }
            ncall++;
        }
        free(lut);
    }
    ASSERT_EQ(10, ncall);
    ASSERT(nspill >= 15);
    PASS();
}

/* ---- item 8: PIColorAdjustPlanar's tile cuts: Kodak's SpEvaluate call sizes for every axis length 1..700 and around the
 * 256-multiples above, both axes, five run kinds (docs/re/26 section 8) ---- */
TEST icc_tile_cuts(void) {
    static const char *const kinds[5] = { "plain", "usm", "usm_sat", "usm_bnw", "sat_bnw" };
    static const int usm[5] = { 0, 1, 1, 1, 0 };
    int ncase = 0;
    for (int q = 0; q < 5; q++) {
        char nm[48];
        snprintf(nm, sizeof nm, "tiles_%s_lens", kinds[q]); const pkv_array *Ls = pkv_get(B, nm);
        ASSERT(Ls);
        for (int ax = 0; ax < 2; ax++) {
            snprintf(nm, sizeof nm, "tiles_%s_%c", kinds[q], ax ? 'h' : 'w'); const pkv_array *Z = pkv_get(B, nm);
            ASSERT(Z && Z->dims[0] == Ls->dims[0] && Z->dims[1] == 16);
            for (int i = 0; i < (int)Ls->dims[0]; i++) {
                int d = i32(Ls)[i], got[16], n = pkc_icc_tile_sizes(d, usm[q], got, 16);
                const int32_t *want = i32(Z) + 16 * i;
                int nw = 0; while (nw < 16 && want[nw]) nw++;
                char msg[160];
                snprintf(msg, sizeof msg, "%s axis %c length %d: %d tiles, Kodak %d (first %d / %d)", kinds[q], ax ? 'h' : 'w', d, n, nw, got[0], want[0]);
                if (n != nw) FAILm(msg);
                for (int k = 0; k < n; k++) if (got[k] != want[k]) FAILm(msg);
                ncase++;
            }
        }
    }
    ASSERT_EQ(2 * (744 + 744 + 148 * 3), ncase);
    int tmp[3];
    ASSERT_EQ(0, pkc_icc_tile_sizes(0, 1, tmp, 3)); ASSERT_EQ(0, pkc_icc_tile_sizes(5, 0, tmp, 0));
    PASS();
}

SUITE(branches) {
    RUN_TEST(icc_tile_cuts);
    RUN_TEST(failed_roll);
    RUN_TEST(fos_off);
    RUN_TEST(flag_2000);
    RUN_TEST(splice_warning_inert);
    RUN_TEST(setshifts_flat);
}

GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    B = pkv_open(PKV_DIR "/branches.pkv"); RT = pkv_open(PKV_DIR "/roll_truth.pkv");
    A4 = pkv_open(PKV_DIR "/analysis_r4.pkv"); A2 = pkv_open(PKV_DIR "/analysis_r2.pkv");
    if (!B || !RT || !A4 || !A2) { fprintf(stderr, "vectors missing\n"); return 2; }
    RUN_SUITE(branches);
    pkv_close(B); pkv_close(RT); pkv_close(A4); pkv_close(A2);
    GREATEST_MAIN_END();
}
