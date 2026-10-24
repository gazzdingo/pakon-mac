/* Task 15: FOS roll passes #1 and #2 against Kodak's own SbaCalcFosResults at x87 PC53 (vectors/fos_truth.pkv,
 * lab/vectors/gen_fos_truth.py, lab/rollbal/truth/t15). Entries: r4 / r2 (Kodak film base, Task 11), r4v1 (v1's film
 * base = RE 16's inputs, the brief's numbers), synf (crafted: no accepted sample, method 2) and the t15* rolls of
 * lab/rollbal/gen_t15syn.py, each crafted (with the port as predictor) to sit on one branch boundary: t15w / t15t
 * (weighted means; exactly 3 scenes in the radius), t15s (weights summing to exactly 300), t15e (dist^2 = r^2), t15p (the
 * weight ramp's rounding and isqrt; a scene with exactly 30 samples), t15q (29 samples; N = 0 in method 1), t15d (the
 * eigen discriminant error); r1 / r12 / syns (< 4 scenes) ran no FOS at Kodak; t15cap = 41 scenes, Kodak used 40. */
#include "greatest.h"
#include "pkv.h"
#include "analysis/fos.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

static pkc_sba_ctx CTX;
static pkc_fos_params FP;
static int ctx_ok;
static int need_ctx(void) {
    if (!ctx_ok) ctx_ok = pkc_sba_ctx_load(VENDOR_ROOT, DERIVED_ROOT, &CTX) == PK_OK && pkc_fos_params_load(VENDOR_ROOT, &FP) == PK_OK;
    return ctx_ok;
}
static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }
static const int16_t *i16(const pkv_array *a) { return (const int16_t *)a->data; }

/* one roll pass: n scenes of grids / dmins / scene states, heap */
typedef struct { int n; int32_t (*grid)[3][PKC_GRID_N]; uint16_t (*dmin)[3]; pkc_sba_scene *sc; } roll;
static void roll_free(roll *r) { free(r->grid); free(r->dmin); free(r->sc); memset(r, 0, sizeof *r); }
static int roll_alloc(roll *r, int n) {
    r->n = n; r->grid = calloc((size_t)n, sizeof *r->grid); r->dmin = calloc((size_t)n, sizeof *r->dmin); r->sc = calloc((size_t)n, sizeof *r->sc);
    return r->grid && r->dmin && r->sc;
}
static void set_grid(roll *r, int k, const int16_t *g, const int16_t *d) {
    for (int i = 0; i < 3 * PKC_GRID_N; i++) r->grid[k][i / PKC_GRID_N][i % PKC_GRID_N] = g[i];
    for (int c = 0; c < 3; c++) r->dmin[k][c] = (uint16_t)d[c];
}
static const int SLOT[5] = { 4, 5, 480, 481, 612 };

/* the 18 SbaFOSResults words as the port reports them (word 13 = theta: never written by the calc) */
static void words(const pkc_fos_result *o, int32_t w[18]) {
    for (int c = 0; c < 3; c++) { w[c] = o->order_fpo[c]; w[3 + c] = o->order_avg[c]; w[6 + c] = o->dmin[c]; }
    w[9] = o->gm_slope; w[10] = o->gm_off; w[11] = o->ill_slope; w[12] = o->ill_off; w[13] = 0;
    w[14] = o->ofpo_method; w[15] = o->num_pixels; w[16] = o->gm_rsq; w[17] = o->ill_rsq;
}

#define CHECK(cond) do { if (!(cond)) { fail_line = __LINE__; fail_expr = #cond; goto done; } } while (0)
#define FINISH() do { if (fail_line) { static char fmsg[200]; snprintf(fmsg, sizeof fmsg, "line %d: %s (%s)", fail_line, fail_expr, detail); FAILm(fmsg); } PASS(); } while (0)
static const char *const ROLLS[11] = { "r4", "r2", "r4v1", "synf", "t15w", "t15t", "t15s", "t15e", "t15p", "t15q", "t15d" };

/* Every entry two ways: (a) the FOS core on Kodak's own pass-1 scene objects (mask + the five slots it reads);
 * (b) the chain: the port's pass 1 (Task 12) on Kodak's grid, whose mask and slots must equal Kodak's, then FOS.
 * Both must reproduce all 18 words Kodak wrote (orderFpo, orderAvg, fosDmin, gm/ill slope + offset, ofpoMethod,
 * numPixels, gm/ill R^2). */
TEST kodak_truth(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[120] = "";
    pkv_file *t = NULL; roll r = { 0 }; pkc_sba_measure *m = NULL;
    int seen_method[3] = { 0, 0, 0 }, nent = 0, nlow = 0;
    if (!need_ctx()) FAILm("ctx / fos params load failed");
    t = pkv_open(PKV_DIR "/fos_truth.pkv"); CHECK(t);
    m = malloc(sizeof *m); CHECK(m);
    const pkv_array *NE = pkv_get(t, "n"); CHECK(NE);
    nent = i32(NE)[0];
    for (int e = 0; e < nent; e++) {
        char nm[32]; const pkv_array *X[6]; static const char *const sfx[6] = { "meta", "grid", "dmin", "slots", "mask", "out" };
        for (int j = 0; j < 6; j++) { snprintf(nm, sizeof nm, "f%d_%s", e, sfx[j]); X[j] = pkv_get(t, nm); CHECK(X[j]); }
        const int32_t *meta = i32(X[0]);
        int n = meta[2];
        snprintf(detail, sizeof detail, "entry %d: %s FOS#%d, %d scenes", e, ROLLS[meta[0]], meta[1], n);
        CHECK((int)X[1]->n == n * 3 * PKC_GRID_N && (int)X[5]->n == 18);
        roll_free(&r); CHECK(roll_alloc(&r, n));
        /* Kodak's packer invariant that makes the helper's bank gate moot at equality (0x1028f301 jle vs jl): with
         * slot 612 (the mask-1 count) <= par+0xe = dc+0xe, slots 480/481 are slots 4/5 (synf: 612 = 0) */
        for (int k = 0; k < n; k++) {
            const int32_t *sl = i32(X[3]) + 5 * k;
            if (sl[4] <= 10) { CHECK(sl[2] == sl[0] && sl[3] == sl[1]); nlow++; }
        }
        for (int pass = 0; pass < 2; pass++) {
            for (int k = 0; k < n; k++) {
                set_grid(&r, k, i16(X[1]) + k * 3 * PKC_GRID_N, i16(X[2]) + 3 * k);
                pkc_sba_scene_init(&r.sc[k]);
                if (pass == 0) {      /* (a) Kodak's objects */
                    memcpy(r.sc[k].mask, (const uint8_t *)X[4]->data + k * PKC_GRID_N, PKC_GRID_N);
                    for (int j = 0; j < 5; j++) { r.sc[k].vec[SLOT[j]] = i32(X[3])[5 * k + j]; r.sc[k].known[SLOT[j]] = 1; }
                } else {              /* (b) the port's pass 1 */
                    CHECK(pkc_sba_measure_scene(NULL, (const int32_t (*)[PKC_GRID_N])r.grid[k], NULL, &CTX, PKC_SBA_PASS1, &r.sc[k], m) == PK_OK);
                    CHECK(!memcmp(r.sc[k].mask, (const uint8_t *)X[4]->data + k * PKC_GRID_N, PKC_GRID_N));
                    for (int j = 0; j < 5; j++) CHECK(r.sc[k].known[SLOT[j]] && r.sc[k].vec[SLOT[j]] == i32(X[3])[5 * k + j]);
                }
            }
            pkc_fos_result o; int32_t w[18];
            CHECK(pkc_fos_roll(&CTX, &FP, n, (const int32_t (*)[3][PKC_GRID_N])r.grid, (const uint16_t (*)[3])r.dmin, r.sc, &o) == PK_OK);
            CHECK(o.valid == (meta[3] == 0) && o.calc_err == meta[3]);   /* t15d: Kodak's eigen discriminant error */
            words(&o, w);
            for (int j = 0; j < 18; j++) {
                if (w[j] != i16(X[5])[j]) snprintf(detail, sizeof detail, "entry %d %s FOS#%d %s: word %d port %d kodak %d", e,
                                                    ROLLS[meta[0]], meta[1], pass ? "chain" : "core", j, (int)w[j], i16(X[5])[j]);
                CHECK(w[j] == i16(X[5])[j]);
            }
            seen_method[o.ofpo_method]++;
        }
    }
    snprintf(detail, sizeof detail, "%d scenes with slot 612 <= 10", nlow);
    CHECK(nlow > 0);
    snprintf(detail, sizeof detail, "%d entries", nent);
    CHECK(nent == 21);
    snprintf(detail, sizeof detail, "methods seen %d/%d/%d", seen_method[0], seen_method[1], seen_method[2]);
    CHECK(seen_method[0] && seen_method[1] && seen_method[2]);     /* all three helper arms are pinned by Kodak */
done:
    roll_free(&r); free(m); pkv_close(t);
    FINISH();
}

/* The brief's numbers (RE 16's table, recorded before R13) are Kodak's at PC53 too: they are the r4v1 entries of the
 * truth vector (the port is checked on those entries, like every other, by kodak_truth). */
TEST brief_numbers_in_truth(void) {
    pkv_file *t = pkv_open(PKV_DIR "/fos_truth.pkv"); ASSERT(t);
    static const int16_t want[2][13] = {
        { 2659, 75, 510, 686, 1113, 1393, 333, 783, 998, -219, -40, 386, 148 },
        { 2661, 106, 452, 693, 1122, 1315, 335, 787, 940, -60, 0, 186, 86 } };
    int ok = 1;
    for (int h = 0; h < 2; h++) {
        char nm[32]; snprintf(nm, sizeof nm, "f%d_out", 4 + h);
        const pkv_array *O = pkv_get(t, nm), *M; snprintf(nm, sizeof nm, "f%d_meta", 4 + h); M = pkv_get(t, nm);
        ok = ok && O && M && i32(M)[0] == 2 && i32(M)[1] == h + 1 && !memcmp(i16(O), want[h], sizeof want[h]);
    }
    pkv_close(t);
    ASSERT(ok);
    PASS();
}

/* dpi params and dc words: the values Kodak used (fos_truth dc = params+0xdc words, asserted in the generator) */
TEST params(void) {
    if (!need_ctx()) FAILm("ctx / fos params load failed");
    static const int16_t wt[5] = { 250, 900, 0, 100, 1 };
    ASSERT_MEM_EQ(wt, FP.wtab, sizeof wt);
    ASSERT_EQ(4, FP.min_frames); ASSERT_EQ(40, FP.max_frames);
    pkv_file *t = pkv_open(PKV_DIR "/fos_truth.pkv"); ASSERT(t);
    const pkv_array *DC = pkv_get(t, "dc");
    static const int OFF[7] = { 0x0e, 0x18, 0x1c, 0x1e, 0x20, 0x2c, 0x2e }, BRIEF[7] = { 10, 150, 605, 750, 250, 3, 30 };
    int ok = DC && DC->n == 7;
    for (int j = 0; ok && j < 7; j++) {
        const uint8_t *p = CTX.params + 0xDC + OFF[j];
        ok = (int16_t)(uint16_t)(p[0] | p[1] << 8) == i32(DC)[j] && i32(DC)[j] == BRIEF[j];
    }
    pkv_close(t);
    ASSERT(ok);
    pkc_fos_params p;
    ASSERT_EQ(PK_E_ARG, pkc_fos_params_load(NULL, &p));
    ASSERT_EQ(PK_E_ARG, pkc_fos_params_load(VENDOR_ROOT, NULL));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_fos_params_load("/nonexistent", &p));
    PASS();
}

/* pkc_fos_params_load on edited copies of the shipped dpi in a temp vendor tree: Kodak's own dpi checks (the strings at
 * 0x105a6cf8..0x105a6e64), integers only, maxFramesToFos in 1..PKC_FOS_MAX_SCENES, and the paths the port lacks
 * (fosOn other than 0 / 1, useHistory != 0) are PK_E_VENDOR_DATA; the unedited copy loads (fosOn = 0 loads as fos_on = 0: RE 26). */
static int write_dpi(const char *root, const char *src, const char *from, const char *to) {
    char dir[600], path[700]; char *buf = NULL; int ok = 0;
    snprintf(dir, sizeof dir, "%s/anselinstalldir/dataPathItems/sba/SbaDPI", root);
    snprintf(path, sizeof path, "%s/sba-CN-default.dpi", dir);
    FILE *f = fopen(src, "rb"); if (!f) return 0;
    buf = calloc(1, 1 << 16); size_t n = fread(buf, 1, (1 << 16) - 1, f); fclose(f);
    char *hit = from ? strstr(buf, from) : NULL;
    if (!from || hit) {
        FILE *o = fopen(path, "wb");
        if (o) {
            if (hit) { fwrite(buf, 1, (size_t)(hit - buf), o); fputs(to, o); fputs(hit + strlen(from), o); }
            else fwrite(buf, 1, n, o);
            ok = fclose(o) == 0;
        }
    }
    free(buf);
    return ok;
}
TEST params_validation(void) {
    char root[] = "/tmp/pk_fos_XXXXXX", src[1200], d[700];
    ASSERT(mkdtemp(root));
    snprintf(src, sizeof src, "%s/anselinstalldir/dataPathItems/sba/SbaDPI/sba-CN-default.dpi", VENDOR_ROOT);
    static const char *const sub[5] = { "/anselinstalldir", "/dataPathItems", "/sba", "/SbaDPI", NULL };
    snprintf(d, sizeof d, "%s", root);
    for (int i = 0; sub[i]; i++) { strncat(d, sub[i], sizeof d - strlen(d) - 1); mkdir(d, 0700); }
    static const char *const cases[][2] = {
        { "fosOn = 1", "fosOn = 2" }, { "useHistory = 0", "useHistory = 1" },
        { "orderFpoMinWeight = 0", "orderFpoMinWeight = 100" }, { "orderFpoMaxWeight = 100", "orderFpoMaxWeight = 101" },
        { "orderFpoMinWeight = 0", "orderFpoMinWeight = -1" }, { "orderFpoLowSatLimit = 250", "orderFpoLowSatLimit = 900" },
        { "orderFpoLowSatLimit = 250", "orderFpoLowSatLimit = 0" }, { "orderFpoHighSatLimit = 900", "orderFpoHighSatLimit = 200" },
        { "maxFramesToFos = 40", "maxFramesToFos = 0" }, { "maxFramesToFos = 40", "maxFramesToFos = 65" },
        { "mff = 4", "mff = 2.5" }, { "mff = 4", "mff = 40000" }, { "orderFpoMaxWeight = 100", "orderFpoMaxWt = 100" } };
    int ncase = (int)(sizeof cases / sizeof *cases), bad = -1, okfile = 1;
    pkc_fos_params p; pk_status st0;
    okfile = write_dpi(root, src, NULL, NULL);
    st0 = pkc_fos_params_load(root, &p);
    for (int i = 0; i < ncase && bad < 0 && okfile; i++) {
        okfile = write_dpi(root, src, cases[i][0], cases[i][1]);
        if (okfile && pkc_fos_params_load(root, &p) != PK_E_VENDOR_DATA) bad = i;
    }
    snprintf(d, sizeof d, "%s/anselinstalldir/dataPathItems/sba/SbaDPI/sba-CN-default.dpi", root); unlink(d);
    for (int i = 3; i >= 0; i--) {
        snprintf(d, sizeof d, "%s", root);
        for (int j = 0; j <= i; j++) strncat(d, sub[j], sizeof d - strlen(d) - 1);
        rmdir(d);
    }
    rmdir(root);
    ASSERT(okfile);
    ASSERT_EQ(PK_OK, st0);
    ASSERT_EQ_FMT(-1, bad, "%d");     /* index of the first edit that loaded */
    PASS();
}

/* Load entry e (Kodak objects) into r. */
static int load_entry(pkv_file *t, int e, roll *r) {
    char nm[32]; const pkv_array *X[5]; static const char *const sfx[5] = { "meta", "grid", "dmin", "slots", "mask" };
    for (int j = 0; j < 5; j++) { snprintf(nm, sizeof nm, "f%d_%s", e, sfx[j]); X[j] = pkv_get(t, nm); if (!X[j]) return 0; }
    int n = i32(X[0])[2];
    if (!roll_alloc(r, n)) return 0;
    for (int k = 0; k < n; k++) {
        set_grid(r, k, i16(X[1]) + k * 3 * PKC_GRID_N, i16(X[2]) + 3 * k);
        pkc_sba_scene_init(&r->sc[k]);
        memcpy(r->sc[k].mask, (const uint8_t *)X[4]->data + k * PKC_GRID_N, PKC_GRID_N);
        for (int j = 0; j < 5; j++) { r->sc[k].vec[SLOT[j]] = i32(X[3])[5 * k + j]; r->sc[k].known[SLOT[j]] = 1; }
    }
    return 1;
}
#define FOS(r, nn, o) pkc_fos_roll(&CTX, &FP, (nn), (const int32_t (*)[3][PKC_GRID_N])(r).grid, (const uint16_t (*)[3])(r).dmin, (r).sc, (o))

/* Kodak's gate (Impl+0x90 = mff = 4): r1 / r12 / syns ran no calc at Kodak (asserted by the generator); here 3 of r4's
 * scenes -> valid 0. */
TEST gate_n3(void) {
    if (!need_ctx()) FAILm("ctx / fos params load failed");
    pkv_file *t = pkv_open(PKV_DIR "/fos_truth.pkv"); ASSERT(t);
    roll r = { 0 }; int ok = load_entry(t, 0, &r);
    pkv_close(t);
    pkc_fos_result o; memset(&o, 0x55, sizeof o);
    pk_status s3 = ok ? FOS(r, 3, &o) : PK_E_ARG;
    int v3 = o.valid, e3 = o.calc_err, f3 = o.order_fpo[0];
    pk_status s0 = ok ? FOS(r, 0, &o) : PK_E_ARG;
    int v0 = o.valid;
    pk_status s4 = ok ? FOS(r, 4, &o) : PK_E_ARG;
    int v4 = o.valid;
    roll_free(&r);
    ASSERT(ok);
    ASSERT_EQ(PK_OK, s3); ASSERT_EQ(0, v3); ASSERT_EQ(0, e3); ASSERT_EQ(0, f3);
    ASSERT_EQ(PK_OK, s0); ASSERT_EQ(0, v0);
    ASSERT_EQ(PK_OK, s4); ASSERT_EQ(1, v4);
    PASS();
}

/* maxFramesToFos (Impl+0x8c = 40): a 41-scene roll at Kodak passed n = 40 and analysed scenes 0..39 (t15cap). The
 * port on all 41 = Kodak; scene 40 (a dark crafted frame) would change fosDmin if it were used. */
TEST cap_41(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[120] = "";
    pkv_file *t = NULL; roll r = { 0 }; pkc_sba_measure *m = NULL;
    if (!need_ctx()) FAILm("ctx / fos params load failed");
    t = pkv_open(PKV_DIR "/fos_truth.pkv"); CHECK(t);
    const pkv_array *G = pkv_get(t, "cap_grid"), *D = pkv_get(t, "cap_dmin"), *O = pkv_get(t, "cap_out");
    CHECK(G && D && O && (int)G->n == 41 * 3 * PKC_GRID_N && (int)D->n == 41 * 3 && (int)O->n == 18);
    CHECK(roll_alloc(&r, 41)); m = malloc(sizeof *m); CHECK(m);
    for (int k = 0; k < 41; k++) {
        set_grid(&r, k, i16(G) + k * 3 * PKC_GRID_N, i16(D) + 3 * k);
        pkc_sba_scene_init(&r.sc[k]);
        CHECK(pkc_sba_measure_scene(NULL, (const int32_t (*)[PKC_GRID_N])r.grid[k], NULL, &CTX, PKC_SBA_PASS1, &r.sc[k], m) == PK_OK);
    }
    pkc_fos_result o, o40, o41; int32_t w[18];
    CHECK(FOS(r, 41, &o) == PK_OK && o.valid);
    words(&o, w);
    for (int j = 0; j < 18; j++) { snprintf(detail, sizeof detail, "word %d port %d kodak %d", j, (int)w[j], i16(O)[j]); CHECK(w[j] == i16(O)[j]); }
    CHECK(FOS(r, 40, &o40) == PK_OK && !memcmp(&o, &o40, sizeof o));
    pkc_fos_params fp41 = FP; fp41.max_frames = 41;
    CHECK(pkc_fos_roll(&CTX, &fp41, 41, (const int32_t (*)[3][PKC_GRID_N])r.grid, (const uint16_t (*)[3])r.dmin, r.sc, &o41) == PK_OK);
    snprintf(detail, sizeof detail, "scene 40 does not move fosDmin");
    CHECK(memcmp(o41.dmin, o.dmin, sizeof o.dmin) != 0);
done:
    roll_free(&r); free(m); pkv_close(t);
    FINISH();
}

/* R18: a slot FOS reads that the port does not know is an error, never a silent read. */
TEST unknown_slot(void) {
    if (!need_ctx()) FAILm("ctx / fos params load failed");
    pkv_file *t = pkv_open(PKV_DIR "/fos_truth.pkv"); ASSERT(t);
    roll r = { 0 }; int ok = load_entry(t, 0, &r);
    pkv_close(t);
    pk_status st[5];
    for (int j = 0; j < 5 && ok; j++) {
        pkc_fos_result o;
        r.sc[2].known[SLOT[j]] = 0; st[j] = FOS(r, 4, &o); r.sc[2].known[SLOT[j]] = 1;
    }
    pkc_fos_result o; pk_status s3 = ok ? FOS(r, 3, &o) : PK_E_ARG;    /* below the gate nothing is read */
    if (ok) r.sc[0].known[480] = 0;
    pk_status s3b = ok ? FOS(r, 3, &o) : PK_E_ARG;
    roll_free(&r);
    ASSERT(ok);
    for (int j = 0; j < 5; j++) ASSERT_EQ(PK_E_VENDOR_DATA, st[j]);
    ASSERT_EQ(PK_OK, s3); ASSERT_EQ(PK_OK, s3b);
    PASS();
}

TEST bad_args(void) {
    if (!need_ctx()) FAILm("ctx / fos params load failed");
    pkv_file *t = pkv_open(PKV_DIR "/fos_truth.pkv"); ASSERT(t);
    roll r = { 0 }; int ok = load_entry(t, 0, &r);
    pkv_close(t);
    pkc_fos_result o;
    const int32_t (*g)[3][PKC_GRID_N] = (const int32_t (*)[3][PKC_GRID_N])r.grid;
    const uint16_t (*d)[3] = (const uint16_t (*)[3])r.dmin;
    pk_status s[7] = {
        pkc_fos_roll(NULL, &FP, 4, g, d, r.sc, &o), pkc_fos_roll(&CTX, NULL, 4, g, d, r.sc, &o),
        pkc_fos_roll(&CTX, &FP, 4, g, d, r.sc, NULL), pkc_fos_roll(&CTX, &FP, -1, g, d, r.sc, &o),
        pkc_fos_roll(&CTX, &FP, 4, NULL, d, r.sc, &o), pkc_fos_roll(&CTX, &FP, 4, g, NULL, r.sc, &o),
        pkc_fos_roll(&CTX, &FP, 4, g, d, NULL, &o) };
    roll_free(&r);
    ASSERT(ok);
    for (int j = 0; j < 7; j++) ASSERT_EQ(PK_E_ARG, s[j]);
    PASS();
}

/* flags[4] == 1 (Kodak's byte[sba+0x388c+4]: a fiduciary scene) skips every scene in the helper and the paxel walk
 * (0x1028f2ed / 0x1028f99e): method 2 and no sample. Disassembly-derived (no Kodak run carries the flag). */
TEST skipped_scenes(void) {
    if (!need_ctx()) FAILm("ctx / fos params load failed");
    pkv_file *t = pkv_open(PKV_DIR "/fos_truth.pkv"); ASSERT(t);
    roll r = { 0 }; int ok = load_entry(t, 0, &r);
    pkv_close(t);
    pkc_sba_ctx c = CTX; c.flags[4] = 1;
    pkc_fos_result o, k;
    pk_status st = ok ? pkc_fos_roll(&c, &FP, 4, (const int32_t (*)[3][PKC_GRID_N])r.grid, (const uint16_t (*)[3])r.dmin, r.sc, &o) : PK_E_ARG;
    pk_status sk = ok ? FOS(r, 4, &k) : PK_E_ARG;
    roll_free(&r);
    ASSERT(ok);
    ASSERT_EQ(PK_OK, st); ASSERT_EQ(PK_OK, sk);
    ASSERT_EQ(1, o.valid); ASSERT_EQ(2, o.ofpo_method); ASSERT_EQ(0, o.num_pixels);
    ASSERT_MEM_EQ(k.dmin, o.dmin, sizeof o.dmin);
    ASSERT_EQ(0, o.gm_slope); ASSERT_EQ(0, o.ill_slope);
    PASS();
}

SUITE(fos) {
    RUN_TEST(kodak_truth); RUN_TEST(brief_numbers_in_truth); RUN_TEST(params); RUN_TEST(params_validation); RUN_TEST(gate_n3); RUN_TEST(cap_41);
    RUN_TEST(unknown_slot); RUN_TEST(bad_args); RUN_TEST(skipped_scenes);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(fos);
    if (ctx_ok) pkc_sba_ctx_free(&CTX);
    GREATEST_MAIN_END();
}
