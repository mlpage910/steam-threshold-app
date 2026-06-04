# Steam Threshold Calibration

A small Streamlit workbench for finding the noise-removal thresholds that make
the Steam marketplace legible enough to study discovery and traction patterns.
Drives the [indie-investor-pci-pipeline](https://github.com/mlpage910/indie-investor-pci-pipeline)
upstream and feeds its locked findings (A–VV).

> **Live app:** [Streamlit Community Cloud deployment](https://share.streamlit.io/)
> · **Static fallback (read-only snapshot):** auto-published to GitHub Pages
> on every push to `main` (see [deployment](#deployment) below).

## What this is — and isn't

| It is | It isn't |
|---|---|
| A **calibration workbench**: sliders set filters, graphs show what survives, normality tests on the *Findings* tab tell you when a filter combination has produced a well-behaved response distribution worth recording. | A shovelware classifier. |
| The honest place where filter-layer decisions get made and saved. | A predictive model or scoring engine. |
| Single-researcher tooling — opinionated defaults, JSONL-logged snapshots. | A polished public product. |

The output of this workbench is a *filter snapshot* (a JSON record on the
*Findings* tab). Those snapshots are then re-played by `investor_pipeline.py`
in the companion repository to produce the locked 146-candidate roster.

## Three filter layers (kept strictly separate)

The app's central design discipline is that filters are organized into three
layers, applied in a fixed order. They are **never mixed** in a single
condition. Each layer answers a different question.

### 1. Data hygiene — *"is this row even readable?"*

Drops rows with missing or invalid fields. Implemented in
[`filters.hygiene_mask`](filters.py).

| Toggle | What it drops |
|---|---|
| `require_release_date` | rows whose `release_date` failed to parse |
| `require_owners_band` | rows with no SteamSpy `owners_range` (cannot order them on the ordinal scale) |
| `require_developer` / `require_publisher` | empty, `\N`, `None`, `null`, `NULL` developer/publisher strings |
| `paid_requires_price` | `is_free = 0` rows missing a price (Steam-side scrape glitches) |
| `drop_future_release` | release dates after the scrape's reference date (`2024-10-28`) |
| `require_review_row` | optional: rows with no entry in `reviews.csv` |

These gates are not analytical decisions — they are the floor below which
**any** downstream conclusion would be unsound. Default: all on.

### 2. Structural exclusions — *"does this title follow the same rules as the rest?"*

Drops *populations* that behave categorically differently from the main study
universe. Implemented in [`filters.structural_mask`](filters.py).

| Toggle | What it excludes and why |
|---|---|
| `exclude_demos` | `type = "demo"`. Demos are marketing assets, not products. |
| `exclude_free_to_play` | `is_free = 1`. F2P economics are non-comparable to paid titles. |
| `require_english` | catalogs lacking English. Restricts to titles competing in the broad anglophone Steam market. |
| `require_us_available` | titles with a parseable `price_overview` currency. Our scrape was run from a non-US IP, so `currency = USD` is unreliable; any store listing is the best available proxy for "sold via Steam store anywhere." |
| `exclude_early_access` | catalogs whose genre list contains `Early Access`. EA owners-vs-reviews ratios are unreliable because the build is still changing under players. |

A title removed at this layer is not a "bad" title — it just plays by
different rules and would bias every downstream comparison.

> Locked-finding **LL** in the companion pipeline documents a subtle EA/F2P
> "dual-location filter trap" that motivated the genre-list based EA gate
> here.

### 3. Analytical thresholds — *the actual research object*

The tunable knobs that define which subset of the (hygienic, structurally
homogeneous) population is being studied. Implemented in
[`filters.analytical_mask`](filters.py).

| Knob | Meaning |
|---|---|
| `min_owners_band` | floor on the SteamSpy owners ordinal (see [next section](#owners_range-the-ordinal-anchor)) |
| `min_concurrent_users` | floor on yesterday's CCU |
| `release_age_range` | `(min, max)` years since release |
| `price_range` | `(min, max)` USD |
| `dev_output_range` | `(min, max)` titles by the same developer in the dataset |
| `genres_any` | union of Steam genres |
| `categories_any` | union of Steam categories (Single-player, Multi-player, …) |
| `min_total_reviews`, `min_pct_positive`, `min_reviews_per_year` | response-side floors. Use with care if reviews are also your outcome. |

This is the layer that *changes* between research questions. Layer 1 and 2
are usually identical across snapshots; layer 3 is the experiment.

## `owners_range` — the ordinal anchor

Review counts conflate adoption with willingness-to-review. The SteamSpy
`owners_range` field is a *revealed-acquisition* signal — a player actually
owns the title. We treat it as an **ordinal scale of 14 bands** and sweep
cutoffs to find natural elbows, rather than committing to a single number.

The mapping lives in [`loader.py`](loader.py):

```python
OWNERS_ORDER = [
    "0 .. 20,000",                # rank 0
    "20,000 .. 50,000",           # rank 1
    "50,000 .. 100,000",          # rank 2
    "100,000 .. 200,000",         # rank 3
    "200,000 .. 500,000",         # rank 4
    "500,000 .. 1,000,000",       # rank 5
    "1,000,000 .. 2,000,000",     # rank 6
    "2,000,000 .. 5,000,000",     # rank 7
    "5,000,000 .. 10,000,000",    # rank 8
    "10,000,000 .. 20,000,000",   # rank 9
    "20,000,000 .. 50,000,000",   # rank 10
    "50,000,000 .. 100,000,000",  # rank 11
    "100,000,000 .. 200,000,000", # rank 12
    "200,000,000 .. 500,000,000", # rank 13
]
OWNERS_RANK  = {band: i for i, band in enumerate(OWNERS_ORDER)}
OWNERS_LOWER = {band: int(band.split("..")[0].strip().replace(",", "")) for band in OWNERS_ORDER}
```

Two derived columns are computed at load time and used everywhere downstream:

- `owners_rank` — integer 0–13. The **primary** ordering key. Used in survival
  curves, threshold sweeps, and the `min_owners_band` analytical filter.
- `owners_lower` — the **lower bound** of the band, in raw owner units. Used
  when a numeric stand-in is needed (e.g. log-scale histograms). This is the
  *conservative* reading; if you average it, you systematically under-count.

> The Portfolio Concentration Index (PCI) used in the companion pipeline
> sums `owners_lower` across a developer's catalog. Conservative-floor math
> is one of the reasons C1 PCI distributions tilt diversified — locked
> finding **PP** in the pipeline repo.

## Data

Source:
[NewbieIndieGameDev/steam-insights](https://github.com/NewbieIndieGameDev/steam-insights)
(October 2024 scrape). Place the following CSVs in `data/`:

| Required | File |
|---|---|
| ✅ | `games.csv` |
| ✅ | `steamspy_insights.csv` |
| ✅ | `genres.csv` |
| ✅ | `tags.csv` |
| optional | `reviews.csv` (enables `total_reviews`, `pct_positive`, etc.) |
| optional | `categories.csv` (enables the categories filter) |

All `.csv` files are gitignored. Fetch them locally — the loader detects
which optional tables are present and adapts the SELECT accordingly.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the browser tab Streamlit prints. Filters live in the sidebar;
the five tabs are *Survival curve*, *Distribution profile*, *Threshold sweep*,
*Cohort table*, and *Findings*.

## Dropping in a second scrape for A/B comparison

The whole point of this workbench is to make threshold decisions that hold up
across scrapes. The workflow:

```text
data/                    # Scrape 1 (e.g. October 2024)
├── games.csv
├── steamspy_insights.csv
├── genres.csv
├── tags.csv
├── reviews.csv          # optional
└── categories.csv       # optional

data_v2/                 # Scrape 2 (a fresh fetch)
├── games.csv
├── steamspy_insights.csv
├── genres.csv
└── tags.csv
```

Then in a Python session or a notebook:

```python
from loader import load
from filters import apply_all

df_a = load("data")
df_b = load("data_v2")

# Re-apply the same filter snapshot to both scrapes
hyg    = dict(require_release_date=True, require_owners_band=True,
              require_developer=True, require_publisher=True,
              paid_requires_price=True, drop_future_release=True)
struct = dict(exclude_demos=True, exclude_free_to_play=True,
              require_english=True, require_us_available=True,
              exclude_early_access=True)
ana    = dict(min_owners_band="20,000 .. 50,000",
              release_age_range=(0, 5))

cohort_a, counts_a = apply_all(df_a, hyg, struct, ana)
cohort_b, counts_b = apply_all(df_b, hyg, struct, ana)

print("Scrape A:", counts_a)
print("Scrape B:", counts_b)
```

Three comparisons are worth running:

1. **Funnel reconciliation.** Compare `counts_a` to `counts_b`. If hygiene
   counts diverge by more than a few percent, one of the scrapes has a parse
   problem — investigate before trusting analytical results.
2. **Distribution stability.** Run a Kolmogorov–Smirnov test on a response
   variable (e.g. `owners_rank`, `concurrent_users_yesterday`, `pct_positive`)
   between the two filtered cohorts. A small KS statistic means the
   threshold survives a fresh scrape.
3. **Overlap rank correlation.** Inner-join `cohort_a` and `cohort_b` on
   `app_id` and Spearman-correlate `owners_rank`. High correlation = the
   ordinal scale itself is stable.

> A future version of `app.py` will surface this side-by-side. Until then,
> the Python snippet above plus the `loader.load(...)` adapter is the
> canonical way to A/B two scrapes.

## Project layout

```
app.py                        Streamlit UI: sidebar filters + 5 tabs
filters.py                    Pure filter functions (hygiene / structural / analytical)
loader.py                     DuckDB → pandas, derived columns, owners-band ordering
findings_content.py           Locked-finding prose served on the Findings tab
scripts/build_static.py       Renders the static GitHub Pages fallback
.github/workflows/
  └── static-fallback.yml     Builds + deploys the static fallback on every push
.streamlit/config.toml        Theme + server settings (matches site palette)
data/                         CSVs (gitignored)
site/                         Generated static fallback (gitignored)
findings.log                  JSONL of saved filter snapshots (gitignored)
```

## Deployment

There are **two** deployment paths and they serve different purposes.

### Path A — Streamlit Community Cloud (primary, interactive)

Streamlit Community Cloud is the only no-cost way to run the *actual*
Streamlit server with live sliders. GitHub Pages cannot host Streamlit —
Pages is static HTML/JS only, while Streamlit is a Python server process.

To deploy:

1. Push this repo to GitHub (this README assumes you already have).
2. Go to [share.streamlit.io](https://share.streamlit.io/), sign in with
   GitHub, and click **New app**.
3. Pick the repo, branch `main`, main file `app.py`.
4. Add your data: either commit the CSVs (they are large — see size table
   below) or use `streamlit secrets` to point at an external object store.
5. Hit **Deploy**. Subsequent commits to `main` redeploy automatically.

Streamlit Cloud has a ~1 GB memory ceiling for free apps. The October 2024
scrape sits comfortably under that with DuckDB, but a much larger scrape
may require pre-aggregation.

### Path B — Static fallback to GitHub Pages (read-only, automatic)

The `static-fallback.yml` workflow renders a read-only snapshot of the
default cohort to GitHub Pages on every push to `main`. This guarantees
that the repo always has a public surface even if Streamlit Cloud is
unavailable, and gives every commit a deterministic figure set.

To enable it once after creating the repo:

1. Go to **Settings → Pages**.
2. Under **Source**, choose **GitHub Actions**.
3. Push any commit to `main`. The workflow builds `site/` and publishes
   it to `https://<owner>.github.io/steam-threshold-app/`.

What the static fallback renders:

| Page | Content |
|---|---|
| `index.html` | Filter-stack reconciliation table at default thresholds |
| `survival.html` | Survival curve across all 14 owners bands |
| `distribution.html` | Owners / price / age histograms for the default cohort |
| `sweep.html` | Median price / age / dev output across cutoffs |
| `cohort.html` | Top-200 surviving titles, sortable in the browser |

If `data/` is empty at build time (the default for a fresh clone), the
workflow emits a placeholder page explaining how to populate it.

### Why not just deploy Streamlit to Pages?

Because it isn't possible. Pages serves static files; Streamlit needs a
running Python interpreter that holds DuckDB tables in memory and pushes
re-renders to the browser via websockets. The static fallback exists to
give the repo a public surface for cases where the live Streamlit Cloud
deployment is down or paused.

## License

MIT.

## Companion repos

- [mlpage910/indie-investor-pci-pipeline](https://github.com/mlpage910/indie-investor-pci-pipeline)
  — the 11-stage pipeline whose locked findings (A–VV) calibrate this
  workbench. Its [methodology page](https://mlpage910.github.io/indie-investor-pci-pipeline/methodology/)
  documents every threshold this app calibrates.
- [NewbieIndieGameDev/steam-insights](https://github.com/NewbieIndieGameDev/steam-insights)
  — the upstream Steam scrape consumed by `loader.py`.
