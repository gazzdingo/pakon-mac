/* SBA measuring pass: port of lab/reference pakon_sba_measure.py (fcn.102aece0 as far as the L term reads it),
 * pakon_orderfpo_vecpack.py (fcn.102b7440 + the fcn.1028b8d0 tail) and the L-term driver of sbamode2.scene_inputs.
 * Integer arithmetic throughout; Python's // never occurs here -- every division is the DLL's idiv (truncation). */
#include "data/diag.h"
#include "analysis/sba_measure.h"
#include "analysis/kint.h"
#include "data/kodak_text.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define N PKC_GRID_N
#define NBANDS 6
#define A6_LEN 0x0B00
#define A7_LEN 0x28

/* ---------------------------------------------------------------- helpers */

static int32_t ld32(const uint8_t *b, int off) {
    return (int32_t)((uint32_t)b[off] | (uint32_t)b[off + 1] << 8 | (uint32_t)b[off + 2] << 16 | (uint32_t)b[off + 3] << 24);
}
static void st32(uint8_t *b, int off, int64_t v) {
    uint32_t u = (uint32_t)pkc_wrap32(v);
    b[off] = (uint8_t)u; b[off + 1] = (uint8_t)(u >> 8); b[off + 2] = (uint8_t)(u >> 16); b[off + 3] = (uint8_t)(u >> 24);
}
static int16_t ld16(const uint8_t *b, int off) { return (int16_t)(uint16_t)(b[off] | b[off + 1] << 8); }
static void st16(uint8_t *b, int off, int v) { b[off] = (uint8_t)v; b[off + 1] = (uint8_t)(v >> 8); }

/* x86 idiv: truncation toward zero; #DE on d == 0 or an out-of-range quotient -> nonzero return */
static int idiv_chk(int64_t n, int64_t d, int32_t *q) {
    if (d == 0) return 1;
    int64_t r = n / d;
    if (r < INT32_MIN || r > INT32_MAX) return 1;
    *q = (int32_t)r;
    return 0;
}
static int64_t tdiv(int64_t n, int64_t d) { return n / d; }   /* d != 0 by construction at every call */

/* ---------------------------------------------------------------- opening axes */

/* imul magic; sar edx,N; add (edx>>31) (pakon_fos._msvc_magic_div) */
static int32_t magic_div(int64_t value, int32_t magic, int sar) {
    int64_t prod = (int64_t)pkc_wrap32(value) * (int64_t)magic;
    int32_t edx = (int32_t)(prod >> 32);
    edx >>= sar;
    return edx + (edx < 0 ? 1 : 0);
}
/* 32-bit imul by 100000, sign test of the wrapped product, +-bias (0x1028b979..: Kodak's registers are 32-bit) */
static int64_t biased_scale(int64_t term, int64_t bias) {
    int32_t t = pkc_wrap32(term * 100000);
    return t >= 0 ? (int64_t)t + bias : (int64_t)t - bias;
}
void pkc_sba_axes(int r, int g, int b, int32_t *y, int32_t *c1, int32_t *c2) {
    r = pkc_sx16((uint32_t)r); g = pkc_sx16((uint32_t)g); b = pkc_sx16((uint32_t)b);
    *y = magic_div(biased_scale(r + g + b, 0x1524A), 0x306E8227, 0xF);
    *c1 = magic_div(biased_scale(2 * g - b - r, 0x1DE6A), 0x111F883D, 0xE);
    *c2 = magic_div(biased_scale(b - r, 0x11436), 0x3B510A6F, 0xF);
}

/* ---------------------------------------------------------------- ctx */

static pk_status read_exact(const char *path, void *buf, size_t n) {
    FILE *f = pkc_fopen(path, "rb");
    if (!f) return PK_E_VENDOR_DATA;
    size_t got = fread(buf, 1, n, f);
    int extra = fgetc(f);
    fclose(f);
    return got == n && extra == EOF ? PK_OK : PK_E_VENDOR_DATA;
}

static pk_status load_tables(const char *derived_root, pkc_sba_ctx *c) {
    static const char *bytes[5] = { "105a8e10", "105a94d0", "105a9170", "105a9830", "105a9b90" };
    static const char *dwords[4] = { "1069e5a0", "106a00a0", "1069f320", "106a0e20" };
    char path[1100];
    for (int i = 0; i < 5; i++) {
        snprintf(path, sizeof path, "%s/imau_tables/sel_byte_%s.bin", derived_root, bytes[i]);
        pk_status st = read_exact(path, c->sel_byte[i], N);
        if (st != PK_OK) return st;
    }
    for (int i = 0; i < 4; i++) {
        uint8_t raw[4 * N];
        snprintf(path, sizeof path, "%s/imau_tables/sel_dword_%s.bin", derived_root, dwords[i]);
        pk_status st = read_exact(path, raw, sizeof raw);
        if (st != PK_OK) return st;
        for (int k = 0; k < N; k++) c->sel_dword[i][k] = (uint32_t)ld32(raw, 4 * k);
    }
    uint8_t g[4];
    snprintf(path, sizeof path, "%s/imau_tables/hue_wb_global_106bc820.bin", derived_root);
    pk_status st = read_exact(path, g, 4);
    if (st != PK_OK) return st;
    c->hue_wb_global = (uint32_t)ld32(g, 0);
    snprintf(path, sizeof path, "%s/imau_tables/en_static_1069d0f0.bin", derived_root);
    return read_exact(path, c->en_static, 0x2C);        /* past 0x2c: zero (memset by ctx_load) */
}

/* fcn.1028b8d0 0x1028bc..: which gate table, par quad and mode the flag bytes pick */
static pk_status derive_mode(pkc_sba_ctx *c) {
    int c1 = (int8_t)c->flags[1], c2 = (int8_t)c->flags[2], c3 = (int8_t)c->flags[3], c4 = (int8_t)c->flags[4];
    c->sel = (uint16_t)(int16_t)c1;
    if (c1 == -1 || c1 == -2 || c1 == -3 || c1 == -4) { c->mode = 1; c->en_off = 0; }
    else if (c2 == -1 || c2 == -2) { c->mode = 2; c->en_off = 0x2C; }
    else if (c3 == 0 || c4 == 1 || c2 == 0) { c->mode = 8; c->en_off = 0x84; }
    else if (c2 == 1) { c->mode = 4; c->en_off = 0xB0; }
    else return PK_E_VENDOR_DATA;                   /* the DLL reads an uninitialised local here */
    return PK_OK;
}

pk_status pkc_sba_ctx_load(const char *vendor_root, const char *derived_root, pkc_sba_ctx *out) {
    if (!vendor_root || !derived_root || !out) return PK_E_ARG;
    char dpi[1100];
    pk_status st = pkc_vendor_path(vendor_root, PKC_SBA_DPI_DEFAULT, dpi, sizeof dpi);
    if (st != PK_OK) { memset(out, 0, sizeof *out); return st; }
    return pkc_sba_ctx_load_dpi(vendor_root, derived_root, dpi, out);
}

pk_status pkc_sba_ctx_load_dpi(const char *vendor_root, const char *derived_root, const char *dpi, pkc_sba_ctx *out) {
    if (!vendor_root || !derived_root || !dpi || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    char path[1100], rel[256];
    pkc_kt *kt = NULL;
    pk_status st = pkc_kt_load(dpi, &kt);
    if (st != PK_OK) return st == PK_E_FORMAT ? st : PK_E_VENDOR_DATA;
    double fpo[3];
    const char *pc = pkc_kt_str(kt, "pcode");
    if (pkc_kt_num(kt, "fpo", fpo, 3) != 3 || !pc || strchr(pc, '/') || strlen(pc) > 100) {
        pkc_kt_free(kt);
        return PK_E_VENDOR_DATA;
    }
    double w3[3];
    /* Kodak's dpi parser matches keys case-insensitively ("nonflashadj" 0x102ad4d7); the file spells them "nonFlashAdj" */
    if (pkc_kt_num(kt, "pcwf", &w3[0], 1) != 1 || pkc_kt_num(kt, "ix_pcwf", &w3[1], 1) != 1 ||
        (pkc_kt_num(kt, "nonFlashAdj", &w3[2], 1) != 1 && pkc_kt_num(kt, "nonflashadj", &w3[2], 1) != 1)) {
        pkc_kt_free(kt);
        return PK_E_VENDOR_DATA;
    }
    double fs[2];      /* fog / splicePct: analyzePass1's splice crop (Task 21; every shipped SBA dpi has both) */
    if (pkc_kt_num(kt, "fog", &fs[0], 1) != 1 || pkc_kt_num(kt, "splicePct", &fs[1], 1) != 1) {
        pkc_kt_free(kt);
        return PK_E_VENDOR_DATA;
    }
    out->fog = (int16_t)(int)fs[0]; out->splice_pct = (int16_t)(int)fs[1];
    for (int i = 0; i < 3; i++) out->opening[i] = (int16_t)(int)fpo[i];
    out->pcwf = (int16_t)(int)w3[0]; out->ix_pcwf = (int16_t)(int)w3[1]; out->non_flash_adj = (int16_t)(int)w3[2];
    snprintf(rel, sizeof rel, "anselinstalldir/dataPathItems/sba/Pcode/%s", pc);
    pkc_kt_free(kt);
    st = pkc_vendor_path(vendor_root, rel, path, sizeof path);
    if (st == PK_OK) st = pkc_sba_pcode_load(path, out->params, &out->prog);
    /* 0x1028b91a..0x1028b94e: pcwf / ix_pcwf outside [params[0x104], params[0x106]] make Kodak's sba core fail with 0x18bd on
     * every scene. That is a property of the dpi + pcode pair, not of an image: reported at load (RE 27 section 3) */
    if (st == PK_OK) {
        int lo_r = ld16(out->params, 0x104), hi_r = ld16(out->params, 0x106);
        if (out->pcwf < lo_r || out->pcwf > hi_r || out->ix_pcwf < lo_r || out->ix_pcwf > hi_r) st = PK_E_VENDOR_DATA;
    }
    if (st == PK_OK) st = load_tables(derived_root, out);
    if (st == PK_OK) {
        static const uint8_t flags[8] = { 0xFE, 0xFE, 0xFE, 0xFF, 0xFF, 0xFE, 0x00, 0xFE };
        memcpy(out->flags, flags, sizeof flags);
        out->flagsword = 0;
        st = derive_mode(out);
    }
    if (st != PK_OK) pkc_sba_ctx_free(out);
    return st;
}

pk_status pkc_sba_ctx_set_flags(pkc_sba_ctx *c, const uint8_t flags[8], uint16_t flagsword) {
    if (!c || !flags || ((flagsword & 0x800) && (flagsword & 0x1000))) return PK_E_ARG;
    pkc_sba_ctx t = *c;                      /* shallow copy: only the scalar fields change */
    memcpy(t.flags, flags, 8); t.flagsword = flagsword;
    pk_status st = derive_mode(&t);
    if (st != PK_OK) return st;
    c->mode = t.mode; c->sel = t.sel; c->en_off = t.en_off;
    memcpy(c->flags, flags, 8); c->flagsword = flagsword;
    return PK_OK;
}

void pkc_sba_ctx_free(pkc_sba_ctx *ctx) {
    if (!ctx) return;
    pkc_sba_prog_free(&ctx->prog);
}

/* ---------------------------------------------------------------- pass configuration */

typedef struct {
    int mode;                              /* *(scene+0x5d2*2): par quad, slot 730 */
    int mode_pack;                         /* fcn.102aece0 arg5 = fcn.1028b8d0 arg4 */
    const uint8_t *en;                     /* 64-byte zone gate table */
} pkc_pass_cfg;

/* fcn.1028b8d0 0x1028bc..: arg4 == 1 selects the static gate table and mode 1 (0x1028bcab..), otherwise the flags pick
 * the pcode table / mode (derive_mode); arg4 is forwarded unchanged as fcn.102aece0's arg5 (0x1028bdbc / 0x1028be08). */
static void pass_config(const pkc_sba_ctx *c, int pass, pkc_pass_cfg *pc) {
    pc->mode_pack = pass;
    if (pass == PKC_SBA_PASS1) { pc->mode = 1; pc->en = c->en_static; }
    else { pc->mode = c->mode; pc->en = c->params + c->en_off; }
}

static void sel_tables(const pkc_sba_ctx *c, const uint8_t **bytetab, const uint32_t **dwtab) {
    int s = c->sel & 0xFFFF, b = 4, d = 2;                     /* the 0x102af210 default arm */
    if (s <= 7) { b = d = s & 3; }
    *bytetab = c->sel_byte[b]; *dwtab = c->sel_dword[d];
}

/* ---------------------------------------------------------------- the hue wheel and the mask */

/* (hue_lo, hue_hi, chroma_lo, chroma_hi) offsets into par, by mode (0x102af145) */
static int mode_params(int mode, int off[4]) {
    static const int t[9][4] = { {0}, { 0x52, 0x54, 0x4E, 0x50 }, { 0x4A, 0x4C, 0x46, 0x48 }, {0},
                                 { 0x42, 0x44, 0x3E, 0x40 }, {0}, {0}, {0}, { 0x3A, 0x3C, 0x36, 0x38 } };
    if (mode != 1 && mode != 2 && mode != 4 && mode != 8) return 1;
    memcpy(off, t[mode], sizeof t[mode]);
    return 0;
}

/* The 864-byte selection mask (obj+0xc20), both stages, updated in place: mask enters as the scene object's previous
 * mask (what stage 2 of a FOS pass reads, and what survives where the DLL stores nothing). slot479 = scene+0x7b8 as
 * the previous pass left it. */
static pk_status pkc_selection_mask(const int32_t *im, const int32_t off[NBANDS], const pkc_sba_ctx *c,
                                    const pkc_pass_cfg *pc, int32_t slot479, uint8_t *mask) {
    const uint8_t *en = pc->en, *par = c->params + 0xDC;
    const uint8_t *tab_a; const uint32_t *tab_b;
    sel_tables(c, &tab_a, &tab_b);
    if (!(en[0x0E] || (en[0x0F] & 0x40) || (en[0x14] & 0x40))) return PK_OK;     /* je 0x102b124e */
    int mo[4];
    if (mode_params(pc->mode, mo)) return PK_E_VENDOR_DATA;                      /* 0x102b4ca3: ret 0x189c */
    int a5 = pc->mode_pack & 0xFFFF;
    int thr = ld16(par, 0x0C);
    int hue_lo = ld16(par, mo[0]), hue_hi = ld16(par, mo[1]);
    int32_t c_lo = pkc_wrap32((int64_t)ld16(par, mo[2]) * ld16(par, mo[2]));
    int32_t c_hi = pkc_wrap32((int64_t)ld16(par, mo[3]) * ld16(par, mo[3]));
    int bias = ld16(par, 0x56);
    for (int idx = 0; idx < N; idx++) {
        int32_t band[NBANDS];
        for (int p = 0; p < NBANDS; p++) band[p] = pkc_wrap32((int64_t)im[N * p + idx] - off[p]);
        int a = tab_a[idx];
        if (a5 != 2) {                                  /* stage 1 (0x102b09ed: arg5 == 2 skips it): local contrast on plane 3 */
            if (a == 0) mask[idx] = 0;
            else {
                int base = idx + 2555;                  /* 0x13f6/2: plane 3 centre minus a row and a column */
                int32_t mn = im[base], mx = im[base];
                for (int k = 0; k < 3; k++)
                    for (int row = 0; row < 3 * 36; row += 36) {
                        int32_t v = im[base + row + k];
                        if (v < mn) mn = v;
                        else if (v > mx) mx = v;
                    }
                mask[idx] = (uint8_t)((int64_t)mx - mn > thr ? 1 : 0);
            }
        }
        if (a5 == 1 || a == 0) continue;                /* stage 2: the hue/chroma window sets bit 1 */
        uint8_t b = mask[idx];
        if (b == 1) continue;
        if (c->hue_wb_global) return PK_E_VENDOR_DATA;  /* white-balanced hue arm 0x102b0b15: dead in the shipped DLL */
        int32_t chroma2 = pkc_wrap32((int64_t)band[4] * band[4] + (int64_t)band[5] * band[5]);
        int h = pkc_hue120(band[0], band[1], band[2]);
        if (band[3] < pkc_wrap32((int64_t)slot479 + bias)) continue;
        if (h <= hue_lo || h >= hue_hi) continue;
        if (chroma2 <= c_lo || chroma2 >= c_hi) continue;
        mask[idx] = (uint8_t)(b | 2);
    }
    return PK_OK;
}

/* ---------------------------------------------------------------- statistics blocks */

static int bank_base(int n) { return 0x120 * (n / 2) + 0x90 * (n % 2); }

static void acc_bank(uint8_t *A6, const uint8_t *en, int n, const int32_t band[NBANDS]) {
    int gate = en[n];
    if (!gate) return;
    int b = bank_base(n);
    for (int p = 0; p < NBANDS; p++)
        if (gate & (1 << p)) {
            int32_t v = band[p];
            if (ld32(A6, b + 4 * p) > v) st32(A6, b + 4 * p, v);
            if (ld32(A6, b + 0x18 + 4 * p) < v) st32(A6, b + 0x18 + 4 * p, v);
            st32(A6, b + 0x30 + 4 * p, (int64_t)ld32(A6, b + 0x30 + 4 * p) + v);
        }
}

/* index of the lowest set bit of x within [lo, hi), or -1 */
static int lowest_bit(uint32_t x, int lo, int hi) {
    for (int k = lo; k < hi; k++) if (x & (1u << k)) return k;
    return -1;
}

static void sample_bands(const int32_t *im, const int32_t off[NBANDS], int idx, int32_t band[NBANDS]) {
    for (int p = 0; p < NBANDS; p++) band[p] = pkc_wrap32((int64_t)im[N * p + idx] - off[p]);
}

/* A6 14-bank min/max/sum region (pakon_sba_measure.measure_bank_block) */
static void pkc_measure_bank_block(uint8_t *A6, const int32_t *im, const int32_t off[NBANDS], const uint8_t *en,
                                   const uint32_t *dw) {
    for (int n = 0; n < 14; n++) {
        if (!en[n]) continue;
        int b = bank_base(n);
        for (int j = 0; j < 6; j++) { st32(A6, b + 4 * j, 10000); st32(A6, b + 0x18 + 4 * j, -10000); }
    }
    static const int rng[3][2] = { {0, 5}, {5, 9}, {9, 13} };
    for (int idx = 0; idx < N; idx++) {
        int32_t band[NBANDS];
        sample_bands(im, off, idx, band);
        acc_bank(A6, en, 0, band);
        for (int r = 0; r < 3; r++) {
            int k = lowest_bit(dw[idx], rng[r][0], rng[r][1]);
            if (k >= 0) acc_bank(A6, en, k + 1, band);
        }
        if (en[0x14] & 8) {
            /* row +0x48 [3] of bank 0 (A6+0x54, 0x102af..: local_c24) and of bank 5 (A6+0x324, local_954, taken when the
             * sample's lowest dword bit in 0..4 is 4): band3^2 >> 5, gated by en[0x14] & 8. The other banks' row +0x48
             * cells are not modelled. */
            int32_t sq = pkc_wrap32((int64_t)band[3] * band[3]) >> 5;
            st32(A6, 0x54, (int64_t)ld32(A6, 0x54) + sq);
            if (lowest_bit(dw[idx], 0, 5) == 4) st32(A6, 0x324, (int64_t)ld32(A6, 0x324) + sq);
        }
    }
}

typedef struct { int n_mask1, sum_sel, n_b4, sum_sel_b4, n_mask2; } pkc_hdr;

/* the whole-frame bank the L term reads, plus the four header counters (measure_whole_frame) */
static pkc_hdr pkc_measure_whole_frame(uint8_t *A6, const int32_t *im, const int32_t off[NBANDS], const uint8_t *mask,
                                       const uint8_t *en, const uint8_t *par, const uint8_t *bytetab, const uint32_t *dw) {
    const int WF = 0x7E0;
    int en0e = en[0x0E] | en[0x0F] << 8, lo = en0e & 0xFF, en14 = en[0x14];
    pkc_hdr h = { 0, 0, 0, 0, 0 };
    int par58 = ld16(par, 0x58);
    if (en0e != 0)
        for (int j = 0; j < 6; j++) { st32(A6, WF + 4 * j, 10000); st32(A6, WF + 0x18 + 4 * j, -10000); }
    for (int idx = 0; idx < N; idx++) {
        if (mask[idx] == 2) {
            /* hue-window samples (0x102b11ba cmp al,2; 0x102b11c9..0x102b122d): the byte-table weight joins the same
             * sum as mask==1's (scene+8 -> slot 614, slot 719's divisor), and (Y + par[0x58]) * weight joins the sum
             * at A6+0x8AC that slot 719 divides. (The matching min/max rows and the count scene+0x1a are unmodelled.) */
            int32_t band[NBANDS];
            sample_bands(im, off, idx, band);
            int selbyte = (int8_t)bytetab[idx];
            h.n_mask2++; h.sum_sel += selbyte;
            st32(A6, 0x8AC, (int64_t)ld32(A6, 0x8AC) + pkc_wrap32((int64_t)(par58 + band[3]) * selbyte));
            continue;
        }
        if (mask[idx] != 1) continue;
        int32_t band[NBANDS];
        sample_bands(im, off, idx, band);
        int selbyte = (int8_t)bytetab[idx];
        int32_t ebp = pkc_wrap32((int64_t)band[3] * selbyte);
        h.n_mask1++; h.sum_sel += selbyte;
        for (int p = 0; p < NBANDS; p++)
            if (lo & (1 << p)) {
                int32_t v = band[p];
                if (ld32(A6, WF + 4 * p) > v) st32(A6, WF + 4 * p, v);
                if (ld32(A6, WF + 0x18 + 4 * p) < v) st32(A6, WF + 0x18 + 4 * p, v);
                st32(A6, WF + 0x30 + 4 * p, (int64_t)ld32(A6, WF + 0x30 + 4 * p) + v);
                if (p == 3) st32(A6, 0x8AC, (int64_t)ld32(A6, 0x8AC) + ebp);
            }
        if (en14 & 0x40) st32(A6, 0x834, (int64_t)ld32(A6, 0x834) + (pkc_wrap32((int64_t)band[3] * band[3]) >> 5));
        if (dw[idx] & 0x10) {
            st32(A6, 0x9CC, (int64_t)ld32(A6, 0x9CC) + ebp);
            h.n_b4++; h.sum_sel_b4 += selbyte;
        }
    }
    return h;
}

typedef struct { int nbins, bias, scale; int32_t *h; } hist_t;

static int bin_idx(int32_t v, const hist_t *h) {
    int64_t b = tdiv((int64_t)v + h->bias, h->scale);
    return b < 0 ? 0 : b > h->nbins - 1 ? h->nbins - 1 : (int)b;
}
static int32_t pkc_percentile(const hist_t *h, int k) {
    int64_t total = 0;
    for (int i = 0; i < h->nbins; i++) total += h->h[i];
    int target = pkc_sx16((uint32_t)tdiv(k * total + 50, 100) & 0xFFFF);
    int64_t cum = 0; int ecx = 0;
    if (target > 0)
        while (ecx < h->nbins) {
            cum += h->h[ecx]; ecx++;
            if (cum >= target) break;
        }
    return (int32_t)((int64_t)(ecx - 1) * h->scale - h->bias);
}
static int32_t pkc_mode(const hist_t *h) {
    int best_c = 0, best_i = 0;
    for (int i = 0; i < h->nbins; i++)
        if (h->h[i] > best_c) { best_c = h->h[i]; best_i = i; }
    return best_i * h->scale - h->bias;
}
static int32_t pkc_mean_ge2(const hist_t *h) {
    int64_t S = 0, C = 0;
    for (int i = 0; i < h->nbins; i++)
        if (h->h[i] >= 2) { C++; S += i; }
    if (C == 0) return 0;
    int64_t mean1000 = tdiv(S * 1000 + (C >> 1), C);
    int64_t x = mean1000 * h->scale;
    return (int32_t)(tdiv(x + (x >= 0 ? 500 : -500), 1000) - h->bias);
}

/* the four live histograms and the A3 / A4 / A5 entries the L term reads (build_histograms + measure_l_blocks) */
static void pkc_l_blocks(const int32_t *im, const int32_t off[NBANDS], const uint8_t *mask, const uint32_t *dw,
                         int32_t A3[75], int32_t A4[19], int32_t A5[9]) {
    int32_t h0[500], h8[400], h13[400], h14[400];
    memset(h0, 0, sizeof h0); memset(h8, 0, sizeof h8); memset(h13, 0, sizeof h13); memset(h14, 0, sizeof h14);
    hist_t H0 = { 500, 1000, 10, h0 }, H8 = { 400, 1300, 25, h8 }, H13 = { 400, 1300, 25, h13 }, H14 = { 400, 1300, 25, h14 };
    for (int idx = 0; idx < N; idx++) {
        int32_t b0 = pkc_wrap32((int64_t)im[idx] - off[0]), b3 = pkc_wrap32((int64_t)im[3 * N + idx] - off[3]);
        h0[bin_idx(b0, &H0)]++;
        h8[bin_idx(b3, &H8)]++;
        if (lowest_bit(dw[idx], 0, 5) == 4) h13[bin_idx(b3, &H13)]++;
        if (mask[idx] == 1) h14[bin_idx(b3, &H14)]++;
    }
    memset(A3, 0, 75 * sizeof *A3); memset(A4, 0, 19 * sizeof *A4); memset(A5, 0, 9 * sizeof *A5);
    A3[1] = pkc_percentile(&H8, 10);  A3[10] = pkc_percentile(&H8, 50); A3[18] = pkc_percentile(&H8, 90);
    A3[22] = pkc_percentile(&H14, 50); A3[26] = pkc_percentile(&H13, 10);
    A3[29] = pkc_percentile(&H0, 10); A3[52] = pkc_percentile(&H0, 95);
    A4[12] = pkc_mean_ge2(&H13); A4[13] = pkc_mean_ge2(&H0);
    A5[0] = pkc_mode(&H8);
}

/* ---------------------------------------------------------------- the vector (fcn.102b7440) */

typedef struct {
    int32_t *vec;
    uint8_t *known;
    uint8_t *A6;
    uint8_t *A7;
} pack_t;

static void mark(pack_t *k, int lo, int n, int v) { memset(k->known + lo, v, (size_t)n); }

/* The vector slots a bank / group packs are Kodak-exact (known) only when the port fills the A6 rows they copy: banks
 * whose gate byte is non-zero (a gated-off bank's A6 rows are uninitialised stack in Kodak -- pass 1's static gate table
 * enables only bank 0 -- Kodak-observed as junk in slots 544.. of pass-1 objects), and the whole-frame bank; row +0x48
 * and the scalars never are. */
static int pack_bank(pack_t *k, int i, int b, int cell) {
    int src = 0x120 * i + 0x90 * b, dst = 68 * i + 34 * b;
    int div = ld16(k->A7, 4 * i + 2 * b);
    for (int j = 0; j < 6; j++) {
        if (idiv_chk(ld32(k->A6, src + 0x30 + 4 * j), div, &k->vec[dst + j])) return 1;
        k->vec[dst + 6 + j] = ld32(k->A6, src + 4 * j);
        k->vec[dst + 12 + j] = ld32(k->A6, src + 0x18 + 4 * j);
        k->vec[dst + 18 + j] = ld32(k->A6, src + 0x30 + 4 * j);
        k->vec[dst + 24 + j] = ld32(k->A6, src + 0x48 + 4 * j);
    }
    k->vec[dst + 30] = ld32(k->A6, src + 0x7C);
    k->vec[dst + 31] = ld32(k->A6, src + 0x80);
    k->vec[dst + 32] = ld32(k->A6, src + 0x88);
    k->vec[dst + 33] = ld32(k->A6, src + 0x8C);
    mark(k, dst, 24, 1); mark(k, dst + 24, 10, 0);
    k->known[dst + 27] = (uint8_t)cell;                 /* row +0x48 [3] when it is one of the modelled cells */
    return 0;
}
static int pack_group(pack_t *k, int slot, int src, int div, int quad_slot, int quad_src, int kn, int cell) {
    for (int j = 0; j < 6; j++) {
        if (idiv_chk(ld32(k->A6, src + 4 * j), div, &k->vec[slot + j])) return 1;
        k->vec[slot + 6 + j] = ld32(k->A6, src - 0x30 + 4 * j);
        k->vec[slot + 12 + j] = ld32(k->A6, src - 0x18 + 4 * j);
        k->vec[slot + 18 + j] = ld32(k->A6, src + 4 * j);
        k->vec[slot + 24 + j] = ld32(k->A6, src + 0x18 + 4 * j);
    }
    k->vec[quad_slot + 0] = ld32(k->A6, quad_src + 0x00);
    k->vec[quad_slot + 1] = ld32(k->A6, quad_src + 0x04);
    k->vec[quad_slot + 2] = ld32(k->A6, quad_src + 0x0C);
    k->vec[quad_slot + 3] = ld32(k->A6, quad_src + 0x10);
    mark(k, slot, 24, kn); mark(k, slot + 24, 10, 0);
    k->known[slot + 27] = (uint8_t)cell;
    return 0;
}

/* fcn.102b7440 for mode_pack 1 (the mode-1 arm: 612 only past the groups) and the other values (mode_pack 0 / 2 are the
 * same arm). The scene+0x18 weight and the arg6 zero-guards it ends with feed no vector slot and are not computed. */
static pk_status pkc_vecpack(pack_t *k, int mode1, const uint8_t *en, const uint8_t *par, const pkc_hdr *hd,
                             const int32_t A3[75], const int32_t A4[19], const int32_t A5[9]) {
    int v10 = pkc_sx16((uint32_t)hd->n_mask1), v34 = pkc_sx16((uint32_t)hd->sum_sel), v3c = pkc_sx16((uint32_t)hd->n_b4),
        v38 = pkc_sx16((uint32_t)hd->sum_sel_b4);
    int32_t last = 0;
    if (!mode1) {
        static const int a3k[] = { 1, 10, 18, 22, 26, 29, 52 }, a4k[] = { 12, 13 };
        for (int a = 0; a < 75; a++) k->vec[616 + a] = A3[a];
        for (int a = 0; a < 19; a++) k->vec[691 + a] = A4[a];
        for (int a = 0; a < 9; a++) k->vec[710 + a] = A5[a];
        mark(k, 616, 103, 0);
        for (size_t a = 0; a < sizeof a3k / sizeof *a3k; a++) k->known[616 + a3k[a]] = 1;
        for (size_t a = 0; a < sizeof a4k / sizeof *a4k; a++) k->known[691 + a4k[a]] = 1;
        k->known[710] = 1;
        if (v10 > ld16(par, 0x0E)) {
            if (idiv_chk(ld32(k->A6, 0x8AC), v34, &last)) return PK_E_ARG;
        } else {
            if (idiv_chk(ld32(k->A6, 0x3C), ld16(k->A7, 0), &last)) return PK_E_ARG;
            for (int a = 0; a < 0x12; a++) st32(k->A6, 0x7E0 + 4 * a, ld32(k->A6, 4 * a));
            st16(k->A7, 0x1C, 0x360); st16(k->A7, 0x1E, 0x360);
            st16(k->A7, 0x20, ld16(k->A7, 0x0A)); st16(k->A7, 0x22, ld16(k->A7, 0x0A));
        }
    }
    for (int i = 0; i < 7; i++)
        for (int b = 0; b < 2; b++)
            if (en[2 * i + b] && pack_bank(k, i, b, ((i == 0 && b == 0) || (i == 2 && b == 1)) && (en[0x14] & 8))) return PK_E_ARG;
    if (ld16(en, 0x0E) != 0) {
        int high = v10 > ld16(par, 0x0E), alt = ld16(k->A7, 0x20) != 0, bad = 0;
        if (high) {
            bad |= pack_group(k, 476, 0x810, ld16(k->A7, 0x1C), 506, 0x85C, 1, 0);
            if (mode1) {
                if (alt) bad |= pack_group(k, 544, 0x930, ld16(k->A7, 0x20), 574, 0x97C, 0, 0);
                else bad |= pack_group(k, 544, 0x300, ld16(k->A7, 0x0A), 574, 0x34C, en[5] != 0, (en[5] != 0) && (en[0x14] & 8));
            } else {
                bad |= pack_group(k, 510, 0x8A0, ld16(k->A7, 0x1E), 540, 0x8EC, 0, 0);
                if (alt) {
                    bad |= pack_group(k, 544, 0x930, ld16(k->A7, 0x20), 574, 0x97C, 0, 0);
                    bad |= pack_group(k, 578, 0x9C0, ld16(k->A7, 0x22), 608, 0xA0C, 0, 0);
                } else {
                    bad |= pack_group(k, 544, 0x300, ld16(k->A7, 0x0A), 574, 0x34C, en[5] != 0, (en[5] != 0) && (en[0x14] & 8));
                    bad |= pack_group(k, 578, 0x300, ld16(k->A7, 0x0A), 608, 0x34C, en[5] != 0, (en[5] != 0) && (en[0x14] & 8));
                }
            }
        } else {
            bad |= pack_group(k, 476, 0x030, ld16(k->A7, 0x00), 506, 0x07C, en[0] != 0, (en[0] != 0) && (en[0x14] & 8));
            bad |= pack_group(k, 544, 0x300, ld16(k->A7, 0x0A), 574, 0x34C, en[5] != 0, (en[5] != 0) && (en[0x14] & 8));
            if (!mode1) {
                bad |= pack_group(k, 510, 0x030, ld16(k->A7, 0x00), 540, 0x07C, en[0] != 0, (en[0] != 0) && (en[0x14] & 8));
                bad |= pack_group(k, 578, 0x300, ld16(k->A7, 0x0A), 608, 0x34C, en[5] != 0, (en[5] != 0) && (en[0x14] & 8));
            }
        }
        if (bad) return PK_E_ARG;
        /* single A6 cells inside otherwise-unmodelled rows that the port does fill: A6+0x834 (band3^2>>5, gated by
         * en[0x14]&0x40) is row4[3] of the whole-frame group (slot 503), A6+0x8AC (band3*weight over mask 1 and 2) is
         * sum[3] of group 510 (slots 513, 531), A6+0x9CC (band3*weight over mask 1 & dword&0x10) is sum[3] of group 578
         * when the alt arm reads it (slots 581, 599) */
        if (high && (en[0x14] & 0x40)) k->known[503] = 1;
        if (high && !mode1) { k->known[513] = 1; k->known[531] = 1; }
        if (high && !mode1 && alt) { k->known[581] = 1; k->known[599] = 1; }
    }
    k->vec[612] = v10; k->known[612] = 1;                    /* 0x9CC: the only header slot of the mode-1 arm */
    if (mode1) return PK_OK;
    k->vec[614] = v34; k->vec[615] = v38; k->vec[613] = v3c; mark(k, 613, 3, 1);
    k->vec[719] = last; k->known[719] = 1;
    return PK_OK;
}

/* slots 720..732, fcn.1028b8d0's own stores (0x1028be82..0x1028bf79 and 0x1028bb05) */
void pkc_vec_tail(const pkc_sba_ctx *c, int mode, int32_t *vec, uint8_t *known) {
    const uint8_t *f = c->flags;
    /* fcn.1028b8d0 stores param_6[6..8] * 10 here. param_6 is the SBA parameter block the .dpi fills: R16 traced the
     * dpi parser's stores "pcwf" -> +0x26, "ix_pcwf" -> +0x28, "nonflashadj" -> +0x2a (0x102ad3fb/469/4d7), which are
     * block words 6, 7, 8 (observed 70 25 25 in the arg6 block on r4/r1). */
    vec[720] = c->pcwf * 10;
    vec[726] = c->ix_pcwf * 10;
    vec[727] = c->non_flash_adj * 10;
    vec[728] = ld16(c->params, 0x10E);
    vec[729] = ld16(c->params, 0x110);
    vec[721] = f[1] >= 0xFC ? -1 : (int8_t)f[1];
    vec[722] = f[2] >= 0xFE ? -1 : (int8_t)f[2];
    vec[723] = f[3] >= 0xFE ? -1 : (int8_t)f[3];
    vec[724] = f[4] >= 0xFE ? -1 : (int8_t)f[4];
    vec[725] = f[6] == 1;
    vec[730] = mode;
    vec[731] = (c->flagsword & 0x800) != 0;
    vec[732] = (c->flagsword & 0x1000) >> 12;
    memset(known + 720, 1, 13);
}

/* ---------------------------------------------------------------- the pass */

void pkc_sba_scene_init(pkc_sba_scene *s) {
    memset(s->vec, 0, sizeof s->vec);
    memset(s->known, 1, sizeof s->known);
    memset(s->mask, 0, sizeof s->mask);
}

pk_status pkc_sba_measure_scene(const pkc_planes *aimg, const int32_t grid[3][PKC_GRID_N], const uint16_t dmin[3],
                                const pkc_sba_ctx *c, int pass, pkc_sba_scene *scene, pkc_sba_measure *out) {
    (void)aimg; (void)dmin;
    if (!grid || !c || !scene || !out || !c->prog.rec ||
        (pass != PKC_SBA_PASS1 && pass != PKC_SBA_FOS2 && pass != PKC_SBA_SHORT2))
        return PK_E_ARG;
    /* 0x1028b91a..0x1028b94e: pcwf / ix_pcwf must lie in [params[0x104], params[0x106]], else 0x18bd */
    int lo_r = ld16(c->params, 0x104), hi_r = ld16(c->params, 0x106);
    if (c->pcwf < lo_r || c->pcwf > hi_r || c->ix_pcwf < lo_r || c->ix_pcwf > hi_r) return PK_E_ARG;
    int32_t *im = malloc(NBANDS * N * sizeof *im);          /* 6 bands, plane-major, row stride 36 */
    pkc_sba_scene *ns = malloc(sizeof *ns);                 /* the scene as this pass leaves it */
    if (!im || !ns) { free(im); free(ns); return PK_E_NOMEM; }
    *ns = *scene;
    pk_status st = PK_OK;
    pkc_pass_cfg pc;
    pass_config(c, pass, &pc);

    /* build_measure_inputs: bands 0-2 = grid, 3-5 = opening axes per sample; offsets = opening + its axes */
    int32_t off[NBANDS];
    for (int p = 0; p < 3; p++) off[p] = c->opening[p];
    pkc_sba_axes(off[0], off[1], off[2], &off[3], &off[4], &off[5]);
    for (int p = 0; p < 3; p++) memcpy(im + N * p, grid[p], N * sizeof *im);
    for (int i = 0; i < N; i++) pkc_sba_axes(im[i], im[N + i], im[2 * N + i], &im[3 * N + i], &im[4 * N + i], &im[5 * N + i]);

    const uint8_t *en = pc.en, *par = c->params + 0xDC, *bytetab;
    const uint32_t *dw;
    sel_tables(c, &bytetab, &dw);

    st = pkc_selection_mask(im, off, c, &pc, ns->vec[479], ns->mask);   /* scene+0x7b8 as the previous pass left it */
    if (st != PK_OK) goto done;

    uint8_t A6[A6_LEN], A7[A7_LEN];
    memset(A6, 0, sizeof A6); memset(A7, 0, sizeof A7);
    pkc_measure_bank_block(A6, im, off, en, dw);
    pkc_hdr hd = pkc_measure_whole_frame(A6, im, off, ns->mask, en, par, bytetab, dw);
    static const int A7_DIV[14] = { 864, 162, 162, 162, 162, 216, 216, 216, 216, 216, 216, 216, 216, 216 };
    for (int n = 0; n < 14; n++) st16(A7, 2 * n, A7_DIV[n]);
    st16(A7, 0x1C, hd.n_mask1); st16(A7, 0x1E, hd.n_mask1);
    st16(A7, 0x20, hd.n_b4); st16(A7, 0x22, hd.n_b4);
    int32_t A3[75], A4[19], A5[9];
    pkc_l_blocks(im, off, ns->mask, dw, A3, A4, A5);

    pack_t k = { ns->vec, ns->known, A6, A7 };
    st = pkc_vecpack(&k, pass == PKC_SBA_PASS1, en, par, &hd, A3, A4, A5);
    if (st != PK_OK) goto done;

    out->L = 0;
    ns->vec[730] = pc.mode; ns->known[730] = 1;             /* *(scene+0x5d2*2) = mode, stored before the measure call */
    ns->vec[731] = (c->flagsword & 0x800) != 0;             /* 0x1028bb0d / 0x1028bb1f: stored before the pass switch, */
    ns->vec[732] = (c->flagsword & 0x1000) >> 12;           /* so pass 1 writes them too */
    ns->known[731] = ns->known[732] = 1;
    if (pass != PKC_SBA_PASS1) {                            /* pass 1 returns right after fcn.102aece0 (0x1028bdc..) */
        pkc_vec_tail(c, pc.mode, ns->vec, ns->known);
        st = pkc_sba_vm_l(&c->prog, ns->vec, ns->known, PKC_SBA_VEC_N, &out->L, NULL);
        if (st != PK_OK) goto done;
    }
    memcpy(out->Yband, im + 3 * N, N * sizeof *im);
    memcpy(out->C1band, im + 4 * N, N * sizeof *im);
    memcpy(out->C2band, im + 5 * N, N * sizeof *im);
    memcpy(out->mask, ns->mask, N);
    memcpy(out->lvec, ns->vec, sizeof out->lvec);
    out->ythr = ns->vec[3];
    *scene = *ns;
done:
    free(im); free(ns);
    return st;
}
