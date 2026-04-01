# Progress — April 1, 2026

## What We Did

### 1. HPC Hostility Coding — Completed

Job 30868770 (from March 31) timed out after 2h — the sequential client was processing at 0.1 posts/sec (~28h ETA for 11K posts). Rewrote the classification script with async concurrent requests (`AsyncOpenAI`, semaphore-based concurrency of 30). Also filtered to trans/queer posts only (4,313 instead of 11,211).

**Job 30909597 — success:**
- 4,319 posts classified in 44 min (1.4 posts/sec — 14x faster than sequential)
- Server startup: 440s with `--enforce-eager`, `--limit-mm-per-prompt`, `--max-model-len 8192`
- Results: only 21 posts (0.5%) flagged as hostile
- Most flagged posts were false positives — the Qwen hostility framework codes hostile *language* present in quotes/reports without distinguishing attribution (e.g., a journalist quoting anti-trans rhetoric gets flagged)
- Exported 21 hostile posts to CSV for manual review

**Key difference from Haiku classification:** Haiku found 55% anti-trans rhetoric using a broader "negative rhetoric" definition. Qwen's hostility framework (14 hallmarks, severity 0-3, conservative coding) has a much higher bar — it measures explicit hostile speech acts, not rhetorical framing.

**Output:** `analysis/data/hostility_coding_results.parquet`, `analysis/data/hostility_coding_hostile_posts.csv`
**Script:** `analysis/scripts/keyword_filtered_feb26_hostility_coding.py` (async version)

### 2. Figure Updates

**Static figures switched to CA-only data:**
- All three static figures (trends, likes, authors) now use `feb2026_daily_top_rhetoric_ca.parquet` instead of all-seeds
- Top authors now Canadian: Rebel News, Chris Elston, National Post, Kat Kanada (instead of Buck Angel, Matt Walsh, Andy Ngo)

**Likes figure (`keyword_filtered_feb26_rhetoric_trends_likes.png`) updates:**
- Title changed: "Negative Rhetoric" instead of "Anti-Trans Rhetoric", "Top 20 Posts Daily about Trans/Queer Topics"
- Swapped panel order: bar chart on top (shorter), trendlines below (taller)
- Added event annotations: "Hair Salon Fined" (Feb 18), "OpenAI Letter" (Feb 21) with vertical dashed lines
- Moved title to `suptitle` (above bar chart, not sandwiched between panels)
- Increased font sizes throughout
- Moved "Tumblr Ridge shooting" annotation to y=60000 to avoid legend overlap

**Interactive HTML figure updates:**
- Legend moved up to avoid overlapping annotation text
- Panel subtitles moved down to avoid chart title overlap
- Added Feb 18 and Feb 21 event annotations with arrows and vertical lines across all 4 panels

**Maintype chart (`keyword_filtered_feb26_maintype_by_type.png`):**
- Limited timeframe to Feb 10 onward
- Added "Feb 10–28, 2026" as figure caption

### 3. Interactive Presentation

Built an HTML slide deck from the incident report PDF (19 slides + April Fools bonus).

**Features:**
- Staggered entrance animations for text, cards, list items
- Animated number counters (count up from 0)
- Interactive Plotly charts for Fig 1 (daily volume) and Fig 3 (rhetoric engagement trends)
  - Fig 3 has hover-highlight (dims other lines), event annotations, dual-panel layout
- Static PNGs for Fig 2 (maintype), Fig 4 (gender ideology), Fig 5 (political expression) — Plotly versions looked bad
- Fig 4 and 5 in two-column layout (text left, vertical figure right)
- Hover effects on takeaway cards, stat cards, category list items
- Section divider slides with gradient text
- April Fools slide (Mathieu's `april_fools.html`) as lazy-loaded iframe on last slide

**Content updates from latest report version:**
- Threats slide: 0 in Tumbler Ridge seedlist, 9 found in Charlie Kirk dataset (a third deleted, all low engagement)
- Implications replaced with 3 specific recommendations (rapid response protocols, platform identity fraud detection, research on trans civic participation)
- Expanded limitations (posts vs comments, additional note)
- Added "A note on AI" disclosure

**Output:** `analysis/presentation.html`
**Generator script:** `analysis/scripts/generate_presentation.py`

### 4. Pulled Mathieu's Survey Figures

Incorporated `figures/gender_ideology_belief.png` (Fig 4) and `figures/combined_expression.png` (Fig 5) into the presentation after Mathieu pushed them.

## Commits

- `62ca7ab` — Add Haiku rhetoric classification, async HPC hostility coding, and figure updates
- `7af480c` — Add interactive presentation, HPC hostility coding results, and presentation generator
- `2f686b3` — Add April Fools slide, update threats/recommendations/limitations from report

## Still To Do

- [ ] Investigate Feb 21 engagement spike (8 posts, 82K likes — "OpenAI Letter")
- [ ] Compare Haiku rhetoric classification with Qwen hostility coding results (different thresholds, need alignment)
- [ ] Deeper analysis of rhetoric categories by demographic variables (platform, seed type, province, party)
- [ ] Validate Haiku classification against human coders (sample)
