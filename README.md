# Helmi

Find the right bicycle helmet. Tell it how you ride, what matters most (protection, value, budget or aero) and your budget; it ranks helmets using independent lab tests from [Virginia Tech](https://www.helmet.beam.vt.edu/), Folksam, CERTIMOOV and NSW Helmet STAR, matched with current shop prices in Germany, Austria and Switzerland, and explains each pick in plain language.

Two parts:

- **`src/helmet_data/`**: Python pipeline that scrapes and merges the data into `web/public/data/helmets.json`.
- **`web/`**: static Svelte 5 + TypeScript + Tailwind v4 app (Vite) that reads that file.

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

A GitHub Actions workflow (`.github/workflows/update-data.yml`) runs `helmet-data update` every Monday at 04:00 UTC and commits the refreshed data. Start it by hand from the Actions tab ("Run workflow", with optional flags). The price and style caches are committed so price history and fallback prices carry over between runs.

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

The live site is at https://gong-bao-chicken.github.io/Helmi/. `.github/workflows/deploy-pages.yml` rebuilds and deploys it when `web/` changes on `main` and after each successful data update.

The app keeps all state in the URL (`?ride=road&priority=value&budget=150&helmet=…&compare=…`), so any result can be bookmarked or shared.

### How the ranking works (`web/src/lib/finder.ts`)

- **Safety** is a percentile (0–100) across all lab-tested helmets. By default the labs are combined, each weighted by how much its protocol is trusted (VT 1.0, Folksam 0.9, CERTIMOOV/NSW 0.85); under *Advanced* you can use a single lab.
- **Price** is the live shop price in your market; each country only takes prices from its own shops. If a helmet has none, a neighbouring country's shop price is shown instead (Germany ↔ Austria unchanged, since both use euro; to or from Switzerland converted), and without any shop price the converted US price at test time. Both are marked with "≈". Conversions use the ECB reference rates the pipeline fetches on every price update (`meta.exchange_rates` in `helmets.json`).
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
│   └── enrich/                  # ratings fusion, aero, styles, protection tech, matching
├── data/
│   ├── reference/               # hand-maintained inputs (brands, EU brands, MIPS lookup, aero list,
│   │                            #   reviewed helmet styles)
│   └── cache/                   # generated caches, all tracked (the weekly workflow builds on them)
│                                #   except stealth cookies and the browser profile
├── tests/                       # pytest suite
└── web/                         # Vite + Svelte 5 + TypeScript + Tailwind v4
    ├── public/data/helmets.json # generated by the pipeline
    └── src/
        ├── lib/                 # finder (ranking), scoring (Pareto/knee), state (URL sync), types
        └── components/          # Welcome, GoalsPanel, Results, ScatterChart, HelmetDrawer, Compare…
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| “Could not load helmet data” | Run `uv run helmet-data update --quick`, then `./serve.sh` |
| Port 5173 busy | Vite picks the next free port; check the terminal output |
| Extra rating modes show “no data” | Run full `uv run helmet-data update` (not `--quick`) |
| Shop price / rating columns missing | Run full `uv run helmet-data update` (not `--quick`). Geizhals needs `curl_cffi` (installed by `uv sync`). |
| Only Amazon prices appear | Geizhals should work after the curl_cffi fix; Idealo/toppreise may still block bots — see README data sources |

## Data sources

- **Virginia Tech Helmet Lab** — primary STAR scores (lower = safer)
- **CERTIMOOV**, **Folksam**, **NSW Helmet STAR** — optional; crawled by `helmet-data fetch-ratings`
- **Prices shown** — VT US test-time price by default; full `helmet-data update` checks Geizhals, Idealo, and toppreise.ch (median over ~14 days when cached snapshots exist) and uses a lower shop price when found
