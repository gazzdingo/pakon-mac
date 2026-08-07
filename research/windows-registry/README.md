# Windows registry extraction — Pakon F-135 lamp calibration

Everything here was produced on the Mac on **2026-08-06** by carving the
`HKLM\SOFTWARE` hive out of the Parallels VM's virtual disk. The VM was never
booted (its Parallels licence has expired), nothing was written to any registry,
and the scanner was not needed.

**Start with [`NOTES.md`](NOTES.md)** — the verdict and the evidence.
Then [`lamp-calibration.md`](lamp-calibration.md) for the 18 keys in full.
The narrative write-up is `docs/37-calibration-recovered.md`.

## One-paragraph version

This unit's LED calibration is recovered and is in the registry. So is a
*different* scanner's (serial 16275), because the VM is a prebuilt Pakon XP
image from the Facebook community rather than an image of our machine. The two
are separated by write date: the 2025-07 keys were written while our scanner was
attached over USB; the 2022-11-10 keys came with the image. Use the former,
never the latter.

## Results

| file | what |
|---|---|
| `NOTES.md` | verdict, provenance, trust tiers, parsing gotchas |
| `lamp-calibration.md` | all 18 calibration keys as tables |
| `pakon_registry_full.txt` | `HKLM\SOFTWARE\Pakon` + `\Kodak`, .reg-style, 122 keys |
| `pakon_registry_full.json` | the same, machine-readable |

## Tools — the extraction pipeline, in order

Each is standalone Python 3, no dependencies. Paths to the `.hds` are hardcoded
at the top of each file; edit them if the VM moves.

| tool | what it does |
|---|---|
| `extract_hive.py` | **the main one.** Walks `nk`/`vk`/`lf`/`lh`/`ri` records and dumps the Pakon + Kodak subtrees to txt and json |
| `tools/02_classify_hits.py` | separates real registry `vk` records from identical strings in TLB.dll's string table — the step that made the search meaningful |
| `tools/03_find_hive.py` | locates `regf` hive headers in the image and reads their names |
| `tools/04_dump_window.py` | dumps every key and value in a byte window |
| `tools/05_carve_region.py` | wide carve over a 5 MB region; the superset the results were checked against |
| `tools/06_resolve_out_of_line.py` | resolves out-of-line value data (the `DutyCycle_*` strings) |
| `tools/07_correlate_usb_timeline.py` | **the decisive one.** Corrects the guest-clock offset and tests each calibration key's write time against the USB attach windows |

The initial scan that started it all was just:

```bash
LC_ALL=C grep -a -b -o -E "Current_R|Current_Ir|Duty_Ir|TempSetpoint|CiConfigLight|PakonLampLog" "$HDS"
```

## Evidence

| file | what |
|---|---|
| `evidence/usb-attach-events.txt` | every `0f05:f135` line in `parallels.log` — four successful attaches |
| `evidence/usb-timeline-correlation.txt` | output of tool 07: which key belongs to which scanner |
| `evidence/usb-devices-seen.txt` | all USB devices the VM ever saw, with counts |
| `evidence/hds_hits.txt` | raw byte offsets of the initial string scan |
| `evidence/vk_dump.txt` | keys and values in the 107 KB window around the cluster |
| `evidence/pakon_registry_carve.txt` | wide 5 MB carve: 5761 keys, 11709 values |

## Reproducing

The SOFTWARE hive begins at image offset `0x118bcbe00` in

```
~/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/
    PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-6958-40ff-92a7-860e329aab41}.hds
```

The `.hds` is a Parallels expanding image (`WithoutFreeSpace`, pd17), so it is
not a raw disk — but the hive region is contiguous within it, so registry cell
offsets resolve linearly:

```
file_offset = 0x118bcbe00 + 0x1000 + cell_offset
```

That is why no qemu, NTFS driver, or disk conversion was needed. If the hive
ever needs re-carving from a different image, verify that assumption first:
`tools/06_resolve_out_of_line.py` prints how many out-of-line values resolve to
valid cells under it, and a low count means the region is fragmented and a real
conversion is required.
