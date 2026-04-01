"""
Classify anti-trans rhetoric in the top 20 trans-related posts per day
in February 2026 using Claude Haiku.

Keeps all original columns so results can be linked back to demographic variables.

Input:  analysis/data/feb2026_incident_trans_union_keywords.parquet
Output: analysis/data/feb2026_daily_top_rhetoric.parquet
"""

import json
import os
import sys
import time
import pandas as pd
from anthropic import Anthropic

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = "analysis/data/feb2026_incident_trans_union_keywords.parquet"
OUTPUT = "analysis/data/feb2026_daily_top_rhetoric_ca.parquet"
CHECKPOINT = "analysis/data/feb2026_daily_top_rhetoric_ca_checkpoint.parquet"

SYSTEM_PROMPT = """You are a content analyst studying public discourse about trans and queer people in Canadian social media during February 2026. Your task is to classify social media posts for anti-trans rhetoric.

For each post, provide a JSON object with these fields:

1. "contains_anti_trans_rhetoric": true/false — Does the post contain rhetoric that attacks, delegitimizes, dehumanizes, or marginalizes trans/queer people?

2. "rhetoric_categories": list of strings — Which categories of anti-trans rhetoric are present? Use as many as apply from this list, or add new ones if needed:
   - "identity_denial" — Denying trans identities (e.g., "trans women are men", misgendering)
   - "pathologizing" — Framing being trans as mental illness, disorder, or delusion
   - "predator_framing" — Portraying trans people as predators, groomers, or threats to children
   - "ideology_framing" — Dismissing trans identity as ideology, trend, or social contagion
   - "child_protection" — Using child safety rhetoric to oppose trans rights/existence
   - "sports_exclusion" — Framing trans women in sports as unfair/cheating
   - "bathroom_panic" — Framing trans people in gendered spaces as dangerous
   - "medical_opposition" — Opposing gender-affirming care, framing it as mutilation
   - "erasure_of_women" — Claiming trans rights erase or harm cisgender women
   - "dehumanization" — Language that dehumanizes trans people
   - "mockery" — Ridiculing trans people or identities
   - "conspiracy" — Claiming trans movement is driven by hidden agenda/lobby
   - "violence_association" — Associating trans people with violence or criminality
   - "elimination_rhetoric" — Calling for removal/eradication of trans people
   - "other" — Describe in rhetoric_description

3. "rhetoric_description": string — Brief description of the specific rhetoric used (1-2 sentences).

4. "is_tumblr_ridge_connected": true/false — Is the post related to or referencing the Tumblr Ridge shooting (Feb 10, 2026)?

5. "stance": one of "anti_trans", "pro_trans", "neutral", "mixed" — Overall stance of the post toward trans people.

Respond with ONLY the JSON object, no other text."""

USER_TEMPLATE = """Classify this social media post:

Platform: {platform}
Date: {date}
Author type: {seed_type}
Post text:
{text}"""

TOP_N = 20


def classify_post(client, row):
    """Send a single post to Haiku for classification."""
    text = str(row["text_all"] or "")[:3000]
    if not text.strip():
        return None

    user_msg = USER_TEMPLATE.format(
        platform=row["platform"],
        date=str(row["date"])[:10],
        seed_type=row.get("seed_MainType", "unknown"),
        text=text,
    )

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()
            # Parse JSON — handle markdown code blocks
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(raw)
            result["raw_response"] = raw
            result["input_tokens"] = response.usage.input_tokens
            result["output_tokens"] = response.usage.output_tokens
            return result
        except json.JSONDecodeError:
            return {"raw_response": raw, "contains_anti_trans_rhetoric": None, "parse_error": True}
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    return {"raw_response": "FAILED", "contains_anti_trans_rhetoric": None}


def main():
    client = Anthropic()

    df = pd.read_parquet(DATA)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    print(f"Loaded {len(df)} posts")

    # Filter out US influencers
    us_mask = df["seed_Collection"].str.contains("us_influencer", na=False)
    df = df[~us_mask]
    print(f"After removing US influencers: {len(df)}")

    # Filter to trans posts (is_trans or is_both)
    trans = df[df["is_trans"] | df["is_both"]].copy()
    print(f"Trans/both posts: {len(trans)}")

    # Top 20 per day by likes
    trans["day"] = trans["date"].dt.date
    top_daily = (
        trans.sort_values("like_count", ascending=False)
        .groupby("day")
        .head(TOP_N)
        .sort_values(["day", "like_count"], ascending=[True, False])
    )
    print(f"Top {TOP_N}/day selection: {len(top_daily)} posts across {top_daily['day'].nunique()} days")

    # Check for checkpoint
    completed_ids = set()
    results = []
    if os.path.exists(CHECKPOINT):
        checkpoint = pd.read_parquet(CHECKPOINT)
        completed_ids = set(checkpoint["id"].tolist())
        results = checkpoint.to_dict("records")
        print(f"Resuming from checkpoint: {len(completed_ids)} already done")

    remaining = top_daily[~top_daily["id"].isin(completed_ids)]
    print(f"Remaining: {len(remaining)}")

    if len(remaining) == 0:
        print("All posts already classified")
        return

    total_input = 0
    total_output = 0
    t0 = time.time()

    for i, (_, row) in enumerate(remaining.iterrows()):
        result = classify_post(client, row)
        if result is None:
            continue

        # Merge classification with all original columns
        record = row.to_dict()
        record.pop("day", None)
        record.update({f"haiku_{k}": v for k, v in result.items()})
        results.append(record)

        total_input += result.get("input_tokens", 0)
        total_output += result.get("output_tokens", 0)

        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            cost = (total_input * 0.80 + total_output * 4.00) / 1_000_000
            print(f"  {i + 1}/{len(remaining)} ({rate:.1f}/sec) — ${cost:.2f} so far")

            # Checkpoint
            pd.DataFrame(results).to_parquet(CHECKPOINT, index=False)

    # Final save
    results_df = pd.DataFrame(results)
    results_df.to_parquet(OUTPUT, index=False)
    results_df.to_parquet(CHECKPOINT, index=False)

    elapsed = time.time() - t0
    cost = (total_input * 0.80 + total_output * 4.00) / 1_000_000
    print(f"\nDone. {len(results)} posts classified in {elapsed / 60:.1f} min")
    print(f"Total cost: ${cost:.2f} ({total_input:,} input + {total_output:,} output tokens)")
    print(f"Saved to {OUTPUT}")

    # Quick summary
    if "haiku_contains_anti_trans_rhetoric" in results_df.columns:
        anti = results_df["haiku_contains_anti_trans_rhetoric"].sum()
        print(f"\nAnti-trans rhetoric: {anti}/{len(results_df)} ({100*anti/len(results_df):.1f}%)")

        # Stance breakdown
        if "haiku_stance" in results_df.columns:
            print("\nStance:")
            print(results_df["haiku_stance"].value_counts().to_string())


if __name__ == "__main__":
    main()
