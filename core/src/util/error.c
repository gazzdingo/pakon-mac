#include "pakon/error.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

void pk_error_set(pk_error *e, pk_status s, const char *module, const char *fmt, ...) {
    if (!e) return;
    e->status = s;
    snprintf(e->module, sizeof e->module, "%s", module ? module : "");
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(e->context, sizeof e->context, fmt ? fmt : "", ap);
    va_end(ap);
}

void pk_error_push_exchange(pk_error *e, int dir_out, const uint8_t *p, size_t n) {
    if (!e) return;
    if (e->n_last < 0) e->n_last = 0;
    if (e->n_last >= 8) { memmove(&e->last[0], &e->last[1], 7 * sizeof e->last[0]); e->n_last = 7; }
    pk_exchange *x = &e->last[e->n_last++];
    x->dir = dir_out ? 1 : 0;
    x->len = (uint8_t)(n > 64 ? 64 : n);
    if (x->len && p) memcpy(x->bytes, p, x->len); else x->len = 0;
}
