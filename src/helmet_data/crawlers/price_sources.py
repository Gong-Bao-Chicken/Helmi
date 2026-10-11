"""Shop price search adapters for DE/AT/CH bicycle helmet retailers."""

import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from .common import BROWSER_USER_AGENT, normalize_tokens, polite_sleep, token_overlap_score
from .stealth_fetch import (
    geizhals_is_rate_limited,
    is_geizhals_html,
    is_idealo_html,
    is_toppreise_html,
    stealth_get,
)

EXCLUDE_TITLE_RE = re.compile(
    r"\b(ersatz|replacement|pad|polster|visier|cover|sock|hülle|case|goggle|brille)\b",
    re.I,
)
HELMET_HINT_RE = re.compile(r"\b(helm|helmet|fahrradhelm|bike helmet)\b", re.I)
PRICE_RE = re.compile(r"(\d{1,4}[.,]\d{2})")
GEIZHALS_PRODUCT_URL_RE = re.compile(r"-[av]\d+\.html", re.I)
MIN_HELMET_PRICE = {"EUR": 20.0, "CHF": 20.0}

PREFERRED_SOURCES = frozenset({"geizhals", "idealo", "toppreise"})
FALLBACK_SOURCES = frozenset({"amazon_de", "bike24", "galaxus", "velofactory"})
SOURCE_PRIORITY = ("geizhals", "idealo", "toppreise", "amazon_de", "bike24", "galaxus", "velofactory")


@dataclass
class PriceOffer:
    source: str
    title: str
    price: float
    currency: str
    url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    available: bool = True
    match_score: float = 0.0


@dataclass
class PriceSearchContext:
    brand: str
    model: str
    query: str
    needle: str


def build_search_context(brand: str, model: str) -> PriceSearchContext:
    cleaned = re.sub(r"\s+", " ", f"{brand} {model}").strip()
    query = f"{cleaned} Fahrradhelm"
    return PriceSearchContext(brand=brand, model=model, query=query, needle=cleaned)


def parse_decimal_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").replace("'", "").replace("\u2019", "")
    match = PRICE_RE.search(cleaned)
    if not match:
        return None
    raw = match.group(1)
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_amazon_rating(text: str | None) -> tuple[float | None, int | None]:
    if not text:
        return None, None
    rating_match = re.search(r"(\d+[.,]\d+)\s+von\s+5", text, re.I)
    count_match = re.search(r"(\d[\d.]*)", text.split("Stern", 1)[-1] if "Stern" in text else "")
    rating = float(rating_match.group(1).replace(",", ".")) if rating_match else None
    review_count = None
    if count_match:
        try:
            review_count = int(count_match.group(1).replace(".", ""))
        except ValueError:
            review_count = None
    return rating, review_count


def brand_match_tokens(brand: str) -> list[str]:
    tokens: list[str] = []
    for segment in brand.split("/"):
        for word in re.sub(r"[^a-z0-9]+", " ", segment.lower()).split():
            if len(word) > 1:
                tokens.append(word)
    return tokens


def model_overlap_score(model: str, title: str) -> float:
    model_tokens = normalize_tokens(model)
    if not model_tokens:
        return 1.0
    haystack_tokens = normalize_tokens(title)
    return len(model_tokens & haystack_tokens) / len(model_tokens)


def score_offer(ctx: PriceSearchContext, title: str) -> float:
    if EXCLUDE_TITLE_RE.search(title):
        return 0.0
    overlap = token_overlap_score(ctx.needle, title)
    if overlap < 0.45:
        return 0.0
    if not HELMET_HINT_RE.search(title) and overlap < 0.75:
        return 0.0
    brand_tokens = brand_match_tokens(ctx.brand)
    title_lower = title.lower()
    if brand_tokens and not any(token in title_lower for token in brand_tokens):
        return 0.0
    if model_overlap_score(ctx.model, title) < 0.34:
        return 0.0
    return overlap


def is_geizhals_product_url(url: str | None) -> bool:
    return bool(url and GEIZHALS_PRODUCT_URL_RE.search(url))


def accept_offer(ctx: PriceSearchContext, offer: PriceOffer, *, min_score: float = 0.5) -> PriceOffer | None:
    offer.match_score = score_offer(ctx, offer.title)
    if offer.match_score < min_score or not offer.available or offer.price <= 0:
        return None
    min_price = MIN_HELMET_PRICE.get(offer.currency)
    if min_price is not None and offer.price < min_price:
        return None
    if offer.source == "geizhals" and not is_geizhals_product_url(offer.url):
        return None
    return offer


def amazon_page_blocked(html: str) -> bool:
    return len(html) < 10_000 or 'data-component-type="s-search-result"' not in html


def search_amazon_html(html: str, ctx: PriceSearchContext) -> list[PriceOffer]:
    if amazon_page_blocked(html):
        return []
    soup = BeautifulSoup(html, "html.parser")
    offers: list[PriceOffer] = []
    for item in soup.select('[data-component-type="s-search-result"]'):
        title_el = item.select_one("h2 span, h2 a span")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        block_text = item.get_text(" ", strip=True)
        if re.search(r"nicht verfügbar|currently unavailable", block_text, re.I):
            continue

        price_el = item.select_one(".a-price .a-offscreen")
        if not price_el:
            price_el = item.select_one(".a-price-whole")
        price = parse_decimal_price(price_el.get_text(strip=True) if price_el else "")
        if price is None:
            continue

        link_el = item.select_one("h2 a")
        href = link_el.get("href") if link_el else None
        asin = item.get("data-asin")
        if href and href.startswith("/"):
            product_url = f"https://www.amazon.de{href}"
        elif href and href.startswith("http"):
            product_url = href.split("?")[0] if "/dp/" in href else href
        elif asin:
            product_url = f"https://www.amazon.de/dp/{asin}"
        else:
            product_url = None

        rating_el = item.select_one(".a-icon-alt")
        rating, review_count = parse_amazon_rating(rating_el.get_text(strip=True) if rating_el else None)

        offer = PriceOffer(
            source="amazon_de",
            title=title,
            price=price,
            currency="EUR",
            url=product_url,
            rating=rating,
            review_count=review_count,
        )
        accepted = accept_offer(ctx, offer, min_score=0.65)
        if accepted:
            offers.append(accepted)
    return offers


def search_amazon_de(client: httpx.Client, ctx: PriceSearchContext) -> list[PriceOffer]:
    url = f"https://www.amazon.de/s?k={quote_plus(ctx.query)}"
    response = client.get(url)
    if response.status_code != 200:
        return []
    return search_amazon_html(response.text, ctx)


def is_geizhals_blocked(html: str) -> bool:
    if len(html) < 15_000:
        return True
    if "Nur einen Moment" in html and "article.card" not in html and "galleryview" not in html:
        return True
    return "geizhals" not in html.lower() and len(html) < 30_000


def _geizhals_title_link(article) -> object | None:
    name_link = article.select_one("a.galleryview__name-link, h3 a[href*='.html']")
    if name_link is not None:
        title = name_link.get_text(strip=True)
        if len(title) >= 8:
            return name_link
    for link in article.select('a[href*=".html"]'):
        title = link.get_text(strip=True)
        if len(title) >= 8 and "Angebote" not in title and not title.startswith("€"):
            return link
    return None


def parse_geizhals_phist_html(html: str) -> list[tuple[str, float]]:
    """Return (iso-date, eur price) samples from a Geizhals price-history page."""
    if "Nur einen Moment" in html or len(html) < 5_000:
        return []

    points: list[tuple[str, float]] = []
    for match in re.finditer(
        r"(\d{4}-\d{2}-\d{2})[^\d]{0,20}(\d{1,4}[.,]\d{2})\s*€",
        html,
        flags=re.I,
    ):
        try:
            points.append((match.group(1), float(match.group(2).replace(",", "."))))
        except ValueError:
            continue
    return points


def search_geizhals_html(html: str, ctx: PriceSearchContext, *, domain: str) -> list[PriceOffer]:
    if is_geizhals_blocked(html):
        return []

    soup = BeautifulSoup(html, "html.parser")
    offers: list[PriceOffer] = []
    seen_urls: set[str] = set()
    articles = soup.select("article.card, article.galleryview__item")

    for article in articles:
        title_el = _geizhals_title_link(article)
        if title_el is None:
            continue

        title = title_el.get_text(" ", strip=True)
        price_el = article.select_one("span.price, .price")
        price = parse_decimal_price(price_el.get_text(strip=True) if price_el else "")
        if price is None:
            block = article.get_text(" ", strip=True)
            price_match = re.search(
                r"(?:ab\s*)?€\s*(\d{1,4}[.,]\d{2})|(\d{1,4}[.,]\d{2})\s*€",
                block,
                re.I,
            )
            if price_match:
                price = parse_decimal_price(price_match.group(1) or price_match.group(2))
        if price is None:
            continue

        href = title_el.get("href", "")
        product_url = href if href.startswith("http") else urljoin(f"https://{domain}/", href.lstrip("/"))
        if product_url in seen_urls:
            continue
        seen_urls.add(product_url)

        offer = PriceOffer(
            source="geizhals",
            title=title,
            price=price,
            currency="EUR",
            url=product_url,
        )
        accepted = accept_offer(ctx, offer, min_score=0.55)
        if accepted:
            offers.append(accepted)

    if offers:
        return offers

    # Legacy list layout — only when the page has no modern product cards.
    if articles:
        return []

    seen: set[str] = set()
    for link in soup.select('a[href*="-a"], a[href*="-v"]'):
        title = link.get_text(" ", strip=True)
        if len(title) < 8 or len(title) > 140 or title in seen:
            continue
        row = link.find_parent(["tr", "div", "article"]) or link.parent
        block = row.get_text(" ", strip=True) if row else title
        price_match = re.search(
            r"(?:ab\s*)?€\s*(\d{1,4}[.,]\d{2})|ab\s*(\d{1,4}[.,]\d{2})\s*€|(\d{1,4}[.,]\d{2})\s*€",
            block,
            re.I,
        )
        if not price_match:
            continue
        raw_price = next(group for group in price_match.groups() if group)
        price = parse_decimal_price(raw_price)
        if price is None:
            continue
        href = link.get("href", "")
        if not is_geizhals_product_url(href):
            continue
        product_url = href if href.startswith("http") else urljoin(f"https://{domain}/", href.lstrip("/"))
        seen.add(title)
        offer = PriceOffer(
            source="geizhals",
            title=title,
            price=price,
            currency="EUR",
            url=product_url,
        )
        accepted = accept_offer(ctx, offer, min_score=0.55)
        if accepted:
            offers.append(accepted)
    return offers


def search_geizhals(
    client: httpx.Client,
    ctx: PriceSearchContext,
    *,
    domain: str = "geizhals.de",
    page_fetcher: Callable[[str], str | None] | None = None,
) -> list[PriceOffer]:
    url = f"https://{domain}/?fs={quote_plus(ctx.query)}"
    html: str | None
    if page_fetcher is not None:
        html = page_fetcher(url)
    elif geizhals_is_rate_limited():
        html = ""
    else:
        status, html = stealth_get(url, validator=is_geizhals_html)
        if status != 200:
            html = ""
    if not html:
        return []
    return search_geizhals_html(html, ctx, domain=domain)


def search_galaxus(client: httpx.Client, ctx: PriceSearchContext) -> list[PriceOffer]:
    url = f"https://www.galaxus.ch/de/search?q={quote_plus(ctx.query)}"
    status, html = stealth_get(url)
    if status != 200 or not html:
        return []
    return search_galaxus_html(html, ctx)


def search_galaxus_html(html: str, ctx: PriceSearchContext) -> list[PriceOffer]:
    if len(html) < 20_000:
        return []

    soup = BeautifulSoup(html, "html.parser")
    offers: list[PriceOffer] = []
    for article in soup.select("article"):
        title_el = article.select_one('[data-test="product-title"], a[href*="/product/"]')
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        block = article.get_text(" ", strip=True)
        price_match = re.search(r"(\d{1,4}[.,]\d{2})\s*CHF", block) or re.search(
            r"(\d{1,4}[.,]\d{2})\s*\.–", block
        )
        if not price_match:
            continue
        price = parse_decimal_price(price_match.group(1))
        if price is None:
            continue
        href = title_el.get("href")
        product_url = (
            href if href and href.startswith("http") else f"https://www.galaxus.ch{href}" if href else None
        )
        offer = PriceOffer(
            source="galaxus",
            title=title,
            price=price,
            currency="CHF",
            url=product_url,
        )
        accepted = accept_offer(ctx, offer)
        if accepted:
            offers.append(accepted)
    return offers


def search_shop_html(
    html: str,
    ctx: PriceSearchContext,
    *,
    source: str,
    currency: str,
    base_url: str,
    title_selector: str,
    price_selector: str,
) -> list[PriceOffer]:
    soup = BeautifulSoup(html, "html.parser")
    offers: list[PriceOffer] = []
    for item in soup.select(title_selector):
        title_el = item.select_one("a") or item
        title = title_el.get_text(" ", strip=True)
        price_el = item.select_one(price_selector) if price_selector else item
        price = parse_decimal_price(price_el.get_text(" ", strip=True) if price_el else "")
        if price is None:
            continue
        href = title_el.get("href") if title_el.name == "a" else item.select_one("a")
        link = (
            href.get("href") if href and hasattr(href, "get") else (href if isinstance(href, str) else None)
        )
        product_url = link if link and link.startswith("http") else urljoin(base_url, link or "")
        offer = PriceOffer(
            source=source,
            title=title,
            price=price,
            currency=currency,
            url=product_url or None,
        )
        accepted = accept_offer(ctx, offer)
        if accepted:
            offers.append(accepted)
    return offers


def search_bike24(client: httpx.Client, ctx: PriceSearchContext) -> list[PriceOffer]:
    url = f"https://www.bike24.com/search?q={quote_plus(ctx.query)}"
    response = client.get(url)
    if response.status_code != 200:
        return []
    return search_shop_html(
        response.text,
        ctx,
        source="bike24",
        currency="EUR",
        base_url="https://www.bike24.com",
        title_selector=".product--box, .productbox, .product-list-item",
        price_selector=".product--price, .price--default, .price",
    )


def search_velofactory(client: httpx.Client, ctx: PriceSearchContext) -> list[PriceOffer]:
    url = f"https://www.velofactory.ch/de/search?q={quote_plus(ctx.query)}"
    response = client.get(url)
    if response.status_code != 200:
        return []
    return search_shop_html(
        response.text,
        ctx,
        source="velofactory",
        currency="CHF",
        base_url="https://www.velofactory.ch",
        title_selector=".product-item, .product-card, article",
        price_selector=".price, .product-price",
    )


def search_toppreise_html(html: str, ctx: PriceSearchContext) -> list[PriceOffer]:
    if len(html) < 20_000:
        return []

    soup = BeautifulSoup(html, "html.parser")
    offers: list[PriceOffer] = []
    seen_titles: set[str] = set()

    cards = soup.select("div.Plugin_Offer")
    if not cards:
        cards = soup.select("a.Plugin_Product, .Plugin_Product")

    for product in cards:
        name_el = product.select_one(".product-name a")
        if name_el:
            title = name_el.get_text(" ", strip=True)
        else:
            name_div = product.select_one(".product-name")
            if name_div:
                title = name_div.get_text(" ", strip=True)
            else:
                image = product.select_one("img[alt]")
                title = image.get("alt", "").strip() if image else ""
        if not title or title in seen_titles:
            continue

        price_el = product.select_one(".priceContainer.productPrice .Plugin_Price")
        if not price_el:
            price_el = product.select_one(".Plugin_Price, .price, .product-price")
        price = parse_decimal_price(price_el.get_text(strip=True) if price_el else "")
        if price is None:
            block = product.get_text(" ", strip=True)
            price_match = re.search(r"CHF\s*([\d'\u2019]+(?:\.\d{2})?)", block)
            if price_match:
                price = parse_decimal_price(price_match.group(1))
        if price is None:
            continue

        href = product.get("data-link") or ""
        if not href:
            link = product.select_one("a[href]")
            href = link.get("href", "") if link else ""
        product_url = href if href.startswith("http") else f"https://www.toppreise.ch{href}" if href else None
        seen_titles.add(title)

        offer = PriceOffer(
            source="toppreise",
            title=title,
            price=price,
            currency="CHF",
            url=product_url,
        )
        accepted = accept_offer(ctx, offer)
        if accepted:
            offers.append(accepted)
    return offers


def search_toppreise(client: httpx.Client, ctx: PriceSearchContext) -> list[PriceOffer]:
    url = f"https://www.toppreise.ch/produktsuche?q={quote_plus(ctx.query)}"
    status, html = stealth_get(url, validator=is_toppreise_html)
    if status != 200 or not html:
        return []
    return search_toppreise_html(html, ctx)


def is_idealo_blocked(html: str) -> bool:
    return len(html) < 10_000 or "akamai" in html.lower() or "sec-if-cpt-container" in html


def search_idealo_html(html: str, ctx: PriceSearchContext) -> list[PriceOffer]:
    if is_idealo_blocked(html):
        return []
    return search_shop_html(
        html,
        ctx,
        source="idealo",
        currency="EUR",
        base_url="https://www.idealo.de",
        title_selector=(
            '[data-testid="product-list-entry"], .productList-item, .sr-resultList__item, '
            '[class*="productList"]'
        ),
        price_selector='[data-testid="product-price"], .productList-item_price, .price',
    )


def search_idealo(client: httpx.Client, ctx: PriceSearchContext) -> list[PriceOffer]:
    url = f"https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q={quote_plus(ctx.query)}"
    status, html = stealth_get(url, validator=is_idealo_html)
    if status != 200 or not html:
        return []
    return search_idealo_html(html, ctx)


def make_price_client() -> httpx.Client:
    return httpx.Client(
        timeout=25.0,
        follow_redirects=True,
        headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )


def search_http_sources(client: httpx.Client, ctx: PriceSearchContext) -> list[PriceOffer]:
    offers: list[PriceOffer] = []
    preferred = (
        lambda: search_geizhals(client, ctx, domain="geizhals.de"),
        lambda: [] if geizhals_is_rate_limited() else search_geizhals(client, ctx, domain="geizhals.eu"),
        lambda: search_idealo(client, ctx),
        lambda: search_toppreise(client, ctx),
    )
    fallback = (
        lambda: search_amazon_de(client, ctx),
        lambda: search_bike24(client, ctx),
        lambda: search_galaxus(client, ctx),
        lambda: search_velofactory(client, ctx),
    )

    for search_fn in preferred:
        with contextlib.suppress(httpx.HTTPError):
            offers.extend(search_fn())
        polite_sleep(1.5)

    if not any(offer.source in PREFERRED_SOURCES for offer in offers):
        for search_fn in fallback:
            with contextlib.suppress(httpx.HTTPError):
                offers.extend(search_fn())
            polite_sleep(0.25)

    return offers


def dedupe_offers(offers: list[PriceOffer]) -> list[PriceOffer]:
    best_by_source: dict[str, PriceOffer] = {}
    for offer in offers:
        current = best_by_source.get(offer.source)
        if current is None or offer.price < current.price:
            best_by_source[offer.source] = offer
    priority = {source: index for index, source in enumerate(SOURCE_PRIORITY)}
    return sorted(
        best_by_source.values(),
        key=lambda item: (priority.get(item.source, 99), item.price),
    )


def pick_best_offer(offers: list[PriceOffer], currency: str) -> PriceOffer | None:
    matching = [offer for offer in offers if offer.currency == currency and offer.available]
    if not matching:
        return None
    preferred = [offer for offer in matching if offer.source in PREFERRED_SOURCES]
    pool = preferred or matching
    return min(
        pool,
        key=lambda item: (
            SOURCE_PRIORITY.index(item.source) if item.source in SOURCE_PRIORITY else 99,
            item.price,
        ),
    )
