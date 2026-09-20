"""When ChromIQ refuses a file, the words on screen are words ChromIQ wrote.

Two faults measured on screen and one dead line behind them, all in the same
window.

**B8-548.** Picking a `.zip` in the ISO half produced *"ChromIQ could not read
that file: 'utf-8' codec can't decode byte 0xe2 in position 10: invalid
continuation byte"*. `install_user_values` calls
`json.loads(read_text(encoding="utf-8"))`, and BOTH of its failures are
ValueError subclasses, so the caller's catch-all formatted the exception into
the sentence and showed it to a person who had simply picked the wrong file.

**B8-553.** The frame around it doubled the sentence: *"ChromIQ could not read
that file: That file is not text ChromIQ can read."* Every ValueError raised by
an installer in this window is already written English, and the Fogra half had
been doubled the same way since `b7475572`. Challenge round 31 read these
messages as JSON and did not see it. The photograph did.

**B8-551.** And the dead line: `bundled()` assigned `_cache = out` in the
branch taken when `SOURCE.json` cannot be read, while declaring
`global _bundled_cache`, so it wrote a local and threw it away. Harmless, and
unreadable: a reader checking whether a broken SOURCE.json could hide a user's
own supplied sets had to prove that statement did nothing first. The test below
pins the BEHAVIOUR, which is what the line was ambiguous about: a failed read
is not cached, so the sets come back the moment the file can be read again.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest


@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    """The real window, with what it says captured instead of shown modally."""
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    from workflow import reference_sets as rs
    rs.reset_cache()
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    dlg = ReferenceValuesDialog()
    said: list[str] = []
    monkeypatch.setattr(type(dlg), "_say",
                        lambda self, text: said.append(text))
    dlg.show()
    qapp.processEvents()
    try:
        yield dlg, said
    finally:
        dlg.close()


def _a_zip(tmp_path: Path) -> Path:
    z = tmp_path / "not-a-values-file.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("readme.txt", "Fogra ships archives, and a user picks one.")
    return z


def _press_iso_use(dlg, path: Path, monkeypatch):
    """Press the BUTTON, not the handler behind it.

    A guard that calls the slot cannot tell whether any control is wired to it,
    and this project has shipped three dead buttons that way: beta 26's whole
    ISO row raised NameError on every press and five presses were in the log
    before anybody looked.
    """
    import ui.widgets as W
    monkeypatch.setattr(W, "open_file_dialog", lambda *a, **k: str(path))
    from PyQt6.QtWidgets import QPushButton
    wanted = [b for b in dlg.findChildren(QPushButton)
              if "fill" in b.text().lower()]
    use = [b for b in wanted if "use" in b.text().lower()]
    assert use, [b.text() for b in dlg.findChildren(QPushButton)]
    use[0].click()


def test_a_file_that_is_not_text_is_refused_in_chromiqs_own_words(
        window, tmp_path, monkeypatch):
    """No codec, no byte offset, no exception class. B8-548.

    MUTATION, proven to land: let `install_user_values` raise through again and
    the codec message comes back.
    """
    dlg, said = window
    _press_iso_use(dlg, _a_zip(tmp_path), monkeypatch)
    assert said, "the window said nothing at all about a file it refused"
    text = " ".join(said)
    for tell in ("codec", "Traceback", "0xe2", "UnicodeDecodeError",
                 "position 10"):
        assert tell not in text, (
            f"the window showed {tell!r} to a user: {text!r}")
    assert "text" in text.lower(), (
        f"the refusal does not say what was wrong with the file: {text!r}")


def test_the_refusal_is_not_wrapped_in_a_second_sentence(
        window, tmp_path, monkeypatch):
    """B8-553, and it applies to the Fogra half as much as the ISO half.

    MUTATION, proven to land: wrap a ValueError in "ChromIQ could not read that
    file: {error}" again and the doubled opening comes back.
    """
    dlg, said = window
    _press_iso_use(dlg, _a_zip(tmp_path), monkeypatch)
    text = said[0]
    assert not text.startswith("ChromIQ could not read that file:"), (
        f"the window wrapped a sentence it had already written: {text!r}")
    # the tell is a SECOND capitalised opening right after the colon
    assert "file: That file" not in text, f"doubled sentence: {text!r}"


def test_a_source_json_that_cannot_be_read_is_not_cached(tmp_path,
                                                         monkeypatch):
    """B8-551: the failed read must not stick.

    An unreadable `SOURCE.json` is a condition of the disk, not a fact about
    the build, so a cached empty list would outlive the file becoming readable
    and the user would see no reference sets until they restarted.

    MUTATION, proven to land: cache `out` in that branch (which is what the
    dead line looked like it was doing) and the second call still finds none.
    """
    from workflow import reference_sets as rs

    staged = tmp_path / "fogra"
    staged.mkdir(parents=True)
    real = rs._data_dir()
    for f in real.glob("*"):
        (staged / f.name).write_bytes(f.read_bytes())
    good = (staged / "SOURCE.json").read_bytes()
    (staged / "SOURCE.json").write_bytes(b"{ this is not json")

    monkeypatch.setattr(rs, "_data_dir", lambda: staged)
    rs.reset_cache()
    assert rs.bundled() == [], "an unreadable SOURCE.json still offered sets"

    (staged / "SOURCE.json").write_bytes(good)
    assert len(rs.bundled()) == 11, (
        "the failed read was cached, so repairing SOURCE.json changed nothing")
    rs.reset_cache()
