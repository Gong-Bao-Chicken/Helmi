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
  { key: "lavender", label: "Lavender", plate: 215, swatches: ["#fdbf68", "#006eb8", "#bf5892"] },
  { key: "spectrum", label: "Spectrum", plate: 257, swatches: ["#e31f26", "#fcb315", "#006eb8", "#a36aa5"] },
];

const KEY = "helmet-compare-colorway";

export function currentColorway(): string {
  return document.documentElement.dataset.colorway ?? "benzol";
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
