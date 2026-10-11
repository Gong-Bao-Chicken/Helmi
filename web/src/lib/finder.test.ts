import { describe, expect, it } from "vitest";
import { DEFAULT_GOALS, explain, findHelmets, peersOf, priceFor } from "./finder";
import type { Dataset, Helmet } from "./types";

const features = {
  mips_standard: false,
  mips_spherical: false,
  wavecel: false,
  spin: false,
  sweet_2vi: false,
  koroyd: false,
  rotational_protection: false,
  nta8776: false,
  asia_fit: false,
  round_fit: false,
};

function helmet(id: string, opts: Partial<Helmet> & { safety: number; eur?: number; usd?: number }): Helmet {
  const { safety, eur, usd, ...rest } = opts;
  return {
    id,
    brand: "Brand",
    model: id,
    search_text: id,
    score: null,
    ratings: {
      virginia_tech: { rank_pct: safety },
      fused: { rank_pct: safety, sources: ["virginia_tech"], weights: { virginia_tech: 1 } },
    },
    style: "Road",
    test_year: "2024",
    certifications: "CPSC",
    price_at_test_usd: usd ?? 100,
    features,
    feature_labels: [],
    european_market: true,
    listings: eur == null ? {} : { de: { price: eur, currency: "EUR", rating: null, review_count: null, url: null, source: "geizhals" } },
    protection_group: "none",
    ...rest,
  };
}

function dataset(helmets: Helmet[]): Dataset {
  return {
    meta: { generated_at: "2026-01-01", helmet_count_total: helmets.length },
    filters: { rating_sources: [], styles: [], protection_groups: [], protection_technologies: [], markets: [], aero_tiers: [], aero_sources: [] },
    helmets,
  };
}

const fx = { USD: 1, EUR: 0.9, CHF: 0.85 };

describe("priceFor", () => {
  it("prefers a live shop price and falls back to a converted test price", () => {
    expect(priceFor(helmet("a", { safety: 0.5, eur: 80 }), "de", fx)).toMatchObject({ amount: 80, kind: "live" });
    expect(priceFor(helmet("b", { safety: 0.5, usd: 100 }), "de", fx)).toMatchObject({ amount: 90, kind: "estimate" });
    expect(priceFor(helmet("c", { safety: 0.5, usd: 100 }), "us", fx)).toMatchObject({ amount: 100, currency: "USD" });
  });
});

describe("findHelmets", () => {
  const data = dataset([
    helmet("cheap-ok", { safety: 0.62, eur: 40 }),
    helmet("value", { safety: 0.9, eur: 90 }),
    helmet("premium", { safety: 0.95, eur: 280 }),
    helmet("poor", { safety: 0.2, eur: 150 }),
    helmet("mtb", { safety: 0.99, eur: 60, style: "Mountain" }),
    helmet("us-only", { safety: 0.97, eur: 50, european_market: false }),
  ]);

  it("filters by riding style and EU market", () => {
    const ids = findHelmets(data, { ...DEFAULT_GOALS, ride: "road" }, fx).ranked.map((r) => r.helmet.id);
    expect(ids).not.toContain("mtb");
    expect(ids).not.toContain("us-only");
    expect(ids[0]).toBe("value");
  });

  it("respects the budget in market currency", () => {
    const ids = findHelmets(data, { ...DEFAULT_GOALS, ride: "road", budget: 100 }, fx).ranked.map((r) => r.helmet.id);
    expect(ids.sort()).toEqual(["cheap-ok", "value"]);
  });

  it("maximum protection puts the safest helmet first", () => {
    const res = findHelmets(data, { ...DEFAULT_GOALS, ride: "road", priority: "protection" }, fx);
    expect(res.ranked[0]!.helmet.id).toBe("premium");
  });

  it("budget priority enforces the safety bar and sorts by price", () => {
    const res = findHelmets(data, { ...DEFAULT_GOALS, ride: "road", priority: "budget" }, fx);
    expect(res.ranked.map((r) => r.helmet.id)).toEqual(["cheap-ok", "value", "premium"]);
    expect(res.excluded).toContainEqual({ reason: "below the safety bar", count: 1 });
  });

  it("labels picks and explains them", () => {
    const res = findHelmets(data, { ...DEFAULT_GOALS, ride: "road" }, fx);
    const kinds = Object.fromEntries(res.picks.map((p) => [p.kind, p.item.helmet.id]));
    expect(kinds.best).toBe("value");
    expect(kinds.safest).toBe("premium");
    expect(kinds.budget).toBe("cheap-ok");
    const reasons = explain(res.ranked[0]!, res, (k) => k).map((r) => r.text);
    expect(reasons[0]).toMatch(/Safer than 90%/);
    expect(reasons).toContain("No helmet on your list is both safer and cheaper");
  });
});

describe("evidence", () => {
  const data = dataset([
    helmet("target", { safety: 0.8, eur: 50 }),
    helmet("p1", { safety: 0.82, eur: 120 }),
    helmet("p2", { safety: 0.75, eur: 100 }),
    helmet("p3", { safety: 0.88, eur: 140 }),
    helmet("far", { safety: 0.3, eur: 20 }),
  ]);
  const res = findHelmets(data, { ...DEFAULT_GOALS, ride: "road" }, fx);
  const target = res.ranked.find((r) => r.helmet.id === "target")!;

  it("peersOf uses the safety window and market-currency median", () => {
    const { peers, medianPrice } = peersOf(target, res);
    expect(peers.map((p) => p.helmet.id).sort()).toEqual(["p1", "p2", "p3"]);
    expect(medianPrice).toBe(120);
  });

  it("the % cheaper claim carries the same peer set as its evidence", () => {
    const reason = explain(target, res, (k) => k).find((r) => r.evidence?.kind === "peers")!;
    expect(reason.text).toBe("58% cheaper than similarly safe helmets");
    expect(reason.evidence).toMatchObject({ kind: "peers", medianPrice: 120 });
    if (reason.evidence?.kind === "peers") expect(reason.evidence.ids.sort()).toEqual(["p1", "p2", "p3"]);
  });

  it("tags rank and frontier reasons", () => {
    const kinds = explain(target, res, (k) => k).map((r) => r.evidence?.kind);
    expect(kinds).toContain("rank");
    expect(kinds).toContain("frontier");
  });
});
