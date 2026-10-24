/* Task 16: the roll scpLut against Kodak's own core FUN_10287eb0 at x87 PC53 (vectors/scplut_truth.pkv,
 * lab/vectors/gen_scplut_truth.py, lab/rollbal/truth/t16). Entries: every real and crafted roll of Tasks 11-15 (FOS#1
 * words as Kodak's analyzeScpLutBalance read them; r1 / r12 / syns ran no FOS -> zero words), the same rolls under two
 * edited SCPLut dpis (vA: DMIN_PIVOT, visualWeighting off, prop 1.25, thr 0.1; vB: SCP_OFFSET, thr 0), and 25 crafted
 * core arguments (lab/rollbal/gen_t16poke.py: the slopeDist = 0.30 boundary, int16 extremes, every offset option,
 * truncation and int16 wrap of the fill, NaN slopes, a 64-bit _ftol2 value). Each must give Kodak's nine result doubles
 * bit for bit (plus the worker's tenth, the spread of the final slopes) and its 3x4096 LUT (FNV-1a 64 of all 24576
 * bytes; element-wise where the LUT is stored). NaN results compare as NaN (Kodak's x87 indefinite is 0xfff8...). */
#include "greatest.h"
#include "pkv.h"
#include "analysis/scplut.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }
static const double *f64(const pkv_array *a) { return (const double *)a->data; }

static uint64_t fnv64(const pkc_lut3 *L) {
    const unsigned char *b = (const unsigned char *)L->t; uint64_t h = 0xcbf29ce484222325ull;
    for (size_t i = 0; i < sizeof L->t; i++) { h ^= b[i]; h *= 0x100000001b3ull; }
    return h;
}
static int same_double(double a, double b) { return (isnan(a) && isnan(b)) || memcmp(&a, &b, sizeof a) == 0; }

/* A FOS#1 result carrying entry e's words; junk in the high 16 bits (Kodak reads the low word with movsx) and in every
 * field the scpLut must not read. */
static void fos_of(const int32_t *w, int valid, int32_t junk, pkc_fos_result *f) {
    memset(f, 0x5a, sizeof *f);
    f->valid = valid; f->calc_err = 0;
    if (!valid) return;
    f->gm_slope = w[0] + junk; f->gm_off = w[1] - junk; f->ill_slope = w[2] + junk; f->ill_off = w[3] + junk;
    for (int c = 0; c < 3; c++) f->dmin[c] = w[4 + c] - junk;
}
static void params_of(const int32_t *opt, const double *par, pkc_scplut_params *p) {
    memset(p, 0, sizeof *p);
    p->offset_option = (int16_t)opt[0]; p->visual_weighting = (uint8_t)opt[1]; p->prop = par[0]; p->thr = par[1];
    p->modify_dmin = 1; p->run_after_lut = 1; p->ntd_choice = 1; p->ctd_choice = 2;
}

/* compare the port on entry e of t (with the given params) against Kodak; 0 = equal, else a description in msg */
static int check_entry(pkv_file *t, int e, const pkc_scplut_params *p, int32_t junk, char *msg, size_t cap) {
    char nm[32]; const pkv_array *X[6]; static const char *const sfx[6] = { "meta", "words", "opt", "par", "res", "fnv" };
    for (int j = 0; j < 6; j++) { snprintf(nm, sizeof nm, "e%d_%s", e, sfx[j]); X[j] = pkv_get(t, nm); if (!X[j]) { snprintf(msg, cap, "e%d: no %s", e, sfx[j]); return 1; } }
    snprintf(nm, sizeof nm, "e%d_lut_id", e); const pkv_array *lid = pkv_get(t, nm), *luts = pkv_get(t, "luts");
    pkc_fos_result f; fos_of(i32(X[1]), i32(X[0])[3], junk, &f);
    pkc_scplut_params pp; if (!p) { params_of(i32(X[2]), f64(X[3]), &pp); p = &pp; }
    pkc_lut3 *L = malloc(sizeof *L); pkc_scplut_result r; memset(&r, 0x77, sizeof r);
    if (!L) { snprintf(msg, cap, "oom"); return 1; }
    pk_status st = pkc_scplut_build(p, &f, L, &r);
    int bad = 0;
    if (st != PK_OK) { snprintf(msg, cap, "e%d: status %d", e, (int)st); bad = 1; }
    const double *k = f64(X[4]), got[10] = { r.slope[0], r.slope[1], r.slope[2], r.offset[0], r.offset[1], r.offset[2],
                                             r.slope_dist, r.slope_limiter, r.visual_gamma, r.slope_spread };
    for (int j = 0; j < 10 && !bad; j++)
        if (!same_double(got[j], k[j])) { snprintf(msg, cap, "e%d: result double %d: %.17g, Kodak %.17g", e, j, got[j], k[j]); bad = 1; }
    if (!bad && lid && i32(lid)[0] >= 0 && luts) {
        const int16_t *K = (const int16_t *)luts->data + (size_t)i32(lid)[0] * 3 * 4096;
        for (int c = 0; c < 3 && !bad; c++)
            for (int i = 0; i < 4096 && !bad; i++)
                if (L->t[c][i] != K[c * 4096 + i]) { snprintf(msg, cap, "e%d: LUT[%d][%d] = %d, Kodak %d", e, c, i, L->t[c][i], K[c * 4096 + i]); bad = 1; }
    }
    uint64_t h = fnv64(L), hk = (uint64_t)(uint32_t)i32(X[5])[0] | (uint64_t)(uint32_t)i32(X[5])[1] << 32;
    if (!bad && h != hk) { snprintf(msg, cap, "e%d: LUT hash %016llx, Kodak %016llx", e, (unsigned long long)h, (unsigned long long)hk); bad = 1; }
    free(L);
    return bad;
}

/* Every entry, twice: plain words and words with junk high halves. */
TEST kodak_truth(void) {
    pkv_file *t = pkv_open(PKV_DIR "/scplut_truth.pkv"); ASSERT(t);
    int n = i32(pkv_get(t, "n"))[0], bad = 0, ncase = 0, nflag0 = 0; char msg[200] = "";
    for (int e = 0; e < n && !bad; e++) {
        bad = check_entry(t, e, NULL, 0, msg, sizeof msg) || check_entry(t, e, NULL, 0x7fff0000, msg, sizeof msg);
        char nm[32]; snprintf(nm, sizeof nm, "e%d_meta", e); const int32_t *m = i32(pkv_get(t, nm));
        ncase += m[4] > 0; nflag0 += m[3] == 0;
    }
    pkv_close(t);
    if (bad) FAILm(msg);
    ASSERT_EQ_FMT(50, n, "%d"); ASSERT_EQ_FMT(28, ncase, "%d"); ASSERT_EQ_FMT(5, nflag0, "%d");   /* r1, r12, syns, vA_r1, vB_r1: no FOS */
    PASS();
}

/* The brief's slopes (RE 16: FOS#1 gm -219 / ill 386 on v1's film base) are Kodak's r4v1 entry at PC53; on Kodak's own
 * film base (Task 11, the pipeline's input since then) FOS#1 is gm -217 / ill 388 and the slopes move. The port must
 * reproduce both entries (bit for bit, as in kodak_truth). */
TEST brief_slopes(void) {
    pkv_file *t = pkv_open(PKV_DIR "/scplut_truth.pkv"); ASSERT(t);
    const double *r4 = f64(pkv_get(t, "e0_res")), *r4v1 = f64(pkv_get(t, "e2_res"));
    const int32_t *w4 = i32(pkv_get(t, "e0_words")), *w4v1 = i32(pkv_get(t, "e2_words"));
    double a[3], b[3]; memcpy(a, r4, sizeof a); memcpy(b, r4v1, sizeof b);
    int ww[4] = { w4[0], w4[2], w4v1[0], w4v1[2] };
    char msg[200] = "";
    int bad = check_entry(t, 0, NULL, 0, msg, sizeof msg) || check_entry(t, 2, NULL, 0, msg, sizeof msg);   /* the port on both */
    pkv_close(t);
    if (bad) FAILm(msg);
    ASSERT_EQ(-217, ww[0]); ASSERT_EQ(388, ww[1]); ASSERT_EQ(-219, ww[2]); ASSERT_EQ(386, ww[3]);
    ASSERT_IN_RANGE(1.005645, b[0], 1e-6); ASSERT_IN_RANGE(1.005056, b[1], 1e-6); ASSERT_IN_RANGE(0.941887, b[2], 1e-6);
    ASSERT_IN_RANGE(1.005917, a[0], 1e-6); ASSERT_IN_RANGE(1.004847, a[1], 1e-6); ASSERT_IN_RANGE(0.941816, a[2], 1e-6);
    PASS();
}

/* No FOS (r1: 1 scene): the shipped dpi gives the identity, whatever the FOS struct holds. */
TEST no_fos_identity(void) {
    pkc_scplut_params p; pkc_fos_result f; pkc_lut3 *L = malloc(sizeof *L); ASSERT(L);
    ASSERT_EQ(PK_OK, pkc_scplut_params_load(VENDOR_ROOT, &p));
    int32_t w[7] = { 900, 50, -700, 30, 400, 800, 900 };
    fos_of(w, 1, 0, &f); f.valid = 0;            /* words present but not valid: Kodak passes zeros */
    pk_status st = pkc_scplut_build(&p, &f, L, NULL);
    int ident = 1;
    for (int c = 0; c < 3; c++) for (int i = 0; i < 4096; i++) ident &= L->t[c][i] == i;
    free(L);
    ASSERT_EQ(PK_OK, st); ASSERT(ident);
    PASS();
}

/* FOS calc error (t15d): Kodak never reaches the scpLut; the port refuses and leaves out alone. */
TEST calc_error(void) {
    pkc_scplut_params p; pkc_fos_result f; pkc_lut3 *L = malloc(sizeof *L); ASSERT(L);
    ASSERT_EQ(PK_OK, pkc_scplut_params_load(VENDOR_ROOT, &p));
    memset(&f, 0, sizeof f); f.valid = 0; f.calc_err = 0x189d;
    memset(L, 0x33, sizeof *L);
    pk_status st = pkc_scplut_build(&p, &f, L, NULL);
    int untouched = L->t[0][0] == 0x3333 && L->t[2][4095] == 0x3333;
    free(L);
    ASSERT_EQ(PK_E_ARG, st); ASSERT(untouched);
    PASS();
}

/* every loaded field against Kodak's Impl copy of entry e (dumped at 0x10212937): modifyDmin, offsetOption, useSCPLut,
 * runSCPAfterLut, visualWeighting, ntdChoice, ctdChoice, then prop and thr bit for bit */
static int same_as_impl(pkv_file *t, int e, const pkc_scplut_params *p) {
    char nm[32]; snprintf(nm, sizeof nm, "e%d_impl", e); const pkv_array *a = pkv_get(t, nm);
    snprintf(nm, sizeof nm, "e%d_impl_par", e); const pkv_array *b = pkv_get(t, nm);
    if (!a || !b) return 0;
    const int32_t *k = i32(a);
    return p->modify_dmin == k[0] && p->offset_option == k[1] && k[2] == 1 && p->run_after_lut == k[3] &&
           p->visual_weighting == k[4] && p->ntd_choice == k[5] && p->ctd_choice == k[6] &&
           memcmp(&p->prop, f64(b), 8) == 0 && memcmp(&p->thr, f64(b) + 1, 8) == 0;
}

/* The shipped dpi, as Kodak's Impl held it (dumped at 0x10212937 on every run: 01 . 02 00 01 01 01 . 01 00 02 00 ...
 * 0.7 0.3; entry 0 = r4). */
TEST params_shipped(void) {
    pkc_scplut_params p; memset(&p, 0x5a, sizeof p);
    ASSERT_EQ(PK_OK, pkc_scplut_params_load(VENDOR_ROOT, &p));
    pkv_file *t = pkv_open(PKV_DIR "/scplut_truth.pkv"); ASSERT(t);
    int same = same_as_impl(t, 0, &p);
    pkv_close(t);
    ASSERT(same);
    uint64_t pb, tb; memcpy(&pb, &p.prop, 8); memcpy(&tb, &p.thr, 8);
    ASSERT_EQ(2, p.offset_option); ASSERT_EQ(1, p.visual_weighting); ASSERT_EQ(1, p.modify_dmin); ASSERT_EQ(1, p.run_after_lut);
    ASSERT_EQ(1, p.ntd_choice); ASSERT_EQ(2, p.ctd_choice);
    ASSERT_EQ(0x3fe6666666666666ull, pb); ASSERT_EQ(0x3fd3333333333333ull, tb);
    PASS();
}

/* temp vendor tree holding one SCPLut dpi */
static char ROOTD[] = "/tmp/pk_scp_XXXXXX";
static int tree_ok;
static const char *const SUB[3] = { "/anselinstalldir", "/dataPathItems", "/SCPLut" };
static int tree_make(void) {
    char d[300];
    strcpy(ROOTD, "/tmp/pk_scp_XXXXXX");
    if (!mkdtemp(ROOTD)) return 0;
    snprintf(d, sizeof d, "%s", ROOTD);
    for (int i = 0; i < 3; i++) { strncat(d, SUB[i], sizeof d - strlen(d) - 1); if (mkdir(d, 0700)) return 0; }
    return tree_ok = 1;
}
static const char *dpi_path(void) {
    static char p[400]; snprintf(p, sizeof p, "%s/anselinstalldir/dataPathItems/SCPLut/SCPLut-scanner-prod-gen-default-default-default.dpi", ROOTD);
    return p;
}
static int write_bytes(const void *b, size_t n) {
    FILE *o = fopen(dpi_path(), "wb"); if (!o) return 0;
    size_t w = fwrite(b, 1, n, o); return fclose(o) == 0 && w == n;
}
static void tree_free(void) {
    if (!tree_ok) return;
    unlink(dpi_path());
    for (int i = 2; i >= 0; i--) {
        char d[300]; snprintf(d, sizeof d, "%s", ROOTD);
        for (int j = 0; j <= i; j++) strncat(d, SUB[j], sizeof d - strlen(d) - 1);
        rmdir(d);
    }
    rmdir(ROOTD); tree_ok = 0;
}
/* the shipped dpi with one line replaced */
static int write_edit(const char *from, const char *to) {
    char src[700]; snprintf(src, sizeof src, "%s/anselinstalldir/dataPathItems/SCPLut/SCPLut-scanner-prod-gen-default-default-default.dpi", VENDOR_ROOT);
    FILE *f = fopen(src, "rb"); if (!f) return 0;
    char buf[4096], out[4200]; size_t n = fread(buf, 1, sizeof buf - 1, f); fclose(f); buf[n] = 0;
    char *hit = from ? strstr(buf, from) : NULL;
    if (from && !hit) return 0;
    if (!hit) return write_bytes(buf, n);
    size_t a = (size_t)(hit - buf);
    memcpy(out, buf, a); size_t m = a + (size_t)snprintf(out + a, sizeof out - a, "%s%s", to, hit + strlen(from));
    return write_bytes(out, m);
}

/* Changed dpi -> changed params and LUT, end to end: Kodak read dpi/vA.dpi, vB.dpi and vE.dpi (lab/rollbal/truth/t16:
 * vA/vB change the four core parameters, vE modifyDmin, runSCPAfterLut, ntdChoice and ctdChoice) and built the LUTs of
 * the entries in variant_e; the port loads the same files: every field must equal Kodak's Impl copy and the LUTs must
 * be Kodak's. vC (prop 2.5): Kodak's PIBegin fails (-20); vD (useSCPLut false): not ported. */
TEST params_variants(void) {
    pkv_file *t = pkv_open(PKV_DIR "/scplut_truth.pkv"); ASSERT(t);
    static const char *const V[5] = { "dpi_vA", "dpi_vB", "dpi_vE", "dpi_vC", "dpi_vD" };
    const int32_t *ve = i32(pkv_get(t, "variant_e"));
    int ok = tree_make(), bad = 0, nent = 0; char msg[200] = "";
    pk_status st[5] = { PK_OK, PK_OK, PK_OK, PK_OK, PK_OK }; pkc_scplut_params p[5];
    for (int v = 0; v < 5 && ok; v++) {
        const pkv_array *b = pkv_get(t, V[v]);
        ok = b && write_bytes(b->data, b->n);
        if (ok) st[v] = pkc_scplut_params_load(ROOTD, &p[v]);
    }
    tree_free();
    for (int v = 0; v < 3 && ok && !bad; v++) {
        if (st[v] != PK_OK) { snprintf(msg, sizeof msg, "%s: status %d", V[v], (int)st[v]); bad = 1; break; }
        for (int j = 0; j < 3 && !bad; j++) {
            int e = ve[3 * v + j];
            if (e < 0) continue;
            nent++;
            if (!same_as_impl(t, e, &p[v])) { snprintf(msg, sizeof msg, "%s: params differ from Kodak's Impl (e%d)", V[v], e); bad = 1; }
            else bad = check_entry(t, e, &p[v], 0, msg, sizeof msg);
        }
    }
    pkv_close(t);
    ASSERT(ok);
    if (bad) FAILm(msg);
    ASSERT_EQ_FMT(7, nent, "%d");
    ASSERT_EQ(PK_E_VENDOR_DATA, st[3]); ASSERT_EQ(PK_E_VENDOR_DATA, st[4]);
    PASS();
}

/* Loader rules (header): each edit of the shipped dpi must fail; the boundary values Kodak accepts must load. */
TEST params_validation(void) {
    static const char *const rej[][2] = {
        { "slopeDeltaThreshold = 0.30", "slopeDeltaThreshold = -0.01" }, { "slopeDeltaThreshold = 0.30", "slopeDeltaThreshold = 2.0001" },
        { "proportionalCorrection = 0.7", "proportionalCorrection = nan" }, { "proportionalCorrection = 0.7", "proportionalCorrection = inf" },
        { "proportionalCorrection = 0.7", "proportionalCorrection = x" }, { "offsetOption = ANS_SCPLUT_ZERO_PIVOT", "offsetOption = ZERO" },
        { "useSCPLut = true", "useSCPLut = 1" }, { "slopeDeltaThreshold", "slopeDeltaThresh" },
        { "ctdChoice", "ctd" } };
    static const struct { const char *from, *to; int field; double want; } acc[] = {
        { "slopeDeltaThreshold = 0.30", "slopeDeltaThreshold = 2", 0, 2.0 }, { "proportionalCorrection = 0.7", "proportionalCorrection = 0", 1, 0.0 },
        { "offsetOption = ANS_SCPLUT_ZERO_PIVOT", "offsetOption = ans_scplut_scp_offset", 2, 0 },
        { "visualWeighting = true", "visualWeighting = TRUE", 3, 1 }, { "visualWeighting = true", "visualWeighting = yes", 3, 0 },
        { "ntdChoice = ANS_LUT_FIRST_PASS", "ntdChoice = ANS_SECOND_PASS", 4, 2 }, { "ntdChoice = ANS_LUT_FIRST_PASS", "ntdChoice = other", 4, 0 },
        { "modifyDmin = true", "modifyDmin = false", 5, 0 }, { "runSCPAfterLut = true", "runSCPAfterLut = false", 6, 0 },
        { "ctdChoice = ANS_SECOND_PASS", "ctdChoice = ANS_FIRST_PASS", 7, 0 }, { "ctdChoice = ANS_SECOND_PASS", "ctdChoice = ans_lut_first_pass", 7, 1 } };
    int ok = tree_make(), bad = -1, badacc = -1;
    pkc_scplut_params p;
    for (int i = 0; i < (int)(sizeof rej / sizeof *rej) && ok && bad < 0; i++)
        if (!(ok = write_edit(rej[i][0], rej[i][1])) || pkc_scplut_params_load(ROOTD, &p) != PK_E_VENDOR_DATA) bad = i;
    for (int i = 0; i < (int)(sizeof acc / sizeof *acc) && ok && badacc < 0; i++) {
        if (!(ok = write_edit(acc[i].from, acc[i].to)) || pkc_scplut_params_load(ROOTD, &p) != PK_OK) { badacc = i; break; }
        double got = acc[i].field == 0 ? p.thr : acc[i].field == 1 ? p.prop : acc[i].field == 2 ? p.offset_option :
                     acc[i].field == 3 ? p.visual_weighting : acc[i].field == 4 ? p.ntd_choice : acc[i].field == 5 ? p.modify_dmin :
                     acc[i].field == 6 ? p.run_after_lut : p.ctd_choice;
        if (got != acc[i].want) badacc = i;
    }
    tree_free();
    ASSERT(ok);
    ASSERT_EQ_FMT(-1, bad, "%d");      /* index of the first rejected edit that loaded */
    ASSERT_EQ_FMT(-1, badacc, "%d");   /* index of the first accepted edit that failed or read wrong */
    PASS();
}

TEST bad_args(void) {
    pkc_scplut_params p, q; pkc_fos_result f; pkc_lut3 *L = malloc(sizeof *L); ASSERT(L);
    ASSERT_EQ(PK_OK, pkc_scplut_params_load(VENDOR_ROOT, &p));
    memset(&f, 0, sizeof f); f.valid = 1;
    pk_status s[10];
    s[0] = pkc_scplut_build(NULL, &f, L, NULL); s[1] = pkc_scplut_build(&p, NULL, L, NULL); s[2] = pkc_scplut_build(&p, &f, NULL, NULL);
    q = p; q.offset_option = 3; s[3] = pkc_scplut_build(&q, &f, L, NULL);
    q = p; q.visual_weighting = 2; s[4] = pkc_scplut_build(&q, &f, L, NULL);
    q = p; q.prop = 2.5; s[5] = pkc_scplut_build(&q, &f, L, NULL);
    q = p; q.thr = -0.5; s[6] = pkc_scplut_build(&q, &f, L, NULL);
    q = p; q.thr = NAN; s[7] = pkc_scplut_build(&q, &f, L, NULL);
    s[8] = pkc_scplut_params_load(NULL, &q); s[9] = pkc_scplut_params_load(VENDOR_ROOT, NULL);
    free(L);
    for (int i = 0; i < 10; i++) ASSERT_EQ_FMT(PK_E_ARG, s[i], "%d");
    PASS();
}

SUITE(scplut) {
    RUN_TEST(kodak_truth); RUN_TEST(brief_slopes); RUN_TEST(no_fos_identity); RUN_TEST(calc_error);
    RUN_TEST(params_shipped); RUN_TEST(params_variants); RUN_TEST(params_validation); RUN_TEST(bad_args);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(scplut);
    GREATEST_MAIN_END();
}
