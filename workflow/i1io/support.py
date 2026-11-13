"""THE ONE SWITCH FOR i1iO TABLE SUPPORT (Preferences > Beta).

The X-Rite i1iO is a motorised table that carries an i1Pro over a chart. This
first step only MAKES charts for it: ChromIQ sends nothing to any table. The
switch is OFF by default, and with it off ChromIQ must behave exactly as 4.3.32
did: no i1iO in any list, no i1iO code loaded, no chart file read to find out
whether it is an i1iO chart, and no new key in any target's ``meta.json``.
Every i1iO hook in shared code asks :func:`i1io_enabled` first, and
``tests/test_i1io_off_changes_nothing.py`` fails on a hook that does not.

**Restart to apply**, like the other instrument Betas: the instrument
lists are built once, so the value is read ONCE per process (``main()`` latches
it before the window is built).

**Names.** The Create Chart entry is generation-specific (``IO2``: an i1iO 2
with an i1Pro 2, the only pair we have data for); the chart FILES carry the
family name ``"X-Rite i1iO"`` and record the table generation and the head
separately (the ``.ti2`` keyword ``CHROMIQ_I1IO_TABLE`` and the side file), so
a later i1iO / i1iO 3 entry never renames a file already written.
"""

from __future__ import annotations

from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "i1io_support_beta"

#: The Create Chart instrument code of the one supported pair.
CODE = "IO2"

#: Every Create Chart code that is an i1iO entry (one today).
CODES: "frozenset[str]" = frozenset({CODE})

#: What the Instrument lists show for it (also `data.patch_db.
#: INSTRUMENT_LABELS` and `data/parameters.yaml`).
LABEL = "i1iO 2 + i1Pro 2"

#: The family name every i1iO chart carries in ``TARGET_INSTRUMENT``.
TARGET_INSTRUMENT = "X-Rite i1iO"

#: What this entry records as the table and the head.
TABLE_MODEL = "i1iO 2"
HEAD_MODEL = "i1Pro 2"

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


def i1io_enabled() -> bool:
    """True when i1iO support is on for THIS run of ChromIQ (read once)."""
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


def is_i1io_code(code: Any) -> bool:
    """True for a Create Chart instrument code that is an i1iO entry."""
    return str(code or "") in CODES


def is_i1io_instrument_name(name: "str | None") -> bool:
    """True for a CHART's ``TARGET_INSTRUMENT`` naming the i1iO family, in any
    letter case, with or without the quotes CGATS puts around it: the family
    name ChromIQ writes, a vendor-qualified generation ("X-Rite i1iO 3") or
    the bare "i1iO". A bare generation ("i1iO 2") is NOT taken: it is
    i1Profiler's own name, which older imports wrote into measurements
    (challenge of 2026-11-13). Asked of ``.ti2`` charts only."""
    text = str(name or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    folded = text.casefold()
    if folded == "i1io":
        return True
    for prefix in ("x-rite ", "xrite ", "gretagmacbeth "):
        if folded.startswith(prefix):
            rest = folded[len(prefix):].strip()
            return rest == "i1io" or rest.startswith("i1io ")
    return False


def chart_names_i1io(path: Any) -> "bool | None":
    """Whether the chart file at *path* names the i1iO in ``TARGET_INSTRUMENT``.

    None when there is no chart file. Never raises: a file that cannot be read
    is not an i1iO chart. Only the header BYTES are read (a chart made on a
    German Windows is cp1252)."""
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
            return is_i1io_instrument_name(line[17:].strip().decode("latin-1"))
    return False


# ---- a target made with the Beta on, opened with it off --------------------
#
# The same carry rules as the other Beta instrument (`workflow.beta_chart_
# carry`): with the switch off the tab shows the instrument it falls back to,
# which is not the user's choice, so the target's stored i1iO values are put
# back over it when the target is written, and an untouched project's
# `meta.json` stays byte-identical.

CHART_PARAM_KEYS = ("printtarg-i", "printtarg-p")
CHART_GUIDED_KEYS = ("instrument", "paper", "pages", "i1io_crosses",
                     "i1io_clip_border")
CHART_RECIPE_KEYS = ("instrument", "paper", "border", "margin_top",
                     "margin_right", "margin_bottom", "margin_left",
                     "use_instrument_margins", "patch_w_mm", "patch_h_mm",
                     "layout_mode", "i1io_crosses", "i1io_clip_border")


def target_names_i1io(stored_params: "dict | None",
                      stored_ui: "dict | None") -> bool:
    """True when a target's stored Create Chart block names an i1iO entry."""
    from workflow.beta_chart_carry import target_names
    return any(target_names(code, stored_params, stored_ui) for code in CODES)


def carry_i1io_chart_keys(wanted, ui_state, stored_params, stored_ui,
                          screen_at_load=None, own=None) -> set:
    """`workflow.beta_chart_carry.carry_chart_keys` for the i1iO."""
    from workflow.beta_chart_carry import carry_chart_keys
    users: set = set()
    for code in sorted(CODES):
        users |= carry_chart_keys(code, i1io_enabled(), wanted, ui_state,
                                  stored_params, stored_ui, screen_at_load,
                                  own, param_keys=CHART_PARAM_KEYS,
                                  guided_keys=CHART_GUIDED_KEYS,
                                  recipe_keys=CHART_RECIPE_KEYS)
    return users


def off_snapshot(screen_params, screen_ui, stored_params, stored_ui):
    """An i1iO target as the switch-off tab opened it."""
    from workflow.beta_chart_carry import OffSnapshot

    class I1ioOffSnapshot(OffSnapshot):
        __slots__ = ()

        def carry(self, wanted, ui_state):
            return carry_i1io_chart_keys(wanted, ui_state, self.stored[0],
                                         self.stored[1], self.screen, self.own)

        def chart_names(self, path):
            return chart_names_i1io(path)

    return I1ioOffSnapshot(screen_params, screen_ui, stored_params, stored_ui)


# ---- how an i1iO chart is shown ON SCREEN (display only) ------------------
#
# The owner, 2026-11-13: an i1iO chart is shown the way it is used, landscape
# as it lies on the table (the portrait page turned a quarter turn
# CLOCKWISE), its letters and numbers upright, wherever ChromIQ shows it: the
# preview's own view rotation (`ui.tiff_preview.TiffPreview`) turns the
# picture, every overlay, the pointer readout and every click with it. The
# chart's files, its PDF and printing never change.

#: Degrees clockwise an i1iO chart is turned on screen.
DISPLAY_ROTATION = 90


def pages_are_i1io_chart(paths: Any) -> bool:
    """True when *paths* are the page images of an i1iO chart: each one sits
    beside the chart's ``<stem>.i1io.json`` and a ``<stem>.ti2`` that names
    the i1iO (``<stem>.tif`` or ``<stem>_NN.tif``). Never raises."""
    import re
    from pathlib import Path
    try:
        pages = [Path(p) for p in paths]
    except TypeError:
        return False
    if not pages:
        return False
    for page in pages:
        stems = [page.stem]
        m = re.fullmatch(r"(.+)_\d+", page.stem)
        if m:
            stems.append(m.group(1))
        if not any(page.with_name(s + ".i1io.json").is_file()
                   and chart_names_i1io(page.with_name(s + ".ti2")) is True
                   for s in stems):
            return False
    return True


def aim_for_pages(paths: Any) -> str:
    """What the i1iO chart whose page images are *paths* records as the
    thing to aim at: "crosses", "corner patches" or "unknown"
    (`workflow.i1io.chart.aim_recorded`). Never raises."""
    import re
    from pathlib import Path
    try:
        page = Path(list(paths)[0])
        stem = page.stem
        m = re.fullmatch(r"(.+)_\d+", stem)
        for s in ([m.group(1)] if m else []) + [stem]:
            ti2 = page.with_name(s + ".ti2")
            if ti2.is_file():
                from workflow.i1io.chart import aim_recorded
                return aim_recorded(ti2)
    except Exception:      # noqa: BLE001
        pass
    return "unknown"


def display_rotation_for(paths: Any) -> int:
    """The angle to turn *paths* by on screen: DISPLAY_ROTATION for an i1iO
    chart's pages while i1iO support is on, 0 for every other chart. With
    the support off nothing is read at all, not even whether a file
    exists."""
    if not i1io_enabled():
        return 0
    return DISPLAY_ROTATION if pages_are_i1io_chart(paths) else 0
