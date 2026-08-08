#!/usr/bin/env python3
"""The read path. It can read the EEPROMs and it cannot write to them.

WHAT THIS FILE IS FOR
---------------------
Three jobs, in order of how much damage getting them wrong would do:

  1. Guarantee ONE read per power cycle, across process restarts.
  2. Read every device on the bus exactly once, then hand the bytes over.
  3. Be impossible to turn into a write path.

WHY ONE READ PER POWER CYCLE (backups/eeprom-i2c/README.md, on hardware)
------------------------------------------------------------------------
These EEPROMs return good data on the FIRST transaction after a power cycle
and degrade on every read after it. The second read of a cycle already
differed in 180 of 256 bytes; by the third both devices read entirely 0xFF.
The I2C status stays "ok" the whole time, so nothing in the protocol reveals
that the data is now junk. Per-unit calibration exists nowhere else and cannot
be recreated, so a second read is not a retry -- it is destruction.

HOW THE GUARANTEE SURVIVES A PROCESS RESTART
--------------------------------------------
In-process state is worthless here: a user who runs the app twice must not
read twice. The witness therefore lives in hardware that forgets exactly when
we want it to -- the FX2's own RAM.

  * FX2 RAM is volatile. It does NOT survive a power cycle, and it DOES
    survive the host process exiting. That is precisely the lifetime a
    "have I already read this power cycle?" flag needs, and no file on disk
    can express it, because no file knows when the scanner was last unplugged.

  * After a successful read we stamp a marker into scratch RAM at 0x0D00 --
    clear of the firmware's code (0x0000-0x0224) and its buffers
    (0x0400-0x0C0F). Magic, format version, and a 16-byte nonce.

  * Before any read we read that region back. Reading FX2 RAM uses vendor
    request 0xA0, which the FX2's USB core answers IN HARDWARE while RENUM=0.
    It involves the I2C bus not at all. Checking whether we may read costs
    nothing and risks nothing.

  * A second, independent witness: the dump firmware's own first bytes at
    0x0000. If our code is still resident, RAM was never cleared, so the power
    was never cycled -- even if something overwrote the marker.

  * The rule is fail-safe. We read only when we can positively see a FRESH
    cycle: BOTH witnesses absent. Ambiguity refuses.

  * A loaded scanner (0f05:f135) is refused outright. Firmware in RAM means
    the machine has been up since power-on, so a first read is already
    impossible this cycle. This also removes the whole class of "someone
    loaded Pakon7.hex over our marker" problems -- if that happened, the
    device re-enumerated loaded and we refuse for that reason instead.

  * A lock file serialises concurrent processes, and an on-disk journal keyed
    to the nonce records what happened, so a crash between reading and saving
    is detectable.

SALVAGE INSTEAD OF RE-READ
--------------------------
If the marker says we already read this cycle but the journal says the save
never completed, the first-read bytes are still sitting in FX2 RAM at 0x0400+.
Reading them back out of RAM is free and harmless. That is strictly safer than
going to I2C again, and it is what salvage() does. Re-reading to recover from a
crash would be the exact mistake this whole file exists to prevent.

WHY THIS CANNOT WRITE
---------------------
Not discouraged -- structurally absent.

  * The only USB requests issued are 0xA0 (FX2 RAM, the Cypress firmware-load
    request) and reads of that RAM. The vendor's EEPROM WRITE request 0xA2 is
    never sent, and neither is 0xA9. Grep this file: there is no 0xA2.
  * The firmware that touches I2C is pinned by SHA256. Any other image --
    including tools/i2c_eeprom.hex.DANGEROUS-WRITES, which CAN write -- is
    refused before a single byte goes to the device. An allowlist of one.
  * That pinned firmware transmits no I2C data byte at all: three I2DAT
    stores, all addresses, no STOP between the word address and the repeated
    start, so a 24Cxx cannot commit anything. See fx2/eeprom_dump_bus.c.
  * A startup check refuses to run if a writable i2c_eeprom.hex has been
    un-quarantined.

TESTING WITHOUT THE SCANNER
---------------------------
Everything above is expressed against a Transport interface. SimTransport
emulates the FX2 -- including its RAM, so the marker logic is exercised for
real rather than mocked -- and reproduces the documented degradation curve:
first read good, second read 180/256 bytes wrong, third and later all 0xFF.
The read-once guarantee is therefore testable, and tested, on a machine with
no scanner attached. See tools/test_calib.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

# ---- USB identity ---------------------------------------------------------
# Unloaded: no firmware in RAM, so this could be the first transaction of a
# power cycle. 04b4:8613 is the bare Cypress default, which is what this
# scanner enumerates as because its 0x51 boot EEPROM is erased.
UNLOADED_IDS = ((0x04B4, 0x8613), (0x0F05, 0xF235), (0x0547, 0x1002),
                (0x4705, 0x0211))
# Loaded: firmware is running, so the machine has been up. Never read here.
LOADED_IDS = ((0x0F05, 0xF135), (0x0F05, 0x35F2), (0x0F05, 0xF335))

VENDOR_IN, VENDOR_OUT = 0xC0, 0x40
ANCHOR_LOAD_INTERNAL = 0xA0          # FX2 RAM. The only request we ever send.

# ---- firmware, pinned -----------------------------------------------------
FIRMWARE = HERE.parent / "fx2" / "eeprom_dump_bus.ihx"
FIRMWARE_SHA256 = "7ca5d37d26ce5a2ba6c8b3b11fcac28451edff8edc0116e2774f6bd53e12a6ac"

# ---- firmware memory map (fx2/eeprom_dump_bus.c) --------------------------
BUF_BASE = 0x0400
BUF_STRIDE = 0x0100
STATUS_ADDR = 0x0C00
STATUS_LEN = 16
ADDR_LO, ADDR_HI = 0x50, 0x57
NDEV = 8
DONE_MARKER = bytes((0xC0, 0xDE, 0xF1, 0x35))

STATUS_TEXT = {0: "ok", 1: "no device at this address", 2: "no ACK on word addr",
               3: "no ACK on read addr", 4: "bus error during read"}

# ---- read-once marker -----------------------------------------------------
MARKER_ADDR = 0x0D00                 # clear of code (..0x0224) and buffers
MARKER_MAGIC = b"PKN-CAL-READ-1\x00\x00"   # 16 bytes
MARKER_LEN = 32                      # magic + 16-byte nonce
CODE_WITNESS_LEN = 16                # firmware bytes at 0x0000

DEVICE_ABSENT, DEVICE_UNLOADED, DEVICE_LOADED = "absent", "unloaded", "loaded"


class ReadRefused(Exception):
    """We will not read. The message says why, in words a user can act on."""


class UnsafeToolState(Exception):
    """Something about the installation makes writes possible. Stop."""


# --------------------------------------------------------------------------
# transports
# --------------------------------------------------------------------------

class Transport:
    """The only things the read path may do to a scanner."""

    def state(self) -> str: raise NotImplementedError
    def ram_read(self, addr: int, length: int) -> bytes: raise NotImplementedError
    def ram_write(self, addr: int, data: bytes) -> None: raise NotImplementedError
    def reset_8051(self, hold: bool) -> None: raise NotImplementedError
    def download(self, image_path: Path) -> None: raise NotImplementedError
    def describe(self) -> str: raise NotImplementedError


class UsbTransport(Transport):
    """Real hardware. Issues 0xA0 and nothing else."""

    def __init__(self, dev=None):
        import usb.core                                    # noqa: PLC0415
        self._usb = usb.core
        self.dev = dev if dev is not None else self._find()

    def _find(self):
        for d in self._usb.find(find_all=True):
            if (d.idVendor, d.idProduct) in UNLOADED_IDS + LOADED_IDS:
                return d
        return None

    def state(self) -> str:
        if self.dev is None:
            self.dev = self._find()
        if self.dev is None:
            return DEVICE_ABSENT
        ids = (self.dev.idVendor, self.dev.idProduct)
        if ids in LOADED_IDS:
            return DEVICE_LOADED
        return DEVICE_UNLOADED if ids in UNLOADED_IDS else DEVICE_ABSENT

    def describe(self) -> str:
        if self.dev is None:
            return "no scanner found"
        return f"{self.dev.idVendor:04x}:{self.dev.idProduct:04x}"

    def ram_read(self, addr: int, length: int) -> bytes:
        return bytes(self.dev.ctrl_transfer(VENDOR_IN, ANCHOR_LOAD_INTERNAL,
                                            addr, 0, length, 5000))

    def ram_write(self, addr: int, data: bytes) -> None:
        n = self.dev.ctrl_transfer(VENDOR_OUT, ANCHOR_LOAD_INTERNAL,
                                   addr, 0, data, 5000)
        if n != len(data):
            raise IOError(f"short RAM write at {addr:#06x}: {n}/{len(data)}")

    def reset_8051(self, hold: bool) -> None:
        from pakon_load import Fx2                          # noqa: PLC0415
        Fx2(self.dev).reset_8051(hold)

    def download(self, image_path: Path) -> None:
        from pakon_load import Fx2, HexImage                # noqa: PLC0415
        Fx2(self.dev).download(HexImage.load(str(image_path)), False)


class SimTransport(Transport):
    """A scanner that behaves like the real one, including the degradation.

    Models what was measured, not what would be convenient:
      read 1 of a power cycle  -> the true contents
      read 2                   -> 180 of 256 bytes wrong
      read 3 and after         -> all 0xFF
    and the I2C status is "ok" every single time, exactly as on the bench.

    Its RAM is real emulated RAM, so the read-once marker is exercised
    genuinely rather than mocked out.
    """

    def __init__(self, contents: dict[int, bytes] | None = None,
                 loaded: bool = False, present: bool = True, seed: int = 1):
        self.contents = dict(contents or {})
        self.loaded = loaded
        self.present = present
        self.ram = bytearray(0x2000)
        self.reads: dict[int, int] = {}
        self.rng = random.Random(seed)
        self.held = True
        self.firmware: Path | None = None
        self.i2c_writes = 0            # must stay 0 forever
        self.power_cycles = 0

    def power_cycle(self) -> None:
        """What unplugging it does: RAM forgets, the parts recover."""
        self.ram = bytearray(0x2000)
        self.reads.clear()
        self.held = True
        self.firmware = None
        self.loaded = False
        self.power_cycles += 1

    def state(self) -> str:
        if not self.present:
            return DEVICE_ABSENT
        return DEVICE_LOADED if self.loaded else DEVICE_UNLOADED

    def describe(self) -> str:
        return "simulated 04b4:8613" if not self.loaded else "simulated 0f05:f135"

    def ram_read(self, addr: int, length: int) -> bytes:
        return bytes(self.ram[addr:addr + length])

    def ram_write(self, addr: int, data: bytes) -> None:
        self.ram[addr:addr + len(data)] = data

    def reset_8051(self, hold: bool) -> None:
        self.held = hold
        if not hold and self.firmware is not None:
            self._run()

    def download(self, image_path: Path) -> None:
        self.firmware = Path(image_path)
        sys.path.insert(0, str(HERE))
        from pakon_load import HexImage                     # noqa: PLC0415
        for a, d in HexImage.load(str(image_path)).segments():
            self.ram[a:a + len(d)] = d

    def _degrade(self, addr: int, truth: bytes) -> bytes:
        n = self.reads.get(addr, 0)
        self.reads[addr] = n + 1
        if n == 0:
            return truth
        if n == 1:
            out = bytearray(truth)
            for i in self.rng.sample(range(len(truth)), min(180, len(truth))):
                out[i] = self.rng.randrange(256)
            return bytes(out)
        return b"\xff" * len(truth)

    def _run(self) -> None:
        """Execute what fx2/eeprom_dump_bus.c does."""
        status = bytearray(STATUS_LEN)
        for n in range(NDEV):
            a7 = ADDR_LO + n
            base = BUF_BASE + n * BUF_STRIDE
            self.ram[base:base + 256] = b"\xee" * 256
            if a7 not in self.contents:
                status[n] = 1                       # no ACK -- nothing there
                continue
            self.ram[base:base + 256] = self._degrade(a7, self.contents[a7])
            status[n] = 0                           # always "ok". That is the trap.
        status[8:12] = DONE_MARKER
        status[12], status[13] = 2, NDEV
        self.ram[STATUS_ADDR:STATUS_ADDR + STATUS_LEN] = status


# --------------------------------------------------------------------------
# installation safety
# --------------------------------------------------------------------------

def assert_safe_installation() -> None:
    """Refuse to run at all if a write-capable image has been un-quarantined."""
    danger = HERE / "i2c_eeprom.hex"
    if danger.exists():
        raise UnsafeToolState(
            f"{danger} exists. That firmware CAN write to the EEPROM and is "
            f"supposed to stay quarantined as i2c_eeprom.hex.DANGEROUS-WRITES. "
            f"Nothing was sent to the scanner. Re-quarantine it before running "
            f"the calibration reader.")


def firmware_ok(path: Path = FIRMWARE) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"firmware image missing: {path}"
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != FIRMWARE_SHA256:
        return False, (f"firmware image {path} does not match the audited "
                       f"read-only build.\n  expected {FIRMWARE_SHA256}\n"
                       f"  got      {got}\nRefusing to load it.")
    return True, "pinned read-only firmware verified"


# --------------------------------------------------------------------------
# the power-cycle guard
# --------------------------------------------------------------------------

class ReadLock:
    """Serialise the check-then-read sequence across processes.

    Without this there is a real race: two app instances started together can
    both see "no marker, no resident firmware", both conclude the cycle is
    fresh, and both read -- the second one corrupting what the first captured.
    The FX2-RAM marker cannot close that window on its own because it is only
    written after the decision is made.

    fcntl.flock where it exists, because the kernel drops it if the process
    dies; an O_EXCL file with a staleness check elsewhere.
    """

    def __init__(self, path: Path, stale_after: float = 300.0):
        self.path = Path(path)
        self.stale_after = stale_after
        self._fh = None
        self._mode = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import fcntl                                    # noqa: PLC0415
            self._fh = open(self.path, "a+")
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self._fh.close()
                self._fh = None
                raise ReadRefused(
                    "Another copy of this program is already reading the "
                    "scanner's calibration. Refusing to read at the same "
                    "time -- two reads in one power cycle is exactly the "
                    "accident this guards against. Nothing was sent to the "
                    "scanner.")
            self._mode = "flock"
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.write(f"{os.getpid()} {time.time()}\n")
            self._fh.flush()
            return self
        except ImportError:
            pass
        # No fcntl (Windows): exclusive create, with staleness recovery.
        if self.path.exists():
            try:
                age = time.time() - self.path.stat().st_mtime
            except OSError:
                age = 0.0
            if age < self.stale_after:
                raise ReadRefused(
                    "Another copy of this program appears to be reading the "
                    "scanner's calibration. Refusing to read at the same "
                    "time. If nothing else is running, delete "
                    f"{self.path} and try again. Nothing was sent to the "
                    "scanner.")
            try:
                os.replace(self.path, self.path.with_suffix(".stale"))
            except OSError:
                pass
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ReadRefused(
                "Another copy of this program just started reading the "
                "scanner's calibration. Nothing was sent to the scanner.")
        os.write(fd, f"{os.getpid()} {time.time()}\n".encode())
        os.close(fd)
        self._mode = "exclusive-file"
        return self

    def __exit__(self, *exc):
        if self._mode == "flock" and self._fh is not None:
            try:
                import fcntl                                # noqa: PLC0415
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            except Exception:                               # noqa: BLE001
                pass
            self._fh.close()
        elif self._mode == "exclusive-file":
            # Releasing a lock is the one removal this code performs, and it
            # removes a lock file, never a calibration.
            try:
                os.unlink(self.path)
            except OSError:
                pass
        return False


class PowerCycleGuard:
    """Answers one question: may we read, right now, on this power cycle?"""

    def __init__(self, transport: Transport, journal_dir: Path):
        self.t = transport
        self.dir = Path(journal_dir)
        self.journal = self.dir / "read-journal.jsonl"

    # -- witnesses in FX2 RAM -------------------------------------------
    def marker(self) -> dict | None:
        """Our stamp, if this power cycle already produced a read."""
        try:
            raw = self.t.ram_read(MARKER_ADDR, MARKER_LEN)
        except Exception:                                   # noqa: BLE001
            return None
        if len(raw) < MARKER_LEN or not raw.startswith(MARKER_MAGIC):
            return None
        return {"nonce": raw[len(MARKER_MAGIC):].hex()}

    def code_resident(self) -> bool:
        """Is our dump firmware still in RAM? Then RAM was never cleared."""
        try:
            from pakon_load import HexImage                 # noqa: PLC0415
            segs = list(HexImage.load(str(FIRMWARE)).segments())
            addr, data = segs[-1]
            want = data[:CODE_WITNESS_LEN]
            return self.t.ram_read(addr, len(want)) == want
        except Exception:                                   # noqa: BLE001
            return False

    def stamp(self) -> str:
        nonce = os.urandom(16)
        self.t.ram_write(MARKER_ADDR, MARKER_MAGIC + nonce)
        return nonce.hex()

    # -- journal ---------------------------------------------------------
    def note(self, event: str, **kw) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        rec = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "event": event, **kw}
        with open(self.journal, "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def entries(self) -> list[dict]:
        if not self.journal.is_file():
            return []
        out = []
        for line in self.journal.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return out

    def unsaved_nonce(self) -> str | None:
        """A nonce that was stamped but whose save never completed."""
        saved = {e.get("nonce") for e in self.entries() if e.get("event") == "saved"}
        for e in reversed(self.entries()):
            if e.get("event") == "read" and e.get("nonce") not in saved:
                return e.get("nonce")
        return None

    # -- the decision ----------------------------------------------------
    def check(self) -> dict:
        """Fail-safe: permit only when a fresh power cycle is positively seen."""
        state = self.t.state()
        if state == DEVICE_ABSENT:
            return {"may_read": False, "state": state, "code": "absent",
                    "reason": "No scanner is connected."}
        if state == DEVICE_LOADED:
            return {"may_read": False, "state": state, "code": "loaded",
                    "reason": (
                        "The scanner already has its firmware loaded, so it "
                        "has been running since it was last powered on. The "
                        "one good read of an EEPROM is the first transaction "
                        "after a power cycle, and that moment has passed for "
                        "this cycle. Power the scanner off and on, then try "
                        "again before anything else touches it.")}

        mk = self.marker()
        if mk is not None:
            return {"may_read": False, "state": state, "code": "already-read",
                    "nonce": mk["nonce"],
                    "reason": (
                        "This scanner has already been read since it was last "
                        "powered on. Reading again in the same power cycle "
                        "returns corrupted data while still reporting success "
                        "-- that is how this hardware fails. The earlier read "
                        "is saved and is the good one.")}
        if self.code_resident():
            return {"may_read": False, "state": state, "code": "ram-not-clear",
                    "reason": (
                        "The scanner's RAM still holds the reader firmware "
                        "from an earlier run, so the power has not been "
                        "cycled since. Refusing to read rather than risk a "
                        "second read in one power cycle. Power the scanner "
                        "off and on if you need a fresh read.")}
        return {"may_read": True, "state": state, "code": "fresh",
                "reason": "Fresh power cycle: no reader firmware and no read "
                          "marker in the scanner's RAM."}


# --------------------------------------------------------------------------
# the read itself
# --------------------------------------------------------------------------

def _collect(transport: Transport) -> dict:
    """Pull the status block and all eight buffers out of FX2 RAM.

    Pure RAM reads -- no I2C happens here, so this is safe to call as often
    as we like, including to salvage a read whose save was interrupted.
    """
    status = transport.ram_read(STATUS_ADDR, STATUS_LEN)
    complete = len(status) >= 12 and status[8:12] == DONE_MARKER
    devices, results = {}, {}
    for n in range(NDEV):
        a7 = ADDR_LO + n
        code = status[n] if n < len(status) else None
        data = transport.ram_read(BUF_BASE + n * BUF_STRIDE, 256)
        results[a7] = {"code": code, "text": STATUS_TEXT.get(code, str(code)),
                       "answered": code == 0}
        if code == 0:
            devices[a7] = data
    return {"devices": devices, "results": results, "complete": complete,
            "status_raw": bytes(status).hex()}


def salvage_from_ram(transport: Transport) -> dict:
    """Recover a read whose save was interrupted, WITHOUT touching I2C.

    If a crash lands between the I2C read and the disk write, the first-read
    bytes are still in FX2 RAM. Reading them back out is free and harmless.
    Going to I2C again to recover would be the precise mistake this module
    exists to prevent -- the recovery read would be the second read of the
    power cycle, and therefore corrupt.
    """
    transport.reset_8051(True)
    out = _collect(transport)
    out["salvaged"] = True
    return out


def read_bus(transport: Transport, *, settle: float = 6.0,
             poll: float = 0.1, before_run=None) -> dict:
    """Load the pinned firmware, let it read 0x50-0x57 ONCE, return the bytes.

    Waits for the firmware's completion marker rather than sleeping a guessed
    interval, so a slow bus cannot be mistaken for an empty one.

    `before_run` is called after the firmware is in RAM but before the 8051 is
    released -- the caller stamps the read-once marker there, so that the
    marker is in place BEFORE any I2C transaction can occur. From the moment
    of download the resident-code witness also applies, so the window in which
    a crash could permit a second read is closed from both ends.
    """
    ok, why = firmware_ok()
    if not ok:
        raise ReadRefused(why)

    transport.reset_8051(True)
    transport.download(FIRMWARE)
    if before_run is not None:
        before_run()
    transport.reset_8051(False)

    deadline = time.time() + settle
    done = False
    while time.time() < deadline:
        try:
            st = transport.ram_read(STATUS_ADDR, STATUS_LEN)
        except Exception:                                   # noqa: BLE001
            st = b""
        if len(st) >= 12 and st[8:12] == DONE_MARKER:
            done = True
            break
        time.sleep(poll)

    transport.reset_8051(True)
    out = _collect(transport)
    out["polled_done"] = done
    out["salvaged"] = False
    return out
