#ifndef PAKON_COLOUR_FRONT_H
#define PAKON_COLOUR_FRONT_H
#include <stddef.h>
#include <stdint.h>

/* RE 04: lut[0]=16383, lut[i]=trunc(-3500*log10(i/16383)). */
void pkc_density_lut(uint16_t lut[16384]);
/* RE 03: TLB 3x10 polynomial (x87 PC53 order). in = LUT output, out = 12-bit RPD. */
void pkc_poly3x10(const float k[3][10], const uint16_t *in[3], int16_t *out[3], size_t n);
/* LUT + poly from linear 14-bit input (values > 16383 are clamped). */
void pkc_front(const float k[3][10], const uint16_t *lin[3], int16_t *rpd[3], size_t n);
#endif
