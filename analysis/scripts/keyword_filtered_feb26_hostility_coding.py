"""
Classify posts for hostile speech toward trans and queer people using
Qwen3.5-27B-FP8 via vLLM's OpenAI-compatible API.

Input:  $HOME/scratch/trans_incident/data/feb2026_incident_trans_union_keywords.parquet
Output: $HOME/scratch/trans_incident/output/hostility_coding_results.parquet

Supports checkpointing — safe to resume after interruption.
"""

import argparse
import json
import os
import re
import time
import pandas as pd
from openai import OpenAI
from prompt_hostile_speech_JR import SYSTEM_PROMPT, TASK_PROMPT_CODING

TARGET_GROUP = "trans and queer people"

HALLMARK_NAMES = [
    "Elimination Language",
    "Dehumanization",
    "Harm Celebration",
    "Benevolent Justification",
    "Threat Construction",
    "Identity Erasure",
    "Atrocity Denial",
    "Economic Coercion",
    "Collective Attribution",
    "Hierarchical Positioning",
    "Vilification",
    "Conspiratorial Attribution",
    "Humiliation",
    "Other Hostility",
]


def parse_coding_response(text):
    """Parse the LLM coding response into structured fields."""
    result = {
        "hostile_language_present": None,
        "group_referenced": None,
        "raw_response": text,
    }
    for h in HALLMARK_NAMES:
        result[f"h_{h.lower().replace(' ', '_')}"] = 0

    # Hostile language present
    match = re.search(r"\*\*Hostile Language Present:\*\*\s*(Yes|No)", text, re.IGNORECASE)
    if match:
        result["hostile_language_present"] = match.group(1).strip().lower() == "yes"

    # Group referenced
    match = re.search(r"\*\*Group Referenced:\*\*\s*(.+)", text)
    if match:
        result["group_referenced"] = match.group(1).strip()

    # Hallmark scores
    for h in HALLMARK_NAMES:
        pattern = rf"{re.escape(h)}[:\s]*\[?(\d)\]?"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[f"h_{h.lower().replace(' ', '_')}"] = int(match.group(1))

    return result


def classify_post(client, model, post_text, post_id, max_retries=3):
    """Send a single post through the coding prompt."""
    user_prompt = TASK_PROMPT_CODING.replace(
        "[INPUT_GROUP]", TARGET_GROUP
    ).replace(
        "[INPUT_EXCERPT]", post_text[:4000]  # truncate very long posts
    )

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1500,
                temperature=0.1,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            return parse_coding_response(response.choices[0].message.content)
        except Exception as e:
            print(f"  Post {post_id} attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return {"raw_response": f"FAILED after {max_retries} attempts", "hostile_language_present": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8197)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--batch-size", type=int, default=50, help="Save checkpoint every N posts")
    args = parser.parse_args()

    scratch = os.path.join(os.environ["HOME"], "scratch", "trans_incident")
    data_path = os.path.join(scratch, "data", "feb2026_incident_trans_union_keywords.parquet")
    output_dir = os.path.join(scratch, "output")
    output_path = os.path.join(output_dir, "hostility_coding_results.parquet")
    checkpoint_path = os.path.join(output_dir, "hostility_coding_checkpoint.parquet")

    os.makedirs(output_dir, exist_ok=True)

    # Load data
    df = pd.read_parquet(data_path)
    print(f"Loaded {len(df)} posts")

    # Check for checkpoint
    completed_ids = set()
    results = []
    if os.path.exists(checkpoint_path):
        checkpoint = pd.read_parquet(checkpoint_path)
        completed_ids = set(checkpoint["id"].tolist())
        results = checkpoint.to_dict("records")
        print(f"Resuming from checkpoint: {len(completed_ids)} already done")

    # Filter to remaining
    remaining = df[~df["id"].isin(completed_ids)]
    print(f"Posts remaining: {len(remaining)}")

    if len(remaining) == 0:
        print("All posts already classified")
        if results:
            pd.DataFrame(results).to_parquet(output_path, index=False)
            print(f"Final results saved to {output_path}")
        return

    client = OpenAI(base_url=f"http://localhost:{args.port}/v1", api_key="not-needed")

    t0 = time.time()
    for i, (_, row) in enumerate(remaining.iterrows()):
        post_text = str(row.get("text", "") or row.get("search_text", ""))
        if not post_text.strip():
            continue

        result = classify_post(client, args.model, post_text, row["id"])
        result["id"] = row["id"]
        result["date"] = row["date"]
        result["platform"] = row["platform"]
        result["seed_SeedName"] = row.get("seed_SeedName", "")
        result["seed_MainType"] = row.get("seed_MainType", "")
        results.append(result)

        # Progress
        if (i + 1) % 10 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
            print(f"  {i + 1}/{len(remaining)} ({rate:.1f} posts/sec, ETA: {eta / 60:.0f} min)")

        # Checkpoint
        if (i + 1) % args.batch_size == 0:
            pd.DataFrame(results).to_parquet(checkpoint_path, index=False)
            print(f"  Checkpoint saved ({len(results)} total)")

    # Final save
    results_df = pd.DataFrame(results)
    results_df.to_parquet(output_path, index=False)
    results_df.to_parquet(checkpoint_path, index=False)

    elapsed = time.time() - t0
    print(f"\nDone. {len(results)} posts classified in {elapsed / 60:.1f} min")
    print(f"Results saved to {output_path}")

    # Quick summary
    if "hostile_language_present" in results_df.columns:
        hostile = results_df["hostile_language_present"].sum()
        print(f"Hostile posts found: {hostile} / {len(results_df)} ({100 * hostile / len(results_df):.1f}%)")


if __name__ == "__main__":
    main()
