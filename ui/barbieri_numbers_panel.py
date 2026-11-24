"""The Barbieri Spectro 100xy numbers beside the chart (Create Chart, a Beta).

Built only while the Beta "Barbieri Spectro 100xy" is on, and shown only while
the chart in the preview is a Barbieri chart. It reads the chart's side file
(`workflow.barbieri.chart.write_side_file`) and shows what Barbieri's
programs ask for, so it can be typed in without working anything out:

* Spectro32's grid line for every page (spans from the first patch centre to
  the last, in 0.1 mm, then the columns and the rows), the measuring mode and
  the patch to aim at;
* Gateway's numbers: patches across and down, and the patch area from edge to
  edge in whole millimetres;
* the patch area, the pitch, the pages and the estimated reading time.

The grid lines can be selected and copied.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QVBoxLayout

from core.i18n import decimal_text, tr


def numbers_html(side: dict) -> str:
    """The panel's text for a side file (HTML, translated)."""
    import html
    from workflow.barbieri.chart import head_label, head_of
    head = head_of(side.get("head"))
    pitch = side.get("pitch_mm") or [0, 0]
    rows = []

    def line(name: str, value: str) -> None:
        rows.append(f"<tr><td style='color:#909090; padding-right:10px'>"
                    f"{html.escape(name)}</td><td>{value}</td></tr>")

    line(tr("Opening"), html.escape(tr("{opening} (Spectro32 {code})").format(
        opening=head_label(head), code=head.spectro32 or "?")))
    for pg in side.get("pages_detail") or []:
        gw = pg.get("gateway") or {}
        area = pg.get("patch_area_mm") or [0, 0]
        page = int(pg.get("page") or 1)
        # ON ITS OWN LINE, under its name: the one value that must never be
        # cut off in a narrow window
        rows.append(
            "<tr><td colspan='2' style='padding-top:4px'>"
            f"<span style='color:#909090'>{html.escape(tr('Page {page}, Spectro32').format(page=page))}</span><br>"
            "<span style='font-family: JetBrains Mono, Menlo, monospace'>"
            f"<b>{html.escape(str(pg.get('spectro32', '?')))}</b></span>"
            "</td></tr>")
        line(tr("Aim at"), html.escape(tr(
            "{aim}, the upper-right patch").format(aim=pg.get("aim_patch",
                                                             "?"))))
        line(tr("Page {page}, Gateway").format(page=page), html.escape(tr(
            "patches {cols} x {rows}, target size {gx} x {gy} mm").format(
                cols=gw.get("patches_x", "?"), rows=gw.get("patches_y", "?"),
                gx=gw.get("size_x_mm", "?"), gy=gw.get("size_y_mm", "?"))))
        line(tr("Patch area"), html.escape(tr("{w} x {h} mm").format(
            w=decimal_text(round(float(area[0]), 2)),
            h=decimal_text(round(float(area[1]), 2)))))
    line(tr("Pitch"), html.escape(tr("{x} x {y} mm").format(
        x=decimal_text(round(float(pitch[0]), 3)),
        y=decimal_text(round(float(pitch[1]), 3)))))
    pages = int(side.get("pages") or 1)
    line(tr("Pages"), str(pages))
    line(tr("Reading time"), html.escape(tr("about {minutes} min").format(
        minutes=int(side.get("reading_minutes") or 0))))
    return "<table cellspacing='0' cellpadding='1'>" + "".join(rows) \
        + "</table>"


class BarbieriNumbersPanel(QGroupBox):
    """The grid numbers of the Barbieri chart in the preview."""

    def __init__(self, parent=None) -> None:
        super().__init__(tr("Barbieri Spectro 100xy (Beta)"), parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 12, 10)
        v.setSpacing(4)
        head = QHBoxLayout()
        self._lead = QLabel(tr("What to type into Spectro32 or Gateway:"),
                            self)
        self._lead.setWordWrap(True)
        head.addWidget(self._lead, 1)
        from ui.tooltip_button import TooltipButton
        self._help = TooltipButton(
            tr("Barbieri grid numbers"), numbers_help(), self, min_width=560)
        head.addWidget(self._help)
        v.addLayout(head)
        self._body = QLabel("", self)
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body.setWordWrap(True)
        v.addWidget(self._body)
        self.setVisible(False)

    def show_chart(self, ti2) -> None:
        """Show the numbers of the chart at *ti2*, or hide the panel when it
        is no Barbieri chart (or has no readable side file)."""
        side = None
        try:
            from workflow.barbieri.support import (chart_names_barbieri,
                                                   read_side_file)
            if ti2 and chart_names_barbieri(ti2) is True:
                side = read_side_file(ti2)
        except Exception:      # noqa: BLE001 - a readout, never a blocker
            side = None
        if not side:
            self._body.setText("")
            self.setVisible(False)
            return
        self._body.setText(numbers_html(side))
        self._help.set_content(tr("Barbieri grid numbers"),
                               numbers_help(side))
        self.setVisible(True)


def corner_marks_printed(side: dict) -> bool:
    """Whether page 1 of the chart carries its corner marks (the side file's
    record of what was printed; an older side file: its marks switch)."""
    pages = side.get("pages_detail") or [{}]
    marks = pages[0].get("marks")
    if marks is None:
        return bool(side.get("marks_on", True))
    return bool(marks.get("bold_corner"))


def numbers_help(side: "dict | None" = None) -> str:
    """The help on the numbers; with a chart's side file it also says
    whether that chart's corner marks show Gateway's corners."""
    text = _numbers_help_base()
    if side is None:
        return text
    return text + " " + (tr(
        "On this chart the corner marks show those three corners.")
        if corner_marks_printed(side) else tr(
        "This chart has no corner marks printed, so aim Gateway at the "
        "outer corners of the corner patches."))


def _numbers_help_base() -> str:
    return tr(
        "Spectro32 asks for the grid as one line: R, then two offsets (0 here, "
        "because you aim the head by hand at the upper-right patch and save "
        "that position), then the span across and the span down, from the "
        "centre of the first patch to the centre of the last one, in 0.1 mm, "
        "then the number of columns and of rows. Barbieri Gateway asks "
        "instead for the patches across and down and the target size, the "
        "number of patches times the pitch in whole millimetres (the patch "
        "area from edge to edge when the patches have no gaps), and is aimed "
        "at three corners of the patch area. A chart "
        "of several pages has one line per page. The reading time is worked "
        "out from the datasheet's pace of about 1.9 seconds a patch.")
