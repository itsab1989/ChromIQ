# These partial files are spent — do not merge them

`it.partial.json`, `nl.partial.json`, `no.partial.json`, `sv.partial.json`.

They look like ~1,200 entries of head start each. They are not.

Measured 2026-08-07:

| | |
|---|---|
| entries per file | ~1,203 |
| **already identical to the live catalogue** | 907–1,068 |
| keys that no longer exist (stale) | 120 |

They were merged long ago. What is left is the difference — and where they
differ, **the live catalogue is usually the better text**, because it has had
fixes the staging copies never received.

The clearest example: staging still says `Scheidingsvakken` where the Dutch
terminology sweep settled on `Scheidingslijnen`. Re-merging would silently undo
that sweep, and the same risk applies to the `chart` → `kaart` and
`patch` → `meetveld` corrections made on 2026-08-07.

**If you are translating,** the placeholders in `data/i18n/<code>.json` are the
work — an entry whose value equals its key. `scripts/i18n_verify_batch.py`
reports what is left per language and checks a finished batch.

These files are kept only because deleting a user's files is not ours to decide.
They can go whenever Sebastian confirms.
