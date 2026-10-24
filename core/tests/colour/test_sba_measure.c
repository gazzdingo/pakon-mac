/* Task 12: SBA measure + p-code VM. Three kinds of evidence:
 *  - kodak_truth: vectors/sba_truth.pkv = Kodak's own scene object after pass 1 and pass 2 on all four rolls at x87 PC53
 *    (lab/rollbal/truth/t12, lab/vectors/gen_sba_truth.py) [K];
 *  - roll_*: vectors/analysis_<roll>.pkv (gen_analysis.py): the Y/C1/C2 bands are [K]; the mask / vector / L / Ythr of the
 *    reference chain [R] (the reference zeroes the vector slots the port marks unknown);
 *  - sba_cfg.pkv (gen_sba.py): the reference's baked config vs what the port derives, crafted grids through the
 *    reference's pass 1 + pass 2 [R]. */
#include "greatest.h"
#include "pkv.h"
#include "analysis/sba_measure.h"
#include "data/kodak_text.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>

static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }
static const pkv_array *getk(const pkv_file *f, int k, const char *suffix) {
    char nm[64]; snprintf(nm, sizeof nm, "s%d_%s", k, suffix);
    return pkv_get(f, nm);
}

/* Slots the frozen reference leaves 0 but the port now computes because Kodak's own objects need them (low-arm cells A6+0x54
 * / 0x324 = bank row +0x48 [3], found when the crafted rolls' L disagreed; kodak_truth pins them): reference-equality
 * tests skip them. */
static int ref_gap(int i) { return i == 27 || i == 197 || i == 503 || i == 537 || i == 571 || i == 605; }

static pkc_sba_ctx CTX;
static int ctx_ok;
static int need_ctx(void) {
    if (!ctx_ok) ctx_ok = pkc_sba_ctx_load(VENDOR_ROOT, DERIVED_ROOT, &CTX) == PK_OK;
    return ctx_ok;
}

/* A grid as int32[3][864] from an int16 array (heap; caller frees). */
static int32_t (*grid_of(const pkv_array *G))[PKC_GRID_N] {
    int32_t (*g)[PKC_GRID_N] = malloc(sizeof(int32_t[3][PKC_GRID_N]));
    if (g) for (int i = 0; i < 3 * PKC_GRID_N; i++) g[i / PKC_GRID_N][i % PKC_GRID_N] = ((const int16_t *)G->data)[i];
    return g;
}
static pk_status pass_of(const int32_t (*g)[PKC_GRID_N], int pass, pkc_sba_scene *sc, pkc_sba_measure *m) {
    return pkc_sba_measure_scene(NULL, g, NULL, &CTX, pass, sc, m);
}

/* The scene's passes 1 then 2 against the reference chain's pass-2 outputs (analysis_<roll>.pkv). */
static enum greatest_test_res check_pass(const pkv_file *f, int k, int kind, const char *gridk, const char *mimgk,
                                         const char *maskk, const char *lveck, const char *mk) {
    const pkv_array *G = getk(f, k, gridk), *MI = getk(f, k, mimgk), *MK = getk(f, k, maskk), *LV = getk(f, k, lveck),
                    *M = getk(f, k, mk);
    ASSERT(G && MI && MK && LV && M);
    ASSERT_EQ(3 * PKC_GRID_N, (int)G->n); ASSERT_EQ(6 * PKC_GRID_N, (int)MI->n); ASSERT_EQ(720, (int)LV->n);
    int32_t (*g)[PKC_GRID_N] = grid_of(G); ASSERT(g);
    pkc_sba_measure *m = malloc(sizeof *m); pkc_sba_scene *sc = malloc(sizeof *sc);
    if (!m || !sc) { free(g); free(m); free(sc); FAILm("oom"); }
    pkc_sba_scene_init(sc);
    pk_status st1 = pass_of((const int32_t (*)[PKC_GRID_N])g, PKC_SBA_PASS1, sc, m);
    pk_status st = st1 == PK_OK ? pass_of((const int32_t (*)[PKC_GRID_N])g, kind, sc, m) : st1;
    const int16_t *mi = MI->data;
    int bad_band = -1, bad_mask = -1, bad_vec = -1;
    if (st == PK_OK) {
        for (int i = 0; i < PKC_GRID_N && bad_band < 0; i++)
            if (m->Yband[i] != mi[3 * PKC_GRID_N + i] || m->C1band[i] != mi[4 * PKC_GRID_N + i] ||
                m->C2band[i] != mi[5 * PKC_GRID_N + i]) bad_band = i;
        for (int i = 0; i < PKC_GRID_N && bad_mask < 0; i++) if (m->mask[i] != ((const uint8_t *)MK->data)[i]) bad_mask = i;
        for (int i = 0; i < 720 && bad_vec < 0; i++) if (!ref_gap(i) && sc->vec[i] != i32(LV)[i]) bad_vec = i;
    }
    int ok_scalars = st == PK_OK && m->L == i32(M)[0] && m->ythr == i32(M)[1] && m->lvec[3] == m->ythr &&
                     m->lvec[4] == i32(M)[2] && m->lvec[5] == i32(M)[3] && !memcmp(m->lvec, sc->vec, sizeof m->lvec);
    int32_t L = st == PK_OK ? m->L : 0, yt = st == PK_OK ? m->ythr : 0;
    free(g); free(m); free(sc);
    ASSERT_EQ(PK_OK, st);
    ASSERT_EQ_FMT(-1, bad_band, "%d");          /* index of the first differing band sample */
    ASSERT_EQ_FMT(-1, bad_mask, "%d");
    ASSERT_EQ_FMT(-1, bad_vec, "%d");           /* index of the first differing vector slot */
    ASSERT_EQ_FMT(i32(M)[0], L, "%d");
    ASSERT_EQ_FMT(i32(M)[1], yt, "%d");         /* Ythr exact (v1 was +-1 off) */
    ASSERT(ok_scalars);
    PASS();
}

static enum greatest_test_res check_roll(const char *roll) {
    if (!need_ctx()) FAILm("pkc_sba_ctx_load failed");
    char path[1200]; snprintf(path, sizeof path, PKV_DIR "/analysis_%s.pkv", roll);
    pkv_file *f = pkv_open(path); ASSERT(f);
    const pkv_array *SF = pkv_get(f, "scan_frames"), *FV = pkv_get(f, "fos_valid");
    if (!SF || !FV) { pkv_close(f); FAILm("analysis vector arrays missing"); }
    int n = (int)SF->n, passB = i32(FV)[0], kind = passB ? PKC_SBA_FOS2 : PKC_SBA_SHORT2;
    for (int k = 0; k < n; k++) {
        enum greatest_test_res r = check_pass(f, k, kind, "grid", "mimgA", "maskA", "lvecA", "mA");
        if (r == GREATEST_TEST_RES_PASS && passB) r = check_pass(f, k, kind, "grid2", "mimgB", "maskB", "lvecB", "mB");
        if (r != GREATEST_TEST_RES_PASS) { static char msg[80]; snprintf(msg, sizeof msg, "%s scene %d differs", roll, k); pkv_close(f); FAILm(msg); }
    }
    pkv_close(f);
    PASS();
}
TEST roll_r4(void) { return check_roll("r4"); }
TEST roll_r1(void) { return check_roll("r1"); }
TEST roll_r12(void) { return check_roll("r12"); }
TEST roll_r2(void) { return check_roll("r2"); }

/* Test-local error handling: a failed check records where and jumps to the single cleanup point, so nothing leaks. */
#define CHECK(cond) do { if (!(cond)) { fail_line = __LINE__; fail_expr = #cond; goto done; } } while (0)
#define FINISH() do { if (fail_line) { static char fmsg[160]; snprintf(fmsg, sizeof fmsg, "line %d: %s (%s)", fail_line, fail_expr, detail); FAILm(fmsg); } PASS(); } while (0)

/* Kodak truth (R17): the scene object as PakonIMAu.dll left it after pass 1 and after pass 2's packer, at x87 PC53, on the
 * four real rolls and on two crafted rolls whose hue window fires (mask == 2 samples at Kodak: 365..544 of 864 per scene;
 * lab/rollbal/gen_t12syn.py, truth/t12). Every slot the port marks known must equal Kodak's (incl. 614 and 719, which
 * take Kodak's mask-2 terms); the mask incl. the hue-window bits, slot 479 carried into pass 2, L as Kodak passed it to
 * fcn.1028ae00 and Ythr must equal Kodak's. Slots with known == 0 are the ones the port does not claim. Only slot 479 and
 * the mask are dumped at the pass-2 call; the rest of the carried vector is checked through the pass-2 object. */
static const char *const ROLLS[6] = { "r4", "r1", "r12", "r2", "synf", "syns" };
TEST kodak_truth(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[120] = "";
    pkv_file *t = NULL, *a[4] = { 0 };
    pkc_sba_measure *m = NULL; pkc_sba_scene *sc = NULL; int32_t (*g)[PKC_GRID_N] = NULL;
    int ndiff1 = 0, ndiff2 = 0, nknown1 = 0, nknown2 = 0, nmask2 = 0, seen_kind[3] = { 0, 0, 0 }, n = 0;
    if (!need_ctx()) FAILm("pkc_sba_ctx_load failed");
    t = pkv_open(PKV_DIR "/sba_truth.pkv"); CHECK(t);
    const pkv_array *N = pkv_get(t, "n"); CHECK(N);
    n = i32(N)[0];
    CHECK(n == 26 + 14);
    for (int r = 0; r < 4; r++) { char p[1200]; snprintf(p, sizeof p, PKV_DIR "/analysis_%s.pkv", ROLLS[r]); a[r] = pkv_open(p); CHECK(a[r]); }
    m = malloc(sizeof *m); sc = malloc(sizeof *sc);
    CHECK(m && sc);
    for (int e = 0; e < n; e++) {
        char nm[32]; const pkv_array *X[6]; static const char *const sfx[6] = { "meta", "p1vec", "p1mask", "p2vec", "p2mask", "flags" };
        for (int j = 0; j < 6; j++) { snprintf(nm, sizeof nm, "e%d_%s", e, sfx[j]); X[j] = pkv_get(t, nm); CHECK(X[j]); }
        const int32_t *meta = i32(X[0]);
        int roll = meta[0], scene = meta[1], passB = meta[2], kind = meta[3];
        snprintf(detail, sizeof detail, "entry %d (%s scene %d%s kind %d)", e, ROLLS[roll], scene, passB ? "B" : "A", kind);
        const pkv_array *G;
        if (roll >= 4) { snprintf(nm, sizeof nm, "e%d_grid", e); G = pkv_get(t, nm); }     /* crafted: Kodak's own grid dump */
        else {
            snprintf(nm, sizeof nm, "s%d_%s", scene, passB ? "grid2" : "grid");
            G = pkv_get(a[roll], nm);
            if (!G && passB) { snprintf(nm, sizeof nm, "s%d_grid", scene); G = pkv_get(a[roll], nm); }   /* < 4 frames: the scpLut is the identity */
        }
        CHECK(G);
        free(g); g = grid_of(G); CHECK(g);
        const int32_t (*cg)[PKC_GRID_N] = (const int32_t (*)[PKC_GRID_N])g;
        pkc_sba_scene_init(sc);
        CHECK(pass_of(cg, PKC_SBA_PASS1, sc, m) == PK_OK);
        for (int i = 0; i < PKC_SBA_VEC_N; i++) {
            nknown1 += sc->known[i]; ndiff1 += sc->vec[i] != i32(X[1])[i];
            if (sc->known[i] && sc->vec[i] != i32(X[1])[i]) { snprintf(detail, sizeof detail, "entry %d pass 1 slot %d", e, i); CHECK(0); }
        }
        CHECK(!memcmp(sc->mask, X[2]->data, PKC_GRID_N));
        CHECK(sc->vec[479] == meta[5]);                                    /* slot 479 entering pass 2 */
        CHECK(pass_of(cg, kind, sc, m) == PK_OK);
        for (int i = 0; i < PKC_SBA_VEC_N; i++) {
            nknown2 += sc->known[i]; ndiff2 += sc->vec[i] != i32(X[3])[i];
            if (sc->known[i] && sc->vec[i] != i32(X[3])[i]) { snprintf(detail, sizeof detail, "entry %d pass 2 slot %d", e, i); CHECK(0); }
        }
        CHECK(!memcmp(sc->mask, X[4]->data, PKC_GRID_N));
        for (int i = 0; i < PKC_GRID_N; i++) nmask2 += sc->mask[i] == 2;
        CHECK(m->L == meta[4] && m->ythr == i32(X[3])[3] && !memcmp(CTX.flags, X[5]->data, 8));
        seen_kind[kind]++;
    }
    CHECK(seen_kind[PKC_SBA_FOS2] == 8 + 12 + 8 && seen_kind[PKC_SBA_SHORT2] == 2 + 4 + 6);
    /* the port reproduces most slots, and only ~80 slots per pass-2 object (the review's 81-82) differ from Kodak, all unknown */
    CHECK(nknown1 > n * 650 && nknown2 > n * 380);
    CHECK(ndiff2 <= n * 85 && ndiff1 <= n * 20);
    CHECK(nmask2 > 14 * 300);                                              /* the hue window fired at Kodak and in the port */
done:
    free(g); free(m); free(sc);
    for (int r = 0; r < 4; r++) if (a[r]) pkv_close(a[r]);
    if (t) pkv_close(t);
    FINISH();
}

/* Crafted grids (lab/vectors/gen_sba.py, the frozen reference, both passes): flat / smooth casts and a real grid with a
 * smooth patch. The real rolls reach neither the packer's low arm nor the hue window (mask 2). For scenes with mask-2
 * samples the reference skips Kodak's mask-2 terms in slots 614 / 719 (and so L); there the mask and every other slot
 * are compared, and the divergence is asserted, not the reference's value (Kodak's value: kodak_truth). */
TEST synthetic_scenes(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[100] = "";
    pkv_file *f = NULL; pkc_sba_measure *m = NULL; pkc_sba_scene *sc = NULL; int32_t (*g)[PKC_GRID_N] = NULL;
    int mask2_scenes = 0, mask2_slot_div = 0;
    if (!need_ctx()) FAILm("pkc_sba_ctx_load failed");
    f = pkv_open(PKV_DIR "/sba_cfg.pkv"); CHECK(f);
    const pkv_array *N = pkv_get(f, "syn_n"); CHECK(N);
    int n = i32(N)[0];
    CHECK(n >= 5);
    m = malloc(sizeof *m); sc = malloc(sizeof *sc);
    CHECK(m && sc);
    for (int k = 0; k < n; k++) {
        char nm[48];
        snprintf(nm, sizeof nm, "syn%d_grid", k); const pkv_array *G = pkv_get(f, nm);
        CHECK(G);
        free(g); g = grid_of(G); CHECK(g);
        for (int kind = 0; kind <= 2; kind += 2) {
            const pkv_array *X[5]; static const char *const sfx[5] = { "p1mask", "p1vec", "mask", "lvec", "L" };
            for (int j = 0; j < 5; j++) { snprintf(nm, sizeof nm, "syn%d_%d_%s", k, kind, sfx[j]); X[j] = pkv_get(f, nm); CHECK(X[j]); }
            snprintf(detail, sizeof detail, "synthetic scene %d kind %d", k, kind);
            const int32_t (*cg)[PKC_GRID_N] = (const int32_t (*)[PKC_GRID_N])g;
            pkc_sba_scene_init(sc);
            CHECK(pass_of(cg, PKC_SBA_PASS1, sc, m) == PK_OK);
            CHECK(!memcmp(sc->mask, X[0]->data, PKC_GRID_N));
            for (int i = 0; i < 720; i++) CHECK(sc->vec[i] == i32(X[1])[i]);        /* pass 1 has no mask-2 samples */
            CHECK(pass_of(cg, kind, sc, m) == PK_OK);
            CHECK(!memcmp(m->mask, X[2]->data, PKC_GRID_N));
            int n2 = 0; for (int i = 0; i < PKC_GRID_N; i++) n2 += m->mask[i] == 2;
            int n1 = 0; for (int i = 0; i < PKC_GRID_N; i++) n1 += m->mask[i] == 1;
            if (!n2) {
                for (int i = 0; i < 720; i++) if (!ref_gap(i)) CHECK(sc->vec[i] == i32(X[3])[i]);
                CHECK(m->ythr == i32(X[4])[1] && m->lvec[4] == i32(X[4])[2] && m->lvec[5] == i32(X[4])[3]);
                if (n1 > 10) CHECK(m->L == i32(X[4])[0]);       /* low arm: the reference's L lacks the row +0x48 cells (see ref_gap) */
            } else {
                mask2_scenes++;
                for (int i = 0; i < 720; i++) if (!ref_gap(i) && i != 513 && i != 531 && i != 581 && i != 599 && i != 614 && i != 719) CHECK(sc->vec[i] == i32(X[3])[i]);
                mask2_slot_div += sc->vec[614] != i32(X[3])[614];
            }
        }
    }
    CHECK(mask2_scenes > 0 && mask2_slot_div > 0);          /* stage 2 ran, and Kodak's mask-2 sum differs from the reference's */
done:
    free(g); free(m); free(sc); if (f) pkv_close(f);
    FINISH();
}

/* Pass semantics that Kodak's own runs do not distinguish, from the disassembly: pass 1 returns before the VM / tail
 * and does not run mask stage 2; the FOS pass keeps the previous mask (stage 1 skipped) and reads slot 479. */
TEST pass_kinds(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[8] = "";
    pkv_file *a = NULL; pkc_sba_measure *m = NULL; pkc_sba_scene *sc = NULL, *s2 = NULL; int32_t (*g)[PKC_GRID_N] = NULL;
    if (!need_ctx()) FAILm("pkc_sba_ctx_load failed");
    a = pkv_open(PKV_DIR "/analysis_r4.pkv"); CHECK(a);
    const pkv_array *G = pkv_get(a, "s0_grid"); CHECK(G);
    g = grid_of(G); CHECK(g);
    m = malloc(sizeof *m); sc = malloc(sizeof *sc); s2 = malloc(sizeof *s2);
    CHECK(m && sc && s2);
    const int32_t (*cg)[PKC_GRID_N] = (const int32_t (*)[PKC_GRID_N])g;
    pkc_sba_scene_init(sc);
    CHECK(pass_of(cg, PKC_SBA_PASS1, sc, m) == PK_OK);
    CHECK(m->L == 0);                                      /* no VM in pass 1 */
    CHECK(sc->vec[730] == 1 && sc->vec[720] == 0);         /* mode stored, but no tail */
    CHECK(sc->vec[619] == 0);                              /* no 616..719 A3 copy in the mode-1 arm */
    int n1 = 0; for (int i = 0; i < PKC_GRID_N; i++) n1 += m->mask[i] == 1;
    CHECK(n1 > 10 && sc->vec[612] == n1);
    /* FOS pass: a scene whose previous mask is replaced keeps it (stage 1 skipped); SHORT2 recomputes stage 1 */
    *s2 = *sc;
    memset(s2->mask, 0, sizeof s2->mask);
    CHECK(pass_of(cg, PKC_SBA_FOS2, s2, m) == PK_OK);
    int n2 = 0; for (int i = 0; i < PKC_GRID_N; i++) n2 += s2->mask[i] == 1;
    CHECK(n2 == 0);
    *s2 = *sc; memset(s2->mask, 0, sizeof s2->mask);
    CHECK(pass_of(cg, PKC_SBA_SHORT2, s2, m) == PK_OK);
    n2 = 0; for (int i = 0; i < PKC_GRID_N; i++) n2 += s2->mask[i] == 1;
    CHECK(n2 == n1);
    /* a failed pass leaves the scene untouched; a bad kind is rejected */
    *s2 = *sc;
    CHECK(pass_of(cg, 3, s2, m) == PK_E_ARG && !memcmp(s2, sc, sizeof *sc));
    CHECK(pass_of(cg, -1, s2, m) == PK_E_ARG);
    /* pass 1 stores the flag-word slots too (0x1028bb0d / 0x1028bb1f, before the pass switch) */
    pkc_sba_ctx c = CTX;
    static const uint8_t fl[8] = { 0xFE, 0xFE, 0xFE, 0xFF, 0xFF, 0xFE, 0x00, 0xFE };
    CHECK(pkc_sba_ctx_set_flags(&c, fl, 0x800) == PK_OK);
    pkc_sba_scene_init(s2);
    CHECK(pkc_sba_measure_scene(NULL, cg, NULL, &c, PKC_SBA_PASS1, s2, m) == PK_OK);
    CHECK(s2->vec[731] == 1 && s2->vec[732] == 0 && s2->known[731] && s2->known[732]);
    CHECK(pkc_sba_ctx_set_flags(&c, fl, 0x1000) == PK_OK);
    CHECK(pkc_sba_measure_scene(NULL, cg, NULL, &c, PKC_SBA_PASS1, s2, m) == PK_OK);
    CHECK(s2->vec[731] == 0 && s2->vec[732] == 1);
done:
    free(g); free(m); free(sc); free(s2); if (a) pkv_close(a);
    FINISH();
}

/* Flag bytes / flag word: the mode, gate table and the tail slots they drive (fcn.1028b8d0 0x1028bb05, 0x1028bcxx..) */
TEST flags_and_tail(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[8] = "";
    pkv_file *a = NULL; pkc_sba_measure *m = NULL; pkc_sba_scene *sc = NULL; int32_t (*g)[PKC_GRID_N] = NULL;
    if (!need_ctx()) FAILm("pkc_sba_ctx_load failed");
    a = pkv_open(PKV_DIR "/analysis_r4.pkv"); CHECK(a);
    const pkv_array *G = pkv_get(a, "s0_grid"); CHECK(G);
    g = grid_of(G); CHECK(g);
    const int32_t (*cg)[PKC_GRID_N] = (const int32_t (*)[PKC_GRID_N])g;
    m = malloc(sizeof *m); sc = malloc(sizeof *sc);
    CHECK(m && sc);
    pkc_sba_ctx c = CTX;                                   /* shallow copy: shares prog and params (read only) */
    static const struct { uint8_t f[8]; uint16_t w; int mode, v721, v722, v723, v724, v725, v731, v732; } T[] = {
        { { 0xFE, 0xFE, 0xFE, 0xFF, 0xFF, 0xFE, 0x00, 0xFE }, 0, 1, -1, -1, -1, -1, 0, 0, 0 },
        { { 0xFE, 0xFC, 0xFE, 0xFF, 0xFF, 0xFE, 0x01, 0xFE }, 0x800, 1, -1, -1, -1, -1, 1, 1, 0 },     /* 0xFC: sentinel for slot 721 */
        { { 0xFE, 0x01, 0xFE, 0xFF, 0xFF, 0xFE, 0x00, 0xFE }, 0x1000, 2, 1, -1, -1, -1, 0, 0, 1 },    /* flags[1] = 1 (orientation): flags[2] sentinel -> mode 2 */
        { { 0xFE, 0x01, 0x03, 0x00, 0x00, 0xFE, 0x00, 0xFE }, 0, 8, 1, 3, 0, 0, 0, 0, 0 },           /* flags[3] == 0 -> mode 8 */
        { { 0xFE, 0x01, 0x01, 0x05, 0x00, 0xFE, 0x00, 0xFE }, 0, 4, 1, 1, 5, 0, 0, 0, 0 },           /* flags[2] == 1 -> mode 4 */
    };
    for (size_t i = 0; i < sizeof T / sizeof *T; i++) {
        CHECK(pkc_sba_ctx_set_flags(&c, T[i].f, T[i].w) == PK_OK);
        CHECK(c.mode == T[i].mode);
        pkc_sba_scene_init(sc);
        pk_status st = pkc_sba_measure_scene(NULL, cg, NULL, &c, PKC_SBA_PASS1, sc, m);
        if (st == PK_OK) st = pkc_sba_measure_scene(NULL, cg, NULL, &c, PKC_SBA_SHORT2, sc, m);
        if (i >= 2 && st == PK_E_UNSUPPORTED) {
            /* modes 2 / 8 / 4 are never run by Kodak with the shipped flags and L reads unported slots there: the pass is refused
             * and *sc is not updated, so the tail slots (the flag-driven stores) are checked on pkc_vec_tail itself */
            static int32_t tv[PKC_SBA_VEC_N]; static uint8_t tk[PKC_SBA_VEC_N];
            memset(tv, 0, sizeof tv); memset(tk, 0, sizeof tk);
            pkc_vec_tail(&c, c.mode, tv, tk);
            CHECK(tv[730] == T[i].mode);
            CHECK(tv[721] == T[i].v721 && tv[722] == T[i].v722 && tv[723] == T[i].v723 && tv[724] == T[i].v724);
            CHECK(tv[725] == T[i].v725 && tv[731] == T[i].v731 && tv[732] == T[i].v732);
            CHECK(tv[720] == 700 && tv[726] == 250);
            continue;
        }
        CHECK(st == PK_OK);
        CHECK(sc->vec[730] == T[i].mode);
        CHECK(sc->vec[721] == T[i].v721 && sc->vec[722] == T[i].v722 && sc->vec[723] == T[i].v723 && sc->vec[724] == T[i].v724);
        CHECK(sc->vec[725] == T[i].v725 && sc->vec[731] == T[i].v731 && sc->vec[732] == T[i].v732);
        CHECK(sc->vec[720] == 700 && sc->vec[726] == 250);
    }
    static const uint8_t bad[8] = { 0xFE, 0x02, 0x02, 0x07, 0x07, 0xFE, 0x00, 0xFE };   /* reaches the uninitialised-local branch */
    CHECK(pkc_sba_ctx_set_flags(&c, bad, 0) == PK_E_VENDOR_DATA);
    CHECK(c.mode == 4);                                    /* unchanged on failure */
    CHECK(pkc_sba_ctx_set_flags(&c, T[0].f, 0x1800) == PK_E_ARG);
    CHECK(pkc_sba_ctx_set_flags(NULL, T[0].f, 0) == PK_E_ARG);
done:
    free(g); free(m); free(sc); if (a) pkv_close(a);
    FINISH();
}

TEST derived_config(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[8] = "";
    pkv_file *f = NULL, *a = NULL; pkc_sba_measure *m = NULL; pkc_sba_scene *sc = NULL; int32_t (*g)[PKC_GRID_N] = NULL;
    if (!need_ctx()) FAILm("pkc_sba_ctx_load failed");
    f = pkv_open(PKV_DIR "/sba_cfg.pkv"); CHECK(f);
    const pkv_array *T = pkv_get(f, "tail"), *EN = pkv_get(f, "en"), *PAR = pkv_get(f, "par"), *FL = pkv_get(f, "flags"),
                    *SC = pkv_get(f, "scalars"), *ES = pkv_get(f, "en_static");
    CHECK(T && EN && PAR && FL && SC && ES);
    CHECK(CTX.opening[0] == 879 && CTX.opening[1] == 1250 && CTX.opening[2] == 1386);
    CHECK(!memcmp(CTX.params + CTX.en_off, EN->data, 64));
    CHECK(!memcmp(CTX.params + 0xDC, PAR->data, PAR->n));
    CHECK(!memcmp(CTX.flags, FL->data, 8));
    CHECK(i32(SC)[0] == CTX.sel && i32(SC)[1] == CTX.mode);
    CHECK(!memcmp(CTX.en_static, ES->data, 44));
    static const uint8_t flags_k[8] = { 0xFE, 0xFE, 0xFE, 0xFF, 0xFF, 0xFE, 0x00, 0xFE };   /* Kodak-observed, gen_sba_truth.py */
    CHECK(!memcmp(CTX.flags, flags_k, 8) && CTX.flagsword == 0);
    /* the stage-1 struct's own scalars the tail reads */
    CHECK((int16_t)(CTX.params[0x10E] | CTX.params[0x10F] << 8) == 800);
    CHECK((int16_t)(CTX.params[0x110] | CTX.params[0x111] << 8) == 1200);
    /* the tail comes out of a real measure (pass 2); Kodak's own tail is checked in kodak_truth */
    a = pkv_open(PKV_DIR "/analysis_r4.pkv"); CHECK(a);
    const pkv_array *G = pkv_get(a, "s0_grid"); CHECK(G);
    g = grid_of(G); CHECK(g);
    m = malloc(sizeof *m); sc = malloc(sizeof *sc);
    CHECK(m && sc);
    pkc_sba_scene_init(sc);
    CHECK(pass_of((const int32_t (*)[PKC_GRID_N])g, PKC_SBA_FOS2, sc, m) == PK_OK);
    for (int s = 0; s < 13; s++) CHECK(i32(T)[s] == sc->vec[720 + s]);
done:
    free(g); free(m); free(sc); if (a) pkv_close(a); if (f) pkv_close(f);
    FINISH();
}

TEST pcode_structure(void) {
    if (!need_ctx()) FAILm("pkc_sba_ctx_load failed");
    ASSERT_EQ(264, CTX.prog.nrec);
    int tag1 = 0;
    for (int k = 0; k < CTX.prog.nrec; k++) { ASSERT(CTX.prog.rec[k].words); tag1 += CTX.prog.rec[k].tag == 1; }
    ASSERT_EQ(130, tag1);                               /* records 134..263 */
    ASSERT_EQ(1, CTX.prog.rec[156].tag); ASSERT_EQ(0, CTX.prog.rec[133].tag);
    /* record 156 is `PUSH v133 ; STORE v156 ; HALT` */
    static const uint16_t r156[] = { 1, 3, 133, 2, 156, 255 };
    ASSERT_EQ(6, CTX.prog.rec[156].nwords);
    ASSERT_EQ(0, memcmp(CTX.prog.rec[156].words, r156, sizeof r156));
    /* stage-1: pcode-dls_1.7's gate table starts 0x083f 0x0808 ... (en bytes 3f 08 08 08 08 08 01 01) */
    static const uint8_t en0[8] = { 0x3f, 0x08, 0x08, 0x08, 0x08, 0x08, 0x01, 0x01 };
    ASSERT_EQ(0, memcmp(CTX.params, en0, 8));
    PASS();
}

/* The pcode file read the way the DLL reads either byte order: a little-endian (word-swapped) copy decodes identically. */
TEST pcode_byte_order_and_errors(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[8] = "";
    char p[1200], tmp[] = "/tmp/pk_pcode_XXXXXX";
    static uint8_t raw[20000];
    uint8_t params[PKC_SBA_STRUCT_SIZE], params2[PKC_SBA_STRUCT_SIZE];
    pkc_sba_prog a = { 0, NULL }, b = { 0, NULL };
    int tmp_made = 0;
    CHECK(pkc_vendor_path(VENDOR_ROOT, "anselinstalldir/dataPathItems/sba/Pcode/pcode-dls_1.7", p, sizeof p) == PK_OK);
    FILE *fp = fopen(p, "rb"); CHECK(fp);
    size_t n = fread(raw, 1, sizeof raw, fp); fclose(fp);
    CHECK(n > 10000 && n < sizeof raw);
    CHECK(pkc_sba_pcode_load(p, params, &a) == PK_OK);
    int fd = mkstemp(tmp); CHECK(fd >= 0);
    tmp_made = 1;
    for (size_t i = 0; i + 1 < n; i += 2) { uint8_t t = raw[i]; raw[i] = raw[i + 1]; raw[i + 1] = t; }
    CHECK((size_t)write(fd, raw, n & ~(size_t)1) == (n & ~(size_t)1)); close(fd);
    CHECK(pkc_sba_pcode_load(tmp, params2, &b) == PK_OK);
    CHECK(!memcmp(params, params2, sizeof params));
    CHECK(a.nrec == b.nrec);
    for (int k = 0; k < a.nrec; k++) {
        CHECK(a.rec[k].nwords == b.rec[k].nwords && a.rec[k].tag == b.rec[k].tag);
        CHECK(!memcmp(a.rec[k].words, b.rec[k].words, (size_t)a.rec[k].nwords * 2));
    }
    pkc_sba_prog_free(&a); pkc_sba_prog_free(&b);
    /* truncated file: no 0xFA terminator -> vendor-data error (Kodak 0x18A8) */
    fd = open(tmp, O_WRONLY | O_TRUNC); CHECK(fd >= 0);
    CHECK(write(fd, raw, 100) == 100); close(fd);
    CHECK(pkc_sba_pcode_load(tmp, params2, &b) == PK_E_VENDOR_DATA && !b.rec);
    CHECK(pkc_sba_pcode_load("/nonexistent/pcode", params2, &b) == PK_E_VENDOR_DATA);
    CHECK(pkc_sba_pcode_load(NULL, params2, &b) == PK_E_ARG);
done:
    pkc_sba_prog_free(&a); pkc_sba_prog_free(&b);
    if (tmp_made) unlink(tmp);
    FINISH();
}

TEST ctx_errors(void) {
    pkc_sba_ctx c;
    ASSERT_EQ(PK_E_ARG, pkc_sba_ctx_load(NULL, DERIVED_ROOT, &c));
    ASSERT_EQ(PK_E_ARG, pkc_sba_ctx_load(VENDOR_ROOT, NULL, &c));
    ASSERT_EQ(PK_E_ARG, pkc_sba_ctx_load(VENDOR_ROOT, DERIVED_ROOT, NULL));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_sba_ctx_load("/nonexistent", DERIVED_ROOT, &c));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_sba_ctx_load(VENDOR_ROOT, "/nonexistent", &c));
    ASSERT(!c.prog.rec);                                /* freed on failure */
    static pkc_sba_measure m; static pkc_sba_scene sc; static int32_t g[3][PKC_GRID_N];
    pkc_sba_scene_init(&sc);
    ASSERT_EQ(PK_E_ARG, pkc_sba_measure_scene(NULL, NULL, NULL, &CTX, PKC_SBA_PASS1, &sc, &m));
    ASSERT_EQ(PK_E_ARG, pkc_sba_measure_scene(NULL, (const int32_t (*)[PKC_GRID_N])g, NULL, NULL, PKC_SBA_PASS1, &sc, &m));
    ASSERT_EQ(PK_E_ARG, pkc_sba_measure_scene(NULL, (const int32_t (*)[PKC_GRID_N])g, NULL, &CTX, PKC_SBA_PASS1, NULL, &m));
    ASSERT_EQ(PK_E_ARG, pkc_sba_measure_scene(NULL, (const int32_t (*)[PKC_GRID_N])g, NULL, &CTX, PKC_SBA_PASS1, &sc, NULL));
    pkc_sba_ctx_free(NULL);
    PASS();
}

/* The hue wheel / opening axes: the opening (879,1250,1386) -> (2029, 96, 359) (RE 17), and negative operands. */
TEST axes(void) {
    static const struct { int r, g, b, y, c1, c2; } T[] = {       /* values from pakon_fos.fos_opening_axes */
        { 879, 1250, 1386, 2029, 96, 359 }, { 0, 0, 0, 0, 0, 0 }, { 1000, 0, 0, 577, -408, -707 }, { 0, 1000, 0, 577, 816, 0 },
        { 0, 0, 1000, 577, -408, 707 }, { 4095, 0, 4095, 4729, -3344, 0 }, { -300, 200, -100, -115, 327, 141 } };
    for (size_t i = 0; i < sizeof T / sizeof *T; i++) {
        int32_t y, c1, c2;
        pkc_sba_axes(T[i].r, T[i].g, T[i].b, &y, &c1, &c2);
        ASSERT_EQ_FMT(T[i].y, y, "%d"); ASSERT_EQ_FMT(T[i].c1, c1, "%d"); ASSERT_EQ_FMT(T[i].c2, c2, "%d");
    }
    PASS();
}

/* ------------------------------------------------------------------ the VM on crafted programs */

#define NREC 264
static pkc_sba_prog build(const uint16_t *r133, int n133) {
    pkc_sba_prog p; p.nrec = NREC; p.rec = calloc(NREC, sizeof *p.rec);
    for (int k = 0; k < NREC; k++) {
        static const uint16_t dflt_f[] = { 1, 4, 0, 0, 2, 0, 255 };
        uint16_t *w; int n;
        if (k == 133) { n = n133; w = malloc((size_t)n * 2); memcpy(w, r133, (size_t)n * 2); }
        else if (k == 156) { static const uint16_t r[] = { 1, 3, 133, 2, 156, 255 }; n = 6; w = malloc(12); memcpy(w, r, 12); }
        else { n = 7; w = malloc(14); memcpy(w, dflt_f, 14); w[5] = (uint16_t)k; }
        p.rec[k].words = w; p.rec[k].nwords = n; p.rec[k].tag = k >= 134;
    }
    return p;
}
static pk_status run133(const uint16_t *r, int n, const int32_t *in, int nin, int32_t *L) {
    pkc_sba_prog p = build(r, n);
    pk_status st = pkc_sba_vm_l(&p, in, NULL, nin, L, NULL);
    pkc_sba_prog_free(&p);
    return st;
}
#define P_IMM(v) 1, 4, (uint16_t)((uint32_t)(v) >> 16), (uint16_t)((uint32_t)(v) & 0xFFFF)
#define P_IN(i) 1, 6, (i)
#define FIN 2, 133, 255

TEST vm_ops(void) {
    int32_t L = -999, in[4] = { 7, -7, 2147483647, 1000 };
    { static const uint16_t r[] = { P_IN(0), P_IN(1), 5, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-49, L); }
    { static const uint16_t r[] = { P_IN(1), P_IMM(2), 6, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-3, L); }  /* idiv truncates */
    { static const uint16_t r[] = { P_IN(2), P_IMM(1), 3, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(INT32_MIN, L); }   /* wraps */
    { static const uint16_t r[] = { P_IN(2), P_IN(2), 5, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(1, L); }
    { static const uint16_t r[] = { P_IN(3), 16, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(761, L); }  /* tanh(1)*1000 */
    { static const uint16_t r[] = { P_IN(1), 16, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-6, L); }    /* trunc toward 0 */
    { static const uint16_t r[] = { P_IMM(3), P_IMM(-4), 47, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(5, L); }
    { static const uint16_t r[] = { P_IN(0), 48, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-7, L); }   /* -|x| */
    { static const uint16_t r[] = { P_IN(1), 48, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-7, L); }
    { static const uint16_t r[] = { P_IN(0), P_IN(1), P_IMM(10), P_IMM(20), 31, FIN };   /* 7 > -7 -> 10 */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(10, L); }
    { static const uint16_t r[] = { P_IN(0), P_IN(1), P_IMM(10), P_IMM(20), 32, FIN };   /* 7 < -7 false -> 20 */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(20, L); }
    { static const uint16_t r[] = { P_IMM(5), P_IMM(9), P_IMM(2), P_IMM(3), 30, FIN };   /* MINN n=3 of 5,9,2 */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(2, L); }
    { static const uint16_t r[] = { P_IMM(5), P_IMM(9), P_IMM(2), P_IMM(3), 29, FIN };
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(9, L); }
    { static const uint16_t r[] = { P_IMM(-5), P_IMM(-6), P_IMM(2), 28, FIN };           /* MEANN: -11 / 2 truncates */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-5, L); }
    { static const uint16_t r[] = { P_IMM(0), P_IMM(0), 6, FIN };                         /* divide by zero */
      ASSERT_EQ(PK_E_ARG, run133(r, sizeof r / 2, in, 4, &L)); }
    { static const uint16_t r[] = { P_IN(9), FIN };                                       /* in[9] beyond nin */
      ASSERT_EQ(PK_E_ARG, run133(r, sizeof r / 2, in, 4, &L)); }
    { static const uint16_t r[] = { P_IMM(1), 99, FIN };                                  /* invalid opcode */
      ASSERT_EQ(PK_E_ARG, run133(r, sizeof r / 2, in, 4, &L)); }
    { static const uint16_t r[] = { 3, FIN };                                             /* stack underflow */
      ASSERT_EQ(PK_E_ARG, run133(r, sizeof r / 2, in, 4, &L)); }
    /* CSKIP (55) scans for label triples (254 9191 254): a nonzero condition continues after the 1st label, zero after
     * the 2nd; SKIP (54) pops n and continues after label n+1 */
    { static const uint16_t r[] = { P_IMM(1), 55, P_IMM(111), 254, 9191, 254, P_IMM(222), FIN };
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(222, L); }
    { static const uint16_t r[] = { P_IMM(0), 55, P_IMM(111), 254, 9191, 254, P_IMM(222), 254, 9191, 254, P_IMM(333), FIN };
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(333, L); }
    { static const uint16_t r[] = { P_IMM(0), 54, P_IMM(5), 254, 9191, 254, P_IMM(6), FIN };
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(6, L); }
    { static const uint16_t r[] = { P_IMM(0), 55, P_IMM(111), 254, 9191, 254, P_IMM(222), FIN };   /* scan runs off the record */
      ASSERT_EQ(PK_E_ARG, run133(r, sizeof r / 2, in, 4, &L)); }
    /* equality / zero boundaries and the ops no case above reaches */
    { static const uint16_t r[] = { P_IN(0), P_IN(0), P_IMM(10), P_IMM(20), 31, FIN };     /* SEL_GT, equal -> else */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(20, L); }
    { static const uint16_t r[] = { P_IN(0), P_IN(0), P_IMM(10), P_IMM(20), 34, FIN };     /* SEL_GE, equal -> then */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(10, L); }
    { static const uint16_t r[] = { P_IN(0), P_IN(0), P_IMM(10), P_IMM(20), 35, FIN };     /* SEL_LE */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(10, L); }
    { static const uint16_t r[] = { P_IN(0), P_IN(0), P_IMM(10), P_IMM(20), 33, FIN };     /* SEL_EQ */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(10, L); }
    { static const uint16_t r[] = { P_IN(0), P_IN(1), P_IMM(10), P_IMM(20), 36, FIN };     /* SEL_NE */
      ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(10, L); }
    { static const uint16_t r[] = { P_IMM(0), 48, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(0, L); }   /* -|0| */
    { static const uint16_t r[] = { P_IN(0), 7, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-7, L); }     /* NEG */
    { static const uint16_t r[] = { P_IMM(INT32_MIN), 7, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(INT32_MIN, L); }
    { static const uint16_t r[] = { P_IMM(3), 49, 5, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(9, L); }  /* DUP */
    { static const uint16_t r[] = { P_IMM(10), P_IMM(3), 50, 4, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-7, L); }   /* SWAP: 3 - 10 */
    { static const uint16_t cmp_op[] = { 56, 57, 58, 59, 60, 61 };                         /* GT LT EQ GE LE NE on (5,5) and (5,6) */
      static const int e55[] = { 0, 0, 1, 1, 1, 0 }, e56[] = { 0, 1, 0, 0, 1, 1 };
      for (int i = 0; i < 6; i++) {
          uint16_t r[] = { P_IMM(5), P_IMM(5), cmp_op[i], FIN };
          ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ_FMT(e55[i], L, "%d");
          uint16_t q[] = { P_IMM(5), P_IMM(6), cmp_op[i], FIN };
          ASSERT_EQ(PK_OK, run133(q, sizeof q / 2, in, 4, &L)); ASSERT_EQ_FMT(e56[i], L, "%d");
      } }
    { static const uint16_t r[] = { P_IMM(2), P_IMM(0), 62, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(0, L); }   /* AND */
    { static const uint16_t r[] = { P_IMM(2), P_IMM(0), 63, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(1, L); }   /* OR */
    { static const uint16_t r[] = { P_IMM(2), 64, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(0, L); }             /* NOT */
    { static const uint16_t r[] = { P_IMM(12), P_IMM(10), 68, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(8, L); }   /* BAND */
    { static const uint16_t r[] = { P_IMM(12), P_IMM(3), 69, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(15, L); }  /* BOR */
    { static const uint16_t r[] = { P_IMM(-5), P_IMM(1), 3, 253, FIN };  ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L)); ASSERT_EQ(-4, L); }  /* NOP 253 */
    { static const uint16_t r[] = { P_IMM(-4), 47, FIN };  /* hypot(-4, nothing) underflows */ ASSERT_EQ(PK_E_ARG, run133(r, sizeof r / 2, in, 4, &L)); }
    ASSERT_EQ(PK_E_ARG, pkc_sba_vm_l(NULL, in, NULL, 4, &L, NULL));
    /* opcode 16 = Kodak's msvcr71 _CItanh (pins I-5): (a, (int)(tanh(a * 0.001f) * 1000.0f)) from the native code's own run;
     * libm's tanh gives 999 for 19050..19061 */
    { static const int32_t K[][2] = { { 0, 0 }, { 1, 0 }, { 2, 1 }, { 3, 2 }, { 100, 99 }, { 346, 332 }, { 347, 333 }, { 1013, 767 },
          { 2000, 964 }, { 5953, 999 }, { 15000, 999 }, { 19048, 999 }, { 19049, 999 }, { 19050, 1000 }, { 19061, 1000 },
          { 19062, 1000 }, { 20000, 1000 }, { INT32_MAX, 1000 }, { -1, 0 }, { -3, -2 }, { -1013, -767 }, { -19049, -999 },
          { -19050, -1000 }, { INT32_MIN, -1000 } };
      for (size_t i = 0; i < sizeof K / sizeof *K; i++) {
          uint16_t r[] = { P_IMM(K[i][0]), 16, FIN };
          ASSERT_EQ(PK_OK, run133(r, sizeof r / 2, in, 4, &L));
          ASSERT_EQ_FMT(K[i][1], L, "%d");
      } }
    /* R18 guard (pins I-2): L derived from an unknown slot is PK_E_UNSUPPORTED; an unknown value that is discarded is fine */
    { static const uint16_t r[] = { P_IN(0), 7, FIN };
      pkc_sba_prog p = build(r, sizeof r / 2);
      uint8_t kn_ok[4] = { 1, 1, 1, 1 }, kn_bad[4] = { 0, 1, 1, 1 };
      ASSERT_EQ(PK_OK, pkc_sba_vm_l(&p, in, kn_ok, 4, &L, NULL));
      ASSERT_EQ(PK_E_UNSUPPORTED, pkc_sba_vm_l(&p, in, kn_bad, 4, &L, NULL));
      pkc_sba_prog_free(&p); }
    { static const uint16_t r[] = { P_IMM(1), P_IMM(2), P_IMM(10), P_IN(0), 32, FIN };       /* 1<2 picks C; D (unknown) not chosen */
      pkc_sba_prog p = build(r, sizeof r / 2);
      uint8_t kn_bad[4] = { 0, 1, 1, 1 };
      ASSERT_EQ(PK_OK, pkc_sba_vm_l(&p, in, kn_bad, 4, &L, NULL)); ASSERT_EQ(10, L);
      pkc_sba_prog_free(&p); }
    PASS();
}

SUITE(sba_measure_suite) {
    RUN_TEST(derived_config); RUN_TEST(synthetic_scenes); RUN_TEST(pass_kinds); RUN_TEST(flags_and_tail); RUN_TEST(kodak_truth); RUN_TEST(pcode_structure); RUN_TEST(pcode_byte_order_and_errors); RUN_TEST(ctx_errors);
    RUN_TEST(axes); RUN_TEST(vm_ops);
    RUN_TEST(roll_r4); RUN_TEST(roll_r1); RUN_TEST(roll_r12); RUN_TEST(roll_r2);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); RUN_SUITE(sba_measure_suite); pkc_sba_ctx_free(&CTX); GREATEST_MAIN_END();
}
