#ifndef PAKON_TRANSPORT_H
#define PAKON_TRANSPORT_H
/* The transport seam: everything below it (usb, record, replay) moves bytes; everything above it is hardware-free.
 *
 * Never-write rule: no transport implementation filters or interprets transfers. The write guard (link.h,
 * pk_transport_guard_open) is the single door. pk_usb_open, pk_transport_record_open and pk_transport_replay_open each
 * return a guard-wrapped transport (ruling C4; the seam is pkt_seal() in src/transport/trace.h): the raw transport
 * pointer lives only in the guard's private state, so `impl` of a returned transport is the guard's, and no caller
 * holds a raw one. When the recorder is opened over a guarded transport it is spliced UNDER the guard (the guard stays
 * outermost, so one load window and one A4 state sit above everything, and the trace holds exactly what the guard let
 * through). A refused transfer returns PK_E_WRITE_FORBIDDEN, reaches nothing below and is not recorded. Open the recorder before
 * any stream_read thread starts: splicing it in swaps the guard's inner pointer and is not synchronised with a running reader. */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_transport pk_transport;

/* Largest single transfer (bytes) any transport accepts or returns; larger requests are PK_E_ARG (writes) or are
 * clamped (reads). This is also the trace format's per-event limit.
 *
 * Threading: calls are not re-entrant, with one exception. stream_read may run on one thread while ONE other
 * thread uses bulk_out, bulk_in or control. reopen and close must not run concurrently with anything (stop the
 * stream reader first). `diag` is written only by the link ops (bulk_out, bulk_in, control, reopen) and `sdiag`
 * only by stream_read, so each thread reads its own buffer without a race; a PK_E_TIMEOUT from stream_read is
 * an idle poll and writes no diagnostic.
 *
 * Timeouts: timeout_ms is passed to libusb as is (0 = wait without limit on USB). A bulk_in or stream_read that
 * times out after receiving bytes returns PK_OK with the short count; PK_E_TIMEOUT means nothing was received.
 *
 * Recording: idle stream polls that time out are NOT recorded in a trace (replay answers PK_E_TIMEOUT once the
 * recorded stream events run out). If any trace write fails, the recorder latches: nothing more is written, every
 * later call still reaches the device but returns PK_E_IO, a FAILED marker is left in the trace directory, and
 * replay refuses such a trace with PK_E_CORRUPT.
 *
 * Why the recorder keeps passing calls through after it has failed: a recording problem (disk full, a deleted
 * directory) must never change what the scanner does. The calls that matter most after a failure are the cleanup ones
 * (stop the film, lamp off, session_leave); refusing them would leave the lamp on or the film moving. So the device
 * still gets every call, and the PK_E_IO tells the caller to abort the run, which it does through those same cleanup
 * calls. The cost is a status that misreports some device effects: a call that succeeded on the device returns
 * PK_E_IO, and the data read in that call is still delivered through *got. */
#define PK_TRANSPORT_MAX_XFER ((size_t)1 << 24)

typedef struct pk_transport_ops {
    pk_status (*bulk_out)(pk_transport *, uint8_t ep, const uint8_t *, size_t, unsigned timeout_ms);
    /* *got is the byte count received (0 on failure). */
    pk_status (*bulk_in)(pk_transport *, uint8_t ep, uint8_t *, size_t cap, size_t *got, unsigned timeout_ms);
    /* req_type bit 7 = device-to-host. A device-to-host transfer must fill exactly len bytes. */
    pk_status (*control)(pk_transport *, uint8_t req_type, uint8_t req, uint16_t val, uint16_t idx,
                         uint8_t *data, size_t len, unsigned timeout_ms);
    /* Bulk read on EP 0x86; a short read is normal; a device overflow is PK_E_STREAM_OVERFLOW. */
    pk_status (*stream_read)(pk_transport *, uint8_t *buf, size_t cap, size_t *got, unsigned timeout_ms);
    /* After the device re-enumerates. Must not run concurrently with other calls. */
    pk_status (*reopen)(pk_transport *, uint16_t vid, uint16_t pid, unsigned wait_ms);
    void (*close)(pk_transport *);   /* releases impl; does not free the pk_transport itself */
} pk_transport_ops;

struct pk_transport {
    const pk_transport_ops *ops;
    void *impl;
    char diag[256];   /* detail of the last link-op failure (replay: the byte diff) */
    char sdiag[128];  /* detail of the last stream_read failure (not timeouts) */
};

typedef struct {
    char model[24];
    char fw_sha256[4][65];
    int n_fw;
    char host_os[32];
    char libpakon_version[24];
} pk_trace_meta;

enum { PK_REPLAY_REALTIME = 1 };

/* Takes ownership of inner on success (closing the result closes inner); on failure inner stays the caller's.
 * Writes <trace_dir>/{meta.json,events.jsonl,stream.bin}; refuses (PK_E_ARG) a directory that already holds a trace. */
pk_status pk_transport_record_open(pk_transport *inner, const char *trace_dir, const pk_trace_meta *meta,
                                   pk_transport **out);
/* PK_E_CORRUPT for a truncated, oversized or wrong-version trace; PK_E_NOT_FOUND if events.jsonl/meta.json is absent. */
pk_status pk_transport_replay_open(const char *trace_dir, unsigned flags, pk_transport **out);
void pk_transport_close(pk_transport *);   /* ops->close, then frees */

static inline pk_status pk_t_bulk_out(pk_transport *t, uint8_t ep, const uint8_t *d, size_t n, unsigned to) {
    return t->ops->bulk_out(t, ep, d, n, to);
}
static inline pk_status pk_t_bulk_in(pk_transport *t, uint8_t ep, uint8_t *d, size_t cap, size_t *got, unsigned to) {
    return t->ops->bulk_in(t, ep, d, cap, got, to);
}
static inline pk_status pk_t_control(pk_transport *t, uint8_t rt, uint8_t req, uint16_t val, uint16_t idx,
                                     uint8_t *d, size_t n, unsigned to) {
    return t->ops->control(t, rt, req, val, idx, d, n, to);
}
static inline pk_status pk_t_stream_read(pk_transport *t, uint8_t *b, size_t cap, size_t *got, unsigned to) {
    return t->ops->stream_read(t, b, cap, got, to);
}
static inline pk_status pk_t_reopen(pk_transport *t, uint16_t vid, uint16_t pid, unsigned wait_ms) {
    return t->ops->reopen(t, vid, pid, wait_ms);
}

/* USB backend (libusb 1.0, linked dynamically; PK_E_UNSUPPORTED from list/open when built without it). */
typedef struct { uint16_t vid, pid, rev; uint8_t bus, addr; char serial[32]; } pk_usb_info;
/* Lists attached Pakon-family devices from descriptors only (no device is opened): VID:PID 04B4:8613, 0547:1002
 * and 0F05:*. Writes at most cap entries; *n = entries written. `serial` is left empty here. */
pk_status pk_usb_list(pk_usb_info *out, size_t cap, size_t *n);
pk_status pk_usb_open(const pk_usb_info *which, pk_transport **out);   /* configuration 1, interface 0 */
/* Reads the iSerialNumber string ("" if none) of one device the caller has classified as a Pakon: opens it, sends a
 * string-descriptor request, closes it. Never call it on a device that a session holds open. */
pk_status pk_usb_read_serial(const pk_usb_info *which, char serial[32]);
pk_status pk_usb_map_error(int libusb_error);                          /* pure */

#ifdef __cplusplus
}
#endif
#endif
