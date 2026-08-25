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

2. **The FOS orderFpo source** (docs/74 §66, closed further by §72). The
   ported `fos_analyze_roll`/`fos_calc_results` == `SbaCalcFosResults @
   0x1028f570` (Unicorn-golden), but the per-frame orderFpo writer is
   `0x1028b8d0` — a *different* function (13 args, confirmed via full-body
   read + two independent caller sites, §72.2). §72 went further than the
   Unicorn-diff gate: `0x1028b8d0`'s own top-level code, on the case that
   provably fires live (mode/arg 3 == 0 at both real call sites, §72.3),
   does **not** write the `pref_data+0/2/4` orderFpo triple at all — it
   writes one unrelated word at `+0x3e`, derived from other `pref_data`
   fields, not from FOS statistics. Arg 5 (the input its shared body opens
   Y/C1/C2 on) is a copy of the *same* DPI blob Preference reads (or
   all-zero), not FOS dens/pixel data (§72.4). A Unicorn diff against
   `fos_analyze_roll` is therefore not currently well-posed — it would
   require inventing the 8 unread helpers' semantics, which of two
   observed arg-5 provenances is "normal," and arg 3/8/9's exact live
   value. **`fos_analyze_roll` is not shown to reproduce `0x1028b8d0`,
   and `0x1028b8d0`'s directly-observed output is not the orderFpo triple
   at all.** Next step is a live capture, spec'd precisely in docs/74
   §72.7 (hook `0x1028b8d0` entry+return, dump all 13 args + before/after
   `pref_data`), not more static reading or an invented Unicorn harness.

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

**Status as of the v21 capture (`live_hooks_20260817-112602.jsonl`, md5
`98aa01dbad6014caf63425f14f8e487a`, docs/74 §73): steps 1-3 below are all
answered. Step 4 is now gated on one new, well-scoped question.**

1. ~~**v20 capture**~~ — **DONE.** v21 is a strict superset of v20 (v20's
   source was merged before v21 was built on top of it, so the v21 binary
   carries v20's own `shifts_3a38_arg1` dump — verified directly in the
   compiled DLL). One capture answered both. Result: the third `getShifts`
   **does** fire (18 calls / 6 frames = 3 per frame, where v19 saw only 2).
2. ~~**Find the second `+0x3a38` writer**~~ — **CLOSED, negatively.**
   §71 showed statically there is no second *writer*; §73.5 now shows
   empirically that the field the third `getShifts` reads is **`(0,0,0)` on
   all 12 calls where it is readable** (and unmapped on the other 6). It is
   not Δ's source. The candidate is eliminated, not deferred.
3. ~~**§66 closed the other way**~~ — **REOPENED AND RESOLVED THE OTHER WAY
   AGAIN, live.** §73.2: `0x1028b8d0` **is** the per-frame orderFpo writer,
   confirmed 12/12 with no counterexample (blob is `(0,0,0)` at every
   `arg3==0` entry, non-zero and per-scene-distinct by the time Preference
   reads the same address). §72's own top-level static read still stands —
   the write happens inside one of the **8 helper subroutines** §72.3
   explicitly flagged as unread. Also: §72.3's "arg 3 == 0 at both call
   sites" is **refuted** — 12 of 24 real calls run `arg3 == 1` (§73.3), so
   case 1 is live code, and a Unicorn harness built on that assumption
   would have run the wrong switch case half the time.

4. ~~**Find which of the 8 helpers writes the triple**~~ — **CLOSED. There
   is no helper to find: the write is at `0x1028b8d0`'s own top level**
   (docs/74 §74). Three instructions, in the case-0 shared body:

   ```
   0x1028c2be   mov word [ebp],     ax    ; orderFpo Y   ax = [var_28h]+[var_dch]
   0x1028c2b6   mov word [ebp + 2], cx    ; orderFpo U   cx = [var_2ch]+[var_64h]
   0x1028c2c2   mov word [ebp + 4], dx    ; orderFpo V   dx = [var_68h]+[var_30h]
   ```

   `ebp` is reloaded from arg 12 (`pref_data`) at `0x1028c208` just before
   this block. The same three values are also stored to `+6/+8/+0xa`, which
   is how this was confirmed: that duplication is a prediction the existing
   v21 capture already answers, and it holds **12/12** on real Preference
   observations. §73.2's "it must be in a helper" inference is withdrawn —
   it had inherited §72.3's static negative without re-deriving it, and one
   grep of the function body for `[ebp+N]` stores refuted it. No further
   capture is needed for this question.

5. ~~**Trace the six locals into real inputs**~~ — **DONE for five of six;
   the sixth is a named, well-scoped capture request** (docs/74 §76). The
   write decomposes as

   ```
   orderFpo.Y = fos_opening_axes(arg5).Y  + L[-0x200]      <-- UNRESOLVED
   orderFpo.U = fos_opening_axes(arg5).C1 + out[+4]
   orderFpo.V = fos_opening_axes(arg5).C2 + out[+8]
   ```

   * The three constants **are** the existing `fos_opening_axes` port,
     unchanged: `fos_opening_axes(879,1250,1386) == (2029, 96, 359)`, and
     `arg5` is DPI-static, so those terms are fixed for the whole roll
     (§76.3). Required per-frame deltas, from the six known triples:
     Y `+50/+12/−115/−298/+204/+27`, U `−38/−24/−48/−42/−31/−29`,
     V `+106/+88/+96/+92/+72/+85`.
   * **U and V are fully derived** (§76.4): `out[+4]`/`out[+8]` come from
     `fcn.1028ae00`'s arg 6 out-struct, and on the live `arg3==0` path that
     function's own top level computes a *weighted mean chroma residual*
     over 864 dens samples — a 50×83 `int8` weight table indexed by
     `(c1/16+24, c2/16+41)`, a two-clause sample-selection test, and a
     round-half-away-from-zero divide by `864*100` or `count*100`. **No
     helper emulation is needed.** Full pseudocode with per-instruction
     citations is in §76.4.
   * **Y is not derived** (§76.6). `L−0x200` is a frame local that no
     argument carries and that `0x1028b8d0` never writes; by elimination
     over every stack pointer that leaves the frame, it is
     `((int32_t*)&buf_at_−0x258)[22]`, filled by `fcn.102ac310` from a
     record list hanging off **arg 6** — the argument §75.1 refuted as
     `scene+0x5978` and which has never been dumped. **All** of Y's
     per-frame variation lives in this one term.
   * **Two bit-exact live confirmations** of the branch analysis, on v21
     data recorded before the claim existed: `pref_data+0x5e == 200`
     (12/12) and the vendor's own Newton isqrt reproducing
     `pref_data+0x2a` from `+0x24`/`+0x26` (6/6, where `math.isqrt` gets
     two of the six wrong by one) (§76.5).

   **NEXT on this thread:** the capture list in §76.7. Highest value by far
   is hooking **`0x1028ae00` at entry and logging its raw `stack_dwords`** —
   its `arg 9` *is* `L−0x200`, so one dword per call closes Y outright.
   Note also that §75.2's v22 sizes for `arg0` (`0x40`) and `arg7` (`0x40`)
   are far too small: U/V need `arg0+0x1440` for `0x1440` bytes and `arg7`
   for `0x1036` bytes, plus `arg11+0xc20` for `0x360` bytes and
   `arg11+0x48`.

6. **Δ's source is open** (docs/74 §73.5/§73.6). Δ is measured, real,
   per-frame, and uniform to within one code (−43, +32, +7, +34, −68, +12
   across the six captured frames), but the field §69/§71 nominated reads
   `(0,0,0)` on every readable observation and is eliminated. Shape hint
   for whoever picks it up: it is a *luma-only* offset applied after
   `setshifts_12`, so a scene-level brightness/exposure aim is a likelier
   source than anything remaining in the `+0x3a38` chain.

7. **Wire it** — `pakon_ansel.py` per-frame orderFpo →
   `preference_shifts_hiNN(hi=0, lo=0, non_flash_adj=cmm)` → `setshifts_12`
   → `+Δ`, then re-render and diff against the real vendor output. Gated on
   5 (and on 6 for the Δ term specifically). **Architectural note from
   §73.7 that affects how this is wired:** the whole balance chain is a
   **roll-wide pre-pass** — every `orderFpo`/Preference/`getShifts` call in
   the capture happens *before* the first per-frame render begins, with all
   six scenes computed up front. The port should compute balance for the
   whole roll first, then render, not interleave per frame.
