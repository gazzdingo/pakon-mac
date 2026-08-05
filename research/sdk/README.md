# Recovered Pakon documentation and software

Everything here was recovered from public archives on 2026-08-05.
`PAKONF135.iso` (171 MB) is deliberately **gitignored** — on disk, not in git.

## The prize: official COM SDK documentation

| File | What it is |
|---|---|
| `f235-com-ref.pdf` | **F235 COM Reference Manual**, Pakon #124580 Rev I, 15 Jun 2004, ~150pp. Full function reference for the TLA COM server: interfaces `ITLAMain`, `IScanPictures`, `ISavePictures`, `ILongOpsCB`, `ICallBackClient`; every method (`InitializeScanner`, `ScanPictures`, `SaveToDisk`, `GetPictureColorSettings`…), all enums, error-code tables |
| `f235-com-guide.pdf` | **F235 COM Users Guide**, #124579 Rev I. Architecture, threading model, callback pattern, worked scanning scenarios |

This is the official API documentation for the scanner. It documents the
operation sequence a host must perform — exactly the state machine a macOS port
has to reimplement, which we had been reconstructing packet by packet.

Note from the Users Guide: the SDK shipped a **scanner-less simulator,
`TLAs.dll`** — potentially very useful for testing a reimplementation with no
hardware attached.

## Service and disassembly manuals

| File | Model |
|---|---|
| `F135_SM.pdf` | F-135 Service Manual |
| `F135_Disassembly.pdf`, `F135_Dis2/3.pdf` | F-135 mechanical disassembly |
| `F235_SM.pdf`, `SM124603E.pdf`, `svc.pdf` | F-235 Service Manual (#124603-E) |
| `F235_Disassembly.pdf` | F-235 disassembly (5.9 MB) |
| `F335_SM.pdf`, `F335_Disassembly.pdf` | F-335 service + disassembly (10 MB) |
| `F135_UM.pdf`, `F235_UM.pdf` | User manuals |
| `PSI_Help.pdf` | PSI application help |
| `kodakf235.pdf`, `125336A.pdf` | Kodak-branded F235 material |

## Software

`PAKONF135.iso` — the full 171 MB F-135 software distribution: `TLA.dll`,
`TLB.dll`, `TLC.dll`, `tlx.dll`, `TLXClientDemo.exe`, `PakonIMAu.dll`,
`AIDToolkit.dll`, `DMLDICELib.dll`, drivers `F235Ldr.sys` / `F235usb2.sys` /
`F135usb2.sys` / `FX35usb2.sys`, firmware `Pakon5/7/8.hex`, `PknInit.hex`,
plus `FX35 SDK Release Notes.doc`.

## Text extracts

`*.txt` files are text layers pulled from the PDFs and string dumps from the
binaries, for grepping without opening the originals.
