/**
 * Goal-based helmet finder: turns "what do you ride / what matters / constraints" into a
 * filtered, ranked shortlist with highlighted picks and human-readable reasons.
 */
import { fairValueBand, frontier, kneeId, median, paretoIds, percentileRank, type Bin, type Point } from "./scoring";
import type { Dataset, Helmet, MarketKey, RatingSourceKey } from "./types";

export type RideKey = "road" | "race" | "gravel" | "trail" | "gravity" | "city" | "speed" | "kids" | "any";
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
  { key: "road", label: "Road", blurb: "Training rides, club runs and sportives", styles: ["Road", "Aero", "Multi-sport"] },
  {
    key: "race",
    label: "Racing & tri",
    blurb: "Races, time trials and triathlon: aero helmets",
    styles: ["Aero", "Road"],
    suggestedPriority: "aero",
  },
  { key: "gravel", label: "Gravel", blurb: "Mixed tarmac and dirt, long days out", styles: ["Multi-sport", "Road", "Mountain"] },
  { key: "trail", label: "Trail MTB", blurb: "Singletrack and cross-country on a mountain bike", styles: ["Mountain", "Multi-sport"] },
  { key: "gravity", label: "Enduro & downhill", blurb: "Fast, rough descents: full-face helmets", styles: ["Full-Face"] },
  {
    key: "city",
    label: "City & commute",
    blurb: "Getting to work, errands, e-bikes up to 25 km/h",
    // Unclassified helmets are mostly plain all-round helmets, so they stay available here.
    styles: ["Urban", "Multi-sport", "Road", "Unclassified"],
  },
  {
    key: "speed",
    label: "Speed pedelec",
    blurb: "Fast e-bikes up to 45 km/h, with a number plate",
    styles: null,
    requireNta8776: true,
  },
  { key: "kids", label: "Kids", blurb: "Helmets sized for children and teens", styles: ["Kids"] },
  // Last on purpose: the fallback when no ride is chosen.
  { key: "any", label: "Show me everything", blurb: "Every helmet, any style", styles: null },
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
  /** Only helmets tested by at least two labs. */
  multiLab: boolean;
  /** Wind-tunnel helmet class (racing): vented, semi-aero, aero road or time trial. */
  aeroClass: AeroClass | null;
  safetySource: SafetySource;
}

export type AeroClass = "vented" | "semi_aero" | "aero" | "time_trial";
export const AERO_CLASSES: { key: AeroClass; label: string }[] = [
  { key: "vented", label: "Vented" },
  { key: "semi_aero", label: "Semi-aero" },
  { key: "aero", label: "Aero road" },
  { key: "time_trial", label: "Time trial" },
];

/** The wind-tunnel class of a helmet, from its newest test. */
export function aeroClassOf(helmet: Helmet): AeroClass | null {
  const sources = Object.values(helmet.aero?.sources ?? {}).sort((a, b) => Number(b.test_year ?? 0) - Number(a.test_year ?? 0));
  return (sources.find((s) => s.helmet_class)?.helmet_class as AeroClass | undefined) ?? null;
}

/** Where the safety score comes from: one site-wide setting (top bar), used by every view. */
export const SAFETY_SOURCES: { key: SafetySource; label: string; short: string }[] = [
  { key: "fused", label: "All labs combined", short: "Combined" },
  { key: "virginia_tech", label: "Virginia Tech only", short: "VT" },
  { key: "folksam", label: "Folksam only", short: "Folksam" },
  { key: "certimoov", label: "CERTIMOOV only", short: "CERTIMOOV" },
  { key: "nsw_helmet_star", label: "NSW Helmet STAR only", short: "NSW" },
];

export const DEFAULT_GOALS: Goals = {
  ride: null,
  priority: "value",
  budget: null,
  market: "de",
  rotational: false,
  pricedOnly: false,
  euOnly: true,
  multiLab: false,
  aeroClass: null,
  safetySource: "fused",
};

/** Minimum safety percentile for the "budget" priority and the budget pick. */
export const SAFE_ENOUGH = 0.6;

const CURRENCY: Record<MarketChoice, string> = { de: "EUR", at: "EUR", ch: "CHF", us: "USD" };
const NEIGHBOURS: MarketKey[] = ["de", "at", "ch"];
export const MARKET_NAME: Record<MarketKey, string> = { de: "German", at: "Austrian", ch: "Swiss" };

export function marketCurrency(market: MarketChoice) {
  return CURRENCY[market];
}

export interface Price {
  amount: number;
  currency: string;
  /** live = current shop price here; estimate = another market's price. */
  kind: "live" | "estimate";
  /** For an estimate: the neighbouring country whose shop price is shown, or null for the US launch price. */
  from?: MarketKey | null;
  /** For an estimate: whether the amount was converted from another currency. */
  converted?: boolean;
  source?: string | null;
  url?: string | null;
  window?: string | null;
}

/** Used only when the data file has no exchange rates (an old file, or prices were skipped). */
const FALLBACK_RATES = { EUR: 0.92, CHF: 0.88 };

/** USD → currency rates: the ECB reference rates the data pipeline fetches on every update. */
export function fxRates(dataset: Pick<Dataset, "meta">): Record<string, number> {
  const rates = dataset.meta.exchange_rates;
  return {
    USD: 1,
    EUR: rates?.EUR || FALLBACK_RATES.EUR,
    CHF: rates?.CHF || FALLBACK_RATES.CHF,
  };
}

/** Converts between currencies; same-currency amounts are returned unchanged. */
export function convert(amount: number, from: string, to: string, fx: Record<string, number>) {
  return from === to ? amount : (amount / (fx[from] ?? 1)) * (fx[to] ?? 1);
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
  const currency = CURRENCY[market];
  if (market !== "us") {
    // No shop here: a neighbour's shop price is closer to reality than the US launch price.
    // Prefer a neighbour with the same currency (Germany <-> Austria), whose price needs no conversion.
    const neighbours = NEIGHBOURS.filter((other) => other !== market && helmet.listings[other]?.price != null).sort(
      (a, b) => Number(helmet.listings[b]!.currency === currency) - Number(helmet.listings[a]!.currency === currency),
    );
    const other = neighbours[0];
    if (other) {
      const listing = helmet.listings[other]!;
      const converted = listing.currency !== currency;
      const amount = converted ? Math.round(convert(listing.price!, listing.currency, currency, fx)) : listing.price!;
      return { amount, currency, kind: "estimate", from: other, converted, source: listing.source, url: listing.url };
    }
  }
  if (helmet.price_at_test_usd == null) return null;
  return {
    amount: Math.round(helmet.price_at_test_usd * (fx[currency] ?? 1)),
    currency,
    kind: market === "us" ? "live" : "estimate",
    from: null,
    converted: market !== "us",
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

/** "Top 10%" etc.: what a safety percentile means in words. */
export function scoreBand(safety: number) {
  if (safety >= 0.9) return "Top 10%";
  if (safety >= 0.75) return "Top 25%";
  if (safety >= 0.5) return "Above average";
  if (safety >= 0.25) return "Below average";
  return "Bottom 25%";
}

/** Lab percentiles further apart than this count as the labs disagreeing. */
const DISAGREE_SPREAD = 0.3;

export interface LabEvidence {
  labs: RatingSourceKey[];
  /** single = one lab; agree / disagree = how far apart the labs' percentiles are. */
  agreement: "none" | "single" | "agree" | "disagree";
  /** Newest test year across the labs, if known. */
  newestYear: number | null;
}

/** How solid a helmet's safety score is: how many labs tested it and whether they agree. */
export function evidenceFor(helmet: Helmet): LabEvidence {
  const labs = labsFor(helmet);
  const pcts = labs.map((k) => helmet.ratings[k]!.rank_pct!);
  const years = labs.map((k) => Number(String(helmet.ratings[k]!.test_year ?? "").slice(0, 4))).filter((y) => y > 0);
  const spread = pcts.length ? Math.max(...pcts) - Math.min(...pcts) : 0;
  return {
    labs,
    agreement: labs.length === 0 ? "none" : labs.length === 1 ? "single" : spread > DISAGREE_SPREAD ? "disagree" : "agree",
    newestYear: years.length ? Math.max(...years) : null,
  };
}

/** NSW Helmet STAR caps a helmet at 29/100 for a design fault; the reason in a few words, if any. */
export function nswPenalty(helmet: Helmet): string | null {
  const modifier = helmet.ratings.nsw_helmet_star?.modifier;
  if (!modifier) return null;
  if (/buckle/i.test(modifier)) return "part of the buckle is not permanently attached";
  if (/displacement/i.test(modifier)) return "the helmet can shift on the head in a crash";
  return "a test result fell below NSW's minimum";
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
  /** Kids' helmets: percentile among rated kids' helmets only, since they score lower as a group. */
  groupSafety: { pct: number; n: number } | null;
}

export interface FinderResult {
  ranked: Ranked[];
  picks: { kind: PickKind; item: Ranked }[];
  /** Price/safety frontier; prices in the market currency, like `band`. */
  frontier: Point[];
  /** Typical safety by price across the shortlist (market currency). */
  band: Bin[];
  /** Id of the frontier's knee (the "sweet spot"), if any. */
  kneeId: string | null;
  /** Why the pool is the size it is, for the empty/short-list states. */
  excluded: { reason: string; count: number }[];
  /** Total helmets with a safety rating for the chosen source. */
  ratedTotal: number;
  /** "Fast and safe": wind-tunnel-tested helmets of this riding style that no lab has crash-tested. */
  aeroOnly: Helmet[];
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

export function findHelmets(dataset: Dataset, goals: Goals, fx = fxRates(dataset)): FinderResult {
  const ride = RIDES.find((r) => r.key === goals.ride) ?? RIDES[RIDES.length - 1]!;
  const excluded = new Map<string, number>();
  const drop = (reason: string) => excluded.set(reason, (excluded.get(reason) ?? 0) + 1);

  const candidates: Omit<Ranked, "cheapness" | "score" | "rank" | "safetyRank" | "onFrontier" | "picks" | "groupSafety">[] = [];
  let ratedTotal = 0;
  const aeroOnly: Helmet[] = [];
  const inRide = (helmet: Helmet) =>
    (!ride.styles || ride.styles.includes(helmet.style)) && (!ride.requireNta8776 || helmet.features.nta8776);

  for (const helmet of dataset.helmets) {
    const safety = safetyFor(helmet, goals.safetySource);
    if (safety == null) {
      if (goals.priority === "aero" && helmet.aero?.rank_pct != null && inRide(helmet)) aeroOnly.push(helmet);
      continue;
    }
    ratedTotal += 1;
    if (!inRide(helmet)) continue;
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
    if (goals.multiLab && labsFor(helmet).length < 2) {
      drop("tested by one lab only");
      continue;
    }
    const aero = helmet.aero?.rank_pct ?? null;
    if (goals.priority === "aero" && aero == null) {
      drop("no wind-tunnel data");
      continue;
    }
    if (goals.aeroClass && aeroClassOf(helmet) !== goals.aeroClass) {
      drop("other aero class");
      continue;
    }
    if (goals.priority === "budget" && safety < SAFE_ENOUGH) {
      drop("below the safety bar");
      continue;
    }
    const priceUsd = price ? convert(price.amount, price.currency, "USD", fx) : null;
    candidates.push({ helmet, safety, price, priceUsd, aero, labs: labsFor(helmet) });
  }

  const prices = candidates.map((c) => c.priceUsd);
  // All candidate prices share the market currency, so the frontier and band use it directly.
  const points: Point[] = candidates
    .filter((c) => c.price != null)
    .map((c) => ({ id: c.helmet.id, price: c.price!.amount, safety: c.safety }));
  const pareto = paretoIds(points);
  const front = frontier(points);
  const weights = weightsFor(goals.priority);

  // Kids' helmets are also ranked among kids' helmets: as a group they score lower than adult ones.
  const kidsSafety = dataset.helmets
    .filter((h) => h.style === "Kids")
    .map((h) => safetyFor(h, goals.safetySource))
    .filter((s): s is number => s != null);
  // For money-driven priorities an estimated price only counts as "unknown": the budget pick and
  // best-value ranking must rest on prices people can actually pay.
  const liveOnly = goals.priority === "value" || goals.priority === "budget";

  const ranked: Ranked[] = candidates.map((c) => {
    const pricePct = percentileRank(prices, c.priceUsd);
    let cheapness = pricePct == null ? null : 1 - pricePct;
    if (liveOnly && c.price?.kind === "estimate" && cheapness != null) cheapness = Math.min(cheapness, UNKNOWN_CHEAPNESS);
    const groupSafety =
      c.helmet.style === "Kids" && kidsSafety.length > 1
        ? { pct: kidsSafety.filter((s) => s < c.safety).length / (kidsSafety.length - 1), n: kidsSafety.length }
        : null;
    const score =
      weights.safety * c.safety + weights.cheap * (cheapness ?? UNKNOWN_CHEAPNESS) + weights.aero * (c.aero ?? 0);
    return { ...c, cheapness, score, rank: 0, safetyRank: 0, onFrontier: pareto.has(c.helmet.id), picks: [], groupSafety };
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
  // The budget pick needs a price someone can pay today when any candidate has one.
  const budgetPool = ranked.filter((r) => r.safety >= SAFE_ENOUGH && r.priceUsd != null);
  const liveBudget = budgetPool.filter((r) => r.price?.kind === "live");
  addPick(
    "budget",
    (liveBudget.length ? liveBudget : budgetPool).sort((a, b) => a.priceUsd! - b.priceUsd! || b.safety - a.safety)[0],
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
    band: fairValueBand(points),
    kneeId: knee,
    excluded: [...excluded].map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count),
    ratedTotal,
    aeroOnly: aeroOnly.sort((a, b) => (b.aero?.rank_pct ?? 0) - (a.aero?.rank_pct ?? 0)),
  };
}

export type Evidence =
  | { kind: "rank" }
  | { kind: "peers"; ids: string[]; medianPrice: number; diff: number }
  | { kind: "frontier" }
  | { kind: "labs" }
  | { kind: "aero" };

export interface Reason {
  tone: "good" | "neutral" | "caution";
  text: string;
  /** Which graphic backs this claim. */
  evidence?: Evidence;
}

/** Similarly safe helmets: within this many percentile points. */
export const PEER_WINDOW = 0.1;

/**
 * Helmets on the shortlist with similar safety and a known price, and their median price.
 * Shared by the "% cheaper" reason and its chart so both always use the same set.
 */
export function peersOf(item: Ranked, result: FinderResult) {
  const peers = result.ranked.filter(
    (r) => r !== item && r.price != null && Math.abs(r.safety - item.safety) <= PEER_WINDOW,
  );
  const medianPrice = median(peers.map((r) => r.price!.amount));
  const diff = medianPrice != null && item.price ? (item.price.amount - medianPrice) / medianPrice : null;
  return { peers, medianPrice, diff };
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
    evidence: { kind: "rank" },
  });

  if (item.groupSafety) {
    const kidsPct = Math.round(item.groupSafety.pct * 100);
    reasons.push({
      tone: item.groupSafety.pct >= 0.75 ? "good" : item.groupSafety.pct >= 0.4 ? "neutral" : "caution",
      text: `Safer than ${kidsPct}% of the ${item.groupSafety.n} lab-tested kids' helmets`,
    });
  }

  if (item.labs.length > 1) {
    reasons.push({
      tone: "good",
      text: `Confirmed by ${item.labs.length} labs: ${item.labs.map(labLabel).join(", ")}`,
      evidence: { kind: "labs" },
    });
  } else if (item.labs.length === 1) {
    // One lab is thin evidence; on the pick cards (which show only good and caution lines) it should be visible.
    reasons.push({ tone: "caution", text: `Tested by ${labLabel(item.labs[0]!)} only`, evidence: { kind: "labs" } });
  }

  const { peers, medianPrice, diff } = peersOf(item, result);
  if (medianPrice != null && diff != null && peers.length >= 3) {
    const evidence: Evidence = { kind: "peers", ids: peers.map((r) => r.helmet.id), medianPrice, diff };
    if (diff <= -0.15) {
      reasons.push({ tone: "good", text: `${Math.round(-diff * 100)}% cheaper than similarly safe helmets`, evidence });
    } else if (diff >= 0.25) {
      reasons.push({ tone: "caution", text: `${Math.round(diff * 100)}% pricier than similarly safe helmets`, evidence });
    }
  }

  if (item.onFrontier) {
    reasons.push({ tone: "good", text: "No helmet on your list is both safer and cheaper", evidence: { kind: "frontier" } });
  }

  const penalty = nswPenalty(item.helmet);
  if (penalty) reasons.push({ tone: "caution", text: `NSW capped its score: ${penalty}`, evidence: { kind: "labs" } });

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
      evidence: { kind: "aero" },
    });
  }

  if (item.price?.kind === "estimate") {
    const text = item.price.from
      ? `No shop price in this country; showing the ${MARKET_NAME[item.price.from]} price${item.price.converted ? ", converted" : ""}`
      : "No current shop price found; showing the converted US price at test time";
    reasons.push({ tone: "caution", text });
  }

  const year = Number(item.helmet.test_year);
  if (year && year <= 2019) {
    reasons.push({ tone: "caution", text: `Tested in ${year}; this model may have been replaced` });
  }

  return reasons;
}
