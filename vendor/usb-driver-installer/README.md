# The Windows USB driver installer: what ships and on what terms

ChromIQ's Windows build ships two driver installers (`core/usb_driver_installer.py`):
`assets/wdi_simple.exe`, built in CI from **libwdi** at commit
30df0c0e051b0132c4b9ebed8c054bc8eb3aaaec with three driver packages embedded, and
`assets/zadig.exe` (Zadig 2.9, libwdi v1.5.1), the fallback. This folder holds their licence
texts, which `ChromIQWin.spec` copies into the app under `licenses/usb-driver-installer/`
(`THIRD-PARTY-NOTICES.md`, "USB driver installer on Windows"). Every text here was taken from the
pinned sources the build uses (`.github/workflows/build-windows.yml`), on 2026-11-17.

| what ships | terms (read from its own files) | licence text here |
|---|---|---|
| wdi-simple (libwdi's example program) and libwdi inside it, (c) 2010-2023 Pete Batard and the contributors in `libwdi-AUTHORS` | GNU LGPL version 3 or later (`libwdi/libwdi.c`, `examples/wdi-simple.c` headers; README "LGPL v3") | `libwdi-COPYING-LGPL` (libwdi's COPYING-LGPL), `libwdi-COPYING` (the GPL v3 text the LGPL v3 builds on, libwdi's COPYING), `libwdi-AUTHORS` |
| Zadig 2.9, (c) 2010-2025 Pete Batard | GNU GPL version 3 or later (`examples/zadig.c` header) | `libwdi-COPYING` |
| libusb-win32 1.4.0.0 (embedded in wdi-simple: the driver `libusb0.sys`, the library `libusb0.dll`, the installer parts), (c) Stephan Meyer, Johannes Erdfelt, Thomas Sailer, Travis Robinson and the authors in `libusb-win32-AUTHORS.txt` | "Driver: GNU General Public License (GPL); Library, Test Files, Installer: GNU Lesser General Public License (LGPL)", both version 3 (the package's own `installer_license.txt`, `COPYING_GPL.txt`, `COPYING_LGPL.txt`) | `libusb-win32-installer_license.txt`, `libusb-win32-COPYING_GPL.txt`, `libusb-win32-COPYING_LGPL.txt`, `libusb-win32-AUTHORS.txt` |
| libusbK 3.1.0.0 (embedded in wdi-simple), (c) 2011-2012 Travis Lee Robinson | the New BSD licence option of its dual licence (the bin package carries no licence file; text from the source tag V3.1.0.0, `libusbK/license/LICENSE-bsd.txt`) | `libusbK-LICENSE-bsd.txt`, `libusbK-AUTHORS.txt` |

Sources: libwdi https://github.com/pbatard/libwdi (commit above; Zadig 2.9 is its release v1.5.1),
libusb-win32 https://github.com/mcuee/libusb-win32/releases/tag/release_1.4.0.0, libusbK
https://github.com/mcuee/libusbk/releases/tag/V3.1.0.0. ChromIQ changes none of them; wdi-simple
is built from libwdi's unmodified source (CI compiles libwdi's own `wdi-simple.rc` into it).

Not covered here, said in the notices: wdi-simple also embeds Microsoft's WDF co-installer from
the Windows Driver Kit 8.0 redistributable (`wdfcoinstaller.msi`), under Microsoft's terms from
that package; they were not re-checked for this entry.

sha256 of the files here: see `tests/test_usb_driver_installer_notices.py`, which pins them.
