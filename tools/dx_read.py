#!/usr/bin/env python3
"""Read DX code words off the light board, log the raw bytes, decode them.

WHAT THIS IS
    The missing half of the DX story. ``tools/dx_decode.py`` knows how to turn
    a 30-byte DX packet into (product, specifier, frame); this module knows how
    to *get* those packets out of the scanner, and writes down exactly what
    came back so a wrong decode can be re-argued later without re-scanning a
    roll of film.

HOW THE HOST GETS DX DATA  (docs/53-edge-data.md s1.1, s6)
    Two register reads on the light board, address 0x40:

        01 03 40 01 02      interrupt status, 1 byte   (the gate)
        01 03 40 1E 90      DX events, 30 bytes        (the payload)

    Read the gate; if it has any of the bits 0xA4 set, read 0x90. Both packet
    layouts are transcribed from TLB.dll -- see tools/pakon_commands.py for the
    addresses. A packet has 27 bytes of record budget and records are 3 to 6
    bytes, so it carries between 4 and 9 events depending on their types -- not
    the flat five a fixed stride implied. Either way the poll has to outrun
    their arrival or code words are silently dropped; the vendor polls at
    200 ms idle and 1 ms while scanning (0x1002ed2f).

    Nothing here starts the DX scan or moves film. ``PPB_START_DX_SCAN`` (0x91)
    is already issued by tools/pakon_scan.py on every scan, and pakon_scan is
    the only code in this project that makes the owner's film move. Polling is
    pure reads, so it is safe to run against a live scan or an idle scanner.

WHAT IT REFUSES TO DO
    It does not guess. Where dx_decode declines -- a type byte the board never
    emits, a record that runs off the end of the packet, a word that fails
    parity -- this module records the refusal and reads nothing. A code word
    that did not validate contributes nothing to the product vote.

    The byte-window question (docs/53 s1.4) is no longer one of those places:
    docs/57 s10.2 resolved it to the `obj+0x08 == 0` window, structurally, and
    dx_decode now decodes that one window. The tallies kept here are about
    whether words *validate*, which is still the experiment that says whether
    the read is right.

RAW LOG
    JSON Lines, one object per line, written as it goes so a crash keeps what
    was seen. Every DX record carries the complete USB response as hex, header
    bytes and all, plus the gate byte that let it through and both a monotonic
    elapsed time and a wall clock. ``dx_read.py replay LOG`` re-derives every
    decode from those bytes alone.

    {"kind":"header", ...}                       once, first line
    {"kind":"gate","t":..,"raw":"..","value":0}  on every change of the gate
    {"kind":"dx","seq":1,"t":..,"raw":"01 20 40 88 .."}
    {"kind":"note"|"error", ...}
    {"kind":"summary", ...}                      once, last line

USAGE
    python3 tools/dx_read.py probe                  # one gate + one DX read
    python3 tools/dx_read.py poll --seconds 30 --log dx.jsonl
    python3 tools/dx_read.py replay dx.jsonl
    python3 tools/dx_read.py selftest

STATUS
    The packet layout is [VERIFIED] from TLB.dll. Whether this scanner's light
    board answers a read of register 0x02 at all is NOT yet known -- docs/03
    records a register sweep in which "the light board exposes only registers
    0 and 1". If the gate read errors, ``poll`` says so and falls back to
    reading 0x90 ungated, which is the honest thing to do and is recorded in
    the log. No DX packet from this machine has ever been seen.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dx_decode as dxd                             # noqa: E402
import pakon_commands as pc                         # noqa: E402

LOG_VERSION = 1

#: Minimum seconds between gate reads while a scan is running. The vendor's
#: fast cadence is 1 ms (docs/53 s1.1.1); 5 ms is 200 polls/s, which is two
#: orders of magnitude more than the event rate a 35 mm roll can produce
#: (a half-frame code every few seconds, eight perforations per frame) and
#: leaves the image endpoint alone.
DEFAULT_INTERVAL_S = 0.005
#: Idle cadence, for polling a scanner that is not scanning.
IDLE_INTERVAL_S = 0.2

#: How many consecutive failed gate reads before giving up on the gate and
#: polling 0x90 unconditionally.
GATE_FAILURES_BEFORE_FALLBACK = 5


# --------------------------------------------------------------------------
# raw response handling
# --------------------------------------------------------------------------

def dx_payload(raw: bytes) -> bytes | None:
    """The 30 DX bytes inside a raw ``01 20 40 SS ...`` response.

    Returns None if ``raw`` is too short to contain them. A read reply is
    ``01 <count+2> <addr> <status> <count bytes>`` (docs/03), so the payload
    starts at byte 4. Accepts a bare 30-byte payload too, for logs written by
    something that had already stripped the header.
    """
    if len(raw) == pc.DX_RESPONSE_LEN:
        return bytes(raw)
    if len(raw) >= 4 + pc.DX_RESPONSE_LEN:
        return bytes(raw[4:4 + pc.DX_RESPONSE_LEN])
    return None


def response_status(raw: bytes) -> int | None:
    """Byte 3 of a response: 0 or 8 mean success (docs/03)."""
    return raw[3] if len(raw) > 3 else None


def status_ok(raw: bytes) -> bool:
    s = response_status(raw)
    return s is not None and not (s & pc.STATUS_ERROR_MASK)


# --------------------------------------------------------------------------
# roll-level accumulation
# --------------------------------------------------------------------------

@dataclass
class WindowEvidence:
    """Whether code words validate under the resolved byte window.

    This used to tally which of *two* byte windows passed, because docs/53
    s1.4 could not say which one 35 mm uses. docs/57 s10.2 settled it: a
    type-3 record carries exactly three payload bytes, so there is no d1,d2,d3
    window to try, and dx_decode now decodes the one that exists.

    What is left is still worth counting, and is still the experiment that says
    whether the whole read is right: how many words pass parity and the
    must-be-zero bit, and how many do not. A roll that produces dozens of
    rejects and no passes means the front end, the framing or the table is
    wrong -- it does not mean "try the other window", because there isn't one.

    The field names are unchanged so that logs and sidecars written before this
    can still be replayed and compared. ``window0_only`` is now simply
    "validated"; ``window1_only`` and ``both`` can no longer be produced and
    are kept at zero rather than removed.
    """

    window0_only: int = 0        # validated under the resolved window
    window1_only: int = 0        # unreachable now; kept for log compatibility
    both: int = 0                # unreachable now; kept for log compatibility
    neither: int = 0             # rejected: parity or must-be-zero failed

    #: Words the decoder could not read at all -- a short or unframable record.
    unreadable: int = 0

    def add(self, code) -> None:
        """Record one code-word outcome. ``code`` is a DxCode, or None."""
        if code is None:
            self.unreadable += 1
        elif code.valid:
            self.window0_only += 1
        else:
            self.neither += 1

    def verdict(self, need: int = 5) -> int | None:
        """The window, or None until enough words have actually validated.

        Still deliberately hard to satisfy. The window is resolved on firmware
        evidence, but this reports it only once ``need`` words have passed
        validation *on this machine* -- so a summary cannot claim a settled
        window off a roll where nothing decoded.
        """
        if self.window0_only >= need:
            return 0
        return None

    def to_json(self) -> dict:
        return {"window0_only": self.window0_only,
                "window1_only": self.window1_only,
                "both_valid_ambiguous": self.both,
                "neither_valid": self.neither,
                "unreadable": self.unreadable,
                "verdict": self.verdict(),
                "resolved_by": "docs/57 s10.2 — a type-3 record carries three "
                               "payload bytes, so the obj+0x08 != 0 window "
                               "cannot be formed"}


def anchor_vote(codes: list[tuple[int, int]], step: int) -> dict:
    """The vendor's best-anchor vote over the frame numbers, fcn.100144b0.

    ``codes`` is [(frame, line)] in arrival order, ``step`` the expected
    difference between consecutive codes (+1 head-first 35 mm, -1 tail-first;
    +/-2 for 24 mm -- docs/53 s2.1). For each candidate anchor i it predicts
    ``code[j] = code[i] + step*(j-i)`` and counts agreements
    (0x10014660-0x100146bd). The winner is the anchor with the most.

    This is the whole validation signal: real DX reads off one roll form an
    arithmetic sequence, and noise does not.
    """
    n = len(codes)
    if n == 0:
        return {"entries": 0, "agree": 0, "at": -1, "accepted": False}
    best_i, best_n = 0, 0
    for i in range(n):
        agree = sum(1 for j in range(n)
                    if codes[j][0] == codes[i][0] + step * (j - i))
        if agree > best_n:
            best_i, best_n = i, agree
    # 0x10014753-0x10014778: 1 agreeing code if <= 23 entries, else 2.
    need = 1 if (n // 8) <= 2 else 2
    return {"entries": n, "agree": best_n, "at": best_i,
            "need": need, "accepted": best_n >= need,
            "step": step}


@dataclass
class DxRoll:
    """Everything one poll session saw."""

    polls: int = 0
    dx_reads: int = 0
    packets: int = 0
    events: int = 0
    bad_responses: int = 0
    gate_failures: int = 0
    gated: bool = True
    gate_values: dict = field(default_factory=dict)
    type_counts: dict = field(default_factory=dict)
    codes: list = field(default_factory=list)        # accepted, unambiguous
    ambiguous: int = 0
    rejected: int = 0                                 # parity / must-be-zero
    perforations: list = field(default_factory=list)
    fat_bits: list = field(default_factory=list)
    film_edges: list = field(default_factory=list)
    hardware_cb: int = 0
    emulsion_down: bool = False
    tail_first: bool = False
    film_at_entry: bool = False
    film_at_exit: bool = False
    #: Packets that carried a status nibble at all, i.e. that had >= 1 record.
    #: A packet with none says nothing about the film sensors; see
    #: dx_decode.DxPacket.status_valid.
    status_packets: int = 0
    #: The most recent status nibble that was actually reported, and when.
    last_status: int | None = None
    last_status_at: float | None = None
    #: Packets whose record walk stopped early, with the first reason seen.
    parse_errors: int = 0
    first_parse_error: str = ""
    first_line: int | None = None
    last_line: int | None = None
    notes: list = field(default_factory=list)

    def to_json(self) -> dict:
        vote = dxd.DxVote()
        for c in self.codes:
            vote.add(c["code"])
        winner = vote.winner()
        frames = [(c["frame"], c["line"]) for c in self.codes
                  if c["frame"] is not None]
        pitches = [b[1] - a[1] for a, b in zip(frames, frames[1:])
                   if b[1] > a[1]]
        out = {
            "polls": self.polls,
            "dx_reads": self.dx_reads,
            "packets": self.packets,
            "events": self.events,
            "bad_responses": self.bad_responses,
            "gate_failures": self.gate_failures,
            "gated": self.gated,
            "gate_values": {f"0x{int(k):02X}": v
                            for k, v in sorted(self.gate_values.items())},
            "event_types": {dxd.EventType(t).name
                            if t in dxd.EventType._value2member_map_
                            else f"type{t}": n
                            for t, n in sorted(self.type_counts.items())},
            "code_words": len(self.codes),
            "ambiguous": self.ambiguous,
            "rejected": self.rejected,
            "perforations": len(self.perforations),
            "fat_bits": len(self.fat_bits),
            "film_edges": len(self.film_edges),
            "emulsion_down": self.emulsion_down,
            "tail_first": self.tail_first,
            "film_at_entry": self.film_at_entry,
            "film_at_exit": self.film_at_exit,
            "status_packets": self.status_packets,
            "last_status": (None if self.last_status is None
                            else f"0x{self.last_status:02X}"),
            "parse_errors": self.parse_errors,
            "first_parse_error": self.first_parse_error,
            "hardware_cb": f"0x{self.hardware_cb:08X}",
            "line_span": [self.first_line, self.last_line],
            "product": winner[0] if winner else None,
            "specifier": winner[1] if winner else None,
            "vote": [{"product": p, "specifier": s, "count": c}
                     for (p, s), c in zip(vote.pairs, vote.counts)],
            "frames": frames,
            "mean_code_pitch_lines": (round(sum(pitches) / len(pitches), 1)
                                      if pitches else None),
            "anchor_35mm_head_first": anchor_vote(frames, +1),
            "anchor_35mm_tail_first": anchor_vote(frames, -1),
            "notes": self.notes,
        }
        if winner is None:
            out["film_stock"] = None
            out["why_no_stock"] = (
                "no DX code word passed validation unambiguously"
                if not self.codes else "vote produced no winner")
        else:
            out["film_stock"] = f"{winner[0]}-{winner[1]}"
        return out


# --------------------------------------------------------------------------
# the poller
# --------------------------------------------------------------------------

class DxReader:
    """Polls the light board for DX events and writes a raw log.

    ``xfer`` is any callable taking a command packet and returning the raw
    response bytes, or None/b'' on failure -- ``pakon_scan.Link.xfer`` and
    ``pakon_cmd.exchange`` both fit. Nothing else about the caller is assumed,
    so this works inside a live scan or standalone.
    """

    def __init__(self, xfer, log_path: str | Path | None = None,
                 board: int = pc.AD_LIGHT,
                 interval: float = DEFAULT_INTERVAL_S,
                 half_lines: bool = False,
                 gate: bool = True,
                 meta: dict | None = None) -> None:
        self.xfer = xfer
        self.board = int(board)
        self.interval = float(interval)
        self.gate = bool(gate)
        self.stream = dxd.DxStream(half_lines=half_lines)
        self.roll = DxRoll(gated=bool(gate))
        self.window = WindowEvidence()
        self.t0 = time.monotonic()
        self.seq = 0
        self._next = 0.0
        self._last_gate: int | None = None
        self._gate_fail_run = 0
        self._fh = None
        if log_path:
            p = Path(log_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._fh = p.open("a", buffering=1)
            self._write({
                "kind": "header", "v": LOG_VERSION, "tool": "dx_read.py",
                "started": time.time(), "board": self.board,
                "gate_register": pc.REG_LIGHT_INTERRUPT_STATUS,
                "gate_mask": pc.DX_GATE_DX,
                "dx_register": pc.REG_LIGHT_DX_CODE,
                "dx_length": pc.DX_RESPONSE_LEN,
                "interval_s": self.interval, "gated": self.gate,
                "half_lines": half_lines,
                "meta": meta or {},
            })

    # ---- log ----
    def _write(self, rec: dict) -> None:
        if self._fh is None:
            return
        try:
            self._fh.write(json.dumps(rec) + "\n")
        except OSError:
            pass

    def note(self, what: str, **kw) -> None:
        self.roll.notes.append(what)
        self._write({"kind": "note", "t": round(self.elapsed, 4),
                     "what": what, **kw})

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    # ---- polling ----
    def due(self, now: float | None = None) -> bool:
        return (now if now is not None else time.monotonic()) >= self._next

    def poll_if_due(self, now: float | None = None):
        now = now if now is not None else time.monotonic()
        if now < self._next:
            return None
        return self.poll()

    def poll(self):
        """One gate read, and a DX read if the gate lets it through.

        Returns the decoded :class:`dx_decode.DxPacket`, or None when there was
        nothing to read. Never raises on a transport failure: a scan must not
        die because DX polling did.
        """
        self._next = time.monotonic() + self.interval
        self.roll.polls += 1
        want = True

        if self.gate:
            raw = self._safe_xfer(pc.read_interrupt_status(self.board))
            if not raw or not status_ok(raw) or len(raw) < 5:
                self._gate_fail_run += 1
                self.roll.gate_failures += 1
                if self._gate_fail_run == 1:
                    self._write({"kind": "error", "t": round(self.elapsed, 4),
                                 "what": "gate read failed",
                                 "raw": raw.hex(" ") if raw else None})
                if self._gate_fail_run >= GATE_FAILURES_BEFORE_FALLBACK:
                    self.gate = False
                    self.roll.gated = False
                    self.note(
                        f"register 0x{pc.REG_LIGHT_INTERRUPT_STATUS:02X} did "
                        f"not answer {self._gate_fail_run} times; polling "
                        f"0x{pc.REG_LIGHT_DX_CODE:02X} ungated from here on")
                return None
            self._gate_fail_run = 0
            value = raw[4]
            self.roll.gate_values[value] = self.roll.gate_values.get(value, 0) + 1
            if value != self._last_gate:
                self._last_gate = value
                self._write({"kind": "gate", "t": round(self.elapsed, 4),
                             "value": value, "raw": raw.hex(" ")})
            want = bool(value & pc.DX_GATE_DX)
            gate_byte = value
        else:
            gate_byte = None

        if not want:
            return None
        return self._read_dx(gate_byte)

    def _read_dx(self, gate_byte: int | None):
        raw = self._safe_xfer(pc.read_dx_code(self.board))
        self.roll.dx_reads += 1
        self.seq += 1
        rec = {"kind": "dx", "seq": self.seq, "t": round(self.elapsed, 4),
               "wall": round(time.time(), 4),
               "gate": gate_byte,
               "raw": raw.hex(" ") if raw else None}
        if not raw or not status_ok(raw):
            self.roll.bad_responses += 1
            rec["kind"] = "error"
            rec["what"] = "DX read failed"
            self._write(rec)
            return None
        payload = dx_payload(raw)
        if payload is None:
            self.roll.bad_responses += 1
            rec["kind"] = "error"
            rec["what"] = f"short DX response, {len(raw)} bytes"
            self._write(rec)
            return None
        self._write(rec)
        return self.ingest(payload)

    def _safe_xfer(self, pkt: bytes) -> bytes | None:
        try:
            r = self.xfer(pkt)
        except Exception as e:                              # noqa: BLE001
            self._write({"kind": "error", "t": round(self.elapsed, 4),
                         "what": f"transport: {e}", "pkt": pkt.hex(" ")})
            return None
        return bytes(r) if r else None

    # ---- decode ----
    def ingest(self, payload: bytes):
        """Feed 30 payload bytes through dx_decode and accumulate."""
        try:
            pkt = self.stream.feed(payload)
        except ValueError:
            self.roll.bad_responses += 1
            return None
        r = self.roll
        r.packets += 1
        if r.first_line is None:
            r.first_line = pkt.line_counter
        r.last_line = pkt.line_counter
        if pkt.parse_error:
            r.parse_errors += 1
            if not r.first_parse_error:
                r.first_parse_error = pkt.parse_error
                self.note(f"packet framing: {pkt.parse_error}")
        # Status is only present when the packet carried a record. Accumulating
        # from a packet without one would turn an idle queue into "sensors
        # clear", which the film-sense end-of-roll signal must never see.
        if pkt.status_valid:
            r.status_packets += 1
            r.last_status = pkt.status
            r.last_status_at = self.elapsed
            r.hardware_cb |= pkt.hardware_cb
            r.emulsion_down |= pkt.emulsion_down
            r.tail_first |= pkt.tail_first
            r.film_at_entry |= pkt.film_at_entry
            r.film_at_exit |= pkt.film_at_exit

        for ev in pkt.events:
            r.events += 1
            r.type_counts[ev.type] = r.type_counts.get(ev.type, 0) + 1
            if ev.type in (dxd.EventType.DX_CODE_FULL, dxd.EventType.DX_CODE_SHORT):
                self.window.add(ev.code)
                if ev.ambiguous:
                    r.ambiguous += 1
                elif ev.code is not None and ev.code.valid:
                    r.codes.append({
                        "line": ev.line,
                        "frame": ev.code.frame if ev.code.frame not in
                        (None, dxd.INVALID_FRAME) else None,
                        "product": ev.code.product,
                        "specifier": ev.code.specifier,
                        "window": ev.code.window,
                        "payload": ev.payload.hex(),
                        "code": ev.code,
                    })
                else:
                    r.rejected += 1
            elif ev.type in (dxd.EventType.PERF_LEADING, dxd.EventType.PERF_TRAILING):
                r.perforations.append((int(ev.type), ev.line))
            elif ev.type == dxd.EventType.FAT_BIT:
                r.fat_bits.append(ev.line)
            elif ev.type == dxd.EventType.FILM_EDGE:
                r.film_edges.append(ev.line)
        return pkt

    # ---- finish ----
    def summary(self) -> dict:
        out = self.roll.to_json()
        out["window_evidence"] = self.window.to_json()
        out["seconds"] = round(self.elapsed, 3)
        return out

    def close(self) -> dict:
        s = self.summary()
        self._write({"kind": "summary", "t": round(self.elapsed, 4), **s})
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
        return s


# --------------------------------------------------------------------------
# replay: decode a log without the scanner
# --------------------------------------------------------------------------

def replay(path: str | Path, half_lines: bool = False) -> dict:
    """Re-derive every decode from the raw bytes in a log.

    The point of logging raw is that this can be re-run after the decoder
    changes, against film that has long since been developed and filed.
    """
    reader = DxReader(xfer=lambda _p: None, log_path=None,
                      half_lines=half_lines)
    header = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = rec.get("kind")
        if kind == "header":
            header = rec
        elif kind == "dx" and rec.get("raw"):
            raw = bytes.fromhex(rec["raw"].replace(" ", ""))
            payload = dx_payload(raw)
            if payload is not None:
                reader.roll.dx_reads += 1
                reader.ingest(payload)
        elif kind == "gate" and rec.get("value") is not None:
            v = int(rec["value"])
            reader.roll.gate_values[v] = reader.roll.gate_values.get(v, 0) + 1
    out = reader.summary()
    out["log"] = str(path)
    out["log_header"] = header
    return out


# --------------------------------------------------------------------------
# film stock
# --------------------------------------------------------------------------

def film_stock(product: int | None, specifier: int | None) -> dict:
    """Name the stock, or say plainly that it cannot be named.

    The DX board returns *only* Part 1 (7 bits) and Part 2 (4 bits), which is
    exactly how research/film-products.json is keyed -- so this is a direct
    lookup with no encoding step. There is no six-digit number anywhere in the
    chain; see docs/53 s7.
    """
    if product is None:
        return {"resolved": False,
                "why": "no DX product number was read"}
    try:
        import pakon_filmstock as film
        s = film.lookup(product, specifier)
    except Exception as e:                                  # noqa: BLE001
        return {"resolved": False, "product": product,
                "specifier": specifier, "why": str(e)}
    return {"resolved": True, "product": product, "specifier": specifier,
            "dx": f"{product}-{specifier}", "name": s.name,
            "manufacturer": s.manufacturer, "path": s.path, "iso": s.iso,
            "sba_override": s.sba_override}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _open_link(dry_run: bool = False):
    """Borrow pakon_scan's USB link. Imported here, not at module scope,
    because pakon_scan imports this module."""
    import pakon_scan as scan
    return scan.Link.open(dry_run=dry_run)


def _print_summary(s: dict) -> None:
    print(f"  polls {s['polls']}  DX reads {s['dx_reads']}  "
          f"packets {s['packets']}  events {s['events']}  "
          f"bad {s['bad_responses']}")
    if not s["gated"]:
        print("  gate: NOT USED — register 0x02 did not answer")
    elif s["gate_values"]:
        print(f"  gate values seen: {s['gate_values']}")
    if s["event_types"]:
        print(f"  event types: {s['event_types']}")
    print(f"  code words {s['code_words']}  ambiguous {s['ambiguous']}  "
          f"rejected {s['rejected']}  perforations {s['perforations']}")
    w = s["window_evidence"]
    print(f"  code words: {w['window0_only']} validated, "
          f"{w['neither_valid']} rejected, {w['unreadable']} unreadable -> "
          f"{'window 0 confirmed on this machine' if w['verdict'] is not None else 'NOT YET CONFIRMED on hardware'}")
    if s.get("parse_errors"):
        print(f"  packet framing: {s['parse_errors']} packet(s) stopped early "
              f"— {s.get('first_parse_error', '')}")
    print(f"  status packets {s['status_packets']} "
          f"(last {s['last_status'] or 'none'}); "
          f"a packet with no records carries no status")
    if s["emulsion_down"]:
        print("  FILM EMULSION DOWN")
    if s["tail_first"]:
        print("  FILM TAIL FIRST")
    if s["product"] is None:
        print(f"  film stock: NONE — {s.get('why_no_stock', '')}")
    else:
        st = film_stock(s["product"], s["specifier"])
        print(f"  DX {s['product']}-{s['specifier']}  "
              f"{st.get('name') or st.get('why')}")
        print(f"  vote: {s['vote']}")
    if s["frames"]:
        print(f"  frames (half-frame code, line): {s['frames'][:20]}"
              f"{' …' if len(s['frames']) > 20 else ''}")
        print(f"  printed frame numbers (35 mm, code/2): "
              f"{[round(c / 2, 1) for c, _ in s['frames'][:20]]}")
        # The vendor's acceptance gate is one agreeing code below 24 entries
        # (0x10014753), so BOTH directions can read "accepted". The count is
        # what discriminates; the authority on direction is the tail-first
        # status bit, not this.
        h = s["anchor_35mm_head_first"]
        t = s["anchor_35mm_tail_first"]
        print(f"  anchor head-first {h}")
        print(f"  anchor tail-first {t}")
        print(f"  sequence agrees better "
              f"{'head-first' if h['agree'] > t['agree'] else 'tail-first' if t['agree'] > h['agree'] else 'equally either way'}"
              f" ({h['agree']} vs {t['agree']} of {h['entries']}); "
              f"the status bit says "
              f"{'TAIL FIRST' if s['tail_first'] else 'head first'}")
    for n in s.get("notes", []):
        print(f"  note: {n}")


def cmd_probe(a) -> int:
    link = _open_link(dry_run=a.dry_run)
    try:
        g = pc.read_interrupt_status(a.board)
        rg = link.xfer(g)
        print(f"gate  -> {g.hex(' ')}")
        print(f"      <- {rg.hex(' ') if rg else 'NO RESPONSE'}")
        if rg and status_ok(rg) and len(rg) > 4:
            v = rg[4]
            print(f"      status byte 0x{v:02X}: "
                  f"DX {'SET' if v & pc.DX_GATE_DX else 'clear'} (& 0xA4), "
                  f"lamp {'SET' if v & pc.DX_GATE_LAMP else 'clear'} (& 0x5B)")
        elif rg:
            print("      the light board did not accept a read of register "
                  "0x02 — docs/03 records the same for registers above 1")

        d = pc.read_dx_code(a.board)
        rd = link.xfer(d)
        print(f"dx    -> {d.hex(' ')}")
        print(f"      <- {rd.hex(' ') if rd else 'NO RESPONSE'}")
        payload = dx_payload(rd) if rd else None
        if rd and status_ok(rd) and payload:
            r = DxReader(xfer=lambda _p: None, half_lines=a.half_lines)
            pkt = r.ingest(payload)
            if pkt:
                print(f"      line counter {pkt.line_counter}, "
                      f"{len(pkt.events)} event(s), "
                      f"status 0x{pkt.status:02X}")
                for ev in pkt.events:
                    name = (dxd.EventType(ev.type).name
                            if ev.type in dxd.EventType._value2member_map_
                            else f"type{ev.type}")
                    print(f"        {name:14s} line {ev.line:8d}  "
                          f"{ev.payload.hex()}")
        return 0
    finally:
        link.close()


def cmd_poll(a) -> int:
    link = _open_link(dry_run=a.dry_run)
    started = False
    try:
        if a.start is not None:
            from write_guard import require_writes_unlocked
            require_writes_unlocked(
                "dx_read.py --start",
                "writes light-board register 0x91 to start the DX reader")
            pkt = pc.dx_start(a.start, a.format)
            r = link.xfer(pkt)
            started = True
            print(f"DX start -> {pkt.hex(' ')}  <- "
                  f"{r.hex(' ') if r else 'NO RESPONSE'}")

        r = DxReader(link.xfer, log_path=a.log, board=a.board,
                     interval=a.interval / 1000.0, half_lines=a.half_lines,
                     gate=not a.ungated,
                     meta={"cmd": "poll", "seconds": a.seconds,
                           "started_dx": started})
        print(f"polling for {a.seconds:.0f} s at {a.interval:.1f} ms"
              + (f", logging to {a.log}" if a.log else ", NOT logging"))
        deadline = time.monotonic() + a.seconds
        last_report = 0.0
        try:
            while time.monotonic() < deadline:
                pkt = r.poll_if_due()
                if pkt is not None and a.verbose:
                    print(f"  [{r.elapsed:7.3f}] line {pkt.line_counter:8d} "
                          f"status 0x{pkt.status:02X} "
                          f"{len(pkt.events)} event(s)")
                if r.elapsed - last_report >= 5.0:
                    last_report = r.elapsed
                    print(f"  [{r.elapsed:7.1f}] polls {r.roll.polls} "
                          f"packets {r.roll.packets} events {r.roll.events} "
                          f"codes {len(r.roll.codes)}")
                time.sleep(max(0.0, r._next - time.monotonic()))
        except KeyboardInterrupt:
            print("\ninterrupted")
        s = r.close()
        print("\nsummary:")
        _print_summary(s)
        if a.json:
            print(json.dumps(s, indent=1, default=str))
        return 0
    finally:
        if started:
            try:
                link.xfer(pc.dx_stop(a.board))
            except Exception:                               # noqa: BLE001
                pass
        link.close()


def cmd_replay(a) -> int:
    s = replay(a.log, half_lines=a.half_lines)
    if a.json:
        print(json.dumps(s, indent=1, default=str))
        return 0
    print(f"{a.log}")
    _print_summary(s)
    return 0


def cmd_selftest(a) -> int:
    """End to end over a synthetic scanner, so the packet path is tested
    without film. Proves the wire format, the gate, the raw log and that
    replay reproduces the live decode byte for byte."""
    import tempfile

    fails = 0

    def check(label, got, want):
        nonlocal fails
        if got != want:
            print(f"FAIL {label}: got {got!r}, want {want!r}")
            fails += 1

    # A fake light board that hands out a scripted DX event stream.
    class FakeLight:
        def __init__(self, packets):
            self.packets = list(packets)
            self.gate_reads = 0
            self.dx_reads = 0

        def __call__(self, pkt):
            if pkt == pc.read_interrupt_status():
                self.gate_reads += 1
                v = pc.DX_GATE_DX if self.packets else 0x00
                return bytes([0x01, 0x03, pc.AD_LIGHT, 0x00, v])
            if pkt == pc.read_dx_code():
                self.dx_reads += 1
                body = self.packets.pop(0) if self.packets else bytes(30)
                return bytes([0x01, 0x20, pc.AD_LIGHT, 0x00]) + body
            raise AssertionError(f"unexpected packet {pkt.hex(' ')}")

    # Three half-frame codes at 100-line spacing, product 96 specifier 1
    # (Kodak Gold 400 Gen 9 -- the roll the owner is going to test with).
    # Each packet is a code word followed by two perforations, which is the
    # mix a real roll produces and the mix a fixed 5-byte stride cannot walk.
    packets = []
    for i, frame in enumerate((10, 11, 12)):
        b0, b1, b2 = dxd.encode_dx_full(96, 1, frame)
        line = 1000 + 100 * i
        recs = [
            dxd.encode_record(dxd.EventType.DX_CODE_FULL, bytes([b0, b1, b2]),
                              flags=dxd.DXSTAT_FILM_SENSE),
            dxd.encode_record(dxd.EventType.PERF_LEADING,
                              bytes([(line + 10) >> 8, (line + 10) & 0xFF])),
            dxd.encode_record(dxd.EventType.PERF_TRAILING,
                              bytes([(line + 20) >> 8, (line + 20) & 0xFF])),
        ]
        packets.append(dxd.encode_packet(line, recs))

    light = FakeLight(packets)
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "dx.jsonl"
        r = DxReader(light, log_path=log, interval=0.0)
        for _ in range(6):
            r.poll()
        live = r.close()

        check("gate reads", light.gate_reads, 6)
        check("dx reads", light.dx_reads, 3)
        check("packets", live["packets"], 3)
        check("code words", live["code_words"], 3)
        check("product", live["product"], 96)
        check("specifier", live["specifier"], 1)
        check("ambiguous", live["ambiguous"], 0)
        check("frames", live["frames"], [(10, 1000), (11, 1100), (12, 1200)])
        check("mean pitch", live["mean_code_pitch_lines"], 100.0)
        # The mixed-type packets must walk to the end: 3 codes + 6 perfs.
        check("all records framed", live["events"], 9)
        check("perforations framed", live["perforations"], 6)
        check("no framing errors", live["parse_errors"], 0)
        check("status was reported", live["status_packets"], 3)
        check("film sensed at entry", live["film_at_entry"], True)
        check("film sensed at exit", live["film_at_exit"], True)
        check("hardware_cb", live["hardware_cb"], "0xC0000000")
        check("anchor accepted", live["anchor_35mm_head_first"]["accepted"], True)
        check("anchor agrees", live["anchor_35mm_head_first"]["agree"], 3)
        check("tail-first anchor rejected",
              live["anchor_35mm_tail_first"]["agree"], 1)
        check("gated", live["gated"], True)

        again = replay(log)
        for k in ("packets", "code_words", "product", "specifier", "frames",
                  "ambiguous", "rejected", "window_evidence"):
            check(f"replay {k}", again[k], live[k])
        text = log.read_text().splitlines()
        check("log has a header", json.loads(text[0])["kind"], "header")
        check("log has a summary", json.loads(text[-1])["kind"], "summary")
        raws = [json.loads(x) for x in text if json.loads(x)["kind"] == "dx"]
        check("raw responses logged", len(raws), 3)
        check("raw is the whole response",
              len(bytes.fromhex(raws[0]["raw"].replace(" ", ""))), 34)

    # A gate that never answers must fall back rather than poll forever.
    class DeadBoard:
        # Status 2 = "invalid packet", which is what docs/03 records this
        # light board answering for reads of registers above 1.
        def __call__(self, pkt):
            if pkt == pc.read_interrupt_status():
                return bytes([0x01, 0x03, pc.AD_LIGHT, 0x02, 0x00])
            return bytes([0x01, 0x20, pc.AD_LIGHT, 0x00]) + bytes(30)

    r2 = DxReader(DeadBoard(), interval=0.0)
    for _ in range(GATE_FAILURES_BEFORE_FALLBACK + 2):
        r2.poll()
    s2 = r2.summary()
    check("fell back to ungated", s2["gated"], False)
    check("still read DX after falling back", s2["dx_reads"] > 0, True)

    # A corrupted code word must be rejected, never voted on.
    b0, b1, b2 = dxd.encode_dx_full(96, 1, 10)
    bad = dxd.encode_record(dxd.EventType.DX_CODE_FULL, bytes([b0 ^ 0x04, b1, b2]))
    r3 = DxReader(lambda _p: None, interval=0.0)
    r3.ingest(dxd.encode_packet(0x64, [bad]))
    s3 = r3.summary()
    check("corrupt word yields no product", s3["product"], None)
    check("corrupt word counted", s3["code_words"], 0)
    check("corrupt word is a rejection, not an unreadable",
          s3["window_evidence"]["neither_valid"], 1)

    # A packet the walker could not finish must be recorded as such, and the
    # events before the break must still count. Type 9 does not exist.
    r4 = DxReader(lambda _p: None, interval=0.0)
    r4.ingest(dxd.encode_packet(
        7, [dxd.encode_record(8, bytes([0, 3])), bytes([0x09, 0, 0])]))
    s4 = r4.summary()
    check("framing error recorded", s4["parse_errors"], 1)
    check("events before the break kept", s4["events"], 1)
    check("and the reason is in the summary", "type 9" in s4["first_parse_error"], True)

    # An empty packet must not be read as "film sensors clear".
    r5 = DxReader(lambda _p: None, interval=0.0)
    r5.ingest(dxd.encode_packet(9, []))
    s5 = r5.summary()
    check("no status from an empty packet", s5["status_packets"], 0)
    check("no hardware_cb from an empty packet", s5["hardware_cb"], "0x00000000")

    # The window tally must refuse to claim a settled window on thin evidence.
    w = WindowEvidence(window0_only=4)
    check("4 validated words is not a verdict", w.verdict(), None)
    w.window0_only = 5
    check("5 is", w.verdict(), 0)
    w2 = WindowEvidence()
    w2.add(None)
    check("an unreadable record is counted as such", w2.unreadable, 1)
    check("and is not a validation", w2.verdict(), None)

    print("FAILED" if fails else "OK")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--board", type=lambda s: int(s, 0), default=pc.AD_LIGHT)
        p.add_argument("--half-lines", action="store_true",
                       help="DPI base 4: halve reported line numbers")

    p = sub.add_parser("probe", help="one gate read and one DX read; no writes")
    common(p)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_probe)

    p = sub.add_parser("poll", help="poll for DX events; no writes unless --start")
    common(p)
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S * 1000,
                   help="ms between polls (default %(default)s)")
    p.add_argument("--log", help="raw JSONL log to append to")
    p.add_argument("--ungated", action="store_true",
                   help="skip the 0x02 gate and read 0x90 every time")
    p.add_argument("--start", type=int, metavar="SPEED", default=None,
                   help="WRITE: start the DX reader first (register 0x91)")
    p.add_argument("--format", type=int, default=pc.DX_FORMAT_DEFAULT)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_poll)

    p = sub.add_parser("replay", help="decode a raw log; no scanner needed")
    p.add_argument("log")
    p.add_argument("--half-lines", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_replay)

    p = sub.add_parser("selftest", help="end to end against a synthetic board")
    p.set_defaults(fn=cmd_selftest)

    a = ap.parse_args()
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
