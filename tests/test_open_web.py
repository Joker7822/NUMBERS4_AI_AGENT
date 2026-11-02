"""Offline security and research-authority tests for open public web retrieval."""
from datetime import datetime, timedelta, timezone
import socket
import unittest
from unittest.mock import patch

from numbers4_agent.open_web import (
    EXCERPT_CHARS, MAX_BODY_BYTES, DEFAULT_BATCH_SIZE,
    _PinnedHTTPSConnection, fetch_public_page, inspect_urls,
    public_addresses, text_excerpt, validate_public_url,
)

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 2, 17, 0, tzinfo=JST)
HTML = b"<html><head><script>BAD_INSTRUCTIONS</script></head><body><h1>Research</h1><p>Public reference.</p></body></html>"


def mock_dns(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]


def dns_mixed(host, port, **kwargs):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ]


class FakeResponse:
    def __init__(self, body=HTML, status=200, media="text/html", encoding="identity"):
        self.status = status
        self.body = body
        self.headers = {
            "Content-Type": media, "Content-Encoding": encoding,
            "Content-Length": str(len(body)),
        }

    def getheader(self, key):
        return self.headers.get(key)

    def read(self, size):
        return self.body[:size]


class FakeConnection:
    initialized = []
    requested = []
    response = FakeResponse()

    def __init__(self, host, address, timeout):
        self.initialized.append((host, address, timeout))

    def request(self, method, path, headers):
        self.requested.append((method, path, headers))

    def getresponse(self):
        return self.response

    def close(self):
        pass


class PublicResearchTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.initialized = []
        FakeConnection.requested = []
        FakeConnection.response = FakeResponse()

    def test_public_domains_are_not_fixed_allowlist(self):
        url, host, display = validate_public_url(
            "https://new-public-research.org/articles?id=42")
        self.assertEqual(host, "new-public-research.org")
        self.assertEqual(url, "https://new-public-research.org/articles?id=42")
        self.assertEqual(display, "https://new-public-research.org/articles")
        self.assertEqual(public_addresses(host, resolver=mock_dns), ["8.8.8.8"])

    def test_reject_private_urls_direct_ips_credentials_and_scheme(self):
        unsafe = [
            "http://research.org/", "https://localhost/",
            "https://127.0.0.1/", "https://[::1]/",
            "https://169.254.169.254/latest/meta-data/",
            "https://internal.local/", "https://a.internal/",
            "https://a.org:8443/", "https://alice:secret@a.org/",
            "file:///etc/passwd", "https://a.org/?access_token=secret",
            "https://a.org/?api_key=secret", "https://a.org/#fragment",
            "https://a.org/\r\nOther: injected",
        ]
        for url in unsafe:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_public_url(url)

    def test_dns_rebinding_mixed_record_refused(self):
        with self.assertRaisesRegex(ValueError, "private or reserved"):
            public_addresses("example-public.org", resolver=dns_mixed)
        with self.assertRaisesRegex(ValueError, "no public DNS"):
            public_addresses("example-public.org", resolver=lambda *a, **k: [])
        with self.assertRaisesRegex(ValueError, "DNS lookup failed"):
            public_addresses("example-public.org",
                             resolver=lambda *a, **k: (_ for _ in ()).throw(OSError("no DNS")))

    def test_connection_is_pinned_to_checked_ip_and_tls_sni(self):
        with patch("numbers4_agent.open_web.socket.create_connection") as connect, \
             patch("numbers4_agent.open_web.ssl.create_default_context") as context:
            pinned = _PinnedHTTPSConnection("new-public-research.org", "8.8.8.8", 10)
            pinned.connect()
            connect.assert_called_once_with(("8.8.8.8", 443), 10, source_address=None)
            context.return_value.wrap_socket.assert_called_once_with(
                connect.return_value, server_hostname="new-public-research.org")

    def test_public_research_get_uses_pinned_dns_and_no_redirect(self):
        raw, media = fetch_public_page(
            "https://new-public-research.org/path?q=42",
            resolver=mock_dns, connection_factory=FakeConnection)
        self.assertEqual(raw, HTML)
        self.assertEqual(media, "text/html")
        self.assertEqual(FakeConnection.initialized[0][:2],
                         ("new-public-research.org", "8.8.8.8"))
        method, path, headers = FakeConnection.requested[0]
        self.assertEqual((method, path), ("GET", "/path?q=42"))
        self.assertEqual(headers["Accept-Encoding"], "identity")

        FakeConnection.response = FakeResponse(status=302)
        with self.assertRaisesRegex(ValueError, "redirects refused"):
            fetch_public_page("https://new-public-research.org/", resolver=mock_dns,
                              connection_factory=FakeConnection)

    def test_reject_binary_compression_or_too_large(self):
        for response in [
            FakeResponse(media="application/octet-stream"),
            FakeResponse(encoding="gzip"),
            FakeResponse(body=b"x" * (MAX_BODY_BYTES + 1)),
        ]:
            FakeConnection.response = response
            with self.assertRaises(ValueError):
                fetch_public_page("https://new-public-research.org/",
                                  resolver=mock_dns,
                                  connection_factory=FakeConnection)

    def test_text_is_not_executable_or_verified_evidence(self):
        self.assertNotIn("BAD_INSTRUCTIONS", text_excerpt(HTML, "text/html"))
        self.assertIn("Research", text_excerpt(HTML, "text/html"))
        report = inspect_urls(
            ["https://new-public-research.org/?id=42",
             "https://new-public-research.org/?id=42",
             "http://127.0.0.1/"],
            fetch=lambda url: (HTML, "text/html"), now=NOW)
        self.assertEqual(report["retrieved_pages"], 1)
        self.assertEqual(report["pages"][1]["status"], "duplicate_skipped")
        self.assertEqual(report["pages"][2]["status"], "rejected_or_unavailable")
        self.assertNotIn("url_without_query", report["pages"][2])
        self.assertEqual(report["pages"][0]["url_without_query"],
                         "https://new-public-research.org/")
        self.assertFalse(report["official_results_verified"])
        self.assertFalse(report["model_training_authorized"])
        self.assertFalse(report["production_model_promotion_authorized"])
        self.assertFalse(report["issued_predictions_modified"])

    def test_unlimited_url_list_with_resumable_finite_batches(self):
        urls=[f"https://new-public-research.org/articles/{i}" for i in range(151)]
        first=inspect_urls(urls,fetch=lambda url:(HTML,"text/html"),now=NOW,
                           start_index=0,batch_size=DEFAULT_BATCH_SIZE)
        self.assertEqual(first["submitted_urls"],151)
        self.assertEqual(first["processed_urls"],25)
        self.assertEqual(first["retrieved_pages"],25)
        self.assertEqual(first["next_start_index"],25)
        self.assertTrue(first["has_more_input_urls"])
        self.assertIsNone(first["application_total_url_quota"])
        last=inspect_urls(urls,fetch=lambda url:(HTML,"text/html"),now=NOW,
                          start_index=150,batch_size=25)
        self.assertEqual(last["retrieved_pages"],1)
        self.assertIsNone(last["next_start_index"])
        self.assertFalse(last["has_more_input_urls"])
        for bad in [dict(start_index=-1),dict(start_index=151),
                    dict(start_index=0,batch_size=0)]:
            with self.assertRaises(ValueError):
                inspect_urls(urls,fetch=lambda url:(HTML,"text/html"),**bad)
        with self.assertRaises(ValueError):
            inspect_urls([])
        self.assertEqual(len(text_excerpt(b"a" * (EXCERPT_CHARS + 3), "text/plain")),
                         EXCERPT_CHARS)


if __name__ == "__main__":
    unittest.main()
