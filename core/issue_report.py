"""Pre-filled GitHub issue-form URLs (#56).

The "Report a Bug" / "Request a Feature" buttons open GitHub's web issue forms.
We pre-fill the fields ChromIQ can detect reliably — version, platform, OS — via
the templates' query-parameter support (each `id:` in the .yml is a query key),
so the reporter fills in fewer fields by hand. Fields we can't know for sure
(hardware, ArgyllCMS version, instrument, the descriptions) are left blank.
"""
from __future__ import annotations

import platform as _pf
import re
from pathlib import Path
from urllib.parse import urlencode

from core.proc_text import run_text
from core.version import APP_VERSION

_ISSUES_NEW = "https://github.com/itsab1989/ChromIQ/issues/new"


def detect_platform_option() -> str:
    """The current platform as one of the templates' dropdown option labels."""
    system = _pf.system()
    mach = (_pf.machine() or "").lower()
    if system == "Darwin":
        return ("macOS (Apple Silicon)" if mach in ("arm64", "aarch64")
                else "macOS (Intel)")
    if system == "Windows":
        return ("Windows (ARM64)" if mach in ("arm64", "aarch64")
                else "Windows (x64)")
    if system == "Linux":
        return "Linux"
    return "Other / not sure"


def detect_os_version() -> str:
    """A human-readable OS version string for the `os_version` field."""
    system = _pf.system()
    try:
        if system == "Darwin":
            ver = _pf.mac_ver()[0]
            return f"macOS {ver}" if ver else "macOS"
        if system == "Windows":
            rel = _pf.win32_ver()[0] or _pf.release()
            return f"Windows {rel}".strip()
    except Exception:  # noqa: BLE001 — detection is best-effort
        pass
    return _pf.platform()


def detect_hardware() -> str:
    """A short hardware string for the `hardware` field, best-effort."""
    system = _pf.system()
    try:
        if system == "Darwin":
            model = run_text(
                ["sysctl", "-n", "hw.model"], capture_output=True,
                timeout=3).stdout.strip()
            chip = run_text(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, timeout=3).stdout.strip()
            return ", ".join(p for p in (model, chip) if p)
        if system == "Windows":
            return ", ".join(p for p in (_pf.machine(), _pf.processor()) if p)
        if system == "Linux":
            return ", ".join(p for p in (_pf.machine(), _pf.processor()) if p)
    except Exception:  # noqa: BLE001 — detection is best-effort
        pass
    return ""


def detect_argyll_version(argyll_bin: str | Path | None) -> str:
    """ArgyllCMS version + install path for the `argyll_version` field.

    Runs a bundled Argyll tool to read its version (printed in the usage banner),
    and appends the install folder as the "install method"."""
    if not argyll_bin:
        return ""
    bin_dir = Path(argyll_bin)
    version = ""
    exe = "targen.exe" if _pf.system() == "Windows" else "targen"
    tool = bin_dir / exe
    if tool.is_file():
        try:
            out = run_text([str(tool)], capture_output=True, timeout=5)
            m = re.search(r"[Vv]ersion\s+(\d+\.\d+(?:\.\d+)?)",
                          (out.stderr or "") + (out.stdout or ""))
            if m:
                version = m.group(1)
        except Exception:  # noqa: BLE001
            pass
    if version:
        return f"{version}, installed at {bin_dir}"
    return f"installed at {bin_dir}" if bin_dir else ""


def build_bug_report_url(argyll_bin: str | Path | None = None) -> str:
    """GitHub bug-report form, pre-filled with the auto-detectable fields."""
    params = {
        "template": "bug_report.yml",
        "chromiq_version": f"v{APP_VERSION}",
        "platform": detect_platform_option(),
        "os_version": detect_os_version(),
    }
    hw = detect_hardware()
    if hw:
        params["hardware"] = hw
    argyll = detect_argyll_version(argyll_bin)
    if argyll:
        params["argyll_version"] = argyll
    return _ISSUES_NEW + "?" + urlencode(params)


def build_feature_request_url() -> str:
    """GitHub feature-request form, pre-filled with the current platform."""
    return _ISSUES_NEW + "?" + urlencode({
        "template": "feature_request.yml",
        "platform": detect_platform_option(),
    })
