"""Pop-up 3D RGB-cube view of the layout editor's patch set.

Launched from the editor's Patches controls ("3D distribution…"). Embeds the
shared :class:`ui.patch_cube_panel.PatchCubePanel` (a self-contained Plotly page
in a ``QWebEngineView``) and shows it modally — a one-shot snapshot of the
current patch set. The generator dialogs reuse the same panel *inline* for their
live preview; see :mod:`ui.patch_cube_panel`.

View-only: the cube doesn't edit the chart, so the dialog holds no editor
state. It takes a snapshot of the current program and renders it; reopening
after edits re-renders the new snapshot.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QVBoxLayout, QWidget,
)

from core.logger import get_logger
from core.i18n import tr
from ui.patch_cube_panel import PatchCubePanel
from ui.styles import SPEC_MAGENTA, combo_popup_qss
from ui.tab_header import dialog_masthead

log = get_logger(__name__)


class PatchCubeDialog(QDialog):
    """Modal-ish popup showing the patch set as a rotatable 3D RGB cube.

    ``target_name`` labels the cube (the currently loaded chart). When
    ``compare_presets`` (``[(label, .ti1 path), …]``) is given, a "Compare with
    profile:" dropdown lets the user open a second, camera-synced cube of that
    preset's patches alongside (#66)."""

    def __init__(self, program: list[tuple], *, mode: str = "dark",
                 target_name: str = "",
                 compare_presets: list[tuple[str, Path]] | None = None,
                 numbered: bool = False,
                 lab_cloud: "tuple[list, list] | None" = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._numbered = numbered
        self._target_name = target_name or tr("Current chart")
        # Lab mode (#72): a multi-ink chart shown as a true Lab-space scatter
        # (positions via its preconditioning profile). RGB preset comparison
        # doesn't apply there, so the compare combo is dropped.
        self._lab_cloud = lab_cloud
        self._compare_presets = [] if lab_cloud else list(compare_presets or [])
        self.setWindowTitle(
            tr("Patch distribution — Lab space") if lab_cloud
            else tr("Patch distribution — 3D RGB cube"))
        self.resize(1040 if self._compare_presets else 820, 760)
        self.setMinimumSize(520, 480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Tab-style masthead (eyebrow + serif title) over a full-width spectrum
        # stripe, matching the chart-design windows; the cube sits beneath it.
        head, _header, stripe = dialog_masthead(
            self, tr("PATCH SET · 3D VIEW"), tr("Patch distribution"),
            top=14, bottom=10,
            tooltip_title=tr("Patch distribution (3D)"),
            tooltip_body=tr(
                "Shows the chart's patches as points in the RGB cube, so you can "
                "see how evenly the colours are spread.\n\n"
                "Move the view to inspect it from any angle:\n"
                "• Mouse — drag to rotate, scroll to zoom, right-drag or "
                "middle-drag (wheel-click) to pan.\n"
                "• Keyboard (click the cube first) — arrow keys rotate, "
                "Shift+arrow keys pan, + / − zoom.\n\n"
                "Pick a preset in “Compare with profile” to open a second cube "
                "beside this one; the two cameras stay locked together, so the "
                "same rotate/zoom/pan moves both and you can compare coverage "
                "from any angle."))
        lay.addLayout(head)
        lay.addWidget(stripe)

        # Target name + (optional) "Compare with profile" dropdown.
        bar = QHBoxLayout()
        bar.setContentsMargins(12, 8, 12, 6)
        bar.setSpacing(8)
        # Post-#70 the profile name no longer describes the chart layout, so the
        # caller passes no name and we show a neutral label rather than implying
        # the profile name is the layout's (Knut, #70 follow-up). A specific name,
        # if ever given, still renders as "Chart: <name>".
        name_text = (tr("Chart: {name}").format(name=target_name) if target_name
                     else self._target_name)
        self._name_lbl = QLabel(name_text, self)
        self._name_lbl.setStyleSheet("font-weight: bold;")
        bar.addWidget(self._name_lbl)
        bar.addStretch(1)
        if self._compare_presets:
            bar.addWidget(QLabel(tr("Compare with profile:"), self))
            self._compare_combo = QComboBox(self)
            # Cap the popup at 15 rows + scroll. On macOS maxVisibleItems is
            # honoured ONLY when combobox-popup:0 (which replaces the native menu
            # with a scrollable list) — :1 keeps the native menu and shows every
            # row.
            self._compare_combo.setMaxVisibleItems(15)
            self._compare_combo.setStyleSheet("QComboBox { combobox-popup: 0; }")
            # This window declares no accent of its own, so its dropdown wears
            # the one the user is already looking at: dialog_masthead's default
            # magenta, the stroke drawn above — and the colour the patch-set
            # editor that opens the other cube uses. Without this the popup
            # falls through to the global cyan, which belongs to Build Profile
            # and means nothing here.
            self.setStyleSheet(self.styleSheet() + combo_popup_qss(SPEC_MAGENTA))
            self._compare_combo.addItem(tr("None"), None)
            for group, items in self._compare_presets:
                self._compare_combo.insertSeparator(self._compare_combo.count())
                self._compare_combo.addItem(group)          # instrument header
                hdr = self._compare_combo.model().item(self._compare_combo.count() - 1)
                if hdr is not None:
                    f = hdr.font(); f.setBold(True); hdr.setFont(f)
                    # Bold, but the same colour as the entries (not greyed) — and
                    # still not selectable (Enabled flag kept, Selectable dropped).
                    hdr.setFlags(Qt.ItemFlag.ItemIsEnabled)
                for label, path in items:
                    self._compare_combo.addItem("    " + label, str(path))
            self._compare_combo.currentIndexChanged.connect(self._on_compare_changed)
            bar.addWidget(self._compare_combo)
        lay.addLayout(bar)

        self._panel = PatchCubePanel(mode=mode, numbered=numbered, parent=self)
        self._panel.set_primary_label(self._target_name)
        lay.addWidget(self._panel, 1)
        if self._lab_cloud is not None:
            self._panel.set_lab_cloud(*self._lab_cloud)
        else:
            self._panel.set_program(program)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.setContentsMargins(8, 6, 8, 6)
        lay.addWidget(buttons)

    # ------------------------------------------------------------------
    def _on_compare_changed(self, _index: int) -> None:
        """Open / close the side-by-side comparison cube for the picked preset."""
        path = self._compare_combo.currentData()
        if not path:
            self._panel.clear_compare()
            self._name_lbl.setVisible(True)
            return
        label = self._compare_combo.currentText().strip()   # drop the indent
        from workflow.ti2_relayout import load_rgb_program
        try:
            program_b = load_rgb_program(Path(path))
        except (ValueError, OSError) as exc:
            log.warning("compare preset %s: %s", path, exc)
            program_b = []
        if program_b:
            self._panel.set_compare(program_b, label, self._target_name)
            # Two cubes: each cube now carries its own title, so the bar's
            # name label would just repeat the left cube's — hide it (#77, Knut).
            self._name_lbl.setVisible(False)
        else:
            self._panel.clear_compare()
            self._name_lbl.setVisible(True)

    # ------------------------------------------------------------------
    def exec(self) -> int:  # noqa: A003
        """Build the cube's web view *before* entering the modal loop.

        Instantiating a ``QWebEngineView`` creates a native surface; doing that
        while this dialog already holds the application-modal grab wedges the
        grab on Windows and freezes the app (issue #38 follow-up). So realise
        the dialog non-modally, build the view off the grab, let the surface
        settle, then go modal with the cube already in place."""
        self.show()                      # non-modal: realize the dialog
        self._panel.ensure_view()        # build the web view off the grab
        QApplication.processEvents()     # let the native surface settle
        return super().exec()

    # ------------------------------------------------------------------
    def done(self, result: int) -> None:  # noqa: N802
        # done() is the single chokepoint for both accept() and reject().
        self._panel.teardown()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._panel.teardown()
        super().closeEvent(event)
