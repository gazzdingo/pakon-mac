import sys, struct

H = "/Users/angford-lee/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds"

hits = []
for line in open("/private/tmp/claude-501/-Users-angford-lee/00cd6c2f-4f63-4f5e-a9cf-26cd3fa12eb3/scratchpad/hds_hits.txt"):
    line = line.rstrip("\n")
    if ":" not in line:
        continue
    off, name = line.split(":", 1)
    hits.append((int(off), name))

f = open(H, "rb")
vk_hits = []
for off, name in hits:
    f.seek(max(0, off - 24))
    pre = f.read(24)
    # vk record: sig 'vk' at name_off-20 ; name_len at -18 should equal len(name-ish)
    tag = "-"
    if len(pre) == 24:
        if pre[4:6] == b"vk":
            nlen = struct.unpack("<H", pre[6:8])[0]
            tag = "VK(namelen=%d)" % nlen
        elif pre[2:4] == b"nk":
            tag = "NK(key)"
    f.seek(off)
    after = f.read(len(name) + 40)
    vk_hits.append((off, name, tag, after))

print("hit offset        name           context")
for off, name, tag, after in vk_hits:
    mark = "  <-- REGISTRY" if tag != "-" else ""
    print("%-16d %-14s %-16s %r%s" % (off, name, tag, after[:36], mark))

print()
print("registry-context hits:", sum(1 for h in vk_hits if h[2] != "-"))
