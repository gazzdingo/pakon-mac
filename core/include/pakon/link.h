#ifndef PAKON_LINK_H
#define PAKON_LINK_H
/* The packet link to the scanner's boards, and the write guard (Task 4).
 *
 * NEVER-WRITE RULE (owner): scanner memory (the calibration EEPROM, the boot EEPROM, PIC flash and EEPROM) is never
 * written. The guard has two halves, and no caller can reach a transport without passing both:
 *   - the transport guard (pk_transport_guard_open): an ALLOWLIST on control transfers, and a role-aware check on
 *     every bulk-out packet. pk_usb_open, pk_transport_record_open and pk_transport_replay_open return guarded
 *     transports; the raw handle is held only inside the guard.
 *   - the link (pk_link_*): builds only packet types 1-4, refuses every address that is not exactly a mapped role
 *     address, refuses beta roles wholesale, and applies the FORBID rows of commands.def for every role at the address.
 * Refusals return PK_E_WRITE_FORBIDDEN, send nothing and are recorded in pk_error. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "pakon/error.h"
#include "pakon/transport.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_link pk_link;
/* Board addresses of the connected model (models.def); 0 = no such role. On TLB models dx == light (the DX board
 * answers at the light-board address). The five beta roles are refused wholesale until Task 21 maps their boards. */
typedef struct {
    uint8_t light, motor, host;
    uint8_t dx, lamp235, motor235, dx235, aps235, guide;
} pk_link_roles;

/* Wraps t in a guard (borrowing: closing the guard does not close t; the caller keeps t alive while the guard is in
 * use). Idempotent: an already-guarded transport is returned as is. The openers pk_usb_open,
 * pk_transport_record_open and pk_transport_replay_open do not use this: they hand their raw transport to the
 * guard for good (the guard owns it and closing the guard closes it), so no caller ever holds a raw one. */
pk_status pk_transport_guard_open(pk_transport *inner, pk_transport **out);

/* addr is EXACTLY a mapped role address (non-zero role fields only). */
bool pk_roles_has_address(const pk_link_roles *, uint8_t addr);
/* ANY role at addr is a beta role (lamp235, motor235, dx235, aps235, guide): refused wholesale, types 1-4. */
bool pk_roles_is_beta_address(const pk_link_roles *, uint8_t addr);

/* Models the link knows. The roles (board addresses) come from a library-owned table, never from the caller: a wrong
 * struct could otherwise switch the FORBID rows off for a board (S-R11). The table is core/tables/models.def. */
typedef enum { PK_LINK_F135, PK_LINK_F135_PLUS, PK_LINK_F235, PK_LINK_F335 } pk_link_model;

/* Binds the model's roles to the transport (a guard is created around it if it is not one). The link does not close the
 * transport. F-235 / F-335 map only beta roles, so every board packet to them is refused until Task 21. */
pk_status pk_link_open(pk_transport *, pk_link_model, pk_link **out);
void pk_link_close(pk_link *);

/* After any timeout the link drains EP 0x81 (bounded short reads) before the next request, so a late reply cannot be
 * taken for the answer to a later request. Every call: PK_E_FIRMWARE_WEDGED (sticky, kept on the transport) before anything else once the firmware has wedged; PK_E_WRITE_FORBIDDEN
 * for a refused packet (nothing sent); PK_E_PROTOCOL for a malformed or mismatched response; PK_E_TIMEOUT. */
pk_status pk_link_read(pk_link *, uint8_t addr, uint8_t reg, uint8_t count, uint8_t *out /*count, 1..60*/);   /* type 1, retried x2 */
/* Same, and *status (may be NULL) = the response status byte resp[3] of the exchange that succeeded (bit 7 matters to TLB's light-board 0x02 read). */
pk_status pk_link_read_status(pk_link *, uint8_t addr, uint8_t reg, uint8_t count, uint8_t *out, uint8_t *status);
pk_status pk_link_write(pk_link *, uint8_t addr, uint8_t reg, const uint8_t *data, uint8_t n);               /* type 2, never retried, n <= 252 */
pk_status pk_link_poll(pk_link *, uint8_t addr, uint8_t out[2]);                                             /* type 3, retried x2 */
/* Same, and *status (may be NULL) = resp[3]. For the HOST (FX2) address this is TLB's status read (FUN_10008D70, RE 42 sec 9): bit 7 = a board has an interrupt, bit 1 = FIFO overflow. */
pk_status pk_link_poll_status(pk_link *, uint8_t addr, uint8_t out[2], uint8_t *status);
pk_status pk_link_command(pk_link *, uint8_t addr, uint8_t cmd);                                             /* type 4 */
pk_status pk_link_ping(pk_link *, uint8_t addr);                                                             /* type 4, command 0x00, retried x2 */
const pk_error *pk_link_last_error(const pk_link *);
/* The same, copied under the link's lock (safe while another thread, e.g. a Stop, is using the link). */
void pk_link_last_error_copy(pk_link *, pk_error *out);
/* Leave mode (S-R29), set and cleared by the session around session_leave and open-failure cleanup, and nowhere else: while on, every transfer
 * is capped at 500 ms and at the time left of budget_ms, a request gets one attempt (no retry, no wedge ping), and once the budget is spent
 * calls fail at once with PK_E_TIMEOUT. budget_ms 0 switches it off. The budget is link-wide: reads from another thread (e.g. film_sense) while it is on
 * draw on it and run under the same single-attempt limits. */
void pk_link_set_leave_mode(pk_link *, unsigned budget_ms);
/* The calling thread's own cap (the session's idle status thread): every transfer it makes is at most ms long and gets one attempt with no wedge ping. 0 = off (the default). Other threads are unaffected. */
void pk_link_set_thread_cap(unsigned ms);

#ifdef __cplusplus
}
#endif
#endif
