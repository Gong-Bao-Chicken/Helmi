/** App state, mirrored into the URL so any view can be bookmarked or shared. */
import { DEFAULT_GOALS, PRIORITIES, RIDES, type Goals, type MarketChoice, type SafetySource } from "./finder";

export type View = "find" | "charts" | "explore";

const MARKETS: MarketChoice[] = ["de", "at", "ch", "us"];
const SOURCES: SafetySource[] = ["fused", "virginia_tech", "folksam", "certimoov", "nsw_helmet_star"];
export const MAX_COMPARE = 4;

function readUrl() {
  const p = new URLSearchParams(location.search);
  const goals: Goals = { ...DEFAULT_GOALS };
  const ride = p.get("ride");
  if (RIDES.some((r) => r.key === ride)) goals.ride = ride as Goals["ride"];
  const priority = p.get("priority");
  if (PRIORITIES.some((x) => x.key === priority)) goals.priority = priority as Goals["priority"];
  const budget = Number(p.get("budget"));
  if (budget > 0) goals.budget = budget;
  const market = p.get("market") as MarketChoice;
  if (MARKETS.includes(market)) goals.market = market;
  const source = p.get("source") as SafetySource;
  if (SOURCES.includes(source)) goals.safetySource = source;
  goals.rotational = p.get("rot") === "1";
  goals.pricedOnly = p.get("priced") === "1";
  goals.euOnly = p.get("eu") !== "0";
  return {
    goals,
    view: (["charts", "explore"].includes(p.get("view") ?? "") ? p.get("view") : "find") as View,
    helmet: p.get("helmet"),
    compare: (p.get("compare") ?? "").split(",").filter(Boolean).slice(0, MAX_COMPARE),
  };
}

const initial = readUrl();

export const app = $state({
  goals: initial.goals,
  view: initial.view,
  /** Helmet open in the detail drawer. */
  selected: initial.helmet as string | null,
  compare: initial.compare,
  compareOpen: false,
  /** Hovered helmet, shared between list and chart. */
  hovered: null as string | null,
});

export function writeUrl() {
  const { goals, view, selected, compare } = app;
  const p = new URLSearchParams();
  if (view !== "find") p.set("view", view);
  if (goals.ride) p.set("ride", goals.ride);
  if (goals.priority !== DEFAULT_GOALS.priority) p.set("priority", goals.priority);
  if (goals.budget) p.set("budget", String(goals.budget));
  if (goals.market !== DEFAULT_GOALS.market) p.set("market", goals.market);
  if (goals.safetySource !== DEFAULT_GOALS.safetySource) p.set("source", goals.safetySource);
  if (goals.rotational) p.set("rot", "1");
  if (goals.pricedOnly) p.set("priced", "1");
  if (!goals.euOnly) p.set("eu", "0");
  if (selected) p.set("helmet", selected);
  if (compare.length) p.set("compare", compare.join(","));
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

export function toggleCompare(id: string) {
  const i = app.compare.indexOf(id);
  if (i >= 0) app.compare.splice(i, 1);
  else if (app.compare.length < MAX_COMPARE) app.compare.push(id);
}

const THEME_KEY = "helmet-compare-theme";

export function currentTheme(): "light" | "dark" {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function setTheme(theme: "light" | "dark") {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Storage may be unavailable (private mode); the toggle still works for this visit.
  }
}
