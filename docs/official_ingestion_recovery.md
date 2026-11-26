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

## 2026-11-26 follow-up

The public Mizuho Numbers4 results page still exposes a table template without
explicit draw rows in the retrieved HTML:
https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html

The bank's historical index is public, but its current-year template alone does
not establish a working structured feed:
https://www.mizuhobank.co.jp/takarakuji/check/numbers/backnumber/index.html

A successful PR workflow is a code validation result, not live data recovery.
The dedicated authorized runner is restricted to non-PR main-branch jobs;
PR validation runs on a GitHub-hosted runner with read-only token permissions.
A malformed publisher/month response is rejected atomically.

No publisher permission, access to a configured authorized runner, or fresh
dual-source matches were established by this code change. Do not populate the
approved schedule from generic weekday rules or promote secondary observations.

## 2026-11-26 access-denial handling

The main-branch run https://github.com/Joker7822/NUMBERS4_AI_AGENT/actions/runs/45748239749
reported 0 bank rows, 255 Rakuten rows and 0 matched rows. The bank raw HTML
contained no usable result rows; browser requests returned HTTP 403 for all
12 requested months (2025-12 through 2026-11).

Explicit HTTP 401, 403 or 429, or a detected browser access-block page, now
halts requests to that publisher for the remainder of the sync. The browser
fallback is for ordinary empty templates, not for retrying explicit denial.
The other publisher remains independent and its unverified observations remain
research-only. Diagnostics distinguish denied requests from months not requested.
This reduces unnecessary requests, but is not a restoration of bank access.
A publisher-authorized route and actual dual-source matches remain required.
