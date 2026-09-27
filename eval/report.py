"""
Generate evaluation reports from runner output.
"""
import json
from collections import defaultdict

MODE_LABELS = {
    "vector_only": "Vector Only",
    "vector_ast_graph": "Vector + AST Graph",
    "vector_graph_llm": "Vector + Graph (LLM)",
    "vector_graph_ast_llm": "Vector + Graph (AST+LLM)",
}

METRIC_KEYS = [
    "recall_at_5", "recall_at_10", "recall_at_20", "total_recall",
    "precision_at_5", "precision_at_10", "precision_at_20",
    "mrr", "ndcg_at_5", "ndcg_at_10", "ndcg_at_20",
]
METRIC_LABELS = {
    "precision_at_5": "P@5",
    "precision_at_10": "P@10",
    "precision_at_20": "P@20",
    "precision_at_30": "P@30",
    "recall_at_5": "R@5",
    "recall_at_10": "R@10",
    "recall_at_20": "R@20",
    "recall_at_30": "R@30",
    "total_recall": "R@all",
    "mrr": "MRR",
    "ndcg_at_5": "nDCG@5",
    "ndcg_at_10": "nDCG@10",
    "ndcg_at_20": "nDCG@20",
    "ndcg_at_30": "nDCG@30",
}


def load_results(path: str = "eval/eval_results.json") -> dict:
    with open(path) as f:
        return json.load(f)


def _available_metrics(eval_results: dict) -> list[str]:
    """Return only metric keys that exist in the results."""
    sample = eval_results["per_query"][0]["modes"]["vector_only"]
    return [k for k in METRIC_KEYS if k in sample]


def aggregate_metrics(eval_results: dict) -> dict[str, dict[str, float]]:
    """Compute mean for each metric across all queries, per mode."""
    per_query = eval_results["per_query"]
    n = len(per_query)
    if n == 0:
        return {}

    keys = _available_metrics(eval_results)
    agg = {}
    for mode in MODE_LABELS:
        sums = defaultdict(float)
        for q in per_query:
            for key in keys:
                sums[key] += q["modes"][mode][key]
        agg[mode] = {key: round(sums[key] / n, 3) for key in keys}
        agg[mode]["avg_latency_ms"] = round(
            sum(q["modes"][mode]["latency_ms"] for q in per_query) / n, 1
        )
    return agg


def per_category_metrics(eval_results: dict) -> dict[str, dict[str, dict[str, float]]]:
    """Aggregate metrics grouped by query category."""
    by_cat: dict[str, list] = defaultdict(list)
    for q in eval_results["per_query"]:
        by_cat[q["category"]].append(q)

    keys = _available_metrics(eval_results)
    result = {}
    for cat, queries in sorted(by_cat.items()):
        n = len(queries)
        cat_agg = {}
        for mode in MODE_LABELS:
            sums = defaultdict(float)
            for q in queries:
                for key in keys:
                    sums[key] += q["modes"][mode][key]
            cat_agg[mode] = {key: round(sums[key] / n, 3) for key in keys}
        result[cat] = cat_agg
    return result


def format_summary_table(agg: dict[str, dict[str, float]], metrics: list[str] = None, show_latency: bool = True) -> str:
    """Render a comparison table for given metrics."""
    sample = next(iter(agg.values()), {})
    if metrics is None:
        metrics = [k for k in METRIC_KEYS if k in sample]
    has_latency = show_latency and "avg_latency_ms" in sample

    header = f"| {'Mode':<28s} |"
    for key in metrics:
        header += f" {METRIC_LABELS[key]:>7s} |"
    if has_latency:
        header += f" {'Latency':>8s} |"

    sep = "|" + "-" * 30 + "|"
    for _ in metrics:
        sep += "-" * 9 + "|"
    if has_latency:
        sep += "-" * 10 + "|"

    rows = [header, sep]
    for mode in MODE_LABELS:
        row = f"| {MODE_LABELS[mode]:<28s} |"
        for key in metrics:
            row += f" {agg[mode].get(key, 0):>7.3f} |"
        if has_latency:
            row += f" {agg[mode]['avg_latency_ms']:>6.0f}ms |"
        rows.append(row)

    return "\n".join(rows)


def format_per_query_detail(eval_results: dict) -> str:
    """Per-query breakdown showing found/missed per mode."""
    lines = []
    for q in eval_results["per_query"]:
        lines.append(f"\n### {q['id']}: {q['query']}")
        lines.append(f"Category: {q['category']} | Expected: {q['expected_count']} symbols\n")

        for mode in MODE_LABELS:
            m = q["modes"][mode]
            found = ", ".join(m["found_relevant"]) or "—"
            missed = ", ".join(m["missed_relevant"]) or "—"
            tr = m.get("total_recall", 0)
            lines.append(f"**{MODE_LABELS[mode]}**: R@all={tr:.2f} R@10={m['recall_at_10']:.2f} nDCG@10={m['ndcg_at_10']:.2f} ({m['result_count']} results)")
            lines.append(f"  Found: {found}")
            if m["missed_relevant"]:
                lines.append(f"  Missed: {missed}")

    return "\n".join(lines)


def generate_report(
    eval_results_path: str = "eval/eval_results.json",
    output_path: str = "eval/eval_report.md",
) -> str:
    """Generate full markdown report."""
    results = load_results(eval_results_path)
    agg = aggregate_metrics(results)
    cat_metrics = per_category_metrics(results)

    cfg = results["config"]

    # Recall-focused table
    recall_metrics = ["recall_at_5", "recall_at_10", "recall_at_20", "total_recall"]
    recall_metrics = [m for m in recall_metrics if m in next(iter(agg.values()))]
    # Ranking-focused table
    rank_metrics = ["mrr", "ndcg_at_5", "ndcg_at_10", "ndcg_at_20", "precision_at_5", "precision_at_10", "precision_at_20"]
    rank_metrics = [m for m in rank_metrics if m in next(iter(agg.values()))]

    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"> {cfg['query_count']} queries, top_k={cfg['top_k']}, relevance_threshold={cfg['relevance_threshold']}",
        "",
        "## Recall (does the mode find the right symbols?)",
        "",
        format_summary_table(agg, metrics=recall_metrics),
        "",
        "## Ranking Quality (are the right symbols ranked high?)",
        "",
        format_summary_table(agg, metrics=rank_metrics, show_latency=False),
        "",
        "## Per-Category Breakdown",
    ]

    for cat, cat_agg in cat_metrics.items():
        lines.append(f"\n### {cat}")
        lines.append("")
        lines.append(format_summary_table(cat_agg, metrics=recall_metrics, show_latency=False))

    lines.append("")
    lines.append("## Per-Query Detail")
    lines.append(format_per_query_detail(results))

    report = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(report)
    print(f"Report saved to {output_path}")

    return report


def print_report(eval_results_path: str = "eval/eval_results.json"):
    """Print report to stdout."""
    results = load_results(eval_results_path)
    agg = aggregate_metrics(results)

    sample = next(iter(agg.values()))
    recall_metrics = [m for m in ["recall_at_5", "recall_at_10", "recall_at_20", "total_recall"] if m in sample]
    rank_metrics = [m for m in ["mrr", "ndcg_at_5", "ndcg_at_10", "ndcg_at_20", "precision_at_5", "precision_at_10"] if m in sample]

    print("=" * 70)
    print("  RETRIEVAL EVALUATION RESULTS")
    print("=" * 70)

    print("\n--- Recall ---")
    print(format_summary_table(agg, metrics=recall_metrics))

    print("\n--- Ranking Quality ---")
    print(format_summary_table(agg, metrics=rank_metrics, show_latency=False))

    cat_metrics = per_category_metrics(results)
    for cat, cat_agg in cat_metrics.items():
        print(f"\n--- {cat} ---")
        print(format_summary_table(cat_agg, metrics=recall_metrics, show_latency=False))

    # Mode comparison
    print("\n--- Mode vs Vector Only ---")
    baseline = agg["vector_only"]
    for mode in ["vector_ast_graph", "vector_graph_llm", "vector_graph_ast_llm"]:
        deltas = []
        for key in recall_metrics + ["mrr"]:
            if key in agg[mode]:
                delta = agg[mode][key] - baseline[key]
                deltas.append(f"{METRIC_LABELS[key]}: {delta:+.3f}")
        print(f"  {MODE_LABELS[mode]}: {', '.join(deltas)}")


if __name__ == "__main__":
    print_report()
