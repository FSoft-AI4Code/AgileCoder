import ast
import os

def extract_imports(filename):
    """Extract import statements from a Python source file."""
    try:
        with open(filename, 'r') as file:
            tree = ast.parse(file.read(), filename=filename)
    except:
        return []

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

def get_test_order(adj_list, testing_file_map):
    def dfs(node, visited, stack):
        visited.add(node)
        for neighbor in adj_list.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, visited, stack)
        stack.append(node)
    visited = set()
    stack = []

    # Call the DFS function for each node
    for node in adj_list:
        if node not in visited:
            dfs(node, visited, stack)

    stack = list(filter(lambda x: not (x.startswith('test') or x.split('.')[0].endswith('test')), stack))
    order = []
    for filename in stack:
        if filename in testing_file_map:
            order.extend(list(set(testing_file_map[filename])))
    # print('TEST ORDER:', order)
    return order