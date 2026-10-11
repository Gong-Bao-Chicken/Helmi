/** Colorways from Sanzo Wada's A Dictionary of Color Combinations (tokens in app.css / colorways.css). */
export interface Colorway {
  key: string;
  label: string;
  plate: number;
  /** The plate's original colours, for the picker swatch. */
  swatches: string[];
}

export const COLORWAYS: Colorway[] = [
  { key: "benzol", label: "Benzol", plate: 267, swatches: ["#fdbf68", "#f99d1b", "#00978d", "#006eb8"] },
  { key: "drab", label: "Purple Drab", plate: 236, swatches: ["#bc892b", "#1c4286", "#84565b"] },
  { key: "lilac", label: "Lilac", plate: 282, swatches: ["#da525d", "#c59f6b", "#96d1aa", "#b984af"] },
  { key: "slate", label: "Slate Purple", plate: 248, swatches: ["#f37f94", "#bc892b", "#b5b1d8", "#704357"] },
  { key: "lyons", label: "Lyons Blue", plate: 247, swatches: ["#bb7125", "#ffdd00", "#00978d", "#1c4286"] },
  { key: "rosolanc", label: "Rosolanc", plate: 355, swatches: ["#b73f74", "#4b3317", "#00b49b", "#007190"] },
  { key: "cobalt", label: "Cobalt Green", plate: 156, swatches: ["#d6b43e", "#96d1aa", "#4f4086"] },
];

const KEY = "helmet-compare-colorway";

export function currentColorway(): string {
  const key = document.documentElement.dataset.colorway ?? "benzol";
  // A colorway saved by an older version may no longer exist; fall back to the default.
  if (COLORWAYS.some((c) => c.key === key)) return key;
  setColorway("benzol");
  return "benzol";
}

export function setColorway(key: string) {
  if (key === "benzol") delete document.documentElement.dataset.colorway;
  else document.documentElement.dataset.colorway = key;
  try {
    localStorage.setItem(KEY, key);
  } catch {
    // Storage unavailable (private mode): the choice still applies for this visit.
  }
}
