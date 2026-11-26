# Retrospective score stability audit

Run: python -m numbers4_agent.stability_audit --root .

The four fixed historical replay score series (selected policy and three
positional experts) are recomputed from validated secondary history. Three
cohorts (all, through round 5000, after round 5000) and two circular moving
block lengths (20 and 100) yield 24 within-audit comparisons. Common block
starts across score series retain pairing; the last partial block keeps the
sample size unchanged. Default: 10,000 replications, seed 20261126.
The 95% percentile ranges and wider nominal Bonferroni percentile ranges
are descriptive sensitivity measures, not validated confidence coverage
or formal hypothesis tests. Block lengths are research choices, not fitted
dependence models. The three cohorts overlap. The adjustment only concerns
these 24 comparisons; it does not correct past adaptive hypothesis searches,
model-family selection, or repeated reuse of the same history. No p-values,
model rankings, forecasts or purchase recommendations are emitted.
The existing 500-draw prospective gate, official corroboration, production
model and full historical replay remain unchanged. CI uploads the separate
research-only artifact and checks the safety invariants. No tracked data writes.
