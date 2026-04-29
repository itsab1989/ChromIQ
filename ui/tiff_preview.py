"""Multi-page TIFF preview widget with stripe highlight overlay."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image
from PyQt6.QtCore import QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger

log = get_logger(__name__)

_REFRESH_DELAY_MS = 80   # debounce repaint
_BORDER = 15             # white display border: all sides (px)


class TiffPreview(QWidget):
    """Displays multi-page TIFF files with optional stripe highlight overlay."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pages: list[tuple[Path, int]] = []   # (file_path, frame_index)
        self._current: int = 0
        self._active_stripe: int = -1
        self._stripe_rects: list[QRect] = []
        self._pixmap: QPixmap | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(_REFRESH_DELAY_MS)
        self._refresh_timer.timeout.connect(self._update_display)

        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_tiff(self, paths: list[Path]) -> None:
        """Load a list of TIFF pages (one entry per printable page)."""
        self._pages = []
        for p in paths:
            try:
                img = Image.open(p)
                n_frames = getattr(img, "n_frames", 1)
                for i in range(n_frames):
                    self._pages.append((p, i))
            except Exception as exc:
                log.warning("Cannot open TIFF %s: %s", p, exc)

        if not self._pages and paths:
            log.warning("TiffPreview: received %d path(s) but none could be opened: %s",
                        len(paths), [str(p) for p in paths])

        self._current = 0
        self._active_stripe = -1
        self._stripe_rects = []
        self._update_nav()
        # Fire immediately (after pending events) then again after 80ms for resize
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._update_display)
        self._schedule_refresh()
        log.debug("TiffPreview: loaded %d page(s)", len(self._pages))

    def highlight_stripe(self, stripe_index: int) -> None:
        """Highlight a strip (0-based) in the current preview page."""
        self._active_stripe = stripe_index
        self._schedule_refresh()

    def set_stripe_rects(self, rects: list[QRect]) -> None:
        """Provide precomputed pixel rects for each stripe on current page."""
        self._stripe_rects = rects

    def show_page(self, index: int) -> None:
        """Switch to page by index and repaint."""
        if 0 <= index < len(self._pages) and index != self._current:
            self._current = index
            self._active_stripe = -1
            self._update_nav()
            self._schedule_refresh()

    def clear(self) -> None:
        self._pages = []
        self._current = 0
        self._active_stripe = -1
        self._stripe_rects = []
        self._pixmap = None
        self._img_label.setText("No preview")
        self._update_nav()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Image label
        self._img_label = QLabel("No preview", self)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._img_label.setStyleSheet(
            "background: #111111; border: 1px solid #333; color: #606060; font-family: 'Menlo';"
        )
        _lbl_font = self._img_label.font()
        _lbl_font.setCapitalization(QFont.Capitalization.AllUppercase)
        self._img_label.setFont(_lbl_font)
        self._img_label.setMinimumSize(200, 200)
        layout.addWidget(self._img_label, stretch=1)

        # Navigation bar
        nav = QWidget(self)
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(12, 0, 12, 0)

        self._prev_btn = QPushButton("‹ Prev", nav)
        self._prev_btn.setFixedWidth(84)
        self._prev_btn.clicked.connect(self._go_prev)
        nav_layout.addWidget(self._prev_btn)

        nav_layout.addStretch()
        self._page_label = QLabel("", nav)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("color: #909090; font-size: 12px;")
        nav_layout.addWidget(self._page_label)
        nav_layout.addStretch()

        self._next_btn = QPushButton("Next ›", nav)
        self._next_btn.setFixedWidth(84)
        self._next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self._next_btn)

        layout.addWidget(nav)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        if self._current > 0:
            self._current -= 1
            self._active_stripe = -1
            self._update_nav()
            self._schedule_refresh()

    def _go_next(self) -> None:
        if self._current < len(self._pages) - 1:
            self._current += 1
            self._active_stripe = -1
            self._update_nav()
            self._schedule_refresh()

    def _update_nav(self) -> None:
        n = len(self._pages)
        visible = n > 1
        self._prev_btn.setVisible(visible)
        self._next_btn.setVisible(visible)
        self._page_label.setVisible(n > 0)
        if n > 0:
            self._page_label.setText(f"Page {self._current + 1} / {n}")
        else:
            self._page_label.setText("")
        self._prev_btn.setEnabled(self._current > 0)
        self._next_btn.setEnabled(self._current < n - 1)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def _update_display(self) -> None:
        if not self._pages:
            self._img_label.setText("No preview")
            self._pixmap = None
            return

        path, frame = self._pages[self._current]
        try:
            img = Image.open(path)
            if hasattr(img, "seek"):
                try:
                    img.seek(frame)
                except EOFError:
                    pass
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            self._pixmap = self._pil_to_pixmap(img)
        except Exception as exc:
            log.warning("Preview render error: %s", exc)
            self._img_label.setText(f"Preview error:\n{exc}")
            return

        self._repaint_label()

    def _repaint_label(self) -> None:
        if not self._pixmap:
            return
        B = _BORDER
        dpr = self._img_label.devicePixelRatioF()
        label_size = self._img_label.size()  # logical pixels

        # Scale to device pixels so the preview is sharp on HiDPI/Retina displays
        avail = QSize(
            max(1, int((label_size.width()  - 2 * B) * dpr)),
            max(1, int((label_size.height() - 2 * B) * dpr)),
        )
        scaled = self._pixmap.scaled(
            avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)

        # Canvas at device pixel dimensions; DPR tells Qt the logical display size
        canvas = QPixmap(scaled.width() + int(2 * B * dpr),
                         scaled.height() + int(2 * B * dpr))
        canvas.setDevicePixelRatio(dpr)
        canvas.fill(Qt.GlobalColor.white)

        # Painter coordinates are logical (canvas has DPR set)
        painter = QPainter(canvas)
        painter.drawPixmap(B, B, scaled)

        if self._active_stripe >= 0 and self._stripe_rects:
            # sx/sy: device pixels per original image pixel
            sx = scaled.width()  / self._pixmap.width()
            sy = scaled.height() / self._pixmap.height()

            if self._active_stripe < len(self._stripe_rects):
                r   = self._stripe_rects[self._active_stripe]
                # Convert device-pixel coords → logical coords for painter
                x   = r.x()     * sx / dpr + B
                y   = r.y()     * sy / dpr + B + 3
                rw  = max(1.0, r.width() * sx / dpr + 2.0 / dpr)
                cx  = x + rw / 2
                arrow_h = 20  # logical pixels — constant visual size on all displays
                path = QPainterPath()
                path.moveTo(cx - rw / 2, y)
                path.lineTo(cx + rw / 2, y)
                path.lineTo(cx, y + arrow_h)
                path.closeSubpath()
                painter.fillPath(path, QColor("#56d6a5"))

        painter.end()
        self._img_label.setPixmap(canvas)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._repaint_label()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pil_to_pixmap(img: Image.Image) -> QPixmap:
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        px = QPixmap()
        if not px.loadFromData(buf.read()):
            raise RuntimeError(
                f"QPixmap.loadFromData failed for {img.size} {img.mode} image"
            )
        return px
