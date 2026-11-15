# Dual scan test kit for the i1Pro 2 (version 0.1)

Thank you for helping again. This kit is for one question: **can ChromIQ ever offer the i1Pro 2's
dual scan (M1 and M2), and compute those values well enough?**

i1Profiler's dual scan reads every row twice: forwards with the normal lamp, and back with the
instrument's UV light. Your earlier recordings showed us exactly how i1Profiler asks the instrument
for those two passes. What they cannot show is how i1Profiler turns the two passes into M1 and M2:
that happens inside i1Profiler. So we want to try our own way of computing M1 and M2 from the two
passes, and compare it, patch by patch, with what i1Profiler gives for the very same print. For that
we need the recordings AND i1Profiler's saved measurements of the same sheets.

**It may well turn out that ChromIQ cannot do this well enough.** That would also be a useful
result, and nothing in ChromIQ changes because of this test. ChromIQ already has a different way of
dealing with paper brighteners (the "FWA compensation" option), and our own computation would have
to be clearly better than that one before we offer anything.

## What you need

- Your i1Pro 2 (Rev E) with its calibration tile and the ruler and backing board.
- Windows, with **i1Profiler 3.8.6** (3.8.7 and newer no longer support the i1Pro 2), set up as for
  your earlier recordings.
- Our recording tool, **version 1.6.5** (`chromiq-io-probe-windows.exe` from the latest release of
  `itsab1989/chromiq-i1io-probe`), started as administrator, with USBPcap installed, as before.
- Two papers:
  - **one strongly brightened paper**: a paper that glows bright blue under a UV torch, or that is
    sold as "bright white", for example a common office or copy paper, or a bright-white photo paper;
  - **one paper without brighteners**: many cotton fine-art papers say "OBA free" or "no optical
    brighteners".
- The chart in this kit, printed once on each paper (A4 or US Letter, whichever you use).

**How long:** printing the two sheets (best the day before, so the ink can dry), then four short
recording sessions of about 15 to 20 minutes each. About 1.5 hours in all.

## What is in this kit

| file | what it is |
|---|---|
| `A4/DualScanTest-A4.pdf` and `.tif` | the chart to print on A4 (the PDF and the TIFF are the same sheet) |
| `A4/DualScanTest-A4-i1profiler-turned-i1Pro2.txf` | the i1Profiler test chart that matches the printed sheet |
| `A4/DualScanTest-A4-i1profiler-turned-how-to.txt` | step by step: how to turn the sheet and load the chart in i1Profiler |
| `Letter/...` | the same for US Letter |
| `*.ti1`, `*.ti2`, `*.channels.json`, `*-i1profiler-turned.json`, `*-i1profiler.txt/.pxf`, `*-colours.txt`, `patches.csv` | the chart's own files (patch list and layout); you do not need them, they are for our analysis |

The chart has **4 rows of 23 patches**, each 10 mm. Every row has paper white three times (second
place from each end, and in the middle), plus greys, yellows, light pastel colours and a few strong
colours: brighteners show most in white, light grey, yellow and pastel patches.

## Before you start: print the two sheets

1. Print the PDF (or the TIFF) of your paper size **once on the brightened paper and once on the
   paper without brighteners**, the way you print a profiling chart: **printer colour management
   off, and at 100 % size** (no "fit to page"). It is the same kind of print as a chart from
   ChromIQ or i1Profiler.
2. Write on the back of each sheet which paper it is.
3. Let the sheets dry, ideally a few hours or overnight.

## How each recording session works

You know the recording tool already. For this kit you run it **four times**, once per session
below, and each time you record only the steps listed, with the `--steps` option. To do that: open
**Command Prompt as administrator** (Start menu, type `cmd`, right-click "Command Prompt", "Run as
administrator"), go to the folder with the tool (for example `cd %USERPROFILE%\Downloads`) and
start it like this (the numbers change per session):

```
chromiq-io-probe-windows.exe --i1pro --steps 1,2,8
```

(If you prefer, you can also start the tool as usual and simply skip every step that is not listed.)

The tool's own text for each step talks about "one strip"; **for this kit, please do what this list
says in that step instead.** In the one-line note after each step, write what you did and what
i1Profiler showed, and which measurement mode was selected. Each session ends with its own
`SEND-THIS-....zip`.

**Close i1Profiler before every session.** Step 1 of each session is "start i1Profiler": when
i1Profiler opens the instrument, it reads the instrument's own calibration data, and we need that in
every recording.

Loading the chart in i1Profiler is explained step by step in the `...-how-to.txt` file of your paper
size (it says where on the Test Chart page to load the `.txf` file, and how to turn the sheet). In
short: turn the sheet a quarter turn clockwise, so that the wide empty border is at the top; the
top row is row 1. Measure the rows from top to bottom, each one from left to right, starting and
ending on the white paper beside the row. With dual scan, i1Profiler then asks you to scan each row
back, from right to left (last time the left light blinked blue for that).

## The checklist

### Session A: two small questions (brightened sheet), `--steps 1,2,8`

1. [ ] **Step 1:** start i1Profiler, wait until it shows the instrument, leave it alone about
       10 seconds. Then, while the tool waits between steps, load the chart (see the how-to file)
       and on the Measurement page choose **Single Scan (M0)**, so that **dual scan is off** and only
       M0 is used.
2. [ ] **Step 2:** calibrate, as i1Profiler asks. Note: "Single Scan (M0), dual scan off".
3. [ ] **Step 8:** on the Measurement page choose **Spot (M0)** and read **one** patch (any white
       patch of row 1). Note what was selected.
       Nothing to save from i1Profiler in this session.

*What this answers:* whether i1Profiler still uses the UV light during calibration and for a spot
reading when only M0 is selected.

### Session B: the main one (brightened sheet), `--steps 1,2,4,6`

4. [ ] **Step 1:** start i1Profiler, leave it alone about 10 seconds. Between the steps: load the
       chart and choose **Dual scan (M0,M1,M2 and OBC)** on the Measurement page (last time you
       noted "dual scan is ticked" and "M0, M1, M2 and OBC": the same setting).
5. [ ] **Step 2:** calibrate. Note the mode.
6. [ ] **Step 4:** measure **the whole chart** in dual scan: all 4 rows, each forwards and back. If
       i1Profiler asks you to read a row again, do so (and mention it in the note).
7. [ ] After step 4, before you start step 6: **save the measurement** in i1Profiler as an `.mxf`
       file (Page Data, Save, on the Measurement page), named `B1.mxf`. If it offers which values to
       include, include **M0, M1, M2** and OBC.
8. [ ] **Step 6:** measure **the whole chart again** in dual scan, the same way, from row 1. (We
       have not seen how i1Profiler starts a second measurement of a chart it has already measured;
       whatever it takes, the goal is a second complete measurement of all 4 rows. Please note what
       you had to do.)
9. [ ] Save that second measurement as `B2.mxf`, the same way.

### Session C: the paper without brighteners, `--steps 1,2,4`

10. [ ] **Step 1:** start i1Profiler; load the chart; choose **Dual scan (M0,M1,M2 and OBC)**.
11. [ ] **Step 2:** calibrate.
12. [ ] **Step 4:** measure the whole chart on the **brightener-free sheet** in dual scan.
13. [ ] Save it as `C.mxf` (M0, M1, M2 and OBC).

### Session D: single scans and one slow return (brightened sheet), `--steps 1,2,3,5`

14. [ ] **Step 1:** start i1Profiler; load the chart; choose **Single Scan (M0)**.
15. [ ] **Step 2:** calibrate.
16. [ ] **Step 3:** measure the whole chart (4 rows) in **Single Scan (M0)** on the brightened sheet.
        Save it as `D.mxf`.
17. [ ] **Step 5:** switch to **Dual scan (M0,M1,M2 and OBC)** (calibrate again if i1Profiler asks)
        and read **row 1 only**: forwards at your normal speed, and **back clearly slower**, about
        twice as long, with a short stop of about one second halfway back if i1Profiler lets you.
        Note in one line what i1Profiler said. Nothing to save.

*Why:* session D checks that the dual scan's forward pass equals a normal scan, and the slow return
tests how well we can line the two passes up.

### Optional: a second i1Pro 2

18. [ ] If someone else with an i1Pro 2 would like to help, session B with their instrument (and
        their own print) is the single most useful extra: it tells us whether our computation
        depends on one instrument.

## What the files contain, and where to send them

- Each `SEND-THIS-....zip` holds the USB conversation between i1Profiler and your instrument, your
  notes and the tool's analysis. As the tool tells you before you start, that conversation
  **contains your instrument's serial number and its factory calibration data**, because i1Profiler
  reads them every time it opens the instrument. They identify the instrument, not you.
- The `.mxf` files hold your measurements and, in their header, **also the instrument's serial
  number**.
- The tool's `--clean` option is only for recordings made with version 1.6.1 or older (it removes
  other USB devices' traffic); it does not remove the serial number, and 1.6.5 recordings do not
  need it.
- **We never publish the serial number or the calibration data**, and nothing we write about the
  results will contain them.

Please put the four `SEND-THIS-....zip` files and the `.mxf` files (`B1`, `B2`, `C`, `D`) into one
`.zip` and **attach it in the forum thread, as you did before**. If you would rather not have your
instrument's serial number in a public post, send the zip as a **private message to itsab1989** on
the forum instead (the recording tool's README offers the same).

Thank you!
