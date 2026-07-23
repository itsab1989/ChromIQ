"""Main application window."""
from __future__ import annotations

import colorsys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QMainWindow,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.argyll_detect import all_tools_present, find_argyll_bin_path
from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.logger import get_logger
from core.settings import AppSettings
from core.updater import UpdateChecker
from ui.dialogs.settings_dialog import SettingsDialog
from ui.gradient_overlay import GradientOverlay
from ui.masthead_header import MastheadHeader
from ui.spectrum_tab_bar import SpectrumTabBar
from ui.tabs.tab_chart import TabChart
from ui.tabs.tab_check_refine import TabCheckRefine
from ui.tabs.tab_measure import TabMeasure
from ui.tabs.tab_print import TabPrint
from ui.tabs.tab_profile import TabProfile
from core.i18n import tr

log = get_logger(__name__)


def _darken_for_light_log(hex_color: str) -> str:
    """Return a tab accent darkened for readable log text on the light-mode
    log background. Preserves hue, reduces lightness, and tames very
    saturated inputs so they don't read as a deep indigo / scarlet after
    crushing."""
    r = int(hex_color[1:3], 16) / 255
    g = int(hex_color[3:5], 16) / 255
    b = int(hex_color[5:7], 16) / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.22, l * 0.55)
    if s > 0.85:
        s = 0.70
    else:
        s = max(s, 0.75)
        if 0.48 <= h <= 0.60:
            s = max(s, 0.92)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._settings  = settings
        self._runner    = ArgyllRunner(settings, self)
        self._file_mgr  = FileManager(settings)

        self.setWindowTitle(tr("ChromIQ — Printer Profiling"))
        self.setMinimumSize(900, 650)
        self._title_bar_mode: str = "dark"
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(1440, screen.width())
        h = min(1025, screen.height())
        self.resize(w, h)

        # Central widget
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        from core.version import APP_VERSION
        self._masthead = MastheadHeader(version=APP_VERSION, parent=central)
        self._masthead.settings_clicked.connect(self._open_settings)
        self._masthead.help_clicked.connect(self.open_welcome_dialog)
        self._masthead.tools_clicked.connect(self._open_tools_menu)
        main_layout.addWidget(self._masthead)

        # Tabs
        self._tabs = QTabWidget(central)
        self._tabs.setDocumentMode(True)
        self._tabs.setTabBar(SpectrumTabBar(self._tabs))
        # Focusable tab strip so ⌘1–5 (and Tab) can land on it and ← / → then move
        # between tabs — independent of the macOS "Full Keyboard Access" setting.
        self._tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._tab_chart   = TabChart(self._runner, self._file_mgr, self._settings, self)
        self._tab_print   = TabPrint(self._settings, self)
        self._tab_measure = TabMeasure(self._runner, self._settings, self)
        self._tab_profile = TabProfile(self._runner, self._settings, self)
        self._tab_check   = TabCheckRefine(self._runner, self._settings, self)

        # #130: one shared "Profile run / Run type" selection, owned by a single
        # controller and shown in one bar above the tabs, so the choice stays in
        # step across Create Chart, Print Chart and Measure.
        from ui.measurement_target_bar import (
            MeasurementTargetBar, MeasurementTargetController)
        self._target_ctl = MeasurementTargetController(self._file_mgr, self)
        self._target_bar = MeasurementTargetBar(self._target_ctl, parent=central)
        # Live on the masthead's version rail, centred and in line with the
        # 'PRINTER PROFILING' tagline and the version number (#130). Re-centre
        # whenever the bar's width changes (the Verification box shows/hides).
        self._masthead.set_center_widget(self._target_bar)
        self._target_ctl.changed.connect(self._masthead.reposition_center)
        for _t in (self._tab_chart, self._tab_measure):
            if hasattr(_t, "set_target_controller"):
                _t.set_target_controller(self._target_ctl)

        self._load_state_snapshot: dict | None = None
        # Which (tab → theme) the per-tab stylesheet has already been applied for,
        # so a revisit doesn't pay the ~30 ms style re-polish again. Keyed on the
        # theme so a theme switch (apply_theme sets the mode, then re-styles all
        # tabs) correctly misses and re-applies. Perf: tab-switch snappiness.
        self._styled_tab_theme: dict[int, str] = {}

        self._tabs.addTab(self._tab_chart,   tr("1. Create Chart"))
        self._tabs.addTab(self._tab_print,   tr("2. Print Chart"))
        self._tabs.addTab(self._tab_measure, tr("3. Measure"))
        self._tabs.addTab(self._tab_profile, tr("4. Build Profile"))
        self._tabs.addTab(self._tab_check,   tr("5. Check & Refine"))

        # Gradient wash — left panel only for splitter tabs, full pane for the rest
        from ui.styles import TAB_COLORS
        for _i in range(self._tabs.count()):
            _tab_w = self._tabs.widget(_i)
            _target = getattr(_tab_w, "_left_panel", _tab_w)
            GradientOverlay(TAB_COLORS[_i], parent=_target)

        self._tab_chart.chart_finished.connect(self._on_chart_generated)
        # "Last page not full" hint → open the patch-set editor on the current chart.
        self._tab_chart.edit_patch_set_requested.connect(
            lambda: self._launch_tool("ti2_relayout"))
        self._tab_chart.target_started.connect(self._tab_profile.clear_files)
        self._tab_chart.target_started.connect(self._tab_check.clear_files)
        self._tab_measure.measure_finished.connect(self._on_measure_done)
        self._tab_profile.cal_file_created.connect(self._on_cal_file_created)
        self._tab_profile.cal_chart_requested.connect(self._on_cal_chart_requested)
        self._tab_measure.proceed_to_profile.connect(self._on_proceed_to_profile)
        self._tab_measure.measurement_active.connect(self._on_measurement_active)
        self._tab_profile.profile_active.connect(self._on_profile_active)
        self._tab_profile.profile_built.connect(self._tab_check.set_paths)
        self._tab_profile.check_requested.connect(lambda: self._tabs.setCurrentWidget(self._tab_check))
        self._tab_profile.preconditioning_requested.connect(self._on_preconditioning_requested)
        self._tab_check.preconditioning_requested.connect(self._on_preconditioning_requested)
        self._tab_profile.ti2_found.connect(self._tab_print.set_ti2_path)
        self._tab_profile.about_to_load_ti3.connect(self._save_load_state)
        self._tab_check.about_to_load_ti3.connect(self._save_load_state)
        self._tab_print.ti2_load_cancelled.connect(self._restore_load_state)
        self._tab_print.chart_relocated.connect(self._on_chart_relocated)
        self._tab_check.guide_refinement_requested.connect(self._on_guide_refinement)
        self._tab_check.ti3_selected.connect(self._tab_profile.set_ti3_path)
        self._tab_check.ti2_found.connect(self._tab_measure.set_ti1_path)
        self._tab_print.ti2_loaded.connect(self._tab_measure.set_ti1_path)
        self._tab_measure.ti2_loaded.connect(self._tab_print.apply_loaded_ti2)
        self._tab_print.ti2_replaced.connect(self._tab_profile.clear_files)
        self._tab_print.ti2_replaced.connect(self._tab_check.clear_files)
        self._tab_measure.ti2_replaced.connect(self._tab_profile.clear_files)
        self._tab_measure.ti2_replaced.connect(self._tab_check.clear_files)
        self._tab_profile.ti3_manually_loaded.connect(self._tab_check.clear_files)
        self._tab_measure.measure_finished.connect(lambda _: self._tab_check.clear_files())
        # Loading a chart in Print/Measure reflects it (read-only) in Create Chart
        # so every tab agrees on the active target. Reflect-only: no copy, no
        # folder — see TabChart.reflect_loaded_chart.
        self._tab_print.chart_load_requested.connect(self._tab_chart.reflect_loaded_chart)
        self._tab_measure.chart_load_requested.connect(self._tab_chart.reflect_loaded_chart)

        main_layout.addWidget(self._tabs, stretch=1)

        # 2px accent line on the left edge — child of the main window so it
        # spans the full height including the status bar below the tab widget
        self._accent_line = QFrame(self)
        self._accent_line.setFixedWidth(2)
        self._accent_line.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Style every tab's own widget tree up front. _on_tab_changed otherwise
        # injects the per-tab accent stylesheet lazily, only when a tab is first
        # navigated to — so a tab whose first show happens while it was never the
        # current tab (the app restores active_tab, which may be any tab) renders
        # unstyled on macOS until the user switches away and back. See issue #35.
        for _i in range(self._tabs.count()):
            self._apply_tab_widget_styling(_i)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        QTimer.singleShot(0, lambda: self._on_tab_changed(self._tabs.currentIndex()))

        # Restore geometry
        geom = self._settings.get("window_geometry")
        if geom:
            try:
                self.restoreGeometry(geom)
                available = QApplication.primaryScreen().availableGeometry()
                fg = self.frameGeometry()
                if fg.right() > available.right():
                    fg.moveRight(available.right())
                if fg.bottom() > available.bottom():
                    fg.moveBottom(available.bottom())
                self.move(fg.topLeft())
            except Exception:
                pass

        if self._settings.get("restore_last_tab", True):
            active = int(self._settings.get("active_tab", 0))
            self._tabs.setCurrentIndex(active)

        if self._settings.get("restore_last_session", False):
            QTimer.singleShot(0, self._restore_last_session)

        self.statusBar().hide()
        self._status_msg: str = ""

        self._install_shortcuts()
        self._check_argyll_binaries(initial=True)
        self._startup_update_checker: UpdateChecker | None = None
        QTimer.singleShot(0, lambda: self._apply_title_bar(self._title_bar_mode))
        QTimer.singleShot(0, self._apply_calibration_mode)
        QTimer.singleShot(3000, self._check_for_updates_on_startup)
        log.info("MainWindow initialised")

    def _install_shortcuts(self) -> None:
        """App-wide keyboard shortcuts. Every binding carries the ⌘ modifier (or
        is an F-key) so none can collide with the single keys chartread claims
        during a measurement (Space / Enter / Esc / ← / → and letters): while
        measuring, the Measure tab's application-level key filter owns the
        keyboard and these simply stand down. Kept in sync with the Welcome
        window's "Keyboard shortcuts" Help card."""
        def sc(seq, slot) -> None:
            QShortcut(QKeySequence(seq), self, activated=slot)

        # ⌘1…⌘5 — jump straight to a tab (Qt maps Ctrl→⌘ on macOS).
        for _i in range(self._tabs.count()):
            sc(f"Ctrl+{_i + 1}", lambda i=_i: self._go_to_tab(i))
        # Settings / Help / Tools. Explicit sequences (not StandardKey) so the
        # binding is deterministic — the platform "Preferences"/"HelpContents"
        # standard keys resolve to bare media keys under some Qt platforms. Qt
        # still renders "Ctrl" as ⌘ on macOS.
        sc("Ctrl+,", self._open_settings)                            # ⌘,
        sc("F1", self.open_welcome_dialog)                           # F1
        sc("Ctrl+?", self.open_welcome_dialog)                       # ⌘? (mac Help)
        sc("Ctrl+T", self._open_tools_menu)                          # Tools popup
        # ⌘Return / ⌘Enter — run the current tab's main action.
        sc("Ctrl+Return", self._trigger_primary_action)
        sc("Ctrl+Enter", self._trigger_primary_action)

    # Each tab's main action button, for the ⌘Return shortcut. (The many other
    # objectName="primary" buttons live inside per-tab sub-dialogs.)
    _PRIMARY_ACTION_ATTR = {
        "TabChart": "_generate_btn", "TabPrint": "_print_page_btn",
        "TabMeasure": "_start_btn", "TabProfile": "_build_btn",
        "TabCheckRefine": "_run_btn",
    }

    def _primary_action_button(self):
        """The current tab's primary button, or None."""
        tab = self._tabs.currentWidget()
        attr = self._PRIMARY_ACTION_ATTR.get(type(tab).__name__)
        return getattr(tab, attr, None) if attr else None

    def _go_to_tab(self, i: int) -> None:
        """Switch to tab *i* and put keyboard focus on the tab strip, so ← / →
        then move between tabs (Basti: after ⌘N the arrow keys had nothing to act
        on). QTabBar navigates with the arrows natively once it has focus."""
        self._tabs.setCurrentIndex(i)
        self._tabs.tabBar().setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _trigger_primary_action(self) -> None:
        """Click the current tab's primary button (Generate / Print / Measure /
        Build / Check), if it has one and it's usable."""
        btn = self._primary_action_button()
        if btn is not None and btn.isEnabled() and btn.isVisible():
            btn.click()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refit_accent_line()

    def _refit_accent_line(self) -> None:
        y = self._masthead.height() + self._tabs.tabBar().height()
        self._accent_line.setGeometry(0, y, 2, max(0, self.height() - y))
        self._accent_line.raise_()

    def _on_tab_changed(self, index: int) -> None:
        from ui.styles import TAB_COLORS

        log.info("---- Tab → %s ----", self._tabs.tabText(index))
        # #130: keep the shared Profile-run list current (a run may have been
        # created since the bar last populated). Cheap; the picked run/type stay.
        color = TAB_COLORS[index] if index < len(TAB_COLORS) else TAB_COLORS[-1]
        if getattr(self, "_target_bar", None) is not None:
            self._target_bar.refresh()
            # Tint the bar's combobox highlight + ⓘ icon to the active tab's accent.
            self._target_bar.set_accent(color)
            self._masthead.reposition_center()

        # Compute variants without broken hex-alpha (Qt reads #AARRGGBB, not #RRGGBBAA)
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        color_glow = f"rgba({r},{g},{b},0.33)"
        is_light = getattr(self, "_title_bar_mode", "dark") == "light"
        pane_bg = "#ffffff" if is_light else "#181818"

        self._accent_line.setStyleSheet(f"background: {color}; border: none;")
        self._refit_accent_line()

        # The tab's own widget tree (mode buttons, primary button, combos, the
        # tooltip-button icons) is styled here. Split into its own method so it
        # can also run for every tab at construction — see _apply_tab_widget_styling.
        self._apply_tab_widget_styling(index)

        # The shared QTabWidget pane background follows the *current* tab only.
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {color_glow};
                background: {pane_bg};
            }}
        """)

        # When a tab is shown, Qt hands the initial focus to its first focusable
        # child. If that's a button (e.g. a mode toggle), the space bar would
        # activate it even though the user never tabbed there — so drop the focus
        # off any button the tab auto-focused (Knut).
        from ui.widgets import defer_clear_button_focus
        defer_clear_button_focus(self)

    def _apply_tab_widget_styling(self, index: int) -> None:
        """Inject a tab's per-tab accent stylesheet into its own widget tree.

        Split out of _on_tab_changed so it can run for *every* tab at
        construction, not just lazily when a tab is first navigated to. The app
        restores the last-used tab (active_tab), so a tab is often first shown
        without ever having been the current one. On macOS the first style-polish
        of the heavy Create Chart tree (Manual panel, the built-in-presets star,
        the light-mode combos) lands a beat late on that first show, leaving the
        preset combo, the star and the parameter rows looking blank until the
        user switches away and back. Pre-styling every tab up front makes the
        first show correct. See issue #35.
        """
        from ui.styles import TAB_COLORS
        from ui.tooltip_button import TooltipButton

        tab_w = self._tabs.widget(index)
        if not tab_w:
            return

        color = TAB_COLORS[index] if index < len(TAB_COLORS) else TAB_COLORS[-1]
        # Compute variants without broken hex-alpha (Qt reads #AARRGGBB, not #RRGGBBAA)
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        color_hover = "#{:02x}{:02x}{:02x}".format(int(r * 0.82), int(g * 0.82), int(b * 0.82))
        is_light = getattr(self, "_title_bar_mode", "dark") == "light"

        if is_light:
            # Light theme — keep the colored chip readable on a light bg.
            mode_inactive_bg     = "#eeeae5"
            mode_inactive_border = "#ccc9c3"
            mode_inactive_text   = "#989490"
            mode_hover_bg        = "#e4e0da"
            mode_hover_border    = "#b0aba4"
            mode_hover_text      = "#22211f"
            primary_text         = "#ffffff"
            primary_disabled_bg  = "#e8e6e1"
            primary_disabled_fg  = "#a8a4a0"
            # Greyed checkbox/radio indicator — matches light_styles disabled rule
            disabled_ind_bg      = "#eeece8"   # LM_BG_WINDOW
            disabled_ind_border  = "#d0ccc6"   # LM_BORDER
            # Big "Calculated Patches" number anchors to the masthead
            # "Chrom" wordmark colour, not the tab's spectrum accent, so
            # it reads as a text anchor rather than a per-tab tint.
            patch_count_color    = "#1c1b18"   # _PALETTE_LIGHT["wordmark"]
            log_color            = _darken_for_light_log(color)
        else:
            mode_inactive_bg     = "#2a2a2a"
            mode_inactive_border = "#4a4a4a"
            mode_inactive_text   = "#909090"
            mode_hover_bg        = "#383838"
            mode_hover_border    = "#5a5a5a"
            mode_hover_text      = "#e6e6e6"
            primary_text         = "#0a0a0a"
            primary_disabled_bg  = "#1e1e1e"
            primary_disabled_fg  = "#484848"
            # Greyed checkbox/radio indicator — matches styles.py disabled rule
            disabled_ind_bg      = "#1f1f1f"
            disabled_ind_border  = "#3a3a3a"
            patch_count_color    = "#ffffff"   # _PALETTE_DARK["wordmark"]
            log_color            = color

        _sheet = f"""
                QPushButton#primary {{
                    background: {color};
                    border: 1px solid {color};
                    color: {primary_text};
                    font-weight: 700;
                }}
                QPushButton#primary:hover {{
                    background: {color_hover};
                    border-color: {color_hover};
                }}
                QPushButton#primary:disabled {{
                    background: {primary_disabled_bg};
                    border: 1px solid {color};
                    color: {primary_disabled_fg};
                }}
                QCheckBox::indicator:checked {{
                    background: {color};
                    border-color: {color};
                }}
                QCheckBox::indicator:hover {{
                    border-color: {color};
                }}
                /* Greyed when the group is disabled — must beat :checked,
                   otherwise an active box keeps its bright accent fill. */
                QCheckBox::indicator:checked:disabled {{
                    background: {disabled_ind_bg};
                    border-color: {disabled_ind_border};
                }}
                QRadioButton::indicator:checked {{
                    background: {color};
                    border-color: {color};
                }}
                QRadioButton::indicator:checked:disabled {{
                    background: {disabled_ind_bg};
                    border-color: {disabled_ind_border};
                }}
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
                QComboBox:focus, QComboBox:on {{
                    border-color: {color};
                }}
                QLabel#patch_count {{
                    color: {patch_count_color};
                }}
                QLabel#info {{
                    color: {color};
                    border-color: {color};
                }}
                QLabel#warning {{
                    border-color: {color};
                }}
                QPlainTextEdit#log {{
                    color: {log_color};
                }}
                QPushButton#mode_btn {{
                    background: {mode_inactive_bg};
                    border: 1px solid {mode_inactive_border};
                    color: {mode_inactive_text};
                    font-size: 13px;
                    font-weight: 700;
                    padding: 6px 22px;
                }}
                QPushButton#mode_btn:hover {{
                    background: {mode_hover_bg};
                    border-color: {mode_hover_border};
                    color: {mode_hover_text};
                }}
                QPushButton#mode_btn:checked {{
                    background: {color};
                    border: 1px solid {color};
                    color: {primary_text};
                    font-size: 13px;
                    font-weight: 700;
                    padding: 6px 22px;
                }}
                QPushButton#mode_btn:checked:hover {{
                    background: {color_hover};
                    border-color: {color_hover};
                    color: {primary_text};
                }}
            """

        # The stylesheet is a pure function of (index, theme); a set stylesheet
        # stays applied and cascades to children added later, so on a revisit for
        # the same theme we can skip the costly re-`setStyleSheet` (~30 ms on the
        # heavy Create Chart tree) without any visual change. ACCENT + the tooltip
        # re-tint below still run every call: ACCENT is a class-global new dialogs
        # read, and the loop covers any tooltip button added since (Knut/perf).
        _mode = "light" if is_light else "dark"
        if self._styled_tab_theme.get(index) != _mode:
            tab_w.setStyleSheet(_sheet)
            self._styled_tab_theme[index] = _mode

        TooltipButton.ACCENT = color
        for btn in tab_w.findChildren(TooltipButton):
            btn._set_icon()

    def _on_chart_generated(
        self, tiffs: object, ti2: object, is_external_workflow: bool = False
    ) -> None:
        if is_external_workflow:
            # i1iSis: i1Profiler drives print + measure, so don't push the
            # ChromIQ preview TIFFs or TI2 into those tabs.
            return
        tiff_list = list(tiffs)
        self._tab_print.load_tiffs(tiff_list)
        if ti2 and Path(ti2).exists():
            self._tab_measure.set_ti1_path(Path(ti2))
        elif not tiff_list:
            # #130: an empty payload means the selected Profile-run / Run-type has
            # no chart yet (e.g. switched to Verification before its chart exists).
            # Drop the previous chart from Measure so the wrong chart can't be
            # printed or measured; Print was already cleared by load_tiffs([]).
            self._tab_measure.clear_chart_file()

    def _on_measure_done(self, ti3: Path) -> None:
        cal_mode = bool(self._settings.get("calibration_mode", False))
        # A calibration measurement lives in the project's cal/ folder rather
        # than carrying a cal_ filename prefix.
        if cal_mode and ti3.parent.name == "cal":
            self._tab_profile.set_cal_ti3_path(ti3)
            self._tabs.setCurrentWidget(self._tab_profile)
        else:
            self._tab_profile.set_ti3_path(ti3, propagate=False)
            # Forward the Measure-tab opt-in so Build Profile can merge the
            # pre-conditioning data (ChromIQ-style refinement). None when off.
            self._tab_profile.set_preconditioning_source(
                self._tab_measure.preconditioning_choice()
            )

    def _on_measurement_active(self, active: bool) -> None:
        measure_idx = self._tabs.indexOf(self._tab_measure)
        for i in range(self._tabs.count()):
            if i != measure_idx:
                self._tabs.setTabEnabled(i, not active)

    def _on_profile_active(self, active: bool) -> None:
        profile_idx = self._tabs.indexOf(self._tab_profile)
        for i in range(self._tabs.count()):
            if i != profile_idx:
                self._tabs.setTabEnabled(i, not active)

    def _on_cal_file_created(self, cal_path: Path) -> None:
        """Fill -K/-I fields silently (user chose Done in the result dialog)."""
        self._tab_chart.set_cal_file_paths(cal_path)

    def _on_cal_chart_requested(self, cal_path: Path) -> None:
        """Fill -K/-I fields and navigate to Create Chart (user chose Go to Create Chart)."""
        self._tab_chart.set_cal_file_paths(cal_path)
        self._tabs.setCurrentWidget(self._tab_chart)

    def _on_proceed_to_profile(self) -> None:
        self._tabs.setCurrentWidget(self._tab_profile)

    def _on_guide_refinement(self, ti3: Path, strips_file: Path) -> None:
        self._tabs.setCurrentWidget(self._tab_measure)
        self._tab_measure.start_guided_refinement(ti3, strips_file)

    def _on_preconditioning_requested(self, icc_path: Path) -> None:
        """User chose 'Use as pre-conditioning profile' from a result dialog."""
        self._tabs.setCurrentWidget(self._tab_chart)
        self._tab_chart.apply_preconditioning(icc_path)

    def _save_load_state(self) -> None:
        self._load_state_snapshot = {
            "profile_ti3": self._tab_profile.ti3_path,
            "measure_ti2": self._tab_measure.ti1_path,
            "check_ti3":   self._tab_check.ti3_path,
            "check_icc":   self._tab_check.icc_path,
        }

    def _restore_load_state(self) -> None:
        s = self._load_state_snapshot
        if s is None:
            return
        if s["profile_ti3"] is not None:
            self._tab_profile.set_ti3_path(s["profile_ti3"], propagate=False)
        else:
            self._tab_profile.clear_files()
        if s["measure_ti2"] is not None:
            self._tab_measure.set_ti1_path(s["measure_ti2"])
        else:
            self._tab_measure.clear_chart_file()
        if s["check_ti3"] is not None:
            icc = s["check_icc"] if s["check_icc"] is not None else s["check_ti3"].with_suffix(".icc")
            self._tab_check.set_paths(s["check_ti3"], icc, propagate=False)
        else:
            self._tab_check.clear_files()

    def _on_chart_relocated(self, new_ti2: Path) -> None:
        new_ti3 = new_ti2.with_suffix(".ti3")
        if new_ti3.exists():
            self._tab_profile.set_ti3_path(new_ti3, propagate=False)
            for ext in (".icc", ".icm"):
                icc = new_ti2.with_suffix(ext)
                if icc.exists():
                    self._tab_check.set_paths(new_ti3, icc, propagate=False)
                    break
            else:
                self._tab_check.set_paths(new_ti3, new_ti3.with_suffix(".icc"), propagate=False)
        else:
            self._tab_profile.clear_files()
            self._tab_check.clear_files()

    def open_welcome_dialog(self) -> None:
        # Non-modal so the dialog never blocks the event loop while it's up.
        # A modal exec() during startup preempts macOS's window-state animation
        # (maximize / fullscreen), causing the main window to revert to its
        # plain geometry. Storing a reference on self keeps the dialog alive
        # since show() does not block; clearing it on finished prevents leaks
        # when the user re-opens via the "?" button.
        if getattr(self, "_welcome_dialog", None) is not None:
            try:
                self._welcome_dialog.raise_()
                self._welcome_dialog.activateWindow()
                return
            except RuntimeError:
                self._welcome_dialog = None
        # Imported lazily: welcome_dialog translates its guide texts at
        # module level, which must happen after set_language().
        from ui.dialogs.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(
            self._settings,
            parent=self,
            initial_mode=self._title_bar_mode,
        )
        dlg.setModal(False)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dlg.finished.connect(lambda _: setattr(self, "_welcome_dialog", None))
        self._welcome_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_tools_menu(self) -> None:
        """Show the speech-bubble Tools popup under the masthead's Tools button."""
        from ui.tools_popup import ToolsPopup

        popup = ToolsPopup(self)
        popup.set_appearance(self._title_bar_mode)
        popup.selected.connect(self._launch_tool)
        popup.show_under(self._masthead.tools_button())

    def _launch_tool(self, key: str) -> None:
        if key == "patch_cube":
            self._show_patch_cube()
            return
        from ui.dialogs.tools_dialogs import open_tool_dialog
        # The TI2 layout editor's "Save & apply" hands its chart folder back to
        # the Create Chart tab through this callback.
        on_apply = self._apply_editor_chart if key == "ti2_relayout" else None
        # Pre-load that editor with the current chart so it opens ready to edit
        # (#45) — same accessor as the 3D-cube tool, guarded on the project
        # manifest existing (project() would otherwise materialise one).
        initial_chart = None
        if key == "ti2_relayout":
            initial_chart = self._current_chart_ti2()
        # The Verify-a-Profile tool points its file pickers at the loaded
        # project's run + verification history (#130). Guarded — a missing
        # manifest must never block opening a tool.
        project = None
        if key == "verify_profile" \
                and (self._file_mgr.working_dir() / "project.json").exists():
            try:
                project = self._file_mgr.project()
            except Exception:  # noqa: BLE001
                project = None
        open_tool_dialog(key, self._runner, self._settings, self,
                         on_apply=on_apply, initial_chart=initial_chart,
                         project=project)

    def _current_chart_ti2(self) -> "Path | None":
        """The current run's generated chart .ti2, or None when no chart has
        been generated yet (so the layout editor opens empty as before)."""
        if not (self._file_mgr.working_dir() / "project.json").exists():
            return None
        try:
            ti2 = self._file_mgr.project().current_run().chart_ti2
        except Exception:  # noqa: BLE001 — never block opening the tool
            return None
        return ti2 if ti2.exists() else None

    def _apply_editor_chart(self, src_dir: "Path", name: str) -> bool:
        """Adopt a chart the layout editor just saved and show the Create Chart tab.

        Returns False when the user cancelled a name-collision prompt, so the
        editor stays open instead of closing on a no-op.
        """
        applied = self._tab_chart.apply_external_chart(src_dir, name)
        if applied:
            self._tabs.setCurrentWidget(self._tab_chart)
        return applied

    def _show_patch_cube(self) -> None:
        """Open the 3D RGB-cube view of the chart currently loaded in the app.

        Reads the current project/run's chart (``.ti2``, falling back to
        ``.ti1``) into a 0..100 RGB program and shows it in the same
        ``PatchCubeDialog`` the layout editor uses. Unlike the editor's cube —
        which visualises the patches being edited — this one visualises whatever
        chart the rest of the window is working with, with no file picking.
        """
        from PyQt6.QtWidgets import QMessageBox

        no_chart = tr(
            "No chart is loaded yet.\n\n"
            "Generate or open a chart first (Create Chart tab), then this tool "
            "will show how its patches are spread across the RGB cube."
        )
        # project() materialises a project.json as a side effect, so guard on the
        # manifest existing first — exactly as session restore does.
        if not (self._file_mgr.working_dir() / "project.json").exists():
            QMessageBox.information(self, tr("Show patch distribution (3D)"), no_chart)
            return

        run = self._file_mgr.project().current_run()
        chart = run.chart_ti2 if run.chart_ti2.exists() else run.chart_ti1
        if not chart.exists():
            QMessageBox.information(self, tr("Show patch distribution (3D)"), no_chart)
            return

        from workflow.ti2_relayout import load_rgb_program
        try:
            program = load_rgb_program(chart)
        except ValueError as exc:
            # Multi-ink chart (#72): show it anyway — as a true Lab-space
            # scatter when its preconditioning profile is discoverable, else
            # as the display-RGB projection of the ink values.
            if self._show_nchannel_cube(chart):
                return
            QMessageBox.information(self, tr("Show patch distribution (3D)"), str(exc))
            return
        if not program:
            QMessageBox.information(self, tr("Show patch distribution (3D)"), no_chart)
            return

        from ui.dialogs.patch_cube_dialog import PatchCubeDialog
        from ui.theme import resolve_mode
        mode = resolve_mode(self._settings.get("appearance", "auto"))
        # Compare-with-preset list is built fresh each open, so newly saved /
        # deleted presets (with a .ti1) appear automatically (#66).
        try:
            presets = self._tab_chart.comparable_presets()
        except Exception as exc:  # noqa: BLE001 — never block the viewer on this
            log.warning("comparable_presets failed: %s", exc)
            presets = []
        # No target_name: the chart's file stem is the printer-profile name, which
        # post-#70 doesn't describe the layout — show the neutral "Current chart"
        # label instead of a misleading profile name (Knut, #70 follow-up).
        PatchCubeDialog(program, mode=mode,
                        compare_presets=presets, parent=self).exec()

    def _show_nchannel_cube(self, chart) -> bool:
        """3D distribution for a multi-ink chart (#72): a true Lab-space
        scatter when the chart's preconditioning profile is discoverable
        (xicclu -ff through it), else the display-RGB projection of the ink
        values in the normal cube. Returns False when nothing showable."""
        from pathlib import Path
        try:
            from workflow.layout_engine.colorants import to_display_rgb
            if Path(chart).suffix.lower() == ".ti2":
                from workflow.ti2_relayout import ChartSpec
                spec = ChartSpec.from_ti2(Path(chart))
                devs, rep = [p.dev for p in spec.patches], spec.color_rep
            else:
                from workflow.layout_engine.ti1_reader import read_ti1
                tgt = read_ti1(chart)
                devs, rep = [d for d, _ in tgt.patches], tgt.color_rep
            if not devs:
                return False
            colors = [to_display_rgb(d, rep) for d in devs]

            from ui.dialogs.patch_cube_dialog import PatchCubeDialog
            from ui.theme import resolve_mode
            mode = resolve_mode(self._settings.get("appearance", "auto"))

            from workflow.colorimetric_preview import find_device_profile
            profile = find_device_profile(chart)
            if profile is not None:
                from core.platform_paths import argyll_candidate_dirs
                from core.resource_path import argyll_binary
                bin_dir = next((d for d in argyll_candidate_dirs()
                                if (d / argyll_binary("xicclu")).exists()), None)
                if bin_dir is not None:
                    try:
                        from workflow.xicclu_runner import forward_lab
                        labs = forward_lab(devs, profile, bin_dir)
                        PatchCubeDialog(
                            [], mode=mode, lab_cloud=(labs, colors),
                            target_name=tr("Current chart ({rep}, via profile)"
                                           ).format(rep=rep),
                            parent=self).exec()
                        return True
                    except Exception as exc:  # noqa: BLE001 — fall through
                        log.warning("Lab cube for %s failed: %s", chart, exc)
            # No profile: the ink values projected to display RGB — honest
            # naming so nobody reads it as colorimetric truth.
            program = [(r / 2.55, g / 2.55, b / 2.55) for r, g, b in colors]
            PatchCubeDialog(
                program, mode=mode,
                target_name=tr("Current chart ({rep}, display approximation)"
                               ).format(rep=rep),
                parent=self).exec()
            return True
        except Exception as exc:  # noqa: BLE001 — never block the tool
            log.warning("N-channel cube failed for %s: %s", chart, exc)
            return False

    def _open_settings(self) -> None:
        # SettingsDialog tints its own tooltip ⓘ icons to the dialog's neutral
        # indicator colour (see SettingsDialog.__init__).
        # Preselect the Margin Thresholds combo to the current Create Chart
        # instrument + paper (#80).
        margin_combo = None
        if hasattr(self._tab_chart, "current_margin_combo"):
            margin_combo = self._tab_chart.current_margin_combo()
        # Preselect the Chart Layout tab to the same instrument/paper/mode (#93).
        layout_combo = None
        if hasattr(self._tab_chart, "current_layout_combo"):
            layout_combo = self._tab_chart.current_layout_combo()
        dlg = SettingsDialog(self._settings, self, margin_combo=margin_combo,
                             layout_combo=layout_combo)
        dlg.exec()
        self._check_argyll_binaries()
        self._apply_calibration_mode()
        self._tab_print.apply_native_dialog_mode()
        # Pick up an updated i1Pro chart-defaults preset immediately so the user
        # doesn't have to toggle instruments to see the new margin / scale.
        if hasattr(self._tab_chart, "_apply_instrument_default_margin"):
            self._tab_chart._apply_instrument_default_margin()
        if hasattr(self._tab_chart, "_update_patch_count"):
            self._tab_chart._update_patch_count()
        # Manual mode's Auto -g/-e/-B reflect the grey-ramp-reference anchor;
        # refresh its preview so a changed anchor takes effect immediately.
        if hasattr(self._tab_chart, "_refresh_manual_command_preview"):
            self._tab_chart._refresh_manual_command_preview()
        # Refresh visibility of -L / chart notes / stamp-commands / left-clip
        # rows so toggling 'Use ChromIQ-style clipping border' takes effect
        # immediately on the Create Chart tab.
        if hasattr(self._tab_chart, "refresh_chromiq_clip_visibility"):
            self._tab_chart.refresh_chromiq_clip_visibility()
        # Margin-inspector visibility / thresholds / guide toggle may have changed.
        if hasattr(self._tab_chart, "refresh_margin_inspector_settings"):
            self._tab_chart.refresh_margin_inspector_settings()
        # Engine-only Manual rows (#123) follow the engine beta + accuracy
        # mode — the Build Profile tab stays visible while Settings is
        # open, so its showEvent alone would miss the change.
        if hasattr(self._tab_profile, "_refresh_engine_rows"):
            self._tab_profile._refresh_engine_rows()
        # Chart-reading engine beta (#126): toggling it on/off now takes effect on
        # OK — the Measure tab's engine-only view controls appear/disappear
        # without an app restart (the measurement itself already reads the flag
        # live at each read).
        if hasattr(self._tab_measure, "refresh_engine_visibility"):
            self._tab_measure.refresh_engine_visibility()

    def _apply_calibration_mode(self) -> None:
        enabled = bool(self._settings.get("calibration_mode", False))
        for tab in (self._tab_chart, self._tab_measure, self._tab_profile, self._tab_check):
            if hasattr(tab, "set_calibration_mode"):
                tab.set_calibration_mode(enabled)
        # Same refresh moment for the profile-engine beta selector (#122).
        profile_idx = self._tabs.indexOf(self._tab_profile)
        self._tabs.setTabText(
            profile_idx,
            tr("4. Calibration & Profiling") if enabled else tr("4. Build Profile"),
        )

    def _check_for_updates_on_startup(self) -> None:
        # Honour the global opt-out the update popup offers.
        if not self._settings.get("update_notify", True):
            return
        self._startup_update_checker = UpdateChecker(self)
        self._startup_update_checker.update_available.connect(
            self._on_startup_update_available
        )
        self._startup_update_checker.check_async()

    def _set_tab_status(self, msg: str, warning: bool = False) -> None:
        self._status_msg = msg
        style_warn = (
            "background: #3a2a00; color: #ffb42d; border: 1px solid #ffb42d; "
            "border-radius: 4px; padding: 6px 10px; margin: 0px 16px 8px 16px;"
        )
        style_info = "color: #909090; font-size: 11px; padding: 4px 16px 8px 16px;"
        for tab in (self._tab_chart, self._tab_print, self._tab_measure):
            lbl = tab._status_bar_lbl
            lbl.setText(msg)
            lbl.setStyleSheet(style_warn if warning else style_info)
            lbl.setVisible(bool(msg))

    def _on_startup_update_available(self, latest: str) -> None:
        # Notify with a popup (the masthead-styled UpdateAvailableDialog), not a
        # status-bar line. If the user opts out, suppress all future popups.
        from ui.dialogs.update_dialog import UpdateAvailableDialog
        dlg = UpdateAvailableDialog(latest, self)
        dlg.exec()
        if dlg.disable_notifications:
            self._settings.set("update_notify", False)

    def _check_argyll_binaries(self, initial: bool = False) -> None:
        bin_dir = Path(self._settings.get("argyll_bin_path", "/Applications/Argyll/bin"))

        if all_tools_present(bin_dir):
            self._set_tab_status("")
            return

        if initial:
            # Try to auto-detect a working installation
            detected = find_argyll_bin_path()
            if detected:
                self._settings.set("argyll_bin_path", str(detected))
                log.info("ArgyllCMS auto-configured to %s", detected)
                self._set_tab_status("")
                return

        # Not found — show warning and, on first launch, a popup
        log.warning("ArgyllCMS binaries not found at %s", bin_dir)
        self._set_tab_status(
            "⚠  ArgyllCMS not found. Open Preferences (⚙) to set the path.", warning=True
        )
        if initial:
            self._show_argyll_not_found_dialog()

    def _show_argyll_not_found_dialog(self) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("ArgyllCMS Not Found"))
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            tr("<b>ArgyllCMS could not be found on your system.</b><br><br>"
            "ChromIQ requires ArgyllCMS to create and measure ICC profiles. "
            "It was not detected in any of the usual locations.<br><br>"
            "<b>To install ArgyllCMS:</b><br>"
            "&nbsp;&nbsp;1. Download ArgyllCMS from "
            "<a href='https://www.argyllcms.com'>argyllcms.com</a><br>"
            "&nbsp;&nbsp;2. Extract the archive and move the folder to "
            "<span style='font-family:Menlo, Consolas, \"Courier New\", monospace'>/Applications</span><br>"
            "&nbsp;&nbsp;3. Restart ChromIQ — it will detect the installation "
            "automatically.<br><br>"
            "If ArgyllCMS is already installed in a custom location, click "
            "<b>Open Preferences</b> to set the path manually."),
            dlg,
        )
        msg.setOpenExternalLinks(True)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox()
        prefs_btn = btn_box.addButton(tr("Open Preferences"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_box.addButton(tr("OK"), QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.accepted.connect(dlg.accept)
        prefs_btn.clicked.connect(dlg.accept)
        prefs_btn.clicked.connect(self._open_settings)
        layout.addWidget(btn_box)

        dlg.exec()

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def apply_theme(self, mode: str) -> None:
        """Sync widgets that aren't covered by the global QSS (masthead, title bar,
        TIFF preview, gamut viewer) and re-run the per-tab QSS injector so its
        hardcoded mode-button / primary-button colors match the new theme."""
        self._title_bar_mode = mode
        if hasattr(self._masthead, "set_appearance"):
            self._masthead.set_appearance(mode)
        self._apply_title_bar(mode)
        # Broadcast to any descendant widget that opts in via set_appearance().
        # Used by TiffPreview and GamutPanel to swap their non-QSS bg colors.
        for w in self.findChildren(QWidget):
            fn = getattr(w, "set_appearance", None)
            if callable(fn) and w is not self._masthead:
                try:
                    fn(mode)
                except Exception:
                    pass
        # Reload theme-aware icons (folder glyphs, preset +/-) so their palette-
        # dependent variants repaint without needing an app restart.
        from ui.widgets import apply_themed_icons, reapply_groupbox_surface, reapply_input_stylesheet
        apply_themed_icons(self)
        reapply_groupbox_surface(self)
        reapply_input_stylesheet(self)
        # Re-run the per-tab QSS injector — its mode_btn / primary colors are
        # baked in per-mode, so a theme switch needs to regenerate them. Restyle
        # *every* tab, not just the current one, so non-current tabs (pre-styled
        # at construction for issue #35) don't keep stale-mode colors until they
        # are next navigated to. _on_tab_changed then refreshes the current tab's
        # accent line and pane background.
        if hasattr(self, "_tabs"):
            for _i in range(self._tabs.count()):
                self._apply_tab_widget_styling(_i)
            self._on_tab_changed(self._tabs.currentIndex())
        # Boost the log-widget weight in light mode — QSS font-weight on
        # QPlainTextEdit text is unreliable on Windows because the document
        # uses its own default font, so set it via QFont directly. Done AFTER
        # the per-tab QSS re-injection so the stylesheet's font cascade
        # doesn't overwrite our heavier weight.
        from PyQt6.QtGui import QFont
        _log_weight = QFont.Weight.Black if mode == "light" else QFont.Weight.Normal
        for log in self.findChildren(QPlainTextEdit, "log"):
            f = log.font()
            f.setWeight(_log_weight)
            log.setFont(f)
            # The QTextDocument keeps its own default font that may have been
            # initialised before our widget setFont call — sync it explicitly.
            doc = log.document()
            if doc is not None:
                df = doc.defaultFont()
                df.setWeight(_log_weight)
                doc.setDefaultFont(df)

    def _apply_title_bar(self, mode: str) -> None:
        """Set the macOS native title bar appearance to match `mode`."""
        import sys
        if sys.platform != "darwin":
            return
        ns_name = b"NSAppearanceNameAqua" if mode == "light" else b"NSAppearanceNameDarkAqua"
        try:
            import ctypes, ctypes.util
            objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
            objc.objc_msgSend.restype      = ctypes.c_void_p
            objc.sel_registerName.restype  = ctypes.c_void_p
            objc.objc_getClass.restype     = ctypes.c_void_p

            def _S(name: str):
                return objc.sel_registerName(name.encode())

            def _C(name: str):
                return objc.objc_getClass(name.encode())

            def _msg(obj, sel, *args, argtypes=None):
                objc.objc_msgSend.argtypes = (
                    [ctypes.c_void_p, ctypes.c_void_p]
                    + (argtypes or [ctypes.c_void_p] * len(args))
                )
                return objc.objc_msgSend(obj, _S(sel), *args)

            name_str = _msg(
                _C("NSString"), "stringWithUTF8String:",
                ns_name,
                argtypes=[ctypes.c_char_p],
            )
            appearance = _msg(
                _C("NSAppearance"), "appearanceNamed:",
                ctypes.c_void_p(name_str),
            )
            ns_view   = ctypes.c_void_p(int(self.winId()))
            ns_window = _msg(ns_view, "window")
            _msg(ns_window, "setAppearance:", ctypes.c_void_p(appearance))
        except Exception:
            pass

    def _restore_last_session(self) -> None:
        target = self._settings.get("session_target_name", "")
        if not target:
            return
        self._file_mgr.set_target_name(target)

        # Only the target name is persisted now; every artefact path is derived
        # from the project's current run. Bail if there's no project on disk for
        # this target (deleted folder, or a pre-redesign session).
        if not (self._file_mgr.working_dir() / "project.json").exists():
            log.info("Session restore skipped: no project for target=%s", target)
            return

        proj = self._file_mgr.project()
        run = proj.current_run()

        if proj.schema_too_new:
            # A newer ChromIQ organised this project's folders in a way this
            # build doesn't know. Opening is safe (profiles/measurements sit
            # in the same place in every format) but some files may not be
            # found where this build expects them — tell the user plainly
            # instead of half-working (#127).
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, tr("Project from a newer ChromIQ"),
                tr("The project “{name}” was last used with a newer "
                   "version of ChromIQ, which organises the project folder "
                   "differently.\n\n"
                   "Your profiles and measurements are safe, but some files "
                   "may not be found where this version expects them. Please "
                   "update ChromIQ to keep working with this project."
                   ).format(name=proj.target_name))

        if run.chart_ti1.exists():
            self._tab_measure.set_ti1_path(run.chart_ti1)

        tiffs = run.chart_tiffs()
        if tiffs:
            self._tab_print.load_tiffs(tiffs)

        ti3 = run.measurement_ti3
        icc = run.built_profile_icc()
        if ti3.exists():
            self._tab_profile.set_ti3_path(ti3, propagate=False)
        if icc.exists():
            self._tab_profile.set_icc_path(icc)
        if ti3.exists() and icc.exists():
            self._tab_check.set_paths(ti3, icc)

        if self._settings.get("calibration_mode", False):
            cal_ti3 = proj.calibration.ti3
            if cal_ti3.exists():
                self._tab_profile.set_cal_ti3_path(cal_ti3)

        log.info("Session restored: target=%s run=%s", target, run.id)

    def closeEvent(self, event) -> None:
        # Capture geometry BEFORE hide(): on macOS, hide() can leave the
        # maximized/fullscreen state before saveGeometry() snapshots it,
        # which would make restoreGeometry() on next launch fall back to
        # the plain "normal" geometry instead of re-maximizing.
        self._settings.set("window_geometry", self.saveGeometry())
        self._settings.set("window_maximized", bool(self.isMaximized()))
        self._settings.set("window_fullscreen", bool(self.isFullScreen()))
        # Hide so the window vanishes immediately; the WebEngine drain
        # below runs invisibly. Tear down QtWebEngine before super() returns
        # and Qt destroys the widget tree, otherwise SIP follows a dangling
        # Chromium pointer during QApplication dealloc (EXC_BAD_ACCESS).
        self.hide()
        self._tab_check.shutdown_webengine()
        self._tab_print.shutdown()
        self._settings.set("active_tab", self._tabs.currentIndex())
        # Only the target name is persisted; _restore_last_session derives every
        # artefact path from the project's current run (project.json).
        self._settings.set("session_target_name",  self._file_mgr._target_name)
        self._runner.cleanup()
        super().closeEvent(event)
