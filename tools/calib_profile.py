#!/usr/bin/env python3
"""What a stored calibration MEANS -- the values the pipeline actually needs.

    python3 tools/calib_profile.py                 the profile in force
    python3 tools/calib_profile.py --json          the same, machine-readable
    python3 tools/calib_profile.py matrix          this unit's 3x10 coefficients
    python3 tools/calib_profile.py adopt           attach calibration/README.json
                                                   to the resolved scanner

calib_resolve.py answers "which scanner". This answers "and therefore what
numbers", which is a separate question with a much less comfortable answer.

WHAT IS ON THE PAGE WE HAVE, AND WHAT IS NOT
--------------------------------------------
The 256 bytes at I2C 0x52 that this project can read hold, verified by
arithmetic against the owner's own page (see calib_verify.py):

    0x0F        the scanner serial number
    0x25..0x9C  NegMatrix0..29, the colour-negative 3x10, float32 LE
    0x9D..0xFF  PosMatrix0..23, the reversal 3x10 -- TRUNCATED by the page
                boundary at 24 of 30 elements

That is the whole of it. Everything else the vendor stores per unit is on pages
of the same device that nothing here has ever read, because the addressing
beyond byte 255 is not yet worked out (docs/69). The Windows registry -- being
the vendor's own copy of the EEPROM -- names them: MotorAdjust,
MotorAdjustDrag(_Ir), MotorSpeedPlus(_Ir) and Offset per DPI base, StepperLens,
StepperCCD, and the per-mode lamp calibration Current_*, DutyCycle_* and
DutyCycleOpenGate_* for every DPI base x film mode.

So a profile has two halves with genuinely different standing:

    from_device   the matrices and the serial -- read off THIS scanner
    overlay       the exposure triad, lamp levels and on-counts, AFE gains and
                  offsets -- NOT read off this scanner, because they cannot be
                  yet. They come from a per-unit overlay in the store.

Keeping them separate is the point. The failure this avoids is the quiet one:
handing a second owner's scanner the first owner's lamp currents and calling
the result "calibrated". A borrowed exposure is a legitimate way to get a
picture out of a new machine, and it is not that machine's calibration, and the
difference must survive all the way to the screen.

THE FALLBACK CHAIN, AND WHY IT STOPS WHERE IT DOES
--------------------------------------------------
    1. <store>/units/<serial>/overlay/<newest>.json   this unit's own values
    2. calibration/README.json                        the repo reference
    3. nothing

Step 2 is the file the current unit already runs on, and it must keep working
-- but it describes ONE machine (serial 16275, its lamp values transcribed from
that unit's own vendor registry key, written 2022-11-10). Applied to a
different serial it is borrowed, not calibrated, and this module says so in
every direction it can: in the returned dict, in the CLI, and in the warnings
the app is expected to surface. It is still offered rather than withheld,
because refusing outright would leave a new owner unable to scan at all, and
the values are inside the hardware's own clamps -- the cost of borrowing is a
mis-exposed frame, not a damaged lamp.

NOTHING HERE TOUCHES A SCANNER
------------------------------
Same structural rule as calib_resolve.py and calib_verify.py: no ``usb``
import, no ``calib_device`` import, no transport argument. Everything is a
function of bytes already on disk. tools/test_calib.py asserts it by reading
this file's source.
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

import calib_resolve as cr      # noqa: E402
import calib_store as cs        # noqa: E402
import calib_verify as cv       # noqa: E402

REPO = HERE.parent
REPO_REFERENCE = REPO / "calibration" / "README.json"

#: Which unit calibration/README.json describes. The file itself does not carry
#: a machine-readable serial -- its provenance is in prose -- so this is the
#: attribution, taken from the same constant calib_verify uses to recognise the
#: owner's unit. If a future edit adds a top-level "unit_serial" to that file,
#: it wins; see _reference_serial().
REFERENCE_SERIAL = cv.OWNER_SERIAL

MATRIX_ELEMENTS = 30

# Where each half of a profile came from.
FROM_DEVICE = "device"                  # bytes read off this scanner's EEPROM
FROM_UNIT_OVERLAY = "unit-overlay"      # attached to this serial deliberately
FROM_REFERENCE = "repo-reference"       # calibration/README.json, same unit
FROM_BORROWED = "borrowed"              # calibration/README.json, OTHER unit
FROM_NOTHING = "missing"


def f32(v: float) -> float:
    """Round to float32, as the vendor stores and multiplies these.

    Identical to pakon_color.f32; spelled out here so this module keeps its
    "imports nothing that can open a device" property.
    """
    return struct.unpack("<f", struct.pack("<f", float(v)))[0]


# --------------------------------------------------------------------------
# the profile
# --------------------------------------------------------------------------

@dataclass
class UnitProfile:
    serial: int | None = None
    stamp: str | None = None
    dir: str | None = None

    #: 30 coefficients each, float32-rounded. pos_matrix is zero-filled past
    #: element 23 -- see pos_truncated_from.
    neg_matrix: list = field(default_factory=list)
    pos_matrix: list = field(default_factory=list)
    pos_truncated_from: int | None = None
    pedestals: list = field(default_factory=list)
    matrix_source: str = FROM_NOTHING

    #: The README.json-shaped `config` block: the exposure triad, lamp levels
    #: and on-counts, AFE gains/offsets, geometry. ScanConfig.from_calibration
    #: consumes exactly this shape.
    config: dict = field(default_factory=dict)
    config_source: str = FROM_NOTHING
    config_origin: str = ""

    warnings: list = field(default_factory=list)
    state: str = cr.NO_CALIBRATION

    @property
    def is_this_units_own_colour(self) -> bool:
        return self.matrix_source == FROM_DEVICE

    @property
    def is_this_units_own_exposure(self) -> bool:
        return self.config_source in (FROM_UNIT_OVERLAY, FROM_REFERENCE)

    def matrix(self, film_class: int = 1) -> list:
        """The 30 coefficients fcn.1000d880 multiplies by.

        film_class 2 is the reversal path (PosMatrix), anything else negative
        (NegMatrix) -- the same convention pakon_color.load_unit_matrix uses.
        """
        return list(self.pos_matrix if film_class == 2 else self.neg_matrix)

    def to_json(self) -> dict:
        return {
            "serial": self.serial,
            "stamp": self.stamp,
            "dir": self.dir,
            "state": self.state,
            "matrix": {
                "source": self.matrix_source,
                "neg": self.neg_matrix,
                "pos": self.pos_matrix,
                "pos_truncated_from": self.pos_truncated_from,
                "pedestals": self.pedestals,
                "this_units_own": self.is_this_units_own_colour,
            },
            "config": {
                "source": self.config_source,
                "origin": self.config_origin,
                "this_units_own": self.is_this_units_own_exposure,
                "values": self.config,
            },
            "warnings": self.warnings,
            "device_read_performed": False,
        }


# --------------------------------------------------------------------------
# decoding the page
# --------------------------------------------------------------------------

def matrices_from_page(page: bytes) -> dict:
    """Both 3x10 matrices out of one calibration page. Pure function of bytes.

    PosMatrix needs 120 bytes from 0x9D and the page ends at 256, so elements
    24..29 are not present. They are zero-filled, and the count of what was
    really read is reported rather than hidden: element 22 -- the last diagonal
    entry -- IS present and reads 0.25, and elements 12..23 all read exactly
    0.0, so zero is overwhelmingly likely for the remainder. It is still an
    assumption. calib_verify.cross_page_checks() is the test that would settle
    it, and it needs a device at 0x53 that this unit does not have.
    """
    out = {"neg": [], "pos": [], "pos_read": 0, "pedestals": []}
    for key, base in (("neg", cv.NEG_MATRIX_OFF), ("pos", cv.POS_MATRIX_OFF)):
        avail = max(0, (len(page) - base) // 4)
        n = min(MATRIX_ELEMENTS, avail)
        vals = [f32(v) for v in struct.unpack_from(f"<{n}f", page, base)] if n else []
        out[f"{key}_read"] = n
        out[key] = vals + [0.0] * (MATRIX_ELEMENTS - n)
    out["pedestals"] = [out["neg"][r * 10 + 9] for r in range(cv.ROWS)]
    return out


def _reference_serial(meta: dict) -> int | None:
    """Which unit calibration/README.json is about.

    Honours an explicit ``unit_serial`` if the file ever grows one; otherwise
    falls back to the project's recorded owner serial. Never guesses from the
    prose -- a regex over an English sentence is not attribution.
    """
    v = meta.get("unit_serial")
    if isinstance(v, int):
        return v
    v = (meta.get("config") or {}).get("unit_serial")
    if isinstance(v, int):
        return v
    return REFERENCE_SERIAL


def load_reference(path: Path = REPO_REFERENCE) -> tuple[dict, int | None, str]:
    """The repo's committed reference configuration. Read-only, always."""
    if not path.is_file():
        return {}, None, f"{path} is not present"
    try:
        meta = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return {}, None, f"{path} could not be read ({e})"
    return (meta.get("config") or {}), _reference_serial(meta), str(path)


# --------------------------------------------------------------------------
# building a profile
# --------------------------------------------------------------------------

def profile(store: cs.CalibrationStore | Path | str | None = None,
            serial_hint: int | None = None,
            reference: Path = REPO_REFERENCE) -> UnitProfile:
    """The calibration in force, decoded, with every source labelled.

    Causes no device traffic on any branch: it resolves against the store, then
    reads files. See the module docstring.
    """
    st = store if isinstance(store, cs.CalibrationStore) else cs.CalibrationStore(store)
    rep = cr.resolve(st, serial_hint=serial_hint)
    p = UnitProfile(state=rep["state"], serial=rep["serial"],
                    stamp=rep["stamp"], dir=rep["dir"],
                    warnings=list(rep["warnings"]))

    # --- the colour half: only ever from this scanner's own page ------------
    if rep["state"] == cr.READY:
        rec = st.get(rep["stamp"])
        cal = rec.calibration_device if rec else None
        if rec is not None and cal:
            page = rec.data(cal["addr7"])
            m = matrices_from_page(page)
            p.neg_matrix, p.pos_matrix = m["neg"], m["pos"]
            p.pedestals = m["pedestals"]
            p.matrix_source = FROM_DEVICE
            if m["pos_read"] < MATRIX_ELEMENTS:
                p.pos_truncated_from = m["pos_read"]
                p.warnings.append(
                    f"The reversal matrix is truncated by the 256-byte page "
                    f"boundary: elements {m['pos_read']}..29 of PosMatrix are "
                    f"not on the page that was read and are zero-filled. Every "
                    f"element from 12 to 23 reads exactly 0.0 and the last "
                    f"diagonal entry (element 22) is present and correct, so "
                    f"zero is very likely -- but it is an assumption, and it "
                    f"only affects reversal film. Colour negative is complete.")
    else:
        p.warnings.append(
            "No scanner's own colour matrix is in force. Until one is, the "
            "colour pipeline falls back on the values committed in this "
            "repository, which were measured on serial "
            f"{REFERENCE_SERIAL}'s optics.")

    # --- the exposure half: overlay, then reference, then nothing -----------
    cfg, cfg_src, origin = _config_for(st, p.serial, reference)
    p.config, p.config_source, p.config_origin = cfg, cfg_src, origin
    if cfg_src == FROM_BORROWED:
        p.warnings.append(
            f"Exposure is BORROWED, not calibrated. The lamp currents, duty "
            f"cycles, AFE gains and offsets in force were measured on scanner "
            f"{REFERENCE_SERIAL} and this is scanner {p.serial}. They are "
            f"inside the hardware's own clamps, so nothing is at risk, but the "
            f"exposure will not be right for this machine and no amount of "
            f"post-processing makes it right. This scanner's real values are "
            f"on EEPROM pages that nothing has read yet (docs/69); its own "
            f"Windows registry export, if it has ever run the vendor software, "
            f"is the other way to get them. Attach them with: "
            f"calib_profile.py adopt --from <file>")
    elif cfg_src == FROM_NOTHING:
        p.warnings.append(
            "No exposure configuration is available at all -- neither an "
            "overlay for this scanner nor the repository reference. A scan "
            "would be exposed at values nothing on this machine can decode, "
            "which is why pakon_scan refuses rather than defaults.")
    return p


def _config_for(st: cs.CalibrationStore, serial: int | None,
                reference: Path) -> tuple[dict, str, str]:
    if serial is not None:
        ov = st.overlay(serial)
        if ov and ov.get("config"):
            return (dict(ov["config"]), FROM_UNIT_OVERLAY,
                    f"{st.unit_dir(serial) / 'overlay'} "
                    f"({ov.get('source') or 'overlay'})")
    cfg, ref_serial, origin = load_reference(reference)
    if not cfg:
        return {}, FROM_NOTHING, origin
    if serial is None or ref_serial is None or serial == ref_serial:
        return dict(cfg), FROM_REFERENCE, origin
    return dict(cfg), FROM_BORROWED, origin


def adopt_reference(store: cs.CalibrationStore, serial: int,
                    reference: Path = REPO_REFERENCE) -> Path:
    """Attach the repo's reference configuration to a serial, deliberately.

    This is how the current unit stops depending on a hand-edited file in the
    checkout: its own numbers get copied into the store under its own serial,
    with the provenance recorded, and from then on the lookup is per-serial for
    the exposure half exactly as it already is for the colour half.

    It copies OUT of calibration/README.json and never writes to it.
    """
    cfg, ref_serial, origin = load_reference(reference)
    if not cfg:
        raise FileNotFoundError(origin)
    note = ("copied verbatim from the repository reference configuration"
            if ref_serial is None or ref_serial == serial else
            f"copied from the repository reference configuration, which "
            f"describes serial {ref_serial} and NOT serial {serial}. These "
            f"values are borrowed and were attached on purpose.")
    return st_save(store, serial, cfg, origin, note)


def st_save(store: cs.CalibrationStore, serial: int, cfg: dict, origin: str,
            note: str) -> Path:
    return store.save_overlay(serial, cfg, source=origin, provenance=note)


def adopt_file(store: cs.CalibrationStore, serial: int, path: Path) -> Path:
    """Attach a config block from an arbitrary JSON file to a serial.

    Accepts either a bare config object or a README.json-shaped file with a
    top-level ``config``, so a second owner can point this at their own
    exported values without reshaping them first.
    """
    meta = json.loads(Path(path).read_text())
    cfg = meta.get("config") if isinstance(meta.get("config"), dict) else meta
    if not isinstance(cfg, dict) or not cfg:
        raise ValueError(f"{path} holds no configuration object")
    return st_save(store, serial, dict(cfg), str(path),
                   "supplied by the user for this scanner")


# --------------------------------------------------------------------------

def _fmt(p: UnitProfile) -> str:
    L = [f"scanner  {p.serial if p.serial is not None else '(unidentified)'}"
         f"    state {p.state}",
         f"read     {p.stamp or '(none)'}"]
    L += ["",
          f"colour   {p.matrix_source}"
          + ("   -- this scanner's own" if p.is_this_units_own_colour
             else "   -- NOT this scanner's own")]
    if p.neg_matrix:
        d = [p.neg_matrix[0], p.neg_matrix[11], p.neg_matrix[22]]
        L.append("         negative diagonal  "
                 + "  ".join(f"{v:.6f}" for v in d))
        L.append("         pedestals          "
                 + "  ".join(f"{v:.3f}" for v in p.pedestals))
    if p.pos_truncated_from is not None:
        L.append(f"         reversal matrix read to element "
                 f"{p.pos_truncated_from}/30; the rest zero-filled")
    L += ["", f"exposure {p.config_source}"
              + ("   -- this scanner's own" if p.is_this_units_own_exposure
                 else "   -- NOT this scanner's own"),
          f"         {p.config_origin}"]
    c = p.config
    if c:
        L.append(f"         base {c.get('dpi_base')}  integration "
                 f"{c.get('integration_0x82_idx6')}  N {c.get('lamp_pwm_N')}")
        L.append(f"         levels {c.get('levels_R_G_B_Ir')}  on-counts "
                 f"{c.get('on_counts_R_G_B')}")
        L.append(f"         AFE gains {c.get('afe_gains')}  offsets "
                 f"{c.get('afe_offsets')}")
    for w in p.warnings:
        L += ["", f"  ** {w}"]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="The calibration in force, decoded. Never opens USB.")
    ap.add_argument("--store", type=Path, default=None)
    ap.add_argument("--serial", type=int, default=None,
                    help="resolve this scanner rather than deciding")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("show")
    m = sub.add_parser("matrix")
    m.add_argument("--film-class", type=int, default=1)
    ad = sub.add_parser("adopt", help="attach an exposure configuration to a "
                                      "scanner in the store")
    ad.add_argument("--from", dest="src", type=Path, default=None,
                    help="a JSON file of your own; default is the repository "
                         "reference calibration/README.json")
    a = ap.parse_args()

    st = cs.CalibrationStore(a.store)
    cmd = a.cmd or "show"

    if cmd == "adopt":
        rep = cr.resolve(st, serial_hint=a.serial)
        if rep["serial"] is None:
            print(f"nothing to attach a configuration to: {rep['headline']}",
                  file=sys.stderr)
            return 1
        p = (adopt_file(st, rep["serial"], a.src) if a.src
             else adopt_reference(st, rep["serial"]))
        print(f"attached to scanner {rep['serial']}:\n  {p}")
        return 0

    p = profile(st, serial_hint=a.serial)
    if cmd == "matrix":
        vals = p.matrix(a.film_class)
        if a.json:
            print(json.dumps(vals))
        else:
            for r in range(3):
                print("  " + "  ".join(f"{v: .9g}" for v in vals[r * 10:r * 10 + 10]))
        return 0
    print(json.dumps(p.to_json(), indent=2, sort_keys=True) if a.json
          else "\n" + _fmt(p) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
