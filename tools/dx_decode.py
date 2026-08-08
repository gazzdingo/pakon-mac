#!/usr/bin/env python3
"""Decode the Pakon DX board's event stream (PPB_READ_DX_CODE, opcode 0x90).

WHAT THIS IS
    A decoder for the *packet payload* the scanner's DX board sends back. The
    DX board (light/PICL board, packet address 0x40, firmware dx0211.HEX) has
    four photodiode channels -- TopClock, TopData, BottomClock, BottomData --
    and does all the bar sampling and clock recovery itself. It hands the host
    already-assembled code words. This module turns those into
    (product, specifier, frame number) exactly as TLB.dll does.

WHAT THIS IS NOT
    NOT an image-based barcode reader. The bar geometry -- bar pitch, bar
    widths, position across the film, clock-track structure -- lives in the DX
    board's PIC firmware and appears in no host binary. Do not try to build an
    image decoder from this file. See docs/53-edge-data.md sections 0 and 5.

PROVENANCE
    Field extraction is transcribed from TLB.dll (F-135, base 0x10000000,
    MD5 e7f21021e0140c1935a3ae4de7bd3498) with the address in a comment.
    Record framing is transcribed from the DX board's own PIC16F877 image
    (docs/57-dx-firmware.md), which is the side that *writes* the wire.
    Cross-check that holds: product is 7 bits (0-127) and specifier 4 bits
    (0-15), matching the PIMA/I3A Part 1 / Part 2 widths in docs/09.

RECORDS ARE VARIABLE LENGTH -- 3 TO 6 BYTES -- NOT A FIXED 5-BYTE STRIDE
    This is the correction that matters most (docs/57 s8.1, s10.1). The board's
    only event producer, FUNC_05eb, emits a payload whose length is fixed by
    the event type: 4 bytes for type 1, 5 for type 2, 3 for type 3, 2 for
    type 4 and 2 for types 5-8. The queue stores a length prefix but register
    0x90 does NOT put it on the wire (0x09C0-0x09CA reads the length with the
    pre-increment index and then copies from the type byte).

    docs/53 s1.2 read a fixed 5-byte stride out of TLB.dll's parser. A fixed
    stride desynchronises after the first record that is not type 1, which is
    the most likely reason no code word has ever validated here. The firmware
    is the authority on what is on the wire, so this module keys the stride off
    the type byte, and refuses to walk past a type byte it does not recognise
    rather than guess a length.

THE BYTE WINDOW IS RESOLVED -- IT IS THE `obj+0x08 == 0` WINDOW
    The vendor shifts the code word from either payload bytes d0,d1,d2 or
    d1,d2,d3 (CiDxAndApsHole+0x08, 0x10013cd3-0x10013cf6), and docs/53 s1.4
    could not say which 35 mm uses. The firmware settles it twice over
    (docs/57 s10.2): a type-3 record carries *exactly three* payload bytes, so
    there is no fourth byte for the d1,d2,d3 window to reach, and the
    shift-register assembly order independently fixes 0x114 as b0, 0x115 as b1,
    0x116 as b2. This module therefore decodes one window and no longer returns
    AMBIGUOUS on that axis.

    A consequence worth naming: `obj+0x08 == 0` also excludes the tail-first
    frame-doubling path at 0x10013eb3, which only runs when it is non-zero.

WHAT IT STILL REFUSES TO DO
    Resolving the window did not turn this into a decoder that guesses. It
    still declines, rather than inventing a reading, when:
      * a type byte is outside 1..8 -- the stride is unknown, so the rest of
        the packet is left unparsed and said to be unparsed;
      * a record runs past the end of the buffer;
      * parity or the must-be-zero bit fails -- the word is rejected, and
        contributes a line position but no product;
      * the packet carried no records, in which case the status nibble is
        *absent*, not zero (see DxPacket.status_valid). The board ORs its flags
        into record 0's type byte only, so a packet with N = 0 says nothing
        about the film sensors and must not be read as "sensors clear".
    Types 1 and 2 (APS) are framed and counted but not decoded: their
    acceptance test is a modulo-2 division that is not transcribed here.

STATUS
    NEVER VALIDATED AGAINST HARDWARE. Treat any product number as unconfirmed
    until a roll with a known DX code has been scanned and matched.

    Self-test:  python3 tools/dx_decode.py --selftest
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import IntEnum

# --------------------------------------------------------------------------
# Packet opcodes, on packet address 0x40 (AD_LIGHT).
# Names from the packet logger fcn.1000ab20, 0x1000ad5b-0x1000ad95.
# --------------------------------------------------------------------------
PPB_READ_DX_CODE = 0x90   # request; 30-byte response
PPB_START_DX_SCAN = 0x91  # 3-byte payload: speed_lo, speed_hi, format
PPB_STOP_DX_SCAN = 0x92   # no payload

DX_RESPONSE_LEN = 0x1E    # 30 bytes -- fcn.10009790 @ 0x100097c9
DX_HEADER_LEN = 3         # [line hi][line lo][N], docs/57 s8.2 @ 0x099D

#: Payload bytes carried by each event type, i.e. the record's wire length
#: minus its one type byte. From the DX board's own event producer FUNC_05eb,
#: docs/57 s8.1 (bit count -> type -> payload length, 0x05FF-0x061E):
#:
#:     bits 31 -> type 1 -> 4 payload bytes -> 5 on the wire   (APS id word)
#:     bits 37 -> type 2 -> 5 payload bytes -> 6 on the wire   (APS cartridge)
#:     bits 21 -> type 3 -> 3 payload bytes -> 4 on the wire   (DX + frame)
#:     bits 12 -> type 4 -> 2 payload bytes -> 3 on the wire   (DX, no frame)
#:     types 5,6,7,8      -> 2 payload bytes -> 3 on the wire   ({TMR1H,TMR1L})
#:
#: NOT a constant 5. docs/53 s1.2's `inc edi` / `add edi, 4` transcription is
#: the thing this table replaces; see the module docstring.
DX_RECORD_PAYLOAD = {1: 4, 2: 5, 3: 3, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2}

#: Longest and shortest records, for sizing arguments about capacity.
DX_RECORD_MIN = 1 + min(DX_RECORD_PAYLOAD.values())   # 3
DX_RECORD_MAX = 1 + max(DX_RECORD_PAYLOAD.values())   # 6

#: Ceiling on events per packet: all-shortest records in the 27-byte budget
#: (0x09B1 sets budget = requested_n - 3). The old figure of 5 came from the
#: fixed 5-byte stride and is wrong in both directions -- a packet of type-2
#: records holds 4, a packet of perforations holds 9.
DX_MAX_EVENTS = (DX_RESPONSE_LEN - DX_HEADER_LEN) // DX_RECORD_MIN  # 9

# Only issue the 0x90 read when the light board's interrupt-status byte has
# these bits set -- FN_bDrvGetPpbInterruptStatus @ 0x1000bf80.
DX_POLL_GATE_MASK = 0xA4

# --------------------------------------------------------------------------
# Status flags: high nibble of the FIRST record's type byte only
# (fcn.10009790 @ 0x10009890 `cmp edi, 3`; the board ORs them in at
# 0x09f0 `iorwf 0x03e, F`, docs/57 s8.2).
#
# Translation is fcn.10014320 @ 0x10014320-0x10014343; constant names and
# values from research/net/TLXLib.il lines 2996-2999.
#
# WHAT THE FIRMWARE CALLS THESE FOUR BITS IS NOT WHAT THE HOST CALLS THEM.
# docs/57 s8.2 reads the board side as: bit 4 = live RC6 level, bit 5 = live
# RC7 level, bits 6/7 = the two DX-activity latches set at 0x16BA/0x16BB.
# docs/53 s4.1 reads the host side as: 0x10 -> FILM_SENSE_EXIT, 0x20 ->
# FILM_SENSE_ENTRY, 0x40 -> FILM_EMULSION_DOWN, 0x80 -> FILM_TAIL_FIRST.
# The bit *positions* agree; the meanings of bits 6 and 7 do not, and docs/57
# s12 lists "what RC6 and RC7 sense" as still unknown. So the names below are
# the host's, which is the vocabulary everything downstream speaks -- and the
# mis-load bits are surfaced as warnings, never as an abort.
# --------------------------------------------------------------------------
DXSTAT_FILM_SENSE_EXIT = 0x10
DXSTAT_FILM_SENSE_ENTRY = 0x20
DXSTAT_EMULSION_DOWN = 0x40
DXSTAT_TAIL_FIRST = 0x80

#: Film-position bits, the pair that says whether film is in the transport.
DXSTAT_FILM_SENSE = DXSTAT_FILM_SENSE_ENTRY | DXSTAT_FILM_SENSE_EXIT
#: Mis-load bits. Warn on these; the vendor has no abort path for them
#: (docs/53 s4.2: "no code path in TLB.dll aborts a scan on emulsion-down or
#: tail-first").
DXSTAT_MISLOAD = DXSTAT_EMULSION_DOWN | DXSTAT_TAIL_FIRST

# HARDWARE_CB_FILM_* -- consecutive in the HARDWARE_CB_000 enum. Note that
# ENTRY is bit 30 and EXIT is bit 31, i.e. the opposite order to the DX status
# bits they come from (0x20 -> ENTRY, 0x10 -> EXIT). 0xC0000000, the value in
# every scan sidecar taken so far, is therefore "film sensed at both ends".
HARDWARE_CB_FILM_EMULSION_DOWN = 0x10000000     # from DX status 0x40
HARDWARE_CB_FILM_TAIL_FIRST = 0x20000000        # from DX status 0x80
HARDWARE_CB_FILM_SENSE_ENTRY = 0x40000000       # from DX status 0x20
HARDWARE_CB_FILM_SENSE_EXIT = 0x80000000        # from DX status 0x10

_STATUS_TO_HWCB = (
    (DXSTAT_EMULSION_DOWN, HARDWARE_CB_FILM_EMULSION_DOWN),
    (DXSTAT_TAIL_FIRST, HARDWARE_CB_FILM_TAIL_FIRST),
    (DXSTAT_FILM_SENSE_ENTRY, HARDWARE_CB_FILM_SENSE_ENTRY),
    (DXSTAT_FILM_SENSE_EXIT, HARDWARE_CB_FILM_SENSE_EXIT),
)


class EventType(IntEnum):
    """Low nibble of a record's type byte. Dispatch: fcn.100148a0 @ 0x100148b0."""

    APS_ID = 1          # fcn.10013980
    APS_CARTRIDGE = 2   # fcn.10013af0
    DX_CODE_FULL = 3    # fcn.10013cd0 -- product + specifier + frame number
    DX_CODE_SHORT = 4   # fcn.10013f50 -- product + specifier only
    FILM_EDGE = 5       # fcn.10013900 + fcn.10014130
    FAT_BIT = 6         # fcn.10013900 + fcn.10014220
    PERF_TRAILING = 7   # fcn.10014260
    PERF_LEADING = 8    # fcn.10014260


# Types whose payload IS the event's own 16-bit line number, big-endian.
#
# CORRECTED, and this is a change of behaviour. docs/53 s1.2 said types 1, 2
# and >4 carry a line number in payload bytes d1,d2. The firmware disagrees on
# both counts (docs/57 s10.3): the `call 0x0531` that latches Timer1 sits at
# 0x0624, on the `0x192 != 1` path only, and the code-word path jumps straight
# past it (`061f goto 0x062d`). So ALL FOUR code-word types -- 1, 2, 3 and 4 --
# spend their whole payload on code bits, and only 5, 6, 7 and 8 carry
# {TMR1H, TMR1L}. Those types have a two-byte payload, so the line number is
# payload[0..1]; there is no d1,d2 to read.
_TYPES_WITH_OWN_LINE = frozenset({5, 6, 7, 8})

#: Code-word types, the two this module actually decodes.
_CODE_TYPES = frozenset({EventType.DX_CODE_FULL, EventType.DX_CODE_SHORT})

INVALID_FRAME = -0x80000000  # sentinel stored on parity failure, 0x10013e99
DX_NO_CODE_PRODUCT = -6      # < -6 renders as "DX_ERROR", fcn.10026430 @ 0x1002644c


def _popcount(x: int) -> int:
    return bin(x & 0xFF).count("1")


# --------------------------------------------------------------------------
# The DX code word.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DxCode:
    product: int      # DX number Part 1, 0-127
    specifier: int    # DX number Part 2, 0-15
    frame: int | None  # half-frame index, -6..121; None for the short word
    valid: bool       # parity + must-be-zero both passed
    bit0: int         # meaning UNKNOWN
    bit1: int         # meaning UNKNOWN (tested as `b0 & 2` on the 24 mm path)
    #: Always 0. Kept as a field so logs and sidecars written before the window
    #: was resolved stay comparable with ones written after. See the module
    #: docstring: a type-3 record has three payload bytes and window 1 would
    #: need a fourth.
    window: int = 0

    @property
    def dx_number(self) -> int:
        """Composite DX number as printed on cartridges: Part1*16 + Part2."""
        return self.product * 16 + self.specifier

    @property
    def frame_number(self) -> float | None:
        """Printed frame number. 35 mm codes count HALF-frames, so divide by 2.

        Whole numbers are the numbered frames; x.5 is the "A" half-frame.
        Basis: fcn.10014a10 @ 0x10014a31 halves the expected pitch for 35 mm,
        and fcn.100147a0 @ 0x100147fa steps 35 mm codes by 1.
        NOT valid for 24 mm, where codes step by 2 and are whole frames.
        """
        if self.frame is None or self.frame == INVALID_FRAME:
            return None
        return self.frame / 2.0


def decode_dx_full(b0: int, b1: int, b2: int, window: int = 0) -> DxCode:
    """Event type 3 -- the 21-bit DX code word with a frame number.

    fcn.10013cd0, 0x10013d0b-0x10013de3. Byte roles:
        b0  bit0, bit1 flags; bits2-7 = frame number bits 0-5
        b1  bit0 = frame bit 6; bits1-4 = specifier; bit5 must be 0;
            bits6-7 = product bits 0-1
        b2  bits0-4 = product bits 2-6 (bits 5-7 masked off, 0x10013d97)
    Even parity over all 21 bits.
    """
    b0 &= 0xFF
    b1 &= 0xFF
    b2 &= 0x1F  # `and al, 0x1f` @ 0x10013d97

    product = ((b2 & 0x1F) << 2) | (b1 >> 6)   # 0x10013d0b-0x10013d21
    specifier = (b1 >> 1) & 0x0F               # 0x10013d25-0x10013d2c
    frame = (b0 >> 2) | ((b1 & 1) << 6)        # 0x10013d30-0x10013d43
    if frame > 121:                            # 0x10013d45-0x10013d4a
        frame -= 128

    must_be_zero = (b1 >> 5) & 1               # 0x10013d50-0x10013d5d
    parity = _popcount(b0) + _popcount(b1) + _popcount(b2)  # 0x10013daa-0x10013dcf
    valid = must_be_zero == 0 and (parity & 1) == 0         # 0x10013dd1-0x10013de3

    return DxCode(
        product=product,
        specifier=specifier,
        frame=frame if valid else INVALID_FRAME,
        valid=valid,
        bit0=b0 & 1,
        bit1=(b0 >> 1) & 1,
        window=window,
    )


def decode_dx_short(b0: int, b1: int, window: int = 0) -> DxCode:
    """Event type 4 -- the same word minus the frame-number byte.

    fcn.10013f50, 0x10013f6a-0x10013fc1.
    """
    b0 &= 0xFF
    b1 &= 0xFF

    product = ((b1 & 0x1F) << 2) | (b0 >> 6)   # 0x10013f7b-0x10013f8c
    specifier = (b0 >> 1) & 0x0F               # 0x10013f7e-0x10013f83

    must_be_zero = (b1 >> 5) & 1               # `test dl, 0x20` @ 0x10013fb2
    parity = _popcount(b0) + _popcount(b1)     # 0x10013fa0-0x10013fad
    valid = must_be_zero == 0 and (parity & 1) == 0  # 0x10013fbb

    return DxCode(
        product=product,
        specifier=specifier,
        frame=None,
        valid=valid,
        bit0=b0 & 1,
        bit1=(b0 >> 1) & 1,
        window=window,
    )


def decode_code_record(payload: bytes, full: bool) -> DxCode | None:
    """Decode one type-3 or type-4 record's payload. One window, not two.

    The payload is the record's own bytes -- 3 for type 3, 2 for type 4 -- so
    b0,b1,b2 are payload[0],payload[1],payload[2] and there is no second window
    to try. docs/57 s10.2 and the module docstring have why.

    Returns None if the payload is short, which the record walker treats as a
    record it could not read rather than one it read as zeroes.
    """
    need = 3 if full else 2
    if len(payload) < need:
        return None
    if full:
        return decode_dx_full(payload[0], payload[1], payload[2])
    return decode_dx_short(payload[0], payload[1])


def encode_dx_full(product: int, specifier: int, frame: int, bit1: int = 0) -> tuple[int, int, int]:
    """Inverse of decode_dx_full, using bit0 as the parity bit.

    Used only to exercise the decoder in --selftest. Which of bits 0/1 is the
    real parity bit on actual film is UNKNOWN; the decoder does not care,
    because it parities over all 21 bits either way.
    """
    if not 0 <= product <= 127:
        raise ValueError("product must be 0..127")
    if not 0 <= specifier <= 15:
        raise ValueError("specifier must be 0..15")
    if not -6 <= frame <= 121:
        raise ValueError("frame must be -6..121")

    f = frame & 0x7F
    b0 = ((f & 0x3F) << 2) | ((bit1 & 1) << 1)
    b1 = ((product & 3) << 6) | ((specifier & 0x0F) << 1) | ((f >> 6) & 1)
    b2 = (product >> 2) & 0x1F
    if (_popcount(b0) + _popcount(b1) + _popcount(b2)) & 1:
        b0 |= 1
    return b0, b1, b2


# --------------------------------------------------------------------------
# The 30-byte response.
# --------------------------------------------------------------------------
def encode_record(etype: int, payload: bytes, flags: int = 0) -> bytes:
    """One event record as the board puts it on the wire: [type][payload...].

    Refuses a payload that is not the length the firmware emits for that type,
    so a test or a simulator cannot accidentally assert a stride the machine
    would never produce.
    """
    want = DX_RECORD_PAYLOAD.get(int(etype))
    if want is None:
        raise ValueError(f"no wire length is known for event type {etype}")
    if len(payload) != want:
        raise ValueError(f"type {etype} carries {want} payload bytes, "
                         f"got {len(payload)}")
    return bytes([(int(etype) & 0x0F) | (int(flags) & 0xF0)]) + bytes(payload)


def encode_packet(line: int, records: list[bytes],
                  length: int = DX_RESPONSE_LEN) -> bytes:
    """A whole 30-byte 0x90 response around some already-encoded records."""
    body = b"".join(records)
    buf = bytes([(line >> 8) & 0xFF, line & 0xFF, len(records)]) + body
    if len(buf) > length:
        raise ValueError(f"{len(buf)} bytes will not fit in {length}")
    return buf + bytes(length - len(buf))


@dataclass
class DxEvent:
    type: int
    flags: int          # high nibble; only meaningful on the first record
    payload: bytes      # 2..5 bytes, length fixed by `type` (DX_RECORD_PAYLOAD)
    line: int           # absolute scan line, rollover-extended
    code: DxCode | None = None
    #: Retained for the refusal machinery. The byte-window axis no longer
    #: produces candidates (see the module docstring), so this is empty in
    #: practice; it is not removed because `ambiguous` is the shape callers use
    #: to mean "the decoder had readings and declined to choose", and a future
    #: unresolved axis should reuse it rather than invent a second one.
    candidates: list[DxCode] = field(default_factory=list)

    @property
    def ambiguous(self) -> bool:
        return bool(self.candidates) and self.code is None


@dataclass
class DxPacket:
    line_counter: int
    events: list[DxEvent] = field(default_factory=list)
    status: int = 0        # raw high nibble of the first record's type byte
    hardware_cb: int = 0   # translated HARDWARE_CB_FILM_* bits
    #: True only when a first record existed to carry the status nibble. The
    #: board ORs its flags into record 0's type byte and nowhere else
    #: (0x09f0), so a packet with N = 0 carries NO status. Reading `status == 0`
    #: on such a packet as "film sensors clear" would invent an end of roll out
    #: of an idle queue; every consumer of the film-sense bits must gate on
    #: this.
    status_valid: bool = False
    #: Records the header declared, and how many were actually framed.
    records_declared: int = 0
    #: Why the walk stopped early, if it did. Empty when the packet parsed out.
    parse_error: str = ""

    @property
    def emulsion_down(self) -> bool:
        return bool(self.status & DXSTAT_EMULSION_DOWN)

    @property
    def tail_first(self) -> bool:
        return bool(self.status & DXSTAT_TAIL_FIRST)

    @property
    def film_at_entry(self) -> bool:
        return bool(self.status & DXSTAT_FILM_SENSE_ENTRY)

    @property
    def film_at_exit(self) -> bool:
        return bool(self.status & DXSTAT_FILM_SENSE_EXIT)

    @property
    def film_present(self) -> bool | None:
        """Film at either sensor, or None when this packet cannot say.

        None is not False. See :attr:`status_valid`.
        """
        if not self.status_valid:
            return None
        return bool(self.status & DXSTAT_FILM_SENSE)


class DxStream:
    """Stateful parser: feed it every 30-byte 0x90 response, in order.

    State carried across polls (all from fcn.10009790):
      * rollover count for the 16-bit line counter  (this+0x5c, 0x1000985f)
      * previous packet line counter                (this+0x60, 0x100099a2)

    `half_lines` mirrors obj+0x28: set True when the DPI base is 4, which makes
    the vendor halve every reported line number (fcn.10013800 @ 0x1001386b,
    applied at fcn.10014220 @ 0x10014227 and friends).
    """

    def __init__(self, half_lines: bool = False) -> None:
        self.rollovers = 0
        self.prev_line = 0
        self.half_lines = half_lines

    def feed(self, buf: bytes) -> DxPacket:
        if len(buf) < DX_HEADER_LEN:
            raise ValueError(f"short DX response: {len(buf)} bytes")

        counter16 = (buf[0] << 8) | buf[1]              # 0x10009835-0x10009847
        if counter16 < (self.prev_line & 0xFFFF):       # 0x10009850-0x10009862
            self.rollovers += 1
        packet_line = (self.rollovers << 16) | counter16

        n = buf[2]                                      # 0x1000986d
        pkt = DxPacket(line_counter=packet_line, records_declared=n)

        off = DX_HEADER_LEN
        for i in range(n):
            if off >= len(buf):
                pkt.parse_error = (
                    f"packet declared {n} records; the buffer ran out after {i}")
                break
            type_byte = buf[off]
            etype = type_byte & 0x0F                    # 0x1000988d

            # THE STRIDE COMES FROM THE TYPE. An unrecognised type means an
            # unknown length, and guessing one would silently reframe every
            # record after it -- exactly the failure mode a fixed stride has.
            # So stop, and say so.
            plen = DX_RECORD_PAYLOAD.get(etype)
            if plen is None:
                pkt.parse_error = (
                    f"record {i} has type {etype}, which the board never emits;"
                    f" its length is unknown so the rest of the packet was not"
                    f" parsed")
                break
            if off + 1 + plen > len(buf):
                pkt.parse_error = (
                    f"record {i} (type {etype}) needs {plen} payload bytes but "
                    f"only {len(buf) - off - 1} remain")
                break
            payload = bytes(buf[off + 1 : off + 1 + plen])

            if i == 0:                                  # 0x10009890 `cmp edi, 3`
                pkt.status = type_byte & 0xF0           # 0x1000989d-0x100098a5
                pkt.status_valid = True
                for bit, hwcb in _STATUS_TO_HWCB:
                    if pkt.status & bit:
                        pkt.hardware_cb |= hwcb

            if etype in _TYPES_WITH_OWN_LINE:
                # The whole payload is {TMR1H, TMR1L}, big-endian, extended by
                # the same rollover count. 0x1000993d-0x10009950.
                line = (self.rollovers << 16) | (payload[0] << 8) | payload[1]
                if line + 10000 < self.prev_line:       # 0x10009952-0x1000995d
                    line += 0x10000
            else:
                line = packet_line

            if self.half_lines:
                line >>= 1

            ev = DxEvent(type=etype, flags=type_byte & 0xF0,
                         payload=payload, line=line)
            if etype in _CODE_TYPES:
                ev.code = decode_code_record(
                    payload, full=(etype == EventType.DX_CODE_FULL))

            pkt.events.append(ev)
            off += 1 + plen

        self.prev_line = packet_line
        return pkt


# --------------------------------------------------------------------------
# Roll-level result: pick the winning (product, specifier) the way TLB does.
# --------------------------------------------------------------------------
class DxVote:
    """4-slot plurality vote, exactly as fcn.10013cd0 @ 0x10013deb.

    Only four distinct (product, specifier) pairs are ever tracked; the fifth
    and later distinct pairs are dropped. That is the vendor's behaviour, not
    an approximation.
    """

    SLOTS = 4

    def __init__(self) -> None:
        self.pairs: list[tuple[int, int]] = []
        self.counts: list[int] = []
        # Code words that passed validation. NOT the vendor's "Good Dx Count":
        # that number (obj+0x48) is computed separately at fcn.10014a10
        # 0x10014e11-0x10014e24 and counts array entries whose frame number was
        # read rather than extrapolated.
        self.accepted = 0
        self.ambiguous = 0

    def add(self, event_or_code) -> None:
        if isinstance(event_or_code, DxEvent):
            if event_or_code.ambiguous:
                self.ambiguous += 1
                return
            code = event_or_code.code
        else:
            code = event_or_code
        if code is None or not code.valid:
            return
        self.accepted += 1
        key = (code.product, code.specifier)
        for i, p in enumerate(self.pairs):
            if p == key:
                self.counts[i] += 1
                return
        if len(self.pairs) < self.SLOTS:
            self.pairs.append(key)
            self.counts.append(1)

    def winner(self) -> tuple[int, int] | None:
        if not self.pairs:
            return None
        best = max(range(len(self.pairs)), key=lambda i: self.counts[i])
        return self.pairs[best]


# --------------------------------------------------------------------------
def _selftest() -> int:
    fails = 0

    def check(label: str, got, want) -> None:
        nonlocal fails
        if got != want:
            print(f"FAIL {label}: got {got!r}, want {want!r}")
            fails += 1

    # Round-trip every legal (product, specifier, frame) triple.
    n = 0
    for product in range(128):
        for specifier in range(16):
            for frame in (-6, -1, 0, 1, 2, 35, 76, 121):
                b0, b1, b2 = encode_dx_full(product, specifier, frame)
                c = decode_dx_full(b0, b1, b2)
                n += 1
                if not (c.valid and c.product == product
                        and c.specifier == specifier and c.frame == frame):
                    print(f"FAIL roundtrip p={product} s={specifier} f={frame} -> {c}")
                    fails += 1
    print(f"round-trip: {n} triples")

    # A single flipped bit must be caught by the parity check.
    caught = 0
    b0, b1, b2 = encode_dx_full(109, 9, 12)
    for bit in range(8):
        if not decode_dx_full(b0 ^ (1 << bit), b1, b2).valid:
            caught += 1
        if not decode_dx_full(b0, b1 ^ (1 << bit), b2).valid:
            caught += 1
    for bit in range(5):
        if not decode_dx_full(b0, b1, b2 ^ (1 << bit)).valid:
            caught += 1
    check("single-bit errors caught", caught, 21)

    # Known stocks from docs/09 must land on the right composite DX number.
    for name, p, s, dxnum in (
        ("Ilford HP5 Plus", 109, 9, 1753),
        ("Ilford FP4 Plus", 109, 12, 1756),
        ("Ilford Delta 3200", 108, 10, 1738),
        ("Ilford XP2 Super", 110, 4, 1764),
    ):
        c = decode_dx_full(*encode_dx_full(p, s, 24))
        check(f"{name} product", c.product, p)
        check(f"{name} specifier", c.specifier, s)
        check(f"{name} dx_number", c.dx_number, dxnum)
        check(f"{name} frame_number", c.frame_number, 12.0)

    # Short word: same fields, one byte earlier.
    for product in range(128):
        for specifier in range(16):
            b0 = ((product & 3) << 6) | (specifier << 1)
            b1 = (product >> 2) & 0x1F
            if (_popcount(b0) + _popcount(b1)) & 1:
                b0 |= 1
            c = decode_dx_short(b0, b1)
            if not (c.valid and c.product == product
                    and c.specifier == specifier and c.frame is None):
                print(f"FAIL short p={product} s={specifier} -> {c}")
                fails += 1
    print("short-word round-trip: 2048 pairs")

    # ---- record framing: the wire lengths the board actually emits ----
    check("payload lengths", DX_RECORD_PAYLOAD,
          {1: 4, 2: 5, 3: 3, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2})
    check("shortest record", DX_RECORD_MIN, 3)
    check("longest record", DX_RECORD_MAX, 6)
    check("type 3 is four bytes on the wire",
          len(encode_record(EventType.DX_CODE_FULL, b"\x00\x00\x00")), 4)
    try:
        encode_record(EventType.DX_CODE_FULL, b"\x00\x00\x00\x00")
        check("encode_record rejects a wrong length", "accepted", "raised")
    except ValueError:
        pass

    # Packet framing, status nibble. A type-3 (4 bytes) followed by a type-8
    # (3 bytes) is exactly the case a fixed 5-byte stride gets wrong: at stride
    # 5 the second record would start one byte late and read type 0.
    st = DxStream()
    b0, b1, b2 = encode_dx_full(109, 9, 12)
    rec3 = encode_record(EventType.DX_CODE_FULL, bytes([b0, b1, b2]), flags=0x30)
    rec8 = encode_record(EventType.PERF_LEADING, bytes([0x12, 0x34]))
    buf = encode_packet(0x64, [rec3, rec8])
    pkt = st.feed(buf)
    check("packet line", pkt.line_counter, 0x64)
    check("event count", len(pkt.events), 2)
    check("no parse error", pkt.parse_error, "")
    check("status nibble", pkt.status, 0x30)
    check("status is present", pkt.status_valid, True)
    check("film at entry", pkt.film_at_entry, True)
    check("film at exit", pkt.film_at_exit, True)
    check("film present", pkt.film_present, True)
    check("emulsion down", pkt.emulsion_down, False)
    check("tail first", pkt.tail_first, False)
    check("perf type", pkt.events[1].type, int(EventType.PERF_LEADING))
    check("perf line", pkt.events[1].line, 0x1234)
    check("perf payload is two bytes", len(pkt.events[1].payload), 2)

    # The same two records at the old fixed stride desynchronise, and not
    # harmlessly: at stride 5 the second record starts one byte late, inside the
    # perforation's line number, and 0x12 reads as a type-2 APS cartridge word.
    # Assert it, so the regression stays visible rather than remembered.
    check("fixed stride misreads the second record's type",
          buf[DX_HEADER_LEN + 5] & 0x0F, 2)
    check("the real second record is a perforation",
          buf[DX_HEADER_LEN + 4] & 0x0F, int(EventType.PERF_LEADING))

    # One record of every type, back to back, in one packet. 4+5+... does not
    # fit in 27 bytes, so this is split.
    st_all = DxStream()
    recs = [encode_record(1, bytes(4)), encode_record(2, bytes(5)),
            encode_record(3, bytes([b0, b1, b2])), encode_record(4, bytes(2))]
    p_all = st_all.feed(encode_packet(10, recs))
    check("all four code types framed", [e.type for e in p_all.events],
          [1, 2, 3, 4])
    check("type 1 payload", len(p_all.events[0].payload), 4)
    check("type 2 payload", len(p_all.events[1].payload), 5)
    check("type 3 decoded through variable stride",
          p_all.events[2].code.product if p_all.events[2].code else None, 109)

    # Types 1 and 2 carry NO line number -- they take the packet's. docs/57
    # s10.3 corrects docs/53 on this, and a type-1 record whose payload happens
    # to look like a line number must not be read as one.
    st_aps = DxStream()
    p_aps = st_aps.feed(encode_packet(777, [encode_record(1, bytes([0, 0x12, 0x34, 0]))]))
    check("type 1 uses the packet line", p_aps.events[0].line, 777)
    st_perf = DxStream()
    p_perf = st_perf.feed(encode_packet(777, [encode_record(7, bytes([0x12, 0x34]))]))
    check("type 7 uses its own line", p_perf.events[0].line, 0x1234)

    # Nine perforations fill a packet; a fixed stride of 5 could only see five.
    st9 = DxStream()
    nine = [encode_record(8, bytes([0, i])) for i in range(9)]
    p9 = st9.feed(encode_packet(1, nine))
    check("nine short records fit", len(p9.events), 9)
    check("last of nine", p9.events[8].line, 8)
    check("that is the ceiling", DX_MAX_EVENTS, 9)

    # An unknown type must stop the walk, not guess a stride.
    st_bad = DxStream()
    p_bad = st_bad.feed(encode_packet(
        5, [encode_record(8, bytes([0, 1])), bytes([0x09, 0, 0]),
            encode_record(8, bytes([0, 2]))]))
    check("stopped at the unknown type", len(p_bad.events), 1)
    check("and said why", "type 9" in p_bad.parse_error, True)

    # A record that runs off the end is refused, not zero-filled.
    st_trunc = DxStream()
    p_trunc = st_trunc.feed(bytes([0, 5, 1, EventType.APS_CARTRIDGE, 1, 2]))
    check("truncated record refused", len(p_trunc.events), 0)
    check("truncation explained", "remain" in p_trunc.parse_error, True)

    # Orientation bits.
    buf2 = encode_packet(0x65, [encode_record(
        EventType.DX_CODE_FULL, bytes([b0, b1, b2]), flags=0xC0)])
    pkt2 = st.feed(buf2)
    check("emulsion down set", pkt2.emulsion_down, True)
    check("tail first set", pkt2.tail_first, True)
    check("hardware_cb", pkt2.hardware_cb,
          HARDWARE_CB_FILM_EMULSION_DOWN | HARDWARE_CB_FILM_TAIL_FIRST)
    check("film sense clear here", pkt2.film_present, False)

    # A packet with no records carries NO status. It must not read as
    # "sensors clear", which would invent an end of roll out of an idle queue.
    st_empty = DxStream()
    p_empty = st_empty.feed(encode_packet(0x66, []))
    check("empty packet has no status", p_empty.status_valid, False)
    check("empty packet cannot say", p_empty.film_present, None)
    check("empty packet has no hwcb", p_empty.hardware_cb, 0)

    # Rollover of the 16-bit line counter.
    st2 = DxStream()
    st2.feed(encode_packet(0xFFF0, []))
    p = st2.feed(encode_packet(0x0010, []))
    check("rollover", p.line_counter, 0x10010)

    # The byte window is structural, not chosen: a type-3 payload is three
    # bytes, so the d1,d2,d3 window has nothing to read.
    check("type 3 payload is 3 bytes", DX_RECORD_PAYLOAD[3], 3)
    check("short payload decodes to nothing",
          decode_code_record(b"\x00\x00", full=True), None)
    c_win = decode_code_record(bytes([b0, b1, b2]), full=True)
    check("window is 0", c_win.window, 0)
    check("window 0 decodes the product", c_win.product, 109)

    # Vote ignores ambiguous events, and the refusal path still exists.
    v = DxVote()
    for _ in range(3):
        v.add(decode_dx_full(*encode_dx_full(109, 9, 12)))
    v.add(decode_dx_full(*encode_dx_full(21, 3, 12)))
    check("vote winner", v.winner(), (109, 9))
    check("accepted", v.accepted, 4)
    undecided = DxEvent(type=3, flags=0, payload=b"", line=0, code=None,
                        candidates=[decode_dx_full(b0, b1, b2),
                                    decode_dx_full(b0, b1, b2)])
    v2 = DxVote()
    v2.add(undecided)
    check("an undecided event still votes for nothing", v2.winner(), None)
    check("and is counted as such", v2.ambiguous, 1)

    # A rejected word contributes a line but no frame index (0x10013e99).
    bad_word = decode_dx_full(b0 ^ 0x04, b1, b2)
    check("corrupt word invalid", bad_word.valid, False)
    check("corrupt word has the sentinel frame", bad_word.frame, INVALID_FRAME)
    check("and reports no frame number", bad_word.frame_number, None)

    print("FAILED" if fails else "OK")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--selftest", action="store_true", help="run the built-in checks")
    ap.add_argument("--hex", help="decode one 30-byte 0x90 response given as hex")
    ap.add_argument("--half-lines", action="store_true",
                    help="DPI base 4: halve reported line numbers")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    if args.hex:
        buf = bytes.fromhex(args.hex.replace(" ", "").replace(":", ""))
        pkt = DxStream(half_lines=args.half_lines).feed(buf)
        print(f"line counter {pkt.line_counter}  "
              f"records declared {pkt.records_declared} parsed {len(pkt.events)}")
        if pkt.status_valid:
            print(f"status 0x{pkt.status:02X}  hwcb 0x{pkt.hardware_cb:08X}  "
                  f"film {'PRESENT' if pkt.film_present else 'absent'}")
            if pkt.emulsion_down:
                print("  FILM EMULSION DOWN")
            if pkt.tail_first:
                print("  FILM TAIL FIRST")
        else:
            print("status ABSENT — no records, so the board reported no flags. "
                  "This is not 'sensors clear'.")
        for ev in pkt.events:
            name = (EventType(ev.type).name
                    if ev.type in EventType._value2member_map_ else f"?{ev.type}")
            line = f"  {name:14s} line {ev.line:8d}  {ev.payload.hex()}"
            if ev.code is not None:
                c = ev.code
                line += (f"  product {c.product} specifier {c.specifier}"
                         f" dx {c.dx_number} frame {c.frame_number}"
                         f" {'OK' if c.valid else 'REJECTED (parity/mbz)'}")
            elif ev.candidates:
                line += (f"  AMBIGUOUS ({len(ev.candidates)} readings, none "
                         f"discriminated) -- no reading")
            print(line)
        if pkt.parse_error:
            print(f"  ! {pkt.parse_error}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
