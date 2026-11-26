"""Full archive exact-equivalence benchmark. No timing threshold or data writes."""
from collections import deque
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from numbers4_agent import ensemble_audit, online_learning
from numbers4_agent.historical_archive import load_archive


class ReferenceWindow:
    def __init__(self, length):
        self.values = deque(maxlen=length)

    def append(self, number):
        self.values.append(number)

    def probabilities(self, alpha):
        return online_learning.positional_probs(self.values, alpha)


def check(module, function, rows):
    start = perf_counter()
    optimized = function(rows)
    optimized_seconds = perf_counter() - start
    with patch.object(module, "RollingPositionCounts", ReferenceWindow):
        start = perf_counter()
        reference = function(rows)
        reference_seconds = perf_counter() - start
    if optimized != reference:
        raise ValueError(f"{module.__name__}: optimized report differs from full rescan")
    print(f"{module.__name__}: exact equality; rounds={len(rows)}; "
          f"original={reference_seconds:.6f}s; optimized={optimized_seconds:.6f}s; "
          f"speedup={reference_seconds / max(optimized_seconds, 1e-9):.3f}x")


def main():
    rows, _ = load_archive(Path("."))
    if len(rows) < 2:
        raise ValueError("validated historical archive required")
    check(online_learning, online_learning.replay, rows)
    check(ensemble_audit, ensemble_audit.evaluate, rows)


if __name__ == "__main__":
    main()
