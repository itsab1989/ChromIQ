# Conversion scope and public mathematical reference

Spectral product integration, XYZ/Lab integration and two-illuminant blending
are newly written arithmetic. External profiles supply instrument-specific
weights; no such weights or correction tables are included here. Raw messages
alone are not declared calibrated M0/M1/M2 reflectance.

For separable substrate excitation/emission, define
`q_i(lambda) = integral(I_i(mu) e(mu) dmu) / I_i(lambda)`.
Then `w = (q_target - q_2) / (q_1 - q_2)` and
`B_target = w B_1 + (1-w) B_2`. Input spectra must cover the needed wavelengths;
weights are not silently clamped and undefined source responses are rejected.
This physical model alone does not establish FD-9 raw block semantics.

Public mathematical reference: Yamamoto, Goto and Matsubara,
*The FD-7 Spectrodensitometer*, Konica Minolta Technology Report 8 (2011),
pp. 138-142:
https://research.konicaminolta.com/jp/pdf/technology_report/2011/pdf/industry_008.pdf
The paper discusses the FD-7; it is not proof of FD-9 accuracy.

The experimental conversion API labels its output uncalibrated research data.
One-unit compatibility comparisons are not traceable ISO calibration or proof
of cross-unit accuracy. CIE datasets, external profiles and private measurement
fixtures are not redistributed with this source. See PROVENANCE.md.

## On-device factory/native acquisition

The opt-in `NativeReader` uses the instrument's own numerical conversion and
factory characterization. It does not use the external research models above,
an SDK or a caller-supplied calibration profile. Factory record checksums and
sensor flags are checked; tables are not reapplied on the host.

On one owned unit, non-advancing native controls 0/2/160 matched M0/M1/M2 on paper
white and on one magenta/light-magenta patch,
against isolated offline manufacturer calculations of the identical raw data.
The maximum band difference was below 4.8e-7 reflectance in the later
21-position, seven-row test. The same raw entry
was unchanged across native reads and consumed exactly once afterward.

These checks validate the tested condition mapping and final-point sequence.
They do not establish cross-unit accuracy, every firmware version, certification,
or full native GUI chart acquisition. The native API remains explicitly
experimental. The native reference path needs no external profile or user reference
comparison. New ChromIQ jobs use the automatic-row model path below.

Two successive native positions on the same row completed without ejection
between them, including factory-record checks through the reusable API. Native
M0/M1/M2 agreed with the same-raw references within 3.6e-7 reflectance over both
positions. A subsequent 21-position test passed seven vertical rows and calibration
renewal. Full native GUI chart acquisition and live Stop/Resume remain pending.

## Factory-calibrated automatic rows

The four-block row packets are sensor-calibrated; the host does not apply
opaque unit coefficients again. `InstrumentModel` reads a version-bounded
emission/excitation matrix and three illuminant records from the connected
unit, then applies newly authored two-source radiance-factor arithmetic.
There are no fitted chart weights or bundled instrument numerical assets.
See PROTOCOL.md for the read-only spans and reporting conventions.

The 25-by-16 matrix permits a separate excitation response for each emission
wavelength, rather than imposing a single fitted paper curve. The discrete
response is the sum of matrix × excitation power × 10 nm, divided by the
source power at that emission wavelength. The target response uses the
instrument's own condition power spectrum. Solving between the two measured
source responses gives the requested radiance factor. Missing source UV
samples below 360 nm are zero in this established packet convention.

All 481 entries from the earlier 21-point and 460-point native acquisitions
matched this host conversion within 4.8e-7 reflectance for all three conditions.
This is same-entry arithmetic validation on one device, not cross-device
certification. Physical verification of automatic acquisition plus this host
conversion remains pending. Unknown sensor versions are refused rather than
substituting fitted weights or asking users for manufacturer comparisons.
