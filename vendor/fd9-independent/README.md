# Independent FD-9 package (0.5.5)

GPL-3.0-or-later; Python 3.10+, standard library only. This reusable package
implements experimental Ethernet acquisition and factory-calibrated
M0/M1/M2 conversion with model data read from the connected instrument. Legacy host research conversion helpers are also retained. ChromIQ uses it without the manufacturer SDK at runtime.
No vendor binaries, graphics, extracted numerical tables, fitted calibration
profiles, CIE datasets or private chart/capture fixtures are included.

Source provenance is documented in docs/PROVENANCE.md; protocol observations in
docs/PROTOCOL.md. This is not a certified clean-room implementation: its author
has seen prior vendor-derived analysis. The normal ChromIQ workflow requires no numerical profile weights or user
reference measurement. Native acquisition has been validated on one owned unit;
this is not an independent ISO certification or cross-unit validation claim.

ChromIQ can import this source tree directly. To install the reusable package:

    python -m pip install ./vendor/fd9-independent

To run the package's self-contained library tests (the separate i1Pro2 research
capture tool and its four tests are intentionally not vendored):

    PYTHONPATH=vendor/fd9-independent/src python -m unittest discover -s vendor/fd9-independent/tests

A live acquisition is physical motion. Disconnect other instrument clients and
use ChromIQ's supervised workflow. Cooperative cancellation closes communication;
it does not send an unverified motion-cancel command. Recover a retained sheet
with the instrument controls. No forced registration or automatic motion retry.

Read-only factory access (0.5.3): `Instrument.sensor_factory_data(kind)` reads
the sensor's own records. All eleven record reads passed on one owned unit
without motion or factory writes. No record values are bundled. The cached
`Instrument.cached_sensor_data()` interface distinguishes missing data from
valid basic/native spectra. Live native-spectral acquisition and its ISO
condition mapping are described below. ChromIQ's normal measurement workflow
uses factory-native spectra without external profiles. These reads do not apply factory coefficients
a second time to packets already formed by the spectral sensor.

`Instrument.factory_characterization()` collects all eleven records, verifies
the observed section checksums, and supplies a network-independent fingerprint.
The joined primary section is exposed as opaque bytes, not interpreted or
applied as a second spectral calibration. Corrupt/incomplete snapshots fail.

The complete `sha256` identifies one snapshot, including mutable records 8/9.
`verified_sections_sha256` covers records 0..7 and 10; it identifies verified
content, not a serial number or immutable instrument identity.

## Experimental factory/native API

`NativeReader(instrument, enable_experimental_native=True)` reads on-device
M0/M1/M2 without an SDK, reference chart or external fitted profile. The device
applies its own characterization; the host does not interpret or reapply its
numerical tables. The public condition controls are 0, 2 and 160. The host SDK's
public M2 option 15 is not a wire selector.

Call `reader.after_final_point()` immediately from a final ordinary one-point
row callback. It waits for a fresh controller-ready event, checks factory-data
integrity and sensor flags, acquires one finite entry, peeks the requested
conditions without advancing, verifies unchanged raw data, then consumes once.
The returned `NativeMeasurement` has `for_condition('M2').spectrum` and
JSON-safe `to_dict()` evidence. Continued-row callbacks are refused before I/O;
timeouts use a bounded owned-start stop when the stream permits recovery.

One-unit native M0/M1/M2 spectra matched isolated offline manufacturer
calculations on identical raw entries within 4.8e-7 reflectance over 21 positions
and seven rows, including calibration renewal. The acquisition loaded no
manufacturer library or external profile. These are development checks, not a
user requirement, ISO certification or proof of other firmware/units.

Ejection is separate from clearing the exit paper sensor. Remove the ejected
sheet completely before starting another loading job.

`RawAcquisition.wait_sheet_clear(seconds)` may run in the NEW phase before the
next load. It waits on read-only controller status for mechanism 2 and paper 0,
observed when an ejected sheet fully clears the exit sensor. ChromIQ queues
later sheets through this wait, before model reads or loading. Cancellation,
fault and timeout close communication without an automatic motion command.

`NativeAcquisition` is the separately opted-in batch API. Its loading/pre-scan
methods match `RawAcquisition`; `measure_native(rows)` reads native conditions
before each move, tracks completed rows and retains partial results on failure.
It accepts the same 64-column/128-row coordinate envelope, without a 300-patch
limit. Seven-row transport and periodic calibration have passed on one unit.
This slower API remains available for reference checks and resuming its older
partial sessions. A 460-patch, 20-column native GUI chart passed on one unit.

## Automatic row sequencing (0.5.5)

New ChromIQ jobs use `FactoryRowAcquisition`, which sends one ordinary
acquisition command per row. The FD-9 controls the movements and patch stops,
with calibration renewal every six rows and one final home/ejection. It does
not acquire an additional stationary entry or issue cached getters per patch.
The four-block row packets already contain the sensor's unit calibration.
`InstrumentModel` calculates all three conditions using newly authored host
arithmetic and the emission/excitation matrix and condition illuminants read
from the connected instrument before loading. No numerical model is bundled.

The model-data layout is currently supported only for sensor version 1.0.0.2.
Unknown versions fail before any model-memory request. Only five fixed bounded
read spans are serialized, always with read flag zero; no arbitrary reader,
writer, firmware loader or calibration setter is exposed. Each session retains
the data actually read and its fingerprints. A resumed automatic-row session
must match both the checked factory sections and the conversion model.

Explicit row coordinates may run in either strictly monotonic X direction.
ChromIQ alternates the point order of successive rows, starting with increasing
X on each sheet or resumed pass. This changes head travel, not spectral
conversion, calibration cadence or the final home/ejection. Session evidence
records the ordering; sessions without that field keep the historical increasing-X
interpretation. Synthetic tests cover descending rows and cancellation within
one. A subsequent two-page GUI run completed 2,040 points (30 columns and
34 rows per sheet), with 17 increasing and 17 decreasing rows on each sheet,
and automatic paper-clear handoff. Every filed M0 spectrum matched the
verified raw/model data under its logical patch ID. Physical interruption and
resume within a descending row remain untested.

Offline conversion of 481 previously acquired raw entries across two charts
matched the same-entry native M0/M1/M2 within 4.8e-7 reflectance. Portable
transport tests check single-command rows and prohibit per-patch exposure and
getters. The combined automatic-row path subsequently completed a user-created,
printed 460-patch chart (20 columns, 23 rows) on the owned unit. All three
conditions exported successfully from the saved raw/model wire; the user
confirmed normal measurement speed. Physical Stop/Resume on this path remains
pending. These checks do not establish other versions/units or ISO certification.
