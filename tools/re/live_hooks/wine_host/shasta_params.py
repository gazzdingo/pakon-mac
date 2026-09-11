#!/usr/bin/env python3
"""Build a binary ShastaParams struct from a vendor .dpi file.

The layout was recovered from the vendor's own loader, fcn.1014a200, which
reads each key out of the .dpi dictionary and stores it at a fixed offset:

    push str.params.codeValuesPerButton
    ...
    lea ecx, [edi + 0x48]        <- the field

and independently confirmed by fcn.1008e970 (ShastaParams::operator=), which
copies exactly this set of offsets: ints at 0x38..0x5c, doubles from 0x60 on an
8-byte stride.

This exists so the REAL vendor tone code can be called on REAL parameters under
Wine, instead of hand-porting 771 bytes of x87 stack juggling and hoping. See
docs/74 §127.

NOT verified: the fields below 0x38 (0x1c is a std::string `key`, per the
operator= calling basic_string::operator= on it) and `pfdParams`, a nested
sub-struct the .dpi text does not expose. Those are left zeroed and any result
that depends on them is therefore suspect -- which is exactly why the host
prints what it read back rather than assuming the call succeeded.
"""
import struct
import sys

# offset -> (name, kind)  kind: 'i' int32, 'd' double
LAYOUT = [
    (0x38, "metricGray", "i"), (0x3c, "black", "i"), (0x40, "white", "i"),
    (0x48, "codeValuesPerButton", "d"),
    (0x50, "minValue", "i"), (0x54, "maxValue", "i"),
    (0x58, "analysisImageDim", "i"),
    (0x60, "rowPortion", "d"), (0x68, "colPortion", "d"),
    (0x70, "extShadowPercent", "d"), (0x78, "shadowPercent", "d"),
    (0x80, "highlightPercent", "d"), (0x88, "extHighlightPercent", "d"),
    (0x90, "highlightDiffMult", "d"), (0x98, "highlightDiffLimit", "d"),
    (0xa0, "blackButtons", "d"), (0xa8, "extShadowButtons", "d"),
    (0xb0, "shadowButtons", "d"), (0xb8, "highlightButtons", "d"),
    (0xc0, "extHighlightButtons", "d"),
    (0xc8, "blackAggr", "d"), (0xd0, "extShadowAggr", "d"),
    (0xd8, "shadowAggr", "d"), (0xe0, "highlightAggr", "d"),
    (0xe8, "extHighlightAggr", "d"),
    (0xf0, "shadowExpScale", "d"), (0xf8, "highlightExpScale", "d"),
    (0x100, "shadowMaxExpSlope", "d"), (0x108, "highlightMaxExpSlope", "d"),
    (0x110, "shadowCompBlend", "d"), (0x118, "highlightCompBlend", "d"),
    (0x120, "shadowExpBlend", "d"), (0x128, "highlightExpBlend", "d"),
    (0x130, "shadowTransitionRatio", "d"), (0x138, "highlightTransitionRatio", "d"),
    (0x140, "shadowExpSatFactor", "d"), (0x148, "shadowCompSatFactor", "d"),
    (0x150, "highlightExpSatFactor", "d"), (0x158, "highlightCompSatFactor", "d"),
    (0x160, "satSmoothingWidth", "d"), (0x168, "shadowDesatDim", "d"),
    (0x170, "shadowMinDesat", "d"), (0x178, "shadowDesatLumAdj", "d"),
    (0x180, "shadowDesatBlend", "d"), (0x188, "shadowExpTxtFactor", "d"),
    (0x190, "shadowCompTxtFactor", "d"), (0x198, "highlightExpTxtFactor", "d"),
]
STRUCT_SIZE = 0x200


def parse_dpi(path):
    vals = {}
    for line in open(path):
        line = line.split("#")[0].strip()
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        vals[k.strip()] = v.strip()
    return vals


def build(dpi_path):
    vals = parse_dpi(dpi_path)
    buf = bytearray(STRUCT_SIZE)
    used, missing = [], []
    for off, name, kind in LAYOUT:
        if name not in vals:
            missing.append(name)
            continue
        raw = vals[name]
        try:
            if kind == "i":
                struct.pack_into("<i", buf, off, int(float(raw)))
            else:
                if raw.lower() in ("true", "false"):
                    raise ValueError(raw)
                struct.pack_into("<d", buf, off, float(raw))
            used.append(name)
        except ValueError:
            missing.append(f"{name}(={raw})")
    return bytes(buf), used, missing


if __name__ == "__main__":
    p = (sys.argv[1] if len(sys.argv) > 1 else
         "/Users/guy/www/pakon-mac/.claude/worktrees/tender-gliding-abelson/"
         "vendor/ansel/anselinstalldir/dataPathItems/shasta/shasta-rpd.dpi")
    buf, used, missing = build(p)
    out = sys.argv[2] if len(sys.argv) > 2 else "shasta_params.bin"
    open(out, "wb").write(buf)
    print(f"{p}\n -> {out}  ({len(buf)} bytes)")
    print(f"populated {len(used)} fields; not populated: {missing}")
    for off, name, kind in LAYOUT[:12]:
        v = (struct.unpack_from("<i", buf, off)[0] if kind == "i"
             else struct.unpack_from("<d", buf, off)[0])
        print(f"   +{off:#05x} {name:24s} = {v}")
