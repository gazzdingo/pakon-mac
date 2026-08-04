/* Catch U11's I2C bootloader in its power-on listening window. READ ONLY.
 *
 * THE GAP THIS CLOSES
 * -------------------
 * Every probe ever run on this scanner happened SECONDS after power-on: the
 * FX2 must enumerate, then the host downloads firmware, then we probe. A
 * PIC18F452 at 40 MHz boots in milliseconds. If U11's bootloader listens on
 * I2C for a window before handing off to the application, we have missed it
 * every single time -- including the 128-address scan.
 *
 * WHY IT IS DECISIVE
 * ------------------
 * The bootloader (0x0000-0x03FF) and the application share the SAME MSSP
 * peripheral and the SAME two pins.
 *
 *   bootloader answers in the window -> MSSP hardware WORKS, and the
 *       application is failing to arm it. Firmware problem. Reflashable.
 *       No chip swap, no rework.
 *   bootloader silent too -> the peripheral or the pins are genuinely dead.
 *       Hardware problem.
 *
 * That is exactly the fork we are stuck on, and this answers it without a
 * programmer.
 *
 * HOW IT IS USED
 * --------------
 * This runs on the FX2 and probes continuously. While it is running, the
 * operator briefly shorts JM11 pin 1 (MCLR) to ground, which resets ONLY U11
 * -- the FX2 keeps running with this code already loaded. So the probe loop
 * is live BEFORE the PIC executes its first instruction.
 *
 * Pulling MCLR low is a plain reset, exactly what a programmer does to enter
 * programming mode. Nothing is written and there is no state to get stuck in.
 *
 * SAFETY
 * ------
 * Each probe is START, device address with the R/W bit SET (read direction),
 * one byte clocked out with LASTRD so an ACKing slave releases the bus, then
 * STOP. Exactly ONE write to I2DAT in this file and it is the address. No
 * data byte is ever transmitted to any device.
 *
 * RESULTS (read back over vendor request 0xA0 with the 8051 halted)
 *   0x0400  hit log, 4 bytes per entry: addr, status, tick_hi, tick_lo
 *   0x0500  number of hits
 *   0x0504  free-running 32-bit tick counter (LE), so "when" is
 *           interpretable. 16 bits would wrap in ~4 seconds.
 *   0x0480  marker: C0 DE F1 35 once the loop has started
 */
#define I2CS   (*(volatile __xdata unsigned char *)0xE678)
#define I2DAT  (*(volatile __xdata unsigned char *)0xE679)

#define ST_START  0x80
#define ST_STOP   0x40
#define ST_LASTRD 0x20
#define ST_BERR   0x04
#define ST_ACK    0x02
#define ST_DONE   0x01

#define MAXHIT 48

__xdata __at(0x0400) unsigned char hits[MAXHIT * 4];
__xdata __at(0x0480) unsigned char marker[4];
__xdata __at(0x0500) unsigned int nhit;
/* 32-bit: at ~15,700 passes/sec a 16-bit counter overflows in
 * about 4 seconds, which would make the timing meaningless. */
__xdata __at(0x0504) unsigned long tick;

static unsigned char wait_done(void)
{
    unsigned int t;
    unsigned char s = 0;
    for (t = 0; t < 4000; t++) {          /* short: we want a TIGHT loop */
        s = I2CS;
        if (s & (ST_DONE | ST_BERR))
            return s;
    }
    return s;
}

static void probe(unsigned char a)
{
    unsigned char s;
    unsigned int t;

    I2CS  = ST_START;
    I2DAT = (unsigned char)((a << 1) | 1);   /* READ address, no data sent */
    s = wait_done();

    if ((s & ST_ACK) && !(s & ST_BERR)) {
        if (nhit < MAXHIT) {
            hits[nhit * 4 + 0] = a;
            hits[nhit * 4 + 1] = s;
            hits[nhit * 4 + 2] = (unsigned char)((tick >> 8) & 0xFF);
            hits[nhit * 4 + 3] = (unsigned char)(tick & 0xFF);
            nhit++;
        }
        /* An ACKing slave owns SDA; clock one byte with LASTRD so it lets go,
         * otherwise the bus stays wedged and every later probe reports BERR. */
        I2CS = ST_LASTRD;
        (void)I2DAT;
        (void)wait_done();
        (void)I2DAT;
    }

    I2CS = ST_STOP;
    for (t = 0; t < 4000; t++)
        if (!(I2CS & ST_STOP))
            break;
}

void main(void)
{
    unsigned int i;

    for (i = 0; i < MAXHIT * 4; i++)
        hits[i] = 0;
    nhit = 0;
    tick = 0;
    marker[0] = 0xC0; marker[1] = 0xDE;
    marker[2] = 0xF1; marker[3] = 0x35;

    /* Probe forever. The host halts us by asserting 8051 reset, then reads
     * the log straight out of RAM. */
    for (;;) {
        probe(0x22);            /* PICM application */
        probe(0x23);            /* PICM bootloader  */
        tick++;
    }
}
