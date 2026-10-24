#define _POSIX_C_SOURCE 200809L
/* The packet link (Task 4): builders, response checks, retries, wedge detection. Every packet is checked by
 * pkl_check_packet before it is handed to the (guarded) transport, which checks it again. Docs: spec section on the link,
 * plan Task 4. Wire formats (v1 docs, wire size = PktLen + 2, no checksum):
 *   READ    01 03 AA NN RR          -> 01 (NN+2) AA SS <NN bytes>
 *   WRITE   02 (NN+3) AA NN RR <..> -> 07 02 AA SS
 *   POLL    03 01 AA                -> 03 04 AA SS <2 bytes>
 *   COMMAND 04 03 AA 00 CC          -> 07 02 AA SS */
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "link/guard.h"

#define EP_CMD_OUT 0x01
#define EP_CMD_IN 0x81
#define LINK_TIMEOUT_MS 2000   /* v1 pakon_scan.py _xfer */
#define RETRIES 2              /* reads, polls and pings: retried twice, as in TLB.dll */
#define PING_CMD 0x00
#define LEAVE_XFER_MS 500      /* leave mode (S-R29): every transfer at most this long */

struct pk_link {
    pk_transport *t;             /* always a guarded transport */
    pk_transport *own_guard;     /* the wrapper this link created around a caller's transport, or NULL */
    pk_link_roles roles;
    pk_error err;
    int need_drain;              /* a transfer failed: EP 0x81 may hold a late reply */
    unsigned long long leave_deadline_ms;   /* leave mode (S-R29): non-zero = monotonic deadline of the whole leave; under mu */
    pthread_mutex_t mu;          /* one exchange at a time (S-R23 I-2): covers the drain and the wedge ping */
};

pk_transport *pkl_link_transport(pk_link *l) { return l ? l->t : NULL; }

size_t pkl_build_read(uint8_t addr, uint8_t reg, uint8_t count, uint8_t out[5]) {
    out[0] = 0x01; out[1] = 0x03; out[2] = addr; out[3] = count; out[4] = reg;
    return 5;
}

size_t pkl_build_command(uint8_t addr, uint8_t cmd, uint8_t out[5]) {
    out[0] = 0x04; out[1] = 0x03; out[2] = addr; out[3] = 0x00; out[4] = cmd;
    return 5;
}

size_t pkl_build_poll(uint8_t addr, uint8_t out[3]) {
    out[0] = 0x03; out[1] = 0x01; out[2] = addr;
    return 3;
}

size_t pkl_build_write(uint8_t addr, uint8_t reg, const uint8_t *data, uint8_t n, uint8_t out[PKL_MAX_OUT]) {
    if (n > 252 || (n && !data)) return 0;   /* PktLen = n + 3 must fit its byte */
    out[0] = 0x02; out[1] = (uint8_t)(n + 3); out[2] = addr; out[3] = n; out[4] = reg;
    if (n) memcpy(out + 5, data, n);
    return (size_t)n + 5;
}

pk_status pkl_check_response(const uint8_t *r, size_t n, uint8_t type, uint8_t expect_addr) {
    uint8_t first, len;
    if (!r || n < 4) return PK_E_PROTOCOL;
    switch (type) {
    case 1: first = 1; break;
    case 3: first = 3; break;
    case 2: case 4: first = 7; break;
    default: return PK_E_ARG;
    }
    if (r[0] != first) return PK_E_PROTOCOL;
    len = r[1];
    if ((size_t)len + 2 > n) return PK_E_PROTOCOL;          /* the length byte promises more than arrived */
    /* type 3: TLB checks no length (FUN_10008d70); this unit's HOST answers len 3 when idle (03 03 10 00 aa) and 4 with data (HW 2026-10-22), so only the
     * address and status bytes are required */
    if (type == 1 ? len < 2 : type == 3 ? len < 2 : len != 2) return PK_E_PROTOCOL;
    if (r[2] != expect_addr) return PK_E_PROTOCOL;
    /* Status. Reads and polls: clean when (s & 0x36) == 0. Evidence: v1 captures dx.jsonl files, 8618 of 8619 light-board read
     * replies carry 0x88; docs/03-protocol.md "Real exchanges" (01 02 40 88 ..); v1 tools/pakon_commands.py:269-272 treats
     * status & 0x36 == 0 as clean (bit 0 = busy/retry). Write/command acks: 0 or 8 (TLB resp[3] == 0; v1 ack table). */
    /* A poll's status byte IS the answer (the HOST's interrupt flag, bit 7, and FIFO-overflow flag, bit 1; v1 documents bit 5 as a sticky host fault): TLB's HOST status read
     * (FUN_10008D70) checks only that reply byte 0 is 3 and tests no other bit (RE 42 sec 5, S-R36), so any status byte is accepted here and the caller decides what the bits mean. */
    if (type == 1 ? (r[3] & 0x36) != 0 : type == 3 ? false : (r[3] != 0 && r[3] != 8)) return PK_E_PROTOCOL;
    return PK_OK;
}

/* ---------------------------------------------------------------- open / close */

pk_status pk_link_open(pk_transport *t, pk_link_model model, pk_link **out) {
    if (out) *out = NULL;
    pk_link_roles rr;
    if (!t || !out) return PK_E_ARG;
    pk_status rs = pkl_roles_for_model(model, &rr);   /* library-owned roles, never the caller's */
    if (rs != PK_OK) return rs;
    const pk_link_roles *roles = &rr;
    const uint8_t fields[] = { roles->light, roles->motor, roles->host, roles->dx, roles->lamp235, roles->motor235,
                               roles->dx235, roles->aps235, roles->guide };
    for (size_t i = 0; i < sizeof fields; i++)
        if (fields[i] != 0 && !PKL_ADDR_OK(fields[i])) return PK_E_ARG;   /* odd, or 0xA0..0xAF: reaches the serial EEPROMs */
    pk_link *l = (pk_link *)calloc(1, sizeof *l);
    if (!l) return PK_E_NOMEM;
    pk_status s = pk_transport_guard_open(t, &l->t);
    if (s != PK_OK) { free(l); return s; }
    if (l->t != t) l->own_guard = l->t;
    pthread_mutex_init(&l->mu, NULL);
    l->roles = *roles;
    pkl_guard_bind_roles(l->t, roles);
    *out = l;
    return PK_OK;
}

void pk_link_close(pk_link *l) {
    if (!l) return;
    pkl_guard_bind_roles(l->t, NULL);
    if (l->own_guard) pk_transport_close(l->own_guard);   /* the wrapper only: it does not own the caller's transport */
    pthread_mutex_destroy(&l->mu);
    free(l);
}

const pk_error *pk_link_last_error(const pk_link *l) { return l ? &l->err : NULL; }

void pk_link_last_error_copy(pk_link *l, pk_error *out) {
    if (!out) return;
    memset(out, 0, sizeof *out);
    if (!l) return;
    pthread_mutex_lock(&l->mu);
    *out = l->err;
    pthread_mutex_unlock(&l->mu);
}

/* ---------------------------------------------------------------- one exchange */

typedef struct { int out_timeout; } xinfo;

static unsigned long long mono_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (unsigned long long)ts.tv_sec * 1000ull + (unsigned long long)(ts.tv_nsec / 1000000L);
}

/* The timeout of the next transfer, ms; 0 = the leave budget is spent (leave mode only). Caller holds mu. */
static __thread unsigned tl_cap_ms;          /* pk_link_set_thread_cap: this thread's transfers are capped and single-attempt */

static unsigned xfer_ms(const pk_link *l) {
    unsigned base = tl_cap_ms && tl_cap_ms < LINK_TIMEOUT_MS ? tl_cap_ms : LINK_TIMEOUT_MS;
    if (!l->leave_deadline_ms) return base;
    unsigned long long now = mono_ms();
    if (now >= l->leave_deadline_ms) return 0;
    unsigned long long rem = l->leave_deadline_ms - now;
    unsigned cap = rem < LEAVE_XFER_MS ? (unsigned)rem : LEAVE_XFER_MS;
    return cap < base ? cap : base;
}

void pk_link_set_thread_cap(unsigned ms) { tl_cap_ms = ms; }

/* The budget is link-wide: calls from other threads during the leave (e.g. film_sense) draw on it and get single 500 ms attempts. */
void pk_link_set_leave_mode(pk_link *l, unsigned budget_ms) {
    if (!l) return;
    pthread_mutex_lock(&l->mu);
    l->leave_deadline_ms = budget_ms ? mono_ms() + budget_ms : 0;
    pthread_mutex_unlock(&l->mu);
}

static pk_status exchange(pk_link *l, const uint8_t *pkt, size_t n, uint8_t type, uint8_t addr, uint8_t *resp,
                          size_t *got, xinfo *xi) {
    *got = 0;
    xi->out_timeout = 0;
    pk_error_push_exchange(&l->err, 1, pkt, n);
    unsigned to = xfer_ms(l);
    if (!to) return PK_E_TIMEOUT;
    pk_status s = pk_t_bulk_out(l->t, EP_CMD_OUT, pkt, n, to);
    if (s == PK_E_TIMEOUT) xi->out_timeout = 1;
    if (s != PK_OK) return s;
    to = xfer_ms(l);
    if (!to) return PK_E_TIMEOUT;
    s = pk_t_bulk_in(l->t, EP_CMD_IN, resp, PKL_RESP_CAP, got, to);
    if (s != PK_OK) { *got = 0; return s; }
    if (*got > PKL_RESP_CAP) *got = PKL_RESP_CAP;
    pk_error_push_exchange(&l->err, 0, resp, *got);
    s = pkl_check_response(resp, *got, type, addr);
    if (s == PK_OK && type == 1 && (resp[1] != (uint8_t)(pkt[3] + 2) || *got < (size_t)pkt[3] + 4)) s = PK_E_PROTOCOL;   /* inside the retry loop */
    return s;
}

/* A reply that arrives after its request timed out would be taken for the answer to the next request (replies carry no
 * register echo), misaligning every later exchange. After any failed transfer, and before the next request, drain EP 0x81
 * with bounded short reads (at most DRAIN_MAX, DRAIN_MS each) until one times out empty. */
#define DRAIN_MS 20
#define DRAIN_MAX 8
static void drain(pk_link *l) {
    uint8_t junk[PKL_RESP_CAP];
    for (int i = 0; i < DRAIN_MAX; i++) {
        size_t got = 0;
        if (pk_t_bulk_in(l->t, EP_CMD_IN, junk, sizeof junk, &got, DRAIN_MS) != PK_OK || got == 0) break;
    }
    l->need_drain = 0;
}

static void fail(pk_link *l, pk_status s, const char *what, const uint8_t *pkt) {
    pk_error_set(&l->err, s, "link", "%s (packet type %u, address 0x%02X, byte 4 = 0x%02X)%s%s", what, pkt[0], pkt[2],
                 pkt[0] == 3 ? 0 : pkt[4], l->t->diag[0] ? ": " : "", l->t->diag);
}

/* A bulk-out timeout on EP 0x01 followed by a failed ping means the FX2 firmware stopped draining EP1. The ping goes to
 * the HOST board (answered inside the FX2) when the model has one, else to the address that timed out. */
static int firmware_wedged(pk_link *l, uint8_t fallback_addr) {
    uint8_t pkt[5], resp[PKL_RESP_CAP];
    size_t got;
    xinfo xi;
    uint8_t a = l->roles.host ? l->roles.host : fallback_addr;
    size_t n = pkl_build_command(a, PING_CMD, pkt);
    if (pkl_check_packet(&l->roles, pkt, n, NULL, 0) != PK_OK) return 1;   /* cannot probe: treat as wedged, the safe side */
    return exchange(l, pkt, n, 4, a, resp, &got, &xi) != PK_OK;
}

static pk_status transact_locked(pk_link *l, const uint8_t *pkt, size_t n, int retries, uint8_t *resp, size_t *got) {
    char why[160];
    uint8_t type = pkt[0], addr = pkt[2];
    if (pkl_guard_wedged(l->t)) {
        pk_error_set(&l->err, PK_E_FIRMWARE_WEDGED, "link", "the firmware stopped answering; power-cycle the scanner");
        return PK_E_FIRMWARE_WEDGED;
    }
    pk_status s = pkl_check_packet(&l->roles, pkt, n, why, sizeof why);
    if (s != PK_OK) {   /* nothing is sent */
        pk_error_push_exchange(&l->err, 1, pkt, n);
        pk_error_set(&l->err, s, "link", "write guard refused: %s", why);
        return s;
    }
    int leave = l->leave_deadline_ms != 0 || tl_cap_ms != 0;      /* S-R29: one attempt, no wedge ping, every transfer capped (also for a thread with a cap) */
    if (leave) {
        retries = 0;
        if (!xfer_ms(l)) { pk_error_set(&l->err, PK_E_TIMEOUT, "link", "leave budget spent"); return PK_E_TIMEOUT; }
    }
    for (int attempt = 0;; attempt++) {
        xinfo xi;
        if (l->need_drain) drain(l);
        s = exchange(l, pkt, n, type, addr, resp, got, &xi);
        if (s == PK_OK) return PK_OK;
        l->need_drain = 1;
        if (xi.out_timeout && !leave && firmware_wedged(l, addr)) {
            pkl_guard_set_wedged(l->t);
            pk_error_set(&l->err, PK_E_FIRMWARE_WEDGED, "link", "bulk-out timed out and the ping failed; power-cycle the scanner");
            return PK_E_FIRMWARE_WEDGED;
        }
        if ((s != PK_E_TIMEOUT && s != PK_E_PROTOCOL) || attempt >= retries) break;
    }
    fail(l, s, s == PK_E_PROTOCOL ? "malformed or mismatched response" : s == PK_E_TIMEOUT ? "timeout" : "transfer failed", pkt);
    return s;
}

static pk_status transact(pk_link *l, const uint8_t *pkt, size_t n, int retries, uint8_t *resp, size_t *got) {
    pthread_mutex_lock(&l->mu);
    pk_status s = transact_locked(l, pkt, n, retries, resp, got);
    pthread_mutex_unlock(&l->mu);
    return s;
}

/* ---------------------------------------------------------------- the five calls */

pk_status pk_link_read(pk_link *l, uint8_t addr, uint8_t reg, uint8_t count, uint8_t *out) {
    return pk_link_read_status(l, addr, reg, count, out, NULL);
}

pk_status pk_link_read_status(pk_link *l, uint8_t addr, uint8_t reg, uint8_t count, uint8_t *out, uint8_t *status) {
    uint8_t pkt[5], resp[PKL_RESP_CAP];
    size_t got;
    if (!l || !out || count == 0 || count > PKL_RESP_CAP - 4) return PK_E_ARG;
    size_t n = pkl_build_read(addr, reg, count, pkt);
    pk_status s = transact(l, pkt, n, RETRIES, resp, &got);
    if (s != PK_OK) return s;
    memcpy(out, resp + 4, count);
    if (status) *status = resp[3];
    return PK_OK;
}

pk_status pk_link_write(pk_link *l, uint8_t addr, uint8_t reg, const uint8_t *data, uint8_t n) {
    uint8_t pkt[PKL_MAX_OUT], resp[PKL_RESP_CAP];
    size_t got;
    if (!l) return PK_E_ARG;
    size_t len = pkl_build_write(addr, reg, data, n, pkt);
    if (!len) return PK_E_ARG;
    return transact(l, pkt, len, 0, resp, &got);   /* never retried */
}

pk_status pk_link_poll(pk_link *l, uint8_t addr, uint8_t out[2]) { return pk_link_poll_status(l, addr, out, NULL); }

pk_status pk_link_poll_status(pk_link *l, uint8_t addr, uint8_t out[2], uint8_t *status) {
    uint8_t pkt[3], resp[PKL_RESP_CAP];
    size_t got;
    if (!l || !out) return PK_E_ARG;
    size_t n = pkl_build_poll(addr, pkt);
    pk_status s = transact(l, pkt, n, RETRIES, resp, &got);
    if (s != PK_OK) return s;
    /* TLB FUN_10008d70 (RE 42 sec 9): the reply's byte 0 must be 3 and the status is byte 3; nothing else is checked. HW 2026-10-22: with no
     * interrupt pending this unit's HOST answers in 5 bytes (03 03 10 00 aa), with one pending in 6 (03 04 10 08 aa aa), so the data bytes are optional. */
    if (got < 4 || resp[0] != 3) { fail(l, PK_E_PROTOCOL, "short poll response", pkt); return PK_E_PROTOCOL; }
    out[0] = got > 4 ? resp[4] : 0; out[1] = got > 5 ? resp[5] : 0;
    if (status) *status = resp[3];
    return PK_OK;
}

pk_status pk_link_command(pk_link *l, uint8_t addr, uint8_t cmd) {
    uint8_t pkt[5], resp[PKL_RESP_CAP];
    size_t got;
    if (!l) return PK_E_ARG;
    size_t n = pkl_build_command(addr, cmd, pkt);
    return transact(l, pkt, n, 0, resp, &got);
}

pk_status pk_link_ping(pk_link *l, uint8_t addr) {
    uint8_t pkt[5], resp[PKL_RESP_CAP];
    size_t got;
    if (!l) return PK_E_ARG;
    size_t n = pkl_build_command(addr, PING_CMD, pkt);
    return transact(l, pkt, n, RETRIES, resp, &got);
}
