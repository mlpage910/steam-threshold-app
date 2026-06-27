# Steam Data Refresh — Runbook

This runbook covers the [`refresh_steam_data.ipynb`](../notebooks/refresh_steam_data.ipynb) Colab notebook that refreshes the Steam dataset behind the indie-investor pipeline and commits the new CSVs straight to `main` in this repo.

## What it does

Two refresh scopes, chosen via the `SCOPE` constant in Cell 1:

| Scope | What it scans | Purpose | Wall time | Cost |
|---|---|---|---|---|
| **A** | The ~700 titles by the 254 known devs (146 candidates + 108 research pool) | Drift detection — owners shifts, new titles by known devs, dormancy flips | ~90 min | $0 |
| **B** | Full Steam catalogue → filtered to multi-title non-AAA cohort | Newcomer detection — devs who weren't on the radar in Oct 2024 | 3.5–5 hr | $0 |

Both scopes write 4 (or 6, with reviews + categories) loader-schema CSVs to `data_v2/` and commit to `main`.

## One-time setup (5 minutes)

### 1. GitHub fine-scoped PAT

1. Go to https://github.com/settings/personal-access-tokens/new (fine-grained, not classic)
2. **Token name:** `Colab — steam refresh`
3. **Expiration:** 90 days (or your preference)
4. **Repository access:** Only select repositories → `mlpage910/steam-threshold-app`
5. **Repository permissions:**
   - Contents: **Read and write**
   - Metadata: Read-only (auto-selected)
6. Click **Generate token**, copy it (starts with `github_pat_...`)

### 2. Steam Web API key

1. Visit https://steamcommunity.com/dev/apikey
2. Sign in with any Steam account
3. **Domain:** `localhost` (anything works)
4. Agree to terms → copy the key

### 3. Store both in Colab Secrets

In Colab, click the 🔑 **Secrets** icon (left sidebar):

| Name | Value | Notebook access |
|---|---|---|
| `GITHUB_PAT` | paste the GitHub token | ON |
| `STEAM_API_KEY` | paste the Steam key | ON |

These persist across Colab sessions on your Google account. You'll never see them again — and neither will I.

## How to run

1. Open the notebook in Colab via the badge in the [main README](../README.md) (or this direct link: [Open in Colab](https://colab.research.google.com/github/mlpage910/steam-threshold-app/blob/main/notebooks/refresh_steam_data.ipynb))
2. **Cell 1:** Edit `SCOPE = "A"` for a quick refresh or `"B"` for newcomer hunt
3. Runtime → **Run all**
4. Wait. Scope A finishes in ~90 min, Scope B in ~3.5–5 hr
5. Cell 8 pushes to `main`; a link to the new `data_v2/` folder prints when done
6. (Optional) point the Streamlit app at the new data: `DATA_DIR=data_v2 streamlit run app.py`

## Phase-by-phase

| Phase | Cell | Scope A time | Scope B time |
|---|---|---|---|
| 1. Resolve app universe | 3 | 5 sec (read CSVs from repo) | 30 sec (paginated GetAppList) |
| 2. SteamSpy bulk pre-filter | 4 | skipped | 50–60 min (1 page/60s × ~60 pages) |
| 3. Cohort filter (in-memory) | 5 | instant | 2 sec |
| 4. appdetails + per-app SteamSpy | 6 | 30–60 min (~1,400 calls) | 2.5–4 hr (~6–10K calls @ 1.5s) |
| 5. Reshape → 4 CSVs | 7 | 1 min | 3 min |
| 6. Commit to `main` | 8 | 15 sec | 15 sec |

Phase 4 **checkpoints every 500 calls** and writes a `done_ids` file. If Colab disconnects (12-hour limit, browser tab closes, etc.), rerunning the notebook resumes from where it left off.

## Cohort gates (matches your main pipeline)

- **Multi-title:** dev has ≥ 2 titles in Steam catalogue (configurable: `MULTI_TITLE_MIN`)
- **Active:** dev's newest release within 5 years of today (configurable: `ACTIVE_WITHIN_YEARS`)
- **Non-AAA:** dev has no title at owners band ≥ 5M (configurable: `AAA_OWNERS_FLOOR`)

The active gate runs *after* appdetails since release dates live there. The multi-title and non-AAA gates run on SteamSpy bulk (Scope B) or are implicit (Scope A — your existing devs already pass these).

## Output schema (matches `loader.py`)

| File | Key columns |
|---|---|
| `games.csv` | `app_id, name, type, is_free, release_date, languages, price_overview` |
| `steamspy_insights.csv` | `app_id, developer, publisher, owners_range, concurrent_users_yesterday, price, initial_price, genres, positive, negative` |
| `genres.csv` | `app_id, genre` (long format, one row per app-genre) |
| `tags.csv` | `app_id, tag, votes` (long format) |
| `reviews.csv` *(optional)* | `app_id, recommendations, metacritic_score` |
| `categories.csv` *(optional)* | `app_id, category` (e.g. Single-player, Multi-player) |

Schema is **identical** to the existing `data/` folder, so the Streamlit app, DuckDB loader, and `investor_pipeline.py` work without changes.

## A/B comparison

After a successful refresh, compare drift against the Oct 2024 baseline:

```python
from loader import load
base = load("data")          # frozen Oct 2024
new  = load("data_v2")       # fresh
# Devs new to v2:
new_devs = set(new.developer.dropna()) - set(base.developer.dropna())
# Owners drift on known devs:
shared = set(base.app_id) & set(new.app_id)
drift = (new.set_index("app_id").loc[list(shared), "owners_lower"]
         - base.set_index("app_id").loc[list(shared), "owners_lower"])
print(f"{len(new_devs):,} new devs; median owners drift {drift.median():.0f}")
```

## Troubleshooting

**"429 Too Many Requests" during appdetails (Phase 4):**
The notebook auto-retries with 30s backoff. If it persists, Steam has banned your IP for the day — increase `STEAM_RATE_SEC` to `2.0` in Cell 6 and resume tomorrow. Colab gives you a fresh IP per runtime.

**SteamSpy bulk returns 502 / empty pages (Phase 2):**
SteamSpy occasionally goes down. The retry decorator handles transient failures. If a whole hour passes without progress, try again later — SteamSpy is a one-person operation.

**"Missing GITHUB_PAT" assertion (Cell 2):**
Colab Secrets are per-notebook by default. Open the 🔑 icon, find your secret, toggle **Notebook access: ON** for this notebook.

**Push fails with "permission denied":**
Your fine-scoped PAT expired or doesn't include `Contents: Read and write`. Regenerate and update the Colab Secret.

**Resume after disconnect:**
Just re-open the notebook and Run All. Cell 6 reads `raw/appdetails_progress.txt` and skips done apps.

## Safety

- The notebook **never prints, logs, or commits** either secret.
- The PAT is fine-scoped to **only this repo, only Contents read/write**. It cannot access your other repos, Actions, settings, or any other GitHub surface.
- Revoke any time: https://github.com/settings/personal-access-tokens

## What to do with the new data

1. **Eyeball Phase 5 row counts** in the notebook output — Scope B should produce 5K–12K titles by ~800–1,500 cohort-candidate devs
2. **Diff against Oct 2024** using the A/B recipe above
3. **Run the investor pipeline on the refresh:** `python investor_pipeline.py --data data_v2`
4. **Compare candidate sets** — new candidates that weren't in the Oct 2024 146 are the newcomers
5. **Decide whether to update the live Streamlit app's default data dir** — if Scope B looks healthy, change `DATA_DIR` in `app.py` from `data` to `data_v2`
