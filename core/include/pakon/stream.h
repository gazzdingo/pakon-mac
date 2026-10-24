#ifndef PAKON_STREAM_H
#define PAKON_STREAM_H
/* Scan-stream capture (EP 0x86 -> ring -> raw file) and the roll sidecar (<roll>.json, format_version 1).
 *
 * Threads: a reader polls pk_transport.stream_read into a ring; a writer drains the ring into raw_path. The reader checks
 * line sync inline (a line starts with a 16-bit little-endian word whose bit 0 is 1; the first one is searched for, see below) and stops on the first fatal
 * condition (PK_E_LOST_SYNC, PK_E_STREAM_OVERFLOW from the ring or the device, any other transport error). Nothing is
 * dropped silently: the writer still flushes everything captured before the fatal status is returned. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"
#include "pakon/transport.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct pk_stream pk_stream;
/* Called on the reader thread for every complete line, in order, once the line grid is synced (Task 13: TLB's film start / end test reads the line). `segment` counts
 * the sync restarts (0 at start, +1 for each pk_stream_rearm_sync the reader has taken); `line` is the line's index over the whole stream, counting like pk_stream_poll's
 * lines; `byte_offset` is where it starts in the raw file; `data` is words_per_line x 2 bytes, valid only during the call. It must be quick and must not call the stream. */
typedef void (*pk_stream_line_cb)(void *user, unsigned segment, uint64_t line, uint64_t byte_offset, const uint8_t *data);
typedef struct {
    size_t ring_bytes;          /* 0 = 120 MB (4 s at 30 MB/s) */
    unsigned words_per_line;    /* pk_words_per_line(); required */
    const char *raw_path;       /* NULL discards the data (counts and sync checks still run) */
    unsigned read_timeout_ms;   /* stream_read poll interval; 0 = 100 */
    pk_stream_line_cb line_cb;  /* NULL = none */
    void *line_user;
    /* Segment 0 only: words dropped before the first-sync search begins (they count as lead and stay in the raw file). The scan passes
     * PK_STREAM_STRIP0_SKIP_WORDS: TLB's scan thread searches strip 0 from the third ring packet (RE 30 sec 2.2.1). 0 = search from the first word. */
    unsigned first_skip_words;
    /* TLB's calibration reader FUN_1001d170 (RE 43 sec 2 notes): the line-start search has no window, and a line start without bit 0 is not an error, the
     * search simply starts again there (0x1001d2b0). PK_E_LOST_SYNC is then never returned. false = the scan thread's rules (window, fixed grid). */
    bool resync;
} pk_stream_cfg;
/* Two driver ring packets of 0x5000 bytes (TLB cfg+0x1600, constructor default FUN_10010b60 0x10010c3f): strip 0's first-sync search starts after them. */
#define PK_STREAM_STRIP0_SKIP_WORDS 20480u

pk_status pk_stream_start(pk_transport *t, const pk_stream_cfg *cfg, pk_stream **out);
/* PK_OK while healthy; the first fatal error otherwise. bytes / lines may be NULL. The raw file may still be
 * flushing: only pk_stream_stop guarantees it holds everything captured. */
pk_status pk_stream_poll(pk_stream *s, uint64_t *bytes, uint64_t *lines);
/* Stops the reader, flushes and closes the raw file, joins. Returns the first fatal error seen, else PK_OK. Idempotent. */
pk_status pk_stream_stop(pk_stream *s, uint64_t *total_bytes);
/* Words of an incomplete final line (0 when the stream ended on a line boundary). Meaningful after stop. */
unsigned pk_stream_tail_words(const pk_stream *s);
/* First-sync search (RE 30 section 2.2.1, ruling S-R28). The stream does NOT start on a line boundary: from capture
 * start (after cfg first_skip_words, segment 0 only) the reader searches up to 10240 words (TLB's default window, 0x5000 bytes) for the first word with bit 0 set
 * (resync mode: without a window, and again after any line start that lacks bit 0);
 * that word starts line 0, and only after it is every line start checked at exactly words_per_line. No such word in the
 * window is PK_E_LOST_SYNC, with pk_stream_diag saying the first sync was not found (a later loss says so too). The
 * skipped words stay in the raw file (it holds every byte received); lines and tail words count from the first line
 * start. This returns the words that belong to no line: those skipped by searches (including a search that never finished, up to
 * the window), plus a partial line left at a re-arm. Words stay on the stream's own word grid: a re-arm at an odd byte
 * count counts the stray byte as lead and searches from the next word. */
uint64_t pk_stream_lead_words(const pk_stream *s);
/* The first synced line of segment `segment` (0 = the first search; +1 per pk_stream_rearm_sync the reader has taken): its byte offset in the raw file and its line index
 * (counting like pk_stream_poll's lines). This is where TLB's per-strip loop head initialises the kernel and from which it feeds EVERY synced line (Task 20 fix round 2,
 * ruling S-R44). PK_E_NOT_FOUND until that segment has found its first line start. */
pk_status pk_stream_segment_start(const pk_stream *, unsigned segment, uint64_t *byte_offset, uint64_t *line);
/* TLB restarts the search for every strip: after this call the next words received are searched again within the
 * window and the line grid restarts at the new first line start (RE 30 section 2.2.1). Safe to call from another thread
 * while the reader runs; takes effect at the reader's next chunk. Task 13 calls it at each strip start. */
pk_status pk_stream_rearm_sync(pk_stream *s);
/* Copies the text describing the first fatal error that has one (sync or overflow; "" if none) into buf. It always
 * describes the same error pk_stream_poll / pk_stream_stop return. */
void pk_stream_diag(const pk_stream *s, char *buf, size_t cap);
void pk_stream_free(pk_stream *s);   /* stops first if still running */

/* ---- roll sidecar ---- */
typedef struct pk_sidecar pk_sidecar;
#define PK_SIDECAR_VERSION 1

pk_sidecar *pk_sidecar_new(void);   /* format_version already set */
void pk_sidecar_free(pk_sidecar *sc);
/* Setting an existing key replaces it; keys keep their first-set order. A NULL string writes JSON null. */
pk_status pk_sidecar_set_str(pk_sidecar *sc, const char *key, const char *val);
pk_status pk_sidecar_set_int(pk_sidecar *sc, const char *key, long long val);
pk_status pk_sidecar_set_bool(pk_sidecar *sc, const char *key, bool val);
/* An object or list value (scan_config, calibration_ids, ...); PK_E_ARG if json_text does not parse. */
pk_status pk_sidecar_set_json(pk_sidecar *sc, const char *key, const char *json_text);
pk_status pk_sidecar_add_event(pk_sidecar *sc, const char *text);
pk_status pk_sidecar_add_strip_json(pk_sidecar *sc, const char *json_object);   /* PK_E_ARG unless an object */
/* Task 13: strip `index` becomes json_object (a replace when it exists, an append when index == the strip count; PK_E_ARG beyond). Used for the strip in progress, which is rewritten at
 * every flush until it ends. */
pk_status pk_sidecar_set_strip_json(pk_sidecar *sc, size_t index, const char *json_object);
void pk_sidecar_truncate_strips(pk_sidecar *sc, size_t n);   /* keeps the first n strips */
const char *pk_sidecar_get_str(const pk_sidecar *sc, const char *key);
long long pk_sidecar_get_int(const pk_sidecar *sc, const char *key, long long dflt);
bool pk_sidecar_get_bool(const pk_sidecar *sc, const char *key, bool dflt);
/* The whole sidecar as a DOM (for arrays such as strips); valid until the next change or free. */
const struct pku_json *pk_sidecar_json(const pk_sidecar *sc);
pk_status pk_sidecar_write(const pk_sidecar *sc, const char *path);   /* atomic */
/* PK_E_NOT_FOUND / PK_E_IO from the file, PK_E_CORRUPT for truncated or malformed text, PK_E_FORMAT for another format_version. */
pk_status pk_sidecar_read(const char *path, pk_sidecar **out);

#ifdef __cplusplus
}
#endif
#endif
