#!/usr/bin/env python3
"""The colour engine boundary: Python's frame data into Go, sRGB back.

This is phase 2 of docs/62. The app renders through Go now. Everything from
the stage-2 polynomial onward — the F-135 inversion, SBA/balance, Shasta,
FUGC, the ICC hop — lives in ``tools/ansel/pipeline`` and is reached from here
through a c-shared dylib loaded by ctypes.

WHAT CROSSES, AND WHAT DOES NOT
-------------------------------
Python keeps capture, sync/unpack, per-pixel dark x gain, CCD deskew, framing
and frame slicing, transport geometry, and every piece of metadata handling —
the sidecar, the transport scale, the pitch measurement, DX resolution, and
the refusals at the front door. Go keeps the colour chain.

What crosses is the calibrated **14-bit frame slice on the capture's own
grid**, before ``unsquash_transport`` and before ``rot90``, as a contiguous
``(h, w, 3)`` uint16 buffer, and an ``(h, w, 3)`` uint8 buffer comes back. One
image per frame, no intermediates, nothing written to disk in either
direction: the dylib is structurally unable to write a file and structurally
unable to resample (there is no scale on the call and the output is the same
h x w as the input).

WHY A DYLIB
-----------
docs/62 §3.2 measured the three options on this machine. A ctypes call into Go
costs **2.8 us**; a process spawn costs **6.6 ms** and a framed round-trip over
pipes a further **16 ms at display size and 54 ms at full**, per render, every
render. Re-rendering to move a slider has to stay interactive, so the transport
had to cost nothing. The repo already loads two shared libraries exactly this
way (``pakon_color._LIB_C``, ``pakon_sba_apply._LIB_ANSEL``), so this is the
existing architecture rather than a new one.

The cost, stated plainly and not mitigated away: Go now shares a crash domain
with the backend. ``cabi.go`` recovers panics at every exported entry point and
returns them as errors, but that is a review discipline, not a compiler
guarantee. If it ever proves insufficient the same JSON request/response moves
onto a pipe without changing this module's interface.

ERRORS ARE DATA
---------------
Go refuses rather than guesses — no film base, no film class, no stock — and
those refusals have to reach the operator as readable text. Nothing here parses
stderr and nothing infers meaning from an exit status: every call returns a
code and a JSON object, and this module raises it as ``GoColourError`` with
``.kind`` and ``.message``. ``tools/pakon_app.py`` turns that into the JSON
body ``app/src/api.js:frameError`` already knows how to display.

NO SILENT FALLBACK
------------------
``pakon_color.py`` degrades to numpy without a word when its dylib is missing,
and ``docs/62`` §10 risk 5 names that as the same failure shape as the missing
inversion: you cannot tell from the output which engine produced it. This
module raises instead. If the dylib is absent, stale, or does not match
``tools/native-manifest.json``, you get an exception naming the file and the
build command — never a quietly different image.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass, field, asdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: Bumped in lockstep with ``AbiVersion`` in tools/ansel/pipeline/cabi.go.
#: A mismatch is refused on the Go side, by number, rather than discovered as
#: a wrong-looking image.
ABI_VERSION = 1

#: Name of the built library. Kept distinct from ``libpakon_color.dylib``
#: (the C stage-2 kernel) and ``libpakon_ansel.dylib`` (the C balance apply):
#: three different libraries with three different jobs, and the packaging
#: manifest lists all of them.
LIB_BASENAME = "libpakon_colour_go"

MANIFEST = os.path.join(HERE, "native-manifest.json")

BUILD_HINT = ("Build it with tools/build-native.sh — that is the only "
              "sanctioned way to produce it, and it is what writes "
              "tools/native-manifest.json.")


class GoColourError(RuntimeError):
    """A refusal or failure from the Go colour engine, as structured data.

    ``kind`` is one of request | refused | load | buffer | internal.
    ``message`` is the operator-readable prose; it is what reaches the UI.
    """

    def __init__(self, code: int, kind: str, message: str, stack: str = ""):
        super().__init__(message)
        self.code = int(code)
        self.kind = str(kind)
        self.message = str(message)
        self.stack = str(stack)

    def as_dict(self) -> dict:
        d = {"error": self.message, "engine": "go", "kind": self.kind,
             "code": self.code}
        if self.stack:
            d["trace"] = self.stack[-1500:]
        return d


class NativeMissing(GoColourError):
    """The dylib is absent, stale, or not the one the manifest describes."""

    def __init__(self, message: str):
        super().__init__(-3, "load", message)


# --------------------------------------------------------------------------
# the request
# --------------------------------------------------------------------------

def _default_ansel_root() -> str:
    fx35 = os.environ.get("PAKON_FX35_ROOT") or os.path.join(REPO, "vendor", "ansel")
    return os.path.join(fx35, "anselinstalldir", "dataPathItems")


def _default_fx35_root() -> str:
    return os.environ.get("PAKON_FX35_ROOT") or os.path.join(REPO, "vendor", "ansel")


@dataclass
class ColourRequest:
    """One frame's worth of everything that is not pixels. docs/62 §4.3.

    Every field is a value, is explicitly unknown, or the render is refused —
    there is no fourth state and no silent default. ``dxPart1``/``dxPart2`` of
    ``-1`` and ``iso`` of ``0`` mean "explicitly unknown", and they are legal
    only because ``sba.map`` and ``fugc-rgb-lutMap.map`` genuinely carry ``X``
    cells for them. ``filmPath`` has no wildcard, so an empty one is refused by
    name on the Go side rather than defaulted here.

    The field names are matched case-insensitively against ``RenderRequest`` in
    tools/ansel/pipeline/request.go. ``tools/ansel/pipeline/cabi_test.go``
    asserts that the exact JSON this dataclass emits still populates every
    field, so a rename on either side fails a test instead of silently
    dropping a value.
    """

    model: str = "f135"

    # film selection
    dxPart1: int = -1
    dxPart2: int = -1
    iso: int = 0
    filmPath: str = ""
    anselPath: str = "CN-Premium"
    sourceType: int = 1
    sbaKeyOverride: str = ""

    # stage-2 coefficients. docs/62 §2.11: there is no "auto". Empty is not a
    # default, it is the thing Go refuses by name.
    coeffSource: str = ""
    coeffPath: str = ""

    # The ROLL's film base, in linear 12-bit codes: FindDmin over the whole
    # strip, taken once at open. Not this frame's — measuring it per frame
    # makes the same negative render differently depending on which frames
    # were exported (docs/62 §2.6). 0 is FindDmin's sentinel and is refused.
    filmBase: tuple = (0, 0, 0)
    filmBaseFromFrame: bool = False

    # The choices docs/62 refuses to leave implicit. They have no defaults
    # here on purpose: an empty string reaches ``RenderRequest.Validate`` and
    # comes back as a refusal naming the flag and the reason, which is the
    # only way a caller that has not thought about them finds out. Every
    # caller in this repo states them at the call site, next to why.
    stageOrder: str = ""
    iccInput: str = ""
    fugcMode: int = 1

    # Python has already deskewed (Roll.attach carries it in the cache) and
    # already carries the lens 180°, so both are off here. They are passed
    # rather than assumed so that a change on the Python side has to be
    # reflected here to take effect.
    ccdDeskew: tuple = (0, 0, 0)
    rotate180: bool = False

    #: The operator's correction, in RPD-12 codes, applied to the toned image
    #: immediately before the ICC hop — the same seam as
    #: ``pakon_render.apply_correction``. The parameter model stays in Python;
    #: only the three resolved numbers cross.
    userOffsets: tuple = (0.0, 0.0, 0.0)

    provenance: dict = field(default_factory=dict)

    def wire(self) -> bytes:
        return json.dumps({
            "abi": ABI_VERSION,
            "fx35Root": _default_fx35_root(),
            "anselRoot": _default_ansel_root(),
            "request": asdict(self),
        }).encode("utf-8")


# --------------------------------------------------------------------------
# loading the library, and refusing to load the wrong one
# --------------------------------------------------------------------------

def _lib_candidates() -> list[str]:
    ext = {"Darwin": ".dylib", "Windows": ".dll"}.get(platform.system(), ".so")
    return [os.path.join(HERE, LIB_BASENAME + ext)]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_against_manifest(path: str) -> dict:
    """Refuse a library the manifest does not vouch for.

    docs/62 §5.2: the contents of a package are currently a function of
    whatever untracked binaries happen to be on the builder's disk — two
    same-sized, different-content Go binaries with identical ``vcs.modified``
    buildinfo, both older than their own sources. A build that can ship a
    stale colour engine is worse than one that fails, so this fails.
    """
    if os.environ.get("PAKON_NATIVE_UNVERIFIED") == "1":
        # The one escape hatch, for someone iterating on the Go side with an
        # unstamped build. It is loud, it is not the default, and it is not
        # what the app ever runs.
        sys.stderr.write(
            "pakon_colour_go: PAKON_NATIVE_UNVERIFIED=1 — loading %s without "
            "checking tools/native-manifest.json. The image this produces is "
            "not attributable to any source revision.\n" % path)
        return {}
    if not os.path.exists(MANIFEST):
        raise NativeMissing(
            "%s exists but %s does not, so there is no way to say what source "
            "built it. %s" % (path, MANIFEST, BUILD_HINT))
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        man = json.load(fh)
    entry = (man.get("artifacts") or {}).get(os.path.basename(path))
    if not entry:
        raise NativeMissing(
            "%s is not listed in %s. %s" % (path, MANIFEST, BUILD_HINT))
    got = _sha256(path)
    if got != entry.get("sha256"):
        raise NativeMissing(
            "%s does not match %s: manifest says sha256 %s, the file on disk "
            "is %s. Something rebuilt or replaced the library without "
            "restamping. %s"
            % (path, MANIFEST, str(entry.get("sha256"))[:16],
               got[:16], BUILD_HINT))
    return man


_LIB = None
_LIB_PATH = ""
_MANIFEST_DATA: dict = {}


def load() -> ctypes.CDLL:
    """Load and validate the dylib. Raises rather than falling back."""
    global _LIB, _LIB_PATH, _MANIFEST_DATA
    if _LIB is not None:
        return _LIB

    tried = _lib_candidates()
    path = next((p for p in tried if os.path.exists(p)), None)
    if path is None:
        raise NativeMissing(
            "the Go colour engine is not built: none of %s exists. %s "
            "There is no numpy fallback on this path by design — a silent "
            "fallback is how you ship the wrong engine without noticing "
            "(docs/62 §10 risk 5). To run the deprecated Python colour chain "
            "instead, set PAKON_COLOUR_ENGINE=python, which says so in the "
            "log." % (", ".join(tried), BUILD_HINT))

    _MANIFEST_DATA = _verify_against_manifest(path)
    lib = ctypes.CDLL(path)

    lib.PakonColorAbiVersion.argtypes = []
    lib.PakonColorAbiVersion.restype = ctypes.c_int32
    lib.PakonColorOpen.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32]
    lib.PakonColorOpen.restype = ctypes.c_int32
    lib.PakonColorRender.argtypes = [
        ctypes.c_char_p,                    # request JSON
        ctypes.POINTER(ctypes.c_uint16),    # in  (h, w, 3) u16
        ctypes.c_int32, ctypes.c_int32,     # h, w
        ctypes.POINTER(ctypes.c_uint8),     # out (h, w, 3) u8
        ctypes.c_char_p, ctypes.c_int32,    # msg buffer
    ]
    lib.PakonColorRender.restype = ctypes.c_int32
    lib.PakonColorClose.argtypes = []
    lib.PakonColorClose.restype = None

    got = int(lib.PakonColorAbiVersion())
    if got != ABI_VERSION:
        raise NativeMissing(
            "%s speaks ABI %d, this module speaks %d. The dylib and "
            "tools/pakon_colour_go.py are out of step. %s"
            % (path, got, ABI_VERSION, BUILD_HINT))

    _LIB, _LIB_PATH = lib, path
    return lib


def library_path() -> str:
    load()
    return _LIB_PATH


def build_provenance() -> dict:
    """What the manifest says produced the loaded library."""
    load()
    art = (_MANIFEST_DATA.get("artifacts") or {}).get(os.path.basename(_LIB_PATH), {})
    return {
        "path": _LIB_PATH,
        "gitRev": _MANIFEST_DATA.get("gitRev", "?"),
        "gitDirty": _MANIFEST_DATA.get("gitDirty"),
        "builtAt": _MANIFEST_DATA.get("builtAt", "?"),
        "goVersion": _MANIFEST_DATA.get("goVersion", "?"),
        "sha256": art.get("sha256", "?"),
        "arch": art.get("arch", "?"),
    }


# --------------------------------------------------------------------------
# the calls
# --------------------------------------------------------------------------

_MSG_LEN = 8192


def _decode(rc: int, buf) -> dict:
    raw = buf.value.decode("utf-8", "replace") if buf.value else ""
    try:
        obj = json.loads(raw) if raw else {}
    except ValueError:
        obj = {"code": rc, "kind": "internal",
               "message": raw or "the engine returned no explanation"}
    if rc != 0:
        raise GoColourError(obj.get("code", rc), obj.get("kind", "internal"),
                            obj.get("message") or "the engine failed without "
                            "saying why", obj.get("stack", ""))
    return obj


def open_selection(req: ColourRequest) -> dict:
    """Warm the tables and return what the vendor's selections resolved to.

    Returns the ``resolved`` map — sba key, shasta key, which ``lutMap`` and
    which FUGC LUT, the contrast class, the coefficient source and the paths
    every one of them came from — so the app can show the operator which
    stock's tables their frame went through instead of asking them to trust it.
    """
    lib = load()
    buf = ctypes.create_string_buffer(_MSG_LEN)
    rc = lib.PakonColorOpen(req.wire(), buf, _MSG_LEN)
    return _decode(rc, buf).get("resolved", {})


def render(rgb14: np.ndarray, req: ColourRequest,
           log: list | None = None) -> np.ndarray:
    """Calibrated 14-bit ``(h, w, 3)`` frame -> sRGB ``(h, w, 3)`` uint8.

    ``rgb14`` is the capture's own grid: not unsquashed, not rotated, not
    resampled. It is passed by pointer and read in place — nothing is copied
    on the way in and nothing is written to disk in either direction.
    """
    lib = load()
    arr = np.ascontiguousarray(rgb14, dtype=np.uint16)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise GoColourError(-4, "buffer",
                            "render expects (h, w, 3), got %r" % (arr.shape,))
    h, w = int(arr.shape[0]), int(arr.shape[1])
    out = np.empty((h, w, 3), dtype=np.uint8)
    buf = ctypes.create_string_buffer(_MSG_LEN)

    rc = lib.PakonColorRender(
        req.wire(),
        arr.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),
        ctypes.c_int32(h), ctypes.c_int32(w),
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
        buf, _MSG_LEN,
    )
    obj = _decode(rc, buf)
    if log is not None and obj.get("log"):
        log.append(obj["log"])
    return out


def close() -> None:
    """Drop the warm tables. The library stays loaded."""
    if _LIB is not None:
        _LIB.PakonColorClose()


if __name__ == "__main__":  # a smoke check, not a parity check
    r = ColourRequest(dxPart1=96, dxPart2=1, iso=400, filmPath="ColNeg",
                      coeffSource="eeprom", coeffPath=os.path.join(REPO, "backups", "eeprom-i2c",
                                             "eeprom_52.bin"),
                      filmBase=(3000, 3000, 3000))
    print("library :", library_path())
    print("build   :", json.dumps(build_provenance(), indent=2))
    print("resolved:", json.dumps(open_selection(r), indent=2))
