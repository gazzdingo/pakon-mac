#ifndef PAKON_LINK_INTERNAL_H
#define PAKON_LINK_INTERNAL_H
/* Internal link helpers (pkl_ prefix; not part of the public API, C31). */
#include <stddef.h>
#include <stdint.h>
#include "pakon/image.h"
#include "pakon/link.h"

#define PKL_MAX_OUT 0x200   /* largest packet written to the board */
#define PKL_RESP_CAP 64     /* response buffer */

/* Packet builders: return the wire length (PktLen + 2), or 0 if the arguments cannot be encoded. Types 1-4 only. */
size_t pkl_build_write  (uint8_t addr, uint8_t reg, const uint8_t *data, uint8_t n, uint8_t out[PKL_MAX_OUT]);   /* 02 (n+3) AA n RR <n bytes>; n <= 252 */
size_t pkl_build_command(uint8_t addr, uint8_t cmd, uint8_t out[5]);                                           /* 04 03 AA 00 CC */
size_t pkl_build_read   (uint8_t addr, uint8_t reg, uint8_t count, uint8_t out[5]);                            /* 01 03 AA NN RR */
size_t pkl_build_poll   (uint8_t addr, uint8_t out[3]);                                                        /* 03 01 AA */

/* resp[0] = 1 for READ, 3 for POLL, 7 for WRITE/COMMAND; resp[1] = the length byte, resp[1] + 2 <= n; resp[2] == expect_addr;
 * resp[3]: READ and POLL accept (s & 0x36) == 0 (bit 0 and bit 3 are informational; v1 captures show 0x88 on 8618 of 8619
 * light-board read replies, tools/pakon_commands.py:269-272); WRITE/COMMAND acks accept 0 or 8. PK_E_PROTOCOL otherwise. */
pk_status pkl_check_response(const uint8_t *resp, size_t n, uint8_t type, uint8_t expect_addr);

/* True if ANY role mapped to addr has a FORBID row for (type, reg_or_cmd) in commands.def. Pure; no state. */
int pkl_is_forbidden(const pk_link_roles *, uint8_t type, uint8_t addr, uint8_t reg_or_cmd);

/* The role-and-packet check shared by the link and by the guarded transport's bulk-out. pkt is a complete wire packet.
 * PK_OK, or PK_E_WRITE_FORBIDDEN (address not a role, beta role, forbidden register, or a packet that is not a
 * well-formed type 1-4 packet). `why` (may be NULL) receives a one-line reason. */
pk_status pkl_check_packet(const pk_link_roles *, const uint8_t *pkt, size_t n, char *why, size_t why_cap);

/* The load window (S-R7..S-R9, rewritten by S-R25 for Kodak's own sequence): A0 while held, then A3 while the pinned stage-1 runs.
 * pk_device_load_firmware brackets its whole sequence with these. `guarded` must be a transport returned by
 * pk_transport_guard_open or an opener; otherwise nothing is opened (A0 and A3 stay refused). stage1 MUST hash to
 * PKL_STAGE1_CANON_SHA256 (Kodak's stage-1 as extracted from F235Ldr.sys, 360 records, 4476 bytes): the guard checks it itself and a
 * mismatch is PK_E_CORRUPT with no window. fw has been hash-verified by the caller. Both images must outlive the window. Opening
 * a window while one is open restarts it. */
#define PKL_STAGE1_CANON_SHA256 "8056b9f060ab645e8338de4c7df6a70b8be76c5b622471ae7e8e4166b9b5672e"
void pkl_image_canon_hex(const pk_image *img, char hex[65]);   /* canonical SHA-256 over (addr_hi, addr_lo, value) of the used bytes, lowercase hex */
pk_status pkl_guard_load_begin(pk_transport *guarded, const pk_image *stage1, const pk_image *fw);   /* PK_E_NOMEM / PK_E_CORRUPT: no window opened */

/* The roles of a link model, from the library-owned model table (core/tables/models.def, device/models.c). */
pk_status pkl_roles_for_model(pk_link_model, pk_link_roles *out);
void pkl_guard_load_end(pk_transport *guarded);

/* The guarded transport a link sends through (Task 15: the calibration-chip read and the calibration stream use it). Borrowed. */
pk_transport *pkl_link_transport(pk_link *);

#endif
