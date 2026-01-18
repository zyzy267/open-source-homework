import ast
import os
import re
import sys
import json
from queue import Queue
from copy import deepcopy
from core import *
from core.source_visitor import SourceVisitor
from wheel_inspect import inspect_wheel
import tarfile
from zipfile import ZipFile
from packaging.version import parse as parse_version
import networkx as nx
import argparse
import multiprocessing
from itertools import repeat
import shutil
import pickle


cwd = os.getcwd()
#error_log = r'/home/haowei/s2/error_log_return_type_history.txt'
error_log = os.path.join(cwd, "error_log_removed_history.txt")

class Tree:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.children = []
        self.parent = None
        self.cargo = {}
        self.api_alias = {}
        self.source = ''
        self.ast = None
        self.return_type_dict=None
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))

class ModuleOrPackageNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.children = []
        self.parent = None
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))

class ClassNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.children = []
        self.aliases = set()
        self.default_values = None
        self.source = None
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))


class ClassAliasNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.children = []
        self.real_class = None
        self.default_values = None
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))

class APINode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.source = None
        self.aliases = set()
        self.ast = None
        self.kws=None
        self.default_values=None
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))


class APIAliasNode:
    def __init__(self, name):
        self.name = name
        self.full_name = None
        self.parent = None
        self.source = None
        self.real_API = None
        self.kws=None
        self.default_values=None
    def __str__(self):
        return str(self.name)
    def __hash__(self):
        return hash(id(self))


class GetFunctionNodeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.result = {}
    def visit_FunctionDef(self, node):
        if node.name not in self.result:
            self.result[node.name] = node
        return node


class GetClassNodeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.result = {}
    def visit_ClassDef(self, node):
        self.result[node.name] = node
        return node


def parse_import(tree):
    module_item_dict = {}
    try:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None and node.level not in module_item_dict:
                    module_item_dict[node.level] = []
                elif node.module not in module_item_dict:
                   module_item_dict[node.module] = []
                items = [nn.__dict__ for nn in node.names]
                for d in items:
                    if node.module is None:
                        module_item_dict[node.level].append(d['name'])
                    else:
                        module_item_dict[node.module].append(d['name'])

        return module_item_dict
    except(AttributeError):
        return None


def gen_AST(filename):
    try:
        source = open(filename).read()
        tree = ast.parse(source, mode='exec')
        return tree
    except (SyntaxError,UnicodeDecodeError,):  # to avoid non-python code
        pass
        return None


def parse_pyx(filename):
    lines = open(filename).readlines()
    all_func_names = []
    for line in lines:
        names = re.findall(r'def ([\s\S]*?)\(', str(line))
        if len(names)>0:
            all_func_names.append(names[0])


def extract_class(filename):
    try:
        print(filename)
        source = open(filename).read()
        tree = ast.parse(source, mode='exec')
        visitor = SourceVisitor()
        visitor.visit(tree)
        print('testing')
        return visitor.result, tree
    except Exception as e:  # to avoid non-python code
        # fail passing python3
        if filename[-3:] == 'pyx':
            parse_pyx(filename)
        return {}, None  # return empty


def extract_class_from_source(source):
    try:
        tree = ast.parse(source, mode='exec')
        visitor = SourceVisitor()
        visitor.visit(tree)
        return visitor.result, tree
    except Exception as e:  # to avoid non-python code
        #if filename[-3:] == 'pyx':
        #    #print(filename)
        #    parse_pyx(filename)
        print(e)
        return {}, None# return empty

def build_dir_tree(node):
    if node.name in ['test', 'tests', 'testing']:
        return
    if os.path.isdir(node.name) is True:
        os.chdir(node.name)
        items  = os.listdir('.')

        for item in items:
            child_node = Tree(item)
            child_node.parent =  node
            build_dir_tree(child_node)
            node.children.append(child_node)
        os.chdir('..')
    else:
        # this is a file
        if node.name.endswith('.py'):
            source = open(node.name, 'rb').read()
            node.source = source.decode("utf-8", errors="ignore")
            res, tree = extract_class_from_source(node.source)
            node.cargo = res
            node.ast = tree

def leaf2root(node):
    tmp_node = node
    path_to_root = []
    # not init.py
    while tmp_node is not None:
        path_to_root.append(tmp_node.name)
        tmp_node = tmp_node.parent
    if node.name == '__init__.py':
        path_to_root = path_to_root[1:]
        path_name = ".".join(reversed(path_to_root))
        return path_name
    else:
        path_name = ".".join(reversed(path_to_root[1:]))
        path_name = "{}.{}".format(path_name, node.name.split('.')[0])
        return path_name

def pf_leaf2root(node):
    if isinstance(node,ClassNode) or isinstance(node,APINode) or isinstance(node,ClassAliasNode) or isinstance(node,APIAliasNode):
        return node.full_name
    tmp_node = node
    path_to_root = []
    # not init.py
    while tmp_node is not None:
        path_to_root.append(tmp_node.name)
        tmp_node = tmp_node.parent
    if isinstance(node,APINode) and node.name[0].isupper():
        path_to_root = path_to_root[1:]
        path_name = ".".join(reversed(path_to_root))
        return path_name
    else:
        path_name = ".".join(reversed(path_to_root[1:]))
        path_name = "{}.{}".format(path_name, node.name)
        return path_name


def find_child_by_name(node, name):
    for ch in node.children:
        if ch.name == name:
            return ch
    return None


def find_node_by_name(nodes, name):
    for node in nodes:
        if node.name == name or node.name.rstrip('.py') == name:
            return node
    return None


def go_to_that_node(root, cur_node, visit_path):
    route_node_names = visit_path.split('.')
    route_length = len(route_node_names)
    tmp_node = None
    # go to the siblings of the current node
    tmp_node =  find_node_by_name(cur_node.parent.children, route_node_names[0])
    if tmp_node is not None:
        for i in range(1,route_length):
            tmp_node =  find_node_by_name(tmp_node.children, route_node_names[i])
            if tmp_node is None:
                break
    # from the topmost
    elif route_node_names[0] == root.name:
        tmp_node = root
        for i in range(1,route_length):
            tmp_node =  find_node_by_name(tmp_node.children, route_node_names[i])
            if tmp_node is None:
                break
        return tmp_node
    # from its parent
    elif route_node_names[0] == cur_node.parent.name:
        tmp_node = cur_node.parent
        for i in range(1,route_length):
            tmp_node =  find_node_by_name(tmp_node.children, route_node_names[i])
            if tmp_node is None:
                break

    # we are still in the directory
    if tmp_node is not None and tmp_node.name.endswith('.py') is not True:
       tmp_node =  find_node_by_name(tmp_node.children, '__init__.py')

    return tmp_node

def tree_infer_levels(root_node,output_dir_store_src):
    API_name_lst = []
    api_alias_map = {}
    leaf_stack = []
    working_queue = []
    working_queue.append(root_node)

    # bfs to search all I leafs
    while len(working_queue)>0:
        tmp_node = working_queue.pop(0)
        if tmp_node.name.endswith('.py') == True:
            leaf_stack.append(tmp_node)
        working_queue.extend(tmp_node.children)
    tmp_dst_node_map={}
    # visit all elements from the stack
    for node in leaf_stack[::-1]:
        # private modules
        if node.name!='__init__.py' and node.name[0]=='_':
            continue

        module_item_dict = parse_import(node.ast)
        if module_item_dict is None:
            continue

        for k, v in module_item_dict.items():
            if k is None or isinstance(k, int):
                continue
            dst_node = go_to_that_node(root_node, node, k)
            if dst_node is not None:
                if v[0] =='*':
                    for k_ch, v_ch in dst_node.cargo.items():
                        #node.cargo[k_ch] = v_ch
                        if dst_node not in tmp_dst_node_map:
                            dst_API_prefix = leaf2root(dst_node)
                            tmp_dst_node_map[dst_node]=dst_API_prefix
                        node.api_alias[k_ch]=tmp_dst_node_map[dst_node]
                    for k_ch,v_ch in dst_node.api_alias.items():
                        node.api_alias[k_ch]=dst_node.api_alias[k_ch]
                else:
                    for api in v:
                        if api in dst_node.cargo:
                            #node.cargo[api]= dst_node.cargo[api]
                            if dst_node not in tmp_dst_node_map:
                                dst_API_prefix = leaf2root(dst_node)
                                tmp_dst_node_map[dst_node] = dst_API_prefix
                            node.api_alias[api] = tmp_dst_node_map[dst_node]
                        if api in dst_node.api_alias:
                            node.api_alias[api] = dst_node.api_alias[api]
            else:
                pass
        if node.name=='__init__.py':
            node.parent.cargo=node.cargo
            node.parent.source = node.source
            node.parent.ast = node.ast
            node.parent.api_alias=node.api_alias

    # construct profile tree
    pf_root_node = ModuleOrPackageNode(root_node.name.split('.')[0])
    pf_root_node.full_name=pf_root_node.name
    child_nodes = root_node.children
    construct_tree_for_profile(child_nodes,pf_root_node,output_dir_store_src)

    for node in leaf_stack:
        API_prefix = leaf2root(node)
        store_the_alias_info(pf_root_node, node.api_alias, API_prefix)
    pf_leaf_stack = []
    pf_working_queue = []
    pf_working_queue.append(pf_root_node)

    # bfs to search all I leafs
    while len(pf_working_queue) > 0:
        tmp_node = pf_working_queue.pop(0)
        pf_leaf_stack.append(tmp_node)
        if hasattr(tmp_node,"children"):
            pf_working_queue.extend(tmp_node.children)

    for node in pf_leaf_stack:
        API_full=pf_leaf2root(node)
        node.full_name = API_full


    return pf_root_node, pf_leaf_stack



def construct_pf_node_if_not_exist(API_prefix):
    path = API_prefix.split(".")
    pass


def store_the_alias_info(pf_root_node,alias_map,API_prefix):
    pf_node = go_to_api_node_from_root(pf_root_node,API_prefix)
    if not pf_node:
        raise Exception("cannot find alias node!")
    for api,dst_API_prefix in alias_map.items():
        pf_dst_node = go_to_api_node_from_root(pf_root_node,dst_API_prefix+"."+api)
        if pf_dst_node:
            #construct a node here
            # if api class:
            if isinstance(pf_dst_node, ClassNode):
                pf_alias_node = ClassAliasNode(api)
                pf_alias_node.full_name = API_prefix + "." + api
                pf_alias_node.parent = pf_node
                pf_node.children.append(pf_alias_node)
                pf_alias_node.real_class = pf_dst_node
            elif isinstance(pf_dst_node, APINode):
                pf_alias_node = APIAliasNode(api)
                pf_alias_node.full_name=API_prefix+"."+api
                pf_alias_node.parent=pf_node
                pf_node.children.append(pf_alias_node)
                pf_alias_node.real_API=pf_dst_node
            else:
                raise Exception("cannot create alias node")
            pf_dst_node.aliases.add(pf_alias_node)
            #pf_dst_node.aliases.add(API_prefix+"."+api)
            #class node
            if isinstance(pf_dst_node,ClassNode):
                for child in pf_dst_node.children:
                    child_alias_node = APIAliasNode(child.name)
                    if child_alias_node.name == pf_dst_node.name:
                        child_alias_node.full_name = API_prefix + "." + pf_dst_node.name
                    else:
                        child_alias_node.full_name = API_prefix + "." + pf_dst_node.name + "." + child.name
                    child_alias_node.parent = pf_alias_node
                    pf_alias_node.children.append(child_alias_node)
                    child_alias_node.real_API = child
                    child.aliases.add(child_alias_node)


def go_to_api_node_from_root(root_node,acces_path):
    acces_path_list = acces_path.split(".")
    tmp_node = root_node
    for i in acces_path_list[1:]:
        pas = False
        for child in tmp_node.children:
            if child.name == i:
                tmp_node = child
                pas=True
                break
        if not pas:
            return None
    return tmp_node




def construct_tree_for_profile(child_nodes,pf_parent_node,output_dir_store_src):
    for child_node in child_nodes:
        pf_child_node = ModuleOrPackageNode(child_node.name.split('.')[0])
        API_prefix = leaf2root(child_node)
        pf_child_node.full_name=API_prefix
        pf_child_node.parent=pf_parent_node
        for k,v in child_node.cargo.items():
            if k == "Categorical":
                print("here")
            if k[0] == '_':
                continue
            # this is a function def
            if isinstance(v, tuple):
                if k[0] != '_':
                    func_node = APINode(k)
                    func_node.full_name = API_prefix+"."+k
                    func_node.kws=v[0]
                    func_node.default_values=v[1]
                    pf_child_node.children.append(func_node)
                    func_node.parent=pf_child_node
                    get_functin_node_visitor = GetFunctionNodeVisitor()
                    get_functin_node_visitor.visit(child_node.ast)
                    ast_node = get_functin_node_visitor.result[k]
                    func_node.source=ast.get_source_segment(child_node.source, ast_node)
                    file_path = os.path.join(output_dir_store_src,func_node.full_name)+".py"
                    with open(file_path,"w",encoding="utf-8") as f:
                        f.write(func_node.source)
                    func_node.source=file_path
            elif isinstance(v, dict):
                cls_node = ClassNode(k)
                cls_node.full_name = API_prefix + "." + k
                pf_child_node.children.append(cls_node)
                cls_node.parent=pf_child_node
                get_class_node_visitor = GetClassNodeVisitor()
                get_class_node_visitor.visit(child_node.ast)
                class_ast_node = get_class_node_visitor.result[k]
                cls_node.ast = class_ast_node
                cls_node.source = ast.get_source_segment(child_node.source, class_ast_node)
                # there is a constructor
                if '__init__' in v:
                    args = v['__init__']
                    func_node = APINode(k)
                    func_node.full_name = API_prefix + "." + k
                    func_node.kws = args[0]
                    func_node.default_values = args[1]
                    cls_node.children.append(func_node)
                    func_node.parent=cls_node
                    cls_node.kws = args[0]
                    cls_node.default_values = args[1]
                    get_functin_node_visitor = GetFunctionNodeVisitor()
                    get_functin_node_visitor.visit(cls_node.ast)
                    ast_node = get_functin_node_visitor.result['__init__']
                    func_node.source = ast.get_source_segment(child_node.source, ast_node)
                    file_path = os.path.join(output_dir_store_src, func_node.full_name) + ".__init__.py"
                    print(file_path)
                    with open(file_path, "w",encoding="utf-8") as f:
                        f.write(func_node.source)
                    func_node.source = file_path

                # there is no a constructor
                else:
                    args = ([], "")
                    func_node = APINode(k)
                    func_node.full_name = API_prefix + "." + k
                    func_node.kws = args[0]
                    func_node.default_values = args[1]
                    cls_node.children.append(func_node)
                    func_node.parent = cls_node
                    cls_node.kws = args[0]
                    cls_node.default_values = args[1]
                    func_node.source=""

                for f_name, args in v.items():
                    if f_name[0] != '_':  # private functions
                        func_node = APINode(f_name)
                        func_node.full_name = API_prefix + "." + k+"."+f_name
                        func_node.kws = args[0]
                        func_node.default_values = args[1]
                        cls_node.children.append(func_node)
                        func_node.parent = cls_node
                        get_functin_node_visitor = GetFunctionNodeVisitor()
                        get_functin_node_visitor.visit(cls_node.ast)
                        ast_node = get_functin_node_visitor.result[f_name]
                        func_node.source = ast.get_source_segment(child_node.source, ast_node)
                        file_path = os.path.join(output_dir_store_src, func_node.full_name) + ".py"
                        with open(file_path, "w",encoding="utf-8") as f:
                            f.write(func_node.source)
                        func_node.source = file_path
                cls_node.ast = None
                file_path = os.path.join(output_dir_store_src, cls_node.full_name) + ".py"
                with open(file_path, "w",encoding="utf-8") as f:
                    f.write(cls_node.source)
                cls_node.source = file_path
        pf_parent_node.children.append(pf_child_node)
        construct_tree_for_profile(child_node.children,pf_child_node,output_dir_store_src)


def make_API_full_name_alias_map(meta_data, API_prefix):
    API_map = {}
    for api, dst_node in meta_data.items():
        if api[0] == '_':
            continue
        full_api_string = API_prefix+"."+api
        dst_node_API_prefix = leaf2root(dst_node)
        if api not in dst_node.cargo:
            print("error!")
        dst_node_full_api_string = dst_node_API_prefix+"."+api
        API_map[full_api_string] = dst_node_full_api_string
    return API_map


def make_API_full_name(meta_data, API_prefix):
    API_lst = []
    for k, v in meta_data.items():
        # to be revised
        if k[0] == '_':
            continue      # private functions or classes
        # this is a function def
        if isinstance(v, tuple):
            if k[0] != '_':
                API_name = "{}.{},{},{},{}".format(API_prefix, k, ";".join(v[0]), v[1], "func")
                API_lst.append(API_name)
        # this is a class
        elif isinstance(v, dict):
            # there is a constructor
            if '__init__' in v:
                args = v['__init__']
                API_name = "{}.{},{},{},{}".format(API_prefix, k, ";".join(args[0]), args[1], "cls")
                API_lst.append(API_name)
            # there is no a constructor
            else:
                args = ([], "")
                API_name = "{}.{},{},{},{}".format(API_prefix,k, ";".join(args[0]), args[1], "cls")
                API_lst.append(API_name)

            for f_name, args in v.items():
                if f_name[0] != '_':  # private functions
                    API_name = "{}.{}.{},{},{},{}".format(API_prefix, k, f_name, ";".join(args[0]), args[1], "cls_func")
                    API_lst.append(API_name)

    return API_lst
def search_targets(root_dir, targets):
     entry_points = []
     for root, dirs, files in os.walk(root_dir):
         n_found = 0
         for t in targets:
             if t in dirs :
                entry_points.append(os.path.join(root, t))
                n_found += 1
             elif t+'.py' in files:
                 entry_points.append(os.path.join(root, t+'.py'))
                 n_found += 1
         if n_found == len(targets):
             return entry_points
     return None
# filter wheel
# notice we will add egginfo soon
def process_wheel(path, l_name):
    # there will be multiple wheel files
    res = []
    all_file_names = os.listdir(path)
    whl_final = ''
    max_py_ver = ''
    for fn in all_file_names:
        if fn.endswith('.whl') and (fn.find('linux')>=0 or fn.find('any')>=0):  # this is a wheel
            whl_path = os.path.join(path, fn)
            try:
                output = inspect_wheel(whl_path)
                if output['pyver'][-1] > max_py_ver:  # -1 means the last one. Use the biggest version number
                    max_py_ver = output['pyver'][-1]
                    whl_final = fn
            except Exception as e:
                print("failed to handle {}".format(whl_path))
                print(e)
                with open(error_log, 'a') as f:
                    f.write("Failed to handle {} ".format(whl_path) + "\n")
    if whl_final != '':
        whl_path = os.path.join(path, whl_final)
        output = inspect_wheel(whl_path)
        # print(output.keys())
        if 'top_level' not in output['dist_info']:
            top_levels = [l_name]
        else:
            top_levels = output['dist_info']['top_level']

        with ZipFile(whl_path, 'r') as zipObj:
           # Extract all the contents of zip file in current directory
           source_dir = os.path.join(path, 'tmp')
           if not os.path.exists(source_dir):
               zipObj.extractall(source_dir)
        entry_points = search_targets(source_dir, top_levels)
        return entry_points
    return None

def process_single_module(module_path,output_dir_store_src):
    pf_tree = None
    pf_leaf_stack={}
    # process other modules !!!
    if os.path.isfile(module_path):
        first_name = os.path.basename(module_path)
        # process a single file module
        root_node = Tree(first_name)
        build_dir_tree(root_node)
        pf_tree, pf_leaf_stack = tree_infer_levels(root_node,output_dir_store_src)
    else:
        first_name = os.path.basename(module_path)
        working_dir = os.path.dirname(module_path)
        path = []
        cwd = os.getcwd() # save current working dir
        os.chdir(working_dir)
        root_node = Tree(first_name)
        build_dir_tree(root_node)
        pf_tree, pf_leaf_stack = tree_infer_levels(root_node,output_dir_store_src)
        os.chdir(cwd) # go back cwd
    return pf_tree, pf_leaf_stack

def map_API(lib_dir, output_dir, output_dir_store_src):
    # try:
    lib_name = os.path.basename(lib_dir)
    if os.path.exists(os.path.join(output_dir, "{}.json".format(lib_name))):
        print("skip {}", lib_name)
        return
    versions = os.listdir(lib_dir)
    versions.sort(key=lambda x: parse_version(x))

    API_data = {"module": [], "API": {}, "version": []}
    API_data['version'] = versions

    for v in versions:
        v_dir = os.path.join(lib_dir, v)
        output_v_dir=os.path.join(os.path.join(output_dir, lib_name),v)
        if output_dir_store_src.startswith("./"):
            output_dir_store_src=output_dir_store_src[2:]
        output_store_src_v = os.path.join(os.path.join(cwd,output_dir_store_src),v)
        if not os.path.exists(output_v_dir):
            os.makedirs(output_v_dir)
        if not os.path.exists(output_store_src_v):
            os.makedirs(output_store_src_v)
        #if os.path.exists(os.path.join(output_dir, "{}_{}.json".format(lib_name, v))):
            #print(lib_name+v+" skip")
            #continue

        print(v_dir)
        entry_points = process_wheel(v_dir, lib_name)
        if entry_points is not None:
            API_data['module'] = entry_points
            API_list = []
            API_alias_map = {}
            API_alias_map_part2 = {}
            for ep in entry_points:
                try:
                    pf_tree, pf_leaf_stack = process_single_module(ep, output_store_src_v)  # finish one version
                    if pf_tree:
                        pkg_name = pf_tree.name
                        with open(os.path.join(output_v_dir, "{}.pickle".format(pkg_name)), 'wb') as f:
                            pickle.dump(pf_tree, f, pickle.HIGHEST_PROTOCOL)

                except Exception as e:
                    os.chdir(cwd)
                    print("Error: "+str(e))
                    with open(error_log, 'a') as f:
                        f.write("Error: {}, {}\n".format("{}_{}.json".format(lib_name, v), str(e)))


        if os.path.exists(os.path.join(v_dir, 'tmp')):
            try:
                shutil.rmtree(os.path.join(v_dir, 'tmp'))
            except OSError as e:
                print("Error: %s - %s." % (e.filename, e.strerror))
                with open(error_log, 'a') as f:
                    f.write("Error: %s - %s.\n" % (e.filename, e.strerror))



def main():
    parser = argparse.ArgumentParser(
        description="download all versions of a library")
    parser.add_argument('path', metavar='lib_database', type=str,
                        help='The path to library database')
    parser.add_argument('output_path', metavar='output_json_directory', type=str,
                        help='The path for json output')
    parser.add_argument('output_dir_store_src', metavar='output_json_directory', type=str,
                        help='The path for json output')
    parser.add_argument('-n', metavar='parallel_number', type=str,
                        help='The number of parallel works, default is 15', default=1)
    with open("./lib_names.txt") as f:
        lib_list = f.read().splitlines()[:200]
    args = parser.parse_args()
    database_dir = args.path
    output_dir = args.output_path
    output_dir_store_src = args.output_dir_store_src
    number = int(args.n)
    lib_dirs = [os.path.join(database_dir, lib_dir) for lib_dir in lib_list if
                os.path.isdir(os.path.join(database_dir, lib_dir))]
    #lib_dirs = [os.path.join(database_dir, lib_dir) for lib_dir in os.listdir(database_dir) if
    #            os.path.isdir(os.path.join(database_dir, lib_dir))]
    if './data/sda/pypi_libs/udata' in lib_dirs:
        lib_dirs.remove('/data/sda/pypi_libs/udata')
    #with multiprocessing.Pool(processes=number) as pool:
        #pool.starmap(map_API, zip(lib_dirs, repeat(output_dir),repeat(output_dir_store_src)))
    map_API(lib_dirs[0],output_dir,output_dir_store_src)

if __name__ == '__main__':
    #a,b=process_single_module(r"C:\Users\Bill Quan\Downloads\pandas-0.23.0-cp36-cp36m-manylinux1_x86_64\pandas")
    #with open(os.path.join(".", "pandas_0.23.0rc22.json"), 'w') as f:
        #f.write(json.dumps({"api_list": a}))
    #with open(os.path.join(".", "pandas_0.23.0rc2_alias_map.json"), 'w') as f:
        #json.dump(b,f)
    # a = map_API("./New folder/requests", "./test_results")
    # print(a)
    main()