/* Dump EVERY serial EEPROM on the FX2 I2C bus, 7-bit 0x50..0x57. READ ONLY.
 *
 * RELATIONSHIP TO eeprom_dump_all.c
 * ---------------------------------
 * This is eeprom_dump_all.c generalised from two hard-coded devices to the
 * whole 0x50-0x57 serial-EEPROM range. The dump() routine below is byte-for-
 * byte the same logic as the one that produced the VERIFIED backups in
 * backups/eeprom-i2c/ on 2026-08-05. Nothing about the I2C sequence changed;
 * only the caller loops. That was deliberate -- the read sequence is the part
 * that has been proven against real hardware, so it is the part not to touch.
 *
 * WHY THE WHOLE RANGE
 * -------------------
 * On the owner's unit the bus scan ACKed at 0x51 and 0x52 only. Two facts say
 * that is not the general case:
 *
 *   1. 0x51 (FX2 boot personality) is ERASED on that unit. Other owners may
 *      have an intact one. It is genuinely valuable -- it is how a scanner
 *      boots without the host loading firmware -- and it is 8 bytes that
 *      nobody can reconstruct once lost.
 *   2. docs/35 established that the 256 bytes at 0x52 are a FRAGMENT.
 *      FN_bReadEEPromToRegistry reads two CRC32-checked sections of 398 and
 *      36 bytes; 398 does not fit in 256. A 24C04/24C08/24C16 exposes its
 *      further pages as 0x53, 0x54, ... So the rest of the calibration is very
 *      probably at addresses this project has never read.
 *
 * The vendor enumerates exactly this range itself: fcn.100160a0 in TLB.dll
 * issues its EEPROM read with wValue = ((n | 0x50) << 1) | readBit for n <= 7.
 *
 * SAFETY -- WHY THIS CANNOT WRITE
 * -------------------------------
 * A 24Cxx random read needs a "dummy write" of the word address to position
 * the internal address pointer, then a REPEATED START to turn the bus around.
 * Three properties make a write structurally impossible here:
 *
 *   1. There are exactly three I2DAT stores in this file: the device address,
 *      the word address, and the read address. No data byte is ever
 *      transmitted -- grep the source, there is no fourth store.
 *   2. No STOP is issued between the word address and the repeated start.
 *      A 24Cxx begins its internal write cycle only on STOP, so the byte the
 *      part latched as an address pointer can never be committed to the array.
 *   3. The word address is always 0x00 and is never taken from the host.
 *      There is no mailbox, no host-supplied parameter, and no code path that
 *      varies what is sent. The firmware takes no input at all.
 *
 * ONE READ PER DEVICE, ONE RUN PER POWER CYCLE
 * --------------------------------------------
 * Established on hardware 2026-08-05 (backups/eeprom-i2c/README.md): these
 * parts return good data on the FIRST transaction after a power cycle and
 * degrade silently on every read after it -- the second read of a cycle
 * differed in 180 of 256 bytes, the third was all 0xFF, and the I2C status
 * stayed "ok" throughout. So each address is read exactly ONCE per run, and
 * the host must not run this twice in one power cycle.
 *
 * Reading eight addresses in one run is safe, and is not a second read of
 * anything: degradation is per-device (first transaction to THAT device).
 * The evidence is the existing backups -- eeprom_dump_all.c read 0x51 and then
 * 0x52 in a single pass, and both files reproduced byte-identically from a
 * separate power cycle.
 *
 * MEMORY MAP (all read back by the host via vendor request 0xA0)
 *   0x0400 + n*0x100   256 bytes from 7-bit address (0x50 + n), n = 0..7
 *                      so 0x50 -> 0x0400, 0x51 -> 0x0500, 0x52 -> 0x0600,
 *                         0x53 -> 0x0700 ... 0x57 -> 0x0B00
 *   0x0C00             status block, 16 bytes:
 *                        [0..7]   per-device result, index n
 *                        [8..11]  completion marker C0 DE F1 35
 *                        [12]     firmware format version = 2
 *                        [13]     device count = 8
 *                        [14..15] reserved, zero
 *
 * Result codes: 0 = ok, 1 = no ACK on device addr (nothing at that address),
 *               2 = no ACK on word addr, 3 = no ACK on read addr,
 *               4 = bus error during read.
 *
 * Buffers are pre-filled with 0xEE, a "never read" sentinel. 0xEE is
 * deliberately neither 0x00 nor 0xFF, so the host can tell "the firmware did
 * not run" apart from "the device answered with erased bytes" -- a
 * distinction that matters enormously here, because all-0xFF is exactly what
 * a degraded read looks like.
 *
 * Build (reproduces byte-identically with sdcc 4.6.0):
 *   sdcc -mmcs51 --iram-size 0x80 --xram-size 0x200 --code-size 0x400 \
 *        --xram-loc 0x0D00 eeprom_dump_bus.c
 */
#define I2CS   (*(volatile __xdata unsigned char *)0xE678)
#define I2DAT  (*(volatile __xdata unsigned char *)0xE679)

#define ST_START  0x80
#define ST_STOP   0x40
#define ST_LASTRD 0x20
#define ST_BERR   0x04
#define ST_ACK    0x02
#define ST_DONE   0x01

#define NDEV 8

__xdata __at(0x0400) unsigned char buf[NDEV][256];
__xdata __at(0x0C00) unsigned char st[16];

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

/* addr8 is the 8-bit WRITE address, e.g. 0xA2 for 7-bit 0x51.
 * Reads 256 bytes from word address 0 into out[]. Never transmits a data
 * byte. Returns a result code as documented above. */
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
    unsigned char n;

    for (n = 0; n < 16; n++)
        st[n] = 0;

    /* One pass, one read per address, ascending. 7-bit (0x50 + n) becomes the
     * 8-bit write address 0xA0 + 2n. */
    for (n = 0; n < NDEV; n++)
        st[n] = dump((unsigned char)(0xA0 + (n << 1)), buf[n]);

    st[8] = 0xC0; st[9] = 0xDE; st[10] = 0xF1; st[11] = 0x35;
    st[12] = 2;                              /* firmware format version */
    st[13] = NDEV;

    for (;;)
        ;
}
