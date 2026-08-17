# 76 — Per-frame balance handover: where the colour port stands, and how to continue it

This is the pickup document for the per-frame balance work. It records what is
bit-exact-verified, what is open, and — most importantly — the exact working
method that produced the findings, so a fresh agent can continue in the same
style rather than re-derive the discipline.

The detailed evidence lives in `docs/74-washed-out-tone-chain-architecture-and-dmin-methodology.md`
§62–§69 (every claim there is tiered). This doc is the map, not the archive.

---

## 1. The goal

Byte-for-byte port of the Pakon F-135 colour science, focused on the
per-frame **balance** stage that drives the "not enough red / washed-out"
defect. The pipeline under investigation is, per frame:

```
FOS orderFpo (scene+0x38a2, opponent Y/U/V)
  → Preference (0x1028c780, mode=0)          → A (+0x3a38)
  → setShifts (0x10100260) (1,2) combine     → setshifts_12(A,A)
  → + Δ (per-frame uniform luma offset)       → scene+0x4b6
  → balance LUT clamp(i + shift, 0, 4095)
```

The live reference DLL is `/Users/guy/pakon-windows-repair/COM-SERVER/PakonIMAu.dll`
(sha256 `0ede8d9813af4ee95dddd85e5adc495a27f014a8fd4817cfbc3b3b1e107f511f`) —
the same build `pablonavarrob/pakon-tlx-macos` uses, so that project is a
viable ground-truth source too.

---

## 2. What is verified, what is open

### Verified (bit-exact against live capture, and/or Unicorn-golden)

1. **The Preference chain is fully reproduced** (docs/74 §64/§67/§68). The
   live Preference runs **mode=0** (confirmed by v18: `scene+0x5074`=0), and:
   - `aim_y = param0 = scene+0x38a2[0]` = orderFpo **Y**
   - `aim_uv = scene+0x38a2[+2]/[+4]` = orderFpo **U/V** (the `hi=0`
     else-branch reads the *param* struct `[ebp+8]`, **not** the blob `fpo`)
   - the chroma-aim scale is `cmm` (blob+0x30) = 1000
   
   `preference_shifts_hiNN(hi=0, lo=0, param0=orderFpoY, param_uv=orderFpoUV,
   non_flash_adj=1000) == +0x3a38` bit-exact, 6/6 frames. The `hi=0`
   else-branch bug (`fpo[1]/fpo[2]` instead of `param[2]/param[4]`) is **fixed**
   in `pakon_sba_preference.py` and Unicorn-pinned (golden cases 21–23).

2. **`setshifts_12` = the (1,2) combine** (Unicorn-golden,
   `pakon_setshifts_golden.py`).

3. **The balance shift is `setshifts_12(A,A) + Δ`**, Δ a per-frame uniform
   (luma-only) offset, bit-exact (docs/74 §63/§69).

### Open

1. **Δ's source** (docs/74 §69). Δ is added in the setShifts caller
   (`0x10101xxx`) at `0x10102033..57` from a **third** getShifts call
   (`0x10101ff6`) that reads a **different** `+0x3a38` field
   (`*(arg1+0x10)+0x3a38`, arg1=`&[esp+0x30]`). Two sub-questions remain:
   (a) does that third call actually fire live (v19 showed only 2
   `sba_get_shifts`/frame), and (b) **what writes that second `+0x3a38`
   field**. v20 (built, un-captured at handoff) dumps the real read to answer
   (a).

2. **The FOS orderFpo source** (docs/74 §66). The ported
   `fos_analyze_roll`/`fos_calc_results` == `SbaCalcFosResults @ 0x1028f570`
   (Unicorn-golden), but the per-frame orderFpo writer is `0x1028b8d0` — a
   *different* function (13 args, 8 helpers, no overlap with the ported
   leaves). Not yet proven that the ported FOS reproduces the live per-frame
   orderFpo. Gate: Unicorn-diff `0x1028b8d0`'s OUT vs `fos_analyze_roll`, or a
   live capture of the FOS inputs + `scene+0x38a2`.

3. **The wiring.** `pakon_ansel.py:280 preference_shift_words` still uses the
   DPI-static `preference_shifts_from_dpi_fields` (mode 0x11). It must become:
   per-frame orderFpo → `preference_shifts_hiNN(hi=0, lo=0, param0, param_uv,
   non_flash_adj=cmm)` → `setshifts_12` → `+Δ`. Blocked on (1) and (2).

Also flagged-not-fixed: `preference_aim_uv`'s `hi=0x20` (neu) and `hi=0x40`
(lo42/hi44) branches read from the *param* struct, not the blob — the port's
`neu`/`lo42`/`hi44` are wrong for those two modes, but mode=0 never reaches
them.

---

## 3. How to keep working — the method (this is the "prompt")

Use this as the working contract. It is the single most important part of the
handover: every finding above came from following it, and every near-miss in
this repo's history came from not.

```
You are reverse-engineering the Pakon F-135 colour pipeline to a byte-for-byte
port, verified against the real vendor DLL under Unicorn and against live
hardware captures. Work to this standard, in this order:

1. EVIDENCE HIERARCHY — the only thing that counts is bit-exactness.
   Tier 1 (strongest): live Unicorn emulation of the real DLL, diffed
     bit-exact against the port's own output for identical input.
   Tier 2: live hook capture on real hardware (real DLL functions hooked,
     args/buffers dumped), diffed bit-exact against the port.
   Tier 3: static disassembly at REAL function boundaries (af/pdf, never raw
     pD byte ranges) — triage only, never a claim on its own.
   "Looks right" / "structurally matches" is NOT a finding. A suggestive
   function name is not a finding until it clears the bar. Read whole function
   bodies; do not infer from names (several near-misses were dead code).

2. NEVER INVENT. No fabricated hardware measurements, no guessed calibration
   values, no plausible-but-unverified formulas. If a measurement isn't
   available (e.g. hardware down), say so and pivot to real file/capture
   evidence. Every port change must be backed by Tier 1 or Tier 2 evidence.

3. THE CAPTURE-DECODE-DIFF LOOP — the fastest path to a finding.
   (a) Add a dump to the live hook (tools/re/live_hooks/win_inject/
       hookcore_real_table.c g_extraDumps[]), build with ./build.sh (must show
       "only KERNEL32.dll", 29 hooks sync, "selftest ALL PASS"), upload the
       hookdll+injector to the drop server.
   (b) Decode the dumped buffer against the known structures.
   (c) Diff against the port's own output for the same input. Bit-exact
       mismatch/agreement is the signal.

4. TRACE THE DATA, NOT THE NAMES. To find where a value comes from: find every
   write to that offset (search immediates; if none, the write is via a
   pointer — follow the register); find every read; the gap between write and
   read is where a transformation lands. To find a function's args: read the
   verified golden-test harness's frame layout and cross-check the DLL's
   [ebp+N] reads against it — the golden harness is the authority on the
   signature, not a guess.

5. DOCUMENT EVERYTHING, TIERED. Every finding — positive AND negative — goes
   into docs/74 with its evidence tier stated plainly. A ruled-out hypothesis
   is recorded as clearly as a confirmed one. Cite DLL addresses, capture
   hashes, and the exact table rows. Re-grep the section number before writing
   (collision hazard when multiple agents touch the same doc).

6. COMMIT SMALL. One real finding or one real fix per commit, evidence-cited
   message. Push to branch `per-frame-balance` (never main/master). Scratch
   RE scripts live in /tmp/pakon_re/ and are NOT committed.

7. VERIFY THE FIX, THEN RE-RENDER. After wiring, re-run the golden tests
   (PYTHONPATH=tools/ansel/python-pipeline python3 -m <module>_golden
   /Users/guy/pakon-windows-repair/COM-SERVER/PakonIMAu.dll) and the render
   regression (python3 tools/test_render_f135.py), then re-render
   scan-20260812-091633.bin to confirm the red cast closes.
```

---

## 4. Tooling map

- **Live hooks** — `tools/re/live_hooks/win_inject/`. `hookcore_real_table.c`
  has `g_extraDumps[]` (the dump specs) and the hook table. Dump kinds in
  `hookcore.h`/`hookcore.c`: `EXTRA_DUMP_STACK_PTR` (sp[idx]),
  `EXTRA_DUMP_DEREF_PTR` (*(sp[idx]+off)), `EXTRA_DUMP_THIS_OFFSET` (ecx+off),
  `EXTRA_DUMP_THIS_DEREF_OFFSET` (*(ecx+idx)+off),
  `EXTRA_DUMP_STACK_PTR_OFFSET` (sp[idx]+off),
  `EXTRA_DUMP_STACK_DEREF2_OFFSET` (*(sp[idx]+off)+off2).
  `build.sh` cross-compiles + runs a static sanity pass; `check_table_sync.py`
  keeps `hookcore_real_table.c` ⇄ `agent.js` hook lists in sync.
- **Unicorn golden tests** — `tools/ansel/python-pipeline/*_golden.py`
  (`pakon_preference_golden.py`, `pakon_setshifts_golden.py`,
  `pakon_fos_golden.py`, `pakon_postbalance_golden.py`). Run with the DLL path
  as argv[1].
- **The port** — `tools/ansel/python-pipeline/pakon_sba_preference.py`
  (`preference_shifts_hiNN`, `preference_aim_uv`, `preference_aim_y`),
  `pakon_sba_apply.py` (`setshifts_12`), `pakon_fos.py` (`fos_analyze_roll`,
  `fos_calc_results`), `pakon_ansel.py` (the render wiring,
  `preference_shift_words` at line ~280).
- **Live captures** — `/tmp/pakon_re/live_hooks_*.jsonl`:
  v14 `…-180542`, v15 `…-185402`, v16 `…-191735` (md5 `6f8892…`),
  v17 `…-193632` (md5 `a92a7b…`), v18 `…-091509` (md5 `3518fb9e…`),
  v19 `…-110241` (md5 `740bfe5e…`). Drop server `http://192.168.86.67:8000/`
  (intermittent; owner runs scans on the XP box).
- **DLL** — `PakonIMAu.dll` sha256 `0ede8d98…`, `TLB.dll` sha256 `5866ec56…`.

---

## 5. Immediate next steps (in order)

1. **v20 capture** (already built; un-captured at handoff) — the new
   `shifts_3a38_arg1` dump (`*(arg1+0x10)+0x3a38`) settles whether the third
   getShifts fires and reveals the Δ's value directly. Hookdll_v20
   `553b05ee…`, injector_v20 `28c54e93…`.
2. **Find the second `+0x3a38` writer** — the Δ's source field. Trace who
   writes that offset in the scene (search write sites; likely in the setShifts
   caller or a FOS/pass1 function).
3. **Close §66** — prove (or refute) that `fos_analyze_roll` per-frame
   reproduces the live `scene+0x38a2` orderFpo (Unicorn-diff `0x1028b8d0` OUT,
   or a FOS-input capture).
4. **Wire it** — `pakon_ansel.py` per-frame orderFpo → `preference_shifts_hiNN
   (hi=0, lo=0, non_flash_adj=cmm)` → `setshifts_12` → `+Δ`, then re-render and
   diff against the real vendor output.
