"""The ONE demo package attached to every release (#182 K29).

Knut, #182 5795310999: *"Create a bigger demo project package that attacks all
thresholds, metrics, requirement, output behaviour and messages and
functionality, from more angles of attack, so that none of these things are
only tested against one way of thinking, but rather multiple ways. Use these
demo projects in tests, but also release for download at release of app. Try
to use available paper data as part of the simulation data to make it more
realistic."*

`scripts/make_release_demo_package.py` builds it. The fast tests below pin
what can be checked without building: every ruling in the design record's
index is answered, every paper class says what its source says, the archive
is named after the version, and a build path cannot reach the public download.
The slow test builds the package (about four minutes, cached on disk keyed by
the generators and the app code they call) and asserts the coverage matrix.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _pkg():
    import importlib
    return importlib.import_module("make_release_demo_package")


def _gen():
    import importlib
    return importlib.import_module("make_report_limit_demos")


# ---------------------------------------------------------------------------
# fast
# ---------------------------------------------------------------------------
def test_every_live_ruling_in_the_spec_index_names_its_demonstration():
    """A ruling added to the index tomorrow is a row this package must answer.

    MUTATION: delete the "§19.4" entry of RULE_DEMOS and this goes red."""
    pkg = _pkg()
    rows = pkg.rule_map(pkg.spec_index_rows())
    assert len(rows) > 40, "the index table was not found in the spec"
    unanswered = [f"{r['section']} {r['subject']}" for r in rows
                  if not r["answered"]]
    assert not unanswered, unanswered


def test_every_project_a_demonstration_names_is_one_the_package_builds():
    pkg, gen = _pkg(), _gen()
    present = {n for n, _p in gen.PROJECTS} | {
        "Report-Limits-Evenness", "Report-Notes-Every-Reason",
        "Report-Limits-Every-Metric"}
    rows = pkg.rule_map(pkg.spec_index_rows(), present)
    wrong = [(r["section"], r["missing_projects"]) for r in rows
             if r["missing_projects"]]
    assert not wrong, wrong


def test_every_message_the_package_claims_is_in_the_catalogue():
    from workflow.measurement_messages import CATALOGUE
    pkg = _pkg()
    assert not [m for m in pkg.MESSAGE_DEMOS if m not in CATALOGUE]
    # and every report message the app has is listed, with a way to raise it
    # or the reason there is none
    missing = [m["id"] for m in pkg.message_rows() if not m["demos"]]
    assert not missing, missing


def test_the_paper_classes_say_what_their_sources_say():
    """Each class sits where the cited public fact puts it.

    Brightened papers measure blue (negative b*) and a paper without
    brighteners measures warm (positive b*); the office class's CIE whiteness
    is inside the 130 to 170 its source gives; the baryta class's is within
    a few units of the 96.30 its datasheet gives; newsprint is the darkest by
    a wide margin."""
    gen = _gen()
    pcs = gen.PAPER_CLASSES
    assert set(pcs) == {"glossy_oba", "baryta", "matte_rag", "office",
                        "newsprint"}
    for pc in pcs.values():
        L, a, b = pc.lab
        assert 80.0 <= L <= 97.0 and abs(a) <= 2.5, pc
        assert "http" in pc.source and pc.fact, pc
        if pc.oba == "high":
            assert b <= -5.0, pc
        elif pc.oba == "very low":
            assert -4.0 < b < 0.0, pc
        else:
            assert b > 0.0, pc
    assert 130.0 <= pcs["office"].cie_whiteness <= 170.0
    assert abs(pcs["baryta"].cie_whiteness - 96.30) < 3.0
    others = [pc.lab[0] for k, pc in pcs.items() if k != "newsprint"]
    assert pcs["newsprint"].lab[0] <= min(others) - 8.0


def test_every_paper_class_is_printed_on_by_a_run():
    gen = _gen()
    used = {plan.paper_class for _n, plans in gen.PROJECTS for plan in plans}
    assert set(gen.PAPER_CLASSES) <= used


def test_no_paper_class_copies_a_value_from_the_shipped_iso_file():
    """The package is public. The repository's ISO file carries no licensed
    numbers, and no paper white of ours may equal one it ever gains."""
    gen = _gen()
    iso = json.loads((ROOT / "data" / "compliance_sets" / "iso12647.json")
                     .read_text(encoding="utf-8"))
    text = json.dumps(iso)
    for pc in gen.PAPER_CLASSES.values():
        triple = [pc.lab[0], pc.lab[1], pc.lab[2]]
        assert json.dumps(triple) not in text


def test_border_dates_step_one_thousandth_either_side_of_the_limit():
    gen = _gen()
    by_row: dict = {}
    for vid, (row, value) in gen.BORDER_VALUES.items():
        by_row.setdefault((row, vid[:7]), []).append(value)
    assert len(by_row) >= 4
    for key, values in by_row.items():
        values.sort()
        assert len(values) == 3, key
        assert abs(values[1] - values[0] - 0.001) < 1e-9, key
        assert abs(values[2] - values[1] - 0.001) < 1e-9, key


def test_the_archive_is_named_after_the_app_version():
    from core.version import APP_VERSION
    pkg = _pkg()
    assert pkg.zip_name() == f"ChromIQ-Demo-Projects_v{APP_VERSION}.zip"
    assert pkg.root_name() == f"ChromIQ-Demo-Projects_v{APP_VERSION}"


def test_a_build_path_cannot_reach_the_public_package(tmp_path):
    """A saved report records the absolute folder of each measurement. Built
    on a Desktop, that is somebody's home folder in a public download."""
    pkg = _pkg()
    root = tmp_path / pkg.root_name("9.9.9")
    rep = root / "P" / "runs" / "run1" / "reports"
    rep.mkdir(parents=True)
    f = rep / "report_x.json"
    f.write_text(json.dumps({"dir": str(root / "P" / "runs" / "run1")}),
                 encoding="utf-8")
    (root / "img.tif").write_bytes(b"\x00" + str(root).encode())
    assert pkg.path_leaks(root), "the leak check must see the build path"
    assert pkg.neutralise_paths(root) == 1
    assert not pkg.path_leaks(root)
    assert json.loads(f.read_text(encoding="utf-8"))["dir"] == \
        f"{pkg.NEUTRAL_PREFIX}/{root.name}/P/runs/run1"


# ---------------------------------------------------------------------------
# slow: the real package
# ---------------------------------------------------------------------------
_CACHE_NAME = "chromiq-release-demo-cache"


def _source_key() -> str:
    """The generators and every app module they call. A change to either
    rebuilds; nothing else does."""
    h = hashlib.sha256()
    files = sorted([*(ROOT / "scripts").glob("make_*demo*.py"),
                    *(ROOT / "scripts").glob("make_verification_preset_demos.py"),
                    *(ROOT / "workflow").rglob("*.py"),
                    *(ROOT / "core").rglob("*.py"),
                    ROOT / "docs" / "design" / "measurement_report_limits.md"])
    for p in files:
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


# THE CACHE IS SHARED BY EVERY RUN ON THE MACHINE, SO NO RUN MAY DELETE WHAT
# ANOTHER IS USING (2026-10-03). This fixture used to keep "one build" by
# emptying the whole cache folder before building into the key folder itself.
# A second session's gate, running at the same time on another branch (another
# key), was building into its own key folder at that moment; the first run
# deleted it from under printtarg, and that gate came out with five setup
# errors, "printtarg: Unable to open file 'chart.ti2' for writing".
#
# So now:
# * a build goes into a PRIVATE folder (``chromiq-build-<pid>-*``) and is published
#   onto the key path with one rename, so nobody ever sees, or deletes, a
#   half-built package under a key;
# * a run that uses a key holds a lease on it (``.in-use/<key>.<pid>``) until
#   its module is done, and touches the key folder;
# * pruning removes only an entry that is BOTH older than
#   :data:`_STALE_AFTER_S` AND held by no live process (a key with no live
#   lease, a build folder whose pid is gone). The speed benefit is the same:
#   a warm key is used as it is.
_STALE_AFTER_S = 6 * 3600
_LEASES = ".in-use"
_BUILD_PREFIX = "chromiq-build-"   # spelled out at the mkdtemp too (sweep test)
_READY = "coverage-matrix.json"


def _pid_alive(pid: int) -> bool:
    """Is process *pid* running? True when that cannot be told: a lease is
    only ever ignored on proof that its holder is gone."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) TERMINATES the process on Windows; ask instead.
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            try:
                if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                    return True
                return code.value == 259             # STILL_ACTIVE
            finally:
                k32.CloseHandle(h)
        except Exception:                            # noqa: BLE001
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                                  # someone else's, alive
    except OSError:
        return True
    return True


def _take_lease(cache: Path, key: str, pid: "int | None" = None) -> Path:
    leases = cache / _LEASES
    leases.mkdir(parents=True, exist_ok=True)
    lease = leases / f"{key}.{pid or os.getpid()}"
    lease.write_text(str(pid or os.getpid()), encoding="utf-8")
    return lease


def _holders(cache: Path, name: str) -> "list[int]":
    """The live processes holding *name* (a key folder or a build folder)."""
    if name.startswith(_BUILD_PREFIX):
        try:
            pid = int(name[len(_BUILD_PREFIX):].split("-", 1)[0])
        except ValueError:
            return []
        return [pid] if _pid_alive(pid) else []
    live = []
    for lease in (cache / _LEASES).glob(f"{name}.*"):
        try:
            pid = int(lease.name.rsplit(".", 1)[1])
        except ValueError:
            continue
        if _pid_alive(pid):
            live.append(pid)
    return live


def _prune(cache: Path, keep: str, now: "float | None" = None) -> "list[str]":
    """Remove every entry that is stale by age AND held by nobody alive.
    Returns the names removed. Never touches *keep*."""
    now = time.time() if now is None else now
    removed = []
    if not cache.is_dir():
        return removed
    for lease in list((cache / _LEASES).glob("*")):
        try:
            if not _pid_alive(int(lease.name.rsplit(".", 1)[1])):
                lease.unlink()
        except (ValueError, OSError):
            pass
    for entry in list(cache.iterdir()):
        if entry.name in (keep, _LEASES) or not entry.is_dir():
            continue
        try:
            if now - entry.stat().st_mtime < _STALE_AFTER_S:
                continue                             # young: maybe in use
        except OSError:
            continue                                 # vanished meanwhile
        if _holders(cache, entry.name):
            continue                                 # a live run holds it
        shutil.rmtree(entry, ignore_errors=True)
        removed.append(entry.name)
    return removed


def _ensure_package(cache: Path, key: str, root_name: str,
                    build) -> "tuple[Path, Path | None]":
    """The package for *key*: (its root, a private folder to delete after use,
    or None). *build(folder)* builds ``folder / root_name``.

    Call with the lease on *key* already taken. Builds privately and
    publishes with a rename; a complete package another run published first
    wins and ours is dropped."""
    here = cache / key
    root = here / root_name
    if (root / _READY).is_file():
        return root, None
    cache.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"chromiq-build-{os.getpid()}-",
                                    dir=str(cache)))
    try:
        build(staging)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if not (staging / root_name / _READY).is_file():
        return staging / root_name, staging          # let the caller report it
    for attempt in range(3):
        try:
            os.replace(staging, here)                # POSIX: onto an empty dir too
            return root, None
        except OSError:
            if (root / _READY).is_file():
                shutil.rmtree(staging, ignore_errors=True)
                return root, None                    # theirs is as good as ours
            # An incomplete folder on the key path: an interrupted build of
            # the old code, or an old-code run building there NOW (new runs
            # never build on a key path). Only an old one is moved aside;
            # otherwise ours stays private and is deleted after use.
            try:
                old = time.time() - here.stat().st_mtime >= _STALE_AFTER_S
            except OSError:
                continue                             # it just went; retry
            if not old:
                break
            aside = cache / f"{_BUILD_PREFIX}0-stale-{os.getpid()}-{attempt}"
            try:
                os.replace(here, aside)
            except OSError:
                continue
            shutil.rmtree(aside, ignore_errors=True)
    return staging / root_name, staging


@pytest.fixture(scope="module")
def built_package(tmp_path_factory):
    pkg = _pkg()
    if not Path("/Applications/Argyll/bin/targen").exists() and not \
            os.environ.get("CHROMIQ_ARGYLL_BIN"):
        pytest.skip("ArgyllCMS is needed to build the demo package")
    cache = Path(os.environ.get("CHROMIQ_RELEASE_DEMO_CACHE",
                                Path(os.environ.get("CHROMIQ_SUITE_REAL_TMP")
                                     or tempfile.gettempdir()) / _CACHE_NAME))
    key = _source_key()
    outcome: dict = {}

    def build(into: Path) -> None:
        sandbox = tmp_path_factory.mktemp("demo-build-sandbox")
        env = dict(os.environ,
                   CHROMIQ_SETTINGS_FILE=str(sandbox / "settings.ini"),
                   CHROMIQ_PRESETS_DIR=str(sandbox / "presets"),
                   CHROMIQ_COMPLIANCE_ISO_FILE=str(
                       ROOT / "data" / "compliance_sets" / "iso12647.json"),
                   QT_QPA_PLATFORM="offscreen")
        outcome["r"] = subprocess.run(
            [sys.executable,
             str(ROOT / "scripts" / "make_release_demo_package.py"), str(into)],
            cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3600)

    lease = _take_lease(cache, key)
    private = None
    try:
        root, private = _ensure_package(cache, key, pkg.root_name(), build)
        if private is None:
            try:
                os.utime(cache / key)                # last used: now
            except OSError:
                pass
        _prune(cache, keep=key)
        r = outcome.get("r")
        assert (root / _READY).is_file(), (
            f"the package did not finish building (exit {r.returncode}):\n"
            f"{r.stdout[-4000:]}\n{r.stderr[-4000:]}" if r else
            "the package did not finish building")
        yield root
    finally:
        if private is not None:
            shutil.rmtree(private, ignore_errors=True)
        try:
            lease.unlink()
        except OSError:
            pass


# fast: the cache is safe to share --------------------------------------------
def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait(timeout=60)
    return p.pid


def _age(path: Path, seconds: float) -> None:
    t = time.time() - seconds
    os.utime(path, (t, t))


def test_pruning_spares_what_another_run_holds_and_drops_the_abandoned(tmp_path):
    """Only an entry that is old AND held by no live process goes.

    MUTATION: make `_holders` return [] (the old "empty the cache" rule) and
    the other run's package and build folder are deleted."""
    cache = tmp_path
    other, dead = os.getppid(), _dead_pid()
    old = 2 * _STALE_AFTER_S
    for name in ("theirs", "abandoned", "young", "mine",
                 f"{_BUILD_PREFIX}{other}-x", f"{_BUILD_PREFIX}{dead}-y"):
        (cache / name / "pkg").mkdir(parents=True)
    _take_lease(cache, "theirs", pid=other)
    _take_lease(cache, "abandoned", pid=dead)
    for name in ("theirs", "abandoned", "mine",
                 f"{_BUILD_PREFIX}{other}-x", f"{_BUILD_PREFIX}{dead}-y"):
        _age(cache / name, old)
    removed = _prune(cache, keep="mine")
    assert sorted(removed) == sorted(["abandoned", f"{_BUILD_PREFIX}{dead}-y"])
    left = {p.name for p in cache.iterdir()}
    assert {"theirs", "young", "mine", f"{_BUILD_PREFIX}{other}-x"} <= left
    assert not (cache / _LEASES / f"abandoned.{dead}").exists()
    assert (cache / _LEASES / f"theirs.{other}").exists()


def test_two_runs_building_at_once_do_not_break_each_other(tmp_path, monkeypatch):
    """Three runs at once, two keys, one cache, and age protecting nothing
    (`_STALE_AFTER_S` = 0): every run gets a complete package, each key is
    published once, nothing half-built is left on a key path.

    This is the 2026-10-03 failure simulated: each "build" writes its chart,
    pauses while the others prune, then finishes. Under the old fixture the
    second run's pruning deleted the first run's folder mid-build."""
    import threading
    monkeypatch.setattr(sys.modules[__name__], "_STALE_AFTER_S", 0)
    cache = tmp_path / "cache"
    gate = threading.Barrier(3, timeout=30)
    results: dict = {}
    errors: list = []

    def build(into: Path) -> None:
        root = into / "Pkg"
        root.mkdir(parents=True)
        (root / "chart.ti2").write_text("ti2", encoding="utf-8")
        gate.wait()                       # everyone is mid-build now
        time.sleep(0.2)                   # …while the others prune
        assert (root / "chart.ti2").is_file(), "deleted under a build"
        (root / _READY).write_text("{}", encoding="utf-8")

    def one_run(tag: str, key: str) -> None:
        lease = _take_lease(cache, key)
        try:
            root, private = _ensure_package(cache, key, "Pkg", build)
            _prune(cache, keep=key)
            results[tag] = (root, private, (root / _READY).is_file(),
                            (root / "chart.ti2").is_file())
        except BaseException as e:        # noqa: BLE001 — reported below
            errors.append((tag, repr(e)))

    cache.mkdir()
    threads = [threading.Thread(target=one_run, args=a)
               for a in (("a", "key1"), ("b", "key2"), ("c", "key1"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert all(ok and chart for _r, _p, ok, chart in results.values()), results
    assert all(p is None for _r, p, _o, _c in results.values()), results
    assert results["a"][0] == results["c"][0] == cache / "key1" / "Pkg"
    assert (cache / "key2" / "Pkg" / _READY).is_file()
    assert not [p.name for p in cache.iterdir()
                if p.name.startswith(_BUILD_PREFIX)]


def test_a_warm_key_is_used_without_building(tmp_path):
    (tmp_path / "k" / "Pkg").mkdir(parents=True)
    (tmp_path / "k" / "Pkg" / _READY).write_text("{}", encoding="utf-8")

    def build(_into):
        raise AssertionError("a warm cache must not rebuild")
    assert _ensure_package(tmp_path, "k", "Pkg", build) == \
        (tmp_path / "k" / "Pkg", None)


def test_the_fixture_never_empties_the_shared_cache():
    """MUTATION: put back `for old in cache.iterdir(): shutil.rmtree(old)`."""
    text = Path(__file__).read_text(encoding="utf-8")
    src = text[text.index("def built_package("):
               text.index("# fast: the cache is safe to share")]
    assert "rmtree(old" not in src and "iterdir()" not in src
    assert "_ensure_package(" in src and "_take_lease(" in src


@pytest.mark.slow
def test_the_built_package_verifies(built_package):
    """Every project present, every design matched, every measurable row
    tripped and passed from two angles each, every ruling answered, no path
    of the build machine in any file."""
    gaps = _pkg().verify(built_package)
    assert not gaps, gaps


@pytest.mark.slow
def test_every_measurable_row_is_tripped_and_passed_from_two_angles(built_package):
    m = json.loads((built_package / "coverage-matrix.json")
                   .read_text(encoding="utf-8"))
    measurable = [r for r in m["metrics"] if r["measurable"]]
    assert len(measurable) >= 18
    short = [(r["id"], r["trip_angles"], r["pass_angles"]) for r in measurable
             if r["trip_angles"] < 2 or r["pass_angles"] < 2]
    assert not short, short


@pytest.mark.slow
def test_every_selectable_set_trips_and_passes_every_row_it_can(built_package):
    """Knut's matrix, now from two routes: every (row, set) cell that any
    report judged shows the row both over its limit and inside it."""
    m = json.loads((built_package / "coverage-matrix.json")
                   .read_text(encoding="utf-8"))
    one_sided = [(c["row"], c["set"]) for c in m["cells"]
                 if not (c["trip_angles"] and c["pass_angles"])]
    assert not one_sided, one_sided


@pytest.mark.slow
def test_every_paper_class_reaches_the_paper_white_line(built_package):
    """The paper white a sheet printed THROUGH the profile records is its
    class's, so the paper is in the numbers and not only in a table.

    Measured on screen (2026-09-23): 96.0 on the glossy class, 94.5 on the
    rag. A sheet judged in absolute Lab and a From Profile Gamut chart put
    every patch, the paper too, at its designed distance from the chart's aim
    (office paper's unrecorded sheet read L* 100.4), so those are not asked;
    nor, since K49, a date that designs its paper off the profile's."""
    gen = _gen()
    seen: dict = {}
    for p in built_package.glob("Report-Limits-*/runs/run*/verifications/*/"
                                "reports/report_*.json"):
        rep = json.loads(p.read_text(encoding="utf-8"))
        if (rep.get("printing") or {}).get("colour") != "through-profile" or \
                rep.get("reference_source") == "colorimetric":
            continue
        # #182 K49, (b2): the paper row is judged on an ordinary chart now,
        # and a date that designs the paper off its profile's (`white_de`)
        # prints on a drifted paper on purpose. The class's own paper is the
        # sheet whose paper row reads it, within rounding.
        paper = (rep.get("condition_reference") or {}).get("paper") or {}
        if paper.get("de") is None or float(paper["de"]) > 0.1:
            continue
        meta = json.loads((p.parents[3] / "meta.json").read_text(encoding="utf-8"))
        seen.setdefault(meta.get("paper"), []).append(rep["paper_white"]["lab"])
    for pc in gen.PAPER_CLASSES.values():
        labs = seen.get(f"{pc.name} (demo)")
        assert labs, pc.id
        assert all(max(abs(x - y) for x, y in zip(lab, pc.lab)) < 0.15
                   for lab in labs), (pc.id, labs)


@pytest.mark.slow
def test_one_project_answers_every_metric_passed_and_failed(built_package):
    """K40-3 (Knut, #182 5832026677: "yes"): Report-Limits-Every-Metric's one
    FROM PROFILE GAMUT chart answers every metric the presets window counts
    (18 of 18), and its three dates judge all twenty ChromIQ can compute:
    PASS, PASS, FAIL, with only "the same chart measured again" N-A on the
    first. The tone row is read on the chart's neutral aims (K40-2).

    MUTATION, proven red: ``neutral_aims=None`` in `build_report`'s call of
    `ramps_block` (no "source" on the grey axis); and the project left out of
    `make_release_demo_package.build` (the project is missing)."""
    from workflow import measurement_report as MR
    from workflow import preset_eligibility as PE
    from workflow.compliance_sets import ROWS
    root = built_package / "Report-Limits-Every-Metric"
    assert (root / "project.json").is_file()
    run = root / "runs" / "run1"
    chart = next((run / "verifications").glob("*.ti2"))
    PE.clear_cache()
    a = PE.assess(chart, PE.ANY_REPORT_TYPE, PE.ALL_METRICS)
    assert len(a.asked) == 18 and not a.missing, a.missing
    computable = [r.id for r in ROWS if r.status in ("now", "build", "ref")]
    assert len(computable) == 20
    reps = sorted(run.glob("verifications/*/reports/report_*.json"))
    assert len(reps) == 3, reps
    want = ("PASS", "PASS", "FAIL")
    for k, (p, word) in enumerate(zip(reps, want)):
        rep = json.loads(p.read_text(encoding="utf-8"))
        assert rep["reference_source"] == "colorimetric"
        assert rep["ramps_30_70"]["axes"]["grey"].get("source") == "neutral_aims"
        rows = {r["row_id"]: r for r in MR.recorded_verdict(rep)["rows"]}
        for rid in computable:
            expect = word
            if k == 0 and rid == "repeat_measurement_de00_max":
                expect = "N-A"
            assert rows[rid]["word"] == expect, (p.parts[-3], rid, rows[rid])

