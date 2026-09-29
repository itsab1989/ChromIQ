"""The macOS print dialog is the DEFAULT route, and it silently converted any
chart whose pixels were not RGB.

Adversary round 26, R26-F8. `use_native_print_dialog` defaults to True on
macOS, so this is the path a chart takes unless somebody changes a setting, and
`print_frames` built every page through `Image.convert("RGB")` into an
`NSDeviceRGBColorSpace` bitmap - under a docstring promising *"pixel values
reach the driver unchanged"*. Measured on a real `targen -d4` chart: CMYK
``75,0,128,255`` reached the driver as RGB ``0,0,0``; ``255,255,0,136`` as
``0,0,119``.

What makes it worth a guard rather than a note: an RGB chart is unaffected,
because `convert` is then a no-op, and a six-ink chart already failed loudly,
because PIL cannot open it at all. **Four inks was the one case that went
through quietly** - and quietly is the whole problem, because the printed sheet
then disagrees with the `.ti2` and the `.ti3` measured from it is paired with
values that were never printed.

**APPKIT IS REPLACED FOR BOTH TESTS, AND THAT IS NOT TIDINESS.** The first
version of this file let the CMYK case call the real module, on the reasoning
that the refusal happens before `import AppKit`. It does - until the mutation
that proves the guard removes the refusal, and then the test builds a real
`NSPrintOperation` and **opens the macOS print dialog**, which waits for a
person who is not there. The mutation run hung for ten minutes and had to be
killed. With the fake in place the same mutation comes back as a red naming the
sentinel, in a third of a second, and nothing reaches the window server.

Both directions are pinned. A guard that only proved the refusal would pass
just as well if the route refused every chart there is.
"""
from __future__ import annotations

import sys
import types

import pytest

from PIL import Image  # noqa: E402

pytest.importorskip("PyQt6")

from workflow.native_print_macos import ChartIsNotRGB, print_frames  # noqa: E402


class Reached(RuntimeError):
    """Raised by the fake AppKit: the mode check let this chart through."""


@pytest.fixture()
def no_window_server(monkeypatch):
    fake = types.ModuleType("AppKit")

    class _Rep:
        @staticmethod
        def alloc():
            raise Reached("reached the bitmap")

    fake.NSBitmapImageRep = _Rep
    fake.NSDeviceRGBColorSpace = "NSDeviceRGBColorSpace"
    monkeypatch.setitem(sys.modules, "AppKit", fake)
    return fake


def _tiff(tmp_path, mode, name):
    path = tmp_path / name
    Image.new(mode, (8, 8), 0).save(path, dpi=(300, 300))
    return path


def test_a_four_ink_chart_is_refused_rather_than_converted(
        tmp_path, no_window_server):
    tiff = _tiff(tmp_path, "CMYK", "four-ink.tif")
    with pytest.raises(ChartIsNotRGB) as exc:
        print_frames([(tiff, 0)])
    assert "CMYK" in str(exc.value), (
        "the refusal must name what the chart really is, or nobody can act on it")


def test_an_rgb_chart_still_gets_past_the_check(tmp_path, no_window_server):
    """The gate lets the ordinary chart through, which is the other half."""
    tiff = _tiff(tmp_path, "RGB", "rgb.tif")
    with pytest.raises(Reached):
        print_frames([(tiff, 0)])
