/* TLB.dll FUN_100246d0, the arithmetic of one scan line (RE 30 sec 5). Bit-exact with Kodak's MMX code under Unicorn (core_decode_kodak). */
#include "decode/kernel.h"

static inline uint16_t mulhu(uint32_t a, uint32_t b) { return (uint16_t)((a * b) >> 16); }
static inline uint16_t subus(uint32_t a, uint32_t b) { return a > b ? (uint16_t)(a - b) : 0; }

void pkd_kernel_init(pkd_kernel_state *s) { s->mean4[0] = s->mean4[1] = s->mean4[2] = 0; }

pk_status pkd_kernel_line(const pkd_kernel_cfg *c, pkd_kernel_state *s, const uint16_t *raw, uint16_t *out) {
    if (!c || !s || !raw || !out || !c->t || c->n_px <= 0 || (c->n_px & 3) || c->n_px != c->t->n_px ||
        (c->ratio != 4 && c->ratio != 6 && c->ratio != 8) || (c->channels != 3 && c->channels != 4)) return PK_E_ARG;
    const pk_cal_tables *t = c->t;
    const int n = c->n_px;
    for (int ch = 0; ch < c->channels; ch++) if (!t->dark[ch] || !t->gain[ch]) return PK_E_ARG;
    if (c->channels == 4) for (int ch = 0; ch < 3; ch++) if (!t->smear[ch]) return PK_E_ARG;   /* dark[3] / gain[3] checked above */
    uint32_t sum[3] = {0, 0, 0};
    for (int ch = 0; ch < 3; ch++) {
        const uint16_t sc = mulhu(s->mean4[ch], t->smearc[ch]);
        uint16_t *o = out + (size_t)ch * n;
        for (int p = 0; p < n; p++) {
            uint16_t v = subus(raw[3 * p + ch], t->dark[ch][p]);
            v = subus(v, c->channels == 3 ? sc : mulhu(s->mean4[ch], t->smear[ch][p]));
            v = mulhu(v, (uint16_t)(t->gain[ch][p] >> 2));
            if (v > 0x3FFF) v = 0x3FFF;
            o[p] = v; sum[ch] += v;
        }
    }
    if (c->channels == 4) {
        uint16_t *ir = out + 3 * (size_t)n;
        const uint16_t *r = out, *rawir = raw + 3 * (size_t)n;
        const unsigned f = c->ir_crosstalk_factor;
        const uint16_t k = f ? (uint16_t)(0x10000u / f) : 0;
        for (int p = 0; p < n; p++) {
            uint16_t v = mulhu(subus(rawir[p], t->dark[3][p]), (uint16_t)(t->gain[3][p] >> 2));
            if (f && c->ratio != 6) {
                /* TLB's tail loop reuses the clamp register for pmulhuw(R, k) of the previous group of 4 pixels (RE 30 sec 5.4): reproduced. */
                uint32_t cc = p < 4 ? 0xC000u : mulhu(r[p - 4], k);
                uint32_t u = v + cc; if (u > 0xFFFF) u = 0xFFFF;
                v = subus((uint16_t)(u - cc), mulhu(r[p], k));
            } else {
                if (v > 0x3FFF) v = 0x3FFF;
                if (f) v = subus(v, mulhu(r[p], k));
            }
            ir[p] = v;
        }
    }
    for (int ch = 0; ch < 3; ch++) s->mean4[ch] = (uint16_t)((sum[ch] * 4u) / (uint32_t)n);
    return PK_OK;
}
