/* Task 18: the SBA exposure (fcn.102ae9d0's half-stop word, getSbaExposure's float) against Kodak at x87 PC53
 * (vectors/exposure_truth.pkv, lab/vectors/gen_exposure_truth.py, lab/rollbal/truth/t18, docs/re/23-sba-exposure.md).
 * Runs: r4 / r2 / r1 / r12 on Task 11's Kodak film base and on v1's (r4v1 ...), every crafted roll of Tasks 12-17, this
 * task's t18a..d (large exposures of both signs, both pass-2 kinds), RE 11's falloff-gate variants fg0..fg11 re-run at
 * PC53 (x1.15 / x0.85 brightness: fg7 / fg8), and p1: t15cap's 41 scenes with stores at the writer's operands
 * (lab/rollbal/gen_t18poke.py). Every writer call (both SBA instances) is checked against the port's word; every scene of
 * the sba instance against getSbaExposure's float, the flesh calculator's arg7 and, where the roll ran the balance, the
 * falloff export gate's decision through pkc_falloff_enabled. */
#include "greatest.h"
#include "pkv.h"
#include "falloff.h"
#include "analysis/exposure.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static pkc_sba_ctx CTX;
static pkc_falloff_params FP;
static int ctx_ok;
static int need_ctx(void) {
    if (!ctx_ok)
        ctx_ok = pkc_sba_ctx_load(VENDOR_ROOT, DERIVED_ROOT, &CTX) == PK_OK && pkc_falloff_params_load(VENDOR_ROOT, &FP) == PK_OK;
    return ctx_ok;
}
static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }

#define CHECK(cond) do { if (!(cond)) { fail_line = __LINE__; fail_expr = #cond; goto done; } } while (0)
#define FINISH() do { if (fail_line) { static char fmsg[300]; snprintf(fmsg, sizeof fmsg, "line %d: %s (%s)", fail_line, fail_expr, detail); FAILm(fmsg); } PASS(); } while (0)

typedef struct { int n, mode, gated, poked; const int32_t *y, *yo, *hs, *L, *ebits, *gate, *flesh; } run;
static int get_run(const pkv_file *t, int e, run *r) {
    char nm[32]; const pkv_array *a[8];
    static const char *const K[8] = { "meta", "y", "yo", "hs", "L", "ebits", "gate", "flesh" };
    for (int j = 0; j < 8; j++) {
        snprintf(nm, sizeof nm, "e%d_%s", e, K[j]);
        if (!(a[j] = pkv_get(t, nm)) || a[j]->dtype != 4) return 0;
    }
    r->n = i32(a[0])[0]; r->mode = i32(a[0])[1]; r->gated = i32(a[0])[2]; r->poked = i32(a[0])[3];
    if (a[0]->n != 4 || a[1]->n != (size_t)(2 * r->n) || a[2]->n != a[1]->n || a[3]->n != a[1]->n || a[4]->n != a[1]->n ||
        a[5]->n != (size_t)r->n || a[6]->n != (size_t)r->n || a[7]->n != (size_t)r->n) return 0;
    r->y = i32(a[1]); r->yo = i32(a[2]); r->hs = i32(a[3]); r->L = i32(a[4]); r->ebits = i32(a[5]); r->gate = i32(a[6]); r->flesh = i32(a[7]);
    return 1;
}
static int run_index(const pkv_file *t, const char *id) { return pkv_list_index(t, "names", id); }
static int nruns(const pkv_file *t) { return pkv_list_count(t, "names"); }
static uint32_t fbits(double v) { float f = (float)v; uint32_t b; memcpy(&b, &f, 4); return b; }
static pk_status stops_of(int16_t yword, double *st) {
    pkc_sba_triple_out t; memset(&t, 0, sizeof t);
    t.triple[0] = yword;
    return pkc_sba_exposure_stops(&t, &CTX, st);
}

/* every writer call: the port's word = Kodak's (both instances, the stored operands of p1 included) */
TEST kodak_writer(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[200] = "";
    pkv_file *t = pkv_open(PKV_DIR "/exposure_truth.pkv");
    int ncall = 0, nrun = 0;
    CHECK(t);
    nrun = nruns(t);
    for (int e = 0; e < nrun; e++) {
        run r; CHECK(get_run(t, e, &r));
        for (int i = 0; i < 2 * r.n; i++) {
            CHECK(r.y[i] == (int16_t)r.y[i]);
            int got = pkc_sba_exposure_halfstops((int16_t)r.y[i], r.yo[i]);
            snprintf(detail, sizeof detail, "run %d call %d: Y %d Yo %d port %d kodak %d", e, i, r.y[i], r.yo[i], got, r.hs[i]);
            CHECK(got == r.hs[i]);
            ncall++;
        }
    }
    snprintf(detail, sizeof detail, "%d runs, %d calls", nrun, ncall);
    CHECK(nrun == 54 && ncall == 786);
done:
    pkv_close(t);
    FINISH();
}

/* every scene of the sba instance: the triple's Y word through pkc_sba_exposure_stops (Yo from the dpi opening) gives
 * getSbaExposure's float, the flesh calculator's arg7 and the falloff gate's decision */
TEST kodak_stops(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[200] = "";
    pkv_file *t = NULL;
    int nscene = 0, ngate = 0, non = 0;
    if (!need_ctx()) FAILm("load failed");
    t = pkv_open(PKV_DIR "/exposure_truth.pkv"); CHECK(t);
    for (int e = 0; e < nruns(t); e++) {
        run r; CHECK(get_run(t, e, &r));
        for (int k = 0; k < r.n; k++) {
            CHECK(r.yo[k] == 2029);                         /* the sba instance's operands are never stored to (p1: Y only) */
            if (!r.poked) CHECK(r.y[k] == (int16_t)(r.L[k] + 2029));    /* the triple's Y word = int16(L + Yo) */
            double st = 99;
            CHECK(stops_of((int16_t)r.y[k], &st) == PK_OK);
            snprintf(detail, sizeof detail, "run %d scene %d: port %.9g (%08x) kodak %08x", e, k, st, fbits(st), (uint32_t)r.ebits[k]);
            CHECK(fbits(st) == (uint32_t)r.ebits[k] && (double)(float)st == st && st == r.hs[k] * 0.5);
            CHECK(fbits(st) == (uint32_t)r.flesh[k]);
            if (r.gated) {
                CHECK(r.gate[k] == 0 || r.gate[k] == 1);
                CHECK(pkc_falloff_enabled(&FP, st) == r.gate[k]);
                ngate++; non += r.gate[k];
            } else CHECK(r.gate[k] == -1);
            nscene++;
        }
    }
    snprintf(detail, sizeof detail, "%d scenes, %d gate decisions (%d on)", nscene, ngate, non);
    CHECK(nscene == 393 && ngate == 115);
done:
    pkv_close(t);
    FINISH();
}

/* RE 11 / 18 and the brief: r4 0 / -0.5 / -1.0 / +1.0 stops (falloff on / on / off / on), r2 +4.0 / -2.5 / +1.5 / -0.5 /
 * +1.5 / +1.0 -- Kodak's at PC53 on both film bases --, and RE 11's brightness variants of r4 scene 2: x1.15 -> -0.5
 * (falloff on), x0.85 -> -2.0 (off) */
TEST brief_numbers(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[200] = "";
    pkv_file *t = NULL;
    static const struct { const char *id; int n; double st[6]; int on[6]; } B[] = {
        { "r4", 4, { 0, -0.5, -1.0, 1.0 }, { 1, 1, 0, 1 } },
        { "r4v1", 4, { 0, -0.5, -1.0, 1.0 }, { 1, 1, 0, 1 } },
        { "r2", 6, { 4.0, -2.5, 1.5, -0.5, 1.5, 1.0 }, { 1, 0, 1, 1, 1, 1 } },
        { "r2v1", 6, { 4.0, -2.5, 1.5, -0.5, 1.5, 1.0 }, { 1, 0, 1, 1, 1, 1 } },
        { "fg7", 4, { 0, -0.5, -0.5, 1.0 }, { 1, 1, 1, 1 } },
        { "fg8", 4, { 0, -0.5, -2.0, 1.0 }, { 1, 1, 0, 1 } },
    };
    if (!need_ctx()) FAILm("load failed");
    t = pkv_open(PKV_DIR "/exposure_truth.pkv"); CHECK(t);
    for (size_t b = 0; b < sizeof B / sizeof B[0]; b++) {
        int e = run_index(t, B[b].id); run r;
        CHECK(e >= 0 && get_run(t, e, &r) && r.n == B[b].n && r.gated);
        for (int k = 0; k < r.n; k++) {
            double st = 99;
            CHECK(stops_of((int16_t)r.y[k], &st) == PK_OK);
            snprintf(detail, sizeof detail, "%s scene %d: %g (brief %g)", B[b].id, k, st, B[b].st[k]);
            CHECK(st == B[b].st[k] && r.gate[k] == B[b].on[k] && pkc_falloff_enabled(&FP, st) == B[b].on[k]);
        }
    }
done:
    pkv_close(t);
    FINISH();
}

/* p1's stored operands, each Kodak's word (asserted in the vector here, so a regenerated vector cannot silently change
 * the documented behaviour): x = Y - Yo in 7/1000 half-stops, rounded half away from zero, 32-bit registers throughout */
TEST stored_operands(void) {
    int fail_line = 0; const char *fail_expr = ""; char detail[200] = "";
    pkv_file *t = pkv_open(PKV_DIR "/exposure_truth.pkv");
    static const struct { int call, y, yo, hs; const char *why; } C[] = {
        { 1, 2029 + 71, 2029, 0, "0.497" }, { 2, 2029 + 72, 2029, 1, "0.504" }, { 3, 2029 - 71, 2029, 0, "-0.497" },
        { 4, 2029 - 72, 2029, -1, "-0.504" }, { 5, 2029 + 500, 2029, 4, "tie 3.5 away from zero" },
        { 6, 2029 - 500, 2029, -4, "tie -3.5 (floor(x + .5) gives -3)" }, { 7, 2029 + 1500, 2029, 11, "tie 10.5 (half-even gives 10)" },
        { 8, 2029 - 1500, 2029, -11, "tie -10.5" }, { 9, 2029 - 142, 2029, -1, "-0.5 stop: falloff on" },
        { 10, 2029 - 215, 2029, -2, "-1.0 stop: falloff off" }, { 11, 2029 - 214, 2029, -1, "-1.498" },
        { 12, 2029 + 2000, 2029, 14, "7.0 stops: falloff on" }, { 13, 2029 + 2071, 2029, 14, "14.497" },
        { 14, 2029 + 2072, 2029, 15, "7.5 stops: falloff off" }, { 15, 2029 - 1071, 2029, -7, "-7.497" },
        { 16, 2029 - 1072, 2029, -8, "-4.0 stops = flesh exposureLimit" }, { 17, 2029 - 1215, 2029, -9, "-4.5 stops" },
        { 18, 32767, 2029, 215, "int16 max word" }, { 19, -32768, 2029, -244, "int16 min word" }, { 20, 2029, 2029, 0, "0" },
        { 21, 2028, 2029, 0, "-0.007" }, { 22, 2029 + 2500, 2029, 18, "tie 17.5" }, { 23, 2029 - 2500, 2029, -18, "tie -17.5" },
        { 24, 2029 + 3500, 2029, 25, "tie 24.5 (half-even gives 24)" },
        { 42, 500, 0, 4, "Yo 0" }, { 43, -32768, 56755, -627, "largest negative x of an int16 opening" },
        { 44, 32767, -56755, 627, "largest positive x" }, { 45, -32768, 0x7fffffff, -229, "x wraps in 32 bits" },
        { 46, 0, INT32_MIN, 0, "x = INT32_MIN, x * 1190 wraps to 0" }, { 47, 1, INT32_MIN, 0, "x wraps, product wraps" },
        { 48, 0, 1000000, -7000, "exact -7000: biased -7000.5 truncated" }, { 49, 0, -1800000, 12600, "exact 12600" },
        { 50, 0, -1805000, -12630, "x * 1190 wraps negative" }, { 51, 0, -1804575, -12631, "x * 1190 + 85000 wraps" },
        { 52, 0, 1804575, 12631, "x * 1190 - 85000 wraps" }, { 53, 1000, 1000, 0, "0" },
    };
    int e = -1; run r;
    CHECK(t && (e = run_index(t, "p1")) >= 0 && get_run(t, e, &r) && r.poked && r.n == 41);
    for (size_t c = 0; c < sizeof C / sizeof C[0]; c++) {
        int i = C[c].call - 1;
        snprintf(detail, sizeof detail, "call %d (%s): kodak Y %d Yo %d -> %d", C[c].call, C[c].why, r.y[i], r.yo[i], r.hs[i]);
        CHECK(r.y[i] == C[c].y && r.yo[i] == C[c].yo && r.hs[i] == C[c].hs);
        CHECK(pkc_sba_exposure_halfstops((int16_t)C[c].y, C[c].yo) == C[c].hs);
    }
done:
    pkv_close(t);
    FINISH();
}

TEST bad_args(void) {
    if (!need_ctx()) FAILm("load failed");
    pkc_sba_triple_out t; memset(&t, 0, sizeof t);
    double st = 42;
    ASSERT_EQ(PK_E_ARG, pkc_sba_exposure_stops(NULL, &CTX, &st));
    ASSERT_EQ(PK_E_ARG, pkc_sba_exposure_stops(&t, NULL, &st));
    ASSERT_EQ(PK_E_ARG, pkc_sba_exposure_stops(&t, &CTX, NULL));
    t.triple[0] = 32768;
    ASSERT_EQ(PK_E_ARG, pkc_sba_exposure_stops(&t, &CTX, &st));
    t.triple[0] = -32769;
    ASSERT_EQ(PK_E_ARG, pkc_sba_exposure_stops(&t, &CTX, &st));
    ASSERT_EQ(42.0, st);
    t.triple[0] = -32768;
    ASSERT_EQ(PK_OK, pkc_sba_exposure_stops(&t, &CTX, &st));
    ASSERT_EQ(-122.0, st);
    PASS();
}

SUITE(exposure) {
    RUN_TEST(kodak_writer); RUN_TEST(kodak_stops); RUN_TEST(brief_numbers); RUN_TEST(stored_operands); RUN_TEST(bad_args);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(exposure);
    pkc_sba_ctx_free(&CTX);
    GREATEST_MAIN_END();
}
