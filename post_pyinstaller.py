import ast
import shutil
import os


# %% Get dist root directory name from *.spec
def parse_ast_tree(tree):
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == 'coll':  # Check for 'coll' variable in COLLECT
                for keyword in node.value.keywords:
                    if keyword.arg == 'name':  # Find the 'name' argument in COLLECT
                        return ast.literal_eval(keyword.value)


with open("main.spec") as f:
    spec = f.read()
spec_tree = ast.parse(spec)
dist_dir_name = parse_ast_tree(spec_tree)

# %% Add static files.
analysis_data = [
    ('header_csrf_token.json', '.'),
    ('header_login.json', '.'),
    ('request_usage.ps1', '.'),
]
for src, raw_dst in analysis_data:
    dst = os.path.join(f"dist/{dist_dir_name}", raw_dst)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(dst, os.path.basename(src)))
    else:
        # "copy" doesn't copy metadata, "copy2" does
        shutil.copy(src, dst)
