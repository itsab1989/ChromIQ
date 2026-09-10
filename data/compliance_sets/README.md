# Limit sets for the Measurement Report

A **limit set** is one column of the Report limits table: the number a report
judges each row against. ChromIQ's own sets are defined in code, in
`workflow/compliance_sets.py`. This folder holds the sets whose numbers belong
to somebody else.

## What is in here today, and what is not

`iso12647.json` **ships empty, on purpose.** It is the file that would carry the
tolerance values of ISO 12647-7:2016 and ISO 12647-8:2021, and it carries none
of them, because nobody has given ChromIQ permission to publish them. ISO's
answer was that reproducing the content of a standard inside software needs
explicit permission or a licence, that a single-user reading licence is not
enough, and that the route is the national member body. That request is open.

Until it is answered:

* no ISO cell holds a number. Most read `?`, meaning the value exists in the
  standard and we have not licensed it; others read `–` where the standard sets
  no limit on that row, or `✕` where ChromIQ has no way to measure it at all;
* neither ISO set can be chosen for a run;
* nothing is hidden or masked to make it look otherwise.

**If you own the standards**, you can supply the numbers yourself and ChromIQ
will use them without ever distributing them. Two ways, both already built:

1. **Type them in.** In the Report limits window, a Custom column is editable.
   The cells you can type into are the ones showing a dash, because an empty
   spin box paints itself that way; a cell still showing `?` is one ChromIQ
   cannot evaluate from a chart it can read, so a number there would have
   nothing to judge, and it will still read `?` after any licence arrives.
   The dash is doing double duty here and that is confusing, so it is worth
   saying plainly: in a Custom column, type into the dashes.
2. **Point ChromIQ at your own file.** Set the environment variable
   `CHROMIQ_COMPLIANCE_ISO_FILE` to the path of a JSON file in the shape
   `iso12647.json` describes, and ChromIQ reads that instead of the empty one
   it ships. Nothing is copied into ChromIQ and nothing is published.

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
That is why a report judged against an ISO column can never read PASS overall.
It is a limit of what is being measured, not of what has been licensed, and it
will not change when a licence arrives.
