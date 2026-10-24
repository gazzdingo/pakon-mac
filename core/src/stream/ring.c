#define _POSIX_C_SOURCE 200809L
#include "stream/ring.h"
#include <errno.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

struct pk_ring {
    uint8_t *buf;
    size_t cap, head, count;
    bool closed, overflow;
    pthread_mutex_t mu;
    pthread_cond_t cv;
};

pk_ring *pkr_new(size_t cap) {
    if (!cap) return NULL;
    pk_ring *r = (pk_ring *)calloc(1, sizeof *r);
    if (!r) return NULL;
    r->buf = (uint8_t *)malloc(cap);
    if (!r->buf) { free(r); return NULL; }
    r->cap = cap;
    pthread_mutex_init(&r->mu, NULL);
    pthread_cond_init(&r->cv, NULL);
    return r;
}

void pkr_free(pk_ring *r) {
    if (!r) return;
    pthread_cond_destroy(&r->cv);
    pthread_mutex_destroy(&r->mu);
    free(r->buf);
    free(r);
}

size_t pkr_write(pk_ring *r, const uint8_t *data, size_t n) {
    pthread_mutex_lock(&r->mu);
    size_t room = r->cap - r->count, take = n < room ? n : room;
    if (take < n) r->overflow = true;
    size_t tail = (r->head + r->count) % r->cap, first = r->cap - tail;
    if (first > take) first = take;
    memcpy(r->buf + tail, data, first);
    memcpy(r->buf, data + first, take - first);
    r->count += take;
    pthread_cond_signal(&r->cv);
    pthread_mutex_unlock(&r->mu);
    return take;
}

size_t pkr_read(pk_ring *r, uint8_t *out, size_t cap, unsigned wait_ms) {
    pthread_mutex_lock(&r->mu);
    if (!r->count && !r->closed && wait_ms) {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_sec += wait_ms / 1000;
        ts.tv_nsec += (long)(wait_ms % 1000) * 1000000L;
        if (ts.tv_nsec >= 1000000000L) { ts.tv_sec++; ts.tv_nsec -= 1000000000L; }
        while (!r->count && !r->closed)
            if (pthread_cond_timedwait(&r->cv, &r->mu, &ts) == ETIMEDOUT) break;
    }
    size_t take = r->count < cap ? r->count : cap;
    size_t first = r->cap - r->head;
    if (first > take) first = take;
    memcpy(out, r->buf + r->head, first);
    memcpy(out + first, r->buf, take - first);
    r->head = (r->head + take) % r->cap;
    r->count -= take;
    pthread_mutex_unlock(&r->mu);
    return take;
}

void pkr_close(pk_ring *r) {
    pthread_mutex_lock(&r->mu);
    r->closed = true;
    pthread_cond_broadcast(&r->cv);
    pthread_mutex_unlock(&r->mu);
}

bool pkr_drained(pk_ring *r) {
    pthread_mutex_lock(&r->mu);
    bool d = r->closed && !r->count;
    pthread_mutex_unlock(&r->mu);
    return d;
}

bool pkr_overflowed(const pk_ring *r) {
    pk_ring *m = (pk_ring *)r;
    pthread_mutex_lock(&m->mu);
    bool o = r->overflow;
    pthread_mutex_unlock(&m->mu);
    return o;
}
