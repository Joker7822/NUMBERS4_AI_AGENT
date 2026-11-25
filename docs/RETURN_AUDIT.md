# Historical return audit (research only)

Run from the repository root:

```sh
python -m numbers4_agent.cli --root . audit-returns --simulations 10000 --seed 20261126
```

The command is read-only, uses the existing provenance-checked secondary history and
payout loaders, and prints JSON. It neither issues forecasts nor writes a purchase
ledger, changes the champion, or approves an official result.

- Gross recovery = payout / cost × 100. Net ROI = gross recovery minus 100 points.
- STRAIGHT: one independent uniformly chosen ordered string per draw.
- BOX: one independent uniformly chosen **valid ordered** string per draw (9,990
  choices). A four-equal winning result has no BOX payout. This differs from
  the existing retrospective regrading that skips invalid straight candidates.
- Analytic expected payout and conditional variance are computed from historical
  payouts; deterministic Monte Carlo provides a descriptive outcome distribution,
  not a prospective confidence interval or evidence of skill.
- The output is historical only: no model is promoted and the decision is SKIP.
  Zero spending does not imply 100% recovery.

## Remaining work

Official source matching and approved draw schedule need genuine evidence.
Do not relax the existing official verification or prospective publication gates.
Next steps: collect independent pre-draw evidence, preregister scoring and
calibration tests, assess data availability for a payout model without leakage,
and verify against genuinely new observations. No automatic purchases.
