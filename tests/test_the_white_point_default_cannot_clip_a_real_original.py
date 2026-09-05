"""The scanner white-point default is the one that cannot clip a real original,
and moving it took everybody's remembered setting with it — announced, once.

**Basti approved the change on 2026-09-05**, and he ruled the migration too:
*"our user base is not very big at the moment so i want the better default"*.
So there is no per-target escape hatch pinning old settings to the old value —
a stored "" adopts the new default. This file is what stops that ruling being
undone by accident, and what stops it firing twice.

WHY IT MOVED — measured independently on 2026-09-05, on the 864-patch IT8 scan
extracted from Knut's own profile (`beta 9/knut-whitepoint/`), `colprof -ax -qh`,
with the working files kept in `beta 9/wp-default/measure/`:

* the old default put the CHART'S OWN WHITE BOARD at PCS white, and that board
  is only **84.286 %** reflectance (`colprof` says so itself before it fits
  anything: `Approximate White point XYZ = 0.82462 0.84286 0.70454`). So every
  reflective original brighter than a piece of IT8 board exceeded PCS white:
  measured media-relative, 84.1 % arrived at **L\\* 101.12**, 89.3 % at 103.47,
  95.2 % at 106.08 and a perfect diffuse reflector at 108.06 — and all four
  came out of an sRGB conversion as exactly **255 255 255**. Four physically
  different whites, one value, irreversibly.
* `-u -R` puts PCS white at a perfect diffuse reflector instead. The same four
  land at L\\* 93.50 / 95.69 / 98.12 / 99.98. Nothing physically possible clips.
* it costs no accuracy: `profcheck -k -Ia` gives **0.336709** average ΔE00
  against the old default's **0.336727** (max 3.657 against 3.636).
* and it stays NEUTRAL, which is the whole reason it and not `-ua` is the
  default. The board reads a\\* −0.83 / b\\* −0.50 through `-u -R` against the
  old default's −0.89 / −0.53 — the same chromaticity. `-ua` is more accurate
  still (0.332197) but reports the chart's real cast, a\\* +1.49 on the board
  rising to +2.50 on a perfect diffuser: right for an instrument, wrong as a
  global default for pictures.

And one fact the change rests on, so it is pinned here too: `-u 1 -R` (which is
what was measured, and what Knut built) is `-u -R`. `colprof.c:494` sets
`autowpsc = 1` before it reads the number and `xfit.c:2753` defaults the scale
to 1.0. Rebuilt both at `-ax -qh`: identical `A2B0`, `B2A0`, `wtpt` and `bkpt`
— every colour tag the same, only `desc` differing, because that is the file
name. So the default carries no scale number and needs none.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication          # noqa: E402

from ui.dialogs import scanner_colprof as sc      # noqa: E402
from workflow.profile_builder import ProfileBuilder, ProfileParams  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def _cmd(adv, ptype="s", quality="m"):
    p = sc.make_profile_params(Path("x.ti3"), "S",
                               {"ptype": ptype, "quality": quality}, adv)
    return ProfileBuilder(None)._build_args(p)


# ---------------------------------------------------------------- the default
def test_the_default_is_the_one_that_cannot_clip():
    """One constant, and it names an entry that exists."""
    assert sc.WP_MODE_DEFAULT == "uR"
    assert sc.WP_MODE_DEFAULT in dict(sc.WP_MODE_CHOICES)


def test_a_fresh_scanner_build_asks_colprof_for_u_and_R():
    """The point of the whole change, at the only place it can be observed:
    the command. Nobody has touched anything, and colprof is asked for -u -R."""
    args = _cmd(sc.effective_adv_vals({}, False, None))
    assert "-u" in args and "-R" in args
    # …and -u carries no number: `-u 1` IS `-u`, so a scale would be noise in
    # the command the window shows the user.
    assert args[args.index("-u") + 1] == "-R"


def test_the_R_switch_and_the_default_do_not_stack_into_two_flags():
    """Both sources of -R at once. colprof would take it twice; the command
    the window PRINTS is the command it runs, and "-u -R -R" is not one."""
    adv = sc.effective_adv_vals({}, False, None)
    adv["-R"] = True
    assert _cmd(adv).count("-R") == 1


def test_the_old_behaviour_is_still_one_entry_in_the_same_dropdown():
    """Basti's migration is defensible only because nothing was taken away.
    "Map chart white to white" is still there and still means no flag at all."""
    labels = dict(sc.WP_MODE_CHOICES)
    assert "" in labels and labels[""].startswith("Map chart white to white")
    args = _cmd(sc.effective_adv_vals({"wp_mode": ""}, False, None))
    assert "-u" not in args and "-R" not in args


def test_a_printer_build_is_untouched_by_any_of_this():
    """The printer-mode default was NOT part of this change, and the -u family
    is not applicable to an output profile at all."""
    v = sc.effective_adv_vals({"wp_mode": sc.WP_MODE_DEFAULT}, True, None)
    assert "wp_mode" not in v and "wp_scale" not in v
    assert "-u" not in _cmd(v, ptype="l")
    # …and the engine refuses it with colprof's own words if it ever arrived.
    from workflow.engine_builder import settings_from_params
    with pytest.raises(ValueError, match="output device"):
        settings_from_params(ProfileParams(ti3_path=Path("x.ti3"),
                                           wp_mode=sc.WP_MODE_DEFAULT))


def test_the_dataclass_default_did_not_move_with_it():
    """`ProfileParams.wp_mode` stays "" — every caller that is not this window
    builds an OUTPUT profile, and giving them -u would be a different change
    nobody approved."""
    assert ProfileParams(ti3_path=Path("x.ti3")).wp_mode == ""
    assert "-u" not in ProfileBuilder(None)._build_args(
        ProfileParams(ti3_path=Path("x.ti3")))


# ------------------------------------------------------------------ the window
def test_the_window_marks_the_default_entry_and_only_that_one(_app):
    """The label and the constant cannot drift: the marker is applied from
    WP_MODE_DEFAULT, so exactly one entry says "(default)" and it is that one."""
    dlg = sc.ScannerAdvancedDialog({}, None, printer=False)
    try:
        combo = dlg._wp_mode
        marked = [i for i in range(combo.count()) if "(default)" in combo.itemText(i)]
        assert len(marked) == 1, [combo.itemText(i) for i in range(combo.count())]
        assert combo.itemData(marked[0]) == sc.WP_MODE_DEFAULT
        # and a window nobody has configured OPENS on it
        assert combo.currentData() == sc.WP_MODE_DEFAULT
    finally:
        dlg.deleteLater()


def test_restore_defaults_goes_to_the_new_default_and_leaves_R_alone(_app):
    dlg = sc.ScannerAdvancedDialog({"wp_mode": "ua", "-R": True}, None, printer=False)
    try:
        dlg.restore_defaults()
        out = dlg.values()
        assert out["wp_mode"] == sc.WP_MODE_DEFAULT
        assert out["-R"] is False        # "uR" carries its own -R
    finally:
        dlg.deleteLater()


def test_a_missing_key_takes_the_default_and_a_stored_one_does_not(_app):
    """An ABSENT wp_mode and a stored "" are different things now, because ""
    is an entry a user can choose. Read them the same way and a deliberate
    "Map chart white to white" is silently re-defaulted on every open."""
    fresh = sc.ScannerAdvancedDialog({}, None, printer=False)
    chosen = sc.ScannerAdvancedDialog({"wp_mode": ""}, None, printer=False)
    try:
        assert fresh._wp_mode.currentData() == sc.WP_MODE_DEFAULT
        assert chosen._wp_mode.currentData() == ""
    finally:
        fresh.deleteLater()
        chosen.deleteLater()


def test_what_the_window_writes_carries_the_schema_stamp(_app):
    dlg = sc.ScannerAdvancedDialog({}, None, printer=False)
    try:
        assert dlg.values()[sc.ADV_SCHEMA_KEY] == sc.ADV_SCHEMA_VERSION
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------- the migration
def _stored(wp, stamped=False):
    adv = {"-r": 0.5}
    if wp is not None:
        adv["wp_mode"] = wp
    if stamped:
        adv[sc.ADV_SCHEMA_KEY] = sc.ADV_SCHEMA_VERSION
    return {"chart": {"main": {"ptype": "s"}, "adv": adv}}


def test_a_setting_saved_before_the_change_adopts_the_new_default():
    """Basti's ruling, in one assertion."""
    out, migrated = sc.migrate_stored_configs(_stored(""))
    assert migrated == ["chart"]
    assert out["chart"]["adv"]["wp_mode"] == sc.WP_MODE_DEFAULT
    assert out["chart"]["adv"]["-r"] == 0.5          # nothing else is touched
    assert out["chart"]["main"] == {"ptype": "s"}


def test_the_migration_happens_once_and_not_on_every_open():
    once, first = sc.migrate_stored_configs(_stored(""))
    twice, second = sc.migrate_stored_configs(once)
    assert first == ["chart"] and second == []
    assert twice["chart"]["adv"]["wp_mode"] == sc.WP_MODE_DEFAULT


def test_a_choice_made_after_the_change_is_never_re_defaulted():
    """The stamp is what separates "" written because it was the default from
    "" chosen on purpose. Without it the migration would fire for ever."""
    out, migrated = sc.migrate_stored_configs(_stored("", stamped=True))
    assert migrated == []
    assert out["chart"]["adv"]["wp_mode"] == ""


@pytest.mark.parametrize("chosen", ["u", "ua", "uc", "scale"])
def test_a_setting_somebody_actually_chose_is_left_where_it_is(chosen):
    """He ruled that a stored "" adopts the new default — not that a setting
    somebody went looking for is overruled."""
    out, migrated = sc.migrate_stored_configs(_stored(chosen))
    assert migrated == []
    assert out["chart"]["adv"]["wp_mode"] == chosen
    assert out["chart"]["adv"][sc.ADV_SCHEMA_KEY] == sc.ADV_SCHEMA_VERSION


def test_a_printer_bucket_never_gains_an_input_profile_setting():
    """A printer configuration has no wp_mode at all, and must not be given
    one: colprof refuses the -u family on output data."""
    out, migrated = sc.migrate_stored_configs(
        {"printer": {"main": {}, "adv": {"-r": 0.5}}})
    assert migrated == []
    assert "wp_mode" not in out["printer"]["adv"]


def test_a_bucket_nobody_ever_saved_is_not_reported_as_migrated():
    """It has no stored setting to move, so telling its owner that theirs was
    moved would be a message about nothing."""
    for empty in ({}, {"chart": {}}, {"chart": {"main": {}, "adv": {}}}):
        out, migrated = sc.migrate_stored_configs(empty)
        assert migrated == [], empty


def test_rubbish_in_the_store_does_not_take_the_window_down():
    """A settings file can hold anything; this runs before the window is built."""
    for junk in (None, [], "nonsense", {"chart": 7}, {"chart": {"adv": "x"}},
                 {"chart": {"adv": {"wp_mode": "", sc.ADV_SCHEMA_KEY: "?"}}}):
        out, migrated = sc.migrate_stored_configs(junk)
        assert isinstance(out, dict) and isinstance(migrated, list)


# ------------------------------------------------------- it is not done silently
def test_the_change_has_a_message_and_it_is_not_approved_yet():
    """CLAUDE.md principle 10: migrate in place, ANNOUNCE it. The wording is
    §M-PROPOSED and is Basti's to approve, so it is `approved=False` and it
    speaks through the log until he has seen it."""
    from workflow import measurement_messages as M
    msg = M.CATALOGUE["M-SCAN-WP-DEFAULT"]
    assert msg.approved is False
    assert "M-SCAN-WP-DEFAULT" in M.PROPOSED
    title, body = msg.render()
    # it must say the three things a person needs: what changed, that their
    # existing work is untouched, and how to get the old behaviour back
    assert "Scale white to a perfect white surface" in body
    assert "untouched" in body
    assert "Map chart white to white" in body
    assert "{" not in title and "{" not in body      # nothing left unfilled


def test_the_window_says_it_once_and_only_when_something_moved(_app, tmp_path):
    """Not on a first-ever run, not twice, and not to somebody whose setting
    did not move."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    class _Settings:
        def __init__(self, store):
            from core.settings import DEFAULTS
            self._s = {**DEFAULTS, **store}
            self._s["custom_output_path"] = str(tmp_path)

        def get(self, k, d=None):
            return self._s.get(k, d)

        def set(self, k, v):
            self._s[k] = v

    def _open(store):
        s = _Settings(store)
        d = ScannerProfileDialog(object(), s)
        try:
            d._announce_wp_default_migration()
            said = "white point setting" in d._log.toPlainText().lower()
            # a second call must add nothing
            d._announce_wp_default_migration()
            twice = d._log.toPlainText().lower().count("white point setting")
            return said, twice, s.get("scanner_colprof_configs")
        finally:
            d.deleteLater()

    # nobody has ever saved anything → nothing to migrate, nothing to say
    said, _, _ = _open({})
    assert said is False

    # a configuration written before the change → said once, and written back
    said, twice, stored = _open({"scanner_colprof_configs": _stored("")})
    assert said is True and twice == 1
    assert stored["chart"]["adv"]["wp_mode"] == sc.WP_MODE_DEFAULT

    # …and opening again on the migrated store says nothing
    said, _, _ = _open({"scanner_colprof_configs": stored})
    assert said is False


def test_showing_the_window_is_what_says_it(_app, tmp_path):
    """The mutation that survived the first pass: every assertion above called
    `_announce_wp_default_migration` itself, so deleting the ONE line that
    calls it in `showEvent` left the whole file green over a migration nobody
    was ever told about. This drives the real window instead."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    class _Settings:
        def __init__(self, store):
            from core.settings import DEFAULTS
            self._s = {**DEFAULTS, **store}
            self._s["custom_output_path"] = str(tmp_path)

        def get(self, k, d=None):
            return self._s.get(k, d)

        def set(self, k, v):
            self._s[k] = v

    d = ScannerProfileDialog(object(), _Settings(
        {"scanner_colprof_configs": _stored("")}))
    try:
        assert "white point setting" not in d._log.toPlainText().lower(), \
            "said before the window was shown"
        d.show()
        _app.processEvents()
        assert "white point setting" in d._log.toPlainText().lower(), \
            "the window opened on a migrated setting and said nothing"
    finally:
        d.close()
        d.deleteLater()


# --------------------------------------------------------------- the consumers
def test_the_two_consumers_of_a_scanner_profile_still_read_it_as_they_did():
    """Nothing about this change touches how ChromIQ itself USES a scanner
    profile, and both paths are pinned so a later change cannot do it quietly.

    `scanin -c` — printer profiling, where the scanner is the instrument — asks
    Argyll for the forward table with `icAbsoluteColorimetric`, hard-coded in
    `scanin.c`, so it is indifferent to the white point the profile was built
    with. The device-link / conversion path uses media-relative (`-i r`), which
    is the intent this default is chosen for.
    """
    import inspect

    from workflow import cctiff_apply, scanin_runner
    args = cctiff_apply.convert_args(Path("a.icc"), Path("b.icc"),
                                     Path("in.tif"), Path("out.tif"))
    assert args.count("-i") == 2 and set(args[i + 1] for i, a in enumerate(args)
                                         if a == "-i") == {"r"}
    # scanin is handed the profile with -c and nothing about an intent: the
    # intent is Argyll's own, and ChromIQ neither sets nor can set it.
    src = inspect.getsource(scanin_runner)
    assert '"-c"' in src or "'-c'" in src
    for absent in ("-ir", "icRelativeColorimetric"):
        assert absent not in src


# ------------------------------------------------------------------- the help
def test_the_help_calls_the_new_default_the_default_and_the_old_one_not():
    """The window may not contradict itself. Three places say what the default
    is — the combo marker, the white-point help and the profile-type help —
    and all three have to name the same entry."""
    body = sc._TIP_WP
    assert "Scale white to a perfect white surface (-u -R) — the default" in body
    assert "Map chart white to white (default)" not in body
    # the profile-type help sends people to this control; it must not describe
    # a ceiling that the current default has already lifted
    _, ptype = sc.ptype_help(False)
    assert "Scale white to a perfect white surface" in ptype
    assert "which lifts the ceiling" not in ptype


def test_the_help_says_the_R_switch_is_already_in_the_default():
    """Otherwise the obvious reading of the Expert switch is that the default
    is missing something, and people tick it for nothing."""
    assert "ALREADY APPLIED" in sc._TIP_R
    assert "Scale white to a perfect white surface" in sc._TIP_R


def test_the_help_still_says_what_the_default_costs():
    """A default that makes every scan open slightly grey has to say so where
    somebody meets it, or the first reaction is that something is broken."""
    body = sc._TIP_WP
    assert "L* 93" in body
    assert "levels step" in body
