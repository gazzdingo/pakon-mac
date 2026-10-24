/* Roll scpLut: core FUN_10287eb0 of PakonIMAu.dll, ported from the disassembly (docs/re/16 section 2) and pinned against
 * Kodak at x87 PC53 (lab/rollbal/truth/t16). Every operation below is in Kodak's order: at PC53 each x87 result rounds to
 * double exactly as these C doubles do (-ffp-contract=off; no value leaves the double exponent range), so registers kept
 * across instructions (R and G, the spread sum, the blue slope) need no explicit store. */
#include "analysis/scplut.h"
#include "analysis/kint.h"
#include "data/kodak_text.h"
#include <math.h>
#include <string.h>

/* .rdata constants (the opponent basis is FUN_1028c4e0's, shared with Preference) */
static const double I3 = 0.5773502717125849;    /* 0x105a6f38 */
static const double I6 = 0.40824829759439285;   /* 0x105a6f30 */
static const double I2 = 0.7071067623730956;    /* 0x105a6f28 */
static const double S23 = 0.8164965951887857;   /* 0x105a6f40 */
static const double SQRT3 = 1.7320508;          /* 0x105a69e0: Kodak's literal, not sqrt(3) */
static const double E4 = 0.0001;                /* 0x105a69e8 */
static const double VW_R = 0.414, VW_B = 0.079, VW_G = 0.507;   /* 0x105a69d8 / 0x105a69d0 / 0x105a69c8 */

/* FUN_1028c4e0: o = basis(a, b, c) */
static void basis(double a, double b, double c, double o[3]) {
    o[0] = (a * I3 - b * I6) - c * I2;
    o[1] = b * S23 + a * I3;
    o[2] = c * I2 + (a * I3 - b * I6);
}

/* 0x104ffe44 (_ftol2, kint.h). The caller stores ax (0x10288218 / 0x1028822d / 0x10288241): only the low 16 bits
 * survive, read back as a signed word. */
static int16_t ftol2_word(double x) { return pkc_sx16(pkc_ftol64(x)); }

pk_status pkc_scplut_build(const pkc_scplut_params *p, const pkc_fos_result *f, pkc_lut3 *out, pkc_scplut_result *res) {
    if (!p || !f || !out) return PK_E_ARG;
    if (f->calc_err) return PK_E_ARG;               /* PIAnselAnalyzeRoll fails before the scpLut (t15d) */
    if (p->offset_option < 0 || p->offset_option > 2 || p->visual_weighting > 1 ||
        !(p->prop >= 0.0 && p->prop <= 2.0) || !(p->thr >= 0.0 && p->thr <= 2.0)) return PK_E_ARG;

    /* analyzeScpLutBalance 0x100fd8d3..0x100fd903: the seven SbaFOSResults words when FOS ran, else zeros; the core
     * reads each with movsx (0x10287ec2...) */
    int16_t gs = 0, go = 0, is = 0, io = 0, dm[3] = { 0, 0, 0 };
    if (f->valid) {
        gs = (int16_t)f->gm_slope; go = (int16_t)f->gm_off; is = (int16_t)f->ill_slope; io = (int16_t)f->ill_off;
        for (int c = 0; c < 3; c++) dm[c] = (int16_t)f->dmin[c];
    }

    /* 0x10287f35..0x10287f8b: v = basis(1, gs * 1e-4, is * 1e-4) * 1.7320508 */
    double o[3];
    basis(1.0, (double)gs * E4, (double)is * E4, o);
    double R = o[0] * SQRT3, G = o[1] * SQRT3, B = o[2] * SQRT3;
    /* 0x10287f8f..0x10287fb1: the spread, B^2 first */
    double q = (((B * B + G * G) + R * R) - G * R - B * R) - B * G;
    double sp = sqrt(q);                            /* fsqrt: NaN for q < 0 (no int16 pair reaches it) */
    /* 0x10287fb7..0x10287fd6: fcomp + test ah,1 -- below or unordered keeps k = 1 */
    double k = 1.0;
    if (sp >= p->thr) k = p->thr / sp;
    /* 0x10287fdf..0x1028805f: limited, then proportional; each stage stored as a double */
    double l[3] = { (R - 1.0) * k + 1.0, (G - 1.0) * k + 1.0, (B - 1.0) * k + 1.0 }, d[3];
    for (int c = 0; c < 3; c++) d[c] = (l[c] - 1.0) * p->prop + 1.0;
    /* 0x10288063..0x1028808b: visualWeighting word == 1 */
    double w = 1.0;
    if (p->visual_weighting == 1) w = 1.0 / ((VW_R * d[0] + d[2] * VW_B) + d[1] * VW_G);
    /* 0x1028808f..0x102880d2 */
    double s[3];
    for (int c = 0; c < 3; c++) s[c] = 1.0 / (d[c] * w);
    /* offsets: 0x102880dc (SCP_OFFSET), 0x10288169 (DMIN_PIVOT), 0x102881bf (ZERO_PIVOT) */
    double off[3] = { 0.0, 0.0, 0.0 };
    if (p->offset_option == 0) {
        double oo[3];
        basis(0.0, (double)go, (double)io, oo);
        off[0] = s[0] * (oo[0] * SQRT3);
        off[1] = s[1] * (oo[1] * SQRT3);
        off[2] = (oo[2] * SQRT3) * s[2];
    } else if (p->offset_option == 1) {
        for (int c = 0; c < 3; c++) off[c] = (s[c] - 1.0) * (double)dm[c];
    }
    /* 0x102881f6..0x102882af: fill, word store, clamp the word to 0..0xfff */
    for (int c = 0; c < 3; c++)
        for (int i = 0; i < 4096; i++) {
            int16_t v = ftol2_word(((double)i * s[c] - off[c]) + 0.5);
            out->t[c][i] = v < 0 ? 0 : v > 0xfff ? 0xfff : v;
        }
    if (res) {
        for (int c = 0; c < 3; c++) { res->slope[c] = s[c]; res->offset[c] = off[c]; }
        res->slope_dist = sp; res->slope_limiter = k; res->visual_gamma = w;
        /* the worker, after the core (0x10212899..0x102128bd, Impl+0xb0): the same spread on the final slopes, which it
         * holds as st0 = blue, st1 = green, st2 = red */
        double qs = (((s[2] * s[2] + s[1] * s[1]) + s[0] * s[0]) - s[1] * s[0] - s[2] * s[0]) - s[2] * s[1];
        res->slope_spread = sqrt(qs);
    }
    return PK_OK;
}

/* ASCII case-insensitive compare (readAscii uses _stricmp) */
static int ieq(const char *a, const char *b) {
    for (; *a && *b; a++, b++) {
        int x = (unsigned char)*a, y = (unsigned char)*b;
        if (x >= 'A' && x <= 'Z') x += 32;
        if (y >= 'A' && y <= 'Z') y += 32;
        if (x != y) return 0;
    }
    return *a == *b;
}

pk_status pkc_scplut_params_load(const char *vendor_root, pkc_scplut_params *out) {
    if (!vendor_root || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    char path[1100];
    pkc_kt *kt = NULL;
    pk_status st = pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/SCPLut/SCPLut-scanner-prod-gen-default-default-default.dpi",
                                   path, sizeof path);
    if (st == PK_OK) st = pkc_kt_load(path, &kt);
    if (st == PK_E_NOMEM) return PK_E_NOMEM;
    if (st != PK_OK) return PK_E_VENDOR_DATA;
    static const char *const BKEY[4] = { "modifyDmin", "useSCPLut", "runSCPAfterLut", "visualWeighting" };
    static const char *const OPT[3] = { "ANS_SCPLUT_SCP_OFFSET", "ANS_SCPLUT_DMIN_PIVOT", "ANS_SCPLUT_ZERO_PIVOT" };
    static const char *const PASS[3] = { "ANS_FIRST_PASS", "ANS_LUT_FIRST_PASS", "ANS_SECOND_PASS" };
    static const char *const PKEY[2] = { "ntdChoice", "ctdChoice" };
    int ok = 1, b[4] = { 0, 0, 0, 0 };
    for (int i = 0; i < 4 && ok; i++) {             /* "true" -> 1, any other token -> 0 (0x101d05e2..0x101d05f7) */
        const char *v = pkc_kt_str(kt, BKEY[i]);
        ok = v != NULL;
        if (ok) b[i] = ieq(v, "true");
    }
    /* offsetOption 0x101d0642..0x101d068f: another token leaves the dpi ctor's value -- not ported, rejected */
    const char *v = ok ? pkc_kt_str(kt, "offsetOption") : NULL;
    int opt = -1;
    for (int i = 0; v && i < 3; i++) if (ieq(v, OPT[i])) opt = i;
    ok = ok && opt >= 0;
    int pass[2] = { 0, 0 };
    for (int j = 0; j < 2 && ok; j++) {             /* an unknown token gives 0 (neg/sbb/and/add at 0x101d082a / 0x101d08c5) */
        v = pkc_kt_str(kt, PKEY[j]);
        ok = v != NULL;
        for (int i = 0; ok && i < 3; i++) if (ieq(v, PASS[i])) pass[j] = i;
    }
    double pr = 0.0, th = 0.0;                      /* %lf, then [0, 2] (0x101d0915..0x101d0931, 0x101d09bb..0x101d09d7) */
    ok = ok && pkc_kt_num(kt, "proportionalCorrection", &pr, 1) == 1 && pkc_kt_num(kt, "slopeDeltaThreshold", &th, 1) == 1;
    pkc_kt_free(kt);
    ok = ok && pr >= 0.0 && pr <= 2.0 && th >= 0.0 && th <= 2.0 && b[1] == 1;
    if (!ok) return PK_E_VENDOR_DATA;
    out->offset_option = (int16_t)opt; out->visual_weighting = (uint8_t)b[3];
    out->modify_dmin = (uint8_t)b[0]; out->run_after_lut = (uint8_t)b[2];
    out->ntd_choice = (int16_t)pass[0]; out->ctd_choice = (int16_t)pass[1];
    out->prop = pr; out->thr = th;
    return PK_OK;
}

/* 0x100d9340's loop (0x100d9822..0x100d986b): one sample of each plane at a time, out_c = lut_c[movsx in_c] */
pk_status pkc_scplut_apply(const pkc_lut3 *lut, const pkc_planes *in, pkc_planes *out) {
    if (!lut || !in || !out || in->w < 1 || in->h < 1) return PK_E_ARG;
    for (int c = 0; c < 3; c++) if (!in->p[c] || !out->p[c]) return PK_E_ARG;
    size_t n = (size_t)in->w * in->h;
    for (int c = 0; c < 3; c++)
        for (size_t i = 0; i < n; i++) {
            int v = in->p[c][i];
            out->p[c][i] = lut->t[c][v < 0 ? 0 : v > 4095 ? 4095 : v];
        }
    out->w = in->w; out->h = in->h;
    return PK_OK;
}
