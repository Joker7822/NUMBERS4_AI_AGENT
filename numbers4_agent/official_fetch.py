"""Numbers4 result fetcher: official bank is primary, Rakuten is corroboration.

Uncorroborated historical observations are research-only and NEVER enter the
preissued-forecast scorer. Network I/O is bounded; URLs are hard-coded hosts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .rules import four_digits
from .sources import JST, iso_date
from .store import append, file_hash, load

BANK = "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html"
RAKUTEN = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/"
AUTO_LEDGER = "auto_verified_draws.jsonl"
RAW_RESEARCH = "historical_unverified.json"
MAX_BYTES = 2_000_000
MIN_PUBLISH_HOUR = 18


class ResultFetchError(ValueError):
    pass


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words: list[str] = []
        self.table: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._ignored += 1
        if not self._ignored and tag == "tr":
            self._row = []
        if not self._ignored and tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._ignored = max(0, self._ignored - 1)
            return
        if self._ignored:
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join(" ".join(self._cell).split()))
            self._cell = None
        if tag == "tr" and self._row is not None:
            if self._row:
                self.table.append(self._row)
            self._row = None

    def handle_data(self, data):
        if not self._ignored and data.strip():
            stripped = " ".join(data.split())
            self.words.append(stripped)
            if self._cell is not None:
                self._cell.append(stripped)


def _text(html: str) -> VisibleText:
    parsed = VisibleText()
    parsed.feed(html)
    return parsed


def _normalize_date(text: str) -> str:
    value = re.fullmatch(r"\s*(\d{4})\s*[年/-]\s*(\d{1,2})\s*[月/-]\s*(\d{1,2})\s*日?\s*", text)
    if not value:
        raise ResultFetchError("unrecognized official draw date")
    result = f"{int(value[1]):04d}-{int(value[2]):02d}-{int(value[3]):02d}"
    iso_date(result)
    return result


def _put(rows: dict[int, dict], rnd: int, draw_date: str, number: str):
    if not (1 <= rnd <= 100_000):
        raise ResultFetchError("invalid draw round")
    four_digits(number)
    date = _normalize_date(draw_date)
    row = {"round": rnd, "draw_date": date, "winning_number": number}
    if rnd in rows and rows[rnd] != row:
        raise ResultFetchError(f"conflicting draw {rnd} within a single publisher")
    rows[rnd] = row


def parse_rakuten(html: str) -> list[dict]:
    """Only explicit Japanese Numbers4 draw labels, never arbitrary 4-digit text."""
    page = _text(html)
    if not re.search("ナンバーズ4|NUMBERS4", " ".join(page.words), re.I):
        raise ResultFetchError("Rakuten response is not a Numbers4 result page")
    stream = " ".join(page.words)
    # Some versions render separate tables; others use mobile text cards.
    pattern = re.compile(
        r"回号\s*第\s*(\d{1,6})\s*回\s*抽せん日\s*"
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})\s*当せん番号\s*([0-9]{4})(?![0-9])"
    )
    found: dict[int, dict] = {}
    for m in pattern.finditer(stream):
        _put(found, int(m[1]), m[2], m[3])
    if not found:
        raise ResultFetchError("Rakuten response lacks structured Numbers4 draw rows")
    return [found[k] for k in sorted(found)]


def parse_mizuhobank(html: str) -> list[dict]:
    """Official main monthly view + legacy 20-round bank backnumber pages."""
    page = _text(html)
    stream = " ".join(page.words)
    if not re.search("ナンバーズ4|ナンバーズ４", stream):
        raise ResultFetchError("bank page is not a Numbers4 result page")
    found: dict[int, dict] = {}
    # Main bank page: labeled round/date/winning number cards.
    pattern = re.compile(
        r"回別\s*第\s*(\d{1,6})\s*回\s*抽せん日\s*"
        r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)\s*"
        r"抽せん数字\s*([0-9]{4})(?![0-9])"
    )
    for m in pattern.finditer(stream):
        _put(found, int(m[1]), m[2], m[3])
    # Older bank pages are true table rows: [round, date, Numbers3, Numbers4].
    for cells in page.table:
        if len(cells) != 4:
            continue
        rnd = re.fullmatch(r"第\s*(\d{1,6})\s*回", cells[0])
        if rnd and re.fullmatch(r"[0-9]{3}", cells[2]) and re.fullmatch(r"[0-9]{4}", cells[3]):
            _put(found, int(rnd[1]), cells[1], cells[3])
    if not found:
        raise ResultFetchError("bank page had no usable official Numbers4 results (possibly JS-only)")
    return [found[k] for k in sorted(found)]


def _download(url: str, host: str, *, opener=None) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ResultFetchError("unapproved official results URL")
    request = urllib.request.Request(url, headers={"User-Agent": "NUMBERS4_AI_AGENT/0.2 (+read-only-verification)", "Accept": "text/html"})
    fetch = opener or urllib.request.urlopen
    try:
        with fetch(request, timeout=16) as response:
            actual_url = response.geturl()
            actual = urlparse(actual_url)
            if actual.scheme != "https" or actual.hostname != host:
                raise ResultFetchError("redirected outside approved source host")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ResultFetchError("publisher HTML exceeded size limit")
            declared = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        # Keep the status visible in Actions; a 403 is not an empty results table.
        raise ResultFetchError(f"publisher rejected request: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ResultFetchError(f"publisher network fetch failed: {type(exc).__name__}") from exc
    try:
        return body.decode(declared), hashlib.sha256(body).hexdigest()
    except (UnicodeDecodeError, LookupError) as exc:
        raise ResultFetchError("publisher HTML encoding not recognized") from exc


def month_pairs(now: datetime, months_back: int) -> list[tuple[int, int]]:
    if not 1 <= months_back <= 12:
        raise ValueError("months_back must be within 1-12")
    local = now.astimezone(JST)
    pairs = []
    for offset in range(months_back):
        position = local.year * 12 + local.month - 1 - offset
        pairs.append((position // 12, position % 12 + 1))
    return pairs


def _render_bank_page(url: str) -> tuple[str, str]:
    """Read JS-rendered bank results from the SAME approved bank host.

    This is a fallback for pages whose raw HTML only contains an empty result
    template. A browser success by itself is never an official verification:
    the parser must recover explicit rows and Rakuten must agree independently.
    """
    host = "www.mizuhobank.co.jp"
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ResultFetchError("unapproved bank browser URL")
    try:
        from playwright.sync_api import (
            sync_playwright, Error as PlaywrightError,
            TimeoutError as PlaywrightTimeoutError,
        )
    except ImportError as exc:
        raise ResultFetchError("bank browser unavailable: install playwright and chromium") from exc

    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            try:
                page = browser.new_page(locale="ja-JP")
                response = page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                if response is not None and response.status in (401, 403, 429):
                    raise ResultFetchError(
                        f"bank browser request rejected: HTTP {response.status}"
                    )
                try:
                    # Do not treat a merely loaded empty template as evidence.
                    page.wait_for_function(
                        r"() => /第\s*\d+\s*回/.test(document.body?.innerText || '')",
                        timeout=12_000,
                    )
                except PlaywrightTimeoutError:
                    pass  # The ordinary parser will reject a still-empty page.
                actual = urlparse(page.url)
                if actual.scheme != "https" or actual.hostname != host:
                    raise ResultFetchError("bank browser navigated outside approved host")
                rendered = page.content()
                # WAF challenge pages may return HTTP 200 and the original URL.
                # Never accept their numeric reference IDs as lottery evidence.
                visible = " ".join(_text(rendered).words)
                if re.search(r"access denied|request blocked|bot detection|"
                             r"アクセス(が|を)?(拒否|制限)", visible, re.I):
                    raise ResultFetchError("bank browser served a blocked-access page")
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise ResultFetchError(f"bank browser render failed: {type(exc).__name__}") from exc
    payload = rendered.encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise ResultFetchError("bank browser DOM exceeded size limit")
    return rendered, hashlib.sha256(payload).hexdigest()


def publisher_month(url: str, host: str, parser, *, opener=None,
                    bank_browser_fallback: bool = False) -> tuple[list[dict], str]:
    try:
        text, sha = _download(url, host, opener=opener)
        return parser(text), sha
    except ResultFetchError as raw_error:
        # A WAF HTTP rejection must also attempt the permitted browser fallback.
        # Only the original bank HTTPS host is allowed; a recovered HTML page
        # still needs explicit draw rows and independent Rakuten agreement.
        if not bank_browser_fallback or host != "www.mizuhobank.co.jp":
            raise
        try:
            rendered, rendered_sha = _render_bank_page(url)
            return parser(rendered), rendered_sha
        except ResultFetchError as render_error:
            raise ResultFetchError(
                f"bank raw request rejected ({raw_error}); browser fallback rejected ({render_error})"
            ) from render_error


def sync(root: Path, *, now: datetime | None = None, months_back: int = 12,
         opener=None, record_unverified: bool = True,
         bank_browser_fallback: bool = False) -> dict:
    """Fetch every month independently; commit only dual-publisher matching rows.

    Neither a single source nor two copies from the same publisher counts as
    verified. Missing bank data are *explicitly* reported, never invented.
    """
    now = (now or datetime.now(JST)).astimezone(JST)
    bank: dict[int, dict] = {}
    rakuten: dict[int, dict] = {}
    errors = []
    for year, month in month_pairs(now, months_back):
        link_b = f"{BANK}?year={year}&month={month}"
        link_r = f"{RAKUTEN}{year}{month:02d}/"
        for name, url, host, parse, target in (
            ("mizuhobank", link_b, "www.mizuhobank.co.jp", parse_mizuhobank, bank),
            ("rakuten", link_r, "takarakuji.rakuten.co.jp", parse_rakuten, rakuten),
        ):
            try:
                observations, content_sha = publisher_month(
                    url, host, parse, opener=opener,
                    bank_browser_fallback=bank_browser_fallback and name == "mizuhobank",
                )
                for row in observations:
                    if row["draw_date"][:7] != f"{year:04d}-{month:02d}":
                        raise ResultFetchError("publisher month disagrees with request")
                    if row["round"] in target and any(target[row["round"]][key] != row[key] for key in ("round", "draw_date", "winning_number")):
                        raise ResultFetchError("conflicting publisher row")
                    target[row["round"]] = {**row, "url": url, "sha256": content_sha}
            except (ResultFetchError, ValueError) as exc:
                errors.append({"publisher": name, "month": f"{year:04d}-{month:02d}", "reason": str(exc)})
    path = root / "data" / AUTO_LEDGER
    previous = {r["round"]: r for r in load(path)}
    common = sorted(bank.keys() & rakuten.keys())
    conflicts = []
    new = 0
    for rnd in common:
        b, r = bank[rnd], rakuten[rnd]
        if (b["draw_date"], b["winning_number"]) != (r["draw_date"], r["winning_number"]):
            conflicts.append(rnd)
    if conflicts:
        raise ResultFetchError("publisher disagreement: " + ",".join(map(str, conflicts)))
    # A correction conflicting with any pre-existing verification must abort
    # the whole batch, not commit part of the new official history.
    for rnd in common:
        b = bank[rnd]
        if rnd in previous and (previous[rnd]["draw_date"], previous[rnd]["winning_number"]) != (b["draw_date"], b["winning_number"]):
            raise ResultFetchError("publisher corrected an already recorded outcome; requires human review")
        publication_time = datetime.fromisoformat(b["draw_date"] + "T18:30:00+09:00")
        if now < publication_time:
            raise ResultFetchError("official draw date has not passed release window")
    # Validate the research sidecar BEFORE writing a single verified draw.
    # An invalid or revised cache must never leave a partially accepted batch.
    cache = None
    if record_unverified and rakuten:
        dest = root / "research" / RAW_RESEARCH
        old = json.loads(dest.read_text(encoding="utf-8")) if dest.is_file() else None
        if old is not None and (old.get("version") != "numbers4-research-source-v1" or old.get("verified_official") is not False):
            raise ResultFetchError("existing research source cache has invalid provenance")
        merged = {r["round"]: r for r in old["rows"]} if old else {}
        for rnd, row in rakuten.items():
            if rnd in merged and any(merged[rnd][k] != row[k] for k in ("round", "draw_date", "winning_number")):
                raise ResultFetchError("historical publisher revised an existing draw; manual review required")
            merged[rnd] = row
        source_rows = [merged[k] for k in sorted(merged)]
        cache = {
            "version": "numbers4-research-source-v1", "verified_official": False,
            "publisher": "rakuten_lottery_publication_only", "fetched_at_jst": now.isoformat(timespec="seconds"),
            "rows": source_rows, "rows_count": len(source_rows),
            "official_confirmed_count_in_this_sync": len(common) - len(conflicts),
            "warning": "These single-publisher historical rows cannot grade issued forecasts or prove predictive skill",
        }
    for rnd in common:
        b, r = bank[rnd], rakuten[rnd]
        if rnd in previous:
            continue
        record = {
            "round": rnd, "draw_date": b["draw_date"], "winning_number": b["winning_number"],
            "verified_at_jst": now.isoformat(timespec="seconds"),
            "verification": "bank_primary_rakuten_publication_match",
            "bank_url": b["url"], "bank_response_sha256": b["sha256"],
            "corroborator_url": r["url"], "corroborator_response_sha256": r["sha256"],
            "not_a_digital_signature": True,
        }
        append(path, record)
        new += 1
    # A sidecar is NEVER a verified official result; it exists solely to run
    # explicitly labeled descriptive historical experiments, not to grade bets.
    if cache is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "version": "numbers4-official-fetch-v1", "checked_at_jst": now.isoformat(timespec="seconds"),
        "status": "publisher_disagreement" if conflicts else
                  "verified" if common else "blocked_no_bank_verified_results",
        "bank_rows": len(bank), "rakuten_rows": len(rakuten),
        "publisher_matched_rows": len(common) - len(conflicts),
        "new_verified_rows": new, "conflicted_rounds": conflicts,
        "bank_missing_coverage": sorted(set(rakuten) - set(bank)),
        "errors": errors,
        "bank_browser_fallback_enabled": bank_browser_fallback,
        "bank_errors": [error for error in errors if error["publisher"] == "mizuhobank"],
        "rakuten_errors": [error for error in errors if error["publisher"] == "rakuten"],
        "ledger_sha256": file_hash(path), "automatic_model_promotion": False,
        "verified_claim_only_on_matching_records": True,
    }
