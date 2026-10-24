/* Session events (Task 12): built here, delivered on the worker thread to the caller's callback with no session lock held. */
#include <stdio.h>
#include <string.h>
#include "session/session_internal.h"

void pks_emit(pk_session *s, const pk_event *e) {
    if (s->cb) s->cb(s->cb_user, e);
}

void pks_emit_state(pk_session *s, pk_state st) {
    pk_event e;
    memset(&e, 0, sizeof e);
    e.kind = PK_EV_STATE;
    e.state = st;
    pks_emit(s, &e);
}

void pks_emit_msg(pk_session *s, pk_event_kind kind, pk_status st, uint32_t code, const char *fmt, ...) {
    pk_event e;
    memset(&e, 0, sizeof e);
    e.kind = kind;
    e.state = pks_state(s);
    e.status = st;
    e.code = code;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(e.text, sizeof e.text, fmt, ap);
    va_end(ap);
    pks_emit(s, &e);
}

void pks_emit_progress(pk_session *s, int percent) {
    pk_event e;
    memset(&e, 0, sizeof e);
    e.kind = PK_EV_WARMUP_PROGRESS;
    e.state = pks_state(s);
    e.percent = percent;
    pks_emit(s, &e);
}
