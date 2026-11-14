"""The ruler check's figures and its one question (workflow/ruler_check.py),
on streams synthesised from the i1Pro 2 recordings' figures (R1/R3: a full
strip 318-353 steps, partial swipes 224 and 262, no ruler 0 changes; 16
patches at 17.3 steps, so a patch span of about 277 steps)."""
from workflow import ruler_check as rc

CLOCK = 36e-6
GRAY = (0, 2, 3, 1)          # +1 per step in ArgyllCMS's table


def stream(steps: int, readings: int, clocks: int = 136, *, start_frac=0.1,
           end_frac=0.9, sign=-1, extra=0, illegal=0, gen="i1pro2",
           ended="short"):
    """A record whose ruler moves *steps* steps evenly between the two
    fractions of the scan."""
    samples = readings * clocks - (5 if gen == "i1pro2" else 0) + extra
    a, b = int(samples * start_frac), int(samples * end_frac)
    changes = []
    last = 0
    code_i = 0
    for k in range(steps):
        at = a + (b - a) * k // max(1, steps)
        code_i = (code_i + (1 if sign > 0 else -1)) % 4
        changes += [at - last, GRAY[code_i]]
        last = at
    for _ in range(illegal):
        code_i = (code_i + 2) % 4
        changes += [3, GRAY[code_i]]
    return {"instrument": gen, "ended": ended, "samples": samples,
            "readings": readings, "clocks": clocks, "clock_s": CLOCK,
            "first": GRAY[0], "changes": changes}


def test_a_full_strip_is_usable_and_measured():
    f = rc.figures(stream(318, 570))
    assert f.usable and f.seen and f.pairs
    assert f.travel_steps == 318 and f.net_steps == -318 and f.sign == -1
    assert f.mean_steps_s > 0 and f.peak_steps_s >= f.mean_steps_s * 0.9


def test_the_direction_follows_the_sign():
    assert rc.figures(stream(300, 570, sign=+1)).sign == +1


def test_no_ruler_is_not_usable_and_says_why():
    f = rc.figures(stream(0, 460))
    assert not f.usable and f.why_not == "no_ruler"
    f = rc.figures(stream(8, 460, gen="i1pro3"))   # jctay's no-ruler scan
    assert f.why_not == "no_ruler"


def test_a_count_that_does_not_pair_falls_back():
    assert rc.figures(stream(318, 570, extra=64)).usable      # one packet: kept
    f = rc.figures(stream(318, 570, extra=-500))
    assert not f.usable and f.why_not == "not_paired"


def test_illegal_changes_fall_back():
    f = rc.figures(stream(318, 570, illegal=1))
    assert not f.usable and f.why_not == "garbled"


def test_a_read_that_did_not_end_normally_falls_back():
    for ended in ("timeout", "error", "not_started", ""):
        assert rc.figures(stream(318, 570, ended=ended)).why_not == "read"
    assert rc.figures(stream(318, 570, ended="cancelled")).usable


def test_garbage_never_raises():
    f = rc.figures({"changes": ["x"], "samples": "?"})
    assert not f.usable and f.why_not == "read"


def test_the_question_on_the_recordings_figures():
    # span 277 steps known from today's cut in this session
    span = 16 * 17.3
    for full in (318, 337, 345, 353):
        assert not rc.not_covered(rc.figures(stream(full, 600)), span)
    assert rc.not_covered(rc.figures(stream(224, 300)), span)
    assert not rc.not_covered(rc.figures(stream(262, 550)), span)  # a miss


def test_the_question_needs_usable_data_and_a_span():
    assert not rc.not_covered(rc.figures(stream(100, 300)), None)
    assert not rc.not_covered(rc.figures(stream(100, 300, illegal=2)), 277)


def test_an_unknown_step_size_makes_the_span_shorter_never_longer():
    # chart patch span 240 mm; i1Pro 2 upper bound 1.10 mm per step
    s = rc.span_steps("i1pro2", 240.0)
    assert abs(s - 240.0 / 1.10) < 1e-9
    assert abs(rc.span_steps("i1pro2", 240.0, derived_mm_per_step=0.8)
               - 240.0 / 0.88) < 1e-9
    assert rc.span_steps("i1pro2", None, session_span_steps=277.0) == 277.0
    assert rc.span_steps("i1pro2", None) is None


def test_i1pro3_pairs_by_argylls_own_trim():
    assert rc.figures(stream(270, 600, gen="i1pro3", ended="argyll")).usable
    f = rc.figures(stream(270, 600, gen="i1pro3", extra=-3 * 136,
                          ended="argyll"))
    assert not f.usable


def test_thresholds_are_marked_provisional():
    assert rc.THRESHOLDS["provisional"] is True
