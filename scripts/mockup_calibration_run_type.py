"""Mockups for the "Calibration as a Run type" design draft (#130).

These are **not drawings**. The real MainWindow is launched with the real fonts,
the real theme and the real widgets; the live widgets are then put into the
*proposed* state and grabbed. What you see is what the app would look like, at
the pixel — only the state is invented, never the styling.

Nothing here touches the app's code paths: every change is made to widget
instances after construction, and the script quits when it is done.

    source .venv/bin/activate
    python scripts/mockup_calibration_run_type.py [dark|light]

Output: docs/design/mockups/calibration_run_type/*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtGui import QFontDatabase                          # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402
import PyQt6.QtWebEngineWidgets  # noqa: F401,E402  (must precede QApplication)

from core.resource_path import resource_path                   # noqa: E402
from core.settings import AppSettings                          # noqa: E402
from ui.styles import WinButtonLayoutStyle                     # noqa: E402
from ui.theme import apply_appearance                          # noqa: E402
from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter  # noqa: E402
from ui.main_window import MainWindow                          # noqa: E402

OUT = ROOT / "docs" / "design" / "mockups" / "calibration_run_type"
PROJECT = Path.home() / "ChromIQ" / "Canon-Pro300-CanonSG-i1Pro"
#: The home folder is written the way the app writes it in help text —
#: these images are published, and nobody's user name belongs in them.
PROJECT_SHOWN = f"~/ChromIQ/{PROJECT.name}"


def log(msg: str) -> None:
    print(f"[mockup] {msg}", flush=True)


def pump(ms: int) -> None:
    import time
    from PyQt6.QtCore import QEvent
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.02)


def build_app():
    app = QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))
    return app


def save(widget, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pump(250)
    pix = widget.grab()
    path = OUT / f"{name}.png"
    pix.save(str(path))
    log(f"saved {path.name}  ({pix.width()}x{pix.height()})")


# ---------------------------------------------------------------------------
# The proposed state, applied to live widgets
# ---------------------------------------------------------------------------
CAL = "calibration"          # the proposed RUN_TYPE_CALIBRATION value

RUN_TYPE_TIP = (
    "Are you building the printer profile itself, checking a finished one, or "
    "calibrating the printer first?\n\n"
    "• Profiling — measure a chart printed with colour management OFF, so "
    "ChromIQ can learn your printer and build a profile from it. This is the "
    "normal choice.\n\n"
    "• Verification — measure a (usually smaller) chart printed THROUGH a "
    "finished profile, with colour management ON, to check how accurate that "
    "profile still is.\n\n"
    "• Calibration — measure a special chart that brings the printer itself to "
    "a known, repeatable state before any profile is built. It produces a "
    "calibration file (.cal) which every profile run of this project can then "
    "use. One calibration is shared by the whole project, so there is nothing "
    "to choose under “Profile run” while this is selected. This step is "
    "optional; use it when you want your printer to behave the same way today "
    "and in six months.")

PROFILE_RUN_TIP = (
    "A calibration describes your printer, your paper and your inks — not one "
    "particular profile — so a project keeps exactly one, in its “cal” folder, "
    "and every profile run can use it. There is no run to pick here.")


def bar_as_calibration(win) -> None:
    """Run type = Calibration: the third value, the fixed Profile run, no
    Verification box."""
    bar = win._target_bar
    combo = bar._type_combo
    if combo.findData(CAL) < 0:
        combo.addItem("Calibration", CAL)
    combo.setToolTip(RUN_TYPE_TIP)
    combo.blockSignals(True)
    combo.setCurrentIndex(combo.findData(CAL))
    combo.blockSignals(False)

    run = bar._run_combo
    run.blockSignals(True)
    run.clear()
    run.addItem("Project calibration", "cal")
    run.setCurrentIndex(0)
    run.blockSignals(False)
    run.setEnabled(False)
    run.setToolTip(PROFILE_RUN_TIP)
    # "Project calibration" is longer than "Run 8 (overwrite)", which is what
    # the box's floor was sized for — without this it clips to "Project
    # calibratior". Uses the bar's own fitter, the one every other box uses.
    bar._fit_box(run, ["Project calibration"])
    bar._fit_box(combo, [combo.itemText(i) for i in range(combo.count())])

    bar._verify_label.setVisible(False)
    bar._verify_combo.setVisible(False)
    # Duplicate and Delete are about runs; they say which Run type they need.
    for btn, why in ((bar._duplicate_btn,
                      "Duplicating works on a profile run. Switch “Run type” to "
                      "“Profiling” to duplicate a run."),
                     (bar._delete_btn,
                      "There is one calibration per project, and it is replaced "
                      "rather than deleted — making a new calibration chart "
                      "moves the old one to “cal/old”.")):
        btn.setEnabled(False)
        btn.setToolTip(why)
    bar._restore_btn.setEnabled(False)
    bar._restore_btn.setToolTip(
        "A calibration chart keeps no stored copy yet, so there is nothing to "
        "put back. Switch “Run type” to “Profiling” or “Verification” to use "
        "this.")


def bar_as_profiling(win) -> None:
    """Today's bar, for comparison — Profiling, unchanged."""
    bar = win._target_bar
    bar.refresh()
    pump(100)


def chart_tab_as_calibration(win) -> None:
    """Create Chart with a Calibration target: the checkbox is gone, the
    calibration knobs are set by the run type instead."""
    tab = win._tab_chart
    tab._switch_mode("manual")
    win._tabs.setCurrentIndex(0)
    pump(200)
    # The checkbox the run type replaces.
    tab._cal_target_grp.setVisible(False)
    # …but its knob preset still applies: this is what ticking it did.
    tab._on_cal_target_toggled(True)
    # EVERY "Auto" GOES OFF, AND SINGLE CHANNEL STEPS GOES TO 20.
    #
    # Sebastian, 2026-08-05: *"setting run type to calibration turns the auto
    # settings off … total patch count, white, black patches, grey axis steps.
    # Single channel steps should be set to 20 on a calibration run by default
    # … and then also be reset to how it was before when the user sets another
    # runtype again."*
    #
    # This is the half the checkbox never did: it wrote -f 0 into a spinbox
    # that "Auto" owns and had disabled, so the 0 was cosmetic and the
    # page-filling estimate overrode it at Generate (D7). A calibration chart's
    # size comes from the ramp, not from how many pages you want to fill, so
    # the Auto boxes are unticked AND disabled — visibly not in charge — and
    # the Pages control goes with them.
    tab._on_auto_patches_toggled(False)
    for cb in (tab._manual_auto_patches_check, tab._manual_auto_white_check,
               tab._manual_auto_black_check, tab._manual_auto_grey_check):
        if cb is not None:
            cb.setChecked(False)
            cb.setEnabled(False)
    for which in ("white", "black", "grey"):
        tab._on_auto_neutral_toggled(which, False)
    if tab._manual_pages_spin is not None:
        tab._manual_pages_spin.setEnabled(False)
    if getattr(tab, "_manual_pages_lbl", None) is not None:
        tab._manual_pages_lbl.setEnabled(False)
    # AND THE TARGEN SECTION OPENS. Sebastian, 2026-08-04: *"When run type is
    # set to calibration then the targen settings in create chart should not be
    # collapsed so the user directly sees where to dial in the desired
    # settings."* It starts collapsed because most charts never touch the patch
    # recipe — but a calibration chart is nothing BUT the patch recipe: the
    # single-channel steps are the setting that decides the calibration.
    if getattr(tab, "_manual_targen_grp", None) is not None:
        tab._manual_targen_grp.set_collapsed(False)
    pump(300)
    # …and the rows that decide the calibration are scrolled into view. Opening
    # the section is not enough on its own: "Single Channel Steps" — the ramp
    # this chart is — sits below the fold, which is the part of his point that
    # only shows up in a picture.
    #
    # Frame the WHOLE block, -f through -s: Total Patch Count, White Patches,
    # Black Patches and Grey Axis Steps are the four "Auto" boxes the run type
    # switches off, so a picture that crops any of them does not show the
    # change. Scroll to the last row first, then back to the first — the second
    # call wins, and lands the block at the top of the viewport.
    from PyQt6.QtWidgets import QAbstractScrollArea

    def _reveal(flag: str, y_margin: int) -> None:
        for pw in tab._manual_widgets.get("targen", []):
            if pw.flag == flag:
                node = pw.parentWidget()
                while node is not None and not isinstance(node, QAbstractScrollArea):
                    node = node.parentWidget()
                if node is not None:
                    node.ensureWidgetVisible(pw, 60, y_margin)
                return

    _reveal("-s", 140)
    pump(120)
    _reveal("-f", 40)
    for f in (getattr(tab, "_manual_target_name_edit", None),
              getattr(tab, "_target_name_edit", None)):
        if f is not None:
            f.setText(PROJECT.name)
    pump(300)


def chart_tab_prefill(win):
    """The .cal prefill that already works today, shown in a Profiling target:
    printtarg -K and -I carry the path, and the status line says so.

    Returned as a composite of the three real widgets, because the two
    parameter rows live far down the scrolling panel and the status line sits
    at the top of it — a single grab would show one or the other.
    """
    from PyQt6.QtGui import QPainter, QPixmap

    tab = win._tab_chart
    tab._switch_mode("manual")
    win._tabs.setCurrentIndex(0)
    tab._cal_target_grp.setVisible(True)
    tab._cal_target_check.setVisible(False)      # the retired control
    cal = f"{PROJECT_SHOWN}/cal/{PROJECT.name}-cal.cal"
    for pw in (tab._manual_cal_k_pw, tab._manual_cal_i_pw):
        if pw is not None:
            pw.set_value(cal)
    # The app's CURRENT wording, verbatim (ui/tabs/tab_chart.py:3566-3569) —
    # this shot documents today's behaviour, so it must not carry draft text.
    tab._cal_status_lbl.setText(
        f"Calibration file found: {PROJECT.name}-cal.cal — auto-filled into "
        "-I and -K fields below.")
    tab._cal_status_lbl.setVisible(True)
    pump(300)

    # The two rows live inside collapsible sections in a scrolling panel:
    # expand every ancestor and scroll them into view, then grab the panel's
    # own viewport — a real, contiguous piece of the app, not a paste-up.
    from ui.widgets import CollapsibleGroupBox
    from PyQt6.QtWidgets import QAbstractScrollArea

    rows = [w for w in (tab._manual_cal_k_pw, tab._manual_cal_i_pw)
            if w is not None]
    viewport = None
    for pw in rows:
        node = pw
        while node is not None:
            if isinstance(node, CollapsibleGroupBox) and node.is_collapsed():
                node.set_collapsed(False)
            if isinstance(node, QAbstractScrollArea) and viewport is None:
                viewport = node
            node = node.parentWidget()
        pw.setVisible(True)
    pump(400)
    if viewport is not None and rows:
        viewport.ensureWidgetVisible(rows[0], 60, 120)
        pump(400)

    parts = [tab._cal_status_lbl.grab()]
    if viewport is not None:
        # The rows are at the top of the scrolled panel after
        # ensureWidgetVisible; take that band rather than the whole viewport,
        # which is mostly empty below them.
        shot = viewport.viewport().grab()
        band = min(shot.height(), 250)
        parts.append(shot.copy(0, 0, shot.width(), band))
    else:
        parts += [pw.grab() for pw in rows]

    pad = 14
    width = max(p.width() for p in parts) + pad * 2
    height = sum(p.height() for p in parts) + pad * (len(parts) + 1)
    canvas = QPixmap(width, height)
    canvas.fill(win.palette().window().color())
    painter = QPainter(canvas)
    y = pad
    for p in parts:
        painter.drawPixmap(pad, y, p)
        y += p.height() + pad
    painter.end()
    return canvas


def profile_tab(win, *, target: str) -> None:
    """Tab 4's modules for a target: Calibration shows only CREATE CALIBRATION
    FILE; Profiling shows BUILD PROFILE and APPLY CALIBRATION."""
    p = win._tab_profile
    win._settings.set("calibration_mode", True)
    win._apply_calibration_mode()
    win._tabs.setCurrentIndex(3)
    pump(200)
    if target == CAL:
        p._cal_create_btn.setVisible(True)
        p._cal_profile_btn.setVisible(False)
        p._cal_apply_btn.setVisible(False)
        p._switch_cal_mode(1)                    # printcal
        p._header.set_texts("STEP 04 · CREATE CALIBRATION FILE",
                            "Calibration")
        # The in-section loader goes, as it already has everywhere else.
        # Sebastian, 2026-08-04: *"in the screenshot that show the create
        # calibration file module there is still the loading button / icon in
        # the measurement data section. Is this still needed here as we moved
        # the button out of this section for all other tabs…?"* It is not: the
        # header's loader is the one button, and Build Profile's own frame is
        # already just a label (tab_profile.py:451-458).
        if getattr(p, "_pc_load_btn", None) is not None:
            p._pc_load_btn.setVisible(False)
    else:
        p._cal_create_btn.setVisible(False)
        p._cal_profile_btn.setVisible(True)
        p._cal_apply_btn.setVisible(True)
        p._switch_cal_mode(0)                    # colprof
    pump(300)


def replace_warning(win):
    """The data-safety window this design will not ship without — the real
    QMessageBox the §4 windows use, with the draft text."""
    from PyQt6.QtWidgets import QMessageBox
    from ui.widgets import fit_message_box_buttons

    title = "This project already holds a calibration"
    body = (
        "Making a new calibration chart replaces the one this project has. "
        "What is here now moves to “cal/old/2026-08-04_061500”, and nothing is "
        "deleted:\n"
        "•  the calibration chart and its printed pages\n"
        "•  the calibration measurement of 84 patches\n"
        "•  the calibration curves themselves "
        "(Canon-Pro300-CanonSG-i1Pro-cal.cal)\n\n"
        "What this costs you if you go ahead: “Re-calibrate” and “Verify” in "
        "the Create Calibration File module both read the calibration you "
        "already have and compare the new readings against it. With it moved "
        "aside, the only mode left is “Initial” — a fresh start, with nothing "
        "to compare against.\n\n"
        "Your profile runs are not touched. Any profile already built with "
        "this calibration keeps working exactly as it does now.\n\n"
        "The “old” folder is here:\n"
        f"{PROJECT_SHOWN}/cal/old")
    box = QMessageBox(win)
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    go = box.addButton("Generate the new chart",
                       QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(go)
    fit_message_box_buttons(box)
    box.show()
    pump(500)
    save(box, "05-replace-warning")
    box.close()


def main() -> int:
    theme = sys.argv[1] if len(sys.argv) > 1 else "dark"
    app = build_app()
    settings = AppSettings()
    settings.set("show_welcome_dialog", False)
    settings.set("calibration_mode", True)
    apply_appearance(app, None, theme)
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(1200)
    apply_appearance(app, win, theme)
    pump(400)

    if PROJECT.exists():
        try:
            win._file_mgr.set_target_name(PROJECT.name)
            win._target_bar.refresh()
        except Exception as exc:                    # noqa: BLE001
            log(f"project seed skipped: {exc}")
    pump(400)

    bar = win._target_bar

    bar_as_profiling(win)
    save(bar, "01-bar-today-profiling")

    bar_as_calibration(win)
    save(bar, "02-bar-proposed-calibration")

    chart_tab_as_calibration(win)
    # Switching tabs refreshes the bar from the real target, so the proposed
    # state is re-applied last, immediately before the grab.
    bar_as_calibration(win)
    win._tab_chart._preview.set_notice(
        "No calibration chart in this project yet.\n\n"
        "Choose your options above and press “Generate Chart” to make one. It "
        "is saved in this project's “cal” folder and shared by every profile "
        "run, so you only make it once — until you want to calibrate the "
        "printer again.")
    save(win, "03-create-chart-calibration")

    profile_tab(win, target=CAL)
    save(win._tab_profile, "06-tab4-calibration-run")

    profile_tab(win, target="profiling")
    save(win._tab_profile, "07-tab4-profiling-run")

    bar_as_profiling(win)
    composite = chart_tab_prefill(win)
    OUT.mkdir(parents=True, exist_ok=True)
    composite.save(str(OUT / "04-create-chart-prefill.png"))
    log(f"saved 04-create-chart-prefill.png  "
        f"({composite.width()}x{composite.height()})")

    replace_warning(win)

    log("done")
    win.close()
    app.quit()
    return 0


if __name__ == "__main__":
    import os
    os._exit(main())        # WebEngine teardown, as main.py does
