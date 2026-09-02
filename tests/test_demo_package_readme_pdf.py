"""The demo package ships a printable copy of its own steps.

Knut, beta.139: *"Also, in the demo project package, make a pdf version of the
readme.md file, every time it is rebuilt."* The steps are walked next to an
instrument, so a copy you can put on a tablet or print and tick off is the point.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


SAMPLE = """# Demo package

Some prose that has to survive the trip.

## Demo-01

| Step | Do this | You should see |
|---|---|---|
| 1 | Open the project | The chart appears |
| 2 | Press Generate | A warning window |

```
a fenced block
```
"""


def test_a_pdf_is_written_beside_the_markdown(tmp_path, qapp):
    from scripts.make_demo_package import write_readme_pdf

    md = tmp_path / "README.md"
    md.write_text(SAMPLE, encoding="utf-8")
    pdf = write_readme_pdf(md)

    assert pdf is not None and pdf.exists()
    assert pdf.name == "README.pdf"
    assert pdf.read_bytes()[:5] == b"%PDF-", "not a PDF"
    # Big enough to be the rendered document rather than an empty page.
    assert pdf.stat().st_size > 4096


def test_rebuilding_replaces_the_pdf(tmp_path, qapp):
    """"every time it is rebuilt" — a stale PDF beside a fresh README would be
    worse than none."""
    from scripts.make_demo_package import write_readme_pdf

    md = tmp_path / "README.md"
    md.write_text(SAMPLE, encoding="utf-8")
    write_readme_pdf(md)
    first = (tmp_path / "README.pdf").read_bytes()

    md.write_text(SAMPLE + "\n## Demo-02\n\nA whole extra section.\n" * 40, encoding="utf-8")
    write_readme_pdf(md)
    second = (tmp_path / "README.pdf").read_bytes()

    assert second != first, "the PDF was not re-rendered"
    assert len(second) > len(first)


def test_the_package_self_check_demands_the_pdf():
    """The build's own verification fails if the PDF is missing, so it cannot
    quietly stop being produced."""
    import inspect
    from scripts import make_demo_package

    src = inspect.getsource(make_demo_package)
    assert "README.pdf is missing" in src
