"""
IR evaluation metrics for retrieval comparison.

All functions take retrieved IDs (ordered) and relevance info,
return a single float score.
"""
import math


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of top-k results that are relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    return sum(1 for rid in top_k if rid in relevant_ids) / len(top_k)


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of relevant items found in top-k."""
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    return sum(1 for rid in top_k if rid in relevant_ids) / len(relevant_ids)


def mrr(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of first relevant result."""
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevance_map: dict[str, int], k: int) -> float:
    """
    Normalized Discounted Cumulative Gain at k.

    relevance_map: {node_id: relevance_grade} where grade is 1-3.
    Uses DCG = sum(rel_i / log2(i + 2)) for i in 0..k-1.
    """
    top_k = retrieved_ids[:k]

    # DCG
    dcg = 0.0
    for i, rid in enumerate(top_k):
        rel = relevance_map.get(rid, 0)
        dcg += rel / math.log2(i + 2)

    # Ideal DCG: sort all relevant grades descending
    ideal_rels = sorted(relevance_map.values(), reverse=True)[:k]
    idcg = 0.0
    for i, rel in enumerate(ideal_rels):
        idcg += rel / math.log2(i + 2)

    if idcg == 0:
        return 0.0
    return dcg / idcg


def total_recall(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Fraction of relevant items found anywhere in results (no k cutoff)."""
    if not relevant_ids:
        return 0.0
    return sum(1 for rid in retrieved_ids if rid in relevant_ids) / len(relevant_ids)
