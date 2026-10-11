import re
from dataclasses import dataclass

from ..crawlers.common import slugify, token_overlap_score

MATCH_THRESHOLD = 0.72


@dataclass
class HelmetMatch:
    helmet_id: str
    brand: str
    model: str
    confidence: float
    method: str


def _brand_candidates(helmets: list[dict]) -> list[str]:
    brands = sorted({helmet["brand"] for helmet in helmets}, key=len, reverse=True)
    return brands


def _match_by_slug(slug: str, helmets_by_id: dict[str, dict]) -> HelmetMatch | None:
    if slug in helmets_by_id:
        helmet = helmets_by_id[slug]
        return HelmetMatch(
            helmet_id=helmet["id"],
            brand=helmet["brand"],
            model=helmet["model"],
            confidence=1.0,
            method="slug",
        )
    return None


def _match_by_brand_model(
    brand: str,
    model: str,
    helmets: list[dict],
    brand_candidates: list[str],
) -> HelmetMatch | None:
    brand_norm = brand.strip().lower()
    model_norm = model.strip()

    exact = [
        helmet
        for helmet in helmets
        if helmet["brand"].lower() == brand_norm and helmet["model"].lower() == model_norm.lower()
    ]
    if len(exact) == 1:
        helmet = exact[0]
        return HelmetMatch(
            helmet_id=helmet["id"],
            brand=helmet["brand"],
            model=helmet["model"],
            confidence=0.98,
            method="brand_model_exact",
        )

    needle = f"{brand} {model}"
    best: HelmetMatch | None = None
    for helmet in helmets:
        haystack = f"{helmet['brand']} {helmet['model']}"
        score = token_overlap_score(needle, haystack)
        if best is None or score > best.confidence:
            best = HelmetMatch(
                helmet_id=helmet["id"],
                brand=helmet["brand"],
                model=helmet["model"],
                confidence=score,
                method="token_overlap",
            )

    if best and best.confidence >= MATCH_THRESHOLD:
        return best
    return None


def _match_by_model_only(
    model_name: str,
    helmets: list[dict],
    brand_candidates: list[str],
) -> HelmetMatch | None:
    model_name = re.sub(r"\s+", " ", model_name).strip()
    model_lower = model_name.lower()

    inferred_brand = None
    for brand in brand_candidates:
        if model_lower.startswith(brand.lower()):
            inferred_brand = brand
            break

    if inferred_brand:
        remainder = model_name[len(inferred_brand) :].strip(" -")
        matched = _match_by_brand_model(inferred_brand, remainder, helmets, brand_candidates)
        if matched:
            return matched

    best: HelmetMatch | None = None
    for helmet in helmets:
        score = token_overlap_score(model_name, f"{helmet['brand']} {helmet['model']}")
        if best is None or score > best.confidence:
            best = HelmetMatch(
                helmet_id=helmet["id"],
                brand=helmet["brand"],
                model=helmet["model"],
                confidence=score,
                method="model_token_overlap",
            )

    if best and best.confidence >= MATCH_THRESHOLD:
        return best
    return None


def match_certimoov(
    rating: dict,
    helmets: list[dict],
    *,
    brand_candidates: list[str] | None = None,
) -> HelmetMatch | None:
    helmets_by_id = {helmet["id"]: helmet for helmet in helmets}
    brand_candidates = brand_candidates or _brand_candidates(helmets)

    by_slug = _match_by_slug(rating["slug"], helmets_by_id)
    if by_slug:
        return by_slug

    slug_guess = slugify(rating.get("brand", ""), rating.get("model", ""))
    by_guess = _match_by_slug(slug_guess, helmets_by_id)
    if by_guess:
        return by_guess

    return _match_by_brand_model(
        rating.get("brand", ""),
        rating.get("model", ""),
        helmets,
        brand_candidates,
    )


def match_folksam(
    rating: dict,
    helmets: list[dict],
    *,
    brand_candidates: list[str] | None = None,
) -> HelmetMatch | None:
    brand_candidates = brand_candidates or _brand_candidates(helmets)
    return _match_by_model_only(rating["name"], helmets, brand_candidates)


def match_nsw(
    rating: dict,
    helmets: list[dict],
    *,
    brand_candidates: list[str] | None = None,
) -> HelmetMatch | None:
    brand_candidates = brand_candidates or _brand_candidates(helmets)
    return _match_by_model_only(rating["model"], helmets, brand_candidates)
