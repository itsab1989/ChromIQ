"""Tools → "Apply a device-link to an image" (cctiff wrapper).

Pushes one or more images through an ICC **device-link** (built by the "Create
device-link profile" tool) with ``cctiff``, writing a **printer-native TIFF**
next to each image (``<name>-printready.tif``). That file is already in the
printer's colour space with no embedded profile, so it should be printed *raw*
— the same way ChromIQ prints test charts, with the driver's colour management
off — or handed to a RIP. This deliberately avoids the print pipeline so it
works cross-platform and doesn't depend on the raw-print path.

**Source-space auto-fix:** a device-link bakes in a specific source colour space
and ``cctiff`` ignores the image's embedded profile, so the image must be in that
space. When the link carries a ``<name>.source.icc`` sidecar (ChromIQ writes one
next to every link it builds), this tool reads each image's embedded profile and,
if it differs, converts the image into the link's source space first. Third-party
links without a sidecar fall back to a plain warning.

Follows the shared Tools-dialog chrome (:class:`_ToolDialogBase`): amber masthead
(the print-family accent), a ⓘ help button per option, ChromIQ's own non-native
file pickers with image preview.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
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
from ui.styles import SPEC_AMBER
from ui.theme import accent_for, resolve_mode
from ui.tooltip_button import TooltipButton
from ui.widgets import (
    disabled_primary_qss,
    primary_hover,
    primary_label,
    confirm,
    icc_profile_paths,
    load_folder_icon,
    make_browse_button,
    open_file_dialog,
    open_files_dialog,
)
from workflow.cctiff_apply import convert_args, link_args
from workflow.icc_convert import NotConvertible, to_v2
from workflow.icc_info import IccParseError, is_v4

log = get_logger(__name__)

_ICC_FILTER = "ICC profiles (*.icc *.icm);;All files (*)"
_IMG_FILTER = "Images (*.tif *.tiff *.jpg *.jpeg);;All files (*)"


def _embedded_icc(image_path: Path) -> bytes | None:
    """The image's embedded ICC profile bytes, or None if it has none."""
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            return im.info.get("icc_profile")
    except Exception:  # noqa: BLE001 — unreadable/odd file → treat as "no profile"
        return None


class DeviceLinkApplyDialog(_ToolDialogBase):
    TOOL_KEY  = "devicelink_apply"
    TITLE     = tr("Apply a device-link to an image")
    EYEBROW   = tr("PROFILES · APPLY DEVICE-LINK")
    ACCENT    = SPEC_AMBER
    RUN_LABEL = tr("Apply && save")   # && → a literal ampersand (Qt mnemonic escape)
    MIN_WIDTH = 700

    HELP = (
        tr("Applies a device-link profile (built with 'Create device-link "
        "profile') to your images and saves a printer-ready file next to each "
        "one — <name>-printready.tif.\n\n"
        "That file is already in your printer's own colours, with no profile "
        "attached. Print it 'raw' — the same way ChromIQ prints a test chart, "
        "with the printer's colour management switched OFF — or load it in your "
        "RIP. Don't let Photoshop or the printer driver convert it again, or the "
        "colours will be transformed twice.\n\n"
        "Why not just print through Photoshop? Because some printer drivers "
        "quietly re-apply colour management even when you ask for 'no "
        "correction', which double-converts the link's output. Printing the "
        "file raw sidesteps that entirely."))
    DESCRIPTION = (
        tr("Apply a device-link to your images and save a printer-ready TIFF "
        "next to each — to print raw (colour management off) or load in a RIP."))

    def __init__(self, runner, settings, parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._runner = runner
        self._link_path: Path | None = None
        self._src_profile: Path | None = None   # link's source space (sidecar/manual)
        self._image_paths: list[Path] = []
        self._temp_dir: Path | None = None
        self._temp_files: list[Path] = []
        self._jobs: list[dict] = []
        self._build_inputs()
        self._autofill_last_link()
        self._run_btn.setObjectName("primary")
        self.setStyleSheet(self.styleSheet() + neutral_controls_qss(SPEC_AMBER))
        self._style_primary_button()
        self._refresh()

    def _style_primary_button(self) -> None:
        """Amber primary button, mirroring the other tools: filled when ready,
        muted with an amber accent border when required fields aren't filled."""
        mode = resolve_mode(self._settings.get("appearance", "auto"))
        c = accent_for(SPEC_AMBER, mode)
        hover = primary_hover(c, mode, 0.86)
        label = primary_label(mode)
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background: {c}; border: 1px solid {c}; color: {label};"
            f" font-weight: 700; }}"
            f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
            + disabled_primary_qss(c, mode))

    # ------------------------------------------------------------------ UI
    def _tip(self, title: str, body: str, min_width: int = 500) -> TooltipButton:
        return TooltipButton(title, body, self, min_width=min_width, color=SPEC_AMBER)

    def _label_row(self, layout: QVBoxLayout, text: str, tip_title: str, tip_body: str) -> None:
        head = QHBoxLayout()
        head.addWidget(QLabel(text, self))
        head.addStretch(1)
        head.addWidget(self._tip(tip_title, tip_body), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(head)

    def _file_row(self, layout: QVBoxLayout, placeholder: str, on_pick) -> QLineEdit:
        row = QHBoxLayout()
        field = QLineEdit(self)
        field.setReadOnly(True)
        field.setPlaceholderText(placeholder)
        row.addWidget(field, 1)
        browse = make_browse_button(self, tr("Browse…"), icon="folder_print")
        browse.clicked.connect(on_pick)
        row.addWidget(browse)
        layout.addLayout(row)
        return field

    def _build_inputs(self) -> None:
        form = self._content

        self._label_row(
            form, tr("Device-link profile:"), tr("Device-link profile"),
            tr("The device-link you built with 'Create device-link profile'. It "
            "bakes in a fixed source→printer conversion. If you built it here, "
            "ChromIQ also knows which colour space it expects and can prepare "
            "your images accordingly."))
        self._link_field = self._file_row(
            form, tr("Pick a device-link .icc (auto-filled from the last one built)…"),
            self._pick_link)

        self._label_row(
            form, tr("Link's source colour space (optional):"),
            tr("Link's source colour space"),
            tr("The colour space the link was built for (e.g. sRGB, AdobeRGB, "
            "ProPhoto). ChromIQ fills this in automatically for links built here. "
            "When it's set, any image that's in a different space is converted "
            "into it first, so the result is correct even if your image wasn't "
            "already in the link's source space. Leave empty only if you're sure "
            "your images are already in it."))
        self._src_field = self._file_row(
            form, tr("Auto-filled for links built in ChromIQ…"), self._pick_source)

        self._note = QLabel("", self)
        self._note.setWordWrap(True)
        self._note.setStyleSheet("color: palette(mid); font-size: 12px;")
        form.addWidget(self._note)

        self._label_row(
            form, tr("Images to convert:"), tr("Images"),
            tr("The images to run through the link. They should be in the link's "
            "source colour space (ChromIQ converts them for you when it knows "
            "that space). Add a whole set at once — each is processed the same "
            "way. TIFF and JPEG are supported."))
        self._image_list = QListWidget(self)
        self._image_list.setMaximumHeight(150)
        self._image_list.itemSelectionChanged.connect(self._on_image_selection)
        form.addWidget(self._image_list)

        _COMPACT = "QPushButton { min-height: 24px; max-height: 24px; padding: 2px 12px; }"
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 2, 0, 6)
        self._img_add = QPushButton(tr("Add images…"), self)
        self._img_add.setStyleSheet(_COMPACT)
        self._img_add.setIcon(load_folder_icon("folder_print"))
        self._img_add.setIconSize(QSize(14, 14))
        self._img_add.clicked.connect(self._pick_images)
        self._img_remove = QPushButton(tr("Remove"), self)
        self._img_remove.setStyleSheet(_COMPACT)
        self._img_remove.setEnabled(False)
        self._img_remove.clicked.connect(self._remove_selected_images)
        btns.addWidget(self._img_add)
        btns.addWidget(self._img_remove)
        btns.addStretch(1)
        form.addLayout(btns)

        out_note = QLabel(
            tr("Each result is saved next to its image with a “-printready” "
            "suffix. Print it raw — the same way you print a test chart, with the "
            "printer's colour management off — or load it in your RIP."), self)
        out_note.setWordWrap(True)
        out_note.setStyleSheet("color: palette(mid); font-size: 12px;")
        form.addWidget(out_note)

    def _refresh_note(self) -> None:
        if self._src_profile is not None:
            self._note.setText(tr(
                "✓ Source space known: images in a different space are converted "
                "into it automatically."))
        elif self._link_path is not None:
            self._note.setText(tr(
                "⚠ This link's source colour space is unknown — make sure your "
                "images are already in it, or pick the source profile above."))
        else:
            self._note.setText("")

    # --------------------------------------------------------------- pickers
    def _pick_link(self) -> None:
        path = open_file_dialog(
            self, tr("Choose device-link profile"), _ICC_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
            extra_paths=tuple(icc_profile_paths()))
        if not path:
            return
        self._set_link(Path(path))

    def _set_link(self, link: Path) -> None:
        self._link_path = link
        self._link_field.setText(str(link))
        _remember_dir(self._settings, self.TOOL_KEY, link.parent)
        # Auto-detect the source-space sidecar written next to ChromIQ links.
        sidecar = link.with_name(link.stem + ".source.icc")
        if sidecar.exists():
            self._src_profile = sidecar
            self._src_field.setText(str(sidecar))
        self._refresh_note()
        self._refresh()

    def _pick_source(self) -> None:
        path = open_file_dialog(
            self, tr("Choose the link's source colour space"), _ICC_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)),
            extra_paths=tuple(icc_profile_paths()))
        if path:
            self._src_profile = Path(path)
            self._src_field.setText(path)
            self._refresh_note()

    def _pick_images(self) -> None:
        paths = open_files_dialog(
            self, tr("Choose images to convert"), _IMG_FILTER,
            start_dir=str(_initial_dir(self._settings, self.TOOL_KEY)), preview=True)
        if not paths:
            return
        added = False
        for s in paths:
            p = Path(s)
            if p not in self._image_paths:
                self._image_paths.append(p)
                item = QListWidgetItem(p.name)
                item.setData(Qt.ItemDataRole.UserRole, str(p))
                item.setToolTip(str(p))
                self._image_list.addItem(item)
                added = True
        if added:
            _remember_dir(self._settings, self.TOOL_KEY, Path(paths[0]).parent)
            self._refresh()

    def _remove_selected_images(self) -> None:
        for item in self._image_list.selectedItems():
            p = Path(item.data(Qt.ItemDataRole.UserRole))
            if p in self._image_paths:
                self._image_paths.remove(p)
            self._image_list.takeItem(self._image_list.row(item))
        self._refresh()

    def _on_image_selection(self) -> None:
        self._img_remove.setEnabled(bool(self._image_list.selectedItems()))

    def _autofill_last_link(self) -> None:
        last = str(self._settings.get("devicelink_last_link", ""))
        if last and Path(last).exists():
            self._set_link(Path(last))

    # --------------------------------------------------------------- run
    def _can_run(self) -> bool:
        return self._link_path is not None and bool(self._image_paths)

    def _tempfile(self, ext: str) -> Path:
        if self._temp_dir is None:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="chromiq_dlapply_"))
        p = self._temp_dir / f"t{len(self._temp_files)}{ext}"
        self._temp_files.append(p)
        return p

    def _source_for_image(self, img: Path, warnings: list[str]) -> Path | None:
        """A v2 profile describing the image's actual colour space, ready to feed
        cctiff — or None if it needs no conversion / can't be converted."""
        if self._src_profile is None:
            return None
        emb = _embedded_icc(img)
        if emb is None:
            return None                         # no embedded profile → assume source
        try:
            if emb == self._src_profile.read_bytes():
                return None                     # already the link's source
        except OSError:
            return None
        p_icc = self._tempfile(".icc")
        p_icc.write_bytes(emb)
        try:
            if is_v4(p_icc):
                v2 = to_v2(p_icc)
                self._temp_files.append(Path(v2))
                return Path(v2)
            return p_icc
        except NotConvertible:
            warnings.append(tr(
                "Skipped {name}: its embedded profile is an ICC v4 profile ChromIQ "
                "can't convert — convert the image to the link's source space in "
                "your editor first.").format(name=img.name))
            return "skip"  # sentinel
        except IccParseError:
            return None    # unreadable embedded profile → apply link directly

    def _build_jobs(self):
        jobs: list[dict] = []
        warnings: list[str] = []
        for img in self._image_paths:
            out = img.parent / f"{img.stem}-printready.tif"
            conv = self._source_for_image(img, warnings)
            if conv == "skip":
                continue
            label = tr("Applying the device-link to {name}…").format(name=img.name)
            if conv is not None:
                tmp = self._tempfile(".tif")
                jobs.append(dict(
                    args=convert_args(conv, self._src_profile, img, tmp), out=tmp,
                    final=False,
                    label=tr("Converting {name} to the link's source space…"
                             ).format(name=img.name)))
                jobs.append(dict(args=link_args(self._link_path, tmp, out),
                                 out=out, final=True, label=label))
            else:
                jobs.append(dict(args=link_args(self._link_path, img, out),
                                 out=out, final=True, label=label))
        return jobs, warnings

    def _execute(self) -> None:
        if self._runner.is_running:
            self._log.appendPlainText(tr("[BUSY] Another operation is running — please wait."))
            self._finish(False)
            return
        assert self._link_path is not None
        outs = [img.parent / f"{img.stem}-printready.tif" for img in self._image_paths]
        existing = [o for o in outs if o.exists()]
        if existing:
            choice = confirm(
                self, tr("Overwrite existing files?"),
                tr("Printer-ready files already exist next to some of your images "
                   "and will be overwritten. Continue?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                self._finish(False)
                return

        self._log.clear()
        self._temp_dir = None
        self._temp_files = []
        self._jobs, warnings = self._build_jobs()
        for w in warnings:
            self._log.appendPlainText(f"[WARNING] {w}")
        if not self._jobs:
            self._cleanup_temps()
            self._log.appendPlainText(tr("Nothing to convert — see messages above."))
            self._finish(False)
            return
        self._run_job(0)

    def _run_job(self, i: int) -> None:
        if i >= len(self._jobs):
            self._cleanup_temps()
            self._log.appendPlainText(
                tr("Done — printer-ready files saved next to your images."))
            self._finish(True)
            return
        job = self._jobs[i]
        self._log.appendPlainText(job["label"])

        def _on_finish(code: int) -> None:
            if code != 0 or (job["final"] and not job["out"].exists()):
                self._cleanup_temps()
                self._log.appendPlainText(
                    tr("[ERROR] cctiff failed — see messages above."))
                self._finish(False)
                return
            if job["final"]:
                self._log.appendPlainText(tr("[OK] Wrote {path}").format(path=job["out"]))
                _remember_dir(self._settings, self.TOOL_KEY, job["out"].parent)
            self._run_job(i + 1)

        self._runner.run("cctiff", job["args"], job["out"].parent,
                         on_line=lambda ln: self._log_line(ln), on_finish=_on_finish)

    def _log_line(self, line: str) -> None:
        text = line.rstrip()
        if text and not text.endswith("%"):
            self._log.appendPlainText(text)
            self._log.ensureCursorVisible()

    def _cleanup_temps(self) -> None:
        for p in self._temp_files:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None
        self._temp_files = []

    def reject(self) -> None:  # noqa: D102
        self._cleanup_temps()
        super().reject()
