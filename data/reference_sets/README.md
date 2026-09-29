# Reference data for the Measurement Report

A **reference set** is a table of aim colours: what a patch was supposed to
look like. It is not a limit set. A limit set says how close is close enough,
and those live next door in `data/compliance_sets/` and in
`workflow/compliance_sets.py`. The two are kept apart on purpose, and §7.1 of
the specification says why.

## What is in here

`fogra/` holds Fogra characterisation data, unmodified, as Fogra publishes it.

`fogra/SOURCE.json` records, per file: where it came from, the terms it comes
under, which archive and which published date, when it was downloaded, and the
sha256 of the file as shipped. **`workflow/reference_sets.py` refuses to offer a
file that has no entry there, or whose entry names no source and no terms.** The
credit condition below is therefore met by construction, not by a reader
remembering to write a line.

Eleven printing conditions are bundled, each as Fogra's own **72-patch
MediaWedge V3 subset** rather than the full 1,617-patch set. Seventy-two patches
fit a verification chart; 1,617 is a profiling chart. The full sets exist and
are not bundled, because nothing in ChromIQ can use one yet.

| File | Printing condition |
|---|---|
| `FOGRA51_MW3_Subset.txt` | coated commercial print, current (ISO 12647-2:2013, premium coated) |
| `FOGRA52_MW3_Subset.txt` | uncoated commercial print, current (ISO 12647-2:2013, wood-free uncoated) |
| `FOGRA39_MW3_Subset.txt` | coated commercial print, before 2016 (ISO 12647-2:2004/Amd 1) |
| `FOGRA47_MW3_Subset.txt` | uncoated commercial print, before 2016 |
| `FOGRA56_MW3_Subset.txt` | coated, matt laminated |
| `FOGRA57_MW3_Subset.txt` | coated, glossy laminated |
| `FOGRA45_MW3_Subset.txt` | magazine, improved light-weight coated |
| `FOGRA46_MW3_Subset.txt` | magazine, standard light-weight coated |
| `FOGRA42_MW3_Subset.txt` | newspaper, standard newsprint |
| `FOGRA48_MW3_Subset.txt` | newspaper, improved newsprint |
| `FOGRA60_MW3_Subset.txt` | metal decoration (ISO 12647-9:2021, white coated metal) |

## Credits, and the conditions attached to them

**Fogra Forschungsinstitut für Medientechnologien e.V.** is the source of every
file in `fogra/`. Their terms, quoted from
https://fogra.org/en/downloads/work-tools/characterisation-data as read on
2026-09-10:

> Free use and redistribution of the Fogra characterisation data is permitted,
> including redistribution as part of commercial and non-commercial software,
> provided that the data are distributed unmodified and Fogra is identified as
> the source. The designation FOGRAxx may be used solely to identify the
> respective reference data. Such use does not imply certification, approval or
> endorsement by Fogra.

Three things follow, and ChromIQ has to make each of them true rather than
merely avoid contradicting it.

1. **Fogra is named wherever the data is used.** On screen beside the chosen
   set, and in the saved report's own text, not in a footer.
2. **The data is passed on unmodified.** These are Fogra's bytes with Fogra's
   header. ChromIQ reads them; it never rewrites one. If ChromIQ ever converts a
   value between colour spaces or rounds it, the result does not keep the
   FOGRAxx name, because altered data must never be presented as the original.
3. **Naming a set is not a certification.** Saying a measurement was compared
   against FOGRA51 says what it was compared against. It does not say the print
   conforms to anything, is approved by anybody, or is endorsed by Fogra.

## The promise that governs all of it

**ChromIQ never says that a print conforms to, is certified to, or qualifies as
any standard or any printing condition.** It says what it measured, what it
compared that against, and what it could not check. That promise was made to a
rights holder in writing and it holds permanently, in every language ChromIQ
speaks.

A reference set supplies **aim colours only**. The limits a value is judged
against always come from a ChromIQ limit set or from the user's own, so the word
PASS never appears under a Fogra name.

## What a reference set can and cannot judge, and why

ChromIQ profiles RGB printers. Every set in `fogra/` describes a **CMYK**
printing condition. A ChromIQ verification sheet and a Fogra CMYK set have no
patch in common except the paper: the sheet's device values are R, G and B, the
set's are C, M, Y and K, and there is no correspondence between them.

So on an ordinary verification sheet, exactly one row can honestly be filled
from one of these files: **the paper**. A paper's colour is a property of the
paper and not of the process that will be printed on it, and both numbers are a
measurement of bare stock.

The solid colours cannot be. Pairing a printer's most saturated cyan with a
100 % cyan offset solid because both are called C is pairing two things because
their labels rhyme, and the large number that results is not a fault in the
printer. `workflow/reference_sets.py` refuses that pairing rather than warning
about it.

Everything beyond the paper needs a chart whose patches were produced **from**
the reference set's aim colours through the profile under test. That is a proof,
it is what the industry does, and ChromIQ has the machinery for it from the
verification work of August 2026. It is not built against Fogra data yet.

## Adding a file

Add its entry to `fogra/SOURCE.json` in the same change, with its source, its
terms and its sha256. A file without one will not load, which is deliberate: a
data file with no credit beside it is a licence breach waiting to happen, and
the grant above is conditional on the credit existing.
