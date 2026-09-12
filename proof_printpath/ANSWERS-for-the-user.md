# Answers for the user verifying a profile

Two questions, both answered by driving the app and measuring the files, not by
reading the source. Everything below is checkable against the JSON in
`proof_printpath/onscreen/`.

---

## 1. "How would I get 'Through the Profile' to be enabled?"

**Short answer: the run you have selected in the bar at the top has to contain a
finished profile. That is the only thing standing between you and the option.**

ChromIQ keeps verification inside the profiling run it is judging, so the
question it asks is not "does this project have a profile" but "does *this run*
have one". There are four things it checks, and only the third is likely to be
your case:

1. **You have a chart on the Print Chart tab.** With nothing loaded, the whole
   "How this chart is printed" box is hidden, so the option is not there at all.
2. **Run type is set to Verification.** On a Profiling or Calibration run the
   Colour row is hidden, because there is nothing to print through yet. If you
   cannot see "Through the profile" at all, this is why.
3. **The run selected under "Profile run" has a built profile in it** (a `.icc`
   file in that run's folder). This is the one that greys the option out. Note
   that it is *that run*, not the project: if you have run 1 with a profile and
   run 2 without, the option is greyed the whole time the bar is on run 2, even
   though the profile you want is one click away. Switch "Profile run" to the
   run whose profile you are verifying and the option comes back.
4. **The chart is not one of the profile-tailored ones.** If the chart was built
   by the "From Profile Gamut" module, its colours already went through the
   profile when it was made, so the option is deliberately switched off and the
   other choice reads "Raw, already converted". Printing it through the profile
   a second time would print different colours from the ones being tested and
   nothing afterwards could tell.

**The app does tell you which of these it is.** Whenever the option is greyed
there is a message directly under the box, about a finger's width below the
radio button, that names the reason and the way out. Measured on screen it is
fully painted at every window size we tried, so it is not hidden behind
anything — but it is below the box rather than on the button, so it is easy to
read past. In the "no profile in this run" case it says:

> **There is no finished profile in this run yet**, so there is nothing for
> ChromIQ to print through. You can still print this sheet raw and measure it,
> but the result would describe your printer, not a profile, so it cannot tell
> you how accurate a profile is.
>
> To get there: set **Run type** to **Profiling**, then create, print and
> measure the profiling chart as usual, and build the profile on the **Build
> Profile** tab. Come back here afterwards and this option will be waiting for
> you.

**Is it a fault?** No, in the sense that matters: the control is not greyed in
silence, and everything it does matches the design record
(`docs/design/verification_printing_and_target.md` §3.1 rows A3/A4 and §3.1a).
One thing is worth flagging for us rather than for her: that message assumes the
project has no profile anywhere, so a user who has a profile in another run is
told to build one they already have. Nobody needs a code change to get
unstuck, but the wording could name the run.

---

## 2. "Is the .tif file saved in the verifications folder pre-converted?"

**Short answer: no. That file is the raw chart. If you print it yourself, you are
printing the unconverted sheet, and the measurement will describe your printer
rather than your profile.**

Measured, not deduced. A chart's `.ti2` lists the exact device value of every
patch. A raw sheet paints those numbers; a converted one cannot. So we compared
the two:

| file | how many of the 99 device values in the `.ti2` are painted verbatim |
|---|---|
| `verifications/<name>-verify_01.tif` as ChromIQ leaves it | **99 of 99 (100 %)** |
| the same page after ChromIQ converts it through the run's profile | **9 of 99 (9 %)** |

(The nine survivors are the extremes the profile happens to map to themselves,
black among them. The two files are not byte-identical.)

**Where the converted sheet actually lives.** ChromIQ does not overwrite the
chart. When you choose "Through the profile" and print, it converts each page at
that moment and writes the converted copy into a **`cache` folder inside the
verifications folder**, then sends that copy to the printer. The `cache` folder
is always safe to delete; the chart beside it stays raw so it can be converted
again with a different profile or intent later.

**So what does the Print Chart tab do with the file?**

* **Colour = Through the profile, Route = Print here.** ChromIQ converts, prints
  the converted copy, and sends it with no colour management of any kind, which
  is right, because the colour work is already done. This is the one to use.
* **Colour = Raw.** The chart goes to the printer exactly as it is. Useful for a
  different question, "is my printer still behaving as it did last month", but
  it cannot tell you how good the profile is.
* **Colour = Through the profile, Route = In another application.** ChromIQ
  converts the pages and opens the folder holding them, so you can print them
  from somewhere else. **This is the answer if you want to print it yourself:**
  take the files from that folder, not the ones next to the chart, and print
  them with colour conversion switched off and at 100 % size.

Whichever you pick is written into a small record beside the chart, so the
report can say later which of the two questions a set of figures answered.
