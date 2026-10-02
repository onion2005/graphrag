"""
Evaluation runner: loads golden dataset, runs all retrieval modes,
computes metrics, saves structured results.
"""
import json
import time

from ingestion.id_registry import make_node_id
from retrieval.hybrid import vector_only, hybrid_retrieve
from eval.metrics import precision_at_k, recall_at_k, mrr, ndcg_at_k, total_recall

MODES = {
    "vector_only": {"func": vector_only, "kwargs": {}},
    "vector_ast_graph": {"func": hybrid_retrieve, "kwargs": {"graph_type": "baseline"}},
    "vector_graph_llm": {"func": hybrid_retrieve, "kwargs": {"graph_type": "llm"}},
    "vector_graph_ast_llm": {"func": hybrid_retrieve, "kwargs": {"graph_type": "both"}},
    "vector_graphify": {"func": hybrid_retrieve, "kwargs": {"graph_type": "graphify"}},
}


def load_golden_dataset(path: str = "eval/golden_dataset.json") -> dict:
    with open(path) as f:
        return json.load(f)


def resolve_ids(expected_symbols: list[dict]) -> dict[str, int]:
    """Convert (name, file, type) to {node_id: relevance_grade}."""
    relevance_map = {}
    for s in expected_symbols:
        # For cross-repo datasets, file already includes repo prefix (e.g. "httpx/httpx/_auth.py")
        # and repo_name is provided separately. For single-repo datasets, no repo field.
        repo_name = s.get("repo")
        if repo_name:
            file_path = s["file"]
            # Cross-repo datasets have paths like "httpx/httpx/_auth.py" (repo/package/file)
            # Single-repo datasets have paths like "httpx/_client.py" (package/file)
            # Strip repo prefix only if file starts with "repo/repo" (doubled prefix)
            prefix = f"{repo_name}/{repo_name}"
            if file_path.startswith(prefix):
                file_path = file_path[len(f"{repo_name}/"):]
            node_id = make_node_id(file_path, s["name"], s["type"], repo_name=repo_name)
        else:
            node_id = make_node_id(s["file"], s["name"], s["type"])
        relevance_map[node_id] = s["relevance"]
    return relevance_map


def evaluate_query(
    query_entry: dict,
    top_k: int = 10,
    relevance_threshold: int = 2,
) -> dict:
    """Run all 4 modes on one query, compute metrics per mode."""
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

        retrieved_set = set(retrieved_ids)
        found = [s for s in query_entry["expected_symbols"]
                 if resolve_ids([s]).keys() & retrieved_set]
        missed = [s for s in query_entry["expected_symbols"]
                  if not (resolve_ids([s]).keys() & retrieved_set)]

        results[mode_name] = {
            "precision_at_5": precision_at_k(retrieved_ids, relevant_ids, 5),
            "precision_at_10": precision_at_k(retrieved_ids, relevant_ids, 10),
            "precision_at_20": precision_at_k(retrieved_ids, relevant_ids, 20),
            "precision_at_30": precision_at_k(retrieved_ids, relevant_ids, 30),
            "recall_at_5": recall_at_k(retrieved_ids, relevant_ids, 5),
            "recall_at_10": recall_at_k(retrieved_ids, relevant_ids, 10),
            "recall_at_20": recall_at_k(retrieved_ids, relevant_ids, 20),
            "recall_at_30": recall_at_k(retrieved_ids, relevant_ids, 30),
            "total_recall": total_recall(retrieved_ids, relevant_ids),
            "mrr": mrr(retrieved_ids, relevant_ids),
            "ndcg_at_5": ndcg_at_k(retrieved_ids, relevance_map, 5),
            "ndcg_at_10": ndcg_at_k(retrieved_ids, relevance_map, 10),
            "ndcg_at_20": ndcg_at_k(retrieved_ids, relevance_map, 20),
            "ndcg_at_30": ndcg_at_k(retrieved_ids, relevance_map, 30),
            "latency_ms": round(latency * 1000, 1),
            "result_count": len(retrieved),
            "vector_count": vector_count,
            "graph_count": graph_count,
            "file_count": len(files),
            "found_relevant": [s["name"] for s in found],
            "missed_relevant": [s["name"] for s in missed],
        }

    return results


def run_evaluation(
    golden_path: str = "eval/golden_dataset.json",
    top_k: int = 10,
    relevance_threshold: int = 2,
    output_path: str = "eval/eval_results.json",
) -> dict:
    """Run full evaluation across all queries and modes."""
    dataset = load_golden_dataset(golden_path)
    queries = dataset["queries"]

    print(f"Running evaluation: {len(queries)} queries × {len(MODES)} modes")

    # Warmup (load models and connections)
    print("Warmup...")
    vector_only("warmup", top_k=1)

    per_query = []
    for i, q in enumerate(queries):
        print(f"  [{i+1}/{len(queries)}] {q['query'][:60]}...")
        result = evaluate_query(q, top_k=top_k, relevance_threshold=relevance_threshold)
        per_query.append({
            "id": q["id"],
            "query": q["query"],
            "category": q["category"],
            "expected_count": len(q["expected_symbols"]),
            "modes": result,
        })

    eval_results = {
        "config": {
            "top_k": top_k,
            "relevance_threshold": relevance_threshold,
            "golden_dataset": golden_path,
            "query_count": len(queries),
        },
        "per_query": per_query,
    }

    with open(output_path, "w") as f:
        json.dump(eval_results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    return eval_results


if __name__ == "__main__":
    run_evaluation()
