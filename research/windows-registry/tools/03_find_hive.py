import struct

H = "/Users/angford-lee/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds"
TARGET = 4731517608

f = open(H, "rb")
start = max(0, TARGET - 32 * 1024 * 1024)
f.seek(start)
CHUNK = 4 * 1024 * 1024
found = []
pos = start
while pos < TARGET + 4 * 1024 * 1024:
    f.seek(pos)
    buf = f.read(CHUNK + 8)
    if not buf:
        break
    i = 0
    while True:
        i = buf.find(b"regf", i)
        if i == -1 or i > CHUNK:
            break
        found.append(pos + i)
        i += 4
    pos += CHUNK

print("regf signatures found:", len(found))
for off in found:
    f.seek(off)
    hdr = f.read(0x200)
    # hive file name: offset 0x30, 64 bytes UTF-16LE
    try:
        name = hdr[0x30:0x30 + 64].decode("utf-16-le", "replace").split("\x00")[0]
    except Exception:
        name = "?"
    seq1, seq2 = struct.unpack("<II", hdr[4:12])
    ts = struct.unpack("<Q", hdr[12:20])[0]
    major, minor = struct.unpack("<II", hdr[20:28])
    print("  0x%x (%d)  delta_to_target=%+d  seq=%d/%d  ver=%d.%d  name=%r"
          % (off, off, TARGET - off, seq1, seq2, major, minor, name))

# FILETIME -> readable
def ft(v):
    import datetime
    if v == 0:
        return "none"
    return str(datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=v // 10))

for off in found:
    f.seek(off + 12)
    ts = struct.unpack("<Q", f.read(8))[0]
    print("  hive 0x%x last-written: %s" % (off, ft(ts)))
