/*
 * Pakon FX2 stage-1 copier.
 *
 * WHY THIS EXISTS
 * ---------------
 * The EZ-USB FX2's hardwired boot loader (vendor request 0xA0) can only write
 * internal RAM, 0x0000-0x3FFF.  The Pakon firmware images extend to 0x47AC
 * (Pakon5/7/8) or 0x492E (PknInit), which lives in external SRAM on the Pakon
 * USB board.  Request 0xA3 (ANCHOR_LOAD_EXTERNAL) is NOT a hardware feature --
 * it must be serviced by already-running 8051 firmware -- so the boot loader
 * alone can never complete the load.  Verified on hardware: 0xA3 times out
 * against a halted CPU, and 0xA0 writes above 0x3FFF are ACKed but discarded.
 *
 * Also verified on hardware: external SRAM at 0x4000 IS present and is
 * writable by the 8051 via MOVX.
 *
 * Rather than implement a USB stack in stage 1, this avoids USB entirely:
 *
 *   1. host writes a payload chunk into an UNUSED GAP in internal RAM
 *      (the firmware images leave 0x0056-0x0FFF and 0x10BE-0x1FFF empty)
 *   2. host writes the copy parameters into scratch RAM
 *   3. host writes this copier, sets the reset vector, releases the 8051
 *   4. this copier MOVXs the chunk from the gap into external SRAM, then
 *      reads it back through the external bus and verifies
 *   5. host halts the 8051 and inspects the result in scratch RAM
 *   6. repeat from 1 for further chunks
 *   7. host finally loads the real firmware over the top; external SRAM
 *      retains its contents across the 8051 reset
 *
 * Scratch RAM (0xE000-0xE1FF) is the communication channel because it is the
 * one region the host can read back via 0xA0 while the CPU is halted.
 * Internal code RAM only reads back while halted; register space (0xE200+)
 * does not read back at all.
 *
 * Build:
 *   sdcc -mmcs51 --code-loc 0x0100 --xram-loc 0xE100 --xram-size 0x80 \
 *        --iram-size 0x80 --no-xinit-opt stage1_copier.c
 *   packihx stage1_copier.ihx > stage1_copier.hex
 *
 * --xram-loc/--xram-size confine SDCC's own data to high scratch RAM so its
 * startup code cannot touch the staging gap or the external SRAM.
 * The host must place LJMP 0x0100 (02 01 00) at address 0x0000.
 */

/* ---- host/device shared mailbox, in scratch RAM ---------------------- */
#define MB(off)     ((__xdata unsigned char *)(0xE010u + (off)))

#define MB_SRC_LO   MB(0)
#define MB_SRC_HI   MB(1)
#define MB_DST_LO   MB(2)
#define MB_DST_HI   MB(3)
#define MB_LEN_LO   MB(4)
#define MB_LEN_HI   MB(5)

/* status, written by the device */
#define ST_MARK     ((__xdata unsigned char *)0xE001)
#define ST_VERIFY   ((__xdata unsigned char *)0xE004)
#define ST_FAILLO   ((__xdata unsigned char *)0xE005)
#define ST_FAILHI   ((__xdata unsigned char *)0xE006)
#define ST_GOTLO    ((__xdata unsigned char *)0xE007)  /* byte actually read */
#define ST_WANTLO   ((__xdata unsigned char *)0xE008)  /* byte expected      */

#define MARK_RUNNING  0xC1
#define MARK_COPIED   0xC2
#define MARK_DONE     0x77

#define VERIFY_OK     0xA5
#define VERIFY_FAIL   0xEE

void main(void)
{
    __xdata unsigned char *src;
    __xdata unsigned char *dst;
    unsigned int len, i;
    unsigned char bad = 0;
    unsigned char got, want;

    *ST_MARK = MARK_RUNNING;

    src = (__xdata unsigned char *)
              (((unsigned int)*MB_SRC_HI << 8) | *MB_SRC_LO);
    dst = (__xdata unsigned char *)
              (((unsigned int)*MB_DST_HI << 8) | *MB_DST_LO);
    len = ((unsigned int)*MB_LEN_HI << 8) | *MB_LEN_LO;

    for (i = 0; i < len; i++)
        dst[i] = src[i];

    *ST_MARK = MARK_COPIED;

    /* Read back through the external bus and compare.  This is the only way
     * the host can confirm the external write path worked, since the host
     * cannot read 0x4000+ itself. */
    for (i = 0; i < len; i++) {
        got  = dst[i];
        want = src[i];
        if (got != want) {
            bad = 1;
            *ST_FAILLO = (unsigned char)(i & 0xFF);
            *ST_FAILHI = (unsigned char)(i >> 8);
            *ST_GOTLO  = got;
            *ST_WANTLO = want;
            break;
        }
    }

    *ST_VERIFY = bad ? VERIFY_FAIL : VERIFY_OK;
    *ST_MARK = MARK_DONE;

    for (;;)
        ;
}
