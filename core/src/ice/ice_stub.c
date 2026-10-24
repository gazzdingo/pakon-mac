/* Digital ICE is not built (PK_WITH_ICE=OFF, the public tree: src/ice/variants.c is generated from Kodak's code and is not published).
 * Callers must check pk_ice_available() and not offer ICE; a save that still asks for it fails with PK_E_UNSUPPORTED and writes nothing. */
#include "pakon/ice.h"

int pk_ice_available(void) { return 0; }

pk_status pk_ice_apply(uint16_t *r, uint16_t *g, uint16_t *b, uint16_t *ir, int w, int h, size_t stride,
                       const pk_ice_opts *opts, pk_ice_stats *out) {
    (void)r; (void)g; (void)b; (void)ir; (void)w; (void)h; (void)stride; (void)opts; (void)out;
    return PK_E_UNSUPPORTED;
}
