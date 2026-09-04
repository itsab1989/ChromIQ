"""Shared ti2 file loading workflow: working-folder detection, copy/rename dialogs."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from workflow.chart_import import ReplaceFailed
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt

from core.i18n import tr
from core.logger import get_logger
from core.measurement_target import (RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
                                     MeasurementTarget)
import workflow.chart_import as _chart_import
from core.platform_paths import default_output_root
from ui.warning_sign import set_information_icon, set_warning_icon

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from core.settings import AppSettings

log = get_logger(__name__)


# Matches:  TARGET_INSTRUMENT "GretagMacbeth i1 Pro"
_TARGET_INSTRUMENT_RE = re.compile(r'TARGET_INSTRUMENT\s+"([^"]*)"')
# Matches:  SPECTRAL_BANDS "36"   (number of spectral bands recorded per patch)
_SPECTRAL_BANDS_RE = re.compile(r'SPECTRAL_BANDS\s+"?(\d+)"?')
# printtarg writes RANDOM_START on a randomised chart and CHART_ID on a
# fixed-order one (printtarg.c:3718). chartread keys its auto strip-ID and
# bidirectional recognition off the same keyword (chartread.c:2980).
_RANDOM_START_RE = re.compile(r'\bRANDOM_START\b')

# The exact TARGET_INSTRUMENT strings ChromIQ lays out charts for. ArgyllCMS
# writes the same value into the resulting .ti3, so detection works on either.
#
# ⚠ "CR30" IS THE ONE NAME ARGYLLCMS DOES NOT KNOW (#159). Every other entry
# here is an ArgyllCMS instrument name, and stock `chartread` matches the
# keyword against its own instrument table. ChromIQ reads the CR30 itself, so
# the chart carries the honest name the device reports for itself — and the
# price of that honesty is that stock chartread REFUSES a CR30 chart outright.
# ChromIQ's own chartread fork accepts it.
#
# This list means "a name ChromIQ recognises and can act on", which is what
# every consumer actually asks it. It is NOT "a name ArgyllCMS will accept" —
# `TabMeasure._blocked_by_stock_chartread_for_cr30` is the guard that asks the
# second question, and it must run for a CR30 chart before the measurement is
# armed. Adding "CR30" here without that guard would silence a warning that is
# still true whenever Preferences has the chart-reading engine on ArgyllCMS.
KNOWN_INSTRUMENTS: tuple[str, ...] = (
    "X-Rite ColorMunki",          # ColorMunki / i1Studio / ColorChecker Studio
    "GretagMacbeth i1 Pro",       # i1 Pro family (i1 Pro / Pro 2 / Pro 3 / Pro 3+)
    "GretagMacbeth SpectroScan",  # motorized XY table (patch-by-patch, not strips)
    "CR30",                       # ChnSpec CR30 — ChromIQ reads it, Argyll cannot
)



def is_self_collision(working_dir, name: str, path) -> bool:
    """Would replacing ``working_dir/name`` destroy the file being imported?

    One line, because the logic lives in `core.file_manager.dir_holds` — both
    loaders had their own copy and both were wrong the same way, which is how
    replacing a project deleted the project, its profile AND the file being
    imported.

    Module level, not a closure inside the dialog, so that it can be driven
    without building a window: the test that guards this used to grep the
    module for the word "dir_holds", and a loader that had stopped calling it
    still passed, because the name survived in a docstring.
    """
    from core.file_manager import dir_holds
    return dir_holds(working_dir / name, path)


def read_target_instrument(cgats_path: Path) -> str | None:
    """Return the TARGET_INSTRUMENT value from a CGATS file (.ti1/.ti2/.ti3), or None.

    ArgyllCMS records the instrument a chart was laid out for in this keyword and
    carries it through into the measured .ti3, e.g.
    ``TARGET_INSTRUMENT "GretagMacbeth i1 Pro"`` (i1 Pro family, incl. i1Pro3+),
    ``TARGET_INSTRUMENT "X-Rite ColorMunki"`` (ColorMunki/i1Studio) or
    ``TARGET_INSTRUMENT "GretagMacbeth SpectroScan"`` (XY table). See
    ``KNOWN_INSTRUMENTS`` for the values ChromIQ produces.
    """
    try:
        text = cgats_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = _TARGET_INSTRUMENT_RE.search(text)
    return m.group(1).strip() if m else None


def is_colormunki(name: str | None) -> bool:
    """Whether the instrument is a ColorMunki (incl. its i1Studio rebrand).

    Single source of truth for the ColorMunki check used both by the chartread
    -B decision and by the option-gating in the Build-Profile / Check-Refine tabs.
    """
    return bool(name) and "colormunki" in name.lower()


def is_spectroscan(name: str | None) -> bool:
    """Whether the instrument is a GretagMacbeth SpectroScan.

    The SpectroScan is a motorized XY table that reads each patch individually
    rather than scanning strips, so the bidirectional (-B) concept does not apply.
    """
    return bool(name) and "spectroscan" in name.lower()


def instrument_label(name: str | None) -> str | None:
    """Friendly display name for a TARGET_INSTRUMENT value (UI output only).

    ArgyllCMS tags whole instrument families under one string; this expands them
    to the model names users recognise. Detection/gating still use the raw value
    (see ``is_colormunki`` / ``is_spectroscan``) — this is purely for display.
    Unrecognised instruments (incl. the SpectroScan) are shown unchanged.
    """
    if not name:
        return None
    if is_colormunki(name):
        return "ColorMunki / i1Studio / CCStudio"
    low = name.lower()
    if "i1 pro" in low or "i1pro" in low:
        return "i1Pro / i1Pro2 / i1Pro3(+)"
    return name


def is_i1pro(name: str | None) -> bool:
    """Whether the instrument is an i1 Pro family device.

    The i1 Pro / Pro 2 / Pro 3 / Pro 3+ are all tagged ``"GretagMacbeth i1 Pro"``
    by ArgyllCMS (some builds report ``"X-Rite i1 Pro …"``). They can read a
    strip in either direction (``inst2_bidi_scan``), so they support chartread's
    force-bidirectional mode (``-b``).
    """
    if not name:
        return False
    low = name.lower()
    return "i1 pro" in low or "i1pro" in low


def is_cr30(name: str | None) -> bool:
    """Whether the instrument is a CHNSpec CR30 (#159).

    Single source of truth for the CR30 check. The chart is stamped with the
    honest name the device reports for itself, so this is a plain match and
    never borrows another instrument's identity — a borrowed name would make
    every ``is_colormunki`` consumer lie about what took the readings.
    """
    return bool(name) and "cr30" in name.lower()


def spectral_options_unavailable(name: str | None,
                                 has_spectral: bool = True) -> bool:
    """Whether the spectral-only profiling options (colprof ``-f`` FWA, the
    illuminant and the observer) must be disabled for this measurement.

    Two independent reasons, either of which is enough:

    * **The instrument cannot see what the option needs.** A ColorMunki and a
      CR30 both illuminate with a blue-pump white LED, which does not excite
      optical brightening agents, so a fluorescent-whitening adjustment has
      nothing to work from. This has gated the ColorMunki since the option
      existed; the CR30 belongs on the same side of it (#159).
    * **The measurement carries no spectra at all.** FWA, illuminant and
      observer are all computed FROM the spectral curve. A CR30 ``.ti3`` is
      colorimetric only - by design, because the device's 31 reported bands
      carry 8 degrees of freedom and writing 31 ``SPECTRAL_*`` columns would
      tell ``colprof`` it has 31 independent measurements when it has 8
      (#159). So the second test is not a CR30 special case: it is true of any
      measurement without spectral columns, and offering an option that has no
      data to act on is worse than not offering it.

    *has_spectral* defaults True so a caller that has not looked is judged on
    the instrument alone, exactly as before.
    """
    return is_colormunki(name) or is_cr30(name) or not has_spectral


def instrument_family(name: str | None) -> "str | None":
    """Coarse instrument family for instruction wording: ``"colormunki"``
    (ColorMunki / i1Studio / ColorChecker Studio), ``"i1pro"`` (the whole i1 Pro
    line — Argyll tags them all the same, so they share one instruction set),
    ``"cr30"`` (CHNSpec CR30 hand-held spot reader), ``"spectroscan"`` (XY
    table), or ``None`` when unrecognised (→ generic
    wording). Accepts a TARGET_INSTRUMENT value or spotread's reported model."""
    if is_cr30(name):
        return "cr30"
    if is_colormunki(name):
        return "colormunki"
    if is_spectroscan(name):
        return "spectroscan"
    if is_i1pro(name):
        return "i1pro"
    return None


def calibration_instructions_html(family: "str | None") -> str:
    """The calibration-position pop-up body for an instrument *family*.

    Placing-the-instrument wording is device-specific where the chart tells us
    the family; the SpectroScan and any unknown instrument keep the generic
    text. HTML (``<b>…</b>``) — the caller shows it in a rich-text label."""
    if family == "colormunki":
        return tr(
            "<b>Your instrument needs to be calibrated before measuring.</b>"
            "<br><br>Turn the dial on the side of your ColorMunki / i1Studio to "
            "the <b>calibration position</b> (the small gear icon), then click "
            "<b>Start Calibration</b>.<br><br>Calibration takes only a few "
            "seconds. Once it's done, another message will tell you how to start "
            "measuring.")
    if family == "cr30":
        return tr(
            "<b>Your instrument needs to be calibrated before measuring.</b>"
            "<br><br>Your CR30 came with a small <b>magnetic cap</b>. That cap "
            "holds the <b>white tile</b> your instrument calibrates against, so "
            "there is no separate tile to look for.<br><br>"
            "<b>1.</b> Put the cap on the measuring end of the CR30, with the "
            "<b>white side facing inwards</b>, towards the lens. It should sit "
            "flat and snap into place.<br>"
            "<b>2.</b> Press the <b>button on the instrument itself</b>. The "
            "CR30 reads the white tile and shows the result on its own little "
            "display.<br>"
            "<b>3.</b> Come back here and click <b>Start Calibration</b> so "
            "ChromIQ can check that it worked.<br><br>"
            "Calibration takes only a second or two. Once it's done, another "
            "message will tell you how to start measuring.<br><br>"
            "<b>Please check the cap is the right way round.</b> If the cap is "
            "reversed, the CR30 will happily calibrate against the wrong "
            "surface, and every reading afterwards will look perfectly normal "
            "while being wrong.")
    if family == "i1pro":
        return tr(
            "<b>Your instrument needs to be calibrated before measuring.</b>"
            "<br><br>Place your i1Pro on its <b>calibration base</b>, with the "
            "measuring aperture over the <b>white tile</b>. On the i1Pro and "
            "i1Pro 2, make sure the base's slider is set to the white-tile "
            "(calibration) position. Then click <b>Start Calibration</b>."
            "<br><br>Calibration takes only a few seconds. Once it's done, "
            "another message will tell you how to start measuring.")
    return tr(
        "<b>Your instrument needs to be calibrated before measuring.</b><br><br>"
        "Place the instrument in the <b>calibration position</b> as described "
        "in its manual, then click <b>Start Calibration</b>.<br><br>The "
        "calibration takes only a few seconds. Once it is complete, another "
        "message will appear with instructions on how to start measuring the "
        "strips.")


def measurement_instructions_html(family: "str | None") -> str:
    """The measurement-position instruction for an instrument *family* — how to
    physically place and read a strip. Generic for SpectroScan / unknown."""
    if family == "colormunki":
        return tr(
            "Turn the dial to the <b>measurement position</b> (the target / "
            "aperture icon). Rest the device flat on the paper with the lens at "
            "the <b>start of the strip</b>, then <b>press and hold the side "
            "button</b> and slide the whole device smoothly along the strip at "
            "a steady pace.")
    if family == "cr30":
        return tr(
            "<b>Take the magnetic cap off first.</b> With the cap (or any "
            "magnet) near the instrument, the CR30 does not measure at all.<br>"
            "<br>Stand the CR30 flat on the <b>highlighted patch</b>, so the "
            "measuring opening sits well inside it, then <b>press the button on "
            "the instrument</b>. ChromIQ picks the reading up on its own and "
            "moves the highlight to the next patch. You do not need to touch "
            "the keyboard.<br><br>Each patch takes about two seconds. You can "
            "stop at any time; every patch you have already read is saved.")
    if family == "i1pro":
        return tr(
            "Take the i1Pro off its base. Place it flat at the <b>start of the "
            "strip</b> (on the lead-in, just before the first patch), press and "
            "<b>hold the button</b>, and slide it smoothly along the whole strip "
            "at an even speed.")
    return tr(
        "Place your instrument at the <b>start of the strip</b> and scan it as "
        "described in its manual.")


def spot_measurement_instructions_html(family: "str | None") -> str:
    """How to read a colour with the Read Single Patches tool.

    Nearly the patch-by-patch text, but that one says "the highlighted patch" —
    there is a chart on screen there, and here there is not: you choose whatever
    colour you like. Knut asked for the two to be separated rather than have one
    describe the other's screen (#130, 2026-07-31): *"separate the patch-by-patch
    window wording and make a window with specific wording for the Read Single
    Patches tool."*
    """
    if family == "colormunki":
        return tr(
            "Turn the dial to the <b>measurement position</b> (the target / "
            "aperture icon). Rest the device flat on the colour you want to "
            "read, with the aperture fully inside it.")
    if family == "cr30":
        # ASSEMBLED FROM SENTENCES THIS APP ALREADY SHOWS FOR THIS INSTRUMENT,
        # not written fresh: the cap warning is `measurement_instructions_html`'s
        # opening, word for word, and the placing sentence is the generic one
        # below it. Everything else in the chart versions describes a
        # highlighted patch, which this window does not have.
        #
        # The cap sentence has to be here. With the cap on, a CR30 does not
        # measure at all — it performs a white calibration against whatever is
        # under the aperture — and the magnet guard can only refuse the reading
        # afterwards, by which time the instrument has already recalibrated
        # itself.
        return tr(
            "<b>Take the magnetic cap off first.</b> With the cap (or any "
            "magnet) near the instrument, the CR30 does not measure at all."
            "<br><br>Place your instrument flat on the colour you want to "
            "read, with its aperture fully inside the area.")
    if family == "i1pro":
        return tr(
            "Take the i1Pro <b>off its base</b>. Place it flat on the colour you "
            "want to read so the aperture sits fully inside it.")
    return tr(
        "Place your instrument flat on the colour you want to read, with its "
        "aperture fully inside the area.")


def patch_measurement_instructions_html(family: "str | None") -> str:
    """How to read a SINGLE patch with an instrument *family*.

    The strip version of this describes a swipe — press, hold, slide — which is
    not what patch-by-patch mode asks of you, so quoting it there would be
    describing something the user is not doing (Knut, #131 2026-07-28). Same
    per-instrument treatment, different action.
    """
    if family == "colormunki":
        return tr(
            "Turn the dial to the <b>measurement position</b> (the target / "
            "aperture icon). Rest the device flat on the highlighted patch, "
            "with the aperture fully inside it, and <b>press the side button "
            "once</b>. Hold it still until the reading is taken, there is no "
            "sliding in this mode.")
    if family == "cr30":
        return tr(
            "Take the <b>magnetic cap off</b> the measuring end first, with "
            "the cap on, the CR30 reads its own white tile instead of your "
            "print.<br><br>Rest the instrument flat on the highlighted patch "
            "with the aperture fully inside it, hold it still, and <b>press "
            "the button on the instrument</b>. ChromIQ collects the reading by "
            "itself and moves on to the next patch, there is nothing to press "
            "on screen, and there is no sliding in this mode.<br><br>"
            "You can also press the <b>space bar</b> (or Enter) to take the "
            "reading without touching the instrument at all, that keeps it "
            "perfectly still and is steadier than pressing its button. It "
            "becomes available once ChromIQ has learned your instrument's "
            "white tile, which it offers after calibrating.<br><br>"
            "A CR30 chart is always read one patch at a time; the instrument "
            "has no strip reading to offer.")
    if family == "i1pro":
        return tr(
            "Take the i1Pro off its base. Place it flat on the highlighted "
            "patch so the aperture sits fully inside it, and <b>press the "
            "button once</b>. Keep it still until the reading is taken, there "
            "is no sliding in this mode.")
    if family == "spectroscan":
        return tr(
            "The SpectroScan positions itself over each patch; follow the "
            "prompts on the table and let it complete each reading before "
            "moving on.")
    return tr(
        "Place your instrument flat on the highlighted patch, with its aperture "
        "fully inside the patch, and take a single reading as described in its "
        "manual.")


def disable_bidir_for_instrument(name: str | None) -> bool:
    """Whether the Auto toggle should disable bidirectional strip recognition
    (chartread ``-B``).

    No instrument auto-selects ``-B`` any more. The ColorMunki (and its
    i1Studio rebrand) reads strips in one direction, but ArgyllCMS's default
    behaviour already handles that correctly, so Auto leaves the ColorMunki on
    the Argyll default (no ``-B``) rather than forcing ``-B``. The i1 Pro family
    auto-forces ``-b`` instead (see ``force_bidir_for_instrument``); the
    SpectroScan and the CR30 read patches individually, so the bidirectional
    concept does not apply to either. Users can still pick "Bidirectional
    disabled" by hand.

    Always returns ``False`` — kept as the single Auto ``-B`` decision point so
    the behaviour stays documented in one place.
    """
    return False


def force_bidir_for_instrument(name: str | None) -> bool:
    """Whether to force-enable bidirectional strip recognition (chartread -b).

    chartread only auto-enables bidirectional reading when the chart is
    randomised; on a fixed-order chart (e.g. printtarg ``-r``) it otherwise
    reads one direction only and rejects strips scanned backwards. The i1 Pro
    family reads either direction, so ``-b`` forces the auto-detection on for
    those charts. The ColorMunki reads one direction only, and the SpectroScan
    and the CR30 read patches individually, so none of them should force it.
    ``-b`` and ``-B`` are mutually exclusive; this only returns True for the
    i1 Pro family.
    """
    return is_i1pro(name)


def is_randomized(cgats_path: Path) -> bool:
    """Whether a chart was laid out in randomised patch order.

    printtarg randomises by default and writes ``RANDOM_START``; its ``-r`` flag
    keeps the source order and writes ``CHART_ID`` instead. chartread reads the
    same keyword to decide whether it may auto-recognise strips and read them in
    either direction. Randomisation gives every strip a unique colour signature,
    which is what makes that recognition reliable — a fixed-order chart (no
    ``RANDOM_START``) can confuse it, especially with forced bidirectional
    reading (``-b``).

    Returns ``True`` only when ``RANDOM_START`` is present; a missing/unreadable
    file is treated as randomised (``True``) so callers don't warn spuriously.
    """
    try:
        text = cgats_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True
    return bool(_RANDOM_START_RE.search(text))


def has_spectral_data(cgats_path: Path) -> bool:
    """Whether a CGATS file (.ti3) contains spectral measurements.

    Spectral-dependent options (FWA compensation, illuminant, observer) only work
    when the .ti3 carries per-patch spectral readings, flagged by a positive
    ``SPECTRAL_BANDS`` keyword. Returns False on a missing/unreadable file.
    """
    try:
        text = cgats_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    m = _SPECTRAL_BANDS_RE.search(text)
    return bool(m) and int(m.group(1)) > 0



def _say_the_replace_failed(parent, folder, reason) -> None:
    """Show M-PROJECT-REPLACE-FAILED — the promise that nothing is deleted,
    when it could not be kept.

    "Replace it" promises everything is moved into the project's own `old/`
    folder. When that move cannot be made — a read-only folder, a share that
    has gone away, a file another program holds open — `_archive_project_contents`
    puts back whatever it had moved and raises. Until now the raise reached
    nothing but `chromiq.log`: driven through a real button with the excepthook
    `main.py` installs, the window never appeared, the tab log said nothing, and
    the app looked idle. The copy functions take no widget, so this is said at
    the layer that has one.
    """
    from PyQt6.QtWidgets import QMessageBox
    from core.file_manager import is_a_project
    from workflow import measurement_messages as M
    # A PLAIN FOLDER IS NOT A PROJECT, and this window's headline said it was:
    # "The existing project could not be moved aside", about a read-only folder
    # holding one text file (round 2, T1-D). Same act, same promise, and the
    # only difference is the one sentence that describes what is there.
    # M-IMPORT-REPLACE-FOLDER-FAILED, approved by Basti on 2026-09-02.
    _msg = (M.M_PROJECT_REPLACE_FAILED if is_a_project(folder)
            else M.M_IMPORT_REPLACE_FOLDER_FAILED)
    title, body = _msg.render(folder=str(folder), reason=str(reason))
    box = QMessageBox(parent)
    set_warning_icon(box)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()


def _say_where_the_old_project_went(parent, name, dest) -> None:
    """M-IMPORT-REPLACED-KEPT — "Nothing is deleted" is only true if the person
    can find it again.

    Report 10, finding 9: nothing anywhere recorded where a replaced project had
    gone — no window, no log line, not even a line in the tab's log. The
    catalogue entry existed for a round with no call site, which is worse than
    not having it: the specification then describes a promise the app does not
    keep. Shown from here because the `_copy_*` functions take no widget.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow import measurement_messages as M
    title, body = M.M_IMPORT_REPLACED_KEPT.render(name=name,
                                                  folder=str(dest / "old"))
    box = QMessageBox(parent)
    set_information_icon(box)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()

def resolve_ti2(
    parent: "QWidget",
    ti2_path: Path,
    settings: "AppSettings",
    controller=None,
) -> tuple[Path, list[Path]] | None:
    """Determine how to load a ``.ti2`` file, honouring the shared Profile-run /
    Run-type bar (#130 unified file-handling model).

    Returns ``(ti2_path_to_use, tiff_list)`` — the original paths (used in place)
    or newly copied ones — or ``None`` if the user cancelled. Every path shows an
    explaining pop-up first (the universal rule); nothing is copied/moved silently.

    *controller* is the shared :class:`MeasurementTargetController`. When a
    profile project is loaded, the model routes by where the file lives:
      • inside the loaded project → **Continue** in place (sets the bar) or copy
        out (A2a);
      • inside a different project → **Open** it, or copy out (A2b);
      • a complete project outside the folder → copy the whole project, or import
        just this chart per the bar (A1b);
      • a loose chart (or an older/flat layout) → import into the bar's target run
        per Run type, with a New-vs-Replace choice on overwrite (A1a / A2c).
    When no project is loaded (or no controller), it falls back to the original
    "create a new profile project" flow so a first chart can still be loaded.
    """
    # THE PROMISE THAT NOTHING IS DELETED, KEPT OR EXPLAINED.
    try:
        working_dir = _resolve_working_dir(settings)
        inside_root = _project_root_for(ti2_path, working_dir)
        loaded_root = _loaded_project_root(controller)

        # NOTHING OPEN, BUT THE CHART BELONGS TO A PROJECT.
        #
        # This used to fall through to the create-a-new-project flow below, which is
        # the ordinary first action after launching: open ChromIQ, load a chart. The
        # chart's own project was never opened, so the bar stayed on "New run" — and
        # from there the "this chart already has a measurement" window has no scope
        # to remember its suppress tick against, so it returned on every visit to the
        # Measure tab (Basti, 2026-08-08). The resolver below already knew which
        # project the file belongs to; nothing asked it.
        if controller is not None and loaded_root is None and inside_root is not None:
            return _handle_inside_nothing_open(parent, ti2_path, inside_root,
                                               working_dir, controller)

        if controller is not None and loaded_root is not None:
            if inside_root is not None and inside_root == loaded_root:
                return _handle_inside_current(parent, ti2_path, working_dir,
                                              controller)                      # A2a
            if inside_root is not None:
                return _handle_inside_other(parent, ti2_path, inside_root,
                                            working_dir, controller)           # A2b
            full = _chart_import.is_full_project(ti2_path)
            if full is not None:
                return _handle_full_project(parent, ti2_path, full, working_dir,
                                            controller)                        # A1b
            return _handle_loose_into_project(parent, ti2_path, working_dir,
                                              controller)                      # A1a/A2c

        # No project loaded → the original new-project flow (loads the first chart).
        if inside_root is not None:
            return _handle_inside(parent, ti2_path, working_dir)
        return _handle_outside(parent, ti2_path, working_dir)
    except ReplaceFailed as exc:
        # ONLY a failed archive. Any other OSError is a different fault and
        # must not be reported as "the existing project could not be moved
        # aside — nothing has been changed", which would be false.
        _say_the_replace_failed(parent, exc.folder, exc.reason)
        return None

def _loaded_project_root(controller) -> "Path | None":
    if controller is None:
        return None
    try:
        proj = controller.project_or_none()
        return proj.root if proj is not None else None
    except Exception:      # noqa: BLE001 — never break a load on this
        return None


# ---------------------------------------------------------------------------
# #130 unified model — bar-aware load dialogs (each shows an explaining pop-up
# first; nothing is copied/moved silently).
# ---------------------------------------------------------------------------
def _run_label(target) -> str:
    rid = getattr(target, "profile_run", "") or ""
    if not rid:
        return tr("New run")
    n = rid[3:] if rid.startswith("run") else rid
    return tr("run {n}").format(n=n)


def _type_label(target) -> str:
    return tr("Verification") if target.is_verification() else tr("Profiling")


def _bar_header(target) -> str:
    return tr("Since <b>Profile run</b> = {run} and <b>Run type</b> = {kind}, the "
              "following actions are available:").format(
                  run=_run_label(target), kind=_type_label(target))


#: Longest project name a button may carry before it is elided. 28 characters
#: is the widest label that still leaves the three buttons on one row at the
#: default font — see `_short_name`.
_BUTTON_NAME_LIMIT = 28


def _short_name(name: str) -> str:
    """A project name cut to a length a button can hold.

    A BUTTON CANNOT CARRY AN UNBOUNDED NAME. ``Open {name}`` grows with the
    project and the window grows with the button: measured offscreen, a
    66-character project asked for a 633px button, which together with the
    other two overflowed the window and clipped every label — the very fault
    fixed the day before, returning by another route (Basti asked what happens
    to a long name, 2026-08-08).

    Elided in the **middle**, not the end. Project names differ most in their
    last few characters — ``…_June2026_matte`` against ``…_June2026_gloss`` —
    so a right-elide would render two different projects as the same button.
    The description below the buttons still gives the name in full, so the
    short form costs the reader nothing.
    """
    if len(name) <= _BUTTON_NAME_LIMIT:
        return name
    keep = _BUTTON_NAME_LIMIT - 1                    # the ellipsis takes one
    head = (keep + 1) // 2
    return f"{name[:head]}…{name[len(name) - (keep - head):]}"


def _choice_dialog(parent, title, intro_html, choices):
    """Ask the user to pick one of several ways to load a file.

    *choices* = ``[(button_label, description_html, key)]``. Returns the chosen
    key, or ``None`` on Cancel.

    Built as a QMessageBox so it looks like every other window in ChromIQ: the
    explanation above, the buttons in one row at the bottom. It used to stack a
    button and a description panel per choice down the middle of a QDialog —
    which put the buttons in the body, in the wrong order, and gave each
    description the `#info` styling, a maroon panel meant for a single inline
    hint rather than three of them in a column (Basti, 2026-08-08).

    The descriptions move into the text, under "What each button does" — the
    same shape the measurement windows use, so the reader learns one layout
    instead of two.
    """
    from PyQt6.QtWidgets import QMessageBox

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setWindowTitle(title)
    box.setTextFormat(Qt.TextFormat.RichText)

    # HEADLINE IN setText, EVERYTHING ELSE IN setInformativeText.
    #
    # QMessageBox paints setText in bold. Putting the whole explanation there
    # made every word of it bold, so nothing stood out and the wall of heavy
    # text was harder to read than the plain version it replaced (Basti,
    # 2026-08-08). The measurement windows already split it this way.
    box.setText(title)
    parts = []
    if intro_html:
        parts.append(intro_html)
    parts.append(tr("What each button does:"))
    for label, desc, _key in choices:
        # A COLON, LIKE THE CANCEL BULLET BELOW IT. Removing the em dashes
        # from the descriptions left this generated bullet with a dash while
        # its sibling had a comma, so one list carried two punctuations
        # (spotted in a verification screenshot, 2026-09-01).
        parts.append(f"&nbsp;&nbsp;•&nbsp; <b>{label}</b>: {desc}")
    parts.append(tr("&nbsp;&nbsp;•&nbsp; <b>Cancel</b>: nothing is opened, "
                    "copied or changed, and the file you picked is left exactly "
                    "as it is."))
    box.setInformativeText("<br><br>".join(parts))

    # ActionRole keeps them in the order given, before Cancel, under the app's
    # button-layout style.
    buttons = {}
    for label, _desc, key in choices:
        buttons[box.addButton(label, QMessageBox.ButtonRole.ActionRole)] = key
    cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)

    from ui.widgets import fit_message_box_buttons
    fit_message_box_buttons(box)

    # THE CHOICES TOGETHER ON THE LEFT, CANCEL ON ITS OWN AT THE RIGHT.
    #
    # Qt lays all three out as one group, so "Cancel" sat shoulder to shoulder
    # with the two actions and read like a third thing you might want to do
    # (Basti, 2026-08-08). Separating it says what it is: the way out, not an
    # option. A stretch inside the button box does it without disturbing the
    # order the app's button-layout style produces.
    try:
        from PyQt6.QtWidgets import QDialogButtonBox
        bb = box.findChild(QDialogButtonBox)
        if bb is not None and bb.layout() is not None:
            idx = bb.layout().indexOf(cancel)
            if idx > 0:
                bb.layout().insertStretch(idx, 1)
    except Exception:      # noqa: BLE001 — a layout tweak must never block the window
        pass

    box.exec()
    return buttons.get(box.clickedButton())


def _next_run_id(project) -> str:
    """The id the next ``project.new_run()`` would create (``run3``, …), so a
    pop-up can name the exact folder an import will land in. Purely read-only;
    falls back to a generic label when the project can't be inspected."""
    try:
        return f"run{project._next_run_index()}"
    except Exception:      # noqa: BLE001 — a label must never break a load
        return tr("the next run")


def _dest_tiffs(ti2_in_project: Path) -> "list[Path]":
    from core.file_manager import stem_files
    return stem_files(ti2_in_project.parent, ti2_in_project.stem, "_*.tif")


def _run_and_kind_for_ti2(ti2_path: Path) -> "tuple[str, bool]":
    """(run id, is_verification) for a .ti2 that lives inside a project — a verify
    chart sits under ``…/runs/runN/verifications/``."""
    from core.file_manager import Run
    parent = ti2_path.parent
    if parent.name == "verifications":
        run = Run.for_dir(parent.parent)
        return run.id, True
    run = Run.for_dir(parent)
    return run.id, False


def _copy_out_new_project(parent, ti2_path, working_dir):
    """Reuse the classic 'copy to a new profile project' flow (name prompt +
    copy), used by the 'Use as base for a new profile' choice."""
    ti1, tiffs = _related_files(ti2_path)
    res = _ask_profile_name(parent, ti2_path, ti1, tiffs, working_dir)
    if res is None:
        return None
    name, overwrite = res
    return _copy_files(ti2_path, ti1, tiffs, working_dir, name, overwrite=overwrite)


def _handle_loose_into_project(parent, ti2_path, working_dir, controller):
    """A1a / A2c — a loose external chart (or an older/flat layout inside the
    working folder). Import into the bar's target run per Run type."""
    ti1, tiffs = _related_files(ti2_path)
    proj = controller.project_or_none()
    t = controller.target
    verif = t.is_verification()
    header = _bar_header(t)
    next_id = _next_run_id(proj)
    if not t.profile_run:                      # New run
        if verif:
            desc = tr("Copies only the chart files into a brand-new run inside "
                      "the profile project you have open, as its verification "
                      "chart: <code>runs/{run}/verifications/</code>. Any "
                      ".icc/.icm and .ti3 beside the file are not copied, and no "
                      "existing run is touched.").format(run=next_id)
        else:
            desc = tr("Copies the chart, and its measurement (.ti3) and profile "
                      "(.icc/.icm) if present, into a brand-new run inside the "
                      "profile project you have open: <code>runs/{run}/</code>. "
                      "No existing run is touched.").format(run=next_id)
        key = _choice_dialog(parent, tr("Import this chart"), header,
                             [(tr("Import as a new run"), desc, "import")])
        if key != "import":
            return None
        out = _chart_import.import_external_chart(ti2_path, ti1, tiffs, proj, t)
    else:                                       # Overwrite run N
        runlabel = _run_label(t)
        rid = t.profile_run
        if verif:
            rep = tr("Moves the current verification chart into "
                     "<code>runs/{run}/verifications/old/</code>, nothing is "
                     "deleted, and then installs the loaded chart as this run's "
                     "verification chart in <code>runs/{run}/verifications/</code>. "
                     "Your dated verification results are kept exactly where they "
                     "are, and so are this run's own chart, measurement and "
                     "printer profile. Any .icc/.icm and .ti3 beside the loaded "
                     "file are ignored.").format(run=rid)
        else:
            rep = tr("Moves this run's chart, measurement and printer profile, "
                     "together with every folder inside it, including its "
                     "reports and verifications, into "
                     "<code>runs/{run}/old/</code>, and then copies the loaded "
                     "files into <code>runs/{run}/</code>. Nothing is deleted. "
                     "Everything moves because a new chart no longer matches the "
                     "measurement, profile or checks made from the old one."
                     ).format(run=rid)
        key = _choice_dialog(parent, tr("Import this chart"), header, [
            (tr("Create a new run instead"),
             tr("Imports into a brand-new run, <code>runs/{new}/</code>, inside "
                "the profile project you have open. Nothing in {run} is touched, "
                "and no new profile project is created.")
             .format(new=next_id, run=runlabel), "new"),
            (tr("Replace {run}").format(run=runlabel), rep, "replace")])
        if key == "new":
            t = MeasurementTarget(run_type=t.run_type, profile_run="")
            out = _chart_import.import_external_chart(ti2_path, ti1, tiffs, proj, t)
        elif key == "replace":
            out = _chart_import.import_external_chart(ti2_path, ti1, tiffs, proj,
                                                     t, replace=True)
        else:
            return None
    _point_bar_at_current_run(controller)
    return out, _dest_tiffs(out)


def _handle_inside_current(parent, ti2_path, working_dir, controller):
    """A2a — the file is inside the currently loaded project."""
    run_id, verif = _run_and_kind_for_ti2(ti2_path)
    n = run_id[3:] if run_id.startswith("run") else run_id
    what = tr("verification chart") if verif else tr("chart")
    header = tr("This file is run {n}'s {what}.").format(n=n, what=what)
    key = _choice_dialog(parent,
        tr("This chart belongs to the loaded project"), header, [
        (tr("Continue"),
         tr("Use it in place; nothing is copied. Profile run is set to "
            "<b>Run {n}</b> and Run type to <b>{kind}</b> to match.")
         .format(n=n, kind=(tr("Verification") if verif else tr("Profiling"))),
         "continue"),
        (tr("Use as base for a new profile"),
         tr("Copies it out into a new printer profile project (you'll pick a "
            "name); the original is untouched."), "new")])
    if key == "continue":
        controller.set_run_type(RUN_TYPE_VERIFICATION if verif else RUN_TYPE_PROFILING)
        controller.set_profile_run(run_id)
        _, tiffs = _related_files(ti2_path)
        return ti2_path, tiffs
    if key == "new":
        return _copy_out_new_project(parent, ti2_path, working_dir)
    return None


def _handle_inside_nothing_open(parent, ti2_path, inside_root, working_dir,
                                controller):
    """No project is open and the chart lives in one — offer to open it.

    The same two choices as A2b, worded for the case where there is nothing to
    switch *away* from. Opening copies nothing: the run the chart belongs to
    becomes the selected run, exactly as if the project had been opened first
    and the chart loaded from inside it.

    A verification chart selects Run type = Verification, matching A2a. Getting
    that wrong would point the bar at a profiling run and quietly invite a
    measurement into the wrong place.
    """
    name = inside_root.name
    key = _choice_dialog(parent, tr("This chart belongs to a profile project"), "", [
        (tr("Open {name}").format(name=_short_name(name)),
         tr("Opens <b>{name}</b> and selects the profile run this chart was "
            "made for, so the bar above the tabs shows what you are working "
            "on. Nothing is copied or moved: the chart, its printed pages and "
            "any measurement already made stay exactly where they are. Choose "
            "this when you are picking up work you started earlier."
            ).format(name=name), "open"),
        (tr("Use as base for a new profile"),
         tr("Copies this chart into a new printer profile project (new name → "
            "new folder). The original {name} is untouched.").format(name=name),
         "new")])
    if key == "open":
        try:
            controller._fm.open_project_at(inside_root)
        except Exception:      # noqa: BLE001
            log.warning("Could not open project %s", name, exc_info=True)
            return None
        # (run_id, IS_VERIFICATION) — a bool, not a name. Comparing it to a
        # string would silently open every verification chart as a profiling
        # run, and point the bar at the wrong place to measure into.
        run_id, is_verif = _run_and_kind_for_ti2(ti2_path)
        controller.set_run_type(
            RUN_TYPE_VERIFICATION if is_verif else RUN_TYPE_PROFILING)
        controller.set_profile_run(run_id)
        _, tiffs = _related_files(ti2_path)
        return ti2_path, tiffs
    if key == "new":
        return _copy_out_new_project(parent, ti2_path, working_dir)
    return None


def _handle_inside_other(parent, ti2_path, inside_root, working_dir, controller):
    """A2b — the file is inside a DIFFERENT current-structure project."""
    other = inside_root.name
    key = _choice_dialog(parent, tr("Load another profile project"), "", [
        (tr("Open {name}").format(name=_short_name(other)),
         tr("Switches the working project to <b>{name}</b>. Profile run is set to "
            "its current run and Run type to Profiling. Nothing is copied.")
         .format(name=other), "open"),
        (tr("Use as base for a new profile"),
         tr("Copies this chart into a new printer profile project (new name → new "
            "folder). The original {name} is untouched.").format(name=other),
         "new")])
    if key == "open":
        try:
            # Open at the project's ACTUAL folder (handles a nested sub-folder
            # location as well as a direct child of the ChromIQ folder, #130).
            controller._fm.open_project_at(inside_root)
        except Exception:      # noqa: BLE001
            log.warning("Could not switch to project %s", other, exc_info=True)
            return None
        controller.set_run_type(RUN_TYPE_PROFILING)
        run_id, _ = _run_and_kind_for_ti2(ti2_path)
        controller.set_profile_run(run_id)
        _, tiffs = _related_files(ti2_path)
        return ti2_path, tiffs
    if key == "new":
        return _copy_out_new_project(parent, ti2_path, working_dir)
    return None


def _handle_full_project(parent, ti2_path, src_root, working_dir, controller):
    """A1b — a complete ChromIQ project sitting outside the working folder."""
    t = controller.target
    key = _choice_dialog(parent, tr("This is a complete ChromIQ project"), "", [
        (tr("Copy the whole project in"),
         tr("Copies the entire project (all runs, verifications, calibration) "
            "into your ChromIQ folder. Profile run / Run type are not used, the "
            "copy reproduces the project exactly. You'll confirm the project name "
            "(pre-filled with <b>{name}</b>); if it already exists you can pick a "
            "different one or Replace it (the old one is moved to its "
            "<code>old/</code> folder first).").format(name=src_root.name),
         "whole"),
        (tr("Import just this chart"),
         tr("Ignores the rest of the project and copies only this chart per your "
            "current Profile run = {run} and Run type = {kind}.").format(
                run=_run_label(t), kind=_type_label(t)), "chart")])
    if key == "whole":
        name = _ask_project_name(parent, src_root.name, working_dir)
        if name is None:
            return None
        new_name, replace = name
        dest = _chart_import.copy_whole_project(src_root, working_dir, new_name,
                                                replace=replace)
        try:
            # Point at the copy's ACTUAL folder — if a project of the same name
            # is open from a sub-folder, the name alone would still resolve there.
            controller._fm.open_project_at(dest)
        except Exception:      # noqa: BLE001
            pass
        _point_bar_at_current_run(controller)
        from core.file_manager import Project
        run = Project.load(dest).current_run()
        return run.chart_ti2, run.stem_files(run.stem, "_*.tif")
    if key == "chart":
        return _handle_loose_into_project(parent, ti2_path, working_dir, controller)
    return None


def _ask_project_name(parent, default_name, working_dir):
    """Prompt for a project name (pre-filled with *default_name*). Returns
    ``(name, replace)`` or None. On a name collision the user may Replace."""
    from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                                 QPushButton, QVBoxLayout)
    from core.file_manager import FileManager
    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("Copy project"))
    dlg.setMinimumWidth(520)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 20)
    lay.setSpacing(10)
    lay.addWidget(QLabel(tr("Copy the project into your ChromIQ folder as:"), dlg))
    edit = QLineEdit(default_name, dlg)
    edit.selectAll()
    lay.addWidget(edit)
    err = QLabel("", dlg)
    # A VALIDATION LINE IS EMPTY UNTIL IT HAS SOMETHING TO SAY, which is why no
    # pixel census has drawn this one: it only fills in when the name you typed
    # is one this dialog cannot accept. Its appearing IS the alarm, and the text
    # says what is wrong — so the red was decoration and `set_ink` takes it out
    # in Neutral, handing Light and Dark the same `#e05555` they had.
    from ui.widgets import set_ink
    set_ink(err, "#e05555")
    err.setWordWrap(True)
    lay.addWidget(err)
    out = {"val": None}
    row = QHBoxLayout()
    cont = QPushButton(tr("Continue"), dlg)
    cont.setDefault(True)
    # "Replace it" — the same words as everywhere else, and the same as
    # the error line below, which named a button that was not on screen.
    replace_btn = QPushButton(tr("Replace it"), dlg)
    replace_btn.setAutoDefault(False)
    replace_btn.setVisible(False)
    row.addWidget(cont)
    row.addWidget(replace_btn)
    row.addStretch(1)
    cancel = QPushButton(tr("Cancel"), dlg)
    cancel.setAutoDefault(False)
    cancel.clicked.connect(dlg.reject)
    row.addWidget(cancel)
    lay.addLayout(row)

    def _exists(name):
        return (Path(working_dir) / FileManager._sanitise(
            FileManager.strip_workfile_ext(name))).exists()

    def _accept(replace):
        name = edit.text().strip()
        if not name:
            err.setText(tr("Please enter a name.")); return
        # THE SAME DOOR AS EVERY OTHER NAME BOX. This one was missed when the
        # other four were routed through `name_prompt.validate`: it knew only
        # "empty" and "already taken", so it was looser even than the four-line
        # checks the loaders used to carry — a 250-character name, `CON`,
        # `.hidden` and `bad:name` all came through. Two of its three callers
        # then COPY A WHOLE PROJECT into that folder and the third calls
        # `start_new_project`, so the first page bitmap dies with Errno 63
        # (`<250 chars>_01.tif` is 257 bytes) and `CON` makes a folder Windows
        # cannot open. The sentence is `validate`'s own, in the error label
        # this dialog already has — no new wording reaches a user.
        # `on_disk` — a name already on disk is a fixed point, and this window
        # exists to REPLACE such a project, which reuses its paths rather than
        # lengthening them. Without it, tightening the length cap for Windows
        # would refuse to re-import into a project ChromIQ itself made under the
        # older cap. See `core.path_budget`.
        from ui.dialogs.name_prompt import validate as _one_door
        _why = _one_door(edit.text(), on_disk=_exists(name))
        if _why is not None:
            err.setText(_why); return
        if _exists(name) and not replace:
            replace_btn.setVisible(True)
            err.setText(tr("A project named “{name}” already exists. Choose a "
                           "different name, or Replace it (the existing one is "
                           "moved to its own old/ folder).").format(name=name))
            return
        if replace:
            # A SECOND LOOK. This archived a whole project on ONE CLICK, with
            # no confirmation of any kind — the only replace route in the app
            # that did. Its own message, because what arrives here is a whole
            # project with its own runs, not a file landing in run 1.
            from PyQt6.QtWidgets import QMessageBox as _QMB
            from workflow import measurement_messages as _M
            _dest = Path(working_dir) / FileManager._sanitise(
                FileManager.strip_workfile_ext(name))
            _t, _b = _M.M_IMPORT_REPLACE_PROJECT_CONFIRM.render(
                name=name, folder=str(_dest))
            _box = _QMB(dlg)
            _box.setIcon(_QMB.Icon.NoIcon)
            _box.setWindowTitle(_t)
            _box.setText(_t)
            _box.setInformativeText(_b)
            _yes = _box.addButton(tr("Replace it"),
                                  _QMB.ButtonRole.DestructiveRole)
            _back = _box.addButton(tr("Go back"), _QMB.ButtonRole.RejectRole)
            _box.setDefaultButton(_back)      # Return must never replace
            from ui.widgets import (fit_message_box_buttons,
                                    spread_message_box_buttons)
            fit_message_box_buttons(_box)
            spread_message_box_buttons(_box, order=[_yes, _back])
            _box.exec()
            if _box.clickedButton() is not _yes:
                return
        out["val"] = (name, replace)
        dlg.accept()

    cont.clicked.connect(lambda: _accept(False))
    replace_btn.clicked.connect(lambda: _accept(True))
    dlg.exec()
    return out["val"]


def _point_bar_at_current_run(controller) -> None:
    """After an import, point the bar at the project's current run so it reflects
    where the chart landed (keeps Run type)."""
    try:
        proj = controller.project_or_none()
        if proj is not None:
            controller.set_profile_run(proj.current_run().id)
    except Exception:      # noqa: BLE001
        pass
    # Force a refresh even when the run id is unchanged, so the Create Chart
    # name field reflects a newly switched-in project (#130 Bug C, Knut).
    controller.notify_changed()


def chart_beside(ti3_path: Path) -> "Path | None":
    """The `.ti2` that will become the chart of the run an import creates.

    ONE EXPRESSION, ONE PLACE. `resolve_ti3` decides by this whether a loose
    measurement brings a chart with it, and the import door has to judge the
    measurement against the very chart that is about to be imported beside it
    (`ui/measurement_filing.py`, round 2 T1-G). Two copies of
    `with_suffix(".ti2")` is how those two come to disagree about what the
    chart even is.
    """
    sibling = Path(ti3_path).with_suffix(".ti2")
    return sibling if sibling.is_file() else None


def resolve_ti3(
    parent: "QWidget",
    ti3_path: Path,
    settings: "AppSettings",
    *,
    name: str | None = None,
) -> Path | None:
    """Determine how to load a .ti3 relative to the working folder.

    Mirrors ``resolve_ti2``: returns the path to use — either the original
    (when the file is already inside a structured project) or a newly copied
    path inside a freshly-created project. Returns ``None`` if the user
    cancelled.

    For an external .ti3 with a sibling .ti2, the full ti2 import flow is
    reused (the .ti2 is the chart; the .ti3 is its measurement). For a bare
    .ti3 (no chart files beside it), a measurement-only project is created.
    Either way, ``Project.create`` writes the "Where are my files.txt" README
    at the new project root so the user gets the new layout on the spot.

    *name* IS THE ANSWER SOMEBODY HAS ALREADY GIVEN, and it is used instead of
    asking again. The import door (`ui/measurement_filing.py`) asks "where
    should this measurement go?" and takes a name; without this it then handed
    the file here, and here asked for the name a second time, in different
    words, with the box empty. One question, one answer, carried. When *name*
    is given, the only window this can still raise is the one that has a
    genuinely different question to ask: a folder of that name already exists
    and something has to be done about it.
    """
    # THE PROMISE THAT NOTHING IS DELETED, KEPT OR EXPLAINED.
    try:
        working_dir = _resolve_working_dir(settings)
        if _project_root_for(ti3_path, working_dir) is not None:
            return ti3_path                              # already in a project
        sibling_ti2 = chart_beside(ti3_path)
        if sibling_ti2 is not None:
            result = _handle_outside(parent, sibling_ti2, working_dir,
                                     name=name)
            if result is None:
                return None
            new_ti2, _tiffs = result
            new_ti3 = new_ti2.with_suffix(".ti3")
            return new_ti3 if new_ti3.exists() else None
        # Bare .ti3 — import the measurement (and sibling .icc, if any) alone.
        return _handle_outside_ti3_only(parent, ti3_path, working_dir,
                                        name=name)
    except ReplaceFailed as exc:
        # ONLY a failed archive. Any other OSError is a different fault and
        # must not be reported as "the existing project could not be moved
        # aside — nothing has been changed", which would be false.
        _say_the_replace_failed(parent, exc.folder, exc.reason)
        return None

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_working_dir(settings: "AppSettings") -> Path:
    custom = settings.get("custom_output_path", "")
    return Path(custom) if custom else default_output_root()


def _project_root_for(path: Path, working_dir: Path) -> Path | None:
    """Return the ChromIQ project root that contains ``path``, or None.

    A project root is any folder UNDER ``working_dir`` (at any depth — projects
    may be organised in sub-folders, #130 Knut) that holds a ``project.json``.
    ``path`` counts as "inside" when such a manifest is found walking up from it
    — so a chart already structured as ``<project>/runs/<id>/chart.ti2`` (or a
    calibration in ``<project>/cal/``) is recognised and not re-imported.
    """
    try:
        p = path.resolve()
        wd = working_dir.resolve()
        p.relative_to(wd)               # must live under the ChromIQ folder
    except ValueError:
        return None
    cur = p.parent
    while True:
        if (cur / "project.json").exists():
            return cur
        if cur == wd or wd not in cur.parents:
            return None                 # reached the ChromIQ folder, no project
        cur = cur.parent


def _related_files(ti2_path: Path) -> tuple[Path | None, list[Path]]:
    """Return (ti1_or_None, sorted_tiff_list) for a given .ti2."""
    from core.file_manager import stem_files
    folder = ti2_path.parent
    stem   = ti2_path.stem
    ti1    = folder / f"{stem}.ti1"
    # Set-comprehension dedupes Windows' case-insensitive glob matches
    # (chart.tif matches both *.tif and *.TIF), which otherwise made the
    # preview show "Page 1/2 and 2/2" for a single-file chart when *loading an
    # existing target* (forum #148275 — same root cause as the generation-path
    # fix in chart_creator._printtarg_done for #148124).
    tiffs  = sorted({
        *stem_files(folder, stem, "*.tif", "*.TIF", "*.tiff"),
    })
    return (ti1 if ti1.exists() else None), tiffs


def _name_is_free(working_dir: Path, name: str) -> bool:
    """Whether *name* can be used without asking anybody anything.

    The name has already been answered for at the import door; the only thing
    that can still need a window is a folder that is already sitting there.
    Judged on the SANITISED name, because that is the folder that will really
    be made — asking about the typed string was the trap that reported
    "Demo-Report-Matrix copy" free while its sanitised twin existed.
    """
    from core.file_manager import FileManager
    cleaned = FileManager.strip_workfile_ext(name or "")
    if not cleaned.strip():
        return False
    try:
        return not (working_dir / FileManager._sanitise(cleaned)).exists()
    except OSError:
        return False


def _handle_outside(
    parent: "QWidget",
    ti2_path: Path,
    working_dir: Path,
    *,
    name: str | None = None,
) -> tuple[Path, list[Path]] | None:
    ti1, tiffs = _related_files(ti2_path)
    if name and _name_is_free(working_dir, name):
        result = (name, False)           # asked at the door, answered there
    else:
        result = _ask_profile_name(parent, ti2_path, ti1, tiffs, working_dir,
                                   prefill=name or "")
    if result is None:
        return None
    new_name, overwrite = result
    out = _copy_files(ti2_path, ti1, tiffs, working_dir, new_name, overwrite=overwrite)
    if overwrite:
        _say_where_the_old_project_went(parent, new_name, working_dir / new_name)
    return out


def _handle_inside(
    parent: "QWidget",
    ti2_path: Path,
    working_dir: Path,
) -> tuple[Path, list[Path]] | None:
    from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("Load Test Session"))
    dlg.setMinimumWidth(460)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)

    lbl = QLabel(
        tr("The session <b>{name}</b> is already set up in your working "
           "folder.<br><br>"
           "What would you like to do?").format(name=ti2_path.stem),
        dlg,
    )
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    cont_desc = QLabel(
        tr("<i>Continue</i>: use the files in this folder as they are. "
        "Nothing will be copied or moved."),
        dlg,
    )
    cont_desc.setWordWrap(True)
    layout.addWidget(cont_desc)

    new_desc = QLabel(
        tr("<i>Use as base for a new profile</i>: copy the files to a new "
        "subfolder so you can build a separate ICC profile without overwriting "
        "the original."),
        dlg,
    )
    new_desc.setWordWrap(True)
    layout.addWidget(new_desc)

    btn_box    = QDialogButtonBox(dlg)
    cont_btn   = btn_box.addButton(tr("Continue"),                     QDialogButtonBox.ButtonRole.AcceptRole)
    new_btn    = btn_box.addButton(tr("Use as base for a new profile"), QDialogButtonBox.ButtonRole.ActionRole)
    cancel_btn = btn_box.addButton(tr("Cancel"),                        QDialogButtonBox.ButtonRole.RejectRole)
    layout.addWidget(btn_box)

    choice: list[str | None] = [None]

    def _on_continue() -> None:
        choice[0] = "continue"
        dlg.accept()

    def _on_new() -> None:
        choice[0] = "new"
        dlg.accept()

    cont_btn.clicked.connect(_on_continue)
    new_btn.clicked.connect(_on_new)
    cancel_btn.clicked.connect(dlg.reject)
    dlg.exec()

    if choice[0] == "continue":
        # Run the project through Project.load so an in-place load benefits
        # from the load-time housekeeping (README backfill, v1→v2 folder
        # migration, #127) exactly like a session restore. Best-effort — a
        # corrupt manifest must not block using the chart files as-is.
        root = _project_root_for(ti2_path, working_dir)
        if root is not None:
            try:
                from core.file_manager import Project
                Project.load(root)
            except Exception:  # noqa: BLE001
                log.warning("in-place load: could not run project "
                            "housekeeping for %s", root, exc_info=True)
        _, tiffs = _related_files(ti2_path)
        return ti2_path, tiffs
    if choice[0] == "new":
        ti1, tiffs = _related_files(ti2_path)
        result = _ask_profile_name(parent, ti2_path, ti1, tiffs, working_dir)
        if result is None:
            return None
        new_name, overwrite = result
        out = _copy_files(ti2_path, ti1, tiffs, working_dir, new_name, overwrite=overwrite)
        if overwrite:
            _say_where_the_old_project_went(parent, new_name, working_dir / new_name)
        return out
    return None


def _ask_profile_name(
    parent: "QWidget",
    ti2_path: Path,
    ti1: Path | None,
    tiffs: list[Path],
    working_dir: Path,
    subject: str | None = None,
    is_measurement: bool = False,
    prefill: str = "",
) -> tuple[str, bool] | None:
    # *prefill* is a name the person has ALREADY given, at the import door.
    # This window then opens with it in the box and its collision line already
    # showing, so what is being asked is the one thing the door could not
    # answer — replace what is there, or choose another name — rather than the
    # name all over again. It used to arrive empty: the answer to "Give this
    # project a name" was discarded, and pressing OK without retyping was
    # refused with "Please enter a name." (R3 review F2).
    # *subject* names what is being imported, for the windows this dialog
    # raises. It is shared by two routes that import different things: three
    # callers hand it a .ti2 (a chart) and one hands it a bare .ti3 (a
    # measurement), and it called both "chart files" — so somebody importing a
    # measurement was asked to confirm replacing a project "with the imported
    # chart files".
    """Ask the user for a profile name.

    Returns (name, overwrite) — `overwrite=True` means the user explicitly
    confirmed wiping an existing folder of the same name. Returns None if
    the user cancelled.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import (
        QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
    )

    # Build the file list, deduping so the bare-.ti3 import path (where
    # ti2_path is actually a .ti3) doesn't list the same file twice.
    seen: set[Path] = set()
    file_lines: list[str] = []
    def _add(p: Path) -> None:
        try:
            r = p.resolve()
        except OSError:
            r = p
        if r not in seen:
            seen.add(r)
            file_lines.append(f"  • {p.name}")
    _add(ti2_path)
    if ti1:
        _add(ti1)
    for t in tiffs:
        _add(t)
    ti3 = ti2_path.with_suffix(".ti3")
    if ti3.exists():
        _add(ti3)
    for ext in (".icc", ".icm"):
        icc = ti2_path.with_suffix(ext)
        if icc.exists():
            _add(icc)
            break

    dlg = QDialog(parent)
    # The title follows what is being imported: this dialog serves three
    # .ti2 callers and one bare-.ti3 caller, and called a measurement
    # "Chart Files". On macOS a QDialog title is on screen.
    # NEVER match on the TRANSLATED text. `subject` arrives already through
    # `tr()`, so `"measurement" in subject` is true in English and false in
    # every other language — the title fell back to "Copy Chart Files" in 12 of
    # 13, which is the exact fault this was written to fix.
    dlg.setWindowTitle(tr("Copy the measurement in") if is_measurement
                       else tr("Copy Chart Files"))
    dlg.setMinimumWidth(580)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(10)

    info = QLabel(
        tr("The following files from <b>{folder}/</b> will be "
           "copied into your working folder as a new profile set:<br><br>"
           "<pre>{files}</pre>"
           "They will be placed in:<br>"
           "<code>{target}/&lt;name&gt;/</code><br><br>"
           "Enter a name for the new profile:").format(
            folder=ti2_path.parent.name,
            files="<br>".join(file_lines),
            target=working_dir,
        ),
        dlg,
    )
    info.setWordWrap(True)
    layout.addWidget(info)

    name_edit = QLineEdit(dlg)
    name_edit.setPlaceholderText(tr("e.g. Canon_ProGraf_Glossy_240g"))
    layout.addWidget(name_edit)

    error_lbl = QLabel("", dlg)
    # Hidden until the name is refused — see the note on the other validation
    # line in this module.
    from ui.widgets import set_ink
    set_ink(error_lbl, "#e05555")
    error_lbl.setWordWrap(True)
    layout.addWidget(error_lbl)

    btn_row = QHBoxLayout()

    ok_btn = QPushButton(tr("OK"), dlg)
    ok_btn.setDefault(True)
    btn_row.addWidget(ok_btn)

    overwrite_btn = QPushButton(tr("Replace it"), dlg)
    overwrite_btn.setAutoDefault(False)
    overwrite_btn.setVisible(False)
    btn_row.addWidget(overwrite_btn)

    btn_row.addStretch(1)

    cancel_btn = QPushButton(tr("Cancel"), dlg)
    cancel_btn.setAutoDefault(False)
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn)

    layout.addLayout(btn_row)

    result: dict = {"name": None, "overwrite": False}

    def _is_self_collision(name: str) -> bool:
        """True when the folder we would replace HOLDS the file being imported."""
        return is_self_collision(working_dir, name, ti2_path)

    def _self_collision_line(name: str) -> str:
        """…and it says "project" only when it IS one (round 2, T1-D)."""
        from core.file_manager import is_a_project
        from workflow import measurement_messages as M
        if is_a_project(working_dir / name):
            return tr("That project holds the file you are importing, so "
                      "replacing it would take the file with it. Please pick "
                      "a different name.")
        return M.self_collision_folder_line()

    def _normalise(text: str) -> str:
        """Sanitise the typed name the same way set_target_name does (spaces→-,
        illegal chars→_), so the on-disk folder = the user-facing name. Empty
        in → empty out (so the dialog can still report "please enter a name")."""
        from core.file_manager import FileManager
        cleaned = FileManager.strip_workfile_ext(text)
        return FileManager._sanitise(cleaned) if cleaned.strip() else ""

    def _validate(name: str) -> str | None:
        """The shape of a name — asked at THE one door, not at this one.

        This used to be a private four-line check that knew about the forbidden
        characters and nothing else, and it was handed the ALREADY SANITISED
        name, which no longer has any: so it passed everything. A 250-character
        name and `CON` both came through, and `ui/dialogs/name_prompt` is the
        module whose own docstring names these loaders as the two copies of this
        question that had drifted. Driven, before and after:
        `review/FIX-NAMES/evidence/*-f2-doors.txt`.

        The TYPED text goes in, not the sanitised name — `validate` judges both,
        and a leading dot or a device name is a fact about what the person
        typed.

        A NAME ALREADY ON DISK IS A FIXED POINT, so a name that is already a
        project is judged without the LENGTH rule — the window's own job here
        is to replace that project, which reuses its paths and adds nothing to
        them. Without this, tightening the cap for Windows would refuse to
        re-import into a project ChromIQ itself made under the older cap.
        """
        from core.file_manager import is_a_project
        from ui.dialogs.name_prompt import validate as _one_door
        folder = _normalise(name)
        return _one_door(name, on_disk=bool(folder)
                         and is_a_project(working_dir / folder))

    def _on_name_changed(_text: str = "") -> None:
        name = _normalise(name_edit.text())
        collision = bool(name) and (working_dir / name).exists() and not _is_self_collision(name)
        if collision:
            # WHICH OF THE TWO IT IS, because they are not the same thing and
            # this line asserts one of them. `.exists()` alone said "already a
            # project" about any folder at all - including the plain folder
            # whose NOT being a project is the only reason this window opens
            # (round 2, T1-D). M-IMPORT-FOLDER-EXISTS, approved by Basti on 2026-09-02.
            from core.file_manager import is_a_project
            from workflow import measurement_messages as M
            if is_a_project(working_dir / name):
                error_lbl.setText(
                    tr("“{name}” is already a project. Choose a different name, "
                       "or click “Replace it”.").format(name=name)
                )
            else:
                error_lbl.setText(M.folder_taken_line(name))
            ok_btn.setVisible(False)
            overwrite_btn.setVisible(True)
        else:
            error_lbl.setText("")
            ok_btn.setVisible(True)
            overwrite_btn.setVisible(False)

    name_edit.textChanged.connect(_on_name_changed)
    # AFTER the connection, so the collision line and the Replace button are
    # already correct for the name that was carried in. Setting it before would
    # show the name with the window still dressed as though nothing existed.
    if prefill:
        name_edit.setText(prefill)
        name_edit.selectAll()

    def _on_accept() -> None:
        name = _normalise(name_edit.text())
        err = _validate(name_edit.text())
        if err:
            error_lbl.setText(err)
            return
        if (working_dir / name).exists() and not _is_self_collision(name):
            _on_name_changed()
            return
        if _is_self_collision(name):
            error_lbl.setText(_self_collision_line(name))
            return
        result["name"] = name
        result["overwrite"] = False
        dlg.accept()

    def _on_overwrite() -> None:
        name = _normalise(name_edit.text())
        err = _validate(name_edit.text())
        if err:
            error_lbl.setText(err)
            return
        if _is_self_collision(name):
            error_lbl.setText(_self_collision_line(name))
            return
        dest = working_dir / name
        if not dest.exists():
            result["name"] = name
            result["overwrite"] = False
            dlg.accept()
            return
        # THE SECOND LOOK, IN THE WORDS §S4.7 USES — see the twin in
        # `ui/txt_loader.py`. It promised to "permanently delete", which was
        # true when this ran `shutil.rmtree` and is a lie now that it archives.
        # Rendered from the catalogue because WINDOW_SOURCES cannot express a
        # module-level function, so literals here are checked by nothing.
        # `QMessageBox()` rather than the `.warning` static, which runs its own
        # C++ event loop and cannot be reached by a test.
        from workflow import measurement_messages as M
        _subject = subject or tr("the chart")
        # …AND THE SECOND LOOK SAYS WHICH OF THE TWO IT IS MOVING ASIDE.
        # M-IMPORT-REPLACE-CONFIRM opens "Everything this project holds", which
        # is false of a folder that is not one - and a folder that is not one
        # is the ONLY thing this branch can be reached for once the collision
        # line above tells them apart (round 2, T1-D).
        # M-IMPORT-REPLACE-FOLDER-CONFIRM, approved by Basti on 2026-09-02.
        from core.file_manager import is_a_project
        _confirm = (M.M_IMPORT_REPLACE_CONFIRM if is_a_project(dest)
                    else M.M_IMPORT_REPLACE_FOLDER_CONFIRM)
        _title, _body = _confirm.render(
            name=name, folder=str(dest), subject=_subject)
        _box = QMessageBox(dlg)
        _box.setIcon(QMessageBox.Icon.NoIcon)
        _box.setWindowTitle(_title)
        _box.setText(_title)
        _box.setInformativeText(_body)
        _yes = _box.addButton(tr("Replace it"),
                              QMessageBox.ButtonRole.DestructiveRole)
        _back = _box.addButton(tr("Go back"), QMessageBox.ButtonRole.RejectRole)
        _box.setDefaultButton(_back)     # Return must never be a replace
        # The house rules: fit each button to its words, and Cancel/Go back on
        # the far right (Basti, 2026-08-27; the clipping fault is Knut's #130).
        from ui.widgets import (fit_message_box_buttons,
                                spread_message_box_buttons)
        fit_message_box_buttons(_box)
        spread_message_box_buttons(_box, order=[_yes, _back])
        _box.exec()
        if _box.clickedButton() is _yes:
            result["name"] = name
            result["overwrite"] = True
            dlg.accept()

    ok_btn.clicked.connect(_on_accept)
    overwrite_btn.clicked.connect(_on_overwrite)

    QTimer.singleShot(0, name_edit.setFocus)
    if dlg.exec() == QDialog.DialogCode.Accepted and result["name"]:
        return result["name"], result["overwrite"]
    return None


def _copy_files(
    ti2_path: Path,
    ti1: Path | None,
    tiffs: list[Path],
    working_dir: Path,
    new_name: str,
    overwrite: bool = False,
) -> tuple[Path, list[Path]]:
    """Import an external chart into a fresh project as run1.

    Builds the per-run layout (see docs/dev_folder_layout.md): a project at
    ``working_dir/<new_name>/`` with ``project.json`` and the imported chart
    placed under ``runs/run1/`` with the canonical ``chart`` stem
    (``chart.ti2`` / ``chart.ti1`` / ``chart_NN.tif`` / ``chart.ti3`` /
    ``chart.icc``). Returns (run1 chart.ti2, copied page tiffs).
    """
    from core.file_manager import FileManager, Project

    # Defensive: the dialog already sanitises, but make the contract explicit
    # so any programmatic caller also gets a clean folder name.
    new_name = FileManager._sanitise(FileManager.strip_workfile_ext(new_name))

    old_stem = ti2_path.stem
    dest      = working_dir / new_name
    if overwrite and dest.exists():
        # ARCHIVE, NEVER DESTROY. §S4.7 of the measurement specification says a
        # replace "archive[s] the whole project into its `old/`", and T2.6 says
        # "nothing is ever deleted" — but these three import routes reached for
        # `shutil.rmtree`, which is not atomic: it removes what it can and
        # raises at the end, so one unwritable sub-folder left a project with
        # one file of six, `project.json` among the casualties, while the app
        # reported that nothing had changed (`core/trash.py` records the
        # measurement). Basti's ruling, 2026-08-31.
        #
        # Archiving into the SAME folder and then calling `Project.create` on it
        # is safe: `create` is `mkdir(exist_ok=True)` and removes nothing, so
        # the `old/` written here survives the new project being made on top.
        from workflow.chart_import import (ReplaceFailed,
                                            _archive_project_contents)
        try:
            _kept_at = _archive_project_contents(dest)
        except OSError as exc:
            raise ReplaceFailed(dest, exc) from exc
        log.info("replaced %s, everything it held is kept at %s", dest, _kept_at)

    proj = Project.create(dest, new_name)
    run  = proj.current_run()
    run.ensure_dir()

    shutil.copy2(ti2_path, run.chart_ti2)
    if ti1:
        shutil.copy2(ti1, run.chart_ti1)

    # Chart recognition + channels sidecar travel with the chart when present.
    cht = ti2_path.with_suffix(".cht")
    if cht.exists():
        shutil.copy2(cht, run.chart_cht)
    channels = ti2_path.with_name(f"{old_stem}.channels.json")
    if channels.exists():
        shutil.copy2(channels, run.chart_channels_json)

    # Pages are renumbered <stem>_01.tif, <stem>_02.tif, … in sorted order.
    new_tiffs: list[Path] = []
    for i, tiff in enumerate(sorted(tiffs), start=1):
        new_tiff = run.dir / f"{run.stem}_{i:02d}.tif"
        shutil.copy2(tiff, new_tiff)
        new_tiffs.append(new_tiff)

    ti3 = ti2_path.with_suffix(".ti3")
    if ti3.exists():
        shutil.copy2(ti3, run.measurement_ti3)   # chart.ti3

    for ext in (".icc", ".icm"):
        icc = ti2_path.with_suffix(ext)
        if icc.exists():
            shutil.copy2(icc, run.profile_icc)    # chart.icc
            break

    return run.chart_ti2, new_tiffs


def _handle_outside_ti3_only(
    parent: "QWidget",
    ti3_path: Path,
    working_dir: Path,
    *,
    name: str | None = None,
) -> Path | None:
    """Import a bare .ti3 (no chart files) into a new project as the
    canonical measurement. The matching .icc/.icm is carried over too.
    Reuses _ask_profile_name to gather the project name + overwrite intent —
    unless *name* was already answered for at the import door, in which case
    nothing is asked at all and that answer is what is used."""
    if name and _name_is_free(working_dir, name):
        result = (name, False)
    else:
        result = _ask_profile_name(parent, ti3_path, ti1=None, tiffs=[],
                                   subject=tr("the measurement"),
                                   is_measurement=True,
                                   working_dir=working_dir,
                                   prefill=name or "")
    if result is None:
        return None
    name, overwrite = result
    return _copy_ti3_only(ti3_path, working_dir, name, overwrite=overwrite)


def _copy_ti3_only(
    ti3_path: Path,
    working_dir: Path,
    new_name: str,
    overwrite: bool = False,
) -> Path:
    """Create a project shell around an external .ti3.

    Places the .ti3 at ``runs/run1/<new_name>.ti3`` (the canonical
    measurement) and a sibling .icc/.icm (if present) at
    ``runs/run1/<new_name>.icc``. Returns the new .ti3 path.
    """
    from core.file_manager import FileManager, Project

    new_name = FileManager._sanitise(FileManager.strip_workfile_ext(new_name))
    dest = working_dir / new_name
    if overwrite and dest.exists():
        # ARCHIVE, NEVER DESTROY. §S4.7 of the measurement specification says a
        # replace "archive[s] the whole project into its `old/`", and T2.6 says
        # "nothing is ever deleted" — but these three import routes reached for
        # `shutil.rmtree`, which is not atomic: it removes what it can and
        # raises at the end, so one unwritable sub-folder left a project with
        # one file of six, `project.json` among the casualties, while the app
        # reported that nothing had changed (`core/trash.py` records the
        # measurement). Basti's ruling, 2026-08-31.
        #
        # Archiving into the SAME folder and then calling `Project.create` on it
        # is safe: `create` is `mkdir(exist_ok=True)` and removes nothing, so
        # the `old/` written here survives the new project being made on top.
        from workflow.chart_import import (ReplaceFailed,
                                            _archive_project_contents)
        try:
            _kept_at = _archive_project_contents(dest)
        except OSError as exc:
            raise ReplaceFailed(dest, exc) from exc
        log.info("replaced %s, everything it held is kept at %s", dest, _kept_at)

    proj = Project.create(dest, new_name)
    run  = proj.current_run()
    run.ensure_dir()

    shutil.copy2(ti3_path, run.measurement_ti3)
    for ext in (".icc", ".icm"):
        icc = ti3_path.with_suffix(ext)
        if icc.exists():
            shutil.copy2(icc, run.profile_icc)
            break
    return run.measurement_ti3
