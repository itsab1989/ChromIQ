"""English placeholders in the catalogues must be COUNTABLE, not invisible.

`scripts/i18n_extract.py --missing` only checks whether a KEY EXISTS. A key
whose value is still the English source passes it, and
`tests/test_i18n.py::test_catalog_is_complete` passes too. That blind spot
already bit once: eleven keys shipped as English in eleven languages while the
tooling reported "0 missing of 4431", and I told Basti the catalogues were
clean on the strength of it.

Placeholders are LEGITIMATE during a beta — the project rule is English
placeholders while text is still moving, all languages before final. What is
not legitimate is not knowing how many there are. This test does not forbid
them; it makes the number visible and fails if it grows without anyone
noticing.
"""
import json
import pathlib

import pytest

_I18N = pathlib.Path(__file__).resolve().parent.parent / "data" / "i18n"

# Raise DELIBERATELY when adding beta text, lower it when translating before a
# final. Never edit it to make a red run green without looking at what grew.
# Measured 2026-08-25, end of the answered-questions batch: German 35, the rest
# 60-62. German stays low because Basti and Knut read it, so it is kept current;
# everything else accumulates English placeholders under the beta rule and is
# translated in one pass before a final.
#
# RAISE THIS DELIBERATELY, never to make a red run green. It has been raised
# three times in one day — twice for the two new §M patch-set messages and once
# for the "Load setup from preset" tooltip — and each rise was a real decision
# to defer translation, not an accident. If a rise ever cannot be explained in
# one sentence, something was added that nobody meant to add. Of those,
# 23 per language are the three new Tools help cards, added as English
# placeholders under the project's beta rule; the remainder pre-date them.
# German is lower because Basti and Knut read it, so it is kept current.
# 2026-08-30, beta 2, raised 92 -> 93: a chart naming no instrument now says
# so, because ArgyllCMS otherwise claims it is for a GretagMacbeth i1 Pro --
# its own default, not anything in the file. One string.
#
# 2026-08-30, #159, raised 86 -> 92: a dark reference that does not read as
# dark now opens a window offering to retake it (Basti: a failure must not
# hide in a log panel he keeps closed), and both calibration texts were
# corrected to stop claiming the read-back checks what the user pointed at —
# hardware says it does not: white paper read back 0.004 %.
#
# 2026-08-30, #159, raised 83 -> 86: a lost Bluetooth link is now told apart
# from a refused calibration. The owner's CR30 powered itself off mid-session
# and ChromIQ said 'the measurement can go ahead' over a dead link, quoting
# bleak's 'Service Discovery has not been performed yet' as the reason.
#
# 2026-08-30, #159, raised 80 -> 83: the measure panel's advice line now says
# what a CR30 owner actually does ("rest it on the patch and press its button"
# rather than "scan each strip"), and a re-arm that finds nothing outstanding
# says so instead of going quiet. Three strings.
#
# 2026-08-30, #159, raised 76 -> 80 for the windows the owner asked for: a
# pop-up for a vanished instrument ("if this is an important message this
# should be in a pop up windows with benefitial options"), and a real Cancel on
# the black-calibration window, whose close button used to mean "skip". Four
# strings; the two revised message bodies replace keys already counted, and
# German is translated as usual because it is read.
#
# 2026-08-30, #159, raised 75 -> 76 for the sentence that says the measurement
# is still stopped after a magnet, when the user declines to end it. One string.
#
# 2026-08-30, #159, raised 73 -> 75 for the read-failure window: a refused
# reading was announced only in the log, where Basti did not see it, so it now
# opens a window that closes itself when the reading arrives. Two new strings,
# German translated as usual because it is read.
#
# 2026-08-30, #159, raised 70 -> 73 for the magnet window: a magnet
# recalibrated the owner's instrument mid-chart (a MacBook under his paper) and
# the session carried on, so the refusal now stops the session and offers to
# retake the white calibration. New beta text under the project's rule.
#
# 2026-08-29, #159, raised 62 -> 70 for the CR30 instrument work: the
# no-device help (which had never been translatable at all — fifteen sentences
# built as bare strings the extractor could not see), the greyed-option
# explanation, the disconnect and re-arm notices, and the two calibration
# windows including the dark-reference step. All are new beta text under the
# project's rule, and German is translated as usual because it is read.
# Raised from 93 on 2026-08-30, deliberately, for the CR30's
# learned-tile step and its keyboard-trigger refusal (#159, both §M-PROPOSED).
# Their wording is not approved yet, and this project does not translate a
# message before it is agreed -- translating it twice is the waste that rule
# exists to prevent. German is translated as usual, which is why its budget
# does not move.
#
# 97 is the highest ACTUAL count across the twelve, not an estimate: the old 93
# was a uniform ceiling and the real figures sat below it by different amounts,
# so a uniform "+2" under-shot for some languages and passed for others.
# 2026-08-31, #159, raised 110 -> 115: the learn-the-white-tile window was
# rebuilt after Basti's own Bluetooth session -- it now listens while it is
# open, counts the presses as they land, and names the count the OPEN
# TRANSPORT needs (one over USB, two over Bluetooth), which is two message
# bodies plus three live-progress lines. Five strings. German is translated,
# as always.
# 2026-08-31, #159, raised 115 -> 116: a tile learn that failed for any
# reason other than being declined said nothing at all -- thirty-four seconds
# of a feature failing left no trace in the log, which is why the first
# explanation of it was wrong. It now says how many readings it took and why
# they were not enough. Two substantial strings.
#
# 2026-09-01, #159, raised 117 -> 122: the beta-5 challenge round. The import
# window's accept button now NAMES the run it will file into ("File it in
# Run 2") because "File it here" read as the run already on screen; the row
# indicator checkbox and its warnings say "row indicators" rather than "row
# numbers", which stopped being true when the band started following the
# chart's own patch pattern; and the import path's user-facing em dashes are
# gone at Basti's request. Where a key was only REWORDED, the existing
# translation was carried across rather than dropped back to English -- 19 of
# the 32 new keys kept their German. Five substantial strings are new.
#
# 2026-09-01, raised 122 -> 125: the verification round found the K8
# rename had never reached German (the checkbox still said
# "Zeilennummern", the very misnomer the rename cured, in the language
# the reporter reads) and that the import button's translations were
# lost when it was renamed. German now carries all of them; the other
# eleven hold three more English placeholders, from repairing the comma
# splices the em-dash removal left behind.
#
# 2026-09-01, raised 125 -> 127: Check & Refine became a real import door
# (docs/design/import_doors_amendment.md), which adds the two window
# bodies that explain filing versus checking in place. German carries
# both; the other eleven hold the English under the beta rule.
# 2026-09-02, raised 128 -> 135 for the eleven; German does not move.
# Basti's option-3 ruling made the calibration-replacement window's promise
# false, and he approved its replacement wording the same day. Seven
# substantial strings: the two window bodies, the log line that finally names
# where an archive went, the file guide's "cal/old" entry, the Delete tooltip,
# the welcome card's calibration paragraph, and one that is NOT from this work
# at all -- `M_CHART_CORRUPT_WITH_PROFILE`, which is handed to tr() at two call
# sites and had no key in any language, because `scripts/i18n_extract.py`
# resolved module constants from a hand-kept list of names and nobody had added
# it. That list is now a sweep of the module, so the next one cannot be missed.
#
# German carries all seven and its own count is 31 against a budget of 35.
# 135 is the highest ACTUAL count across the eleven (fr), not a round ceiling,
# following the note above about uniform ceilings hiding real figures.
# 2026-09-03, review 3, +6 for the eleven and +0 for German: the two windows
# that stop Tools ▸ Read single patches binning a measuring session in silence
# (M-SPOT-CLEAR, M-SPOT-UNSAVED). Six SUBSTANTIAL strings — the two headlines
# and the four bodies, singular and plural of each. German carries all six and
# stays at 31 against its budget of 35. The eleven hold the English source
# while the wording is §M-PROPOSED, exactly as M-INSTRUMENT-BUSY does.
# 141 is again the highest ACTUAL count across the eleven (fr), not a round
# ceiling.
# 2026-09-03, review 5, +7 for the eleven and +0 for German: the four windows
# that stop Tools > Build profile with scanner or camera building a profile
# from data that is not the chart it thinks it is (M-SCAN-REF-SHORT,
# M-SCAN-REF-DISAGREES, M-SCAN-CLIPPED, M-SCAN-PROFILE-ARCHIVED). Eight keys
# arrive; SEVEN of them are counted here, because M-SCAN-REF-DISAGREES's body
# opens with the word "ChromIQ" and the filter above treats a string beginning
# with a brand name as legitimately identical. German carries all eight and
# stays at 31 against its budget of 35. The eleven hold the English source
# while the wording is section M-PROPOSED, exactly as M-INSTRUMENT-BUSY and the
# M-SPOT pair do. 148 is again the highest ACTUAL count across the eleven (fr),
# not a round ceiling.
# 2026-09-03, Auto align: +9 for the eleven and +0 for German. Twelve keys
# arrive and four leave (the reason-code wording they replace), and NINE of the
# twelve are counted here: "Target reference data" is under the 25-character
# floor, and two bodies open with the word "ChromIQ", which the filter above
# treats as legitimately identical. German carries all twelve and stays at 31
# against its budget of 35. Unlike every entry above, this text IS approved —
# Basti approved it the day it was written — so the eleven hold English for the
# other reason: eleven languages are translated before a final, not during a
# beta. 157 is again the highest ACTUAL count across the eleven (fr), not a
# round ceiling.
# 2026-09-03, the Windows verification's finding D: +4 for the eleven and +0
# for German. Eight keys arrive and FOUR of the eight are counted here — the
# other four are under the 25-character floor ("Building", "Hexagon patches",
# "Applying calibration…", "Creating calibration…"). None of this is new text:
# all eight were already on screen in English in every language, as literals
# that never reached `tr()`, and the eleven simply keep displaying what they
# were displaying. German carries all eight and does not move, because none of
# them is the same wording in German. 161 is again fr's ACTUAL count, not a
# round ceiling.
# 2026-09-04, beta 8 items B8-01 and B8-03: +6 for the eleven and +0 for
# German. Three §M-PROPOSED messages arrived — the under-exposed scan, the
# reference with too few distinct colours, and the profile whose self-check
# came back as no number at all. German is translated, as always, because it is
# the language the owner reads. The eleven carry the English source deliberately
# and not by neglect: the WORDING is awaiting review, and translating a draft
# means translating it twice. 167 is es's ACTUAL count, not a round ceiling.
# 2026-09-04, beta 8 items B8-04/13/15/16/17: two more §M-PROPOSED messages
# (M-SCAN-LOADED, M-SCAN-DIAGNOSTIC). German is translated; the eleven carry
# the English source, because the wording is awaiting review and translating
# a draft translates it twice. These are each language's ACTUAL count.
#: 2026-09-04, beta 8, the photograph path: +9 substantial strings in each of
#: the eleven, +0 in German. Five §M-PROPOSED messages and a button's tooltip;
#: the short labels fall under this file's own length filter. The wording is
#: awaiting review, so the eleven carry the English source rather than a
#: translated draft — the same rule every M-SCAN-* string of review 5 follows.
# 2026-09-04, B8-02: one §M-PROPOSED message, M-SCAN-ALIGN-NOT-SEATED —
# the refusal for a photograph taken off square, whose grid would read part
# of the neighbouring patch. German is translated; the eleven carry the
# English source, because the wording is awaiting review.
# 2026-09-04, beta 8 items B8-14, B8-30, B8-31 and B8-32 (AGENT-M): +9 for the
# eleven and +0 for German. Eleven new keys, of which nine are long enough to be
# counted here -- two §M-PROPOSED messages (M-SCAN-SHOT-EMPTY,
# M-SCAN-TARGET-CHANGED) and their headlines, the corrected "Indicator font"
# tooltip and the note saying which control in "Strip && row labels" reaches
# which label, the "Reading options" and "Save as Defaults" tooltips rewritten
# around a removed control and three newly-saved ones, and the margin-raise
# warning's second form. German is translated; the eleven carry the English
# source, because the wording is awaiting review and translating a draft
# translates it twice. The four keys that went away with the "Correct
# perspective" control were already translated everywhere, so removing them
# moves nothing here. These are each language's ACTUAL count.
#: 2026-09-04, B8-42: minus 9 in every catalogue but German. The merged
#: placement button retired fifteen English echoes — the separate button's
#: label, tooltip and busy note, the old Auto align tooltip, and the eight
#: halves of the four messages withdrawn with it, plus the two rewritten
#: bodies — and added six, of which all but one open with "ChromIQ" and are
#: therefore not counted here at all.
# 2026-09-04, beta 8 item B8-21 §4 (AGENT-R): NO MOVEMENT, and the arithmetic
# is recorded so the zero is not mistaken for "nobody looked". The forty-word
# reach note went away (-1 in the eleven, 0 in German) and the sub-frame title
# "Strip letters and row numbers" arrived untranslated in the eleven (+1);
# "Strip letters only" is 18 characters and this detector only counts strings
# of 25 or more, so it is invisible here on purpose. Net 0.
#: 2026-09-04, AGENT-S (the buttons under the scanner preview): +1 in every
#: catalogue but German. The Pop-out button's label was shortened from a
#: sentence to "⤢ Pop out" and the four dropped words moved into a TOOLTIP,
#: which is new user-facing wording APPROVED by Basti, 2026-09-04 ("it is
#: ok") — §M-PROPOSED, "Button labels … Confirmed behaviour". It carries the
#: English source in the eleven for the ordinary beta reason (translation
#: happens before a final), not because anything is pending. The label itself is 9 characters and this detector only
#: counts 25 or more, so it is invisible here on purpose; the label it replaced
#: was translated everywhere, so removing it moves nothing. Net +1.
# 2026-09-04, beta 8 item B8-52 (AGENT-T): +2 in the eleven, 0 in German. The
# Create Chart notices moved out of their sections onto the ⓘ of the control
# each belongs to (Basti: *"the info text in create chart tab that is directly
# inside the sections (even that that you made collapsible) - i want that
# gone"*). Two sentences had to be REWRITTEN by the move rather than merely
# relocated, because both pointed at a place that no longer exists — "…tick at
# least one edge ABOVE" was true of a label under the two tick boxes and false
# of an ⓘ on the row above them, and the "Show markers for" help ended
# "ChromIQ says so UNDER THE BOXES". Both were translated in these eleven and
# both arrive carrying the English source, so +2; German is translated for
# both. The third key retired by the move, the collapsible box's title "Text
# and label notes", is 20 characters and this detector only counts strings of
# 25 or more, so it is invisible here on purpose. These are each language's
# ACTUAL count.
#   …and +1 more on top of that, same item, same day: the "Text distance from
#   edge" help itself ended *"the text overflows toward this line and a margin
#   warning is shown"*. After the move nothing is SHOWN — the warning is on the
#   ⓘ beside the measured margins — so that sentence had to be rewritten too,
#   which retires a key translated in all twelve and adds one carrying the
#   English source in the eleven. So the item's total is +3 in the eleven and
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
# 2026-09-04, beta 8 item B8-54 (AGENT-AF): +22 in the eleven, 0 in German. The
# Profile type help in Tools ▸ Build profile with scanner or camera was one
# paragraph-blob that told the user the two cLUTs were interchangeable and that
# Lab "sometimes gives slightly smoother neutrals". Nothing measured that;
# B8-19 measured a different difference entirely (a Lab cLUT cannot encode
# anything above its chart's white). It is now built from paragraphs and is
# MODE-AWARE, because a scanner input profile and a printer output profile want
# different types and this window already marks a different "(default)" for
# each: 21 paragraph/label keys, the combo's "(recommended cLUT)" marker and
# three live notes. All 22 are 25 characters or more, so all 22 are visible to
# this detector — none of it is hiding under the threshold. The one key retired
# was translated in all twelve, so it moves nothing here. The eleven carry the
# English source for the ordinary beta reason (translation happens before a
# final, not during a beta) AND because the wording is still PROPOSED — see
# §M-PROPOSED, "⏳ Awaiting confirmation — Profile type help text". German is
# translated for all 22 and does not move. These are each language's ACTUAL
# count.
#: 2026-09-05, the white-point help correction: **+4 in every catalogue but
#: German**. The tooltip stated "1.00 makes no change", which is false — in
#: ArgyllCMS `colprof.c:494` sets autowpsc BEFORE reading the argument and
#: `xfit.c:2753` defaults the scale to 1.0, so `-u 1` is byte-for-byte `-u`.
#: Knut built a profile on that sentence. Correcting it takes four new
#: substantial strings; German is translated, the eleven carry the English
#: source under the beta convention (translation happens before a final, not
#: during a beta). Raised on purpose, and this note is the purpose.
#: 2026-09-05, the -ua help: **+10 more in every catalogue but German**. Nothing
#: in ChromIQ said that a scanner profile used as a measuring instrument must be
#: built for that purpose, so a user following our own steps built one that
#: flattens its top range and never learned why. Measured through the path
#: `scanin` actually uses: a cLUT-Lab profile on the default white point returns
#: ONE colour for device 0.76 / 0.80 / 0.85 / 0.90 / 1.00. German translated,
#: the eleven carry English under the beta convention. Raised on purpose.
# +2 each in the eleven, 0 in German, 2026-09-05 (AGENT BQ): the scanner
# white-point default moved to "Scale white to a perfect white surface" (-u -R).
# Two of the eight keys it brings are long enough to count as substantial —
# M-SCAN-WP-DEFAULT's body, the one-time note saying the default moved, and the
# profile-type help's Lab-cLUT bullet, whose ceiling is a different height under
# the new default. Both are new wording in a beta and both are PROPOSED besides,
# so the eleven carry the English source and German is translated.
# 2026-09-06, Knut's beta 10 batch for the scanner/camera window (B8-78):
# +15 for the eleven and +0 for German. Twenty-six keys arrive and nine
# leave, and fifteen of the survivors are long enough to count here: the
# three scenario glosses, the ⓘ behind the scenario heading, the greyed
# printer reason, the divergence line, the Custom line, the line saying
# what the patch count set up, the note under the locked -R switch, and
# the six rewritten help bodies. German is translated for all twenty-six
# and stays where it was. The eleven carry the English source for the
# usual reason: translated before a final, not during a beta. These are
# each language's ACTUAL count, not a round ceiling.
# 2026-09-06, the review of that same batch (CL-1, CL-6): +2 for the
# eleven and +0 for German. Three keys arrive and one leaves; two of the
# three are long enough to count here (the saved-bucket line with a patch
# count in it, and the rewritten Lab-table note), and the short form of
# the saved-bucket line is under the 25-character floor. These are each
# language's ACTUAL count, not a round ceiling.
#
# 2026-09-06, AGENT CR, the scanner and camera HELP brought up to those
# scenarios: +42 for the eleven and +0 for German. Fifty keys arrive and
# twenty leave. Both printable cards were rewritten around the three
# scenarios, with their reasoning moved out of the numbered steps into a new
# note register (a step may now carry `(heading, body)` notes, closed on
# screen and printed in full); the window's own ⓘ was corrected, having said
# since 2026-07-13 that the target-source choice is "at the top of the window"
# and that the build button reads "Build profile with scanner or camera"
# (in printer mode it reads "Build printer profile"); and the "Which source?"
# ⓘ, the "Save as Defaults" tooltip and the printer-tick log line each gained
# a sentence naming the scenarios. German is translated for all fifty.
#
# GERMAN'S OWN NUMBER FELL 31 -> 4, AND NOT BECAUSE OF THIS CHANGE. Measured
# both sides: German carried exactly 4 echoes before this work and exactly 4
# after. The 31 was a stale ceiling from an earlier batch that this file's own
# rule ("each language's ACTUAL count, not a round ceiling") had already
# outgrown. It is recorded as the actual so a German string arriving
# untranslated is caught the day it arrives.
# 2026-09-06, the colprof algorithm fix (B8-93 to B8-96): +4 for the eleven
# and +0 for German. Eight keys arrive and four leave, and the arithmetic is
# 7 in, 3 out rather than 8 and 4 — MEASURED by diffing the counted SETS
# rather than reasoning about it, because the two ends do not cancel:
#   * of the eight arriving, seven are counted; "ArgyllCMS has two more
#     variants…" opens with the brand name, which the filter above treats as
#     legitimately identical.
#   * of the four leaving, three were counted; the fourth is the Build Profile
#     Algorithm tooltip, which the eleven had actually TRANSLATED. Its
#     replacement is a new key, so it arrives as English and is counted. That
#     is one tooltip going from translated to English until the sweep, and it
#     is the honest cost of rewriting a string whose old translation described
#     eight list entries that no longer exist: a `tr()` key IS its English
#     source, so a stale translation cannot be carried across.
# German is translated for all eight and does not move; its budget of 31 is an
# old ceiling and its actual count is 4. These are each language's ACTUAL
# count, not a round ceiling.
# Re-measured on the merged tree: the help-card rewrite and the colprof
# algorithm fix landed together, so neither branch's table was right alone.
_BUDGET = {
    "de": 4,
    "es": 290,
    "fr": 291,
    "it": 290,
    "ja": 290,
    "nl": 4,
    "no": 290,
    "pl": 290,
    "pt": 4,
    "ru": 289,
    "sv": 4,
    "zh_CN": 289,
}


def _codes():
    return sorted(p.stem for p in _I18N.glob("*.json")
                  if not p.stem.startswith("parameters"))


def _english_echoes(code: str) -> list[str]:
    c = json.loads((_I18N / f"{code}.json").read_text(encoding="utf-8"))
    out = []
    for k, v in c.items():
        if k.startswith("@") or not isinstance(v, str):
            continue
        if v != k:
            continue
        # Strings that are legitimately identical in every language: units,
        # format fragments, brand and file-format names, bare punctuation.
        if len(k) < 25 or not any(ch.isalpha() for ch in k):
            continue
        if k.split()[0] in {"ChromIQ", "ArgyllCMS", "Adobe", "ICC", "sRGB"}:
            continue
        out.append(k)
    return out


@pytest.mark.parametrize("code", _codes())
def test_untranslated_strings_stay_within_budget(code):
    echoes = _english_echoes(code)
    budget = _BUDGET.get(code, 40)
    assert len(echoes) <= budget, (
        f"{code}: {len(echoes)} substantial strings are still English, budget "
        f"is {budget}. Either translate them or raise the budget on purpose.\n"
        + "\n".join(f"    {e[:70]}…" for e in echoes[:5]))


def test_the_echo_detector_is_not_vacuous():
    """Guard the guard: prove the detector can actually see an echo.

    A detector that returns [] because its filters are too greedy would make
    this whole file worthless — which is the failure mode it exists to prevent.
    """
    import tempfile

    sample = ("This is a long English sentence that no translator has touched "
              "yet and which must be counted as an echo.")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "xx.json"
    tmp.write_text(json.dumps({"@language_name": "Test", sample: sample}),
                   encoding="utf-8")
    c = json.loads(tmp.read_text(encoding="utf-8"))
    found = [k for k, v in c.items()
             if not k.startswith("@") and v == k and len(k) >= 25
             and any(ch.isalpha() for ch in k)]
    assert found == [sample], "the echo detector cannot see a plain echo"
