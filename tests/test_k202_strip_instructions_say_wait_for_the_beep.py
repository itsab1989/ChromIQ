"""The strip instructions say to start sliding at the beep (Knut, #202
5951426710): the Calibration Complete window of an i1Pro 2 told him how to slide
but not when, while strips are timed from the beep. The i1Pro and ColorMunki
drivers announce the reading with it (ArgyllCMS issue_scan_ready); a CR30 reads
patch by patch and an unknown instrument is told nothing it may not do."""
from __future__ import annotations

from ui.ti2_loader import measurement_instructions_html as how


def test_i1pro_and_colormunki_say_wait_for_the_beep():
    for fam in ("i1pro", "colormunki"):
        assert "Start sliding when you hear the beep." in how(fam), fam


def test_instruments_without_a_strip_beep_do_not():
    for fam in ("cr30", None, "spectroscan"):
        assert "beep" not in how(fam), fam
