# Routing the loaders through §S4.7

STATUS: in-progress — design for challenge, no code written

Basti approved (2026-08-31): an import that lands on an existing project name
gets the SAME window Create Chart shows, not a bare "Overwrite existing folder"
button. `docs/reports/09` measured why: the same act is called "Overwrite" in
one loader and "Replace" in the other, and until today they had opposite
consequences.

## What exists

* **The window** — `ui/tabs/tab_chart.py:8799 _gate_typed_project_name`: four
  buttons (Replace it / Continue this project / Use a different name / Cancel)
  plus a **run picker**, defaulting deliberately to a NEW run because that is
  the only answer that cannot cost anything.
* **Its two builders take `peek` and almost no tab state**:
  `_build_run_picker(self, peek)` and `_project_exists_message(self, peek,
  chosen_run_id)`. `_run_label` is a `@staticmethod`.
* **The fact it is built from is already core**: `core.file_manager.peek_project`
  — read-only, never creates, never migrates.
* **The loaders' own versions**: `ui/txt_loader.py` ("Overwrite existing
  folder") and `ui/ti2_loader.py` ("Replace existing"), each with its own
  wording, its own collision check and — until report 09 — its own consequence.

## The design, to be challenged

Extract the window into **`ui/dialogs/project_exists.py`**, exporting one
function that takes `(parent, peek)` and returns a decision —
`REPLACE` / `CONTINUE(run_id)` / `DIFFERENT_NAME` / `CANCEL`. `tab_chart` calls
it; both loaders call it; the loaders' own dialogs and their two spellings of
the same question are deleted.

**Why extract rather than have the loaders reach into the tab:** a loader
importing a tab to ask a question inverts the dependency, and `tab_chart` is
already 17,000 lines. The window is a function of `peek`, so it does not need
the tab.

## Risks this must not realise
1. **§S4.7 is a specified, tuned path.** Its defaults (new run), its button
   order (Cancel far right), and the fact that it carries §4's answer for the
   run it names are all specified. Extraction must not change any observable
   behaviour in Create Chart. That is the main regression risk.
2. `_pending_replace` and `_adopt_run_choice` are TAB state the window sets.
   The extracted dialog must RETURN a decision and let each caller apply it —
   not reach back into a tab.
3. The loaders run in a different context: a `.txt`/`.ti2`/`.ti3` import has no
   Profile-run bar to point at, so "Continue this project" means something
   subtly different. Say exactly what.
4. The spec says §S4.7 fires for a name typed in Create Chart. Extending it to
   the loaders is a SPEC CHANGE that Basti has approved; §I/§S4.7 must be
   amended in writing, marked awaiting confirmation.

## Open questions
1. Does "Continue this project" make sense for an import, and into WHICH run —
   the picker's, presumably, but the loaders currently always create `run1`.
2. What happens to a loader import when the project exists but is EMPTY?
   §S4.7 shows no window at all in that case — is that right here?
3. The loaders can be reached with no project open at all. Does anything change?
4. Three still-open findings from report 10 belong with this work: the stale
   manifest/bar after replacing the OPEN project (F4), failures that are logged
   but never shown (F2), and the wording that still says "permanently delete".

---

## Challenge

STATUS: in progress — adversarial review, no source changed.

Proof: `~/Desktop/knut-s47/` (INDEX.md). Settings sandboxed to a scratch `.ini`
for every probe; the owner's `custom_output_path` was **unset** before this work
started and is checked by VALUE at the end.

Skeleton (filled in below as each is measured):

- C0  The headline / verdict
- C1  Is the extraction even possible — every piece of tab state, one by one
- C2  What must be verified to prove Create Chart is unchanged; what the tests catch
- C3  Does §S4.7 MEAN the same thing for a loader — Continue / empty / no project open
- C4  The opposite case: two questions that merely look alike
- C5  Report 10's three open findings — F4, F2, the wording
- C6  The exact wording, and whether it must go to §M-PROPOSED first
- C7  The spec amendment, as it would read
- C8  Numbered implementation plan
- C9  Numbered OPEN QUESTIONS for the owner

---

### C0. The headline — **AGREE WITH CHANGES**, and two of the changes are load-bearing

The extraction is possible and worth doing. Three things in the design as
written are wrong, and one of them would be a **data-safety regression on the
data-safety round**:

1. **`(parent, peek) -> Decision` is the wrong signature.** It silently drops
   the two rules that decide whether there is a run picker at all and what it
   defaults to — `is_calibration` and `_is_verification_target`. Those are read
   off the TAB (`tab_chart.py:8915-8918`, `:8952-8956`) and a loader has
   neither. A function that takes only `peek` cannot express them, so either
   the loaders get a picker they must not have, or Create Chart loses one it
   must keep.
2. **§S4.7's "an empty project raises no window" MUST NOT be carried to the
   loaders.** Measured below (C3.2): a project holding an interrupted
   measurement, a printed page, a quality report, an earlier `old/` archive and
   a typed run description reads `holds_anything = False`. Under the rule as
   specified there is no window, the import proceeds, and `Project.create`
   rewrites `project.json` from `run4 / [run1..run4]` to `run1 / [run1]` and
   **blanks the run description the user typed**. Nothing is archived. Today
   this is impossible, because the loaders test `dest.exists()` — the folder,
   not its contents.
3. **"Continue this project" does not exist for `.txt` or a bare `.ti3`.** It is
   not an extraction, it is a feature: there is no code anywhere that files a
   measurement into a chosen run of a project that is not open. `.ti2` has it
   (`workflow/chart_import.import_external_chart`, which takes an arbitrary
   `Project`); the other two routes have `Project.create` + `current_run()` and
   nothing else.

And the risk the design names first — *"extraction must not change any
observable behaviour in Create Chart"* — is **real, unguarded and free to
trip**. Two mutations that change what the person sees leave **98 tests green**
(C2).

### C1. Is the extraction possible — every piece of TAB state, one by one

Read in full: `_typed_project_peek` (`ui/tabs/tab_chart.py:8695-8742`),
`_run_label` (`:8744`), `_project_exists_message` (`:8773-8797`),
`_gate_typed_project_name` (`:8799-8892`), `_build_run_picker` (`:8894-8944`),
`_attach_run_picker` (`:8946-8971`), `_apply_gate_run_choice` (`:8973-8992`),
`_s4_is_answered_by_this_window` (`:8994-9018`), `_gate_route_and_replace`
(`:9020-9062`), `_forget_gate_answer` (`:9064-9083`), `_perform_pending_replace`
(`:9085-9112`), `_confirm_replace_whole_project` (`:9114-9139`),
`_replace_whole_project` (`:9141-9167`), `_confirm_displacing_results`
(`:14372-…`).

| # | Tab state | Read / written | Can it be a returned decision? | Plan |
|---|---|---|---|---|
| 1 | `self._name_typed_by_user` | read, via `_typed_project_peek` | **No — and it must not move.** It exists so a name the APP filled in never raises the window (`:8705-8712`). A loader's name box has no such trap: every character in it was typed. | **Stays in `tab_chart`.** The caller decides *whether to ask*; the dialog only *asks*. `_typed_project_peek` does not move. |
| 2 | `self._active_name_field()` (`_manual_target_name_edit` / `_target_name_edit`) | read twice — once for the peek, once in the Replace branch to store `name_then` | No | Stays. The Replace branch's second read is the arm-then-act drift guard (#4 below). |
| 3 | `self._file_mgr` — `resolved_root_for_name`, `is_named`, `working_dir` | read, via `_typed_project_peek` | No | Stays. The loaders resolve their own destination (`working_dir / _normalise(name)`), which is a different resolver — see C4.1. |
| 4 | `self._pending_replace` | set `None` on entry; set `(root, typed)` on Replace | **Yes** → `Decision.REPLACE` | Returned. Each caller applies it: `tab_chart` arms it (it has four early returns between the answer and the point of no return, `:9066-9072`); a loader performs it at once (nothing can drift inside one call). |
| 5 | `self._adopted_via_gate` | set `False` on entry, `True` on Continue | **Yes** → `Decision.CONTINUE` | Returned. It is consumed by `_builds_into_project`, a Create-Chart concept. |
| 6 | `self._adopt_run_choice` | `del` on entry, set on Continue | **Yes** → `Decision.CONTINUE(run_id)` | Returned. `_apply_gate_run_choice` stays on the tab — it drives the Profile-run bar, which a loader has none of. |
| 7 | `self._target_ctl.target.is_calibration()` | read in `_build_run_picker` (`:8915-8918`) **and** `_s4_is_answered_by_this_window` (`:9011-9012`) | **No** | **Must become an INPUT.** This is the gap in the proposed signature. |
| 8 | `self._is_verification_target()` | read in `_build_run_picker` for the picker default (`:8936-8940`) and in `_s4_is_answered_by_this_window` | **No** | **Must become an INPUT** (the default run id). |
| 9 | `self` as the `QMessageBox` parent | read | Yes | Already `parent` in the proposed signature. |
| 10 | `self._focus_project_name_field()` on "Use a different name" (`:8890`) | written (focus + `selectAll`) | **Yes, but the meaning differs** → `Decision.DIFFERENT_NAME` | Returned. For `tab_chart` the caller focuses the persistent field; for a loader there is no persistent field — the name box was inside the dialog that just closed, so the caller must **re-open its own name prompt**. See C4.2. |
| 11 | `self._confirm_replace_whole_project(peek)` (`:9114`) | calls a second window | Yes — pure in `peek` | **Moves with the dialog.** It reads nothing but `peek` and `self` (as parent). |
| 12 | `self._project_exists_message(peek, chosen)` (`:8773`) | pure given `peek` | Yes | Moves. **But see C2.4 — it is named in `test_message_catalogue.py::WINDOW_SOURCES` as a (module, class, method) triple, and moving it breaks that test.** |
| 13 | `self._run_label` | `@staticmethod`, pure | Yes | Moves. |
| 14 | `self._replace_whole_project` / `_replace_failed_message` (`:9141`, `:9169`) | calls `_archive_project_contents`, then `self._file_mgr.forget_cached_project()` | Partly | **Split.** The archive + the failure window move; `forget_cached_project()` is FileManager state and belongs to the caller — and the loaders do not call it today, which is report 10's F4 (C5.a). |

**Verdict on C1: possible, but the signature must be**

```python
@dataclass(frozen=True)
class Question:
    peek: ProjectPeek
    run_picker: bool = True      # False for a calibration build (#7)
    default_run: str = ""        # "" = a new run; peek.run_id for a verification (#8)
    subject: str = "chart"       # which M-PROJECT-EXISTS wording — C6

@dataclass(frozen=True)
class Decision:
    kind: str                    # "replace" | "continue" | "rename" | "cancel"
    run_id: str = ""             # only for "continue"

def ask_project_exists(parent, q: Question) -> Decision: ...
```

`_s4_is_answered_by_this_window` **does not move.** It is a statement about the
tab's own run type (`:8994-9018`), not about the window, and it is meaningless
for a loader. `tab_chart` keeps computing it and keeps returning the second
half of its tuple unchanged.

### C2. What must be verified to prove Create Chart is unchanged — and what the tests actually catch

**§S4.7 as it behaves TODAY, captured from the real app.** The real
`MainWindow`, the real `TabChart`, a real project in a scratch working folder,
the name typed with `QTest.keyClicks` so `textEdited` fires exactly as a
keystroke does. Proof: `~/Desktop/knut-s47/shots/` — `01-s47-window-default.png`
and its `.json`, `02`/`03` (the picker on a new run and moved to Run 1),
`04-s47-replace-confirm.png`.

Measured observables, all of which extraction could change:

| # | Observable | Value TODAY (measured) |
|---|---|---|
| O1 | `text()` | *"There is already a project called “Canon”"* |
| O2 | `windowTitle()` | `""` — **macOS shows no message-box title at all**; `setWindowTitle(title)` at `:8843` reaches nobody on this platform. The heading the person reads is `setText`. |
| O3 | `icon()` | `Icon.NoIcon` |
| O4 | `defaultButton()` | **Cancel** |
| O5 | `buttons()` — creation order | `[Continue this project, Cancel, Replace it, Use a different name]` — **Cancel is SECOND** |
| O6 | **left-to-right by x** | `[Continue this project, Replace it, Use a different name, Cancel]` |
| O7 | picker items | `[("A new run (nothing already there is touched)", ""), ("Run 1","run1"), ("Run 2","run2"), ("Run 3","run3")]` |
| O8 | picker current | `("A new run …", "")` |
| O9 | picker label | *"Make the new chart in:"*, and the picker sits **above** the button row |
| O10 | body follows the picker | *"nothing yet: no chart, no measurement and no profile"* on a new run → *"a chart, a measurement, a built profile"* on Run 1 (`03-…json`) |

**O5 vs O6 is the whole point.** Qt lays a `QDialogButtonBox` out by ROLE, and
on macOS that puts Cancel second. The visual order is correct only because
`spread_message_box_buttons(box, order=[go, replace, rename, cancel])`
(`:8868`) overrides it. That call is Basti's ruling of 2026-08-27 — *"i want
cancel on the very right"*.

#### C2.1 Three mutations, each proven to land, run on an rsync'd copy in the scratchpad — never in the repo

| Mutation | Lands? | `test_project_name_collision.py` + `test_message_catalogue.py` |
|---|---|---|
| **A** — `spread_message_box_buttons(box, order=[…])` → `spread_message_box_buttons(box)` | yes, `:8868` | **98 passed** |
| **B** — `box.setDefaultButton(cancel)` → `setDefaultButton(replace)` | yes, `:8854` | **98 passed** |
| **C** — the picker default `""` → `peek.run_id` | yes, `:8936` | **2 failed**, 96 passed |

**Mutation A is not cosmetic, and it is measured, not argued.** The same driver
run against the mutated tree gives:

```
buttons_left_to_right_by_x: ["Use a different name", "Replace it", "Cancel", "Continue this project"]
```

Cancel third; the destructive **Replace it** second from the left; the safe
answer exiled to the far right. Side by side:
`~/Desktop/knut-s47/shots/01-s47-window-default.png` (today) vs
`~/Desktop/knut-s47/mutation/51-s47-window-default.png` (mutation A).
**Ninety-eight tests stay green.**

Mutation B means a Return keypress on the window is an **overwrite** — the one
thing `:8853` exists to forbid, in a comment saying so. Green.

#### C2.2 What no test asserts

Swept the whole suite: **nothing** asserts button order, the default button,
the icon, the picker's label, the picker's placement above the button row
(`_attach_run_picker`, `:8946` — Qt would otherwise put a plainly added widget
UNDER the buttons), or the picker's `_input_bg_qss()` stylesheet (`:8925-8929`,
Basti's beige-combo complaint of 2026-08-27). `tests/test_project_name_collision.py`
selects buttons by TEXT out of `self.buttons()` (`:229-234`) — creation order —
so it is structurally blind to the layout.

#### C2.3 The list a reader must check to be sure extraction changed nothing

O1–O10 above, each as a NEW assertion, plus:

* R1 the `peek` is still computed by `_typed_project_peek` — i.e. the
  `_name_typed_by_user` guard still gates the window;
* R2 `_gate_typed_project_name` still returns `(proceed, s4_answered)` with the
  same four mappings (`test_each_button_leads_where_it_says` covers three);
* R3 the Replace is still ARMED, not performed (`:8886`), and still dropped when
  the name drifts (`:9101-9107`);
* R4 a calibration build still gets **no picker** (`:8915-8918`);
* R5 a verification build's picker still defaults to `peek.run_id` (`:8936-8940`);
* R6 `_confirm_replace_whole_project` still runs BEFORE the arm (`:8878`);
* R7 the window is still never opened from the live preview.

R2–R7 are covered today. **O2–O9 are not, and A and B prove the gap is
exploitable.** Whoever does the extraction must land O4, O6, O8 and O9 as tests
in the same commit, or the refactor ships unguarded.

#### C2.4 The extraction breaks `test_message_catalogue.py`, mechanically

`WINDOW_SOURCES` (`tests/test_message_catalogue.py:309-325`) names
`("ui.tabs.tab_chart", "TabChart", "_project_exists_message")` as a
**(module, class, method)** triple and does
`getattr(getattr(mod, cls), method)`. Mutation D — the method renamed off the
class, which is what extraction does — gives:

```
FAILED test_the_window_takes_its_text_from_the_catalogue[ui.tabs.tab_chart-TabChart-_project_exists_message]
FAILED test_the_window_writes_no_prose_of_its_own[ui.tabs.tab_chart-TabChart-_project_exists_message]
3 failed, 95 passed
```

The list cannot express a module-level function, so the extraction requires a
change to the shape of `WINDOW_SOURCES` itself. That is a cost the design does
not mention, and the temptation — dropping the row — would remove the only
check that this window's text comes from the catalogue.

### C3. Does §S4.7 MEAN the same thing for a loader?

**What the loaders show TODAY**, captured from the real app the same way
(`~/Desktop/knut-s47/shots/05`–`09`):

| | `.txt` (Build Profile ▸ Load measurement data) | `.ti2` (Print ▸ Load chart) |
|---|---|---|
| window | *Choose a name for the profile* | *Choose a name for the profile* |
| buttons before a collision | `OK` (default) · `Cancel` | `OK` (default) · `Cancel` |
| buttons after typing `Canon` | **`Overwrite existing folder`** · `Cancel` — `OK` is HIDDEN | same |
| red line | *“Canon” already exists. Click “Overwrite existing folder” to replace it.* | same |
| the confirmation | `windowTitle=""` · icon **Warning** · *"This will permanently delete:\n\n {dest}\n\nand replace it with the imported **measurement**. Continue?"* · buttons `No` `Yes` left-to-right, default **No** | identical but *"…the imported **chart files**. Continue?"* |

Two measured facts report 10 could not have seen:

* **The heading "Overwrite existing folder?" is not on screen.** `windowTitle`
  is `""` on macOS for a `QMessageBox`; the only sentence the person reads is
  *"This will permanently delete…"*. So the inaccurate text is not merely
  *also* present — it is **the whole window**.
* **`QMessageBox.warning` is a static that runs its own C++ event loop.**
  Patching `QMessageBox.exec` in Python does not reach it: this driver hung on
  a real modal until a `QTimer` was armed before the call. Anyone writing tests
  for these two dialogs needs to know that.

#### C3.1 "Continue this project" for an import — into which run?

**For `.txt` and a bare `.ti3`, there is no answer, because the capability does
not exist.**

* `ui/txt_loader.py:333-341`, `ui/ti2_loader.py:1324-1332` and `:1395-1404` all
  do `Project.create(dest, name)` then `proj.current_run()` — **always `run1`**,
  always a fresh manifest. There is no parameter for a run and no caller that
  passes one.
* `resolve_txt` (`ui/txt_loader.py:29-44`) takes **no controller**. It cannot
  see which project is open, cannot move a Profile-run bar, and its caller
  (`ui/tabs/tab_profile.py:4298`) never opens the project it just created. So
  §S4.7's `_apply_gate_run_choice` — *"point the Profile-run bar at the run the
  picker names"* (`tab_chart.py:8973`) — has no counterpart at all.
* `.ti2` is the exception: `workflow/chart_import.import_external_chart(ti2, ti1,
  tiffs, project, target, replace=…)` (`:47-72`) takes an **arbitrary**
  `Project` and a `MeasurementTarget`, so `CONTINUE(run_id)` is implementable
  there as `import_external_chart(…, Project.load(root), MeasurementTarget(
  run_type=…, profile_run=run_id))`.

So "Continue this project" is **one feature for `.ti2` and two unwritten
features for `.txt` and `.ti3`** — not an extraction. A window that offers a
run picker and a Continue button on a route where neither can be honoured is
worse than the button we have.

There is also a **prior claim on the phrase**. `_handle_loose_into_project`
(`ui/ti2_loader.py:640-704`) already asks a richer version of the same
question — *Import as a new run* / *Create a new run instead* / *Replace
{run}* — against the OPEN project, with per-choice prose naming
`runs/{run}/old/`. It is reached *before* the name prompt. So for `.ti2` the
app already has a "continue this project" window; §S4.7's would be a **second**
one, differing only in which project it targets.

#### C3.2 §S4.7 shows NO window when the project is EMPTY. Is that right for an import? — **No. Measured.**

`peek_project` counts `*.ti1`/`*.ti2`, `*.ti3`, `*.icc`/`*.icm`, dated
verification folders, and `cal/*.cal`/`cal/*.ti3`
(`core/file_manager.py:2867-2894`). It does **not** count:

* `runs/runN/meta.json` — the run **description** the user typed, which
  `docs/design/per_run_description.md` governs;
* `runs/runN/reports/`, `runs/runN/exports/`, project-level `exports/`;
* `runs/runN/old/` — an earlier archive, the one thing this whole round exists
  to keep;
* a page TIFF whose `.ti2` is gone;
* **`<stem>.ti3.engine-partial`** — an interrupted measurement. `glob("*.ti3")`
  does not match it. That is the exact file report 10 §F confirmed
  `Calibration.reset`'s fix was written to preserve.

Driven through the real `_copy_txt` with `overwrite=False` — which is what
§S4.7's "no window" branch produces:

```
PEEK.holds_anything : False
PEEK.runs           : [('run1', False), ('run2', False), ('run3', False), ('run4', False)]
MANIFEST BEFORE     : run4 ['run1', 'run2', 'run3', 'run4']

>>> §S4.7 says: NO WINDOW.  So the import just goes ahead:

MANIFEST AFTER      : run1 ['run1']
RUN FOLDERS ON DISK : ['run1', 'run2', 'run3', 'run4']
ORPHANED BY MANIFEST: ['run2', 'run3', 'run4']
run1 meta.json desc : ''            ← was "Knut's run — the cable came out at patch 42"
any old/ archive at project level: NONE
```

`Project.create` (`core/file_manager.py:1597-1610`) writes
`ProjectManifest.fresh(...)` **and** `run.save_meta(RunMeta.fresh("run1"))`.
So the person loses their typed description, their manifest is rewritten to
name one run of four, and **nothing is archived** — because no window was
shown, nobody agreed to a Replace, and `_archive_project_contents` never ran.

**Today this cannot happen.** The loaders test `(working_dir / name).exists()`
(`ui/txt_loader.py:240`, `ui/ti2_loader.py:1229`) — the FOLDER, not its
contents — so the person is stopped and must click through the confirmation,
and the replace then archives. Carrying §S4.7's emptiness rule over would be a
**regression introduced by the data-safety round**.

The right rule for a loader is the one the loaders already use: **the question
is asked whenever the destination folder exists**, because the act is not
"build into a project" but "create a project where a folder already is".

#### C3.3 No project open at all

* `resolve_txt` never had a controller (C3.1). `resolve_ti2` is called without
  one from `ui/tabs/tab_print.py:1341`, and `resolve_ti2` then routes to
  `_handle_inside` / `_handle_outside` — the *"original new-project flow"*
  (`ui/ti2_loader.py:462-465`). That is the ordinary first action after launch.
* §S4.7's own "not a collision" rule is *"the project already open is not a
  collision — it is this project"* (`tab_chart.py:8726-8736`, `same_dir` against
  `_file_mgr.working_dir()`). **A loader has no equivalent and must not grow
  one**: its `_is_self_collision` is `dir_holds(working_dir / name, path)` —
  "does the folder I would replace HOLD the file I am importing" — a different
  question with a different answer (report 10 §C).
* So the answer to open question 3 is: with nothing open, nothing changes for
  the loaders — but **the converse is the hazard**. If the shared dialog also
  inherits §S4.7's open-project suppression, importing into the OPEN project by
  name would show **no window at all** and `Project.create` would rewrite it
  in place. That is report 10's F4 turned from a stale bar into a silent
  overwrite. The suppression rule must stay in `_typed_project_peek`, on the
  tab — which is what C1 row 1 already requires.

### C4. The opposite case: two questions that merely look alike

Argued as strongly as it can be, because it is close.

**C4.1 The questions differ in what they resolve.** Create Chart asks about a
name in a **persistent field**, resolved by
`FileManager.resolved_root_for_name` — which deliberately keeps a NESTED
project where it is, and whose absence once let one click empty a project the
build never touched (`tab_chart.py:8717-8723`). The loaders ask about
`working_dir / FileManager._sanitise(strip_workfile_ext(name))` — always flat,
never nested. **Two different resolvers, two different folders**, and the
window's whole body is *"ChromIQ found it here: {folder}"*. Merging the windows
without merging the resolvers means one window that is right about the path
half the time.

**C4.2 "Use a different name" is a button in one and the text cursor in the
other.** In Create Chart the name box outlives the window, so the button is
`_focus_project_name_field()` (`:9182`). In a loader the name box **is inside
the dialog** (`ui/txt_loader.py:182`), so a §S4.7 window raised on top of it
would offer a button that says "take me back to the box I am covering". Either
the loaders lose their name prompt — a much larger change than the design
describes — or §S4.7 is raised *from inside* it and the button is a no-op.

**C4.3 The four answers are not four answers on every route.** C3.1: `CONTINUE`
does not exist for `.txt` or a bare `.ti3`. `REPLACE` is arm-then-act on the tab
(four early returns sit between the answer and the point of no return,
`:9066-9072`) and act-now in a loader.

**C4.4 The silence rule inverts.** C3.2: "empty ⇒ no window" is safe for a
build and destructive for an import.

**Is that case stronger? — Partly, and it changes the SHAPE of the fix, not the
goal.** The owner's ruling is about consistency of **consequence**, and the
report says so in its opening. That is satisfiable without one window:

* one **consequence** — already true since report 09: all three sites archive
  into `old/<date>/`;
* one **vocabulary** — "Replace it", never "Overwrite"; "moved into its own
  old folder", never "permanently delete";
* one **catalogue entry** with a `{subject}` slot, so the sentences are written
  once and reviewed once;
* one **shared decision type**, so a reader can see the three call sites give
  the same four (or three) answers.

What does NOT have to be shared is the **container**. Create Chart's is a
free-standing `QMessageBox`; the loaders' is a state INSIDE a name prompt that
already shows the collision live as you type (`_on_name_changed`,
`ui/txt_loader.py:238-251`) — which is, if anything, better than a modal,
because the person sees the collision before they commit to anything.

**So: agree with the ruling, and implement it as a shared catalogue entry, a
shared decision type and a shared consequence — with the loaders' collision
state gaining the missing answers in place, rather than the loaders' name
prompt being replaced by a window that cannot host a name box.** If the owner
wants literally the same window, that is his call and it is question Q1 below;
it costs the loaders' live collision feedback and needs C4.2 answered.

### C5. Report 10's three open findings, and how each is handled here

#### C5.a — F4, the stale manifest and the lying run bar (report 10 §D, "Still wrong" 1)

**It belongs here, and it is three lines.** `tab_chart.py:9166` already calls
`self._file_mgr.forget_cached_project()` immediately after
`_archive_project_contents`, with a comment saying exactly why. The three import
sites (`ui/txt_loader.py:361`, `ui/ti2_loader.py:1351`, `:1435`) do not.

But `forget_cached_project()` alone is **not sufficient** for the bar. Report 10
measured the bar still listing `Run 1 … Run 4` after only `run1` survived,
because the bar is the `MeasurementTargetController`'s cached view, not the
FileManager's. `ui/ti2_loader.py:905-917` already has the helper that fixes
that — `_point_bar_at_current_run(controller)`, which calls
`controller.set_profile_run(proj.current_run().id)` **and**
`controller.notify_changed()` *"so the Create Chart name field reflects a newly
switched-in project (#130 Bug C, Knut)"*.

So: **after any replace, `forget_cached_project()` and then, where a controller
exists, `_point_bar_at_current_run`.** `.txt` has no controller (C3.1) — that
is Q4 below.

Do not fold this into the dialog. It is what the CALLER does with
`Decision.REPLACE`, and putting it inside a window is how a window ends up
owning FileManager state.

#### C5.b — F2, failures logged but never shown (report 10 §B2, "Still wrong" 5)

The three `_copy_*` functions take no parent widget, so they cannot open a
window; `ui/tabs/tab_profile.py:4298` calls `resolve_txt` bare, so the `OSError`
escapes to `main.py`'s excepthook and the app looks idle.

**Fix it at the seam this work already opens.** The dialog function receives
`parent` anyway. The archive belongs on the *caller* side of the decision, not
inside `_copy_txt`:

```
decision = ask_project_exists(parent, q)
if decision.kind == "replace":
    try:
        dest_old = _archive_project_contents(dest)
    except OSError as exc:
        show M-PROJECT-REPLACE-FAILED(folder=dest, reason=exc)   # already exists
        return None                                              # import does not proceed
```

`M-PROJECT-REPLACE-FAILED` is already written (§M-PROPOSED, spec line 1648) and
already rendered by `tab_chart._replace_failed_message` (`:9169`). Reusing it
closes F2 with **no new message text** — which matters, because new text needs
approval and this does not.

That also closes report 10 finding 9 in the same move: log the returned archive
path, which `tab_chart.py:9160-9161` already does and neither loader does.

#### C5.c — the wording (report 10 "Still wrong" 8)

Four separate untruths, not one:

| # | Where | Says | Truth |
|---|---|---|---|
| W1 | `ui/txt_loader.py:197`, `ui/ti2_loader.py:1184` | button **"Overwrite existing folder"** | it archives |
| W2 | `ui/txt_loader.py:252`, `ui/ti2_loader.py:1240` | *Click “Overwrite existing folder” to replace it.* | ditto, and it names a button that will be renamed |
| W3 | `ui/txt_loader.py:301-304`, `ui/ti2_loader.py:1289-1292` | **"This will permanently delete:"** | nothing is deleted — and C3 measured this is the ONLY sentence on screen |
| W4 | `ui/txt_loader.py:274/289`, `ui/ti2_loader.py:1262/1277` | *"the measurement's own folder"* / *"the chart's own folder"* | since the F1 fix the guard means an **ancestor** — the project the file lives inside |
| W5 | `ui/ti2_loader.py:1394` (bare `.ti3` reusing `_ask_profile_name`) | *"the imported **chart files**"* | it is a measurement |

### C6. The exact wording — and yes, it must go to §M-PROPOSED first

**It must.** CLAUDE.md: *"New user-facing message text … goes to §M-PROPOSED
first and is not written into a tab until it is approved."* And report 09 is
right that `test_message_catalogue.py` would not catch it: `WINDOW_SOURCES`
(`:309-325`) is an allow-list of **(module, class, method)** triples with no
loader entry — and both loaders' dialogs are **module-level functions**, so the
list cannot express them even if someone wanted to add them. New text written
into `ui/txt_loader.py` or `ui/ti2_loader.py` today is invisible to every check
in the suite. That is the second reason to render from the catalogue rather
than write literals in the loaders.

Note that **M-PROJECT-EXISTS itself is still PROPOSED** (spec line 1537, inside
§M-PROPOSED). Extending it to a second family of callers does not promote it.

`{n}` is the number of runs and `{f}` how many hold work; the count-bearing
phrases reuse `M.runs_phrase`, which already has real singular and plural and
never `(s)`.

#### M-IMPORT-PROJECT-EXISTS · PROPOSED · the name for an imported file is already a project — Build Profile ▸ Load measurement data, Print ▸ Load chart

*`{name}` is the sanitised folder name, `{folder}` its path, `{runs}` the
`runs_phrase`, `{cal}` the calibration sentence, and `{subject}` is* the
measurement *for an i1Profiler `.txt` and for a bare `.ti3`, and* the chart *for
a `.ti2`.

> **There is already a project called “{name}”**
>
> ChromIQ found it here:
> {folder}
>
> Importing {subject} under that name would start a new project in the same place. This one has {runs}.{cal}
>
> Nothing has been changed yet. Choose what you would like to do:
>
> •  Replace it: everything the project holds now is moved into its own “old” folder, with today’s date, and the imported {subject} is put into a new, empty project of the same name. Nothing is deleted, and ChromIQ asks you to confirm before it does it.
>
> •  Use a different name: nothing is touched, and ChromIQ takes you back to the name box so you can type another one.
>
> •  Cancel: stops here and changes nothing.

Buttons: **Replace it** · **Use a different name** · **Cancel**, default
**Cancel**, Cancel on the far right.

**"Continue this project" is deliberately absent** — see C3.1: the capability
does not exist on two of the three routes. Adding the button is Q2 below.

#### M-IMPORT-REPLACE-CONFIRM · PROPOSED · the second look, before an import clears a project

> **Start “{name}” again from empty?**
>
> Everything this project holds is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays inside the project, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.
>
> After that, a new and completely empty project of the same name is started in the same place, and {subject} you are importing is put into its first run.

Buttons: **Replace it** · **Go back**, default **Go back**.

*(This is `M-PROJECT-REPLACE-CONFIRM` with one clause changed — "your new chart
is made in its first run" → "{subject} you are importing is put into its first
run". If the owner prefers, make the existing entry take `{subject}` and have
one message instead of two; that is Q3.)*

#### The line under the name box, live as the person types (replaces W2)

> “{name}” is already a project, with {runs}. Choose a different name, or click “Replace it”.

#### After a successful replace — closes report 10 finding 9 (new, and the smallest possible)

> The earlier “{name}” has been moved into its own “old” folder:
> {folder}
> Nothing was deleted.

#### The self-collision refusals (replaces W4 — accurate at last)

For the `.txt` and bare-`.ti3` routes:

> That name points at the project this measurement is already inside, so importing it there would replace the file itself. Pick a different name.

For the `.ti2` route:

> That name points at the project this chart is already inside, so importing it there would replace the file itself. Pick a different name.

#### W5

The bare-`.ti3` route must not reuse the chart wording. With `{subject}` in the
catalogue this fixes itself — `_handle_outside_ti3_only`
(`ui/ti2_loader.py:1375-1389`) passes *the measurement*.

#### What is deleted rather than reworded

W1 and W3 go away entirely: the button becomes **Replace it** and the
confirmation becomes M-IMPORT-REPLACE-CONFIRM. There is then no string
anywhere in ChromIQ saying "Overwrite existing folder" or "permanently delete"
for an act that archives.

### C7. The spec amendment, drafted as the specification would read

To be inserted after §S4.7 in `docs/design/unified_measurement_management.md`.
**Not written into the spec by this report** — it is a draft for review.

---

#### S4.8 · **PROPOSED** · a file imported under a name that is already a project

**⏳ Awaiting confirmation. Confirmed by:** *nobody yet.*

| # | Condition | Sequence |
|---|---|---|
| S4.8 | a `.txt`, `.ti2` or bare `.ti3` is imported into a NEW project (Build Profile ▸ Load measurement data · Print ▸ Load chart · Measure ▸ Load chart, "Use as base for a new profile"), and the destination folder **already exists** | 1 **M-IMPORT-PROJECT-EXISTS** → 2 *Cancel / Use a different name stops, nothing written* → 3 Replace it → **M-IMPORT-REPLACE-CONFIRM** → *Go back stops* → archive the whole project into its `old/<date>/` → 4 create the project and file the import in `run1` |

**The consequence is the same as S4.7's, and that is the point of the rule.**
The same act — "the name I want is taken, replace what is there" — moves the
whole project into its own `old/<date>/` and deletes nothing, whether it was
reached from Create Chart or from a loader. Before 4.1.5 one loader called it
"Overwrite" and destroyed, the other called it "Replace" and archived, and
which one a person got was decided by which file type they had loaded.

**Three differences from S4.7, each deliberate:**

1. **The window is raised whenever the destination FOLDER exists — not only
   when the project holds something.** S4.7's silence for an empty project is
   right for a build, which continues an existing project through
   `Project.load`. An import calls `Project.create`, which writes a fresh
   manifest and a fresh `run1/meta.json`, so it rewrites the project's record
   of itself and blanks the run description `per_run_description.md` governs —
   and `peek_project` does not count a run description, a `reports/` folder, an
   `old/` archive, an unmeasured page or an interrupted
   `<stem>.ti3.engine-partial` as "something". A project that reads as empty is
   therefore not a project it is safe to write over unasked.
2. **There is no run picker and no "Continue this project".** An import creates
   `run1` of a new project; it does not join an existing one. Joining a project
   already open is a different act with its own window (Print ▸ Load chart, a
   loose chart while a project is open) and its own choices — *Import as a new
   run* · *Create a new run instead* · *Replace {run}*.
3. **"Use a different name" returns to the loader's own name box**, which is
   part of the same window rather than a field behind it.

**T2.6 applies unchanged**: after any of these, the original is in
`old/{date}/` and readable; nothing is ever deleted.

**When the archive fails, the import does not proceed** and
**M-PROJECT-REPLACE-FAILED** is shown. An import that cannot make room must
never half-create a project on top of one it could not move.

**After a replace, the app's own view of the project is dropped** — the cached
`Project` and, where the caller has one, the Profile-run bar — so nothing goes
on offering runs that are now in `old/`.

---

Message entries to add to §M-PROPOSED: **M-IMPORT-PROJECT-EXISTS** and
**M-IMPORT-REPLACE-CONFIRM**, as drafted in C6.

### C8. Numbered implementation plan

Nothing below is built. Steps 1–3 are the gate; 4 onwards need the answers to
C9.

1. **Pin §S4.7 before touching it.** Add to
   `tests/test_project_name_collision.py`, against the real `TabChart`, the
   observables C2 measured and nothing guards: O4 (`defaultButton()` is
   Cancel), O6 (buttons sorted by x are `Continue · Replace · Use a different
   name · Cancel`), O8 (the picker's current data is `""`), O9 (the picker's
   label, and that it sits above the `QDialogButtonBox`). **Prove each is a
   real guard by re-running mutations A and B and watching them fail** — they
   pass today. This commit must go in *before* the extraction, on the
   unrefactored code, or it proves nothing.
2. **Fix `WINDOW_SOURCES`.** Widen it to accept a module-level function
   (`(module, None, name)` or a dotted path) so the extracted
   `_project_exists_message` stays checked. Do not drop the row.
3. **Run the targeted set green**: `tests/test_project_name_collision.py`
   `tests/test_message_catalogue.py` `tests/test_txt_loader.py`
   `tests/test_ti2_loader.py` `tests/test_an_import_never_destroys_a_project.py`
   `tests/test_project_name_is_never_invented.py`
   `tests/test_backing_out_of_a_preset_changes_nothing.py`. Baselines measured
   today: 53 · 45 · 78 across the three loader files · —.
4. **Write the two catalogue entries** (C6) into `docs/design/…` §M-PROPOSED and
   into `workflow/measurement_messages.py`, with `{subject}`. **No loader
   literals.** Nothing is wired to a tab until the entries are approved.
5. **Amend the specification** with §S4.8 (C7), marked
   `**Confirmed by:** *nobody yet.*`
6. **Extract `ui/dialogs/project_exists.py`** with the `Question` / `Decision`
   signature from C1 — not `(parent, peek)`. Move `_project_exists_message`,
   `_run_label`, `_build_run_picker`, `_attach_run_picker`,
   `_confirm_replace_whole_project` and `_replace_failed_message`. Leave
   `_typed_project_peek`, `_s4_is_answered_by_this_window`,
   `_apply_gate_run_choice`, `_pending_replace`, `_perform_pending_replace`,
   `_forget_gate_answer` and `_replace_whole_project`'s
   `forget_cached_project()` on the tab.
   `_gate_typed_project_name` becomes a thin adapter that builds the `Question`
   from tab state and maps the `Decision` back onto the four flags. **The tests
   from step 1 must still pass with no edit.** If any needs editing, the
   extraction changed behaviour — stop.
7. **Re-run the on-screen capture** (`~/Desktop/knut-s47/INDEX.md` has the
   driver's method) and diff O1–O10 against `01-s47-window-default.json`. That
   is the before; this is the after.
8. **Loaders — consequence and wording, no window change yet.** Rename the
   button to **Replace it**; replace the confirmation with
   M-IMPORT-REPLACE-CONFIRM; fix W4 and W5; add the post-replace line saying
   where the project went. Wire `Decision` in so the three call sites share one
   type even while the container differs (C4).
9. **Close F2**: move `_archive_project_contents` out of `_copy_txt` /
   `_copy_files` / `_copy_ti3_only` to the caller, which has `parent`, and show
   the existing **M-PROJECT-REPLACE-FAILED** on `OSError`, aborting the import.
   Log the archive path on success.
10. **Close F4**: `forget_cached_project()` after every replace, plus
    `_point_bar_at_current_run(controller)` where a controller exists.
11. **Tests that enter the real code**, closing report 10 findings 6 and 7:
    drive `ui.txt_loader._ask_profile_name`, `ui.ti2_loader._ask_profile_name`,
    `_copy_files` and `_copy_ti3_only` themselves. Note that
    `QMessageBox.warning` is a **static running its own event loop** — patching
    `QMessageBox.exec` does not reach it (C3); use a `QTimer` armed before the
    call, or convert the confirmation to an instance `QMessageBox` so it can be
    driven at all.
12. **Only then**, and only if the owner says so (Q1/Q2), replace the loaders'
    name prompt with the shared window and build `CONTINUE(run_id)` — starting
    with `.ti2`, which has `import_external_chart`, and treating `.txt` and
    bare `.ti3` as separate work.

### Anything I would do differently, including doing less

* **Do steps 1–3 and 8–11 and stop.** They deliver everything the ruling asked
  for — one consequence, one vocabulary, one decision type, and the user finally
  told where their project went — and they are the parts with no open questions
  attached. Steps 6 and 12 are the parts that can regress a tuned path.
* **Do not extract in the same commit as the loader changes.** A pure refactor
  and a behaviour change in one diff means a bisect cannot tell them apart, and
  this window has already cost six data-loss faults in one implementation
  (`_confirm_replace_whole_project`'s docstring, `:9117-9120`).
* **Do not move `_typed_project_peek`.** Its `_name_typed_by_user` guard is the
  memory note *"the app answered its own question"* made into code, and it has
  no meaning for a loader. Moving it into a shared module invites a future
  caller to use it and re-open that fault.
* **Consider not merging the run picker at all.** It is the single most tuned
  part of the window (C2, mutation C is the only mutation the suite catches)
  and it is meaningless on every loader route today.

### C9. OPEN QUESTIONS — only the owner can answer these

1. **Same window, or same consequence?** The ruling was that an import must not
   get a bare "Overwrite" button. C4 argues the two questions differ in what
   they resolve, where the name box lives, and which answers exist. Is the
   requirement (a) literally the §S4.7 window on the loaders — which costs them
   their name box and their live as-you-type collision line — or (b) the same
   words, the same consequence and the same set of answers, in the loaders'
   own prompt? *(This report recommends (b).)*
2. **Should an import be able to join an existing project — "Continue this
   project"?** It does not exist today for `.txt` or a bare `.ti3` and would be
   new work (C3.1). For `.ti2` it partly exists already, as a *different*
   window aimed at the project that is open. If yes, this is a feature and
   should be its own issue, not part of a refactor.
3. **One catalogue entry with a `{subject}` slot, or two?**
   M-PROJECT-EXISTS/M-PROJECT-REPLACE-CONFIRM parameterised, or the separate
   M-IMPORT-… pair drafted in C6? One entry means one review and one
   translation pass in thirteen languages; two means neither message carries a
   clause that is wrong for half its callers.
4. **The `.txt` route has no `MeasurementTargetController`** (`resolve_txt`
   takes none, and `tab_profile` never opens the project it creates). After a
   replace there, the Profile-run bar cannot be corrected — only the cached
   `Project` can be dropped. Should `resolve_txt` be given the controller so it
   behaves like the `.ti2` route, or is it correct that an i1Profiler import
   leaves the open project alone?
5. **§S4.7's own emptiness rule.** C3.2 measured that "empty" as
   `peek_project` defines it excludes a typed run description, an
   `old/` archive, a `reports/` folder, an unmeasured printed page and an
   interrupted `.ti3.engine-partial`. §S4.8 as drafted does not inherit the
   rule. **Should §S4.7 keep it?** A Create Chart build into such a project
   goes through `Project.load`, so it does not rewrite the manifest — but it
   also shows the person nothing about the partial measurement sitting there.
   This is a question about the model, and it contradicts nothing that is
   confirmed, so it is reported rather than changed.
6. **Report 10's findings 2, 3 and 4** (`duplicate_run` clobbering an unlisted
   run, `_discard_run`'s suffix filter, `verify_chart_snapshot`'s rollback) are
   *not* on the import routes and are not addressed by this work. Do they block
   4.1.5, or do they get their own round?

---

**Proof.** `~/Desktop/knut-s47/` — `INDEX.md`, `shots/` (§S4.7 and both loaders
as they behave today, PNG plus a JSON of every measured observable),
`mutation/` (the same window with mutation A applied).

**Safety, verified by value.**

| check | result |
|---|---|
| `defaults read com.chromiq.ChromIQ custom_output_path` | *does not exist* — unset, before and after |
| `~/ChromIQ` top-level inventory | 23 entries, unchanged |
| `~/ChromIQ/CR30-Test` | untouched |
| `~/Desktop/i1Profiler` | untouched |
| repo source files | **none changed** — this report is the only edit |

Every driver set `CHROMIQ_SETTINGS_FILE=/tmp/claude-s47-challenge.ini` and
asserted on `AppSettings._qs.fileName()` before constructing a widget; the
working folder was a scratch tree under the session scratchpad. Mutation
testing was done on an rsync'd copy in the scratchpad, never in the repo.

STATUS: challenged
