# ChromIQ 4.0.0 — release notes (DRAFT)

**The maintained text now lives in `CHANGELOG.md` as the `## v4.0.0-beta.1`
entry** (Sebastian, 2026-08-11: the consolidated overview IS the beta.1
changelog, marked as covering everything since v3.14.7). Keep it current
there — one source, no drift.

At **4.0.0 final**:

1. Copy the beta.1 entry (minus its "later betas add their own entries"
   note) as the `## v4.0.0` entry, folding in whatever the later 4.0.0
   betas added.
2. Re-derive the counts — `git tag -l 'v3.14.8-beta.*' 'v4.0.0-beta.*' |
   wc -l` and `git rev-list --count v3.14.7..HEAD` — they have gone stale
   in this file twice. Never publish a number nobody re-derived.
3. The stable tag needs Sebastian's explicit go-ahead; betas are cut on
   the assistant's initiative, a stable release never is.
