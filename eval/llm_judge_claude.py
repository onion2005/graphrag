"""
Run LLM-as-judge evaluation using Claude Haiku for comparison with self-hosted model.
Uses the same queries and retrieval results, only swaps the judge LLM.
"""
import json
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from eval.llm_judge import (
    _format_symbol,
    JUDGE_PROMPT,
    MAX_SYMBOLS_PER_CALL,
    MODES,
)
from eval.metrics import ndcg_at_k, precision_at_k, mrr
from retrieval.hybrid import vector_only, hybrid_retrieve

load_dotenv()

CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def judge_results_claude(
    query: str,
    retrieved: list[dict],
    client: anthropic.Anthropic,
) -> list[dict]:
    """Have Claude judge relevance of each retrieved symbol."""
    if not retrieved:
        return []

    symbols_to_judge = retrieved[:MAX_SYMBOLS_PER_CALL]
    symbols_text = "\n".join(
        f"{i+1}. {_format_symbol(r)}" for i, r in enumerate(symbols_to_judge)
    )

    prompt = JUDGE_PROMPT.format(query=query, symbols_text=symbols_text)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        judgments = json.loads(text)
    except json.JSONDecodeError:
        print(f"  Failed to parse Claude response for: {query[:50]}")
        return []

    scored = []
    for i, r in enumerate(symbols_to_judge):
        if i < len(judgments):
            j = judgments[i]
            scored.append({
                "id": r["id"],
                "name": r["name"],
                "file": r.get("file", ""),
                "type": r.get("type", ""),
                "source": r.get("source", ""),
                "system_score": r.get("score", 0),
                "judge_relevance": j.get("relevance", 0),
                "judge_reason": j.get("reason", ""),
            })
        else:
            scored.append({
                "id": r["id"],
                "name": r["name"],
                "file": r.get("file", ""),
                "type": r.get("type", ""),
                "source": r.get("source", ""),
                "system_score": r.get("score", 0),
                "judge_relevance": 0,
                "judge_reason": "not judged",
            })

    return scored


def run():
    # Load same queries used by Qwen judge
    with open("eval/golden_dataset.json") as f:
        dataset = json.load(f)
    queries = [{"query": q["query"], "id": q["id"], "category": q["category"]}
               for q in dataset["queries"]]

    client = anthropic.Anthropic()

    total_calls = len(queries) * len(MODES)
    print(f"Claude Judge: {len(queries)} queries x {len(MODES)} modes = {total_calls} calls", flush=True)

    # Warmup
    vector_only("warmup", top_k=1)

    per_query = []
    call_count = 0

    for i, q in enumerate(queries):
        query = q["query"]
        print(f"  [{i+1}/{len(queries)}] {query[:60]}...", flush=True)

        mode_results = {}
        for mode_name, mode_config in MODES.items():
            func = mode_config["func"]
            kwargs = {**mode_config["kwargs"]}
            if func == vector_only:
                kwargs["top_k"] = 10
            else:
                kwargs["vector_top_k"] = 10

            for attempt in range(3):
                try:
                    retrieved = func(query, **kwargs)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"    Retry {attempt+1} for {mode_name}: {e}", flush=True)
                        time.sleep(5)
                    else:
                        print(f"    FAILED {mode_name}: {e}", flush=True)
                        retrieved = []

            judgments = judge_results_claude(query, retrieved, client)
            call_count += 1

            if call_count % 20 == 0:
                print(f"    ({call_count}/{total_calls} calls done)", flush=True)

            time.sleep(0.3)

            retrieved_ids = [j["id"] for j in judgments]
            relevance_map = {j["id"]: j["judge_relevance"] for j in judgments}
            relevant_ids = {jid for jid, grade in relevance_map.items() if grade >= 2}

            avg_relevance = (sum(j["judge_relevance"] for j in judgments) / len(judgments)) if judgments else 0

            mode_results[mode_name] = {
                "judgments": judgments,
                "avg_relevance": round(avg_relevance, 3),
                "relevant_count": len(relevant_ids),
                "result_count": len(judgments),
                "precision_at_5": precision_at_k(retrieved_ids, relevant_ids, 5),
                "precision_at_10": precision_at_k(retrieved_ids, relevant_ids, 10),
                "ndcg_at_10": ndcg_at_k(retrieved_ids, relevance_map, 10),
                "ndcg_at_20": ndcg_at_k(retrieved_ids, relevance_map, 20),
                "mrr": mrr(retrieved_ids, relevant_ids),
            }

        per_query.append({
            "id": q["id"],
            "query": query,
            "category": q.get("category", ""),
            "modes": mode_results,
        })

    results = {
        "config": {
            "judge_model": CLAUDE_MODEL,
            "top_k": 10,
            "query_count": len(queries),
        },
        "per_query": per_query,
    }

    output_path = "eval/llm_judge_results_claude.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    return results


if __name__ == "__main__":
    run()
