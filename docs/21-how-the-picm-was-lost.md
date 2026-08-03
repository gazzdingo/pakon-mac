# 21 — How the PICM ended up in its bootloader, and the likely way back

## It was not the EEPROM sweep

The sweep that damaged the boot EEPROM wrote only to boards `0xa2`-`0xa5`
(I2C devices `0x51`/`0x52`), in the form `02 05 a2 02 <reg> <d0> <d1>`. Those
are the serial EEPROMs. That sweep never addressed the PICM.

## It was the Type 4 command sweep on board 0x44

`tools/find_light_path.py:130-133` walks the **entire Type 4 command space of
the motor board**, hunting for a command that would admit light:

```python
for cmd in range(0x100):
    r = send(d, bytes([0x04, 0x03, board, 0x00, cmd]))   # board = 0x44
```

256 blind commands to the live PICM. The recorded result at the time was that
commands `0x01`-`0x0d` were **accepted**, and what they did was never
established -- the tool only watched EP 0x86 for illumination, so any command
that did something other than turn on a lamp registered as "accepted" and
nothing more.

A mode switch into the bootloader would look exactly like that: accepted,
no light, no obvious change until the next power cycle.

## Why this is good news

Entering the bootloader is a **mode**, not destruction. `TLB.dll` treats it as
a switch with two payloads on register `0x0a`:

| payload | meaning | where |
|---------|---------|-------|
| `{0x00, 0x55}` | enter bootloader | `FN_bPicToBootLoaderState`, `fcn.1001b9b0` |
| `{0x00, 0xAA}` | **exit bootloader, run the application** | `FN_bUpdate`, `0x1001cc6d`-`0x1001cc72` |

The exit form, byte for byte from `0x1001cc60`:

```asm
push 0                      ; flag
push 2                      ; dataLen
push edx                    ; data pointer
push 0xa                    ; register 0x0A
push edi                    ; board
mov byte [esp + 0x4c], 0    ; data[0] = 0x00
mov byte [esp + 0x4d], 0xaa ; data[1] = 0xAA
call fcn.10009ae0
```

which on the wire is:

```
02 05 <board> 02 0a 00 aa
```

`FN_bUpdate` sends this **after** flashing, to bring the PIC back into its
freshly written application. If this unit's PICM still holds its firmware and
was merely switched into bootloader mode, the same packet should bring it back
**without flashing anything**.

## Why this is worth trying before the flasher

- it is a **mode switch, not a flash operation** -- no erase, no program write
- if the firmware is intact, the PICM returns to `0x44` and the scanner works
- if the firmware really is gone, the PIC has nothing to run and stays in the
  bootloader, which is where it already is; nothing is lost
- it is one packet, and reversible by the `{00, 0x55}` counterpart

Compare with flashing: 166 erases plus 664 writes plus a reset, with a
read-back offset that is still unproven on hardware. The mode switch is
strictly the safer first move, and if it works the flasher is never needed.

## Proposed test

With the scanner powered on and firmware loaded:

1. confirm the current state -- `0x44` absent, `0x46` present, controls silent
2. send `02 05 46 02 0a 00 aa`
3. re-probe: does `0x44` now answer?
4. if not, power-cycle and re-probe -- the switch may only take on reset

Nothing else is sent. If `0x44` comes back, the board never lost its firmware
and the whole flashing exercise is unnecessary.

## Lesson

Do not sweep an unknown command space on a live controller. The lamp hunt that
produced this sweep was already the wrong approach -- the answer was in
`TLB.dll` the whole time -- and it has now cost this project twice: the boot
EEPROM via the address sweep, and most likely the PICM's operating mode via
the command sweep.
