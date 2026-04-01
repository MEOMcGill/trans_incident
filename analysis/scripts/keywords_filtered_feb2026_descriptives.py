"""
Generate descriptive analysis figures for the filtered incident/trans dataset.

Input:  analysis/data/feb2026_incident_trans_union_keywords.parquet
Output: analysis/figures/keyword_filtered_feb26_*.png
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

df = pd.read_parquet("analysis/data/feb2026_incident_trans_union_keywords.parquet")
df["day"] = pd.to_datetime(df["date"]).dt.date
df["post_type"] = "Incident only"
df.loc[df.is_trans & ~df.is_incident, "post_type"] = "Trans only"
df.loc[df.is_both, "post_type"] = "Both"

colors = {"Incident only": "#4C72B0", "Trans only": "#DD8452", "Both": "#C44E52"}
figdir = "analysis/figures"
type_order = ["Incident only", "Trans only", "Both"]

# ── 1. Daily post volume by type (stacked area) ─────────────────────────────
daily = df.groupby(["day", "post_type"]).size().unstack(fill_value=0)
daily = daily.reindex(columns=type_order, fill_value=0)

fig, ax = plt.subplots(figsize=(12, 5))
ax.stackplot(
    daily.index,
    daily["Incident only"], daily["Trans only"], daily["Both"],
    labels=type_order,
    colors=[colors[c] for c in type_order],
    alpha=0.85,
)
ax.axvline(pd.Timestamp("2026-02-10").date(), color="black", ls="--", lw=1, label="Shooting (Feb 10)")
ax.legend(loc="upper right")
ax.set_ylabel("Posts per day")
ax.set_title("Daily post volume by type - February 2026")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_daily_volume_by_type.png", dpi=200)
plt.close()
print("1. keyword_filtered_feb26_daily_volume_by_type.png")

# ── 2. Platform distribution by post type ────────────────────────────────────
plat_type = df.groupby(["platform", "post_type"]).size().unstack(fill_value=0)
plat_type = plat_type.reindex(columns=type_order, fill_value=0)
plat_type = plat_type.loc[plat_type.sum(axis=1).sort_values(ascending=True).index]

fig, ax = plt.subplots(figsize=(10, 5))
plat_type.plot.barh(stacked=True, color=[colors[c] for c in type_order], ax=ax)
ax.set_xlabel("Number of posts")
ax.set_title("Posts by platform and type")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_platform_by_type.png", dpi=200)
plt.close()
print("2. keyword_filtered_feb26_platform_by_type.png")

# ── 3. MainType distribution (Feb 10 onward) ────────────────────────────────
df_post = df[df["day"] >= pd.Timestamp("2026-02-10").date()]
mt = df_post.groupby(["seed_MainType", "post_type"]).size().unstack(fill_value=0)
mt = mt.reindex(columns=type_order, fill_value=0)
mt = mt.loc[mt.sum(axis=1).sort_values(ascending=True).index]

fig, ax = plt.subplots(figsize=(10, 5))
mt.plot.barh(stacked=True, color=[colors[c] for c in type_order], ax=ax)
ax.set_xlabel("Number of posts")
ax.set_title("Posts by seed type")
fig.text(0.5, -0.02, "Feb 10–28, 2026", ha="center", fontsize=10, style="italic", color="#555")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_maintype_by_type.png", dpi=200, bbox_inches="tight")
plt.close()
print("3. keyword_filtered_feb26_maintype_by_type.png")

# ── 4. Province (top 10) ─────────────────────────────────────────────────────
df["prov"] = df["seed_Province"].fillna("(missing)").replace("", "(missing)")
top_prov = df["prov"].value_counts().head(10).index
prov_type = df[df.prov.isin(top_prov)].groupby(["prov", "post_type"]).size().unstack(fill_value=0)
prov_type = prov_type.reindex(columns=type_order, fill_value=0)
prov_type = prov_type.loc[prov_type.sum(axis=1).sort_values(ascending=True).index]

fig, ax = plt.subplots(figsize=(10, 5))
prov_type.plot.barh(stacked=True, color=[colors[c] for c in type_order], ax=ax)
ax.set_xlabel("Number of posts")
ax.set_title("Posts by province/state (top 10)")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_province_by_type.png", dpi=200)
plt.close()
print("4. keyword_filtered_feb26_province_by_type.png")

# ── 5. Gender ─────────────────────────────────────────────────────────────────
df["gender"] = df["seed_Gender"].fillna("(missing)").replace("", "(missing)")
gen_type = df.groupby(["gender", "post_type"]).size().unstack(fill_value=0)
gen_type = gen_type.reindex(columns=type_order, fill_value=0)
gen_type = gen_type.loc[gen_type.sum(axis=1).sort_values(ascending=True).index]

fig, ax = plt.subplots(figsize=(8, 4))
gen_type.plot.barh(stacked=True, color=[colors[c] for c in type_order], ax=ax)
ax.set_xlabel("Number of posts")
ax.set_title("Posts by gender of seed account")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_gender_by_type.png", dpi=200)
plt.close()
print("5. keyword_filtered_feb26_gender_by_type.png")

# ── 6. Age ────────────────────────────────────────────────────────────────────
df["age"] = df["seed_Age"].fillna("(missing)").replace("", "(missing)")
age_type = df.groupby(["age", "post_type"]).size().unstack(fill_value=0)
age_type = age_type.reindex(columns=type_order, fill_value=0)
age_order = ["young", "middle", "older", "unknown", "(missing)"]
age_type = age_type.reindex([a for a in age_order if a in age_type.index])

fig, ax = plt.subplots(figsize=(8, 4))
age_type.plot.barh(stacked=True, color=[colors[c] for c in type_order], ax=ax)
ax.set_xlabel("Number of posts")
ax.set_title("Posts by age group of seed account")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_age_by_type.png", dpi=200)
plt.close()
print("6. keyword_filtered_feb26_age_by_type.png")

# ── 7. Language ───────────────────────────────────────────────────────────────
df["lang"] = df["seed_Language"].fillna("(missing)").replace("", "(missing)")
lang_type = df.groupby(["lang", "post_type"]).size().unstack(fill_value=0)
lang_type = lang_type.reindex(columns=type_order, fill_value=0)
lang_type = lang_type.loc[lang_type.sum(axis=1).sort_values(ascending=True).index]

fig, ax = plt.subplots(figsize=(8, 4))
lang_type.plot.barh(stacked=True, color=[colors[c] for c in type_order], ax=ax)
ax.set_xlabel("Number of posts")
ax.set_title("Posts by language of seed account")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_language_by_type.png", dpi=200)
plt.close()
print("7. keyword_filtered_feb26_language_by_type.png")

# ── 8. Party (non-empty only) ────────────────────────────────────────────────
df["party"] = df["seed_Party"].fillna("(no party)").replace("", "(no party)")
party_sub = df[~df.party.isin(["(no party)"])]
party_type = party_sub.groupby(["party", "post_type"]).size().unstack(fill_value=0)
party_type = party_type.reindex(columns=type_order, fill_value=0)
party_type = party_type.loc[party_type.sum(axis=1).sort_values(ascending=True).index]

fig, ax = plt.subplots(figsize=(8, 4))
party_type.plot.barh(stacked=True, color=[colors[c] for c in type_order], ax=ax)
ax.set_xlabel("Number of posts")
ax.set_title("Posts by party affiliation (partisan seeds only)")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_party_by_type.png", dpi=200)
plt.close()
print("8. keyword_filtered_feb26_party_by_type.png")

# ── 9. Engagement: median likes by type over time ────────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))
for ptype in type_order:
    sub = df[df.post_type == ptype].groupby("day")["like_count"].median()
    ax.plot(sub.index, sub.values, label=ptype, color=colors[ptype], lw=1.5)
ax.axvline(pd.Timestamp("2026-02-10").date(), color="black", ls="--", lw=1, label="Shooting (Feb 10)")
ax.set_ylabel("Median likes")
ax.set_title("Daily median likes by post type")
ax.legend(loc="upper right")
ax.set_yscale("symlog")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_daily_engagement_by_type.png", dpi=200)
plt.close()
print("9. keyword_filtered_feb26_daily_engagement_by_type.png")

# ── 10. Total daily likes for 'Both' posts ───────────────────────────────────
both = df[df.is_both].groupby("day")["like_count"].sum()
fig, ax = plt.subplots(figsize=(12, 5))
ax.bar(both.index, both.values, color=colors["Both"], alpha=0.8)
ax.axvline(pd.Timestamp("2026-02-10").date(), color="black", ls="--", lw=1, label="Shooting (Feb 10)")
ax.set_ylabel("Total likes")
ax.set_title("Daily total likes - intersection (incident + trans) posts")
ax.legend(loc="upper right")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(f"{figdir}/keyword_filtered_feb26_daily_engagement_both.png", dpi=200)
plt.close()
print("10. keyword_filtered_feb26_daily_engagement_both.png")

print("\nDone - 10 figures saved to analysis/figures/")
