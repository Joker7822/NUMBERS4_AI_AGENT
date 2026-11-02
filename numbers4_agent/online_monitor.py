"""Production-source monitoring: bounded discovery, semantic rule guards, no model promotion.

This is deliberately an allowlisted search/verification registry rather than
untrusted web-wide autonomous scraping. Source reachability != draw attestation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
import re
import unicodedata

JST = timezone(timedelta(hours=9))
VERSION = "numbers4-operational-official-rule-monitor-v2"
SOURCES = (
    ("official_purchase_rules",
     "https://www.takarakuji-official.jp/kuji/numbers/numbers4/howto.html",
     "rule", ("product", "ticket_200", "straight", "box", "box_order")),
    ("official_game_rules",
     "https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/",
     "rule", ("product", "straight", "box", "box_order", "all_same_box_invalid", "straight_probability")),
    ("mizuho_rules",
     "https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html",
     "rule", ("product", "ticket_200", "straight", "box", "box_order", "all_same_box_invalid")),
    ("mizuho_results_page",
     "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html",
     "result_page", ("product", "draw_heading")),
    ("scoring_method_reference",
     "https://stat.uw.edu/research/tech-reports/strictly-proper-scoring-rules-prediction-and-estimation",
     "research_reference", ()),
)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.ignored += 1
        if not self.ignored and tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.fragments.append(alt)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.ignored = max(0, self.ignored-1)

    def handle_data(self, text):
        if not self.ignored:
            self.fragments.append(text)


def _semantic_text(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not (100 <= len(raw) <= 1_600_000):
        raise ValueError("invalid official page size")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("official HTML was not UTF-8") from exc
    parsed = _Text()
    parsed.feed(decoded)
    cleaned = unicodedata.normalize("NFKC", " ".join(parsed.fragments))
    return re.sub(r"\s+", "", cleaned)


def _markers(text: str) -> dict[str, bool]:
    return {
        "product": "ナンバーズ4" in text or "NUMBERS4" in text.upper(),
        "ticket_200": bool(re.search(r"(?:1口|1口あたり)200円", text)),
        "straight": "ストレート" in text,
        "box": "ボックス" in text,
        "box_order": (
            "順序は問わない" in text or "順序を問わない" in text or
            "並び順は不問" in text or "順番は問わない" in text or
            "並びの順序は問わない" in text or
            "並びの順序を問わない" in text
        ),
        "all_same_box_invalid": (
            "1111" in text and
            ("できません" in text or "できない" in text or "申込不可" in text)
        ),
        "straight_probability": bool(re.search(r"1/10,?000", text)),
        "draw_heading": "抽せん数字" in text or "抽せん番号" in text,
    }


def audit(now: datetime | None = None, *, fetch=None) -> dict:
    """Find trusted online sources, verify explicit game-rule anchors.

    Unavailable source => unverified, content contradiction => manual review.
    An HTML URL responding 200 does not verify any winning draw or money.
    """
    if fetch is None:
        from .secondary_feed import read_url
        fetch = read_url
    now = (now or datetime.now(JST)).astimezone(JST)
    records = []
    checked = 0
    drift = 0
    unknown = 0
    result_page = "unavailable_or_unverified"
    for name, url, kind, required in SOURCES:
        row = {"topic": name, "url": url, "category": kind, "status": "pending"}
        try:
            raw = fetch(url)
            if not isinstance(raw, bytes):
                raise ValueError("source response is not bytes")
            row["response_sha256"] = sha256(raw).hexdigest()
            row["size_bytes"] = len(raw)
            if kind == "research_reference":
                row["status"] = "reference_reachable_not_scientifically_reviewed"
            else:
                text = _semantic_text(raw)
                found = _markers(text)
                missing = [key for key in required if not found[key]]
                row["required_markers"] = list(required)
                row["missing_markers"] = missing
                if kind == "rule":
                    if missing:
                        row["status"] = "rule_change_requires_review"
                        drift += 1
                    else:
                        row["status"] = "rule_anchors_consistent"
                        checked += 1
                elif missing:
                    row["status"] = "result_page_structure_changed_not_verified"
                    result_page = row["status"]
                else:
                    row["status"] = "result_page_reachable_draws_not_verified"
                    result_page = row["status"]
        except (ConnectionError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
            row["status"] = "unavailable_or_unverified"
            row["reason"] = type(exc).__name__
            if kind == "result_page":
                result_page = row["status"]
        if kind == "rule" and row["status"] == "unavailable_or_unverified":
            unknown += 1
        records.append(row)
    status = ("rule_change_requires_review" if drift else
              "degraded_official_rules_unverified" if unknown else
              "official_rule_anchors_consistent")
    return {
        "version": VERSION,
        "checked_at_jst": now.isoformat(timespec="seconds"),
        "status": status,
        "required_rule_sources": 3,
        "rule_sources_consistent": checked,
        "rule_sources_unavailable": unknown,
        "rule_sources_changed": drift,
        "result_page_status": result_page,
        "topics": records,
        "automatic_lottery_rules_adoption": False,
        "official_draw_result_verified_by_this_audit": False,
        "official_payouts_verified_by_this_audit": False,
        "paper_relevance_confirmed": False,
        "automatic_external_code_execution": False,
        "lottery_predictive_improvement_confirmed": False,
        "model_auto_promotion_authorized": False,
        "inspection_policy": "allowlisted_official_sources_rule_anchor_checks_only",
        "interpretation": "Fixed trusted online search registry, semantically checked rule markers. A successful site read is not official draw or payout verification.",
    }
