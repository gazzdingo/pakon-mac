#ifndef PAKON_FRAMING_FRAME_H
#define PAKON_FRAMING_FRAME_H
/* Internal framing (C25, C26, C31). Evidence: docs/re/31-framing.md; bit-exact against TLB under Unicorn by core_frame_kodak. */
#include <stddef.h>
#include "pakon/framing.h"
#include "boards/dx_internal.h"
#include "decode/strip.h"

/* The detection pass only (Task 18's check calls it): FUN_100072c0 up to and including Between (FUN_100063d0), then FUN_100079c0's rectangle conversion. Uninitialised stack
 * locals of Kodak's code read as 0 (ruling S-R19): strips that reach them are 'framing not Kodak-exact'. */
pk_status pkf_detect(const uint8_t *profile, int rows, const pk_frame_params *p, pk_framing **out);
/* Film geometry beyond pk_frame_params; all-zero = the 35 mm negative defaults of pkf_detect. */
typedef struct {
    int scan_window_lines;      /* strip+0xc70: the frame spacing, 1603 / 2405 / 3206; 0 = derived from frame_pitch_lines */
    bool positive;              /* positive film (strip+0x20 == 2): the gray value is not inverted */
    bool aps;                   /* 24 mm APS path (strip+0xc98 == 0), where the DX veto and its 267-row end skip apply */
} pkf_film;
pk_status pkf_detect_ex(const uint8_t *profile, int rows, const pk_frame_params *p, const pkf_film *film, pk_framing **out);
/* The full sequence of pk_frame_strip_profile with the explicit scan window. */
pk_status pkf_frame_ex(const uint8_t *profile, int rows, const pk_frame_params *p, const pkf_film *film, pk_framing **out);
/* = pk_frame_strip_profile(s->profile, pkd_strip_readable_rows(s->rows, planes), ...); planes = 3, or 4 for an IR strip (R = rows - (planes - 1)). Checked in core_frame_kodak. */
pk_status pkf_frame_strip(const pkd_strip *s, int planes, const pk_frame_params *p, const pk_frame_film *film, pk_framing **out);
/* TLB's DX line -> lo-res row conversion for the positional veto (RE 31 sec 6): in TLB's shipped configuration (hole+0x08 == 1) no perforation pair
 * ever completes, so the answer is 0 rows for any event list. The sec 6 arithmetic (hole+0x08 == 0) is deliberately NOT ported; rows_out and cap are unused. Returns the row count written (at most cap). */
int pkf_dx_rows(const pkb_dx_event *ev, size_t n_ev, int ratio, int *rows_out, int cap);
#endif
