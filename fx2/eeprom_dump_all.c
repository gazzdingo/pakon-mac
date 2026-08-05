/* Dump BOTH I2C EEPROMs in full. READ ONLY.
 *
 * WHY
 * ---
 * The raw bus scan found ACKs at 7-bit 0x51 AND 0x52, but NOT at 0x50 or
 * 0x53-0x57. A single multi-page device (24C16 style) would answer across a
 * contiguous block of addresses, so this is very likely TWO SEPARATE EEPROM
 * chips with their address pins strapped differently.
 *
 * We have only ever read 16 bytes of 0x51 (the FX2 boot personality, now
 * erased). The rest of that device, and ALL of 0x52, has never been looked at.
 *
 * TLB.dll exposes FN_bEEPromReadSection / FN_bEEPromWriteSection, implying the
 * store is partitioned, and PTS has tabs for "PCS EEProm" magnification,
 * optical alignment and per-format motor speeds. That per-unit calibration is
 * irreplaceable -- it describes THIS scanner's optics and transport and cannot
 * be downloaded from anywhere. If it lives here, we want it off the chip.
 *
 * SAFETY
 * ------
 * A 24Cxx random read needs a "dummy write" of the word address to position
 * the internal pointer, followed by a REPEATED START. No STOP is issued
 * between the address and the repeated start, and a 24Cxx only commits a write
 * on STOP -- so nothing can be written. There is exactly one I2DAT write for
 * the device address, one for the word address, and one for the read address.
 * No data byte is ever transmitted.
 *
 * RESULTS
 *   0x0400  256 bytes from device 0x51
 *   0x0500  256 bytes from device 0x52
 *   0x0600  status: [0]=dev51 result [1]=dev52 result [2..5]=marker
 *           result 0 = ok, 1 = no ACK on device addr, 2 = no ACK on word addr,
 *           3 = no ACK on read addr, 4 = bus error during read
 */
#define I2CS   (*(volatile __xdata unsigned char *)0xE678)
#define I2DAT  (*(volatile __xdata unsigned char *)0xE679)

#define ST_START  0x80
#define ST_STOP   0x40
#define ST_LASTRD 0x20
#define ST_BERR   0x04
#define ST_ACK    0x02
#define ST_DONE   0x01

__xdata __at(0x0400) unsigned char d51[256];
__xdata __at(0x0500) unsigned char d52[256];
__xdata __at(0x0600) unsigned char st[8];

static unsigned char wd(void)
{
    unsigned int t;
    unsigned char s = 0;
    for (t = 0; t < 30000; t++) {
        s = I2CS;
        if (s & (ST_DONE | ST_BERR))
            return s;
    }
    return s;
}

static void stop(void)
{
    unsigned int t;
    I2CS = ST_STOP;
    for (t = 0; t < 30000; t++)
        if (!(I2CS & ST_STOP))
            break;
}

/* addr8 is the 8-bit write address, e.g. 0xA2 for 7-bit 0x51 */
static unsigned char dump(unsigned char addr8, __xdata unsigned char *out)
{
    unsigned int i;
    unsigned char s;

    for (i = 0; i < 256; i++)
        out[i] = 0xEE;                       /* "never read" sentinel */

    I2CS  = ST_START;
    I2DAT = addr8;                           /* device address, write dir */
    s = wd();
    if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 1; }

    I2DAT = 0x00;                            /* word address 0 -- pointer only */
    s = wd();
    if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 2; }

    I2CS  = ST_START;                        /* REPEATED start, no STOP first */
    I2DAT = (unsigned char)(addr8 | 1);      /* device address, read dir */
    s = wd();
    if (!(s & ST_ACK) || (s & ST_BERR)) { stop(); return 3; }

    (void)I2DAT;                             /* starts the first byte */
    for (i = 0; i < 256; i++) {
        if (i == 255)
            I2CS = ST_LASTRD;                /* NACK the final byte */
        s = wd();
        if (s & ST_BERR) { stop(); return 4; }
        out[i] = I2DAT;
    }
    stop();
    return 0;
}

void main(void)
{
    unsigned char i;
    for (i = 0; i < 8; i++) st[i] = 0;

    st[0] = dump(0xA2, d51);                 /* 7-bit 0x51 */
    st[1] = dump(0xA4, d52);                 /* 7-bit 0x52 */

    st[2] = 0xC0; st[3] = 0xDE; st[4] = 0xF1; st[5] = 0x35;
    for (;;)
        ;
}
