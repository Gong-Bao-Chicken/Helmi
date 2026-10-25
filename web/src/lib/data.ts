import type { Dataset } from "./types";

/** The site loads the slim copy (no pipeline debug fields); data/helmets.json is the complete file. */
export const DATA_URL = `${import.meta.env.BASE_URL}data/helmets.site.json`;

export async function loadDataset(): Promise<Dataset> {
  const res = await fetch(DATA_URL);
  if (!res.ok) throw new Error(`Could not load helmet data (HTTP ${res.status})`);
  const data = (await res.json()) as Dataset;
  for (const helmet of data.helmets) {
    // The pipeline emits test_year as string or number; normalise for display and sorting.
    helmet.test_year = helmet.test_year == null ? null : String(helmet.test_year);
  }
  return data;
}
