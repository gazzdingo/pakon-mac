/* Boards: status LED, film LED, LED reset (Task 9, spec B). Ported from TLB FN_bDrvSetLed (FUN_1000C1F0, table checked against the
 * decompile) and FN_bStateMachineLedFilm (FUN_1000C420). The packet is the FPGA-style register 0x82 index 9 write on the motor
 * board: 02 06 <board> 03 82 09 <lo> <hi> (v1 write_ccd_register shape). */
#include "boards/boards.h"

uint16_t pkb_led_word(uint16_t old, pk_led_which which, unsigned code, bool *ok) {
    static const struct { unsigned code; uint16_t smask, sset, fmask, fset; } T[] = {
        { 0x0, 0xFCFF, 0x000C, 0xFF3F, 0x0003 },
        { 0x1, 0xFCFB, 0x0008, 0xFF3E, 0x0002 },
        { 0x2, 0xFCF7, 0x0004, 0xFF3D, 0x0001 },
        { 0x3, 0xFCF3, 0x0000, 0xFF3C, 0x0000 },
        { 0x4, 0xFDFB, 0x0108, 0xFF7E, 0x0042 },
        { 0x8, 0xFEF7, 0x0204, 0xFFBD, 0x0081 },
        { 0xC, 0xFFF3, 0x0300, 0xFFFC, 0x00C0 },
    };
    if (ok) *ok = false;
    if (which != PK_LED_STATUS && which != PK_LED_FILM) return old;
    for (size_t i = 0; i < sizeof T / sizeof T[0]; i++)
        if (T[i].code == code) {
            if (ok) *ok = true;
            return which == PK_LED_STATUS ? (uint16_t)((old & T[i].smask) | T[i].sset) : (uint16_t)((old & T[i].fmask) | T[i].fset);
        }
    return old;
}

uint8_t pkb_film_led_control(pk_filmled s) {
    switch (s) {
    case PK_FILMLED_OFF: return 0x40;
    case PK_FILMLED_FOUND: return 0x42;
    case PK_FILMLED_WAITING: return 0x48;
    case PK_FILMLED_REMOVE: return 0x4C;
    }
    return 0xFF;
}

pk_status pk_leds_enable(pk_boards *b, bool on) {
    if (!b) return PK_E_ARG;
    b->led.enabled = on;
    return PK_OK;
}

pk_status pk_led_set(pk_boards *b, pk_led_which which, unsigned code) {
    if (!b) return PK_E_ARG;
    bool ok;
    uint16_t w = pkb_led_word(b->led.shadow, which, code, &ok);
    if (!ok) return PK_E_ARG;
    if (!b->led.enabled || !b->led_gate) return PK_OK;  /* TlaControlLeds == 0, or the 0x97 gate not open: TLB returns success without writing */
    if (w != b->led.shadow) {
        uint8_t d[3] = { 9, (uint8_t)(w & 0xFF), (uint8_t)(w >> 8) };
        pk_status s = pk_link_write(b->link, b->motor, PKB_REG_CCD_FPGA, d, 3);
        if (s != PK_OK) return s;
        b->led.shadow = w;
    }
    if (which == PK_LED_STATUS) b->status_led_code = (int)code;
    return PK_OK;
}

pk_status pk_film_led(pk_boards *b, pk_filmled state) {
    if (!b) return PK_E_ARG;
    uint8_t c = pkb_film_led_control(state);
    if (c == 0xFF) return PK_E_ARG;
    return pk_led_set(b, PK_LED_FILM, c & 0x3Fu);
}

pk_status pk_leds_reset(pk_boards *b) {
    if (!b) return PK_E_ARG;
    /* TLB flags &= 0xC40548C0 keeps the fault bits and drops the warnings. */
    b->sticky &= PK_LIGHT_F_FAULT | PK_LIGHT_F_LAMP_FAULT | PK_LIGHT_F_MAIN_FAULT | PK_LIGHT_F_STATUS0;
    uint32_t ir = 0;
    pk_status s = pkb_irq_take(b, 0x5Bu, &ir);       /* TLB's forced path reads (and acknowledges) 0x02 first */
    if (s != PK_OK) return s;
    s = pkb_lamp_monitor(b, ir, true, NULL);         /* the forced poll: 0x83 read, bands judged only when 0x83 bit 3 */
    if (s != PK_OK) return s;
    if (b->status_led_code == 2 || b->status_led_code == 4)   /* ready / pending: re-evaluate; scanning and calibrating are left alone */
        return pk_led_set(b, PK_LED_STATUS, b->sticky ? 4u : 2u);
    return PK_OK;
}

pk_status pk_boards_open_led_gate(pk_boards *b) {
    if (!b) return PK_E_ARG;
    uint8_t one = 1;
    pk_status s = pk_link_write(b->link, b->motor, 0x97, &one, 1);   /* MOTOR_REG_97 (allowed): TLB FUN_1001C3E0 writes it at session open */
    if (s == PK_OK) b->led_gate = true;
    return s;
}
