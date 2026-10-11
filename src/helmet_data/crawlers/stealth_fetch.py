"""HTTP fetch with browser TLS fingerprints (bypasses bot checks on Geizhals etc.)."""

import json
import random
import time
from collections.abc import Callable

from curl_cffi import requests as curl_requests

from ..paths import STEALTH_COOKIES_PATH

# safari17_0 has been the most reliable for geizhals.de; chrome often gets 403.
IMPERSONATE_ORDER = ("safari17_0", "safari18_0", "safari15_5", "chrome131", "chrome124", "chrome120")

COOKIE_FILE = STEALTH_COOKIES_PATH
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

_session: curl_requests.Session | None = None
_last_request_at: float = 0.0
_geizhals_backoff_until: float = 0.0
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


def _save_cookies(session: curl_requests.Session) -> None:
    try:
        cookies: list[dict[str, str]] = []
        jar = session.cookies
        if hasattr(jar, "jar"):
            for cookie in jar.jar:
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
    except (OSError, TypeError, AttributeError):
        pass


def get_session(*, impersonate: str = "safari17_0") -> curl_requests.Session:
    global _session
    if _session is None:
        _session = curl_requests.Session(impersonate=impersonate)
        _load_cookies(_session)
    return _session


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


def _polite_wait() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    gap = MIN_REQUEST_GAP_S + random.uniform(0.2, 0.8)
    if elapsed < gap:
        time.sleep(gap - elapsed)


def stealth_get(
    url: str,
    *,
    timeout: float = 30.0,
    validator: Callable[[str], bool] | None = None,
    max_retries: int = 1,
) -> tuple[int, str]:
    """Fetch a URL with curl_cffi TLS impersonation and a shared cookie session."""
    last_status = 0
    last_text = ""

    for attempt in range(max_retries + 1):
        for impersonate in IMPERSONATE_ORDER:
            try:
                _polite_wait()
                session = get_session(impersonate=impersonate)
                response = session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    headers=DEFAULT_HEADERS,
                )
                _save_cookies(session)
                global _last_request_at
                _last_request_at = time.monotonic()

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
                continue

        if attempt < max_retries:
            time.sleep(2**attempt + random.uniform(0.5, 1.5))

    return last_status, last_text
