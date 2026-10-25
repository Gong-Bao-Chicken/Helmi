/** Turning wind-tunnel watts into race time. */
import type { AeroSourceResult } from "./types";

export const RACE_PRESETS = [
  { key: "tt40", label: "40 km TT", distanceKm: 40, speedKph: 42 },
  { key: "half", label: "70.3 bike (90 km)", distanceKm: 90, speedKph: 36 },
  { key: "full", label: "Ironman bike (180 km)", distanceKm: 180, speedKph: 34 },
] as const;

/**
 * Seconds saved against the test's baseline helmet over `distanceKm` at `speedKph`, holding power constant.
 * Aero drag power grows with speed cubed, so the share of power saved is the same at any speed; at the same
 * power the rider goes faster by the cube root of that share.
 */
export function timeSaved(src: AeroSourceResult, distanceKm: number, speedKph: number) {
  const total = src.drag_watts_40kph;
  const saved = src.watts_saved;
  if (!total || saved == null || distanceKm <= 0 || speedKph <= 0) return null;
  const share = saved / total;
  const hours = distanceKm / speedKph;
  const seconds = hours * 3600 * (1 - Math.cbrt(1 - share));
  return { seconds, withinError: src.error_margin_w != null && Math.abs(saved) <= src.error_margin_w };
}
