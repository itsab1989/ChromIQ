"""Translate / edit language — spreadsheet export & import.

A translator who only has the shipped app can export every UI phrase to a CSV
or XLSX spreadsheet, edit the translation column in Excel / LibreOffice /
Sheets, and import the file back.  Imports land in the writable
:func:`core.i18n.user_i18n_dir` (so the read-only ``.app`` is never touched) and
take effect after a restart.  A "Send to developer" button opens a pre-filled
GitHub issue so the finished file can be contributed back.

All the real work lives in :mod:`workflow.i18n_roundtrip`; this is the GUI only.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from core.stem_paths import artefact

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.i18n import SOURCE_LANGUAGE, available_languages, tr
from core.logger import get_logger
from core.preset_store import reveal_in_file_manager
from ui.dialogs.tools_dialogs import _indicator_color, neutral_controls_qss
from ui.styles import SPEC_MAGENTA
from ui.tab_header import dialog_masthead
from ui.theme import resolve_mode
from ui.widgets import confirm, NoScrollComboBox, open_file_dialog, save_file_dialog
from workflow import i18n_roundtrip as rt
from ui.warning_sign import inform, warn

try:
    from core.version import APP_VERSION
except Exception:  # pragma: no cover
    APP_VERSION = ""

log = get_logger("translation_dialog")

_NEW_LANG = "__new__"
_ISSUES_NEW = "https://github.com/itsab1989/ChromIQ/issues/new"


class TranslationDialog(QDialog):
    """Export / import the UI language as a spreadsheet."""

    def __init__(self, settings: "AppSettings", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(tr("Translate / edit language"))
        self.setMinimumWidth(640)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        # Tab-style masthead (eyebrow + serif title + ⓘ) over a full-width
        # spectrum stripe, matching the chart-design windows. The outer layout
        # spans full width so the stripe bleeds to the edges; the content below
        # re-adds the side inset.
        body_text = tr(
            "Export every phrase in ChromIQ to a spreadsheet, translate the "
            "right-hand column in Excel, LibreOffice or Google Sheets, then "
            "import the file back. Imported translations apply after a restart "
            "and are saved to your personal ChromIQ folder — your edits survive "
            "app updates."
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head, _header, stripe = dialog_masthead(
            self, tr("LANGUAGE · TRANSLATE"), tr("Translate / edit language"),
            tooltip_title=tr("Translate / edit language"), tooltip_body=body_text)
        root.addLayout(head)
        root.addWidget(stripe)

        outer = QVBoxLayout()
        outer.setContentsMargins(22, 14, 22, 16)
        outer.setSpacing(12)
        root.addLayout(outer)

        body = QLabel(body_text, self)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.PlainText)
        outer.addWidget(body)

        # ---- target language ------------------------------------------------
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("Language:"), self))
        self._lang_combo = NoScrollComboBox(self)
        for code, name in available_languages():
            if code == SOURCE_LANGUAGE:
                continue  # English is the source — nothing to translate into it
            self._lang_combo.addItem(f"{name} ({code})", code)
        self._lang_combo.addItem(tr("New language…"), _NEW_LANG)
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        lang_row.addWidget(self._lang_combo, 1)
        outer.addLayout(lang_row)

        # New-language code + native name (hidden unless "New language…")
        self._new_row = QWidget(self)
        nr = QHBoxLayout(self._new_row)
        nr.setContentsMargins(0, 0, 0, 0)
        nr.addWidget(QLabel(tr("Code:"), self._new_row))
        self._code_edit = QLineEdit(self._new_row)
        self._code_edit.setPlaceholderText(tr("e.g. fi or pt_BR"))
        self._code_edit.setMaximumWidth(120)
        nr.addWidget(self._code_edit)
        nr.addWidget(QLabel(tr("Native name:"), self._new_row))
        self._name_edit = QLineEdit(self._new_row)
        self._name_edit.setPlaceholderText(tr("e.g. Suomi"))
        nr.addWidget(self._name_edit, 1)
        self._new_row.setVisible(False)
        outer.addWidget(self._new_row)

        outer.addWidget(self._hline())

        # ---- export ---------------------------------------------------------
        outer.addWidget(self._section_label(tr("1.  Export a spreadsheet to edit")))
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(tr("Format:"), self))
        self._csv_radio = QRadioButton("CSV", self)
        self._xlsx_radio = QRadioButton("Excel (XLSX)", self)
        self._xlsx_radio.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._csv_radio)
        grp.addButton(self._xlsx_radio)
        fmt_row.addWidget(self._csv_radio)
        fmt_row.addWidget(self._xlsx_radio)
        fmt_row.addStretch(1)
        export_btn = QPushButton(tr("Export…"), self)
        export_btn.clicked.connect(self._on_export)
        fmt_row.addWidget(export_btn)
        outer.addLayout(fmt_row)

        outer.addWidget(self._hline())

        # ---- import ---------------------------------------------------------
        outer.addWidget(self._section_label(tr("2.  Import your edited spreadsheet")))
        imp_row = QHBoxLayout()
        imp_note = QLabel(tr(
            "Pick the CSV or XLSX file you edited. ChromIQ checks it and tells "
            "you how many phrases were translated before saving."
        ), self)
        imp_note.setWordWrap(True)
        imp_row.addWidget(imp_note, 1)
        import_btn = QPushButton(tr("Import…"), self)
        import_btn.clicked.connect(self._on_import)
        imp_row.addWidget(import_btn, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(imp_row)

        # ---- status + buttons ----------------------------------------------
        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #888;")
        outer.addWidget(self._status)

        bb = QDialogButtonBox(self)
        send_btn = bb.addButton(tr("Send to developer…"),
                                QDialogButtonBox.ButtonRole.ActionRole)
        send_btn.clicked.connect(self._on_send)
        close_btn = bb.addButton(tr("Close"), QDialogButtonBox.ButtonRole.RejectRole)
        close_btn.clicked.connect(self.reject)
        outer.addWidget(bb)

        # Neutral indicators, but the dropdown wears this window's own accent —
        # dialog_masthead's default magenta, which is the stroke drawn above.
        self.setStyleSheet(
            neutral_controls_qss(_indicator_color(settings), popup=SPEC_MAGENTA))

    # ------------------------------------------------------------------
    def _hline(self) -> QFrame:
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        return sep

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setStyleSheet("font-weight: bold;")
        return lbl

    def _on_lang_changed(self) -> None:
        self._new_row.setVisible(self._lang_combo.currentData() == _NEW_LANG)

    # ------------------------------------------------------------------
    def _resolve_target(self) -> tuple[str, str | None] | None:
        """(code, native_name|None) for the selected language, or None if the
        new-language inputs are incomplete/invalid (a message is shown)."""
        data = self._lang_combo.currentData()
        if data != _NEW_LANG:
            return data, None
        code = self._code_edit.text().strip()
        name = self._name_edit.text().strip()
        if not code or not name:
            self._warn(tr("Enter a language code and native name for the new language."))
            return None
        # Accept "xx" or "xx_YY" — the same shape as the bundled catalog codes.
        import re
        if not re.fullmatch(r"[A-Za-z]{2,3}(_[A-Za-z]{2})?", code):
            self._warn(tr(
                "“{code}” is not a valid language code. Use two letters such as "
                "“fi”, optionally with a region like “pt_BR”."
            ).format(code=code))
            return None
        return code, name

    # ------------------------------------------------------------------
    def _on_export(self) -> None:
        target = self._resolve_target()
        if target is None:
            return
        code, name = target
        is_xlsx = self._xlsx_radio.isChecked()
        ext = ".xlsx" if is_xlsx else ".csv"
        default_path = str(Path.home() / f"ChromIQ-{code}{ext}")
        chosen = save_file_dialog(
            self, tr("Save translation spreadsheet"),
            (tr("Excel files (*.xlsx)") if is_xlsx else tr("CSV files (*.csv)")),
            start_path=default_path,
        )
        if not chosen:
            return
        path = Path(chosen)
        # By name: a typed "catalogue v1.2" has a "suffix" of ".2", and
        # with_suffix() would REPLACE it (core/stem_paths.py).
        if not path.name.lower().endswith(ext):
            path = artefact(path, ext)
        try:
            rows = rt.build_rows(code, language_name=name)
            if is_xlsx:
                rt.write_xlsx(rows, path)
            else:
                rt.write_csv(rows, path)
        except Exception as exc:
            log.exception("Export failed")
            self._warn(tr("Could not write the file:\n{error}").format(error=exc))
            return
        n = sum(1 for r in rows if r.section in ("ui", "param"))
        self._status.setText(tr(
            "Exported {count} phrases to {path}. Open it in a spreadsheet, fill "
            "in the translation column, then use Import below."
        ).format(count=n, path=path.name))
        reveal_in_file_manager(path.parent)

    # ------------------------------------------------------------------
    def _on_import(self) -> None:
        target = self._resolve_target()
        if target is None:
            return
        code, _name = target
        chosen = open_file_dialog(
            self, tr("Choose your edited spreadsheet"),
            tr("Spreadsheets (*.csv *.xlsx)"),
            start_dir=str(Path.home()),
        )
        if not chosen:
            return
        try:
            rows = rt.read_rows(chosen)
            json_dict, yaml_dict, report = rt.apply_rows(code, rows)
        except Exception as exc:
            log.exception("Import failed")
            self._warn(tr("Could not read the file:\n{error}").format(error=exc))
            return

        if report.code_mismatch:
            keep = confirm(
                self, tr("Different language"),
                tr(
                    "This file was exported for “{sheet}”, but you selected "
                    "“{chosen}”. Import it as “{chosen}” anyway?"
                ).format(sheet=report.code_mismatch, chosen=code),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if keep != QMessageBox.StandardButton.Yes:
                return

        if report.has_errors:
            self._warn(self._error_text(report))
            return

        summary = self._summary_text(report)
        if confirm(
            self, tr("Import translation"), summary + "\n\n" + tr("Save now?"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Save:
            return

        try:
            out = rt.save_translation(code, json_dict, yaml_dict)
        except Exception as exc:
            log.exception("Saving imported translation failed")
            self._warn(tr("Could not save the translation:\n{error}").format(error=exc))
            return

        self._status.setText(tr("Saved to {path}.").format(path=str(out)))
        inform(
            self, tr("Import translation"),
            tr(
                "Translation saved. Restart ChromIQ and choose “{code}” under "
                "Preferences → Language to see your changes."
            ).format(code=code),
        )

    # ------------------------------------------------------------------
    def _on_send(self) -> None:
        target = self._resolve_target()
        code = target[0] if target else self._lang_combo.currentData()
        if code == _NEW_LANG:
            code = ""
        title = f"[Translation] {code}".strip()
        bodylines = [
            "Thanks for contributing a translation!",
            "",
            f"Language code: {code or '(fill in)'}",
            f"ChromIQ version: {APP_VERSION}",
            "",
            "Please drag your exported CSV or XLSX file into this issue to "
            "attach it, then submit.",
        ]
        url = (
            f"{_ISSUES_NEW}?labels=translation"
            f"&title={quote(title)}&body={quote(chr(10).join(bodylines))}"
        )
        QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------------
    def _summary_text(self, report: "rt.Report") -> str:
        translated = (
            tr("1 phrase translated") if report.translated == 1
            else tr("{count} phrases translated").format(count=report.translated)
        )
        missing = (
            tr("1 phrase still untranslated (English will be used)")
            if report.missing == 1
            else tr("{count} phrases still untranslated (English will be used)")
            .format(count=report.missing)
        )
        return f"{translated}\n{missing}"

    def _error_text(self, report: "rt.Report") -> str:
        lines = [tr("The file can't be imported yet:"), ""]
        if report.placeholder_errors:
            sample = ", ".join(report.placeholder_errors[:5])
            n = len(report.placeholder_errors)
            lines.append(
                tr("1 phrase changed a placeholder — keep the parts in curly "
                   "braces exactly as in the English text:")
                if n == 1 else
                tr("{count} phrases changed a placeholder — keep the parts in curly "
                   "braces exactly as in the English text:").format(count=n)
            )
            lines.append(sample)
            lines.append("")
        if report.label_errors:
            sample = ", ".join(report.label_errors[:5])
            n = len(report.label_errors)
            lines.append(
                tr("1 list of choices is incomplete — translate every option or "
                   "leave them all blank:")
                if n == 1 else
                tr("{count} lists of choices are incomplete — translate every option "
                   "or leave them all blank:").format(count=n)
            )
            lines.append(sample)
        return "\n".join(lines)

    def _warn(self, text: str) -> None:
        warn(self, tr("Translate / edit language"), text)
