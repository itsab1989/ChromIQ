"""Tools → "Create scanner target" — write a chart's ``.cht`` + ``.cie`` from a
measurement, so the printed chart can be read off a flatbed scan (#97).

Pick a **measured** chart (its ``.ti3``); ChromIQ pairs it with the chart's exact
engine geometry and writes two files next to the chart:

* ``<chart>.cht`` — where every patch sits (per page, with fiducial corners),
* ``<chart>.cie`` — what every patch truly measured.

``scanin`` uses that pair to turn a scan of the printed chart into a measurement,
which ``colprof`` builds into a **scanner** profile. Pure file generation — no
Argyll binary is called here.

This is the standalone fallback; the primary entry point is an opt-in checkbox
after measuring. Both need an **engine** chart (exact geometry) plus a
measurement. Follows the shared Tools chrome (:class:`_ToolDialogBase`): green
masthead (the measure/scanner family), a ⓘ per option, ChromIQ's non-native
pickers.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from ui.dialogs.tools_dialogs import (
    _ToolDialogBase,
    _initial_dir,
    _remember_dir,
    neutral_controls_qss,
)
from ui.styles import SPEC_GREEN
from ui.theme import resolve_mode
from ui.tooltip_button import TooltipButton
from ui.widgets import make_browse_button, open_file_dialog, open_files_dialog
from workflow.scanin_target import (
    ScaninTargetError,
    build_scanin_target_from_paths,
    build_scanin_target_from_render,
    has_scanner_geometry,
)

log = get_logger(__name__)

_TI3_FILTER = "Measurements (*.ti3);;All files (*)"
_PATCHSET_FILTER = ("Patch sets (*.ti1 *.txt *.pxf);;TI1 (*.ti1);;"
                    "i1Profiler CGATS (*.txt);;i1Profiler CxF (*.pxf);;All files (*)")
_TIFF_FILTER = "Chart pages (*.tif *.tiff);;All files (*)"
# The i1Profiler-mode measurement may be a ready .ti3, or an i1Profiler
# measurement — its native saved file (.mxf) or a .txt / .cxf export — which
# ChromIQ converts on the spot (no export step needed).
_MEAS_FILTER = ("Measurements (*.ti3 *.mxf *.txt *.cxf);;TI3 (*.ti3);;"
                "i1Profiler measurement (*.mxf *.txt *.cxf);;All files (*)")


def _chart_base(ti3: Path) -> Path:
    """The chart's stem path for a chosen ``.ti3`` — strips a ``-verify`` suffix
    so a colour-managed verification read still resolves to ``<chart>``."""
    stem = ti3.stem
    if stem.endswith("-verify"):
        stem = stem[: -len("-verify")]
    return ti3.with_name(stem)


# Shared "which chart should I use?" guidance, appended to both scanner tool
# dialogs' ⓘ help. Defined once so the two dialogs share a single catalog key.
WHICH_CHART_HELP = tr(
    "Which chart makes the best scanner profile?\n\n"
    "The reference colours always come from your spectrophotometer "
    "measurement, so the profile is correct as long as you scan the very sheet "
    "you measured. The choice is only about how well the target matches what "
    "you'll actually scan:\n\n"
    "• Reuse the chart you already measured (no reprint) — free, correct, and "
    "ideal for general use and most photographers. Printed without colour "
    "management, it actually spans your printer's full gamut.\n\n"
    "• Print a fresh chart through your normal colour-managed workflow — the "
    "same paper and settings you use for real prints — then measure THAT sheet "
    "and scan it. This is best when you mainly scan your own colour-managed "
    "prints, because the target then matches the exact colours and rendering "
    "you produce. You must measure the reprint: you can't reuse the earlier "
    "measurement for a different sheet.\n\n"
    "Whichever you choose, match the paper and finish (glossy vs. matte) to "
    "what you'll scan.")


# Camera counterpart to the "which chart" guidance above — the core idea is the
# same, but a camera cares about light, not paper. Kept as its own key so the
# shared block above stays stable.
WHICH_CHART_CAMERA_NOTE = tr(
    "Does this apply to a camera?\n\n"
    "The main idea is the same: the reference colours come from your "
    "measurement, so any chart you measure and then photograph is correct. But "
    "a camera profile depends far more on the light than on the paper, so a few "
    "things change:\n\n"
    "• A printed chart suits flat, copy-style work — artwork, documents, "
    "repro — photographed under even, controlled light. The profile then "
    "describes your camera under that light.\n\n"
    "• Match the light, not the finish. For a scanner you match the paper you'll "
    "scan; for a camera, light the chart evenly with the light you'll actually "
    "shoot under, because the profile is tied to that light.\n\n"
    "• For general photography, a ready-made camera target (such as an X-Rite "
    "ColorChecker) is usually easier — load it under 'A standard target I own' "
    "in Build profile with scanner or camera, and see that window's 'Profiling a "
    "camera' section for how to shoot it.")


class ScaninTargetDialog(_ToolDialogBase):
    TOOL_KEY    = "scanner_target"
    TITLE       = tr("Create scanner or camera target")
    EYEBROW     = tr("MEASURE · SCANNER / CAMERA TARGET")
    ACCENT      = SPEC_GREEN
    RUN_LABEL   = tr("Create the files")
    MIN_WIDTH   = 640
    # The i1Profiler mode adds three pickers + help, so the rows scroll and the
    # log/buttons stay pinned when the window is short.
    SCROLLABLE_CONTENT = True

    HELP = tr(
        "Builds two small files from a chart you've already measured, so you can "
        "later profile a scanner — or a camera — from that same chart, with no "
        "need to print or measure anything again.\n\n"
        "• <chart>.cht — where each patch sits on the page.\n"
        "• <chart>.cie — the real colours the spectrophotometer measured.\n\n"
        "Pick the chart's measurement (its .ti3); the two files are saved next to "
        "the chart. Then capture the printed chart on the device you want to "
        "profile — scan it on a scanner, or photograph it with a camera — and use "
        "'Build profile with scanner or camera'. ArgyllCMS's scanin reads your capture "
        "against these files, and colprof turns that into the device's ICC "
        "profile. The same two files work for both: scan the chart to profile a "
        "scanner, or photograph it to profile a camera.\n\n"
        "Works for charts created with ChromIQ's layout engine, which knows each "
        "patch's exact position. (Support for older or imported charts is planned.)"
    ) + "\n\n───────────────\n" + WHICH_CHART_HELP \
      + "\n\n───────────────\n" + WHICH_CHART_CAMERA_NOTE
    DESCRIPTION = tr(
        "Turn a measured chart into recognition files (.cht + .cie) so you can "
        "profile a scanner or a camera from the same chart.")

    # Beginner-first walkthrough of the i1Profiler route, shown under that mode.
    I1PROFILER_HELP = tr(
        "Using a chart you laid out in i1Profiler\n\n"
        "Some instruments — an i1iSis, or a robot-arm like the i1iO — are driven "
        "by X-Rite's i1Profiler, not by ChromIQ. You can still turn such a chart "
        "into a scanner or camera target. Here's the idea, step by step:\n\n"
        "1. In ChromIQ, export your patches for i1Profiler (Tools → Export for "
        "i1Profiler) and load them into i1Profiler.\n"
        "2. Let i1Profiler lay the chart out, and save it as a TIFF (its 'Save "
        "as…' button under the chart). A chart that runs onto several pages "
        "saves as several TIFF files — keep them all.\n"
        "3. Print that chart and measure it with your instrument in i1Profiler, "
        "and keep the measurement file it exports — you can hand that straight to "
        "ChromIQ below (it converts it for you), or convert it yourself first "
        "with Tools → Convert i1Profiler → TI3.\n"
        "4. Come back here, pick those three things below, and ChromIQ works out "
        "where every patch sits by reading the saved chart — then writes the "
        "same .cht + .cie recognition files.\n\n"
        "Why the saved chart is needed: i1Profiler always arranges the patches "
        "its own way, so ChromIQ can't know the layout in advance. Reading it "
        "back from the chart i1Profiler saved is what makes this exact and "
        "reliable — ChromIQ checks every patch's colour and refuses rather than "
        "guess if anything doesn't line up.")

    def __init__(self, settings, parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._mode = "chromiq"           # "chromiq" | "i1profiler"
        self._ti3_path: Path | None = None
        # i1Profiler-mode inputs.
        self._pset_path: Path | None = None
        self._tiff_paths: list[Path] = []
        self._meas_path: Path | None = None
        # Readable secondary-text colour (palette(mid) is too faint on the dialog
        # background in both themes).
        light = resolve_mode(settings.get("appearance", "auto")) == "light"
        self._hint_color = "#4a4a4a" if light else "#b8b8b8"
        self._build_inputs()
        self._run_btn.setObjectName("primary")
        self.setStyleSheet(self.styleSheet() + neutral_controls_qss(SPEC_GREEN))
        self._style_primary_button()
        self._refresh()

    # ------------------------------------------------------------------ style
    def _style_primary_button(self) -> None:
        light = resolve_mode(self._settings.get("appearance", "auto")) == "light"
        c = SPEC_GREEN
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        hover = "#{:02x}{:02x}{:02x}".format(int(r * 0.86), int(g * 0.86), int(b * 0.86))
        dis_bg = "#e8e6e1" if light else "#1e1e1e"
        dis_fg = "#a8a4a0" if light else "#484848"
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background: {c}; border: 1px solid {c}; color: #0a0a0a;"
            f" font-weight: 700; }}"
            f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
            f"QPushButton:disabled {{ background: {dis_bg}; border: 1px solid {c};"
            f" color: {dis_fg}; }}")

    # ------------------------------------------------------------------ UI
    def _tip(self, title: str, body: str) -> TooltipButton:
        return TooltipButton(title, body, self, min_width=500, color=SPEC_GREEN)

    def _pick_row(self, field: QLineEdit, handler, icon: str = "folder_measure"):
        """A read-only path field + Browse button row."""
        row = QHBoxLayout()
        field.setReadOnly(True)
        row.addWidget(field, 1)
        browse = make_browse_button(self, tr("Browse…"), icon=icon)
        browse.clicked.connect(handler)
        row.addWidget(browse)
        return row

    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {self._hint_color}; font-size: 12px;")
        return lbl

    def _build_inputs(self) -> None:
        form = self._content

        # ---- mode switch: where was the chart laid out? --------------------
        mode_head = QHBoxLayout()
        mode_head.addWidget(QLabel(tr("Where did you lay out this chart?"), self))
        mode_head.addStretch(1)
        mode_head.addWidget(self._tip(
            tr("Where the chart was laid out"),
            tr("Pick 'In ChromIQ' for any chart you created here — ChromIQ "
            "already knows exactly where each patch sits, so it only needs the "
            "measurement.\n\nPick 'In i1Profiler' if X-Rite's i1Profiler arranged "
            "the chart (for example to drive an i1iSis or an i1iO robot arm). "
            "ChromIQ then reads the layout back from the chart image i1Profiler "
            "saved, so it needs a little more from you.")),
            0, Qt.AlignmentFlag.AlignVCenter)
        form.addLayout(mode_head)

        self._mode_group = QButtonGroup(self)
        self._rb_chromiq = QRadioButton(tr("In ChromIQ"), self)
        self._rb_i1p = QRadioButton(tr("In i1Profiler"), self)
        self._rb_chromiq.setChecked(True)
        radios = QHBoxLayout()
        for rb in (self._rb_chromiq, self._rb_i1p):
            self._mode_group.addButton(rb)
            radios.addWidget(rb)
        radios.addStretch(1)
        form.addLayout(radios)
        self._rb_chromiq.toggled.connect(self._on_mode_changed)

        # ---- panel A: a chart made in ChromIQ ------------------------------
        self._panel_chromiq = QWidget(self)
        pa = QVBoxLayout(self._panel_chromiq)
        pa.setContentsMargins(0, 4, 0, 0)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("Measured chart (.ti3):"), self))
        head.addStretch(1)
        head.addWidget(self._tip(
            tr("Measured chart"),
            tr("The measurement of the chart you want to scan later — its .ti3 "
            "file, produced when you measured the chart. ChromIQ pairs it with "
            "the chart's exact layout to write the scanner files. Pick the "
            "chart's own measurement; a colour-managed verification read works "
            "too.")), 0, Qt.AlignmentFlag.AlignVCenter)
        pa.addLayout(head)
        self._ti3_field = QLineEdit(self)
        self._ti3_field.setPlaceholderText(tr("Pick the chart's measurement (.ti3)…"))
        pa.addLayout(self._pick_row(self._ti3_field, self._pick_ti3))
        self._note = self._hint("")
        pa.addWidget(self._note)
        pa.addWidget(self._hint(tr(
            "The recognition files (.cht + .cie) are saved next to your chart, "
            "and work for profiling either a scanner or a camera from it. "
            "Multi-page charts get one .cht per page and a single .cie.")))
        form.addWidget(self._panel_chromiq)

        # ---- panel B: a chart laid out in i1Profiler -----------------------
        self._panel_i1p = QWidget(self)
        pb = QVBoxLayout(self._panel_i1p)
        pb.setContentsMargins(0, 4, 0, 0)
        # Short inline intro; the full step-by-step lives behind the ⓘ so it
        # doesn't crowd the pickers on a short window.
        intro = QHBoxLayout()
        intro.addWidget(self._hint(tr(
            "For a chart i1Profiler arranged — e.g. to drive an i1iSis or i1iO. "
            "Pick the three things below and ChromIQ reads the layout off the "
            "saved chart. New to this? Open the ⓘ for the full walkthrough.")), 1)
        intro.addWidget(self._tip(tr("How this works, step by step"),
                                  self.I1PROFILER_HELP),
                        0, Qt.AlignmentFlag.AlignTop)
        pb.addLayout(intro)

        ph = QHBoxLayout()
        ph.addWidget(QLabel(tr("1. Your patch set (.ti1, .txt or .pxf):"), self))
        ph.addStretch(1)
        ph.addWidget(self._tip(
            tr("Your patch set"),
            tr("The very file you loaded into i1Profiler — the patch set you "
            "exported from ChromIQ (Tools → Export for i1Profiler). It tells "
            "ChromIQ each patch's colour and the order i1Profiler placed them "
            "in, so it can find them on the saved chart. A .ti1, .txt or .pxf "
            "all work.")), 0, Qt.AlignmentFlag.AlignVCenter)
        pb.addLayout(ph)
        self._pset_field = QLineEdit(self)
        self._pset_field.setPlaceholderText(tr("Pick the patch set you loaded into i1Profiler…"))
        pb.addLayout(self._pick_row(self._pset_field, self._pick_pset))

        th = QHBoxLayout()
        th.addWidget(QLabel(tr("2. The chart i1Profiler saved (.tif):"), self))
        th.addStretch(1)
        th.addWidget(self._tip(
            tr("The saved chart"),
            tr("The chart image i1Profiler saved with its 'Save as…' button. "
            "ChromIQ reads the exact layout off it. If the chart ran onto "
            "several pages, i1Profiler saves one TIFF per page — pick them all "
            "at once, in page order (they're usually named …_1_2, …_2_2 and so "
            "on).")), 0, Qt.AlignmentFlag.AlignVCenter)
        pb.addLayout(th)
        self._tiff_field = QLineEdit(self)
        self._tiff_field.setPlaceholderText(tr("Pick the saved chart pages…"))
        pb.addLayout(self._pick_row(self._tiff_field, self._pick_tiffs))

        mh = QHBoxLayout()
        mh.addWidget(QLabel(tr("3. Your measurement (.ti3):"), self))
        mh.addStretch(1)
        mh.addWidget(self._tip(
            tr("Your measurement"),
            tr("The measurement of the printed chart. You can pick an i1Profiler "
            "measurement straight from i1Profiler — its own saved file (.mxf, no "
            "export step needed) or a .txt / .cxf export — and ChromIQ converts "
            "it for you, or pick a .ti3 you converted earlier. This is where the "
            "true colours come from. ChromIQ matches it to the chart by patch "
            "number, so use the measurement of this very chart.")),
            0, Qt.AlignmentFlag.AlignVCenter)
        pb.addLayout(mh)
        self._meas_field = QLineEdit(self)
        self._meas_field.setPlaceholderText(tr("Pick i1Profiler's measurement (.mxf / .txt / .cxf) or a .ti3…"))
        pb.addLayout(self._pick_row(self._meas_field, self._pick_meas))

        self._i1p_note = self._hint("")
        pb.addWidget(self._i1p_note)
        self._panel_i1p.setVisible(False)
        form.addWidget(self._panel_i1p)

    # ------------------------------------------------------------------ pick
    def _pick_ti3(self) -> None:
        path = open_file_dialog(
            self, tr("Choose the chart's measurement"), _TI3_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
            declutter_settings=self._settings)
        if not path:
            return
        if self._reject_if_hexagonal(_chart_base(Path(path))):
            return
        self._ti3_path = Path(path)
        self._ti3_field.setText(path)
        _remember_dir(self._settings, self.TOOL_KEY, self._ti3_path.parent)
        self._refresh_note()
        self._refresh()

    def _reject_if_hexagonal(self, chart_base: Path) -> bool:
        """Turn a hexagonal chart away unless the user has opted in.

        The old refusal said the CHT format made this impossible. It does not:
        a CHT describes the rectangle SAMPLED inside each patch, taken from the
        chart's own recorded geometry, and a hexagonal chart has been read and
        profiled end to end. What is unsolved is scanin's chart FINDER, which
        looks for long straight edges to measure rotation and can abort on a
        honeycomb even with the four corners given — plus the sampling square,
        which escapes the hexagon above a Sample area of about 64 %.

        So the default stays exactly as it has always been, and Preferences →
        Beta opens it for anyone who wants to try. Returns True if rejected.
        """
        from workflow.hex_support import (chart_is_hexagonal,
                                          hex_scanner_allowed,
                                          hex_scanner_message)
        if not chart_is_hexagonal(chart_base):
            return False
        if hex_scanner_allowed(getattr(self, "_settings", None)):
            return False
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, tr("Hexagonal chart"), hex_scanner_message())
        return True

    def _pick_pset(self) -> None:
        path = open_file_dialog(
            self, tr("Choose the patch set you loaded into i1Profiler"),
            _PATCHSET_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)))
        if not path:
            return
        self._pset_path = Path(path)
        self._pset_field.setText(path)
        _remember_dir(self._settings, self.TOOL_KEY, self._pset_path.parent)
        self._refresh_i1p_note()
        self._refresh()

    def _pick_tiffs(self) -> None:
        paths = open_files_dialog(
            self, tr("Choose the chart pages i1Profiler saved"), _TIFF_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
            preview=True,
            declutter_settings=self._settings)
        if not paths:
            return
        # Page order matters; i1Profiler's …_1_2 / …_2_2 names sort correctly.
        self._tiff_paths = [Path(p) for p in sorted(paths)]
        self._tiff_field.setText(", ".join(p.name for p in self._tiff_paths))
        _remember_dir(self._settings, self.TOOL_KEY, self._tiff_paths[0].parent)
        self._refresh_i1p_note()
        self._refresh()

    def _pick_meas(self) -> None:
        path = open_file_dialog(
            self, tr("Choose your measurement"), _MEAS_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
            declutter_settings=self._settings)
        if not path:
            return
        if self._reject_if_hexagonal(_chart_base(Path(path))):
            return
        self._meas_path = Path(path)
        self._meas_field.setText(path)
        _remember_dir(self._settings, self.TOOL_KEY, self._meas_path.parent)
        self._refresh_i1p_note()
        self._refresh()

    # ------------------------------------------------------------------ mode
    def _on_mode_changed(self, _checked: bool = False) -> None:
        self._mode = "chromiq" if self._rb_chromiq.isChecked() else "i1profiler"
        self._panel_chromiq.setVisible(self._mode == "chromiq")
        self._panel_i1p.setVisible(self._mode == "i1profiler")
        self._refresh()

    def _refresh_note(self) -> None:
        if self._ti3_path is None:
            self._note.setText("")
            return
        base = _chart_base(self._ti3_path)
        channels = base.with_name(base.name + ".channels.json")
        if has_scanner_geometry(channels):
            self._note.setText(tr(
                "✓ Ready — recognition files will be written as {stem}.cht / .cie."
            ).format(stem=base.name))
        else:
            self._note.setText(tr(
                "⚠ ChromIQ doesn't have this chart's patch positions. Recreate the "
                "chart in a current ChromIQ version to enable recognition files."))

    def _refresh_i1p_note(self) -> None:
        have = sum(x is not None and x != [] for x in
                   (self._pset_path, self._tiff_paths or None, self._meas_path))
        if have < 3:
            self._i1p_note.setText(tr(
                "Pick all three above. ChromIQ then reads the layout from the "
                "saved chart and writes the recognition files next to your "
                "measurement."))
            return
        base = _chart_base(self._meas_path)
        self._i1p_note.setText(tr(
            "✓ Ready — recognition files will be written as {stem}.cht / .cie "
            "next to your measurement."
        ).format(stem=base.name))

    # ------------------------------------------------------------------ run
    def _can_run(self) -> bool:
        if self._mode == "chromiq":
            return self._ti3_path is not None
        return (self._pset_path is not None and bool(self._tiff_paths)
                and self._meas_path is not None)

    def _execute(self) -> None:
        self._log.clear()
        if self._mode == "chromiq":
            self._execute_chromiq()
        else:
            self._execute_i1profiler()

    def _report(self, res) -> None:
        for p in res.cht_paths:
            self._log.appendPlainText(tr("[OK] Wrote {path}").format(path=p))
        self._log.appendPlainText(tr("[OK] Wrote {path}").format(path=res.cie_path))
        self._log.appendPlainText((
            tr("Recognition files for {n} patches on one page saved next to your "
               "chart. Scan or photograph the printed chart, then use 'Build "
               "profile with scanner or camera'.")
            if res.n_pages == 1 else
            tr("Recognition files for {n} patches on {pages} pages saved next to "
               "your chart. Scan or photograph the printed chart, then use 'Build "
               "profile with scanner or camera'.")
        ).format(n=res.n_patches, pages=res.n_pages))

    def _execute_chromiq(self) -> None:
        assert self._ti3_path is not None
        base = _chart_base(self._ti3_path)
        channels = base.with_name(base.name + ".channels.json")
        try:
            res = build_scanin_target_from_paths(channels, self._ti3_path, base)
        except ScaninTargetError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return
        self._report(res)
        _remember_dir(self._settings, self.TOOL_KEY, self._ti3_path.parent)
        self._finish(True)

    def _execute_i1profiler(self) -> None:
        assert self._pset_path and self._tiff_paths and self._meas_path
        base = _chart_base(self._meas_path)
        # Accept i1Profiler's raw measurement export (.txt) too — convert it
        # with txt2ti3 here so the user needn't run Convert i1Profiler → TI3 first.
        from workflow.reference_convert import (
            ReferenceConvertError, convert_i1profiler_measurement, is_ti3,
        )
        ti3 = self._meas_path
        if not is_ti3(ti3):
            self._log.appendPlainText(tr(
                "Converting i1Profiler's measurement to a .ti3…"))
            try:
                ti3 = convert_i1profiler_measurement(
                    self._meas_path, self._settings.get("argyll_bin_path", ""),
                    self._meas_path.parent)
            except ReferenceConvertError as exc:
                self._log.appendPlainText(f"[ERROR] {exc}")
                self._finish(False)
                return
            base = _chart_base(ti3)

        self._log.appendPlainText(tr("Reading the layout from the saved chart…"))
        try:
            res = build_scanin_target_from_render(
                self._pset_path, self._tiff_paths, ti3, base)
        except ScaninTargetError as exc:
            self._log.appendPlainText(f"[ERROR] {exc}")
            self._finish(False)
            return
        self._report(res)
        _remember_dir(self._settings, self.TOOL_KEY, self._meas_path.parent)
        self._finish(True)
