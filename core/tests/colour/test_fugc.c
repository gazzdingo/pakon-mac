/* Task 17: the FUGC LUT and the context dmin it reads, against Kodak at x87 PC53 (vectors/fugc_truth.pkv,
 * lab/vectors/gen_fugc_truth.py, lab/rollbal/truth/t17). 252 scenes from 38 runs: r4 / r2 / r1 / r12 on both film
 * bases, the Task 12-15 crafted rolls, edited flesh dpis (other shifts), an SCPLut dpi with modifyDmin false (no remap),
 * the Task 17 crafted rolls (context dmin kept below the limit, or exactly at it; every aim-check boundary reached by a
 * real AddScene dmin), an edited seed table (vL.lut: 2-value row, fractional index, negative halves)
 * and 25 crafted operands on t15cap (lab/rollbal/gen_t17poke.py: aim-check bounds, O = 0, +-1, 4095/4096, -4095/-4096,
 * int16 extremes, 16-bit wrap). Per scene the port must reproduce Kodak's whole context chain (both SBA instances'
 * pass-1 write-back and pass-2 min, the remap), dmin', and the 3 x 4096 LUT (FNV-1a 64 of all 24576 bytes; element-wise
 * for r2 frame 0 and the crafted operands). docs/re/22. */
#include "greatest.h"
#include "pkv.h"
#include "analysis/fugc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

static const int32_t *i32(const pkv_array *a) { return (const int32_t *)a->data; }

static uint64_t fnv64(const pkc_lut3 *L) {
    const unsigned char *b = (const unsigned char *)L->t; uint64_t h = 0xcbf29ce484222325ull;
    for (size_t i = 0; i < sizeof L->t; i++) { h ^= b[i]; h *= 0x100000001b3ull; }
    return h;
}

/* column names of gen_fugc_truth.py's COLS, in order */
enum { C_RUN, C_SCENE, C_POKE, C_ADD, C_SP1IN, C_SP1OUT, C_SFOS, C_SFOSD, C_SP2OUT, C_REMAP, C_RIN, C_ROUT, C_AP1IN,
       C_AP1OUT, C_AFOS, C_AFOSD, C_AP2OUT, C_DMIN, C_SHIFT, C_AIM, C_TDMIN, C_OPS, C_SCP, C_LUT, C_MODIFY, C_GRIDS, C_GRIDA,
       C_SEEDID, NCOL_NAMES };

static pkv_file *T;
static const int32_t *COL;
static int16_t SEED[3][PKC_FUGC_N], SEED_VL[3][PKC_FUGC_N];   /* Kodak's seeds: shipped .lut, edited vL.lut */

static void u3(const int32_t *r, int c, uint16_t o[3]) { for (int k = 0; k < 3; k++) o[k] = (uint16_t)r[COL[c] + k]; }
static int eq3u(const uint16_t a[3], const int32_t *r, int c) {
    for (int k = 0; k < 3; k++) if ((int16_t)a[k] != (int16_t)r[COL[c] + k]) return 0;
    return 1;
}

/* one SBA instance: pass-1 write-back from the observed scene dmin, then pass 2 */
static int instance(uint16_t ctx[3], const int32_t *r, int in, int out, int fos, int fosd, int p2out, char *msg, size_t cap) {
    uint16_t scene[3];
    if (!eq3u(ctx, r, in)) { snprintf(msg, cap, "pass-1 input %d %d %d, Kodak %d %d %d", ctx[0], ctx[1], ctx[2], r[COL[in]], r[COL[in] + 1], r[COL[in] + 2]); return 1; }
    u3(r, out, scene);
    if (pkc_ctx_dmin_pass1(ctx, scene) != PK_OK) { snprintf(msg, cap, "pass1 status"); return 1; }
    pkc_fos_result f; memset(&f, 0x5a, sizeof f);
    f.valid = r[COL[fos]]; f.calc_err = 0;
    for (int c = 0; c < 3; c++) f.dmin[c] = r[COL[fosd] + c];
    if (pkc_ctx_dmin_pass2(ctx, scene, &f) != PK_OK) { snprintf(msg, cap, "pass2 status"); return 1; }
    if (!eq3u(scene, r, p2out)) { snprintf(msg, cap, "pass-2 scene dmin %d %d %d", scene[0], scene[1], scene[2]); return 1; }
    return 0;
}

static int check_row(int i, char *msg, size_t cap) {
    const int32_t *r = i32(pkv_get(T, "rows")) + (size_t)i * i32(pkv_get(T, "ncol"))[0];
    uint16_t ctx[3]; u3(r, C_ADD, ctx);
    if (instance(ctx, r, C_SP1IN, C_SP1OUT, C_SFOS, C_SFOSD, C_SP2OUT, msg, cap)) return 1;
    pkc_scplut_params p; memset(&p, 0, sizeof p); p.modify_dmin = (uint8_t)r[COL[C_MODIFY]];
    pkc_lut3 *id = malloc(sizeof *id); if (!id) { snprintf(msg, cap, "oom"); return 1; }
    for (int c = 0; c < 3; c++) for (int k = 0; k < 4096; k++) id->t[c][k] = (int16_t)(4095 - k);   /* must not be read */
    const pkc_lut3 *scp = id;
    if (r[COL[C_REMAP]]) {
        if (!eq3u(ctx, r, C_RIN)) { snprintf(msg, cap, "remap input"); free(id); return 1; }
        scp = (const pkc_lut3 *)((const int16_t *)pkv_get(T, "scps")->data + (size_t)r[COL[C_SCP]] * 3 * 4096);
    }
    pk_status st = pkc_ctx_dmin_remap(ctx, &p, scp);
    free(id);
    if (st != PK_OK) { snprintf(msg, cap, "remap status"); return 1; }
    if (r[COL[C_REMAP]] && !eq3u(ctx, r, C_ROUT)) { snprintf(msg, cap, "remap output %d %d %d", ctx[0], ctx[1], ctx[2]); return 1; }
    if (instance(ctx, r, C_AP1IN, C_AP1OUT, C_AFOS, C_AFOSD, C_AP2OUT, msg, cap)) return 1;
    int poke = r[COL[C_POKE]];
    if (poke != 1 && !eq3u(ctx, r, C_DMIN)) { snprintf(msg, cap, "FUGC dmin %d %d %d, Kodak %d %d %d", ctx[0], ctx[1], ctx[2], r[COL[C_DMIN]], r[COL[C_DMIN] + 1], r[COL[C_DMIN] + 2]); return 1; }
    uint16_t dmin[3]; int16_t aim[3], dp[3], shift[3], td[3];
    u3(r, C_DMIN, dmin);
    for (int c = 0; c < 3; c++) { aim[c] = (int16_t)r[COL[C_AIM] + c]; shift[c] = (int16_t)r[COL[C_SHIFT] + c]; td[c] = (int16_t)r[COL[C_TDMIN] + c]; }
    if (pkc_fugc_dmin_prime(dmin, aim, dp) != PK_OK) { snprintf(msg, cap, "dmin' status"); return 1; }
    const int32_t *ops = r + COL[C_OPS];
    if (poke != 2)
        for (int c = 0; c < 3; c++)
            if (dp[c] != ops[c] || shift[c] != ops[3 + c] || td[c] != ops[6 + c]) { snprintf(msg, cap, "operands ch %d: dmin' %d (Kodak %d)", c, dp[c], ops[c]); return 1; }
    for (int c = 0; c < 3; c++) { dp[c] = (int16_t)ops[c]; shift[c] = (int16_t)ops[3 + c]; td[c] = (int16_t)ops[6 + c]; }
    pkc_lut3 *L = malloc(sizeof *L); if (!L) { snprintf(msg, cap, "oom"); return 1; }
    memset(L, 0x33, sizeof *L);
    int bad = pkc_fugc_lut((const int16_t (*)[PKC_FUGC_N])(r[COL[C_SEEDID]] ? SEED_VL : SEED), dp, td, shift, L) != PK_OK;
    if (bad) snprintf(msg, cap, "lut status");
    int lid = r[COL[C_LUT]];
    if (!bad && lid >= 0) {
        const int16_t *K = (const int16_t *)pkv_get(T, "luts")->data + (size_t)lid * 3 * 4096;
        for (int c = 0; c < 3 && !bad; c++)
            for (int k = 0; k < 4096 && !bad; k++)
                if (L->t[c][k] != K[c * 4096 + k]) { snprintf(msg, cap, "LUT[%d][%d] = %d, Kodak %d", c, k, L->t[c][k], K[c * 4096 + k]); bad = 1; }
    }
    const int32_t *fv = i32(pkv_get(T, "fnv")) + 2 * i;
    uint64_t hk = (uint64_t)(uint32_t)fv[0] | (uint64_t)(uint32_t)fv[1] << 32;
    if (!bad && fnv64(L) != hk) { snprintf(msg, cap, "LUT hash %016llx, Kodak %016llx", (unsigned long long)fnv64(L), (unsigned long long)hk); bad = 1; }
    free(L);
    return bad;
}

TEST seed_and_aim_shipped(void) {
    int16_t (*s)[PKC_FUGC_N] = malloc(3 * sizeof *s), td[3] = { 0, 0, 0 }, aim[3] = { 0, 0, 0 };
    ASSERT(s);
    ASSERT_EQ(PK_OK, pkc_fugc_seed(VENDOR_ROOT, s, td));
    ASSERT_MEM_EQ(SEED, s, sizeof SEED);
    ASSERT(td[0] == 500 && td[1] == 500 && td[2] == 500);
    ASSERT(s[1][3200] == 3199 && s[1][3201] == 3200 && s[1][4095] == 4094);   /* +1 per entry after the last row */
    ASSERT_EQ(PK_OK, pkc_fugc_aim_load(VENDOR_ROOT, aim));
    ASSERT(aim[0] == 500 && aim[1] == 1000 && aim[2] == 1000);
    free(s);
    PASS();
}

TEST kodak_truth(void) {
    int n = i32(pkv_get(T, "n"))[0], npoke = 0, nfb = 0, nvl = 0; char msg[200] = "";
    const int32_t *R = i32(pkv_get(T, "rows")); int nc = i32(pkv_get(T, "ncol"))[0];
    for (int i = 0; i < n; i++) {
        if (check_row(i, msg, sizeof msg)) FAILm((snprintf(msg + strlen(msg), sizeof msg - strlen(msg), " (row %d run %d scene %d)", i, R[i * nc], R[i * nc + 1]), msg));
        npoke += R[i * nc + COL[C_POKE]] != 0;
        nfb += R[i * nc + COL[C_OPS]] == 500 && R[i * nc + COL[C_OPS] + 1] == 1000 && R[i * nc + COL[C_OPS] + 2] == 1000;
        nvl += R[i * nc + COL[C_SEEDID]] == 1;
    }
    ASSERT(n >= 250 && npoke == 25 && nfb >= 10 && nvl == 7);   /* 252 scenes, 16 fallbacks, vL_r1 + vL_r2 */
    PASS();
}

/* the brief's numbers are Kodak's on v1's film base (r4v1, r2v1); Kodak's film base (r4, r2) moves them */
TEST brief_numbers(void) {
    const int32_t *R = i32(pkv_get(T, "rows")); int n = i32(pkv_get(T, "n"))[0], nc = i32(pkv_get(T, "ncol"))[0];
    const int32_t *ix = i32(pkv_get(T, "runs_r2"));      /* run indices of r2, r4, p1 */
    int seen = 0;
    for (int i = 0; i < n; i++) {
        const int32_t *r = R + (size_t)i * nc;
        if (r[0] == ix[0] && r[1] == 0) {             /* r2 frame 0: O < 0 in every channel */
            ASSERT(r[COL[C_DMIN]] == 535 && r[COL[C_DMIN] + 1] == 639 && r[COL[C_DMIN] + 2] == 701);
            ASSERT(r[COL[C_ROUT] + 2] == 731);         /* scpLut(dmin) would be 731: the afterSCPLut pass-2 min wins */
            ASSERT(r[COL[C_SHIFT]] == -208 && r[COL[C_SHIFT] + 1] == -346 && r[COL[C_SHIFT] + 2] == -298);
            ASSERT(r[COL[C_LUT]] >= 0);                /* stored in full: compared element-wise by kodak_truth */
            int16_t dp[3] = { 535, 639, 701 }, td[3] = { 500, 500, 500 }, sh[3] = { -208, -346, -298 };
            pkc_lut3 *L = malloc(sizeof *L); ASSERT(L);
            ASSERT_EQ(PK_OK, pkc_fugc_lut((const int16_t (*)[PKC_FUGC_N])SEED, dp, td, sh, L));
            /* G: O = -207. Highlights below the identity tail are seed + O = i - 1 (RE 18's one-code residue: the
             * reference's seed was the identity above row 3200), the top 207 codes are the identity. */
            ASSERT_EQ(3400 - 1, L->t[1][3400]); ASSERT_EQ(4095 - 207 - 1, L->t[1][4095 - 207]); ASSERT_EQ(3889, L->t[1][3889]);
            ASSERT_EQ(4095, L->t[1][4095]); ASSERT_EQ(0, L->t[1][0]);
            free(L); seen++;
        }
        if (r[0] == ix[1] && r[1] == 0) {             /* r4 (Kodak film base); r4v1 gives the brief's 335/787/940 */
            ASSERT(r[COL[C_DMIN]] == 328 && r[COL[C_DMIN] + 1] == 781 && r[COL[C_DMIN] + 2] == 940); seen++;
        }
    }
    ASSERT_EQ(2, seen);
    PASS();
}

/* ---- loader edge cases on a temp vendor tree ---- */
static char TMP[256];
static void put(const char *rel, const char *text) {
    char p[512]; snprintf(p, sizeof p, "%s/anselinstalldir/dataPathItems/fugc/%s", TMP, rel);
    FILE *f = fopen(p, "wb"); if (f) { fputs(text, f); fclose(f); }
}
static void mkdirs(void) {
    snprintf(TMP, sizeof TMP, "/tmp/pk_fugc_%d", (int)getpid());
    char p[512];
    const char *d[] = { "", "/anselinstalldir", "/anselinstalldir/dataPathItems", "/anselinstalldir/dataPathItems/fugc" };
    for (int i = 0; i < 4; i++) { snprintf(p, sizeof p, "%s%s", TMP, d[i]); mkdir(p, 0700); }
}
static const char *MAP = "film =   X   X   X   2.25\ncontrast =  1.00  a.lut\ncontrast =  2.25  t.lut\n";
static pk_status load_text(const char *lut, int16_t (*s)[PKC_FUGC_N], int16_t td[3]) {
    put("fugc-rgb-lutMap.map", MAP); put("t.lut", lut);
    return pkc_fugc_seed(TMP, s, td);
}

TEST seed_rules(void) {
    mkdirs();
    int16_t (*s)[PKC_FUGC_N] = malloc(3 * sizeof *s), td[3];
    ASSERT(s);
    /* 2-value rows (R = G = B), rounding trunc(x + 0.5), continuation +1, clamp of negatives and > 4095 */
    ASSERT_EQ(PK_OK, load_text("# c\nkey = t.lut\nversion = 1\naTableDmin = 400 450 -3\r\n\t0 -5 7 4100\n1 2.5\n2 3.49 1.5 -0.4\n", s, td));
    ASSERT(td[0] == 400 && td[1] == 450 && td[2] == -3);
    ASSERT(s[0][0] == 0 && s[1][0] == 7 && s[2][0] == 4095);
    ASSERT(s[0][1] == 3 && s[1][1] == 3 && s[2][1] == 3);
    ASSERT(s[0][2] == 3 && s[1][2] == 2 && s[2][2] == 0);
    ASSERT(s[0][3] == 4 && s[1][3] == 3 && s[2][3] == 1 && s[0][4095] == 4095 && s[1][4095] == 4095 && s[2][4095] == 4093);
    /* errors */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\n0 1 2 3\n", s, td));                       /* no aTableDmin */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\naTableDmin = 1 2\n0 1 2 3\n", s, td));     /* 2 numbers */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = x.lut\naTableDmin = 1 2 3\n0 1 2 3\n", s, td));   /* key != file */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\naTableDmin = 1 2 3\n", s, td));           /* no rows */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\naTableDmin = 1 2 3\n0 1 2 3\n2 1 2 3\n", s, td));   /* index gap */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\naTableDmin = 1 2 3\n0 1 2\n", s, td));     /* 3 numbers */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\naTableDmin = 1 2 3\n0 1 2 3\n  \n", s, td));   /* blank line */
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\naTableDmin = 1 2 3\n0 1 2 3\nfoo = 1\n", s, td));
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key = t.lut\nfoo = 1\naTableDmin = 1 2 3\n0 1 2 3\n", s, td));
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text("key=t.lut\naTableDmin = 1 2 3\n0 1 2 3\n", s, td));
    char *big = malloc(4097 * 24 + 64); ASSERT(big);
    int o = sprintf(big, "key = t.lut\naTableDmin = 1 2 3\n");
    for (int i = 0; i < 4097; i++) o += sprintf(big + o, "%d %d %d %d\n", i, i, i, i);
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text(big, s, td));                                       /* 4097 rows */
    big[o - (int)strlen("4096 4096 4096 4096\n")] = 0;
    ASSERT_EQ(PK_OK, load_text(big, s, td));                                                  /* exactly 4096 */
    char longl[300]; memset(longl, ' ', sizeof longl); longl[299] = 0; memcpy(longl + 290, "0 1 2 3\n", 8); longl[298] = 0;
    snprintf(big, 4097 * 24, "key = t.lut\naTableDmin = 1 2 3\n%s", longl);
    ASSERT_EQ(PK_E_VENDOR_DATA, load_text(big, s, td));                                       /* line > 255 */
    free(big);
    /* map selection: no wildcard film row; contrast without a lut row; another contrast */
    put("t.lut", "key = t.lut\naTableDmin = 1 2 3\n0 1 2 3\n"); put("a.lut", "key = a.lut\naTableDmin = 7 8 9\n0 1\n");
    put("fugc-rgb-lutMap.map", "film = X X 400 2.25\n"); ASSERT_EQ(PK_E_VENDOR_DATA, pkc_fugc_seed(TMP, s, td));
    put("fugc-rgb-lutMap.map", "film = X X X 3.5\ncontrast = 2.25 t.lut\n"); ASSERT_EQ(PK_E_VENDOR_DATA, pkc_fugc_seed(TMP, s, td));
    put("fugc-rgb-lutMap.map", "film = X X X 1.0\ncontrast = 2.25 t.lut\ncontrast = 1.00 a.lut\n");
    ASSERT_EQ(PK_OK, pkc_fugc_seed(TMP, s, td)); ASSERT(td[0] == 7 && s[2][0] == 1 && s[2][1] == 2);
    /* aim */
    int16_t aim[3];
    put("fugc-defaultParams.dpi", "aFilmAimDmin = 500 1000 1000\n"); ASSERT_EQ(PK_OK, pkc_fugc_aim_load(TMP, aim));
    put("fugc-defaultParams.dpi", "aFilmAimDmin = 500 1000\n"); ASSERT_EQ(PK_E_VENDOR_DATA, pkc_fugc_aim_load(TMP, aim));
    put("fugc-defaultParams.dpi", "aFilmAimDmin = 500 1000 40000\n"); ASSERT_EQ(PK_E_VENDOR_DATA, pkc_fugc_aim_load(TMP, aim));
    put("fugc-defaultParams.dpi", "mode = RGB\n"); ASSERT_EQ(PK_E_VENDOR_DATA, pkc_fugc_aim_load(TMP, aim));
    free(s);
    char cmd[300]; snprintf(cmd, sizeof cmd, "rm -rf '%s'", TMP); ASSERT_EQ(0, system(cmd));
    PASS();
}

/* Kodak's own seed from an edited .lut (vL: a 2-value row, a fractional index, a last row -2.5 -0.5 2.5 whose
 * trunc(x + 0.5) -- not round-half-away -- feeds the +1 continuation), read by the port from the same bytes. */
TEST seed_edited_kodak(void) {
    mkdirs();
    const pkv_array *b = pkv_get(T, "lut_vL"); ASSERT(b);
    char p[512]; snprintf(p, sizeof p, "%s/anselinstalldir/dataPathItems/fugc/NoShift_fugc-generic0225.lut", TMP);
    FILE *f = fopen(p, "wb"); ASSERT(f); ASSERT_EQ(b->n, fwrite(b->data, 1, b->n, f)); fclose(f);
    put("fugc-rgb-lutMap.map", "film = X X X 2.25\ncontrast = 2.25 NoShift_fugc-generic0225.lut\n");
    int16_t (*s)[PKC_FUGC_N] = malloc(3 * sizeof *s), td[3]; ASSERT(s);
    ASSERT_EQ(PK_OK, pkc_fugc_seed(TMP, s, td));
    ASSERT_MEM_EQ(SEED_VL, s, sizeof SEED_VL);
    ASSERT(s[0][3203] == 1 && s[1][3201] == 1);       /* round-half-away would give 0 and 0 */
    free(s);
    char cmd[300]; snprintf(cmd, sizeof cmd, "rm -rf '%s'", TMP); ASSERT_EQ(0, system(cmd));
    PASS();
}

/* pure rules the truth pins, restated: the write-back needs a strictly lower grid value; ties and NULL FOS */
TEST ctx_rules(void) {
    uint16_t ctx[3] = { 525, 653, 647 }, scene[3] = { 525, 653, 4095 };
    ASSERT_EQ(PK_OK, pkc_ctx_dmin_pass1(ctx, scene)); ASSERT(ctx[2] == 647);              /* 4095 alone: kept */
    scene[2] = 701; ASSERT_EQ(PK_OK, pkc_ctx_dmin_pass1(ctx, scene)); ASSERT(ctx[2] == 701);
    uint16_t c2[3] = { 1, 2, 3 }, s2[3] = { 10, 20, 30 };
    ASSERT_EQ(PK_OK, pkc_ctx_dmin_pass2(c2, s2, NULL)); ASSERT(c2[0] == 1 && s2[0] == 10);
    pkc_fos_result f; memset(&f, 0, sizeof f); f.valid = 1; f.dmin[0] = 11; f.dmin[1] = 21; f.dmin[2] = 30;   /* tie on B */
    ASSERT_EQ(PK_OK, pkc_ctx_dmin_pass2(c2, s2, &f)); ASSERT(c2[0] == 10 && c2[1] == 20 && c2[2] == 30);
    f.valid = 0; f.dmin[2] = 0; ASSERT_EQ(PK_OK, pkc_ctx_dmin_pass2(c2, s2, &f)); ASSERT(s2[2] == 30);
    PASS();
}

/* Branches the shipped seed cannot reach (its entries satisfy seed[j] <= j, so seed[i - O] + O < 4096): Kodak's high
 * clamp (0x101f83a5..0x101f83ad, from the disassembly) on a synthetic seed; and the port's remap-index clamp (Kodak
 * indexes unchecked; the global LUT-input rule) -- neither is reachable from 12-bit data. */
TEST unreachable_edges(void) {
    static int16_t s[3][PKC_FUGC_N]; pkc_lut3 *L = malloc(sizeof *L); ASSERT(L);
    for (int c = 0; c < 3; c++) for (int i = 0; i < PKC_FUGC_N; i++) s[c][i] = 4095;
    int16_t dp[3] = { 510, 500, 500 }, td[3] = { 500, 500, 500 }, sh[3] = { 0, 0, 0 };
    ASSERT_EQ(PK_OK, pkc_fugc_lut((const int16_t (*)[PKC_FUGC_N])s, dp, td, sh, L));
    ASSERT_EQ(10, L->t[0][9]); ASSERT_EQ(4095, L->t[0][10]); ASSERT_EQ(4095, L->t[0][4095]); ASSERT_EQ(4095, L->t[1][0]);
    /* the 16-bit add (add cx, bx; jns): seed 32767 + O = 1 wraps to -32768 -> 0 */
    for (int i = 0; i < PKC_FUGC_N; i++) s[2][i] = 32767;
    int16_t dp2[3] = { 501, 501, 501 };
    ASSERT_EQ(PK_OK, pkc_fugc_lut((const int16_t (*)[PKC_FUGC_N])s, dp2, td, sh, L));
    ASSERT_EQ(1, L->t[2][0]); ASSERT_EQ(0, L->t[2][1]); ASSERT_EQ(0, L->t[2][4095]); ASSERT_EQ(4095, L->t[0][1]);
    for (int c = 0; c < 3; c++) for (int i = 0; i < PKC_FUGC_N; i++) L->t[c][i] = (int16_t)(i + 1);
    pkc_scplut_params p; memset(&p, 0, sizeof p); p.modify_dmin = 1;
    uint16_t ctx[3] = { 5000, 0xfffd, 7 };
    ASSERT_EQ(PK_OK, pkc_ctx_dmin_remap(ctx, &p, L));
    ASSERT(ctx[0] == 4096 && ctx[1] == 1 && ctx[2] == 8);
    p.modify_dmin = 0; ASSERT_EQ(PK_OK, pkc_ctx_dmin_remap(ctx, &p, L)); ASSERT(ctx[2] == 8);
    free(L);
    PASS();
}

TEST bad_args(void) {
    int16_t x[3] = { 0 }, (*s)[PKC_FUGC_N] = SEED; uint16_t u[3] = { 0 }; pkc_lut3 L; pkc_scplut_params p; memset(&p, 0, sizeof p);
    ASSERT_EQ(PK_E_ARG, pkc_fugc_seed(NULL, s, x)); ASSERT_EQ(PK_E_ARG, pkc_fugc_seed(VENDOR_ROOT, NULL, x));
    ASSERT_EQ(PK_E_ARG, pkc_fugc_seed(VENDOR_ROOT, s, NULL)); ASSERT_EQ(PK_E_ARG, pkc_fugc_aim_load(VENDOR_ROOT, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_ctx_dmin_pass1(NULL, u)); ASSERT_EQ(PK_E_ARG, pkc_ctx_dmin_pass2(u, NULL, NULL));
    ASSERT_EQ(PK_E_ARG, pkc_ctx_dmin_remap(u, &p, NULL)); ASSERT_EQ(PK_E_ARG, pkc_fugc_dmin_prime(u, NULL, x));
    ASSERT_EQ(PK_E_ARG, pkc_fugc_lut((const int16_t (*)[PKC_FUGC_N])SEED, x, x, NULL, &L));
    ASSERT_EQ(PK_E_ARG, pkc_fugc_lut(NULL, x, x, x, &L));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_fugc_seed("/nonexistent", s, x));
    PASS();
}

SUITE(fugc) {
    RUN_TEST(seed_and_aim_shipped); RUN_TEST(kodak_truth); RUN_TEST(brief_numbers); RUN_TEST(seed_rules);
    RUN_TEST(seed_edited_kodak); RUN_TEST(ctx_rules); RUN_TEST(unreachable_edges); RUN_TEST(bad_args);
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    T = pkv_open(PKV_DIR "/fugc_truth.pkv");
    if (!T) { fprintf(stderr, "no fugc_truth.pkv\n"); return 1; }
    COL = i32(pkv_get(T, "cols"));
    memcpy(SEED, pkv_get(T, "seed")->data, sizeof SEED);
    memcpy(SEED_VL, pkv_get(T, "seed_vL")->data, sizeof SEED_VL);
    GREATEST_MAIN_BEGIN();
    RUN_SUITE(fugc);
    pkv_close(T);
    GREATEST_MAIN_END();
}
