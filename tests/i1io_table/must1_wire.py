"""4.3.47 MUST-1 (independent safety review, 18 Nov 2026): the one difference the job's wire may
have from tester 0.6.0's (test support).

Before a computed move the job reads the arm once more when the reading the move would be judged
from was taken before the person's last answer (or before the motors last let the arm go):
``TableJob._read_again_if_asked``. That is ONE recorded position query, ``;p025``, and nothing
else. Tester 0.6.0 did not send it, so its frozen captures lack it. The wire tests compare the
job's lines with exactly those queries taken out, and check each one taken out:

* it is ``;p025``;
* the job itself recorded it as such a reading (``job.reads_after_question``);
* the line after it is the computed ``;m0`` it guards, or nothing (the step stopped there).

A case that puts a fault or a cancel at tester line *i* puts it at the job's line for the same
tester line (``job_index``), using the extra readings of the fault-free sitting the case is
built on (pinned below and checked by ``test_4347_must1_wire_difference.py``).
"""
from __future__ import annotations

P0 = ";p025"

#: the extra readings (0-based job line numbers) of the fault-free sittings the fault and cancel
#: cases are built on; both are the check move to mark 3 (D2) after its first-visit question
EXTRA_IN_ALIGN_SITTING = (44,)           # job_wire_cases, "A warm d1 d2 f"
EXTRA_IN_STRIP_E2_SITTING = (46,)        # job_strip_wire_cases, "S C1 D1 D2 E2 F"
EXTRA_IN_READING_D3_SITTING = ()         # job_reading_wire_cases, "D C1 D1 D3 F" (a free arm:
#                                          the row's own stillness pair is read after the
#                                          questions already)


#: the two creep sittings (job_wire_cases "C ..."): the check move to mark 3 (the tests' copy of
#: tester 0.6.0's D2, tester_d2) after its first-visit question. 4.3.50: the creep's first move
#: has no extra reading any more: "Go forward carefully, my hands are away" is asked in the
#: alignment, before the creep reads the arm, and no first-visit question follows it
EXTRA_IN_CREEP_SITTINGS = {"S2 684.0": (59,), "R1 401.6": (63,)}


def rng_neutral_at(sim, indices) -> None:
    """The simulator's position readings carry a random jitter of +-1 unit, drawn per reading.
    An extra reading would shift every later draw, and the creep (which steps on from where the
    arm reads) would then send other, equally valid, numbers than the frozen capture: noise of
    the simulator, not a change of the job. At the job lines *indices* (the extra readings, pinned
    above and checked against ``job.reads_after_question``) the reading leaves the random state
    as it found it, so every later reading answers as it did for tester 0.6.0."""
    want = set(indices)
    orig = sim._c_execute

    def execute(line, cid, a, fault):
        if cid == "p0" and len(sim.received) - 1 in want:
            state = sim._rng.getstate()
            try:
                return orig(line, cid, a, fault)
            finally:
                sim._rng.setstate(state)
        return orig(line, cid, a, fault)
    sim._c_execute = execute


def job_index(i: int, extra) -> int:
    """The job's line number for tester line *i*, the extra readings *extra* counted in."""
    j = i
    for e in sorted(extra):
        if e <= j:
            j += 1
    return j


def without_must1(got, job):
    """The job's lines with its MUST-1 readings taken out (each checked)."""
    extra = list(job.reads_after_question)
    assert len(set(extra)) == len(extra), extra
    for k in extra:
        assert 0 <= k < len(got), (k, len(got))
        assert got[k] == P0, (k, got[k - 2:k + 2])
        if k + 1 < len(got):
            assert got[k + 1].startswith(";m0"), (k, got[k - 2:k + 3])
    drop = set(extra)
    return [ln for n, ln in enumerate(got) if n not in drop]


#: 2026-11-21, THE VENDOR'S WAY HOME (geometry.homing_detour): the tester 0.6.0 captures home
#: straight from everywhere; the job first drives to the home line from the far side and the back
#: strip (i1Profiler's recordings N3, R1). The wire tests compare the rest with the capture.
def without_detours(got):
    """(got without the detour lines, the lines taken out): each m0 at speed 200 and the one p0
    after it (its arrival; the simulator arrives exactly, so it is not read again), and the
    second reading of a free arm right before the first of them."""
    out, taken = list(got), []
    for _ in range(2):                                  # at most two detour moves
        k = next((i for i, ln in enumerate(out) if ln.startswith(";m0") and ln[11:15] == "00c8"),
                 None)
        if k is None:
            break
        first = k - 1 if not taken and out[k - 1] == out[k - 2] == ";p025" else k
        assert out[k + 1] == ";p025", out[k:k + 2]
        taken += out[first:k + 2]
        out = out[:first] + out[k + 2:]
    return out, taken
