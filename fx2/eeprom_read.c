/* Read the FX2 boot EEPROM. READ ONLY.
 *
 * WHY: the scanner is enumerating as 04b4:8613 (Cypress default) instead of
 * 0f05:f235, which means the FX2 is ignoring its boot EEPROM. The raw I2C
 * scan proved the EEPROM is present and ACKs at 0x51/0x52, so the bus is
 * fine and the CONTENTS must be wrong -- byte 0 is the C0 format signature
 * and anything else makes the FX2 fall back to its hardwired IDs.
 *
 * ON "READ ONLY": a 24Cxx random read requires a so-called dummy write --
 * device address followed by the word address -- to position the chip's
 * internal address pointer, then a repeated START to read. NO DATA BYTE
 * FOLLOWS, and a 24Cxx only commits a write when data bytes are clocked in
 * before the STOP. Setting the address pointer cannot alter stored contents.
 * This is the standard and only way to read from a chosen offset.
 */
#define I2CS   (*(volatile __xdata unsigned char *)0xE678)
#define I2DAT  (*(volatile __xdata unsigned char *)0xE679)

#define ST_START  0x80
#define ST_STOP   0x40
#define ST_LASTRD 0x20
#define ST_BERR   0x04
#define ST_ACK    0x02
#define ST_DONE   0x01

#define N 16

__xdata __at(0x0400) unsigned char buf[N];
__xdata __at(0x0420) unsigned char st[4];
__xdata __at(0x0480) unsigned char marker[4];

static unsigned char wait_done(void)
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

void main(void)
{
    unsigned char i, s;
    unsigned int t;

    for (i = 0; i < N; i++) buf[i] = 0xEE;
    st[0] = st[1] = st[2] = st[3] = 0;
    marker[0] = marker[1] = marker[2] = marker[3] = 0;

    /* Dummy write: device address (W) then word address. Pointer only. */
    I2CS  = ST_START;
    I2DAT = 0xA2;
    s = wait_done(); st[0] = s;
    if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE1; goto done; }

    I2DAT = 0x00;                       /* word address 0 -- not data */
    s = wait_done(); st[1] = s;
    if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE2; goto done; }

    /* Repeated START, device address (R). */
    I2CS  = ST_START;
    I2DAT = 0xA3;
    s = wait_done(); st[2] = s;
    if (!(s & ST_ACK) || (s & ST_BERR)) { marker[0] = 0xE3; goto done; }

    (void)I2DAT;                        /* starts the first byte */
    for (i = 0; i < N; i++) {
        if (i == N - 1)
            I2CS = ST_LASTRD;
        s = wait_done();
        buf[i] = I2DAT;
    }
    st[3] = s;
    marker[0] = 0xC0; marker[1] = 0xDE;

done:
    I2CS = ST_STOP;
    for (t = 0; t < 30000; t++)
        if (!(I2CS & ST_STOP))
            break;
    marker[2] = 0xF1; marker[3] = 0x35;

    for (;;)
        ;
}
