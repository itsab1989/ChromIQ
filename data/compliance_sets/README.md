# Limit sets for the Measurement Report

A **limit set** is one column of the Report limits table: the number a report
judges each row against. ChromIQ's own sets are defined in code, in
`workflow/compliance_sets.py`. This folder holds the sets whose numbers belong
to somebody else.

## What is in here, and on what basis

`iso12647.json` is the file that carries the tolerance values of
ISO 12647-7:2016 and ISO 12647-8:2021. **Each of its two sets is either empty or
complete, never half of one**, and a test holds it to that.

**The values may ship, as values only.** ISO's first answer was that
reproducing the content of a standard inside software needs explicit
permission or a licence, and that the route is the national member body. That
body, DIN, answered through its legal department in writing on 2026-09-23:

> *"wenn Sie definitiv nur Werte aus der Norm verwenden – keine Bilder, keine
> Seiten, keine Texte, dann fällt das nicht unter Vervielfältigung."*
>
> (If you definitely use only values from the standard, no images, no pages,
> no texts, that does not count as reproduction.)

So a complete set holds one number per row and nothing else: the row names,
the help texts, the order and the layout are ChromIQ's own, and no wording,
table, figure or page of either standard is in this folder or anywhere in
ChromIQ. The statement is about the general rule and covers both parts alike.
The values are put in on the owner's go-ahead, with
`scripts/install_iso_12647_values_into_repo.py`, which prints no value.

What each state means on screen:

* **A complete set** fills its read-only column, which judges like any other
  and can be chosen for a run. The Custom column beside it does NOT start from
  those values: it keeps the limits researched from industry practice that
  Knut set as its defaults, so the two columns can be read against each other.
* **An empty set** is one ChromIQ does not ship. Its cells read `?`, meaning
  the value exists in the standard and is not here; others read `–` where the
  standard sets no limit on that row, or `✕` where ChromIQ has no way to
  measure it at all. It cannot be chosen for a run.
* Either way, nothing is hidden or masked to make it look otherwise.

**If you own the standards**, you can supply the numbers yourself and ChromIQ
will use them without ever distributing them. A number you supply takes the
place of the shipped one for its row, a row you leave out keeps the shipped
one, and a Custom column starts from YOUR figures where you gave them. Two
ways, both already built:

1. **Type them in.** In the Report limits window, a Custom column is editable.
   The cells you can type into are the ones showing a dash, because an empty
   spin box paints itself that way; a cell still showing `?` is one ChromIQ
   cannot evaluate from a chart it can read, so a number there would have
   nothing to judge, and it will still read `?` after any licence arrives.
   The dash is doing double duty here and that is confusing, so it is worth
   saying plainly: in a Custom column, type into the dashes.
2. **Point ChromIQ at your own file.** Set the environment variable
   `CHROMIQ_COMPLIANCE_ISO_FILE` to the path of a JSON file in the shape
   `iso12647.json` describes, and ChromIQ lays it over the one it ships.
   Nothing is copied into ChromIQ and nothing is published.

Either way the numbers are yours, they stay on your machine, and a report you
then send to somebody else carries them. That last part is worth a thought
before you send one.

## Credits, and the conditions attached to them

No third-party reference data is bundled in ChromIQ yet. The lines below are
here **before** any such file arrives, so that no data can ever land in this
folder without its credit sitting beside it. Each is the condition its owner
actually stated, in writing, when they gave permission.

* **Fogra Forschungsinstitut für Medientechnologien e.V.** Fogra's
  characterization data may be used and passed on unchanged, including inside
  commercial software, **provided Fogra is clearly named as the source**. Naming
  a Fogra reference set to say what a print was compared against is a statement
  of what was compared, and is **not** a certification, an approval or an
  endorsement by Fogra.
* **CGATS, through the Association for PRINT Technologies.** The CGATS data sets
  have been made generally available to the industry and may be used in
  software. No further condition was stated.
* **ICC.** Registry data may be redistributed, with the proviso that **altered
  data must never be presented as the original**. If ChromIQ ever changes a
  value, converts it between colour spaces, or rounds it, the result does not
  keep the original name.
* **DIN (Deutsches Institut für Normung), for ISO 12647-7 and ISO 12647-8.**
  The standards' values may be used, as values only: *"keine Bilder, keine
  Seiten, keine Texte"* (no images, no pages, no texts), in DIN's legal
  department's words of 2026-09-23. ChromIQ names the standards and uses their
  values; everything around the values is its own.
* **Idealliance, now PRINTING United Alliance.** Their profiles may be included
  in and distributed with software, under any licence, **provided the profile is
  unaltered**. Running a device value through a profile to obtain an aim colour
  is use, not alteration. They ask that we print:

  > GRACoL is a registered trademark of PRINTING United Alliance.

## The promise that governs all of it

**ChromIQ never says that a print conforms to, is certified to, or qualifies as
any standard.** It says what it measured, what it compared that against, and
what it could not check. That promise is not a house style: it was made to a
rights holder in writing as part of the permission above, so it holds
permanently, in every language ChromIQ speaks.

A limit set named after a standard means *the numbers in this column are that
standard's published figures, applied to the chart you printed*. It does not
mean the chart is that standard's control strip, and ChromIQ cannot make it one.
It is a limit of what is being measured, not of what has been licensed, and it
will not change when a licence arrives.

Such a column reads PASS or FAIL like any other, for the metrics that were
checked, and every report carrying one prints a note beside the result saying
what that PASS is: **an indication that the print would likely meet the
standard, and not proof that it does.** The note is the promise; the verdict
word is not.

*(Until 2026-09-22 the word carried it instead: a column named after a standard
was held at COND however well it read, and this paragraph said a report judged
against one "can never read PASS overall". Knut retired that cap, on the
reasoning that most people want to know whether the measurements passed the
criteria they chose, and that the note is where the rest belongs. Nothing about
the promise above changed with it.)*
