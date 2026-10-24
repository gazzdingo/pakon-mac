#define _POSIX_C_SOURCE 200809L
/* Boards: open/close, host (FX2) commands and the CCD / FPGA / AFE configuration (Task 7). Every packet goes through
 * pk_link_*, so the write guard sees it. Byte layouts are ported from v1 tools/pakon_scan.py (ccd_configure, acquire,
 * reset_fifos) and tools/pakon_commands.py (write_ccd_register, afe_offset_word); the register sequence is v1's. */
#include "boards/boards.h"
#include "link/link.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

void pkb_sleep_ms(unsigned ms) {
    if (!ms) return;
    struct timespec ts = { (time_t)(ms / 1000u), (long)(ms % 1000u) * 1000000L };
    while (nanosleep(&ts, &ts) != 0 && errno == EINTR) {}
}

/* A pulled cable (PK_E_DISCONNECTED) is final too: a retry cannot help, and the session must fail fast (Task 12). */
bool pkb_status_is_final(pk_status s) { return s == PK_E_WRITE_FORBIDDEN || s == PK_E_FIRMWARE_WEDGED || s == PK_E_ARG || s == PK_E_DISCONNECTED; }

pk_status pk_boards_open(pk_link *link, const pk_model *model, pk_boards **out) {
    if (!out) return PK_E_ARG;
    *out = NULL;
    if (!link || !model) return PK_E_ARG;
    if (!model->roles.light || !model->roles.motor || !model->roles.host) return PK_E_ARG;
    pk_boards *b = calloc(1, sizeof *b);
    if (!b) return PK_E_NOMEM;
    b->link = link;
    b->model = model;
    b->light = model->roles.light;
    b->motor = model->roles.motor;
    b->host = model->roles.host;
    b->fpga_ctrl = -1;
    b->light_89 = -1;
    b->dx_nibble = -1;
    b->led.enabled = true;
    b->led.shadow = PKB_LED_SHADOW_INIT;
    b->light_fw_ver = -1;
    b->lamp_state = -1;
    b->status_led_code = -1;
    b->roller_cache = PKB_ROLLER_UNKNOWN;
    b->guide_pos = -1;
    if (pthread_mutex_init(&b->film_mu, NULL) != 0) { free(b); return PK_E_NOMEM; }
    if (pthread_mutex_init(&b->irq_mu, NULL) != 0) { pthread_mutex_destroy(&b->film_mu); free(b); return PK_E_NOMEM; }
    if (pthread_mutex_init(&b->nib_mu, NULL) != 0) { pthread_mutex_destroy(&b->irq_mu); pthread_mutex_destroy(&b->film_mu); free(b); return PK_E_NOMEM; }
    *out = b;
    return PK_OK;
}

void pk_boards_close(pk_boards *b) {
    if (!b) return;
    /* PSI: lamp off on destroy (spec C); a running move is stopped. Best effort, errors ignored. */
    if (b->film_moving) (void)pk_motor_stop(b);
    if (b->lamp_on) (void)pk_light_lamp_off(b);
    pthread_mutex_destroy(&b->film_mu);
    pthread_mutex_destroy(&b->irq_mu);
    pthread_mutex_destroy(&b->nib_mu);
    free(b);
}
void pk_boards_set_leave_mode(pk_boards *b, bool on, unsigned budget_ms) {
    if (!b) return;
    b->leave_mode = on;
    pk_link_set_leave_mode(b->link, on ? budget_ms : 0);
}
int pkb_attempts(const pk_boards *b) { return b->leave_mode ? 1 : PKB_LAMP_OFF_ATTEMPTS; }
pk_link *pk_boards_link(pk_boards *b) { return b ? b->link : NULL; }
pk_transport *pk_boards_transport(pk_boards *b) { return b ? pkl_link_transport(b->link) : NULL; }
const pk_model *pk_boards_model(const pk_boards *b) { return b ? b->model : NULL; }

pk_status pkb_ccd_window_for(const pk_model *m, int dpi_base, pkb_ccd_window *out) {
    if (!m || !out) return PK_E_ARG;
    pk_status s = pk_model_check_base(m, dpi_base);
    if (s != PK_OK) return s;
    const pk_base_geom *g = &m->geom[dpi_base == 4 ? 0 : dpi_base == 8 ? 1 : 2];
    if (g->ccd_px_height <= 0) return PK_E_UNSUPPORTED;
    out->px_offset = (uint16_t)g->ccd_px_offset;
    out->px_height = (uint16_t)g->ccd_px_height;
    out->binned = dpi_base == 4;          /* TLB FUN_10011A60: the binning flag (+0x8C) is set in the base-4 branch only */
    out->light_89 = dpi_base == 8 ? 1 : 0; /* ... and the light-89 flag (+0x90) in the base-8 branch only */
    return PK_OK;
}

/* ---------------------------------------------------------------- CCD / FPGA / AFE */
/* v1 write_ccd_register: 02 06 AA 03 RR II lo hi. */
static pk_status reg3(pk_boards *b, uint8_t reg, uint8_t idx, unsigned value) {
    uint8_t d[3] = { idx, (uint8_t)(value & 0xFF), (uint8_t)(value >> 8 & 0xFF) };
    return pk_link_write(b->link, b->motor, reg, d, 3);
}
static pk_status fpga(pk_boards *b, uint8_t idx, unsigned v) { return reg3(b, PKB_REG_CCD_FPGA, idx, v); }
static pk_status adc(pk_boards *b, uint8_t idx, unsigned v) { return reg3(b, PKB_REG_CCD_ADC, idx, v); }

/* v1 afe_offset_word (= vendor FN_bDrvPutCcdAtoDOffsets 0x100299dc..0x100299fc): 9-bit sign-magnitude. */
static pk_status afe_offset_word(int v, unsigned *word) {
    if (v <= -PKB_ADC_OFFSET_MAX) return PK_E_ARG;
    if (v >= PKB_ADC_OFFSET_MAX) v = PKB_ADC_OFFSET_MAX;
    *word = (unsigned)(v < 0 ? -v : v) | (v < 0 ? PKB_ADC_OFFSET_SIGN : 0u);
    return PK_OK;
}

/* The checks both CCD entry points make before a byte is sent; fills the AFE offset words and the control word. */
static pk_status ccd_check(const pk_ccd_cfg *c, unsigned offs[3], unsigned *ctrl) {
    /* TLB FUN_1002C340's own checks (its assertion strings), then v1's. */
    unsigned lower = c->binned ? 3u : 6u, limit = c->binned ? 0x424u : 0x848u;
    unsigned end = (unsigned)c->px_offset + c->px_height;
    if (c->px_height == 0 || c->px_offset < lower || end > limit) return PK_E_ARG;
    if (!c->binned && c->light_89 && (c->px_height & 3u)) return PK_E_ARG;
    if (c->light_89 > 1) return PK_E_ARG;
    if (c->integration > PKB_INTEGRATION_MAX) return PK_E_ARG;
    for (int i = 0; i < 3; i++) {
        if (c->afe_gain[i] > PKB_ADC_GAIN_MAX) return PK_E_ARG;
        if (afe_offset_word(c->afe_offset[i], &offs[i]) != PK_OK) return PK_E_ARG;
    }
    /* TLB FUN_1002C340 -> FUN_10029770(this, ctx, 2, binned): control bit 0x002 follows the binning flag. */
    *ctrl = (unsigned)c->fpga_ctrl & PKB_FPGA_CTRL_MASK & ~(unsigned)PKB_FPGA_CTRL_ACQUIRE & ~0x002u;
    if (c->binned) *ctrl |= 0x002u;
    return PK_OK;
}

static void ccd_remember(pk_boards *b, const pk_ccd_cfg *c, const unsigned offs[3], unsigned end) {
    b->ccd_off = c->px_offset;
    b->ccd_end = end;
    b->ccd_int = c->integration;
    for (int i = 0; i < 3; i++) { b->afe_gain[i] = c->afe_gain[i]; b->afe_off[i] = offs[i]; }
    b->ccd_known = true;
}

pk_status pk_host_ccd_configure(pk_boards *b, const pk_ccd_cfg *c) {
    if (!b || !c) return PK_E_ARG;
    unsigned offs[3], ctrl;
    pk_status s = ccd_check(c, offs, &ctrl);
    if (s != PK_OK) return s;
    unsigned end = (unsigned)c->px_offset + c->px_height;
    b->ccd_known = false;     /* until the whole sequence has gone out */
    /* idx 5 is the END pixel (offset + height), not the height (v1 ccd_configure comment, docs/53). */
    if ((s = fpga(b, PKB_FPGA_PIXEL_OFFSET, c->px_offset)) != PK_OK) return s;
    if ((s = fpga(b, PKB_FPGA_PIXEL_END, end)) != PK_OK) return s;
    if ((s = fpga(b, PKB_FPGA_INTEGRATION, c->integration)) != PK_OK) return s;
    if ((s = fpga(b, PKB_FPGA_IDX_0B, 0)) != PK_OK) return s;
    for (uint8_t idx = 1; idx <= 3; idx++)
        if ((s = fpga(b, idx, 0)) != PK_OK) return s;
    if ((s = fpga(b, PKB_FPGA_IDX_0A, 0x400)) != PK_OK) return s;
    if ((s = adc(b, 0, 0x78)) != PK_OK) return s;
    if ((s = adc(b, 1, 0x80)) != PK_OK) return s;
    for (int i = 0; i < 3; i++)
        if ((s = adc(b, (uint8_t)(2 + i), c->afe_gain[i])) != PK_OK) return s;
    for (int i = 0; i < 3; i++)
        if ((s = adc(b, (uint8_t)(5 + i), offs[i])) != PK_OK) return s;
    if (b->light_89 != c->light_89) {   /* TLB FUN_1002C340 -> FUN_10009F90: only when the per-base flag changes (it writes 0 at init) */
        uint8_t v = c->light_89;
        if ((s = pk_link_write(b->link, b->light, PKB_REG_LIGHT_89, &v, 1)) != PK_OK) return s;
        b->light_89 = c->light_89;
    }
    s = fpga(b, PKB_FPGA_CONTROL, ctrl);
    if (s != PK_OK) { b->fpga_ctrl = -1; return s; }   /* what the FPGA holds is now unknown */
    b->fpga_ctrl = (int)ctrl;
    ccd_remember(b, c, offs, end);
    return PK_OK;
}

pk_status pk_host_ccd_update(pk_boards *b, const pk_ccd_cfg *c) {
    if (!b || !c) return PK_E_ARG;
    unsigned offs[3], ctrl;
    pk_status s = ccd_check(c, offs, &ctrl);
    if (s != PK_OK) return s;
    if (!b->ccd_known || b->fpga_ctrl < 0) return pk_host_ccd_configure(b, c);
    unsigned end = (unsigned)c->px_offset + c->px_height;
    b->ccd_known = false;     /* a failed write leaves the shadows unknown: the next update is a full configure */
    /* TLB FUN_1002C340 (RE 41 row 9): IR bit 0x100 and binning bit 0x002 are cleared / set on index 0 first, the acquire bit is kept. */
    unsigned want = ctrl | ((unsigned)b->fpga_ctrl & PKB_FPGA_CTRL_ACQUIRE);
    if (want != (unsigned)b->fpga_ctrl) {
        if ((s = fpga(b, PKB_FPGA_CONTROL, want)) != PK_OK) { b->fpga_ctrl = -1; return s; }
        b->fpga_ctrl = (int)want;
    }
    if (c->integration != b->ccd_int && (s = fpga(b, PKB_FPGA_INTEGRATION, c->integration)) != PK_OK) return s;
    if (c->px_offset != b->ccd_off && (s = fpga(b, PKB_FPGA_PIXEL_OFFSET, c->px_offset)) != PK_OK) return s;
    if (end != b->ccd_end && (s = fpga(b, PKB_FPGA_PIXEL_END, end)) != PK_OK) return s;
    if (b->light_89 != c->light_89) {
        uint8_t v = c->light_89;
        if ((s = pk_link_write(b->link, b->light, PKB_REG_LIGHT_89, &v, 1)) != PK_OK) return s;
        b->light_89 = c->light_89;
    }
    for (int i = 0; i < 3; i++)          /* FUN_100299C0: offsets first ... */
        if (offs[i] != b->afe_off[i] && (s = adc(b, (uint8_t)(5 + i), offs[i])) != PK_OK) return s;
    for (int i = 0; i < 3; i++)          /* ... then FUN_100298B0: gains */
        if (c->afe_gain[i] != b->afe_gain[i] && (s = adc(b, (uint8_t)(2 + i), c->afe_gain[i])) != PK_OK) return s;
    ccd_remember(b, c, offs, end);
    return PK_OK;
}

pk_status pk_host_acquire(pk_boards *b, bool on) {
    if (!b) return PK_E_ARG;
    if (b->fpga_ctrl < 0) return PK_E_BUSY;
    unsigned ctrl = (unsigned)b->fpga_ctrl;
    ctrl = on ? (ctrl | PKB_FPGA_CTRL_ACQUIRE) : (ctrl & ~(unsigned)PKB_FPGA_CTRL_ACQUIRE);
    pk_status s = fpga(b, PKB_FPGA_CONTROL, ctrl & PKB_FPGA_CTRL_MASK);
    if (s == PK_OK) b->fpga_ctrl = (int)(ctrl & PKB_FPGA_CTRL_MASK);
    else b->fpga_ctrl = -1;
    return s;
}

pk_status pk_host_fifo_reset(pk_boards *b) {
    if (!b) return PK_E_ARG;
    uint8_t v = PKB_HOST_FIFO_RESET_VALUE;
    pk_status s1 = pk_link_write(b->link, b->host, PKB_REG_HOST_FIFO_RESET, &v, 1);
    pk_status s2 = pk_link_command(b->link, b->light, PKB_CMD_LIGHT_FIFO_RESET);
    return s1 != PK_OK ? s1 : s2;
}

pk_status pkb_light_int_ack(pk_boards *b, uint8_t v) {
    uint8_t d[2] = { 0x00, v ? v : 0xFF };      /* TLB FUN_1000BDD0 -> FUN_10009AE0(light, 0x06, [00, v], 2) */
    return pk_link_write(b->link, b->light, PKB_REG_LIGHT_INT_ACK, d, 2);
}

static pk_status irq_take_locked(pk_boards *b, uint32_t mask, uint32_t *out, uint8_t *value, bool *event) {
    uint8_t v = 0, st = 0;
    pk_status s = pk_link_read_status(b->link, b->light, PKB_REG_LIGHT_INTERRUPT_STATUS, 1, &v, &st);
    if (s != PK_OK) return s;
    if (value) *value = v;
    if (event) *event = (st & 0x80) != 0;
    if (st & 0x80) {                            /* TLB acts on the value only when the status byte says it is an event */
        b->irq_pending |= v;                    /* kept even if the acknowledge fails */
        s = pkb_light_int_ack(b, v);
        if (s != PK_OK) return s;
    }
    *out = b->irq_pending & mask;
    b->irq_pending &= ~mask;
    return PK_OK;
}

pk_status pkb_irq_take_ex(pk_boards *b, uint32_t mask, uint32_t *out, uint8_t *value, bool *event) {
    pthread_mutex_lock(&b->irq_mu);
    pk_status r = irq_take_locked(b, mask, out, value, event);
    pthread_mutex_unlock(&b->irq_mu);
    return r;
}

pk_status pkb_irq_take(pk_boards *b, uint32_t mask, uint32_t *out) { return pkb_irq_take_ex(b, mask, out, NULL, NULL); }

pk_status pk_host_status(pk_boards *b, uint8_t *status) {
    if (!b || !status) return PK_E_ARG;
    uint8_t d[2];
    return pk_link_poll_status(b->link, b->host, d, status);
}

pk_status pk_motor_irq_service(pk_boards *b, uint8_t *value) {
    if (!b) return PK_E_ARG;
    uint8_t v = 0, st = 0;
    pk_status s = pk_link_read_status(b->link, b->motor, PKB_REG_LIGHT_INTERRUPT_STATUS, 1, &v, &st);
    if (s != PK_OK) return s;
    if (value) *value = v;
    if (st & 0x80) {
        uint8_t d[2] = { 0x00, v ? v : 0xFF };      /* the same acknowledge TLB sends to the light board */
        s = pk_link_write(b->link, b->motor, PKB_REG_LIGHT_INT_ACK, d, 2);
    }
    return s;
}

pk_status pk_host_interrupt_status(pk_boards *b, uint32_t *out) {
    if (!b || !out) return PK_E_ARG;
    uint32_t none;
    pk_status s = pkb_irq_take(b, 0u, &none);     /* a peek: reads (and acknowledges) but takes nothing */
    if (s == PK_OK) { pthread_mutex_lock(&b->irq_mu); *out = b->irq_pending; pthread_mutex_unlock(&b->irq_mu); }
    return s;
}
