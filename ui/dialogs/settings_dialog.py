"""Settings / Preferences dialog."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFontMetrics
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.updater import UpdateChecker, _RELEASES_PAGE
from core.version import APP_VERSION
from ui.tooltip_button import TooltipButton
from ui.widgets import make_browse_button, open_dir_dialog

if TYPE_CHECKING:
    from core.settings import AppSettings

log = get_logger(__name__)

_ARGYLL_DOWNLOAD_PAGE = "https://www.argyllcms.com/downloadmac.html"


class SettingsDialog(QDialog):
    def __init__(self, settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._update_checker: UpdateChecker | None = None
        self.setWindowTitle("ChromIQ Preferences")
        self.setMinimumWidth(540)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._build_ui()
        self._load_settings()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # ---- ArgyllCMS ----
        argyll_grp = QGroupBox("ArgyllCMS Binaries", self)
        ag = QVBoxLayout(argyll_grp)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Binary path:", self))
        self._argyll_edit = QLineEdit(self)
        path_row.addWidget(self._argyll_edit, stretch=1)
        browse_btn = make_browse_button(self, "Select ArgyllCMS bin folder", icon="folder")
        browse_btn.clicked.connect(self._browse_argyll)
        path_row.addWidget(browse_btn)
        path_row.addWidget(TooltipButton(
            "ArgyllCMS Binary Path",
            "Directory containing targen, printtarg, chartread, and colprof.\n"
            "Default: /Applications/Argyll/bin\n"
            "You can download the latest version from argyllcms.com.",
            self,
        ))
        ag.addLayout(path_row)

        btn_row = QHBoxLayout()
        test_btn = QPushButton("Test binaries", self)
        test_btn.clicked.connect(self._test_argyll)
        dl_btn = QPushButton("Download latest ArgyllCMS…", self)
        dl_btn.clicked.connect(self._open_argyll_download)
        btn_row.addWidget(test_btn)
        btn_row.addWidget(dl_btn)
        btn_row.addStretch()
        ag.addLayout(btn_row)

        self._argyll_status = QLabel("", self)
        self._argyll_status.setWordWrap(True)
        ag.addWidget(self._argyll_status)

        layout.addWidget(argyll_grp)

        # ---- Output folder ----
        folder_grp = QGroupBox("Output Folder", self)
        fl = QVBoxLayout(folder_grp)

        folder_lbl = QLabel(
            "Default output folder (leave blank to use ~/ChromIQ/):", self
        )
        folder_lbl.setWordWrap(True)
        fl.addWidget(folder_lbl)

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit(self)
        self._folder_edit.setPlaceholderText("~/ChromIQ/  (default)")
        folder_row.addWidget(self._folder_edit, stretch=1)
        folder_browse = make_browse_button(self, "Select output folder", icon="folder")
        folder_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(folder_browse)
        fl.addLayout(folder_row)

        layout.addWidget(folder_grp)

        # ---- About / Updates ----
        credit1 = QLabel(f"ChromIQ v{APP_VERSION} · Created by Sebastian Reiprich", self)
        credit1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit1.setStyleSheet("color: #606060; font-size: 11px;")
        layout.addWidget(credit1)

        credit2 = QLabel(
            "Built on ArgyllCMS by Graeme Gill · With thanks to Knut Georg Larsson", self
        )
        credit2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit2.setStyleSheet("color: #606060; font-size: 11px;")
        layout.addWidget(credit2)

        self._update_status = QLabel("", self)
        self._update_status.setStyleSheet("font-size: 11px;")
        self._update_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_status.setFixedHeight(QFontMetrics(self._update_status.font()).height())
        layout.addWidget(self._update_status)

        # ---- Bottom row: Restore Defaults | Check for Updates | Cancel / OK ----
        bottom_row = QHBoxLayout()
        reset_btn = QPushButton("Restore Factory Defaults", self)
        reset_btn.setStyleSheet(
            "QPushButton { background: #f4f4f4; color: #121212; border: 1px solid #d0d0d0; }"
            "QPushButton:hover { background: #e0e0e0; border-color: #bbbbbb; }"
        )
        reset_btn.clicked.connect(self._restore_defaults)
        bottom_row.addWidget(reset_btn)
        bottom_row.addStretch()

        self._update_btn = QPushButton("Check for Updates", self)
        self._update_btn.clicked.connect(self._check_for_updates)
        bottom_row.addWidget(self._update_btn)
        bottom_row.addSpacing(8)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        bb.accepted.connect(self._save_and_close)
        bb.rejected.connect(self.reject)
        bottom_row.addWidget(bb)
        layout.addLayout(bottom_row)

        self.setStyleSheet("QLineEdit:focus { border-color: #f4f4f4; }")

    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        s = self._settings
        self._argyll_edit.setText(s.get("argyll_bin_path", "/Applications/Argyll/bin"))
        self._folder_edit.setText(s.get("custom_output_path", ""))

    def _save_and_close(self) -> None:
        s = self._settings
        s.set("argyll_bin_path",       self._argyll_edit.text().strip())
        s.set("custom_output_path",    self._folder_edit.text().strip())
        log.info("Settings saved")
        self.accept()

    def _browse_argyll(self) -> None:
        d = open_dir_dialog(
            self, "Select ArgyllCMS bin directory",
            start_dir=self._argyll_edit.text() or "/Applications",
        )
        if d:
            self._argyll_edit.setText(d)

    def _browse_folder(self) -> None:
        d = open_dir_dialog(
            self, "Select output folder",
            start_dir=self._folder_edit.text() or str(Path.home()),
        )
        if d:
            self._folder_edit.setText(d)

    def _test_argyll(self) -> None:
        bin_dir = Path(self._argyll_edit.text().strip())
        results = []
        for tool in ("targen", "printtarg", "chartread", "colprof",
                     "profcheck", "printcal", "applycal"):
            p = bin_dir / tool
            if tool == "chartread":
                # chartread probes USB hardware even with -?, causing a hang.
                # Existence + executable check is sufficient here.
                if p.exists() and os.access(str(p), os.X_OK):
                    results.append(f"✓ {tool}")
                else:
                    results.append(f"✗ {tool} (not found)")
                continue
            if p.exists():
                try:
                    subprocess.run(
                        [str(p), "-?"], capture_output=True, timeout=5,
                    )
                    results.append(f"✓ {tool}")
                except Exception:
                    results.append(f"✗ {tool} (error)")
            else:
                results.append(f"✗ {tool} (not found)")
        msg = "  ".join(results)
        all_ok = all(r.startswith("✓") for r in results)
        self._argyll_status.setStyleSheet(
            "color: #4caf50;" if all_ok else "color: #ff9800;"
        )
        self._argyll_status.setText(msg)
        log.info("ArgyllCMS test: %s", msg)

    def _open_argyll_download(self) -> None:
        self._argyll_status.setStyleSheet("")
        self._argyll_status.setText(
            "Opening argyllcms.com — download the latest version for your Mac "
            "(arm64 for Apple Silicon, osx64 for Intel), then unpack and set the "
            "bin path above."
        )
        QDesktopServices.openUrl(QUrl(_ARGYLL_DOWNLOAD_PAGE))

    def _restore_defaults(self) -> None:
        self._settings.reset_to_defaults()
        self._load_settings()
        log.info("Factory defaults restored")

    def _check_for_updates(self) -> None:
        self._update_btn.setEnabled(False)
        self._update_btn.setText("Checking…")
        self._update_status.setText("")

        self._update_checker = UpdateChecker(self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.up_to_date.connect(self._on_up_to_date)
        self._update_checker.check_failed.connect(self._on_update_failed)
        self._update_checker.check_async()

    def _on_update_available(self, latest: str) -> None:
        self._update_btn.setEnabled(True)
        self._update_btn.setText("Check for Updates")
        self._update_status.setStyleSheet("font-size: 11px; color: #e67e00;")
        self._update_status.setText(
            f'{latest} available — <a href="{_RELEASES_PAGE}">open GitHub Releases</a>'
        )
        self._update_status.setOpenExternalLinks(True)

    def _on_up_to_date(self) -> None:
        self._update_btn.setEnabled(True)
        self._update_btn.setText("Check for Updates")
        self._update_status.setStyleSheet("font-size: 11px; color: #4caf50;")
        self._update_status.setText("You're up to date.")

    def _on_update_failed(self, reason: str) -> None:
        self._update_btn.setEnabled(True)
        self._update_btn.setText("Check for Updates")
        self._update_status.setStyleSheet("font-size: 11px; color: #888;")
        self._update_status.setText(f"Check failed: {reason}")
