"""Preset metric certificates (#182, Knut 6045500910, answer 5; beta 12).

Knut: *"at every release of the app it is checked if any new built-in presets
exists, and if those that exist have been checked a certificate is stored
telling if a chart can accommodate all 18 metrics or not. [...] On an
installed ChromIQ app, when opening the window in Create chart (or the check
when entering run type verification) to check which metrics a preset may
answer, the certificate is first checked. IF existing, the number in the
certificate is used without having to regenerate the preset's chart. Only if
any other presets exist, such as a locally made preset, does not have the
certificate, then a chart i[s] generated for those presets and a certificate
is created. If a local preset is later deleted, the certificate is also
deleted, and if the preset is updated/changed, then the certificate must be
re-created."*

A certificate is the answer :func:`workflow.preset_eligibility.chart_row_values`
gives for a preset's chart (``{row_id: {"value", "reason", ...}}``, every
metric the chart can and cannot answer, and why). Every count the presets
window and the run-type check show is derived from it with the limits of the
moment, so one certificate serves every report type and limit set.

It is valid only for

* the **same preset**: :func:`preset_hash`, a SHA-256 of the chart file, its
  layout recipe (machine paths taken out, a file it names hashed by content)
  and every file beside the chart the answer reads (the ``.ti2``, the
  ``.channels.json``, the page images, a colorimetric reference); and
* the **same judge**: :func:`code_version`, the app version and the
  certificate format. A new ChromIQ never trusts an older one's answer.

Two stores:

* **built-in presets**, ``data/preset_certificates.json``, shipped with the
  app and written at release time by ``scripts/make_preset_certificates.py``;
* **the user's own presets**, ``preset_certificates.json`` beside the presets
  folder (never in the repository), written the first time a preset is
  checked, replaced when the preset changes, and dropped when it is deleted.

A stale certificate is never used: a lookup that does not match both keys is
a miss, and the chart is worked out as before.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: Bump when what a certificate holds changes shape.
CERT_FORMAT = 1

#: The shipped file, relative to the app's resource root.
SHIPPED_ASSET = "data/preset_certificates.json"

#: Recipe keys that name THIS machine (the ArgyllCMS folder), not the preset.
_MACHINE_KEYS = frozenset({"argyll_bin"})

_lock = threading.RLock()
_hash_memo: "dict[tuple, str]" = {}
_shipped: "dict | None" = None
_user: "dict | None" = None
#: Tests (and the release script) switch certificates off to compute afresh.
_disabled = False


def code_version() -> str:
    """The judge a certificate was made by: app version and format."""
    try:
        from core.version import APP_VERSION
    except Exception:      # noqa: BLE001
        APP_VERSION = "unknown"
    return f"{APP_VERSION}/cert{CERT_FORMAT}"


def user_store_path() -> Path:
    """The user's own certificates, beside the presets folder (sandboxed with
    it by ``CHROMIQ_PRESETS_DIR``)."""
    from core.platform_paths import presets_dir
    return presets_dir().parent / "preset_certificates.json"


def _sha_file(p: Path) -> str:
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    hit = _hash_memo.get(key)
    if hit is None:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        hit = _hash_memo[key] = h.hexdigest()
    return hit


def _normal(value, chart_dir: Path):
    """The recipe with this machine taken out: a path to a file becomes the
    file's name and content hash, so the same preset hashes the same on every
    computer and a changed file is a changed preset."""
    if isinstance(value, dict):
        return {k: _normal(v, chart_dir) for k, v in sorted(value.items())
                if k not in _MACHINE_KEYS}
    if isinstance(value, (list, tuple)):
        return [_normal(v, chart_dir) for v in value]
    if isinstance(value, str) and ("/" in value or "\\" in value):
        p = Path(value)
        try:
            if p.is_file():
                return {"file": p.name, "sha256": _sha_file(p)}
        except OSError:
            pass
        return value.replace("\\", "/").rsplit("/", 1)[-1]
    return value


def _beside(chart: Path) -> "list[Path]":
    """The files beside the chart its answer reads."""
    from core.file_manager import stem_files
    from workflow.verification_print import colorimetric_reference_for
    ti2 = chart if chart.suffix.lower() == ".ti2" else chart.with_suffix(".ti2")
    out = [ti2, ti2.with_suffix(".channels.json"),
           colorimetric_reference_for(chart)]
    out += sorted(stem_files(ti2.parent, ti2.stem, ".tif", ".TIF", ".tiff",
                             "_*.tif", "_*.TIF", "_*.tiff"))
    return [p for p in dict.fromkeys(out) if p != chart and p.is_file()]


def preset_hash(chart: "str | Path", recipe: "dict | None") -> str:
    """The preset's identity for a certificate. Raises OSError when the chart
    cannot be read."""
    chart = Path(chart)
    h = hashlib.sha256(b"chromiq-preset-certificate\n")
    h.update(_sha_file(chart).encode())
    h.update(json.dumps(_normal(recipe or {}, chart.parent), sort_keys=True,
                        default=str).encode())
    for p in _beside(chart):
        h.update(f"\n{p.name}:{_sha_file(p)}".encode())
    return h.hexdigest()


def _read(path: Path) -> dict:
    """A certificate store, or ``{}``. A file that is not one (cut short,
    edited by hand, ``"certificates"`` not a mapping) is read as empty, never
    as a reason to fail the presets window (beta-12 review)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    if not isinstance(data.get("certificates"), dict):
        data["certificates"] = {}
    return data


def _shipped_store() -> dict:
    global _shipped
    if _shipped is None:
        from core.resource_path import resource_path
        _shipped = _read(resource_path(SHIPPED_ASSET))
    return _shipped


def _user_store() -> dict:
    global _user
    if _user is None:
        _user = _read(user_store_path())
        _user.setdefault("certificates", {})
    return _user


def _write_user() -> None:
    path = user_store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_user_store(), indent=1, sort_keys=True),
                       encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        log.warning("could not write the preset certificates %s", path,
                    exc_info=True)


def lookup(chart: "str | Path", recipe: "dict | None") -> "dict | None":
    """The certified answer for this preset, or None (no certificate, or a
    stale one: another preset, or another ChromIQ). Never raises."""
    if _disabled:
        return None
    try:
        digest = preset_hash(chart, recipe)
    except OSError:
        return None
    version = code_version()
    with _lock:
        shipped = _shipped_store()
        if shipped.get("code_version") == version:
            cert = (shipped.get("certificates") or {}).get(digest)
            if isinstance(cert, dict) and isinstance(cert.get("values"), dict):
                return cert["values"]
        cert = _user_store()["certificates"].get(digest)
        if (isinstance(cert, dict) and cert.get("code_version") == version
                and isinstance(cert.get("values"), dict)):
            return cert["values"]
    return None


def is_user_preset_chart(chart: "str | Path") -> bool:
    """Whether *chart* is a user preset's own patch set (in the presets
    folder): only those get a certificate in the user's store."""
    from core.platform_paths import presets_dir
    try:
        Path(chart).resolve().relative_to(presets_dir().resolve())
        return True
    except (ValueError, OSError):
        return False


def record(chart: "str | Path", recipe: "dict | None", values: dict) -> bool:
    """Certify *values* for a user preset's chart (replacing that preset's
    earlier certificate). Built-in charts are certified at release time, not
    here. Returns whether a certificate was written. Never raises."""
    if _disabled or not is_user_preset_chart(chart):
        return False
    try:
        digest = preset_hash(chart, recipe)
        values = json.loads(json.dumps(values))
    except (OSError, TypeError, ValueError):
        return False
    # the preset is known by its patch-set file, one per user preset
    name = Path(chart).stem
    with _lock:
        certs = _user_store()["certificates"]
        for k in [k for k, c in certs.items()
                  if isinstance(c, dict) and c.get("preset") == name]:
            del certs[k]
        certs[digest] = {"preset": name, "code_version": code_version(),
                         "values": values}
        _write_user()
    log.info("preset certificate written for %s", name)
    return True


def forget(chart: "str | Path") -> int:
    """Drop the certificate of a deleted user preset, named by its patch-set
    file. Returns how many."""
    preset = Path(chart).stem
    with _lock:
        certs = _user_store()["certificates"]
        gone = [k for k, c in certs.items()
                if isinstance(c, dict) and c.get("preset") == preset]
        for k in gone:
            del certs[k]
        if gone:
            _write_user()
    return len(gone)


def keep_only(charts) -> int:
    """Drop every user certificate whose preset no longer exists (a preset
    removed outside ChromIQ): *charts* are the patch-set files of the user
    presets there are. Returns how many."""
    presets = {Path(c).stem for c in charts}
    with _lock:
        certs = _user_store()["certificates"]
        gone = [k for k, c in certs.items()
                if not isinstance(c, dict) or c.get("preset") not in presets]
        for k in gone:
            del certs[k]
        if gone:
            _write_user()
    return len(gone)


def reset() -> None:
    """Forget what was read from disk (tests, and after the release script)."""
    global _shipped, _user
    with _lock:
        _shipped = None
        _user = None
        _hash_memo.clear()


def set_disabled(off: bool) -> None:
    """Switch certificates off (the release script computes afresh)."""
    global _disabled
    _disabled = bool(off)
