# Running the real vendor DLLs under Wine, on macOS

`pref_host.exe` loads the **real** `PakonIMAu.dll` and calls a real function in
it, on this Mac, with no XP box and no scanner. It exists as an independent
second engine to cross-check the Unicorn harnesses in
`tools/ansel/python-pipeline/*_golden.py`.

## Why bother, when Unicorn already runs these functions

The Unicorn harness stubs 471 bound imports by hand, sets its own FPU control
word, and poison-fills mapped pages. Every one of those is a place a wrong
answer could hide — and docs/74 §98 found exactly such a trap: poison reads are
silent, so "zero faults" did **not** mean "all inputs captured".

Wine removes all three: the real loader resolves the real imports, the DLL sets
its own FPU state, and unsupplied memory is ordinary zeroed heap. Same inputs,
same function, two unrelated engines. Agreement is strong evidence;
disagreement would have meant the emulator was wrong.

## Result (docs/74 §99)

Byte-identical shifts **and** anchors on all 12 captured `sba_preference`
calls. The Unicorn port is confirmed correct, and §97's 3-of-6 mismatch against
the vendor's real shifts is a **captured-data** deficit (§98's 384 poisoned
bytes), not an engine defect.

## Dependencies

`PakonIMAu.dll` imports `MSVCR71`, `MSVCP71`, `ekjpegi`, `KODAKCMS` and
`xerces-c_2_2_0`. All five ship in the vendor installer; without them
`LoadLibrary` fails with **126** (`ERROR_MOD_NOT_FOUND`). They are **not**
committed — copy them next to the exe:

    cp "$HOME/Downloads/Pakon Update/msvcr71.dll" .
    cp "$HOME/Downloads/Pakon Update/msvcp71.dll" .
    cp "$HOME/Downloads/Pakon Update/fx35install/System32/xerces-c_2_2_0.dll" .
    cp "$HOME/Downloads/Pakon Update/fx35install/System32/kodakcms.dll" .
    cp "$HOME/Downloads/Pakon Update/fx35install/System32/ekjpegi.dll" .
    cp /Users/guy/pakon-windows-repair/COM-SERVER/PakonIMAu.dll .

## Build and run

    i686-w64-mingw32-gcc -O2 -o pref_host.exe pref_host.c
    python3 pref_host_gen.py [capture.jsonl] [pref_args.bin]
    WINEPREFIX=$HOME/wineprefixes/hookcore_test WINEDEBUG=-all \
        wine pref_host.exe PakonIMAu.dll pref_args.bin

## Two things that will bite

**Captured pointers belong to another process.** `pref_host` reallocates each
dumped buffer locally and rewrites the arg to point at it. Relative offsets
inside a buffer are what the function actually uses, so those are preserved.

**Args with no dump still need valid memory.** Preference *writes* through
several of them (the anchor at `arg2+0x02`, the shift at `arg2+0x08`), so any
arg holding a captured-heap-looking pointer gets a zeroed scratch page. Without
this it faults at `0x1028C802` writing to the captured address — which is
exactly what the first run did.

## Where this goes next

The same pattern generalises: any `PakonIMAu`/`TLB` function whose inputs are
captured can be driven this way. Two limits to keep in view — the captured
buffers are still the *only* inputs (Wine does not conjure the 384 bytes §98
found missing), and driving the full SBA pipeline rather than one function
would need the vendor's own call sequence, not just one entry point.
