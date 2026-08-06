# Reading the Pakon's PIC18F452 on the Intel Mac

You need: the **scanner**, the **PICkit 3**, and this laptop. Internet for one download.

Why the Intel Mac: MPLAB X for macOS is an x86 build and its USB library
(`libUSBAccessLink_3_36.dylib`) is x86-only. On Apple Silicon it runs under
Rosetta and fails to drive the programmer (`MPLABComm ... -109`). On an Intel
Mac it is native, which should just work.

---

## 1. Install MPLAB X

Download from the archive: <https://www.microchip.com/en-us/tools-resources/archives/mplab-ecosystem>

Any version from **v5.50 up to v6.20** — v6.20 is the LAST with PICkit 3
support. Take the macOS installer. Install the IDE (IPE comes with it).

You only need **MPLAB IPE**, not the full IDE. No compilers needed.

## 2. Wire the PICkit to the scanner

The header is **JM11**, the 5-pin one beside the 44-pin chip marked
`125507A 2208`. The board is silkscreened: **pin 1 left, pin 5 right**.

| PICkit 3 pin | JM11 pin |
|---|---|
| **1** (the ▲ arrow on the case) | 1 (left) |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |
| 5 | 5 (right) |
| 6 | leave unconnected |

Connect with the **scanner switched off**, then power the scanner on.
The scanner runs from its own supply — the PICkit does not power it.

## 3. Read

Open **MPLAB IPE**.

1. Device: `PIC18F452`  → **Apply**
2. Tool: the PICkit 3 (it will show its serial, `BUR195068601`)
3. **Connect** — should report the device ID and target voltage
4. **Read**
5. **File → Export → Hex**, save as `read-A.hex`

Then **disconnect and reconnect**, and do it again as `read-B.hex`.
Two independent reads. We compare them; if they differ, the read is not
trustworthy and we do not act on it.

## 4. DO NOT press

**Program. Erase. Blank Check.**

Read and Connect only. The chip holds a 1 KB bootloader that exists nowhere
else on Earth, and programming BULK-ERASES the entire device before writing.

## 5. Bring back

`read-A.hex` and `read-B.hex`. That is everything. The analysis runs on the
main Mac — `tools/flash_diff.py` takes any Intel HEX.

---

## If Connect fails

* **"Target voltage low/absent"** — scanner not powered, or VDD/VSS wiring.
  It stops safely before applying the 12 V, so nothing is at risk.
* **"Target not found" with good voltage** — power and ground are right but
  MCLR/PGC/PGD are not reaching the chip. Tells us JM11 is not what we assume.
* **"Could not connect to tool hardware"** — the programmer itself, not the
  target. That is the failure we get on Apple Silicon; if it happens here too,
  stop and tell me.

## Also in this folder

`pk2cmd/` — an open-source alternative (jaka-fi/pk2cmd, supports PICkit 3).
Not needed if MPLAB works. It requires the PICkit to carry "scripting"
firmware rather than MPLAB debugger firmware, which is why we are not
leading with it.
