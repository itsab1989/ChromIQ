"""The Windows USB driver installer's third-party notices (found in build step 6): wdi-simple
(libwdi), the libusb-win32 and libusbK packages it embeds, and Zadig ship in the Windows build,
so their licence texts travel with it and THIRD-PARTY-NOTICES.md names them, as for the USB
library (tests/test_usb_library.py)."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "vendor" / "usb-driver-installer"

#: taken on 2026-11-17 from the pinned sources the Windows build uses
LICENCES = {
    "libwdi-COPYING-LGPL": "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
    "libwdi-COPYING": "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903",
    "libwdi-AUTHORS": "e9e61d16854cd24d72b62df22e5346b1c279522123ce9231d6c4bf32003d531d",
    "libusb-win32-installer_license.txt":
        "1a590bfda657dbf1756cd3caa19accf31bf7fae5490e61417d208757fb79bac0",
    "libusb-win32-COPYING_GPL.txt":
        "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903",
    "libusb-win32-COPYING_LGPL.txt":
        "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
    "libusb-win32-AUTHORS.txt": "52718d277bd2878c1df3c26dd59e0f8fbdaf0de8a9ab9a523f85d753c1f02706",
    "libusbK-LICENSE-bsd.txt": "0649d566561ce1a8b0f7521c4c62e046f7ef81cefe0a993c9463a3e3f4a8a328",
    "libusbK-AUTHORS.txt": "058fbd0223733c26b93dae46d8cef249d4d363623c51c12372ecf93dd5ed2d1b",
}


def test_the_licence_texts_are_the_packages_own():
    for name, sha in LICENCES.items():
        assert hashlib.sha256((V / name).read_bytes()).hexdigest() == sha, name
    assert (V / "libwdi-COPYING-LGPL").read_text(encoding="utf-8").lstrip().startswith(
        "GNU LESSER GENERAL PUBLIC LICENSE\n                       Version 3")
    assert (V / "libwdi-COPYING").read_text(encoding="utf-8").lstrip().startswith(
        "GNU GENERAL PUBLIC LICENSE\n                       Version 3")
    terms = (V / "libusb-win32-installer_license.txt").read_text(encoding="utf-8")
    assert "Driver:      GNU General Public License (GPL)" in terms
    assert "Library, Test Files, Installer:    GNU Lesser General Public License (LGPL)" in terms
    assert "Redistributions in binary form must reproduce the above copyright" in \
        (V / "libusbK-LICENSE-bsd.txt").read_text(encoding="utf-8")


def test_the_windows_build_ships_them_and_the_notices_name_them():
    spec = (ROOT / "ChromIQWin.spec").read_text(encoding="utf-8")
    assert "*_driver_installer_licences" in spec and "'licenses/usb-driver-installer'" in spec
    for name in list(LICENCES) + ["README.md"]:
        assert f"'{name}'" in spec, name
    assert "'usb.backend.libusb0'" in spec
    notices = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    sec = notices.split("## USB driver installer on Windows", 1)[1].split("\n## ", 1)[0]
    flat = " ".join(sec.split())
    for text in ("libwdi", "30df0c0e051b0132c4b9ebed8c054bc8eb3aaaec",
                 "GNU Lesser General Public License, version 3 or later",
                 "Zadig 2.9", "GNU General Public License, version 3 or later",
                 "libusb-win32 1.4.0.0", "the driver under the GNU General Public License",
                 "libusbK 3.1.0.0", "New BSD", "WDF co-installer",
                 "https://github.com/mcuee/libusb-win32/releases/tag/release_1.4.0.0"):
        assert text in flat, text
    readme = (V / "README.md").read_text(encoding="utf-8")
    for name in LICENCES:
        assert name in readme, name
    # the pins the notices quote are the build's own
    wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
    assert "30df0c0e051b0132c4b9ebed8c054bc8eb3aaaec" in wf
    assert "libusb-win32-bin-1.4.0.0.zip" in wf and "libusbK-3.1.0.0-bin.7z" in wf
    assert "zadig-2.9.exe" in wf
    from ui.licences import NOTICE_SECTIONS
    assert "USB driver installer on Windows" in NOTICE_SECTIONS
