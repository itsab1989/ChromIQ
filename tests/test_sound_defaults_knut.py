"""#148 (Knut, 2026-08-14): three sounds get the defaults he chose.

After using the pack through a real measurement he asked for:

    *"Patch reading looks off" to be set to "bump" as default*
    *"Measurement finished" to be set to "Chime-long" as default*
    *"Profile build finished" to be set to "applause" as default*

Changing a default is never only a dictionary edit here. Preferences → Save
writes **every** key, so anyone who has ever opened that dialog carries a stored
copy of the old default — and without a migration they would keep the old sound
for ever and never know a better one had been chosen. Schema 20 drops those
echoes; a sound the user actually picked is left alone.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.sound as snd                                    # noqa: E402


def test_knuts_three_defaults():
    assert snd.DEFAULT_CHOICE[snd.PATCH_OUT_OF_TOL] == "bump"
    assert snd.DEFAULT_CHOICE[snd.MEASUREMENT_FINISHED] == "chime-long"
    assert snd.DEFAULT_CHOICE[snd.PROFILE_BUILT] == "applause"


def test_the_other_defaults_are_untouched():
    """He named three. The rest must not drift along with them."""
    assert snd.DEFAULT_CHOICE[snd.PATCH_OK] == "tick"
    assert snd.DEFAULT_CHOICE[snd.STRIP_OK] == "bell"
    assert snd.DEFAULT_CHOICE[snd.STRIP_FAIL] == "failure"
    assert snd.DEFAULT_CHOICE[snd.INSTRUMENT_ERROR] == "error"
    assert snd.DEFAULT_CHOICE[snd.SLOW_DOWN] == "slowdown"


def test_every_default_is_a_sound_that_actually_ships():
    """A default naming a file that is not in the pack would resolve to OFF and
    the event would be silent — the failure mode this whole issue is about."""
    for event, stem in snd.DEFAULT_CHOICE.items():
        folder = snd.bundled_sounds_root() / snd.SUBFOLDER_OF[event]
        assert (folder / f"{stem}.wav").is_file(), (event, stem)


def test_the_superseded_defaults_are_recorded():
    assert snd.SUPERSEDED_DEFAULT_CHOICE == {
        snd.PATCH_OUT_OF_TOL: "thump",
        snd.MEASUREMENT_FINISHED: "drumroll",
        snd.PROFILE_BUILT: "trumpet",
    }


def test_no_event_supersedes_its_own_new_default():
    """A stale value equal to the NEW default would be dropped for nothing."""
    for event, old in snd.SUPERSEDED_DEFAULT_CHOICE.items():
        assert old != snd.DEFAULT_CHOICE[event], event


def _settings(tmp_path, stored: dict):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in stored.items():
        s._qs.setValue(k, v)
    return s


def test_a_stored_echo_of_the_old_default_is_dropped(tmp_path):
    s = _settings(tmp_path, {
        "sound_choice_patch_out_of_tol": "thump",
        "sound_choice_measurement_finished": "drumroll",
        "sound_choice_profile_built": "trumpet",
    })
    s.migrate()
    assert snd.choice_for(s, snd.PATCH_OUT_OF_TOL) == "bump"
    assert snd.choice_for(s, snd.MEASUREMENT_FINISHED) == "chime-long"
    assert snd.choice_for(s, snd.PROFILE_BUILT) == "applause"


def test_a_sound_the_user_chose_survives(tmp_path):
    """The whole point of the migration is that it only clears echoes."""
    s = _settings(tmp_path, {
        "sound_choice_patch_out_of_tol": "buzz",
        "sound_choice_measurement_finished": "fanfare",
        "sound_choice_profile_built": "OFF",
    })
    s.migrate()
    assert snd.choice_for(s, snd.PATCH_OUT_OF_TOL) == "buzz"
    assert snd.choice_for(s, snd.MEASUREMENT_FINISHED) == "fanfare"
    assert snd.choice_for(s, snd.PROFILE_BUILT) == snd.OFF


def test_a_fresh_install_needs_no_migration(tmp_path):
    s = _settings(tmp_path, {})
    s.migrate()
    assert snd.choice_for(s, snd.PROFILE_BUILT) == "applause"


def test_migrating_twice_is_harmless(tmp_path):
    s = _settings(tmp_path, {"sound_choice_profile_built": "trumpet"})
    s.migrate()
    s.migrate()
    assert snd.choice_for(s, snd.PROFILE_BUILT) == "applause"


def test_the_defaults_are_not_written_down_twice():
    """AppSettings used to carry its own copy of every sound default, and that
    copy won — so changing core.sound.DEFAULT_CHOICE did nothing at all. It cost
    a real fix its effect before anyone noticed. One source of truth now, and
    this fails if a second one is reintroduced."""
    import inspect
    from core import settings as st
    src = inspect.getsource(st)
    # The dict literal must not name the keys directly any more.
    assert '"sound_choice_profile_built":' not in src
    for event in snd.ALL_EVENTS:
        assert st.DEFAULTS[f"sound_choice_{event}"] == snd.DEFAULT_CHOICE[event]
