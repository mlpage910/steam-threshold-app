"""Findings and Methodology tab content for the Steam Threshold Calibration app.

Organized as nested sub-tabs. Every chart has a plain-English write-up next to it
so a reader without statistics background can follow the reasoning.
"""
from __future__ import annotations
import streamlit as st
from pathlib import Path

FIG_DIR = Path(__file__).parent / "figures"


def show(name: str, caption: str = "", width: int | None = None):
    """Display a figure if present, otherwise show a placeholder."""
    path = FIG_DIR / name
    if path.exists():
        st.image(str(path), caption=caption, use_container_width=(width is None))
    else:
        st.info(f"_(figure not found: {name})_")


# =====================================================================
# FINDINGS TAB
# =====================================================================
def render_findings_tab(interactive_normality_fn=None):
    """Render the Findings tab.

    interactive_normality_fn — optional callable that draws the live
    normality-check UI inside its own sub-tab. Keeps the interactive
    widget close to the static results.
    """
    st.subheader("Findings")
    st.markdown(
        "The findings below come from a multi-month study of the Steam catalog "
        "(140,082 titles scraped through 2024-10-28). The investigation worked "
        "in layers: clean the data, exclude structurally different populations, "
        "separate active developers into two cohorts, then carve each cohort "
        "into bands by their average per-game owners and look for distinct "
        "behavior patterns."
    )

    tabs_labels = [
        "Brief",
        "Study setup",
        "Normality results",
        "Owners as the anchor",
        "Two cohorts",
        "Cohort 1 bands",
        "Cohort 2 bands",
        "Genre + tag patterns",
        "Follow-up segments",
    ]
    if interactive_normality_fn is not None:
        tabs_labels.append("Run your own normality check")

    all_tabs = st.tabs(tabs_labels)
    (sub_brief, sub_setup, sub_norm, sub_owners, sub_cohorts,
     sub_c1_bands, sub_c2_bands, sub_genre_tag, sub_followup) = all_tabs[:9]
    sub_interactive = all_tabs[9] if interactive_normality_fn is not None else None

    # --------- Brief ---------
    with sub_brief:
        st.markdown("### Findings brief")
        st.markdown("""
**The short version.** This study set out to answer one practical question: *what
filter combination makes the Steam marketplace clean enough to study discovery
and traction patterns?* The answer turned out to be richer than a single
threshold — there are two genuinely different active-developer populations on
Steam, and they behave like different markets even though they sit on the same
storefront.

**Key findings:**

1. **There are two real active-developer populations, separated at 50K average
   owners per game.** Below that line, developer catalogs show a "long upper
   tail" distribution — most titles register zero adoption and a handful break
   out. Above that line, the shape reverses — most titles cluster near a ceiling
   with a few stragglers below. These are not the same curve at different
   scales; they are different operating regimes.

2. **The most populous group across the entire dataset is the zero band.**
   Cohort 1 has 3,587 developers (60.7%) whose entire multi-game catalog reads
   zero owners on Steam Spy. This is more than half of all active multi-release
   developers. It is the dominant population and deserves separate study
   (flagged as a follow-up segment).

3. **The "up-and-coming" stage label is misleading without owner-band
   qualification.** 79% of Cohort 1 up-and-coming developers sit in the zero
   band — they are "new" but show no adoption signal at all. A credible
   up-and-coming watchlist requires at least one game to register on Steam Spy.

4. **The 50K threshold is defensible analytically.** The per-title owners
   distribution flips skew direction (positive below 50K, negative above 50K),
   the median title flips from zero owners to a non-zero bucket at the same
   boundary, and the genre composition shifts (Indie label dominates below,
   loses ground above).

5. **Tag clusters identify clean audience-size targets within Cohort 2.** At
   75K–100K owners, party games and niche vehicle sims cluster tightly. At
   100K–125K, tools/builders/educational content dominates. At 125K–150K,
   the roguelike family converges. These bands are narrow enough to serve
   as benchmarks for a new release of a given type.

6. **Reviews are not the adoption anchor.** Review counts are heavily shaped
   by genre culture and willingness-to-review. Steam Spy owner ranges are
   used as the primary adoption signal; reviews enter as a secondary response
   variable to confirm that band ordering is real (review medians climb
   monotonically across owner bands, which validates the banding).

7. **The 50K boundary is not a smooth gradient.** Developers cross into a
   qualitatively different operating regime at AA+ — different distribution
   shape, different genre mix, different tag profile. This is what makes the
   50K threshold a real analytical boundary rather than an arbitrary cut.

**What this enables.** A researcher or analyst can now (a) confidently exclude
the structurally noisy population (demos, free-to-play, non-English, delisted),
(b) study each active cohort separately rather than averaging across two
different regimes, and (c) use the band structure to find audience-size
benchmarks for new releases by genre and tag. The Streamlit app exposes the
filter knobs that produced these findings so anyone can re-run the analysis
on a future Steam scrape and check for replication.
        """)

    # --------- Study setup ---------
    with sub_setup:
        st.markdown("### How the study is set up")
        st.markdown("""
**The dataset.** 140,082 Steam titles scraped through October 28, 2024. Each
row carries a release date, developer, publisher, price, genre and tag lists,
and a Steam Spy "owners range" which is a coarse audience-size estimate
bucketed into 14 fixed bands from "0–20K" up to "200M–500M."

**Three layers of filtering, kept strictly separate.**

1. **Data hygiene.** Drop rows with missing or invalid fields. These are not
   judgment calls — a row with no release date or no owners band cannot be
   analyzed, period. ~140K → ~86K rows survive.

2. **Structural exclusions.** Drop populations that play by different rules
   and would contaminate a paid-game / English-market analysis: demos,
   free-to-play, non-English-language, delisted titles. ~86K → ~64K rows.

3. **Analytical thresholds.** Tunable sliders in the sidebar for testing
   hypotheses (minimum owners band, minimum concurrent users, price band,
   developer output, release-age window). These are the actual research
   object — defaults are off so the underlying analysis population is visible
   before any cuts are applied.

**Why three layers and not one?** Mixing hygiene with analytical decisions
poisons replication. If a later scrape is used to confirm findings, the
hygiene and structural layers stay identical; only the analytical sliders
change to test whether the same patterns appear. This keeps the methodology
portable to future Steam scrapes and to other platforms (Kindle, Itch, etc.)
where only the data loader changes.

**Adoption anchor.** Steam Spy's owners range is the primary adoption signal —
a player actually owns the title, which is a revealed-acquisition signal.
Reviews enter as a secondary response variable; they are heavily shaped by
genre culture (RPG players review; horror players don't) and willingness to
review, which makes them unreliable as a standalone adoption metric.
        """)

    # --------- Normality results ---------
    with sub_norm:
        st.markdown("### Normality check on the response distributions")
        st.markdown("""
A standard goal in calibration work is to find a filter combination whose
response distribution (reviews, price, release age, etc.) is "well-behaved" —
ideally close to a normal bell curve. A normal distribution lets ordinary
statistics (means, t-tests, confidence intervals) work correctly, and it
indicates the filter has separated a coherent population from a contaminated one.

**Tests used.**
- **Shapiro–Wilk test** — direct check for normality, most powerful for small-
  to medium-sized samples. P-value above 0.05 means "we can't reject normal."
- **D'Agostino K² test** — combines skew and kurtosis checks, works better on
  large samples. Same p-value interpretation.
- **Q–Q plot** — visual check. If the data points hug the diagonal reference
  line, the distribution is close to normal.

**Findings A and B (game-level normality):**

After applying hygiene + structural filters and using `total_reviews` (log10
transformed) as the response variable, Shapiro–Wilk gives p ≈ 0.18 and
D'Agostino K² gives p ≈ 0.42 — both comfortably above 0.05. The Q–Q plot
hugs the reference line through the bulk of the distribution with mild
deviation in the upper tail (the breakout titles).

In plain English: **once you remove the demos, free-to-play, non-English, and
delisted titles, what remains is a well-behaved log-normal population of
paid English-market Steam games.** This is the "Internal Consistency Rule" —
the dataset is self-consistent once the structural noise is gone.

**Findings C and D (developer-level normality):**

When developers are aggregated by their average per-game owners (rather than
title-by-title), two additional clean populations emerge: the broad AAA cluster
(avg owners above 200K) and the AA+ established benchmark (avg between 50K and
200K). Both pass the normality tests on log scale with p > 0.10.

**How to use the Findings tab below in the app:** Pick a response variable,
apply log transform for skewed counts (reviews, price), and watch the p-values
update as you change the sidebar filters. A non-significant p (> 0.05) plus a
Q–Q plot that hugs the reference line means the current filter combination is
a candidate finding — record the filter set.
        """)

    # --------- Owners as the anchor ---------
    with sub_owners:
        st.markdown("### Why owners — not reviews — is the adoption anchor")

        cols = st.columns(2)
        with cols[0]:
            show("owners_compare.png",
                 "Survival curves at successive owners-band cutoffs.")
        with cols[1]:
            show("owners_ge_reviews.png",
                 "Owners-anchored cohort vs. review-anchored cohort.")

        st.markdown("""
**The problem with reviews as an adoption anchor:**
- Review willingness varies dramatically by genre (strategy and RPG players
  review much more than action and casual players).
- Review counts are inflated by review bombs (politically motivated mass
  reviews) and deflated by free-key giveaways that suppress reviewers.
- Many genuinely-owned titles have zero reviews because players don't review
  what they only briefly tried.

**The owners-range advantage:** Steam Spy's bucketed owners count is derived
from sampling actual library data — it's a revealed acquisition signal, not a
willingness-to-comment signal.
        """)

        st.markdown("---")
        st.markdown("**Joint filter: owners ≥ reviews**")
        show("joint_filter.png",
             "What happens when both filters are applied together.")
        st.markdown("""
**Plain reading:** if a developer has more reviews than owners on a title,
that's a sign of artificial inflation. Conversely, titles with many owners
and few reviews are common and legitimate. Filtering to "owners ≥ reviews"
keeps the honest dataset and drops the suspicious one.
        """)

        st.markdown("---")
        st.markdown("**Titles with zero reviews but non-zero owners**")
        show("zero_rev_some_own.png",
             "These titles are NOT noise — they're owned but un-reviewed.")
        st.markdown("""
This chart shows a substantial population of titles with zero reviews but
positive owner bands. If reviews were used as the adoption anchor, these
titles would be dropped — but they have evidence of actual ownership. This
is the strongest argument for using owners rather than reviews to filter.
        """)

    # --------- Two cohorts ---------
    with sub_cohorts:
        st.markdown("### Two active-developer cohorts, separated at 50K")

        st.markdown("""
After structural filtering, active multi-release developers split cleanly
into two cohorts at the 50K average-owners-per-game line.
        """)

        cols = st.columns(2)
        with cols[0]:
            show("non_aaa_active.png",
                 "Cohort 1: non-AAA, multi-release, non-dormant")
        with cols[1]:
            show("aa_plus_active.png",
                 "Cohort 2: AA+ (excl Broad AAA), multi-release, non-dormant")

        st.markdown("""
**Definitions:**
- **Cohort 1** — developers whose average owners per game is below 50K. The
  large body of active multi-release Steam developers. 5,911 developers,
  24,801 qualifying titles after structural filtering (no demos, no Early
  Access used in chart data).
- **Cohort 2** — developers whose average owners per game is between 50K
  and the Broad AAA boundary (~1M). The active "AA+" middle. 924 developers,
  3,065 qualifying titles.

**Why "non-dormant"?** A developer is considered active if they have released
at least one title in the last 3 years (relative to the 2024-10-28 scrape
cutoff). Dormant developers are excluded because their data describes a
past market regime, not the current one.

**Why "multi-release"?** A single-release developer cannot be characterized
across a body of work. The two cohorts are about *developer behavior across
multiple titles*, which requires a multi-game catalog.

**Why use the looser cohort for stage determination?** When deciding whether
a developer is dormant, we allow Early Access (Steam Early Access — not
Electronic Arts the publisher) and demos to count as "activity." But all
title-level chart data uses the strict structural cohort with no EA, no
demos — those are different populations with different release rhythms.
        """)

        st.markdown("---")
        show("aaa_tiers.png",
             "Broad AAA tier composition (out of analytical scope but shown for completeness).")
        show("tier_profile.png",
             "Age and price profile across all tiers.")

    # --------- Cohort 1 bands ---------
    with sub_c1_bands:
        st.markdown("### Cohort 1 carved into 5K bands")

        st.markdown("""
Cohort 1 (the 5,911 developers below 50K average owners per game) is carved
into bands 5K-owners wide:
- **C1-Z** — exactly zero average owners
- **C1-01** through **C1-10** — bands at 0–5K, 5K–10K, ..., 45K–<50K

The Steam Spy data is bucketed (14 fixed values from 0 to 200M), so 5K bands
are the finest resolution that still produces meaningful groups.
        """)

        show("cohort1_5k_bands_overview.png",
             "Developer counts per Cohort 1 band, with stage mix.")

        st.markdown("""
**Read the top panel:** dev count per band. C1-Z dominates with 3,587
developers — over 60% of the entire cohort. C1-02 (5K–10K) is the second-
biggest band at 967 developers. Everything else is thin.

**Read the bottom panel:** stage mix within each band. Green is up-and-coming,
blue is mid-career active, gray is "mid zone" (between active and dormant),
red is established active. Notice how up-and-coming dominates the zero band
and tapers as the band rises — by C1-10, established active is the largest
slice. **This is the phase transition: developers ascend through bands as
they accumulate career time AND adoption signal together.**
        """)

        cols = st.columns(2)
        with cols[0]:
            show("cohort1_5k_bands_ecdf.png",
                 "Per-title owners ECDF curves across all bands.")
        with cols[1]:
            show("cohort1_5k_bands_shape.png",
                 "Distribution shape (skew + kurtosis) across bands.")

        st.markdown("""
**ECDF reading (left):** each curve shows the cumulative share of a band's
titles at each owners level. Bands with bigger gaps between zero and the
first jump have more zero-owner titles; bands whose curves rise sharply
above zero have titles with adoption.

**Shape reading (right):** all Cohort 1 bands have positive skew on log10
owners — meaning the long tail extends upward (a few breakout titles above
a near-zero mode). This is the opposite shape of Cohort 2.

**Phase transition finding (E–J):** between C1-03 and C1-04 (the 15K boundary),
the median title flips from zero to a non-zero owners bucket. This is the
empirical phase transition within Cohort 1 — below this point, the typical
title in a developer's catalog reads zero; above this point, the typical
title shows adoption.
        """)

    # --------- Cohort 2 bands ---------
    with sub_c2_bands:
        st.markdown("### Cohort 2 carved into 25K bands")

        st.markdown("""
Cohort 2 (the 924 developers between 50K and 1M average owners per game) is
carved into bands 25K-owners wide below 200K, then bucket-aligned above:

- **C2-A1** [50K–75K)  — AA+ near-floor
- **C2-A2** [75K–100K)
- **C2-A3** [100K–125K)
- **C2-A4** [125K–150K)
- **C2-A5** [150K–175K)
- **C2-A6** [175K–200K)
- **C2-A7** [200K–300K)
- **C2-A8** [300K–500K)
- **C2-A9** [500K–1M)
- **C2-A10** [1M+) — overflow

**Why 25K bands and not 10K?** An earlier 10K-wide sweep produced artifact
clusters — developers with only 2 games can only land on certain arithmetic
averages of bucket floors (50K, 75K, 100K, 150K). The 10K bands captured
those gravity wells as distinct clusters when they're actually arithmetic
collisions. 25K bands are wide enough to merge collisions into real groups
while still resolving meaningful structure.
        """)

        show("cohort2_25k_bands_overview.png",
             "Developer counts and stage mix across Cohort 2 bands.")

        st.markdown("""
**Plain reading:** the AA+ near-floor band C2-A1 holds 35% of Cohort 2 (325
developers). More than a third of "active AA+" developers barely cleared the
threshold that defined them. The distribution then decays cleanly: 107, 155,
45, 38, 10, 87, 51, 63, 43. No artifact spikes.

**Stage mix (bottom panel):** mid-career active (blue) and mid zone (gray)
dominate every band, accounting for 70–85% of every band's developers.
Up-and-coming is concentrated in the lowest band (C2-A1) and rare elsewhere —
**young developers who reach AA+ almost always land just above the floor.**
        """)

        cols = st.columns(2)
        with cols[0]:
            show("cohort2_25k_bands_ecdf.png",
                 "Per-title owners ECDF across Cohort 2 bands.")
        with cols[1]:
            show("cohort2_25k_bands_shape.png",
                 "Distribution shape across Cohort 2 bands.")

        st.markdown("""
**Mirror image of Cohort 1.** Every Cohort 2 band has *negative* skew on
log10 owners (Cohort 1 had positive skew). The mode sits near the band
ceiling and the tail extends downward toward zero.

**Per-title zero-rate decays sharply:** 34.4% (C2-A1) → 17.8% → 18.0% →
12.0% → ... → 4.6% (C2-A10). Above the C2-A2 band the typical title clears
the AA+ floor.

**Review medians climb monotonically:** 255 → 678 → 1,078 → 1,811 → ... →
26,219 reviews per title across the bands. **This is what confirms the
banding is real** — reviews are exact integers (not bucketed), so they have
real resolution, and they agree with the owner-band ordering.
        """)

    # --------- Genre + tag patterns ---------
    with sub_genre_tag:
        st.markdown("### Genre and tag patterns by band")

        st.markdown("""
The next layer of investigation asks: within each band, which genres and
which tags concentrate? "Over-indexed" means a tag appears more often in
a specific band than its overall cohort prevalence would predict. A lift
of 3× means a tag is 3 times as common in that band as in the cohort
average.
        """)

        st.markdown("#### Cohort 1 — genre by band")
        show("cohort1_genre_x_band_heatmap.png",
             "Top: raw title counts. Bottom: % of each genre's titles in each band.")
        st.markdown("""
- 86% of Cohort 1 titles ship as Indie — the Indie label dominates the entire
  below-50K cohort.
- Casual is back-loaded: a larger share of Casual titles concentrates in the
  zero band than other genres.
- RPG and Strategy share climbs as the band rises — these genres carry more
  per-title adoption than Casual.
        """)

        st.markdown("#### Cohort 1 — tag by band")
        show("cohort1_tag_x_band_heatmap.png",
             "Top 25 tags by total count, distributed across Cohort 1 bands.")
        st.markdown("""
**Key tag findings:**
- **Adult content** (NSFW, Hentai, Nudity, Sexual Content) over-indexes
  heavily in the zero band — these titles do not move on Steam.
- **Great Soundtrack** tag over-indexes 6.43× at the AA+ doorstep (C1-10).
  This is the strongest tag-to-band lift in the entire Cohort 1 analysis.
- **Turn-Based** is the only tag that over-indexes at the floor of *both*
  Cohort 1 and Cohort 2 — niche-with-fans regardless of audience scale.
- **Visual Novel** appears only in tags (not genres) and has an 83% zero-rate
  in Cohort 1 — extreme zero-wall behavior.
        """)

        st.markdown("#### Cohort 1 — per-genre sales curves")
        show("cohort1_genre_sales_overlay.png",
             "Sales curves for each primary genre, overlaid for comparison.")
        show("cohort1_genre_sales_curves.png",
             "Sales curves for each primary genre, displayed individually.")

        st.markdown("---")
        st.markdown("#### Cohort 2 — genre by band")
        show("cohort2_genre_x_band_heatmap.png",
             "Top: raw counts. Bottom: row-normalized %.")
        st.markdown("""
- Action share climbs from 35% (C2-A1) to 67% (C2-A10) — at million-owner
  scale the catalog is decisively Action-led.
- Indie share inverts: 25% (C2-A1) to 5% (C2-A10) — these studios are no
  longer presenting as Indie.
- Massively Multiplayer over-indexes 3.1× at the C2-A10 [1M+) band and again
  at C2-A1 — bimodal distribution. MMO entries either disappear at the floor
  or break out into 1M+.
        """)

        st.markdown("#### Cohort 2 — tag by band")
        show("cohort2_tag_x_band_heatmap.png",
             "Top 25 tags by total, distributed across Cohort 2 bands.")
        st.markdown("""
**The cleanest tag-cluster findings of the entire study:**

- **C2-A2 [75K–100K) — Vehicle + Party Game cluster.** Motocross (5.66× lift),
  Motorbike (5.18×), Trivia (5.17×), Bikes (4.86×), Party (4.11×), Party Game
  (3.76×). This is a tight audience-size band for niche-vehicle sims and
  party-style games.

- **C2-A3 [100K–125K) — Tools, builders, education cluster.** Software (4.33×),
  Trading Card Game (4.10×), Game Development (3.71×), Design & Illustration
  (2.57×), Capitalism (2.16×), Education (2.01×).

- **C2-A4 [125K–150K) — Roguelike family + Shoot 'em Up cluster.** Shoot 'Em
  Up (3.07×), Side Scroller (2.72×), Post-apocalyptic (2.50×), Roguelite
  (2.16×), Action Roguelike (1.93×), Roguelike (1.91×).

- **C2-A5 [150K–175K) — Strategy and base-building cluster.** Historical
  (3.03×), Strategy RPG (2.95×), Base Building (2.70×), Crafting (2.35×),
  Resource Management (1.99×).

- **C2-A8 through C2-A10 — Open World + Co-op cluster.** Open World, Online
  Co-Op, Multiplayer, Moddable lift increases monotonically with band. The
  500K+ tiers are about persistent-world social play.

**Why this matters:** these clusters give a benchmark audience size for a
new title of a known type. A new party game has C2-A2 (~75K–100K) as a
realistic target; a new roguelike has C2-A4 (~125K–150K).
        """)

        st.markdown("#### Cohort 2 — per-genre sales curves")
        show("cohort2_genre_sales_overlay.png",
             "Sales curves by primary genre, overlaid.")
        show("cohort2_genre_sales_curves.png",
             "Sales curves by primary genre, displayed individually.")

        st.markdown("---")
        st.markdown("#### Visual Novel — a tag that crosses cohorts")
        show("visual_novel_cohorts.png",
             "Visual Novel-tagged titles in both cohorts.")
        st.markdown("""
83% of Cohort 1 Visual Novel titles read zero owners. But the 124 Visual
Novel developers who reach AA+ cluster as Adventure-primary in Cohort 2.
**Few break out — but those that do, break out cleanly.**
        """)

    # --------- Follow-up segments ---------
    with sub_followup:
        st.markdown("### Sub-segments flagged for follow-up study")
        st.markdown("""
The current study has identified two sub-segments worth investigating
separately rather than as part of the main cohort analysis. They are large
enough to overwhelm general findings and have distinctive enough behavior
to deserve their own treatment.

**Segment 1 — C1-Z (the zero band)**
- 3,587 developers, **52.5% of the entire 6,835-developer combined cohort**.
- Multi-release developers whose entire catalog reads zero on Steam Spy.
- Heavily concentrated in up-and-coming stage (79% of all up-and-coming
  Cohort 1 devs are here).
- Adult-content tags over-index here significantly.
- Needs its own analysis: by stage, by latest_release recency, by genre
  and tag concentration, and by career_span. The question to answer: what
  distinguishes "active but invisible" from "newly active without signal yet"?

**Segment 2 — C2-A1 (AA+ near-floor)**
- 325 developers, 35% of Cohort 2.
- Active developers with average owners per game between 50K and 75K — the
  population that barely cleared the threshold defining them as AA+.
- Highest zero-rate inside Cohort 2 (34.4% of titles still read zero).
- Hentai tag over-indexes here (only adult-content lift in Cohort 2).
- Needs its own analysis: how many are at *exactly* 50K (the bucket floor)
  vs distributed across 50K–75K, and what differentiates the floor-stuck
  from the climbing.

**Rename in progress (pending decision):** the current "up-and-coming"
stage label is misleading because 79% of those developers sit in C1-Z.
A proposed split would create:
- `new_unproven` — career < 3 years AND avg owners = 0
- `emerging` — career < 3 years AND avg owners > 0

This makes the watchlist segment (emerging) credible without the zero-band
mass washing it out.
        """)

    # --------- Interactive normality check (optional, last sub-tab) ---------
    if sub_interactive is not None:
        with sub_interactive:
            interactive_normality_fn()


# =====================================================================
# METHODOLOGY TAB
# =====================================================================
def render_methodology_tab(df, hyg, struct):
    import pandas as pd
    from filters import hygiene_mask, structural_mask

    st.subheader("Methodology")
    st.markdown(
        "This is a **calibration workbench**, not a classifier. The goal is to "
        "find filter thresholds that make Steam legible enough to study "
        "discovery and traction — not to label individual titles."
    )

    (sub_arch, sub_anchor, sub_english, sub_us, sub_cohorts,
     sub_bands, sub_replication, sub_live) = st.tabs([
        "Architecture",
        "Adoption anchor",
        "English filter",
        "US-availability proxy",
        "Cohort definitions",
        "Band design",
        "Replication plan",
        "Live exclusion summary",
    ])

    # --------- Architecture ---------
    with sub_arch:
        st.markdown("### Three-layer filter architecture")
        st.markdown("""
The filtering logic is split into three layers that are kept strictly separate
in code and in the sidebar.

**Layer 1 — Data hygiene.** Drop rows with missing or invalid required fields:
no release date, no Steam Spy owners band, missing developer, missing
publisher. These are not analytical decisions — a row with no owners band
cannot be analyzed regardless of methodology.

**Layer 2 — Structural exclusions.** Drop populations that play by different
rules and would contaminate a paid-English-market analysis: demos, free-to-play,
non-English titles, delisted titles, Steam Early Access (Steam's "EA," not
the publisher Electronic Arts). The set surviving layers 1+2 is the
**underlying analysis population** that everything downstream reads from.

**Layer 3 — Analytical thresholds.** Tunable sliders in the sidebar for
testing hypotheses (minimum owners band, minimum concurrent users, price
band, developer output, release-age window, optional review thresholds).
Defaults are all off so the underlying population is visible before any
analytical cuts are applied.

**Why three layers and not one?** Mixing hygiene with analytical decisions
poisons replication. If a future Steam scrape is used to confirm findings,
the hygiene and structural layers stay identical; only the analytical
sliders move to test for replication. This keeps the methodology portable
to future scrapes and to other platforms.
        """)

    # --------- Adoption anchor ---------
    with sub_anchor:
        st.markdown("### Why owners — not reviews — is the adoption anchor")
        st.markdown("""
Reviews are not the adoption anchor in this study. Steam Spy's `owners_range`
is the primary signal because:

- It reflects **revealed acquisition** — a player actually owns the title.
- It is **less culture-dependent** than reviews (RPG and strategy players
  review prolifically; horror and casual players rarely do).
- It is **less manipulable** than reviews (review bombs and key-giveaway
  suppression both distort review counts but not library counts).

**Owners is treated as ordinal** across 14 fixed Steam Spy bands rather than
as a numeric variable. The bands are:

`0–20K, 20K–50K, 50K–100K, 100K–200K, 200K–500K, 500K–1M, 1M–2M, 2M–5M,
5M–10M, 10M–20M, 20M–50M, 50M–100M, 100M–200M, 200M–500M`.

Sweeping through these as cutoffs (rather than committing to one number)
reveals natural elbows in the data.

**Reviews enter the analysis as response variables** in the Findings tab,
kept logically distinct from filtering logic to avoid circularity. Review
medians climbing monotonically across owners bands is what validates the
banding is real — review counts are exact integers and have real resolution.
        """)

    # --------- English filter ---------
    with sub_english:
        st.markdown("### English-language requirement")
        st.markdown("""
**Operationalization:** raw `languages` field contains the string "English"
(case-insensitive). The flag is computed once in the loader as `has_english`.

**Coverage:** approximately 91% of the dataset qualifies (~127K of 140K
titles). Drops include foreign-only releases (Chinese-only, Russian-only,
Korean-only indie titles) which follow different discovery dynamics in the
English-speaking market.

**Why not currency = USD?** See the next sub-tab — it's not usable as a
direct US-availability filter.
        """)

    # --------- US-availability proxy ---------
    with sub_us:
        st.markdown("### US-availability proxy")
        st.markdown("""
**The problem.** The source scrape was made from a non-US IP address. Only
482 of 140,082 rows carry USD pricing directly; the rest are in EUR, empty,
or other regional currencies. So `currency = USD` cannot be used as a US-
availability filter.

**The proxy used.** Presence of a parseable currency code in the
`price_overview` field. This indicates the title has an active, priced
Steam store listing somewhere — and in practice almost always including
the US store. Approximately 76K of 140K rows qualify.

**Excluded rows.** Predominantly delisted titles, free-to-play titles with
incomplete metadata, and region-restricted listings.

**Honest limitation.** A US-side rescrape would tighten this filter
significantly. Out of scope for v1; flagged in the README as a known
limitation. The proxy is *conservative* — it errs on the side of
inclusion, so any title showing real listing data passes through.
        """)

    # --------- Cohort definitions ---------
    with sub_cohorts:
        st.markdown("### Two cohorts, kept separate throughout")
        st.markdown("""
**Cohort 1 — Non-AAA, multi-release, non-dormant**
- Average owners per game **< 50K**.
- Career has at least 2 released titles.
- Most recent release within 3 years of the scrape (2024-10-28).
- **5,911 developers, 24,801 qualifying titles.**

**Cohort 2 — AA+, multi-release, non-dormant, excluding Broad AAA**
- Average owners per game **between 50K and the Broad AAA boundary** (~1M).
- Career has at least 2 released titles.
- Most recent release within 3 years of the scrape.
- **924 developers, 3,065 qualifying titles.**

**Broad AAA developers** (avg owners ≥ 1M) are excluded from Cohort 2 to
keep the analysis focused on the working middle. Broad AAA is a separate
sub-segment with its own dynamics.

**Why "non-dormant"?** A dormant developer's data describes a past market
regime, not the current one.

**Why "multi-release"?** Single-release developers cannot be characterized
across a body of work, which is what cohort analysis requires.

**Dormancy is determined with a looser cohort.** Early Access titles and
demos count as "activity" for dormancy purposes only. All chart data uses
the strict structural cohort (no EA, no demos) — those are different
populations with different release rhythms.

**A note on "EA" terminology.** Throughout this project "EA" refers to
**Steam Early Access** (Steam's category for in-development titles being
sold). It does **not** refer to Electronic Arts the publisher. The
analytical exclusion is of titles with `early_access = 1` on Steam.
        """)

    # --------- Band design ---------
    with sub_bands:
        st.markdown("### Band design and resolution limits")
        st.markdown("""
**Cohort 1 — 5K bands.**
- C1-Z (exactly 0) plus 10 bands at 0–5K, 5K–10K, ..., 45K–<50K.
- 5K is the finest practical resolution for Cohort 1 because Steam Spy
  bucket-floor averages of 2- and 3-game catalogs produce coarse arithmetic
  values; narrower bands would just split arithmetic collisions.

**Cohort 2 — 25K bands below 200K, then bucket-aligned above.**
- C2-A1 through C2-A6 at 25K-wide bands covering 50K–200K.
- C2-A7 [200K, 300K), C2-A8 [300K, 500K), C2-A9 [500K, 1M), C2-A10 [1M+).
- An earlier 10K-wide sweep produced artifact clusters because developers
  with only 2 games can only land on certain arithmetic averages of bucket
  floors (50K, 75K, 100K, 150K). 25K bands merge those gravity wells.
- Above 200K the available data thins quickly and the Steam Spy bucket
  boundaries themselves become natural breakpoints (200K, 500K, 1M).

**Honest accounting:** Steam Spy owners ranges are 14 fixed bucketed values,
not exact counts. The `owners_lower` field stores each title's bucket floor.
A developer's `avg_owners_per_game` is the mean of their titles' bucket
floors. This means the achievable averages are constrained by which buckets
the developer's titles occupy. The banding respects this resolution limit.
        """)

    # --------- Replication plan ---------
    with sub_replication:
        st.markdown("### Replication and portability plan")
        st.markdown("""
**When a second Steam scrape arrives:**

1. The same hygiene + structural filters apply (Layer 1 and Layer 2 are
   data-defined and shouldn't move).
2. The same analytical thresholds are tested for replication.
3. **Kolmogorov–Smirnov test** on the response distributions checks whether
   the new scrape produces the same shape under the same filters.
4. **Rank correlation** on overlapping titles checks whether the relative
   ordering of titles is preserved across scrapes.

**Cross-platform portability.** The three-layer architecture is designed
to transfer to other digital storefronts:

- **Kindle / self-publishing** — the loader changes (Kindle metadata is
  different) and the structural-exclusion list changes (sample-pages
  instead of demos, KDP-Select-exclusive instead of region-restricted),
  but the architecture is identical. The adoption anchor on Kindle becomes
  sales-rank decay rather than owner buckets.
- **Itch.io** — same architecture; structural exclusions adapt to itch's
  category system; adoption anchor becomes downloads + ratings.
- **Other platforms** — the abstraction is "three-layer filter set + one
  adoption anchor + reviews-as-response." Anything that fits this shape
  can be analyzed with the same code with a new loader and structural list.
        """)

    # --------- Live exclusion summary ---------
    with sub_live:
        st.markdown("### Live exclusion summary (current filter state)")
        st.caption(
            "How many rows the current filter combination drops, broken "
            "down by the specific reason. Numbers reflect every sidebar "
            "toggle as of right now."
        )

        excl_rows = []
        n_total = len(df)

        if hyg.get("require_release_date"):
            excl_rows.append(("Hygiene", "Missing/invalid release_date",
                              int(df["release_date"].isna().sum())))
        if hyg.get("require_owners_band"):
            excl_rows.append(("Hygiene", "Missing SteamSpy owners_range",
                              int(df["owners_range"].isna().sum())))
        if hyg.get("require_developer"):
            excl_rows.append(("Hygiene", "Missing developer",
                              int(df["developer"].isna().sum() +
                                  (df["developer"].fillna("").astype(str).str.strip() == "").sum()
                                  - df["developer"].isna().sum())))
        if hyg.get("require_publisher"):
            excl_rows.append(("Hygiene", "Missing publisher",
                              int(df["publisher"].isna().sum())))
        if hyg.get("paid_requires_price"):
            excl_rows.append(("Hygiene", "Paid title with no price_usd",
                              int(((df["is_free"] == 0) & df["price_usd"].isna()).sum())))
        if hyg.get("drop_future_release"):
            excl_rows.append(("Hygiene", "Release date after scrape (2024-10-28)",
                              int((df["release_date"] > pd.Timestamp("2024-10-28")).sum())))

        if struct.get("exclude_demos"):
            excl_rows.append(("Structural", "type = 'demo'",
                              int((df["type"] == "demo").sum())))
        if struct.get("exclude_free_to_play"):
            excl_rows.append(("Structural", "is_free = 1",
                              int((df["is_free"] == 1).sum())))
        if struct.get("require_english"):
            excl_rows.append(("Structural", "No English in languages field",
                              int((df["has_english"] == 0).sum())))
        if struct.get("require_us_available"):
            excl_rows.append(("Structural", "No parseable currency in price_overview "
                              "(delisted / region-restricted / no real listing)",
                              int((df["has_store_listing"] == 0).sum())))

        excl_df = pd.DataFrame(excl_rows, columns=["Layer", "Reason", "Rows matching"])
        excl_df["% of raw"] = (excl_df["Rows matching"] / n_total * 100).round(2)
        st.dataframe(excl_df, use_container_width=True, hide_index=True)

        st.markdown(
            "Note: a single row may match more than one reason above, so "
            "the rows in this table do not sum to the total dropped. The "
            "header counters at the top of the page show the actual cascade "
            "after deduplication."
        )

        st.divider()
        st.subheader("Underlying analysis population (post-structural)")
        hs_mask = hygiene_mask(df, hyg) & structural_mask(df, struct)
        base_n = int(hs_mask.sum())
        st.metric("Rows in underlying analysis set", f"{base_n:,}",
                  f"-{n_total - base_n:,} excluded")
        st.caption(
            "This is the population every analytical-tab graph reads from. "
            "Sliders in section 3 of the sidebar tune downward from this "
            "set — they never add rows back."
        )
