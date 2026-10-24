#include "icc.h"
#include <stdio.h>
#include <stdlib.h>

/* int32 wraparound like the imul/add sequence (done in uint32 to avoid UB) */
static inline int32_t wmul(int32_t a, int32_t b) { return (int32_t)((uint32_t)a * (uint32_t)b); }
static inline int32_t wadd(int32_t a, int32_t b) { return (int32_t)((uint32_t)a + (uint32_t)b); }

/* The ETI evaluator's interpolation (identical to lab/kcms/c/kcms_eti.c): for the 12-bit triple (r, g, b) the three clut anchors A[ch]
 * and the signed int32 interpolation sums s[ch]; the 8-bit output is otab[ch][4 * A + (s >> 14)] (pkc_icc_eval). The 16-bit
 * evaluator below reads the same A and s, so both share this one body. */
static inline void eti_interp(const pkc_kct *t, uint32_t r, uint32_t g, uint32_t b, int32_t A[3], int32_t s[3]) {
  const int32_t *T0 = t->idx, *T1 = t->idx + 4096 * 2, *T2 = t->idx + 2 * 4096 * 2;
  const char *clut = (const char *)t->clut;
  int32_t fr = T0[r * 2 + 1], fg = T1[g * 2 + 1], fb = T2[b * 2 + 1];
  int base = T0[r * 2] + T1[g * 2] + T2[b * 2];
  int Pa, Pb; int32_t w0, w1, w2;
  if (fr > fg) {
    if (fg > fb)      { w0 = fr; w1 = fg; w2 = fb; Pa = t->offR;  Pb = t->offRG; }
    else if (fr > fb) { w0 = fr; w1 = fb; w2 = fg; Pa = t->offR;  Pb = t->offRB; }
    else              { w0 = fb; w1 = fr; w2 = fg; Pa = t->offB;  Pb = t->offRB; }
  } else {
    if (fg > fb) {
      if (fr > fb)    { w0 = fg; w1 = fr; w2 = fb; Pa = t->offG;  Pb = t->offRG; }
      else            { w0 = fg; w1 = fb; w2 = fr; Pa = t->offG;  Pb = t->offGB; }
    } else            { w0 = fb; w1 = fg; w2 = fr; Pa = t->offB;  Pb = t->offGB; }
  }
  for (int ch = 0; ch < 3; ch++) {
    const char *c = clut + base + 2 * ch;
    int32_t a = *(const uint16_t *)c;
    int32_t C = *(const uint16_t *)(c + Pa);
    int32_t B = *(const uint16_t *)(c + Pb);
    int32_t D = *(const uint16_t *)(c + t->offRGB);
    A[ch] = a;
    s[ch] = wadd(wadd(wmul(D - B, w2), wmul(C - a, w0)), wmul(B - C, w1));
  }
}

void pkc_icc_eval(const pkc_kct *t, const int16_t *in[3], uint8_t *out[3], size_t n) {
  const int16_t *in0 = in[0], *in1 = in[1], *in2 = in[2];
  const uint8_t *O0 = t->otab, *O1 = t->otab + 16384, *O2 = t->otab + 32768;
  uint32_t pk = 0, pb = 0xFFFFFFFFu;            /* asm cache key: (r<<16)|g, b */
  uint8_t o0 = 0, o1 = 0, o2 = 0;
  for (size_t i = 0; i < n; i++) {
    uint32_t r = (uint32_t)in0[i] & 0xFFF, g = (uint32_t)in1[i] & 0xFFF, b = (uint32_t)in2[i] & 0xFFF;
    uint32_t key = (r << 16) | g;
    if (!(key == pk && b == pb)) {
      pk = key; pb = b;
      int32_t A[3], s[3];
      eti_interp(t, r, g, b, A, s);
      o0 = O0[4 * A[0] + (s[0] >> 14)];       /* arithmetic shift, as sar */
      o1 = O1[4 * A[1] + (s[1] >> 14)];
      o2 = O2[4 * A[2] + (s[2] >> 14)];
    }
    out[0][i] = o0; out[1][i] = o1; out[2][i] = o2;
  }
}

/* ---- the small-call evaluator 0x100168d0 (lab/kcms/small_168d0.asm; reference model lab/kcms/fut_model.py). All
 * arithmetic is the asm's 32-bit integer one: unsigned where it uses mul / shr, signed where it uses imul / sar. ---- */

/* d * fr / 256, rounded (0x10016f06..0x10016f4a and 0x10016dcf..0x10016e0d): one multiply when d fits 11 signed bits,
 * else split into the low byte and the rest */
static int32_t fmul(int32_t d, uint32_t fr) {
  uint32_t m = (uint32_t)d & 0xfffff800u;
  if (m == 0 || m == 0xfffff800u) return (int32_t)((uint32_t)d * fr + 0x7fu) >> 8;
  return ((int32_t)(((uint32_t)d & 0xffu) * fr + 0x7fu) >> 8) + (d >> 8) * (int32_t)fr;
}

/* 0x10016ec0: table lookup with linear interpolation; x scaled by q + f / 2^15 into a 12.20 position */
static uint32_t flookup(const uint16_t *t, int n, uint32_t x, uint32_t q, uint32_t f) {
  uint32_t pos = x * q + ((x * f + 0x3fffu) >> 15);
  uint32_t idx = pos >> 20, fr = pos & 0xfffffu;
  int32_t v0 = t[idx];
  if (idx >= (uint32_t)(n - 1)) return (uint32_t)v0;
  return (uint32_t)(v0 + ((fmul((int32_t)t[idx + 1] - v0, fr) + 0x7ff) >> 12));
}

/* ((n - 1) << 20) / mx as an integer part and a 15-bit fraction (0x100169ef..0x10016a29; mx = 65535 through the
 * 0x80008001 multiply, 0x10016a30..0x10016a61, which is exact for 32-bit operands) */
static void fscale(uint32_t nm1, uint32_t mx, uint32_t *q, uint32_t *f) {
  uint32_t c = nm1 << 20;
  *q = c / mx;
  uint32_t r = c - *q * mx;
  *f = ((r << 15) + (mx > 1) - 1) / mx;
}

/* one body for both outputs: out8 (Kodak's 8-bit store) or out16 (the o16 it is made from) */
static void small_run(const pkc_kfut *f, const int16_t *in[3], uint8_t *out8[3], uint16_t *out16[3], size_t n) {
  uint32_t iq[3], ifr[3], gq[3], gf[3], oq[3], of[3];
  for (int c = 0; c < 3; c++) {
    fscale((uint32_t)f->in_n[c] - 1, 0xfff, &iq[c], &ifr[c]);         /* input type 10: 12 bits */
    fscale((uint32_t)f->grid[c] - 1, 65535, &gq[c], &gf[c]);
    fscale((uint32_t)f->out_n[c] - 1, 65535, &oq[c], &of[c]);
  }
  /* output type 3 (8 bits): out = (o16 * mult + rnd) >> 23, mult = (255 << 23) / 65535 (0x10016bc4..0x10016bf4) */
  const int32_t mult = (int32_t)((255u << 23) / 65535u), rnd = (1 << 22) - 1;
  for (size_t i = 0; i < n; i++) {
    uint32_t off = 0, fr[3];
    int32_t st[3];
    for (int c = 0; c < 3; c++) {
      uint32_t r = flookup(f->itab[c], f->in_n[c], (uint16_t)in[c][i] & 0xfffu, iq[c], ifr[c]);
      uint32_t g = r * gq[c] + ((r * gf[c] + 0x3fffu) >> 15);
      uint32_t ix = g >> 20;
      if (ix < (uint32_t)(f->grid[c] - 1)) fr[c] = g & 0xfffffu;
      else { fr[c] = 0xfffffu; ix--; }
      off = off * (uint32_t)f->grid[c] + ix;
    }
    st[2] = 1; st[1] = f->grid[2]; st[0] = f->grid[2] * f->grid[1];
    /* the sorting network for three inputs (0x100515ec: (0,1) (0,2) (1,2)): fractions descending, strides along */
    static const int pr[3][2] = { { 0, 1 }, { 0, 2 }, { 1, 2 } };
    for (int p = 0; p < 3; p++) {
      int a = pr[p][0], b = pr[p][1];
      if ((int32_t)fr[a] < (int32_t)fr[b]) {
        uint32_t t = fr[a]; fr[a] = fr[b]; fr[b] = t;
        int32_t u = st[a]; st[a] = st[b]; st[b] = u;
      }
    }
    for (int ch = 0; ch < 3; ch++) {
      const uint16_t *g = f->gtab[ch];
      uint32_t p = off;
      int32_t prev = g[p], acc = prev << 12;
      for (int d = 0; d < 3; d++) {
        p += (uint32_t)st[d];
        int32_t v1 = g[p];
        acc += fmul(v1 - prev, fr[d]);
        prev = v1;
      }
      uint32_t v = (uint32_t)((acc + 0x7ff) >> 12);
      uint32_t o16 = flookup(f->otab[ch], f->out_n[ch], v, oq[ch], of[ch]);
      if (out16) out16[ch][i] = (uint16_t)o16;
      else out8[ch][i] = (uint8_t)(((int32_t)o16 * mult + rnd) >> 23);
    }
  }
}

void pkc_icc_eval_small(const pkc_kfut *f, const int16_t *in[3], uint8_t *out[3], size_t n) { small_run(f, in, out, NULL, n); }
void pkc_icc_eval_small16(const pkc_kfut *f, const int16_t *in[3], uint16_t *out[3], size_t n) { small_run(f, in, NULL, out, n); }

/* ---- the 16-bit Kodak output (docs/re/50) ---- */

/* 8-bit store of the small-call evaluator: q = (o16 * MULT + RND) >> 23 (int32 arithmetic, as above). The o16 values that give
 * a code q are lo[q] .. hi[q] (an interval, the map is monotone). */
#define K8_MULT ((int64_t)((255u << 23) / 65535u))
#define K8_RND ((int64_t)((1 << 22) - 1))
static void k8_interval(int q, uint16_t *lo, uint16_t *hi) {
  int64_t l = q == 0 ? 0 : (((int64_t)q << 23) - K8_RND + K8_MULT - 1) / K8_MULT;
  int64_t h = q == 255 ? 65535 : ((((int64_t)(q + 1) << 23) - K8_RND - 1) / K8_MULT);
  *lo = (uint16_t)l; *hi = (uint16_t)(h > 65535 ? 65535 : h);
}

/* Fractional bits the 16-bit ETI evaluator keeps below the 14-bit table index of pkc_icc_eval. */
#define ETI_FINE 8

void pkc_icc_eval16(const pkc_kct *t, const int16_t *in[3], uint16_t *out[3], size_t n) {
  const pkc_kfut *f = t->fut;
  uint16_t lo[256], hi[256];
  for (int q = 0; q < 256; q++) k8_interval(q, &lo[q], &hi[q]);
  const int32_t maxp = (16384 << ETI_FINE) - 1;
  uint32_t pk = 0, pb = 0xFFFFFFFFu;
  uint16_t o[3] = { 0, 0, 0 };
  for (size_t i = 0; i < n; i++) {
    uint32_t r = (uint32_t)in[0][i] & 0xFFF, g = (uint32_t)in[1][i] & 0xFFF, b = (uint32_t)in[2][i] & 0xFFF;
    uint32_t key = (r << 16) | g;
    if (!(key == pk && b == pb)) {
      pk = key; pb = b;
      int32_t A[3], s[3];
      eti_interp(t, r, g, b, A, s);
      for (int ch = 0; ch < 3; ch++) {
        /* the position pkc_icc_eval indexes its table with, 4 * A + (s >> 14), carried with ETI_FINE more bits of s */
        int32_t p = (int32_t)((uint32_t)A[ch] << (2 + ETI_FINE)) + (s[ch] >> (14 - ETI_FINE));
        p = p < 0 ? 0 : p > maxp ? maxp : p;
        const int x14 = p >> ETI_FINE;
        const int q = t->otab[ch * 16384 + x14];                    /* the 8-bit code Kodak's ETI evaluator stores */
        /* the fut output curve at the same place: x14 / 16383 of the way along its n entries (docs/re/50 section 3) */
        const int n_out = f->out_n[ch];
        const uint16_t *ot = f->otab[ch];
        const uint64_t pos = (((uint64_t)p * (uint64_t)(n_out - 1)) << 20) / ((uint64_t)16383 << ETI_FINE);
        const uint32_t idx = (uint32_t)(pos >> 20), fr = (uint32_t)(pos & 0xfffffu);
        int32_t v = ot[idx < (uint32_t)n_out ? idx : (uint32_t)n_out - 1];
        if (idx < (uint32_t)(n_out - 1)) v += (fmul((int32_t)ot[idx + 1] - v, fr) + 0x7ff) >> 12;
        /* keep Kodak's 8-bit code exactly: the value stays inside the 8-bit code's own interval */
        o[ch] = (uint16_t)(v < lo[q] ? lo[q] : v > hi[q] ? hi[q] : v);
      }
    }
    out[0][i] = o[0]; out[1][i] = o[1]; out[2][i] = o[2];
  }
}

/* the tile cuts of one axis: start offsets of its tiles, the last ending at d.  Measured, not derived from Ima's tile
 * planner (docs/re/26 section 8; its tile-size limits 128 / 256 are static constants, so the rule is host-independent): Kodak-exact for every length 1..700 and the sizes around 256-multiples up to 2947, both
 * axes, with and without sharpening, saturation and B&W. */
static int tile_starts(int d, int usm, int *s, int cap) {
  int n = 0;
  s[n++] = 0;
  if (usm) {
    if (d >= 128) {
      int b = d / 2 + 1 < 129 ? d / 2 + 1 : 129;
      for (; b < d && n < cap; b += 256) s[n++] = b;
    }
  } else
    for (int b = 256; b < d && n < cap; b += 256) s[n++] = b;
  return n;
}

pk_status pkc_icc_eval_frame(const pkc_kct *k, const int16_t *in[3], uint8_t *out[3], int w, int h, int usm) {
  if (!k || !in || !out || w < 1 || h < 1) return PK_E_ARG;
  int nx = w / 128 + 3, ny = h / 128 + 3;
  int *sx = malloc(sizeof *sx * (size_t)(nx + ny)), *sy;
  if (!sx) return PK_E_NOMEM;
  sy = sx + nx;
  nx = tile_starts(w, usm, sx, nx);
  ny = tile_starts(h, usm, sy, ny);
  pk_status st = PK_OK;
  for (int ty = 0; ty < ny && !st; ty++)
    for (int tx = 0; tx < nx; tx++) {
      const int x0 = sx[tx], x1 = tx + 1 < nx ? sx[tx + 1] : w, y0 = sy[ty], y1 = ty + 1 < ny ? sy[ty + 1] : h;
      /* SpEvaluate: w * h * 3 > 1499 samples -> ETI, else the small-call evaluator (RE 09) */
      const int small = (long long)(x1 - x0) * (y1 - y0) * 3 <= 1499;
      if (small && !k->fut) { st = PK_E_VENDOR_DATA; break; }
      for (int y = y0; y < y1; y++) {
        size_t o = (size_t)y * w + x0;
        const int16_t *ip[3] = { in[0] + o, in[1] + o, in[2] + o };
        uint8_t *op[3] = { out[0] + o, out[1] + o, out[2] + o };
        if (small) pkc_icc_eval_small(k->fut, ip, op, (size_t)(x1 - x0));
        else pkc_icc_eval(k, ip, op, (size_t)(x1 - x0));
      }
    }
  free(sx);
  return st;
}

pk_status pkc_icc_eval_frame16(const pkc_kct *k, const int16_t *in[3], uint16_t *out[3], int w, int h, int usm) {
  if (!k || !in || !out || w < 1 || h < 1) return PK_E_ARG;
  if (!k->fut) return PK_E_VENDOR_DATA;                        /* the output curve and the small tiles both need the fut tables */
  int nx = w / 128 + 3, ny = h / 128 + 3;
  int *sx = malloc(sizeof *sx * (size_t)(nx + ny)), *sy;
  if (!sx) return PK_E_NOMEM;
  sy = sx + nx;
  nx = tile_starts(w, usm, sx, nx);
  ny = tile_starts(h, usm, sy, ny);
  for (int ty = 0; ty < ny; ty++)
    for (int tx = 0; tx < nx; tx++) {
      const int x0 = sx[tx], x1 = tx + 1 < nx ? sx[tx + 1] : w, y0 = sy[ty], y1 = ty + 1 < ny ? sy[ty + 1] : h;
      const int small = (long long)(x1 - x0) * (y1 - y0) * 3 <= 1499;
      for (int y = y0; y < y1; y++) {
        size_t o = (size_t)y * w + x0;
        const int16_t *ip[3] = { in[0] + o, in[1] + o, in[2] + o };
        uint16_t *op[3] = { out[0] + o, out[1] + o, out[2] + o };
        if (small) pkc_icc_eval_small16(k->fut, ip, op, (size_t)(x1 - x0));
        else pkc_icc_eval16(k, ip, op, (size_t)(x1 - x0));
      }
    }
  free(sx);
  return PK_OK;
}

pk_status pkc_icc_select(const char *derived_root, int film_class, int saturation, int bnw, pkc_kct **out) {
  if (!derived_root || !out || saturation < -5 || saturation > 5 || bnw < 0 || bnw > 3) return PK_E_ARG;
  static const char *const sat[11] = {"satminus15", "satminus12", "satminus09", "satminus06", "satminus03",
                                      "unity", "satplus03", "satplus06", "satplus09", "satplus12", "satplus15"};
  static const char *const bw[4] = {"unity", "warm_bw", "cold_bw", "sepia"};
  const char *p0 = (film_class == 0 || film_class == 4) ? "romm" : "rpd";
  char path[1024];
  int len = snprintf(path, sizeof path, "%s/kcms/%s__%s__%s.kct", derived_root, p0, sat[saturation + 5], bw[bnw]);
  if (len < 0 || (size_t)len >= sizeof path) return PK_E_FORMAT;
  pk_status st = pkc_kct_load(path, out);
  if (st || film_class == 0 || film_class == 4) return st;    /* romm (not on the colour-negative path): ETI only */
  len = snprintf(path, sizeof path, "%s/kcms/fut/%s__%s__%s.kfut", derived_root, p0, sat[saturation + 5], bw[bnw]);
  if (len < 0 || (size_t)len >= sizeof path) st = PK_E_FORMAT;
  else st = pkc_kfut_load(path, &(*out)->fut);
  if (st) { pkc_kct_free(*out); *out = NULL; }
  return st;
}

int pkc_icc_tile_sizes(int d, int usm, int *sizes, int cap) {
    int s[64], n = d < 1 || cap < 1 ? 0 : tile_starts(d, usm, s, 64 < cap ? 64 : cap);
    for (int i = 0; i < n; i++) sizes[i] = (i + 1 < n ? s[i + 1] : d) - s[i];
    return n;
}
