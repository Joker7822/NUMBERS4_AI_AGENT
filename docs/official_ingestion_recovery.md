# Official Numbers4 ingestion: HTTP 403 recovery

Last investigated: 2026-11-13 (JST).

## Confirmed incident

On GitHub-hosted `ubuntu-latest`, the Mizuho Numbers4 monthly HTML template
contains no usable draw rows. Chromium also receives HTTP 403 from the bank
host. Rakuten still publishes rows, but these **must not** be labeled
independently verified without matching bank observations.

The verification gate intentionally remains fail-closed: no bank source means
zero verified official rows, regardless of historical secondary mirror counts.
The nightly workflow now exits nonzero if zero bank/Rakuten matches are obtained,
after writing source diagnostics and an incident.

## Restore an authorized bank source

1. Verify that automated requests are permitted for the bank publisher and
   obtain an authorized access route (or a publisher-supported structured feed).
   Do not bypass access controls or scrape through an unapproved third-party
   mirror.
2. If an authorized machine can access the **original bank URL** and its
   explicit round/date/four-digit results, register it as a repo-scoped GitHub
   Actions runner. Keep it patched, isolated from untrusted pull requests and
   limited to this repository.
3. Assign a dedicated runner label such as `numbers4-official`; in GitHub
   **Settings → Secrets and variables → Actions → Variables**, set the repository
   variable `NUMBERS4_OFFICIAL_RUNNER` to that exact label.
   Without the variable the workflow uses `ubuntu-latest`.
4. Manually run **Numbers4 Official-Primary Results and Historical Evidence**
   from GitHub Actions, or inspect the next scheduled run.
5. Inspect the `numbers4-official-source-diagnostics` artifact. A successful
   data recovery requires `bank_rows > 0`,
   `publisher_matched_rows > 0`, and records in
   `data/auto_verified_draws.jsonl` only for exactly agreeing bank and
   independently published Rakuten rows. The run should not be considered
   recovered just because the workflow job started or the dashboard deployed.
6. If HTTP 403 persists on the authorized runner, request sanctioned
   machine-readable access from the publisher. No code-only workaround is
   demonstrated as safe or functional.

## Safety invariants

- Source URLs must remain approved HTTPS publisher domains.
- Both publications must independently supply matching round, draw date and
  four-digit winning number. A shared third-party mirror cannot replace bank
  evidence.
- A browser page or a successful HTTP response without explicit matching
  results must not increment verified draws.
- Preserve immutable forecast and observation ledgers.
- Never infer predictive skill from retrospective results or authorize purchases.
