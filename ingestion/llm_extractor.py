import json
import itertools
from pathlib import Path

import numpy as np
import openai
from sentence_transformers import SentenceTransformer

import config
from ingestion.embedder import build_chunk_text

CROSS_REPO_PROMPT = """\
You are a code relationship extractor. Given two code symbols from DIFFERENT codebases, determine if there is a meaningful semantic relationship between them.

Symbol A (from {repo_a}):
  Name: {name_a}
  Type: {type_a}
  Source:
```python
{source_a}
```

Symbol B (from {repo_b}):
  Name: {name_b}
  Type: {type_b}
  Source:
```python
{source_b}
```

Classify the relationship as exactly ONE of:
- SIMILAR_TO: both symbols serve a similar purpose or implement similar logic (e.g. both handle auth, both parse URLs)
- DEPENDS_ON: one symbol's design depends on or wraps the other (e.g. requests.HTTPAdapter wraps urllib3.PoolManager)
- NONE: no meaningful relationship

Respond with a JSON object only, no other text:
{{"relationship": "<type>", "confidence": <0.0-1.0>, "reason": "<brief explanation>", "direction": "A->B" or "B->A" or "bidirectional"}}
"""

PROMPT = """\
You are a code relationship extractor. Given two code symbols from the same file, determine if there is a meaningful relationship between them.

Symbol A:
  Name: {name_a}
  Type: {type_a}
  Source:
```python
{source_a}
```

Symbol B:
  Name: {name_b}
  Type: {type_b}
  Source:
```python
{source_b}
```

Note: CALLS, IMPORTS, INHERITS, and USES_TYPE are already captured by static analysis. Focus only on semantic relationships that static analysis cannot detect.

Classify the relationship as exactly ONE of:
- SIMILAR_TO: both symbols serve a similar purpose or implement similar logic
- DEPENDS_ON: one symbol depends on the other (shared state, config, initialization order)
- NONE: no meaningful relationship

Respond with a JSON object only, no other text:
{{"relationship": "<type>", "confidence": <0.0-1.0>, "reason": "<brief explanation>", "direction": "A->B" or "B->A" or "bidirectional"}}
"""


def extract_pair(client: openai.OpenAI, node_a: dict, node_b: dict) -> dict | None:
    """Extract relationship between two nodes using LLM."""
    source_a = node_a.get("source_code", "")[:500]
    source_b = node_b.get("source_code", "")[:500]

    prompt = PROMPT.format(
        name_a=node_a["name"], type_a=node_a["type"], source_a=source_a,
        name_b=node_b["name"], type_b=node_b["type"], source_b=source_b,
    )

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None

    if result.get("relationship", "NONE") == "NONE":
        return None
    if result.get("confidence", 0) < config.LLM_MIN_CONFIDENCE:
        return None

    direction = result.get("direction", "A->B")
    if direction == "B->A":
        source_id, target_id = node_b["id"], node_a["id"]
    else:
        source_id, target_id = node_a["id"], node_b["id"]

    return {
        "source": source_id,
        "target": target_id,
        "source_name": node_a["name"] if direction != "B->A" else node_b["name"],
        "target_name": node_b["name"] if direction != "B->A" else node_a["name"],
        "type": result["relationship"],
        "confidence": result["confidence"],
        "reason": result.get("reason", ""),
        "source_label": "llm",
    }


def _rank_pairs_by_embedding(nodes: list[dict], top_k_per_node: int = 10) -> list[tuple[dict, dict, float]]:
    """
    Rank all candidate pairs by embedding cosine similarity.
    Instead of O(n²) LLM calls, embed once O(n) then pick top-k neighbors per node.
    Returns deduplicated (node_a, node_b, similarity) sorted descending.
    """
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    texts = [build_chunk_text(n) for n in nodes]
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    # Cosine similarity matrix (embeddings are normalized, so dot product = cosine)
    sim_matrix = embeddings @ embeddings.T

    # Collect top-k per node, deduplicate
    seen = set()
    ranked = []
    for i in range(len(nodes)):
        # Get top-k most similar (exclude self)
        sims = sim_matrix[i]
        top_indices = np.argsort(sims)[::-1]
        count = 0
        for j in top_indices:
            if j == i:
                continue
            pair_key = (min(i, j), max(i, j))
            if pair_key not in seen:
                seen.add(pair_key)
                ranked.append((nodes[i], nodes[j], float(sims[j])))
                count += 1
            if count >= top_k_per_node:
                break

    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked


def extract_file_relationships(nodes: list[dict], client: openai.OpenAI = None) -> list[dict]:
    """Extract LLM relationships using brute-force same-file pairing."""
    if client is None:
        client = openai.OpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
        )

    by_file: dict[str, list[dict]] = {}
    for n in nodes:
        if n["type"] == "module":
            continue
        by_file.setdefault(n["file"], []).append(n)

    edges = []
    pair_count = 0

    for file, file_nodes in sorted(by_file.items()):
        pairs = list(itertools.combinations(file_nodes, 2))
        for a, b in pairs:
            if pair_count >= config.LLM_MAX_PAIRS:
                print(f"Hit max_pairs limit ({config.LLM_MAX_PAIRS}), stopping.")
                _save(edges)
                return edges

            edge = extract_pair(client, a, b)
            pair_count += 1

            if pair_count % 50 == 0:
                print(f"  Processed {pair_count} pairs, found {len(edges)} edges...")

            if edge is not None:
                edges.append(edge)

    print(f"Done: {pair_count} pairs processed, {len(edges)} LLM edges found.")
    _save(edges)
    return edges


def extract_with_pruning(
    nodes: list[dict],
    top_k_per_node: int = 10,
    max_pairs: int = None,
    client: openai.OpenAI = None,
) -> list[dict]:
    """
    Embedding-pruned LLM extraction.

    1. Embed all nodes once → O(n)
    2. For each node, pick top-k most similar neighbors → O(n·k) pairs
    3. Only run LLM on those high-similarity pairs

    Much cheaper than brute-force O(n²) and covers the whole repo,
    not just the first few files alphabetically.
    """
    if client is None:
        client = openai.OpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
        )

    max_pairs = max_pairs or config.LLM_MAX_PAIRS

    # Filter out modules
    symbol_nodes = [n for n in nodes if n["type"] != "module"]
    print(f"Ranking {len(symbol_nodes)} nodes by embedding similarity...")

    ranked_pairs = _rank_pairs_by_embedding(symbol_nodes, top_k_per_node=top_k_per_node)
    total_candidate = len(ranked_pairs)
    print(f"Candidate pairs: {total_candidate} (top-{top_k_per_node} per node, deduplicated)")

    # Cap at max_pairs
    pairs_to_process = ranked_pairs[:max_pairs]
    print(f"Processing {len(pairs_to_process)} pairs with LLM...")

    edges = []
    for i, (a, b, sim) in enumerate(pairs_to_process):
        edge = extract_pair(client, a, b)
        if edge is not None:
            edge["embedding_similarity"] = sim
            edges.append(edge)

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(pairs_to_process)} pairs, found {len(edges)} edges...")

    print(f"Done: {len(pairs_to_process)} pairs processed, {len(edges)} LLM edges found.")
    _save(edges, filename="llm_edges_pruned.json")
    return edges


def extract_cross_repo_pair(client: openai.OpenAI, node_a: dict, node_b: dict) -> dict | None:
    """Extract relationship between two nodes from different repos."""
    source_a = node_a.get("source_code", "")[:500]
    source_b = node_b.get("source_code", "")[:500]

    prompt = CROSS_REPO_PROMPT.format(
        repo_a=node_a.get("repo", "?"), name_a=node_a["name"], type_a=node_a["type"], source_a=source_a,
        repo_b=node_b.get("repo", "?"), name_b=node_b["name"], type_b=node_b["type"], source_b=source_b,
    )

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None

    if result.get("relationship", "NONE") == "NONE":
        return None
    if result.get("confidence", 0) < config.LLM_MIN_CONFIDENCE:
        return None

    direction = result.get("direction", "A->B")
    if direction == "B->A":
        source_id, target_id = node_b["id"], node_a["id"]
    else:
        source_id, target_id = node_a["id"], node_b["id"]

    return {
        "source": source_id,
        "target": target_id,
        "source_name": node_a["name"] if direction != "B->A" else node_b["name"],
        "target_name": node_b["name"] if direction != "B->A" else node_a["name"],
        "type": result["relationship"],
        "confidence": result["confidence"],
        "reason": result.get("reason", ""),
        "source_label": "llm_cross_repo",
        "source_repo": node_a.get("repo", ""),
        "target_repo": node_b.get("repo", ""),
    }


def _rank_cross_repo_pairs(
    nodes_by_repo: dict[str, list[dict]],
    top_k_per_node: int = 5,
) -> list[tuple[dict, dict, float]]:
    """Rank cross-repo pairs by embedding similarity. Only pairs from different repos."""
    all_nodes = []
    repo_labels = []
    for repo_name, nodes in nodes_by_repo.items():
        for n in nodes:
            if n["type"] != "module":
                all_nodes.append(n)
                repo_labels.append(repo_name)

    model = SentenceTransformer(config.EMBEDDING_MODEL)
    texts = [build_chunk_text(n) for n in all_nodes]
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    sim_matrix = embeddings @ embeddings.T

    seen = set()
    ranked = []
    for i in range(len(all_nodes)):
        sims = sim_matrix[i]
        top_indices = np.argsort(sims)[::-1]
        count = 0
        for j in top_indices:
            if j == i or repo_labels[j] == repo_labels[i]:
                continue  # skip same-repo pairs
            pair_key = (min(i, j), max(i, j))
            if pair_key not in seen:
                seen.add(pair_key)
                ranked.append((all_nodes[i], all_nodes[j], float(sims[j])))
                count += 1
            if count >= top_k_per_node:
                break

    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked


def extract_cross_repo(
    nodes_by_repo: dict[str, list[dict]],
    top_k_per_node: int = 5,
    max_pairs: int = None,
    client: openai.OpenAI = None,
) -> list[dict]:
    """Extract cross-repo LLM relationships using embedding-pruned pairs."""
    if client is None:
        client = openai.OpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
        )

    max_pairs = max_pairs or config.LLM_MAX_PAIRS

    total_nodes = sum(len([n for n in nodes if n["type"] != "module"]) for nodes in nodes_by_repo.values())
    print(f"Ranking {total_nodes} nodes across {len(nodes_by_repo)} repos for cross-repo pairs...")

    ranked_pairs = _rank_cross_repo_pairs(nodes_by_repo, top_k_per_node=top_k_per_node)
    print(f"Cross-repo candidate pairs: {len(ranked_pairs)}")

    pairs_to_process = ranked_pairs[:max_pairs]
    print(f"Processing {len(pairs_to_process)} pairs with LLM...")

    edges = []
    for i, (a, b, sim) in enumerate(pairs_to_process):
        edge = extract_cross_repo_pair(client, a, b)
        if edge is not None:
            edge["embedding_similarity"] = sim
            edges.append(edge)

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(pairs_to_process)} pairs, found {len(edges)} edges...")

    print(f"Done: {len(pairs_to_process)} pairs processed, {len(edges)} cross-repo edges found.")
    _save(edges, filename="llm_edges_cross_repo.json")
    return edges


def _save(edges: list[dict], filename: str = "llm_edges.json"):
    output_path = Path(filename)
    output_path.write_text(json.dumps(edges, indent=2))
    print(f"Saved to {output_path}")
