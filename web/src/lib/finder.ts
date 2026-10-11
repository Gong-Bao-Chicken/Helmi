/**
 * Goal-based helmet finder: turns "what do you ride / what matters / constraints" into a
 * filtered, ranked shortlist with highlighted picks and human-readable reasons.
 */
import { frontier, kneeId, median, paretoIds, percentileRank, type Point } from "./scoring";
import type { Dataset, Helmet, MarketKey, RatingSourceKey } from "./types";

export type RideKey = "road" | "race" | "gravel" | "trail" | "gravity" | "city" | "speed" | "any";
export type PriorityKey = "protection" | "value" | "aero" | "budget";
export type MarketChoice = MarketKey | "us";
export type SafetySource = "fused" | RatingSourceKey;

export interface Ride {
  key: RideKey;
  label: string;
  blurb: string;
  styles: string[] | null;
  requireNta8776?: boolean;
  suggestedPriority?: PriorityKey;
}

export const RIDES: Ride[] = [
  { key: "road", label: "Road", blurb: "Training rides, sportives, club runs", styles: ["Road", "Aero", "Multi-sport"] },
  {
    key: "race",
    label: "Racing & tri",
    blurb: "Every watt counts",
    styles: ["Aero", "Road"],
    suggestedPriority: "aero",
  },
  { key: "gravel", label: "Gravel", blurb: "Mixed surfaces, long days", styles: ["Multi-sport", "Road", "Mountain"] },
  { key: "trail", label: "Trail MTB", blurb: "Singletrack, XC, all-mountain", styles: ["Mountain", "Multi-sport"] },
  { key: "gravity", label: "Enduro & downhill", blurb: "Full-face protection", styles: ["Full-Face"] },
  { key: "city", label: "City & commute", blurb: "Everyday riding, e-bikes", styles: ["Urban", "Multi-sport", "Road"] },
  {
    key: "speed",
    label: "Speed pedelec",
    blurb: "45 km/h e-bikes (NTA 8776)",
    styles: null,
    requireNta8776: true,
  },
  { key: "any", label: "Show me everything", blurb: "All styles", styles: null },
];

export interface Priority {
  key: PriorityKey;
  label: string;
  blurb: string;
}

export const PRIORITIES: Priority[] = [
  { key: "value", label: "Best protection for the money", blurb: "Balances lab safety against price" },
  { key: "protection", label: "Maximum protection", blurb: "Price only breaks near-ties" },
  { key: "budget", label: "Cheapest that's still safe", blurb: "Top-40% safety, lowest price first" },
  { key: "aero", label: "Fast and safe", blurb: "Wind-tunnel tested helmets only" },
];

export interface Goals {
  ride: RideKey | null;
  priority: PriorityKey;
  /** Maximum price in the market's currency. */
  budget: number | null;
  market: MarketChoice;
  /** Require slip-plane, spherical or crumple technology. */
  rotational: boolean;
  /** Only helmets with a current shop price in the chosen market. */
  pricedOnly: boolean;
  /** Only brands/versions sold in Europe. */
  euOnly: boolean;
  safetySource: SafetySource;
}

export const DEFAULT_GOALS: Goals = {
  ride: null,
  priority: "value",
  budget: null,
  market: "de",
  rotational: false,
  pricedOnly: false,
  euOnly: true,
  safetySource: "fused",
};

/** Minimum safety percentile for the "budget" priority and the budget pick. */
export const SAFE_ENOUGH = 0.6;

const CURRENCY: Record<MarketChoice, string> = { de: "EUR", at: "EUR", ch: "CHF", us: "USD" };

export function marketCurrency(market: MarketChoice) {
  return CURRENCY[market];
}

export interface Price {
  amount: number;
  currency: string;
  /** live = current shop price; estimate = converted US price at test time. */
  kind: "live" | "estimate";
  source?: string | null;
  url?: string | null;
  window?: string | null;
}

/** USD → currency rates, derived from the dataset's own conversions with sane fallbacks. */
export function deriveFxRates(helmets: readonly Helmet[]): Record<string, number> {
  const eur = median(
    helmets
      .map((h) => h.current_price)
      .filter((p) => p?.currency === "EUR" && p.usd_equiv > 0)
      .map((p) => p!.amount / p!.usd_equiv),
  );
  const chfPerEur = median(
    helmets
      .filter((h) => h.listings.ch?.price && h.listings.de?.price)
      .map((h) => h.listings.ch!.price! / h.listings.de!.price!),
  );
  const eurRate = eur ?? 0.88;
  return { USD: 1, EUR: eurRate, CHF: eurRate * (chfPerEur ?? 0.95) };
}

export function priceFor(helmet: Helmet, market: MarketChoice, fx: Record<string, number>): Price | null {
  if (market !== "us") {
    const listing = helmet.listings[market];
    if (listing?.price != null) {
      return {
        amount: listing.price,
        currency: listing.currency,
        kind: "live",
        source: listing.source,
        url: listing.url,
        window: listing.price_window,
      };
    }
  }
  if (helmet.price_at_test_usd == null) return null;
  const currency = CURRENCY[market];
  return {
    amount: Math.round(helmet.price_at_test_usd * (fx[currency] ?? 1)),
    currency,
    kind: market === "us" ? "live" : "estimate",
    source: market === "us" ? "US retail at test time" : null,
  };
}

const LAB_ORDER: RatingSourceKey[] = ["virginia_tech", "folksam", "certimoov", "nsw_helmet_star", "hiper"];

/** Lab sources with a usable percentile for this helmet. */
export function labsFor(helmet: Helmet): RatingSourceKey[] {
  return LAB_ORDER.filter((key) => helmet.ratings[key]?.rank_pct != null);
}

export function safetyFor(helmet: Helmet, source: SafetySource): number | null {
  if (source === "fused") {
    return helmet.ratings.fused?.rank_pct ?? helmet.ratings.virginia_tech?.rank_pct ?? null;
  }
  return helmet.ratings[source]?.rank_pct ?? null;
}

export function hasRotationalTech(helmet: Helmet) {
  return (helmet.protection_group ?? "none") !== "none";
}

export type PickKind = "best" | "safest" | "value" | "budget" | "aero" | "alt";

export interface Ranked {
  helmet: Helmet;
  safety: number;
  price: Price | null;
  /** Price converted to USD so all candidates compare on one scale. */
  priceUsd: number | null;
  /** 1 = cheapest in the candidate pool. */
  cheapness: number | null;
  aero: number | null;
  score: number;
  rank: number;
  safetyRank: number;
  onFrontier: boolean;
  picks: PickKind[];
  labs: RatingSourceKey[];
}

export interface FinderResult {
  ranked: Ranked[];
  picks: { kind: PickKind; item: Ranked }[];
  frontier: Point[];
  /** Why the pool is the size it is, for the empty/short-list states. */
  excluded: { reason: string; count: number }[];
  /** Total helmets with a safety rating for the chosen source. */
  ratedTotal: number;
}

function weightsFor(priority: PriorityKey) {
  switch (priority) {
    case "protection":
      return { safety: 0.95, cheap: 0.05, aero: 0 };
    case "budget":
      return { safety: 0.3, cheap: 0.7, aero: 0 };
    case "aero":
      return { safety: 0.45, cheap: 0.15, aero: 0.4 };
    default:
      return { safety: 0.55, cheap: 0.45, aero: 0 };
  }
}

/** Unknown prices rank as slightly worse than the median, not as free. */
const UNKNOWN_CHEAPNESS = 0.35;

export function findHelmets(dataset: Dataset, goals: Goals, fx = deriveFxRates(dataset.helmets)): FinderResult {
  const ride = RIDES.find((r) => r.key === goals.ride) ?? RIDES[RIDES.length - 1]!;
  const excluded = new Map<string, number>();
  const drop = (reason: string) => excluded.set(reason, (excluded.get(reason) ?? 0) + 1);

  const candidates: Omit<Ranked, "cheapness" | "score" | "rank" | "safetyRank" | "onFrontier" | "picks">[] = [];
  let ratedTotal = 0;

  for (const helmet of dataset.helmets) {
    const safety = safetyFor(helmet, goals.safetySource);
    if (safety == null) continue;
    ratedTotal += 1;
    if (ride.styles && !ride.styles.includes(helmet.style)) continue;
    if (ride.requireNta8776 && !helmet.features.nta8776) continue;
    if (goals.euOnly && goals.market !== "us" && !helmet.european_market) {
      drop("not sold in Europe");
      continue;
    }
    if (goals.rotational && !hasRotationalTech(helmet)) {
      drop("no rotational protection");
      continue;
    }
    const price = priceFor(helmet, goals.market, fx);
    if (goals.pricedOnly && price?.kind !== "live") {
      drop("no current shop price");
      continue;
    }
    if (goals.budget != null && (price == null || price.amount > goals.budget)) {
      drop(price == null ? "no known price" : "over budget");
      continue;
    }
    const aero = helmet.aero?.rank_pct ?? null;
    if (goals.priority === "aero" && aero == null) {
      drop("no wind-tunnel data");
      continue;
    }
    if (goals.priority === "budget" && safety < SAFE_ENOUGH) {
      drop("below the safety bar");
      continue;
    }
    const priceUsd = price ? price.amount / (fx[price.currency] ?? 1) : null;
    candidates.push({ helmet, safety, price, priceUsd, aero, labs: labsFor(helmet) });
  }

  const prices = candidates.map((c) => c.priceUsd);
  const points: Point[] = candidates
    .filter((c) => c.priceUsd != null)
    .map((c) => ({ id: c.helmet.id, price: c.priceUsd!, safety: c.safety }));
  const pareto = paretoIds(points);
  const front = frontier(points);
  const weights = weightsFor(goals.priority);

  const ranked: Ranked[] = candidates.map((c) => {
    const pricePct = percentileRank(prices, c.priceUsd);
    const cheapness = pricePct == null ? null : 1 - pricePct;
    const score =
      weights.safety * c.safety + weights.cheap * (cheapness ?? UNKNOWN_CHEAPNESS) + weights.aero * (c.aero ?? 0);
    return { ...c, cheapness, score, rank: 0, safetyRank: 0, onFrontier: pareto.has(c.helmet.id), picks: [] };
  });

  ranked.sort((a, b) => b.score - a.score || b.safety - a.safety);
  ranked.forEach((r, i) => (r.rank = i + 1));
  [...ranked].sort((a, b) => b.safety - a.safety).forEach((r, i) => (r.safetyRank = i + 1));

  const byId = new Map(ranked.map((r) => [r.helmet.id, r]));
  const picks: { kind: PickKind; item: Ranked }[] = [];
  const addPick = (kind: PickKind, item: Ranked | undefined) => {
    if (!item) return;
    item.picks.push(kind);
    if (!picks.some((p) => p.item === item)) picks.push({ kind, item });
  };

  addPick("best", ranked[0]);
  addPick(
    "safest",
    [...ranked].sort((a, b) => b.safety - a.safety || (a.priceUsd ?? Infinity) - (b.priceUsd ?? Infinity))[0],
  );
  const knee = kneeId(front);
  addPick("value", knee ? byId.get(knee) : undefined);
  addPick(
    "budget",
    ranked
      .filter((r) => r.safety >= SAFE_ENOUGH && r.priceUsd != null)
      .sort((a, b) => a.priceUsd! - b.priceUsd! || b.safety - a.safety)[0],
  );
  if (goals.priority === "aero" || ride.key === "race" || ride.key === "road") {
    addPick(
      "aero",
      ranked.filter((r) => r.aero != null && r.safety >= 0.5).sort((a, b) => b.aero! - a.aero!)[0],
    );
  }

  // When one helmet wins several badges, fill the remaining slots with runners-up.
  for (const r of ranked) {
    if (picks.length >= 4) break;
    if (!r.picks.length) addPick("alt", r);
  }

  return {
    ranked,
    picks,
    frontier: front,
    excluded: [...excluded].map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count),
    ratedTotal,
  };
}

export interface Reason {
  tone: "good" | "neutral" | "caution";
  text: string;
}

/** Plain-language reasons why a helmet is on the list, plus honest caveats. */
export function explain(item: Ranked, result: FinderResult, labLabel: (key: RatingSourceKey) => string): Reason[] {
  const reasons: Reason[] = [];
  const pct = Math.round(item.safety * 100);
  const total = result.ranked.length;

  reasons.push({
    tone: item.safety >= 0.75 ? "good" : item.safety >= 0.4 ? "neutral" : "caution",
    text: `${pct >= 100 ? "Among the very safest lab-tested helmets" : `Safer than ${pct}% of lab-tested helmets`}${
      total > 1 ? ` · #${item.safetyRank} of ${total} matches` : ""
    }`,
  });

  if (item.labs.length > 1) {
    reasons.push({ tone: "good", text: `Confirmed by ${item.labs.length} labs: ${item.labs.map(labLabel).join(", ")}` });
  } else if (item.labs.length === 1) {
    reasons.push({ tone: "neutral", text: `Rated by ${labLabel(item.labs[0]!)} only` });
  }

  if (item.priceUsd != null) {
    const peers = result.ranked.filter(
      (r) => r !== item && r.priceUsd != null && Math.abs(r.safety - item.safety) <= 0.1,
    );
    const peerMedian = median(peers.map((r) => r.priceUsd!));
    if (peerMedian != null && peers.length >= 3) {
      const diff = (item.priceUsd - peerMedian) / peerMedian;
      if (diff <= -0.15) {
        reasons.push({ tone: "good", text: `${Math.round(-diff * 100)}% cheaper than similarly safe helmets` });
      } else if (diff >= 0.25) {
        reasons.push({ tone: "caution", text: `${Math.round(diff * 100)}% pricier than similarly safe helmets` });
      }
    }
  }

  if (item.onFrontier) {
    reasons.push({ tone: "good", text: "No helmet on your list is both safer and cheaper" });
  }

  const tech = item.helmet.protection?.rotational_label ?? item.helmet.protection?.mips_label;
  if (tech) reasons.push({ tone: "neutral", text: `Rotational protection: ${tech}` });

  const aero = item.helmet.aero;
  if (aero?.tier && aero.watts_saved != null) {
    const tone = aero.tier === "elite" || aero.tier === "strong" ? "good" : aero.tier === "draggy" ? "caution" : "neutral";
    const baseline = aero.sources.cyclingnews_sseh_2025?.baseline_helmet;
    reasons.push({
      tone,
      text: `Aero ${aero.tier}: ${aero.watts_saved > 0 ? "saves" : "costs"} ${Math.abs(aero.watts_saved).toFixed(1)} W at 40 km/h${
        baseline ? ` vs ${baseline}` : ""
      }`,
    });
  }

  if (item.price?.kind === "estimate") {
    reasons.push({ tone: "caution", text: "No current shop price found; showing the converted US price at test time" });
  }

  const year = Number(item.helmet.test_year);
  if (year && year <= 2019) {
    reasons.push({ tone: "caution", text: `Tested in ${year}; this model may have been replaced` });
  }

  return reasons;
}
