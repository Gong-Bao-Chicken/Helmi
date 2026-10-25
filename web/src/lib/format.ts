import { MARKET_NAME, type Price } from "./finder";
import type { Dataset, RatingSourceKey } from "./types";

const moneyFormatters = new Map<string, Intl.NumberFormat>();

export function money(amount: number | null | undefined, currency: string) {
  if (amount == null) return "–";
  let fmt = moneyFormatters.get(currency);
  if (!fmt) {
    const locale = currency === "USD" ? "en-US" : currency === "CHF" ? "de-CH" : "de-DE";
    fmt = new Intl.NumberFormat(locale, { style: "currency", currency, maximumFractionDigits: 0 });
    moneyFormatters.set(currency, fmt);
  }
  return fmt.format(amount);
}

export function priceLabel(price: Price | null) {
  if (!price) return "Price unknown";
  return `${price.kind === "estimate" ? "≈ " : ""}${money(price.amount, price.currency)}`;
}

export function priceSourceLabel(price: Price | null) {
  if (!price) return "No price data";
  if (price.kind === "estimate") {
    if (!price.from) return "US price at test time, converted";
    return `${MARKET_NAME[price.from]} shop price${price.converted ? ", converted" : ""}`;
  }
  return [shopName(price.source), priceWindowLabel(price.window)].filter(Boolean).join(" · ");
}

/** "30d_median" -> "30-day median"; the pipeline writes `<days>d_<median|latest>`. */
export function priceWindowLabel(window: string | null | undefined) {
  const match = /^(\d+)d_(median|latest)$/.exec(window ?? "");
  if (!match) return null;
  return match[2] === "median" ? `${match[1]}-day median` : "latest price";
}

const SHOPS: Record<string, string> = {
  geizhals: "Geizhals",
  idealo: "Idealo",
  toppreise: "toppreise.ch",
  amazon: "Amazon",
  galaxus: "Galaxus",
};

/**
 * Display name of a price source. Sources carry a country suffix ("idealo_at", "amazon_de"), and a
 * listing built from several shops joins them ("geizhals, idealo"); each company is named once.
 */
export function shopName(source: string | null | undefined) {
  if (!source) return "";
  const names = source.split(",").map((part) => {
    const company = part.trim().split("_")[0]!;
    return SHOPS[company] ?? company;
  });
  return [...new Set(names)].join(", ");
}

export function pct(value: number | null | undefined) {
  return value == null ? "–" : `${Math.round(value * 100)}`;
}

export function makeLabLabel(dataset: Dataset) {
  const map = new Map(dataset.filters.rating_sources.map((s) => [s.key, s.short]));
  return (key: RatingSourceKey) => map.get(key) ?? key;
}

export function relativeDate(iso: string | undefined) {
  if (!iso) return "unknown";
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
}
