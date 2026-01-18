import ast
from  _ast import *
import pkgutil
import os
import sys

def iter_fields(node):
    """
    Yield a tuple of ``(fieldname, value)`` for each field in ``node._fields``
    that is present on *node*.
    """
    for field in node._fields:
        try:
            yield field, getattr(node, field)
        except AttributeError:
            pass

def iter_child_nodes(node):
    """
    Yield all direct child nodes of *node*, that is, all fields that are nodes
    and all items of fields that are lists of nodes.
    """
    for name, field in iter_fields(node):
        if isinstance(field, AST):
            yield field
        elif isinstance(field, list):
            for item in field:
                if isinstance(item, AST):
                    yield item

def find_local_modules(import_smts):
    smts = "\n".join(import_smts)
    tree = ast.parse(smts, mode='exec')
    search_path = ['.']
    module_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) :
            for nn in node.names:
                module_names.add(nn.name.split('.')[0])
        if isinstance(node, ast.ImportFrom):
            if node.level==2:
                search_path += ['..']
            if node.module is not None:
                module_names.add(node.module.split('.')[0])
            else:
                for nn in node.names:
                    module_names.add(nn.name)
    module_name_plus = ['random', 'unittest', 'warning', 'os', 'pandas', 'IPython', 'seaborn', 'matplotlib', 'sklearn', 'numpy', 'scipy', 'math', 'matplotlib']
    search_path = list(set(search_path))
    all_modules = [x[1] for x in pkgutil.iter_modules(path=search_path)]
    all_modules += list(sys.builtin_module_names) + module_name_plus
    result = []
    for m_name in module_names:
        if m_name not in all_modules:
            result  += [m_name]
    return result

def get_path_by_extension(root_dir, num_of_required_paths, flag='.ipynb'):
    paths = []
    for root, dirs, files in os.walk(root_dir):
        files = [f for f in files if not f[0] == '.'] 
        dirs[:] = [d for d in dirs if not d[0] == '.']
        for file in files:
            if file.endswith(flag):
                paths.append(os.path.join(root, file))
                if len(paths) == num_of_required_paths:
                    return paths
    return paths


# 在 util.py 中添加以下函数
def get_code_list(filename):
    """
    从 Jupyter Notebook (.ipynb) 文件中提取所有代码单元格的内容
    如果文件是 .py 文件，则读取整个文件内容并返回单元素列表
    """
    import json

    if filename.endswith('.py'):
        with open(filename, 'r', encoding='utf-8') as f:
            return [f.read()]
    elif filename.endswith('.ipynb'):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                nb = json.load(f)

            code_cells = []
            for cell in nb.get('cells', []):
                if cell.get('cell_type') == 'code':
                    # 获取代码单元格内容
                    source = cell.get('source', [])
                    if isinstance(source, list):
                        code_cells.append(''.join(source))
                    else:
                        code_cells.append(source)
            return code_cells
        except Exception as e:
            print(f"Error reading notebook {filename}: {e}")
            return []
    else:
        return []