"""THE ONE SWITCH FOR FD-9 SUPPORT (Preferences > Beta).

FD-9 support was written and contributed by lessbones (PR #213). It is a beta
and it is OFF by default, and with it off ChromIQ must behave exactly as 4.3.21
did: no FD-9 in any list, no FD-9 panel on the Measure tab, no chart file read
to find out whether it is an FD-9 chart, and no new key in any target's
``meta.json``. Every FD-9 hook in shared code asks :func:`fd9_enabled` first,
and ``tests/test_fd9_off_changes_nothing.py`` fails on a hook that does not.

**Restart to apply.** The instrument lists are built once, when the window is
built, so a live switch would leave half the app on the old answer. The value
is therefore read ONCE per process (``main()`` latches it before the window is
built) and Preferences shows the usual "Takes effect after you restart
ChromIQ." beside the box while the stored value differs from the running one.
"""

from __future__ import annotations

from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "fd9_support_beta"

#: Every spelling of the FD-9 a chart or measurement file can carry in
#: ``TARGET_INSTRUMENT``. ChromIQ writes the first; the second is what charts
#: made before the Beta switch (lessbones' own) carry, and still opens.
TARGET_INSTRUMENT_NAMES: "tuple[str, ...]" = ("Konica Minolta FD-9", "FD-9")

#: The name ChromIQ writes into a new FD-9 ``.ti2`` / ``.ti3``.
TARGET_INSTRUMENT = TARGET_INSTRUMENT_NAMES[0]

_latched: "bool | None" = None


def stored_value(settings: Any) -> bool:
    """What Preferences holds now (it may differ from the running value)."""
    try:
        return bool(settings.get(SETTING, False))
    except Exception:  # noqa: BLE001 — a broken store means "off"
        return False


def latch_from(settings: Any) -> bool:
    """Fix the running value from *settings*. Called once by ``main()``."""
    global _latched
    _latched = stored_value(settings)
    return _latched


def fd9_enabled() -> bool:
    """True when FD-9 support is on for THIS run of ChromIQ.

    Read once and then kept (restart-to-apply). Cheap: no file is read after
    the first call, and none at all for a chart."""
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


def is_fd9_instrument_name(name: "str | None") -> bool:
    """True for a ``TARGET_INSTRUMENT`` value that names the FD-9: either
    spelling, in any letter case, with or without the quotes CGATS puts
    around it (review r1 minor: a chart edited by hand or written by another
    tool says "fd-9" or 'FD-9' just as well)."""
    text = str(name or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text.casefold() in {n.casefold() for n in TARGET_INSTRUMENT_NAMES}


#: What makes a target's Create Chart settings the FD-9's (review r2 S1), per
#: place they are stored. With the Beta off the tab cannot show an FD-9, so
#: these are the values it would otherwise replace with the i1Pro it falls
#: back to. Everything else in the block is the user's, FD-9 or not.
CHART_PARAM_KEYS = ("printtarg-i", "printtarg-p")
CHART_GUIDED_KEYS = ("instrument", "paper", "pages")
CHART_RECIPE_KEYS = ("instrument", "paper", "border", "margin_top",
                     "margin_right", "margin_bottom", "margin_left",
                     "use_instrument_margins", "patch_w_mm", "patch_h_mm",
                     "fd9_gap_mm", "layout_mode")


def _names_fd9(value: Any) -> bool:
    return str(value or "") == "FD9"


def chart_names_fd9(path: Any) -> "bool | None":
    """Whether the chart file at *path* names the FD-9 in its
    ``TARGET_INSTRUMENT`` (either spelling, see :func:`is_fd9_instrument_name`).

    None when there is no chart file to ask. Never raises: a file that cannot
    be read is not an FD-9 chart. Only the header BYTES are read (a chart made
    on a German Windows is cp1252), and nothing else from ``workflow.fd9`` is
    imported, so the off app loads no FD-9 code for it (review r3 R3-1).
    Asked only while the Beta is off AND the target's stored settings name the
    FD-9, so a 4.3.21 target never has its chart read for this."""
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
            value = line[17:].strip().decode("latin-1")
            return is_fd9_instrument_name(value)
    return False


def target_names_fd9(stored_params: "dict | None",
                     stored_ui: "dict | None") -> bool:
    """True when a target's stored Create Chart block names the FD-9."""
    params = stored_params if isinstance(stored_params, dict) else {}
    if _names_fd9((params.get("printtarg-i") or {}).get("value")):
        return True
    ui = stored_ui if isinstance(stored_ui, dict) else {}
    return any(isinstance(ui.get(b), dict) and _names_fd9(ui[b].get("instrument"))
               for b in ("guided", "engine_recipe"))


def carry_fd9_chart_keys(wanted: "dict | None", ui_state: "dict | None",
                         stored_params: "dict | None",
                         stored_ui: "dict | None",
                         screen_at_load: "tuple | None" = None,
                         own: "set | None" = None) -> set:
    """Put the stored FD-9 Create Chart values back into *wanted* and
    *ui_state* (in place) while FD-9 support is OFF (review r2 S1, narrowed
    in review r3 R3-1 and r4 R4-1).

    The Create Chart counterpart of ``measure_settings.carry_fd9_keys``. A
    target whose chart was made for the FD-9 with the Beta on keeps its FD-9
    instrument, sheet, pages, margins and gap when it is opened with the Beta
    off: the tab shows the i1Pro instead, as 4.3.21 would, but that is the
    app's fallback and not the user's choice, so it is never filed into the
    target. With nothing else changed the write is then skipped altogether
    and ``meta.json`` stays byte-identical.

    *stored_params* / *stored_ui* are the target's blocks AS THEY WERE WHEN
    THE TAB OPENED IT, never as ``meta.json`` reads at write time: once the
    user's own value has been written, the file holds the user's value, and
    carrying "the stored value" back would then put the user's earlier choice
    over their later one (R4-1). *screen_at_load* is ``(wanted, ui_state)``
    as the tab showed them right after that load. A key is carried ONLY while
    its value on screen is still that one and it is not in *own*: a value the
    user changed is the user's and is written as it is (R3-1). Keys are named
    ``("params", key)`` or ``(block, key)``.

    The other FD-9 values of a block come back only while its instrument
    does: a user who picks another instrument has made the block theirs.

    Returns the keys this write files as the user's. The caller adds them to
    *own* once the write is done, so a key the user changed is never carried
    again, even after they change it back to the value it opened with.

    Without a snapshot nothing is carried; the caller passes None once the
    target's chart is no longer an FD-9 chart or the user has generated into
    it, so ``meta.json`` then describes the chart that is really there. With
    the Beta on this does nothing: the tab writes its own FD-9 values."""
    # The rules live in `workflow.beta_chart_carry` since the i1iO became a
    # second Beta instrument; the FD-9's behaviour is exactly what it was.
    from workflow.beta_chart_carry import carry_chart_keys
    return carry_chart_keys("FD9", fd9_enabled(), wanted, ui_state,
                            stored_params, stored_ui, screen_at_load, own,
                            param_keys=CHART_PARAM_KEYS,
                            guided_keys=CHART_GUIDED_KEYS,
                            recipe_keys=CHART_RECIPE_KEYS)


class Fd9OffSnapshot:
    """An FD-9 target as the Beta-off tab opened it (review r3 R3-1, r4 R4-1).

    *screen* is what the tab showed right after the load, *stored* the
    target's Create Chart blocks as ``meta.json`` held them then, and *own*
    the keys since written as the user's (never carried again)."""

    __slots__ = ("screen", "stored", "own")

    def __init__(self, screen_params, screen_ui, stored_params, stored_ui):
        import copy
        self.screen = (copy.deepcopy(screen_params), copy.deepcopy(screen_ui))
        self.stored = (copy.deepcopy(stored_params), copy.deepcopy(stored_ui))
        self.own: set = set()

    def carry(self, wanted: "dict | None", ui_state: "dict | None") -> set:
        """`carry_fd9_chart_keys` from the values as loaded. Returns the keys
        this write files as the user's; pass them to :meth:`written`."""
        return carry_fd9_chart_keys(wanted, ui_state, self.stored[0],
                                    self.stored[1], self.screen, self.own)

    def chart_names(self, path: Any) -> "bool | None":
        """Whether the target's chart is still an FD-9 chart."""
        return chart_names_fd9(path)

    def written(self, users: set) -> None:
        """The write that carried went to disk: its user keys are theirs."""
        self.own |= set(users or ())


# ---- how an FD-9 chart is turned ON SCREEN (display only) -----------------

#: The AppSettings key (``core.settings.DEFAULTS``: 0). Preferences > Beta,
#: the row under FD-9 support. Display only: no chart file, no PDF and no
#: print ever changes with it (the owner, 2026-11-04).
ROTATION_SETTING = "fd9_display_rotation"

#: The choices, in degrees clockwise. 0 is "Off": the view of 4.3.24.
ROTATIONS = (0, 90, 180, 270)


def stored_rotation(settings: Any) -> int:
    """The angle Preferences holds, 0 for anything that is not a choice."""
    try:
        value = int(settings.get(ROTATION_SETTING, 0) or 0)
    except Exception:  # noqa: BLE001 — a broken store means "off"
        return 0
    return value if value in ROTATIONS else 0


def display_rotation(settings: Any = None) -> int:
    """How far FD-9 charts are turned on screen in THIS run: 0 whenever FD-9
    support is off, whatever Preferences holds (the row is greyed then).
    Applies live: read each time it is asked, which is once per chart load
    and once when Preferences closes."""
    if not fd9_enabled():
        return 0
    if settings is None:
        try:
            from core.settings import AppSettings
            settings = AppSettings()
        except Exception:  # noqa: BLE001
            return 0
    return stored_rotation(settings)


def pages_are_fd9_chart(paths: Any) -> bool:
    """True when *paths* are the page images of an FD-9 chart: each one sits
    beside the chart's ``<stem>.fd9.json`` and a ``<stem>.ti2`` that names
    the FD-9 (``<stem>.tif`` or ``<stem>_NN.tif``). Never raises; asked only
    while FD-9 support is on (see :func:`display_rotation_for`)."""
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
        if not any((page.with_name(s + ".fd9.json")).is_file()
                   and chart_names_fd9(page.with_name(s + ".ti2")) is True
                   for s in stems):
            return False
    return True


def display_rotation_for(paths: Any, settings: Any = None) -> int:
    """The angle to turn *paths* by on screen: :func:`display_rotation` for
    an FD-9 chart's pages, 0 for every other chart. With FD-9 support off
    nothing is read at all, not even whether a file exists."""
    if not fd9_enabled():
        return 0
    angle = display_rotation(settings)
    if not angle or not pages_are_fd9_chart(paths):
        return 0
    return angle
