/* Boards: light board (Task 7). Ported from v1 pakon_scan.py (lamp_init_thresholds, lamp_on, lamp_switch_to_scan_duty, lamp_off,
 * poll_lamp) and pakon_commands.py (led_levels, led_pwm, lamp_set_mask). */
#include "boards/boards.h"
#include <string.h>

pk_status pk_light_lamp_init_thresholds(pk_boards *b) {
    if (!b) return PK_E_ARG;
    static const struct { uint8_t reg; uint8_t d[4]; } T[] = {   /* v1 order; PSI capture steps 9-12 carry the same bytes */
        { PKB_REG_LIGHT_TEMP_8F, { 0xE8, 0xFF, 0x18, 0x00 } },
        { PKB_REG_LIGHT_TEMP_8C, { 0xE0, 0xFF, 0x20, 0x00 } },
        { PKB_REG_LIGHT_TEMP_8B, { 0xF0, 0x00, 0x20, 0x03 } },
        { PKB_REG_LIGHT_TEMP_8D, { 0xA0, 0x00, 0x70, 0x03 } },
    };
    pk_status s;
    for (size_t i = 0; i < sizeof T / sizeof T[0]; i++)
        if ((s = pk_link_write(b->link, b->light, T[i].reg, T[i].d, 4)) != PK_OK) return s;
    uint8_t zero = 0, one = 1;
    if ((s = pk_link_write(b->link, b->light, PKB_REG_LIGHT_D0, &zero, 1)) != PK_OK) return s;
    return pk_link_write(b->link, b->light, PKB_REG_LIGHT_D1, &one, 1);
}

pk_status pk_light_lamp_on(pk_boards *b, bool visible, bool ir) {
    if (!b) return PK_E_ARG;
    uint8_t mask = (uint8_t)((visible ? 1 : 0) | (ir ? 2 : 0));
    pk_status s = pk_link_write(b->link, b->light, PKB_REG_LIGHT_LAMP_ENABLE, &mask, 1);
    if (s == PK_OK) { b->lamp_on = mask != 0; b->lamp_mask = mask; }
    return s;
}

/* v1 LED_LEVEL_MAX, keyed by (the light board is 0x40, IR on); slot order R, G, B, Ir. */
static void level_max(bool main_board, bool ir_on, unsigned m[4]) {
    static const unsigned T[2][2][4] = {
        { { 6, 8, 8, 0 }, { 8, 8, 8, 8 } },         /* non-0x44 board: IR off, IR on */
        { { 4, 20, 20, 0 }, { 8, 24, 24, 8 } },     /* 0x44 board: IR off, IR on */
    };
    memcpy(m, T[main_board ? 1 : 0][ir_on ? 1 : 0], 4 * sizeof m[0]);
}

pk_status pk_light_set_levels(pk_boards *b, const uint16_t levels[4]) {
    if (!b || !levels) return PK_E_ARG;
    unsigned m[4];
    level_max(b->light == 0x40, levels[3] > 0, m);
    for (int i = 0; i < 4; i++)
        if (levels[i] > m[i]) return PK_E_ARG;      /* v1 raises rather than clamps: a caller over the maximum has misread the units */
    uint8_t d[5] = { (uint8_t)levels[2], (uint8_t)levels[3], (uint8_t)levels[0], 0x00, (uint8_t)levels[1] };   /* [B, Ir, R, 0, G] */
    b->lamp_lv_known = false;
    pk_status s = pk_link_write(b->link, b->light, PKB_REG_LIGHT_LED_LEVELS, d, 5);
    if (s == PK_OK) { memcpy(b->lamp_lv, levels, sizeof b->lamp_lv); b->lamp_lv_known = true; }
    return s;
}

static pk_status check_duty(const uint16_t on[4], uint16_t period) {
    if (!on || period < 2) return PK_E_ARG;
    for (int i = 0; i < 4; i++)
        if (on[i] > period - 2) return PK_E_ARG;    /* the driver clamps on-counts to N-2 (v1 lamp_on_count, fcn.1002c5f0 @ 0x1002cd17) */
    return PK_OK;
}

static pk_status write_duty(pk_boards *b, const uint16_t on[4], uint16_t period) {
    const uint16_t w[6] = { on[2], on[3], on[0], 0, on[1], period };   /* [on_B, on_Ir, on_R, 0, on_G, N] */
    uint8_t d[12];
    for (int i = 0; i < 6; i++) { d[2 * i] = (uint8_t)(w[i] & 0xFF); d[2 * i + 1] = (uint8_t)(w[i] >> 8); }
    b->lamp_duty_known = false;
    pk_status s = pk_link_write(b->link, b->light, PKB_REG_LIGHT_LED_DUTY, d, 12);
    if (s == PK_OK) { memcpy(b->lamp_on_cnt, on, sizeof b->lamp_on_cnt); b->lamp_period = period; b->lamp_duty_known = true; }
    return s;
}

pk_status pk_light_set_duty(pk_boards *b, const uint16_t on_counts[4], uint16_t period) {
    if (!b) return PK_E_ARG;
    pk_status s = check_duty(on_counts, period);
    return s != PK_OK ? s : write_duty(b, on_counts, period);
}

pk_status pk_light_set_scan_duty(pk_boards *b, const uint16_t on_counts[4], uint16_t period) {
    if (!b) return PK_E_ARG;
    pk_status s = check_duty(on_counts, period);
    if (s != PK_OK) return s;
    memcpy(b->scan_on, on_counts, sizeof b->scan_on);
    b->scan_period = period;
    b->scan_duty_set = true;
    return PK_OK;
}

pk_status pk_light_scan_duty(pk_boards *b) {
    if (!b) return PK_E_ARG;
    if (!b->scan_duty_set) return PK_E_BUSY;
    return write_duty(b, b->scan_on, b->scan_period);
}

/* S-R26: TLB's FN_bEndScan lamp-off, exactly (RE 29 sec 14; .superpowers/sdd/.../lamp-off-debug.md):
 *   FUN_1000C4D0   LIGHT 0x80 = 0                          04 ... 02 04 40 01 80 00
 *   FUN_1000A730   FN_bDrvResetFifos:
 *     FUN_10009F90   HOST 0x84 = 2                         02 04 10 01 84 02
 *     FUN_10009E50   LIGHT type-4 command 0x8A             04 03 40 00 8A
 * then a read of 0x83 to confirm. On the light board 0x8A only sets the "reload the PWM chip" request (nl050A handler 0x3FE0: bsf 0xB3.6,
 * nothing else; the main loop then runs 0x1130); a bare 0x80 = 0 rewrites only the PWM control register and left the lamp lit on the
 * owner's F-135 Plus (HW-1 2026-10-19). Nothing here writes scanner memory. Each step is retried like v1's lamp-off. */
static pk_status lamp_off_step_retry(pk_boards *b, int step) {
    pk_status s = PK_E_IO;
    uint8_t zero = 0;
    for (int i = 0; i < pkb_attempts(b); i++) {
        s = step == 0 ? pk_link_write(b->link, b->light, PKB_REG_LIGHT_LAMP_ENABLE, &zero, 1) : pk_host_fifo_reset(b);
        if (s == PK_OK || pkb_status_is_final(s)) return s;
        if (i + 1 < pkb_attempts(b)) pkb_sleep_ms(PKB_RETRY_PAUSE_MS);
    }
    return s;
}

pk_status pk_light_lamp_off_ex(pk_boards *b, uint8_t *status83) {
    if (!b) return PK_E_ARG;
    if (status83) *status83 = 0;
    /* HW-1 follow-up 2026-10-19: Kodak's scan-end sequence alone (below) left the owner's lamp lit outside a scan, twice; zeroing
     * the drive first (0x82 on-counts 0, PSI's period N = 982, as PSI's own start-up does: v1 docs/59 step 17) put it out every
     * time. PSI's lamp does go dark after a real scan (owner), so its scan context must supply what is missing here; until that
     * is traced (Task 13), the drive is zeroed first. Every lamp-on rewrites 0x81 and 0x82, so this costs nothing later. */
    {
        static const uint16_t zero[4] = { 0, 0, 0, 0 };
        pk_status z = PK_E_IO;
        for (int i = 0; i < pkb_attempts(b); i++) {
            z = write_duty(b, zero, 982);
            if (z == PK_OK || pkb_status_is_final(z)) break;
            if (i + 1 < pkb_attempts(b)) pkb_sleep_ms(PKB_RETRY_PAUSE_MS);
        }
        /* A failed zero-drive stops here with lamp_on still set (R2-I1): HW-1 step 9a, 0x80 = 0 without the zero drive left the lamp lit
         * while 0x83 read "off", and a bare 0x80 = 0 makes the firmware skip its own ~60 s idle shut-off (lamp-off-debug.md:138, HW-1
         * step 10). Sending nothing more keeps that shut-off armed; pk_boards_close and the kept session marker retry. */
        if (z != PK_OK) return z;
    }
    pk_status s = lamp_off_step_retry(b, 0);
    if (s != PK_OK) return s;
    b->lamp_on = false;
    b->lamp_mask = 0;     /* the enables are off in the firmware; the rest is the reload and the proof */
    s = lamp_off_step_retry(b, 1);
    if (s != PK_OK) return s;
    /* Confirm: 0x83 data bit 1 (lamp on / stable) clear. Bit 4 means "all LED levels zero", which TLB's EndScan sequence does not
     * set (it leaves 0x81 alone), so it is reported in *status83 but not required (controller ruling on S-R26 concern 1; the HW-1
     * follow-up step 9a records the real byte). The PIC applies 0x80 / 0x8A on its next main-loop pass, so allow a short settle. */
    uint8_t st = 0;
    for (int i = 0; i < PKB_LAMP_OFF_ATTEMPTS; i++) {
        s = pk_link_read(b->link, b->light, PKB_REG_LIGHT_STATUS, PKB_LIGHT_STATUS_LEN, &st);
        if (s != PK_OK) { if (pkb_status_is_final(s) || (b->leave_mode && s == PK_E_TIMEOUT)) return s; }   /* leave mode: a timed-out read is not retried (S-R29) */
        else {
            if (status83) *status83 = st;
            if (!(st & PKB_LAMP_STATUS_STABLE)) return PK_OK;
            s = PK_E_DEVICE;
        }
        if (i + 1 < PKB_LAMP_OFF_ATTEMPTS) pkb_sleep_ms(PKB_RETRY_PAUSE_MS);
    }
    return s;
}

pk_status pk_light_lamp_off(pk_boards *b) { return pk_light_lamp_off_ex(b, NULL); }

pk_status pk_light_health_poll(pk_boards *b, pk_light_health *out) {
    if (!b || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    out->lamp_temp_raw = out->setpoint_raw = out->main_temp_raw = -1;
    uint8_t st = 0, sp[PKB_LIGHT_TEMPERATURE_LEN], tm[PKB_LIGHT_TEMPS_LEN];
    /* TLB FN_bDrvGetHardwareStatusLamp (FUN_1000B890): 0x83, then 0x84 (setpoint), then 0x88 (measured). */
    pk_status s = pk_link_read(b->link, b->light, PKB_REG_LIGHT_STATUS, PKB_LIGHT_STATUS_LEN, &st);
    if (s != PK_OK) return s;
    out->status = st;
    if (st & PKB_LAMP_STATUS_FAULT_MASK) out->flags |= PK_LIGHT_F_FAULT;
    if (st & PKB_LAMP_STATUS_TEMP_VALID) out->flags |= PK_LIGHT_F_TEMP_VALID;
    s = pk_link_read(b->link, b->light, PKB_REG_LIGHT_TEMPERATURE, PKB_LIGHT_TEMPERATURE_LEN, sp);
    if (s == PK_OK) s = pk_link_read(b->link, b->light, PKB_REG_LIGHT_TEMPS, PKB_LIGHT_TEMPS_LEN, tm);
    if (s == PK_E_WRITE_FORBIDDEN || s == PK_E_FIRMWARE_WEDGED) return s;
    if (s != PK_OK) {
        out->flags |= PK_LIGHT_F_TEMP_UNREAD;
    } else {
        int setpoint = sp[0] | sp[1] << 8, lamp = tm[0] | tm[1] << 8, main = tm[2] | tm[3] << 8;
        out->setpoint_raw = setpoint;
        out->lamp_temp_raw = lamp;
        out->main_temp_raw = main;
        int d = lamp - setpoint;
        if (d < 0) d = -d;
        if (d > 32) out->flags |= PK_LIGHT_F_LAMP_FAULT;         /* 0x8C band, +-32 (TLB if / else if: one flag per side) */
        else if (d > 24) out->flags |= PK_LIGHT_F_LAMP_WARN;     /* 0x8F band, +-24 */
        if (main < 160 || main > 880) out->flags |= PK_LIGHT_F_MAIN_FAULT;    /* 0x8D */
        else if (main < 240 || main > 800) out->flags |= PK_LIGHT_F_MAIN_WARN;   /* 0x8B */
    }
    out->ok = !(out->flags & (PK_LIGHT_F_FAULT | PK_LIGHT_F_LAMP_FAULT | PK_LIGHT_F_MAIN_FAULT));
    return PK_OK;
}
