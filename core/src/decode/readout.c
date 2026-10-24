/* TLB.dll FUN_100013b0, the registered read-out (RE 30 sec 9, RE 45 sec 2.2): the three colour planes are stored a stagger d apart per plane and
 * registered here; the IR plane of a 4-plane record is the same stored row as plane 0. */
#include <string.h>
#include "decode/strip.h"

pk_status pkd_readout_planes(const uint16_t *const sp[], int planes, size_t stored_rows, int stride, int col, int width, int d, size_t row0, size_t rows,
                             uint16_t *const op[]) {
    if (!sp || !op || (planes != 3 && planes != 4) || width <= 0 || stride <= 0 || col < 0 || col > stride - width || d <= 0 || rows == 0 || rows < 2 * (size_t)d)
        return PK_E_ARG;
    for (int c = 0; c < planes; c++) if (!sp[c] || !op[c]) return PK_E_ARG;
    if (row0 >= stored_rows || rows > stored_rows - row0 || row0 + rows - 1 + 2 * (size_t)d >= stored_rows) return PK_E_ARG;
    for (size_t r = 0; r < rows; r++)
        for (int c = 0; c < planes; c++) {
            const size_t src = row0 + r + (c < 3 ? (size_t)c * (size_t)d : 0);
            memcpy(op[c] + r * (size_t)width, sp[c] + src * (size_t)stride + (size_t)col, (size_t)width * sizeof(uint16_t));
        }
    return PK_OK;
}

pk_status pkd_readout(const uint16_t *const sp[3], size_t stored_rows, int width, int d, size_t row0, size_t rows, uint16_t *const op[3]) {
    return pkd_readout_planes(sp, 3, stored_rows, width, 0, width, d, row0, rows, op);
}

pk_status pkd_strip_read_lores(const pkd_strip *s, size_t row0, size_t rows, uint16_t *const op[3]) {
    if (!s || (size_t)s->rows + 2 > (size_t)s->alloc_rows) return PK_E_ARG;      /* never read past the allocation */
    const uint16_t *sp[3] = { s->plane[0], s->plane[1], s->plane[2] };
    return pkd_readout_planes(sp, 3, (size_t)s->rows + 2, s->width, 0, s->width, PKD_LORES_STAGGER, row0, rows, op);
}
