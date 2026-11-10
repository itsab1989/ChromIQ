"""Expert review 2026-11-10: two engine builds in one process never overlap.

A build writes its switches into module-level state (oog_clip.PARAMS,
b2a.REFIT_ANCHOR, ...) and clears it when it ends, so a second build running
at the same time on another thread would change the first one's profile with
no error. ``build_profile`` holds a lock for the whole build.
"""
import threading
import time

from workflow.profile_engine import builder


def test_a_second_build_waits_for_the_first(monkeypatch, tmp_path):
    inside = []
    overlaps = []
    first_in = threading.Event()

    def fake_impl(ti3, out, settings, started):
        inside.append(ti3)
        if len(inside) > 1:
            overlaps.append(tuple(inside))
        first_in.set()
        time.sleep(0.3)
        inside.remove(ti3)
        return ti3

    monkeypatch.setattr(builder, "_build_profile_impl", fake_impl)
    results = {}

    def run(name):
        results[name] = builder.build_profile(name, tmp_path / name)

    a = threading.Thread(target=run, args=("a",))
    a.start()
    assert first_in.wait(5)
    b = threading.Thread(target=run, args=("b",))
    b.start()
    a.join(10)
    b.join(10)
    assert results == {"a": "a", "b": "b"}
    assert overlaps == []


def test_the_lock_is_free_again_after_a_failed_build(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise RuntimeError("no")

    monkeypatch.setattr(builder, "_build_profile_impl", boom)
    for _ in range(2):
        try:
            builder.build_profile("x", tmp_path / "x")
        except RuntimeError:
            pass
    assert builder._BUILD_LOCK.acquire(timeout=1)
    builder._BUILD_LOCK.release()
