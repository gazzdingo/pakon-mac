import struct

H = "/Users/angford-lee/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds"
LO, HI = 4729000000, 4734000000
HIVE_BASE = 0x118bcbe00
D0 = HIVE_BASE + 0x1000

f = open(H, "rb")
f.seek(LO)
region = f.read(HI - LO)

# collect out-of-line vks of interest
targets = []
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
        if 0 < name_len < 64 and not inline and 0 < dlen < 256 and i + 20 + name_len <= len(region):
            try:
                name = region[i + 20:i + 20 + name_len].decode("ascii")
            except Exception:
                i += 2
                continue
            if name.startswith(("DutyCycle", "WaitForLamp")):
                targets.append((LO + i, name, dlen, data_off, vtype))
    i += 2

print("out-of-line targets:", len(targets))

def try_delta(D, n=40):
    ok = 0
    for off, name, dlen, doff, vtype in targets[:n]:
        fo = D + doff
        if not (LO <= fo < HI - 64):
            continue
        cell = region[fo - LO: fo - LO + 4 + dlen]
        if len(cell) < 4 + dlen:
            continue
        size = struct.unpack("<i", cell[:4])[0]
        if size < 0 and abs(size) >= dlen + 4:
            data = cell[4:4 + dlen]
            try:
                s = data.decode("utf-16-le").rstrip("\x00")
                if s and all(c in "0123456789.-+eE" for c in s):
                    ok += 1
            except Exception:
                pass
    return ok

print("testing D0 = hive_base+0x1000 -> valid:", try_delta(D0))

# derive delta empirically from a UTF-16 decimal string near the first target
best = (0, None)
if try_delta(D0) < 5 and targets:
    off, name, dlen, doff, vtype = targets[0]
    cands = {}
    j = 0
    while True:
        j = region.find(b".\x00", j)
        if j == -1 or j > len(region):
            break
        st = max(0, j - 20)
        chunk = region[st:j + 20]
        try:
            s = chunk.decode("utf-16-le", "ignore")
        except Exception:
            j += 2
            continue
        j += 2
        # candidate data start = position of a numeric utf16 run
        for k in range(st, j):
            pass
    # simpler: scan every 2-byte aligned pos for an 18-byte utf16 numeric string
    pos = 0
    while pos < len(region) - 20:
        d = region[pos:pos + dlen]
        try:
            s = d.decode("utf-16-le")
        except Exception:
            pos += 2
            continue
        if s and s[0].isdigit() and all(c in "0123456789.\x00" for c in s) and "." in s:
            sz = struct.unpack("<i", region[pos - 4:pos])[0] if pos >= 4 else 0
            if sz < 0:
                D = (LO + pos) - doff
                cands[D] = cands.get(D, 0) + 1
        pos += 2
    for D in sorted(cands, key=lambda x: -cands[x])[:10]:
        v = try_delta(D)
        if v > best[0]:
            best = (v, D)
    print("best empirical delta:", best)

D = D0 if try_delta(D0) >= 5 else best[1]
print("using delta:", D)
print()
if D:
    print("%-12s %-24s %-8s %s" % ("vk offset", "name", "len", "value"))
    for off, name, dlen, doff, vtype in targets:
        fo = D + doff
        if LO <= fo < HI - 64:
            cell = region[fo - LO: fo - LO + 4 + dlen]
            if len(cell) >= 4 + dlen:
                data = cell[4:4 + dlen]
                try:
                    s = data.decode("utf-16-le").rstrip("\x00")
                except Exception:
                    s = data.hex()
                print("%-12d %-24s %-8d %r" % (off, name, dlen, s))
