#define _POSIX_C_SOURCE 200809L
/* Boards: film transport (Task 9, spec A). Ported from TLB FN_bDriveMotorAdvanceFilm (0x1000B6D0) / FN_bDriveMotorStop (0x1000A440)
 * and v1 set_motor_speed / motor_forward / motor_reverse / motor_stop. There is no jog (S-R15, PSI has none): a move runs at the
 * board's maximum speed until Stop or max_ms. Eject is PSI's: one AdvanceFilm(500 ms, 1000) push (S-R24). */
#include "boards/boards.h"
#include <time.h>

unsigned long long pkb_now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (unsigned long long)ts.tv_sec * 1000ull + (unsigned long long)(ts.tv_nsec / 1000000L);
}

#define PKB_FILM_MAX_MS 300000u          /* PSI / TLB AdvanceFilm validates 1..300000 */
#define PKB_FILM_SLICE_MS 50u            /* stop-flag granularity */
#define PKB_EJECT_MS 500u                /* PSI EjectFilm = AdvanceFilm(500, 1000): PTS ScannerSettings.EjectFilm, types 0x546 / 0x547 */
#define PKB_EJECT_SPEED 1000             /* PSI passes speed 1000 to AdvanceFilm, which stores x100 = 100000 and TLB clamps it to the maximum (0x7FFE Plus, 0x251C base); HW-1 2026-10-19: register 1000 did not move the film */
#define PKB_SENSE_EXIT 0x10
#define PKB_SENSE_ENTRY 0x20
#define PKB_SENSE_EMULSION 0x40
#define PKB_SENSE_TAIL 0x80

unsigned pkb_speed_register(const pk_model *m, int v) {
    bool plus = m && m->roles.motor == 0x44;           /* TLB: board byte +0x130 == 'D' */
    long long lo = plus ? 1000 : 400, hi = plus ? 32766 : 9500;
    if (v == 0) return (unsigned)hi;
    long long r = (long long)v * 100;                  /* TLB AdvanceFilm stores speed x 100.0 */
    if (r < lo) r = lo;
    if (r > hi) r = hi;
    return (unsigned)r;
}

static pk_status nibble_locked(pk_boards *b, uint8_t dx, uint8_t *nibble);

pk_status pkb_dx_status_nibble(pk_boards *b, uint8_t *nibble) {
    if (!b || !nibble) return PK_E_ARG;
    uint8_t dx = b->model->roles.dx;
    if (!dx) return PK_E_UNSUPPORTED;
    pthread_mutex_lock(&b->nib_mu);                    /* film_sense may run beside the session worker (S-R30 m3) */
    pk_status r = nibble_locked(b, dx, nibble);
    pthread_mutex_unlock(&b->nib_mu);
    return r;
}

static pk_status nibble_locked(pk_boards *b, uint8_t dx, uint8_t *nibble) {
    uint32_t st = 0;
    pk_status s = pkb_irq_take(b, 0xA4u, &st);
    if (s != PK_OK) return s;
    if ((st & 0xA4u) != 0 || b->dx_nibble < 0) {       /* same gate as pk_dx_poll; nothing known yet reads once */
        uint8_t buf[PKB_LIGHT_DX_LEN];
        s = pk_link_read(b->link, dx, PKB_REG_LIGHT_DX, PKB_LIGHT_DX_LEN, buf);
        if (s != PK_OK) return s;
        if (buf[2]) b->dx_rec_seq++;
        b->dx_nibble = buf[2] ? (int)(buf[3] & 0xf0) : (b->dx_nibble < 0 ? 0 : b->dx_nibble);   /* pk_dx_poll: buf[3] & 0xf0 when the packet has a record */
    }
    *nibble = (uint8_t)b->dx_nibble;
    return PK_OK;
}

pk_status pk_film_sense(pk_boards *b, pk_film_sensors *out) {
    if (!b || !out) return PK_E_ARG;
    uint8_t n = 0;
    pk_status s = pkb_dx_status_nibble(b, &n);
    if (s != PK_OK) return s;
    out->exit = (n & PKB_SENSE_EXIT) != 0;
    out->entry = (n & PKB_SENSE_ENTRY) != 0;
    out->emulsion_down = (n & PKB_SENSE_EMULSION) != 0;
    out->tail_first = (n & PKB_SENSE_TAIL) != 0;
    return PK_OK;
}

pk_status pk_film_stop(pk_boards *b) {
    if (!b) return PK_E_ARG;
    pthread_mutex_lock(&b->film_mu);
    if (b->film_moving) b->film_stop_req = true;
    pk_status s = pk_motor_stop(b);
    pthread_mutex_unlock(&b->film_mu);
    return s;
}

bool pk_film_is_moving(pk_boards *b) {
    if (!b) return false;
    pthread_mutex_lock(&b->film_mu);
    bool m = b->film_moving;
    pthread_mutex_unlock(&b->film_mu);
    return m;
}

static pk_status run(pk_boards *b, pk_film_dir dir, unsigned max_ms, unsigned reg) {
    if (max_ms == 0) max_ms = PKB_FILM_MAX_MS;
    if (max_ms > PKB_FILM_MAX_MS) return PK_E_ARG;
    pthread_mutex_lock(&b->film_mu);
    if (b->film_moving) { pthread_mutex_unlock(&b->film_mu); return PK_E_BUSY; }
    b->film_moving = true;
    b->film_stop_req = false;
    uint8_t d[2] = { (uint8_t)(reg & 0xFF), (uint8_t)(reg >> 8) };
    pk_status s = pk_link_write(b->link, b->motor, PKB_REG_MOTOR_SPEED, d, 2);
    if (s == PK_OK) s = pk_link_command(b->link, b->motor, dir == PK_FILM_FORWARD ? PKB_CMD_MOTOR_FORWARD : PKB_CMD_MOTOR_REVERSE);
    if (s != PK_OK) {                                   /* the speed may be set without the start: make sure it is stopped */
        if (!pkb_status_is_final(s)) (void)pk_motor_stop(b);
        b->film_moving = false;
        pthread_mutex_unlock(&b->film_mu);
        return s;
    }
    pthread_mutex_unlock(&b->film_mu);

    unsigned long long t0 = pkb_now_ms();
    pk_status result = PK_OK;
    bool stopped_by_other = false;
    for (;;) {
        pthread_mutex_lock(&b->film_mu);
        stopped_by_other = b->film_stop_req;
        pthread_mutex_unlock(&b->film_mu);
        if (stopped_by_other) { result = PK_E_CANCELLED; break; }
        unsigned long long now = pkb_now_ms();
        if (now - t0 >= max_ms) { result = PK_OK; break; }
        pkb_sleep_ms(PKB_FILM_SLICE_MS);
    }
    pthread_mutex_lock(&b->film_mu);
    {                                                   /* always our own stop (TLB FUN_1000B6D0 does), even after pk_film_stop's: A2 is idempotent and its send may have failed */
        pk_status ss = pk_motor_stop(b);
        if (ss != PK_OK && (result == PK_OK || result == PK_E_TIMEOUT || result == PK_E_CANCELLED)) result = ss;
    }
    b->film_moving = false;
    b->film_stop_req = false;
    pthread_mutex_unlock(&b->film_mu);
    return result;
}

pk_status pk_film_start_register(pk_boards *b, pk_film_dir dir, unsigned reg) {
    if (!b || (dir != PK_FILM_FORWARD && dir != PK_FILM_REVERSE)) return PK_E_ARG;
    bool plus = b->model && b->model->roles.motor == 0x44;
    unsigned lo = plus ? 1000u : 400u, hi = plus ? 0x7FFEu : 0x251Cu;
    if (reg < lo) reg = lo;
    if (reg > hi) reg = hi;
    pthread_mutex_lock(&b->film_mu);
    if (b->film_moving) { pthread_mutex_unlock(&b->film_mu); return PK_E_BUSY; }
    uint8_t d[2] = { (uint8_t)(reg & 0xFF), (uint8_t)(reg >> 8) };
    pk_status s = pk_link_write(b->link, b->motor, PKB_REG_MOTOR_SPEED, d, 2);
    if (s == PK_OK) s = pk_link_command(b->link, b->motor, dir == PK_FILM_FORWARD ? PKB_CMD_MOTOR_FORWARD : PKB_CMD_MOTOR_REVERSE);
    if (s != PK_OK && !pkb_status_is_final(s)) (void)pk_motor_stop(b);   /* the speed may be set without the start: make sure it is stopped */
    pthread_mutex_unlock(&b->film_mu);
    return s;
}

pk_status pk_film_move(pk_boards *b, pk_film_dir dir, unsigned max_ms, int speed) {
    if (!b || speed < 0 || (dir != PK_FILM_FORWARD && dir != PK_FILM_REVERSE)) return PK_E_ARG;
    return run(b, dir, max_ms, pkb_speed_register(b->model, speed));
}

/* TLB FUN_1000B6D0 takes the register value as is (clamped 1000..0x7FFE on the Plus, 400..0x251C on the base board); PSI passes e.g. MotorSpeedPlus = 5917. */
pk_status pk_film_move_register(pk_boards *b, pk_film_dir dir, unsigned max_ms, unsigned reg) {
    if (!b || (dir != PK_FILM_FORWARD && dir != PK_FILM_REVERSE)) return PK_E_ARG;
    bool plus = b->model && b->model->roles.motor == 0x44;
    unsigned lo = plus ? 1000u : 400u, hi = plus ? 0x7FFEu : 0x251Cu;
    return run(b, dir, max_ms, reg < lo ? lo : reg > hi ? hi : reg);
}

pk_status pk_film_eject(pk_boards *b) {
    if (!b) return PK_E_ARG;
    return run(b, PK_FILM_FORWARD, PKB_EJECT_MS, pkb_speed_register(b->model, PKB_EJECT_SPEED));
}
