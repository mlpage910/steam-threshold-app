# Four-Tier Discovery Index — Strategy

A continuous-refresh strategy for the indie-investor candidate pipeline that
preserves Oct 2024 methodology while keeping each refresh session bounded in
time. Replaces the single 15–19 hour scrape with cadenced tier updates.

## Why this exists

The original Oct 2024 methodology was a single point-in-time scrape of 140K+
Steam titles → 146 final candidates. As Steam's catalogue has grown (~14K new
games/year), a faithful re-scrape now exceeds 19 hours of API calls — too long
for a single Colab session and impractical to do often enough to keep findings
current. The four-tier index is a **scheduling and prioritisation layer** that
sits between the API and the methodology gates; it does not modify any gate.

## Methodology invariants (do not touch)

Every app, regardless of tier, must pass the same Oct 2024 gates before
entering the merged dataset that `investor_pipeline.py` consumes:

1. **Multi-title:** Developer has ≥ 2 titles in Steam catalogue
2. **Non-AAA:** Developer has no title at owners band ≥ 5,000,000
3. **Active:** Developer's newest release within 5 years of refresh date

A tier change **never** lets an app skip these gates. Tiers only decide
*which apps get scraped this session* and *in what order*.

## The four tiers

| Tier | Definition | Estimated size | Refresh cadence | Per-run time |
|---|---|---|---|---|
| **T1 — Active candidates** | Apps owned by current candidates + research pool (~254 devs) | ~1,400 titles | Weekly | ~35 min |
| **T2 — Watch list** | New cohort-pass devs with at least one title at owners ≥ 100K | ~3,000–5,000 titles | Monthly | ~2 hr |
| **T3 — Emerging pool** | Cohort-pass devs with no title above 100K, max owners ≥ 20K | ~10,000–15,000 titles | Quarterly | ~5–6 hr |
| **T4 — Long tail** | Cohort-pass devs with all titles below 20K owners | ~30,000–45,000 titles | Annual or on-demand | ~15–18 hr |

Within each tier, apps are sorted by owners band descending so partial-run
data still captures the highest-signal candidates.

## Refresh cadence (recommended)

| Day | What runs | Apps touched | Time |
|---|---|---|---|
| Every Monday | T1 (active candidates) | ~1,400 | 35 min |
| First of month | T1 + T2 (watch list) | ~5,000 | ~2.5 hr |
| First of quarter | T1 + T2 + T3 (emerging pool) | ~20,000 | ~8 hr (run overnight) |
| Annually (or as needed) | All tiers including T4 | ~50,000 | ~19 hr (over 2–3 sessions) |

## How newcomers enter the index

Each refresh begins by pulling the full Steam catalogue via `GetAppList`. Any
appid not previously seen is **triaged into a tier on its first appearance**,
based on SteamSpy bulk signal (owners band):

| Initial signal | Initial tier |
|---|---|
| Owners ≥ 100K | T2 (skip T1 — not yet a candidate, but high enough to watch) |
| Owners 20K – 100K | T2 |
| Owners < 20K, multi-title dev | T3 |
| Owners < 20K, single-title dev | Excluded (fails multi-title gate) |

If a dev with apps in T3 later releases a title above 100K owners, the new
title enters T2 on its next refresh, and the dev's existing T3 titles are
**promoted** to T2 on the next monthly cycle. Promotion ensures the merged
dataset converges to the same set of methodology-passing apps over time,
regardless of which tier surfaced them first.

## Data layout

```
data_v2/
├── tier_1/                # Refreshed weekly
│   ├── games.csv
│   ├── steamspy_insights.csv
│   ├── genres.csv
│   ├── tags.csv
│   ├── reviews.csv
│   └── categories.csv
├── tier_2/                # Refreshed monthly
│   └── (same shape)
├── tier_3/                # Refreshed quarterly
│   └── (same shape)
├── tier_4/                # Refreshed annually
│   └── (same shape)
└── merged/                # Produced by scripts/merge_tiers.py
    ├── games.csv          # T1 + T2 + T3 + T4 unioned, deduped, tier_origin col
    ├── steamspy_insights.csv
    ├── genres.csv
    ├── tags.csv
    ├── reviews.csv
    └── categories.csv
```

The Streamlit app and `investor_pipeline.py` read from `data_v2/merged/`. Tier
subdirectories are inputs to the merge step; consumers don't need to know
which tier an app came from (though `tier_origin` is preserved as a column
in `merged/` for audit).

## Running a tier refresh

In `refresh_steam_data.ipynb`:

```python
# Cell 1 config
TIER = 1   # or 2, 3, 4, or "ALL"
```

Then Runtime → Run all. The notebook will:

1. Pull the full Steam catalogue (Phase 1, fast)
2. Run SteamSpy bulk to get dev/owners for all apps (Phase 2, ~60 min — does NOT need to repeat per tier in the same session if you run TIER changes in sequence)
3. Apply methodology gates + tier slice (Phase 3, instant)
4. appdetails for tier-N apps only (Phase 4, varies by tier)
5. Reshape into CSVs in `data_v2/tier_N/` (Phase 5, fast)
6. Push to `main` (Cell 8)

After all tiers you care about are scraped, run `scripts/merge_tiers.py` to
produce `data_v2/merged/`, then run `investor_pipeline.py` against the merged
data to get refreshed candidates.

## Bootstrap plan (first-time fill)

| Phase | What | Time |
|---|---|---|
| Tonight | TIER=1 bootstrap | ~2 hr |
| Tomorrow | TIER=2 bootstrap | ~3 hr |
| Next weekend | TIER=3 bootstrap | ~6 hr |
| Later (optional) | TIER=4 bootstrap | ~15 hr |

After the bootstrap, the regular weekly/monthly/quarterly cadence kicks in
and nothing is ever this slow again.

## Audit log

Each tier directory carries a `_meta.json` (auto-written by the notebook) with:

- Refresh date
- TIER value
- MULTI_TITLE_MIN, ACTIVE_WITHIN_YEARS, AAA_OWNERS_FLOOR at time of scrape
- Number of apps in tier before/after methodology gates
- ETA vs actual runtime

This preserves the link between any merged-data row and the methodology
parameters under which it was scraped — essential for the Handshake AI
Showcase claim that "results are reproducible under Oct 2024 methodology."

## What this is not

- **Not a sampling strategy.** Every app in the methodology-pass set will
  eventually be scraped (T1+T2+T3+T4 = full set). Tiers only decide order.
- **Not a filter relaxation.** Multi-title, non-AAA, active <5y still apply.
- **Not lossy.** Running all four tiers and merging produces a dataset
  methodologically identical to a single 19-hour scrape.
- **Not Steam-rate-limit avoidance.** Each tier still respects 1.5s/appdetails.
  Tiers help your session budget, not Steam's.

## See also

- [`notebooks/refresh_steam_data.ipynb`](../notebooks/refresh_steam_data.ipynb) — the notebook with `TIER` config
- [`scripts/merge_tiers.py`](../scripts/merge_tiers.py) — merges per-tier CSVs into `merged/`
- [`docs/refresh-runbook.md`](refresh-runbook.md) — original single-scrape runbook
