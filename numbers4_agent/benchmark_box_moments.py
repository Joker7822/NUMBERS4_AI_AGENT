"""Compare all BOX audit outputs to full-vector reference; informational timings."""
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from . import box_calibration as box
from .historical_archive import load_archive

ABS_TOLERANCE = 1e-12


class ReferenceMoments:
    def __init__(self):
        self.counts = [0] * len(box.SIGNATURES)

    def observe(self, actual):
        self.counts[actual] += 1

    def evaluate(self, actual, alpha):
        q = box.posterior(self.counts, alpha)
        return (*box.score(q, actual), box.pattern_probs(q))


def max_difference(actual, expected):
    """Require identical keys, types, counts, flags and non-numeric metadata."""
    if type(actual) is not type(expected):
        raise ValueError("BOX report type mismatch")
    if isinstance(actual, dict):
        if actual.keys() != expected.keys():
            raise ValueError("BOX report keys mismatch")
        return max((max_difference(actual[k], expected[k]) for k in actual), default=0.0)
    if isinstance(actual, (tuple, list)):
        if len(actual) != len(expected):
            raise ValueError("BOX report sequence mismatch")
        return max((max_difference(a, b) for a, b in zip(actual, expected)), default=0.0)
    if type(actual) is float:
        difference = abs(actual - expected)
        if not difference <= ABS_TOLERANCE:
            raise ValueError(f"BOX numeric mismatch: {actual} vs {expected}")
        return difference
    if actual != expected:
        raise ValueError("BOX report metadata mismatch")
    return 0.0


def main():
    rows, _ = load_archive(Path("."))
    if len(rows) <= box.WARMUP:
        raise ValueError("validated historical archive required")
    start = perf_counter()
    optimized = box.evaluate(rows)
    optimized_seconds = perf_counter() - start
    with patch.object(box, "PosteriorMoments", ReferenceMoments):
        start = perf_counter()
        reference = box.evaluate(rows)
        reference_seconds = perf_counter() - start
    error = max_difference(optimized, reference)
    print(f"BOX full archive: rounds={len(rows)}; max_abs_difference={error:.3g}; "
          f"original={reference_seconds:.6f}s; optimized={optimized_seconds:.6f}s; "
          f"speedup={reference_seconds/max(optimized_seconds, 1e-9):.3f}x")


if __name__ == "__main__":
    main()
