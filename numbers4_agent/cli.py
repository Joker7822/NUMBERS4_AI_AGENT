"""Numbers4 command line entry point. No network writes or lottery purchases."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import os
import sys

from .dashboard import snapshot, write_dashboard
from .evaluation import graded_predictions, walk_forward
from .ledger import issue
from .models import ranked_candidates
from .sources import corroborated_draws, record_observation, reconcile
from .official_fetch import sync
from .proof import run as research_proof, save_report
from .historical_archive import archive_summary
from .online_learning import write_replay
from .straight_challenger import write_report as write_straight_benchmark
from .open_web import inspect_urls as inspect_public_web
from .research_discovery import (
    DEFAULT_TOPICS, write_research_cycle as write_predictive_research_cycle,
)
from .secondary_feed import refresh as refresh_secondary, audit_related
from .automatic_learning import (freeze_shadow, assess as assess_prospective,
                                  apply_policy, recommend_champion)
from .publication_witness import verify_and_record as verify_shadow_publication
from .evolution import cycle as evolve_research_cycle


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
    recommend.add_argument("--method", choices=["champion", "uniform", "positional"], default="champion")
    recommend.add_argument("--count", type=int, default=1)
    publish = sub.add_parser("issue", help="append one explicit advice-only, pre-deadline forecast")
    publish.add_argument("--target-round", type=int, required=True)
    publish.add_argument("--draw-date", required=True)
    publish.add_argument("--deadline-jst", required=True, help="draw day and no later than 18:30 +09:00")
    publish.add_argument("--mode", choices=["straight", "box", "set"], required=True)
    publish.add_argument("--numbers", nargs=1, required=True, metavar="NNNN")
    publish.add_argument("--model-version", required=True)
    publish.add_argument("--ack-advice-only", action="store_true", required=True)
    frozen = sub.add_parser("freeze-shadow",
                            help="freeze one-bank-verified-history, draw-day shadow model forecast")
    frozen.add_argument("--target-round", type=int, required=True)
    frozen.add_argument("--draw-date", required=True)
    sub.add_parser("witness-shadow", help="verify public GitHub push-run predraw publication receipts")
    sub.add_parser("assess-challengers", help="audit true prospective official-only candidate metrics")
    sub.add_parser("auto-promote", help="advance or rollback champion ONLY if rigorous gates pass")
    sub.add_parser("audit", help="print snapshot and source conflicts")
    sub.add_parser("evaluate", help="grade existing pre-issued tickets against two entered sources")
    sub.add_parser("backtest", help="historical walk-forward, never prospective confirmation")
    sub.add_parser("audit-history", help="validate full secondary archive from round 1 (not officially verified)")
    sub.add_parser("replay-history", help="research-only predict each draw starting from round 2")
    challenger = sub.add_parser("benchmark-straight",
                               help="research-only rolling STRAIGHT models against a uniform reference")
    challenger.add_argument("--split-round", type=int, default=5000,
                            help="last historical development round (default 5000)")
    challenger.add_argument("--output", type=Path, default=Path("research/straight_challenger_report.json"),
                            help="exploratory report only; never overwrite issuance ledgers")
    sub.add_parser("refresh-secondary", help="append only corroborated two-mirror secondary history")
    sub.add_parser("audit-references", help="read-only check allowlisted online official rules and statistical methods")
    evolution = sub.add_parser("evolve-research",
        help="search method hypotheses, evolve safe learners and FULL-replay draw 2 onward")
    evolution.add_argument("--query", action="append", default=[],
                           help="optional research query (repeat without a fixed query-count cap)")
    evolution.add_argument("--split-round", type=int, default=5000,
                           help="reused historical development split, never prospective proof")
    evolution.add_argument("--search-requests", type=int, default=8,
                           help="bounded API request budget per generation (1-100); no lifetime source cap")
    evolution.add_argument("--offline", action="store_true",
                           help="explicit offline fallback (no online retrieval) for testing")
    scientific = sub.add_parser("research-cycle",
        help="search for predictive-method research and benchmark frozen STRAIGHT challengers")
    scientific.add_argument("--query", action="append", default=[],
                            help="research question; repeat for multiple searches (max 8)")
    scientific.add_argument("--output", type=Path,
                            default=Path("research/predictive_research_cycle.json"),
                            help="research-only evidence report")
    research_web = sub.add_parser("research-web",
                                  help="inspect opt-in public HTTPS pages beyond the official source allowlist")
    research_web.add_argument("--url", action="append", default=[],
                              help="one public HTTPS page, repeat for additional pages")
    research_web.add_argument("--url-file", type=Path,
                              help="optional UTF-8 file of one HTTPS URL per line; no fixed total")
    research_web.add_argument("--start-index", type=int, default=0,
                              help="resume URL list from zero-based index")
    research_web.add_argument("--batch-size", type=int, default=25,
                              help="pages to process this run; next_start_index continues the remaining list")
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
            if args.method == "champion":
                if args.count != 1 or args.mode != "straight":
                    raise ValueError("automatic champion is a one-ticket STRAIGHT-only model")
                result = recommend_champion(root, args.target_round)
            else:
                result = ranked_candidates(corroborated_draws(root), args.target_round,
                                           mode=args.mode, count=args.count, method=args.method)
        elif args.command == "freeze-shadow":
            result = freeze_shadow(root, target_round=args.target_round,
                                   draw_date=args.draw_date)
        elif args.command == "witness-shadow":
            result = verify_shadow_publication(root)
        elif args.command == "assess-challengers":
            result = assess_prospective(root)
        elif args.command == "auto-promote":
            result = apply_policy(root)
        elif args.command == "issue":
            result = issue(root, target_round=args.target_round, draw_date=args.draw_date,
                           mode=args.mode, numbers=args.numbers,
                           deadline_jst=args.deadline_jst, model_version=args.model_version)
        elif args.command == "evaluate":
            result = {"status": "two_source_manual_entry_only", "graded": graded_predictions(root)}
        elif args.command == "backtest":
            result = walk_forward(root)
        elif args.command == "audit-history":
            result = archive_summary(root)
        elif args.command == "replay-history":
            result = write_replay(root)
        elif args.command == "benchmark-straight":
            result = write_straight_benchmark(root, output=args.output,
                                              split_round=args.split_round)
        elif args.command == "refresh-secondary":
            result = refresh_secondary(root)
            report=root/"research/online_source_audit.json"
            report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        elif args.command == "audit-references":
            result = audit_related()
            report=root/"research/online_reference_audit.json"
            report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        elif args.command == "evolve-research":
            result = evolve_research_cycle(
                root, queries=args.query or None,
                offline=args.offline, split_round=args.split_round,
                search_request_budget=args.search_requests,
                brave_api_key=os.environ.get("BRAVE_SEARCH_API_KEY") or None,
            )
        elif args.command == "research-cycle":
            result = write_predictive_research_cycle(
                root, args.output,
                queries=args.query or list(DEFAULT_TOPICS),
                brave_api_key=os.environ.get("BRAVE_SEARCH_API_KEY") or None,
            )
        elif args.command == "research-web":
            urls = list(args.url)
            if args.url_file is not None:
                urls.extend(line.strip() for line in
                            args.url_file.read_text(encoding="utf-8-sig").splitlines()
                            if line.strip() and not line.lstrip().startswith("#"))
            result = inspect_public_web(urls, start_index=args.start_index,
                                        batch_size=args.batch_size)
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
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"検証エラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
