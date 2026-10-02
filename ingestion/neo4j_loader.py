from neo4j import GraphDatabase

import config


def get_driver():
    return GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))


def create_indexes(driver):
    with driver.session() as session:
        session.run("CREATE INDEX code_node_id IF NOT EXISTS FOR (n:CodeNode) ON (n.id)")


def load_nodes(driver, nodes: list[dict]):
    query = """
    UNWIND $nodes AS n
    MERGE (c:CodeNode {id: n.id})
    SET c.name = n.name,
        c.type = n.type,
        c.file = n.file,
        c.docstring = n.docstring,
        c.source_code = n.source_code,
        c.lineno = n.lineno,
        c.repo = n.repo,
        c.qualified_name = n.file + ':' + n.name + ':' + n.type
    """
    with driver.session() as session:
        session.run(query, nodes=nodes)


def load_baseline_edges(driver, edges: list[dict]):
    query = """
    UNWIND $edges AS e
    MATCH (a:CodeNode {id: e.source}), (b:CodeNode {id: e.target})
    MERGE (a)-[r:RELATES {type: e.type}]->(b)
    SET r.source = 'baseline'
    """
    with driver.session() as session:
        session.run(query, edges=edges)


def load_llm_edges(driver, edges: list[dict]):
    query = """
    UNWIND $edges AS e
    MATCH (a:CodeNode {id: e.source}), (b:CodeNode {id: e.target})
    MERGE (a)-[r:LLM_RELATES {type: e.type}]->(b)
    SET r.confidence = e.confidence,
        r.reason = e.reason,
        r.source = 'llm'
    """
    with driver.session() as session:
        session.run(query, edges=edges)


def load_cross_repo_edges(driver, edges: list[dict]):
    query = """
    UNWIND $edges AS e
    MATCH (a:CodeNode {id: e.source}), (b:CodeNode {id: e.target})
    MERGE (a)-[r:CROSS_REPO_RELATES {type: e.type}]->(b)
    SET r.confidence = e.confidence,
        r.reason = e.reason,
        r.source = 'llm_cross_repo'
    """
    with driver.session() as session:
        session.run(query, edges=edges)


def load_graphify_edges(driver, edges: list[dict]):
    query = """
    UNWIND $edges AS e
    MATCH (a:CodeNode {id: e.source}), (b:CodeNode {id: e.target})
    MERGE (a)-[r:GRAPHIFY_RELATES {type: e.type}]->(b)
    SET r.source = 'graphify'
    """
    with driver.session() as session:
        session.run(query, edges=edges)


def clear_graph(driver):
    with driver.session() as session:
        session.run("MATCH (n:CodeNode) DETACH DELETE n")


def load_baseline(nodes: list[dict], edges: list[dict], clear_first: bool = True):
    """Full baseline load: clear, index, nodes, edges."""
    driver = get_driver()
    try:
        if clear_first:
            clear_graph(driver)
        create_indexes(driver)
        load_nodes(driver, nodes)
        load_baseline_edges(driver, edges)
    finally:
        driver.close()
