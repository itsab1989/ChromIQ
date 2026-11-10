"""F-06: the CMY+N gamut-mapping helper is an Argyll child like colprof and
xicclu: while it runs it is in the registry, so a quit
(terminate_argyll_children, then os._exit) kills it instead of leaving it
running beside a closed app."""
from __future__ import annotations

import os
import sys
import threading
import time

import numpy as np
import pytest

from workflow.profile_engine import gamut_map, gammap_helper


@pytest.mark.skipif(os.name == "nt", reason="the stand-in helper is a shell script")
def test_quit_kills_a_running_helper(tmp_path, monkeypatch):
    fake = tmp_path / "chromiq-gammap"
    fake.write_text(f"#!/bin/sh\nexec {sys.executable} -c 'import time; time.sleep(60)'\n",
                    encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("CHROMIQ_GAMMAP", str(fake))
    errors: list = []

    def call():
        try:
            gammap_helper.run_gammap(np.zeros((2, 3)), src_gam=tmp_path / "s.gam",
                                     intent="p", mapres=9,
                                     dst_cloud_jab=np.zeros((4, 3)),
                                     wp_jab=np.zeros(3), bp_jab=np.zeros(3))
        except Exception as exc:                      # noqa: BLE001
            errors.append(exc)
    t = threading.Thread(target=call, daemon=True)
    t0 = time.monotonic()
    t.start()
    while not gamut_map._LIVE_CHILDREN and time.monotonic() - t0 < 10:
        time.sleep(0.05)
    assert gamut_map._LIVE_CHILDREN, "the helper never registered"
    assert gamut_map.terminate_argyll_children() == 1
    t.join(10)
    assert not t.is_alive() and time.monotonic() - t0 < 30
    assert errors and isinstance(errors[0], gammap_helper.HelperUnavailable)
    assert not gamut_map._LIVE_CHILDREN
