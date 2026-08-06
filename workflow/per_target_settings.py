"""Which settings belong to a target, discovered rather than listed.

Specification: ``docs/design/per_target_settings.md`` §1 and **S1.1**; test plan
``docs/design/per_target_settings_test_plan.md`` §2 (P1/P2).

Knut's rule (#130) is that **all** non-global parameters are stored, not a
selection of them:

    "If some settings are saved and other not, then it is very confusing for a
    user when settings he never set for a run … suddenly change, and when the
    user wants to reproduce a chart or a profile build, he will not get the same
    result."

A hand-written list of those parameters cannot satisfy that rule for long: a
parameter added to ``parameters.yaml`` appears in the UI automatically — that is
the whole point of the YAML — and would be silently absent from the store. The
same shape of mistake has already cost this project twice: a hand-copied section
list that made ``### Documentation`` render as nothing, and a hand-maintained
sound table that drifted from the code.

So this module **asks the tab** what it has, and the tests are generated from
the same answer. A widget nobody has taught it to read is an error, never a
skip.

Nothing here writes anything. It is the vocabulary the store and the tests
share.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

#: Settings that describe the installation rather than a target (§1.1). Held as
#: flags because that is what identifies a row in ``parameters.yaml``.
GLOBAL_FLAGS: frozenset[str] = frozenset({
    # The ArgyllCMS binary path, language, appearance and sounds are not
    # parameter rows at all — they live in Preferences — so nothing is listed
    # here yet. The set exists so that a parameter which *should* be global can
    # be declared as such in one place instead of being quietly left out of the
    # registry, which would be indistinguishable from an oversight.
})


@dataclass(frozen=True)
class Param:
    """One per-target parameter, and how to read and write it on screen.

    ``widgets`` is a tuple because **a parameter can repeat**. targen's ``-D``
    is a cascade: one visible row plus ten hidden ones, all carrying the same
    flag, because targen accepts ``-D`` more than once. Treating them as
    duplicates and keeping one would silently drop every device value after the
    first — which is what the first version of this module did, and what the
    duplicate check caught the moment it met the real tab.
    """

    tool: str          #: "targen", "printtarg", "colprof", "printcal", "chartread"
    flag: str          #: the CLI flag, e.g. "-f"
    widgets: tuple     #: the live ParameterWidget(s), in the order they appear

    @property
    def key(self) -> str:
        """The JSON tag this parameter is stored under.

        Tool-qualified because a flag is only unique within its tool: targen and
        printtarg both have a ``-p``, and storing them under one key would make
        each overwrite the other — silently, and only for users who set both.
        """
        return f"{self.tool}{self.flag}"

    @property
    def repeats(self) -> bool:
        return len(self.widgets) > 1

    # -- reading and writing the screen ------------------------------------
    def read(self) -> dict:
        """What the screen has, in the shape that is stored.

        ``{"enabled": …, "value": …}`` for an ordinary row, and
        ``{"repeats": [ … ]}`` for a repeatable one. Two shapes rather than one
        because forcing every row into a list would make the common case
        unreadable in the JSON, and this file is one a user may well open.

        Enabled and value are always both recorded: a row can be off with a
        value still typed in it, and test plan R3 requires that state to come
        back exactly as it was.
        """
        def one(w):
            return {"enabled": bool(w.is_enabled_by_user),
                    "value": w.get_raw_value()}
        if self.repeats:
            return {"repeats": [one(w) for w in self.widgets]}
        return one(self.widgets[0])

    def write(self, record: dict) -> None:
        """Put a stored record back on screen.

        Value before enable, always: a row switched on before it has its value
        briefly shows the default, and with auto-update listening that is a
        redraw of the wrong chart (§7 B).
        """
        def one(w, rec):
            w.set_value(rec.get("value"))
            w.set_user_enabled(bool(rec.get("enabled", True)))

        if self.repeats:
            recs = record.get("repeats") or []
            for w, rec in zip(self.widgets, recs):
                if isinstance(rec, dict):
                    one(w, rec)
            # Rows beyond what was stored are cleared, or a longer cascade from
            # a previous target would leave its tail behind on this one.
            for w in self.widgets[len(recs):]:
                w.set_value("")
                w.set_user_enabled(False)
            return
        one(self.widgets[0], record)


def params_for(tab: Any) -> "list[Param]":
    """Every per-target parameter the tab currently has, in a stable order.

    The tab is asked through ``per_target_widgets()``, which each in-scope tab
    provides. A tab that does not provide it yields nothing rather than raising:
    Print Chart and Check & Refine are deliberately out of scope (§5), and being
    out of scope must not break the caller.
    """
    source = getattr(tab, "per_target_widgets", None)
    if source is None:
        return []
    grouped: "dict[tuple[str, str], list]" = {}
    for tool, widgets in sorted(source().items()):
        for pw in widgets:
            flag = getattr(pw, "flag", "")
            if not flag or flag in GLOBAL_FLAGS:
                continue
            grouped.setdefault((tool, flag), []).append(pw)
    return [Param(tool=t, flag=f, widgets=tuple(ws))
            for (t, f), ws in grouped.items()]


def snapshot(tab: Any) -> "dict[str, dict]":
    """What the tab would store for the selected target, right now."""
    return {p.key: p.read() for p in params_for(tab)}


def apply(tab: Any, stored: "dict[str, dict]") -> "list[str]":
    """Put ``stored`` on screen. Returns the keys it did not recognise.

    Unknown keys are returned rather than raised: a chart made before a
    parameter was renamed or removed must still open (§7 A). Losing a whole
    target's settings over one stale tag would be far worse than ignoring it.
    """
    by_key = {p.key: p for p in params_for(tab)}
    unknown: list[str] = []
    for key, rec in (stored or {}).items():
        p = by_key.get(key)
        if p is None or not isinstance(rec, dict):
            unknown.append(key)
            continue
        p.write(rec)
    return unknown


def iter_tabs(*tabs: Any) -> Iterator["tuple[Any, list[Param]]"]:
    """(tab, its parameters) for each tab that has any — for the test harness."""
    for tab in tabs:
        params = params_for(tab)
        if params:
            yield tab, params
