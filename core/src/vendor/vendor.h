#ifndef PAKON_VENDOR_INTERNAL_H
#define PAKON_VENDOR_INTERNAL_H
/* Internal (pkvn_ prefix; pkv_ is the PKV reader's): the vendor functions over a caller-supplied manifest table. The
 * public ones pass the generated table. */
#include "pakon/vendor.h"

/* paths: accepted relative locations (first = where the store keeps the file), NULL-terminated early.
 * hash_only: verified, never handed out by pk_vendor_file. optional: absence is reported, not an error. */
typedef struct { int item; const char *paths[4]; size_t size; const char *sha256; int hash_only; int optional; } pkvn_row;

pk_status pkvn_open_with(const pkvn_row *rows, size_t n, const char *dest_root, pk_vendor **out);
pk_status pkvn_open_rep_with(const pkvn_row *rows, size_t n, const char *dest_root, pk_vendor_report *rep, pk_vendor **out);
pk_status pkvn_import_with(const pkvn_row *rows, size_t n, const char *src_dir, const char *dest_root, pk_vendor_report *out);

#endif
