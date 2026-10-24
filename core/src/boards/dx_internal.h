#ifndef PAKON_DX_INTERNAL_H
#define PAKON_DX_INTERNAL_H
/* Internal to the boards module: what core_dx_kodak reads (events and votes) and what the lock-step development harness reads
 * (the raw object). Event layout is the one gen_dx.py records. */
#include <stddef.h>
#include <stdint.h>
#include "pakon/dx.h"

typedef struct {
    int pkt;                 /* index of the packet within the file (filled by the caller of the check; this module sets it to the running packet number) */
    int type;                /* the record's low nibble, 1..8: the types TLB's dispatcher FUN_100148a0 handles (0 and 9..15 are skipped) */
    int rollover;            /* rec[1], the flag byte (bit 0 / bit 1: which side the edge or code belongs to) */
    int line;                /* the 32-bit line TLB passes to the handler: header counter with rollover, or the record's own line (types 1, 2, 5..15) */
    int w0, w1;              /* types 3 and 4: the raw code word (3: rec[2..4] 21 bits; 4: rec[2..3] 16 bits) and 1 if TLB accepted it (parity and the must-be-zero bit); else 0, 0 */
} pkb_dx_event;

/* Events of the most recent pk_dx_feed_packet (at most PK_DX_MAX_RECORDS). */
void pkb_dx_events(const pk_dx *, const pkb_dx_event **ev, size_t *n);
/* The four vote slots (product, specifier, count; -1/-1/0 for an empty slot) and TLB's winner index (hole+0xba0). */
void pkb_dx_votes(const pk_dx *, int votes[4][3], int *winner);

/* The raw CiDxAndApsHole words (byte offset / 4, 0xC00 bytes), the two board words and the status word, for the development
 * harness that compares this port with TLB word for word. */
#define PKB_DX_HOLE_WORDS 0x300
typedef struct { const uint32_t *hole; uint32_t board_roll, board_last, status, scanw; int fault; } pkb_dx_state;
void pkb_dx_state_get(const pk_dx *, pkb_dx_state *out);
/* Runs the end-of-strip analysis now (FUN_10015520 up to and including FUN_100150e0); idempotent. */
void pkb_dx_analyse(pk_dx *);

#endif
