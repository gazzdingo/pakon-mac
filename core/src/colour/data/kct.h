#ifndef PAKON_COLOUR_KCT_H
#define PAKON_COLOUR_KCT_H
#include <stdint.h>
#include "pakon/status.h"

/* Evaluator-resolved KCMS table (RE 09, lab/kcms/README.md "Format of .kct"):
 * "KCT1", int32 gridN, int32 off[7] (B,G,GB,R,RB,RG,RGB), then idx (3*4096*2
 * int32), clut (gridN^3*3 u16), otab (3*16384 u8). Little-endian host assumed. */
/* The composed transform's fut tables (Task 21, docs/re/09 "Small-call path"): what kodakcms' small-call evaluator
 * 0x100168d0 reads, dumped from kodakcms.dll by lab/kcms/dump_kfut.py: "KFT1", int32 nin (3), nout (3), in_n[3], grid[3],
 * out_n[3], then the u16 input tables (in_n each), grids (prod(grid) each, input 0 slowest) and output tables (out_n each). */
typedef struct pkc_kfut {
  int in_n[3], grid[3], out_n[3];
  const uint16_t *itab[3], *gtab[3], *otab[3];
  void *blob;
} pkc_kfut;

typedef struct pkc_kct {
  pkc_kfut *fut;    /* the same transform's fut (pkc_icc_select loads it; NULL from pkc_kct_load alone) */
  int gridN;
  int offB, offG, offGB, offR, offRB, offRG, offRGB;
  int32_t *idx;     /* [3][4096][2] {byteOffset, weight} */
  uint16_t *clut;
  uint8_t *otab;    /* [3][16384] */
  void *blob;
} pkc_kct;

/* Missing/unreadable file -> PK_E_VENDOR_DATA; bad magic/size/offsets -> PK_E_FORMAT. */
pk_status pkc_kct_load(const char *path, pkc_kct **out);
void pkc_kct_free(pkc_kct *k);     /* frees k->fut too */
/* Missing/unreadable -> PK_E_VENDOR_DATA; bad magic, counts (nin / nout != 3, a table under 2 or over 65536 entries, a
 * grid side under 2 or over 256) or size -> PK_E_FORMAT. */
pk_status pkc_kfut_load(const char *path, pkc_kfut **out);
void pkc_kfut_free(pkc_kfut *f);
#endif
