import struct, datetime

H = "/Users/angford-lee/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds"
LO, HI = 4731500000, 4731610000

TYPES = {0: "REG_NONE", 1: "REG_SZ", 2: "REG_EXPAND_SZ", 3: "REG_BINARY",
         4: "REG_DWORD", 7: "REG_MULTI_SZ", 11: "REG_QWORD"}

f = open(H, "rb")
f.seek(LO)
region = f.read(HI - LO)
print("window %d..%d (%d KB)\n" % (LO, HI, len(region) // 1024))

def ft(v):
    try:
        return str(datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=v // 10))
    except Exception:
        return "?"

# --- every nk (key) name in the window --------------------------------------
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
            name = region[i + 76:i + 76 + namelen]
            try:
                name = name.decode("ascii")
                if name.isprintable():
                    keys.append((LO + i, name, nval, ft(ts)))
            except Exception:
                pass
    i += 2

print("=== KEYS (nk) in window ===")
for off, name, nval, ts in keys:
    print("  %-12d %-34s values=%-4d last-written=%s" % (off, name, nval, ts))

# --- every vk (value) in the window -----------------------------------------
print("\n=== VALUES (vk) in window ===")
print("%-12s %-24s %-12s %-8s %s" % ("offset", "name", "type", "size", "value"))
i = 0
seen = 0
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
            name = region[i + 20:i + 20 + name_len]
            try:
                name = name.decode("ascii")
            except Exception:
                i += 2
                continue
            if name.isprintable() and name.strip():
                val = "<not inline>"
                if inline:
                    raw = struct.pack("<I", data_off)
                    if vtype == 4:
                        val = struct.unpack("<I", raw)[0]
                    else:
                        val = raw[:dlen].hex()
                print("%-12d %-24s %-12s %-8d %s" % (LO + i, name, TYPES[vtype], dlen, val))
                seen += 1
    i += 2
print("\ntotal values printed:", seen)
