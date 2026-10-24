/* Boards: the one conversion from light settings to a pk_ccd_cfg (Task 13, ruling C63), the TLB period / on-count rules, and the calibration seeds
 * (RE 41 sec 1). Nothing here sends a packet. */
#include "boards/boards.h"
#include "pakon/calib.h"
#include <math.h>
#include <string.h>

#define PKB_FPGA_SCAN_CTRL 0x0060u      /* the control word TLB writes with its first window: 0x0060, acquire (bit 0) added at the start of the stream */
#define PKB_PWM_CLOCK 2083333.3         /* RE 41 row 12: N = trunc(integration x 10^6 / (2 x 2083333.3)) */

unsigned pkb_pwm_period(unsigned integration) {
    return (unsigned)((double)integration * 1000000.0 / (2.0 * PKB_PWM_CLOCK));
}

unsigned pkb_duty_on_count(unsigned period, double duty) {
    if (period < 2 || !(duty > 0.0)) return 0;
    double on = ceil((double)period * duty);
    unsigned cap = period - 2;
    return on >= (double)cap ? cap : (unsigned)on;
}

pk_status pkb_ccd_cfg_from(const pk_model *m, const struct pk_cal_light *cal, int dpi_base, pk_ccd_cfg *out) {
    if (!m || !cal || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    pkb_ccd_window w;
    pk_status s = pkb_ccd_window_for(m, dpi_base, &w);
    if (s != PK_OK) return s;
    if (cal->dpi_base != dpi_base || cal->integration == 0 || cal->integration > PKB_INTEGRATION_MAX) return PK_E_ARG;
    out->px_offset = cal->px_offset ? (uint16_t)cal->px_offset : w.px_offset;   /* the unit's own offset replaces TLB's default (RE 29 sec 12) */
    out->px_height = w.px_height;
    out->integration = (uint16_t)cal->integration;
    for (int i = 0; i < 3; i++) {
        if (cal->afe_gain[i] > PKB_ADC_GAIN_MAX || cal->afe_offset[i] <= -PKB_ADC_OFFSET_MAX || cal->afe_offset[i] > PKB_ADC_OFFSET_MAX) return PK_E_ARG;
        out->afe_gain[i] = (uint8_t)cal->afe_gain[i];
        out->afe_offset[i] = (int16_t)cal->afe_offset[i];
    }
    out->fpga_ctrl = PKB_FPGA_SCAN_CTRL | (cal->ir ? 0x100u : 0u);   /* FUN_10029770(0x100, ir): the IR bit */
    out->binned = w.binned;
    out->light_89 = w.light_89;
    out->lamp_period = (uint16_t)pkb_pwm_period(cal->integration);
    for (int i = 0; i < 3; i++) out->on_counts[i] = (uint16_t)pkb_duty_on_count(out->lamp_period, cal->duty_film[i]);
    return PK_OK;
}

/* TLB light-config constructor FUN_1000FC10 (OBSERVED, RE 41 sec 1): Gain 13, Offset 0, Current 1, every duty 0.0; the integration is FUN_10011A60's per base:
 * 0x753 / 0xAFD / 0xFFD non-IR and 0x4E2 / 0x850 / 0x9C2 IR at base 4 / 8 / 16 (RE 42 sec 1.1). The F-135 base board's 0x913 / 0xD9D / 0xFF0 (RE 07's table)
 * belong to another constructor (FUN_10010760), reached only without a 0x44 motor board (RE 42 sec 4). */
pk_status pk_cal_light_seed(pk_cal_light *out, int dpi_base, bool ir) {
    if (!out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    if (dpi_base != 4 && dpi_base != 8 && dpi_base != 16) return PK_E_UNSUPPORTED;
    static const unsigned INT_RGB[3] = { 0x753, 0xAFD, 0xFFD }, INT_IR[3] = { 0x4E2, 0x850, 0x9C2 };
    out->version = 1;
    out->dpi_base = dpi_base;
    out->ir = ir;
    for (int i = 0; i < 3; i++) out->afe_gain[i] = 13;
    for (int i = 0; i < 4; i++) out->current[i] = 1;
    out->integration = (ir ? INT_IR : INT_RGB)[dpi_base == 4 ? 0 : dpi_base == 8 ? 1 : 2];
    return PK_OK;
}
