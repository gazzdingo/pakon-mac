/* The model table, classification and base/geometry queries. Const data only; no global or static mutable state. */
#include "device/models.h"
#include "link/guard.h"
#include <stddef.h>

#define PK_G(...) { __VA_ARGS__, 0, 0 }
#define PK_GC(a, b, c, d, e, f, off, h) { a, b, c, d, e, f, off, h }
#define PK_G0 { 0, 0, 0, 0, 0, 0, 0, 0 }
#define PK_GEOM3(a, b, c) { a, b, c }

/* ------------------------------------------------------------------ build-time assertions over models.def (Task 4 note)
 * Every role address obeys PKL_ADDR_OK (non-zero, even, outside 0xA0..0xAF); on the TLB models dx == light; a BETA row
 * carries beta roles only and a VERIFIED row carries none. A violated rule is a negative array size: the build fails. */
#define PK_RA(a) ((a) == 0 || PKL_ADDR_OK(a))
#define PK_ROLES(l, m, h, d, l2, m2, d2, a2, g) (PK_RA(l) && PK_RA(m) && PK_RA(h) && PK_RA(d) && PK_RA(l2) && PK_RA(m2) && \
                                                   PK_RA(d2) && PK_RA(a2) && PK_RA(g) && (d) == (l)), \
                                                  ((l2) != 0 || (m2) != 0 || (d2) != 0 || (a2) != 0 || (g) != 0), ((l) == 0 && (m) == 0 && (h) == 0)
#define PK_MODEL(ID, NAME, SUP, FW, LINK, USB, LPID, ROLES, BASES, G35, G24, CAPS, ST0, ST1) \
    PK_MODEL_ASSERT(ID, SUP, ROLES)
#define PK_MODEL_ASSERT(ID, SUP, ...) PK_MODEL_ASSERT2(ID, SUP, __VA_ARGS__)
#define PK_MODEL_ASSERT2(ID, SUP, ok, has_beta, no_tlb) \
    typedef char pkm_assert_##ID[((ok) && ((SUP) == PK_SUPPORT_BETA ? ((has_beta) && (no_tlb)) : !(has_beta))) ? 1 : -1];
#include "tables/models.def"
#undef PK_MODEL
#undef PK_MODEL_ASSERT
#undef PK_MODEL_ASSERT2
#undef PK_ROLES
#undef PK_RA

/* ------------------------------------------------------------------ the table */
#define PK_ROLES(...) { __VA_ARGS__ }

typedef struct {
    pk_model m;
    pk_link_model link;
    pk_model_id usb_family;   /* the model the USB identity classifies as (F135 for both F-135s) */
    uint16_t loaded_pid;
} row;

#define PK_MODEL(ID, NAME, SUP, FW, LINK, USB, LPID, ROLES, BASES, G35, G24, CAPS, ST0, ST1) \
    [PK_MODEL_##ID] = { { PK_MODEL_##ID, NAME, SUP, FW, ROLES, BASES, G35, G24, CAPS, { ST0, ST1 } }, LINK, PK_MODEL_##USB, LPID },
static const row ROWS[PK_MODEL__COUNT] = {
#include "tables/models.def"
};
#undef PK_MODEL

const pk_model *pk_model_get(pk_model_id id) {
    if ((unsigned)id >= (unsigned)PK_MODEL__COUNT || ROWS[id].m.name == NULL) return NULL;
    return &ROWS[id].m;
}

/* The REV (device ID) the unloaded device reports and its boot EEPROM repeats: AA07 F-135, AA05 F-235, AA08 F-335 (the same
 * mapping as pk_device_classify). 0 for a NULL or unknown model. */
uint16_t pkm_boot_rev(const pk_model *m) {
    if (!m || (unsigned)m->id >= (unsigned)PK_MODEL__COUNT) return 0;
    switch (ROWS[m->id].usb_family) {
    case PK_MODEL_F135: return 0xAA07;
    case PK_MODEL_F235: return 0xAA05;
    case PK_MODEL_F335: return 0xAA08;
    default: return 0;
    }
}

pk_status pkm_loaded_identity(const pk_model *m, uint16_t *vid, uint16_t *pid) {
    if (!m || (unsigned)m->id >= (unsigned)PK_MODEL__COUNT) return PK_E_ARG;
    if (vid) *vid = 0x0F05;
    if (pid) *pid = ROWS[m->id].loaded_pid;
    return PK_OK;
}

/* The roles of a link model (the first table row that maps to it; the C variants share their family's roles). The link
 * (pk_link_open) takes a model id, never a caller-supplied struct (S-R11). */
pk_status pkl_roles_for_model(pk_link_model m, pk_link_roles *out) {
    if (!out) return PK_E_ARG;
    for (int i = 0; i < PK_MODEL__COUNT; i++) {
        if (ROWS[i].m.name && ROWS[i].link == m) { *out = ROWS[i].m.roles; return PK_OK; }
    }
    return PK_E_ARG;
}

const pk_model *pk_model_refine(const pk_model *usb, unsigned scanner_type) {
    if (!usb || (unsigned)usb->id >= (unsigned)PK_MODEL__COUNT) return NULL;
    pk_model_id fam = ROWS[usb->id].usb_family;
    for (int i = 0; i < PK_MODEL__COUNT; i++) {
        if (!ROWS[i].m.name || ROWS[i].usb_family != fam) continue;
        if (scanner_type != 0 && (ROWS[i].m.scanner_type[0] == scanner_type || ROWS[i].m.scanner_type[1] == scanner_type)) return &ROWS[i].m;
    }
    return NULL;
}

pk_status pk_model_check_base(const pk_model *m, int dpi_base) {
    if (!m) return PK_E_ARG;
    int bit = dpi_base == 4 ? 0 : dpi_base == 8 ? 1 : dpi_base == 16 ? 2 : -1;
    return bit >= 0 && (m->bases_mask >> bit & 1u) ? PK_OK : PK_E_UNSUPPORTED;
}

unsigned pk_words_per_line(const pk_model *m, int dpi_base, bool ir) {
    if (pk_model_check_base(m, dpi_base) != PK_OK) return 0;
    /* TLB FUN_10032d90: words per line = planes x PB+0x68, the hi-res pixels per line (3000 / 4500 / 6000 RGB, 4000 / 6000 / 8000 with IR on the F-135 Plus; RE 42 sec 1.1). Not the
     * CCD window: at base 8 the window is 2000 pixels but the line is 1500 (how the board maps one to the other is UNRESOLVED, RE 42 sec 12 item 3). */
    const pk_base_geom *g = &m->geom[dpi_base == 4 ? 0 : dpi_base == 8 ? 1 : 2];
    return g->hires_px > 0 ? (unsigned)(ir ? 4 : 3) * (unsigned)g->hires_px : 0;
}

pk_dev_class pk_device_classify(uint16_t vid, uint16_t pid, uint16_t rev) {
    pk_dev_class c = { PK_DEV_UNKNOWN, NULL };
    if ((vid == 0x04B4 && pid == 0x8613) || (vid == 0x0547 && pid == 0x1002)) { c.state = PK_DEV_BARE; return c; }
    if (vid != 0x0F05) return c;
    if (pid == 0xF235 && (rev >> 8) == 0xAA) {
        c.state = PK_DEV_UNLOADED;
        /* the REV picks the firmware (vendor INF, v1 FIRMWARE_BY_PERSONALITY): AA05 Pakon5 (F-235), AA07 Pakon7 (F-135),
         * AA08 Pakon8 (F-335). Any other 0xAAxx is unloaded with no model, so no image is ever chosen for it. */
        switch (rev & 0xFF) {
        case 0x05: c.model = pk_model_get(PK_MODEL_F235); break;
        case 0x07: c.model = pk_model_get(PK_MODEL_F135); break;
        case 0x08: c.model = pk_model_get(PK_MODEL_F335); break;
        default: break;
        }
        return c;
    }
    if (pid == 0xF135) { c.state = PK_DEV_LOADED; c.model = pk_model_get(PK_MODEL_F135); }
    else if (pid == 0x35F2) { c.state = PK_DEV_LOADED; c.model = pk_model_get(PK_MODEL_F235); }
    else if (pid == 0xF335) { c.state = PK_DEV_LOADED; c.model = pk_model_get(PK_MODEL_F335); }
    return c;
}
