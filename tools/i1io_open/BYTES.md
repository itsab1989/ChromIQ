# BYTES.md: everything chromiq-i1io-open 0.2.1 can send to the table (warm only)

This file is the allow-list. `tests/test_i1io_open_tool.py` reads the table below and
fails if the program's own list (`i1io_open_table.WIRE`) differs from it by a single byte, or
if any simulated run, on any path and with any fault, writes a byte string that is not in
it. Nothing outside this file is ever written to the table's bulk OUT endpoint 0x02.

Sources (times are seconds from the start of each recording, as `io_decode.py` prints them):

* **S1** the tester's cold-start recording of 14 Nov 2026 (probe 1.6.2, i1Profiler 3.8.6;
  a power cycle with the arm at rest was asked for and is not yet confirmed by the tester;
  i1Profiler opened and quit).
* **R1**, **R2** the tester's recordings of 12/13 Nov 2026 (warm table: the table had been
  on, USB replugged).
* **S2** the tester's measuring recording of 14 Nov 2026 (five i1Profiler sessions).

Every line below is byte-identical to a line i1Profiler sent, and is sent here only in the
place where i1Profiler sent it (column "context"). Every two lines that follow each other in
this program also follow each other in the recordings (the tests carry the pair list, from
`pairs_all.py` over R1, R2, S1 and S2). The whole warm run is:

```
opening   a1 a1 k2 u8 u8 a0                      (every recorded open)
          s0 f4 f4 f4 f4                         (R2 34.932-34.985, 378.530-378.585)
          ... the person's yes ...               (f4 then s0 after a pause: 13x, up to 162 s)
homings   s0 p0 i1 p0 i1 s0 f4 f4                (R1 190.077-197.900, R2 134.258-142.039,
                                                  R2 417.165-425.021: i1Profiler's double
                                                  homing before a calibration, after an s0)
          ... the person looks at the arm ...     (f4 then s0 after a pause, as above)
closing   s0 f0 f3                               (S1 22.919-22.951, R2 361.579-361.611)
```

0.2.0 read `p0` after the homing and then sent `s0`: that pair is never recorded (no
recording follows `p0` with anything but a movement, `c4` or another `p0`), and on the
tester's table the reading (1102, 19) stopped the run before its close. After the independent
safety review of 2026-11-14 (B1) the start-up line i0 is NOT in this list: a table that
answers a0 = 111800 gets only lines 1-5 below (six lines) and nothing else; no closing is
recorded for a table in that state, so none is sent. The checksum (last two hex digits) is
the two's complement of the 8-bit sum of the characters before it; every line ends with
one CR (0x0D).

## Lines to the table (bulk OUT 0x02, one line per USB write)

| # | line (ASCII, then CR) | hex | sent by this program | recorded at (context) |
|---|---|---|---|---|
| 1 | `;a133` | `3b 61 31 33 33 0d` | 1st and 2nd line of every run | S1 1.141 + 1.311 (cold open); R2 34.546 + 34.715, 378.147 + 378.314 (warm open). Always the first two lines after the USB set-up |
| 2 | `;k228` | `3b 6b 32 32 38 0d` | 3rd line | S1 1.327; R2 34.731, 378.331. Always right after the second a1 |
| 3 | `;u8000060000100d1` | `3b 75 38 30 30 30 30 36 30 30 30 30 31 30 30 64 31 0d` | 4th line | S1 1.343; R2 34.747, 378.347. Right after k2 |
| 4 | `;u8000061000068c3` | `3b 75 38 30 30 30 30 36 31 30 30 30 30 36 38 63 33 0d` | 5th line | S1 1.450; R2 34.853, 378.453. Right after the first u8 |
| 5 | `;a034` | `3b 61 30 33 34 0d` | 6th line. Answer 111800: STOP here (nothing more is sent). Answer 130000: go on. Anything else: stop | S1 1.502 (answer 111800); R2 34.906, 378.505 (answer 130000). Right after the second u8 |
| 6 | `;s022` | `3b 73 30 32 32 0d` | after a0 (warm); after the person's yes, right before p0; after the second i1; before f0 | R2 34.932 + 378.530 (after a0, warm); R1 87.464 / R2 378.905 (an s0 before the p0 of a double homing); R1 197.852, R2 141.991, 424.974 (after the second i1); R2 361.579 and S1 22.919 (before f0) |
| 7 | `;f42b` | `3b 66 34 32 62 0d` | four times after the first s0; twice after the s0 that follows the second i1 | R2 34.940-34.985, 378.539-378.585; S1 4.706-4.748; R1 197.871/197.885, R2 142.010/142.024, 424.993/425.006. Always answered 00 there |
| 8 | `;p025` | `3b 70 30 32 35 0d` | after the person's yes, right after s0 and right before the first i1; right after the first i1 and right before the second | R1 190.077 + 190.404, R2 134.258 + 134.587, R2 417.165 + 417.445 (the double homing); R2 35.017, 378.617 (before the opening's i1). Never followed by s0, f4 or f0 in any recording, so never sent after the second i1 |
| 9 | `;i12b` | `3b 69 31 32 62 0d` | twice, each right after the p0 that read the resting place | R1 190.093 (from (1102, 32), 0.304 s) + 190.412 (from (1102, 2), 0.048 s); R2 134.274 + 134.610; R2 417.181 + 417.453; at the opening R2 378.632, R2 35.033, S1 4.796. On the tester's table with 0.2.0: from (1101, 46), 0.336 s |
| 10 | `;f02f` | `3b 66 30 32 66 0d` | after the closing s0, arm at rest, motors holding (f4 00) | S1 22.935; R2 361.594; R1 0.017 |
| 11 | `;f32c` | `3b 66 33 32 63 0d` | right after f0 | S1 22.951; R2 361.611; R1 0.033 |

## USB control requests (endpoint 0, before the first line)

Recorded at every open (S1 1.124-1.141, R2 34.534-34.546, R2 378.128-378.147), sent in this
order, about 4 ms apart, bmRequestType 0x40, wIndex 0, no data stage:

| # | bRequest | wValue | FTDI meaning |
|---|---|---|---|
| C1 | 0x00 | 0x0000 | reset |
| C2 | 0x00 | 0x0001 | purge RX |
| C3 | 0x00 | 0x0002 | purge TX |
| C4 | 0x03 | 0x0034 | baud divisor 52 = 57 600 baud |
| C5 | 0x04 | 0x0008 | 8 data bits, no parity, 1 stop bit |

Besides these, libusb's own standard requests (GET_DESCRIPTOR when the device is listed,
SET_CONFIGURATION only if the device reports no configuration, claim/release of interface
0) and the reads of bulk IN 0x81. The serial-number string descriptor is never asked for.

## Replies the program accepts (anything else stops it, with nothing more sent)

Every line must have a valid checksum. The acceptance `:!` + id + checksum must come first;
`:#` + id + code + checksum is the table's refusal (seen on the tester's table as `:#s01CF`,
0.1.0 run 1) and stops the program.

| line | accepted `:$` answer (recorded) | recorded at |
|---|---|---|
| a1 | `:$a10005D010702DD` exactly | every open |
| k2 | `:$k200B60000000001319` exactly | every open |
| u8 6000/0100 | status 0 and 512 hex characters starting `6801000056312E31` (length 360, "V1.1"); content never logged | every open |
| u8 6100/0068 | status 0 and 208 hex characters; content never logged | every open |
| a0 | `:$a00111800B6` (cold) or `:$a00130000BD` (warm) | S1 1.517; R2 34.906, 378.520 |
| s0 | `:$s00CF` | 75 times |
| f4 | `:$f400078` (00), everywhere it is read (01 was only ever read after f1, which is never sent) | every open; after every double homing |
| p0 | status 0 and 8 hex characters; then the arm must be at its resting place, X 1097..1107, Y -5..50 (every read at rest in R1, R2, S1, S2 and both real runs: X 1101..1102, Y 0..47; 0.16 s after the homing on the tester's table Y 19) | 457 times |
| i1 | `:$i10D8`, within 12 s; stop if it took longer than 2 s (recorded at rest 0.047-0.352 s; 0.336 s on the tester's table) | 22 times; status 3 once (R1 272.555, free arm): stops here |
| f0 | `:$f00007C` (00) | 11 times |
| f3 | `:$f300079` (00) | 13 times |

## Never sent (not in this program, and the tests check that no such line exists in it)

i0 (`;i02c`, the start-up of a table just switched on: recorded once, its motion and its
context not established; removed after the safety review), m0, m1, m2 (moves), c3, c4, d1 (scan
synchronisation; meaning not established), a3, f1 (frees the arm), p1, and any command id or
argument not in the table above.
