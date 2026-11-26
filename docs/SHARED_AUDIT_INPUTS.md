# Shared validated historical inputs

The integrated audit previously parsed and validated the archive five times
and each payout CSV three times (11 validated CSV loads). It now runs the
same strict loaders once per CSV (3 total) and passes the local results to
internal report builders. The public individual audit functions still load
and validate their own inputs. There is no persistent or cross-run cache.

SHA-256 fingerprints of the three CSVs and three provenance files are checked
at the beginning and end of the integrated call. Missing or changed inputs
abort the report. This is detection of observed changes, not a filesystem
transaction or protection against a malicious writer who restores prior bytes.
All existing provenance and cross-report checks remain. Extra raw file reads
for fingerprints must not be counted as eliminated disk I/O.

CI compares complete reports with the independently loaded path, including
the fixed simulation seed. Timings are informational, not a guaranteed
speedup. No changes to production issuance, purchase or promotion authority.

Run: python -m numbers4_agent.benchmark_shared_audit
