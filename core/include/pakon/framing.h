#ifndef PAKON_FRAMING_H
#define PAKON_FRAMING_H
/* Frame detection on a strip's lo-res row profile: Kodak's TLB FUN_100079c0 / FUN_100072c0 (docs/re/31-framing.md). */
#include <stdbool.h>
#include <stdint.h>
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct { int top, bottom;       /* hi-res line range in strip coordinates */
                 int lo_top, lo_bottom; /* lo-res stored-row range (TLB's lo-res rect) */
                 int number;            /* frame index within the strip (the position in TLB's list; TLB's own DX frame number is matched later) */
                 char type;             /* TLB's source code of the rectangle: 1 LookForNicePictures, 2 InBetween, 3 Beginning, 4 End, 9 blind
                                           (the 'H','C','P' print types of the plan are APS-only and not produced by framing, RE 31 sec 0 item 6) */ } pk_frame_rect;
typedef struct {
    unsigned scanw;     /* framing bits 0x100..0x800 */
    int n;
    pk_frame_rect *rects;
    bool not_kodak_exact; /* ruling S-R19: the detection read run statistics that Kodak leaves uninitialised (the first run search found no run: blank,
                             leader-only, all-bright/dark or only-falling profiles). Kodak's own answer there is stack garbage; ours takes 0 as Unicorn does,
                             so the framing may differ from what Kodak gives on a real machine. Report such strips as 'framing not Kodak-exact'. */
} pk_framing;
typedef struct {
    int frame_pitch_lines;      /* the frame height in hi-res lines, strip+0xc74: 1500 / 2250 / 3000 by base (pk_base_geom.frame_lines) */
    int strip_lines;            /* hi-res line count of the strip (rectangles are clamped to it) */
    int ratio;                  /* hi-res lines per lo-res row: 4 / 6 / 8 */
    bool aggressive;
    const int *dx_edge_rows;    /* the DX positional-veto rows (pkf_dx_rows); empty in TLB's shipped configuration (RE 31 sec 0). Used only on the 24 mm path: TLB never vetoes 35 mm */
    int n_dx_edges;
} pk_frame_params;

/* Film kind beyond the geometry in pk_frame_params; NULL = 35 mm negative. The scan window (1603 / 2405 / 3206) is derived from frame_pitch_lines. */
typedef struct {
    bool positive;      /* positive film (TLB strip+0x20 == 2): the gray value is not inverted */
    bool aps;           /* the 24 mm path (TLB strip+0xc98 == 0): the DX veto and the 267-row end skip apply */
} pk_frame_film;

/* The public entry: FN_bEndScan's sequence for one strip, FUN_100079c0(strip, aggressive, 0, 0) (detection, in-between, LookAtEnd, LookAtBeginning) and,
 * when that finds no frame, the blind placement FUN_100079c0(strip, 1, 1, 0) with scanw bit 0x800. scanw bits: 0x100 Between added frames, 0x200
 * LookAtEnd added, 0x400 LookAtBeginning added, 0x800 blind. out->not_kodak_exact (ruling S-R19) is carried through the blind pass and must be reported
 * with the strip ('framing not Kodak-exact'). profile: 3 bytes per lo-res row, stored order plane2, plane1, plane0; rows = R (pkd_strip_readable_rows). */
pk_status pk_frame_strip_profile(const uint8_t *profile, int rows, const pk_frame_params *p, const pk_frame_film *film, pk_framing **out);
void pk_framing_free(pk_framing *f);

#ifdef __cplusplus
}
#endif
#endif
