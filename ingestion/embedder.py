import chromadb
from sentence_transformers import SentenceTransformer

import config


def build_chunk_text(node: dict) -> str:
    """Build the text chunk for embedding a node."""
    source_preview = node.get("source_code", "")[:300]
    return f"{node['type']}: {node['name']}\n{node.get('docstring', '')}\n{source_preview}"


def build_vector_store(nodes: list[dict]):
    """Embed all nodes and store in Chroma."""
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
    collection = client.get_or_create_collection(config.CHROMA_COLLECTION)

    # Deduplicate nodes by ID (e.g. property getter/setter pairs)
    seen = {}
    for n in nodes:
        if n["id"] not in seen:
            seen[n["id"]] = n
    unique_nodes = list(seen.values())

    ids = [n["id"] for n in unique_nodes]
    documents = [build_chunk_text(n) for n in unique_nodes]
    metadatas = [{"name": n["name"], "type": n["type"], "file": n["file"], "repo": n.get("repo", "")} for n in unique_nodes]
    embeddings = model.encode(documents, show_progress_bar=True).tolist()

    # Chroma has a batch size limit, insert in chunks of 5000
    batch_size = 5000
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.upsert(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
            embeddings=embeddings[i:end],
        )

    return collection
