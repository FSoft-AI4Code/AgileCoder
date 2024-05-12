import ast
import os

def extract_imports(filename):
    """Extract import statements from a Python source file."""
    with open(filename, 'r') as file:
        tree = ast.parse(file.read(), filename=filename)

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    return imports

def build_dependency_graph(directory):
    """Build a dependency graph for Python files in a directory."""
    graph = {}
    all_files = os.listdir(directory)
    all_modules = set(list(map(lambda x: x.replace(".py", ""), all_files)))
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                imports = list(map(lambda x: x + '.py', set(extract_imports(filepath)) & set(all_modules)))
                if len(imports) == 0: continue
                graph[file] = imports
    return graph

def dfs(adj_list, node, visited, result):
    visited.add(node)
    if node in adj_list:
        for neighbor in adj_list[node]:
            if neighbor not in visited:
                dfs(adj_list, neighbor, visited, result)
    result.append(node)

def get_test_order(adj_list):
    if not adj_list:
        return []

    visited = set()
    test_order = []

    # Find leaf nodes (test suites)
    leaf_nodes = [node for node in adj_list if node.startswith("test")]

    # Perform DFS starting from each leaf node
    for leaf_node in leaf_nodes:
        if leaf_node not in visited:
            dfs(adj_list, leaf_node, visited, test_order)
    print(test_order)
    return test_order