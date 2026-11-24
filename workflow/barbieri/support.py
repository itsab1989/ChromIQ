"""THE ONE SWITCH FOR BARBIERI SPECTRO 100xy CHARTS (Preferences > Beta).

The Barbieri Spectro 100xy is an XY table that carries a spectrophotometer
head from patch to patch. It reads a chart BY COORDINATES: its own program
(Spectro32, or Barbieri's later Gateway) is told where the patch grid is and
how many patches it has, the person aims the head at one patch (Spectro32) or
at three corners (Gateway), and the table then visits every patch in a fixed
order. ChromIQ cannot talk to it yet (ArgyllCMS has no Barbieri driver), so
this Beta MAKES charts for it: a plain patch grid, sized for the measuring
opening, laid out by ChromIQ's own layout engine, with marks to aim at and the
grid numbers the vendor programs ask for. Bringing the measurement back into
ChromIQ comes in a later step.

The switch is OFF by default, and with it off ChromIQ behaves exactly as it
did before: no Barbieri entry in any list, no Barbieri code loaded, no chart
file read to find out whether it is a Barbieri chart, and no new key in any
target's ``meta.json``. Every hook in shared code asks
:func:`barbieri_enabled` first (``tests/test_barbieri_off_changes_nothing.py``).

**Restart to apply**, like the other instrument Betas: the value is read ONCE
per process (``main()`` latches it before the window is built).

**Names.** One Create Chart entry, ``B100XY``, "Barbieri Spectro 100xy". The
chart files carry the vendor and model in ``TARGET_INSTRUMENT``; the measuring
opening chosen is recorded in the chart's side file and a ``.ti2`` keyword.
"""

from __future__ import annotations

from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "barbieri_chart_beta"

#: The Create Chart instrument code.
CODE = "B100XY"

#: Every Create Chart code that is a Barbieri entry (one).
CODES: "frozenset[str]" = frozenset({CODE})

#: What the Instrument lists show for it.
LABEL = "Barbieri Spectro 100xy"

#: The friendly name in the margin-threshold table (Preferences > Instrument
#: Limits).
THRESHOLD_LABEL = "Barbieri 100xy (Beta)"

#: The name every Barbieri chart carries in ``TARGET_INSTRUMENT``.
TARGET_INSTRUMENT = "Barbieri Spectro 100xy"

#: The suffix of the chart's side file (``<stem>.barbieri.json``).
SIDE_SUFFIX = ".barbieri.json"

_latched: "bool | None" = None


def stored_value(settings: Any) -> bool:
    """What Preferences holds now (it may differ from the running value)."""
    try:
        return bool(settings.get(SETTING, False))
    except Exception:  # noqa: BLE001 - a broken store means "off"
        return False


def latch_from(settings: Any) -> bool:
    """Fix the running value from *settings*. Called once by ``main()``."""
    global _latched
    _latched = stored_value(settings)
    return _latched


def barbieri_enabled() -> bool:
    """True when Barbieri charts are on for THIS run of ChromIQ (read once)."""
    global _latched
    if _latched is None:
        try:
            from core.settings import AppSettings
            _latched = stored_value(AppSettings())
        except Exception:  # noqa: BLE001
            _latched = False
    return _latched


def set_enabled_for_this_process(value: "bool | None") -> None:
    """Tests and drivers only: set the running value (None = read again)."""
    global _latched
    _latched = None if value is None else bool(value)


def is_barbieri_code(code: Any) -> bool:
    """True for a Create Chart instrument code that is the Barbieri entry."""
    return str(code or "") in CODES


def is_barbieri_instrument_name(name: "str | None") -> bool:
    """True for a CHART's ``TARGET_INSTRUMENT`` naming the Barbieri Spectro
    100xy as ChromIQ writes it (any case, with or without CGATS quotes)."""
    text = str(name or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    folded = " ".join(text.casefold().split())
    return folded == TARGET_INSTRUMENT.casefold()


def chart_names_barbieri(path: Any) -> "bool | None":
    """Whether the chart file at *path* names the Barbieri in
    ``TARGET_INSTRUMENT``. None when there is no chart file. Never raises:
    a file that cannot be read is not a Barbieri chart. Only the header BYTES
    are read (a chart made on a German Windows is cp1252)."""
    from pathlib import Path
    try:
        p = Path(path)
        if not p.is_file():
            return None
        with open(p, "rb") as f:
            head = f.read(65536)
    except (OSError, TypeError, ValueError):
        return None if path is None else False
    head = head.split(b"BEGIN_DATA_FORMAT", 1)[0]
    for raw in head.splitlines():
        line = raw.strip()
        if line[:17].upper() == b"TARGET_INSTRUMENT" and (
                len(line) == 17 or line[17:18] in (b" ", b"\t")):
            return is_barbieri_instrument_name(
                line[17:].strip().decode("latin-1"))
    return False


def side_file_for(ti2_path: Any):
    """The ``<stem>.barbieri.json`` beside a ``<stem>.ti2`` (a Path; it may
    not exist)."""
    from pathlib import Path
    p = Path(ti2_path)
    name = p.name[:-4] if p.name.lower().endswith(".ti2") else p.name
    return p.with_name(name + SIDE_SUFFIX)


def read_side_file(ti2_path: Any) -> "dict | None":
    """The chart's side file as a dict, or None. Never raises."""
    import json
    try:
        doc = json.loads(side_file_for(ti2_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return doc if isinstance(doc, dict) else None


# ---- a target made with the Beta on, opened with it off --------------------
#
# The shared carry rules (`workflow.beta_chart_carry`), as for the i1iO and
# the i1iSis: with the switch off the tab shows the instrument it falls back
# to, which is not the user's choice, so the target's stored Barbieri values
# are put back over it when the target is written, and an untouched project's
# `meta.json` stays byte-identical.

CHART_PARAM_KEYS = ("printtarg-i", "printtarg-p")
CHART_GUIDED_KEYS = ("instrument", "paper", "pages", "barbieri_head")
CHART_RECIPE_KEYS = ("instrument", "paper", "border", "margin_top",
                     "margin_right", "margin_bottom", "margin_left",
                     "use_instrument_margins", "patch_w_mm", "patch_h_mm",
                     "layout_mode", "inter_patch_mm", "strip_gap_mm",
                     "barbieri_head", "barbieri_check_patches",
                     "barbieri_marks", "barbieri_size", "page_size",
                     "tiff_res_unit", "dpi")


def target_names_barbieri(stored_params: "dict | None",
                          stored_ui: "dict | None") -> bool:
    """True when a target's stored Create Chart block names the Barbieri."""
    from workflow.beta_chart_carry import target_names
    return any(target_names(code, stored_params, stored_ui) for code in CODES)


def carry_barbieri_chart_keys(wanted, ui_state, stored_params, stored_ui,
                              screen_at_load=None, own=None) -> set:
    """`workflow.beta_chart_carry.carry_chart_keys` for the Barbieri."""
    from workflow.beta_chart_carry import carry_chart_keys
    users: set = set()
    for code in sorted(CODES):
        users |= carry_chart_keys(code, barbieri_enabled(), wanted, ui_state,
                                  stored_params, stored_ui, screen_at_load,
                                  own, param_keys=CHART_PARAM_KEYS,
                                  guided_keys=CHART_GUIDED_KEYS,
                                  recipe_keys=CHART_RECIPE_KEYS)
    return users


def off_snapshot(screen_params, screen_ui, stored_params, stored_ui):
    """A Barbieri target as the switch-off tab opened it."""
    from workflow.beta_chart_carry import OffSnapshot

    class BarbieriOffSnapshot(OffSnapshot):
        __slots__ = ()

        def carry(self, wanted, ui_state):
            return carry_barbieri_chart_keys(wanted, ui_state, self.stored[0],
                                             self.stored[1], self.screen,
                                             self.own)

        def chart_names(self, path):
            return chart_names_barbieri(path)

    return BarbieriOffSnapshot(screen_params, screen_ui, stored_params,
                               stored_ui)
