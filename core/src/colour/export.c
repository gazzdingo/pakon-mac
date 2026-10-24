/* Exports: the u8 sRGB interleave of pk_colour_render, and two 16-bit exports for DNG that are ours (PSI has none). */
#include <stdlib.h>
#include "export.h"

void pkc_interleave_u8(const uint8_t *planes, size_t n, uint8_t *out) {
    for (size_t i = 0; i < n; i++) { out[3 * i] = planes[i]; out[3 * i + 1] = planes[n + i]; out[3 * i + 2] = planes[2 * n + i]; }
}

void pkc_interleave_u16(const uint16_t *planes, size_t n, uint16_t *out) {
    for (size_t i = 0; i < n; i++) { out[3 * i] = planes[i]; out[3 * i + 1] = planes[n + i]; out[3 * i + 2] = planes[2 * n + i]; }
}

void pkc_rpd12_to_u16(const int16_t *const p[3], size_t n, uint16_t *out) {
    for (size_t i = 0; i < n; i++) for (int c = 0; c < 3; c++) {
        int v = p[c][i]; v = v < 0 ? 0 : v > 4095 ? 4095 : v;
        out[3 * i + c] = (uint16_t)(v * 16 + v / 256);
    }
}

void pkc_linear14_to_u16(const uint16_t *const p[3], size_t n, uint16_t *out) {
    for (size_t i = 0; i < n; i++) for (int c = 0; c < 3; c++) {
        unsigned v = p[c][i]; if (v > 16383) v = 16383;
        out[3 * i + c] = (uint16_t)(v * 4);
    }
}

pk_status pk_colour_export_rpd16(const pk_colour *c, const pk_roll_input *in, const pk_roll_result *r, int frame,
                                 pk_image_u16 *out) {
    if (!out || !out->rgb) return PK_E_ARG;
    pkc_planes bal;
    pk_status st = pkc_colour_balanced(c, in, r, frame, NULL, 0, &bal);
    if (st) return st;
    pkc_rpd12_to_u16((const int16_t *const *)bal.p, (size_t)bal.w * bal.h, out->rgb);
    out->width = bal.w; out->height = bal.h;
    free(bal.p[0]);
    return PK_OK;
}

pk_status pk_colour_export_linear16(const pk_roll_input *in, int frame, pk_image_u16 *out) {
    if (!in || !out || !out->rgb || !in->frames || frame < 0 || frame >= in->n_frames) return PK_E_ARG;
    const pk_frame_linear *f = &in->frames[frame];
    if (!f->linear14[0] || !f->linear14[1] || !f->linear14[2] || f->width < 1 || f->height < 1) return PK_E_ARG;
    /* Digital ICE first when the roll has it on and the frame has an IR plane, on the crop as stored, the same step as the hi-res path (S-R46, RE 45 sec 4). */
    pk_frame_linear iced;
    uint16_t *scratch = NULL;
    pk_status st = pkc_ice_crop(in, f, &iced, &scratch);
    if (st) return st;
    pkc_linear14_to_u16(scratch ? (const uint16_t *const *)iced.linear14 : f->linear14, (size_t)f->width * f->height, out->rgb);
    free(scratch);
    out->width = f->width; out->height = f->height;
    return PK_OK;
}
