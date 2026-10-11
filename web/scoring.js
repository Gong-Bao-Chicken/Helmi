/**
 * Pure scoring helpers for helmet value, price cohorts, and knee detection.
 * Loaded by index.html; tested via scoring.test.mjs (node).
 */
(function (root) {
  function percentileRank(values, value) {
    const sorted = values.filter((v) => v != null && !Number.isNaN(v)).sort((a, b) => a - b);
    if (!sorted.length || value == null || Number.isNaN(value)) return null;
    let below = 0;
    let equal = 0;
    for (const v of sorted) {
      if (v < value) below += 1;
      else if (v === value) equal += 1;
    }
    return (below + equal * 0.5) / sorted.length;
  }

  /** rawPricePct = expensiveness percentile (1 = most expensive). Higher valueIndex = better deal. */
  function computeValueFromPercentiles(safetyPct, rawPricePct) {
    const cheapnessPct = rawPricePct == null ? null : 1 - rawPricePct;
    let valueIndex = null;
    if (safetyPct != null && rawPricePct != null) {
      valueIndex = safetyPct - rawPricePct;
    } else if (safetyPct != null) {
      valueIndex = safetyPct;
    } else if (rawPricePct != null) {
      valueIndex = -rawPricePct;
    }
    const valueScore = valueIndex == null ? null : Math.round((valueIndex + 1) * 50);
    return { valueIndex, valueScore, cheapnessPct };
  }

  function priceNormInCohort(price, prices) {
    if (price == null || !prices.length) return null;
    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    if (maxP === minP) return 1;
    return (maxP - price) / (maxP - minP);
  }

  function splitPriceCohorts(helmets, hasLivePrice, getPrice) {
    const live = [];
    const test = [];
    for (const helmet of helmets) {
      const price = getPrice(helmet);
      if (price == null) continue;
      if (hasLivePrice(helmet)) live.push(helmet);
      else test.push(helmet);
    }
    return { live, test };
  }

  function assignPriceNorms(helmets, hasLivePrice, getPrice) {
    const norms = new Map();
    const { live, test } = splitPriceCohorts(helmets, hasLivePrice, getPrice);
    for (const cohort of [live, test]) {
      if (!cohort.length) continue;
      const prices = cohort.map((h) => getPrice(h));
      for (const helmet of cohort) {
        norms.set(helmet.id, priceNormInCohort(getPrice(helmet), prices));
      }
    }
    return norms;
  }

  /** Pick frontier point with largest slope change (knee), not the straightest segment. */
  function findKneeId(frontier, getPrice, getSafety, higherIsSafer) {
    if (frontier.length < 3) return frontier[0]?.id ?? null;
    let bestKnee = null;
    let bestAngle = -Infinity;
    for (let i = 1; i < frontier.length - 1; i += 1) {
      const prev = frontier[i - 1];
      const curr = frontier[i];
      const next = frontier[i + 1];
      const dx1 = getPrice(curr) - getPrice(prev);
      const dx2 = getPrice(next) - getPrice(curr);
      const dy1 = higherIsSafer ? getSafety(curr) - getSafety(prev) : getSafety(prev) - getSafety(curr);
      const dy2 = higherIsSafer ? getSafety(next) - getSafety(curr) : getSafety(curr) - getSafety(next);
      if (dx1 <= 0 || dx2 <= 0 || dy1 <= 0 || dy2 <= 0) continue;
      const angle = Math.abs(Math.atan2(dy2 / dx2, 1) - Math.atan2(dy1 / dx1, 1));
      if (angle > bestAngle) {
        bestAngle = angle;
        bestKnee = curr;
      }
    }
    return bestKnee?.id ?? null;
  }

  const api = {
    percentileRank,
    computeValueFromPercentiles,
    priceNormInCohort,
    splitPriceCohorts,
    assignPriceNorms,
    findKneeId,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.HelmetScoring = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
