# Progress — March 30, 2026

## Project Context

Group incident report (team of 3) on the Tumblr Ridge shooting (Feb 10, 2026) and trans panic narratives.

- **Task 1 (Saewon):** Identify threats and hate speech targeting queer/trans people
- **Task 2:** Narrative phases around trans people post-incident
- **Task 3:** Survey data on trans people's comfort voicing political opinions

## What We Did

### 1. Keyword Filtering

Filtered Feb 2026 seedlist data (555K posts from Canadian politicians, media, influencers) for posts related to the incident and trans/queer topics.

**Keywords used:**
- Incident: tumbler ridge, jesse van rootselaar, rootselaar, jesse strang
- Trans/queer: transgender, trans, lgbtq, queer, gender identity, transphob, etc. (with leetspeak-aware regex)

**Results:**
- 7,512 incident posts (mostly Twitter 5.2K, Bluesky 1K)
- 4,313 trans/queer posts (mostly Twitter 3.3K)
- 614 posts mentioning both
- 11,211 total union

**Output:** `analysis/data/feb2026_incident_trans_union_keywords.parquet`
**Script:** `analysis/scripts/feb2026_incident_trans_union_keywords.py`

### 2. Descriptive Analysis

Generated 10 figures breaking down the filtered posts by platform, seed type, province, gender, age, language, party, and engagement (likes only — other metrics not consistent across platforms).

**Key findings:**
- Massive spike on Feb 11 (day after shooting), rapid decay
- Twitter dominates; Bluesky notable for incident-only posts
- Influencers (especially commentators) drive most "both" posts; news outlets rarely link incident to trans topics
- BC and Ontario top provinces
- NDP and PPC overrepresented in intersection posts
- "Both" posts have high shares/views but low likes — outrage/controversy pattern
- Second engagement spike on Feb 21 (8 posts, 82K likes) — not yet investigated

**Figures:** `analysis/figures/keyword_filtered_feb26_*.png`
**Script:** `analysis/scripts/keywords_filtered_feb2026_descriptives.py`

### 3. HPC Setup (In Progress)

Setting up Alliance Canada Fir cluster for LLM-based hostility coding.

**Done:**
- Created SSH key and uploaded to CCDB
- SSH config for fir/nibi/rorqual (no ControlMaster — doesn't work on Windows)
- Created `~/.hpc.env` config
- Successfully connected to Fir via Git Bash
- Wrote hostility coding script using the `prompt_hostile_speech_JR.py` framework (TASK_PROMPT_CODING, 14 hallmarks, target group: "trans and queer people")
- Wrote SLURM job script for Qwen3.5-27B-FP8 on Fir H100

**Not done yet:**
- Create directories on Fir: `ssh fir "mkdir -p ~/scratch/trans_incident/data ~/scratch/trans_incident/scripts ~/scratch/trans_incident/output"`
- Push data and scripts to Fir via scp
- Set up Python venv (`venv_qwen35`) with vLLM on Fir
- Download Qwen3.5-27B-FP8 weights to Fir
- Submit the SLURM job

**Scripts ready locally:**
- `analysis/scripts/keyword_filtered_feb26_hostility_coding.py` — classification client
- `analysis/scripts/keyword_filtered_feb26_hostility_coding.sh` — SLURM job script

## Commits

- `545f8f6` — Add keyword-filtered dataset and script (pushed to MEOMcGill/trans_incident)
