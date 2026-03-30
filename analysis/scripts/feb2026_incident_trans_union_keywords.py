"""
Filter February 2026 seedlist data for posts related to the Tumblr Ridge
shooting incident and trans/queer keywords.

Input:  ../analysis/data/phh_2026_02.parquet (relative to repo root)
Output: analysis/data/feb2026_incident_trans_union_keywords.parquet
"""

import pandas as pd

# ── Load data ────────────────────────────────────────────────────────────────

df = pd.read_parquet("../../analysis/data/phh_2026_02.parquet")

# Combine all text fields for search
df["search_text"] = (
    df["text"].fillna("")
    + " " + df["text_all"].fillna("")
    + " " + df["title"].fillna("")
    + " " + df["description"].fillna("")
    + " " + df["message"].fillna("")
    + " " + df["caption"].fillna("")
)
text_lower = df["search_text"].str.lower()

# ── Leetspeak-aware regex builder ────────────────────────────────────────────

def leet(word):
    """Build regex that matches common self-censored variants of a word."""
    subs = {
        "a": "[a@4]", "s": "[s$5]", "e": "[e3]",
        "i": "[i1!]", "o": "[o0]", "g": "[g9]",
    }
    return "".join(subs.get(c, c) for c in word.lower())

# ── Keywords ─────────────────────────────────────────────────────────────────

# Incident: Tumblr Ridge shooting (Feb 10, 2026)
# Shooter: Jesse Van Rootselaar (also known as Jesse Strang), a trans woman
incident_kw = [
    "tumbler ridge", "tumbler-ridge", "tumblerridge",
    "jesse van rootselaar", "van rootselaar", "rootselaar",
    "jesse strang",
]

# Trans/queer-related terms
trans_words = [
    "trans ", "transgender", "transgenre", "transsexual", "transphob",
    "trans panic", "nonbinary", "non-binary", "non binary",
    "lgbtq", "lgbt", "queer", "gender identity", "gender ideology",
    "two-spirit", "two spirit", "2slgbtq", "trans rights", "trans people",
    "trans community", "trans woman", "trans man", "trans folk", "transidentit",
]
trans_patterns = [leet(w) for w in trans_words]

# ── Filter ───────────────────────────────────────────────────────────────────

incident_mask = text_lower.str.contains("|".join(incident_kw), regex=True)
trans_mask = text_lower.str.contains("|".join(trans_patterns), regex=True)

df["is_incident"] = incident_mask
df["is_trans"] = trans_mask
df["is_both"] = incident_mask & trans_mask

union = df[incident_mask | trans_mask].copy()

# ── Save ─────────────────────────────────────────────────────────────────────

out_path = "../data/feb2026_incident_trans_union_keywords.parquet"
union.to_parquet(out_path, index=False)
print(f"Saved {len(union)} posts to {out_path}")
print(f"  Incident only: {(incident_mask & ~trans_mask).sum()}")
print(f"  Trans only:    {(trans_mask & ~incident_mask).sum()}")
print(f"  Both:          {(incident_mask & trans_mask).sum()}")
