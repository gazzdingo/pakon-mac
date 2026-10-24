#ifndef PAKON_COLOUR_KODAK_TEXT_H
#define PAKON_COLOUR_KODAK_TEXT_H

#include <stddef.h>
#include "pakon/status.h"

/* Parsed Kodak text data file (.dpi / .map / .lut / .tbl). */
typedef struct pkc_kt pkc_kt;

/* Missing/unreadable file -> PK_E_VENDOR_DATA. */
pk_status pkc_kt_load(const char *path, pkc_kt **out);
void pkc_kt_free(pkc_kt *kt);

/* First value token of the first entry named key, or NULL. */
const char *pkc_kt_str(const pkc_kt *kt, const char *key);

/* Numbers of the first entry named key (including continuation lines), up to
 * max. Stops at the first non-numeric token. Returns the count (0 if absent). */
int pkc_kt_num(const pkc_kt *kt, const char *key, double *vals, int max);

/* All entries named key, in file order. *tokens is a row-major array of
 * n * *ncols value tokens (short rows padded with ""), owned by kt.
 * Returns the row count (0 if none; *tokens = NULL, *ncols = 0). */
int pkc_kt_rows(const pkc_kt *kt, const char *key, char ***tokens, int *ncols);

/* 1 iff the whole of s is a plain decimal number, [+-]digits[.digits][(e|E)[+-]digits] (at least one digit before the
 * exponent): the one grammar every Kodak text value is checked against (pkc_kt_num, fugc.c's .lut rows). nan, inf and
 * hex, which strtod would take, are rejected. */
int pkc_kt_is_number(const char *s);

/* pkc_kt_is_number(s) and the whole token parses to a finite value; the parse is locale independent (strtod_l with a
 * private C locale), so a host's setlocale cannot change a Kodak number. Returns 1 and sets *v, else 0. */
int pkc_kt_parse_number(const char *s, double *v);

/* Reentrant replacement for strtok(s, " \t\r\n"): *cur is the caller's cursor (start it at the line). Returns the next
 * blank-separated token, NUL-terminated in place, or NULL at the end. No hidden state. */
char *pkc_kt_next_token(char **cur);

/* out = vendor_root + "/" + rel. PK_E_ARG on NULL, PK_E_FORMAT if it won't fit. */
pk_status pkc_vendor_path(const char *vendor_root, const char *rel, char *out, size_t cap);

#endif
