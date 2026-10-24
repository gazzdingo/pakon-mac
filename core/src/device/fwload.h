#ifndef PAKON_DEVICE_FWLOAD_H
#define PAKON_DEVICE_FWLOAD_H
/* Internal pieces of the firmware load (fwload.c). The public entry points are pk_device_load_firmware and
 * pk_device_personality in pakon/device.h. */
#include "pakon/device.h"

#define PKFW_CPUCS 0xE600u        /* hold 0x01, release 0x00 (Kodak FX35Loader Ezusb_8051Reset; the guard allows only these) */
#define PKFW_EXT_START 0x4000u    /* internal RAM ends here; A0 reads and writes stay below it */
#define PKFW_EXT_END 0xE000u      /* no load transfer reaches this address or above */
#define PKFW_A3_MIN_EXCL 0x1B3Fu  /* Kodak's MAX_INTERNAL_ADDRESS: records above it go by A3, the rest by A0 */
#define PKFW_REC_MAX 16u          /* Kodak's MAX_INTEL_HEX_RECORD_LENGTH */

/* Kodak's stage-1 inside F235Ldr.sys (sha 785bd29f...): INTEL_HEX_RECORD array at file offset 0x1700, 22-byte stride
 * (len, pad, addr LE, type, 16 data bytes, pad), 360 data records, then the EOF record (to 0x3606). */
#define PKFW_LDR_OFF 0x1700u
#define PKFW_LDR_STRIDE 22u
#define PKFW_LDR_NREC 360u
/* Cuts the stage-1 out of an F235Ldr.sys image: its bytes as an image plus the records in array order (free() them). PK_E_CORRUPT on
 * any deviation from that layout. It does NOT check the pin: the callers compare pkl_image_canon_hex with PKL_STAGE1_CANON_SHA256. */
pk_status pkfw_stage1_from_ldr(const uint8_t *sys, size_t n, pk_image **img, pk_ihex_rec **recs, size_t *nrecs);

/* Boot-EEPROM identity the unloaded device enumerates with (and its EEPROM personality repeats): 0F05:F235. */
#define PKFW_BOOT_VID 0x0F05
#define PKFW_BOOT_PID 0xF235

#endif
