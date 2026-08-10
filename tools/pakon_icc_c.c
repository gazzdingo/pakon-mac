/*
 * pakon_icc_c.c — ICC v2 mft1/mft2 CLUT parser + trilinear evaluator (pure C).
 *
 * Cite: docs/58-colour-pipeline.md §6.1 ("ICC mft2 evaluation, exactly")
 * Cite: docs/58-colour-pipeline.md §6 table row 9: Rpd2Pcs_HR200_QS_v5s10.pf
 *       A2B0 mft2, 31³ grid, n_in=4096, n_out=512, 16-bit
 *       input clips RPD above code 3000.
 * Cite: docs/58-colour-pipeline.md §6 table row 10: Srgb_v2.pf
 *       B2A0 mft2, 25³ grid, n_in=256, n_out=4096, 16-bit
 *       output clips at 65295. The A2B0 tag in Srgb_v2.pf is mft1 (8-bit),
 *       but the render path uses B2A0 (docs/58 §10).
 *
 * Evaluation order (docs/58 §6.1):
 *   1. Normalise input → 1-D input table (linear interp, n entries)
 *   2. Trilinear interp over CLUT at q_c = v_c * (g-1)
 *   3. 1-D output table (linear interp, m entries)
 *
 * CLUT node address: clut[ (((c0*g + c1)*g + c2) * o) + k ]
 * Channel 0 slowest (outermost), last channel fastest.
 *
 * The matrix in mft2 is identity for all profiles here (docs/58 §6.1), skip it.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#define ICC_MFT2_TAG  0x6D667432  /* 'mft2' big-endian */
#define ICC_MFT1_TAG  0x6D667431  /* 'mft1' big-endian */
#define ICC_A2B0_TAG  0x41324230  /* 'A2B0' */
#define ICC_B2A0_TAG  0x42324130  /* 'B2A0' */
#define MAX_CHANNELS  3

typedef struct {
    int     n_in;       /* input channels */
    int     n_out;      /* output channels */
    int     grid;       /* CLUT grid size per axis */
    int     n_table_in; /* entries per input 1-D table */
    int     n_table_out;/* entries per output 1-D table */
    uint16_t *table_in; /* [n_in * n_table_in] big-endian already swapped */
    uint16_t *clut;     /* [grid^n_in * n_out] */
    uint16_t *table_out;/* [n_out * n_table_out] */
} IccMft2;

static uint16_t be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | p[1]);
}

static uint32_t be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16)
         | ((uint32_t)p[2] << 8)  |  (uint32_t)p[3];
}

/*
 * Find a named tag body in ICC profile bytes.
 * sig_want: ICC_A2B0_TAG or ICC_B2A0_TAG
 * Returns pointer to tag data and sets *len. Returns NULL if not found.
 */
static const uint8_t *icc_find_tag(const uint8_t *data, size_t size,
                                    uint32_t sig_want, size_t *len) {
    if (size < 132) return NULL;
    uint32_t tag_count = be32(data + 128);
    const uint8_t *dir = data + 132;
    for (uint32_t i = 0; i < tag_count && (size_t)(dir - data + 12) <= size; i++, dir += 12) {
        uint32_t sig    = be32(dir + 0);
        uint32_t offset = be32(dir + 4);
        uint32_t taglen = be32(dir + 8);
        if (sig == sig_want && offset + taglen <= size) {
            *len = taglen;
            return data + offset;
        }
    }
    return NULL;
}

/*
 * Parse an mft2 (lut16Type) tag body.
 * Cite: docs/58-colour-pipeline.md §6.1 mft2 layout.
 *
 * mft2 layout (offsets from tag body start):
 *   0:  'mft2'  4 bytes
 *   4:  reserved 4 bytes
 *   8:  n_in    uint8
 *   9:  n_out   uint8
 *  10:  grid    uint8
 *  11:  reserved
 *  12: 3x3 s15Fixed16 matrix (36 bytes) — identity for all profiles here, skip
 *  48: n_table_in  uint16 BE
 *  50: n_table_out uint16 BE
 *  52: input tables:  n_in * n_table_in * uint16 BE
 *      CLUT:          grid^n_in * n_out * uint16 BE
 *      output tables: n_out * n_table_out * uint16 BE
 *
 * mft1 (lut8Type) layout — used by Srgb_v2.pf A2B0:
 *   0:  'mft1'  4 bytes
 *   4:  reserved 4 bytes
 *   8:  n_in    uint8
 *   9:  n_out   uint8
 *  10:  grid    uint8
 *  11:  reserved
 *  12: 3x3 s15Fixed16 matrix (36 bytes)
 *  48: input tables:  n_in * 256 * uint8
 *      CLUT:          grid^n_in * n_out * uint8
 *      output tables: n_out * 256 * uint8
 * We convert mft1 uint8 values → uint16 by scaling * 257 (0xFF→0xFFFF).
 */
int icc_mft2_parse(const uint8_t *body, size_t body_len, IccMft2 *out) {
    if (body_len < 48) return -1;
    uint32_t type_sig = be32(body);
    int is_mft1 = (type_sig == ICC_MFT1_TAG);
    int is_mft2 = (type_sig == ICC_MFT2_TAG);
    if (!is_mft1 && !is_mft2) return -2;

    memset(out, 0, sizeof(*out));
    out->n_in  = body[8];
    out->n_out = body[9];
    out->grid  = body[10];

    if (is_mft2) {
        if (body_len < 52) return -1;
        out->n_table_in  = (int)be16(body + 48);
        out->n_table_out = (int)be16(body + 50);
    } else { /* mft1: fixed 256-entry tables */
        out->n_table_in  = 256;
        out->n_table_out = 256;
    }

    if (out->n_in < 1 || out->n_in > MAX_CHANNELS) return -3;
    if (out->n_out < 1 || out->n_out > MAX_CHANNELS) return -4;
    if (out->grid < 2) return -5;

    /* Compute CLUT size = grid^n_in */
    size_t clut_nodes = 1;
    for (int i = 0; i < out->n_in; i++) clut_nodes *= (size_t)out->grid;

    size_t tin_words  = (size_t)out->n_in  * (size_t)out->n_table_in;
    size_t clut_words = clut_nodes * (size_t)out->n_out;
    size_t tout_words = (size_t)out->n_out * (size_t)out->n_table_out;

    out->table_in  = (uint16_t *)malloc(tin_words  * sizeof(uint16_t));
    out->clut      = (uint16_t *)malloc(clut_words * sizeof(uint16_t));
    out->table_out = (uint16_t *)malloc(tout_words * sizeof(uint16_t));
    if (!out->table_in || !out->clut || !out->table_out) return -7;

    if (is_mft2) {
        size_t total_words = tin_words + clut_words + tout_words;
        if (52 + total_words * 2 > body_len) return -6;
        const uint8_t *p = body + 52;
        for (size_t i = 0; i < tin_words;  i++) { out->table_in[i]  = be16(p); p += 2; }
        for (size_t i = 0; i < clut_words; i++) { out->clut[i]      = be16(p); p += 2; }
        for (size_t i = 0; i < tout_words; i++) { out->table_out[i] = be16(p); p += 2; }
    } else { /* mft1: uint8 entries, scale to uint16 by *257 */
        size_t total_bytes = tin_words + clut_words + tout_words;
        if (48 + total_bytes > body_len) return -6;
        const uint8_t *p = body + 48;
        for (size_t i = 0; i < tin_words;  i++) { out->table_in[i]  = (uint16_t)(*p++ * 257u); }
        for (size_t i = 0; i < clut_words; i++) { out->clut[i]      = (uint16_t)(*p++ * 257u); }
        for (size_t i = 0; i < tout_words; i++) { out->table_out[i] = (uint16_t)(*p++ * 257u); }
    }
    return 0;
}

void icc_mft2_free(IccMft2 *m) {
    free(m->table_in);  m->table_in  = NULL;
    free(m->clut);      m->clut      = NULL;
    free(m->table_out); m->table_out = NULL;
}

/*
 * 1-D table linear interpolation (docs/58 §6.1: "linear interpolation at p = v*(n-1)").
 * Input v in [0, 65535]. Output in [0, 65535].
 */
static double linterp_1d(const uint16_t *table, int n, double v_norm) {
    /* v_norm = v / 65535.0, in [0,1] */
    double p = v_norm * (double)(n - 1);
    int lo = (int)p;
    if (lo >= n - 1) return (double)table[n - 1];
    if (lo < 0) return (double)table[0];
    double frac = p - (double)lo;
    return (double)table[lo] * (1.0 - frac) + (double)table[lo + 1] * frac;
}

/*
 * Trilinear CLUT interpolation for 3-in, 3-out mft2.
 * Cite: docs/58 §6.1 "multilinear (trilinear for i=3) interpolation over 2^i surrounding CLUT nodes"
 * CLUT addressing: clut[ (((c0*g + c1)*g + c2) * n_out) + k ]
 * Channel 0 slowest — exactly as docs/58 §6.1 states.
 *
 * in_norm[3]: each in [0,1] (after input table)
 * out[3]: output codes in [0, 65535]
 */
static void trilinear_clut(const IccMft2 *m, const double in_norm[3], double out[3]) {
    int g = m->grid;
    int no = m->n_out;

    /* Grid fractional positions */
    double q[3];
    int lo[3], hi[3];
    double frac[3];
    for (int c = 0; c < 3; c++) {
        q[c] = in_norm[c] * (double)(g - 1);
        lo[c] = (int)q[c];
        if (lo[c] >= g - 1) lo[c] = g - 2;
        if (lo[c] < 0) lo[c] = 0;
        hi[c] = lo[c] + 1;
        frac[c] = q[c] - (double)lo[c];
    }

    /* 8 corners: c0 slowest (docs/58): idx = ((c0*g + c1)*g + c2) * n_out + k */
    #define NODE(c0,c1,c2,k) ((double)(m->clut[(((c0)*g+(c1))*g+(c2))*no+(k)]))

    for (int k = 0; k < no; k++) {
        double v =
            NODE(lo[0],lo[1],lo[2],k) * (1.0-frac[0]) * (1.0-frac[1]) * (1.0-frac[2])
          + NODE(lo[0],lo[1],hi[2],k) * (1.0-frac[0]) * (1.0-frac[1]) * frac[2]
          + NODE(lo[0],hi[1],lo[2],k) * (1.0-frac[0]) * frac[1]       * (1.0-frac[2])
          + NODE(lo[0],hi[1],hi[2],k) * (1.0-frac[0]) * frac[1]       * frac[2]
          + NODE(hi[0],lo[1],lo[2],k) * frac[0]       * (1.0-frac[1]) * (1.0-frac[2])
          + NODE(hi[0],lo[1],hi[2],k) * frac[0]       * (1.0-frac[1]) * frac[2]
          + NODE(hi[0],hi[1],lo[2],k) * frac[0]       * frac[1]       * (1.0-frac[2])
          + NODE(hi[0],hi[1],hi[2],k) * frac[0]       * frac[1]       * frac[2];
        out[k] = v;
    }
    #undef NODE
}

/*
 * Full mft2 evaluation: 3 uint16 inputs → 3 uint16 outputs.
 * in_vals[3]: raw input codes in [0, 65535]
 * out_vals[3]: output codes in [0, 65535]
 */
void icc_mft2_eval(const IccMft2 *m, const uint16_t in_vals[3], uint16_t out_vals[3]) {
    double in_norm[3];
    /* Step 1: input 1-D table */
    for (int c = 0; c < 3; c++) {
        double raw_norm = (double)in_vals[c] / 65535.0;
        double after_tin = linterp_1d(m->table_in + c * m->n_table_in, m->n_table_in, raw_norm);
        in_norm[c] = after_tin / 65535.0;
    }
    /* Step 2: trilinear CLUT */
    double clut_out[3];
    trilinear_clut(m, in_norm, clut_out);
    /* Step 3: output 1-D table */
    for (int k = 0; k < m->n_out; k++) {
        double norm = clut_out[k] / 65535.0;
        double v = linterp_1d(m->table_out + k * m->n_table_out, m->n_table_out, norm);
        uint32_t vi = (uint32_t)(v + 0.5);
        if (vi > 65535) vi = 65535;
        out_vals[k] = (uint16_t)vi;
    }
}

/* -------------------------------------------------------------------------
 * Load ICC profile, trying the specified tag (A2B0 or B2A0).
 * If preferred_tag not found, tries the other direction.
 * Returns 0 on success. Caller must call icc_mft2_free() on success.
 * ------------------------------------------------------------------------- */
static int icc_load_profile_tag(const char *path, uint32_t preferred_tag, IccMft2 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "icc_load: cannot open %s\n", path); return -1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    rewind(f);
    if (sz <= 0) { fclose(f); return -2; }
    uint8_t *data = (uint8_t *)malloc((size_t)sz);
    if (!data) { fclose(f); return -3; }
    if (fread(data, 1, (size_t)sz, f) != (size_t)sz) { free(data); fclose(f); return -4; }
    fclose(f);

    size_t tag_len = 0;
    const uint8_t *tag = icc_find_tag(data, (size_t)sz, preferred_tag, &tag_len);
    if (!tag) {
        /* Try the other direction */
        uint32_t alt = (preferred_tag == ICC_A2B0_TAG) ? ICC_B2A0_TAG : ICC_A2B0_TAG;
        tag = icc_find_tag(data, (size_t)sz, alt, &tag_len);
    }
    if (!tag) {
        free(data);
        fprintf(stderr, "icc_load: no A2B0/B2A0 tag in %s\n", path);
        return -5;
    }

    int rc = icc_mft2_parse(tag, tag_len, out);
    free(data);
    if (rc != 0) fprintf(stderr, "icc_load: parse=%d in %s\n", rc, path);
    return rc;
}

/* Load using A2B0 (default for most profiles) */
int icc_load_profile(const char *path, IccMft2 *out) {
    return icc_load_profile_tag(path, ICC_A2B0_TAG, out);
}

/* Load using B2A0 (for Srgb_v2.pf which has mft2 on B2A0, docs/58 §6 row 10) */
int icc_load_profile_b2a0(const char *path, IccMft2 *out) {
    return icc_load_profile_tag(path, ICC_B2A0_TAG, out);
}

/*
 * Encode 12-bit RPD code (0..4095) to 16-bit ICC input.
 *
 * Cite: docs/58-colour-pipeline.md §6 row 9:
 *   "input tables min(65535, round(i·65535/3000)) — clips above RPD code 3000"
 *
 * This is what rpd12_to_icc_u8 does in the Python pipeline before the CLUT:
 * map RPD 0..4095 → input table index 0..65535 by the profile's own input
 * table (which already encodes the clip at 3000).
 * We just need the raw 16-bit code to feed the profile's input table:
 *   v16 = min(65535, round(rpd * 65535 / 3000))
 */
static uint16_t rpd12_to_u16(int rpd12) {
    if (rpd12 <= 0) return 0;
    if (rpd12 >= 4095) return 65535;
    /* Map 0..4095 RPD code to 0..65535 for table_in index (n_table_in = 4096 entries).
     * Cite: docs/58-colour-pipeline.md §6.1: table_in[i] has 4096 entries corresponding
     * directly to 12-bit RPD codes 0..4095. Entry i contains min(65535, round(i*65535/3000)). */
    int v = (int)((double)rpd12 * 65535.0 / 4095.0 + 0.5);
    if (v > 65535) v = 65535;
    return (uint16_t)v;
}

/*
 * Two-stage ICC render: RPD 12-bit → sRGB 8-bit via Rpd2Pcs + Srgb profiles.
 *
 * Cite: PakonIMAu.dll @ 0x1027b970 (profile path Rpd2Pcs_HR200_QS_v5s10.pf → Srgb_v2.pf)
 * Cite: dataPathItems/profile/profile-Rpd2Srgb.dpi: profile1 = Rpd2Pcs_HR200_QS_v5s10.pf
 *       profile2 = Srgb_v2.pf, dataType = U8, renderIntent = P
 *
 * rpd[3]: 12-bit RPD values (0..4095) per channel R,G,B
 * Returns packed sRGB (R,G,B in 0..255).
 */
void icc_rpd12_to_srgb8(
    const IccMft2 *rpd2pcs,   /* Rpd2Pcs_HR200_QS_v5s10.pf A2B0 */
    const IccMft2 *srgb,      /* Srgb_v2.pf A2B0 */
    const int32_t  rpd[3],
    uint8_t        srgb_out[3])
{
    /* Stage 1: RPD → PCS (Lab) */
    uint16_t in1[3], pcs[3];
    for (int c = 0; c < 3; c++) {
        int v = rpd[c];
        if (v < 0) v = 0;
        if (v > 4095) v = 4095;
        in1[c] = rpd12_to_u16(v);
    }
    icc_mft2_eval(rpd2pcs, in1, pcs);

    /* Stage 2: PCS (Lab) → sRGB
     * Srgb_v2.pf is B2A0 in reverse direction; for the A2B0 direction we use
     * the sRGB profile's A2B0 tag which maps Lab→sRGB.
     * Input encoding: PCS Lab16: L 0..0xFF00, a/b 0..0xFFFF with 0x8000=0
     * (docs/58 §6 row 13 note). But Rpd2Pcs output is already in the range
     * the Srgb A2B0 input table expects (both are 16-bit ICC v2 values).
     */
    uint16_t srgb16[3];
    icc_mft2_eval(srgb, pcs, srgb16);

    /* dataType = U8: scale 0..65535 → 0..255 */
    for (int c = 0; c < 3; c++) {
        uint32_t v = (uint32_t)srgb16[c] * 255 / 65535;
        srgb_out[c] = (uint8_t)(v > 255 ? 255 : v);
    }
}
