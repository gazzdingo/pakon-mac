/*
 * pakon_ansel_c.c — High-performance C implementation for Ansel engine operations.
 *
 * Cite: PakonIMAu.dll @ 0x100dc310 (applyBalanceShifts), 0x10100a37 (setShifts 1,2),
 *       0x101f82c0 (FUGC setLutInfo), 0x100147ed (Contrast LUT), 0x10370de0 (Unsharp).
 * Docs: docs/49-preference-fpu-binary.md, docs/52-setshifts-binary.md, docs/58-colour-pipeline.md.
 */

#include <stdint.h>
#include <stdlib.h>
#include <math.h>

#define MASTER_MAX 4095
#define PIVOT_0x60E 0x60E
#define INV_SQRT3 0.5773502717125849
#define INV_SQRT6 0.40824829759439285
#define INV_SQRT2 0.7071067623730956
#define SQRT_2_OVER_3 0.8164965951887857

static inline int16_t to_i16(int32_t x) {
    int16_t v = (int16_t)(x & 0xFFFF);
    return v;
}

static inline int32_t clamp_0_4095(int32_t val) {
    if (val < 0) return 0;
    if (val > MASTER_MAX) return MASTER_MAX;
    return val;
}

/*
 * Opponent forward transform: FOS opening axes Y, C1, C2
 */
static inline void fos_axes(double r, double g, double b, double* y, double* c1, double* c2) {
    *y = (r + g + b) * INV_SQRT3;
    *c1 = (2.0 * g - r - b) * INV_SQRT6;
    *c2 = (b - r) * INV_SQRT2;
}

/*
 * Opponent inverse transform
 */
static inline void fos_axes_inverse(double y, double c1, double c2, double* r, double* g, double* b) {
    double ys = y * INV_SQRT3;
    double us = c1 * INV_SQRT6;
    double vs = c2 * INV_SQRT2;
    *r = ys - us - vs;
    *g = ys + c1 * SQRT_2_OVER_3;
    *b = ys - us + vs;
}

/*
 * setshifts_12 @ 0x10100a37: transforms raw shifts_a, shifts_b through 3-band planar LUT.
 */
void pakon_setshifts_12_c(const int16_t shifts_a[3], const int16_t shifts_b[3],
                         const int16_t* planar_lut, int num_lut, int16_t out_shifts[3]) {
    /* Pivot 0x60E - A */
    int16_t ap[3];
    for (int i = 0; i < 3; i++) {
        ap[i] = to_i16(PIVOT_0x60E - shifts_a[i]);
    }

    /* Planar LUT lookup */
    double lut_rgb[3];
    lut_rgb[0] = (double)to_i16(planar_lut[(uint16_t)ap[0]]);
    lut_rgb[1] = (double)to_i16(planar_lut[(uint16_t)ap[1] + num_lut]);
    lut_rgb[2] = (double)to_i16(planar_lut[(uint16_t)ap[2] + 2 * num_lut]);

    double y, c1_dummy, c2_dummy;
    fos_axes(lut_rgb[0], lut_rgb[1], lut_rgb[2], &y, &c1_dummy, &c2_dummy);

    /* Pivot 0x60E - B */
    int16_t bp[3];
    for (int i = 0; i < 3; i++) {
        bp[i] = to_i16(PIVOT_0x60E - shifts_b[i]);
    }
    double y_dummy, c1, c2;
    fos_axes((double)bp[0], (double)bp[1], (double)bp[2], &y_dummy, &c1, &c2);

    /* Reconstruct */
    double rec[3];
    fos_axes_inverse(y, c1, c2, &rec[0], &rec[1], &rec[2]);

    /* Final pivot subtraction */
    for (int i = 0; i < 3; i++) {
        out_shifts[i] = to_i16(PIVOT_0x60E - (int32_t)trunc(rec[i]));
    }
}

/*
 * applyBalanceShifts @ 0x1019a0c0: out = clamp(code + shift, 0, 4095) per channel.
 */
void pakon_apply_balance_shifts_c(const int32_t* in_rgb, int32_t* out_rgb,
                                 int num_pixels, const int16_t shifts[3]) {
    int32_t s0 = (int32_t)shifts[0];
    int32_t s1 = (int32_t)shifts[1];
    int32_t s2 = (int32_t)shifts[2];

    for (int i = 0; i < num_pixels; i++) {
        int idx = i * 3;
        out_rgb[idx]     = clamp_0_4095(in_rgb[idx]     + s0);
        out_rgb[idx + 1] = clamp_0_4095(in_rgb[idx + 1] + s1);
        out_rgb[idx + 2] = clamp_0_4095(in_rgb[idx + 2] + s2);
    }
}

/*
 * FUGC setLutInfo @ 0x101f82c0: builds 3-channel apply LUT (4096 x 3).
 */
void pakon_fugc_set_lut_info_c(const int32_t* seed_rgb, const int32_t offsets[3],
                              int32_t* out_lut, int n) {
    for (int c = 0; c < 3; c++) {
        int off = offsets[c];
        int col_offset = c;
        if (off > n - 1) {
            for (int i = 0; i < n; i++) {
                out_lut[i * 3 + col_offset] = i;
            }
            continue;
        }
        if (off > 0) {
            for (int i = 0; i < off; i++) {
                out_lut[i * 3 + col_offset] = off;
            }
        }
        for (int i = off; i < n; i++) {
            int seed_idx = (i - off) * 3 + col_offset;
            int val = seed_rgb[seed_idx] + off;
            if (val < 0) val = 0;
            if (val > n - 1) val = n - 1;
            out_lut[i * 3 + col_offset] = val;
        }
    }
}

/*
 * Apply 3-channel 1D LUT across an HWC int32 image buffer.
 */
void pakon_apply_3chan_lut_c(const int32_t* in_rgb, int32_t* out_rgb,
                            int num_pixels, const int32_t* lut_3chan, int num_lut) {
    for (int i = 0; i < num_pixels; i++) {
        int idx = i * 3;
        for (int c = 0; c < 3; c++) {
            int code = in_rgb[idx + c];
            if (code < 0) code = 0;
            if (code >= num_lut) code = num_lut - 1;
            out_rgb[idx + c] = lut_3chan[code * 3 + c];
        }
    }
}

/*
 * ColorAdjust Contrast LUT Build @ 0x100147ed: builds 3 x 4096 LUTs.
 */
void pakon_color_adjust_contrast_lut_c(int contrast, int brightness, const int rgb_offset[3],
                                       int32_t* out_lut) {
    int half = contrast / 2;
    int scale = half + 1000;

    for (int c = 0; c < 3; c++) {
        int total_offset = rgb_offset[c] + brightness;
        /* delta ≈ trunc(total_offset * 1.024) */
        int delta = (int)trunc((double)(total_offset * 1.024));

        for (int i = 0; i < 4096; i++) {
            int val = (int)trunc((double)(i - PIVOT_0x60E) * (double)scale / 1000.0) + PIVOT_0x60E;
            val += delta;
            out_lut[i * 3 + c] = clamp_0_4095(val);
        }
    }
}

/*
 * Separable 3-tap Unsharp Mask filter [0.25, 0.5, 0.25] @ 0x10370de0.
 */
void pakon_color_adjust_unsharp_c(const int32_t* in_rgb, int32_t* out_rgb,
                                 int width, int height, float amount) {
    int num_pixels = width * height;
    float* temp = (float*)malloc(num_pixels * 3 * sizeof(float));
    float* blur = (float*)malloc(num_pixels * 3 * sizeof(float));

    if (!temp || !blur) {
        if (temp) free(temp);
        if (blur) free(blur);
        return;
    }

    /* Horizontal 1D pass: [0.25, 0.5, 0.25] */
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int x_prev = (x > 0) ? x - 1 : x;
            int x_next = (x < width - 1) ? x + 1 : x;
            for (int c = 0; c < 3; c++) {
                float p0 = (float)in_rgb[(y * width + x_prev) * 3 + c];
                float p1 = (float)in_rgb[(y * width + x) * 3 + c];
                float p2 = (float)in_rgb[(y * width + x_next) * 3 + c];
                temp[(y * width + x) * 3 + c] = 0.25f * p0 + 0.5f * p1 + 0.25f * p2;
            }
        }
    }

    /* Vertical 1D pass: [0.25, 0.5, 0.25] */
    for (int y = 0; y < height; y++) {
        int y_prev = (y > 0) ? y - 1 : y;
        int y_next = (y < height - 1) ? y + 1 : y;
        for (int x = 0; x < width; x++) {
            for (int c = 0; c < 3; c++) {
                float p0 = temp[(y_prev * width + x) * 3 + c];
                float p1 = temp[(y * width + x) * 3 + c];
                float p2 = temp[(y_next * width + x) * 3 + c];
                blur[(y * width + x) * 3 + c] = 0.25f * p0 + 0.5f * p1 + 0.25f * p2;
            }
        }
    }

    /* Combine: out = clamp(orig + amount * (orig - blur)) */
    for (int i = 0; i < num_pixels * 3; i++) {
        float orig = (float)in_rgb[i];
        float b_val = blur[i];
        float res = orig + amount * (orig - b_val);
        int val = (int)trunc(res);
        out_rgb[i] = clamp_0_4095(val);
    }

    free(temp);
    free(blur);
}
