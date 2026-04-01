"""
Classify posts for hostile speech toward trans and queer people using
Qwen3.5-27B-FP8 via vLLM's OpenAI-compatible API.

Input:  $HOME/scratch/trans_incident/data/feb2026_incident_trans_union_keywords.parquet
Output: $HOME/scratch/trans_incident/output/hostility_coding_results.parquet

Supports checkpointing and async concurrent requests for throughput.
"""

import argparse
import asyncio
import os
import re
import time
import pandas as pd
from openai import AsyncOpenAI
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

    match = re.search(r"\*\*Hostile Language Present:\*\*\s*(Yes|No)", text, re.IGNORECASE)
    if match:
        result["hostile_language_present"] = match.group(1).strip().lower() == "yes"

    match = re.search(r"\*\*Group Referenced:\*\*\s*(.+)", text)
    if match:
        result["group_referenced"] = match.group(1).strip()

    for h in HALLMARK_NAMES:
        pattern = rf"{re.escape(h)}[:\s]*\[?(\d)\]?"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[f"h_{h.lower().replace(' ', '_')}"] = int(match.group(1))

    return result


async def classify_post(client, model, post_text, post_id, semaphore, max_retries=3):
    """Send a single post through the coding prompt with concurrency control."""
    user_prompt = TASK_PROMPT_CODING.replace(
        "[INPUT_GROUP]", TARGET_GROUP
    ).replace(
        "[INPUT_EXCERPT]", post_text[:4000]
    )

    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=1000,
                    temperature=0.1,
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
                return parse_coding_response(response.choices[0].message.content)
            except Exception as e:
                print(f"  Post {post_id} attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
    return {"raw_response": f"FAILED after {max_retries} attempts", "hostile_language_present": None}


async def process_batch(client, model, rows, semaphore):
    """Process a batch of rows concurrently."""
    tasks = []
    for _, row in rows.iterrows():
        post_text = str(row.get("text", "") or row.get("search_text", ""))
        if not post_text.strip():
            continue
        task = classify_post(client, model, post_text, row["id"], semaphore)
        tasks.append((row, task))

    results = []
    for row, task in tasks:
        result = await task
        result["id"] = row["id"]
        result["date"] = row["date"]
        result["platform"] = row["platform"]
        result["seed_SeedName"] = row.get("seed_SeedName", "")
        result["seed_MainType"] = row.get("seed_MainType", "")
        results.append(result)
    return results


async def main_async(args):
    scratch = os.path.join(os.environ["HOME"], "scratch", "trans_incident")
    data_path = os.path.join(scratch, "data", "feb2026_incident_trans_union_keywords.parquet")
    output_dir = os.path.join(scratch, "output")
    output_path = os.path.join(output_dir, "hostility_coding_results.parquet")
    checkpoint_path = os.path.join(output_dir, "hostility_coding_checkpoint.parquet")

    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_parquet(data_path)
    print(f"Loaded {len(df)} posts")

    # Filter to trans/queer posts only (includes "both" posts)
    df = df[df["is_trans"] == True].reset_index(drop=True)
    print(f"Filtered to {len(df)} trans/queer posts")

    # Resume from checkpoint
    completed_ids = set()
    results = []
    if os.path.exists(checkpoint_path):
        checkpoint = pd.read_parquet(checkpoint_path)
        completed_ids = set(checkpoint["id"].tolist())
        results = checkpoint.to_dict("records")
        print(f"Resuming from checkpoint: {len(completed_ids)} already done")

    remaining = df[~df["id"].isin(completed_ids)]
    print(f"Posts remaining: {len(remaining)}")

    if len(remaining) == 0:
        print("All posts already classified")
        if results:
            pd.DataFrame(results).to_parquet(output_path, index=False)
        return

    client = AsyncOpenAI(base_url=f"http://localhost:{args.port}/v1", api_key="not-needed")
    semaphore = asyncio.Semaphore(args.concurrency)

    t0 = time.time()
    checkpoint_interval = args.checkpoint_every
    batch_size = args.concurrency * 2  # feed enough to keep the pipeline full

    # Process in batches for checkpointing
    total_remaining = len(remaining)
    processed = 0

    for batch_start in range(0, total_remaining, batch_size):
        batch_end = min(batch_start + batch_size, total_remaining)
        batch = remaining.iloc[batch_start:batch_end]

        # Fire all requests in the batch concurrently (semaphore limits in-flight)
        tasks = []
        row_list = []
        for _, row in batch.iterrows():
            post_text = str(row.get("text", "") or row.get("search_text", ""))
            if not post_text.strip():
                continue
            row_list.append(row)
            tasks.append(classify_post(client, model=args.model, post_text=post_text,
                                       post_id=row["id"], semaphore=semaphore))

        batch_results = await asyncio.gather(*tasks)

        for row, result in zip(row_list, batch_results):
            result["id"] = row["id"]
            result["date"] = row["date"]
            result["platform"] = row["platform"]
            result["seed_SeedName"] = row.get("seed_SeedName", "")
            result["seed_MainType"] = row.get("seed_MainType", "")
            results.append(result)

        processed += len(row_list)
        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total_remaining - processed) / rate if rate > 0 else 0
        print(f"  {processed}/{total_remaining} ({rate:.1f} posts/sec, ETA: {eta / 60:.0f} min)")

        # Checkpoint periodically
        if processed % checkpoint_interval < batch_size:
            pd.DataFrame(results).to_parquet(checkpoint_path, index=False)
            print(f"  Checkpoint saved ({len(results)} total)")

    # Final save
    results_df = pd.DataFrame(results)
    results_df.to_parquet(output_path, index=False)
    results_df.to_parquet(checkpoint_path, index=False)

    elapsed = time.time() - t0
    print(f"\nDone. {len(results)} posts classified in {elapsed / 60:.1f} min")
    print(f"Results saved to {output_path}")

    if "hostile_language_present" in results_df.columns:
        hostile = results_df["hostile_language_present"].sum()
        print(f"Hostile posts found: {hostile} / {len(results_df)} ({100 * hostile / len(results_df):.1f}%)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8197)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--concurrency", type=int, default=30,
                        help="Max concurrent requests to vLLM")
    parser.add_argument("--checkpoint-every", type=int, default=200,
                        help="Save checkpoint every N posts")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
