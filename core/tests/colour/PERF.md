# Performance and determinism (Task 23, local checks; no CI by ruling R34)

## Bench

`cmake --build build --target colour_bench && build/colour_bench /private/tmp/pakon_re_v2/work/e2e/rolls/r4 [40] [rotation]`
(`core/tests/colour/bench.c`, not registered with ctest). Times `pk_colour_analyse_roll` over 40 scenes (the roll's four
real lo-res frames repeated; the analysis reads only lo-res + strip) and one full 2000 x 3047 `pk_colour_render_rotated`
(best of 3; rotation 0 by default, 270 = PSI's default save geometry). Exit 1 if a target is missed.

Apple M2 Max, Release (-O2 -ffp-contract=off), 2026-10-15:

| | before the final-fix round (single thread, idle machine) | after (NRA fast path + row bands, machine loaded: load average 14-37) | target |
|---|---|---|---|
| 40-frame analysis | 2.27 s (earlier run 1.71 s) | 2.37 s | <= 5 s |
| one full-frame render, rotation 0 | 0.991 s | **0.205 s** | <= 1 s |
| one full-frame render, rotation 270 (PSI's default save) | 0.997 s | **0.225 s** | <= 1 s |

The "after" numbers were taken while other jobs kept the machine at a load average of 14 (earlier runs of the same build
at load 28-37 gave 0.33 s and 0.90 s), so they are a pessimistic floor, not a best case. The render now has 4-5x headroom
on this machine; the analysis has 2x.

### What changed in the render (bit-exact, `nra.c`)

The render was ~93 % `pkc_nra_apply`. Two changes, neither touching an arithmetic result (the tap sums are integers, so order
and split are irrelevant):

1. Interior pixels (not within 5 of an edge, nearly all of a frame) no longer reflect every tap (`refl101` per tap): a row is
   done tap by tap over all its interior pixels with plain strided loads, which the compiler vectorises. CPU time of the NRA
   on three 2000 x 3047 planes of dense random data, same loaded machine: 1.04-1.38 s -> 0.48 s (2-3x). The border band keeps
   the reflecting walk.
2. The three planes are cut into 8 row bands each and dealt to up to 8 worker threads (`sysconf(_SC_NPROCESSORS_ONLN)`, capped
   at 8; images under 400 000 pixels per plane stay on the calling thread; a thread that cannot be created is run inline).
   Wall time of that NRA call: 1.06 s -> 0.10 s.

Proof of bit-exactness: `nra` ctest (16 tests) and the whole suite; `lab/nra/band_check.c` (build against `libpakon_colour.a`) against the previous per-pixel code on
2000 x 3047 random data with random thresholds, plus 37 x 25, 11 x 11, 12 x 400 and 400 x 12 (equal, memcmp); the e2e corpus
(`core/tests/colour/e2e.py`, 5 rolls on disk: 42 frames, 0 differing u8 and 12-bit outputs, 80 adjusted renders and 7
AnselOrientation-0 renders, 0 differing); `xarch_check.sh` (arm64 twice and x86_64 under Rosetta: 8 files identical) and the
suite built for x86_64 (21/21).

Note for callers: `pk_colour_render*` uses worker threads of its own for large frames. The host controls it (R40, review I-NEW-1):
`pk_colour_open_opts(.., &(pk_colour_options){ .size = sizeof(pk_colour_options), .threads = N }, ..)` fixes the count in the handle, which stays immutable: 0 = automatic
(the default, cores capped at 8), 1 = the calling thread only (a host rendering several frames in parallel, or with its own pool),
N = up to N (at most 8). `pakon_render --threads N`, `e2e.py --threads N` and `colour_bench <roll> [n] [rotation] [threads]` take it too.
The results do not depend on it: e2e on the five rolls on disk (42 frames, 80 adjusted renders, 7 AnselOrientation 0 renders) gives 0
differing at threads=1 and at threads=0, and `xarch_check.sh` (arm64 twice, x86_64 under Rosetta) 8 files identical.

Render on the calling thread only (threads = 1), 2026-10-15, M2 Max, Release, machine loaded (load average 8-10), rotation 270:
**0.354 s** per 2000 x 3047 frame (threads = 0: 0.165 s; analysis 1.74 s / 1.76 s). Still 2.8x inside the 1 s target without any
worker thread.

### Where the time goes now (macOS `sample`, before the change)

* Render (before): `pkc_nra_apply` (noise reduction) ~93 %, `pkc_icc_eval` ~4 %, falloff and scene LUT ~2 %. After it,
  the ICC and falloff share is larger; none is a hot spot.
* Analysis: `pkc_flesh_exp1000` (the exact exp in the flesh probability) ~97 %, ~40 ms per scene.

### Speed-ups proposed, not applied (all bit-exact: Kodak's per-pixel / per-scene math is independent)

1. Analysis: scenes are independent once the roll config is loaded, so one thread per scene (or per scene chunk) divides
   the 2.4 s by the core count. The sba-instance ordering rule (Task 19 M7) concerns which result feeds exposure, not
   computation order.
2. `pkc_flesh_exp1000`: Kodak's exp is reproduced exactly (double, PC53); a table of the argument values actually
   reached would be bit-exact but needs care; threading (1) is the safer win.
3. `pk_colour_render` on different frames is thread-safe (handles are read-only), so a multi-frame export can run frames in
   parallel today with no change.

## Determinism

`sh core/tests/colour/xarch_check.sh [roll_dir]` builds `pakon_render` for arm64 and for x86_64
(`-DCMAKE_OSX_ARCHITECTURES=x86_64`, run under Rosetta), renders the e2e roll r4 (4 frames, 2000 x ~3000) with each and
the arm64 build twice, and compares the SHA-256 of every `f*.srgb.u8` and `f*.sb.u16` (8 files).

Result (2026-10-15): arm64 twice identical; arm64 vs x86_64 identical (all 8 files; combined hash
dd45a7d5f3ace1e96f39b32080f6f150fe06fe1432245e8e6815ccbbfb94a880). Rosetta is a cheap proxy for a real Intel Mac or
Linux build (same compiler flags, libm differs from glibc), not a replacement for the owner's R27 hardware check.
The e2e roll directories live in the /private/tmp scratch tree (restore: `lab/restore_scratch.sh`, see lab/oracle/README.md).
