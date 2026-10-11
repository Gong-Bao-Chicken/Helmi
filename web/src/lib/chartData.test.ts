import { describe, expect, it } from "vitest";
import { brandRows, countryPair, histogram, spearman, type Valued } from "./chartData";
import type { Dataset, Helmet } from "./types";

const helmet = (id: string, brand: string) => ({ id, brand }) as Helmet;

describe("spearman", () => {
  it("is 1 for a monotonic relationship and -1 for a reversed one", () => {
    const up = [1, 2, 3, 4, 5].map((x) => ({ x, y: x * x }));
    expect(spearman(up)).toBeCloseTo(1);
    expect(spearman(up.map((p) => ({ x: p.x, y: -p.y })))).toBeCloseTo(-1);
  });

  it("handles ties with average ranks and needs three points", () => {
    expect(spearman([{ x: 1, y: 1 }, { x: 2, y: 2 }])).toBeNull();
    const r = spearman([
      { x: 1, y: 2 },
      { x: 2, y: 2 },
      { x: 3, y: 3 },
    ]);
    expect(r).toBeGreaterThan(0.8);
  });
});

describe("histogram", () => {
  it("bins values and clamps the tails into the end bins", () => {
    const bins = histogram([-500, -15, -5, 5, 999], 10, [-20, 20]);
    expect(bins.map((b) => b.count)).toEqual([2, 1, 1, 1]);
  });
});

describe("brandRows", () => {
  it("keeps brands with enough helmets, safest median first", () => {
    const items: Valued[] = [
      ...[10, 20, 30].map((v, i) => ({ helmet: helmet(`a${i}`, "Alpha"), value: v })),
      ...[70, 80, 90].map((v, i) => ({ helmet: helmet(`b${i}`, "Beta"), value: v })),
      { helmet: helmet("c0", "Gamma"), value: 99 },
    ];
    expect(brandRows(items, 3).map((r) => r.label)).toEqual(["Beta", "Alpha"]);
  });
});

describe("countryPair", () => {
  const listing = (price: number | null, currency: string) => ({ price, currency, rating: null, review_count: null, url: null, source: "x" });
  const ds = {
    helmets: [
      { id: "a", listings: { de: listing(90, "EUR"), ch: listing(170, "CHF") } },
      { id: "b", listings: { de: listing(90, "EUR"), ch: listing(null, "CHF") } },
      { id: "c", listings: { de: listing(90, "EUR") } },
    ],
  } as unknown as Dataset;

  it("only pairs helmets with a real price in both countries, converted to euro", () => {
    const pts = countryPair(ds, "de", "ch", { USD: 1, EUR: 0.9, CHF: 0.85 });
    expect(pts.map((p) => p.helmet.id)).toEqual(["a"]);
    expect(pts[0]!.x).toBeCloseTo(90);
    expect(pts[0]!.y).toBeCloseTo(180);
    expect(pts[0]!.b).toEqual({ amount: 170, currency: "CHF" });
  });
});
