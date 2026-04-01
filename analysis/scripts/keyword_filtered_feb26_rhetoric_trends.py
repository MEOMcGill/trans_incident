"""
Visualize rhetoric category time trends and top authors from
Haiku-classified daily top trans posts.

Input:  analysis/data/feb2026_daily_top_rhetoric.parquet
Output: analysis/figures/keyword_filtered_feb26_rhetoric_trends.png
        analysis/figures/keyword_filtered_feb26_rhetoric_authors.png
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import Counter
import datetime
import numpy as np

DATA = "analysis/data/feb2026_daily_top_rhetoric_ca.parquet"
FIG_TRENDS = "analysis/figures/keyword_filtered_feb26_rhetoric_trends.png"
FIG_TRENDS_LIKES = "analysis/figures/keyword_filtered_feb26_rhetoric_trends_likes.png"
FIG_AUTHORS = "analysis/figures/keyword_filtered_feb26_rhetoric_authors.png"

# Top 6 categories get their own lines; bottom 4 grouped as "Other Anti-Trans"
MAIN_CATS = [
    "ideology_framing",
    "conspiracy",
    "mockery",
    "violence_association",
    "identity_denial",
    "child_protection",
]
OTHER_CATS = [
    "predator_framing",
    "pathologizing",
    "dehumanization",
    "medical_opposition",
]

# All categories (still used for author chart)
TOP_CATS = MAIN_CATS + OTHER_CATS

CAT_LABELS = {
    "ideology_framing": "Ideology Framing",
    "conspiracy": "Conspiracy",
    "mockery": "Mockery",
    "violence_association": "Violence Association",
    "identity_denial": "Identity Denial",
    "child_protection": "Child Protection",
    "predator_framing": "Predator Framing",
    "pathologizing": "Pathologizing",
    "dehumanization": "Dehumanization",
    "medical_opposition": "Medical Opposition",
}

COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12",
    "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#607d8b",
]


def main():
    df = pd.read_parquet(DATA)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["day"] = df["date"].dt.date

    # Explode categories into boolean columns
    for cat in TOP_CATS:
        df[f"cat_{cat}"] = df["haiku_rhetoric_categories"].apply(
            lambda x: cat in list(x) if x is not None and hasattr(x, "__iter__") else False
        )

    # --- Figure 1: Time trends (3-day rolling) ---
    days = sorted(df["day"].unique())

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1]})

    # Plot main categories as individual lines
    for cat, color in zip(MAIN_CATS, COLORS):
        daily = df.groupby("day")[f"cat_{cat}"].sum()
        daily = daily.reindex(days, fill_value=0)
        rolling = daily.rolling(3, center=True, min_periods=1).mean()
        ax1.plot(
            [datetime.datetime.combine(d, datetime.time()) for d in rolling.index],
            rolling.values,
            label=CAT_LABELS[cat],
            color=color,
            linewidth=2,
            alpha=0.85,
        )

    # Plot "Other Anti-Trans" as combined line (predator, pathologizing, dehumanization, medical)
    other_daily = sum(
        df.groupby("day")[f"cat_{cat}"].sum().reindex(days, fill_value=0)
        for cat in OTHER_CATS
    )
    other_rolling = other_daily.rolling(3, center=True, min_periods=1).mean()
    ax1.plot(
        [datetime.datetime.combine(d, datetime.time()) for d in other_rolling.index],
        other_rolling.values,
        label="Other Anti-Trans",
        color="#95a5a6",
        linewidth=2,
        linestyle="--",
        alpha=0.85,
    )

    shooting_date = datetime.datetime(2026, 2, 10)
    ax1.axvline(shooting_date, color="black", linestyle="--", alpha=0.7, linewidth=1.5)
    ax1.annotate("Tumblr Ridge\nshooting", xy=(shooting_date, ax1.get_ylim()[1] * 0.95),
                 fontsize=9, ha="right", va="top",
                 xytext=(-10, -5), textcoords="offset points")

    ax1.set_ylabel("Posts per day (3-day rolling avg)")
    ax1.set_title("Anti-Trans Rhetoric Categories — Top 20 Trans Posts Daily, Feb 2026")
    ax1.legend(loc="upper left", fontsize=8, ncol=2, framealpha=0.9)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax1.grid(axis="y", alpha=0.3)

    # Bottom panel: total anti-trans posts per day
    daily_anti = df.groupby("day")["haiku_contains_anti_trans_rhetoric"].sum()
    daily_anti = daily_anti.reindex(days, fill_value=0)
    daily_total = df.groupby("day").size().reindex(days, fill_value=0)
    ax2.bar(
        [datetime.datetime.combine(d, datetime.time()) for d in days],
        daily_total.values,
        color="#bdc3c7", alpha=0.5, label="All top posts",
    )
    ax2.bar(
        [datetime.datetime.combine(d, datetime.time()) for d in days],
        daily_anti.values,
        color="#e74c3c", alpha=0.7, label="Anti-trans",
    )
    ax2.axvline(shooting_date, color="black", linestyle="--", alpha=0.7, linewidth=1.5)
    ax2.set_ylabel("Posts")
    ax2.set_xlabel("Date")
    ax2.legend(fontsize=8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(FIG_TRENDS, dpi=150, bbox_inches="tight")
    print(f"Saved {FIG_TRENDS}")

    # --- Figure 1b: Time trends by LIKES (3-day rolling) ---
    plt.rcParams.update({"font.size": 13})
    fig, (ax2, ax1) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [1, 3]})

    for cat, color in zip(MAIN_CATS, COLORS):
        # Sum likes for posts that have this category
        daily_likes = df[df[f"cat_{cat}"]].groupby("day")["like_count"].sum()
        daily_likes = daily_likes.reindex(days, fill_value=0)
        rolling = daily_likes.rolling(3, center=True, min_periods=1).mean()
        ax1.plot(
            [datetime.datetime.combine(d, datetime.time()) for d in rolling.index],
            rolling.values,
            label=CAT_LABELS[cat],
            color=color,
            linewidth=2,
            alpha=0.85,
        )

    # Other Anti-Trans combined likes
    other_mask = df[f"cat_{OTHER_CATS[0]}"].copy()
    for cat in OTHER_CATS[1:]:
        other_mask = other_mask | df[f"cat_{cat}"]
    other_daily_likes = df[other_mask].groupby("day")["like_count"].sum()
    other_daily_likes = other_daily_likes.reindex(days, fill_value=0)
    other_rolling = other_daily_likes.rolling(3, center=True, min_periods=1).mean()
    ax1.plot(
        [datetime.datetime.combine(d, datetime.time()) for d in other_rolling.index],
        other_rolling.values,
        label="Other Anti-Trans",
        color="#95a5a6",
        linewidth=2,
        linestyle="--",
        alpha=0.85,
    )

    salon_date = datetime.datetime(2026, 2, 18)
    letter_date = datetime.datetime(2026, 2, 21)

    ax1.axvline(shooting_date, color="black", linestyle="--", alpha=0.7, linewidth=1.5)
    ax1.axvline(salon_date, color="black", linestyle="--", alpha=0.5, linewidth=1)
    ax1.axvline(letter_date, color="black", linestyle="--", alpha=0.5, linewidth=1)
    ax1.annotate("Tumblr Ridge\nshooting", xy=(shooting_date, 60000),
                 fontsize=11, ha="right", va="top",
                 xytext=(-10, -5), textcoords="offset points")
    ax1.annotate("Hair Salon\nFined", xy=(salon_date, ax1.get_ylim()[1] * 0.95),
                 fontsize=11, ha="right", va="top",
                 xytext=(-10, -5), textcoords="offset points")
    ax1.annotate("OpenAI\nLetter", xy=(letter_date, ax1.get_ylim()[1] * 0.95),
                 fontsize=11, ha="right", va="top",
                 xytext=(-10, -5), textcoords="offset points")
    ax1.set_ylabel("Likes per day (3-day rolling avg)")
    fig.suptitle("Negative Rhetoric by Engagement (Likes) — Top 20 Posts Daily about Trans/Queer Topics, Feb 2026", fontsize=15, y=0.99)
    ax1.legend(loc="upper left", fontsize=10, ncol=2, framealpha=0.9)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax1.grid(axis="y", alpha=0.3)

    # Bottom panel: total likes for anti-trans vs all
    anti_mask = df["haiku_contains_anti_trans_rhetoric"] == True
    daily_anti_likes = df[anti_mask].groupby("day")["like_count"].sum().reindex(days, fill_value=0)
    daily_total_likes = df.groupby("day")["like_count"].sum().reindex(days, fill_value=0)
    ax2.bar(
        [datetime.datetime.combine(d, datetime.time()) for d in days],
        daily_total_likes.values,
        color="#bdc3c7", alpha=0.5, label="All top posts",
    )
    ax2.bar(
        [datetime.datetime.combine(d, datetime.time()) for d in days],
        daily_anti_likes.values,
        color="#e74c3c", alpha=0.7, label="Anti-trans",
    )
    ax2.axvline(shooting_date, color="black", linestyle="--", alpha=0.7, linewidth=1.5)
    ax2.axvline(salon_date, color="black", linestyle="--", alpha=0.5, linewidth=1)
    ax2.axvline(letter_date, color="black", linestyle="--", alpha=0.5, linewidth=1)
    ax2.set_ylabel("Likes")
    ax2.set_xlabel("Date")
    ax2.legend(fontsize=10)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(FIG_TRENDS_LIKES, dpi=150, bbox_inches="tight")
    plt.rcParams.update({"font.size": 10})  # reset for subsequent figures
    print(f"Saved {FIG_TRENDS_LIKES}")

    # --- Figure 2: Top authors ---
    anti = df[df["haiku_contains_anti_trans_rhetoric"] == True]

    # Author frequency
    author_counts = anti["seed_SeedName"].value_counts().head(25)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    # Left: top authors by post count
    ax1.barh(
        author_counts.index[::-1],
        author_counts.values[::-1],
        color="#e74c3c", alpha=0.8,
    )
    ax1.set_xlabel("Anti-trans posts in top 20 daily")
    ax1.set_title("Top 25 Authors — Anti-Trans Rhetoric")

    # Right: top authors with their dominant categories
    top_authors = author_counts.head(15).index.tolist()
    author_cat_data = []
    for author in top_authors:
        author_posts = anti[anti["seed_SeedName"] == author]
        cat_counter = Counter()
        for cats in author_posts["haiku_rhetoric_categories"].dropna():
            for c in list(cats):
                if c in TOP_CATS:
                    cat_counter[c] += 1
        for cat in TOP_CATS:
            author_cat_data.append({
                "author": author,
                "category": CAT_LABELS[cat],
                "count": cat_counter.get(cat, 0),
            })

    acd = pd.DataFrame(author_cat_data)
    pivot = acd.pivot(index="author", columns="category", values="count").fillna(0)
    pivot = pivot.loc[top_authors[::-1]]  # reverse for barh

    pivot.plot.barh(stacked=True, ax=ax2, color=COLORS[:len(pivot.columns)], alpha=0.85)
    ax2.set_xlabel("Category mentions")
    ax2.set_title("Top 15 Authors — Rhetoric Profile")
    ax2.legend(fontsize=7, loc="lower right", ncol=2)

    plt.tight_layout()
    plt.savefig(FIG_AUTHORS, dpi=150, bbox_inches="tight")
    print(f"Saved {FIG_AUTHORS}")

    # Print author summary
    print("\n=== TOP 25 AUTHORS (anti-trans posts in daily top 20) ===")
    for author, count in author_counts.items():
        author_posts = anti[anti["seed_SeedName"] == author]
        platforms = author_posts["platform"].unique()
        main_type = author_posts["seed_MainType"].iloc[0]
        cats = Counter()
        for c_list in author_posts["haiku_rhetoric_categories"].dropna():
            for c in list(c_list):
                if c in TOP_CATS:
                    cats[c] += 1
        top3 = ", ".join(c for c, _ in cats.most_common(3))
        print(f"  {author} ({main_type}, {'/'.join(platforms)}): {count} posts — {top3}")


if __name__ == "__main__":
    main()
