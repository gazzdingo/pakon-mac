# Vendor scans — end-to-end ground truth

Six frames of real film, scanned by the vendor software (PSI) on the XP VM,
from this scanner, in one session. Each frame is a **pair**:

| file | what it is |
|---|---|
| `rawAA00N.png` | PSI's "RAW" export — the least-processed stage it will emit |
| `AA00N.png` | PSI's finished render of the same frame |

This is the only end-to-end ground truth in the project: the same photons
through the vendor's whole pipeline, against which the port can be compared.

## Two things to know before using them

**1. `rawAA00N` is not sensor data.** It is 8-bit RGB and already substantially
processed — a positive image, not a negative. PSI does not export the 12-bit
path at all. Do not treat these as CCD output.

**2. These are lossless conversions of the original TIFFs.** The originals were
uncompressed 8-bit RGB TIFF, 2941×1960, 17,293,326 B each — 208 MB for twelve,
against a 45 MB repo. Converting to PNG gives 103 MB and loses nothing:

* every PNG was verified to round-trip to **pixel-identical** bytes
* `manifest.json` records the SHA-256 of the original TIFF **and** of the raw
  pixel buffer for each file, so identity is checkable
* the originals carried no vendor metadata — 16 structural TIFF tags, nothing
  else, and identical between the raw and rendered files. Only the 300 DPI
  resolution needed preserving, and PNG carries it.

Verify any file:

```python
from PIL import Image; import hashlib, json
m = json.load(open("manifest.json"))
px = Image.open("rawAA005.png").tobytes()
assert hashlib.sha256(px).hexdigest() == m["rawAA005.tif"]["pixel_sha256"]
```

## The measurement that defines the defect

Per channel, 0-255:

```
frame        ch     p1    p5   p50   p95   p99   min   max
rawAA005     R      14    19    76   164   180     7   202
             G      10    14    42   112   122     4   131
             B       6     8    35   107   114     2   125
vendorAA005  R       0     0    35   228   241     0   255
             G       6     8    87   226   245     5   255
             B       5     8    94   236   253     0   255
```

The vendor reaches **p1 = 0/6/5** — true black — and uses the full range. The
port's floor on this same frame is 60-110. `AA005` is the reference frame used
throughout `docs/54` and `docs/58`; if you are testing a fix, test it here
first.

Originals remain at `~/pakon-findings/incoming/*.tif`, outside git.
