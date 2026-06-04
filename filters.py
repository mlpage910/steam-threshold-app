"""Filter logic, kept separate from the UI so it can be unit-tested or reused
in notebooks. Each function returns a boolean Series aligned to the input df.

Three layers, in fixed order:
    1. Data hygiene  - drop rows with missing/invalid data
    2. Structural    - drop categorically different populations (demos, F2P)
    3. Analytical    - tunable thresholds for the research question
"""
from __future__ import annotations
import pandas as pd
from loader import OWNERS_RANK


# ---------- Layer 1: Data hygiene ----------
def hygiene_mask(df: pd.DataFrame, opts: dict) -> pd.Series:
    m = pd.Series(True, index=df.index)
    if opts.get("require_release_date", True):
        m &= df["release_date"].notna()
    if opts.get("require_owners_band", True):
        m &= df["owners_range"].notna()
    null_tokens = {"", "\\N", "None", "null", "NULL"}
    if opts.get("require_developer", True):
        m &= df["developer"].notna() & ~df["developer"].astype(str).str.strip().isin(null_tokens)
    if opts.get("require_publisher", True):
        m &= df["publisher"].notna() & ~df["publisher"].astype(str).str.strip().isin(null_tokens)
    if opts.get("paid_requires_price", True):
        # If marked as paid (is_free=0) but no price, drop
        paid_no_price = (df["is_free"] == 0) & df["price_usd"].isna()
        m &= ~paid_no_price
    if opts.get("drop_future_release", True):
        m &= df["release_date"] <= pd.Timestamp("2024-10-28")
    if opts.get("require_review_row", False) and "total_reviews" in df.columns:
        m &= df["total_reviews"].notna()
    return m


# ---------- Layer 2: Structural exclusions ----------
def structural_mask(df: pd.DataFrame, opts: dict) -> pd.Series:
    m = pd.Series(True, index=df.index)
    if opts.get("exclude_demos", True):
        m &= df["type"] != "demo"
    if opts.get("exclude_free_to_play", True):
        m &= df["is_free"] != 1
    if opts.get("require_english", True) and "has_english" in df.columns:
        m &= df["has_english"] == 1
    if opts.get("require_us_available", True) and "has_store_listing" in df.columns:
        # Operationalized as "has a Steam store listing with price metadata."
        # Scrape was made from a non-US IP, so currency=USD is not reliable;
        # any store listing is the strongest available proxy for "sold via Steam
        # store anywhere" — which in practice almost always includes the US.
        m &= df["has_store_listing"] == 1
    if opts.get("exclude_early_access", True) and "genres_list" in df.columns:
        # Early Access games are structurally different: incomplete builds,
        # evolving review counts, and wishlist-driven owner estimates make
        # the owners <-> reviews consistency check unreliable.
        m &= ~df["genres_list"].apply(
            lambda lst: isinstance(lst, list) and "Early Access" in lst
        )
    return m


# ---------- Layer 3: Analytical thresholds ----------
def analytical_mask(df: pd.DataFrame, opts: dict) -> pd.Series:
    m = pd.Series(True, index=df.index)

    min_owners_band = opts.get("min_owners_band")
    if min_owners_band:
        min_rank = OWNERS_RANK[min_owners_band]
        m &= df["owners_rank"] >= min_rank

    min_ccu = opts.get("min_concurrent_users", 0)
    if min_ccu > 0:
        m &= df["concurrent_users_yesterday"].fillna(0) >= min_ccu

    age_min, age_max = opts.get("release_age_range", (None, None))
    if age_min is not None:
        m &= df["release_age_years"] >= age_min
    if age_max is not None:
        m &= df["release_age_years"] <= age_max

    price_min, price_max = opts.get("price_range", (None, None))
    if price_min is not None:
        m &= df["price_usd"].fillna(-1) >= price_min
    if price_max is not None:
        m &= df["price_usd"].fillna(1e9) <= price_max

    dev_min, dev_max = opts.get("dev_output_range", (None, None))
    if dev_min is not None:
        m &= df["dev_output_count"] >= dev_min
    if dev_max is not None:
        m &= df["dev_output_count"] <= dev_max

    genres_any = opts.get("genres_any") or []
    if genres_any:
        m &= df["genres_list"].apply(
            lambda lst: bool(lst) and any(g in lst for g in genres_any)
        )

    categories_any = opts.get("categories_any") or []
    if categories_any:
        m &= df["categories_list"].apply(
            lambda lst: bool(lst) and any(c in lst for c in categories_any)
        )

    # Review-based analytical thresholds (response signals; use with care to
    # avoid circularity if reviews are also your outcome variable)
    min_reviews = opts.get("min_total_reviews", 0)
    if min_reviews > 0:
        m &= df["total_reviews"].fillna(0) >= min_reviews

    min_pct_pos = opts.get("min_pct_positive")
    if min_pct_pos is not None and min_pct_pos > 0:
        m &= df["pct_positive"].fillna(-1) >= min_pct_pos

    min_rpy = opts.get("min_reviews_per_year", 0)
    if min_rpy > 0:
        m &= df["reviews_per_year"].fillna(0) >= min_rpy

    return m


def apply_all(df: pd.DataFrame, hyg: dict, struct: dict, ana: dict):
    """Returns (filtered_df, stage_counts dict)."""
    h = hygiene_mask(df, hyg)
    s = structural_mask(df, struct)
    a = analytical_mask(df, ana)
    counts = {
        "raw": len(df),
        "after_hygiene": int(h.sum()),
        "after_structural": int((h & s).sum()),
        "after_analytical": int((h & s & a).sum()),
    }
    return df[h & s & a].copy(), counts
