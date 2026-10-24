/* The SBA triple, Preference and setShifts (1,2): FUN_1028ae00 with the FOS-pointer count / weight of fcn.102aece0 /
 * fcn.102b7440, fcn.1028c780 (mode 0), ColorNegativePath::setShifts 0x10100a37, and Makesfs (fcn.102ac820) for the
 * 50x83 weight table. Ported from the disassembly (docs/re/17) and pinned against Kodak at x87 PC53
 * (lab/rollbal/truth/t13, core/tests/colour/test_sba_pref.c). Integer arithmetic wraps like Kodak's 32-bit registers
 * and 16-bit word stores; Preference's x87 at PC53 rounds every operation to double exactly as the C doubles below do
 * (-ffp-contract=off; no value leaves the double exponent range), in Kodak's operation order. */
#include "data/diag.h"
#include "analysis/sba_pref.h"
#include "analysis/kint.h"
#include "data/kodak_text.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define N PKC_GRID_N

static int16_t par_w(const pkc_sba_ctx *c, int i) {          /* the pcode params at +0xdc, as words */
    const uint8_t *p = c->params + 0xDC + 2 * i;
    return (int16_t)(uint16_t)(p[0] | p[1] << 8);
}

/* ------------------------------------------------------------------------------------------------ Makesfs */

/* fcn.102b7130: Kodak's integer square root, -1 for a negative argument (pkc_isqrt for the rest) */
static int32_t isqrt_neg(int32_t x) { return x < 0 ? -1 : pkc_isqrt(x); }
/* fcn.102b7280: the row check (0 = accepted; Kodak's codes 6..14 otherwise) */
static int sfs_check(const int16_t r[6][4]) {
    if (r[0][0] == 0) return 0xe;
    int done = 0;
    for (int k = 0; k < 6; k++) {
        int a = r[k][0], rad = r[k][1], b = r[k][2], fl = r[k][3];
        if (done) { if (a || b || rad || fl) return 6; continue; }
        if (a == 0 || b == 0 || rad == 0) {                 /* 0x102b72f9: only an all-zero row ends the list */
            if (a != 0 || b != 0 || rad != 0 || fl != 0) return 6;
            done = 1; continue;
        }
        if (a < 1 || a > 120) return 10;
        if (b < 1 || b > 120) return 0xc;
        if (rad < 1 || rad > 2000) return 0xb;
        if (fl < 0 || fl > 100) return 0xd;
        int na = r[(k + 1) % 6][0];
        if (na == 0) na = r[0][0];
        else if (k != 5 && a >= na) return 7;               /* starts must increase */
        if (k == 0 && r[1][0] == 0) {                       /* 0x102b73a0: a single row must span at least 60 hues */
            if ((b - a + 120) % 120 < 60) return 8;
        } else if (a > b) {                                  /* 0x102b73cd: a wrapping span must end before the next start */
            if (na >= a || na <= b) return 9;
        } else if (na >= a && na <= b) return 9;
        if ((na - b + 120) % 120 >= 60) return 8;           /* 0x102b73e6: the gap to the next row */
    }
    return 0;
}
/* 0x102ac6e0..: the sine table at a folded hue distance (0 outside 0..30) */
static int32_t fold_sin(int x, const int16_t sn[31]) {
    if (x < 0) x += 120;
    if (x > 30) x = 60 - x;
    return (x < 0 || x > 30) ? 0 : sn[x];
}
/* fcn.102ac590: the 120 hue entries (radius, floor) from the rows; set[] = 1 for entries written, 2 where Kodak divides
 * by zero writing it */
static void sfs_hues(const int16_t r[6][4], const int16_t sn[31], int16_t ent[120][2], uint8_t set[120]) {
    int nx = 1, done = 0;
    for (int k = 0; k < 6 && !done; k++) {
        int a = r[k][0], rk = r[k][1], b = r[k][2], mk = r[k][3];
        int an = r[nx][0], rn = r[nx][1], mn = r[nx][3];
        int span = b - a;
        if (b < a) span += 120;
        for (int i = 0; i <= span; i++) {                   /* 0x102ac620: the row over its own hues */
            int ix = (i + a - 1) % 120;
            ent[ix][0] = (int16_t)rk; ent[ix][1] = (int16_t)mk; set[ix] = 1;
        }
        if (an == 0) { rn = r[0][1]; mn = r[0][3]; an = r[0][0]; nx = 0; done = 1; }   /* the end row: back to row 0 */
        int gap = an < b ? an - b + 120 : an - b;
        if (gap > 1) {                                      /* 0x102ac686: blend across the gap */
            int32_t half = gap / 2, dm = mn - mk, jd = dm, jdh = dm - half;
            int32_t sg = fold_sin(gap, sn);
            for (int j = 1; j < gap; j++) {
                int ix = (b + j - 1) % 120;
                int32_t numr = pkc_wrap32((int64_t)pkc_wrap32((int64_t)sg * rn) * rk);
                int32_t den = pkc_wrap32((int64_t)pkc_wrap32((int64_t)fold_sin(j, sn) * rk) + pkc_wrap32((int64_t)fold_sin(gap - j, sn) * rn));
                if (den) { ent[ix][0] = pkc_sx16(pkc_wrap32((int64_t)den / 2 + numr) / (int64_t)den); set[ix] = 1; }
                else set[ix] = 2;                           /* Kodak: #DE */
                /* the floor: pkc_half_round_div(j * dm, gap) + mk ([esp+0x38] = j*dm, [esp+0x24] = j*dm - half: 0x102ac77e..) */
                int32_t q = jd < 0 ? (gap >= 0 ? jdh : jd + half) : (gap >= 0 ? jd + half : jdh);
                ent[ix][1] = pkc_sx16(q / gap + mk);
                jd += dm; jdh += dm;
            }
        }
        nx = (nx + 1) % 6;
    }
}
pk_status pkc_sfs_build(const int16_t rows[6][4], const int16_t sin_tab[31], int8_t out[PKC_SFS_N]) {
    if (!rows || !sin_tab || !out) return PK_E_ARG;
    if (sfs_check(rows)) return PK_E_VENDOR_DATA;           /* Makesfs returns the code; AnsSfsTableDPI's ctor fails */
    int16_t ent[120][2]; uint8_t set[120];
    memset(ent, 0, sizeof ent); memset(set, 0, sizeof set);
    sfs_hues(rows, sin_tab, ent, set);
    /* fcn.102ac430: cell (gx, gy) at C1 = -384 + 16 gx, C2 = -656 + 16 gy: the hue of an RGB-like triple of the cell, its
     * entry's radius e and floor; weight = max(100 - pkc_half_round_div(isqrt(100 (C1^2 + C2^2)), e), floor) */
    int k = 0;
    for (int gx = 0; gx < PKC_SFS_NX; gx++) {
        int32_t c = -384 + 16 * gx, v10 = -0x17EB00 + 0xFF20 * gx, v14 = -0x2FD780 + 0x1FE50 * gx, v18 = 0x17EB00 - 0xFF20 * gx;
        for (int gy = 0; gy < PKC_SFS_NY; gy++, k++) {
            int32_t e2 = -656 + 16 * gy, es = -0x46C770 + 0x1B9F0 * gy;
            int h = pkc_hue120(pkc_wrap32((int64_t)v18 - es), v14, pkc_wrap32((int64_t)es - v10));
            int32_t rr = isqrt_neg(pkc_wrap32((int64_t)pkc_wrap32((int64_t)e2 * e2 + (int64_t)c * c) * 100));
            if (set[h - 1] != 1) return PK_E_VENDOR_DATA;   /* an entry the rows never wrote, or a #DE writing it */
            int32_t e = ent[h - 1][0];
            if (e == 0) return PK_E_VENDOR_DATA;            /* idiv by zero (#DE) */
            int32_t half = e / 2;
            int32_t num = (rr < 0) == (e < 0) ? rr + half : rr - half;
            int32_t val = 100 - num / e;
            if (val < ent[h - 1][1]) val = ent[h - 1][1];
            out[k] = (int8_t)(uint8_t)val;                  /* mov byte [eax], cl */
        }
    }
    return PK_OK;
}

/* operator>>(istream&, AnsSfsTableDef&) (0x102ac8c0): 24 shorts, whitespace separated (MSVC num_get: optional sign and
 * digits; out of short range or no digits sets failbit; reaching end of file sets eofbit; any state bit after the 24
 * reads -- or before one -- is "Error reading file") */
static int read_short(FILE *f, int16_t *v) {
    int ch;
    do ch = getc(f); while (ch != EOF && isspace(ch));
    if (ch == EOF) return 0;                                /* end of file before a number */
    int neg = 0;
    if (ch == '+' || ch == '-') { neg = ch == '-'; ch = getc(f); }
    long x = 0; int nd = 0;
    while (ch != EOF && isdigit(ch)) { if (x < 100000) x = x * 10 + (ch - '0'); nd++; ch = getc(f); }
    if (!nd || ch == EOF) return 0;                         /* failbit, or eofbit inside the number */
    ungetc(ch, f);
    if (neg) x = -x;
    if (x < -32768 || x > 32767) return 0;
    *v = (int16_t)x;
    return 1;
}
pk_status pkc_sfs_table(const char *sfs_path, const char *derived_root, int8_t out[PKC_SFS_N]) {
    if (!sfs_path || !derived_root || !out) return PK_E_ARG;
    char path[1100];
    int16_t sn[31], rows[6][4];
    if (snprintf(path, sizeof path, "%s/imau_tables/sfs_sin_105a8830.bin", derived_root) >= (int)sizeof path) return PK_E_ARG;
    FILE *f = pkc_fopen(path, "rb");
    if (!f) return PK_E_VENDOR_DATA;
    uint8_t raw[62];
    size_t got = fread(raw, 1, sizeof raw, f);
    int extra = fgetc(f) != EOF;
    fclose(f);
    if (got != sizeof raw || extra) return PK_E_VENDOR_DATA;
    for (int k = 0; k < 31; k++) sn[k] = (int16_t)(uint16_t)(raw[2 * k] | raw[2 * k + 1] << 8);
    f = pkc_fopen(sfs_path, "rb");
    if (!f) return PK_E_VENDOR_DATA;
    int ok = 1;
    for (int k = 0; ok && k < 6; k++)                      /* streamed like the istream: no size limit, the rest unread */
        for (int j = 0; ok && j < 4; j++) ok = read_short(f, &rows[k][j]);
    fclose(f);
    if (!ok) return PK_E_VENDOR_DATA;
    return pkc_sfs_build((const int16_t (*)[4])rows, sn, out);
}

/* ------------------------------------------------------------------------------------------------ dpi */

static int kt_int(const pkc_kt *kt, const char *key, int n, int16_t *v) {
    double d[3];
    if (pkc_kt_num(kt, key, d, n) != n) return 0;
    for (int i = 0; i < n; i++) {
        if (!(d[i] >= -32768.0 && d[i] <= 32767.0) || d[i] != (double)(long)d[i]) return 0;
        v[i] = (int16_t)d[i];
    }
    return 1;
}
/* 0x104ffe44 (_ftol2, kint.h): callers keep ax (a word store) or eax (fild dword) */
static int64_t ftol2(double x) { return pkc_ftol64(x); }
pk_status pkc_sba_pref_load(const char *vendor_root, const char *derived_root, pkc_sba_pref *out) {
    if (!vendor_root || !derived_root || !out) return PK_E_ARG;
    char dpi[1100];
    if (pkc_vendor_path(vendor_root, PKC_SBA_DPI_DEFAULT, dpi, sizeof dpi) != PK_OK) { memset(out, 0, sizeof *out); return PK_E_VENDOR_DATA; }
    return pkc_sba_pref_read(vendor_root, derived_root, dpi, out);
}

pk_status pkc_sba_pref_read(const char *vendor_root, const char *derived_root, const char *dpi, pkc_sba_pref *out) {
    if (!vendor_root || !derived_root || !dpi || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    char path[1100];
    pkc_kt *kt = NULL;
    pk_status st = pkc_kt_load(dpi, &kt);
    if (st != PK_OK) return st == PK_E_NOMEM ? st : PK_E_VENDOR_DATA;
    /* fcn.10214f20's block from the scene's dpi copy (scene+0x4cf0..+0x4d52); the words it copies, in block order */
    static const struct { const char *key; int word, n; } K[] = {
        { "fpo", 0, 3 }, { "fpa", 3, 3 }, { "neu", 6, 3 }, { "neo", 9, 3 }, { "dmd", 12, 3 }, { "pcls", 15, 1 },
        { "pcwf", 16, 1 }, { "ix_pcwf", 17, 1 }, { "nonFlashAdj", 18, 1 }, { "fmt", 19, 1 }, { "cmm", 24, 1 }, { "fog", 25, 1 },
        { "fxr", 26, 1 }, { "blk", 27, 1 }, { "bxr", 28, 1 }, { "ll1", 29, 1 }, { "ll2", 30, 1 }, { "mff", 32, 1 } };
    int ok = 1;
    for (size_t i = 0; ok && i < sizeof K / sizeof K[0]; i++) ok = kt_int(kt, K[i].key, K[i].n, out->blob + K[i].word);
    int16_t nb = 0, nbp = 0;
    double under = 0, over = 0;
    ok = ok && kt_int(kt, "neutralButton", 1, &nb) && kt_int(kt, "neutralBalancePoint", 1, &nbp) &&
         pkc_kt_num(kt, "neutralUnderConstraint", &under, 1) == 1 && pkc_kt_num(kt, "neutralOverConstraint", &over, 1) == 1 &&
         under > -1e9 && under < 1e9 && over > -1e9 && over < 1e9;
    const char *sfs = ok ? pkc_kt_str(kt, "sfsTable") : NULL;
    char rel[300];
    ok = ok && sfs && strlen(sfs) < 200 && !strchr(sfs, '/') &&
         snprintf(rel, sizeof rel, "anselinstalldir/dataPathItems/sba/Sfs/%s", sfs) < (int)sizeof rel;
    pkc_kt_free(kt);
    if (!ok) { memset(out, 0, sizeof *out); return PK_E_VENDOR_DATA; }
    out->blob[20] = 50; out->blob[21] = 83; out->blob[31] = 140;
    out->blob[33] = pkc_sx16(ftol2((double)nb * under));       /* 0x10215048: fild nb; fmul qword under; _ftol; mov word */
    out->blob[34] = pkc_sx16(ftol2((double)nb * over));
    out->blob[35] = pkc_sx16(pkc_bias_div(pkc_wrap32((int64_t)nbp * 0x2A495), 0xC350, 100000));   /* 0x10215084: (nbp*173205 +- 50000) / 1e5 */
    st = pkc_vendor_path(vendor_root, rel, path, sizeof path);
    if (st == PK_OK) st = pkc_sfs_table(path, derived_root, out->sfs);
    if (st != PK_OK) { memset(out, 0, sizeof *out); return PK_E_VENDOR_DATA; }
    return PK_OK;
}

/* ------------------------------------------------------------------------------------------------ the triple */

pk_status pkc_sba_triple(const pkc_sba_measure *m, const pkc_sba_scene *scene, const pkc_sba_ctx *c, const pkc_sba_pref *pref,
                         int pass, const pkc_fos_result *fos, pkc_sba_triple_out *out) {
    if (!m || !scene || !c || !pref || !out || (pass != PKC_SBA_FOS2 && pass != PKC_SBA_SHORT2)) return PK_E_ARG;
    int mode = pass == PKC_SBA_FOS2 ? 2 : 0;               /* fcn.1028b8d0 hands FUN_1028ae00 its arg4 (the pass kind) */
    if (mode && (!fos || !fos->valid)) return PK_E_ARG;
    for (int i = 0; i < N; i++)                             /* Kodak's measure image planes 3-5 are int16 words */
        if (m->Yband[i] != pkc_sx16(m->Yband[i]) || m->C1band[i] != pkc_sx16(m->C1band[i]) || m->C2band[i] != pkc_sx16(m->C2band[i]))
            return PK_E_ARG;
    for (int j = 3; j < 6; j++) if (!scene->known[j]) return PK_E_VENDOR_DATA;     /* R18: obj+0x48 / +0x4c / +0x50 */
    memset(out, 0, sizeof *out);

    /* the opening: RGB (dpi fpo) and its axes, fcn.1028b8d0's local_2b4 block */
    int32_t op[6];
    for (int k = 0; k < 3; k++) op[k] = c->opening[k];
    pkc_sba_axes(op[0], op[1], op[2], &op[3], &op[4], &op[5]);
    int8_t cfg4 = (int8_t)c->flags[4];
    int32_t L = m->L;
    const int32_t ythr = scene->vec[3], s4 = scene->vec[4], s5 = scene->vec[5];

    /* fcn.102aece0 with the FOS pointer (0x102afaf9..0x102afb51, 0x102b07e7..0x102b07fb): the dmin-luma count, stored as
     * the word scene+0x16 (0x102b2169), and fcn.102b7440's tail (0x102b7d06..0x102b7d58): its weight, word scene+0x18.
     * Without the FOS pointer (mode 0) the count is 0. */
    int32_t count = 0, s2 = 0;
    if (mode) {
        int32_t sum = pkc_wrap32((int64_t)pkc_sx16(fos->dmin[2]) + pkc_sx16(fos->dmin[1]) + pkc_sx16(fos->dmin[0]));
        int32_t yd = pkc_bias_div(pkc_wrap32((int64_t)sum * 100000), 0x1524A, 0x2A495);
        int32_t thr = pkc_wrap32((int64_t)par_w(c, cfg4 == 1 ? 18 : 19) - op[3] + yd);
        for (int i = 0; i < N; i++) if ((int64_t)pkc_sx16(m->Yband[i]) - op[3] < thr) count++;
        count = pkc_sx16(count);
    }
    {
        int32_t t0 = par_w(c, cfg4 == 1 ? 0 : 2), t1 = par_w(c, cfg4 == 1 ? 1 : 3);
        if (t0 == 0) s2 = 1000;
        else if (count <= t0) s2 = 0;
        else {
            if (t1 == 0) return PK_E_ARG;                   /* Kodak: #DE */
            s2 = pkc_sx16(pkc_half_round_div(pkc_wrap32((int64_t)(count - t0) * 1000), t1));
        }
    }
    out->count = count;
    out->s2 = s2;

    /* FUN_1028ae00 */
    int32_t r1sq = pkc_wrap32((int64_t)par_w(c, 10) * par_w(c, 10)), r2sq = pkc_wrap32((int64_t)par_w(c, 11) * par_w(c, 11));
    int32_t lim = par_w(c, 24), nmin = par_w(c, 9), s3 = par_w(c, 17), p13 = par_w(c, 13);
    if ((c->flagsword & 0x2000) != 0) {                    /* fcn.1028b8d0 0x1028bfcb: no weight table (0x1028ae88) */
        out->out4 = s4; out->out8 = s5; out->flag = 0xcb;
        for (int k = 0; k < 3; k++) out->p15[k] = op[3 + k];
        goto triple;
    }
    if (cfg4 < 0) r1sq = 4000000;                           /* 0x1028aec5 */
    int16_t gmS = 0, gmO = 0, ilS = 0, ilO = 0;
    int32_t l5c = 0, l58 = 0;
    if (mode == 0) {
        out->flag = 200;
        for (int k = 0; k < 3; k++) out->p15[k] = op[3 + k];
    } else {
        int16_t gm = pkc_sx16(fos->gm_slope), il = pkc_sx16(fos->ill_slope);
        if (gm > lim || gm < -lim || il > lim || il < -lim) {   /* 0x1028af2e..0x1028af4d: the slope-limit fallback */
            gmO = pkc_sx16((int64_t)pkc_sx16(fos->order_fpo[1]) - op[4]);   /* word subtracts (0x1028af72 / 0x1028af7e) */
            ilO = pkc_sx16((int64_t)pkc_sx16(fos->order_fpo[2]) - op[5]);
            out->flag = 100;
        } else {
            gmS = gm; gmO = pkc_sx16(fos->gm_off); ilS = il; ilO = pkc_sx16(fos->ill_off);
            out->flag = 0;
        }
        int8_t f3 = (int8_t)c->flags[3], f2 = (int8_t)c->flags[2];   /* 0x1028af92..0x1028b011: DAT_1069c0b8 / DAT_1069b080 */
        if ((f3 == 3 || f3 == 2 || f3 == 1) && (f2 == 0 || (f2 == 1 && cfg4 == 1)))
            return PK_E_VENDOR_DATA;                        /* the alternative tables are not extracted (R12) */
        int32_t base = pkc_wrap32((int64_t)p13 + L);
        l5c = pkc_wrap32((int64_t)pkc_wrap32((int64_t)gmS * base) / 10000 + gmO);
        l58 = pkc_wrap32((int64_t)pkc_wrap32((int64_t)ilS * base) / 10000 + ilO);
        out->p15[0] = base; out->p15[1] = pkc_wrap32((int64_t)op[4] + l5c); out->p15[2] = pkc_wrap32((int64_t)op[5] + l58);
    }
    int32_t sa1 = 0, sa2 = 0, ss1 = 0, ss2 = 0, nsel = 0;
    for (int i = 0; i < N; i++) {                           /* 0x1028b0b8..0x1028b247 */
        int16_t c1 = pkc_sx16((int64_t)pkc_sx16(m->C1band[i]) - op[4]);   /* word subtracts of the opening's low words */
        int16_t c2 = pkc_sx16((int64_t)pkc_sx16(m->C2band[i]) - op[5]);
        int16_t y = pkc_sx16((int64_t)pkc_sx16(m->Yband[i]) - op[3]);
        int32_t a = c1, b = c2;
        if (mode) {
            a = pkc_wrap32((int64_t)c1 - pkc_wrap32((int64_t)gmS * y) / 10000 - gmO);
            b = pkc_wrap32((int64_t)c2 - pkc_wrap32((int64_t)ilS * y) / 10000 - ilO);
        }
        /* the cell: trunc(x / 16) + (n - 1) / 2, compared as a word (0x1028b16a..0x1028b18f) */
        int16_t gx = pkc_sx16((int64_t)(a / 16) + (PKC_SFS_NX - 1) / 2), gy = pkc_sx16((int64_t)(b / 16) + (PKC_SFS_NY - 1) / 2);
        if (gx < 0) gx = 0;
        if (gx >= PKC_SFS_NX) gx = PKC_SFS_NX - 1;
        if (gy < 0) gy = 0;
        if (gy >= PKC_SFS_NY) gy = PKC_SFS_NY - 1;
        int32_t w = pref->sfs[gy + gx * PKC_SFS_NY];        /* movsx byte */
        if (nsel < nmin) { sa1 = pkc_wrap32((int64_t)sa1 + pkc_wrap32((int64_t)w * a)); sa2 = pkc_wrap32((int64_t)sa2 + pkc_wrap32((int64_t)w * b)); }
        int32_t sq = pkc_wrap32((int64_t)pkc_wrap32((int64_t)b * b) + pkc_wrap32((int64_t)a * a));
        if ((scene->mask[i] == 1 && sq < r1sq) || (y > ythr && sq < r2sq)) {
            nsel++;
            ss1 = pkc_wrap32((int64_t)ss1 + pkc_wrap32((int64_t)w * a)); ss2 = pkc_wrap32((int64_t)ss2 + pkc_wrap32((int64_t)w * b));
        }
    }
    out->nsel = nsel;
    int32_t d = nsel < nmin ? N * 100 : pkc_wrap32((int64_t)nsel * 100);
    if (d == 0) return PK_E_ARG;                            /* Kodak: #DE */
    int32_t u = pkc_wrap32((int64_t)pkc_half_round_div(nsel < nmin ? sa1 : ss1, d) + l5c);
    int32_t v = pkc_wrap32((int64_t)pkc_half_round_div(nsel < nmin ? sa2 : ss2, d) + l58);
    out->u = u; out->v = v;
    if (mode == 0) { out->out4 = u; out->out8 = v; goto triple; }
    {   /* 0x1028b2ca..0x1028b49c: the blend with the FOS dmin chroma and the whole-frame means (slots 4 / 5) */
        int32_t dr = pkc_sx16(fos->dmin[0]), dg = pkc_sx16(fos->dmin[1]), db = pkc_sx16(fos->dmin[2]);
        int32_t c1d = pkc_wrap32((int64_t)pkc_bias_div(pkc_wrap32((int64_t)pkc_wrap32(2 * (int64_t)dg - dr - db) * 100000), 0x1DE6A, 0x3BCD5) - op[4]);
        int32_t c2d = pkc_wrap32((int64_t)pkc_bias_div(pkc_wrap32((int64_t)pkc_wrap32((int64_t)db - dr) * 100000), 0x11436, 0x2286D) - op[5]);
        int32_t k1 = 1000 - s2, k2 = pkc_wrap32((int64_t)(100 - s3) * s2);
        out->out4 = pkc_wrap32((int64_t)pkc_bias_div(pkc_wrap32((int64_t)k2 * c1d), 50000, 100000) +
                           pkc_bias_div(pkc_wrap32((int64_t)pkc_wrap32((int64_t)s4 * s3) * s2), 50000, 100000) + pkc_bias_div(pkc_wrap32((int64_t)k1 * u), 500, 1000));
        out->out8 = pkc_wrap32((int64_t)pkc_bias_div(pkc_wrap32((int64_t)k2 * c2d), 50000, 100000) +
                           pkc_bias_div(pkc_wrap32((int64_t)pkc_wrap32((int64_t)s5 * s3) * s2), 50000, 100000) + pkc_bias_div(pkc_wrap32((int64_t)k1 * v), 500, 1000));
    }
triple:
    /* fcn.1028b8d0 0x1028c291..: the triple as words (scene+0x38a2 words 0..2); the flag is its word 0x2f */
    out->triple[0] = pkc_sx16((int64_t)L + op[3]);
    out->triple[1] = pkc_sx16((int64_t)op[4] + out->out4);
    out->triple[2] = pkc_sx16((int64_t)op[5] + out->out8);
    return PK_OK;
}

/* ------------------------------------------------------------------------------------------------ Preference */

static const double I3 = 0.5773502717125849;    /* 0x105a6f38 */
static const double I6 = 0.40824829759439285;   /* 0x105a6f30 */
static const double I2 = 0.7071067623730956;    /* 0x105a6f28 */
static const double S23 = 0.8164965951887857;   /* 0x105a6f40 */
static const double ONE3 = 0.3333333333333333;  /* 0x105943c0 */
static const double MILLI = 0.0010000000474974513;   /* 0x105a0800: the float 0.001 */

/* 0x1028cc33 / 0x1028cc79: back to RGB; 0x1028ccc0 / 0x1028cce7: _ftol word stores */
static void inv_rgb(double y, double u, double v, int16_t o[3]) {
    double ys = y * I3, d = ys - u * I6, vs = v * I2;
    o[0] = pkc_sx16(ftol2(d - vs));
    o[1] = pkc_sx16(ftol2(u * S23 + ys));
    o[2] = pkc_sx16(ftol2(vs + d));
}
pk_status pkc_preference_shift(const int32_t triple[3], const pkc_sba_pref *pref, int mode, int16_t shift[3], int16_t anchor[3]) {
    if (!triple || !pref || !shift) return PK_E_ARG;
    /* 0x1028c78e..0x1028c7a4: only the low byte counts (lo = mode & 0x0f, hi = mode & 0xf0); their non-zero arms are not
     * ported (R24) */
    if (mode & 0xFF) return PK_E_UNSUPPORTED;
    const int16_t *bl = pref->blob;
    /* 0x1028c7d4..0x1028c8a5: the opening (blob fpo) */
    double v0 = bl[0], v1 = bl[1], v2 = bl[2];
    double op_y = ((v2 + v1) + v0) * I3, op_u = ((v1 + v1) - v0 - v2) * I6, op_v = (v2 - v0) * I2;
    /* mode 0: the aims are the triple's words (0x1028c983, 0x1028ca2f) */
    double aim_y = pkc_sx16(triple[0]), aim_u = pkc_sx16(triple[1]), aim_v = pkc_sx16(triple[2]);
    double d_u = aim_u - op_u, d_v = aim_v - op_v;
    double w1e = bl[15];                                    /* pcls (0x1028ca6b keeps a float32 copy: exact for a word) */
    double d_y = (w1e + aim_y) - op_y;
    /* 0x1028ca7b: d_y <= 0 takes neu (+0x0c), else neo (+0x12); helper 0x1028c540 */
    const int16_t *hr = bl + (d_y > 0.0 ? 9 : 6);
    double hm = (((double)hr[1] + hr[0]) + hr[2]) * MILLI * ONE3;
    double h1 = ((double)hr[1] * MILLI - hm) * I2;
    double h2 = ((double)hr[2] * MILLI - (double)hr[0] * MILLI) * I6;
    double scale = (double)bl[24] * MILLI;                  /* cmm */
    double p0 = bl[3], p1 = bl[4], p2 = bl[5];              /* fpa */
    double a_y = ((p2 + p1) + p0) * I3, a_u = ((p1 + p1) - p0 - p2) * I6, a_v = (p2 - p0) * I2;
    /* 0x1028cb27..0x1028cbad: each delta _ftol'd (eax, read back with fild dword) before use */
    double i_dy = (double)pkc_wrap32(ftol2(d_y));
    double y_r = ((hm * i_dy) + a_y) + op_y;
    double i_du = (double)pkc_wrap32(ftol2(d_u));
    double u_r = (((i_du * scale) + (i_dy * h1)) + a_u) + op_u;
    double i_dv = (double)pkc_wrap32(ftol2(d_v));
    double v_r = (((i_dv * scale) + (i_dy * h2)) + a_v) + op_v;
    /* 0x1028cbb1..0x1028cc1b: s' = clamp(lim46 - (y_r - pcls), lo, hi): fcom lo + test ah,5 / jp takes lo only when
     * below; fcom hi + test ah,0x41 / jne takes hi only when above (an unordered s' would be kept: unreachable, every
     * input is a finite word) */
    double lim = bl[35], lo = bl[33], hi = bl[34];
    double s = lim - (y_r - w1e);
    if (s < lo) s = lo;
    else if (s > hi) s = hi;
    if (anchor) inv_rgb(lim - s, u_r, v_r, anchor);
    inv_rgb(s, -u_r, -v_r, shift);
    return PK_OK;
}

/* ------------------------------------------------------------------------------------------------ setShifts (1,2) */

static int32_t axis_y(int32_t s) { return pkc_bias_div(pkc_wrap32((int64_t)s * 100000), 0x1524A, 0x2A495); }
static int32_t axis_c1(int32_t s, int32_t k) { return pkc_bias_div(pkc_wrap32((int64_t)s * k), 0x1DE6A, 0x3BCD5); }
static int32_t axis_c2(int32_t s) { return pkc_bias_div(pkc_wrap32((int64_t)s * 100000), 0x11436, 0x2286D); }
/* fcn.10100a37 reads the scpLut as one flat table (base pointer + the per-band entry count 4096 from the LUT object,
 * [esp+0x28] / [esp+0x2c]): base[ar], base[4096 + ag], base[8192 + ab] with the words ar = 1550 - A as signed indices and no
 * bounds check. Inside the 3 x 4096 table an index off its band reads the neighbouring band (Kodak-pinned by pokes,
 * truth/t22 sspoke_*: docs/re/26 section 4); outside the table Kodak reads whatever its heap holds, which the port
 * refuses (PK_E_UNSUPPORTED). pkc_lut3 is exactly this flat table. */
typedef char pkc_lut3_is_flat_table[sizeof(pkc_lut3) == 3 * 4096 * sizeof(int16_t) ? 1 : -1];
pk_status pkc_setshifts_12(const int16_t A[3], const int16_t B[3], const pkc_lut3 *lut, int16_t out[3]) {
    if (!A || !B || !lut || !out) return PK_E_ARG;
    /* 0x10100a40..0x10100ad0: Y of the scpLut at 1550 - A (planar, 4096 entries per band) */
    int16_t ar = pkc_sx16(1550 - A[0]), ag = pkc_sx16(1550 - A[1]), ab = pkc_sx16(1550 - A[2]);
    const int16_t *flat = &lut->t[0][0];
    const int32_t fr = ar, fg = 4096 + ag, fb = 8192 + ab;
    if (fr < 0 || fr >= 3 * 4096 || fg < 0 || fg >= 3 * 4096 || fb < 0 || fb >= 3 * 4096) return PK_E_UNSUPPORTED;
    int16_t lr = flat[fr], lg = flat[fg], lb = flat[fb];
    int32_t y = axis_y(pkc_wrap32((int64_t)lb + lg + lr));
    /* 0x10100ae0..0x10100b86: C1 / C2 of 1550 - B */
    int16_t br = pkc_sx16(1550 - B[0]), bg = pkc_sx16(1550 - B[1]), bb = pkc_sx16(1550 - B[2]);
    int32_t c1 = axis_c1(pkc_wrap32((int64_t)bg + bg - bb - br), 100000), c2 = axis_c2(pkc_wrap32((int64_t)bb - br));
    /* 0x10100b76.., 0x10100651.., 0x10100ed5..: R = Yc - C2c - C1c, G = C1(x2)c + Yc, B = C2c - C1c + Yc; out = 1550 - RGB */
    int32_t yc = axis_y(y), c1c = axis_c1(c1, 100000), c2c = axis_c2(c2), c1x2 = axis_c1(c1, 200000);
    int32_t r = pkc_wrap32((int64_t)yc - c2c - c1c), g = pkc_wrap32((int64_t)c1x2 + yc), b = pkc_wrap32((int64_t)c2c - c1c + yc);
    out[0] = pkc_sx16(1550 - (int64_t)r); out[1] = pkc_sx16(1550 - (int64_t)g); out[2] = pkc_sx16(1550 - (int64_t)b);
    return PK_OK;
}
