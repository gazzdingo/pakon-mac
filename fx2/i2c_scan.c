/* Raw I2C bus scan on the FX2's own I2C controller.
 *
 * WHY THIS EXISTS
 * ---------------
 * Every previous address sweep went through the vendor packet protocol, which
 * has two blind spots:
 *
 *   1. The FX2 firmware handles board byte 0x10 itself ("self") and never puts
 *      it on the wire, so 7-bit address 0x08 has never been physically probed.
 *   2. The vendor's "present" test requires a complete well-formed response
 *      packet. A chip that ACKs its address but then fails the rest of the
 *      transaction reads as ABSENT -- indistinguishable from silence.
 *
 * A raw scan only needs the address ACK, which is a far lower bar and a far
 * more sensitive test of "is anything alive at this address".
 *
 * SAFETY
 * ------
 * Each probe sends START, the device address with the R/W bit SET (read
 * direction), then STOP. A read-direction address declares read intent on the
 * wire and no data byte is ever transmitted, so nothing can be written to any
 * device on the bus. A 24Cxx needs address byte(s) AND data before a write
 * commits. This cannot repeat the boot-EEPROM damage.
 *
 * Results land at 0x0400 and are read back over vendor request 0xA0 with the
 * 8051 held in reset, so no USB enumeration from our side is needed.
 */
#define I2CS   (*(volatile __xdata unsigned char *)0xE678)
#define I2DAT  (*(volatile __xdata unsigned char *)0xE679)

#define ST_START 0x80
#define ST_STOP  0x40
#define ST_BERR  0x04
#define ST_ACK   0x02
#define ST_DONE  0x01
#define ST_LASTRD 0x20

/* 128 status bytes, then a completion marker the host can poll. */
__xdata __at(0x0400) unsigned char results[128];
__xdata __at(0x0480) unsigned char marker[4];

static void probe(unsigned char a)
{
    unsigned int t;
    unsigned char st = 0;

    /* NOTE: do NOT issue a STOP before the START. A stop with no
     * transaction in progress sets BERR on every subsequent probe --
     * that mistake made run 2 useless. */
    I2CS  = ST_START;
    I2DAT = (unsigned char)((a << 1) | 1);   /* READ address, no data sent */

    for (t = 0; t < 30000; t++) {
        st = I2CS;
        if (st & (ST_DONE | ST_BERR))
            break;
    }
    results[a] = st;                          /* captured before recovery */

    /* A slave that ACKs a READ takes ownership of SDA. If we STOP without
     * clocking its byte out it stays wedged and every later probe reports
     * BERR -- which is exactly what the first run did from 0x52 onward.
     * Clock one byte with LASTRD set so it releases the bus cleanly. */
    if ((st & ST_ACK) && !(st & ST_BERR)) {
        I2CS = ST_LASTRD;
        (void)I2DAT;                          /* dummy read starts the byte */
        for (t = 0; t < 30000; t++)
            if (I2CS & (ST_DONE | ST_BERR))
                break;
        (void)I2DAT;                          /* collect it, freeing the bus */
    }

    I2CS = ST_STOP;
    for (t = 0; t < 30000; t++)
        if (!(I2CS & ST_STOP))
            break;
}

void main(void)
{
    unsigned char a;

    marker[0] = 0; marker[1] = 0; marker[2] = 0; marker[3] = 0;
    for (a = 0; a < 128; a++)
        results[a] = 0xEE;                /* "never ran" sentinel */

    for (a = 0; a < 128; a++)
        probe(a);

    marker[0] = 0xC0; marker[1] = 0xDE;   /* scan complete */
    marker[2] = 0xF1; marker[3] = 0x35;

    for (;;)
        ;
}
