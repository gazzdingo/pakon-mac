#ifndef PAKON_UTIL_UTIL_H
#define PAKON_UTIL_UTIL_H
/* Scanner-core util helpers (pku_ prefix, internal). */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"

typedef struct { uint32_t h[8]; uint64_t n; uint8_t buf[64]; size_t fill; } pku_sha256;
void pku_sha256_init(pku_sha256 *c);
void pku_sha256_update(pku_sha256 *c, const void *data, size_t n);
void pku_sha256_final(pku_sha256 *c, uint8_t out[32]);
void pku_sha256_hex(const void *data, size_t n, char out[65]);

/* RFC 4648 base64 with padding. Encode returns the length (0 if cap is too small: needs 4*ceil(n/3)+1); NUL-terminated. */
size_t pku_b64_encode(const uint8_t *in, size_t n, char *out, size_t cap);
/* PK_E_CORRUPT on a bad character, bad padding, bad length or overflow of cap. */
pk_status pku_b64_decode(const char *in, size_t len, uint8_t *out, size_t cap, size_t *got);

/* JSON-lines flat objects, parsed in place (line is modified). */
typedef struct { const char *key; const char *s; long long n; int is_str; } pku_jl_kv;
int pku_jl_parse(char *line, pku_jl_kv *kv, int max);   /* pair count, or -1 if malformed / too many pairs */
const pku_jl_kv *pku_jl_get(const pku_jl_kv *kv, int n, const char *key);

/* A small JSON DOM. Parse limits: 32 nested containers, input 64 MiB. Strings are unescaped (\" \\ \/ \n \t \uXXXX to UTF-8, surrogate
 * pairs joined); any other escape, a lone surrogate, \u0000, trailing text or truncation is PK_E_CORRUPT. */
typedef struct pku_json pku_json;
typedef enum { PKU_J_NULL, PKU_J_BOOL, PKU_J_NUM, PKU_J_STR, PKU_J_ARR, PKU_J_OBJ } pku_jtype;
pk_status pku_json_parse(const char *text, size_t n, pku_json **root);
/* As pku_json_parse, for a value that will sit base_depth containers deep inside a larger document (the 32-level limit
 * then counts from that document's root), so text that parses here also parses once embedded. */
pk_status pku_json_parse_at(const char *text, size_t n, int base_depth, pku_json **root);
void pku_json_free(pku_json *j);
pku_jtype pku_json_type(const pku_json *j);
const pku_json *pku_json_get(const pku_json *obj, const char *key);   /* first member named key, or NULL */
const pku_json *pku_json_at(const pku_json *j, size_t i);             /* array element or object member value, or NULL */
const char *pku_json_key(const pku_json *obj, size_t i);              /* object member name, or NULL */
size_t pku_json_len(const pku_json *j);                               /* array / object size, else 0 */
const char *pku_json_str(const pku_json *j);                          /* NULL unless a string */
double pku_json_num(const pku_json *j);                               /* 0 unless a number */
int pku_json_is_int(const pku_json *j);                               /* a number written without fraction or exponent that fits long long */
long long pku_json_int(const pku_json *j);
int pku_json_bool(const pku_json *j);

/* Append-only JSON builder. Errors (allocation, unbalanced use) are sticky and surface from pku_jw_finish as NULL. */
typedef struct pku_jw pku_jw;
pku_jw *pku_jw_new(void);
void pku_jw_free(pku_jw *w);
void pku_jw_obj_begin(pku_jw *w);
void pku_jw_obj_end(pku_jw *w);
void pku_jw_arr_begin(pku_jw *w);
void pku_jw_arr_end(pku_jw *w);
void pku_jw_key(pku_jw *w, const char *key);
void pku_jw_str(pku_jw *w, const char *s);               /* NULL writes null */
void pku_jw_int(pku_jw *w, long long v);
void pku_jw_uint(pku_jw *w, unsigned long long v);
void pku_jw_num(pku_jw *w, double v);
void pku_jw_bool(pku_jw *w, int v);
void pku_jw_null(pku_jw *w);
void pku_jw_raw(pku_jw *w, const char *json);            /* an already-valid JSON value */
const char *pku_jw_finish(pku_jw *w, size_t *len);       /* NUL-terminated, owned by w; NULL if an error occurred or containers are open */

pk_status pku_read_file(const char *path, uint8_t **data, size_t *n);   /* malloc'd; caller frees */
pk_status pku_write_file_atomic(const char *path, const void *data, size_t n);
pk_status pku_mkdirs(const char *path);
int pku_path_is_safe(const char *rel);

/* CRC-32 (IEEE 802.3, as in zip): pass 0 to start, the previous result to continue. */
uint32_t pku_crc32(uint32_t crc, const void *data, size_t n);

/* Stored-only zip (method 0, no zip64, one disk), CRC-32 checked. The reader works on a buffer the caller keeps alive; entry data points into it.
 * pku_zip_open is hostile-input safe: every header field is bounds-checked and cross-checked against its local header, and PK_E_CORRUPT is returned for
 * a compressed, encrypted, zip64 or multi-disk archive, a name that fails pku_path_is_safe (or ends in '/', or is over 255 bytes), a duplicate name,
 * more than max_entries entries, an entry over max_entry_size or a total over max_total, data outside the file or overlapping the directory or another entry,
 * a local header that disagrees with the central one (flags; sizes and CRC unless a data descriptor is flagged), trailing bytes, or a CRC mismatch. */
typedef struct pku_zip pku_zip;
typedef struct { char name[256]; const uint8_t *data; size_t size; } pku_zip_entry;
pk_status pku_zip_open(const uint8_t *buf, size_t n, size_t max_entries, size_t max_entry_size, size_t max_total, pku_zip **z);
size_t pku_zip_count(const pku_zip *z);
const pku_zip_entry *pku_zip_at(const pku_zip *z, size_t i);
const pku_zip_entry *pku_zip_find(const pku_zip *z, const char *name);   /* NULL if absent */
void pku_zip_close(pku_zip *z);

/* The writer copies what it is given and emits a deterministic archive (fixed DOS time). Names are 1..255 bytes without NUL; no other check is made. */
typedef struct pku_zipw pku_zipw;
pku_zipw *pku_zipw_new(void);
pk_status pku_zipw_add(pku_zipw *w, const char *name, const void *data, size_t n);
pk_status pku_zipw_finish(pku_zipw *w, uint8_t **out, size_t *n);        /* malloc'd; caller frees */
void pku_zipw_free(pku_zipw *w);

#endif
