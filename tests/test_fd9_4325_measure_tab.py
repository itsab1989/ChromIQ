"""4.3.25, F8: the Measure tab for an FD-9 chart looks like the tab for any
other instrument.

* the FD-9's row sits under the STEP 03 heading (it was above it), as a
  "Measurement Options" group, with the condition as an ordinary row;
* chartread's options are HIDDEN for an FD-9 chart, not just greyed, so
  chartread's Resume no longer stands beside the FD-9's own; leaving the FD-9
  chart gives every group back exactly as it was;
* the preview is titled with the chart's name, not a cache file's.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
from tests.test_fd9_beta_option import (_plain_chart, fd9_chart,  # noqa: F401
                                        tab)


def test_the_fd9_group_is_under_the_heading_and_the_chart_file(tab):
    from PyQt6.QtWidgets import QGroupBox
    panel = tab._fd9_panel
    assert isinstance(panel, QGroupBox) and panel.title() == "Measurement Options"
    assert panel.parentWidget() is tab._file_grp.parentWidget()
    lay = panel.parentWidget().layout()
    assert lay.indexOf(panel) == lay.indexOf(tab._file_grp) + 1
    # The condition is a row of its own, labelled as the other rows are.
    from PyQt6.QtWidgets import QLabel
    labels = [lb.text() for lb in panel.findChildren(QLabel)]
    assert "Measurement condition:" in labels


def test_chartread_options_are_hidden_and_given_back(tab, fd9_chart,
                                                     tmp_path):
    plain = _plain_chart(tmp_path)
    tab.set_ti1_path(plain.with_suffix(".ti1"))
    groups = tab._fd9_chartread_groups()
    assert groups
    before = {id(g): g.isHidden() for g in groups}
    assert tab._fd9_panel.isHidden()
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert all(g.isHidden() for g in groups)
    assert tab._guided_fixed_lbl in groups      # chartread's flags, named
    assert not tab._fd9_panel.isHidden()
    assert tab._resume_cb.isHidden() or tab._resume_cb.parentWidget().isHidden() \
        or any(g.isAncestorOf(tab._resume_cb) for g in groups)
    tab.set_ti1_path(plain.with_suffix(".ti1"))
    assert {id(g): g.isHidden() for g in groups} == before
    assert tab._fd9_panel.isHidden()


def test_the_preview_is_titled_with_the_charts_name(tab, fd9_chart):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert tab._fd9_load_preview(fd9_chart)
    names = [p.stem for p in tab._tiff_pages]
    assert names and all(n.startswith(fd9_chart.stem + "_") for n in names)
    assert tab._preview._filename_lbl.text() == fd9_chart.stem
