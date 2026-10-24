#ifndef PAKON_ROLL_INTERNAL_H
#define PAKON_ROLL_INTERNAL_H
/* Internal to the roll module (prefix pkr_, ruling C31): the roll object, shared by roll.c and colour_input.c. */
#include <stdbool.h>
#include <stdio.h>
#include "pakon/calib.h"
#include "pakon/calstore.h"
#include "pakon/device.h"
#include "pakon/dx.h"
#include "pakon/framing.h"
#include "pakon/roll.h"
#include "pakon/stream.h"
#include "calib/calib.h"
#include "decode/kernel.h"
#include "decode/strip.h"

/* Per-base geometry of the roll (pk_base_geom of the sidecar's model and base). */
typedef struct {
    int ratio;              /* hi-res lines per lo-res row: 4 / 6 / 8 (also the hi-res read-out stagger d) */
    int hires_px;           /* pixels per line = the kernel's n_px = the hi-res frame width */
    int lores_px;           /* lo-res pixels per row (250) */
    int frame_lines;        /* the frame height in hi-res lines (strip+0xc74): 1500 / 2250 / 3000 */
    int planes;             /* 3, or 4 with IR */
} pkr_geom;
pk_status pkr_geometry(const pk_model *m, int dpi_base, bool ir, pkr_geom *g);

/* TLB's hi-res buffer FUN_10003860 (RE 30 sec 8.2): lines - (planes - 1) * ratio, 0 below that. This is the framing's strip_lines. */
size_t pkr_hires_readable_lines(size_t film_lines, int ratio, int planes);

/* A frame rectangle checked against the strip: PK_E_CORRUPT when it cannot be read out (negative, past the readable lines, or too short for the stagger). */
pk_status pkr_check_rect(const pkr_geom *g, size_t film_lines, const pk_frame_rect *r);

/* Reverses a plane's samples (a 180 degree turn of a w x h plane). */
void pkr_rotate180(uint16_t *plane, size_t w, size_t h);

/* ---- the roll ---- */
typedef struct {
    bool decoded;
    uint64_t seg_start;         /* byte offset of the strip's first synced line (the segment start, where TLB initialises the kernel); = byte_start in a sidecar that predates it */
    size_t pre;                 /* lines from the segment start to the film-detect line (fed to the kernel with the film flag off) */
    size_t tail;                /* 1 when the strip ended and the raw file holds the ENDING line (the line at byte_end): TLB feeds it to the kernel with film 1 but it is not a hi-res line (S-R44) */
    uint64_t byte_start;        /* the film-detect line (sidecar line_start): hi-res line 0 of the strip */
    size_t lines;               /* whole film lines present in the raw file, from byte_start (the detect line included) */
    pkd_strip *strip;           /* the lo-res strip and the row profile (NULL when lines == 0) */
    uint16_t (*mean4)[3];       /* the kernel state after each line from the segment start (pre + lines entries), for the exact re-run of pass 2 */
    pk_framing *fr;             /* NULL when lines == 0 */
    uint32_t sums_end[3];       /* S-R41: the roll's profile sums after this strip (the strip shares this array while it decodes) */
    bool dx_done;
    pk_dx *dx;
    pk_dx_strip dxr;
    bool manual;
    int man_product, man_spec;
    const struct pku_json *js;  /* the sidecar's strip object */
} pkr_strip;

struct pk_roll {
    char raw_path[1024];
    pk_sidecar *sc;
    const pk_model *model;
    int dpi_base;
    bool ir, complete;
    unsigned ir_xtalk;          /* the scan's IrCrossTalkFactor (sidecar scan_config, default 10, clamped 1..20): the kernel's IR cross-talk argument on an IR roll (S-R45 a) */
    unsigned words_per_line;
    pkr_geom geom;
    uint64_t raw_size;
    FILE *fp;                   /* the raw file, read only */
    int n_strips;
    pkr_strip *st;
    pk_calstore *store;
    /* loaded on first decode */
    bool cal_loaded;
    pk_calibration *cal;
    pk_cal_tables tables;
    pk_eeprom *ee;
    uint32_t sums[3];           /* S-R41: zeroed once here; each strip starts from the previous strip's sums_end (strip 0 from this) */
};

/* Loads the calibration tables and the EEPROM image (once). PK_E_NOT_FOUND when the sidecar names no calibration, the store lacks it, or the unit has no EEPROM image. */
pk_status pkr_load_calibration(pk_roll *r);
/* Reads `n` whole lines starting at line `first` COUNTED FROM THE SEGMENT START (pre + hi-res line index) into out (n * words_per_line words). PK_E_CORRUPT when a line does not start with a sync word. */
pk_status pkr_read_lines(pk_roll *r, int strip, size_t first, size_t n, uint16_t *out);
/* Pass 1 of a strip (and every strip before it): the lo-res strip, the profile, the per-line kernel state and the framing. */
pk_status pkr_decode_strip(pk_roll *r, int strip);
/* The strip's DX result (re-feeds the packets on first use) and honours a manual pick. */
pk_status pkr_dx(pk_roll *r, int strip, pk_dx_strip *out);
pk_status pkr_dx_object(pk_roll *r, int strip, pk_dx **dx);

#endif
