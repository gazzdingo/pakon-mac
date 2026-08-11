# vendor/ — third-party files

Nothing in this directory is our work. It is here so the pipeline resolves its
data with no flags on a fresh checkout.

## `vendor/ansel/` — Kodak/Pakon Ansel colour data

**These files are Kodak's / Pakon's, not ours.** We did not write them, we do
not own them, and no licence to redistribute them has been granted to us. They
are copied verbatim from a Pakon **F-X35 COM SERVER** installation (the driver
package for the Pakon F-135 / F-235 / F-335 film scanners, a discontinued Kodak
product line). File dates run 2002–2006.

The directory reproduces the layout of that installation exactly, so path
resolution stays trivial:

```
vendor/ansel/
  Config/ColorCorrection/                 # 22 files
      _ClientColNegLut.txt, _ClientColNegMat.txt   stage-2 colour-neg LUT + matrix
      rpd.pf, srgb.pf, romm.pf, unity.pf           ICC-style colour profiles
      sat*.pf, warm_bw*.pf, cold_bw.pf, sepia*.pf  abstract tone profiles
      defaults.ini                                 DX film-product table
  anselinstalldir/dataPathItems/          # 91 files
      sba/       SbaDPI/*.dpi + sba.map, Pcode/, Sfs/   scene-balance params
      shasta/    shasta-*.dpi + shasta.map              tone-scale aims
      fugc/      *.lut + fugc-lutMap.map                film undercolour LUTs
      profile/   Rpd2Pcs_*.pf, Srgb_v2.pf + profile.map ICC profiles
      common/    common-sraFwdLut-*.lut, luts6_*.lut    SRA + 3-band LUTs
      color/, contrast/, SCPLut/                        selector + adjust tables
```

Roughly 3.8 MB, 113 files: 40 `.dpi` parameter files, 22 `.lut` tables,
21 `.pf` profiles, 8 `.map` selector files, plus the `Config/ColorCorrection`
text tables and the `sba/Pcode` and `sba/Sfs` blobs.

Only the subdirectories the pipeline actually reads were copied. The rest of a
real install (`area/`, `deRender/`, `reRender/`, `pnr/`, `noiseTable/`, and the
DLLs) is not here.

### Why they are in the repo

The renderers are a reimplementation of the vendor pipeline, and their output is
only meaningful against the vendor's own tables. Without these files
`tools/pakon_decode.py` and `tools/ansel/pipeline/` cannot resolve a profile and
will not run.

### Overriding them

The in-repo copy is only the default. Both engines accept:

- `--data-dir` / `--ansel-root` (Python), `-ansel-root` (Go) — highest priority.
- `PAKON_FX35_ROOT` — point at a real `F-X35 COM SERVER` directory to use an
  original install instead of this copy.

### If you own the rights to this material

If you are the rights holder and would rather these files were not distributed
here, open an issue and they will be removed; the loaders already work against
an external install via `PAKON_FX35_ROOT`.

## `vendor/FX35/` — F-X35 driver source

Third-party driver source, kept for reference. The upstream repository ships no
`LICENSE` file. Also not ours.
