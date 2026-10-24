#ifndef PAKON_COLOUR_KODAK_MAP_H
#define PAKON_COLOUR_KODAK_MAP_H
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"

/* Kodak's data-file selection for a scene (docs/re/24 section 8): the film ISO from the product / gen codes, the .map
 * selection tables (AnsKeySelector) and the key -> file resolution of the Ansel cache. */

/* common-ProdCodeTable.dpi: 128 product codes x 16 gen codes of film ISO, in file order (comments '#' to end of line).
 * PK_E_ARG on NULLs; PK_E_VENDOR_DATA if the file is missing or does not hold exactly 2048 integers in int16 range. */
pk_status pkc_film_iso_load(const char *vendor_root, int16_t table[128][16]);
/* AnsCommonProdCodeTable lookup (0x101f1740) as getFilmIsoString uses it (0x101a2f1b..0x101a2f48): the table word for
 * 0 <= pc < 128 and 0 <= gc < 16 (signed word compares), else 0; a result <= 0 counts as 0 (unknown ISO). */
int pkc_film_iso(const int16_t table[128][16], int pc, int gc);

/* The value a selection column is matched against. */
enum { PKC_MAP_UNKNOWN = 0, PKC_MAP_STR, PKC_MAP_INT, PKC_MAP_ABSENT };
/* PKC_MAP_ABSENT: the scene context has no such key (Task 21, ruling R33: productCode / genCode when TLB passed -1 / -1,
 * i.e. no DX read): only `any` matches and every other cell simply does not -- Kodak skips sba.map's product rows then
 * and selects the default dpi (truth t21 codes_m1: the Preference block carries the default dpi's fpa / neu / neo). */
typedef struct { const char *name; int kind; const char *s; long v; } pkc_map_key;

/* First-match selection over a .map file's `mapping =` table (dataPathItems/<cap>/<cap>.map; RE 05): the line after
 * `mapping =` names the columns ("name type" pairs), every later non-comment line is a row of one cell per column plus
 * the result. A cell matches when it is `any`, equals the key (a string compared case-insensitively; an integer
 * compared as a number) or, for an integer, is a range `(a, b)` with a <= v <= b (both ends inclusive: Kodak-pinned by
 * noiseTable.map's (160, 200) / (800, 3200) at ISO 160 / 200 / 800 / 3200, truth t19 runs_codes). A column whose key
 * is not given (or PKC_MAP_UNKNOWN) only matches `any`; a row that would need its value is not decidable here:
 * (PKC_MAP_ABSENT: such a row just does not match)
 * PK_E_UNSUPPORTED if such a row is reached before a match. out receives the result token. PK_E_ARG on NULLs;
 * PK_E_VENDOR_DATA if the file is missing or malformed or no row matches; PK_E_FORMAT if the result does not fit. */
pk_status pkc_map_select(const char *map_path, const pkc_map_key *keys, int nkeys, char *out, size_t cap);

/* The file in directory dir (".dpi" files) whose `key =` is key, as the Ansel cache resolves keys. PK_E_VENDOR_DATA if
 * none or more than one file carries it, or the directory cannot be read. PK_E_FORMAT if the path does not fit. */
pk_status pkc_dpi_by_key(const char *dir, const char *key, char *out, size_t cap);
#endif
