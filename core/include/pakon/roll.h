#ifndef PAKON_ROLL_H
#define PAKON_ROLL_H
/* A scanned roll on disk (<roll>.raw + <roll>.json + a calibration store) and its hand-off to the colour library (spec sections G and N, plan Task 20).
 *
 * This is where decode (the TLB scan-line kernel, the lo-res strip), framing (TLB's frame detection) and the colour library meet. A pk_roll reads the
 * sidecar next to the raw file, decodes LAZILY, strip by strip, and caches the lo-res strips, their row profiles, their frames and their DX results. The hi-res
 * frame crops are NOT cached: pk_roll_colour_input re-runs the kernel over each frame's lines (the kernel's only state is the previous line's mean, which pass 1
 * records for every line, so the re-run is exact) and hands the crops over in a pk_roll_input_storage that the caller frees.
 *
 * Calibration. Decode uses the calibration named LAST in the sidecar's calibration_ids (the scan writes one id and a calibration made inside the scan replaces it:
 * the child session calibration holds that scan's own dark and flat), looked up in the store given to pk_roll_open. The per-pixel tables are what matter for decode; the
 * light settings are irrelevant. A calibration of another scanner (foreign) is allowed for decode. The negative colour matrix (poly_neg) comes from the unit's
 * EEPROM image in the same store (units/<unit>/eeprom/), CalWiz +0x26.
 *
 * Profile sums (ruling S-R41). Kodak's lo-res profile sums are process-lifetime globals that its strip init never clears, so a block left partial by one strip leaks
 * into the next strip's first row. A pk_roll carries ONE uint32_t sums[3], zeroed when the roll is opened and shared across the roll's strips in strip order. Kodak's
 * live process keeps the sums across rolls; decoding a SAVED roll can only start them at zero, so per-roll-open is the closest we can get (a roll decoded in the same
 * process after another in Kodak would start from that roll's leftover sums; a live session will be able to pass its own sums later). Strips are decoded in order
 * whatever order the caller asks for them, so the answer never depends on the order of calls.
 *
 * Not thread safe: a pk_roll caches on first use, even through its const accessors. Use one thread per roll. */
#include <stdbool.h>
#include <stdint.h>
#include "pakon/colour.h"
#include "pakon/dx.h"
#include "pakon/framing.h"
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_roll pk_roll;
/* Owns every pointer a pk_roll_input from pk_roll_colour_input hands out (frames, lores, the strip copy, the IR planes). Free it after the colour call is finished. */
typedef struct pk_roll_input_storage pk_roll_input_storage;

/* raw_path = ".../<name>.raw"; the sidecar is ".../<name>.json" next to it (PK_E_ARG when raw_path does not end in ".raw"). calstore_root = the calibration store root
 * (NULL or "" = $PAKON_HOME, else ~/Library/Application Support/PakonMac, as pk_calstore_open). Reads only: nothing is written under either path. Nothing is decoded and
 * neither the calibration nor the EEPROM is looked up yet, so a roll with a missing calibration opens and fails in pk_roll_frames / pk_roll_colour_input with PK_E_NOT_FOUND.
 * PK_E_NOT_FOUND / PK_E_IO / PK_E_CORRUPT / PK_E_FORMAT from the sidecar or the raw file; PK_E_UNSUPPORTED for a model or base the core cannot decode (the sidecar names a
 * model it does not know, or a base the model lacks). */
pk_status pk_roll_open(const char *raw_path, const char *calstore_root, pk_roll **out);
void      pk_roll_close(pk_roll *);
int       pk_roll_strip_count(const pk_roll *);
bool      pk_roll_complete(const pk_roll *);     /* the sidecar's "complete": false = a partial roll, which decodes whatever whole lines exist */
int       pk_roll_dpi_base(const pk_roll *);     /* 4, 8 or 16 */
bool      pk_roll_ir(const pk_roll *);           /* four planes (Digital ICE) */

/* The film lines of a strip (hi-res lines between the sidecar's byte_start and byte_end that exist in the raw file; 0 for a strip without film). PK_E_ARG for a bad strip. */
pk_status pk_roll_strip_lines(const pk_roll *, int strip, size_t *lines);

/* The strip's DX result: product / specifier = TLB strip+0x4c / +0x50, from re-feeding the sidecar's dx_packets through pk_dx (-1 / -1 for no accepted read, 0 / 0 is a
 * real unassigned code pair). dx_source is "dx", "none" or "manual" (a manual pick, or the sidecar's own "manual" strip when the packets gave none). */
pk_status pk_roll_dx(const pk_roll *, int strip, pk_dx_strip *out);

/* TLB's half-frame number of frame `frame` (INT32_MIN in *half_frames when the DX table holds none for it). `frame` is ROLL-GLOBAL, counted in strip order: the first
 * strip's frames, then the second's, ... (C61); the table entry used is the frame's index inside its strip. PK_E_ARG for a frame out of range. The framing's frame
 * list is decoded for the count, so this can fail like pk_roll_frames. The match between the framing's rectangle order and the DX table is by position (TLB matches
 * them later; RE 31 sec 0). */
pk_status pk_roll_frame_number(const pk_roll *, int frame, int *half_frames, bool *read_not_extrapolated);

/* Marks the strip's film as picked by hand: pk_roll_dx then returns this product / specifier with dx_source "manual" and pk_roll_colour_input passes them. PK_E_ARG for what
 * the colour library would refuse: product outside 0..32767 or specifier outside 0..15, unless both are PK_DX_NONE (-1; the colour library takes that as "no DX read"). */
pk_status pk_roll_set_manual_film(pk_roll *, int strip, int product, int specifier);

/* The frame rectangles of a strip, in TLB's list order (valid until pk_roll_close). n = 0 for a strip without lines. */
pk_status pk_roll_frames(const pk_roll *, int strip, const pk_frame_rect **rects, int *n);

/* What the framing says about a strip beyond its rectangles. not_kodak_exact is ruling S-R19: the detection read run statistics that Kodak leaves uninitialised, so the
 * frames may differ from what Kodak gives on a real machine; report such a strip as "framing not Kodak-exact". scanw = the framing bits (0x100 Between, 0x200 LookAtEnd,
 * 0x400 LookAtBeginning, 0x800 blind placement). */
typedef struct { int n_frames; unsigned scanw; bool not_kodak_exact; } pk_roll_framing_info;
pk_status pk_roll_framing_info_get(const pk_roll *, int strip, pk_roll_framing_info *out);

/* Kernel start (fix round 1, ruling S-R43). TLB initialises the kernel (init = 1) at a strip's FIRST SYNCED line and feeds every line from there, with the film flag off
 * until film is detected: the detect line itself is fed with film 0 (it is the strip's first hi-res line) and film is 1 from the next line. The sidecar's strip object
 * therefore records segment_byte_start (the first synced line) next to byte_start / line_start (the detect line); lines in between are the pre-film lines, and the lo-res
 * stored rows may hold up to ratio-1 of them (RE 30 sec 4.4). A sidecar without segment_byte_start is read as having no pre-film lines.
 *
 * Fills a pk_roll_input for the colour library, in TLB's layout (spec section N):
 *   frames[k]  hi-res frame k (its linear14[PK_PLANE_IR] is the IR plane once pk_roll_colour_frame has loaded it, on an IR roll): the scan-line kernel's corrected lines registered with the read-out stagger d = ratio (4 / 6 / 8 at base 4 / 8 / 16), cropped to TLB's frame
 *              rectangle, in the stored orientation (rows = hi-res lines, width = the base's hires_px), linear 14-bit;
 *   lores[k]   the lo-res frame: the lo-res strip registered with d = 1 (PKD_LORES_STAGGER), cropped to TLB's lo-res rectangle, turned by 180 degrees, linear 14-bit.
 *              That is PSI's default AnselOrientation 0x10E. This version hands off ONLY the default; AnselOrientation 0 (a 270 degree turn) is revisited if the HW-2
 *              registry export shows it (C39a);
 *   strip      the whole stored lo-res strip: 250 px wide, the stored rows (lines / ratio + 1), plane c one row late, values <= 16383 (a copy owned by the storage);
 *   poly_neg   the unit's EEPROM block (CalWiz +0x26) from the store;
 *   product_code / gen_code   pk_roll_dx's product / specifier; -1 / -1 is PK_DX_NONE, 0 / 0 is passed through, a manual pick is passed (its source stays recorded in pk_roll_dx).
 * A strip with no lines gives n_frames = 0 and PK_OK (the colour library reports its own status for an empty roll). PK_E_UNSUPPORTED for F-235 / F-335 rolls: Task 21 records
 * their Dmin constants but pk_roll_input has no field for them (a colour.h change for sub-project 2; C39b). PK_E_NOT_FOUND for a calibration or EEPROM image the store lacks.
 * The hi-res frames are NOT loaded: frames[k] has its width and height but NULL planes, which is all pk_colour_analyse_roll needs (it reads only lores and strip). Call
 * pk_roll_colour_frame for the frame about to be rendered or exported (36 MB at base 16) and pk_roll_colour_frame_release when done. There is no TIFF export here (C41): the
 * CLI writes TIFFs from pk_colour_export_linear16.
 * *keep is set only on PK_OK (also for n_frames == 0) and is freed by pk_roll_input_storage_free. */
pk_status pk_roll_colour_input(const pk_roll *, int strip, pk_roll_input *out, pk_roll_input_storage **keep);
void      pk_roll_input_storage_free(pk_roll_input_storage *);

/* Loads hi-res frame k of the strip into `keep` and points in->frames[k] at it (`in` and `keep` are the pair pk_roll_colour_input returned; PK_E_ARG otherwise, and for a
 * frame out of range). Idempotent: a loaded frame is kept. PK_E_CORRUPT when the raw file no longer holds the frame's lines. Memory per loaded frame: planes x h x w x 2 bytes. */
pk_status pk_roll_colour_frame(const pk_roll *, int strip, int k, pk_roll_input *in, pk_roll_input_storage *keep);
/* `keep` remembers the roll and strip it was made from: another roll or strip is PK_E_ARG (never a crop beyond the buffer).
 * Frames whose hi-res planes are not loaded still carry their width and height, so pk_colour_saved_size works on them (it needs the size only; the renders and exports
 * need the planes and refuse NULL planes with PK_E_ARG). Load a frame before rendering or exporting it. */
/* Frees frame k's hi-res planes (the planes of in->frames[k] become NULL again; its width and height stay). */
void      pk_roll_colour_frame_release(pk_roll_input *in, pk_roll_input_storage *keep, int k);

/* Digital ICE hand-over (docs/re/45): on a roll scanned with IR the storage also holds each LOADED hi-res frame's IR plane (width x height samples, the same crop as frames[k], the
 * IR plane of the same stored row as R, not staggered; values may exceed 16383 at ratios 4 and 8 when a cross-talk factor is set). NULL when the roll has no IR plane, the frame is not loaded or the
 * frame is out of range. pk_roll_colour_frame also sets in->frames[k].linear14[PK_PLANE_IR] to the same plane (NULL on a roll without IR), which is how the colour library gets it: set pk_roll_input.ice to run Digital ICE on the save (colour.h, S-R45 b). The IR plane is never part of lores[] or the strip. The pointer is valid until the storage is freed (or the frame is released). */
const uint16_t *pk_roll_input_storage_ir(const pk_roll_input_storage *, int frame);

#ifdef __cplusplus
}
#endif
#endif
