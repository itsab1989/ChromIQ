"""Main application window."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QMainWindow,
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

log = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._settings  = settings
        self._runner    = ArgyllRunner(settings, self)
        self._file_mgr  = FileManager(settings)

        self.setWindowTitle("ChromIQ — Printer Profiling")
        self.setMinimumSize(1440, 1025)
        self.resize(1440, 1025)

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
        main_layout.addWidget(self._masthead)

        # Tabs
        self._tabs = QTabWidget(central)
        self._tabs.setDocumentMode(True)
        self._tabs.setTabBar(SpectrumTabBar(self._tabs))

        self._tab_chart   = TabChart(self._runner, self._file_mgr, self._settings, self)
        self._tab_print   = TabPrint(self._settings, self)
        self._tab_measure = TabMeasure(self._runner, self._settings, self)
        self._tab_profile = TabProfile(self._runner, self._settings, self)
        self._tab_check   = TabCheckRefine(self._runner, self._settings, self)

        self._tabs.addTab(self._tab_chart,   "1. Create Chart")
        self._tabs.addTab(self._tab_print,   "2. Print Chart")
        self._tabs.addTab(self._tab_measure, "3. Measure")
        self._tabs.addTab(self._tab_profile, "4. Build Profile")
        self._tabs.addTab(self._tab_check,   "5. Check & Refine")

        # Gradient wash — left panel only for splitter tabs, full pane for the rest
        from ui.styles import TAB_COLORS
        for _i in range(self._tabs.count()):
            _tab_w = self._tabs.widget(_i)
            _target = getattr(_tab_w, "_left_panel", _tab_w)
            GradientOverlay(TAB_COLORS[_i], parent=_target)

        self._tab_chart.chart_finished.connect(self._on_chart_generated)
        self._tab_measure.measure_finished.connect(self._on_measure_done)
        self._tab_measure.proceed_to_profile.connect(self._on_proceed_to_profile)
        self._tab_profile.profile_built.connect(self._tab_check.set_paths)
        self._tab_profile.check_requested.connect(lambda: self._tabs.setCurrentWidget(self._tab_check))
        self._tab_check.guide_refinement_requested.connect(self._on_guide_refinement)
        self._tab_check.ti2_found.connect(self._tab_measure.set_ti1_path)
        self._tab_print.ti2_loaded.connect(self._tab_measure.set_ti1_path)

        main_layout.addWidget(self._tabs, stretch=1)

        # 2px accent line on the left edge — child of the main window so it
        # spans the full height including the status bar below the tab widget
        self._accent_line = QFrame(self)
        self._accent_line.setFixedWidth(2)
        self._accent_line.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        QTimer.singleShot(0, lambda: self._on_tab_changed(self._tabs.currentIndex()))

        # Restore geometry
        geom = self._settings.get("window_geometry")
        if geom:
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass

        active = int(self._settings.get("active_tab", 0))
        self._tabs.setCurrentIndex(active)

        self.statusBar().hide()
        self._status_msg: str = ""

        self._check_argyll_binaries(initial=True)
        self._startup_update_checker: UpdateChecker | None = None
        QTimer.singleShot(0, self._apply_dark_title_bar)
        QTimer.singleShot(3000, self._check_for_updates_on_startup)
        log.info("MainWindow initialised")

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refit_accent_line()

    def _refit_accent_line(self) -> None:
        y = self._masthead.height() + self._tabs.tabBar().height()
        self._accent_line.setGeometry(0, y, 2, max(0, self.height() - y))
        self._accent_line.raise_()

    def _on_tab_changed(self, index: int) -> None:
        from ui.styles import TAB_COLORS
        from ui.tooltip_button import TooltipButton

        color = TAB_COLORS[index] if index < len(TAB_COLORS) else TAB_COLORS[-1]

        # Compute variants without broken hex-alpha (Qt reads #AARRGGBB, not #RRGGBBAA)
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        color_hover = "#{:02x}{:02x}{:02x}".format(int(r * 0.82), int(g * 0.82), int(b * 0.82))
        color_glow  = f"rgba({r},{g},{b},0.33)"

        self._accent_line.setStyleSheet(f"background: {color}; border: none;")
        self._refit_accent_line()


        tab_w = self._tabs.widget(index)
        if tab_w:
            tab_w.setStyleSheet(f"""
                QPushButton#primary {{
                    background: {color};
                    border: 1px solid {color};
                    color: #0a0a0a;
                    font-weight: 700;
                }}
                QPushButton#primary:hover {{
                    background: {color_hover};
                    border-color: {color_hover};
                }}
                QPushButton#primary:disabled {{
                    background: #1e1e1e;
                    border: 1px solid {color};
                    color: #484848;
                }}
                QCheckBox::indicator:checked {{
                    background: {color};
                    border-color: {color};
                }}
                QRadioButton::indicator:checked {{
                    background: {color};
                    border-color: {color};
                }}
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
                QComboBox:focus, QComboBox:on {{
                    border-color: {color};
                }}
                QLabel#patch_count {{
                    color: {color};
                }}
                QLabel#info {{
                    color: {color};
                    border-color: {color};
                }}
                QPlainTextEdit#log {{
                    color: {color};
                }}
                QPushButton#mode_btn {{
                    background: #2a2a2a;
                    border: 1px solid #4a4a4a;
                    color: #909090;
                }}
                QPushButton#mode_btn:hover {{
                    background: #383838;
                    border-color: #5a5a5a;
                    color: #e6e6e6;
                }}
                QPushButton#mode_btn:checked {{
                    background: {color};
                    border: 1px solid {color};
                    color: #0a0a0a;
                    font-weight: 700;
                }}
                QPushButton#mode_btn:checked:hover {{
                    background: {color_hover};
                    border-color: {color_hover};
                    color: #0a0a0a;
                }}
            """)

        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {color_glow};
                background: #181818;
            }}
        """)

        TooltipButton.ACCENT = color
        if tab_w:
            for btn in tab_w.findChildren(TooltipButton):
                btn._set_icon()

    def _on_chart_generated(self, tiffs: object, ti2: object) -> None:
        self._tab_print.load_tiffs(list(tiffs))
        if ti2 and Path(ti2).exists():
            self._tab_measure.set_ti1_path(Path(ti2))

    def _on_measure_done(self, ti3: Path) -> None:
        self._tab_profile.set_ti3_path(ti3)

    def _on_proceed_to_profile(self) -> None:
        self._tabs.setCurrentWidget(self._tab_profile)

    def _on_guide_refinement(self, ti3: Path, strips_file: Path) -> None:
        self._tabs.setCurrentWidget(self._tab_measure)
        self._tab_measure.start_guided_refinement(ti3, strips_file)

    def _open_settings(self) -> None:
        from ui.tooltip_button import TooltipButton
        dlg = SettingsDialog(self._settings, self)
        for btn in dlg.findChildren(TooltipButton):
            btn._color_override = "#f4f4f4"
            btn._set_icon()
        dlg.exec()
        self._check_argyll_binaries()

    def _check_for_updates_on_startup(self) -> None:
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
        if not self._status_msg:
            self._set_tab_status(
                f"Update available: ChromIQ {latest} — open Preferences (⚙) to download."
            )

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
        dlg.setWindowTitle("ArgyllCMS Not Found")
        dlg.setMinimumWidth(520)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        msg = QLabel(
            "<b>ArgyllCMS could not be found on your system.</b><br><br>"
            "ChromIQ requires ArgyllCMS to create and measure ICC profiles. "
            "It was not detected in any of the usual locations.<br><br>"
            "<b>To install ArgyllCMS:</b><br>"
            "&nbsp;&nbsp;1. Download ArgyllCMS from "
            "<a href='https://www.argyllcms.com'>argyllcms.com</a><br>"
            "&nbsp;&nbsp;2. Extract the archive and move the folder to "
            "<span style='font-family:monospace'>/Applications</span><br>"
            "&nbsp;&nbsp;3. Restart ChromIQ — it will detect the installation "
            "automatically.<br><br>"
            "If ArgyllCMS is already installed in a custom location, click "
            "<b>Open Preferences</b> to set the path manually.",
            dlg,
        )
        msg.setOpenExternalLinks(True)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox()
        prefs_btn = btn_box.addButton("Open Preferences", QDialogButtonBox.ButtonRole.ActionRole)
        btn_box.addButton("OK", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.accepted.connect(dlg.accept)
        prefs_btn.clicked.connect(dlg.accept)
        prefs_btn.clicked.connect(self._open_settings)
        layout.addWidget(btn_box)

        dlg.exec()

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def _apply_dark_title_bar(self) -> None:
        """Force the macOS title bar to use dark (black) appearance."""
        import sys
        if sys.platform != "darwin":
            return
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

            dark_str = _msg(
                _C("NSString"), "stringWithUTF8String:",
                b"NSAppearanceNameDarkAqua",
                argtypes=[ctypes.c_char_p],
            )
            appearance = _msg(
                _C("NSAppearance"), "appearanceNamed:",
                ctypes.c_void_p(dark_str),
            )
            ns_view   = ctypes.c_void_p(int(self.winId()))
            ns_window = _msg(ns_view, "window")
            _msg(ns_window, "setAppearance:", ctypes.c_void_p(appearance))
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        self._settings.set("window_geometry", self.saveGeometry())
        self._settings.set("active_tab", self._tabs.currentIndex())
        super().closeEvent(event)
