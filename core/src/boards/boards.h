#ifndef PAKON_BOARDS_INTERNAL_H
#define PAKON_BOARDS_INTERNAL_H
/* Internal to the boards module (pkb_ prefix). */
#include <pthread.h>
#include "pakon/boards.h"

/* Constants copied from v1 tools/pakon_commands.py and tools/pakon_scan.py (not invented). */
#define PKB_REG_LIGHT_STATUS 0x83
#define PKB_LIGHT_STATUS_LEN 1
#define PKB_REG_LIGHT_TEMPERATURE 0x84        /* 2 bytes, little-endian, 1/16 degC: the temperature SETPOINT readback (see boards.h) */
#define PKB_LIGHT_TEMPERATURE_LEN 2
#define PKB_REG_LIGHT_TEMPS 0x88              /* 4 bytes: measured lamp board, measured main board, u16 LE, 1/16 degC */
#define PKB_LIGHT_TEMPS_LEN 4
#define PKB_REG_LIGHT_DX 0x90
#define PKB_LIGHT_DX_LEN 0x1E
#define PKB_LAMP_TEMP_WORKING_MIN 0x250
#define PKB_LAMP_TEMP_WORKING_MAX 0x300
#define PKB_CMD_LIGHT_FIFO_RESET 0x8A
#define PKB_CMD_LIGHT_DX_STOP 0x92

#define PKB_REG_LIGHT_INTERRUPT_STATUS 0x02
#define PKB_REG_LIGHT_INT_ACK 0x06
#define PKB_REG_LIGHT_LAMP_ENABLE 0x80
#define PKB_REG_LIGHT_LED_LEVELS 0x81
#define PKB_REG_LIGHT_LED_DUTY 0x82
#define PKB_REG_LIGHT_89 0x89
#define PKB_REG_LIGHT_TEMP_8B 0x8B
#define PKB_REG_LIGHT_TEMP_8C 0x8C
#define PKB_REG_LIGHT_TEMP_8D 0x8D
#define PKB_REG_LIGHT_TEMP_8F 0x8F
#define PKB_REG_LIGHT_D0 0xD0
#define PKB_REG_LIGHT_D1 0xD1
#define PKB_LAMP_STATUS_FAULT_MASK 0x60
#define PKB_LAMP_STATUS_TEMP_VALID 0x08
#define PKB_LAMP_STATUS_STABLE 0x02          /* 0x83 bit 1: lamp stable (cleared by a lamp change) */
#define PKB_LAMP_STATUS_LEVELS_ZERO 0x10     /* 0x83 bit 4: all four LED levels zero (nl050A 0x106.4) */
#define PKB_REG_LIGHT_DEVINFO_SELECT 0x03
#define PKB_REG_LIGHT_DEVINFO 0x07
#define PKB_LIGHT_DEVINFO_LEN 12
#define PKB_REG_LIGHT_87 0x87
#define PKB_LAMP_OFF_ATTEMPTS 4              /* v1 LAMP_OFF_ATTEMPTS; the motor stop uses the same count */
#define PKB_RETRY_PAUSE_MS 50                /* v1 sleeps 0.05 s between lamp-off attempts */

#define PKB_REG_MOTOR_SPEED 0xA5
#define PKB_CMD_MOTOR_FORWARD 0xA0
#define PKB_CMD_MOTOR_REVERSE 0xA1
#define PKB_CMD_MOTOR_STOP 0xA2

#define PKB_REG_HOST_FIFO_RESET 0x84
#define PKB_HOST_FIFO_RESET_VALUE 0x02
#define PKB_REG_CCD_FPGA 0x82
#define PKB_REG_CCD_ADC 0x84
#define PKB_FPGA_CONTROL 0x00
#define PKB_FPGA_PIXEL_OFFSET 0x04
#define PKB_FPGA_PIXEL_END 0x05
#define PKB_FPGA_INTEGRATION 0x06
#define PKB_FPGA_IDX_0A 0x0A
#define PKB_FPGA_IDX_0B 0x0B
#define PKB_FPGA_CTRL_ACQUIRE 0x001
#define PKB_FPGA_CTRL_MASK 0x3FF
#define PKB_ADC_GAIN_MAX 0x3F
#define PKB_ADC_OFFSET_MAX 255
#define PKB_ADC_OFFSET_SIGN 0x100
#define PKB_INTEGRATION_MAX 0xFFD

struct pk_boards {
    pk_link *link;
    const pk_model *model;
    uint8_t light, motor, host;     /* addresses from model->roles */
    int fpga_ctrl;                  /* shadow of FPGA control (bit 0 = acquire); -1 until pk_host_ccd_configure */
    int light_89;                   /* last value written to light register 0x89; -1 = none yet */
    bool ccd_known;                 /* the CCD / AFE shadows below hold what the boards were last given (pk_host_ccd_update is change-only on them) */
    unsigned ccd_off, ccd_end, ccd_int, ccd_ctrl;   /* FPGA index 4, 5, 6 and the control word */
    unsigned afe_gain[3], afe_off[3];               /* AD9826 index 2..4 and the offset words of index 5..7 */
    bool lamp_lv_known, lamp_duty_known;            /* shadows of light registers 0x81 and 0x82 as last written (TLB changed-value-only sends, RE 41 row 12) */
    uint16_t lamp_lv[4];                            /* R, G, B, IR drive steps */
    uint16_t lamp_on_cnt[4], lamp_period;           /* R, G, B, IR on-counts and the period */
    bool scan_duty_set;
    uint16_t scan_on[4];            /* R, G, B, IR */
    uint16_t scan_period;
    /* Task 9 */
    bool leave_mode;                /* S-R29: single attempts in the lamp-off / motor-stop retry loops */
    pthread_mutex_t irq_mu, nib_mu; /* irq_pending (pkb_irq_take_ex); dx_nibble: so film_sense may run beside the worker (S-R30 m3) */
    pthread_mutex_t film_mu;        /* serialises the film mover's packets with pk_film_stop (the only cross-thread call) */
    bool film_moving, film_stop_req;   /* under film_mu */
    int dx_nibble;                  /* last DX status nibble (0x10 exit .. 0x80 tail first); -1 until read */
    unsigned dx_rec_seq;            /* counts the 0x90 packets that carried a record (each one refreshes dx_nibble); under nib_mu. The remove-film hold releases only on a record newer than itself */
    pk_led_state led;               /* shadow word of FPGA index 9 (lamp_obj+0x68 in TLB; starts 0) and the TlaControlLeds gate */
    int status_led_code;            /* last status-LED code commanded; -1 none */
    uint32_t sticky;                /* OR of the PK_LIGHT_F_* flags pk_light_health_poll has seen since the last pk_leds_reset */
    unsigned lamp_standby_s, lamp_off_s;   /* pk_lamp_saver (stored; fired by the session) */
    int roller_cache;               /* 0..3, or PKB_ROLLER_UNKNOWN */
    int guide_pos;                  /* pk_film_format, or -1 */
    bool guide_moved;               /* TLA flag +0x2C4 bit 3 */
    int light_fw_ver;               /* devinfo[2] of the light board = its hardware version byte (TLB cfg+0x47C, FUN_1001C3E0 at 0x1001C744), -1 until read */
    uint32_t irq_pending;           /* register 0x02 bits read (and acknowledged) but not yet taken by a consumer (lamp 0x5B, DX 0xA4) */
    int lamp_state;                 /* TLB lamp object +0xD0: -1 at construction, 0, then latched 1 = stable */
    bool led_gate;                  /* TLB lamp object +0xC0, opened by pk_boards_open_led_gate */
    uint8_t lamp_mask;              /* the light register 0x80 value last written by pk_light_lamp_on (1 visible, 2 IR); 0 after a lamp-off */
    bool lamp_on;                   /* a lamp-on write succeeded and no lamp-off since (TLB this+0xD4) */
    pk_guide_fault_cb guide_cb;
    void *guide_cb_user;
};
#define PKB_ROLLER_UNKNOWN (-1)     /* TLA marks the cache invalid with 0x80000000 */
#define PKB_WARMUP_STABLE_BIT 0x02  /* register 0x02 / 0x83 bit 1 (TLB FUN_1000B890 / FUN_1000BDD0 set lamp+0xD0 from it) */

/* The guarded transport under the boards' link (borrowed): the calibration stream and the calibration-chip read (Task 15, C32). */
pk_transport *pk_boards_transport(pk_boards *);

/* Monotonic milliseconds. */
unsigned long long pkb_now_ms(void);
/* The DX status nibble (spec A): register 0x02, then 0x90 when its DX bits 0xA4 are pending; cached. */
pk_status pkb_dx_status_nibble(pk_boards *, uint8_t *nibble);
/* Pure helpers (spec A, B, C). */
uint8_t pkb_film_led_control(pk_filmled);
/* TLB's gated lamp judgement (FUN_1000BDD0 / FUN_1000B890): see lamp.c. ir = register 0x02 value; forced = ResetStatusLeds poll. */
pk_status pkb_lamp_monitor(pk_boards *, uint32_t ir, bool forced, pk_light_health *last /* may be NULL */);
/* All 12 devinfo bytes of the light board (write 0x03 = 1, read 0x07 x12); also fills the cached hardware version. */
pk_status pkb_light_devinfo(pk_boards *, uint8_t out[12]);
/* The retry count of the lamp-off and motor-stop loops: PKB_LAMP_OFF_ATTEMPTS, or 1 in leave mode. */
int pkb_attempts(const pk_boards *);
/* devinfo[2] of the light board (write 0x03 = 1, read 0x07 x12), cached. */
pk_status pkb_light_fw_version(pk_boards *, int *out);
/* Light-board register 0x02 as TLB reads it (FUN_1000BDD0): when the response status byte has bit 7, acknowledge with 0x06 = [00, v] (0xFF if v is 0) and
 * take v as a one-shot event; with bit 7 clear the value is not an event. The bits read accumulate in irq_pending; this returns and clears the bits in mask. */
pk_status pkb_irq_take(pk_boards *, uint32_t mask, uint32_t *out);
/* The same, also returning the raw register-0x02 value and whether the status byte flagged it an event (bit 7); either pointer may be NULL. */
pk_status pkb_irq_take_ex(pk_boards *, uint32_t mask, uint32_t *out, uint8_t *value, bool *event);
/* The acknowledge, in the only form TLB sends: [0x00, v]. The data[0] != 0 form raises interrupts and is never built. */
pk_status pkb_light_int_ack(pk_boards *, uint8_t v);
#define PKB_LED_SHADOW_INIT 0x10    /* TLB lamp-object constructor FUN_1000AE30 at 0x1000AF7A; PSI's wire words all carry it */


/* Sleeps ms milliseconds (no state). */
void pkb_sleep_ms(unsigned ms);
/* True for the statuses a retry cannot help (refused, wedged, disconnected): the retry loops stop at once. */
bool pkb_status_is_final(pk_status s);

/* The CCD window TLB uses for a base (RE 29 sec 12), from the model's ccd_px_offset / ccd_px_height. PK_E_UNSUPPORTED when the
 * model has none (beta models) or lacks the base. Used by pkb_ccd_cfg_from (Task 13). */
typedef struct { uint16_t px_offset, px_height; bool binned; uint8_t light_89; } pkb_ccd_window;
pk_status pkb_ccd_window_for(const pk_model *, int dpi_base, pkb_ccd_window *out);

/* Builds the pk_ccd_cfg of a scan from the light settings plus the model's per-base window (ruling C63): the one place a pk_ccd_cfg is made
 * (core/src/boards/ccd_cfg.c). PK_E_UNSUPPORTED when the base has no window, PK_E_ARG for bad light settings. The control word is TLB's 0x0060. */
struct pk_cal_light;
pk_status pkb_ccd_cfg_from(const pk_model *, const struct pk_cal_light *, int dpi_base, pk_ccd_cfg *out);
/* TLB's PWM period for an integration value: trunc(integration x 10^6 / (2 x 2083333.3)) (982 at 0xFFD; RE 41 row 12). */
unsigned pkb_pwm_period(unsigned integration);
/* TLB's on-count for a duty fraction: min(ceil(N x duty), N - 2) (RE 07 sec 1.3). */
unsigned pkb_duty_on_count(unsigned period, double duty);

#endif
