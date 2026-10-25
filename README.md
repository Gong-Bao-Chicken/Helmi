# Helmi

Find the right bicycle helmet. Tell it how you ride, what matters most (protection, value, budget or aero) and your budget; it ranks helmets using independent lab tests from [Virginia Tech](https://www.helmet.beam.vt.edu/), Folksam, CERTIMOOV and NSW Helmet STAR, matched with current shop prices in Germany, Austria and Switzerland, and explains each pick in plain language.

Two parts:

- **`src/helmet_data/`**: Python pipeline that scrapes and merges the data into `web/public/data/helmets.json` (plus a compact `helmets.site.json` for the website).
- **`web/`**: static Svelte 5 + TypeScript + Tailwind v4 app (Vite) that reads it.

## Requirements

- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — it installs the
  pinned Python (see `.python-version`) and all dependencies from `uv.lock`
- [Node.js](https://nodejs.org/) 22+ for the website (`brew install node`)
- Internet access to download helmet data

## First-time setup

```bash
cd /path/to/Helmi
uv sync            # creates .venv with runtime + dev dependencies
npm --prefix web install
```

## Fetch / update data

| Command | What it does | Time |
|---------|----------------|------|
| `uv run helmet-data update --quick` | Virginia Tech dataset only; merges cached extra ratings, protection data and shop prices if present | ~5 s |
| `uv run helmet-data update` | VT + aero refresh + crawl extra labs + live shop prices (Geizhals, Idealo, …) | ~15–45 min |

`./update-data.sh [flags]` is a thin wrapper around `uv run helmet-data update [flags]`.

`update` flags: `--quick`, `--fetch-manufacturer`, `--skip-prices`, `--force-prices`.

A GitHub Actions workflow (`.github/workflows/update-data.yml`) runs `helmet-data update` every Monday at 04:00 UTC and commits the refreshed data. Start it by hand from the Actions tab ("Run workflow", with optional flags). The price and style caches are committed so price history and fallback prices carry over between runs. Geizhals blocks GitHub's servers, so the workflow keeps each helmet's last Geizhals price; run `./update-data.sh` locally and push to refresh them.

Individual steps (run `uv run helmet-data <command> --help` for all flags):

| Command | Replaces | Purpose |
|---------|----------|---------|
| `build` (alias `fetch-vt`) | `fetch_helmets.py` | Fetch VT ratings and assemble `helmets.json` from cached enrichments (`--skip-extra-ratings`, `--verify-styles`, `--crawl-manufacturer-protection`, …) |
| `fetch-ratings` | `fetch_extra_ratings.py` | Crawl CERTIMOOV / Folksam / NSW Helmet STAR → `data/cache/extra_ratings*.json` |
| `fetch-prices` | `fetch_listings.py` | Shop prices → `helmets.json` (`--cache-only`, `--force`, `--limit N`, `--all-helmets`) |
| `fetch-aero` | `fetch_aero_ratings.py` | Aero coverage report; `--fetch` refreshes `data/reference/aero_ratings.json` from CN Labs |
| `fetch-protection` | `fetch_manufacturer_protection.py` | Crawl manufacturer/retailer pages for MIPS etc. (`--helmet ID`, `--brand`, `--all-missing`, `--retailers`, `--write-lookup`) |

Development:

```bash
uv run pytest          # tests
uv run ruff check      # lint (ruff format to format)
```

## Start the website

```bash
./serve.sh                 # = npm --prefix web run dev → http://localhost:5173
```

Other frontend commands (run in `web/`):

| Command | Purpose |
|---------|---------|
| `npm run build` | Production build to `web/dist/`: a static site you can host anywhere (relative paths, so subfolders like GitHub Pages work) |
| `npm run preview` | Serve the production build locally |
| `npm test` | Unit tests for the ranking logic (Vitest) |
| `npm run check` | Type-check Svelte + TypeScript |

The site loads `web/public/data/helmets.site.json`, a compact copy of `helmets.json` without the pipeline's debug fields (both are written together); `helmets.json` stays complete for anyone reusing the data. The *How it works* page (`?view=about`) explains the method.

The live site is at https://gong-bao-chicken.github.io/Helmi/. `.github/workflows/deploy-pages.yml` rebuilds and deploys it when `web/` changes on `main` and after each successful data update.

The app keeps all state in the URL (`?ride=road&priority=value&budget=150&helmet=…&compare=…`), so any result can be bookmarked or shared.

### How the ranking works (`web/src/lib/finder.ts`)

- **Safety** is a percentile (0–100) across all lab-tested helmets. By default the labs are combined, each weighted by how much its protocol is trusted (VT 1.0, Folksam 0.9, CERTIMOOV/NSW 0.85); under *Advanced* you can use a single lab.
- **Price** is the live shop price in your market; each country only takes prices from its own shops. If a helmet has none, a neighbouring country's shop price is shown instead (Germany ↔ Austria unchanged, since both use euro; to or from Switzerland converted), and without any shop price the converted US price at test time. Both are marked with "≈". Conversions use the ECB reference rates the pipeline fetches on every price update (`meta.exchange_rates` in `helmets.json`).
- **Evidence:** every score says how many labs tested the helmet and whether they agree (percentiles more than 30 points apart count as disagreeing); tapping it shows the weighted calculation. Kids' helmets are also ranked among kids' helmets only. For the money-driven priorities an estimated price ranks like an unknown one, and the budget pick needs a live price when one exists.
- **Duplicates:** helmets listed twice because two labs named them differently are folded together via `data/reference/helmet_merges.json` (checked by hand; two tests by the same lab are two versions and stay apart).
- **Style** comes from Virginia Tech's category, the hand-checked corrections in `data/reference/style_overrides.json` (these win), or words in the model name. Helmets none of these can place are *Unclassified*.
- **Priorities** set the weights: value = 55% safety / 45% cheapness; max protection = 95/5; cheapest-safe = only top-40% safety, then mostly price; fast-and-safe adds wind-tunnel results (wind-tunnel-tested helmets only).
- **Picks**: *Best match* (top of the ranking), *Safest*, *Sweet spot* (the knee of the price/safety frontier, where spending more stops buying much more safety), *Budget pick* (cheapest with top-40% safety) and *Fastest safe*.

## Project layout

```
Helmi/
├── pyproject.toml / uv.lock     # Python project (helmet-data), deps, ruff + pytest config
├── update-data.sh               # wrapper: uv run helmet-data update "$@"
├── src/helmet_data/
│   ├── cli.py                   # `helmet-data` entry point (subcommands)
│   ├── pipeline.py              # `update`: orchestrates the steps below
│   ├── build.py                 # VT fetch + dataset assembly → helmets.json
│   ├── paths.py                 # all file locations
│   ├── steps/                   # fetch-ratings, fetch-prices, fetch-aero, fetch-protection
│   ├── crawlers/                # CERTIMOOV, Folksam, NSW, price sources, stealth (curl_cffi) fetch
│   ├── enrich/                  # ratings fusion, aero, styles, merges, protection tech, matching
│   └── site_data.py             # writes helmets.json and the compact helmets.site.json
├── data/
│   ├── reference/               # hand-maintained inputs (brands, EU brands, MIPS lookup, aero list,
│   │                            #   reviewed helmet styles, merged duplicate helmets)
│   └── cache/                   # generated caches, all tracked (the weekly workflow builds on them)
│                                #   except stealth cookies and the browser profile
├── tests/                       # pytest suite
└── web/                         # Vite + Svelte 5 + TypeScript + Tailwind v4
    ├── public/data/             # helmets.json (complete) + helmets.site.json (what the site loads)
    └── src/
        ├── lib/                 # finder (ranking, evidence), scoring (Pareto/knee), chartData, aero (race time),
        │                        #   format, site (links, lab texts), state (URL sync), types
        └── components/          # Welcome, GoalsPanel, Results, PickCard, ResultRow, EvidenceChip, HelmetDrawer,
                                 #   CompareDialog, ExploreTable, ChartsView, AboutView, Header, Footer, charts/
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| “Could not load helmet data” | Run `uv run helmet-data update --quick`, then `./serve.sh` |
| Port 5173 busy | Vite picks the next free port; check the terminal output |
| Extra rating modes show “no data” | Run full `uv run helmet-data update` (not `--quick`) |
| Shop price / rating columns missing | Run full `uv run helmet-data update` (not `--quick`). Geizhals needs `curl_cffi` (installed by `uv sync`). |
| Geizhals prices are old or missing | Geizhals blocks GitHub's servers and rate-limits long crawls; the last price per helmet is kept. Run `./update-data.sh` locally later and push. |

## Data sources

- **Virginia Tech Helmet Lab** — STAR scores (lower = safer); each helmet links to VT's result chart for it
- **CERTIMOOV** (score out of 5), **Folksam** (result vs best in test), **NSW Helmet STAR** (total out of 100, with its parts and any penalty; NSW caps a helmet at 29 for a design fault) — crawled by `helmet-data fetch-ratings` (`--sources` to crawl only some; the others keep their last results)
- **Prices** — Geizhals and Idealo (Germany, Austria; Geizhals limited to the country's own shops), toppreise.ch (Switzerland) and Amazon, for every helmet sold in Europe, including those only Folksam, CERTIMOOV or NSW tested. Median of the last 14 days of prices (30 days when there are too few); implausible offers (accessories, other models) are dropped. Without a shop price the site shows a neighbouring country's price or the converted US launch price, marked "≈".
- **Exchange rates** — ECB reference rates (Frankfurter), refreshed on every price update
