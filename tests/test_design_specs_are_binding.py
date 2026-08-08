"""The design specifications are binding, and must stay findable.

Knut, #130, 2026-08-06: *"These must always be consulted on changing code so
that behaviour defined is not violated. And if faults are found that do not
match with the specification is must be reviewed and approved."*

A rule nobody can find is not a rule. These tests hold two things in place: the
documents CLAUDE.md points at all exist, and each of them carries the notice
saying it is binding. Both are the kind of thing that rots silently — a file
renamed, a banner lost to a rewrite — and neither would ever fail a normal test.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "design"

BINDING = [
    "unified_measurement_management.md",
    "per_run_description.md",
    "measurement_exit_strategy.md",
    "per_target_settings.md",
    "per_target_settings_test_plan.md",
    "measurement_window_sounds.md",
    "tool_availability.md",
    "verification_printing_and_target.md",
]


def test_every_binding_specification_exists():
    missing = [n for n in BINDING if not (DESIGN / n).is_file()]
    assert not missing, f"named in CLAUDE.md but not on disk: {missing}"


def test_each_one_says_it_is_binding():
    """Someone opening the file alone must learn the rule from the file."""
    silent = [n for n in BINDING
              if "These specifications are binding" not in (DESIGN / n).read_text()]
    assert not silent, f"no binding notice: {silent}"


def test_claude_md_names_them_all():
    """CLAUDE.md is what an agent reads first, so the list lives there too."""
    text = (ROOT / "CLAUDE.md").read_text()
    assert "The design specifications are binding" in text
    unnamed = [n for n in BINDING if n not in text]
    assert not unnamed, f"not listed in CLAUDE.md: {unnamed}"


def test_the_docs_do_not_link_to_each_other_by_a_dead_path():
    """A cross-reference that 404s is how a binding document stops being read."""
    dead = []
    for name in BINDING:
        doc = DESIGN / name
        for target in re.findall(r"\]\((?!https?:)([^)#]+\.md)[^)]*\)", doc.read_text()):
            if not (doc.parent / target).resolve().is_file():
                dead.append(f"{name} → {target}")
    assert not dead, f"dead cross-references: {dead}"


# ---- only CONFIRMED behaviour belongs in a specification -----------------
#
# Knut, 2026-08-08: *"only the behavior that you confirm as correct, after bugs
# are confirmed fixed, should be written into the design specification.
# Otherwise the specification looses its value with lots of trash Claude thinks
# is correct behavior."*
#
# The gate is a HUMAN's confirmation, not the assistant's own on-screen run: a
# driver proves what the app does, not that what it does is what it should do.
# The assistant had already written a "✅ Confirmed behaviour" section on its own
# authority the same day, which is exactly the failure mode named above — so
# this is enforced rather than promised.

#: Who is allowed to confirm behaviour into a specification.
CONFIRMERS = ("Knut", "Sebastian", "Basti")

_CONFIRMED_HEADING = re.compile(r"^#{2,4}\s*(?:[^\w\s]\s*)?Confirmed behaviour",
                                re.M | re.I)
_AWAITING = re.compile(r"Awaiting confirmation", re.I)


def _sections(text: str) -> "list[tuple[str, str]]":
    """(heading, body) for every heading in the document."""
    parts = re.split(r"^(#{2,4} .*)$", text, flags=re.M)
    return list(zip(parts[1::2], parts[2::2]))


def test_a_confirmed_behaviour_section_names_who_confirmed_it():
    """"Confirmed" without a name is the assistant confirming itself."""
    offenders = []
    for name in BINDING:
        for heading, body in _sections((DESIGN / name).read_text()):
            if not _CONFIRMED_HEADING.match(heading.lstrip("#").strip()) \
                    and not _CONFIRMED_HEADING.search(heading):
                continue
            if _AWAITING.search(heading):
                continue          # explicitly marked as not yet confirmed
            if not re.search(r"\*\*Confirmed by:\*\*\s*(" +
                             "|".join(CONFIRMERS) + r")", body):
                offenders.append(f"{name}: {heading.strip()}")
    assert not offenders, (
        "a section headed 'Confirmed behaviour' must carry "
        "'**Confirmed by:** <Knut|Sebastian|Basti>, <date>' — otherwise it is "
        "the assistant marking its own homework:\n  " + "\n  ".join(offenders))


def test_an_awaiting_section_does_not_claim_to_be_confirmed():
    """The two states must stay tellable apart at a glance."""
    offenders = []
    for name in BINDING:
        for heading, body in _sections((DESIGN / name).read_text()):
            if not _AWAITING.search(heading):
                continue
            if "**Confirmed by:** *nobody yet.*" not in body:
                offenders.append(f"{name}: {heading.strip()}")
    assert not offenders, (
        "a section awaiting confirmation must say so in its body, in as many "
        "words ('**Confirmed by:** *nobody yet.*'), so it cannot be skimmed as "
        "settled:\n  " + "\n  ".join(offenders))
