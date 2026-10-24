/* Warning sentences (Task 13, spec sec K, C53; RE 42 sec 7). The core holds no display text of its own beyond these English defaults, which are PSI's own where PSI has a
 * string (PSI.exe RT_STRING, language 1033, doubled spaces as PSI has them); the app may replace them. psi_string_id 0 = PSI shows no message for this bit.
 *   0x1000 -> string 44 (PSI shows it only when the roll has a strip count other than 1), 0x2000 -> 32769 (its "%s" argument is not traced, so it is left out),
 *   0x10000000 -> 39 on the F-135 / F-135 Plus and 36 on the F-235 / F-335 family (PSI's capability bit 0x1000000), 0x20000000 -> 37.
 * The speed bits 0x20 / 0x80 (the +-1 % ones, mask 0xA0): PSI answers them by calling AdjustMotorSpeed, an EEPROM write. This driver NEVER does (owner rule: scanner memory is
 * never written), so the bits are a warning only. */
#include "pakon/session.h"

static pk_warning_text emulsion(bool f235_family) {
    return f235_family
        ? (pk_warning_text){ 36, "The film was inserted with the emulsion side down.  For the best scan quality, the film should be inserted with the emulsion side up." }
        : (pk_warning_text){ 39, "The film was inserted with the emulsion side out.  For the best scan quality, the film should be inserted with the emulsion side in." };
}

pk_warning_text pk_warning_sentence_for(const pk_model *m, unsigned bit) {
    switch (bit) {
    case PK_SCANW_DX_BAD: return (pk_warning_text){ 0, "The edge code on this strip could not be read reliably." };
    case PK_SCANW_FILM_PRODUCT_AND_SPECIFIER_BAD: return (pk_warning_text){ 0, "The film product code read from the edge is not valid." };
    case PK_SCANW_SPEED_SLOW_HALF: return (pk_warning_text){ 0, "The film ran about half a percent slower than expected." };
    case PK_SCANW_SPEED_FAST_HALF: return (pk_warning_text){ 0, "The film ran about half a percent faster than expected." };
    case PK_SCANW_SPEED_SLOW_ONE: return (pk_warning_text){ 0, "The film ran about one percent slower than expected. PSI would re-tune the motor speed here; this driver does not, because it never writes scanner memory." };
    case PK_SCANW_SPEED_FAST_ONE: return (pk_warning_text){ 0, "The film ran about one percent faster than expected. PSI would re-tune the motor speed here; this driver does not, because it never writes scanner memory." };
    case PK_SCANW_FRAMING_100: case PK_SCANW_FRAMING_200: case PK_SCANW_FRAMING_400: case PK_SCANW_FRAMING_800:
        return (pk_warning_text){ 0, "Some frames on this strip could not be located exactly." };
    case PK_SCANW_MAX_FILM_LENGTH_EXCEEDED:
        return (pk_warning_text){ 44, "Either the film jammed during the scan or the film strip is longer than the scanner is configured to capture in one scan." };
    case PK_SCANW_LIGHT_DIM:
        return (pk_warning_text){ 32769, "An insufficient light condition exists. Scans may not be optimal.  If the problem persist, please contact technical support." };
    case PK_WARN_PSI_EMULSION_DOWN:
        return emulsion(m && (m->id == PK_MODEL_F235 || m->id == PK_MODEL_F235C || m->id == PK_MODEL_F335 || m->id == PK_MODEL_F335C));
    case PK_WARN_PSI_TAIL_FIRST: return (pk_warning_text){ 37, "The film was inserted tail first.  This can adversely affect the printing of the Index Sleeving." };
    default: return (pk_warning_text){ 0, "" };
    }
}

pk_warning_text pk_warning_sentence(unsigned bit) { return pk_warning_sentence_for(NULL, bit); }   /* the F-135 / F-135 Plus wording (string 39) */
