#!/usr/bin/env python3
"""Convert the FX35 driver's embedded stage-1 loader into an Intel HEX file.

The Pakon firmware images cannot be loaded by the EZ-USB boot loader alone --
addresses above 0x1B3F require vendor request 0xA3, which is serviced by
firmware rather than hardware. The vendor driver embeds a stage-1 loader that
provides it, as an INTEL_HEX_RECORD array in FX35Loader/Loader.c.

That loader is not redistributed here. Fetch it yourself:

    git clone --depth 1 https://github.com/ktkaufman03/FX35 vendor/FX35
    ./extract_stage1.py vendor/FX35/FX35Loader/Loader.c vendor/stage1_vendor.hex
"""
import re
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <Loader.c> <out.hex>", file=sys.stderr)
        return 2
    src = open(sys.argv[1]).read()
    recs = re.findall(r'\{\s*(\d+)u?,\s*(\d+)u?,\s*(\d+)u?,\s*\{([^}]*)\}\s*\}', src)
    if not recs:
        print("no INTEL_HEX_RECORD entries found", file=sys.stderr)
        return 1
    out = []
    for length, addr, rtype, data in recs:
        length, addr, rtype = int(length), int(addr), int(rtype)
        body = [int(x.strip().rstrip('u')) for x in data.split(',') if x.strip()][:length]
        rec = [length, (addr >> 8) & 0xFF, addr & 0xFF, rtype] + body
        out.append(':' + ''.join(f'{b:02X}' for b in rec) + f'{(-sum(rec)) & 0xFF:02X}')
    with open(sys.argv[2], 'w') as fh:
        fh.write('\n'.join(out) + '\n')
    print(f"wrote {len(out)} records to {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
