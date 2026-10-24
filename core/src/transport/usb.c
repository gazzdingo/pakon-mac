#define _POSIX_C_SOURCE 200809L
#include <stdlib.h>
#include <string.h>
#include "transport/trace.h"

#ifndef PK_HAVE_LIBUSB

pk_status pk_usb_list(pk_usb_info *out, size_t cap, size_t *n) {
    (void)out; (void)cap;
    if (n) *n = 0;
    return PK_E_UNSUPPORTED;
}
pk_status pk_usb_open(const pk_usb_info *which, pk_transport **out) {
    (void)which;
    if (out) *out = NULL;
    return PK_E_UNSUPPORTED;
}
pk_status pk_usb_read_serial(const pk_usb_info *which, char serial[32]) {
    (void)which;
    if (serial) serial[0] = 0;
    return PK_E_UNSUPPORTED;
}

#else

#include <limits.h>
#include <stdio.h>
#include <time.h>
#include <libusb.h>

/* usb_errmap.c hard-codes these values. */
typedef char pk_chk_errmap[(LIBUSB_ERROR_IO == -1 && LIBUSB_ERROR_ACCESS == -3 && LIBUSB_ERROR_NO_DEVICE == -4 &&
                            LIBUSB_ERROR_NOT_FOUND == -5 && LIBUSB_ERROR_BUSY == -6 && LIBUSB_ERROR_TIMEOUT == -7 &&
                            LIBUSB_ERROR_OVERFLOW == -8 && LIBUSB_ERROR_PIPE == -9 && LIBUSB_ERROR_NO_MEM == -11)
                           ? 1 : -1];

#define STREAM_EP 0x86

typedef struct {
    libusb_context *ctx;       /* one context per transport: no global state */
    libusb_device_handle *h;   /* NULL after a failed reopen */
    uint8_t bus;
} usbt;

static pk_status fail(pk_transport *t, const char *what, int rc) {
    snprintf(t->diag, sizeof t->diag, "%s: %s", what, libusb_error_name(rc));
    return pk_usb_map_error(rc);
}

static pk_status fail_s(pk_transport *t, const char *what, int rc) {
    if (rc != LIBUSB_ERROR_TIMEOUT) snprintf(t->sdiag, sizeof t->sdiag, "%s: %s", what, libusb_error_name(rc));
    return pk_usb_map_error(rc);
}

static int clamp_timeout(unsigned ms) { return ms > (unsigned)INT_MAX ? INT_MAX : (int)ms; }

static pk_status ub_bulk_out(pk_transport *t, uint8_t ep, const uint8_t *d, size_t n, unsigned to) {
    usbt *u = (usbt *)t->impl;
    if (!u->h) return PK_E_DISCONNECTED;
    if ((ep & 0x80) || (n && !d) || n > PK_TRANSPORT_MAX_XFER) return PK_E_ARG;
    size_t done = 0;
    do {   /* a zero-length write is sent once */
        int x = 0;
        int rc = libusb_bulk_transfer(u->h, ep, (unsigned char *)(uintptr_t)(d ? d + done : NULL), (int)(n - done), &x,
                                      (unsigned)clamp_timeout(to));
        if (rc != 0) return fail(t, "bulk_out", rc);
        done += (size_t)x;
        if (x == 0 && done < n) return fail(t, "bulk_out stalled", LIBUSB_ERROR_IO);
    } while (done < n);
    return PK_OK;
}

static pk_status ub_bulk_in(pk_transport *t, uint8_t ep, uint8_t *d, size_t cap, size_t *got, unsigned to) {
    usbt *u = (usbt *)t->impl;
    if (got) *got = 0;
    if (!u->h) return PK_E_DISCONNECTED;
    if (!(ep & 0x80) || (cap && !d)) return PK_E_ARG;
    if (cap > PK_TRANSPORT_MAX_XFER) cap = PK_TRANSPORT_MAX_XFER;
    int x = 0;
    int rc = libusb_bulk_transfer(u->h, ep, d, (int)cap, &x, (unsigned)clamp_timeout(to));
    if (rc == LIBUSB_ERROR_TIMEOUT && x > 0) rc = 0;   /* bytes already received are never dropped */
    if (rc != 0) return fail(t, "bulk_in", rc);
    if (got) *got = (size_t)x;
    return PK_OK;
}

static pk_status ub_control(pk_transport *t, uint8_t rt, uint8_t req, uint16_t val, uint16_t idx, uint8_t *d,
                            size_t n, unsigned to) {
    usbt *u = (usbt *)t->impl;
    if (!u->h) return PK_E_DISCONNECTED;
    if ((n && !d) || n > 0xFFFF) return PK_E_ARG;   /* also within PK_TRANSPORT_MAX_XFER */
    int rc = libusb_control_transfer(u->h, rt, req, val, idx, d, (uint16_t)n, (unsigned)clamp_timeout(to));
    if (rc < 0) return fail(t, "control", rc);
    if ((size_t)rc != n) {
        snprintf(t->diag, sizeof t->diag, "control: short transfer, %d of %zu bytes", rc, n);
        return PK_E_TRANSPORT;
    }
    return PK_OK;
}

static pk_status ub_stream(pk_transport *t, uint8_t *buf, size_t cap, size_t *got, unsigned to) {
    usbt *u = (usbt *)t->impl;
    if (got) *got = 0;
    if (!u->h) return PK_E_DISCONNECTED;
    if (cap && !buf) return PK_E_ARG;
    if (cap > PK_TRANSPORT_MAX_XFER) cap = PK_TRANSPORT_MAX_XFER;
    int x = 0;
    int rc = libusb_bulk_transfer(u->h, STREAM_EP, buf, (int)cap, &x, (unsigned)clamp_timeout(to));
    if (rc == LIBUSB_ERROR_TIMEOUT && x > 0) rc = 0;   /* bytes already received are never dropped */
    if (rc == LIBUSB_ERROR_OVERFLOW) {
        snprintf(t->sdiag, sizeof t->sdiag, "stream_read: device overflow");
        return PK_E_STREAM_OVERFLOW;
    }
    if (rc != 0) return fail_s(t, "stream_read", rc);   /* a timeout is PK_E_TIMEOUT; the caller polls again */
    if (got) *got = (size_t)x;
    return PK_OK;
}

/* Configuration 1, interface 0. Takes ownership of h (closed on failure). */
static pk_status setup_handle(pk_transport *t, libusb_device_handle *h) {
    int rc = libusb_set_auto_detach_kernel_driver(h, 1);
    if (rc != 0 && rc != LIBUSB_ERROR_NOT_SUPPORTED) { libusb_close(h); return fail(t, "auto_detach", rc); }
    int cfg = 0;
    rc = libusb_get_configuration(h, &cfg);
    if (rc != 0) { libusb_close(h); return fail(t, "get_configuration", rc); }
    if (cfg != 1) {
        rc = libusb_set_configuration(h, 1);
        if (rc != 0) { libusb_close(h); return fail(t, "set_configuration", rc); }
    }
    rc = libusb_claim_interface(h, 0);
    if (rc != 0) { libusb_close(h); return fail(t, "claim_interface", rc); }
    ((usbt *)t->impl)->h = h;
    return PK_OK;
}

static void release(usbt *u) {
    if (!u->h) return;
    libusb_release_interface(u->h, 0);
    libusb_close(u->h);
    u->h = NULL;
}

static pk_status ub_reopen(pk_transport *t, uint16_t vid, uint16_t pid, unsigned wait_ms) {
    usbt *u = (usbt *)t->impl;
    release(u);
    struct timespec t0;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    pk_status last = PK_E_TIMEOUT;
    for (;;) {
        libusb_device **list = NULL;
        ssize_t n = libusb_get_device_list(u->ctx, &list);
        if (n < 0) return fail(t, "get_device_list", (int)n);
        libusb_device *pick = NULL;
        for (ssize_t i = 0; i < n; i++) {   /* prefer the old bus when several match */
            struct libusb_device_descriptor dd;
            if (libusb_get_device_descriptor(list[i], &dd) != 0 || dd.idVendor != vid || dd.idProduct != pid) continue;
            if (!pick || libusb_get_bus_number(list[i]) == u->bus) pick = list[i];
        }
        pk_status s = PK_E_TIMEOUT;
        if (pick) {
            last = PK_E_TIMEOUT;
            libusb_device_handle *h = NULL;
            int rc = libusb_open(pick, &h);
            if (rc == 0) {
                u->bus = libusb_get_bus_number(pick);
                s = setup_handle(t, h);
            } else {
                s = fail(t, "open", rc);
            }
            libusb_free_device_list(list, 1);
            if (s == PK_OK) return s;
            last = s;   /* a device that is still settling (any open or setup error) is retried until wait_ms */
        } else {
            libusb_free_device_list(list, 1);
        }
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        long long waited = (long long)(now.tv_sec - t0.tv_sec) * 1000 + (now.tv_nsec - t0.tv_nsec) / 1000000;   /* wall clock, open/setup time included */
        if (waited >= (long long)wait_ms) {
            snprintf(t->diag, sizeof t->diag, "reopen: %04x:%04x not usable within %u ms (last: %s)", vid, pid, wait_ms,
                     pk_status_str(last));
            return last;
        }
        struct timespec ts = { 0, 100 * 1000000L };
        nanosleep(&ts, NULL);
    }
}

static void ub_close(pk_transport *t) {
    usbt *u = (usbt *)t->impl;
    if (!u) return;
    release(u);
    if (u->ctx) libusb_exit(u->ctx);
    free(u);
    t->impl = NULL;
}

static const pk_transport_ops USB_OPS = { ub_bulk_out, ub_bulk_in, ub_control, ub_stream, ub_reopen, ub_close };

static int libusb_read_serial(libusb_device *dev, const struct libusb_device_descriptor *dd, char out[32]) {
    out[0] = 0;
    if (!dd->iSerialNumber) return 0;
    libusb_device_handle *h = NULL;
    int rc = libusb_open(dev, &h);
    if (rc != 0) return rc;
    unsigned char b[32];
    int n = libusb_get_string_descriptor_ascii(h, dd->iSerialNumber, b, (int)sizeof b - 1);
    if (n > 0) { memcpy(out, b, (size_t)n); out[n] = 0; }
    libusb_close(h);
    return n < 0 ? n : 0;
}

/* TODO(Task 6): replace with the models.def table. Spec "device classes": bare 04B4:8613 and 0547:1002, and every
 * Pakon-vendor (0F05) device (unloaded F235, loaded F135 / 35F2 / F335). */
static int is_pakon_id(uint16_t vid, uint16_t pid) {
    return (vid == 0x04B4 && pid == 0x8613) || (vid == 0x0547 && pid == 0x1002) || vid == 0x0F05;
}

static void fill_info(libusb_device *dev, const struct libusb_device_descriptor *dd, pk_usb_info *o) {
    memset(o, 0, sizeof *o);
    o->vid = dd->idVendor; o->pid = dd->idProduct; o->rev = dd->bcdDevice;
    o->bus = libusb_get_bus_number(dev); o->addr = libusb_get_device_address(dev);
}

pk_status pk_usb_list(pk_usb_info *out, size_t cap, size_t *n) {
    if (n) *n = 0;
    if (!n || (cap && !out)) return PK_E_ARG;
    libusb_context *ctx = NULL;
    int rc = libusb_init(&ctx);
    if (rc != 0) return pk_usb_map_error(rc);
    libusb_device **list = NULL;
    ssize_t cnt = libusb_get_device_list(ctx, &list);
    if (cnt < 0) { libusb_exit(ctx); return pk_usb_map_error((int)cnt); }
    for (ssize_t i = 0; i < cnt && *n < cap; i++) {   /* descriptors are cached by the OS: nothing is opened */
        struct libusb_device_descriptor dd;
        if (libusb_get_device_descriptor(list[i], &dd) != 0 || !is_pakon_id(dd.idVendor, dd.idProduct)) continue;
        fill_info(list[i], &dd, &out[(*n)++]);
    }
    libusb_free_device_list(list, 1);
    libusb_exit(ctx);
    return PK_OK;
}

pk_status pk_usb_read_serial(const pk_usb_info *which, char serial[32]) {
    if (serial) serial[0] = 0;
    if (!which || !serial) return PK_E_ARG;
    if (!is_pakon_id(which->vid, which->pid)) return PK_E_ARG;
    libusb_context *ctx = NULL;
    int rc = libusb_init(&ctx);
    if (rc != 0) return pk_usb_map_error(rc);
    libusb_device **list = NULL;
    ssize_t cnt = libusb_get_device_list(ctx, &list);
    pk_status s = cnt < 0 ? pk_usb_map_error((int)cnt) : PK_E_NOT_FOUND;
    for (ssize_t i = 0; i < cnt; i++) {
        struct libusb_device_descriptor dd;
        if (libusb_get_device_descriptor(list[i], &dd) != 0) continue;
        if (dd.idVendor != which->vid || dd.idProduct != which->pid) continue;
        if (libusb_get_bus_number(list[i]) != which->bus || libusb_get_device_address(list[i]) != which->addr) continue;
        s = pk_usb_map_error(libusb_read_serial(list[i], &dd, serial));
        break;
    }
    if (cnt >= 0) libusb_free_device_list(list, 1);
    libusb_exit(ctx);
    return s;
}

pk_status pk_usb_open(const pk_usb_info *which, pk_transport **out) {
    if (out) *out = NULL;
    if (!which || !out) return PK_E_ARG;
    pk_transport *t = (pk_transport *)calloc(1, sizeof *t);
    usbt *u = (usbt *)calloc(1, sizeof *u);
    if (!t || !u) { free(t); free(u); return PK_E_NOMEM; }
    t->ops = &USB_OPS;
    t->impl = u;
    int rc = libusb_init(&u->ctx);
    if (rc != 0) { u->ctx = NULL; pk_status s = fail(t, "init", rc); pk_transport_close(t); return s; }
    libusb_device **list = NULL;
    ssize_t cnt = libusb_get_device_list(u->ctx, &list);
    pk_status s = PK_E_NOT_FOUND;
    if (cnt < 0) s = fail(t, "get_device_list", (int)cnt);
    for (ssize_t i = 0; i < cnt; i++) {
        struct libusb_device_descriptor dd;
        if (libusb_get_device_descriptor(list[i], &dd) != 0) continue;
        if (dd.idVendor != which->vid || dd.idProduct != which->pid) continue;
        if (libusb_get_bus_number(list[i]) != which->bus || libusb_get_device_address(list[i]) != which->addr) continue;
        libusb_device_handle *h = NULL;
        rc = libusb_open(list[i], &h);
        if (rc != 0) { s = fail(t, "open", rc); break; }
        u->bus = which->bus;
        s = setup_handle(t, h);
        break;
    }
    if (cnt >= 0) libusb_free_device_list(list, 1);
    if (s == PK_E_NOT_FOUND) snprintf(t->diag, sizeof t->diag, "no device %04x:%04x at bus %u address %u",
                                      which->vid, which->pid, which->bus, which->addr);
    if (s != PK_OK) { pk_transport_close(t); return s; }
    s = pkt_seal(t, out);
    if (s != PK_OK) pk_transport_close(t);
    return s;
}

#endif
