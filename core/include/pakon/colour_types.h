#ifndef PAKON_COLOUR_TYPES_H
#define PAKON_COLOUR_TYPES_H

/* PSI per-picture user adjustments, as passed to PIColorAdjustPlanar (RE 06 §1).
 * r, g, b, brightness, contrast: -1000..1000 (one UI click = 25).
 * sharpness: 0..2000 (0 = off).
 * saturation: -5..5 (0 = none).
 * bnw: 0 none, 1 warm, 2 cold, 3 sepia. */
typedef struct { int r, g, b, brightness, contrast, sharpness; int saturation; int bnw; } pk_adjust;

#endif
