import ast
from pathlib import Path

from ingestion.id_registry import make_node_id


def parse_file(file_path: Path, repo_root: Path, repo_name: str | None = None) -> tuple[list[dict], list[dict]]:
    """Parse a single Python file into nodes and baseline edges."""
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    nodes = []
    edges = []
    rel_path = file_path.relative_to(repo_root).as_posix()
    module_name = rel_path.replace("/", ".").removesuffix(".py")
    module_id = make_node_id(rel_path, module_name, "module", repo_name=repo_name)
    module_docstring = ast.get_docstring(tree) or ""

    # Prefix file path with repo name for multi-repo disambiguation
    display_path = f"{repo_name}/{rel_path}" if repo_name else rel_path

    nodes.append({
        "id": module_id,
        "file": display_path,
        "name": module_name,
        "type": "module",
        "source_code": "",
        "docstring": module_docstring,
        "lineno": 1,
        "repo": repo_name or "",
    })

    def _add_symbol(node, symbol_type, parent_id, class_name=None):
        qualified = f"{class_name}.{node.name}" if class_name else node.name
        node_id = make_node_id(rel_path, qualified, symbol_type, repo_name=repo_name)
        source_code = ast.get_source_segment(source, node) or ""
        docstring = ast.get_docstring(node) or ""

        nodes.append({
            "id": node_id,
            "file": display_path,
            "name": qualified,
            "type": symbol_type,
            "source_code": source_code,
            "docstring": docstring,
            "lineno": node.lineno,
            "repo": repo_name or "",
        })

        # CONTAINS: parent → this symbol
        edges.append({
            "source": parent_id,
            "target": node_id,
            "type": "CONTAINS",
            "source_label": "baseline",
        })

        # CALLS: detect function/method calls inside the body
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                callee_name = _resolve_call_name(child)
                if callee_name is not None:
                    callee_id = make_node_id(rel_path, callee_name, "function", repo_name=repo_name)
                    edges.append({
                        "source": node_id,
                        "target": callee_id,
                        "type": "CALLS",
                        "source_label": "baseline",
                    })

        return node_id

    # Top-level statements only
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_id = _add_symbol(node, "function", module_id)

            # USES_TYPE: function → type annotations
            for ann_name in _extract_type_names(node):
                ann_id = make_node_id(rel_path, ann_name, "class", repo_name=repo_name)
                edges.append({
                    "source": func_id,
                    "target": ann_id,
                    "type": "USES_TYPE",
                    "source_label": "baseline",
                })
        elif isinstance(node, ast.ClassDef):
            class_id = _add_symbol(node, "class", module_id)

            # INHERITS: class → base class
            for base in node.bases:
                base_name = _resolve_name(base)
                if base_name:
                    base_id = make_node_id(rel_path, base_name, "class", repo_name=repo_name)
                    edges.append({
                        "source": class_id,
                        "target": base_id,
                        "type": "INHERITS",
                        "source_label": "baseline",
                    })

            # Class → methods
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_id = _add_symbol(child, "function", class_id, class_name=node.name)

                    # USES_TYPE: method → type annotations
                    for ann_name in _extract_type_names(child):
                        ann_id = make_node_id(rel_path, ann_name, "class", repo_name=repo_name)
                        edges.append({
                            "source": method_id,
                            "target": ann_id,
                            "type": "USES_TYPE",
                            "source_label": "baseline",
                        })

    # IMPORTS: module → imported name
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[-1]
                target_id = make_node_id(rel_path, name, "import", repo_name=repo_name)
                edges.append({
                    "source": module_id,
                    "target": target_id,
                    "type": "IMPORTS",
                    "source_label": "baseline",
                    "module": alias.name,
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                target_id = make_node_id(rel_path, name, "import", repo_name=repo_name)
                edges.append({
                    "source": module_id,
                    "target": target_id,
                    "type": "IMPORTS",
                    "source_label": "baseline",
                    "module": module,
                })

    return nodes, edges


def _resolve_name(node: ast.expr) -> str | None:
    """Extract a name from an AST expression (Name or Attribute)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _extract_type_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract type annotation names from a function's args and return type."""
    names = []
    # Return type
    if func_node.returns:
        name = _resolve_name(func_node.returns)
        if name:
            names.append(name)
    # Argument annotations
    for arg in func_node.args.args + func_node.args.posonlyargs + func_node.args.kwonlyargs:
        if arg.annotation:
            name = _resolve_name(arg.annotation)
            if name:
                names.append(name)
    return names


def _resolve_call_name(call_node: ast.Call) -> str | None:
    """Extract a simple callee name from an ast.Call node."""
    func = call_node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def parse_repo(repo_root: Path, repo_name: str | None = None) -> tuple[list[dict], list[dict]]:
    """Walk a repo and parse all Python files."""
    all_nodes = []
    all_edges = []
    for py_file in sorted(repo_root.rglob("*.py")):
        try:
            nodes, edges = parse_file(py_file, repo_root, repo_name=repo_name)
            all_nodes.extend(nodes)
            all_edges.extend(edges)
        except SyntaxError:
            continue
    return all_nodes, all_edges
