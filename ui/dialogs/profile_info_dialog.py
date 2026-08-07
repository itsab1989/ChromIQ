"""Profile info — Tools ▸ "Inspect a profile".

Reads an ICC profile's header (via :mod:`workflow.icc_info`, no ArgyllCMS) and
shows it in plain language: version, kind, colour space, white point, who made
it, and a description. For ICC **v2** RGB/CMYK output or display profiles it
also computes the gamut volume with ``iccgamut``.

Crucially, it's the one place that explains the **ICC v4** limitation: Argyll
only reads v2 profiles, so a v4 profile (typically from i1Profiler / X-Rite)
can't be shown in the 3D gamut viewer or the soft-proof tool. A clear banner
says so, instead of leaving the user with Argyll's cryptic "ICC V4 not
supported!" error.

Standalone ``QDialog`` (no Run/log shape), styled like the other Tools windows
via :func:`ui.tab_header.dialog_masthead`. No WebEngine, so nothing here can
crash or hang on quit.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from core.platform_paths import icc_system_dirs
from ui.dialog_sizing import pin_min_height
from ui.dialogs.tools_dialogs import _indicator_color, neutral_controls_qss
from ui.fade_scroll import FadeScrollArea
from ui.styles import SPEC_AMBER, SPEC_VIOLET, TEXT_DIM, TEXT_MAIN
from ui.tab_header import dialog_masthead
from ui.widgets import make_browse_button, open_file_dialog, save_file_dialog
from workflow.icc_info import IccInfo, IccParseError, read_icc

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)

_ACCENT = SPEC_VIOLET

_HELP = tr(
    "Open any ICC profile to see what's inside it, in plain language — its "
    "version, what kind of device it describes, its colour space, white point, "
    "and which program created it.\n\n"
    "This is also where you'll find out if a profile is ICC v4. ArgyllCMS (which "
    "ChromIQ uses for its gamut viewer and soft-proof) only reads ICC v2 "
    "profiles, so a v4 profile — common from i1Profiler — can't be visualised "
    "here, even though it still works in other colour-managed apps."
)


class ProfileInfoDialog(QDialog):
    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._settings = settings
        self._info: IccInfo | None = None
        self._gamut_viewer = None  # lazily created (workflow.GamutViewer)
        # Theme-aware detail-text colours — the dark-theme greys are invisible
        # on a light background.
        self._text_main, self._text_dim = self._resolve_text_colors()

        self.setWindowTitle(tr("Profile info"))
        self.setMinimumWidth(620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head, _header, stripe = dialog_masthead(
            self, tr("PROFILE · INSPECT"), tr("Profile info"),
            tooltip_title=tr("Profile info"), tooltip_body=_HELP,
            accent=_ACCENT)
        root.addLayout(head)
        root.addWidget(stripe)

        self._inner = QVBoxLayout()
        self._inner.setContentsMargins(22, 14, 22, 16)
        self._inner.setSpacing(12)
        root.addLayout(self._inner)

        self._body = QLabel(
            tr("Open an ICC profile to inspect its contents."), self)
        self._body.setWordWrap(True)
        self._inner.addWidget(self._body)

        # --- File picker row ----------------------------------------------
        pick = QHBoxLayout()
        pick.setSpacing(8)
        pick.addWidget(QLabel(tr("Profile:"), self))
        self._path_edit = QLineEdit(self)
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText(tr("Browse for an ICC / ICM profile…"))
        pick.addWidget(self._path_edit, 1)
        browse = make_browse_button(self, tr("Browse for an ICC/ICM profile"), "folder_check")
        browse.clicked.connect(self._on_browse)
        pick.addWidget(browse)
        self._inner.addLayout(pick)

        # --- v4 / error banner (hidden until needed) ----------------------
        self._banner = QLabel("", self)
        self._banner.setWordWrap(True)
        self._banner.setTextFormat(Qt.TextFormat.RichText)
        self._banner.setVisible(False)
        self._inner.addWidget(self._banner)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self._inner.addWidget(sep)

        # --- Scrollable details -------------------------------------------
        self._scroll = FadeScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        # The details are the point of this window, so give the scroll a tall
        # floor — otherwise the no-overlap minimum collapses it to a sliver and
        # a loaded profile's rows are barely visible. Tall enough that the full
        # row set (incl. the paper-white/max-black contrast block) fits without
        # scrolling.
        self._scroll.setMinimumHeight(430)

        self._details = QWidget()
        self._grid = QGridLayout(self._details)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(8)
        self._grid.setColumnStretch(1, 1)
        self._scroll.setWidget(self._details)
        self._inner.addWidget(self._scroll, 1)

        self._placeholder = QLabel(tr("No profile loaded yet."), self._details)
        self._placeholder.setStyleSheet(f"color: {self._text_dim};")
        self._grid.addWidget(self._placeholder, 0, 0, 1, 2,
                             Qt.AlignmentFlag.AlignHCenter)

        # --- Bottom buttons -----------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._save_btn = QPushButton(tr("Save report…"), self)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_report)
        btn_row.addWidget(self._save_btn)
        close_btn = QPushButton(tr("Close"), self)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        self._inner.addLayout(btn_row)

        self.setStyleSheet(neutral_controls_qss(_indicator_color(settings)))

    # ------------------------------------------------------------------
    def _resolve_text_colors(self) -> tuple[str, str]:
        """(main, dim) detail-text colours for the active light/dark theme."""
        from ui.theme import resolve_mode
        if resolve_mode(self._settings.get("appearance", "auto")) == "light":
            return "#1c1b18", "#5a5a5a"
        return TEXT_MAIN, TEXT_DIM

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        pin_min_height(
            self, min_width=620, wrap_labels=(self._body, self._banner),
            inner_margins=self._inner.contentsMargins(), resize_width=True)

    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        sidebar = [str(d) for d in icc_system_dirs() if Path(d).exists()]
        path = open_file_dialog(
            self, tr("Select an ICC/ICM profile"),
            tr("ICC profiles (*.icc *.icm);;All files (*)"),
            start_dir=(sidebar[0] if sidebar else ""),
            extra_paths=sidebar,
        )
        if path:
            self.load_profile(Path(path))

    def load_profile(self, path: Path) -> None:
        self._path_edit.setText(str(path))
        try:
            self._info = read_icc(path)
        except (OSError, IccParseError) as exc:
            self._info = None
            self._show_error_banner(str(exc))
            self._populate_error(str(exc))
            return
        self._populate(self._info)
        self._update_banner(self._info)
        self._save_btn.setEnabled(True)
        # Gamut volume only for ICC v2 (Argyll can't read v4).
        if not self._info.is_v4 and self._info.device_class in ("prtr", "mntr"):
            self._compute_volume(path)

    def _on_save_report(self) -> None:
        if self._info is None:
            return
        src = self._info.path
        from datetime import datetime

        from core.version import APP_VERSION
        lines = []
        for r in range(self._grid.rowCount()):
            k = self._grid.itemAtPosition(r, 0)
            v = self._grid.itemAtPosition(r, 1)
            if (k and v and k.widget() is not None and v.widget() is not None
                    and k.widget() is not v.widget()):
                lines.append(f"  {k.widget().text()}: {v.widget().text()}")
        header = [
            tr("ChromIQ — Profile report"),
            tr("Profile: {name}").format(name=src.name),
            tr("Generated by ChromIQ {ver} on {date}").format(
                ver=APP_VERSION, date=datetime.now().strftime("%Y-%m-%d %H:%M")),
            "=" * 60,
        ]
        text = "\n".join(header + lines) + "\n"
        out = save_file_dialog(
            self, tr("Save profile report"),
            tr("Text files (*.txt);;All files (*)"),
            start_path=str(src.parent / f"{src.stem}-report.txt"),
            extra_paths=[str(src.parent)])
        if not out:
            return
        if not out.lower().endswith(".txt"):
            out += ".txt"
        try:
            Path(out).write_text(text, encoding="utf-8")
        except OSError as exc:
            self._show_error_banner(tr("Could not save the report: {msg}").format(msg=str(exc)))

    # ------------------------------------------------------------------
    # Banner
    # ------------------------------------------------------------------
    def _update_banner(self, info: IccInfo) -> None:
        if info.is_v4:
            self._banner.setText(
                tr("<b>This is an ICC v{ver} profile.</b> ArgyllCMS — which ChromIQ uses "
                   "for the 3D gamut viewer and the soft-proof tool — only reads ICC v2 "
                   "profiles, so this profile can't be visualised in those tools. It still "
                   "works normally in ColorSync and other colour-managed applications."
                   ).format(ver=info.version))
            self._banner.setStyleSheet(
                f"QLabel {{ background: rgba(255,180,45,0.12); color: {SPEC_AMBER};"
                f" border: 1px solid {SPEC_AMBER}; border-radius: 4px; padding: 8px 10px; }}")
            self._banner.setVisible(True)
        else:
            self._banner.setVisible(False)

    def _show_error_banner(self, msg: str) -> None:
        self._banner.setText(tr("Could not read this profile: {msg}").format(msg=msg))
        self._banner.setStyleSheet(
            "QLabel { background: rgba(255,69,115,0.12); color: #ff4573;"
            " border: 1px solid #ff4573; border-radius: 4px; padding: 8px 10px; }")
        self._banner.setVisible(True)

    # ------------------------------------------------------------------
    # Details grid
    # ------------------------------------------------------------------
    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)   # remove from view immediately, not on the
                w.deleteLater()     # next event loop (else it paints over rows)

    def _add_row(self, row: int, key: str, value: str, tooltip: str = "") -> None:
        k = QLabel(key, self._details)
        k.setStyleSheet(
            f"color: {self._text_dim}; font-family: Menlo, Consolas, monospace; font-size: 11px;")
        k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v = QLabel(value or "—", self._details)
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.setStyleSheet(
            f"color: {self._text_main}; font-family: Menlo, Consolas, monospace; font-size: 12px;")
        if tooltip:
            k.setToolTip(tooltip)
            v.setToolTip(tooltip)
        self._grid.addWidget(k, row, 0)
        self._grid.addWidget(v, row, 1)

    def _populate(self, info: IccInfo) -> None:
        self._clear_grid()
        self._text_main, self._text_dim = self._resolve_text_colors()
        rows = [
            (tr("Description"),     info.description, ""),
            (tr("ICC version"),     tr("v{ver}").format(ver=info.version), ""),
            (tr("Profile type"),    info.device_class_label, ""),
            (tr("Colour space"),    info.color_space_label, ""),
            (tr("Connection space"),info.pcs_label, ""),
            (tr("Rendering intent"),info.rendering_intent_label, ""),
        ]
        rows += self._contrast_rows(info)
        rows += [
            (tr("Created by"),      info.creator_label, ""),
            (tr("Created"),         info.created, ""),
            (tr("Embedded"),        tr("Yes") if info.is_embedded else tr("No"), ""),
            (tr("File size"),       tr("{kb:,.0f} KB").format(kb=info.size / 1024.0), ""),
        ]
        for i, (k, v, tip) in enumerate(rows):
            self._add_row(i, k, v, tip)
        self._gamut_row = len(rows)
        self._body.setText(
            tr("Showing details for “{name}”.").format(name=info.path.name))

    def _contrast_rows(self, info: IccInfo) -> list[tuple[str, str, str]]:
        """Paper-white / max-black rows: white point, the two L* values and the
        three contrast figures (ratio, dynamic range, ΔL*). Falls back to the
        header illuminant if the profile has no media white-point tag."""
        if info.media_white is not None:
            wp = "  ".join(f"{c:.4f}" for c in info.media_white)
            wp_label = tr("Paper white (XYZ)")
            wp_tip = tr(
                "The colour of the blank paper as the profile records it — the "
                "lightest the print can be. Read from the profile's media "
                "white-point tag (not the fixed D50 reference).")
        else:
            wp = "  ".join(f"{c:.4f}" for c in info.white_point)
            wp_label = tr("White point (XYZ)")
            wp_tip = tr(
                "The profile's reference white. This profile has no media "
                "white-point tag, so this is the connection-space illuminant "
                "(D50), not the paper itself.")
        rows: list[tuple[str, str, str]] = [(wp_label, wp, wp_tip)]

        wlab, blab = info.white_lab, info.black_lab
        if wlab is not None:
            rows.append((
                tr("Paper white L*"), tr("{l:.1f}").format(l=wlab[0]),
                tr("Lightness of the paper white on the 0–100 L* scale. Higher "
                   "means a brighter, whiter paper.")))
        if blab is not None:
            rows.append((
                tr("Max black L*"), tr("{l:.1f}").format(l=blab[0]),
                tr("Lightness of the darkest black this paper-and-ink "
                   "combination can print. Lower means a deeper black.")))

        ratio = info.contrast_ratio
        if ratio is not None:
            rows.append((
                tr("Contrast ratio"), tr("{r:,.0f} : 1").format(r=ratio),
                tr("How many times brighter the paper white is than the "
                   "deepest black (their luminance ratio). A bigger number "
                   "means more contrast — punchier prints.")))
        drange = info.dynamic_range
        if drange is not None:
            rows.append((
                tr("Dynamic range"), tr("{d:.2f} D").format(d=drange),
                tr("The same contrast expressed as optical density, the way "
                   "print and photo people measure it: the span from the "
                   "lightest to the darkest tone. Each whole step is a "
                   "ten-fold change in reflected light.")))
        dl = info.delta_lstar
        if dl is not None:
            rows.append((
                tr("Lightness range ΔL*"), tr("{d:.1f}").format(d=dl),
                tr("The gap in lightness between paper white and max black on "
                   "the L* scale — a quick, perceptual measure of contrast.")))
        return rows

    def _populate_error(self, msg: str) -> None:
        self._clear_grid()
        lbl = QLabel(tr("This file could not be read as an ICC profile.\n\n{msg}")
                     .format(msg=msg), self._details)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {self._text_dim};")
        self._grid.addWidget(lbl, 0, 0, 1, 2)

    # ------------------------------------------------------------------
    # Gamut volume (v2 only)
    # ------------------------------------------------------------------
    def _compute_volume(self, path: Path) -> None:
        row = getattr(self, "_gamut_row", None)
        if row is None:
            return
        self._add_row(row, tr("Gamut volume"), tr("computing…"))
        try:
            from workflow.gamut_viewer import GamutViewer, GamutViewerParams
        except ImportError:
            return
        if self._runner.is_running:
            self._set_volume_text(tr("—  (another process is running)"))
            return
        self._gamut_viewer = GamutViewer(self._runner, self)
        self._gamut_viewer.finished.connect(
            lambda vol, *_: self._set_volume_text(tr("{v:,.0f} units³").format(v=vol)))
        self._gamut_viewer.error.connect(lambda *_: self._set_volume_text("—"))
        # Coarse surface resolution: we only need the volume number, not a mesh.
        self._gamut_viewer.run(
            GamutViewerParams(icc_path=path, sres=10.0),
            on_line=lambda _l: None, on_finish=lambda _c: None,
            themed=False)

    def _set_volume_text(self, text: str) -> None:
        row = getattr(self, "_gamut_row", None)
        if row is None:
            return
        item = self._grid.itemAtPosition(row, 1)
        if item is not None and item.widget() is not None:
            item.widget().setText(text)
