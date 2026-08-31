# The three paths that still destroy a whole project

STATUS: in-progress — analysis for challenge, no code written

Basti, 2026-08-31: fix these before building the import.

## What exists

`core/trash.py` already solves this, and its docstring records why, from a
measured incident on 2026-08-28 through the real Delete button:

> `rmtree` RAISED → the app said "Nothing was changed."
> files before 6, files now 1 — `project.json` still there: **False**

`shutil.rmtree` is not atomic: it removes what it can reach and raises at the
end, so one unwritable sub-folder leaves a project half-destroyed — and
`project.json` among the casualties means the survivors cannot be opened by
ChromIQ at all. **Basti ruled on 2026-08-28 that deleting moves to the Trash.**

`move_to_trash` is already the shipped behaviour in five places:
`ui/measurement_target_bar.py:2007`, `core/run_delete.py:629/649/743`,
`core/file_manager.py:2564`.

## The three that were missed

All identical in shape, all UI-reachable, all on import routes:

| Site | Route |
|---|---|
| `ui/txt_loader.py:333` | i1Profiler `.txt` import → "Overwrite existing folder" |
| `ui/ti2_loader.py:1324` | `.ti2` chart import |
| `ui/ti2_loader.py:1395` | bare `.ti3` import — **the route the new import feature touches** |

```python
dest = working_dir / new_name
if overwrite and dest.exists():
    shutil.rmtree(dest)          # ← destroys a whole project
proj = Project.create(dest, new_name)
```

Two faults, not one:

1. **It destroys instead of archiving**, against the 2026-08-28 ruling and
   against the standing rule that user work is archived, never deleted.
2. **The word is wrong too.** `txt_loader`'s button says "Overwrite existing
   folder" while `ti2_loader`'s equivalent says "Replace" and *archives* to
   `old/`. Same act, opposite consequence, decided by which file type the
   person happened to load.

## The fix, to be challenged

Replace the `rmtree` with `move_to_trash`, and treat `False` as **nothing
happened**: say so, abort the import, and never fall back to destroying — the
module's docstring names that fallback as the exact behaviour it exists to
remove.

## Numbered open questions
1. **Trash, or `old/`?** `ti2_loader`'s other path archives to `old/<timestamp>/`
   *inside the project*. The bar's Delete moves to the system Trash. Which is
   right when a whole project is being replaced by an import? They are not the
   same promise: `old/` keeps it inside the project (and inside a folder about
   to be replaced — is it then destroyed with it?), the Trash takes it out.
2. What must the button SAY once it no longer overwrites? "Overwrite existing
   folder" would be a lie.
3. On `move_to_trash` returning False (read-only volume, a share with no
   trash), the import must abort — what does the user see, and is there any
   route where aborting leaves half-written state?
4. Is `Project.create` on a path whose folder was just trashed safe on every
   platform (does the Trash move complete before the create)?
5. Are these three genuinely the last ones? A previous count said three, with
   `core/file_manager.py:2121` excluded as a rollback — confirm.

---

## Challenge

STATUS: in progress — adversarial review, no source changed.

Proof: `~/Desktop/knut-rmtree/` (INDEX.md).
Settings sandboxed to a scratch `.ini` for every probe; the owner's
`custom_output_path` was **unset** before this work started and is checked
by VALUE at the end.

Skeleton (filled in below as each is measured):

- C1  Trash or `old/` — the design question
- C2  Is `move_to_trash` safe here (contract, failures, abort)
- C3  Race / ordering / case-folding
- C4  Wording, and §M
- C5  The full destructive-call inventory
- C6  What happens when the project being replaced is OPEN
- C7  Tests that pin the destructive behaviour
- C8  Faults found that the proposed fix does NOT address
- Verdict, plan, open questions

---

### C0. The headline

**Agree with the diagnosis, DISAGREE with the fix.** The three sites must stop
destroying, but the replacement is **not** the Trash — it is the project's own
`old/<timestamp>/`, because that is what the model already says this exact act
does, and what two other implementations of it already do. And the swap on its
own is not enough: measurement found **four further faults on the same three
routes** that a straight `rmtree → move_to_trash` edit leaves in place, one of
which destroys the very file the person is importing.

---

### C1. Trash, or `old/`? — **`old/`. The model already decided it.**

The 2026-08-28 Trash ruling is about **Delete** — a button whose whole purpose
is to get rid of something. An import that replaces a project is not a delete,
and the app already draws that line in two places:

| Act | Where | What happens |
|---|---|---|
| Delete a project | `core/file_manager.py:2564` (`delete_project_folder`) | Trash |
| Delete a run | `core/run_delete.py:629/649/743` | Trash |
| **Replace a project by name** (Create Chart) | `ui/tabs/tab_chart.py:9141` `_replace_whole_project` | `old/<timestamp>/` |
| **Replace a project by name** (Copy the whole project in ▸ Replace) | `workflow/chart_import.py:163` | `old/<timestamp>/` |
| **Replace a project by name** (the three import routes) | `ui/txt_loader.py:333`, `ui/ti2_loader.py:1324/1395` | **destroyed** |

`tab_chart.py:9143-9146` says why, in the code itself:

> *"Not a delete: the same operation "Copy the whole project in ▸ Replace"
> already performs (`workflow/chart_import._archive_project_contents`), so one
> word means one thing in both places."*

And the binding specification says it outright.
`docs/design/unified_measurement_management.md`:

- **§S4.7** (line 2159) — a typed name that resolves to a project that exists
  and holds something → *"Replace it → M-PROJECT-REPLACE-CONFIRM → **archive
  the whole project into its `old/`** and start a fresh one"*.
- **T2.6** (line 2219) — *"every path that archives | the original is in
  `old/{date}/` and readable; **nothing is ever deleted**"*.
- **M-PROJECT-EXISTS** (line 1582), already written and awaiting review:
  *"Replace it: everything the project holds now is moved into its own "old"
  folder, with today's date, and a new, empty project of the same name is
  started. **Nothing is deleted**, and ChromIQ asks you to confirm before it
  does it."*
- **M-PROJECT-REPLACE-CONFIRM** (line 1640): *"That "old" folder **stays inside
  the project**, so you can open it at any time and take anything back out of
  it."*
- `docs/design/calibration_run_type.md:108` names the rule: *#130 §2a/§4,
  **"archive, never delete"***.

So `move_to_trash` at these three sites would not end the inconsistency the
report complains about — it would **rotate** it: three import routes throwing
work out of the project while the two "Replace" routes keep it inside, and the
model saying the second thing.

#### The trap in the brief, measured

*"if `old/` sits inside the folder being replaced, archiving there and then
replacing the folder may destroy the archive too"* — **it does not, provided the
`rmtree` is removed rather than kept.** `Project.create` is
`mkdir(parents=True, exist_ok=True)` + `save_manifest` + `write_readme`
(`core/file_manager.py:1590-1602`); it removes nothing. Measured
(`p6_archive_option.py`, case 1):

```
archived into: Canon/old/2026-08-31_090306
old/ still there: True
archived measurement recoverable: True | archived profile: True | archived cal: True
fresh run1 is empty: ['meta.json']
peek: runs=(run1) chart=False measurement=False profile=False calibration=False
runs/ children: ['run1']            ← old/<ts>/ is not mistaken for a run
```

The trap is real for exactly one implementation: **archive → `rmtree(dest)` →
`Project.create`**. That order must not be written. The correct order is
**archive → `Project.create` on the SAME folder**, which is what
`copy_whole_project` already does (`workflow/chart_import.py:163-172`).

#### What `old/` costs, honestly

1. It does not free disk space, and the replaced project's page TIFFs can be
   large. Neither does the Trash until it is emptied — `core/trash.py:29-31`
   says so — but the Trash at least has a familiar "empty me" control and
   `old/` has none. Nothing in the app ever prunes an `old/` archive.
2. An archive at `old/<ts>/` is a **fully recognised project**. Measured
   (`p9_archive_sideeffects.py`): `_project_root_for` and
   `chart_import.is_full_project` both return the archive folder for a `.ti2`
   inside it, and `peek_project` reports `exists=True, runs=['run1'],
   measurement=True`. That is what makes recovery possible — and it also means
   loading a chart out of an archive silently opens the archive as the project.
   Pre-existing behaviour of the `old/` precedent, not new.
3. A later project rename rewrites the archive's file stems too. Measured:
   archive `run1` held `Canon.ti3` before `Project.rename("Epson")` and
   `Epson.ti3` after (`core/file_manager.py:1885`, the rename `rglob` does not
   skip `old/`). Pre-existing; worth a separate issue, not this one.

---

### C2. Is `move_to_trash` safe here? — safe, but it answers the wrong question

Measured on this machine, Qt 6.11.0 / PyQt 6.11.0
(`p2_trash_contract.py`, `p3_volumes.py`):

| case | result |
|---|---|
| plain project in `$TMPDIR` | `ok=True`, `~/.Trash/Plain`, 6 files recovered, `project.json` present |
| project with a **read-only `reports/`** (the 2026-08-28 incident) | `ok=True`, all 6 files recovered, `project.json` present |
| project whose **parent folder** is read-only | `ok=False`, source untouched, plain reason |
| project on a second HFS+ volume | `ok=True`, `/Volumes/KnutRW/.Trashes/502/VolProj` |
| project on an **exFAT** volume | `ok=True`, `/Volumes/KNUTEX/.Trashes/502/VolProj` |
| project on a **read-only mounted volume** | `ok=False`, source untouched (`rmtree` there raised `OSError 30` and left all 4 files) |
| same name trashed twice | two distinct destinations (`SameName`, `SameName 08-59-49-943`) |

So the contract in `core/trash.py:23-27` holds: `False` means nothing happened.
It is a sound primitive. It is simply not the primitive this act calls for.

**`_archive_project_contents` survives the same cases**
(`p6_archive_option.py`, cases 2 and 3):

- read-only `reports/` inside the run: **archive succeeded**, 8 of 8 files
  recoverable including the read-only report. A top-level `shutil.move` is a
  rename; an unwritable grandchild cannot defeat it, exactly as for the Trash.
- read-only project **root**: raises `OSError("… is not writable")` **before
  moving anything** (`workflow/chart_import.py:196`), all 8 files still there,
  `project.json` intact — and the caller already has a window for it,
  **M-PROJECT-REPLACE-FAILED** (`ui/tabs/tab_chart.py:9173`).

**Does aborting leave anything half-written?** On all three routes the
destructive call is the first statement that touches the destination and
`Project.create` is the next one (`ui/txt_loader.py:331-337`,
`ui/ti2_loader.py:1322-1327`, `ui/ti2_loader.py:1392-1398`), so an abort placed
*before* `Project.create` writes nothing. **But abort where?** — see C8/F2: the
three `_copy_*` functions have no parent widget and cannot say anything, and
today a raise from them is swallowed in silence.

---

### C3. Race, ordering, case-folding

- **Ordering.** No race. `QFile.moveToTrash` is a synchronous rename;
  `move_to_trash` additionally refuses to report success while the path still
  exists (`core/trash.py:85-94`). Measured: `Project.create` on the just-trashed
  path completed in **1.1 ms** and the new tree held **no leftovers** of the old
  one (`p2_trash_contract.py`, case f). The same is true of the archive: the
  folder never stops existing at all.
- **Case folding — a real hole, in the guard rather than in the delete.** On
  APFS `Path.resolve()` does **not** fold case. Measured:
  `(w/'canon').exists() → True` while `(w/'canon').resolve() == (w/'Canon').resolve() → **False**`.
  `move_to_trash(w/'canon')` moved the folder actually named `Canon` (the Trash
  entry is named `Canon`), and `Project.create(w/'canon')` then produced a
  folder named `canon` — so the person's project `Canon` disappears and a
  differently-cased one takes its place. Identical under today's `rmtree`, so
  not a regression; but the app already owns the right predicate,
  `core.file_manager.same_dir`, which answers **True** for that pair
  (`p8_ti2_self.py`). Both loaders use raw `.resolve() ==` instead
  (`ui/txt_loader.py:217`, `ui/ti2_loader.py:1205`).
- **Same-second collision in the `old/` archive — a genuine new hazard, and it
  is in the code we would be adopting.** `_archive_project_contents` names the
  folder `old/%Y-%m-%d_%H%M%S` (`workflow/chart_import.py:200`) and
  `mkdir(exist_ok=True)`. Two replaces inside one second share it, and
  `shutil.move` then **overwrites top-level files** and **nests directories**.
  Measured (`p7_same_second.py`):

```
a1 == a2 : True 2026-08-31_090324
   a-file-of-mine.txt      = SECOND loose file      ← the FIRST one is gone
   runs/run1/Canon.ti3     = FIRST measurement
   runs/runs/run1/Canon.ti3 = SECOND measurement    ← nested
FIRST loose file recoverable anywhere?  []  (only the SECOND survives)
```

  This must be fixed in the same change: the timestamped folder has to be
  uniquified (`…_2`, `…_3`) rather than reused. It already affects Create Chart's
  Replace and "Copy the whole project in ▸ Replace" today.

---

### C6. Replacing the project that is OPEN — driven on screen

Real `MainWindow`, real tabs, real dialogs; only the clicks are automated so a
modal `.exec()` does not sit waiting for a person. Settings sandboxed, working
folder a temp tree (`drive_open_project.py`, `drive_stale_manifest.py`;
screenshots `01`–`05` in the proof folder).

**Run 1** — `Canon` open, holding a chart, a measurement, a profile and a
report. Load Measurement ▸ an outside `.txt` ▸ type `Canon`:

```
WINDOW 1: 'Choose a name for the profile'
   line under the box: '"Canon" already exists. Click "Overwrite existing folder" to replace it.'
   buttons: 'Overwrite existing folder', 'Cancel'
WINDOW 2: 'This will permanently delete:\n\n    …/Canon\n\nand replace it with the imported measurement. Continue?'
   buttons: '&Yes', '&No'

=== AFTER ===
Canon.ti3 there: False     Canon.icc there: False     Canon.ti2 there: False
old/ there: False          in the Trash: []
```

Two clicks, and the open project's chart, measurement, profile and report are
gone with no copy anywhere. Note what the second window does **not** say: not
the project's name, not that it is open, not one word about what is inside it.
Compare M-PROJECT-EXISTS, which lists every run and what each holds.

**Run 2** — the same, on a `Canon` with **four** runs. The app's `FileManager`
never drops its cached `Project`:

```
BEFORE  runs on disk: ['run1','run2','run3','run4']   manifest current_run: 'run4'
AFTER   runs on DISK: ['run1']                        manifest on disk: runs ['run1']
the app is STILL holding the same Project object: True
what the app believes its runs are: ['run1','run2','run3','run4']
after one save_manifest() from that cached object, project.json says:
   {"current_run":"run4","runs":["run1","run2","run3","run4"]}
   runs listed that do NOT exist on disk: ['run2','run3','run4']
```

So after the wipe the app is pointing at a run that no longer exists, and the
next ordinary manifest write **puts the stale run list back on disk**.
`tab_chart._replace_whole_project` calls `self._file_mgr.forget_cached_project()`
for exactly this reason (`ui/tabs/tab_chart.py:9166`); none of the three import
sites does. **Any** fix here — Trash or `old/` — must call it too.

---

### C7. Tests that pin the destructive behaviour

One test names it, and it does **not** go red on a correct fix:

`tests/test_txt_loader.py:35` `test_copy_txt_overwrite_replaces_existing`

```python
assert not (stale / "stale.txt").exists(), "overwrite must wipe the old folder"
```

It asserts only that the stale file is **not at its old path**, which is equally
true after a Trash move and after an archive to `old/<ts>/`. So it pins the
*word* and not the *behaviour*: it would stay green through the fix, and it
would also stay green through a regression back to `rmtree`. It should be
rewritten to assert the archive is readable, not merely that the file moved.

No other test in `tests/` asserts destruction on these routes — `grep -rln
"_copy_txt|_copy_ti3_only|_copy_files|Overwrite existing folder|overwrite=True"
tests` returns only `tests/test_txt_loader.py` and `tests/test_ti2_loader.py`.
Baseline: both files green, **68 passed in 0.27 s**.

---

### C8. Four faults on the same three routes that the proposed fix does not touch

#### F1 — the import destroys the file it is importing

`_is_self_collision` compares the destination to the loaded file's **immediate
parent only** (`ui/txt_loader.py:217`, `ui/ti2_loader.py:1205`). A ChromIQ
project keeps its measurement at `<project>/runs/run1/<name>.txt`, so the guard
is asked whether `<work>/Canon` equals `<work>/Canon/runs/run1` — it does not,
the guard stays silent, the Overwrite button appears, and the "outside" copy
path is run against a source **inside** the folder it is about to remove.

Reachable: Load Measurement on a `.txt` already in the working folder ▸
*"Use as base for a new profile"* ▸ type the project's own name
(`ui/txt_loader.py:44` → `:65` → `:137-142`). Same shape for a `.ti2` via
`_handle_inside_current` ▸ *"Use as base for a new profile"*
(`ui/ti2_loader.py:723-727` → `:632-637`).

Measured, `.txt` (`p1_self_collision.py`):

```
source .txt lives at: Canon/runs/run1/Canon.txt
files before: 8
_copy_txt RAISED: FileNotFoundError … 'Canon/runs/run1/Canon.txt'
files after: 5    source .txt still there: False
original Canon.ti3 still there: False    original Canon.icc still there: False
```

Measured, `.ti2` (`p8_ti2_self.py`): `files before=7 after=3`; chart,
measurement, profile and page image all `False`.

The person loses the project **and** the file they were importing, and the
import cannot complete because its own source has been deleted. Neither
`move_to_trash` nor an `old/` archive fixes this by itself — both would move the
source away and `shutil.copy2` would still fail. The fix is three-part: use
`core.file_manager.same_dir` instead of `.resolve() ==`, test **containment**
(`dest in source.parents`) and not just equality, and copy the source to a temp
file *before* anything moves.

#### F2 — the failure is silent, and the app carries on

There is no `try` anywhere on these routes.
`ui/tabs/tab_profile.py:4298` calls `resolve_txt` bare. A `PermissionError` or
`FileNotFoundError` from `_copy_txt` therefore reaches PyQt's slot handler.
Measured, PyQt 6.11.0: with the **default** excepthook the process aborts
(exit **134**); with the hook `main.py:21-29` installs — log a `CRITICAL` line,
call `sys.__excepthook__`, return — the process **survives** and shows the user
nothing at all (`p5_slot_abort.py`, `p5b.py`).

So today's worst case is: project half-destroyed, no window, no log panel entry,
the app apparently idle. That is the 2026-08-28 incident's *"the app said
'Nothing was changed'"* with the message removed. The proposed fix says "treat
`False` as nothing happened: say so" — **there is nowhere in `_copy_txt` /
`_copy_files` / `_copy_ti3_only` to say it from**; they take no parent widget.
The decision and the window must move up into the dialog layer.

#### F3 — the incident itself reproduces on the import route

The same read-only `reports/` folder, the same fingerprint as
`core/trash.py:8-9` (`p4_incident_on_import.py`):

```
files before: 6
import RAISED: PermissionError [Errno 13] … 'Canon/runs/run1/reports'
files now: 1
project.json still there: False
Canon.ti3 still there: False   Canon.icc still there: False
peek_project sees: exists=False
```

`peek_project` reading `exists=False` means the survivors cannot be opened by
ChromIQ at all — the exact loss the Trash module was written to end, still
shipping on three routes.

#### F4 — the stale cached `Project` (see C6)

None of the three calls `forget_cached_project()`.

---

### C4. The wording, and where it has to go first

#### Does it need §M-PROPOSED? Yes — and the test will not catch it

CLAUDE.md: new user-facing message text goes to §M-PROPOSED and is not written
into a tab until approved. But `tests/test_message_catalogue.py` will **not**
fail on these windows: link 3 is an allow-list, `WINDOW_SOURCES`, and the file
says so itself — *"a window nobody added to it can invent its own wording and
this file stays green. That is exactly how new text reached the overlay-failure
window in #155."* The import dialogs are not in that list. So this is
discipline, not enforcement, and **the change must add the new render functions
to `WINDOW_SOURCES`** or it repeats #155.

#### Reuse before inventing

Three messages already sit in §M-PROPOSED for the *same act* — a typed name that
already names a project on disk (`workflow/measurement_messages.py:1152/1248/1259`,
`docs/design/unified_measurement_management.md:1582/1640` and §S4.7):

- **M-PROJECT-EXISTS** — what is there, and the four choices
- **M-PROJECT-REPLACE-CONFIRM** — the second look before a project is emptied
- **M-PROJECT-REPLACE-FAILED** — the archive could not be made; nothing changed

**M-PROJECT-REPLACE-FAILED can be used verbatim** on the import routes; its body
already reads *"before starting a fresh one of the same name"*. The other two are
written for Create Chart (*"building now would carry on inside that project"*,
*"the new chart is made in the run named in the box below"*) and need an import
wording. Whether that is a variant of the existing IDs or two new ones is
**OQ-3** below.

#### Proposed text (draft — for §M-PROPOSED, not for a tab)

**M-IMPORT-PROJECT-EXISTS** — the line under the name box, replacing
`ui/txt_loader.py:240` and `ui/ti2_loader.py:1229`:

> There is already a project called "{name}". Choose a different name, or
> Replace it — everything it holds now is moved into its own "old" folder first,
> so nothing is lost.

Button, replacing `Overwrite existing folder`
(`ui/txt_loader.py:196`, `ui/ti2_loader.py:1184`):

> **Replace it**

— the same word "Replace" the other two routes already use
(`ui/ti2_loader.py:693/870`), which is the point.

**M-IMPORT-REPLACE-CONFIRM** — the second look, replacing the
`QMessageBox.warning` at `ui/txt_loader.py:287` and `ui/ti2_loader.py:1276`:

> **Title:** Replace "{name}" with what you are importing?
>
> ChromIQ found a project of that name here:
>
> {folder}
>
> It has {runs}, and {chosen} holds:
>
> {holds}
>
> Everything it holds now is moved into its own "old" folder, with today's date
> on it, and a new and completely empty project of the same name is started in
> the same place. Your imported {what} is placed in its first run.
>
> Nothing is deleted. That "old" folder stays inside the project, so you can
> open it at any time and take anything back out of it: the charts, the
> measurements, the profiles, all of it.
>
> If you did not mean to touch this project, go back and type a different name
> instead — that leaves everything exactly as it is.
>
> **Buttons:** Replace it · Go back  (default: **Go back**)

`{runs}` and `{holds}` are `measurement_messages.runs_phrase()` /
`chosen_phrase()` and the `_HOLDS_*` fragments already in the catalogue
(`workflow/measurement_messages.py:1163-1205`) — count-aware, "one run" /
"{n} runs", never "(s)". `{what}` is "measurement" for the `.txt` and bare
`.ti3` routes, "chart" for the `.ti2` route.

**After it has happened**, the person is told where the old project went — the
one thing today's window never says. A line in the tab's log is not enough
(that is the mistake `ui/tabs/tab_chart.py:9151-9154` records); this belongs in
the window that confirms the import:

> Your earlier "{name}" project is kept here: {folder}/old/{date}

**M-PROJECT-REPLACE-FAILED** — reused unchanged for the abort path, rendered
with `folder=` the project and `reason=` the `OSError`
(`workflow/measurement_messages.py:1259`). It already says *"Nothing has been
changed. Anything that had already been moved has been put back, and no new
chart has been made"* — the last clause wants "chart" → "{what}" for the import
routes, which is **OQ-4**.

**The self-collision refusals** (`ui/txt_loader.py:262/276`,
`ui/ti2_loader.py:1251/1266`) currently say *"You're trying to overwrite the
measurement's own folder"*. With F1 fixed the guard is about containment, not
equality, so:

> That name is the project this measurement is already in, so importing it
> there would replace the file with itself. Pick a different name — or close
> this and choose "Continue", which uses the measurement where it is.

Every string above goes through `tr()`, and `python scripts/i18n_extract.py
--missing de` plus the twelve other catalogues must be filled in the same
commit (CLAUDE.md).

---

### C5. The full destructive-call inventory

Swept `core/`, `ui/`, `workflow/`, `main.py` for `shutil.rmtree`, `unlink`,
`os.remove/unlink/rmdir`, `os.replace`/`Path.replace`, `shutil.move` onto a
possibly-existing path, `copytree(dirs_exist_ok=True)`, and in-place writes over
a real `.ti3`/`.ti2`. `tests/` and `.venv/` excluded; `scripts/` listed apart.

**Verdict on the previous count: the "three" is right for the *shape* named in
the report and WRONG as a statement that these are the last hazards. Five more
sites can destroy user work, and `core/file_manager.py:2121` must NOT be
excluded — the exclusion is refuted below, by measurement.**

#### The hazards

| file:line | call | what it destroys | verdict |
|---|---|---|---|
| `ui/txt_loader.py:333` | `rmtree(dest)` | a whole project, `old/` archives included | **HAZARD — the subject of this report** |
| `ui/ti2_loader.py:1324` | `rmtree(dest)` | same | **HAZARD** |
| `ui/ti2_loader.py:1395` | `rmtree(dest)` | same | **HAZARD** |
| `core/file_manager.py:2121` | `rmtree(run.dir, ignore_errors=True)` (`_discard_run`) | a whole run | **HAZARD — exclusion REFUTED, measured** |
| `core/file_manager.py:701` | `p.unlink()` (`Calibration.reset`) | the calibration's `.engine-partial` | **HAZARD — measured** |
| `workflow/verify_chart_snapshot.py:463/663` | `rmtree(stash)` in `finally` | the displaced live `.ti2` + pages | **NEEDS-JUDGEMENT** |
| `ui/tabs/tab_chart.py:15266/15271` | unguarded `shutil.move`, then `rmtree(bak)` in `finally` | the only copy of the profiling chart during verify-chart generation | **NEEDS-JUDGEMENT** |
| `workflow/reference_convert.py:197/238/246`, `ui/dialogs/scanin_dialog.py:3547`, `workflow/ti2_relayout.py:1235/1259` | `write_text` over a live `.ti3`/`.ti2` | the file, on a crash mid-write | NEEDS-JUDGEMENT — non-atomic; `core/file_manager.py:251` already has the atomic helper |
| `workflow/chart_import.py:171` | `copytree(dirs_exist_ok=True)` | same-named files in a dest emptied except `old/` | NEEDS-JUDGEMENT |
| `ui/tabs/tab_measure.py:9797` | `shutil.move` onto a chosen `verifications/<date>/` | an existing dated verification | NEEDS-JUDGEMENT (comment at `:9788` says intended) |
| `workflow/chart_import.py:70` | `t.unlink(missing_ok)` | run-root page TIFFs | SAFE **only** because the sole caller (`ui/ti2_loader.py:699`) passes `replace=True`; a `replace=False` caller would destroy |

**`core/file_manager.py:2121` — the exclusion is wrong.** `_discard_run`'s
docstring calls it "only for undoing a failed `duplicate_run`", and
`duplicate_run` gets its folder from `new_run()` → `_next_run_index()`
(`:2129-2135`), which reads **only `self._manifest.runs`** and never the disk,
then `ensure_dir()` (`mkdir(exist_ok=True)`, `:1121`). `Project.load` never
reconciles the manifest against the run folders — `peek_project` says so at
`:2753`: *"EVERY run on disk, not only the ones the manifest lists — a folder
the manifest has lost still holds somebody's work."* Measured
(`p10_verify_agent_claims.py`, A) on a manifest that has lost `run2` while the
folder is still there:

```
manifest runs: ['run1']   on disk: ['run1','run2']
new_run() returned: run2  ->  that folder ALREADY held: ['X.icc','X.ti3','meta.json']
after _discard_run: folder still there: False   ti3: False   in the Trash: []
```

A stranger's measurement and profile, destroyed with nothing in the Trash. And
a manifest can lose a run: a hand-edited `project.json`, a half-merged sync, a
project restored from the Trash after `delete_run` renumbered. Not a rollback —
a `rmtree` on user work that `run_delete.py`'s 2026-08-28 conversion missed
alongside the three in this report.

**`core/file_manager.py:701` — a calibration's interrupted measurement.**
`Calibration.reset` archives only `RESULT_SUFFIXES = ('.ti3','.cal','.icc','.icm')`
(`:615`) and then unlinks every remaining live file. The engine's partial backup
is `<name>.ti3.engine-partial` (`workflow/measure_manager.py:731`), whose
`Path.suffix` is `.engine-partial`. `Run.reset_chart_artefacts` names
`self.partial_ti3` in its archive list explicitly (`:1298`) *"so it can never be
forgotten"*; `Calibration.reset` does not. Measured
(`p10_verify_agent_claims.py`, B):

```
before: ['Y-cal.ti1', 'Y-cal.ti3', 'Y-cal.ti3.engine-partial']
archived into cal/old/: ['Y-cal.ti3']
the .engine-partial survived anywhere: []
```

Real ink on real paper, unrecoverable, on Generate-a-new-calibration-chart.

#### Confirmed safe (abbreviated)

- **`core/run_delete.py`** — no `rmtree`, no `unlink`. All three deletes
  (`:629/:649/:743`) are `move_to_trash`, each treating `ok=False` as "nothing
  happened" and raising `DeleteFailed`. This is the model the rest should follow.
- **The chart stash** (`core/file_manager.py:1201/1236/1245`) — `:1201` fires
  only behind a proven-empty check (`:1196`); `:1236` only clears a dead build's
  leftover to make room for the original being restored; `:1245` runs after
  restore-or-supersede and writes `STASH_SUPERSEDED` on failure so `Project.load`
  cannot restore a stale copy. Stash dirs are minted `exist_ok=False`.
- **`:826` `clear_reads`** — safe only because `reset_chart_artefacts` archives
  `reads/` at `:1317` under the identical `not keep_results` condition. The
  method itself has no guard; a future caller destroys hand-taken readings.
- **`:706` / `:1329`** (`exports/`, `cache/`) — regenerable by `write_sidecars`;
  `cache/` is "always safe to delete" per CLAUDE.md.
- **`workflow/verify_chart_snapshot.py:314`** — empties the snapshot slot only
  once there is a new chart to put in it (`if not sources: return None`, `:307`).
- **`Run.archive_to_old` / `Calibration.archive_to_old`** — pure-additive, both
  resolve collisions by suffixing (`:1082`, `:653`). Note `Calibration` has the
  same-second guard (`:647-656`) that `chart_import._archive_project_contents`
  lacks — see C3.
- **`core/file_manager.py:2486`** (rename) — guarded by `FileExistsError`.
- Everything in `ui/dialogs/*`, `workflow/gamut_viewer.py`,
  `workflow/softproof_runner.py`, `workflow/cups_printer.py`,
  `ui/tabs/tab_print.py:1741` — `mkdtemp` temp trees.

#### Does anything ever remove or prune an `old/` archive?

**No pruning, retention or age-out logic exists.** Every reference to `old/` in
a delete context is an *exclusion* (`chart_import.py:110/195`,
`file_manager.py:2019` `DUPLICATE_NEVER`, `measurement_report_dialog.py:983`).
`Calibration.reset` states the rule at `:692`: *"an archive of archives helps
nobody."*

**The only production code that can destroy an `old/` archive is the three
`rmtree`s in this report** — they take `<project>/old/` and every
`runs/runN/old/` with them, behind a window that says *"This will permanently
delete: {dest}"* and never mentions that the archives are inside.
(`run_delete.py:649/743` also takes a run's `old/`, but to the Trash;
`_discard_run` takes one too, and does not.)

#### Can an archive be opened as a project?

Yes, but only deliberately. There is no recursive scan: `peek_project`
(`:2700`) reads `root/"project.json"` and nothing else, `resolved_root_for_name`
(`:2378`) returns one level, and there is no project-listing function. But
Create Chart ▸ "Open an existing profile" (`ui/tabs/tab_chart.py:5892`) is a
plain file dialog filtered to `project.json`, and its internal/external test
(`:5927`) accepts **any depth** under the ChromIQ folder on purpose (#130,
nested projects). Measured (`p9_archive_sideeffects.py`): `_project_root_for`,
`chart_import.is_full_project` and `peek_project` all accept
`<project>/old/<ts>/` as a project. So a person who navigates into an archive
and picks its manifest gets no warning, `open_project_at` sets
`_project_root_override` there, and new work is written **into the archive** —
persisted as `session_project_root` (`ui/main_window.py:2562`) and reopened next
launch. Not caused by this change; made more likely by adopting `old/` on three
more routes, and worth its own issue.

#### `scripts/`

Not reachable from the app. `drive_*.py` copy the user's project into a sandbox
and `rmtree` only the sandbox. The one to watch is
`scripts/make_report_demo.py:151`, which `shutil.move`s a live project root
aside rather than copying it.

---

### Verdict

**AGREE WITH CHANGES — and the central change is the destination.**

| the proposal | verdict |
|---|---|
| the three `rmtree`s must go | **agree**, and F3 measures the incident reproducing on them |
| replace with `move_to_trash` | **disagree** — the model, the two existing Replace paths and the code's own comment all say `old/<timestamp>/`. Trash is for **Delete**; this is a **Replace** |
| treat `False` as "nothing happened", never fall back to destroying | **agree**, and it maps onto `_archive_project_contents` raising `OSError` after its all-or-nothing rollback, with **M-PROJECT-REPLACE-FAILED** already written for it |
| "say so, abort the import" | **agree in principle, wrong place** — the three `_copy_*` functions have no widget and today a raise from them is swallowed in silence (F2). The decision and the window belong in the dialog layer |
| three sites is the whole job | **disagree** — F1, F2, F4 sit on the same three routes and are not fixed by the swap, and C5 finds two more `rmtree`/`unlink` hazards elsewhere |

### Implementation plan

1. **Do not start with the loaders.** Fix the same-second collision in
   `workflow/chart_import._archive_project_contents` first (`:200`): uniquify
   the timestamped folder the way `Calibration.archive_to_old` already does
   (`core/file_manager.py:647-656`). It is a live bug in Create Chart's Replace
   and in "Copy the whole project in ▸ Replace" today, and adopting `old/` on
   three more routes multiplies it. Test: two replaces inside one second keep
   both archives whole.
2. **Fix the self-collision guard (F1) before touching the delete.** In
   `ui/txt_loader.py:213-219` and `ui/ti2_loader.py:1200-1207`, replace
   `.resolve() ==` with `core.file_manager.same_dir` (case-correct on APFS,
   measured) **and** test containment, not equality:
   `same_dir(dest, src.parent) or dest in src.resolve().parents`. Test:
   `<work>/Canon` vs a source at `<work>/Canon/runs/run1/Canon.txt`, and the
   `canon`/`Canon` pair.
3. **Copy the source aside first.** In all three `_copy_*`, copy the loaded file
   (and, for `.ti2`, its `.ti1`/`.cht`/`.channels.json`/pages/`.ti3`/`.icc`) into
   a `mkdtemp` before anything moves, and import from there. Belt and braces for
   step 2, and the only thing that makes the import survivable if the source
   turns out to be inside the destination by a route nobody predicted.
4. **Replace the `rmtree` with the archive, in this order and no other:**
   `_archive_project_contents(dest)` → `Project.create(dest, name)` on the
   **same** folder. Never `rmtree` after archiving — that is the trap in the
   brief, and it is the only way `old/` gets destroyed (measured: with this
   order the archive survives intact).
5. **Give the failure a window.** Change the three `_copy_*` to raise a typed
   error (or return a result), catch it in `_handle_outside` /
   `_handle_inside` / `_handle_outside_ti3_only` / `_copy_out_new_project`, and
   render **M-PROJECT-REPLACE-FAILED** there. Nothing may be written before the
   archive succeeds — verified: on all three routes the destructive call is the
   first statement touching the destination.
6. **Call `self._file_mgr.forget_cached_project()`** after a successful replace,
   as `ui/tabs/tab_chart.py:9166` does (F4), and re-point the Profile-run bar.
7. **Rewrite the wording** (C4), through `tr()`, and add the new render
   functions to `tests/test_message_catalogue.py::WINDOW_SOURCES` so the
   allow-list stops being a hole.
8. **Fix the test that pins the word rather than the behaviour**
   (`tests/test_txt_loader.py:35`): assert the archive is readable and holds the
   old files, not merely that they left their old path.
9. **New tests**, one per fault: the read-only `reports/` project survives a
   replace; a read-only project **root** aborts with everything intact; a source
   inside the destination is refused or survives; two replaces in one second
   keep both archives; the cached `Project` is dropped.
10. **Separately, not in this change:** `_discard_run` (`:2121`) and
    `Calibration.reset`'s `.engine-partial` (`:701`) — both measured, both
    destroy user work, both belong on the same issue as the 2026-08-28
    conversion that missed them.

### Numbered open questions — only the owner can answer

1. **`old/` or the Trash for an import that replaces?** The evidence says
   `old/`: §S4.7 and T2.6 of `unified_measurement_management.md`,
   M-PROJECT-EXISTS / -REPLACE-CONFIRM, and both existing Replace
   implementations. Confirm — because the 2026-08-28 ruling as written says
   "deleting moves to the Trash", and whether an import *is* a delete is the
   owner's call, not ours.
2. **Do the import routes fall under §S4.7 at all?** The section is written for
   the Create Chart typed name. If it governs every "this name is taken"
   moment, the specification should say so; if not, the import routes need
   their own row. Either way this is a spec change, which per CLAUDE.md is
   reviewed and approved before it is implemented — it is not ours to write.
3. **New message IDs, or a variant of the existing three?** M-PROJECT-EXISTS and
   M-PROJECT-REPLACE-CONFIRM are worded for a chart build. Two new IDs
   (M-IMPORT-PROJECT-EXISTS, M-IMPORT-REPLACE-CONFIRM) keep both readable;
   parameterising the existing two keeps the catalogue small.
4. **M-PROJECT-REPLACE-FAILED's last clause** says "and no new chart has been
   made". Reuse it verbatim on the import routes, or make that word a
   parameter?
5. **Should an `old/` archive ever be prunable?** Nothing in the app removes one,
   and a replaced project's page TIFFs stay on the disk for ever. If a person
   replaces a project *because the disk is full*, `old/` does not help them and
   the Trash barely does. A "delete the archive" control is new behaviour and
   needs a ruling.
6. **The archive is openable as a project** (C5). Should ChromIQ refuse a
   manifest whose path contains `old/<timestamp>/`, warn, or leave it — given
   that being openable is exactly what makes recovery possible?
7. **`_discard_run` and the calibration `.engine-partial`** — separate issue, or
   folded into this one? Both are measured destructions of user work.

STATUS: challenged
