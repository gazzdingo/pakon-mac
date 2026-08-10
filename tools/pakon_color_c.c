/*
 * pakon_color_c.c — High-performance C implementation for Pakon F-135 stage-0 & stage-2.
 *
 * Cite: TLB.dll @ 0x1000d880 (poly_pixel 3x10 polynomial) and TLB.dll @ 0x100246d0 (sensor_correct).
 * Docs: docs/58-colour-pipeline.md §2 & §4.
 */

#include <stdint.h>
#include <stdlib.h>
#include <math.h>

#define POLY_MIN 0.0f
#define POLY_MAX 4095.0f
#define POLY_HALF 0.5f

/*
 * One pixel of TLB.dll:fcn.1000d880 polynomial evaluation.
 * Intermediate float32 spills match x87 stack behavior:
 * - rr = double(r*r), gg = double(g*g)
 * - bb, rg, rb, gb spilled through float32 (fstp dword)
 * - final accumulator + 0.5 spilled through float32 before clamp and _ftol chop.
 */
static inline void poly_pixel_c(uint16_t r_in, uint16_t g_in, uint16_t b_in,
                                const float* coeffs, int32_t out[3]) {
    /* Stage 0 outputs 14-bit (0..0x3FFF). If input contains unshifted 16-bit raw counts (>0x3FFF), shift to 14-bit.
     * Cite: docs/58-colour-pipeline.md §2 */
    double r = (double)(r_in > 0x3FFF ? (r_in >> 2) : r_in);
    double g = (double)(g_in > 0x3FFF ? (g_in >> 2) : g_in);
    double b = (double)(b_in > 0x3FFF ? (b_in >> 2) : b_in);

    double rr = r * r;
    double gg = g * g;

    float bb_f = (float)(b * b);
    float rg_f = (float)(r * g);
    float rb_f = (float)(r * b);
    float gb_f = (float)(g * b);

    double bb = (double)bb_f;
    double rg = (double)rg_f;
    double rb = (double)rb_f;
    double gb = (double)gb_f;

    for (int k = 0; k < 3; k++) {
        const float* c = &coeffs[10 * k];
        double acc = c[0] * r + c[1] * g + c[2] * b
                   + c[3] * rr + c[4] * gg + c[5] * bb
                   + c[6] * rg + c[7] * rb + c[8] * gb
                   + c[9];
        float acc_f = (float)(acc + POLY_HALF);
        if (acc_f < POLY_MIN) {
            acc_f = POLY_MIN;
        } else if (acc_f > POLY_MAX) {
            acc_f = POLY_MAX;
        }
        out[k] = (int32_t)acc_f; /* _ftol truncation */
    }
}

/*
 * Process an HWC u16 image buffer of shape (height, width, 3) in place or to out_buf.
 * out_buf is int32_t array of shape (height * width * 3).
 */
void pakon_poly_hwc_c(const uint16_t* in_rgb, int32_t* out_rgb,
                     int num_pixels, const float* coeffs, int film_class) {
    /* film_class check: 1, 4, 8 or 2 allowed; otherwise output unchanged */
    if (film_class != 1 && film_class != 4 && film_class != 8 && film_class != 2) {
        for (int i = 0; i < num_pixels * 3; i++) {
            out_rgb[i] = (int32_t)in_rgb[i];
        }
        return;
    }

    for (int i = 0; i < num_pixels; i++) {
        int idx = i * 3;
        poly_pixel_c(in_rgb[idx], in_rgb[idx + 1], in_rgb[idx + 2], coeffs, &out_rgb[idx]);
    }
}

#define DEF_POLY_MAP(name, a, b, c) \
void pakon_poly_##name##_hwc_c(const uint16_t* in_raw, int32_t* out_rgb, \
                          int num_pixels, const float* coeffs, int film_class) { \
    for (int i = 0; i < num_pixels; i++) { \
        int idx = i * 3; \
        poly_pixel_c(in_raw[idx + a], in_raw[idx + b], in_raw[idx + c], coeffs, &out_rgb[idx]); \
    } \
}

DEF_POLY_MAP(rgb, 0, 1, 2)
DEF_POLY_MAP(rbg, 0, 2, 1)
DEF_POLY_MAP(grb, 1, 0, 2)
DEF_POLY_MAP(gbr, 1, 2, 0)
DEF_POLY_MAP(brg, 2, 0, 1)
DEF_POLY_MAP(bgr, 2, 1, 0)

/*
 * Process Planar uint16 image buffer of shape (3, height * width):planes are contiguous:
 * [R0..RN-1], [G0..GN-1], [B0..BN-1].
 * Writes HWC int32_t array of shape (num_pixels * 3).
 * Cite: docs/58-colour-pipeline.md §2 (Stage 0 outputs contiguous planes).
 */
void pakon_poly_planar_c(const uint16_t* in_planar, int32_t* out_rgb,
                        int num_pixels, const float* coeffs, int film_class) {
    const uint16_t* r_plane = in_planar;
    const uint16_t* g_plane = in_planar + num_pixels;
    const uint16_t* b_plane = in_planar + num_pixels * 2;

    for (int i = 0; i < num_pixels; i++) {
        int idx = i * 3;
        poly_pixel_c(r_plane[i], g_plane[i], b_plane[i], coeffs, &out_rgb[idx]);
    }
}

/*
 * Process Line-Planar uint16 image buffer of shape (height, 3, width):
 * For each line y: [R0..RW-1], [G0..GW-1], [B0..BW-1].
 * Writes HWC int32_t array of shape (height * width * 3).
 * Cite: docs/58-colour-pipeline.md §2 (Stage 0 outputs line-planar contiguous planes).
 */
void pakon_poly_line_planar_c(const uint16_t* in_raw, int32_t* out_rgb,
                             int width, int height, const float* coeffs, int film_class) {
    for (int y = 0; y < height; y++) {
        const uint16_t* r_line = in_raw + ((size_t)y * 3 + 0) * (size_t)width;
        const uint16_t* g_line = in_raw + ((size_t)y * 3 + 1) * (size_t)width;
        const uint16_t* b_line = in_raw + ((size_t)y * 3 + 2) * (size_t)width;
        int32_t* out_line = out_rgb + (size_t)y * (size_t)width * 3;

        for (int x = 0; x < width; x++) {
            poly_pixel_c(r_line[x], g_line[x], b_line[x], coeffs, &out_line[x * 3]);
        }
    }
}

/*
 * Unsigned saturating subtract: psubusw
 */
static inline uint16_t sat_sub_u16(uint16_t a, uint16_t b) {
    int v = (int)a - (int)b;
    return (v > 0) ? (uint16_t)v : 0;
}

/*
 * Unsigned saturating add: paddusw
 */
static inline uint16_t sat_add_u16(uint16_t a, uint16_t b) {
    int v = (int)a + (int)b;
    return (v < 0xFFFF) ? (uint16_t)v : 0xFFFF;
}

/*
 * Stage 0 sensor correction for a line of pixels: TLB.dll @ 0x100246d0.
 * acc_u16 in/out array of 3 elements for (R, G, B) next line smear accumulator.
 */
void pakon_sensor_correct_line_c(const uint16_t* raw, const uint16_t* dark,
                                const uint16_t* smear_q16, const uint16_t* gain_q16,
                                uint16_t* out, int width, uint64_t acc_u16[3]) {
    uint64_t sum[3] = {0, 0, 0};

    for (int i = 0; i < width; i++) {
        for (int c = 0; c < 3; c++) {
            int idx = i * 3 + c;
            uint16_t r_val = raw[idx] & 0xFFFF;
            uint16_t d_val = dark[idx] & 0xFFFF;
            uint16_t sm_val = smear_q16[idx] & 0xFFFF;
            uint16_t g_val = gain_q16[idx] & 0xFFFF;

            uint16_t sig = sat_sub_u16(r_val, d_val);
            uint16_t sm_sub = (uint16_t)((acc_u16[c] * sm_val) >> 16);
            sig = sat_sub_u16(sig, sm_sub);

            uint16_t v = (uint16_t)(((uint32_t)sig * (uint32_t)g_val) >> 16);
            /* 14-bit clamp: min(v, 0x3FFF) */
            uint16_t corrected = (v > 0x3FFF) ? 0x3FFF : v;
            out[idx] = corrected;
            sum[c] += corrected;
        }
    }

    if (width > 0) {
        for (int c = 0; c < 3; c++) {
            uint64_t next_acc = (sum[c] * 4) / (uint64_t)width;
            acc_u16[c] = (next_acc > 0xFFFF) ? 0xFFFF : next_acc;
        }
    }
}
