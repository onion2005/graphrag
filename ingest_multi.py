"""
Multi-repo ingestion: parse, embed, and load multiple repos into a shared graph + vector store.

Usage:
    python ingest_multi.py [--skip-llm] [--cross-repo-only]
"""
import argparse
import json
import sys

import config
from ingestion.parser import parse_repo
from ingestion.embedder import build_vector_store
from ingestion.neo4j_loader import (
    get_driver, clear_graph, create_indexes,
    load_nodes, load_baseline_edges, load_llm_edges, load_cross_repo_edges,
)
from ingestion.llm_extractor import extract_cross_repo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true", help="Skip cross-repo LLM extraction")
    parser.add_argument("--cross-repo-only", action="store_true", help="Only run cross-repo LLM extraction (skip parse/embed)")
    parser.add_argument("--max-pairs", type=int, default=500, help="Max LLM pairs per repo pair")
    args = parser.parse_args()

    repos = config.REPOS

    if not args.cross_repo_only:
        # 1. Parse all repos
        all_nodes = []
        all_edges = []
        nodes_by_repo = {}

        for repo_name, repo_path in repos.items():
            print(f"\nParsing {repo_name} from {repo_path}...")
            nodes, edges = parse_repo(repo_path, repo_name=repo_name)
            print(f"  {len(nodes)} nodes, {len(edges)} edges")
            all_nodes.extend(nodes)
            all_edges.extend(edges)
            nodes_by_repo[repo_name] = nodes

        print(f"\nTotal: {len(all_nodes)} nodes, {len(all_edges)} edges across {len(repos)} repos")

        # 2. Load into Neo4j
        print("\nLoading into Neo4j...")
        driver = get_driver()
        try:
            clear_graph(driver)
            create_indexes(driver)
            load_nodes(driver, all_nodes)
            load_baseline_edges(driver, all_edges)

            # Also load within-repo LLM edges if they exist
            try:
                with open("llm_edges_pruned.json") as f:
                    llm_edges = json.load(f)
                print(f"Loading {len(llm_edges)} within-repo LLM edges...")
                load_llm_edges(driver, llm_edges)
            except FileNotFoundError:
                print("No within-repo LLM edges found (llm_edges_pruned.json)")
        finally:
            driver.close()

        # 3. Build merged vector store
        print("\nBuilding merged vector store...")
        # Delete old store to avoid stale data
        import shutil
        import os
        if os.path.exists(config.CHROMA_PERSIST_DIR):
            shutil.rmtree(config.CHROMA_PERSIST_DIR)
        collection = build_vector_store(all_nodes)
        print(f"  {collection.count()} vectors stored")

        # Save nodes_by_repo for cross-repo extraction
        for repo_name, nodes in nodes_by_repo.items():
            with open(f"nodes_{repo_name}.json", "w") as f:
                json.dump(nodes, f)
    else:
        # Load previously saved nodes
        nodes_by_repo = {}
        for repo_name in repos:
            try:
                with open(f"nodes_{repo_name}.json") as f:
                    nodes_by_repo[repo_name] = json.load(f)
                print(f"Loaded {len(nodes_by_repo[repo_name])} nodes for {repo_name}")
            except FileNotFoundError:
                print(f"ERROR: nodes_{repo_name}.json not found. Run without --cross-repo-only first.")
                sys.exit(1)

    # 4. Cross-repo LLM extraction
    if not args.skip_llm:
        print("\nExtracting cross-repo LLM edges...")
        cross_edges = extract_cross_repo(
            nodes_by_repo,
            top_k_per_node=5,
            max_pairs=args.max_pairs,
        )

        print(f"\nLoading {len(cross_edges)} cross-repo edges into Neo4j...")
        driver = get_driver()
        try:
            load_cross_repo_edges(driver, cross_edges)
        finally:
            driver.close()

    # 5. Summary
    driver = get_driver()
    try:
        with driver.session() as s:
            node_count = s.run("MATCH (n:CodeNode) RETURN count(n) AS c").single()["c"]
            baseline_count = s.run("MATCH ()-[r:RELATES]->() RETURN count(r) AS c").single()["c"]
            llm_count = s.run("MATCH ()-[r:LLM_RELATES]->() RETURN count(r) AS c").single()["c"]
            cross_count = s.run("MATCH ()-[r:CROSS_REPO_RELATES]->() RETURN count(r) AS c").single()["c"]

            repos_in_graph = s.run("MATCH (n:CodeNode) RETURN DISTINCT n.repo AS repo, count(n) AS cnt").data()

        print(f"\n{'='*50}")
        print(f"  MULTI-REPO GRAPH SUMMARY")
        print(f"{'='*50}")
        print(f"Nodes:              {node_count}")
        print(f"AST edges:          {baseline_count}")
        print(f"LLM edges (intra):  {llm_count}")
        print(f"LLM edges (cross):  {cross_count}")
        for r in repos_in_graph:
            print(f"  {r['repo']}: {r['cnt']} nodes")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
