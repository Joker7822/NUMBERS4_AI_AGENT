"""Numbers4 command line entry point. No network writes or lottery purchases."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import sys

from .dashboard import snapshot, write_dashboard
from .evaluation import graded_predictions, walk_forward
from .ledger import issue
from .models import ranked_candidates
from .sources import corroborated_draws, record_observation, reconcile
from .official_fetch import sync
from .proof import run as research_proof, save_report


def print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="numbers4-agent", description="Numbers4 research and read-only audit toolkit")
    ap.add_argument("--root", type=Path, default=Path("."), help="repository root")
    sub = ap.add_subparsers(dest="command", required=True)
    observe = sub.add_parser("observe", help="append a human-entered official-source observation")
    observe.add_argument("--round", type=int, required=True)
    observe.add_argument("--draw-date", required=True)
    observe.add_argument("--number", required=True, help="exactly four digits including leading zero")
    observe.add_argument("--source", choices=["mizuhobank", "takarakuji_official"], required=True)
    observe.add_argument("--url", required=True, help="actual official page containing this draw")
    recommend = sub.add_parser("recommend", help="produce non-issued research candidates")
    recommend.add_argument("--target-round", type=int, required=True)
    recommend.add_argument("--mode", choices=["straight", "box", "set"], default="straight")
    recommend.add_argument("--method", choices=["uniform", "positional"], default="positional")
    recommend.add_argument("--count", type=int, default=5)
    publish = sub.add_parser("issue", help="append five explicit advice-only, pre-deadline forecasts")
    publish.add_argument("--target-round", type=int, required=True)
    publish.add_argument("--draw-date", required=True)
    publish.add_argument("--deadline-jst", required=True, help="draw day and no later than 18:30 +09:00")
    publish.add_argument("--mode", choices=["straight", "box", "set"], required=True)
    publish.add_argument("--numbers", nargs=5, required=True, metavar="NNNN")
    publish.add_argument("--model-version", required=True)
    publish.add_argument("--ack-advice-only", action="store_true", required=True)
    sub.add_parser("audit", help="print snapshot and source conflicts")
    sub.add_parser("evaluate", help="grade existing pre-issued tickets against two entered sources")
    sub.add_parser("backtest", help="historical walk-forward, never prospective confirmation")
    fetch = sub.add_parser("fetch-official", help="retrieve bank/Rakuten and verify identical published draw rows")
    fetch.add_argument("--months-back", type=int, default=12)
    proof = sub.add_parser("prove", help="run preregistration-limited exploratory historical test")
    proof.add_argument("--output", type=Path, default=Path("research/historical_backtest.json"))
    dash = sub.add_parser("build-dashboard", help="produce public snapshot without changing evidence")
    dash.add_argument("--output", type=Path, default=Path("docs/data/status.json"))
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "observe":
            result = record_observation(root, round_number=args.round, draw_date=args.draw_date,
                                        number=args.number, source=args.source, url=args.url)
        elif args.command == "recommend":
            result = ranked_candidates(corroborated_draws(root), args.target_round,
                                       mode=args.mode, count=args.count, method=args.method)
        elif args.command == "issue":
            result = issue(root, target_round=args.target_round, draw_date=args.draw_date,
                           mode=args.mode, numbers=args.numbers,
                           deadline_jst=args.deadline_jst, model_version=args.model_version)
        elif args.command == "evaluate":
            result = {"status": "two_source_manual_entry_only", "graded": graded_predictions(root)}
        elif args.command == "backtest":
            result = walk_forward(root)
        elif args.command == "fetch-official":
            result = sync(root, months_back=args.months_back)
        elif args.command == "prove":
            result = save_report(root, root / args.output)
        elif args.command == "build-dashboard":
            result = write_dashboard(root, args.output)
        else:
            result = snapshot(root)
            result["source_rounds"] = reconcile(root)
        print_json(result)
        return 0
    except (ValueError, TypeError, KeyError) as exc:
        print(f"検証エラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
