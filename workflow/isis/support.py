"""THE ONE SWITCH FOR i1iSis CHARTS (Preferences > Beta).

The X-Rite i1iSis family (i1iSis, i1iSis 2, i1iSis XL, i1iSis 2 XL) are
automatic chart readers: the printed sheet is fed into a slot, the
instrument's camera finds a black bar and a black diamond at both ends of
every patch row, and it reads the whole sheet by itself. ChromIQ cannot talk
to them (ArgyllCMS 3.5.0 has no i1iSis driver), so this Beta MAKES charts
for them, laid out by ChromIQ's own layout engine with exactly the furniture
X-Rite's chart rules and i1Profiler 3.8.8 use, plus an i1Profiler test-chart
file (``.txf``) that makes i1Profiler expect exactly that sheet. The sheet is
measured in i1Profiler and the measurement imported back.

The switch is OFF by default, and with it off ChromIQ behaves as 4.3.37 did
with ONE stated exception, the owner's ruling of 2026-11-14: the old
printtarg entry "i1iSis (via i1Profiler)" is gone for everybody, and a stale
saved ``isis`` reads as no instrument (``data.patch_db.
REMOVED_INSTRUMENT_CODES``). Every hook in shared code asks
:func:`isis_enabled` first (``tests/test_isis_off_changes_nothing.py``).

**Restart to apply**, like the other instrument Betas: the value is read ONCE
per process (``main()`` latches it before the window is built).

**Names.** One Create Chart entry, ``XRISIS``, "i1iSis family", for both
generations (i1Profiler draws the same chart for an i1iSis and an i1iSis 2,
REQUIREMENTS §1); the XL models' wider sheets are a choice of the entry
("model width"), recorded in the chart's side file. The chart files carry
the family name ``"X-Rite i1iSis"``. The code differs from the removed
``isis`` by more than letter case, because ``isis`` lives on as the model
FAMILY of imported measurements (``data.patch_db.instrument_family_of``).
"""

from __future__ import annotations

from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "isis_charts_beta"

#: The Create Chart instrument code.
CODE = "XRISIS"

#: Every Create Chart code that is an i1iSis entry (one).
CODES: "frozenset[str]" = frozenset({CODE})

#: What the Instrument lists show for it.
LABEL = "i1iSis family"

#: The friendly name in the margin-threshold table (Preferences > Instrument
#: Limits). NOT "i1iSis": that was the removed entry's label, and its stored
#: thresholds must not be picked up by the new entry.
THRESHOLD_LABEL = "i1iSis (Beta)"

#: The family name every i1iSis chart carries in ``TARGET_INSTRUMENT``.
TARGET_INSTRUMENT = "X-Rite i1iSis"

#: The model width choice (a recipe field): the standard models read sheets
#: up to 230 mm wide, the XL models up to 330 mm.
MODEL_STANDARD = "standard"
MODEL_XL = "xl"
MODELS = (MODEL_STANDARD, MODEL_XL)

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


def isis_enabled() -> bool:
    """True when i1iSis charts are on for THIS run of ChromIQ (read once)."""
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


def is_isis_code(code: Any) -> bool:
    """True for a Create Chart instrument code that is the i1iSis entry."""
    return str(code or "") in CODES


def model_of(value: Any) -> str:
    """A stored model width read safely: "xl" or "standard"."""
    return MODEL_XL if str(value or "").strip().lower() == MODEL_XL \
        else MODEL_STANDARD


def device_name(model: Any) -> str:
    """The device name i1Profiler itself writes for the model width:
    "i1iSis" (it draws the same chart for an i1iSis 2) or "i1iSis XL"
    (X-Rite's own ``default-i1iSis.txf`` says so)."""
    return "i1iSis XL" if model_of(model) == MODEL_XL else "i1iSis"


def is_isis_instrument_name(name: "str | None") -> bool:
    """True for a CHART's ``TARGET_INSTRUMENT`` naming the i1iSis family that
    ChromIQ writes ("X-Rite i1iSis", any case, with or without CGATS quotes).
    The bare "i1iSis" is NOT taken: it is i1Profiler's own name, which
    imported measurements carry (they are not ChromIQ i1iSis charts)."""
    text = str(name or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    folded = text.casefold()
    for prefix in ("x-rite ", "xrite "):
        if folded.startswith(prefix):
            rest = folded[len(prefix):].strip()
            return rest == "i1isis" or rest.startswith("i1isis ")
    return False


def chart_names_isis(path: Any) -> "bool | None":
    """Whether the chart file at *path* names the i1iSis in
    ``TARGET_INSTRUMENT``. None when there is no chart file. Never raises:
    a file that cannot be read is not an i1iSis chart. Only the header BYTES
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
            return is_isis_instrument_name(
                line[17:].strip().decode("latin-1"))
    return False


def side_file_for(ti2_path: Any):
    """The ``<stem>.isis.json`` beside a ``<stem>.ti2`` (a Path; it may not
    exist)."""
    from pathlib import Path
    p = Path(ti2_path)
    name = p.name[:-4] if p.name.lower().endswith(".ti2") else p.name
    return p.with_name(name + ".isis.json")


def read_side_file(ti2_path: Any) -> "dict | None":
    """The chart's side file as a dict, or None. Never raises."""
    import json
    try:
        return json.loads(side_file_for(ti2_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


# ---- a target made with the Beta on, opened with it off --------------------
#
# The shared carry rules (`workflow.beta_chart_carry`), as for the i1iO: with
# the switch off the tab shows the instrument it falls back to, which is not
# the user's choice, so the target's stored i1iSis values are put back over it
# when the target is written, and an untouched project's `meta.json` stays
# byte-identical.

CHART_PARAM_KEYS = ("printtarg-i", "printtarg-p")
CHART_GUIDED_KEYS = ("instrument", "paper", "pages", "isis_model",
                     "isis_notes_band")
CHART_RECIPE_KEYS = ("instrument", "paper", "border", "margin_top",
                     "margin_right", "margin_bottom", "margin_left",
                     "use_instrument_margins", "patch_w_mm", "patch_h_mm",
                     "layout_mode", "isis_model", "isis_header_mm",
                     "isis_tight", "isis_barcode", "isis_trailer_mm",
                     "isis_arrows", "isis_outline", "isis_corner_labels",
                     "isis_strip_letters",
                     "isis_notes_band", "isis_notes_place",
                     "isis_notes_height_mm")


def target_names_isis(stored_params: "dict | None",
                      stored_ui: "dict | None") -> bool:
    """True when a target's stored Create Chart block names the i1iSis."""
    from workflow.beta_chart_carry import target_names
    return any(target_names(code, stored_params, stored_ui) for code in CODES)


def carry_isis_chart_keys(wanted, ui_state, stored_params, stored_ui,
                          screen_at_load=None, own=None) -> set:
    """`workflow.beta_chart_carry.carry_chart_keys` for the i1iSis."""
    from workflow.beta_chart_carry import carry_chart_keys
    users: set = set()
    for code in sorted(CODES):
        users |= carry_chart_keys(code, isis_enabled(), wanted, ui_state,
                                  stored_params, stored_ui, screen_at_load,
                                  own, param_keys=CHART_PARAM_KEYS,
                                  guided_keys=CHART_GUIDED_KEYS,
                                  recipe_keys=CHART_RECIPE_KEYS)
    return users


def off_snapshot(screen_params, screen_ui, stored_params, stored_ui):
    """An i1iSis target as the switch-off tab opened it."""
    from workflow.beta_chart_carry import OffSnapshot

    class IsisOffSnapshot(OffSnapshot):
        __slots__ = ()

        def carry(self, wanted, ui_state):
            return carry_isis_chart_keys(wanted, ui_state, self.stored[0],
                                         self.stored[1], self.screen, self.own)

        def chart_names(self, path):
            return chart_names_isis(path)

    return IsisOffSnapshot(screen_params, screen_ui, stored_params, stored_ui)
