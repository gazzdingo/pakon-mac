# 55 — The vendor's real CCD bring-up, captured from a live scan

> **INCOMPLETE — see `docs/59`.** The "46 distinct writes" below came from a
> regex that matched only 3-byte-payload packets, so every lamp, LED and
> threshold write was dropped. The real count is 126. The CCD table here is
> correct as far as it goes; the light board is in `docs/59`.

**Date: 2026-08-13.** Ground truth, not inference. Captured with API Monitor
hooking `DeviceIoControl` inside `PSI.exe` while it initialised the scanner.
This **supersedes the ordering** in `docs/42`, which was reconstructed
statically from `TLB.dll` and marked `[INFERRED]`.

## How it was captured

USB sniffing was a dead end on every route tried: SnoopyPro's filter driver
wedged the Windows USB stack twice and produced zero packets; USBlyzer's vendor
has gone (domain resold, no archived installer); and macOS exposes **no USB
capture interface at all** (no `XHC*` in `tcpdump -D`, no usbmon equivalent,
no USB packet-logger kext — only `IOBluetoothPacketLogger.kext`), so Wireshark
on the host cannot see the traffic Parallels passes through.

The commands do not have to be caught on the wire. `TLB.dll` builds them and
hands them to **`DeviceIoControl`** with `IOCTL_EZUSB_VENDOR_OR_CLASS_REQUEST`
(`0x222059`, `docs/13`), and `tlx.dll` is an **in-process** COM server — the
`F-X35 COM SERVER` directory contains only DLLs, no server `.exe` — so all of it
happens inside `PSI.exe`'s address space and is reachable from user mode.

API Monitor v2r13 (free, XP-compatible), `DeviceIoControl` filtered, attach mode
**Static Import** so the hook is live before any code runs. No kernel driver,
so nothing can wedge the USB stack.

Capture file format, for whoever needs it next: `.apmx86` is a text banner, then
the magic `RBAPM`, then a **plain ZIP** starting at offset `0xda`
(`PK\x03\x04`). Entries: `definitions`, `log/monitoring.txt`, `process/0/info`,
`process/0/calls`, `process/0/data`. The captured buffers are in
`process/0/data`; packets can be recovered directly with a regex for
`02 <len> <board> 03`. Each packet appears **twice** (pre- and post-call
buffer), so deduplicate consecutive identical writes.

## The sequence

92 raw hits, 46 distinct writes. Packet form is `02 <len> <board> 03 <reg>
<idx> <lo> <hi>` (`docs/16`), board `0x44` = CCD/motor, `0x40` = light.

```
 1   0x44  0x82 idx 6  = 0x0FFD    integration time -- the MAXIMUM bound
 2   0x44  0x82 idx 0  = 0x0060    mask word: bits 5,6 set
 3   0x44  0x82 idx 11 = 0x0000
 4   0x44  0x82 idx 4  = 0x003E
 5   0x44  0x82 idx 5  = 0x080E
 6   0x44  0x82 idx 1  = 0x0000
 7   0x44  0x82 idx 2  = 0x0000
 8   0x44  0x82 idx 3  = 0x0000
 9   0x44  0x82 idx 10 = 0x0400
10   0x44  0x84 idx 0  = 0x0078    A/D constants
11   0x44  0x84 idx 1  = 0x0080
12   0x44  0x82 idx 9  = 0x0014
13   0x44  0x82 idx 9  = 0x0017
14   0x40  0x91 idx 60 = 0x0100    LIGHT board, mid-sequence
15   0x44  0x82 idx 9  = 0x0313
16   0x44  0x82 idx 4  = 0x0006
17   0x44  0x82 idx 5  = 0x0807
18   0x44  0x82 idx 0  = 0x0061    ACQUIRE: bit 0 set on top of 0x0060
19   0x44  0x84 idx 2  = 0x000D    gain R = 13
20   0x44  0x84 idx 3  = 0x000D    gain G = 13
21   0x44  0x84 idx 4  = 0x000D    gain B = 13
22   0x44  0x84 idx 5  = 0x000A    offset R = +10   \
23   0x44  0x84 idx 6  = 0x000A    offset G = +10    |  dark-offset
24   0x44  0x84 idx 7  = 0x000A    offset B = +10    |  calibration loop
25   0x44  0x84 idx 5  = 0x011D    offset R = -29    |  (sign-magnitude,
26   0x44  0x84 idx 6  = 0x0126    offset G = -38    |   bit 8 = sign)
27   0x44  0x84 idx 7  = 0x011E    offset B = -30    |
28   0x44  0x84 idx 5  = 0x0115    offset R = -21    |
29   0x44  0x84 idx 6  = 0x011E    offset G = -30    |
30   0x44  0x84 idx 7  = 0x0116    offset B = -22    |
31   0x44  0x84 idx 5  = 0x0113    offset R = -19    |
32   0x44  0x84 idx 6  = 0x0119    offset G = -25    |
33   0x44  0x84 idx 7  = 0x0113    offset B = -19    |
34   0x44  0x84 idx 6  = 0x011A    offset G = -26   /   <- converged
35   0x44  0x82 idx 0  = 0x0060    acquire OFF
36   0x44  0x82 idx 4  = 0x0037
37   0x44  0x82 idx 9  = 0x0017
38   0x44  0x82 idx 9  = 0x0217
39   0x44  0x82 idx 9  = 0x0295
40   0x44  0x82 idx 0  = 0x0061    acquire ON
41   0x40  0x91 idx 60 = 0x0100    light board again
42   0x44  0x82 idx 9  = 0x0215
43   0x44  0x82 idx 0  = 0x0060    acquire OFF
44   0x44  0x82 idx 9  = 0x02D4
45   0x44  0x82 idx 9  = 0x00D4
46   0x44  0x82 idx 9  = 0x0017
```

## What this corrects in `docs/42`

`docs/42` got the **encoding** right and the **ordering** wrong. Anything built
on its sequence — including `~/pakon-findings/ccd_bringup.py`, which should not
be run — would have failed:

| `docs/42` said | actually |
|---|---|
| `0x82` mask `0x100` first, building to `0x0163` | **`0x100` is never written at all.** The mask word is `0x0060`, and acquire is `0x0061` |
| gains/offsets **before** the acquire bit | gains/offsets come **after** it (steps 19-34 follow step 18) |
| integration time a mid-range guess (`0x400` in my script) | **`0x0FFD`** — the maximum bound |
| `0x84` idx 0,1 = `0x78`, `0x80` | **confirmed** |
| offsets are sign-magnitude, sign in bit 8 | **confirmed** — `0x011D` = −29, `0x0126` = −38 |

It also reveals registers `docs/42` never knew about: `0x82` indices
**1, 2, 3, 4, 5, 9, 10, 11**, and a **light-board** write (`0x40` reg `0x91`
idx 60 = `0x0100`) interleaved into the CCD sequence at steps 14 and 41.

`0x82 idx 9` is written eleven times with varying values (`0x0014`, `0x0017`,
`0x0313`, `0x0217`, `0x0295`, `0x0215`, `0x02D4`, `0x00D4`) — a per-operation
parameter, not a one-shot setup value. `[UNKNOWN]` what it selects.

## Independent confirmation of the recovered calibration

Steps 19-34 are the vendor's live **dark-offset calibration loop**: it starts at
`+10, +10, +10` and converges by successive approximation. Compare the endpoint
against the per-unit values recovered from the VM registry in `docs/37`:

| | R | G | B |
|---|---|---|---|
| captured, converged (this doc) | **−19** | **−26** | **−19** |
| registry `Offset_R/G/B` (`docs/37`) | −18 | **−26** | −20 |
| registry `Gain_R/G/B` (`docs/37`) | 13 | 13 | 13 |
| captured gains (steps 19-21) | **13** | **13** | **13** |

Gains match exactly. G offset matches exactly; R and B land within one count of
the stored values — the difference being where this run's convergence stopped.
Two completely independent routes — carving a Windows registry hive out of a
VM disk image, and hooking a live scan — agree. `docs/37`'s recovered
calibration is correct.

## Why `start_acquire.py` never worked

It writes `0x82 idx 0 = 0x0001` and nothing else. The vendor's acquire word is
**`0x0061`** — bit 0 *plus* the `0x0060` base — and it only means anything after
integration time, the idx 1-5/9-11 setup and the A/D constants are in place.
Setting bit 0 alone on a bare register does nothing, which is exactly the
"un-armed acquisition" the stream showed: EP `0x86` pinned at ~1245 with no gain
response.

## Next

Rewrite the bring-up from this table rather than from `docs/42`, sampling EP
`0x86` after each step. The open question is `0x82 idx 9`, and whether the
light-board write at step 14 is a prerequisite for the sensor to respond.

Artefacts: `~/pakon-findings/incoming/caputre.apmx86` (raw capture),
extracted tree under `apmcap/`.
