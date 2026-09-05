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
_IDENTICAL_TO_KEY = {
    "de": 152,
    "es": 383,
    "fr": 403,
    "it": 395,
    "ja": 372,
    "nl": 412,
    "no": 396,
    "pl": 387,
    "pt": 387,
    "ru": 359,
    "sv": 400,
    "zh_CN": 365,
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
