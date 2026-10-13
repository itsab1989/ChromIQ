"""A fork never waits on numpy's OpenBLAS (Knut, #182 6144104040, 4.3.5-beta.2).

The beta-2 hang: the window's thread started a subprocess, and inside
``fork()`` OpenBLAS's fork handler waited for ever on its thread pool while
the gamut-reach thread sat in a numpy matrix product. ``main.py`` now pins
OpenBLAS to one thread before numpy loads (``core/blas_threads.py``), and the
frozen apps do it again from a PyInstaller runtime hook.

The stress test below hung 5 runs in 5 with the numpy ChromIQ ships on macOS
(the OpenBLAS wheel) when the pin was missing. With the development venv's
Accelerate numpy it cannot hang either way; the static tests are what hold
the pin in place there.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

STDLIB_PRELUDE = {"__future__", "logging", "os", "sys", "traceback", "pathlib"}


def test_main_pins_openblas_before_anything_else_is_imported():
    tree = ast.parse((REPO / "main.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue                                   # the docstring
        if isinstance(node, ast.Import):
            assert {a.name for a in node.names} <= STDLIB_PRELUDE, ast.dump(node)
            continue
        if isinstance(node, ast.ImportFrom):
            if node.module == "core.blas_threads":
                continue
            assert node.module in STDLIB_PRELUDE, node.module
            continue
        # the first statement that does anything is the pin itself
        assert (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", "") == "pin_blas_threads"), \
            f"main.py does {ast.unparse(node)!r} before pinning OpenBLAS"
        return
    raise AssertionError("main.py never calls pin_blas_threads()")


def test_the_frozen_apps_pin_it_from_a_runtime_hook():
    from core.blas_threads import PINNED
    hook = REPO / "hooks" / "rth_blas_threads.py"
    env: dict = {}
    src = hook.read_text(encoding="utf-8")
    assert "import numpy" not in src
    exec(compile(src.replace("os.environ", "env"), str(hook), "exec"),
         {"env": env, "os": os})
    assert env == PINNED
    for spec in ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec"):
        text = (REPO / spec).read_text(encoding="utf-8")
        assert "runtime_hooks=['hooks/rth_blas_threads.py']" in text, spec


def _run(code: str, env_extra: "dict | None" = None, timeout: float = 180):
    env = dict(os.environ)
    env.pop("OPENBLAS_NUM_THREADS", None)
    env.pop("GOTO_NUM_THREADS", None)
    env.update(env_extra or {})
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(REPO), env.get("PYTHONPATH", "")) if p)
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)],
                          cwd=REPO, env=env, capture_output=True, text=True,
                          encoding="utf-8", timeout=timeout)


def test_the_pin_overrides_a_thread_count_already_in_the_environment():
    r = _run("""
        from core.blas_threads import pin_blas_threads, blas_thread_count
        assert pin_blas_threads() is True
        import numpy
        numpy.ones((64, 64)) @ numpy.ones((64, 64))
        print("threads", blas_thread_count())
        """, {"OPENBLAS_NUM_THREADS": "8"})
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split()[-1] in ("1", "None"), r.stdout


def test_a_late_pin_says_so():
    r = _run("""
        import numpy
        from core.blas_threads import pin_blas_threads
        print(pin_blas_threads())
        """)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip() == "False"


def test_forking_while_the_gamut_reach_multiplies_never_hangs(tmp_path):
    """The beta-2 flow in miniature: the app's own start-up prelude, then a
    background thread in gamut_target's matrix products while the main
    thread starts process after process for a few seconds."""
    code = """
        import runpy, subprocess, threading, time
        runpy.run_path("main.py", run_name="not_main")     # the app's prelude
        import numpy as np
        from workflow import gamut_target
        from core.blas_threads import blas_thread_count
        stop = threading.Event()
        def reach():
            x = np.random.default_rng(1).random((2048, 3)) * 100
            while not stop.is_set():
                gamut_target.wide_cube_labs()
                gamut_target._nearest(x, x)
        t = threading.Thread(target=reach, daemon=True)
        t.start()
        spawns, end = 0, time.monotonic() + 4.0
        while time.monotonic() < end:
            subprocess.run(["/bin/sh", "-c", "exit 0"] if __import__("os").name != "nt"
                           else ["cmd", "/c", "exit 0"])
            spawns += 1
        stop.set(); t.join()
        print("DONE", spawns, blas_thread_count())
        """
    try:
        r = _run(code, {"CHROMIQ_LOG_DIR": str(tmp_path)},
                 timeout=240)
    except subprocess.TimeoutExpired:
        raise AssertionError(
            "did not finish in 240 s: a process start waited on OpenBLAS's "
            "thread pool (the 4.3.5-beta.2 hang); is OpenBLAS still pinned "
            "to one thread before numpy loads?") from None
    assert r.returncode == 0, r.stderr[-2000:]
    words = r.stdout.split()
    assert words[0] == "DONE" and int(words[1]) > 0, r.stdout
    assert words[2] in ("1", "None"), r.stdout
