# Both edge types (baseline + LLM)
BOTH_ONE_HOP = """
UNWIND $entry_ids AS entry_id
MATCH (start:CodeNode {id: entry_id})-[:RELATES|LLM_RELATES]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, 1 AS hops
LIMIT $limit
"""

BOTH_TWO_HOP = """
UNWIND $entry_ids AS entry_id
MATCH path = (start:CodeNode {id: entry_id})-[:RELATES|LLM_RELATES*1..2]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
WITH neighbor, min(length(path)) AS hops
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, hops
LIMIT $limit
"""

# Baseline edges only (AST-derived)
BASELINE_ONE_HOP = """
UNWIND $entry_ids AS entry_id
MATCH (start:CodeNode {id: entry_id})-[:RELATES]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, 1 AS hops
LIMIT $limit
"""

BASELINE_TWO_HOP = """
UNWIND $entry_ids AS entry_id
MATCH path = (start:CodeNode {id: entry_id})-[:RELATES*1..2]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
WITH neighbor, min(length(path)) AS hops
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, hops
LIMIT $limit
"""

# LLM edges only
LLM_ONE_HOP = """
UNWIND $entry_ids AS entry_id
MATCH (start:CodeNode {id: entry_id})-[:LLM_RELATES]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, 1 AS hops
LIMIT $limit
"""

LLM_TWO_HOP = """
UNWIND $entry_ids AS entry_id
MATCH path = (start:CodeNode {id: entry_id})-[:LLM_RELATES*1..2]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
WITH neighbor, min(length(path)) AS hops
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, hops
LIMIT $limit
"""

# Cross-repo LLM edges only
CROSS_REPO_ONE_HOP = """
UNWIND $entry_ids AS entry_id
MATCH (start:CodeNode {id: entry_id})-[:CROSS_REPO_RELATES]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, 1 AS hops
LIMIT $limit
"""

CROSS_REPO_TWO_HOP = """
UNWIND $entry_ids AS entry_id
MATCH path = (start:CodeNode {id: entry_id})-[:CROSS_REPO_RELATES*1..2]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
WITH neighbor, min(length(path)) AS hops
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, hops
LIMIT $limit
"""

# AST + cross-repo LLM edges
AST_CROSS_ONE_HOP = """
UNWIND $entry_ids AS entry_id
MATCH (start:CodeNode {id: entry_id})-[:RELATES|CROSS_REPO_RELATES]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, 1 AS hops
LIMIT $limit
"""

AST_CROSS_TWO_HOP = """
UNWIND $entry_ids AS entry_id
MATCH path = (start:CodeNode {id: entry_id})-[:RELATES|CROSS_REPO_RELATES*1..2]-(neighbor:CodeNode)
WHERE NOT neighbor.id IN $entry_ids
WITH neighbor, min(length(path)) AS hops
RETURN DISTINCT neighbor.id AS id, neighbor.name AS name, neighbor.type AS type,
       neighbor.file AS file, neighbor.docstring AS docstring, hops
LIMIT $limit
"""

TEMPLATES = {
    "both":       {1: BOTH_ONE_HOP, 2: BOTH_TWO_HOP},
    "baseline":   {1: BASELINE_ONE_HOP, 2: BASELINE_TWO_HOP},
    "llm":        {1: LLM_ONE_HOP, 2: LLM_TWO_HOP},
    "cross_repo": {1: CROSS_REPO_ONE_HOP, 2: CROSS_REPO_TWO_HOP},
    "ast_cross":  {1: AST_CROSS_ONE_HOP, 2: AST_CROSS_TWO_HOP},
}
