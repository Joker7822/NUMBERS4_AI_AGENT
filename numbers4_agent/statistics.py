"""Descriptive probability checks for past-only Numbers4 research.

These calculations assume independent, exactly uniform future draws.  They
do not establish that a post-hoc model has genuine forecasting skill.
"""
from __future__ import annotations

from math import exp, lgamma, log, log1p


def binomial_right_tail(trials: int, hits: int, probability: float) -> float:
    """P[X >= hits] for X ~ Binomial(trials, probability).

    Summing from the observed number of hits avoids cancellation from
    subtracting a nearly-one lower tail. No external statistical library
    is needed. This is descriptive only when the protocol was not frozen
    prospectively.
    """
    if (type(trials) is not int or type(hits) is not int or
            trials < 0 or not 0 <= hits <= trials):
        raise ValueError("trials and hits must be valid nonnegative integers")
    if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
        raise ValueError("probability must be between zero and one")
    if hits == 0:
        return 1.0
    if probability == 0:
        return 0.0
    if probability == 1:
        return 1.0
    log_first = (lgamma(trials + 1) - lgamma(hits + 1) -
                 lgamma(trials - hits + 1) +
                 hits * log(probability) +
                 (trials - hits) * log1p(-probability))
    term = exp(log_first)
    total = term
    odds = probability / (1 - probability)
    for k in range(hits, trials):
        term *= (trials - k) / (k + 1) * odds
        total += term
        if term == 0.0:
            break
    return max(0.0, min(1.0, total))
