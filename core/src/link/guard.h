#ifndef PAKON_LINK_GUARD_H
#define PAKON_LINK_GUARD_H
/* The transport guard (internal). The raw transport pointer is held only in the guard's private state (guard.c). */
#include "link/link.h"

/* A link address is acceptable in a role: non-zero, even, not in 0xA0..0xAF. Models.def rows are checked against it at
 * build time by Task 6 (static assertion over the table), and pk_link_open checks it at run time. */
#define PKL_ADDR_OK(a) ((a) != 0 && (((a) & 1) == 0) && ((a) < 0xA0 || (a) > 0xAF))

/* Used by the openers (pkt_seal): the guard takes ownership of raw for good; on failure raw stays the caller's. */
pk_status pkl_guard_adopt(pk_transport *raw, pk_transport **out);
int pkl_guard_is_guarded(const pk_transport *t);

/* Splicing the recorder under an owning guard (record.c only): the guard stays outermost so one guard (one window, one
 * A4 state) sits above everything. peek returns the guard's inner transport, or NULL if t is not a guard or the guard
 * does not own its inner; set replaces it (the caller has built the replacement around the old inner, which it now owns). */
pk_transport *pkl_guard_peek_inner(pk_transport *g);
void pkl_guard_set_inner(pk_transport *g, pk_transport *inner);

/* The sticky wedge flag lives on the guard, so a fresh link on the same transport still sees it. */
int pkl_guard_wedged(const pk_transport *g);
void pkl_guard_set_wedged(pk_transport *g);

/* Role binding for the bulk-out check; NULL unbinds. Called by pk_link_open / pk_link_close. */
void pkl_guard_bind_roles(pk_transport *g, const pk_link_roles *roles);

#endif
