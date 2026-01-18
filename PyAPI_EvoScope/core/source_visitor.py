import ast
from .class_visitor import ClassVisitor
from .fun_def_visitor import FunDefVisitor

def get_keywords(node):
    args = node.args
    arg_names = []
    defaults = args.defaults
    for arg in args.args:
        arg_names += [arg.arg]
    #return (arg_names, len(defaults))
    return (arg_names, defaults)


class SourceVisitor(ast.NodeVisitor):
    def __init__(self):
        self.result = {}
    def visit_FunctionDef(self, node):
        kw_names = get_keywords(node)
        self.result[node.name] = kw_names
        return node
    def visit_ClassDef(self, node):
        visitor = ClassVisitor()
        visitor.visit(node)
        self.result[node.name] = visitor.result
        return node

class RemoveWeakVisitor(ast.NodeVisitor):
    def __init__(self):
        self.call_name = set()
        self.class_def = set()
    def visit_Name(self, node):
        self.call_name.add(node.id)
        return node
    def visit_ClassDef(self, node):
        self.class_def.add(node.name)
        rwc_visitor = RemoveWeakClassVisitor()
        rwc_visitor.visit(node)
        for item in rwc_visitor.call_name:
            self.call_name.add(item)
        return node


class RWFunctionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.func_def = set()
        self.class_def = set()
    def visit_FuncDef(self, node):
        self.func_def.add(node.name)
        return node


class RemoveWeakClassVisitor(ast.NodeVisitor):
    def __init__(self):
        self.call_name = set()
    def visit_Call(self, node):
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                self.call_name.add(n.id)
        return node