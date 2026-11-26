# Research storage and PR validation efficiency

Source identity is (provider, id). Existing append-only source history is
preserved. A staged collection now carries the content hashes of its source
ledger and pagination checkpoint; persistence rejects stale inputs, duplicate
staged identities, and inconsistent source counts. An identical checkpoint is
not rewritten. No historical records are deleted or compressed. This is not
a filesystem transaction or multiprocess lock: the main research workflow
serializes its own jobs, and a crash between ledger append and checkpoint
write still requires a fresh collection.

The read-only official-source PR job runs the full test suite, including
injected publisher-response fixtures, plus the local historical proof command.
It no longer contacts the live publishers on each PR. Main-only production
ingestion retains its existing schedule, strict corroboration gates, access
denial handling and diagnostics. CI success is not live source availability.
No changes to full-history research replay, acquisition budgets, or model
and purchase authorization.

Avoided checkpoint rewrites do not imply lower Git object storage for
identical contents, which Git already deduplicates. Actions cost savings are
not asserted without billing data.
