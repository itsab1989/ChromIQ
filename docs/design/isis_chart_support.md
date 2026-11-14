# X-Rite i1iSis family: chart creation (Beta)

> **These specifications are binding.** They must be consulted before changing
> code in the area they cover, and a fault that contradicts one is reported and
> approved before it is implemented; the specification may be the part that
> needs to change.

## ⏳ Awaiting confirmation: what the i1iSis chart Beta does (2026-11-14)

**Confirmed by:** *nobody yet.*

*Written from the owner's requests and rulings of 2026-11-14 (the Beta; the
old entry removed for everybody without migration; the header notes band in
the first version, off by default; every layout option open unless it has no
meaning or makes the chart unreadable) and the study
`ChromIQ-work/2026-11-14_isis_chart_study` (REQUIREMENTS v2, PROPOSAL v2, the
challenge and the response). What the app does, verified by tests and on
screen without an instrument. Nobody on the project owns an i1iSis; no
ChromIQ chart has been read by one.*

### The option

* Preferences > Beta, "X-Rite i1iSis charts (beta)", off by default, restart
  to apply (`workflow/isis/support.py`, setting `isis_charts_beta`).
* Ticking it opens a consent window first (no icon, "Keep it off" the
  default, "Turn it on" marked as the risky choice). Cancel leaves it off;
  unticking asks nothing; ticking again asks again.

### Off: ChromIQ is 4.3.37, with one deliberate exception

The printtarg instrument "i1iSis (via i1Profiler)" and its help bullet are
gone (the owner's ruling, see `issue_182_answers.md` §2y/§2z and the note
below §2z); a stored `isis` (Save as Defaults, a preset, a target's settings,
a 4.3.36 project) reads as no instrument (i1Pro, A4; the entry's own A3+, -n
and -P with it) with one log line, nothing written back until the person
saves (`data.patch_db.REMOVED_INSTRUMENT_CODES`,
`ui.tabs.tab_chart._saved_beta_instrument_is_off`). Start on an i1iSis chart
shows M-ISIS-SUPPORT-OFF. Nothing else of the i1iSis is offered, loaded or
read; a target made with the Beta on keeps its stored values untouched.

### On: Create Chart

* One entry, "i1iSis family" (code `XRISIS`), in Guided, Manual and the
  layout panel, with a model width: "i1iSis / i1iSis 2" (sheets up to 230 mm,
  right marker up to 218 mm from the paper's left edge) or "XL models" (330
  and 318 mm). Laid out by ChromIQ's layout engine only.
* Furniture as i1Profiler 3.8.8 draws it: the black bar 6 mm high, its top
  at header + 0.5 mm (header 32 to 80 mm, default 32), across every column of
  a full page; 6 mm clear under it (20 mm with the barcode); a 5 x 2.5 mm
  diamond at both ends of every row, 5 mm from the chart edge and 5 mm from
  the patches (4 and 3 with tight margins); patches side by side without
  gaps, 6 to 20 mm each way (default 6 x 6); trailer at least 25.5 mm; chart
  at least 171 mm long and at least 60 mm wide (white beyond the right
  markers when narrower); two feed arrows in the diamond columns; a dashed
  outline; the name and page line and the corner labels in the first 12 mm,
  the bottom corner labels in the last 3.5 mm.
* The grid is i1Profiler's rule (T = ceil(N / Cmax), P = ceil(T / Rmax),
  R = ceil(T / P), C = ceil(N / (R x P)); column-major; unused cells at the
  end white), reproducing all 38 layouts measured in i1Profiler.
* Placement: the chart's outline top-left inside the page margins (default
  5 mm), moved by Manual's patch area alignment and the chart offset.
* The cut rule: a sheet may be fed as printed when, from the paper edges, the
  paper is 60 to 230 (XL 330) mm wide and 170 to 660 mm long, the right
  marker within 218 / 318 mm, the bar's top within 80 mm of the leading edge
  and the left marker at least 3 mm in; otherwise the chart is still made and
  every instruction says to cut along the dashed outline. Refused
  (M-ISIS-SHEET-CHECK) only what cannot be read even when cut. More than 3000
  patches a page, or a chart over 660 mm, takes more pages instead.
* Options: as the options table of PROPOSAL v2 §4; greyed with their own
  reason are the spacers and gaps, edge spacers, patch and spacer scale, the
  mode row, offset strips and hexagons, "Don't cap strip length", the side
  clip band and "Clip", the ruler helper markers; in this version also the
  area-first layout and the engine's own strip and row label boxes and their
  rotation, underline, alignment and offsets (the chart's own strip letters
  and row numbers are in its group). Every option persists through Save as
  Defaults, presets, the target's settings and the chart's record.
* The notes band (off by default): in the header (the header grows by the
  band's height, up to 80 mm; the band ends 20 mm above the bar) or the
  trailer (from 22 mm after the last row), filled by the clip-border content.
* Papers in Guided: A4, Letter, A5, 5 x 7 in, 8 x 10 in; with XL also A3,
  11 x 17 in and A3+ (329 x 483). Manual: every engine paper and Custom.
* Every run type (profiling, verification, calibration) makes i1iSis charts
  in its usual folder.

### On: Files

`<stem>.isis.json` (every element in mm, the grid, the barcode text per page,
fed as printed or cut); in `exports/`, `<stem>-i1profiler-isis.txf` (device
"i1iSis" or "i1iSis XL", a custom page half a patch larger than the grid both
ways, the margins, patch size as slider percent, header percent, tight
margins, barcode, the patch list in placement order with ChromIQ's names) and
`<stem>-i1profiler-isis.order.json`; the `.pxf` beside every chart names the
device i1Profiler writes. RGB charts only for the `.txf` in this version.

### On: Measure and import

Start shows M-ISIS-NOT-YET before anything is armed: the i1Profiler steps, the
grid to check, the cut instruction, and for several pages that bringing them
back needs a later version. Import Measurement pairs a one-page measurement
through the order file (by position, checked by the device values); a
measurement of several pages is refused with a sentence saying so.
