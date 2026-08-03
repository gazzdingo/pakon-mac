# 23 — Why the PICM does not answer after a cold boot

Written **before** reading the parallel analysis, so the two can be compared as
independent readings rather than one agreeing with the other. Each hypothesis
below states a prediction that would confirm or kill it.

## The observation

| path | result |
|------|--------|
| in-session restart from the bootloader (`04 03 46 00 08`, wait 8 s, hand-off) | 0x44 answers; the **entire** CCD bring-up is accepted, every packet status 0 |
| cold power-on | neither 0x44 nor 0x46 answers; front LEDs green / orange / orange |

The application demonstrably works — it accepted geometry, integration time,
A/D configuration and the control word. So this is not a broken board.

The informative detail is that **both** addresses are silent after a cold boot.
A PIC starts execution at 0x0000, which is bootloader territory. So on power-up
the bootloader runs and either stays resident (0x46 would answer) or hands off
to the application (0x44 would answer). Silence from both means it hands off
and the application then stops answering.

## H1 — More of the flash is erased than the two rows found

**The weakest point in the repair.** The damage was mapped by reading blocks
0x400-0x4F0 exhaustively and then sampling only 0x800, 0x1000 and 0x2000. Four
sample points out of 664 blocks were used to conclude "everything above 0x480
is intact".

The bootloader-entry command erased two rows at the vectors. Nothing establishes
that it erased *only* those two. If it also cleared a configuration block, a
checksum table or a self-test region elsewhere, the application would start,
fail its own validation, and halt — which is exactly the observed behaviour,
orange LEDs included.

**Prediction:** a full read-back of 0x000400-0x002D7F diffed against
`nm0506.HEX` shows one or more further blank blocks.
**Kill condition:** all 664 blocks match; then the flash is complete and this is
not the cause.

## H2 — The resident firmware is a different revision from nm0506

The vectors written came from `nm0506.HEX` (PCB #125430C). The reset vector is
`e1 ef 15 f0`, a PIC18 `GOTO 0x2BC2`. If the resident firmware were `nm0406`
(#125430B) or `nm0306` (#125430A), its entry point would sit elsewhere and that
jump would land in the middle of unrelated code — the application would start
and immediately go wrong.

Against this: blocks at 0x480-0x4F0, 0x800, 0x1000 and 0x2000 all matched
`nm0506` byte-for-byte. Four independent matches at scattered addresses is
strong evidence the resident image *is* nm0506. But it is evidence, not proof,
and the PCB revision has never been read off the board.

**Prediction:** a full diff shows systematic mismatches in regions we never
sampled.
**Kill condition:** all 664 blocks match nm0506, which settles the revision
question at the same time.

## H3 — The application requires a host handshake before it services I2C

The two paths differ in more than timing. In the working case the host had just
completed a bootloader conversation, waited 8 seconds, and sent an explicit
hand-off to 0x44. In the failing case the host does nothing at all — it loads
FX2 firmware and starts probing.

The vendor driver may perform an initialisation the port does not: a power gate,
a reset release, an enable, or simply a settling delay far longer than the
probes allow. `FN_bInit2` (fcn.1000b100) is the obvious candidate, and an
earlier pass noted host register 0x8f with a 100 ms settle gating an auxiliary
board.

**Prediction:** the vendor's init sequence contains packets we never send, and
sending them makes 0x44 answer.
**Kill condition:** `FN_bInit2` turns out to send nothing to 0x44 before probing
it, exactly as the port does.

## H4 — The application halts on a failed self test

The board has a built-in self test with dedicated error codes:

```
EC_BistPicmVinFail  EC_BistPicm13VFail  EC_BistPicm12VFail
EC_BistPicm6VFail   EC_BistPicm5VFail   EC_BistPicm3VFail
EC_BistPicmMotorFail   EC_BistPiclMotherBdFpgaCommFail
```

Two orange LEDs fit a board reporting a fault. If the application runs its BIST,
fails, and halts rather than continuing, it would never reach the point of
servicing I2C.

Note this overlaps H1: a partially erased flash is one *reason* a self test
would fail. It is also possible on its own — a genuine hardware fault that was
always present and simply invisible while the board was in its bootloader.

**Prediction:** the BIST result is readable from the host or the light board,
and names a specific failure.
**Kill condition:** no BIST result is reachable while the PICM is silent, or it
reports success.

## H5 — Timing

The application may take longer to become ready than the probes allow. The
successful path included an 8-second wait; the cold-boot probe starts within a
second or two of firmware load.

**Prediction:** probing 0x44 repeatedly for 30-60 seconds after a cold boot
eventually gets an answer.
**Kill condition:** it stays silent for a minute.

Cheap to test and worth eliminating early, precisely because it is cheap.

## Ranking

1. **H1** — the repair's weakest assumption, testable read-only, and the fix is
   the same surgical write already performed once.
2. **H5** — trivial to test, read-only, eliminates a dull explanation.
3. **H3** — most likely of the "we are missing something" explanations, and
   answerable from the binary.
4. **H4** — plausible, but overlaps H1 and is harder to observe directly.
5. **H2** — least likely given four scattered byte-exact matches, and a full
   diff settles it as a side effect of testing H1.

H1 and H5 are both read-only and between them cover the two most likely
explanations. They should be run before anything is written.
