"""Opt-in research retrieval of arbitrary PUBLIC HTTPS pages.

This module is deliberately separate from official draw verification, payouts,
model promotion, and forecast publication. Untrusted page content is DATA,
never executable code, verified evidence, or an instruction to the agent.

Unlike the fixed official-monitor registry, public research hosts are not
allowlisted. To prevent SSRF (including DNS rebinding), all resolved addresses
must be global and the HTTPS connection is pinned to a validated IP.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
import http.client
import ipaddress
import re
import socket
import ssl
from urllib.parse import urlsplit, urlunsplit

JST = timezone(timedelta(hours=9))
VERSION = "numbers4-open-web-research-v1"
USER_AGENT = "NUMBERS4_AI_AGENT/0.6 (opt-in, read-only research)"
MAX_BODY_BYTES = 4_000_000
MAX_PAGES_PER_INVOCATION = 50
EXCERPT_CHARS = 5000
TIMEOUT_SECONDS = 10
_ALLOWED_APPLICATION_TYPES = {
    "application/json", "application/xml", "application/rss+xml",
    "application/atom+xml", "application/csv",
}
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".test",
                     ".invalid", ".example", ".onion", ".arpa")
_SECRET_QUERY_KEYS = ("key", "token", "secret", "password", "auth",
                      "credential", "signature", "session")


def validate_public_url(url: str) -> tuple[str, str, str]:
    """Return HTTPS URL, DNS host and safe-to-publish URL without query.

    An arbitrary public domain can be inspected, but localhost, IP literals,
    credentials, non-standard ports, private networks and other schemes cannot.
    """
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise ValueError("invalid URL length or type")
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError("URL contains control characters")
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("only public HTTPS pages may be fetched")
    if "@" in parsed.netloc or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError("URL credentials, fragments, and custom ports are forbidden")
    host = parsed.hostname
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("malformed DNS name") from exc
    if (host.startswith(".") or host.endswith(".") or
            len(host) > 253 or "." not in host or
            any(not _HOST_LABEL.fullmatch(part) for part in host.split(".")) or
            host.endswith(_BLOCKED_SUFFIXES)):
        raise ValueError("non-public DNS host is forbidden")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("direct IP literals are forbidden")
    # Do not accidentally send API credentials or signed URLs to the research
    # collector, where metadata could otherwise be printed to a log.
    for pair in parsed.query.split("&"):
        key = pair.split("=", 1)[0].lower()
        if any(sensitive in key for sensitive in _SECRET_QUERY_KEYS):
            raise ValueError("credential-style URL query is forbidden")
    path = parsed.path or "/"
    full = urlunsplit(("https", host, path, parsed.query, ""))
    display = urlunsplit(("https", host, path, "", ""))
    return full, host, display


def public_addresses(host: str, *, resolver=None) -> list[str]:
    """Resolve host once. Reject the entire domain if ANY address is private."""
    resolver = resolver or socket.getaddrinfo
    try:
        entries = resolver(host, 443, type=socket.SOCK_STREAM)
    except (OSError, ValueError) as exc:
        raise ValueError("DNS lookup failed") from exc
    addresses: list[str] = []
    for record in entries:
        try:
            address = ipaddress.ip_address(record[4][0])
        except (IndexError, ValueError, TypeError) as exc:
            raise ValueError("malformed DNS record") from exc
        if not address.is_global:
            raise ValueError("DNS resolved to a private or reserved IP")
        value = str(address)
        if value not in addresses:
            addresses.append(value)
    if not addresses:
        raise ValueError("no public DNS addresses")
    return addresses


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Use a validated IP for the socket and original host for TLS SNI."""
    def __init__(self, host: str, address: str, timeout: int):
        super().__init__(host, port=443, timeout=timeout,
                         context=ssl.create_default_context())
        self.pinned_address = address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self.pinned_address, 443), self.timeout,
            source_address=self.source_address)
        self.sock = self._context.wrap_socket(self.sock,
                                              server_hostname=self.host)


def fetch_public_page(url: str, *, resolver=None, connection_factory=None) -> tuple[bytes, str]:
    """Fetch a SINGLE bounded public URL: no redirects, scripts or proxies."""
    validated, host, _ = validate_public_url(url)
    ips = public_addresses(host, resolver=resolver)
    parsed = urlsplit(validated)
    target = parsed.path + (("?" + parsed.query) if parsed.query else "")
    factory = connection_factory or _PinnedHTTPSConnection
    last_error: OSError | None = None
    for ip in ips:
        conn = factory(host, ip, TIMEOUT_SECONDS)
        try:
            conn.request("GET", target, headers={
                "User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json,application/xml,text/csv",
                "Accept-Encoding": "identity", "Connection": "close",
            })
            response = conn.getresponse()
            if response.status != 200:
                raise ValueError("remote page did not return HTTP 200 (redirects refused)")
            media_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
            if not (media_type.startswith("text/") and
                    media_type not in {"text/javascript", "text/css"} or
                    media_type in _ALLOWED_APPLICATION_TYPES):
                raise ValueError("unsupported remote content type")
            if (response.getheader("Content-Encoding") or "identity").lower() != "identity":
                raise ValueError("compressed remote responses are not accepted")
            length = response.getheader("Content-Length")
            if length is not None and (not length.isdecimal() or int(length) > MAX_BODY_BYTES):
                raise ValueError("remote response too large")
            raw = response.read(MAX_BODY_BYTES + 1)
            if len(raw) > MAX_BODY_BYTES:
                raise ValueError("remote response exceeds size ceiling")
            return raw, media_type
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            last_error = OSError("public website unavailable")
        finally:
            conn.close()
    raise ConnectionError("all validated public addresses were unreachable") from last_error


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "iframe", "template"}:
            self.ignore_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "iframe", "template"}:
            self.ignore_depth = max(0, self.ignore_depth - 1)

    def handle_data(self, data):
        if self.ignore_depth == 0:
            self.chunks.append(data)


def text_excerpt(raw: bytes, media_type: str) -> str:
    decoded = raw.decode("utf-8-sig", errors="replace")
    if media_type == "text/html":
        parser = _VisibleText()
        parser.feed(decoded)
        decoded = " ".join(parser.chunks)
    return re.sub(r"\s+", " ", decoded).strip()[:EXCERPT_CHARS]


def inspect_urls(urls: list[str], *, fetch=None, now: datetime | None = None) -> dict:
    """Collect public research evidence; never auto-verify numbers or learn."""
    if not isinstance(urls, list) or not urls or len(urls) > MAX_PAGES_PER_INVOCATION:
        raise ValueError("provide 1 to 50 opt-in public page URLs per invocation")
    fetch = fetch or fetch_public_page
    now = (now or datetime.now(JST)).astimezone(JST)
    entries = []
    visited = set()
    for candidate in urls:
        fingerprint = sha256(str(candidate).encode("utf-8")).hexdigest()
        row: dict = {"request_sha256": fingerprint, "status": "unverified"}
        try:
            validated, host, display = validate_public_url(candidate)
            if validated in visited:
                row["status"] = "duplicate_skipped"
            else:
                visited.add(validated)
                row["host"] = host
                row["url_without_query"] = display
                raw, media_type = fetch(validated)
                if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES:
                    raise ValueError("unexpected response type or size")
                if not isinstance(media_type, str):
                    raise ValueError("invalid media type")
                row.update({
                    "status": "retrieved_untrusted_research_only",
                    "content_type": media_type,
                    "response_sha256": sha256(raw).hexdigest(),
                    "response_bytes": len(raw),
                    "text_excerpt": text_excerpt(raw, media_type),
                })
        except (ValueError, ConnectionError, OSError, UnicodeError) as exc:
            row["status"] = "rejected_or_unavailable"
            row["error_type"] = type(exc).__name__
        entries.append(row)
    return {
        "version": VERSION,
        "retrieved_at_jst": now.isoformat(timespec="seconds"),
        "status": "untrusted_research_sources_only",
        "submitted_urls": len(urls),
        "retrieved_pages": sum(x["status"] == "retrieved_untrusted_research_only" for x in entries),
        "pages": entries,
        "source_host_allowlist_required": False,
        "network_resource_limits_enabled": True,
        "official_results_verified": False,
        "official_payouts_verified": False,
        "issued_predictions_modified": False,
        "model_training_authorized": False,
        "production_model_promotion_authorized": False,
        "automatic_external_code_execution": False,
        "interpretation": "Opt-in read-only public web observations; no official result, forecast accuracy, or model authority.",
    }
