# Ensemble score audit (research only)

```sh
python -m numbers4_agent.ensemble_audit --root .
```

Read-only comparison using the three existing positional experts (60, 250,
1000 draws) and the fair uniform reference. Fixed weights: equal experts,
50% uniform plus equal experts, 90% uniform plus equal experts, and 100%
uniform. These research specifications are not preregistered prospective tests.
Every model uses the same 1000-draw warmup. No result-dependent weight tuning.

The mixture is a weighted sum of complete joint distributions, not a product
of averaged position marginals. Exact Brier scoring uses pairwise products of
four marginal inner products, avoiding enumeration of 10,000 outcomes per draw.
The current outcome is added to the training windows only after scoring.
Positive log/Brier edges indicate improved probabilistic scores versus uniform.

Round 5000 separates previously observed historical cohorts. A small positive
edge in one cohort is not an independently verified forecast advantage.
No model selection, ticket rankings, expected-value claims, model promotion or
purchase authorization. The command does not alter existing CLI, data or reports.
