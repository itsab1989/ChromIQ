"""THE i1PRO 2 RULER STREAM PAIRS BY CHROMIQ'S OWN ENGINE (4.3.47, issue 216).

An ES-2000 (an OEM i1Pro 2, fw 634) on Windows: 79 of 80 strips had
samples = readings x clocks - 2, the 80th one 64-sample USB packet more
(220382 samples for 1620 readings at 136 clocks). The rule of 4.3.35,
|samples - (readings x clocks - 5)| <= 64, came from i1Profiler's recordings;
that strip was 67 off and lost its ruler figures. The same "- 2" holds on
104 of 104 strips of another i1Pro 2 with ChromIQ's engine.

The rule is now "under half a reading from readings x clocks - 2": it keeps
the extra packet, and still refuses every stream that belongs to another
number of readings, even one with an extra packet towards the expected count.
"""
from workflow import ruler_check as rc


def _rec(samples, readings=1620, clocks=136):
    # a clean ruler: 340 legal steps (quadrature 0,2,3,1) spread over the scan
    gray = (0, 2, 3, 1)
    changes, last = [], 0
    for k in range(340):
        at = int(samples * 0.1) + int(samples * 0.8) * k // 340
        changes += [at - last, gray[(k + 1) % 4]]
        last = at
    return {"instrument": "i1pro2", "ended": "short", "samples": samples,
            "readings": readings, "clocks": clocks, "clock_s": 36e-6,
            "first": 0, "changes": changes}


def test_the_es2000_strip_with_one_extra_packet_keeps_its_figures():
    f = rc.figures(_rec(220382))            # issue 216, strip A
    assert f.pairs and f.usable, f.why_not
    assert f.expected_samples == 1620 * 136 - 2


def test_the_engines_own_count_pairs_exactly():
    assert rc.figures(_rec(1540 * 136 - 2, readings=1540)).usable


def test_a_stream_of_another_reading_count_is_refused():
    exp = 1620 * 136 - 2
    for wrong in (exp + 136, exp - 136,            # one reading more / fewer
                  exp - 136 + 64,                  # one fewer, plus a packet
                  exp + 136 - 64,                  # one more, less a packet
                  exp + 128,                       # two extra packets
                  exp // 2):                       # half the stream
        f = rc.figures(_rec(wrong))
        assert not f.pairs and f.why_not == "not_paired", wrong


def test_the_bound_is_under_half_a_reading_at_other_clocks():
    # at i1Profiler's 139 clocks its "- 5" is 3 off, its "+64" case 61 off:
    # both paired; 70 off (more than half of 139) is not
    exp = 570 * 139 - 2
    assert rc.figures(_rec(570 * 139 - 5, 570, 139)).pairs
    assert rc.figures(_rec(570 * 139 - 5 + 64, 570, 139)).pairs
    assert not rc.figures(_rec(exp + 70, 570, 139)).pairs
    assert rc.figures(_rec(exp + 69, 570, 139)).pairs


def test_the_diagnostics_file_records_the_rule():
    assert rc.THRESHOLDS["i1pro2_pair_offset"] == 2
    assert rc.THRESHOLDS["i1pro2_pair_tolerance_readings"] == 0.5
    assert "i1pro2_pair_tolerance" not in rc.THRESHOLDS
    from workflow import ruler_diagnostics as rd
    assert rd.REVISION == 4
