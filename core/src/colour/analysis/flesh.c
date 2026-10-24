/* The flesh correction, fcn.10270280 of PakonIMAu.dll (MD5 eea9dcf78ee21d4f7c515a6c2512242d) on the colour-negative path
 * (useAdvanced = 0, oneDTable = 1, useSmallAnalysisImage = 0, arg3 = arg4, arg8 = 1), with the weight map fcn.10271bc0
 * and the pad fcn.104e7880 its caller AnsFleshCapabilityImpl::analyze (0x101c92c0) runs first. Ported from the
 * disassembly with lab/reference/pakon_flesh.py (Unicorn-verified stage by stage) as the lead, and pinned against Kodak
 * at x87 PC53 (lab/rollbal/truth/t14; docs/re/16 section 8). The arithmetic x87 operations (fadd/fsub/fmul/fdiv/fsqrt)
 * are C double operations in Kodak's order (PC53: each result rounds to double; -ffp-contract=off); float32 stores are
 * explicit. The two operations the precision control does not govern are modelled explicitly in the weight map's
 * exponential: fldl2e's 64-bit constant (rounded product, exact) and f2xm1's 64-bit result (assumed correctly rounded;
 * see pkc_flesh_exp1000). */
#include "analysis/flesh.h"
#include "analysis/kint.h"
#include "data/kodak_text.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef __SIZEOF_INT128__
#error "flesh.c needs unsigned __int128 (ruling R25: the library targets 64-bit macOS, arm64 and x86_64 clang)"
#endif
typedef unsigned __int128 u128;

/* .rdata (verified by value against the DLL) */
static const double INV_1732 = 0.57736720554272514;    /* 0x105a4c90 = 0x3fe279caca32d863: a typed-in 1/1.732 */
static const double ONE_THIRD = 1.0 / 3.0;             /* 0x105943c0 = 0x3fd5555555555555 */
static const double INV_130 = 1.0 / 130.0;             /* 0x105a4c88 = 0x3f7f81f81f81f820 (results +0x18 only) */
static const double INV_255 = 1.0 / 255.0;             /* 0x105a1778 = 0x3f70101010101010 (results +0x20 only) */
static const double PROB_FLOOR = 0.001;                /* 0x1059db90 = 0x3f50624dd2f1a9fc */
static const double PROB_SCALE = 255.0;                /* 0x10575690 */
static const double W_LOG = -8.0;                      /* 0x10596dc0 */
static const double W_HALF = -0.5;                     /* 0x1057ae70 */
static const double W_PEAK = 1000.0;                   /* 0x105a3c18 */
#define EDGE_MIN 400            /* 0x1029c2c0: |Sobel| >= 0x190 -> 255 */
#define HIST_BINS 64            /* fcn.1029ec50: malloc(0x100) floats */
#define SMOOTH_HALF 7           /* 0x1029f4f0: the window [i - 7, i + 7] */
#define BIN_NONE 64             /* 0x1029f558: no valley found -> threshold 256 */

static int values_ok(const pkc_flesh_params *p);

/* ---- loading ---- */

/* a decimal integer token (%ld / %hd / %d) */
static int read_int(const pkc_kt *kt, const char *key, long lo, long hi, long *out) {
    const char *v = pkc_kt_str(kt, key);
    if (!v || !*v) return 0;
    char *end; long x = strtol(v, &end, 10);
    if (*end || x < lo || x > hi) return 0;
    *out = x;
    return 1;
}
static int read_dbl(const pkc_kt *kt, const char *key, double *out) {
    double x;
    if (pkc_kt_num(kt, key, &x, 1) != 1 || !isfinite(x)) return 0;
    *out = x;
    return 1;
}

/* a condProbTbl file: "size = 32", "vals =" and 32 numbers */
static pk_status read_table(const char *dir, const char *name, double out[PKC_FLESH_BINS]) {
    char path[1200];
    if (strchr(name, '/') || strchr(name, '\\') || snprintf(path, sizeof path, "%s/%s", dir, name) >= (int)sizeof path)
        return PK_E_VENDOR_DATA;
    pkc_kt *kt = NULL;
    pk_status st = pkc_kt_load(path, &kt);
    if (st != PK_OK) return st == PK_E_NOMEM ? st : PK_E_VENDOR_DATA;
    double size = 0.0, v[PKC_FLESH_BINS + 1];
    int ok = pkc_kt_num(kt, "size", &size, 1) == 1 && size == PKC_FLESH_BINS &&
             pkc_kt_num(kt, "vals", v, PKC_FLESH_BINS + 1) == PKC_FLESH_BINS;
    pkc_kt_free(kt);
    for (int i = 0; ok && i < PKC_FLESH_BINS; i++) ok = isfinite(v[i]);
    if (!ok) return PK_E_VENDOR_DATA;
    memcpy(out, v, PKC_FLESH_BINS * sizeof *out);
    return PK_OK;
}

pk_status pkc_flesh_params_read(const char *dpi_path, const char *tables_dir, pkc_flesh_params *out) {
    if (!out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    if (!dpi_path || !tables_dir) return PK_E_ARG;
    pkc_kt *kt = NULL;
    pk_status st = pkc_kt_load(dpi_path, &kt);
    if (st != PK_OK) return st == PK_E_NOMEM ? st : PK_E_VENDOR_DATA;
    pkc_flesh_params p; memset(&p, 0, sizeof p);
    long iv[10];
    /* fcn.10272380's formats: %lf for the doubles, %hd loff/soff/toff, %ld useAdvanced/stOnly/oneDTable, an int stored as
     * (v != 0) for tSpace / writeIntermediateImages / useSmallAnalysisImage / darkenOnly */
    int ok = read_dbl(kt, "axialProb", &p.axial_prob) && read_dbl(kt, "clipAmount", &p.clip_amount) &&
             read_int(kt, "loff", -32768, 32767, &iv[0]) && read_int(kt, "soff", -32768, 32767, &iv[1]) &&
             read_int(kt, "toff", -32768, 32767, &iv[2]) &&
             read_dbl(kt, "lscale", &p.lscale) && read_dbl(kt, "sscale", &p.sscale) && read_dbl(kt, "tscale", &p.tscale) &&
             read_int(kt, "useAdvanced", INT32_MIN, INT32_MAX, &iv[3]) &&
             read_dbl(kt, "growThreshold", &p.grow_threshold) && read_dbl(kt, "regionThreshold", &p.region_threshold) &&
             read_int(kt, "stOnly", INT32_MIN, INT32_MAX, &iv[4]) && read_int(kt, "tSpace", INT32_MIN, INT32_MAX, &iv[5]) &&
             read_int(kt, "oneDTable", INT32_MIN, INT32_MAX, &iv[6]) &&
             read_dbl(kt, "beta", &p.beta) && read_dbl(kt, "frontLitBeta", &p.front_lit_beta) &&
             read_dbl(kt, "backLitBeta", &p.back_lit_beta) && read_dbl(kt, "fleshPrefAdj", &p.flesh_pref_adj) &&
             read_dbl(kt, "fleshNeutralAim", &p.flesh_neutral_aim) && read_dbl(kt, "fleshCountThresh", &p.flesh_count_thresh) &&
             read_dbl(kt, "percentFleshAdj", &p.percent_flesh_adj) && read_dbl(kt, "exposureLimit", &p.exposure_limit) &&
             read_int(kt, "writeIntermediateImages", INT32_MIN, INT32_MAX, &iv[7]) &&
             read_int(kt, "useSmallAnalysisImage", INT32_MIN, INT32_MAX, &iv[8]) &&
             read_int(kt, "darkenOnly", INT32_MIN, INT32_MAX, &iv[9]);
    const char *key[3] = { NULL, NULL, NULL };
    if (ok) { key[0] = pkc_kt_str(kt, "lCondProbKey"); key[1] = pkc_kt_str(kt, "sCondProbKey"); key[2] = pkc_kt_str(kt, "tCondProbKey"); }
    ok = ok && key[0] && key[1] && key[2];
    char kc[3][256];
    for (int i = 0; ok && i < 3; i++) ok = snprintf(kc[i], sizeof kc[i], "%s", key[i]) < (int)sizeof kc[i];
    pkc_kt_free(kt);
    if (!ok) return PK_E_VENDOR_DATA;
    p.loff = (int16_t)iv[0]; p.soff = (int16_t)iv[1]; p.toff = (int16_t)iv[2];
    p.use_advanced = (int32_t)iv[3]; p.st_only = (int32_t)iv[4]; p.t_space = iv[5] != 0; p.one_d_table = (int32_t)iv[6];
    p.write_intermediate_images = iv[7] != 0; p.use_small_analysis_image = iv[8] != 0; p.darken_only = iv[9] != 0;
    /* AnsFleshDPI::readAscii, after the parameter reader: frontLitBeta = backLitBeta = beta (0x101ce26c..0x101ce285), so
     * the dpi's own frontLitBeta / backLitBeta values never reach the calculator (observed: edited dpis vF, vT..vW) */
    p.front_lit_beta = p.beta; p.back_lit_beta = p.beta;
    double *tab[3] = { p.cond_l, p.cond_s, p.cond_t };
    for (int i = 0; i < 3; i++) if ((st = read_table(tables_dir, kc[i], tab[i])) != PK_OK) return st;
    /* the weight map needs 0 < axialProb < 1: <= 0 fails it (0x10271d1d, status 0xffff), 1 gives sigma 0 (0x10271d63,
     * 0xfffe), above 1 a NaN sigma. clipAmount outside [0, 1) and scales <= 0 or below about 2.1e-5 make Kodak read and
     * write outside its images (values_ok): refused rather than modelled. */
    if (!values_ok(&p)) return PK_E_VENDOR_DATA;
    if (p.use_advanced || !p.one_d_table || p.use_small_analysis_image) return PK_E_UNSUPPORTED;
    *out = p;
    return PK_OK;
}

pk_status pkc_flesh_params_load(const char *vendor_root, pkc_flesh_params *out) {
    if (!out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    if (!vendor_root) return PK_E_ARG;
    char dpi[1100], dir[1100];
    if (pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/flesh/FleshDPI/flesh-srcType-metric-default-default.dpi",
                        dpi, sizeof dpi) != PK_OK ||
        pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/flesh/CondProbTables", dir, sizeof dir) != PK_OK)
        return PK_E_VENDOR_DATA;
    return pkc_flesh_params_read(dpi, dir, out);
}

/* ---- Kodak's integer idioms (kint.h) ---- */

static int32_t ftol32(double x) { return pkc_wrap32(pkc_ftol64(x)); }     /* _ftol, eax kept */
/* cdq; sub eax, edx; sar eax, 1: halve toward zero */
static int32_t half0(int32_t v) { return (v - (v >> 31)) >> 1; }
/* 0x10270712..0x1027075f and 0x10271c11..0x10271c4e: _ftol(dim * clipAmount), halved toward zero, minus 1 unless 0 */
static int32_t border(int32_t dim, double clip) {
    int32_t b = half0(ftol32((double)dim * clip));
    return b ? b - 1 : b;
}
/* the largest |v| an axis index divides: L <= 3 * 4095, |S| <= 4095, |T| <= 8190 (the planes are clamped to 0..4095)
 * minus an offset >= -32768 */
#define AXIS_VMAX 45053.0
/* values the port can compute without leaving its buffers (Kodak has no such check: it reads / writes outside its
 * images for them): 0 <= clipAmount < 1 (both borders >= 0, 1 - clip > 0), 0 < axialProb < 1, and float32 scales > 0
 * whose quotient can never reach 2^31 (an index read as a negative eax) */
static int scale_ok(double s) {
    float f = (float)s;
    return f > 0.0f && AXIS_VMAX / (double)f < 2147483648.0;
}
static int values_ok(const pkc_flesh_params *p) {
    return p->clip_amount >= 0.0 && p->clip_amount < 1.0 && p->axial_prob > 0.0 && p->axial_prob < 1.0 &&
           scale_ok(p->lscale) && scale_ok(p->sscale) && scale_ok(p->tscale);
}
static int params_ok(const pkc_flesh_params *p) {
    return !p->use_advanced && p->one_d_table && !p->use_small_analysis_image && values_ok(p);
}

/* ---- the weight plane: fcn.10271bc0 + fcn.104e7880 ---- */

/* x87 fldl2e: log2(e) rounded to 64 bits = 0xb8aa3b295c17f0bc * 2^-63 (constant loads ignore the precision control);
 * fmulp at PC53 rounds the exact product of a double and this constant once, to 53 bits. */
static double mul_l2e(double v) {
    if (v == 0.0 || !isfinite(v)) return v * 1.4426950408889634;
    int e;
    double m = frexp(fabs(v), &e);                          /* |v| = m 2^e, m in [0.5, 1) */
    uint64_t mv = (uint64_t)ldexp(m, 53);                   /* 53-bit integer, |v| = mv 2^(e - 53) */
    u128 pr = (u128)mv * 0xb8aa3b295c17f0bcull;   /* |v| l2e = pr 2^(e - 53 - 63) */
    int bits = 0;
    for (u128 t = pr; t; t >>= 1) bits++;
    int sh = bits - 53;                                      /* keep 53 bits, round half even */
    u128 q = pr >> sh, rem = pr - (q << sh), half = (u128)1 << (sh - 1);
    if (rem > half || (rem == half && (q & 1))) q++;
    double r = ldexp((double)(uint64_t)q, e - 53 - 63 + sh);
    return v < 0.0 ? -r : r;
}

/* ---- the x87 exponential of the weight map (0x10271e1c..0x10271e3c) at PC53 ----
 *   fldl2e; fmulp       t = round53(z * log2(e)_64)        the constant is loaded to 64 bits; the product rounds once
 *   fld st0; frndint    n = round-to-nearest-even(t)
 *   fxch; fsub st1      f = t - n                          exact, |f| <= 0.5
 *   f2xm1               u = 2^f - 1 to 64 bits             transcendental results ignore the precision control
 *   fld1; faddp         v = round53(1 + u)
 *   fscale; fstp st1    V = v * 2^n                        exact
 *   fmul 1000.0         P = round53(V * 1000)
 * Modelled with f2xm1 correctly rounded to 64 bits (round to nearest even): u is evaluated in double-double (error
 * below 2^-98 relative) and rounded with integers; a value whose rounding the double-double cannot decide (within 2^-95
 * of a 64-bit half-way point; never met on any reachable shipped-dpi pixel, lab/flesh/expsweep.c) keeps the
 * double-double's rounding and reports it. Real f2xm1 implementations are accurate to about 1 ulp of 64 bits, not
 * correctly rounded (measured on Rosetta's x87, lab/flesh/rosetta_f2xm1/chk.py: 1.0 % of 24 000 inputs are off by exactly
 * one 64-bit ulp from the correctly rounded value, 0 of them change round53(1 + u)); v is sensitive to that only when 1 + u lies within one 64-bit ulp of a 53-bit half-way point
 * (docs/re/16 section 8: the measured bound). */
typedef struct { double hi, lo; } dd;
static dd quick2(double a, double b) { double s = a + b; dd r = { s, b - (s - a) }; return r; }
static dd two_sum(double a, double b) {
    double s = a + b, bb = s - a; dd r = { s, (a - (s - bb)) + (b - bb) }; return r;
}
static dd dd_add(dd a, dd b) {
    dd s = two_sum(a.hi, b.hi), t = two_sum(a.lo, b.lo);
    s.lo += t.hi; s = quick2(s.hi, s.lo); s.lo += t.lo;
    return quick2(s.hi, s.lo);
}
static dd dd_mul(dd a, dd b) {
    double p = a.hi * b.hi, e = fma(a.hi, b.hi, -p);
    e += a.hi * b.lo + a.lo * b.hi;
    return quick2(p, e);
}
static dd dd_div_d(dd a, double d) {
    double q1 = a.hi / d, p1 = q1 * d, p2 = fma(q1, d, -p1);
    dd s = two_sum(a.hi, -p1);
    s.lo -= p2; s.lo += a.lo;
    double q2 = (s.hi + s.lo) / d;
    return quick2(q1, q2);
}
static int bits128(u128 v) { int b = 0; while (v) { v >>= 1; b++; } return b; }
/* round v (> 0) to `keep` significant bits, half to even; returns the kept integer, *sh = bits dropped */
static u128 round_bits(u128 v, int keep, int *sh, u128 *rem_out, u128 *half_out) {
    int s = bits128(v) - keep;
    if (s <= 0) { *sh = 0; if (rem_out) *rem_out = 0; if (half_out) *half_out = 1; return v; }
    u128 q = v >> s, rem = v - (q << s), half = (u128)1 << (s - 1);
    if (rem_out) *rem_out = rem;
    if (half_out) *half_out = half;
    if (rem > half || (rem == half && (q & 1))) q++;
    if (bits128(q) > keep) { q >>= 1; s++; }     /* carried into a new bit: the dropped bit is 0 */
    *sh = s;
    return q;
}

/* f2xm1(f), |f| <= 0.5: u = sgn * m * 2^q with m < 2^64; returns 0 when u is exactly 0. *decided as above. */
static int f2xm1_64(double f, int *sgn, uint64_t *m, int *q, int *decided) {
    *decided = 1;
    if (f == 0.0) return 0;
    static const double LN2_HI = 0x1.62e42fefa39efp-1, LN2_LO = 0x1.abc9e3b39803fp-56, LN2_LO2 = 0x1.7b57a079a1934p-111;
    double p = f * LN2_HI, e = fma(f, LN2_HI, -p);
    dd x = quick2(p, e + (f * LN2_LO + f * LN2_LO2));
    /* expm1(x) = x (1 + x/2 (1 + x/3 (... (1 + x/24)))) , |x| <= 0.35: the last term is below 2^-110 */
    dd r = { 1.0, 0.0 }, one = { 1.0, 0.0 };
    for (int k = 24; k >= 2; k--) r = dd_add(one, dd_div_d(dd_mul(x, r), (double)k));
    dd u = dd_mul(x, r);
    u = quick2(u.hi, u.lo);
    if (u.hi == 0.0) return 0;
    *sgn = u.hi < 0.0 ? -1 : 1;
    double H = fabs(u.hi), L = u.hi < 0.0 ? -u.lo : u.lo;
    int eh = ilogb(H);                               /* H in [2^eh, 2^(eh+1)) */
    /* exact integer sum at weight 2^(eh - 112): H's lsb is 2^(eh - 52), |L| <= 2^(eh - 53) with lsb >= 2^(eh - 105) */
    __int128 S = (__int128)ldexp(H, 112 - eh);
    S += (__int128)ldexp(L, 112 - eh);
    u128 rem, half; int sh;
    u128 qv = round_bits((u128)S, 64, &sh, &rem, &half);
    u128 dist = rem > half ? rem - half : half - rem;
    if (dist <= ((u128)1 << 17)) *decided = 0;       /* within 2^-95 relative of the half-way point */
    *m = (uint64_t)qv; *q = eh - 112 + sh;
    return 1;
}

/* v = round53(1 + u) */
static double one_plus(int sgn, uint64_t m, int q) {
    if (q + 64 <= -60) return 1.0;                   /* |u| < 2^-60: 1 + u rounds to 1 either side */
    /* fixed point, lsb 2^-126: 1 + u < 1.42 fits below 2^127 */
    __int128 T = (__int128)1 << 126, U = (__int128)m;
    int s = q + 126;                                 /* >= 2 here */
    U <<= s;
    T = sgn < 0 ? T - U : T + U;
    int sh;
    u128 r = round_bits((u128)T, 53, &sh, NULL, NULL);
    return ldexp((double)(uint64_t)r, sh - 126);
}

/* z below about -708 (V < 2^-1022): P is a double denormal or 0 here and an extended-range value at Kodak (fscale is exact, the
 * range is 15 bits); both truncate to a weight of 0 after the fmul and _ftol, and z < -3000 / ln2 short-cuts to P = 0 below.
 * P = the double fmul 1000.0 leaves (V below about 1e-305 rounds as a double denormal here, in the extended range at
 * Kodak: such a P truncates to 0 either way; reachable only for axialProb below about 1e-150, since z >= 2 ln axialProb
 * inside the map). v and decided (may be NULL) report the stages. */
double pkc_flesh_exp1000(double z, double *v_out, int *decided) {
    int dec = 1;
    double t = mul_l2e(z);
    double v = 1.0, P;
    if (!(t == t)) { v = t; P = t; }                 /* NaN: f2xm1 and fscale propagate it */
    else if (t < -3000.0) { v = 1.0; P = 0.0; }      /* far below the double range (and int range for n) */
    else {
        double n = nearbyint(t), f = t - n;
        int sg; uint64_t m; int q;
        if (f2xm1_64(f, &sg, &m, &q, &dec)) v = one_plus(sg, m, q);
        P = ldexp(v, (int)n) * W_PEAK;
    }
    if (v_out) *v_out = v;
    if (decided) *decided = dec;
    return P;
}

pk_status pkc_flesh_weight_plane(const pkc_flesh_params *p, int rows, int cols, int16_t *out) {
    if (!p || !out || rows < 1 || cols < 1 || rows > 32767 || cols > 32767) return PK_E_ARG;
    if (!values_ok(p)) return PK_E_ARG;
    /* fcn.10271bc0(rows, cols): the borders of each axis, the map inside them */
    int32_t br = border(rows, p->clip_amount), bc = border(cols, p->clip_amount);
    if (rows - 2 * br < 1 || cols - 2 * bc < 1) return PK_E_ARG;
    /* 0x10271d3b..0x10271d49: g = sqrt(-8 ln axialProb) (fldln2; fyl2x; fmul; fsqrt) */
    double g = sqrt(log(p->axial_prob) * W_LOG);
    double inv_g = 1.0 / g;                                 /* 0x10271d88 */
    double sx = ((1.0 - p->clip_amount) * (double)cols) * inv_g;    /* 0x10271da4..0x10271dac (stored) */
    double sy = ((1.0 - p->clip_amount) * (double)rows) * inv_g;    /* 0x10271db0..0x10271db6 (register) */
    double cy = (double)half0(rows), cx = (double)half0(cols);
    /* the pad (operation 1, replicate) places the map at ((rows - mr) / 2, (cols - mc) / 2) = (br, bc) */
    for (int y = br; y < rows - br; y++) {
        double ny = ((double)y - cy) * (1.0 / sy);          /* 0x10271df0..0x10271e02 */
        double ny2 = ny * ny;
        double isx = 1.0 / sx;                              /* 0x10271e08..0x10271e0e */
        int16_t *row = out + (size_t)y * cols;
        for (int x = bc; x < cols - bc; x++) {
            double nx = ((double)x - cx) * isx;
            double z = (nx * nx + ny2) * W_HALF;            /* 0x10271e1a..0x10271e20 */
            row[x] = pkc_sx16(ftol32(pkc_flesh_exp1000(z, NULL, NULL)));   /* 0x10271e1c..0x10271e57 */
        }
        for (int x = 0; x < bc; x++) row[x] = row[bc];
        for (int x = cols - bc; x < cols; x++) row[x] = row[cols - bc - 1];
    }
    for (int y = 0; y < br; y++) memcpy(out + (size_t)y * cols, out + (size_t)br * cols, (size_t)cols * sizeof *out);
    for (int y = rows - br; y < rows; y++)
        memcpy(out + (size_t)y * cols, out + (size_t)(rows - br - 1) * cols, (size_t)cols * sizeof *out);
    return PK_OK;
}

/* ---- the detector: fcn.102a1500 (V1, oneDTable) with the threshold chooser fcn.1029ec50 (mode 2) ---- */

/* one axis index, 0x102a1817..0x102a18a9: v - off truncated, negative -> 0 (no divide), else truncated v / (float)scale,
 * clamped at 31 */
static int axis_index(double value, int16_t off, float scale) {
    int32_t v = ftol32(value - (double)off);
    if (v < 0) return 0;
    int32_t i = ftol32((double)v / (double)scale);
    if (i < 0) return 0;     /* Kodak reads before the table here; unreachable once the scales passed values_ok */
    return i > PKC_FLESH_BINS - 1 ? PKC_FLESH_BINS - 1 : i;
}

/* the int16 probability plane, 0..255: p = t[ti] s[si] (l[li]), floored at 0.001, stored as float32, then * 255.0 into
 * float32 and truncated to int16 (0x102a1964 / 0x102a197f) */
static void prob_plane(const pkc_flesh_params *p, const int16_t *R, const int16_t *G, const int16_t *B, size_t n, int16_t *out) {
    float ls = (float)p->lscale, ss = (float)p->sscale, ts = (float)p->tscale;
    for (size_t i = 0; i < n; i++) {
        int32_t r = R[i], g = G[i], b = B[i];
        int32_t L = r + g + b, S = r - b, T = 2 * g - b - r;    /* 0x102a17f0..0x102a1809 */
        float Sf = (float)S, Tf = (float)T;                      /* fstp dword: S, T round to float32 */
        int li = axis_index((double)L, p->loff, ls);
        int si = axis_index((double)Sf, p->soff, ss);
        int ti = axis_index((double)Tf, p->toff, ts);
        double pr = p->cond_t[ti] * p->cond_s[si];               /* 0x102a18be / 0x102a18c4 */
        if (!p->st_only) pr = pr * p->cond_l[li];                /* 0x102a18cf */
        if (pr < PROB_FLOOR) pr = 0.0;                           /* 0x102a18d2: ordered < (a NaN is kept) */
        float pf = (float)pr;
        float sc = (float)((double)pf * PROB_SCALE);
        out[i] = pkc_sx16(ftol32((double)sc));
    }
}

/* the 3x3 correlation (0x104dd9d0) with the reflecting border: index -1 reads 1, n reads n - 2 */
static int mirror(int i, int n) {
    if (n <= 1) return 0;
    while (i < 0 || i >= n) { if (i < 0) i = -i; if (i >= n) i = 2 * n - 2 - i; }
    return i;
}

/* fcn.1029cad0: border forced to 0; a zero pixel becomes 255 unless >= 2 of its 4 neighbours are 0; a non-zero pixel
 * stays 255 only if >= 2 neighbours are > 0 */
static void edge_clean(const int16_t *in, int w, int h, int16_t *out) {
    memset(out, 0, (size_t)w * h * sizeof *out);
    for (int y = 1; y < h - 1; y++)
        for (int x = 1; x < w - 1; x++) {
            const int16_t *c = in + (size_t)y * w + x;
            int nb[4] = { c[-1], c[-w], c[1], c[w] }, n = 0;
            if (*c == 0) {
                for (int k = 0; k < 4; k++) n += nb[k] == 0;
                out[(size_t)y * w + x] = n >= 2 ? 0 : 255;
            } else {
                for (int k = 0; k < 4; k++) n += nb[k] > 0;
                out[(size_t)y * w + x] = n >= 2 ? 255 : 0;
            }
        }
}

/* fcn.1029ec50 with mode 2, useAdvanced 0: the threshold (bin * 4) */
static int32_t threshold_of(const int16_t *P, int w, int h, int16_t *tmp, int16_t *mask) {
    static const int KX[3][3] = { { 1, 0, -1 }, { 2, 0, -2 }, { 1, 0, -1 } }, KY[3][3] = { { 1, 2, 1 }, { 0, 0, 0 }, { -1, -2, -1 } };
    /* 0x1029eeef..0x1029f02d: |conv(P, Sobel x)| + |conv(P, Sobel y)| (int16 stores), >= 400 -> 255, then fcn.1029cad0 */
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            int gx = 0, gy = 0;
            for (int i = 0; i < 3; i++) {
                const int16_t *row = P + (size_t)mirror(y + i - 1, h) * w;
                for (int j = 0; j < 3; j++) {
                    int v = row[mirror(x + j - 1, w)];
                    gx += KX[i][j] * v; gy += KY[i][j] * v;
                }
            }
            int ax = pkc_sx16(gx), ay = pkc_sx16(gy);
            int m = pkc_sx16((ax < 0 ? -ax : ax) + (ay < 0 ? -ay : ay));
            tmp[(size_t)y * w + x] = (int16_t)(m >= EDGE_MIN ? 255 : 0);
        }
    edge_clean(tmp, w, h, mask);
    /* 0x1029f350..0x1029f4bd: 64 float32 bins over the mask's 255 pixels, bin = v / 4 toward zero (v is 0..255 here;
     * Kodak does not range-check the bin) */
    float hist[HIST_BINS] = { 0 }, sm[HIST_BINS];
    for (size_t i = 0; i < (size_t)w * h; i++)
        if ((mask[i] & 0xff) == 0xff) {
            int b = P[i] / 4;
            if (b >= 0 && b < HIST_BINS) hist[b] = (float)((double)hist[b] + 1.0);
        }
    /* 0x1029f4f0..0x1029f537: the 15-tap mean over the bins inside [0, 64), then bins 0 and 1 cleared (0x1029f543) */
    for (int i = 0; i < HIST_BINS; i++) {
        double acc = 0.0; int n = 0;
        for (int j = i - SMOOTH_HALF; j <= i + SMOOTH_HALF; j++)
            if (j >= 0 && j < HIST_BINS) { acc += (double)hist[j]; n++; }
        sm[i] = (float)(acc / (double)n);
    }
    sm[0] = 0.0f; sm[1] = 0.0f;
    /* 0x1029f619..0x1029f6b6: the first bin in 2..61 that is a local minimum over +-2 after a local maximum (the max
     * flag is never cleared) */
    int seen_max = 0;
    for (int i = 2; i < HIST_BINS - 2; i++) {
        int gt = 0, eq = 0, lt = 0;
        const int nb[4] = { i - 2, i - 1, i + 1, i + 2 };
        for (int k = 0; k < 4; k++) { gt += sm[nb[k]] > sm[i]; eq += sm[nb[k]] == sm[i]; lt += sm[nb[k]] < sm[i]; }
        if (eq + lt == 4 && lt) seen_max = 1;
        if (seen_max && eq + gt == 4 && gt) return i * 4;
    }
    return BIN_NONE * 4;
}

pk_status pkc_flesh_delta(const pkc_flesh_params *p, const pkc_planes *img, const int16_t preflesh[3], float exposure,
                          int16_t total[3], pkc_flesh_result *res) {
    if (!p || !img || !preflesh || !total) return PK_E_ARG;
    if (!img->p[0] || !img->p[1] || !img->p[2] || !params_ok(p)) return PK_E_ARG;
    int w = img->w, h = img->h;
    if (w < 3 || h < 3 || w > 32767 || h > 32767) return PK_E_IMAGE_TOO_SMALL;
    /* 0x102706fe..0x1027075f: the borders, from the image's rows (b_outer) and cols (b_inner) */
    int32_t bo = border(h, p->clip_amount), bi = border(w, p->clip_amount);
    if (bo == 0) return PK_E_IMAGE_TOO_SMALL;
    size_t n = (size_t)w * h;
    int16_t *buf = malloc(7 * n * sizeof *buf);
    if (!buf) return PK_E_NOMEM;
    int16_t *S[3] = { buf, buf + n, buf + 2 * n }, *prob = buf + 3 * n, *tmp = buf + 4 * n, *mask = buf + 5 * n, *wt = buf + 6 * n;
    /* 0x102707a7..0x10270979 (and 0x10270ab9.., arg8 = 1, the same image): lut_c[i] = clamp(i + shift_c, 0, 4095) from
     * fcn.1026fed0's table (indexed -0x8000..0x7fff, unchecked beyond: shift_c > 28672 would read past it), applied with a
     * movsx index (unchecked; clamped here) */
    for (int c = 0; c < 3; c++)
        for (size_t i = 0; i < n; i++) {
            int v = img->p[c][i];
            v = (v < 0 ? 0 : v > 4095 ? 4095 : v) + preflesh[c];
            S[c][i] = (int16_t)(v <= 0 ? 0 : v > 4095 ? 4095 : v);
        }
    /* fcn.102a1500: the probability plane, the threshold, then the binary plane prob > threshold cleaned once more
     * (0x102a1e69 / 0x102a1e8e) -- the plane fcn.10270280's clamp loop and reduction read */
    prob_plane(p, S[0], S[1], S[2], n, prob);
    int32_t thr = threshold_of(prob, w, h, tmp, mask);
    for (size_t i = 0; i < n; i++) tmp[i] = (int16_t)(prob[i] > thr ? 255 : 0);
    edge_clean(tmp, w, h, mask);
    /* 0x102711d0..0x10271219: the 0 / 10 / 20 / 255 clamp map over the whole plane, and the any-flesh flag (a value
     * above 20) */
    int any = 0;
    for (size_t i = 0; i < n; i++) {
        int v = mask[i];
        if (v == 0) v = 0;
        else if (v > 255) { v = 255; any = 1; }
        else if (v < 10) v = 0;
        else if (v > 20) any = 1;
        mask[i] = (int16_t)v;
    }
    double stat = 0.0, nsum = 0.0;
    int32_t count = 0, maxp = -1;
    if (any) {
        pk_status st = pkc_flesh_weight_plane(p, h, w, wt);
        if (st != PK_OK) { free(buf); return PK_E_ARG; }
        /* 0x102712ac..0x102714c7: rows h - bo down to bo + 1, cols bi .. w - bi - 1 */
        for (int y = h - bo; y > bo; y--)
            for (int x = bi; x < w - bi; x++) {
                size_t i = (size_t)y * w + x;
                int pv = mask[i];
                if (!((double)pv > (double)thr)) continue;          /* 0x10271413: fcomp; test ah, 0x41 */
                if (pv > maxp) maxp = pv;
                int32_t s = (int32_t)S[0][i] + S[1][i] + S[2][i];
                stat += (double)(int32_t)(uint32_t)((uint32_t)(int32_t)wt[i] * (uint32_t)s);   /* imul, wraps */
                nsum += (double)wt[i];
                count++;
            }
    } else {
        maxp = 0;                                                    /* 0x1027122c / 0x10271607 */
    }
    /* 0x102714e1..0x1027173e */
    double x;
    if (count == 0) x = p->flesh_neutral_aim;
    else x = stat * (p->t_space ? INV_1732 : ONE_THIRD) / nsum;
    double d0 = x - p->flesh_neutral_aim;
    double d = -(d0 * (d0 < 0.0 ? p->back_lit_beta : p->front_lit_beta));   /* fcom 0.0; test ah, 1 */
    int32_t area = (int32_t)(uint32_t)((uint32_t)(w - 2 * bo) * (uint32_t)(h - 2 * bi));   /* 0x1027167f..0x102716a8 */
    double q = (double)count / (double)area;
    int16_t delta = 0;
    if (!(q < p->flesh_count_thresh || isnan(q)) && !((double)exposure < p->exposure_limit || isnan(exposure))) {
        int32_t t = ftol32(d * p->percent_flesh_adj * INV_1732);   /* 0x102716ea..0x10271702 */
        delta = pkc_sx16(ftol32((double)t - p->flesh_pref_adj));        /* 0x10271706..0x10271718 */
    }
    if (p->darken_only && d > 0.0) delta = 0;                       /* 0x10271736..0x10271752 */
    for (int c = 0; c < 3; c++) total[c] = (int16_t)(uint16_t)((uint32_t)(uint16_t)preflesh[c] + (uint16_t)delta);
    if (res) {
        res->x = x; res->nsum = nsum; res->q = q;
        res->neg_d130 = -(d * INV_130); res->max_prob255 = (double)maxp * INV_255; res->threshold = (double)thr;
        for (int c = 0; c < 3; c++) res->adjust[c] = delta;
        res->stat = stat; res->d = d; res->count = count; res->max_prob = maxp; res->area = area;
        res->b_outer = bo; res->b_inner = bi; res->any_flesh = any;
    }
    free(buf);
    return PK_OK;
}
