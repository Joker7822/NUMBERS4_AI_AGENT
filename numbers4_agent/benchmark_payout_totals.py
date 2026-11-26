"""Read-only full-history comparison with the original full-list payout means."""
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from . import payout_research as p
from .historical_archive import load_archive
from .finance import load_payouts
from .box_finance import load_box_payouts


class ReferenceTotals(list):
    def estimates(self):
        return p.prior_estimates(self)


def main():
    root = Path(".")
    rows, _ = load_archive(root)
    straight, _ = load_payouts(root, rows)
    box, _ = load_box_payouts(root, rows)
    start = perf_counter()
    optimized = p.evaluate(rows, straight, box)
    optimized_seconds = perf_counter() - start
    with patch.object(p, "PayoutTotals", ReferenceTotals):
        start = perf_counter()
        reference = p.evaluate(rows, straight, box)
        reference_seconds = perf_counter() - start
    if optimized != reference:
        raise ValueError("payout report differs from original full-list estimates")
    print(f"Payout full archive: exact equality; rounds={len(rows)}; "
          f"original={reference_seconds:.6f}s; optimized={optimized_seconds:.6f}s; "
          f"speedup={reference_seconds/max(optimized_seconds, 1e-9):.3f}x")


if __name__ == "__main__":
    main()
