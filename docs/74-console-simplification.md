# 74 — Console simplification: one page, tabs, no explanations

Design spec for the UI rework agreed in chat, approved against an interactive
mockup (published as a Claude artifact, not checked into the repo — this doc
is the durable record). Supersedes the three-step (Scan → Edit → Export) shell
described in `App.jsx`'s current header comment.

## Why

The console reads like an engineer's bench: a machine-state rail with lamp
temperature and register numbers, `<Info>` popovers explaining *why* on nearly
every control, transport speed and lamp-refresh knobs on the scan sheet, and a
mode switcher that puts Config/Diagnostics/Calibration next to the three steps
of the actual job. That is the right UI for bringing the F-135 back from the
dead. It is the wrong UI for scanning a roll of film. Everything below the
"why" is either genuinely a scanning-time concern or it is not user-facing
software at all — this pass draws that line and removes everything on the
wrong side of it.

## What is being removed

- **Config / Diagnostics / Calibration as navigation.** Their screens
  (`Config.jsx`, `Info.jsx`) and the `TOOLS` mode switcher in `components.jsx`
  come out of the app shell entirely. The API calls they use stay in `api.js`
  — nothing server-side changes — the entry points just disappear from the UI.
  If a future need for on-machine diagnostics resurfaces it gets its own
  decision, not a grandfathered menu item.
- **The machine-state rail** (`machineRows` in `App.jsx`, the `<State
  rows={machine}>` block on Scan and Review). Lamp status/temperature, USB
  identity, transport register, calibration bookkeeping — none of it is a
  scanning decision, it's a debugging aid. The one fact from that rail a user
  actually needs — *can I scan right now, and if not why not* — survives as a
  single blocked-state line in the Scan Roll modal (see below).
- **Every `<Info>` popover**, and the component itself goes unused. Labels
  state what a control is; they stop justifying themselves.
- **Scan-time settings that aren't about the scan you asked for**: transport
  speed override, lamp refresh toggle, "derive exposure" cross-check. These
  are recovery/debug tools for a specific hardware failure mode (the lamp
  dying at 60s) that belong to whoever is nursing the machine, not to someone
  scanning a roll. They come out of `StartSheet` entirely; the backend keeps
  its existing defaults (`lamp_refresh_s`, calibrated speed for the chosen
  base) and the app no longer offers to change them.
- **The three-step wizard bar** (`Steps` in `components.jsx`, `stepRows` in
  `App.jsx`) and the top mode-switcher bar (`TopBar`). Replaced by the tab
  strip and toolbar below — there is no "step" concept once scan/edit/export
  live on one page per roll.

## What stays, unchanged in behavior

- The render pipeline, job polling, export planning/collision flow
  (`planExport`/`CollisionSheet`), apply-to-roll confirm sheet, undo, and the
  boundary-correction backend calls (`boundary`, `redetect`) — all reused
  as-is through the existing `api.js`.
- The cleanup dialog for leftover captures from a crashed session
  (`CleanupDialog`) — still runs on boot, unchanged. It is not a workflow
  screen, it's a one-time disk-hygiene prompt.
- **Boundary editor** — kept, per decision: tucked behind a small "Fix
  frames" button (contact sheet toolbar and frame-editor action bar), not
  exposed until asked for. Same drag-to-move/split/merge/redetect tool, its
  `<Info>` explanations stripped along with everywhere else.
- **Open capture** — kept, per decision: a secondary "Open existing
  capture…" link on the empty-tab screen, next to the primary "Scan a roll"
  button. Same dialog, same `api.openCapture`/`lookupFilm` flow underneath.

## Shell

```
┌ tab strip (Chrome-style) ──────────────────────────────────┐
│ [Portra 400 · Aug 7] [● Gold 200 · Aug 5] [New scan] [+]   │
├ toolbar ─────────────────────────────────────────────────────┤
│ Portra 400 · Aug 7   36 frames   [Contact sheet|Frame] [Export…] [☾]│
├ main view (swaps per active tab's state) ───────────────────┤
│  Empty  │  Scanning  │  Contact sheet  │  Frame editor       │
└──────────────────────────────────────────────────────────────┘
```

**Tabs** are driven directly by `rolls` (from `api.rolls()`), one tab per open
roll, plus one ephemeral "New scan" tab that exists only while its scan job
or decode is in flight and turns into a real roll tab the moment
`api.rolls()` includes it (mirrors the existing auto-open effect in
`App.jsx` — that effect's logic does not change, only what renders while it
runs). A tab whose roll is not the active one but has a scan running shows a
small spinner ring in place of its close button — this is the existing
"scans survive navigating away" architecture (`scanJob` lives in `App` state,
above any screen), now made visible per-tab instead of only in a global step
bar. Closing a tab calls `api.closeRoll(id)`; it does not delete anything on
disk.

**Toolbar** shows the active roll's name/frame count, a two-way switch
between Contact sheet and Frame views (mirrors `sel`), the Export button, and
the theme toggle. No brand wordmark, no chip row — those belonged to a title
bar that had to state which of five screens you were on; there is only one
screen now.

**Main view** is a straight state swap on the active tab, no routing:

| State | Shown when | Replaces |
|---|---|---|
| Empty | tab has no roll and no scan job | old boot-into-Scan-step |
| Scanning | tab's scan job is running | `Live` in `Scan.jsx` (kept, machine telemetry stripped to elapsed/frames-found/verdict) |
| Contact sheet | roll loaded, no frame selected for editing | `ContactSheetModal` (promoted from modal to the default view) |
| Frame editor | a frame is selected | `Review.jsx`'s centre+right rail (kept almost unchanged) |

## Scan Roll modal

Replaces `StartSheet`. Fields: **Roll name**, **Film** (Colour neg / B&W
segmented — Positive still omitted, still unsupported), **Quality** (Base
4/8/16 segmented, one caption line "Faster ↔ Sharper — Base 16 is calibrated
for best colour", no per-option tooltip). Start button. If `blockedReason()`
(kept from `Scan.jsx`, unchanged logic) says the scanner can't run right now,
the Start button becomes "Recheck scanner" and one line under it states the
reason in plain words (`blocked.title`) — this is the one place hardware
state still surfaces, collapsed from a whole rail to a single line.

## Frame editor

Centre stage unchanged (image, rotate/flip, reject/accept). Right rail keeps
the histogram plot and the full slider stack (Exposure, R/G/B, Brightness,
Contrast, Saturation, Highlights, Shadows, Sharpening) plus Reset/Apply to
roll/Undo — this is the "powerful to edit" half of the brief and none of it
is scanning-setting clutter, so it stays close to what `Review.jsx` already
does. What changes is furniture only: no `<Info>` buttons, no capture-settings
read-only fields (film path/resolution/DX shown elsewhere now, not repeated
here), no machine-state block.

## Export modal

Replaces the `Export.jsx` screen with a modal, opened from the toolbar.
Thumbnail grid, one cell per frame, **all frames selected by default except
already-rejected ones**, click to toggle, Select all/Select none. Below the
grid: destination path field with a **Browse…** button (`window.pakon
.chooseFolder`, already implemented and used today), **Format** segmented
(JPEG / TIFF / PNG — all three already exist in `Export.jsx`'s `FORMATS`),
and **Colour** segmented (sRGB·8 / Linear·16 — kept because it's a real
8-bit-vs-16-bit decision, not an explanation of one). The naming template and
its token chips are kept but demoted to a collapsed "Rename pattern"
disclosure under the format row, default closed. `CollisionSheet` is reused
unchanged — a plan that would overwrite files still stops and asks.

## Data flow / state

No change to where state lives: `scanJob`, `exportJob`, `autoOpen`, `roll`,
`rolls` all stay lifted in `App.jsx` exactly as now, for the same reason the
current header comment gives (a job must outlive the screen showing it). What
changes is purely what `App.jsx` renders: the tab strip + toolbar + one of
{Empty, Scanning, Contact sheet, Frame editor} instead of `TopBar` + `Steps` +
{Scan, Review, Export, Config, Diagnostics, Calibration}. `mode` collapses
from a six-way screen switch to `activeTabId` + a per-tab `view: 'contact' |
'editor'`.

## Testing

No backend changes, so no new API tests. Manual pass through: simulated
scanner (`PAKON_SCAN_SIMULATE`) end to end — new tab → Scan Roll modal → scan
→ auto-opens into Contact sheet → open a frame → adjust with sliders →
Reject one → Export (verify rejected frame is excluded by default, verify
Browse/format/colour, verify a real collision still stops the export) →
switch tabs mid-scan on a second roll to confirm the background-scan
indicator and that switching tabs never interrupts the job. Both themes.
