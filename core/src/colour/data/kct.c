#include "data/diag.h"
#include "kct.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define KCT_IDX_BYTES (3u * 4096u * 2u * 4u)
#define KCT_OTAB_BYTES (3u * 16384u)

pk_status pkc_kct_load(const char *path, pkc_kct **out) {
  if (!path || !out) return PK_E_ARG;
  *out = NULL;
  FILE *f = pkc_fopen(path, "rb");
  if (!f) return PK_E_VENDOR_DATA;
  char m[4]; int32_t hdr[8];
  if (fread(m, 1, 4, f) != 4 || memcmp(m, "KCT1", 4) || fread(hdr, 4, 8, f) != 8 ||
      hdr[0] < 2 || hdr[0] > 64) { fclose(f); return PK_E_FORMAT; }
  size_t g = (size_t)hdr[0], nc = g * g * g * 6, total = KCT_IDX_BYTES + nc + KCT_OTAB_BYTES;
  /* exact size: the payload must be complete and nothing may follow it */
  if (fseek(f, 0, SEEK_END) || ftell(f) != (long)(36 + total) || fseek(f, 36, SEEK_SET)) {
    fclose(f); return PK_E_FORMAT;
  }
  pkc_kct *k = calloc(1, sizeof *k);
  void *blob = malloc(total);
  if (!k || !blob) { free(k); free(blob); fclose(f); return PK_E_NOMEM; }
  if (fread(blob, 1, total, f) != total) { free(k); free(blob); fclose(f); return PK_E_IO; }
  fclose(f);
  k->gridN = hdr[0]; k->offB = hdr[1]; k->offG = hdr[2]; k->offGB = hdr[3];
  k->offR = hdr[4]; k->offRB = hdr[5]; k->offRG = hdr[6]; k->offRGB = hdr[7];
  k->blob = blob;
  k->idx = (int32_t *)blob;
  k->clut = (uint16_t *)((char *)blob + KCT_IDX_BYTES);
  k->otab = (uint8_t *)blob + KCT_IDX_BYTES + nc;
  /* every clut read at base + off + 2*ch must stay inside the clut */
  int64_t maxoff = 0, mx[3] = {0, 0, 0}; int bad = 0;
  const int offs[7] = {k->offB, k->offG, k->offGB, k->offR, k->offRB, k->offRG, k->offRGB};
  for (int i = 0; i < 7; i++) { if (offs[i] < 0) bad = 1; if (offs[i] > maxoff) maxoff = offs[i]; }
  for (int c = 0; c < 3; c++)
    for (int i = 0; i < 4096; i++) {
      int32_t o = k->idx[(c * 4096 + i) * 2];
      if (o < 0) bad = 1; else if (o > mx[c]) mx[c] = o;
    }
  if (bad || mx[0] + mx[1] + mx[2] + maxoff + 6 > (int64_t)nc) { pkc_kct_free(k); return PK_E_FORMAT; }
  *out = k;
  return PK_OK;
}

void pkc_kct_free(pkc_kct *k) {
  if (!k) return;
  pkc_kfut_free(k->fut);
  free(k->blob);
  free(k);
}

pk_status pkc_kfut_load(const char *path, pkc_kfut **out) {
  if (!path || !out) return PK_E_ARG;
  *out = NULL;
  FILE *f = pkc_fopen(path, "rb");
  if (!f) return PK_E_VENDOR_DATA;
  char m[4]; int32_t h[11];
  if (fread(m, 1, 4, f) != 4 || memcmp(m, "KFT1", 4) || fread(h, 4, 11, f) != 11 || h[0] != 3 || h[1] != 3) {
    fclose(f); return PK_E_FORMAT;
  }
  size_t words = 0, cells = 1;
  for (int i = 0; i < 3; i++) {
    if (h[2 + i] < 2 || h[2 + i] > 65536 || h[5 + i] < 2 || h[5 + i] > 256 || h[8 + i] < 2 || h[8 + i] > 65536) {
      fclose(f); return PK_E_FORMAT;
    }
    words += (size_t)h[2 + i] + (size_t)h[8 + i];
    cells *= (size_t)h[5 + i];
  }
  words += 3 * cells;
  if (fseek(f, 0, SEEK_END) || ftell(f) != (long)(48 + 2 * words) || fseek(f, 48, SEEK_SET)) { fclose(f); return PK_E_FORMAT; }
  pkc_kfut *k = calloc(1, sizeof *k);
  uint16_t *b = malloc(2 * words);
  if (!k || !b) { free(k); free(b); fclose(f); return PK_E_NOMEM; }
  if (fread(b, 2, words, f) != words) { free(k); free(b); fclose(f); return PK_E_IO; }
  fclose(f);
  k->blob = b;
  const uint16_t *p = b;
  for (int i = 0; i < 3; i++) { k->in_n[i] = h[2 + i]; k->grid[i] = h[5 + i]; k->out_n[i] = h[8 + i]; }
  for (int i = 0; i < 3; i++) { k->itab[i] = p; p += k->in_n[i]; }
  for (int j = 0; j < 3; j++) { k->gtab[j] = p; p += cells; }
  for (int j = 0; j < 3; j++) { k->otab[j] = p; p += k->out_n[j]; }
  *out = k;
  return PK_OK;
}

void pkc_kfut_free(pkc_kfut *f) {
  if (!f) return;
  free(f->blob);
  free(f);
}
