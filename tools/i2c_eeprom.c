/*
 * FX2 I2C EEPROM repair / inspection tool.
 *
 * WHY THIS EXISTS
 * ---------------
 * The Pakon USB board carries a Cypress "C0 format" boot EEPROM on the FX2's
 * I2C bus. It holds 8 bytes:
 *
 *     C0  VIDlo VIDhi  PIDlo PIDhi  DIDlo DIDhi  CFG
 *     C0  05 0F        35 F2        07 AA        04       <- this scanner
 *
 * The leading 0xC0 is the format signature. If it is anything else the FX2
 * ignores the EEPROM entirely and enumerates with its hardwired default IDs
 * (04B4:8613), which is exactly the failure being repaired here.
 *
 * On this unit byte 0 became 0x5C while bytes 1..7 stayed intact, so only the
 * signature needs rewriting.
 *
 * The FX2's hardwired boot loader implements only vendor request 0xA0 (load
 * into RAM); it cannot touch the I2C bus. So the host loads THIS program,
 * which drives the FX2's I2C controller directly, then reads the result back
 * out of scratch RAM -- the one region the host can read while the CPU is
 * halted.
 *
 * MAILBOX (scratch RAM, written by the host before release)
 *     0xE010  operation: 0 = read only, 1 = write then verify
 *     0xE011  I2C device address, 8-bit form (0xA2 for the boot EEPROM)
 *     0xE012  offset within the EEPROM
 *     0xE013  byte to write (operation 1 only)
 *
 * RESULTS (written by this program, read back by the host)
 *     0xE000  progress marker: C1 started, C2 addressed, 77 finished
 *     0xE001  status: 0 ok, 1 no ACK on device address,
 *                     2 no ACK on offset, 3 no ACK on data, 4 bus error
 *     0xE002  byte read back at the requested offset
 *     0xE003  0xA5 if a verify read matched the byte written
 *     0xE004..0xE00B  the first 8 bytes of the EEPROM, read sequentially
 *
 * Build:
 *   sdcc -mmcs51 --code-loc 0x0100 --xram-loc 0xE100 --xram-size 0x40 \
 *        --iram-size 0x80 --no-xinit-opt i2c_eeprom.c
 *   packihx i2c_eeprom.ihx > i2c_eeprom.hex
 * The host must place LJMP 0x0100 (02 01 00) at address 0x0000.
 */

/* FX2 I2C controller registers */
__xdata __at (0xE678) volatile unsigned char I2CS;
__xdata __at (0xE679) volatile unsigned char I2DAT;
__xdata __at (0xE67A) volatile unsigned char I2CTL;

#define I2CS_START   0x80
#define I2CS_STOP    0x40
#define I2CS_LASTRD  0x20
#define I2CS_ID1     0x10
#define I2CS_ID0     0x08
#define I2CS_BERR    0x04
#define I2CS_ACK     0x02
#define I2CS_DONE    0x01

#define MB_OP    ((__xdata unsigned char *)0xE010)
#define MB_DEV   ((__xdata unsigned char *)0xE011)
#define MB_OFF   ((__xdata unsigned char *)0xE012)
#define MB_VAL   ((__xdata unsigned char *)0xE013)

#define ST_MARK  ((__xdata unsigned char *)0xE000)
#define ST_STAT  ((__xdata unsigned char *)0xE001)
#define ST_READ  ((__xdata unsigned char *)0xE002)
#define ST_VER   ((__xdata unsigned char *)0xE003)
#define ST_DUMP  ((__xdata unsigned char *)0xE004)

static unsigned char wait_done(void)
{
    unsigned int guard = 0;
    while (!(I2CS & I2CS_DONE)) {
        if (++guard == 0)
            return 0xFF;              /* timed out */
    }
    if (I2CS & I2CS_BERR)
        return 4;
    return (I2CS & I2CS_ACK) ? 0 : 1; /* 1 == device did not acknowledge */
}

static void settle(void)
{
    unsigned int i;
    for (i = 0; i < 20000; i++)
        ;
}

void main(void)
{
    unsigned char dev, off, val, op, rc, i;

    *ST_MARK = 0xC1;
    *ST_STAT = 0xFF;
    *ST_VER = 0x00;

    I2CTL = 0x00;                     /* 100 kHz, safest for old parts */

    op  = *MB_OP;
    dev = *MB_DEV;
    off = *MB_OFF;
    val = *MB_VAL;

    if (op == 1) {
        /* ---- byte write: START, dev|W, offset, data, STOP ---- */
        I2CS = I2CS_START;
        I2DAT = dev & 0xFE;
        rc = wait_done();
        if (rc) { *ST_STAT = rc ? 1 : 0; I2CS = I2CS_STOP; goto dump; }

        I2DAT = off;
        rc = wait_done();
        if (rc) { *ST_STAT = 2; I2CS = I2CS_STOP; goto dump; }

        I2DAT = val;
        rc = wait_done();
        if (rc) { *ST_STAT = 3; I2CS = I2CS_STOP; goto dump; }

        I2CS = I2CS_STOP;
        settle();                     /* EEPROM internal write cycle */
    }

dump:
    *ST_MARK = 0xC2;

    /* ---- sequential read of the first 8 bytes ---- */
    I2CS = I2CS_START;
    I2DAT = dev & 0xFE;
    if (wait_done()) { *ST_STAT = 1; I2CS = I2CS_STOP; goto done; }
    I2DAT = off;
    if (wait_done()) { *ST_STAT = 2; I2CS = I2CS_STOP; goto done; }

    I2CS = I2CS_START;                /* repeated START */
    I2DAT = dev | 0x01;               /* read address */
    if (wait_done()) { *ST_STAT = 1; I2CS = I2CS_STOP; goto done; }

    for (i = 0; i < 8; i++) {
        if (i == 7)
            I2CS = I2CS_LASTRD;       /* NAK the final byte */
        (void)I2DAT;                  /* dummy read starts the transfer */
        if (wait_done()) break;
        ST_DUMP[i] = I2DAT;
    }
    I2CS = I2CS_STOP;

    *ST_READ = ST_DUMP[0];
    if (op == 1)
        *ST_VER = (ST_DUMP[0] == val) ? 0xA5 : 0xEE;
    if (*ST_STAT == 0xFF)
        *ST_STAT = 0;

done:
    *ST_MARK = 0x77;
    for (;;)
        ;
}
