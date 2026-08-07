# Lamp-on: the setpoint blocker is gone, and the exact sequence — 2026-08-06

Static analysis of TLB.dll (536,576 B, MD5 `e7f21021e0140c1935a3ae4de7bd3498`),
full linear disassembly of `.text`, exact esp tracking, raw-byte pointer scans
for xref completeness.

**`docs/14`'s "the setpoints are the blocker" conclusion does not survive.**

## 1. The gate — verified at two independent sites

With `UseTemperatureSetpoints = 0`, which is how this install ran, the vendor
**never writes reg `0x8E`** — the TEC working setpoint:

```
0x1002d33b  mov  eax, [esi+0xb4]      ; UseTemperatureSetpoints
0x1002d341  test eax, eax
0x1002d343  je   0x1002d369           ; flag==0 -> SKIP the 0x8E write
0x1002d347  mov  cx, word [esi+0xc0]  ; LampTempWorking
0x1002d357  push 0x8e
0x1002d360  call 0x1000a9e0           ; PutRegisterWord
0x1002d369  ...                       ; join: 0xD0 <- 00, 0xD1 <- 01
```

Refinement of `docs/14`: the flag does **not** skip "the `0x8B`–`0x8F` writes".
`0x8F`, `0x8C`, `0x8B`, `0x8D`, `0xD0`, `0xD1` are written *unconditionally* —
they are **monitor thresholds**, not TEC commands. Only `0x8E`, the one register
that commands a TEC target, is gated.

Second gate: the config loader `fcn.10010cc0` skips every thermal registry read
when the flag is 0 (`0x1001101f je 0x10011236`), leaving the threshold fields at
constructor defaults.

**Hive cross-proof.** `fcn.1000c940` *creates* missing registry values on read.
The hive contains `UseTemperatureSetpoints`, `WaitForLamp_*` and
`WriteLightStabilityLog` — but **no `LampTemp*` or `MotherBoardTemp*` values at
all**. That absence is only possible if the flag=0 branch actually executed on
the vendor install.

## 2. Why stability can be reached without setpoints

`FN_bLampTemperatureStable` is still required by the pre-scan path
(`fcn.10021590`, unconditional). But it passes on `[driver+0x298] > 0`, and the
complete write set of that field contains **no temperature comparison**: it is
driven by bit 1 of the light board's **event register `0x02`** (`0x1000b951`)
or of **status reg `0x83`** (`0x1000ba1b`), then set to 1 unconditionally on the
next monitor pass (`0x1000b970`).

The reference the monitor compares against is **the setpoint the light board
echoes back in reg `0x84`** — the firmware runs its own default and reports it.
The host never needs to supply one.

## 3. Registry → wire, exactly

`FN_bDrvLampOn` = `fcn.1002c5f0`.

```
reg 0x81, 5 B   [level_B, level_Ir, level_R, 0x00, level_G]
reg 0x82, 12 B  six LE u16: [on_B][on_Ir][on_R][0x0000][on_G][N]

N_float = exposure * 1e6 / (2 * clock)      clock = 2,083,333.3  ([root+0x450])
N       = trunc(N_float)
on_ch   = trunc(floor(N_float * duty_ch))   clamped to <= N-2
```

Duties go on the wire as **PWM on-counts**, not scaled bytes. There is no other
scale factor. Note the channel order is **B, Ir, R, –, G** in both registers,
and byte 3 of `0x81` is a hard zero.

Which duty set: `FN_bBeforeScan` passes **`DutyCycleOpenGate_*`** for the
no-film case and `DutyCycle_*` for with-film. Open-gate is correct — and lower
power — for a first light.

### Two corrections to `docs/15`

Both because the doc recovered the **legacy** scanner's values, not the F-135's:

* **§5b clock.** The "×0.6" factor is legacy. `[root+0x450]` initialises to
  2,083,333.3; the 833,333.3 constant is stored only by `fcn.10011510`, whose
  single call site is the legacy `0x24/0x20` discovery path. For the F-135
  (`0x44/0x40`): **N = trunc(exposure × 0.24)**.
* **§3 exposure table.** 2323/1549/3485/4080/3098 is legacy-only. The F-135
  values, written by `fcn.10011a60`:

| DPI base | non-IR | IR |
|---|---|---|
| DpiBase4_35 | 1875 | 1250 |
| DpiBase8_35 | 2813 | 2128 |
| DpiBase16_35 | 4093 | **2498** |

## 4. Clamps — our values are mid-scale

`fcn.100203c0`, selected by `[this+0x2f8]==0x44`:

```
IR on   R<=8   G<=24  B<=24  Ir<=8
IR off  R<=4   G<=20  B<=20  Ir<=0
```

Ours (5/20/11/4) sit at **63 % / 83 % / 46 % / 50 %** of their ceilings. The
calibration search stopped on CCD targets, not on the clamps — healthy.

The `cmp edx, 0x9c40` in `docs/15` compares the **maximum pixel of an averaged
CCD line** against 40000. It is an IR *sensor target*, not a current.

## 5. The sequence — ColNegIr @ DpiBase16_35, open gate

exposure 2498 → `N_float = 599.5200`, `N = 599 = 0x0257`, `N−2 = 597`;
on_R=394, on_G=228, on_B=100, on_Ir=531 — all ≤ 597.

Board `0x40`, expect `07 02 40 00` after each:

```
1  02 04 40 01 80 00                                    lamp off, known state
2  02 0F 40 0C 82 64 00 13 02 8A 01 00 00 E4 00 57 02   PWM on-counts + N
3  02 08 40 05 81 0B 04 05 00 14                        levels B,Ir,R,0,G
4  02 04 40 01 80 03                                    enable visible+IR
   wait ~5 s   (WaitForLamp default 5.0, hive confirms 5.000000)
5  poll 0x83 status; 0x88 = [TempLB u16][TempMB u16], 1/16 degC
   sanity: TempLB within +-2 degC of the u16 echoed in 0x84; TempMB 10-55 degC
6  02 04 40 01 80 00                                    lamp off
```

**More conservative first light — visible only:** step 2 payload
`64 00 00 00 8A 01 00 00 E4 00 57 02`, step 3 `0B 00 05 00 14`, step 4 mask `01`.

**Never send reg `0x8E`.** No per-unit `LampTempWorking` exists for this
scanner, and the vendor never sent it either.

`0x8B/0x8C/0x8D/0x8F` + `0xD0=00`/`0xD1=01` are optional monitor thresholds
(flag=0 defaults: `8F: E8 FF 18 00`, `8C: E0 FF 20 00`, `8B: F0 00 20 03`,
`8D: A0 00 70 03`). Send them first only if you want vendor-faithful bring-up.

Our host has no monitor thread, so **time-box the first light to seconds and
watch TempLB**.

## 6. Corroboration that the values belong to this code

`fcn.1001e020`'s open-gate estimate `base_ch × (n−1)/n`, with the film-colour
attenuations and n = 5/20/11/4, predicts duties **0.574 / 0.378 / 0.175 /
0.750**. Stored `DutyCycleOpenGate` is **0.658 / 0.380 / 0.167 / 0.887** —
matching to 0.6 % on G and 5 % on B, with R and Ir refined further by the CCD
search.

Registry values, currents, and the code's own formula are mutually consistent.
That is independent of the timestamp argument and of the owner's confirmation.

## 7. One weak leg, called out

Fable's report says the flag=0 path is "proven empirically, twice", one of which
is *"this project's own operator-confirmed lamp-on"*. **Discount that one.** It
traces to `docs/06`'s stage-4 row ("lamp visually confirmed"), which
`docs/14` supersedes and which `docs/38` corrected today — the lamp has never
lit in this project.

The conclusion does not depend on it. The remaining evidence is strong:

* the gate instructions themselves, read directly;
* the **absence** of `LampTemp*` values in a hive whose loader creates them on
  read — only possible if flag=0 executed;
* **the five 2025 calibration keys exist at all.** `FN_bCalibrateFindLedCurrent`
  must light the lamp and measure CCD response to produce them. So the lamp
  demonstrably lit *on this unit*, with this flag at 0, in July 2025.

That third point is the strongest single piece of evidence in the whole
analysis, and it is independent of any claim made inside this project.

---

## 8. Reconciled with the independent disk-image analysis

Two analyses reached the same conclusions from different evidence: this one from
a full disassembly of TLB.dll, the other from scanning the 11.8 GB VM image and
its hives. They agree on every material point.

| Claim | Disassembly | Disk image |
|---|---|---|
| `0x8E` gated on `UseTemperatureSetpoints`, flag=0 → never sent | `0x1002d343 je` | §6a field map ends at `+0xb4` |
| Stability is not a host thermal comparison | `[driver+0x298]` write set has none | `FN_bLampTemperatureStable` polls a board-set flag |
| No per-unit temperature calibration exists | ctor defaults only | **zero occurrences** of `LampTemp*`/`MotherBoardTemp*` in 11.8 GB |
| `WaitForLamp` = 5.0 s | ctor `.rdata:0x1005d388` | hive value `"5.000000"` |
| `LampTempWorking` | ctor 640 = 40.0 °C | clamped `[592,768]` = 37–48 °C |

The clamp point is the decisive one: **a per-unit calibration would not be
forced into a fixed window.** It is an operating limit, not a measurement. The
host does not own the thermal loop — the light board regulates and the host
waits.

### Corrections that fell out

* **`docs/36` was wrong** and it was mine: it listed `TempSetpoint`, `TempLB`,
  `TempMB` as registry targets. They are **log column headers** — fields of the
  light-stability log, in a tab-separated run inside a binary string table.
  Telemetry names, never keys. That sent the first registry scan down a dead
  end.
* `WriteLightStabilityLog = 0`, so that log was never written — which is why no
  `PakonLampLog.txt` exists anywhere on the disk. **That item is closed, not
  outstanding.**
* **`docs/15` §6a** infers the subkey as `Software\Pakon\TLB\Test`. It is
  `HKLM\SOFTWARE\Pakon\TLB\Scan\Test`.
* The temperature fields sit under `CiConfigTest` — the engineering/diagnostics
  block (`DrawDxLines`, `LockSteppers`, `UsePpbDebugTraces`, `HighWaterTest`) —
  because they are **service overrides for a loop the board runs itself**, not
  calibration.

## 9. Better first light: search from below instead of injecting values

`FN_bCalibrateFindLedCurrent` re-derives the currents rather than reading them:

```
n = 1
loop:  lamp on at n -> acquire a line -> take max pixel
       if max >= target: stop
       n += 1                        range [1, 24], one byte on the wire
targets:  R 64000   G 64000   B 65500   Ir 40000
```

**This is a safer first light than sending 5/20/11/4 directly**, and it is what
the vendor does:

* it **starts at minimum current and steps up**, so it is safe from below —
  overdrive is not reachable, the loop stops the moment it exceeds target;
* it needs no trust in our recovered encoding before any current flows;
* it **self-validates**: if a fresh search converges near 5/20/11/4 for
  `ColNegIr`, the recovered calibration is confirmed against the physical unit,
  and the serial question answers itself for free.

It does require working CCD acquisition (`docs/38` §B/C), so it is gated behind
that. Until acquisition works, the recovered values plus the §5 sequence remain
the route — but if acquisition lands first, prefer the search.

**Recommended order:** characterise EP 0x86 → get a line read → run the search
from n=1 → compare against 5/20/11/4. That reaches first light without ever
trusting a number we did not measure on this machine.
