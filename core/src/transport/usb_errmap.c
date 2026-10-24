#include "pakon/transport.h"

/* libusb_error values are part of libusb's stable ABI; usb.c asserts them against the real header, so this file
 * (which builds with or without libusb) needs no libusb include. */
enum { E_IO = -1, E_ACCESS = -3, E_NO_DEVICE = -4, E_NOT_FOUND = -5, E_BUSY = -6, E_TIMEOUT = -7, E_OVERFLOW = -8,
       E_PIPE = -9, E_NO_MEM = -11 };

pk_status pk_usb_map_error(int e) {
    switch (e) {
    case 0: return PK_OK;
    case E_TIMEOUT: return PK_E_TIMEOUT;
    case E_NO_DEVICE: return PK_E_DISCONNECTED;
    case E_NO_MEM: return PK_E_NOMEM;
    case E_PIPE: case E_ACCESS: case E_BUSY: case E_IO: case E_OVERFLOW: case E_NOT_FOUND:
    default: return PK_E_TRANSPORT;
    }
}
