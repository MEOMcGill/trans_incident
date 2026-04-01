"""
Generate interactive HTML presentation with embedded Plotly charts.

Input:  analysis/data/*.parquet, figures/reference/*/
Output: analysis/presentation.html
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import datetime
import pandas as pd
import numpy as np

OUTPUT = "analysis/presentation.html"

# ── Load data ────────────────────────────────────────────────────────────────

# Fig 1: Daily volume
df1 = pd.read_parquet("analysis/data/feb2026_incident_trans_union_keywords.parquet")
df1["date"] = pd.to_datetime(df1["date"], utc=True)
df1["day"] = df1["date"].dt.date
df1["post_type"] = "Incident only"
df1.loc[df1.is_trans & ~df1.is_incident, "post_type"] = "Trans only"
df1.loc[df1.is_both, "post_type"] = "Both"

days1 = sorted(df1["day"].unique())
daily1 = df1.groupby(["day", "post_type"]).size().unstack(fill_value=0)
for col in ["Incident only", "Trans only", "Both"]:
    if col not in daily1.columns:
        daily1[col] = 0
daily1 = daily1.reindex(days1, fill_value=0)

fig1_dates = [d.isoformat() for d in days1]
fig1_incident = daily1["Incident only"].tolist()
fig1_trans = daily1["Trans only"].tolist()
fig1_both = daily1["Both"].tolist()

# Fig 2: Maintype by type (Feb 10+)
df2 = df1[df1["day"] >= datetime.date(2026, 2, 10)]
mt = df2.groupby(["seed_MainType", "post_type"]).size().unstack(fill_value=0)
for col in ["Incident only", "Trans only", "Both"]:
    if col not in mt.columns:
        mt[col] = 0
mt = mt[["Incident only", "Trans only", "Both"]]
mt["total"] = mt.sum(axis=1)
mt = mt.sort_values("total", ascending=True)
fig2_labels = mt.index.tolist()
fig2_incident = mt["Incident only"].tolist()
fig2_trans = mt["Trans only"].tolist()
fig2_both = mt["Both"].tolist()

# Fig 3: Rhetoric trends by likes
df3 = pd.read_parquet("analysis/data/feb2026_daily_top_rhetoric_ca.parquet")
df3["date"] = pd.to_datetime(df3["date"], utc=True)
df3["day"] = df3["date"].dt.date

MAIN_CATS = ["ideology_framing", "conspiracy", "mockery", "violence_association", "identity_denial", "child_protection"]
OTHER_CATS = ["predator_framing", "pathologizing", "dehumanization", "medical_opposition"]
ALL_CATS = MAIN_CATS + OTHER_CATS

CAT_LABELS = {
    "ideology_framing": "Ideology Framing", "conspiracy": "Conspiracy",
    "mockery": "Mockery", "violence_association": "Violence Association",
    "identity_denial": "Identity Denial", "child_protection": "Child Protection",
}
COLORS = {
    "ideology_framing": "#e74c3c", "conspiracy": "#3498db", "mockery": "#2ecc71",
    "violence_association": "#9b59b6", "identity_denial": "#f39c12",
    "child_protection": "#1abc9c", "other": "#95a5a6",
}

for cat in ALL_CATS:
    df3[f"cat_{cat}"] = df3["haiku_rhetoric_categories"].apply(
        lambda x: cat in list(x) if x is not None and hasattr(x, "__iter__") else False
    )

days3 = sorted(df3["day"].unique())
fig3_dates = [d.isoformat() for d in days3]

# Bar data
anti_mask = df3["haiku_contains_anti_trans_rhetoric"] == True
fig3_total_likes = df3.groupby("day")["like_count"].sum().reindex(days3, fill_value=0).tolist()
fig3_anti_likes = df3[anti_mask].groupby("day")["like_count"].sum().reindex(days3, fill_value=0).tolist()

# Trend data (3-day rolling)
fig3_trends = {}
for cat in MAIN_CATS:
    daily_likes = df3[df3[f"cat_{cat}"]].groupby("day")["like_count"].sum().reindex(days3, fill_value=0)
    rolling = daily_likes.rolling(3, center=True, min_periods=1).mean()
    fig3_trends[cat] = [round(v, 1) for v in rolling.tolist()]

other_mask = df3[[f"cat_{c}" for c in OTHER_CATS]].any(axis=1)
other_daily = df3[other_mask].groupby("day")["like_count"].sum().reindex(days3, fill_value=0)
other_rolling = other_daily.rolling(3, center=True, min_periods=1).mean()
fig3_trends["other"] = [round(v, 1) for v in other_rolling.tolist()]

# Top 5 posts per day for tooltip table
top5_by_day = {}
for day in days3:
    day_posts = df3[df3["day"] == day].nlargest(5, "like_count")
    posts = []
    for _, row in day_posts.iterrows():
        text = str(row.get("text_all", "") or "")[:200].replace("\n", " ").replace('"', "'").strip()
        posts.append({
            "seed": str(row.get("seed_SeedName", "")),
            "likes": int(row["like_count"]) if pd.notna(row["like_count"]) else 0,
            "text": text,
        })
    top5_by_day[day.isoformat()] = posts

# Fig 4: Gender ideology (from reference CSVs)
fig4_l2 = pd.read_csv("figures/reference/gender_ideology_belief/layer2_data.csv")
fig4_l3 = pd.read_csv("figures/reference/gender_ideology_belief/layer3_data.csv")

# Map PANEL+y to category labels
panel_map = {1: "Age", 2: "Gender", 3: "Ideology", 4: "Social media"}
y_labels = {
    (1, 4): "18-29", (1, 3): "30-44", (1, 1): "45-59", (1, 2): "60+",
    (2, 2): "Man", (2, 1): "Woman",
    (3, 3): "Left (0-3)", (3, 2): "Centre (4-6)", (3, 1): "Right (7-10)",
    (4, 2): "Daily SM user", (4, 1): "Not daily",
}

fig4_items = []
for _, row in fig4_l3.iterrows():
    p, y_val = int(row["PANEL"]), int(row["y"])
    label = y_labels.get((p, y_val), f"P{p}Y{y_val}")
    group = panel_map.get(p, "")
    pct = float(row["x"])
    # Find matching CI from layer2
    match = fig4_l2[(fig4_l2["PANEL"] == p) & (fig4_l2["y"] == y_val)]
    ci_lo = float(match["xmin"].iloc[0]) if len(match) > 0 else pct
    ci_hi = float(match["xmax"].iloc[0]) if len(match) > 0 else pct
    fig4_items.append({"label": label, "group": group, "pct": round(pct, 1),
                        "ci_lo": round(ci_lo, 1), "ci_hi": round(ci_hi, 1)})

# Fig 5: Combined expression (from reference CSVs)
fig5_l1 = pd.read_csv("figures/reference/combined_expression/layer1_data.csv")
fig5_l2 = pd.read_csv("figures/reference/combined_expression/layer2_data.csv")

color_to_measure = {
    "#1A4AAD": "Express opinions online",
    "#D71B1E": "Respond to disagreeable posts",
    "#229A44": "Discuss politics at work/school",
    "#FF8200": "Discuss politics with coworkers",
}

fig5_items = []
for _, row in fig5_l2.iterrows():
    measure = color_to_measure.get(row["colour"], row["colour"])
    # y > 1.5 = Cisgender panel (top), y <= 1.5 = Non-binary/Trans (bottom)
    gender = "Cisgender" if row["y"] > 1.5 else "Non-binary/Trans"
    pct = float(row["x"])
    # Find matching CI
    match = fig5_l1[(fig5_l1["colour"] == row["colour"]) & (abs(fig5_l1["y"] - row["y"]) < 0.01)]
    ci_lo = float(match["xmin"].iloc[0]) if len(match) > 0 else pct
    ci_hi = float(match["xmax"].iloc[0]) if len(match) > 0 else pct
    fig5_items.append({"measure": measure, "gender": gender, "pct": round(pct, 1),
                        "ci_lo": round(ci_lo, 1), "ci_hi": round(ci_hi, 1),
                        "color": row["colour"]})


# ── Build HTML ───────────────────────────────────────────────────────────────

def j(obj):
    return json.dumps(obj)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Trans Panic Narratives Around Mass Shootings</title>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
    --text: #f1f5f9; --text-muted: #94a3b8;
    --accent: #38bdf8; --accent2: #818cf8;
    --red: #f87171; --green: #4ade80; --orange: #fb923c;
  }}
  html, body {{ height: 100%; font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); overflow: hidden; }}

  .slide {{ display: none; min-height: 100vh; padding: 50px 70px; flex-direction: column; justify-content: center; }}
  .slide.active {{ display: flex; }}
  .slide.active .anim {{
    opacity: 0; transform: translateY(20px);
    animation: slideUp 0.5s ease forwards;
  }}
  .slide.active .anim:nth-child(1) {{ animation-delay: 0.05s; }}
  .slide.active .anim:nth-child(2) {{ animation-delay: 0.12s; }}
  .slide.active .anim:nth-child(3) {{ animation-delay: 0.19s; }}
  .slide.active .anim:nth-child(4) {{ animation-delay: 0.26s; }}
  .slide.active .anim:nth-child(5) {{ animation-delay: 0.33s; }}
  .slide.active .anim:nth-child(6) {{ animation-delay: 0.40s; }}
  .slide.active .anim:nth-child(7) {{ animation-delay: 0.47s; }}
  .slide.active .anim:nth-child(8) {{ animation-delay: 0.54s; }}
  .slide.active .anim:nth-child(9) {{ animation-delay: 0.61s; }}
  .slide.active .anim:nth-child(10) {{ animation-delay: 0.68s; }}

  @keyframes slideUp {{ to {{ opacity: 1; transform: translateY(0); }} }}
  @keyframes scaleIn {{ from {{ opacity: 0; transform: scale(0.95); }} to {{ opacity: 1; transform: scale(1); }} }}
  @keyframes fadeInLeft {{ from {{ opacity: 0; transform: translateX(-30px); }} to {{ opacity: 1; transform: translateX(0); }} }}
  @keyframes fadeInRight {{ from {{ opacity: 0; transform: translateX(30px); }} to {{ opacity: 1; transform: translateX(0); }} }}
  @keyframes pulseGlow {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(56,189,248,0); }}
    50% {{ box-shadow: 0 0 20px 4px rgba(56,189,248,0.15); }}
  }}
  @keyframes countUp {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

  .nav {{
    position: fixed; bottom: 20px; right: 30px;
    display: flex; gap: 10px; z-index: 100; align-items: center;
  }}
  .nav button {{
    background: var(--surface2); border: none; color: var(--text);
    padding: 10px 18px; border-radius: 8px; cursor: pointer;
    font-size: 14px; font-family: inherit; font-weight: 500;
    transition: all 0.25s ease;
  }}
  .nav button:hover {{ background: var(--accent); color: var(--bg); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(56,189,248,0.3); }}
  .nav button:active {{ transform: translateY(0); }}
  .nav .counter {{ font-size: 13px; color: var(--text-muted); }}

  .progress {{ position: fixed; top: 0; left: 0; height: 3px; background: linear-gradient(90deg, var(--accent), var(--accent2)); transition: width 0.4s cubic-bezier(0.4,0,0.2,1); z-index: 100; }}

  h1 {{ font-size: 48px; font-weight: 700; line-height: 1.1; margin-bottom: 16px; }}
  h2 {{ font-size: 36px; font-weight: 600; line-height: 1.2; margin-bottom: 20px; color: var(--accent); }}
  h3 {{ font-size: 24px; font-weight: 600; margin-bottom: 14px; }}
  p, li {{ font-size: 20px; line-height: 1.6; color: var(--text-muted); }}
  .slide p + p {{ margin-top: 14px; }}

  .title-slide h1 {{ font-size: 56px; opacity: 0; animation: slideUp 0.8s ease 0.1s forwards; }}
  .title-slide .subtitle {{ font-size: 22px; color: var(--text-muted); margin-bottom: 40px; opacity: 0; animation: slideUp 0.8s ease 0.3s forwards; }}
  .title-slide .meta {{ font-size: 16px; color: var(--surface2); border-top: 1px solid var(--surface2); padding-top: 20px; margin-top: 20px; opacity: 0; animation: slideUp 0.8s ease 0.5s forwards; }}
  .title-slide .meta span {{ color: var(--text-muted); }}

  .takeaway {{ background: var(--surface); border-radius: 12px; padding: 24px 28px; margin-bottom: 16px; border-left: 4px solid var(--accent); transition: all 0.3s ease; cursor: default; }}
  .takeaway:hover {{ transform: translateX(8px); background: var(--surface2); box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
  .takeaway strong {{ color: var(--text); font-weight: 600; }}
  .takeaway p {{ font-size: 17px; margin: 0; }}

  .stats {{ display: flex; gap: 24px; margin: 24px 0; flex-wrap: wrap; }}
  .stat {{ background: var(--surface); border-radius: 12px; padding: 24px 30px; flex: 1; min-width: 200px; text-align: center; transition: all 0.3s ease; cursor: default; }}
  .stat:hover {{ transform: translateY(-6px); box-shadow: 0 8px 30px rgba(0,0,0,0.4); background: var(--surface2); }}
  .stat .number {{ font-size: 48px; font-weight: 700; color: var(--accent); line-height: 1; }}
  .stat .number.red {{ color: var(--red); }}
  .stat .number.green {{ color: var(--green); }}
  .stat .number.orange {{ color: var(--orange); }}
  .stat .label {{ font-size: 14px; color: var(--text-muted); margin-top: 8px; }}

  .chart-container {{ width: 100%; margin: 12px 0; opacity: 0; }}
  .slide.active .chart-container {{ animation: scaleIn 0.5s ease 0.2s forwards; }}

  ul, ol {{ padding-left: 28px; }}
  li {{ margin-bottom: 10px; }}
  li strong {{ color: var(--text); }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: center; }}
  .slide.active .two-col > :first-child {{ opacity: 0; animation: fadeInLeft 0.5s ease 0.15s forwards; }}
  .slide.active .two-col > :last-child {{ opacity: 0; animation: fadeInRight 0.5s ease 0.25s forwards; }}

  .cat-list {{ list-style: none; padding: 0; }}
  .cat-list li {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--surface2); font-size: 18px; transition: all 0.2s ease; }}
  .cat-list li:hover {{ padding-left: 12px; background: var(--surface); border-radius: 6px; }}
  .cat-list .dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; transition: transform 0.2s ease; }}
  .cat-list li:hover .dot {{ transform: scale(1.5); }}

  .section-slide {{ justify-content: center; align-items: center; text-align: center; }}
  .section-slide h2 {{ font-size: 44px; background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; opacity: 0; }}
  .section-slide.active h2 {{ animation: slideUp 0.6s ease 0.1s forwards; }}
  .section-slide p {{ max-width: 600px; opacity: 0; }}
  .section-slide.active p {{ animation: slideUp 0.6s ease 0.3s forwards; }}

  .method-text p, .method-text li {{ font-size: 16px; line-height: 1.5; }}

  .keyboard-hint {{ position: fixed; bottom: 24px; left: 30px; font-size: 12px; color: var(--surface2); transition: opacity 0.3s; }}
</style>
</head>
<body>

<div class="progress" id="progress"></div>

<!-- Slide 1: Title -->
<div class="slide title-slide active" data-slide="0">
  <h1>Trans Panic Narratives Around Mass Shootings</h1>
  <p class="subtitle">The Tumbler Ridge shooting and anti-trans discourse in the Canadian information ecosystem</p>
  <div class="meta">
    <span>Team: Mathieu, Saewon, Ben</span> &middot;
    <span>March 2026</span> &middot;
    <span>Media Ecosystem Observatory</span>
  </div>
</div>

<!-- Slide 2: Key Takeaways -->
<div class="slide" data-slide="1">
  <h2 class="anim">Key Takeaways</h2>
  <div class="takeaway anim">
    <p><strong>Trans panic narratives were significant but a minority</strong> of Tumbler Ridge shooting discussions, driven primarily by influencers.</p>
  </div>
  <div class="takeaway anim" style="border-color: var(--red);">
    <p><strong>Negative rhetoric dominated engagement</strong> with trans-related posts, especially violence association and identity denial.</p>
  </div>
  <div class="takeaway anim" style="border-color: var(--orange);">
    <p><strong>Canadians are deeply polarized on gender identity</strong> along ideological lines. Only 8% of left-leaning vs 66% of right-leaning believe schools indoctrinate with gender ideology.</p>
  </div>
  <div class="takeaway anim" style="border-color: var(--green);">
    <p><strong>Trans and non-binary Canadians are not less likely to participate</strong> in online political spaces despite a hostile environment.</p>
  </div>
</div>

<!-- Slide 3: Context -->
<div class="slide" data-slide="2">
  <h2 class="anim">Context</h2>
  <p class="anim">On February 10, 2026, 18-year-old Jesse Van Rootselaar killed her mother and half-brother at home in Tumbler Ridge, BC, then walked to Tumbler Ridge Secondary School, killing six and wounding 27 before dying by suicide. Canada's deadliest school shooting since 1989.</p>
  <p class="anim">The next day, RCMP confirmed Van Rootselaar was a trans woman. Within hours:</p>
  <ul style="margin-top: 12px;">
    <li class="anim">A fraudulent X account was renamed to match the shooter's YouTube channel with white supremacist content</li>
    <li class="anim">A BC MLA tweeted about the "transgender violence epidemic"</li>
    <li class="anim">An unrelated trans woman in Ontario was misidentified across platforms</li>
    <li class="anim">Elon Musk pushed viral charts claiming trans people are disproportionately responsible for mass shootings (reality: &lt;0.1%)</li>
  </ul>
</div>

<!-- Slide 4: Prior incidents -->
<div class="slide" data-slide="3">
  <h2 class="anim">A Pattern of Weaponization</h2>
  <p class="anim">Tumbler Ridge follows three prior incidents where trans identity was weaponized after mass violence:</p>
  <div class="stats" style="margin-top: 24px;">
    <div class="stat anim" style="text-align: left;">
      <div class="number" style="font-size: 28px;">2023</div>
      <div class="label" style="font-size: 16px; margin-top: 12px;">Nashville school shooting &mdash; shooter revealed to be transgender</div>
    </div>
    <div class="stat anim" style="text-align: left;">
      <div class="number" style="font-size: 28px;">2024</div>
      <div class="label" style="font-size: 16px; margin-top: 12px;">Annunciation shooting &mdash; shooter revealed to be trans</div>
    </div>
    <div class="stat anim" style="text-align: left;">
      <div class="number" style="font-size: 28px;">2025</div>
      <div class="label" style="font-size: 16px; margin-top: 12px;">Charlie Kirk assassination &mdash; shooter's partner was transgender</div>
    </div>
  </div>
</div>

<!-- Slide 5: Research Questions -->
<div class="slide" data-slide="4">
  <h2 class="anim">Research Questions</h2>
  <div style="margin-top: 10px;">
    <div class="takeaway anim" style="border-color: var(--accent);"><p><strong>1.</strong> What was the salience of the trans panic narrative and its source?</p></div>
    <div class="takeaway anim" style="border-color: var(--accent2);"><p><strong>2.</strong> What was the nature and reach of negative speech about transgenderism?</p></div>
    <div class="takeaway anim" style="border-color: var(--green);"><p><strong>3.</strong> Are Canadians polarized on gender identity, and does it suppress trans participation online?</p></div>
  </div>
</div>

<!-- Slide 6: Section divider - RQ1 -->
<div class="slide section-slide" data-slide="5">
  <h2>RQ1: Salience and Source</h2>
  <p>What share of the discussion mentioned transgenderism, and who was driving it?</p>
</div>

<!-- Slide 7: Volume (interactive) -->
<div class="slide" data-slide="6">
  <h2 class="anim">Post Volume Spiked After the Shooting</h2>
  <p class="anim">Posts about Tumbler Ridge spiked on Feb 11 (UTC). Trans-related discussion increased but remained a minority.</p>
  <div class="chart-container" id="fig1" style="height: 420px;"></div>
</div>

<!-- Slide 8: Source (interactive) -->
<div class="slide" data-slide="7">
  <h2 class="anim">Influencers Drove Trans-Related Discourse</h2>
  <p class="anim">Influencers were the main source. News outlets, politicians, and government organizations rarely linked the incident to transgenderism.</p>
  <div class="chart-container" id="fig2" style="height: 380px;"></div>
</div>

<!-- Slide 9: Section divider - RQ2 -->
<div class="slide section-slide" data-slide="8">
  <h2>RQ2: Nature and Reach of Negative Speech</h2>
  <p>How much engagement did negative rhetoric receive, and what themes dominated?</p>
</div>

<!-- Slide 10: Classification -->
<div class="slide" data-slide="9">
  <h2 class="anim">Classification Approach</h2>
  <p class="anim">Using Claude Haiku 4.5, we classified the <strong style="color: var(--text);">top 20 posts per day</strong> in February 2026 (Canadian seeds, 560 posts).</p>
  <div class="stats anim">
    <div class="stat"><div class="number" data-count="55">0%</div><div class="label">negative rhetoric</div></div>
    <div class="stat"><div class="number red" data-count="307">0</div><div class="label">anti-trans</div></div>
    <div class="stat"><div class="number green" data-count="150">0</div><div class="label">pro-trans</div></div>
    <div class="stat"><div class="number orange" data-count="102">0</div><div class="label">neutral</div></div>
  </div>
  <ul class="cat-list" style="margin-top: 16px;">
    <li class="anim"><span class="dot" style="background: #9b59b6;"></span><strong>Violence association</strong> &mdash; Trans people with violence or criminality</li>
    <li class="anim"><span class="dot" style="background: #e74c3c;"></span><strong>Ideology framing</strong> &mdash; Dismissing trans identity as ideology or trend</li>
    <li class="anim"><span class="dot" style="background: #3498db;"></span><strong>Conspiracy</strong> &mdash; Hidden agenda/lobby claims</li>
    <li class="anim"><span class="dot" style="background: #2ecc71;"></span><strong>Mockery</strong> &mdash; Ridiculing trans people or identities</li>
    <li class="anim"><span class="dot" style="background: #f39c12;"></span><strong>Identity denial</strong> &mdash; Denying trans identities, misgendering</li>
    <li class="anim"><span class="dot" style="background: #1abc9c;"></span><strong>Child protection</strong> &mdash; Child safety rhetoric against trans rights</li>
  </ul>
</div>

<!-- Slide 11: Engagement (interactive) -->
<div class="slide" data-slide="10">
  <h2 class="anim">Engagement Concentrated in Negative Rhetoric</h2>
  <div class="chart-container" id="fig3" style="height: 520px;"></div>
</div>

<!-- Slide 12: Before/after -->
<div class="slide" data-slide="11">
  <h2 class="anim">The Shooting Weaponized Existing Discourse</h2>
  <div class="two-col">
    <div>
      <h3>Before Feb 10</h3>
      <div class="stats" style="flex-direction: column; gap: 12px;">
        <div class="stat" style="padding: 16px 20px; text-align: left;">
          <div class="number" style="font-size: 36px;" data-count="50">0%</div>
          <div class="label">anti-trans rate</div>
        </div>
      </div>
      <p style="font-size: 17px; margin-top: 12px;">Ideology framing (28%), conspiracy (19%), child protection (19%). Violence association only <strong style="color: var(--text);">5%</strong>.</p>
    </div>
    <div>
      <h3>Week After (Feb 11&ndash;17)</h3>
      <div class="stats" style="flex-direction: column; gap: 12px;">
        <div class="stat" style="padding: 16px 20px; text-align: left; animation: pulseGlow 2s ease infinite;">
          <div class="number red" style="font-size: 36px;" data-count="74">0%</div>
          <div class="label">anti-trans rate</div>
        </div>
      </div>
      <p style="font-size: 17px; margin-top: 12px;">Violence association to <strong style="color: var(--red);">49%</strong>. Conspiracy doubles. Identity denial triples.</p>
    </div>
  </div>
  <p class="anim" style="margin-top: 24px; font-size: 17px;">The baseline <strong style="color: var(--text);">never returned to pre-shooting levels</strong>. Feb 18&ndash;28 held at 75%.</p>
</div>

<!-- Slide 13: Threats -->
<div class="slide" data-slide="12">
  <h2 class="anim">Explicit Threats Were Absent</h2>
  <p class="anim">We searched all 11,211 posts for explicit violent threats using regex patterns.</p>
  <div class="stats anim" style="margin-top: 24px;">
    <div class="stat"><div class="number" data-count="51">0</div><div class="label">posts flagged</div></div>
    <div class="stat"><div class="number green" data-count="0">0</div><div class="label">true positives</div></div>
  </div>
  <p class="anim" style="margin-top: 20px;">All 51 were false positives &mdash; posts <em>about</em> violence against trans people. Hostility in this corpus is <strong style="color: var(--text);">coded and indirect</strong>. Explicit threats may be more common among anonymous accounts not in our seedlist.</p>
</div>

<!-- Slide 14: Section divider - RQ3 -->
<div class="slide section-slide" data-slide="13">
  <h2>RQ3: Polarization and Participation</h2>
  <p>Are Canadians polarized on gender identity, and does hostility suppress trans voices?</p>
</div>

<!-- Slide 15: Polarization (interactive) -->
<div class="slide" data-slide="14">
  <h2 class="anim">Deep Ideological Polarization</h2>
  <p class="anim">"Schools are indoctrinating kids with radical gender ideology" &mdash; % who believe probably/definitely true</p>
  <div class="chart-container" id="fig4" style="height: 440px;"></div>
</div>

<!-- Slide 16: Participation (interactive) -->
<div class="slide" data-slide="15">
  <h2 class="anim">Trans and Non-Binary Canadians Are More Active Online</h2>
  <p class="anim" style="font-size: 18px;">Predicted % from OLS controlling for age, political interest, SM use, education, region, and survey wave. Differences do not extend to offline speech &mdash; consistent with an <em>activated minority</em> framework.</p>
  <div class="chart-container" id="fig5" style="height: 440px;"></div>
</div>

<!-- Slide 17: Implications -->
<div class="slide" data-slide="16">
  <h2 class="anim">Implications</h2>
  <div class="takeaway anim"><p><strong>Influencers are the primary vector</strong> for trans panic narratives. News outlets and politicians largely didn't connect the shooting to transgenderism.</p></div>
  <div class="takeaway anim" style="border-color: var(--red);"><p><strong>Hostility is coded, not overt.</strong> Violence association, identity denial, and conspiracy framing &mdash; not explicit threats.</p></div>
  <div class="takeaway anim" style="border-color: var(--orange);"><p><strong>Events are weaponized instantly.</strong> 50% &rarr; 74% anti-trans rhetoric within one week.</p></div>
  <div class="takeaway anim" style="border-color: var(--green);"><p><strong>Trans voices persist online despite hostility</strong> &mdash; but this may reflect selection bias.</p></div>
</div>

<!-- Slide 18: Limitations -->
<div class="slide" data-slide="17">
  <h2 class="anim">Limitations</h2>
  <ul style="margin-top: 12px;">
    <li class="anim">Seedlist covers prominent accounts only &mdash; threats may exist among anonymous users</li>
    <li class="anim">Haiku 4.5 classification not validated against human coders for this task</li>
    <li class="anim">Top-20-per-day sampling may miss lower-engagement patterns</li>
    <li class="anim">Trans participation finding is correlational &mdash; self-selection into surveys</li>
    <li class="anim">Gender ideology question fielded to English-speaking respondents only</li>
  </ul>
</div>

<!-- Slide 19: Methodology -->
<div class="slide method-text" data-slide="18">
  <h2 class="anim">Methodology</h2>
  <div class="two-col">
    <div>
      <h3>Social media data</h3>
      <ul>
        <li>Seedlist of politically influential Canadian entities</li>
        <li>Feb 2026 posts filtered by Tumbler Ridge + trans/queer keywords</li>
        <li>11,211 posts (7,512 incident, 4,313 trans, 614 both)</li>
        <li>Top 20 trans posts/day classified by Claude Haiku 4.5</li>
        <li>560 posts classified (Canadian seeds only)</li>
      </ul>
    </div>
    <div>
      <h3>Survey data</h3>
      <ul>
        <li>MEO monthly tracking survey, Jul 2024 &ndash; Feb 2026</li>
        <li>~1,500/month (Leger panel), 32,632 total</li>
        <li>Post-stratification weights on age, gender, region</li>
        <li>Gender ideology: Oct 2025 (N=710, English only)</li>
        <li>Political expression: 17 waves (N=32,632)</li>
        <li>OLS, wave-clustered SEs, standard controls</li>
      </ul>
    </div>
  </div>
</div>

<!-- Navigation -->
<div class="nav">
  <button onclick="prev()">&larr; Prev</button>
  <span class="counter" id="counter">1 / 19</span>
  <button onclick="next()">Next &rarr;</button>
</div>
<div class="keyboard-hint" id="hint">Arrow keys or Space to navigate</div>

<script>
// ── Slide navigation ────────────────────────────────────────────────────────
const slides = document.querySelectorAll('.slide');
let current = 0;
const chartInited = new Set();

function show(n) {{
  if (n === current && n !== 0) return;
  slides[current].classList.remove('active');
  current = Math.max(0, Math.min(n, slides.length - 1));
  const slide = slides[current];
  void slide.offsetWidth;
  slide.classList.add('active');
  document.getElementById('counter').textContent = (current + 1) + ' / ' + slides.length;
  document.getElementById('progress').style.width = ((current + 1) / slides.length * 100) + '%';
  runCounters(slide);
  document.getElementById('hint').style.opacity = '0';
  // Lazy-init charts when their slide becomes active
  const idx = parseInt(slide.dataset.slide);
  if (!chartInited.has(idx)) {{
    chartInited.add(idx);
    if (idx === 6) initFig1();
    if (idx === 7) initFig2();
    if (idx === 10) initFig3();
    if (idx === 14) initFig4();
    if (idx === 15) initFig5();
  }}
}}

function next() {{ show(current + 1); }}
function prev() {{ show(current - 1); }}

document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === ' ') {{ e.preventDefault(); next(); }}
  if (e.key === 'ArrowLeft') {{ e.preventDefault(); prev(); }}
}});

function runCounters(slide) {{
  slide.querySelectorAll('[data-count]').forEach(el => {{
    const target = parseInt(el.dataset.count);
    const suffix = el.textContent.includes('%') ? '%' : '';
    const duration = 800;
    const start = performance.now();
    function tick(now) {{
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(eased * target) + suffix;
      if (t < 1) requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);
  }});
}}

const plotlyConfig = {{ displayModeBar: false, responsive: true }};
const darkLayout = {{
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: {{ family: 'Inter', color: '#94a3b8' }},
  xaxis: {{ gridcolor: '#1e293b', zerolinecolor: '#334155' }},
  yaxis: {{ gridcolor: '#1e293b', zerolinecolor: '#334155' }},
  margin: {{ l: 60, r: 20, t: 40, b: 50 }},
  hoverlabel: {{ bgcolor: '#1e293b', bordercolor: '#334155', font: {{ color: '#f1f5f9', family: 'Inter' }} }},
}};

// ── Fig 1: Daily volume stacked area ────────────────────────────────────────
function initFig1() {{
  const dates = {j(fig1_dates)};
  const shooting = '2026-02-10';
  Plotly.newPlot('fig1', [
    {{ x: dates, y: {j(fig1_incident)}, name: 'Incident only', stackgroup: 'one',
       fillcolor: 'rgba(76,114,176,0.7)', line: {{width: 0}},
       hovertemplate: '<b>Incident only</b>: %{{y}}<extra></extra>' }},
    {{ x: dates, y: {j(fig1_trans)}, name: 'Trans only', stackgroup: 'one',
       fillcolor: 'rgba(221,132,82,0.7)', line: {{width: 0}},
       hovertemplate: '<b>Trans only</b>: %{{y}}<extra></extra>' }},
    {{ x: dates, y: {j(fig1_both)}, name: 'Both', stackgroup: 'one',
       fillcolor: 'rgba(196,78,82,0.7)', line: {{width: 0}},
       hovertemplate: '<b>Both</b>: %{{y}}<extra></extra>' }},
  ], {{
    ...darkLayout,
    hovermode: 'x unified',
    legend: {{ orientation: 'h', y: 1.08, font: {{ size: 13 }} }},
    yaxis: {{ ...darkLayout.yaxis, title: 'Posts per day' }},
    shapes: [{{ type: 'line', x0: shooting, x1: shooting, y0: 0, y1: 1, yref: 'paper',
               line: {{ dash: 'dash', color: '#f1f5f9', width: 1 }}, opacity: 0.5 }}],
    annotations: [{{ x: shooting, y: 1, yref: 'paper', text: 'Shooting', showarrow: false,
                     font: {{ size: 11, color: '#94a3b8' }}, yanchor: 'bottom' }}],
  }}, plotlyConfig);
}}

// ── Fig 2: Maintype horizontal bars ─────────────────────────────────────────
function initFig2() {{
  const labels = {j(fig2_labels)};
  Plotly.newPlot('fig2', [
    {{ y: labels, x: {j(fig2_incident)}, name: 'Incident only', type: 'bar', orientation: 'h',
       marker: {{ color: 'rgba(76,114,176,0.7)' }},
       hovertemplate: '<b>%{{y}}</b><br>Incident: %{{x}}<extra></extra>' }},
    {{ y: labels, x: {j(fig2_trans)}, name: 'Trans only', type: 'bar', orientation: 'h',
       marker: {{ color: 'rgba(221,132,82,0.7)' }},
       hovertemplate: '<b>%{{y}}</b><br>Trans: %{{x}}<extra></extra>' }},
    {{ y: labels, x: {j(fig2_both)}, name: 'Both', type: 'bar', orientation: 'h',
       marker: {{ color: 'rgba(196,78,82,0.7)' }},
       hovertemplate: '<b>%{{y}}</b><br>Both: %{{x}}<extra></extra>' }},
  ], {{
    ...darkLayout,
    barmode: 'stack',
    legend: {{ orientation: 'h', y: 1.08, font: {{ size: 13 }} }},
    xaxis: {{ ...darkLayout.xaxis, title: 'Number of posts' }},
    margin: {{ ...darkLayout.margin, l: 180 }},
    annotations: [{{ x: 0.5, y: -0.12, xref: 'paper', yref: 'paper',
                     text: '<i>Feb 10\u201328, 2026</i>', showarrow: false,
                     font: {{ size: 12, color: '#64748b' }} }}],
  }}, plotlyConfig);
}}

// ── Fig 3: Rhetoric trends (likes, dual panel) ─────────────────────────────
function initFig3() {{
  const dates = {j(fig3_dates)};
  const trends = {j(fig3_trends)};
  const catLabels = {j(CAT_LABELS)};
  const colors = {j(COLORS)};
  const totalLikes = {j(fig3_total_likes)};
  const antiLikes = {j(fig3_anti_likes)};
  const top5 = {j(top5_by_day)};
  const shooting = '2026-02-10';

  const traces = [];

  // Bar traces (top panel)
  traces.push({{ x: dates, y: totalLikes, name: 'All top posts', type: 'bar',
    marker: {{ color: 'rgba(189,195,199,0.4)' }}, xaxis: 'x', yaxis: 'y',
    hovertemplate: 'All: %{{y:,.0f}}<extra></extra>', legendgroup: 'bar_all' }});
  traces.push({{ x: dates, y: antiLikes, name: 'Anti-trans', type: 'bar',
    marker: {{ color: 'rgba(231,76,60,0.6)' }}, xaxis: 'x', yaxis: 'y',
    hovertemplate: 'Anti-trans: %{{y:,.0f}}<extra></extra>', legendgroup: 'bar_anti' }});

  // Trend traces (bottom panel)
  const catOrder = ['ideology_framing','conspiracy','mockery','violence_association','identity_denial','child_protection'];
  catOrder.forEach(cat => {{
    traces.push({{ x: dates, y: trends[cat], name: catLabels[cat], type: 'scatter', mode: 'lines',
      line: {{ color: colors[cat], width: 2.5 }}, xaxis: 'x2', yaxis: 'y2',
      legendgroup: cat,
      hovertemplate: '<b>' + catLabels[cat] + '</b>: %{{y:,.0f}}<extra></extra>' }});
  }});
  traces.push({{ x: dates, y: trends['other'], name: 'Other Anti-Trans', type: 'scatter', mode: 'lines',
    line: {{ color: colors['other'], width: 2.5, dash: 'dash' }}, xaxis: 'x2', yaxis: 'y2',
    legendgroup: 'other',
    hovertemplate: '<b>Other</b>: %{{y:,.0f}}<extra></extra>' }});

  const shapeBase = {{ type: 'line', y0: 0, y1: 1, line: {{ dash: 'dash', color: '#f1f5f9', width: 1 }}, opacity: 0.4 }};

  Plotly.newPlot('fig3', traces, {{
    ...darkLayout,
    height: 520,
    barmode: 'overlay',
    hovermode: 'x unified',
    legend: {{ orientation: 'h', y: 1.06, font: {{ size: 11 }}, tracegroupgap: 5 }},
    xaxis:  {{ domain: [0,1], anchor: 'y',  showticklabels: false, gridcolor: '#1e293b' }},
    yaxis:  {{ domain: [0.62,0.95], anchor: 'x', title: 'Likes', gridcolor: '#1e293b', zerolinecolor: '#334155' }},
    xaxis2: {{ domain: [0,1], anchor: 'y2', gridcolor: '#1e293b' }},
    yaxis2: {{ domain: [0,0.55], anchor: 'x2', title: 'Likes (3-day rolling)', gridcolor: '#1e293b', zerolinecolor: '#334155' }},
    shapes: [
      {{ ...shapeBase, x0: shooting, x1: shooting, xref: 'x', yref: 'y domain' }},
      {{ ...shapeBase, x0: shooting, x1: shooting, xref: 'x2', yref: 'y2 domain' }},
      {{ ...shapeBase, x0: '2026-02-18', x1: '2026-02-18', xref: 'x2', yref: 'y2 domain' }},
      {{ ...shapeBase, x0: '2026-02-21', x1: '2026-02-21', xref: 'x2', yref: 'y2 domain' }},
    ],
    annotations: [
      {{ x: shooting, y: 0.97, yref: 'y2 domain', xref: 'x2', text: 'Shooting', showarrow: false, font: {{ size: 10, color: '#94a3b8' }} }},
      {{ x: '2026-02-18', y: 0.97, yref: 'y2 domain', xref: 'x2', text: 'Hair Salon', showarrow: false, font: {{ size: 10, color: '#94a3b8' }} }},
      {{ x: '2026-02-21', y: 0.97, yref: 'y2 domain', xref: 'x2', text: 'OpenAI Letter', showarrow: false, font: {{ size: 10, color: '#94a3b8' }} }},
    ],
    margin: {{ l: 70, r: 20, t: 40, b: 40 }},
  }}, plotlyConfig);

  // Hover highlight: dim other lines in trend panel
  const fig3El = document.getElementById('fig3');
  const trendStart = 2; // first trend trace index
  const trendEnd = traces.length;

  fig3El.on('plotly_hover', function(data) {{
    const idx = data.points[0].curveNumber;
    if (idx < trendStart) return;
    const update = {{}};
    update['line.width'] = [];
    update['opacity'] = [];
    for (let i = 0; i < traces.length; i++) {{
      if (i >= trendStart) {{
        update['line.width'].push(i === idx ? 4.5 : 1);
        update['opacity'].push(i === idx ? 1 : 0.15);
      }} else {{
        update['line.width'].push(undefined);
        update['opacity'].push(undefined);
      }}
    }}
    Plotly.restyle(fig3El, update);
  }});

  fig3El.on('plotly_unhover', function() {{
    const update = {{}};
    update['line.width'] = [];
    update['opacity'] = [];
    for (let i = 0; i < traces.length; i++) {{
      if (i >= trendStart) {{
        update['line.width'].push(2.5);
        update['opacity'].push(1);
      }} else {{
        update['line.width'].push(undefined);
        update['opacity'].push(undefined);
      }}
    }}
    Plotly.restyle(fig3El, update);
  }});
}}

// ── Fig 4: Gender ideology dot plot ─────────────────────────────────────────
function initFig4() {{
  const items = {j(fig4_items)};
  const groups = ['Age', 'Gender', 'Ideology', 'Social media'];
  const labels = items.map(d => d.label).reverse();
  const pcts = items.map(d => d.pct).reverse();
  const ciLo = items.map(d => d.pct - d.ci_lo).reverse();
  const ciHi = items.map(d => d.ci_hi - d.pct).reverse();
  const grps = items.map(d => d.group).reverse();

  // Add group separator lines
  const shapes = [];
  let prevGroup = grps[0];
  for (let i = 1; i < grps.length; i++) {{
    if (grps[i] !== prevGroup) {{
      shapes.push({{ type: 'line', x0: 0, x1: 100, y0: i - 0.5, y1: i - 0.5,
                     line: {{ color: '#334155', width: 0.5 }} }});
      prevGroup = grps[i];
    }}
  }}

  Plotly.newPlot('fig4', [{{
    x: pcts, y: labels, type: 'scatter', mode: 'markers',
    marker: {{ color: '#1A4AAD', size: 12 }},
    error_x: {{ type: 'data', symmetric: false, array: ciHi, arrayminus: ciLo,
               color: '#1A4AAD', thickness: 2, width: 6 }},
    hovertemplate: '<b>%{{y}}</b>: %{{x:.0f}}%<extra></extra>',
  }}], {{
    ...darkLayout,
    showlegend: false,
    xaxis: {{ ...darkLayout.xaxis, title: '% who believe probably/definitely true', range: [0, 100],
             dtick: 20 }},
    yaxis: {{ ...darkLayout.yaxis, automargin: true }},
    shapes: [
      ...shapes,
      {{ type: 'line', x0: 50, x1: 50, y0: -0.5, y1: labels.length - 0.5,
         line: {{ color: '#475569', width: 1, dash: 'dash' }} }}
    ],
    margin: {{ l: 130, r: 30, t: 20, b: 50 }},
  }}, plotlyConfig);
}}

// ── Fig 5: Combined expression grouped dot plot ─────────────────────────────
function initFig5() {{
  const items = {j(fig5_items)};
  const colorMap = {{
    '#1A4AAD': 'Express opinions online',
    '#D71B1E': 'Respond to disagreeable posts',
    '#229A44': 'Discuss politics at work/school',
    '#FF8200': 'Discuss politics with coworkers',
  }};

  // Group by gender
  const genders = ['Non-binary/Trans', 'Cisgender'];
  const measures = Object.values(colorMap);
  const colorList = Object.keys(colorMap);

  const traces = measures.map((measure, mi) => {{
    const color = colorList[mi];
    const xs = [], ys = [], errLo = [], errHi = [], texts = [];
    genders.forEach(g => {{
      const item = items.find(d => d.gender === g && d.measure === measure);
      if (item) {{
        xs.push(item.pct);
        ys.push(g);
        errLo.push(item.pct - item.ci_lo);
        errHi.push(item.ci_hi - item.pct);
        texts.push(item.pct + '%');
      }}
    }});
    return {{
      x: xs, y: ys, text: texts, textposition: 'top center',
      textfont: {{ color: color, size: 12 }},
      type: 'scatter', mode: 'markers+text', name: measure,
      marker: {{ color: color, size: 11 }},
      error_x: {{ type: 'data', symmetric: false, array: errHi, arrayminus: errLo,
                 color: color, thickness: 2, width: 5 }},
      hovertemplate: '<b>' + measure + '</b><br>%{{y}}: %{{x:.0f}}%<extra></extra>',
    }};
  }});

  Plotly.newPlot('fig5', traces, {{
    ...darkLayout,
    legend: {{ orientation: 'h', y: -0.15, font: {{ size: 11 }}, xanchor: 'center', x: 0.5 }},
    xaxis: {{ ...darkLayout.xaxis, title: '% (predicted)', range: [15, 70], dtick: 10 }},
    yaxis: {{ ...darkLayout.yaxis, automargin: true }},
    margin: {{ l: 140, r: 30, t: 20, b: 80 }},
  }}, plotlyConfig);
}}

show(0);
</script>

</body>
</html>"""

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Saved {OUTPUT}")
