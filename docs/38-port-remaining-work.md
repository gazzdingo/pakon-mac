# What is left to finish the macOS port — 2026-08-06

Written the day U34 was repaired and the lamp calibration recovered. Both
changed the shape of the remaining work, so this supersedes the status table in
`docs/06-roadmap.md`.

**Correction to `docs/06` first:** its stage-4 row reads "lamp visually
confirmed". That is wrong and `docs/14-lamp-decoded.md` supersedes it — the
board ACKs the enable and the illuminant stays dark. Do not plan against that
row.

## Where it actually stands

| Stage | Status |
|---|---|
| 1. Enumerate + load FX2 firmware | **done**, automated, no kext |
| 2. Command round-trip | **done**, both PIC boards answer |
| 3. Scanner identity / registers | partial — reads work, semantics thin |
| 4a. Motor / transport | **done today** — verified turning |
| 4b. Lamp | blocked → now *probably* unblocked, see below |
| 5. Acquire scan lines | the old blocker; **status changed today** |
| 6. Strip scan → file | not started |
| 7. Imaging pipeline | **done and verified** |
| 8. Packaging | not started |

Stage 7 landing before 4–6 is unusual but deliberate: the colour work needed no
hardware and is the part that actually distinguishes this scanner.

## The three things that changed today

1. **U34 (PICM, the motor board) was repaired.** One erased 64-byte flash row
   restored. Motor confirmed turning; both boards answer on I²C.
2. **EP 0x86 now looks different.** `docs/06` recorded it pinned near a dark
   baseline of ~1242 and unresponsive — the reason stage 5 was "THE BLOCKER".
   It now reads mean ~2531 with a real distribution (min ~1092, max ~3486).
   **PICM drives CCD timing**, so the repair is a plausible cause. Unverified.
3. **This unit's LED calibration was recovered** from a Windows registry hive
   carved out of a VM disk (`docs/37`, `research/windows-registry/`).

Points 1 and 2 together are the important part: **stage 5 may have been blocked
by the broken chip all along**, not by a missing command. That reframes the
single largest unknown in the project.

## Remaining work, in dependency order

### A. Light the lamp — in progress
Calibrated `Current_*` and `DutyCycle_*` are in hand. Two open questions, both
static and answerable offline (Fable is on them):
* is setpoint programming gated on `UseTemperatureSetpoints = 0`, which would
  mean `docs/14`'s "setpoints are the blocker" no longer applies;
* **how do registry values become register payloads** — `Current_R = 5` and
  `DutyCycle_R = "0.917161"` must become bytes in `0x81` (5 B) and `0x82`
  (12 B). Scale, layout, channel order and the 5th byte of `0x81` are all
  undetermined. Right numbers in the wrong encoding are as damaging as wrong
  numbers.

### B. Establish what EP 0x86 is actually carrying — do this next, it is cheap
Pure reads, no risk, and it may retire the project's oldest blocker:
* is the new distribution structured (line sync, per-channel interleave) or
  noise? Autocorrelate for a repeating line length.
* does it respond to a physical light change — open the gate, shine a torch,
  compare means. That is the light-meter test `docs/06` used, now worth
  re-running against repaired hardware.
* does it change when the motor runs?

**Do B before A if the lamp answer is slow.** It needs no calibration data and
no writes, and a positive result changes the plan for everything after it.

### C. CCD initialisation and acquisition
`tools/init_ccd.py` and `tools/start_acquire.py` exist and are interlocked.
`FN_bDrvCcdAcquireControl` sets bit 0 of CCD register `0x82` (`docs/12`).
Needed: confirm what must be programmed before acquisition is meaningful —
`Gain_R/G/B` (13/13/13) and `Offset_R/G/B` (−18/−26/−20) are now known per mode
from the registry, which is new.

### D. Scan-line framing
Find the sync marker in the EP 0x86 stream and recover line length, channel
order and bit packing. Note `docs/06:139` — the FIFO free-runs and stalls full
of stale data, so it must be flushed before any measurement is trusted.

### E. Transport choreography
Motor primitives work (`0xA5` speed, `0xA0/0xA1` run, `0xA2` stop). Needed:
frame detection, film-present sensing (`FilmPresent` appears in TLB.dll's
strings), and the advance/settle/scan loop. Registry gives real per-mode motor
values: `MotorSpeedPlus/_Ir` 5917/4850, 11467/7580, 25802/19335,
`MotorAdjust` 1000, `MotorAdjustDrag` 1008.

### F. Assemble frames and hand off to the colour pipeline
The pipeline is done and verified to 0.000050 against the vendor tables. This
step is plumbing: lines → frame buffer → `tools/pakon_color.py` → 16-bit TIFF.
**This is where the project starts producing photographs.**

### G. Packaging
A CLI that runs a whole roll end to end, then whatever UI is wanted. Nothing
here is research.

## Known gaps worth closing separately

* **The scanner EEPROM is only partly read.** `0x52` is one 256-byte page; the
  driver reads a 398-byte section, and our page contains none of the documented
  motor fields. Other pages (`0x53`+) are unread. One read per power cycle —
  see `backups/eeprom-i2c/README.md`, these parts degrade silently after the
  first read.
* **`PakonLampLog.txt` was never recovered** — it needs NTFS parsing of the same
  VM disk image the registry came from.
* **Read the physical unit's serial.** If it is 16275, the 2022 registry
  calibration is also ours and we gain a `DpiBase8` set we currently lack.
* **`DpiBase8_35` has no 2025 calibration** — this unit was only calibrated at
  bases 4 and 16.

## Honest assessment

The hard reverse-engineering is done: protocol, firmware loading, colour
science, motor control, and now a repaired machine that answers. What is left is
mostly **sequencing and format work against a scanner that finally responds** —
different in kind from the last several months, which were spent fighting a
chip with a hole in its flash.

The single highest-value next action is **B**, because it is free, it is
read-only, and it may retire the oldest blocker in the project.
