# BYTES.md: everything chromiq-i1io-session 0.6.0 can send to the table

0.6.0 adds ONE line, line 46 below: `;i02c` (i0), the start-up of a table that has just been
switched on, byte for byte as i1Profiler sent it in the one recording of a cold start (S1).
It is sent only in the start-up (section "The start-up" below): only on a table whose a0
answered 111800, only after the person's typed yes, at most once per sitting. The lines that
follow it there are lines 6 to 9, already on this list. On a started table (a0 = 130000)
0.6.0 sends exactly what 0.5.1 sends: no other line, gate, cap or limit changed.

This file is the allow-list. `tests/test_i1io_session_tool.py` reads the table below and fails
if the program's own list (`i1io_session_table.WIRE`) differs from it by a single byte, or if any
simulated session, on any path, with any fault, any stop or Ctrl-C at any point, writes a byte
string that is not in it. Nothing outside this file is ever written to the table's bulk OUT
endpoint 0x02. Part A may send only lines 1 to 16 (0.3.1's lines); part B may send lines 1 to
11, 14 to 16 and 17 to 45 (not the two moves of part A's step 2). Part C (0.5.0) has its own
section at the end of this file: lines 1 to 11, 14 to 45, five further recorded lines, and
computed moves of a recorded form.

Sources (seconds from the start of each recording): **R1**, **R2** the tester's recordings of
12/13 Nov 2026; **S1** the cold-start recording and **S2** the measuring recording of 14 Nov
2026 (i1Profiler 3.8.6 on the tester's own i1iO 2). Every line below is byte-identical to a
line i1Profiler sent; lines 17 to 45 were checked in the raw S2 capture file itself, not only in
its decoded timeline. There is no line built from numbers: the targets and the speed of every
move are the recorded ones, fixed in the line.

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
| 17 | `;m10b10055b012c42` | `3b 6d 31 30 62 31 30 30 35 35 62 30 31 32 63 34 32 0d` | m1 | after m0 (2507, 1498) in every measuring session that began without a calibration: S2 3.488, 270.753, 383.348, 526.841, 683.957 (0.399-0.400 s), then s0 f4 f4 f3 f4 f4 f1; R1, R2 after (1000, 1500): 1.759 s |
| 18 | `;m0fb63067a012c03` | `3b 6d 30 66 62 36 33 30 36 37 61 30 31 32 63 30 33 0d` | spot01 | S2 session 3, S2 454.218, from (-1297, 2681), 1.456 s to (-1181, 1658) at 300; context p0 p0 m0 p0 (the first spot move, from the free arm after s0 f4 f4 f4 f4) |
| 19 | `;m0fbba067b012ca8` | `3b 6d 30 66 62 62 61 30 36 37 62 30 31 32 63 61 38 0d` | spot02 | S2 session 3, S2 456.128, from (-1180, 1658), 0.431 s to (-1094, 1659) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 20 | `;m0fc11067b012c08` | `3b 6d 30 66 63 31 31 30 36 37 62 30 31 32 63 30 38 0d` | spot03 | S2 session 3, S2 457.625, from (-1093, 1660), 0.432 s to (-1007, 1659) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 21 | `;m0fc68067b012cfc` | `3b 6d 30 66 63 36 38 30 36 37 62 30 31 32 63 66 63 0d` | spot04 | S2 session 3, S2 459.137, from (-1006, 1659), 0.432 s to (-920, 1659) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 22 | `;m0fcbf067b012ca2` | `3b 6d 30 66 63 62 66 30 36 37 62 30 31 32 63 61 32 0d` | spot05 | S2 session 3, S2 460.644, from (-920, 1659), 0.431 s to (-833, 1659) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 23 | `;m0fd17067b012c01` | `3b 6d 30 66 64 31 37 30 36 37 62 30 31 32 63 30 31 0d` | spot06 | S2 session 3, S2 462.327, from (-833, 1659), 0.431 s to (-745, 1659) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 24 | `;m0fd6e067c012ccd` | `3b 6d 30 66 64 36 65 30 36 37 63 30 31 32 63 63 64 0d` | spot07 | S2 session 3, S2 463.598, from (-744, 1659), 0.432 s to (-658, 1660) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 25 | `;m0fdc5067c012cd0` | `3b 6d 30 66 64 63 35 30 36 37 63 30 31 32 63 64 30 0d` | spot08 | S2 session 3, S2 465.087, from (-657, 1660), 0.431 s to (-571, 1660) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 26 | `;m0fe1c067c012cd3` | `3b 6d 30 66 65 31 63 30 36 37 63 30 31 32 63 64 33 0d` | spot09 | S2 session 3, S2 466.554, from (-570, 1660), 0.432 s to (-484, 1660) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 27 | `;m0fe74067c012cfc` | `3b 6d 30 66 65 37 34 30 36 37 63 30 31 32 63 66 63 0d` | spot10 | S2 session 3, S2 468.030, from (-484, 1660), 0.432 s to (-396, 1660) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 28 | `;m0fecb067c012ca2` | `3b 6d 30 66 65 63 62 30 36 37 63 30 31 32 63 61 32 0d` | spot11 | S2 session 3, S2 469.539, from (-395, 1661), 0.431 s to (-309, 1660) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 29 | `;m0ff22067d012c01` | `3b 6d 30 66 66 32 32 30 36 37 64 30 31 32 63 30 31 0d` | spot12 | S2 session 3, S2 471.049, from (-309, 1661), 0.431 s to (-222, 1661) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 30 | `;m0ff79067d012cf5` | `3b 6d 30 66 66 37 39 30 36 37 64 30 31 32 63 66 35 0d` | spot13 | S2 session 3, S2 472.697, from (-222, 1661), 0.432 s to (-135, 1661) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 31 | `;m0ffd0067d012cd1` | `3b 6d 30 66 66 64 30 30 36 37 64 30 31 32 63 64 31 0d` | spot14 | S2 session 3, S2 474.037, from (-134, 1661), 0.431 s to (-48, 1661) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 32 | `;m00027067d012c68` | `3b 6d 30 30 30 32 37 30 36 37 64 30 31 32 63 36 38 0d` | spot15 | S2 session 3, S2 475.517, from (-47, 1662), 0.431 s to (39, 1661) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 33 | `;m0007e067d012c35` | `3b 6d 30 30 30 37 65 30 36 37 64 30 31 32 63 33 35 0d` | spot16 | S2 session 3, S2 477.011, from (39, 1662), 0.432 s to (126, 1661) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 34 | `;m000d5067d012c38` | `3b 6d 30 30 30 64 35 30 36 37 64 30 31 32 63 33 38 0d` | spot17 | S2 session 3, S2 478.511, from (126, 1661), 0.431 s to (213, 1661) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 35 | `;m0012c067e012c3a` | `3b 6d 30 30 31 32 63 30 36 37 65 30 31 32 63 33 61 0d` | spot18 | S2 session 3, S2 480.010, from (213, 1661), 0.432 s to (300, 1662) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 36 | `;m00184067e012c63` | `3b 6d 30 30 31 38 34 30 36 37 65 30 31 32 63 36 33 0d` | spot19 | S2 session 3, S2 481.519, from (300, 1663), 0.432 s to (388, 1662) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 37 | `;m001db067e012c09` | `3b 6d 30 30 31 64 62 30 36 37 65 30 31 32 63 30 39 0d` | spot20 | S2 session 3, S2 483.231, from (388, 1662), 0.431 s to (475, 1662) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 38 | `;m00232067e012c69` | `3b 6d 30 30 32 33 32 30 36 37 65 30 31 32 63 36 39 0d` | spot21 | S2 session 3, S2 484.529, from (475, 1662), 0.432 s to (562, 1662) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 39 | `;m00289067e012c5d` | `3b 6d 30 30 32 38 39 30 36 37 65 30 31 32 63 35 64 0d` | spot22 | S2 session 3, S2 486.041, from (562, 1662), 0.432 s to (649, 1662) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 40 | `;m002e0067f012c38` | `3b 6d 30 30 32 65 30 30 36 37 66 30 31 32 63 33 38 0d` | spot23 | S2 session 3, S2 487.541, from (649, 1662), 0.431 s to (736, 1663) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 41 | `;m00338067f012c61` | `3b 6d 30 30 33 33 38 30 36 37 66 30 31 32 63 36 31 0d` | spot24 | S2 session 3, S2 489.019, from (736, 1663), 0.431 s to (824, 1663) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 42 | `;m0038f067f012c2e` | `3b 6d 30 30 33 38 66 30 36 37 66 30 31 32 63 32 65 0d` | spot25 | S2 session 3, S2 490.514, from (823, 1663), 0.432 s to (911, 1663) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 43 | `;m003e6067f012c31` | `3b 6d 30 30 33 65 36 30 36 37 66 30 31 32 63 33 31 0d` | spot26 | S2 session 3, S2 492.024, from (911, 1663), 0.431 s to (998, 1663) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 44 | `;m0043d067f012c34` | `3b 6d 30 30 34 33 64 30 36 37 66 30 31 32 63 33 34 0d` | spot27 | S2 session 3, S2 493.757, from (997, 1663), 0.432 s to (1085, 1663) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 45 | `;m00495067f012c5d` | `3b 6d 30 30 34 39 35 30 36 37 66 30 31 32 63 35 64 0d` | spot28 | S2 session 3, S2 495.037, from (1085, 1663), 0.432 s to (1173, 1663) at 300; context p0 m0 p0 (spot pass, one patch on) |
| 46 | `;i02c` | `3b 69 30 32 63 0d` | start_up | ONCE: S1 1.517, right after a0 answered `:$a00111800B6` (just switched on); accepted `:!i00C` at 1.533, done `:$i00D9` at 4.684 (3.167 s); checked in the raw S1 capture file (one USB write of these six bytes) |

## The start-up (new in 0.6.0; only on a table just switched on)

S1, the one recording of a cold start (14 Nov 2026, i1Profiler 3.8.6, the tester's table),
read byte by byte from its raw capture file: after the USB set-up and `a1 a1 k2 u8 u8`, `a0`
answered `:$a00111800B6` (a started table answers `:$a00130000BD`). i1Profiler then sent, each
as one USB write, with these answers:

| S1 time | line | answer(s) | took | 0.6.0 checks |
|---|---|---|---|---|
| 1.517 | `;i02c` (line 46) | `:!i00C` 1.533, `:$i00D9` 4.684 | 3.167 s | accepted within 1 s; done with status 0 and no data within **1.0 to 8.0 s** (it waits for the done answer up to 15 s) |
| 4.693 | `;s022` (6) | `:$s00CF` | 0.007 s | as recorded |
| 4.706, 4.716, 4.738, 4.748 | `;f42b` x4 (7) | `:$f400078` (00) each | 0.010-0.016 s | 00 each |
| 4.766 | `;s022` (6) | `:$s00CF` | 0.014 s | as recorded |
| 4.780 | `;p025` (8) | `:$p00044E000E20`: X 1102, Y 14 | 0.016 s | must read START_GUARD (X 1090 to 1115, Y -1 to 250), the box of every first homing |
| 4.796 | `;i12b` (9) | `:$i10D8` | 0.224 s | the homing's usual windows (0.6 s from Y up to 48, 1.1 s up to 80, 2.0 s up to 250) |
| 5.020 | `;s022` (6) | `:$s00CF` | 0.016 s | as recorded |

The only differences of a cold table seen in S1: the answer of a0 (111800), and that i0 is
needed (a status line sent to a cold table before i0 was refused with `:#s01CF` in the tester's
earlier trace run T1: that is what a refusal looks like). Every other answer, including a1,
k2 and the start of the memory block, was the same as on a started table. Between i0's done
answer and the next line, i1Profiler switched the i1Pro 2's light (4.689); this program never
talks to the instrument in the start-up.

**The window for i0, and why.** Recorded once, 3.167 s, with the arm believed at rest; what the
arm does during it is not recorded. Lower limit 1.0 s: under a third of the recorded time (a
much quicker answer would not be the recorded start-up). Upper limit 8.0 s: 2.5 times the
recorded time and longer than the longest movement ever recorded (a strip move, 7.215 s), room
for a travel to end positions from a slightly different start. Outside the window, on a refusal
(`:#i0` and a code), on any answer not in the recorded form, on no answer within 15 s, on a lost
link or Ctrl-C: nothing more is sent, and the person is told to switch the table off (a
movement may be unfinished) and to let i1Profiler start the table after switching it on again.

**What is different from the recording.** In S1, i0 followed a0's answer at once (0.000 s); here
it follows the person's typed yes, seconds or minutes later (the table never speaks unasked,
and the program listens for 0.05 s before every line). Nothing else: the ten lines, their order
and their bytes are S1's.

**Caps.** The start-up is 10 lines and 2 movements (i0 and the homing), at most once per sitting,
and comes ON TOP of the chosen part's caps (`Table.cold_allowance`): part A then at most 120
lines and 21 movements, part B 124 and 35, part C 8690 and 3062. On a started table the caps
are 0.5.1's, unchanged. After the start-up the table is treated as started, and the chosen part
begins as on a started table (its first homing reads the resting place again).

## Part A: the steps of 0.3.1 (each at most once per session, each only after the person's yes)

The opening (always first, only reads): `a1 a1 k2 u8 u8 a0 s0 f4 f4 f4 f4` (11 lines; a
table that answers a0 = 111800 gets the first six and nothing more, unless the person
chooses the start-up: then `i0 s0 f4 f4 f4 f4 s0 p0 i1 s0`, section "The start-up" above).

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
must read X 1090..1115, Y -1..250, `START_GUARD`, since 0.3.1; the checks at rest after a homing
from the table and before the free-arm homing read X 1101..1103, Y -1..80, `REST_GUARD`). Between two moves that i1Profiler sent back to back, the program reads the position once (the recorded spot-pass pattern `m0 p0 m0`) and stops if the first move did not arrive. Every movement must finish inside its time window
(`TIME_WINDOW` in the program, from the recorded times, widened); every arrival is checked by
a p0 against the target (plus or minus 5 units). The person is never asked anything while the
arm is away from its resting place.

## Part B: the recorded spot row over the empty table (new in 0.4.0)

The opening as in part A, then these steps, in this order, each only after the person's yes;
each needs the one before it. The optional steps are offered only where named.

| id | step | lines (at most) | movements | risk | lines in order |
|---|---|---|---|---|---|
| B1 | b_home | 4 | 1 | low | `s0 p0 i1 s0` |
| B2 | b_align | 19 | 3 | medium | `f4 f4 p0 m0 p0 m0 p0 m1 p0 s0 f4 f4 f3 f4 f4 f1 f4 f4 p0` |
| B3 | b_place | 11 | 0 | low | `s0 f4 f4 f4 f4 p0 p0 p0 p0 p0 p0` |
| B4 | b_first | 4 | 1 | medium | `p0 p0 m0 p0` |
| B5 | b_row | 54 | 27 | low-medium | `p0 m0` x 27 |
| B6 | b_end | 8 | 1 | low | `s0 p0 i1 s0 f0 f4 f4 p0` |
| opt | home_from_patch | 8 | 1 | medium | `s0 p0 i1 s0 f0 f4 f4 p0` |
| opt | close_after_end | 3 | 0 | low | `s0 f0 f3` |

Hard caps for part B: per step its own lines and movements (above); per session **114 lines, 33 movements** (the opening, every B step once, and the close after the end of job; the homing from a patch replaces the rest of the row and the end of job and never adds to it). Part A keeps **110 lines, 19 movements**.

Details: in B2 the arm is read after each of the three moves; after m1 it must read either `AT_M1_SENSOR` (X 2827 to 2837, Y 1366 to 1376: m1 moved the sensor like an m0) or `AT_M1_SIGHT` (X 2697 to 2742, Y 1033 to 1080: m1 placed the sight there, the belief); after f1 the free arm must read within 5 units of that. B3: after the person's first "placed", `s0 f4 f4 f4 f4` (each 01), then one `p0` per try, at most 6 tries, until the arm reads inside `START_BOX` (X -1360 to -1200, Y 2600 to 2700). B4: `p0` inside `START_BOX`, a second `p0` within 2 units of the first, then the first patch move, then a 1 s pause and `p0` at patch 1 plus or minus 5. B5: 27 times [1 s pause, `p0` at the patch reached plus or minus 5, the next patch move]; then 1 s. B6: `s0`, `p0` at patch 28, `i1`, `s0 f0 f4 f4` (00 00), `p0` at rest (REST_GUARD). Time windows: m1 0.25-0.80 s (recorded 0.399-0.400), first patch 1.0-2.4 s (1.456), patch 0.35-0.70 s (0.431-0.432), homing from the row end 1.6-4.5 s (2.559), homing from another patch 1.0-6.0 s (2.559, 3.711).

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
| i1, m0, m1 | status 0, no data, inside the time window of that movement |
| f0, f3 | `:$f00007C`, `:$f300079` (00) |
| f1 | `:$f10017A` (01) |

## Never sent in parts A and B (the tests check that no such line exists in their code)

i0 outside the start-up (it is never part of a part's own steps), m2, c3, c4, d1, a3 (the scanning lines, which occur only
between "arm at a patch" and "reading" in a scan), p1, any u8 other than the two reads, any
write to the table's or the instrument's memory, any m0 other than the 32 fixed lines, any m1
other than the one recorded line, any other speed, any traffic to the i1Pro 2, and any command
id or argument not in the table above.

## Part C (0.5.0): what it adds

Part C's gate is `i1io_c_lines.classify` (called by `Table._write` for every line, and once
more by the USB writer itself). It passes exactly three kinds of line and nothing else
(`tests/test_i1io_part_c.py` checks every line of every simulated sitting against it, and that
it refuses every other form):

1. Lines 1 to 11 and 14 to 45 above, byte for byte (not part A's two moves to Y 250 and Y 1000).
2. Five further lines, each byte for byte as i1Profiler sent it to the tester's table:

| # | line (ASCII, then CR) | hex | name in the program | recorded at |
|---|---|---|---|---|
| C1 | `;p124` | `3b 70 31 32 34 0d` | aim | after each of the 30 button presses of the ten recorded alignments, 3-5 ms after the press, arm free (R1 263.517 ... S2 710.005); answer 8 data characters |
| C2 | `;c42e` | `3b 63 34 32 65 0d` | scan_c4 | at the start of all 44 recorded row scans, 1 ms after the i1Pro 2's lights-off (R1 9, R2 12, S2 23); answer one byte B7..BB, 0.171-0.218 s |
| C3 | `;d1016d35` | `3b 64 31 30 31 36 64 33 35 0d` | scan_d1 | before all 44 recorded row scans, always 016d (365); answer the echo 016D |
| C4 | `;a331` | `3b 61 33 33 31 0d` | scan_a3 | 0.016 s after all 44 recorded m2 lines, while the scan move waits; answer A, T, V |
| C5 | `;c32f` | `3b 63 33 32 66 0d` | scan_c3 | right after a3 in all 44 recorded row scans; answer no data |

3. COMPUTED moves, built only by `i1io_geometry.m0_line` / `m2_line`, in exactly the recorded
   form apart from the numbers (`;m0` or `;m2`, X, Y as 16-bit two's complement in lower-case
   hex, the speed, the recorded checksum rule, CR):
   * `m0` only at the recorded chart speed **300**;
   * `m2` (the strip move) only at a recorded scan speed: 40, 53, 54, 61, 87, 88, 110, 118, 137, 138 (mm/s);
   * the target inside the measuring area X -1384..1716,
     Y 523..2723 (a 320 x 230 mm area, the size X-Rite gives for the i1iO and the i1iO 3 and
     our assumption for the i1iO 2, placed on the table as derived in `i1io_geometry.py` from
     where the measuring opening was READ (p0) in the recordings, minus 5 mm on every side;
     where it lies on the table is our estimate);
   * only right after a position reading, and the whole rectangle swept from that reading to
     the target inside X -1434..1766, Y 473..2773;
   * fix 2, the FRONT ZONE: in front of that, targets up to Y 3109 at the most (up to the
     frontmost mark of the recorded alignments, p1 Y 3109, and no further; `classify` refuses
     anything beyond it on every computed line), a target only up to the Y this sitting has
     confirmed (`Table.front_y`; swept rectangles up to 5 units beyond it, never beyond Y 3114,
     because a move may start where the arm reads after a clean arrival); confirming it is stage DZ: m0 at 300 of at most 50 units per axis
     from a fresh reading and at most 50 units beyond the confirmed Y (the gate checks it on
     the bytes), at most 11 movements per run, 3 runs per sitting.

Answers part C expects to its own lines (anything else is a doubt):

| line | answer |
|---|---|
| p1 | status 0, 8 hex characters (a position) |
| c4 | status 0, one byte; only B7..BB (recorded) lets the strip go on |
| d1 | status 0, the echo `016D` |
| m0 (computed) | status 0, no data, inside the time window predicted from the recorded moves |
| m2 | accepted at once; its done answer only after the instrument's lamp, within the recorded 0.42-0.50 s after lamp + T + A (accepted 0.25-1.20) |
| a3 | status 0, 20 hex characters (A, T, V; compared with the plan, logged) |
| c3 | status 0, no data |

Part C sends at most **8680 lines and 3060 movements** in one sitting.

Never sent in part C either: i0 (except in the start-up, before part C's first stage), any u8 other than the two reads, any write to the memory of
the table or the instrument, any other speed, any target outside the area, any line form not
seen in a recording. The instrument (0971:2000) is opened only by ChromIQ's reader in `bin/`;
what the reader sends to it is the reader's own (ArgyllCMS 3.5.0's i1Pro driver, the same
requests as ChromIQ 4.3.41 when you measure by hand; for strip readings, i1Profiler's requests
byte for byte); its memory write is compiled out.
