#define _POSIX_C_SOURCE 200809L
/* The idle status thread (RE 47 sec 5.3, ruling S-R48). TLB's status thread never stops: with no scan it waits 200 ms between passes (RE 42 sec 9) and each pass reads HOST status, the light board's
 * register 0x02 (+ the 0x06 acknowledge), 0x90 when the event path asks for it, the lamp judgement, and re-evaluates the held film-LED phase (FUN_1000C420). This thread is that loop for an open
 * session between runs:
 *   - it runs only while no worker is active (state IDLE) and no manual control other than a film move owns the boards; pks_claim and the worker's start wait for a poll in progress (idle_active),
 *     so a poll never overlaps the lamp, LED, calibration or scan code. A manual film move or eject runs beside it (film_manual): both only use the link, which serialises each exchange, and the
 *     lamp keep-alive must not stop for the 300 s a move may last;
 *   - the "remove film" hold (keep_film_led, film LED 0x4C) is released here: once a 0x90 record NEWER than the hold shows both sensors clear, the LED goes to phase 0 (0x40). A pass that reads no
 *     record leaves the old sensor bits, exactly as FUN_10009790 does, so the LED keeps blinking until the film is really seen to be gone. No timer is used.
 * Whether the light board still produces sensor records after DX-off (0x92) is UNKNOWN (RE 47 U2): this thread starts no DX scan (TLB does not), so if it does not, nothing here can see the film go.
 * Nothing is written to scanner memory and no 0x08 / 0x94..0x98 is sent. */
#include "session/session_internal.h"

#define LOAD(p) __atomic_load_n(&(p), __ATOMIC_SEQ_CST)
#define STORE(p, v) __atomic_store_n(&(p), (v), __ATOMIC_SEQ_CST)

void pks_hold_film_led(pk_session *s) {
    pthread_mutex_lock(&s->b->nib_mu);
    s->hold_seq = s->b->dx_rec_seq;
    pthread_mutex_unlock(&s->b->nib_mu);
    STORE(s->keep_film_led, true);
}

bool pk_session_idle_alive(pk_session *s) { return s && s->idle_started && !LOAD(s->idle_dead); }

bool pk_session_remove_film_pending(pk_session *s) { return s && LOAD(s->keep_film_led) && pks_state(s) == PK_S_IDLE && !LOAD(s->idle_dead); }

/* FUN_1000C420 at idle: the hold ends when a fresh record has both the entry (0x20) and exit (0x10) sensor bits clear. */
static pk_status release_hold(pk_session *s) {
    pk_boards *b = s->b;
    if (!LOAD(s->keep_film_led)) return PK_OK;
    pthread_mutex_lock(&b->nib_mu);
    unsigned seq = b->dx_rec_seq;
    int nib = b->dx_nibble;
    pthread_mutex_unlock(&b->nib_mu);
    if (seq == s->hold_seq || nib < 0 || (nib & 0x30)) return PK_OK;
    pk_status st = pk_film_led(b, PK_FILMLED_OFF);
    if (st == PK_OK) STORE(s->keep_film_led, false);
    return st;
}

/* One pass: TLB's FUN_1000BDD0 for the idle case. Light 0x02 is read every pass (as the warm-up and the keep-alive do at 200 ms); 0x90 follows an event or an A4 bit. */
static pk_status idle_poll(pk_session *s) {
    pk_boards *b = s->b;
    uint8_t hs = 0;
    pk_status st = pk_host_status(b, &hs);
    if (st != PK_OK) return st;
    if (LOAD(s->idle_stop)) return PK_OK;                      /* close is waiting: no more transfers than needed */
    uint32_t taken = 0;
    bool ev = false;
    st = pkb_irq_take_ex(b, 0x5Bu | 0xA4u, &taken, NULL, &ev);
    if (st != PK_OK) return st;
    if (LOAD(s->idle_stop)) return PK_OK;
    if (b->lamp_on) {
        st = pkb_lamp_monitor(b, taken & 0x5Bu, false, NULL);
        if (st != PK_OK) return st;
    }
    if (ev || (taken & 0xA4u)) {
        pk_dx *dx = NULL;
        if (pk_dx_new(&dx) == PK_OK) {
            uint8_t nib = 0;
            st = pk_dx_read_packet(b, dx, &nib);
            pk_dx_free(dx);
            if (st != PK_OK) return st;
        }
    }
    if (hs & 0x80) {                                           /* the host still reports an interrupt: the motor board's share */
        st = pk_motor_irq_service(b, NULL);
        if (st != PK_OK) return st;
    }
    if (b->lamp_on && !s->opts.no_keepalive) {                 /* lamp keep-alive: the 0x83 / 0x84 / 0x88 telemetry pass of the scan loop */
        pk_light_health h;
        st = pk_light_health_poll(b, &h);
        if (st != PK_OK) return st;
    }
    return release_hold(s);
}

static void *idle_main(void *arg) {
    pk_session *s = (pk_session *)arg;
    pk_link_set_thread_cap(PKS_IDLE_XFER_MS);                  /* S-R29: this thread's transfers are short and single-attempt, so close and claims never wait long behind one */
    unsigned long long next = pkb_now_ms() + PKS_IDLE_POLL_MS;
    while (!LOAD(s->idle_stop)) {
        while (!LOAD(s->idle_stop) && pkb_now_ms() < next) pkb_sleep_ms(10);
        if (LOAD(s->idle_stop)) break;
        next += PKS_IDLE_POLL_MS;
        unsigned long long now = pkb_now_ms();
        if (next < now) next = now + PKS_IDLE_POLL_MS;            /* fell behind (a long poll): no burst of catch-up polls */
        pthread_mutex_lock(&s->mu);
        bool go = !s->running && pks_state(s) == PK_S_IDLE && (!s->hw_busy || s->film_manual);
        if (go) s->idle_active = true;
        pthread_mutex_unlock(&s->mu);
        if (!go) continue;
        pk_status st = idle_poll(s);
        s->idle_polls++;
        pthread_mutex_lock(&s->mu);
        s->idle_active = false;
        pthread_cond_broadcast(&s->cv);
        pthread_mutex_unlock(&s->mu);
        if (pkb_status_is_final(st)) {                            /* the scanner is gone, or a write was refused: stop polling a dead link; nothing can release the hold now */
            STORE(s->keep_film_led, false);
            STORE(s->idle_dead, 1);
            break;
        }
    }
    return NULL;
}

void pks_idle_start(pk_session *s) {
    if (s->idle_started) return;
    STORE(s->idle_stop, 0);
    STORE(s->idle_dead, 0);
    s->idle_started = pthread_create(&s->idle_th, NULL, idle_main, s) == 0;
}

void pks_idle_stop(pk_session *s) {
    if (!s->idle_started) return;
    STORE(s->idle_stop, 1);
    pthread_join(s->idle_th, NULL);
    s->idle_started = false;
}
