# Third-party notices — every bundled asset, and on what terms it is here

ChromIQ itself is GPLv3 (`LICENSE`). This file covers everything ChromIQ
*ships* that somebody else wrote: the files under `assets/`, `data/` and
`native/` that end up inside `dist/ChromIQ.app` or the Windows build.

**It exists because one of them was here on terms nobody had read.** From v2.3.0
to 4.1.5-beta, `assets/USWebCoatedSWOP.icc` (now removed) — 557,168 bytes, whose
own copyright tag reads *"Copyright 2000 Adobe Systems, Inc."* — shipped with
no licence, no attribution, and nothing anywhere recording that anyone had asked
whether we were permitted to redistribute it. It was added in one line of an
eight-file commit (`a4c7c53f`, *"assets: bundle USWebCoatedSWOP.icc so ICC
conversion works on all Macs"*). That was our error, made by an earlier session
of this assistant, not the owner's.

The terms have since been read. Adobe's end-user agreement for these profiles
says *"No other distribution of the Software is allowed; including, without
limitation, distribution of the Software when incorporated into or bundled with
any application software."* We were not compliant. The file has been removed —
see [The Adobe profile](#the-adobe-profile-removed) below for the full quotes,
both agreements, and what replaced it.

`tests/test_every_bundled_asset_says_on_what_terms_it_is_here.py` enforces this
file, so it cannot quietly go out of date the way the note it replaces never
existed to.

---

## The rule

**A file that ChromIQ did not write, and that ChromIQ ships, must have its terms
stated here — before it is committed, not after somebody asks.** "Someone said
it would be fine" is not a term. If the terms cannot be established from a
primary source, the file does not ship.

Two things are *not* redistribution and need no entry: reading a profile the
user already has installed on their own machine, and shelling out to an
ArgyllCMS binary the user installed themselves.

---

## Colour profiles — `assets/profiles/`

Five ICC profiles, each **copied byte for byte** from ArgyllCMS 3.5.0's `ref/`
folder. Each one carries its own public-domain dedication in its ICC `cprt`
tag, written by the copyright holder and readable from the file itself:

> `Created by Graeme W. Gill. Released into the public domain. No Warranty, Use at your own risk.`

(`ClayRGB1998.icm` words it as *"Public Domain. No Warranty, Use at own risk."*)

| file | bytes | md5 | ICC `desc` |
|---|---|---|---|
| `ClayRGB1998.icm` | 576 | `ebcf7a256031f62815bf7b3bdca02b1e` | Interchangeable with Adobe RGB (1998) |
| `cmyk.icm` | 961,644 | `6de8c139e9c1a54afd513d03efb7501f` | Chemical proof |
| `DisplayP3.icm` | 2,740 | `8033598b9b9fff5de8c1cc7ebbdc56eb` | DisplayP3 color profile |
| `ProPhoto.icm` | 2,748 | `4a11993a32909bb6a532e25ee223080b` | ProPhoto RGB |
| `sRGB.icm` | 3,004 | `7c93b91188d4b5c1c91712bcbd3da013` | sRGB IEC61966-2.1 |

**Terms: public domain.** No notice obligation, no attribution requirement, no
restriction on modification or sale, and so nothing that could conflict with the
rights GPLv3 grants everyone who receives ChromIQ. The dedication is credited
here anyway, because crediting people who give their work away is worth doing.

Author: Graeme W. Gill, <https://www.argyllcms.com/>. The ArgyllCMS *programs*
are AGPLv3; these data files are not, by their own notice.

`cmyk.icm` is the one the CMYK TIFF preview uses
(`ui/tiff_preview.py::_get_cmyk_transform`). The other four are ChromIQ's
mirror of Argyll's `ref/` for users whose Argyll install hides it
(`core/argyll_detect.find_ref_profile`, `workflow/softproof_runner`).

---

## Fonts — `assets/fonts/`

| family | files | copyright (from each font's own `name` table) |
|---|---|---|
| Inter | `Inter-VariableFont_opsz,wght.ttf`, `Inter-Italic-VariableFont_opsz,wght.ttf` | Copyright 2016 The Inter Project Authors (https://github.com/rsms/inter) |
| JetBrains Mono | `JetBrainsMono-VariableFont_wght.ttf`, `JetBrainsMono-Italic-VariableFont_wght.ttf` | Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono) |
| Instrument Serif | `InstrumentSerif-Regular.ttf`, `InstrumentSerif-Italic.ttf` | Copyright 2022 The Instrument Serif Project Authors (https://github.com/Instrument/instrument-serif) |

**Terms: SIL Open Font License 1.1.** Full text: **`assets/fonts/OFL.txt`**.

That file was added in the same change as this one. OFL 1.1 §2 makes the licence
travel with the fonts —

> *"The above copyright notice and this license notice shall be included in all copies of one or more of the Font Software typefaces."*

— and until now ChromIQ shipped six OFL fonts with no copy of the licence
anywhere in the tree. The notice inside each font's `name` table names the
licence but is not the licence.

No GPL tension: the OFL preamble says the fonts *"can be bundled, embedded,
redistributed and/or sold with any software"*; only selling the fonts **by
themselves** is forbidden, which ChromIQ does not do.

---

## Vendored JavaScript — `assets/plotly-gl3d.min.js`

plotly.js 2.35.2, gl3d bundle, 1,695,217 bytes, md5
`f7471208ce4d82e9b4cca724d8aadbfe`. Used by the 3D gamut viewer. Its own header
reads *"Copyright 2012-2024, Plotly, Inc. … Licensed under the MIT license"* and
refers to a sidecar `plotly-gl3d.min.js.LICENSE.txt` that has never been present
in this repo. **Terms: MIT.** The permission notice MIT requires is reproduced
here in full, from <https://github.com/plotly/plotly.js/blob/v2.35.2/LICENSE>:

```
The MIT License (MIT)

Copyright (c) 2021 Plotly, Inc

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

The minified bundle also embeds several MIT/BSD-licensed dependencies whose
individual notices normally live in that missing sidecar. Regenerating the
bundle should bring `plotly-gl3d.min.js.LICENSE.txt` with it; see
[Still open](#still-open).

---

## Sounds — `assets/sounds/`

Documented in **`assets/sounds/CREDITS.md`**, which predates this file and is
the model for it. Everything is either synthesised by
`scripts/make_default_sounds.py` from seeded sources (so its provenance is the
source code) or CC0. One recorded file, `task-complete/applause.wav`, from
Wikimedia Commons / Freesound #277021 by *sandermotions*, CC0 1.0. **Terms: CC0
and ChromIQ's own — no attribution required, credited anyway.**

## Test image — `assets/test_images/`

Documented in **`assets/test_images/ATTRIBUTION.md`**, with the licence itself
shipped beside it as `PhotoDisc-Freeware-License.pdf`.
`photodisc-pdi-target.jpg` is the PhotoDisc / PDI colour target under the
**PhotoDisc Freeware License**: free to use, copy, modify and distribute
provided it is not sold, the embedded company logos are not altered, and the
licence travels with it.

**Note the "not sold" condition.** GPLv3 gives everyone who receives ChromIQ the
right to sell copies of *ChromIQ*; this file's own terms say it may not be sold.
Those coexist only on the reading that a bundled data file is a §5 aggregate
rather than part of the covered work — see
[Aggregation](#a-word-on-gplv3-and-aggregation). It is the only such condition
ChromIQ carries, and it was a deliberate choice, not an oversight.

## Scanner target recognition files — `data/scanner_targets/`

**Eight** `.cht` files, documented in **`data/scanner_targets/README.md`**, with
`LICENSE` beside it. Corrected geometry by Knut Georg Larsson (rectarg), derived
from the recognition files distributed with ArgyllCMS.

That derivation is no longer a description taken on trust: it was measured per
file on 2026-09-06 and the method and numbers are in that README under
**Provenance — measured, not assumed**. All eight carry ArgyllCMS's patch
geometry — `BOX_SHRINK` and the declared patch size are Argyll's in 8 of 8, and
three of the files sit at Argyll's absolute coordinates over 864, 288 and 528
patches.

**Licence: AGPLv3, decided 2026-09-06 by Basti.** ArgyllCMS's `ref/ReadMe.txt`
names all eight of these files as covered by `ref/License.txt`, which is the GNU
Affero GPL v3; unlike Argyll's `.icm` profiles they carry no public-domain
dedication. A work derived from an AGPLv3 work cannot be redistributed under the
plain GPLv3, so the folder's `LICENSE` — GPLv3 since its first commit — now
carries the same AGPLv3 text Argyll ships. Note this is **not** an aggregation
argument of the kind weighed below: nothing here needed one, because the folder
simply adopts its upstream's licence rather than asserting a different one.

**ChromIQ's own licence is untouched** and remains GPLv3. Only this folder is
AGPLv3; the files are data, read at run time and never linked. No code reads the
`LICENSE`, and no `.cht` coordinate changed, so the application behaves exactly
as before — the one visible effect is that `ensure_user_targets_dir` refreshes an
unmodified copy of the file in the user's `scanner-test-targets` folder.

## Argyll-derived helpers — `native/`

`native/argyll/LICENSE` (AGPLv3), `native/instlib/License.txt` (AGPLv3) and
`native/instlib/License2.txt` (GPLv2) are already in place and travel with the
code they cover.

---

## ChromIQ's own

Listed so the sweep is exhaustive and nobody has to re-derive it:

- **Icons and images** — `assets/*.svg`, `assets/folder/`, `assets/refresh/`,
  `assets/app_icon.*`, `assets/settings_v2.png`, `assets/clipborder.psd`,
  `assets/exported/`: drawn for ChromIQ (hand-written SVG, or Photoshop/Inkscape
  documents whose XMP names only the tool used). GPLv3 with the rest of the
  project.

  One qualification, from the sweep: **`assets/clipborder.psd` has the standard
  sRGB IEC61966-2.1 ICC profile embedded in it by Photoshop** (3,144 bytes, at
  offset 18,460), carrying the text tag *"Copyright (c) 1998 Hewlett-Packard
  Company"*. That is an embedded working-space profile in a design document —
  ordinary practice, and the HP sRGB profile is about the most widely
  redistributed ICC file in existence — so it is recorded rather than acted on.
  Worth knowing separately: the `.psd` is **referenced nowhere in the code**, and
  `ChromIQ.spec` ships the whole `assets` tree, so 588 KB of unused source
  document is in every build. Dropping it from the bundle (not from the repo —
  it is the source for the clip-border artwork) would remove both the weight and
  the stray copyright string. See [Still open](#still-open).
- **Help artwork** — `assets/help/workflow/*.svg` and
  `assets/help/example-workflow.pdf`: made for ChromIQ.
- **Charts** — `assets/charts/` (277 files) and
  `assets/verification/chromiq-verification-set-PROVISIONAL-r1.ti1`: patch sets
  generated by ArgyllCMS `targen` from recipes in this repo. Each carries the
  recipe that made it (`recipe.json`, or the `CHROMIQ_SET_RECIPE` keyword), so
  they are reproducible outputs of the workflow rather than copied data. The
  `assets/charts/knut/` recipes were contributed to this project by Knut Georg
  Larsson.
- **Reference data** — none. ChromIQ deliberately ships no characterization
  dataset (no FOGRA, no IT8.7/4, no ISO tables); the tolerance and aim work links
  to them instead. That decision is recorded in issue #182.

---

## A word on GPLv3 and aggregation

Two questions get run together, and only the first one can sink you.

**1. Do we have permission to copy the file at all?** That is plain copyright,
and no choice of licence for our own work can cure a missing permission. This is
where the Adobe profile failed: nobody established one.

**2. If we do, do the conditions attached conflict with GPLv3?** GPLv3 §10 says
*"You may not impose any further restrictions on the exercise of the rights
granted or affirmed under this License."* §5 says a *"compilation of a covered
work with other separate and independent works, which are not by their nature
extensions of the covered work, and which are not combined with it such as to
form a larger program, in or on a volume of a storage or distribution medium, is
called an 'aggregate'"*, and that *"inclusion of a covered work in an aggregate
does not cause this License to apply to the other parts of the aggregate."*

An ICC profile has a decent claim to be an aggregate: it is data, not code; it
is not linked; it is read at run time by a third-party CMM; ChromIQ runs without
it; any other CMYK profile would do. But the clause was drafted for compilations
*on a distribution medium*, and a file that lives inside the application bundle
and is opened by the program as part of its job is not the paradigm case. **This
is a defensible reading, not a settled one**, and it is worth saying plainly that
distributors who take the question seriously do not resolve it by arguing
aggregation — Debian and Fedora move non-free data into a separate non-free
archive, which a single signed `.app` cannot do.

The practical consequence: **prefer assets whose terms raise the question at
all.** Public domain raises none of it. That is why `assets/profiles/` is the
shape the rest of this file should grow towards.

---

## The Adobe profile (removed)

`assets/USWebCoatedSWOP.icc`, removed — ICC v2.1, `prtr`/CMYK/Lab, CMM `ADBE`, creator
`ADBE`, created 2000-07-26, 557,168 bytes, md5
`79d7e984ea3ac74eed7cc92bf6b22a0d`, ICC `desc` *"U.S. Web Coated (SWOP) v2"*,
ICC `cprt` *"Copyright 2000 Adobe Systems, Inc."*.

It was used for one thing: converting a CMYK or multi-channel TIFF to sRGB for
the on-screen chart preview — a path the app itself badges **"Approximate
colours — the ink values in the file are exact."**

### Adobe's terms, established from Adobe

Adobe publishes these profiles under **two different agreements**, distributed
with two different download packages that contain **byte-identical profiles**.
Which one governs depends on which package you took the file from.

**The end-user agreement**, §2, verbatim, from
<https://www.adobe.com/support/downloads/iccprofiles/icc_eula_win_end.html>
(live, and unchanged in Wayback captures from 2008 and 2012):

> Subject to the terms of this Agreement, Adobe hereby grants you the worldwide, non-exclusive, nontransferable, royalty-free license to use, reproduce, and publicly display the Software. Adobe also grants you the rights to distribute the Software only (a) as embedded within digital image files and (b) on a standalone basis. **No other distribution of the Software is allowed; including, without limitation, distribution of the Software when incorporated into or bundled with any application software.** You may not modify the Software.

That sentence describes exactly what ChromIQ was doing. Note also that the grant
separates the verbs: *use* and *reproduce* are granted broadly, *distribution* is
enumerated. ChromIQ's reading of the profile at run time was never in question;
shipping it in a release was.

**The bundling agreement**, §2, verbatim, from
<https://www.adobe.com/support/downloads/iccprofiles/icc_eula_win_dist.html>:

> Adobe also grants you the rights to distribute the Software: (a) on a standalone basis (b) as embedded within digital image files. (c) as embedded within hardware products that author digital images, where there is no End User access to the Software, and **(d) as bundled with your own application software, provided that you comply with all the distribution requirements in Section 3 below.** No other distribution of the Software is allowed. All individual profiles must be referenced by their ICC Profile description string. YOU MAY NOT MODIFY THE SOFTWARE.

Its Exhibit A names **"U.S. Web Coated (SWOP) v2"** among the fourteen CMYK
profiles it covers. Adobe still serves the bundler package today
(`https://download.adobe.com/pub/adobe/iccprofiles/win/AdobeICCProfilesCS4Win_bundler.zip`,
HTTP 200, 6,692,991 bytes), and the profile inside it is byte-identical to the
one in the end-user package and to the one this repo shipped.

**So: were we compliant? No.** Nothing in this repo or its history records the
file being taken under the bundling agreement, or the agreement being accepted.
Absent that, the terms that reach a copy of this file are the end-user ones, and
they prohibit bundling in application software in those words.

### Why we did not simply take the bundler licence instead

That route exists, and would have needed no change to a single byte. It was
rejected because its conditions do not sit inside a GPLv3 release:

- **§3 requires binding the recipient first** — *"If you distribute the Software
  on a standalone or bundled basis, you will do so by first obtaining the
  agreement of the end user under the terms of either the Adobe End User License
  Agreement ("Adobe EULA"), attached as Exhibit B, or your own license
  agreement…"*. ChromIQ is a download with no click-through. Worse, GPLv3 gives
  **every recipient** the right to redistribute; each of them would inherit that
  obligation without being told, which is the shape of a "further restriction"
  GPLv3 §10 forbids us from imposing.
- **§7 makes the grant terminable** — *"Upon any such termination, you must
  return to Adobe all full and partial copies of the Software in your possession
  or control."* GPLv3's grant to downstream is irrevocable. We cannot hand
  someone a permanent right to redistribute a file we might be required to
  recall.
- **"YOU MAY NOT MODIFY THE SOFTWARE"**, non-transferability, an indemnity
  running to Adobe, and exclusive California jurisdiction.

Under the aggregation reading above, those conditions attach to the file and not
to ChromIQ's own code — but the first two land on our distribution and on every
downstream redistributor regardless of how the aggregation question comes out.
Debian's practice is the corroborating datapoint: its `icc-profiles` package is
in `non-free` and ships **no Adobe profiles at all**, not even there, where the
only bar is whether Debian may redistribute. It ships Idealliance's
`SWOP2006_Coated3v2.icc` instead.

### What replaced it, and what that cost

`assets/profiles/cmyk.icm`, ArgyllCMS's public-domain CMYK reference profile —
because public domain removes the question instead of answering it. Measured over
a 6⁴ CMYK grid converted to sRGB and compared in CIELab, the replacement sits a
mean **5.2 ΔE76** (median 4.9, p95 11.0) from the Adobe profile, inside a preview
the app already calls approximate. Deleting the profile outright and falling back
to the naive subtractive conversion would have cost **16.9 ΔE76** mean, p95 47.0,
and painted 100 % cyan as `#00FFFF`.

Idealliance's `SWOP2006_Coated3v2.icc` (ICC registry, *"may be used, embedded,
exchanged, and shared without restriction. It may not be altered, or sold without
written permission of IDEAlliance"*) was the other serious candidate and would
have been a closer colorimetric match to the file being replaced. It was not
chosen because *"may not be sold"* re-opens the aggregation argument for no gain
in a preview, where 5 ΔE is invisible — and because the public-domain route was
already the house pattern, used four times over in the same folder.

---

## Still open

Two items this sweep turned up that are **not** for this assistant to decide.
(A third — the scanner targets' licence — was decided on 2026-09-06 and is
recorded above under **Scanner target recognition files**.)

1. **`assets/plotly-gl3d.min.js.LICENSE.txt` is missing.** The bundle's own
   header points at it. The MIT notice above covers plotly.js itself; the
   individual notices for the dependencies webpack folded in do not travel with
   the file today. Cheapest fix: regenerate the bundle and commit the sidecar
   webpack emits beside it.
2. **`assets/clipborder.psd` ships in every build and nothing uses it.** 588 KB
   of Photoshop source, referenced by no code, carried in because `ChromIQ.spec`
   bundles `assets` wholesale — and it brings an embedded HP sRGB profile's
   copyright string with it. Excluding it (and anything else under `assets/` that
   is source rather than runtime data) from the spec is a packaging decision, not
   a licensing one, so it is left here rather than made.
