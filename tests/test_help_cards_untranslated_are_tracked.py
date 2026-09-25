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
# RE-MEASURED 2026-09-07, after the English-source fixes for 4.2.0: all
# twelve UNCHANGED. Fourteen keys were re-spelled and every translation
# was carried to the new key, so nothing arrived here as a fresh echo.
# 2026-09-07, the usage-scenario glosses (B8-101): +4 for the eleven and +0
# for German. Each gloss became one line and its full text moved into the
# window's own ⓘ, which is a MOVE and not a rewrite — the tip body is composed
# from the same `tr()` literals the glosses carried, so nothing went stale and
# no translation was lost. What arrives is four genuinely new keys: the three
# one-line glosses and the heading above them in the tip. All four are over
# the 25-character floor this file counts at, so all four are counted. German
# is translated for all four.
#: 2026-09-08, #182: the Measurement Report is judged against LIMIT SETS. 90
#: substantial strings in each of the eleven placeholder languages: the report
#: window's help block (rewritten, so its twelve translations were lost with the
#: key), the Judged-against tooltips, the five-word definition paragraph, the
#: Report limits window's help and legend, the Preferences frame's two tooltips,
#: the unlock confirmation, the provenance sentences, the two proposed section
#: M messages, and the limit-set table's row notes and set blurbs. German is
#: translated for all of them and stays at 4. The eleven carry the English
#: source under the beta rule; the full pass happens before the final release.
#: Same day, after the adversarial review: the Overall summary sentences, the two
#: write-failure windows and the reworded provenance and gamut texts add 16 more.
#: 2026-09-10, #182: REFERENCE sets, a different object from the limit sets
#: above. Eleven Fogra printing conditions are bundled, and 26 of the 37 new
#: keys are over this file's 25-character floor: the eleven set blurbs, four
#: refusal sentences, the Fogra credit line, three coverage sentences, and
#: seven of the labels. German is translated for every one of them and stays
#: at 4. The eleven carry the English source under the beta rule; the full
#: pass happens before the final release. Measured, not rounded.
# 2026-09-11, #182 F7. The Report limits window now says so when the limits
# file a licence holder points CHROMIQ_COMPLIANCE_ISO_FILE at cannot be read,
# which it used to swallow in silence. Those seven strings were translated
# into all twelve languages rather than carried in English under the beta
# rule, so these budgets came DOWN, not up: 141 -> 139 and its neighbours.
# Re-measured, not adjusted: a budget left above the truth admits the next
# untranslated string for free.
# 2026-09-11, #182: the tooltip on the disabled "Show all measurement runs"
# tick, which says why a one-page colour summary does not widen to the whole
# history. One string, over the 25-character floor, German translated and the
# eleven carrying the English source under the beta rule: every budget but de
# goes up by exactly one. Measured against the run that failed, not guessed.
# 2026-09-11, Knut's "shrinking has a floor" ruling (#182): **all twelve
# UNCHANGED.** Nine keys arrive and six go stale, and every one of the nine is
# translated in every one of the twelve, so nothing arrives here as a fresh
# echo. MEASURED by diffing the counted SETS, per language: 0 in, 0 out.
#
# The beta rule — German now, the other eleven before the final — does NOT
# reach these nine, and an earlier draft of this change raised every budget by
# 9 because it did. Each of the nine quotes a ChromIQ control in curly quotes,
# and `test_a_quoted_control_names_the_control_the_reader_has.py` refuses a
# translation that tells a Spanish reader to look for a control called “Clip”
# when the window says «Pinza». That is 238 offences for nine placeholders. A
# string that quotes a control is translated with the string or not added.
# 2026-09-11, THE MERGE OF THE TWO ROUNDS ABOVE. Each round moved this
# table on its own base, so the two disagreed and neither described the
# merged catalogues. The numbers below are MEASURED on the merged tree
# rather than reconciled from the two sides.
# 2026-09-11, #182 items A/B and K7: +3 for the eleven, +0 for German. COUNTED,
# not estimated -- every number below is `_english_echoes(code)` re-run on the
# tree this commit leaves behind, and the eleven really did each move by exactly
# three. Three keys arrive and two go stale:
#   * the hexagon note (`workflow/hex_support.hex_two_heights_note`) is
#     REWRITTEN, not extended: it opened "Hexagonal patches have two heights"
#     and a honeycomb turned 30 degrees has two WIDTHS, so the old sentence was
#     false on that sheet. A `tr()` key IS its English source, so its twelve
#     translations cannot be carried across;
#   * the Custom-paper naming note is rewritten for Knut's two corrections
#     ("mm" in the size, "Square" for a square sheet), same consequence;
#   * `hex_patch_width_row_note` is genuinely new, on the margin inspector's ⓘ.
# German is translated for all three and does not move. The other eleven carry
# the English source under the beta rule (translations are swept before a final,
# not during one), which is why this is +3 and not 0.
# 2026-09-11, THE SECOND MERGE. Three rounds have now moved this table,
# each on its own base. Re-measured on the merged catalogues rather than
# reconciled: a number carried across a merge is a number nobody counted.
# 2026-09-11, #182: M-IMPORT-NOT-A-CHART, the refusal shown when the file
# picked as a chart holds no chart. TWO strings, and only ONE of them counts
# here: the body is long, the headline "That file holds no chart" is 24
# characters and falls under this file's 25-character floor. German is
# translated for both and stays at 4; the eleven carry the English source
# under the beta rule, so every other budget rises by exactly one. Counted
# with this file's own `_english_echoes`, not adjusted upward.
# 2026-09-11, THE THIRD MERGE. Measured again on the merged catalogues.
# 2026-09-11, the from-profile-gamut round. The grey line under "Colours to
# test" is replaced by two sentences that say what actually happened, one per
# case; German is translated, so de does not move (4, unchanged). Of the two
# new keys only ONE is counted here: `_english_echoes` skips anything whose
# first word is "ChromIQ", and the other sentence begins with it. So every
# non-German budget goes up by exactly 1 -- RE-MEASURED on the catalogues this
# commit leaves behind, key by key, not assumed from the count of strings
# added: de 4, es 143, fr 144, it 143, ja 143, nl 143, no 143, pl 143, pt 143,
# ru 142, sv 143, zh_CN 142, and in each of the eleven the one new echo is
# "The reference colour set could not be read...".
# 2026-09-11, THE FOURTH MERGE. Measured again on the merged catalogues.
# 2026-09-11, the adversarial round: the Build Profile tab now says when the
# measurement already in the run carries its CIE columns on the 0..1 scale.
# TWO strings, the label suffix and the Build button's tooltip, and BOTH count
# here (the suffix is 37 characters, over this file's 25-character floor, and
# neither begins with a skipped brand word). German is translated for both and
# stays at 4; the eleven carry the English source under the beta rule, so every
# other budget rises by exactly two. RE-MEASURED with this file's own
# `_english_echoes` on the catalogues this change leaves behind.
# 2026-09-11, Knut's four #182 rulings on alignment and margins. EIGHT strings
# arrive and four go stale, and only SIX of the eight count here: the two
# bodies of M-SCAN-ALIGN-PLACED-UNCHECKED and M-SCAN-ALIGN-PLACED-NOT-SEATED
# both open with the word "ChromIQ", which `_english_echoes` skips. The four
# stale ones were TRANSLATED in all twelve, so they were never echoes and their
# removal moves nothing. German is translated for all eight and stays at 4; the
# eleven each rise by exactly 6. RE-MEASURED with this file's own
# `_english_echoes` on the catalogues this change leaves behind, key by key,
# not derived from the count of strings added.
#
# Three of those six are REWRITES of strings that had real translations in all
# twelve (the two row-indicator raise warnings and the hexagonal Sample-area
# tooltip), so this round loses translated text in the eleven rather than only
# adding untranslated text. The pre-release pass has to pick them up, and
# `--missing` will not name them because a placeholder is present.
# 2026-09-11, the Report-window round on Knut's report of that day (#182 W1 to
# W7). Twelve keys arrive and three go stale in every catalogue. ELEVEN of the
# twelve count here and ONE does not: "Bound, and locked." is 18 characters and
# falls under this file's 25-character floor. All three of the stale keys
# counted, so each non-German budget rises by exactly 8. German is translated
# for all twelve and stays at 4. RE-MEASURED with this file's own
# `_english_echoes` on the catalogues this change leaves behind, key by key,
# not adjusted upward from the old numbers.
# 2026-09-12, merged with the round beside it and MEASURED again on the
# merged catalogues. Each round counted on its own base.
# 2026-09-12, the verification-import round. An i1Profiler export of a
# chart i1Profiler did not generate carries no device values at all, so
# the import now pairs it with the chart by patch NAME, asks the person
# the one thing it cannot check, and states the counts against the SHEET
# as well as the design. EIGHTEEN keys arrive and three go stale.
# SEVENTEEN of the eighteen count here and one does not: "Import it" is
# 9 characters and falls under this file's 25-character floor. The three
# stale keys were TRANSLATED in all twelve catalogues, so they were never
# echoes and their removal moves nothing. German is translated for all
# eighteen and does not move; the eleven others each rise by exactly 17.
# RE-MEASURED with this file's own `_english_echoes` on the catalogues
# this change leaves behind, key by key, never adjusted upward.
# 2026-09-12, the adversarial round after it. A measurement with no device
# values and NO chart beside it had nothing to complete it from and was being
# filed anyway, so `assess` refuses it with ONE new reason sentence, long enough
# to count here. German is translated and does not move; the eleven others each
# rise by exactly 1. RE-MEASURED with this file's own `_english_echoes` on the
# catalogues this change leaves behind, never adjusted upward.
# RE-MEASURED 2026-09-16, the beta 19 text-placement round. Six remedies that
# named a control which does not move what the sentence says it moves are now
# offered only where they work, and say so plainly where they do not; the
# strip-letter notice gained a wording for the layout mode in which "T" is inert.
# **13 keys in, 6 stale out**; all thirteen are long enough to count here and
# all six that went were translated everywhere, so they were never in these
# counts. German is translated and does not move (4); the eleven others carry
# the English source under the beta rule and each rises by exactly 13.
# RE-MEASURED with this file's own `_english_echoes` on the catalogues this
# change leaves behind, never the old number plus thirteen.
# RE-MEASURED 2026-09-16, B8-246: a report is written against ONE limit set,
# so the red line that told a reader the table in front of them was not
# comparable is replaced by three keys naming the measurements left out and
# why. **3 keys in, 0 stale out**; all three are long enough to count here and
# the old warning's two keys are still used as an unreachable backstop and were
# translated everywhere, so they were never in these counts. German is
# translated and does not move (4); the eleven others carry the English source
# under the beta rule and each rises by exactly 3. RE-MEASURED with this file's
# own `_english_echoes` on the catalogues this change leaves behind, never the
# old number plus three.
#
# 2026-09-16, the text round, each of the eleven +6 and de unmoved: SIX keys,
# and two of them are a coverage LOSS rather than new text, so they are named
# here for the pass before GA. The Print Chart tab's "Load image (TIFF)"
# tooltip and its status line both sent the reader to "the grid button", which
# that tab has not had since #130 moved it to the masthead; the new wording
# names "Open Chart File (.ti2)" instead, and because the key changed, eleven
# languages dropped from a real translation to the English. The other four are
# text that was never translatable at all: the averaging-failed window's body
# (title through tr(), body not) and the three sentences of the lp-path print
# warning, all four hidden from `i18n_extract.unwrapped_literals` by a `+` in
# the argument. German is written for all six.
_BUDGET = {
    # RE-MEASURED 2026-09-25, K39 (Knut #182 5831246553: B8-1111 to B8-1114, M-REPORT-WORKED-OUT-EARLIER without "Update works the report out again.", M-REPORT-WORKED-OUT-DIFFERENTLY-UPDATE-OR-NEW and M-REPORT-NEW-REPORT-SETTINGS titles and bodies, the "New report…" tooltip, and the audit's rewordings: "the profile runs it is drawn from", the colorimetric-missing paragraphs, the Paper white graph's reason). 10 keys in, 6 out. German by hand, does not move; the twelve others carry the English under the beta rule and each rises by exactly 5 (5 of the 6 retired keys were English echoes there). COUNTED off the tree rebased onto 1c4995c2, BOTH ledgers.
    # RE-MEASURED 2026-09-25, B8-1097 (Basti: the gear window gets OK and Close; its third paragraph now says "OK keeps your choice; Close leaves the lists as they were."). One key replaced by one: German by hand, does not move; the twelve others carried the old sentence in English already (K35, beta rule), so each loses one English echo and gains one and does not move. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-25, challenge 5 of beta 42 fixes (B8-1091 to B8-1095: M-REPORT-WORKED-OUT-EARLIER, title and body, and the two true reasons an empty trend graph gives). German by hand, does not move; the twelve others carry the English under the beta rule and each rises by exactly 4. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, K37 (B8-1081 to B8-1088: M-REPORT-PAPER-WHITE-FROM-PROFILE, M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE, M-REPORT-STRIP-CORNERS-PREDICTED and M-REPORT-STRIP-CORNERS-IDEAL, titles and bodies, and the (e) line of "How the colours were judged"). German by hand, does not move; the twelve others carry the English under the beta rule and each rises by exactly 9. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, K36 (B8-1061 to B8-1068: the ISO report type holds "Judged against" to the four ISO sets and its refusal lines, the Preferences type help, the Dictionary's profile run, verification run and calibration run, the Run type entry, the help cards' and the report's run words, M-REPORT-NO-PAPER-PATCH reworded). German by hand, does not move; the twelve others carry the English under the beta rule. COUNTED off the tree rebased onto 3d05ec2b (challenge 3 fixes, B8-1051 to B8-1053, the 4.3 landing page), BOTH ledgers.
    # RE-MEASURED 2026-09-24, challenge 3 fixes of beta 42 (B8-1031 to B8-1040: the ISO heading and the two ISO lines, the red line while Generate is greyed, the greyed controls' tooltip) rebased onto B8-1011 to B8-1016 and B8-1041. German by hand; the others carry the English under the beta rule. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, K34 (B8-1011 to B8-1016: M-REPORT-SCOPE-RUN-DELETED's title and two bodies, M-REPORT-NO-PAPER-PATCH's title and body, "Paper white" as a note's label) rebased onto K35 (B8-1021 to B8-1024). German by hand, does not move; the twelve others carry the English under the beta rule and each rises by exactly 6 here and 5 in the echo budget ("Paper white" is under 25 characters). COUNTED off the rebased tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, K35 (B8-1021 to B8-1024: the curated built-in presets, the gear button's window, the arrow rows, the Manual Presets help with the gear line). German by hand; the others carry the English under the beta rule. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, B8-1008 (the trend title names no printer) merged. COUNTED off the merged tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, challenge round 2 fixes (B8-1001 to B8-1007) merged onto K33 (B8-991 to B8-999). German by hand; the others carry the English under the beta rule. COUNTED off the merged tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, K33 (B8-992 to B8-999: the presets window's intro, Any and its count lines, the repeatability note, Sort by and its two entries, the ISO-use paragraph, the Custom blurbs, the refusal of an ISO type without values, the two report help paragraphs). German by hand; the twelve others carry the English under the beta rule. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, K32 (B8-981 to B8-990: the Printing record's graph sentence, the empty window's three sentences, the reordered Update / Create New bodies) merged onto B8-974 and B8-978. German by hand; each of the others carries the English under the beta rule. COUNTED off the merged tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, B8-978 (Custom ISO columns, three texts re-keyed, all already English outside German) merged with B8-974 (All metrics). COUNTED off the merged tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, B42 (B8-974): "All metrics" in the presets window, five keys in, and the FROM PROFILE GAMUT remedy says "metric" for "row" (its translations lost under the beta rule). German by hand, does not move; the eleven translated languages rise by exactly 6, Ukrainian (which carried that remedy in English already) by 5. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, B42 (B8-965, B8-968): the Max strip length tooltips, two keys in and the (i) help text changed. German by hand, does not move; the twelve others carry the English under the beta rule and each rises by exactly 3. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, the translation credit removed from Settings (Basti). COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-24, B40-B (B8-940 to B8-952), the beta 40 challenge B text fixes: German by hand; the twelve others carry the new English under the beta rule. COUNTED off the tree with this file's own expression, BOTH ledgers.
    # RE-MEASURED 2026-09-24, B40-A (B8-935 to B8-939): one key in, the "Judged against" tooltip for a set carried over from an earlier ChromIQ. German by hand, so it does not move; the twelve others carry the English and each rises by exactly 1. COUNTED off the tree, BOTH ledgers.
    # RE-MEASURED 2026-09-24, K31-A (B8-890 to B8-899) and K31-B (B8-900 to B8-909) cherry-picked onto beta 39 (B8-910 to B8-925). COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, the R2 text fixes (B8-911 to B8-915) merged onto the help fixes. COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, the beta 39 help fixes (B8-910) merged onto the R1 fixes. COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, the R1 fixes (B8-916 to B8-919): M-REPORT-UPDATE-NOTHING-LEFT and "covers no measurement". COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, K31 metrics (B8-900 to B8-907): the version 1 names, rule A, the neutral aims, the evenness line and their help texts; German by hand, the twelve others English under the beta rule. COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, the report-window fixes (B8-880 to B8-886) merged onto the challenge C fixes. COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, the challenge C fixes (B8-870 to B8-873) merged onto K30. COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, G7 (B8-848) merged onto K28a. COUNTED, BOTH ledgers.
    # RE-MEASURED 2026-09-23, K28a (B8-846) merged onto Calibration and G12.
    # COUNTED off the merged tree, BOTH ledgers.
    # RE-MEASURED 2026-09-23, Calibration reports (B8-844) merged onto the G12
    # notes (B8-845). COUNTED off the merged tree, BOTH ledgers.
    # RE-MEASURED 2026-09-23, #182 beta 39 G12 (Knut 5774852534, "OK" in
    # 5775260868): three new keys (the Printing record's notes heading
    # "Notes on the values above:", its closing sentence, and the detailed
    # gamut paragraph without "The Result judges"). German by hand, does not
    # move; the twelve others carry the English under the beta rule and each
    # rises by exactly 3. COUNTED off the tree with this file's own
    # expression, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-23, the beta 38 challenge-round fixes and Knut's
    # 5794078008 (the folder-renamed window's three choices): 23 new keys
    # (the rename refusals in words, M-PROJECT-FOLDER-RENAME-FAILED's and
    # M-PROJECT-FOLDER-RENAMED's bodies reworded, the Colour accuracy legend
    # "(ΔE00)", three folder-guide rows that no longer promise a
    # recalculation, the window's three buttons) and 10 retired. German by
    # hand and unmoved; each of the twelve others rises by exactly 6.
    # COUNTED off the tree with this file's own expression, BOTH ledgers in
    # the same commit.
    # RE-MEASURED 2026-09-23, #182 K26 (Knut 5792484060), on top of beta 38's
    # E2 round: 20 new keys and 2 changed ones, the old two gone from every
    # catalogue. German by hand and unmoved; each of the twelve others rises
    # by exactly 13 (the new keys long enough to count here, less the two
    # retired ones). COUNTED off the tree with this file's own expression,
    # BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-23, #182 K25 graphs, on top of the K25 list round:
    # 26 new keys, 24 of them long enough to count here (the two short ones
    # are placeholder templates). German by hand and unmoved; the twelve
    # others carry the English under the beta rule and each rises by exactly
    # 24. COUNTED off the tree with this file's own expression, BOTH ledgers
    # in the same commit.
    # RE-MEASURED 2026-09-23, the fixes for the two challenge rounds before
    # beta 37: report text reworded for K18 ("the test chart used", no
    # "you"/"your", no ChromIQ explanation), the evenness noise note
    # (A-F3/B-H2), the worst-5 % note (B-M5), the one-page ISO summary
    # (B-M1), the translated title prefixes (B-H5) and one new strip
    # message (B-M7). German by hand, and two report lines that were still
    # English in German translated, so de falls; the twelve others carry
    # the new English under the beta rule. COUNTED off the tree with this
    # file's own expression, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-23, the trend graphs (#182 K20/K21): unchanged in
    # every language, because the eleven new keys are all under 25 characters.
    # Its twin `_IDENTICAL_TO_KEY` rose in the same commit.
    # RE-MEASURED 2026-09-23, the evenness rows (B8-814) merged onto K22/K24:
    # the new evenness strings are German by hand and English placeholders in
    # the twelve others. COUNTED off the merged tree, BOTH ledgers.
    # RE-MEASURED 2026-09-23, K22 (Knut: every N-A note names what is missing
    # in the measured chart, never what to add or where). Twenty-seven reason
    # sentences reworded ("the measured chart", no instructions). German by
    # hand; the twelve others back to English placeholders for the reworded
    # keys. COUNTED off the tree, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-23, the final round before beta 36 (K18 again):
    # six report sentences that still explained ChromIQ reworded (bound and
    # locked, the recorded-verdict line, the verification bullet, the drift
    # paragraph, the example-colours line, the summary footer), and one key
    # added (the mixed-kinds Generate tooltip). German by hand; the twelve
    # others back to English placeholders for the reworded keys. COUNTED off
    # the tree, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-23, K18 (Knut: report text is for a customer; it
    # never explains the past or how to use ChromIQ). Twelve report strings
    # reworded: the COND, INFO and drift lines of the guide, the standard
    # paragraph and its caveat, the three standard summaries, the Printing
    # record and nothing-checked summaries, and the example-colours line; one
    # key folded into the existing "not recorded". German by hand, so it does
    # not move. The twelve others had TRANSLATED the old sentences, and a
    # translation of the old text under the new key would say the old thing,
    # so each is back to the English placeholder under the beta rule and the
    # counts rise. COUNTED off the tree, BOTH ledgers in the same commit.
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
    # RE-MEASURED 2026-09-22, for Knut's retirement of the ISO COND cap and
    # the two pieces of text he asked for in the same conversation. FOUR keys
    # out (the report guide's COND bullet, its standards paragraph, the
    # Getting Started glossary's Overall entry, and STANDARD_CAVEAT, all four
    # of which taught or carried the cap) and EIGHT in (their replacements
    # plus M-VERIFY-UNCHECKED-METRICS and M-REPORT-PATCH-COUNTS-DIFFER, a
    # title and a body each). German is written by hand and does not move: 22
    # before and 22 after, which is the check that the hand translation really
    # landed rather than falling back to the English.
    #
    # **UKRAINIAN MOVES BY 4 AND THE OTHER ELEVEN BY 5, AND THAT IS NOT AN
    # INCONSISTENCY.** Measured per language rather than assumed: all four
    # departing keys were English echoes in `uk`, and only three of the four
    # were in the others, because one of them was genuinely translated there.
    # 8 in minus 4 counted out is +4; 8 minus 3 is +5.
    #
    # COUNTED with this file's own `_english_echoes`, off the tree, never the
    # old number plus a guess, and BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-22, for Knut's ruling that the unchecked values
    # shall be listed. The ISO summary sentence is now three sentences, one
    # per case, because the promise was unconditional and a column with
    # nothing unchecked also said the unchecked values were listed below.
    # German by hand; the twelve others carry the English under the beta
    # rule. COUNTED off the tree, BOTH ledgers this time.

    # RE-MEASURED 2026-09-22, and this ledger was MISSED when its twin was
    # updated earlier the same day. Three gate runs came back red identically,
    # twelve failures each, which is what a deterministic miss looks like:
    # `tests/test_i18n.py::_IDENTICAL_TO_KEY` had been re-measured for Knut's
    # beta 32 batch and this one had not. The two are named together in the
    # project's own rules for exactly this reason, and updating one of them is
    # not updating the ledgers.
    #
    # The batch: the Report limits button renamed "Restore defaults", the
    # Measurement Report saying which metrics a report type judges, and the
    # verification pre-flight corrected to ask the generic question. German is
    # written by hand and moves by nothing; the twelve others carry the English
    # source under the beta rule.
    #
    # COUNTED with this file's own `_english_echoes`, off the tree, never
    # adjusted upward to make a run pass.

    # RE-MEASURED 2026-09-21, Knut's help-card batch (issue #182, 2026-09-20
    # 20:58): the workflow steps of twelve cards rewritten into his
    # to-do-steps-first shape with the reasoning in collapsible notes, the
    # verification card brought up to date with the preset-eligibility window
    # and the Measurement Report, the folder guide given the folders and files
    # the report work introduced, and thirty new Dictionary terms. 324 keys
    # arrive and 69 retire.
    #
    # **German is written by hand for all 324, so `de` does not move except by
    # ONE**: the Dictionary headword "FOGRAxx (FOGRA39, FOGRA51, FOGRA61 …)"
    # is nothing but Fogra's own set identifiers and is the same string in
    # every language, so it is legitimately identical and is counted here
    # because it does not begin with a brand word this file already excuses.
    # The eleven others carry the English under the project's beta rule and
    # rise by 293 each: 324 new keys minus the 31 that fall under this file's
    # own 25-character floor.
    #
    # COUNTED with this file's own `_english_echoes`, off the tree, never
    # adjusted upward to make a run green.
    # RE-MEASURED 2026-09-20, challenge round 31 on the Fogra reference-set
    # door. Seven new strings, of which FIVE are long enough for this file to
    # count: the "no copy of that set shipped" sentence, the too-large refusal,
    # the duplicate-member refusal, and two of the four "which file is in
    # force" lines. German is written by hand for all seven, so de does not
    # move; the eleven others carry the English under the beta rule and rise by
    # exactly 5. COUNTED with this file's own `_english_echoes`, never adjusted
    # upward.
    # RE-MEASURED 2026-09-20, Knut's beta 25 batch in one sweep. German is
    # translated by hand throughout, so de does not move; the eleven others
    # carry the English under the beta rule. COUNTED with this file's own
    # `_english_echoes`, never adjusted upward.
    # RE-MEASURED 2026-09-20, Knut's beta 25 batch in one sweep. German is
    # translated by hand throughout, so de does not move; the eleven others
    # carry the English under the beta rule. COUNTED with this file's own
    # `_english_echoes`, never adjusted upward.
    # RE-MEASURED 2026-09-20, Knut's beta 25 batch in one sweep. German is
    # translated by hand throughout, so de does not move; the eleven others
    # carry the English under the beta rule. COUNTED with this file's own
    # `_english_echoes`, never adjusted upward.
    # RE-MEASURED 2026-09-19, the round-26 printing refusal and the round-27
    # report fixes landing together: the macOS print dialog now says why it
    # cannot carry a four-ink chart (one body long enough to count), and the
    # "Show detailed data" help was rewritten. German is translated for all of
    # them, so de does not move; the eleven others carry the English under the
    # beta rule. COUNTED with this file's own `_english_echoes`, never
    # adjusted upward.
    # RE-MEASURED 2026-09-18, round 19: one more long string, the plural of
    # the numberless scope sentence. Every language up by exactly 1.
    # RE-MEASURED 2026-09-18, round 18: the report's scope sentence gained a
    # second wording for a folder that cannot be counted. One new string long
    # enough to count, so every language rises by exactly 1. Counted with this
    # file's own `_english_echoes`.
    # RE-MEASURED 2026-09-18, round 13 on the B8-346 fixes: the Measurement
    # Report's scope sentence gained a second form for a document drawn from
    # more than one project. ONE new string long enough to count, so every
    # language rises by exactly 1, German included, because this family is on
    # the beta rule (its sibling sentence is an English placeholder in German
    # too). The two chart-layout help texts changed again in the same pass and
    # do NOT move the number: they were already counted as English. Counted
    # with this file's own `_english_echoes`, never adjusted upward.
    # MERGED 2026-09-16: two branches raised this for different reasons, and
    # these numbers are neither side's and not their sum. They are counted
    # off the merged catalogues, because a budget adjusted upward admits the
    # next regression for free.
    # RE-MEASURED 2026-09-16, B8-250: the "Saved reports" row and its delete
    # question. **10 keys in, 0 stale out**; five of the ten are long enough to
    # count here (the tooltip, the refusal, the two delete bodies and the
    # delete title falls under the 25-character floor, so: the tooltip, the
    # refusal and the two bodies, plus "Saved reports ({run}):"). German is
    # translated and does not move (4); the eleven others each rise by exactly
    # 5. RE-MEASURED with this file's own `_english_echoes`, never adjusted
    # upward from the old numbers.
    # RE-MEASURED 2026-09-17: the two chart-layout help texts. Knut asked for
    # the difference between the two layout methods to be explained properly,
    # including that "Prioritise patch size" comes from ArgyllCMS's printtarg
    # and inherits its limitations. The "Create layout" tooltip and the Create
    # Chart step help were both rewritten, so the translations the OLD wording
    # had do not carry over, and both are long enough to count here. Every
    # language rises by exactly two, GERMAN INCLUDED this time, because these
    # two were translated in German where the last batch's five were not.
    # Counted with this file's own `_english_echoes`, never adjusted upward.
    # RE-MEASURED 2026-09-18, the beta-20 batch, and German moves most because
    # German was the only language that HAD these strings translated. Four
    # pieces of work, all of them replacing text rather than adding it:
    # Knut's ruling that the Measurement Report reads as a document printed for
    # a customer (five sentences rewritten or removed), the Patch Set editor's
    # two counting rows, the chart-layout help written twice (the first rewrite
    # was measured false on 154 of the 160 built-in charts, so it was written
    # again from the real mechanism), and the Settings strip-length list, which
    # named four instruments where the combo offers five.
    # Counted with this file's own `_english_echoes`, never adjusted upward.
    # RE-MEASURED 2026-09-18, B8-380/B8-383: the generated-reports control.
    # Fourteen keys in, eight stale out; three of the fourteen are long enough
    # to count here (the list's own tooltip and the two bodies of the revised
    # M-REPORT-DELETE). German is translated in the same commit and does not
    # move; the eleven others each rise by exactly 3 under the beta rule.
    # Counted with this file's own `_english_echoes`, never adjusted upward.
    # RE-MEASURED 2026-09-18, B8-388/B8-391/B8-392: the Measurement Report
    # defaults. Seventeen keys in, six stale out; EIGHT of the seventeen are
    # long enough to count here (the three Preferences help texts, the "New
    # report…" tooltip, the Measure tab's "Save measurement report" help, the
    # one-measurement sentence beside "Show all measurement runs", the unlock
    # question with its false clause removed, and the two Preferences tick-box
    # labels). German is translated in the same commit and does not move; the
    # eleven others each rise by exactly 8 under the beta rule.
    # Counted with this file's own `_english_echoes`, never adjusted upward.
    # RE-MEASURED again the same evening, one LOWER: the on-screen run of the
    # new defaults photographed two sentences that had become false with
    # B8-391 (the unlock tick box's own label, and the two tooltips that
    # promised a recalculation the door no longer does). Rewriting them
    # retired one long English placeholder in the eleven languages.
    # RE-MEASURED 2026-09-18 for B8-397, the five limit rows that had no
    # detection method. Twenty-two new strings in the limits and report
    # windows, German translated in the same commit (so `de` does not move) and
    # twenty-one substantial ones left English in the other twelve, which is
    # the standing rule during a beta. Counted with this file's own
    # `_english_echoes`, never adjusted upward.
    # RE-MEASURED 2026-09-19, beta 22, with TWO change sets in the tree at once,
    # and the split is recorded because they are not one piece of work:
    #
    # * the control-strip declaration (B8-405) adds 6 keys, **all six
    #   translated into German in the same commit**, of which 5 are long enough
    #   to count here. German therefore does not move for them; the other
    #   eleven carry the English source under the beta rule and rise by 5;
    # * the "Which presets can be verified?" window adds 38 keys, untranslated
    #   in every language, 28 of them long enough to count. German does not
    #   move either, because its own count is already 20 against a budget of 20
    #   and none of those 28 is in the family this file counts for `de`.
    #
    # So `de` stands still at 20 and each of the other eleven rises by exactly
    # 33. COUNTED with this file's own `_english_echoes` over the catalogues as
    # they stand, never adjusted upward: 245 -> 278 and its neighbours.
    # RE-MEASURED 2026-09-19, and the tree held TWO change sets when it was
    # counted, so the split is written down rather than left as "+3":
    #
    # * the round-26 fix set, already committed (e85f2630 / 49094c3a): the
    #   Apply Calibration output placeholder and the printcal success window's
    #   next step were both rewritten, so eleven languages dropped from a real
    #   translation to the English source. Both are long enough to count here.
    #   `_IDENTICAL_TO_KEY` in `test_i18n.py` was moved for them and this was
    #   not, which is why the two numbers disagreed by two;
    # * round 27 (R27-F1): the Measurement Report's "Show detailed data for
    #   each run" help ended *"which is why it starts unticked"*, which stopped
    #   being true when P.3 made the box default ON. The replacement names the
    #   Preferences lever instead. ONE key in, one stale out, German translated
    #   in the same change set.
    #
    # So `de` stands still at 20 and each of the other eleven rises by exactly
    # 3. COUNTED with this file's own `_english_echoes` over the catalogues as
    # they stand, never adjusted upward from the old numbers.
    # RE-MEASURED 2026-09-19, Knut's beta 25 Create Chart batch (B8-444 to
    # B8-450). The preset-eligibility window is renamed, says "metric" where it
    # said "row", and gained the From-Profile-Gamut note: **17 keys in, 11
    # stale out**, of which 14 in and 10 out are long enough for this file to
    # count, so each of the eleven non-German catalogues rises by exactly 4.
    #
    # `de` STANDS STILL AT 20. Sixteen of the seventeen are translated into
    # German in the same change; the seventeenth, `{metric}: {explanation}`,
    # is two placeholders with no German to write and is under this file's own
    # 25-character floor, so it is not counted here at all (it IS counted by
    # `_IDENTICAL_TO_KEY` in test_i18n.py, which has no floor -- that is why
    # the two ledgers move by different amounts this time).
    #
    # Three of the seventeen came from the concurrent Measurement Report work
    # sharing this tree, not from this change set; see the same note in
    # test_i18n.py.
    #
    # COUNTED with this file's own `_english_echoes` over the catalogues as
    # they stand, never adjusted upward.
    # RE-MEASURED once more the same evening for B8-464 (see the same note in
    # test_i18n.py): the Report limits window's two ISO sentences, stale since
    # `1db705f1`. Both are long enough to count here, both are translated into
    # German in the same change, so **de stands still at 20** and each of the
    # eleven others rises by exactly 1. COUNTED, not adjusted.
    # 2026-09-19, Knut's beta-25 report-window ruling (B8-490 / B8-491). THREE
    # of the round's six new keys are long enough for this detector to see: the
    # three-button question's body and the two tick-box tooltips, which are
    # rewordings rather than additions and so cost one key in and one key out
    # each -- no movement from those two. What moves each non-German budget is
    # the question's body, plus the two tooltips only insofar as their OLD text
    # was already an English echo in those eleven and their NEW text still is:
    # counted rather than reasoned, every non-German budget rises by exactly 3
    # and German does not move (20, unchanged), because all six are translated
    # by hand in the same change. RE-MEASURED with this file's own
    # `_english_echoes` on the catalogues this commit leaves behind, never
    # adjusted upward.
    # RE-MEASURED 2026-09-20, Knut's beta 26 review (B8-520 to B8-526). Nine
    # new keys, of which EIGHT are long enough for this detector to see: the
    # four sentences a greyed "Unlock this run's limits" owes the reader, the
    # two the one-page summary owes it, the type bullet that says what a Colour
    # summary cannot hold, and the sentence saying why "Judged against" is not
    # the Preferences default. ("What each set is" is too short to count.)
    # German is translated by hand in the same change, so **de does not move
    # (21)** and each of the eleven others rises by exactly 8. RE-MEASURED with
    # this file's own `_english_echoes` on the catalogues this change leaves
    # behind, never adjusted upward.
    # RE-MEASURED 2026-09-20, the Fogra reference-set upgrade path: a user may
    # point ChromIQ at a newer Fogra file, per set, without a new ChromIQ.
    # Twenty-eight keys in and two out, of which FOURTEEN are long enough and
    # wordy enough for this detector to see -- the ⓘ card for the new section,
    # the five sentences that refuse a file ChromIQ cannot read, the two that
    # refuse an archive, the "you supplied this" provenance sentence, the one
    # that says nothing in the file says whether it is a real paper, the
    # archive-version line, the "nothing in that archive could be used" line
    # and the "it has also changed" clause. German is translated by hand in the
    # same change, so **de does not move (21)**, and each of the eleven others
    # rises by exactly 14. COUNTED with this file's own `_english_echoes` on
    # the catalogues this change leaves behind, never adjusted upward.
    # RE-MEASURED 2026-09-20, B8-548: the ISO half of the Reference values
    # window answered a bad file with a raw Python exception string, and now
    # answers it with two sentences ChromIQ wrote, the way the Fogra half of
    # the same window already did. Both are long enough for this detector to
    # see. German is translated by hand in the same change, so **de does not
    # move (21)** and each of the eleven others rises by exactly 2. COUNTED
    # with this file's own `_english_echoes` on the catalogues this change
    # leaves behind, never adjusted upward.
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
    # RE-MEASURED 2026-09-23, K25 (the grouped "Report shown" list, #182):
    # two headings and two "Where are my files" rows, all of 25 characters
    # or more, so the twelve rise by exactly 4; the two M-REPORT-DELETE keys
    # were renamed in place and were already English there. German by hand,
    # does not move. COUNTED off the tree, BOTH ledgers in the same commit.
    # RE-MEASURED 2026-09-23, #182 beta 38 E2 (page coverage): nine new keys
    # (the coverage notes, the two lines of the presets window, the pages left
    # out) and three changed ones (the evenness help and remedy text, and
    # M-REPORT-CHART-MISMATCH-LAYOUT). German by hand, does not move; the twelve
    # others carry the English under the beta rule and each rises by exactly 9.
    # COUNTED off the tree with this file's own expression, BOTH ledgers in the
    # same commit.
    # RE-MEASURED 2026-09-23, #182 S-2 (§23, the ISO values prepared to ship):
    # eight new keys (the per-column ISO clauses, "The two ISO columns are
    # read-only.", the shipped variants of the Custom note and of the
    # Reference values line) and twelve changed ones whose old keys left every
    # catalogue. German by hand, does not move; each of the twelve others
    # rises by exactly 6 under the beta rule. COUNTED off the tree, BOTH
    # ledgers in the same commit.
    # RE-MEASURED 2026-09-23, #182 K30: the same 25 keys in and 8 out; the
    # twelve rise by exactly 15 (the new keys of 25 characters or more, less
    # the retired English echoes), German falls by one (the Report limits
    # intro is translated now). COUNTED off the tree, BOTH ledgers in the
    # same commit.
    # RE-MEASURED 2026-09-25, K39-7 (B8-1101 to B8-1104, Knut #182 5831246553):
    # Export list and Import list, 23 keys in, none out. German by hand, does
    # not move; each of the twelve others rises by exactly 17 (the new keys of
    # 25 characters or more) under the beta rule. COUNTED off the tree, BOTH
    # ledgers in the same commit.
    "de": 13,
    "es": 989,
    "fr": 990,
    "it": 989,
    "ja": 989,
    "nl": 989,
    "no": 989,
    "pl": 989,
    "pt": 989,
    "ru": 988,
    "sv": 989,
    "zh_CN": 988,
    "uk": 1132,
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
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="chromiq-test-")) / "xx.json"
    tmp.write_text(json.dumps({"@language_name": "Test", sample: sample}),
                   encoding="utf-8")
    c = json.loads(tmp.read_text(encoding="utf-8"))
    found = [k for k, v in c.items()
             if not k.startswith("@") and v == k and len(k) >= 25
             and any(ch.isalpha() for ch in k)]
    assert found == [sample], "the echo detector cannot see a plain echo"
