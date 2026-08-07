# 41 — Sensor inventory: what we can read, and what we still can't

A gap list. Answers "which sensors do we not have yet?" by enumerating every
register the vendor driver *reads*, and every sensor the vendor telemetry
*names*, then subtracting what is decoded.

Method: every call site of the register accessors in
`research/native/TLB.text.asm`, with the register constant recovered from the
preceding pushes; plus the log header rows carved out of the binaries on the VM
disk. `[VERIFIED-FROM-BINARY]` unless marked.

## Every register TLB.dll touches

Reads are sensors. Writes are actuators.

| reg | dir | accessor | what |
|---|---|---|---|
| `0x10` | R/W | GetRegWord / PutRegByte | documented in `docs/12` / `docs/03` |
| `0x28` | R/W | GetRegByte / PutRegWord | documented in `docs/12` / `docs/16` |
| `0x83` | **R** | GetRegByte | light-board status — **decoded**, `docs/39` |
| `0x84` | **R** | GetRegWord | lamp temp setpoint — **decoded**, `docs/39` |
| `0x88` | **R**/W | GetReg(4) | lamp + motherboard temps — **decoded**, `docs/39` |
| `0x93` | **R** | GetReg(4) | 4 bytes, 4 out-params — **decoded, `docs/43`**; paired with `0x96` |
| `0x96` | W | fcn.10009ee0 | 4 bytes — trim/pot write, pair of `0x93` (`docs/43`) |
| `0xea` | **R** | GetRegByte | **UNDECODED — byte, board `0x28`** |
| `0xef` | **R** | GetRegByte | **UNDECODED — byte, board `[this+0x2f8]`** |
| `0x80` `0x81` `0x82` | W | Put | LED enable / current / duty (`docs/15`) |
| `0x87` `0x89` `0x8b`–`0x8f` | W | Put | temperature bands, setpoint (`docs/15` §6c) |
| `0x97` `0xa5` `0xd0`–`0xd6` `0xff` `0x0a` `0x25` | W | Put | latch/enable, misc |

**Three read registers — `0x93`, `0xea`, `0xef` — appear in no document in this
repo.** Those are the concrete gaps.

## The three undecoded reads

### `0x93` — a four-value sensor bank. The biggest gap.

`fcn.1000a830` reads **4 bytes** from register `0x93` on the light board
(`[this+0x131]`) and hands them back as **four separate byte out-params**:

```
byte0 -> *arg1     byte1 -> *arg2     byte2 -> *arg3     byte3 -> *arg4
```

(`0x1000a880`–`0x1000a897`.) It is called from **15 sites**, all clustered in
`0x1002ad8c`–`0x1002b9c1`, each on the driver object at `[ebp+0x1c8]`. A single
read returning four independent bytes, polled from fifteen places, is a sensor
bank rather than a status word. Decoding it means working out what those 15
callers do with each byte — that is the highest-value next step here.

### `0xea` — a byte on a *different board*

`fcn.1000bd40`, immediately after the temperature monitor. Reads one byte, but
note the board address is the **literal `0x28`**, not `[this+0x131]` like every
lamp read. So this is a second board. On failure it ORs error bit `0x20` into
the caller's status word and logs message `0x62`.

### `0xef` — a byte on the board at `[this+0x2f8]`

`0x1002ea11`. Reads one byte from the board address held at `[this+0x2f8]` —
one of the two board-address bytes `docs/15` §9 identifies. Preceded by a
**1000 ms sleep** (`0x1002e9ec`), which says the read follows a state change that
needs settling. Logs message `0xd7` on failure.

## Sensors the vendor telemetry names

Two log header rows carved from binaries on the VM disk, with the matching
`printf` format row giving the types.

**Row A — the F-135 lamp log** (this is our machine's; `%d/%f/%u` types shown):

```
Time | FilmPresent | TempMB | TempLB | TempSetpoint | VisOn | IrOn |
Current_R | Current_G | Current_B | Current_Ir | Duty_R | Duty_G | Duty_B | Duty_Ir |
IntegrationTime
  %d     %d           %f       %f       %f          %d      %d
  %u        %u          %u        %u        %f      %f      %f      %f
  %u
```

This independently confirms `docs/39`: exactly three temperatures, all `%f`
(the ×0.0625 scaling), named setpoint / LB / MB. It also names one sensor we
have **not** located a register for:

* **`FilmPresent`** (`%d`) — **located, `docs/43`**: it is `[[this+0x28]+0x54]`,
  a cached host-side field, not a register read at all. The remaining question
  is which code path writes it.

**Row B — a richer telemetry set, from a different binary on the same disk:**

```
Time | Timer | TempAmbient | TempLocked | TempVisible | TempIr | BlowerRPM | FanRPM
TECooler_I | TECooler_DutyCycle | VisOn | IrOn | Current_R | Current_G | Current_B | Current_Ir
```

Sensors named here with no register mapped in TLB.dll at all:

| name | likely meaning |
|---|---|
| `TempAmbient` | ambient air temperature |
| `TempVisible` | visible-LED die/array temperature |
| `TempIr` | IR-LED temperature |
| `TempLocked` | thermal-lock achieved flag — **plausibly the missing stability predicate** `[this+0x298]` of `docs/39` `[INFERRED]` |
| `BlowerRPM` | blower tachometer |
| `FanRPM` | fan tachometer |
| `TECooler_I` | TEC current |
| `TECooler_DutyCycle` | TEC PWM duty |

**Attribute Row B before believing it applies to us.** `HKLM\SOFTWARE\Pakon\PSI
F235` exists in the recovered registry, so more than one scanner model is
represented in these binaries, and a TEC with blower and fan tachometers is
plausibly the larger F-235 rather than the F-135. Row A is the one carrying
`TempMB`/`TempLB`/`TempSetpoint` that `docs/39` decoded against real F-135
registers, so Row A is ours. Row B is a lead, not a fact. `[INFERRED]`

## The gap list, ranked

1. ~~`0x93`~~ — **done, `docs/43`.** It is a four-channel trim/measure pair with
   `0x96`, most likely the DX pots — and it does **not** carry `FilmPresent`.
   What remains is the channel→sensor assignment.
2. **`TempLocked`** — if it is a real F-135 field, it is the natural source of
   the stability flag `docs/39` could not find a writer for. Worth chasing
   together with the TLA.dll thread.
3. **`0xef`** — single byte, second board, 1 s settle. Small, self-contained.
4. **`0xea`** — single byte on board `0x28`. Smallest remaining unknown.
5. **`TECooler_I` / `TECooler_DutyCycle` / `TempAmbient` / `TempVisible` /
   `TempIr` / `BlowerRPM` / `FanRPM`** — only pursue after Row B is attributed
   to a model. If they are F-235 fields they are not our gaps at all.

## What is NOT missing

Worth stating, because it bounds the search: the lamp thermal path is complete.
Setpoint (`0x84`), lamp temperature and motherboard temperature (`0x88`), the
status byte (`0x83`), all eight supervision comparisons, and the abort mask are
decoded in `docs/39`. Nothing further is needed to read the scanner's
temperatures or to supervise the lamp safely.

## Correction (see `docs/43`)

This table's write column is a **lower bound**. It was built from a fixed list of
accessor functions; `fcn.10009ee0` was not among them, so register `0x96` was
missed entirely. Any register reached only through an unlisted accessor is
absent here.

---

## `0x93` probed on hardware — 2026-08-06

Polled at ~1.4 s while film was fed through the gate, 40 s, lamp off,
acquisition idle. Also polled `0xEF` on board `0x44` (which `FN_bInit3` reads
for film home) and the CCD mean.

```
distinct 0x93 values:  a8 f1 b3 f8 | a9 f1 b3 f8 | a8 f1 b2 f8 | 4f f1 b3 f8
distinct 0xEF values:  81   (constant throughout)
CCD mean:              1235.7 - 1237.0, flat
```

**Bytes 1 and 3 are constant (`f1`, `f8`). Bytes 0 and 2 vary.** Byte 0 sits at
`a8`/`a9` (168/169) and byte 2 at `b2`/`b3` (178/179) — ±1 jitter, which reads
as **analog sensor values, not digital flags**. One outlier: byte 0 dropped to
`4f` (79) at t+7.1 s, a large excursion.

**Inconclusive for `FilmPresent`.** No clean two-state transition appeared. Two
readings are possible and this run does not separate them: either `0x93` carries
analogue levels that need thresholding (the config does carry `DetectFilm_G` /
`DetectWhite_G` thresholds), or the film never reached whatever it senses.

`0xEF` did not move at all, so it is not a film-present flag — or film never
reached its sensor either.

Worth re-running with: a slower poll, film held stationary in the gate rather
than fed through, and a before/after comparison rather than a rolling log.

**Note on the log format used:** the `CHANGED` flag latched permanently after
the first difference, so it fired on every subsequent row including pure noise.
That made the output look far more eventful than it was. Compare against a
baseline, not against "has anything ever differed".
