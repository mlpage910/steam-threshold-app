#!/usr/bin/env python3
"""
merge_tiers.py — Unify per-tier CSVs into a single data_v2/merged/ directory
consumed by investor_pipeline.py and the Streamlit app.

Tiers are produced by refresh_steam_data.ipynb with different TIER= values.
This script reads whatever tier_N/ subdirectories exist under data_v2/,
deduplicates by app_id (keeping the latest scrape for each app), tags every
row with a tier_origin column for audit, and writes the merged result.

Usage:
    python scripts/merge_tiers.py
    python scripts/merge_tiers.py --data-dir data_v2 --out merged

If a tier directory is missing (e.g. T4 not yet bootstrapped), the merge
still runs with whatever tiers ARE present and logs a warning.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime

import pandas as pd


CSV_NAMES = [
    "games.csv",
    "steamspy_insights.csv",
    "genres.csv",
    "tags.csv",
    "reviews.csv",
    "categories.csv",
]

TIER_LABELS = {
    "tier_1": 1,
    "tier_2": 2,
    "tier_3": 3,
    "tier_4": 4,
    "all": "ALL",
}


def find_tier_dirs(data_dir: Path) -> list[tuple[str, Path]]:
    """Return [(tier_label, path), ...] for every tier_N subdirectory."""
    found = []
    for sub in sorted(data_dir.iterdir()):
        if sub.is_dir() and sub.name in TIER_LABELS:
            found.append((sub.name, sub))
    return found


def load_csv_safely(path: Path) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return None


def merge_one_filename(filename: str, tier_dirs: list[tuple[str, Path]]) -> pd.DataFrame:
    """Concatenate one CSV across tiers, tag with tier_origin, dedupe by app_id."""
    frames = []
    for tier_label, tier_path in tier_dirs:
        df = load_csv_safely(tier_path / filename)
        if df is None or df.empty:
            print(f"    skip: {tier_path / filename} (missing or empty)")
            continue
        df["tier_origin"] = TIER_LABELS[tier_label]
        frames.append(df)
        print(f"    {tier_label}/{filename}: {len(df):,} rows")
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)

    # Dedup strategy: long-format files (genres, tags, categories) keep all rows;
    # wide files (games, steamspy_insights, reviews) dedup on app_id keeping
    # the lowest-numbered tier (most authoritative refresh).
    long_format = {"genres.csv", "tags.csv", "categories.csv"}
    if filename in long_format:
        # For long format, dedupe on (app_id, value) keeping lowest tier_origin
        value_col = {
            "genres.csv": "genre",
            "tags.csv": "tag",
            "categories.csv": "category",
        }[filename]
        if value_col in combined.columns and "app_id" in combined.columns:
            combined = combined.sort_values(["app_id", value_col, "tier_origin"])
            combined = combined.drop_duplicates(subset=["app_id", value_col], keep="first")
    else:
        if "app_id" in combined.columns:
            # Sort so lowest tier_origin (most authoritative refresh) is first; keep first
            combined = combined.sort_values(["app_id", "tier_origin"])
            combined = combined.drop_duplicates(subset="app_id", keep="first")

    return combined.reset_index(drop=True)


def write_meta(out_dir: Path, tier_dirs: list[tuple[str, Path]], row_counts: dict):
    meta = {
        "merged_at": datetime.utcnow().isoformat() + "Z",
        "tiers_included": [t for t, _ in tier_dirs],
        "tiers_missing": [t for t in TIER_LABELS if t not in {td[0] for td in tier_dirs} and t != "all"],
        "row_counts": row_counts,
        "note": "Per-tier app_id collisions resolved by lowest-numbered tier_origin (most authoritative refresh).",
    }
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data_v2", help="Root data directory containing tier_N/ subdirs")
    ap.add_argument("--out", default="merged", help="Output subdirectory name under --data-dir")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data dir not found: {data_dir}")

    tier_dirs = find_tier_dirs(data_dir)
    if not tier_dirs:
        raise SystemExit(f"No tier_N/ subdirectories found under {data_dir}")

    print(f"Found {len(tier_dirs)} tier(s): {[t for t, _ in tier_dirs]}")

    out_dir = data_dir / args.out
    out_dir.mkdir(exist_ok=True, parents=True)

    row_counts = {}
    for filename in CSV_NAMES:
        print(f"\nMerging {filename}:")
        merged = merge_one_filename(filename, tier_dirs)
        if merged.empty:
            print(f"  -> no data, skipping write")
            continue
        out_path = out_dir / filename
        merged.to_csv(out_path, index=False)
        row_counts[filename] = len(merged)
        print(f"  -> wrote {out_path} ({len(merged):,} rows)")

    write_meta(out_dir, tier_dirs, row_counts)
    print(f"\n✓ Merge complete: {out_dir}")
    print(f"  Tiers included: {[t for t, _ in tier_dirs]}")
    print(f"  Total rows by file:")
    for f, n in row_counts.items():
        print(f"    {f}: {n:,}")


if __name__ == "__main__":
    main()
