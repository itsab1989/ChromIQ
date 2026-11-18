# USB libraries of the i1iO table drive: what ships and on what terms

ChromIQ's i1iO table drive (part of the i1iO Beta; `core/usb_library.py`) opens an X-Rite i1iO 2
table over USB with **pyusb** on top of **libusb-1.0**. The three PyInstaller specs bundle them from
the packages pinned in `requirements.txt`; this folder holds their licence texts, which the specs
copy into the app under `licenses/usb/` (`THIRD-PARTY-NOTICES.md`, "USB access for the i1iO table").

| what ships | from | terms | licence text here |
|---|---|---|---|
| pyusb 1.2.1 (Python) | PyPI `pyusb` | BSD 3-clause, (c) 2009-2017 Wander Lairson Costa, 2009-2021 PyUSB contributors | `pyusb-LICENSE` (the wheel's own) |
| libusb-package 1.0.30.1 (Python part) | PyPI `libusb-package` | Apache 2.0 | `libusb-package-LICENSE` (the wheel's own) |
| libusb-1.0 1.0.30 (the shared library inside that wheel: `libusb-1.0.dylib` / `.dll` / `.so`) | built by the `libusb-package` project from libusb 1.0.30 | LGPL 2.1 or later; copyright holders in `libusb-AUTHORS` | `libusb-COPYING`, `libusb-AUTHORS` (libusb 1.0.30's own files, as installed by Homebrew's libusb 1.0.30) |
| importlib_resources 7.1.0 (Python, needed by libusb-package) | PyPI `importlib_resources` | Apache 2.0 | `importlib_resources-LICENSE` (the wheel's own) |

**LGPL 2.1 for libusb.** ChromIQ does not change libusb and links it only at run time (`ctypes`
loads the separate library file), so the library can be replaced by another build of it. Its
complete source is libusb 1.0.30 as published by the libusb project
(https://github.com/libusb/libusb/releases/tag/v1.0.30)
and, as packaged, the `libusb-package` project's tag v1.0.30.1 (https://github.com/pyocd/libusb-package/tree/v1.0.30.1), which builds it from libusb's unmodified v1.0.30 source (included there as a submodule).

Not bundled: Windows on ARM64 (`libusb-package` publishes no wheel for it), and that build needs
none: on Windows the table drive lists devices through Windows' cfgmgr32 and opens the table through
libusb-win32's `libusb0.dll`, which ChromIQ's driver installer puts into System32 (ARM64 there,
measured 2026-11-18). Nothing more is bundled for it.

sha256 of the files here: see `tests/test_usb_library.py`, which pins them.

The `libusb-package` 1.0.30.1 wheels on PyPI (uploaded 2026-11-09, no provenance attestation; the
review of 2026-11-17 inspected them, did not rebuild them), first 16 hex digits of their sha256 as
PyPI lists them: macOS x86_64 `7ee86d9e...`, macOS arm64 `46c7ca99...`, manylinux x86_64
`7fed1daa...`, win_amd64 `57ed5757...`. A build that installs a different file is a change to be
looked at, not taken silently.
