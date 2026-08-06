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
