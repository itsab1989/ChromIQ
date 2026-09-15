"""ChromIQ has two Install buttons and they disagreed about the name.

Measured on screen, same window, same run, same tick: with "Name the installed
copy after the description" ticked and the description
``RR ColorJet Canon Pro-1100 v5``, Build ICC profile's Install wrote
``RR ColorJet Canon Pro-1100 v5.icc`` and Check and Refine's "Install Profile
Anyway" wrote ``Pro-1100-ColorJet3.icc`` — because the second one was its own
``shutil.copy2`` under its own name rule and never read the setting at all.

Both now go through `workflow.profile_builder.install_profile_file`, and both
get the name from `installed_profile_name`.

The deliberate half of the rule is kept and guarded here too: **the project's
own file always keeps its stem, only the installed COPY is named after the
description** (Knut). Forcing the file stem to follow the description is a
different and much riskier change, and is NOT what this does.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                       # noqa: E402
from PyQt6.QtWidgets import QApplication                 # noqa: E402

from workflow import profile_builder as PB               # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _profile_tab(tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return TabProfile(ArgyllRunner(s), s), s


class _Settings(dict):
    """Just enough of AppSettings for the name decision."""

    def get(self, key, default=None):          # noqa: A003
        return dict.get(self, key, default)


@pytest.fixture
def installed(tmp_path, monkeypatch):
    d = tmp_path / "ColorSync"
    monkeypatch.setattr(PB, "_profile_dir", lambda: d)
    return d


def _icc(tmp_path: Path, name: str = "Pro-1100-ColorJet3.icc") -> Path:
    p = tmp_path / name
    p.write_bytes(b"pretend this is a profile")
    return p


# ---- the two buttons, one answer ------------------------------------------

DESC = "RR ColorJet Canon Pro-1100 v5"


def test_both_install_buttons_write_the_same_name(installed, tmp_path):
    """The fault, in one assertion: the same profile, the same tick and the
    same description must install under ONE name whichever button is pressed."""
    icc = _icc(tmp_path)
    on = _Settings({"install_named_by_description": True})

    # Build ICC profile: the description comes off the tab's field.
    build_dest = PB.install_profile_file(
        icc, PB.installed_profile_name(DESC, on))

    # Check and Refine: the description comes out of the profile's own tag,
    # and the run stem is only the FALLBACK.
    refine_dest = PB.install_profile_file(
        icc, PB.installed_profile_name(DESC, on),
        fallback_stem="Pro-1100-ColorJet3")

    assert build_dest.name == refine_dest.name == f"{DESC}.icc"
    assert icc.name == "Pro-1100-ColorJet3.icc", "the project's file was renamed"


def test_with_the_tick_off_both_keep_their_own_rule(installed, tmp_path):
    """Unticked, Check and Refine still names the copy after the project
    rather than after a role file like merged.icc, and the Build tab still
    keeps the source name. That was deliberate and is not what broke."""
    off = _Settings({"install_named_by_description": False})
    assert PB.installed_profile_name(DESC, off) is None

    plain = PB.install_profile_file(_icc(tmp_path, "Demo.icc"), None)
    assert plain.name == "Demo.icc"

    merged = PB.install_profile_file(_icc(tmp_path, "merged.icc"), None,
                                     fallback_stem="Demo-Switching")
    assert merged.name == "Demo-Switching.icc", (
        "a system profile folder full of files called merged names nothing")


def test_an_empty_description_falls_back_rather_than_installing_nothing(
        installed, tmp_path):
    on = _Settings({"install_named_by_description": True})
    assert PB.installed_profile_name("   ", on) is None
    dest = PB.install_profile_file(_icc(tmp_path, "merged.icc"),
                                   PB.installed_profile_name("  ", on),
                                   fallback_stem="Demo")
    assert dest.name == "Demo.icc"


def test_the_source_profile_is_never_touched(installed, tmp_path):
    icc = _icc(tmp_path, "keepme.icc")
    before = icc.read_bytes()
    on = _Settings({"install_named_by_description": True})
    PB.install_profile_file(icc, PB.installed_profile_name(DESC, on))
    assert icc.exists() and icc.name == "keepme.icc"
    assert icc.read_bytes() == before


# ---- neither tab copies a profile into the system folder by hand ----------

@pytest.mark.parametrize("module,func", [
    ("ui.tabs.tab_check_refine", None),
])
def test_check_and_refine_does_not_install_behind_the_doors_back(module, func):
    """The fault was a second `shutil.copy2` into the profile folder with its
    own naming rule. There must not be one again."""
    import importlib
    src = inspect.getsource(importlib.import_module(module))
    # The word may appear in a comment explaining the history; what must not
    # come back is a copy paired with the system profile directory.
    assert "install_profile_file(" in src, (
        "Check and Refine no longer installs through the one door")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "_profile_dir" not in code, (
        "Check and Refine reaches for the system profile folder itself again; "
        "that is how the two Install buttons drifted apart")


def test_the_build_tab_really_goes_through_the_shared_sanitiser(qapp, tmp_path):
    """DRIVEN, not read.

    A source check is not enough here: the Build tab can keep the helper's name
    in its text and still not behave like it. "CON" is the proof, because the
    tab's own old regex kept it (Windows cannot create "CON.icc") and only the
    shared sanitiser repairs it.
    """
    tab, s = _profile_tab(tmp_path)
    tab._install_name_cb.setChecked(True)
    tab._desc_edit.setText("CON")
    assert tab._install_name() == "CON_", (
        "the Build tab sanitises the installed name on its own again")
    tab._desc_edit.setText("Canon Pro-1100 " * 40)
    assert len(tab._install_name()) <= PB.MAX_INSTALL_STEM


# ---- the sanitiser, including what Windows refuses ------------------------

def test_the_old_behaviour_is_unchanged():
    """The characters Windows forbids still become underscores, exactly as
    before, and a name that was fine stays byte for byte the same."""
    assert PB.sanitise_install_stem('Epson P900 / Baryta "matt" 2026') == \
        "Epson P900 _ Baryta _matt_ 2026"
    assert PB.sanitise_install_stem(DESC) == DESC
    assert PB.sanitise_install_stem("   ") is None
    assert PB.sanitise_install_stem("") is None
    assert PB.sanitise_install_stem("...") is None


@pytest.mark.parametrize("reserved", ["CON", "nul", "Com1", "LPT9", "AUX",
                                      "prn"])
def test_a_windows_device_name_is_repaired_not_kept(reserved):
    """ChromIQ ships on Windows, where "CON.icc" cannot be created at all.
    The old sanitiser kept every one of these."""
    out = PB.sanitise_install_stem(reserved)
    assert out is not None
    assert out.upper() not in PB._WINDOWS_RESERVED_STEMS, (
        f"{reserved!r} would install as a file Windows refuses to create")
    assert out.lower().startswith(reserved.lower()), (
        "the repair should still show what the user typed")


def test_a_reserved_name_with_more_words_is_left_alone():
    """Only the whole stem is reserved; "CONTACT" and "Console" are fine."""
    assert PB.sanitise_install_stem("CONTACT") == "CONTACT"
    assert PB.sanitise_install_stem("Console profile") == "Console profile"


def test_an_endless_description_is_cut_to_something_installable():
    long = "Canon Pro-1100 " * 40                       # 600 characters
    out = PB.sanitise_install_stem(long)
    assert out is not None
    assert len(out) <= PB.MAX_INSTALL_STEM
    assert not out.endswith((" ", ".")), (
        "Windows refuses a file name ending in a space or a dot, and the cut "
        "can land on one")


def test_a_control_character_never_reaches_the_file_name():
    """Invisible in the field, illegal in a Windows file name."""
    out = PB.sanitise_install_stem("Canon\x07Pro\x1f1100")
    assert out == "CanonPro1100"


def test_an_accented_description_keeps_its_accents():
    """ADVERSARY ROUND 3. ChromIQ goes out of its way to keep accents in the
    profile's own name (`core/icc_text.py` repairs the Unicode field precisely
    so "Müller-Prüfdruck" does not read back as "M?ller-Pr?fdruck"). The file
    name must not undo that: none of these characters is illegal anywhere."""
    assert PB.sanitise_install_stem("Müller-Prüfdruck") == "Müller-Prüfdruck"
    assert PB.sanitise_install_stem("Épreuve — été") == "Épreuve — été"
    assert PB.sanitise_install_stem("プリンター 2026") == "プリンター 2026"


def test_a_description_of_nothing_but_illegal_characters_still_yields_a_name():
    """It must not return something unusable, and it must not return a name
    that is only spaces or dots."""
    out = PB.sanitise_install_stem('///:::***')
    assert out and out.strip(" .") == out


def test_the_length_cap_counts_the_name_the_user_would_see():
    """The cap is on the stem; ".icc" is added afterwards, so the file name is
    four characters longer and must still be comfortable."""
    out = PB.sanitise_install_stem("x" * 500)
    assert len(f"{out}.icc") <= PB.MAX_INSTALL_STEM + 4


def test_the_name_decision_survives_a_settings_store_that_raises():
    class Broken:
        def get(self, *a, **k):
            raise RuntimeError("no settings today")
    assert PB.installed_profile_name(DESC, Broken()) is None
