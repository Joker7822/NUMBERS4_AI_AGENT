# Rolling payout totals performance

All five payout groups retain exact integer expanding totals and two bounded
windows of 30 and 100 observations. The same means are formed for every
group before the current draw is consumed. The warmup, chronological cohorts,
MAE/RMSE/bias calculations and research-only authority remain unchanged.
The original prior_estimates function is retained for regression comparisons.

The cumulative mean update is O(1) rather than O(n) in the prior observation
count. The per-group retained payout history is at most 130 deque entries
(30+100); counts and totals are integers. Evaluation events are still retained
for reporting. This does not change the size of committed research ledgers.

Four tests check exact means, bounded windows, invalid inputs and all group
reports. CI compares the complete historical report with the original full-list
implementation and reports informational timing. No persistent cache is used.
The scheduled research generation explicitly promises full replay, so it is not
skipped when data are unchanged. Existing append-only research evidence and
public files are not pruned.

Run: python -m numbers4_agent.benchmark_payout_totals
