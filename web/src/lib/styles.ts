/** Riding styles in display order, each with its fixed chart color (see the --style-* tokens in app.css). */
export const STYLES = [
  { key: "Road", label: "Road", color: "var(--style-road)" },
  { key: "Aero", label: "Aero", color: "var(--style-aero)" },
  { key: "Multi-sport", label: "Multi-sport", color: "var(--style-multi)" },
  { key: "Mountain", label: "Mountain", color: "var(--style-mountain)" },
  { key: "Full-Face", label: "Full-face", color: "var(--style-fullface)" },
  { key: "Urban", label: "Urban & commute", color: "var(--style-urban)" },
  { key: "Kids", label: "Kids", color: "var(--style-kids)" },
  { key: "Unclassified", label: "Unclassified", color: "var(--dot)" },
] as const;

const BY_KEY = new Map<string, (typeof STYLES)[number]>(STYLES.map((s) => [s.key, s]));

export const styleColor = (key: string | null | undefined) => (key && BY_KEY.get(key)?.color) || "var(--dot)";
export const styleLabel = (key: string | null | undefined) => (key && BY_KEY.get(key)?.label) || key || "–";

/** The data's styles in display order; unknown ones go last, so new styles never vanish. */
export function orderedStyles(present: readonly string[]) {
  const known = STYLES.filter((s) => present.includes(s.key)).map((s) => ({ key: s.key as string, label: s.label as string }));
  const extra = present.filter((p) => !BY_KEY.has(p)).map((p) => ({ key: p, label: p }));
  return [...known, ...extra];
}
