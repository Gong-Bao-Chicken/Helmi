"""HTTP fetch with browser TLS fingerprints (bypasses bot checks on Geizhals etc.)."""

import json
import random
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

from curl_cffi import requests as curl_requests

from ..paths import STEALTH_COOKIES_PATH

# safari17_0 has been the most reliable for geizhals.de; chrome often gets 403.
IMPERSONATE_ORDER = ("safari17_0", "safari18_0", "safari15_5", "chrome131", "chrome124", "chrome120")

COOKIE_FILE = STEALTH_COOKIES_PATH
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

# One session and one request gap per site: different shops are fetched in parallel,
# while each single site still sees at most one request per MIN_REQUEST_GAP_S.
_sessions: dict[str, curl_requests.Session] = {}
_host_locks: dict[str, threading.Lock] = {}
_host_last_request_at: dict[str, float] = {}
_registry_lock = threading.Lock()
_cookie_lock = threading.Lock()
_geizhals_backoff_until: float = 0.0
# Per site: [requests, seconds the site was held, failed requests]. Shows the bottleneck.
site_stats: dict[str, list[float]] = {}
MIN_REQUEST_GAP_S = 1.2
MAX_429_WAIT_S = 15


def _load_cookies(session: curl_requests.Session) -> None:
    if not COOKIE_FILE.exists():
        return
    try:
        data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        for item in data:
            session.cookies.set(
                item["name"],
                item["value"],
                domain=item.get("domain"),
                path=item.get("path", "/"),
            )
    except (json.JSONDecodeError, KeyError, OSError, TypeError):
        pass


def _save_cookies() -> None:
    """Write the cookies of all host sessions to one file (shared across runs)."""
    with _cookie_lock:
        try:
            cookies: list[dict[str, str]] = []
            for session in list(_sessions.values()):
                jar = session.cookies
                if hasattr(jar, "jar"):
                    for cookie in list(jar.jar):
                        cookies.append(
                            {
                                "name": cookie.name,
                                "value": cookie.value,
                                "domain": cookie.domain,
                                "path": cookie.path or "/",
                            }
                        )
                else:
                    for name, value in jar.items():
                        cookies.append({"name": name, "value": value, "domain": "", "path": "/"})
            COOKIE_FILE.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        except (OSError, TypeError, AttributeError, RuntimeError):
            pass


def _host(url: str) -> str:
    """The site a URL belongs to, used as the pacing key: geizhals.de and geizhals.eu (one
    backend, one rate limit) share it; www.idealo.de becomes idealo."""
    labels = (urlsplit(url).hostname or "").split(".")
    return labels[-2] if len(labels) >= 2 else labels[0]


def _host_lock(host: str) -> threading.Lock:
    with _registry_lock:
        return _host_locks.setdefault(host, threading.Lock())


def get_session(host: str) -> curl_requests.Session:
    """Session for one host. Callers hold that host's lock, so a session is never shared
    between threads at the same time."""
    session = _sessions.get(host)
    if session is None:
        session = curl_requests.Session(impersonate=IMPERSONATE_ORDER[0])
        _load_cookies(session)
        _sessions[host] = session
    return session


def is_geizhals_html(html: str) -> bool:
    if len(html) < 50_000:
        return False
    if "Sichere Verbindung" in html or ("Nur einen Moment" in html and "article.card" not in html):
        return False
    return "article.card" in html or "galleryview__item" in html


def is_toppreise_html(html: str) -> bool:
    return len(html) > 50_000 and (
        "Plugin_Offer" in html or "Plugin_Product" in html or "produktsuche" in html.lower()
    )


def is_idealo_html(html: str) -> bool:
    if len(html) < 20_000:
        return False
    if "sec-if-cpt-container" in html or "akamai" in html.lower():
        return False
    return any(marker in html for marker in ("product-list-entry", "productList-item", "sr-resultList__item"))


def mark_geizhals_rate_limited() -> None:
    global _geizhals_backoff_until
    _geizhals_backoff_until = time.monotonic() + 300.0


def geizhals_is_rate_limited() -> bool:
    return time.monotonic() < _geizhals_backoff_until


def _polite_wait(host: str) -> None:
    elapsed = time.monotonic() - _host_last_request_at.get(host, 0.0)
    gap = MIN_REQUEST_GAP_S + random.uniform(0.2, 0.8)
    if elapsed < gap:
        time.sleep(gap - elapsed)


@contextmanager
def host_slot(url: str) -> Iterator[None]:
    """Hold ``url``'s host for one request, spaced MIN_REQUEST_GAP_S after the previous one.

    For plain httpx fetches, so every shop - stealth or not - gets the same per-host pacing
    however many helmets are being fetched in parallel.
    """
    host = _host(url)
    with _host_lock(host):
        start = time.monotonic()
        _polite_wait(host)
        try:
            yield
        finally:
            _host_last_request_at[host] = time.monotonic()
            _count(host, start, failed=False)


def stealth_get(
    url: str,
    *,
    timeout: float = 30.0,
    validator: Callable[[str], bool] | None = None,
    max_retries: int = 1,
) -> tuple[int, str]:
    """Fetch a URL with curl_cffi TLS impersonation and a cookie session per host.

    Thread-safe: requests to the same host are serialised and spaced out, requests to
    different hosts run concurrently.
    """
    host = _host(url)
    with _host_lock(host):
        start = time.monotonic()
        status, text = _stealth_get_locked(
            url, host, timeout=timeout, validator=validator, max_retries=max_retries
        )
        _count(host, start, failed=status != 200)
        return status, text


def _count(host: str, start: float, *, failed: bool) -> None:
    entry = site_stats.setdefault(host, [0, 0.0, 0])
    entry[0] += 1
    entry[1] += time.monotonic() - start
    entry[2] += int(failed)


def site_report() -> str:
    """One line per site, busiest first: requests, time held (incl. pacing and retries), failures."""
    rows = sorted(site_stats.items(), key=lambda item: -item[1][1])
    return "\n".join(
        f"  {site:<10} {int(n):>4} requests  {busy / 60:5.1f} min busy  {int(failed)} failed"
        for site, (n, busy, failed) in rows
    )


def _stealth_get_locked(
    url: str,
    host: str,
    *,
    timeout: float,
    validator: Callable[[str], bool] | None,
    max_retries: int,
) -> tuple[int, str]:
    last_status = 0
    last_text = ""

    for attempt in range(max_retries + 1):
        for impersonate in IMPERSONATE_ORDER:
            try:
                _polite_wait(host)
                session = get_session(host)
                response = session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    headers=DEFAULT_HEADERS,
                    impersonate=impersonate,
                )
                _host_last_request_at[host] = time.monotonic()
                _save_cookies()
                last_status = response.status_code
                last_text = response.text

                if response.status_code == 429:
                    if "geizhals" in url:
                        mark_geizhals_rate_limited()
                    retry_after = int(response.headers.get("Retry-After", 5))
                    time.sleep(min(retry_after, MAX_429_WAIT_S))
                    break

                if response.status_code != 200:
                    continue

                if validator is not None and not validator(response.text):
                    continue

                if validator is None and len(response.text) < 5_000:
                    continue

                return response.status_code, response.text
            except Exception:
                _host_last_request_at[host] = time.monotonic()
                continue

        if "geizhals" in url and last_status in (403, 503):
            # Bot challenge ("Sichere Verbindung wird überprüft"): every impersonation was
            # refused, so back off instead of hammering it for every helmet.
            mark_geizhals_rate_limited()
            break

        if attempt < max_retries:
            time.sleep(2**attempt + random.uniform(0.5, 1.5))

    return last_status, last_text
