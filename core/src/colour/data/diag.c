#include "data/diag.h"
#include <string.h>

static _Thread_local pkc_diag *bound;

void pkc_diag_bind(pkc_diag *d) {
    if (d) memset(d, 0, sizeof *d);
    bound = d;
}

FILE *pkc_fopen(const char *path, const char *mode) {
    FILE *f = fopen(path, mode);
    if (bound && path) {
        size_t n = strlen(path);
        if (n >= sizeof bound->path) n = sizeof bound->path - 1;
        memcpy(bound->path, path, n);
        bound->path[n] = 0;
        bound->opened = f != NULL;
        bound->have = 1;
    }
    return f;
}
