# 43 — Register `0x93` decoded, and where `FilmPresent` actually comes from

Follows the gap list in `docs/41-sensor-inventory.md`. Two results and two
corrections. `[VERIFIED-FROM-BINARY]` unless marked.

## 1. `0x93` is half of a read/write pair — and `0x96` was missing from doc 41

`fcn.1000a830` reads register **`0x93`**, 4 bytes, from the light board
(`[this+0x131]`), and returns them as four independent byte out-params
(`0x1000a880`–`0x1000a897`). Logger id `0x58`.

Its counterpart: `fcn.1000a950` writes register **`0x96`**, 4 bytes, same board,
four values (`0x1000a97b`). Logger id `0x57` — adjacent to the reader's `0x58`,
which is how a Get/Put pair is numbered throughout this driver.

**`0x96` does not appear in `docs/41`'s register table.** That table was built
from a fixed list of accessor functions and `fcn.10009ee0` was not in it, so any
register reached only through that accessor was missed. Treat doc 41's write
column as a lower bound, not a complete set.

## 2. What the pair does — a four-channel closed-loop trim

The 15 call sites of the reader all sit in `0x1002ad6a`–`0x1002b9c1`, in a
repeating pattern:

```
read  0x93   -> four bytes
call  fcn.1002a7e0  with four constants (e.g. 0xffffffe1 = -31)  -> writes 0x96
read  0x93   -> four bytes again
... repeat with different constants
```

Four channels, measured and then trimmed, iteratively. The trim constant `-31`
is the bottom of a **±31 range**, i.e. a 6-bit signed control — the signature of
a digital potentiometer.

**Most likely `FN_bDrvDxGetHardware` / `FN_bDrvDxPutHardware`, driving the DX
sensor pots.** `[INFERRED]` The supporting evidence is circumstantial but
consistent: the FN list contains `FN_bAdjustDxPots`, `FN_bDrvDxChangePots`,
`FN_bDrvDxGetHardware` and `FN_bDrvDxPutHardware`; a pot-adjust routine is
exactly a measure/trim/re-measure loop; and ±31 matches a 6-bit pot. What is
*not* established is the channel→sensor assignment, i.e. which of the four bytes
is which DX detector.

To settle it, instrument the four values on hardware while varying the trim —
the loop structure means each byte should respond monotonically to its own
channel's pot and to nothing else.

## 3. `FilmPresent` is not a register read

This is the substantive correction to my own suggestion in `docs/41` that `0x93`
probably carried it.

The lamp-log row is formatted at `0x1000bc49` with

```
"%d\t%d\t%f\t%f\t%f\t%d\t%d\t%u\t%u\t%u\t%u\t%f\t%f\t%f\t%f\t%u\r\n"   (0x1005c37c)
```

matching the header `Time | FilmPresent | TempMB | TempLB | TempSetpoint | …`
carved in `docs/41`. Arguments are pushed right-to-left, so field 2 is the last
value pushed before `Time`. That push is at `0x1000bc3c`, and its source two
instructions earlier is:

```asm
0x1000bc13   mov eax, dword [esi + 0x28]     ; sibling object
0x1000bc1d   mov ecx, dword [eax + 0x54]     ; <- FilmPresent
0x1000bc3c   push ecx                        ; field 2
0x1000bc43   call 0x10034030                 ; returns Time
0x1000bc48   push eax                        ; field 1
```

So **`FilmPresent = [[this+0x28] + 0x54]`** — a cached host-side state field on
the object at `[this+0x28]`, read at log time, not sampled from hardware there.
(That same `[this+0x28]` object is used in `FN_bLampTemperatureStable` at
`0x1002cf60`.)

The consequence for the port: **there is no "read film present" register to
call.** Whatever samples the film path writes into that field, and the logger
merely reports the cached value. Finding the writer is the remaining step —
`FN_bFilmFound` and the error code `EC_FilmInGuides` are the leads, and
`[X+0x54]` has 45 reader sites to narrow down.

## 4. Correction: FN ids cannot be recovered from `TLB.tbl.txt`

I briefly derived an `id = line − 4` mapping from `research/native/TLB.tbl.txt`
and used it to name several functions. **It is invalid — discard any names
derived from it.** The check that caught it: doc 15 establishes
`FN_bLampTemperatureStable` = 346, and line 350 is `FN_bSetReadFilePosition`.

`TLB.tbl.txt` is sorted **alphabetically**, not by enum id — visible directly in
the file (`FN_bReadEEPromData`, `FN_bReadExternalMofFile`, `FN_bReadLut`,
`FN_bReadMatrix_3x10`, …). The gains/offsets pair appeared to validate the
offset only because those two are adjacent both alphabetically and by id.

The underlying name array in the DLL (UTF-16, 359 `FN_` entries at file offset
`0x0613b0`–`0x065104`) is the same alphabetical list stored in reverse, so it
does not yield ids either. The logger resolves names through **`FormatMessageW`**
(`0x1001addf`), so the id→name association lives in the message-table resource,
not in any flat array. Symbolicating by logger id needs that resource parsed
properly.

## 5. Also worth noting: the disassembly matches the shipped DLL

`docs/39` flagged that `research/native/TLB.text.asm` was unattributed and that
two `TLB.dll` copies of identical size had different MD5s. The `.text` of both
copies **matches the disassembly** byte-for-byte at every address checked
(`0x1000b890`, `0x100298b0`, `0x1000a950`). My earlier doubt came from a bad
RVA→file-offset calculation: in this PE every section has
`PointerToRawData == VirtualAddress`, so the file offset of an address is simply
`vaddr − 0x10000000`. The two copies differ somewhere other than `.text`.
