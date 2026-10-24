#ifndef PAKON_ERROR_H
#define PAKON_ERROR_H
/* Rich error record for the scanner core: the status, the module that raised it, a formatted context, and the
 * newest (up to 8) raw packet exchanges seen before it. */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct { uint8_t dir; uint8_t len; uint8_t bytes[64]; } pk_exchange;   /* dir: 1 = host to device */
typedef struct {
    pk_status status;
    char module[16];
    char context[160];
    pk_exchange last[8];   /* oldest first */
    int n_last;
} pk_error;

/* Sets status, module and the printf-formatted context (truncated to fit). e may be NULL. Keeps the exchange ring. */
void pk_error_set(pk_error *e, pk_status s, const char *module, const char *fmt, ...);
/* Appends an exchange (first 64 bytes kept); once 8 are held the oldest is dropped. e may be NULL. */
void pk_error_push_exchange(pk_error *e, int dir_out, const uint8_t *p, size_t n);

#ifdef __cplusplus
}
#endif
#endif
