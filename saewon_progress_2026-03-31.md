# Progress — March 31, 2026

## What We Did

### 1. HPC Job Submission (Fir)

Pushed data and scripts to Fir, verified venv (`venv_qwen35`) and Qwen3.5-27B-FP8 weights already existed from prior setup.

**Submission history:**
- Job 30819802 (4h walltime) — **failed**. vLLM server never started; no error output captured.
- Job 30829391 (2h, with diagnostics) — **failed**. vLLM loaded model (80s) but `torch.compile` took 154s, total startup ~7 min. Server was still compiling when 10-min health check timed out.
- Job 30859854 (2h, `--enforce-eager`) — **failed**. Skipped torch.compile but hung at encoder cache / multimodal profiling step.
- Job 30861509 (2h, `--enforce-eager` + `--limit-mm-per-prompt`) — **started successfully** (225s startup). However, all 11,211 posts failed: the prompt (~2,597 input tokens) + `max_tokens=1500` exceeded `--max-model-len 4096` by 1 token. Every request returned a 400 error.
- Job 30868770 (2h, `--max-model-len 8192` + `max_tokens=1000`) — **pending/running**. Should resolve all prior issues.

**Key lessons:**
- vLLM on Fir H100 needs `--enforce-eager` (no torch.compile, saves 2.5 min) and `--limit-mm-per-prompt.image 0 --limit-mm-per-prompt.video 0` (skip multimodal profiling for text-only tasks)
- Server startup takes ~225s with these flags
- Must ensure `--max-model-len` accommodates the full prompt + output tokens
- SSH ControlMaster works via WSL (not native Windows)

### 2. Threat Keyword Scan

Regex-based scan for explicit threat language (death threats, violence incitement, elimination rhetoric, direct threats) across all 11,211 posts.

**Results:** 51 posts flagged (0.5%), but **no true positives**. All matches were false positives — posts *about* violence against trans people (not threats *toward* them), quotes containing threat-adjacent words in non-threat contexts (e.g., "kill themselves" in suicide discussion), or reporting on violence.

**Conclusion:** Explicit threat language is essentially absent from the seedlist data. Anti-trans hostility in this corpus is coded and indirect, not overt threats.

**Output:** `analysis/data/feb2026_threat_scan.parquet`
**Script:** `analysis/scripts/keyword_filtered_feb26_threat_scan.py`

### 3. Haiku Rhetoric Classification

Classified the top 20 trans-related posts per day (by likes) in February using Claude Haiku. Two versions:

**Version 1 — All seeds (including US influencers):**
- 560 posts, cost $0.02
- 66.1% contain anti-trans rhetoric
- Stance: 369 anti-trans / 78 pro-trans / 73 neutral
- Output: `analysis/data/feb2026_daily_top_rhetoric.parquet`

**Version 2 — Canadian seeds only (filtered `us_influencer` from Collection):**
- 560 posts (different top 20/day after filtering 311 US influencer posts from source), cost $0.43
- **54.8% contain anti-trans rhetoric** (down from 66.1%)
- Stance: 307 anti-trans / 150 pro-trans / 102 neutral
- More pro-trans voices surface when US influencers are removed
- Output: `analysis/data/feb2026_daily_top_rhetoric_ca.parquet`

**Classification schema:**
- Anti-trans rhetoric present (yes/no)
- Rhetoric categories (ideology framing, conspiracy, mockery, violence association, identity denial, child protection, predator framing, pathologizing, dehumanization, medical opposition, etc.)
- Tumbler Ridge connection (yes/no)
- Overall stance (anti_trans, pro_trans, neutral, mixed)

**Top rhetoric categories (all seeds version):**
| Category | Posts | % |
|----------|-------|---|
| Ideology framing | 179 | 32.0% |
| Conspiracy | 148 | 26.4% |
| Mockery | 122 | 21.8% |
| Violence association | 122 | 21.8% |
| Identity denial | 107 | 19.1% |
| Child protection | 100 | 17.9% |
| Predator framing | 85 | 15.2% |
| Pathologizing | 71 | 12.7% |
| Dehumanization | 65 | 11.6% |
| Medical opposition | 57 | 10.2% |

**Before/after the shooting (Feb 10):**
- **Before:** 50% anti-trans rate. Dominated by ideology framing (28%), conspiracy (19%), child protection (19%). Violence association only 5%.
- **Week after:** 74% anti-trans rate. Violence association explodes to 49%. Conspiracy doubles to 39%, identity denial triples to 29%, predator framing jumps to 24%.
- **Later (Feb 18-28):** 75% anti-trans rate. Violence association drops to 21% but stays 4x above pre-shooting baseline. Ideology framing rises to 42%.

**Interpretation:** The shooting weaponized existing anti-trans discourse. The same categories were present before, but the incident amplified them and introduced violence association as a major new frame. The baseline shifted upward and never returned to pre-shooting levels.

**Top authors (all seeds, almost all influencers):**
- Buck Angel (22 posts) — mockery, pathologizing, identity denial
- Andy Ngo (17) — violence association, conspiracy, identity denial
- Chris Elston (14) — ideology framing, pathologizing, child protection
- Matt Walsh (11) — violence association, conspiracy, ideology framing
- Nick Sortor (9) — mockery, violence association

Only Rebel News and National Post appeared as news outlets in the top 25.

**Script:** `analysis/scripts/keyword_filtered_feb26_daily_top_rhetoric.py`

### 4. Rhetoric Trend Visualizations

**Static figures (3):**
- Rhetoric trends by post count (3-day rolling avg, top 6 categories + "Other Anti-Trans")
- Rhetoric trends by likes (same structure, engagement-weighted)
- Top authors bar chart + stacked rhetoric profile

**Interactive HTML:**
- Combined chart with 4 vertically stacked panels: post count trendlines → post count bars → likes trendlines → likes bars
- Hover highlights the selected line and dims others in the same panel
- Date picker table at the bottom shows top 5 posts for the selected date (author, platform, text, likes)
- Uses Canadian seeds only

**Figures:**
- `analysis/figures/keyword_filtered_feb26_rhetoric_trends.png`
- `analysis/figures/keyword_filtered_feb26_rhetoric_trends_likes.png`
- `analysis/figures/keyword_filtered_feb26_rhetoric_authors.png`
- `analysis/figures/keyword_filtered_feb26_rhetoric_trends_interactive.html`

**Scripts:**
- `analysis/scripts/keyword_filtered_feb26_rhetoric_trends.py` (static)
- `analysis/scripts/keyword_filtered_feb26_rhetoric_trends_interactive.py` (interactive)

## Commits

- `36b1548` — Add descriptive figures, hostility coding scripts, threat scan, and progress notes (pushed to MEOMcGill/trans_incident)

## Still To Do

- [ ] Pull and analyze HPC hostility coding results once job 30868770 succeeds
- [ ] Investigate Feb 21 engagement spike (8 posts, 82K likes)
- [ ] Deeper analysis of rhetoric categories by demographic variables (platform, seed type, province, party)
- [ ] Compare Haiku rhetoric classification with HPC hostility coding results
- [ ] Rerun rhetoric trends with CA-only data for static figures + author chart
