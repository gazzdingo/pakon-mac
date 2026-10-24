#ifndef PAKON_VENDOR_H
#define PAKON_VENDOR_H
/* Kodak/PSI vendor files the scanner driver needs (firmware images, F-235/F-335 driver files, Config/Firmware images).
 * The manifest (core/tables/vendor_manifest.def) holds sizes and SHA-256 only; the bytes come from the user's install.
 * Required: the four F-135 firmware images (PknInit, Pakon5, Pakon7 2004, Pakon8). Everything else is optional: reported
 * when absent, hash-verified when present. A vendor folder is treated as hostile (see pk_vendor_import). */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The enum is generated into core/tables/vendor_items.def by tools/gen_vendor_manifest.py. The first ten:
 * PKV_PKNINIT_HEX, PKV_PAKON5_HEX, PKV_PAKON7_HEX_2004, PKV_PAKON7_HEX_2006, PKV_PAKON8_HEX, PKV_F235_PAKON_HEX,
 * PKV_F235_PAKON1_HEX, PKV_F235_PAKON2_HEX, PKV_F235_PAKON5_HEX, PKV_F235_PKNINIT_HEX; then the other F-235 and the F-335
 * driver files, then PKV_FW_<name>_HEX for every Config/Firmware image. */
typedef enum {
#define PKV_ITEM(n) n,
#include "../../tables/vendor_items.def"
#undef PKV_ITEM
    PKV_ITEM__COUNT
} pk_vendor_item;

typedef struct pk_vendor pk_vendor;
typedef struct {
    size_t n_ok;         /* items present in the store afterwards (verified) */
    size_t n_added;      /* of those, items this import wrote (all of n_ok for a fresh store) */
    size_t n_missing;    /* items not found (optional ones included) */
    size_t n_mismatch;   /* items found but wrong size/hash, or refused as hostile */
    char names[16][96];  /* first 16 problem items (required and missing, or mismatched), "" after the last */
} pk_vendor_report;
typedef struct { uint8_t *data; size_t len; } pk_bytes;

/* Copies every manifest file found under src_dir into dest_root/3.0.4.27/ after verifying all of them in memory
 * (accepted layouts: CD root, fx35install/..., program files/Pakon/..., or a bare Pakon folder). All or nothing: on any
 * failure nothing is written to dest_root and nothing is ever deleted. A symlink, a non-regular file, a file whose size is
 * not the manifest's, or a path escaping src_dir is PK_E_CORRUPT; a missing required item or a hash mismatch is
 * PK_E_VENDOR_MISSING; the report names up to 16 offenders. An existing store is verified (a damaged one is PK_E_CORRUPT, nothing written) and then gains the verified items it
 * lacks, each written whole; items already in it are never replaced; n_added counts them.
 * A write failure after verification (PK_E_IO) can leave a dest_root/.tmp.<pid> folder, which is never read. */
pk_status pk_vendor_import(const char *src_dir, const char *dest_root, pk_vendor_report *out);
/* Opens dest_root/3.0.4.27/ and verifies the hash of every present file. A missing required item or a hash mismatch is
 * PK_E_VENDOR_MISSING, a symlink / wrong-size file PK_E_CORRUPT; pk_vendor_open_ex also names the offenders. */
pk_status pk_vendor_open(const char *dest_root, pk_vendor **out);
pk_status pk_vendor_open_ex(const char *dest_root, pk_vendor_report *rep, pk_vendor **out);
/* Re-reads and re-verifies the file. caller frees out->data. PK_E_VENDOR_MISSING if absent; PK_E_ARG for a hash-only item. */
pk_status pk_vendor_file(pk_vendor *v, pk_vendor_item item, pk_bytes *out);
/* The manifest SHA-256 (lowercase hex) of an item that is present (any item; Config/Firmware images are only reachable this way). */
pk_status pk_vendor_hash_only(pk_vendor *v, pk_vendor_item item, char sha256_hex[65]);
/* 1 if the item is present in this store. */
int pk_vendor_has(const pk_vendor *v, pk_vendor_item item);
void pk_vendor_close(pk_vendor *v);

/* Lo-res decimation weights (C9). The 116 weights of TLB.dll's lo-res strip are not compiled into libpakon: they are cut out of the user's own
 * TLB.dll (3.0.4.27, size and SHA-256 checked) when pk_vendor_import runs, into dest_root/3.0.4.27/lores_weights.bin (464 bytes, hash-checked
 * again on load). TLB.dll is optional for the import (without it the store simply has no weights and a scan cannot be decoded).
 * pk_lores_weights_import does the copy on its own (pk_vendor_import calls it after a successful import and ignores its status).
 * PK_E_VENDOR_MISSING: no TLB.dll under src_dir; PK_E_CORRUPT: a TLB.dll that is not 3.0.4.27. An existing lores_weights.bin is never replaced. */
pk_status pk_lores_weights_import(const char *src_dir, const char *dest_root);
/* Installs the weights for this process: first dest_root/3.0.4.27/lores_weights.bin, then the derived tables of the owner's build
 * (derived_root/imau_tables/tlb_lores_*.bin, same bytes). Either argument may be NULL. Call once at start; pk_roll_open also tries
 * calstore_root/vendor itself. PK_E_VENDOR_MISSING when neither has them. Decoding a strip without weights fails with PK_E_VENDOR_MISSING. */
pk_status pk_lores_weights_load(const char *dest_root, const char *derived_root);
/* 1 when the weights are installed in this process. */
int pk_lores_weights_loaded(void);

#ifdef __cplusplus
}
#endif
#endif
