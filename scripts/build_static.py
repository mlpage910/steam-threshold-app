"""Static-site fallback build script.

Renders the key views of the Streamlit app (survival curve, distribution
profile, threshold sweep, cohort summary, findings text) to a static HTML
site under `site/` that can be served by GitHub Pages.

This is a fallback for when the live Streamlit Community Cloud deployment is
unavailable, or for archival/reproducibility snapshots. It is intentionally
read-only — no sliders, no normality tests on demand. The full interactive
experience requires running `streamlit run app.py` locally or via Streamlit
Cloud.

Defaults (overridable via env vars):
    DATA_DIR        data
    OUT_DIR         site
    DEFAULT_OWNERS  "20,000 .. 50,000"   (analytical min owners band)
    DEFAULT_AGE_MAX 5                     (years)
"""
from __future__ import annotations
import os
import sys
import shutil
from pathlib import Path
from textwrap import dedent

import pandas as pd
import plotly.express as px
import plotly.io as pio

# Make sibling modules importable when the script is run from repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from loader import load, OWNERS_ORDER, OWNERS_RANK  # noqa: E402
from filters import apply_all  # noqa: E402

DATA_DIR = Path(os.environ.get("DATA_DIR", REPO_ROOT / "data"))
OUT_DIR = Path(os.environ.get("OUT_DIR", REPO_ROOT / "site"))
DEFAULT_OWNERS = os.environ.get("DEFAULT_OWNERS", "20,000 .. 50,000")
DEFAULT_AGE_MAX = float(os.environ.get("DEFAULT_AGE_MAX", "5"))


def have_data() -> bool:
    required = ["games.csv", "steamspy_insights.csv", "genres.csv", "tags.csv"]
    return all((DATA_DIR / f).exists() for f in required)


def placeholder_site() -> None:
    """Render a placeholder site when no CSVs are present in `data/`."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(dedent("""\
        <!doctype html>
        <html lang="en"><head><meta charset="utf-8">
        <title>Steam Threshold Calibration — static fallback</title>
        <style>
          body{font-family:-apple-system,Segoe UI,sans-serif;max-width:760px;
               margin:4rem auto;padding:0 1.5rem;color:#222;line-height:1.55}
          h1{color:#6b1414}
          code{background:#f5f2eb;padding:0.1rem 0.35rem;border-radius:3px}
          .note{background:#fbf6ed;border-left:3px solid #c89b3c;
                padding:0.8rem 1rem;margin:1.2rem 0}
        </style></head><body>
        <h1>Steam Threshold Calibration</h1>
        <p>This static site is the fallback view. The build job did not find a
           Steam scrape in <code>data/</code>, so the figures below are blank.</p>
        <div class="note">
          To populate this site, drop the four CSVs from
          <a href="https://github.com/NewbieIndieGameDev/steam-insights">
          NewbieIndieGameDev/steam-insights</a> into <code>data/</code> and
          re-run the workflow, or run <code>streamlit run app.py</code> locally
          for the full interactive experience.
        </div>
        <p>See <a href="https://github.com/mlpage910/steam-threshold-app">the
           repository README</a> for the full setup.</p>
        </body></html>
    """))


def page(body: str, title: str) -> str:
    return dedent(f"""\
        <!doctype html>
        <html lang="en"><head><meta charset="utf-8">
        <title>{title}</title>
        <style>
          body{{font-family:-apple-system,Segoe UI,sans-serif;max-width:1100px;
               margin:2rem auto;padding:0 1.2rem;color:#222;line-height:1.5}}
          h1,h2{{color:#6b1414}}
          nav a{{margin-right:1rem;color:#1f3a5f;text-decoration:none}}
          nav a:hover{{text-decoration:underline}}
          .panel{{margin:1.5rem 0;border:1px solid #e7e2d6;padding:1rem;
                  border-radius:4px;background:#fbfaf6}}
          table{{border-collapse:collapse;margin:0.5rem 0}}
          th,td{{border:1px solid #e0dccb;padding:0.35rem 0.7rem;font-size:0.92rem}}
          th{{background:#f1ebd9;text-align:left}}
        </style></head><body>
        <nav>
          <strong>Steam Threshold Calibration</strong> ·
          <a href="index.html">Overview</a>
          <a href="survival.html">Survival</a>
          <a href="distribution.html">Distribution</a>
          <a href="sweep.html">Threshold sweep</a>
          <a href="cohort.html">Cohort</a>
        </nav>
        <hr>
        {body}
        <hr><p style="color:#888;font-size:0.85rem">Static snapshot rendered by
        <code>scripts/build_static.py</code>. For interactive sliders run
        <code>streamlit run app.py</code> locally.</p>
        </body></html>
    """)


def build_full(df: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Default thresholds, mirroring the app defaults
    hyg = dict(require_release_date=True, require_owners_band=True,
               require_developer=True, require_publisher=True,
               paid_requires_price=True, drop_future_release=True)
    struct = dict(exclude_demos=True, exclude_free_to_play=True,
                  require_english=True, require_us_available=True,
                  exclude_early_access=True)
    ana = dict(min_owners_band=DEFAULT_OWNERS,
               release_age_range=(0, DEFAULT_AGE_MAX))

    filtered, counts = apply_all(df, hyg, struct, ana)
    raw_n = counts["raw"]

    # --- Overview ---
    overview_table = "".join(
        f"<tr><td>{stage}</td><td style='text-align:right'>{counts[stage]:,}</td>"
        f"<td style='text-align:right'>{counts[stage]/raw_n*100:.1f}%</td></tr>"
        for stage in ["raw", "after_hygiene", "after_structural", "after_analytical"]
    )
    (OUT_DIR / "index.html").write_text(page(dedent(f"""\
        <h1>Steam Threshold Calibration — static snapshot</h1>
        <p class="panel">Static export of the Streamlit app's default cohort.
           For sliders + interactive filter exploration, run
           <code>streamlit run app.py</code> or visit the live Streamlit Cloud
           deployment (see README).</p>
        <h2>Filter stack at default thresholds</h2>
        <table>
          <tr><th>Stage</th><th>Surviving rows</th><th>% of raw</th></tr>
          {overview_table}
        </table>
        <p><strong>Defaults:</strong> min owners band ≥ <code>{DEFAULT_OWNERS}</code>,
           release age ≤ {DEFAULT_AGE_MAX}y, English required, store listing
           required, no demos / F2P / Early Access. All hygiene gates on.</p>
        <p>See the
           <a href="https://github.com/mlpage910/steam-threshold-app#three-filter-layers">
           README</a> for the three filter layers and how the
           <code>owners_range</code> ordinal mapping works.</p>
    """), "Steam Threshold Calibration"))

    # --- Survival curve ---
    survival_rows = []
    for band in OWNERS_ORDER:
        sub = df[df["owners_rank"] >= OWNERS_RANK[band]]
        survival_rows.append({"min_owners_band": band, "rank": OWNERS_RANK[band],
                              "surviving": len(sub)})
    surv_df = pd.DataFrame(survival_rows)
    fig = px.line(surv_df, x="rank", y="surviving", markers=True,
                  title="Survival curve — titles surviving as the min owners band rises")
    fig.update_xaxes(tickvals=surv_df["rank"], ticktext=surv_df["min_owners_band"],
                     tickangle=-40)
    fig.update_yaxes(type="log", title="surviving titles (log)")
    (OUT_DIR / "survival.html").write_text(page(
        "<h1>Survival curve</h1>" + pio.to_html(fig, include_plotlyjs="cdn",
                                                full_html=False),
        "Survival — Steam Threshold Calibration"))

    # --- Distribution profile ---
    fig1 = px.histogram(filtered, x="owners_rank", title="Owners band distribution",
                        nbins=14)
    fig1.update_xaxes(tickvals=list(range(len(OWNERS_ORDER))), ticktext=OWNERS_ORDER,
                      tickangle=-40)
    fig2 = px.histogram(filtered.query("price_usd > 0 and price_usd <= 60"),
                        x="price_usd", nbins=30, title="Price (USD) — paid only, ≤$60")
    fig3 = px.histogram(filtered, x="release_age_years", nbins=30,
                        title="Release age (years) at scrape date")
    dist_html = "".join(pio.to_html(f, include_plotlyjs="cdn", full_html=False)
                        for f in (fig1, fig2, fig3))
    (OUT_DIR / "distribution.html").write_text(page(
        "<h1>Distribution profile</h1>" + dist_html,
        "Distribution — Steam Threshold Calibration"))

    # --- Threshold sweep ---
    sweep_rows = []
    for band in OWNERS_ORDER:
        sub = df[df["owners_rank"] >= OWNERS_RANK[band]]
        sub_, _ = apply_all(sub,
                            {k: True for k in ["require_release_date",
                                               "require_owners_band",
                                               "require_developer",
                                               "require_publisher",
                                               "paid_requires_price",
                                               "drop_future_release"]},
                            struct, {})
        sweep_rows.append({
            "min_band": band, "rank": OWNERS_RANK[band], "n": len(sub_),
            "median_price": sub_["price_usd"].median(),
            "median_age": sub_["release_age_years"].median(),
            "median_dev_output": sub_["dev_output_count"].median(),
        })
    sw = pd.DataFrame(sweep_rows)
    fig_a = px.line(sw, x="rank", y="median_price", markers=True,
                    title="Median price across owners-band cutoffs")
    fig_b = px.line(sw, x="rank", y="median_age", markers=True,
                    title="Median release age across owners-band cutoffs")
    fig_c = px.line(sw, x="rank", y="median_dev_output", markers=True,
                    title="Median developer output across owners-band cutoffs")
    for f in (fig_a, fig_b, fig_c):
        f.update_xaxes(tickvals=sw["rank"], ticktext=sw["min_band"], tickangle=-40)
    sweep_html = "".join(pio.to_html(f, include_plotlyjs="cdn", full_html=False)
                         for f in (fig_a, fig_b, fig_c))
    (OUT_DIR / "sweep.html").write_text(page(
        "<h1>Threshold sweep</h1>"
        "<p>Median moments of the surviving cohort as the min-owners cutoff rises. "
        "Stable plateaus across multiple bands suggest robust thresholds.</p>"
        + sweep_html,
        "Threshold sweep — Steam Threshold Calibration"))

    # --- Cohort table (top 200 by owners_rank then ccu) ---
    cohort = filtered.sort_values(["owners_rank", "concurrent_users_yesterday"],
                                  ascending=False).head(200)
    cols = ["app_id", "name", "developer", "owners_range",
            "concurrent_users_yesterday", "price_usd", "release_age_years",
            "dev_output_count"]
    cohort_html = cohort[cols].to_html(index=False, classes="cohort", border=0,
                                       float_format=lambda v: f"{v:.1f}" if pd.notna(v) else "")
    (OUT_DIR / "cohort.html").write_text(page(
        f"<h1>Cohort sample (top 200 of {len(filtered):,})</h1>"
        f"<p>Filter: {DEFAULT_OWNERS} ≤ owners band, release ≤ {DEFAULT_AGE_MAX}y, "
        "demos / F2P / EA excluded.</p>" + cohort_html,
        "Cohort — Steam Threshold Calibration"))


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not have_data():
        print(f"[build_static] no scrape found in {DATA_DIR}, writing placeholder.")
        placeholder_site()
        return
    print(f"[build_static] loading scrape from {DATA_DIR}...")
    df = load(str(DATA_DIR))
    print(f"[build_static] loaded {len(df):,} rows. Rendering static site to {OUT_DIR}/...")
    build_full(df)
    print("[build_static] done.")


if __name__ == "__main__":
    main()
