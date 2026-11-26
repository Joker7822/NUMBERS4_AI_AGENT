# BOX probability and calibration research

Run from the repository root:

```sh
python -m numbers4_agent.box_calibration --root .
```

The full distribution includes 715 unordered signatures, including the ten
four-equal outcomes that cannot be purchased as BOX. There are 705 purchasable
signatures. The fair reference is the distribution induced by 10,000 equally
probable ordered strings; it is NOT a uniform distribution over signatures.
Each signature has mass equal to its permutation multiplicity / 10,000.

Compare three fixed Dirichlet prior strengths (100, 1000, 10000), all centred
on the fair reference. Score the same draws, after a common 100-draw warmup,
before incorporating each actual result. Positive log-score and Brier edges
indicate improvement over the reference. Pattern-level mean predicted
probability versus observed frequency is descriptive calibration, not proof of
calibration for individual signatures.

Round 5000 separates development and already observed later history. The report
does not select a champion, rank ticket candidates, estimate positive expected
value or authorize purchases. It uses validated secondary history only.
No production files or CLI integration are changed; the module command avoids
overlapping the pending CLI changes in PRs #29 and #31.
