/* DX / edge data (Task 8): TLB's register-0x90 parser, vote logic, end-of-strip analysis and strip hand-off, ported from TLB.dll.
 *
 * The state TLB keeps per strip is one object (CiDxAndApsHole, constructed at strip+0x78 by FUN_10013620). It is modelled here as
 * the raw word array it is, addressed by TLB's own byte offsets (H(0x44) is "hole+0x44"), because TLB's table code overlaps
 * fields (the 100-entry frame table runs into the perforation counters, FUN_10014a10 reads entry 100, FUN_100144b0 reads one
 * count before its array) and a byte-exact port has to share those overlaps. Every function below names the TLB address it
 * ports; docs/re/33-dx-parser.md has the evidence. The offsets and what each field is:
 *   +08 dual-edge flag (always 1: FUN_10004f00's caller passes the literal 1)      +0c height   +10 dpi_base   +14 ratio
 *   +18 aux (stored, never read here)  +1c frame pitch  +20 35 mm flag (0 = 24 mm APS)  +24 cartridge flag  +28 IR (four planes)
 *   +2c +30 +58 geometry derived by FUN_10013800  +34 film context  +38 film-found line (-1 = none)  +3c film-found offset
 *   +40 last valid frame-table index  +44 frame-table count  +48 good count  +4c +50 +54 pending edge lines  +5c pending code
 *   +60 tail-first flag  +64 DX enabled  +6c.. frame table, 100 entries of five words {code, line, flagA, flagB, unused}
 *   +838 pending perforation start  +83c perforation count  +840.. perforation list  +9d0 fat-bit count  +9d4.. fat-bit list
 *   +b64 expected half-frame spacing  +b68 +b6c anchor vote  +b70 product slots  +b80 specifier slots  +b90 counts  +ba0 winner
 *   +ba4 +ba8 +bb4 flags  +bb8 (3000) APS spacing  +bbc +bc0 APS type-2 id  +bc4 +bc8 APS type-1 id  +bec log flag  +bf0 serial
 * Hostile input: a bad length or record count is PK_E_PROTOCOL before any state changes; every table index TLB's own bounds
 * keep inside the object is also clamped by hp(), so no input can make this code read or write outside the object. */
#include "boards/dx_internal.h"
#include "boards/boards.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>

#define HOLE_BYTES (PKB_DX_HOLE_WORDS * 4u)

struct pk_dx {
    uint32_t h[PKB_DX_HOLE_WORDS];      /* the hole */
    uint32_t sink;                       /* target of an out-of-range access (never read back as data) */
    int fault;                           /* an access fell outside the object */
    /* board object (FUN_10009790's this): +0x5c rollover count, +0x60 last full line */
    uint32_t b_roll, b_last;
    uint32_t status;                     /* *param_2 of FUN_10009790: 0x40000000 entry, 0x80000000 exit, 0x10000000 bit 0x40, 0x20000000 bit 0x80 */
    uint32_t ctx74;                      /* scanner+0x74, cleared by FUN_10013900 and FUN_10015520 */
    uint32_t ctx_a8;                     /* scanner+0xa8, the film-found context */
    uint32_t scanw;                      /* strip+0x6ca8 */
    bool single_strip;
    bool analysed;
    bool saw_bit40;
    bool cal;                            /* board state 3 or 4 (calibration) instead of 5 (scanning) */
    bool cal_require;                    /* RequireDxSensorsDuringLightCalibration (DAT_10075554+0x1614) */
    bool cal_flag10;                     /* request flags (board+0x2c)+0x18 bit 0x10 */
    bool cal_abort;                      /* film sensed during calibration: TLB set the 0x1 bit in the request's word */
    pk_dx_speed_history own_hist;
    pk_dx_speed_history *hist;
    pkb_dx_event ev[PK_DX_MAX_RECORDS];
    size_t nev;
    int npkt;
    uint8_t *plog;                       /* the 30-byte packets fed so far, when pk_dx_log_packets is on (Task 13: the sidecar's dx_packets) */
    size_t plog_n, plog_cap;
    bool plog_on, plog_full;
    uint32_t type_count[16];             /* records seen per low-nibble type, 0..15 (not used by the parser; the scan reads their sum to know a strip has seen its first record, scan.c cur_sw) */
};

/* ---------------------------------------------------------------- bounds-clamped hole access */
static uint32_t *hp(pk_dx *d, uint32_t off) {
    uint32_t i = off >> 2;
    if (off & 3u || i >= PKB_DX_HOLE_WORDS) {
        d->fault = 1;
        d->sink = 0;
        return &d->sink;
    }
    return &d->h[i];
}
#define H(o) (*hp(d, (uint32_t)(o)))
#define HS(o) ((int32_t)*hp(d, (uint32_t)(o)))
/* frame-table entry i: code +0x6c, line +0x70, flagA +0x74, flagB +0x78 (offsets as TLB computes them: 0x6c + 0x14 * i) */
#define EOFF(i) ((uint32_t)(0x6c + 0x14 * (int32_t)(i)))

/* ---------------------------------------------------------------- FUN_10013620 + FUN_10013800: construct and initialise */
static void hole_construct(pk_dx *d) {
    memset(d->h, 0, HOLE_BYTES);
    d->h[0] = 0x1005b70cu;                       /* vtable pointer */
    d->h[1] = 0x1d;
    H(0x20) = 1; H(0x64) = 1;
    H(0x34) = H(0x38) = 0xffffffffu;
    H(0x4c) = H(0x50) = H(0x54) = 0xffffffffu;
    H(0x5c) = 0x80000000u;
    H(0x838) = 0xffffffffu;
    for (int i = 0; i < 4; i++) { H(0xb70 + 4 * i) = 0xffffffffu; H(0xb80 + 4 * i) = 0xffffffffu; }
    H(0xba8) = 2;
    H(0xbb8) = 0x28;
}

static void hole_init(pk_dx *d, const pk_dx_geometry *g) {
    uint32_t height = g->height, dpi = g->dpi_base, ratio = g->ratio;
    H(0x08) = 1;                                 /* FUN_10004f00 passes the literal 1 (RE 33 section 3) */
    H(0x1c) = g->frame_pitch;
    H(0x18) = g->aux18;
    H(0x20) = g->aps24 ? 0 : 1;
    H(0x10) = dpi;
    H(0x0c) = height;
    H(0x14) = ratio;
    H(0x58) = (height * 0x695fu) / dpi;
    H(0x24) = 0;
    H(0x28) = g->ir ? 1 : 0;                     /* (vfn+0x44 == 4): four planes */
    H(0x2c) = (height * 0x16a8u) / (dpi * ratio);
    H(0x30) = (height * 0x652cu) / (dpi * ratio);
    H(0xbec) = 0;
    H(0xbf0) = 0;
}

pk_status pk_dx_geometry_for(int dpi_base, bool ir, pk_dx_geometry *out) {
    if (!out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    out->dpi_base = 23700;
    out->ir = ir;
    out->single_strip = true;
    switch (dpi_base) {                          /* FUN_10011a60 */
    case 4:  out->height = 1000; out->ratio = 4; out->aux18 = 1500; out->frame_pitch = 1603; break;
    case 8:  out->height = 1500; out->ratio = 6; out->aux18 = 2250; out->frame_pitch = 2405; break;
    case 16: out->height = 2000; out->ratio = 8; out->aux18 = 3000; out->frame_pitch = 3206; break;
    default: return PK_E_UNSUPPORTED;
    }
    return PK_OK;
}

pk_status pk_dx_new_geometry(const pk_dx_geometry *g, pk_dx **out) {
    if (!out) return PK_E_ARG;
    *out = NULL;
    if (!g || !g->height || !g->dpi_base || !g->ratio) return PK_E_ARG;
    if ((uint64_t)g->dpi_base * g->ratio > 0xffffffffu || (uint64_t)g->height * 0x695fu > 0xffffffffu) return PK_E_ARG;
    /* the expected spacing (hole+0xb64) is the frame pitch, halved for 35 mm; TLB divides by it and by a third of it */
    if ((g->aps24 ? g->frame_pitch : g->frame_pitch >> 1) < 8) return PK_E_ARG;
    pk_dx *d = calloc(1, sizeof *d);
    if (!d) return PK_E_NOMEM;
    hole_construct(d);
    hole_init(d, g);
    d->ctx_a8 = g->film_context;
    d->ctx74 = 0xdeadbeefu;
    d->single_strip = g->single_strip;
    d->hist = &d->own_hist;
    *out = d;
    return PK_OK;
}

pk_status pk_dx_new(pk_dx **out) {
    pk_dx_geometry g;
    pk_status s = pk_dx_geometry_for(16, false, &g);
    if (s != PK_OK) { if (out) *out = NULL; return s; }
    return pk_dx_new_geometry(&g, out);
}

void pk_dx_free(pk_dx *d) {
    if (d) free(d->plog);
    free(d);
}

#define PK_DX_LOG_MAX ((size_t)8 << 20)      /* 8 MiB = about 280,000 packets */
void pk_dx_log_packets(pk_dx *d, bool on) { if (d) d->plog_on = on; }
const uint8_t *pk_dx_logged_packets(const pk_dx *d, size_t *n, bool *truncated) {
    if (n) *n = d ? d->plog_n / PK_DX_PACKET_LEN : 0;
    if (truncated) *truncated = d && d->plog_full;
    return d ? d->plog : NULL;
}
static void plog_add(pk_dx *d, const uint8_t *buf) {
    if (!d->plog_on || d->plog_full) return;
    if (d->plog_n + PK_DX_PACKET_LEN > PK_DX_LOG_MAX) { d->plog_full = true; return; }
    if (d->plog_n + PK_DX_PACKET_LEN > d->plog_cap) {
        size_t nc = d->plog_cap ? d->plog_cap * 2 : 4096;
        uint8_t *np = (uint8_t *)realloc(d->plog, nc);
        if (!np) { d->plog_full = true; return; }
        d->plog = np;
        d->plog_cap = nc;
    }
    memcpy(d->plog + d->plog_n, buf, PK_DX_PACKET_LEN);
    d->plog_n += PK_DX_PACKET_LEN;
}

pk_status pk_dx_set_calibration(pk_dx *d, const pk_dx_calibration *c) {
    if (!d) return PK_E_ARG;
    d->cal = c && c->calibrating;
    d->cal_require = c && c->require_sensors;
    d->cal_flag10 = c && c->request_flag10;
    return PK_OK;
}

bool pk_dx_calibration_abort(const pk_dx *d) { return d && d->cal_abort; }
uint32_t pk_dx_status_word(const pk_dx *d) { return d ? d->status : 0; }
bool pk_dx_tail_first(const pk_dx *d) { return d && d->h[0x60 >> 2] != 0; }

pk_status pk_dx_attach_speed_history(pk_dx *d, pk_dx_speed_history *h) {
    if (!d) return PK_E_ARG;
    d->hist = h ? h : &d->own_hist;
    return PK_OK;
}

/* ---------------------------------------------------------------- votes (shared by FUN_10013cd0 and FUN_10013f50) */
static void vote(pk_dx *d, uint32_t prod, uint32_t spec) {
    for (int i = 0; i < 4; i++) {
        uint32_t p = H(0xb70 + 4 * i), s = H(0xb80 + 4 * i);
        if (p == prod && s == spec) { H(0xb90 + 4 * i) = H(0xb90 + 4 * i) + 1; break; }
        if (p == 0xffffffffu && s == 0xffffffffu) {
            H(0xb70 + 4 * i) = prod;
            H(0xb80 + 4 * i) = spec;
            H(0xb90 + 4 * i) = 1;
            break;
        }
    }
    int32_t best = 0;                            /* highest count, first maximum wins */
    if (0 < HS(0xb90)) { H(0xba0) = 0; best = HS(0xb90); }
    if (best < HS(0xb94)) { H(0xba0) = 1; best = HS(0xb94); }
    if (best < HS(0xb98)) { H(0xba0) = 2; best = HS(0xb98); }
    if (best < HS(0xb9c)) H(0xba0) = 3;
}

/* ---------------------------------------------------------------- FUN_10013900 */
static void h_13900(pk_dx *d, uint32_t line, uint32_t p2, uint32_t *p3) {
    if (H(0x24) != 0) { H(0x34) = 0; H(0x38) = 0; return; }
    if (H(0x08) != 0 || p2 != 0) {
        *p3 = 0;
        if (H(0x28) != 0) line >>= 1;
        H(0x34) = p2;
        H(0x38) = line;
    }
}

/* ---------------------------------------------------------------- FUN_10013980 (type 1, APS) and FUN_10013af0 (type 2, APS) */
static uint64_t crc9(uint64_t v) {               /* division by x^3 + 1 (0x9), TLB's shift/xor loop; the remainder is 0 for a valid word */
    uint64_t poly = 0x0900000000000000ull, mask = 0x0800000000000000ull;
    do {
        if (mask & v) v ^= poly;
        poly >>= 1;
        mask >>= 1;
    } while ((poly & 1) == 0);
    if (mask & v) v ^= poly;
    return v;
}

static void h_13980(pk_dx *d, const uint8_t *p) {
    uint64_t v = ((((uint64_t)p[3] * 0x100 + p[2]) * 0x100 + p[1]) * 0x100) + p[0];
    uint64_t r = crc9(v);
    if (H(0xbc8) == 0) {
        H(0xbc4) = (((uint32_t)(p[3] & 0x7f) * 0x100 + p[2]) * 0x100 + p[1]) * 0x10 + (uint32_t)(p[0] >> 4);
        if (r == 0 && (p[0] & 8) == 0) H(0xbc8) = 1;
        if (H(0xbc8) == 0) H(0xbc4) = 0xffffffffu;
    }
}

static void h_13af0(pk_dx *d, uint8_t *p) {
    uint8_t b1 = p[0], b2 = p[3], b3 = p[2], b4 = p[4] & 0x1f;
    p[4] = b4;
    uint64_t v = ((((uint64_t)b4 * 0x100 + b2) * 0x100 + b3) * 0x100 + p[1]) * 0x100 + b1;
    uint32_t good = crc9(v) == 0 ? 1u : 0u;
    if (H(0xbc0) == 0) {
        H(0xbbc) = (uint32_t)(b1 >> 7) + ((((uint32_t)b4 * 0x100 + p[3]) * 0x100 + p[2]) * 0x100 + p[1]) * 2u;
        H(0xbc0) = good;
        uint8_t b = p[0];
        if ((b & 0x10) == 0) {
            if ((b & 0x20) == 0) { if (b & 0x40) H(3000) = 0xf; }
            else H(3000) = 0x19;
        } else H(3000) = 0x28;
    }
    if (H(0xbc0) == 0) H(0xbbc) = 0xffffffffu;
}

/* ---------------------------------------------------------------- FUN_10013cd0 (type 3, 21-bit code word) */
static void reset_pending(pk_dx *d) { H(0x50) = 0xffffffffu; H(0x54) = 0xffffffffu; H(0x4c) = 0xffffffffu; }

/* the shared tail of FUN_10013cd0 / FUN_10013f50 when the strip is read head first: pair the code with the edge seen before it */
static void pair_with_edge(pk_dx *d, uint32_t code, const uint8_t *p) {
    int32_t cnt;
    if (H(0x08) == 0) {
        uint32_t line = H(0x4c);
        cnt = HS(0x44);
        if (line == 0xffffffffu || 99 < cnt) { reset_pending(d); return; }
        H(EOFF(cnt) + 4) = line;
    } else {
        if (H(0x50) == 0xffffffffu || 99 < HS(0x44) || (p[0] & 1) == 0) {
            uint32_t line = H(0x54);
            cnt = HS(0x44);
            if (line == 0xffffffffu || 99 < cnt || (p[0] & 2) == 0) { reset_pending(d); return; }
            H(EOFF(cnt) + 4) = line;
        } else {
            cnt = HS(0x44);
            H(EOFF(cnt) + 4) = H(0x58) + H(0x50);
        }
    }
    H(EOFF(cnt)) = code;
    H(0x44) = (uint32_t)(HS(0x44) + 1);
    H(0x5c) = 0x80000000u;
    reset_pending(d);
}

static void h_13cd0(pk_dx *d, uint8_t *p, bool *accepted) {
    bool dual = H(0x08) != 0;
    int i1 = 1, i2 = 2;
    uint32_t l0 = 0;
    if (dual) { i1 = 2; i2 = 3; l0 = 1; }
    uint8_t b1 = p[i1];
    uint32_t prod = (uint32_t)(b1 >> 6) + (uint32_t)(p[i2] & 0x1f) * 4u;
    uint32_t spec = (uint32_t)(b1 >> 1) & 0xf;
    uint32_t frame = (uint32_t)(p[l0] >> 2) + (uint32_t)(b1 & 1) * 0x40u;
    if (0x79 < frame) frame -= 0x80;
    uint32_t ok = ~((uint32_t)(p[i1] >> 5)) & 1u;
    if (H(0x20) == 0) { if (H(0xba4) == 0) H(0xba4) = p[l0] & 2u; }
    else if (p[l0] & 2u) ok = 0;
    uint8_t b2 = p[i2];
    p[i2] = b2 & 0x1f;
    uint8_t par = 0, bit = 1;
    for (int k = 0; k < 8; k++) {
        if (p[l0] & bit) par++;
        if (p[i1] & bit) par++;
        if (b2 & 0x1f & bit) par ^= 1;
        bit = (uint8_t)(bit << 1);
    }
    if (ok == 0 || (par & 1)) { frame = 0x80000000u; *accepted = false; }
    else { vote(d, prod, spec); *accepted = true; }
    if (H(0x60) != 0) {
        H(0x5c) = frame;
        if (H(0x08) != 0) H(0x5c) = (p[0] & 1u) | (frame * 2u);
        reset_pending(d);
        return;
    }
    pair_with_edge(d, frame, p);
}

/* ---------------------------------------------------------------- FUN_10013f50 (type 4, 12-bit code word) */
static void h_13f50(pk_dx *d, uint8_t *p, bool *accepted) {
    bool dual = H(0x08) != 0;
    int i0 = dual ? 1 : 0, i1 = dual ? 2 : 1;
    uint8_t b0 = p[i0], b1 = p[i1];
    uint32_t spec = (uint32_t)(b0 >> 1) & 0xf;
    uint32_t prod = (uint32_t)(b0 >> 6) + (uint32_t)(b1 & 0x1f) * 4u;
    uint8_t par = 0, bit = 1;
    for (int k = 0; k < 8; k++) {
        if (bit & b0) par++;
        if (bit & b1) par ^= 1;
        bit = (uint8_t)(bit << 1);
    }
    *accepted = false;
    if ((b1 & 0x20) == 0 && !(par & 1)) { vote(d, prod, spec); *accepted = true; }
    if (H(0x60) != 0) {
        H(0x5c) = 0x80000000u;
        if (H(0x08) != 0) {
            H(0x5c) = 0;
            reset_pending(d);
            H(0x5c) = p[0] & 1u;
            return;
        }
        reset_pending(d);
        return;
    }
    /* head first: the same pairing as type 3, but the stored code is the invalid marker 0x80000000 */
    pair_with_edge(d, 0x80000000u, p);
}

/* ---------------------------------------------------------------- FUN_10014130 (type 5, edge) */
static void h_14130(pk_dx *d, uint32_t line, const uint8_t *p) {
    if (H(0x28) != 0) line >>= 1;
    if (H(0x60) != 0) {
        int32_t cnt = HS(0x44);
        if (cnt < 100) {
            if (H(0x08) == 0) {
                H(EOFF(cnt) + 4) = line;
            } else {
                uint8_t b = p[0];
                if ((b & 1u) != (H(0x5c) & 1u)) {
                    H(0x5c) = 0x80000000u;
                    H(0x50) = 0xffffffffu;
                    H(0x54) = 0xffffffffu;
                    return;
                }
                H(0x5c) = (uint32_t)((int32_t)H(0x5c) >> 1);
                H(EOFF(cnt) + 4) = line;
                if (b & 1u) H(EOFF(cnt) + 4) = H(EOFF(cnt) + 4) + H(0x58);
            }
            H(EOFF(cnt)) = H(0x5c);
            H(0x44) = (uint32_t)(HS(0x44) + 1);
        }
        H(0x5c) = 0x80000000u;
        reset_pending(d);
        return;
    }
    if (H(0x08) == 0) { H(0x4c) = line; return; }
    if (p[0] & 1u) { H(0x50) = line; H(0x54) = 0xffffffffu; return; }
    H(0x54) = line;
    H(0x50) = 0xffffffffu;
}

/* ---------------------------------------------------------------- FUN_10014220 (type 6, fat bit) */
static void h_14220(pk_dx *d, uint32_t line) {
    if (H(0x28) != 0) line >>= 1;
    if (HS(0x9d0) < 100) {
        H(0x9d4 + 4u * (uint32_t)HS(0x9d0)) = line / H(0x14);
        H(0x9d0) = (uint32_t)(HS(0x9d0) + 1);
    }
}

/* ---------------------------------------------------------------- FUN_10014260 (types 7 and 8, perforations) */
static void h_14260(pk_dx *d, int type, uint32_t line) {
    if (H(0x20) == 0 && HS(0x83c) < 100) {
        if (H(0x28) != 0) line >>= 1;
        if (type == 8) { H(0x838) = line; return; }
        uint32_t start = H(0x838);
        if (start != 0xffffffffu) {
            uint32_t div = H(0x10);
            uint32_t h = H(0x0c);
            if (h * 1000u / div + start <= line && line <= h * 0x9c4u / div + start) {
                uint32_t k = H(0x60) == 0 ? 600u : 0x4b0u;
                H(0x840 + 4u * (uint32_t)HS(0x83c)) = (((start + line) >> 1) + h * k / div) / H(0x14);
                H(0x83c) = (uint32_t)(HS(0x83c) + 1);
            }
            H(0x838) = 0xffffffffu;
        }
    }
}

/* ---------------------------------------------------------------- FUN_10014320 (status bits 0x40 / 0x80) */
static uint32_t h_14320(pk_dx *d, uint8_t st) {
    uint32_t f = 0;
    if (st & 0x40) f = 0x10000000u;
    if (st & 0x80) { f |= 0x20000000u; H(0x60) = 1; }
    return f;
}

/* ---------------------------------------------------------------- FUN_100148a0 */
static void dispatch(pk_dx *d, uint32_t line, uint32_t p2, uint32_t *p3, int type, uint8_t *rec1, bool *accepted) {
    switch (type) {
    case 1: h_13980(d, rec1); return;
    case 2: h_13af0(d, rec1); return;
    case 3: h_13cd0(d, rec1, accepted); return;
    case 4: h_13f50(d, rec1, accepted); return;
    case 5:
        if (H(0x08) == 0) {
            if (HS(0x38) == -1) {
                h_13900(d, 0x3fffffffu, p2, p3);
                if (H(0x24) != 0) H(0xbb4) = 1;
            }
        } else if (HS(0x38) == -1 && (rec1[0] & 2)) {
            h_13900(d, 0x3fffffffu, p2, p3);
            h_14130(d, line, rec1);
            return;
        }
        h_14130(d, line, rec1);
        return;
    case 6:
        if (HS(0x38) == -1) h_13900(d, 0x3fffffffu, p2, p3);
        h_14220(d, line);
        return;
    case 7:
        if (H(0x08) == 0) {
            if (HS(0x38) == -1) { h_13900(d, line, p2, p3); return; }
            h_14260(d, type, line);
            return;
        }
        if (HS(0x38) == -1 && (rec1[0] & 2)) { h_13900(d, line, p2, p3); return; }
        return;
    case 8:
        h_14260(d, type, line);
        return;
    default:
        return;
    }
}

/* ---------------------------------------------------------------- FUN_10009790: one register-0x90 packet */
pk_status pk_dx_feed_packet(pk_dx *d, const uint8_t *buf, size_t n) {
    if (!d || !buf) return PK_E_ARG;
    if (n != PK_DX_PACKET_LEN) return PK_E_PROTOCOL;
    if (buf[2] > PK_DX_MAX_RECORDS) return PK_E_PROTOCOL;       /* TLB would parse past byte 29; refuse before changing anything */
    if (d->analysed) return PK_E_BUSY;
    plog_add(d, buf);
    uint8_t loc[32];
    memcpy(loc, buf, 30);
    loc[30] = loc[31] = 0;
    d->nev = 0;
    d->npkt++;
    uint32_t cnt16 = ((uint32_t)loc[0] << 8) + loc[1];
    uint32_t roll = d->b_roll;
    if (cnt16 < (d->b_last & 0xffffu)) roll++;
    uint32_t full = cnt16 + roll * 0x10000u;
    uint8_t status = loc[3];
    uint32_t left = loc[2];
    uint32_t off = 3;
    while (left) {
        uint8_t b = loc[off];
        int type = b & 0xf;
        d->type_count[type]++;
        if (off == 3) {
            uint32_t s = d->status;
            s = (status & 0x20) ? (s | 0x40000000u) : (s & 0xbfffffffu);
            s = (status & 0x10) ? (s | 0x80000000u) : (s & 0x7fffffffu);
            d->status = s;
            if (d->cal) {
                /* states 3 and 4 (FUN_10009790 0x100098ea): nothing else of this packet runs, not even FUN_10014320, and
                 * the line-counter words are not stored. Film sensed while the calibration wants none ends the calibration. */
                if (!d->cal_flag10 && d->cal_require && (status & 0x30)) {
                    d->cal = false;
                    d->status |= 0x100u;
                    d->cal_abort = true;
                }
                return PK_OK;
            }
            d->status |= h_14320(d, (uint8_t)(status & 0xf0));
            if (status & 0x40) d->saw_bit40 = true;
        }
        uint32_t line = full;
        if (type != 0 && (type < 3 || 4 < type)) {
            line = (((uint32_t)loc[off + 2] + d->b_roll * 0x100u) * 0x100u) + loc[off + 3];
            if (line + 10000u < d->b_last) line += 0x10000u;
        }
        bool accepted = false;
        if (type >= 1 && type <= 8) {
            pkb_dx_event *e = &d->ev[d->nev++];
            e->pkt = d->npkt - 1;
            e->type = type;
            e->rollover = loc[off + 1];
            e->line = (int)line;
            e->w0 = e->w1 = 0;
            dispatch(d, line, d->ctx_a8, &d->ctx74, type, &loc[off + 1], &accepted);
            if (type == 3) {
                bool dual = H(0x08) != 0;
                const uint8_t *q = &loc[off + 1];
                e->w0 = (int)((uint32_t)q[dual ? 1 : 0] | ((uint32_t)q[dual ? 2 : 1] << 8) | ((uint32_t)(loc[off + (dual ? 4 : 3)] & 0x1f) << 16));
                e->w1 = accepted ? 1 : 0;
            } else if (type == 4) {
                bool dual = H(0x08) != 0;
                const uint8_t *q = &loc[off + 1];
                e->w0 = (int)((uint32_t)q[dual ? 1 : 0] | ((uint32_t)q[dual ? 2 : 1] << 8));
                e->w1 = accepted ? 1 : 0;
            }
        }
        left--;
        off += 5;
    }
    d->b_roll = roll;
    d->b_last = full;
    return PK_OK;
}

/* ---------------------------------------------------------------- FUN_10014470 (drop entry p) and FUN_10014350 (insert) */
static void remove_entry(pk_dx *d, int32_t p) {
    if (p < 0x62) {
        uint32_t o = EOFF(p);
        for (int32_t k = 0x62 - p; k != 0; k--, o += 0x14) {
            H(o) = H(o + 0x14); H(o + 4) = H(o + 0x18); H(o + 8) = H(o + 0x1c); H(o + 12) = H(o + 0x20);
        }
    }
    H(0x44) = (uint32_t)(HS(0x44) - 1);
}

static void insert_entries(pk_dx *d, int32_t *count, int32_t at, int32_t mode) {
    int32_t iv4 = *count + HS(0x44);
    if (iv4 < 0x65) H(0x44) = (uint32_t)iv4;
    else { *count = 100 - HS(0x44); H(0x44) = 100; }
    if (mode == 0) at++;
    iv4 = *count - 1 + at;
    int32_t iv6 = HS(0x44) - 1;
    if (iv4 < iv6) {
        uint32_t o = EOFF(iv6) + 4;               /* the line word of entry iv6 */
        do {
            int32_t src = iv6 - *count;
            iv6--;
            uint32_t s = EOFF(src);
            H(o - 4) = H(s);
            H(o) = H(s + 4);
            H(o + 4) = H(s + 8);
            H(o + 8) = H(s + 12);
            o -= 0x14;
        } while (iv4 < iv6);
    }
    if (at <= iv4) {
        uint32_t o = EOFF(at) + 8;                /* flagA of entry `at` */
        for (int32_t k = iv4 - at + 1; k != 0; k--, o += 0x14) {
            H(o - 8) = 0x80000000u;
            H(o) = 1;
            H(o + 4) = 0;
        }
    }
    if (mode == 0) {
        if (at <= iv4) {
            uint32_t o = EOFF(at) + 4;
            for (int32_t k = iv4 - at + 1; k != 0; k--, o += 0x14) H(o) = H(o - 0x14) + H(0xb64);
        }
    } else if (at <= iv4) {
        uint32_t o = EOFF(iv4) + 4;
        for (int32_t k = iv4 - at + 1; k != 0; k--, o -= 0x14) {
            if (H(o + 0x14) < H(0xb64)) H(o) = 0;
            else H(o) = H(o + 0x14) - H(0xb64);
        }
    }
}

/* ---------------------------------------------------------------- FUN_10014a10 (gap fill) */
static bool gap_fill(pk_dx *d) {
    int32_t n0 = HS(0x44);
    if (n0 < 1) return false;
    H(0xb64) = H(0x20) == 0 ? H(0x1c) : H(0x1c) >> 1;
    uint32_t exp = H(0xb64);
    uint32_t hi = exp + (exp >> 3), lo = exp - (exp >> 3);
    uint32_t cost[100];
    for (int k = 0; k < 100; k++) cost[k] = 0xffffffffu;
    uint32_t big = H(0x28) != 0 ? 0x8000u : 0x10000u;
    int32_t i = 0;
    if (0 < n0 - 1) {
        do {
            int32_t saved = i;
            uint32_t e = H(0xb64);
            uint32_t li = H(EOFF(i) + 4), l1 = H(EOFF(i) + 0x18), l2 = H(EOFF(i) + 0x2c);   /* lines of entries i, i+1, i+2 */
            uint32_t gap = l1 - li;
            uint32_t q = gap / e;
            bool drop = false;
            if ((int32_t)q < 7) {
                uint32_t k1 = q + 1;
                uint32_t a = (k1 * e - gap) / k1;
                uint32_t b = (gap - e * q) / k1;
                cost[i] = b < a ? b : a;
            } else if (li < l1) {
                if (big < gap) {
                    uint32_t g2 = gap - big;
                    if (g2 < lo || hi < g2 || HS(0x44) - 2 <= i) drop = true;
                    else {
                        uint32_t u = (l2 - l1) + big;
                        if (u < lo || hi < u) drop = true;
                    }
                    if (!drop) H(EOFF(i) + 0x18) = l1 - big;
                }
            } else if (i == 0) {
                remove_entry(d, 0);
                i = -1;
            } else drop = true;
            if (drop) {
                remove_entry(d, i + 1);
                i = saved - 1;
            }
            i++;
        } while (i < HS(0x44) - 1);
    }
    int32_t lim = HS(0x44) - 1;
    int32_t best = 0;
    uint32_t bv = 0xffffffffu;
    if (0 < lim) {
        int32_t k = 0;
        do {
            if (cost[k] < bv) { bv = cost[k]; best = k; }
            k++;
        } while (k < HS(0x44) - 1);
    }
    int32_t k = best;
    if (best < lim) {
        do {
            uint32_t gap = H(EOFF(k) + 0x18) - H(EOFF(k) + 4);
            if (gap < lo) {
                int32_t from = k + 1;
                if (from < 0x62) {
                    uint32_t o = EOFF(from);
                    for (int32_t c = 0x62 - from; c != 0; c--, o += 0x14) {
                        H(o) = H(o + 0x14); H(o + 4) = H(o + 0x18); H(o + 8) = H(o + 0x1c); H(o + 12) = H(o + 0x20);
                    }
                }
                H(0x44) = (uint32_t)(HS(0x44) - 1);
            } else if (hi < gap) {
                uint32_t e = H(0xb64);
                int32_t cnt = (int32_t)(gap / e);
                if (gap - e * (uint32_t)cnt <= e >> 1) cnt--;
                insert_entries(d, &cnt, k, 0);
                k = k + 1 + cnt;
            } else k++;
        } while (k < HS(0x44) - 1);
    }
    if (0 < best) {
        int32_t b = best;
        uint32_t lp = EOFF(b) + 4;               /* line of entry b */
        do {
            uint32_t gap = H(lp) - H(lp - 0x14);
            if (gap < lo) {
                int32_t from = b - 1;
                if (from < 0x62) {
                    uint32_t o = EOFF(from);
                    for (int32_t c = 0x62 - from; c != 0; c--, o += 0x14) {
                        H(o) = H(o + 0x14); H(o + 4) = H(o + 0x18); H(o + 8) = H(o + 0x1c); H(o + 12) = H(o + 0x20);
                    }
                }
                H(0x44) = (uint32_t)(HS(0x44) - 1);
            } else if (hi < gap) {
                uint32_t e = H(0xb64);
                int32_t cnt = (int32_t)(gap / e);
                if (gap - e * (uint32_t)cnt <= e >> 1) cnt--;
                insert_entries(d, &cnt, b, 1);
            }
            lp -= 0x14;
            b--;
        } while (0 < b);
    }
    int32_t first = 0;
    int32_t pos = 0;
    uint32_t found = 0;
    for (;;) {
        uint32_t fa = H(EOFF(pos) + 8), fb = H(EOFF(pos) + 12);
        bool stop = false;
        if (fa == 0 && fb == 0) {
            found = (uint32_t)pos;
            if (H(0x3c) <= H(EOFF(pos) + 4)) stop = true;
        }
        if (stop) break;
        pos++;
        found = (uint32_t)first;
        if (!(pos < 0x65)) break;
    }
    first = (int32_t)found;
    uint32_t fl = H(EOFF(first) + 4);
    int32_t q2 = (int32_t)((fl - H(0x3c)) / H(0xb64));
    int32_t ins;
    if (q2 < 5) ins = 5;
    else ins = q2;                                /* (more than 10 is only logged) */
    insert_entries(d, &ins, 0, 1);
    int32_t hundred = 100;
    insert_entries(d, &hundred, HS(0x44) - 1, 0);
    H(0x44) = (uint32_t)n0;
    for (int32_t c = 0; c < 100; c++)
        if (H(EOFF(c) + 8) == 0 && H(EOFF(c) + 12) == 0) H(0x48) = H(0x48) + 1;
    return true;
}

/* ---------------------------------------------------------------- FUN_100144b0 (anchor vote) */
static int32_t anchor(pk_dx *d) {
    int32_t a[201];                               /* a[0..99] valid flags, a[100..200] counts: TLB's two stack arrays are contiguous */
    int32_t *ok = a, *cnt = a + 100;
    for (int k = 0; k < 100; k++) ok[k] = 1;
    for (int k = 0; k < 101; k++) cnt[k] = 0;
    uint32_t dir = H(0x60);
    int32_t first = -1, i;
    uint32_t step;                                /* code arithmetic is unsigned: the invalid marker 0x80000000 must wrap like TLB's registers */
    int aps = H(0x20) == 0;
    int32_t iv7 = first;
    if (dir == 0) { step = aps ? 2u : 1u; i = 0; }
    else { step = aps ? 0xfffffffeu : 0xffffffffu; i = 99; }
    int inc = dir == 0 ? 1 : -1;
    do {
        int32_t code = HS(EOFF(i));
        bool bad = aps ? (code < 2 || (code & 1) != 0 || H(EOFF(i) + 4) == 0xffffffffu)
                       : (code < -6 || H(EOFF(i) + 4) == 0xffffffffu);
        if (bad) { ok[i] = 0; iv7 = first; }
        else {
            iv7 = i;
            if (-1 < first) { H(0x40) = (uint32_t)i; iv7 = first; }
        }
        i += inc;
        first = iv7;
    } while (dir == 0 ? i < 100 : -1 < i);
    if (iv7 < 0) {
        H(0x40) = 0xfffffffeu;
    } else {
        int32_t cur = HS(0x40);
        if (cur == 0) { H(0xb68) = (uint32_t)iv7; H(0xb6c) = (uint32_t)iv7; H(0x40) = (uint32_t)iv7; return iv7; }
        if (dir != 0) { H(0x40) = (uint32_t)iv7; iv7 = cur; }
    }
    int32_t hi = HS(0x40);
    if (iv7 <= hi) {
        int32_t i6 = iv7;
        do {
            uint32_t code = H(EOFF(i6));
            uint32_t c5 = code;
            uint32_t po = EOFF(i6);
            for (int32_t i2 = i6; i2 < hi; i2++) {
                if (ok[i2] != 0 && c5 == H(po)) cnt[i6]++;
                c5 += step;
                po += 0x14;
            }
            uint32_t c1 = code - step;
            po = EOFF(i6);
            int32_t i5 = i6;
            while (i5 = i5 - 1, iv7 <= i5) {
                po -= 0x14;
                if (ok[i5] != 0 && c1 == H(po)) cnt[i6]++;
                c1 -= step;
            }
            i6++;
        } while (i6 <= hi);
    }
    int32_t best = 0;
    int32_t mid = (hi - iv7) / 2 + iv7;
    H(0xb68) = 0; H(0xb6c) = 0;
    int32_t i6 = mid;
    if (iv7 <= mid) {
        do {
            int32_t c = cnt[i6];
            if (best < c) { H(0xb6c) = (uint32_t)i6; best = c; }
            i6--;
        } while (iv7 <= i6);
        H(0xb68) = (uint32_t)best;
    }
    if (mid < hi) {
        do {
            if (HS(0xb68) < cnt[mid]) { H(0xb68) = (uint32_t)cnt[mid]; H(0xb6c) = (uint32_t)mid; }
            mid++;
        } while (mid < HS(0x40));
    }
    int32_t c44 = HS(0x44);
    int32_t need = (c44 + ((c44 >> 31) & 7)) >> 3;
    need = (need < 3 || need == 2) ? 1 : 2;
    if (need <= HS(0xb68)) return HS(0xb6c);
    return -1;
}

/* ---------------------------------------------------------------- FUN_100147a0 / FUN_10014820 (extrapolate up and down from the anchor) */
static void extrapolate_up(pk_dx *d, int32_t p) {
    if (p < 99) {
        uint32_t o = EOFF(p);
        for (int32_t k = 99 - p; k != 0; k--, o += 0x14) {
            if (H(o + 0x18) == 0xffffffffu) H(o + 0x18) = H(o + 4) + H(0xb64);
            uint32_t want;
            if (H(0x20) == 0) want = H(o) + (H(0x60) == 0 ? 2u : 0xfffffffeu);
            else want = H(o) + (H(0x60) == 0 ? 1u : 0xffffffffu);
            if (H(o + 0x14) != want) { H(o + 0x14) = want; H(o + 0x20) = 1; }
        }
    }
}

static void extrapolate_down(pk_dx *d, int32_t p) {
    if (0 < p) {
        uint32_t o = EOFF(p);
        do {
            if (H(o - 0x10) == 0xffffffffu) {
                if (H(o + 4) < H(0xb64)) H(o - 0x10) = 0;
                else H(o - 0x10) = H(o + 4) - H(0xb64);
            }
            uint32_t want;
            if (H(0x20) == 0) want = H(o) + (H(0x60) == 0 ? 0xfffffffeu : 2u);
            else want = H(o) + (H(0x60) == 0 ? 0xffffffffu : 1u);
            if (H(o - 0x14) != want) { H(o - 0x14) = want; H(o - 8) = 1; }
            o -= 0x14;
            p--;
        } while (0 < p);
    }
}

/* ---------------------------------------------------------------- FUN_10031420 / FUN_100317a0 / FUN_100317d0 (speed history) */
static bool hist_mean(const pk_dx_speed_history *hs, double *mean) {
    const int32_t *s = (const int32_t *)hs->slot;
    int32_t i1 = s[4];
    if (i1 == 0) { *mean = 0.0; return false; }
    int32_t i2 = s[0], i3 = s[1], i4 = i2;
    if (i2 < i3) i4 = i3;
    uint32_t u5 = (uint32_t)(i2 < i3);
    int32_t i6 = i2;
    if (i3 < i2) i6 = i3;
    uint32_t u7 = (uint32_t)(i3 < i2);
    i2 = s[2];
    if (i4 < i2) { u5 = 2; i4 = i2; }
    if (i2 < i6) { u7 = 2; i6 = i2; }
    i2 = s[3];
    if (i4 < i2) { u5 = 3; i4 = i2; }
    if (i2 < i6) { u7 = 3; i6 = i2; }
    if (i4 < i1) u5 = 4;
    if (i1 < i6) u7 = 4;
    int32_t sum = 0;
    if (u5 != 0 && u7 != 0) sum = s[0];
    if (u5 != 1 && u7 != 1) sum += s[1];
    if (u5 != 2 && u7 != 2) sum += s[2];
    if (u5 != 3 && u7 != 3) sum += s[3];
    if (u5 != 4 && u7 != 4) sum += s[4];
    if (u5 == u7) sum -= s[u7];
    *mean = (double)sum * 0.3333333333333333;
    return true;
}

static void speed_flags(const pk_dx_speed_history *hs, uint32_t expected, uint32_t *flags) {
    double m;
    if (!hist_mean(hs, &m)) return;
    volatile double e = (double)expected;         /* fild of an unsigned 32-bit value */
    volatile double hi1 = e * 1.005;
    if (!(m <= hi1)) {
        *flags |= 0x10;
        volatile double hi2 = e * 1.01;
        if (!(m <= hi2)) *flags |= 0x20;
    } else {
        volatile double lo1 = e * 0.995;
        if (m < lo1) {
            *flags |= 0x40;
            volatile double lo2 = e * 0.99;
            if (m < lo2) *flags |= 0x80;
        }
    }
    /* TLB also derives a clamped speed correction (900..1100 per mille, this+0xc of the history object) here; nothing in the DX
     * hand-off reads it, so it is not kept. */
}

/* ---------------------------------------------------------------- FUN_100150e0 */
static bool analyse_frames(pk_dx *d) {
    if (!gap_fill(d)) return false;
    H(0x40) = 0;
    int32_t anc = anchor(d);
    if (anc == -1) return false;
    extrapolate_up(d, anc);
    extrapolate_down(d, anc);
    if (!d->single_strip) return true;
    int32_t top = HS(0x40);
    int32_t iv1 = 0, iv8 = 0;
    if (top < 0) return true;
    uint32_t o = EOFF(0) + 12;                    /* flagB of entry 0; flagA is o - 4 */
    while (H(o - 4) != 0 || H(o) != 0 || (++iv1 < 3)) {
        iv8++;
        o += 0x14;
        if (HS(0x40) < iv8) return true;
    }
    if (iv8 < 0) return true;
    iv1 = 0;
    if (top <= iv8) return true;
    uint32_t po = EOFF(top) + 12;
    while (H(po - 4) != 0 || H(po) != 0 ||
           (++iv1 < 3 || (H(0x20) != 0 && (((H(EOFF(iv8)) ^ H(po - 12)) & 1) == 0)))) {
        top--;
        po -= 0x14;
        if (top <= iv8) return true;
    }
    if (top < 0) return true;
    uint32_t span = (uint32_t)(top - iv8);
    uint32_t avg = (H(EOFF(top) + 4) - H(EOFF(iv8) + 4)) / span;
    uint32_t flags = 0, reads = 1;
    int32_t j = iv8 + 1;
    if (j < top) {
        uint32_t q = EOFF(j) + 12;
        for (int32_t k = top - j; k != 0; k--, q += 0x14)
            if (H(q - 4) == 0 && H(q) == 0) reads++;
    }
    if (H(0x20) == 0 ? reads >= 0x10 : reads >= 0x22) {
        /* FUN_100317a0: newest first */
        uint32_t *s = d->hist->slot;
        for (int k = 4; k > 0; k--) s[k] = s[k - 1];
        s[0] = avg;
        speed_flags(d->hist, H(0xb64), &flags);
    }
    d->scanw |= flags;
    return true;
}

/* ---------------------------------------------------------------- FUN_10015520, up to and including its call of FUN_100150e0 */
void pkb_dx_analyse(pk_dx *d) {
    if (d->analysed) return;
    d->analysed = true;
    d->ctx74 = 0;
    if (H(0xbb4) != 0 || (H(0x24) == 0 && H(0x38) == 0xffffffffu)) {
        H(0xbb4) = 1;
        d->scanw = 1;                              /* an assignment, not an OR (0x10015d0b) */
        return;
    }
    if (H(0x24) != 0) {
        H(0x3c) = (H(0x0c) * 16000u) / H(0x10);
    } else {
        uint32_t film = H(0x38);
        uint32_t h = H(0x0c);
        uint32_t div = H(0x10);
        H(0x3c) = film;
        uint32_t k = H(0x08) == 0 ? 0x3d9au : 0x2979u;
        uint32_t u8 = (h * k) / div;
        uint32_t u4 = (h * 0x4b00u) / div;
        if (H(0x34) + u4 < film) {
            H(0x3c) = H(0x3c) + ((film - H(0x34)) - u4);
        } else {
            u4 = H(0x3c) + H(0x34) + u4;
            H(0x3c) = u4;
            if (film < u4) H(0x3c) = u4 - film;
            else H(0x3c) = 0;
        }
        uint32_t i11;
        uint32_t u7;
        if (H(0x20) == 0) {
            if (H(0x60) == 0) {
                u7 = (h * 0x8cau) / div;
                if (u7 < H(0x3c)) H(0x3c) = H(0x3c) - u7; else H(0x3c) = 0;
                u7 = h * 0x4e2u;
            } else {
                u7 = (h * 3000u) / div;
                if (u7 < H(0x3c)) H(0x3c) = H(0x3c) - u7; else H(0x3c) = 0;
                u7 = h * 0x5dcu;
            }
            i11 = u8 + u7 / div;
        } else {
            u7 = (h * 2000u) / div;
            u8 = u8 + u7;
            if (H(0x60) == 0) {
                H(0x3c) = H(0x3c) + u7;
                u7 = h * 0xd61u;
                i11 = u8 + u7 / div;
            } else {
                u7 = (h * 0x1d4cu) / div;
                if (u7 < H(0x3c)) H(0x3c) = H(0x3c) - u7; else H(0x3c) = 0;
                u7 = (h * 6000u) / div;
                i11 = u7 < u8 ? u8 - u7 : 0;
            }
        }
        uint32_t w = (h * 2000u) / div;
        uint32_t u7b = i11 + H(0x34);
        uint32_t lo = u7b - w;
        uint32_t hi = w + u7b;
        if (H(0x3c) < lo || hi < H(0x3c)) H(0x3c) = u7b;
    }
    if (!analyse_frames(d)) H(0xbb4) = 1;
}

/* ---------------------------------------------------------------- queries */
void pkb_dx_events(const pk_dx *d, const pkb_dx_event **ev, size_t *n) {
    *ev = d->ev;
    *n = d->nev;
}

void pkb_dx_votes(const pk_dx *d, int votes[4][3], int *winner) {
    for (int i = 0; i < 4; i++) {
        votes[i][0] = (int)d->h[(0xb70 >> 2) + i];
        votes[i][1] = (int)d->h[(0xb80 >> 2) + i];
        votes[i][2] = (int)d->h[(0xb90 >> 2) + i];
    }
    *winner = (int)d->h[0xba0 >> 2];
}

void pkb_dx_state_get(const pk_dx *d, pkb_dx_state *out) {
    out->hole = d->h;
    out->board_roll = d->b_roll;
    out->board_last = d->b_last;
    out->status = d->status;
    out->scanw = d->scanw;
    out->fault = d->fault;
}

int pk_dx_frame_half_frames(pk_dx *d, int frame_index, bool *read_not_extrapolated) {
    if (read_not_extrapolated) *read_not_extrapolated = false;
    if (!d) return INT_MIN;
    pkb_dx_analyse(d);
    if (frame_index < 0 || frame_index >= 100) return INT_MIN;
    uint32_t o = EOFF(frame_index);
    if (read_not_extrapolated) *read_not_extrapolated = H(o + 8) == 0 && H(o + 12) == 0;
    return (int)H(o);
}

pk_status pk_dx_finish_strip(pk_dx *d, bool publish_ran, pk_dx_strip *out) {
    if (!d || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    int winner = (int)H(0xba0);
    if (winner < 0 || winner > 3) return PK_E_PROTOCOL;
    if (publish_ran) pkb_dx_analyse(d);
    pkb_dx_votes(d, out->votes, &winner);
    out->good_count = (int)H(0x48);
    out->status_bit40_seen = d->saw_bit40;
    out->tail_first = H(0x60) != 0;
    out->scanw = d->scanw;
    if (!publish_ran) {                            /* the constructor's 0/0: FUN_10005820 never ran */
        out->product = 0;
        out->specifier = 0;
        strcpy(out->dx_source, "none");
        return PK_OK;
    }
    out->product = out->votes[winner][0];
    out->specifier = out->votes[winner][1];
    if (H(0xbb4) != 0) out->scanw |= 1u;           /* FUN_100057f0: strip+0xc2c is hole+0xbb4 */
    if (out->product < 1) out->scanw |= 2u;
    strcpy(out->dx_source, out->product != PK_DX_NONE_CODE ? "dx" : "none");
    return PK_OK;
}

void pk_dx_record_counts(const pk_dx *d, uint32_t out[16]) {
    if (!out) return;
    if (d) memcpy(out, d->type_count, sizeof d->type_count); else memset(out, 0, 16 * sizeof out[0]);
}

/* ---------------------------------------------------------------- the board commands */
static uint8_t dx_addr(pk_boards *b) {      /* 0 = no DX role: the callers refuse */
    const pk_model *m = pk_boards_model(b);
    return m ? m->roles.dx : 0;
}

pk_status pk_dx_start(pk_boards *b, unsigned speed16, unsigned format) {
    if (!b) return PK_E_ARG;
    if (speed16 > 0xffffu || format > 0xffu) return PK_E_ARG;
    if (!dx_addr(b)) return PK_E_ARG;
    uint8_t d[3] = { (uint8_t)(speed16 & 0xff), (uint8_t)(speed16 >> 8), (uint8_t)format };
    return pk_link_write(pk_boards_link(b), dx_addr(b), 0x91, d, 3);
}

pk_status pk_dx_stop(pk_boards *b) {
    if (!b || !dx_addr(b)) return PK_E_ARG;
    return pk_link_command(pk_boards_link(b), dx_addr(b), 0x92);
}

/* Reads register 0x90 (FUN_10009790) and feeds the packet. */
static pk_status dx_read_packet(pk_boards *b, pk_dx *d, uint8_t *status_nibble) {
    uint8_t buf[PK_DX_PACKET_LEN];
    pk_status s = pk_link_read(pk_boards_link(b), dx_addr(b), 0x90, PK_DX_PACKET_LEN, buf);
    if (s != PK_OK) return s;
    s = pk_dx_feed_packet(d, buf, sizeof buf);
    if (s != PK_OK) return s;
    *status_nibble = buf[2] ? (uint8_t)(buf[3] & 0xf0) : 0;
    if (buf[2]) { pthread_mutex_lock(&b->nib_mu); b->dx_nibble = *status_nibble; b->dx_rec_seq++; pthread_mutex_unlock(&b->nib_mu); }       /* keeps pk_film_sense / eject current */
    return PK_OK;
}

pk_status pk_dx_read_packet(pk_boards *b, pk_dx *d, uint8_t *status_nibble) {
    if (!b || !d || !status_nibble || !dx_addr(b)) return PK_E_ARG;
    *status_nibble = 0;
    return dx_read_packet(b, d, status_nibble);
}

pk_status pk_dx_poll(pk_boards *b, pk_dx *d, uint8_t *status_nibble) {
    if (!b || !d || !status_nibble || !dx_addr(b)) return PK_E_ARG;
    *status_nibble = 0;
    uint32_t st = 0;
    pk_status s = pkb_irq_take(b, 0xA4u, &st);
    if (s != PK_OK) return s;
    if ((st & 0xA4u) == 0) return PK_OK;
    return dx_read_packet(b, d, status_nibble);
}

/* TLB FUN_1000BDD0 (0x1000bf7b..bfa1), scan flag +0xe0 == 0, which is the whole strip of a real scan: register 0x02 is read and, when its
 * status byte flags an event (bit 7), acknowledged with 0x06 and register 0x90 is read whatever the value's bits are. */
pk_status pk_dx_poll_event(pk_boards *b, pk_dx *d, uint8_t *status_nibble, bool *event) {
    if (!b || !d || !status_nibble || !dx_addr(b)) return PK_E_ARG;
    *status_nibble = 0;
    if (event) *event = false;
    uint32_t taken = 0;
    bool ev = false;
    pk_status s = pkb_irq_take_ex(b, 0xA4u, &taken, NULL, &ev);
    if (s != PK_OK) return s;
    if (event) *event = ev;
    if (!ev) return PK_OK;
    return dx_read_packet(b, d, status_nibble);
}

/* The single end-of-strip drain read of FUN_1000BDD0 (flag +0xe0 == 1, 0x1000bf7b): register 0x02 is read (and acknowledged when it is an event)
 * and register 0x90 is read when the VALUE has (value & 0xA4) != 0, event bit or not. */
pk_status pk_dx_drain(pk_boards *b, pk_dx *d, uint8_t *status_nibble) {
    if (!b || !d || !status_nibble || !dx_addr(b)) return PK_E_ARG;
    *status_nibble = 0;
    uint32_t taken = 0;
    uint8_t v = 0;
    pk_status s = pkb_irq_take_ex(b, 0xA4u, &taken, &v, NULL);
    if (s != PK_OK) return s;
    if ((v & 0xA4u) == 0) return PK_OK;
    return dx_read_packet(b, d, status_nibble);
}

/* FN_bDrvDxGetHardware 0x1000a830: light register 0x93, 4 bytes = raw AN0..AN3 (nl050A 0x3d6c). Read-only. */
pk_status pk_dx_read_levels(pk_boards *b, uint8_t out[4]) {
    if (!b || !out || !dx_addr(b)) return PK_E_ARG;
    /* HW-1 run 4: 27 of 930 replies carried status 0x29 and a body (84 93 08 02) that is not sensor data; the real replies carry status 0x08
     * (0x88 with the event flag). Anything else is PK_E_PROTOCOL and out is left unchanged. */
    uint8_t v[4], st = 0;
    pk_status s = pk_link_read_status(pk_boards_link(b), dx_addr(b), 0x93, 4, v, &st);
    if (s != PK_OK) return s;
    if ((st & 0x7Fu) != 0x08u) return PK_E_PROTOCOL;
    memcpy(out, v, 4);
    return PK_OK;
}
