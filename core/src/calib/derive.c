/* TLB's calibration-table arithmetic (Task 15 A). Origin: Kodak TLB.dll FN_bCalibrateFixedPatternDark FUN_1001e4a0 and
 * FN_bCalibrateFixedPatternBright FUN_1001f550 with the mean helper FUN_1001d4c0 (docs/re/30-tlb-scan-kernel.md sec 13). v1's
 * tools/build_calibration.py build_tables (gain = mean(flat)/flat per channel) is NOT followed: TLB's gain is absolute. */
#include "calib/calib.h"
#include <stdlib.h>
#include <string.h>

/* FUN_1001d4c0(buf, first, end, 1): an x87 sum from 0.0 in pixel order, divided by the count, truncated by _ftol. Every partial
 * sum is an integer below 2^53, so the double sum is exact and one IEEE division reproduces the x87 result at precision 53. */
static uint32_t range_mean(const uint32_t *row, int first, int end) {
    uint64_t s = 0;
    for (int i = first; i < end; i++) s += row[i];
    return (uint32_t)((double)s / (double)(end - first));
}

void pkcal_tables_free(pk_cal_tables *t) {
    if (!t) return;
    for (int c = 0; c < 4; c++) { free(t->dark[c]); free(t->gain[c]); }
    for (int c = 0; c < 3; c++) free(t->smear[c]);
    memset(t, 0, sizeof *t);
}

/* The two-pass form TLB really runs (RE 43 row C5): the Dark table is the truncated 128-line AVERAGE of pass 1 (FUN_1001e4a0, FUN_1001d590 with average = 1), and the
 * OB / active means and the gain denominators use the 128-line SUMS of a separate pass 2. channels = 4 adds the IR channel (index 3):
 *   IR gain = low32(0x7530000000 / den) clamped to 0x3FFFF (60000 * 65536 * 128; FUN_1001f550's IR branch, DISASSEMBLED) -- UNCHECKED: no UC vector exists for IR
 *   (RE 43 sec 4; checked against an HW-2 IR capture when one exists), and the per-pixel Smear ramp of the three colour channels in IR mode
 *   smear[c][i] = SmearC_c - ftol(i * SmearC_c / (n_px - 1))  (RE 07 sec 1.3 h, RE 43 sec 4) -- UNCHECKED likewise.
 * In IR mode the R/G/B Dark tables written here are replaced by pkcal_irlag_dark (TLB's FixedPatternDark keeps only the IR dark, FUN_1001e4a0; FixedPatternIrLag writes R, G, B). */
pk_status pkcal_derive_tables2(const uint32_t *dark1_sum, const uint32_t *dark_sum, const uint32_t *bright_sum, int n_lines, int n_px, int channels,
                               int ob_px, pk_cal_tables *out) {
    if (!out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    if (!dark1_sum || !dark_sum || !bright_sum || n_lines != PKCAL_TABLE_LINES || n_px <= 0 || ob_px <= 0 || n_px > 0x10000 || ob_px > 64)
        return PK_E_ARG;
    if (channels != 3 && channels != 4) return PK_E_ARG;
    const int w = ob_px + n_px;
    out->n_px = n_px;
    for (int c = 0; c < channels; c++) {
        out->dark[c] = malloc((size_t)n_px * sizeof *out->dark[c]);
        out->gain[c] = malloc((size_t)n_px * sizeof *out->gain[c]);
        if (!out->dark[c] || !out->gain[c]) { pkcal_tables_free(out); return PK_E_NOMEM; }
    }
    if (channels == 4)
        for (int c = 0; c < 3; c++) {
            out->smear[c] = malloc((size_t)n_px * sizeof *out->smear[c]);
            if (!out->smear[c]) { pkcal_tables_free(out); return PK_E_NOMEM; }
        }
    for (int c = 0; c < channels; c++) {
        const uint32_t *d1 = dark1_sum + (size_t)c * (size_t)w, *d = dark_sum + (size_t)c * (size_t)w, *b = bright_sum + (size_t)c * (size_t)w;
        const uint64_t num = c == 3 ? (UINT64_C(0x75) << 32 | UINT64_C(0x30000000)) : (UINT64_C(0x7D) << 32);
        for (int i = 0; i < n_px; i++) out->dark[c][i] = (uint16_t)(d1[ob_px + i] / (uint32_t)PKCAL_TABLE_LINES);
        const uint32_t dob = range_mean(d, 0, ob_px), dact = range_mean(d, ob_px, w);
        const uint32_t bob = range_mean(b, 0, ob_px), bact = range_mean(b, ob_px, w);
        uint16_t smearc = 0;
        if (bact > dact) {
            const int64_t q = ((int64_t)bob - (int64_t)dob) * 65536 / (int64_t)(bact - dact);   /* __alldiv: toward zero */
            if (q >= 1 && q <= 699) smearc = (uint16_t)q;
        }
        if (c < 3) out->smearc[c] = smearc;
        if (c < 3 && channels == 4)
            for (int i = 0; i < n_px; i++) {
                const double ramp = n_px > 1 ? (double)i * (double)smearc / (double)(n_px - 1) : 0.0;
                out->smear[c][i] = (uint16_t)(smearc - (int)ramp);
            }
        for (int i = 0; i < n_px; i++) {
            const uint32_t den = b[ob_px + i] - d[ob_px + i] - bob + dob;                    /* mod 2^32, as TLB */
            uint32_t g = 0;
            if (den) {
                g = (uint32_t)(num / den);                                                   /* low dword only */
                if (g > 0x3FFFFu) g = 0x3FFFFu;
            }
            out->gain[c][i] = g;
        }
    }
    return PK_OK;
}

/* The one-dark-sum form the Kodak-match test uses (the golden holds a single dark sum, so both TLB passes read it). */
pk_status pkcal_derive_tables(const uint32_t *dark_sum, const uint32_t *bright_sum, int n_lines, int n_px, int channels, int ob_px,
                              pk_cal_tables *out) {
    return pkcal_derive_tables2(dark_sum, dark_sum, bright_sum, n_lines, n_px, channels, ob_px, out);
}

/* FN_bCalibrateFixedPatternIrLag FUN_1001fb80 after its 128-line average (FUN_1001d590 average = 1): per colour channel the minimum over the active pixels (FUN_1001ce20 for R, the
 * same loop inline for G and B, from 0xFFFF), then Dark_i = avg_i + (300 - min) when min < 301, else avg_i - (min - 300): both are (u16)(avg_i - min + 300). The low 16 bits of
 * each averaged dword are read (a short pointer stepping by 2). UNCHECKED against a Kodak vector (none exists for IR). */
pk_status pkcal_irlag_dark(const uint32_t *lag_sum, int n_lines, int n_px, int ob_px, pk_cal_tables *t) {
    if (!lag_sum || !t || n_lines != PKCAL_TABLE_LINES || n_px <= 0 || ob_px <= 0 || t->n_px != n_px) return PK_E_ARG;
    const int w = ob_px + n_px;
    for (int c = 0; c < 3; c++) {
        if (!t->dark[c]) return PK_E_ARG;
        const uint32_t *row = lag_sum + (size_t)c * (size_t)w + (size_t)ob_px;
        uint32_t mn = 0xFFFFu;
        for (int i = 0; i < n_px; i++) { const uint32_t v = row[i] / (uint32_t)n_lines; if (v < mn) mn = v; }
        for (int i = 0; i < n_px; i++) t->dark[c][i] = (uint16_t)((uint16_t)(row[i] / (uint32_t)n_lines) - (uint16_t)mn + 300u);
    }
    return PK_OK;
}
