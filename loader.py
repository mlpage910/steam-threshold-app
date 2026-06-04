"""DuckDB loader: builds an in-memory analysis table from the four CSVs.

Single source of truth for the app. Returns a pandas DataFrame with one row per
app_id and cleaned/typed columns ready for filtering.
"""
from __future__ import annotations
from pathlib import Path
import duckdb
import pandas as pd

# Ordinal mapping of SteamSpy owners bands (lower bound used for numeric sweeps).
OWNERS_ORDER = [
    "0 .. 20,000",
    "20,000 .. 50,000",
    "50,000 .. 100,000",
    "100,000 .. 200,000",
    "200,000 .. 500,000",
    "500,000 .. 1,000,000",
    "1,000,000 .. 2,000,000",
    "2,000,000 .. 5,000,000",
    "5,000,000 .. 10,000,000",
    "10,000,000 .. 20,000,000",
    "20,000,000 .. 50,000,000",
    "50,000,000 .. 100,000,000",
    "100,000,000 .. 200,000,000",
    "200,000,000 .. 500,000,000",
]
OWNERS_RANK = {band: i for i, band in enumerate(OWNERS_ORDER)}
# Lower-bound numeric values, in owner units
OWNERS_LOWER = {
    band: int(band.split("..")[0].strip().replace(",", "")) for band in OWNERS_ORDER
}


def load(data_dir: str | Path) -> pd.DataFrame:
    """Load all CSVs into a single typed analysis DataFrame."""
    d = Path(data_dir)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE games AS SELECT * FROM read_csv_auto('{d/'games.csv'}', header=True)")
    con.execute(f"CREATE TABLE spy   AS SELECT * FROM read_csv_auto('{d/'steamspy_insights.csv'}', header=True)")
    con.execute(f"CREATE TABLE genres AS SELECT * FROM read_csv_auto('{d/'genres.csv'}', header=True)")
    con.execute(f"CREATE TABLE tags  AS SELECT * FROM read_csv_auto('{d/'tags.csv'}', header=True)")
    # Optional tables (may not be present in every batch)
    has_reviews = (d / 'reviews.csv').exists()
    has_categories = (d / 'categories.csv').exists()
    if has_reviews:
        con.execute(f"CREATE TABLE reviews AS SELECT * FROM read_csv_auto('{d/'reviews.csv'}', header=True)")
    if has_categories:
        con.execute(f"CREATE TABLE categories AS SELECT * FROM read_csv_auto('{d/'categories.csv'}', header=True)")

    reviews_select = """
            ,TRY_CAST(r.positive AS BIGINT) AS positive_reviews,
            TRY_CAST(r.negative AS BIGINT) AS negative_reviews,
            TRY_CAST(r.total AS BIGINT) AS total_reviews,
            TRY_CAST(r.review_score AS INTEGER) AS review_score,
            r.review_score_description AS review_score_label,
            TRY_CAST(r.metacritic_score AS INTEGER) AS metacritic_score,
            TRY_CAST(r.recommendations AS BIGINT) AS recommendations
    """ if has_reviews else ""
    reviews_join = "LEFT JOIN reviews r ON g.app_id = r.app_id" if has_reviews else ""

    df = con.execute(f"""
        SELECT
            g.app_id,
            g.name,
            g.type,
            CAST(g.is_free AS INTEGER) AS is_free,
            TRY_CAST(g.release_date AS DATE) AS release_date,
            g.languages AS languages_raw,
            g.price_overview AS price_overview_raw,
            regexp_extract(g.price_overview, '\"currency\": \"([A-Z]+)\"', 1) AS store_currency,
            CASE WHEN g.languages ILIKE '%English%' THEN 1 ELSE 0 END AS has_english,
            -- A title has a real store listing if its price_overview JSON carries
            -- a parseable currency code. The empty-price_overview rows are typically
            -- delisted, region-restricted, or never sold.
            CASE WHEN regexp_extract(g.price_overview, '\"currency\": \"([A-Z]+)\"', 1) <> '' THEN 1 ELSE 0 END AS has_store_listing,
            s.developer,
            s.publisher,
            s.owners_range,
            s.concurrent_users_yesterday,
            TRY_CAST(s.price AS INTEGER) / 100.0 AS price_usd,
            TRY_CAST(s.initial_price AS INTEGER) / 100.0 AS initial_price_usd,
            s.genres AS spy_genres
            {reviews_select}
        FROM games g
        LEFT JOIN spy s ON g.app_id = s.app_id
        {reviews_join}
    """).df()

    # Derived columns
    df["owners_rank"] = df["owners_range"].map(OWNERS_RANK)
    df["owners_lower"] = df["owners_range"].map(OWNERS_LOWER)
    today = pd.Timestamp("2024-10-28")  # scrape date
    df["release_age_years"] = (today - df["release_date"]).dt.days / 365.25

    # Developer output count (titles per developer in dataset)
    dev_counts = df.groupby("developer")["app_id"].count().rename("dev_output_count")
    df = df.merge(dev_counts, on="developer", how="left")

    # Genre aggregation (list of strings per app)
    gdf = con.execute("SELECT app_id, genre FROM genres").df()
    genre_lists = gdf.groupby("app_id")["genre"].apply(list).rename("genres_list")
    df = df.merge(genre_lists, on="app_id", how="left")

    # Category aggregation (Steam categories, e.g. "Single-player", "Multi-player")
    if has_categories:
        cdf = con.execute("SELECT app_id, category FROM categories").df()
        cat_lists = cdf.groupby("app_id")["category"].apply(list).rename("categories_list")
        df = df.merge(cat_lists, on="app_id", how="left")
    else:
        df["categories_list"] = None

    # Derived review metrics
    if has_reviews:
        df["pct_positive"] = (df["positive_reviews"] /
                              df["total_reviews"].replace(0, pd.NA)) * 100.0
        # Reviews per year since release (engagement-velocity proxy)
        df["reviews_per_year"] = df["total_reviews"] / df["release_age_years"].where(
            df["release_age_years"] > 0)
    else:
        for c in ("positive_reviews", "negative_reviews", "total_reviews",
                  "review_score", "review_score_label", "metacritic_score",
                  "recommendations", "pct_positive", "reviews_per_year"):
            df[c] = None

    return df


if __name__ == "__main__":
    df = load("data")
    print(df.shape)
    print(df.dtypes)
    print(df.head(3))
