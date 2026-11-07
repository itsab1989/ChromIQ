# Independent FD-9 measurement integration (experimental)

ChromIQ's normal Measure tab can acquire supported FD-9 Ethernet charts without
FD-S2w, a manufacturer SDK or the OpenRIP working backend. The GPL-3.0-or-later
standard-library driver is included as source under `vendor/fd9-independent`,
with its license, protocol observations and provenance statement. All three
platform packaging specifications include it; packaged-converter smoke tests
have been run on macOS. Windows/Linux device access has not been validated.

The normal workflow uses the FD-9 firmware to apply its own factory
characterization. No manufacturer host software, external conversion profile,
reference measurement or user comparison is required. ChromIQ uses its existing
bundled D50 and 1931 2-degree data for XYZ/Lab integration. Manufacturer
numerical assets and private validation fixtures are not bundled. The author has seen earlier vendor-derived analysis; this is not a
certified clean-room implementation. See the vendored provenance document.

## Setup and supported charts

A TI2 naming `TARGET_INSTRUMENT "FD-9"` and a matching `.fd9.json` physical-layout
sidecar select this path. Chart import, copy and rename preserve the sidecar.
`workflow.fd9.measurement.prepare_chart` wraps an existing supported layout in
TI1/TI2 files; it neither prints nor changes the physical target. Current support
is regular rectangular grids with four marks,
including CMYK+N device values. Arbitrary chart recognition is not implemented.
The four marks are symmetric: they validate geometry, not chart identity or
180-degree orientation. Supply the matching sheet arrow first, printed face up.
After each sheet, `workflow/fd9/page_check.py` compares the measured lightness
pattern with the .ti2 aims for the expected page, the page turned round and
every other page with the same grid, and refuses to file the sheet when
another hypothesis fits clearly better (M-FD9-SHEET-TURNED,
M-FD9-WRONG-SHEET). It is conservative and stays quiet when it cannot decide
(few patches, little contrast, a pattern that looks the same turned round).

In Measure, open FD-9 setup and supply the instrument's Ethernet address.
Select M0, M1 or M2. Selecting an FD-9 chart automatically uses the independent
driver; there is no separate enable checkbox. There is no
profile or reference-file selector. The driver checks factory-record integrity
on the current device, reads its spectral model, and calculates all three
conditions from each factory-calibrated row packet. Only the selected condition is filed as the project's TI3; the session
retains all three for later export without another sheet insertion.
The bundled driver is used by default. The developer command-line tool also
supports a source override. Other FD-9 clients must be disconnected.

## Measurement and interruption

Start Measurement waits for insertion, pre-scans, checks the four marks, measures
on the retained sheet, homes and ejects. A worker owns the instrument lease and
keeps the computer awake only while active. Project `fd9-sessions` preserve the
chart, pre-scan, geometry, raw records, wire transcript and conversion provenance.
The TI3 retains sample IDs, locations and original CMYK+N values, and declares
`CALIBRATED_REFLECTANCE "YES"`, `FD9_CONVERSION_SOURCE "INSTRUMENT_MODEL"`
and `FD9_EXPERIMENTAL "YES"`. This describes where factory calibration is
applied; it does not assert independent ISO certification or cross-unit validation.
Spectra use 36 bands, 380–730 nm. Reflectance is exported on a percent scale
without clipping fluorescence. Since 4.3.24, XYZ/Lab are worked out by
ArgyllCMS's own method (`workflow/argyll_colorimetry.py`, D50, 1931 2-degree,
1 nm, as `spec2cie`), recorded as `CHROMIQ_XYZ_METHOD`; a .ti3 without that
keyword used the earlier 10 nm sums, and a Resume of it continues with them,
so one measurement never mixes the two.

Stop and Quit use ChromIQ's shared Save/Discard/Keep ending question. Save keeps
only verified, acknowledged complete rows, writes a partial TI3 and archives the
prior canonical measurement. Discard preserves the prior canonical measurement.
Keep leaves a live acquisition running. If the connection has already failed,
Keep retains the staged readings and offers an explicit Continue; recover the
sheet with instrument controls before restarting. It does not retry motion
silently. Quitting waits for the worker to close before destroying its window.
No unverified motion-cancel command is sent; a stopped sheet may remain loaded.

Resume accepts only a consistent prefix of whole rows from the same chart,
condition, conversion source, endpoint and bundled colour data. The saved
factory and spectral-model fingerprints must match this device before the
insertion screen opens. Older partial sessions using firmware-native getters
retain their original conversion path on Resume. It re-scans the reinserted same sheet
and requests the remaining rows, retaining earlier readings unchanged. Invalid
or complete inputs are rejected before motion. Concurrent changes to the
canonical measurement are detected before replacement. Only complete results
signal completion to the existing profiling/report workflow.

Factory-native partial Save/Discard/Keep and suffix-resume are covered by
portable synthetic workflow and UI tests. The earlier raw/profile path passed
300-patch GUI acquisition and physical stop/resume on one unit. The new native
batch path passed 21 positions across seven rows, including dark mixtures,
paper white and calibration renewal (2026-11-02). All three conditions matched
isolated offline manufacturer calculations on identical raw entries within
4.8e-7 reflectance. Those comparisons are development checks, never user setup
requirements, and their fixtures are excluded. A 460-patch native GUI acquisition on a 20-column sheet passed. The new
automatic-row conversion matches those 460 raw entries plus the earlier 21
within 4.8e-7 reflectance. The combined automatic-row path then completed the user-created and printed
460-patch chart at normal speed, using 23 row commands and no extra finite
per-patch acquisitions. Its physical Stop/Resume check remains pending.
Other devices/firmware and Windows/Linux access remain untested.

## Command-line and tests

`python tools/run_fd9_independent.py --help` exposes explicit live capture or
verification/export of a saved factory-native session. Supply `--session`,
`--layout` and `--allow-experimental`; live `--scan` also requires `--host`.
`--driver-source` is optional. No profile, SDK or CIE file arguments are needed.
Export folders must be new; existing evidence is not overwritten. Outputs are
condition-labelled TI3 files for M0, M1 and M2 from the same acquisition.

Run `pytest tests/test_fd9_*` for integration checks and the vendored README's
unittest command for the independent library. Portable tests use invented
frames, factory records and geometry. Legacy research-export API tests remain
for existing local sessions; that conversion is not exposed by the normal GUI
or command-line workflow. A full `pytest --runslow -n auto` is required before
any merge decision.

## Scan preview and live progress

Automatic factory-calibrated jobs now alternate row travel direction: first
increasing sensor X, then decreasing X, repeating within the sheet. Each new
sheet or resumed pass starts increasing X, irrespective of its original row
number. Progress and live colours use the actual acquisition locations; TI3
rows remain in logical chart order so whole-row prefix resumes stay stable.
The capture's `progress.json` records `row_order` as `alternating-x-v1` or
`increasing-x-v1`. Missing means the historical increasing-X policy. Unknown
policies and declared order that disagrees with wire commands are refused.
The legacy native-point reference backend remains forward-only. No extra device
command, exposure, calibration write or conversion is added. Synthetic checks
pass. A two-page GUI run then measured 2,040 patches using alternating rows
and automatic handoff. Against the same sheets measured forward-only, median
M0 repeat difference was 0.177 delta E76 (maximum 1.382). Every exported M0
spectrum matched its verified raw/model sample under the correct patch ID.
This is a one-unit repeat comparison, not an absolute accuracy certification.

Once the pre-scan geometry passes, Measure shows the actual grayscale scan in
feed orientation with skew-corrected patch outlines. Pending rows have cyan
outlines, the next row is amber, and completed rows are green. These marks show
acquisition progress, not colour-quality verdicts. The original scan is retained
unchanged; the display image and cell geometry are derived evidence. A matching
saved measurement reloads its scan when the project is reopened.

The header progress updates after each native point and respects
the existing progress-bar preference. Resume starts from the saved patch count
and adds only new locations; repeated notifications do not inflate the total.
Discard restores progress from the prior canonical measurement. A scan-display
failure leaves measurement and evidence preservation working normally.

## Creating printable charts

Choose **FD-9** in Create Chart, select a listed sheet (or Manual’s ordinary
Custom paper entry), set Pages and use **Generate Chart**. The ordinary Print and Measure
tabs receive the resulting chart automatically. Guided uses targen's RGB patch
recipe; Manual also accepts ChromIQ's CMYK and CMYK+N recipes or existing TI1
patch sets. TIFF pixels retain device channels, including distinct light inks.
Optional vector PDF uses the same patch geometry and named inks.
Calibration targets start each pure single-ink ramp in a fresh column, with its
own paper white. Long ramps continue in the next column; unused cells remain
white. Eleven 25-level ink ramps fit a 300-cell sheet. Longer targets continue on additional sheets. The chart keeps nominal values while printer
calibration, when selected, affects only the printable colors.

The default grid uses the selected sheet area with 8 mm patches and 1 mm white gaps.
A4 fits 500 patches, Letter 460, A3 1,102 and 330 × 660 mm 2,145. Charts can span multiple sheets. Width is 137–330 mm and length 170–660 mm in feed
orientation. Side fiducials have 4 mm of paper outside their outer edges;
the upper/lower clear areas retain the transport allowances. Larger requests are split into numbered page TIFFs, one PDF and one TI2.
The last page pads complete columns only. Variable columns and rows flow
through TI2/FD9 geometry, command point counts, wire verification, row progress,
partial saves and suffix resume. Locations continue A..Z, AA..AG on wide sheets.

The expanded grid is validated with invented transport and full 2,145-point
partial/resume tests. A 20-column, 460-patch native GUI print/measurement completed on one unit.
The automatic-row factory conversion also passed the 20-column chart at
normal speed. Larger variable-width sheets remain untested. No hardware capacity
or ISO certification claim follows from the larger PDF/TIFF outputs.

Feed arrow first, printed face up, at actual size. Sheet size, seed, geometry
and patch identities travel with the chart. Reopening/importing preserves
existing print files. Changes take effect on Generate. Printer calibration is
applied to print pixels when requested; TI2 retains nominal device values. CAL
tables and total ink limits pass into measurements, including partial saves and
Resume. Native acquisition uses the instrument’s own factory characterization
and uses the independent backend automatically for FD-9 charts.

Tests cover RGB/gray/CMYK/eleven-channel pixels, sheet limits, registration at
scan resolution, calibration and ink-limit filing, seed/precision, dotted names,
and tab handoff. The user-created Letter chart has passed print/scan validation
on one unit; larger and smaller-patch layouts still need physical checks. Arbitrary grids,
auto feeding and certified ISO measurement are not supported.

Patch width and height use the standard layout panel, independently from
6 to 30 mm. Its inter-patch gap controls separation along the feed and its strip
gap controls separation across the feed, each 0..5 mm. Zero means touching.
Choosing the FD-9 loads its own stored layout (Preferences > Chart Layout;
default 8 x 8 mm with 1 mm gaps) into Manual's controls, never the previous
instrument's values, and leaving it gives those back. Guided never reads
Manual's panel: it uses a loaded FD-9 layout, Save as Defaults, or the FD-9's
Chart Layout preset, with Guided's own resolution and options. The greyed
controls show what an FD-9 chart uses: its fixed margins (38/15/33/15 mm),
no spacers, patch first. The 33 mm at the trailing end stays: the owner of
the unit confirmed (4.3.26) that the FD-9 still holds the sheet in its
rollers while it reads the last row, so the clear area after it is what the
transport needs and is not spare paper to be given to patches.

The page number "N/M" at the top left of each sheet of a multi-sheet chart,
and the FD-9 clip border in the trailing clear area, are printed upright: they
read the right way up with the arrow pointing up. The FD-9 is fed from the
front, with the person standing in front of it, so the arrow pointing up, away
from them, is already how they read the sheet; 4.3.25 printed both turned
180 degrees, which was upside down for exactly that person. The clip border is
on by default since 4.3.26: on real sheets the extra labels read fine and the
four marks were found every time. Every page that carries either one still
goes through the detector check (`workflow/fd9/sheet_check.py`) before the
chart is written.
Edit layout defaults opens Chart Layout preferences, never printtarg for FD-9.
The extra FD-9 dialog and Guided Custom sheet button have been removed.
Legacy equal-gap recipes and schema-1 physical charts are still read.

Multi-page charts use schema 2 with a per-page physical grid and globally unique
patch IDs/locations. Each sheet is pre-scanned and measured on the retained
sheet using the existing single-sheet acquisition; the shared page-pause panel
announces the automatically queued next sheet after ejection/disconnection.
The worker waits read-only for mechanism 2 and paper 0 before loading again,
but only after a sheet this same Start has ejected: a Resume that begins at
page 2 or later starts like a first page, because the wait returns only on a
sensor notification an empty sensor may never send (review of #214, M3);
the notice closes when the insertion prompt appears, without Continue. Stop
still preserves completed pages while waiting for the exit sensor. Earlier pages stay
in the same measurement, including on partial Save/Resume. Session evidence is
nested by page below the normal per-Start fd9-sessions directory. Page numbers
are printed for the operator: four symmetric marks cannot prove page identity,
so the readings are checked against the chart after each sheet (see Setup).
Synthetic tests cover generation, second-page failure, cross-page resume,
previews and the automatic handoff. A two-page, 2,040-patch M0 run and page-2
resume passed on one unit; its first 1,020 readings were unchanged. That run
used forward-only rows and the earlier manual handoff. A follow-up run on the
same two sheets then passed alternating rows and automatic exit-sensor handoff,
with both pages combined into one 2,040-patch M0 measurement. Stop/Resume within
a descending row remains covered by synthetic tests only.

The detector finds four isolated square fiducials and uses the declared grid;
it does not detect each colour patch. Patch gaps and square patch shapes are
therefore not recognition requirements. The fiducial clear areas are retained.
Synthetic scan tests cover touching rectangular grids. Physical validation of
rectangular/smaller/gapless patches is pending; paper bleed or registration error
may affect real measurements.

At zero gap, shared raster edges prevent slivers or overlaps. At the six-mm
floor, pixel quantization can increase the effective dimension slightly; that
realised geometry is also used for capacity, PDF paths and the physical
measurement definition. Requested sizes remain in generation metadata. Existing
printed charts retain their original definitions; changes take effect on Generate.
Manufacturer size reference (each dimension 6..30 mm):
https://www.konicaminolta.com/instruments/download/instruction_manual/software/pdf/fd-s2w_instruction_eng.pdf

Factory/native acquisition reads integrity-checked sensor records and obtains
calibrated row packets from the firmware. Unit calibration remains on
the instrument. The host reads the version-gated response matrix and condition
illuminants once and calculates M0/M1/M2 without extra per-patch acquisitions. Older
local fitted-profile research functions remain available for historical data,
but are not offered as a user conversion option in this integration.

Automatic row sequencing sends a single controller request for every row,
retaining the device's own patch-stop timing, periodic calibration and final
ejection. This does not claim physically continuous motion. Scan preview,
per-point progress and completed-row highlighting remain available; interrupted
sessions recover only fully converted and wire-verified rows. New sessions save
the model read from that connection alongside raw and converted data. Only
sensor version 1.0.0.2 currently has an established read layout; other versions
fail before model memory reads and before the insertion screen.

The scan preview uses the normal Live preview controls: measured colours,
expected colours, or their diagonal split, with the usual patch values on
hover. Selected-condition XYZ is queued from the acquisition worker after each
reading; the GUI does not poll the device or partially written files. Colour
fills follow the four-point skewed cells and leave gaps untouched. Completed
rows retain their status outline. A resumed prefix is remapped to the new scan,
including staged unsaved readings; reopening restores colours from the saved
measurement for RGB, gray, CMYK and CMYK+N charts. Preview errors cannot change
or discard spectral measurements.

With the system print dialog, the edge note (M-EDGE-NOT-PRINTED) on the
Print and Create Chart tabs is about the printer that dialog last printed to,
never the hidden direct-print queue, which may name an unrelated printer
(`workflow/printer_edges.py::note_printer`). Until something has been printed
through the dialog it is about the system's default printer, the one the
dialog opens on. ChromIQ's own route is unchanged.
