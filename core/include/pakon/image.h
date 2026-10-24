#ifndef PAKON_IMAGE_H
#define PAKON_IMAGE_H
/* A parsed Intel-HEX image (FX2 firmware or the stage-1 copier). Declared here, not in device.h, because the write
 * guard (link, Task 4) must read images before the device module (Task 6) exists; device.h includes this header and
 * must not declare pk_image again. Heap-allocated by the parser (pk_ihex_parse, Task 6). */
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t mem[0x10000];
    uint8_t used[0x10000 / 8];   /* bit (a & 7) of used[a >> 3], least significant bit first: 1 = byte a is set by a record */
    uint32_t min_addr, max_addr;
    size_t nbytes;
} pk_image;

#define PK_IMAGE_USED(img, a) ((((img)->used[(a) >> 3]) >> ((a) & 7)) & 1u)

#endif
