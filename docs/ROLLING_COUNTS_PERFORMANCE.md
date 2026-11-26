# Exact rolling count performance audit

The historical replay and ensemble audit previously recounted every digit of
each trailing window on each evaluation. A 60+250+1000 draw window requires
4*(60+250+1000)=5240 historical digit observations per fully warmed iteration.
The new rolling counter updates four incoming and four outgoing digits per
window (24 count changes over three windows) and evaluates the same 120
probabilities. This is a reduction of repeated counting, not a claim of
equivalent end-to-end speedup.

The reference positional_probs function remains unchanged. Tests compare exact
floating-point probabilities, all replay output rows and ensemble reports,
including window eviction, leading zeros and invalid inputs. The CI benchmark
recomputes both full reports on the entire validated archive and requires exact
equality. Timings are informational; no fragile runtime threshold. Run:

```sh
python -m numbers4_agent.benchmark_rolling_counts
```

No changes to model formulas, weights, selection logic, data provenance,
prospective policy, actual purchases or issuance. The benchmark is read-only.
