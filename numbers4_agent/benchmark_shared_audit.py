"""Full archive comparison of shared inputs versus independent validated loads."""
from pathlib import Path
from time import perf_counter

from . import integrated_audit as m


def main():
    root = Path(".")
    start = perf_counter()
    optimized = m.audit(root, simulations=10000, seed=20261126)
    optimized_seconds = perf_counter() - start
    start = perf_counter()
    reference = m.integrate({
        "returns": m.return_audit.audit(root, simulations=10000, seed=20261126),
        "payouts": m.payout_research.audit(root),
        "box": m.box_calibration.audit(root),
        "ensemble": m.ensemble_audit.audit(root),
        "cashflow": m.cashflow_risk.audit(root),
    }, m.assess_prospective(root))
    reference_seconds = perf_counter() - start
    if optimized != reference:
        raise ValueError("shared audit differs from independently validated reports")
    print(f"Shared audit: exact equality; last_round={optimized['last_round']}; "
          f"independent={reference_seconds:.6f}s; shared={optimized_seconds:.6f}s; "
          f"speedup={reference_seconds/max(optimized_seconds, 1e-9):.3f}x")


if __name__ == "__main__":
    main()
