/* The write guard (Task 4). Evidence: docs/re/29-write-guard-audit.md sections 7.1-7.5, plan rulings S-R5, S-R7..S-R10, S-R25.
 *
 * Two layers live here:
 *  1. the packet rules: role lookup, the FORBID rows of commands.def, the exact-address and beta-role refusals
 *     (pkl_check_packet), used by the link and by the guarded transport's bulk-out;
 *  2. the guarded transport: a pk_transport whose private state is the ONLY holder of the raw transport. Control
 *     transfers are an allowlist (A0 and A3 only inside a load window, A3 only while Kodak's pinned stage-1 runs (S-R25), A4 with 0xA5/0xA3, A9 IN after such an A4). Bulk-out is
 *     checked packet by packet against the roles bound by the link. Everything else is passed through (bulk-in, stream).
 *
 * State is per guard instance (heap), never global. When in doubt a rule refuses; a refusal sends nothing. In the load
 * window, state updates that RESTRICT (voiding an approval, marking an internal write, a hold) happen before the
 * transfer is sent; updates that PERMIT (coverage, status confirmation, the A4 selection) happen only after it succeeded. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "link/guard.h"
#include "util/util.h"

/* ---------------------------------------------------------------- packet rules (commands.def) */

enum { ROLE_LIGHT, ROLE_MOTOR, ROLE_HOST, ROLE_DX, ROLE_LAMP235, ROLE_MOTOR235, ROLE_DX235, ROLE_APS235, ROLE_GUIDE,
       ROLE__N };

typedef struct { uint8_t type, role, reg, forbid; } cmd_row;
#define PK_CMD(n, t, r, g, l, f, ti, s) { t, ROLE_##r, g, f },
static const cmd_row ROWS[] = {
#include "tables/commands.def"
};
#undef PK_CMD
#define NROWS (sizeof ROWS / sizeof ROWS[0])

/* Build-time check of the address rule itself, so that the macro Task 6 asserts over models.def is known to be right. */
typedef char pkl_assert_addr_rule[(PKL_ADDR_OK(0x40) && PKL_ADDR_OK(0x10) && PKL_ADDR_OK(0xF4) && PKL_ADDR_OK(0x20) &&
                                   !PKL_ADDR_OK(0x41) && !PKL_ADDR_OK(0xA0) && !PKL_ADDR_OK(0xA4) && !PKL_ADDR_OK(0xAE) &&
                                   !PKL_ADDR_OK(0xAF) && PKL_ADDR_OK(0xB0) && PKL_ADDR_OK(0x9E) && !PKL_ADDR_OK(0)) ? 1 : -1];

static uint8_t role_addr(const pk_link_roles *r, int role) {
    switch (role) {
    case ROLE_LIGHT: return r->light;
    case ROLE_MOTOR: return r->motor;
    case ROLE_HOST: return r->host;
    case ROLE_DX: return r->dx ? r->dx : r->light;   /* the DX rows always apply at the light-board address (TLB models) */
    case ROLE_LAMP235: return r->lamp235;
    case ROLE_MOTOR235: return r->motor235;
    case ROLE_DX235: return r->dx235;
    case ROLE_APS235: return r->aps235;
    case ROLE_GUIDE: return r->guide;
    default: return 0;
    }
}

static int role_is_beta(int role) { return role >= ROLE_LAMP235; }

bool pk_roles_has_address(const pk_link_roles *r, uint8_t addr) {
    if (!r || addr == 0) return false;
    for (int k = 0; k < ROLE__N; k++) if (role_addr(r, k) == addr) return true;
    return false;
}

bool pk_roles_is_beta_address(const pk_link_roles *r, uint8_t addr) {
    if (!r || addr == 0) return false;
    for (int k = 0; k < ROLE__N; k++) if (role_is_beta(k) && role_addr(r, k) == addr) return true;
    return false;
}

int pkl_is_forbidden(const pk_link_roles *r, uint8_t type, uint8_t addr, uint8_t reg) {
    if (!r || addr == 0) return 0;
    for (size_t i = 0; i < NROWS; i++) {   /* linear scan; FORBID=1 rows only */
        if (!ROWS[i].forbid || ROWS[i].type != type || ROWS[i].reg != reg) continue;
        if (role_addr(r, ROWS[i].role) == addr) return 1;
    }
    return 0;
}

#if defined(__GNUC__)
#define PKL_PRINTF(a, b) __attribute__((format(printf, a, b)))
#else
#define PKL_PRINTF(a, b)
#endif

PKL_PRINTF(3, 4) static pk_status refuse_pkt(char *why, size_t cap, const char *fmt, ...) {
    if (why && cap) {
        va_list ap;
        va_start(ap, fmt);
        vsnprintf(why, cap, fmt, ap);
        va_end(ap);
    }
    return PK_E_WRITE_FORBIDDEN;
}

pk_status pkl_check_packet(const pk_link_roles *r, const uint8_t *p, size_t n, char *why, size_t cap) {
    if (why && cap) why[0] = 0;
    if (!r || !p || n < 3 || n > PKL_MAX_OUT) return refuse_pkt(why, cap, "not a packet (%u bytes)", (unsigned)n);
    uint8_t type = p[0], addr = p[2];
    if (type < 1 || type > 4) return refuse_pkt(why, cap, "packet type %u is not 1-4", type);
    if ((size_t)p[1] + 2 != n) return refuse_pkt(why, cap, "type %u: length byte %u does not match the packet", type, p[1]);
    int ok;
    switch (type) {
    case 1: ok = n == 5; break;
    case 2: ok = n >= 5 && p[1] == (uint8_t)(p[3] + 3); break;
    case 3: ok = n == 3; break;
    default: ok = n == 5 && p[3] == 0; break;
    }
    if (!ok) return refuse_pkt(why, cap, "type %u: malformed packet (%u bytes)", type, (unsigned)n);
    if (!pk_roles_has_address(r, addr))
        return refuse_pkt(why, cap, "type %u: address 0x%02X is not a role address of this model", type, addr);
    if (pk_roles_is_beta_address(r, addr))
        return refuse_pkt(why, cap, "type %u: address 0x%02X belongs to a beta role (refused wholesale)", type, addr);
    if (type != 3 && pkl_is_forbidden(r, type, addr, p[4]))
        return refuse_pkt(why, cap, "type %u: register/command 0x%02X at 0x%02X is a forbidden (memory-writing) row", type, p[4], addr);
    return PK_OK;
}

/* ---------------------------------------------------------------- guarded transport */

#define BM_BYTES (0x10000 / 8)
#define BIT_GET(m, a) (((m)[(a) >> 3] >> ((a) & 7)) & 1u)
#define BIT_SET(m, a) ((m)[(a) >> 3] = (uint8_t)((m)[(a) >> 3] | (1u << ((a) & 7))))
#define BIT_CLR(m, a) ((m)[(a) >> 3] = (uint8_t)((m)[(a) >> 3] & ~(1u << ((a) & 7))))

#define A0_CPUCS 0xE600u
#define A0_INT_END 0x4000u       /* internal RAM ends below this */
#define A0_EXT_END 0xE000u       /* A3 never reaches this address or above (registers, CPUCS, the I2C controller) */
#define A3_MIN_EXCL 0x1B3Fu      /* Kodak's MAX_INTERNAL_ADDRESS: A3 only above it, A0 only at or below it */
#define LOAD_REC_MAX 16u         /* Kodak's MAX_INTEL_HEX_RECORD_LENGTH: no load transfer is longer */
#define CPUCS_HOLD 0x01          /* Kodak FX35Loader.c Ezusb_8051Reset(1) / v1 pakon_load.py: 8051RES set */
#define CPUCS_RELEASE 0x00       /* Ezusb_8051Reset(0) */
#define CTL_MAX 0x1000           /* largest control transfer; the guard works on a private copy of it */

/* The load window follows Kodak's own sequence (S-R25; RE 29 sec 7.5, hw1-load-debug.md sec 6):
 *   PH_NEW      window open, nothing sent yet
 *   PH_S1_LOAD  held; A0 writes equal to records of the PINNED stage-1 (from Kodak's F235Ldr.sys) and nothing else
 *   PH_S1_RUN   the stage-1 runs (released with every stage-1 byte resident): A3 OUT/IN, at most 16 bytes, address above
 *               0x1B3F and below 0xE000, OUT bytes equal to the image at those addresses; no A0 write, no A4, no A9
 *   PH_FW       held again (a hold ends PH_S1_RUN for good: A3 is refused from here on): A0 writes equal to image records
 *               at or below 0x1B3F; the final release needs every image byte written AND read back equal
 * The window closes on the final release. There is no path back from PH_FW to PH_S1_RUN.
 *
 * It keeps a SHADOW of internal RAM 0x0000..0x3FFF: what the guard has itself let be written by A0, byte by byte (S-R11).
 * The shadow is wiped when the stage-1 is released, because the running stage-1 owns that RAM. Restricting updates (a
 * hold, a release, voiding a write's earlier read-back) happen before the transfer is sent; permitting ones (coverage,
 * read-back confirmation, the shadow bytes) only after it succeeded. */
enum { PH_NEW, PH_S1_LOAD, PH_S1_RUN, PH_FW };
typedef struct {
    const pk_image *s1, *fw;
    int phase;
    int held;                     /* a hold succeeded and no release was attempted since */
    uint8_t sh[A0_INT_END];       /* shadow bytes */
    uint8_t sh_set[BM_BYTES];     /* bit a: sh[a] is what the device holds at a */
    uint8_t a3_conf[BM_BYTES];    /* fw bytes A3-written (transfer succeeded) while the stage-1 ran */
    uint8_t rb_ext[BM_BYTES];     /* fw bytes whose last A3 IN read-back equalled the image */
    uint8_t rb_int[BM_BYTES];     /* fw bytes (below 0x4000) whose last A0 IN read-back, held, equalled the image */
} win;

typedef struct {
    pk_transport *inner;
    int owns;                     /* closing the guard closes inner */
    uint8_t a4;                   /* 0, or the allowed A4 wValue (0xA5 / 0xA3) selected for a following A9 IN */
    int roles_bound; pk_link_roles roles;
    int wedged;                   /* the firmware stopped answering (sticky, set by the link) */
    win *w;                       /* the open load window, or NULL */
} gst;

static const pk_transport_ops GUARD_OPS;

int pkl_guard_is_guarded(const pk_transport *t) { return t && t->ops == &GUARD_OPS; }
static gst *G(pk_transport *t) { return (gst *)t->impl; }

PKL_PRINTF(2, 3) static pk_status forbid(pk_transport *t, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(t->diag, sizeof t->diag, fmt, ap);
    va_end(ap);
    return PK_E_WRITE_FORBIDDEN;
}

static void sync_diag(pk_transport *t) {
    memcpy(t->diag, G(t)->inner->diag, sizeof t->diag);
    t->diag[sizeof t->diag - 1] = 0;
}

/* every byte of [a, a+n) is set in img and equals d */
static int matches_image(const pk_image *img, unsigned a, const uint8_t *d, size_t n) {
    if (!img || a + n > 0x10000) return 0;
    for (size_t i = 0; i < n; i++) if (!PK_IMAGE_USED(img, a + i) || img->mem[a + i] != d[i]) return 0;
    return 1;
}

static int sh_is(const win *w, unsigned a, uint8_t v) { return BIT_GET(w->sh_set, a) && w->sh[a] == v; }

/* every byte of the stage-1 image is in the shadow with the image's value */
static int s1_resident(const win *w) {
    for (unsigned a = 0; a < A0_INT_END; a++)
        if (PK_IMAGE_USED(w->s1, a) && !sh_is(w, a, w->s1->mem[a])) return 0;
    return 1;
}
/* every image byte is written (A0 shadow at or below 0x1B3F, A3 above it) and was read back equal (A3 IN above 0x1B3F, A0 IN
 * below 0x4000, both where both apply) */
static int fw_complete(const win *w) {
    for (unsigned a = 0; a < 0x10000; a++) {
        if (!PK_IMAGE_USED(w->fw, a)) continue;
        if (a <= A3_MIN_EXCL) {
            if (!sh_is(w, a, w->fw->mem[a])) return 0;
        } else {
            if (a >= A0_EXT_END || !BIT_GET(w->a3_conf, a) || !BIT_GET(w->rb_ext, a)) return 0;
        }
        if (a < A0_INT_END && !BIT_GET(w->rb_int, a)) return 0;
    }
    return 1;
}

/* One 40/A0 write inside the window, vetted against the window state. */
typedef struct {
    int kind;   /* 1 hold, 2 stage-1 release, 3 final release, 6 RAM write */
    unsigned a; size_t n; const uint8_t *d;
} a0_plan;

static pk_status a0_write_plan(pk_transport *t, win *w, unsigned a, const uint8_t *d, size_t n, a0_plan *p) {
    memset(p, 0, sizeof *p);
    p->a = a; p->n = n; p->d = d;
    if (!d || n == 0 || n > CTL_MAX || a + n > 0x10000)
        return forbid(t, "write guard: A0 write of %u bytes at 0x%04X is not a load-window write", (unsigned)n, a);
    if (a == A0_CPUCS) {
        if (n == 1 && d[0] == CPUCS_HOLD) { p->kind = 1; return PK_OK; }
        if (n == 1 && d[0] == CPUCS_RELEASE) {
            if (w->phase == PH_S1_LOAD && w->held) {
                if (!s1_resident(w))
                    return forbid(t, "write guard: CPUCS release while the pinned stage-1 is not fully resident in the shadow");
                p->kind = 2;
                return PK_OK;
            }
            if (w->phase == PH_FW && w->held) {
                if (!fw_complete(w))
                    return forbid(t, "write guard: final release before every firmware byte was written and read back equal");
                p->kind = 3;
                return PK_OK;
            }
            return forbid(t, "write guard: CPUCS release refused in this phase of the load (stage-1 written and held, or the final held phase)");
        }
        return forbid(t, "write guard: CPUCS write 0x%02X is neither the hold nor the release value", n == 1 ? d[0] : 0xFFu);
    }
    if (!w->held) return forbid(t, "write guard: A0 write at 0x%04X refused: the 8051 is not held (CPUCS hold first)", a);
    if (n > LOAD_REC_MAX) return forbid(t, "write guard: A0 write of %u bytes refused (load records are at most %u)", (unsigned)n, LOAD_REC_MAX);
    if (w->phase == PH_S1_LOAD && a + n <= A0_INT_END && matches_image(w->s1, a, d, n)) { p->kind = 6; return PK_OK; }
    if (w->phase == PH_FW && a + n - 1 <= A3_MIN_EXCL && matches_image(w->fw, a, d, n)) { p->kind = 6; return PK_OK; }
    return forbid(t, "write guard: A0 write of %u bytes at 0x%04X is not an image byte destined for that address in this phase (stage-1 records, then firmware records at or below 0x%04X)",
                  (unsigned)n, a, A3_MIN_EXCL);
}

static void a0_restrict(win *w, const a0_plan *p) {   /* before the transfer */
    switch (p->kind) {
    case 1: if (w->phase == PH_S1_RUN) w->phase = PH_FW; break;   /* a hold ends the stage-1 run: A3 is refused from here */
    case 2:
        w->held = 0;
        w->phase = PH_S1_RUN;
        memset(w->sh_set, 0, sizeof w->sh_set);   /* the running stage-1 owns that RAM now */
        break;
    case 3: w->held = 0; break;
    case 6:
        for (size_t i = 0; i < p->n; i++) { BIT_CLR(w->sh_set, p->a + (unsigned)i); BIT_CLR(w->rb_int, p->a + (unsigned)i); }   /* unknown until the transfer succeeds */
        break;
    default: break;
    }
}

static void a0_permit(win *w, const a0_plan *p) {   /* after the transfer succeeded */
    switch (p->kind) {
    case 1: w->held = 1; if (w->phase == PH_NEW) w->phase = PH_S1_LOAD; break;
    case 6:
        for (size_t i = 0; i < p->n; i++) { w->sh[p->a + i] = p->d[i]; BIT_SET(w->sh_set, p->a + (unsigned)i); }
        break;
    default: break;
    }
}

/* ---- control ops */

static pk_status g_control(pk_transport *t, uint8_t rt, uint8_t req, uint16_t val, uint16_t idx, uint8_t *data, size_t len,
                           unsigned to) {
    gst *g = G(t);
    uint8_t buf[CTL_MAX];   /* a private copy: what is vetted is what is sent, whatever other threads do to the caller's buffer */
    int in = (rt & 0x80) != 0;
    uint8_t a4 = g->a4;
    if (!(req == 0xA4 && !in) && !(req == 0xA9 && in)) g->a4 = 0;   /* any other transfer clears the A4 selection */
    if (rt != 0x40 && rt != 0xC0)   /* the vendor handlers act only on exactly 0x40 / 0xC0 (RE 29 sec 7.1) */
        return forbid(t, "write guard: control request type 0x%02X refused (only 0x40 / 0xC0)", rt);
    if (len > CTL_MAX) return forbid(t, "write guard: control transfer of %u bytes refused", (unsigned)len);
    if (req == 0xA0) {
        g->a4 = 0;   /* and so does every A0, allowed or not */
        win *w = g->w;
        if (!w) return forbid(t, "write guard: A0 outside a load window is refused");
        if (in) {
            if (!data || len == 0 || (unsigned)val + len > 0x10000)
                return forbid(t, "write guard: C0/A0 read of %u bytes at 0x%04X refused", (unsigned)len, val);
            if (val & 1u)   /* HW-1 2026-10-19: on the owner's FX2 an A0 IN at an odd address returns the bytes from the even address
                               below (289 of 289 odd reads shifted, 263 of 263 even reads exact), so its bytes cannot be checked */
                return forbid(t, "write guard: C0/A0 read at odd address 0x%04X refused (the boot ROM reads from the even address below)", val);
            if ((unsigned)val < 0xE67Au && (unsigned)val + len > 0xE678u)   /* the I2C controller registers */
                return forbid(t, "write guard: C0/A0 read overlapping the I2C controller (0xE678) refused");
            pk_status s = g->inner->ops->control(g->inner, rt, req, val, idx, buf, len, to);
            sync_diag(t);
            if (s == PK_OK) memcpy(data, buf, len);
            if (s == PK_OK && w->held && w->phase == PH_FW && (unsigned)val + len <= A0_INT_END)   /* the read-back that the final release requires */
                for (size_t i = 0; i < len; i++) {
                    unsigned a = (unsigned)val + (unsigned)i;
                    if (!PK_IMAGE_USED(w->fw, a)) continue;
                    if (buf[i] == w->fw->mem[a]) BIT_SET(w->rb_int, a); else BIT_CLR(w->rb_int, a);
                }
            return s;
        }
        if (!data) return forbid(t, "write guard: A0 write with no data refused");
        memcpy(buf, data, len);
        a0_plan p;
        pk_status s = a0_write_plan(t, w, val, buf, len, &p);
        if (s != PK_OK) return s;
        a0_restrict(w, &p);
        if (p.kind == 3) { free(g->w); g->w = NULL; w = NULL; }   /* the window closes on the final release, however the transfer ends */
        s = g->inner->ops->control(g->inner, rt, req, val, idx, buf, len, to);
        sync_diag(t);
        if (s == PK_OK && w) a0_permit(w, &p);
        return s;
    }
    if (req == 0xA3) {
        g->a4 = 0;
        win *w = g->w;
        if (!w) return forbid(t, "write guard: A3 outside a load window is refused");
        if (w->phase != PH_S1_RUN)
            return forbid(t, "write guard: A3 is allowed only while the pinned stage-1 runs (after its release, before the next hold)");
        if (idx != 0 || len < 1 || len > LOAD_REC_MAX || (unsigned)val <= A3_MIN_EXCL || (unsigned)val + len > A0_EXT_END)
            return forbid(t, "write guard: A3 of %u bytes at 0x%04X wIndex 0x%04X is outside 1..%u bytes, above 0x%04X, below 0x%04X", (unsigned)len, val, idx,
                          LOAD_REC_MAX, A3_MIN_EXCL, A0_EXT_END);
        if (!data) return forbid(t, "write guard: A3 with no data refused");
        if (in) {
            pk_status s = g->inner->ops->control(g->inner, rt, req, val, idx, buf, len, to);
            sync_diag(t);
            if (s != PK_OK) return s;
            memcpy(data, buf, len);
            for (size_t i = 0; i < len; i++) {   /* the read-back the final release requires */
                unsigned a = (unsigned)val + (unsigned)i;
                if (!PK_IMAGE_USED(w->fw, a)) continue;
                if (buf[i] == w->fw->mem[a]) BIT_SET(w->rb_ext, a); else BIT_CLR(w->rb_ext, a);
            }
            return PK_OK;
        }
        memcpy(buf, data, len);
        if (!matches_image(w->fw, val, buf, len))
            return forbid(t, "write guard: A3 write of %u bytes at 0x%04X is not the firmware image at that address", (unsigned)len, val);
        for (size_t i = 0; i < len; i++) { BIT_CLR(w->a3_conf, val + (unsigned)i); BIT_CLR(w->rb_ext, val + (unsigned)i); }   /* restrict first */
        pk_status s = g->inner->ops->control(g->inner, rt, req, val, idx, buf, len, to);
        sync_diag(t);
        if (s == PK_OK) for (size_t i = 0; i < len; i++) BIT_SET(w->a3_conf, val + (unsigned)i);
        return s;
    }
    if (req == 0xA4 && !in) {
        g->a4 = 0;
        if (g->w && g->w->phase == PH_S1_RUN) return forbid(t, "write guard: A4 refused while the stage-1 runs");
        if (val != 0xA5 && val != 0xA3) return forbid(t, "write guard: A4 with wValue 0x%04X refused (only 0xA5 and 0xA3)", val);
        if (len != 0) return forbid(t, "write guard: A4 with a data stage refused");
        pk_status s = g->inner->ops->control(g->inner, rt, req, val, idx, NULL, 0, to);
        sync_diag(t);
        g->a4 = s == PK_OK ? (uint8_t)val : 0;
        return s;
    }
    if (req == 0xA9 && in) {
        if (g->w && g->w->phase == PH_S1_RUN) { g->a4 = 0; return forbid(t, "write guard: A9 refused while the stage-1 runs"); }
        if (a4 == 0) return forbid(t, "write guard: A9 IN with no preceding allowed A4 refused");
        g->a4 = a4;   /* a refused A9 IN does not drop the selection (the Task 24 text requires it; nothing is sent); an allowed one keeps it */
        if (!data || len > 0x40 || (unsigned)val + len > 0x2000)
            return forbid(t, "write guard: A9 IN at 0x%04X length %u is outside offset+length <= 0x2000, length <= 0x40", val, (unsigned)len);
        pk_status s = g->inner->ops->control(g->inner, rt, req, val, idx, buf, len, to);
        sync_diag(t);
        if (s == PK_OK) memcpy(data, buf, len);
        return s;
    }
    return forbid(t, "write guard: control request 0x%02X (%s) refused", req, in ? "IN" : "OUT");
}

/* ---- bulk, stream, reopen, close */

static pk_status g_bulk_out(pk_transport *t, uint8_t ep, const uint8_t *d, size_t n, unsigned to) {
    gst *g = G(t);
    uint8_t buf[PKL_MAX_OUT];
    g->a4 = 0;
    if (ep != 0x01) return forbid(t, "write guard: bulk-out to endpoint 0x%02X refused (only EP 0x01 board packets)", ep);
    if (!g->roles_bound) return forbid(t, "write guard: bulk-out with no link bound (roles unknown) refused");
    if (!d || n > sizeof buf) return forbid(t, "write guard: bulk-out of %u bytes refused", (unsigned)n);
    memcpy(buf, d, n);   /* vet and send the same bytes */
    char why[160];
    pk_status s = pkl_check_packet(&g->roles, buf, n, why, sizeof why);
    if (s != PK_OK) { snprintf(t->diag, sizeof t->diag, "write guard: %s", why); return s; }
    s = g->inner->ops->bulk_out(g->inner, ep, buf, n, to);
    sync_diag(t);
    return s;
}

static pk_status g_bulk_in(pk_transport *t, uint8_t ep, uint8_t *d, size_t cap, size_t *got, unsigned to) {
    gst *g = G(t);
    g->a4 = 0;
    pk_status s = g->inner->ops->bulk_in(g->inner, ep, d, cap, got, to);
    sync_diag(t);
    return s;
}

static pk_status g_stream_read(pk_transport *t, uint8_t *buf, size_t cap, size_t *got, unsigned to) {
    gst *g = G(t);   /* touches only inner and t->sdiag: safe beside one link-thread caller */
    pk_status s = g->inner->ops->stream_read(g->inner, buf, cap, got, to);
    if (s != PK_OK && s != PK_E_TIMEOUT) {
        memcpy(t->sdiag, g->inner->sdiag, sizeof t->sdiag);
        t->sdiag[sizeof t->sdiag - 1] = 0;
    }
    return s;
}

static pk_status g_reopen(pk_transport *t, uint16_t vid, uint16_t pid, unsigned wait_ms) {
    gst *g = G(t);
    g->a4 = 0;
    free(g->w); g->w = NULL;   /* a re-enumeration ends any load window */
    pk_status s = g->inner->ops->reopen(g->inner, vid, pid, wait_ms);
    sync_diag(t);
    return s;
}

static void g_close(pk_transport *t) {
    gst *g = G(t);
    if (!g) return;
    if (g->owns && g->inner) pk_transport_close(g->inner);
    free(g->w);
    free(g);
    t->impl = NULL;
}

static const pk_transport_ops GUARD_OPS = { g_bulk_out, g_bulk_in, g_control, g_stream_read, g_reopen, g_close };

static pk_status guard_new(pk_transport *inner, int owns, pk_transport **out) {
    pk_transport *t = (pk_transport *)calloc(1, sizeof *t);
    gst *g = (gst *)calloc(1, sizeof *g);
    if (!t || !g) { free(t); free(g); return PK_E_NOMEM; }
    g->inner = inner;
    g->owns = owns;
    t->ops = &GUARD_OPS;
    t->impl = g;
    *out = t;
    return PK_OK;
}

pk_status pk_transport_guard_open(pk_transport *inner, pk_transport **out) {
    if (out) *out = NULL;
    if (!inner || !out || !inner->ops) return PK_E_ARG;
    if (pkl_guard_is_guarded(inner)) { *out = inner; return PK_OK; }
    return guard_new(inner, 0, out);
}

pk_status pkl_guard_adopt(pk_transport *raw, pk_transport **out) {
    if (out) *out = NULL;
    if (!raw || !out || !raw->ops) return PK_E_ARG;
    if (pkl_guard_is_guarded(raw)) { *out = raw; return PK_OK; }
    return guard_new(raw, 1, out);
}

pk_transport *pkl_guard_peek_inner(pk_transport *t) {
    if (!pkl_guard_is_guarded(t) || !G(t)->owns) return NULL;
    return G(t)->inner;
}

void pkl_guard_set_inner(pk_transport *t, pk_transport *inner) {
    if (pkl_guard_is_guarded(t) && inner) G(t)->inner = inner;
}

void pkl_guard_bind_roles(pk_transport *t, const pk_link_roles *roles) {
    if (!pkl_guard_is_guarded(t)) return;
    gst *g = G(t);
    if (roles) { g->roles = *roles; g->roles_bound = 1; } else { memset(&g->roles, 0, sizeof g->roles); g->roles_bound = 0; }
}

int pkl_guard_wedged(const pk_transport *t) { return pkl_guard_is_guarded(t) && ((gst *)t->impl)->wedged; }
void pkl_guard_set_wedged(pk_transport *t) { if (pkl_guard_is_guarded(t)) G(t)->wedged = 1; }

/* Canonical SHA-256 of an image: over (addr_hi, addr_lo, value) of every used byte in address order. */
void pkl_image_canon_hex(const pk_image *img, char hex[65]) {
    pku_sha256 c;
    uint8_t d[32];
    static const char hx[] = "0123456789abcdef";
    pku_sha256_init(&c);
    for (unsigned a = 0; a < 0x10000; a++) {
        if (!PK_IMAGE_USED(img, a)) continue;
        uint8_t r[3] = { (uint8_t)(a >> 8), (uint8_t)a, img->mem[a] };
        pku_sha256_update(&c, r, 3);
    }
    pku_sha256_final(&c, d);
    for (int i = 0; i < 32; i++) { hex[2 * i] = hx[d[i] >> 4]; hex[2 * i + 1] = hx[d[i] & 15]; }
    hex[64] = 0;
}

pk_status pkl_guard_load_begin(pk_transport *t, const pk_image *stage1, const pk_image *fw) {
    if (!pkl_guard_is_guarded(t) || !stage1 || !fw) return PK_E_ARG;
    gst *g = G(t);
    free(g->w);
    g->w = NULL;
    g->a4 = 0;
    char hex[65];
    pkl_image_canon_hex(stage1, hex);
    if (strcmp(hex, PKL_STAGE1_CANON_SHA256) != 0) {   /* not Kodak's stage-1: no window, so not one transfer */
        snprintf(t->diag, sizeof t->diag, "write guard: the stage-1 image is not the pinned Kodak stage-1 (canonical SHA-256 %.16s...)", hex);
        return PK_E_CORRUPT;
    }
    for (unsigned a = A0_INT_END; a < 0x10000; a++)
        if (PK_IMAGE_USED(stage1, a)) { snprintf(t->diag, sizeof t->diag, "write guard: stage-1 byte at 0x%04X is outside internal RAM", a); return PK_E_CORRUPT; }
    win *w = (win *)calloc(1, sizeof *w);
    if (!w) return PK_E_NOMEM;   /* no window: every A0 and A3 stays refused */
    w->s1 = stage1;
    w->fw = fw;
    w->phase = PH_NEW;
    g->w = w;
    return PK_OK;
}

void pkl_guard_load_end(pk_transport *t) {
    if (!pkl_guard_is_guarded(t)) return;
    gst *g = G(t);
    free(g->w);
    g->w = NULL;
    g->a4 = 0;
}
