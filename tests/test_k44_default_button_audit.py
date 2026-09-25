"""K44 audit: which windows gain a filled main button, and which stay as
they were (Knut, #182 5833776276, 5833983335; Basti's rule, 2026-09-25).

Knut: *"there is no indication that the Create New button is the default
choice"*, and *"all windows and pop-up windows then should follow the same
standard."* Basti's rule for that standard, 2026-09-25:

1. a window or pop-up that ALREADY has one or more coloured buttons keeps them
   exactly as they are: no colour removed, nothing recoloured;
2. only a window or pop-up with NO coloured button gets its main button, the
   one Return presses, filled in the window's accent;
3. a destructive question whose safe default is Cancel keeps Cancel unfilled
   (listed for Knut).

`scripts/audit_default_buttons.py` builds each window the way the app does,
with the app's own event filters (so the default is settled and frozen as on
screen), in Light, Dark and Neutral, and reads every push button's painted
fill; a greyed button is also read once enabled. The already-coloured windows
are compared with the same audit run on the tree BEFORE K44
(`tests/data/k44_already_coloured_before.json`): every coloured button, its
fill and its fill once enabled, unchanged.

It runs in a subprocess because it sets the application's style sheet, which
a test in this process must never do.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODES = ("light", "dark", "neutral")
BEFORE = json.loads((ROOT / "tests" / "data" /
                     "k44_already_coloured_before.json").read_text("utf-8"))

#: Rule 2: no coloured button before K44; now the button Return presses is
#: filled (a tool's main action once its inputs are chosen, as it is greyed
#: until then).
FILLED_NOW = {
    "Preferences": "OK",
    "gear window": "OK",
    "report question (as built)": "Create New",
    "tool/average": "Average",
    "tool/merge": "Merge",
    "tool/ti1_to_i1p": "Convert",
    "tool/i1p_to_ti3": "Convert",
    "tool/i1p_to_ti1": "Convert",
    "tool/verify": "Verify",
    "tool/verify_profile": "Verify profile",
}
#: Rule 1: already coloured, unchanged (pinned against the tree before K44).
#: The four result windows are Basti's example, 2026-09-25: both stay
#: coloured. The device-link family's "frame" is its #primary greyed; enabled
#: it is the fill it always was.
ALREADY_COLOURED = tuple(BEFORE["light"])
#: Rule 3 and C9: no filled button, on purpose (listed for Knut).
NOTHING_FILLED = (
    "destructive question (Cancel default)",   # rule 3
    "tool/measurement_report", "Report limits",  # C9, Knut: Return opens nothing
    # K44: Qt made a file chooser the default here (the first button built);
    # Return now presses nothing, as in C9. No main action to fill.
    "tool/profile_info", "tool/ti3_info", "tool/softproof", "tool/translate",
)
#: Neutral's Restore Factory Defaults is an ACTION fill, left as it was
#: (rule 1); OK, the default, is ACTION-filled beside it. Put to Knut.
NEUTRAL_PREFERENCES_EXTRA = ["Restore Factory Defaults"]
#: Decision for beta 43, 2026-09-25: a DESTRUCTIVE action is never drawn
#: filled (B8-1156). And Knut, #182 5835722977 (beta 43): "I think Cancel as
#: the default is the safest." So in every destructive question of B8-1155's
#: list, Return presses Cancel (No, Keep using colprof), which is drawn plain.
#: {window: (the destructive action, the safe default)}.
DESTRUCTIVE_QUESTIONS = {
    "Delete Preset (Create Chart)": ("Delete", "Cancel"),
    "Delete Preset (Measure)": ("Delete", "Cancel"),
    "Delete Preset (Build Profile)": ("Delete", "Cancel"),
    "Delete Preset (Check & Refine)": ("Delete", "Cancel"),
    "Preset already exists": ("Overwrite", "Cancel"),
    "Restore Chart": ("Restore Chart", "Cancel"),
    "Overwrite patch set": ("Overwrite", "Cancel"),
    "New chart over a run's work": ("Generate the new chart", "Cancel"),
    "Measure anyway": ("Measure anyway", "Cancel"),
    "Build here anyway": ("Build here anyway", "Cancel"),
    "Clear & Print": ("Clear  Print", "Cancel"),  # "&&" draws one "&"
    "Profile engine opt-in": ("Enable the engine", "Keep using colprof"),
    "Different language": ("Yes", "No"),
}
#: Delete Preset in Measure, Build Profile and Check & Refine was a tinted
#: #primary before K44 and keeps that colour (Basti's rule wins, B8-1156):
#: Delete stays coloured, only the default moved to Cancel. Measure's is
#: pinned against the before file in ALREADY_COLOURED; these two were not in
#: the audit before, so their colour is pinned here.
COLOURED_DELETES = ("Delete Preset (Build Profile)",
                    "Delete Preset (Check & Refine)")
#: Every other destructive question: nothing coloured at all.
PLAIN_DESTRUCTIVE = tuple(n for n in DESTRUCTIVE_QUESTIONS
                          if n not in COLOURED_DELETES
                          and n not in ALREADY_COLOURED)


@pytest.fixture(scope="module")
def audit(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("k44audit")
    (tmp / "presets").mkdir()
    env = dict(os.environ)
    env.update(QT_QPA_PLATFORM="offscreen",
               CHROMIQ_SETTINGS_FILE=str(tmp / "s.ini"),
               CHROMIQ_PRESETS_DIR=str(tmp / "presets"),
               CHROMIQ_COMPLIANCE_ISO_FILE=str(
                   ROOT / "data" / "compliance_sets" / "iso12647.json"),
               CHROMIQ_TREE=str(ROOT))
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_default_buttons.py"),
         str(tmp / "out"), ",".join(MODES)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=600)
    line = next((ln for ln in proc.stdout.splitlines()
                 if ln.startswith("RESULT ")), None)
    assert line, ("the audit did not finish:\n"
                  f"{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
    return json.loads(line[len("RESULT "):])


def _filled(rows):
    return [r["text"] for r in rows if r.get("filled")]


def _coloured(rows):
    """Filled as shown, or filled once a greyed button is enabled."""
    return [r["text"] for r in rows
            if r.get("filled") or r.get("filled_when_enabled")]


def _default(rows):
    return [r for r in rows if r.get("default")]


def test_every_audited_window_is_in_exactly_one_class(audit):
    names = set(audit["light"])
    classes = [set(FILLED_NOW), set(ALREADY_COLOURED), set(NOTHING_FILLED),
               set(PLAIN_DESTRUCTIVE), set(COLOURED_DELETES)]
    assert sum(len(c) for c in classes) == len(set().union(*classes))
    assert set().union(*classes) | {"#primary beside another default"} \
        == names, names


@pytest.mark.parametrize("mode", MODES)
def test_a_window_without_colour_now_fills_the_button_return_presses(audit, mode):
    bad = []
    for name, want in FILLED_NOW.items():
        rows = audit[mode][name]
        d = _default(rows)
        if [r["text"] for r in d] != [want]:
            bad.append(f"{name}: default {[r['text'] for r in d]}, want {want!r}")
            continue
        extra = (NEUTRAL_PREFERENCES_EXTRA
                 if (mode, name) == ("neutral", "Preferences") else [])
        r = d[0]
        if r["enabled"]:
            if sorted(_filled(rows)) != sorted(extra + [want]):
                bad.append(f"{name}: filled {_filled(rows)}, want [{want!r}]")
        else:
            if _filled(rows) != extra:
                bad.append(f"{name}: filled {_filled(rows)} beside a greyed default")
            if not (r.get("filled_when_enabled") and r.get("default_when_enabled")):
                bad.append(f"{name}: {want!r} is not filled once enabled "
                           f"({r.get('fill_when_enabled')})")
    assert not bad, f"{mode}:\n" + "\n".join(bad)


@pytest.mark.parametrize("mode", MODES)
def test_a_window_already_coloured_is_exactly_as_before(audit, mode):
    """Rule 1: every coloured button, its fill as shown and once enabled, is
    what the tree before K44 painted; and no other button gained a fill."""
    bad = []
    for name in ALREADY_COLOURED:
        rows = audit[mode][name]
        now = [[r["text"], r["fill"], r.get("fill_when_enabled")]
               for r in rows if r.get("filled") or r.get("filled_when_enabled")]
        if now != BEFORE[mode][name]:
            bad.append(f"{name}:\n  before {BEFORE[mode][name]}\n  now    {now}")
    assert not bad, f"{mode}:\n" + "\n".join(bad)


@pytest.mark.parametrize("mode", MODES)
def test_every_window_has_a_coloured_button_but_the_listed_ones(audit, mode):
    bare = [n for n in (*FILLED_NOW, *ALREADY_COLOURED)
            if not _coloured(audit[mode][n])]
    assert not bare, f"{mode}: {bare}"
    filled = {n: _coloured(audit[mode][n]) for n in NOTHING_FILLED
              if _coloured(audit[mode][n])}
    assert not filled, f"{mode}: {filled}"


@pytest.mark.parametrize("mode", MODES)
def test_a_destructive_question_draws_its_safe_default_plain(audit, mode):
    rows = audit[mode]["destructive question (Cancel default)"]
    assert [r["text"] for r in _default(rows)] == ["Cancel"]
    assert _filled(rows) == [], rows


@pytest.mark.parametrize("mode", MODES)
def test_a_primary_window_gains_no_second_fill(audit, mode):
    rows = audit[mode]["#primary beside another default"]
    assert [r["text"] for r in _default(rows)] == ["Done"]
    assert _filled(rows) == ["Install"], rows


@pytest.mark.parametrize("mode", MODES)
def test_the_default_does_not_move_with_focus(audit, mode):
    """After the window settles, only the default is still autoDefault, so
    focusing another button cannot hand it the default (and the fill)."""
    bad = [(n, r["text"]) for n in FILLED_NOW for r in audit[mode][n]
           if r.get("auto") and not r.get("default")]
    assert not bad, f"{mode}: {bad}"


@pytest.mark.parametrize("mode", ("light", "dark"))
def test_the_fill_is_the_windows_own_accent(audit, mode):
    """The gear window belongs to Create Chart: its OK is filled in the tab's
    magenta (the per-tab sheet); the report question takes its window's
    green; Preferences, with no accent of its own, the application's."""
    from ui.styles import SPEC_GREEN, SPEC_MAGENTA
    from ui.theme import app_accent

    def fill(name, text):
        return next(r["fill"] for r in audit[mode][name] if r["text"] == text)
    assert fill("gear window", "OK").lower() == SPEC_MAGENTA.lower()
    assert fill("report question (as built)", "Create New").lower() == \
        SPEC_GREEN.lower()
    assert fill("Preferences", "OK").lower() == app_accent(mode).lower()


@pytest.mark.parametrize("mode", MODES)
def test_every_destructive_question_defaults_to_cancel(audit, mode):
    """Knut, #182 5835722977: "I think Cancel as the default is the safest."
    Return presses Cancel (No, Keep using colprof) in every destructive
    question, and that safe default is drawn plain, never as the main
    action."""
    bad = []
    for name, (action, safe) in DESTRUCTIVE_QUESTIONS.items():
        rows = audit[mode][name]
        if any("error" in r for r in rows):
            bad.append(f"{name}: {rows}")
            continue
        texts = [r["text"] for r in rows]
        if action not in texts or safe not in texts:
            bad.append(f"{name}: buttons {texts}, want {action!r} and {safe!r}")
        d = [r["text"] for r in _default(rows)]
        if d != [safe]:
            bad.append(f"{name}: Return presses {d}, want [{safe!r}]")
        if safe in _coloured(rows):
            bad.append(f"{name}: the safe default {safe!r} is filled")
    assert not bad, f"{mode}:\n" + "\n".join(bad)


@pytest.mark.parametrize("mode", MODES)
def test_a_destructive_action_is_never_newly_filled(audit, mode):
    """B8-1156: a destructive question with no coloured button before K44
    has none now; the coloured Delete Preset windows keep Delete, and only
    Delete, coloured."""
    bad = []
    for name in PLAIN_DESTRUCTIVE:
        if _coloured(audit[mode][name]):
            bad.append(f"{name}: filled {_coloured(audit[mode][name])}")
    for name in COLOURED_DELETES:
        if _coloured(audit[mode][name]) != ["Delete"]:
            bad.append(f"{name}: coloured {_coloured(audit[mode][name])}, "
                       "want ['Delete'] as before K44")
    assert not bad, f"{mode}:\n" + "\n".join(bad)
