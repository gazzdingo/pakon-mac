import struct, datetime, sys

H = "/Users/angford-lee/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds"
LO, HI = 4729000000, 4734000000     # ~5 MB spanning the Pakon subtree

TYPES = {0: "REG_NONE", 1: "REG_SZ", 2: "REG_EXPAND_SZ", 3: "REG_BINARY",
         4: "REG_DWORD", 7: "REG_MULTI_SZ", 11: "REG_QWORD"}

f = open(H, "rb")
f.seek(LO)
region = f.read(HI - LO)

def ft(v):
    try:
        return str(datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=v // 10))
    except Exception:
        return "?"

keys = []
i = 0
while True:
    i = region.find(b"nk", i)
    if i == -1:
        break
    if i + 80 <= len(region):
        b = region[i:i + 80]
        flags = struct.unpack("<H", b[2:4])[0]
        ts = struct.unpack("<Q", b[4:12])[0]
        nval = struct.unpack("<I", b[36:40])[0]
        namelen = struct.unpack("<H", b[72:74])[0]
        if 0 < namelen < 64 and flags in (0x20, 0x2c, 0x28, 0x24) and nval < 500:
            try:
                name = region[i + 76:i + 76 + namelen].decode("ascii")
                if name.isprintable() and 1601 < int(ft(ts)[:4]) < 2027:
                    keys.append((LO + i, name, nval, ft(ts)))
            except Exception:
                pass
    i += 2

vals = []
i = 0
while True:
    i = region.find(b"vk", i)
    if i == -1:
        break
    if i + 24 <= len(region):
        b = region[i:i + 24]
        name_len, data_len, data_off, vtype, flags = struct.unpack("<HIIIH", b[2:18])
        inline = bool(data_len & 0x80000000)
        dlen = data_len & 0x7FFFFFFF
        if 0 < name_len < 64 and vtype in TYPES and i + 20 + name_len <= len(region):
            try:
                name = region[i + 20:i + 20 + name_len].decode("ascii")
            except Exception:
                i += 2
                continue
            if name.isprintable() and name.strip():
                if inline:
                    raw = struct.pack("<I", data_off)
                    val = struct.unpack("<I", raw)[0] if vtype == 4 else raw[:dlen].hex()
                else:
                    val = "<out-of-line, len=%d>" % dlen
                vals.append((LO + i, name, TYPES[vtype], dlen, val))
    i += 2

out = open(sys.argv[1] if len(sys.argv) > 1 else "/dev/stdout", "w")
out.write("Registry carve from PakonScanXP-F135.pvm virtual disk (HKLM\\SOFTWARE hive)\n")
out.write("Image window %d..%d\n" % (LO, HI))
out.write("Keys: %d   Values: %d\n\n" % (len(keys), len(vals)))

out.write("=" * 78 + "\nKEYS\n" + "=" * 78 + "\n")
for off, name, nval, ts in keys:
    out.write("%-12d %-36s values=%-4d %s\n" % (off, name, nval, ts))

out.write("\n" + "=" * 78 + "\nVALUES\n" + "=" * 78 + "\n")
out.write("%-12s %-28s %-14s %-6s %s\n" % ("offset", "name", "type", "size", "value"))
for off, name, t, dlen, val in vals:
    out.write("%-12d %-28s %-14s %-6d %s\n" % (off, name, t, dlen, val))
out.close()

CAL = ("Current_", "Duty", "Temp", "Offset", "Motor", "Integration", "VisOn",
       "IrOn", "Lamp", "Led", "LED", "Exposure", "Gain", "TEC")
print("keys=%d values=%d" % (len(keys), len(vals)))
print("\ncalibration-relevant value names present:")
names = {}
for off, name, t, dlen, val in vals:
    if any(c in name for c in CAL):
        names.setdefault(name, []).append(val)
for n in sorted(names):
    v = names[n]
    print("  %-28s x%-3d  %s" % (n, len(v), sorted(set(map(str, v)))[:8]))
