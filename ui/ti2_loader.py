"""Shared ti2 file loading workflow: working-folder detection, copy/rename dialogs."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt

from core.i18n import tr
from core.logger import get_logger
from core.measurement_target import (RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
                                     MeasurementTarget)
import workflow.chart_import as _chart_import

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
KNOWN_INSTRUMENTS: tuple[str, ...] = (
    "X-Rite ColorMunki",          # ColorMunki / i1Studio / ColorChecker Studio
    "GretagMacbeth i1 Pro",       # i1 Pro family (i1 Pro / Pro 2 / Pro 3 / Pro 3+)
    "GretagMacbeth SpectroScan",  # motorized XY table (patch-by-patch, not strips)
)


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


def instrument_family(name: str | None) -> "str | None":
    """Coarse instrument family for instruction wording: ``"colormunki"``
    (ColorMunki / i1Studio / ColorChecker Studio), ``"i1pro"`` (the whole i1 Pro
    line — Argyll tags them all the same, so they share one instruction set),
    ``"spectroscan"`` (XY table), or ``None`` when unrecognised (→ generic
    wording). Accepts a TARGET_INSTRUMENT value or spotread's reported model."""
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
            "once</b>. Hold it still until the reading is taken — there is no "
            "sliding in this mode.")
    if family == "i1pro":
        return tr(
            "Take the i1Pro off its base. Place it flat on the highlighted "
            "patch so the aperture sits fully inside it, and <b>press the "
            "button once</b>. Keep it still until the reading is taken — there "
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
    SpectroScan reads patches individually. Users can still pick "Bidirectional
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
    those charts. The ColorMunki reads one direction only and the SpectroScan
    reads patches individually, so neither should force it. ``-b`` and ``-B``
    are mutually exclusive; this only returns True for the i1 Pro family.
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

    parts = [f"<b>{title}</b>"]
    if intro_html:
        parts.append(intro_html)
    parts.append(tr("What each button does:"))
    for label, desc, _key in choices:
        parts.append(f"&nbsp;&nbsp;•&nbsp; <b>{label}</b> — {desc}")
    parts.append(tr("&nbsp;&nbsp;•&nbsp; <b>Cancel</b> — nothing is opened, "
                    "copied or changed, and the file you picked is left exactly "
                    "as it is."))
    box.setText("<br><br>".join(parts))

    # ActionRole keeps them in the order given, before Cancel, under the app's
    # button-layout style.
    buttons = {}
    for label, _desc, key in choices:
        buttons[box.addButton(label, QMessageBox.ButtonRole.ActionRole)] = key
    cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)

    from ui.widgets import fit_message_box_buttons
    fit_message_box_buttons(box)
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
    return sorted(ti2_in_project.parent.glob(f"{ti2_in_project.stem}_*.tif"))


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
            desc = tr("Copies the chart — and its measurement (.ti3) and profile "
                      "(.icc/.icm) if present — into a brand-new run inside the "
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
                     "<code>runs/{run}/verifications/old/</code> — nothing is "
                     "deleted — and then installs the loaded chart as this run's "
                     "verification chart in <code>runs/{run}/verifications/</code>. "
                     "Your dated verification results are kept exactly where they "
                     "are, and so are this run's own chart, measurement and "
                     "printer profile. Any .icc/.icm and .ti3 beside the loaded "
                     "file are ignored.").format(run=rid)
        else:
            rep = tr("Moves this run's chart, measurement and printer profile — "
                     "together with every folder inside it, including its "
                     "reports and verifications — into "
                     "<code>runs/{run}/old/</code>, and then copies the loaded "
                     "files into <code>runs/{run}/</code>. Nothing is deleted. "
                     "Everything moves because a new chart no longer matches the "
                     "measurement, profile or checks made from the old one."
                     ).format(run=rid)
        key = _choice_dialog(parent, tr("Import this chart"), header, [
            (tr("Create a new run instead"),
             tr("Imports into a brand-new run — <code>runs/{new}/</code> — inside "
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
        (tr("Open {name}").format(name=name),
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
        (tr("Open {name}").format(name=other),
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
            "into your ChromIQ folder. Profile run / Run type are not used — the "
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
        return run.chart_ti2, sorted(run.dir.glob(f"{run.stem}_*.tif"))
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
    err.setStyleSheet("color:#e05555;")
    err.setWordWrap(True)
    lay.addWidget(err)
    out = {"val": None}
    row = QHBoxLayout()
    cont = QPushButton(tr("Continue"), dlg)
    cont.setDefault(True)
    replace_btn = QPushButton(tr("Replace existing"), dlg)
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
        if _exists(name) and not replace:
            replace_btn.setVisible(True)
            err.setText(tr("A project named “{name}” already exists. Choose a "
                           "different name, or Replace it (the existing one is "
                           "moved to its own old/ folder).").format(name=name))
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


def resolve_ti3(
    parent: "QWidget",
    ti3_path: Path,
    settings: "AppSettings",
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
    """
    working_dir = _resolve_working_dir(settings)
    if _project_root_for(ti3_path, working_dir) is not None:
        return ti3_path                              # already in a project
    sibling_ti2 = ti3_path.with_suffix(".ti2")
    if sibling_ti2.is_file():
        result = _handle_outside(parent, sibling_ti2, working_dir)
        if result is None:
            return None
        new_ti2, _tiffs = result
        new_ti3 = new_ti2.with_suffix(".ti3")
        return new_ti3 if new_ti3.exists() else None
    # Bare .ti3 — import the measurement (and sibling .icc, if any) alone.
    return _handle_outside_ti3_only(parent, ti3_path, working_dir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_working_dir(settings: "AppSettings") -> Path:
    custom = settings.get("custom_output_path", "")
    return Path(custom) if custom else Path.home() / "ChromIQ"


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
    folder = ti2_path.parent
    stem   = ti2_path.stem
    ti1    = folder / f"{stem}.ti1"
    # Set-comprehension dedupes Windows' case-insensitive glob matches
    # (chart.tif matches both *.tif and *.TIF), which otherwise made the
    # preview show "Page 1/2 and 2/2" for a single-file chart when *loading an
    # existing target* (forum #148275 — same root cause as the generation-path
    # fix in chart_creator._printtarg_done for #148124).
    tiffs  = sorted({
        *folder.glob(f"{stem}*.tif"),
        *folder.glob(f"{stem}*.TIF"),
        *folder.glob(f"{stem}*.tiff"),
    })
    return (ti1 if ti1.exists() else None), tiffs


def _handle_outside(
    parent: "QWidget",
    ti2_path: Path,
    working_dir: Path,
) -> tuple[Path, list[Path]] | None:
    ti1, tiffs = _related_files(ti2_path)
    result = _ask_profile_name(parent, ti2_path, ti1, tiffs, working_dir)
    if result is None:
        return None
    new_name, overwrite = result
    return _copy_files(ti2_path, ti1, tiffs, working_dir, new_name, overwrite=overwrite)


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
        tr("<i>Continue</i> — use the files in this folder as-is — "
        "nothing will be copied or moved."),
        dlg,
    )
    cont_desc.setWordWrap(True)
    layout.addWidget(cont_desc)

    new_desc = QLabel(
        tr("<i>Use as base for a new profile</i> — copy the files to a new "
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
        return _copy_files(ti2_path, ti1, tiffs, working_dir, new_name, overwrite=overwrite)
    return None


def _ask_profile_name(
    parent: "QWidget",
    ti2_path: Path,
    ti1: Path | None,
    tiffs: list[Path],
    working_dir: Path,
) -> tuple[str, bool] | None:
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
    dlg.setWindowTitle(tr("Copy Chart Files"))
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
    error_lbl.setStyleSheet("color: #e05555;")
    error_lbl.setWordWrap(True)
    layout.addWidget(error_lbl)

    btn_row = QHBoxLayout()

    ok_btn = QPushButton(tr("OK"), dlg)
    ok_btn.setDefault(True)
    btn_row.addWidget(ok_btn)

    overwrite_btn = QPushButton(tr("Overwrite existing folder"), dlg)
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
        # Guard against rmtree'ing the .ti2's own parent folder
        # (only possible when loading a chart that already lives inside
        # the working folder).
        try:
            return (working_dir / name).resolve() == ti2_path.parent.resolve()
        except OSError:
            return False

    def _normalise(text: str) -> str:
        """Sanitise the typed name the same way set_target_name does (spaces→-,
        illegal chars→_), so the on-disk folder = the user-facing name. Empty
        in → empty out (so the dialog can still report "please enter a name")."""
        from core.file_manager import FileManager
        cleaned = FileManager.strip_workfile_ext(text)
        return FileManager._sanitise(cleaned) if cleaned.strip() else ""

    def _validate(name: str) -> str | None:
        if not name:
            return "Please enter a name."
        if any(c in name for c in r'/\:*?"<>|'):
            return "Name contains invalid characters."
        return None

    def _on_name_changed(_text: str = "") -> None:
        name = _normalise(name_edit.text())
        collision = bool(name) and (working_dir / name).exists() and not _is_self_collision(name)
        if collision:
            error_lbl.setText(
                tr("“{name}” already exists. Click “Overwrite existing folder” to replace it.").format(name=name)
            )
            ok_btn.setVisible(False)
            overwrite_btn.setVisible(True)
        else:
            error_lbl.setText("")
            ok_btn.setVisible(True)
            overwrite_btn.setVisible(False)

    name_edit.textChanged.connect(_on_name_changed)

    def _on_accept() -> None:
        name = _normalise(name_edit.text())
        err = _validate(name)
        if err:
            error_lbl.setText(err)
            return
        if (working_dir / name).exists() and not _is_self_collision(name):
            _on_name_changed()
            return
        if _is_self_collision(name):
            error_lbl.setText(
                tr("That name points to the chart's own folder. Pick a different name.")
            )
            return
        result["name"] = name
        result["overwrite"] = False
        dlg.accept()

    def _on_overwrite() -> None:
        name = _normalise(name_edit.text())
        err = _validate(name)
        if err:
            error_lbl.setText(err)
            return
        if _is_self_collision(name):
            error_lbl.setText(
                tr("You're trying to overwrite the chart's own folder. "
                "Pick a different name.")
            )
            return
        dest = working_dir / name
        if not dest.exists():
            result["name"] = name
            result["overwrite"] = False
            dlg.accept()
            return
        confirm = QMessageBox.warning(
            dlg,
            tr("Overwrite existing folder?"),
            tr("This will permanently delete:\n\n    {dest}\n\n"
               "and replace it with the imported chart files. Continue?"
               ).format(dest=dest),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
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
        shutil.rmtree(dest)

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
) -> Path | None:
    """Import a bare .ti3 (no chart files) into a new project as the
    canonical measurement. The matching .icc/.icm is carried over too.
    Reuses _ask_profile_name to gather the project name + overwrite intent."""
    result = _ask_profile_name(parent, ti3_path, ti1=None, tiffs=[],
                                working_dir=working_dir)
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
        shutil.rmtree(dest)

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
