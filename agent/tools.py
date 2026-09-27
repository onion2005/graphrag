from langchain_core.tools import tool

from retrieval.hybrid import vector_only, hybrid_retrieve


def _truncate_results(results: list[dict], max_results: int = 15, max_doc_len: int = 500) -> str:
    """Format retrieval results as readable text, truncating for context limits."""
    output = []
    for node in results[:max_results]:
        doc = node.get("document") or node.get("docstring") or ""
        if len(doc) > max_doc_len:
            doc = doc[:max_doc_len] + "..."
        source = node.get("source", "unknown")
        score = node.get("score", 0)
        output.append(
            f"[{source}] {node['name']} ({node['type']}) — {node['file']} (score: {score:.3f})\n{doc}"
        )
    total = len(results)
    shown = min(total, max_results)
    header = f"Found {total} results (showing {shown}):\n"
    return header + "\n---\n".join(output)


@tool
def search_code(query: str, top_k: int = 5) -> str:
    """Embedding search for code symbols. Best for finding specific functions/classes
    by name or description. Returns top-k most similar symbols."""
    results = vector_only(query, top_k=top_k)
    return _truncate_results(results)


@tool
def search_code_with_graph(
    query: str,
    vector_top_k: int = 5,
    graph_hops: int = 1,
    max_graph_nodes: int = 20,
) -> str:
    """Hybrid search: vector search + graph expansion along AST edges
    (CONTAINS, CALLS, INHERITS, USES_TYPE). Use this when you need to find
    related/connected code — e.g., 'what methods does class X have',
    'what calls function Y', or 'show the inheritance hierarchy'."""
    results = hybrid_retrieve(
        query,
        vector_top_k=vector_top_k,
        graph_hops=graph_hops,
        max_graph_nodes=max_graph_nodes,
        graph_type="baseline",
    )
    return _truncate_results(results)


@tool
def read_symbol_source(symbol_name: str) -> str:
    """Look up a specific code symbol by exact name. Use when you already know
    the name of a function/class and want its full source code."""
    results = vector_only(symbol_name, top_k=3)
    # For targeted lookups, show full source (no truncation on doc length)
    return _truncate_results(results, max_results=3, max_doc_len=2000)
