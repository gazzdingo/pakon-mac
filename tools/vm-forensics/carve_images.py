"""Carve large images (JPEG/TIFF) out of the Parallels virtual disk.

Read-only. Filters by decoded pixel dimensions so we get scans rather than
the XP install's icons and wallpapers.
"""
import struct, os, sys

H = ("/Users/angford-lee/Parallels/PakonScanXP-F135.pvm/"
     "PakonScanXP-F135-disk001-fixed.hdd/"
     "PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds")
OUT = "/Users/angford-lee/pakon-findings/carved"
MIN_W = 800          # scans are ~2151 px wide; icons/wallpaper are below this
CHUNK = 32 * 1024 * 1024
OVERLAP = 4096


def jpeg_dims(f, off):
    """Parse JPEG markers from off, return (w,h,end_off) or None."""
    f.seek(off)
    d = f.read(4)
    if len(d) < 4 or d[0:2] != b"\xff\xd8" or d[2] != 0xFF:
        return None
    pos = off + 2
    w = h = None
    for _ in range(400):
        f.seek(pos)
        hdr = f.read(4)
        if len(hdr) < 4 or hdr[0] != 0xFF:
            return None
        m = hdr[1]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            pos += 2
            continue
        seglen = struct.unpack(">H", hdr[2:4])[0]
        if seglen < 2:
            return None
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            f.seek(pos + 5)
            hw = f.read(4)
            if len(hw) < 4:
                return None
            h, w = struct.unpack(">HH", hw)
        if m == 0xDA:                       # start of scan -- find EOI
            p = pos + 2 + seglen
            f.seek(p)
            buf = f.read(64 * 1024 * 1024)
            e = buf.find(b"\xff\xd9")
            end = p + e + 2 if e != -1 else None
            return (w, h, end) if w else None
        pos += 2 + seglen
    return None


def tiff_dims(f, off):
    f.seek(off)
    d = f.read(8)
    if len(d) < 8:
        return None
    if d[0:4] == b"II\x2a\x00":
        en = "<"
    elif d[0:4] == b"MM\x00\x2a":
        en = ">"
    else:
        return None
    ifd = struct.unpack(en + "I", d[4:8])[0]
    if ifd > 200 * 1024 * 1024:
        return None
    f.seek(off + ifd)
    cnt_raw = f.read(2)
    if len(cnt_raw) < 2:
        return None
    n = struct.unpack(en + "H", cnt_raw)[0]
    if n > 512:
        return None
    ents = f.read(12 * n)
    w = h = None
    maxend = 0
    for i in range(n):
        e = ents[i * 12:(i + 1) * 12]
        if len(e) < 12:
            break
        tag, typ, cn = struct.unpack(en + "HHI", e[0:8])
        val = struct.unpack(en + "I", e[8:12])[0]
        if typ == 3:
            val = struct.unpack(en + "H", e[8:10])[0]
        if tag == 256: w = val
        elif tag == 257: h = val
        elif tag in (273, 279, 324, 325):
            maxend = max(maxend, val)
    if w and h:
        return (w, h, off + max(ifd + 2 + 12 * n + 4, maxend + 1))
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    size = os.path.getsize(H)
    f = open(H, "rb")
    found = []
    pos = 0
    while pos < size:
        f.seek(pos)
        buf = f.read(CHUNK + OVERLAP)
        if not buf:
            break
        for sig in (b"\xff\xd8\xff", b"II\x2a\x00", b"MM\x00\x2a"):
            i = 0
            while True:
                i = buf.find(sig, i)
                if i == -1 or i > CHUNK:
                    break
                off = pos + i
                try:
                    r = jpeg_dims(f, off) if sig[0] == 0xFF else tiff_dims(f, off)
                except Exception:
                    r = None
                if r and r[0] and r[0] >= MIN_W and r[2] and r[2] > off:
                    length = r[2] - off
                    if 20000 < length < 400 * 1024 * 1024:
                        kind = "jpg" if sig[0] == 0xFF else "tif"
                        found.append((off, r[0], r[1], length, kind))
                        print("  %-12d %5dx%-5d %9d B  %s" % (off, r[0], r[1], length, kind))
                i += 2
        pos += CHUNK
        pct = 100.0 * pos / size
        print("...%.0f%% (%d candidates)" % (pct, len(found)), file=sys.stderr)
    print("\ntotal candidates:", len(found))
    # de-duplicate identical (offset) and write out
    seen = set()
    n = 0
    for off, w, h, ln, kind in found:
        if off in seen:
            continue
        seen.add(off)
        f.seek(off)
        data = f.read(ln)
        name = "%s/img_%02d_%dx%d.%s" % (OUT, n, w, h, kind)
        open(name, "wb").write(data)
        n += 1
    print("written:", n, "->", OUT)


if __name__ == "__main__":
    main()
