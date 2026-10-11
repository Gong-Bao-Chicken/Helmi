from __future__ import annotations

import re
import time
from typing import Callable

import httpx

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CRAWLER_USER_AGENT = "HelmetCompare/0.1 (+https://github.com/local/helmet-compare; research)"


def slugify(*parts: str) -> str:
    text = "-".join(parts).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_tokens(text: str) -> set[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop = {
        "helmet",
        "mips",
        "the",
        "bike",
        "bicycle",
        "youth",
        "adult",
        "jr",
        "junior",
        "led",
    }
    return {token for token in text.split() if token not in stop and len(token) > 1}


def token_overlap_score(needle: str, haystack: str) -> float:
    needle_tokens = normalize_tokens(needle)
    if not needle_tokens:
        return 0.0
    haystack_tokens = normalize_tokens(haystack)
    return len(needle_tokens & haystack_tokens) / len(needle_tokens)


def make_client(*, browser: bool = False, timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": BROWSER_USER_AGENT if browser else CRAWLER_USER_AGENT},
        follow_redirects=True,
    )


def polite_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def fetch_pages(
    client: httpx.Client,
    urls: list[str],
    *,
    delay: float = 0.25,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, str]:
    results: dict[str, str] = {}
    total = len(urls)
    for index, url in enumerate(urls, start=1):
        if on_progress:
            on_progress(index, total, url)
        response = client.get(url)
        response.raise_for_status()
        results[url] = response.text
        polite_sleep(delay)
    return results
