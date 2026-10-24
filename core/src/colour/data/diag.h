#ifndef PAKON_COLOUR_DATA_DIAG_H
#define PAKON_COLOUR_DATA_DIAG_H
#include <stdio.h>

/* Which Kodak file a load failed on (pk_colour_open_ex, R6). Every loader opens its files through pkc_fopen, which notes the
 * path and whether the open worked in the diag record the calling thread bound for the duration of one call (the record
 * lives on that caller's stack; nothing persists after pkc_diag_bind(NULL) and no state is shared between threads). The last
 * file touched when a load fails is the one reported: "cannot be opened" if its open failed, otherwise its content was
 * rejected (a loader returns PK_E_VENDOR_DATA after reading it). */
typedef struct pkc_diag { char path[1100]; int opened; int have; } pkc_diag;

void pkc_diag_bind(pkc_diag *d);                 /* this thread's record, or NULL to unbind */
FILE *pkc_fopen(const char *path, const char *mode);   /* fopen + note */
#endif
