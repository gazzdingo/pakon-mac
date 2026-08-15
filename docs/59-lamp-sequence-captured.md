# 59 — The vendor's complete lamp/LED sequence, captured

> **ONE INFERENCE WITHDRAWN, ONE READING CORRECTED.** The "green-reference
> white balance" reading below is withdrawn — I built it on two coincidences.
> The real relationship, from the `calibration-and-tone-port` work: the vendor
> keeps **two duty sets**, and `FN_bBeforeScan` (`0x1002e137` → `0x1002d7f0`)
> selects `DutyCycle_*` with film in the gate and `DutyCycleOpenGate_*` without.
> They differ by exactly **10^D**, the colour-negative base density — the
> with-film set adds back what the orange mask absorbs.
>
> Verified against the registry, exact to six figures:
>
> ```
> ch   with-film   open-gate      ratio     10^D      D
> R     0.917161    0.658333   1.393157   EXACT   0.1440
> G     0.955468    0.380378   2.511891   EXACT   0.4000
> B     0.865802    0.166885   5.188016   EXACT   0.7150
> ```
>
> And against **the captured pair**, which is the stronger test: step 82's
> on-counts × 10^D reproduce step 100's to within 1 count on R and G, 5 on B.
>
> **So steps 82 and 100 are not "dim then bright".** They are the open-gate set
> and the with-film set. What reads as a ramp is the vendor switching sets when
> film enters the gate. That supersedes the "drive ramp" explanation for the
> flash below.
>
> Safety consequence, now fixed in `tools/lamp_replay_vendor.py`: `--full` is
> the **with-film** set and saturates blue on a bare gate. The default is the
> open-gate set, which is correct for a bare gate.

**Date: 2026-08-13.** Ground truth for the light board, from the same API
Monitor capture as `docs/55`. This is the answer to "the LEDs flash under PSI
but not under ours".

## First: `docs/55` under-reported its own capture

`docs/55` said "92 raw hits, 46 distinct writes". That was an extraction bug.
The regex was `02 <len> <board> 03` — and that `03` is the **payload length**,
so it matched only 3-byte-payload writes. Lamp and LED packets carry payload
lengths `01`, `05`, `0C` and `04`, and were silently dropped.

Re-parsed with a real framer:

```
packet = <type> <pktlen> <addr> <paylen> <reg> <payload[paylen]>
         pktlen == paylen + 3,  total bytes == 2 + pktlen
```

**380 packets, 126 after consecutive-dedupe** — not 46. The entire light board
was in the capture the whole time. `docs/55`'s CCD table is still correct as far
as it goes; it was incomplete, not wrong.

## The light board sequence

```
  5   t2 LIGHT  0x03 [1]  01                            board select / init
  8   t4 LIGHT  0x8A [0]                                FIFO/DX reset
  9   t2 LIGHT  0x8F [4]  E8 FF 18 00     = [ -24,  24]  monitor threshold
 10   t2 LIGHT  0x8C [4]  E0 FF 20 00     = [ -32,  32]  monitor threshold
 11   t2 LIGHT  0x8B [4]  F0 00 20 03     = [ 240, 800]  monitor threshold
 12   t2 LIGHT  0x8D [4]  A0 00 70 03     = [ 160, 880]  monitor threshold
 13   t2 LIGHT  0xD0 [1]  00
 14   t2 LIGHT  0xD1 [1]  01
 15   t2 LIGHT  0x87 [2]  00 00
 16   t2 LIGHT  0x80 [1]  01                            ENABLE, visible
 17   t2 LIGHT  0x82 [12] all zero except N=0x03D6      drive = 0  -> dark
 18   t2 LIGHT  0x80 [1]  00                            disable
 19   t2 LIGHT  0x89 [1]  00
      ... CCD bring-up (docs/55 steps 20-79) ...
 80   t2 LIGHT  0x80 [1]  01                            ENABLE, visible
 81   t2 LIGHT  0x81 [5]  07 00 03 00 0B                LED LEVELS
 82   t2 LIGHT  0x82 [12] 9C 00 00 00 8E 02 00 00 76 01 D6 03    <- LIT
 85   t2 LIGHT  0x82 [12] ...75 01 D6 03                hunt (G 374->373)
 88   t2 LIGHT  0x82 [12] ...75 01 D6 03
 91   t2 LIGHT  0x82 [12] ...75 01 D6 03
100   t2 LIGHT  0x82 [12] 24 03 00 00 90 03 00 00 AA 03 D6 03    <- FULL SCAN
107   t2 LIGHT  0x91 [3]  3C 00 01                      idx 60 = 0x0100
114   t2 LIGHT  0x80 [1]  00                            lamp off
117   t4 LIGHT  0x92 [0]
```

Interleaved throughout: `HOST 0x84 [1] 02` immediately followed by
`t4 LIGHT 0x8A`, **20 times**. That pair is the poll/ack loop the calibration
search runs between drive changes. And `LIGHT 0x06 [2]` alternating `00 02` /
`00 20`, 7 times, during the scan itself — `[UNKNOWN]`, but it tracks the scan,
not the lamp.

## The drive values, decoded

Channel order is `B, Ir, R, –, G` in both registers, per `docs/40` — **not**
R,G,B. Byte 3 of `0x81` is a hard zero, slot 3 of `0x82` a hard zero u16.

```
0x81  LED LEVELS   07 00 03 00 0B    ->  B=7   Ir=0   R=3   G=11

0x82  PWM on-counts (6 x u16 LE, last = N, the period)
  step 17   B=  0  Ir=0  R=  0  G=  0   N=982     drive zero
  step 82   B=156  Ir=0  R=654  G=374   N=982     duty .159 / .666 / .381
  step 100  B=804  Ir=0  R=912  G=938   N=982     duty .819 / .928 / .955
```

## Three independent confirmations of `docs/40`

`docs/40` derived the encoding statically from `FN_bDrvLampOn`. The capture
tests it against what the vendor actually put on the wire, and it holds on
every point:

**1. The clock correction is right.** `docs/40` corrected `docs/15`'s legacy
×0.6 factor to `N = trunc(exposure × 1e6 / (2 × 2,083,333.3))`. The captured
`N = 982` matches **exactly one** entry in `docs/40`'s F-135 exposure table:

```
exposure 4093 (DpiBase16_35, non-IR)  ->  N_float = 982.32  ->  N = 982
```

No other table entry produces 982. So the corrected clock *and* the corrected
exposure table are both confirmed, and the captured scan was DpiBase16_35
non-IR.

**2. The clamps are right.** `Ir = 0`, so `docs/40`'s IR-off set applies:

| ch | captured | ceiling | |
|---|---|---|---|
| R | 3 | 4 | OK |
| G | 11 | 20 | OK |
| B | 7 | 20 | OK |
| Ir | 0 | 0 | OK |

Every level is inside the ceiling, and R sits at 3 of 4 — tight enough that the
clamp table is clearly the real one and not a coincidence.

**3. `on_ch <= N-2` holds.** Max captured on-count is 938, against `N-2 = 980`.

**4. The setpoint gate is right.** `docs/40` said `0x8E` is the only gated
register and is skipped when `UseTemperatureSetpoints = 0`. The capture writes
`0x8F`, `0x8C`, `0x8B`, `0x8D`, `0xD0`, `0xD1` — and **never `0x8E`**. Exactly
as predicted.

## So why do their LEDs flash and ours do not

Three separate reasons, in order of how much they matter:

1. **We have never written `0x81`/`0x82` with real values.** `docs/14`
   established that `0x80` is an enable, not a brightness, and that `0x81`/`0x82`
   are write-only so they cannot be read back. Enabling with zero drive gives
   `07 02 40 00` success and darkness — which is what the port does.
   `tools/lamp_first_light.py` caps every level at 4 because it was inventing
   values. **It no longer has to.** The four numbers above are this unit's own,
   captured off this unit's own wire.

2. **The visible "flash" is the drive ramp, not a blink.** `0x80` is written
   only four times in the entire session (`01 00 01 00`) — two on/off cycles.
   What the eye reads as flashing is step 82 → 100: lamp comes up at duty
   .16/.67/.38, holds through the CCD dark-offset calibration, then jumps to
   .82/.93/.96 for the scan. Dim, pause, bright, off.

3. **The step 16-18 pulse.** Enable is asserted *before* drive is zeroed. If the
   board retains non-zero duty from a previous session, that is a genuine brief
   flash at startup. `[INFERRED]` — it depends on prior board state, and this
   capture cannot show what the board held before it began.

## What to do with it

`tools/lamp_replay_vendor.py` replays the light-board sequence above byte for
byte. It defaults to a dry run and prints the packets without sending them.

**On safety.** These are not invented values. Every byte was sent to this exact
unit by the vendor software, and every one satisfies the clamp table derived
independently from the binary. That is the strongest safety argument available
short of not lighting the lamp at all. The script still ramps: it programs drive
*before* enable (the reverse of the vendor's step 16-18 order, deliberately, so
there is no pulse), uses the step-82 calibration level rather than the step-100
scan level by default, and turns the lamp off on any exception.

## Does this transfer to other F-135s?

Mostly yes. The split is clean, and it is **two register writes** wide.

### Universal — same on any F-135 / F-135 Plus

* Packet framing, the light-board register map, and the `B, Ir, R, –, G`
  channel order. Protocol, not calibration.
* The ordering of the sequence itself.
* `N = trunc(exposure × 1e6 / (2 × 2,083,333.3))` and the F-135 exposure table.
  Per *model*, not per unit — and note `docs/40` found the legacy `0x20`/`0x24`
  boards use a different clock (833,333.3), so this does **not** carry to
  pre-Plus hardware.
* The clamp ceilings. They live in the board firmware (`fcn.100203c0`), so they
  are the same for every unit running that firmware.
* **The four threshold blocks `0x8B/0x8C/0x8D/0x8F` and `0xD0`/`0xD1`.** These
  look like calibration but are not. `docs/40` showed that with
  `UseTemperatureSetpoints = 0` the config loader skips every thermal registry
  read, leaving those fields at **constructor defaults** — and the recovered
  hive contains no `LampTemp*` values at all, which is only possible if that
  branch ran. So these are constants, and they transfer.

### Per-unit — the only two writes that do not transfer

`0x81` levels and `0x82` drive. Both come from `CiConfigLight` in the registry
(`docs/37`), and both differ between units because LED output varies with bin
and with age.

### A finding about where those values come from

Comparing the capture against the registry values recovered in `docs/37`
(`Current_*`, `DutyCycle_*`, `DutyCycleOpenGate_*`), with `N_float = 982.32`:

```
                        registry -> predicted    captured    delta
OpenGate  R  0.658333            646              654        +8
          G  0.380378            373              373       *** EXACT ***
          B  0.166885            163              156        -7

DutyCycle R  0.917161            900              912       +12
          G  0.955468            938              938       *** EXACT ***
          B  0.865802            850              804       -46
```

**G is taken from the registry verbatim in both drive sets. R and B are not.**
That happens twice, on two independent value sets, which is not coincidence.

The natural reading is that **green is the reference channel and R/B are trimmed
live against the CCD response** — standard practice for balancing an RGB LED
illuminant, and consistent with `FN_bCalibrateFindLedDutyCycle` existing at all.
`[INFERRED]` — the trim deltas are not consistent between the two sets (−7 vs
−46 on B), so the trim is clearly measurement-driven rather than a fixed offset.

If that reading holds, a port that wants to be correct on *any* unit needs to
run the search, not just replay stored numbers. Replaying gets you a lit lamp;
the search gets you a balanced one.

### Which unit is this?

`docs/37` recovered the registry from the image builder's unit,
`ScannerSerialNumber 16275`, and left "read the serial off the physical
scanner" as an open action. `docs/55` then found the captured CCD dark offsets
agree with the stored ones to within one count (R −19/−18, G −26/−26, B −19/−20).
Combined with G matching the stored duty exactly, twice, the registry is almost
certainly **this unit's own**. Not proof — read the serial and close it.

### Using the script on a different scanner

`--levels` and `--duty` override the two per-unit writes; everything else stays.
The captured defaults are *conservative* for an arbitrary unit — levels
`3/11/7/0` sit below the registry's `5/20/11/4` and well under the ceilings — so
on another F-135 the likely failure is a dim or colour-shifted lamp, not an
over-driven one. The clamp check refuses anything out of range either way.

## Still open

- `LIGHT 0x06 [2]` `00 02` / `00 20` — 7 writes, tracks the scan.
- `LIGHT 0x87 [2] 00 00`, `0x89 [1] 00`, `t4 0x92`.
- `HOST 0x84 [1] 02` + `t4 LIGHT 0x8A` as a 20× poll pair — almost certainly the
  calibration wait, but the ack semantics are unread.
- Whether step 82's duties come from the registry `DutyCycleOpenGate_*` or are a
  search iterate. `docs/40`'s worked example gives duty_G ≈ 0.3808-0.3818 and
  the capture gives 0.3807 — **G agrees**, R and B do not, which points at a
  search in progress rather than a stored set.

Artefact: `~/pakon-findings/incoming/apmcap/process/0/data`.
