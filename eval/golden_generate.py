"""
Generate a golden evaluation dataset using LLM.

Reads the symbol index from Chroma, sends it to the LLM per category,
and produces query→expected_symbols pairs for human review.
"""
import json
import random
from datetime import datetime, timezone

import openai
import chromadb

import config

CATEGORIES = {
    "structural_navigation": (
        "Generate queries where the answer requires navigating code structure — "
        "finding methods of a class, understanding class hierarchies, or locating "
        "where a function is defined and what it calls. "
        "These queries should be answerable by following CONTAINS, CALLS, INHERITS edges."
    ),
    "semantic_similarity": (
        "Generate queries where the answer requires finding code that serves a similar "
        "purpose or implements similar logic, even if the implementations differ. "
        "For example, finding all authentication implementations, or all serialization methods. "
        "These queries test SIMILAR_TO relationships."
    ),
    "cross_file_dependency": (
        "Generate queries where the answer spans multiple files — a function in one module "
        "depends on a class in another, or configuration in one file affects behavior elsewhere. "
        "These queries test the system's ability to follow cross-file relationships."
    ),
    "api_surface": (
        "Generate queries about the public API — how to use a feature, what parameters "
        "a function accepts, what exceptions can be raised. These queries should map to "
        "specific public functions, classes, or methods that a developer would need to find."
    ),
}

QUERIES_PER_CATEGORY = 7
MAX_SYMBOLS_IN_PROMPT = 300  # Cap symbols sent to LLM to fit context window

PROMPT_TEMPLATE = """\
You are generating evaluation queries for a code retrieval system.

The system indexes a Python codebase (httpx — an HTTP client library). Given a natural language query, it retrieves relevant code symbols (functions, classes, modules).

Below is the complete symbol index — every symbol in the codebase:

{symbol_index}

## Task

{category_description}

Generate exactly {n} queries for this category. For each query, list the expected relevant symbols from the index above.

Rules:
- Only reference symbols that appear in the index above (exact name, file, type match)
- Each query should have 3-8 expected symbols
- Assign relevance grades: 3 = essential/primary, 2 = important/related, 1 = peripherally relevant
- At least 2 symbols per query should have relevance >= 2
- Queries should be realistic — things a developer would actually search for
- Vary the queries: don't repeat the same pattern

Respond with a JSON array only, no other text:
[
  {{
    "query": "How does httpx handle...",
    "expected_symbols": [
      {{"name": "SymbolName", "file": "path/to/file.py", "type": "class", "relevance": 3}},
      ...
    ]
  }}
]
"""


def get_symbol_index() -> list[dict]:
    """Load all symbols from Chroma metadata."""
    client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
    collection = client.get_collection(config.CHROMA_COLLECTION)

    result = collection.get(include=["metadatas"])
    symbols = []
    for meta in result["metadatas"]:
        symbols.append({
            "name": meta["name"],
            "type": meta["type"],
            "file": meta["file"],
        })
    return symbols


def format_symbol_index(symbols: list[dict]) -> str:
    """Format symbol index for the prompt."""
    by_file: dict[str, list[dict]] = {}
    for s in symbols:
        by_file.setdefault(s["file"], []).append(s)

    lines = []
    for file in sorted(by_file):
        lines.append(f"\n## {file}")
        for s in sorted(by_file[file], key=lambda x: x["name"]):
            lines.append(f"  - {s['type']}: {s['name']}")
    return "\n".join(lines)


def validate_symbols(queries: list[dict], symbol_index: list[dict]) -> list[dict]:
    """Check that every expected symbol matches an actual symbol. Drop invalid ones."""
    index_set = {(s["name"], s["file"], s["type"]) for s in symbol_index}

    validated = []
    total_dropped = 0

    for q in queries:
        valid_symbols = []
        for s in q["expected_symbols"]:
            key = (s["name"], s["file"], s["type"])
            if key in index_set:
                valid_symbols.append(s)
            else:
                print(f"  DROPPED: {s['name']} ({s['file']}, {s['type']}) — not in index")
                total_dropped += 1

        if len(valid_symbols) >= 2:
            q["expected_symbols"] = valid_symbols
            validated.append(q)
        else:
            print(f"  SKIPPED query '{q['query'][:50]}...' — too few valid symbols")

    if total_dropped:
        print(f"  Total symbols dropped: {total_dropped}")
    return validated


def generate_category(
    category: str,
    description: str,
    symbols: list[dict],
    client: openai.OpenAI,
) -> list[dict]:
    """Generate queries for one category."""
    # Sample symbols to fit context window of smaller models (seeded for reproducibility)
    if len(symbols) > MAX_SYMBOLS_IN_PROMPT:
        rng = random.Random(42)
        sampled = rng.sample(symbols, MAX_SYMBOLS_IN_PROMPT)
    else:
        sampled = symbols
    symbol_index_text = format_symbol_index(sampled)

    prompt = PROMPT_TEMPLATE.format(
        symbol_index=symbol_index_text,
        category_description=description,
        n=QUERIES_PER_CATEGORY,
    )

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        queries = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  Failed to parse LLM response for {category}: {e}")
        return []

    return queries


def generate_golden_dataset(output_path: str = "eval/golden_dataset.json"):
    """Generate full golden dataset across all categories."""
    print("Loading symbol index from Chroma...")
    symbols = get_symbol_index()
    print(f"  {len(symbols)} symbols loaded")

    client = openai.OpenAI(
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
    )

    all_queries = []
    query_id = 1

    for category, description in CATEGORIES.items():
        print(f"\nGenerating {QUERIES_PER_CATEGORY} queries for '{category}'...")

        queries = generate_category(category, description, symbols, client)
        print(f"  LLM returned {len(queries)} queries")

        queries = validate_symbols(queries, symbols)
        print(f"  {len(queries)} queries after validation")

        for q in queries:
            q["id"] = f"q{query_id:02d}"
            q["category"] = category
            query_id += 1

        all_queries.extend(queries)

    dataset = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": config.LLM_MODEL,
        "reviewed": False,
        "queries": all_queries,
    }

    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"\nDone: {len(all_queries)} queries saved to {output_path}")
    print("Review the file and set 'reviewed' to true when ready.")


if __name__ == "__main__":
    generate_golden_dataset()
