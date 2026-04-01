"""
Interactive HTML chart: rhetoric trends (post count + likes) stacked vertically.
Order: count trendline, count bars, likes trendline, likes bars.
Hover highlights the selected line and dims others.
Date picker table shows top 5 posts for the selected date.

Input:  analysis/data/feb2026_daily_top_rhetoric_ca.parquet
Output: analysis/figures/keyword_filtered_feb26_rhetoric_trends_interactive.html
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import datetime
import json
import html as html_lib
import pandas as pd

DATA = "analysis/data/feb2026_daily_top_rhetoric_ca.parquet"
OUTPUT = "analysis/figures/keyword_filtered_feb26_rhetoric_trends_interactive.html"

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
ALL_CATS = MAIN_CATS + OTHER_CATS

CAT_LABELS = {
    "ideology_framing": "Ideology Framing",
    "conspiracy": "Conspiracy",
    "mockery": "Mockery",
    "violence_association": "Violence Association",
    "identity_denial": "Identity Denial",
    "child_protection": "Child Protection",
    "other": "Other Anti-Trans",
}

COLORS = {
    "ideology_framing": "#e74c3c",
    "conspiracy": "#3498db",
    "mockery": "#2ecc71",
    "violence_association": "#9b59b6",
    "identity_denial": "#f39c12",
    "child_protection": "#1abc9c",
    "other": "#95a5a6",
}


def build_series(df, days, cat_key, metric):
    if metric == "count":
        return df[df[cat_key]].groupby("day").size().reindex(days, fill_value=0)
    else:
        return df[df[cat_key]].groupby("day")["like_count"].sum().reindex(days, fill_value=0)


def main():
    df = pd.read_parquet(DATA)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["day"] = df["date"].dt.date

    for cat in ALL_CATS:
        df[f"cat_{cat}"] = df["haiku_rhetoric_categories"].apply(
            lambda x: cat in list(x) if x is not None and hasattr(x, "__iter__") else False
        )

    days = sorted(df["day"].unique())
    dates_str = [d.isoformat() for d in days]
    other_mask = df[[f"cat_{c}" for c in OTHER_CATS]].any(axis=1)
    anti_mask = df["haiku_contains_anti_trans_rhetoric"] == True

    # Top 5 posts per day for the table
    top5_by_day = {}
    for day in days:
        day_posts = df[df["day"] == day].nlargest(5, "like_count")
        posts = []
        for _, row in day_posts.iterrows():
            text = str(row["text_all"] or "")[:300].replace("\n", " ").strip()
            posts.append({
                "seed": html_lib.escape(str(row.get("seed_SeedName", ""))),
                "platform": str(row["platform"]),
                "text": html_lib.escape(text),
                "likes": int(row["like_count"]) if pd.notna(row["like_count"]) else 0,
            })
        top5_by_day[day.isoformat()] = posts

    traces = []

    # === Panel 1: Count trendlines (7 traces, indices 0-6) ===
    for cat in MAIN_CATS:
        s = build_series(df, days, f"cat_{cat}", "count")
        traces.append({
            "x": dates_str, "y": s.tolist(),
            "name": CAT_LABELS[cat], "type": "scatter", "mode": "lines",
            "line": {"color": COLORS[cat], "width": 2.5},
            "xaxis": "x", "yaxis": "y",
            "legendgroup": cat, "showlegend": True,
            "hovertemplate": f"<b>{CAT_LABELS[cat]}</b>: %{{y}}<extra></extra>",
        })
    s = df[other_mask].groupby("day").size().reindex(days, fill_value=0)
    traces.append({
        "x": dates_str, "y": s.tolist(),
        "name": "Other Anti-Trans", "type": "scatter", "mode": "lines",
        "line": {"color": COLORS["other"], "width": 2.5, "dash": "dash"},
        "xaxis": "x", "yaxis": "y",
        "legendgroup": "other", "showlegend": True,
        "hovertemplate": "<b>Other Anti-Trans</b>: %{y}<extra></extra>",
    })

    # === Panel 2: Count bars (2 traces, indices 7-8) ===
    total_count = df.groupby("day").size().reindex(days, fill_value=0)
    anti_count = df[anti_mask].groupby("day").size().reindex(days, fill_value=0)
    traces.append({
        "x": dates_str, "y": total_count.tolist(),
        "name": "All top posts", "type": "bar",
        "marker": {"color": "rgba(189,195,199,0.5)"},
        "xaxis": "x2", "yaxis": "y2",
        "legendgroup": "bar_all", "showlegend": True,
        "hovertemplate": "All: %{y}<extra></extra>",
    })
    traces.append({
        "x": dates_str, "y": anti_count.tolist(),
        "name": "Anti-trans", "type": "bar",
        "marker": {"color": "rgba(231,76,60,0.7)"},
        "xaxis": "x2", "yaxis": "y2",
        "legendgroup": "bar_anti", "showlegend": True,
        "hovertemplate": "Anti-trans: %{y}<extra></extra>",
    })

    # === Panel 3: Likes trendlines (7 traces, indices 9-15) ===
    for cat in MAIN_CATS:
        s = build_series(df, days, f"cat_{cat}", "likes")
        traces.append({
            "x": dates_str, "y": s.tolist(),
            "name": CAT_LABELS[cat], "type": "scatter", "mode": "lines",
            "line": {"color": COLORS[cat], "width": 2.5},
            "xaxis": "x3", "yaxis": "y3",
            "legendgroup": cat, "showlegend": False,
            "hovertemplate": f"<b>{CAT_LABELS[cat]}</b>: %{{y:,.0f}}<extra></extra>",
        })
    s = df[other_mask].groupby("day")["like_count"].sum().reindex(days, fill_value=0)
    traces.append({
        "x": dates_str, "y": s.tolist(),
        "name": "Other Anti-Trans", "type": "scatter", "mode": "lines",
        "line": {"color": COLORS["other"], "width": 2.5, "dash": "dash"},
        "xaxis": "x3", "yaxis": "y3",
        "legendgroup": "other", "showlegend": False,
        "hovertemplate": "<b>Other Anti-Trans</b>: %{y:,.0f}<extra></extra>",
    })

    # === Panel 4: Likes bars (2 traces, indices 16-17) ===
    total_likes = df.groupby("day")["like_count"].sum().reindex(days, fill_value=0)
    anti_likes = df[anti_mask].groupby("day")["like_count"].sum().reindex(days, fill_value=0)
    traces.append({
        "x": dates_str, "y": total_likes.tolist(),
        "name": "All top posts", "type": "bar",
        "marker": {"color": "rgba(189,195,199,0.5)"},
        "xaxis": "x4", "yaxis": "y4",
        "legendgroup": "bar_all", "showlegend": False,
        "hovertemplate": "All: %{y:,.0f}<extra></extra>",
    })
    traces.append({
        "x": dates_str, "y": anti_likes.tolist(),
        "name": "Anti-trans", "type": "bar",
        "marker": {"color": "rgba(231,76,60,0.7)"},
        "xaxis": "x4", "yaxis": "y4",
        "legendgroup": "bar_anti", "showlegend": False,
        "hovertemplate": "Anti-trans: %{y:,.0f}<extra></extra>",
    })

    # Compute y-axis max for count trends (with 15% padding)
    count_max_vals = []
    for cat in MAIN_CATS:
        s = build_series(df, days, f"cat_{cat}", "count")
        count_max_vals.append(s.max())
    other_s = df[other_mask].groupby("day").size().reindex(days, fill_value=0)
    count_max_vals.append(other_s.max())
    count_ymax = max(count_max_vals) * 1.15

    shooting = "2026-02-10"
    shape_template = {
        "type": "line", "x0": shooting, "x1": shooting,
        "y0": 0, "y1": 1,
        "line": {"dash": "dash", "color": "black", "width": 1},
        "opacity": 0.5,
    }

    layout = {
        "title": {
            "text": "Anti-Trans Rhetoric — Top 20 Trans Posts Daily, Feb 2026 (Canadian seeds only)",
            "font": {"size": 18},
            "y": 0.99, "yanchor": "top",
        },
        "height": 1400,
        "width": 1100,
        "barmode": "overlay",
        "hovermode": "closest",
        "template": "plotly_white",
        "margin": {"t": 120},
        "legend": {
            "orientation": "h",
            "yanchor": "top",
            "y": 1.0,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 12},
        },
        # Panel 1: count trends (top)
        "xaxis":  {"domain": [0, 1], "anchor": "y",  "showticklabels": False},
        "yaxis":  {"domain": [0.78, 0.92], "anchor": "x",  "title": "Posts per day",
                   "range": [0, count_ymax]},
        # Panel 2: count bars
        "xaxis2": {"domain": [0, 1], "anchor": "y2"},
        "yaxis2": {"domain": [0.58, 0.72], "anchor": "x2", "title": "Posts"},
        # Panel 3: likes trends
        "xaxis3": {"domain": [0, 1], "anchor": "y3", "showticklabels": False},
        "yaxis3": {"domain": [0.32, 0.52], "anchor": "x3", "title": "Likes per day"},
        # Panel 4: likes bars
        "xaxis4": {"domain": [0, 1], "anchor": "y4", "title": "Date"},
        "yaxis4": {"domain": [0.0, 0.26], "anchor": "x4", "title": "Likes"},
        "annotations": [
            {"x": 0.5, "y": 0.925, "xref": "paper", "yref": "paper",
             "text": "<b>Post Volume by Category</b>", "showarrow": False, "font": {"size": 14}},
            {"x": 0.5, "y": 0.73, "xref": "paper", "yref": "paper",
             "text": "<b>Post Volume: All vs Anti-Trans</b>", "showarrow": False, "font": {"size": 14}},
            {"x": 0.5, "y": 0.53, "xref": "paper", "yref": "paper",
             "text": "<b>Like Volume by Category</b>", "showarrow": False, "font": {"size": 14}},
            {"x": 0.5, "y": 0.27, "xref": "paper", "yref": "paper",
             "text": "<b>Like Volume: All vs Anti-Trans</b>", "showarrow": False, "font": {"size": 14}},
            {"x": shooting, "y": 0.92, "yref": "paper", "xref": "x",
             "text": "Tumbler Ridge<br>Shooting", "showarrow": True, "arrowhead": 0,
             "ax": 0, "ay": -20, "font": {"size": 10, "color": "black"}},
            {"x": "2026-02-18", "y": 0.92, "yref": "paper", "xref": "x",
             "text": "Hair Salon<br>Fined", "showarrow": True, "arrowhead": 0,
             "ax": 0, "ay": -20, "font": {"size": 10, "color": "black"}},
            {"x": "2026-02-21", "y": 0.92, "yref": "paper", "xref": "x",
             "text": "OpenAI<br>Letter", "showarrow": True, "arrowhead": 0,
             "ax": 0, "ay": -20, "font": {"size": 10, "color": "black"}},
        ],
        "shapes": [
            {**shape_template, "xref": "x",  "yref": "y domain"},
            {**shape_template, "xref": "x2", "yref": "y2 domain"},
            {**shape_template, "xref": "x3", "yref": "y3 domain"},
            {**shape_template, "xref": "x4", "yref": "y4 domain"},
            # Hair Salon Fined (Feb 18)
            {**shape_template, "x0": "2026-02-18", "x1": "2026-02-18", "xref": "x",  "yref": "y domain"},
            {**shape_template, "x0": "2026-02-18", "x1": "2026-02-18", "xref": "x2", "yref": "y2 domain"},
            {**shape_template, "x0": "2026-02-18", "x1": "2026-02-18", "xref": "x3", "yref": "y3 domain"},
            {**shape_template, "x0": "2026-02-18", "x1": "2026-02-18", "xref": "x4", "yref": "y4 domain"},
            # OpenAI Letter (Feb 21)
            {**shape_template, "x0": "2026-02-21", "x1": "2026-02-21", "xref": "x",  "yref": "y domain"},
            {**shape_template, "x0": "2026-02-21", "x1": "2026-02-21", "xref": "x2", "yref": "y2 domain"},
            {**shape_template, "x0": "2026-02-21", "x1": "2026-02-21", "xref": "x3", "yref": "y3 domain"},
            {**shape_template, "x0": "2026-02-21", "x1": "2026-02-21", "xref": "x4", "yref": "y4 domain"},
        ],
    }

    # Line trace indices: 0-6 (count), 9-15 (likes)
    count_line_start, count_line_end = 0, 7
    likes_line_start, likes_line_end = 9, 16
    total_traces = len(traces)

    traces_str = json.dumps(traces)
    layout_str = json.dumps(layout)
    top5_str = json.dumps(top5_by_day)
    dates_js = json.dumps(dates_str)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Anti-Trans Rhetoric Trends — Feb 2026</title>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #fafafa; }}
  #chart {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  #table-section {{
    margin-top: 20px; padding: 20px; background: white;
    border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  #table-section h3 {{ margin: 0 0 12px 0; font-size: 16px; color: #333; }}
  .date-picker-row {{
    display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
  }}
  .date-picker-row label {{ font-weight: 600; font-size: 14px; color: #555; }}
  .date-picker-row input {{
    padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px;
    font-size: 14px; cursor: pointer;
  }}
  .date-picker-row .date-nav {{
    padding: 6px 12px; border: 1px solid #ccc; border-radius: 4px;
    background: #f8f8f8; cursor: pointer; font-size: 14px; user-select: none;
  }}
  .date-picker-row .date-nav:hover {{ background: #eee; }}
  #post-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  #post-table th {{ text-align: left; padding: 8px 10px; border-bottom: 2px solid #ddd; color: #555; font-weight: 600; }}
  #post-table td {{ padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
  #post-table td.text-col {{ max-width: 550px; word-wrap: break-word; line-height: 1.4; }}
  #post-table td.likes-col {{ text-align: right; white-space: nowrap; font-weight: 500; }}
  #post-table tr:hover {{ background: #f9f9f9; }}
  .no-data {{ color: #999; font-style: italic; padding: 12px 0; }}
</style>
</head>
<body>

<div id="chart"></div>

<div id="table-section">
  <h3>Top 5 Posts by Likes</h3>
  <div class="date-picker-row">
    <span class="date-nav" id="prev-date">&larr;</span>
    <label for="date-input">Date:</label>
    <input type="date" id="date-input" min="2026-02-01" max="2026-02-28" value="2026-02-10">
    <span class="date-nav" id="next-date">&rarr;</span>
  </div>
  <div id="table-content">
    <p class="no-data">Select a date to view the top posts.</p>
  </div>
</div>

<script>
const traces = {traces_str};
const layout = {layout_str};
const top5 = {top5_str};
const allDates = {dates_js};
const TOTAL = {total_traces};
const COUNT_LINE = [{count_line_start}, {count_line_end}];
const LIKES_LINE = [{likes_line_start}, {likes_line_end}];

Plotly.newPlot('chart', traces, layout, {{
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
}});

const chartEl = document.getElementById('chart');

function isLineTrace(i) {{
  return (i >= COUNT_LINE[0] && i < COUNT_LINE[1]) || (i >= LIKES_LINE[0] && i < LIKES_LINE[1]);
}}

function getLineGroup(i) {{
  if (i >= COUNT_LINE[0] && i < COUNT_LINE[1]) return 'count';
  if (i >= LIKES_LINE[0] && i < LIKES_LINE[1]) return 'likes';
  return null;
}}

// Highlight hovered trace, dim others in same panel
chartEl.on('plotly_hover', function(data) {{
  const idx = data.points[0].curveNumber;
  if (!isLineTrace(idx)) return;

  const group = getLineGroup(idx);
  const update = {{'line.width': [], 'opacity': []}};

  for (let i = 0; i < TOTAL; i++) {{
    const g = getLineGroup(i);
    if (g === group) {{
      update['line.width'].push(i === idx ? 4.5 : 1);
      update['opacity'].push(i === idx ? 1 : 0.15);
    }} else {{
      update['line.width'].push(undefined);
      update['opacity'].push(undefined);
    }}
  }}
  Plotly.restyle(chartEl, update);
}});

chartEl.on('plotly_unhover', function() {{
  const update = {{'line.width': [], 'opacity': []}};
  for (let i = 0; i < TOTAL; i++) {{
    if (isLineTrace(i)) {{
      update['line.width'].push(2.5);
      update['opacity'].push(1);
    }} else {{
      update['line.width'].push(undefined);
      update['opacity'].push(undefined);
    }}
  }}
  Plotly.restyle(chartEl, update);
}});

// Date picker table
function renderTable(dateStr) {{
  const posts = top5[dateStr];
  const container = document.getElementById('table-content');
  if (!posts || posts.length === 0) {{
    container.innerHTML = '<p class="no-data">No posts for this date.</p>';
    return;
  }}
  let html = '<table id="post-table">';
  html += '<tr><th style="width:140px">Author</th><th style="width:80px">Platform</th><th>Text</th><th style="width:80px">Likes</th></tr>';
  posts.forEach(function(p) {{
    html += '<tr><td>' + p.seed + '</td><td>' + p.platform + '</td>';
    html += '<td class="text-col">' + p.text + '</td>';
    html += '<td class="likes-col">' + p.likes.toLocaleString() + '</td></tr>';
  }});
  html += '</table>';
  container.innerHTML = html;
}}

const dateInput = document.getElementById('date-input');
dateInput.addEventListener('change', function() {{ renderTable(this.value); }});

document.getElementById('prev-date').addEventListener('click', function() {{
  const cur = allDates.indexOf(dateInput.value);
  if (cur > 0) {{ dateInput.value = allDates[cur - 1]; renderTable(allDates[cur - 1]); }}
}});
document.getElementById('next-date').addEventListener('click', function() {{
  const cur = allDates.indexOf(dateInput.value);
  if (cur < allDates.length - 1) {{ dateInput.value = allDates[cur + 1]; renderTable(allDates[cur + 1]); }}
}});

// Init table with default date
renderTable(dateInput.value);
</script>

</body>
</html>"""

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
