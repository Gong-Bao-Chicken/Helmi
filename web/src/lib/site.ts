/** Where the project lives, for "report a problem" and the footer. */
import type { Dataset, Helmet } from "./types";

export const REPO_URL = "https://github.com/Gong-Bao-Chicken/Helmi";

/** A new GitHub issue, pre-filled with what the maintainer needs to find and fix the entry. */
export function reportUrl(dataset: Dataset, helmet?: Helmet) {
  const title = helmet ? `Data problem: ${helmet.brand} ${helmet.model}` : "Problem report";
  const body = [
    helmet ? `Helmet: ${helmet.brand} ${helmet.model} (id \`${helmet.id}\`)` : null,
    `Page: ${location.href}`,
    `Data from: ${dataset.meta.generated_at}`,
    "",
    "What is wrong (lab result, match, price, style, feature…)?",
    "",
    "What should it be, and where can it be checked (link)?",
    "",
  ]
    .filter((line) => line != null)
    .join("\n");
  return `${REPO_URL}/issues/new?${new URLSearchParams({ title, body })}`;
}

/** What each lab measures, in one line. */
export const LAB_EXPLAINERS: Record<string, string> = {
  virginia_tech:
    "US university lab. Concussion risk from 4 impact points at 2 speeds, rotation included.",
  folksam: "Swedish insurer. Straight and angled impacts; the result is shown against the best helmet in that year's test.",
  certimoov: "French lab. Angled impacts at 6 points, faster than the EN 1078 standard requires; rated 0–5.",
  nsw_helmet_star:
    "Run by the New South Wales government (Australia). Impact, rotation, strap strength and coverage, scored out of 100; the stars are bands of that score.",
};

/** The certification string ("CPSC, EN 1078") split into its standards. */
export function certifications(raw: string | null | undefined) {
  return (raw ?? "")
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);
}
