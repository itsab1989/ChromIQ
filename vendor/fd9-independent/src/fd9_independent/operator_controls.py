# SPDX-License-Identifier: GPL-3.0-or-later
"""Development-test input checks; never issue instrument commands."""
from pathlib import Path
import uuid


def fresh_output(requested):
    requested=Path(requested)
    requested.parent.mkdir(parents=True,exist_ok=True)
    candidate=requested
    while True:
        try:candidate.mkdir(exist_ok=False);return candidate
        except FileExistsError:candidate=requested.with_name(requested.name+'-'+uuid.uuid4().hex[:12])


def stage_control(text,expected):
    value=text.strip().lower()
    if value=='abort':raise RuntimeError('Operator stopped staged test')
    return value==expected
