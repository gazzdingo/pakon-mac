#ifndef PAKON_STREAM_RING_H
#define PAKON_STREAM_RING_H
/* Single-producer / single-consumer byte ring between the stream reader and writer threads (mutex + condvar, no global
 * state). A full ring never blocks the producer: the surplus is refused and the sticky overflow flag is set. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct pk_ring pk_ring;

pk_ring *pkr_new(size_t cap);                     /* NULL on allocation failure or cap 0 */
void pkr_free(pk_ring *r);
size_t pkr_write(pk_ring *r, const uint8_t *data, size_t n);   /* bytes accepted; fewer than n sets the overflow flag */
/* Waits up to wait_ms for data; returns the bytes copied (0 on timeout, or once closed and drained). */
size_t pkr_read(pk_ring *r, uint8_t *out, size_t cap, unsigned wait_ms);
void pkr_close(pk_ring *r);                       /* no more writes: wakes the reader */
bool pkr_drained(pk_ring *r);                     /* closed and empty */
bool pkr_overflowed(const pk_ring *r);

#endif
