"""`write_json_atomically` may carry a file's properties across, not its age.

B8-312, and it is a fault in a fix of my own (B8-301, the atomic write). The
helper called `shutil.copystat(path, tmp)` so that a file's mode, flags and
xattrs survived a rewrite, and `copystat` carries `st_mtime` with them. The
rewritten file therefore claimed it had not changed.

What that cost: the Measurement Report's label cache is keyed on
`st_mtime_ns`, so after a recalculation the "Saved reports" entry went on
reading "Quick check" over a file that now held `chromiq_default`, for the rest
of the session. A freshly opened window was correct, which is why no test that
reopens the dialog could see it.
"""
from __future__ import annotations

import os
import time

import pytest


def _write(path, payload):
    from core.file_manager import write_json_atomically
    write_json_atomically(path, payload)


def test_a_rewrite_moves_the_modification_time(tmp_path):
    """MUTATION: put a bare `shutil.copystat(path, tmp)` back and this goes
    red."""
    p = tmp_path / "report.json"
    _write(p, {"set": "chromiq_quick"})
    # age the file, the way a report saved days ago is aged
    old_ns = int((time.time() - 86400) * 1e9)
    os.utime(p, ns=(old_ns, old_ns))
    before = p.stat().st_mtime_ns
    _write(p, {"set": "chromiq_default"})
    after = p.stat().st_mtime_ns
    assert after > before, (
        "the rewritten file still claims the timestamp it had before, so "
        "anything keyed on its mtime goes on serving the old contents")


def test_a_rewrite_still_carries_the_mode(tmp_path):
    """The reason `copystat` is there at all: a property the USER set on the
    file must survive a rewrite.

    MUTATION: drop the `copystat` call and this goes red.
    """
    p = tmp_path / "report.json"
    _write(p, {"set": "chromiq_quick"})
    os.chmod(p, 0o640)
    _write(p, {"set": "chromiq_default"})
    assert (p.stat().st_mode & 0o777) == 0o640, (
        "the rewrite lost a permission the user had set on the file")


@pytest.mark.parametrize("payload", [{"a": 1}, {"a": [1, 2, 3]}])
def test_the_rewrite_is_still_the_content_that_was_asked_for(tmp_path, payload):
    import json
    p = tmp_path / "x.json"
    _write(p, payload)
    assert json.loads(p.read_text(encoding="utf-8")) == payload
