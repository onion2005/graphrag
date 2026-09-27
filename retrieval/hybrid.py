import numpy as np
import chromadb
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

import config
from retrieval.cypher_templates import TEMPLATES

# Shared resources (avoid reloading per call)
_model = None
_collection = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
        _collection = client.get_collection(config.CHROMA_COLLECTION)
    return _collection


def _rerank_graph_nodes(query: str, graph_nodes: dict[str, dict]) -> dict[str, dict]:
    """Score graph-expanded nodes by embedding similarity to the query."""
    if not graph_nodes:
        return graph_nodes

    model = _get_model()
    query_emb = model.encode([query], normalize_embeddings=True)

    node_ids = list(graph_nodes.keys())
    collection = _get_collection()

    # Fetch stored embeddings from Chroma
    fetched = collection.get(ids=node_ids, include=["embeddings"])
    if not fetched["embeddings"]:
        return graph_nodes

    node_embs = np.array(fetched["embeddings"])
    # Normalize for cosine similarity
    norms = np.linalg.norm(node_embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    node_embs = node_embs / norms

    similarities = (node_embs @ query_emb.T).flatten()

    for nid, sim in zip(fetched["ids"], similarities):  # use fetched IDs, not original list
        graph_nodes[nid]["score"] = float(sim)

    return graph_nodes


def vector_only(query: str, top_k: int = None) -> list[dict]:
    """Embedding search only — no graph expansion."""
    top_k = top_k or config.VECTOR_TOP_K
    model = _get_model()
    collection = _get_collection()

    results = collection.query(
        query_embeddings=model.encode([query]).tolist(),
        n_results=top_k,
    )

    nodes = []
    for doc_id, doc, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        nodes.append({
            "id": doc_id,
            "name": meta["name"],
            "type": meta["type"],
            "file": meta["file"],
            "document": doc,
            "score": 1 - dist / 2,  # L2 on unit-norm vectors: L2 = 2*(1-cosine), so cosine = 1 - L2/2
            "source": "vector",
        })
    return nodes


def hybrid_retrieve(
    query: str,
    vector_top_k: int = None,
    graph_hops: int = None,
    max_graph_nodes: int = None,
    graph_type: str = "both",
    rerank: bool = True,
    hop_decay: float = None,
    min_similarity: float = None,
) -> list[dict]:
    """
    Hybrid retrieval: vector search → graph expansion → rerank → damping → merge.

    graph_type: "baseline" (AST only), "llm" (LLM only), "both"
    rerank: if True, score graph nodes by embedding similarity to query
            if False, use flat 0.5 score (old behavior)
    hop_decay: damping factor per hop (score *= hop_decay ^ hops). Default 0.8.
    min_similarity: drop graph nodes below this reranked score. Default 0.0 (keep all).
    """
    vector_top_k = vector_top_k or config.VECTOR_TOP_K
    graph_hops = graph_hops or config.GRAPH_HOPS
    max_graph_nodes = max_graph_nodes or config.MAX_GRAPH_NODES
    hop_decay = hop_decay if hop_decay is not None else config.HOP_DECAY
    min_similarity = min_similarity if min_similarity is not None else config.MIN_SIMILARITY

    # 1. Vector search
    vector_results = vector_only(query, top_k=vector_top_k)
    vector_nodes = {n["id"]: n for n in vector_results}

    # 2. Graph expansion
    entry_ids = list(vector_nodes.keys())
    templates = TEMPLATES.get(graph_type, TEMPLATES["both"])
    cypher = templates.get(graph_hops, templates[1])

    driver = GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )
    graph_nodes = {}
    try:
        with driver.session() as session:
            records = session.run(cypher, entry_ids=entry_ids, limit=max_graph_nodes)
            for record in records:
                nid = record["id"]
                if nid not in vector_nodes:
                    graph_nodes[nid] = {
                        "id": nid,
                        "name": record["name"],
                        "type": record["type"],
                        "file": record["file"],
                        "docstring": record["docstring"],
                        "score": 0.5,
                        "source": "graph",
                        "hops": record["hops"],
                    }
    finally:
        driver.close()

    # 3. Rerank graph nodes by embedding similarity
    if rerank:
        graph_nodes = _rerank_graph_nodes(query, graph_nodes)

    # 4. Apply hop-based decay: score *= hop_decay ^ hops
    if hop_decay < 1.0:
        for node in graph_nodes.values():
            hops = node.get("hops", 1)
            node["score"] *= hop_decay ** hops

    # 5. Filter by minimum similarity threshold
    if min_similarity > 0:
        graph_nodes = {nid: n for nid, n in graph_nodes.items()
                       if n["score"] >= min_similarity}

    # 6. Merge + dedup (vector wins if same id)
    merged = {**graph_nodes, **vector_nodes}
    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return ranked


def compare(query: str, vector_top_k: int = 10, graph_hops: int = 1) -> dict:
    """
    Run all retrieval modes and return comparison.

    Modes:
      - vector_only: embedding search only
      - vector_ast_graph: vector + AST graph expansion (reranked)
      - vector_graph_llm: vector + LLM graph expansion (reranked)
      - vector_graph_ast_llm: vector + both graph types (reranked)
    """
    return {
        "query": query,
        "vector_only": vector_only(query, top_k=vector_top_k),
        "vector_ast_graph": hybrid_retrieve(
            query, vector_top_k=vector_top_k, graph_hops=graph_hops, graph_type="baseline",
        ),
        "vector_graph_llm": hybrid_retrieve(
            query, vector_top_k=vector_top_k, graph_hops=graph_hops, graph_type="llm",
        ),
        "vector_graph_ast_llm": hybrid_retrieve(
            query, vector_top_k=vector_top_k, graph_hops=graph_hops, graph_type="both",
        ),
    }


def print_comparison(query: str, vector_top_k: int = 10, graph_hops: int = 1):
    """Run comparison and print a readable summary."""
    results = compare(query, vector_top_k=vector_top_k, graph_hops=graph_hops)

    labels = {
        "vector_only": "Vector Only",
        "vector_ast_graph": "Vector + AST Graph",
        "vector_graph_llm": "Vector + Graph (LLM)",
        "vector_graph_ast_llm": "Vector + Graph (AST+LLM)",
    }

    for mode in labels:
        nodes = results[mode]
        vector_count = sum(1 for n in nodes if n["source"] == "vector")
        graph_count = sum(1 for n in nodes if n["source"] == "graph")
        files = set(n["file"] for n in nodes)

        print(f"\n{'='*70}")
        print(f"  {labels[mode]}  ({len(nodes)} results: {vector_count} vector + {graph_count} graph, {len(files)} files)")
        print(f"{'='*70}")
        for n in nodes:
            src = n["source"]
            print(f"  [{src:6s}] {n['score']:+.3f}  {n['name']}  ({n['file']})")
