"""Language support: catalog loading, fallback, overlay merge, hygiene.

The German catalog itself is also validated here (completeness against
the tr() call sites, placeholder integrity, parameters overlay coverage)
so a future string change that forgets the translation fails CI instead
of silently showing mixed-language UI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from core import i18n

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from i18n_extract import (UNTRANSLATED_ON_PURPOSE,  # noqa: E402
                          extract_keys, is_user_facing_text,
                          unwrapped_literals)


@pytest.fixture(autouse=True)
def _reset_language():
    # i18n state is module-global — never leak a language into other tests.
    yield
    i18n.set_language("en")


# ----------------------------------------------------------------------
# Core behaviour
# ----------------------------------------------------------------------

def test_english_is_passthrough():
    i18n.set_language("en")
    assert i18n.tr("Build Profile") == "Build Profile"
    assert i18n.current_language() == "en"


def test_german_translates_known_string():
    i18n.set_language("de")
    assert i18n.current_language() == "de"
    assert i18n.tr("Cancel") == "Abbrechen"


def test_unknown_string_falls_through_untranslated():
    i18n.set_language("de")
    assert i18n.tr("zz-not-a-real-source-string") == "zz-not-a-real-source-string"


def test_unknown_language_falls_back_to_english():
    i18n.set_language("xx")
    assert i18n.current_language() == "en"
    assert i18n.tr("Cancel") == "Cancel"


def test_available_languages_lists_english_and_german():
    langs = dict(i18n.available_languages())
    assert langs["en"] == "English"
    assert langs["de"] == "Deutsch"


# ----------------------------------------------------------------------
# German catalog hygiene
# ----------------------------------------------------------------------

def _catalog_codes() -> list[str]:
    return sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))


def _load_catalog(code: str) -> dict[str, str]:
    with open(ROOT / "data" / "i18n" / f"{code}.json", encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("@")}


@pytest.mark.parametrize("code", _catalog_codes())
def test_catalog_is_complete(code):
    missing = sorted(extract_keys() - set(_load_catalog(code)))
    assert not missing, f"[{code}] {len(missing)} untranslated, e.g. {missing[:5]}"


@pytest.mark.parametrize("code", _catalog_codes())
def test_catalog_has_no_stale_keys(code):
    stale = sorted(set(_load_catalog(code)) - extract_keys())
    assert not stale, f"[{code}] {len(stale)} stale keys, e.g. {stale[:5]}"


@pytest.mark.parametrize("code", _catalog_codes())
def test_placeholders_match_source(code):
    bad = i18n.check_placeholders(_load_catalog(code))
    assert not bad, f"[{code}] placeholder mismatch in: {bad[:5]}"


@pytest.mark.parametrize("code", _catalog_codes())
def test_short_labels_stay_compact(code):
    """Button/label-sized strings must not balloon in translation
    (clipping). Short English strings are the ones that end up on buttons
    and tab labels; allow modest growth plus a small constant."""
    offenders = []
    for src, dst in _load_catalog(code).items():
        if "\n" in src or len(src) > 24 or "{" in src:
            continue
        if len(dst) > int(len(src) * 1.6) + 6:
            offenders.append((src, dst))
    assert not offenders, f"[{code}] over-long short labels: {offenders}"


# ----------------------------------------------------------------------
# parameters.yaml overlay
# ----------------------------------------------------------------------

def _load_params() -> dict:
    with open(ROOT / "data" / "parameters.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["parameters"]


def _overlay_codes() -> list[str]:
    return sorted(p.suffixes[0].lstrip(".")
                  for p in (ROOT / "data" / "i18n").glob("parameters.*.yaml"))


@pytest.mark.parametrize("code", _overlay_codes())
def test_parameters_overlay_covers_every_parameter(code):
    overlay = yaml.safe_load(
        (ROOT / "data" / "i18n" / f"parameters.{code}.yaml").read_text(encoding="utf-8")
    )["parameters"]
    problems = []
    for tool, defs in _load_params().items():
        for p in defs:
            entry = overlay.get(tool, {}).get(p["flag"])
            if entry is None:
                problems.append(f"{tool} {p['flag']}: no overlay entry")
                continue
            for field in ("name", "tooltip_title", "tooltip_body"):
                if field in p and field not in entry:
                    problems.append(f"{tool} {p['flag']}: missing {field}")
            if "labels" in p and len(entry.get("labels", [])) != len(p["labels"]):
                problems.append(f"{tool} {p['flag']}: label count mismatch")
    assert not problems, problems


def test_translate_parameters_merges_german():
    i18n.set_language("de")
    params = i18n.translate_parameters(_load_params())
    d = next(p for p in params["targen"] if p["flag"] == "-d")
    assert d["name"] == "Gerätetyp"
    assert len(d["labels"]) == 16


def test_translate_parameters_is_noop_for_english():
    i18n.set_language("en")
    params = _load_params()
    translated = i18n.translate_parameters(params)
    d = next(p for p in translated["targen"] if p["flag"] == "-d")
    assert d["name"] == "Device Type"


def test_label_count_mismatch_keeps_english_labels(tmp_path, monkeypatch):
    """A stale overlay with the wrong number of labels must be ignored
    for that list — labels and choices may never desynchronise."""
    i18n.set_language("de")
    params = {"targen": [{"flag": "-d", "name": "Device Type",
                          "labels": ["a", "b", "c"]}]}
    monkeypatch.setattr(
        i18n, "_load_parameters_overlay",
        lambda code: {"targen": {"-d": {"name": "Gerätetyp",
                                        "labels": ["nur", "zwei"]}}},
    )
    out = i18n.translate_parameters(params)
    assert out["targen"][0]["name"] == "Gerätetyp"
    assert out["targen"][0]["labels"] == ["a", "b", "c"]


def test_qt_fallback_translates_norwegian_buttons(qapp):
    """PyQt6 ships no qtbase_nb.qm — the JSON fallback in data/i18n/qt/
    must still translate Qt's standard dialog buttons for Norwegian."""
    from PyQt6.QtCore import QCoreApplication
    i18n.set_language("no")
    i18n.install_qt_translator(qapp)
    try:
        assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Avbryt"
        assert QCoreApplication.translate("QPlatformTheme", "Close") == "Lukk"
    finally:
        if i18n._qt_translator is not None:
            qapp.removeTranslator(i18n._qt_translator)
            i18n._qt_translator = None


# ---- the message catalogue is translatable at all ------------------------
def test_the_message_catalogue_reaches_the_translations():
    """The §M catalogue hands its strings to ``tr()`` as ``tr(self.body)`` —
    an attribute, not a literal — so the extractor cannot find them by walking
    the source. It reads them from the module instead.

    Without that the whole catalogue silently dropped out: 4009 keys became
    3966, and every window in the Measurement Management model would have shown
    English in every language while every test stayed green.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from i18n_extract import extract_keys

    from workflow.measurement_messages import CATALOGUE

    keys = extract_keys()
    for mid, msg in sorted(CATALOGUE.items()):
        assert msg.title in keys, f"{mid}: headline is not translatable"
        assert msg.body in keys, f"{mid}: body is not translatable"
        if msg.body_one:
            assert msg.body_one in keys, f"{mid}: singular body is not translatable"


def test_the_catalogue_is_actually_translated_into_german():
    from core.i18n import tr, set_language
    from workflow.measurement_messages import CATALOGUE

    set_language("de")
    try:
        for mid, msg in sorted(CATALOGUE.items()):
            assert tr(msg.title) != msg.title, f"{mid}: headline still English"
    finally:
        set_language("en")


# ---------------------------------------------------------------------------
# The gap the other tests here CANNOT see
# ---------------------------------------------------------------------------
#
# Every check above starts from `extract_keys()`, which collects `tr()` calls.
# So "0 missing" has only ever meant "everything already wrapped has a
# translation" — and it said exactly that, out loud, while
# `ui/scan_grid_marquee.py` painted "Load a scan of the printed chart" as a
# bare literal into the scanner window's preview pane, in English, in all
# thirteen languages. A person reading a German window on a Windows 11 VM found
# it; this file was green throughout (2026-09-03, WINDOWS-VM-REPORT.md §D).
#
# The sweep that closes it lives in `scripts/i18n_extract.py` next to the
# extractor, because the two questions share one list of source files and one
# idea of what a user-facing string looks like.

def test_no_user_facing_literal_skips_tr():
    """Nothing puts a bare string literal on screen.

    A hit is one of two things and both need doing something about: a string
    that should be wrapped in `tr()`, or one that is deliberately the same in
    every language — in which case it goes in `UNTRANSLATED_ON_PURPOSE` **with
    the reason**, so the next person does not have to guess.
    """
    hits = unwrapped_literals()
    assert hits == [], (
        f"{len(hits)} user-facing literals never reach tr():\n"
        + "\n".join(f"    {f}:{ln}  {sink}(arg{i})  {text[:60]!r}"
                     for f, ln, sink, i, text in hits[:10]))


def test_the_literal_sweep_is_not_vacuous():
    """Guard the guard, twice over.

    A sweep that returns [] because it looks at nothing would pass the test
    above for ever, which is the exact failure the whole finding is about. So:
    the sinks must actually be recognised on a real call, and the sentence
    filter must accept a sentence while still rejecting a key.
    """
    import ast
    from i18n_extract import _sink_positions

    def positions(src):
        return _sink_positions(ast.parse(src, mode="eval").body)

    # The shape that shipped untranslated, and three others.
    assert positions('p.drawText(r, flag, "hello")') == (2,)
    assert positions('w.setText("hello")') == (0,)
    assert positions('QLabel("hello")') == (0,)
    assert positions('bar.set_label("hello", "sub")') == (0, 1)
    # …and a logger is not a text sink, or the sweep drowns in 380 log lines.
    assert positions('log.warning("could not read %s", p)') == ()

    assert is_user_facing_text("Load a scan of the printed chart")
    assert not is_user_facing_text("area_first")
    assert not is_user_facing_text("could not read %s")


def test_every_deliberate_exception_says_why():
    """An allow-list with no reasons is where unwrapped strings hide.

    Each entry must sit under a comment in the source. Checked by reading the
    file, because a set literal cannot carry its own annotations.
    """
    src = (ROOT / "scripts" / "i18n_extract.py").read_text(encoding="utf-8")
    body = src[src.index("UNTRANSLATED_ON_PURPOSE = {"):]
    body = body[:body.index("\n}")]
    assert len(UNTRANSLATED_ON_PURPOSE) >= 12, UNTRANSLATED_ON_PURPOSE
    # A comment line arms the next run of entries; a blank line disarms it. So
    # every group of exceptions has to be introduced, and appending one to the
    # end of the file without a word is what fails here.
    reason = False
    orphans = []
    for raw in body.splitlines()[1:]:
        ln = raw.strip()
        if not ln:
            reason = False
        elif ln.startswith("#"):
            reason = True
        elif not reason:
            orphans.append(ln)
    assert orphans == [], f"no reason given for: {orphans}"


# ---------------------------------------------------------------------------
# A value that is identical to its key is INVISIBLE to every other check here
# ---------------------------------------------------------------------------
#
# `test_catalog_is_complete` only asks whether the KEY exists, and the
# untranslated-budget test in `test_help_cards_untranslated_are_tracked.py`
# only counts strings of 25 characters or more. So a SHORT string whose value
# is still the English source is seen by nothing at all — which is how renaming
# the import button from "File it here" to "File it in Run 2" silently threw
# away twelve working translations and was reported as fixed after German alone
# had been restored (found by a challenge round, 2026-09-01).
#
# A value equal to its key is NOT always untranslated: "Adobe RGB (1998)",
# "Alt", " Hz" and "-{flag}" are the same word in German, and forbidding that
# outright would be wrong. So the NUMBER is tracked instead, and any rise has
# to be looked at.
#
# RAISE THESE DELIBERATELY, never to make a red run green. A rise means either
# a genuinely identical new string (fine, say so here) or a translation that
# has just been lost (not fine). Measured 2026-09-01, 4716 keys.
# 2026-09-01, +1 for the eleven: the guided-refinement window's "there is no
# chart to check this against" message is new (the no-chart guard used to
# protect one of the two roads into the import and now protects both). German
# carries it; the rest hold the English source under the beta rule. The two
# renamed file-name strings were CARRIED, not re-Englished, so they cost
# nothing here.
#
# 2026-09-01, +4 for the eleven and -1 for German: Check & Refine became a
# real import door, which is four new strings (the third answer, its log
# line and the two window bodies). German carries all four, which also
# cleared one older placeholder it shared wording with.
# 2026-09-02, +1 for German only: the Neutral appearance's combo entry. The
# German for the theme IS "Neutral" — it is the same word, in the same sense,
# and inventing a different one to satisfy a counter would be the wrong way
# round. Every other language names it differently (Neutro, Neutre, Nøytral,
# ニュートラル, 中性色, …), so no other count moves. The tooltip that lists the
# four appearances is translated in all twelve and is not identical anywhere.
# 2026-09-02, +8 for the eleven and +1 for German: the calibration-replacement
# wording Basti approved that day, after his option-3 ruling made the old
# sentence false. Eight keys, and only ONE of them moves German — "{folder}",
# which is a bare placeholder and is the same in every language. German carries
# a real translation of the other seven, which is why its SUBSTANTIAL count
# (the other budget, in test_help_cards_untranslated_are_tracked.py) does not
# move at all.
#
# THE ELEVEN DELIBERATELY DID NOT CARRY THEIR OLD TRANSLATIONS ACROSS, and that
# is the whole reason this rises by eight rather than by two. Five of the eight
# keys are rewordings of keys that already had translations — but they were
# reworded because the ruling made what they said UNTRUE ("moves the one you
# have" became "moves the calibration you have measured"). Carrying the old
# text across would have left eleven languages quietly asserting the thing the
# whole exercise existed to stop asserting, which is worse than English. The
# two keys that changed by PUNCTUATION only (an em dash became a comma) were
# carried, and cost nothing here.
# 2026-09-02, #159, +1 for German and +3 for the other eleven: Tools ▸ Read
# single patches can now read a CR30, and it brought nine strings with it.
# German carries all nine. The eleven carry eight — including the CR30's
# spot-reading instruction, whose SIBLINGS in the same function are translated
# everywhere, so leaving that one in English would have been conspicuous in a
# way the §M messages are not. Two are identical to their key:
#
#   •  "CR30 (ChnSpec)" is the product's name, identical in all twelve, German
#      included. That is German's +1.
#   •  M-INSTRUMENT-BUSY's body is PROPOSED wording (§M-PROPOSED). Translating
#      a sentence nobody has approved is the churn behind "translate before the
#      final, not during a beta", and the whole M-CR30-* family already sits in
#      English in these eleven for the same reason.
# 2026-09-03, review 3, +9 for the eleven and +0 for German: Tools ▸ Read
# single patches could throw a whole measuring session away in silence by two
# routes, and both now ask first (M-SPOT-CLEAR, M-SPOT-UNSAVED). Nine keys: two
# headlines, four bodies (each message states a count, so each has a singular
# and a plural body) and three labels — "Discard", "Undo clear" and the status
# line "Readings restored.". German carries all nine and moves by nothing,
# because none of them is the same word in German. The eleven hold the English
# source, for the reason already given for M-INSTRUMENT-BUSY one line above:
# the WORDING is §M-PROPOSED and nobody has approved it, so translating it now
# is the churn that "translate before the final, not during a beta" exists to
# avoid. When Basti approves the text, these nine are part of the GA pass.
# 2026-09-03, review 5, +8 for the eleven and +0 for German: Tools > Build
# profile with scanner or camera built a profile from data that was not the
# chart it thought it was, and said nothing (M-SCAN-REF-SHORT,
# M-SCAN-REF-DISAGREES, M-SCAN-CLIPPED, M-SCAN-PROFILE-ARCHIVED). Eight keys:
# four headlines, three bodies and the singular body of the one that states a
# count. German carries all eight, and moves by nothing, because none of them
# is the same wording in German. The eleven hold the English source, for the
# reason already given for M-INSTRUMENT-BUSY and the M-SPOT-* pair above: the
# WORDING is §M-PROPOSED and nobody has approved it, so translating it now is
# the churn that "translate before the final, not during a beta" exists to
# avoid. When Basti approves the text, these eight are part of the GA pass.
#
# 2026-09-03, Auto align: twelve more in the eleven. These ARE approved text --
# Basti approved the wording the same day it was written, so they are in §M and
# not in §M-PROPOSED -- but the beta rule is about the release, not about
# approval: translating eleven languages during a beta is the churn that
# "translate before the final, not during a beta" exists to avoid. German is
# carried in German, as always, because it is the language the owner reads.
#
# 2026-09-03, the Windows verification's finding D: +8 for the eleven and +0
# for German. NOTHING NEW IS ON SCREEN. These eight keys were ALREADY being
# shown, in English, in all thirteen languages, as bare literals that never
# reached `tr()` — the preview placeholder "Load a scan of the printed chart"
# that a German user read on the Windows VM, the six progress labels on the
# Build Profile tab, and the two "[ERROR] …" lines under Create/Apply
# Calibration. Wrapping them changes only whether they CAN be translated.
# German now carries all eight, which is a strict gain; the eleven hold the
# English source they were already displaying, so the pixels do not move and
# the count rises by exactly the eight that became visible to this counter.
# `scripts/i18n_extract.py --unwrapped` is the guard that stops the next one,
# and `tests/test_i18n.py::test_no_user_facing_literal_skips_tr` runs it.
#: 2026-09-04, beta 8: +7 in each of the twelve, and 0 in German. B8-01 and
#: B8-03 added three §M-PROPOSED messages (M-SCAN-DARK,
#: M-SCAN-FIT-UNSUPPORTED, M-SCAN-SELFCHECK-UNUSABLE) — a title and a body
#: each, plus a singular body for the second, which is the shape both of the
#: degenerate references reduce to. German is translated; the other twelve
#: carry the English source, the same way every review-5 M-SCAN-* string does,
#: because the wording is awaiting review and translating it before it is
#: approved translates a draft.
#: 2026-09-04, beta 8, the photograph path: +13 in each of the eleven and 0 in
#: German. Five §M-PROPOSED messages (M-SCAN-CONVERTED and the four
#: M-SCAN-FIT-*) plus the new button's label, its tooltip and its busy note.
#: German is translated; the eleven carry the English source, because the
#: wording is awaiting review and translating a draft is exactly the churn the
#: beta rule exists to avoid.
# 2026-09-04, B8-02: one §M-PROPOSED message, M-SCAN-ALIGN-NOT-SEATED —
# the refusal for a photograph taken off square, whose grid would read part
# of the neighbouring patch. German is translated; the eleven carry the
# English source, because the wording is awaiting review.
# +11 each, 2026-09-04, beta 8 items B8-14, B8-30, B8-31 and B8-32 (AGENT-M):
# two §M-PROPOSED messages and their headlines (M-SCAN-SHOT-EMPTY,
# M-SCAN-TARGET-CHANGED), the corrected "Indicator font" tooltip and the note
# saying which control in "Strip && row labels" reaches which label, the
# "Reading options" and "Save as Defaults" tooltips rewritten around a removed
# control and three newly-saved ones, an empty averaging slot's entry in the
# shot combo, the margin-raise warning's second form (the one that does not
# advise reducing "Clip" in a state where Clip cannot move anything) and the
# margin inspector's new "Text and label notes" box. German is translated for
# all eleven; the other eleven languages carry the English source, which is the
# beta convention. FOUR keys also went away with the "Correct perspective"
# control -- all four were already translated in every language, so they cost
# nothing here. These are each language's ACTUAL count.
#: 2026-09-04, B8-42: minus 10 in every catalogue but German. Merging "Auto
#: align" and "Fit to the patches" into one button retired fourteen strings —
#: the button's label, its tooltip, its busy note, the old Auto align tooltip
#: and the eight halves of the four messages that went with it — and added
#: three: the new Auto align tooltip and the two rewritten refusal bodies.
#: Thirteen of the fourteen carried the English source in these eleven
#: catalogues, and the fourteenth ("Fit to the patches") was translated
#: everywhere, so the arithmetic is -13 + 3. German is translated and does not
#: move.
# +1 each in the eleven, 0 in German, 2026-09-04, beta 8 item B8-21 §4
# (AGENT-R): the "Strip && row labels" frame stopped explaining itself in a
# paragraph and started explaining itself by its SHAPE. ONE key went away --
# the forty-word reach note added under B8-14 the day before, translated in
# German and English everywhere else -- and TWO arrived, the sub-frame titles
# "Strip letters and row numbers" and "Strip letters only". Net -1 +2 = +1 for
# the eleven; German is translated for both, so it does not move. The titles
# are user-facing wording awaiting Basti's ruling (§M-PROPOSED), which is why
# the eleven carry the English source. These are each language's ACTUAL count.
#: 2026-09-04, AGENT-S (the buttons under the scanner preview): +2 in every
#: catalogue but German. "⤢ Pop out for a bigger view" was the longest label in
#: the window and cost the button block a whole row of its own; it is now
#: "⤢ Pop out", with the four dropped words moved into a tooltip. So ONE key
#: went away — translated in all twelve, so it costs nothing here — and TWO
#: arrived: the short label and its tooltip. Both are new user-facing wording
#: APPROVED by Basti, 2026-09-04 ("it is ok") — see §M-PROPOSED, "Button
#: labels … Confirmed behaviour". The eleven still carry the English source, but
#: for the ordinary beta reason (translation happens before a final, not during
#: a beta), NOT because anything is still pending. German is translated for both
#: and does not move. These are each language's ACTUAL count.
# +1 each in the eleven, 0 in German, 2026-09-04, beta 8 item B8-52 (AGENT-T):
# the Create Chart panel notices left their sections for the ⓘ they belong to
# (Basti: *"the info text in create chart tab that is directly inside the
# sections (even that that you made collapsible) - i want that gone. You can
# fit it inside of a tooltip where it fits but not directly inside a
# section"*). Three keys went and two arrived. "Text and label notes" — the
# collapsible box's title, English in these eleven — simply went, -1. The
# other two are RENAMES forced by the move, because both sentences pointed at
# a place that no longer exists: "…tick at least one edge ABOVE" was true of a
# label under the two tick boxes and false of an ⓘ on the row above them, and
# the "Show markers for" help ended "ChromIQ says so UNDER THE BOXES". Both
# were translated in these eleven and both arrive carrying the English source,
# so that pair is +2. Net -1 +2 = +1. German is translated for both and does
# not move. These are each language's ACTUAL count.
#   …and +1 more on top of that, same item, same day: the "Text distance from
#   edge" help itself ended *"the text overflows toward this line and a margin
#   warning is shown"*. After the move nothing is SHOWN — the warning is on the
#   ⓘ beside the measured margins — so that sentence had to be rewritten too,
#   which retires a key translated in all twelve and adds one carrying the
#   English source in the eleven. So the item's total is +2 in the eleven and
#   0 in German.
#: 2026-09-04, the #182 spin-off (AGENT-AE): +6 in each of the eleven, 0 in
#: German. Two are M-REPORT-NOT-SAVED's headline and body — the dated report
#: ChromIQ saves after every measurement could fail and say nothing on screen,
#: while a report that SUCCEEDED announced itself in the measurement log, so
#: the two outcomes looked identical. One is the "[Report] Technical detail:"
#: line that carries the exception OUT of the message: Basti's standing rule is
#: "friendly, extensive, easy to understand and correct", and an errno with a
#: path in it is none of the first three. The other three are the Measurement
#: Report window's provenance lines — the sentence under a run's accuracy table
#: saying its verdict was recorded when the report was saved (and that the spin
#: boxes no longer move it), the sentence for a report saved before ChromIQ
#: recorded one, and the footnote under Report Results saying that a column
#: reading "not recorded" is not a fault. German is translated for all six and
#: moves by nothing, because none of them is the same wording in German. The
#: eleven carry the English source: M-REPORT-NOT-SAVED is §M-PROPOSED, and the
#: rest is new wording in a beta, which is exactly what "translate before the
#: final, not during a beta" covers. These are each language's ACTUAL count.
# +22 each in the eleven, 0 in German, 2026-09-04, beta 8 item B8-19 / B8-54
# (AGENT-AF): the Profile type help in Tools ▸ Build profile with scanner or
# camera. The one key that went away said the two cLUTs were interchangeable and
# that Lab "sometimes gives slightly smoother neutrals" — nothing measured that,
# and B8-19 measured the opposite kind of difference (a Lab cLUT cannot encode
# anything above its chart's white). It was translated in all twelve, so
# retiring it costs nothing here. In its place the help is built from paragraphs
# and is MODE-AWARE, because a scanner input profile and a printer output
# profile want different types and this window already marks a different
# "(default)" for each: 21 paragraph/label keys plus the combo's new
# "(recommended cLUT)" marker and three live notes — 22 arriving, each carrying
# the English source in the eleven for the ordinary beta reason (translation
# happens before a final, not during a beta) AND because the wording is still
# PROPOSED. German is translated for all 22 and does not move. See §M-PROPOSED,
# "⏳ Awaiting confirmation — Profile type help text". These are each language's
# ACTUAL count.
# +4 each in the eleven, 0 in German, 2026-09-05 (AGENT BJ): the white-point
# help in Tools ▸ Build profile with scanner or camera ▸ Advanced. The sentence
# that went away — "1.00 makes no change" — was FALSE: ArgyllCMS sets
# `autowpsc = 1` before it reads the number (`colprof.c:494`) and defaults the
# scale to 1.0 anyway (`xfit.c:2753`), so `-u 1` builds the same profile as a
# bare `-u`. Two keys are the corrected tooltip bodies, two are the combo label
# and tip title, which stopped saying "(-u)" — the list had TWO different
# entries under that one flag. German is translated for all four and does not
# move. The eleven carry the English source: new wording in a beta, and it is
# PROPOSED wording besides. These are each language's ACTUAL count.
# +10 each in the eleven, 0 in German, 2026-09-05 (AGENT BJ, second commit):
# the -ua help. Eleven keys arrive and five retire — the printer-mode help, the
# scanner-profile help, the "Which source?" help, the white-point help, the
# "Restrict" help, three new help-card steps, the standard-mode explanation of
# why "Profile my printer from this scan" is not offered there, and the visible
# line in the printer box. Knut, beta 9: *"this is really an important detail
# that the workflow steps in help cards and help descriptions must be clear
# about"* — he wrote his own colprof command with -ua in it and still had to
# relearn why. German is translated for all eleven and does not move. The
# eleven catalogues carry the English source: new wording in a beta, and
# PROPOSED wording besides. These are each language's ACTUAL count.
# -1 in each of the eleven and -35 in German, 2026-09-05 (AGENT BP). THE
# BUDGET MOVES DOWN, WHICH IS THE ONLY DIRECTION IT MAY MOVE.
#
# The eleven lose ONE key: "Not now" (W-06). It is the DECLINE button of the
# driver-consent window "Before ChromIQ starts", the one window in ChromIQ
# whose entire purpose is informed consent before an elevated driver install,
# and it read the English "Not now" in every language but German. This is a
# deliberate exception to "translate before the final, not during a beta" and
# it is worth stating why, so the next agent does not read it as a licence:
# the key is NOT new beta wording. `ui/cr30_calibration.py` has shipped a
# button carrying it since the CR30 work, German has carried "Jetzt nicht"
# throughout, and §M's entry for it says in as many words "zero new
# translation keys". Nothing about it is a draft. What the beta rule protects
# against is re-translating wording that is still moving; it was never meant
# to leave the word "no" in English on a consent button.
#
# German loses THIRTY-FIVE, and that is the more interesting half. German is
# recorded here at 152 and ACTUALLY sat at 139, so the ratchet had thirteen of
# slack and could not fire for German at all — and inside those 139 were 22
# strings of real German-facing PROSE still in English, every one of them from
# the CR30 sprint of 2026-08-28 → 2026-09-01 (`22f005aa`, `8ecac82f`,
# `e7eb81f9`, `18867d76`, `1bbc2211`). Among them: "ChromIQ has lost contact
# with your CR30 while measuring patch {loc}", both windows of the white and
# dark calibration, the magnet give-up window, and the two longest pieces of
# Chart Layout help in the app. The standing convention every note above this
# one repeats is that German is carried in German BECAUSE IT IS THE LANGUAGE
# THE OWNER READS; those 22 are that convention having quietly slipped, not an
# instance of it. All 22 are now German. The remaining four "prose-shaped"
# identity values in German are file-path and format templates
# ("reports/Verify_Reference_N_{name}.txt", "{name}.ti1 / {name}.ti2") and are
# correctly English. 139 - 22 = 117.
#
# The 262 keys that are identity in ALL ELEVEN while German has a translation
# are NOT touched and are NOT a leak: they are the tracked deferral every note
# above accounts for, most of them §M-PROPOSED wording nobody has ruled on. A
# ranked list of them, by the harm of reading them in English, is in the
# AGENT BP report. These are each language's ACTUAL count.
# +4 each in the eleven, 0 in German, 2026-09-05 (AGENT BQ): the scanner
# white-point default moved to "Scale white to a perfect white surface" (-u -R).
# Eight keys arrive and five retire — the two shortened combo labels, the new
# one, the three help bodies that had to move with the default (white-point
# handling, the manual scale, and "Restrict white, black and primaries"), the
# profile-type help's Lab-cLUT bullet, whose ceiling is a different height under
# the new default, and the two halves of M-SCAN-WP-DEFAULT, the one-time note
# saying the default moved and took the user's remembered setting with it.
# German is translated for all eight and does not move. The eleven catalogues
# carry the English source: new wording in a beta, and PROPOSED wording besides.
# Moved again on 2026-09-06 by Knut's beta 10 batch for this same window:
# the usage-scenario control (heading, three labels, three glosses, the
# divergence line, the greyed printer reason and its ⓘ), the two
# white-point "(best for …)" markers that replaced the single
# "(default)" one, the line that says what the patch count set up, the
# note under the locked -R switch, and the six help bodies that had to be
# rewritten with them. 26 keys in, 9 stale keys out. German is translated
# for all 26 and does not move; the eleven others carry the English
# source, so each of them gains 17.
# …and again the same day, by the review of that work (CL-1, CL-6): the
# line that says a saved bucket is being left alone rather than blaming
# the user for ChromIQ's own choice, in its two forms, and the rewritten
# Lab-table note, which had gone on describing the world before B8-75
# moved the white-point default. Three keys in, one out; German
# translated, the eleven +2 each.
# …and once more on 2026-09-06 (AGENT CR), bringing the scanner and camera
# HELP up to the usage scenarios those two entries added. Both printable help
# cards were rewritten around the three scenarios, with their reasoning moved
# out of the numbered steps into the new note register; the window's own ⓘ was
# corrected, having said for fifty-five days that the source choice was "at the
# top of the window" (it is the scenario radios) and that the build button
# reads "Build profile with scanner or camera" (it reads "Build printer
# profile" in printer mode); and three more bodies gained a sentence naming the
# scenarios. 50 keys in, 20 stale out. German is translated for all 50 and does
# not move; the eleven others carry the English source under the beta rule, so
# each of them gains 43.
# …and again on 2026-09-06, by the colprof algorithm fix. Five of the
# Build Profile Algorithm list's eight entries could not build a printer
# profile at all and a sixth built the same file as the entry above it, so
# the list is now the two that work, in both windows: the two Algorithm
# tooltips are rewritten, the Profile type ⓘ says why the printer side
# offers two and the scanner side four, the Quality note stops claiming it
# applies to cLUTs only, and three lines say out loud when a stored
# algorithm had to be moved. 8 keys in, 4 stale keys out. German is
# translated for all 8 and does not move; the eleven others carry the
# English source, and each gains 5 (three of the four keys that left were
# English placeholders there too).
# These are each language's ACTUAL count, re-measured on the merged tree:
# both changes above landed together, so neither branch's figure was right
# on its own.
# RE-MEASURED 2026-09-07, after the English-source fixes for 4.2.0: every
# one of these twelve numbers is UNCHANGED. Fourteen English keys were
# re-spelled that day (comma splices, quoted control names, `dark
# calibration`, `[WARN]`, `Unexpected Colour Response`), and a re-key is
# the one move that loses twelve translations at once. The table not
# moving is the proof that every one of them was carried across rather
# than left to fall back to English.
# …and again on 2026-09-07, by the usage-scenario glosses (B8-101). Basti:
# *"the help text for the usage scenarios under the 3 radio options is very
# extensive (which is good) but it uses a lot of space there. I'd rather have
# the detailed info put inside the tooltip."* Each gloss is now one line and
# the full text moved into the window's own ⓘ. The MOVE cost nothing: the tip
# body is composed from the same `tr()` literals the glosses carried, so all
# twelve translations came across and no key went stale. 4 keys in (three
# one-line glosses and the heading above them in the tip), 0 out. German is
# translated for all 4 and does not move; the eleven others carry the English
# source under the beta rule, so each of them gains 4.
# 2026-09-08, #182: the Measurement Report is judged against LIMIT SETS. 137
# keys in (the report window's Judged-against row, its five verdict words and
# their definitions, the Report limits window, the Preferences frame, the
# limit-set table's row and set labels), 15 out (the two Pass-threshold spin
# boxes and their help). German is translated for all 137; it moves by exactly
# the FIVE verdict words PASS / FAIL / COND / INFO / N-A, which Knut ruled as
# English tokens (K-f) and which read the same in German. The eleven others
# carry the English source under the beta rule, so each gains 137.
# Same day, after the adversarial review: 17 sentences added (the Overall
# summaries, the two write-failure windows, the reworded provenance and COND
# texts) and six long texts re-keyed after a rewording; German carries all of
# them, the eleven others gain the difference.
# 2026-09-10, #182: REFERENCE sets, which are a different object from the limit
# sets above. A limit set says how close is close enough; a reference set says
# what colour a patch was supposed to be, and eleven Fogra printing conditions
# are now bundled (`data/reference_sets/`, `workflow/reference_sets.py`).
# 37 keys in: six group labels, eleven set labels, eleven blurbs, four refusal
# sentences, the Fogra credit line, three coverage sentences and the display
# label. 0 out. German is translated for 36 of the 37 and moves by exactly ONE,
# `{label} ({name})`, which is punctuation in every language. The eleven others
# carry the English source under the beta rule; two of the 37 keys ("Magazine",
# "Metal") were already in those catalogues and translated, so each gains 35.
# …and again on 2026-09-10, by Knut's ruling that text on any of the four sides
# is never dropped. The two overflow warnings that existed (top strip labels,
# bottom sheet text) were rewritten to name the exact boxes that fix the
# collision, and more joined them: two for the chart notes down the right edge
# (the lever differs when a clip border sits on that edge), two for the clip
# border's own content on either side, a two-line variant of the bottom one
# because "(s)" is not written in this project's text, and the reworded help
# line above them. **8 keys in, 3 stale out.** German is translated for all 8
# and does not move; the eleven others carry the English source under the beta
# rule, and all three that left were translated in every one of them, so each
# gains exactly 8.
#
# THE FIRST DRAFT OF THIS NOTE SAID 7 IN AND 2 OUT while raising every ceiling
# by 8, and it is worth saying why that matters more than an arithmetic slip.
# This dict is the one place in the suite where a check is loosened on purpose,
# so the note beside it is the whole audit trail. A note that does not match its
# own numbers is how the next person raises a ceiling without noticing they are
# the second to do it. Counted from the catalogues, not from memory:
# `set(after) - set(before)` is 8 and `set(before) - set(after)` is 3, in every
# one of the twelve.
# 2026-09-11: the 4.2.4 line merged into this branch. THE CATALOGUES WERE NOT
# UNIONED, and that is the point worth recording. A union cannot tell "they
# added this key" from "we deleted it", so it silently resurrected 22 strings
# the #182 report rework had removed, in ten languages. The catalogues follow
# the MERGED SOURCE instead: `scripts/i18n_extract.py --stale <code>` names
# every key the merged code no longer uses, and those were pruned. The ceilings
# below did not move, which is the check that the merge changed no translation.
# 2026-09-11, Knut's "several report types per run": every language gains one,
# German included, for "{type} ({count})". That string is two placeholders and
# a bracket; it is the same in every language that uses round brackets, and the
# two that do not (ja, zh_CN) were given their own full-width form and are NOT
# among the identical ones. An identity, not a missing translation.
# 2026-09-11, #182 F3, fr 314 -> 315: the French for "Licences" is
# "Licences". An identical value here means "untranslated" for every string
# but the handful that are genuinely the same word, and this is one of them.
# 2026-09-11, #182 F7. The seven strings the Report limits window now uses to
# name what it could not read in a licence holder's own limits file were
# translated into all twelve rather than carried in English under the beta
# rule, so the ceilings came DOWN by two instead of up by five: two English
# placeholders from an earlier round were replaced in the same pass.
# 2026-09-11, #182: the one-page colour summary is about ONE sheet, so the tick
# box that widens every other report to the whole history is disabled while T1
# is chosen, and its tooltip says why. German is translated; the other eleven
# carry the English sentence under the beta rule, so every ceiling but de goes
# up by exactly one. Counted, not assumed: `set(after) - set(before)` is that
# one string in each of the eleven, and `set(before) - set(after)` is empty.
#
# …and again on 2026-09-11, by Knut's ruling that shrinking text has a floor
# (#182). **9 keys in, 6 stale out**, counted with `set(after) - set(before)`
# and `set(before) - set(after)` on each catalogue rather than from memory:
# four help texts (Chart Notes, "Stamp settings used on the chart", the
# Sheet-text Font/Size row, the Clip-border Font/Size row), three chart-note
# warnings where there were two, and the clip-border text's own warning in a
# singular and a plural form. **EVERY TWELVE IS TRANSLATED, so every number
# below is UNCHANGED: 0 in, 0 out, in all twelve.**
#
# THE BETA RULE DOES NOT REACH THESE NINE, and that was found the hard way:
# each of them quotes a ChromIQ control in curly quotes, and
# `test_a_quoted_control_names_the_control_the_reader_has.py` refuses a
# translation that sends a Spanish reader looking for a control called “Clip”
# when the window says «Pinza». English placeholders in the eleven raised 238
# offences there. A string that quotes a control is translated or it is not
# added.
#
# **AND THE TABLE IS NOW EACH LANGUAGE'S ACTUAL COUNT, which it had stopped
# being.** It stood eight above every one of them (es was recorded at 112 and
# was 104), and eight units of slack is eight free regressions per language.
# Re-measured here, on the catalogues: de 117, es 104, fr 125, it 115, ja 91,
# nl 132, no 116, pl 108, pt 106, ru 79, sv 118, zh_CN 85.
# 2026-09-11, THE MERGE OF THE TWO ROUNDS ABOVE. The report round and
# the text-fitting round each moved this table on their own base, so the
# two tables disagreed and neither described the merged catalogues. The
# numbers below are MEASURED on the merged tree, not reconciled from the
# two sides: a ceiling carried across a merge is a ceiling nobody has
# counted, and a ceiling above the truth admits the next regression for
# free.
#
# RE-MEASURED 2026-09-11, #182 items A/B and K7: NOT RAISED, because it did not
# need to be. Three keys arrive (the rewritten hexagon note, the rewritten
# Custom-paper naming note, the new margin-inspector "Patch width" note) and two
# go stale, so the eleven non-German catalogues each gain 3 English echoes and
# German gains 0. Counted from the catalogues on the tree this commit leaves
# behind: de 117, es 107, fr 128, it 118, ja 94, nl 135, no 119, pl 111, pt 109,
# ru 82, sv 121, zh_CN 88 -- every one at or under the ceiling already recorded
# here, German exactly at 117 and the rest with room to spare. Left alone on
# purpose: a raised budget admits the next regression for free.
# 2026-09-11, THE SECOND MERGE. Three rounds have now moved this table,
# each on its own base. Re-measured on the merged catalogues rather than
# reconciled: a number carried across a merge is a number nobody counted.
# 2026-09-11, the from-profile-gamut round. The grey line under "Colours to
# test" used to say the in-gamut count "runs the first time a profile is
# available" -- in a label that is only drawn when a profile IS available, so
# it named a cause that cannot be the one. It becomes two sentences that say
# what actually happened, one per case. **2 keys in, 1 stale out, counted with
# `set(after) - set(before)` and `set(before) - set(after)` on each catalogue
# and not from memory.** German is translated, so de does not move at all
# (124, unchanged); the eleven others carry the English sentences under the
# beta rule and each gains exactly 2 -- the stale key they lost was itself
# translated in every one of the twelve, so it was never in these counts.
# Re-measured on the catalogues this commit leaves behind, not derived: de 124,
# es 300, fr 322, it 311, ja 286, nl 327, no 312, pl 304, pt 302, ru 275,
# sv 313, zh_CN 280.
# 2026-09-12, MERGED with the sheet-text and demo-pack rounds and measured
# AGAIN on the merged catalogues. Every round counted on its own base, so no
# round's table described this tree. Counted with the same expression the
# test below uses, never adjusted upward.
_IDENTICAL_TO_KEY = {
    # RE-MEASURED 2026-09-23, round 3B's text findings: three several-places
    # tooltips reworded (one entry at a time), the Report type help and the
    # Preferences default text corrected, "{type} ({count})" became
    # "{type}: {count}", and one key added ("No measurement is loaded yet.").
    # German by hand, so it does not move; the placeholders follow their
    # renamed keys, so only the new key moves the others. COUNTED off the
    # tree, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-22, round 2B's text findings on K13/K14: the
    # several-runs tooltips, the Report type help, the Preferences default
    # text and the coverage sentences reworded, one no-run tooltip added.
    # German by hand, so it does not move; `uk` does not move because the
    # departing keys were English echoes in it already; the eleven others rise
    # by exactly 2 in both ledgers. COUNTED off the tree, BOTH ledgers in the
    # same commit.
    # RE-MEASURED 2026-09-22, K10 (Knut on beta 34: the one-page summary's
    # numbers carried no unit). Two keys in ("Average difference {v} ΔE00",
    # "Largest {v} ΔE00") and their two unit-less predecessors out. German by
    # hand, so it does not move. The identical-to-key count rises by 2 in the
    # eleven languages that had translated the old keys and not at all in
    # `uk`, which had not; the echo budget rises by 1 everywhere, because the
    # "Largest" key is too short for that detector. COUNTED off the tree,
    # BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-22, K4 (Knut on beta 34: Generate on a selected
    # report with nothing changed made a new report without asking). Two keys
    # in, none out: M-REPORT-UNCHANGED-UPDATE-OR-NEW's headline and body.
    # German by hand, so it does not move; the twelve others rise by exactly
    # 2. COUNTED off the tree, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-22, K14 (Knut on beta 34: the Report Scope count
    # belongs to the run type and the listed measurements). Five keys in (the
    # coverage sentence for a profiling document, one project or several, and
    # for a verification document, this run / these runs / several projects)
    # and none out. German is translated by hand for all five AND for the four
    # older coverage sentences round B found still in English, so German FALLS
    # by 4; the twelve others rise by exactly 5. COUNTED off the tree, BOTH
    # ledgers in the same commit.
    # RE-MEASURED 2026-09-22, round B's text findings: German loses one English
    # echo (the N-A note, translated by hand) and gains none, because the
    # three rewritten "more than one profile run" tooltips and the extended
    # Report type help are translated by hand in the same change; the twelve
    # others do not move, because the departing keys were English echoes in
    # them already. COUNTED off the tree, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-22, K13 (Knut on beta 34: which report types each
    # run type may have). Four keys in (the two greyed-entry tooltips, the
    # Report type help paragraph saying which types are available when, and
    # the Preferences "Report type, default" text with its new paragraph) and
    # one out (that text's previous version, translated in every language).
    # German by hand, so it does not move; all twelve others, uk included,
    # rise by exactly 3. COUNTED off the tree, BOTH ledgers in one commit.
    # RE-MEASURED 2026-09-22, K17 (Knut on beta 34: two runs ticked and the
    # report type could not be chosen). One key out (the type pulldown's
    # "Several measurement runs are loaded" tooltip, retired with the grey)
    # and one in (Generate's reason with several runs). German by hand, so it
    # does not move; `uk` does not move because the departing key was already
    # English there; the eleven others rise by exactly 1. COUNTED off the
    # tree with each file's own helper, BOTH ledgers in the same commit.
    # RE-MEASURED a third time on 2026-09-22, after adversary round 40b drove
    # both new messages in the real app and found the first one false in most
    # states. The texts were rewritten, so six keys changed: German is written
    # by hand and stays at its number, which is how a hand translation that
    # quietly fell back to English would show up here. Counted off the tree
    # with this file's own helper, BOTH ledgers in the same commit.
    # RE-MEASURED AGAIN the same day, when `STANDARD_CAVEAT` was split into
    # two keys. The one-page summary branches away before the block that
    # prints the caveat, so T1 needed it too, and measured on that page's own
    # A4 layout the whole caveat left 52 px spare against the 60 px its
    # headroom guard requires. The second half leaves 82, so the note is
    # translated in halves and joined where there is room for both. One key
    # out, two in; German written by hand for both and unmoved.
    # RE-MEASURED 2026-09-22, the ISO COND cap round, and **BOTH LEDGERS IN
    # THE SAME COMMIT**: its twin is `_BUDGET` in
    # `tests/test_help_cards_untranslated_are_tracked.py`. Updating one of
    # them is not updating the ledgers, which was learned the hard way on
    # 2026-09-22 itself: three gate runs came back red identically, twelve
    # failures each, because the other ledger had been missed.
    #
    # The change: four keys out (the report guide's COND bullet, its standards
    # paragraph, the Getting Started glossary's Overall entry, and
    # STANDARD_CAVEAT) and eight in (their replacements, plus a title and a
    # body each for M-VERIFY-UNCHECKED-METRICS and
    # M-REPORT-PATCH-COUNTS-DIFFER). German is written by hand and does not
    # move at all, which is how a hand translation that quietly fell back to
    # the English would show up here.
    #
    # Ukrainian rises by 4 and the other eleven by 5, measured per language:
    # all four departing keys were untranslated in `uk`, and one of the four
    # was genuinely translated in the others.
    # RE-MEASURED 2026-09-22, for Knut's ruling that the unchecked values
    # shall be listed. The ISO summary sentence is now three sentences, one
    # per case, because the promise was unconditional and a column with
    # nothing unchecked also said the unchecked values were listed below.
    # German by hand; the twelve others carry the English under the beta
    # rule. COUNTED off the tree, BOTH ledgers this time.

    # RE-MEASURED 2026-09-22 again, for Knut's four faults in the verification
    # pre-flight. The biggest is a fault of LOGIC rather than wording: the
    # window named "this report type and limit set" at a moment when the user
    # has opened no report and chosen neither, so it now asks the union over
    # every built type and every selectable set. Measured on his chart: one
    # pair asks 7 rows, the union asks 16. Four keys in, two stale out; German
    # written by hand, the twelve others carry the English source under the
    # beta rule, so each rises by exactly TWO. COUNTED off the catalogues.

    # RE-MEASURED 2026-09-22, Knut's beta 32 batch: the Report limits button is
    # renamed "Restore defaults" on his word, and the Measurement Report now
    # says which metrics a report type actually judges, because Grey and tone
    # check showed three rows while the set had thresholds for far more and
    # nothing said that was deliberate. Three keys in, two stale out. German is
    # written by hand and does not move; the twelve others carry the English
    # source under the rule that they are translated in one pass before a
    # final, not during a beta, so each rises by exactly ONE. COUNTED off the
    # catalogues on disk.

# +324 each in the eleven and +1 in German, 2026-09-21: Knut's help-card batch
# (issue #182, 2026-09-20 20:58). Twelve cards rewritten into his
# to-do-steps-first shape with the reasoning in collapsible notes; the
# verification card updated for the preset-eligibility window and the
# Measurement Report; the folder guide given the folders and files the report
# work introduced (compliance/, reference_sets/, the control-strip
# declaration, the colorimetric reference, the print record, reports/old); and
# thirty new Dictionary terms for the report, verification, the standards and
# the Fogra tools. 324 keys arrive, 69 retire.
#
# German is translated by hand for all 324. It rises by exactly ONE because
# the headword "FOGRAxx (FOGRA39, FOGRA51, FOGRA61 …)" is a list of Fogra's
# own set identifiers, identical in every language; translating it would mean
# inventing a German name for a standard's designation.
#
# The eleven carry the English source under the project's rule that eleven
# languages are translated in one pass before a final, not during a beta.
# These are each language's ACTUAL count, measured off the tree.
    # RE-MEASURED 2026-09-20, challenge round 31 on the Fogra reference-set
    # door: seven new strings, German written by hand (de does not move) and
    # the eleven others carrying the English source under the beta rule, so
    # each rises by exactly 7. COUNTED off the catalogues on disk, never
    # adjusted upward.
    # RE-MEASURED 2026-09-18, round 19: the numberless scope sentence gained
    # its own plural form for a document drawn from more than one project,
    # which the numbered one has had since R13-3. One key in, none out.
    # RE-MEASURED 2026-09-18 again, for round 18's fix to the report's scope
    # sentence: a folder that cannot be counted no longer has a number invented
    # for it, so there is a second wording with no numbers in it. ONE key in,
    # none out, every catalogue up by exactly 1. Counted, not adjusted.
    # RE-MEASURED 2026-09-18, the round-13 fix for B8-346/R13-3: the
    # Measurement Report's scope sentence gained a second form for a document
    # drawn from more than one project ("...recorded for the projects it is
    # drawn from"), because the single-project wording was summing two folders
    # and calling the total "this project". ONE key in, none out, so every
    # catalogue rose by exactly 1 -- German included, because the sentence it
    # is a sibling of is itself an English placeholder there, so the family is
    # on the beta rule and not on the German-is-complete rule. Counted with
    # `len([k for k, v in cat.items() if v == k and not k.startswith("@")])`
    # per catalogue, which is the expression the test below uses.
    # RE-MEASURED AGAIN after the merge of that round into this branch:
    # the numbers above were counted on ITS base, which did not carry the
    # report round's placeholders. Counted on the merged catalogues.
    # RE-MEASURED 2026-09-11 (#182, the chart-file import refusal).
    # M-IMPORT-NOT-A-CHART is two strings, a headline and a body. German is
    # translated, so its 124 is unchanged; the other eleven carry the English
    # source as a documented placeholder under the beta rule, so each rose by
    # exactly 2. COUNTED, not adjusted upward: the count is
    # `len([k for k, v in cat.items() if v == k and not k.startswith("@")])`
    # per catalogue, which is the same expression the test below uses.
    # RE-MEASURED AGAIN 2026-09-11 (#182, the adversarial round): the Build
    # Profile tab now says when a measurement already on disk carries its CIE
    # columns on the 0..1 scale. Two more strings, a label suffix and the Build
    # button's tooltip; German is translated, so 124 stands, and the other
    # eleven each rose by exactly 2 again. Counted with the expression above.
    # RE-MEASURED 2026-09-11, the Report-window round on Knut's report of that
    # day (#182 W1 to W7). **12 keys in, 3 stale out**, counted with
    # `set(after) - set(before)` and `set(before) - set(after)` on each
    # catalogue rather than from memory. The twelve: the five verdict words
    # broken out of one paragraph into one bullet each (W5), the paragraph that
    # replaces the struck "never says that anything conforms" sentence (W6),
    # the lead sentence those bullets hang off, the "Bound, and locked."
    # heading and its paragraph (W4), the two rewritten Custom-set blurbs and
    # the note at the limits table saying whose numbers those columns hold
    # (W7). The three that went stale are the single long verdict-words
    # paragraph and the two old Custom blurbs, and all three were translated in
    # every one of the twelve, so they were never in these counts.
    #
    # German is translated, so **de does not move at all (124)**; the eleven
    # others carry the English under the beta rule and each rises by exactly 9.
    # None of the twelve quotes a ChromIQ control in curly quotes, which is the
    # rule that would have required all twelve to be translated: the only
    # quoted word is "drift", which is a word the report PRINTS IN A CELL
    # rather than a control the reader has to find, and
    # `test_a_quoted_control_names_the_control_the_reader_has.py` was run to
    # confirm that rather than assumed.
    #
    # Every number below is this tree's actual count, not the old number plus
    # nine: a ceiling above the truth admits the next regression for free.
    #
    # RE-MEASURED 2026-09-12, the verification-import round. An i1Profiler
    # export of a chart i1Profiler did not generate carries no device values at
    # all, so the import now pairs it with the chart by patch NAME, asks the
    # person the one thing it cannot check, and states the counts against the
    # SHEET as well as the design. **18 keys in, 3 stale out**, counted with
    # `set(after) - set(before)` and `set(before) - set(after)` on each
    # catalogue and not from memory. The eighteen: the asking window's
    # headline, its "Import it" button, its two bodies (singular and plural),
    # the cancelled-import log line, the two "the chart supplied the device
    # values" log lines, eleven refusal reasons, and the rewritten import-panel
    # sentence that now names the designed count AND the printed one. The three
    # that went stale are the patch-identity INFO line the tab no longer writes
    # and the two count sentences that stopped being true; all three were
    # translated in every one of the twelve, so they were never in these counts.
    #
    # German is translated, so **de does not move at all (124)**; the eleven
    # others carry the English under the beta rule and each rises by exactly
    # 18. Counted on the catalogues this commit leaves behind, with the same
    # expression the test below uses, never adjusted upward.
    #
    # RE-MEASURED 2026-09-12 AGAIN, the adversarial round after it. A
    # measurement with no device values and NO chart beside it had nothing to
    # complete it from and was being filed anyway, so `assess` refuses it with
    # one new reason sentence. **1 key in, 0 stale out**, counted the same way.
    # German is translated, so **de does not move (124)**; the eleven others
    # carry the English under the beta rule and each rises by exactly 1.
    #
    # RE-MEASURED 2026-09-16, the beta 19 text-placement round. Three testers
    # drove beta 18 on screen and found six remedies that name a control which
    # does not move what the sentence says it moves; every one of them is now
    # offered where it works and withheld, with the reason, where it does not.
    # **13 keys in, 6 stale out**, counted with `set(after) - set(before)` and
    # `set(before) - set(after)` on each catalogue rather than from memory. The
    # thirteen: the two conditional "Clip border width" clauses and their
    # positive counterpart, the two "smaller Size under Sheet text" clauses,
    # the "lowering B buys almost nothing in Prioritise patch size" sentence,
    # the four clip-border and chart-note messages with their inert levers
    # taken out, the two bottom-text messages with theirs taken out, and the
    # new strip-letter message for the layout mode in which "T" moves nothing.
    # The six that went stale are the earlier wordings of those same messages,
    # and all six were translated in every one of the twelve, so they were
    # never in these counts.
    #
    # German is translated, so **de does not move at all (124)**; the eleven
    # others carry the English under the beta rule and each rises by exactly
    # 13. Every number below is this tree's actual count, taken with the same
    # expression the test below uses, never the old number plus thirteen.
    #
    # RE-MEASURED 2026-09-16, B8-246: a report is written against ONE limit
    # set, so the red line that told a reader the table they were reading was
    # not comparable is replaced by three keys that say which measurements are
    # left out and why. **3 keys in, 0 stale out**, counted with
    # `set(after) - set(before)` on each catalogue. The old warning's two keys
    # are still used, as the backstop for a state nothing can reach any more,
    # and both are translated everywhere, so they were never in these counts.
    #
    # German is translated, so **de does not move (124)**; the eleven others
    # carry the English under the beta rule and each rises by exactly 3. Every
    # number below is this tree's own count, taken from the test's own
    # expression.
    #
    # RE-MEASURED 2026-09-16, B8-250: the Measurement Report gained a "Saved
    # reports" row, so a run's several reports of one measurement can be shown
    # and one of them deleted, with M-REPORT-DELETE's question in front of it.
    # **10 keys in, 0 stale out**, counted with `set(after) - set(before)`.
    # German is translated, so **de does not move (124)**; the eleven others
    # carry the English under the beta rule and each rises by exactly 10.
    # 2026-09-16, the text round: SIX more, and two of them are the price of a
    # rewording rather than of a new sentence. The Print Chart tab's "Load
    # image (TIFF)" tooltip and its status line both sent the reader to "the
    # grid button", which that tab has not had since #130 moved it to the
    # masthead; the new wording names "Open Chart File (.ti2)" instead, and the
    # eleven lose the translation the OLD sentence had until the pass before
    # GA. The other four are the averaging-failed window's body (title
    # translated, body never) and the three sentences of the lp-path print
    # warning, all four of which were hidden from `unwrapped_literals` by a `+`
    # in the argument. de does not move (124); the eleven rise by exactly six,
    # and every number is this tree's measured count.
    #
    # MERGED 2026-09-16: both branches above raised this budget for
    # different reasons, and the numbers here are NEITHER side's and not
    # their sum. They are counted off the merged catalogues, because a
    # budget adjusted upward admits the next regression for free.
    # 2026-09-17: EVERY language rises by exactly TWO, and by the same two.
    # Knut asked for the difference between the two chart layout methods to be
    # explained properly: *"The help text for the chart layout options does not
    # clear enough detail the differences between them and the advantages the
    # 'Prioritise chart area...' method has over the old printtarg-based
    # method... it is also not mentioned that 'Prioritise patch size...' is
    # based on the ArgyllCMS printtarg, thus have many of its limitations."*
    # So the "Create layout" tooltip and the Create Chart step help were both
    # rewritten, and the twelve translations the OLD wording had do not carry
    # over to a string that now says something different.
    #
    # They stay English until the pass before GA, which is the standing rule
    # for a beta: strings churn, and translating each change as it lands is
    # work that gets thrown away. Every number below is counted off this tree,
    # not the old number plus two, because a budget adjusted upward admits the
    # next regression for free.
    # 2026-09-18: every language rises by exactly EIGHT, and by the same eight.
    # Knut's Patch Set editor batch (#182): the Add window's count beside
    # "Pure white & black" disagreed with the total it fed, and "Fill remaining
    # gaps" showed 0 without saying that its target counts the patches already
    # on the chart. Fixing both changed five strings (the shared generator
    # essay, the Add window's intro, the white/black, fill and unique tooltips)
    # and added three ("fill chart to:", "patches in total", "target already
    # met"). The translations the OLD wording had do not carry over to strings
    # that now say something different.
    #
    # They stay English until the pass before GA, which is the standing rule
    # for a beta. Every number below is counted off this tree.
    # 2026-09-18, later the same night: B8-309, and the numbers move in BOTH
    # directions, which is why they are counted and not adjusted. Knut ruled
    # that the Measurement Report must read as a document printed for a
    # customer, so five sentences that named a window control or another
    # report's limit set were rewritten or removed. The removals took
    # untranslated placeholders with them in the eleven languages that had not
    # been swept, so de rises by five while es, fr and the rest fall.
    # ...and once more, +1 each, for B8-328's SECOND attempt: three layout help
    # texts rewritten after an adversary round measured the first rewrite false
    # on 154 of the 160 built-in charts.
    # 2026-09-18, B8-380/B8-383: the generated-reports control gained fourteen
    # strings (the list's own name and help, "Delete Selected Report", the two
    # sentences L.9 asks for, the four clauses a generated NAME is built from,
    # and the revised M-REPORT-DELETE). German is translated in the same commit,
    # so `de` does not move; the other twelve stay English until the pass before
    # GA, which is the standing rule for a beta, so each rises by six. Six and
    # not fourteen: eight of the fourteen were already in those catalogues from
    # elsewhere, and `i18n_sync` also retired eight stale keys.
    # 2026-09-18, B8-388/B8-391/B8-392: seventeen new strings (the renamed
    # Preferences frame, the "Report type, default" pulldown and its two tick
    # boxes with their help, the "New report…" entry and its tooltip, the
    # Measure tab's "Save measurement report" help, the sentence a window
    # holding one measurement shows, the three date flags and "Detailed" in a
    # generated report's name, and the unlock question with its false clause
    # removed). German is translated in the same commit, so `de` does not move;
    # the other twelve rise by eleven each, which is the seventeen less the six
    # that were already in those catalogues from elsewhere. **Counted off this
    # tree, not adjusted**: `python - <<'PY'` over data/i18n/*.json, values
    # identical to their key.
    # 2026-09-18, B8-397: the five limit rows that had no detection method got
    # one, so the limits window gained 22 strings (the changed group heading,
    # five blurbs, three detection essays, three levers, and the ten fragments
    # the report window builds the four new reasons out of). German is
    # translated in the same commit, so `de` does not move; the other twelve
    # rise by twenty-one each, which is the twenty-two less the one that was
    # already in those catalogues from elsewhere, and `i18n_sync` also retired
    # nine stale keys. **Counted off this tree, not adjusted.**
    # RE-MEASURED 2026-09-19, the round-24 fix set (B8-404): the Measurement
    # Report's limit controls no longer tell a user that the calibration they
    # are looking at is outside the project it sits in. ONE key in, none out --
    # "This measurement does not belong to a profile run, so the choice is not
    # stored anywhere." -- and the sentence it replaces is still in use for a
    # file that really is in no project, so nothing went stale. German is
    # translated, so **de does not move (143)**; the eleven others carry the
    # English under the beta rule and each rises by exactly 1.
    #
    # COUNTED, not adjusted: every number below is
    # `len([k for k, v in cat.items() if v == k and not k.startswith("@")])`
    # run over each catalogue at HEAD and again here, and the HEAD column came
    # back equal to the numbers that were recorded, so the eleven +1s are the
    # whole of the change.
    # 2026-09-19, beta 22, TWO change sets landing together and the split is
    # worth recording because the two behave differently.
    #
    # * the control-strip declaration (#182, M-VERIFY-NO-CONTROL-STRIP and four
    #   Create Chart log lines) adds **6 keys, all six translated into German**,
    #   so de does not move for them and the eleven others each carry the
    #   English under the beta rule;
    # * the "Which presets can be verified?" window adds **38**, and the line
    #   above recorded them as untranslated in German too. **RE-MEASURED the
    #   same day, once that window's German landed: all 38 are translated, so
    #   de does not move at all and stays at 143.** 181 would have been an
    #   upper bound with 38 keys of slack under it, and a budget with slack
    #   admits the next regression for free -- this test only checks `<=`, so
    #   nothing would have gone red.
    #
    # So de does NOT move (143) and each of the other eleven rises by 44.
    # COUNTED, not adjusted: every number below is
    # `len([k for k, v in cat.items() if v == k and not k.startswith("@")])`
    # run over each catalogue as it stands, and the arithmetic above is the
    # whole of the difference from the previous column.
    # RE-MEASURED 2026-09-19, the round-26 fix set: three strings, all three
    # translated into German in the same commit, so **de does not move (143)**
    # and each of the other eleven rises by exactly 3.
    #
    # * the Apply Calibration output placeholder, which promised a filename
    #   nothing writes ("cal_<name>.icc" and "cal_{stem}.icc", both retired);
    # * the printcal success window's next step, which sent the user to a
    #   checkbox #137 removed, so its old translations describe a control that
    #   is not there and could not be carried across;
    # * the warning line for a profile that could not be archived before the
    #   build that replaces it.
    #
    # Two keys out, three in. COUNTED, not adjusted:
    # `len([k for k, v in cat.items() if v == k and not k.startswith("@")])`
    # run over each catalogue as it stands.
    # RE-MEASURED again the same morning, the round-26 printing fix: the macOS
    # print dialog refuses a chart it would otherwise convert, which is two new
    # strings (the window's title and its body). German is translated in the
    # same commit, so **de does not move (143)** and each of the other eleven
    # rises by exactly 2. COUNTED off the tree, not adjusted.
    # RE-MEASURED 2026-09-19, Knut's beta 25 Create Chart batch (B8-444 to
    # B8-450): the preset-eligibility window is renamed "Which presets can be
    # used for verification", says "metric" where it said "row", names the
    # metrics a prebuilt-TIFF preset can never fulfil, and tells the reader a
    # double-click loads the preset. **17 keys in, 11 stale out.**
    #
    # Sixteen of the seventeen are translated into German in the same change.
    # The seventeenth is `{metric}: {explanation}`, which is nothing but two
    # placeholders and has no German to write, so it counts as identical to
    # its key and **de moves by exactly one, 143 -> 144**. The eleven others
    # carry the English under the beta rule and each rises by 17 - 11 = 6.
    #
    # THREE OF THE SEVENTEEN ARE NOT THIS CHANGE SET'S. "Report settings",
    # "Included Measurements in report:" and "Every metric this report judges,
    # and what it means:" arrived in the same working tree from the concurrent
    # Measurement Report work and were already missing from every catalogue
    # before this change; `i18n_sync` is a whole-tree operation and picked them
    # up, and their German is written here so the tree is not left red. If that
    # work rewords them, sync again and re-measure this block rather than
    # nudging it.
    #
    # COUNTED, not adjusted:
    # `len([k for k, v in cat.items() if v == k and not k.startswith("@")])`
    # run over each catalogue as it stands.
    # RE-MEASURED once more the same evening, for B8-464, which the concurrent
    # Measurement Report round found and left alone rather than have two agents
    # rewrite one ledger. It is INHERITED: `1db705f1` grew the Report limits
    # window's two ISO sentences and never synced the catalogues, so both were
    # stale AND missing in all twelve at HEAD. Two keys in, two out; **de does
    # not move**, because both German translations already existed for the
    # shorter sentences and the added sentence is written here by hand (and the
    # older of the two was in Sie-Form against the German Du rule, which the
    # rewrite corrects). Each of the eleven others rises by exactly 1.
    # COUNTED off the tree, not adjusted.
    # 2026-09-19, Knut's beta-25 report-window ruling (B8-490 / B8-491). SIX
    # keys in: the three-button question's headline and body, its two new
    # button labels ("Update", "Create New"), and the "updated {when}" clause a
    # report's name gains when Update is pressed. The two tick-box tooltips
    # were REWORDED rather than added, so each of them is one key in and one
    # key out and neither moves a count: German is written by hand in the same
    # change for both, and the eleven others carried the old sentences in
    # English already. **German does not move at all (144, unchanged): all six
    # new keys are translated here.** Each of the eleven others gains exactly
    # 6. COUNTED off the catalogues this commit leaves behind, with the same
    # expression the test below uses, and never adjusted upward.
    # RE-MEASURED 2026-09-20, the whole of Knut's beta 25 batch in one sweep:
    # the Create Chart rename and its metrics wording, the report window's
    # three bugs and its re-layout, the Update / Create New / Cancel popup, and
    # the door that lets a licence holder supply a standard's own limit values
    # without a terminal. German is translated by hand for every one of them,
    # so **de does not move**; the eleven others carry the English under the
    # beta rule. COUNTED off the tree with each file's own expression, never
    # adjusted to make a red go green.
    # RE-MEASURED 2026-09-20, Knut's beta 26 review (B8-520 to B8-526): nine
    # new keys and none retired -- the four sentences a greyed "Unlock this
    # run's limits" owes the reader, the two the one-page summary owes it, the
    # bullet heading "What each set is", the type bullet that says what a
    # Colour summary cannot hold, and the sentence that says why "Judged
    # against" is not the Preferences default. **German is translated by hand
    # in the same change, so de does not move (145)**; the eleven others carry
    # the English under the beta rule and each rises by exactly 9. COUNTED off
    # the catalogues this change leaves behind, with the expression the test
    # below uses, and never adjusted to make a red go green.
    # RE-MEASURED 2026-09-20, the Fogra reference-set upgrade path: a user may
    # point ChromIQ at a newer Fogra file, per set, without a new ChromIQ.
    # TWENTY-EIGHT keys in and TWO out. The two that went are casualties of the
    # same change and not of a rename elsewhere: the Reference values window's
    # opening sentence, which said the data "cannot be shipped inside the
    # program" and is now false of half of what the window covers, and "Use a
    # file I filled in", which came back a moment later as `Source.pick_title`
    # because deriving a dialog title by stripping "…" off a button label
    # makes it invisible to `scripts/i18n_extract.py` and guesses at
    # punctuation in thirteen languages.
    #
    # **German does not move (145)**: all twenty-eight are translated by hand
    # in this change. The eleven others carry the English under the beta rule
    # and each rises by exactly 28 - 2 = 26. COUNTED off the catalogues this
    # change leaves behind, with the expression the test below uses, and never
    # adjusted to make a red go green.
    # RE-MEASURED 2026-09-20, B8-548. The ISO half of the Reference values
    # window used to print a raw Python exception at a user who picked the
    # wrong file ("'utf-8' codec can't decode byte 0xe2 in position 10"),
    # measured on screen in challenge round 31. It now answers with two
    # sentences ChromIQ wrote. German is translated by hand in the same change,
    # so **de does not move (145)** and each of the eleven others rises by
    # exactly 2, which is the two new keys carrying their English source under
    # the beta rule. COUNTED off the catalogues this change leaves behind,
    # never adjusted upward.
    # RE-MEASURED 2026-09-22 on the COMBINED tree, after merging four parallel
    # rounds (the help-card rework, the verification pre-flight popup, the
    # guided stamp and the rounded frames). Neither agent's numbers were taken:
    # both rounds moved these files, so either set alone would have been stale
    # the moment the other landed. COUNTED with this file's own helper on the
    # tree this commit leaves behind, never adjusted upward. German is
    # translated by hand in the same change and so moves only by strings that
    # are identical in every language.
    # RE-MEASURED 2026-09-22 on the COMBINED tree, after merging five parallel
    # rounds. Neither any agent's numbers nor my own earlier ones were carried
    # forward: every round that lands moves these files, so any figure written
    # before the last merge is stale by construction. COUNTED with this file's
    # own helper on the tree this commit leaves behind, never adjusted upward.
    # RE-MEASURED 2026-09-22 on the COMBINED tree, after merging six parallel
    # rounds. No agent's numbers and none of my own earlier ones were carried
    # forward: every round that lands moves these files, so any figure written
    # before the last merge is stale by construction. COUNTED with this file's
    # own helper on the tree this commit leaves behind, never adjusted upward.
    # RE-MEASURED 2026-09-22 on the COMBINED tree, after merging eight rounds
    # and adding Ukrainian. No agent's numbers and none of my own earlier ones
    # were carried forward: every round that lands moves these files, so any
    # figure written before the last merge is stale by construction. COUNTED
    # with this file's own helper on the tree this commit leaves behind.
    # RE-MEASURED 2026-09-21, B8-670 (Knut's researched industry figures as
    # the two Custom columns' defaults). **13 keys in, 7 stale out**, and
    # every count FALLS: the eleven fall by 4 and Ukrainian by 8, because the
    # seven retired keys were English placeholders in those catalogues and the
    # thirteen replacements were translated in all thirteen languages rather
    # than carried in English. German is written by hand and does not move.
    #
    # The one that mattered is `ChromIQ's own numbers`, which had been an
    # English placeholder in all twelve. It is a FRAGMENT of a sentence those
    # twelve now assemble, so left untranslated it would have put an English
    # phrase in the middle of translated prose; and this round left it with
    # exactly one caller, so translating it could not disturb anything else.
    # Counted off the catalogues on disk with the expression the test below
    # uses, and NEVER adjusted upward.
    # RE-MEASURED 2026-09-22 on the COMBINED tree, after ten rounds and a fix
    # round. No agent's numbers and none of my own earlier ones were carried
    # forward: every round that lands moves these files, so any figure written
    # before the last merge is stale by construction. COUNTED with this file's
    # own helper on the tree this commit leaves behind.
    # RE-MEASURED 2026-09-22 on the COMBINED tree, after ten rounds, a fix round
    # and a recovery. No agent's numbers and none of my own earlier ones were
    # carried forward. German stands still at its own figure because German is
    # translated by hand in the same change; a RISING German number means an
    # untranslated German string, not a bigger budget, and is fixed rather than
    # recorded. COUNTED with this file's own helper on the tree this commit
    # leaves behind.
    "de": 141,
    "es": 956,
    "fr": 978,
    "it": 967,
    "ja": 942,
    "nl": 983,
    "no": 968,
    "pl": 960,
    "pt": 958,
    "ru": 931,
    "sv": 969,
    "zh_CN": 936,
    # RE-MEASURED 2026-09-22, and it RISES BY THREE ON PURPOSE, which is the
    # one direction this ledger is not normally allowed to move. The three are
    # `chartread`, `colprof` and `scanin`: ArgyllCMS EXECUTABLE NAMES, which
    # the contributed catalogue had translated into `діаграма` ("chart"),
    # `кольпроф` (a transliteration) and `сканування` ("scanning"). A user
    # types those names, reads them in a log and sees them in Finder, so they
    # must stay in English, and all twelve other catalogues leave them alone.
    # Restoring them therefore ADDS three values identical to their key.
    #
    # A FOURTH followed the same day and for the same reason: `Lab (CIELAB)`.
    # The catalogue had rendered Lab, the colour space, as "Лабораторія", a
    # LABORATORY, and once as "Лабораторний стіл", a laboratory BENCH, on the
    # profile-type control. Every one of the twelve other catalogues keeps
    # `Lab`, so Ukrainian does too, and `Lab (CIELAB)` is then identical to its
    # key.
    #
    # This is the one shape of rise that is not translation rot, and it is
    # spelled out here because the rule everywhere else in this project is that
    # a rising number means an untranslated string and the budget is never
    # nudged to admit it. COUNTED off the catalogue on disk: 1166 before the
    # restorations, 1169 after the three tool names, 1170 with `Lab (CIELAB)`,
    # and back to 1169 once `Edit / create chart patch set` was translated: it
    # had never been translated at all, while two messages quoted that control
    # in Ukrainian, so the pointer could not match whatever the user read.
    # Nothing else changed. The ceiling is re-measured DOWN here rather than
    # left where it was, so the next rise still has to justify itself.
    "uk": 1191,
}



@pytest.mark.parametrize("code", _catalog_codes())
def test_untranslated_values_do_not_creep_in_unseen(code):
    cat = _load_catalog(code)
    same = sorted(k for k, v in cat.items()
                  if v == k and not k.startswith("@"))
    allowed = _IDENTICAL_TO_KEY.get(code)
    if allowed is None:
        pytest.skip(f"no recorded count for {code}")
    assert len(same) <= allowed, (
        f"[{code}] {len(same)} values are identical to their key, and "
        f"{allowed} were recorded. Something was renamed and lost its "
        f"translation, or a new string arrived untranslated. Newest few: "
        f"{same[-3:]}"
    )


def test_the_import_button_is_translated_everywhere(_=None):
    """The specific loss, pinned: it is short enough to hide from every count.

    Renaming a button is the easiest way to lose twelve translations at once,
    because the new key simply is not in any catalogue and the old one goes
    stale unnoticed.
    """
    keys = ("File it in {run}", "File it in a new run",
            "File it in the selected run")
    for code in _catalog_codes():
        cat = _load_catalog(code)
        for k in keys:
            assert k in cat, f"[{code}] the import button lost its key {k!r}"
            assert cat[k] != k, (
                f"[{code}] the import button is still English: {k!r}")


# ---- Ukrainian, contributed on issue #198 by LackiUA ---------------------
#
# A language is "working" only if all four of these are true at once, and each
# of them has been the thing that was missing on this project at some point:
# the Settings combobox can FIND it (it discovers a language by globbing
# `data/i18n/*.json` and reading `@language_name` out of it, so a catalogue
# with no native name is listed by its bare code), `set_language` LOADS it,
# the UI catalogue actually answers, and the parameter overlay merges so the
# Create Chart rows are Ukrainian too rather than half-English.
#
# The native name is asserted verbatim because it is the string the user picks
# in the combobox, and a catalogue that lost it still passes every other test
# in this file.

def test_ukrainian_is_discoverable_in_the_language_list():
    langs = dict(i18n.available_languages())
    assert langs.get("uk") == "Українська", (
        "Settings would not offer Ukrainian by name; available_languages() "
        f"returned {langs.get('uk')!r}")


def test_ukrainian_loads_and_translates():
    i18n.set_language("uk")
    assert i18n.current_language() == "uk"
    assert i18n.tr("Cancel") == "Скасувати"
    assert i18n.tr("Build Profile") == "Побудувати профіль"


def test_ukrainian_parameter_overlay_merges():
    """The overlay is a separate file from the catalogue and it is merged by a
    separate function, so a language can be fully loaded and still show every
    Create Chart row in English."""
    i18n.set_language("uk")
    params = i18n.translate_parameters(_load_params())
    d = next(p for p in params["targen"] if p["flag"] == "-d")
    english = next(p for p in _load_params()["targen"] if p["flag"] == "-d")
    assert d["name"] == "Тип пристрою"
    assert len(d["labels"]) == len(english["labels"]) == 16
    assert d["labels"] != english["labels"]


#: The longest verbatim run of the ENGLISH source that may appear inside a
#: German string. MEASURED off the catalogue, 2026-09-22, over all 1,750
#: German strings of 120 characters or more: the largest legitimate run is
#: **215** characters, inside a 5,199-character technical passage about
#: building a printer profile from a scan. The next four are 106, 104, 104 and
#: 96, and the 104s are a list of file names and an HTML fragment, which are
#: identical in every language by nature.
_DE_MAX_ENGLISH_RUN = 300


def test_a_german_string_is_not_english_with_a_sentence_spliced_in():
    """German is translated by hand, and half-translating it passes every
    other guard in this file.

    **MEASURED, AND IT WAS MINE.** Renaming one button changed one sentence
    inside a 684-character Report-limits help text. What went in as "German
    written by hand" was the ENGLISH source with a single German sentence
    spliced into the middle: the string went from **5.7 % English to 76.8 %
    English**, and a German user read an English paragraph with one German
    sentence in it.

    It slipped past everything: it is not a MISSING key, so the missing-key
    guard is silent; it is not IDENTICAL to its key, so
    `_IDENTICAL_TO_KEY` is silent and stayed at 146; and it carries no
    placeholder fault. Challenge round 38 found it by measuring the text
    against its own source.

    Only German is asked, deliberately. The other twelve carry the English
    source ON PURPOSE during a beta, which is the project's own rule and the
    reason `_IDENTICAL_TO_KEY` exists with numbers in the hundreds.
    """
    from difflib import SequenceMatcher
    cat = _load_catalog("de")
    bad = []
    for key, val in cat.items():
        if key.startswith("@") or len(key) < 120 or val == key:
            continue
        m = SequenceMatcher(None, key, val, autojunk=False).find_longest_match(
            0, len(key), 0, len(val))
        if m.size > _DE_MAX_ENGLISH_RUN:
            bad.append(f"{m.size} characters of the English source survive "
                       f"verbatim in: {key[:70]!r}")
    assert not bad, (
        "a German string carries a long verbatim run of its English source, "
        "which is what a half-translated string looks like:\n  "
        + "\n  ".join(bad[:5])
        + f"\n\nThe measured ceiling is {_DE_MAX_ENGLISH_RUN}; the largest "
          "legitimate run in the catalogue is 215. Translate the whole string "
          "rather than splicing a sentence into the English."
    )
