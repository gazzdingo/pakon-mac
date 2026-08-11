// electron-builder afterPack — fail the build rather than ship a colour
// engine nobody can identify.
//
// WHY
// ---
// docs/62 §5.2, all verified at the time: the Go pipeline binary predated its
// own sources by three minutes; a second binary of the same size and different
// content sat beside it with identical `go version -m` buildinfo because both
// said vcs.modified=true; libpakon_color.dylib predated its .c by twenty
// hours; every one of them was untracked; and extraResources swept ../tools
// in by a `**/*` glob. So the contents of a package were a function of
// whatever native artefacts happened to be on the builder's disk, and nothing
// downstream could tell.
//
// This hook closes that. tools/build-native.sh is the only thing that writes
// tools/native-manifest.json; this refuses to package unless
//
//   1. the manifest exists, both in the repo and inside Resources/tools;
//   2. the two are the same manifest — a stale Resources/tools copy, which
//      this tree has carried before, fails here;
//   3. every artefact named in it is present in the package and hashes to
//      what the manifest says;
//   4. no source file is newer than the artefact built from it;
//   5. the artefacts carry the architecture being packaged.
//
// A build that fails loudly costs an afternoon. A build that ships a stale
// colour engine is discovered from the photographs, months later.

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function fail(lines) {
  const msg = ['', 'PACKAGING REFUSED — the native colour engine cannot be identified.', '']
    .concat(lines.map((l) => '  ' + l))
    .concat(['', '  Fix: run tools/build-native.sh, then rebuild.', ''])
    .join('\n');
  throw new Error(msg);
}

// electron-builder's Arch enum: 0=ia32, 1=x64, 2=armv7l, 3=arm64, 4=universal
const ARCH_NAMES = { 0: 'i386', 1: 'x86_64', 2: 'armv7l', 3: 'arm64', 4: 'universal' };

exports.default = async function afterPack(context) {
  const repoRoot = path.resolve(__dirname, '..', '..');
  const repoManifestPath = path.join(repoRoot, 'tools', 'native-manifest.json');

  // Where extraResources landed. macOS buries it in the bundle; the other
  // platforms put it beside the executable.
  const resourcesDir =
    context.electronPlatformName === 'darwin'
      ? path.join(
          context.appOutDir,
          `${context.packager.appInfo.productFilename}.app`,
          'Contents',
          'Resources'
        )
      : path.join(context.appOutDir, 'resources');
  const packedManifestPath = path.join(resourcesDir, 'tools', 'native-manifest.json');

  const problems = [];

  if (!fs.existsSync(repoManifestPath)) {
    fail([
      `${repoManifestPath} does not exist, so there is no record of what built`,
      'the native artefacts in tools/. Nothing may be packaged without it.',
    ]);
  }
  if (!fs.existsSync(packedManifestPath)) {
    fail([
      `${packedManifestPath} is missing from the package.`,
      'extraResources did not copy tools/native-manifest.json — check the',
      'filter list in app/package.json.',
    ]);
  }

  const repoManifest = JSON.parse(fs.readFileSync(repoManifestPath, 'utf8'));
  const packedRaw = fs.readFileSync(packedManifestPath, 'utf8');

  // (2) The stale-copy check. app/dist/.../Resources/tools has carried old
  //     copies before; if the packed manifest is not byte-identical to the
  //     repo's, the package is not the tree.
  if (packedRaw !== fs.readFileSync(repoManifestPath, 'utf8')) {
    problems.push(
      'the manifest inside the package differs from tools/native-manifest.json —',
      'Resources/tools is a stale copy. Delete app/release/ and rebuild.'
    );
  }

  const artifacts = (repoManifest.artifacts || {});
  const names = Object.keys(artifacts);
  if (names.length === 0) {
    problems.push('the manifest lists no artefacts at all.');
  }

  const wantArch = ARCH_NAMES[context.arch];

  for (const name of names) {
    const a = artifacts[name];
    const packed = path.join(resourcesDir, 'tools', a.path);

    if (!fs.existsSync(packed)) {
      // Not every artefact is meant to ship — the offline CLI is not in the
      // extraResources allow-list on purpose. Only complain about the ones
      // the app actually loads.
      if (/\.(dylib|so|dll)$/.test(name) || name === 'native-manifest.json') {
        problems.push(`${name}: listed in the manifest but absent from the package.`);
      }
      continue;
    }

    const got = sha256(packed);
    if (got !== a.sha256) {
      problems.push(
        `${name}: the copy in the package hashes ${got.slice(0, 16)}, the manifest`,
        `  says ${String(a.sha256).slice(0, 16)}. Something replaced it after the build.`
      );
    }

    // (4) staleness, against the repo copy's own sources.
    const repoCopy = path.join(repoRoot, 'tools', a.path);
    if (fs.existsSync(repoCopy)) {
      const built = fs.statSync(repoCopy).mtimeMs;
      for (const src of a.sources || []) {
        const sp = path.join(repoRoot, src);
        if (fs.existsSync(sp) && fs.statSync(sp).mtimeMs > built) {
          problems.push(`${name}: ${src} is newer than the artefact built from it.`);
        }
      }
    }

    // (5) architecture.
    if (wantArch && wantArch !== 'universal' && a.arch && a.arch !== '?') {
      const have = String(a.arch).split(/\s+/);
      if (!have.includes(wantArch)) {
        problems.push(
          `${name}: built for [${have.join(', ')}] but this package targets ${wantArch}.`,
          '  Run tools/build-native.sh --universal.'
        );
      }
    }
  }

  if (repoManifest.gitDirty) {
    // Not fatal — the owner builds from a working tree — but it must be said,
    // because a dirty tree is exactly what made the two Go binaries in
    // docs/62 §5.2 indistinguishable.
    console.warn(
      '\n  NOTE: native-manifest.json says gitDirty=true. The artefacts in this\n' +
        `  package were built from uncommitted changes on top of ${String(
          repoManifest.gitRev
        ).slice(0, 12)};\n` +
        '  the revision alone does not describe them.\n'
    );
  }

  if (problems.length) fail(problems);

  console.log(
    `  native engine verified: ${names.length} artefact(s), rev ` +
      `${String(repoManifest.gitRev).slice(0, 12)}, go ${repoManifest.goVersion}, ` +
      `archs [${(repoManifest.archs || []).join(', ')}]`
  );
};
