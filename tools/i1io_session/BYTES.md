# BYTES.md: everything chromiq-i1io-session 0.3.0 can send to the table

This file is the allow-list. `tests/test_i1io_session_tool.py` reads the table below and fails
if the program's own list (`i1io_session_table.WIRE`) differs from it by a single byte, or if any
simulated session, on any path, with any fault, any stop or Ctrl-C at any point, writes a byte
string that is not in it. Nothing outside this file is ever written to the table's bulk OUT
endpoint 0x02.

Sources (seconds from the start of each recording): **R1**, **R2** the tester's recordings of
12/13 Nov 2026; **S1** the cold-start recording and **S2** the measuring recording of 14 Nov
2026 (i1Profiler 3.8.6 on the tester's own i1iO 2). Every line below is byte-identical to a
line i1Profiler sent. There is no line built from numbers: the targets and the speed of the
four moves are the recorded ones, fixed in the line.

## Lines to the table (bulk OUT 0x02, one line per USB write)

| # | line (ASCII, then CR) | hex | name in the program | recorded at |
|---|---|---|---|---|
| 1 | `;a133` | `3b 61 31 33 33 0d` | identity | every open: S1 1.141/1.311; R2 34.546/34.715, 378.147/378.314; R1 83.666 |
| 2 | `;k228` | `3b 6b 32 32 38 0d` | k2 | every open, right after the second a1: S1 1.327; R2 34.731, 378.331 |
| 3 | `;u8000060000100d1` | `3b 75 38 30 30 30 30 36 30 30 30 30 31 30 30 64 31 0d` | memory_a | every open, right after k2: S1 1.343; R2 34.747, 378.347 |
| 4 | `;u8000061000068c3` | `3b 75 38 30 30 30 30 36 31 30 30 30 30 36 38 63 33 0d` | memory_b | every open, right after the first u8: S1 1.450; R2 34.853, 378.453 |
| 5 | `;a034` | `3b 61 30 33 34 0d` | a0 | every open: S1 1.502 (111800, cold); R2 34.906, 378.505 (130000, warm) |
| 6 | `;s022` | `3b 73 30 32 32 0d` | status | R2 34.932, 378.530 after a0; S1 4.766, R2 35.003, 268.621 before the p0 of a homing; R2 265.659, 268.909 after a homing; R2 427.359/427.389 after a move; S1 22.919, R2 361.579 before f0 |
| 7 | `;f42b` | `3b 66 34 32 62 0d` | arm_mode | R2 34.940-34.985 and 378.539-378.585 (00); R2 424.993/425.006 before the way out (00); S2 3.909-3.999 around f3 (00); S2 4.033/4.048 after f1 (01); R2 256.592-256.638 before the cancel (01) |
| 8 | `;p025` | `3b 70 30 32 35 0d` | position | R2 35.017, 378.617 before the homing; R2 425.026 before the way out; R2 427.445 at (1000, 1500); R2 261.628 on the free arm before the cancel |
| 9 | `;i12b` | `3b 69 31 32 62 0d` | home | at rest from Y 14..47 (S1 4.796; R2 35.033, 134.274, 268.653, 378.632, 417.181; R1 190.093) and Y 0..2 (R1 190.412; R2 134.610, 417.453); from held positions on the table (S2 179.201, 371.169, 497.615, 586.887, 769.808; R1 338.379, 546.843, 740.993; R2 706.049; from (1102, 1202) R1 85.848); from the free arm after f1 (R2 261.644 status 0, 4.01 s; R1 272.124 status 3) |
| 10 | `;f02f` | `3b 66 30 32 66 0d` | f0 | the close, after s0: S1 22.935, R2 361.594; R1 0.017 |
| 11 | `;f32c` | `3b 66 33 32 63 0d` | f3 | right after f0 in the close: S1 22.951, R2 361.611; before f1 at every alignment: S2 3.957, R1 202.158, R2 146.302 |
| 12 | `;m0044e00fa012c0e` | `3b 6d 30 30 34 34 65 30 30 66 61 30 31 32 63 30 65 0d` | to_250 | from rest right after p0: R2 425.038 from (1102, 4), R2 142.056, R1 197.917; 0.719-0.720 s |
| 13 | `;m003e805dc012c06` | `3b 6d 30 30 33 65 38 30 35 64 63 30 31 32 63 30 36 0d` | to_1000 | right after to_250: R2 425.758, R2 142.775, R1 198.637; 1.599 s |
| 14 | `;m0044e05da012c0b` | `3b 6d 30 30 34 34 65 30 35 64 61 30 31 32 63 30 62 0d` | to_1498 | from rest right after p0: R1 398.217, 713.401; S2 267.330, 379.924, 523.418, 680.534 (from Y 29..37), 1.727-1.728 s |
| 15 | `;m009cb05da012cda` | `3b 6d 30 30 39 63 62 30 35 64 61 30 31 32 63 64 61 0d` | to_2507 | right after to_1498: R1 399.945, 715.129; S2 1.792, 269.057, 381.652, 525.146, 682.262; 1.695 s |
| 16 | `;f12e` | `3b 66 31 32 65 0d` | free | at every alignment, after s0 f4 f4 f3 f4 f4: S2 4.018 (answer 01; f4 then reads 01), R1 202.217, 402.173, 717.356, R2 146.366, 429.355; 10 in all |

## The steps (each at most once per session, each only after the person's yes)

The opening (always first, only reads): `a1 a1 k2 u8 u8 a0 s0 f4 f4 f4 f4` (11 lines; a
table that answers a0 = 111800 gets the first six and nothing more).

| # | step | lines | movements | risk | lines in order |
|---|---|---|---|---|---|
| 1 | home | 4 | 1 | low | `s0 p0 i1 s0` |
| 2 | near | 21 | 5 | medium | `s0 p0 i1 s0 f4 f4 p0 m0 p0 m0 s0 s0 f4 f4 p0 i1 s0 s0 p0 i1 s0` |
| 3 | straight | 19 | 4 | medium | `s0 p0 i1 s0 f4 f4 p0 m0 s0 s0 f4 f4 p0 i1 s0 s0 p0 i1 s0` |
| 4 | across | 27 | 6 | medium | `s0 p0 i1 s0 f4 f4 p0 m0 p0 m0 s0 s0 f4 f4 p0 m0 s0 s0 f4 f4 p0 i1 s0 s0 p0 i1 s0` |
| 5 | free | 25 | 3 | medium | `s0 p0 i1 s0 f4 f4 f3 f4 f4 f1 f4 f4 s0 f4 f4 f4 f4 s0 p0 i1 s0 s0 p0 i1 s0` |
| 6 | close | 3 | 0 | low | `s0 f0 f3` |

Hard caps: per step exactly its own lines and movements (above); per session the opening plus
every step once: **110 lines, 19 movements**. A step struck by the reviewer is removed
by deleting its entry in `STEPS`; the caps follow from that list.

Every step starts with i1Profiler's own homing `s0 p0 i1 s0` from the resting place (the p0
must read X 1101..1103, Y -1..80). Between two moves that i1Profiler sent back to back, the program reads the position once (the recorded spot-pass pattern `m0 p0 m0`) and stops if the first move did not arrive. Every movement must finish inside its time window
(`TIME_WINDOW` in the program, from the recorded times, widened); every arrival is checked by
a p0 against the target (plus or minus 5 units). The person is never asked anything while the
arm is away from its resting place.

## USB control requests (endpoint 0, before the first line)

As recorded at every open: bmRequestType 0x40, wIndex 0, about 4 ms apart: reset (0x00,
0x0000), purge RX (0x00, 0x0001), purge TX (0x00, 0x0002), baud 57 600 (0x03, 0x0034), 8N1
(0x04, 0x0008). The serial-number string descriptor is never asked for.

## Replies the program accepts (anything else stops it, with nothing more sent)

| line | accepted `:$` answer (recorded) |
|---|---|
| a1 | `:$a10005D010702DD` exactly |
| k2 | `:$k200B60000000001319` exactly |
| u8 6000/0100 | status 0, 512 hex characters starting `6801000056312E31`; content never logged |
| u8 6100/0068 | status 0, 208 hex characters; content never logged |
| a0 | `:$a00130000BD` (go on) or `:$a00111800B6` (stop) |
| s0 | `:$s00CF` |
| f4 | `:$f400078` (00) or `:$f400177` (01), each only where the step expects it (01 only after f1) |
| p0 | status 0, 8 hex characters, then the place check of that point |
| i1, m0 | status 0, no data, inside the time window of that movement |
| f0, f3 | `:$f00007C`, `:$f300079` (00) |
| f1 | `:$f10017A` (01) |

## Never sent (not in this program, and the tests check that no such line exists in it)

i0 (start-up of a cold table), m1 (move to the alignment start; its timing does not fit a
plain move, meaning not established), m2, c3, c4, d1, a3 (the scanning lines, which occur only
between "arm at a patch" and "reading"), p1, any u8 other than the two reads, any write to the
table's or the instrument's memory, any m0 other than the four fixed lines, any other speed,
and any command id or argument not in the table above.
