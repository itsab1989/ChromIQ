# Amendment to §I.9 — where a measurement may be imported, and working in place

**STATUS: PROPOSED — awaiting Sebastian's approval.** Nothing in §3 below is
built until it is approved. §1 and §2 record decisions Basti has already made
and the specification text they need.

`docs/design/unified_measurement_management.md` §I.9 governs measurement
import. It names the doors a measurement may come in through, and it says what
an import's new run carries. Two of Basti's rulings (2026-09-01) do not fit the
text as written, so the text has to change or the rulings do. This document
puts the change where it can be reviewed instead of discovering it in the code
later.

---

## §1 · Check & Refine becomes an import door

**Basti's ruling:** *"check refine shall be an import door — that is the reason
we are building this. it already was and i want it improved."*

§I.9 names the import doors as Measure and Build Profile. Check & Refine is not
listed — but it has been importing all along, and worse than the listed doors
do: `ui/tabs/tab_check_refine.py:1200` sends the file to `resolve_ti3`, which
for a file outside the working folder **creates a project without asking**.

So this amendment does not add a door. It describes one that exists and brings
it up to the standard of the other two: the same project picker, the same run
picker, the same validation, in Check & Refine's own accent.

**Proposed text for §I.9:** the doors are Measure, Build Profile and Check &
Refine. All three ask the same question, in the same window, and file through
the same helper.

---

## §2 · Working in place, and where the files go

**Basti's rulings:** check in place is approved; build in place is wanted, *"so
the user is not forced into chromiq for this"*; and **the resulting files are
saved where the measurement file is.**

### §2.1 What "in place" means

The measurement is neither moved nor copied. ChromIQ reads it where the person
found it and writes what it produces into **the folder that measurement is in**:
the check report beside a checked `.ti3`, the ICC profile beside a built one.

### §2.2 What it costs, stated so nobody meets it as a surprise

* There is **no run**, so there is no run history, no `project.json` entry and
  no place for the other artefacts a run holds. The window says so before the
  person chooses.
* ChromIQ writes into a folder it does not own. A read-only folder, a volume
  that goes away mid-write, or a name that is already taken has to be handled
  where today the app can assume its own folder.
* **Nothing the user created is deleted, only archived** applies unchanged. An
  output whose name is already taken beside their file is numbered, the way
  `Quality_Check_N` and `Refine_Strips_N` already are. No `old/` folder is
  created in somebody's own directory.

### §2.3 The conflict this amendment exists to resolve

**Build Profile is required by confirmed text to have a store.** A build writes
`runs/runN/meta.json`, and `store_for_target` returns `None` when there is no
project. §6c says profcheck checks *"the data it was built from"*, which
assumes the data has a place. Building in place contradicts that.

Basti has ruled that he wants it. **This is the paragraph Sebastian is being
asked to approve**, because it is his section:

> A profile may be built from a measurement that is not in a project. It then
> has no run, no `meta.json` and no history: the ICC and the build log are
> written beside the measurement, numbered if those names are taken, and the
> window says plainly that this build is not recorded in a project. Everything
> a run would have given it — the chart it was built from, the report, the
> ability to rebuild it later — is not available, and the person is told that
> before they choose.

### §2.4 Filing stays the primary answer

In every window the in-place answer sits **after** the filing answers, never
first and never the default. The result window carries a **"Keep this in a
project"** button, so choosing in place is a deferral rather than a fork.

---

## §3 · What an import's new run carries

§I.9 says a run made for an import copies **the chart only**. For Check &
Refine that leaves the run with nothing to check, because a profile check needs
a profile.

**Basti's ruling (2026-09-01):** do **not** copy the `profile` group. Carry the
sibling `.icc` or `.icm` when one sits beside the measurement, which is the
common case, and otherwise say so inline beside the browse button that is
already there.

So §I.9's chart-only clause **stands unchanged**. The sibling profile is not a
group copy; it travels with the measurement the person picked, exactly as
`_copy_ti3_only` already carries it.

---

## ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

Open for Sebastian:

1. **§1** — Check & Refine named as a door.
2. **§2.3** — a profile built with no run at all. This is the one that
   contradicts confirmed text; the rest describe or narrow.
3. **§2.4** — whether "Keep this in a project" on the result window is enough
   to keep filing the normal path, or whether in place should be harder to
   reach than one button.
