"""Which Measure-tab settings belong to a target, and how to read them back.

Specification: ``docs/design/per_target_settings.md`` §5 puts the Measure tab in
scope; Knut added it (*"measure tab must be included"*) after two of his own
reports came from exactly these controls — the ``-N`` that survived from an
earlier session, and the resume tick that disagreed with itself.

**Why this is not the Create Chart registry.** Only Create Chart is built from
``ParameterWidget``, which knows its own flag, value and enabled-state; that is
what makes ``workflow.per_target_settings`` able to discover its parameters. The
Measure tab is plain Qt controls plus one enumerable list, so it needs its own
reader — same store, different way of reaching the screen.

**The drift guard is the point.** ``MEASURE_CONTROLS`` is hand-written, which is
exactly the shape of mistake that has cost this project several faults. So
``tests/test_measure_settings.py`` checks it against ``MeasureParams``: a field
added there that nobody maps here fails the suite, rather than being silently
absent from every target's stored settings.
"""
from __future__ import annotations

from typing import Any

#: Fields of :class:`MeasureParams` that are NOT user settings, with the reason.
#: Listed so the drift test can tell "deliberately not stored" from "forgotten".
NOT_A_SETTING = {
    "ti1_path":      "the chart being measured, not a preference",
    "extra_args":    "assembled from the chartread options below",
    "engine_helper": "the bundled binary's path — an installation detail",
    "engine_replay": "a developer replay script",
    "instrument":    "which instrument is plugged in, not a property of the run",
    "cal_auto_retries": "a Preferences value, global by §1.1",
    "engine_safenet":   "a Preferences value, global by §1.1",
    "engine_xy_chart":  "a Preferences (Beta) value, global by §1.1",
    "high_res":      ("the UI drives -H through the chartread option 'highres', "
                      "so it is stored as chartread.highres; this dataclass "
                      "field is a second route that nothing on screen sets"),
    "disable_bidir": "derived from the bidirectional choice below",
    "force_bidir":   "derived from the bidirectional choice below",
}

#: setting key -> the manual-mode attribute on the tab that holds it.
#: Manual only: Guided is a way of *choosing* these, and it fills the same
#: underlying reading — the same rule Create Chart follows.
MEASURE_CONTROLS: "dict[str, str]" = {
    "suppress_warnings":   "_m_suppress_cb",
    "disable_initial_cal": "_m_nocal_cb",
    "patch_by_patch":      "_m_pbp_cb",
    "resume":              "_m_resume_cb",
    "bidirectional":       "_m_bidir_combo",
}


def _read(widget) -> "tuple[bool, Any] | None":
    """``(enabled, value)`` for a control, or None when it is not on screen."""
    if widget is None:
        return None
    if hasattr(widget, "isChecked"):
        return True, bool(widget.isChecked())
    if hasattr(widget, "currentData"):
        return True, widget.currentData()
    if hasattr(widget, "value"):
        return True, widget.value()
    if hasattr(widget, "text"):
        return True, widget.text()
    return None


def _write(widget, value) -> None:
    if widget is None:
        return
    if hasattr(widget, "setChecked"):
        widget.setChecked(bool(value))
    elif hasattr(widget, "findData"):
        i = widget.findData(value)
        if i >= 0:
            widget.setCurrentIndex(i)
    elif hasattr(widget, "setValue"):
        widget.setValue(value)
    elif hasattr(widget, "setText"):
        widget.setText("" if value is None else str(value))


def snapshot(tab: Any) -> "dict[str, dict]":
    """What the Measure tab would store for the selected target, right now."""
    out: "dict[str, dict]" = {}
    for key, attr in MEASURE_CONTROLS.items():
        got = _read(getattr(tab, attr, None))
        if got is not None:
            out[key] = {"enabled": got[0], "value": got[1]}
    # …and every chartread option, which the tab already keeps as a list — the
    # one part of this tab that is enumerable, so it cannot be forgotten.
    for opt in getattr(tab, "_chartread_opts", []) or []:
        cb, w = getattr(opt, "checkbox", None), getattr(opt, "widget", None)
        if cb is None:
            continue
        rec: dict = {"enabled": bool(cb.isChecked())}
        got = _read(w)
        if got is not None:
            rec["value"] = got[1]
        out[f"chartread.{opt.key}"] = rec
    return out


def apply(tab: Any, stored: "dict[str, dict]") -> "list[str]":
    """Put ``stored`` on screen. Returns the keys it did not recognise.

    Unknown keys are reported rather than raised: a target stored before an
    option was renamed must still open (§7 A).
    """
    unknown: list[str] = []
    opts = {f"chartread.{o.key}": o
            for o in (getattr(tab, "_chartread_opts", []) or [])}
    for key, rec in (stored or {}).items():
        if not isinstance(rec, dict):
            unknown.append(key)
            continue
        if key in MEASURE_CONTROLS:
            _write(getattr(tab, MEASURE_CONTROLS[key], None), rec.get("value"))
        elif key in opts:
            opt = opts[key]
            if "value" in rec:
                _write(getattr(opt, "widget", None), rec["value"])
            cb = getattr(opt, "checkbox", None)
            if cb is not None:
                cb.setChecked(bool(rec.get("enabled", False)))
        else:
            unknown.append(key)
    return unknown
