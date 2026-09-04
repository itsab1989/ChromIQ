"""Every warning in the app wears ChromIQ's sign, not the platform's.

`ui/warning_sign.py` draws a warning triangle for Light, Dark and Neutral,
built from the same tokens as every other accent — Basti asked for it on
2026-09-03. It was then used in exactly ONE dialog. Every other warning in the
app still showed `QMessageBox.Icon.Warning`: on macOS the system caution
triangle with the application badged into its corner, at whatever size and hue
the OS picks, in a different visual language from every other mark here — and
carrying a hue that Neutral exists to remove.

51 sites across 13 files. That is not the kind of thing anyone re-checks by
hand, and a sign used in one place out of fifty-two is not a house style. So it
is checked here.

Both spellings are banned, because both produce the platform sign:

* ``setIcon(QMessageBox.Icon.Warning)`` — use ``set_warning_icon(box)``;
* ``QMessageBox.warning(...)`` — use ``ui.warning_sign.warn(...)``, which has
  the same signature shape and the same return, in the manner of
  ``ui.widgets.confirm`` for the question mark.

Information and Question are covered too, since Basti asked for ChromIQ signs
for both (2026-09-04): `set_information_icon` / `inform(...)` and
`set_question_icon` / `ask(...)`. The question mark had been REMOVED from this
app once already on his word — `ui.widgets.confirm` exists because of it — and
removing a sign is not the same as having one.

`Icon.Critical` is deliberately NOT covered: no ChromIQ sign has been drawn for
it, and banning a thing with no replacement only teaches people to skip the
check. When one is drawn, add it here.
"""
import re
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "ui"
#: the module that draws the sign is allowed to name what it replaces
_EXEMPT = {"warning_sign.py"}

_BANNED = (
    (re.compile(r"setIcon\(\s*QMessageBox\.Icon\.Warning\s*\)"),
     "setIcon(QMessageBox.Icon.Warning) — call set_warning_icon(box) instead"),
    (re.compile(r"\bQMessageBox\.warning\("),
     "QMessageBox.warning(...) — call ui.warning_sign.warn(...) instead"),
    (re.compile(r"setIcon\(\s*QMessageBox\.Icon\.Information\s*\)"),
     "setIcon(QMessageBox.Icon.Information) — call set_information_icon(box)"),
    (re.compile(r"\bQMessageBox\.information\("),
     "QMessageBox.information(...) — call ui.warning_sign.inform(...) instead"),
    (re.compile(r"setIcon\(\s*QMessageBox\.Icon\.Question\s*\)"),
     "setIcon(QMessageBox.Icon.Question) — call set_question_icon(box)"),
    (re.compile(r"\bQMessageBox\.question\("),
     "QMessageBox.question(...) — call ui.warning_sign.ask(...), or "
     "ui.widgets.confirm(...) for an everyday Yes/No that wants no sign"),
)


def _offences():
    out = []
    for path in sorted(UI.rglob("*.py")):
        if path.name in _EXEMPT:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            for pat, why in _BANNED:
                if pat.search(line):
                    out.append(f"{path.relative_to(UI.parent)}:{i}: {why}")
    return out


def test_every_sign_renders_in_every_appearance():
    """Three signs, three appearances, nine pixmaps — and `theme.by_mode` is
    written to fail loudly on an appearance it does not know, so a fourth one
    cannot quietly inherit Dark's amber."""
    from ui.warning_sign import (information_pixmap, question_pixmap,
                                 warning_pixmap)
    for mode in ("light", "dark", "neutral"):
        for name, fn in (("warning", warning_pixmap),
                         ("information", information_pixmap),
                         ("question", question_pixmap)):
            px = fn(48, mode, 2.0)
            assert not px.isNull(), f"{name} draws nothing in {mode}"
            assert px.devicePixelRatio() == 2.0, (
                f"{name}/{mode} lost its device pixel ratio — a warning that "
                f"looks soft is a warning that looks like a mistake")


def test_neutral_says_it_with_shape_not_hue():
    """Neutral's whole rule. All three signs share its one accent pairing
    there, so if the shapes were not doing the work, the three would be
    indistinguishable — which is exactly what this would catch."""
    from ui.warning_sign import (information_colours, question_colours,
                                 warning_colours)
    got = {warning_colours("neutral"), information_colours("neutral"),
           question_colours("neutral")}
    assert len(got) == 1, f"Neutral is using more than one pairing: {got}"
    for mode in ("light", "dark"):
        assert warning_colours(mode) != information_colours(mode), (
            f"{mode}: the warning and the notice share a colour — amber must "
            f"stay the only sign that means 'be careful'")


def test_no_dialog_uses_the_platform_warning_sign():
    bad = _offences()
    assert not bad, (
        f"{len(bad)} warning(s) still wearing the platform's sign:\n  "
        + "\n  ".join(bad))


#: one real example of each banned spelling, in the order of `_BANNED`
_EXAMPLES = (
    "        box.setIcon(QMessageBox.Icon.Warning)",
    '        QMessageBox.warning(self, tr("t"), tr("m"))',
    "        box.setIcon(QMessageBox.Icon.Information)",
    '        QMessageBox.information(self, tr("t"), tr("m"))',
    "        box.setIcon(QMessageBox.Icon.Question)",
    '        if QMessageBox.question(self, tr("t"), tr("m")) == yes:',
)


def test_the_check_can_actually_see_every_offence_it_bans():
    """A guard that cannot fail guards nothing. Each pattern is shown the exact
    line it exists to catch, and must catch that one and no other — so a
    pattern cannot be quietly widened until it matches everything, nor
    narrowed until it matches nothing."""
    assert len(_EXAMPLES) == len(_BANNED), (
        "a spelling was banned without an example proving the pattern sees it")
    for i, (pat, why) in enumerate(_BANNED):
        assert pat.search(_EXAMPLES[i]), (
            f"pattern {pat.pattern!r} does not match its own example "
            f"{_EXAMPLES[i]!r} — the ban is dead code ({why})")
        others = [j for j, ex in enumerate(_EXAMPLES) if j != i and pat.search(ex)]
        assert not others, (
            f"pattern {pat.pattern!r} also matches examples {others} — too "
            f"broad to report the right fix")


def test_a_clean_line_is_not_reported():
    """The replacements themselves must not trip the guard, or every fix would
    look like the fault it replaced."""
    clean = ("        set_warning_icon(box)",
             "        warn(self, tr('t'), tr('m'))",
             "        set_information_icon(box)",
             "        inform(self, tr('t'), tr('m'))",
             "        set_question_icon(box)",
             "        ask(self, tr('t'), tr('m'))",
             "        confirm(self, tr('t'), tr('m'), buttons)",
             "        box.setIcon(QMessageBox.Icon.NoIcon)")
    for line in clean:
        for pat, why in _BANNED:
            assert not pat.search(line), f"{line!r} wrongly flagged by {why}"


def test_the_replacement_exists_and_keeps_its_shape():
    """`warn` must stay a drop-in: same argument order as the static call it
    replaces, so a conversion can never silently reorder title and text."""
    import inspect
    from ui.warning_sign import set_warning_icon, warn
    names = list(inspect.signature(warn).parameters)
    assert names[:3] == ["parent", "title", "text"], names
    assert list(inspect.signature(set_warning_icon).parameters)[0] == "box"
