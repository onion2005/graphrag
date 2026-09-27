"""
Standalone cross-repo LLM extraction using Anthropic SDK.
Extracts edges, saves to llm_edges_cross_repo.json, loads into Neo4j.
"""
import json
import os

import anthropic
import numpy as np
from sentence_transformers import SentenceTransformer

import config
from ingestion.embedder import build_chunk_text
from ingestion.neo4j_loader import get_driver, load_cross_repo_edges

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

If there is a meaningful cross-repo relationship, respond with JSON:
{{"relationship": "<type>", "confidence": <0.0-1.0>, "reason": "<why>", "direction": "A->B"}}

Relationship types: SIMILAR_TO, WRAPS, IMPLEMENTS_SAME_INTERFACE, DEPENDS_ON, ALTERNATIVE_TO
If no meaningful relationship exists, respond: {{"relationship": "NONE"}}
Respond ONLY with the JSON object, no other text."""


def extract_pair(client, node_a, node_b):
    source_a = node_a.get("source_code", "")[:500]
    source_b = node_b.get("source_code", "")[:500]

    prompt = CROSS_REPO_PROMPT.format(
        repo_a=node_a.get("repo", "?"), name_a=node_a["name"], type_a=node_a["type"], source_a=source_a,
        repo_b=node_b.get("repo", "?"), name_b=node_b["name"], type_b=node_b["type"], source_b=source_b,
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
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


def rank_pairs(nodes_by_repo, top_k_per_node=5):
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
                continue
            pair_key = (min(i, j), max(i, j))
            if pair_key not in seen:
                seen.add(pair_key)
                ranked.append((all_nodes[i], all_nodes[j], float(sims[j])))
                count += 1
            if count >= top_k_per_node:
                break

    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked


def main():
    # Load nodes
    nodes_by_repo = {}
    for repo_name in config.REPOS:
        with open(f"nodes_{repo_name}.json") as f:
            nodes_by_repo[repo_name] = json.load(f)
        print(f"  {repo_name}: {len(nodes_by_repo[repo_name])} nodes")

    # Rank pairs
    print("Ranking cross-repo pairs...")
    ranked = rank_pairs(nodes_by_repo, top_k_per_node=5)
    print(f"  {len(ranked)} candidate pairs")

    pairs = ranked[:500]
    print(f"Processing {len(pairs)} pairs with Claude Haiku...")

    client = anthropic.Anthropic(
        default_headers={"anthropic-workspace-id": "wrkspc_013b68RhKngegNc3a8e7CkJm"},
    )

    edges = []
    for i, (a, b, sim) in enumerate(pairs):
        try:
            edge = extract_pair(client, a, b)
            if edge is not None:
                edge["embedding_similarity"] = sim
                edges.append(edge)
        except Exception as e:
            print(f"  Error at pair {i}: {e}")

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(pairs)} processed, {len(edges)} edges found")
            # Save checkpoint
            with open("llm_edges_cross_repo.json", "w") as f:
                json.dump(edges, f, indent=2)

    print(f"\nDone: {len(edges)} cross-repo edges from {len(pairs)} pairs")

    # Save final
    with open("llm_edges_cross_repo.json", "w") as f:
        json.dump(edges, f, indent=2)
    print(f"Saved to llm_edges_cross_repo.json")

    # Load into Neo4j
    print(f"\nLoading {len(edges)} edges into Neo4j...")
    driver = get_driver()
    try:
        load_cross_repo_edges(driver, edges)
    finally:
        driver.close()
    print("Done!")


if __name__ == "__main__":
    main()
