/* Test helper: see synframe.h. */
#include "synframe.h"
#include <stdlib.h>
#include <string.h>

/* ---- numpy's legacy RandomState: MT19937 (init_genrand seeding), randint by masked rejection on 32-bit draws (int64
 * dtype, range < 2^32), uniform = low + (high - low) * ((a >> 5) * 2^26 + (b >> 6)) / 2^53 ---- */
typedef struct { uint32_t mt[624]; int i; } np_rs;

static void rs_seed(np_rs *s, uint32_t seed) {
    s->mt[0] = seed;
    for (int i = 1; i < 624; i++) s->mt[i] = 1812433253u * (s->mt[i - 1] ^ (s->mt[i - 1] >> 30)) + (uint32_t)i;
    s->i = 624;
}
static uint32_t rs_next(np_rs *s) {
    if (s->i >= 624) {
        for (int k = 0; k < 624; k++) {
            uint32_t y = (s->mt[k] & 0x80000000u) | (s->mt[(k + 1) % 624] & 0x7fffffffu);
            s->mt[k] = s->mt[(k + 397) % 624] ^ (y >> 1) ^ ((y & 1u) ? 0x9908b0dfu : 0u);
        }
        s->i = 0;
    }
    uint32_t y = s->mt[s->i++];
    y ^= y >> 11; y ^= (y << 7) & 0x9d2c5680u; y ^= (y << 15) & 0xefc60000u; y ^= y >> 18;
    return y;
}
static double rs_uniform(np_rs *s, double lo, double hi) {
    uint32_t a = rs_next(s) >> 5, b = rs_next(s) >> 6;
    return lo + (hi - lo) * (((double)a * 67108864.0 + (double)b) / 9007199254740992.0);
}
/* randint(lo, hi): one value in [lo, hi) */
static int64_t rs_randint(np_rs *s, int64_t lo, int64_t hi) {
    uint64_t rng = (uint64_t)(hi - 1 - lo), mask = rng;
    if (!rng) return lo;
    mask |= mask >> 1; mask |= mask >> 2; mask |= mask >> 4; mask |= mask >> 8; mask |= mask >> 16;
    uint64_t v;
    while ((v = (rs_next(s) & mask)) > rng) {}
    return lo + (int64_t)v;
}

static uint16_t clip_u16(double v) {             /* np.clip(v, 0, 4095).astype('<u2') */
    if (v < 0.0) v = 0.0;
    if (v > 4095.0) v = 4095.0;
    return (uint16_t)v;                          /* truncation, as astype */
}

/* npar rows (lab/vectors/gen_flesh_truth.py, npar_rows):
 *   [12, H, W, base0..2, amp, noise, seed, tex lo, tex hi, tex ncols (0: none)]                       gen_t12syn.frame
 *   [13, H, W, base0..2, gain0..2, line0..2, seed]                                                     gen_t13syn.frame
 *   [15, H, W, base0..2, amp, noise, seed, tex lo, tex hi, tex ncols, has bi, bi0..2]                 gen_t15syn.frame
 *   [16, H, W, X0..2, drop, ncols]                                                                     gen_t15syn.neutral
 *   [17, H, W, base0..2, amp0..2, noise0..2, seed]                                                     gen_t17syn.frame */
int synframe_numpy(const double q[20], uint16_t **out, int *pw, int *ph) {
    int gen = (int)q[0], H = (int)q[1], W = (int)q[2];
    if (H < 1 || W < 1 || H > 4096 || W > 4096) return -1;
    size_t n = (size_t)H * W;
    double *lo = malloc(3 * n * sizeof *lo);
    uint16_t *o = malloc(3 * n * sizeof *o);
    if (!lo || !o) { free(lo); free(o); return -1; }
    np_rs r;
    if (gen == 12 || gen == 15) {
        /* r = RandomState(seed); per channel: a, b = r.uniform(-1, 1, 2);
         * lo[c] = base[c] + amp * (a * yy / H + b * xx / W) + r.randint(-noise, noise + 1, (H, W)) */
        int amp = (int)q[6], noise = (int)q[7];
        rs_seed(&r, (uint32_t)q[8]);
        for (int c = 0; c < 3; c++) {
            double a = rs_uniform(&r, -1.0, 1.0), b = rs_uniform(&r, -1.0, 1.0);
            for (int y = 0; y < H; y++)
                for (int x = 0; x < W; x++) {
                    double g = a * (double)y / (double)H + b * (double)x / (double)W;
                    double v = (double)(int)q[3 + c] + (double)amp * g;
                    lo[(size_t)c * n + (size_t)y * W + x] = v + (double)rs_randint(&r, -noise, noise + 1);
                }
        }
        int tlo = (int)q[9], thi = (int)q[10], tn = (int)q[11];
        if (tn > 0) {
            /* blk = RandomState(11).randint(tlo, thi, (3, nb, tn)) (as float for t15, plus a +-bi checkerboard);
             * lo[c, :, W - bw * tn:] = kron(blk[c], ones((bh, bw))) -- t12: 24 x tn blocks of 10 x 7, t15: 25 x tn of 15 x 10 */
            int nb = gen == 12 ? 24 : 25, bh = gen == 12 ? 10 : 15, bw = gen == 12 ? 7 : 10;
            if (nb * bh != H || bw * tn > W) { free(lo); free(o); return -1; }
            double *blk = malloc((size_t)3 * nb * tn * sizeof *blk);
            if (!blk) { free(lo); free(o); return -1; }
            np_rs r11; rs_seed(&r11, 11);
            for (int i = 0; i < 3 * nb * tn; i++) blk[i] = (double)rs_randint(&r11, tlo, thi);
            if (gen == 15 && (int)q[12])
                for (int c = 0; c < 3; c++)
                    for (int i = 0; i < nb; i++)
                        for (int j = 0; j < tn; j++)
                            blk[(c * nb + i) * tn + j] += (double)((((i + j) % 2) * 2 - 1) * (int)q[13 + c]);
            for (int c = 0; c < 3; c++)
                for (int y = 0; y < H; y++)
                    for (int x = W - bw * tn; x < W; x++)
                        lo[(size_t)c * n + (size_t)y * W + x] = blk[(c * nb + y / bh) * tn + (x - (W - bw * tn)) / bw];
            free(blk);
        }
    } else if (gen == 13) {
        /* t = (yy / H + xx / W) / 2; lo[c] = base[c] + 400 * gain[c] * t + r.randint(-20, 21, (H, W));
         * v = RandomState(seed + 100).randint(300, 700, (25, 8)).astype(float);
         * lo[c, :, W - 80:] = kron(v * line[c], ones((15, 10))) */
        int seed = (int)q[12];
        rs_seed(&r, (uint32_t)seed);
        for (int c = 0; c < 3; c++) {
            double k = (double)(400 * (int)q[6 + c]);
            for (int y = 0; y < H; y++)
                for (int x = 0; x < W; x++) {
                    double t = ((double)y / (double)H + (double)x / (double)W) / 2.0;
                    double v = (double)(int)q[3 + c] + k * t;
                    lo[(size_t)c * n + (size_t)y * W + x] = v + (double)rs_randint(&r, -20, 21);
                }
        }
        if (H != 375 || W < 80) { free(lo); free(o); return -1; }
        double v[25 * 8];
        np_rs r2; rs_seed(&r2, (uint32_t)(seed + 100));
        for (int i = 0; i < 25 * 8; i++) v[i] = (double)rs_randint(&r2, 300, 700);
        for (int c = 0; c < 3; c++)
            for (int y = 0; y < H; y++)
                for (int x = W - 80; x < W; x++)
                    lo[(size_t)c * n + (size_t)y * W + x] = v[(y / 15) * 8 + (x - (W - 80)) / 10] * q[9 + c];
    } else if (gen == 16) {
        /* lo[c] = X[c]; lo[c, :, W - 10 * ncols:] = X[c] - drop */
        int drop = (int)q[6], nc = (int)q[7];
        for (int c = 0; c < 3; c++)
            for (int y = 0; y < H; y++)
                for (int x = 0; x < W; x++)
                    lo[(size_t)c * n + (size_t)y * W + x] = (double)((int)q[3 + c] - (x >= W - 10 * nc ? drop : 0));
    } else if (gen == 17) {
        /* r = RandomState(seed); per channel: a, b = r.uniform(-1, 1, 2);
         * lo[c] = base[c] + amp[c] * (a * yy / H + b * xx / W) / 2 + r.randint(-noise[c], noise[c] + 1, (H, W)) */
        rs_seed(&r, (uint32_t)q[12]);
        for (int c = 0; c < 3; c++) {
            double a = rs_uniform(&r, -1.0, 1.0), b = rs_uniform(&r, -1.0, 1.0);
            int amp = (int)q[6 + c], noise = (int)q[9 + c];
            for (int y = 0; y < H; y++)
                for (int x = 0; x < W; x++) {
                    double g = a * (double)y / (double)H + b * (double)x / (double)W;
                    double v = (double)(int)q[3 + c] + (double)amp * g / 2.0;
                    lo[(size_t)c * n + (size_t)y * W + x] = v + (double)rs_randint(&r, -noise, noise + 1);
                }
        }
    } else { free(lo); free(o); return -1; }
    for (size_t i = 0; i < 3 * n; i++) o[i] = clip_u16(lo[i]);
    free(lo);
    *out = o; *pw = W; *ph = H;
    return 0;
}

static uint32_t xs32(uint32_t *s) { uint32_t x = *s; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *s = x; }

int synframe_recipe(const int32_t *R, int len, uint16_t **out, int *pw, int *ph) {
    if (len < 8) return -1;
    int W = R[0], H = R[1], nr = R[7];
    if (W < 1 || H < 1 || W > 4096 || H > 4096 || nr < 0 || len != 8 + 8 * nr) return -1;
    size_t n = (size_t)W * H;
    int32_t *v = malloc(3 * n * sizeof *v);
    uint16_t *o = malloc(3 * n * sizeof *o);
    if (!v || !o) { free(v); free(o); return -1; }
    uint32_t s = (uint32_t)R[6] ? (uint32_t)R[6] : 1u;
    int amp = R[5];
    for (int c = 0; c < 3; c++)
        for (size_t i = 0; i < n; i++)
            v[(size_t)c * n + i] = R[2 + c] + (amp > 0 ? (int32_t)(xs32(&s) % (uint32_t)(2 * amp + 1)) - amp : 0);
    for (int k = 0; k < nr; k++) {
        const int32_t *q = R + 8 + 8 * k;
        int x0 = q[0] < 0 ? 0 : q[0], y0 = q[1] < 0 ? 0 : q[1], x1 = q[2] > W ? W : q[2], y1 = q[3] > H ? H : q[3];
        for (int c = 0; c < 3; c++)
            for (int y = y0; y < y1; y++)
                for (int x = x0; x < x1; x++)
                    v[(size_t)c * n + (size_t)y * W + x] = q[4 + c] + (q[7] > 0 ? (int32_t)(xs32(&s) % (uint32_t)(2 * q[7] + 1)) - q[7] : 0);
    }
    for (size_t i = 0; i < 3 * n; i++) o[i] = (uint16_t)(v[i] < 0 ? 0 : v[i] > 4095 ? 4095 : v[i]);
    free(v);
    *out = o; *pw = W; *ph = H;
    return 0;
}
