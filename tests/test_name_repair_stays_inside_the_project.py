"""The repair journal may never move a file outside the project folder.

`name-repair.json` lives inside a project folder, and project folders get
zipped and sent to other people. `_apply` used to do `root / entry["from"]`
and rename it — and `Path("/a") / "../x"` escapes, while `Path("/a") / "/etc/x"`
discards the root entirely. So opening a shared project whose journal was
crafted (or merely corrupted) renamed files anywhere the recipient could write,
silently. The only precondition is a dotted folder name, which the sender
chooses.

Shipped in 4.1.3-beta.17. Proven before the fix: `_apply` returned `done=1` and
the file outside the project was gone.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import name_repair


def _project(tmp_path: Path):
    """A project folder with a victim file sitting OUTSIDE it."""
    victim = tmp_path / "IMPORTANT-ORIGINALS.tif"
    victim.write_bytes(b"the user's only copy")
    root = tmp_path / "Victim-w10.0mm"
    (root / "runs" / "run1").mkdir(parents=True)
    return root, victim


@pytest.mark.parametrize("frm,to", [
    ("../IMPORTANT-ORIGINALS.tif", "../STOLEN.tif"),          # relative escape
    ("runs/run1/../../../IMPORTANT-ORIGINALS.tif", "runs/run1/x.tif"),
    ("/etc/hosts", "runs/run1/x.tif"),                        # absolute source
    ("runs/run1/a.ti2", "/tmp/chromiq-escape.ti2"),           # absolute target
])
def test_an_entry_pointing_outside_is_refused(tmp_path, frm, to):
    root, victim = _project(tmp_path)
    entries = [{"from": frm, "to": to}]
    done, _failed = name_repair._apply(entries, root)

    assert done == 0, f"{frm!r} -> {to!r} was executed"
    assert entries[0].get("state") == "skipped-outside-project"
    assert victim.exists() and victim.read_bytes() == b"the user's only copy"
    assert not (tmp_path / "STOLEN.tif").exists()
    assert not Path("/tmp/chromiq-escape.ti2").exists()


def test_a_legitimate_entry_still_runs(tmp_path):
    """THE CONTROL. Without this, "refuse everything" would pass the test above.

    A rename wholly inside the project must still happen, or the repair is
    broken rather than safe.
    """
    root, _victim = _project(tmp_path)
    src = root / "runs" / "run1" / "Victim-w10.ti2"
    src.write_bytes(b"chart")
    entries = [{"from": "runs/run1/Victim-w10.ti2",
                "to": "runs/run1/Victim-w10.0mm.ti2"}]
    done, failed = name_repair._apply(entries, root)

    assert (done, failed) == (1, 0), "a legitimate in-project rename was refused"
    assert entries[0]["state"] == "done"
    assert (root / "runs" / "run1" / "Victim-w10.0mm.ti2").read_bytes() == b"chart"
    assert not src.exists()
