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
from core.measurement_target import RUN_TYPE_PROFILING

log = get_logger(__name__)

# THE FIRST-LAUNCH "ARGYLLCMS NOT FOUND" TEXT, ONE STEP PER PLATFORM.
#
# It used to be a single message telling every user to "move the folder to
# /Applications". On Windows that folder does not exist, so the first
# instruction a new Windows user reads is impossible to follow. It was wrong on
# macOS too, in a quieter way: /Applications is one of eight locations searched
# (core/platform_paths.py), and naming only it makes a Homebrew user — whose
# install IS found automatically — think they have done something wrong.
#
# Module-level constants, not inline literals, because tr() needs the exact
# English string as its catalogue key and scripts/i18n_extract.py resolves
# module-level `NAME = "literal"` for tr(NAME) — by AST walk, not by importing
# this module. Two consequences, both learned the hard way: they must be PLAIN
# literals (an f-string is ast.JoinedStr and extracts to nothing), and tr() must
# wrap the module-level NAME itself, never a local holding it.
# NB: PLAIN literals, never f-strings. scripts/i18n_extract.py resolves
# tr(NAME) only for `NAME = <ast.Constant>`; an f-string parses to ast.JoinedStr
# and the key becomes invisible to extraction, so all 12 catalogues report it as
# a stale entry. Adjacent literals fold into one Constant, so wrapping is fine.
# EVERY PATH NAMED BELOW MUST BE ONE core.platform_paths.argyll_candidate_dirs()
# ACTUALLY SEARCHES. tests/test_argyll_not_found_dialog.py asserts exactly that,
# because the first draft of this message got it wrong twice: it sent macOS users
# to ~/Applications (only /Applications gets the versioned scan — the home arm is
# the literal ~/Applications/Argyll/bin) and told Linux users to unpack to
# /opt/argyll (there is no versioned scan on Linux at all; the candidate is the
# literal /opt/argyll/bin). Both would have reproduced the very bug this message
# exists to fix: telling a user to put ArgyllCMS where ChromIQ does not look.
#
# The version number is deliberately NOT named. It would bake "3.5.0" into a
# translated key, so a 3.6.0 bump would invalidate all 12 catalogues — and the
# download page always serves the current release.
_ARGYLL_WHERE_WINDOWS = (
    "Unzip it and move the Argyll folder it contains into "
    "<span style='font-family:Menlo, Consolas, \"Courier New\", monospace'>"
    "C:\\Program Files\\ArgyllCMS\\</span>, or into "
    "<span style='font-family:Menlo, Consolas, \"Courier New\", monospace'>"
    "%LOCALAPPDATA%\\ArgyllCMS\\</span> if you do not have administrator rights"
)
_ARGYLL_WHERE_MACOS = (
    "Unpack it and move the Argyll folder it contains into "
    "<span style='font-family:Menlo, Consolas, \"Courier New\", monospace'>"
    "/Applications</span> — Homebrew and MacPorts installations are found "
    "automatically too"
)
_ARGYLL_WHERE_LINUX = (
    "Unpack it so the binaries end up in "
    "<span style='font-family:Menlo, Consolas, \"Courier New\", monospace'>"
    "/opt/argyll/bin</span>, or copy them into a directory on your "
    "<span style='font-family:Menlo, Consolas, \"Courier New\", monospace'>"
    "PATH</span> such as "
    "<span style='font-family:Menlo, Consolas, \"Courier New\", monospace'>"
    "/usr/local/bin</span>"
)
_ARGYLL_NOT_FOUND_MSG = (
    "<b>ArgyllCMS could not be found on your system.</b><br><br>"
    "ChromIQ requires ArgyllCMS to create and measure ICC profiles. "
    "It was not detected in any of the usual locations.<br><br>"
    "<b>To install ArgyllCMS:</b><br>"
    "&nbsp;&nbsp;1. Download ArgyllCMS from "
    "<a href='{url}'>argyllcms.com</a><br>"
    "&nbsp;&nbsp;2. {where}<br>"
    "&nbsp;&nbsp;3. Restart ChromIQ — it will detect the installation "
    "automatically.<br><br>"
    "ChromIQ also finds it anywhere else you may have put it, as long as you "
    "point it there: click <b>Open Preferences</b> to set the path manually."
)


def _mix_hex(a: str, b: str, t: float) -> str:
    """Blend two #rrggbb colours, *t* = share of *a*. Used for the "locked on"
    checkbox fill: a muted version of the tab accent that still reads as a tick
    against the disabled background."""
    def _c(h):
        h = h.lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    ca, cb = _c(a), _c(b)
    return "#" + "".join(f"{round(x * t + y * (1 - t)):02x}"
                         for x, y in zip(ca, cb))


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
    # How long the chart-build lock waits for a follow-on tool before letting
    # go on its own. A Manual build runs targen then printtarg back to back
    # (measured: the gap is under 10 ms), so this only ever fires when a build
    # ended without emitting `chart_finished`.
    _CHART_LOCK_GRACE_MS = 1500

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._settings  = settings
        # The log panels are user-resizable and share one remembered size, so
        # the helpers need somewhere to read and write it (Basti). Bound before
        # any tab is built, because each log registers itself as it is sized.
        from ui.widgets import bind_log_settings
        bind_log_settings(settings)
        self._runner    = ArgyllRunner(settings, self)
        self._file_mgr  = FileManager(settings)

        self.setWindowTitle(tr("ChromIQ — Printer Profiling"))
        self.setMinimumSize(900, 650)
        # SEEDED FROM THE APPEARANCE ALREADY RESOLVED, NOT ASSUMED DARK.
        #
        # This drives the real title bar (_apply_title_bar), the masthead popup —
        # and, at :393/:444, the is_light flag the five construction-time tab
        # stylesheets are built and CACHED under. Hard-coded "dark", every one of
        # them was built dark and filed under "dark", so apply_theme("light")
        # missed all five and re-styled the lot: 327 ms in dark against 732 ms in
        # light. main() resolves the appearance long before this runs (measured at
        # 371 ms of a 5.2 s launch), so the answer is already known here.
        from ui.theme import resolve_mode
        try:
            self._title_bar_mode: str = resolve_mode(
                settings.get("appearance", "auto"))
        except Exception:      # noqa: BLE001 — a theme guess must not stop startup
            self._title_bar_mode = "dark"
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
        self._masthead.load_project_clicked.connect(self._on_masthead_load_project)
        self._masthead.load_ti2_clicked.connect(self._on_masthead_load_ti2)
        self._masthead.close_project_clicked.connect(self._on_masthead_close_project)
        # Compute the masthead's starting state now, or Close Project looks
        # available on a fresh launch with nothing open.
        QTimer.singleShot(0, self._refresh_masthead_availability)
        main_layout.addWidget(self._masthead)

        # Tabs
        self._tabs = QTabWidget(central)
        # THE PANE STYLESHEET BEFORE THE PAGES, NOT AFTER.
        #
        # Setting it once the five tabs are in re-polishes the whole pane and
        # everything under it — 395 ms. Set on the empty widget it costs 9 ms and
        # reaches the same place, because a stylesheet cascades to children added
        # later. `_on_tab_changed` then finds its string already applied and its
        # cache skips the work.
        # SCOPED TO THIS TAB WIDGET, not every QTabWidget in the app.
        #
        # An unscoped `QTabWidget::pane` cascades into any dialog parented to a
        # tab, and three of them are: MeasurementReportDialog (Measure), and
        # SettingsDialog from "Edit layout defaults" (Create Chart). On master
        # they inherited the pane rule and painted the CURRENT TAB'S accent —
        # Preferences opened from Create Chart showed a pink hairline. Worse,
        # our `border: none` also stripped the left/right/bottom frame light
        # mode gives every pane, so the same dialog looked different depending
        # on where it was opened from: 60,759 px apart for the report, 69,009
        # for Preferences. Scoping the selector leaves those dialogs alone.
        self._tabs.setObjectName("chromiq_main_tabs")
        # The three "something is running" flags, declared up front. Every
        # reader used getattr(..., False) because a fresh window did not have
        # them — harmless, but it meant `w._measuring` raised AttributeError on
        # a window nobody had measured with yet.
        self._measuring = False
        self._profile_building = False
        self._chart_building = False
        self._chart_locked = False
        self._pane_qss = self._compose_pane_qss()
        self._tabs.setStyleSheet(self._pane_qss)
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
        # Tab 4 is not available for a verification — see _apply_profile_tab_gate.
        self._target_ctl.changed.connect(self._apply_profile_tab_gate)
        # …and the masthead: Close Project has something to close the moment a
        # project exists. Without this the button stayed greyed after
        # generating a chart or opening a project, because nothing told it
        # (Basti, #164).
        self._target_ctl.changed.connect(self._refresh_masthead_availability)
        # …and the FileManager itself, which is where "is a project open?"
        # actually lives. The bar signal above only catches routes that also
        # move the bar; this catches every route that names or unnames a
        # project, however it got there (#164).
        add_listener = getattr(self._file_mgr, "add_named_state_listener", None)
        if callable(add_listener):
            add_listener(self._refresh_masthead_availability)
            # …and the Create Chart hint that says "you already have a project
            # with this name". It only ever refreshed when the TEXT changed, and
            # adopting a project does not change the text — so it went on
            # showing after ChromIQ had opened exactly the project it was
            # warning about. This listener fires whenever the open project
            # changes, which is the real rule.
            add_listener(self._refresh_project_hint)
        # A restored verification chart must reach every tab, so nothing is left
        # showing or printing the pages it replaced (#130, Knut).
        self._target_ctl.chart_restored.connect(self._on_verify_chart_restored)
        # The WRITE trigger of the settings queue (#130): the pulldown is
        # open but nothing picked yet, so what is on screen still belongs
        # to the target it was set on.
        self._target_ctl.about_to_change_target.connect(
            self._save_settings_of_visible_tab)
        # …and the READ trigger (§2 L3/L4): the tab ON SCREEN loads the new
        # target the moment it is selected. Create Chart always did this
        # through its own _on_target_changed; Measure and Build Profile did
        # not, so they kept showing the OLD target's values — and then filed
        # them onto the new target when the tab was left, the §2.1 corruption.
        # Knut, 2026-08-11: "All tabs must save-on-change-from /
        # reload-on-change-to a tab … same principle, same method."
        self._target_ctl.changed.connect(self._load_settings_of_visible_tab)
        # "Delete the whole project" has to leave the app as it starts — every
        # tab empty, nothing loaded, and no project silently made again (#130,
        # Knut 2026-07-29).
        self._target_bar.project_deleted.connect(self._on_project_deleted)
        self._target_bar.run_duplicated.connect(self._on_run_duplicated)
        # §6: "Duplicate the run and build there" in the Build Profile warning
        # runs the bar's own Duplicate — same confirmation, same guards, and the
        # copy is selected afterwards, so the next build lands in it.
        self._tab_profile.duplicate_run_requested.connect(
            self._target_bar.request_duplicate)
        # Build Profile joins them (#130, beta.133): it had no idea which run
        # was selected, so its measurement could point at another run entirely
        # — and the profile then landed there.
        for _t in (self._tab_chart, self._tab_measure, self._tab_print,
                   self._tab_profile, self._tab_check):
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

        self._hint_primary_action_shortcuts()
        self._tab_chart.chart_finished.connect(self._on_chart_generated)
        # Any Argyll tool starting or stopping can change what the masthead may
        # offer — see _refresh_masthead_availability.
        self._tab_chart.target_started.connect(self._on_chart_build_started)
        self._tab_chart.chart_finished.connect(
            lambda *_a: self._on_chart_build_finished())
        # …and the runner itself, so a build that ends without its own signal
        # still releases the masthead.
        self._runner.finished.connect(lambda *_a: self._on_a_tool_finished())
        # …and the moment a tool actually starts. `target_started` fires before
        # the process exists, so it alone can never satisfy the "a chart build
        # is running" test — this is the edge that engages the lock.
        self._runner.started.connect(self._on_a_tool_started)
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
        # The log panels exist by now, so honour the preference before the
        # window is first shown rather than after the first Preferences visit.
        self._apply_log_visibility()

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
        #: Set by _check_argyll_binaries(initial=True); consumed once by
        #: show_startup_warnings() after the window is up. Initialised here so
        #: it exists on the healthy path too, where that check early-returns.
        self._argyll_missing_at_start: bool = False

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
        from ui.keyboard_help import BINDINGS

        def sc(action, slot) -> None:
            """Install one binding BY NAME, from the single registry.

            The specs used to be typed here as literals and typed AGAIN in the
            Help card's `_shortcuts()`, so the two agreed only by hand — and a
            tooltip carrying the same key would have made a third copy. Naming
            the action means all three read one dictionary.
            """
            QShortcut(QKeySequence(BINDINGS[action]), self, activated=slot)

        # ⌘1…⌘5 — jump straight to a tab (Qt maps Ctrl→⌘ on macOS).
        for _i in range(self._tabs.count()):
            sc(f"tab_{_i + 1}", lambda i=_i: self._go_to_tab(i))
        # Settings / Help / Tools. Explicit sequences (not StandardKey) so the
        # binding is deterministic — the platform "Preferences"/"HelpContents"
        # standard keys resolve to bare media keys under some Qt platforms. Qt
        # still renders "Ctrl" as ⌘ on macOS.
        sc("preferences", self._open_settings)                            # ⌘,
        sc("help", self.open_welcome_dialog)                           # F1
        sc("help_alt", self.open_welcome_dialog)                       # ⌘? (mac Help)
        sc("tools", self._open_tools_menu)                          # Tools popup
        # The two masthead buttons that bring something in (#164). ⌘O reads off
        # "Open Project"; ⇧⌘O off "Open Chart File", keeping the pair on one
        # key. NOT ⌘L — the button says nothing with an L in it, and ⌘L is the
        # address bar in every browser, so it is the key most likely to be
        # pressed by muscle memory meaning something else. Close Project gets
        # NO shortcut: ⌘W would close the window on macOS, and a project is not
        # something to let go of by reflex.
        sc("open_project", self._on_masthead_load_project)                 # ⌘O
        sc("open_chart_file", self._on_masthead_load_ti2)               # ⇧⌘O
        # ⌘Return / ⌘Enter — run the current tab's main action.
        sc("primary_action", self._trigger_primary_action)
        sc("primary_action_alt", self._trigger_primary_action)

    # Each tab's main action button, for the ⌘Return shortcut. (The many other
    # objectName="primary" buttons live inside per-tab sub-dialogs.)
    _PRIMARY_ACTION_ATTR = {
        "TabChart": "_generate_btn", "TabPrint": "_print_page_btn",
        "TabMeasure": "_start_btn", "TabProfile": "_build_btn",
        "TabCheckRefine": "_run_btn",
    }

    def _hint_primary_action_shortcuts(self) -> None:
        """Give each tab's main button its ⌘↵ hint (Knut, #164).

        Five of the buttons a user presses most had NO tooltip at all, so the
        shortcut existed, was listed on the Help card, and was invisible where
        it would actually be discovered. The label supplies the text — it is
        already translated, so this adds no key to any catalogue — and the
        binding comes from `keyboard_help.BINDINGS`, so it can never drift from
        what `_install_shortcuts` installs.
        """
        from ui.keyboard_help import attach_shortcut_hint

        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            attr = self._PRIMARY_ACTION_ATTR.get(type(tab).__name__)
            btn = getattr(tab, attr, None) if attr else None
            if btn is not None:
                attach_shortcut_hint(btn, "primary_action")

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
        if event.oldSize().height() != event.size().height():
            self._refit_log_panes()

    def _refit_log_panes(self) -> None:
        """Keep the log panels inside the window when its height changes.

        A shorter window must not push the panel through the bottom of the
        frame (Basti, beta.141: *"the border to the frame of the app's main
        window is gone and it looks strange"*), and a taller one should give
        back the size that was asked for. Re-entrant by nature — resizing the
        panels resizes the window's contents — so it is guarded rather than
        left to recurse.
        """
        if getattr(self, "_refitting_logs", False):
            return
        self._refitting_logs = True
        try:
            from ui.widgets import refit_log_panes

            refit_log_panes()
        finally:
            self._refitting_logs = False

    def _refit_accent_line(self) -> None:
        y = self._masthead.height() + self._tabs.tabBar().height()
        self._accent_line.setGeometry(0, y, 2, max(0, self.height() - y))
        self._accent_line.raise_()

    def _on_tab_changed(self, index: int) -> None:
        from ui.styles import TAB_COLORS

        log.info("---- Tab → %s ----", self._tabs.tabText(index))
        # §3 W6 / §2 L1 — Knut's general rule: "Load settings when activating
        # tab, Save / write settings when leaving tab". The tab being LEFT is
        # written before the tab being entered loads, so a tab that is both
        # (there is only one Create Chart, but the order still has to be
        # stated) cannot read what it is about to overwrite.
        self._save_settings_of_tab_left()
        self._load_settings_of_tab_entered(index)
        # A tab that has just become visible can be measured for the first
        # time, so its log panel settles into whatever room this tab has.
        QTimer.singleShot(0, self._refit_log_panes)
        # #130: keep the shared Profile-run list current (a run may have been
        # created since the bar last populated). Cheap; the picked run/type stay.
        color = TAB_COLORS[index] if index < len(TAB_COLORS) else TAB_COLORS[-1]
        if getattr(self, "_target_bar", None) is not None:
            # Check & Refine works on the measurement file loaded into it, not
            # on this selection, so the bar is shown but locked there (#130,
            # Knut 2026-07-26). Build Profile used to be locked with it and is
            # not any more (Knut, beta.157: *"Unlock the bar on tab 4; leave it
            # locked on Check & Refine. ==> OK do it."*) — you pick the run you
            # are building there, so the bar has to be live.
            self._target_bar.set_locked(index == 4)
            # …but not to Verification, which has no profile to build. Greying
            # the one entry, rather than moving the user off the tab, is his
            # ruling too: it says why, where being thrown out says nothing.
            self._target_bar.set_verification_selectable(index != 3)
            self._target_bar.refresh()
            # Tint the bar's combobox highlight + ⓘ icon to the active tab's accent.
            self._target_bar.set_accent(color)
            self._masthead.reposition_center()


        self._accent_line.setStyleSheet(f"background: {color}; border: none;")
        self._refit_accent_line()

        # The tab's own widget tree (mode buttons, primary button, combos, the
        # tooltip-button icons) is styled here. Split into its own method so it
        # can also run for every tab at construction — see _apply_tab_widget_styling.
        self._apply_tab_widget_styling(index)

        # The shared QTabWidget pane background follows the *current* tab only.
        #
        # CACHED ON THE COMPOSED STRING. Setting a stylesheet re-polishes the
        # whole pane, and startup set this same 182-character string two or three
        # times over (twice always; a third when "restore last tab" is on) for
        # 390 ms of pure repetition. The key is the string itself rather than the
        # tab index, because the colour follows the current tab's accent AND the
        # theme — so it cannot go stale the way an index key would.
        pane_qss = self._compose_pane_qss()
        if pane_qss != getattr(self, "_pane_qss", None):
            self._pane_qss = pane_qss
            self._tabs.setStyleSheet(pane_qss)

        # When a tab is shown, Qt hands the initial focus to its first focusable
        # child. If that's a button (e.g. a mode toggle), the space bar would
        # activate it even though the user never tabbed there — so drop the focus
        # off any button the tab auto-focused (Knut).
        from ui.widgets import defer_clear_button_focus
        defer_clear_button_focus(self)

    def _compose_pane_qss(self) -> str:
        """The QTabWidget pane stylesheet — the SAME for every tab.

        It used to carry the current tab's accent in ``border-top``, which made
        the string different on every tab and cost 256 ms a switch: setting a
        stylesheet on the tab widget re-polishes all five trees, 26,053
        style/font/palette events, every time. Keyed on the string, the cache
        could never hit.

        Dropping the accent changes nothing on screen. The hairline is covered by
        the tab bar — forcing it opaque red over a bright green pane moved 0 of
        7,464,960 pixels, while a 12 px border moved a million, so the rule
        reaches the widget and is simply not visible. What you see under the
        active tab is `_accent_line`, a real child widget.

        THE BORDER STILL HAS TO BE A COLOUR, and it must be the THEME's, not a
        tab's: this sheet cascades into `MeasurementReportDialog`, which is
        parented to the Measure tab, and there its own trend tabs' pane border is
        NOT occluded. Freezing it to tab 0's accent turned that dialog's green
        hairline magenta. The theme colour matches what the same dialog shows
        when it is opened from the Tools menu.

        The rule is not simply deleted: light mode's app-wide sheet borders all
        four sides, so removing ours would put side and bottom borders back.

        Takes NO arguments: both colours come from the theme here, so a caller
        cannot pass a background that disagrees with the border, and a leftover
        positional argument cannot bind silently to the wrong parameter.
        """
        is_light = getattr(self, "_title_bar_mode", "dark") == "light"
        pane_bg = "#ffffff" if is_light else "#181818"
        # MEASURED, not chosen. These are the colours that make
        # MeasurementReportDialog agree with itself: its trend tabs inherit this
        # sheet when the dialog is opened from the Measure tab and do not when it
        # is opened from Tools, so any other value shows a different hairline
        # depending on where the user came from. rgba(0,0,0,0.10) left the two
        # entry points 2,400 px apart at dRGB 42; these give (0,0,0) from both.
        glow = "#d0ccc6" if is_light else "#000000"
        return (
            "\n            QTabWidget#chromiq_main_tabs::pane {\n"
            "                border: none;\n"
            f"                border-top: 1px solid {glow};\n"
            f"                background: {pane_bg};\n"
            "            }\n        "
        )

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
        from ui.styles import TAB_COLORS, combo_popup_qss
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
            # A box that is disabled BECAUSE it is forced on: muted accent, so
            # the tick still reads while the control stays obviously inactive.
            locked_on_bg         = _mix_hex(color, "#eeece8", 0.45)
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
            locked_on_bg         = _mix_hex(color, "#1f1f1f", 0.45)
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
                /* …EXCEPT when the box is disabled BECAUSE it is forced on.
                   The rule above makes a ticked-and-disabled box look
                   identical to an unticked one, which is right for "this whole
                   group is off" and wrong for "this is on and not yours to
                   change": the user then cannot see the mode they are actually
                   in (Basti, 2026-08-28, on the CR30 patch-by-patch lock).
                   #locked_on keeps a muted accent fill so the tick still
                   reads, while staying obviously inactive. */
                QCheckBox#locked_on::indicator:checked:disabled {{
                    background: {locked_on_bg};
                    border-color: {color};
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

        # ---- combobox popup hover highlight, in this tab's accent ---------
        # One shared definition, `ui.styles.combo_popup_qss` — the tool dialogs
        # use the same two rules with their own accent, so a dropdown looks and
        # behaves the same wherever it is opened. See that function for why BOTH
        # rules are needed and why `padding-left: 0px` is not cosmetic.
        _sheet += combo_popup_qss(color)

        # The stylesheet is a pure function of (index, theme); a set stylesheet
        # stays applied and cascades to children added later, so on a revisit for
        # the same theme we can skip the costly re-`setStyleSheet` (~30 ms on the
        # heavy Create Chart tree) without any visual change. ACCENT + the tooltip
        # re-tint below still run every call: ACCENT is a class-global new dialogs
        # read, and the loop covers any tooltip button added since (Knut/perf).
        # KEYED ON THE APPEARANCE, NOT ON `is_light`. The boolean has two
        # values and the app is growing a third appearance: two appearances
        # that both answer `is_light == False` would share one cache entry, and
        # switching between them would be a HIT — skipping the very re-style a
        # theme switch exists to perform.
        from ui.theme import APPEARANCE_DARK, accept_mode
        _mode = accept_mode(getattr(self, "_title_bar_mode", APPEARANCE_DARK))
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
            # The Print tab must judge THIS chart's .ti2 — a gamut-module
            # chart is already converted, and its Colour row forces Raw only
            # if the tab knows which chart it is holding (§3.1a).
            self._tab_print.note_generated_chart(Path(ti2))
            self._tab_measure.set_ti1_path(Path(ti2))
            # A real chart is loaded → clear any "no chart yet" guidance.
            self._tab_print.set_chart_notice(None)
            self._tab_measure.set_chart_notice(None)
        elif not tiff_list:
            # #130: an empty payload means the selected Profile-run / Run-type has
            # no chart yet (e.g. switched to Verification before its chart exists).
            # Drop the previous chart from Measure so the wrong chart can't be
            # printed or measured; Print was already cleared by load_tiffs([]).
            self._tab_measure.clear_chart_file()
            # …and drop the Print tab's chart context with it, so a later
            # chart doesn't inherit the previous one's Colour-row state.
            self._tab_print.note_generated_chart(None)
            # Guide the user in BOTH tabs' preview (Knut): explain there's no
            # chart yet and where to make it — it stays visible on tab switch.
            guidance = self._no_chart_guidance_text()
            self._tab_print.set_chart_notice(guidance)
            self._tab_measure.set_chart_notice(guidance)
        # THE RUN BAR HAS TO BE TOLD THE CHART CHANGED.
        #
        # Building a chart changes whether the stored copy differs from the live
        # one, which is exactly what greys or enables Restore Used Chart — but
        # nothing here re-asked, so the button kept its previous state until
        # some other event happened to refresh the bar. Knut, #130 2026-08-01:
        # *"the 'Restore Used Chart' was still greyed out, but after changing
        # tab to print chart, then it was activated (it should have been active
        # immediately after generate chart was runned)."*
        try:
            self._target_bar.refresh()
        except Exception:      # noqa: BLE001 — never fail a finished build
            log.warning("Could not refresh the run bar after a chart build",
                        exc_info=True)

    def _no_chart_guidance_text(self) -> str:
        """Guidance for the Print/Measure preview when the selected Profile-run /
        Run-type has no chart yet (#130, Knut) — tailored to Profiling vs
        Verification, and pointing at the Create Chart tab."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is not None and ctl.target.is_verification():
            return tr(
                "No verification chart for this run yet.\n\n"
                "Create it in the Create Chart tab with “Run type” = "
                "“Verification”, print it through this run's finished profile, "
                "then come back here to measure it.")
        return tr(
            "No chart for this profile run yet.\n\n"
            "Create it in the Create Chart tab, then print it and measure it "
            "here.")

    def _on_measure_done(self, ti3: Path) -> None:
        cal_mode = bool(self._settings.get("calibration_mode", False))
        # A calibration measurement lives in the project's cal/ folder rather
        # than carrying a cal_ filename prefix.
        if cal_mode and ti3.parent.name == "cal":
            # Hand the measurement over, but DO NOT change tab.
            #
            # This fired for every calibration measurement that produced a
            # .ti3 — including one the user stopped after a single patch — so
            # pressing Stop threw them onto another tab. Knut, beta.150:
            # *"Then the tab changes from measure tab to Calibration &
            # Profiling tab automatically. This shall not happen. Finishing /
            # stopping a measurement shall not do this automatically."*
            # Going to tab 4 is the completion window's button to offer, and it
            # arrives here through `proceed_to_profile` like every other run.
            self._tab_profile.set_cal_ti3_path(ti3)
        else:
            self._tab_profile.set_ti3_path(ti3, propagate=False)
            # Forward the Measure-tab opt-in so Build Profile can merge the
            # pre-conditioning data (ChromIQ-style refinement). None when off.
            self._tab_profile.set_preconditioning_source(
                self._tab_measure.preconditioning_choice()
            )

    def _lock_other_tabs(self, active: bool, keep_idx: int, why: str, *,
                         reason: str) -> None:
        """Grey every tab but ``keep_idx`` — and say WHY on each greyed one.

        Basti, #164 Q6: the Build Profile tab was already greyed for the
        duration of a measurement, but silently: hovering a dead tab told you
        nothing, so it read as a bug rather than a lock. Option (b) — *"greyed
        with a note saying why"* — is what this adds, and a build gets the same
        courtesy (Q7: *"should be locked the same way"*).

        LOCKS ARE COUNTED, NOT BOOLEAN. Two things can hold the tabs at once —
        the ChromIQ profile engine builds in a QThread of its own
        (`workflow/engine_builder.py`), outside the single ArgyllRunner that
        otherwise serialises everything, so a measurement and a build are not
        mutually exclusive by construction. With a plain on/off flag, whichever
        finished FIRST unlocked everything: driven, ending a build while a
        measurement was still running left every tab live and the profile tab
        wearing the stale measurement tooltip. `_apply_profile_tab_gate` cannot
        repair that — it early-returns on both flags. So each holder is named,
        and the tabs come back only when the last one lets go.

        Each tab's own tooltip is put back then, so the verification gate's
        explanation on tab 4 survives a measurement.
        """
        held = getattr(self, "_tab_lock_reasons", None)
        if held is None:
            held = self._tab_lock_reasons = {}

        if active:
            # Save the real tooltips once, before the FIRST holder overwrites
            # them — otherwise the second holder would save our own "why" text
            # as if it were the tab's own, and the note would stick for good.
            if not held:
                self._tab_tips_before_lock = {
                    i: self._tabs.tabToolTip(i) for i in range(self._tabs.count())
                }
            held[reason] = (keep_idx, why)
        else:
            held.pop(reason, None)

        if held:
            # Still locked by someone. The tab a holder is working IN stays
            # live only while it is the sole holder — two holders means no tab
            # is safe to walk into.
            keeps = {k for k, _w in held.values()}
            # With two holders there is no single "working" tab, so keep the
            # one the user is STANDING IN. Disabling every tab also disabled
            # the Measure page — and Stop lives on it, so the only control that
            # could end a running measurement became unreachable while the
            # tooltip said "wait for them to finish", which a measurement does
            # not do on its own.
            # EVERY holder's tab stays usable, not just one. Picking a single
            # tab made the result depend on which lock arrived FIRST:
            # build-then-measurement left the Measure page disabled, and Stop
            # lives on it, so the only control that could end the measurement
            # was unreachable while the tooltip said "wait for them to finish".
            keeps.discard(None)
            why_now = next(iter(held.values()))[1] if len(held) == 1 else tr(
                "Not while a measurement and a profile build are both "
                "running.\n\nWait for them to finish — this tab comes back as "
                "soon as the last one is done.")
            for i in range(self._tabs.count()):
                if i not in keeps:
                    self._tabs.setTabEnabled(i, False)
                    self._tabs.setTabToolTip(i, why_now)
                else:
                    self._tabs.setTabEnabled(i, True)
            return

        saved = getattr(self, "_tab_tips_before_lock", None)
        if saved is None:
            # An unlock with no matching lock — nothing was ever saved, so
            # there is nothing to restore. Writing "" over every tab here would
            # silently wipe tooltips this method never set.
            for i in range(self._tabs.count()):
                self._tabs.setTabEnabled(i, True)
            return
        for i in range(self._tabs.count()):
            self._tabs.setTabEnabled(i, True)
            self._tabs.setTabToolTip(i, saved.get(i, ""))
        self._tab_tips_before_lock = None

    def _on_measurement_active(self, active: bool) -> None:
        # Recorded BEFORE anything downstream reacts: `_apply_profile_tab_gate`
        # runs from the signals below and re-enables the Build Profile tab three
        # lines after this method disables it, so it has to be able to see that
        # a measurement is running. Measured before the fix: idle → enabled,
        # measuring → still enabled.
        self._measuring = bool(active)
        measure_idx = self._tabs.indexOf(self._tab_measure)
        self._lock_other_tabs(active, measure_idx, reason="measuring", why=tr(
            "Not while a measurement is running.\n\n"
            "The instrument is reading patches into this run right now, and "
            "every one of these tabs can change what it is reading into — the "
            "chart, the settings, or the profile it will build.\n\n"
            "This tab comes back the moment the measurement finishes, whether "
            "you let it run to the end or stop it early."))
        # Chart-changing controls on the shared bar go quiet for the duration
        # (#130, Knut): Restore Used Chart must not swap the chart out from
        # under a running measurement.
        ctl = getattr(self, "_target_ctl", None)
        if ctl is not None:
            ctl.set_measuring(active)
        # …and so do the masthead's Load buttons. Load .ti2 always had this
        # guard on the Measure tab; Load Project never did, and Knut asked for
        # it when he accepted the move (#130, 2026-07-31): *"Remember that also
        # the Load Project icon should be Disabled while a measurement runs."*
        # Tools and Preferences go with them: both open windows that can change
        # what the app is working on. Help stays live — Knut, beta.120: *"Help
        # button can be active still."*
        self._refresh_masthead_availability()
        if not active:
            # …and the verification gate has its say again. It DOES already get
            # one via `ctl.set_measuring` above, but only by signal ordering —
            # say it outright so tab 4 cannot come back live on a verification
            # run if that ordering ever changes.
            self._apply_profile_tab_gate()

    def _on_chart_build_started(self) -> None:
        """Create Chart says a build is in flight. Not a lock yet — no process
        exists at this point, and some paths emit this and run no tool at all
        (a preset copy, an editor apply)."""
        self._chart_building = True

    def _on_a_tool_started(self) -> None:
        """A tool actually began. Lock if a chart build is in flight.

        The intent is NOT consumed here. A Manual chart is TWO runs — targen
        then printtarg (`workflow/chart_creator.py`) — and consuming it on the
        first meant printtarg never re-locked: measured at 50 ms intervals
        through a real build, the masthead was greyed for all 19 samples of
        targen and 0 of the 8 samples of printtarg. printtarg is the phase that
        writes the .ti2 and the printable pages into the run folder, which is
        exactly what the lock is for, and Close Project was a live dead click
        again for its whole duration.
        """
        if getattr(self, "_chart_building", False):
            self._chart_locked = True
            self._stop_chart_lock_watchdog()
            self._refresh_masthead_availability()

    def _on_a_tool_finished(self) -> None:
        """A tool ended. Hold the lock if the chart build has more to run.

        Between targen finishing and printtarg starting the runner is briefly
        idle; releasing there is the hole above. `chart_finished` is what really
        ends a build, so the lock waits for it — with a watchdog underneath, so
        a build that ends without that signal cannot leave the window greyed.
        """
        if getattr(self, "_chart_building", False):
            self._start_chart_lock_watchdog()
            return
        self._chart_locked = False
        self._refresh_masthead_availability()

    def _start_chart_lock_watchdog(self) -> None:
        """Release the lock if no further tool starts within a grace period."""
        from PyQt6.QtCore import QTimer

        wd = getattr(self, "_chart_lock_watchdog", None)
        if wd is None:
            wd = self._chart_lock_watchdog = QTimer(self)
            wd.setSingleShot(True)
            wd.timeout.connect(self._on_chart_lock_watchdog)
        wd.start(self._CHART_LOCK_GRACE_MS)

    def _stop_chart_lock_watchdog(self) -> None:
        wd = getattr(self, "_chart_lock_watchdog", None)
        if wd is not None and wd.isActive():
            wd.stop()

    def _on_chart_lock_watchdog(self) -> None:
        """No follow-on tool arrived and nothing is running — let go."""
        try:
            still_running = bool(self._runner.is_running)
        except Exception:      # noqa: BLE001
            still_running = False
        if still_running:
            self._start_chart_lock_watchdog()
            return
        if not getattr(self, "_chart_locked", False):
            # Announced, but no tool ever started — just drop the intent.
            self._chart_building = False
            return
        log.info("Chart-build lock released by watchdog — no chart_finished "
                 "arrived after the last tool ended")
        self._on_chart_build_finished()

    def _on_chart_build_finished(self) -> None:
        self._stop_chart_lock_watchdog()
        self._chart_building = False
        self._chart_locked = False
        self._refresh_masthead_availability()

    def _refresh_masthead_availability(self) -> None:
        """Recompute what the masthead offers — from ONE place.

        Called from every transition that can change it: a measurement
        starting or ending, a profile build starting or ending, and a project
        opening or closing. Nothing else may enable or disable those buttons,
        or they drift apart the way the Build Profile tab did (#164).
        """
        busy = None
        if getattr(self, "_measuring", False):
            busy = self._masthead.BUSY_MEASURING
        elif getattr(self, "_profile_building", False):
            busy = self._masthead.BUSY_BUILDING
        elif getattr(self, "_chart_locked", False):
            # A CHART BUILD LOCKS TOO. Only colprof and chartread had their own
            # flags, so during targen/printtarg the user could switch project,
            # open another chart or open Tools mid-build — the "build in flight
            # vs the run's stored Create Chart state" shape that has been
            # clobbered twice — and Close Project LOOKED live while doing
            # nothing (its own guard returned silently). The flag is latched
            # by `ArgyllRunner.started` and released by `chart_finished`, with
            # a watchdog underneath so it cannot be left stuck on.
            busy = self._masthead.BUSY_CHART
        self._masthead.set_availability(busy, self._file_mgr.is_named())
        # …AND THE TARGET BAR, from the same three flags and the same one place.
        # It used to lock for a measurement only, so during a chart or profile
        # build Delete, Duplicate, the run picker and Restore Used Chart all
        # stayed live on the run being written to. Restore Used Chart is the
        # sharpest of them: it replaces the very .ti2 that colprof is reading
        # its measurement against.
        bar = getattr(self, "_target_bar", None)
        if bar is not None and hasattr(bar, "set_build_running"):
            bar.set_build_running(bool(
                getattr(self, "_profile_building", False)
                or getattr(self, "_chart_locked", False)
                or getattr(self, "_chart_building", False)))

    def _refresh_project_hint(self) -> None:
        """Re-ask the Create Chart tab whether its name still names another
        project. Best-effort: a hint must never break a project switch."""
        try:
            self._tab_chart._refresh_project_exists_line()
        except Exception:      # noqa: BLE001
            log.debug("could not refresh the project hint", exc_info=True)

    def _on_verify_chart_restored(self) -> None:
        """React to Restore Used Chart having put an older verification chart
        back (#130, Knut).

        When the snapshot carried no page images — the normal case, because the
        chart's layout recipe can redraw them — the pages are rebuilt here, and
        the finished build feeds the preview and the other tabs by the usual
        route. Otherwise the images came back with the snapshot and only a
        refresh is needed, so nothing is rebuilt needlessly."""
        outcome = getattr(self._target_ctl, "_last_restore", None)
        rebuilt = False
        if outcome is not None and outcome.should_rebuild:
            try:
                rebuilt = self._tab_chart.rebuild_verification_pages()
            except Exception:      # noqa: BLE001
                log.warning("Could not rebuild the restored pages", exc_info=True)
        if not rebuilt:
            try:
                self._tab_chart._on_target_changed()
            except Exception:      # noqa: BLE001 — never crash on a refresh
                log.warning("Could not refresh the tabs after a chart restore",
                            exc_info=True)
        if getattr(self, "_target_bar", None) is not None:
            self._target_bar.refresh()
        self._note_archived_measurement_after_restore()

    def _note_archived_measurement_after_restore(self) -> None:
        """Say so when the restored chart's measurement is sitting in ``old/``.

        Knut, #130 2026-07-30, and his ruling on how to handle it. His sequence:
        measure a row, stop, change the chart options, **Generate Chart** — which
        archives the measurement into ``old/<date>/`` because a new chart no
        longer describes those readings — then Restore Used Chart. The chart comes
        back correctly, but the Measure tab then offers neither "Refine / resume"
        nor "Show overlay", and he read that as the tab failing to update.

        It was not: the measurement really is gone from the run, and the tab was
        telling the truth. What was missing is any word about WHERE it went. So
        this says it, and names the folder. Nothing is moved back — he chose
        option 1 deliberately, so that readings he displaced are never
        resurrected behind his back.
        """
        try:
            ctl = getattr(self, "_target_ctl", None)
            proj = ctl.project_or_none() if ctl is not None else None
            run_id = ctl.target.profile_run if ctl is not None else ""
            if proj is None or not run_id or not proj.has_run(run_id):
                return
            run = proj.run(run_id)
            if run.measurement_ti3.exists() or not run.old_dir.is_dir():
                return          # nothing missing, or nothing archived
            archived = sorted(
                (d for d in run.old_dir.iterdir()
                 if d.is_dir() and any(p.suffix == ".ti3" for p in d.iterdir())),
                key=lambda d: d.name)
            if not archived:
                return
            newest = archived[-1]
            self._tab_chart._log.appendPlainText(tr(
                "The chart is back exactly as it was measured — but this run's "
                "measurement is not here any more: it was moved to “old/{folder}” "
                "when a new chart was generated over it, because a new chart no "
                "longer describes those readings.\n\nThat is why Measure offers "
                "no “Refine / resume” or “Show overlay” for this run. Your "
                "readings are safe in that folder; copy the .ti3 back beside the "
                "chart if you want to carry on from them, or simply measure the "
                "restored chart again."
                ).format(folder=newest.name))
        except Exception:      # noqa: BLE001 — a note must never break a restore
            log.warning("Could not check for an archived measurement",
                        exc_info=True)

    def _on_project_deleted(self) -> None:
        """The project was deleted — return the app to its starting state."""
        self._reset_after_project_gone(deleted=True)

    def _reset_after_project_gone(self, *, deleted: bool) -> None:
        """Return the whole app to its starting state (#130, Knut 2026-07-29).

        Shared by DELETING a project and CLOSING one (#164). The two must land
        in the same place — an app with two different "no project" states is
        one the user cannot predict — so they differ only in what they say
        afterwards, and in the settings flush the caller does first.

        *"After deletion of the whole project I was working in, the user
        interface must return to the starting state of the app, empty and no
        loaded project. It must not create another project that I did not ask
        for."*

        Both halves matter. Emptying the tabs is the visible half; forgetting the
        NAME is the half that stops the folder being created again, because
        anything that asks for "the project" makes it — which is how switching to
        the Print Chart tab resurrected a deleted project under its old name.

        The order is deliberate: the name goes first, so nothing that runs
        afterwards can still resolve a project, and the remembered session is
        cleared last, so a failure in between cannot leave the app reopening a
        folder that is gone.
        """
        # 1. No project is named any more — exactly as at launch.
        self._file_mgr.close_project()
        # 2. No run, no run type, no verification date is selected any more.
        self._target_ctl.reset_to_empty()
        # 3. Every tab lets go of what it was showing.
        try:
            self._tab_chart.clear_loaded_project()
        except Exception:      # noqa: BLE001 — a delete must never end in a crash
            log.warning("Could not clear the Create Chart tab", exc_info=True)
        self._tab_print.load_tiffs([])
        self._tab_measure.clear_chart_file()
        self._tab_profile.clear_files()
        self._tab_check.clear_files()
        guidance = self._no_chart_guidance_text()
        self._tab_print.set_chart_notice(guidance)
        self._tab_measure.set_chart_notice(guidance)
        # 4. The bar redraws itself against an empty disk.
        try:
            self._target_bar.refresh()
        except Exception:      # noqa: BLE001
            log.warning("Could not refresh the bar after the project was %s",
                        "deleted" if deleted else "closed", exc_info=True)
        # 4b. The masthead now has nothing to close.
        self._refresh_masthead_availability()
        # 5. Nothing about the project is remembered for next launch.
        for key in ("session_target_name", "session_project_root",
                    "session_ti1_path", "session_ti3_path", "session_icc_path",
                    "session_cal_ti3_path"):
            self._settings.set(key, "")
        # 6. And we are standing where a new project begins. (The statusbar line
        #    is left alone on purpose — it carries the ArgyllCMS warning, which
        #    must not be pushed aside by a message about something else. The
        #    Create Chart log and both empty previews say what happened.)
        self._tabs.setCurrentWidget(self._tab_chart)
        # Say which it was. Telling a user who merely CLOSED their project
        # that it was deleted is the worst thing this feature could do (#164).
        log.info("Project %s: the app is back in its starting state",
                 "deleted" if deleted else "closed")

    def _on_masthead_load_project(self) -> None:
        """Open an existing project — the button moved out of Create Chart."""
        btn = getattr(self._masthead, "_load_project_btn", None)
        if btn is not None and not btn.isEnabled():
            return          # the shortcut obeys the button's lock
        self._tabs.setCurrentWidget(self._tab_chart)
        self._tab_chart._load_existing_profile()
        # Whether or not the bar happened to change, a project may now be open.
        self._refresh_masthead_availability()

    def _on_masthead_close_project(self) -> None:
        """Put ChromIQ back to its starting state, without touching a file.

        Basti, #164: *"add that button … when one is opened ask for
        confirmation in a pop up window"*. Nothing on disk changes — every run,
        chart, measurement and profile stays exactly where it is — so the
        confirmation's job is to say what IS lost (what you typed but have not
        used yet), not to warn about a deletion that is not happening.
        """
        from PyQt6.QtWidgets import QMessageBox

        if not self._file_mgr.is_named():
            return                                # the button is greyed anyway
        if self._runner.is_running:
            return                                # so is this, but belt and braces

        box = QMessageBox(self)
        # No question-mark glyph (Basti, #164) — the heading already asks the
        # question, and the icon only pushed the text into a narrow column.
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("Close this project?"))
        box.setText(tr("Close this project?"))
        box.setInformativeText(tr(
            "Nothing is deleted. Every run, chart, measurement and profile "
            "stays exactly where it is on disk, and “Open Project” brings it "
            "all back whenever you want it.\n\n"
            "What you have typed but not yet used is not kept: the name in "
            "“Printer profile project name” and the run description beside "
            "it. The Create Chart settings go back to your saved defaults, or "
            "to ChromIQ's own if you have not saved any.\n\n"
            "ChromIQ then looks the way it does on a fresh install, with no "
            "project open."))
        close_btn = box.addButton(tr("Close project"),
                                  QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(box.buttons()[-1])   # Cancel is the safe default
        try:
            from ui.widgets import (accent_message_box_button,
                                    fit_message_box_buttons)
            # ACCENT FIRST, THEN FIT. The accent stylesheet adds
            # `padding: 6px 14px`; applying it after the width was fitted left
            # the button too narrow for its own label. Measured offscreen in
            # German: fitted to 139 px, needed 160 px for "PROJEKT SCHLIESSEN".
            accent_message_box_button(close_btn)
            fit_message_box_buttons(box)
        except Exception:      # noqa: BLE001 — a narrow button is not fatal
            pass
        box.exec()
        if box.clickedButton() is not close_btn:
            return
        self.close_current_project()

    def close_current_project(self) -> None:
        """The close itself — the same reset a delete does, minus the delete.

        Shares `_reset_after_project_gone` with `_on_project_deleted` so the
        two cannot drift: an app with two different "no project" states is one
        the user cannot predict.
        """
        # WRITE THE OUTGOING TARGET'S SETTINGS FIRST. Moving the selection to
        # nothing is still moving it, and per-target settings are recorded when
        # a target is left (per_target_settings.md §2.1/N1). A delete does not
        # need this — the target is going away — but a close must, or the last
        # edit before closing is silently lost.
        # EVERY tab, not a hand-written list. The list said chart/measure/
        # profile and silently omitted Print, so a Rendering-intent change made
        # on the Print Chart tab was lost by Close Project — driven: close from
        # the Print tab stored {}, switching tab first stored the real value.
        # The tab switch at the end of `_reset_after_project_gone` cannot save
        # it either, because `close_project()` has run by then and
        # `store_for_target` returns None. Walking the widgets means a fifth tab
        # is covered the day it is added.
        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            saver = getattr(tab, "save_target_settings", None)
            if callable(saver):
                try:
                    saver()
                except Exception:      # noqa: BLE001
                    log.warning("could not record settings before closing",
                                exc_info=True)
        self._reset_after_project_gone(deleted=False)

    def _on_masthead_load_ti2(self) -> None:
        """Open a chart file — ONE button where Print and Measure each had one.

        Knut's spec (#130, 2026-07-31) settles which of the two routes survives:
        the Measure one. Its ``set_ti1_path`` drives the preview, the resume
        tick and the overlay offer, where Print's only recorded the path — so
        taking Print's would have quietly dropped all three.

        Print's own contribution is kept: it is the tab that tells you when a
        .ti2 has no page images beside it, and that message is worth having.
        """
        btn = getattr(self._masthead, "_load_ti2_btn", None)
        if btn is not None and not btn.isEnabled():
            return          # the shortcut obeys the button's lock
        before = getattr(self._tab_measure, "_ti1_path", None)
        self._tab_measure._on_load_ti2()
        loaded = getattr(self._tab_measure, "_ti1_path", None)
        if loaded is None or loaded == before:
            return                       # cancelled, or nothing changed
        # Every tab shows the chart that was just opened, and Create Chart is
        # the one brought to the front — the tabs are numbered in workflow
        # order, so that is where a freshly opened chart is looked at first.
        if not self._tab_print.has_pages():
            self._tab_print.set_chart_notice(tr(
                "No TIFF files found matching the selected .ti2 file.\n\n"
                "The chart's pages live beside it as “{stem}_01.tif” and so on. "
                "If they were moved or renamed, put them back next to the .ti2 "
                "— or open the chart again from the project it belongs to."
            ).format(stem=Path(loaded).stem))
        # DO NOT MOVE SOMEONE WHO IS ALREADY WHERE THE CHART IS USED.
        #
        # This used to navigate to Create Chart unconditionally, on the reasoning
        # that the tabs run in workflow order so a freshly opened chart is looked
        # at there first. That holds when the chart arrives from somewhere with
        # nothing to do with it — but the masthead is the ONLY way to load a
        # chart, so a user standing on Measure, about to measure, was thrown back
        # to tab 1 every time (Basti, 2026-08-08). It also sat badly beside a rule
        # this model has already corrected twice: ending a measurement, and
        # stopping a calibration, must not change tab by themselves (K18).
        #
        # Measure and Print both show the loaded chart, so being on either is
        # already the right place to be.
        if self._tabs.currentWidget() not in (self._tab_measure, self._tab_print):
            self._tabs.setCurrentWidget(self._tab_chart)
        self._target_bar.refresh()

    def _on_run_duplicated(self, run_id: str) -> None:
        """Show the run the Duplicate button just made (#130, "course B").

        Knut's point 6: *"After duplicating the Profile run should switch to the
        new run. Create Chart tab shows its chart is good."* The controller has
        already selected it; what is left is to put its chart in front of the
        user on all three tabs, so the copy is visibly the thing being worked on
        rather than an entry in a dropdown.
        """
        try:
            proj = self._target_ctl.project_or_none()
            if proj is None or not proj.has_run(run_id):
                return
            run = proj.run(run_id)
            tiffs = run.chart_tiffs()
            if not run.chart_ti2.exists() or not tiffs:
                return              # nothing to show; the copy is still real
            source_id = (run.load_meta().duplicated_from or "")
            # The generic "a loaded chart now shows here" notice is wrong for a
            # duplicate — it reassures about a project you never left. Suppress
            # it and say something true instead (Knut, #130 2026-08-01).
            self._tab_chart._suppress_reflect_notice = True
            try:
                self._tab_chart.reflect_loaded_chart(run.chart_ti2, tiffs)
            finally:
                self._tab_chart._suppress_reflect_notice = False
            self._tab_print.load_tiffs(tiffs)
            self._tab_print.note_generated_chart(run.chart_ti2)
            self._tab_measure.set_ti1_path(run.chart_ti2)
            self._tabs.setCurrentWidget(self._tab_chart)
            # A DUPLICATE IS A PROFILING RUN.
            #
            # Knut, #130 2026-08-01: *"After duplicate is complete and Create
            # Chart opens and loads chart etc, the 'Run type' must start in
            # 'Profiling', not in Verification."* Reasserted after the tabs have
            # loaded, because showing the chart runs through paths that can put
            # the bar back to whatever it was before.
            self._target_ctl.set_run_type(RUN_TYPE_PROFILING)
            self._target_bar.refresh()
            self._tab_chart.announce_duplicated_run(
                run.chart_ti2,
                self._target_bar._run_phrase(run_id),
                self._target_bar._run_phrase(source_id) if source_id
                else tr("the run it was copied from"))
        except Exception:      # noqa: BLE001 — the copy is made; never crash now
            log.warning("Could not show the duplicated run %s", run_id,
                        exc_info=True)

    def _save_settings_of_visible_tab(self) -> None:
        """Flush the tab on screen without forgetting that it is on screen.

        `_save_settings_of_tab_left` clears the "which tab is showing" note,
        because a tab that has been left is no longer showing. Here the user has
        merely opened a pulldown — the tab stays where it is, and clearing the
        note would mean the next real tab change wrote nothing.
        """
        tab = getattr(self, "_settings_tab_showing", None)
        if tab is None:
            return
        try:
            tab.save_target_settings()
        except Exception:      # noqa: BLE001 — never break a pulldown
            log.warning("Could not flush the tab before a target change",
                        exc_info=True)

    def _load_settings_of_visible_tab(self) -> None:
        """§2 L3/L4 — the visible tab loads the target just selected.

        The write against the OUTGOING target already happened when the
        pulldown opened (`about_to_change_target` → the Q-1 trigger), so by
        the time `changed` fires the values on screen may be reloaded safely.
        Create Chart also reloads through its own `_on_target_changed`; its
        loader is guarded and idempotent, so the double call is harmless and
        keeping one central path for every tab is what Knut asked for.
        """
        tab = self._tabs.currentWidget()
        if not hasattr(tab, "load_target_settings"):
            return
        self._settings_tab_showing = tab
        try:
            tab.load_target_settings()
        except Exception:      # noqa: BLE001 — never break a selection change
            log.warning("Could not reload the visible tab after a target "
                        "change", exc_info=True)

    def _save_settings_of_tab_left(self) -> None:
        """§3 W6 — the tab the user has just left records its settings."""
        left = getattr(self, "_settings_tab_showing", None)
        self._settings_tab_showing = None
        if left is None:
            return
        try:
            left.save_target_settings()
        except Exception:      # noqa: BLE001 — never break a tab change
            log.warning("Could not save the settings of the tab being left",
                        exc_info=True)

    def _load_settings_of_tab_entered(self, index: int) -> None:
        """§2 L1 — the tab being shown loads the selected target's settings."""
        widget = self._tabs.widget(index)
        if not hasattr(widget, "load_target_settings"):
            return
        self._settings_tab_showing = widget
        try:
            widget.load_target_settings()
        except Exception:      # noqa: BLE001
            log.warning("Could not load the settings of the tab being shown",
                        exc_info=True)

    def _apply_profile_tab_gate(self) -> None:
        """Tab 4 is unavailable while the selection is a Verification.

        Knut's matrix (#130, beta.156 correction — it also settles the open
        question on #133):

        ==========================  ===============================================
        Run type                    tab 4
        ==========================  ===============================================
        Profiling                   shown — colprof, and applycal with calibration on
        **Verification**            **greyed and locked, with a tooltip saying why**
        Calibration                 shown — printcal (calibration options only)
        ==========================  ===============================================

        A verification measures an existing profile; it never builds one. The
        tab used to be fully live there, so every control in it pointed at a
        run whose profile it could only overwrite.
        """
        idx = self._tabs.indexOf(self._tab_profile)
        if idx < 0:
            return
        try:
            is_verification = bool(self._target_ctl.target.is_verification())
        except Exception:      # noqa: BLE001 — a tab gate is never worth a crash
            return
        # Never fight the "a profile is building" lock, which disables
        # everything else and must win while it is on.
        if getattr(self, "_profile_building", False):
            return
        if getattr(self, "_measuring", False):
            # A measurement owns the tabs for its duration — re-enabling Build
            # Profile here would undo `_on_measurement_active` and let the user
            # walk into a build mid-read.
            return
        self._tabs.setTabEnabled(idx, not is_verification)
        self._tabs.setTabToolTip(idx, "" if not is_verification else tr(
            "Not for a verification run.\n\n"
            "A verification measures the profile this run already has — it "
            "checks how the profile is doing, and it never builds one. "
            "Building here would overwrite the very profile you are checking.\n\n"
            "To build or rebuild a profile, set “Run type” back to "
            "“Profiling” in the bar above."))
        # If the user is standing on it when it closes, move them somewhere
        # that makes sense rather than leaving a disabled tab on screen.
        if is_verification and self._tabs.currentIndex() == idx:
            self._tabs.setCurrentWidget(self._tab_measure)

    def _on_profile_active(self, active: bool) -> None:
        profile_idx = self._tabs.indexOf(self._tab_profile)
        self._profile_building = bool(active)
        self._lock_other_tabs(active, profile_idx, reason="building", why=tr(
            "Not while a profile is being built.\n\n"
            "colprof is writing the ICC profile into this run right now. "
            "These tabs all feed that build — changing one mid-way would "
            "leave the finished profile disagreeing with what is on screen.\n\n"
            "This tab comes back as soon as the build finishes."))
        # A BUILD LOCKS THE MASTHEAD THE SAME WAY A MEASUREMENT DOES.
        # Basti, #164: *"should be locked the same way"*. Open Project, Open
        # Chart File and Tools all open windows that change what the app is
        # working on, and colprof is writing into the loaded run.
        self._refresh_masthead_availability()
        if not active:
            # …and the verification gate has its say again.
            self._apply_profile_tab_gate()

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
        """Show the speech-bubble Tools popup under the masthead's Tools button.

        THE SHORTCUT MUST OBEY THE SAME LOCK AS THE BUTTON. ⌘T reached this
        directly, so during a measurement the Tools button was greyed and ⌘T
        opened the menu anyway — every tool one keystroke away from a running
        read (#164). A shortcut that bypasses the guard its own button honours
        is worse than no guard at all, because the greyed button says the app
        is protected.
        """
        from ui.tools_popup import ToolsPopup

        btn = self._masthead.tools_button()
        if btn is not None and not btn.isEnabled():
            return

        popup = ToolsPopup(self)
        popup.set_appearance(self._title_bar_mode)
        popup.selected.connect(self._launch_tool)
        popup.show_under(self._masthead.tools_button())

    def _run_cr30_bluetooth_report(self) -> None:
        """Write a Bluetooth diagnostic the user can send us.

        IN THE APP, NOT IN A SCRIPT. `bleak` and its platform backend live
        inside the bundle, where a system Python cannot reach them — so asking
        someone with a connection problem to install Python and pip a library
        is both a wall and a different test: it would exercise a bleak that is
        not the one failing. This runs the app's own stack.
        """
        from pathlib import Path
        from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from ui.widgets import fit_message_box_buttons

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("CR30 Bluetooth report"))
        box.setText(tr("Find out why the instrument will not connect"))
        box.setInformativeText(tr(
            "ChromIQ will look for Bluetooth instruments for about half a "
            "minute and write down what it finds, so somebody can see where "
            "the connection stops.\n\n"
            "Switch your CR30 on and leave it awake — press its button once if "
            "you are not sure — and keep it near this computer. There is no "
            "Bluetooth setting to turn on: a CR30 has none, and is on from the "
            "moment it comes out of the box.\n\n"
            "Watch the instrument's own screen while this runs. An indicator "
            "appears there when a computer asks to connect, so the display "
            "tells you whether the request is arriving at all.\n\n"
            "Nothing here can change your instrument. It is never asked to "
            "measure and never asked to calibrate.\n\n"
            "To tell your instrument apart from other Bluetooth gadgets, "
            "ChromIQ briefly contacts anything nearby that offers the same "
            "kind of connection and asks what it is — the same question it "
            "asks whenever you measure over Bluetooth.\n\n"
            "The window will be unresponsive while it looks."),
            )
        go = box.addButton(tr("Look now"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(go)
        fit_message_box_buttons(box)
        box.exec()
        if box.clickedButton() is not go:
            return

        # ASK FOR THE SERIAL, OPTIONALLY. It is NOT used to find the
        # instrument -- searching goes by service and then by protocol, so it
        # works on a unit nobody has seen. It is used to catch the one case
        # searching cannot: a device that advertises its NAME but not the
        # service, which ChromIQ skips and this report would otherwise hide
        # behind the redaction. Then the instrument is sitting in the list and
        # nobody can tell.
        from PyQt6.QtWidgets import QInputDialog
        serial, _ok = QInputDialog.getText(
            self, tr("CR30 Bluetooth report"),
            tr("If you know your instrument's serial number, type it here.\n\n"
               "The manufacturer's own software shows it under Instrument "
               "settings, and it may be printed on the instrument itself. It "
               "is optional — leave it empty and the report still works.\n\n"
               "ChromIQ does not use it to search. It uses it to spot your "
               "instrument in the list even if it is not announcing itself "
               "the way ChromIQ expects, which is one of the things that can "
               "go wrong."))
        serial = (serial or "").strip()

        # ON A WORKER THREAD, AND NOT ONLY TO KEEP THE WINDOW ALIVE.
        #
        # On Windows this MUST leave the GUI thread. Qt's Windows platform
        # plugin calls OleInitialize, which makes that thread a single-threaded
        # apartment; bleak's WinRT scanner asserts it is in a multi-threaded
        # apartment and raises "Thread is configured for Windows GUI but
        # callbacks are not working" within about half a second. So the tool
        # written for a Windows user who cannot connect would have failed
        # instantly ON WINDOWS, and its own text would then have told him to
        # check whether Bluetooth was switched on.
        #
        # It is also why this is not the same code path as his original fault:
        # the Measure tab's Bluetooth already runs on the reader's worker
        # thread, which is free of that apartment.
        import asyncio
        import threading
        from PyQt6.QtCore import QEventLoop

        result: dict = {}

        def _work() -> None:
            try:
                from workflow.cr30.bluetooth_report import collect
                loop = asyncio.new_event_loop()
                try:
                    rep = loop.run_until_complete(collect(serial=serial))
                finally:
                    loop.close()          # one leaked loop per run otherwise
                result["text"] = rep.text
                result["confirmed"] = rep.confirmed
            except Exception as exc:                # noqa: BLE001 — report it
                result["text"] = (f"The report could not be produced: "
                                  f"{type(exc).__name__}: {exc}")
                log.warning("CR30 Bluetooth report failed", exc_info=True)

        worker = threading.Thread(target=_work, daemon=True,
                                  name="cr30-bluetooth-report")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        worker.start()
        try:
            while worker.is_alive():
                # EXCLUDE USER INPUT. With AllEvents the window went on
                # accepting clicks while the dialog said it would not: a tab
                # switch landed mid-scan with Start Measurement live, a second
                # report could be nested inside the first, and closing the
                # window ran the whole quit teardown and then put dialogs up
                # over a quitting app — with an accepted repair written after
                # the settings had already been flushed, and lost.
                QApplication.processEvents(
                    QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, 50)
                worker.join(0.05)
        finally:
            QApplication.restoreOverrideCursor()
        text = result.get("text", "The report produced nothing.")

        suggested = str(Path.home() / "Desktop" / "cr30-bluetooth-report.txt")
        # NOT `QFileDialog.getSaveFileName`. A static convenience call builds,
        # execs and destroys the dialog inside Qt, so there is no object to
        # install `NameOrderProxy` on and this one dialog listed names in a
        # different order from every other. It also ignored the user's
        # native-dialogs preference, got no sidebar shortcuts, and skipped the
        # start-path checks `save_file_dialog` grew after the PosixPath crash.
        # There is no static `QFileDialog.get*` left in app code; keep it that
        # way (Basti, 2026-09-02).
        from ui.widgets import save_file_dialog
        path = save_file_dialog(
            self, tr("Save the Bluetooth report"),
            tr("Text files (*.txt)"), suggested)
        if not path:
            # DO NOT THROW THE REPORT AWAY. It took half a minute of the user's
            # time and a scan they may not be able to repeat (the instrument
            # has to be awake and unclaimed). A mis-clicked Cancel used to lose
            # all of it silently.
            path = suggested
            log.info("CR30 Bluetooth report: save cancelled; keeping it at %s",
                     path)
        try:
            Path(path).write_text(text, encoding="utf-8")
        except Exception as exc:                    # noqa: BLE001
            QMessageBox.warning(self, tr("CR30 Bluetooth report"),
                                tr("The report could not be saved: {error}"
                                   ).format(error=exc))
            return
        done = QMessageBox(self)
        done.setIcon(QMessageBox.Icon.NoIcon)
        done.setWindowTitle(tr("CR30 Bluetooth report"))
        done.setText(tr("Saved"))
        done.setInformativeText(tr(
            "The report is at:\n{path}\n\nOpen it and read it before you "
            "send it — it describes what your computer could see. Send it "
            "PRIVATELY, by message or email rather than a public post: a "
            "Bluetooth scan lists what is switched on around you. ChromIQ has "
            "already hidden the names of everything that was not a possible "
            "instrument.").format(path=path))
        done.setStandardButtons(QMessageBox.StandardButton.Ok)
        fit_message_box_buttons(done)
        done.exec()
        self._offer_cr30_bluetooth_repair(result.get("confirmed") or [])

    def _offer_cr30_bluetooth_repair(self, confirmed: list) -> None:
        """If the report reached an instrument, offer to use it from now on.

        THE REPAIR HALF. A user whose Bluetooth "does not work" may have an
        instrument ChromIQ can reach perfectly well once it stops searching for
        it -- discovery is the fragile part, and it is the part this can skip.
        Remembering the address is exactly what `DeviceReader._open_ble` already
        consumes on its fast path.

        ONLY A CONFIRMED ADDRESS. Never one that merely advertised the right
        service: `ffe0` is generic, and writing a stranger's address into the
        setting is the fault closed in 1de3f3af, where the next frames sent to
        whatever answered were calibration commands. Everything offered here has
        answered as a CR30. The fast path re-identifies it before trusting it
        anyway, so a device that later changes is refused rather than used.
        """
        if not confirmed:
            return
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import fit_message_box_buttons
        first = confirmed[0]
        address = str(first.get("address") or "")
        if not address:
            return
        name = str(first.get("name") or "") or tr("your CR30")

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(tr("CR30 Bluetooth report"))
        box.setText(tr("ChromIQ reached your instrument"))
        box.setInformativeText(tr(
            "It found {name} and the instrument answered correctly. If "
            "measuring over Bluetooth has been failing for you, the searching "
            "is the fragile part — and ChromIQ can skip it by going straight "
            "to this instrument in future.\n\n"
            "Would you like it to do that? It is remembered on this computer "
            "only, and ChromIQ still checks that the instrument really is a "
            "CR30 before using it, so nothing else can take its place.\n\n"
            "You can undo it at any time: run this report again and choose "
            "“Search normally”. That is the whole of it — there is nothing to "
            "hunt for in Preferences.\n\n"
            "Please still send the report either way. If this works for you it "
            "means ChromIQ's search has a fault that we would rather fix than "
            "leave you working around."
            ).format(name=name))
        use = box.addButton(tr("Go straight to this instrument"),
                            QMessageBox.ButtonRole.AcceptRole)
        clear = box.addButton(tr("Search normally"),
                              QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Leave it as it is"),
                      QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(use)
        fit_message_box_buttons(box)
        box.exec()
        clicked = box.clickedButton()
        if clicked is not use and clicked is not clear:
            return
        try:
            from workflow.cr30.measure_bridge import DeviceReader
            self._settings.set(DeviceReader.REMEMBERED_ADDRESS_KEY,
                               address if clicked is use else "")
            log.info("CR30: remembered Bluetooth address %s",
                     "set from the report" if clicked is use else "cleared")
        except Exception:                      # noqa: BLE001 — never fatal
            log.warning("could not store the CR30 address", exc_info=True)

    def _launch_tool(self, key: str) -> None:
        if key == "patch_cube":
            self._show_patch_cube()
            return
        if key == "cr30_bt_report":
            self._run_cr30_bluetooth_report()
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
        # measurement_report seeds itself from the current target so the
        # window opens on the loaded project's reports — it needs the project
        # for that just like verify_profile does (Sebastian, 2026-08-10: the
        # Tools entry still opened empty while the Measure-tab button worked).
        # ASK has_project(), NOT working_dir(). `working_dir()` goes through
        # `get_target_name()`, which INVENTS AND STORES a name when there is
        # none — so merely opening the Tools menu after closing a project armed
        # a phantom: the next `project()` call created
        # ~/ChromIQ/Printer_Paper_Type_Instr_<date>/ that nobody asked for
        # (#164; the same shape as Knut's #130 *"It must not create another
        # project that I did not ask for"*). `has_project()` short-circuits on
        # an empty name and never creates anything.
        if key in ("verify_profile", "measurement_report") \
                and self._file_mgr.has_project():
            try:
                project = self._file_mgr.project()
            except Exception:  # noqa: BLE001
                project = None
        open_tool_dialog(key, self._runner, self._settings, self,
                         on_apply=on_apply, initial_chart=initial_chart,
                         project=project)

    def _current_chart_ti2(self) -> "Path | None":
        """The SELECTED target's generated chart .ti2, or None when there isn't
        one yet (so the patch set editor opens empty as before).

        A CALIBRATION IS A THIRD TARGET, AND THIS KNEW ONLY ONE.

        This asked the project for ``current_run().chart_ti2`` — the profiling
        chart — whatever the bar was pointing at. So with Run type =
        Calibration the patch set editor opened the *profile run's* patch set:
        driven on screen against Demo-Full-RGB it showed **400 patches** under
        the name ``Demo-Full-RGB`` when the calibration chart beside it was 64
        patches of ``Demo-Full-RGB-cal``. Editing and applying from there lays
        the wrong patch set out and — because a calibration build writes to
        ``cal/`` (``_confirm_replacing_calibration``) — writes it over the
        calibration chart. Same shape as beta.165: two run types were assumed
        where there are three.

        The cure is not another copy of the branching, which is what produced
        the fault; it is to ask the one method that already resolves this for
        every run type. ``_resolve_target_chart`` wants the sheet TIFFs to
        exist as well as the ``.ti2``, which is a slightly stricter test than
        this used to apply — deliberately kept, because a chart whose pages are
        missing is not one the preview, Print Chart or Measure will accept
        either, and one definition of "the selected target's chart" is the
        whole point.
        """
        if not self._file_mgr.has_project():
            return None
        try:
            resolved = self._tab_chart._resolve_target_chart()
        except Exception:  # noqa: BLE001 — never block opening the tool
            return None
        if not resolved:
            return None
        ti2 = resolved[0]
        return ti2 if ti2.exists() else None

    def _apply_editor_chart(self, src_dir: "Path", name: str) -> bool:
        """Adopt a chart the layout editor just saved and show the Create Chart tab.

        Returns False when the user cancelled a name-collision prompt, so the
        editor stays open instead of closing on a no-op.
        """
        # NO PROJECT MEANS NOWHERE TO PUT IT.
        # Adopting a chart stages it INTO the project folder, and asking where
        # that is used to INVENT one: `working_dir()` goes through
        # `get_target_name()`, which makes up a name and stores it. The editor's
        # "Save & apply" then wrote `edited_patch_set.ti1` into a folder with no
        # project.json — an orphan ChromIQ can never find again — and the next
        # action created a second, real project beside it. Two folders from one
        # click (#164).
        #
        # Guarded HERE rather than inside `apply_external_chart`, because this
        # is the door a user comes through with no project open; the method
        # itself is also driven programmatically, where a project is already
        # established.
        if not self._file_mgr.is_named():
            log.warning("No project is open; the edited chart was not adopted")
            from ui.tooltip_button import InfoDialog
            InfoDialog(
                tr("No project to put this chart in"),
                tr("This chart has nowhere to go yet, so nothing was changed.\n\n"
                   "Charts live inside a profile project. Type a name in "
                   "“Printer profile project name” on the Create Chart tab and "
                   "press “Generate Chart” to start one — or open an existing "
                   "project with “Open Project” at the top left — and then use "
                   "“Apply / Save…” again."),
                self,
            ).exec()
            return False
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
        if not self._file_mgr.has_project():
            QMessageBox.information(self, tr("Show patch distribution (3D)"), no_chart)
            return

        # THE SAME FAULT THE PATCH SET EDITOR HAD, IN ITS SIBLING.
        #
        # This asked for `current_run().chart_ti2` — the profiling chart —
        # whatever the bar pointed at, so with Run type = Calibration it drew
        # the profile run's cube and called it "Current chart". Found while
        # building Knut's tool-availability table, which is exactly the kind of
        # thing that table is meant to surface. Resolve through the one method
        # that knows all three run types, and fall back to the .ti1 as before.
        resolved = self._tab_chart._resolve_target_chart()
        if resolved:
            ti2, _tiffs, ti1 = resolved
            chart = ti2 if ti2.exists() else ti1
        else:
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
        # The label-style boxes in Create Chart → Manual show Preferences'
        # values for a chart that carries none of its own, so a change here has
        # to reach them or the visible controls would go stale (Knut, beta-6).
        if hasattr(self._tab_chart, "refresh_label_style_defaults"):
            self._tab_chart.refresh_label_style_defaults()
        # "Show measurement progress bar" takes effect at once (#153, Knut:
        # *"the checkbox did not remove progress bar when disabled and pressing
        # OK … Changing tabs did also not update"*). Preferences pushes changes
        # at the tabs rather than the tabs polling, so a new option that is not
        # pushed here simply never arrives.
        if hasattr(self._tab_measure, "refresh_progress_setting"):
            self._tab_measure.refresh_progress_setting()
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
        # "Show the location being edited" (#130, Knut): the bar reads the
        # preference every time it refreshes, but nothing refreshed it when
        # Preferences closed — so turning the line off appeared to do nothing
        # until the run selection happened to change.
        if getattr(self, "_target_bar", None) is not None:
            self._target_bar.refresh()
        self._apply_log_visibility()

    def _apply_log_visibility(self) -> None:
        """Show or hide the log panel on every tab at once.

        Basti asked for one switch rather than a per-tab one, so this finds the
        panels by object name instead of listing them: every tab's log is a
        ``QPlainTextEdit`` called ``"log"``, and there are six of them — Build
        Profile alone has three, one per module. A hand-written list would miss
        the next one added, and the failure would be a log that stubbornly
        stays visible with no clue why.

        A wrapper that exists only to hold a log goes with it, or hiding the
        log would leave its margins behind as a blank strip.
        """
        from PyQt6.QtWidgets import QPlainTextEdit

        show = not bool(self._settings.get("hide_log_output", False))
        for log in self.findChildren(QPlainTextEdit, "log"):
            log.setVisible(show)
            parent = log.parentWidget()
            if parent is not None and parent.objectName() == "log_container":
                parent.setVisible(show)

    def _apply_calibration_mode(self) -> None:
        enabled = bool(self._settings.get("calibration_mode", False))
        for tab in (self._tab_chart, self._tab_measure, self._tab_profile, self._tab_check):
            if hasattr(tab, "set_calibration_mode"):
                tab.set_calibration_mode(enabled)
        # The bar is the fifth listener (#137): the "Calibration" run type is
        # offered only while this preference is on, and switching the
        # preference off while it is selected drops back to Profiling. One
        # fan-out, so the bar and the tabs can never disagree about the mode.
        if getattr(self, "_target_bar", None) is not None:
            self._target_bar.set_calibration_allowed(enabled)
        # Same refresh moment for the profile-engine beta selector (#122).
        profile_idx = self._tabs.indexOf(self._tab_profile)
        self._tabs.setTabText(
            profile_idx,
            tr("4. Calibration & Profiling") if enabled else tr("4. Build Profile"),
        )
        # The tab's NAME has changed; whether it is available has not, but the
        # gate is cheap and this is the other moment tab 4 is reconsidered.
        self._apply_profile_tab_gate()

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
            # DEFERRED, not shown here. This runs inside __init__, i.e. while the
            # startup splash is still up and always-on-top — a modal opened now
            # sits under it, unreachable except by Alt+Tab (Windows). The status
            # line above, the auto-detect and the settings write all stay put;
            # only the dialog waits for main() to call show_startup_warnings().
            self._argyll_missing_at_start = True

    def show_startup_warnings(self) -> None:
        """Show the first-launch ArgyllCMS dialog — after the window is up.

        Called by ``main()`` once ``win.show()`` has happened and the splash has
        been finished, because a modal raised any earlier is covered by the
        always-on-top splash and cannot be clicked. Safe to call more than once
        and safe when nothing is pending: it clears the flag as it fires.
        """
        if self._argyll_missing_at_start:
            self._argyll_missing_at_start = False
            self._show_argyll_not_found_dialog()

    def _show_argyll_not_found_dialog(self) -> None:
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("ArgyllCMS Not Found"))
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Name the places THIS platform actually searches, and send the user to
        # its own download page rather than the generic site.
        # tr() must wrap the MODULE-LEVEL name here, not a local holding it:
        # scripts/i18n_extract.py resolves tr(NAME) only for module-level
        # constants, so tr(local) extracts nothing and all 12 catalogues report
        # the entry as stale.
        import sys as _sys
        from core.platform_paths import argyll_download_page
        if _sys.platform == "win32":
            where = tr(_ARGYLL_WHERE_WINDOWS)
        elif _sys.platform == "darwin":
            where = tr(_ARGYLL_WHERE_MACOS)
        else:
            where = tr(_ARGYLL_WHERE_LINUX)

        msg = QLabel(
            tr(_ARGYLL_NOT_FOUND_MSG).format(
                url=argyll_download_page(), where=where),
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
            # FORGET WHAT WAS STYLED AT CONSTRUCTION.
            #
            # The per-tab cache keys on (index, mode). While _title_bar_mode was
            # hard-coded "dark" this pass was always a cache MISS in light mode
            # and every tab was genuinely re-styled — and something in that
            # second pass was needed: seeding the mode correctly turned the miss
            # into a hit, the re-style stopped happening, and Create Chart came
            # up wrong on launch until the user switched tabs and back (Basti,
            # on a real launch). Applying a theme is exactly when a re-style must
            # not be skipped, so the cache is cleared for it; it still saves the
            # per-switch re-styling it was written for.
            # LIGHT ONLY. Rendered comparison of the whole window: with the
            # clear, both themes are pixel-identical to master; without it, dark
            # is still identical and light differs by 21% of the window — the
            # QGroupBox rectangles, because apply_theme turns their
            # autoFillBackground ON (light only) and the per-tab setStyleSheet
            # two statements later repolishes it back OFF. The second pass exists
            # to undo the first. Dark never enters that fight, so it keeps the
            # cache and a quarter-second of launch.
            if mode == "light":
                self._styled_tab_theme.clear()
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
            # …AND THE VIEWPORT, which is what actually paints the placeholder.
            #
            # Without this, going light -> dark left the viewport at Weight.Black
            # and the placeholder text stayed visibly bolder (3,331 ink pixels
            # against 4,441). It has never been noticed because the next tab
            # switch re-styles the whole tree and repairs it by accident — the
            # same accidental repair the pane-stylesheet fix removes. Found only
            # with a FRESH profile: hiding the log panes hides the symptom.
            vp = log.viewport()
            if vp is not None:
                vf = vp.font()
                vf.setWeight(_log_weight)
                vp.setFont(vf)

    def _apply_title_bar(self, mode: str) -> None:
        """Set the macOS native title bar appearance to match `mode`."""
        import sys
        if sys.platform != "darwin":
            return
        # Only a real Cocoa window has an NSView behind winId(). Under the
        # offscreen platform (the on-screen test drivers' headless mode) the
        # handle is a fake, and objc_msgSend on it is a segfault the except
        # below cannot catch — it killed drive_demo_package.py before its
        # first line of output (2026-08-12).
        from PyQt6.QtWidgets import QApplication
        if QApplication.platformName() != "cocoa":
            return
        # ONE OF THE FEW GENUINELY TWO-ANSWER SITES: macOS ships
        # NSAppearanceNameAqua and NSAppearanceNameDarkAqua and no third, so
        # this cannot carry an appearance the way a repaint can. It must still
        # not ask `mode == "light"` — an appearance that is light-grey is not
        # named "light", would take the else branch, and would hang a black
        # title bar over a light window. Ask which KIND of ground it paints.
        from ui.theme import has_dark_ground
        ns_name = (b"NSAppearanceNameDarkAqua" if has_dark_ground(mode)
                   else b"NSAppearanceNameAqua")
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
        # #130: a nested project (in a sub-folder of the ChromIQ folder) is
        # restored at its actual location; a direct child by name as before.
        nested = self._settings.get("session_project_root", "")
        if nested and (Path(nested) / "project.json").exists():
            self._file_mgr.open_project_at(Path(nested))
        else:
            self._file_mgr.set_target_name(target)

        # Only the target name is persisted now; every artefact path is derived
        # from the project's current run. Bail if there's no project on disk for
        # this target (deleted folder, or a pre-redesign session).
        if not self._file_mgr.has_project():
            # CLEAR THE NAME, don't just bail. `set_target_name` above already
            # took, so bailing left `is_named()` True with `has_project()`
            # False — and everything that asks "may I write into the project
            # folder?" trusts `is_named()`. The next thing to ask would have
            # recreated the folder the user deleted outside ChromIQ, which is
            # precisely the #130 fault `close_project` was written to make
            # impossible (see its docstring). Reproduced with
            # restore_last_session on and the folder removed in Finder.
            log.info("Session restore skipped: no project for target=%s", target)
            self._file_mgr.close_project()
            self._refresh_masthead_availability()
            return

        # The failure path above refreshes explicitly; do the same here rather
        # than rely on `set_profile_run` happening to emit `changed` because
        # `profile_run` was "" at startup.
        self._refresh_masthead_availability()
        proj = self._file_mgr.project()
        run = proj.current_run()
        # #130: default the shared Profile-run bar to the restored project's
        # current run, so a plain Generate overwrites it (not a spurious new run).
        if getattr(self, "_target_ctl", None) is not None:
            self._target_ctl.set_profile_run(run.id)

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
            # A LOADED chart must carry its .ti2 into the Print tab too —
            # an already-converted chart forces Raw only if the tab knows
            # which chart it is holding (§3.1a; Basti, 2026-08-10).
            if run.chart_ti2.exists():
                self._tab_print.note_generated_chart(run.chart_ti2)

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

    def _mark_quit_on_the_measurement(self) -> bool:
        """Tell a running measurement that the app is closing. True if told.

        ⚠ THE ATTRIBUTE IS `_tab_measure`. An earlier version of this looked
        for `self.tab_measure` and `self._measure_manager` — **MainWindow has
        neither** — so the guard was dead code and the quit warning it was
        written to remove kept firing on every quit. `getattr` fails silently,
        which is exactly why a wrong name survives.

        It is a METHOD rather than four lines inside `closeEvent` so a test can
        run the real lookup on a real window. The test that let the dead code
        through read `inspect.getsource`: source contains the right words
        whether or not the names resolve.
        """
        mgr = getattr(getattr(self, "_tab_measure", None), "_manager", None)
        note = getattr(mgr, "note_app_quitting", None)
        if not callable(note):
            return False
        try:
            note()
            return True
        except Exception:              # noqa: BLE001 — never block a quit
            log.debug("could not mark the quit", exc_info=True)
            return False

    def closeEvent(self, event) -> None:
        # §3 W6 — QUITTING COUNTS AS LEAVING THE VISIBLE TAB.
        #
        # Qt raises no tab-change for it, so without this the one tab the user
        # actually worked in is the one tab that never records anything. Knut
        # ruled it writes silently (2026-08-06, Q2: "yes, write silently"), so
        # there is no prompt and no notice — and it writes that tab for the
        # selected target only (§2.0), never a sweep.
        self._save_settings_of_tab_left()
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
        # #130: remember a nested project's actual folder so it restores there.
        self._settings.set(
            "session_project_root",
            str(self._file_mgr.project_root_override() or ""))
        # SAY WHY BEFORE KILLING. cleanup() kills the helper, and the
        # session's finish handler runs synchronously off that — it must know
        # this ending was the user quitting, not a failure. See
        # MeasureManager.note_app_quitting.
        self._mark_quit_on_the_measurement()
        self._runner.cleanup()
        # LAST, and while the event loop is still alive: main._hard_exit calls
        # os._exit, which skips the flush QSettings would otherwise do on
        # destruction. Without this everything written above — the active tab,
        # the window geometry, the session — could be lost (Knut, #130).
        self._settings.sync()
        super().closeEvent(event)
