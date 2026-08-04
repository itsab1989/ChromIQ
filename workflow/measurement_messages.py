"""The approved message catalogue — §M of the Unified Measurement Management
model, transcribed and used verbatim.

Knut, #130 beta.125: *"Only approved message text shall be used in any of the
windows. Verify that ALL message windows in the code for the Measurement
Management model conforms with the defined and reviewed Unified Measurement
Management model."*

He was right to ask. The first implementation wrote its own sentences —
better ones in places, but not the reviewed ones — and there was no way to
check the difference short of reading both documents side by side. So the
catalogue now lives **here**, once, and every window takes its text from it.
`tests/test_message_catalogue.py` parses §M out of
`docs/design/unified_measurement_management.md` and fails if the two disagree,
which is what makes "conforms with the model" a fact rather than a claim.

**Changing a message means changing the model.** Edit §M in the design
document and this module together, and say so on the issue — the text is
Knut's to approve, not mine.

Two conventions:

* ``{placeholders}`` are filled by the caller with real numbers. A message is
  never shown with one left in it (``tests/`` check this).
* IDs marked **PROPOSED** below are cases the reviewed model does not cover
  yet. They exist because the alternative was a window that prints something
  false — see ``M_REPLACE_UNCOUNTABLE``. They are flagged in the design
  document too, and listed on the issue for approval.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.i18n import tr


@dataclass(frozen=True)
class Message:
    """One entry of §M: an ID, a headline, and the body under it.

    Where a message states a count it carries **two** bodies. Knut, #130
    2026-08-03: *"Yes, use house rule with real singular and plural. You do not
    need to ask about this."* — so "1 dated verification measurements" never
    reaches the screen, and neither does the bracketed "(s)".
    """

    id: str
    title: str
    body: str
    #: False while the reviewed model does not carry this message yet.
    approved: bool = True
    #: The body used when :attr:`count_key` is exactly 1.
    body_one: "str | None" = None
    #: Which placeholder decides singular from plural.
    count_key: str = ""

    def render(self, **kw) -> "tuple[str, str]":
        """(title, body) with the placeholders filled and nothing left over."""
        body = self.body
        if (self.body_one is not None and self.count_key
                and kw.get(self.count_key) == 1):
            body = self.body_one
        title = tr(self.title).format(**kw) if "{" in self.title else tr(self.title)
        return title, tr(body).format(**kw)


def _m(id_: str, title: str, body: str, *, approved: bool = True,
       body_one: "str | None" = None, count_key: str = "") -> Message:
    return Message(id_, title, body, approved, body_one, count_key)


# ---------------------------------------------------------------------------
# §5 — starting a measurement over an existing one
# ---------------------------------------------------------------------------
M_REPLACE_PARTIAL = _m(
    "M-REPLACE-PARTIAL",
    "This run already holds part of a measurement",
    "{c} of the chart's {a} patches have been read. Starting now without "
    "“Refine / resume existing measurement” replaces them.\n\n"
    "Tick that option to keep what you have and read only the patches that are "
    "still missing. The existing measurement is moved to the run's “old” "
    "folder either way, so nothing is lost.\n\n"
    "The measurement file is:\n{path}",
    count_key="c",
    body_one=
    "One of the chart's {a} patches has been read. Starting now without "
    "“Refine / resume existing measurement” replaces it.\n\n"
    "Tick that option to keep what you have and read only the patches that are "
    "still missing. The existing measurement is moved to the run's “old” "
    "folder either way, so nothing is lost.\n\n"
    "The measurement file is:\n{path}")

M_REPLACE_COMPLETE = _m(
    "M-REPLACE-COMPLETE",
    "This chart is fully measured",
    "All {a} patches have been read, and this run's profile was built from "
    "that measurement.\n\n"
    "Starting a new measurement replaces it. The finished measurement is moved "
    "to the run's “old” folder and nothing is deleted — but the profile in this "
    "run will no longer match the measurement beside it until you build it "
    "again.\n\n"
    "Refine / resume is left exactly as you set it before pressing Start; this "
    "window does not change your choice.\n\n"
    "The measurement file is:\n{path}")

M_TI3_MISMATCH = _m(
    "M-TI3-MISMATCH",
    "This run's measurement and its chart do not match",
    "The measurement file holds {c} readings, and the chart ({stem}.ti2) "
    "describes {a} patches. {extra}\n\n"
    "ChromIQ cannot tell which of the two is the wrong one. A measurement can "
    "be cut short by an interrupted session, and a chart can be replaced or "
    "edited outside ChromIQ — both look the same from here.\n\n"
    "What each button does:\n\n"
    "•  Start a fresh measurement — the safe choice if this chart is the one "
    "you printed. The existing measurement is moved to the run's “old” folder "
    "and nothing is lost.\n\n"
    "•  Cancel and look at the files first — the run is at {path}. This run's "
    "“chart” folder holds the copy of the chart that was stored when it was "
    "last measured, and “Restore Used Chart” puts that copy back. There is "
    "exactly one; ChromIQ does not keep earlier versions of a chart.\n\n"
    "Resuming is not offered here, because resuming into a mismatch would "
    "write readings against patch positions that may not be the ones on your "
    "paper.",
    count_key="c",
    body_one=
    "The measurement file holds one reading, and the chart ({stem}.ti2) "
    "describes {a} patches. {extra}\n\n"
    "ChromIQ cannot tell which of the two is the wrong one. A measurement can "
    "be cut short by an interrupted session, and a chart can be replaced or "
    "edited outside ChromIQ — both look the same from here.\n\n"
    "What each button does:\n\n"
    "•  Start a fresh measurement — the safe choice if this chart is the one "
    "you printed. The existing measurement is moved to the run's “old” folder "
    "and nothing is lost.\n\n"
    "•  Cancel and look at the files first — the run is at {path}. This run's "
    "“chart” folder holds the copy of the chart that was stored when it was "
    "last measured, and “Restore Used Chart” puts that copy back. There is "
    "exactly one; ChromIQ does not keep earlier versions of a chart.\n\n"
    "Resuming is not offered here, because resuming into a mismatch would "
    "write readings against patch positions that may not be the ones on your "
    "paper.")

#: The trailing sentence of M-TI3-MISMATCH, only when the file also disagrees
#: with itself (§3a's ``B ≠ C``).
M_TI3_MISMATCH_EXTRA = (
    "The file's own header claims {b} readings, which does not match the {c} "
    "it contains — so this file may be damaged as well as mismatched.")

# --- PROPOSED: cases the reviewed model does not cover yet ------------------
M_REPLACE_UNCOUNTABLE = _m(
    "M-REPLACE-UNCOUNTABLE",
    "This run already holds a measurement file",
    "ChromIQ cannot tell how many readings it contains — the file is there, "
    "but it holds no readable measurement data. That usually means a session "
    "ended before the first patch was read, or the file was changed outside "
    "ChromIQ.\n\n"
    "Starting now writes a new measurement in its place. The file you have is "
    "moved to the run's “old” folder and nothing is deleted, so you can always "
    "look at it afterwards.\n\n"
    "Refine / resume is not offered for this file, because there is nothing in "
    "it to resume from.\n\n"
    "The measurement file is:\n{path}")      # approved by Knut, 2026-08-04

#: **Removed 2026-08-04.** There was a proposed M-REPLACE-NO-CHART for
#: "readings, but no chart beside them to count against". Knut asked whether
#: that condition can arise at all — *"Can a chart read at all be initiated if
#: a ti2 file does not exist? I thought it could not."* Measured: Start
#: Measurement **was** offered without a `.ti2`, because the Measure tab can be
#: loaded from the `.ti1`. That was a bug, not a case needing a message, and it
#: is fixed in `TabMeasure.set_ti1_path`. With Start unavailable the condition
#: cannot occur, so the message is gone rather than unused.
# ---------------------------------------------------------------------------
# §4 — chart integrity
# ---------------------------------------------------------------------------
M_CHART_PROFILING = _m(
    "M-CHART-PROFILING",
    "This run already holds work made with the chart you are about to replace",
    "Replacing the chart in this run means what is here no longer describes "
    "it:\n\n{items}\n\n"
    "Everything is moved to the run's “old” folder and nothing is deleted — "
    "but this run would no longer hold a matching set of files.\n\n"
    "Duplicate the run and make the new chart in the copy if you want a "
    "different chart while keeping this run's work.\n\n"
    "The “old” folder is here:\n{folder}")

#: The {items} of M-CHART-PROFILING. §M: *"{items} lists only what is actually
#: present"*.
M_CHART_ITEM_MEASUREMENT = "•  a measurement of {c} patches"
M_CHART_ITEM_MEASUREMENT_ONE = "•  a measurement of one patch"
M_CHART_ITEM_PROFILE = "•  the profile built from it"
#: PROPOSED — the model's list has no entry for a measurement file with
#: nothing readable in it. Knut, 2026-08-04: *"If the {c}-value is equal to
#: zero … then why not just say the ti3 file is corrupt or empty."* Quite so.
M_CHART_ITEM_MEASUREMENT_UNCOUNTABLE = (
    "•  a measurement file that is corrupt or empty")

# --- PROPOSED: the corrupt-or-empty measurement, and what it costs ---------
M_CHART_CORRUPT = _m(
    "M-CHART-CORRUPT",
    "The measurement file in this run cannot be read",
    "It has no readable measurement data in it — no readings, or a structure "
    "ChromIQ cannot make sense of. That can happen when a session ended before "
    "the first patch was read, or when the file was changed outside "
    "ChromIQ.\n\n"
    "It is moved to the run's “old” folder rather than deleted. **Look at it "
    "there before you measure again** — ChromIQ cannot tell whether it holds "
    "anything you would want to keep, and only you can judge that.",
    approved=False)

#: Appended to M-CHART-CORRUPT when the run also holds a profile. Knut,
#: 2026-08-04: *"the connection between chart and profile built is broken and
#: new measurements may be only way to rebuild the continuity of information."*
M_CHART_CORRUPT_WITH_PROFILE = (
    "\n\nThe profile in this run moves to the “old” folder with it. That "
    "profile was built from a measurement, and the measurement file that "
    "should describe it can no longer be read — so nothing on disk now "
    "connects the profile to the chart it came from. ChromIQ cannot tell "
    "whether the file was always like this or became so later, and it cannot "
    "repair it. Measuring the chart again is the way to get a run whose chart, "
    "measurement and profile describe each other once more.")


M_CHART_W4 = _m(
    "M-CHART-W4",
    "This would undo the whole run, not just its chart",
    "Replacing this run's chart breaks the chain three links deep:\n\n"
    "•  the measurement of {c} patches no longer describes the chart in this "
    "run;\n"
    "•  the profile built from that measurement no longer describes anything "
    "on disk;\n"
    "•  and the {v} dated verification runs under this run were printed "
    "through that profile, so they stop describing a profile that exists.\n\n"
    "Everything is kept in the run's “old” folder and nothing is deleted — but "
    "the run would no longer hold a set of files that belong together, and its "
    "verification history could not be continued.\n\n"
    "Duplicate the run and change the chart in the copy if you want a "
    "different chart while keeping this one's work and its history.\n\n"
    "The “old” folder is here:\n{folder}",
    count_key="v",
    body_one=
    "Replacing this run's chart breaks the chain three links deep:\n\n"
    "•  the measurement of {c} patches no longer describes the chart in this "
    "run;\n"
    "•  the profile built from that measurement no longer describes anything "
    "on disk;\n"
    "•  and the one dated verification run under this run was printed "
    "through that profile, so it stops describing a profile that exists.\n\n"
    "Everything is kept in the run's “old” folder and nothing is deleted — but "
    "the run would no longer hold a set of files that belong together, and its "
    "verification history could not be continued.\n\n"
    "Duplicate the run and change the chart in the copy if you want a "
    "different chart while keeping this one's work and its history.\n\n"
    "The “old” folder is here:\n{folder}")

M_CHART_VERIFY = _m(
    "M-CHART-VERIFY",
    "The verification measurements already made in this run used the chart "
    "you are about to replace",
    "The {v} dated verification measurements in this run were all made with "
    "this verification chart. Replacing it does not make them wrong, and the "
    "report can still compare their figures — but those measurements would no "
    "longer have the chart they were made with, so nothing on disk would say "
    "what they were readings of.\n\n"
    "A trend across the change also compares two different charts, which is "
    "not the same measurement made twice.\n\n"
    "The chart is moved to the “old” folder inside “verifications” and no "
    "measurement is touched. Duplicate the run instead if you want a different "
    "verification chart while keeping this run's verification measurements "
    "intact.",
    count_key="v",
    body_one=
    "The one dated verification measurement in this run was made with this "
    "verification chart. Replacing it does not make it wrong, and the report "
    "can still compare its figures — but that measurement would no longer have "
    "the chart it was made with, so nothing on disk would say what it was "
    "readings of.\n\n"
    "A trend across the change also compares two different charts, which is "
    "not the same measurement made twice.\n\n"
    "The chart is moved to the “old” folder inside “verifications” and no "
    "measurement is touched. Duplicate the run instead if you want a different "
    "verification chart while keeping this run's verification measurements "
    "intact.")

M_CHART_NOPAGES = _m(
    "M-CHART-NOPAGES",
    "This chart's printed pages cannot be recreated",
    "This chart has no layout recipe (.channels.json), so ChromIQ cannot "
    "redraw its pages. {pages}\n\n"
    "If you have the printed sheets, keep them — they are the only copy. "
    "Everything is moved to the run's “old” folder rather than deleted.")

M_CHART_NOPAGES_SOME = "The {n} page images in this run are the only ones there will be."
M_CHART_NOPAGES_ONE = "The one page image in this run is the only one there will be."
M_CHART_NOPAGES_NONE = "This run has no page images to lose."

# --- PROPOSED --------------------------------------------------------------
M_PREVIEW_PAUSED = _m(
    "M-PREVIEW-PAUSED",
    "The live preview is not being re-drawn",
    "This run already holds work made with the chart the preview would "
    "replace, so the preview is left as it is rather than re-drawn over it.\n\n"
    "Press “Generate Chart” when you want the new layout. You will be told "
    "exactly what moves to the run's “old” folder first, and nothing is "
    "deleted.\n\n"
    "This window appears once each time you switch “Auto-update preview” on. "
    "While it stays on, the same note goes to the log instead, so your layout "
    "work is not interrupted.")      # approved by Knut, 2026-08-04


# ---------------------------------------------------------------------------
# §6 — rebuilding the profile under existing verification measurements
# ---------------------------------------------------------------------------
M_PROFILE_VERIFY = _m(
    "M-PROFILE-VERIFY",
    "The verification measurements in this run were made against the profile "
    "you are about to replace",
    "This run holds {n} dated verification measurements, going back to "
    "{date}. Each was printed through the profile in this run and measured "
    "against it, so each records how that profile behaved on that day.\n\n"
    "Building a new profile here does not make those measurements wrong, and "
    "it deletes nothing — but they will no longer say which profile they "
    "belong to, and comparing them with verification measurements made "
    "afterwards means comparing against two different profiles.\n\n"
    "What each button does:\n\n"
    "•  Duplicate the run and build there (recommended) — copies this run's "
    "chart, measurement and profile into a new run and builds there. This run "
    "keeps its profile and its verification measurements exactly as they are, "
    "and the copy starts fresh. This is the clean way to try a different "
    "profile from the same readings.\n\n"
    "•  Build here anyway — replaces this run's profile. The current profile "
    "is moved to the run's “old” folder, and the {n} dated verification "
    "measurements are moved to the “old” folder inside “verifications” with "
    "it, because they describe the profile being replaced. Nothing is "
    "deleted.\n\n"
    "•  Cancel — changes nothing.{blocked}",
    count_key="n",
    body_one=
    "This run holds one dated verification measurement, made on {date}. It "
    "was printed through the profile in this run and measured against it, so "
    "it records how that profile behaved on that day.\n\n"
    "Building a new profile here does not make that measurement wrong, and it "
    "deletes nothing — but it will no longer say which profile it belongs to, "
    "and comparing it with verification measurements made afterwards means "
    "comparing against two different profiles.\n\n"
    "What each button does:\n\n"
    "•  Duplicate the run and build there (recommended) — copies this run's "
    "chart, measurement and profile into a new run and builds there. This run "
    "keeps its profile and its verification measurement exactly as they are, "
    "and the copy starts fresh. This is the clean way to try a different "
    "profile from the same readings.\n\n"
    "•  Build here anyway — replaces this run's profile. The current profile "
    "is moved to the run's “old” folder, and the dated verification "
    "measurement is moved to the “old” folder inside “verifications” with it, "
    "because it describes the profile being replaced. Nothing is deleted.\n\n"
    "•  Cancel — changes nothing.{blocked}")

#: The checkbox on M-PROFILE-VERIFY (§6d) and its tooltip. In the catalogue
#: because it is text the window shows, and the window shows nothing that is
#: not here.
M_SILENCE_LABEL = "Don't show this again for this run"
M_SILENCE_TOOLTIP = (
    "Only for this one run, and only until you close ChromIQ. Every other run "
    "keeps asking, and so does this one the next time you start the program.")

M_DUPLICATE_BLOCKED = (
    "\n\nDuplicate is not available for this run. It needs all four of these: "
    "the patch list (.ti1), the laid-out chart (.ti2), the layout recipe "
    "(.channels.json) and at least one printed page (.tif). This run is "
    "missing {missing}.")


# ---------------------------------------------------------------------------
CATALOGUE = {m.id: m for m in (
    M_REPLACE_PARTIAL, M_REPLACE_COMPLETE, M_TI3_MISMATCH,
    M_REPLACE_UNCOUNTABLE,
    M_CHART_PROFILING, M_CHART_W4, M_CHART_VERIFY, M_CHART_NOPAGES,
    M_CHART_CORRUPT,
    M_PREVIEW_PAUSED, M_PROFILE_VERIFY,
)}

#: Paragraphs appended to another message rather than shown on their own.
#: They have an ID in the model and are quoted in the demo guide, so they are
#: listed here too — a lookup that missed them would call a real ID unknown.
FRAGMENTS = {
    "M-DUPLICATE-BLOCKED": M_DUPLICATE_BLOCKED,
}

#: Every ID the model defines, message or fragment.
ALL_IDS = tuple(sorted(set(CATALOGUE) | set(FRAGMENTS)))

#: The IDs the reviewed model has not approved yet — listed on the issue.
PROPOSED = tuple(sorted(m.id for m in CATALOGUE.values() if not m.approved))
