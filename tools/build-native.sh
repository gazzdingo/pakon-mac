#!/usr/bin/env bash
#
# build-native.sh — the only sanctioned way to produce this repo's native
# artefacts, and the only thing that writes tools/native-manifest.json.
#
# WHY THIS EXISTS
# ---------------
# docs/62 §5.2 measured the state it replaces, and every item was verified:
#
#   * tools/ansel/pipeline/pakonpipeline was built at 12:24:52 from sources
#     last edited at 12:27:44 and 12:54:00 — the binary predated its own code.
#   * pipeline_test was a second build of the same package: identical byte
#     size, different SHA-256, 1.59 M differing bytes, and `go version -m`
#     reported identical buildinfo for both because each said
#     vcs.modified=true. There was no way to tell what source produced either.
#   * tools/libpakon_color.dylib predated tools/pakon_color_c.c by ~20 hours.
#   * All of them are gitignored and untracked, and app/package.json's
#     extraResources sweeps ../tools in by a `**/*` glob — so the contents of
#     a package were a function of whatever happened to be on the builder's
#     disk.
#
# A build that can ship a stale colour engine is worse than one that fails, so
# this script records what it built, from which revision, with which toolchain,
# and the loaders refuse anything the manifest does not vouch for
# (tools/pakon_colour_go.py:_verify_against_manifest) — as does packaging
# (app/build/afterPack.js).
#
# USAGE
#   tools/build-native.sh                 # every artefact, this machine's arch
#   tools/build-native.sh --universal     # arm64 + x86_64, lipo'd
#   tools/build-native.sh --check         # verify the manifest, build nothing
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PIPELINE="$HERE/ansel/pipeline"
PYPIPE="$HERE/ansel/python-pipeline"
MANIFEST="$HERE/native-manifest.json"

UNIVERSAL=0
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --universal) UNIVERSAL=1 ;;
    --check)     CHECK_ONLY=1 ;;
    -h|--help)   sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "build-native.sh: unknown argument $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '  %s\n' "$*"; }
head2() { printf '\n== %s\n' "$*"; }
die()  { printf 'build-native.sh: %s\n' "$*" >&2; exit 1; }

sha() { shasum -a 256 "$1" | awk '{print $1}'; }

# --- toolchain, pinned and recorded --------------------------------------
# docs/62 §5.3.3: tools/ansel/pipeline/go.mod requires go 1.25.0 and the
# installed toolchain here is 1.24.4. That builds today only because
# GOTOOLCHAIN=auto already fetched 1.25.0 into the module cache; on a
# network-isolated builder, or with GOTOOLCHAIN=local, it fails outright.
# Failing here, by name, is the point — the alternative is a package built
# with a toolchain nobody recorded.
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is not on PATH"; }
need go
need cc
need shasum

GO_WANT="$(awk '/^go /{print $2}' "$PIPELINE/go.mod")"
GO_HAVE="$(go env GOVERSION | sed 's/^go//')"
GO_TOOLCHAIN="$(cd "$PIPELINE" && go version | awk '{print $3}')"

verify_manifest() {
  [ -f "$MANIFEST" ] || die "no $MANIFEST — run tools/build-native.sh"
  python3 - "$MANIFEST" <<'PY'
import hashlib, json, os, sys
man = json.load(open(sys.argv[1]))
root = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[1])))
tools = os.path.dirname(os.path.abspath(sys.argv[1]))
bad = []
for name, a in (man.get("artifacts") or {}).items():
    p = os.path.join(tools, a["path"])
    if not os.path.exists(p):
        bad.append(f"{name}: missing at {p}")
        continue
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if h != a["sha256"]:
        bad.append(f"{name}: sha256 {h[:16]} != manifest {a['sha256'][:16]}")
        continue
    # Staleness: a source newer than the artefact means the artefact is not
    # what the source says. This is the check that would have caught
    # pakonpipeline predating main.go.
    art_mtime = os.path.getmtime(p)
    for s in a.get("sources", []):
        sp = os.path.join(root, s)
        if os.path.exists(sp) and os.path.getmtime(sp) > art_mtime:
            bad.append(f"{name}: {s} is newer than the built artefact")
if bad:
    print("\n".join("  " + b for b in bad))
    sys.exit(1)
print("  manifest verified: %d artefact(s), rev %s%s"
      % (len(man.get("artifacts") or {}), man.get("gitRev", "?"),
         " (dirty)" if man.get("gitDirty") else ""))
PY
}

if [ "$CHECK_ONLY" = 1 ]; then
  head2 "checking $MANIFEST"
  verify_manifest
  exit 0
fi

head2 "toolchain"
say "go.mod wants go $GO_WANT; the installed toolchain is go $GO_HAVE"
say "building with $GO_TOOLCHAIN"
say "cc: $(cc --version | head -1)"

ARCHS=(arm64)
if [ "$UNIVERSAL" = 1 ]; then ARCHS=(arm64 x86_64); fi
say "target arch(s): ${ARCHS[*]}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- 1. the Go colour engine, as a c-shared dylib ------------------------
# This is the phase-2 boundary. tools/pakon_colour_go.py loads it by ctypes
# and refuses to load one the manifest does not describe.
head2 "libpakon_colour_go (Go c-shared)"
GO_DYLIB="$HERE/libpakon_colour_go.dylib"
parts=()
for a in "${ARCHS[@]}"; do
  goarch=arm64; [ "$a" = x86_64 ] && goarch=amd64
  out="$TMP/libpakon_colour_go.$a.dylib"
  say "arch $a (GOARCH=$goarch)"
  ( cd "$PIPELINE" && CGO_ENABLED=1 GOARCH="$goarch" \
      CGO_CFLAGS="-arch $a" CGO_LDFLAGS="-arch $a" \
      go build -trimpath -buildmode=c-shared -o "$out" . ) \
    || die "c-shared build failed for $a"
  parts+=("$out")
done
if [ ${#parts[@]} -gt 1 ]; then
  lipo -create -output "$GO_DYLIB" "${parts[@]}"
else
  cp "${parts[0]}" "$GO_DYLIB"
fi
codesign -f -s - "$GO_DYLIB"
cp "$TMP/libpakon_colour_go.${ARCHS[0]}.h" "$HERE/libpakon_colour_go.h" 2>/dev/null || true
say "-> $GO_DYLIB  ($(lipo -archs "$GO_DYLIB"))"

# --- 2. the offline CLI, from the same package ---------------------------
# One artefact, one name. pipeline_test is not rebuilt: it was an untracked
# duplicate build with a misleading name (docs/62 §5.3.7) and it is removed
# below rather than managed.
head2 "pakonpipeline (Go CLI)"
CLI="$PIPELINE/pakonpipeline"
parts=()
for a in "${ARCHS[@]}"; do
  goarch=arm64; [ "$a" = x86_64 ] && goarch=amd64
  out="$TMP/pakonpipeline.$a"
  ( cd "$PIPELINE" && CGO_ENABLED=1 GOARCH="$goarch" \
      CGO_CFLAGS="-arch $a" CGO_LDFLAGS="-arch $a" \
      go build -trimpath -o "$out" . ) || die "CLI build failed for $a"
  parts+=("$out")
done
if [ "${#parts[@]}" -gt 1 ]; then
  lipo -create "${parts[@]}" -output "$CLI"
else
  cp "${parts[0]}" "$CLI"
fi
say "-> $CLI  ($(lipo -archs "$CLI"))"
if [ -e "$PIPELINE/pipeline_test" ]; then
  rm -f "$PIPELINE/pipeline_test"
  say "removed pipeline_test (untracked duplicate build, docs/62 §5.3.7)"
fi

# --- 3. the C kernels Python still calls ---------------------------------
head2 "libpakon_color (C stage-2 kernel)"
C_DYLIB="$HERE/libpakon_color.dylib"
archflags=(); for a in "${ARCHS[@]}"; do archflags+=(-arch "$a"); done
cc -O2 -shared -fPIC "${archflags[@]}" -o "$C_DYLIB" "$HERE/pakon_color_c.c" -lm
codesign -f -s - "$C_DYLIB"
say "-> $C_DYLIB  ($(lipo -archs "$C_DYLIB"))"

head2 "libpakon_ansel (C balance apply)"
A_DYLIB="$PYPIPE/libpakon_ansel.dylib"
cc -O2 -shared -fPIC "${archflags[@]}" -o "$A_DYLIB" "$PYPIPE/pakon_ansel_c.c" -lm
codesign -f -s - "$A_DYLIB"
say "-> $A_DYLIB  ($(lipo -archs "$A_DYLIB"))"

# --- 4. stamp the manifest ------------------------------------------------
head2 "native-manifest.json"
GIT_REV="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
GIT_DIRTY=false
if ! git -C "$REPO" diff --quiet 2>/dev/null || \
   ! git -C "$REPO" diff --cached --quiet 2>/dev/null; then
  GIT_DIRTY=true
fi

GO_SOURCES="$(cd "$PIPELINE" && ls *.go | sed 's#^#tools/ansel/pipeline/#' | tr '\n' ' ')"

python3 - "$MANIFEST" "$HERE" "$GIT_REV" "$GIT_DIRTY" "$GO_TOOLCHAIN" \
        "$(printf '%s' "${ARCHS[*]}")" "$GO_SOURCES" <<'PY'
import datetime, hashlib, json, os, subprocess, sys

manifest, tools, rev, dirty, gover, archs, go_sources = sys.argv[1:8]
repo = os.path.dirname(tools)


def entry(rel_to_tools, sources):
    p = os.path.join(tools, rel_to_tools)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    try:
        arch = subprocess.run(["lipo", "-archs", p], capture_output=True,
                              text=True).stdout.strip()
    except Exception:
        arch = "?"
    return os.path.basename(p), {
        "path": rel_to_tools,
        "sha256": h,
        "bytes": os.path.getsize(p),
        "arch": arch,
        "sources": sources,
    }


gos = [s for s in go_sources.split() if not s.endswith("_test.go")]
arts = dict([
    entry("libpakon_colour_go.dylib", gos + ["tools/ansel/pipeline/go.mod"]),
    entry("ansel/pipeline/pakonpipeline", gos + ["tools/ansel/pipeline/go.mod"]),
    entry("libpakon_color.dylib", ["tools/pakon_color_c.c"]),
    entry("ansel/python-pipeline/libpakon_ansel.dylib",
          ["tools/ansel/python-pipeline/pakon_ansel_c.c"]),
])

doc = {
    "_comment": (
        "Written only by tools/build-native.sh. Loaders and the Electron "
        "afterPack hook refuse any native artefact this file does not vouch "
        "for; see docs/62 section 5. Do not hand-edit."),
    "manifestVersion": 1,
    "builtAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "gitRev": rev,
    "gitDirty": dirty == "true",
    "goVersion": gover,
    "archs": archs.split(),
    "artifacts": arts,
}
with open(manifest, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=2, sort_keys=True)
    fh.write("\n")
print("  wrote %s (%d artefacts, rev %s%s)"
      % (manifest, len(arts), rev[:12], " DIRTY" if dirty == "true" else ""))
PY

head2 "verify"
verify_manifest

if [ "$GIT_DIRTY" = true ]; then
  cat >&2 <<'EOF'

  NOTE: the working tree is dirty, so gitDirty=true in the manifest and the
  revision recorded above does not fully describe these binaries. That is
  exactly the condition that made pakonpipeline and pipeline_test
  indistinguishable (docs/62 §5.2). It is recorded rather than hidden; commit
  before building anything you intend to ship.
EOF
fi
