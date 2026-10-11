import { describe, expect, it } from "vitest";
import { frontier, kneeId, median, paretoIds, percentileRank } from "./scoring";

describe("percentileRank", () => {
  const prices = [50, 100, 150, 200];
  it("uses mid-rank for ties and bounds", () => {
    expect(percentileRank(prices, 50)).toBe(0.125);
    expect(percentileRank(prices, 200)).toBe(0.875);
  });
  it("ignores missing values", () => {
    expect(percentileRank([null, 10, undefined, 20], 20)).toBe(0.75);
    expect(percentileRank(prices, null)).toBeNull();
    expect(percentileRank([], 5)).toBeNull();
  });
});

describe("median", () => {
  it("handles odd, even and empty inputs", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 2, 3])).toBe(2.5);
    expect(median([])).toBeNull();
  });
});

describe("pareto frontier", () => {
  const points = [
    { id: "cheap", price: 50, safety: 0.5 },
    { id: "mid", price: 100, safety: 0.72 },
    { id: "dominated", price: 120, safety: 0.6 },
    { id: "top", price: 200, safety: 0.85 },
  ];
  it("drops helmets that are both pricier and less safe than another", () => {
    expect([...paretoIds(points)].sort()).toEqual(["cheap", "mid", "top"]);
  });
  it("returns the frontier sorted by price", () => {
    expect(frontier(points).map((p) => p.id)).toEqual(["cheap", "mid", "top"]);
  });
  it("tolerates near-identical points", () => {
    const twins = [
      { id: "a", price: 100, safety: 0.8 },
      { id: "b", price: 102, safety: 0.79 },
    ];
    expect(paretoIds(twins).size).toBe(2);
  });
});

describe("kneeId", () => {
  it("picks the bend point, not a straight segment", () => {
    const front = [
      { id: "a", price: 50, safety: 0.5 },
      { id: "b", price: 100, safety: 0.72 },
      { id: "c", price: 150, safety: 0.8 },
      { id: "d", price: 200, safety: 0.85 },
    ];
    expect(kneeId(front)).toBe("b");
  });
  it("falls back to the safest point on short frontiers", () => {
    expect(kneeId([{ id: "x", price: 1, safety: 0.1 }, { id: "y", price: 2, safety: 0.9 }])).toBe("y");
    expect(kneeId([])).toBeNull();
  });
});
