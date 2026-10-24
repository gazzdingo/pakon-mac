#ifndef PAKON_DECODE_LORES_WEIGHTS_H
#define PAKON_DECODE_LORES_WEIGHTS_H
/* TLB.dll lo-res decimation weights (RE 30 sec 7.1): 4x4 + 6x6 + 8x8 = 116 entries, the low 16 bits of the DLL's u32 tables at 0x10066120 /
 * 0x10066260 / 0x10066160. They are not compiled in (C9): they come from the user's own TLB.dll, copied out at vendor import. The blob is the
 * three u32 tables back to back (464 bytes, little endian) and is checked against a SHA-256 before use. */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"

#define PKD_LORES_BLOB 464

/* 1 once a blob has been loaded and verified in this process */
int pkd_lores_ready(void);
/* Row `l` of the ratio x ratio weight table, or NULL when not loaded / ratio not 4, 6 or 8. */
const uint16_t *pkd_lores_row(int ratio, int l);
/* Verifies and installs a blob (PK_E_CORRUPT when the hash differs). Idempotent for the same blob. */
pk_status pkd_lores_install(const uint8_t *blob, size_t n);
/* Cuts the blob out of TLB.dll bytes: needs TLB.dll 3.0.4.27 exactly (size and SHA-256 are checked). */
pk_status pkd_lores_from_tlb(const uint8_t *tlb, size_t n, uint8_t blob[PKD_LORES_BLOB]);
/* Reads a blob file / the three derived imau_tables files and installs it. PK_E_VENDOR_MISSING when absent. */
pk_status pkd_lores_load_blob_file(const char *path);
pk_status pkd_lores_load_derived(const char *derived_root);
#endif
