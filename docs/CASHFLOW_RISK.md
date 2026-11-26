# Historical cash-flow risk audit

```sh
python -m numbers4_agent.cashflow_risk --root .
```

Read-only recomputation of the existing prior-only replay and its validated
straight and BOX financial reconstructions, plus their uniform references.
The no-purchase scenario is included to show that zero spending has undefined
recovery (not 100%). No additional ticket strategy is evaluated.

The audit reports final hypothetical net, gross recovery and net ROI,
minimum settled cumulative net, maximum peak-to-trough settled drawdown,
maximum pre-settlement cash shortfall and consecutive losing purchased tickets.
The pre-settlement shortfall accounts for paying each ticket before any prize;
it is not an advisable starting bankroll. Skipped invalid BOX entries neither
extend nor reset a streak of losing purchased tickets.

Past realized cash flow is not a future maximum loss estimate. All data are
secondary history; no actual purchases, authorized bankroll, positive expected
value or prospective predictive skill are established. The research decision
remains SKIP. No production data, model, forecast or purchase code is changed.
