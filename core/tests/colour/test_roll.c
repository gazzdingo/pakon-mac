/* Task 19: the roll orchestration (analysis/roll.c) and the public API (pakon/colour.h).
 * Kodak truth (vectors/roll_truth.pkv, lab/vectors/gen_roll_truth.py, lab/rollbal/truth/t19, docs/re/24): 56 rolls,
 * 364 scenes at x87 PC53 -- r4 / r2 / r1 / r12 on Task 11's Kodak film base and on v1's, RE 11's twelve falloff-gate
 * variants (fg7 / fg8 = scene 2 x 1.15 / x 0.85), every crafted roll of Tasks 12-18, t15cap (41 scenes in one PakonIMAu
 * roll), t15d (FOS calc error) and t19a / t19b (flesh around the exposure limit, where only the sba instance's exposure
 * gives Kodak's total). Two rolls (t14w2, t14x1) hold a frame whose grid read leaves the image: refused
 * (PK_E_UNSUPPORTED). For every scene the port, run from the lo-res frames and AddScene dmins Kodak got, must give
 * Kodak's scene LUT (all 3 x 4096 entries: the table of PIAnselColorSceneBalancePlanar's LUT op), its getSbaExposure
 * float and its falloff export decision. Fix round 1: 25 runs with product / gen codes (runs_codes: the four sba.map
 * product rows, every noise-table ISO class and range end, out-of-table codes, gen 20) -- scene LUT, exposure, falloff,
 * the selected dpi's Preference block and each scene's balanced 2x hi-res image (NRA with the ISO's noise table).
 * Then: TLB's batching of 40, the public API against the stages called directly (analysis and render, three films),
 * the failure and unsupported paths. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE    /* mkdtemp, symlink on macOS under -std=c99 */
#include "greatest.h"
#include "pkv.h"
#include "synframe.h"
#include "pakon/colour.h"
#include "front.h"
#include "render.h"
#include "adjust.h"
#include "icc.h"
#include "nra.h"
#include "data/kodak_map.h"
#include "analysis/fugc.h"
#include "analysis/roll.h"
#include "analysis/dmin.h"
#include "analysis/image.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <unistd.h>
#include <sys/stat.h>

static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }
static uint64_t fnv_bytes(uint64_t h, const void *p, size_t n) {
    const unsigned char *b = p;
    for (size_t i = 0; i < n; i++) { h ^= b[i]; h *= 0x100000001b3ull; }
    return h;
}
#define FNV0 0xcbf29ce484222325ull
static uint64_t le64(const uint8_t *b) { uint64_t v = 0; for (int i = 7; i >= 0; i--) v = v << 8 | b[i]; return v; }
static uint32_t fbits(float f) { uint32_t u; memcpy(&u, &f, sizeof u); return u; }

/* pkc_grid24x36's geometry on the analysis image of a w x h frame: 1 if its last block reads past the image */
static int reads_past(int w, int h) {
    int ow, oh; pkc_analysis_dims(w, h, &ow, &oh);
    int so = oh / 24, si = ow / 36, mo = (oh - so * 24) / 2, mi = (ow - si * 36) / 2;
    return (long long)(mo + 23 * so + si - 1) * ow + (mi + 35 * si + so - 1) >= (long long)ow * oh;
}

#define CHECK(cond) do { if (!(cond)) { fail_line = __LINE__; fail_expr = #cond; goto done; } } while (0)
#define FINISH() do { if (fail_line) { static char fmsg[400]; snprintf(fmsg, sizeof fmsg, "line %d: %s (%s)", fail_line, fail_expr, detail); FAILm(fmsg); } PASS(); } while (0)

static pkv_file *T, *A4, *A2;
static pkc_roll_cfg CFG;
static int cfg_ok;
static int need_cfg(void) {
    if (!cfg_ok) cfg_ok = pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, 0, 0, &CFG) == PK_OK;
    return cfg_ok;
}
static const pkv_array *get(const char *fmt, int i) {
    char nm[64]; snprintf(nm, sizeof nm, fmt, i);
    const pkv_array *a = pkv_get(T, nm);
    if (!a) { fprintf(stderr, "roll_truth.pkv has no %s\n", nm); exit(2); }
    return a;
}

/* a real lo-res frame (analysis_r4 / r2.pkv f<k>_lo, the oracle inputs): planar u16, malloc'd */
static int real_frame(int scan, int k, uint16_t **lo, int *w, int *h) {
    char nm[32]; snprintf(nm, sizeof nm, "f%d_lo", k);
    const pkv_array *a = pkv_get(scan == 4 ? A4 : A2, nm);
    if (!a) return -1;
    *h = a->dims[1]; *w = a->dims[2];
    if (!(*lo = malloc(a->n * sizeof **lo))) return -1;
    memcpy(*lo, a->data, a->n * sizeof **lo);
    return 0;
}

/* frame source row (gen_roll_truth.py r<i>_src): real, numpy-crafted, recipe, or a transformed real frame */
static int frame_of(const int32_t *s, uint16_t **lo, int *w, int *h) {
    if (s[0] == 0) return real_frame(s[1], s[2], lo, w, h);
    if (s[0] == 1) return synframe_numpy((const double *)pkv_get(T, "npar")->data + (size_t)s[1] * 20, lo, w, h);
    if (s[0] == 2) {
        const pkv_array *R = pkv_get(T, "recipe");
        return synframe_recipe(i32(R) + (size_t)s[1] * R->dims[1], i32(pkv_get(T, "recipe_len"))[s[1]], lo, w, h);
    }
    if (s[0] != 3) return -1;
    int op = s[3], a = s[4], b = s[5];
    if (op == 5) {                                   /* flat a, b x 250 */
        *w = 250; *h = b;
        if (!(*lo = malloc((size_t)3 * b * 250 * sizeof **lo))) return -1;
        for (size_t i = 0; i < (size_t)3 * b * 250; i++) (*lo)[i] = (uint16_t)a;
        return 0;
    }
    uint16_t *src; int sw, sh;
    if (real_frame(s[1], s[2], &src, &sw, &sh)) return -1;
    int oh = op == 3 || op == 4 ? a : sh;
    *w = sw; *h = oh;
    if (!(*lo = malloc((size_t)3 * oh * sw * sizeof **lo))) { free(src); return -1; }
    for (int c = 0; c < 3; c++)
        for (int y = 0; y < oh; y++)
            for (int x = 0; x < sw; x++) {
                int sy = op == 4 ? (int)((long long)y * sh / a) : y;
                double v = src[((size_t)c * sh + sy) * sw + x];
                if (op == 1) v += a;
                if (op == 2) v *= a / 1000.0;
                v = v < 0 ? 0 : v > 4095 ? 4095 : v;
                (*lo)[((size_t)c * oh + y) * sw + x] = (uint16_t)v;
            }
    free(src);
    return 0;
}

typedef struct { int n; uint16_t **lo; pkc_roll_frame *fr; uint16_t (*dmin)[3]; } roll_in;
static void roll_free(roll_in *r) {
    if (r->lo) for (int k = 0; k < r->n; k++) free(r->lo[k]);
    free(r->lo); free(r->fr); free(r->dmin);
    memset(r, 0, sizeof *r);
}
/* run i's frames, checked against the FNV of the file Kodak read; 0 = ok */
static int roll_load(int i, roll_in *r, char *msg, size_t cap) {
    memset(r, 0, sizeof *r);
    r->n = i32(get("r%d_n", i))[0];
    r->lo = calloc((size_t)r->n, sizeof *r->lo); r->fr = calloc((size_t)r->n, sizeof *r->fr);
    r->dmin = malloc((size_t)r->n * sizeof *r->dmin);
    if (!r->lo || !r->fr || !r->dmin) { snprintf(msg, cap, "oom"); return 1; }
    const int32_t *src = i32(get("r%d_src", i)), *dm = i32(get("r%d_dmin", i));
    const uint8_t *ff = (const uint8_t *)get("r%d_ffnv", i)->data;
    for (int k = 0; k < r->n; k++) {
        int w, h;
        if (frame_of(src + 6 * k, &r->lo[k], &w, &h)) { snprintf(msg, cap, "run %d frame %d: no frame", i, k); return 1; }
        size_t n = (size_t)w * h;
        if (fnv_bytes(FNV0, r->lo[k], 3 * n * 2) != le64(ff + 8 * k)) { snprintf(msg, cap, "run %d frame %d: not the frame Kodak read", i, k); return 1; }
        r->fr[k].w = w; r->fr[k].h = h;
        for (int c = 0; c < 3; c++) { r->fr[k].p[c] = r->lo[k] + c * n; r->dmin[k][c] = (uint16_t)dm[3 * k + c]; }
    }
    return 0;
}

static const char *run_name(int i, char *buf, size_t cap) {
    const pkv_array *a = pkv_get(T, "runs"); const char *s = a->data; size_t j = 0; int k = 0;
    while (j < a->n && k < i) if (s[j++] == ',') k++;
    size_t l = 0; while (j < a->n && s[j] != ',' && l + 1 < cap) buf[l++] = s[j++];
    buf[l] = 0;
    return buf;
}

TEST kodak_truth(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "", nm[32];
    roll_in r = { 0 }; pkc_roll_scene *out = NULL; pkc_roll_info info;
    int nruns = pkv_list_count(T, "runs"), nscene = 0, nfull = 0, nfail = 0, noff = 0, nunsup = 0, nunsup_runs = 0;
    CHECK(need_cfg() && nruns == 56);
    for (int i = 0; i < nruns; i++) {
        run_name(i, nm, sizeof nm);
        if (roll_load(i, &r, detail, sizeof detail)) CHECK(0);
        out = malloc((size_t)r.n * sizeof *out);
        CHECK(out);
        pk_status st = pkc_roll_analyse(&CFG, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, &info);
        snprintf(detail, sizeof detail, "%s: status %s", nm, pk_status_str(st));
        int past = 0;
        for (int k = 0; k < r.n; k++) past |= reads_past(r.fr[k].w, r.fr[k].h);
        if (past) {
            /* a frame whose grid sampler reads past the analysis image (t14w2 frame 38, 356 x 123: Kodak averages
             * whatever follows its buffer into the last grid row, pkc_grid24x36): refused, not guessed */
            CHECK(st == PK_E_UNSUPPORTED);
            nunsup_runs++;
            nunsup += r.n;
            free(out); out = NULL; roll_free(&r);
            continue;
        }
        CHECK(st == PK_OK);
        int rc = i32(get("r%d_rc", i))[0];
        snprintf(detail, sizeof detail, "%s: failed %d, Kodak AnalyzeRoll rc %d", nm, info.failed, rc);
        CHECK(info.failed == (rc == 0));
        nfail += info.failed;
        const uint8_t *lf = (const uint8_t *)get("r%d_lfnv", i)->data;
        const int32_t *ex = i32(get("r%d_expo", i)), *g = i32(get("r%d_gate", i));
        const pkv_array *full = NULL;
        { char k_[32]; snprintf(k_, sizeof k_, "r%d_lut", i); full = pkv_get(T, k_); }
        for (int k = 0; k < r.n; k++) {
            const pkc_roll_scene *s = &out[k];
            CHECK(s->failed == info.failed);
            if (full) {
                const int16_t *K = (const int16_t *)full->data + (size_t)k * 3 * 4096;
                for (int c = 0; c < 3; c++)
                    for (int j = 0; j < 4096; j++)
                        if (s->lut_s.t[c][j] != K[c * 4096 + j]) {
                            snprintf(detail, sizeof detail, "%s scene %d: LUT[%d][%d] = %d, Kodak %d (total %d %d %d, dmin' %d %d %d)", nm, k, c, j,
                                     s->lut_s.t[c][j], K[c * 4096 + j], s->total[0], s->total[1], s->total[2], s->dmin_prime[0], s->dmin_prime[1], s->dmin_prime[2]);
                            CHECK(0);
                        }
                nfull++;
            }
            snprintf(detail, sizeof detail, "%s scene %d: scene LUT differs from Kodak's (total %d %d %d, dmin' %d %d %d, exposure %g)", nm, k,
                     s->total[0], s->total[1], s->total[2], s->dmin_prime[0], s->dmin_prime[1], s->dmin_prime[2], s->exposure);
            CHECK(fnv_bytes(FNV0, s->lut_s.t, sizeof s->lut_s.t) == le64(lf + 8 * k));
            snprintf(detail, sizeof detail, "%s scene %d: exposure %g, Kodak %08x / gate %d, Kodak %d", nm, k, s->exposure, (unsigned)ex[k], s->falloff, g[2 * k + 1]);
            CHECK((double)(float)s->exposure == s->exposure && fbits((float)s->exposure) == (uint32_t)ex[k]);
            CHECK((uint32_t)g[2 * k] == (uint32_t)ex[k] && s->falloff == g[2 * k + 1]);
            noff += !s->falloff;
            nscene++;
        }
        free(out); out = NULL; roll_free(&r);
    }
    snprintf(detail, sizeof detail, "%d scenes, %d full LUTs, %d failed rolls, %d without falloff, %d refused (%d rolls)", nscene, nfull, nfail, noff, nunsup, nunsup_runs);
    CHECK(nscene + nunsup == 364 && nscene == 310 && nunsup_runs == 2 && nfull == 21 && nfail == 1 && noff > 60);
done:
    free(out); roll_free(&r);
    FINISH();
}

static int run_index(const char *id) { return pkv_list_index(T, "runs", id); }

/* the roll-level facts the brief names, at Kodak: per-frame exposure and falloff of r4 / r2 (RE 23's table), fg7 / fg8;
 * the scpLut is the identity under 4 frames (no FOS: seven zero words, shipped dpi) and not on r4 */
TEST brief_numbers(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "";
    roll_in r = { 0 }; pkc_roll_scene *out = NULL; pkc_roll_info info;
    static const struct { const char *id; int n; double e[6]; int fo[6]; int ident; } B[] = {
        { "r4", 4, { 0, -0.5, -1.0, 1.0 }, { 1, 1, 0, 1 }, 0 },
        { "r2", 6, { 4.0, -2.5, 1.5, -0.5, 1.5, 1.0 }, { 1, 0, 1, 1, 1, 1 }, 0 },
        { "r1", 1, { -0.5 }, { 1 }, 1 },
        { "r12", 2, { -0.5, -1.0 }, { 1, 0 }, 1 },
        { "fg7", 4, { 0, -0.5, -0.5, 1.0 }, { 1, 1, 1, 1 }, 0 },
        { "fg8", 4, { 0, -0.5, -2.0, 1.0 }, { 1, 1, 0, 1 }, 0 },
        { "syns", 3, { -2.5, -2.0, -2.0 }, { 0, 0, 0 }, 1 } };
    CHECK(need_cfg());
    for (size_t b = 0; b < sizeof B / sizeof B[0]; b++) {
        int i = run_index(B[b].id);
        snprintf(detail, sizeof detail, "%s", B[b].id);
        CHECK(i >= 0);
        if (roll_load(i, &r, detail, sizeof detail)) CHECK(0);
        CHECK(r.n == B[b].n);
        out = malloc((size_t)r.n * sizeof *out); CHECK(out);
        CHECK(pkc_roll_analyse(&CFG, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, &info) == PK_OK);
        for (int k = 0; k < r.n; k++) CHECK(out[k].exposure == B[b].e[k] && out[k].falloff == B[b].fo[k]);
        int ident = 1;
        for (int c = 0; c < 3; c++) for (int j = 0; j < 4096; j++) ident &= info.scplut.t[c][j] == j;
        CHECK(ident == B[b].ident && info.fos1.valid == !B[b].ident && info.n_fos == (B[b].ident ? 0 : r.n));
        free(out); out = NULL; roll_free(&r);
    }
done:
    free(out); roll_free(&r);
    FINISH();
}

/* t15cap: 41 scenes in ONE PakonIMAu roll (Kodak truth: FOS takes the first 40, scene 40 still gets the FOS pass) vs
 * TLB's batching, which never builds such a roll: frames 0-39 are one roll and frame 40 a roll of its own. */
TEST batches(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "";
    roll_in r = { 0 }; pkc_roll_scene *one = NULL, *bat = NULL, *forty = NULL, single; pkc_roll_info info;
    CHECK(need_cfg());
    int i = run_index("t15cap");
    CHECK(i >= 0);
    if (roll_load(i, &r, detail, sizeof detail)) CHECK(0);
    CHECK(r.n == 41);
    one = malloc(41 * sizeof *one); bat = malloc(41 * sizeof *bat); forty = malloc(40 * sizeof *forty);
    CHECK(one && bat && forty);
    CHECK(pkc_roll_analyse(&CFG, 41, r.fr, (const uint16_t (*)[3])r.dmin, one, &info) == PK_OK);
    CHECK(info.n_fos == 40 && info.fos1.valid);
    /* TLB passes one film base per strip: give every frame r4's (the first 40 frames mix two; scene 40 is r4's) */
    for (int k = 0; k < 41; k++) memcpy(r.dmin[k], r.dmin[40], sizeof r.dmin[k]);
    CHECK(pkc_roll_batches(&CFG, 41, r.fr, r.dmin[40], bat) == PK_OK);
    CHECK(pkc_roll_analyse(&CFG, 40, r.fr, (const uint16_t (*)[3])r.dmin, forty, NULL) == PK_OK);
    CHECK(pkc_roll_analyse(&CFG, 1, r.fr + 40, (const uint16_t (*)[3])r.dmin, &single, NULL) == PK_OK);
    for (int k = 0; k < 40; k++) {
        snprintf(detail, sizeof detail, "frame %d", k);
        CHECK(!memcmp(&bat[k], &forty[k], sizeof bat[k]));
    }
    CHECK(!memcmp(&bat[40], &single, sizeof single));
    /* the single-frame batch has no FOS: not what Kodak's 41-scene roll gives scene 40 */
    CHECK(memcmp(&bat[40].lut_s, &one[40].lut_s, sizeof one[40].lut_s) != 0);
done:
    free(one); free(bat); free(forty); roll_free(&r);
    FINISH();
}

/* A failed batch (t15d: FOS calc error) does not stop the next one, and the failed scenes are what PSI renders with. */
TEST failed_batch(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "";
    roll_in a = { 0 }, d = { 0 }; pkc_roll_scene *out = NULL, *ref = NULL;
    CHECK(need_cfg());
    if (roll_load(run_index("r2"), &a, detail, sizeof detail)) CHECK(0);
    if (roll_load(run_index("t15d"), &d, detail, sizeof detail)) CHECK(0);
    /* 40 frames: r2's six cycled; then t15d's four */
    pkc_roll_frame fr[44];
    for (int k = 0; k < 40; k++) fr[k] = a.fr[k % 6];
    for (int k = 0; k < 4; k++) fr[40 + k] = d.fr[k];
    out = malloc(44 * sizeof *out); ref = malloc(40 * sizeof *ref);
    CHECK(out && ref);
    uint16_t dm[3] = { 326, 777, 1003 }, dm40[40][3];
    for (int k = 0; k < 40; k++) memcpy(dm40[k], dm, sizeof dm);
    CHECK(pkc_roll_batches(&CFG, 44, fr, dm, out) == PK_OK);
    CHECK(pkc_roll_analyse(&CFG, 40, fr, (const uint16_t (*)[3])dm40, ref, NULL) == PK_OK);
    CHECK(!memcmp(out, ref, 40 * sizeof *ref));
    for (int k = 40; k < 44; k++) {
        int zero = 1;
        for (int c = 0; c < 3; c++) for (int j = 0; j < 4096; j++) zero &= out[k].lut_s.t[c][j] == 0;
        CHECK(out[k].failed && zero && out[k].exposure == 0.0 && out[k].falloff == 1);
    }
done:
    free(out); free(ref); roll_free(&a); roll_free(&d);
    FINISH();
}

/* Pins I-1 (docs/re/27): rolls of r4 frames with one or two frames replaced by a top-left crop, run through Kodak at PC53
 * (lab/rollbal/gen_t23small.py, truth/t23): a scene whose analysis image is under 107 in either side gets no SBA pass and no
 * balance (identity LUT, no falloff), is counted as an all-zero scene by FOS, and every other scene's LUT is Kodak's
 * (FNV-1a 64 of the 3 x 4096 int16 table; 0 = Kodak built no LUT). Without the skip the whole call used to fail. */
typedef struct { const char *id; int n; int src[4], cw[4], ch[4]; uint64_t lut[4]; } small_case;
static const small_case SMALL[] = {
    { "c100", 4, { 0, 1, 2, 3 }, { 250, 100, 250, 250 }, { 380, 100, 343, 375 }, { 0x15ae2d1fdd8eb48full, 0, 0x41e7440f9cb33912ull, 0x0fcd823e77b9aab2ull } },
    { "ch90", 4, { 0, 1, 2, 3 }, { 250, 250, 250, 250 }, { 380, 90, 343, 375 }, { 0x15ae2d1fdd8eb48full, 0, 0x41e7440f9cb33912ull, 0x0fcd823e77b9aab2ull } },
    { "c106w", 4, { 0, 1, 2, 3 }, { 250, 106, 250, 250 }, { 380, 107, 343, 375 }, { 0x15ae2d1fdd8eb48full, 0, 0x41e7440f9cb33912ull, 0x0fcd823e77b9aab2ull } },
    { "cw90", 4, { 0, 1, 2, 3 }, { 250, 90, 250, 250 }, { 380, 250, 343, 375 }, { 0x15ae2d1fdd8eb48full, 0, 0x41e7440f9cb33912ull, 0x0fcd823e77b9aab2ull } },
    { "c106h", 4, { 0, 1, 2, 3 }, { 250, 107, 250, 250 }, { 380, 106, 343, 375 }, { 0x15ae2d1fdd8eb48full, 0, 0x41e7440f9cb33912ull, 0x0fcd823e77b9aab2ull } },
    { "c107", 4, { 0, 1, 2, 3 }, { 250, 107, 250, 250 }, { 380, 107, 343, 375 }, { 0x5f5364f137f5c958ull, 0x8c921eeb7e5ede1dull, 0x0eaadfcdecbfa9c8ull, 0x09dfa000ce430ebeull } },
    { "last100", 4, { 0, 2, 3, 1 }, { 250, 250, 250, 100 }, { 380, 343, 375, 100 }, { 0x15ae2d1fdd8eb48full, 0x41e7440f9cb33912ull, 0x0fcd823e77b9aab2ull, 0 } },
    { "one100", 1, { 1 }, { 100 }, { 100 }, { 0 } },
    { "two_s", 2, { 1, 2 }, { 100, 100 }, { 100, 100 }, { 0, 0 } },
};
TEST small_frames_truth(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "";
    uint16_t *src[4] = { 0 }, *lo[4] = { 0 };
    pkc_roll_scene out[4]; pkc_roll_frame fr[4]; uint16_t dm[4][3];
    CHECK(need_cfg());
    for (size_t t = 0; t < sizeof SMALL / sizeof *SMALL; t++) {
        const small_case *sc = &SMALL[t];
        for (int k = 0; k < sc->n; k++) {
            int w, h;
            snprintf(detail, sizeof detail, "%s frame %d", sc->id, k);
            CHECK(real_frame(4, sc->src[k], &src[k], &w, &h) == 0 && w == 250);
            lo[k] = malloc((size_t)3 * sc->cw[k] * sc->ch[k] * sizeof **lo);
            CHECK(lo[k]);
            for (int c = 0; c < 3; c++)
                for (int y = 0; y < sc->ch[k]; y++)
                    memcpy(lo[k] + ((size_t)c * sc->ch[k] + y) * sc->cw[k], src[k] + ((size_t)c * h + y) * w, (size_t)sc->cw[k] * sizeof **lo);
            fr[k].w = sc->cw[k]; fr[k].h = sc->ch[k];
            for (int c = 0; c < 3; c++) fr[k].p[c] = lo[k] + (size_t)c * sc->cw[k] * sc->ch[k];
            dm[k][0] = 326; dm[k][1] = 777; dm[k][2] = 1003;
        }
        snprintf(detail, sizeof detail, "%s", sc->id);
        CHECK(pkc_roll_analyse(&CFG, sc->n, fr, (const uint16_t (*)[3])dm, out, NULL) == PK_OK);
        for (int k = 0; k < sc->n; k++) {
            snprintf(detail, sizeof detail, "%s scene %d: skipped %d, LUT fnv %016llx", sc->id, k, out[k].skipped, (unsigned long long)fnv_bytes(FNV0, out[k].lut_s.t, sizeof out[k].lut_s.t));
            if (sc->lut[k] == 0) {
                CHECK(out[k].skipped && !out[k].falloff && out[k].exposure == 0.0 && !out[k].failed);
                for (int c = 0; c < 3; c++) for (int j = 0; j < 4096; j++) CHECK(out[k].lut_s.t[c][j] == j);
            } else
                CHECK(!out[k].skipped && fnv_bytes(FNV0, out[k].lut_s.t, sizeof out[k].lut_s.t) == sc->lut[k]);
        }
        for (int k = 0; k < sc->n; k++) { free(src[k]); free(lo[k]); src[k] = lo[k] = NULL; }
    }
done:
    for (int k = 0; k < 4; k++) { free(src[k]); free(lo[k]); }
    FINISH();
}

/* M7 (docs/re/27): the public API on a frame Kodak skips. One synthetic frame (lab/e2e/gen_skipped_roll.py: a 60 x 44 hi-res frame, a
 * 100 x 100 lo-res frame, a 250 x 120 strip) through pk_colour_analyse_roll and pk_colour_render_rotated(270); Kodak's engine on the
 * same data (lab/oracle/scripts/e2e_oracle.py --geom 270,0, x87 PC53) gave the u8 output with this FNV-1a 64 (planar R, G, B). */
static void lcg_img(uint16_t *o, int w, int h, uint32_t seed) {
    uint32_t s = seed;
    for (int c = 0; c < 3; c++) for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        s = (s * 1103515245u + 12345u) & 0x7fffffffu;
        o[((size_t)c * h + y) * w + x] = (uint16_t)(((x * 37 + y * 29 + c * 500) % 8000) + 1500 + ((s >> 16) % 400));
    }
}
TEST api_skipped_frame_truth(void) {
    static const uint32_t POLY[30] = { 0x3e941242, 0x3b10aa52, 0xbaa7593d, 0xb5c070fe, 0xb5dfea5a, 0xb5a14a19, 0x3479f794, 0xb5c1d656,
        0x367327d2, 0x431f97ff, 0x3984935b, 0x3e8d39af, 0xbbe6bc87, 0x3552ab0c, 0x368f3f4a, 0x355651a1, 0xb68c2abc, 0xb39e4501,
        0x35ce39bd, 0x43de5ff6, 0x3a41a23d, 0x3c268342, 0x3e8e7508, 0xb4cf3b70, 0x36ff475d, 0x36fe43f3, 0xb5865d89, 0x354040e4,
        0xb7943d79, 0x441ee241 };
    static uint16_t hi[3 * 60 * 44], lo[3 * 100 * 100], st[3 * 250 * 120];
    pk_colour *c = NULL; pk_roll_result *r = NULL; pk_image_u8 im = { 0, 0, NULL };
    lcg_img(hi, 60, 44, 1); lcg_img(lo, 100, 100, 2); lcg_img(st, 250, 120, 3);
    pk_frame_linear fh = { 60, 44, { hi, hi + 60 * 44, hi + 2 * 60 * 44 } }, fl = { 100, 100, { lo, lo + 10000, lo + 20000 } };
    pk_roll_input in = { 1, &fh, &fl, { 250, 120, { st, st + 250 * 120, st + 2 * 250 * 120 } }, { { 0 } }, 4, 4, 0 };
    memcpy(in.poly_neg, POLY, sizeof POLY);
    pk_colour_options opt = { sizeof opt, 1 };
    int sk = -1;
    ASSERT_EQ(PK_OK, pk_colour_open_opts(VENDOR_ROOT, DERIVED_ROOT, &opt, NULL, &c));
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &in, &r));
    ASSERT_EQ(PK_OK, pk_roll_result_skipped(r, 0, &sk));
    ASSERT_EQ(1, sk);
    ASSERT_EQ(PK_OK, pk_roll_result_status(r, 0));
    ASSERT_EQ(PK_E_ARG, pk_roll_result_skipped(r, 1, &sk));
    im.rgb = malloc(60 * 44 * 3);
    ASSERT(im.rgb);
    ASSERT_EQ(PK_OK, pk_colour_render_rotated(c, &in, r, 0, NULL, 270, &im));
    ASSERT(im.width == 44 && im.height == 60);
    uint64_t h = FNV0;
    for (int ch = 0; ch < 3; ch++) for (int i = 0; i < 44 * 60; i++) h = fnv_bytes(h, &im.rgb[3 * i + ch], 1);
    ASSERT_EQ_FMT(0x3294bae494a3b0fcull, h, "%016llx");
    free(im.rgb); pk_roll_result_free(r); pk_colour_close(c);
    PASS();
}

/* Refusal scope (not a Kodak-match test; ruling R41): t14w2 holds a frame whose grid reads past the image. Only that frame is
 * refused, the others of its batch are inexact, frames of the other batches are what a separate call gives. */
TEST refused_batch_is_local(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "";
    roll_in w = { 0 }, a = { 0 }; pkc_roll_scene *out = NULL, *ref = NULL;
    CHECK(need_cfg());
    if (roll_load(run_index("t14w2"), &w, detail, sizeof detail)) CHECK(0);
    if (roll_load(run_index("r2"), &a, detail, sizeof detail)) CHECK(0);
    CHECK(w.n >= 1 && a.n >= 4);
    int nw = w.n < PKC_ROLL_BATCH ? w.n : PKC_ROLL_BATCH;
    pkc_roll_frame fr[PKC_ROLL_BATCH + 4];
    for (int k = 0; k < PKC_ROLL_BATCH; k++) fr[k] = w.fr[k % nw];
    for (int k = 0; k < 4; k++) fr[PKC_ROLL_BATCH + k] = a.fr[k];
    uint16_t dm[3] = { 326, 777, 1003 }, d4[PKC_ROLL_BATCH][3];
    for (int k = 0; k < PKC_ROLL_BATCH; k++) memcpy(d4[k], dm, sizeof dm);
    out = malloc((PKC_ROLL_BATCH + 4) * sizeof *out); ref = malloc(4 * sizeof *ref);
    CHECK(out && ref);
    CHECK(pkc_roll_analyse(&CFG, PKC_ROLL_BATCH, fr, (const uint16_t (*)[3])d4, out, NULL) != PK_OK);   /* the first batch alone is refused */
    CHECK(pkc_roll_batches(&CFG, PKC_ROLL_BATCH + 4, fr, dm, out) == PK_OK);
    /* R41: only the odd frames (grid past the image) are refused; the rest of the batch is analysed, flagged inexact */
    int nodd = 0;
    for (int k = 0; k < PKC_ROLL_BATCH; k++) {
        int odd = reads_past(fr[k].w, fr[k].h);
        nodd += odd;
        CHECK(odd ? out[k].status == PK_E_UNSUPPORTED : (out[k].status == PK_OK && out[k].inexact));
        CHECK(out[k].inexact);
    }
    CHECK(nodd >= 1);
    CHECK(pkc_roll_analyse(&CFG, 4, fr + PKC_ROLL_BATCH, (const uint16_t (*)[3])d4, ref, NULL) == PK_OK);
    for (int k = 0; k < 4; k++) CHECK(out[PKC_ROLL_BATCH + k].status == PK_OK && !memcmp(&out[PKC_ROLL_BATCH + k], &ref[k], sizeof ref[k]));
done:
    free(out); free(ref); roll_free(&w); roll_free(&a);
    FINISH();
}

/* Refusal scope through the public API (owner's rule R41; not a Kodak-match test): a roll of 6 lo-res frames of which one is
 * 250 x 120 (its grid reads past the analysis image). That frame gets PK_E_UNSUPPORTED and exact 0; the others render and have
 * exact 0; the same roll without the odd frame is exact 1 everywhere. The odd roll is identical at 1 thread and auto (frame 3 is 700 x 600, over the 400 000 px threading threshold). */
TEST odd_frame_scope(void) {
    static const uint32_t POLY[30] = { 0x3e941242, 0x3b10aa52, 0xbaa7593d, 0xb5c070fe, 0xb5dfea5a, 0xb5a14a19, 0x3479f794, 0xb5c1d656,
        0x367327d2, 0x431f97ff, 0x3984935b, 0x3e8d39af, 0xbbe6bc87, 0x3552ab0c, 0x368f3f4a, 0x355651a1, 0xb68c2abc, 0xb39e4501,
        0x35ce39bd, 0x43de5ff6, 0x3a41a23d, 0x3c268342, 0x3e8e7508, 0xb4cf3b70, 0x36ff475d, 0x36fe43f3, 0xb5865d89, 0x354040e4,
        0xb7943d79, 0x441ee241 };
    enum { N = 6, LH = 375 };
    enum { BW = 700, BH = 600 };
    static uint16_t hi[N][3 * 60 * 44], big[3 * BW * BH], lo[N][3 * 250 * LH], st[3 * 250 * 120];
    pk_frame_linear fh[N], fl[N];
    pk_colour *c1 = NULL, *c0 = NULL; pk_roll_result *r = NULL, *r0 = NULL; pk_image_u8 im = { 60, 44, NULL }, im0 = { 60, 44, NULL };
    lcg_img(st, 250, 120, 3);
    lcg_img(big, BW, BH, 99);
    for (int k = 0; k < N; k++) {
        lcg_img(hi[k], 60, 44, 10 + k);
        fh[k] = (pk_frame_linear){ 60, 44, { hi[k], hi[k] + 60 * 44, hi[k] + 2 * 60 * 44 } };
    }
    fh[3] = (pk_frame_linear){ BW, BH, { big, big + BW * BH, big + 2 * BW * BH } };
    pk_roll_input in = { N, fh, fl, { 250, 120, { st, st + 250 * 120, st + 2 * 250 * 120 } }, { { 0 } }, 4, 4, 0 };
    memcpy(in.poly_neg, POLY, sizeof POLY);
    pk_colour_options o1 = { sizeof o1, 1 }, o0 = { sizeof o0, 0 };
    ASSERT_EQ(PK_OK, pk_colour_open_opts(VENDOR_ROOT, DERIVED_ROOT, &o1, NULL, &c1));
    ASSERT_EQ(PK_OK, pk_colour_open_opts(VENDOR_ROOT, DERIVED_ROOT, &o0, NULL, &c0));
    im.rgb = malloc((size_t)BW * BH * 3); im0.rgb = malloc((size_t)BW * BH * 3);
    ASSERT(im.rgb && im0.rgb);
    for (int pass = 0; pass < 2; pass++) {            /* pass 0: frame 2 is 250 x 120; pass 1: all 250 x 375 */
        for (int k = 0; k < N; k++) {
            int h = (pass == 0 && k == 2) ? 120 : LH;
            lcg_img(lo[k], 250, h, 100 + k);
            fl[k] = (pk_frame_linear){ 250, h, { lo[k], lo[k] + 250 * h, lo[k] + 2 * 250 * h } };
        }
        ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c1, &in, &r));
        for (int k = 0; k < N; k++) {
            int ex = -1;
            ASSERT_EQ(PK_OK, pk_roll_result_exact(r, k, &ex));
            if (pass == 0 && k == 2) {
                ASSERT_EQ(PK_E_UNSUPPORTED, pk_roll_result_status(r, k));
                ASSERT_EQ(0, ex);
                ASSERT_EQ(PK_E_UNSUPPORTED, pk_colour_render(c1, &in, r, k, NULL, &im));
            } else {
                ASSERT_EQ(PK_OK, pk_roll_result_status(r, k));
                ASSERT_EQ(pass == 0 ? 0 : 1, ex);
                im.width = im0.width = fh[k].width; im.height = im0.height = fh[k].height;
                ASSERT_EQ(PK_OK, pk_colour_render(c1, &in, r, k, NULL, &im));
                if (pass == 0) {
                    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c0, &in, &r0));
                    ASSERT_EQ(PK_OK, pk_colour_render(c0, &in, r0, k, NULL, &im0));
                    ASSERT(!memcmp(im.rgb, im0.rgb, (size_t)im.width * im.height * 3));       /* thread count does not matter */
                    pk_roll_result_free(r0); r0 = NULL;
                }
            }
        }
        { int ex; ASSERT_EQ(PK_E_ARG, pk_roll_result_exact(r, N, &ex)); }
        pk_roll_result_free(r); r = NULL;
    }
    /* m2 (R42): without DX codes FOS does not run, so the odd frame couples nothing: the others stay exact */
    in.product_code = in.gen_code = PK_DX_NONE;
    lcg_img(lo[2], 250, 120, 102);
    fl[2] = (pk_frame_linear){ 250, 120, { lo[2], lo[2] + 250 * 120, lo[2] + 2 * 250 * 120 } };
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c1, &in, &r));
    for (int k = 0; k < N; k++) {
        int ex = -1;
        ASSERT_EQ(PK_OK, pk_roll_result_exact(r, k, &ex));
        ASSERT_EQ(k == 2 ? 0 : 1, ex);
    }
    pk_roll_result_free(r); r = NULL;
    free(im.rgb); free(im0.rgb); pk_colour_close(c1); pk_colour_close(c0);
    PASS();
}

/* m1 (R42): a skipped frame inside an odd batch is exact (its output never uses batch statistics) and equals Kodak's skip output.
 * Frame 0 is api_skipped_frame_truth's frame (same data, strip, poly, rotation 270: Kodak's FNV below); frames 1..5 are normal
 * 250 x 375 lo-res frames with frame 3 at 250 x 120 (its grid reads past the image: refused, the others inexact). */
TEST skipped_in_odd_batch(void) {
    static const uint32_t POLY[30] = { 0x3e941242, 0x3b10aa52, 0xbaa7593d, 0xb5c070fe, 0xb5dfea5a, 0xb5a14a19, 0x3479f794, 0xb5c1d656,
        0x367327d2, 0x431f97ff, 0x3984935b, 0x3e8d39af, 0xbbe6bc87, 0x3552ab0c, 0x368f3f4a, 0x355651a1, 0xb68c2abc, 0xb39e4501,
        0x35ce39bd, 0x43de5ff6, 0x3a41a23d, 0x3c268342, 0x3e8e7508, 0xb4cf3b70, 0x36ff475d, 0x36fe43f3, 0xb5865d89, 0x354040e4,
        0xb7943d79, 0x441ee241 };
    enum { N = 6 };
    static uint16_t hi[N][3 * 60 * 44], lo0[3 * 100 * 100], lo[N][3 * 250 * 375], st[3 * 250 * 120];
    pk_frame_linear fh[N], fl[N];
    pk_colour *c = NULL; pk_roll_result *r = NULL; pk_image_u8 im = { 44, 60, NULL };
    lcg_img(st, 250, 120, 3);
    for (int k = 0; k < N; k++) {
        lcg_img(hi[k], 60, 44, k == 0 ? 1 : 10 + k);
        fh[k] = (pk_frame_linear){ 60, 44, { hi[k], hi[k] + 60 * 44, hi[k] + 2 * 60 * 44 } };
        int h = k == 3 ? 120 : 375;
        lcg_img(lo[k], 250, h, 100 + k);
        fl[k] = (pk_frame_linear){ 250, h, { lo[k], lo[k] + 250 * h, lo[k] + 2 * 250 * h } };
    }
    lcg_img(lo0, 100, 100, 2);
    fl[0] = (pk_frame_linear){ 100, 100, { lo0, lo0 + 10000, lo0 + 20000 } };
    pk_roll_input in = { N, fh, fl, { 250, 120, { st, st + 250 * 120, st + 2 * 250 * 120 } }, { { 0 } }, 4, 4, 0 };
    memcpy(in.poly_neg, POLY, sizeof POLY);
    pk_colour_options opt = { sizeof opt, 1 };
    int sk = -1, ex = -1;
    ASSERT_EQ(PK_OK, pk_colour_open_opts(VENDOR_ROOT, DERIVED_ROOT, &opt, NULL, &c));
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &in, &r));
    ASSERT_EQ(PK_E_UNSUPPORTED, pk_roll_result_status(r, 3));          /* the batch is odd */
    ASSERT_EQ(PK_OK, pk_roll_result_exact(r, 1, &ex));
    ASSERT_EQ(0, ex);
    ASSERT_EQ(PK_OK, pk_roll_result_skipped(r, 0, &sk));
    ASSERT_EQ(1, sk);
    ASSERT_EQ(PK_OK, pk_roll_result_exact(r, 0, &ex));
    ASSERT_EQ(1, ex);
    im.rgb = malloc(60 * 44 * 3);
    ASSERT(im.rgb);
    ASSERT_EQ(PK_OK, pk_colour_render_rotated(c, &in, r, 0, NULL, 270, &im));
    uint64_t h = FNV0;
    for (int ch = 0; ch < 3; ch++) for (int i = 0; i < 44 * 60; i++) h = fnv_bytes(h, &im.rgb[3 * i + ch], 1);
    ASSERT_EQ_FMT(0x3294bae494a3b0fcull, h, "%016llx");
    free(im.rgb); pk_roll_result_free(r); pk_colour_close(c);
    PASS();
}

TEST bad_args(void) {
    pkc_roll_scene s; uint16_t dm[1][3] = { { 326, 777, 1003 } }, px[3 * 200 * 200];
    for (size_t i = 0; i < sizeof px / sizeof px[0]; i++) px[i] = 1500;
    pkc_roll_frame f = { 200, 200, { px, px + 40000, px + 80000 } };
    ASSERT(need_cfg());
    ASSERT_EQ(PK_E_ARG, pkc_roll_analyse(NULL, 1, &f, dm, &s, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_roll_analyse(&CFG, 0, &f, dm, &s, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_roll_analyse(&CFG, PKC_ROLL_MAX + 1, &f, dm, &s, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_roll_batches(&CFG, 0, &f, dm[0], &s));
    px[5] = 4096;                                      /* AddScene data is 12-bit */
    ASSERT_EQ(PK_E_ARG, pkc_roll_analyse(&CFG, 1, &f, dm, &s, NULL));
    px[5] = 1500;
    pkc_roll_frame small = { 106, 200, { px, px + 106 * 200, px + 2 * 106 * 200 } };   /* analysis image 106 x 200: skipped */
    ASSERT_EQ(PK_OK, pkc_roll_analyse(&CFG, 1, &small, dm, &s, NULL));
    ASSERT(s.skipped && !s.falloff && s.exposure == 0.0 && s.lut_s.t[2][4000] == 4000);
    pkc_lut3 a; int16_t t[3] = { 0, 0, 0 };
    ASSERT_EQ(PK_E_ARG, pkc_roll_scene_lut(NULL, t, &a, &a));
    ASSERT_EQ(-1, pkv_list_index(T, "runs", NULL));
    PASS();
}

/* A vendor tree of symlinks to the shipped one in which one file (rel, under anselinstalldir/dataPathItems) is a copy with
 * `from` replaced by `to` (from NULL: an unedited copy). Every directory on rel's path is real; its other entries are
 * symlinks. root receives the tree's path. 0 on success. */
static int mirror(const char *src, const char *dst, const char *rel, const char *from, const char *to) {
    if (mkdir(dst, 0700)) return -1;
    const char *slash = strchr(rel, '/');
    size_t l = slash ? (size_t)(slash - rel) : strlen(rel);
    DIR *D = opendir(src); struct dirent *e;
    if (!D) return -1;
    while ((e = readdir(D))) {
        if (e->d_name[0] == '.' || (strlen(e->d_name) == l && !strncmp(e->d_name, rel, l))) continue;
        char a[1200], b[1200];
        snprintf(a, sizeof a, "%s/%s", src, e->d_name); snprintf(b, sizeof b, "%s/%s", dst, e->d_name);
        if (symlink(a, b)) { closedir(D); return -1; }
    }
    closedir(D);
    char s2[1200], d2[1200];
    snprintf(s2, sizeof s2, "%s/%.*s", src, (int)l, rel); snprintf(d2, sizeof d2, "%s/%.*s", dst, (int)l, rel);
    if (slash) return mirror(s2, d2, slash + 1, from, to);
    static char txt[65536];
    FILE *f = fopen(s2, "rb"); if (!f) return -1;
    size_t len = fread(txt, 1, sizeof txt - 1, f); fclose(f); txt[len] = 0;
    char *hit = from ? strstr(txt, from) : NULL;
    if (from && !hit) return -1;
    f = fopen(d2, "wb"); if (!f) return -1;
    if (hit) { fwrite(txt, 1, (size_t)(hit - txt), f); fputs(to, f); fputs(hit + strlen(from), f); }
    else fputs(txt, f);
    fclose(f);
    return 0;
}
static int edited_file_tree(char *root, const char *rel, const char *from, const char *to) {
    char d[1200], src[1200], dst[1200];
    strcpy(root, "/tmp/pk_roll_XXXXXX");
    if (!mkdtemp(root)) return -1;
    snprintf(d, sizeof d, "%s/anselinstalldir", root); if (mkdir(d, 0700)) return -1;
    snprintf(src, sizeof src, "%s/Config", VENDOR_ROOT); snprintf(dst, sizeof dst, "%s/Config", root);
    if (symlink(src, dst)) return -1;
    snprintf(src, sizeof src, "%s/anselinstalldir/dataPathItems", VENDOR_ROOT);
    snprintf(d, sizeof d, "%s/anselinstalldir/dataPathItems", root);
    return mirror(src, d, rel, from, to);
}
/* An SCPLut dpi selecting what the orchestration does not have is refused at load, never run silently (ctdChoice =
 * ANS_FIRST_PASS: setShifts (1, 0) is not ported; runSCPAfterLut = false: no afterSCPLut instance). The unedited copy loads. */
static int edited_tree(char *root, const char *from, const char *to) {
    return edited_file_tree(root, "SCPLut/SCPLut-scanner-prod-gen-default-default-default.dpi", from, to);
}
static void rm_tree(const char *root) {
    char cmd[1300]; snprintf(cmd, sizeof cmd, "rm -rf '%s'", root);
    if (system(cmd)) fprintf(stderr, "could not remove %s\n", root);
}

TEST unsupported_scplut(void) {
    static const char *const from[3] = { NULL, "ctdChoice = ANS_SECOND_PASS", "runSCPAfterLut = true" };
    static const char *const to[3] = { NULL, "ctdChoice = ANS_FIRST_PASS", "runSCPAfterLut = false" };
    static const pk_status want[3] = { PK_OK, PK_E_UNSUPPORTED, PK_E_UNSUPPORTED };
    for (int i = 0; i < 3; i++) {
        char root[64]; pkc_roll_cfg c; pk_colour *pc = (pk_colour *)1;
        ASSERT_EQ(0, edited_tree(root, from[i], to[i]));
        pk_status s1 = pkc_roll_cfg_load(root, DERIVED_ROOT, 0, 0, &c);
        if (s1 == PK_OK) pkc_roll_cfg_free(&c);
        pk_status s2 = pk_colour_open(root, DERIVED_ROOT, &pc);
        if (s2 == PK_OK) pk_colour_close(pc);
        rm_tree(root);
        ASSERT_EQ_FMT((int)want[i], (int)s1, "%d");
        ASSERT_EQ_FMT((int)want[i], (int)s2, "%d");
        if (s2) ASSERT(pc == NULL);
    }
    PASS();
}

/* Selections an edited tree could make that no Kodak run covers are refused, not guessed: a FUGC film row for a product
 * (its key forms come from the disassembly), and an sba.map row that needs a column whose value this path does not know
 * (a scannerName) before the default row. The codes those rows do not touch still load. */
TEST unsupported_selections(void) {
    char root[64]; pkc_roll_cfg *c = malloc(sizeof *c);
    int16_t (*seed)[PKC_FUGC_N] = malloc(3 * sizeof *seed), td[3];
    ASSERT(c && seed);
    ASSERT_EQ(0, edited_file_tree(root, "fugc/fugc-rgb-lutMap.map", "film =   X   X   X   2.25", "film = 78 13 X 2.75\nfilm =   X   X   X   2.25"));
    pk_status a = pkc_fugc_seed_film(root, 78, 13, 400, seed, td), b = pkc_fugc_seed_film(root, 2, 8, 400, seed, td);
    pk_status d = pkc_roll_cfg_load(root, DERIVED_ROOT, 78, 13, c);
    if (d == PK_OK) pkc_roll_cfg_free(c);
    rm_tree(root);
    ASSERT_EQ(PK_E_UNSUPPORTED, a); ASSERT_EQ(PK_OK, b); ASSERT_EQ(PK_E_UNSUPPORTED, d);
    ASSERT_EQ(0, edited_file_tree(root, "sba/SbaDPI/sba.map", "any any 1  any any any ansel-sba-CN-default",
                                  "any HR200 1  any any any ansel-sba-96-1\nany any 1  any any any ansel-sba-CN-default"));
    pk_status e = pkc_roll_cfg_load(root, DERIVED_ROOT, 2, 8, c);
    if (e == PK_OK) pkc_roll_cfg_free(c);
    pk_status f = pkc_roll_cfg_load(root, DERIVED_ROOT, 78, 13, c);       /* matched by its own row first */
    if (f == PK_OK) pkc_roll_cfg_free(c);
    rm_tree(root);
    free(c); free(seed);
    ASSERT_EQ(PK_E_UNSUPPORTED, e); ASSERT_EQ(PK_OK, f);
    PASS();
}

/* Pins I-6 (R6): a failed load names the Kodak file. */
TEST load_error_names_file(void) {
    pk_colour *c = NULL; pk_load_error e; char root[64];
    memset(&e, 'x', sizeof e);
    ASSERT_EQ(PK_E_VENDOR_DATA, pk_colour_open_ex("/nonexistent", DERIVED_ROOT, &e, &c));
    ASSERT(c == NULL && strstr(e.path, "/nonexistent/") && !strcmp(e.reason, "cannot be opened"));
    ASSERT_EQ(0, edited_file_tree(root, "SCPLut/SCPLut-scanner-prod-gen-default-default-default.dpi", "ctdChoice", "ctdChoiceX"));
    pk_status st = pk_colour_open_ex(root, DERIVED_ROOT, &e, &c);
    rm_tree(root);
    ASSERT_EQ(PK_E_VENDOR_DATA, st);
    ASSERT(strstr(e.path, "SCPLut-scanner-prod-gen-default-default-default.dpi") && !strcmp(e.reason, "content rejected"));
    /* Task 22: pcwf outside the pcode's range is Kodak's 0x18bd on every scene -- a load error, not an analysis error */
    ASSERT_EQ(0, edited_file_tree(root, "sba/SbaDPI/sba-CN-default.dpi", "pcwf = 70", "pcwf = 30000"));
    st = pk_colour_open_ex(root, DERIVED_ROOT, &e, &c);
    rm_tree(root);
    ASSERT_EQ(PK_E_VENDOR_DATA, st);
    ASSERT(strstr(e.path, "/Pcode/") != NULL);
    ASSERT_EQ(PK_E_ARG, pk_colour_open_ex(NULL, DERIVED_ROOT, &e, &c));
    ASSERT(e.path[0] == 0 && e.reason[0]);
    ASSERT_EQ(PK_OK, pk_colour_open_ex(VENDOR_ROOT, DERIVED_ROOT, &e, &c));
    ASSERT(c && e.path[0] == 0);
    pk_colour_close(c);
    PASS();
}

/* ---- fix round 1: product / gen codes (truth t19 runs_codes, docs/re/24 section 8) ---- */

static const char *list_name(const char *list, int i, char *buf, size_t cap) {
    const pkv_array *a = pkv_get(T, list); const char *s = a->data; size_t j = 0; int k = 0;
    while (j < a->n && k < i) if (s[j++] == ',') k++;
    size_t l = 0; while (j < a->n && s[j] != ',' && l + 1 < cap) buf[l++] = s[j++];
    buf[l] = 0;
    return buf;
}

/* Every code run: the selected dpi's Preference block = Kodak's; the scene LUT, exposure and falloff = Kodak's; and each
 * scene's 2x hi-res image rendered through pkc_render_scene (NRA with the film ISO's noise table -> scene LUT -> falloff)
 * = Kodak's PIAnselColorSceneBalancePlanar output bit for bit. gen 20 (Kodak's AddScene fails) is refused. */
TEST kodak_codes(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "", nm[32];
    roll_in r = { 0 }; pkc_roll_scene *out = NULL; pkc_roll_cfg *cfg = NULL; int16_t *hi = NULL, *ob = NULL;
    int nruns = pkv_list_count(T, "cruns"), nscene = 0, nrouted = 0, nsb = 0, nrefused = 0;
    CHECK(nruns == 28);       /* incl. Task 21 (R33): cm1 / cm1_1 / cm1_2, codes PK_DX_NONE (no DX read: no FOS) */
    cfg = malloc(sizeof *cfg); CHECK(cfg);
    for (int i = 0; i < nruns; i++) {
        list_name("cruns", i, nm, sizeof nm);
        const int32_t *cd = i32(get("c%d_codes", i));
        char an[32]; snprintf(an, sizeof an, "c%d_addfail", i);
        pk_status st = pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, cd[0], cd[1], cfg);
        snprintf(detail, sizeof detail, "%s (%d/%d): cfg %s", nm, cd[0], cd[1], pk_status_str(st));
        if (pkv_get(T, an)) { CHECK(st == PK_E_UNSUPPORTED); nrefused++; continue; }
        CHECK(st == PK_OK);
        const int16_t *pb = (const int16_t *)get("c%d_pblob", i)->data;
        for (int j = 0; j < 36; j++) {
            snprintf(detail, sizeof detail, "%s: Preference block word %d = %d, Kodak %d (%s)", nm, j, cfg->pref.blob[j], pb[j], cfg->sba_key);
            CHECK(j == 22 || j == 23 || cfg->pref.blob[j] == pb[j]);
        }
        int routed = strcmp(cfg->sba_key, "ansel-sba-CN-default") != 0;
        nrouted += routed;
        /* the frames, as Kodak got them */
        r.n = i32(get("c%d_n", i))[0];
        r.lo = calloc((size_t)r.n, sizeof *r.lo); r.fr = calloc((size_t)r.n, sizeof *r.fr); r.dmin = malloc((size_t)r.n * sizeof *r.dmin);
        CHECK(r.lo && r.fr && r.dmin);
        const int32_t *src = i32(get("c%d_src", i)), *dm = i32(get("c%d_dmin", i)), *hw = i32(get("c%d_hw", i));
        for (int k = 0; k < r.n; k++) {
            int w, h;
            CHECK(frame_of(src + 6 * k, &r.lo[k], &w, &h) == 0);
            r.fr[k].w = w; r.fr[k].h = h;
            for (int c = 0; c < 3; c++) { r.fr[k].p[c] = r.lo[k] + (size_t)c * w * h; r.dmin[k][c] = (uint16_t)dm[3 * k + c]; }
        }
        out = malloc((size_t)r.n * sizeof *out); CHECK(out);
        st = pkc_roll_analyse(cfg, r.n, r.fr, (const uint16_t (*)[3])r.dmin, out, NULL);
        snprintf(detail, sizeof detail, "%s: analyse %s", nm, pk_status_str(st));
        CHECK(st == PK_OK);
        const uint8_t *lf = (const uint8_t *)get("c%d_lfnv", i)->data, *sf = (const uint8_t *)get("c%d_sfnv", i)->data;
        const int32_t *ex = i32(get("c%d_expo", i)), *g = i32(get("c%d_gate", i));
        for (int k = 0; k < r.n; k++) {
            snprintf(detail, sizeof detail, "%s scene %d: scene LUT / exposure / gate (%s, ISO %d)", nm, k, cfg->sba_key, cfg->film_iso);
            CHECK(fnv_bytes(FNV0, out[k].lut_s.t, sizeof out[k].lut_s.t) == le64(lf + 8 * k));
            CHECK(fbits((float)out[k].exposure) == (uint32_t)ex[k] && out[k].falloff == g[2 * k + 1]);
            /* the 2x hi-res image through the render chain */
            int W = hw[2 * k], H = hw[2 * k + 1], w = r.fr[k].w;
            CHECK(W == 2 * w && H == 2 * r.fr[k].h);
            size_t np = (size_t)W * H;
            hi = malloc(3 * np * sizeof *hi); ob = malloc(3 * np * sizeof *ob); CHECK(hi && ob);
            for (int c = 0; c < 3; c++)
                for (int y = 0; y < H; y++)
                    for (int x = 0; x < W; x++) hi[c * np + (size_t)y * W + x] = (int16_t)r.fr[k].p[c][(size_t)(y / 2) * w + x / 2];
            pkc_planes in = { W, H, { hi, hi + np, hi + 2 * np } }, o = { W, H, { ob, ob + np, ob + 2 * np } };
            CHECK(pkc_render_scene(&in, &out[k].lut_s, out[k].falloff, &cfg->nra, &cfg->falloff, &o) == PK_OK);
            snprintf(detail, sizeof detail, "%s scene %d: balanced hi-res image differs from Kodak's (ISO %d)", nm, k, cfg->film_iso);
            CHECK(fnv_bytes(FNV0, ob, 3 * np * sizeof *ob) == le64(sf + 8 * k));
            free(hi); free(ob); hi = ob = NULL;
            nsb++; nscene++;
        }
        free(out); out = NULL; roll_free(&r);
        pkc_roll_cfg_free(cfg);
    }
    snprintf(detail, sizeof detail, "%d scenes, %d routed runs, %d images, %d refused", nscene, nrouted, nsb, nrefused);
    CHECK(nscene == 106 && nrouted == 9 && nsb == 106 && nrefused == 1);
done:
    free(hi); free(ob); free(out); roll_free(&r);
    if (cfg) { pkc_roll_cfg_free(cfg); free(cfg); }
    FINISH();
}

/* The selections themselves: sba.map rows, the ISO table and its bounds, the noise-table ranges. */
TEST selections(void) {
    static const struct { int pc, gc, iso; const char *key; } S[] = {
        { 0, 0, 0, "ansel-sba-CN-default" }, { 78, 13, 400, "ansel-sba-78-13" }, { 79, 15, 400, "ansel-sba-79-15" },
        { 78, 12, -1, "ansel-sba-CN-default" }, { 96, 1, 400, "ansel-sba-96-1" }, { 96, 5, 0, "ansel-sba-96-1" },
        { 43, 1, 800, "ansel-sba-43-1" }, { 43, 15, -1, "ansel-sba-43-1" }, { 81, 1, 25, "ansel-sba-CN-default" },
        { 2, 11, 3200, "ansel-sba-CN-default" }, { 200, 1, 0, "ansel-sba-CN-default" }, { 127, 15, -1, "ansel-sba-CN-default" } };
    pkc_roll_cfg *c = malloc(sizeof *c);
    ASSERT(c);
    for (size_t i = 0; i < sizeof S / sizeof S[0]; i++) {
        ASSERT_EQ(PK_OK, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, S[i].pc, S[i].gc, c));
        ASSERT_STR_EQ(S[i].key, c->sba_key);
        if (S[i].iso >= 0) ASSERT_EQ(S[i].iso, c->film_iso);
        pkc_roll_cfg_free(c);
    }
    ASSERT_EQ(PK_E_UNSUPPORTED, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, 5, 16, c));
    ASSERT_EQ(PK_E_ARG, pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, -1, 0, c));
    free(c);
    int16_t (*t)[16] = malloc(128 * sizeof *t);
    ASSERT(t);
    ASSERT_EQ(PK_OK, pkc_film_iso_load(VENDOR_ROOT, t));
    ASSERT_EQ(0, pkc_film_iso((const int16_t (*)[16])t, 128, 0));
    ASSERT_EQ(0, pkc_film_iso((const int16_t (*)[16])t, 2, 16));
    ASSERT_EQ(t[2][4], pkc_film_iso((const int16_t (*)[16])t, 65536 + 2, 4));   /* the codes are words */
    ASSERT_EQ(0, pkc_film_iso((const int16_t (*)[16])t, -1, 4));
    free(t);
    /* noise tables: range ends inclusive (Kodak-pinned by kodak_codes' hi-res images at ISO 25 / 125 / 160 / 200 / 800 / 3200) */
    static const int iso[] = { 0, 24, 25, 125, 126, 159, 160, 200, 201, 400, 799, 800, 3200, 3201 };
    static const char *const tbl[] = { "0100", "0100", "0100", "0100", "0100", "0100", "0200", "0200", "0100", "0400", "0100", "0800", "0800", "0100" };
    for (size_t i = 0; i < sizeof iso / sizeof iso[0]; i++) {
        pkc_lut3 *a = malloc(sizeof *a), *b = malloc(sizeof *b);
        char tp[1200], dp[1200];
        snprintf(tp, sizeof tp, "%s/anselinstalldir/dataPathItems/noiseTable/negative35-%s.tbl", VENDOR_ROOT, tbl[i]);
        snprintf(dp, sizeof dp, "%s/anselinstalldir/dataPathItems/nra/nra-srcType-speed-negative35-default.dpi", VENDOR_ROOT);
        int ok = a && b && pkc_nra_prepare_film(VENDOR_ROOT, iso[i], a) == PK_OK && pkc_nra_prepare_files(tp, dp, b) == PK_OK &&
                 !memcmp(a, b, sizeof *a);
        free(a); free(b);
        if (!ok) { static char m[80]; snprintf(m, sizeof m, "ISO %d: not negative35-%s.tbl", iso[i], tbl[i]); FAILm(m); }
    }
    PASS();
}

/* ---- the public API against the stages called directly ---- */

static float K[3][10];
static int k_ok;
static int need_k(void) {
    if (!k_ok) {
        pkv_file *f = pkv_open(PKV_DIR "/front.pkv");
        const pkv_array *a = f ? pkv_get(f, "k") : NULL;
        if (a && a->n == 30) { memcpy(K, a->data, sizeof K); k_ok = 1; }
        pkv_close(f);
    }
    return k_ok;
}
static uint32_t xs(uint32_t *s) { uint32_t x = *s; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *s = x; }
/* a smooth linear frame with noise: planar u16, malloc'd */
static uint16_t *lin_frame(int w, int h, uint32_t seed, int base) {
    uint16_t *p = malloc((size_t)3 * w * h * sizeof *p);
    if (!p) return NULL;
    for (int c = 0; c < 3; c++)
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
                p[((size_t)c * h + y) * w + x] = (uint16_t)(base + 900 * c + 6 * x + 9 * y + (int)(xs(&seed) % 400));
    return p;
}

typedef struct { pk_roll_input in; pk_frame_linear *fr, *lo; uint16_t **buf; int nb; } api_roll;
static void api_free(api_roll *r) {
    if (r->buf) for (int i = 0; i < r->nb; i++) free(r->buf[i]);
    free(r->buf); free(r->fr); free(r->lo);
    memset(r, 0, sizeof *r);
}
/* n frames (hi w x h, lo-res 250 x 375) and a 250 x 700 strip; poly = K or the identity */
static int api_make(api_roll *r, int n, int w, int h, int ident) {
    memset(r, 0, sizeof *r);
    r->fr = calloc((size_t)n, sizeof *r->fr); r->lo = calloc((size_t)n, sizeof *r->lo);
    r->buf = calloc((size_t)(2 * n + 1), sizeof *r->buf);
    if (!r->fr || !r->lo || !r->buf) return -1;
    for (int k = 0; k < n; k++) {
        uint16_t *hi = lin_frame(w, h, 7 + k, 2000 + 300 * (k % 5)), *lo = lin_frame(250, 375, 101 + k, 2000 + 300 * (k % 5));
        r->buf[r->nb++] = hi; r->buf[r->nb++] = lo;
        if (!hi || !lo) return -1;
        r->fr[k] = (pk_frame_linear){ w, h, { hi, hi + (size_t)w * h, hi + (size_t)2 * w * h } };
        r->lo[k] = (pk_frame_linear){ 250, 375, { lo, lo + 250 * 375, lo + 2 * 250 * 375 } };
    }
    uint16_t *st = lin_frame(250, 700, 999, 6000);   /* <= 16383 everywhere: TLB's clamp keeps stored samples there */
    r->buf[r->nb++] = st;
    if (!st) return -1;
    r->in.n_frames = n; r->in.frames = r->fr; r->in.lores = r->lo;
    r->in.strip = (pk_frame_linear){ 250, 700, { st, st + 250 * 700, st + 2 * 250 * 700 } };
    memset(r->in.poly_neg, 0, sizeof r->in.poly_neg);
    if (ident) for (int c = 0; c < 3; c++) r->in.poly_neg[c][c] = 1.0f;
    else memcpy(r->in.poly_neg, K, sizeof K);
    return 0;
}

/* the stages by hand: film base -> front -> pkc_roll_batches */
static pk_status by_hand(const pkc_roll_cfg *cfg, const pk_roll_input *in, pkc_roll_scene *out) {
    uint16_t fb[3], dm[3]; int16_t o[3];
    const uint16_t *sp[3] = { in->strip.linear14[0], in->strip.linear14[1], in->strip.linear14[2] };
    pk_status st = pkc_film_base(sp, in->strip.width, in->strip.height, PKC_DMIN_DPI_BASE, fb);
    if (st) return st;
    const uint16_t *lp[3] = { &fb[0], &fb[1], &fb[2] }; int16_t *op[3] = { &o[0], &o[1], &o[2] };
    pkc_front(in->poly_neg, lp, op, 1);
    for (int c = 0; c < 3; c++) dm[c] = (uint16_t)o[c];
    int n = in->n_frames;
    pkc_roll_frame *fr = calloc((size_t)n, sizeof *fr);
    int16_t **b = calloc((size_t)n, sizeof *b);
    st = PK_E_NOMEM;
    if (fr && b) {
        st = PK_OK;
        for (int k = 0; k < n && !st; k++) {
            const pk_frame_linear *f = &in->lores[k];
            size_t np = (size_t)f->width * f->height;
            if (!(b[k] = malloc(3 * np * sizeof *b[k]))) { st = PK_E_NOMEM; break; }
            int16_t *pp[3] = { b[k], b[k] + np, b[k] + 2 * np };
            const uint16_t *lp2[3] = { f->linear14[0], f->linear14[1], f->linear14[2] };
            pkc_front(in->poly_neg, lp2, pp, np);
            fr[k].w = f->width; fr[k].h = f->height;
            for (int c = 0; c < 3; c++) fr[k].p[c] = (const uint16_t *)pp[c];
        }
        if (!st) st = pkc_roll_batches(cfg, n, fr, dm, out);
    }
    if (b) for (int k = 0; k < n; k++) free(b[k]);
    free(b); free(fr);
    return st;
}

/* codes 0 / 0, an ISO-400 default-row film (2 / 8: another noise table) and a routed product (78 / 13: its own SBA dpi):
 * the API equals the stages called with that film's cfg */
static int api_vs_stages(int pc, int gc, char *detail, size_t dcap) {
    int fail_line = 0; const char *fail_expr = "";
    pk_colour *c = NULL; pk_roll_result *res = NULL; api_roll r; pkc_roll_scene *hand = NULL; pkc_roll_cfg *fc = NULL;
    memset(&r, 0, sizeof r);
    uint8_t *got = NULL, *want = NULL; int16_t *rp = NULL, *bp = NULL; uint8_t *u8 = NULL; pkc_kct *kct = NULL;
    CHECK(need_cfg() && need_k());
    CHECK((fc = malloc(sizeof *fc)) && pkc_roll_cfg_load(VENDOR_ROOT, DERIVED_ROOT, pc, gc, fc) == PK_OK);
    CHECK(pk_colour_open(VENDOR_ROOT, DERIVED_ROOT, &c) == PK_OK);
    const int n = 6, W = 64, H = 48;
    CHECK(api_make(&r, n, W, H, 0) == 0);
    r.in.product_code = pc; r.in.gen_code = gc;
    CHECK(pk_colour_analyse_roll(c, &r.in, &res) == PK_OK);
    hand = malloc((size_t)n * sizeof *hand); CHECK(hand);
    CHECK(by_hand(fc, &r.in, hand) == PK_OK);
    int nf = 0; CHECK(pk_roll_result_frames(res, &nf) == PK_OK && nf == n);
    got = malloc((size_t)3 * W * H); want = malloc((size_t)3 * W * H); u8 = malloc((size_t)3 * W * H);
    rp = malloc((size_t)3 * W * H * sizeof *rp); bp = malloc((size_t)3 * W * H * sizeof *bp);
    CHECK(got && want && u8 && rp && bp);
    static const pk_adjust adjs[3] = { { 0, 0, 0, 0, 0, 0, 0, 0 }, { 25, -50, 0, 100, 75, 500, 2, 0 }, { 0, 0, 0, 0, 0, 0, -3, 3 } };
    for (int k = 0; k < n; k++) {
        double e; int on;
        CHECK(pk_roll_result_status(res, k) == PK_OK);
        CHECK(pk_roll_result_exposure(res, k, &e) == PK_OK && e == hand[k].exposure);
        CHECK(pk_roll_result_falloff(res, k, &on) == PK_OK && on == hand[k].falloff);
        for (int ai = 0; ai < 3; ai++) {
            const pk_adjust *adj = ai ? &adjs[ai] : NULL;
            pk_image_u8 img = { 0, 0, got };
            snprintf(detail, dcap, "codes %d/%d frame %d adjust %d", pc, gc, k, ai);
            CHECK(pk_colour_render(c, &r.in, res, k, adj, &img) == PK_OK && img.width == W && img.height == H);
            /* by hand: front -> NRA -> scene LUT -> falloff -> adjust -> KCMS (per Ima tile) -> interleave */
            size_t np = (size_t)W * H;
            pkc_planes in = { W, H, { rp, rp + np, rp + 2 * np } }, out = { W, H, { bp, bp + np, bp + 2 * np } };
            const uint16_t *lk[3] = { r.fr[k].linear14[0], r.fr[k].linear14[1], r.fr[k].linear14[2] };
            pkc_front(r.in.poly_neg, lk, in.p, np);
            CHECK(pkc_render_scene(&in, &hand[k].lut_s, hand[k].falloff, &fc->nra, &fc->falloff, &out) == PK_OK);
            CHECK(pkc_adjust_apply(&out, &adjs[ai]) == PK_OK);
            CHECK(pkc_icc_select(DERIVED_ROOT, 1, adjs[ai].saturation, adjs[ai].bnw, &kct) == PK_OK);
            uint8_t *o3[3] = { u8, u8 + np, u8 + 2 * np };
            CHECK(pkc_icc_eval_frame(kct, (const int16_t **)out.p, o3, W, H, adjs[ai].sharpness != 0) == PK_OK);
            pkc_kct_free(kct); kct = NULL;
            for (size_t j = 0; j < np; j++) for (int ch = 0; ch < 3; ch++) want[3 * j + ch] = o3[ch][j];
            CHECK(!memcmp(got, want, 3 * np));
        }
    }
    /* the result is per roll size; frames out of range; NULLs */
    pk_image_u8 img = { 0, 0, got };
    double e; int on;
    CHECK(pk_colour_render(c, &r.in, res, n, NULL, &img) == PK_E_ARG);
    CHECK(pk_roll_result_status(res, -1) == PK_E_ARG && pk_roll_result_exposure(res, n, &e) == PK_E_ARG &&
          pk_roll_result_falloff(NULL, 0, &on) == PK_E_ARG && pk_roll_result_frames(res, NULL) == PK_E_ARG);
    { pk_adjust bad = { 0, 0, 0, 0, 0, 0, 6, 0 }; CHECK(pk_colour_render(c, &r.in, res, 0, &bad, &img) == PK_E_ARG); }
    r.in.n_frames = n - 1;
    CHECK(pk_colour_render(c, &r.in, res, 0, NULL, &img) == PK_E_ARG);
    r.in.n_frames = n;
done:
    pkc_kct_free(kct);
    free(got); free(want); free(u8); free(rp); free(bp); free(hand);
    if (fc) { pkc_roll_cfg_free(fc); free(fc); }
    pk_roll_result_free(res); pk_colour_close(c); api_free(&r);
    if (fail_line) { char t[300]; snprintf(t, sizeof t, "line %d: %s (%s)", fail_line, fail_expr, detail); snprintf(detail, dcap, "%s", t); }
    return fail_line;
}
TEST api_matches_stages(void) {
    char detail[400] = "";
    static const int codes[3][2] = { { 0, 0 }, { 2, 8 }, { 78, 13 } };
    for (int i = 0; i < 3; i++) if (api_vs_stages(codes[i][0], codes[i][1], detail, sizeof detail)) FAILm(detail);
    PASS();
}

/* 41 frames through the API: batches 0-39 and 40, each as the stages give it */
TEST api_batches(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "";
    pk_colour *c = NULL; pk_roll_result *res = NULL; api_roll r; pkc_roll_scene *hand = NULL;
    memset(&r, 0, sizeof r);
    CHECK(need_cfg() && need_k());
    CHECK(pk_colour_open(VENDOR_ROOT, DERIVED_ROOT, &c) == PK_OK);
    CHECK(api_make(&r, 41, 16, 16, 0) == 0);
    CHECK(pk_colour_analyse_roll(c, &r.in, &res) == PK_OK);
    hand = malloc(41 * sizeof *hand); CHECK(hand);
    CHECK(by_hand(&CFG, &r.in, hand) == PK_OK);
    for (int k = 0; k < 41; k++) {
        double e; int on;
        snprintf(detail, sizeof detail, "frame %d", k);
        CHECK(pk_roll_result_exposure(res, k, &e) == PK_OK && e == hand[k].exposure);
        CHECK(pk_roll_result_falloff(res, k, &on) == PK_OK && on == hand[k].falloff);
    }
done:
    free(hand); pk_roll_result_free(res); pk_colour_close(c); api_free(&r);
    FINISH();
}

/* t15d through the public API: with the identity polynomial the linear frames are chosen so that TLB's LUT gives
 * exactly Kodak's input (the frames t15d's AddScene received) and the strip's film base gives its dmin 326/777/1003.
 * The analysis succeeds as a call; the frames report PK_E_ANALYSIS and render as PSI does (zero scene LUT + falloff). */
TEST api_failed_roll(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[300] = "";
    pk_colour *c = NULL; pk_roll_result *res = NULL; api_roll r; roll_in d = { 0 };
    uint16_t lut[16384], inv[4096]; uint8_t *got = NULL, *want = NULL; int16_t *bp = NULL, *rp = NULL; uint8_t *u8 = NULL;
    memset(&r, 0, sizeof r);
    CHECK(need_cfg());
    pkc_density_lut(lut);
    for (int t = 0; t < 4096; t++) inv[t] = 0;
    for (int i = 16383; i >= 1; i--) if (lut[i] < 4096 && !inv[lut[i]]) inv[lut[i]] = (uint16_t)i;
    CHECK(pk_colour_open(VENDOR_ROOT, DERIVED_ROOT, &c) == PK_OK);
    if (roll_load(run_index("t15d"), &d, detail, sizeof detail)) CHECK(0);
    CHECK(api_make(&r, 4, 32, 24, 1) == 0);
    for (int k = 0; k < 4; k++) {
        CHECK(d.fr[k].w == 250 && d.fr[k].h == 375);
        uint16_t *lo = (uint16_t *)r.lo[k].linear14[0];
        for (size_t j = 0; j < (size_t)3 * 250 * 375; j++) {
            uint16_t t = d.lo[k][j];
            CHECK(inv[t] && lut[inv[t]] == t);
            lo[j] = inv[t];
        }
    }
    uint16_t *st = (uint16_t *)r.in.strip.linear14[0];
    for (int ch = 0; ch < 3; ch++) for (size_t j = 0; j < 250 * 700; j++) st[(size_t)ch * 250 * 700 + j] = inv[d.dmin[0][ch]];
    CHECK(pk_colour_analyse_roll(c, &r.in, &res) == PK_OK);
    size_t np = 32 * 24;
    got = malloc(3 * np); want = malloc(3 * np); u8 = malloc(3 * np); bp = malloc(3 * np * sizeof *bp); rp = malloc(3 * np * sizeof *rp);
    CHECK(got && want && u8 && bp && rp);
    for (int k = 0; k < 4; k++) {
        double e; int on;
        CHECK(pk_roll_result_status(res, k) == PK_E_ANALYSIS);
        CHECK(pk_roll_result_exposure(res, k, &e) == PK_OK && e == 0.0 && pk_roll_result_falloff(res, k, &on) == PK_OK && on == 1);
        pk_image_u8 img = { 0, 0, got };
        CHECK(pk_colour_render(c, &r.in, res, k, NULL, &img) == PK_OK);
        pkc_lut3 *z = calloc(1, sizeof *z); CHECK(z);
        pkc_planes in = { 32, 24, { rp, rp + np, rp + 2 * np } }, out = { 32, 24, { bp, bp + np, bp + 2 * np } };
        const uint16_t *lk[3] = { r.fr[k].linear14[0], r.fr[k].linear14[1], r.fr[k].linear14[2] };
        pkc_front(r.in.poly_neg, lk, in.p, np);
        pk_status s = pkc_render_scene(&in, z, 1, &CFG.nra, &CFG.falloff, &out);
        free(z);
        CHECK(s == PK_OK);
        pkc_kct *kc = NULL;
        CHECK(pkc_icc_select(DERIVED_ROOT, 1, 0, 0, &kc) == PK_OK);
        uint8_t *o3[3] = { u8, u8 + np, u8 + 2 * np };
        CHECK(pkc_icc_eval_frame(kc, (const int16_t **)out.p, o3, out.w, out.h, 0) == PK_OK);
        pkc_kct_free(kc);
        for (size_t j = 0; j < np; j++) for (int ch = 0; ch < 3; ch++) want[3 * j + ch] = o3[ch][j];
        CHECK(!memcmp(got, want, 3 * np));
    }
done:
    free(got); free(want); free(u8); free(bp); free(rp);
    pk_roll_result_free(res); pk_colour_close(c); api_free(&r); roll_free(&d);
    FINISH();
}

TEST api_errors(void) {
    pk_colour *c = NULL; pk_roll_result *res = (pk_roll_result *)1; api_roll r;
    ASSERT_EQ(PK_E_ARG, pk_colour_open(NULL, DERIVED_ROOT, &c));
    ASSERT(c == NULL);
    ASSERT_EQ(PK_E_VENDOR_DATA, pk_colour_open("/nonexistent", DERIVED_ROOT, &c));
    ASSERT(c == NULL);
    ASSERT_EQ(PK_OK, pk_colour_open(VENDOR_ROOT, DERIVED_ROOT, &c));
    ASSERT(need_k() && api_make(&r, 2, 16, 16, 0) == 0);
    r.in.product_code = 5; r.in.gen_code = 16;               /* not a DX gen code: Kodak's AddScene fails (run c5g20) */
    ASSERT_EQ(PK_E_UNSUPPORTED, pk_colour_analyse_roll(c, &r.in, &res));
    ASSERT(res == NULL);
    r.in.product_code = -1; r.in.gen_code = 0;                /* PK_DX_NONE only for both */
    ASSERT_EQ(PK_E_ARG, pk_colour_analyse_roll(c, &r.in, &res));
    r.in.product_code = 4; r.in.gen_code = PK_DX_NONE;
    ASSERT(pk_colour_analyse_roll(c, &r.in, &res) != PK_OK);
    r.in.product_code = PK_DX_NONE; r.in.gen_code = PK_DX_NONE;   /* no DX read (R33): accepted */
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &r.in, &res));
    {   /* the save rotation: 0 is pk_colour_render; 90 / 270 swap the size; anything else is PK_E_ARG */
        int W = r.in.frames[0].width, H = r.in.frames[0].height;
        uint8_t *a = malloc((size_t)W * H * 3), *b = malloc((size_t)W * H * 3);
        ASSERT(a && b);
        pk_image_u8 ia = { 0, 0, a }, ib = { 0, 0, b };
        ASSERT_EQ(PK_OK, pk_colour_render(c, &r.in, res, 0, NULL, &ia));
        ASSERT_EQ(PK_OK, pk_colour_render_rotated(c, &r.in, res, 0, NULL, 0, &ib));
        ASSERT(ia.width == ib.width && !memcmp(a, b, (size_t)W * H * 3));
        ASSERT_EQ(PK_OK, pk_colour_render_rotated(c, &r.in, res, 0, NULL, 270, &ib));
        ASSERT(ib.width == H && ib.height == W);
        ASSERT_EQ(PK_E_ARG, pk_colour_render_rotated(c, &r.in, res, 0, NULL, 45, &ib));
        free(a); free(b);
    }
    pk_roll_result_free(res); res = NULL;
    r.in.product_code = 43; r.in.gen_code = 2;                /* a routed product and a default-row code are accepted */
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &r.in, &res));
    pk_roll_result_free(res); res = NULL;
    r.in.product_code = 12; r.in.gen_code = 9;
    ASSERT_EQ(PK_OK, pk_colour_analyse_roll(c, &r.in, &res));
    pk_roll_result_free(res); res = NULL;
    r.in.product_code = 0; r.in.gen_code = 0; r.in.n_frames = 0;
    ASSERT_EQ(PK_E_ARG, pk_colour_analyse_roll(c, &r.in, &res));
    r.in.n_frames = 2; r.in.strip.linear14[1] = NULL;
    ASSERT_EQ(PK_E_ARG, pk_colour_analyse_roll(c, &r.in, &res));
    ASSERT_EQ(PK_E_ARG, pk_colour_analyse_roll(c, NULL, &res));
    pk_roll_result_free(NULL); pk_colour_close(NULL);
    pk_colour_close(c); api_free(&r);
    ASSERT_STR_EQ("PK_E_ANALYSIS", pk_status_str(PK_E_ANALYSIS));
    PASS();
}

SUITE(roll) {
    RUN_TEST(kodak_truth); RUN_TEST(brief_numbers); RUN_TEST(batches); RUN_TEST(failed_batch); RUN_TEST(small_frames_truth); RUN_TEST(api_skipped_frame_truth); RUN_TEST(refused_batch_is_local); RUN_TEST(odd_frame_scope); RUN_TEST(skipped_in_odd_batch); RUN_TEST(bad_args);
    RUN_TEST(unsupported_scplut); RUN_TEST(unsupported_selections); RUN_TEST(load_error_names_file); RUN_TEST(kodak_codes); RUN_TEST(selections); RUN_TEST(api_matches_stages); RUN_TEST(api_batches); RUN_TEST(api_failed_roll);
    RUN_TEST(api_errors);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    T = pkv_open(PKV_DIR "/roll_truth.pkv"); A4 = pkv_open(PKV_DIR "/analysis_r4.pkv"); A2 = pkv_open(PKV_DIR "/analysis_r2.pkv");
    if (!T || !A4 || !A2) { fprintf(stderr, "missing vectors\n"); return 2; }
    RUN_SUITE(roll);
    pkc_roll_cfg_free(&CFG); pkv_close(T); pkv_close(A4); pkv_close(A2);
    GREATEST_MAIN_END();
}
