import { describe, expect, it } from "vitest";
import { brandRows, countryPair, spearman, trendOf, type Valued } from "./chartData";
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

describe("trendOf", () => {
  const item = (year: string, value: number) => ({ helmet: { id: year + value, test_year: year } as Helmet, value });

  it("compares the recent helmets' median with the older ones", () => {
    const items = [item("2018", 40), item("2019", 50), item("2025", 70), item("2026", 80)];
    expect(trendOf(items, 2025)).toEqual({ value: 75, n: 2, delta: 30 });
  });

  it("needs two recent helmets, and two older ones for a direction", () => {
    expect(trendOf([item("2019", 40), item("2026", 80)], 2025)).toBeNull();
    expect(trendOf([item("2025", 70), item("2026", 80)], 2025)).toEqual({ value: 75, n: 2, delta: null });
  });

  it("leaves undated helmets out of both groups", () => {
    const undated = [10, 20].map((v) => ({ helmet: { id: `u${v}`, test_year: null } as Helmet, value: v }));
    expect(trendOf([item("2025", 70), item("2026", 80), ...undated], 2025)).toEqual({ value: 75, n: 2, delta: null });
  });
});
