# Helmet Compare

Compare bicycle helmet safety ratings from [Virginia Tech](https://www.helmet.beam.vt.edu/), with optional scores from CERTIMOOV, Folksam, and NSW Helmet STAR. Filter by EU market, rotational protection, price, and more.

## Requirements (Mac)

- macOS with **Python 3.11+** (check with `python3 --version`)
- Internet access to download helmet data

## First-time setup

Open Terminal and run:

```bash
cd /path/to/Helmet
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or use the helper script (creates the venv for you):

```bash
chmod +x update-data.sh serve.sh
./update-data.sh --quick
```

## Fetch / update data

| Command | What it does | Time |
|---------|----------------|------|
| `./update-data.sh --quick` | Virginia Tech dataset only; merges cached extra ratings and cached shop prices if present | ~5 s |
| `./update-data.sh` | VT + crawl extra labs + live shop prices (Amazon, Geizhals, …) | ~15–45 min |

Equivalent Python commands (with venv activated):

```bash
python scripts/update_data.py --quick
python scripts/update_data.py
```

Refresh only Virginia Tech (skip extra sources):

```bash
python scripts/fetch_helmets.py --skip-extra-ratings
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
├── README.md
├── serve.sh              # start local web server
├── update-data.sh        # fetch / refresh all data
├── requirements.txt
├── scripts/
│   ├── update_data.py    # main data update entry point
│   ├── fetch_helmets.py  # Virginia Tech + merge into web/data/helmets.json
│   ├── fetch_extra_ratings.py
│   └── extra_ratings.json   # generated; merged into helmets.json
└── web/
    ├── index.html
    └── data/
        └── helmets.json  # generated; required for the UI
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| “Could not load helmet data” / blank page | Run `./update-data.sh --quick`, then `./serve.sh` |
| Opened file in Finder | Use `./serve.sh` and visit http://localhost:8080 |
| `Address already in use` | Another server is on that port — use `PORT=9000 ./serve.sh` |
| Extra rating modes show “no data” | Run full `./update-data.sh` (not `--quick`) |
| Shop price / rating columns missing | Run full `./update-data.sh` (not `--quick`). Geizhals needs `curl_cffi` (installed via `requirements.txt`). |
| Only Amazon prices appear | Geizhals should work after the curl_cffi fix; Idealo/toppreise may still block bots — see README data sources |

## Data sources

- **Virginia Tech Helmet Lab** — primary STAR scores (lower = safer)
- **CERTIMOOV**, **Folksam**, **NSW Helmet STAR** — optional; crawled by `fetch_extra_ratings.py`
- **Prices shown** — VT US test-time price by default; full `./update-data.sh` checks Geizhals, Idealo, and toppreise.ch (median over ~14 days when cached snapshots exist) and uses a lower shop price when found
