#include "front.h"
#include <math.h>
#include <pthread.h>

static inline float f32(double x) { return (float)x; }

void pkc_density_lut(uint16_t lut[16384]) {
    lut[0] = 16383;
    for (int i = 1; i < 16384; i++)
        lut[i] = (uint16_t)(int)(-3500.0 * log10((double)i * (1.0 / 16383.0)));
}

void pkc_poly3x10(const float k[3][10], const uint16_t *in[3], int16_t *out[3], size_t n) {
    for (size_t i = 0; i < n; i++) {
        double R = in[0][i], G = in[1][i], B = in[2][i];
        double RR = R * R, GG = G * G;
        double BB = f32(B * B), RG = f32(G * R), RB = f32(B * R), GB = f32(B * G);
        for (int c = 0; c < 3; c++) {
            const float *q = k[c];
            double acc = R * q[0];
            acc = acc + G * q[1];
            acc = acc + B * q[2];
            acc = acc + RR * q[3];
            acc = acc + GG * q[4];
            acc = acc + BB * q[5];
            acc = acc + RG * q[6];
            acc = acc + RB * q[7];
            acc = acc + GB * q[8];
            acc = acc + q[9];
            acc = acc + 0.5f;
            float v = f32(acc);
            if (!(v > 0.0f)) v = 0.0f;  /* also maps NaN to 0 */
            if (v > 4095.0f) v = 4095.0f;
            out[c][i] = (int16_t)(int)v;
        }
    }
}

static uint16_t g_lut[16384];
static pthread_once_t g_once = PTHREAD_ONCE_INIT;
static void build_lut(void) { pkc_density_lut(g_lut); }

void pkc_front(const float k[3][10], const uint16_t *lin[3], int16_t *rpd[3], size_t n) {
    pthread_once(&g_once, build_lut);
    const uint16_t *lut = g_lut;
    enum { CH = 512 };
    uint16_t tmp[3][CH];
    for (size_t o = 0; o < n; o += CH) {
        size_t m = n - o < CH ? n - o : CH;
        const uint16_t *ip[3]; int16_t *op[3];
        for (int c = 0; c < 3; c++) {
            for (size_t i = 0; i < m; i++) {
                uint16_t v = lin[c][o + i];
                tmp[c][i] = lut[v > 16383 ? 16383 : v];
            }
            ip[c] = tmp[c]; op[c] = rpd[c] + o;
        }
        pkc_poly3x10(k, ip, op, m);
    }
}
