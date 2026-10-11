import { createRequire } from "module";
import assert from "assert";

const require = createRequire(import.meta.url);
const {
  percentileRank,
  computeValueFromPercentiles,
  priceNormInCohort,
  findKneeId,
} = require("./scoring.js");

const prices = [50, 100, 150, 200];

assert.strictEqual(percentileRank(prices, 50), 0.125);
assert.strictEqual(percentileRank(prices, 200), 0.875);

const safeCheap = computeValueFromPercentiles(0.9, percentileRank(prices, 50));
const safeExpensive = computeValueFromPercentiles(0.9, percentileRank(prices, 200));
assert.ok(
  safeCheap.valueScore > safeExpensive.valueScore,
  "safe+cheap should beat safe+expensive"
);
assert.ok(safeCheap.valueIndex > safeExpensive.valueIndex);

assert.strictEqual(priceNormInCohort(50, prices), 1);
assert.strictEqual(priceNormInCohort(200, prices), 0);

const frontier = [
  { id: "a", price: 50, safety: 0.5 },
  { id: "b", price: 100, safety: 0.72 },
  { id: "c", price: 150, safety: 0.8 },
  { id: "d", price: 200, safety: 0.85 },
];
const knee = findKneeId(
  frontier,
  (h) => h.price,
  (h) => h.safety,
  true
);
assert.strictEqual(knee, "b", "knee should be the bend point, not a straight segment");

console.log("scoring.test.mjs: all assertions passed");
