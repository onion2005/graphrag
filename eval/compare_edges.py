"""
Compare baseline (AST) edges vs LLM edges:
- Coverage: how many unique node pairs does each method find?
- Overlap: what do both methods agree on?
- LLM-only: what semantic relationships does LLM find that AST cannot?
- AST-only: what structural relationships does AST find that LLM misses?
"""
import json
from pathlib import Path
from collections import Counter

from neo4j import GraphDatabase
import config


def load_edges_from_neo4j():
    driver = GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )

    baseline_edges = []
    llm_edges = []

    with driver.session() as session:
        # Baseline edges
        records = session.run("""
            MATCH (a:CodeNode)-[r:RELATES]->(b:CodeNode)
            RETURN a.id AS source, a.name AS source_name,
                   b.id AS target, b.name AS target_name,
                   r.type AS type
        """)
        for r in records:
            baseline_edges.append(dict(r))

        # LLM edges
        records = session.run("""
            MATCH (a:CodeNode)-[r:LLM_RELATES]->(b:CodeNode)
            RETURN a.id AS source, a.name AS source_name,
                   b.id AS target, b.name AS target_name,
                   r.type AS type, r.confidence AS confidence, r.reason AS reason
        """)
        for r in records:
            llm_edges.append(dict(r))

    driver.close()
    return baseline_edges, llm_edges


def compare():
    baseline, llm = load_edges_from_neo4j()

    # Normalize pairs (unordered) for overlap comparison
    def pair_key(e):
        return frozenset([e["source"], e["target"]])

    baseline_pairs = {pair_key(e) for e in baseline}
    llm_pairs = {pair_key(e) for e in llm}

    overlap = baseline_pairs & llm_pairs
    baseline_only = baseline_pairs - llm_pairs
    llm_only = llm_pairs - baseline_pairs

    # Edge type distributions
    baseline_types = Counter(e["type"] for e in baseline)
    llm_types = Counter(e["type"] for e in llm)

    # LLM-only edges by type
    llm_only_lookup = {pair_key(e): e for e in llm}
    llm_only_types = Counter()
    llm_only_examples = []
    for pk in llm_only:
        e = llm_only_lookup.get(pk)
        if e:
            llm_only_types[e["type"]] += 1
            if len(llm_only_examples) < 20:
                llm_only_examples.append(e)

    # Overlap edges — what type did each method assign?
    overlap_comparison = []
    baseline_lookup = {pair_key(e): e for e in baseline}
    for pk in list(overlap)[:20]:
        b = baseline_lookup.get(pk)
        l = llm_only_lookup.get(pk)
        if b and l:
            overlap_comparison.append({
                "source_name": b["source_name"],
                "target_name": b["target_name"],
                "baseline_type": b["type"],
                "llm_type": l["type"],
            })

    # Node coverage
    baseline_nodes = set()
    for e in baseline:
        baseline_nodes.add(e["source"])
        baseline_nodes.add(e["target"])

    llm_nodes = set()
    for e in llm:
        llm_nodes.add(e["source"])
        llm_nodes.add(e["target"])

    report = {
        "summary": {
            "baseline_edge_count": len(baseline),
            "llm_edge_count": len(llm),
            "baseline_unique_pairs": len(baseline_pairs),
            "llm_unique_pairs": len(llm_pairs),
            "overlap_pairs": len(overlap),
            "baseline_only_pairs": len(baseline_only),
            "llm_only_pairs": len(llm_only),
            "baseline_node_coverage": len(baseline_nodes),
            "llm_node_coverage": len(llm_nodes),
        },
        "edge_types": {
            "baseline": dict(baseline_types),
            "llm": dict(llm_types),
            "llm_only_by_type": dict(llm_only_types),
        },
        "llm_only_examples": [
            {
                "source_name": e.get("source_name"),
                "target_name": e.get("target_name"),
                "type": e["type"],
                "confidence": e.get("confidence"),
                "reason": e.get("reason"),
            }
            for e in llm_only_examples
        ],
        "overlap_type_comparison": overlap_comparison,
    }

    return report


def print_report():
    report = compare()
    s = report["summary"]

    print("=" * 60)
    print("  BASELINE (AST) vs LLM EDGE COMPARISON")
    print("=" * 60)

    print(f"\n{'Metric':<30s} {'Baseline':>10s} {'LLM':>10s}")
    print("-" * 52)
    print(f"{'Total edges':<30s} {s['baseline_edge_count']:>10d} {s['llm_edge_count']:>10d}")
    print(f"{'Unique pairs':<30s} {s['baseline_unique_pairs']:>10d} {s['llm_unique_pairs']:>10d}")
    print(f"{'Node coverage':<30s} {s['baseline_node_coverage']:>10d} {s['llm_node_coverage']:>10d}")

    print(f"\n{'Overlap pairs':<30s} {s['overlap_pairs']:>10d}")
    print(f"{'Baseline-only pairs':<30s} {s['baseline_only_pairs']:>10d}")
    print(f"{'LLM-only pairs':<30s} {s['llm_only_pairs']:>10d}")

    print("\n--- Edge Type Distribution ---")
    all_types = sorted(set(list(report["edge_types"]["baseline"]) + list(report["edge_types"]["llm"])))
    print(f"{'Type':<15s} {'Baseline':>10s} {'LLM':>10s} {'LLM-only':>10s}")
    print("-" * 47)
    for t in all_types:
        b = report["edge_types"]["baseline"].get(t, 0)
        l = report["edge_types"]["llm"].get(t, 0)
        lo = report["edge_types"]["llm_only_by_type"].get(t, 0)
        print(f"{t:<15s} {b:>10d} {l:>10d} {lo:>10d}")

    examples = report["llm_only_examples"]
    if examples:
        print(f"\n--- LLM-only Edges (sample, {len(examples)} shown) ---")
        for e in examples:
            print(f"  {e['type']:<12s} {e['source_name']} -> {e['target_name']}")
            print(f"               conf={e['confidence']:.2f}  {e['reason'][:70]}")

    # Save full report
    output = Path("eval/edge_comparison.json")
    output.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nFull report saved to {output}")


if __name__ == "__main__":
    print_report()
