/** Pure derivations for the Charts page: each function turns the dataset into one chart's rows. */
import { priceFor, safetyFor, type MarketChoice, type Price, type SafetySource } from "./finder";
import { median } from "./scoring";
import type { Dataset, Helmet, MarketKey, RatingSourceKey } from "./types";

export interface ChartFilters {
  market: MarketChoice;
  source: SafetySource;
  euOnly: boolean;
}

export const DEFAULT_CHART_FILTERS: ChartFilters = { market: "de", source: "fused", euOnly: true };

export interface Valued {
  helmet: Helmet;
  value: number;
}

export function inScope(helmet: Helmet, filters: ChartFilters) {
  return !filters.euOnly || filters.market === "us" || helmet.european_market;
}

/** Helmets in scope with a safety percentile (0–100) for the chosen source. */
export function ratedHelmets(dataset: Dataset, filters: ChartFilters): Valued[] {
  const out: Valued[] = [];
  for (const helmet of dataset.helmets) {
    if (!inScope(helmet, filters)) continue;
    const s = safetyFor(helmet, filters.source);
    if (s != null) out.push({ helmet, value: s * 100 });
  }
  return out;
}

export interface PricePoint {
  helmet: Helmet;
  price: Price;
  /** 0–100 safety percentile. */
  safety: number;
}

export function priceSafetyPoints(dataset: Dataset, filters: ChartFilters, fx: Record<string, number>, includeEstimates: boolean) {
  const out: PricePoint[] = [];
  for (const { helmet, value } of ratedHelmets(dataset, filters)) {
    const price = priceFor(helmet, filters.market, fx);
    if (!price || (price.kind === "estimate" && !includeEstimates)) continue;
    out.push({ helmet, price, safety: value });
  }
  return out;
}

export interface Row {
  key: string;
  label: string;
  hint?: string;
  items: Valued[];
}

export function groupRows(items: Valued[], keyOf: (h: Helmet) => string | null | undefined, order: { key: string; label: string; hint?: string }[]): Row[] {
  return order.map((o) => ({ ...o, items: items.filter((i) => keyOf(i.helmet) === o.key) })).filter((r) => r.items.length > 0);
}

export const rowMedian = (row: Row) => median(row.items.map((i) => i.value)) ?? 0;

export function sortByMedian(rows: Row[]) {
  return [...rows].sort((a, b) => rowMedian(b) - rowMedian(a));
}

/** Virginia Tech percentile by the year VT tested the helmet, oldest first. */
export function vtByYear(dataset: Dataset, filters: ChartFilters): Row[] {
  const byYear = new Map<string, Valued[]>();
  for (const helmet of dataset.helmets) {
    const vt = helmet.ratings.virginia_tech;
    if (!inScope(helmet, filters) || vt?.rank_pct == null || !vt.test_year) continue;
    const year = String(vt.test_year).slice(0, 4);
    byYear.set(year, [...(byYear.get(year) ?? []), { helmet, value: vt.rank_pct * 100 }]);
  }
  return [...byYear.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([year, items]) => ({ key: year, label: year, items }));
}

/** Brands with at least `minCount` rated helmets, safest median first. */
export function brandRows(items: Valued[], minCount = 6): Row[] {
  const byBrand = new Map<string, Valued[]>();
  for (const item of items) {
    const key = (item.helmet.brand_key ?? item.helmet.brand).toLowerCase();
    byBrand.set(key, [...(byBrand.get(key) ?? []), item]);
  }
  return sortByMedian(
    [...byBrand.entries()]
      .filter(([, list]) => list.length >= minCount)
      .map(([key, list]) => ({ key, label: list[0]!.helmet.brand, items: list })),
  );
}

const IMPACTS: { key: string; label: string }[] = [
  { key: "choc-frontal", label: "Front" },
  { key: "choc-frontal-oblique", label: "Front, angled" },
  { key: "choc-lateral", label: "Side" },
  { key: "choc-lateral-oblique-1", label: "Side, angled (1)" },
  { key: "choc-lateral-oblique-2-", label: "Side, angled (2)" },
  { key: "choc-arriere", label: "Rear" },
];

/** CERTIMOOV's per-impact scores (0–5, higher is better), one row per impact location. */
export function certimoovImpactRows(dataset: Dataset, filters: ChartFilters): Row[] {
  const rows = IMPACTS.map((impact) => ({ ...impact, items: [] as Valued[] }));
  for (const helmet of dataset.helmets) {
    const scores = helmet.ratings.certimoov?.impact_scores;
    if (!scores || !inScope(helmet, filters)) continue;
    for (const row of rows) {
      const v = scores[row.key];
      if (v != null) row.items.push({ helmet, value: v });
    }
  }
  return sortByMedian(rows.filter((r) => r.items.length));
}

export interface XY {
  helmet: Helmet;
  x: number;
  y: number;
}

/** Spearman rank correlation (average ranks for ties). */
export function spearman(pairs: readonly { x: number; y: number }[]): number | null {
  const n = pairs.length;
  if (n < 3) return null;
  const rank = (values: number[]) => {
    const order = values.map((v, i) => [v, i] as const).sort((a, b) => a[0] - b[0]);
    const ranks = new Array<number>(n);
    for (let i = 0; i < n; ) {
      let j = i;
      while (j + 1 < n && order[j + 1]![0] === order[i]![0]) j += 1;
      for (let k = i; k <= j; k += 1) ranks[order[k]![1]] = (i + j) / 2;
      i = j + 1;
    }
    return ranks;
  };
  const rx = rank(pairs.map((p) => p.x));
  const ry = rank(pairs.map((p) => p.y));
  const mean = (n - 1) / 2;
  let cov = 0;
  let vx = 0;
  let vy = 0;
  for (let i = 0; i < n; i += 1) {
    const dx = rx[i]! - mean;
    const dy = ry[i]! - mean;
    cov += dx * dy;
    vx += dx * dx;
    vy += dy * dy;
  }
  return vx && vy ? cov / Math.sqrt(vx * vy) : null;
}

export interface LabPair {
  a: RatingSourceKey;
  b: RatingSourceKey;
  points: XY[];
  rho: number | null;
}

/** Helmets rated by both labs of each pair, as percentiles (0–100). Pairs with too few helmets are dropped. */
export function labPairs(dataset: Dataset, filters: ChartFilters, minCount = 8): LabPair[] {
  const labs: RatingSourceKey[] = ["virginia_tech", "certimoov", "nsw_helmet_star", "folksam"];
  const out: LabPair[] = [];
  for (let i = 0; i < labs.length; i += 1) {
    for (let j = i + 1; j < labs.length; j += 1) {
      const [a, b] = [labs[i]!, labs[j]!];
      const points: XY[] = [];
      for (const helmet of dataset.helmets) {
        const pa = helmet.ratings[a]?.rank_pct;
        const pb = helmet.ratings[b]?.rank_pct;
        if (pa != null && pb != null && inScope(helmet, filters)) points.push({ helmet, x: pa * 100, y: pb * 100 });
      }
      if (points.length >= minCount) out.push({ a, b, points, rho: spearman(points) });
    }
  }
  return out.sort((p, q) => q.points.length - p.points.length);
}

/** How many helmets each lab tested, and how many were tested by two or more. */
export function labCoverage(dataset: Dataset, filters: ChartFilters) {
  const labs: RatingSourceKey[] = ["virginia_tech", "certimoov", "nsw_helmet_star", "folksam"];
  const counts = new Map(labs.map((l) => [l, 0]));
  let multi = 0;
  let any = 0;
  for (const helmet of dataset.helmets) {
    if (!inScope(helmet, filters)) continue;
    const tested = labs.filter((l) => helmet.ratings[l]?.rank_pct != null);
    for (const l of tested) counts.set(l, counts.get(l)! + 1);
    if (tested.length) any += 1;
    if (tested.length > 1) multi += 1;
  }
  return { counts: labs.map((key) => ({ key, count: counts.get(key)! })), multi, any };
}

/** VT low- vs high-speed impact scores (lower is safer). */
export function vtImpactPoints(dataset: Dataset, filters: ChartFilters): XY[] {
  const out: XY[] = [];
  for (const helmet of dataset.helmets) {
    const vt = helmet.ratings.virginia_tech;
    if (!inScope(helmet, filters) || vt?.score_low_impact == null || vt.score_high_impact == null) continue;
    out.push({ helmet, x: vt.score_low_impact, y: vt.score_high_impact });
  }
  return out;
}

/** Aero percentile (higher = faster) against safety percentile, for wind-tunnel-tested helmets. */
export function aeroSafetyPoints(dataset: Dataset, filters: ChartFilters): XY[] {
  const out: XY[] = [];
  for (const { helmet, value } of ratedHelmets(dataset, filters)) {
    const aero = helmet.aero?.rank_pct;
    if (aero != null) out.push({ helmet, x: aero * 100, y: value });
  }
  return out;
}

/** Current shop price against the US price at test time, as a % change (negative = cheaper now). */
export function priceVsLaunch(dataset: Dataset, filters: ChartFilters, fx: Record<string, number>): Valued[] {
  const out: Valued[] = [];
  for (const helmet of dataset.helmets) {
    if (!inScope(helmet, filters) || !helmet.price_at_test_usd) continue;
    const price = priceFor(helmet, filters.market, fx);
    if (!price || price.kind !== "live" || filters.market === "us") continue;
    const usd = price.amount / (fx[price.currency] ?? 1);
    out.push({ helmet, value: (usd / helmet.price_at_test_usd - 1) * 100 });
  }
  return out;
}

export const MARKET_LABEL: Record<MarketKey, string> = { de: "Germany", at: "Austria", ch: "Switzerland" };

/** Today's shop price against the US launch price, one row per country. Only real shop prices count. */
export function priceVsLaunchByMarket(dataset: Dataset, filters: ChartFilters, fx: Record<string, number>): Row[] {
  return (Object.keys(MARKET_LABEL) as MarketKey[])
    .map((market) => ({ key: market, label: MARKET_LABEL[market], items: priceVsLaunch(dataset, { ...filters, market }, fx) }))
    .filter((row) => row.items.length > 0);
}

export interface PairPoint extends XY {
  /** Shop prices in each country's own currency. */
  a: { amount: number; currency: string };
  b: { amount: number; currency: string };
}

/**
 * The same helmet's shop price in two countries, both converted to euro so the diagonal means
 * "same price" (x = country a, y = country b). Only helmets with a real shop price in both.
 */
export function countryPair(dataset: Dataset, a: MarketKey, b: MarketKey, fx: Record<string, number>): PairPoint[] {
  const toEur = (amount: number, currency: string) => (amount / (fx[currency] ?? 1)) * (fx.EUR ?? 1);
  const out: PairPoint[] = [];
  for (const helmet of dataset.helmets) {
    const la = helmet.listings[a];
    const lb = helmet.listings[b];
    if (la?.price == null || lb?.price == null) continue;
    out.push({
      helmet,
      x: toEur(la.price, la.currency),
      y: toEur(lb.price, lb.currency),
      a: { amount: la.price, currency: la.currency },
      b: { amount: lb.price, currency: lb.currency },
    });
  }
  return out;
}

export interface HistBin {
  x0: number;
  x1: number;
  count: number;
}

export function histogram(values: readonly number[], step: number, clamp: [number, number]): HistBin[] {
  const [lo, hi] = clamp;
  const bins: HistBin[] = [];
  for (let x0 = lo; x0 < hi; x0 += step) bins.push({ x0, x1: x0 + step, count: 0 });
  for (const v of values) {
    const c = Math.min(hi - 1e-9, Math.max(lo, v));
    bins[Math.floor((c - lo) / step)]!.count += 1;
  }
  return bins;
}
