#ifndef PAKON_STATUS_H
#define PAKON_STATUS_H

/* Values are stable (appended only). */
typedef enum {
    PK_OK = 0,
    PK_E_NOMEM,
    PK_E_IO,
    PK_E_VENDOR_DATA,
    PK_E_FORMAT,
    PK_E_IMAGE_TOO_SMALL,
    PK_E_ARG,
    PK_E_UNSUPPORTED,     /* 7: a Kodak path the port has not reproduced yet (e.g. a Preference mode other than 0) */
    PK_E_ANALYSIS,        /* 8: Kodak's own roll analysis failed for this frame's batch (PIAnselAnalyzeRoll returned 0) */
    /* scanner core (values 9.. appended) */
    PK_E_TRANSPORT,       /* 9: USB / transport I/O failed */
    PK_E_TIMEOUT,         /* a transfer or a board reply timed out */
    PK_E_PROTOCOL,        /* a malformed or unexpected board packet */
    PK_E_DEVICE,          /* the scanner reported an error */
    PK_E_DISCONNECTED,    /* the scanner went away */
    PK_E_FIRMWARE_WEDGED, /* the FX2 firmware needs a power cycle */
    PK_E_FIRMWARE_MISMATCH,
    PK_E_STREAM_OVERFLOW, /* the scan stream ring overflowed */
    PK_E_LOST_SYNC,       /* line sync lost in the scan stream */
    PK_E_LAMP_WARMUP,     /* the lamp is not warm yet */
    PK_E_VENDOR_MISSING,  /* an imported Kodak file is missing */
    PK_E_WRITE_FORBIDDEN, /* the write guard refused a scanner-memory write */
    PK_E_BUSY,            /* the session state does not allow this call */
    PK_E_CAL_LIGHT,       /* calibration: light level out of range */
    PK_E_NO_FILM,         /* no film in the gate */
    PK_E_CAL_FOREIGN,     /* calibration data belongs to another scanner */
    PK_E_REPLAY_MISMATCH, /* a replayed trace diverged from the request */
    PK_E_CANCELLED,       /* cancelled by the caller */
    PK_E_NOT_FOUND,       /* a file or record does not exist */
    PK_E_CORRUPT,         /* data failed validation */
    PK_E_LOADED_UNVERIFIED, /* the firmware is loaded and the device re-enumerated, but the boot-EEPROM personality could not be read */
    PK_E_FILM_IN_GUIDES,  /* film is over the entry or exit sensor at scan start (TLB EC_FilmInGuides 0x81) */
    PK_E__COUNT           /* not a status */
} pk_status;

typedef enum {
    PK_CAT_NONE, PK_CAT_ARG, PK_CAT_TRANSPORT, PK_CAT_PROTOCOL, PK_CAT_DEVICE, PK_CAT_FILM, PK_CAT_VENDOR,
    PK_CAT_CALIBRATION, PK_CAT_IO, PK_CAT_COLOUR
} pk_category;

/* A stable name for a status ("PK_E_UNSUPPORTED", ...; "PK_E_?" for a value outside the enum). */
static inline const char *pk_status_str(pk_status s) {
    static const char *const name[] = {
        "PK_OK", "PK_E_NOMEM", "PK_E_IO", "PK_E_VENDOR_DATA", "PK_E_FORMAT", "PK_E_IMAGE_TOO_SMALL", "PK_E_ARG",
        "PK_E_UNSUPPORTED", "PK_E_ANALYSIS", "PK_E_TRANSPORT", "PK_E_TIMEOUT", "PK_E_PROTOCOL", "PK_E_DEVICE",
        "PK_E_DISCONNECTED", "PK_E_FIRMWARE_WEDGED", "PK_E_FIRMWARE_MISMATCH", "PK_E_STREAM_OVERFLOW", "PK_E_LOST_SYNC",
        "PK_E_LAMP_WARMUP", "PK_E_VENDOR_MISSING", "PK_E_WRITE_FORBIDDEN", "PK_E_BUSY", "PK_E_CAL_LIGHT", "PK_E_NO_FILM",
        "PK_E_CAL_FOREIGN", "PK_E_REPLAY_MISMATCH", "PK_E_CANCELLED", "PK_E_NOT_FOUND", "PK_E_CORRUPT", "PK_E_LOADED_UNVERIFIED", "PK_E_FILM_IN_GUIDES" };
    return (unsigned)s < (unsigned)PK_E__COUNT ? name[s] : "PK_E_?";
}

/* The user-facing category of a status. */
static inline pk_category pk_status_category(pk_status s) {
    switch (s) {
    case PK_E_NOMEM: case PK_E_IO: case PK_E_NOT_FOUND: case PK_E_CORRUPT: return PK_CAT_IO;
    case PK_E_VENDOR_DATA: case PK_E_VENDOR_MISSING: return PK_CAT_VENDOR;
    case PK_E_FORMAT: case PK_E_ARG: case PK_E_UNSUPPORTED: return PK_CAT_ARG;
    case PK_E_IMAGE_TOO_SMALL: case PK_E_ANALYSIS: return PK_CAT_COLOUR;
    case PK_E_TRANSPORT: case PK_E_TIMEOUT: case PK_E_DISCONNECTED: case PK_E_FIRMWARE_WEDGED:
    case PK_E_REPLAY_MISMATCH: return PK_CAT_TRANSPORT;
    case PK_E_PROTOCOL: case PK_E_WRITE_FORBIDDEN: return PK_CAT_PROTOCOL;
    case PK_E_DEVICE: case PK_E_FIRMWARE_MISMATCH: case PK_E_LOADED_UNVERIFIED: case PK_E_LAMP_WARMUP: case PK_E_BUSY: case PK_E_CANCELLED:
        return PK_CAT_DEVICE;
    case PK_E_STREAM_OVERFLOW: case PK_E_LOST_SYNC: case PK_E_NO_FILM: case PK_E_FILM_IN_GUIDES: return PK_CAT_FILM;
    case PK_E_CAL_LIGHT: case PK_E_CAL_FOREIGN: return PK_CAT_CALIBRATION;
    default: return PK_CAT_NONE;
    }
}

#endif
