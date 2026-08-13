#!/usr/bin/env python3
"""READ-ONLY: dump the Pakon FX2 boot EEPROM personality.

Writes nothing. Uses vendor request 0xA9 (READ) only -- the write request
(0xA2) is never issued and is not even referenced below.

Expected healthy content for an F-135 (Kodak's USB F135.bin):

    c0 05 0f 35 f2 07 aa 04 02
       |  VID  |  PID  | rev |
       0x0F05   0xF235   0xAA07      byte 5 = 0x07 = F135

Hypothesis under test: the PID field now reads  f2 35  instead of  35 f2,
i.e. 0x35F2 instead of 0xF235 -- a byte-swap that makes the scanner enumerate
as an F-235 and prevents the WDGTLDR loader from ever binding.

Before running:
  * the scanner must be attached to the MAC, not passed through to the VM.
    Shut the Parallels VM down, or disconnect the device from it.

Run:
  python3 read_personality.py
"""
import sys

READ = 0xA9                     # stage-1 loader personality read
VENDOR_IN = 0xC0                # device-to-host | vendor | device
PAKON_VID = 0x0F05
EXPECTED = bytes.fromhex("c0050f35f207aa0402")


def get_backend():
    candidates = []
    try:
        import libusb_package
        candidates.append(("libusb-package", libusb_package.get_libusb1_backend()))
    except Exception:
        pass
    import usb.backend.libusb1
    for p in ("/Applications/microchip/mplabcomm/3.53.00/lib/libusb-1.0.0.dylib",
              "/Applications/microchip/mplabcomm/3.47.00/lib/libusb-1.0.0.dylib",
              "/usr/local/lib/libusb-1.0.dylib"):
        try:
            b = usb.backend.libusb1.get_backend(find_library=lambda x, p=p: p)
            if b is not None:
                candidates.append((p, b))
        except Exception:
            pass
    return candidates


def main():
    import usb.core
    for name, backend in get_backend():
        if backend is None:
            continue
        devs = list(usb.core.find(find_all=True, backend=backend))
        if not devs:
            print("[%s] enumerated 0 devices, trying next backend" % name)
            continue
        print("[%s] %d USB devices visible" % (name, len(devs)))
        pak = [d for d in devs if d.idVendor == PAKON_VID]
        if not pak:
            print("  no Pakon (VID 0x0F05) device found.")
            print("  Is it still passed through to the Parallels VM? Shut the VM down.")
            return 1
        for d in pak:
            print("\n  FOUND  %04x:%04x  bcdDevice=0x%04x" % (d.idVendor, d.idProduct, d.bcdDevice))
            if d.idProduct == 0x35F2:
                print("         (enumerating as 0x35F2 -- the F-235 identity)")
            elif d.idProduct == 0xF235:
                print("         (enumerating as 0xF235 -- correct bootloader identity)")
            elif d.idProduct == 0xF135:
                print("         (enumerating as 0xF135 -- firmware loaded, healthy)")
            try:
                raw = bytes(d.ctrl_transfer(VENDOR_IN, READ, 0, 0, 9, 5000))
            except Exception as e:
                print("         personality read failed: %s: %s" % (type(e).__name__, e))
                continue
            print("         personality: %s" % raw.hex(" "))
            print("         expected   : %s" % EXPECTED.hex(" "))
            if raw == EXPECTED:
                print("         => MATCHES the healthy F-135 personality.")
                print("            The EEPROM is NOT the problem; look elsewhere.")
            elif len(raw) >= 5 and raw[3:5] == bytes.fromhex("f235"):
                print("         => PID field is BYTE-SWAPPED (f2 35, should be 35 f2).")
                print("            Confirms the diagnosis in docs/69.")
            else:
                print("         => differs from expected, but not a simple byte-swap.")
                print("            Do not write anything yet -- report this output first.")
        return 0
    print("No usable libusb backend enumerated any devices.")
    print("Try running this from a normal Terminal window.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
