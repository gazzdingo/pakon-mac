/* Boards: film guides and pressure rollers (Task 9, spec D; BETA, F-235 / F-335). Ported from the TLA decompile
 * (FUN_1000F5A0 = FN_bDrvMoveFilmPressureRollers, FUN_1000FFB0 = FN_bDrvMoveFilmGuides, FUN_1000DB50 / FUN_1000DAB0 packet builders).
 * The link refuses the guide role until Task 21 maps the F-235 / F-335 boards, so nothing here reaches the wire yet. */
#include "boards/boards.h"

#define PKB_GUIDE_REG_ROLLER 0xEE
#define PKB_GUIDE_CMD_35MM 0xE0
#define PKB_GUIDE_CMD_24MM 0xE1
#define PKB_ROLLER_SETTLE_MS 1500u            /* Sleep(0x5DC) */

void pk_boards_set_guide_fault_cb(pk_boards *b, pk_guide_fault_cb cb, void *user) {
    if (!b) return;
    b->guide_cb = cb;
    b->guide_cb_user = user;
}

/* v: 0..3. Writes only when it differs from the cache (FUN_1000F5A0); settles 1500 ms after a write. */
static pk_status set_rollers(pk_boards *b, unsigned v) {
    uint8_t a = b->model->roles.guide;
    if (v > 3) return PK_E_ARG;
    if (b->roller_cache == (int)v) return PK_OK;
    uint8_t d = (uint8_t)v;
    pk_status s = pk_link_write(b->link, a, PKB_GUIDE_REG_ROLLER, &d, 1);
    if (s != PK_OK) { b->roller_cache = PKB_ROLLER_UNKNOWN; return s; }   /* TLA caches before the write; we do not trust it after a failure */
    b->roller_cache = (int)v;
    pkb_sleep_ms(PKB_ROLLER_SETTLE_MS);
    return PK_OK;
}

pk_status pk_pressure_rollers(pk_boards *b, bool engage) {
    if (!b) return PK_E_ARG;
    if (!(b->model->caps & PK_CAP_ROLLERS) || !b->model->roles.guide) return PK_E_UNSUPPORTED;
    return set_rollers(b, engage ? 3u : 0u);
}

pk_status pk_film_guide_set(pk_boards *b, pk_film_format f) {
    if (!b) return PK_E_ARG;
    if (f != PK_FILM_35MM && f != PK_FILM_24MM) return PK_E_ARG;
    if (!(b->model->caps & PK_CAP_GUIDES) || !b->model->roles.guide) return PK_E_UNSUPPORTED;
    /* FUN_1000FFB0: rollers to 3 on scanner types below 1000 (F-235), to 0 from 1000 up (F-335). */
    pk_status s = set_rollers(b, b->model->scanner_type[0] < 1000u ? 3u : 0u);
    if (s != PK_OK) return s;
    bool was_moved = b->guide_moved;
    s = pk_link_command(b->link, b->model->roles.guide, f == PK_FILM_35MM ? PKB_GUIDE_CMD_35MM : PKB_GUIDE_CMD_24MM);
    if (s != PK_OK) return s;
    b->guide_pos = (int)f;
    b->guide_moved = true;
    if (was_moved && b->guide_cb) b->guide_cb(b->guide_cb_user);      /* HARDWARE_CB_MOTOR_FILM_GUIDE */
    return PK_OK;
}

pk_status pk_film_guide_get(pk_boards *b, pk_film_format *out) {
    if (!b || !out) return PK_E_ARG;
    if (!(b->model->caps & PK_CAP_GUIDES)) return PK_E_UNSUPPORTED;
    if (b->guide_pos < 0) return PK_E_NOT_FOUND;
    *out = (pk_film_format)b->guide_pos;
    return PK_OK;
}
