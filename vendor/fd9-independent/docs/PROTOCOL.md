# Observed FD-9 Ethernet subset

These are empirical observations, not an official manufacturer specification.
Only TCP port 49152 has been tested in the parent experimental project.

Transport: a four-byte little-endian header consists of direction byte,
continuation byte, and payload length uint16. Client direction is 0; device
direction is 1. Device chunks have length 1..8192 and continuation 0 or 1.
Concatenate chunks until continuation is zero. A complete payload begins
with a little-endian uint32 command/message identifier. Neither a TCP read
nor a packet is necessarily one message.

| Identifier | Observed layout / candidate support |
| --- | --- |
| 0x0003 | Normal registration: uint32 ID plus 20 NUL-padded ASCII application bytes; eight-byte reply with uint32 result |
| 0x0000 | Status request: ID only; forty-byte reply, result then eight opaque uint32 status words |
| 0x0001 | Calibration-data request: ID plus zero uint32; 7348-byte reply, result plus instrument-supplied opaque data |
| 0x0300 | 36-byte asynchronous message: ID and eight uint32 fields; field semantics remain empirical |
| 0x0304 | 3648-byte image message: ID, uint32 value 3640, signed int16 row index, 3638 grayscale bytes |
| 0x0305 | 620-byte raw spectral message: ID, four uint16 header fields, four blocks of 38 float32 values |

No wavelength/measurement-condition claims are attached to raw blocks in this
candidate. Identifying raw fields is distinct from deriving reflectance.
Calibration bytes may be device-specific and are not embedded in this package.

Notification queues, chunk sizes, total message size and response time are
bounded. A malformed or incomplete response closes the connection, preventing
partial bytes from becoming a subsequent command's reply. Nonzero command
results are errors. There is no automatic forced registration or retry.

## Experimental motion subset

The optional motion API newly serializes observed identifiers: job 0x0004,
display upload 0x0005, sensor selection 0x0203, position 0x0104, image capture
0x0105, explicit line geometry 0x0106, sensor homing 0x0100 and ejection
0x0101. Full-sheet acquisition and a supervised 36-patch stop/save followed by a
264-patch suffix resume have been exercised on one owned unit. The sheet was
recovered with instrument controls and reinserted before resuming. Other firmware
versions and physical units remain unverified.

Display messages have 64 bytes of metadata: command/type uint32 fields, an
eight-byte identifier, eleven reserved zero words and a chunk index. DEFAULT
followed by NUL is an observed protocol identifier, not copied artwork. Newly
generated 320-by-352 monochrome images are encoded as 16-bit black/white words
and split into 8000-byte pixel chunks; 29 messages complete a screen. Byte
order is immaterial for black and white. Other colours are not supported.

Line requests carry nine uint32 fields followed by twelve records of four
float32 values: explicit X/Y sensor-image coordinates and two zero fields.
Header constants 130, 150 and 65 are empirical controls whose meanings are
not asserted. Coordinates and the per-six-row flag schedule are checked by
synthetic tests; this does not establish spectral calibration accuracy.

Variable-grid extension (2026-11-01): command 0x106's point count and point
array are emitted from each declared row, within 1..64 points; the row loop
accepts up to 128 rows. Twelve-point framing remains byte-identical. This
extension is tested with invented messages and a 33-point acquisition, not a
new physical capture. The 12-point hardware-tested history above is retained.

## Sensor characterization and cached-output reads (2026-11-01)

The spectral sensor has a separate record interface. A read request is uint32
`0x206`, uint8 zero (read, never write), uint8 record kind. Successful replies
contain uint32 ID, uint32 controller result, uint8 sensor result, uint8 kind,
two reserved zero bytes, and the record. Observed byte lengths for kinds 0..10
are 28, 8000, 8000, 8000, 8000, 8000, 2240, 2512, 8000, 3436 and 16. These
are framing lengths, not calibration coefficients. All eleven read requests
succeeded on one owned unit without motion. Records remain opaque device data;
their values are never embedded in the package or its synthetic tests.

This interface is distinct from the controller's 7340-byte `0x0001` block.
Do not assume either record can be applied to the 4-by-38 spectral packet
without establishing its semantics; applying characterization twice would be
incorrect. The host's offline conversion can operate on those packets without
loading a factory record. That supports an existing sensor-side conversion
stage, but does not prove the meaning of every factory coefficient.

The sensor also accepts cached-output request `0x205`: basic selector 0 carries
two argument bytes `(0, 1)`; native spectral selector 1 carries five bytes
`(1, 1, 0, 0, 0)`. Successful nested responses have the command/result words,
then a 12-byte sensor header, then 152 or 36 float32 values respectively.
Sensor-header byte 0 is the result, bytes 1..3 are opaque, offsets 4 and 6 hold
uint16 sum/data counts, and offset 8 holds uint32 measurement-result flags.
Short sensor-error replies must not be mistaken for spectral data. The live
idle unit returned sensor error 7/detail 10 for both reads. The normal raw
stream consumes sensor queue entries, so querying after an ordinary row also
returns result 7. A 36-float response alone does not establish its condition;
the controlled native-acquisition checks are described below.

The complete sensor snapshot also verifies ones-complement byte-sum checksums
for record 0, the joined records 1..6 (42240 bytes), record 7 and record 10.
Each checksum is the final little-endian uint32 of its section. These four
checks matched the owned device records; coefficient semantics remain unknown.
Records 8/9 remain opaque and are preserved in the snapshot fingerprint,
without asserting a checksum rule for them. No characterization is applied
a second time to the sensor's spectral outputs.

Records 8/9 changed after ordinary measurement while all checksum-verified
sections remained identical. `sha256` is therefore a complete snapshot hash;
`verified_sections_sha256` covers records 0..7 and 10. Neither is a serial
number or a guarantee that characterization never changes.

## Experimental native final-point sequence

Sensor status is request `uint32 0x200` with no arguments. Its exact 24-byte
reply is the command/result words followed by `<BBHIII>`: numeric control
state, calculation state, queue count, fatal, warning and calibration-result
fields. There is no nested sensor-result byte in this status response.

After a final ordinary point and a fresh controller-ready event, the tested
finite request is `<IBBH>(0x203, 2, 0, 2)`. Mode 2 completes an acquisition;
mode 1 waits for triggers and must not be substituted. The tested finite
request produced one queued entry with integration sum 2 and data count 1.
Native control values 0, 2 and 160 mapped to M0, M1 and M2 in same-raw
comparisons on the owned unit. Public host-SDK M2 option 15 is translated to
160; sending 15 directly was rejected with sensor result 3. Control 14
returned all zeros on a white patch and is not used as M2.

Basic peeks use `(selector=0, advance=0)`. Native peeks use
`(selector=1, advance=0, condition, 0, 0)`. A second basic peek must match the
first exactly. Advancing the basic read once must return that same entry and
reduce queue count from 1 to 0. The typed native API checks these invariants,
sensor flags, integration counts and factory-record integrity. It never sends
factory writes or embeds factory numerical values.

On an owned started acquisition in active states 10/11/12, a bounded sensor
stop uses `(0x203, uint8 4)`. It does not home or move paper. No recovery RPC is
sent into a closed, cancelled or interrupted transport stream. A continued-row
callback must not issue native or status RPCs; the controller needs the next
row promptly and previously closed a connection after an interleaved query.

Single-point native M0/M1/M2 and two successive positions on one row are
demonstrated on one unit. Multirow transport remains experimental. A sheet can remain across the exit sensor
after ejection; measurement completion and physical paper clearance are
separate events.


## Native batch validation (2026-11-02)

NativeAcquisition ends each positioning request as a one-point final row,
then reads a preserved finite sensor entry before moving again. Twenty-one
positions across seven printed rows passed on one owned FD-9, with calibration
renewal at selected rows 1 and 7 and a single final home/ejection. M0/M1/M2
matched isolated same-raw manufacturer calculations within 4.8e-7 reflectance.
This slower reference path uses no profile, reference chart, manufacturer host
software or user comparison. New GUI jobs use the automatic rows below. The firmware
applies factory coefficients; the host reads opaque records and checks integrity.
A 460-point, 20-column native GUI chart passed. Physical native Stop/Resume
validation remains pending.

## Version-gated row model reads (0.5.5)

Sensor information is request `uint32 0x216` and an exact 48-byte reply.
Only successful replies with version bytes `01 00 00 02` at offset 8 enable
model reads. Read the model before starting paper loading, with an idle empty
sensor and clear error flags. Do not send memory requests on other versions.

The model read request is `<IBBHI>(0x20E, 0, 0, length, address)`.
The exact reply is `<IIBBHI>(0x20E, 0, 0, 0, length, address)` followed by
`length` raw bytes. Require the complete successful echo. Those raw numerical
bytes are big endian; the surrounding transport fields are little endian.
Only these spans are allowed, in this order:

| Address | Bytes | Interpretation |
| --- | ---: | --- |
| 0x0C02E520 | 4 | Condition base pointer; require 0x0C034C28 |
| 0x0C04C378 | 4 | Condition count; require 27 |
| 0x0C02D4F8 | 1600 | 25 × 16 float32 emission/excitation matrix |
| 0x0C034C28 | 8000 | First condition-record chunk |
| 0x0C036B68 | 2584 | Remaining condition-record bytes |

The first two four-byte checks precede bulk reads. Condition records are
392 bytes: uint32 identifier plus 97 float32 powers from 300 to 780 nm in
5 nm steps. Require unique M0/M1/M2 identifiers 0/2/160. Other custom slots
may change and are not part of the conversion fingerprint. The matrix spans
emission 370–610 nm and excitation 300–450 nm in 10 nm increments. No values
from these spans are embedded in source or test fixtures.

The host applies the two-source radiance-factor equation in CALIBRATION.md
to the sensor-calibrated four-block row packet. Float32 reporting conventions
retain the second source below 400 nm, use a two-source mean above 610 nm,
extrapolate 730 nm from 710/720 nm, copy the 400 nm result to 380/390 nm for
M2, and floor reflectance at 0.0001 without an upper clamp. Near-zero source
response contrast uses an equal-source blend. These conventions match tested
native output; they are not independently certified spectral coverage claims.

Automatic acquisition preserves ordinary `0x106` row continuation, calibrates
rows 1, 7, 13, …, and never interleaves finite sensor acquisitions or cached
getters. Per-point callbacks are passive: issuing an instrument command there
is rejected. The original native final-point API remains available for
reference work and continuation of older native partial sessions.

## Automatic-row GUI validation (2026-11-02)

The normal Measure tab completed a user-created and printed 460-patch Letter
chart: 20 columns by 23 rows. Its same-connection transcript contains five
read-only model spans, eleven read-only factory records, 23 whole-row `0x106`
requests, only the pre-scan's mode-5 `0x203`, no cached `0x205` getters, and
one final home/ejection. All rows, raw/model conversion, geometry and three
condition exports passed offline verification. The user reported normal speed.
This validates the tested combined path on one owned unit. Physical Stop/Resume,
other sensor versions and larger or smaller-patch layouts remain separate checks.
