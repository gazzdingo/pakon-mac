#!/bin/sh
# Cross-architecture determinism check (Task 23, run by hand; needs Rosetta): builds pakon_render for x86_64 and arm64 with
# the project's flags, renders one corpus roll with each (and the arm64 build twice) and compares the SHA-256 of every
# output file. usage: sh core/tests/colour/xarch_check.sh [roll_dir]   (default: the e2e scratch roll r4)
set -e
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); R=${1:-/private/tmp/pakon_re_v2/work/e2e/rolls/r4}; T=${TMPDIR:-/tmp}/pk_xarch
CM=${CMAKE:-/tmp/cmvenv/bin/cmake}
rm -rf "$T"; mkdir -p "$T/a1" "$T/a2" "$T/x"
for a in arm64 x86_64; do
  $CM -S "$ROOT/core" -B "$T/b_$a" -DCMAKE_OSX_ARCHITECTURES=$a >/dev/null
  $CM --build "$T/b_$a" --target pakon_render >/dev/null
done
"$T/b_arm64/pakon_render" "$R" "$T/a1" >/dev/null
"$T/b_arm64/pakon_render" "$R" "$T/a2" >/dev/null     # repeat run, same binary
"$T/b_x86_64/pakon_render" "$R" "$T/x" >/dev/null     # runs under Rosetta
sums() { (cd "$1" && shasum -a 256 f*.srgb.u8 f*.sb.u16); }
sums "$T/a1" > "$T/a1.sum"; sums "$T/a2" > "$T/a2.sum"; sums "$T/x" > "$T/x.sum"
cmp "$T/a1.sum" "$T/a2.sum" && echo "repeat run (arm64 twice): identical"
# RE 39: PSI's scaled save too (double-precision resample: no FMA, same operation order on both architectures)
mkdir -p "$T/s1" "$T/sx"
for sz in 1,1536,1024 1,3600,2400 2,800,1200; do
  "$T/b_arm64/pakon_render" "$R" "$T/s1" --frames 0,1 --save-size $sz >/dev/null && (cd "$T/s1" && shasum -a 256 f*.srgb.u8 | sed "s/^/$sz /") >> "$T/s1.sum"
  "$T/b_x86_64/pakon_render" "$R" "$T/sx" --frames 0,1 --save-size $sz >/dev/null && (cd "$T/sx" && shasum -a 256 f*.srgb.u8 | sed "s/^/$sz /") >> "$T/sx.sum"
done
cmp "$T/s1.sum" "$T/sx.sum" && echo "scaled saves, arm64 vs x86_64: identical ($(wc -l < "$T/s1.sum" | tr -d ' ') files)"
cmp "$T/a1.sum" "$T/x.sum" && echo "arm64 vs x86_64: identical ($(wc -l < "$T/a1.sum" | tr -d ' ') files)"
