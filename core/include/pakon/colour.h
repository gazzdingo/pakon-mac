#ifndef PAKON_COLOUR_H
#define PAKON_COLOUR_H
/* libpakon colour: Kodak PSI's default colour-negative rendering (PSI 3.0.4.27, PakonIMAu CN-Enhanced class 1),
 * reproduced bit for bit against Kodak's own DLLs as run under Wine / Rosetta on the reference Mac (the real-x86 / XP check of
 * docs/re/25, ruling R27, is the owner's and has not been run: until it is, "bit for bit" means that). docs/re/24-roll-orchestration.md
 * maps every step to Kodak's code.
 *
 * Handles are opaque. A pk_colour holds only data read at pk_colour_open and is never modified afterwards, so one
 * handle may serve several threads at once; a pk_roll_result is likewise read-only after pk_colour_analyse_roll. No
 * function keeps mutable global state after first use (one lazily built, immutable lookup table and one C-locale object, both
 * behind pthread_once; a pk_colour_open_ex / pk_colour_analyse_roll_ex call binds a caller-stack diagnostic record to its
 * own thread for its duration). pk_colour_render* may use up to 8 worker threads internally (NRA row bands; the output does
 * not depend on the split; pk_colour_open_opts sets the count, 1 = none). Every function that can fail returns pk_status (pakon/status.h). */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"
#include "pakon/colour_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_colour pk_colour;
typedef struct pk_roll_result pk_roll_result;

/* One image as the scanner delivers it: linear 14-bit, three planes of width x height samples, row-major. In frames
 * and lores a value above 16383 is clamped to 16383 as TLB's LUT does; in the strip a sample above 16383 inside the
 * film-base finder's window is PK_E_ARG (Kodak's histogram has 16384 bins; TLB's scan-time clamp never stores one). */
/* linear14[PK_PLANE_IR] is the frame's Digital ICE infrared plane (S-R45 b, docs/re/45): width x height samples, the same crop and stride (= width) as the three colour
 * planes, or NULL for a frame scanned without IR (a zero-initialised or three-plane literal leaves it NULL). Only a HI-RES frame (pk_roll_input.frames) uses it, and only when
 * pk_roll_input.ice is set; lores[] and strip never do (TLB never applies ICE to them). Samples above 16383 are possible on a roll decoded with an IR cross-talk factor (RE 45
 * sec 4.1); pk_ice_apply reads them as Kodak does (docs/re/45 U2). */
#define PK_PLANE_IR 3
typedef struct { int width, height; const uint16_t *linear14[4]; } pk_frame_linear;

/* A scanned roll (one TLB strip).
 *   frames[k] : frame k at scan resolution (what PSI saves, through pk_colour_render);
 *   lores[k]  : frame k in TLB's lo-res buffer (RE 04: the 4/6/8-line weighted decimation, registered planes, the
 *               frame's crop) as PIAnselAddScene receives it, before TLB's LUT + 3x10 polynomial -- what PSI analyses.
 *               TLB rotates it at scan time (FUN_10034a60 -> FUN_10028520): by 180 degrees when the registry's
 *               AnselOrientation is non-zero (PSI's default, 0x10E), by 270 when it is 0; the caller supplies it so.
 *               frames[k] stay in the stored orientation (the save path balances them unrotated at the default);
 *   strip     : the whole lo-res strip as TLB stores it -- planes un-registered (stored row r of plane c = registered
 *               row r - c), height = TLB's stored-row count. Kodak's film-base finder (TLB FN_bFindDmin, RE 20) runs
 *               on it and the result, through the same LUT + polynomial, is every scene's AddScene dmin. The strip
 *               (not a film-base number) is the input because that is what Kodak measures: the film base comes from
 *               rows between and around the frames, so the finder belongs here, not in the caller;
 *   poly_neg  : the scanner's negative 3x10 colour matrix (EEPROM, RE 04 Q5);
 *   product_code, gen_code : the film's DX codes (AddScene descriptor words 0x18 / 0x19), or PK_DX_NONE for both when
 *               the scanner read no DX code: TLB's DX vote slots start at -1 and it passes the winning slot, so a strip
 *               without an accepted DX read reaches PakonIMAu as -1 / -1, which leaves the scene context without a
 *               product / gen code -- no film ISO, sba.map's product rows skipped, and no FOS analysis (Kodak's FOS
 *               needs both keys), a visibly different render. 0 / 0 is a real (unassigned) code pair, not "none".
 *               Kodak picks its
 *               files from them (docs/re/24 section 8): the SBA dpi by sba.map (78/13, 79/15, 96/any, 43/any have
 *               their own), the film ISO by common-ProdCodeTable.dpi and through it NRA's noise table, the FUGC
 *               tables (the shipped map sends every film to one row); all Kodak-pinned. product_code must be
 *               0..32767 (PK_E_ARG otherwise; codes outside the table have ISO 0); gen_code 0..15 (a DX gen code is
 *               4 bits; Kodak's AddScene fails for others: PK_E_UNSUPPORTED); PK_DX_NONE is only valid for both. */
#define PK_DX_NONE (-1)
typedef struct {
    int n_frames;
    const pk_frame_linear *frames;
    const pk_frame_linear *lores;
    pk_frame_linear strip;
    float poly_neg[3][10];
    int product_code, gen_code;
    /* Digital ICE on the save (S-R45 b; TLB save bit 0x80, iSaveControl & 0x80). 0 (the default of a zeroed struct) = off. When non-zero, every hi-res render and export below
     * (pk_colour_render*, pk_colour_export_rpd16) runs Kodak's ICE (pk_ice_apply, bit-exact) on a scratch copy of the frame's R, G, B and IR planes BEFORE TLB's LUT + polynomial,
     * which is TLB's order (FUN_10026c90, RE 45 sec 4.2): ICE on the crop in its stored orientation, then LUT, polynomial, rotation, scene balance, the scaled-save resample, the
     * adjustments. The gate is TLB's: `ice` set AND the frame has an IR plane (frames[k].ir != NULL); a frame without IR renders exactly as with `ice` 0, silently (RE 45 sec 4.3).
     * Never ICE'd: the lo-res frames and the film-base strip (so a roll's analysis is the same with and without ICE) (pk_colour_export_linear16 DOES apply ICE, S-R46, below).
     * Frames below the DLL's size limits (RE 45 sec 4.2: Kodak's code crashes there, so there is no Kodak result): the render fails with PK_E_ARG and writes nothing, it never
     * saves the frame without ICE; pk_colour_ice_check says why. A user crop is at least 128 x 128, so this is practically unreachable. */
    int ice;
} pk_roll_input;

typedef struct { int width, height; uint8_t *rgb; } pk_image_u8;      /* interleaved RGB, row-major */
typedef struct { int width, height; uint16_t *rgb; } pk_image_u16;   /* interleaved RGB, row-major (the 16-bit exports) */

/* vendor_root = ".../F-X35 COM SERVER" (holds anselinstalldir/), derived_root = ".../vendor/derived". Reads every Kodak
 * data file the analysis and the default render use for the handle's own file selection -- the one a film with DX codes 0 / 0
 * gets; a film with other codes, and PK_DX_NONE (no ISO, no FOS), have their files selected and read per call by
 * pk_colour_analyse_roll. PK_E_ARG on NULLs; PK_E_VENDOR_DATA for a missing or malformed
 * file; PK_E_FORMAT for an over-long path; PK_E_IO for a read error on an existing file; PK_E_UNSUPPORTED when the vendor tree
 * selects a path the port does not have; PK_E_NOMEM. *out is NULL on error. */
pk_status pk_colour_open(const char *vendor_root, const char *derived_root, pk_colour **out);

/* Which Kodak file a failed load came from (support: the user's PSI install is imported, and "vendor data error" alone does
 * not say what to fix). path is the last file the loader touched when it failed with PK_E_VENDOR_DATA / PK_E_FORMAT / PK_E_IO, or empty
 * when the failure names no file (PK_E_ARG, PK_E_NOMEM, PK_E_UNSUPPORTED: a vendor tree selecting a path the port lacks, decided
 * after all files were read -- reason says so); reason is a short fixed phrase:
 * "cannot be opened" (missing or unreadable), "content rejected" (opened, but malformed or inconsistent) or
 * "unsupported selection". Both are filled only when the call fails and are always NUL-terminated. */
typedef struct { char path[1100]; char reason[48]; } pk_load_error;

/* pk_colour_open that also reports the failing file in *err (may be NULL). Same result and *out as pk_colour_open. */
pk_status pk_colour_open_ex(const char *vendor_root, const char *derived_root, pk_load_error *err, pk_colour **out);

/* Options fixed at open (the handle stays immutable afterwards; there is no global setter).
 * Zero-initialise the struct, then set size = sizeof(pk_colour_options) and the fields you want: a field left 0 is its default.
 * Later versions add fields at the end; the library accepts a size from the first version's up to its own (a smaller struct
 * means the newer fields are defaults), and PK_E_ARG for anything else (size 0, too small, or larger than the library knows).
 *   size    : sizeof(pk_colour_options) as the caller was compiled with. Required.
 *   threads : worker threads the render may use (the NRA row bands of pk_colour_render* and the 16-bit RPD export).
 *             0 = automatic (the online cores, at most 8; the default of pk_colour_open / pk_colour_open_ex),
 *             1 = the calling thread only (a host with its own pool, or one rendering several frames in parallel),
 *             2..8 = up to that many, > 8 is treated as 8. Negative is PK_E_ARG. The output is bit-identical for every value.
 *             Threading only starts for frames of about 400 000 px per plane or more (smaller frames always run on the calling
 *             thread), and pk_colour_analyse_roll is single-threaded whatever the setting. */
typedef struct { size_t size; int threads; } pk_colour_options;

/* pk_colour_open_ex with options (opt may be NULL = all defaults). Same errors as pk_colour_open_ex, plus PK_E_ARG for a
 * negative thread count or a bad opt->size. */
pk_status pk_colour_open_opts(const char *vendor_root, const char *derived_root, const pk_colour_options *opt,
                              pk_load_error *err, pk_colour **out);
void      pk_colour_close(pk_colour *c);

/* PSI's scan-time roll analysis: the film base (TLB), then PakonIMAu's analysis in TLB's batches of 40 frames (frames
 * 0-39 form one Kodak roll, 40-79 the next, ...; each batch is analysed on its own, as PSI does).
 * A batch whose analysis Kodak fails (FOS calc error 0x189d: PIAnselAnalyzeRoll returns 0, TLB logs error 2 and goes on)
 * is not an API error: the call returns PK_OK and those frames report PK_E_ANALYSIS from pk_roll_result_status.
 * A frame whose analysis grid would read past its image (Kodak averages heap memory beyond it, docs/re/24 section 5) is
 * refused alone: it reports PK_E_UNSUPPORTED from pk_roll_result_status and from every render, and its batch is analysed with that
 * frame's out-of-bounds cells clamped to the image edge (a NON-Kodak choice of the owner, R41); the batch's other frames render
 * and report pk_roll_result_exact = 0 (docs/re/27 section 9).
 * A batch the port cannot reproduce (a Kodak division fault the port models, or an unported branch) is not an API error either:
 * the call returns PK_OK, the other batches are analysed and render normally, and each frame of the refused batch reports
 * that status (PK_E_UNSUPPORTED, PK_E_VENDOR_DATA, ...) from pk_roll_result_status and from every render / export
 * (docs/re/27). A lo-res frame whose analysis image is under 107 x 107 in either side is not refused: Kodak skips its
 * analysis and builds no transform for it, so it is rendered unbalanced (no NRA, no scene LUT, no falloff; exposure 0, falloff
 * off) while the rest of its batch is analysed with that frame counted as an all-zero scene (observed).
 * Errors (*out NULL): PK_E_ARG on NULLs, n_frames < 1, a lo-res frame / strip with NULL planes or a size < 1, a strip
 * sample > 16383 in the finder's window, product_code outside 0..32767 unless both codes are PK_DX_NONE (frames are
 * checked by pk_colour_render);
 * PK_E_UNSUPPORTED for gen_code outside 0..15 or a vendor tree selecting a path the port lacks; PK_E_VENDOR_DATA for a
 * missing or malformed data file; PK_E_NOMEM. */
pk_status pk_colour_analyse_roll(const pk_colour *c, const pk_roll_input *in, pk_roll_result **out);
/* pk_colour_analyse_roll that reports the failing Kodak file in *err (may be NULL) -- the files a film's DX codes select are
 * read here, so a missing one is named like an open failure. */
pk_status pk_colour_analyse_roll_ex(const pk_colour *c, const pk_roll_input *in, pk_load_error *err, pk_roll_result **out);
void      pk_roll_result_free(pk_roll_result *r);

/* Number of frames of the result. PK_E_ARG on NULLs. */
pk_status pk_roll_result_frames(const pk_roll_result *r, int *n);
/* PK_OK; PK_E_ANALYSIS when the frame's batch failed in Kodak (the frame still renders, as PSI does: see pk_colour_render); or
 * the status with which the port refused the frame's batch (see pk_colour_analyse_roll; the frame does not render).
 * PK_E_ARG for a NULL result or a frame out of range. */
pk_status pk_roll_result_status(const pk_roll_result *r, int frame);
/* Whether Kodak skipped the frame's analysis (*skipped = 1): its analysis image is under 107 x 107 in either side, so Kodak builds no
 * transform for it and the frame is rendered unbalanced (no NRA, no scene LUT, no falloff; pk_roll_result_status is PK_OK,
 * exposure 0, falloff off). An app can use it to say why such a frame looks unbalanced. PK_E_ARG for NULLs or a frame out of range. */
pk_status pk_roll_result_skipped(const pk_roll_result *r, int frame, int *skipped);
/* Whether the frame's result is bit-exact with Kodak's (*exact = 1) -- every frame of a normal roll. 0 for a frame the port
 * refused (pk_roll_result_status is not PK_OK or PK_E_ANALYSIS) and for every other frame of a batch holding an "odd" frame
 * (owner decision R41, docs/re/27 section 9): such a frame renders, but its batch's roll statistics (FOS, scene dmin,
 * exposure) used a grid that the port filled with clamped reads, so they are not Kodak's. A skipped frame in such a batch keeps
 * Kodak's skip rule (unbalanced) and stays 1 (R42: its output never uses batch statistics). When FOS did not run in the batch
 * (no DX codes, fosOn 0, or too few scenes) and the roll did not fail, no statistic crosses frames and the other frames stay 1
 * too. Frames of the other batches of the same call stay 1. An app should
 * show the flag. PK_E_ARG for NULLs or a frame out of range. */
pk_status pk_roll_result_exact(const pk_roll_result *r, int frame, int *exact);
/* Whether ICE can run on hi-res frame `frame` of a roll input (S-R45 c). PK_OK when `in->ice` is off, the frame has no IR plane (such a frame renders without ICE, silently) or its size
 * is one Digital ICE accepts. PK_E_ARG for NULLs / a frame out of range, and for a frame below the DLL's limits (width <= 3, height < 8, or height < 32 at 1,000,000 pixels
 * or more) while ICE would run on it; then msg (may be NULL; cap bytes) names the frame size and the limit. Reads sizes only. */
pk_status pk_colour_ice_check(const pk_roll_input *in, int frame, char *msg, size_t cap);

/* Whether PSI applies its lens-falloff correction to the frame (the SBA exposure lies in -0.5 .. 7.0 stops). */
pk_status pk_roll_result_falloff(const pk_roll_result *r, int frame, int *on);
/* The frame's SBA exposure in stops, in half-stop steps (0 for a failed batch). */
pk_status pk_roll_result_exposure(const pk_roll_result *r, int frame, double *stops);

/* The frame as PSI saves it, 8-bit sRGB: TLB's LUT + 3x10 polynomial, NRA noise reduction, the scene LUT, lens falloff
 * (when the result says so), PSI's adjustments (adj; NULL = PSI's defaults, all zero) and the KCMS output transform.
 * Geometry: this is the frame in its stored orientation (rotation 0). PSI's save path (TLB FUN_10027ac0 / FUN_10026c90,
 * docs/re/02 "Geometry") balances the stored frame and then rotates it with PIScaleAndRotatePlanar before
 * PIColorAdjustPlanar; because sharpening and the KCMS stage work per Ima tile, the rotation changes pixels, so use
 * pk_colour_render_rotated for PSI's saved files (PSI's default: 270).
 * A frame of a failed batch is rendered as PSI renders it: every sample through an all-zero scene LUT, then falloff.
 * out->rgb must hold width * height * 3 bytes of the frame's size; width / height are set.
 * PK_E_ARG on NULLs, a frame out of range, a result made from a different roll size, or adjustments out of range;
 * PK_E_IMAGE_TOO_SMALL for a frame under 11 x 11 (NRA's window; or under 3 x 3 with sharpening); PK_E_VENDOR_DATA if the
 * KCMS table cannot be read; PK_E_NOMEM. */
pk_status pk_colour_render(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                           const pk_adjust *adj, pk_image_u8 *out);

/* pk_colour_render with PSI's save rotation applied between the balance and the adjustments, as TLB does (a pure pixel
 * rotation at scale 1, Kodak-pinned): rotation 0, 90 (clockwise), 180 or 270 (counter-clockwise); 90 / 270 swap
 * width and height. TLB derives it from the picture's rotation code r (0..3, PutPictureRotation; 0 on a new scan) and
 * the registry's AnselOrientation (0x10E unless set to 0): rotation = (630, 540, 450, 360)[r] - (0x10E - AnselOrientation)
 * mod 360, i.e. PSI's default save is rotation 270 (a landscape image). This is the save path at PSI's default
 * AnselOrientation; pk_colour_render_saved takes the registry value itself. Only full-size saves are covered here: a scaled save
 * (iSaveControl bits 0x01 / 0x02) is pk_colour_render_saved_scaled (docs/re/39). PK_E_ARG
 * for any other rotation; otherwise as pk_colour_render. */
pk_status pk_colour_render_rotated(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                   const pk_adjust *adj, int rotation, pk_image_u8 *out);

/* TLB's AnselOrientation registry value as PSI's default has it (0x10E = 270; a positive registry value is forced to it). */
#define PK_ANSEL_ORIENTATION_PSI 270

/* PSI's whole save geometry (TLB SaveToDisk, FUN_10026c90 / docs/re/02 "Geometry"): the hi-res frame is first rotated by
 * 0x10E - AnselOrientation with PIRotatePlanar, then balanced, then rotated by (630, 540, 450, 360)[picture_rotation] -
 * (0x10E - AnselOrientation) mod 360, then adjusted and converted. The two orders end in the same orientation, but NRA, the
 * scene LUT and the lens falloff run on the image in the rotated order, and the falloff's floating-point position terms are
 * not symmetric under the swap of width and height: with AnselOrientation = 0 a frame can differ from PSI's default save in
 * +-1 code of the 12-bit buffer (Kodak-pinned on real frames, docs/re/26 section 6: 2000 x 3047 differs, 2000 x 3000 does not).
 *   ansel_orientation : PK_ANSEL_ORIENTATION_PSI (270, the default) or 0; PK_E_ARG otherwise (a registry value below 0 would
 *                       give PIRotatePlanar an angle outside {90, 180, 270}; not ported);
 *   picture_rotation  : 0..3, TLB's picture rotation code (0 on a new scan).
 * (270, 0) is pk_colour_render_rotated(.., 270, ..). With AnselOrientation = 0 TLB also turns the AddScene lo-res frame by
 * 270 instead of 180 at scan time: pk_roll_input.lores must be supplied that way for the analysis to be PSI's.
 * Errors as pk_colour_render_rotated. */
pk_status pk_colour_render_saved(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                 const pk_adjust *adj, int ansel_orientation, int picture_rotation, pk_image_u8 *out);

/* ---- PSI's scaled save (iSaveControl bits 0x01 / 0x02 / 0x800; docs/re/39) ----
 * TLB's SaveToDisk sizes the picture with FUN_100267a0 and lets PakonIMAu's PIScaleAndRotatePlanar resample the scene-balanced
 * 12-bit frame to that size (bicubic, iScalingMethod 2, which PSI always passes) while it turns it, before PIColorAdjustPlanar;
 * the sharpening and KCMS stages then run on the scaled image. The two functions below reproduce that, Kodak-pinned
 * (core/tests/colour/e2e.py, section "scaled"). Not offered: the lo-res export (iSaveControl 0x08) and the other two
 * interpolation modes (0, 1), which PSI never uses. */
typedef struct pk_save_size {
    int fit;          /* iSaveControl & 3: 0 = full size (bound_w / bound_h ignored), 1 = scale to fit inside the box
                       * bound_w x bound_h as given, 2 = the same with the box turned (width and height swapped) when the saved
                       * picture's orientation (portrait / landscape) differs from the box's; 3 is invalid in PSI too */
    int bound_w, bound_h;   /* iBoundingWidth / iBoundingHeight in pixels of the SAVED picture, at least 17 each when fit != 0 (PSI's rule); the port also caps them at 65535 */
    int no_upscale;   /* iSaveControl & 0x800: a picture whose fitting side is smaller than the box is saved at full size */
} pk_save_size;

/* The size of the saved picture, as SaveToDisk computes it: the fitting side takes the box's size and the other side
 * (side * box / fitting side, integer truncation) follows; a fitting side that already equals the box (or, with no_upscale, is
 * under it) leaves the picture at full size. Full size is the frame's size turned by the save rotation (height x width for PSI's
 * default rotation 270, as pk_colour_render_saved returns it). size NULL = full size. picture_rotation as for
 * pk_colour_render_saved (TLB feeds the same code to its size planner). PK_E_ARG on NULLs, a frame out of range, a rotation
 * outside 0..3, a fit outside 0..2, a box under 17 pixels (PSI refuses that too) or over 65535 (the port's own limit), a size whose
 * arithmetic would overflow Kodak's 32-bit integers (the planner's product is checked here, the resample tables when rendering),
 * or a side that rounds to 0 (Kodak's PI returns rc 0 for such a size; the port deliberately refuses, an aspect ratio above 17:1
 * with a 17-pixel box). */
pk_status pk_colour_saved_size(const pk_roll_input *in, int frame, int picture_rotation, const pk_save_size *size,
                               int *width, int *height);

/* pk_colour_render_saved with PSI's size option: the balanced frame is resampled to pk_colour_saved_size()'s size by Kodak's
 * bicubic (Catmull-Rom weights in double arithmetic, edge samples replicated, clamp to 12 bits, trunc(x + 0.5); the resample
 * happens before the rotation, so its size is the saved size, width and height swapped for a 90 / 270 turn), then rotated,
 * adjusted and converted. size NULL or fit 0 is exactly pk_colour_render_saved. out->rgb must hold width * height * 3 bytes of
 * the saved size (call pk_colour_saved_size first); width / height are set. Errors as pk_colour_render_saved and
 * pk_colour_saved_size; PK_E_IMAGE_TOO_SMALL also when the SCALED picture is under 3 x 3 with sharpening. Handles stay
 * immutable; thread-safe like the render; no state. */
pk_status pk_colour_render_saved_scaled(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                        const pk_adjust *adj, int ansel_orientation, int picture_rotation,
                                        const pk_save_size *size, pk_image_u8 *out);

/* ---- "16-bit Kodak" (C10, docs/re/50): libpakon's own addition, Kodak never made this output ----
 * pk_colour_render_saved_scaled with the same arguments, but the sRGB output is carried at 16 bits per channel: Kodak's whole
 * chain runs unchanged (TLB's LUT and polynomial, ICE, NRA, scene LUT, falloff, the resample, the rotation, the adjustments) up to
 * the KCMS input, which is 12-bit as in Kodak; the KCMS stage then returns the value Kodak's evaluator quantises to 8 bits, at
 * 16 bits. Reducing any sample with Kodak's own 8-bit store, (v * 32640 + 4194303) >> 23, gives EXACTLY the byte
 * pk_colour_render_saved_scaled writes for the same arguments (smoother, not Kodak-identical). out->rgb must hold
 * width * height * 3 uint16_t of the saved size (pk_colour_saved_size); width / height are set. Errors as pk_colour_render_saved_scaled. */
pk_status pk_colour_render_saved_scaled16(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                          const pk_adjust *adj, int ansel_orientation, int picture_rotation,
                                          const pk_save_size *size, pk_image_u16 *out);

/* NOTE (Task 22): the 16-bit exports below always use the stored orientation (pre-rotation 0); there is no AnselOrientation 0
 * variant of them. */

/* ---- 16-bit exports for DNG. These are libpakon's own addition: PSI has no such export. (PSI's own 48-bit save is a
 * separate thing, on the parity backlog; these functions are not it.) Conventions as pk_colour_render: the caller
 * allocates out->rgb for width * height * 3 uint16_t of the frame's size; width / height are set on success; thread-safe
 * like the render. ---- */

/* The scene-balanced RPD, interleaved RGB, 12 -> 16 bit as v * 16 + v / 256 (0 -> 0, 4095 -> 65535). It is the render
 * chain's buffer just before the KCMS/ICC stage: TLB's LUT + polynomial, NRA, the scene LUT, lens falloff (when the
 * result says so). PSI's user adjustments are NOT applied (there is no adjust argument): the export is the scene's own
 * balance and a DNG consumer makes its own adjustments; Kodak applies PIColorAdjustPlanar before ICC, so
 * pk_colour_render with adj = NULL (all zero, the identity) reaches the same buffer. A frame of a failed batch
 * (PK_E_ANALYSIS) is exported as pk_colour_render renders it (all-zero scene LUT, then falloff), returning PK_OK.
 * Errors: PK_E_ARG on NULLs, a frame out of range or a result made from a different roll size; PK_E_IMAGE_TOO_SMALL for a
 * frame under 11 x 11 (NRA's window); PK_E_NOMEM. */
pk_status pk_colour_export_rpd16(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                 pk_image_u16 *out);

/* The scanner's linear 14-bit samples of in->frames[frame], interleaved RGB, times 4 (a sample above 16383 is clamped to
 * 16383 first, as everywhere in this API, so the maximum is 65532). No colour processing; needs no analysis.
 * S-R46 (owner decision 2026-10-22, replacing the earlier raw-only ruling): when in->ice is set and the frame has an IR plane, pk_ice_apply runs first on a scratch copy of the frame
 * crop, the same step at the same point as the hi-res path (RE 45 sec 4); with ice 0 or no IR plane the output is byte-identical to the raw samples. A frame ICE cannot run on
 * (pk_colour_ice_check) fails with PK_E_ARG and writes nothing; PK_E_NOMEM.
 * PK_E_ARG on NULLs, a frame out of range, or a frame with NULL planes or a size < 1. */
pk_status pk_colour_export_linear16(const pk_roll_input *in, int frame, pk_image_u16 *out);

#ifdef __cplusplus
}
#endif
#endif
