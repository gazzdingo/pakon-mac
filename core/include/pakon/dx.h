#ifndef PAKON_DX_H
#define PAKON_DX_H
/* DX / edge data (Task 8): the register-0x90 packet parser, the code-word votes, the frame-number analysis and the strip
 * hand-off, ported byte for byte from Kodak's TLB.dll (docs/re/33-dx-parser.md has the function map, the evidence tiers and
 * the places where TLB differs from what the plan said). Kodak truth: lab/vectors/uc_tlb_dx.py runs TLB's own code under
 * Unicorn; the kept check core_dx_kodak compares every event, vote, winner, frame number and hand-off against it.
 *
 * pk_dx is the state TLB keeps per strip in its CiDxAndApsHole object (strip + 0x78) plus the two line-counter words of the
 * board object; one pk_dx per strip, one thread. Nothing here writes scanner memory: pk_dx_start sends the 0x91 row, pk_dx_stop
 * the 0x92 row and pk_dx_poll reads registers 0x02 and 0x90 and pk_dx_read_levels register 0x93, all rows of commands.def. Every packet goes through pk_link_*. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "pakon/boards.h"
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PK_DX_NONE_CODE (-1)
#define PK_DX_PACKET_LEN 30
#define PK_DX_MAX_RECORDS 5            /* (30 - 3) / 5: the most 5-byte records one packet can carry */

typedef struct {
    int product, specifier;            /* TLB strip+0x4c / +0x50: the winning vote, -1/-1 when none, 0/0 when the publish did not run */
    int good_count;                    /* hole+0x48: frame-table entries read from the film (not inserted, not extrapolated) */
    int votes[4][3];                   /* the four vote slots: product, specifier, count (-1/-1/0 when empty) */
    unsigned scanw;                    /* TLB strip+0x6ca8, the DX-related scan-warning bits: 0x1 the end-of-strip analysis failed or found no film-found marker (hole+0xbb4), 0x2 product < 1, 0x10 | 0x20 the trimmed mean line spacing of the last five strips is more than 0.5 % | 1 % above the expected spacing, 0x40 | 0x80 the same below (see dx.c; RE 33 section 7) */
    bool status_bit40_seen;            /* a status nibble with bit 0x40 was seen (TLB sets word bit 0x10000000; what it means is UNRESOLVED in RE 33) */
    bool tail_first;                   /* a status nibble with bit 0x80 was seen: hole+0x60, the direction flag of the frame numbering */
    char dx_source[8];                 /* "dx" | "none" ("manual" is set by the roll layer) */
} pk_dx_strip;

/* TLB's per-resolution constants (FUN_10011a60's table) and the scan mode that reach the DX object (FUN_10013800). */
typedef struct {
    unsigned height;                   /* hole+0x0c: 1000 / 1500 / 2000 at base 4 / 8 / 16 */
    unsigned dpi_base;                 /* hole+0x10: 23700 (the same constant as strip+0xc6c in RE 20) */
    unsigned ratio;                    /* hole+0x14: hi-res / lo-res ratio 4 / 6 / 8 */
    unsigned aux18;                    /* hole+0x18: 1500 / 2250 / 3000 (stored by TLB, not read by any function ported here) */
    unsigned frame_pitch;              /* hole+0x1c: 1603 / 2405 / 3206 lines, the frame pitch (half of it is the expected spacing of two half-frame codes) */
    bool aps24;                        /* hole+0x20 == 0: the 24 mm (APS) strip; false = 35 mm */
    bool ir;                           /* hole+0x28: four planes (IR): TLB halves every DX line number */
    bool single_strip;                 /* FN_bEndScan passes (strips == 1) as the "do the speed analysis" flag */
    unsigned film_context;             /* scanner+0xa8, the film-found context word (0) */
} pk_dx_geometry;

/* 35 mm geometry of the F-135 / F-135 Plus at base 4, 8 or 16 (PK_E_UNSUPPORTED otherwise). */
pk_status pk_dx_geometry_for(int dpi_base, bool ir, pk_dx_geometry *out);

/* The five newest average line spacings of earlier strips, newest first (TLB scanner+0x398). TLB compares the trimmed mean of
 * five with the expected spacing and raises the speed bits once all five are filled; a pk_dx made without one starts with an
 * empty history, so those bits stay 0 for a single strip. */
typedef struct { uint32_t slot[5]; } pk_dx_speed_history;

typedef struct pk_dx pk_dx;                                     /* one per strip */
pk_status pk_dx_new(pk_dx **out);                               /* slots start product/specifier = -1, counts 0; F-135 base 16, 35 mm, three planes */
pk_status pk_dx_new_geometry(const pk_dx_geometry *, pk_dx **out);
void      pk_dx_free(pk_dx*);
/* Task 13: keeps a copy of every packet pk_dx_feed_packet accepts (at most 8 MiB, then logging stops and *truncated is set), so the roll sidecar can store them for
 * Task 20 to re-feed. Off by default. The pointer is valid until the next feed or free; n = packets, 30 bytes each. */
void pk_dx_log_packets(pk_dx*, bool on);
const uint8_t *pk_dx_logged_packets(const pk_dx*, size_t *n, bool *truncated);
/* Borrows h for the analysis of this strip (updated by it); NULL = a private empty history. */
pk_status pk_dx_attach_speed_history(pk_dx*, pk_dx_speed_history *h);

/* TLB board states 3 and 4 are the calibration states (a normal scan runs in state 5, which is what pk_dx_new gives). In them a
 * packet's records are not parsed, FUN_10014320 and the line-counter stores are skipped, and only the entry/exit bits of the status word
 * are updated. With require_sensors (registry RequireDxSensorsDuringLightCalibration, default 1) and request_flag10 clear, a packet whose
 * first record shows film (status & 0x30) ends the calibration state, ORs 0x100 into the status word and sets the abort flag; that packet is
 * itself discarded. calibrating=false (or c == NULL) returns to the scanning state. */
typedef struct { bool calibrating, require_sensors, request_flag10; } pk_dx_calibration;
pk_status pk_dx_set_calibration(pk_dx*, const pk_dx_calibration *c);
bool      pk_dx_calibration_abort(const pk_dx*);        /* film was sensed during calibration */
uint32_t  pk_dx_status_word(const pk_dx*);              /* TLB's status word: 0x40000000 entry, 0x80000000 exit, 0x10000000 bit 0x40, 0x20000000 bit 0x80, 0x100 calibration abort */
bool      pk_dx_tail_first(const pk_dx*);

/* Feeds the 30-byte register 0x90 response. n != 30, or a record count above 5, is PK_E_PROTOCOL and changes nothing (TLB would
 * read past its 32-byte buffer). PK_E_BUSY once the strip has been analysed (pk_dx_frame_half_frames, pk_dx_finish_strip). */
pk_status pk_dx_feed_packet(pk_dx*, const uint8_t *buf, size_t n);
/* FUN_10005820 hand-off after the end-of-strip analysis; publish_ran=false -> the constructor's 0/0 (only the destroy and
 * event-create-failure exits). publish_ran=true: product/specifier of the winning slot, -1/-1 when no vote was accepted. */
pk_status pk_dx_finish_strip(pk_dx*, bool publish_ran, pk_dx_strip *out);
/* Reads register 0x02 and, when (status & 0xA4) != 0, register 0x90 (30 bytes) and feeds it. *status_nibble = the status bits of
 * the packet's first record in place (buf[3] & 0xF0: 0x10 exit sensor, 0x20 entry sensor, 0x40, 0x80), 0 when nothing was read
 * or the packet had no record. */
pk_status pk_dx_poll(pk_boards*, pk_dx*, uint8_t *status_nibble);
/* Reads register 0x90 now (30 bytes) and feeds it: the second half of pk_dx_poll_event, for a caller that has read register 0x02 itself (the scan loop shares one 0x02
 * read between the lamp judgement and the DX reader, as TLB's status thread does). *status_nibble as pk_dx_poll. */
pk_status pk_dx_read_packet(pk_boards*, pk_dx*, uint8_t *status_nibble);
/* TLB's rule for the whole strip of a real scan (FUN_1000BDD0 0x1000bf7b..bfa1, scan flag 0): reads register 0x02 and, whenever its status byte
 * flags an event (bit 7), reads and feeds register 0x90, whatever the value's bits are. *event (may be NULL) = an event was seen. */
pk_status pk_dx_poll_event(pk_boards*, pk_dx*, uint8_t *status_nibble, bool *event);
/* TLB's single end-of-strip drain read (same function, flag 1): reads register 0x02 and reads/feeds 0x90 only when (value & 0xA4) != 0, event bit or not.
 * Call once after the strip has left, before pk_dx_stop. */
pk_status pk_dx_drain(pk_boards*, pk_dx*, uint8_t *status_nibble);
/* Diagnostic: how many records of each type (the low nibble of a record's first byte, 0..15) pk_dx_feed_packet has parsed so far. */
void      pk_dx_record_counts(const pk_dx*, uint32_t out[16]);
/* Light register 0x93, 4 bytes: the raw DX sensor levels AN0..AN3 (FN_bDrvDxGetHardware 0x1000a830; firmware nl050A 0x3d6c). Read-only.
 * A reply whose status is not 0x08 (0x88 with the event flag) is not sensor data: PK_E_PROTOCOL, out unchanged. */
pk_status pk_dx_read_levels(pk_boards*, uint8_t out[4]);
pk_status pk_dx_start(pk_boards*, unsigned speed16, unsigned format);   /* 0x91 START_DX_SCAN: speed16 little-endian, then the format byte */
pk_status pk_dx_stop (pk_boards*);                                       /* 0x92, owner-allowed DX self-tune row */
/* The frame table after the end-of-strip analysis (run on first use): TLB's half-frame number of entry frame_index, INT32_MIN
 * when the entry holds none (or the index is outside 0..99). *read_not_extrapolated = the entry was read from the film (neither
 * inserted nor extrapolated). */
int       pk_dx_frame_half_frames(pk_dx*, int frame_index, bool *read_not_extrapolated);

#ifdef __cplusplus
}
#endif
#endif
