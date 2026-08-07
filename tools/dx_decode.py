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
    Every field is transcribed from TLB.dll (F-135, base 0x10000000,
    MD5 e7f21021e0140c1935a3ae4de7bd3498) with the address in a comment.
    Cross-check that holds: product is 7 bits (0-127) and specifier 4 bits
    (0-15), matching the PIMA/I3A Part 1 / Part 2 widths in docs/09.

THE ONE UNKNOWN, AND HOW IT IS HANDLED
    The vendor reads the code word from either payload bytes d0,d1,d2 or
    d1,d2,d3, selected by CiDxAndApsHole+0x08. Which applies to 35 mm was NOT
    determined from the binary. Rather than guess -- a wrong guess yields a
    plausible but WRONG film stock, silently -- this module decodes BOTH
    windows and reports a product only when exactly one passes validation.
    When both or neither pass, it reports AMBIGUOUS and refuses to choose.

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
DX_RECORD_STRIDE = 5      # fcn.10009790 @ 0x10009923 / 0x10009928
DX_HEADER_LEN = 3
DX_MAX_EVENTS = (DX_RESPONSE_LEN - DX_HEADER_LEN) // DX_RECORD_STRIDE  # 5

# Only issue the 0x90 read when the light board's interrupt-status byte has
# these bits set -- FN_bDrvGetPpbInterruptStatus @ 0x1000bf80.
DX_POLL_GATE_MASK = 0xA4

# --------------------------------------------------------------------------
# Status flags: high nibble of the FIRST record's type byte only
# (fcn.10009790 @ 0x10009890 `cmp edi, 3`).
# Translation is fcn.10014320 @ 0x10014320-0x10014343; constant names from
# research/net/TLXLib.il lines 2996-2999.
# --------------------------------------------------------------------------
DXSTAT_FILM_SENSE_EXIT = 0x10
DXSTAT_FILM_SENSE_ENTRY = 0x20
DXSTAT_EMULSION_DOWN = 0x40
DXSTAT_TAIL_FIRST = 0x80

HARDWARE_CB_FILM_EMULSION_DOWN = 0x10000000
HARDWARE_CB_FILM_TAIL_FIRST = 0x20000000
HARDWARE_CB_FILM_SENSE_ENTRY = 0x40000000
HARDWARE_CB_FILM_SENSE_EXIT = 0x80000000

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


# Types whose payload bytes d1,d2 hold the event's own 16-bit line number.
# Types 3 and 4 instead use the packet-level counter and spend all four
# payload bytes on code data. fcn.10009790 @ 0x1000992b-0x1000993d.
_TYPES_WITH_OWN_LINE = frozenset({1, 2, 5, 6, 7, 8})

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
    window: int       # which byte window produced this: 0 = d0d1d2, 1 = d1d2d3

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


def decode_both_windows(payload: bytes, full: bool) -> tuple[DxCode | None, list[DxCode]]:
    """Decode a code record under BOTH byte windows and refuse to guess.

    The vendor picks the window from CiDxAndApsHole+0x08 (fcn.10013cd0
    @ 0x10013cd3-0x10013cf6). Its value for 35 mm is UNKNOWN, so we try both.

    Returns (resolved, candidates). `resolved` is the single decode that
    passed validation, or None when zero or two passed -- i.e. AMBIGUOUS.
    Callers must treat None as "no reading", never as an excuse to pick one.
    """
    cands: list[DxCode] = []
    for w in (0, 1):
        if full:
            cands.append(decode_dx_full(payload[w], payload[w + 1], payload[w + 2], w))
        else:
            cands.append(decode_dx_short(payload[w], payload[w + 1], w))
    passed = [c for c in cands if c.valid]
    return (passed[0] if len(passed) == 1 else None), cands


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
@dataclass
class DxEvent:
    type: int
    flags: int          # high nibble; only meaningful on the first record
    payload: bytes      # 4 bytes d0..d3
    line: int           # absolute scan line, rollover-extended
    code: DxCode | None = None          # resolved decode, or None if AMBIGUOUS
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
        pkt = DxPacket(line_counter=packet_line)

        off = DX_HEADER_LEN
        for i in range(n):
            if off + DX_RECORD_STRIDE > len(buf):
                break
            type_byte = buf[off]
            etype = type_byte & 0x0F                    # 0x1000988d
            payload = bytes(buf[off + 1 : off + 5])

            if i == 0:                                  # 0x10009890
                pkt.status = type_byte & 0xF0           # 0x1000989d-0x100098a5
                for bit, hwcb in _STATUS_TO_HWCB:
                    if pkt.status & bit:
                        pkt.hardware_cb |= hwcb

            if etype in _TYPES_WITH_OWN_LINE:
                # (rollovers << 16) | (d1 << 8) | d2, 0x1000993d-0x10009950
                line = (self.rollovers << 16) | (payload[1] << 8) | payload[2]
                if line + 10000 < self.prev_line:       # 0x10009952-0x1000995d
                    line += 0x10000
            else:
                line = packet_line

            if self.half_lines:
                line >>= 1

            ev = DxEvent(type=etype, flags=type_byte & 0xF0, payload=payload, line=line)

            if etype == EventType.DX_CODE_FULL:
                ev.code, ev.candidates = decode_both_windows(payload, full=True)
            elif etype == EventType.DX_CODE_SHORT:
                ev.code, ev.candidates = decode_both_windows(payload, full=False)

            pkt.events.append(ev)
            off += DX_RECORD_STRIDE

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

    # Packet framing, status nibble, rollover.
    st = DxStream()
    b0, b1, b2 = encode_dx_full(109, 9, 12)
    rec3 = bytes([0x30 | EventType.DX_CODE_FULL, b0, b1, b2, 0x00])
    rec8 = bytes([EventType.PERF_LEADING, 0x00, 0x12, 0x34, 0x00])
    buf = bytes([0x00, 0x64, 2]) + rec3 + rec8
    buf += b"\x00" * (DX_RESPONSE_LEN - len(buf))
    pkt = st.feed(buf)
    check("packet line", pkt.line_counter, 0x64)
    check("event count", len(pkt.events), 2)
    check("status nibble", pkt.status, 0x30)
    check("film at entry", pkt.film_at_entry, True)
    check("film at exit", pkt.film_at_exit, True)
    check("emulsion down", pkt.emulsion_down, False)
    check("tail first", pkt.tail_first, False)
    check("perf line", pkt.events[1].line, 0x1234)

    # The window must resolve to exactly one candidate here.
    ev = pkt.events[0]
    check("window resolved", ev.code is not None, True)
    if ev.code:
        check("dx product", ev.code.product, 109)
        check("dx specifier", ev.code.specifier, 9)
        check("dx window", ev.code.window, 0)
    check("not ambiguous", ev.ambiguous, False)

    # Orientation bits.
    buf2 = bytes([0x00, 0x65, 1]) + bytes([0xC0 | EventType.DX_CODE_FULL, b0, b1, b2, 0x00])
    buf2 += b"\x00" * (DX_RESPONSE_LEN - len(buf2))
    pkt2 = st.feed(buf2)
    check("emulsion down set", pkt2.emulsion_down, True)
    check("tail first set", pkt2.tail_first, True)
    check("hardware_cb", pkt2.hardware_cb,
          HARDWARE_CB_FILM_EMULSION_DOWN | HARDWARE_CB_FILM_TAIL_FIRST)

    # Rollover of the 16-bit line counter.
    st2 = DxStream()
    st2.feed(bytes([0xFF, 0xF0, 0]) + b"\x00" * 27)
    p = st2.feed(bytes([0x00, 0x10, 0]) + b"\x00" * 27)
    check("rollover", p.line_counter, 0x10010)

    # Ambiguity must be reported, never silently resolved. Search for a payload
    # where both windows validate; assert we return None rather than guessing.
    found_ambiguous = False
    for d3 in range(256):
        payload = bytes([b0, b1, b2, d3])
        resolved, cands = decode_both_windows(payload, full=True)
        if sum(c.valid for c in cands) == 2:
            found_ambiguous = True
            check("both-valid returns None", resolved, None)
            break
    check("an ambiguous payload exists", found_ambiguous, True)

    # Vote ignores ambiguous events.
    v = DxVote()
    for _ in range(3):
        v.add(decode_dx_full(*encode_dx_full(109, 9, 12)))
    v.add(decode_dx_full(*encode_dx_full(21, 3, 12)))
    check("vote winner", v.winner(), (109, 9))
    check("accepted", v.accepted, 4)

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
        print(f"line counter {pkt.line_counter}  status 0x{pkt.status:02X}"
              f"  hwcb 0x{pkt.hardware_cb:08X}")
        if pkt.emulsion_down:
            print("  FILM EMULSION DOWN")
        if pkt.tail_first:
            print("  FILM TAIL FIRST")
        for ev in pkt.events:
            name = (EventType(ev.type).name
                    if ev.type in EventType._value2member_map_ else f"?{ev.type}")
            line = f"  {name:14s} line {ev.line:8d}  {ev.payload.hex()}"
            if ev.code is not None:
                c = ev.code
                line += (f"  product {c.product} specifier {c.specifier}"
                         f" dx {c.dx_number} frame {c.frame_number}"
                         f" [window {c.window}]")
            elif ev.candidates:
                nvalid = sum(c.valid for c in ev.candidates)
                line += f"  AMBIGUOUS ({nvalid} of 2 windows validate) -- no reading"
            print(line)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
