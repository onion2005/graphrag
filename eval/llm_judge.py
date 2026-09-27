"""
LLM-as-judge evaluation: have an LLM grade the relevance of each
retrieved symbol to the query, independent of the golden dataset.

This catches:
- False negatives in golden set (relevant symbols it didn't list)
- False positives in golden set (symbols it listed but aren't useful)
- Ranking quality from a semantic perspective
"""
import json
import time
from collections import defaultdict

import openai

import config
from retrieval.hybrid import vector_only, hybrid_retrieve
from eval.metrics import ndcg_at_k, precision_at_k, recall_at_k, mrr

MODES = {
    "vector_only": {"func": vector_only, "kwargs": {}},
    "vector_ast_graph": {"func": hybrid_retrieve, "kwargs": {"graph_type": "baseline"}},
    "vector_graph_llm": {"func": hybrid_retrieve, "kwargs": {"graph_type": "llm"}},
    "vector_graph_ast_llm": {"func": hybrid_retrieve, "kwargs": {"graph_type": "both"}},
}

JUDGE_PROMPT = """\
You are evaluating a code retrieval system. Given a query and a list of retrieved code symbols, judge how relevant each symbol is to the query.

Query: {query}

Retrieved symbols (ranked by the system):
{symbols_text}

For each symbol, assign a relevance grade:
- 3: Essential — directly answers the query
- 2: Important — closely related, useful context
- 1: Peripheral — tangentially related
- 0: Irrelevant — not useful for this query

Respond with a JSON array of objects, one per symbol, in the same order:
[{{"name": "<symbol name>", "relevance": <0-3>, "reason": "<brief reason>"}}]
"""

MAX_SYMBOLS_PER_CALL = 25


def _format_symbol(result: dict) -> str:
    """Format a retrieved result for the judge prompt."""
    doc = result.get("document", result.get("docstring", ""))
    if doc and len(doc) > 200:
        doc = doc[:200] + "..."
    return f"- {result['type']}: {result['name']} ({result['file']})\n  {doc}"


def judge_results(
    query: str,
    retrieved: list[dict],
    client: openai.OpenAI,
) -> list[dict]:
    """Have the LLM judge relevance of each retrieved symbol."""
    if not retrieved:
        return []

    symbols_to_judge = retrieved[:MAX_SYMBOLS_PER_CALL]
    symbols_text = "\n".join(
        f"{i+1}. {_format_symbol(r)}" for i, r in enumerate(symbols_to_judge)
    )

    prompt = JUDGE_PROMPT.format(query=query, symbols_text=symbols_text)

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        judgments = json.loads(text)
    except json.JSONDecodeError:
        print(f"  Failed to parse judge response for: {query[:50]}")
        return []

    # Align judgments with retrieved results
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


def run_llm_judge(
    queries: list[dict] = None,
    golden_path: str = "eval/golden_dataset.json",
    top_k: int = 10,
    output_path: str = "eval/llm_judge_results.json",
) -> dict:
    """Run LLM judge evaluation across all queries and modes."""
    if queries is None:
        with open(golden_path) as f:
            dataset = json.load(f)
        queries = [{"query": q["query"], "id": q["id"], "category": q["category"]}
                   for q in dataset["queries"]]

    client = openai.OpenAI(
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
    )

    total_calls = len(queries) * len(MODES)
    print(f"LLM Judge: {len(queries)} queries × {len(MODES)} modes = {total_calls} judge calls", flush=True)

    # Warmup retrieval
    print("Warmup...", flush=True)
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
                kwargs["top_k"] = top_k
            else:
                kwargs["vector_top_k"] = top_k

            # Retry with backoff for Neo4j connection drops
            retrieved = None
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

            judgments = judge_results(query, retrieved, client)
            call_count += 1

            if call_count % 20 == 0:
                print(f"    ({call_count}/{total_calls} judge calls done)", flush=True)

            time.sleep(0.5)  # breathing room for Neo4j

            # Compute metrics from judge grades
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
            "judge_model": config.LLM_MODEL,
            "top_k": top_k,
            "query_count": len(queries),
        },
        "per_query": per_query,
    }

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    return results


def print_report(results_path: str = "eval/llm_judge_results.json"):
    """Print LLM judge report."""
    with open(results_path) as f:
        results = json.load(f)

    per_query = results["per_query"]
    n = len(per_query)

    mode_labels = {
        "vector_only": "Vector Only",
        "vector_ast_graph": "Vector + AST Graph",
        "vector_graph_llm": "Vector + Graph (LLM)",
        "vector_graph_ast_llm": "Vector + Graph (AST+LLM)",
    }

    print("=" * 70)
    print("  LLM-AS-JUDGE EVALUATION")
    print("=" * 70)

    # Aggregate
    metrics = ["avg_relevance", "relevant_count", "precision_at_10", "ndcg_at_10", "ndcg_at_20", "mrr"]
    labels = {"avg_relevance": "AvgRel", "relevant_count": "Rel#", "precision_at_10": "P@10",
              "ndcg_at_10": "nDCG@10", "ndcg_at_20": "nDCG@20", "mrr": "MRR"}

    header = f"| {'Mode':<28s} |"
    for m in metrics:
        header += f" {labels[m]:>7s} |"
    sep = "|" + "-" * 30 + "|" + ("-" * 9 + "|") * len(metrics)

    print(f"\n{header}")
    print(sep)

    for mode in mode_labels:
        row = f"| {mode_labels[mode]:<28s} |"
        for m in metrics:
            avg = sum(q["modes"][mode][m] for q in per_query) / n
            row += f" {avg:>7.3f} |"
        print(row)

    # Per-category
    by_cat = defaultdict(list)
    for q in per_query:
        by_cat[q["category"]].append(q)

    for cat, queries in sorted(by_cat.items()):
        cn = len(queries)
        print(f"\n--- {cat} ---")
        print(header)
        print(sep)
        for mode in mode_labels:
            row = f"| {mode_labels[mode]:<28s} |"
            for m in metrics:
                avg = sum(q["modes"][mode][m] for q in queries) / cn
                row += f" {avg:>7.3f} |"
            print(row)

    # Relevance distribution
    print("\n--- Relevance Grade Distribution ---")
    print(f"| {'Mode':<28s} | {'Grade 0':>7s} | {'Grade 1':>7s} | {'Grade 2':>7s} | {'Grade 3':>7s} |")
    print(f"|{'-'*30}|{'-'*9}|{'-'*9}|{'-'*9}|{'-'*9}|")
    for mode in mode_labels:
        counts = [0, 0, 0, 0]
        total = 0
        for q in per_query:
            for j in q["modes"][mode]["judgments"]:
                grade = j["judge_relevance"]
                if 0 <= grade <= 3:
                    counts[grade] += 1
                    total += 1
        row = f"| {mode_labels[mode]:<28s} |"
        for c in counts:
            row += f" {c/total*100 if total else 0:>5.1f}% |"
        print(row)


if __name__ == "__main__":
    run_llm_judge()
