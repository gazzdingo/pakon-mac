#ifndef SYNFRAME_H
#define SYNFRAME_H
/* Test helper: regenerate the crafted lo-res frames of the Kodak truth rolls, so their vectors carry parameters instead
 * of 0.5 MB images. The test checks each regenerated frame against the FNV of the image Kodak analysed.
 *   numpy frames (lab/rollbal/gen_t12syn.py / gen_t13syn.py / gen_t15syn.py / gen_t17syn.py): numpy's legacy RandomState (MT19937,
 *     masked-rejection randint, 53-bit uniform) and the generators' float64 arithmetic in numpy's operation order;
 *   recipes (lab/rollbal/gen_t14syn.py): integer only (background, xorshift32 noise, rectangles). */
#include <stdint.h>

/* npar: one row of flesh_truth.pkv's npar (layout in synframe.c). out: 3 planes of H x W u16 (malloc'd), *w / *h set.
 * 0 on success, -1 on a bad row or no memory. */
int synframe_numpy(const double npar[20], uint16_t **out, int *w, int *h);
/* recipe: [W, H, bgR, bgG, bgB, noise, seed, nrect, (x0, y0, x1, y1, R, G, B, noise) x nrect], len words: the background,
 * then each rectangle [x0, x1) x [y0, y1) over it, every sample + (xorshift32() % (2 noise + 1)) - noise when noise > 0
 * (one xorshift32 stream from seed, drawn plane by plane, row by row), clamped to 0..4095 at the end. */
int synframe_recipe(const int32_t *recipe, int len, uint16_t **out, int *w, int *h);
#endif
