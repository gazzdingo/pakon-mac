#ifndef PAKON_COLOUR_INTERNAL_H
#define PAKON_COLOUR_INTERNAL_H

#include <stdint.h>
#include "pakon/status.h"

/* Three planar int16 channels, w*h samples each. */
typedef struct { int w, h; int16_t *p[3]; } pkc_planes;

/* Three 4096-entry per-channel lookup tables. */
typedef struct { int16_t t[3][4096]; } pkc_lut3;

#endif
