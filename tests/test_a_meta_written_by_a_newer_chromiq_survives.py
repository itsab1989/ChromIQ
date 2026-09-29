"""A field this build has never heard of is not a field to be deleted.

``ProjectManifest``, ``RunMeta`` and ``CalibrationMeta`` each filtered a stored
dict down to their own field names, and each ``save_meta`` then wrote
``asdict(meta)`` back over the file. So anything a NEWER ChromIQ had written was
silently erased by the first ordinary save an older one did — no warning, no
schema signal, nothing to recover from.

MEASURED, 2026-09-22, running both builds' real code: ``SCHEMA_VERSION`` is 3 in
v4.2.7 and 3 in 4.3.0-beta.30 — it did not move across the whole of #182 — so
``schema_too_new`` cannot fire. v4.2.7 doing nothing but
``Run.for_dir(...).load_meta()`` then ``.save_meta(meta)`` erased all seven of
the run's #182 fields: ``compliance_set_id``, ``compliance_set_label``,
``compliance_thresholds`` (32 rows of limits), ``compliance_bound_at``,
``compliance_unlocked``, ``compliance_columns`` and ``report_type``. The run's
frozen copy of its limits — the thing Knut's D20 exists to protect — was gone,
and the run read ``bound=False``. The owner ships a stable build and a beta side
by side over one ``~/ChromIQ`` folder, so opening one project in the older of
the two once was enough.

A build that has already shipped cannot be repaired. This is the class being
stopped, so that from here on an older ChromIQ CARRIES what it cannot read.

MUTATION, proven both ways:

* put ``return cls(**{k: v for k, v in d.items() if k in known})`` back in any
  of the three ``from_dict`` methods and the carrying test for that class goes
  red;
* put ``asdict(meta)`` back in either ``save_meta`` or in ``save_manifest`` and
  the corresponding test goes red.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import (CalibrationMeta,                  # noqa: E402
                               Project, ProjectManifest, RunMeta,
                               UNKNOWN_FIELDS_ATTR, meta_to_json,
                               split_known_fields)

#: What a ChromIQ newer than this one might have written. Three shapes, because
#: a carrier that only survives strings is not a carrier.
FROM_THE_FUTURE = {
    "compliance_evidence_pack": {"id": "e7", "rows": 44},
    "report_signature": "abc123",
    "future_flag": True,
}


#: One field each class really declares, and its value, so the three can be
#: driven by one parametrisation. CalibrationMeta has no ``created_at``.
OWN_FIELD = {"ProjectManifest": ("created_at", "2027-01-01T00:00:00"),
             "RunMeta": ("created_at", "2027-01-01T00:00:00"),
             "CalibrationMeta": ("description", "a calibration")}


@pytest.mark.parametrize("cls", [ProjectManifest, RunMeta, CalibrationMeta])
def test_the_split_keeps_what_the_class_does_not_declare(cls):
    name, value = OWN_FIELD[cls.__name__]
    stored = dict(FROM_THE_FUTURE)
    stored[name] = value
    mine, rest = split_known_fields(cls, stored)
    assert mine == {name: value}, (
        f"{cls.__name__} no longer recognises its own field")
    assert rest == FROM_THE_FUTURE, (
        f"{cls.__name__} dropped a field a newer ChromIQ wrote instead of "
        f"carrying it")


@pytest.mark.parametrize("cls", [ProjectManifest, RunMeta, CalibrationMeta])
def test_a_round_trip_through_the_dataclass_loses_nothing(cls):
    """from_dict → meta_to_json is what load_meta → save_meta really is."""
    name, value = OWN_FIELD[cls.__name__]
    out = meta_to_json(cls.from_dict(dict(FROM_THE_FUTURE, **{name: value})))
    for k, v in FROM_THE_FUTURE.items():
        assert out.get(k) == v, (
            f"{cls.__name__} erased {k!r} on save — every field a newer "
            f"ChromIQ wrote is destroyed by the first ordinary save this one "
            f"does")
    assert out[name] == value


@pytest.mark.parametrize("cls", [ProjectManifest, RunMeta, CalibrationMeta])
def test_the_carrier_itself_never_reaches_disk(cls):
    """It is a mechanism, not a field. A file that grew one would then have a
    key the NEXT build carries as data, for ever."""
    out = meta_to_json(cls.from_dict(dict(FROM_THE_FUTURE)))
    assert UNKNOWN_FIELDS_ATTR not in out, (
        f"{cls.__name__} wrote its carrier into the file")


@pytest.mark.parametrize("cls", [ProjectManifest, RunMeta, CalibrationMeta])
def test_this_builds_own_value_always_wins(cls):
    """A carried key can never shadow one the class declares — and if the two
    ever collided, the dataclass is the truth."""
    name, value = OWN_FIELD[cls.__name__]
    meta = cls.from_dict({name: value})
    getattr(meta, UNKNOWN_FIELDS_ATTR)[name] = "a value from the carried set"
    assert meta_to_json(meta)[name] == value


def test_a_runs_meta_json_survives_the_ordinary_read_and_write(tmp_path):
    """The real file, the real `load_meta`, the real `save_meta`."""
    from core.file_manager import Run
    rd = tmp_path / "P" / "runs" / "run1"
    rd.mkdir(parents=True)
    (rd / "meta.json").write_text(
        json.dumps(dict(FROM_THE_FUTURE, run_id="run1"), indent=2),
        encoding="utf-8")

    run = Run.for_dir(rd)
    meta = run.load_meta()
    assert meta.run_id == "run1", "the fields this build DOES know must load"
    run.save_meta(meta)

    back = json.loads((rd / "meta.json").read_text(encoding="utf-8"))
    missing = sorted(k for k in FROM_THE_FUTURE if k not in back)
    assert not missing, (
        f"{missing} were erased from runs/run1/meta.json by a read and a save. "
        f"That is how v4.2.7 destroyed every #182 field of a beta-30 run: the "
        f"schema number never moved, so nothing even warned")
    assert back["run_id"] == "run1"
    assert UNKNOWN_FIELDS_ATTR not in back


def test_a_project_json_survives_the_ordinary_read_and_write(tmp_path):
    root = tmp_path / "P"
    (root / "runs" / "run1").mkdir(parents=True)
    (root / "project.json").write_text(json.dumps({
        "schema_version": 3, "target_name": "P", "current_run": "run1",
        "runs": ["run1"], **FROM_THE_FUTURE}, indent=2), encoding="utf-8")

    Project.load(root).save_manifest()

    back = json.loads((root / "project.json").read_text(encoding="utf-8"))
    missing = sorted(k for k in FROM_THE_FUTURE if k not in back)
    assert not missing, (
        f"{missing} were erased from project.json by a read and a save")
    assert back["target_name"] == "P"
    assert UNKNOWN_FIELDS_ATTR not in back


def test_the_three_classes_all_go_through_the_one_rule():
    """Guards the seam: a fourth manifest dataclass added with the old filter
    would pass every test above by simply not being in them."""
    import inspect

    from core import file_manager as fm
    src = inspect.getsource(fm)
    stale = "known = {f.name for f in fields(cls)}\n        return cls(**{"
    assert stale not in src, (
        "a from_dict is back on the filter-and-drop rule, so a field a newer "
        "ChromIQ wrote is erased again")
    for name in ("ProjectManifest", "RunMeta", "CalibrationMeta"):
        body = inspect.getsource(getattr(fm, name))
        assert "split_known_fields" in body, (
            f"{name}.from_dict no longer uses the shared rule")
    for writer in ("write_json_atomically(self.meta_path, asdict(",
                   "write_json_atomically(self.manifest_path, asdict("):
        assert writer not in src, (
            "a writer is back on asdict(), which drops the carried fields on "
            "the way to disk")
