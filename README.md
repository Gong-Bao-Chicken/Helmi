# Helmet Compare

Compare bicycle helmet safety ratings from [Virginia Tech](https://www.helmet.beam.vt.edu/), with optional scores from CERTIMOOV, Folksam, and NSW Helmet STAR. Filter by EU market, rotational protection, price, and more.

## Requirements

- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — it installs the
  pinned Python (see `.python-version`) and all dependencies from `uv.lock`
- Internet access to download helmet data

## First-time setup

```bash
cd /path/to/Helmet
uv sync            # creates .venv with runtime + dev dependencies
```

## Fetch / update data

| Command | What it does | Time |
|---------|----------------|------|
| `uv run helmet-data update --quick` | Virginia Tech dataset only; merges cached extra ratings, protection data and shop prices if present | ~5 s |
| `uv run helmet-data update` | VT + aero refresh + crawl extra labs + live shop prices (Geizhals, Idealo, …) | ~15–45 min |

`./update-data.sh [flags]` is a thin wrapper around `uv run helmet-data update [flags]`.

`update` flags: `--quick`, `--fetch-manufacturer`, `--skip-prices`, `--force-prices`.

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

**Do not** open `web/index.html` directly in the browser — the app loads JSON over HTTP and will fail as a `file://` page.

From the project folder:

```bash
./serve.sh
```

Then open **http://localhost:8080** in your browser.

Use a different port if 8080 is busy:

```bash
PORT=9000 ./serve.sh
```

Manual alternative:

```bash
python3 -m http.server 8080 --directory web
```

If you start the server from the project root **without** `--directory web`, open **http://localhost:8080/web/** instead (or use `./serve.sh`).

After updating data, hard-refresh the page (Cmd+Shift+R) so the browser does not use a cached `helmets.json`.

## Project layout

```
Helmet/
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
│   ├── reference/               # hand-maintained inputs (brands, EU brands, MIPS lookup, aero list)
│   └── cache/                   # generated caches (extra ratings + protection caches tracked;
│                                #   price/style caches, cookies, browser profile gitignored)
├── tests/                       # pytest suite
└── web/                         # frontend; reads web/public/data/helmets.json (generated)
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| “Could not load helmet data” / blank page | Run `uv run helmet-data update --quick`, then `./serve.sh` |
| Opened file in Finder | Use `./serve.sh` and visit http://localhost:8080 |
| `Address already in use` | Another server is on that port — use `PORT=9000 ./serve.sh` |
| Extra rating modes show “no data” | Run full `uv run helmet-data update` (not `--quick`) |
| Shop price / rating columns missing | Run full `uv run helmet-data update` (not `--quick`). Geizhals needs `curl_cffi` (installed by `uv sync`). |
| Only Amazon prices appear | Geizhals should work after the curl_cffi fix; Idealo/toppreise may still block bots — see README data sources |

## Data sources

- **Virginia Tech Helmet Lab** — primary STAR scores (lower = safer)
- **CERTIMOOV**, **Folksam**, **NSW Helmet STAR** — optional; crawled by `helmet-data fetch-ratings`
- **Prices shown** — VT US test-time price by default; full `helmet-data update` checks Geizhals, Idealo, and toppreise.ch (median over ~14 days when cached snapshots exist) and uses a lower shop price when found
