"""EVERY INSTRUMENT BEHAVES LIKE THE OTHERS ON CREATE CHART, OR SAYS WHY NOT.

The owner, 2026-11-13, after three reviews found by hand that a new
instrument behaved differently from the others (a Preferences style reaching
Manual but not Guided, risky values following a person from one instrument
to the next, options greyed for one instrument only): the app should feel
the same whatever instrument is chosen, and a person adding an instrument
should be able to check that themselves.

`scripts/instrument_parity.py` observes, for EVERY instrument the app lists
(Beta instruments switched on), in Guided, in Manual and in Manual with the
layout engine off:

  a. every Create Chart control: shown, enabled or greyed, its default, and a
     visible reason when it is greyed for that instrument only;
  b. every option kept by Save as Defaults (and the next start), the preset
     bar, a named preset, the target's own stored settings, and a new target
     opened after Save as Defaults; and every option the reference's panel
     keeps that this instrument's does not ("lacks_option");
  c. instrument A -> B -> A gives A back what it had, and B takes over only
     the values the allow-list calls shared;
  d. every run type can be chosen and built;
  e. Preferences' label style treated as it is for the reference.

Each is compared with the reference instrument, the i1Pro strip reader. A
difference must be in `tests/data/instrument_parity_allowlist.json`, under
"intended" with its reason or under "known_to_review" (seen, not yet judged).
An entry that no longer matches what the app does fails too, so the list
cannot go stale. The failure message prints the rows ready to paste; or run

    QT_QPA_PLATFORM=offscreen python scripts/instrument_parity.py

to see them without the suite. Nothing here needs ArgyllCMS, a printer or a
window; the settings are throwaway files.
"""
from __future__ import annotations

import json
import os
from dataclasses import fields

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts import instrument_parity as ip  # noqa: E402

EM_DASH = chr(0x2014)


@pytest.fixture(scope="module")
def observed(qapp, tmp_path_factory):
    with ip.betas_on():
        obs = ip.observe(tmp_path_factory.mktemp("parity"))
    obs["rows"] = ip.differences(obs)
    return obs


@pytest.fixture(scope="module")
def allow():
    return ip.load_allowlist()


# ---- the tables themselves (no Qt) -----------------------------------------

def test_every_recipe_field_has_a_candidate():
    """A layout option added later is walked too, or says why not."""
    from workflow.layout_engine.presets import LayoutRecipe
    names = {f.name for f in fields(LayoutRecipe)}
    assert not set(ip.CANDIDATES) & set(ip.NOT_A_CANDIDATE)
    missing = names - set(ip.CANDIDATES) - set(ip.NOT_A_CANDIDATE)
    assert not missing, (
        "a LayoutRecipe field with no candidate value in "
        f"scripts/instrument_parity.py CANDIDATES: {sorted(missing)}")
    assert not (set(ip.CANDIDATES) | set(ip.NOT_A_CANDIDATE)) - names


def test_the_allow_list_is_well_formed(allow):
    assert allow["reference"] == ip.REFERENCE
    keys = set()
    for status in ("intended", "known_to_review"):
        for e in allow[status]:
            assert e["check"] in ip.CHECKS, e
            assert e.get("mode", "") in ("", *ip.MODES), e
            assert e["instrument"], e
            assert "expected" in e, e
            reason = str(e.get("reason", "")).strip()
            assert reason and "WRITE ONE" not in reason, (
                f"an entry with no reason: {e}")
            assert EM_DASH not in reason, f"no em dash in a reason: {e}"
            inst = e["instrument"]
            items = e["item"] if isinstance(e["item"], list) else [e["item"]]
            for c in (inst if isinstance(inst, list) else [inst]):
                for item in items:
                    k = (e["check"], e.get("mode", ""), c, item, e["aspect"])
                    assert k not in keys, f"listed twice: {k}"
                    keys.add(k)
    shared = allow.get("shared") or {}
    assert shared.get("fields") and shared.get("reason"), \
        "the shared list names its fields and says why"


# ---- discovery --------------------------------------------------------------

def test_every_beta_instrument_is_switched_on():
    names = [m.__name__ for m in ip.beta_support_modules()]
    assert "workflow.i1io.support" in names
    assert "workflow.fd9.support" in names


def test_the_instruments_are_discovered(observed):
    codes = observed["instruments"]
    assert codes[0] == ip.REFERENCE
    # every list the app offers instruments in is part of the union
    for name, members in observed["lists"].items():
        assert set(members) <= set(codes), name
    # and every instrument is looked at in every mode that offers it
    for code in observed["lists"]["guided"]:
        assert ("guided", code) in observed["controls"], code
    for code in observed["lists"]["layout_panel"]:
        assert ("manual", code) in observed["controls"], code


def test_the_walks_really_walked(observed):
    """A walk that silently saw nothing would pass everything."""
    ref = observed["controls"][("manual", ip.REFERENCE)]
    assert len(ref) > 100
    assert len(observed["controls"][("guided", ip.REFERENCE)]) > 5
    opts = observed["kept"][("manual", ip.REFERENCE)]["_options"]
    assert len(opts) > 40, opts
    assert observed["switching"]
    assert all(observed["run_types"][("guided", ip.REFERENCE)].values())
    # a REAL calibration target, in every mode the reference is offered in
    for mode in ip.MODES:
        got = observed["run_types"][(mode, ip.REFERENCE)]["calibration"]
        assert "builds a calibration chart" in got, (mode, got)
    # the fifth kept path really opened a new target
    assert "new_target_after_defaults" in \
        observed["kept"][("manual", ip.REFERENCE)]


def test_no_two_entries_claim_the_same_row(observed, allow):
    """A "*" entry and an explicit one for the same row (or two explicit
    ones) would overwrite each other silently."""
    assert ip.collisions(allow, observed["instruments"]) == []


def test_an_entry_for_an_instrument_no_longer_listed_fails(allow):
    """Rot: an entry naming a code the app no longer lists is stale."""
    fake = {"intended": [{"check": "control", "mode": "guided",
                          "instrument": "GONE", "item": "_lb_check",
                          "aspect": "present", "expected": False,
                          "reason": "x"}],
            "known_to_review": [], "shared": allow.get("shared")}
    _un, stale, _mis = ip.compare([], fake, [ip.REFERENCE])
    assert [s["instrument"] for s in stale] == ["GONE"]


# ---- the comparison ---------------------------------------------------------

def _explain(rows, title):
    return (f"{title}\n(paste into tests/data/instrument_parity_allowlist.json "
            "under 'intended' with one plain sentence, or under "
            "'known_to_review' if nobody has judged it yet)\n"
            + ip.as_entries(rows))


@pytest.mark.parametrize("check", ip.CHECKS)
def test_every_difference_is_on_the_allow_list(observed, allow, check):
    rows = [r for r in observed["rows"] if r["check"] == check]
    unexplained, _stale, mismatched = ip.compare(rows, allow,
                                                 observed["instruments"])
    assert not unexplained, _explain(
        unexplained, f"{len(unexplained)} '{check}' difference(s) from the "
        f"reference ({ip.REFERENCE}) that the allow-list does not explain")
    assert not mismatched, (
        f"the allow-list expects another state for these '{check}' rows:\n"
        + json.dumps(mismatched, indent=1, ensure_ascii=False))


@pytest.mark.parametrize("check", ip.CHECKS)
def test_no_allow_list_entry_is_stale(observed, allow, check):
    rows = [r for r in observed["rows"] if r["check"] == check]
    only = {"intended": [e for e in allow["intended"] if e["check"] == check],
            "known_to_review": [e for e in allow["known_to_review"]
                                if e["check"] == check],
            "shared": allow.get("shared")}
    _un, stale, _mis = ip.compare(rows, only, observed["instruments"])
    assert not stale, (
        f"allow-list '{check}' entries the app no longer shows (remove them, "
        "or the difference came back in another form):\n"
        + json.dumps(stale, indent=1, ensure_ascii=False))


def test_every_shared_field_really_is_shared(observed, allow):
    """The shared list cannot keep a field nothing carries any more."""
    carried = set()
    for (_a, _b), r in observed["switching"].items():
        carried |= set(r["inherited"])
    unused = sorted(ip.shared_fields(allow) - carried)
    assert not unused, f"shared fields no instrument carries: {unused}"
