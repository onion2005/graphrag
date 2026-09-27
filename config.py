import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Corpus
REPO_ROOT = Path("corpus/httpx")

# Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "changeme")

# LLM
LLM_MODEL = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "graphrag-local-key-change-me")
LLM_TEMPERATURE = 0.1
LLM_MAX_PAIRS = 500
LLM_MIN_CONFIDENCE = 0.6

# Chroma
CHROMA_PERSIST_DIR = "chroma_store"
CHROMA_COLLECTION = "code_nodes"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Retrieval
VECTOR_TOP_K = 5
GRAPH_HOPS = 1
MAX_GRAPH_NODES = 20
HOP_DECAY = 0.8
MIN_SIMILARITY = 0.0
