/* AFE (AD9826) black-level convergence (Task 15). Origin: TLB FN_bCalibrateFindDarkOffset FUN_1001e1c0 (code 0x1c) with the offset writer FUN_100299C0 and the gain writer FUN_100298B0
 * (docs/re/43-calibration-sequence.md row C3; docs/re/07-calibration.md sec 1.3 step c). v1's opt-in converge_afe_offsets (tools/pakon_scan.py:1926) used a different window and is not followed. */
#include <math.h>
#include "boards/boards.h"
#include "calib/calib.h"

#define PKCAL_GAIN_START 13u         /* FUN_100201d0(1.2) = ceil(75.6 * (1 - 1/1.2)) */
#define PKCAL_OFFSET_START 10        /* the offsets start at +10 */
#define PKCAL_OB_LINES 32u
#define PKCAL_OB_TARGET 300
#define PKCAL_OB_LO 268              /* pass when 268 <= m <= 332 (FUN_1001ce50(m, 300, 32, 32)) */
#define PKCAL_OB_HI 332
#define PKCAL_OFFSET_MAX 255         /* FUN_100299c0 clamps to +-255; the 9-bit sign-magnitude word cannot hold -255 here (pk_host_ccd_configure refuses it) */
#define PKCAL_OFFSET_MIN (-254)

/* FindDarkOffset. Per round: a 32-line SUM; m = trunc(sum over the optical-black pixels / (ob_px * 32)); a channel passes when 268 <= m <= 332, else its offset moves by
 * ftol((m - 300) * 2 * -0.0133928571) (= trunc(-(m-300) * 3/112)); channels converge independently; at most max_rounds (TLB 8) rounds, the offsets left by the last round are
 * kept and non-convergence is NOT an error (RE 43 row C3). Only the three colour channels have an AFE offset. */
pk_status pkcal_afe_converge(pkcal_run *r, unsigned max_rounds) {
    pk_ccd_cfg *cfg = &r->ccd;
    bool done[3] = { false, false, false };
    for (int c = 0; c < 3; c++) { cfg->afe_gain[c] = (uint8_t)PKCAL_GAIN_START; cfg->afe_offset[c] = PKCAL_OFFSET_START; }
    pk_status st = pk_host_ccd_update(r->b, cfg);
    for (unsigned round = 0; st == PK_OK && round < max_rounds; round++) {
        if ((st = pkcal_acquire(r, PKCAL_OB_LINES, r->acc)) != PK_OK) break;
        bool all = true;
        for (int c = 0; c < 3; c++) {
            uint64_t sum = 0;
            for (int p = 0; p < r->ob_px; p++) sum += r->acc[(size_t)c * (size_t)r->n_acq + (size_t)p];   /* FUN_1001d4c0(buf + c x n_acq, 0, ob) */
            const int m = (int)(sum / ((uint64_t)r->ob_px * PKCAL_OB_LINES));
            done[c] = m >= PKCAL_OB_LO && m <= PKCAL_OB_HI;
            if (done[c]) continue;
            all = false;
            int off = cfg->afe_offset[c] + (int)((double)(m - PKCAL_OB_TARGET) * 2.0 * -0.0133928571);   /* _ftol truncates toward zero */
            cfg->afe_offset[c] = (int16_t)(off > PKCAL_OFFSET_MAX ? PKCAL_OFFSET_MAX : off < PKCAL_OFFSET_MIN ? PKCAL_OFFSET_MIN : off);
        }
        if (all) break;
        if ((st = pk_host_ccd_update(r->b, cfg)) != PK_OK) break;          /* changed values only */
        pkcal_progress(r->c, 8 + (int)round, "black level round %u", round + 1);
    }
    if (st == PK_OK)
        for (int c = 0; c < 3; c++) { r->light.afe_offset[c] = cfg->afe_offset[c]; r->light.afe_gain[c] = cfg->afe_gain[c]; }
    return st;
}
