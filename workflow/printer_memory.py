"""What the user's own prints through the macOS print dialog taught ChromIQ.

Beta 15 (Basti, 2026-10-08): the direct ``lp`` route must send the paper profile
the vendor's print dialog would write for the medium.  For the models whose
driver tables ChromIQ can read, or which it has measured, it knows that value
(``workflow.ppd_color``).  For any other model it learns it: after a print
through the macOS dialog the job is read back from CUPS
(``workflow.print_ticket``), and the paper-profile key the dialog wrote is kept
here, per printer model, medium and print quality.  The next direct print of
that model and medium sends the same key.

This is part of the user's setup, not of a target: it is global
(docs/design/per_target_settings.md section 1.1, "your setup"), and lives in
ChromIQ's settings folder beside the presets, as ``printer_paper_profiles.json``.
A driver run that sandboxes the settings (``CHROMIQ_SETTINGS_FILE``) keeps it
beside that file instead, so the real one is never touched.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: Point the memory at a file of your own (tests, drivers).
MEMORY_FILE_ENV = "CHROMIQ_PRINTER_MEMORY_FILE"
FILE_NAME = "printer_paper_profiles.json"
_SCHEMA = 1
_lock = threading.Lock()


def memory_path() -> Path:
    """Where the learned paper profiles live (see the module docstring)."""
    override = os.environ.get(MEMORY_FILE_ENV, "").strip()
    if override:
        return Path(override)
    from core.settings import SETTINGS_FILE_ENV
    sandbox = os.environ.get(SETTINGS_FILE_ENV, "").strip()
    if sandbox:
        p = Path(sandbox)
        return p.with_name(p.stem + "." + FILE_NAME)
    from core.platform_paths import presets_dir
    return presets_dir().parent / FILE_NAME


class PaperProfileMemory:
    """The learned entries, one per (model, medium, quality)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else memory_path()

    # -- storage -----------------------------------------------------------------
    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema": _SCHEMA, "models": {}}
        except (OSError, ValueError) as exc:
            log.warning("printer memory %s unreadable (%s); starting empty", self.path, exc)
            return {"schema": _SCHEMA, "models": {}}
        if not isinstance(data, dict) or not isinstance(data.get("models"), dict):
            return {"schema": _SCHEMA, "models": {}}
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    @staticmethod
    def _key(media_option: str, media_value: str, quality_option: str, quality: str) -> str:
        return f"{media_option}={media_value}|{quality_option}={quality}"

    # -- the two questions ---------------------------------------------------------
    def lookup(self, model: str, media_option: str, media_value: str,
               quality_option: str = "", quality: str = "") -> dict | None:
        """The entry the dialog wrote for *model* and this medium.

        With *quality* given (the Print Chart tab offers the model's quality),
        that quality's entry wins.  Without one (Canon: the tab has no quality
        control, so lp would send the PPD's default) the newest entry for the
        medium is used, and its ``keys`` carry the quality the dialog wrote, so
        the job is the dialog's."""
        with _lock:
            entries = (self._load()["models"].get(model) or {})
        prefix = f"{media_option}={media_value}|"
        hits = [e for k, e in entries.items() if k.startswith(prefix)]
        if not hits:
            return None
        newest = dict(max(hits, key=lambda e: e.get("learned_at", 0)))
        if not quality:
            return newest
        exact = entries.get(self._key(media_option, media_value, quality_option, quality))
        if exact is not None:
            return exact
        # The tab asks for a quality the dialog was never used with.  The
        # paper profile depended on the quality on no model whose tables were
        # read (vendor tests 2026-10-08, PRO-100 apart), so one value seen for
        # every quality of the medium is used, at the tab's own quality; two
        # different values leave the model unknown for this quality.
        if len({str(e.get("value")) for e in hits}) != 1:
            return None
        newest["keys"] = {k: v for k, v in (newest.get("keys") or {}).items()
                          if k != quality_option}
        return newest

    def record(self, model: str, vendor: str, media_option: str, media_value: str,
               quality_option: str, quality: str, profile_option: str, value: str,
               label: str = "", keys: dict[str, str] | None = None,
               queue: str = "") -> bool:
        """Keep what the dialog wrote.  Returns True when the entry is new or
        changed (logged), False when it was already known."""
        if not (model and media_value and value):
            return False
        entry = {"vendor": vendor, "media_option": media_option, "media": media_value,
                 "quality_option": quality_option, "quality": quality,
                 "option": profile_option, "value": value, "label": label,
                 "keys": dict(keys or {}), "queue": queue,
                 "learned_at": time.time()}
        k = self._key(media_option, media_value, quality_option, quality)
        with _lock:
            data = self._load()
            models = data.setdefault("models", {})
            old = (models.get(model) or {}).get(k)
            same = old is not None and all(
                old.get(f) == entry[f] for f in ("value", "keys"))
            models.setdefault(model, {})[k] = entry
            try:
                self._save(data)
            except OSError as exc:
                log.warning("printer memory: could not save %s: %s", self.path, exc)
                return False
        if not same:
            log.info("printer memory: %s, %s=%s, %s=%s -> %s=%s (%s) learned from the "
                     "dialog", model, media_option, media_value, quality_option,
                     quality or "-", profile_option, value, label)
        return not same


def learn_from_report(report, memory: PaperProfileMemory | None = None) -> bool:
    """Record what a dialog-route job carries (a ``print_ticket.TicketReport``
    read back from CUPS).  Only a job in application colour matching that names
    the medium and its paper profile teaches anything."""
    from workflow.ppd_color import APPLICATION_COLOUR_MATCHING
    pp = getattr(report, "paper_profile", None)
    if report is None or not report.read or pp is None or not pp.model:
        return False
    carried = report.carried
    want = APPLICATION_COLOUR_MATCHING["AP_ColorMatchingMode"]
    if str(carried.get("AP_ColorMatchingMode")) != want:
        return False
    value = carried.get(pp.option)
    media = carried.get(pp.rule.media_option)
    if value is None or media is None:
        return False
    quality = str(carried.get(pp.rule.quality_option, "")) if pp.rule.quality_option else ""
    names = {k for k, _ in pp.rule.dialog_keys} | {"EPIJ_Mode", "EPIJ_CCor"}
    keys = {k: str(carried[k]) for k in sorted(names) if k in carried}
    if pp.rule.quality_option and quality:
        keys[pp.rule.quality_option] = quality
    return (memory or PaperProfileMemory()).record(
        pp.model, pp.rule.vendor, pp.rule.media_option, str(media),
        pp.rule.quality_option, quality, pp.option, str(value), pp.label, keys,
        queue=report.queue)
