"""Steam Threshold Calibration — v1

A single-page Streamlit tool for finding noise-removal thresholds that make
the Steam marketplace legible enough to study discovery and traction.

Run locally:
    streamlit run app.py
"""
from __future__ import annotations
import io
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from loader import load, OWNERS_ORDER, OWNERS_RANK
from filters import apply_all
from findings_content import render_findings_tab, render_methodology_tab

st.set_page_config(page_title="Steam Threshold Calibration", layout="wide")


# ---------- Data loading (cached) ----------
@st.cache_data(show_spinner="Loading Steam dataset…")
def get_data():
    return load("data")


df = get_data()
ALL_GENRES = sorted({g for lst in df["genres_list"].dropna() for g in (lst or [])})
ALL_CATEGORIES = sorted({c for lst in df["categories_list"].dropna() for c in (lst or [])})
HAS_REVIEWS = df["total_reviews"].notna().any()


# ---------- Sidebar ----------
st.sidebar.title("Filters")

with st.sidebar.expander("1. Data hygiene (exclude bad rows)", expanded=True):
    hyg = {
        "require_release_date": st.checkbox("Require valid release date", True),
        "require_owners_band": st.checkbox("Require SteamSpy owners band", True),
        "require_developer": st.checkbox("Require developer", True),
        "require_publisher": st.checkbox("Require publisher", True),
        "paid_requires_price": st.checkbox("Paid titles must have a price", True),
        "drop_future_release": st.checkbox("Drop future release dates", True),
    }
    if HAS_REVIEWS:
        hyg["require_review_row"] = st.checkbox(
            "Require review row present (not total > 0)", False,
            help="Drops the few rows with no reviews record at all. Zero-review titles are kept."
        )

with st.sidebar.expander("2. Structural exclusions", expanded=True):
    struct = {
        "exclude_demos": st.checkbox("Exclude demos", True),
        "exclude_free_to_play": st.checkbox("Exclude free-to-play", True),
        "require_english": st.checkbox(
            "Require English language", True,
            help="Title's languages field contains 'English'. ~91% of the dataset."
        ),
        "require_us_available": st.checkbox(
            "Require Steam store listing (US-availability proxy)", True,
            help="Title has a parseable currency code in its price_overview "
                 "(≈76k of 140k rows). Scrape was made from a non-US IP so "
                 "currency=USD is not a reliable filter; a real priced listing "
                 "in any currency is the strongest available proxy. Excludes "
                 "delisted and region-restricted titles."
        ),
    }

with st.sidebar.expander("3. Analytical thresholds (off by default)", expanded=True):
    st.caption(
        "All analytical thresholds default to OFF — the post-structural population "
        "shows in full so you can see the noise before deciding where to cut."
    )
    min_band = st.select_slider(
        "Minimum owners band (primary anchor)",
        options=OWNERS_ORDER,
        value=OWNERS_ORDER[0],  # lowest band = no cut
    )
    min_ccu = st.number_input("Minimum concurrent users yesterday", 0, 100000, 0, step=1)
    age_max_default = float(np.ceil(df["release_age_years"].max())) if df["release_age_years"].notna().any() else 30.0
    age_range = st.slider("Release age (years since 2024-10-28)", 0.0, age_max_default, (0.0, age_max_default), 0.25)
    price_max_default = float(np.ceil(df["price_usd"].max())) if df["price_usd"].notna().any() else 1000.0
    price_range = st.slider("Price (USD)", 0.0, price_max_default, (0.0, price_max_default), 0.5)
    dev_max = int(df["dev_output_count"].max())
    dev_range = st.slider(
        "Developer output count (titles in dataset)",
        1, dev_max, (1, dev_max),
    )
    genres_any = st.multiselect("Genres (any-of)", ALL_GENRES, [])
    categories_any = st.multiselect("Steam categories (any-of)", ALL_CATEGORIES, [])

    if HAS_REVIEWS:
        st.markdown("**Review-based thresholds**")
        st.caption(
            "Use with care: if reviews are also your response variable, applying "
            "a review threshold here introduces circularity. Prefer leaving these "
            "at 0 unless you're explicitly studying titles above a review floor."
        )
        min_total_reviews = st.number_input("Minimum total reviews", 0, 1_000_000, 0, step=10)
        min_pct_positive = st.slider("Minimum % positive", 0, 100, 0)
        min_reviews_per_year = st.number_input("Minimum reviews per year (velocity)", 0.0, 100000.0, 0.0, step=1.0)
    else:
        min_total_reviews = 0
        min_pct_positive = 0
        min_reviews_per_year = 0.0

ana = {
    "min_owners_band": min_band,
    "min_concurrent_users": int(min_ccu),
    "release_age_range": age_range,
    "price_range": price_range,
    "dev_output_range": dev_range,
    "genres_any": genres_any,
    "categories_any": categories_any,
    "min_total_reviews": int(min_total_reviews),
    "min_pct_positive": int(min_pct_positive),
    "min_reviews_per_year": float(min_reviews_per_year),
}


# ---------- Apply filters ----------
filtered, counts = apply_all(df, hyg, struct, ana)


# ---------- Header counters ----------
st.title("Steam Threshold Calibration")
st.caption("Scrape: October 2024 — single-snapshot calibration. v1 (calibration mode).")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Raw rows", f"{counts['raw']:,}")
c2.metric("After hygiene", f"{counts['after_hygiene']:,}",
          f"-{counts['raw']-counts['after_hygiene']:,}")
c3.metric("After structural", f"{counts['after_structural']:,}",
          f"-{counts['after_hygiene']-counts['after_structural']:,}")
c4.metric("After analytical", f"{counts['after_analytical']:,}",
          f"-{counts['after_structural']-counts['after_analytical']:,}")

if len(filtered) == 0:
    st.warning("No rows survive the current filter combination. Loosen a threshold.")
    st.stop()


# ---------- Tabs ----------
(tab_survival, tab_dist, tab_sweep, tab_cohort, tab_breakdowns,
 tab_findings, tab_method) = st.tabs(
    ["Survival curve", "Distribution profile", "Threshold sweep", "Cohort table",
     "Cohort breakdowns", "Findings", "Methodology"]
)


# ---- Tab 1: Survival ----
with tab_survival:
    st.subheader("Population surviving at each owners-band cutoff")
    st.caption(
        "Apply the current hygiene + structural filters, then sweep the minimum "
        "owners band from lowest to highest. Look for natural elbows."
    )
    base = df[
        (df.index.isin(filtered.index)) | True  # we want hygiene+structural only here
    ].copy()
    # Reapply only hygiene+structural to get the baseline for sweeping
    from filters import hygiene_mask, structural_mask
    hs = hygiene_mask(df, hyg) & structural_mask(df, struct)
    base = df[hs]
    rows = []
    for band in OWNERS_ORDER:
        rk = OWNERS_RANK[band]
        n = int((base["owners_rank"] >= rk).sum())
        rows.append({"min_band": band, "rank": rk, "surviving": n})
    sdf = pd.DataFrame(rows)
    fig = px.line(sdf, x="min_band", y="surviving", markers=True,
                  log_y=True, labels={"min_band": "Minimum owners band", "surviving": "Surviving titles (log)"})
    fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(sdf, use_container_width=True, hide_index=True)


# ---- Tab 2: Distribution profile ----
with tab_dist:
    st.subheader("Distribution profile of the filtered population")
    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(filtered, x="owners_rank", nbins=len(OWNERS_ORDER),
                           title="Owners band (ordinal rank)")
        st.plotly_chart(fig, use_container_width=True)
        fig = px.histogram(filtered, x="price_usd", nbins=40, title="Price (USD)")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.histogram(filtered, x="release_age_years", nbins=40, title="Release age (years)")
        st.plotly_chart(fig, use_container_width=True)
        ccu = filtered["concurrent_users_yesterday"].fillna(0)
        ccu_log = np.log10(ccu.replace(0, np.nan)).dropna()
        fig = px.histogram(ccu_log, nbins=40, title="log10(concurrent users yesterday), > 0 only")
        st.plotly_chart(fig, use_container_width=True)

    if HAS_REVIEWS:
        st.markdown("#### Reviews")
        col3, col4 = st.columns(2)
        with col3:
            tr = filtered["total_reviews"].fillna(0)
            tr_log = np.log10(tr.replace(0, np.nan)).dropna()
            fig = px.histogram(tr_log, nbins=40, title="log10(total reviews), > 0 only")
            st.plotly_chart(fig, use_container_width=True)
        with col4:
            fig = px.histogram(filtered["pct_positive"].dropna(), nbins=40, title="% positive")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Adoption-vs-response cross-check")
        st.caption(
            "How tightly do the two adoption signals (owners band) and the response "
            "signal (review count) agree across the filtered cohort? Tighter clustering "
            "around a monotone trend = better-behaved filter set."
        )
        sub = filtered.dropna(subset=["total_reviews", "owners_rank"]).copy()
        sub = sub[sub["total_reviews"] > 0]
        if len(sub) > 0:
            sub["log10_total_reviews"] = np.log10(sub["total_reviews"])
            # Sample to keep plot snappy on very large cohorts
            if len(sub) > 8000:
                sub = sub.sample(8000, random_state=42)
            fig = px.scatter(sub, x="owners_rank", y="log10_total_reviews",
                             hover_data=["name", "owners_range", "total_reviews", "pct_positive"],
                             opacity=0.35, title="owners_rank vs log10(total_reviews)")
            st.plotly_chart(fig, use_container_width=True)


# ---- Tab 3: Threshold sweep ----
with tab_sweep:
    st.subheader("How distribution moments shift as the owners-band threshold tightens")
    st.caption(
        "For each candidate owners-band cutoff, recompute the response variable's "
        "summary stats. Stable moments across a band of cutoffs = a robust threshold."
    )
    sweep_options = ["price_usd", "release_age_years", "concurrent_users_yesterday", "dev_output_count"]
    if HAS_REVIEWS:
        sweep_options += ["total_reviews", "pct_positive", "reviews_per_year"]
    response_var = st.selectbox(
        "Response variable",
        sweep_options,
        index=0,
    )
    from filters import hygiene_mask, structural_mask
    hs = hygiene_mask(df, hyg) & structural_mask(df, struct)
    base = df[hs]
    rows = []
    for band in OWNERS_ORDER:
        rk = OWNERS_RANK[band]
        sub = base[base["owners_rank"] >= rk][response_var].dropna()
        if len(sub) < 5:
            continue
        rows.append({
            "min_band": band, "n": len(sub),
            "median": float(sub.median()),
            "mean": float(sub.mean()),
            "iqr": float(sub.quantile(0.75) - sub.quantile(0.25)),
            "skew": float(sub.skew()) if len(sub) > 2 else np.nan,
        })
    mdf = pd.DataFrame(rows)
    if len(mdf):
        fig = go.Figure()
        for col, name in [("median", "Median"), ("mean", "Mean")]:
            fig.add_trace(go.Scatter(x=mdf["min_band"], y=mdf[col], name=name, mode="lines+markers"))
        fig.update_layout(title=f"Central tendency of {response_var} vs. owners-band cutoff",
                          xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.line(mdf, x="min_band", y="skew", markers=True,
                       title=f"Skewness of {response_var} vs. owners-band cutoff")
        fig2.update_xaxes(tickangle=-30)
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(mdf, use_container_width=True, hide_index=True)


# ---- Tab 4: Cohort table ----
with tab_cohort:
    st.subheader("Surviving titles")
    show_cols = ["app_id", "name", "developer", "publisher", "type", "is_free",
                 "release_date", "owners_range", "concurrent_users_yesterday",
                 "price_usd", "release_age_years", "dev_output_count",
                 "total_reviews", "pct_positive", "reviews_per_year",
                 "review_score_label", "metacritic_score"]
    show_cols = [c for c in show_cols if c in filtered.columns]
    sort_view = filtered.sort_values("owners_rank", ascending=False)[show_cols]
    st.dataframe(sort_view, use_container_width=True, hide_index=True)
    buf = io.StringIO()
    filtered[show_cols].to_csv(buf, index=False)
    st.download_button("Download filtered cohort (CSV)", buf.getvalue(),
                       file_name="filtered_cohort.csv", mime="text/csv")


# ---- Tab 5: Cohort breakdowns ----
with tab_breakdowns:
    st.subheader("Cohort breakdowns")
    st.caption(
        "Bucketed summaries of the filtered cohort. Useful for spotting where "
        "the noise lives — e.g. how many surviving titles sit in the bottom "
        "review band, or how prolific the average surviving developer is."
    )

    # --- Reviews breakdown ---
    st.markdown("### By total reviews")
    review_bins = [-1, 0, 9, 49, 249, 999, 4999, 24999, 1e12]
    review_labels = [
        "0 (no reviews)",
        "1–9",
        "10–49",
        "50–249",
        "250–999",
        "1,000–4,999",
        "5,000–24,999",
        "25,000+",
    ]
    fr = filtered.copy()
    fr["_review_bucket"] = pd.cut(
        fr["total_reviews"].fillna(0), bins=review_bins, labels=review_labels
    )
    review_tbl = (
        fr.groupby("_review_bucket", observed=True)
        .agg(
            titles=("app_id", "count"),
            median_owners_rank=("owners_rank", "median"),
            median_price=("price_usd", "median"),
            median_pct_positive=("pct_positive", "median"),
            median_reviews_per_year=("reviews_per_year", "median"),
        )
        .reset_index()
        .rename(columns={"_review_bucket": "Reviews bucket"})
    )
    review_tbl["% of cohort"] = (review_tbl["titles"] / len(fr) * 100).round(2)
    review_tbl = review_tbl[[
        "Reviews bucket", "titles", "% of cohort", "median_owners_rank",
        "median_price", "median_pct_positive", "median_reviews_per_year",
    ]]
    st.dataframe(review_tbl, use_container_width=True, hide_index=True)

    fig = px.bar(review_tbl, x="Reviews bucket", y="titles",
                 title="Titles per review bucket (current cohort)")
    st.plotly_chart(fig, use_container_width=True)

    # --- Developer output breakdown ---
    st.markdown("### By developer output (titles per developer in the dataset)")
    st.caption(
        "Developer output = number of titles attributed to that developer across "
        "the entire raw dataset. A solo developer with one title sits in the "
        "'1 (solo)' bucket; established studios climb into the higher buckets. "
        "This is a useful proxy for separating asset-flip / shovelware studios "
        "from established developers."
    )
    dev_bins = [0, 1, 4, 9, 24, 99, 1e6]
    dev_labels = [
        "1 (solo)",
        "2–4",
        "5–9",
        "10–24",
        "25–99",
        "100+",
    ]
    fr["_dev_bucket"] = pd.cut(
        fr["dev_output_count"].fillna(0), bins=dev_bins, labels=dev_labels
    )
    dev_tbl = (
        fr.groupby("_dev_bucket", observed=True)
        .agg(
            developers=("developer", "nunique"),
            titles=("app_id", "count"),
            median_owners_rank=("owners_rank", "median"),
            median_total_reviews=("total_reviews", "median"),
            median_pct_positive=("pct_positive", "median"),
        )
        .reset_index()
        .rename(columns={"_dev_bucket": "Developer output bucket"})
    )
    dev_tbl["% of titles"] = (dev_tbl["titles"] / len(fr) * 100).round(2)
    dev_tbl = dev_tbl[[
        "Developer output bucket", "developers", "titles", "% of titles",
        "median_owners_rank", "median_total_reviews", "median_pct_positive",
    ]]
    st.dataframe(dev_tbl, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(dev_tbl, x="Developer output bucket", y="developers",
                     title="Unique developers per bucket")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(dev_tbl, x="Developer output bucket", y="titles",
                     title="Titles per bucket")
        st.plotly_chart(fig, use_container_width=True)

    # --- Symmetric trim by review count ---
    st.markdown("### Symmetric trim by review count")
    st.caption(
        "Bottom-up trimming pairs each low-review cut with an equally-sized cut "
        "from the top end of the review distribution. The idea: low-review titles "
        "are background clutter, but the ultra-popular outliers (Counter-Strike, "
        "Palworld, etc.) are also distortionary mass that drags means and skew. "
        "Symmetric trimming preserves the middle of the distribution — the "
        "market the research is actually trying to study."
    )

    max_low_cut = st.slider(
        "Trim titles with at most N reviews (and the same count from the top)",
        0, 50, 10, 1,
        help="Step 0 = drop 0-review titles only. Step 1 = drop ≤1-review titles. Etc."
    )

    rev_series = filtered["total_reviews"].fillna(0).astype(int)
    trim_rows = []
    for n in range(0, max_low_cut + 1):
        low_mask = rev_series <= n
        n_low = int(low_mask.sum())
        if n_low == 0:
            continue
        # Take the top n_low titles by review count (any ties broken arbitrarily)
        kept = filtered[~low_mask].copy()
        if len(kept) <= n_low:
            continue
        top_threshold_rank = kept["total_reviews"].fillna(0).nlargest(n_low).min()
        top_mask = kept["total_reviews"].fillna(0) >= top_threshold_rank
        # Refine to exactly n_low rows (handles ties at the boundary)
        top_idx = kept[top_mask].nlargest(n_low, "total_reviews").index
        middle = kept.drop(top_idx)
        # Compute middle stats
        mid_rev = middle["total_reviews"].dropna()
        log_mid = np.log10(mid_rev.replace(0, np.nan)).dropna()
        if len(log_mid) >= 8:
            sample = log_mid.sample(min(len(log_mid), 5000), random_state=42)
            sh_p = float(stats.shapiro(sample).pvalue)
        else:
            sh_p = np.nan
        trim_rows.append({
            "low cutoff (≤ N reviews)": n,
            "bottom dropped": n_low,
            "top dropped": n_low,
            "middle N": len(middle),
            "% of cohort kept": round(len(middle) / len(filtered) * 100, 2),
            "middle median reviews": float(mid_rev.median()) if len(mid_rev) else np.nan,
            "middle median % positive": float(middle["pct_positive"].median()),
            "middle skew (log10 reviews)": float(log_mid.skew()) if len(log_mid) > 2 else np.nan,
            "Shapiro p (log10 reviews)": sh_p,
        })
    trim_df = pd.DataFrame(trim_rows)
    st.dataframe(trim_df, use_container_width=True, hide_index=True)

    if len(trim_df):
        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(trim_df, x="low cutoff (≤ N reviews)",
                          y="middle skew (log10 reviews)", markers=True,
                          title="Middle-distribution skew shrinks toward 0 as we trim")
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.line(trim_df, x="low cutoff (≤ N reviews)",
                          y="% of cohort kept", markers=True,
                          title="Share of cohort retained after symmetric trim")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            "**How to read this:** as the low cutoff climbs, the middle skew "
            "should drift toward zero and the Shapiro p-value should climb (less "
            "non-normal). The level at which skew flattens and p stabilizes is "
            "a candidate threshold pair to record on the Findings tab."
        )

    st.markdown("### Top developers in the current cohort")
    top_devs = (
        filtered.groupby("developer")
        .agg(
            titles_in_cohort=("app_id", "count"),
            total_reviews_sum=("total_reviews", "sum"),
            median_pct_positive=("pct_positive", "median"),
            top_owners_band=("owners_range", lambda s: s.value_counts().index[0] if len(s) else None),
        )
        .reset_index()
        .sort_values("titles_in_cohort", ascending=False)
        .head(25)
    )
    st.dataframe(top_devs, use_container_width=True, hide_index=True)


# ---- Tab 6: Findings ----
def _interactive_normality_ui():
    """Interactive normality check on the current filtered cohort."""
    st.markdown("### Run a normality check on the current filtered cohort")
    st.caption(
        "Apply your own sidebar filters, then pick a response variable below. "
        "This sub-tab runs the Shapiro–Wilk and D'Agostino K² tests live on "
        "whatever survives the current filter combination, and shows the "
        "matching Q–Q plot."
    )
    response_options = ["price_usd", "release_age_years", "concurrent_users_yesterday",
                        "owners_rank", "dev_output_count"]
    if HAS_REVIEWS:
        response_options += ["total_reviews", "pct_positive", "reviews_per_year",
                             "metacritic_score", "recommendations"]
    rvar = st.selectbox(
        "Response variable for normality test",
        response_options,
        index=response_options.index("reviews_per_year") if "reviews_per_year" in response_options else 0,
        key="findings_rvar",
    )
    log_transform = st.checkbox(
        "Apply log10 transform (recommended for skewed counts/prices)", False,
        key="findings_log_transform")

    series = filtered[rvar].dropna()
    if log_transform:
        series = np.log10(series.replace(0, np.nan)).dropna()

    if len(series) < 8:
        st.info("Need at least 8 values for normality tests.")
    else:
        sample = series.sample(min(len(series), 5000), random_state=42)
        sh_stat, sh_p = stats.shapiro(sample)
        try:
            da_stat, da_p = stats.normaltest(series)
        except ValueError:
            da_stat, da_p = (np.nan, np.nan)

        c1, c2, c3 = st.columns(3)
        c1.metric("N", f"{len(series):,}")
        c2.metric("Shapiro–Wilk p", f"{sh_p:.4g}",
                  "normal-ish" if sh_p > 0.05 else "not normal")
        c3.metric("D'Agostino K² p", f"{da_p:.4g}",
                  "normal-ish" if da_p > 0.05 else "not normal")

        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(series, nbins=50,
                               title=f"Histogram of {'log10 ' if log_transform else ''}{rvar}")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            qq = stats.probplot(series, dist="norm")
            x = np.array(qq[0][0])
            y = np.array(qq[0][1])
            slope, intercept, _ = qq[1]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=y, mode="markers", name="Sample"))
            fig.add_trace(go.Scatter(x=x, y=slope*x + intercept, mode="lines",
                                     name="Normal reference"))
            fig.update_layout(title="Q–Q plot vs. normal",
                              xaxis_title="Theoretical quantiles",
                              yaxis_title="Sample quantiles")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            "**How to read this:** A non-significant p-value (> 0.05) on either test, "
            "plus a Q–Q plot whose points hug the reference line, means the current "
            "filter set has produced a near-normal distribution on this response variable. "
            "Record the filter combination — that's a candidate finding."
        )

    st.divider()
    st.subheader("Save / log this filter combination")
    note = st.text_input("Optional note for this filter snapshot", key="findings_note")
    if st.button("Append to findings.log", key="findings_save_btn"):
        import json, datetime, pathlib
        rec = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "n_surviving": len(filtered),
            "hygiene": hyg, "structural": struct, "analytical": ana,
            "note": note,
        }
        pathlib.Path("findings.log").open("a").write(json.dumps(rec, default=str) + "\n")
        st.success("Saved to findings.log")

with tab_findings:
    render_findings_tab(interactive_normality_fn=_interactive_normality_ui)


# ---- Tab 7: Methodology ----
with tab_method:
    render_methodology_tab(df, hyg, struct)
