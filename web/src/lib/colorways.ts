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
  { key: "turquoise", label: "Turquoise", plate: 272, swatches: ["#ffefae",  "#f37420",  "#b5decc",  "#97acc8"] },
  { key: "pistachio", label: "Pistachio", plate: 127, swatches: ["#fdc57e",  "#648f7b",  "#66629c"] },
  { key: "cossack", label: "Cossack", plate: 294, swatches: ["#f5ecc2",  "#fdbf68",  "#437742",  "#97acc8"] },
  { key: "rufous", label: "Rufous", plate: 172, swatches: ["#c27544",  "#007190",  "#59256a"] },
  { key: "madder", label: "Madder", plate: 314, swatches: ["#f37f94",  "#793327",  "#1c4286",  "#4e1d4c"] },
  { key: "nile", label: "Nile", plate: 345, swatches: ["#793327",  "#bce4e5",  "#62c6bf",  "#6450a1"] },
  { key: "rosolanc", label: "Rosolanc", plate: 355, swatches: ["#b73f74",  "#4b3317",  "#00b49b",  "#007190"] },
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
