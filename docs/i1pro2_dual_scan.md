# M0, M1 and M2 from an X-Rite i1Pro 2: the dual scan, step by step

This guide shows how to measure a chart by hand with the **dual scan** of an X-Rite i1Pro 2,
what to look for at each step, and what to send us after a first try. The dual scan is new in
ChromIQ 4.3.48. It is a beta option and a first try: **no part of it has run on a real
instrument yet.** Please read [Honest limits](#honest-limits) before you rely on it.

> The pictures in this guide were made with the real ChromIQ app in a real window, but with a
> **simulated instrument**: the readings are invented, and so are the three "suspected misreads"
> in picture 9. The paths in the pictures were shortened to `~/ChromIQ/...`.

## What the dual scan is, and what it is for

M0, M1 and M2 are three ways of measuring the same colour. They differ only in how much
ultraviolet (UV) light reaches the paper:

* **M0** is what the instrument's own lamp gives. Until now this was all an i1Pro 2 gave ChromIQ.
* **M1** adds the amount of UV that daylight has (the ISO 13655 condition for D50).
* **M2** leaves the UV out altogether ("UV cut").

They matter for papers with optical brighteners, which glow blue under UV light. On such paper
the three conditions give noticeably different numbers, and a profile made from the condition
that matches how your prints will be viewed can be the better one.

An i1Pro 2 has a small UV light beside its lamp. X-Rite's own software uses it to read each strip
a second time. With the dual scan on, ChromIQ does the same: it reads every strip twice, first
as usual with the lamp, then once more over the same strip with the UV light, and works out M1
and M2 from the two readings and the data X-Rite stored in your instrument at the factory.
ChromIQ does this itself: you do not need i1Profiler or a licence for any X-Rite software.

## What you need

* An **X-Rite i1Pro 2** (ArgyllCMS calls it the "Eye-One Pro Rev E"), with its **white
  calibration tile** and its **position ruler** (the guide the instrument slides along when you
  read a strip). **The dual scan by hand needs the ruler**: ChromIQ matches the two passes patch
  by patch with the instrument's position readings. Without the ruler, ChromIQ measures M0 only.
* A chart made in **Create Chart** for the i1Pro (the "i1Pro" entry covers the i1Pro 2).

Which instruments cannot do it:

* The **first i1Pro** (ArgyllCMS: Rev A, B or D; also sold as the EFI ES-1000) has no UV light.
* Some **OEM i1Pro 2** units, such as an EFI ES-2000, were built without the UV light (ArgyllCMS
  names the part number EO2-XR-UF for them), and some units may lack the factory data the dual
  scan needs. You do not need to find out which kind yours is: choose "i1Pro 2" for it all the
  same. ChromIQ notices it by itself at the start of the measurement or at the calibration, and
  such an instrument then measures as always, without the dual scan (so without M1 and M2). The
  Measure log says why.
* The **i1Pro 3** and **i1Pro 3 Plus** need no dual scan: they keep M0, M1 and M2 in their own
  way (the option above the dual-scan switch is for them).

Not available with the dual scan: **"High resolution spectral mode (-H)"** (the instrument's
factory data for M1 and M2 is given only at 10 nm steps). Switch it off before a dual-scan
measurement.

## 1. Switch it on

Open **Preferences > Beta** and switch on **"X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from
every scan (beta)"**, then the switch under it, **"X-Rite i1Pro 2: also M1 and M2, by a dual scan
(beta, first try)"**. A window first says what the option does and asks you to confirm it. The ⓘ
beside each switch explains it in more detail.

Under the switch, **"Instrument for the dual scan:"** shows what ChromIQ remembers about your
instrument: "Ask before the next measurement" (nothing remembered yet), "i1Pro 2", or "Another
instrument (not an i1Pro 2)". You can change it here at any time.

![Preferences > Beta with both switches on and "Instrument for the dual scan:"](i1pro2_dual_scan/01-preferences-beta.png)

## 2. The Measure tab before START

Load your chart in the **Measure** tab as usual. The row **"Spectral filter type (-F)"** (under
Additional Options) now chooses **which condition your profile is made from**: "M0: no filter
(lamp as it is)", "M1: D50 daylight (with UV)" or "M2: UV cut (no UV)". With an i1Pro 2 it is not
sent to the instrument (an i1Pro 2 has no filter ArgyllCMS could switch); ChromIQ records your
choice. With the row switched off, the profile is made from M0.

The line under the log says **"Dual scan (beta, first try): each strip is read twice, on the
ruler"**, and the log explains it: first as usual with the lamp, then once more over the same
strip with the UV light, without lifting the instrument.

![The Measure tab before START: the filter row on M2 and the dual-scan line](i1pro2_dual_scan/02-measure-before-start.png)

Two things refuse the start, with a window that says what to change:

* **"Spectral filter type (-F)"** set to a choice an i1Pro 2 does not have (a polarising filter
  or D65).
* **"Skip initial calibration (-N)"** ticked: the dual scan needs a new calibration at the start of
  every measurement, because only then is the white tile read with the UV light too.

## 3. Which instrument?

The first time, if ChromIQ cannot tell from the USB connection which instrument is connected, it
asks **"Which instrument do you measure with?"** and explains how to tell the instruments apart.
Choose **i1Pro 2**. Not sure? Choose **Not sure**: ChromIQ then starts as for an i1Pro 2. Your
answer is remembered (see step 1).

At the start of every measurement the instrument reports itself (the Measure log shows a line
"Instrument Type:", which reads "i1Pro2" for an i1Pro 2), and that report always wins: if it is
not what ChromIQ assumed, ChromIQ starts the measurement again the right way before anything is
read, and says so.

![Which instrument do you measure with?](i1pro2_dual_scan/03-which-instrument.png)

## 4. The calibration: keep the instrument on its tile

Put the instrument on its white tile and start the calibration as usual. With the dual scan the
calibration also reads the tile with the UV light, which takes a few seconds more. **Keep the
instrument on the tile** until ChromIQ says you can lift it: the amber line under the chart says
"Keep the instrument on its white tile ...".

![The calibration: keep the instrument on its white tile](i1pro2_dual_scan/04-calibration-keep-on-tile.png)

When the window **Calibration Complete** says that the white tile was read with the UV light too,
you can lift the instrument.

![Calibration Complete: the tile was read with the UV light too](i1pro2_dual_scan/05-calibration-complete.png)

If the UV reading of the tile did not succeed, the window says that M1 and M2 cannot be worked
out from this calibration. M0 is measured as always; to have M1 and M2 as well, calibrate again
(press K or the Calibrate button) before the next strip.

## 5. Each strip twice: pass 1 with the lamp, pass 2 with the UV light

Put the instrument on the ruler at the strip the preview marks (the green arrows above and below
the strip). The line under the log tells you which pass is due.

**Pass 1 of 2 (lamp).** Read the strip as usual.

![Strip A, pass 1 of 2 (lamp)](i1pro2_dual_scan/06-strip-pass-1-lamp.png)

**Pass 2 of 2 (UV light).** Read the **same strip** once more, **without lifting the instrument
off the ruler**: from the white paper before the first patch to the white paper after the last,
at an even speed. **Either direction is fine**: the ruler tells ChromIQ which way you went. This
time the instrument reads with
its UV light.

![Strip A, pass 2 of 2 (UV light)](i1pro2_dual_scan/07-strip-pass-2-uv-light.png)

What to look for:

* The line under the log names the strip and the pass. Read pass 2 only when it says
  "pass 2 of 2 (UV light)".
* The green arrows in the preview mark the strip that is due. Both passes are of that strip.
* During pass 2 the instrument's UV light should come on. Please tell us whether you saw it.

ChromIQ checks that the second pass really belongs to the same strip: it matches the two passes
patch by patch with the ruler's positions and compares their readings. A second pass over the
wrong strip, one too short, too fast, too slow, one that jumped part of the way, one that does
not line up with the first, or one that brought back almost no light, is **refused**.

## 6. A refused second pass: both passes are read again

When a pass is refused, the window **Strip Read Failed** says why and what to do. For now
ChromIQ always reads the two passes of a strip together, so **both passes are read again**:
press **Retry** and read the strip with the lamp, then with the UV light. **Skip Strip** leaves
the strip for later in this session, **Save Partial & Quit** keeps what was read so far.

![Strip Read Failed: the second pass of strip B failed](i1pro2_dual_scan/08-second-pass-refused.png)

### When M1 and M2 stop for the measurement

In a few cases M1 and M2 cannot go on for the rest of the measurement. The Measure tab then says
**"Dual scan: M1 and M2 stop for this measurement"** with the reason, and that from here on
ChromIQ reads M0 as always, one pass per strip: carry on measuring. The cases are:

* the ruler cannot be used for the rest of the measurement (it gave no usable positions, or a
  second pass was left unread);
* the instrument is not an i1Pro 2, or does not offer what the dual scan needs;
* a strip was read after a calibration that could not give M1 and M2, without calibrating again
  first (ChromIQ asks you to calibrate again before that strip, and says what happens if you do
  not);
* a value was typed in by hand;
* the files for M1 and M2 could not be saved, or something unexpected happened (the app's log
  file has the details).

A strip read after that has M0 only, and **Continue Measurement cannot add M1 and M2 to it
later**: for M1 and M2, measure the chart again as a new measurement. Before you continue such a
measurement, the Measure tab says that it will continue as M0 only.

## 7. The end of the measurement and Build Profile

When every strip has both passes, **All Strips Read** appears as after any measurement.

![All Strips Read](i1pro2_dual_scan/09-all-strips-read.png)

The measurement is saved in M0 as usual, with M1 and M2 beside it. **Build Profile** then starts
with **"Build from:"** set to the condition you chose in the filter row of the Measure tab (here
M2), once every strip has both passes. The profile description gets the condition's name.

![Build Profile with "Build from:" set to M2](i1pro2_dual_scan/10-build-profile-build-from.png)

To build from another condition, open **"Build from:"** and choose it. Your choice stands.

![The choices of "Build from:": M0, M1 and M2](i1pro2_dual_scan/11-build-from-choices.png)

### Where the files are

All of it stays in the run's folder (`~/ChromIQ/<your project>/runs/runN/`):

* `<project>.ti3`: the measurement, in M0, as always.
* `conditions/<number>-M1.ti3` and `conditions/<number>-M2.ti3`: the same patches in M1 and M2.
  The number is made from the measurement's readings, so the files stay paired with them.
* `dual_scan/<project>.passes.json`: ChromIQ's record of both passes of every strip and of the
  calibration's UV reading. It holds no serial number.

## Honest limits

* **No part of the dual scan has run on a real instrument yet.** It was built from USB
  recordings of X-Rite's i1Profiler, made with two i1Pro 2 instruments, and checked against those
  recordings and with a simulated instrument. Everything ChromIQ sends to the instrument for it is
  in the forms seen in those recordings, and nothing is written into the instrument. The first
  real runs may still stop early, or be refused where they should not be. If that happens,
  ChromIQ says why.
* **How close M1 and M2 come to X-Rite's own values.** On the recorded readings, ChromIQ's M1 and
  M2 agree with i1Profiler's values to a few hundredths of a ΔE00 on average (about 0.05 to 0.08)
  when the instrument's own factor is known. That factor differs from instrument to instrument,
  and ChromIQ uses a **standard factor** (1.156) for every i1Pro 2. With it, M2 was off by about
  0.2 ΔE00 on average (up to about 0.5 on single patches) on strongly brightened paper for one of
  the two instruments, and by less for the other; M1 by less. Papers without optical brightener
  should not be affected, but that has not been measured yet.
* By hand, the dual scan needs the ruler; if one pass of a strip fails, both passes are read
  again; M1 and M2 cannot be taken up again with Continue Measurement once they have ended.
* The new texts are shown as proposed texts and may still be reworded.

## What would help us

After a first try, whether it worked or not, please send us on
[GitHub](https://github.com/itsab1989/ChromIQ/issues):

* from the run's folder: the **`conditions/`** and **`dual_scan/`** folders and the measurement
  (`<project>.ti3`);
* the text of the **Measure log** (select it in the Measure tab and copy it);
* a **USB recording** of the run, if you use a recording tool for that.

And please tell us:

* whether the **UV light came on during pass 2** (a faint violet glow under the instrument);
* whether any pass was **refused**, and with which message;
* whether M1 and M2 **stopped** for the measurement, and what the Measure tab said;
* which paper you measured, and whether it has optical brighteners.
