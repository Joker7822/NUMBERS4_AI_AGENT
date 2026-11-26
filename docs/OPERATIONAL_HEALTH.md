# Operational health diagnostics

The official-results main workflow writes a bounded summary to
research/official_ingestion_status.json before generating its dashboard. It
publishes counts, timestamps, denied publisher names and the verified ledger
hash, not arbitrary response bodies. Missing, malformed, future-dated or
ledger-mismatched diagnostics are not success. The 96-hour freshness threshold
includes weekends and is distinct from the 150-minute dashboard generation
threshold. A matched batch is not a guarantee that all recent draws are present.

The dashboard and daily audit distinguish the latest ingestion attempt, today's
reviewed schedule, verified training history, publication witnesses and the
prospective sample count. A missing schedule is not proof that a draw was
scheduled. All states are advisory only; no model promotion, purchasing,
calendar approval or extra publisher requests are authorized by the monitor.
The existing official source and prospective gates remain unchanged.
