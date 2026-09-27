"""
Cross-repo evaluation runner.
Tests whether cross-repo LLM edges improve retrieval over vector-only and AST-only.
"""
import json
import time

from retrieval.hybrid import vector_only, hybrid_retrieve
from eval.runner import load_golden_dataset, resolve_ids
from eval.metrics import precision_at_k, recall_at_k, mrr, ndcg_at_k, total_recall

MODES = {
    "vector_only": {"func": vector_only, "kwargs": {}},
    "vector_ast": {"func": hybrid_retrieve, "kwargs": {"graph_type": "baseline"}},
    "vector_cross_repo": {"func": hybrid_retrieve, "kwargs": {"graph_type": "cross_repo"}},
    "vector_ast_cross": {"func": hybrid_retrieve, "kwargs": {"graph_type": "ast_cross"}},
}


def evaluate_query(query_entry, top_k=10, relevance_threshold=2):
    query = query_entry["query"]
    relevance_map = resolve_ids(query_entry["expected_symbols"])
    relevant_ids = {rid for rid, grade in relevance_map.items() if grade >= relevance_threshold}

    results = {}
    for mode_name, mode_config in MODES.items():
        func = mode_config["func"]
        kwargs = {**mode_config["kwargs"]}

        if func == vector_only:
            kwargs["top_k"] = top_k
        else:
            kwargs["vector_top_k"] = top_k

        start = time.perf_counter()
        retrieved = func(query, **kwargs)
        latency = time.perf_counter() - start

        retrieved_ids = [r["id"] for r in retrieved]

        vector_count = sum(1 for r in retrieved if r.get("source") == "vector")
        graph_count = sum(1 for r in retrieved if r.get("source") == "graph")
        files = set(r.get("file", "") for r in retrieved)
        repos = set(r.get("file", "").split("/")[0] for r in retrieved if "/" in r.get("file", ""))

        retrieved_set = set(retrieved_ids)
        found = [s for s in query_entry["expected_symbols"]
                 if resolve_ids([s]).keys() & retrieved_set]
        missed = [s for s in query_entry["expected_symbols"]
                  if not (resolve_ids([s]).keys() & retrieved_set)]

        # Count cross-repo hits
        found_repos = set(s.get("repo", "") for s in found)

        results[mode_name] = {
            "precision_at_5": precision_at_k(retrieved_ids, relevant_ids, 5),
            "precision_at_10": precision_at_k(retrieved_ids, relevant_ids, 10),
            "recall_at_5": recall_at_k(retrieved_ids, relevant_ids, 5),
            "recall_at_10": recall_at_k(retrieved_ids, relevant_ids, 10),
            "total_recall": total_recall(retrieved_ids, relevant_ids),
            "mrr": mrr(retrieved_ids, relevant_ids),
            "ndcg_at_10": ndcg_at_k(retrieved_ids, relevance_map, 10),
            "latency_ms": round(latency * 1000, 1),
            "result_count": len(retrieved),
            "vector_count": vector_count,
            "graph_count": graph_count,
            "file_count": len(files),
            "repo_count": len(repos),
            "found_repos": sorted(found_repos - {""}),
            "found_relevant": [f"{s.get('repo','')}/{s['name']}" for s in found],
            "missed_relevant": [f"{s.get('repo','')}/{s['name']}" for s in missed],
        }

    return results


def run(
    golden_path="eval/golden_cross_repo.json",
    top_k=10,
    output_path="eval/eval_cross_repo_results.json",
):
    dataset = load_golden_dataset(golden_path)
    queries = dataset["queries"]

    print(f"Cross-repo eval: {len(queries)} queries × {len(MODES)} modes")

    print("Warmup...")
    vector_only("warmup", top_k=1)

    per_query = []
    for i, q in enumerate(queries):
        print(f"  [{i+1}/{len(queries)}] {q['query'][:60]}...")
        result = evaluate_query(q, top_k=top_k)
        per_query.append({
            "id": q["id"],
            "query": q["query"],
            "category": q["category"],
            "expected_count": len(q["expected_symbols"]),
            "modes": result,
        })

    eval_results = {
        "config": {
            "type": "cross_repo",
            "top_k": top_k,
            "golden_dataset": golden_path,
            "query_count": len(queries),
        },
        "per_query": per_query,
    }

    with open(output_path, "w") as f:
        json.dump(eval_results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    # Print summary
    modes = list(MODES.keys())
    metrics = ['recall_at_10', 'total_recall', 'mrr', 'ndcg_at_10']
    n = len(per_query)

    print(f"\n{'Mode':<22s}", end='')
    for m in metrics:
        print(f'{m:>14s}', end='')
    print(f"{'graph_nodes':>14s}")
    print("-" * 90)

    for mode in modes:
        print(f'{mode:<22s}', end='')
        for m in metrics:
            val = sum(q['modes'][mode][m] for q in per_query) / n
            print(f'{val:>14.3f}', end='')
        gc = sum(q['modes'][mode]['graph_count'] for q in per_query) / n
        print(f'{gc:>14.1f}')

    return eval_results


if __name__ == "__main__":
    run()
