"""Application language support (restart-to-apply).

ChromIQ translates its UI through a plain string catalog instead of Qt
Linguist: `tr("English text")` looks the English source string up in
`data/i18n/<code>.json` and returns the translation, or the English text
itself when no entry exists (so missing translations degrade gracefully
instead of crashing or showing placeholders).

The language is read once at startup (`set_language()` in main.py) and
never changes during a session — the Settings dialog tells the user to
restart.  That keeps every call site a one-shot lookup; no widget needs
a retranslate path.

Strings with runtime values use str.format placeholders:

    tr("Removed {count} patches").format(count=n)

The placeholder names are part of the catalog key, and
`check_placeholders()` (used by the tests) verifies every translation
keeps exactly the placeholders of its source string, so a bad catalog
entry can't raise KeyError at runtime.

`data/parameters.yaml` is translated separately: an overlay file
`data/i18n/parameters.<code>.yaml` mirrors the tool/flag structure and
`translate_parameters()` merges its text fields (name, labels,
tooltip_title, tooltip_body) over the loaded definitions.
"""
from __future__ import annotations

import json
import re
import string
from pathlib import Path
from typing import Any

from core.logger import get_logger
from core.resource_path import resource_path
from core.platform_paths import default_output_root

log = get_logger("i18n")

# Built-in source language — always available, needs no catalog file.
SOURCE_LANGUAGE = "en"
SOURCE_LANGUAGE_NAME = "English"

# Catalog files may carry metadata under keys with this prefix.
_META_PREFIX = "@"

_language: str = SOURCE_LANGUAGE
_catalog: dict[str, str] = {}
# Per-category forms for count-bearing strings, from the catalogue's
# "@plurals" entry: {English key: {"count": placeholder, "one": …, …}}.
_plurals: dict[str, dict[str, str]] = {}

# The catalogue key that holds the plural forms (see `plural_category`).
PLURALS_KEY = "@plurals"


def user_i18n_dir() -> Path:
    """Writable directory for user-imported translation catalogs.

    Mirrors ``FileManager.root_dir()`` (``custom_output_path`` setting, else
    ``~/ChromIQ``) and appends ``i18n/``.  Imported catalogs land here so the
    read-only frozen ``.app`` bundle never needs to be written, and the loaders
    below prefer this directory over the bundled ``data/i18n``.  Read lazily and
    defensively so importing this module needs no Qt and no QApplication.
    """
    root: Path | None = None
    try:
        # THROUGH THE APP'S OWN STORE, so `CHROMIQ_SETTINGS_FILE` is honoured.
        # Reading `QSettings("ChromIQ", "ChromIQ")` directly walks straight
        # past the sandbox every driver and test sets, and lands on the real
        # preferences — the one thing that env var exists to make impossible
        # (found by a challenge round, 2026-09-01).
        from core.settings import AppSettings
        custom = AppSettings().get("custom_output_path", "")
        if custom:
            root = Path(str(custom))
    except Exception:
        pass
    if root is None:
        root = default_output_root()
    return root / "i18n"


def _catalog_file(code: str) -> Path:
    """Path to ``<code>.json`` — user override if present, else bundled."""
    override = user_i18n_dir() / f"{code}.json"
    return override if override.exists() else resource_path(f"data/i18n/{code}.json")


# ----------------------------------------------------------------------
# Plural forms (CLDR categories)
# ----------------------------------------------------------------------
#
# English has two forms, and the code already writes both out (a "1 patch"
# key and a "{n} patches" key, see `count_phrase`). Russian, Ukrainian and
# Polish have three: 1 патч, 2 патча, 5 патчей, but also 21 патч and 22
# патча, so "singular or plural" cannot say which one a number needs.
#
# A catalogue gives those forms under its "@plurals" entry, keyed by the
# English source string like everything else:
#
#     "@plurals": {
#       "{n} patches": {"count": "n",
#                       "one": "{n} патч", "few": "{n} патча",
#                       "many": "{n} патчей"}
#     }
#
# "count" names the placeholder whose number picks the form. The flat entry
# ("{n} patches": "{n} патчей") stays, and is the "many" form: it is what a
# lookup that never learns the number shows. `tr()` then hands back a
# `PluralText`, which picks the right form as soon as it is formatted with
# that placeholder (or given the number with ``tr(text, count=n)``).

#: The categories each language's forms must cover. Every other language
#: has English's two (one / other), and needs no "@plurals" entry at all.
PLURAL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "ru": ("one", "few", "many"),
    "uk": ("one", "few", "many"),
    "pl": ("one", "few", "many"),
}

#: Where a missing form is looked for. "other" is the CLDR category for a
#: fraction (1,5 патча, 1,5 strony): those three languages put a fraction's
#: noun in the genitive singular, which is spelled like the "few" form.
_FALLBACK = ("other", "few", "many", "one")


def plural_category(n, lang: str | None = None) -> str:
    """The CLDR plural category of the number `n` in `lang` (default: the
    active language): "one", "few", "many" or "other".

    ru / uk: one = n%10 == 1 and n%100 != 11; few = n%10 in 2..4 and
    n%100 not in 12..14; many = every other whole number.
    pl: one = n == 1; few as above; many = every other whole number.
    A fraction is "other" in all three. Everywhere else: one = 1, other.
    """
    lang = _language if lang is None else lang
    if isinstance(n, str):
        # A number that was already written out: "21", "1 234", "1,5".
        # U+202F is the narrow no-break space some locales group with.
        n = (n.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
              .replace(",", "."))
    try:
        value = float(n)
    except (TypeError, ValueError):
        return "other"
    whole = value.is_integer()
    i = abs(int(value)) if whole else None
    if lang in ("ru", "uk"):
        if not whole:
            return "other"
        if i % 10 == 1 and i % 100 != 11:
            return "one"
        if 2 <= i % 10 <= 4 and not 12 <= i % 100 <= 14:
            return "few"
        return "many"
    if lang == "pl":
        if not whole:
            return "other"
        if i == 1:
            return "one"
        if 2 <= i % 10 <= 4 and not 12 <= i % 100 <= 14:
            return "few"
        return "many"
    return "one" if whole and i == 1 else "other"


def _pick_form(forms: dict[str, str], n, fallback: str) -> str:
    cat = plural_category(n)
    for c in (cat,) + _FALLBACK:
        if isinstance(forms.get(c), str):
            return forms[c]
    return fallback


class PluralText(str):
    """A translation that has per-number forms.

    It is an ordinary string (the "many" form), so every caller that just
    shows it keeps working; `format()` with the counting placeholder, or
    `for_count()`, picks the form that number needs.
    """

    __slots__ = ("forms", "count_field")

    def __new__(cls, text: str, forms: dict[str, str], count_field: str):
        obj = super().__new__(cls, text)
        obj.forms = forms
        obj.count_field = count_field
        return obj

    def __reduce__(self):
        # A copy or a pickle is the plain text: the forms belong to the lookup.
        return (str, (str(self),))

    def for_count(self, n) -> str:
        return _pick_form(self.forms, n, str(self))

    def format(self, *args, **kwargs) -> str:  # noqa: A003 — str API
        if self.count_field in kwargs:
            return self.for_count(kwargs[self.count_field]).format(*args, **kwargs)
        return str.format(self, *args, **kwargs)


def tr(text: str, count=None) -> str:
    """Translate an English source string into the active language.

    Returns `text` unchanged when the active language is English or the
    catalog has no entry — callers never need to handle a miss.

    A string that counts something may have one form per number category
    in the active language (see `PluralText`). Pass the number as `count`
    to get that form directly; without it the result picks its form when it
    is formatted with the counting placeholder.
    """
    if not _catalog:
        return text
    found = _catalog.get(text, text)
    forms = _plurals.get(text)
    if forms is None:
        return found
    result = PluralText(found, forms, forms.get("count", "n"))
    return result.for_count(count) if count is not None else result


def count_phrase(n: int, singular: str, plural: str) -> str:
    """``"1 page"`` / ``"3 pages"`` — a counted phrase with a real plural.

    House rule (Basti): a message that carries a count gets proper singular and
    plural forms, never ``"page(s)"``. Both forms are separate catalogue keys,
    which is also what a translator needs — plenty of languages do not form a
    plural by adding a letter, and several change the noun's case after a
    number.

    Pass the two forms already written out, with ``{n}`` where the number goes::

        count_phrase(len(tiffs), tr("1 page"), tr("{n} pages"))

    The singular normally has no placeholder, so it is returned as-is; if it
    does have one, it is filled in too.
    """
    text = singular if n == 1 else plural
    if isinstance(text, PluralText):
        # Russian, Ukrainian, Polish: 21 takes the "one" form, 22 the "few".
        text = text.for_count(n)
    return text.format(n=n) if "{n}" in text else text


def current_language() -> str:
    return _language


def available_languages() -> list[tuple[str, str]]:
    """[(code, native name), …] — English plus every data/i18n/<code>.json."""
    names: dict[str, str] = {}
    # Bundled catalogs first, then user overrides — a user entry wins on a code
    # clash, and a newly imported language (no bundled file) still appears.
    dirs = [resource_path("data/i18n")]
    user = user_i18n_dir()
    if user.exists():
        dirs.append(user)
    for i18n_dir in dirs:
        try:
            for path in sorted(i18n_dir.glob("*.json")):
                code = path.stem
                if code == SOURCE_LANGUAGE:
                    continue
                name = code
                try:
                    with open(path, encoding="utf-8") as f:
                        name = json.load(f).get("@language_name", code)
                except Exception:
                    log.warning("Unreadable language catalog: %s", path, exc_info=True)
                names[code] = name
        except Exception:
            log.warning("Cannot scan %s for languages", i18n_dir, exc_info=True)
    langs = [(SOURCE_LANGUAGE, SOURCE_LANGUAGE_NAME)]
    langs.extend(sorted(names.items()))
    return langs


def set_language(code: str) -> None:
    """Load the catalog for `code`.  Called once at startup, before any UI.

    Unknown/missing catalogs fall back to English silently (logged) — a
    settings value pointing at a removed language must not block startup.
    """
    global _language, _catalog, _plurals
    code = (code or SOURCE_LANGUAGE).strip()
    _plurals = {}
    if code == SOURCE_LANGUAGE:
        _language, _catalog = SOURCE_LANGUAGE, {}
        return
    try:
        path = _catalog_file(code)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        _catalog = {
            k: v for k, v in raw.items()
            if not k.startswith(_META_PREFIX) and isinstance(v, str)
        }
        plurals = raw.get(PLURALS_KEY)
        if isinstance(plurals, dict):
            _plurals = {
                k: v for k, v in plurals.items()
                if isinstance(v, dict) and k in _catalog
            }
        _language = code
        log.info("Language: %s (%d strings)", code, len(_catalog))
    except FileNotFoundError:
        log.warning("No catalog for language %r — falling back to English", code)
        _language, _catalog = SOURCE_LANGUAGE, {}
    except Exception:
        log.error("Broken catalog for language %r — falling back to English",
                  code, exc_info=True)
        _language, _catalog = SOURCE_LANGUAGE, {}


_qt_translator = None  # keep a reference — Qt does not own installed translators


def install_qt_translator(app) -> None:
    """Load Qt's own qtbase translations for the active language.

    QDialogButtonBox standard buttons (OK / Cancel / Close), context menus
    and other Qt-internal strings are translated by Qt itself, not by our
    catalog — without qtbase_<code>.qm they stay English.
    """
    global _qt_translator
    if _language == SOURCE_LANGUAGE:
        return
    try:
        from PyQt6.QtCore import QLibraryInfo, QTranslator
        tr_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        # Qt ships some languages only under a variant name.
        candidates = [_language, {"pt": "pt_BR", "no": "nb"}.get(_language)]
        t = QTranslator(app)
        for cand in filter(None, candidates):
            if t.load(f"qtbase_{cand}", tr_dir):
                app.installTranslator(t)
                _qt_translator = t
                log.info("Qt base translations loaded: qtbase_%s", cand)
                _install_button_names(app)
                return
        # PyQt6 ships no qtbase .qm for this language (e.g. Norwegian).
        # Fall back to our own minimal catalog of Qt's standard-button
        # strings so OK/Cancel/Close still follow the UI language.
        fb = _load_qt_fallback(_language)
        if fb:
            t = _JsonQtTranslator(fb, app)
            app.installTranslator(t)
            _qt_translator = t
            log.info("Qt fallback button translations loaded for %r", _language)
            _install_button_names(app)
            return
        log.warning("No qtbase translations for %r in %s", _language, tr_dir)
    except Exception:
        log.warning("Could not install Qt base translations", exc_info=True)


#: Qt's standard-button labels that ChromIQ's own texts name. 4.3.12: the
#: Measure tab's instrument-choice window said "•  Гаразд: applies the choice
#: above" while its OK button, translated by qtbase_uk.qm, read "OK". Qt's own
#: catalogues and ours disagree on a handful of these words (uk and ru "OK",
#: sv "Ok", fr/ja/ru/uk "Discard", pl/pt "Save", nl "Retry"), and a text that
#: tells someone to press a button has to name the button they can see. So a
#: standard button reads exactly what tr() gives for the same word, in every
#: language and every window; a word our catalogue does not have still comes
#: from Qt. Labels with a mnemonic ("&Yes") are left to Qt, which already
#: agrees with us on them and knows where each language puts its "&".
STANDARD_BUTTON_LABELS = (
    "OK", "Cancel", "Close", "Save", "Save All", "Open", "Discard", "Apply",
    "Reset", "Restore Defaults", "Help", "Abort", "Retry", "Ignore",
    "Don't Save", "Close without Saving",
)

_button_translator = None   # kept alive for as long as the app runs


def _install_button_names(app) -> None:
    """Install, after Qt's own catalogue, a translator that makes every
    standard button read the same word as ChromIQ's catalogue. Qt asks the
    most recently installed translator first, so this one wins wherever it
    has an answer and falls through to qtbase where it has none."""
    global _button_translator
    names = {w: _catalog[w] for w in STANDARD_BUTTON_LABELS
             if isinstance(_catalog.get(w), str) and _catalog[w]}
    if not names or _JsonQtTranslator is None:
        return
    t = _JsonQtTranslator(names, app)
    app.installTranslator(t)
    _button_translator = t
    log.info("Standard buttons follow the catalogue for %r: %s",
             _language, ", ".join(sorted(names)))


def remove_qt_translators(app) -> None:
    """Take out what `install_qt_translator` put in (a test, or a language
    switch inside one process, starts again from Qt's English)."""
    global _qt_translator, _button_translator
    for t in (_button_translator, _qt_translator):
        if t is not None:
            app.removeTranslator(t)
    _qt_translator = _button_translator = None


# Qt-internal contexts whose user-visible strings the fallback covers.
_QT_FALLBACK_CONTEXTS = frozenset(
    {"QPlatformTheme", "QDialogButtonBox", "QMessageBox", "QGnomeTheme"}
)


def _load_qt_fallback(code: str) -> dict | None:
    """data/i18n/qt/<code>.json — flat source→translation map for Qt's
    standard-button strings. Kept outside data/i18n/*.json so the language
    combobox and the catalog-hygiene tests don't pick it up."""
    path = resource_path(f"data/i18n/qt/{code}.json")
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.warning("Broken Qt fallback catalog %s", path, exc_info=True)
        return None


def _make_json_qt_translator():
    from PyQt6.QtCore import QTranslator

    class _JsonQtTranslator(QTranslator):
        """Answers Qt-internal lookups from a plain dict; returning a
        null string (None) lets Qt fall through to the untranslated source."""

        def __init__(self, catalog: dict, parent=None):
            super().__init__(parent)
            self._catalog = catalog

        def isEmpty(self) -> bool:  # noqa: N802 — Qt naming
            return False

        def translate(self, context, source, disambiguation=None, n=-1):
            # None, not "": PyQt hands "" to Qt as an EMPTY string, which
            # Qt takes as the answer, so every Qt string the catalogue does
            # not hold came out blank (Norwegian's line-edit menu read
            # "", "", "" for Undo, Cut, Copy). None is Qt's null string,
            # and a null answer is what lets the next translator, or the
            # English source, speak instead.
            if context in _QT_FALLBACK_CONTEXTS:
                found = self._catalog.get(source)
                return found if found else None
            return None

    return _JsonQtTranslator


try:
    _JsonQtTranslator = _make_json_qt_translator()
except Exception:  # PyQt6 absent (pure-logic test environments)
    _JsonQtTranslator = None


# ----------------------------------------------------------------------
# parameters.yaml overlay
# ----------------------------------------------------------------------

# Text fields of a parameter definition that an overlay may replace.
_PARAM_TEXT_FIELDS = ("name", "tooltip_title", "tooltip_body")


def translate_parameters(params: dict[str, Any]) -> dict[str, Any]:
    """Merge data/i18n/parameters.<lang>.yaml over loaded parameter defs.

    The overlay mirrors the structure  {tool: {flag: {field: text}}}.
    Only known text fields are taken; a `labels` list is only applied
    when its length matches the original (a stale overlay must never
    desynchronise labels from their `choices` values).
    Returns `params` unchanged for English or when no overlay exists.
    """
    if _language == SOURCE_LANGUAGE:
        return params
    overlay = _load_parameters_overlay(_language)
    if not overlay:
        return params
    for tool, defs in params.items():
        tool_overlay = overlay.get(tool)
        if not isinstance(tool_overlay, dict) or not isinstance(defs, list):
            continue
        for param in defs:
            entry = tool_overlay.get(str(param.get("flag")))
            if not isinstance(entry, dict):
                continue
            for field in _PARAM_TEXT_FIELDS:
                if isinstance(entry.get(field), str):
                    param[field] = entry[field]
            labels = entry.get("labels")
            if isinstance(labels, list):
                if len(labels) == len(param.get("labels", [])):
                    param["labels"] = [str(x) for x in labels]
                else:
                    log.warning(
                        "parameters.%s.yaml: label count mismatch for %s %s "
                        "(%d vs %d) — keeping English labels",
                        _language, tool, param.get("flag"),
                        len(labels), len(param.get("labels", [])),
                    )
    return params


def _load_parameters_overlay(code: str) -> dict[str, Any]:
    try:
        override = user_i18n_dir() / f"parameters.{code}.yaml"
        path = override if override.exists() else \
            resource_path(f"data/i18n/parameters.{code}.yaml")
        if not path.exists():
            return {}
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("parameters", {})
    except Exception:
        log.error("Cannot load parameters overlay for %r", code, exc_info=True)
        return {}


# ----------------------------------------------------------------------
# Catalog hygiene helpers (used by tests / completeness tooling)
# ----------------------------------------------------------------------

def placeholders(text: str) -> set[str]:
    """The set of str.format placeholder fields in `text` ({name} or {0})."""
    fields = set()
    for _, field, _, _ in string.Formatter().parse(text):
        if field is not None:
            # strip attribute/index access: "a.b" / "a[0]" -> "a"
            fields.add(re.split(r"[.\[]", field)[0])
    return fields


def check_placeholders(catalog: dict[str, str]) -> list[str]:
    """Return a list of catalog keys whose translation's placeholders
    don't exactly match the source string's — must be empty for a
    catalog to be safe to ship."""
    bad = []
    for src, dst in catalog.items():
        if src.startswith(_META_PREFIX) or not isinstance(dst, str):
            continue
        try:
            if placeholders(src) != placeholders(dst):
                bad.append(src)
        except ValueError:
            bad.append(src)  # unbalanced braces in translation
    return bad


def catalog_texts(raw: dict) -> "list[tuple[str, str]]":
    """Every (English key, shown text) pair of a loaded catalogue file: the
    plain values and each per-number form under "@plurals", so a check of
    what users read covers the forms too. Metadata ("@…") is left out."""
    out = [(k, v) for k, v in raw.items()
           if not k.startswith(_META_PREFIX) and isinstance(v, str)]
    for k, forms in (raw.get(PLURALS_KEY) or {}).items():
        if isinstance(forms, dict):
            out.extend((k, v) for c, v in forms.items()
                       if c != "count" and isinstance(v, str))
    return out
