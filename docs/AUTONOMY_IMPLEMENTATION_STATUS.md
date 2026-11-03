# Automation implementation status (2026-11-03 JST)

## Trusted data-to-promotion path

1. `official-results.yml` fetches the bank and Rakuten read-only, including a bounded Chromium fallback for JavaScript-rendered bank pages. Bank-only or Rakuten-only outcomes are never accepted as verified draws.
2. `online-learning.yml` performs historical research and `predictive-research.yml` searches Crossref by default, with optional Brave web search when `BRAVE_SEARCH_API_KEY` is configured. It evaluates allowed method hypotheses, not arbitrary downloaded code.
3. `verified-autolearn.yml` runs automatically at the declared UTC cron times, witnesses pre-draw shadow forecasts and assesses genuine verified future outcomes. Production pointer changes only when the fixed prospective 500-draw and e-value gates pass. It does not purchase tickets.
4. `recovery-watchdog.yml` retries failed GitHub workflows **once**, then creates a deduplicated human-review incident. A code change or new forecasting method requires its own tested PR and preregistration.

## Known blockers that are *not* silently bypassed

- A successful source-fetch workflow may still have zero matched bank/Rakuten records. Review the `numbers4-official-source-diagnostics` artifact and the source-incident issue. Browser rendering may still fail if a site changes its structure.
- `research/approved_draw_schedule.json` is empty. Without explicit date/round evidence from an official schedule, no shadow prediction is frozen. Weekday inference is insufficient.
- Brave full-web search is unavailable until the user configures `BRAVE_SEARCH_API_KEY` in GitHub Actions secrets. Crossref research still works without it.
- Searches and historical replays are not demonstrations of future predictive skill. An untrusted paper's Python code is never auto-executed or auto-promoted.
- Temporary job failures can be retried automatically, but arbitrary source-code self-repair and deployment without code review are **not** implemented. This is an explicit safety limit, not proof of complete autonomy.

## Verify a deployment

- Run repository CI on the pull request before merge.
- On merge, inspect the next scheduled official-fetch workflow artifact for bank rows, Rakuten rows, errors and independently matched rows.
- Inspect `research/prospective_auto_learning_status.json`: `eligible_prospective_draws`, `production_champion`, `automatic_promotion_executed` are the authoritative outcomes.
- Confirm no issued forecasts were rewritten and that `data/auto_verified_draws.jsonl` only contains matching official evidence.
