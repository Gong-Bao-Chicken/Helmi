/** Pure numeric helpers: percentiles, price/safety Pareto frontier, knee detection. */

export function percentileRank(values: readonly (number | null | undefined)[], value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return null;
  const sorted = values.filter((v): v is number => v != null && !Number.isNaN(v));
  if (!sorted.length) return null;
  let below = 0;
  let equal = 0;
  for (const v of sorted) {
    if (v < value) below += 1;
    else if (v === value) equal += 1;
  }
  return (below + equal * 0.5) / sorted.length;
}

export function median(values: readonly number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
}

export interface Point {
  id: string;
  /** Price in a common currency; lower is better. */
  price: number;
  /** Safety on a 0–1 scale; higher is better. */
  safety: number;
}

const EPS_SAFETY = 0.03;
const EPS_PRICE_ABS = 10;
const EPS_PRICE_FRAC = 0.05;

function priceEpsilon(price: number) {
  return Math.max(EPS_PRICE_ABS, price * EPS_PRICE_FRAC);
}

/**
 * Helmets not dominated by any other (one that is at least as safe and as cheap, and clearly
 * better on one axis). Small tolerances stop near-identical points from knocking each other out.
 */
export function paretoIds(points: readonly Point[]): Set<string> {
  const ids = new Set<string>();
  for (const a of points) {
    const epsP = priceEpsilon(a.price);
    const dominated = points.some(
      (b) =>
        b.id !== a.id &&
        b.safety >= a.safety - EPS_SAFETY &&
        b.price <= a.price + epsP &&
        (b.safety >= a.safety + EPS_SAFETY || b.price <= a.price - epsP),
    );
    if (!dominated) ids.add(a.id);
  }
  return ids;
}

/** Frontier sorted by price, keeping only steps that buy more safety. */
export function frontier(points: readonly Point[]): Point[] {
  const ids = paretoIds(points);
  const sorted = points.filter((p) => ids.has(p.id)).sort((a, b) => a.price - b.price || b.safety - a.safety);
  const out: Point[] = [];
  for (const p of sorted) {
    if (!out.length || p.safety > out[out.length - 1]!.safety) out.push(p);
  }
  return out;
}

/**
 * The frontier point where extra money stops buying much extra safety: the largest drop in
 * slope between neighbouring frontier segments. Prices are scaled to 0–1 so slopes compare fairly.
 */
export function kneeId(front: readonly Point[]): string | null {
  if (front.length < 3) return front[front.length - 1]?.id ?? null;
  const minP = front[0]!.price;
  const span = front[front.length - 1]!.price - minP || 1;
  const x = (p: Point) => (p.price - minP) / span;
  let best: string | null = null;
  let bestDrop = -Infinity;
  for (let i = 1; i < front.length - 1; i += 1) {
    const [prev, curr, next] = [front[i - 1]!, front[i]!, front[i + 1]!];
    const dx1 = x(curr) - x(prev);
    const dx2 = x(next) - x(curr);
    if (dx1 <= 0 || dx2 <= 0) continue;
    const drop = Math.atan((curr.safety - prev.safety) / dx1) - Math.atan((next.safety - curr.safety) / dx2);
    if (drop > bestDrop) {
      bestDrop = drop;
      best = curr.id;
    }
  }
  return best;
}
