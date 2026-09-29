"""Target-rename chooser dialog (#52): button labels must not clip."""
import pytest

pytest.importorskip("PyQt6")
from pathlib import Path  # noqa: E402

from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

from ui.dialogs.target_change_dialog import TargetChangeDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("old,new", [
    ("Glossy", "Matte"),
    ("Canon-PRO-300-Hahnemuehle-PhotoRag-308-Glossy",
     "Canon-PRO-300-Hahnemuehle-FineArt-Baryta-Matte"),     # long names (#52)
])
def test_option_buttons_are_wide_enough_for_their_text(qapp, old, new):
    dlg = TargetChangeDialog(old, new, Path("/u/" + old), Path("/u/" + new))
    dlg.resize(dlg.sizeHint())
    dlg.show()
    qapp.processEvents()
    try:
        # Only the #52 option buttons carry an explicit minimum width; the
        # plain Cancel button uses Qt's own default sizing, which fits "Cancel"
        # without our heuristic.
        option_btns = [b for b in dlg.findChildren(QPushButton)
                       if b.minimumWidth() > 0]
        assert option_btns
        for b in option_btns:
            need = b.fontMetrics().horizontalAdvance(b.text())
            # THE TEXT MUST FIT. It used to demand need + 36 as well — the
            # stylesheet's 18px padding on each side — but that turned a
            # comfortable margin into a requirement, and requiring it of every
            # button's MINIMUM width is what made rows of buttons overlap rather
            # than tighten (Sebastian, #130 2026-07-29). The margin is still
            # applied; it is simply no longer something a very long label has to
            # find room for on top of itself. This label is a whole project name
            # twice over, and at 794px for 762px of text it is not clipped.
            assert b.width() >= need, f"clipped: {b.text()!r}"
    finally:
        dlg.close()


def test_the_heading_is_one_grammatical_sentence(qapp):
    """The heading dropped its subject halfway through, for months.

    On screen it read *"You already created the profile "gen-a", and now asked
    to generate one called "gen-b"."* — "You ... now asked" has no subject that
    works, and every one of the thirteen translations had quietly written the
    sentence the English meant to be. Found by driving a second Generate in one
    session (2026-09-19); the window itself was doing exactly the right thing,
    which is why nothing before this had looked at what it said.

    Pinned here rather than left to a reader's ear: a wording that thirteen
    catalogues are keyed on cannot be corrected twice.
    """
    from PyQt6.QtWidgets import QLabel

    dlg = TargetChangeDialog("gen-a", "gen-b", Path("/u/gen-a"), Path("/u/gen-b"))
    try:
        heads = [l.text() for l in dlg.findChildren(QLabel)
                 if l.text().startswith("You already created")]
        assert heads, "the heading is gone, or no longer starts the same way"
        assert heads[0] == (
            'You already created the profile "gen-a", and have now asked for '
            'one called "gen-b".'), heads[0]
    finally:
        dlg.close()
