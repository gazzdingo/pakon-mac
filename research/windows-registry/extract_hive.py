import struct, datetime, sys, json

H = "/Users/angford-lee/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds"
HIVE_BASE = 0x118bcbe00
D0 = HIVE_BASE + 0x1000

f = open(H, "rb")
TYPES = {0: "REG_NONE", 1: "REG_SZ", 2: "REG_EXPAND_SZ", 3: "REG_BINARY",
         4: "REG_DWORD", 5: "REG_DWORD_BE", 7: "REG_MULTI_SZ", 11: "REG_QWORD"}

def rd(off, n):
    f.seek(off)
    return f.read(n)

def cell(cell_off, n):
    return rd(D0 + cell_off + 4, n)

def ft(v):
    try:
        return (datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=v // 10)).isoformat(sep=" ")
    except Exception:
        return "?"

def parse_vk(cell_off):
    b = cell(cell_off, 24)
    if b[0:2] != b"vk":
        return None
    name_len, data_len, data_off, vtype, flags = struct.unpack("<HIIIH", b[2:18])
    inline = bool(data_len & 0x80000000)
    dlen = data_len & 0x7FFFFFFF
    name = cell(cell_off + 20, name_len).decode("latin-1") if name_len else "(Default)"
    if inline:
        raw = struct.pack("<I", data_off)[:dlen if dlen <= 4 else 4]
    else:
        raw = cell(data_off, min(dlen, 8192)) if dlen else b""
    if vtype == 4 and len(raw) >= 4:
        v = struct.unpack("<i", raw[:4])[0]
    elif vtype in (1, 2):
        v = raw.decode("utf-16-le", "replace").rstrip("\x00")
    elif vtype == 7:
        v = [s for s in raw.decode("utf-16-le", "replace").split("\x00") if s]
    elif vtype == 11 and len(raw) >= 8:
        v = struct.unpack("<Q", raw[:8])[0]
    else:
        v = raw.hex()
    return {"name": name, "type": TYPES.get(vtype, "type%d" % vtype), "size": dlen, "value": v}

def parse_nk(cell_off):
    b = cell(cell_off, 80)
    if b[0:2] != b"nk":
        return None
    ts = struct.unpack("<Q", b[4:12])[0]
    nsub = struct.unpack("<I", b[20:24])[0]
    sublist = struct.unpack("<i", b[28:32])[0]
    nval = struct.unpack("<I", b[36:40])[0]
    vallist = struct.unpack("<i", b[40:44])[0]
    namelen = struct.unpack("<H", b[72:74])[0]
    name = cell(cell_off + 76, namelen).decode("latin-1", "replace")
    return {"cell": cell_off, "ts": ts, "nsub": nsub, "sublist": sublist,
            "nval": nval, "vallist": vallist, "name": name}

def subkeys(nk):
    if nk["nsub"] == 0 or nk["sublist"] < 0:
        return []
    b = cell(nk["sublist"], 8)
    sig = b[0:2]
    n = struct.unpack("<H", b[2:4])[0]
    out = []
    if sig in (b"lf", b"lh"):
        raw = cell(nk["sublist"] + 4, 8 * n)
        for i in range(n):
            out.append(struct.unpack("<i", raw[i * 8:i * 8 + 4])[0])
    elif sig == b"li":
        raw = cell(nk["sublist"] + 4, 4 * n)
        for i in range(n):
            out.append(struct.unpack("<i", raw[i * 4:i * 4 + 4])[0])
    elif sig == b"ri":
        raw = cell(nk["sublist"] + 4, 4 * n)
        for i in range(n):
            sub = struct.unpack("<i", raw[i * 4:i * 4 + 4])[0]
            b2 = cell(sub, 8)
            n2 = struct.unpack("<H", b2[2:4])[0]
            raw2 = cell(sub + 4, 8 * n2)
            for j in range(n2):
                out.append(struct.unpack("<i", raw2[j * 8:j * 8 + 4])[0])
    return out

def values(nk):
    if nk["nval"] == 0 or nk["vallist"] < 0:
        return []
    raw = cell(nk["vallist"], 4 * nk["nval"])
    out = []
    for i in range(nk["nval"]):
        vo = struct.unpack("<i", raw[i * 4:i * 4 + 4])[0]
        v = parse_vk(vo)
        if v:
            out.append(v)
    return out

root_cell = struct.unpack("<i", rd(HIVE_BASE + 0x24, 4))[0]
root = parse_nk(root_cell)
print("root key:", root["name"], "subkeys:", root["nsub"], file=sys.stderr)

for c in subkeys(root):
    nk = parse_nk(c)
    if nk:
        print("  /%s  (subkeys=%d values=%d)  %s" % (nk["name"], nk["nsub"], nk["nval"], ft(nk["ts"])), file=sys.stderr)

# ---- full recursive dump of chosen subtrees ---------------------------------
def dump(nk, path, out, jout, depth=0):
    vals = values(nk)
    entry = {"path": path, "last_written": ft(nk["ts"]), "values": vals}
    jout.append(entry)
    out.write("\n[%s]\n" % path)
    out.write("; last written %s   (%d values, %d subkeys)\n" % (ft(nk["ts"]), nk["nval"], nk["nsub"]))
    for v in vals:
        out.write('"%s"=%s:%s\n' % (v["name"], v["type"], v["value"]))
    for c in subkeys(nk):
        child = parse_nk(c)
        if child:
            dump(child, path + "\\" + child["name"], out, jout, depth + 1)

WANT = ("Pakon", "Kodak")
out = open("pakon_registry_full.txt", "w")
out.write("Full registry extraction from the PakonScanXP-F135 virtual disk\n")
out.write("Source hive: HKLM\\SOFTWARE  (regf at image offset 0x%x)\n" % HIVE_BASE)
out.write("Extracted offline from the .hds image; the VM was never booted.\n")
jout = []
for c in subkeys(root):
    nk = parse_nk(c)
    if nk and nk["name"] in WANT:
        dump(nk, "HKEY_LOCAL_MACHINE\\SOFTWARE\\" + nk["name"], out, jout)
out.close()
json.dump(jout, open("pakon_registry_full.json", "w"), indent=1)
print("keys dumped:", len(jout), file=sys.stderr)
