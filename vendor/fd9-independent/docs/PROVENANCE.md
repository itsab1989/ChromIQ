# Provenance ledger

The transport facts and message layouts below were observed in the local
FD-9 reverse-engineering project. Some interpretations were informed by
vendor-binary analysis. This implementation is not represented as the work
of an unexposed clean-room team.

| Material | Candidate treatment |
| --- | --- |
| Framing, command numbers, message lengths | Newly written serializers/parsers; factual protocol specification |
| Local client traffic and measurement captures | Development evidence only; not copied into package or synthetic tests |
| FD-S2w/FD9SDK executables and libraries | Excluded; never loaded by this package; isolated offline comparison outputs are private validation evidence only |
| Captured FD-9 display graphics | Excluded; replacement artwork and glyphs are newly authored in display.py |
| libDIColor extracted fluorescence/illuminant tables | Excluded, including external conversion profiles; not used by the normal factory-calibrated path |
| Vendor/native chart files | Excluded |
| Instrument-specific factory data | Read on the device connection and integrity-checked; the sensor applies unit calibration; automatic rows additionally read the device’s response model and illuminants for host calculation; no numerical table is bundled or applied twice |
| Argyll/CIE numerical datasets | No bundled datasets; official CIE datasets used privately for arithmetic checks, with published hashes and CC BY-SA 4.0 metadata retained |
| Synthetic test messages | Constructed from the documented layouts using invented values |
| Existing OpenRIP implementation | Not imported or packaged; its research informed the specification |

The old backend includes vendor-derived display payloads and numerical
conversion data. It remains a separate experimental system. No assertion is
made that placing this candidate in a different directory resolves legal
questions or establishes strict clean-room provenance.

The contributed serializers, acquisition state machine, display renderer and
conversion arithmetic are newly authored Python source, licensed
GPL-3.0-or-later. Protocol identifiers, field sizes and reporting conventions
record observed behaviour; they are not copied manufacturer source code.
The conversion models use explicit caller-supplied reference curves and weights.
Some private validation profiles were fitted against manufacturer output; those
profiles, their coefficients and the manufacturer-output fixtures are excluded.
ChromIQ’s normal workflow instead obtains calibrated row packets and model data
from the connected device, without a fitted profile. The sensor applies unit
calibration before packet delivery; newly authored host arithmetic calculates
M0/M1/M2 using the read-only model. The older native reference API passed
21 positions over seven rows and a 460-patch GUI chart on one owned unit. Offline same-raw
manufacturer comparisons are private development validation, never a required
user setup step. The driver does not load the SDK or decode/reapply every
factory coefficient on the host.


The submission audit covers the source and assets included in this contribution,
not a legal finding about reverse engineering or a claim of independent
discovery of every protocol fact. Maintainers can review the observed protocol
specification and source separately. Do not ship captured vendor payloads or
extracted numerical tables as a shortcut to completing the implementation.

Spectral/fluorescence source consists of newly authored arithmetic following
public equations, with explicit input curves. The public FD-7 technical paper
is identified in CALIBRATION.md. No excitation curve or instrument correction
table is shipped. The automatic-row driver reads its model from the connected
unit using a version-gated, fixed-span, read-only protocol; these session files
remain user runtime evidence, not package assets. Private firmware analysis
helped establish that protocol and reporting conventions, but no manufacturer
code or extracted numerical arrays are copied into this package. Legacy host
research models require explicit reference inputs; factory-calibrated rows do not.
