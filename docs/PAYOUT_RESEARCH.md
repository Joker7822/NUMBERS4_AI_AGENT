# Payout forecast research

Run the read-only historical comparison:

```sh
python -m numbers4_agent.cli --root . audit-payouts
```

The existing archive and payout loaders validate provenance and alignment first.
The fixed comparison is expanding mean, rolling 30 and rolling 100 observations,
all using a common 100-observation warmup per group. STRAIGHT uses all draws.
BOX uses separate permutation-pattern groups and excludes four-equal outcomes.
All five conditional estimates are formed before consuming the current outcome.
The actual winning pattern only determines which BOX estimate is scored.

Metrics are MAE, RMSE and signed mean error in yen; each model uses the same
observations. Round 5000 separates the development and late historical cohorts.
The latter is already observed, not an independent prospective holdout.
There is no automatic model selection, number-level recommendation, estimated
positive EV, promotion or purchase authorization. Results are not official
payout verification. No external dependencies or data writes.

Next: independent prospective assessment and publisher-authorized evidence.
A lower payout error alone is not proof of a higher return rate.
