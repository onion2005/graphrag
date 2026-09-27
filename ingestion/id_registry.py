import hashlib
from pathlib import Path


def make_node_id(file_path: str | Path, symbol_name: str, symbol_type: str, repo_root: str | Path | None = None, repo_name: str | None = None) -> str:
    """
    Generate a stable 16-char hex ID for a code symbol.

    Key format: [<repo_name>/]<relative_file_path>:<symbol_name>:<symbol_type>
    e.g. "httpx/httpx/client.py:Client:class"

    If repo_root is provided, file_path is made relative to it.
    If repo_name is provided, it's prepended to the path for cross-repo uniqueness.
    """
    path = Path(file_path)
    if repo_root is not None:
        path = path.relative_to(Path(repo_root))
    path_str = path.as_posix()
    if repo_name:
        path_str = f"{repo_name}/{path_str}"
    key = f"{path_str}:{symbol_name}:{symbol_type}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def make_chunk_id(file_path: str | Path, symbol_name: str, repo_root: str | Path | None = None, repo_name: str | None = None) -> str:
    """
    Generate a chunk ID for vector storage.

    Uses the same hash scheme as make_node_id with symbol_type='chunk',
    so graph node IDs and chunk IDs share the same namespace and format.
    """
    return make_node_id(file_path, symbol_name, "chunk", repo_root=repo_root, repo_name=repo_name)
