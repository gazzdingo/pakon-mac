/* FOS: SbaCalcFosResults (PakonIMAu.dll 0x1028f570) and its callers' gate, ported from the disassembly (docs/re/16
 * section 6). lab/reference pakon_fos.py fos_analyze_roll is the same algorithm but reorders the eigen solver's
 * floating-point operations and leaves the helper's weight table off; this port follows Kodak's instruction order.
 * Integer arithmetic is Kodak's 32-bit (wrapping) arithmetic; floating point is double = x87 at PC53. */
#include "analysis/fos.h"
#include "analysis/kint.h"
#include "data/kodak_text.h"
#include <math.h>
#include <string.h>

#define N PKC_GRID_N
#define ERR_DISC 0x189d          /* eigen discriminant failure (0x1029006b) */

static int32_t rd16(const uint8_t *b, int off) { return pkc_sx16(b[off] | b[off + 1] << 8); }

/* _ftol2 (kint.h); every caller stores the low word */
static int32_t ftol_word(double x) { return pkc_sx16(pkc_ftol64(x)); }

/* sar 5 of a 32-bit product (floor division by 32) */
static int32_t sar5(int32_t p) { return p >= 0 ? p / 32 : -(int32_t)(((int64_t)-(int64_t)p + 31) / 32); }

/* The rdata doubles the calc multiplies by (0x105a6f28.., 0x1058f6c0, ...), by bit pattern. */
static double kd(uint64_t bits) { double d; memcpy(&d, &bits, sizeof d); return d; }

/* 0x1028f362..0x1028f393: the integer square root (kint.h); a negative argument falls into its "below 2" exit */
static int32_t isqrt_k(int32_t x) { return x < 2 ? x : pkc_isqrt(x); }

/* 0x1028f1b0: the distance weight. t = lo, mid (orderFpoLow/HighSatLimit), mid_w, hi_w (Min/MaxWeight). */
static int32_t weight(int32_t r, const int16_t *t) {
    int32_t lo = t[0], mid = t[1], mid_w = t[2], hi_w = t[3];
    if (r <= lo) return hi_w;
    if (r >= mid) return mid_w;
    int32_t slope = pkc_wrap32((int64_t)(hi_w - mid_w) * r), base = pkc_wrap32((int64_t)pkc_wrap32((int64_t)mid_w * lo - mid) * 100);
    int32_t num = pkc_wrap32((int64_t)slope + base);
    return pkc_half_round_div(pkc_wrap32((int64_t)num * 1000), pkc_wrap32((int64_t)(lo - mid) * 1000));
}

/* The 290c / 388c / dc / weight-table inputs of one roll, as the helper and the paxel walk see them. */
typedef struct { int32_t c1_lo, c2_lo, c1_hi, c2_hi, gate; } bank;

/* 0x1028f250: orderFpo deltas. Returns 0, -1 (method 2: the caller falls back to the dmin chroma), or -2 where this port
 * cannot follow Kodak: the overflow exit (0x1028f424, delta 0 left uninitialised) or a division by zero (#DE) that only
 * a negative dc threshold would reach. */
static int helper(const bank *bk, int m, int skip, const uint8_t *dc, const int16_t *wtab, const int32_t dmo[6],
                  int32_t delta[3], int32_t *ofpo) {
    int32_t r = rd16(dc, 0x20), r2 = pkc_wrap32((int64_t)r * r);         /* helper radius 250 */
    int32_t w_gm = rd16(dc, 0x1c), w_ill = rd16(dc, 0x1e);              /* blend weights 605 / 750 */
    int32_t thresh = rd16(dc, 0x2c), gate = rd16(dc, 0x0e);             /* in-radius count 3, hi/lo bank gate 10 */
    int32_t enable = wtab[4];                                           /* orderFpoUseExpandedSatLimit */
    int32_t s1 = 0, s2 = 0, cnt = 0;                                    /* in-radius sums */
    int32_t ws1 = 0, ws2 = 0, wsw = 0, ret = 0;                         /* weighted sums */
    *ofpo = 0;
    for (int k = 0; k < m; k++) {
        if (skip) continue;                                      /* byte[388c+4] == 1 */
        int hi = bk[k].gate > gate;                                     /* 0x1028f301 jle */
        int32_t c1 = hi ? bk[k].c1_hi : bk[k].c1_lo, c2 = hi ? bk[k].c2_hi : bk[k].c2_lo;
        int32_t d1 = pkc_wrap32((int64_t)bk[k].c1_lo - dmo[4]), d2 = pkc_wrap32((int64_t)bk[k].c2_lo - dmo[5]);
        int32_t dist2 = pkc_wrap32(pkc_wrap32((int64_t)d1 * d1) + (int64_t)pkc_wrap32((int64_t)d2 * d2));
        if (dist2 < r2) {                                               /* 0x1028f333 jge */
            s1 = pkc_wrap32((int64_t)s1 + c1);
            s2 = pkc_wrap32((int64_t)s2 + c2);
            cnt++;
        }
        if (enable != 0) {
            if (dist2 < 0) return -2;                            /* Kodak: return -1 with delta 0 unset (0x1028f424) */
            int32_t w = weight(isqrt_k(dist2), wtab);
            ws1 = pkc_wrap32((int64_t)ws1 + pkc_wrap32((int64_t)c1 * w));
            ws2 = pkc_wrap32((int64_t)ws2 + pkc_wrap32((int64_t)c2 * w));
            wsw = pkc_wrap32((int64_t)wsw + w);
        }
    }
    int32_t m1 = s1, m2 = s2;
    if (pkc_sx16(cnt) > thresh) {                                    /* cmp di, ax: 16-bit */
        if (cnt == 0) return -2;
        m1 = s1 / cnt; m2 = s2 / cnt;
    } else if (wsw > pkc_wrap32((int64_t)thresh * 100) && enable != 0) {   /* 0x1028f444 jle */
        int32_t den = pkc_wrap32((int64_t)wsw * 1000);
        if (den == 0) return -2;
        m1 = pkc_half_round_div(pkc_wrap32((int64_t)ws1 * 1000), den);
        m2 = pkc_half_round_div(pkc_wrap32((int64_t)ws2 * 1000), den);
        *ofpo = 1;
    } else { ret = -1; *ofpo = 2; }                              /* means stay the raw in-radius sums */
    delta[0] = pkc_wrap32((int64_t)dmo[0] + 0x498);
    delta[1] = pkc_wrap32((int64_t)pkc_wrap32((int64_t)w_gm * m1) + pkc_wrap32((int64_t)(1000 - w_gm) * dmo[4])) / 1000;
    delta[2] = pkc_wrap32((int64_t)pkc_wrap32((int64_t)w_ill * m2) + pkc_wrap32((int64_t)(1000 - w_ill) * dmo[5])) / 1000;
    return ret;
}

/* Paxel sums (0x1028f9a8..0x1028fe2b): u32 accumulators, read back as Kodak's signed dwords. */
typedef struct { uint32_t n, sr, sg, sb, su, sv, sw, prg, prb, pgb, prr, pgg, pbb, puv, puw, puu, pvv, pww; } sums;
#define ADD(f, v) (s.f += (uint32_t)(int32_t)(v))
static double fd(uint32_t v) { return (double)pkc_wrap32(v); }

pk_status pkc_fos_roll(const pkc_sba_ctx *ctx, const pkc_fos_params *fp, int n, const int32_t (*grids)[3][PKC_GRID_N],
                       const uint16_t (*dmins)[3], const pkc_sba_scene *scenes, pkc_fos_result *out) {
    if (!ctx || !fp || !out || n < 0 || (n > 0 && (!grids || !dmins || !scenes))) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    int m = n < fp->max_frames ? n : fp->max_frames;            /* Impl::analyze: min(scenes, maxFramesToFos) */
    if (m < 0) m = 0;
    if (m > PKC_FOS_MAX_SCENES) return PK_E_ARG;
    if (!fp->fos_on) return PK_OK;                              /* fosOn 0, useHistory 0: Impl::analyze never calculates */
    if (m < fp->min_frames) return PK_OK;                       /* < mff, useHistory 0: no FOS */
    if (m < 1) { out->calc_err = 0x18a5; return PK_OK; }        /* (short)n < 1 */
    static const int SLOT[5] = { 4, 5, 480, 481, 612 };
    for (int k = 0; k < m; k++)
        for (int j = 0; j < 5; j++) if (!scenes[k].known[SLOT[j]]) return PK_E_VENDOR_DATA;   /* R18 */
    const uint8_t *dc = ctx->params + 0xDC;
    int skip = ctx->flags[4] == 1;

    /* opening (0x1028f608), fosDmin (0x1028f6d8: signed word min), dmin - open (0x1028f750) */
    int32_t op[3] = { ctx->opening[0], ctx->opening[1], ctx->opening[2] }, oy, oc1, oc2;
    pkc_sba_axes(op[0], op[1], op[2], &oy, &oc1, &oc2);
    int32_t dm[3];
    for (int c = 0; c < 3; c++) dm[c] = pkc_sx16(dmins[0][c]);
    for (int k = 1; k < m; k++) for (int c = 0; c < 3; c++) if (dm[c] > pkc_sx16(dmins[k][c])) dm[c] = pkc_sx16(dmins[k][c]);
    int32_t dmo[6];
    for (int c = 0; c < 3; c++) dmo[c] = pkc_sx16(dm[c] - op[c]);
    pkc_sba_axes(dmo[0], dmo[1], dmo[2], &dmo[3], &dmo[4], &dmo[5]);

    bank bk[PKC_FOS_MAX_SCENES];
    for (int k = 0; k < m; k++) {
        const int32_t *v = scenes[k].vec;
        bk[k] = (bank){ v[4], v[5], v[480], v[481], v[612] };
    }
    int32_t delta[3], ofpo;
    int hr = helper(bk, m, skip, dc, fp->wtab, dmo, delta, &ofpo);
    if (hr == -2) return PK_E_VENDOR_DATA;
    if (hr == -1) { delta[1] = dmo[4]; delta[2] = dmo[5]; }      /* 0x1028f878 */
    out->order_fpo[0] = pkc_sx16(oy + delta[0]);
    out->order_fpo[1] = pkc_sx16(oc1 + delta[1]);
    out->order_fpo[2] = pkc_sx16(oc2 + delta[2]);
    for (int c = 0; c < 3; c++) out->dmin[c] = dm[c];
    out->ofpo_method = ofpo;

    /* paxel walk: rows 1..22, cols 1..34 of the 24x36 grid; mask == 1 and inside the paxel radius around the deltas */
    int32_t pr = rd16(dc, 0x18), pr2 = pkc_wrap32((int64_t)pr * pr), nthr = rd16(dc, 0x2e);
    sums g; memset(&g, 0, sizeof g);
    for (int k = 0; k < m && !skip; k++) {
        sums s; memset(&s, 0, sizeof s);
        const int32_t (*gr)[N] = grids[k];
        const uint8_t *mask = scenes[k].mask;
        for (int row = 0x25; row < 0x33d; row += 0x24)
            for (int i = row; i < row + 0x22; i++) {
                if (mask[i] != 1) continue;
                int32_t y, c1, c2;
                pkc_sba_axes(pkc_sx16(gr[0][i]), pkc_sx16(gr[1][i]), pkc_sx16(gr[2][i]), &y, &c1, &c2);
                int32_t R = pkc_sx16(gr[0][i] - op[0]), G = pkc_sx16(gr[1][i] - op[1]), B = pkc_sx16(gr[2][i] - op[2]);
                int32_t U = pkc_sx16(y - op[2]), V = pkc_sx16(c1 - oc1), W = pkc_sx16(c2 - oc2);   /* U: Y minus open B (0x1028faa0) */
                int32_t dv = V - delta[1], dw = W - delta[2];
                if (pkc_wrap32((int64_t)pkc_wrap32((int64_t)dv * dv) + pkc_wrap32((int64_t)dw * dw)) >= pr2) continue;
                ADD(sr, R); ADD(sg, G); ADD(sb, B);
                ADD(su, U); ADD(sv, V); ADD(sw, W);
                ADD(prg, sar5(G * R)); ADD(prb, sar5(B * R)); ADD(pgb, sar5(B * G));
                ADD(prr, sar5(R * R)); ADD(pgg, sar5(G * G)); ADD(pbb, sar5(B * B));
                ADD(puv, sar5(U * V)); ADD(puw, sar5(U * W));
                ADD(puu, sar5(U * U)); ADD(pvv, sar5(V * V)); ADD(pww, sar5(W * W));
                s.n++;
            }
        if (pkc_wrap32(s.n) < nthr) continue;                       /* 0x1028fcdd jl: fewer than 30 samples */
        g.n += s.n; g.sr += s.sr; g.sg += s.sg; g.sb += s.sb; g.su += s.su; g.sv += s.sv; g.sw += s.sw;
        g.prg += s.prg; g.prb += s.prb; g.pgb += s.pgb; g.prr += s.prr; g.pgg += s.pgg; g.pbb += s.pbb;
        g.puv += s.puv; g.puw += s.puw; g.puu += s.puu; g.pvv += s.pvv; g.pww += s.pww;
    }
    if (g.n == 0) {                                              /* 0x10290401: offsets = the deltas */
        out->gm_off = pkc_sx16(delta[1]); out->ill_off = pkc_sx16(delta[2]);
        out->valid = 1;
        return PK_OK;
    }

    /* 0x1028fe61..: the covariance, then the smallest eigenvalue of tr*I - C by the trigonometric cubic, in Kodak's order */
    double Nn = fd(g.n), SR = fd(g.sr), SG = fd(g.sg), SB = fd(g.sb);
    double xRG = -(fd(g.prg) * 32.0 - SR * SG / Nn);            /* [0x38] */
    double xRB = -(fd(g.prb) * 32.0 - SB * SR / Nn);            /* [0x18] */
    double xGB = -(fd(g.pgb) * 32.0 - SB * SG / Nn);            /* [0x40] */
    double cRR = fd(g.prr) * 32.0 - SR * SR / Nn;
    double cGG = fd(g.pgg) * 32.0 - SG * SG / Nn;
    double cBB = fd(g.pbb) * 32.0 - SB * SB / Nn;
    double a = cBB + cGG, b = cBB + cRR, c = cGG + cRR;         /* [0x20] [0x98] st */
    double d = -((b + c) + a);                                  /* [0x10] */
    double e = xRG * xRG;                                       /* [0x14c] */
    double gq = (((c * a + b * a) + b * c) - e - xRB * xRB) - xGB * xGB;
    double h = (d * d - gq * 3.0) * kd(0x3fbc71c71c71c71cULL);  /* [0x154] (x 1/9) */
    double s4 = (((a * xGB) * xGB + (b * xRB) * xRB) + (c * xRG) * xRG - (b * c) * a) - ((xGB * xRB) * xRG + (xGB * xRB) * xRG);
    double q = (((d * d) * d + (d * d) * d) - (gq * d) * 9.0 + s4 * 27.0) * kd(0x3f92f684bda12f68ULL);   /* [0x48] (x 1/54) */
    double h3 = (h * h) * h;
    if (h3 < q * q) {                                           /* 0x1029005f: error 0x189d */
        out->calc_err = ERR_DISC;
        return PK_OK;
    }
    double th = acos(q / sqrt(h3));
    const double third = kd(0x3fd5555555555555ULL);
    double d3 = d * third, mm = sqrt(h) * -2.0, ph = th * third;
    double cph = cos(ph), sph = sin(ph), k5 = cph * -0.5;
    double sg1 = (k5 - sph * kd(0x3febb67ae6502b91ULL)) * mm - d3, sg2 = (k5 - sph * kd(0xbfebb67ae6502b91ULL)) * mm - d3;
    double sg0 = cph * mm - d3;
    double sig = sg0;
    if (sg1 < sig) sig = sg1;
    if (sg2 < sig) sig = sg2;
    double u = b - sig, v = a - sig;
    double inv = 1.0 / (v * u - e);
    double p1 = (xGB * xRG - u * xRB) * inv, p2 = (xRB * xRG - v * xGB) * inv;
    double sc = 1.0 / sqrt((p2 * p2 + p1 * p1) + 1.0);
    double eR = p1 * sc, eB = sc, eG = p2 * sc;
    if (eR < 0.0) { eR = -eR; eG = -eG; eB = -eB; }
    double mR = SR / Nn, mG = SG / Nn, mB = SB / Nn;
    const double K3 = kd(0x3fe279a746eaf3d8ULL), K6 = kd(0x3fda20bd77b432acULL), K2 = kd(0x3fe6a09e5c65884eULL);
    double ye = ((eB + eG) + eR) * K3, c1e = ((eG + eG - eR) - eB) * K6, c2e = (eB - eR) * K2;
    double ym = ((mB + mG) + mR) * K3, c1m = ((mG + mG - mR) - mB) * K6, c2m = (mB - mR) * K2;
    out->order_avg[0] = ftol_word((double)op[0] + mR);
    out->order_avg[1] = ftol_word((double)op[1] + mG);
    out->order_avg[2] = ftol_word((double)op[2] + mB);
    out->gm_slope = ftol_word(c1e * 10000.0);
    double iy = 1.0 / ye;
    out->gm_off = ftol_word(c1m - (c1e * iy) * ym);
    out->ill_slope = ftol_word(c2e * 10000.0);
    out->ill_off = ftol_word(c2m - (iy * c2e) * ym);
    /* R^2 (0x10290332..): 1000 Cov(U,X)^2 / (Var X * Var U) for X = V (gm) and W (ill) */
    double SU = fd(g.su), SV = fd(g.sv), SW = fd(g.sw);
    double cuv = fd(g.puv) * 32.0 - SU * SV / Nn, vu = fd(g.puu) * 32.0 - SU * SU / Nn;
    out->gm_rsq = ftol_word(((cuv * cuv) * 1000.0) / ((fd(g.pvv) * 32.0 - SV * SV / Nn) * vu));
    double cuw = fd(g.puw) * 32.0 - SW * SU / Nn;
    out->ill_rsq = ftol_word(((cuw * cuw) * 1000.0) / ((fd(g.pww) * 32.0 - SW * SW / Nn) * vu));
    out->num_pixels = pkc_sx16(g.n);
    out->valid = 1;
    return PK_OK;
}

pk_status pkc_fos_params_load(const char *vendor_root, pkc_fos_params *out) {
    if (!vendor_root || !out) return PK_E_ARG;
    char path[1100];
    if (pkc_vendor_path(vendor_root, PKC_SBA_DPI_DEFAULT, path, sizeof path) != PK_OK) { memset(out, 0, sizeof *out); return PK_E_VENDOR_DATA; }
    return pkc_fos_params_read(path, out);
}

pk_status pkc_fos_params_read(const char *dpi, pkc_fos_params *out) {
    if (!dpi || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    pkc_kt *kt = NULL;
    if (pkc_kt_load(dpi, &kt) != PK_OK) return PK_E_VENDOR_DATA;
    static const char *const KEY[9] = { "orderFpoLowSatLimit", "orderFpoHighSatLimit", "orderFpoMinWeight", "orderFpoMaxWeight",
                                        "orderFpoUseExpandedSatLimit", "mff", "maxFramesToFos", "fosOn", "useHistory" };
    double v[9];
    for (int i = 0; i < 9; i++)
        if (pkc_kt_num(kt, KEY[i], &v[i], 1) != 1 || !(v[i] >= -32768.0 && v[i] <= 32767.0) || v[i] != floor(v[i])) {
            pkc_kt_free(kt);
            return PK_E_VENDOR_DATA;
        }
    pkc_kt_free(kt);
    for (int i = 0; i < 5; i++) out->wtab[i] = (int16_t)v[i];
    out->min_frames = (int32_t)v[5]; out->max_frames = (int32_t)v[6]; out->fos_on = v[7] != 0;
    /* Kodak's dpi checks (strings at 0x105a6cf8..0x105a6e64) and the paths this port does not have */
    if (!(v[0] > 0 && v[1] > 0 && v[0] < v[1] && v[2] >= 0 && v[2] <= 100 && v[3] >= 0 && v[3] <= 100 && v[2] < v[3]) ||
        (v[7] != 1 && v[7] != 0) || v[8] != 0 || out->max_frames < 1 || out->max_frames > PKC_FOS_MAX_SCENES) {
        memset(out, 0, sizeof *out);
        return PK_E_VENDOR_DATA;
    }
    return PK_OK;
}
