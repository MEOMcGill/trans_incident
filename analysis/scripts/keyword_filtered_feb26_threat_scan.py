"""
Scan keyword-filtered posts for explicit threat language targeting
trans/queer people or related to the Tumblr Ridge incident.

Input:  analysis/data/feb2026_incident_trans_union_keywords.parquet
Output: analysis/data/feb2026_threat_scan.parquet
        analysis/figures/keyword_filtered_feb26_threat_scan.png
"""

import re
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = "analysis/data/feb2026_incident_trans_union_keywords.parquet"
OUT_DATA = "analysis/data/feb2026_threat_scan.parquet"
OUT_FIG = "analysis/figures/keyword_filtered_feb26_threat_scan.png"

# --- Threat keyword patterns ---
# Each category is a list of regex patterns (case-insensitive)
THREAT_PATTERNS = {
    "death_threats": [
        r"\bkill\s+(them|all|every|these|those|trans|queer|fag|lgbtq)",
        r"\bshould\s+(be\s+)?kill(ed)?\b",
        r"\bdeserve[sd]?\s+to\s+die\b",
        r"\bput\s+(them|trans|queer)\s+down\b",
        r"\bdeath\s+to\b",
        r"\bexecut(e|ed|ion)\b",
        r"\bhang\s+(them|all|every)\b",
        r"\bline\s+(them|em)\s+up\b.*\b(shoot|shot|wall)\b",
        r"\b(gas|burn)\s+(them|all|every|these|those)\b",
    ],
    "violence_incitement": [
        r"\bshoot\s+(them|all|every|these|those|trans|queer)",
        r"\bbeat\s+(them|the\s+shit|up)\b",
        r"\bbash(ing)?\s+(trans|queer|fag|lgbtq)",
        r"\b(punch|attack|assault)\s+(them|trans|queer|every)",
        r"\bviolence\s+(against|toward|is\s+the\s+answer)",
        r"\bshould\s+(be\s+)?(beaten|shot|attacked|assaulted|hurt)",
        r"\bcurb\s*stomp",
        r"\bbullet\b.*\b(deserve|need|for)\b",
        r"\b(deserve|need)s?\s+a\s+bullet\b",
    ],
    "celebration_of_harm": [
        r"\b(glad|happy|good)\s+(that|they|he|she)\s+(died|dead|killed|shot)",
        r"\bgot\s+what\s+(they|he|she)\s+deserve",
        r"\bone\s+(less|fewer)\b",
        r"\bgood\s+riddance\b",
        r"\bshould\s+happen\s+more\b",
        r"\bwish\s+(it|this)\s+(happened|happens)\s+more\b",
        r"\blol\b.*\b(dead|died|killed|shot)\b",
        r"\bcelebrat(e|ing)\b.*\b(death|dead|killed)\b",
    ],
    "elimination_rhetoric": [
        r"\beradicat(e|ed|ing|ion)\b",
        r"\belminat(e|ed|ing|ion)\b",  # catches "eliminate" typos too
        r"\beliminate\b.*\b(trans|queer|lgbtq|them)\b",
        r"\bwipe\s+(them|trans|out)\b",
        r"\bpurg(e|ed|ing)\b",
        r"\bcleans(e|ed|ing)\b.*\b(trans|queer|lgbtq|society|country)\b",
        r"\bget\s+rid\s+of\b.*\b(trans|queer|lgbtq|them|all)\b",
        r"\bexterminate\b",
        r"\bgenocide\b.*\b(trans|queer|lgbtq)\b",
        r"\btrans\b.*\bgenocide\b",
    ],
    "direct_threats": [
        r"\bi('ll|m\s+going\s+to|m\s+gonna)\s+(kill|shoot|hurt|beat|find|hunt)",
        r"\bwatch\s+(your|ur)\s+back\b",
        r"\bcoming\s+for\s+(you|them|trans|queer)\b",
        r"\byou('re|\s+are)\s+(dead|next)\b",
        r"\btarget\s+on\s+(your|their)\s+back\b",
        r"\bknow\s+where\s+you\s+(live|work)\b",
        r"\bwon'?t\s+be\s+safe\b",
    ],
}


def scan_threats(text, patterns_dict):
    """Return dict of category -> list of matched snippets."""
    if not isinstance(text, str) or not text.strip():
        return {}
    matches = {}
    for category, patterns in patterns_dict.items():
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                matches.setdefault(category, []).append(m.group())
    return matches


def main():
    df = pd.read_parquet(DATA)
    print(f"Loaded {len(df)} posts")

    # Scan
    df["_threat_matches"] = df["text_all"].apply(lambda t: scan_threats(t, THREAT_PATTERNS))
    df["has_threat"] = df["_threat_matches"].apply(lambda m: len(m) > 0)

    # Explode categories
    def get_categories(matches):
        return list(matches.keys()) if matches else []

    df["threat_categories"] = df["_threat_matches"].apply(get_categories)

    # Category flags
    for cat in THREAT_PATTERNS:
        df[f"threat_{cat}"] = df["threat_categories"].apply(lambda cats: cat in cats)

    # Summary
    threats = df[df["has_threat"]]
    print(f"\nPosts with threat language: {len(threats)} / {len(df)} ({100*len(threats)/len(df):.1f}%)")
    print("\nBy category:")
    for cat in THREAT_PATTERNS:
        n = df[f"threat_{cat}"].sum()
        if n > 0:
            print(f"  {cat}: {n}")

    print(f"\nBy platform:")
    print(threats.groupby("platform").size().sort_values(ascending=False).to_string())

    # Print flagged posts
    print("\n" + "="*80)
    print("FLAGGED POSTS")
    print("="*80)
    for _, row in threats.iterrows():
        cats = ", ".join(row["threat_categories"])
        matches = row["_threat_matches"]
        matched_text = "; ".join(
            f"[{cat}] {', '.join(ms)}" for cat, ms in matches.items()
        )
        print(f"\n--- {row['platform']} | {row['date']} | {row.get('seed_SeedName','')} | Categories: {cats}")
        print(f"Matched: {matched_text}")
        text = str(row["text_all"])[:500]
        print(f"Text: {text}")
        print()

    # Save
    # Drop the raw match dict for parquet (not serializable)
    out = df.drop(columns=["_threat_matches"])
    out.to_parquet(OUT_DATA, index=False)
    print(f"\nSaved to {OUT_DATA}")

    # --- Figure ---
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # 1. Category counts
    cat_counts = {cat: df[f"threat_{cat}"].sum() for cat in THREAT_PATTERNS}
    cat_counts = {k: v for k, v in cat_counts.items() if v > 0}
    if cat_counts:
        ax = axes[0]
        cats_sorted = sorted(cat_counts, key=cat_counts.get, reverse=True)
        ax.barh(
            [c.replace("_", " ").title() for c in cats_sorted],
            [cat_counts[c] for c in cats_sorted],
            color="#e74c3c",
        )
        ax.set_xlabel("Posts")
        ax.set_title("Threat Posts by Category")
        ax.invert_yaxis()

    # 2. Platform breakdown
    ax = axes[1]
    plat = threats.groupby("platform").size().sort_values(ascending=True)
    plat.plot.barh(ax=ax, color="#3498db")
    ax.set_xlabel("Posts")
    ax.set_title("Threat Posts by Platform")

    # 3. Timeline
    ax = axes[2]
    df["date"] = pd.to_datetime(df["date"], utc=True)
    threats = df[df["has_threat"]]
    threats_daily = threats.set_index("date").resample("D").size()
    all_daily = df.set_index("date").resample("D").size()
    ax.fill_between(all_daily.index, all_daily.values, alpha=0.3, color="#bdc3c7", label="All posts")
    ax.bar(threats_daily.index, threats_daily.values, color="#e74c3c", width=0.8, label="Threat posts")
    ax.set_ylabel("Posts")
    ax.set_title("Threat Posts Over Time")
    ax.legend()
    fig.autofmt_xdate()

    plt.suptitle(f"Threat Language Scan — {len(threats)} flagged / {len(df)} total", fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(OUT_FIG, dpi=150, bbox_inches="tight")
    print(f"Figure saved to {OUT_FIG}")


if __name__ == "__main__":
    main()
