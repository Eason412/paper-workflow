"""Standard-library metadata requests and guarded, atomic PDF downloads."""
from __future__ import annotations

import ipaddress
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import store

VERSION = "0.5.0"
MAX_PDF_BYTES = 80 * 1024 * 1024
DEFAULT_TIMEOUT = 30
UA = f"oa-paper-fetch/{VERSION} (+legal-open-access)"
PDF_UA = UA


def request_json(url: str, timeout: int) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return None


def safe_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if port not in {None, 80, 443}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False
    if host in {"localhost", "metadata.google.internal", "metadata.aws.internal", "metadata"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # urllib/socket accept several legacy numeric loopback spellings that
        # ipaddress intentionally rejects (for example 2130706433 or 0177.0.0.1).
        if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}",
                        host, re.I):
            return False
        # Do not pre-resolve and then reconnect by name: that would still be
        # vulnerable to DNS rebinding, while VPN/proxy resolvers commonly map
        # public hosts into synthetic address ranges. Reject local namespaces
        # here and reapply this URL policy to every redirect hop instead.
        if host.endswith((".localhost", ".local", ".internal", ".home.arpa")):
            return False
        return True
    return ip.is_global


class UnsafeRedirectError(ValueError):
    """Raised when a redirect crosses the public-URL safety boundary."""


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Apply the same public-URL policy to every HTTP redirect hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        if not safe_url(target):
            raise UnsafeRedirectError(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def _request_arxiv_feed(params: dict[str, str], timeout: int) -> ET.Element | None:
    query = urllib.parse.urlencode(params)
    url = f"https://export.arxiv.org/api/query?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            xml = response.read()
    except Exception:
        return None
    try:
        return ET.fromstring(xml)
    except ET.ParseError:
        return None


def download_pdf(url: str, dest: Path, timeout: int, overwrite: bool) -> tuple[bool, str]:
    if not safe_url(url):
        return False, "unsafe_url"
    if store.verify_pdf(dest) and not overwrite:
        return True, "exists"
    req = urllib.request.Request(url, headers={"User-Agent": PDF_UA, "Accept": "application/pdf,*/*"})
    try:
        opener = urllib.request.build_opener(SafeRedirectHandler())
        with opener.open(req, timeout=timeout) as response:
            data = response.read(MAX_PDF_BYTES + 1)
    except UnsafeRedirectError:
        return False, "unsafe_redirect"
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except Exception as exc:
        return False, f"network_{type(exc).__name__}"
    if len(data) > MAX_PDF_BYTES:
        return False, "too_large"
    if not store.has_pdf_signature(data):
        return False, "not_pdf"
    store.atomic_write_bytes(dest, data)
    return True, "downloaded"
