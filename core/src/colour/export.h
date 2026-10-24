#ifndef PAKON_COLOUR_EXPORT_H
#define PAKON_COLOUR_EXPORT_H
#include <stddef.h>
#include <stdint.h>
#include "pakon/colour.h"
#include "internal.h"

/* three contiguous u8 planes (p, p + n, p + 2n) -> interleaved RGB */
void pkc_interleave_u8(const uint8_t *planes, size_t n, uint8_t *out);
/* the same for three contiguous u16 planes */
void pkc_interleave_u16(const uint16_t *planes, size_t n, uint16_t *out);
/* planar 12-bit RPD (clamped to 0..4095) -> interleaved u16, v * 16 + v / 256 (0 -> 0, 4095 -> 65535) */
void pkc_rpd12_to_u16(const int16_t *const p[3], size_t n, uint16_t *out);
/* planar linear14 (clamped to 16383, as TLB's LUT does) -> interleaved u16, v * 4 (16383 -> 65532) */
void pkc_linear14_to_u16(const uint16_t *const p[3], size_t n, uint16_t *out);

/* colour.c: the render chain up to the KCMS input (see there), rotated by `rotation` (0 / 90 / 180 / 270, as
 * PIScaleAndRotatePlanar) between the balance and the adjustments; *bal's three planes are one malloc'd block, p[0]. */
pk_status pkc_colour_balanced(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                              const pk_adjust *adj, int rotation, pkc_planes *bal);
/* colour.c: Digital ICE on a scratch copy of a frame's crop (see there); *scratch NULL when it does not apply */
pk_status pkc_ice_crop(const pk_roll_input *in, const pk_frame_linear *f, pk_frame_linear *iced, uint16_t **scratch);
/* test seam: force the falloff decision of a frame of a result (PK_E_ARG out of range) */
pk_status pkc_roll_result_force_falloff(pk_roll_result *r, int frame, int on);
#endif
