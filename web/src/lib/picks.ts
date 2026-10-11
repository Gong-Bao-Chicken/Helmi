import type { PickKind } from "./finder";

export const PICK_META: Record<PickKind, { label: string; hint: string }> = {
  best: { label: "Best match", hint: "Top of the ranking for your goals" },
  safest: { label: "Safest", hint: "Highest lab safety score on your list" },
  value: { label: "Sweet spot", hint: "Where spending more stops buying much more safety" },
  budget: { label: "Budget pick", hint: "Cheapest helmet with top-40% safety" },
  aero: { label: "Fastest safe", hint: "Best wind-tunnel result with above-median safety" },
  alt: { label: "Runner-up", hint: "Next best for your goals" },
};
