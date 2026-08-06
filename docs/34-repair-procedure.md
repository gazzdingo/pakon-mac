# U34 repair — diagnosis, artifacts, procedure

Status: **image built and verified; nothing programmed yet.**
Date: 2026-08-06. Supersedes the chip-replacement plan in `docs/31`.

---

## 1. The fault, proven

U34 (PICM, PIC18F452) is **alive**. Every earlier ICSP failure was connection
quality; with a good connection it reads first time (`Revision ID 7`). Six reads
taken, five in agreement (pass B dropped mid-read, excluded).

Its flash has **exactly one erased 64-byte row at `0x000D00`–`0x000D3F`**.

```
application vs nm0506.HEX : 10616 bytes compared, 64 mismatch
all 64 inside 0x0D00-0x0D3F, 64-byte aligned, chip reads clean 0xFF
```

That is the exact footprint of one PIC18 row-erase. Everything else is intact —
`0x400`=`EFE1`, `0x1A8C`=`0E36` (SSPEN), `0x1A90`=`C134`, `0x2C62`=`0E44`
(the I²C address), `0x2C64`=`0101`, `0x2C66`=`6F34`.

### Why that one row kills the board

The row sits inside the cold-boot BIST's shift-register loopback test
(`0x0CAC`–`0x0D7A`). Read the vendor bytes for the row and the mechanism is
self-evident — **the loop's only exit lives inside the erased row**:

```
0D18: 2B3F  INCF  0x3F        loop-1 counter
0D1A: D7E2  BRA   0x0CE0      loop-1 back-edge
0D1C: 6B3F  CLRF  0x3F        reset counter for loop 2
0D1E: 513F  MOVF  0x3F,W      loop-2 exit test ...
0D20: 080F  SUBLW 0x0F        ... 16 iterations ...
0D22: E31F  BNC   0x0D62      ... and the only way out
```

With the row reading `0xFF`, `0x0D1E`–`0x0D3E` execute as NOPs. Execution slides
into the surviving code at `0x0D40`, runs down to `0x0D60` (`BRA 0x0D1E`) — and
lands back at the top of the NOP slide.

**A closed infinite loop, with the surviving `CLRWDT` at `0x0D42` inside it**, so
the watchdog can never break out. Verified by direct inspection of `nm0506.HEX`:
`0x0D40`=`2B3E`, `0x0D42`=`0004` (CLRWDT), `0x0D60`=`D7DE` (BRA 0x0D1E).

Reachability: reset `0x0400` → `0x2BC2` → `0x1746` → POR branch `0x1956` → BIST
`0x1990` → `0x0FCE` → `0x136C` → `0x13B8` → `BRA 0x0CAC`. The MSSP is armed at
`0x1A8C` only after that chain returns at `0x1A16`.

**So the hang happens strictly before I²C is armed, and only on POR.** That also
explains the one thing `docs/22` never could: in-session warm restarts worked
(BIST skipped), every cold boot went silent.

Nothing else needs to be wrong. This single row explains every symptom.

## 2. What erased it — do not repeat this

Three facts narrow it decisively:

1. **The application cannot write flash at all** — no `TBLWT` anywhere, never
   sets `EECON1.EEPGD`. The only row-erase code on the chip is the bootloader's
   command-4 handler.
2. **The bootloader's guard permits it**: the write guard rejects addresses
   `<= 0x3FE` (`SUBLW 0xFE` at `0x234`). `0x0D00` is application space —
   erasable on command, by design.
3. **The window is bounded**: after the `docs/22` cold boot neither `0x44` nor
   `0x46` ever ACKed again, and ICSP reads do not erase. It died during the
   bootloader era.

The mechanism class, read out of U34's own dispatch code: **any 2-byte type-4
packet to `0x46` whose command byte has bits 3+2 set (`0x0C`–`0x0F`) is accepted
by the bit-3 length rule and dispatched as a row erase at the currently latched
address** — erase is tested first. Likewise `0x0A`/`0x0B` writes 16 stale RAM
bytes and `0x08`/`0x09` exits the bootloader.

So `04 03 46 00 0d` is one byte away from a presence probe and is a row erase.
The address latch persists and auto-increments across reads, so any freeform
probing at `0x46` after a read near `0x0D00` fits exactly. No session log
survives to name the packet; **the class is certain, the instance is not.**

> Current tools are clean — `picm_read_flash.py` sends a literal `0x07`,
> `catch_bootloader.py` sends only `00 00` probes — but nothing *asserts* it.
> Add that assertion before any I²C session.

Corollary: `docs/22`'s theory that the vendor erases the vectors on bootloader
entry **cannot be right** — no code on the chip erases anything on entry.

## 3. Artifacts (all verified, none programmed)

Built by `build/build_u34_repair.py`. Everything comes off **this chip** except
the application.

| File | sha256 | Purpose |
|---|---|---|
| `build/u34-repair.hex` | `b37a9bf8…` | Full device, app runs on first power-up |
| `build/u34-repair-staged.hex` | `7a2bd9a7…` | Same, but EEPROM[0]=`0x00` → parks in bootloader |
| `build/u34-stage-eeprom.hex` | `4fb721eb…` | 256 EEPROM bytes only — the staging write |

| Region | Source |
|---|---|
| `0x0000`–`0x03FF` bootloader | U34's own read, 705 non-`0xFF` |
| `0x0400`+ application | `nm0506.HEX`, 10616 bytes (carries the `0x0D00` row) |
| config | U34's own — `CONFIG2H=0x09`, **not** nm0506's `0x0D` |
| EEPROM | U34's own, 256 bytes |

**Independently verified** (separate strict HEX parser, shares no code with the
builder — checksums, record lengths, duplicate detection):

- bootloader 0 mismatches; application 10616/10616 identical to nm0506 including
  the full `0x0D00` row; config exactly 14 bytes; EEPROM 256/256
- **0 bytes invented, 0 missing** — every byte attributable to its declared source
- post-programming simulation: device would differ from its current state in
  **exactly the 64 repair bytes and nothing else**
- upper flash `0x2D7C`–`0x7FFF` and ID `0x200000`–`07` are `0xFF` on the chip, so
  a bulk erase loses nothing there
- `u34-repair-staged.hex` differs from `u34-repair.hex` in **exactly one byte**
  (`0xF00000`: `AA`→`00`); `u34-stage-eeprom.hex` is 256 bytes, all `>= 0xF00000`,
  differing from the chip in that same single byte. EEPROM index 5 stays `0x00`
  (no-fault) in both.

### Config: keep the chip's `0x09`

`CONFIG2H` `0x09` = WDT on, postscale 1:16 (~290 ms); vendor `0x0D` = 1:64
(~1.15 s). Every other byte is identical. Keep `0x09`: this chip ran this exact
firmware on it for two decades, U11 also reads `0x09` (so it is Kodak's
production value), and the postscale is irrelevant to this fault either way —
the hang loop feeds the watchdog. Writing `0x0D` would be the one invented byte
in an image whose entire argument is that nothing is invented.

### New finding: U34's bootloader is its own build

It is **not** U11's with six patches — registers moved to `0xC4`–`0xD5`, plus a
delay subroutine and new PORTD/TRISD parking code. The `docs/31` synthesis plan
is obsolete. Its protocol analysis is confirmed against the real code, though:
I²C literal `MOVLW 0x46`, EEPROM[0]==`0xAA` gate → `GOTO 0x400`, the write guard
above, identical command interlock and dispatch order.

## 4. Procedure — staged, never erases anything

**Do not lead with bulk-erase ICSP programming.** The one demonstrated failure
mode of this setup is the ICSP connection dropping mid-operation (it already did,
on pass B), and bulk erase is the only path where the chip is ever blank —
including the bootloader, of which our read is the only copy in existence.

The row is **already `0xFF`**, and PIC18 programming only clears bits, so the
repair needs **no erase command at all**.

**Phase 0 — prep.** Confirm off-machine copies of `backups/u34-picm/`. Fix
`tools/flash_picm.py:242` (`read_block()` still uses the broken single-packet
form — its verify pass will abort as written) and give it a start-address option
(chunks currently always begin at `0x400`). Assert that any type-1 fetch to
`0x46` uses command byte `0x07` exactly.

**Phase 1 — ICSP, EEPROM only.** The only ICSP write in the whole plan.
Fresh `-GF` read, diff against `u34-full-A.hex`, then:

```
ipecmd -P18F452 -TPPK3 -Fbuild/u34-stage-eeprom.hex -ME -OH -OD -OV
```

`-OH` is **load-bearing** — verified against the installed binary's own help,
which uses the same three-column convention that settled the `-W` question:
`OH | Erase All Before Programming (Not Selected) | Selected`. The default *is*
erase-all; `-OH` deselects it. `-OV` verifies device ID first. `-OD` is
VDD-before-VPP. **Never pass `-W`** — that means "power target from tool".

Re-read with `-GF` and diff. Expected: **one changed byte** (`0xF00000` AA→00).
If the tool misbehaves and erases flash, nothing is lost — that is simply the
fallback's starting point, with full backups in hand.

**Phase 2 — power cycle.** Chip parks in its own bootloader at `0x46`, pins in
Kodak's designed safe state (PORTD/TRISD parked, wait on RB5, RD6/RD7 raised,
everything else high-Z). This state was observed harmless on this board for days
during the `docs/20` era. Confirm presence via the control-address method.

**Phase 3 — I²C repair. No erase command is ever sent.** Four command-2 packets
(16 bytes each, each carrying its own address) for `0x0D00`/`0x0D10`/`0x0D20`/
`0x0D30` from `nm0506.HEX`. Then read back `0x0000`–`0x2D7B` over command 1 and
byte-compare — that verifies bootloader, application and repair in one pass, on
the vendor's own path, with nothing at risk. This exact path already worked on
this chip during the vector repair.

**Phase 4 — supervised start.** `04 03 46 00 08` → app runs (warm, BIST skipped)
→ confirm `0x44` ACKs → `02 05 44 02 0a 00 aa` → power cycle → cold boot runs the
repaired BIST → confirm `0x44` ACKs.

Note the sequencing: the cmd-8 first run takes the warm path and **skips the
BIST**. The repaired row first executes on the first true power cycle — which is
the ordinary cold boot every F-135 performs.

**Fallback**, only if the I²C leg proves unavailable: full ICSP program of
`u34-repair-staged.hex` (prefer staged even here), default erase+program, then an
independent `-GF` read diffed against the image file — not merely IPE's own
verify.

### Why stage rather than run immediately

`EEPROM[0]=0xAA` means the application runs unsupervised at first power-up after
programming, and this board drives motors. Staging converts that into "runs when
commanded, host attached", and buys a free end-to-end verification: the
bootloader's command-1 reads are unguarded, so **the entire flash including the
bootloader region can be read back over I²C before the app ever executes**.

The cost is small and reversible — if I²C were unexpectedly dead, one ICSP
EEPROM-only write restores `0xAA`. The un-stage path is the vendor's own.

## 5. Risks, ranked

1. **Bulk-erase ICSP programming** — the only path where the chip is ever blank,
   on a connection that has already dropped once. The procedure above never
   erases anything, anywhere.
2. **A forgotten `-OH`** on the staging write would blank the chip. Recoverable
   from backups, but avoidable; verify by read-back immediately after.
3. **The `0x46` two-byte command class** (`0x0C`–`0x0F` erase, `0x0A`/`0x0B`
   write, `0x08`/`0x09` exit) — almost certainly what destroyed this row and the
   vector rows. Never send unvetted command bytes to `0x46`. Keep `WRITES_LOCKED`
   engaged until the session plan is agreed. (Its text still calls flash_picm's
   target "U11" — stale, worth fixing.)
4. **`flash_picm.py:read_block()` is still broken** and cannot target a single
   row. Fix both, or use a minimal dedicated script for the four writes.
5. **A sparse EEPROM file** would risk a padding tool wiping index 5 (`0x00` = no
   fault) to `0xFF` (= fault `0xF` on the LED). All three artifacts deliberately
   carry the full 256 bytes.

---

## 6. LIVE STATUS — 2026-08-06, mid-procedure. READ THIS FIRST.

**U34's flash is currently BLANK.** Fully recoverable; the image is on disk.

### What happened

1. Device ID read: `PIC18F452 found, Revision ID 7`, target voltage detected.
2. Full `-GF` read → **bit-identical to `u34-full-A.hex`** (sha256 `c786015b…`,
   11160 non-`0xFF` bytes). Saved as `backups/u34-picm/u34-full-G-preflash.hex`.
   That is a 7th agreeing read.
3. Ran Phase 1 exactly as written:
   `ipecmd -P18F452 -TPPK3 -Fbuild/u34-stage-eeprom.hex -ME -OH -OD -OV`
4. The tool printed **`Device Erased...`** and then programmed EEPROM.
5. Read-back: flash **blank** — 20 non-`0xFF` bytes left, `EEPROM[0]=0x00`
   (the staging byte did take). Saved as `u34-full-H-postbulkerase.hex`.

### The finding — correct this in the procedure

> **`-OH` does NOT suppress erase-all on ipecmd v5.50 with `-ME`.**
> The help text's three-column reading was right about the flag's *meaning*;
> the tool simply does not honour it in this combination. A region-scoped
> `-M<region>` program still bulk-erases the device first.

**Consequence: there is no "EEPROM-only write" on this toolchain.** The staged
I²C procedure in §4 loses its safety advantage over ICSP, because reaching the
staged state itself costs a full erase. Any ICSP write here is a full-device
write, so the only safe form is: program the complete verified image, always.

Fable flagged uncertainty about `-OH` and was right to. My verification
established what the flag means, not that it is obeyed — those are different
claims and only the second one mattered.

### Recovery — the pending action

Program the full verified image. Nothing is lost; `u34-repair-staged.hex`
contains bootloader + application (with the row repaired) + config + EEPROM.

```
ipecmd -P18F452 -TPPK3 -Fbuild/u34-repair-staged.hex -M -OD -OV
```

Staged (`EEPROM[0]=0x00`) so the board returns parked in its bootloader rather
than driving motors unsupervised. Then read back and diff against the image.

**Current state is safe to leave**: blank flash simply does not run. No motor
can move. The board may sit like this indefinitely.
