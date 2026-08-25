#!/usr/bin/env python3
"""FLESH (skin-tone) capability: the per-frame RPD Delta.

Scope and evidence tier — read this before using anything here.
====================================================================

`docs/74` §178 measured a per-frame, channel-uniform additive term `Delta`
at the shift-LUT builder's own stack arguments, and §180 identified it as
the FLESH shift: `AnsFleshCapability::getShifts` (`fcn.100f7560`) copies
`FleshImpl+0x0c` = `m_fleshAdjust`, which `analyzePostBalance`
(`fcn.100fdc40`) adds to the shift triple at `arg1+0x0a` with the three
16-bit `add`s at `0x100fe471 / 0x100fe479 / 0x100fe47d`.

`m_fleshAdjust` is produced by the adjust calculator **`fcn.10270280`**
(6451 bytes, `PakonIMAu.dll` md5 `eea9dcf78ee21d4f7c515a6c2512242d`), called
once from `AnsFleshCapabilityImpl::analyze` at `0x101c9d12` (the *only*
caller in the image — 12 cdecl args, `add esp, 0x30`).

This module ports **two** things, at two different evidence tiers:

1. `FleshParams` / `parse_flesh_dpi` — the DPI parameter layout, derived by
   reading `fleshParameterReader::scanParameterT`'s driver `fcn.10272380`
   (3387 bytes) instruction by instruction.  **Tier 3** (`af`+`pdf`, full
   body) for the layout; the values themselves come from the real shipped
   DPI file.

2. `flesh_delta` and its helpers — the arithmetic of `fcn.10270280`'s tail,
   `0x102714e1 … 0x1027173e`.  **Tier 1 (bit-exact)** against the real DLL:
   `pakon_flesh_golden.py` executes those very bytes under Unicorn on a
   real parameter blob and diffs the emitted `word [edi+0x30]`.

3. The **V1 flesh detector's arithmetic core** — the LST transform, the
   three axis indices and the separable skin-probability product
   (`fcn.102a1500`, `0x102a1787 … 0x102a192a`) — plus the analysis-border
   computation (`0x102706fe … 0x10270763`), the 0/10/20/255 clamp map
   (`0x102711d0 … 0x10271219`) and the reduction loop
   (`0x102712ac … 0x102714c7`).  **Tier 1 (bit-exact)** against the real
   DLL: `pakon_flesh_detector_golden.py` executes those very bytes under
   Unicorn and diffs every output.

4. The **threshold chooser** `fcn.1029ec50` (3575 B) and its helper
   `fcn.1029cad0` (545 B) — the Sobel edge mask, the 64-bin histogram, the
   15-tap smoothing, the peak/valley search and the integer threshold that
   reaches `results+0x28`.  **Tier 1 (bit-exact)** against the real DLL:
   `pakon_flesh_threshold_golden.py` runs *the whole function* under
   Unicorn — its C++ image classes, its convolutions, its `malloc`/`free`
   — and diffs the mask, all 64 histogram bins, all 64 smoothed bins, the
   threshold and the returned binary plane.

5. The **weight plane** and the **two 1-D LUT pre-passes** — the two items
   the previous three harnesses each named as the remaining gap.
   `pakon_flesh_weight_golden.py` executes all four of the following under
   Unicorn and diffs every output value:

   * `fcn.10271bc0` (`AnsFleshCapabilityImpl::analyze` @ `0x101c99f0`, the
     "Could not generate weight map" call) — a 2-D **Gaussian** weight map
     over the clip-inset region.  **Tier 1**, 3,078,017 samples.
   * `fcn.104e7880` (`.\IemPad.cpp`) — a centred **replicate** pad, which is
     what `0x1027127e` runs the weight map through to bring it up to the
     analysis image's dimensions.  **Tier 1.**
   * `fcn.1026fed0` + `fcn.10270050` — the 12-bit clamp table and the three
     `lut[i] = clamp(i + shift, 0, 4095)` shift LUTs built at `0x102707e8`
     from `fcn.10270280`'s **arg6, the shift triple itself**.  **Tier 1.**
   * the two pre-passes `0x102708ba…0x10270979` and `0x10270ab9…0x10270b69`
     that apply those LUTs to the three colour planes in place.  **Tier 1.**

6. **`fcn.10270280` AS ONE FUNCTION.**  `pakon_flesh_whole_golden.py` calls
   it at its own entry with its own twelve arguments and lets it run to its
   own `ret`, on images the vendor's own `AnsImageData::copyToIemImage`
   built and a weight map the vendor's own `fcn.10271bc0` built, and diffs
   the results struct **and** four internal buffers against
   `flesh_forward_delta` on the same pixels: 58,462 values, 0 differences.
   **Tier 1** — so the *assembly* below is no longer a tier-3 reading of
   the instruction stream.  It also fixed one real port bug: the no-flesh
   branch reports `maxProb = 0` (`0x1027122c` / `0x10271607`), not the -1
   the accumulator is seeded with at `0x1027123e`.

arg3 and arg4: the SAME image on the colour-negative path
---------------------------------------------------------

The flesh block does not construct its analysis image.  `0x104e8360` —
which earlier passes filed as "the analysis-image construction" — is on the
`useSmallAnalysisImage != 0` branch (`0x102704a9 test cl,cl` on
`params+0x60a9`), and the shipped DPI sets `useSmallAnalysisImage = 0`, so
**it does not execute**.  What does execute is `fcn.102701e0` (a clone
through the impl's `vtbl+0x1c`) and `fcn.1014cc20`, which is
`IemTImage<T>::IemTImage(const IemImage&)` — a *type-checked handle
wrapper*, whose only failure mode is the throw "Can't construct an %s
IemTImage from an %s IemImage".  Neither touches a pixel.  arg3 and arg4
arrive from `AnsImageData::copyToIemImage` (`fcn.100db520`) at
`0x101c9bac` / `0x101c9beb`, i.e. from outside the capability.

Where they come from is now read end to end.  **Tier 3** throughout
(`af`+`pdf`, full bodies; `PakonIMAu.dll` md5
`eea9dcf78ee21d4f7c515a6c2512242d`), and the caller enumeration is a
whole-image `E8`/`E9 rel32` byte scan plus a dword scan for vtable
entries, so it is complete for direct *and* virtual dispatch::

    AnsCnEnhancedPath::analyzeOrder          fcn.10069d80
      -> CnEnhanced_analyzeSceneSpecific     fcn.10069490  @ 0x10069e75
         scene = [ebp+0xc]
         0x100694d3  lea eax, [esi + 4]     ; push -> analyzePostBalance arg4
         0x100694db  lea ebx, [esi + 0x4ac] ; push -> analyzePostBalance arg3
      -> ColorNegativePath::analyzePostBalance   fcn.100fdc40  @ 0x10069503
         0x100fdc89  mov ebp, [esp+0x200]   ; = arg3 = scene+0x4ac
         0x100fdc90  lea eax, [ebp + 0xa]   ; = scene+0x4b6, §168/§178's triple
         0x100fdf5e  mov ebp, [esp+0x204]   ; = arg4 = scene+0x04
         0x100fe396  push ebp
         0x100fe397  push ebp               ; <-- BOTH image arguments
      -> AnsFleshCapability::analyze         fcn.100f7280  @ 0x100fe3ac
         forwards its args 2..8 verbatim (0x100f72dc/0x100f72e0/0x100f72e4/
         0x100f72e5) to
      -> AnsFleshCapabilityImpl::analyze     fcn.101c92c0  @ 0x100f7303
         arg3 = [ebp+0x10]  -> copyToIemImage -> [ebp-0x30] -> fcn.10270280 arg3
         arg4 = [ebp+0x14]  -> copyToIemImage -> [ebp-0x38] -> fcn.10270280 arg4

So on the colour-negative path **arg3 and arg4 are two independent
`IemImage` copies of one and the same `AnsImageData`** — the scene's
analysis image at `scene+0x04`.  Feeding the same planes as both, which
is what `flesh_forward_delta` does, is not a shortcut: it is what the
vendor does.

`AnsImageData::copyToIemImage` (`fcn.100db520`, read in full) does a plain
`int16` deinterleave into `nBands` planes — **same dimensions, no
resampling, no colour transform, no scaling**.  The struct it reads is
`+0x04` interleave code, `+0x0c` cols, `+0x10` rows, `+0x14` nBands
(1..3, else "…has less than one or more than three bands."), `+0x18` bit
depth, `+0x20` data.  The same layout is filled by `apuCheckAnalysisImage`
(`fcn.100d46a0`) with **nBands = 3, bit depth = 12** before it calls
`AnsScene::getImage("StandardAnalysisImage")` (`fcn.100215c0`), and that
image must be at least **107 x 107** (`0x100d47c4 mov ecx, 0x6b`) or the
path aborts with "Scene's analysis image is not OK (too small)".

Two consequences for this module, both upgrades of previously tier-3
caveats:

* the weight plane is built at `word [arg3_obj+0x10]` x `word
  [arg3_obj+0x0c]` (`0x101c99e0`/`0x101c99e6`) and then padded to the arg4
  image's size, so with arg3 == arg4 the pad `fcn.104e7880` is provably an
  **identity** here.  §185.3's "only the equal case is constructible" is
  now "only the equal case occurs".
* `fcn.10270280`'s arg8 — the flag that enables the *second* LUT pre-pass —
  is the literal `1` pushed at `0x100fe392`, so the second pre-pass
  **always runs** on this path.  `second_prepass` defaults to `True` for
  that reason.

The one call site where arg3 != arg4 is `AnsDcPremiumPath::analyzeScene`
(`fcn.1006fa90` @ `0x1007287d`, DC_Premium.cpp) — the digital-camera path,
which also passes arg6 = NULL (no shift triple), arg7 = 0 and arg8 = 0.
It is a different mode and is not the F-135's.

What is **NOT** ported here
---------------------------

* `fcn.10270280`'s arg7 (`float` exposure, the ``exposureLimit`` guard).
  It is `[scene+0x4ac+0x10]` (`0x100fe37b`), caller state, not computed
  here.
* The content of the scene analysis image itself: this module is handed
  planes and does not know what produced them.

Everything between those inputs and `Delta` is ported and bit-exact.

The `useAdvanced != 0` branch — the Bayesian net (`skinSBA.bn`), the region
statistics (`fcn.102a2550`, `fcn.102a2940`, `fcn.1029dbd0`, `fcn.1029c090`,
`fcn.1029bcd0`) and the region->probability mapping at `0x10271020` — is
**not ported and does not need to be**: `0x10270cb2 mov eax,[ebp+0x44]` /
`0x10270cbf je 0x102711a2` gates the whole block on `useAdvanced`, and the
shipped DPI sets `useAdvanced = 0`.  Likewise `oneDTable = 1` selects the
separable three-table product at `0x102a18b3`, so the shipped 3-D LUT
(`ROMM_LST_SkinProb_041403_v5_pack`) is **not read on this path** — the
`oneDTable == 0` branch at `0x102a18f2` is the only consumer.

Consequence: `Delta` **can now be computed forward from real pixels** —
`flesh_forward_delta` runs the whole chain — but reproducing §178's six
*measured* values still requires knowing which frame each one belongs to,
and no capture pairs a measured Delta to the frame that produced it (a
full streaming census of all 2,648,694,028 bytes of
`live_hooks_20260820-180905.jsonl` found 37 labels, none flesh-related).
So the forward run is **tier 4 against §178** — a magnitude and sign
check, not a reproduction — while every *stage* inside it, and the whole
function that assembles them, is tier 1.  That gap is a **capture** gap,
not a port gap: `pakon_flesh_whole_golden.py` shows the port and the real
`fcn.10270280` agree bit-exactly on whatever pixels they are both given.

What actually limits the forward run is **the balance of the planes it is
handed, on the `s = R - B` axis** — not, as §186.3 supposed, a difference
between arg3 and arg4.  The shipped `condProbTbl-s.tbl` peaks at bin 19,
i.e. `S = 19*sscale + soff = 238`; on 14 real hook frames through
`scene_rpd12` with `PAKON_NO_INVERT=1` this port's post-shift mean `S` is
**-325..-67**, which pins 60-99 % of pixels at `s` bin 0 where the skin
probability is ~0.  The `l` and `t` axes land near their tables' peaks;
only `s` collapses.  §178's own six *measured* entry triples have
`R - B` in 634..682, mean 657, against this port's per-roll
683-151 = **532** — a deficit of 125 codes, i.e. `k = 63` split between
the two channels.  Adding `k` to R and subtracting it from B moves the
non-zero rate as::

    k        0    40    60    68    80   100   120   200   300   400
    non-zero 14%  21%   50%   50%   50%   64%   86%   93%   79%   29%

against the vendor's measured **46 %** (§168.1, 18/39).  The 60..80 plateau
brackets the deficit the triples independently imply.  The rate is governed by
the per-frame balance, which is the very quantity Delta exists to correct.
That is tier 4 and cross-roll (the six triples are from the v45 capture,
the frames from `live_hooks_20260819-121153.jsonl`); the Delta *range* at
`k = 68` is -146..+85 against the vendor's -59..+35, so a uniform `k`
buys the rate and not yet the magnitudes.

One structural fact the threshold port settles, which was previously
guesswork: on the V1 path the plane the reduction walks is **binary**.
`fcn.102a1500` copies `fcn.1029ec50`'s returned 0/255 mask into its own
arg2 at `0x102a2125…0x102a215e` (a flat `H*W` word copy) after passing it
through `fcn.1029cad0` again at `0x102a1e8e`.  So the 0/10/20/255 clamp map
is nearly an identity there — its 10/20 arms exist for the `useAdvanced`
path, where the plane carries region probabilities — and the threshold's
effect on the reduction reduces to "does 255 beat it".  It does for every
bin the search can return (max 61 -> 244) and it does not for the
no-valley default (64 -> 256), which is exactly the "no flesh found"
case that forces `X = fleshNeutralAim` and `Delta = 0`.

The arithmetic, in the DLL's own terms
--------------------------------------

`ebp` = the parameter struct (arg1, `esp+0x1c88`), `edi` = the results
struct (arg11, `esp+0x1cb0` = `FleshImpl+0x60c8`; the adjust triple is
therefore `FleshImpl+0x60f8`, which is exactly where §180 saw
`AnsFleshCapabilityImpl::analyze` read `m_fleshAdjust` from).

    0x102714e1  fleshCount == 0  ->  X = fleshNeutralAim         (0x10271610)
    0x102714ed  tSpace = byte [ebp+0x5c]
    0x102714ff  X = stat * (tSpace ? 0.5773672055427251 : 1/3) / nsum
    0x10271616  d0 = X - fleshNeutralAim
    0x1027161e  D  = -(d0 * (d0 >= 0 ? frontLitBeta : backLitBeta))
    0x102716b3  Q  = fleshCount / area
    0x102716c9  Q < fleshCountThresh              -> Delta = 0
    0x102716dd  exposure < exposureLimit          -> Delta = 0
    0x102716ea  t  = ftol(D * percentFleshAdj * 0.5773672055427251)
    0x1027170a  Delta = ftol((double)(int32)t - fleshPrefAdj)
    0x10271736  darkenOnly && D > 0               -> Delta = 0

All three channels are written from the same register
(`0x10271718/1c/20`, with `dx := ax` at `0x10271715`), so Delta is uniform
across channels by construction, not by coincidence.

The V1 detector, in the DLL's own terms
--------------------------------------

`fcn.102a1500`'s per-pixel loop (`0x102a17e5 … 0x102a191e`) reads three
int16 colour planes — plane0/plane1/plane2, call them R/G/B — and forms

    L = R + G + B          (0x102a17f0/f3, an int32 add)
    S = R - B              (0x102a17fd)
    T = 2*G - B - R        (0x102a17ff/1804/1809)

`L` stays an exact integer through `fild`; `S` and `T` are round-tripped
through **float32** (`fstp dword [ebp-0x4c]` / `[ebp-0x60]`).  Each axis is
then offset, divided by its scale **as a float32** and truncated twice:

    l = clamp31(ftol( ftol(L - loff) / f32(lscale) ))   , 0 if L-loff < 0
    s = clamp31(ftol( ftol(S - soff) / f32(sscale) ))   , 0 if S-soff < 0
    t = clamp31(ftol( ftol(T - toff) / f32(tscale) ))   , 0 if T-toff < 0

and with `oneDTable != 0` (which the shipped DPI sets) the probability is
the separable product of the three 32-entry conditional-probability tables

    p = tTable[t] * sTable[s]                (0x102a18be / 0x102a18c4)
    if not stOnly:  p *= lTable[l]           (0x102a18cf)
    if p < 0.001:   p  = 0.0                 (0x102a18d2, `fcom` @0x1059db90)
    floatPlane[x] = (float32) p              (0x102a18ed)

With `oneDTable == 0` the same loop instead writes `l`, `s`, `t` as three
int16 planes (`0x102a18f2 … 0x102a190b`) for a later 3-D LUT lookup; that
branch is dead on this path.

`0x105a4d00`-area key names map to 0x1000-byte string slots in the same
parameter struct (`fcn.10272380`, `0x10272f89 … 0x10273078`):
`lCondProbKey` -> `+0x68`, `sCondProbKey` -> `+0x1068`,
`tCondProbKey` -> `+0x2068`, `bayesianNetKey` -> `+0x3068`,
`3dLutKey` -> `+0x4068`, `intermediateImageDir` -> `+0x50a8`.  The *loaded*
tables sit at `+0x38` / `+0x3c` / `+0x40` (dword pointers, copied verbatim
by the copy-ctor at `0x101c7e3b`).

The loader: `AnsFleshCapabilityImpl::AnsFleshCapabilityImpl`
------------------------------------------------------------

Which loaded table lands in which of those three slots **is** now read out
of the loader — `fcn.101c84f0` (3031 B, `af`+`pdf`, full body).  It is not
`AnsFleshCapability::initialize` (`fcn.100f5da0`): that one takes a *local*
copy of the DPI, checks all three keys are present in the CondProbTables
cache ("Can't find condProbTbl key … in cache."), and throws the local copy
away without binding anything.  The binding happens in the impl's
constructor, on `this`::

    0x101c8c86  lea ebp, [esi + 0x80]      ; impl+0x80    = DPI+0x68   lCondProbKey
    0x101c8cb2  call 0x10089af0            ; cache find -> handle @ esi+0x6110
                                           ; failure: "lCondProb" + " not found."
    0x101c8dc5  call 0x10288bb0            ; mov eax,[ecx+0x30]; ret
    0x101c8dd5  mov [esi + 0x50], eax      ; impl+0x50    = DPI+0x38
    0x101c8dca  lea ebp, [esi + 0x1080]    ; impl+0x1080  = DPI+0x1068  sCondProbKey
    0x101c8df9  call 0x10089af0            ; -> handle @ esi+0x6144
                                           ; failure: "sCondProb" + " not found."
    0x101c8edf  mov [esi + 0x54], eax      ; impl+0x54    = DPI+0x3c
    0x101c8ed4  lea ebp, [esi + 0x2080]    ; impl+0x2080  = DPI+0x2068  tCondProbKey
    0x101c8f03  call 0x10089af0            ; -> handle @ esi+0x6178
                                           ; failure: "tCondProb" + " not found."
    0x101c9000  mov [esi + 0x58], eax      ; impl+0x58    = DPI+0x40

The DPI is embedded in the impl at `+0x18`, which three independent sites
agree on: `0x101c99d7 lea eax,[edi+0x18]` is `fcn.10270280`'s arg1;
`0x101c9c18 mov al, byte [edi+0x4080]` reads the `3dLutKey` string
(`DPI+0x4068`); and `results = impl+0x60c8` sits just past `DPI+0x60ab`.
So the assignment is `l -> +0x38`, `s -> +0x3c`, `t -> +0x40`.

A second, independent tier-3 witness says the same thing in the vendor's
own words: `fcn.1026f5a0` (1336 B) is a `FleshParams` dump that prints every
field with its source name, and it prints `[ebx+0x38]` as **`lCondProb`**
(`0x1026f6ef`), `[ebx+0x3c]` as **`sCondProb`** (`0x1026f71d`) and
`[ebx+0x40]` as **`tCondProb`** (`0x1026f74c`) — alongside `loff/soff/toff`
at `+0x18/+0x1a/+0x1c`, `lscale/sscale/tscale` at `+0x20/+0x28/+0x30`,
`useAdvanced +0x44`, `stOnly +0x58`, `tSpace +0x5c`, `oneDTable +0x60`,
`bn +0x64`, which is a field-by-field confirmation of this module's whole
`FleshParams` layout.  Both witnesses agree with the tier-1 consumer
(`fcn.102a1500`: `+0x38` is the slot `stOnly` skips).  See
``FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED``.

Notes on the detector's frame and its twelve arguments
------------------------------------------------------

Read at tier 3 (`af`+`pdf`) and since **executed** end to end by
`pakon_flesh_whole_golden.py`, which is what settled the `-D/130` and
`maxProb` details below.

* `fcn.10270280` is `cdecl` with **12 args** (`0x101c9d12` … `add esp,0x30`).
  arg1 = the parameter struct (`ebp` here); arg7 = the `float` exposure the
  ``exposureLimit`` guard tests; arg11 = the results struct, which the
  caller forms as ``lea eax,[edi+0x60c8]`` — so ``results+0x30`` *is*
  ``FleshImpl+0x60f8``, the address §180 saw `m_fleshAdjust` read from.
  That is an independent confirmation of the §180.3 write sites.
* The results struct: ``+0x00`` X, ``+0x08`` nsum, ``+0x10`` Q
  (= ``FleshImpl+0x60d8``, §180.3), ``+0x18`` ``-D/130``, ``+0x20``
  ``maxProb/255``, ``+0x28`` the probability threshold (written at
  ``0x10270c7e`` from `fcn.102a1500`'s integer out-param), ``+0x30..0x34``
  the adjust triple.  ``+0x18`` and ``+0x20`` are **multiplies** by the
  doubles nearest 1/130 and 1/255 (``0x105a4c88`` / ``0x105a1778``, at
  ``0x10271659`` / ``0x1027166c``), not divisions — dividing by 130.0
  instead differs by 1 ulp on some frames.  ``D`` itself is spilled to a
  qword at ``0x1027164b`` before either use, so it is a plain ``double``
  by then and no x87 extended precision leaks into ``Delta``.
* ``maxProb`` is seeded to -1 at ``0x1027123e``, but the **no-flesh**
  branch overwrites it with 0 (``0x1027122c xor eax,eax`` /
  ``0x10271607 mov [esp+0x1c], eax``), so ``+0x20`` is 0.0 there and not
  -1/255.  This port had -1 until the whole function was run.
* arg9, arg10 and arg12 feed only debug output: arg9/arg10 are behind
  ``0x10271760 test al,al`` on ``params+0x60a8`` (``writeIntermediateImages``)
  and arg12 gates the image dump at ``0x1027182c``.  The shipped DPI clears
  ``writeIntermediateImages``; passing 0/0/0 gives a clean ``ret``.
* arg2 is a refcounted handle the caller addrefs at ``0x101c9d06`` and this
  function only destroys (``0x1027047a`` / ``0x10271a9b``, ``fcn.104d6f70``);
  a null takes the destructor's own null check.
* The element-type guard at ``0x1027037a … 0x102703d8`` accepts only the
  ``byte`` and ``short`` `IemType` statics (``0x106c8298`` / ``0x106c82dc``)
  and returns ``0xfffa`` otherwise.  The four statics are built by
  ``fcn.104d4170`` from the initialisers at ``0x10570dc0 … 0x10570e20``:
  ``("unspecified",1) ("byte",2) ("short",3) ("float",4)`` — which is an
  independent confirmation of the element-type tags
  `pakon_flesh_threshold_golden.py` had to assert from row strides.
* The reduction loop reads **four** planes: a three-plane colour image
  (rows at ``0x102712f4`` / ``0x10271313`` / ``0x1027133d``), a weight
  plane (``0x10271340``) and a probability plane (``0x1027134e``) which the
  loop walks and **binarises in place** to 0 / 255.  The V1 branch
  (``useAdvanced == 0``, which the shipped DPI selects) weights by the
  weight plane; the ``useAdvanced`` branch weights by the probability
  plane itself.
* Borders: ``b_outer = flesh_border(dim_4520, clipAmount)``,
  ``b_inner = flesh_border(dim_4530, clipAmount)``
  (``0x10270702…0x1027075f``).  The loop insets ``dim_4520`` by ``b_outer``
  and ``dim_4530`` by ``b_inner``; the **area** at ``0x1027167f`` insets
  them the other way round, and on a different image object
  (``esp+0x30`` vs the loop's ``esp+0x3c``).  Reproduced verbatim in
  ``flesh_area``; not corrected.
* Reachability: `tools/re/reachability.py walk 0x100fdc40` (analysis `aaa`,
  439 functions / 135,611 realsz bytes / 288 indirect sites) reaches
  `0x100f7280`, `0x101c92c0`, `0x100f7560`, `0x10270280`, `0x10270050` and
  `0x102a1500` on **direct** call edges.  Reachable is not the same as
  executed *by the vendor's own software on a real scan*; what is now
  settled is that this port and `fcn.10270280` compute the same thing.
* Shipped data: the 3-D LUT is plain ASCII, header ``33 33 33 3 35937``
  then 3 axis vectors of 33 entries then ``3 * 35937`` u8 values;
  `condProbTbl-{l,s,t}.tbl` are ``size = 32`` / ``vals =`` float lists;
  `skinSBA.bn` is an 11-node Bayesian net in a plain-text ``kind general``
  format.  None of these are parsed here.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 -c "import pakon_flesh"``
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

# --- provenance -------------------------------------------------------------

PAKONIMAU_MD5 = "eea9dcf78ee21d4f7c515a6c2512242d"
FLESH_DPI_DEFAULT_MD5 = "51659429d8b71415189bea5099352040"

#: Ported and proven bit-exact against the DLL by ``pakon_flesh_golden.py``.
FLESH_ADJUST_ARITHMETIC_PORTED = True
#: The reduction loop ``0x102712ac…0x102714c7`` — bit-exact against the DLL
#: (``pakon_flesh_detector_golden.py``), including the loop bounds and the
#: in-place binarisation of the probability plane.
FLESH_REDUCTION_LOOP_PORTED = True
#: The LST transform + axis indices + separable probability product
#: (``0x102a1787…0x102a192a``) — bit-exact against the DLL.
FLESH_LST_PROBABILITY_PORTED = True
#: The analysis border ``0x102706fe…0x10270763`` — bit-exact against the DLL.
FLESH_BORDER_PORTED = True
#: The 0/10/20/255 clamp map ``0x102711d0…0x10271219`` — bit-exact.
FLESH_CLAMP_MAP_PORTED = True
#: ``fcn.1029ec50`` (3575 B) together with ``fcn.1029cad0`` — the Sobel edge
#: mask, the 64-bin histogram, the 15-tap smoothing, the peak/valley search
#: and the integer threshold that lands at ``results+0x28`` — **bit-exact**
#: against the real DLL (``pakon_flesh_threshold_golden.py`` runs the whole
#: function under Unicorn and diffs the mask, all 64 histogram bins, all 64
#: smoothed bins, the threshold and the returned binary plane).
FLESH_THRESHOLD_PORTED = True
#: Which of the three loaded conditional-probability tables the loader puts
#: at ``P+0x38`` / ``P+0x3c`` / ``P+0x40``: ``l`` / ``s`` / ``t``, in that
#: order.  The *consumer* side is tier 1 (``+0x38`` is the table `stOnly`
#: skips, ``+0x3c`` is indexed by `s`, ``+0x40`` by `t`).  The *loader* side
#: is now read too, and it agrees — twice over, both tier 3 (`af`+`pdf`,
#: full bodies): `AnsFleshCapabilityImpl::AnsFleshCapabilityImpl`
#: (``fcn.101c84f0``) resolves ``lCondProbKey`` / ``sCondProbKey`` /
#: ``tCondProbKey`` in that order and stores the three results at
#: ``impl+0x50 / +0x54 / +0x58`` = ``DPI+0x38 / +0x3c / +0x40``, and the
#: vendor's own DPI dump ``fcn.1026f5a0`` labels those same three offsets
#: ``lCondProb`` / ``sCondProb`` / ``tCondProb``.  See the module header.
FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED = True
#: ``fcn.10271bc0`` — the 2-D Gaussian weight map.  Bit-exact against the
#: real DLL (``pakon_flesh_weight_golden.py``, 3,078,017 samples).
FLESH_WEIGHT_MAP_PORTED = True
#: ``fcn.104e7880`` (``.\IemPad.cpp``) with ``operation == 1`` — the centred
#: **replicate** pad that brings the weight map up to the analysis image's
#: dimensions at ``0x1027127e``.  Bit-exact against the real DLL.
FLESH_PAD_PORTED = True
#: ``fcn.1026fed0`` (12-bit clamp table) + ``fcn.10270050`` (the three
#: ``clamp(i + shift, 0, 4095)`` LUTs).  Bit-exact against the real DLL.
FLESH_SHIFT_LUT_PORTED = True
#: The two 1-D LUT pre-passes ``0x102708ba…0x10270979`` and
#: ``0x10270ab9…0x10270b69``.  Bit-exact against the real DLL.
FLESH_PREPASS_PORTED = True
#: The two source images (`fcn.10270280` arg3 / arg4).  They are NOT built
#: inside the flesh block — see the module header — so this is a boundary,
#: not a stage.  ``0x104e8360`` is dead on the shipped DPI.
FLESH_ANALYSIS_IMAGE_PORTED = False
#: The whole detector, end to end from pixels.  ``fcn.10270280`` has now
#: been executed **as one function** under Unicorn, with its own twelve
#: arguments, by ``pakon_flesh_whole_golden.py``: its results struct (X,
#: nsum, Q, ``-D/130``, ``maxProb/255``, the threshold and the three
#: ``m_fleshAdjust`` words) and four of its internal buffers (the
#: post-pre-pass colour planes, the padded weight plane, the int16
#: probability plane at ``0x102a1e25`` and the clamped plane at
#: ``0x102712ac``) match ``flesh_forward_delta`` bit-exactly across
#: 58,462 compared values.  So the *assembly* is tier 1, not just the
#: stages.  It remains true that no capture pairs one of §178's six
#: measured Deltas to the frame that produced it, so a comparison against
#: **those numbers** is still tier 4 — that is a data gap, not a port gap.
FLESH_DETECTOR_PORTED = True
#: The ``useAdvanced`` branch (Bayesian net ``skinSBA.bn`` + region stats) and
#: the ``oneDTable == 0`` branch (the shipped 3-D LUT).  Not ported, and
#: unreachable with the shipped DPI — see the module header.
FLESH_ADVANCED_PATH_PORTED = False
FLESH_3DLUT_PATH_PORTED = False

# --- code addresses (PakonIMAu.dll, image base 0x10000000) ------------------

FLESH_ADJUST_CALC = 0x10270280  # the adjust calculator
FLESH_ADJUST_CALL_SITE = 0x101C9D12  # AnsFleshCapabilityImpl::analyze
FLESH_ADJUST_TAIL_ENTRY = 0x102714E1  # mov eax, dword [esp+0x24]  (fleshCount)
FLESH_ADJUST_TAIL_EXIT = 0x10271760  # first insn past the darkenOnly guard
FLESH_PARAM_READER = 0x10272380  # fleshParameterReader driver
FLESH_REDUCTION_LOOP_ENTRY = 0x10271390
FLESH_REDUCTION_LOOP_END = 0x1027149B
#: The whole 2-D reduction, from the row-bound setup to the join point.
FLESH_REDUCE_ENTRY = 0x102712AC
FLESH_REDUCE_EXIT = 0x102714C7
#: The V1 probability builder: ``fcn.102a1500``'s per-row loop.
FLESH_LST_LOOP_ENTRY = 0x102A1787
FLESH_LST_LOOP_EXIT = 0x102A192A
FLESH_PROB_BUILDER = 0x102A1500
#: The analysis-border block in ``fcn.10270280``.
FLESH_BORDER_ENTRY = 0x102706FE
FLESH_BORDER_EXIT = 0x10270763
#: The 0/10/20/255 clamp loop (V1 path only).
FLESH_CLAMP_LOOP_ENTRY = 0x102711A2
FLESH_CLAMP_LOOP_EXIT = 0x1027121B
#: The ``useAdvanced`` gate that skips the whole Bayesian block.
FLESH_USEADVANCED_GATE = 0x10270CB2
#: The threshold chooser this port does NOT have.
FLESH_THRESHOLD_CHOOSER = 0x1029EC50
#: ``fcn.10271bc0`` — the Gaussian weight map.  Called once, from
#: ``AnsFleshCapabilityImpl::analyze`` at ``0x101c99f0``, immediately before
#: the ``"Could not generate weight map; status ="`` error path, with
#: ``(rows, cols, FleshImpl+0x18, &weightImage)``.
FLESH_WEIGHT_MAP_FN = 0x10271BC0
FLESH_WEIGHT_MAP_LOOP = 0x10271DE0
#: ``.\IemPad.cpp``'s entry (`fcn.104e7880`) and its kernel (`fcn.104e7190`).
FLESH_PAD_FN = 0x104E7880
FLESH_PAD_KERNEL = 0x104E7190
#: ``0x1027127e`` — where the pad is called, with the analysis image's own
#: row/col counts and ``fcn.10270280``'s arg5 as the source.
FLESH_PAD_CALL_SITE = 0x1027127E
#: The 12-bit clamp table ctor and the shift-LUT builder.
FLESH_MASTER_TABLE_CTOR = 0x1026FED0
FLESH_SHIFT_LUT_BUILDER = 0x10270050
FLESH_SHIFT_LUT_CALL_SITE = 0x102707E8
#: The two 1-D LUT pre-passes.  The second is gated on ``fcn.10270280``'s
#: arg8 (``0x102709b2 mov al, byte [esp+0x1ca4]``).
FLESH_PREPASS1_ENTRY = 0x102708BA
FLESH_PREPASS1_EXIT = 0x10270979
FLESH_PREPASS2_ENTRY = 0x10270AB9
FLESH_PREPASS2_EXIT = 0x10270B69
#: ``0x102704a9`` — the ``useSmallAnalysisImage`` test that makes the four
#: ``0x104e8360`` calls dead on the shipped DPI.
FLESH_USESMALL_GATE = 0x102704A9
FLESH_SMALL_ANALYSIS_FN = 0x104E8360
FLESH_GETSHIFTS = 0x100F7560  # AnsFleshCapability::getShifts
FLESH_ANALYZE_POST_BALANCE = 0x100FDC40
FLESH_TRIPLE_ADDS = (0x100FE471, 0x100FE479, 0x100FE47D)

#: ``FleshImpl`` offsets seen at the call site (``0x101c9cba lea eax,[edi+0x60c8]``)
FLESH_IMPL_RESULTS = 0x60C8
FLESH_IMPL_ADJUST = FLESH_IMPL_RESULTS + 0x30  # = 0x60f8, m_fleshAdjust source

# --- rdata constants (verified by ``pxq`` at these VAs) ---------------------

#: ``0x105a4c90`` = 0x3fe279caca32d863 — a typed-in 1/1.732, not 1/sqrt(3).
INV_1732 = struct.unpack("<d", struct.pack("<Q", 0x3FE279CACA32D863))[0]
#: ``0x105943c0``
ONE_THIRD = struct.unpack("<d", struct.pack("<Q", 0x3FD5555555555555))[0]
#: ``0x105a4c88`` — 1/130, used only for the reported ``results+0x18``
INV_130 = struct.unpack("<d", struct.pack("<Q", 0x3F7F81F81F81F820))[0]
#: ``0x105a1778`` — 1/255, used only for the reported ``results+0x20``
INV_255 = struct.unpack("<d", struct.pack("<Q", 0x3F70101010101010))[0]
#: ``0x1059db90`` = 0x3f50624dd2f1a9fc — the probability floor at
#: ``0x102a18d2``; anything strictly below it is replaced by ``0.0``
#: (``0x10573c40``).
PROB_FLOOR = struct.unpack("<d", struct.pack("<Q", 0x3F50624DD2F1A9FC))[0]
#: The three conditional-probability tables have exactly this many bins,
#: and the axis index is clamped to ``[0, 31]`` (``0x102a1842`` etc.).
COND_PROB_BINS = 32

# --- the parameter struct ---------------------------------------------------

# Every offset below is a literal ``add eax, N`` (or ``mov byte [eax+N]``)
# in ``fcn.10272380``, where ``eax = *(reader+4)`` is the parameter struct —
# the same base as ``ebp`` in ``fcn.10270280``.  The eight doubles at
# 0x5068..0x50a0 and the byte at 0x60aa land on exactly the offsets the
# adjust calculator reads, which is what pins the two bases together.
FLESH_PARAM_LAYOUT: dict[str, tuple[int, str]] = {
    # key (lower-case, as the reader compares it)  offset   sscanf format
    "axialprob": (0x0008, "%lf"),
    "clipamount": (0x0010, "%lf"),
    "loff": (0x0018, "%hd"),
    "soff": (0x001A, "%hd"),
    "toff": (0x001C, "%hd"),
    "lscale": (0x0020, "%lf"),
    "sscale": (0x0028, "%lf"),
    "tscale": (0x0030, "%lf"),
    "useadvanced": (0x0044, "%ld"),
    "growthreshold": (0x0048, "%lf"),
    "regionthreshold": (0x0050, "%lf"),
    "stonly": (0x0058, "%ld"),
    "tspace": (0x005C, "%d!"),  # scanned to int32, stored as a bool byte
    "onedtable": (0x0060, "%ld"),
    "beta": (0x5068, "%lf"),
    "frontlitbeta": (0x5070, "%lf"),
    "backlitbeta": (0x5078, "%lf"),
    "fleshprefadj": (0x5080, "%lf"),
    "fleshneutralaim": (0x5088, "%lf"),
    "fleshcountthresh": (0x5090, "%lf"),
    "percentfleshadj": (0x5098, "%lf"),
    "exposurelimit": (0x50A0, "%lf"),
    "writeintermediateimages": (0x60A8, "%d!"),
    "usesmallanalysisimage": (0x60A9, "%d!"),
    "darkenonly": (0x60AA, "%d!"),
}

#: Keys the reader copies as NUL-terminated strings into 0x1000-byte slots
#: (``fcn.10272380`` @ ``0x10272f89 … 0x10273078``, each a byte-copy loop).
#: The copy-ctor at ``0x101c7e28 … 0x101c7ec0`` walks the same five slots
#: with ``mov ebp, 0x1000``, which is what pins the stride.
FLESH_PARAM_STRING_LAYOUT: dict[str, int] = {
    "lcondprobkey": 0x0068,
    "scondprobkey": 0x1068,
    "tcondprobkey": 0x2068,
    "bayesiannetkey": 0x3068,
    "3dlutkey": 0x4068,
    "intermediateimagedir": 0x50A8,
}
FLESH_PARAM_STRING_KEYS = tuple(FLESH_PARAM_STRING_LAYOUT)

#: Pointers to the three *loaded* conditional-probability tables, filled in
#: by ``AnsFleshCapability::initialize`` (not by the reader; the ctor at
#: ``0x101c7d44`` zeroes them).  ``+0x38`` is the one ``stOnly`` skips.
FLESH_COND_PROB_PTR_OFFSETS = (0x0038, 0x003C, 0x0040)

#: Smallest blob that holds every mapped field.
FLESH_PARAM_BLOB_SIZE = 0x60B0


@dataclass
class FleshParams:
    """The AnsFleshDPI parameter struct, as ``fcn.10270280`` sees it."""

    axial_prob: float = 0.0
    clip_amount: float = 0.0
    loff: int = 0
    soff: int = 0
    toff: int = 0
    lscale: float = 0.0
    sscale: float = 0.0
    tscale: float = 0.0
    use_advanced: int = 0
    grow_threshold: float = 0.0
    region_threshold: float = 0.0
    st_only: int = 0
    t_space: int = 0
    one_d_table: int = 0
    beta: float = 0.0
    front_lit_beta: float = 0.0
    back_lit_beta: float = 0.0
    flesh_pref_adj: float = 0.0
    flesh_neutral_aim: float = 0.0
    flesh_count_thresh: float = 0.0
    percent_flesh_adj: float = 0.0
    exposure_limit: float = 0.0
    write_intermediate_images: int = 0
    use_small_analysis_image: int = 0
    darken_only: int = 0
    keys: dict[str, str] = field(default_factory=dict)

    _FIELD_BY_KEY = {
        "axialprob": "axial_prob",
        "clipamount": "clip_amount",
        "loff": "loff",
        "soff": "soff",
        "toff": "toff",
        "lscale": "lscale",
        "sscale": "sscale",
        "tscale": "tscale",
        "useadvanced": "use_advanced",
        "growthreshold": "grow_threshold",
        "regionthreshold": "region_threshold",
        "stonly": "st_only",
        "tspace": "t_space",
        "onedtable": "one_d_table",
        "beta": "beta",
        "frontlitbeta": "front_lit_beta",
        "backlitbeta": "back_lit_beta",
        "fleshprefadj": "flesh_pref_adj",
        "fleshneutralaim": "flesh_neutral_aim",
        "fleshcountthresh": "flesh_count_thresh",
        "percentfleshadj": "percent_flesh_adj",
        "exposurelimit": "exposure_limit",
        "writeintermediateimages": "write_intermediate_images",
        "usesmallanalysisimage": "use_small_analysis_image",
        "darkenonly": "darken_only",
    }

    @classmethod
    def from_dpi(cls, raw: dict[str, str]) -> "FleshParams":
        """Build from a ``{lower_key: value_text}`` mapping."""
        out = cls()
        for key, text in raw.items():
            attr = cls._FIELD_BY_KEY.get(key)
            if attr is None:
                if key in FLESH_PARAM_STRING_KEYS:
                    out.keys[key] = text
                continue
            fmt = FLESH_PARAM_LAYOUT[key][1]
            if fmt == "%lf":
                setattr(out, attr, float(text))
            elif fmt == "%d!":
                # scanned as int32, then ``setne dl`` -> stored as 0/1
                setattr(out, attr, 1 if int(float(text)) != 0 else 0)
            else:
                setattr(out, attr, int(float(text)))
        return out

    def to_bytes(self) -> bytearray:
        """Lay the struct out exactly as the DLL reads it."""
        blob = bytearray(FLESH_PARAM_BLOB_SIZE)
        for key, (off, fmt) in FLESH_PARAM_LAYOUT.items():
            val = getattr(self, self._FIELD_BY_KEY[key])
            if fmt == "%lf":
                struct.pack_into("<d", blob, off, float(val))
            elif fmt == "%hd":
                struct.pack_into("<h", blob, off, int(val))
            elif fmt == "%ld":
                struct.pack_into("<i", blob, off, int(val))
            else:  # "%d!" -> a bool byte
                blob[off] = 1 if int(val) else 0
        return blob


def parse_flesh_dpi(path: str | Path) -> FleshParams:
    """Parse a shipped ``flesh-srcType-*.dpi``.

    The reader is line based: split the line, ``strcmp`` the first token
    against the (lower-case) key, then ``sscanf`` the rest with the key's
    format (``fcn.10272050`` @ ``0x102720d0``).  ``#`` starts a comment.
    """
    raw: dict[str, str] = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, val = line.partition("=")
        raw[key.strip().lower()] = val.strip()
    return FleshParams.from_dpi(raw)


# --- the arithmetic ---------------------------------------------------------


def _ftol32(x: float) -> int:
    """MSVC ``_ftol`` @ ``0x104ffe44``, keeping only the low dword.

    ``fistp qword`` with the round-to-zero fixup, then the caller uses
    ``eax`` alone (``0x10271702 mov [esp+0x20], eax``), so the 64-bit
    result is truncated to 32 signed bits.
    """
    if math.isnan(x) or math.isinf(x):
        # x87 indefinite: 0x8000000000000000 -> low dword 0
        return 0
    v = int(x)  # int() truncates toward zero, like _ftol
    return ((v + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def _to_i16(v: int) -> int:
    return ((v + 0x8000) & 0xFFFF) - 0x8000


def _imul32(a: int, b: int) -> int:
    v = (a * b) & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def flesh_statistic(
    stat: float, nsum: float, flesh_count: int, params: FleshParams
) -> float:
    """``X`` — ``0x102714e1 … 0x10271616``."""
    if flesh_count == 0:
        return params.flesh_neutral_aim  # 0x10271610
    k = INV_1732 if params.t_space else ONE_THIRD
    if nsum == 0.0:
        return math.copysign(math.inf, stat * k) if stat != 0.0 else math.nan
    return stat * k / nsum


def flesh_drive(x: float, params: FleshParams) -> float:
    """``D`` — ``0x10271616 … 0x10271645``.

    ``fcom 0.0`` then ``test ah,1`` tests C0 only, i.e. *strictly* less
    than zero picks ``backLitBeta``; ``d0 == 0`` takes ``frontLitBeta``.
    """
    d0 = x - params.flesh_neutral_aim
    beta = params.back_lit_beta if d0 < 0.0 else params.front_lit_beta
    return -(d0 * beta)


def flesh_border(dim: int, clip_amount: float) -> int:
    """``0x10270712 … 0x1027075f`` — the analysis inset for one axis.

    ``_ftol(dim * clipAmount)``, then the ``cdq``/``sub``/``sar 1``
    round-toward-zero halve, then ``if b != 0: b -= 1``.  Tier 3 only: this
    lives above ``FLESH_ADJUST_TAIL_ENTRY`` and is *not* covered by
    ``pakon_flesh_golden.py``.
    """
    v = _ftol32(float(dim) * clip_amount)
    b = (v - (v >> 31)) >> 1  # cdq / sub / sar 1 == divide by 2 toward zero
    if b != 0:
        b -= 1
    return b


def flesh_area(dim_4520: int, dim_4530: int, b_inner: int, b_outer: int) -> int:
    """``0x1027167f … 0x102716a8``.

    Note the borders are crossed relative to the reduction loop: the loop
    walks ``dim_4520`` inset by ``b_outer`` and ``dim_4530`` inset by
    ``b_inner`` (``0x102712b5`` / ``0x1027148f``), but the area insets
    ``dim_4520`` by ``b_inner`` and ``dim_4530`` by ``b_outer``.  That is
    what the instructions do; it is reproduced, not corrected.
    """
    return _imul32(dim_4530 - 2 * b_outer, dim_4520 - 2 * b_inner)


def flesh_fraction(flesh_count: int, area: int) -> float:
    """``Q`` — ``0x102716af fdivp``.  x87 semantics on a zero divisor."""
    if area == 0:
        if flesh_count == 0:
            return math.nan
        return math.copysign(math.inf, float(flesh_count))
    return float(flesh_count) / float(area)


def _lt(a: float, b: float) -> bool:
    """``fcomp`` + ``test ah,1``: C0, which is also set when unordered."""
    if math.isnan(a) or math.isnan(b):
        return True
    return a < b


def flesh_delta_from_drive(
    drive: float,
    fraction: float,
    exposure: float,
    params: FleshParams,
) -> int:
    """``0x102716c9 … 0x1027173e``.  Returns the int16 the DLL writes."""
    if _lt(fraction, params.flesh_count_thresh):  # 0x102716c9
        return 0
    if _lt(float(exposure), params.exposure_limit):  # 0x102716dd
        return 0
    t = _ftol32(drive * params.percent_flesh_adj * INV_1732)  # 0x102716fd
    delta = _to_i16(_ftol32(float(t) - params.flesh_pref_adj))  # 0x10271710
    if params.darken_only and drive > 0.0:  # 0x10271736
        return 0
    return delta


def flesh_delta(
    *,
    stat: float,
    nsum: float,
    flesh_count: int,
    area: int,
    exposure: float,
    params: FleshParams,
) -> int:
    """The whole tail, ``0x102714e1 … 0x1027173e``.

    ``stat`` / ``nsum`` / ``flesh_count`` come from the reduction loop (see
    ``flesh_accumulate``); ``area`` from ``flesh_area``; ``exposure`` is the
    ``float`` arg7 the caller passes at ``0x101c9ce6``.
    """
    x = flesh_statistic(stat, nsum, flesh_count, params)
    drive = flesh_drive(x, params)
    frac = flesh_fraction(flesh_count, area)
    return flesh_delta_from_drive(drive, frac, exposure, params)


def flesh_results(
    *,
    stat: float,
    nsum: float,
    flesh_count: int,
    max_prob: int,
    area: int,
    exposure: float,
    params: FleshParams,
) -> dict[str, float | int]:
    """Every field the DLL writes into the results struct (``edi``).

    ``+0x00`` X, ``+0x08`` nsum, ``+0x10`` Q (= ``FleshImpl+0x60d8``),
    ``+0x18`` -D/130, ``+0x20`` maxProb/255, ``+0x30..+0x34`` the triple.
    """
    x = flesh_statistic(stat, nsum, flesh_count, params)
    drive = flesh_drive(x, params)
    frac = flesh_fraction(flesh_count, area)
    delta = flesh_delta_from_drive(drive, frac, exposure, params)
    return {
        "x": x,
        "nsum": nsum,
        "fraction": frac,
        "neg_drive_over_130": -(drive * INV_130),
        "max_prob_over_255": float(max_prob) * INV_255,
        "drive": drive,
        "delta": delta,
    }


def invert_delta_to_statistic(delta: int, params: FleshParams) -> tuple[float, float]:
    """Given an observed Delta, the ``(D, X)`` interval midpoint it implies.

    Both ``ftol``s truncate, so a Delta only pins ``D`` to an interval; this
    returns the midpoint of that interval.  A *consistency check*, tier 4 —
    it cannot confirm anything on its own.
    """
    lo = float(delta) + params.flesh_pref_adj
    hi = lo + 1.0
    t_mid = (lo + hi) / 2.0
    d_mid = t_mid / (params.percent_flesh_adj * INV_1732)
    beta = params.front_lit_beta if d_mid <= 0 else params.back_lit_beta
    x = params.flesh_neutral_aim - d_mid / beta
    return d_mid, x


# --- the V1 detector: LST -> axis indices -> separable probability ---------


def _f32(x: float) -> float:
    """Round through IEEE binary32, as ``fstp dword`` / ``fld dword`` do."""
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def flesh_lst(r: int, g: int, b: int) -> tuple[int, int, int]:
    """``L, S, T`` — ``0x102a17f0 … 0x102a1809``, all int32 arithmetic.

    ``r``/``g``/``b`` are plane0/plane1/plane2 of the analysis image, read
    with ``movsx word`` (so already signed 16-bit).
    """
    return (r + g + b, r - b, 2 * g - b - r)


def _axis_index(value: float, off: int, scale: float) -> int:
    """One axis of ``0x102a1817 … 0x102a18a9``.

    ``value - off`` is truncated to int32 first; a negative result short-
    circuits to bin 0 **without** the divide.  The divide is by the
    **float32** narrowing of the scale (``fdiv dword``), and its result is
    truncated again and clamped at 31 on the top side only.
    """
    v = _ftol32(value - float(off))
    if v < 0:  # 0x102a1825 / 0x102a1858 / 0x102a188b
        return 0
    i = _ftol32(float(v) / _f32(scale))
    return COND_PROB_BINS - 1 if i > COND_PROB_BINS - 1 else i


def flesh_lst_indices(r: int, g: int, b: int, params: FleshParams) -> tuple[int, int, int]:
    """``(l, s, t)`` bin indices for one pixel.

    ``L`` reaches the subtraction as an exact integer (``fild``); ``S`` and
    ``T`` are stored to **float32** first (``0x102a180e`` / ``0x102a1814``)
    and reloaded, so they carry binary32 rounding for magnitudes above
    2**24.  Reproduced, not idealised.
    """
    lv, sv, tv = flesh_lst(r, g, b)
    return (
        _axis_index(float(lv), params.loff, params.lscale),
        _axis_index(_f32(sv), params.soff, params.sscale),
        _axis_index(_f32(tv), params.toff, params.tscale),
    )


def flesh_skin_probability(
    r: int,
    g: int,
    b: int,
    params: FleshParams,
    tables: "FleshCondProbTables",
) -> float:
    """One pixel of the V1 probability plane (``oneDTable != 0``).

    The multiply order is the DLL's: ``t`` first, then ``s``, then ``l``
    (``0x102a18be`` / ``0x102a18c4`` / ``0x102a18cf``).  ``stOnly`` drops the
    ``l`` factor.  Anything strictly below ``PROB_FLOOR`` becomes ``0.0``;
    a NaN is *kept* (``fcom`` sets C0 and C2, so the ``jp`` is taken).
    The stored value is float32.
    """
    if not params.one_d_table:
        raise NotImplementedError(
            "oneDTable == 0 selects the 3-D LUT branch at 0x102a18f2, "
            "which is not ported (FLESH_3DLUT_PATH_PORTED)"
        )
    l, s, t = flesh_lst_indices(r, g, b, params)
    p = tables.t[t] * tables.s[s]
    if not params.st_only:
        p *= tables.l[l]
    if p < PROB_FLOOR:  # ordered '<' only; NaN survives
        p = 0.0
    return _f32(p)


def flesh_probability_plane(planes, params: FleshParams, tables: "FleshCondProbTables"):
    """``fcn.102a1500``'s whole per-row loop over a three-plane image.

    ``planes`` is ``(plane0, plane1, plane2)``, each a list of rows of
    signed 16-bit ints.  Returns a list of rows of float32 probabilities.
    """
    p0, p1, p2 = planes
    return [
        [
            flesh_skin_probability(p0[y][x], p1[y][x], p2[y][x], params, tables)
            for x in range(len(p0[y]))
        ]
        for y in range(len(p0))
    ]


# --- the 0/10/20/255 clamp map ----------------------------------------------


def flesh_clamp_prob(v: int) -> tuple[int, bool]:
    """``0x102711d0 … 0x102711fd`` — one entry of the V1 clamp loop.

    Returns ``(value, sets_flag)``.  ``sets_flag`` is the "there is real
    flesh probability in this frame" byte at ``[esp+0x17]``; if it stays
    clear the whole reduction is skipped (``0x10271246 je 0x10271607``) and
    ``X`` is forced to ``fleshNeutralAim``.  All comparisons are **signed
    16-bit**, so a negative value falls through the ``< 10`` arm to zero.
    """
    v = _to_i16(v)
    if v == 0:  # 0x102711d6 test ax,ax
        return 0, False
    if v > 255:  # 0x102711db cmp ax,0xff / jle
        return 255, True
    if v < 10:  # 0x102711e8 cmp ax,0xa / jge
        return 0, False
    if v > 20:  # 0x102711f2 cmp ax,0x14 / jle
        return v, True
    return v, False


def flesh_clamp_plane(plane) -> tuple[list, bool]:
    """The whole clamp loop; returns ``(clamped_rows, any_flag)``."""
    flag = False
    out = []
    for row in plane:
        new = []
        for v in row:
            nv, f = flesh_clamp_prob(v)
            flag = flag or f
            new.append(nv)
        out.append(new)
    return out, flag


# --- the reduction loop -----------------------------------------------------


def flesh_loop_rows(height: int, b_outer: int) -> list[int]:
    """``0x102712ac`` / ``0x102714a1`` — the row order, verbatim.

    ``y`` starts at ``height - b_outer`` (which is a *valid* index only
    because ``b_outer >= 1`` for any realistic dimension) and runs **down**
    while ``y > b_outer``.  Asymmetric on purpose: the top inset excludes
    row ``b_outer`` but the bottom one includes row ``height - b_outer``.
    """
    y = height - b_outer
    out = []
    while y > b_outer:
        out.append(y)
        y -= 1
    return out


def flesh_loop_cols(width: int, b_inner: int) -> range:
    """``0x10271361`` / ``0x1027148a`` — ``[b_inner, width - b_inner)``."""
    return range(b_inner, max(b_inner, width - b_inner))


def flesh_accumulate(
    prob,
    weight,
    planes,
    threshold: float,
    *,
    rows,
    cols,
    use_advanced: bool = False,
):
    """``0x10271390 … 0x1027149b``.  **Bit-exact** against the DLL for the
    ``use_advanced == False`` branch (`pakon_flesh_detector_golden.py`
    executes ``0x102712ac … 0x102714c7`` on real synthetic planes and diffs
    ``stat``/``nsum``/``count``/``maxProb`` *and* the rewritten probability
    plane).  The ``use_advanced == True`` branch is **tier 3 only** — it is
    unreachable with the shipped DPI, so it was read, not executed.

    ``prob`` is the plane that gets thresholded and binarised in place to
    ``0`` / ``255``.  ``planes`` are the three colour planes whose sum is
    measured.  ``weight`` is a fourth plane; in the V1 branch the weight
    comes from ``weight``, and in the ``useAdvanced`` branch it is ``prob``
    itself.  Everything is signed 16-bit read, and the product is a
    32-bit ``imul`` that is allowed to wrap.

    Returns ``(stat, nsum, flesh_count, max_prob)``.
    """
    stat = 0.0
    nsum = 0.0
    count = 0
    max_prob = -1
    p0, p1, p2 = planes
    for y in rows:
        for x in cols:
            p = int(prob[y][x])
            if use_advanced:
                if p <= 0:  # 0x1027139e cmp word [esi],0 / jle
                    continue
                w = p
            else:
                if not (float(p) > threshold):  # 0x10271413 fcomp / test ah,0x41
                    prob[y][x] = 0
                    continue
                if p > max_prob:  # 0x1027141d cmp / jle
                    max_prob = p
                prob[y][x] = 255  # 0x1027142a mov word [esi], 0xff
                w = int(weight[y][x])
            s = int(p0[y][x]) + int(p1[y][x]) + int(p2[y][x])
            stat += float(_imul32(w, s))
            nsum += float(w)
            count += 1
            if use_advanced and p > max_prob:
                max_prob = p
    return stat, nsum, count, max_prob


# --- the threshold chooser: fcn.1029ec50 ------------------------------------
#
# `fcn.10270280` never sees this directly.  `fcn.102a1500` calls it at
# `0x102a1e25` with five cdecl arguments
#
#     fcn.1029ec50(out_image, in_image, mode = 2, &threshold, useAdvanced)
#
# where `in_image` is the int16 0..255 probability plane (the float plane
# scaled by 255.0 at `0x102a1964` and cast at `0x102a197f`), and `&threshold`
# is `fcn.102a1500`'s own arg4 — the slot the caller reads back with
# `0x10270c6c fild dword [esp+0xc4]` and stores at `results+0x28`
# (`0x10270c7e fstp qword [edi+0x28]`).  The single write is
# `0x1029f8d1 mov dword [eax], ebp` with `ebp = bin << 2`.
#
# Two of the five arguments kill most of the function on the shipped path:
#
#   * `useAdvanced == 0` (`0x1029f056 mov eax,[esp+0x308]` /
#     `0x1029f067 je 0x1029f2c2`) skips the whole 3x3 connected-neighbour
#     morphology at `0x1029f06d…0x1029f1c4`, and again at `0x1029f6bf` /
#     `0x1029f723` it skips the second refinement pass `0x1029f6cb…0x1029f817`.
#   * `mode == 2` (`0x1029f556 cmp al,1` / `0x1029f611 cmp al,2`) selects the
#     local-minimum search at `0x1029f619…0x1029f6b6`; `mode == 1` selects a
#     different one at `0x1029f566` and any other value leaves the default.
#
# What is left is a compact, portable algorithm:
#
#     mag   = |conv(P, SOBEL_X)| + |conv(P, SOBEL_Y)|      (int16 throughout)
#     edge  = mag >= 400 ? 255 : 0                          (0x1029c2c0)
#     edge  = flesh_edge_clean(edge)                         (fcn.1029cad0)
#     hist[v >> 2] += 1  for every pixel with edge == 255, v = P[y][x]
#     smooth[i] = mean(hist[i-7 .. i+7] within [0,64))
#     smooth[0] = smooth[1] = 0
#     bin  = first i in 2..61 that is a local MINIMUM over +/-2 and comes
#            after (or at) a local MAXIMUM over +/-2; else 64
#     threshold = bin * 4
#
# The two 3x3 kernels are built at `0x1029ecb3…0x1029ee97` from five rdata
# doubles: `0x10574f50` = 1.0, `0x10573c40` = 0.0, `0x10574f58` = -1.0,
# `0x10574f48` = 2.0, `0x10578470` = -2.0.

#: `0x1029ecb3` (`0x104dc4d0(3,3,0)`) then nine `0x104d2eb0(r, c, value)`.
SOBEL_X = ((1.0, 0.0, -1.0), (2.0, 0.0, -2.0), (1.0, 0.0, -1.0))
#: `0x1029edae` and its nine setters.
SOBEL_Y = ((1.0, 2.0, 1.0), (0.0, 0.0, 0.0), (-1.0, -2.0, -1.0))
#: `0x1029c2c0`: ``mov ecx,[esp+4] / xor eax,eax / cmp ecx,0x190 / setl al /
#: dec eax / and eax,0xff / ret`` — i.e. ``x >= 400 ? 255 : 0``.
EDGE_THRESHOLD = 400
#: `0x1029c2e0`: ``mov eax,[esp+4] / test eax,eax / jge +2 / neg eax / ret``.
#: (Ported as ``abs``; the ``-32768`` fixed point is unreachable here because
#: ``|Sobel| <= 4*255``.)
#: The histogram is 64 floats — ``malloc(0x100)`` at `0x1029ec9d`, zeroed by
#: ``rep stosd`` of ``0x40`` dwords at `0x1029f356`.  The bin is ``v / 4``
#: rounded toward zero (`0x1029f3ea cdq / and edx,3 / add eax,edx / sar 2`),
#: **unchecked**: the vendor indexes the 64-float buffer with any int16, so a
#: probability outside ``0..255`` would write out of bounds.  It cannot on
#: this path (the plane is ``f32 p in [0,1] * 255.0`` cast to int16), and the
#: port raises rather than reproducing the corruption.
HIST_BINS = 64
#: `0x1029f4f0`: ``ecx`` starts at 7 and the window is ``[ecx-14, ecx]``, i.e.
#: ``[i-7, i+7]`` for output bin ``i``; the mean divides by the number of taps
#: that actually fall inside ``[0, 64)``.
SMOOTH_HALF_WIDTH = 7
#: `0x1029f826 shl ebp, 2`.
THRESHOLD_BIN_SCALE = 4
#: `0x1029f558 mov dword [esp+0x14], 0x40` — the bin used when the search
#: finds nothing, so the threshold becomes 256 and no pixel passes.
THRESHOLD_BIN_DEFAULT = 64

#: Code addresses, for citation.
FLESH_THRESHOLD_ENTRY = 0x1029EC50
FLESH_THRESHOLD_CALL_SITE = 0x102A1E25
FLESH_THRESHOLD_HIST_ENTRY = 0x1029F350
FLESH_THRESHOLD_HIST_EXIT = 0x1029F829
FLESH_EDGE_CLEAN = 0x1029CAD0
FLESH_CONVOLVE = 0x104DD9D0
FLESH_EDGE_MAP_FN = 0x1029C2C0
FLESH_ABS_FN = 0x1029C2E0
FLESH_THRESHOLD_STORE = 0x1029F8D1


def _mirror(i: int, n: int) -> int:
    """The convolution's out-of-range index policy.

    Established **empirically against the DLL** (`pakon_flesh_threshold_golden`
    runs the real `0x104dd9d0` on impulses and ramps): index ``-1`` reads row
    ``1`` and index ``n`` reads row ``n-2`` — a reflection that does *not*
    repeat the edge sample.  Reproduced, not derived from `fcn.104dcbc0`'s
    padding code, which was not read instruction by instruction.
    """
    if n <= 1:
        return 0
    while i < 0 or i >= n:
        if i < 0:
            i = -i
        if i >= n:
            i = 2 * n - 2 - i
    return i


def flesh_convolve(plane, kernel) -> list:
    """`0x104dd9d0` -> `fcn.104dd6a0` -> `fcn.104dcbc0`, int16 instantiation.

    Correlation, not convolution: ``out[y][x] = sum k[i][j] * P[y+i-1][x+j-1]``
    with the kernel used as written (verified with a single-pixel impulse).
    The accumulator is a double because the kernel is; with the shipped
    integer Sobel kernels every sum is exact, so **the store's rounding rule
    is unobservable on this path** — see the harness, which probes it with a
    deliberately fractional kernel and reports what it finds.
    """
    h = len(plane)
    w = len(plane[0])
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            acc = 0.0
            for i in range(3):
                yy = _mirror(y + i - 1, h)
                for j in range(3):
                    acc += kernel[i][j] * plane[yy][_mirror(x + j - 1, w)]
            row.append(_to_i16(_ftol32(acc)))
        out.append(row)
    return out


def flesh_edge_clean(plane) -> list:
    """`fcn.1029cad0` (545 B) — the 4-neighbour cleanup, in full.

    The border row/column are forced to zero (`0x1029cb40` and `0x1029cb70`);
    every interior pixel is rewritten from its own value and its four
    orthogonal neighbours:

    * a **zero** pixel becomes ``255`` unless at least two of the four
      neighbours are themselves zero (`0x1029cbd7 … 0x1029cc25`);
    * a **non-zero** pixel becomes ``255`` only if at least two of the four
      neighbours are strictly ``> 0`` (`0x1029cc27 … 0x1029cc6c`), otherwise
      ``0``.

    Note the asymmetry, which is the vendor's and is reproduced: the zero
    branch tests neighbours for ``== 0`` while the non-zero branch tests them
    for ``> 0``, so a negative neighbour counts as neither.  The scan order is
    left/up first, then right/down, and it short-circuits once two are found —
    which is invisible in the result but is why only four neighbours, never
    the diagonals, are ever read.
    """
    h = len(plane)
    w = len(plane[0])
    out = [[0] * w for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            v = _to_i16(plane[y][x])
            if v == 0:
                n = 0
                if _to_i16(plane[y][x - 1]) == 0:
                    n = 1
                if _to_i16(plane[y - 1][x]) == 0:
                    n += 1
                if n < 2:
                    if _to_i16(plane[y][x + 1]) == 0:
                        n += 1
                    if _to_i16(plane[y + 1][x]) == 0:
                        n += 1
                out[y][x] = 0 if n >= 2 else 255
            else:
                n = 0
                if _to_i16(plane[y][x - 1]) > 0:
                    n = 1
                if _to_i16(plane[y - 1][x]) > 0:
                    n += 1
                if n < 2:
                    if _to_i16(plane[y][x + 1]) > 0:
                        n += 1
                    if _to_i16(plane[y + 1][x]) > 0:
                        n += 1
                out[y][x] = 255 if n >= 2 else 0
    return out


def flesh_edge_mask(prob) -> list:
    """`0x1029eeef … 0x1029f02d` — the mask the histogram is taken over.

    ``|conv(P, SOBEL_X)| + |conv(P, SOBEL_Y)|``, mapped through
    ``x >= 400 ? 255 : 0``, then `flesh_edge_clean`, then converted to bytes
    (`0x1029f2fd`, ``iemConvert``; the values are already 0/255 so the
    conversion is an identity here and no clamping question arises).
    """
    gx = flesh_convolve(prob, SOBEL_X)
    gy = flesh_convolve(prob, SOBEL_Y)
    mag = [
        [_to_i16(abs(gx[y][x]) + abs(gy[y][x])) for x in range(len(prob[0]))]
        for y in range(len(prob))
    ]
    edge = [[255 if v >= EDGE_THRESHOLD else 0 for v in row] for row in mag]
    return flesh_edge_clean(edge)


def flesh_histogram(prob, mask) -> list:
    """`0x1029f350 … 0x1029f4bd` — 64 float32 bins over the masked pixels.

    ``hist[v // 4] += 1.0f`` for every pixel whose mask byte is exactly
    ``0xff``.  The divide is toward zero, and the vendor does **not** range
    check the result (see ``HIST_BINS``); this raises instead.
    """
    hist = [0.0] * HIST_BINS
    for y in range(len(prob)):
        mrow = mask[y]
        prow = prob[y]
        for x in range(len(prow)):
            if (mrow[x] & 0xFF) != 0xFF:
                continue
            v = _to_i16(prow[x])
            b = -((-v) // 4) if v < 0 else v // 4  # cdq / and 3 / add / sar 2
            if not 0 <= b < HIST_BINS:
                raise ValueError(
                    "probability %d puts the vendor's unchecked histogram index "
                    "%d outside [0,%d) — 0x1029f3ea has no bound check and would "
                    "corrupt the heap; refusing to model that" % (v, b, HIST_BINS)
                )
            hist[b] = _f32(hist[b] + 1.0)
    return hist


def flesh_smooth_histogram(hist) -> list:
    """`0x1029f4f0 … 0x1029f537`, plus the two zeroed bins at `0x1029f543`.

    A 15-tap box mean, divided by the number of taps inside ``[0, 64)`` — so
    the ends are shorter windows, not zero-padded ones.  The sum accumulates
    in the x87 register (double, with the CRT's 53-bit control word) and only
    the quotient is narrowed to float32.  Bins 0 and 1 are then overwritten
    with ``+0.0`` by two integer stores.
    """
    out = []
    for i in range(HIST_BINS):
        acc = 0.0
        n = 0
        for j in range(i - SMOOTH_HALF_WIDTH, i + SMOOTH_HALF_WIDTH + 1):
            if 0 <= j < HIST_BINS:
                acc += hist[j]
                n += 1
        out.append(_f32(acc / n))
    out[0] = 0.0
    out[1] = 0.0
    return out


def flesh_pick_bin(smooth) -> int:
    """`0x1029f619 … 0x1029f6b6` — the ``mode == 2`` search.

    For each candidate ``i`` from 2 to 61 the four neighbours ``i-2, i-1,
    i+1, i+2`` are classified against ``smooth[i]``:

    * all four ``<=`` and at least one ``<``  -> ``i`` is a local **maximum**;
      this sets a flag at ``[esp+0x18]`` that is **never cleared** (`0x1029f685`)
    * all four ``>=`` and at least one ``>``  -> ``i`` is a local **minimum**;
      this sets ``[esp+0x1c]``, which *is* recleared every iteration
      (`0x1029f62e`)

    and the first ``i`` where both flags read 1 wins.  The maximum flag starts
    at zero — `0x1029f548 mov dword [esp+0x1c], eax` with ``eax = 0`` lands on
    that slot while ``esp`` is still 4 low from the ``push ebp`` at
    `0x1029f539`, which is easy to misread; it is the same slot that held the
    (just-freed) histogram pointer.  So a valley before the first peak is
    rejected.  Returns ``THRESHOLD_BIN_DEFAULT`` when nothing matches.
    """
    seen_max = False
    for i in range(2, HIST_BINS - 2):
        greater = equal = less = 0
        for j in (i - 2, i - 1, i + 1, i + 2):
            if smooth[j] > smooth[i]:
                greater += 1
            if smooth[j] == smooth[i]:
                equal += 1
            if smooth[j] < smooth[i]:
                less += 1
        if equal + less == 4 and less:
            seen_max = True
        is_min = (equal + greater) == 4 and greater
        if seen_max and is_min:
            return i
    return THRESHOLD_BIN_DEFAULT


def flesh_threshold_from_plane(prob, *, mode: int = 2, use_advanced: int = 0) -> int:
    """The whole of `fcn.1029ec50`'s output value: ``*arg4``.

    ``prob`` is the int16 0..255 probability plane as rows.  Returns the
    integer that `fcn.102a1500`'s caller ``fild``s into ``results+0x28``.
    """
    if use_advanced:
        raise NotImplementedError(
            "useAdvanced != 0 re-enables the 3x3 morphology at 0x1029f06d and "
            "the second search pass at 0x1029f6cb; neither is ported, and the "
            "shipped DPI sets useAdvanced = 0"
        )
    if mode != 2:
        raise NotImplementedError(
            "only fcn.102a1500's own `push 2` (0x102a1e1b) is ported; mode 1 "
            "selects the different search at 0x1029f566"
        )
    mask = flesh_edge_mask(prob)
    hist = flesh_histogram(prob, mask)
    return flesh_pick_bin(flesh_smooth_histogram(hist)) * THRESHOLD_BIN_SCALE


def flesh_binarise(prob, threshold: int) -> list:
    """`0x1029f8b0 … 0x1029f8c7` — the byte image `fcn.1029ec50` returns.

    ``255`` where the probability is strictly greater than the threshold.
    Walked as one flat buffer, so it covers the whole plane including the
    border the mask zeroed.
    """
    return [
        [255 if _to_i16(v) > threshold else 0 for v in row] for row in prob
    ]


#: ``0x10575690`` — the scale `0x102a1964` hands to ``0x104e2960``.
PROB_PLANE_SCALE = 255.0


def flesh_prob_to_int16(prob_f32) -> list:
    """`0x102a195a … 0x102a197f` — the float plane -> the int16 0..255 plane.

    `0x104e2960` multiplies the float32 plane by the double ``255.0`` in
    place and `0x104de680` (``iemConvert``) casts it to int16.  The cast is
    **truncation toward zero and does not clamp** — verified by running the
    real `0x104de680` on ``0.4/0.5/0.6/1.5/2.5/-0.5/-1.5/254.5/255.4/300``
    (`pakon_flesh_threshold_golden.py` section [1c]); ``300.0`` comes back as
    ``300``, not ``255``.  It cannot go out of range here because the
    probability is ``[0, 1]`` by construction (`flesh_skin_probability`
    multiplies three table entries whose maximum is 1.0 and floors at 0.0).
    """
    return [[_to_i16(_ftol32(_f32(_f32(v) * PROB_PLANE_SCALE))) for v in row]
            for row in prob_f32]


def flesh_reduction_plane(prob, threshold: int) -> list:
    """The plane `fcn.10270280`'s reduction actually walks, on the V1 path.

    **Tier 3 for the composition** (the two halves are each tier 1).  Read
    out of `fcn.102a1500`:

    * `0x102a1e25` calls `fcn.1029ec50`, which returns the byte plane
      ``prob > threshold ? 255 : 0`` (`flesh_binarise`);
    * `0x102a1e69` converts it back to int16 and `0x102a1e8e` runs
      `fcn.1029cad0` over it a second time (`flesh_edge_clean`);
    * `oneDTable != 0` skips the growThreshold block (`0x102a1e96 jne
      0x102a1ef4`) and `useAdvanced == 0` jumps straight to `0x102a2125`,
      which flat-copies ``H*W`` words of it into **arg2** — the object
      `fcn.10270280` clamps at `0x102711a2` and reduces at `0x102712ac`.

    So on this path the reduction's "probability" plane is binary, the
    0/10/20/255 clamp map is nearly an identity over it, and the threshold
    only decides whether *anything* passes: every bin the search can return
    (2..61 -> 8..244) lets 255 through, and only the no-valley default
    (64 -> 256) does not.
    """
    return flesh_edge_clean(flesh_binarise(prob, threshold))


# --- the weight plane: fcn.10271bc0 -> fcn.104e7880 -------------------------
#
# `AnsFleshCapabilityImpl::analyze` builds the weight map ONCE, at
# `0x101c99f0`, before it calls the adjust calculator:
#
#     fcn.10271bc0(rows, cols, FleshImpl+0x18, &weightImage)
#
# and `fcn.10270280` then pads it up to the analysis image's dimensions at
# `0x1027127e` and hands the result to the reduction as `[esp+0x70]`.
#
# The map is a plain 2-D Gaussian, peak 1000 at the image centre, evaluated
# only over the clip-inset region -- so the pad's job is to put it back where
# it came from.  Every constant below is a literal in the function:
#
#     0x10596dc0 = -8.0      0x1057ae70 = -0.5      0x105a3c18 = 1000.0
#
#: `0x10271d41`.
WEIGHT_LOG_SCALE = -8.0
#: `0x10271e20`.
WEIGHT_HALF = -0.5
#: `0x10271e3c` -- the peak value, so the weight plane is 0..1000.
WEIGHT_PEAK = 1000.0


def _sar1(v: int) -> int:
    """``cdq / sub eax, edx / sar eax, 1`` -- halve toward zero."""
    return (v - (v >> 31)) >> 1


def flesh_weight_map(rows: int, cols: int, params: FleshParams) -> list:
    """``fcn.10271bc0``, the ``useSmallAnalysisImage == 0`` path.

    Returns the ``(rows - 2*b_rows) x (cols - 2*b_cols)`` int16 weight plane.

    The arithmetic is transcribed, not idealised, and two details are
    load-bearing -- both were caught only by diffing against the DLL:

    * the DLL divides **once** and then multiplies by the reciprocal
      (`0x10271d90 fdiv` then `0x10271daa fmul st(1)`, and `0x10271e00` /
      `0x10271e0e` again per row).  Writing ``/ sigma`` instead of
      ``* (1/sigma)`` costs 14 pixels in 3,078,017 -- a real ULP difference,
      not a rounding preference.
    * ``rows`` and ``cols`` reach the arithmetic through ``movsx`` from a
      16-bit register (`0x10271c0a`, `0x10271c21`), so a dimension above
      32767 wraps.  Reproduced.

    Both borders come from `flesh_border`, i.e. the same
    ``_ftol(dim*clipAmount) / 2 - 1`` as the analysis inset.
    """
    if not (params.axial_prob > 0.0):  # 0x10271d15, fcom against 0.0
        raise ValueError(
            "axialProb <= 0 makes 0x10271d1d return status 0xffff and "
            "AnsFleshCapabilityImpl::analyze report "
            "'Could not generate weight map'"
        )
    r = _to_i16(rows)
    c = _to_i16(cols)
    b_r = flesh_border(r, params.clip_amount)
    b_c = flesh_border(c, params.clip_amount)
    g = math.sqrt(WEIGHT_LOG_SCALE * math.log(params.axial_prob))
    if g == 0.0:  # 0x10271d5b
        raise ValueError("sqrt(-8*ln(axialProb)) == 0 -> status 0xfffe")
    inv_g = 1.0 / g  # 0x10271d90
    sigma_x = ((1.0 - params.clip_amount) * float(c)) * inv_g  # 0x10271da6/aa
    sigma_y = ((1.0 - params.clip_amount) * float(r)) * inv_g  # 0x10271db2/b6
    cx = _sar1(c)  # 0x10271d94
    cy = _sar1(r)  # 0x10271d9f
    inv_sx = 1.0 / sigma_x  # 0x10271e0e
    inv_sy = 1.0 / sigma_y  # 0x10271e00
    out = []
    for y in range(b_r, r - b_r):
        ny = (float(y) - float(cy)) * inv_sy
        ny2 = ny * ny
        row = []
        for x in range(b_c, c - b_c):
            nx = (float(x) - float(cx)) * inv_sx
            row.append(_to_i16(_ftol32(WEIGHT_PEAK * math.exp(
                WEIGHT_HALF * (nx * nx + ny2)))))
        out.append(row)
    return out


def flesh_pad_replicate(src, rows: int, cols: int) -> list:
    """``fcn.104e7880`` -> ``fcn.104e7190`` with ``operation == 1``.

    The source is placed at ``((rows-sh)/2, (cols-sw)/2)`` -- both halved
    toward zero (`0x104e7939` / `0x104e793c`, two `sar 1` after a `cdq/sub`)
    -- and the edges are **replicated** outward.  The ``double`` fill value
    the call site passes (`0x10270ba4`-style ``0.0``, pushed at
    `0x10271255`) is not used by operation 1; the harness demonstrates that
    rather than assuming it.

    `0x104e78bd` / `0x104e78d3` throw "Output rows/cols must be equal to or
    greater than input rows/cols" if the target is smaller, so that is an
    error here too rather than a silent crop.
    """
    sh = len(src)
    sw = len(src[0]) if sh else 0
    if rows < sh or cols < sw:
        raise ValueError(
            "0x104e78bd/0x104e78d3 throw 'Output rows/cols must be equal to "
            "or greater than input rows/cols' for %dx%d -> %dx%d"
            % (sh, sw, rows, cols)
        )
    top = _sar1(rows - sh)
    left = _sar1(cols - sw)
    out = []
    for y in range(rows):
        sy = min(max(y - top, 0), sh - 1)
        srow = src[sy]
        out.append([srow[min(max(x - left, 0), sw - 1)] for x in range(cols)])
    return out


def flesh_reduction_weight_plane(rows: int, cols: int, params: FleshParams) -> list:
    """The plane `flesh_accumulate`'s ``weight`` argument actually is.

    ``flesh_weight_map`` at the *weight map's own* dimensions, padded up to
    ``rows x cols`` by `flesh_pad_replicate`.  **Tier 3 for the composition
    when the two dimension pairs differ**: `fcn.10271bc0` is called from
    `AnsFleshCapabilityImpl::analyze` with ``word [esi+0x10]`` /
    ``word [esi+0xc]`` of an object this port does not have, while the pad
    at `0x1027127e` uses the analysis image's own row/col counts.  When they
    are equal -- which is the only case this port can construct -- the pad
    reduces to an exact replication of the inset border and the composition
    is unambiguous.
    """
    return flesh_pad_replicate(flesh_weight_map(rows, cols, params), rows, cols)


# --- the shift LUTs and the two 1-D pre-passes ------------------------------
#
# `0x102707a7` builds a clamp table with `fcn.1026fed0(0xc, 0, 0xfff)` --
# 12 bits, so `tbl[v] = 0` for `v <= 0`, `v` for `1 <= v <= 4095`, `4095`
# above -- indexed by a **signed int16** through a base biased by 0x10000.
# `0x102707e8` then calls `fcn.10270050` with that table as `this`, the
# shift triple read straight out of `fcn.10270280`'s **arg6**
# (`0x102707ac … 0x102707bf`, three `word` loads at +0, +2, +4) and a count
# of 0x1000, producing three LUTs
#
#     lut_c[i] = tbl[i + shift_c]      i in [0, 0x1000)
#
# which `0x10270920` applies to plane0/1/2 of the analysis image in place,
# and `0x10270b10` applies to the *second* image if arg8 is set.
#
# This is the single most consequential fact about the flesh block that the
# earlier passes did not have: **the detector runs on the frame's RPD image
# with the candidate shift already applied.**  Delta is therefore a
# correction evaluated at the shift it is about to correct.

#: `0x1026fef5` / `0x1026ff1a` -- both dimensions are rejected at 0x8000.
MASTER_TABLE_SPAN = 0x10000
#: `0x102707a0` pushes ``0xc`` -- 12 bits.
SHIFT_LUT_BITS = 0xC
#: `0x102707d1` pushes ``0x1000``.
SHIFT_LUT_COUNT = 0x1000


def flesh_shift_lut(shift: int, *, count: int = SHIFT_LUT_COUNT,
                    lo: int = 0, hi: int = 0xFFF) -> list:
    """One output of `fcn.10270050`, with `fcn.1026fed0`'s table folded in.

    ``fcn.1026fed0`` fills ``tbl[v] = lo`` for ``v <= 0`` (`0x1026ff80`, the
    loop runs while ``eax <= 0``, so index 0 gets ``lo`` too), ``tbl[v] = v``
    for ``1 <= v <= hi`` and ``tbl[v] = hi`` above.  `fcn.10270050` reads it
    at ``i + shift``.

    The vendor does **not** range check that index: the table covers
    ``[-0x8000, 0x7fff]`` and ``i + shift`` can leave it, which the DLL
    happily reads (measured: shift 32767 returns heap garbage at i == 1).
    This raises instead, on the same principle as `flesh_histogram`.
    """
    top = count - 1 + shift
    if top > 0x7FFF or shift < -0x8000:
        raise ValueError(
            "shift %d puts fcn.10270050's index %d outside the clamp table's "
            "[-0x8000, 0x7fff]; 0x102700ed has no bound check and the DLL "
            "reads past the 0x20002-byte allocation (measured), so this "
            "refuses rather than modelling the garbage" % (shift, top)
        )
    return [lo if i + shift <= 0 else (hi if i + shift > hi else i + shift)
            for i in range(count)]


def flesh_shift_luts(shifts, **kw) -> list:
    """The three LUTs `0x102707e8` builds, in plane order 0/1/2."""
    return [flesh_shift_lut(int(s), **kw) for s in shifts]


def flesh_apply_shift_luts(planes, luts) -> list:
    """`0x10270920 … 0x1027095d` (and the identical `0x10270b10`).

    ``plane_k[y][x] = lut_k[(int16) plane_k[y][x]]``, in place in the DLL and
    by value here.  The index is a ``movsx word`` so it is signed, and the
    LUT the vendor indexes with it starts at 0 -- a negative pixel would read
    before the buffer.  It cannot on this path (the planes are RPD-12), and
    `flesh_shift_lut` returns a list, so Python would wrap; this checks.
    """
    out = []
    for pl, lut in zip(planes, luts):
        rows = []
        for row in pl:
            new = []
            for v in row:
                i = _to_i16(v)
                if not 0 <= i < len(lut):
                    raise ValueError(
                        "pixel %d indexes fcn.10270050's %d-entry LUT out of "
                        "range at 0x10270928; the vendor's `movsx` would read "
                        "outside the allocation" % (i, len(lut))
                    )
                new.append(lut[i])
            rows.append(new)
        out.append(rows)
    return out


# --- the assembled forward chain --------------------------------------------


def flesh_forward_delta(
    lst_planes,
    stat_planes,
    shifts,
    *,
    params: FleshParams,
    tables: "FleshCondProbTables",
    exposure: float = 0.0,
    second_prepass: bool = True,
    weight=None,
):
    """`fcn.10270280` end to end: three colour planes in, ``Delta`` out.

    Every *stage* below is tier 1 (bit-exact against the real DLL under
    Unicorn, in one of the four stage harnesses), and so is the **assembly**:
    `pakon_flesh_whole_golden.py` runs `fcn.10270280` as one function on the
    same pixels and diffs its results struct and four of its internal
    buffers against this function — 58,462 values, 0 differences.

    ``lst_planes`` is `fcn.10270280`'s arg3 -- the image `fcn.102a1500`
    measures the skin probability on, and whose dimensions the weight plane
    is built at.  ``stat_planes`` is arg4 -- the image the reduction sums
    ``L = R+G+B`` over, and which the weight plane is padded up to.

    **On the colour-negative path these are the same image**: both are
    `copyToIemImage` of the one `AnsImageData` at `scene+0x04`, pushed
    twice at `0x100fe396`/`0x100fe397` (module header).  Passing the same
    planes as both arguments is therefore correct, not a smoke test, and
    the pad is an identity.  They differ only on the DC_Premium path.

    ``second_prepass`` is arg8: when set, the LUTs are applied to the arg3
    image too (`0x102709b2`).  It defaults to ``True`` because the colour-
    negative caller pushes the literal `1` for it at `0x100fe392`; the
    ``False`` control in `pakon_flesh_weight_golden.py` shows the switch is
    not cosmetic (it takes the same frame to `fleshCount = 0`).

    Returns a dict with every intermediate, so a caller can see *why* a
    Delta came out the way it did rather than just what it was.
    """
    st = flesh_apply_shift_luts(stat_planes, flesh_shift_luts(shifts))
    lst = lst_planes
    if second_prepass:  # 0x102709b2 / 0x10270ab9
        lst = flesh_apply_shift_luts(lst_planes, flesh_shift_luts(shifts))

    height = len(st[0])
    width = len(st[0][0])
    # 0x102706fe: both insets come from the arg3 image's own dimensions.
    b_outer = flesh_border(len(lst[0]), params.clip_amount)
    b_inner = flesh_border(len(lst[0][0]), params.clip_amount)

    prob_f32 = flesh_probability_plane(lst, params, tables)
    prob_i16 = flesh_prob_to_int16(prob_f32)
    threshold = flesh_threshold_from_plane(prob_i16)
    plane = flesh_reduction_plane(prob_i16, threshold)
    clamped, any_flesh = flesh_clamp_plane(plane)

    if weight is None:
        weight = flesh_reduction_weight_plane(height, width, params)

    if not any_flesh:  # 0x10271246 je 0x10271607
        stat = nsum = 0.0
        count = 0
        # `0x1027122c xor eax,eax` then `0x10271607 mov [esp+0x1c], eax` —
        # the no-flesh branch OVERWRITES the -1 the accumulator was seeded
        # with at `0x1027123e`, so `maxProb/255` at `results+0x20` is 0.0,
        # not -1/255.  Caught by `pakon_flesh_whole_golden.py` running the
        # whole function; this port said -1 until then.
        max_prob = 0
    else:
        stat, nsum, count, max_prob = flesh_accumulate(
            clamped, weight, st, float(threshold),
            rows=flesh_loop_rows(height, b_outer),
            cols=flesh_loop_cols(width, b_inner),
        )
    area = flesh_area(len(lst[0]), len(lst[0][0]), b_inner, b_outer)
    res = flesh_results(
        stat=stat, nsum=nsum, flesh_count=count, max_prob=max_prob,
        area=area, exposure=exposure, params=params,
    )
    res.update({
        "threshold": threshold,
        "any_flesh": any_flesh,
        "flesh_count": count,
        "max_prob": max_prob,
        "area": area,
        "b_inner": b_inner,
        "b_outer": b_outer,
        "stat_raw": stat,
    })
    return res


# --- shipped data -----------------------------------------------------------

REPO_FLESH_DIR = (
    Path(__file__).resolve().parents[3]
    / "vendor"
    / "ansel"
    / "anselinstalldir"
    / "dataPathItems"
    / "flesh"
)
DEFAULT_DPI = REPO_FLESH_DIR / "FleshDPI" / "flesh-srcType-metric-default-default.dpi"
COND_PROB_DIR = REPO_FLESH_DIR / "CondProbTables"

#: md5 of the three shipped tables, cited rather than assumed.
COND_PROB_MD5 = {
    "condProbTbl-l.tbl": "9cd403ca76e273323844773d6515a98e",
    "condProbTbl-s.tbl": "cf30e859fd0b2fe0eb17ea9f77fb55ee",
    "condProbTbl-t.tbl": "73a1ca01664c6dca8d411d042e34e001",
}


@dataclass
class FleshCondProbTables:
    """The three 32-bin conditional-probability tables, as doubles."""

    l: list[float]
    s: list[float]
    t: list[float]


def parse_cond_prob_table(path: str | Path) -> list[float]:
    """Parse a shipped ``condProbTbl-*.tbl``.

    Plain text: ``#`` comments, ``size = N``, then ``vals =`` followed by
    ``N`` whitespace-separated floats.  The file format is read from the
    files themselves, not from the DLL — the loader was not disassembled,
    so this is **tier 4** for the *format* while the *use* of the resulting
    32 doubles is tier 1.
    """
    text = "\n".join(
        line.split("#", 1)[0] for line in Path(path).read_text(errors="replace").splitlines()
    )
    size = None
    for tok in text.replace("=", " = ").split("\n"):
        if "size" in tok:
            parts = tok.split()
            if len(parts) >= 3 and parts[0] == "size":
                size = int(parts[2])
    if size is None:
        raise ValueError(f"{path}: no 'size =' line")
    head, _, tail = text.partition("vals")
    vals = [float(v) for v in tail.partition("=")[2].split()]
    if len(vals) < size:
        raise ValueError(f"{path}: {len(vals)} values, expected {size}")
    return vals[:size]


def porting_state(prefix: str = "        ") -> str:
    """Every ``*_PORTED`` flag in this module, one per line.

    Every flesh harness prints this at the end of its run, so the porting
    state is a fact in the record rather than something a reader has to
    infer from which harness passed.
    """
    names = sorted(n for n in globals() if n.endswith("_PORTED"))
    return "\n".join(f"{prefix}{n} = {globals()[n]}" for n in names)


def default_params() -> FleshParams:
    return parse_flesh_dpi(DEFAULT_DPI)


def default_cond_prob_tables(params: FleshParams | None = None) -> FleshCondProbTables:
    """Load the three tables the shipped DPI names.

    ``lCondProbKey -> P+0x38``, ``sCondProbKey -> P+0x3c``,
    ``tCondProbKey -> P+0x40`` — which is what the loader
    (`AnsFleshCapabilityImpl::AnsFleshCapabilityImpl`, `fcn.101c84f0`) does
    and what the vendor's own DPI dump `fcn.1026f5a0` calls those three
    offsets.  See the module header and
    ``FLESH_COND_PROB_SLOT_ASSIGNMENT_PORTED``.
    """
    p = params or default_params()
    keys = p.keys
    return FleshCondProbTables(
        l=parse_cond_prob_table(COND_PROB_DIR / keys.get("lcondprobkey", "condProbTbl-l.tbl")),
        s=parse_cond_prob_table(COND_PROB_DIR / keys.get("scondprobkey", "condProbTbl-s.tbl")),
        t=parse_cond_prob_table(COND_PROB_DIR / keys.get("tcondprobkey", "condProbTbl-t.tbl")),
    )


if __name__ == "__main__":  # pragma: no cover - smoke
    p = default_params()
    print(f"parsed {DEFAULT_DPI.name}:")
    for key, (off, fmt) in FLESH_PARAM_LAYOUT.items():
        print(f"  +0x{off:04x} {fmt:4s} {key:24s} = {getattr(p, p._FIELD_BY_KEY[key])}")
    for k, v in p.keys.items():
        off = FLESH_PARAM_STRING_LAYOUT.get(k)
        print(f"  +0x{off:04x} str  {k:24s} = {v}" if off else f"  (str) {k:24s} = {v}")
    tabs = default_cond_prob_tables(p)
    print(f"  cond-prob tables: l/s/t peaks at bins "
          f"{tabs.l.index(max(tabs.l))}/{tabs.s.index(max(tabs.s))}/{tabs.t.index(max(tabs.t))}")
