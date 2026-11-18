"""The recording tools read what was recorded and judge it with the app's own allow-list.

`scripts/recording_timeline.py` and `scripts/recording_vs_allowlist.py` are how a recording of a
maker's program becomes an allow-list, and how an owner's results are checked against the app.
These tests use only INVENTED recordings (`scripts/recordings/synthetic.py`), in both formats the
synthetic writer knows, and pin what matters:

* every host line comes out, in order, with its answer time;
* a memory answer is never printed, and instrument data never;
* the allow-list verdict is the app's own (`workflow/i1io/table/lines.py::classify`), so a line
  the app may not send is REFUSED with the app's reason, and the comparer exits 1 for it;
* a computed move is rebuilt by the app's own builder byte for byte;
* a file that is not a recording is refused with exit 2, and `--help` has no side effects.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from recordings import capture, synthetic  # noqa: E402
from recordings.plugins import Line, load_plugin  # noqa: E402
import recording_timeline as tl  # noqa: E402
import recording_vs_allowlist as cmp_  # noqa: E402


@pytest.fixture(params=["darwin", "usbmon"])
def recording(tmp_path, request):
    return synthetic.write(tmp_path / f"invented-{request.param}.pcap", request.param)


def test_every_host_line_comes_out_in_order(recording):
    plugin, _t0, _ev, lines = tl.load(recording, "i1io2-table")
    host = [ln.text for ln in lines if ln.who == "host"]
    assert host[0] == ";a133"
    assert len(host) == 7
    assert host[-1].startswith(";m0044c064001f4")
    times = [ln.t for ln in lines]
    assert times == sorted(times)


def test_answer_times_are_paired_with_their_line(recording):
    plugin, _t0, _ev, lines = tl.load(recording, "i1io2-table")
    rows = {r["line"]: r for r in tl.commands(plugin, lines)}
    move = rows[";m0044e0640012c6b"]
    assert move["count"] == 1
    assert move["took_min_s"] == pytest.approx(1.4, abs=0.01)
    assert rows[";p025"]["count"] == 2


def test_a_memory_answer_and_instrument_data_are_never_printed(tmp_path, capsys):
    rec = synthetic.write(tmp_path / "r.pcap", "darwin")
    assert tl.main([str(rec)]) == 0
    out = capsys.readouterr().out
    assert "DEADBEEF" not in out.upper()
    assert "not shown" in out
    assert "instrument data on endpoint 0x82, 268 bytes (not shown)" in out


def test_the_verdict_is_the_apps_own_allow_list(recording):
    plugin, _t0, _ev, lines = tl.load(recording, "i1io2-table")
    rows = cmp_.verdicts(plugin, lines)
    by_line = {r["line"]: r for r in rows}
    assert by_line[";a133"]["allowed"] and by_line[";a133"]["label"] == "identity"
    move = by_line[";m0044e0640012c6b"]
    assert move["allowed"] and move["motion"] and move["rebuilt"] == "same"
    bad = [r for r in rows if not r["allowed"]]
    assert len(bad) == 1 and "speed 500" in bad[0]["reason"]


def test_the_comparer_exits_1_on_a_refused_line_and_writes_json(tmp_path, capsys):
    rec = synthetic.write(tmp_path / "r.pcap", "darwin")
    second = tmp_path / "second.txt"
    second.write_text(";a133\n# a comment\n;s022\n", encoding="utf-8")
    out_json = tmp_path / "v.json"
    rc = cmp_.main([str(rec), "--second-list", str(second), "--json", str(out_json)])
    assert rc == 1
    rows = json.loads(out_json.read_text(encoding="utf-8"))
    assert [r["in_second_list"] for r in rows[:2]] == [True, True]
    assert rows[2]["in_second_list"] is False
    assert "refused: 1" in capsys.readouterr().out


def test_a_rebuilt_line_that_differs_is_named():
    plugin = load_plugin("i1io2-table")
    # the right form and numbers, but upper-case hex: the app's builder writes lower case
    line = Line(0.0, 0.0, "host", ";m0044E0640012c6b")
    assert plugin.rebuild(line) is None          # not the computed form the app accepts
    good = Line(0.0, 0.0, "host", ";m0044e0640012c6b")
    assert plugin.rebuild(good) == good.text


def test_a_file_that_is_not_a_recording_is_refused(tmp_path, capsys):
    junk = tmp_path / "notes.txt"
    junk.write_text("not a recording", encoding="utf-8")
    assert tl.main([str(junk)]) == 2
    assert cmp_.main([str(junk)]) == 2
    with pytest.raises(capture.NotARecording):
        capture.read_capture(junk)


def test_a_plugin_can_be_loaded_from_a_file(tmp_path):
    src = tmp_path / "my_device.py"
    src.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
        "from recordings.plugins import DevicePlugin\n"
        "class MyDevice(DevicePlugin):\n"
        "    name = 'mine'\n", encoding="utf-8")
    plugin = load_plugin(f"{src}:MyDevice")
    assert plugin.name == "mine"
    assert plugin.check(Line(0, 0, "host", "x")).allowed is False


@pytest.mark.parametrize("script", ["recording_timeline.py", "recording_vs_allowlist.py",
                                    "recordings/synthetic.py"])
def test_help_runs_and_writes_nothing(tmp_path, script):
    before = sorted(p.name for p in tmp_path.iterdir())
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--help"],
                          cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "usage" in proc.stdout.lower()
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_the_synthetic_writer_never_overwrites(tmp_path):
    out = tmp_path / "x.pcap"
    out.write_bytes(b"keep")
    assert synthetic.main([str(out)]) == 2
    assert out.read_bytes() == b"keep"
