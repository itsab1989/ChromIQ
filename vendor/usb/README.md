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
(https://github.com/libusb/libusb/releases/tag/v1.0.30) and, as packaged, the `libusb-package`
1.0.30.1 source distribution on PyPI (https://pypi.org/project/libusb-package/1.0.30.1/#files).

Not bundled: Windows on ARM64 (`libusb-package` publishes no wheel for it); that build has no table
drive and says so.

sha256 of the files here: see `tests/test_usb_library.py`, which pins them.
