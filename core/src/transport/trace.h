#ifndef PAKON_TRANSPORT_TRACE_H
#define PAKON_TRANSPORT_TRACE_H
/* .ptrace on-disk format (internal, pkt_ prefix). */
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include "pakon/transport.h"

#define PKT_FORMAT_VERSION 1
#define PKT_MAX_LEN ((size_t)1 << 24)

typedef enum { PKT_BULK_OUT, PKT_BULK_IN, PKT_CONTROL, PKT_STREAM, PKT_REOPEN } pkt_op;

typedef struct {
    size_t seq;          /* position in events.jsonl (0-based) */
    uint64_t t_us;
    int kind;            /* pkt_op */
    char op[12];         /* "bulk_out" is 8 characters, so 12 rather than the brief's 8 */
    int ep, req, rt, val, idx;   /* -1 when the op does not carry the field; reopen: val = vid, idx = pid */
    size_t len;
    int status;          /* pk_status */
    uint8_t *data;       /* malloc'd, len bytes, or NULL */
    char sha[65];        /* hex SHA-256 of the payload, "" when data is carried */
    size_t off;          /* stream events: offset into stream.bin */
} pkt_event;

const char *pkt_op_name(int kind);
/* Loads and validates <dir>/events.jsonl. stream.bin is not read: it is opened read-only (*stream_fd, -1 if absent)
 * and its size (fstat) is the bound for every stream event, so a multi-GB stream costs no memory; read it with
 * pkt_stream_read. A FAILED marker file (an incomplete recording) gives PK_E_CORRUPT. PK_E_NOT_FOUND if
 * events.jsonl is absent; PK_E_CORRUPT for any malformed line, bad field, oversize len or out-of-range stream ref. */
pk_status pkt_load(const char *dir, pkt_event **events, size_t *n, int *stream_fd, uint64_t *stream_size);
/* pread of exactly len bytes at off; PK_E_CORRUPT if the file shrank, PK_E_IO on a read error. */
pk_status pkt_stream_read(int fd, uint64_t off, uint8_t *buf, size_t len);
void pkt_free_events(pkt_event *events, size_t n);
/* One line (fields per op); PK_E_IO on a write error, PK_E_NOMEM if the base64 buffer cannot be allocated. */
pk_status pkt_write_event(FILE *f, const pkt_event *e);

/* The guard seam (ruling C4). Every opener (usb, record, replay) hands its raw transport to this and returns the
 * result: a guard that owns raw (pkl_guard_adopt, link/guard.h), so the caller never holds a raw transport again. On
 * failure raw stays the caller's. An already-guarded transport is returned as is. */
pk_status pkt_seal(pk_transport *raw, pk_transport **out);

#endif
