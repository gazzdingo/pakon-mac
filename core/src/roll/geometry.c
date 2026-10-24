/* Roll geometry: the per-base numbers decode and framing agree on, TLB's hi-res readable line count, the rectangle checks and the 180 degree turn of the lo-res frame.
 * Evidence: docs/re/30-tlb-scan-kernel.md sec 8.2 (readable lines), docs/re/31-framing.md sec 8 (the frame rectangles), models.def (geom). */
#include "roll/roll_internal.h"

pk_status pkr_geometry(const pk_model *m, int dpi_base, bool ir, pkr_geom *g) {
    if (!m || !g) return PK_E_ARG;
    if (pk_model_check_base(m, dpi_base) != PK_OK) return PK_E_UNSUPPORTED;
    const pk_base_geom *b = &m->geom[dpi_base == 4 ? 0 : dpi_base == 8 ? 1 : 2];
    if (b->hires_px <= 0 || b->lores_decim <= 0 || b->lores_px <= 0 || b->frame_lines <= 0 || b->hires_px % 4 != 0 || b->hires_px != b->lores_px * b->lores_decim)
        return PK_E_UNSUPPORTED;
    g->ratio = b->lores_decim;
    g->hires_px = b->hires_px;
    g->lores_px = b->lores_px;
    g->frame_lines = b->frame_lines;
    g->planes = ir ? 4 : 3;
    return PK_OK;
}

size_t pkr_hires_readable_lines(size_t film_lines, int ratio, int planes) {
    const size_t back = (size_t)(planes - 1) * (size_t)ratio;
    return film_lines > back ? film_lines - back : 0;
}

pk_status pkr_check_rect(const pkr_geom *g, size_t film_lines, const pk_frame_rect *r) {
    if (!g || !r) return PK_E_ARG;
    const size_t readable = pkr_hires_readable_lines(film_lines, g->ratio, g->planes);
    if (r->top < 0 || r->bottom < r->top || (size_t)r->bottom >= readable) return PK_E_CORRUPT;
    if ((size_t)(r->bottom - r->top + 1) < (size_t)2 * (size_t)g->ratio) return PK_E_CORRUPT;       /* pkd_readout_planes: rows >= 2 d */
    if (r->lo_top < 0 || r->lo_bottom < r->lo_top) return PK_E_CORRUPT;
    if (r->lo_bottom - r->lo_top + 1 < 2 * PKD_LORES_STAGGER) return PK_E_CORRUPT;
    return PK_OK;
}

void pkr_rotate180(uint16_t *p, size_t w, size_t h) {
    const size_t n = w * h;
    for (size_t i = 0; i < n / 2; i++) { uint16_t t = p[i]; p[i] = p[n - 1 - i]; p[n - 1 - i] = t; }
}
