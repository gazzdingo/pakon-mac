#define _POSIX_C_SOURCE 200809L
/* Boards: lamp control (Task 9, spec C). F-135 warm-up is the port of TLB FN_bLampTemperatureStable (FUN_1002CF10) over the
 * monitor's own state (FUN_1000BDD0 / FUN_1000B890); the F-235 packets are the TLA ones from the spec (beta, refused by the link
 * until Task 21). */
#include "boards/boards.h"
#include <string.h>

#define PKB_WARMUP_POLL_MS 250u
#define PKB_WARMUP_TIMEOUT_MS 300000u
#define PKB_LAMP235_MAX 0x3A34u
#define PKB_LAMP235_STANDBY 0x2CECu          /* TLA FUN_10033c70(..., 0x2000, 0x2CEC, 0): the minimum non-zero level */
#define PKB_LAMP235_REG_LEVEL 0x80
#define PKB_LAMP235_CMD_OFF 0x81
#define PKB_SAVER_MAX_S 600u                 /* TLA validates 1..600 (cmp ecx, 0x258) */
#define PKB_INT_DX_GATE 0x18u                /* FUN_1000B890 reads 0x83 when register 0x02 has bits 0x18 */
#define PKB_STATUS_FAULT6 0x40u

void pkb_lamp235_level_bytes(unsigned level, uint8_t out[2]) {
    if (level > PKB_LAMP235_MAX) level = PKB_LAMP235_MAX;
    out[0] = (uint8_t)(level & 0xFF);
    out[1] = (uint8_t)(level >> 8);
}

pk_status pk_lamp_keepalive(pk_boards *b) {
    if (!b) return PK_E_ARG;
    uint32_t ir = 0;
    pk_status s = pkb_irq_take(b, 0x5Bu, &ir);      /* the event path: acknowledge, then judge once */
    if (s != PK_OK) return s;
    s = pkb_lamp_monitor(b, ir, false, NULL);
    if (s != PK_OK) return s;
    uint8_t st;                                     /* a plain keep-alive read; not judged (PSI parity) */
    return pk_link_read(b->link, b->light, PKB_REG_LIGHT_STATUS, PKB_LIGHT_STATUS_LEN, &st);
}

pk_status pkb_light_devinfo(pk_boards *b, uint8_t out[12]) {
    uint8_t one = 1;
    pk_status s = pk_link_write(b->link, b->light, PKB_REG_LIGHT_DEVINFO_SELECT, &one, 1);
    if (s == PK_OK) s = pk_link_read(b->link, b->light, PKB_REG_LIGHT_DEVINFO, PKB_LIGHT_DEVINFO_LEN, out);
    if (s == PK_OK) b->light_fw_ver = out[2];
    return s;
}

pk_status pkb_light_fw_version(pk_boards *b, int *out) {
    if (b->light_fw_ver >= 0) { *out = b->light_fw_ver; return PK_OK; }
    uint8_t d[12];                 /* TLB FN_bDrvGetDevInfo FUN_1000A370: 0x03 = 1, then 0x07 x12; devinfo[2] is the hardware version byte (RE 29 sec 9), which TLB keeps in cfg+0x47C */
    pk_status s = pkb_light_devinfo(b, d);
    if (s != PK_OK) return s;
    /* data[2] (TLB FUN_1001C3E0 at 0x1001C744: movzx [esp+0x7E] -> cfg+0x47C) */
    *out = d[2];
    return PK_OK;
}

/* TLB FUN_1000BDD0 -> FUN_1000B890, ported with its gating. ir = register 0x02. TLB calls FUN_1000B890 when (ir & 0x5B) != 0 (or forced):
 *  - ir & 0x18 (or forced): the "full" path. Read 0x83: bit 0 with the light board version byte (devinfo[2]) above 3 -> flag 0x4000 (STATUS0); bits 5/6 -> faults;
 *    with bit 6 clear, bit 1 and state < 0 -> state 0; the temperature bands are judged (forced: only when 0x83 bit 3) and set WARN or FAULT.
 *  - otherwise only ir bit 1 with state < 0 -> state 0.
 *  Then state 0 -> 1 (latched). Flags accumulate in b->sticky (TLB device +0x38). The extra reads (0x84/0x88/0x83) are telemetry, not judged. */
pk_status pkb_lamp_monitor(pk_boards *b, uint32_t ir, bool forced, pk_light_health *last) {
    if (!forced && (ir & 0x5Bu) == 0) return PK_OK;
    bool full = forced || (ir & PKB_INT_DX_GATE) != 0;
    int ver = 0;
    if (full) { pk_status vs = pkb_light_fw_version(b, &ver); if (vs != PK_OK) return vs; }
    pk_light_health h;
    pk_status s = pk_light_health_poll(b, &h);
    if (s != PK_OK) return s;
    if (last) *last = h;
    if (full) {
        uint32_t f = 0;
        if ((h.status & 1u) && ver > 3) f |= PK_LIGHT_F_STATUS0;
        if (h.status & PKB_LAMP_STATUS_FAULT_MASK) f |= PK_LIGHT_F_FAULT;
        if (!(h.status & PKB_STATUS_FAULT6) && (h.status & PKB_WARMUP_STABLE_BIT) && b->lamp_state < 0) b->lamp_state = 0;
        if ((!forced || (h.status & PKB_LAMP_STATUS_TEMP_VALID)) && !(h.flags & PK_LIGHT_F_TEMP_UNREAD))
            f |= h.flags & (PK_LIGHT_F_LAMP_WARN | PK_LIGHT_F_LAMP_FAULT | PK_LIGHT_F_MAIN_WARN | PK_LIGHT_F_MAIN_FAULT);
        b->sticky |= f;
    } else if ((ir & PKB_WARMUP_STABLE_BIT) && b->lamp_state < 0) {
        b->lamp_state = 0;
    }
    if (b->lamp_state == 0) b->lamp_state = 1;
    return PK_OK;
}

#define PKB_FAULT_MASK (PK_LIGHT_F_FAULT | PK_LIGHT_F_LAMP_FAULT | PK_LIGHT_F_MAIN_FAULT | PK_LIGHT_F_STATUS0)   /* TLB abort mask 0x040548C0 */
#define PKB_PROGRESS_EVERY_MS 3000u      /* FUN_1002CF10: FUN_10032580(.., 0x18, 1000 + 10k) after every 12 polls of 250 ms */

pk_status pk_lamp_warmup(pk_boards *b, const pk_warmup_opts *o, pk_progress_cb cb, void *user, const volatile int *cancel) {
    if (!b) return PK_E_ARG;
    unsigned poll = o && o->poll_ms ? o->poll_ms : PKB_WARMUP_POLL_MS;
    unsigned timeout = o && o->timeout_ms ? o->timeout_ms : PKB_WARMUP_TIMEOUT_MS;
    if (poll > 10000u || timeout > PKB_WARMUP_TIMEOUT_MS) return PK_E_ARG;   /* TLB's timer is fixed at 300000 */
    if (b->lamp_state > 0) return PK_OK;                 /* TLB FUN_1002CF10's first test: already stable */
    if (b->motor != 0x44) { b->lamp_state = 1; return PK_OK; }   /* base board: ScannerVersionHw < 200, TLB never polls health and forces stable (FUN_1000BDD0 at 0x1000BFBC) */
    unsigned long long t0 = pkb_now_ms();
    unsigned next_report = PKB_PROGRESS_EVERY_MS, k = 0;
    pk_light_health h;
    memset(&h, 0, sizeof h);
    h.lamp_temp_raw = h.setpoint_raw = h.main_temp_raw = -1;
    for (;;) {
        if (cancel && *cancel) return PK_E_CANCELLED;
        if (b->sticky & PKB_FAULT_MASK) return PK_E_LAMP_WARMUP;         /* sticky faults survive ResetStatusLeds, as TLB's */
        unsigned long long el = pkb_now_ms() - t0;
        if (el >= timeout) return PK_E_LAMP_WARMUP;
        uint32_t ir = 0;
        pk_status s = pkb_irq_take(b, 0x5Bu, &ir);
        if (s != PK_OK) return s;
        s = pkb_lamp_monitor(b, ir, false, &h);
        if (s != PK_OK) return s;
        if (b->sticky & PKB_FAULT_MASK) return PK_E_LAMP_WARMUP;
        if (b->lamp_state > 0) { if (cb) cb(user, 100, &h); return PK_OK; }
        el = pkb_now_ms() - t0;
        if (cb && el >= next_report) {
            k++;
            next_report += PKB_PROGRESS_EVERY_MS;
            unsigned long long permille = (unsigned long long)PKB_PROGRESS_EVERY_MS * k * 1000ull / timeout;   /* 10k at 300 s: TLB passes 1000 + this */
            cb(user, (int)(permille / 10ull > 99ull ? 99ull : permille / 10ull), &h);
        }
        unsigned left = poll;
        while (left) {                                  /* sleep in slices so a cancel is noticed */
            unsigned sl = left < 50u ? left : 50u;
            pkb_sleep_ms(sl);
            left -= sl;
            if (cancel && *cancel) return PK_E_CANCELLED;
        }
    }
}

pk_status pk_lamp_set(pk_boards *b, pk_lamp_level level) {
    if (!b) return PK_E_ARG;
    if (level != PK_LAMP_OFF && level != PK_LAMP_STANDBY && level != PK_LAMP_ON) return PK_E_ARG;
    uint8_t a = b->model->roles.lamp235;
    if (!(b->model->caps & PK_CAP_LAMP_LEVELS) || !a) return PK_E_UNSUPPORTED;
    if (level == PK_LAMP_ON) return PK_E_UNSUPPORTED;   /* Task 21: derive from TLA FN_LampManualControl 0x1004b318 */
    if (level == PK_LAMP_OFF) return pk_link_command(b->link, a, PKB_LAMP235_CMD_OFF);
    uint8_t d[2];
    pkb_lamp235_level_bytes(PKB_LAMP235_STANDBY, d);
    return pk_link_write(b->link, a, PKB_LAMP235_REG_LEVEL, d, 2);
}

pk_status pk_lamp_saver(pk_boards *b, unsigned standby_after_s, unsigned off_after_s) {
    if (!b) return PK_E_ARG;
    if (!b->model->roles.lamp235) return PK_E_UNSUPPORTED;      /* the F-135 has no host idle timer */
    if (standby_after_s > PKB_SAVER_MAX_S || off_after_s > PKB_SAVER_MAX_S) return PK_E_ARG;
    b->lamp_standby_s = standby_after_s;
    b->lamp_off_s = off_after_s;
    if (b->model->id == PK_MODEL_F335 || b->model->id == PK_MODEL_F335C) return PK_E_UNSUPPORTED;   /* TLC delay-off wire format: Task 21 */
    return PK_OK;
}
