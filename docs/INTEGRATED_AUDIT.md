# Integrated research evidence audit

Run:

```sh
python -m numbers4_agent.cli --root . audit-integrated
```

This consolidation incorporates the changes proposed in PRs #29 through #34,
resolving overlapping CLI changes. Review this combined PR instead of merging
all component PRs separately. Existing individual module commands remain available.

The command runs five historical audits and the existing read-only prospective
assessment, and prints JSON. It rejects mismatched archive endpoints and
provenance hashes, mismatched payout provenance, missing reports, unexpected
versions, and unsafe authorization claims. It does not write data or promote a
champion. The reports intentionally keep their distinct sampling conventions
and warmup periods; do not pool them into a single ROI.

CI runs the integrated audit on the repository archive and retains the report
as a research-only artifact. No dashboard publication, automatic purchases,
or production policy changes are introduced. The live official-source access
blocker and independent prospective evidence remain unresolved.
